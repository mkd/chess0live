/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/search.hpp"

#include "chess0live/detail/continuation_history.hpp"
#include "chess0live/detail/move_hint_entry.hpp"
#include "chess0live/detail/transposition_entry.hpp"
#include "chess0live/exchange.hpp"
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"
#include "chess0live/search_policy.hpp"
#include "chess0live/tablebase.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <chrono>
#include <cmath>
#include <exception>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>

namespace chess0live {
namespace {

using Clock = std::chrono::steady_clock;
constexpr int infinity = 32000;
constexpr int history_limit = 16384;
// WDL is not distance-to-mate. Reserve a band below actual mate proofs and
// above heuristic evaluation; never encode DTZ as a mate score.
constexpr int tablebase_score = 29000;
constexpr std::array<int, 7> piece_order_value{0, 100, 320, 330, 500, 900, 20000};

/** Stable-clock ticks, used only for elapsed durations, never wall-clock time. */
std::int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count();
}

/** Saturate pathological direct-API origins without signed subtraction overflow.
 * Normal monotonic durations take the same path; future origins charge zero.
 */
std::int64_t elapsed_ns(std::int64_t end, std::int64_t begin) {
    if (end <= begin) return 0;
    const auto difference = std::uint64_t(end) - std::uint64_t(begin);
    return static_cast<std::int64_t>(std::min(difference,
        std::uint64_t(std::numeric_limits<std::int64_t>::max())));
}

/** Avalanche a position key before adding it to a reversible-history digest. */
std::uint64_t mix(std::uint64_t value) {
    value ^= value >> 30;
    value *= 0xbf58476d1ce4e5b9ULL;
    value ^= value >> 27;
    value *= 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

/** Only provably dead ordinary-chess material configurations are accepted.
 * Two knights against a king, for example, are deliberately NOT called dead:
 * mate is possible with cooperative play, even though it cannot be forced.
 */
bool dead_material(const Position& position) {
    Bitboard bishops = 0;
    Bitboard knights = 0;
    for (Color side : {Color::white, Color::black}) {
        if (position.pieces(side, PieceType::pawn)
            || position.pieces(side, PieceType::rook)
            || position.pieces(side, PieceType::queen)) return false;
        bishops |= position.pieces(side, PieceType::bishop);
        knights |= position.pieces(side, PieceType::knight);
    }
    if (std::popcount(bishops | knights) <= 1) return true;
    if (knights) return false;
    constexpr Bitboard dark_squares = 0xaa55aa55aa55aa55ULL;
    return !(bishops & dark_squares) || !(bishops & ~dark_squares);
}

// Full-key compact entries are copied while their bucket stripe is locked.
// A seqlock around non-atomic Entry fields would still be a C++ data race.
using detail::transposition::Bound;
using detail::transposition::Entry;
using detail::transposition::Bucket;
using detail::transposition::MoveHintEntry;
static_assert(sizeof(Bucket) + sizeof(MoveHintEntry)
              <= detail::transposition::bucket_budget_bytes);
// A child decrements depth before its at-most-one check extension, so no stored
// interior depth can exceed the capped root depth. Keep this proof explicit if
// the search's maximum or extension policy changes in the future.
static_assert(Search::max_ply - 2 <= std::numeric_limits<std::uint8_t>::max());

/** Mate values in a table describe distance from its position, not from the
 * previous search's root. Convert at the table boundary in both directions.
 */
int score_to_table(int score, int ply) {
    if (score >= Search::mate_threshold) return score + ply;
    if (score <= -Search::mate_threshold) return score - ply;
    return score;
}
int score_from_table(int score, int ply) {
    if (score >= Search::mate_threshold) return score - ply;
    if (score <= -Search::mate_threshold) return score + ply;
    return score;
}

struct TimeBudget {
    bool active = false;
    double soft_ms = 0;
    double hard_ms = 0;
};

/** Leave an explicit protocol/transport reserve, and never allocate time which
 * is not on the clock. Increment is a planning input, not spendable current time.
 * A movetime request has one hard deadline and does not stop at a soft deadline.
 */
TimeBudget allocate_time(const Position& position, const SearchLimits& limits) {
    if (limits.infinite) return {};
    const double reserve = std::max(0, limits.move_overhead_ms);
    if (limits.movetime_ms >= 0) {
        const double duration = std::max(0.0, double(limits.movetime_ms) - reserve);
        return {true, duration, duration};
    }
    const auto remaining = position.turn() == Color::white
        ? limits.wtime_ms : limits.btime_ms;
    if (remaining < 0) return {};
    const auto increment = position.turn() == Color::white
        ? limits.winc_ms : limits.binc_ms;
    const double available = std::max(0.0, double(remaining) - reserve);
    const int estimated_moves = std::clamp(
        32 - int(std::min(position.fullmove_number(), std::uint32_t{80})) / 4, 12, 32);
    const int moves = limits.movestogo > 0 ? limits.movestogo : estimated_moves;
    const double planned = available / std::max(1, moves)
        + 0.8 * double(std::max(std::int64_t{0}, increment));
    const double soft = std::min(available, std::max(1.0, planned));
    const bool bounded = limits.time_policy == TimePolicy::bounded
        && limits.depth == 0 && limits.nodes == 0 && limits.mate == 0 && !limits.ponder;
    const double hard = time_management::clock_hard_limit(available, soft, bounded);
    return {true, soft, hard};
}

/** One cache and one cancellation/time domain per Search. Clearing, sizing,
 * generation changes, and worker configuration happen before launching helpers.
 * A single-worker search never acquires a cache mutex. Mutexes are striped to
 * bound synchronization storage independently of Hash; no reference to an Entry
 * escapes a lock. Padded node publications avoid false sharing between workers.
 */
struct SharedSearch {
    static constexpr std::size_t stripe_count = 1024;
    struct alignas(64) PublishedNodes { std::atomic<std::uint64_t> value{0}; };
    std::vector<Bucket> table;
    // Empty when disabled; otherwise exactly one direct-mapped hint per score
    // bucket. The score bucket count/mask and its 96-byte reservation stay fixed.
    // The 80-byte physical total describes retained entry storage; transactional
    // resizing temporarily keeps both old and replacement allocations alive.
    std::vector<MoveHintEntry> move_hints;
    std::array<std::mutex, stripe_count> stripes;
    std::array<PublishedNodes, Search::max_threads> published;
    std::atomic<bool> stopped{false};
    std::atomic<bool> leader_finished{false};
    std::atomic<std::int64_t> ponder_hit_ns{-1};
    std::atomic<std::uint64_t> node_tickets{0};
    std::atomic<std::uint64_t> tbhits{0};
    tablebase::Syzygy tablebases;
    int tablebase_limit = 0; // Immutable during worker execution.
    int threads = 1;
    std::uint8_t generation = 0;

    void resize(std::size_t megabytes) {
        if (megabytes == 0 || megabytes > std::numeric_limits<std::size_t>::max() / (1024 * 1024))
            throw std::invalid_argument("Hash must be a positive, representable number of megabytes");
        const auto count = std::bit_floor(megabytes * 1024 * 1024
                                         / detail::transposition::bucket_budget_bytes);
        std::vector<Bucket> replacement(count);
        std::vector<MoveHintEntry> hint_replacement;
        if (!move_hints.empty()) hint_replacement.resize(count);
        // Both allocations finish before either old cache is changed. A failed
        // resize propagates normally and retains the prior tables and geometry.
        table.swap(replacement);
        move_hints.swap(hint_replacement);
    }

    /** Change optional storage before policy state or cached bounds are cleared.
     * Allocation failure must leave the previous configuration intact rather
     * than silently claim that an enabled ordering experiment actually ran.
     */
    void set_move_hints(bool enabled) {
        if (enabled == !move_hints.empty()) return;
        std::vector<MoveHintEntry> replacement(enabled ? table.size() : 0);
        move_hints.swap(replacement);
    }

    std::unique_lock<std::mutex> lock_bucket(std::size_t bucket) {
        std::unique_lock lock(stripes[bucket % stripe_count], std::defer_lock);
        if (threads > 1) lock.lock();
        return lock;
    }
};

struct SearchWorker {
    using Reporter = Search::Reporter;
    static constexpr int max_ply = Search::max_ply;
    static constexpr int mate_score = Search::mate_score;
    static constexpr int mate_threshold = Search::mate_threshold;
    const nnue::Network& network;
    nnue::Evaluator evaluator;
    SharedSearch& shared;
    const std::size_t id;
    std::array<std::array<std::array<int, 64>, 64>, 2> history_score{};
    std::array<std::array<Move, 2>, max_ply> killers{};
    struct RankedMove { Move move; int score; };
    // Scratch belongs to one worker, not one ply. order() copies the entire
    // result back before any child search can reuse this storage. Retain capacity
    // across nodes, but recompute scores from the current history on every call.
    std::vector<RankedMove> ranked_moves;
    // Six piece types per color, then the previous move's destination. The
    // original piece is used even for a promotion; no game-history move is
    // inferred at the root. Context travels by value through re-searches.
    static constexpr std::size_t no_previous_move = 12 * 64;
    std::array<Move, no_previous_move> countermoves{};
    static_assert(no_previous_move == detail::ContinuationHistory::no_context);
    // Contextual scores belong to one worker and are allocated before dispatch.
    // Neither Hash capacity nor shared-table synchronization depends on them.
    detail::ContinuationHistory continuation_scores;
    std::array<std::array<Move, max_ply>, max_ply> pv{};
    std::array<int, max_ply> pv_length{};
    std::vector<std::uint64_t> game_history;
    SearchLimits limits;
    TimeBudget time;
    std::int64_t started_ns = 0;
    std::uint64_t nodes = 0;
    int seldepth = 0;
    bool aborted = false;
    StopReason stop_reason = StopReason::depth_limit;
    LateMoveStatistics lmr;
    DeepLateMoveStatistics deep_lmr;
    OrderingStatistics ordering;
    CountermoveStatistics countermove;
    ContinuationHistoryStatistics continuation;
    NullMoveStatistics nullmove;
    ReverseFutilityStatistics reverse_futility;
    QSearchSeeStatistics qsearch_see;
    ProbCutStatistics probcut;
    CacheStatistics cache;
    MoveHintStatistics move_hints;
    int completed_depth = 0;

    // Propagate by value through every descendant: neither a fictitious pass
    // nor its legal-move verification may consume selective TT bounds or learn
    // ordering state. ProbCut probes share that isolation but, like verification,
    // retain genuine game-history draws because every searched move is legal.
    enum class Mode { ordinary, null_probe, verification, probcut };

    SearchWorker(const nnue::Network& weights, SharedSearch& state, std::size_t index)
        : network(weights), evaluator(weights), shared(state), id(index) {}

    /** Search-policy changes cannot reuse heuristic bounds or move histories
     * from another policy. Do not clear the externally published stop flag.
     */
    void clear() {
        history_score = {};
        killers = {};
        countermoves = {};
        continuation_scores.clear();
        evaluator.reset();
    }

    std::int64_t elapsed_ms() const { return elapsed_ns(now_ns(), started_ns) / 1000000; }

    /** No timing budget is consumed while awaiting the opponent's ponder move.
     * Atomic timestamp publication also handles ponderhit before worker startup.
     */
    double clock_elapsed_ms() const {
        auto from = started_ns;
        if (limits.ponder) {
            from = shared.ponder_hit_ns.load(std::memory_order_relaxed);
            if (from < 0) return -1.0;
        }
        return double(elapsed_ns(now_ns(), from)) / 1000000.0;
    }

    bool must_stop() {
        if (aborted) return true;
        if (shared.stopped.load(std::memory_order_relaxed)
            || shared.leader_finished.load(std::memory_order_relaxed))
            stop_reason = StopReason::external_stop;
        else if (limits.nodes && (shared.threads == 1 ? nodes
            : shared.node_tickets.load(std::memory_order_relaxed)) >= limits.nodes)
            stop_reason = StopReason::node_limit;
        else if (time.active && clock_elapsed_ms() >= time.hard_ms) {
            stop_reason = StopReason::hard_time;
#ifdef CHESS0LIVE_CLOCK_TRACE
            // One extra clock read only when the first hard stop is observed.
            hard_stop_ns = now_ns();
#endif
        }
        else return false;
        aborted = true;
        return true;
    }

#ifdef CHESS0LIVE_CLOCK_TRACE
    std::int64_t hard_stop_ns = 0;
#endif

    bool visit(int ply) {
        if (must_stop()) return false;
        // Only explicit global node limits pay for a contended atomic per
        // visit. Each successful ticket represents exactly one visited node.
        if (shared.threads > 1 && limits.nodes) {
            auto ticket = shared.node_tickets.load(std::memory_order_relaxed);
            do {
                if (ticket >= limits.nodes) {
                    aborted = true;
                    stop_reason = StopReason::node_limit;
                    return false;
                }
            } while (!shared.node_tickets.compare_exchange_weak(
                ticket, ticket + 1, std::memory_order_relaxed));
        }
        ++nodes;
        if (shared.threads > 1 && (nodes & 127) == 0) publish_nodes();
        seldepth = std::max(seldepth, ply);
        pv_length[static_cast<std::size_t>(ply)] = ply;
        return true;
    }

    void publish_nodes() {
        shared.published[id].value.store(nodes, std::memory_order_relaxed);
    }

    std::uint64_t total_nodes() const {
        if (shared.threads == 1) return nodes;
        auto total = nodes;
        for (int index = 0; index < shared.threads; ++index)
            if (std::size_t(index) != id)
                total += shared.published[std::size_t(index)].value.load(std::memory_order_relaxed);
        return total;
    }

    bool draw(const Position& position, Mode mode = Mode::ordinary) const {
        if (mode == Mode::null_probe) return dead_material(position);
        if (position.halfmove_clock() >= 100 || dead_material(position)) return true;
        int occurrences = 0;
        const auto reversible = std::min(game_history.size(),
            std::size_t(position.halfmove_clock()) + 1);
        const auto begin = game_history.size() - reversible;
        for (auto index = game_history.size(); index > begin;) {
            --index;
            if (game_history[index] == position.key() && ++occurrences == 3) return true;
        }
        return false;
    }

    /** A twofold real-history occurrence is enough to exclude a null probe.
     * The ordinary search still requires three occurrences to claim a draw.
     */
    bool repeated(const Position& position) const {
        int occurrences = 0;
        const auto count = std::min(game_history.size(), std::size_t(position.halfmove_clock()) + 1);
        for (auto i = game_history.size(); i > game_history.size() - count;)
            if (game_history[--i] == position.key() && ++occurrences == 2) return true;
        return false;
    }

    /** Ordinary position-only TT bounds are unsound near repetition or rule 50.
     * Include the halfmove clock and the multiset of reversible-history keys.
     * Addition preserves repeated occurrences (unlike XOR, which cancels pairs).
     * Order is irrelevant to future repetition counts; irreversible moves reset
     * the digest. This deliberately trades some TT hits for correct draw state.
     */
    std::uint64_t table_key(const Position& position, std::uint64_t digest) const {
        return mix(position.key() ^ std::rotl(digest, 17)
                   ^ mix(std::uint64_t(position.halfmove_clock()) + 1));
    }

    /** UCI hashfull samples all retained nonempty entries, including older searches. Sampling is
     * done only when reporting a completed iteration or terminal root; no
     * counters or table scan are added to the ordinary node-search path.
     */
    int hashfull() {
        const auto sample = std::min(std::size_t{1000}, shared.table.size() * std::size_t{4});
        std::size_t occupied = 0;
        for (std::size_t index = 0; index < sample; index += 4) {
            const auto guard = shared.lock_bucket(index / 4);
            for (std::size_t offset = 0; offset < 4 && index + offset < sample; ++offset) {
                const auto& entry = shared.table[index / 4].entries[offset];
                occupied += entry.bound() != Bound::empty;
            }
        }
        return sample == 0 ? 0 : static_cast<int>(1000 * occupied / sample);
    }

    std::optional<Entry> probe(std::uint64_t key) {
        if (limits.diagnostics) ++cache.probes;
        const auto bucket_index = static_cast<std::size_t>(key) & (shared.table.size() - 1);
        const auto guard = shared.lock_bucket(bucket_index);
        for (const auto& entry : shared.table[bucket_index].entries) {
            if (entry.bound() != Bound::empty && entry.key == key) {
                if (limits.diagnostics) ++cache.hits;
                return entry;
            }
        }
        return std::nullopt;
    }

    void save(std::uint64_t key, Move move, int score, int depth, int ply, Bound bound) {
        assert(depth > 0 && depth <= max_ply - 2);
        if (limits.diagnostics) ++cache.stores;
        const auto bucket_index = static_cast<std::size_t>(key) & (shared.table.size() - 1);
        const auto guard = shared.lock_bucket(bucket_index);
        auto& entries = shared.table[bucket_index].entries;
        Entry* victim = &entries.front();
        int lowest_quality = std::numeric_limits<int>::max();
        for (auto& entry : entries) {
            if (entry.bound() == Bound::empty || entry.key == key) {
                victim = &entry;
                break;
            }
            const int age = static_cast<std::uint8_t>(shared.generation - entry.generation);
            const int quality = int(entry.depth) - 8 * age;
            if (quality < lowest_quality) {
                lowest_quality = quality;
                victim = &entry;
            }
        }
        // Keep a deeper exact result while refreshing only its generation.
        if (victim->bound() == Bound::exact && victim->key == key
            && victim->depth > depth && bound != Bound::exact) {
            victim->generation = shared.generation;
            return;
        }
        if (limits.diagnostics && victim->bound() != Bound::empty && victim->key != key)
            ++cache.replacements;
        *victim = {key, move, static_cast<std::int16_t>(score_to_table(score, ply)),
                   static_cast<std::uint8_t>(depth), bound, shared.generation};
    }

    // Only positive-depth alphabeta calls use this gate. Quiescence has no hint
    // lookup/store path; a restricted root's descendants remain unrestricted.
    bool move_hints_allowed(int ply, Mode mode) const {
        return limits.tt_move_hints && !shared.move_hints.empty() && mode == Mode::ordinary
            && (ply != 0 || limits.searchmoves.empty());
    }

    /** Raw hint lookup; callers must first enforce the main-search mode/root
     * guard. Copy under the existing stripe lock; no entry reference escapes.
     */
    std::optional<Move> probe_move_hint(std::uint64_t key) {
        if (!limits.tt_move_hints || shared.move_hints.empty()) return std::nullopt;
        assert(shared.move_hints.size() == shared.table.size());
        if (limits.diagnostics) ++move_hints.probes;
        const auto bucket_index = static_cast<std::size_t>(key) & (shared.table.size() - 1);
        const auto guard = shared.lock_bucket(bucket_index);
        const auto& entry = shared.move_hints[bucket_index];
        if (entry.key != key || !entry.move.valid()) return std::nullopt;
        if (limits.diagnostics) ++move_hints.hits;
        return entry.move;
    }

    /** A context-qualified legal TT move always wins. The fallback only changes
     * ordering of an already legal list; retain contextual_tt separately for
     * score handling and LMR eligibility even when this returns a different move.
     * Move equality includes flags and promotion, not just the two coordinates.
     */
    Move ordering_move(std::uint64_t key, const std::vector<Move>& legal,
                       Move contextual_tt, int ply, Mode mode) {
        if (!move_hints_allowed(ply, mode)) return contextual_tt;
        if (std::find(legal.begin(), legal.end(), contextual_tt) != legal.end())
            return contextual_tt;
        if (const auto hint = probe_move_hint(key))
            if (std::find(legal.begin(), legal.end(), *hint) != legal.end()) {
                if (limits.diagnostics) ++move_hints.legal_matches;
                return *hint;
            }
        return contextual_tt;
    }

    /** The caller supplies the legal best move of a completed ordinary node.
     * Never store from an interrupted, restricted-root or speculative result.
     * Last-completed direct replacement is deliberately independent of score
     * depth, age and bound replacement, with a separate non-nested lock scope.
     */
    void store_move_hint(std::uint64_t key, Move move, int ply, Mode mode) {
        if (!move_hints_allowed(ply, mode) || !move.valid()) return;
        assert(shared.move_hints.size() == shared.table.size());
        const auto bucket_index = static_cast<std::size_t>(key) & (shared.table.size() - 1);
        const auto guard = shared.lock_bucket(bucket_index);
        shared.move_hints[bucket_index] = {key, move};
        if (limits.diagnostics) ++move_hints.stores;
    }

    int ordering_score(const Position& position, Move move, Move tt_move, int ply,
                       Move reply, std::size_t previous_move = no_previous_move) {
        if (move == tt_move) return 2000000;
        if (move.promotion != PieceType::none)
            return 1200000 + piece_order_value[static_cast<unsigned>(move.promotion)];
        if (move.is_capture()) {
            const int victim = move.flags & en_passant ? 100
                : piece_order_value[static_cast<unsigned>(type_of(position.at(move.to)))];
            const int attacker = piece_order_value[static_cast<unsigned>(type_of(position.at(move.from)))];
            return 1000000 + 16 * victim - attacker;
        }
        if (move == killers[static_cast<std::size_t>(ply)][0]) return 900000;
        if (move == killers[static_cast<std::size_t>(ply)][1]) return 800000;
        if (move == reply) return 700000;
        int score = history_score[static_cast<unsigned>(position.turn())][move.from][move.to];
        if (limits.continuation_history && previous_move < no_previous_move) {
            const int contextual = continuation_scores.value(previous_move,
                detail::ContinuationHistory::context(position.at(move.from), move.to));
            score += contextual;
            if (limits.diagnostics) {
                ++continuation.lookups;
                if (contextual != 0) ++continuation.nonzero;
            }
        }
        return score;
    }

    /** Helpers vary only equally ranked root moves. TT/capture/promotion and
     * history priorities stay authoritative; no new selective pruning is used.
     * Worker zero retains the exact original deterministic tie order.
     */
    bool tie_before(Move left, Move right, int ply) const {
        if (id != 0 && ply == 0) {
            const auto key = [&](Move move) {
                return mix(std::uint64_t(move.from) * 64 + move.to + 4096 * id
                           + 65536 * static_cast<unsigned>(move.promotion));
            };
            if (key(left) != key(right)) return key(left) < key(right);
        }
        if (left.from != right.from) return left.from < right.from;
        if (left.to != right.to) return left.to < right.to;
        return left.promotion < right.promotion;
    }

    void order(const Position& position, std::vector<Move>& moves, Move tt_move, int ply,
               Move reply = {}, std::size_t previous_move = no_previous_move) {
        ranked_moves.clear();
        ranked_moves.reserve(moves.size());
        const bool use_see = limits.capture_ordering == CaptureOrdering::see;
        // Freeze the same ranking as the former comparator, whose inputs were
        // immutable during sorting. Scoring once avoids repeated board/history
        // reads; delaying score computation into child search would change order.
        for (const auto move : moves) {
            auto score = ordering_score(position, move, tt_move, ply, reply, previous_move);
            // SEE still visits every eligible capture, including singleton lists.
            // Losing ordinary captures follow quiet history; TT and promotions
            // retain priority. Neither ordering mode prunes any moves.
            if (use_see && move != tt_move && move.is_capture()
                && move.promotion == PieceType::none) {
                ++ordering.see_calls;
                if (static_exchange(position, move) < 0) {
                    ++ordering.losing_captures;
                    score -= 2000000;
                }
            }
            ranked_moves.push_back({move, score});
        }
        std::sort(ranked_moves.begin(), ranked_moves.end(), [&](const RankedMove& left, const RankedMove& right) {
            if (left.score != right.score) return left.score > right.score;
            return tie_before(left.move, right.move, ply);
        });
        std::transform(ranked_moves.begin(), ranked_moves.end(), moves.begin(),
                       [](const RankedMove& ranked) { return ranked.move; });
    }

    void update_history(Color side, Move move, int bonus) {
        auto& value = history_score[static_cast<unsigned>(side)][move.from][move.to];
        bonus = std::clamp(bonus, -history_limit, history_limit);
        value += bonus - value * std::abs(bonus) / history_limit;
    }

    /** Learn from an ordinary quiet cutoff using the caller's completed prefix.
     * Its ordered move list survives child searches and re-searches unchanged;
     * the prefix before cutoff_index is exactly the former collected quiet list
     * after filtering. Read history now, after the children have finished, and
     * retain winner-first / prior-moves-in-order updates, including duplicates.
     * If future pruning skips moves in this loop, preserve the actual searched
     * subset instead of assuming that every earlier list entry was searched.
     */
    void learn_quiet_cutoff(Color side, const std::vector<Move>& moves,
                            std::size_t cutoff_index, int depth, int ply,
                            std::size_t previous_move, Mode mode) {
        assert(cutoff_index < moves.size());
        const auto move = moves[cutoff_index];
        if (mode != Mode::ordinary || move.is_capture() || move.promotion != PieceType::none)
            return;
        if (limits.countermove_ordering && previous_move != no_previous_move) {
            countermoves[previous_move] = move;
            if (limits.diagnostics) ++countermove.updates;
        }
        auto& pair = killers[static_cast<std::size_t>(ply)];
        if (move != pair[0]) { pair[1] = pair[0]; pair[0] = move; }
        const int bonus = std::min(2048, depth * depth * 24);
        update_history(side, move, bonus);
        for (std::size_t index = 0; index < cutoff_index; ++index) {
            const auto quiet_move = moves[index];
            if (!quiet_move.is_capture() && quiet_move.promotion == PieceType::none)
                update_history(side, quiet_move, -bonus);
        }
    }

    /** Learn a separate contextual signal from the same completed quiet prefix.
     * The parent is restored before entry, so its original piece identities
     * are available even after promotions elsewhere in the tree. Never read
     * or train this table through fictional/verification/ProbCut subtrees.
     * A future skipped-move policy must pass the actual searched subset here.
     */
    void learn_continuation_cutoff(const Position& position, const std::vector<Move>& moves,
                                   std::size_t cutoff_index, int depth,
                                   std::size_t previous_move, Mode mode) {
        if (!limits.continuation_history || mode != Mode::ordinary
            || previous_move >= no_previous_move) return;
        assert(cutoff_index < moves.size());
        const auto winner = moves[cutoff_index];
        if (winner.is_capture() || winner.promotion != PieceType::none) return;
        const int bonus = std::min(2048, depth * depth * 24);
        const auto update = [&](Move move, int amount) {
            continuation_scores.update(previous_move,
                detail::ContinuationHistory::context(position.at(move.from), move.to), amount);
            if (limits.diagnostics) ++continuation.updates;
        };
        update(winner, bonus);
        for (std::size_t index = 0; index < cutoff_index; ++index) {
            const auto move = moves[index];
            if (!move.is_capture() && move.promotion == PieceType::none)
                update(move, -bonus);
        }
    }

    void update_pv(int ply, Move move) {
        const auto here = static_cast<std::size_t>(ply);
        const auto child = here + 1;
        pv[here][here] = move;
        pv_length[here] = pv_length[child];
        for (int index = ply + 1; index < pv_length[here]; ++index)
            pv[here][static_cast<std::size_t>(index)] = pv[child][static_cast<std::size_t>(index)];
    }

    int evaluate(const Position& position) {
        // An enabled tablebase result outranks any heuristic neural evaluation.
        // With no configured tables this is exactly the original score range.
        const int ceiling = shared.tablebase_limit > 0 ? tablebase_score : mate_threshold;
        return std::clamp(evaluator.evaluate(position), -ceiling + 1, ceiling - 1);
    }

    /** Captures and promotions stabilize a leaf. In check, every legal evasion
     * is searched and stand-pat is forbidden. Outside check, quiet moves only
     * need to supply a legal-move witness, not a complete list. Establish legal
     * mobility before stand-pat/draw handling so neither stalemate nor a rule-50
     * checkmate can receive an ordinary neural evaluation or draw score.
     */
    int quiescence(Position& position, int alpha, int beta, int ply, Mode mode = Mode::ordinary) {
        if (!visit(ply)) return 0;
        const bool checked = position.in_check(position.turn());
        TacticalMoveList candidates;
        if (checked) {
            candidates.moves = position.legal_moves();
            candidates.has_legal_move = !candidates.moves.empty();
        } else {
            candidates = position.legal_tactical_moves();
        }
        auto& moves = candidates.moves;
        if (!candidates.has_legal_move) return checked ? -mate_score + ply : 0;
        if (draw(position, mode)) return 0;
        if (ply >= max_ply - 1) return evaluate(position);

        const int entry_alpha = alpha;
        if (!checked) {
            const int stand_pat = evaluate(position);
            if (stand_pat >= beta) return stand_pat;
            alpha = std::max(alpha, stand_pat);
        }
        // Use the entry window: stand-pat must not turn a wide/PV window
        // into an eligible scout. Inspect material/history only after surviving
        // stand-pat, and only when the optional policy is enabled.
        bool filter_captures = false;
        if (limits.qsearch_see_pruning && mode == Mode::ordinary
            && !checked && std::int64_t(beta) - entry_alpha == 1) {
            const int band = shared.tablebase_limit > 0 ? tablebase_score : mate_threshold;
            const bool advanced = (position.pieces(Color::white, PieceType::pawn) & (Bitboard{0xffff} << 40))
                || (position.pieces(Color::black, PieceType::pawn) & (Bitboard{0xffff} << 8));
            const search_policy::QSearchSeeContext context{
                ply, checked, std::abs(entry_alpha) >= band || std::abs(beta) >= band,
                false, repeated(position), advanced, position.halfmove_clock(),
                std::popcount(position.occupied()), true};
            filter_captures = search_policy::qsearch_see_eligible(context);
        }
        order(position, moves, {}, ply);
        for (const auto move : moves) {
            int exchange = 0;
            if (filter_captures && search_policy::qsearch_see_capture(
                    move.is_capture(), move.promotion != PieceType::none,
                    (move.flags & en_passant) != 0)) {
                if (limits.diagnostics) ++qsearch_see.evaluations;
                exchange = static_exchange(position, move);
                if (must_stop()) return 0;
            }
            const auto undo = position.make_move(move);
            if (exchange < 0) {
                // Protect checking sacrifices and terminal children using real
                // legal state. No history push or NNUE evaluation occurs until
                // this decision; even a skipped probe must poll search limits.
                const bool child_check = position.in_check(position.turn());
                const bool child_has_moves = child_check || !position.legal_moves().empty();
                const bool skip = search_policy::qsearch_see_skip(
                    exchange, child_check, child_has_moves);
                const bool stopped = must_stop();
                if (skip || stopped) {
                    position.unmake_move(move, undo);
                    if (stopped) return 0;
                    if (limits.diagnostics) ++qsearch_see.pruned;
                    continue;
                }
            }
            if (mode != Mode::null_probe) game_history.push_back(position.key());
            const int score = -quiescence(position, -beta, -alpha, ply + 1, mode);
            if (mode != Mode::null_probe) game_history.pop_back();
            position.unmake_move(move, undo);
            if (aborted) return 0;
            if (score > alpha) {
                alpha = score;
                update_pv(ply, move);
                if (score >= beta) return score;
            }
        }
        return alpha;
    }

    /** Principal-variation search: only the first move needs a full window.
     * Subsequent moves first prove whether they can improve alpha; a successful
     * challenge receives a full-window re-search before becoming the PV.
     * Guarded late quiet moves scout one ply shallower by default; the optional
     * deeper tier uses two. Every reduced result above alpha must be verified at
     * ordinary depth before a cutoff or full-window search. Reduced fail-lows
     * remain heuristic and can miss tactics. Null/futility pruning stays opt-in.
     */
    int alphabeta(Position& position, int depth, int alpha, int beta, int ply,
                  bool pv_node, std::uint64_t digest,
                  std::size_t previous_move = no_previous_move, Mode mode = Mode::ordinary,
                  Move verification_hint = {}) {
        if (depth <= 0) return quiescence(position, alpha, beta, ply, mode);
        if (!visit(ply)) return 0;
        auto moves = position.legal_moves();
        const bool checked = position.in_check(position.turn());
        if (moves.empty()) return checked ? -mate_score + ply : 0;
        if (draw(position, mode)) return 0;
        if (ply >= max_ply - 1) return evaluate(position);
        if (ply == 0 && !limits.searchmoves.empty()) {
            std::erase_if(moves, [&](Move move) {
                return std::find(limits.searchmoves.begin(), limits.searchmoves.end(), move)
                    == limits.searchmoves.end();
            });
            if (moves.empty()) return 0;
        }

        alpha = std::max(alpha, -mate_score + ply);
        beta = std::min(beta, mate_score - ply - 1);
        if (alpha >= beta) return alpha;
        // Five-valued WDL is safe here only immediately after a zeroing move:
        // otherwise its theoretical win may cross the remaining rule-50 budget.
        // Terminal/mate and game-history draws were handled above. A WDL win
        // proves a lower bound, not a precise score or mating distance; a loss
        // proves an upper bound. Keep PV nodes on ordinary search and do not
        // store these direct probe bounds in the TT.
        if (mode == Mode::ordinary && shared.tablebase_limit > 0 && ply > 0 && !pv_node
            && depth >= limits.syzygy_probe_depth && position.halfmove_clock() == 0
            && position.castling_rights() == 0
            && std::popcount(position.occupied()) <= shared.tablebase_limit) {
            if (const auto wdl = shared.tablebases.probe_wdl(position)) {
                shared.tbhits.fetch_add(1, std::memory_order_relaxed);
                const int outcome = static_cast<int>(*wdl);
                if (outcome > -2 && outcome < 2) return 0;
                if (outcome == 2 && tablebase_score >= beta) return tablebase_score;
                if (outcome == -2 && -tablebase_score <= alpha) return -tablebase_score;
            }
        }
        const int original_alpha = alpha;
        // Extending only interior check nodes preserves the meaning of root depth.
        if (checked && ply > 0) ++depth;

        const auto key = table_key(position, digest);
        Move tt_move;
        // Only the legal verification root receives its ordinary caller's
        // already-copied contextual move. It conveys no bound/depth and causes
        // no TT access. Exact legal membership includes flags and promotion;
        // recursive calls omit the argument, so descendants receive no hint.
        if (mode == Mode::verification && verification_hint.valid()
            && std::find(moves.begin(), moves.end(), verification_hint) != moves.end()) {
            tt_move = verification_hint;
            if (limits.diagnostics) ++nullmove.verification_hints;
        }
        if (const auto entry = mode == Mode::ordinary ? probe(key) : std::nullopt) {
            tt_move = entry->move();
            const int score = score_from_table(entry->score, ply);
            if (!pv_node && entry->depth >= depth) {
                if (entry->bound() == Bound::exact
                    || (entry->bound() == Bound::lower && score >= beta)
                    || (entry->bound() == Bound::upper && score <= alpha)) {
                    if (limits.diagnostics) ++cache.cutoffs;
                    return score;
                }
            }
        }

        // Reverse futility is a shallow static hypothesis, not a searched
        // bound. Keep it out of root/PV/check nodes and both null subtrees.
        // Terminal/draw/tablebase/TT handling above retains precedence. The
        // quiet-position restriction deliberately excludes every legal capture
        // or promotion; quiet checks and distant threats remain heuristic risks.
        if (limits.reverse_futility_pruning && mode == Mode::ordinary
            && depth >= 1 && depth <= 3 && ply > 0 && !pv_node && !checked) {
            const auto side = position.turn();
            const auto non_pawns = position.pieces(side, PieceType::knight)
                | position.pieces(side, PieceType::bishop) | position.pieces(side, PieceType::rook)
                | position.pieces(side, PieceType::queen);
            const int band = shared.tablebase_limit > 0 ? tablebase_score : mate_threshold;
            const bool advanced = (position.pieces(Color::white, PieceType::pawn) & (Bitboard{0xffff} << 40))
                || (position.pieces(Color::black, PieceType::pawn) & (Bitboard{0xffff} << 8));
            const bool tactical = std::any_of(moves.begin(), moves.end(), [](Move move) {
                return move.is_capture() || move.promotion != PieceType::none;
            });
            const search_policy::ReverseFutilityContext context{
                depth, ply, pv_node, checked, std::abs(alpha) >= band || std::abs(beta) >= band,
                false, repeated(position), advanced, tactical, position.halfmove_clock(),
                std::popcount(non_pawns), std::popcount(position.pieces(side, PieceType::pawn)),
                std::popcount(position.occupied()), moves.size()};
            if (search_policy::reverse_futility_eligible(context)) {
                if (limits.diagnostics) ++reverse_futility.evaluations;
                const int static_score = evaluate(position);
                if (search_policy::reverse_futility_cutoff(context, static_score, beta, band)) {
                    if (limits.diagnostics) ++reverse_futility.cutoffs;
                    pv_length[static_cast<std::size_t>(ply)] = ply;
                    // Return only the window edge; neither a fabricated line
                    // nor a direct original-depth TT entry is justified. Real
                    // ancestor bounds can still depend on this heuristic.
                    return beta;
                }
            }
        }

        // A null probe is a fictional pass, never a move/history/TT entry. Its
        // complete subtree is isolated, including quiescence. A fail-high is
        // only a reason to search legal moves at reduced depth: it cannot by
        // itself authorize a cutoff or supply a score/PV to the real game.
        if (limits.null_move_pruning && mode == Mode::ordinary && depth >= 5
            && ply > 0 && !pv_node && !checked) {
            const auto side = position.turn();
            const auto non_pawns = position.pieces(side, PieceType::knight)
                | position.pieces(side, PieceType::bishop) | position.pieces(side, PieceType::rook)
                | position.pieces(side, PieceType::queen);
            const int band = shared.tablebase_limit > 0 ? tablebase_score : mate_threshold;
            const bool advanced = (position.pieces(Color::white, PieceType::pawn) & (Bitboard{0xffff} << 40))
                || (position.pieces(Color::black, PieceType::pawn) & (Bitboard{0xffff} << 8));
            const search_policy::NullMoveContext context{
                depth, ply, pv_node, checked, std::abs(alpha) >= band || std::abs(beta) >= band,
                false, repeated(position), advanced, position.halfmove_clock(),
                std::popcount(non_pawns), std::popcount(position.pieces(side, PieceType::pawn)),
                std::popcount(position.occupied()), moves.size()};
            if (search_policy::probe_null_move(context)) {
                const int static_score = evaluate(position);
                if (static_score >= beta && std::abs(static_score) < band) {
                    if (limits.diagnostics) ++nullmove.probes;
                    const auto probe_begin = nodes;
                    const auto undo = position.make_null_move();
                    int null_score;
                    try {
                        null_score = -alphabeta(position, depth - 3, -beta, -beta + 1,
                            ply + 1, false, 0, no_previous_move, Mode::null_probe);
                    } catch (...) {
                        position.unmake_null_move(undo);
                        throw;
                    }
                    position.unmake_null_move(undo);
                    if (limits.diagnostics) nullmove.probe_nodes += nodes - probe_begin;
                    pv_length[static_cast<std::size_t>(ply)] = ply;
                    if (aborted) return 0;
                    // Reject mate/tablebase-band pseudo evidence. Both passes
                    // must finish normally before the real node may fail high.
                    if (null_score >= beta && std::abs(null_score) < band) {
                        if (limits.diagnostics) { ++nullmove.fail_highs; ++nullmove.verifications; }
                        const auto verification_begin = nodes;
                        const int verified = alphabeta(position, depth - 2, beta - 1, beta,
                            ply, false, digest, previous_move, Mode::verification, tt_move);
                        if (limits.diagnostics)
                            nullmove.verification_nodes += nodes - verification_begin;
                        pv_length[static_cast<std::size_t>(ply)] = ply;
                        if (aborted) return 0;
                        if (verified >= beta && std::abs(verified) < band) {
                            if (limits.diagnostics) ++nullmove.cutoffs;
                            // Do not store a shallow heuristic as an ordinary
                            // original-depth TT bound, and never return null's score.
                            return beta;
                        }
                        if (limits.diagnostics) ++nullmove.rejected;
                    }
                }
            }
        }
        Move reply;
        if (limits.countermove_ordering && previous_move != no_previous_move) {
            reply = countermoves[previous_move];
            if (limits.diagnostics) {
                ++countermove.lookups;
                if (reply.valid() && std::find(moves.begin(), moves.end(), reply) != moves.end())
                    ++countermove.matches;
            }
        }
        // Only an exact legal-list match receives a rank. Stale suggestions
        // are never inserted, and quiescence retains its original ordering.
        const auto move_hint = ordering_move(position.key(), moves, tt_move, ply, mode);
        order(position, moves, move_hint, ply, reply,
              mode == Mode::ordinary ? previous_move : no_previous_move);

        // A tactical reduced search is only a prediction of a full-depth
        // fail-high. Keep each subtree isolated from ordinary TT bounds,
        // reductions and learned ordering state. Quiescence screens out cheap
        // failures; the second pass includes every legal quiet defense.
        if (limits.probcut && mode == Mode::ordinary && depth >= 5
            && ply > 0 && !pv_node && !checked && beta - alpha == 1) {
            const auto side = position.turn();
            const auto non_pawns = position.pieces(side, PieceType::knight)
                | position.pieces(side, PieceType::bishop) | position.pieces(side, PieceType::rook)
                | position.pieces(side, PieceType::queen);
            const int band = shared.tablebase_limit > 0 ? tablebase_score : mate_threshold;
            const int raised_beta = beta + search_policy::probcut_margin;
            const bool advanced = (position.pieces(Color::white, PieceType::pawn) & (Bitboard{0xffff} << 40))
                || (position.pieces(Color::black, PieceType::pawn) & (Bitboard{0xffff} << 8));
            const search_policy::ProbCutContext context{
                depth, ply, pv_node, checked,
                std::abs(alpha) >= band || std::abs(beta) >= band || raised_beta >= band,
                false, repeated(position), advanced, position.halfmove_clock(),
                std::popcount(non_pawns), std::popcount(position.pieces(side, PieceType::pawn)),
                std::popcount(position.occupied()), moves.size(), true};
            if (search_policy::probcut_eligible(context)) {
                if (limits.diagnostics) ++probcut.eligible_nodes;
                int examined = 0;
                for (const auto move : moves) {
                    if (!search_policy::probcut_capture(move.is_capture(),
                            move.promotion != PieceType::none, (move.flags & en_passant) != 0))
                        continue;
                    if (examined++ == search_policy::probcut_capture_limit) break;
                    if (limits.diagnostics) ++probcut.see_evaluations;
                    const int exchange = static_exchange(position, move);
                    if (must_stop()) return 0;
                    if (exchange < 0) continue;

                    const auto undo = position.make_move(move);
                    const auto history_size = game_history.size();
                    int score = 0;
                    bool searched = false;
                    try {
                        game_history.push_back(position.key());
                        if (limits.diagnostics) ++probcut.qsearches;
                        score = -quiescence(position, -raised_beta, -raised_beta + 1,
                                            ply + 1, Mode::probcut);
                        if (!aborted && score >= raised_beta && std::abs(score) < band) {
                            if (limits.diagnostics) {
                                ++probcut.qsearch_passes;
                                ++probcut.searches;
                            }
                            searched = true;
                            // Captures zero the rule-50 clock, so the real child
                            // history digest starts afresh. Probe mode cannot use
                            // the TT, but retain correct context nonetheless.
                            score = -alphabeta(position, search_policy::probcut_child_depth(depth),
                                -raised_beta, -raised_beta + 1, ply + 1, false,
                                mix(position.key()), no_previous_move, Mode::probcut);
                        }
                    } catch (...) {
                        game_history.resize(history_size);
                        position.unmake_move(move, undo);
                        pv_length[static_cast<std::size_t>(ply)] = ply;
                        throw;
                    }
                    game_history.resize(history_size);
                    position.unmake_move(move, undo);
                    pv_length[static_cast<std::size_t>(ply)] = ply;
                    if (aborted) return 0;
                    if (searched) {
                        if (score >= raised_beta && std::abs(score) < band) {
                            if (limits.diagnostics) ++probcut.cutoffs;
                            // Do not publish the elevated score, speculative PV
                            // or a direct original-depth TT entry. Ordinary
                            // ancestor bounds may still depend on this heuristic.
                            return beta;
                        }
                        if (limits.diagnostics) ++probcut.rejected;
                    }
                }
            }
        }

        int best_score = -infinity;
        Move best_move;
        std::size_t move_number = 0;
        for (const auto move : moves) {
            const auto undo = position.make_move(move);
            const auto child_context = limits.countermove_ordering || limits.continuation_history
                ? detail::ContinuationHistory::context(undo.moved, move.to)
                : no_previous_move;
            const auto child_key = position.key();
            const auto child_digest = position.halfmove_clock() == 0
                ? mix(child_key) : digest + mix(child_key);
            if (mode != Mode::null_probe) game_history.push_back(child_key);

            int score;
            if (move_number == 0) {
                score = -alphabeta(position, depth - 1, -beta, -alpha, ply + 1,
                                   pv_node, child_digest, child_context, mode);
            } else {
                int reduction = 0;
                if (limits.late_move_reductions && mode == Mode::ordinary) {
                    const search_policy::LateMoveContext context{
                        depth, ply, move_number, pv_node, checked, false,
                        std::abs(alpha) >= (shared.tablebase_limit > 0 ? tablebase_score : mate_threshold)
                            || std::abs(beta) >= (shared.tablebase_limit > 0 ? tablebase_score : mate_threshold),
                        move, undo.moved, tt_move,
                        killers[static_cast<std::size_t>(ply)][0],
                        killers[static_cast<std::size_t>(ply)][1]};
                    // Only pay for the additional attack test after all cheap
                    // parent/move guards pass; a checking child is never reduced.
                    if (search_policy::reduce_late_move(context)
                        && !position.in_check(position.turn())) {
                        reduction = 1;
                        if (limits.deep_quiet_reductions
                            && search_policy::deep_quiet_reduction(
                                context, std::popcount(position.occupied())))
                            reduction = 2;
                    }
                }
                const bool trace_deep = reduction == 2 && limits.diagnostics;
                if (reduction) ++lmr.reductions;
                if (trace_deep) ++deep_lmr.extra_reductions;
                score = -alphabeta(position, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1,
                                   false, child_digest, child_context, mode);
                if (reduction && !aborted && score > alpha) {
                    ++lmr.researches;
                    if (trace_deep) ++deep_lmr.researches;
                    // Both tiers verify directly at ordinary depth. A stopped
                    // or intermediate reduced probe never establishes a bound.
                    score = -alphabeta(position, depth - 1, -alpha - 1, -alpha, ply + 1,
                                       false, child_digest, child_context, mode);
                    if (!aborted) {
                        if (score <= alpha) {
                            ++lmr.fail_lows;
                            if (trace_deep) ++deep_lmr.fail_lows;
                        } else if (score >= beta) {
                            ++lmr.verified_cutoffs;
                            if (trace_deep) ++deep_lmr.verified_cutoffs;
                        }
                    }
                }
                if (!aborted && score > alpha && score < beta)
                    score = -alphabeta(position, depth - 1, -beta, -alpha, ply + 1,
                                       pv_node, child_digest, child_context, mode);
            }
            if (mode != Mode::null_probe) game_history.pop_back();
            position.unmake_move(move, undo);
            if (aborted) return 0;
            ++move_number;

            if (score > best_score) {
                best_score = score;
                best_move = move;
            }
            if (score > alpha) {
                alpha = score;
                update_pv(ply, move);
            }
            if (score >= beta) {
                learn_quiet_cutoff(position.turn(), moves, move_number - 1,
                                   depth, ply, previous_move, mode);
                learn_continuation_cutoff(position, moves, move_number - 1,
                                          depth, previous_move, mode);
                break;
            }
        }
        const auto bound = best_score >= beta ? Bound::lower
            : best_score > original_alpha ? Bound::exact : Bound::upper;
        // A restricted root proves bounds only over its requested subset. Never
        // publish those bounds for a later unrestricted search of this position.
        if (mode == Mode::ordinary && (ply != 0 || limits.searchmoves.empty())) {
            save(key, best_move, best_score, depth, ply, bound);
            store_move_hint(position.key(), best_move, ply, mode);
        }
        return best_score;
    }

    SearchResult run(Position position, std::vector<std::uint64_t> history,
                     const SearchLimits& request, const Reporter& report) {
        if (!network.loaded()) throw std::runtime_error("A compatible NNUE network must be loaded before search");
        // Charge the accepted command's preparation and worker-dispatch delay,
        // including policy-dependent clearing already done by the coordinator.
        // The coordinator supplies one origin for all workers. Clamping a
        // future origin prevents accidental extra budget or negative UCI time.
        const auto entered_at = Clock::now();
        const auto received_at = std::min(request.received_at.value_or(entered_at), entered_at);
        const auto search_started_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            received_at.time_since_epoch()).count();
        limits = request;
        time = allocate_time(position, limits);
        started_ns = search_started_ns;
        nodes = 0;
        completed_depth = 0;
        seldepth = 0;
        aborted = false;
        stop_reason = StopReason::depth_limit;
#ifdef CHESS0LIVE_CLOCK_TRACE
        hard_stop_ns = 0;
#endif
        lmr = {};
        lmr.enabled = limits.late_move_reductions;
        deep_lmr = {};
        deep_lmr.enabled = limits.deep_quiet_reductions;
        ordering = {};
        ordering.policy = limits.capture_ordering;
        countermove = {};
        countermove.enabled = limits.countermove_ordering;
        continuation = {};
        continuation.enabled = limits.continuation_history;
        continuation.entries = continuation_scores.entries();
        continuation.allocated_bytes = continuation_scores.allocated_bytes();
        nullmove = {};
        nullmove.enabled = limits.null_move_pruning;
        reverse_futility = {};
        reverse_futility.enabled = limits.reverse_futility_pruning;
        qsearch_see = {};
        qsearch_see.enabled = limits.qsearch_see_pruning;
        probcut = {};
        probcut.enabled = limits.probcut;
        cache = {};
        move_hints = {};
        move_hints.enabled = limits.tt_move_hints && !shared.move_hints.empty();
        if (limits.diagnostics) {
            cache.entry_bytes = sizeof(Entry);
            cache.bucket_bytes = sizeof(Bucket);
            cache.buckets = shared.table.size();
            cache.capacity = shared.table.size() * std::size_t{4};
            cache.allocated_bytes = shared.table.capacity() * sizeof(Bucket);
            move_hints.slots = shared.move_hints.size();
            move_hints.allocated_bytes = shared.move_hints.capacity() * sizeof(MoveHintEntry);
        }
        evaluator.reset();
        for (auto& side : history_score)
            for (auto& from : side)
                for (auto& score : from) score /= 2;
        continuation_scores.decay();
        killers = {};
        pv_length = {};
        game_history = std::move(history);
        if (game_history.empty() || game_history.back() != position.key())
            game_history.push_back(position.key());
        game_history.reserve(game_history.size() + max_ply);

        SearchResult result;
        // The first forecast policy is deliberately limited to ordinary clocks.
        // Fixed limits remain authoritative. Ponder searches retain the classic
        // policy even after ponderhit, so uncharged ponder iterations never seed
        // this estimator or consume the newly started clock through prediction.
        const bool forecast_active = id == 0 && limits.time_policy == TimePolicy::forecast
            && time.active && limits.movetime_ms < 0 && limits.depth == 0
            && limits.nodes == 0 && limits.mate == 0 && !limits.infinite && !limits.ponder;
        const bool measure_iterations = forecast_active || limits.diagnostics;
        time_management::IterationForecast forecast;
        double target_ms = time.soft_ms;
        if (limits.diagnostics) {
            result.diagnostics.emplace();
            result.diagnostics->iterations.reserve(max_ply - 2);
        }
        const auto finish = [&]() {
            publish_nodes();
            result.nodes = nodes;
            result.lmr = lmr;
            result.deep_lmr = deep_lmr;
            result.ordering = ordering;
            result.countermove = countermove;
            result.continuation_history = continuation;
            result.nullmove = nullmove;
            result.reverse_futility = reverse_futility;
            result.qsearch_see = qsearch_see;
            result.probcut = probcut;
            if (result.diagnostics) {
                auto& diagnostics = *result.diagnostics;
                diagnostics.policy = limits.time_policy;
                diagnostics.forecast_active = forecast_active;
                diagnostics.stop_reason = stop_reason;
                diagnostics.elapsed_ms = double(elapsed_ns(now_ns(), started_ns)) / 1000000.0;
                diagnostics.soft_ms = time.soft_ms;
                diagnostics.hard_ms = time.hard_ms;
                diagnostics.target_ms = target_ms;
                diagnostics.predicted_next_ms = forecast.predicted_next_ms();
                diagnostics.cache = cache;
                diagnostics.move_hints = move_hints;
            }
            return std::move(result);
        };
        auto root_moves = position.legal_moves();
        if (root_moves.empty()) {
            stop_reason = StopReason::terminal;
            result.score = position.in_check(position.turn()) ? -mate_score : 0;
            if (report) report({0, 0, 0, elapsed_ms(), result.score, {}, hashfull(), shared.tbhits.load()});
            return finish();
        }
        if (!limits.searchmoves.empty()) {
            std::erase_if(root_moves, [&](Move move) {
                return std::find(limits.searchmoves.begin(), limits.searchmoves.end(), move)
                    == limits.searchmoves.end();
            });
        }
        if (root_moves.empty()) { stop_reason = StopReason::terminal; return finish(); }
        result.best = root_moves.front(); // Always retain a legal move under immediate stop.
        if (draw(position)) {
            stop_reason = StopReason::draw;
            if (report) report({0, 0, 0, elapsed_ms(), 0, {result.best}, hashfull(), shared.tbhits.load()});
            return finish();
        }

        std::uint64_t digest = 0;
        const auto history_count = std::min(game_history.size(),
            std::size_t(position.halfmove_clock()) + 1);
        for (auto index = game_history.size() - history_count; index < game_history.size(); ++index)
            digest += mix(game_history[index]);

        int depth_limit = limits.depth > 0 ? std::min(limits.depth, max_ply - 2) : max_ply - 2;
        if (limits.mate > 0)
            depth_limit = std::min(depth_limit, 2 * std::min(limits.mate, max_ply / 2 - 1));
        int stable_iterations = 0;
        for (int depth = 1; depth <= depth_limit; ++depth) {
            if (must_stop()) break;
            const auto iteration_start_ns = measure_iterations ? now_ns() : 0;
            const auto iteration_start_nodes = nodes;
            seldepth = 0;
            int window = depth >= 4 ? 64 : infinity * 2;
            int score = 0;
            while (!aborted) {
                const int alpha = std::max(-infinity, result.score - window);
                const int beta = std::min(infinity, result.score + window);
                score = alphabeta(position, depth, alpha, beta, 0, true, digest);
                if (aborted || (score > alpha && score < beta)) break;
                window = std::min(infinity * 2, window * 2);
            }
            if (measure_iterations) {
                const auto iteration_end_ns = now_ns();
                const double duration_ms = double(iteration_end_ns - iteration_start_ns) / 1000000.0;
                if (!aborted && forecast_active) forecast.observe(duration_ms);
                if (result.diagnostics)
                    result.diagnostics->iterations.push_back({
                        depth, !aborted, nodes - iteration_start_nodes, duration_ms,
                        double(elapsed_ns(iteration_end_ns, started_ns)) / 1000000.0});
            }
            if (aborted) break;
            std::vector<Move> line;
            for (int index = 0; index < pv_length[0]; ++index)
                line.push_back(pv[0][static_cast<std::size_t>(index)]);
            if (line.empty()) line.push_back(result.best);
            stable_iterations = line.front() == result.best ? stable_iterations + 1 : 0;
            const int score_drop = result.score - score;
            result.best = line.front();
            result.ponder = line.size() > 1 ? line[1] : Move{};
            result.score = score;
            result.depth = depth;
            completed_depth = depth;
            result.nodes = nodes;
            publish_nodes();
            if (report) report({depth, seldepth, total_nodes(), elapsed_ms(), score, line,
                                hashfull(), shared.tbhits.load(std::memory_order_relaxed)});

            if (limits.mate > 0 && score >= mate_threshold
                && mate_score - score <= 2LL * limits.mate) {
                stop_reason = StopReason::mate_limit;
                break;
            }
            if (id == 0 && time.active && limits.movetime_ms < 0) {
                target_ms = time_management::iteration_target(
                    time.soft_ms, time.hard_ms, stable_iterations, score_drop);
                const double charged_ms = clock_elapsed_ms();
                if (charged_ms >= target_ms) { stop_reason = StopReason::soft_time; break; }
                // Forecast only potentially discarded work at the hard deadline.
                // Finishing after the soft target is permitted while the current
                // elapsed time is below it, preserving the classic soft decision.
                if (forecast_active && !forecast.should_start_next(depth, charged_ms, time.hard_ms)) {
                    stop_reason = StopReason::forecast;
                    break;
                }
            }
        }
        return finish();
    }
};

} // namespace

/** The public Search owns workers and joins every helper on both normal and
 * exceptional exits. Thread creation and reporter exceptions therefore cannot
 * leave an evaluator touching weights during a later network reload.
 */
struct Search::Impl {
    const nnue::Network& network;
    SharedSearch shared;
    std::vector<std::unique_ptr<SearchWorker>> workers;
    bool cache_policy_valid = false;
    bool previous_lmr = false;
    bool previous_deep_lmr = false;
    CaptureOrdering previous_ordering = CaptureOrdering::mvv_lva;
    bool previous_countermove = false;
    bool previous_continuation = false;
    bool previous_tt_move_hints = false;
    bool previous_nullmove = false;
    bool previous_reverse_futility = false;
    bool previous_qsearch_see = false;
    bool previous_probcut = false;
    int previous_tb_limit = 0;
    int previous_tb_depth = 1;

    explicit Impl(const nnue::Network& weights) : network(weights) {}

    void clear() {
        std::fill(shared.table.begin(), shared.table.end(), Bucket{});
        std::fill(shared.move_hints.begin(), shared.move_hints.end(), MoveHintEntry{});
        shared.generation = 0;
        for (auto& worker : workers) worker->clear();
        cache_policy_valid = false;
    }

    void set_threads(int count) {
        if (count < 1 || count > Search::max_threads)
            throw std::invalid_argument("Threads must be between 1 and 64");
        if (std::size_t(count) == workers.size()) return;
        std::vector<std::unique_ptr<SearchWorker>> replacement;
        replacement.reserve(std::size_t(count));
        for (int id = 0; id < count; ++id)
            replacement.push_back(std::make_unique<SearchWorker>(network, shared, std::size_t(id)));
        workers.swap(replacement);
        shared.threads = count;
        clear();
    }

    SearchResult run(Position position, std::vector<std::uint64_t> history,
                     const SearchLimits& limits, const Reporter& report) {
        if (!network.loaded()) throw std::runtime_error("A compatible NNUE network must be loaded before search");
        auto request = limits;
        const auto entered_at = Clock::now();
        request.received_at = std::min(request.received_at.value_or(entered_at), entered_at);
        request.syzygy_probe_limit = std::clamp(request.syzygy_probe_limit, 0, 7);
        request.syzygy_probe_depth = std::clamp(request.syzygy_probe_depth, 1, Search::max_ply);
        // Finish optional allocation before mutating shared policy or clearing
        // any current cache. Failure propagates with the previous state intact.
        // Prepare every worker's new private table before committing any of
        // them. Allocation failure must not leave only a subset enabled or
        // discard the previously trained state. These moves allocate nothing.
        std::vector<detail::ContinuationHistory> continuation_replacements;
        const bool change_continuation =
            workers.front()->continuation_scores.enabled() != request.continuation_history;
        if (change_continuation) {
            continuation_replacements.resize(workers.size());
            for (auto& replacement : continuation_replacements)
                replacement.enable(request.continuation_history);
        }
        shared.set_move_hints(request.tt_move_hints);
        if (change_continuation)
            for (std::size_t id = 0; id < workers.size(); ++id)
                std::swap(workers[id]->continuation_scores, continuation_replacements[id]);
        // Old tables from a disabling transition must not remain resident
        // throughout the next search merely because this local vector lives on.
        continuation_replacements.clear();
        shared.tablebase_limit = std::min(request.syzygy_probe_limit,
                                         int(shared.tablebases.largest()));
        if (cache_policy_valid && (request.late_move_reductions != previous_lmr
            || request.deep_quiet_reductions != previous_deep_lmr
            || request.capture_ordering != previous_ordering
            || request.countermove_ordering != previous_countermove
            || request.continuation_history != previous_continuation
            || request.tt_move_hints != previous_tt_move_hints
            || request.null_move_pruning != previous_nullmove
            || request.reverse_futility_pruning != previous_reverse_futility
            || request.qsearch_see_pruning != previous_qsearch_see
            || request.probcut != previous_probcut
            || shared.tablebase_limit != previous_tb_limit
            || request.syzygy_probe_depth != previous_tb_depth)) clear();
        previous_lmr = request.late_move_reductions;
        previous_deep_lmr = request.deep_quiet_reductions;
        previous_ordering = request.capture_ordering;
        previous_countermove = request.countermove_ordering;
        previous_continuation = request.continuation_history;
        previous_tt_move_hints = request.tt_move_hints;
        previous_nullmove = request.null_move_pruning;
        previous_reverse_futility = request.reverse_futility_pruning;
        previous_qsearch_see = request.qsearch_see_pruning;
        previous_probcut = request.probcut;
        previous_tb_limit = shared.tablebase_limit;
        previous_tb_depth = request.syzygy_probe_depth;
        cache_policy_valid = true;
        ++shared.generation;
        shared.leader_finished.store(false, std::memory_order_relaxed);
        shared.node_tickets.store(0, std::memory_order_relaxed);
        shared.tbhits.store(0, std::memory_order_relaxed);
        for (auto& counter : shared.published) counter.value.store(0, std::memory_order_relaxed);

        // Rank the complete legal root once, before dispatching SMP helpers.
        // The user's restriction is applied BEFORE choosing the best rank, so
        // even a restricted losing move remains a valid searchmoves request.
        // A repeated reversible history is conservatively left to ordinary
        // search: table files alone do not encode the game's repetition rights.
        const auto budget = allocate_time(position, request);
        const auto hit = shared.ponder_hit_ns.load(std::memory_order_relaxed);
        const auto origin = request.ponder && hit >= 0 ? hit
            : std::chrono::duration_cast<std::chrono::nanoseconds>(
                request.received_at->time_since_epoch()).count();
        const bool probe_time_available = (request.ponder && hit < 0) || !budget.active
            || double(elapsed_ns(now_ns(), origin)) / 1000000.0 < budget.hard_ms;
        if (shared.tablebase_limit > 0 && !shared.stopped.load(std::memory_order_relaxed)
            && probe_time_available && position.halfmove_clock() < 100
            && position.castling_rights() == 0 && !dead_material(position)
            && std::popcount(position.occupied()) <= shared.tablebase_limit) {
            if (history.empty() || history.back() != position.key()) history.push_back(position.key());
            const auto count = std::min(history.size(), std::size_t(position.halfmove_clock()) + 1);
            const auto first = history.end() - static_cast<std::ptrdiff_t>(count);
            bool repeated = false;
            for (auto it = first; it != history.end() && !repeated; ++it)
                repeated = std::find(first, it, *it) != it;
            auto legal = position.legal_moves();
            if (!repeated && !legal.empty()) {
                if (const auto ranked = shared.tablebases.probe_root(position, legal)) {
                    int best_rank = std::numeric_limits<int>::min();
                    std::vector<Move> allowed;
                    for (const auto& entry : *ranked) {
                        if (!request.searchmoves.empty()
                            && std::find(request.searchmoves.begin(), request.searchmoves.end(), entry.move)
                                == request.searchmoves.end()) continue;
                        if (entry.rank > best_rank) { best_rank = entry.rank; allowed.clear(); }
                        if (entry.rank == best_rank) allowed.push_back(entry.move);
                    }
                    if (!allowed.empty()) {
                        request.searchmoves = std::move(allowed);
                        shared.tbhits.fetch_add(1, std::memory_order_relaxed);
                    }
                }
            }
        }

        std::vector<std::thread> helpers;
        helpers.reserve(workers.size() - 1);
        std::exception_ptr helper_error;
        std::mutex error_mutex;
        const auto join = [&]() {
            shared.leader_finished.store(true, std::memory_order_relaxed);
            for (auto& helper : helpers) if (helper.joinable()) helper.join();
        };
        SearchResult result;
        try {
            for (std::size_t id = 1; id < workers.size(); ++id) {
                helpers.emplace_back([&, id, root = position, game = history]() mutable {
                    try { (void)workers[id]->run(std::move(root), std::move(game), request, {}); }
                    catch (...) {
                        std::lock_guard guard(error_mutex);
                        if (!helper_error) helper_error = std::current_exception();
                        shared.leader_finished.store(true, std::memory_order_relaxed);
                    }
                });
            }
            result = workers.front()->run(std::move(position), std::move(history), request, report);
#ifdef CHESS0LIVE_CLOCK_TRACE
            result.clock_trace.leader_finished_ns = now_ns();
#endif
        } catch (...) {
            join();
            throw;
        }
        join();
#ifdef CHESS0LIVE_CLOCK_TRACE
        result.clock_trace.search_started_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            entered_at.time_since_epoch()).count();
        result.clock_trace.joined_ns = now_ns();
        result.clock_trace.hard_stop_ns = workers.front()->hard_stop_ns;
        // The Search API accepts int64 millisecond clocks; this diagnostic field
        // saturates rather than overflowing when such a clock is enormous.
        const auto hard_ns = static_cast<long double>(budget.hard_ms) * 1000000.0L;
        result.clock_trace.hard_budget_ns = !budget.active ? -1
            : hard_ns >= static_cast<long double>(std::numeric_limits<std::int64_t>::max())
                ? std::numeric_limits<std::int64_t>::max()
                : static_cast<std::int64_t>(hard_ns);
#endif
        if (helper_error) std::rethrow_exception(helper_error);

        result.smp.threads = shared.threads;
        result.smp.worker_nodes.reserve(workers.size());
        result.smp.worker_depths.reserve(workers.size());
        result.nodes = 0;
        for (std::size_t id = 0; id < workers.size(); ++id) {
            const auto& worker = *workers[id];
            result.smp.worker_nodes.push_back(worker.nodes);
            result.smp.worker_depths.push_back(worker.completed_depth);
            result.nodes += worker.nodes;
            if (id == 0) continue;
            result.lmr.reductions += worker.lmr.reductions;
            result.lmr.researches += worker.lmr.researches;
            result.lmr.fail_lows += worker.lmr.fail_lows;
            result.lmr.verified_cutoffs += worker.lmr.verified_cutoffs;
            result.deep_lmr.extra_reductions += worker.deep_lmr.extra_reductions;
            result.deep_lmr.researches += worker.deep_lmr.researches;
            result.deep_lmr.fail_lows += worker.deep_lmr.fail_lows;
            result.deep_lmr.verified_cutoffs += worker.deep_lmr.verified_cutoffs;
            result.ordering.see_calls += worker.ordering.see_calls;
            result.ordering.losing_captures += worker.ordering.losing_captures;
            result.countermove.lookups += worker.countermove.lookups;
            result.countermove.matches += worker.countermove.matches;
            result.countermove.updates += worker.countermove.updates;
            result.continuation_history.entries += worker.continuation.entries;
            result.continuation_history.allocated_bytes += worker.continuation.allocated_bytes;
            result.continuation_history.lookups += worker.continuation.lookups;
            result.continuation_history.nonzero += worker.continuation.nonzero;
            result.continuation_history.updates += worker.continuation.updates;
            result.nullmove.probes += worker.nullmove.probes;
            result.nullmove.fail_highs += worker.nullmove.fail_highs;
            result.nullmove.verifications += worker.nullmove.verifications;
            result.nullmove.cutoffs += worker.nullmove.cutoffs;
            result.nullmove.rejected += worker.nullmove.rejected;
            result.nullmove.probe_nodes += worker.nullmove.probe_nodes;
            result.nullmove.verification_nodes += worker.nullmove.verification_nodes;
            result.nullmove.verification_hints += worker.nullmove.verification_hints;
            result.reverse_futility.evaluations += worker.reverse_futility.evaluations;
            result.reverse_futility.cutoffs += worker.reverse_futility.cutoffs;
            result.qsearch_see.evaluations += worker.qsearch_see.evaluations;
            result.qsearch_see.pruned += worker.qsearch_see.pruned;
            result.probcut.eligible_nodes += worker.probcut.eligible_nodes;
            result.probcut.see_evaluations += worker.probcut.see_evaluations;
            result.probcut.qsearches += worker.probcut.qsearches;
            result.probcut.qsearch_passes += worker.probcut.qsearch_passes;
            result.probcut.searches += worker.probcut.searches;
            result.probcut.cutoffs += worker.probcut.cutoffs;
            result.probcut.rejected += worker.probcut.rejected;
            if (result.diagnostics) {
                auto& cache = result.diagnostics->cache;
                cache.probes += worker.cache.probes;
                cache.hits += worker.cache.hits;
                cache.cutoffs += worker.cache.cutoffs;
                cache.stores += worker.cache.stores;
                cache.replacements += worker.cache.replacements;
                auto& hints = result.diagnostics->move_hints;
                hints.probes += worker.move_hints.probes;
                hints.hits += worker.move_hints.hits;
                hints.legal_matches += worker.move_hints.legal_matches;
                hints.stores += worker.move_hints.stores;
            }
        }
        const auto started = std::chrono::duration_cast<std::chrono::nanoseconds>(
            request.received_at->time_since_epoch()).count();
#ifdef CHESS0LIVE_CLOCK_TRACE
        result.clock_trace.accounted_ns = now_ns();
        result.time_ms = elapsed_ns(result.clock_trace.accounted_ns, started) / 1000000;
#else
        result.time_ms = elapsed_ns(now_ns(), started) / 1000000;
#endif
        result.hashfull = workers.front()->hashfull();
        result.tbhits = shared.tbhits.load(std::memory_order_relaxed);
        if (result.diagnostics)
            result.diagnostics->elapsed_ms = double(elapsed_ns(now_ns(), started)) / 1000000.0;
        return result;
    }
};

Search::Search(const nnue::Network& network, std::size_t hash_mb, int threads)
    : impl_(std::make_unique<Impl>(network)) {
    impl_->shared.resize(hash_mb);
    impl_->set_threads(threads);
}
Search::~Search() = default;

SearchResult Search::search(Position position, std::vector<std::uint64_t> history,
                            const SearchLimits& limits, Reporter report) {
    return impl_->run(std::move(position), std::move(history), limits, report);
}
void Search::reset_stop() {
    impl_->shared.stopped.store(false, std::memory_order_relaxed);
    impl_->shared.ponder_hit_ns.store(-1, std::memory_order_relaxed);
}
void Search::stop() noexcept { impl_->shared.stopped.store(true, std::memory_order_relaxed); }
void Search::ponderhit() noexcept {
    std::int64_t expected = -1;
    impl_->shared.ponder_hit_ns.compare_exchange_strong(expected, now_ns(), std::memory_order_relaxed);
}
void Search::clear() { impl_->clear(); }
void Search::set_hash(std::size_t megabytes) { impl_->shared.resize(megabytes); }
void Search::set_threads(int threads) { impl_->set_threads(threads); }
bool Search::set_syzygy_path(const std::string& path, std::string& error) {
    impl_->clear();
    return impl_->shared.tablebases.set_path(path, error);
}
unsigned Search::syzygy_largest() const { return impl_->shared.tablebases.largest(); }

} // namespace chess0live
