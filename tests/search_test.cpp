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
#include <cstdint>
#include <filesystem>
#include <future>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

using namespace chess0live;
using namespace std::chrono_literals;

/** Keep checks active even if this executable is compiled with NDEBUG. */
void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    auto position = Position::from_fen(text, error);
    if (!position) throw std::runtime_error("Test FEN rejected: " + error);
    return *position;
}

Move move(Position position, std::string_view text) {
    auto parsed = parse_uci_move(position, text);
    if (!parsed) throw std::runtime_error("Test move rejected: " + std::string(text));
    return *parsed;
}

bool legal(Position position, Move candidate) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), candidate) != moves.end();
}

SearchLimits depth_limit(int depth = 2) {
    SearchLimits limits;
    limits.depth = depth;
    return limits;
}

/** The real, pinned network is the only evaluation path in these tests.
 * One search worker and a one-megabyte hash keep correctness checks modest.
 */
struct Fixture {
    nnue::Network network;
    Search search{network, 1};
    bool enable_lmr = false;

    explicit Fixture(const std::filesystem::path& path) {
        std::string error;
        if (!network.load(path, error)) throw std::runtime_error("Network load failed: " + error);
    }

    SearchResult run(Position position, const SearchLimits& limits = depth_limit(),
                     std::vector<std::uint64_t> history = {}, Search::Reporter reporter = {}) {
        search.reset_stop();
        auto request = limits;
        request.late_move_reductions = request.late_move_reductions || enable_lmr;
        return search.search(std::move(position), std::move(history), request, std::move(reporter));
    }
};

void terminal_positions(Fixture& fixture) {
    // Checkmate wins even though the halfmove clock has reached the draw limit.
    auto position = fen("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51");
    auto result = fixture.run(position);
    require(!result.best.valid(), "A checkmated root must not return a move");
    require(result.score == -Search::mate_score, "Checkmate must take precedence over rule 50");

    position = fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1");
    result = fixture.run(position);
    require(!result.best.valid() && result.score == 0, "Stalemate must be a terminal draw");

    position = fen("7k/8/5K2/8/8/8/8/8 w - - 0 1");
    result = fixture.run(position);
    require(legal(position, result.best) && result.score == 0 && result.nodes == 0,
            "Dead material must be recognized before searching");

    position = fen("7k/8/5KQ1/8/8/8/8/8 w - - 100 51");
    result = fixture.run(position);
    require(legal(position, result.best) && result.score == 0 && result.nodes == 0,
            "An already claimable rule-50 draw must score zero");
}

void mate_at_draw_boundary(Fixture& fixture) {
    auto position = fen("7k/8/5KQ1/8/8/8/8/8 w - - 99 51");
    const auto result = fixture.run(position);
    require(result.score == Search::mate_score - 1, "Mate in one must retain its ply distance");
    require(legal(position, result.best), "Reported mating move must be legal");
    position.make_move(result.best);
    require(position.halfmove_clock() == 100, "Mating test must reach the rule-50 boundary");
    require(position.legal_moves().empty() && position.in_check(position.turn()),
            "Reported mating move must actually give checkmate");
}

void quiescence_terminals_and_evasions(Fixture& fixture) {
    // At depth one, the forced reply is entirely inside quiescence. Quiet king
    // evasions must be searched: a capture-only generator or stand-pat in check
    // would omit this unique legal reply from the principal variation.
    auto position = fen("6k1/5pp1/8/8/8/8/5PPP/4R1K1 w - - 0 1");
    auto limits = depth_limit(1);
    limits.searchmoves = {move(position, "e1e8")};
    auto result = fixture.run(position, limits);
    require(result.best == limits.searchmoves.front(), "The requested checking move must be selected");
    position.make_move(result.best);
    const auto evasions = position.legal_moves();
    require(position.in_check(position.turn()) && evasions.size() == 1,
            "Quiescence fixture must have exactly one evasion");
    require(result.ponder == evasions.front() && !result.ponder.is_capture(),
            "Quiescence must search the unique quiet check evasion");

    // This non-capturing queen move stalemates the opponent at the horizon.
    position = fen("7k/5K2/8/6Q1/8/8/8/8 w - - 0 1");
    limits.searchmoves = {move(position, "g5g6")};
    result = fixture.run(position, limits);
    require(result.score == 0, "Horizon stalemate must override neural stand-pat");
    position.make_move(result.best);
    require(position.legal_moves().empty() && !position.in_check(position.turn()),
            "Horizon stalemate fixture must really be stalemate");
}

void repetition_history(Fixture& fixture) {
    auto position = Position::start();
    std::vector<std::uint64_t> history{position.key()};
    constexpr std::string_view cycle[] = {"g1f3", "g8f6", "f3g1", "f6g8"};
    for (const auto text : cycle) {
        position.make_move(move(position, text));
        history.push_back(position.key());
    }
    auto result = fixture.run(position, depth_limit(), history);
    require(result.nodes > 0, "Two occurrences must not be mistaken for a threefold draw");

    for (const auto text : cycle) {
        position.make_move(move(position, text));
        history.push_back(position.key());
    }
    result = fixture.run(position, depth_limit(), history);
    require(result.score == 0 && result.nodes == 0 && legal(position, result.best),
            "The third occurrence must be recognized from supplied game history");

    history.pop_back(); // API also accepts history that stops immediately before the root.
    result = fixture.run(position, depth_limit(), history);
    require(result.score == 0 && result.nodes == 0, "Missing final root key must be appended");

    // A FEN does not invent earlier positions, despite a nonzero halfmove clock.
    result = fixture.run(position);
    require(result.nodes > 0, "No repetition may be invented without game history");

    position = Position::start();
    result = fixture.run(position, depth_limit(), {position.key(), position.key(), position.key()});
    require(result.nodes > 0, "Irreversible clock reset must exclude preceding repetition keys");
}

void move_restrictions_and_table_bounds(Fixture& fixture) {
    auto position = Position::start();
    auto limits = depth_limit();
    limits.searchmoves = {move(position, "a2a3")};
    auto result = fixture.run(position, limits);
    require(result.best == limits.searchmoves.front(), "Search must honor the root move restriction");

    // A restricted root is not proof of a bound for the full move set. First
    // search a drawing move, then reuse that table while allowing a mating move.
    position = fen("7k/8/5KQ1/8/8/8/8/8 w - - 99 51");
    limits.searchmoves = {move(position, "f6e6")};
    result = fixture.run(position, limits);
    require(result.score == 0, "Restricted boundary move must draw");
    limits.searchmoves.clear();
    result = fixture.run(position, limits);
    require(result.score == Search::mate_score - 1,
            "A restricted search must not poison unrestricted table bounds");
}

void limits_and_principal_variations(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = depth_limit();
    fixture.search.clear();
    int reports = 0;
    const auto reporter = [&](const SearchInfo& info) {
        require(info.depth == ++reports, "Completed depths must be reported in order");
        require(info.seldepth >= info.depth, "Selective depth must cover the completed depth");
        require(!info.pv.empty(), "A nonterminal completed search must report a principal variation");
        auto replay = position;
        for (const auto candidate : info.pv) {
            require(legal(replay, candidate), "Every reported PV move must be legal in sequence");
            replay.make_move(candidate);
        }
    };
    const auto first = fixture.run(position, limits, {}, reporter);
    require(reports == 2 && first.depth == 2 && legal(position, first.best),
            "Depth limit must complete exactly the requested iterations");

    fixture.search.clear();
    const auto second = fixture.run(position, limits);
    require(first.best == second.best && first.score == second.score && first.nodes == second.nodes,
            "Fresh single-worker bounded searches must be deterministic");

    limits = {};
    limits.nodes = 50;
    auto result = fixture.run(position, limits);
    require(legal(position, result.best) && result.nodes <= limits.nodes,
            "A hard node limit must preserve a legal move without overshooting");

    limits.nodes = 1;
    result = fixture.run(position, limits);
    require(legal(position, result.best) && result.nodes == 1,
            "One-node search must retain a legal fallback");

    limits = depth_limit(1);
    limits.infinite = true;
    limits.movetime_ms = 0;
    result = fixture.run(position, limits);
    require(result.depth == 1, "Infinite mode must ignore clock limits while honoring explicit depth");
}

void cancellation_and_pondering(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = depth_limit();
    limits.late_move_reductions = fixture.enable_lmr;
    fixture.search.reset_stop();
    fixture.search.stop();
    auto result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best) && result.lmr.enabled == fixture.enable_lmr,
            "A stop published before worker startup must not be lost");

    // No wall-clock racing is needed: the first completed iteration signals that
    // the worker has entered search, then cancellation is sent from this thread.
    fixture.search.reset_stop();
    limits = {};
    limits.late_move_reductions = fixture.enable_lmr;
    limits.infinite = true;
    std::promise<void> iteration_started;
    auto started = iteration_started.get_future();
    auto pending = std::async(std::launch::async, [&] {
        bool signaled = false;
        return fixture.search.search(position, {}, limits, [&](const SearchInfo&) {
            if (!signaled) { iteration_started.set_value(); signaled = true; }
        });
    });
    const auto status = started.wait_for(5s);
    fixture.search.stop();
    result = pending.get();
    require(status == std::future_status::ready && legal(position, result.best)
            && result.lmr.enabled == fixture.enable_lmr,
            "Concurrent stop must preserve a completed iteration's legal result");

    // A hit can arrive before the search thread starts, just like immediate stop.
    limits = {};
    limits.late_move_reductions = fixture.enable_lmr;
    limits.ponder = true;
    limits.movetime_ms = 0;
    fixture.search.reset_stop();
    fixture.search.ponderhit();
    result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best) && result.lmr.enabled == fixture.enable_lmr,
            "Ponderhit before worker startup must activate the exhausted clock");

    // Clearing that hit for a new ponder must suspend even a zero-millisecond
    // clock. The UCI layer separately holds the completed depth-limited result.
    limits.depth = 1;
    result = fixture.run(position, limits);
    require(result.depth == 1 && result.lmr.enabled == fixture.enable_lmr,
            "Ponder clock must remain inactive before its own ponderhit");
}

void clock_limit(Fixture& fixture) {
    SearchLimits limits;
    limits.movetime_ms = 30;
    limits.move_overhead_ms = 0;
    const auto position = Position::start();
    const auto before = std::chrono::steady_clock::now();
    const auto result = fixture.run(position, limits);
    const auto elapsed = std::chrono::steady_clock::now() - before;
    require(legal(position, result.best), "Timed search must retain a legal move");
    // Deliberately generous for sanitizers and busy machines: this is a broken
    // deadline regression check, not a throughput or scheduler-jitter benchmark.
    require(elapsed < 2s, "A short movetime search must not ignore its hard deadline");

    limits.movetime_ms = -1;
    limits.wtime_ms = 0;
    const auto exhausted = fixture.run(position, limits);
    require(exhausted.nodes == 0 && legal(position, exhausted.best),
            "A zero remaining clock must stop immediately with a legal fallback");
}

void root_diagnostics(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = depth_limit(2);
    fixture.search.clear();
    const auto plain = fixture.run(position, limits);
    require(!plain.diagnostics, "Diagnostics must not be allocated by default");
    fixture.search.clear();
    limits.diagnostics = true;
    std::vector<SearchInfo> reports;
    const auto traced = fixture.run(position, limits, {}, [&](const SearchInfo& info) { reports.push_back(info); });
    require(traced.best == plain.best && traced.score == plain.score && traced.nodes == plain.nodes,
            "Root tracing cannot change a fixed-depth search tree or returned move");
    require(traced.diagnostics && traced.diagnostics->stop_reason == StopReason::depth_limit,
            "Fixed-depth trace must identify its stop reason");
    const auto& trace = *traced.diagnostics;
    require(trace.iterations.size() == 2 && reports.size() == 2, "Every completed iteration must be measured");
    std::uint64_t nodes = 0;
    double duration = 0;
    for (std::size_t i = 0; i < trace.iterations.size(); ++i) {
        const auto& iteration = trace.iterations[i];
        nodes += iteration.nodes;
        duration += iteration.duration_ms;
        require(iteration.completed && iteration.depth == int(i) + 1 && iteration.duration_ms >= 0,
                "Completed trace depth and duration must be valid");
        require(nodes == reports[i].nodes, "Iteration deltas must reconcile with cumulative UCI node counts");
        require(iteration.elapsed_ms >= duration, "Elapsed time must include all measured iteration costs");
    }
    require(nodes == traced.nodes && trace.elapsed_ms >= trace.iterations.back().elapsed_ms,
            "Summary must include every node and completed iteration time");

    // A deterministic node cap allows one completed depth and then interrupts
    // the next iteration. Record those discarded nodes without changing bestmove.
    fixture.search.clear();
    limits.depth = 0;
    limits.nodes = trace.iterations.front().nodes + 1;
    const auto interrupted = fixture.run(position, limits);
    const auto& partial = *interrupted.diagnostics;
    require(partial.stop_reason == StopReason::node_limit && interrupted.nodes == limits.nodes,
            "Node-limited trace must account for the exact interrupted work");
    require(interrupted.depth == 1 && interrupted.best == reports.front().pv.front(),
            "Aborted depth must preserve the last completed result");
    require(partial.iterations.size() == 2 && partial.iterations.front().completed
            && !partial.iterations.back().completed && partial.iterations.back().nodes == 1,
            "The one interrupted attempt must appear as the final iteration");
    require(partial.iterations.front().nodes + partial.iterations.back().nodes == interrupted.nodes,
            "Completed and discarded work must sum to the final node total");

    limits = depth_limit();
    limits.diagnostics = true;
    const auto mate = fixture.run(fen("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51"), limits);
    require(mate.diagnostics->stop_reason == StopReason::terminal
            && mate.diagnostics->iterations.empty() && mate.nodes == 0 && mate.depth == 0,
            "A terminal root must not invent an iteration");
    const auto draw = fixture.run(fen("7k/8/5K2/8/8/8/8/8 w - - 0 1"), limits);
    require(draw.diagnostics->stop_reason == StopReason::draw && draw.diagnostics->iterations.empty(),
            "A drawn root must report its reason without invented search work");
}

void forecast_scope_and_clock_budgets(Fixture& fixture) {
    const auto position = Position::start();
    SearchLimits base;
    base.time_policy = TimePolicy::forecast;
    base.diagnostics = true;
    base.wtime_ms = 5000;
    base.btime_ms = 10000;
    base.winc_ms = 2000;
    base.binc_ms = 4000;
    // Stop before entering the search tree to inspect policy selection and
    // clock allocation deterministically, without sleeping or doing long work.
    const auto inspect = [&](Position root, const SearchLimits& limits) {
        fixture.search.reset_stop();
        fixture.search.stop();
        return fixture.search.search(root, {}, limits);
    };
    auto result = inspect(position, base);
    require(result.diagnostics->forecast_active && result.diagnostics->policy == TimePolicy::forecast
            && result.diagnostics->stop_reason == StopReason::external_stop,
            "Only an ordinary clock-managed forecast request enables prediction");
    require(result.nodes == 0 && result.diagnostics->iterations.empty(), "Prepublished stop must do no search work");
    const auto white_soft = result.diagnostics->soft_ms;
    auto black = position;
    black.make_move(move(black, "e2e4"));
    const auto black_result = inspect(black, base);
    require(black_result.diagnostics->soft_ms > white_soft, "Use the moving side's clock and increment");
    require(result.diagnostics->hard_ms <= 4980 && black_result.diagnostics->hard_ms <= 9980,
            "Neither side can spend its next increment before completing a move");

    for (int exclusion = 0; exclusion < 8; ++exclusion) {
        auto limits = base;
        switch (exclusion) {
            case 0: limits.movetime_ms = 100; break;
            case 1: limits.depth = 2; break;
            case 2: limits.nodes = 100; break;
            case 3: limits.mate = 2; break;
            case 4: limits.infinite = true; break;
            case 5: limits.ponder = true; break;
            case 6: limits.wtime_ms = -1; break;
            case 7: limits.time_policy = TimePolicy::classic; break;
        }
        require(!inspect(position, limits).diagnostics->forecast_active,
                "Explicit limits, ponder, absent moving-side clock, and classic policy exclude forecasting");
    }

    auto exhausted = base;
    exhausted.wtime_ms = 0;
    result = fixture.run(position, exhausted);
    require(result.diagnostics->stop_reason == StopReason::hard_time && result.nodes == 0
            && legal(position, result.best) && result.diagnostics->hard_ms == 0,
            "Forecast cannot spend increment on an exhausted current clock");
    auto tiny = base;
    tiny.wtime_ms = 21;
    require(inspect(position, tiny).diagnostics->hard_ms == 1,
            "A large increment cannot raise the deadline above the remaining spendable millisecond");
}

void selective_search_verification_and_policy_switches(Fixture& fixture) {
    // This ordinary, independently specified six-ply QGD position exercises
    // both accepted and rejected reduced scout challenges. It is a code-path
    // regression case, not a tactical benchmark or held-out strength sample.
    auto position = Position::start();
    std::vector<std::uint64_t> history{position.key()};
    for (const auto text : {"d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6"}) {
        position.make_move(move(position, text));
        history.push_back(position.key());
    }
    const auto original_fen = position.fen();
    const auto original_key = position.key();
    fixture.search.clear();
    const auto baseline = fixture.run(position, depth_limit(3), history);
    require(!baseline.lmr.enabled && baseline.lmr.reductions == 0 && baseline.lmr.researches == 0,
            "The default search must not perform selective reductions");

    auto limits = depth_limit(6);
    limits.nodes = 100000;
    limits.late_move_reductions = true;
    limits.diagnostics = true;
    std::vector<SearchInfo> reports;
    const auto candidate = fixture.run(position, limits, history, [&](const SearchInfo& info) {
        auto replay = position;
        for (const auto pv_move : info.pv) {
            require(legal(replay, pv_move), "Selective re-searches must preserve legal principal variations");
            replay.make_move(pv_move);
        }
        reports.push_back(info);
    });
    require(candidate.lmr.enabled && candidate.lmr.reductions > 0 && candidate.lmr.researches > 0,
            "The regression must exercise reduced and ordinary-depth verification searches");
    require(candidate.lmr.fail_lows > 0 && candidate.lmr.verified_cutoffs > 0,
            "Reduced fail-highs must be both rejected and confirmed by ordinary-depth verification");
    require(candidate.lmr.researches <= candidate.lmr.reductions
            && candidate.lmr.fail_lows + candidate.lmr.verified_cutoffs <= candidate.lmr.researches,
            "Completed verification outcomes cannot exceed the attempted searches");
    require(candidate.nodes <= limits.nodes && legal(position, candidate.best)
            && !reports.empty() && candidate.best == reports.back().pv.front(),
            "An interrupted selective search retains its last completed legal result");
    require(candidate.diagnostics->stop_reason == StopReason::node_limit
            && !candidate.diagnostics->iterations.back().completed,
            "The bounded regression must include an interrupted iteration");
    require(position.fen() == original_fen && position.key() == original_key,
            "Searching cannot mutate the caller's position");

    // No explicit clear here: the public Search API, not just UCI, must isolate
    // selective TT bounds and learned ordering from unreduced baseline searches.
    const auto switched = fixture.run(position, depth_limit(3), history);
    require(switched.best == baseline.best && switched.score == baseline.score
            && switched.nodes == baseline.nodes && !switched.lmr.enabled,
            "Returning from a warm selective search must reproduce a fresh baseline");
    require(switched.lmr.reductions == 0 && switched.lmr.researches == 0
            && switched.lmr.fail_lows == 0 && switched.lmr.verified_cutoffs == 0,
            "Selective counters reset for every search");

    fixture.search.reset_stop();
    fixture.search.stop();
    const auto stopped = fixture.search.search(position, history, limits);
    require(stopped.nodes == 0 && stopped.lmr.enabled && stopped.lmr.reductions == 0
            && stopped.diagnostics->stop_reason == StopReason::external_stop,
            "Clearing policy state must preserve a stop published before startup");

    // A stop sent from an iteration callback is deterministic and does not rely
    // on a scheduling race. The next iteration must never start after it.
    fixture.search.clear();
    limits = depth_limit(6);
    limits.late_move_reductions = true;
    limits.diagnostics = true;
    const auto cancelled = fixture.run(Position::start(), limits, {}, [&](const SearchInfo& info) {
        if (info.depth == 5) fixture.search.stop();
    });
    require(cancelled.depth == 5 && cancelled.lmr.reductions > 0
            && cancelled.diagnostics->stop_reason == StopReason::external_stop,
            "External cancellation must remain effective after selective search work");
}

void selective_special_positions(Fixture& fixture) {
    auto limits = depth_limit(3);
    limits.late_move_reductions = true;
    auto position = fen("k7/8/1QK5/8/8/8/8/8 w - - 0 1");
    auto result = fixture.run(position, limits);
    require(result.best == move(position, "b6b7") && result.score == Search::mate_score - 1,
            "Selective mode must retain the unique quiet mate in one");
    position = fen("R5k1/6p1/4K3/8/8/8/8/8 b - - 0 1");
    result = fixture.run(position, limits);
    require(result.best == move(position, "g8h7"), "Selective mode must preserve the sole quiet check evasion");
    position = fen("8/k1P5/2K5/8/8/8/8/8 w - - 0 1");
    limits.searchmoves = {move(position, "c7c8q")};
    result = fixture.run(position, limits);
    require(result.best == limits.searchmoves.front() && result.score == 0,
            "A restricted queen promotion that stalemates must remain a draw");
    position = fen("8/2k5/8/2K5/2P5/8/8/8 w - - 99 1");
    limits.searchmoves = {move(position, "c5d5")};
    result = fixture.run(position, limits);
    require(result.score == 0, "A quiet move reaching rule 50 must remain a draw in selective mode");
}

void missing_network() {
    nnue::Network empty_network;
    Search search(empty_network, 1);
    bool rejected = false;
    try { (void)search.search(Position::start(), {}, depth_limit(1)); }
    catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "Search must not silently substitute evaluation for a missing NNUE network");
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "Usage: search-test /path/to/compatible-network.nnue\n";
        return 2;
    }
    try {
        missing_network();
        Fixture fixture{std::filesystem::path(argv[1])};
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        move_restrictions_and_table_bounds(fixture);
        limits_and_principal_variations(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
        root_diagnostics(fixture);
        forecast_scope_and_clock_budgets(fixture);
        selective_search_verification_and_policy_switches(fixture);
        selective_special_positions(fixture);
        // Re-run the existing chess-rule cases with the experimental option on.
        // Their exact expectations remain mandatory despite selective search.
        fixture.search.clear();
        fixture.enable_lmr = true;
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        move_restrictions_and_table_bounds(fixture);
        limits_and_principal_variations(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
        std::cout << "Search correctness checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Search test failed: " << error.what() << '\n';
        return 1;
    }
}
