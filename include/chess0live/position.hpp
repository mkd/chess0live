/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include "chess0live/types.hpp"

#include <array>
#include <optional>
#include <string_view>
#include <vector>

namespace chess0live {

/** Irreversible state saved before a move; board changes are reversed from Move. */
struct Undo {
    Piece moved = 0;
    Piece captured = 0;
    std::uint8_t castling = 0;
    int en_passant_square = -1;
    std::uint32_t halfmove = 0;
    std::uint32_t fullmove = 1;
    std::uint64_t key = 0;
};

/** Legal captures/promotions plus a witness for any legal move, including quiet
 * moves. An empty tactical list alone does not distinguish quiet play from
 * stalemate. The list is not a complete set of check evasions.
 */
struct TacticalMoveList {
    std::vector<Move> moves;
    bool has_legal_move = false;
};

/**
 * Standard-chess position, with a1 = bit 0 and white pieces positive.
 * The square array, piece bitboards, occupancy, and incremental key agree after
 * every public operation. Moves passed to make_move must come from this position's
 * generator; unmake calls must be paired in reverse order. No history is retained:
 * repetition detection belongs to the game/search layer.
 */
class Position {
public:
    static Position start();
    /** Parse all six FEN fields, rejecting malformed or locally illegal states. */
    static std::optional<Position> from_fen(std::string_view fen, std::string& error);
    std::string fen() const;
    Color turn() const { return side_; }
    Piece at(int square) const { return board_[static_cast<std::size_t>(square)]; }
    Bitboard pieces(Color side, PieceType type) const {
        return pieces_[static_cast<unsigned>(side)][static_cast<unsigned>(type)];
    }
    Bitboard occupied() const { return occupied_; }
    /** Standard castling bits WK/WQ/BK/BQ; zero is required for tablebases. */
    std::uint8_t castling_rights() const { return castling_; }
    /** FEN target square, or -1 when absent. Legal EP is checked by move generation. */
    int en_passant_square() const { return ep_square_; }
    int king_square(Color side) const;
    bool in_check(Color side) const;
    bool attacked(int square, Color by) const;
    /** Generate fully legal moves, including all four promotion choices. */
    std::vector<Move> legal_moves();
    /** Return legal captures and all promotions in legal_moves() order, while
     * preserving enough quiet-move legality work to detect terminal positions.
     * This also works in check, but search must use legal_moves() there because
     * quiet evasions are deliberately omitted. The complete position is restored.
     */
    TacticalMoveList legal_tactical_moves();
    Undo make_move(Move move);
    void unmake_move(Move move, const Undo& undo);
    /** Key includes an EP file only when a legal en-passant capture exists. */
    std::uint64_t key() const { return key_; }
    std::uint32_t halfmove_clock() const { return halfmove_; }
    std::uint32_t fullmove_number() const { return fullmove_; }
    /** Search-only pass; caller must not use it to evade check or as game history. */
    Undo make_null_move();
    void unmake_null_move(const Undo& undo);

private:
    Position() = default;
    std::array<Piece, 64> board_{};
    std::array<std::array<Bitboard, 7>, 2> pieces_{};
    Bitboard occupied_ = 0;
    Color side_ = Color::white;
    std::uint8_t castling_ = 0; // White kingside, queenside; black kingside, queenside.
    int ep_square_ = -1;
    std::uint32_t halfmove_ = 0;
    std::uint32_t fullmove_ = 1;
    std::uint64_t key_ = 0;

    void put(int square, Piece piece);
    Piece remove(int square);
    std::vector<Move> pseudo_legal_moves() const;
    bool attacked_with(int square, Color by, Bitboard occupancy, Bitboard pawns) const;
    int ep_hash_file() const;
    void rebuild_key();
    Undo save() const;
    void restore_state(const Undo& undo);
};

/** Count legal leaf positions; depth zero is the current position itself. */
std::uint64_t perft(Position& position, unsigned depth);
/** Match standard UCI coordinate notation against generated legal moves. */
std::optional<Move> parse_uci_move(Position& position, std::string_view text);

} // namespace chess0live
