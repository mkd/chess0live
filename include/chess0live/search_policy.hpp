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

#include <cstddef>

namespace chess0live::search_policy {

/** Cheap eligibility for the first verified null-move experiment. The search
 * supplies material/history facts before paying for a fresh static evaluation.
 * These exclusions reduce zugzwang exposure; they cannot rule it out generally.
 */
struct NullMoveContext {
    int depth = 0;
    int ply = 0;
    bool pv_node = false;
    bool in_check = false;
    bool special_window = false;
    bool speculative = false;
    bool repeated = false;
    bool advanced_pawn = false;
    unsigned halfmove = 0;
    int non_pawns = 0;
    int pawns = 0;
    int pieces = 0;
    std::size_t legal_moves = 0;
};

constexpr bool probe_null_move(const NullMoveContext& c) {
    return c.depth >= 5 && c.ply > 0 && !c.pv_node && !c.in_check
        && !c.special_window && !c.speculative && !c.repeated && !c.advanced_pawn
        && c.halfmove < 80 && c.non_pawns >= 2 && c.pawns >= 1
        && c.pieces > 7 && c.legal_moves >= 2;
}

/** Inputs to the first, deliberately narrow late-move reduction experiment.
 * searched_moves counts earlier moves already searched at this node. The moved
 * piece and move flags describe the parent position; child_in_check describes
 * the position after making that move. No state is changed by this policy.
 */
struct LateMoveContext {
    int depth = 0;
    int ply = 0;
    std::size_t searched_moves = 0;
    bool pv_node = false;
    bool parent_in_check = false;
    bool child_in_check = false;
    bool mate_window = false;
    Move move;
    Piece moved = 0;
    Move tt_move;
    Move killer_a;
    Move killer_b;
};

/** Permit exactly one ply less work on sufficiently late quiet scout moves.
 * Checks, special moves, ordering hints, and advanced pawn pushes retain their
 * ordinary depth. A successful reduced scout still requires ordinary-depth
 * verification in the search; a reduced fail-low is a heuristic assumption and
 * can miss a tactic. This policy is experimental and disabled by default.
 */
constexpr bool reduce_late_move(const LateMoveContext& context) {
    if (context.depth < 3 || context.ply <= 0 || context.searched_moves < 4
        || context.pv_node || context.parent_in_check || context.child_in_check
        || context.mate_window || !context.move.valid() || context.moved == 0)
        return false;
    if (context.move.is_capture() || context.move.promotion != PieceType::none
        || (context.move.flags & castle) || context.move == context.tt_move
        || context.move == context.killer_a || context.move == context.killer_b)
        return false;
    if (type_of(context.moved) == PieceType::pawn) {
        const int rank = context.move.to / 8;
        const int relative_rank = color_of(context.moved) == Color::white ? rank : 7 - rank;
        if (relative_rank >= 5) return false; // White rank 6+; Black rank 3-.
    }
    return true;
}

} // namespace chess0live::search_policy
