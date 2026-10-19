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

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
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

/** Derive the expected pass independently from the serialized six-field state.
 * A null move is a search operation, not a legal game move: the pieces and
 * castling rights stay fixed, EP expires, and the moving side loses one tempo.
 * The documented position counters saturate instead of wrapping at uint32 max.
 */
std::string passed_fen(const Position& position) {
    std::istringstream input(position.fen());
    std::string pieces, turn, castling, ep;
    std::uint64_t halfmove = 0, fullmove = 0;
    require(bool(input >> pieces >> turn >> castling >> ep >> halfmove >> fullmove),
            "cannot split serialized FEN");
    constexpr auto ceiling = std::numeric_limits<std::uint32_t>::max();
    halfmove = std::min<std::uint64_t>(halfmove + 1, ceiling);
    fullmove = std::min<std::uint64_t>(fullmove + (turn == "b"), ceiling);
    return pieces + (turn == "w" ? " b " : " w ") + castling + " - "
         + std::to_string(halfmove) + " " + std::to_string(fullmove);
}

/** Compare every observable field, not only the cached Zobrist key. */
void same_position(const Position& actual, const Position& expected,
                   const std::string& label) {
    require(actual.fen() == expected.fen(), label + ": FEN differs");
    require(actual.key() == expected.key(), label + ": key differs");
    require(actual.turn() == expected.turn(), label + ": turn differs");
    require(actual.en_passant_square() == expected.en_passant_square(), label + ": EP differs");
    require(actual.castling_rights() == expected.castling_rights(), label + ": castling differs");
    require(actual.halfmove_clock() == expected.halfmove_clock(), label + ": halfmove differs");
    require(actual.fullmove_number() == expected.fullmove_number(), label + ": fullmove differs");
    require(actual.occupied() == expected.occupied(), label + ": occupancy differs");
    for (int square = 0; square < 64; ++square)
        require(actual.at(square) == expected.at(square), label + ": square array differs");
    for (const Color side : {Color::white, Color::black}) {
        require(actual.king_square(side) == expected.king_square(side), label + ": king differs");
        for (unsigned type = 1; type <= 6; ++type)
            require(actual.pieces(side, static_cast<PieceType>(type))
                    == expected.pieces(side, static_cast<PieceType>(type)),
                    label + ": piece bitboard differs");
    }
}

/** A new evaluator and the network's full refresh are two independent reset
 * paths. Raw parity alone would miss a side/counter calibration discrepancy.
 */
void same_evaluation(const Position& position, nnue::Evaluator& incremental,
                     const nnue::Network& network, std::size_t& evaluations) {
    nnue::Evaluator fresh(network);
    const auto expected_raw = network.evaluate(position);
    require(incremental.raw(position) == expected_raw,
            "null-transition raw NNUE mismatch at " + position.fen());
    require(incremental.evaluate(position) == fresh.evaluate(position),
            "null-transition calibrated NNUE mismatch at " + position.fen());
    ++evaluations;
}

struct Coverage {
    std::size_t roots = 0;
    std::size_t evaluations = 0;
    std::size_t real_children = 0;
    std::size_t white = 0;
    std::size_t black = 0;
    std::size_t ep = 0;
    bool capture = false;
    bool promotion = false;
    bool castling = false;
    bool double_push = false;
    bool en_passant = false;
    bool king_move = false;
};

void note_move(const Position& position, Move move, Coverage& coverage) {
    coverage.capture |= move.is_capture();
    coverage.promotion |= move.promotion != PieceType::none;
    coverage.castling |= (move.flags & castle) != 0;
    coverage.double_push |= (move.flags & double_push) != 0;
    coverage.en_passant |= (move.flags & en_passant) != 0;
    coverage.king_move |= type_of(position.at(move.from)) == PieceType::king;
}

void check_null(Position& position, nnue::Evaluator& incremental,
                const nnue::Network& network, Coverage& coverage, bool children) {
    // The low-level Position API does not reject a checked-side pass. Search
    // must satisfy this precondition before calling it; eligibility is tested
    // separately by the search-policy and actual-search regression suites.
    require(!position.in_check(position.turn()), "test attempted to pass while checked");
    const auto before = position;
    const auto expected = read(passed_fen(before));
    const auto legal_before = position.legal_moves();
    same_evaluation(position, incremental, network, coverage.evaluations);

    const auto undo = position.make_null_move();
    same_position(position, expected, "after null");
    same_evaluation(position, incremental, network, coverage.evaluations);
    require(position.occupied() == before.occupied(), "null changed occupancy");
    require(undo.moved == 0 && undo.captured == 0, "null invented a moved/captured piece");
    if (children) {
        // Exhaust every first child, including castles and all four promotion
        // types. Search only one reply per child to keep the suite bounded.
        // Captures are preferred to exercise NNUE removal and restoration.
        for (const auto move : position.legal_moves()) {
            note_move(position, move, coverage);
            const auto child_undo = position.make_move(move);
            same_position(position, read(position.fen()), "real child after null");
            same_evaluation(position, incremental, network, coverage.evaluations);
            auto replies = position.legal_moves();
            const auto special = std::find_if(replies.begin(), replies.end(), [](Move reply) {
                return (reply.flags & en_passant) != 0;
            });
            const auto capture_reply = std::find_if(replies.begin(), replies.end(), [](Move reply) {
                return reply.is_capture();
            });
            const auto reply = special != replies.end() ? special
                             : capture_reply != replies.end() ? capture_reply : replies.begin();
            if (reply != replies.end()) {
                const auto child = position;
                note_move(position, *reply, coverage);
                const auto reply_undo = position.make_move(*reply);
                same_position(position, read(position.fen()), "real grandchild after null");
                same_evaluation(position, incremental, network, coverage.evaluations);
                position.unmake_move(*reply, reply_undo);
                same_position(position, child, "grandchild undo");
                same_evaluation(position, incremental, network, coverage.evaluations);
            }
            position.unmake_move(move, child_undo);
            same_position(position, expected, "child undo");
            same_evaluation(position, incremental, network, coverage.evaluations);
            ++coverage.real_children;
        }
    }
    position.unmake_null_move(undo);
    same_position(position, before, "null undo");
    same_evaluation(position, incremental, network, coverage.evaluations);
    require(position.legal_moves() == legal_before, "null undo changed legal moves");
    ++coverage.roots;
    before.turn() == Color::white ? ++coverage.white : ++coverage.black;
    coverage.ep += before.en_passant_square() >= 0;
}

/** Independently composed structural fixtures. They are correctness inputs,
 * not a tactical tuning or strength corpus, and use no held-out opening data.
 */
constexpr std::array<std::string_view, 15> fixtures{
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1",
    "k7/8/8/5pP1/8/8/8/4K3 w - f6 0 20",
    "4k3/8/8/8/2pP4/8/8/7K b - d3 0 20",
    "k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 20",
    "4k3/8/8/8/3Pp3/8/8/K3R3 b - d3 0 20",
    "4k3/8/8/3p4/8/8/8/4K3 w - d6 0 20",
    "4k3/8/8/8/3P4/8/8/4K3 b - d3 0 20",
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 27 18",
    "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 27 18",
    "4k3/P7/8/8/8/8/7p/4K3 w - - 9 42",
    "4k3/P7/8/8/8/8/7p/4K3 b - - 9 42",
    // Black's real double push after White's pass permits a new white EP reply.
    "4k3/5p2/8/6P1/8/8/8/4K3 w - - 0 21",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 4294967295 4294967295",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 4294967295 4294967295"
};

void verify_ep_hash_cases() {
    // Legal EP contributes to the repetition key; unavailable or king-pinned
    // EP does not. All cases still retain their FEN EP target until the pass.
    for (std::size_t index = 2; index < 8; ++index) {
        auto position = read(fixtures[index]);
        std::string fen(position.fen());
        const auto field = fen.find(" - ");
        require(field != std::string::npos, "EP fixture has unexpected castling");
        fen.replace(field + 3, 2, "-");
        const auto no_ep = read(fen);
        require((position.key() != no_ep.key()) == (index < 4),
                "EP fixture does not exercise the expected legal/hash case");
    }
}

void verify(const std::filesystem::path& network_path) {
    nnue::Network network;
    std::string error;
    require(network.load(network_path, error), "pinned network load failed: " + error);
    nnue::Evaluator incremental(network);
    Coverage coverage;
    verify_ep_hash_cases();
    for (const auto fen : fixtures) {
        auto position = read(fen);
        check_null(position, incremental, network, coverage, true);
    }

    // A single evolving legal history makes the accumulator arrive from varied
    // real parents before each null. The deterministic move choice is local to
    // this correctness test and independent of all qualification suites.
    auto position = Position::start();
    for (std::size_t ply = 0; ply < 48; ++ply) {
        auto legal = position.legal_moves();
        if (legal.empty()) break;
        if (!position.in_check(position.turn()))
            check_null(position, incremental, network, coverage, false);
        const auto move = legal[(ply * 17 + 11) % legal.size()];
        position.make_move(move);
        same_evaluation(position, incremental, network, coverage.evaluations);
    }
    require(coverage.white > 15 && coverage.black > 15 && coverage.ep >= 6,
            "insufficient null-state side/EP coverage");
    require(coverage.capture && coverage.promotion && coverage.castling
            && coverage.double_push && coverage.en_passant && coverage.king_move,
            "special real-child coverage is incomplete");
    std::cout << "PASS null state: " << coverage.roots << " roots, "
              << coverage.real_children << " real children, " << coverage.evaluations
              << " incremental/full NNUE comparisons, both colors, EP hash cases, "
                 "castling, captures, promotions, counter saturation, exact undo\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        require(argc <= 2, "Usage: null-state-test [NETWORK]");
        verify(argc == 2 ? argv[1] : "networks/nn-1a298aa575a0.nnue");
        return 0;
    } catch (const std::exception& failure) {
        std::cerr << "FAIL " << failure.what() << '\n';
        return 1;
    }
}
