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
#include <cstdint>

namespace chess0live::search_policy {

/** Eligibility for an experimental losing-capture filter in quiescence.
 * scout describes the original entry window, before stand-pat changes alpha.
 * More than eight pieces also keeps the capture's child outside seven-piece
 * endings. These exclusions limit exposure; SEE is not a tactical proof.
 */
struct QSearchSeeContext {
    int ply = 0;
    bool in_check = false;
    bool special_window = false;
    bool speculative = false;
    bool repeated = false;
    bool advanced_pawn = false;
    unsigned halfmove = 0;
    int pieces = 0;
    bool scout = false;
};

constexpr bool qsearch_see_eligible(const QSearchSeeContext& c) {
    return c.ply > 0 && c.scout && !c.in_check && !c.special_window
        && !c.speculative && !c.repeated && !c.advanced_pawn
        && c.halfmove < 80 && c.pieces > 8;
}

constexpr bool qsearch_see_capture(bool capture, bool promotion, bool en_passant) {
    return capture && !promotion && !en_passant;
}

/** A negative exchange estimate proposes a skip only after examining the real
 * child. Checks and terminal children retain ordinary search. Nonchecking
 * sacrifices with off-square threats can still be missed by this heuristic.
 */
constexpr bool qsearch_see_skip(int see, bool child_in_check, bool child_has_legal_moves) {
    return see < 0 && !child_in_check && child_has_legal_moves;
}

/** Eligibility for one frozen reverse-futility hypothesis. A quiet position
 * here has no legal capture or promotion; quiet checking moves are not excluded.
 * Terminal states and actual draws must be handled before applying this policy.
 * The guards and margins reduce risk, but cannot prove tactical safety.
 */
struct ReverseFutilityContext {
    int depth = 0;
    int ply = 0;
    bool pv_node = false;
    bool in_check = false;
    bool special_window = false;
    bool speculative = false;
    bool repeated = false;
    bool advanced_pawn = false;
    bool tactical_moves = false;
    unsigned halfmove = 0;
    int non_pawns = 0;
    int pawns = 0;
    int pieces = 0;
    std::size_t legal_moves = 0;
};

constexpr bool reverse_futility_eligible(const ReverseFutilityContext& c) {
    return c.depth >= 1 && c.depth <= 3 && c.ply > 0 && !c.pv_node
        && !c.in_check && !c.special_window && !c.speculative && !c.repeated
        && !c.advanced_pawn && !c.tactical_moves && c.halfmove < 80
        && c.non_pawns >= 2 && c.pawns >= 1 && c.pieces > 7 && c.legal_moves >= 2;
}

/** Fixed internal score-unit margins, not tunable UCI parameters. Zero denotes
 * an unsupported depth; eligibility must still be checked by every caller.
 */
constexpr int reverse_futility_margin(int depth) {
    return depth >= 1 && depth <= 3 ? 50 + 150 * depth : 0;
}

constexpr bool reverse_futility_cutoff(const ReverseFutilityContext& c,
                                     int evaluation, int beta, int score_limit) {
    return reverse_futility_eligible(c) && score_limit > 0
        && evaluation > -score_limit && evaluation < score_limit
        && beta > -score_limit && beta < score_limit
        && std::int64_t(evaluation) - std::int64_t(beta) >= reverse_futility_margin(c.depth);
}

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

/** Inputs to the accepted, deliberately narrow late-move reduction policy.
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
 * can miss a tactic. The accepted policy is enabled by default with an explicit
 * opt-out; the separate deeper-reduction hypothesis below remains opt-in.
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

/** Propose one additional ply of reduction for one fixed opt-in hypothesis.
 * The accepted one-ply predicate remains authoritative and unchanged. Only
 * ninth-or-later ordinary piece moves at depth five or more can receive the
 * second ply; every pawn/king move and seven-piece ending keeps its accepted
 * treatment. The caller still excludes speculative search modes and checking
 * children and verifies every reduced alpha-raiser at the original depth.
 * These guards limit exposure; a reduced fail-low is not a tactical proof.
 */
constexpr bool deep_quiet_reduction(const LateMoveContext& context, int pieces) {
    if (!reduce_late_move(context) || context.depth < 5
        || context.searched_moves < 8 || pieces <= 7)
        return false;
    const auto type = type_of(context.moved);
    return type == PieceType::knight || type == PieceType::bishop
        || type == PieceType::rook || type == PieceType::queen;
}

} // namespace chess0live::search_policy
