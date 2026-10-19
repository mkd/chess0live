/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/search_policy.hpp"

#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
using namespace chess0live;
using namespace chess0live::search_policy;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

/** Put every numeric guard at its least restrictive accepted boundary. Changing
 * one field below therefore tests that exclusion independently of the others.
 * Actual board extraction and static-evaluation gates are search-level tests.
 */
NullMoveContext null_candidate() {
    NullMoveContext context;
    context.depth = 5;
    context.ply = 1;
    context.halfmove = 79;
    context.non_pawns = 2;
    context.pawns = 1;
    context.pieces = 8;
    context.legal_moves = 2;
    return context;
}

void protected_null_nodes() {
    require(!probe_null_move({}), "An unspecified node must not permit null pruning");
    const auto base = null_candidate();
    require(probe_null_move(base), "The restrictive null-probe boundaries are inclusive as documented");
    auto context = base;
    for (const int depth : {-1, 0, 1, 4}) {
        context.depth = depth;
        require(!probe_null_move(context), "Null probes require at least five remaining plies");
    }
    for (const int depth : {5, 6, 12}) {
        context.depth = depth;
        require(probe_null_move(context), "Eligible deeper nodes remain eligible without parameter tuning");
    }
    context = base;
    for (const int ply : {-1, 0}) {
        context.ply = ply;
        require(!probe_null_move(context), "Root and invalid negative plies cannot be null-pruned");
    }
    for (const int ply : {1, 2, 12}) {
        context.ply = ply;
        require(probe_null_move(context), "Ordinary interior nodes can pass the ply guard");
    }

    // Every context flag independently vetoes a node otherwise exactly eligible.
    // In particular, speculative covers all descendants of either the fake
    // probe or its real-position verification, not only consecutive passes.
    struct Exclusion {
        bool NullMoveContext::*member;
        std::string_view reason;
    };
    for (const auto exclusion : {
        Exclusion{&NullMoveContext::pv_node, "Principal-variation nodes cannot be null-pruned"},
        Exclusion{&NullMoveContext::in_check, "An evasion cannot be replaced by a pass"},
        Exclusion{&NullMoveContext::special_window, "Mate and tablebase windows retain ordinary search"},
        Exclusion{&NullMoveContext::speculative, "Nested probes and verification descendants cannot null-prune"},
        Exclusion{&NullMoveContext::repeated, "A previous current-position occurrence prevents a null probe"},
        Exclusion{&NullMoveContext::advanced_pawn, "An advanced pawn of either color prevents a null probe"}}) {
        context = base;
        context.*(exclusion.member) = true;
        require(!probe_null_move(context), exclusion.reason);
        context.*(exclusion.member) = false;
        require(probe_null_move(context), "Clearing the sole exclusion restores the original eligible context");
    }

    context = base;
    for (const unsigned halfmove : {0U, 1U, 78U, 79U}) {
        context.halfmove = halfmove;
        require(probe_null_move(context), "Halfmove clocks below eighty can pass the null guard");
    }
    for (const unsigned halfmove : {80U, 99U, 100U, std::numeric_limits<unsigned>::max()}) {
        context.halfmove = halfmove;
        require(!probe_null_move(context), "The eighty-halfmove exclusion must not wrap at large clocks");
    }
}

void protected_null_material_and_mobility() {
    const auto base = null_candidate();
    auto context = base;
    for (const int pieces : {0, 1}) {
        context.non_pawns = pieces;
        require(!probe_null_move(context), "King-pawn and lone-nonpawn material cannot be null-pruned");
    }
    for (const int pieces : {2, 3, 7}) {
        context.non_pawns = pieces;
        require(probe_null_move(context), "Two or more own nonpawn nonking pieces pass this material guard");
    }
    context = base;
    context.pawns = 0;
    require(!probe_null_move(context), "A side without pawns is excluded even with several pieces");
    for (const int pawns : {1, 2, 8}) {
        context.pawns = pawns;
        require(probe_null_move(context), "At least one own pawn is sufficient for the pawn guard");
    }
    context = base;
    for (const int pieces : {2, 6, 7}) {
        context.pieces = pieces;
        require(!probe_null_move(context), "Every position of seven or fewer pieces retains ordinary search");
    }
    for (const int pieces : {8, 9, 32}) {
        context.pieces = pieces;
        require(probe_null_move(context), "Eight or more total pieces can pass the tablebase-size exclusion");
    }
    context = base;
    for (const std::size_t moves : {std::size_t{0}, std::size_t{1}}) {
        context.legal_moves = moves;
        require(!probe_null_move(context), "Terminal and single-choice nodes cannot be null-pruned");
    }
    for (const std::size_t moves : {std::size_t{2}, std::size_t{20}, std::size_t{218}}) {
        context.legal_moves = moves;
        require(probe_null_move(context), "At least two legal choices can pass the mobility guard");
    }
}

LateMoveContext quiet_candidate() {
    LateMoveContext context;
    context.depth = 3;
    context.ply = 1;
    context.searched_moves = 4;
    context.move = {1, 18}; // b1-c3, a quiet knight move.
    context.moved = make_piece(Color::white, PieceType::knight);
    return context;
}

void protected_nodes_and_ordering() {
    const auto base = quiet_candidate();
    require(reduce_late_move(base), "The fifth quiet scout at depth three is eligible");
    auto context = base;
    context.depth = 2;
    require(!reduce_late_move(context), "Near-horizon nodes retain ordinary depth");
    context = base;
    context.searched_moves = 3;
    require(!reduce_late_move(context), "The first four moves retain ordinary depth");
    context = base;
    context.ply = 0;
    require(!reduce_late_move(context), "Root moves retain ordinary depth");
    for (int flag = 0; flag < 4; ++flag) {
        context = base;
        if (flag == 0) context.pv_node = true;
        if (flag == 1) context.parent_in_check = true;
        if (flag == 2) context.child_in_check = true;
        if (flag == 3) context.mate_window = true;
        require(!reduce_late_move(context), "PV nodes, evasions, checks, and mate windows are protected");
    }
    for (int hint = 0; hint < 3; ++hint) {
        context = base;
        if (hint == 0) context.tt_move = context.move;
        if (hint == 1) context.killer_a = context.move;
        if (hint == 2) context.killer_b = context.move;
        require(!reduce_late_move(context), "Hash and killer ordering hints remain protected even if late");
    }
}

void protected_move_types() {
    auto context = quiet_candidate();
    context.move.flags = capture;
    require(!reduce_late_move(context), "Captures retain ordinary depth");
    context.move.flags = capture | en_passant;
    require(!reduce_late_move(context), "En passant retains ordinary depth");
    context.move = {4, 6, PieceType::none, castle};
    context.moved = make_piece(Color::white, PieceType::king);
    require(!reduce_late_move(context), "Castling retains ordinary depth even without check");
    for (auto promotion : {PieceType::knight, PieceType::bishop, PieceType::rook, PieceType::queen}) {
        context.move = {48, 56, promotion};
        context.moved = make_piece(Color::white, PieceType::pawn);
        require(!reduce_late_move(context), "Every promotion type retains ordinary depth");
    }
    for (auto color : {Color::white, Color::black}) {
        context = quiet_candidate();
        context.moved = make_piece(color, PieceType::pawn);
        context.move = color == Color::white ? Move{24, 32} : Move{32, 24};
        require(reduce_late_move(context), "An ordinary fifth-rank quiet pawn push may be reduced");
        context.move = color == Color::white ? Move{32, 40} : Move{24, 16};
        require(!reduce_late_move(context), "Both colors' sixth-rank pawn pushes are protected");
        context.move = color == Color::white ? Move{40, 48} : Move{16, 8};
        require(!reduce_late_move(context), "Both colors' seventh-rank pawn pushes are protected");
    }
}
} // namespace

int main() {
    try {
        protected_null_nodes();
        protected_null_material_and_mobility();
        protected_nodes_and_ordering();
        protected_move_types();
        std::cout << "Selective-search policy checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Search-policy test failed: " << error.what() << '\n';
        return 1;
    }
}
