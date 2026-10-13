/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/position.hpp"

#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

using namespace chess0live;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}

Position read(std::string_view fen) {
    std::string error;
    auto position = Position::from_fen(fen, error);
    require(position.has_value(), "FEN rejected: " + std::string(fen) + ": " + error);
    return *position;
}

void check_state(const Position& position) {
    std::array<std::array<Bitboard, 7>, 2> expected{};
    Bitboard occupancy = 0;
    for (int square = 0; square < 64; ++square) {
        const Piece piece = position.at(square);
        if (!piece) continue;
        expected[static_cast<unsigned>(color_of(piece))][static_cast<unsigned>(type_of(piece))]
            |= square_bit(square);
        occupancy |= square_bit(square);
    }
    require(occupancy == position.occupied(), "array / occupancy disagreement");
    for (const Color side : {Color::white, Color::black})
        for (int type = 1; type <= 6; ++type)
            require(expected[static_cast<unsigned>(side)][type]
                        == position.pieces(side, static_cast<PieceType>(type)),
                    "array / piece-bitboard disagreement");
    const auto rebuilt = read(position.fen());
    require(rebuilt.key() == position.key(), "incremental / reconstructed key disagreement");
    require(rebuilt.fen() == position.fen(), "FEN serialization disagreement");
}

void roundtrip(Position& position, unsigned depth) {
    check_state(position);
    if (!depth) return;
    const auto original = position.fen();
    const auto key = position.key();
    for (const Move move : position.legal_moves()) {
        require(parse_uci_move(position, move.uci()) == move, "UCI move roundtrip");
        const auto undo = position.make_move(move);
        roundtrip(position, depth - 1);
        position.unmake_move(move, undo);
        require(position.fen() == original && position.key() == key, "make/unmake roundtrip");
        check_state(position);
    }
}

void expect_move(Position& position, std::string_view text, bool present) {
    require(parse_uci_move(position, text).has_value() == present,
            std::string(present ? "missing legal move " : "accepted illegal move ") + std::string(text));
}

void perft_suite() {
    // Public factual test vectors. Kiwipete's fifth rank is 3PN3, NOT 2pPN3.
    // https://www.chessprogramming.org/Perft_Results
    // The same FENs are used by Stockfish's own perft regression suite:
    // https://github.com/official-stockfish/Stockfish/blob/master/tests/perft.sh
    auto start = Position::start();
    constexpr std::array<std::uint64_t, 6> counts{1, 20, 400, 8902, 197281, 4865609};
    for (unsigned depth = 0; depth < counts.size(); ++depth)
        require(perft(start, depth) == counts[depth], "start perft depth " + std::to_string(depth));
    struct Vector { const char* fen; unsigned depth; std::uint64_t count; };
    constexpr std::array<Vector, 6> vectors{{
        {"r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 3, 97862},
        {"8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 4, 43238},
        {"r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 3, 9467},
        {"r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1", 3, 9467},
        {"rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 3, 62379},
        {"r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", 3, 89890},
    }};
    for (const auto& vector : vectors) {
        auto position = read(vector.fen);
        const auto actual = perft(position, vector.depth);
        require(actual == vector.count, "perft expected " + std::to_string(vector.count)
                + ", got " + std::to_string(actual) + " for " + vector.fen);
        roundtrip(position, 2);
    }
}

void special_moves() {
    auto horizontal_pin = read("7k/8/8/r4pPK/8/8/8/8 w - f6 0 2");
    expect_move(horizontal_pin, "g5f6", false);
    require(horizontal_pin.key() == read("7k/8/8/r4pPK/8/8/8/8 w - - 0 2").key(),
            "illegal EP must not affect repetition key");
    auto vertical_pin = read("4r2k/8/8/3pP3/8/8/8/4K3 w - d6 0 2");
    expect_move(vertical_pin, "e5d6", false);
    require(vertical_pin.key() == read("4r2k/8/8/3pP3/8/8/8/4K3 w - - 0 2").key(),
            "pinned EP must not affect repetition key");
    auto two_candidates = read("4r2k/8/8/2PpP3/8/8/8/4K3 w - d6 0 2");
    expect_move(two_candidates, "c5d6", true);
    expect_move(two_candidates, "e5d6", false);
    require(two_candidates.key() != read("4r2k/8/8/2PpP3/8/8/8/4K3 w - - 0 2").key(),
            "one legal EP candidate must affect repetition key");
    auto ep_evasion = read("7k/8/8/3pP3/4K3/8/8/8 w - d6 0 2");
    require(ep_evasion.in_check(Color::white), "EP evasion setup is in check");
    expect_move(ep_evasion, "e5d6", true);
    roundtrip(ep_evasion, 2);
    auto black_ep = read("8/8/8/4k3/3Pp3/8/8/7K b - d3 0 2");
    expect_move(black_ep, "e4d3", true);
    roundtrip(black_ep, 2);

    auto through_check = read("4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1");
    expect_move(through_check, "e1g1", false);
    expect_move(through_check, "e1c1", true);
    auto into_check = read("4k3/8/8/8/8/8/6r1/R3K2R w KQ - 0 1");
    expect_move(into_check, "e1g1", false);
    auto out_of_check = read("4k3/8/8/8/8/8/4r3/R3K2R w KQ - 0 1");
    expect_move(out_of_check, "e1g1", false);
    expect_move(out_of_check, "e1c1", false);
    auto b1_attacked = read("4k3/8/8/8/8/8/1r6/R3K2R w KQ - 0 1");
    expect_move(b1_attacked, "e1c1", true);
    auto castles = read("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
    roundtrip(castles, 2);
    auto queenside = *parse_uci_move(castles, "e1c1");
    const auto castle_undo = castles.make_move(queenside);
    require(castles.at(2) == make_piece(Color::white, PieceType::king)
            && castles.at(3) == make_piece(Color::white, PieceType::rook)
            && castles.at(0) == 0 && castles.at(4) == 0, "castling rook relocation");
    castles.unmake_move(queenside, castle_undo);
    const auto rook_capture = *parse_uci_move(castles, "a1a8");
    castles.make_move(rook_capture);
    require(castles.fen().find(" b Kk ") != std::string::npos,
            "moving/capturing home rooks must clear both queenside rights");

    auto promotion = read("r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1");
    for (const char piece : std::string("qrbn")) {
        expect_move(promotion, std::string("b7a8") + piece, true);
        expect_move(promotion, std::string("b7b8") + piece, true);
    }
    expect_move(promotion, "b7a8", false);
    expect_move(promotion, "b7a8k", false);
    roundtrip(promotion, 2);

    auto mate = read("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1");
    require(mate.in_check(Color::black) && mate.legal_moves().empty(), "checkmate");
    auto stalemate = read("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1");
    require(!stalemate.in_check(Color::black) && stalemate.legal_moves().empty(), "stalemate");
    require(perft(mate, 0) == 1 && perft(mate, 1) == 0, "perft terminal semantics");
}

void fen_validation() {
    constexpr const char* invalid[]{
        "", "8/8/8/8/8/8/8/8 w - - 0 1", // Empty board / missing kings.
        "7k/8/8/8/8/8/8/K7 w - - 0", // Missing field.
        "7k/8/8/8/8/8/8/K7 w - - 0 1 trailing",
        "7k/8/8/8/8/8/8/K7 x - - 0 1",
        "7k/8/8/8/8/8/8/K7 w - - -1 1",
        "7k/8/8/8/8/8/8/K7 w - - 0 0",
        "7k/8/8/8/8/8/8/K7 w - - 4294967296 1",
        "7k/8/8/8/8/8/8/K7 w - - 1x 1",
        "7k/8/8/8/8/8/8/K8 w - - 0 1",
        "7k/8/8/8/8/8/K7 w - - 0 1",
        "7k/8/8/8/8/8/8/K7/8 w - - 0 1",
        "7k/8/8/8/8/8/8/K61 w - - 0 1",
        "7k/8/8/8/8/8/8/K6X w - - 0 1",
        "7k/8/8/8/8/8/8/K6P w - - 0 1",
        "7k/8/8/8/8/8/8/K7 w K - 0 1",
        "4k3/8/8/8/8/8/8/4K2R w KK - 0 1",
        "4k3/8/8/8/8/8/8/4K2R w KQ - 0 1",
        "7k/8/8/8/8/8/8/K7 w - d6 0 1",
        "7k/8/8/3pP3/8/8/8/K7 w - d3 0 1",
        "7k/8/3p4/3pP3/8/8/8/K7 w - d6 0 1",
        "7k/3p4/8/3pP3/8/8/8/K7 w - d6 0 1",
        "7k/8/8/3pP3/8/8/8/K7 w - d6 1 1",
        "8/8/8/8/8/8/4k3/4K3 w - - 0 1", // Adjacent kings.
        "4k3/8/8/8/8/8/8/K3R3 w - - 0 1", // Inactive king in check.
    };
    for (const auto* fen : invalid) {
        std::string error;
        require(!Position::from_fen(fen, error) && !error.empty(), "accepted invalid FEN: " + std::string(fen));
    }
    std::string error = "stale error";
    require(Position::from_fen(Position::start().fen(), error).has_value() && error.empty(),
            "successful FEN parse must clear previous error");
    auto checked = read("4k3/8/8/8/8/8/8/K3R3 b - - 0 1");
    require(checked.in_check(Color::black), "valid side-to-move check must be accepted");
}

void history_and_null() {
    auto position = Position::start();
    const auto original_key = position.key();
    for (const auto* text : {"g1f3", "g8f6", "f3g1", "f6g8"})
        position.make_move(*parse_uci_move(position, text));
    require(position.key() == original_key && position.halfmove_clock() == 4
            && position.fullmove_number() == 3, "repetition key ignores move counters");
    const auto before_null = position.fen();
    const auto null_undo = position.make_null_move();
    check_state(position);
    require(position.key() != original_key && position.turn() == Color::black, "null move flips side");
    position.unmake_null_move(null_undo);
    require(position.key() == original_key && position.fen() == before_null, "null move restoration");

    // An active check is forbidden by the caller for null moves, so use a quiet
    // position with a genuinely capturable EP square.
    position = read("7k/8/8/3pP3/8/8/8/4K3 w - d6 0 42");
    const auto ep_fen = position.fen();
    const auto ep_key = position.key();
    const auto ep_undo = position.make_null_move();
    check_state(position);
    require(position.fen().find(" b - - 1 42") != std::string::npos, "null clears EP");
    position.unmake_null_move(ep_undo);
    require(position.fen() == ep_fen && position.key() == ep_key, "null restores EP key");

    // Deterministic legal playouts check incremental state and complete unwinding
    // independently of the perft totals. No external engine is needed at runtime.
    std::uint64_t random = 0x5eed1234;
    for (int game = 0; game < 20; ++game) {
        position = Position::start();
        std::vector<std::pair<Move, Undo>> history;
        for (int ply = 0; ply < 100; ++ply) {
            check_state(position);
            auto moves = position.legal_moves();
            if (moves.empty()) break;
            random ^= random << 13;
            random ^= random >> 7;
            random ^= random << 17;
            const Move move = moves[random % moves.size()];
            history.emplace_back(move, position.make_move(move));
        }
        while (!history.empty()) {
            const auto [move, undo] = history.back();
            history.pop_back();
            position.unmake_move(move, undo);
            check_state(position);
        }
        require(position.fen() == Position::start().fen() && position.key() == original_key,
                "complete game unwind");
    }
}

} // namespace

int main() {
    perft_suite();
    special_moves();
    fen_validation();
    history_and_null();
    std::cout << "position tests passed: public perft vectors, special moves, FEN, state/hash restoration\n";
}
