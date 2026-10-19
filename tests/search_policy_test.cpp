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

/** Each independent RFP exclusion is exercised with all remaining facts at an
 * eligible boundary. These are policy tests, not a proof of tactical safety.
 */
ReverseFutilityContext futility_candidate() {
    ReverseFutilityContext context;
    context.depth = 1;
    context.ply = 1;
    context.halfmove = 79;
    context.non_pawns = 2;
    context.pawns = 1;
    context.pieces = 8;
    context.legal_moves = 2;
    return context;
}

void protected_reverse_futility_nodes() {
    require(!reverse_futility_eligible({}), "Unspecified nodes cannot be reverse-pruned");
    const auto base = futility_candidate();
    require(reverse_futility_eligible(base), "Boundary RFP context must be eligible");
    struct Exclusion {
        bool ReverseFutilityContext::*member;
        std::string_view reason;
    };
    for (const auto exclusion : {
        Exclusion{&ReverseFutilityContext::pv_node, "PV nodes retain ordinary search"},
        Exclusion{&ReverseFutilityContext::in_check, "Check evasions retain ordinary search"},
        Exclusion{&ReverseFutilityContext::special_window, "Mate/tablebase windows retain ordinary search"},
        Exclusion{&ReverseFutilityContext::speculative, "Null-probe and verification descendants cannot reverse-prune"},
        Exclusion{&ReverseFutilityContext::repeated, "A repeated current position cannot reverse-prune"},
        Exclusion{&ReverseFutilityContext::advanced_pawn, "Advanced pawns of either color veto RFP"},
        Exclusion{&ReverseFutilityContext::tactical_moves, "Any legal capture or promotion vetoes RFP"}}) {
        auto context = base;
        context.*(exclusion.member) = true;
        require(!reverse_futility_eligible(context), exclusion.reason);
        require(!reverse_futility_cutoff(context, 1000, 0, 30000), exclusion.reason);
        context.*(exclusion.member) = false;
        require(reverse_futility_eligible(context), "Clearing one guard restores eligibility");
    }
    for (const int depth : {-1, 0, 4, 20, std::numeric_limits<int>::max()}) {
        auto context = base;
        context.depth = depth;
        require(!reverse_futility_eligible(context) && reverse_futility_margin(depth) == 0,
                "Only remaining depths one to three have an RFP margin");
        require(!reverse_futility_cutoff(context, 1000, 0, 30000), "Invalid depth cannot reverse-prune");
    }
    for (const int ply : {-1, 0}) {
        auto context = base;
        context.ply = ply;
        require(!reverse_futility_eligible(context), "Root and invalid plies cannot reverse-prune");
    }
    for (const unsigned halfmove : {80U, 100U, std::numeric_limits<unsigned>::max()}) {
        auto context = base;
        context.halfmove = halfmove;
        require(!reverse_futility_eligible(context), "Draw-near clocks retain ordinary search");
    }
    for (const int non_pawns : {0, 1}) {
        auto context = base;
        context.non_pawns = non_pawns;
        require(!reverse_futility_eligible(context), "Low nonpawn material retains ordinary search");
    }
    auto context = base;
    context.pawns = 0;
    require(!reverse_futility_eligible(context), "Pawnless positions retain ordinary search");
    context = base;
    context.pieces = 7;
    require(!reverse_futility_eligible(context), "Tablebase-size positions retain ordinary search");
    for (const std::size_t moves : {std::size_t{0}, std::size_t{1}}) {
        context = base;
        context.legal_moves = moves;
        require(!reverse_futility_eligible(context), "Terminal and forced-move nodes retain ordinary search");
    }
}

void reverse_futility_score_boundaries() {
    auto context = futility_candidate();
    for (int depth = 1; depth <= 3; ++depth) {
        context.depth = depth;
        const int margin = 50 + 150 * depth;
        require(reverse_futility_margin(depth) == margin, "Frozen RFP margins changed");
        for (const int beta : {-1000, 0, 1000}) {
            require(!reverse_futility_cutoff(context, beta + margin - 1, beta, 30000),
                    "A score one point short cannot fail high");
            require(reverse_futility_cutoff(context, beta + margin, beta, 30000),
                    "The exact depth-dependent margin is inclusive");
            require(reverse_futility_cutoff(context, beta + margin + 1, beta, 30000),
                    "A score beyond the margin is eligible");
        }
    }
    context.depth = 1;
    for (const int band : {29000, 30000}) {
        for (const int score : {-band, band, -band - 1, band + 1,
                                std::numeric_limits<int>::min(), std::numeric_limits<int>::max()}) {
            require(!reverse_futility_cutoff(context, score, -1000, band),
                    "Mate/tablebase/out-of-range evaluations cannot reverse-prune");
            require(!reverse_futility_cutoff(context, 1000, score, band),
                    "Mate/tablebase/out-of-range beta cannot reverse-prune");
        }
        require(reverse_futility_cutoff(context, band - 1, band - 201, band),
                "An ordinary positive score immediately below the band can pass");
        require(reverse_futility_cutoff(context, -band + 201, -band + 1, band),
                "An ordinary negative score immediately above the band can pass");
    }
    // Both operands pass the band check, but their difference exceeds INT_MAX.
    // Widening must occur before subtraction; UBSan checks this call too.
    const int maximum = std::numeric_limits<int>::max();
    require(reverse_futility_cutoff(context, maximum - 1, -maximum + 1, maximum),
            "Large valid operands require wide score subtraction");
    require(!reverse_futility_cutoff(context, -maximum + 1, maximum - 1, maximum),
            "A large negative difference must not wrap into a false cutoff");
    for (const int invalid_band : {-1, 0})
        require(!reverse_futility_cutoff(context, 1000, 0, invalid_band),
                "Nonpositive score bands admit no evaluation");
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
        protected_reverse_futility_nodes();
        reverse_futility_score_boundaries();
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
