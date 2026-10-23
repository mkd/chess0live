/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"
#include "chess0live/search.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using namespace chess0live;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    const auto position = Position::from_fen(text, error);
    if (!position) throw std::runtime_error("Fixture FEN: " + error);
    return *position;
}

bool legal(Position position, Move move) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), move) != moves.end();
}

SearchLimits limits(int depth = 5) {
    SearchLimits request;
    request.late_move_reductions = false; // Combined-policy cases opt in explicitly.
    request.depth = depth;
    request.nodes = 200000;
    request.reverse_futility_pruning = true;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    return request;
}

struct Observation {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

/** Validate public moves and exact joined accounting after every search. A
 * pruned scout may return a bound but cannot invent a PV or incomplete root.
 */
Observation run(Search& search, Position position, const SearchLimits& request,
                std::vector<std::uint64_t> history = {}, bool reset_stop = true) {
    Observation observation;
    if (reset_stop) search.reset_stop();
    observation.result = search.search(position, std::move(history), request,
        [&](const SearchInfo& info) {
            auto replay = position;
            for (const auto move : info.pv) {
                require(move.valid() && legal(replay, move), "RFP search exposed an illegal PV move");
                replay.make_move(move);
            }
            require(info.hashfull >= 0 && info.hashfull <= 1000, "Invalid hashfull");
            observation.reports.push_back(info);
        });
    const auto& result = observation.result;
    if (position.legal_moves().empty()) require(!result.best.valid(), "Terminal root returned a move");
    else {
        require(legal(position, result.best), "RFP search exposed an illegal root move");
        if (result.ponder.valid()) {
            position.make_move(result.best);
            require(legal(position, result.ponder), "RFP search exposed an illegal ponder move");
        }
    }
    const auto& r = result.reverse_futility;
    require(r.enabled == request.reverse_futility_pruning, "RFP option flag is stale");
    require(r.cutoffs <= r.evaluations, "More reverse cutoffs than eligible evaluations");
    if (!request.diagnostics || !request.reverse_futility_pruning)
        require(r.evaluations == 0 && r.cutoffs == 0, "Inactive RFP diagnostics retained counters");
    require(std::accumulate(result.smp.worker_nodes.begin(), result.smp.worker_nodes.end(),
                            std::uint64_t{0}) == result.nodes,
            "Joined worker node totals do not equal the aggregate");
    if (result.diagnostics) {
        std::uint64_t leader_nodes = 0;
        for (const auto& iteration : result.diagnostics->iterations) leader_nodes += iteration.nodes;
        require(!result.smp.worker_nodes.empty() && leader_nodes == result.smp.worker_nodes.front(),
                "Iteration nodes must account for every leader visit");
    }
    if (request.nodes != 0) require(result.nodes <= request.nodes, "RFP search exceeded node cap");
    return observation;
}

void same_search(const Observation& actual, const Observation& expected) {
    const auto& a = actual.result;
    const auto& e = expected.result;
    require(a.best == e.best && a.ponder == e.ponder && a.score == e.score
            && a.depth == e.depth && a.nodes == e.nodes, "Fresh-search signature differs");
    require(actual.reports.size() == expected.reports.size(), "Iteration count differs");
    for (std::size_t i = 0; i < actual.reports.size(); ++i) {
        const auto& ar = actual.reports[i];
        const auto& er = expected.reports[i];
        require(ar.depth == er.depth && ar.seldepth == er.seldepth && ar.nodes == er.nodes
                && ar.score == er.score && ar.pv == er.pv, "Completed iteration signature differs");
    }
}

/** Equivalent fresh policies must agree exactly; selective versus baseline
 * scores need not agree. This catches stale TT/history after policy changes.
 */
void policies_and_diagnostics(Search& search, const Position& position) {
    auto request = limits();
    request.reverse_futility_pruning = false;
    search.clear();
    const auto baseline = run(search, position, request);
    require(baseline.result.depth == request.depth, "Baseline fixture exceeded node ceiling");
    request.reverse_futility_pruning = true;
    const auto candidate = run(search, position, request);
    require(candidate.result.depth == request.depth && candidate.result.reverse_futility.evaluations > 0
            && candidate.result.reverse_futility.cutoffs > 0,
            "The bounded activation fixture must exercise real reverse cutoffs");
    request.reverse_futility_pruning = false;
    same_search(run(search, position, request), baseline);
    request.reverse_futility_pruning = true;
    same_search(run(search, position, request), candidate);
    search.clear();
    request.diagnostics = false;
    same_search(run(search, position, request), candidate);
    search.clear();
    request.diagnostics = true;
    same_search(run(search, position, request), candidate);
    std::cout << "PASS RFP activation: evaluations " << candidate.result.reverse_futility.evaluations
              << ", cutoffs " << candidate.result.reverse_futility.cutoffs << '\n';
}

void protected_roots(Search& search) {
    auto request = limits(4);
    for (const auto text : {
        "7k/6Q1/6K1/8/8/8/8/8 b - - 100 51", // Checkmate overrides the draw clock.
        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",   // Stalemate.
        "7k/8/5KQ1/8/8/8/8/8 w - - 99 51", // Mate at the rule-50 boundary.
        "8/8/2k5/2p5/2P5/2K5/8/8 w - - 0 30", // Pawn-only zugzwang exposure.
        "8/8/3k4/2p5/2P5/3K4/1N6/8 w - - 0 31", // Sparse minor ending.
        "6k1/1P6/8/8/8/8/6p1/3K4 w - - 0 45"}) { // Promotion race.
        const auto position = fen(text);
        request.reverse_futility_pruning = false;
        search.clear();
        const auto baseline = run(search, position, request);
        request.reverse_futility_pruning = true;
        const auto candidate = run(search, position, request);
        same_search(candidate, baseline);
        require(candidate.result.reverse_futility.evaluations == 0,
                "Entire sparse search must retain ordinary search");
    }
    require(run(search, fen("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51"), request).result.score
                == -Search::mate_score, "Terminal mate must precede rule 50");
    require(run(search, fen("7k/8/5KQ1/8/8/8/8/8 w - - 99 51"), request).result.score
                == Search::mate_score - 1, "Mate distance changed at rule-50 boundary");

    auto position = Position::start();
    std::vector<std::uint64_t> history{position.key()};
    constexpr std::array<std::string_view, 4> cycle{"g1f3", "g8f6", "f3g1", "f6g8"};
    for (int repeat = 0; repeat < 2; ++repeat) {
        for (auto text : cycle) {
            const auto move = parse_uci_move(position, text);
            require(move.has_value(), "Invalid repetition fixture move");
            position.make_move(*move);
            history.push_back(position.key());
        }
        const auto result = run(search, position, request, history).result;
        if (repeat == 0) require(result.nodes > 0, "Twofold history became a draw");
        else require(result.nodes == 0 && result.score == 0 && result.reverse_futility.evaluations == 0,
                     "Threefold root must return before reverse pruning");
    }
    history.pop_back();
    require(run(search, position, request, history).result.nodes == 0,
            "Missing final root must be appended before checking repetition");
    require(run(search, position, request).result.nodes > 0,
            "A previous repetition history leaked into the next search");
}

void bounded_workers_and_combinations(Search& search, const Position& position) {
    for (const int threads : {1, 4}) {
        search.set_threads(threads);
        auto request = limits();
        request.depth = 0;
        for (const auto cap : {std::uint64_t{1}, std::uint64_t{257}, std::uint64_t{40000}}) {
            search.clear();
            request.nodes = cap;
            const auto result = run(search, position, request).result;
            require(result.nodes == cap && result.smp.threads == threads
                    && result.smp.worker_nodes.size() == static_cast<std::size_t>(threads)
                    && result.diagnostics->stop_reason == StopReason::node_limit,
                    "One aggregate node cap must cover every worker");
        }
        request.nodes = 0;
        search.reset_stop();
        search.stop();
        const auto stopped = run(search, position, request, {}, false).result;
        require(stopped.nodes == 0 && stopped.reverse_futility.evaluations == 0
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "Published stop must survive worker preparation");
        request.received_at = std::chrono::steady_clock::now() - std::chrono::seconds(1);
        request.movetime_ms = 1;
        const auto expired = run(search, position, request).result;
        require(expired.nodes == 0 && expired.reverse_futility.evaluations == 0,
                "Expired receipt must exclude all pruning work");
        request.received_at.reset();
        request.movetime_ms = -1;
        request.depth = 5;
        request.nodes = 200000;
        search.reset_stop();
        const auto stopped_by_callback = search.search(position, {}, request, [&](const SearchInfo& info) {
            if (info.depth == 2) search.stop();
        });
        require(stopped_by_callback.depth == 2 && legal(position, stopped_by_callback.best)
                && stopped_by_callback.diagnostics->stop_reason == StopReason::external_stop,
                "Leader cancellation must retain a completed iteration and join helpers");

        // This exercises public composition, not every possible speculative
        // subtree. Pure policy checks and source review cover the mode veto.
        for (const bool null_enabled : {false, true}) {
            request.null_move_pruning = null_enabled;
            request.late_move_reductions = true;
            request.depth = 6;
            request.nodes = 120000;
            search.clear();
            const auto combined = run(search, position, request).result;
            require(combined.nullmove.enabled == null_enabled && combined.lmr.enabled,
                    "Combined-search option snapshots are stale");
            require(combined.nullmove.cutoffs + combined.nullmove.rejected
                        <= combined.nullmove.verifications,
                    "Nested policy composition corrupted verification accounting");
        }
        request = limits(2);
        require(run(search, position, request).result.depth == 2,
                "Ordinary policy must remain reusable after combination and cancellation");
    }
    search.set_threads(1);
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: reverse-futility-search-test NETWORK");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned network");
        Search search(network, 1);
        const auto position = Position::start();
        const auto root_fen = position.fen();
        const auto root_key = position.key();
        policies_and_diagnostics(search, position);
        protected_roots(search);
        bounded_workers_and_combinations(search, position);
        require(position.fen() == root_fen && position.key() == root_key,
                "Search changed the caller's root position");
        std::cout << "PASS reverse futility search: activation, policy reset, diagnostics, sparse/terminal "
                     "and repetition rules, stop/clock/node limits, 1/4 workers and policy composition\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL reverse futility search: " << error.what() << '\n';
        return 1;
    }
}
