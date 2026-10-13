/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"

#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace chess0live;
namespace {
void require(bool condition, const std::string& explanation) {
    if (!condition) throw std::runtime_error(explanation);
}
Position parse(const std::string& fen) {
    std::string error;
    auto position = Position::from_fen(fen, error);
    require(position.has_value(), "Invalid test position: " + error + " / " + fen);
    return *position;
}
std::uint64_t random_value(std::uint64_t& state) {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

// Original, deterministic fixture generation; no games or suites imported.
std::vector<std::string> corpus(unsigned games, unsigned plies) {
    std::vector<std::string> positions{
        Position::start().fen(),
        "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",
        "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
        "7k/P7/8/8/8/8/7p/4K3 w - - 0 1",
        "7k/8/8/8/8/8/p7/4K3 b - - 0 1",
        "k7/8/8/8/8/8/8/7K w - - 0 1",
        "8/8/8/4k3/8/3K4/8/8 w - - 99 61",
        "4k3/8/8/8/8/2B5/8/4K3 w - - 0 1",
        "4k3/8/8/8/8/2B5/1N6/4K3 b - - 0 1",
        "4k3/8/8/8/8/2B2p2/1N6/4K3 w - - 0 1",
        "4k3/8/8/8/8/2B2p2/1N3P2/4K3 b - - 0 1",
    };
    // Include every legal one-move successor of the special positions. This
    // covers castling, en passant, promotion/underpromotion and king mirroring.
    const auto special_count = positions.size();
    for (std::size_t i = 1; i < special_count; ++i) {
        auto position = parse(positions[i]);
        for (const auto move : position.legal_moves()) {
            const auto undo = position.make_move(move);
            positions.push_back(position.fen());
            position.unmake_move(move, undo);
        }
    }
    std::uint64_t seed = 0x4348455353304c49ULL;
    for (unsigned game = 0; game < games; ++game) {
        auto position = Position::start();
        for (unsigned ply = 0; ply < plies; ++ply) {
            const auto moves = position.legal_moves();
            if (moves.empty()) break;
            const auto move = moves[random_value(seed) % moves.size()];
            position.make_move(move);
            positions.push_back(position.fen());
        }
    }
    return positions;
}

struct TemporaryFile {
    std::filesystem::path path = std::filesystem::temp_directory_path()
        / ("chess0live-bad-network-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    ~TemporaryFile() { std::error_code error; std::filesystem::remove(path, error); }
    void write(const std::vector<unsigned char>& bytes) const {
        std::ofstream output(path, std::ios::binary);
        output.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    }
};

void malformed_networks() {
    nnue::Network network;
    std::string error;
    TemporaryFile temporary;
    require(!network.load(temporary.path, error) && !error.empty(), "Missing network must be rejected");
    for (const auto& payload : std::vector<std::vector<unsigned char>>{
        {}, {0xfa}, {0, 0, 0, 0},
        {0xfa, 0x8a, 0x44, 0x6a, 0, 0, 0, 0},
    }) {
        temporary.write(payload);
        require(!network.load(temporary.path, error), "Malformed network accepted");
        require(!network.loaded() && !error.empty(), "Failed load must remain explicit");
    }
    // Header identifiers are observed in the pinned artifact, independently of
    // this reader's hash calculation. Small synthetic bodies target boundaries.
    auto block = [](const std::vector<unsigned char>& encoded) {
        std::vector<unsigned char> bytes;
        const auto append = [&](std::uint32_t value) {
            for (unsigned shift = 0; shift < 32; shift += 8)
                bytes.push_back(static_cast<unsigned char>(value >> shift));
        };
        append(0x6a448afa); append(0xa85b2205); append(0); append(0xcb685313);
        const std::string marker = "COMPRESSED_LEB128";
        bytes.insert(bytes.end(), marker.begin(), marker.end());
        append(static_cast<std::uint32_t>(encoded.size()));
        bytes.insert(bytes.end(), encoded.begin(), encoded.end());
        return bytes;
    };
    std::vector<std::vector<unsigned char>> invalid_bodies;
    auto zeros = std::vector<unsigned char>(1024, 0);
    invalid_bodies.push_back(block(zeros)); // Missing the transformer weights.
    auto bad_marker = block(zeros);
    bad_marker[16] = '!';
    invalid_bodies.push_back(std::move(bad_marker));
    zeros.push_back(0);
    invalid_bodies.push_back(block(zeros)); // Extra compressed bytes.
    auto overflow = std::vector<unsigned char>{0xff, 0xff, 0x07};
    overflow.insert(overflow.end(), 1023, 0);
    invalid_bodies.push_back(block(overflow)); // Decodes beyond signed 16 bits.
    auto overlong = std::vector<unsigned char>{0x80, 0x80, 0x80, 0x00};
    overlong.insert(overlong.end(), 1023, 0);
    invalid_bodies.push_back(block(overlong));
    auto truncated = block(std::vector<unsigned char>(1024, 0));
    truncated.pop_back();
    invalid_bodies.push_back(std::move(truncated));
    for (const auto& payload : invalid_bodies) {
        temporary.write(payload);
        require(!network.load(temporary.path, error) && !error.empty(), "Invalid compressed block accepted");
    }
    try {
        (void) network.evaluate(Position::start());
        require(false, "Unloaded evaluation must fail");
    } catch (const std::logic_error&) {}
}

void verify(const std::filesystem::path& path) {
    nnue::Network network;
    std::string error;
    const bool loaded = network.load(path, error);
    require(loaded, "Loading pinned NNUE failed: " + error);
    nnue::Evaluator incremental(network);
    const auto cases = corpus(4, 100);
    // Exact integer oracle observations from the independently compiled, pinned
    // official SF19 source and the manifest network. Inputs above are original.
    constexpr std::array<nnue::Raw, 12> golden{{
        {0, -1}, {0, 73}, {0, 73}, {5, -8}, {-15, 1621}, {3, 1975},
        {0, 1}, {-34, 14}, {801, -819}, {-1563, 916}, {680, 480}, {-709, -1571}
    }};
    constexpr std::array<int, 12> wrapped{-1, 77, 77, -3, 1479, 1775, 1, -11, -17, -569, 1174, -2236};
    for (std::size_t index = 0; index < golden.size(); ++index) {
        const auto position = parse(cases[index]);
        require(network.evaluate(position) == golden[index], "Pinned SF19 raw golden mismatch");
        require(incremental.evaluate(position) == wrapped[index], "Pinned SF19 calibrated golden mismatch");
    }
    for (const auto& fen : cases) {
        const auto position = parse(fen);
        const auto refreshed = network.evaluate(position);
        require(incremental.raw(position) == refreshed, "Incremental/full-refresh mismatch: " + fen);
    }
    // Search transitions backtrack as well as advance. Check every sibling,
    // then check restoring its parent, on special-move and ordinary positions.
    const auto special = corpus(0, 0);
    for (std::size_t index = 0; index < 12; ++index) {
        auto position = parse(special[index]);
        const auto before = incremental.raw(position);
        for (const auto move : position.legal_moves()) {
            const auto undo = position.make_move(move);
            require(incremental.raw(position) == network.evaluate(position), "Sibling evaluation mismatch");
            position.unmake_move(move, undo);
            require(incremental.raw(position) == before, "Make/unmake changed accumulator result");
        }
    }
    incremental.reset();
    const auto before = incremental.raw(Position::start());
    TemporaryFile corrupt;
    corrupt.write({1, 2, 3, 4});
    require(!network.load(corrupt.path, error), "Bad replacement accepted");
    require(network.loaded() && incremental.raw(Position::start()) == before,
            "Failed replacement damaged the previous usable network");
    // Keep every architecture marker valid, but make bucket 7's last-layer
    // bias enormous. The evaluator must reject unsafe calibration, not overflow.
    std::filesystem::copy_file(path, corrupt.path, std::filesystem::copy_options::overwrite_existing);
    {
        std::fstream hostile(corrupt.path, std::ios::binary | std::ios::in | std::ios::out);
        hostile.seekp(-132, std::ios::end);
        const std::array<unsigned char, 4> extreme{0xff, 0xff, 0xff, 0x7f};
        hostile.write(reinterpret_cast<const char*>(extreme.data()), extreme.size());
        require(bool(hostile), "Could not construct the hostile-weight fixture");
    }
    require(network.load(corrupt.path, error), "Hostile-weight fixture must retain a valid file structure");
    bool rejected = false;
    try { (void) incremental.evaluate(Position::start()); }
    catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "Extreme network output must be rejected before calibration products");
    require(network.load(path, error), "Reload failed");
    require(incremental.raw(Position::start()) == before, "Reload retained stale accumulator weights");
    std::cout << "PASS NNUE parser, " << cases.size()
              << " incremental/full-refresh positions, special-move backtracking, reset, reload\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        std::filesystem::path network_path = "networks/nn-1a298aa575a0.nnue";
        bool dump = false, positions = false, explicit_network = false;
        for (int index = 1; index < argc; ++index) {
            const std::string option = argv[index];
            if (option == "--network" && index + 1 < argc) {
                network_path = argv[++index];
                explicit_network = true;
            }
            else if (option == "--dump") dump = true;
            else if (option == "--positions") positions = true;
            else throw std::runtime_error("Usage: nnue_test [--network PATH] [--dump|--positions]");
        }
        if (positions) {
            for (const auto& fen : corpus(12, 160)) std::cout << fen << '\n';
            return 0;
        }
        if (dump) {
            nnue::Network network;
            std::string error;
            require(network.load(network_path, error), error);
            nnue::Evaluator evaluator(network);
            std::string fen;
            while (std::getline(std::cin, fen)) {
                const auto position = parse(fen);
                const auto result = evaluator.raw(position);
                require(result == network.evaluate(position), "Incremental/full-refresh mismatch: " + fen);
                std::cout << result.psqt << ' ' << result.positional << ' ';
                if (position.in_check(position.turn())) std::cout << "check";
                else std::cout << evaluator.evaluate(position);
                std::cout << '\n';
            }
            return 0;
        }
        malformed_networks();
        std::cout << "PASS NNUE malformed-file and unloaded-evaluation rejection\n";
        if (explicit_network || std::filesystem::exists(network_path)) verify(network_path);
        else std::cout << "SKIP real-network tests: run make net or pass --network PATH\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
