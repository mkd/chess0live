/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Exercise worker-private ordering without adding a production test API.
// Link position/NNUE/exchange/tablebase objects, but not search.o. No evaluator
// is invoked: an unloaded network is sufficient for the worker constructor.
#include "../src/search.cpp"

#include <iostream>
#include <memory>
#include <string_view>

namespace {
using namespace chess0live;
std::size_t comparisons = 0;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    const auto result = Position::from_fen(text, error);
    if (!result) throw std::runtime_error("Fixture FEN: " + error);
    return *result;
}

Move move(Position position, std::string_view text) {
    const auto result = parse_uci_move(position, text);
    if (!result) throw std::runtime_error("Fixture move: " + std::string(text));
    return *result;
}

/** Frozen pre-optimization scoring and comparator, intentionally independent
 * of production ordering_score/tie_before. This checks the complete sorted
 * sequence, not just the winner or a coincidentally unchanged search value.
 */
int old_score(const SearchWorker& worker, const Position& position, Move value,
              Move tt, int ply, Move reply) {
    constexpr std::array<int, 7> values{0, 100, 320, 330, 500, 900, 20000};
    if (value == tt) return 2000000;
    if (value.promotion != PieceType::none)
        return 1200000 + values[static_cast<unsigned>(value.promotion)];
    if (value.is_capture()) {
        const int victim = value.flags & en_passant ? 100
            : values[static_cast<unsigned>(type_of(position.at(value.to)))];
        return 1000000 + 16 * victim
            - values[static_cast<unsigned>(type_of(position.at(value.from)))];
    }
    if (value == worker.killers[static_cast<std::size_t>(ply)][0]) return 900000;
    if (value == worker.killers[static_cast<std::size_t>(ply)][1]) return 800000;
    if (value == reply) return 700000;
    return worker.history_score[static_cast<unsigned>(position.turn())][value.from][value.to];
}

bool old_tie(std::size_t id, Move left, Move right, int ply) {
    if (id != 0 && ply == 0) {
        const auto key = [id](Move value) {
            auto bits = std::uint64_t(value.from) * 64 + value.to + 4096 * id
                + 65536 * static_cast<unsigned>(value.promotion);
            bits ^= bits >> 30;
            bits *= 0xbf58476d1ce4e5b9ULL;
            bits ^= bits >> 27;
            bits *= 0x94d049bb133111ebULL;
            return bits ^ (bits >> 31);
        };
        if (key(left) != key(right)) return key(left) < key(right);
    }
    if (left.from != right.from) return left.from < right.from;
    if (left.to != right.to) return left.to < right.to;
    return left.promotion < right.promotion;
}

std::vector<Move> old_order(const SearchWorker& worker, const Position& position,
                           std::vector<Move> moves, Move tt, int ply, Move reply,
                           OrderingStatistics& delta) {
    if (worker.limits.capture_ordering == CaptureOrdering::see) {
        struct Ranked { Move move; int score; };
        std::vector<Ranked> ranked;
        for (const auto value : moves) {
            int score = old_score(worker, position, value, tt, ply, reply);
            if (value != tt && value.is_capture() && value.promotion == PieceType::none) {
                ++delta.see_calls;
                if (static_exchange(position, value) < 0) {
                    ++delta.losing_captures;
                    score -= 2000000;
                }
            }
            ranked.push_back({value, score});
        }
        std::sort(ranked.begin(), ranked.end(), [&](const Ranked& a, const Ranked& b) {
            return a.score != b.score ? a.score > b.score : old_tie(worker.id, a.move, b.move, ply);
        });
        std::transform(ranked.begin(), ranked.end(), moves.begin(), [](const Ranked& r) { return r.move; });
    } else {
        std::sort(moves.begin(), moves.end(), [&](Move a, Move b) {
            const int first = old_score(worker, position, a, tt, ply, reply);
            const int second = old_score(worker, position, b, tt, ply, reply);
            return first != second ? first > second : old_tie(worker.id, a, b, ply);
        });
    }
    return moves;
}

std::vector<Move> check(SearchWorker& worker, const Position& position,
                        std::vector<Move> moves, Move tt = {}, int ply = 0, Move reply = {}) {
    const auto before = position;
    const auto history = worker.history_score;
    const auto killers = worker.killers;
    const auto replies = worker.countermoves;
    const auto game = worker.game_history;
    const auto counters = worker.ordering;
    OrderingStatistics delta;
    const auto expected = old_order(worker, position, moves, tt, ply, reply, delta);
    worker.order(position, moves, tt, ply, reply);
    require(moves == expected, "Ordered move sequence or flags differ from previous implementation");
    require(worker.ordering.see_calls == counters.see_calls + delta.see_calls
            && worker.ordering.losing_captures == counters.losing_captures + delta.losing_captures
            && worker.ordering.policy == counters.policy, "SEE counter deltas changed");
    require(worker.history_score == history && worker.killers == killers
            && worker.countermoves == replies && worker.game_history == game,
            "Ordering changed learned state or game history");
    require(position.fen() == before.fen() && position.key() == before.key()
            && position.occupied() == before.occupied(), "Ordering changed position state");
    for (int square = 0; square < 64; ++square)
        require(position.at(square) == before.at(square), "Ordering changed a square");
    for (const auto side : {Color::white, Color::black}) {
        require(position.king_square(side) == before.king_square(side), "Ordering changed king location");
        for (unsigned type = 1; type <= 6; ++type)
            require(position.pieces(side, static_cast<PieceType>(type))
                    == before.pieces(side, static_cast<PieceType>(type)), "Ordering changed a bitboard");
    }
    ++comparisons;
    return moves;
}

void priorities_and_reuse(SearchWorker& worker) {
    auto position = Position::start();
    worker.clear();
    const auto tt = move(position, "h2h3"), first = move(position, "g2g3");
    const auto second = move(position, "f2f3"), reply = move(position, "e2e4");
    const auto positive = move(position, "d2d3"), zero = move(position, "c2c3");
    const auto negative = move(position, "b2b3");
    const std::vector<Move> input{negative, zero, positive, reply, second, first, tt};
    worker.killers[0] = {first, second};
    worker.history_score[0][positive.from][positive.to] = 16384;
    worker.history_score[0][negative.from][negative.to] = -16384;
    const std::vector<Move> expected{tt, first, second, reply, positive, zero, negative};
    require(check(worker, position, input, tt, 0, reply) == expected, "Priority tiers changed");

    // Earlier output belongs to its caller, even after different-sized sorts
    // and score changes. This models a parent move list surviving child orders.
    auto parent = check(worker, position, input, tt, 0, reply);
    const auto capacity = worker.ranked_moves.capacity();
    const auto* storage = worker.ranked_moves.data();
    check(worker, position, {});
    check(worker, position, {zero});
    require(worker.ranked_moves.capacity() == capacity && worker.ranked_moves.data() == storage,
            "Smaller ordering calls discarded reusable worker storage");
    check(worker, position, position.legal_moves()); // Grow beyond the seven-move parent list.
    worker.killers[0] = {};
    worker.history_score[0][negative.from][negative.to] = 16384;
    worker.history_score[0][positive.from][positive.to] = -16384;
    require(check(worker, position, input).front() == negative, "Scores were reused after history changed");
    require(parent == expected, "Worker scratch overwrote a caller's earlier move list");
    worker.killers[0] = {tt, tt};
    require(check(worker, position, input, tt, 0, tt).front() == tt, "TT overlap lost precedence");

    // e2e4 carries double_push; an identical coordinate with wrong flags is a
    // stale suggestion, not an exact TT/killer/reply match and never inserted.
    auto stale = reply;
    stale.flags = quiet;
    worker.killers[0] = {stale, stale};
    const auto ordered = check(worker, position, input, stale, 0, stale);
    require(ordered.front() == negative && std::find(ordered.begin(), ordered.end(), stale) == ordered.end(),
            "Stale suggestion matched by coordinates or was inserted");
}

void exchange_boundaries(SearchWorker& worker) {
    worker.clear();
    auto position = fen("6k1/8/4p3/3p4/8/8/8/3Q2K1 w - - 0 1");
    const auto losing = move(position, "d1d5"), quiet_move = move(position, "g1h1");
    require(static_exchange(position, losing) < 0, "Expected a losing capture fixture");
    worker.history_score[0][quiet_move.from][quiet_move.to] = -16384;
    worker.limits.capture_ordering = CaptureOrdering::mvv_lva;
    require(check(worker, position, {quiet_move, losing}).front() == losing, "MVV-LVA capture priority changed");
    worker.limits.capture_ordering = CaptureOrdering::see;
    require(check(worker, position, {losing, quiet_move}).front() == quiet_move, "Losing capture outranked quiet history");
    check(worker, position, {losing}); // Still calls SEE once with no sort comparisons.
    const auto calls = worker.ordering.see_calls;
    require(check(worker, position, {quiet_move, losing}, losing).front() == losing
            && worker.ordering.see_calls == calls, "TT capture was demoted or evaluated by SEE");

    // Exactly zero must not be grouped with negative exchanges; either policy
    // keeps nonlosing captures ahead of a maximally rewarded quiet move.
    for (const auto text : {"6k1/8/4p3/3p4/4P3/8/8/6K1 w - - 0 1",
                            "6k1/8/8/3p4/4P3/8/8/6K1 w - - 0 1"}) {
        position = fen(text);
        const auto capture_move = move(position, "e4d5");
        require(static_exchange(position, capture_move) == (position.at(44) ? 0 : 100),
                "Expected zero/winning exchange fixtures");
        worker.history_score[0][quiet_move.from][quiet_move.to] = 16384;
        require(check(worker, position, {quiet_move, capture_move}).front() == capture_move,
                "Nonlosing capture was demoted");
    }
}

void differential_cases(SearchWorker& worker) {
    std::vector<Position> positions{Position::start()};
    for (const auto text : {
            "6k1/8/4p3/3p4/8/8/8/3Q2K1 w - - 0 1",
            "3q2k1/8/8/8/3P4/4P3/8/6K1 b - - 0 1",
            "7k/8/8/3pP3/8/8/8/K7 w - d6 0 1",
            "7k/8/8/8/3Pp3/8/8/K7 b - d3 0 1",
            "r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/1p6/R3K3 b - - 0 1",
            "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
            "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1"}) positions.push_back(fen(text));
    for (auto& position : positions) {
        const auto full = position.legal_moves();
        require(!full.empty(), "Expected playable ordering fixture");
        for (const auto policy : {CaptureOrdering::mvv_lva, CaptureOrdering::see})
            for (const int ply : {0, 7})
                for (const bool learned : {false, true}) {
                    worker.clear();
                    worker.limits.capture_ordering = policy;
                    worker.ordering = {policy, 0, 0};
                    worker.game_history = {position.key()};
                    Move tt, reply;
                    if (learned) {
                        for (unsigned side = 0; side < 2; ++side)
                            for (unsigned from = 0; from < 64; ++from)
                                for (unsigned to = 0; to < 64; ++to)
                                    worker.history_score[side][from][to]
                                        = int(((from * 64 + to + side) * 47) % 32769) - 16384;
                        tt = full.front();
                        worker.killers[static_cast<std::size_t>(ply)] = {full[full.size() / 2], full.back()};
                        reply = full[full.size() / 3];
                        worker.countermoves[0] = reply;
                    }
                    auto input = full;
                    for (int permutation = 0; permutation < 3; ++permutation) {
                        check(worker, position, input, tt, ply, reply);
                        std::reverse(input.begin(), input.end());
                        if (permutation == 1) std::rotate(input.begin(), input.begin() + input.size() / 3, input.end());
                    }
                    std::erase_if(input, [](Move value) {
                        return !value.is_capture() && value.promotion == PieceType::none;
                    });
                    check(worker, position, input, tt, ply, reply);
                    check(worker, position, {}, tt, ply, reply);
                    for (const auto value : input) check(worker, position, {value}, tt, ply, reply);
                }
    }
}
} // namespace

int main() {
    try {
        nnue::Network network;
        auto shared = std::make_unique<SharedSearch>();
        for (const std::size_t id : {0U, 1U, 3U, 9U}) {
            auto worker = std::make_unique<SearchWorker>(network, *shared, id);
            priorities_and_reuse(*worker);
            exchange_boundaries(*worker);
            differential_cases(*worker);
        }
        std::cout << "Ordering parity checks passed: " << comparisons << " comparisons\n";
    } catch (const std::exception& error) {
        std::cerr << "Ordering test failed: " << error.what() << '\n';
        return 1;
    }
}
