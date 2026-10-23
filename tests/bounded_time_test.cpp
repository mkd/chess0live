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
#include <chrono>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using namespace chess0live;
using namespace std::chrono_literals;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

bool legal(Position position, Move candidate) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), candidate) != moves.end();
}

SearchLimits ordinary_limits() {
    SearchLimits limits;
    limits.time_policy = TimePolicy::bounded;
    limits.diagnostics = true;
    limits.wtime_ms = 120000;
    limits.btime_ms = 60000;
    limits.winc_ms = 1000;
    limits.binc_ms = 500;
    limits.syzygy_probe_limit = 0;
    return limits;
}

/** Inspect the real allocation path without entering the tree or sleeping. */
SearchDiagnostics inspect(Search& search, const Position& position, const SearchLimits& limits) {
    search.reset_stop();
    search.stop();
    const auto result = search.search(position, {}, limits);
    require(result.nodes == 0 && result.diagnostics
            && result.diagnostics->iterations.empty()
            && result.diagnostics->stop_reason == StopReason::external_stop,
            "A prepublished stop must permit allocation inspection without tree work");
    require(result.diagnostics->policy == limits.time_policy,
            "Diagnostics must retain the requested policy, including an excluded bounded request");
    if (limits.time_policy == TimePolicy::bounded)
        require(!result.diagnostics->forecast_active && result.diagnostics->predicted_next_ms == 0,
                "Bounded allocation must not silently enable forecasting");
    return *result.diagnostics;
}

void expect_budget(Search& search, const Position& position, const SearchLimits& limits,
                   double soft, double hard) {
    const auto actual = inspect(search, position, limits);
    require(std::abs(actual.soft_ms - soft) < 1e-7 && std::abs(actual.hard_ms - hard) < 1e-7,
            "Real search allocation differs from the specified soft/hard budget");
    require(0 <= actual.soft_ms && actual.soft_ms <= actual.hard_ms,
            "Search allocation must retain ordered nonnegative limits");
}

void allocations_and_exclusions(Search& search) {
    const auto white = Position::start();
    auto black = white;
    const auto e4 = parse_uci_move(black, "e2e4");
    require(e4.has_value(), "Cannot form black-to-move allocation fixture");
    black.make_move(*e4);
    auto limits = ordinary_limits();
    expect_budget(search, white, limits, 4549.375, 9098.75);
    expect_budget(search, black, limits, 2274.375, 4548.75);
    for (const auto policy : {TimePolicy::classic, TimePolicy::forecast}) {
        limits.time_policy = policy;
        expect_budget(search, white, limits, 4549.375, 18197.5);
    }

    limits = ordinary_limits();
    limits.movestogo = 40;
    expect_budget(search, white, limits, 3799.5, 7599.0);
    limits.movestogo = 1;
    expect_budget(search, white, limits, 119980, 119980);
    limits = ordinary_limits();
    limits.wtime_ms = 0;
    expect_budget(search, white, limits, 0, 0);
    limits.wtime_ms = 21;
    expect_budget(search, white, limits, 1, 1);
    limits.move_overhead_ms = 22;
    expect_budget(search, white, limits, 0, 0);
    limits = ordinary_limits();
    limits.winc_ms = -1000;
    expect_budget(search, white, limits, 3749.375, 7498.75);
    limits.winc_ms = std::numeric_limits<std::int64_t>::max();
    expect_budget(search, white, limits, 119980, 119980);
    limits = ordinary_limits();
    limits.move_overhead_ms = -1;
    expect_budget(search, white, limits, 4550, 9100);

    // Explicit work, movetime and all pondering preserve classic allocation.
    // A supplied clock still intersects explicit work limits; exclusion does
    // not mean permission to ignore that clock.
    for (int exclusion = 0; exclusion < 8; ++exclusion) {
        limits = ordinary_limits();
        switch (exclusion) {
            case 0: limits.depth = 3; break;
            case 1: limits.nodes = 512; break;
            case 2: limits.mate = 2; break;
            case 3: limits.movetime_ms = 100; break;
            case 4: limits.infinite = true; break;
            case 5: limits.ponder = true; break;
            case 6: limits.wtime_ms = -1; break;
            case 7: limits.movetime_ms = 0; break;
        }
        const auto bounded = inspect(search, white, limits);
        limits.time_policy = TimePolicy::classic;
        const auto classic = inspect(search, white, limits);
        require(bounded.soft_ms == classic.soft_ms && bounded.hard_ms == classic.hard_ms,
                "An excluded bounded request must use exactly the classic budget");
    }
}

struct Sample {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

Sample sample(Search& search, Position position, const SearchLimits& limits) {
    search.clear();
    search.reset_stop();
    Sample sample;
    sample.result = search.search(position, {}, limits, [&](const SearchInfo& info) {
        auto replay = position;
        for (const auto move : info.pv) {
            require(legal(replay, move), "Every completed principal variation must be legal");
            replay.make_move(move);
        }
        sample.reports.push_back(info);
    });
    require(legal(position, sample.result.best), "A nonterminal search must return a legal move");
    return sample;
}

void fixed_work_parity(Search& search) {
    auto root = Position::start();
    for (int position_index = 0; position_index < 2; ++position_index) {
        if (position_index) {
            const auto move = parse_uci_move(root, "d2d4");
            require(move.has_value(), "Cannot form fixed-work fixture");
            root.make_move(*move);
        }
        for (const bool node_limited : {false, true}) {
            SearchLimits limits;
            limits.diagnostics = true;
            limits.syzygy_probe_limit = 0;
            limits.depth = node_limited ? 0 : 3;
            limits.nodes = node_limited ? 512 : 0;
            const auto classic = sample(search, root, limits);
            limits.time_policy = TimePolicy::bounded;
            const auto bounded = sample(search, root, limits);
            const auto& a = classic.result;
            const auto& b = bounded.result;
            require(a.best == b.best && a.ponder == b.ponder && a.score == b.score
                    && a.depth == b.depth && a.nodes == b.nodes
                    && classic.reports.size() == bounded.reports.size(),
                    "Bounded selection without clocks cannot alter fixed-work results");
            for (std::size_t i = 0; i < classic.reports.size(); ++i) {
                const auto& x = classic.reports[i];
                const auto& y = bounded.reports[i];
                require(x.depth == y.depth && x.seldepth == y.seldepth && x.score == y.score
                        && x.nodes == y.nodes && x.pv == y.pv,
                        "Every fixed-work iteration must retain its deterministic signature");
            }
        }
    }
}

void expired_receipt_and_lifecycle(Search& search) {
    const auto root = Position::start();
    for (const auto threads : {1, 4}) {
        search.set_threads(threads);
        auto limits = ordinary_limits();
        // Ten seconds exceeds bounded's 9.099 s but not classic's 18.198 s.
        // An old command deterministically exercises the new deadline without
        // spending either interval or introducing a wall-clock racing test.
        limits.received_at = std::chrono::steady_clock::now() - 10s;
        const auto expired = sample(search, root, limits).result;
        require(expired.nodes == 0 && expired.depth == 0
                && expired.diagnostics->stop_reason == StopReason::hard_time
                && expired.diagnostics->hard_ms == 9098.75,
                "Every worker must honor bounded's receipt-based hard deadline");

        limits.received_at.reset();
        search.reset_stop();
        const auto stopped = search.search(root, {}, limits, [&](const SearchInfo& info) {
            if (info.depth == 1) search.stop();
        });
        require(stopped.depth == 1 && legal(root, stopped.best)
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "A bounded leader stop must preserve its completed move and join helpers");
        limits.depth = 1;
        require(sample(search, root, limits).result.depth == 1,
                "Search must remain reusable after deadline and external cancellation");
    }
    search.set_threads(1);
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: bounded-time-test NETWORK");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned network");
        Search search(network, 1);
        allocations_and_exclusions(search);
        fixed_work_parity(search);
        expired_receipt_and_lifecycle(search);
        std::cout << "PASS bounded timing: allocations, exclusions, fixed-work parity, "
                     "receipt accounting and 1/4-worker lifecycle\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL bounded timing: " << error.what() << '\n';
        return 1;
    }
}
