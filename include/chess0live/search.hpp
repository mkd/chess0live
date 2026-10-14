/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include "chess0live/types.hpp"
#include "chess0live/time_management.hpp"

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <vector>

namespace chess0live {
class Position;
namespace nnue { class Network; }

enum class CaptureOrdering { mvv_lva, see };

/** Limits are intersections: the first exhausted hard limit stops the search.
 * Negative clock values mean unspecified; zero is a real exhausted clock.
 * Depth and nodes zero mean unlimited. Explicit movetime takes precedence over
 * clock allocation. Pondering defers time consumption until ponderhit().
 */
struct SearchLimits {
    int depth = 0;
    std::uint64_t nodes = 0;
    std::int64_t movetime_ms = -1;
    std::int64_t wtime_ms = -1;
    std::int64_t btime_ms = -1;
    std::int64_t winc_ms = 0;
    std::int64_t binc_ms = 0;
    int movestogo = 0;
    int mate = 0;
    bool infinite = false;
    bool ponder = false;
    int move_overhead_ms = 20;
    TimePolicy time_policy = TimePolicy::classic;
    bool diagnostics = false;
    bool late_move_reductions = false;
    CaptureOrdering capture_ordering = CaptureOrdering::mvv_lva;
    /** Empty means all legal moves; entries must be generated for the root. */
    std::vector<Move> searchmoves;
};

struct SearchInfo {
    int depth = 0;
    int seldepth = 0;
    std::uint64_t nodes = 0;
    std::int64_t time_ms = 0;
    int score = 0;
    std::vector<Move> pv;
};

enum class StopReason {
    external_stop, node_limit, hard_time, soft_time, forecast,
    depth_limit, mate_limit, terminal, draw
};

/** Root-level measurements, never a per-node event stream. A failed aspiration
 * window is part of its enclosing iteration. An interrupted iteration records
 * all discarded work even though the returned move comes from the last complete
 * iteration. Durations use a monotonic clock at greater precision than UCI time.
 */
struct IterationDiagnostics {
    int depth = 0;
    bool completed = false;
    std::uint64_t nodes = 0;
    double duration_ms = 0;
    double elapsed_ms = 0;
};

struct SearchDiagnostics {
    TimePolicy policy = TimePolicy::classic;
    bool forecast_active = false;
    StopReason stop_reason = StopReason::depth_limit;
    double elapsed_ms = 0;
    double soft_ms = 0;
    double hard_ms = 0;
    double target_ms = 0;
    double predicted_next_ms = 0;
    std::vector<IterationDiagnostics> iterations;
};

/** Counts for the optional selective-search hypothesis. Reductions and
 * researches count attempts, including calls interrupted by a limit/stop.
 * fail_lows and verified_cutoffs count only completed ordinary-depth
 * verification outcomes. None of these counters implies a strength gain.
 */
struct LateMoveStatistics {
    bool enabled = false;
    std::uint64_t reductions = 0;
    std::uint64_t researches = 0;
    std::uint64_t fail_lows = 0;
    std::uint64_t verified_cutoffs = 0;
};

/** Rankings performed, including work later interrupted by a search limit.
 * TT moves and promotions retain their priority without calling SEE. Counters
 * are zero in the default MVV-LVA mode; no capture is pruned by either policy.
 */
struct OrderingStatistics {
    CaptureOrdering policy = CaptureOrdering::mvv_lva;
    std::uint64_t see_calls = 0;
    std::uint64_t losing_captures = 0;
};

struct SearchResult {
    Move best;
    Move ponder;
    int score = 0;
    int depth = 0;
    std::uint64_t nodes = 0;
    std::optional<SearchDiagnostics> diagnostics;
    LateMoveStatistics lmr;
    OrderingStatistics ordering;
};

/** Independent, single-worker iterative deepening search.
 *
 * The caller serializes search(), clear(), set_hash(), and destruction. Only
 * stop() and ponderhit() may run concurrently with search(). Call reset_stop()
 * BEFORE launching an asynchronous search, not inside its new thread: this
 * preserves a stop received immediately after UCI "go". Immutable NNUE weights
 * may be shared, while the evaluator and transposition table are worker-local.
 *
 * The game history contains position keys through the root, in chronological
 * order; a missing final root key is appended. Full history enables exact
 * threefold detection. Callbacks run synchronously on the searching thread.
 * A completed depth/node-limited ponder or infinite search may return; the UCI
 * controller must defer bestmove until ponderhit/stop as appropriate.
 */
class Search {
public:
    static constexpr int mate_score = 31000;
    static constexpr int mate_threshold = 30000;
    static constexpr int max_ply = 128;
    static constexpr int max_threads = 1;
    using Reporter = std::function<void(const SearchInfo&)>;

    explicit Search(const nnue::Network& network, std::size_t hash_mb = 64,
                    int threads = 1);
    ~Search();
    Search(const Search&) = delete;
    Search& operator=(const Search&) = delete;
    SearchResult search(Position position, std::vector<std::uint64_t> history,
                        const SearchLimits& limits, Reporter report = {});
    void reset_stop();
    void stop() noexcept;
    void ponderhit() noexcept;
    void clear();
    void set_hash(std::size_t megabytes);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace chess0live
