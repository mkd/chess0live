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
#include <filesystem>
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

Move parsed(Position position, std::string_view text) {
    const auto move = parse_uci_move(position, text);
    if (!move) throw std::runtime_error("Fixture move: " + std::string(text));
    return *move;
}

SearchLimits limits(int depth = 6) {
    SearchLimits request;
    request.late_move_reductions = false; // Isolate null search from the LMR default.
    request.depth = depth;
    request.nodes = 200000;
    request.null_move_pruning = true;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    return request;
}

struct Observation {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

/** Replay public principal variations as legal game moves. A speculative pass
 * may never escape through a PV, bestmove, or ponder move, even after abort.
 */
Observation run(Search& search, Position position, const SearchLimits& request,
                std::vector<std::uint64_t> history = {}, bool reset_stop = true) {
    Observation observation;
    if (reset_stop) search.reset_stop();
    observation.result = search.search(position, std::move(history), request,
        [&](const SearchInfo& info) {
            auto replay = position;
            for (const auto move : info.pv) {
                require(move.valid() && legal(replay, move), "Null search exposed an illegal PV move");
                replay.make_move(move);
            }
            require(info.hashfull >= 0 && info.hashfull <= 1000, "Invalid hashfull");
            observation.reports.push_back(info);
        });
    const auto& result = observation.result;
    if (!position.legal_moves().empty()) {
        require(legal(position, result.best), "Null search exposed an illegal root move");
        if (result.ponder.valid()) {
            position.make_move(result.best);
            require(legal(position, result.ponder), "Null search exposed an illegal ponder move");
        }
    } else require(!result.best.valid(), "Terminal root returned a move");
    require(result.nullmove.enabled == request.null_move_pruning, "Null option flag is stale");
    const auto& n = result.nullmove;
    require(n.fail_highs == n.verifications && n.verifications <= n.probes
            && n.cutoffs + n.rejected <= n.verifications,
            "Null diagnostics have inconsistent attempt/outcome counts");
    if (!request.diagnostics || !request.null_move_pruning)
        require(n.probes == 0 && n.fail_highs == 0 && n.verifications == 0
                && n.cutoffs == 0 && n.rejected == 0, "Inactive null diagnostics retained counts");
    require(std::accumulate(result.smp.worker_nodes.begin(), result.smp.worker_nodes.end(),
                            std::uint64_t{0}) == result.nodes,
            "Joined worker node totals do not equal the public aggregate");
    if (result.diagnostics) {
        std::uint64_t leader_nodes = 0;
        for (const auto& iteration : result.diagnostics->iterations) leader_nodes += iteration.nodes;
        require(!result.smp.worker_nodes.empty()
                && leader_nodes == result.smp.worker_nodes.front(),
                "Iteration nodes must account for every leader visit, including null work");
    }
    if (request.nodes != 0) require(result.nodes <= request.nodes, "Null search exceeded node limit");
    return observation;
}

void same_search(const Observation& actual, const Observation& expected) {
    const auto& a = actual.result;
    const auto& e = expected.result;
    require(a.best == e.best && a.ponder == e.ponder && a.score == e.score
            && a.depth == e.depth && a.nodes == e.nodes,
            "Fresh-search score/move/depth/node signature differs");
    require(actual.reports.size() == expected.reports.size(), "Iteration count differs");
    for (std::size_t index = 0; index < actual.reports.size(); ++index) {
        const auto& ar = actual.reports[index];
        const auto& er = expected.reports[index];
        require(ar.depth == er.depth && ar.seldepth == er.seldepth && ar.nodes == er.nodes
                && ar.score == er.score && ar.pv == er.pv, "Completed iteration signature differs");
    }
}

/** Diagnostic collection is observational; policy changes clear cached bounds
 * and learned ordering before reuse. Exact agreement here is not required
 * between selective and nonselective searches, only equivalent fresh policies.
 */
Observation policies_and_diagnostics(Search& search, const Position& position) {
    auto request = limits();
    request.null_move_pruning = false;
    search.clear();
    const auto baseline = run(search, position, request);
    require(baseline.result.depth == request.depth, "Baseline fixture exceeded its fixed node cap");
    request.null_move_pruning = true;
    const auto candidate = run(search, position, request);
    require(candidate.result.depth == request.depth && candidate.result.nullmove.probes > 0
            && candidate.result.nullmove.verifications > 0,
            "Bounded start-position search must exercise actual null probes and verification");
    request.null_move_pruning = false;
    same_search(run(search, position, request), baseline);
    request.null_move_pruning = true;
    same_search(run(search, position, request), candidate);
    search.clear();
    request.diagnostics = false;
    same_search(run(search, position, request), candidate);
    search.clear();
    request.diagnostics = true;
    same_search(run(search, position, request), candidate);
    return candidate;
}

/** Locate the first attempt through the public diagnostics without depending
 * on a hard-coded node ordering. Each cleared one-worker node-capped search is
 * deterministic. At the minimum cap recording an attempt, its recursive child
 * cannot visit a node: this deliberately aborts inside the selected operation.
 * The fixed depth-6 corpus and 200,000-node ceiling bound this correctness check;
 * these searches do not select parameters or measure a performance gain.
 */
void abort_boundaries(Search& search, const Position& position, const Observation& complete) {
    auto request = limits();
    auto default_request = limits(3);
    default_request.null_move_pruning = false;
    search.clear();
    const auto default_baseline = run(search, position, default_request);
    for (const bool verification : {false, true}) {
        const auto occurred = [verification](const SearchResult& result) {
            return verification ? result.nullmove.verifications > 0 : result.nullmove.probes > 0;
        };
        std::uint64_t low = 1, high = complete.result.nodes;
        require(occurred(complete.result), "Missing required null event in reference search");
        while (low < high) {
            const auto middle = low + (high - low) / 2;
            request.nodes = middle;
            search.clear();
            const auto trial = run(search, position, request);
            if (occurred(trial.result)) high = middle;
            else low = middle + 1;
        }
        request.nodes = low;
        search.clear();
        const auto aborted = run(search, position, request);
        const auto& result = aborted.result;
        require(result.nodes == low && result.diagnostics
                && result.diagnostics->stop_reason == StopReason::node_limit
                && occurred(result) && result.nullmove.cutoffs == 0 && result.nullmove.rejected == 0,
                "Attempt boundary must abort before publishing an outcome");
        if (verification)
            require(result.nullmove.verifications == 1, "First verification boundary is not unique");
        else require(result.nullmove.probes == 1 && result.nullmove.verifications == 0,
                     "First null probe boundary unexpectedly completed a verification");
        require(result.diagnostics->iterations.back().completed == false,
                "Aborted attempt must retain an incomplete iteration record");
        same_search(run(search, position, default_request), default_baseline);
        std::cout << "PASS interrupted " << (verification ? "verification" : "null probe")
                  << " at node cap " << low << ", followed by exact fresh-default reuse\n";
    }
}

void draw_history_and_terminals(Search& search) {
    auto request = limits(3);
    for (const bool enabled : {false, true}) {
        request.null_move_pruning = enabled;
        const auto mate = run(search, fen("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51"), request).result;
        require(mate.score == -Search::mate_score && !mate.best.valid() && mate.nodes == 0,
                "Checkmate must precede rule 50");
        const auto stale = run(search, fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"), request).result;
        require(stale.score == 0 && !stale.best.valid() && stale.nodes == 0,
                "Stalemate must precede null eligibility and evaluation");
        auto mating = fen("7k/8/5KQ1/8/8/8/8/8 w - - 99 51");
        const auto found = run(search, mating, request).result;
        require(found.score == Search::mate_score - 1 && found.nullmove.probes == 0,
                "Mate at the rule-50 boundary must retain exact distance");
        mating.make_move(found.best);
        require(mating.legal_moves().empty() && mating.in_check(mating.turn()),
                "Reported mate must be checkmate on the board");

        auto position = Position::start();
        std::vector<std::uint64_t> history{position.key()};
        constexpr std::array<std::string_view, 4> cycle{"g1f3", "g8f6", "f3g1", "f6g8"};
        for (int repeat = 0; repeat < 2; ++repeat) {
            for (auto text : cycle) {
                position.make_move(parsed(position, text));
                history.push_back(position.key());
            }
            const auto result = run(search, position, request, history).result;
            if (repeat == 0) require(result.nodes > 0, "Twofold history was mistaken for a draw");
            else require(result.nodes == 0 && result.score == 0 && result.nullmove.probes == 0,
                         "Threefold history was ignored");
        }
        history.pop_back();
        require(run(search, position, request, history).result.nodes == 0,
                "Missing final root must still be appended for repetition");
        require(run(search, position, request).result.nodes > 0,
                "Past repetition cannot leak into the next history-free search");

        // Synthetic historical keys are accepted by the public API. Duplicate
        // the side-flipped board's key, never the actual root key: a fictional
        // pass must not be confused with an already-repeated real root.
        position = fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 20 11");
        auto passed = position;
        passed.make_null_move();
        const auto phantom = run(search, position, request,
            {passed.key(), passed.key(), passed.key(), position.key()}).result;
        require(phantom.nodes > 0 && phantom.depth == request.depth,
                "Duplicated fictional-pass keys invented a root draw");
    }
}

void bounded_stops_and_workers(Search& search, const Position& position) {
    for (const int threads : {1, 4}) {
        search.set_threads(threads);
        auto request = limits();
        request.depth = 0;
        for (const auto cap : {std::uint64_t{1}, std::uint64_t{257}, std::uint64_t{120000}}) {
            search.clear();
            request.nodes = cap;
            const auto result = run(search, position, request).result;
            require(result.nodes == cap && result.smp.threads == threads
                    && result.smp.worker_nodes.size() == static_cast<std::size_t>(threads)
                    && result.diagnostics->stop_reason == StopReason::node_limit,
                    "Null work must obey one aggregate node cap across all helpers");
            require(result.nullmove.verifications - result.nullmove.cutoffs - result.nullmove.rejected
                    <= static_cast<std::uint64_t>(threads),
                    "At most one unfinished verification can remain per joined worker");
        }
        request.nodes = 0;
        search.reset_stop();
        search.stop();
        const auto stopped = run(search, position, request, {}, false).result;
        require(stopped.nodes == 0 && stopped.nullmove.probes == 0
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "A published stop must survive worker preparation");

        request.received_at = std::chrono::steady_clock::now() - std::chrono::seconds(1);
        request.movetime_ms = 1;
        const auto expired = run(search, position, request).result;
        require(expired.nodes == 0 && expired.nullmove.probes == 0,
                "Expired command receipt must exclude all speculative work");
        request.received_at.reset();
        request.movetime_ms = -1;
        request.depth = 6;
        request.nodes = 200000;
        search.reset_stop();
        const auto callback_stop = search.search(position, {}, request, [&](const SearchInfo& info) {
            if (info.depth == 2) search.stop();
        });
        require(callback_stop.depth == 2 && legal(position, callback_stop.best)
                && callback_stop.diagnostics->stop_reason == StopReason::external_stop,
                "A leader stop must join helpers and retain the completed iteration");
        request.depth = 2;
        require(run(search, position, request).result.depth == 2,
                "Search must be reusable after helper cancellation and expired clocks");
    }
    search.set_threads(1);
}

void optional_tablebase_rules(Search& search, const std::filesystem::path& tables) {
    if (tables.empty()) return;
    std::string error;
    require(search.set_syzygy_path(tables.string(), error), "Cannot load requested Syzygy fixtures");
    require(search.syzygy_largest() >= 3, "Requested Syzygy directory lacks three-piece fixtures");
    auto request = limits(2);
    request.syzygy_probe_limit = 7;
    auto position = fen("k7/8/8/8/8/6Q1/8/7K w - - 0 1");
    const auto result = run(search, position, request).result;
    require(result.tbhits >= 1 && result.nullmove.probes == 0,
            "Real tablebase domain must retain probing and exclude null search");
    position = fen("k7/8/8/8/8/6Q1/8/7K w - - 20 11");
    const auto repeated = run(search, position, request,
        {position.key(), position.key(), position.key()}).result;
    require(repeated.score == 0 && repeated.nodes == 0 && repeated.tbhits == 0,
            "Root repetition must take precedence over tablebase ranking");
    require(search.set_syzygy_path("", error), "Cannot disable Syzygy after test");
    std::cout << "PASS null option with real tablebase and repetition rules\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2 || argc == 3, "Usage: null-search-test NETWORK [TABLE_DIRECTORY]");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned network");
        Search search(network, 1);
        const auto position = Position::start();
        const auto original_fen = position.fen();
        const auto original_key = position.key();
        const auto complete = policies_and_diagnostics(search, position);
        abort_boundaries(search, position, complete);
        draw_history_and_terminals(search);
        bounded_stops_and_workers(search, position);
        optional_tablebase_rules(search, argc == 3 ? std::filesystem::path(argv[2]) : std::filesystem::path{});
        require(position.fen() == original_fen && position.key() == original_key,
                "Search changed the caller's root position");
        std::cout << "PASS null search: policy reset, diagnostic parity, interrupted probes/verification, "
                     "draw and mate rules, history isolation, node/clock/stop limits, 1/4-worker accounting\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL null search: " << error.what() << '\n';
        return 1;
    }
}
