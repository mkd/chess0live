/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/position.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace chess0live;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

Position read(std::string_view fen) {
    std::string error;
    const auto position = Position::from_fen(fen, error);
    require(position.has_value(), "FEN rejected: " + std::string(fen) + ": " + error);
    return *position;
}

/** Detect restoration errors even if the cached key and serialized board agree. */
void same_position(const Position& actual, const Position& expected) {
    require(actual.fen() == expected.fen(), "tactical generation changed FEN");
    require(actual.key() == expected.key(), "tactical generation changed key");
    require(actual.turn() == expected.turn(), "tactical generation changed turn");
    require(actual.castling_rights() == expected.castling_rights(), "castling changed");
    require(actual.en_passant_square() == expected.en_passant_square(), "EP changed");
    require(actual.halfmove_clock() == expected.halfmove_clock(), "halfmove changed");
    require(actual.fullmove_number() == expected.fullmove_number(), "fullmove changed");
    require(actual.occupied() == expected.occupied(), "occupancy changed");
    for (int square = 0; square < 64; ++square)
        require(actual.at(square) == expected.at(square), "square array changed");
    for (const auto side : {Color::white, Color::black}) {
        require(actual.king_square(side) == expected.king_square(side), "king square changed");
        for (unsigned type = 1; type <= 6; ++type)
            require(actual.pieces(side, static_cast<PieceType>(type))
                    == expected.pieces(side, static_cast<PieceType>(type)), "piece bitboard changed");
    }
}

struct Coverage {
    std::size_t positions = 0;
    std::size_t checked = 0;
    std::size_t quiet_only = 0;
    std::size_t terminal = 0;
    std::size_t null_positions = 0;
    std::array<std::size_t, 2> colors{};
};

/** The established full generator is an independent path: it tests every quiet
 * move. Filtering its completed legal list supplies both order and terminal
 * membership expectations without reproducing the new witness algorithm.
 */
TacticalMoveList compare(Position& position, Coverage& coverage) {
    const auto before = position;
    auto full = position.legal_moves();
    same_position(position, before);
    const bool any_legal = !full.empty();
    std::erase_if(full, [](Move move) {
        return !move.is_capture() && move.promotion == PieceType::none;
    });
    const auto result = position.legal_tactical_moves();
    require(result.moves == full, "tactical move order/content differs at " + before.fen());
    require(result.has_legal_move == any_legal, "terminal witness differs at " + before.fen());
    same_position(position, before);
    // Repetition of the query also guards against hidden incremental mutation.
    const auto again = position.legal_tactical_moves();
    require(again.moves == result.moves && again.has_legal_move == result.has_legal_move,
            "repeated tactical query differs");
    same_position(position, before);
    ++coverage.positions;
    ++coverage.colors[static_cast<unsigned>(position.turn())];
    coverage.checked += position.in_check(position.turn());
    coverage.quiet_only += any_legal && full.empty();
    coverage.terminal += !any_legal;
    return result;
}

bool contains(const TacticalMoveList& result, std::string_view uci) {
    return std::any_of(result.moves.begin(), result.moves.end(), [&](Move move) {
        return move.uci() == uci;
    });
}

void fixed_cases(Coverage& coverage) {
    auto start = Position::start();
    auto result = compare(start, coverage);
    require(result.has_legal_move && result.moves.empty(), "start position has quiet moves only");

    for (const auto fen : {
            "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", // Stalemate.
            "7k/6Q1/6K1/8/8/8/8/8 b - - 100 1"}) { // Mate outranks rule 50.
        auto position = read(fen);
        result = compare(position, coverage);
        require(!result.has_legal_move && result.moves.empty(), "terminal position has a witness");
    }

    // All evasions here are quiet. This is why checked search nodes must still
    // request the full legal list rather than treating tacticals as evasions.
    auto quiet_evasion = read("4r2k/8/8/8/8/8/8/4K3 w - - 0 1");
    result = compare(quiet_evasion, coverage);
    require(quiet_evasion.in_check(Color::white) && result.has_legal_move && result.moves.empty(),
            "quiet check evasions were mistaken for mate");

    auto pinned = read("4r2k/8/8/8/8/2p5/4N3/4K3 w - - 0 1");
    result = compare(pinned, coverage);
    require(result.has_legal_move && !contains(result, "e2c3"), "pinned knight capture accepted");

    // An early pawn quiet move must not stop later rook captures from being
    // collected; its legality witness only removes redundant quiet checks.
    auto later_capture = read("7k/8/8/8/8/8/4P3/1r1RK3 w - - 0 1");
    result = compare(later_capture, coverage);
    require(contains(result, "d1b1"), "capture after a quiet witness was skipped");

    struct EpCase { const char* fen; const char* move; bool legal; };
    constexpr std::array<EpCase, 5> ep_cases{{
        {"7k/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6", true},
        {"7k/8/8/r4pPK/8/8/8/8 w - f6 0 2", "g5f6", false},
        {"4r2k/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6", false},
        {"7k/8/8/3pP3/4K3/8/8/8 w - d6 0 2", "e5d6", true},
        {"8/8/8/4k3/3Pp3/8/8/7K b - d3 0 2", "e4d3", true},
    }};
    for (const auto& entry : ep_cases) {
        auto position = read(entry.fen);
        result = compare(position, coverage);
        require(contains(result, entry.move) == entry.legal, "EP legality differs");
    }
    auto two_ep = read("4r2k/8/8/2PpP3/8/8/8/4K3 w - d6 0 2");
    result = compare(two_ep, coverage);
    require(contains(result, "c5d6") && !contains(result, "e5d6"), "two EP candidates differ");

    struct PromotionCase { const char* fen; const char* capture; const char* quiet; };
    constexpr std::array<PromotionCase, 2> promotion_cases{{
        {"r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1", "b7a8", "b7b8"},
        {"4k3/8/8/8/8/8/1p6/R3K3 b - - 0 1", "b2a1", "b2b1"},
    }};
    for (const auto& entry : promotion_cases) {
        auto position = read(entry.fen);
        result = compare(position, coverage);
        require(result.moves.size() == 8, "expected all four capture and quiet promotions");
        for (const char type : std::string("qrbn")) {
            require(contains(result, std::string(entry.capture) + type), "capture promotion missing");
            require(contains(result, std::string(entry.quiet) + type), "quiet promotion missing");
        }
    }

    for (const auto fen : {
            "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
            "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",
            "4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1",
            "7k/8/8/8/8/8/8/K7 w - - 4294967295 4294967295"}) {
        auto position = read(fen);
        result = compare(position, coverage);
        require(result.has_legal_move, "nonterminal castling/counter position has no witness");
        require(std::none_of(result.moves.begin(), result.moves.end(), [](Move move) {
            return (move.flags & castle) != 0;
        }), "castling entered tactical list");
    }
}

std::uint64_t random_step(std::uint64_t& state) {
    state ^= state >> 12;
    state ^= state << 25;
    state ^= state >> 27;
    return state * UINT64_C(2685821657736338717);
}

/** Original deterministic legal playouts cover both sides and diverse mobility.
 * Every position is also revisited while unwinding the complete move history.
 * This is move-generation parity evidence, not an opening or strength corpus.
 */
void legal_playouts(Coverage& coverage) {
    std::uint64_t random = UINT64_C(0x544143544943414c);
    for (unsigned game = 0; game < 32; ++game) {
        auto position = Position::start();
        const auto initial = position;
        std::vector<std::pair<Move, Undo>> history;
        for (unsigned ply = 0; ply < 128; ++ply) {
            compare(position, coverage);
            auto legal = position.legal_moves();
            if (legal.empty()) break;
            if (ply % 16 == 0 && !position.in_check(position.turn())) {
                const auto before_null = position;
                const auto null_undo = position.make_null_move();
                compare(position, coverage);
                ++coverage.null_positions;
                position.unmake_null_move(null_undo);
                same_position(position, before_null);
            }
            const auto move = legal[random_step(random) % legal.size()];
            history.emplace_back(move, position.make_move(move));
        }
        while (!history.empty()) {
            const auto [move, undo] = history.back();
            history.pop_back();
            position.unmake_move(move, undo);
            compare(position, coverage);
        }
        same_position(position, initial);
    }
    require(coverage.positions >= 6000, "insufficient deterministic playout coverage");
    require(coverage.colors[0] >= 2000 && coverage.colors[1] >= 2000, "both sides not covered");
    require(coverage.checked > 50 && coverage.quiet_only > 50 && coverage.terminal >= 2,
            "check, quiet-only or terminal coverage missing");
    require(coverage.null_positions > 100, "null-search states not covered");
}

} // namespace

int main() {
    try {
        Coverage coverage;
        fixed_cases(coverage);
        legal_playouts(coverage);
        std::cout << "Tactical move generation passed: " << coverage.positions
                  << " position comparisons, " << coverage.checked << " checked, "
                  << coverage.quiet_only << " quiet-only, " << coverage.terminal
                  << " terminal, " << coverage.null_positions << " null-search positions\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
