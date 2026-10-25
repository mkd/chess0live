/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/exchange.hpp"

#include "chess0live/position.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cassert>

namespace chess0live {
namespace {

constexpr std::array<int, 7> material{0, 100, 320, 330, 500, 900, 20000};
constexpr unsigned index(Color side) { return static_cast<unsigned>(side); }
constexpr unsigned index(PieceType piece) { return static_cast<unsigned>(piece); }
constexpr int value(PieceType piece) { return material[index(piece)]; }
constexpr bool on_board(int file, int rank) {
    return file >= 0 && file < 8 && rank >= 0 && rank < 8;
}

/** Symmetric leaper attacks can also be read backwards from the target. */
constexpr auto leaper_masks(bool knight) {
    std::array<Bitboard, 64> masks{};
    for (int square = 0; square < 64; ++square)
        for (int df = -2; df <= 2; ++df)
            for (int dr = -2; dr <= 2; ++dr) {
                const bool reaches = knight ? df * df + dr * dr == 5
                    : df * df <= 1 && dr * dr <= 1 && (df || dr);
                const int file = square % 8 + df, rank = square / 8 + dr;
                if (reaches && on_board(file, rank))
                    masks[static_cast<unsigned>(square)] |= square_bit(rank * 8 + file);
            }
    return masks;
}
constexpr auto knight_masks = leaper_masks(true);
constexpr auto king_masks = leaper_masks(false);

struct RayDirection { int file_step, rank_step; };
constexpr std::array<RayDirection, 8> ray_directions{{
    {-1, -1}, {-1, 0}, {-1, 1}, {0, -1},
    {0, 1}, {1, -1}, {1, 0}, {1, 1},
}};

/** These rays exclude their target square. Every occupied square blocks a ray
 * regardless of color or piece type; only the nearest blocker can attack back.
 * Build the 4 KiB geometry table once, without doing a ray walk during SEE.
 */
constexpr auto slider_ray_masks() {
    std::array<std::array<Bitboard, 8>, 64> masks{};
    for (int square = 0; square < 64; ++square)
        for (std::size_t direction = 0; direction < ray_directions.size(); ++direction) {
            const auto [df, dr] = ray_directions[direction];
            for (int file = square % 8 + df, rank = square / 8 + dr;
                 on_board(file, rank); file += df, rank += dr)
                masks[static_cast<unsigned>(square)][direction] |= square_bit(rank * 8 + file);
        }
    return masks;
}
constexpr auto slider_rays = slider_ray_masks();

/** An exchange needs neither clocks/castling rights nor a mutable Position.
 * Each legal-capture probe copies only these small bitboards and king squares.
 */
struct ExchangeBoard {
    std::array<std::array<Bitboard, 7>, 2> pieces{};
    Bitboard occupied = 0;
    std::array<int, 2> kings{};

    explicit ExchangeBoard(const Position& position) : occupied(position.occupied()) {
        for (Color side : {Color::white, Color::black}) {
            kings[index(side)] = position.king_square(side);
            for (unsigned type = 1; type <= 6; ++type)
                pieces[index(side)][type] = position.pieces(side, static_cast<PieceType>(type));
        }
    }

    void remove(Color side, PieceType piece, int square) {
        pieces[index(side)][index(piece)] &= ~square_bit(square);
        occupied &= ~square_bit(square);
    }
    void place(Color side, PieceType piece, int square) {
        pieces[index(side)][index(piece)] |= square_bit(square);
        occupied |= square_bit(square);
        if (piece == PieceType::king) kings[index(side)] = square;
    }

    /** Pseudo-attacks deliberately include pinned defenders: a king may not
     * enter their attacked squares. Capture candidates separately test whether
     * moving the attacker exposes its own king, using the resulting occupancy.
     */
    Bitboard attackers(int target, Color side) const {
        const auto& own = pieces[index(side)];
        Bitboard result = (knight_masks[static_cast<unsigned>(target)] & own[index(PieceType::knight)])
            | (king_masks[static_cast<unsigned>(target)] & own[index(PieceType::king)]);
        const int target_file = target % 8, target_rank = target / 8;
        const int pawn_rank = target_rank + (side == Color::white ? -1 : 1);
        for (int df : {-1, 1})
            if (on_board(target_file + df, pawn_rank))
                result |= square_bit(pawn_rank * 8 + target_file + df) & own[index(PieceType::pawn)];

        const auto diagonal = own[index(PieceType::queen)] | own[index(PieceType::bishop)];
        const auto orthogonal = own[index(PieceType::queen)] | own[index(PieceType::rook)];
        const auto& rays = slider_rays[static_cast<unsigned>(target)];
        for (std::size_t direction = 0; direction < ray_directions.size(); ++direction) {
            const auto blockers = rays[direction] & occupied;
            if (!blockers) continue;
            const auto [df, dr] = ray_directions[direction];
            // Square numbers are monotonic along each ray. The nonzero guard
            // keeps both bit scans and the resulting square_bit within bounds.
            const int nearest = df + 8 * dr > 0 ? std::countr_zero(blockers)
                                               : 63 - std::countl_zero(blockers);
            result |= square_bit(nearest) & (df && dr ? diagonal : orthogonal);
        }
        return result;
    }

    /** Select one legal LVA, including dynamic x-rays and king recaptures.
     * A pawn is selected at pawn value even when the capture promotes; its new
     * queen value becomes the next victim and the promotion bonus is explicit.
     */
    bool recapture(int target, Color side, PieceType victim, int& gain, PieceType& occupant) {
        const auto candidates = attackers(target, side);
        for (unsigned type = 1; type <= 6; ++type) {
            auto sources = candidates & pieces[index(side)][type];
            while (sources) {
                const int from = std::countr_zero(sources);
                sources &= sources - 1;
                const auto attacker = static_cast<PieceType>(type);
                const bool promotes = attacker == PieceType::pawn
                    && target / 8 == (side == Color::white ? 7 : 0);
                const auto placed = promotes ? PieceType::queen : attacker;
                auto next = *this;
                next.remove(opposite(side), victim, target);
                next.remove(side, attacker, from);
                next.place(side, placed, target);
                if (next.attackers(next.kings[index(side)], opposite(side))) continue;
                *this = next;
                gain = value(victim) + (promotes ? value(PieceType::queen) - value(PieceType::pawn) : 0);
                occupant = placed;
                return true;
            }
        }
        return false;
    }
};

} // namespace

int static_exchange(const Position& position, Move move) noexcept {
    assert(move.valid() && position.at(move.from));
    if (!move.is_capture() && move.promotion == PieceType::none) return 0;
    const auto side = position.turn();
    const auto attacker = type_of(position.at(move.from));
    const int captured_square = move.flags & en_passant
        ? int(move.to) + (side == Color::white ? -8 : 8) : move.to;
    const auto victim = type_of(position.at(captured_square));
    auto occupant = move.promotion == PieceType::none ? attacker : move.promotion;
    ExchangeBoard board(position);
    board.remove(side, attacker, move.from);
    if (victim != PieceType::none) board.remove(opposite(side), victim, captured_square);
    board.place(side, occupant, move.to);

    // A board has 64 squares; every recapture removes a piece. The fixed array
    // therefore covers even unusual legal FENs without a heap allocation.
    std::array<int, 64> gains{};
    gains[0] = value(victim) + value(occupant) - value(attacker);
    std::size_t count = 1;
    auto reply = opposite(side);
    while (occupant != PieceType::king && count < gains.size()
           && board.recapture(move.to, reply, occupant, gains[count], occupant)) {
        ++count;
        reply = opposite(reply);
    }
    int continuation = 0;
    while (--count > 0) continuation = std::max(0, gains[count] - continuation);
    return gains[0] - continuation;
}

} // namespace chess0live
