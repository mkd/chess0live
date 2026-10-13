/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include <cstdint>
#include <string>

namespace chess0live {

using Bitboard = std::uint64_t;
enum class Color : std::uint8_t { white, black };
enum class PieceType : std::uint8_t { none, pawn, knight, bishop, rook, queen, king };

// Squares run from a1 = 0 through h8 = 63. A signed piece stores its type:
// positive means white, negative means black, and zero means an empty square.
using Piece = std::int8_t;
constexpr Color opposite(Color side) { return side == Color::white ? Color::black : Color::white; }
constexpr PieceType type_of(Piece piece) {
    return static_cast<PieceType>(piece < 0 ? -piece : piece);
}
// Precondition: piece is not empty.
constexpr Color color_of(Piece piece) { return piece > 0 ? Color::white : Color::black; }
constexpr Piece make_piece(Color side, PieceType type) {
    return static_cast<Piece>(static_cast<int>(type) * (side == Color::white ? 1 : -1));
}
constexpr Bitboard square_bit(int square) { return Bitboard{1} << square; }

enum MoveFlag : std::uint8_t { quiet = 0, capture = 1, double_push = 2, en_passant = 4, castle = 8 };

/** A value-type move; generated flags describe special board-state changes. */
struct Move {
    std::uint8_t from = 64;
    std::uint8_t to = 64;
    PieceType promotion = PieceType::none;
    std::uint8_t flags = quiet;

    constexpr bool valid() const { return from < 64 && to < 64; }
    constexpr bool is_capture() const { return (flags & capture) != 0; }
    constexpr bool operator==(const Move&) const = default;
    std::string uci() const {
        if (!valid()) return "0000";
        std::string result{char('a' + from % 8), char('1' + from / 8),
                           char('a' + to % 8), char('1' + to / 8)};
        if (promotion != PieceType::none) result += " pnbrqk"[static_cast<int>(promotion)];
        return result;
    }
};

} // namespace chess0live
