/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Exercise the actual worker-private cutoff-learning path without a production
// test API. Link Position/NNUE/exchange/tablebase objects, but not search.o.
// No search or neural evaluation runs; the network may remain unloaded.
#include "../src/search.cpp"

#include <iostream>
#include <memory>
#include <string>
#include <string_view>

namespace {
using namespace chess0live;
std::size_t comparisons = 0;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

struct LearnedState {
    decltype(SearchWorker::history_score) history;
    decltype(SearchWorker::killers) killers;
    decltype(SearchWorker::countermoves) replies;
    CountermoveStatistics counters;
};

LearnedState snapshot(const SearchWorker& worker) {
    return {worker.history_score, worker.killers, worker.countermoves, worker.countermove};
}

bool same_state(const LearnedState& left, const LearnedState& right) {
    return left.history == right.history && left.killers == right.killers
        && left.replies == right.replies && left.counters.enabled == right.counters.enabled
        && left.counters.lookups == right.counters.lookups
        && left.counters.matches == right.counters.matches
        && left.counters.updates == right.counters.updates;
}

/** Frozen former gravity arithmetic, independent of update_history(). */
void old_update(LearnedState& state, Color side, Move move, int bonus) {
    auto& score = state.history[static_cast<unsigned>(side)][move.from][move.to];
    const int bounded = std::clamp(bonus, -16384, 16384);
    score += bounded - score * std::abs(bounded) / 16384;
}

/** Former cutoff path consumes only the list collected before the cutoff.
 * The state is captured after simulated descendants/re-searches have finished,
 * never at the time the parent list was first ordered or collected.
 */
void old_cutoff(LearnedState& state, const std::vector<Move>& collected,
                Color side, Move move, int depth, int ply, std::size_t previous,
                SearchWorker::Mode mode, bool use_countermove, bool diagnostics) {
    if (mode != SearchWorker::Mode::ordinary || move.is_capture()
        || move.promotion != PieceType::none) return;
    if (use_countermove && previous != SearchWorker::no_previous_move) {
        state.replies[previous] = move;
        if (diagnostics) ++state.counters.updates;
    }
    auto& pair = state.killers[static_cast<std::size_t>(ply)];
    if (move != pair[0]) { pair[1] = pair[0]; pair[0] = move; }
    const int bonus = std::min(2048, depth * depth * 24);
    old_update(state, side, move, bonus);
    for (const auto prior : collected) old_update(state, side, prior, -bonus);
}

std::vector<Move> synthetic_moves(Color side) {
    // Deliberately include duplicates. Real legal lists do not contain them,
    // but repeated history cells make update ordering observably significant.
    // The two promotion kinds and both castle flags must retain the former
    // capture/promotion classification, independent of geometric legality here.
    std::vector<Move> moves{
        {8, 16, PieceType::none, quiet},
        {10, 19, PieceType::none, capture},
        {48, 56, PieceType::queen, quiet},
        {4, 6, PieceType::none, castle},
        {36, 43, PieceType::none, capture | en_passant},
        {9, 25, PieceType::none, double_push},
        {49, 56, PieceType::knight, capture},
        {8, 16, PieceType::none, quiet},
        {50, 58, PieceType::knight, quiet},
        {4, 2, PieceType::none, castle},
        {8, 16, PieceType::none, quiet},
    };
    if (side == Color::black)
        for (auto& move : moves) {
            move.from ^= 56;
            move.to ^= 56;
        }
    return moves;
}

void seed(SearchWorker& worker, const std::vector<Move>& moves, std::size_t cutoff,
          int ply, bool use_countermove, bool diagnostics) {
    constexpr std::array<int, 7> scores{-16384, -16383, -11999, 0, 11999, 16383, 16384};
    for (unsigned side = 0; side < 2; ++side)
        for (unsigned from = 0; from < 64; ++from)
            for (unsigned to = 0; to < 64; ++to)
                worker.history_score[side][from][to] = scores[(side + from * 64 + to) % scores.size()];
    for (auto& killers : worker.killers) killers = {moves[3], moves[5]};
    auto& pair = worker.killers[static_cast<std::size_t>(ply)];
    if (cutoff % 3 == 0) pair[0] = moves[cutoff];
    if (cutoff % 3 == 1) pair[1] = moves[cutoff];
    for (std::size_t index = 0; index < worker.countermoves.size(); ++index)
        worker.countermoves[index] = moves[index % moves.size()];
    worker.limits.countermove_ordering = use_countermove;
    worker.limits.diagnostics = diagnostics;
    worker.limits.capture_ordering = CaptureOrdering::mvv_lva;
    worker.countermove = {use_countermove, 11, 7, 3};
    worker.game_history = {0x1234, 0x5678};
}

/** Model completed descendant and re-search effects after the parent list has
 * been frozen. Reuse real ordering scratch with different lists, then apply
 * independent history updates to cells also used by the parent. The pending
 * parent cutoff must operate on these latest values, not an earlier snapshot.
 */
void simulate_descendants(SearchWorker& worker, const Position& child_position,
                          const std::vector<Move>& child_moves,
                          const std::vector<Move>& parent_moves, Color side, int ply) {
    auto ordered_child = child_moves;
    worker.order(child_position, ordered_child, {}, ply + 1);
    auto changed = snapshot(worker);
    old_update(changed, side, parent_moves[0], -777);
    old_update(changed, side, parent_moves[5], 911);
    old_update(changed, side, parent_moves[0], 333); // A re-search touches the same cell again.
    old_update(changed, opposite(side), parent_moves[3], -287);
    worker.history_score = changed.history;
    std::reverse(ordered_child.begin(), ordered_child.end());
    ordered_child.resize(3);
    worker.order(child_position, ordered_child, {}, ply + 1);
}

void differential_cases(SearchWorker& worker) {
    auto child_position = Position::start();
    const auto child_moves = child_position.legal_moves();
    constexpr std::array modes{SearchWorker::Mode::ordinary, SearchWorker::Mode::null_probe,
                               SearchWorker::Mode::verification, SearchWorker::Mode::probcut};
    for (Color side : {Color::white, Color::black}) {
        const auto parent_moves = synthetic_moves(side);
        for (int depth : {1, 3, 10, Search::max_ply - 2})
            for (const auto mode : modes)
                for (const bool use_countermove : {false, true})
                    for (const bool diagnostics : {false, true})
                        for (std::size_t cutoff = 0; cutoff < parent_moves.size(); ++cutoff) {
                            const int ply = cutoff % 2 == 0 ? 0 : 7;
                            const auto previous = cutoff % 3 == 0 ? SearchWorker::no_previous_move
                                : cutoff % 3 == 1 ? std::size_t{0} : SearchWorker::no_previous_move - 1;
                            seed(worker, parent_moves, cutoff, ply, use_countermove, diagnostics);
                            const auto before_children = worker.history_score;
                            std::vector<Move> former_collected;
                            for (std::size_t index = 0; index < cutoff; ++index) {
                                const auto move = parent_moves[index];
                                if (!move.is_capture() && move.promotion == PieceType::none)
                                    former_collected.push_back(move);
                            }
                            simulate_descendants(worker, child_position, child_moves, parent_moves, side, ply);
                            require(worker.history_score != before_children,
                                    "Descendant fixture failed to change history after parent ordering");
                            const auto before = snapshot(worker);
                            const auto game_history = worker.game_history;
                            const auto frozen_moves = parent_moves;
                            auto expected = before;
                            old_cutoff(expected, former_collected, side, parent_moves[cutoff], depth,
                                       ply, previous, mode, use_countermove, diagnostics);
                            worker.learn_quiet_cutoff(side, parent_moves, cutoff, depth, ply, previous, mode);
                            require(same_state(snapshot(worker), expected),
                                    "Cutoff learning differs from the former collected-list path");
                            require(worker.game_history == game_history && parent_moves == frozen_moves,
                                    "Cutoff learning changed game history or the frozen parent moves");
                            if (mode != SearchWorker::Mode::ordinary || parent_moves[cutoff].is_capture()
                                || parent_moves[cutoff].promotion != PieceType::none)
                                require(same_state(snapshot(worker), before),
                                        "Speculative or tactical cutoff changed learned state");
                            ++comparisons;
                        }
    }
}
} // namespace

int main() {
    try {
        nnue::Network network;
        auto shared = std::make_unique<SharedSearch>();
        auto worker = std::make_unique<SearchWorker>(network, *shared, 0);
        differential_cases(*worker);
        std::cout << "Quiet-history prefix checks passed: " << comparisons << " comparisons\n";
    } catch (const std::exception& error) {
        std::cerr << "Quiet-history prefix test failed: " << error.what() << '\n';
        return 1;
    }
}
