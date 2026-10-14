/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/search.hpp"

#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace chess0live {
namespace {

using Clock = std::chrono::steady_clock;
constexpr int infinity = 32000;
constexpr int history_limit = 16384;
constexpr std::array<int, 7> piece_order_value{0, 100, 320, 330, 500, 900, 20000};

/** Stable-clock ticks, used only for elapsed durations, never wall-clock time. */
std::int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count();
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

enum class Bound : std::uint8_t { empty, exact, lower, upper };

/** A table is owned by exactly one searching thread. There are no concurrent
 * non-atomic reads/writes, torn entries, or locks on the node-search hot path.
 * Public resizing and clearing require the controller to join the worker first.
 */
struct Entry {
    std::uint64_t key = 0;
    Move move;
    std::int16_t score = 0;
    std::int16_t depth = 0;
    Bound bound = Bound::empty;
    std::uint8_t generation = 0;
};
struct Bucket { std::array<Entry, 4> entries; };

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

} // namespace

struct Search::Impl {
    const nnue::Network& network;
    nnue::Evaluator evaluator;
    std::atomic<bool> stopped{false};
    std::atomic<std::int64_t> ponder_hit_ns{-1};
    std::vector<Bucket> table;
    std::uint8_t generation = 0;
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

    explicit Impl(const nnue::Network& weights) : network(weights), evaluator(weights) {}

    void resize(std::size_t megabytes) {
        if (megabytes == 0 || megabytes > std::numeric_limits<std::size_t>::max() / (1024 * 1024))
            throw std::invalid_argument("Hash must be a positive, representable number of megabytes");
        const auto count = std::bit_floor(megabytes * 1024 * 1024 / sizeof(Bucket));
        std::vector<Bucket> replacement(count);
        table.swap(replacement);
    }

    std::int64_t elapsed_ms() const { return (now_ns() - started_ns) / 1000000; }

    /** No timing budget is consumed while awaiting the opponent's ponder move.
     * Atomic timestamp publication also handles ponderhit before worker startup.
     */
    double clock_elapsed_ms() const {
        auto from = started_ns;
        if (limits.ponder) {
            from = ponder_hit_ns.load(std::memory_order_relaxed);
            if (from < 0) return -1.0;
        }
        return double(now_ns() - from) / 1000000.0;
    }

    bool must_stop() {
        if (aborted) return true;
        if (stopped.load(std::memory_order_relaxed)) stop_reason = StopReason::external_stop;
        else if (limits.nodes && nodes >= limits.nodes) stop_reason = StopReason::node_limit;
        else if (time.active && clock_elapsed_ms() >= time.hard_ms) stop_reason = StopReason::hard_time;
        else return false;
        aborted = true;
        return true;
    }

    bool visit(int ply) {
        if (must_stop()) return false;
        ++nodes;
        seldepth = std::max(seldepth, ply);
        pv_length[static_cast<std::size_t>(ply)] = ply;
        return true;
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

    const Entry* probe(std::uint64_t key) const {
        const auto& bucket = table[static_cast<std::size_t>(key) & (table.size() - 1)];
        for (const auto& entry : bucket.entries)
            if (entry.bound != Bound::empty && entry.key == key) return &entry;
        return nullptr;
    }

    void save(std::uint64_t key, Move move, int score, int depth, int ply, Bound bound) {
        auto& entries = table[static_cast<std::size_t>(key) & (table.size() - 1)].entries;
        Entry* victim = &entries.front();
        int lowest_quality = std::numeric_limits<int>::max();
        for (auto& entry : entries) {
            if (entry.bound == Bound::empty || entry.key == key) {
                victim = &entry;
                break;
            }
            const int age = static_cast<std::uint8_t>(generation - entry.generation);
            const int quality = int(entry.depth) - 8 * age;
            if (quality < lowest_quality) {
                lowest_quality = quality;
                victim = &entry;
            }
        }
        // Keep a deeper exact result while still refreshing its useful move.
        if (victim->bound == Bound::exact && victim->key == key
            && victim->depth > depth && bound != Bound::exact) {
            victim->generation = generation;
            return;
        }
        *victim = {key, move, static_cast<std::int16_t>(score_to_table(score, ply)),
                   static_cast<std::int16_t>(depth), bound, generation};
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

    void order(const Position& position, std::vector<Move>& moves, Move tt_move, int ply) const {
        std::sort(moves.begin(), moves.end(), [&](Move left, Move right) {
            const auto left_score = ordering_score(position, left, tt_move, ply);
            const auto right_score = ordering_score(position, right, tt_move, ply);
            // Tie-breaking makes benchmark searches reproducible across libraries.
            if (left_score != right_score) return left_score > right_score;
            if (left.from != right.from) return left.from < right.from;
            if (left.to != right.to) return left.to < right.to;
            return left.promotion < right.promotion;
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
        // Evaluation values can never collide with the mate-distance score band.
        return std::clamp(evaluator.evaluate(position), -mate_threshold + 1, mate_threshold - 1);
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
     * There is no unverified null-move, futility, or late-move pruning in v0.1.
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
        const int original_alpha = alpha;
        // Extending only interior check nodes preserves the meaning of root depth.
        if (checked && ply > 0) ++depth;

        const auto key = table_key(position, digest);
        Move tt_move;
        if (const auto* entry = probe(key)) {
            tt_move = entry->move;
            const int score = score_from_table(entry->score, ply);
            if (!pv_node && entry->depth >= depth) {
                if (entry->bound == Bound::exact
                    || (entry->bound == Bound::lower && score >= beta)
                    || (entry->bound == Bound::upper && score <= alpha)) return score;
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
                score = -alphabeta(position, depth - 1, -alpha - 1, -alpha, ply + 1,
                                   false, child_digest);
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
        limits = request;
        time = allocate_time(position, limits);
        started_ns = now_ns();
        nodes = 0;
        seldepth = 0;
        aborted = false;
        stop_reason = StopReason::depth_limit;
        evaluator.reset();
        ++generation;
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
        const bool forecast_active = limits.time_policy == TimePolicy::forecast
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
            result.nodes = nodes;
            if (result.diagnostics) {
                auto& diagnostics = *result.diagnostics;
                diagnostics.policy = limits.time_policy;
                diagnostics.forecast_active = forecast_active;
                diagnostics.stop_reason = stop_reason;
                diagnostics.elapsed_ms = double(now_ns() - started_ns) / 1000000.0;
                diagnostics.soft_ms = time.soft_ms;
                diagnostics.hard_ms = time.hard_ms;
                diagnostics.target_ms = target_ms;
                diagnostics.predicted_next_ms = forecast.predicted_next_ms();
            }
            return std::move(result);
        };
        auto root_moves = position.legal_moves();
        if (root_moves.empty()) {
            stop_reason = StopReason::terminal;
            result.score = position.in_check(position.turn()) ? -mate_score : 0;
            if (report) report({0, 0, 0, elapsed_ms(), result.score, {}});
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
            if (report) report({0, 0, 0, elapsed_ms(), 0, {result.best}});
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
                        double(iteration_end_ns - started_ns) / 1000000.0});
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
            result.nodes = nodes;
            if (report) report({depth, seldepth, nodes, elapsed_ms(), score, line});

            if (limits.mate > 0 && score >= mate_threshold
                && mate_score - score <= 2LL * limits.mate) {
                stop_reason = StopReason::mate_limit;
                break;
            }
            if (time.active && limits.movetime_ms < 0) {
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

Search::Search(const nnue::Network& network, std::size_t hash_mb, int threads)
    : impl_(std::make_unique<Impl>(network)) {
    if (threads != 1) throw std::invalid_argument("This baseline currently supports one search thread");
    impl_->resize(hash_mb);
}
Search::~Search() = default;

SearchResult Search::search(Position position, std::vector<std::uint64_t> history,
                            const SearchLimits& limits, Reporter report) {
    return impl_->run(std::move(position), std::move(history), limits, report);
}
void Search::reset_stop() {
    impl_->stopped.store(false, std::memory_order_relaxed);
    impl_->ponder_hit_ns.store(-1, std::memory_order_relaxed);
}
void Search::stop() noexcept { impl_->stopped.store(true, std::memory_order_relaxed); }
void Search::ponderhit() noexcept {
    std::int64_t expected = -1;
    impl_->ponder_hit_ns.compare_exchange_strong(expected, now_ns(), std::memory_order_relaxed);
}
void Search::clear() {
    std::fill(impl_->table.begin(), impl_->table.end(), Bucket{});
    impl_->history_score = {};
    impl_->killers = {};
    impl_->generation = 0;
    impl_->evaluator.reset();
}
void Search::set_hash(std::size_t megabytes) { impl_->resize(megabytes); }

} // namespace chess0live
