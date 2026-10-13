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

    explicit Fixture(const std::filesystem::path& path) {
        std::string error;
        if (!network.load(path, error)) throw std::runtime_error("Network load failed: " + error);
    }

    SearchResult run(Position position, const SearchLimits& limits = depth_limit(),
                     std::vector<std::uint64_t> history = {}, Search::Reporter reporter = {}) {
        search.reset_stop();
        return search.search(std::move(position), std::move(history), limits, std::move(reporter));
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
    fixture.search.reset_stop();
    fixture.search.stop();
    auto result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best),
            "A stop published before worker startup must not be lost");

    // No wall-clock racing is needed: the first completed iteration signals that
    // the worker has entered search, then cancellation is sent from this thread.
    fixture.search.reset_stop();
    limits = {};
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
    require(status == std::future_status::ready && legal(position, result.best),
            "Concurrent stop must preserve a completed iteration's legal result");

    // A hit can arrive before the search thread starts, just like immediate stop.
    limits = {};
    limits.ponder = true;
    limits.movetime_ms = 0;
    fixture.search.reset_stop();
    fixture.search.ponderhit();
    result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best),
            "Ponderhit before worker startup must activate the exhausted clock");

    // Clearing that hit for a new ponder must suspend even a zero-millisecond
    // clock. The UCI layer separately holds the completed depth-limited result.
    limits.depth = 1;
    result = fixture.run(position, limits);
    require(result.depth == 1, "Ponder clock must remain inactive before its own ponderhit");
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
        std::cout << "Search correctness checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Search test failed: " << error.what() << '\n';
        return 1;
    }
}
