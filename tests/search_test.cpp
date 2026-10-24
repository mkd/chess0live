/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/detail/transposition_entry.hpp"
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"
#include "chess0live/search.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <future>
#include <iostream>
#include <limits>
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

/** Keep historical baseline and isolated-policy cases independent of defaults. */
SearchLimits baseline_limits() {
    SearchLimits limits;
    limits.late_move_reductions = false;
    return limits;
}

SearchLimits depth_limit(int depth = 2) {
    auto limits = baseline_limits();
    limits.depth = depth;
    return limits;
}

/** Test value round trips independently of search, including each generated
 * special-move flag combination. A lost flag can silently break TT move
 * ordering because Move equality compares all fields, not just its squares.
 */
void transposition_entry_round_trips() {
    using namespace detail::transposition;
    constexpr Entry empty;
    static_assert(empty.bound() == Bound::empty && empty.move() == Move{});
    static_assert(sizeof(Entry) == 16 && sizeof(Bucket) == 64 && alignof(Bucket) == 64);
    static_assert(Search::max_ply - 2 <= std::numeric_limits<std::uint8_t>::max());
    constexpr std::uint64_t key = 0xfedcba9876543210ULL;
    for (unsigned from = 0; from <= 64; ++from) {
        for (unsigned to = 0; to <= 64; ++to) {
            for (unsigned promotion = 0; promotion <= static_cast<unsigned>(PieceType::king); ++promotion) {
                for (unsigned flags = 0; flags < 16; ++flags) {
                    const Move original{static_cast<std::uint8_t>(from), static_cast<std::uint8_t>(to),
                                        static_cast<PieceType>(promotion), static_cast<std::uint8_t>(flags)};
                    for (const auto bound : {Bound::empty, Bound::exact, Bound::lower, Bound::upper}) {
                        const Entry entry{key, original, -31000, Search::max_ply - 2, bound, 255};
                        require(entry.key == key && entry.move() == original && entry.score == -31000
                                && entry.depth == Search::max_ply - 2 && entry.bound() == bound
                                && entry.generation == 255,
                                "Packed entries must preserve every legal move field and bound independently");
                    }
                }
            }
        }
    }

    // The packed square/promotion fields retain the complete original bytes,
    // not just their ordinary chess-domain values or the invalid64 sentinel.
    const Move bytes{255, 254, static_cast<PieceType>(253), 15};
    require(Entry{key, bytes, -1, 0, Bound::upper, 0}.move() == bytes,
            "Packing must not truncate full square and promotion bytes");
    for (const auto full_key : {std::uint64_t{0}, std::uint64_t{1}, std::uint64_t{1} << 63,
                               std::numeric_limits<std::uint64_t>::max()}) {
        for (const auto score : {std::numeric_limits<std::int16_t>::min(), std::int16_t{-31000},
                                std::int16_t{-1}, std::int16_t{0}, std::int16_t{1},
                                std::int16_t{31000}, std::numeric_limits<std::int16_t>::max()}) {
            for (unsigned value = 0; value < 256; ++value) {
                const auto byte = static_cast<std::uint8_t>(value);
                Entry entry{full_key, Move{}, score, byte, Bound::exact, byte};
                require(entry.key == full_key && entry.move() == Move{} && entry.score == score
                        && entry.depth == byte && entry.bound() == Bound::exact && entry.generation == byte,
                        "Keys, signed scores, and complete depth/generation bytes must round-trip");
                ++entry.generation;
                require(entry.generation == static_cast<std::uint8_t>(value + 1)
                        && entry.key == full_key && entry.move() == Move{} && entry.score == score
                        && entry.depth == byte && entry.bound() == Bound::exact,
                        "Generation refresh and 255-to-zero wrap cannot corrupt other fields");
            }
        }
    }
    const std::vector<Bucket> buckets(3);
    for (const auto& bucket : buckets) {
        require(reinterpret_cast<std::uintptr_t>(&bucket) % 64 == 0,
                "Dynamically allocated buckets must retain their requested 64-byte alignment");
        for (const auto& entry : bucket.entries)
            require(entry.bound() == Bound::empty && !entry.move().valid() && entry.key == 0,
                    "Default table allocation must contain empty entries with invalid moves");
    }
}

/** The real, pinned network is the only evaluation path in these tests.
 * One search worker and a one-megabyte hash keep correctness checks modest.
 */
struct Fixture {
    nnue::Network network;
    Search search{network, 1};
    bool enable_lmr = false;
    CaptureOrdering capture_ordering = CaptureOrdering::mvv_lva;
    bool enable_countermove = false;

    explicit Fixture(const std::filesystem::path& path) {
        std::string error;
        if (!network.load(path, error)) throw std::runtime_error("Network load failed: " + error);
    }

    SearchResult run(Position position, const SearchLimits& limits = depth_limit(),
                     std::vector<std::uint64_t> history = {}, Search::Reporter reporter = {}) {
        search.reset_stop();
        auto request = limits;
        request.late_move_reductions = request.late_move_reductions || enable_lmr;
        if (capture_ordering == CaptureOrdering::see) request.capture_ordering = capture_ordering;
        request.countermove_ordering = request.countermove_ordering || enable_countermove;
        return search.search(std::move(position), std::move(history), request, std::move(reporter));
    }
};

/** Exercise the public API default directly, bypassing Fixture's mode override. */
void default_selective_search(Fixture& fixture) {
    SearchLimits limits;
    limits.depth = 5;
    limits.nodes = 20000;
    const auto position = Position::start();
    const auto run = [&](std::vector<SearchInfo>& reports) {
        fixture.search.clear();
        fixture.search.reset_stop();
        return fixture.search.search(position, {}, limits, [&](const SearchInfo& info) {
            auto replay = position;
            for (const auto candidate : info.pv) {
                require(legal(replay, candidate), "Default LMR must report legal principal variations");
                replay.make_move(candidate);
            }
            reports.push_back(info);
        });
    };
    std::vector<SearchInfo> default_reports;
    const auto implicit = run(default_reports);
    require(implicit.lmr.enabled && implicit.lmr.reductions > 0
            && implicit.nodes <= limits.nodes && legal(position, implicit.best),
            "An untouched API LMR setting must enable bounded selective search");

    limits.late_move_reductions = true;
    std::vector<SearchInfo> explicit_reports;
    const auto explicit_on = run(explicit_reports);
    require(implicit.best == explicit_on.best && implicit.ponder == explicit_on.ponder
            && implicit.score == explicit_on.score && implicit.depth == explicit_on.depth
            && implicit.nodes == explicit_on.nodes && default_reports.size() == explicit_reports.size(),
            "Default LMR must match the explicit-on single-worker search");
    for (std::size_t i = 0; i < default_reports.size(); ++i) {
        const auto& actual = default_reports[i];
        const auto& expected = explicit_reports[i];
        require(actual.depth == expected.depth && actual.seldepth == expected.seldepth
                && actual.score == expected.score && actual.nodes == expected.nodes
                && actual.pv == expected.pv,
                "Default and explicit-on iterations must have identical search signatures");
    }
    fixture.search.clear();
}

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

    // An empty tactical list can also mean ordinary quiet play. Use a material
    // imbalance so incorrectly returning a stalemate score cannot pass by
    // coincidence; a fresh evaluator supplies the independent stand-pat value.
    position = fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1");
    limits.searchmoves = {move(position, "d1a1")};
    auto child = position;
    child.make_move(limits.searchmoves.front());
    const auto quiet_replies = child.legal_moves();
    require(!child.in_check(child.turn()) && !quiet_replies.empty()
            && std::all_of(quiet_replies.begin(), quiet_replies.end(), [](Move reply) {
                return !reply.is_capture() && reply.promotion == PieceType::none;
            }), "Quiet-only horizon fixture must have legal mobility without tacticals");
    nnue::Evaluator evaluator(fixture.network);
    const int expected = -evaluator.evaluate(child);
    require(expected != 0, "Quiet-only horizon fixture must have a nonzero stand-pat value");
    fixture.search.clear();
    result = fixture.run(position, limits);
    require(result.best == limits.searchmoves.front() && result.score == expected,
            "Quiet-only horizon mobility must preserve stand-pat rather than score stalemate");

    // At depth one the checked root's forced king move reaches an unchecked
    // quiescence leaf. A non-capturing promotion then gives mate. Both colors
    // must retain that promotion even though ordinary quiet moves are omitted.
    struct PromotionMate { std::string_view fen; std::string_view root; std::string_view mate; };
    constexpr PromotionMate promotion_mates[] = {
        {"7k/5KP1/8/6P1/8/8/8/8 b - - 0 1", "h8h7", "g7g8q"},
        {"8/8/8/8/6p1/8/5kp1/7K w - - 0 1", "h1h2", "g2g1q"},
    };
    for (const auto& item : promotion_mates) {
        position = fen(item.fen);
        limits.searchmoves = {move(position, item.root)};
        child = position;
        child.make_move(limits.searchmoves.front());
        const auto promotion = move(child, item.mate);
        require(!child.in_check(child.turn()) && !promotion.is_capture()
                && promotion.promotion == PieceType::queen,
                "Promotion-mate fixture must reach an unchecked leaf with a quiet promotion");
        child.make_move(promotion);
        require(child.in_check(child.turn()) && child.legal_moves().empty(),
                "Quiet promotion fixture must really give checkmate");
        fixture.search.clear();
        result = fixture.run(position, limits);
        require(result.best == limits.searchmoves.front() && result.ponder == promotion
                && result.score == -Search::mate_score + 2,
                "Quiescence must search a quiet promotion mate with the correct ply distance");
    }
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

    limits = baseline_limits();
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
    limits.capture_ordering = fixture.capture_ordering;
    limits.countermove_ordering = fixture.enable_countermove;
    fixture.search.reset_stop();
    fixture.search.stop();
    auto result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best) && result.lmr.enabled == fixture.enable_lmr
            && result.ordering.policy == fixture.capture_ordering
            && result.countermove.enabled == fixture.enable_countermove,
            "A stop published before worker startup must not be lost");

    // No wall-clock racing is needed: the first completed iteration signals that
    // the worker has entered search, then cancellation is sent from this thread.
    fixture.search.reset_stop();
    limits = baseline_limits();
    limits.late_move_reductions = fixture.enable_lmr;
    limits.capture_ordering = fixture.capture_ordering;
    limits.countermove_ordering = fixture.enable_countermove;
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
            && result.lmr.enabled == fixture.enable_lmr && result.ordering.policy == fixture.capture_ordering
            && result.countermove.enabled == fixture.enable_countermove,
            "Concurrent stop must preserve a completed iteration's legal result");

    // A hit can arrive before the search thread starts, just like immediate stop.
    limits = baseline_limits();
    limits.late_move_reductions = fixture.enable_lmr;
    limits.capture_ordering = fixture.capture_ordering;
    limits.countermove_ordering = fixture.enable_countermove;
    limits.ponder = true;
    limits.movetime_ms = 0;
    fixture.search.reset_stop();
    fixture.search.ponderhit();
    result = fixture.search.search(position, {}, limits);
    require(result.nodes == 0 && legal(position, result.best) && result.lmr.enabled == fixture.enable_lmr
            && result.ordering.policy == fixture.capture_ordering
            && result.countermove.enabled == fixture.enable_countermove,
            "Ponderhit before worker startup must activate the exhausted clock");

    // Clearing that hit for a new ponder must suspend even a zero-millisecond
    // clock. The UCI layer separately holds the completed depth-limited result.
    limits.depth = 1;
    result = fixture.run(position, limits);
    require(result.depth == 1 && result.lmr.enabled == fixture.enable_lmr
            && result.ordering.policy == fixture.capture_ordering
            && result.countermove.enabled == fixture.enable_countermove,
            "Ponder clock must remain inactive before its own ponderhit");
}

void clock_limit(Fixture& fixture) {
    auto limits = baseline_limits();
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

/** An old receipt deterministically models delayed dispatch without sleeping
 * or relying on the host scheduler to pause a particular worker. */
void command_time_accounting(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = baseline_limits();
    limits.received_at = std::chrono::steady_clock::now() - 2s;
    limits.movetime_ms = 620;
    limits.diagnostics = true;
    auto result = fixture.run(position, limits);
    require(result.nodes == 0 && result.depth == 0 && legal(position, result.best)
            && result.diagnostics->stop_reason == StopReason::hard_time
            && result.diagnostics->elapsed_ms >= 2000
            && result.diagnostics->hard_ms == 600,
            "Worker dispatch must not restart an expired positive movetime budget");
    limits.received_at = std::chrono::steady_clock::time_point::min();
    result = fixture.run(position, limits);
    require(result.nodes == 0 && result.diagnostics->elapsed_ms >= 2000,
            "Extreme past API origins must expire safely without signed overflow");
    limits.received_at = std::chrono::steady_clock::now() - 2s;

    limits.movetime_ms = -1;
    limits.wtime_ms = limits.btime_ms = 620;
    limits.winc_ms = limits.binc_ms = 600;
    auto black = position;
    black.make_move(move(black, "e2e4"));
    for (const auto& root : {position, black}) {
        result = fixture.run(root, limits);
        require(result.nodes == 0 && legal(root, result.best)
                && result.diagnostics->stop_reason == StopReason::hard_time,
                "Both sides' chess clocks must include command preparation");
    }

    // Explicit finite depth/nodes intersect with a supplied clock; they cannot
    // authorize tree work after that clock's deadline has already passed.
    limits.depth = 1;
    limits.nodes = 10;
    result = fixture.run(position, limits);
    require(result.nodes == 0, "Explicit search bounds do not erase an expired clock");

    limits.nodes = 0;
    limits.infinite = true;
    result = fixture.run(position, limits);
    require(result.depth == 1, "Infinite search ignores an old command timestamp's clock budget");
    limits.infinite = false;
    limits.ponder = true;
    result = fixture.run(position, limits);
    require(result.depth == 1, "Pondering cannot charge time before ponderhit");
    // A fresh hit, even after an old receipt, starts a fresh charged interval.
    fixture.search.reset_stop();
    fixture.search.ponderhit();
    limits.late_move_reductions = fixture.enable_lmr;
    limits.capture_ordering = fixture.capture_ordering;
    limits.countermove_ordering = fixture.enable_countermove;
    result = fixture.search.search(position, {}, limits);
    require(result.depth == 1, "Ponderhit uses its own origin rather than command receipt");

    limits = depth_limit(2);
    fixture.search.clear();
    const auto normal = fixture.run(position, limits);
    fixture.search.clear();
    limits.received_at = std::chrono::steady_clock::now() - 2s;
    const auto old = fixture.run(position, limits);
    require(normal.best == old.best && normal.score == old.score && normal.nodes == old.nodes,
            "Without a clock, command age cannot change fixed-depth search work");

    limits.diagnostics = true;
    limits.received_at = std::chrono::steady_clock::now() + 2s;
    result = fixture.run(position, limits);
    require(result.diagnostics->elapsed_ms >= 0,
            "A future API timestamp must not produce negative elapsed time");
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

/** Exercise public search behavior with exact one-node/table expectations.
 * These checks distinguish a full-key hit, a usable bound, and an attempted
 * store, rather than treating all table traffic as an unspecified hit rate.
 */
void cache_accounting_and_lifecycle(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = depth_limit(1);
    limits.diagnostics = true;
    fixture.search.set_hash(1);
    fixture.search.clear();
    const auto cold = fixture.run(position, limits);
    const auto geometry = cold.diagnostics->cache;
    require(geometry.probes == 1 && geometry.hits == 0 && geometry.cutoffs == 0
            && geometry.stores == 1 && geometry.replacements == 0,
            "A fresh depth-one search probes and fills only the root entry");
    require(geometry.entry_bytes == 16 && geometry.bucket_bytes == 64
            && geometry.buckets == 8192 && geometry.capacity == 32768
            && geometry.allocated_bytes >= geometry.buckets * geometry.bucket_bytes
            && geometry.allocated_bytes <= 1024 * 1024,
            "Cache geometry must describe the actual bounded allocation");

    const auto warm = fixture.run(position, limits);
    const auto& reused = warm.diagnostics->cache;
    require(reused.probes == 1 && reused.hits == 1 && reused.cutoffs == 0
            && reused.stores == 1 && reused.replacements == 0,
            "A warm root hits the full key but cannot cut off a PV node");

    fixture.search.clear();
    const auto cleared = fixture.run(position, limits);
    require(cleared.diagnostics->cache.hits == 0
            && cleared.diagnostics->cache.stores == 1
            && cleared.diagnostics->cache.replacements == 0,
            "Clearing must remove cached bounds and reset per-search events");
    fixture.search.set_hash(2);
    const auto resized = fixture.run(position, limits);
    const auto& larger = resized.diagnostics->cache;
    require(larger.hits == 0 && larger.capacity == 2 * geometry.capacity
            && larger.buckets == 2 * geometry.buckets
            && larger.allocated_bytes == 2 * geometry.allocated_bytes,
            "Resizing must discard old entries and report the replacement allocation");
    fixture.search.set_hash(1);
    fixture.search.clear();
    limits.searchmoves = {move(position, "a2a3")};
    const auto restricted = fixture.run(position, limits);
    require(restricted.diagnostics->cache.probes == 1
            && restricted.diagnostics->cache.stores == 0,
            "Restricted-root bounds must not be counted as stored");

    limits.searchmoves.clear();
    limits.nodes = 1;
    const auto interrupted = fixture.run(position, limits);
    require(interrupted.nodes == 1 && interrupted.diagnostics->cache.probes == 1
            && interrupted.diagnostics->cache.stores == 0,
            "An interrupted root probe counts, but its incomplete bound is never stored");

    fixture.search.reset_stop();
    fixture.search.stop();
    const auto stopped = fixture.search.search(position, {}, limits);
    const auto& idle = stopped.diagnostics->cache;
    require(stopped.nodes == 0 && idle.probes == 0 && idle.hits == 0
            && idle.cutoffs == 0 && idle.stores == 0 && idle.replacements == 0
            && idle.capacity == geometry.capacity,
            "An immediate stop reports geometry without inventing cache activity");
}

void hashfull_and_cache_diagnostic_parity(Fixture& fixture) {
    const auto position = Position::start();
    auto limits = depth_limit(4);
    fixture.search.clear();
    std::vector<SearchInfo> plain_reports;
    const auto plain = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
        plain_reports.push_back(info);
    });
    require(!plain.diagnostics && plain_reports.size() == 4,
            "Default searches report occupancy without allocating diagnostic traces");
    int previous_hashfull = 0;
    for (const auto& info : plain_reports) {
        require(info.hashfull >= previous_hashfull && info.hashfull <= 1000,
                "Retained occupancy must be bounded and cannot fall without clearing");
        previous_hashfull = info.hashfull;
    }
    require(previous_hashfull > 0, "A populated small table must report nonzero sampled occupancy");

    fixture.search.clear();
    limits.diagnostics = true;
    std::vector<SearchInfo> traced_reports;
    const auto traced = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
        traced_reports.push_back(info);
    });
    require(traced.best == plain.best && traced.ponder == plain.ponder && traced.score == plain.score
            && traced.depth == plain.depth && traced.nodes == plain.nodes
            && traced_reports.size() == plain_reports.size(),
            "Cache instrumentation cannot alter deterministic search results");
    for (std::size_t index = 0; index < plain_reports.size(); ++index) {
        const auto& expected = plain_reports[index];
        const auto& observed = traced_reports[index];
        require(observed.depth == expected.depth && observed.seldepth == expected.seldepth
                && observed.nodes == expected.nodes && observed.score == expected.score
                && observed.pv == expected.pv && observed.hashfull == expected.hashfull,
                "Every completed iteration and its occupancy must match with diagnostics on or off");
    }
    const auto& activity = traced.diagnostics->cache;
    require(activity.probes > 0 && activity.hits > 0 && activity.cutoffs > 0
            && activity.cutoffs <= activity.hits && activity.hits <= activity.probes
            && activity.stores > 0 && activity.stores + activity.cutoffs == activity.probes
            && activity.replacements <= activity.stores,
            "Completed unrestricted searches reconcile probes with stores and bound cutoffs");

    // New generations with no tree work retain occupancy. Separate event
    // counters must still report zero activity; occupancy is not a hit rate.
    for (const auto text : {"7k/6Q1/6K1/8/8/8/8/8 b - - 100 51",
                            "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
                            "7k/8/5K2/8/8/8/8/8 w - - 0 1"}) {
        std::vector<SearchInfo> reports;
        const auto terminal = fixture.run(fen(text), limits, {}, [&](const SearchInfo& info) {
            reports.push_back(info);
        });
        const auto& idle = terminal.diagnostics->cache;
        require(terminal.nodes == 0 && reports.size() == 1 && reports.front().hashfull == previous_hashfull
                && idle.probes == 0 && idle.hits == 0 && idle.cutoffs == 0
                && idle.stores == 0 && idle.replacements == 0,
                "Terminal and drawn roots retain occupancy without cache activity");
    }
    fixture.search.clear();
}

void forecast_scope_and_clock_budgets(Fixture& fixture) {
    const auto position = Position::start();
    auto base = baseline_limits();
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
            "An explicitly disabled baseline must not perform selective reductions");

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

/** SMP correctness uses a single small shared Hash and real NNUE weights.
 * These checks assert lifecycle/accounting and chess invariants, never exact
 * multithreaded trees: interleaving of sound shared bounds is nondeterministic.
 */
void parallel_search(Fixture& fixture) {
    fixture.enable_lmr = false;
    fixture.capture_ordering = CaptureOrdering::mvv_lva;
    const auto root = Position::start();
    for (int threads : {2, 4}) {
        fixture.search.set_threads(threads);
        auto limits = depth_limit(3);
        limits.diagnostics = true;
        std::uint64_t reported_nodes = 0;
        const auto result = fixture.run(root, limits, {}, [&](const SearchInfo& info) {
            require(info.nodes >= reported_nodes, "Aggregate reported nodes must be monotonic");
            reported_nodes = info.nodes;
            auto replay = root;
            for (auto pv_move : info.pv) {
                require(legal(replay, pv_move), "Shared-table principal variations must remain legal");
                replay.make_move(pv_move);
            }
        });
        require(result.depth == 3 && legal(root, result.best) && result.nodes >= reported_nodes,
                "The leader must complete the requested depth with coherent aggregate nodes");
        require(result.smp.threads == threads && result.smp.worker_nodes.size() == std::size_t(threads)
                && result.smp.worker_depths.size() == std::size_t(threads),
                "SMP accounting must include each configured worker exactly once");
        std::uint64_t sum = 0;
        for (auto count : result.smp.worker_nodes) sum += count;
        require(sum == result.nodes, "Final aggregate nodes must equal all joined worker counts");
        sum = 0;
        for (const auto& iteration : result.diagnostics->iterations) sum += iteration.nodes;
        require(sum == result.smp.worker_nodes.front(),
                "Iteration diagnostics must describe exactly the leader's visited nodes");
        require(result.diagnostics->cache.allocated_bytes == 8192 * 64,
                "SMP must share one Hash allocation rather than allocate one per worker");
        require(result.hashfull >= 0 && result.hashfull <= 1000 && result.time_ms >= 0,
                "Final shared cache occupancy and elapsed time must be valid");

        for (std::uint64_t budget : {1ULL, 50ULL, 1000ULL}) {
            limits = baseline_limits();
            limits.nodes = budget;
            limits.diagnostics = true;
            const auto bounded = fixture.run(root, limits);
            require(bounded.nodes == budget && legal(root, bounded.best),
                    "A global node budget must be exact even when several workers race for the last node");
            require(bounded.diagnostics->stop_reason == StopReason::node_limit,
                    "The leader must report an exhausted global node limit");
        }

        // Reconfiguration and policy clearing may never consume an external
        // stop posted before worker dispatch.
        fixture.search.reset_stop();
        fixture.search.stop();
        limits = depth_limit(3);
        limits.late_move_reductions = true;
        limits.countermove_ordering = fixture.enable_countermove;
        limits.diagnostics = true;
        const auto stopped = fixture.search.search(root, {}, limits);
        require(stopped.nodes == 0 && legal(root, stopped.best)
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "SMP startup and policy changes must preserve a prepublished stop");

        // A reporter exception must join helpers before propagating. Clearing,
        // resizing, then searching again exercises post-exception ownership.
        bool propagated = false;
        try {
            (void)fixture.run(root, depth_limit(5), {}, [](const SearchInfo&) {
                throw std::runtime_error("intentional reporter failure");
            });
        } catch (const std::runtime_error& error) {
            propagated = std::string_view(error.what()) == "intentional reporter failure";
        }
        require(propagated, "Reporter exceptions must propagate after helper cleanup");
        fixture.search.clear();
        fixture.search.set_hash(1);
        require(fixture.run(root, depth_limit(2)).depth == 2,
                "Search must remain reusable after exceptional helper shutdown");

        limits = depth_limit(3);
        limits.searchmoves = {move(root, "a2a3")};
        require(fixture.run(root, limits).best == limits.searchmoves.front(),
                "All SMP workers must honor the same root restriction");
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
    }
    for (int invalid : {0, Search::max_threads + 1}) {
        bool rejected = false;
        try { fixture.search.set_threads(invalid); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "Invalid worker counts must be rejected before mutation");
        require(fixture.run(root, depth_limit(1)).smp.threads == 4,
                "Rejected worker counts must leave the prior configuration usable");
    }
    fixture.search.set_threads(1);
    fixture.search.clear();
}

void missing_network() {
    nnue::Network empty_network;
    Search search(empty_network, 1);
    bool rejected = false;
    try { (void)search.search(Position::start(), {}, depth_limit(1)); }
    catch (const std::runtime_error&) { rejected = true; }
    require(rejected, "Search must not silently substitute evaluation for a missing NNUE network");
}

void capture_ordering_and_policy_switches(Fixture& fixture) {
    const auto position = fen("6k1/8/4p3/3p4/8/8/8/3Q2K1 w - - 0 1");
    const auto original_fen = position.fen();
    const auto original_key = position.key();
    fixture.search.clear();
    const auto baseline = fixture.run(position, depth_limit(3));
    require(baseline.ordering.policy == CaptureOrdering::mvv_lva
            && baseline.ordering.see_calls == 0 && baseline.ordering.losing_captures == 0,
            "The default policy must not compute exchange estimates");

    auto limits = depth_limit(3);
    limits.capture_ordering = CaptureOrdering::see;
    const auto candidate = fixture.run(position, limits);
    require(candidate.ordering.policy == CaptureOrdering::see && candidate.ordering.see_calls > 0
            && candidate.ordering.losing_captures > 0
            && candidate.ordering.losing_captures <= candidate.ordering.see_calls,
            "The real search must exercise and account for losing-capture ordering");
    require(candidate.score == baseline.score && legal(position, candidate.best),
            "Ordering alone must preserve the completed minimax value in this regression");

    // Switching a warm API object must isolate both TT and learned move order.
    // These checks cover both directions without relying on UCI to clear state.
    const auto restored = fixture.run(position, depth_limit(3));
    require(restored.best == baseline.best && restored.score == baseline.score
            && restored.nodes == baseline.nodes && restored.ordering.see_calls == 0,
            "Returning from SEE must reproduce a fresh default search");
    fixture.search.clear();
    const auto fresh_candidate = fixture.run(position, limits);
    require(fresh_candidate.best == candidate.best && fresh_candidate.score == candidate.score
            && fresh_candidate.nodes == candidate.nodes,
            "Entering SEE from a warm default search must match a fresh SEE search");

    fixture.search.clear();
    limits.diagnostics = true;
    std::vector<SearchInfo> reports;
    const auto traced = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
        auto replay = position;
        for (const auto pv_move : info.pv) {
            require(legal(replay, pv_move), "SEE ordering must preserve legal principal variations");
            replay.make_move(pv_move);
        }
        reports.push_back(info);
    });
    require(traced.best == candidate.best && traced.score == candidate.score && traced.nodes == candidate.nodes
            && traced.ordering.see_calls == candidate.ordering.see_calls,
            "Diagnostics cannot change the SEE search tree or its counters");
    require(position.fen() == original_fen && position.key() == original_key,
            "The ordering experiment cannot mutate its caller's position");

    // A negative exchange estimate must never discard a legal sacrifice,
    // including when it is the only allowed root move.
    limits.searchmoves = {move(position, "d1d5")};
    fixture.search.clear();
    const auto forced = fixture.run(position, limits);
    require(forced.best == limits.searchmoves.front() && forced.depth == 3
            && forced.ordering.losing_captures > 0,
            "A restricted losing capture must still be searched to the requested depth");

    // Interrupt the second iteration after exactly one additional visited node.
    fixture.search.clear();
    limits.searchmoves.clear();
    limits.depth = 0;
    limits.nodes = traced.diagnostics->iterations.front().nodes + 1;
    const auto partial = fixture.run(position, limits);
    require(partial.nodes == limits.nodes && partial.depth == 1
            && partial.best == reports.front().pv.front()
            && !partial.diagnostics->iterations.back().completed,
            "Interrupted SEE work must retain the completed move and exact node accounting");

    // Changing policy cannot erase an already published stop, including when
    // both selective search and ordering settings change in the same request.
    fixture.search.reset_stop();
    fixture.search.stop();
    limits.capture_ordering = CaptureOrdering::mvv_lva;
    limits.late_move_reductions = true;
    const auto stopped = fixture.search.search(position, {}, limits);
    require(stopped.nodes == 0 && stopped.ordering.see_calls == 0 && stopped.lmr.enabled
            && stopped.diagnostics->stop_reason == StopReason::external_stop,
            "A combined policy transition must preserve a prepublished stop");
}

/** Exercise actual learned replies and API isolation without requiring a
 * particular tied move or an improvement in search work. The exposed start
 * position is a mechanism regression, never a strength qualification sample.
 */
void countermove_ordering_and_policy_switches(Fixture& fixture) {
    const auto position = Position::start();
    const auto original_fen = position.fen();
    const auto original_key = position.key();
    auto limits = depth_limit(4);
    fixture.search.clear();
    const auto baseline = fixture.run(position, limits);
    require(!baseline.countermove.enabled && baseline.countermove.lookups == 0
            && baseline.countermove.matches == 0 && baseline.countermove.updates == 0,
            "Default searches must not use or count countermove ordering");

    limits.countermove_ordering = true;
    std::vector<SearchInfo> plain_reports;
    const auto candidate = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
        plain_reports.push_back(info);
    });
    require(candidate.countermove.enabled && candidate.depth == 4
            && candidate.score == baseline.score && legal(position, candidate.best),
            "Quiet reply ordering must preserve the completed value in this regression");
    require(candidate.countermove.lookups == 0 && candidate.countermove.matches == 0
            && candidate.countermove.updates == 0,
            "Reply statistics must remain disabled outside diagnostic searches");

    // Both transition directions are checked through the API, with no UCI
    // controller reset that could hide leaked TT or learned-history state.
    limits.countermove_ordering = false;
    const auto restored = fixture.run(position, limits);
    require(restored.best == baseline.best && restored.score == baseline.score
            && restored.nodes == baseline.nodes && !restored.countermove.enabled,
            "Disabling reply ordering must restore a fresh default search");
    fixture.search.clear();
    limits.countermove_ordering = true;
    const auto fresh = fixture.run(position, limits);
    require(fresh.best == candidate.best && fresh.score == candidate.score
            && fresh.nodes == candidate.nodes,
            "Enabling reply ordering after a warm default must match a fresh candidate");

    fixture.search.clear();
    limits.diagnostics = true;
    std::vector<SearchInfo> traced_reports;
    const auto traced = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
        auto replay = position;
        for (const auto pv_move : info.pv) {
            require(legal(replay, pv_move), "Learned replies must preserve complete legal PVs");
            replay.make_move(pv_move);
        }
        traced_reports.push_back(info);
    });
    require(traced.countermove.lookups > 0 && traced.countermove.matches > 0
            && traced.countermove.updates > 0
            && traced.countermove.matches <= traced.countermove.lookups
            && traced.countermove.updates <= traced.countermove.lookups,
            "The real search must learn and match replies with coherent per-node accounting");
    require(traced.best == candidate.best && traced.score == candidate.score
            && traced.nodes == candidate.nodes && traced_reports.size() == plain_reports.size(),
            "Reply diagnostics must not change the completed search tree");
    for (std::size_t index = 0; index < traced_reports.size(); ++index) {
        const auto& plain = plain_reports[index];
        const auto& trace = traced_reports[index];
        require(plain.depth == trace.depth && plain.seldepth == trace.seldepth
                && plain.nodes == trace.nodes && plain.score == trace.score && plain.pv == trace.pv,
                "Every completed iteration must be identical with reply diagnostics on or off");
    }
    require(position.fen() == original_fen && position.key() == original_key,
            "Learning replies cannot change the caller's position");

    // Cut off the second iteration deterministically, preserving the first
    // completed move rather than exposing any partially searched reply.
    fixture.search.clear();
    limits.depth = 0;
    limits.nodes = plain_reports.front().nodes + 1;
    const auto partial = fixture.run(position, limits);
    require(partial.nodes == limits.nodes && partial.depth == 1
            && partial.best == plain_reports.front().pv.front()
            && !partial.diagnostics->iterations.back().completed,
            "Interrupted reply searches must retain the completed result and exact node cap");

    for (bool enabled : {false, true}) {
        fixture.search.reset_stop();
        fixture.search.stop();
        limits.countermove_ordering = enabled;
        const auto stopped = fixture.search.search(position, {}, limits);
        require(stopped.nodes == 0 && legal(position, stopped.best)
                && stopped.countermove.enabled == enabled
                && stopped.countermove.lookups == 0 && stopped.countermove.matches == 0
                && stopped.countermove.updates == 0
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "Reply-policy transitions must preserve prepublished stop and reset counters");
    }
}

/** A forced root special move supplies the next node's previous-move context.
 * Check both colors and replay full PVs, including pawn-to-knight promotion;
 * no stored reply may insert an illegal move or widen the root restriction.
 */
void countermove_special_move_contexts(Fixture& fixture) {
    struct Case { const char* fen; const char* forced_move; };
    const Case cases[] = {
        {"r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"},
        {"r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", "e8c8"},
        {"7k/8/8/3pP3/8/8/8/K7 w - d6 0 1", "e5d6"},
        {"7k/8/8/8/3Pp3/8/8/K7 b - d3 0 1", "e4d3"},
        {"7k/P6p/8/8/8/8/8/K7 w - - 0 1", "a7a8n"},
        {"7k/8/8/8/8/8/p6P/7K b - - 0 1", "a2a1n"},
    };
    auto limits = depth_limit(3);
    limits.countermove_ordering = true;
    for (const auto& item : cases) {
        const auto position = fen(item.fen);
        limits.searchmoves = {move(position, item.forced_move)};
        fixture.search.clear();
        const auto result = fixture.run(position, limits, {}, [&](const SearchInfo& info) {
            auto replay = position;
            for (const auto pv_move : info.pv) {
                require(legal(replay, pv_move), "Special-move reply context must preserve legal PVs");
                replay.make_move(pv_move);
            }
        });
        require(result.best == limits.searchmoves.front() && result.depth == 3,
                "Reply ordering must honor a forced special root move to the requested depth");
    }
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "Usage: search-test /path/to/compatible-network.nnue\n";
        return 2;
    }
    try {
        transposition_entry_round_trips();
        missing_network();
        Fixture fixture{std::filesystem::path(argv[1])};
        default_selective_search(fixture);
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        move_restrictions_and_table_bounds(fixture);
        limits_and_principal_variations(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
        command_time_accounting(fixture);
        root_diagnostics(fixture);
        cache_accounting_and_lifecycle(fixture);
        hashfull_and_cache_diagnostic_parity(fixture);
        forecast_scope_and_clock_budgets(fixture);
        selective_search_verification_and_policy_switches(fixture);
        selective_special_positions(fixture);
        capture_ordering_and_policy_switches(fixture);
        countermove_ordering_and_policy_switches(fixture);
        countermove_special_move_contexts(fixture);
        parallel_search(fixture);
        // Re-run the existing chess-rule cases with selective search on.
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
        command_time_accounting(fixture);
        // Isolate the ordering experiment from LMR while repeating mandatory
        // chess-rule, cancellation, pondering, and elapsed-clock behavior.
        fixture.search.clear();
        fixture.enable_lmr = false;
        fixture.capture_ordering = CaptureOrdering::see;
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        move_restrictions_and_table_bounds(fixture);
        limits_and_principal_variations(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
        // Isolate full-depth reply ordering from SEE and LMR, and repeat the
        // rule/lifecycle suite with worker-local histories in both serial and
        // parallel searches. Existing default-mode checks remain unchanged.
        fixture.search.clear();
        fixture.capture_ordering = CaptureOrdering::mvv_lva;
        fixture.enable_countermove = true;
        terminal_positions(fixture);
        mate_at_draw_boundary(fixture);
        quiescence_terminals_and_evasions(fixture);
        repetition_history(fixture);
        move_restrictions_and_table_bounds(fixture);
        limits_and_principal_variations(fixture);
        cancellation_and_pondering(fixture);
        clock_limit(fixture);
        command_time_accounting(fixture);
        parallel_search(fixture);
        std::cout << "Search correctness checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Search test failed: " << error.what() << '\n';
        return 1;
    }
}
