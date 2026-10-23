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
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
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
    /** Monotonic receipt of this request, before controller preparation and
     * worker dispatch. Omission starts timing at search entry. Ponder still
     * charges only from ponderhit; infinite/no-clock requests ignore the budget.
     * A future timestamp is clamped to entry time, never granting extra time.
     */
    std::optional<std::chrono::steady_clock::time_point> received_at;
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
    /** Conservative one-ply reductions; opt out for controlled comparisons. */
    bool late_move_reductions = true;
    /** Experimental extra ply for late quiet piece moves; requires ordinary LMR. */
    bool deep_quiet_reductions = false;
    CaptureOrdering capture_ordering = CaptureOrdering::mvv_lva;
    /** Experimental quiet reply ordering; changes neither depth nor pruning. */
    bool countermove_ordering = false;
    /** Experimental reduced null probe followed by a legal-move verification. */
    bool null_move_pruning = false;
    /** Experimental shallow static cutoff at quiet interior scout nodes. */
    bool reverse_futility_pruning = false;
    /** Experimental negative-SEE capture filter in interior scout quiescence. */
    bool qsearch_see_pruning = false;
    /** Zero disables probing. Interior probes require at least this depth;
     * root DTZ ranking is independent of the interior depth threshold. */
    int syzygy_probe_limit = 7;
    int syzygy_probe_depth = 1;
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
    /** Nonempty retained entries per thousand sampled entries, using at most
     * the first 1,000 table entries. Includes older search generations; this
     * is neither a cache hit rate nor the percentage of Hash bytes allocated.
     */
    int hashfull = 0;
    std::uint64_t tbhits = 0;
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

/** Optional transposition-table measurements, reset for each search. Geometry
 * describes actual allocated entry storage (excluding the vector object).
 * A probe counts one bucket lookup; a hit requires a full-key match. A cutoff
 * counts only a bound that actually ends a non-PV node. Stores count save
 * attempts, including attempts retaining a deeper exact entry. Replacements
 * count occupied different-key evictions, never empty fills or same-key writes.
 * Interrupted work remains included. Event counters are updated only when
 * SearchLimits::diagnostics is enabled; no node event stream is retained.
 * With SMP, geometry describes the single shared table and final event totals
 * sum the separate worker counters after joining every helper.
 */
struct CacheStatistics {
    std::size_t entry_bytes = 0;
    std::size_t bucket_bytes = 0;
    std::size_t buckets = 0;
    std::size_t capacity = 0;
    std::size_t allocated_bytes = 0;
    std::uint64_t probes = 0;
    std::uint64_t hits = 0;
    std::uint64_t cutoffs = 0;
    std::uint64_t stores = 0;
    std::uint64_t replacements = 0;
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
    CacheStatistics cache;
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

/** Extra-ply subset of ordinary LMR, measured only with diagnostics enabled.
 * Attempts include interrupted work; outcomes require ordinary-depth verification.
 * The enabled flag reports configuration even when master LMR is disabled.
 */
struct DeepLateMoveStatistics {
    bool enabled = false;
    std::uint64_t extra_reductions = 0;
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

/** Optional positive-depth reply-table measurements, summed across workers.
 * A lookup uses the preceding move's original piece/color and destination.
 * A match means its stored quiet reply occurs in the legal list (possibly
 * already favored by TT/killers); updates count completed quiet beta cutoffs.
 * Counters include interrupted tree work and require diagnostics to be enabled.
 */
struct CountermoveStatistics {
    bool enabled = false;
    std::uint64_t lookups = 0;
    std::uint64_t matches = 0;
    std::uint64_t updates = 0;
};

/** Optional per-worker null-search counters, summed after all helpers join.
 * Probes/verifications include interrupted attempts; accepted/rejected counts
 * require completion. A verified shallow cutoff is still a heuristic, not a
 * proof of the original-depth score. Disabled diagnostics leave counters zero.
 */
struct NullMoveStatistics {
    bool enabled = false;
    std::uint64_t probes = 0;
    std::uint64_t fail_highs = 0;
    std::uint64_t verifications = 0;
    std::uint64_t cutoffs = 0;
    std::uint64_t rejected = 0;
};

/** Fresh static evaluations and accepted shallow reverse-futility cutoffs.
 * Worker-local counters include interrupted tree work, require diagnostics,
 * and aggregate after every helper has joined. A cutoff is heuristic evidence,
 * not a proof of the requested-depth score or preserved playing strength.
 */
struct ReverseFutilityStatistics {
    bool enabled = false;
    std::uint64_t evaluations = 0;
    std::uint64_t cutoffs = 0;
};

/** Exchange evaluations and skipped captures for the optional quiescence
 * filter. Counters require diagnostics, include interrupted work, and are
 * summed only after joining helpers. No counter implies preserved strength.
 */
struct QSearchSeeStatistics {
    bool enabled = false;
    std::uint64_t evaluations = 0;
    std::uint64_t pruned = 0;
};

/** Final accounting for independent workers sharing a transposition table.
 * Worker zero is the leader and supplies the result/PV. Helpers contribute
 * bounds and move ordering, never an unverified vote for the returned move.
 * SearchInfo/SearchResult nodes are aggregate; iteration diagnostics describe
 * only worker zero and sum to worker_nodes.front(). Worker depths are their
 * last fully completed iterations, not a combined or averaged search depth.
 */
struct SmpStatistics {
    int threads = 1;
    std::vector<std::uint64_t> worker_nodes;
    std::vector<int> worker_depths;
};

#ifdef CHESS0LIVE_CLOCK_TRACE
/** Diagnostic-build-only monotonic boundaries. Zero denotes an unavailable
 * sample (e.g. an exception); hard_stop_ns is also zero for non-hard stops.
 * The leader's first hard-stop observation is sampled after the comparison,
 * never with additional clock reads on ordinary visited nodes. These stamps
 * are process clock values, not directly comparable to a host reader's epoch.
 */
struct SearchClockTrace {
    std::int64_t search_started_ns = 0;
    std::int64_t hard_stop_ns = 0;
    std::int64_t leader_finished_ns = 0;
    std::int64_t joined_ns = 0;
    std::int64_t accounted_ns = 0;
    std::int64_t hard_budget_ns = -1;
};
#endif

struct SearchResult {
#ifdef CHESS0LIVE_CLOCK_TRACE
    SearchClockTrace clock_trace;
#endif
    Move best;
    Move ponder;
    int score = 0;
    int depth = 0;
    std::uint64_t nodes = 0;
    /** Final totals include interrupted work and helper shutdown. */
    std::int64_t time_ms = 0;
    int hashfull = 0;
    SmpStatistics smp;
    /** Successful root/interior tablebase probes across all workers, not files read. */
    std::uint64_t tbhits = 0;
    std::optional<SearchDiagnostics> diagnostics;
    LateMoveStatistics lmr;
    DeepLateMoveStatistics deep_lmr;
    OrderingStatistics ordering;
    CountermoveStatistics countermove;
    NullMoveStatistics nullmove;
    ReverseFutilityStatistics reverse_futility;
    QSearchSeeStatistics qsearch_see;
};

/** Independent iterative deepening with optional shared-table Lazy SMP.
 *
 * The caller serializes search(), clear(), set_hash(), set_threads(), and
 * destruction. Only stop() and ponderhit() may run concurrently with search().
 * Call reset_stop()
 * BEFORE launching an asynchronous search, not inside its new thread: this
 * preserves a stop received immediately after UCI "go". Immutable NNUE weights
 * are shared, as is one synchronized transposition table. Evaluators and all
 * mutable search histories are worker-local. Every helper is joined before
 * search() returns or propagates an exception; callbacks run only on the leader.
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
    static constexpr int max_threads = 64;
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
    /** Reconfigure workers while idle; preserve the previous configuration if
     * allocation fails. A successful change clears learned search/cache state.
     */
    void set_threads(int threads);
    /** Configure only while idle. Empty path disables probing; all configuration
     * attempts invalidate cached search bounds. No table files are downloaded. */
    bool set_syzygy_path(const std::string& path, std::string& error);
    unsigned syzygy_largest() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace chess0live
