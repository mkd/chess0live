/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/search.hpp"

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
    const double hard = std::min(available, std::max(soft + 5.0, soft * 4.0));
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
        table.swap(replacement);
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
    OrderingStatistics ordering;
    CacheStatistics cache;
    int completed_depth = 0;

    SearchWorker(const nnue::Network& weights, SharedSearch& state, std::size_t index)
        : network(weights), evaluator(weights), shared(state), id(index) {}

    /** Search-policy changes cannot reuse heuristic bounds or move histories
     * from another policy. Do not clear the externally published stop flag.
     */
    void clear() {
        history_score = {};
        killers = {};
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
        else if (time.active && clock_elapsed_ms() >= time.hard_ms) stop_reason = StopReason::hard_time;
        else return false;
        aborted = true;
        return true;
    }

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

    bool draw(const Position& position) const {
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

    /** UCI hashfull is a cheap generation-local occupancy sample. Sampling is
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
                occupied += entry.bound() != Bound::empty && entry.generation == shared.generation;
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

    int ordering_score(const Position& position, Move move, Move tt_move, int ply) const {
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
        return history_score[static_cast<unsigned>(position.turn())][move.from][move.to];
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

    void order(const Position& position, std::vector<Move>& moves, Move tt_move, int ply) {
        if (limits.capture_ordering == CaptureOrdering::see) {
            struct RankedMove { Move move; int score; };
            std::vector<RankedMove> ranked;
            ranked.reserve(moves.size());
            // Compute each exchange once, never in the sort comparator. Only
            // losing ordinary captures change rank: they follow every quiet
            // history score, while TT moves and all promotions retain priority.
            for (const auto move : moves) {
                auto score = ordering_score(position, move, tt_move, ply);
                if (move != tt_move && move.is_capture() && move.promotion == PieceType::none) {
                    ++ordering.see_calls;
                    if (static_exchange(position, move) < 0) {
                        ++ordering.losing_captures;
                        score -= 2000000;
                    }
                }
                ranked.push_back({move, score});
            }
            std::sort(ranked.begin(), ranked.end(), [&](const RankedMove& left, const RankedMove& right) {
                if (left.score != right.score) return left.score > right.score;
                return tie_before(left.move, right.move, ply);
            });
            std::transform(ranked.begin(), ranked.end(), moves.begin(),
                           [](const RankedMove& ranked_move) { return ranked_move.move; });
            return;
        }
        // Preserve the baseline's ordering and ties exactly when SEE is off.
        std::sort(moves.begin(), moves.end(), [&](Move left, Move right) {
            const auto left_score = ordering_score(position, left, tt_move, ply);
            const auto right_score = ordering_score(position, right, tt_move, ply);
            // Tie-breaking makes benchmark searches reproducible across libraries.
            if (left_score != right_score) return left_score > right_score;
            return tie_before(left, right, ply);
        });
    }

    void update_history(Color side, Move move, int bonus) {
        auto& value = history_score[static_cast<unsigned>(side)][move.from][move.to];
        bonus = std::clamp(bonus, -history_limit, history_limit);
        value += bonus - value * std::abs(bonus) / history_limit;
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
     * is searched and stand-pat is forbidden. Legal moves are generated before
     * stand-pat/draw handling so neither stalemate nor a rule-50 checkmate can
     * accidentally receive an ordinary neural evaluation or draw score.
     */
    int quiescence(Position& position, int alpha, int beta, int ply) {
        if (!visit(ply)) return 0;
        auto moves = position.legal_moves();
        const bool checked = position.in_check(position.turn());
        if (moves.empty()) return checked ? -mate_score + ply : 0;
        if (draw(position)) return 0;
        if (ply >= max_ply - 1) return evaluate(position);

        if (!checked) {
            const int stand_pat = evaluate(position);
            if (stand_pat >= beta) return stand_pat;
            alpha = std::max(alpha, stand_pat);
            std::erase_if(moves, [](Move move) {
                return !move.is_capture() && move.promotion == PieceType::none;
            });
        }
        order(position, moves, {}, ply);
        for (const auto move : moves) {
            const auto undo = position.make_move(move);
            game_history.push_back(position.key());
            const int score = -quiescence(position, -beta, -alpha, ply + 1);
            game_history.pop_back();
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
     * The optional late-move experiment first scouts selected quiet moves one
     * ply shallower. Every reduced result above alpha must be verified at its
     * ordinary depth before causing a cutoff or entering a full-window search.
     * Reduced fail-lows are heuristic and may miss tactics; the default search
     * remains unreduced, with no null-move or futility pruning.
     */
    int alphabeta(Position& position, int depth, int alpha, int beta, int ply,
                  bool pv_node, std::uint64_t digest) {
        if (depth <= 0) return quiescence(position, alpha, beta, ply);
        if (!visit(ply)) return 0;
        auto moves = position.legal_moves();
        const bool checked = position.in_check(position.turn());
        if (moves.empty()) return checked ? -mate_score + ply : 0;
        if (draw(position)) return 0;
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
        if (shared.tablebase_limit > 0 && ply > 0 && !pv_node
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
        if (const auto entry = probe(key)) {
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
        order(position, moves, tt_move, ply);

        int best_score = -infinity;
        Move best_move;
        std::vector<Move> searched_quiets;
        searched_quiets.reserve(moves.size());
        std::size_t move_number = 0;
        for (const auto move : moves) {
            const auto undo = position.make_move(move);
            const auto child_key = position.key();
            const auto child_digest = position.halfmove_clock() == 0
                ? mix(child_key) : digest + mix(child_key);
            game_history.push_back(child_key);

            int score;
            if (move_number == 0) {
                score = -alphabeta(position, depth - 1, -beta, -alpha, ply + 1,
                                   pv_node, child_digest);
            } else {
                bool reduce = false;
                if (limits.late_move_reductions) {
                    const search_policy::LateMoveContext context{
                        depth, ply, move_number, pv_node, checked, false,
                        std::abs(alpha) >= (shared.tablebase_limit > 0 ? tablebase_score : mate_threshold)
                            || std::abs(beta) >= (shared.tablebase_limit > 0 ? tablebase_score : mate_threshold),
                        move, undo.moved, tt_move,
                        killers[static_cast<std::size_t>(ply)][0],
                        killers[static_cast<std::size_t>(ply)][1]};
                    // Only pay for the additional attack test after all cheap
                    // parent/move guards pass; a checking child is never reduced.
                    reduce = search_policy::reduce_late_move(context)
                        && !position.in_check(position.turn());
                }
                if (reduce) ++lmr.reductions;
                score = -alphabeta(position, depth - 1 - int(reduce), -alpha - 1, -alpha, ply + 1,
                                   false, child_digest);
                if (reduce && !aborted && score > alpha) {
                    ++lmr.researches;
                    score = -alphabeta(position, depth - 1, -alpha - 1, -alpha, ply + 1,
                                       false, child_digest);
                    if (!aborted) {
                        if (score <= alpha) ++lmr.fail_lows;
                        else if (score >= beta) ++lmr.verified_cutoffs;
                    }
                }
                if (!aborted && score > alpha && score < beta)
                    score = -alphabeta(position, depth - 1, -beta, -alpha, ply + 1,
                                       pv_node, child_digest);
            }
            game_history.pop_back();
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
                if (!move.is_capture() && move.promotion == PieceType::none) {
                    auto& pair = killers[static_cast<std::size_t>(ply)];
                    if (move != pair[0]) { pair[1] = pair[0]; pair[0] = move; }
                    const int bonus = std::min(2048, depth * depth * 24);
                    update_history(position.turn(), move, bonus);
                    for (const auto quiet_move : searched_quiets)
                        update_history(position.turn(), quiet_move, -bonus);
                }
                break;
            }
            if (!move.is_capture() && move.promotion == PieceType::none)
                searched_quiets.push_back(move);
        }
        const auto bound = best_score >= beta ? Bound::lower
            : best_score > original_alpha ? Bound::exact : Bound::upper;
        // A restricted root proves bounds only over its requested subset. Never
        // publish those bounds for a later unrestricted search of this position.
        if (ply != 0 || limits.searchmoves.empty())
            save(key, best_move, best_score, depth, ply, bound);
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
        lmr = {};
        lmr.enabled = limits.late_move_reductions;
        ordering = {};
        ordering.policy = limits.capture_ordering;
        cache = {};
        if (limits.diagnostics) {
            cache.entry_bytes = sizeof(Entry);
            cache.bucket_bytes = sizeof(Bucket);
            cache.buckets = shared.table.size();
            cache.capacity = shared.table.size() * std::size_t{4};
            cache.allocated_bytes = shared.table.capacity() * sizeof(Bucket);
        }
        evaluator.reset();
        for (auto& side : history_score)
            for (auto& from : side)
                for (auto& score : from) score /= 2;
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
            result.ordering = ordering;
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
    CaptureOrdering previous_ordering = CaptureOrdering::mvv_lva;
    int previous_tb_limit = 0;
    int previous_tb_depth = 1;

    explicit Impl(const nnue::Network& weights) : network(weights) {}

    void clear() {
        std::fill(shared.table.begin(), shared.table.end(), Bucket{});
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
        shared.tablebase_limit = std::min(request.syzygy_probe_limit,
                                         int(shared.tablebases.largest()));
        if (cache_policy_valid && (request.late_move_reductions != previous_lmr
            || request.capture_ordering != previous_ordering
            || shared.tablebase_limit != previous_tb_limit
            || request.syzygy_probe_depth != previous_tb_depth)) clear();
        previous_lmr = request.late_move_reductions;
        previous_ordering = request.capture_ordering;
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
        } catch (...) {
            join();
            throw;
        }
        join();
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
            result.ordering.see_calls += worker.ordering.see_calls;
            result.ordering.losing_captures += worker.ordering.losing_captures;
            if (result.diagnostics) {
                auto& cache = result.diagnostics->cache;
                cache.probes += worker.cache.probes;
                cache.hits += worker.cache.hits;
                cache.cutoffs += worker.cache.cutoffs;
                cache.stores += worker.cache.stores;
                cache.replacements += worker.cache.replacements;
            }
        }
        const auto started = std::chrono::duration_cast<std::chrono::nanoseconds>(
            request.received_at->time_since_epoch()).count();
        result.time_ms = elapsed_ns(now_ns(), started) / 1000000;
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
