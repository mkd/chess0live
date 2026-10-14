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
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
using namespace chess0live;
using namespace chess0live::search_policy;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
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
        protected_nodes_and_ordering();
        protected_move_types();
        std::cout << "Selective-search policy checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Search-policy test failed: " << error.what() << '\n';
        return 1;
    }
}
