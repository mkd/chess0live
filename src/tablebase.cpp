/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute it and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/tablebase.hpp"
#include "chess0live/position.hpp"

#include <tbprobe.h>

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <stdexcept>
#include <string_view>

namespace chess0live::tablebase {
namespace {

/** Fathom owns process-global mapped tables. A generation identifies exactly
 * one configuration; locking covers lifecycle as well as every probe because
 * upstream's root-probe thread-safety descriptions disagree.
 */
struct Backend {
    std::mutex mutex;
    std::uint64_t generation = 0;
    bool initialized = false;
};

Backend& backend() {
    static Backend state;
    return state;
}

void invalidate(Backend& state) {
    if (state.initialized) tb_free();
    state.initialized = false;
    if (++state.generation == 0) ++state.generation;
}

#ifdef _WIN32
constexpr char path_separator = ';';
#else
constexpr char path_separator = ':';
#endif

/** Check only simple download failures. Fathom's compressed payload decoder is
 * not a hostile-input parser; complete file validation belongs to published
 * table checksums. Canonical paths also avoid a later working-directory change
 * silently redirecting lazy table loads.
 */
std::string checked_path(const std::string& input) {
    if (input.find('\0') != std::string::npos)
        throw std::runtime_error("SyzygyPath contains a NUL byte");
    std::string result;
    std::size_t begin = 0;
    do {
        const auto end = input.find(path_separator, begin);
        const auto item = input.substr(begin, end == std::string::npos ? end : end - begin);
        if (item.empty()) throw std::runtime_error("SyzygyPath contains an empty directory");
        const auto directory = std::filesystem::canonical(item);
        if (!std::filesystem::is_directory(directory))
            throw std::runtime_error("SyzygyPath is not a directory: " + item);
        for (const auto& entry : std::filesystem::directory_iterator(directory)) {
            const auto extension = entry.path().extension().string();
            std::uint32_t magic = 0;
            if (extension == ".rtbw") magic = 0x5d23e871;
            else if (extension == ".rtbz") magic = 0xa50c66d7;
            else if (extension == ".rtbm") magic = 0x88ac504b;
            else continue;
            if (!entry.is_regular_file())
                throw std::runtime_error("Syzygy table is not a regular file: " + entry.path().string());
            const auto size = entry.file_size();
            // The generator pads a nonempty header/payload to 64 bytes before
            // appending its 16-byte checksum. A header-only 16-byte truncation
            // has the right congruence but cannot be a complete table.
            if (size < 80 || size % 64 != 16)
                throw std::runtime_error("Incomplete Syzygy table: " + entry.path().string());
            std::array<unsigned char, 4> bytes{};
            std::ifstream file(entry.path(), std::ios::binary);
            file.read(reinterpret_cast<char*>(bytes.data()), bytes.size());
            const auto observed = std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8)
                | (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
            if (!file || observed != magic)
                throw std::runtime_error("Unreadable or invalid Syzygy table header: "
                    + entry.path().string());
        }
        if (!result.empty()) result += path_separator;
        result += directory.string();
        if (end == std::string::npos) break;
        begin = end + 1;
    } while (true);
    return result;
}

struct Board {
    Bitboard white = 0, black = 0;
    std::array<Bitboard, 7> pieces{};
    unsigned ep = 0;
    bool white_to_move = true;

    explicit Board(const Position& position) {
        for (unsigned type = 1; type <= 6; ++type) {
            const auto white_pieces = position.pieces(Color::white, static_cast<PieceType>(type));
            const auto black_pieces = position.pieces(Color::black, static_cast<PieceType>(type));
            white |= white_pieces;
            black |= black_pieces;
            pieces[type] = white_pieces | black_pieces;
        }
        if (position.en_passant_square() >= 0)
            ep = static_cast<unsigned>(position.en_passant_square());
        white_to_move = position.turn() == Color::white;
    }

    Bitboard of(PieceType piece) const { return pieces[static_cast<unsigned>(piece)]; }
};

bool eligible(const Position& position) {
    return position.castling_rights() == 0 && position.halfmove_clock() < 100
        && static_cast<unsigned>(std::popcount(position.occupied())) <= TB_LARGEST;
}

std::optional<PieceType> promotion(unsigned code) {
    switch (code) {
    case TB_PROMOTES_NONE: return PieceType::none;
    case TB_PROMOTES_QUEEN: return PieceType::queen;
    case TB_PROMOTES_ROOK: return PieceType::rook;
    case TB_PROMOTES_BISHOP: return PieceType::bishop;
    case TB_PROMOTES_KNIGHT: return PieceType::knight;
    default: return std::nullopt;
    }
}

} // namespace

struct Syzygy::Impl {
    std::uint64_t generation = 0;
};

Syzygy::Syzygy() : impl_(std::make_unique<Impl>()) {}

Syzygy::~Syzygy() {
    auto& state = backend();
    const std::lock_guard guard(state.mutex);
    if (impl_->generation != 0 && impl_->generation == state.generation) invalidate(state);
}

bool Syzygy::set_path(const std::string& path, std::string& error) {
    error.clear();
    std::string checked;
    try {
        if (!path.empty() && path != "<empty>") checked = checked_path(path);
    } catch (const std::exception& exception) {
        error = exception.what();
        auto& state = backend();
        const std::lock_guard guard(state.mutex);
        if (impl_->generation != 0 && impl_->generation == state.generation) invalidate(state);
        impl_->generation = 0;
        return false;
    }

    auto& state = backend();
    const std::lock_guard guard(state.mutex);
    // Disabling an obsolete binding must not destroy a newer instance's tables.
    if (checked.empty()) {
        if (impl_->generation != 0 && impl_->generation == state.generation) invalidate(state);
        impl_->generation = 0;
        return true;
    }
    invalidate(state);
    impl_->generation = 0;
    try {
        // Mark before initialization so partially constructed upstream state is
        // released as well if the C++ allocation path throws.
        state.initialized = true;
        if (!tb_init(checked.c_str())) {
            error = "Syzygy initialization failed";
            invalidate(state);
            return false;
        }
        impl_->generation = state.generation;
        return true;
    } catch (const std::exception& exception) {
        error = std::string("Syzygy initialization failed: ") + exception.what();
        invalidate(state);
        return false;
    }
}

unsigned Syzygy::largest() const {
    auto& state = backend();
    const std::lock_guard guard(state.mutex);
    return impl_->generation != 0 && impl_->generation == state.generation
        ? TB_LARGEST : 0;
}

std::optional<Wdl> Syzygy::probe_wdl(const Position& position) const {
    if (position.halfmove_clock() != 0) return std::nullopt;
    auto& state = backend();
    const std::lock_guard guard(state.mutex);
    if (impl_->generation == 0 || impl_->generation != state.generation || !eligible(position))
        return std::nullopt;
    const Board board(position);
    const auto result = tb_probe_wdl(board.white, board.black, board.of(PieceType::king),
        board.of(PieceType::queen), board.of(PieceType::rook), board.of(PieceType::bishop),
        board.of(PieceType::knight), board.of(PieceType::pawn), 0, 0, board.ep, board.white_to_move);
    if (result > TB_WIN) return std::nullopt;
    return static_cast<Wdl>(static_cast<int>(result) - 2);
}

std::optional<std::vector<RootMove>> Syzygy::probe_root(
    const Position& position, const std::vector<Move>& legal) const {
    if (legal.empty() || legal.size() > TB_MAX_MOVES) return std::nullopt;
    auto& state = backend();
    const std::lock_guard guard(state.mutex);
    if (impl_->generation == 0 || impl_->generation != state.generation || !eligible(position))
        return std::nullopt;
    const Board board(position);
    TbRootMoves raw{};
    if (!tb_probe_root_dtz(board.white, board.black, board.of(PieceType::king),
            board.of(PieceType::queen), board.of(PieceType::rook), board.of(PieceType::bishop),
            board.of(PieceType::knight), board.of(PieceType::pawn), position.halfmove_clock(),
            0, board.ep, board.white_to_move, false, true, &raw)
        || raw.size != legal.size()) return std::nullopt;

    std::vector<RootMove> result;
    result.reserve(legal.size());
    std::vector<bool> matched(legal.size(), false);
    for (unsigned index = 0; index < raw.size; ++index) {
        const auto& candidate = raw.moves[index];
        const auto promoted = promotion(TB_MOVE_PROMOTES(candidate.move));
        if (!promoted) return std::nullopt;
        const auto move = std::find_if(legal.begin(), legal.end(), [&](Move item) {
            return item.from == TB_MOVE_FROM(candidate.move)
                && item.to == TB_MOVE_TO(candidate.move) && item.promotion == *promoted;
        });
        if (move == legal.end()) return std::nullopt;
        const auto offset = static_cast<std::size_t>(move - legal.begin());
        if (matched[offset]) return std::nullopt;
        matched[offset] = true;
        result.push_back({*move, candidate.tbRank});
    }
    return result;
}

} // namespace chess0live::tablebase
