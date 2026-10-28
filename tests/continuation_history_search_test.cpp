/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Exercise private learning/mode boundaries without exposing a production API.
// Link Position/NNUE/exchange/tablebase objects, but never search.o as well.
#include "../src/search.cpp"

#include <cstdlib>
#include <iostream>
#include <new>
#include <numeric>
#include <string_view>

namespace allocation_fault {
// Fail a chosen matching allocation on the calling thread. This lets the test
// reach the fourth worker's preparation without exhausting real host memory.
thread_local std::size_t bytes = 0;
thread_local unsigned remaining = 0;
void arm(std::size_t size, unsigned ordinal = 1) { bytes = size; remaining = ordinal; }
void disarm() { bytes = 0; remaining = 0; }
}
void* operator new(std::size_t size) {
    if (size != 0 && size == allocation_fault::bytes && --allocation_fault::remaining == 0) {
        allocation_fault::bytes = 0;
        throw std::bad_alloc{};
    }
    if (void* pointer = std::malloc(size == 0 ? 1 : size)) return pointer;
    throw std::bad_alloc{};
}
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
    try { return ::operator new(size); } catch (...) { return nullptr; }
}
void* operator new[](std::size_t size, const std::nothrow_t&) noexcept {
    try { return ::operator new[](size); } catch (...) { return nullptr; }
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }
void operator delete[](void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }

namespace {
using namespace chess0live;
using History = detail::ContinuationHistory;
using Mode = SearchWorker::Mode;
constexpr auto contexts = History::context_count;
constexpr auto table_entries = contexts * contexts;
constexpr auto table_bytes = table_entries * sizeof(std::int16_t);
std::size_t checks = 0, injected_failures = 0;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}
Position fen(std::string_view value) {
    std::string error;
    auto position = Position::from_fen(value, error);
    if (!position) throw std::runtime_error("Fixture FEN: " + error);
    return *position;
}
Move move(Position position, std::string_view coordinate) {
    auto parsed = parse_uci_move(position, coordinate);
    if (!parsed) throw std::runtime_error("Fixture move: " + std::string(coordinate));
    return *parsed;
}
std::size_t context(const Position& position, Move candidate) {
    return History::context(position.at(candidate.from), candidate.to);
}
bool no_events(const ContinuationHistoryStatistics& stats) {
    return stats.lookups == 0 && stats.nonzero == 0 && stats.updates == 0;
}
auto snapshot(const History& table) {
    std::vector<std::int16_t> values;
    values.reserve(table_entries);
    for (std::size_t previous = 0; previous < contexts; ++previous)
        for (std::size_t current = 0; current < contexts; ++current)
            values.push_back(static_cast<std::int16_t>(table.value(previous, current)));
    return values;
}
void same_position(const Position& actual, const Position& expected) {
    require(actual.fen() == expected.fen() && actual.key() == expected.key()
            && actual.occupied() == expected.occupied(), "Search changed board counters/key/occupancy");
    for (unsigned square = 0; square < 64; ++square)
        require(actual.at(square) == expected.at(square), "Search changed a square");
    for (auto side : {Color::white, Color::black}) {
        require(actual.king_square(side) == expected.king_square(side), "Search changed king location");
        for (unsigned type = 1; type <= 6; ++type)
            require(actual.pieces(side, static_cast<PieceType>(type))
                    == expected.pieces(side, static_cast<PieceType>(type)), "Search changed a bitboard");
    }
}
struct Direct {
    SharedSearch shared;
    SearchWorker worker;
    explicit Direct(const nnue::Network& network, std::size_t id = 0) : worker(network, shared, id) {
        shared.resize(1);
        worker.continuation_scores.enable(true);
        worker.limits.continuation_history = true;
        worker.limits.diagnostics = true;
        worker.limits.late_move_reductions = false;
        worker.limits.syzygy_probe_limit = 0;
        worker.limits.nodes = 5000;
        worker.started_ns = now_ns();
    }
};

void ordering_and_frozen_prefix(const nnue::Network& network) {
    auto direct = std::make_unique<Direct>(network);
    auto other = std::make_unique<Direct>(network, 1);
    auto& worker = direct->worker;
    auto& table = worker.continuation_scores;
    const auto position = Position::start();
    const auto a = move(position, "a2a3"), b = move(position, "b2b3"), c = move(position, "c2c3");
    const auto previous = History::context(make_piece(Color::black, PieceType::knight), 45);
    const auto different = History::context(make_piece(Color::black, PieceType::pawn), 45);
    table.update(previous, context(position, a), 700);
    table.update(previous, context(position, b), -300);
    table.update(different, context(position, b), 1000);
    worker.history_score[0][a.from][a.to] = -100;
    worker.history_score[0][b.from][b.to] = 200;
    std::vector<Move> parent{b, c, a};
    worker.order(position, parent, {}, 2, {}, previous);
    require(parent == std::vector<Move>{a, c, b} && worker.continuation.lookups == 3
            && worker.continuation.nonzero == 2, "Context did not rank only this quiet list");
    auto second = std::vector<Move>{a, b};
    worker.order(position, second, {}, 2, {}, different);
    require(second.front() == b, "Previous piece identity did not distinguish continuation rows");
    require(other->worker.continuation_scores.value(previous, context(position, a)) == 0,
            "Learning leaked into another worker");

    // A recursive child reuses ordering scratch and updates this same row. Its
    // changes must not reorder the parent's already searched prefix. Learning
    // must nevertheless use the latest table cell, rather than a stale copy.
    const auto frozen = parent;
    table.update(previous, context(position, a), -2000);
    table.update(previous, context(position, b), 3000);
    auto child = std::vector<Move>{a, b, c};
    worker.order(position, child, {}, 3, {}, previous);
    require(child.front() == b && parent == frozen, "Child ranking changed a pending parent list");
    const int old_a = table.value(previous, context(position, a));
    const int old_c = table.value(previous, context(position, c));
    const int old_b = table.value(previous, context(position, b));
    const auto gravity = [](int old, int bonus) { return old + bonus - old * std::abs(bonus) / 16384; };
    worker.learn_continuation_cutoff(position, parent, 1, 3, previous, Mode::ordinary);
    require(table.value(previous, context(position, c)) == gravity(old_c, 216)
            && table.value(previous, context(position, a)) == gravity(old_a, -216)
            && table.value(previous, context(position, b)) == old_b,
            "Cutoff learning did not use the frozen searched prefix and latest history");

    for (bool enabled : {false, true}) {
        worker.limits.continuation_history = enabled;
        worker.continuation = {};
        auto absent = std::vector<Move>{a, b};
        worker.order(position, absent, {}, 0); // Root deliberately has no prior move.
        require(absent.front() == b && no_events(worker.continuation),
                "Absent root context consulted continuation history");
    }
    worker.limits.continuation_history = false;
    worker.continuation = {};
    (void)worker.ordering_score(position, a, {}, 2, {}, previous);
    require(no_events(worker.continuation), "Disabled candidate consulted its retained direct-test table");
    checks += 4;
}

void priority_boundaries(const nnue::Network& network) {
    auto direct = std::make_unique<Direct>(network);
    auto& worker = direct->worker;
    auto position = fen("r3k2r/1P6/8/3pP3/8/8/P7/R3K2R w KQkq d6 0 1");
    const auto previous = History::context(make_piece(Color::black, PieceType::pawn), 35);
    const auto tt = move(position, "a2a3"), killer0 = move(position, "a2a4");
    const auto killer1 = move(position, "h1h2"), reply = move(position, "e1g1");
    worker.killers[2] = {killer0, killer1};
    const std::array privileged{tt, move(position, "b7b8q"), move(position, "b7a8n"),
                                move(position, "e5d6"), killer0, killer1, reply};
    for (auto candidate : privileged) {
        worker.continuation_scores.update(previous, context(position, candidate), -16384);
        worker.limits.continuation_history = false;
        const auto old = worker.ordering_score(position, candidate, tt, 2, reply, previous);
        worker.limits.continuation_history = true;
        const auto actual = worker.ordering_score(position, candidate, tt, 2, reply, previous);
        require(actual == old, "Contextual history changed a higher-priority ordering tier");
    }
    require(no_events(worker.continuation), "TT/capture/promotion/killer/countermove queried continuation");
    auto ordinary = move(position, "e1d1");
    worker.continuation_scores.update(previous, context(position, ordinary), 16384);
    auto legal = position.legal_moves(), ordered = legal;
    worker.order(position, ordered, tt, 2, reply, previous);
    require(ordered.front() == tt, "A quiet continuation displaced the TT move");
    for (auto candidate : legal)
        require(std::count(ordered.begin(), ordered.end(), candidate) == 1,
                "Continuation ordering lost or duplicated a legal move");
    ++checks;
}

void learning_boundaries(const nnue::Network& network) {
    auto direct = std::make_unique<Direct>(network);
    auto& worker = direct->worker;
    const auto position = fen("r3k2r/1P6/8/3pP3/8/8/P7/R3K2R w KQkq d6 0 1");
    const auto previous = History::context(make_piece(Color::black, PieceType::pawn), 35);
    const std::vector<Move> moves{move(position, "a2a3"), move(position, "e5d6"),
        move(position, "b7b8q"), move(position, "e1g1"), move(position, "a2a4"),
        move(position, "b7a8n"), move(position, "h1h2")};
    worker.learn_continuation_cutoff(position, moves, 4, 4, previous, Mode::ordinary);
    require(worker.continuation.updates == 3
            && worker.continuation_scores.value(previous, context(position, moves[4])) == 384
            && worker.continuation_scores.value(previous, context(position, moves[0])) == -384
            && worker.continuation_scores.value(previous, context(position, moves[3])) == -384,
            "Winner and prior ordinary/castling quiet moves were not learned");
    for (const auto index : {1, 2, 5, 6})
        require(worker.continuation_scores.value(previous, context(position, moves[index])) == 0,
                "Capture/promotion/unsearched move was penalized");
    const auto stored = snapshot(worker.continuation_scores);
    for (const auto mode : {Mode::null_probe, Mode::verification, Mode::probcut})
        worker.learn_continuation_cutoff(position, moves, 4, 4, previous, mode);
    for (const auto index : {1U, 2U, 5U})
        worker.learn_continuation_cutoff(position, moves, index, 4, previous, Mode::ordinary);
    worker.learn_continuation_cutoff(position, moves, 4, 4, SearchWorker::no_previous_move, Mode::ordinary);
    worker.limits.continuation_history = false;
    worker.learn_continuation_cutoff(position, moves, 4, 4, previous, Mode::ordinary);
    require(snapshot(worker.continuation_scores) == stored && worker.continuation.updates == 3,
            "Forbidden learning path modified continuation state or counters");
    worker.limits.continuation_history = true;
    worker.limits.diagnostics = false;
    worker.learn_continuation_cutoff(position, moves, 4, 4, previous, Mode::ordinary);
    require(worker.continuation.updates == 3 && snapshot(worker.continuation_scores) != stored,
            "Diagnostics changed learning behavior or counted disabled events");
    worker.clear();
    const auto cleared = snapshot(worker.continuation_scores);
    require(worker.continuation_scores.enabled() && worker.continuation_scores.allocated_bytes() == table_bytes
            && std::all_of(cleared.begin(), cleared.end(), [](int value) { return value == 0; }),
            "Clear retained learned continuation or dropped enabled allocation");
    checks += 3;
}

void original_piece_context(const nnue::Network& network) {
    const std::array fixtures{
        std::pair{"4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q"},
        std::pair{"4k3/8/8/8/8/8/1p5P/4K3 b - - 0 1", "b2b1n"},
        std::pair{"4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1", "e1g1"},
        std::pair{"r3k2r/8/8/8/8/8/8/4K3 b kq - 0 1", "e8c8"},
        std::pair{"4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"}};
    for (const auto& [text, coordinate] : fixtures) {
        auto direct = std::make_unique<Direct>(network);
        auto& worker = direct->worker;
        auto position = fen(text), original = position;
        const auto forced = move(position, coordinate);
        const auto previous = context(position, forced);
        auto child = position;
        (void)child.make_move(forced);
        const auto replies = child.legal_moves();
        worker.game_history = {position.key()};
        worker.limits.searchmoves = {forced};
        // A deliberately losing root scout window makes its ordinary child
        // fail high on a quiet reply, exposing the exact forwarded context row.
        (void)worker.alphabeta(position, 2, 20000, 20001, 0, true, mix(position.key()));
        require(!worker.aborted && worker.continuation.updates > 0,
                "Special-move context fixture produced no completed quiet cutoff");
        bool found = false;
        for (auto reply : replies)
            found |= worker.continuation_scores.value(previous, context(child, reply)) > 0;
        require(found, "Search did not forward the original moved-piece/destination context");
        if (forced.promotion != PieceType::none) {
            const auto promoted = History::context(child.at(forced.to), forced.to);
            for (auto reply : replies)
                require(worker.continuation_scores.value(promoted, context(child, reply)) == 0,
                        "Promotion forwarded the promoted piece instead of the original pawn");
        }
        require(worker.game_history == std::vector<std::uint64_t>{original.key()},
                "Special-move search did not restore game history");
        same_position(position, original);
        ++checks;
    }
}

void speculative_and_aborted_searches(const nnue::Network& network) {
    for (const auto mode : {Mode::null_probe, Mode::verification, Mode::probcut}) {
        auto direct = std::make_unique<Direct>(network);
        auto& worker = direct->worker;
        auto position = Position::start(), original = position;
        auto candidate = move(position, "d2d4");
        const auto previous = History::context(make_piece(Color::black, PieceType::pawn), 35);
        worker.continuation_scores.update(previous, context(position, candidate), 2000);
        const auto stored = snapshot(worker.continuation_scores);
        worker.game_history = {position.key()};
        (void)worker.alphabeta(position, 2, -infinity, infinity, 1, true,
                              mix(position.key()), previous, mode);
        require(!worker.aborted && no_events(worker.continuation)
                && snapshot(worker.continuation_scores) == stored,
                "Speculative subtree consulted or trained continuation history");
        require(worker.game_history == std::vector<std::uint64_t>{original.key()},
                "Speculation changed game history");
        same_position(position, original);
        ++checks;
    }
    for (const auto budget : {1U, 2U, 17U}) {
        auto direct = std::make_unique<Direct>(network);
        auto& worker = direct->worker;
        auto position = Position::start(), original = position;
        worker.game_history = {position.key()};
        worker.limits.nodes = budget;
        (void)worker.alphabeta(position, 4, -infinity, infinity, 0, true, mix(position.key()));
        require(worker.aborted && worker.nodes == budget
                && worker.game_history == std::vector<std::uint64_t>{original.key()},
                "Interrupted continuation search exceeded budget or changed history");
        same_position(position, original);
        // At budgets one/two no completed child can justify a cutoff update.
        if (budget <= 2) require(worker.continuation.updates == 0, "Aborted child trained a cutoff");
        ++checks;
    }
    auto direct = std::make_unique<Direct>(network);
    auto position = Position::start();
    direct->worker.game_history = {position.key()};
    (void)direct->worker.quiescence(position, -infinity, infinity, 0);
    require(no_events(direct->worker.continuation), "Quiescence used continuation history");
    ++checks;
}

void same_deterministic_result(const SearchResult& actual, const SearchResult& expected) {
    require(actual.best == expected.best && actual.ponder == expected.ponder
            && actual.score == expected.score && actual.depth == expected.depth
            && actual.nodes == expected.nodes && actual.hashfull == expected.hashfull,
            "Clear/toggle/failed allocation changed deterministic search state");
    require(actual.continuation_history.lookups == expected.continuation_history.lookups
            && actual.continuation_history.nonzero == expected.continuation_history.nonzero
            && actual.continuation_history.updates == expected.continuation_history.updates,
            "Continuation event state differs after a transaction/reset");
}

SearchLimits shallow_limits() {
    SearchLimits limits;
    limits.depth = 3;
    limits.late_move_reductions = false;
    limits.syzygy_probe_limit = 0;
    limits.diagnostics = true;
    return limits;
}
SearchResult run(Search& search, const SearchLimits& limits, Position position = Position::start()) {
    search.reset_stop();
    return search.search(position, {}, limits);
}

void public_lifecycle(const nnue::Network& network) {
    auto limits = shallow_limits();
    Search search(network, 1);
    const auto baseline = run(search, limits);
    require(!baseline.continuation_history.enabled && baseline.continuation_history.entries == 0
            && baseline.continuation_history.allocated_bytes == 0 && no_events(baseline.continuation_history),
            "Default API allocated or used continuation history");
    limits.continuation_history = true;
    const auto enabled = run(search, limits);
    require(enabled.continuation_history.enabled && enabled.continuation_history.entries == table_entries
            && enabled.continuation_history.allocated_bytes == table_bytes
            && enabled.continuation_history.lookups > 0 && enabled.continuation_history.updates > 0,
            "Enabled API did not account for allocation/learning");
    require(enabled.score == baseline.score && enabled.depth == baseline.depth,
            "Unpruned shallow minimax score changed with quiet ordering");
    require(enabled.diagnostics->cache.capacity == baseline.diagnostics->cache.capacity
            && enabled.diagnostics->cache.allocated_bytes == baseline.diagnostics->cache.allocated_bytes,
            "Private continuation allocation changed the Hash budget");
    (void)run(search, limits);
    search.clear();
    same_deterministic_result(run(search, limits), enabled);
    limits.continuation_history = false;
    const auto restored = run(search, limits);
    same_deterministic_result(restored, baseline);
    require(restored.continuation_history.entries == 0 && restored.continuation_history.allocated_bytes == 0,
            "Disabling did not release continuation tables");
    limits.continuation_history = true;
    same_deterministic_result(run(search, limits), enabled);
    search.reset_stop();
    search.stop();
    const auto stopped = search.search(Position::start(), {}, limits);
    require(stopped.nodes == 0 && no_events(stopped.continuation_history)
            && stopped.continuation_history.entries == table_entries,
            "Preparation swallowed a published stop or hid allocated geometry");
    for (const auto text : {"7k/6Q1/5K2/8/8/8/8/8 b - - 100 1",
                            "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1",
                            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 100 1"}) {
        auto position = fen(text);
        auto result = run(search, limits, position);
        require(no_events(result.continuation_history)
                && result.continuation_history.entries == table_entries
                && result.score == (position.in_check(position.turn()) ? -Search::mate_score : 0),
                "Continuation changed terminal precedence or event/geometry accounting");
    }
    checks += 7;
}

void allocation_transactions(const nnue::Network& network) {
    // Matching warmed single-worker controls make accidental clearing of the
    // old TT, ordinary history, continuation history or policy observable.
    for (const int scenario : {0, 1, 2}) {
        Search control(network, 1), failing(network, 1);
        auto prior = shallow_limits();
        prior.continuation_history = scenario == 2;
        (void)run(control, prior);
        (void)run(failing, prior);
        auto attempted = prior;
        attempted.continuation_history = !prior.continuation_history;
        attempted.tt_move_hints = scenario != 0;
        allocation_fault::arm(scenario == 0 ? table_bytes : 8192 * sizeof(MoveHintEntry));
        bool failed = false;
        try { (void)run(failing, attempted); } catch (const std::bad_alloc&) { failed = true; }
        allocation_fault::disarm();
        require(failed, "Public transaction fixture did not reach the requested allocation");
        const auto expected = run(control, prior), actual = run(failing, prior);
        same_deterministic_result(actual, expected);
        require(actual.continuation_history.entries == expected.continuation_history.entries
                && actual.diagnostics->cache.hits == expected.diagnostics->cache.hits
                && actual.diagnostics->move_hints.slots == 0,
                "Failed optional allocation partially committed geometry or cleared caches");
        ++injected_failures;
        ++checks;
    }
    for (unsigned ordinal : {1U, 4U}) {
        Search search(network, 1, 4);
        auto limits = shallow_limits();
        limits.continuation_history = true;
        allocation_fault::arm(table_bytes, ordinal);
        bool failed = false;
        try { (void)run(search, limits); } catch (const std::bad_alloc&) { failed = true; }
        allocation_fault::disarm();
        require(failed, "Multiworker preparation did not reach the chosen worker allocation");
        limits.continuation_history = false;
        const auto terminal = fen("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1");
        const auto disabled = run(search, limits, terminal);
        require(disabled.continuation_history.entries == 0
                && disabled.continuation_history.allocated_bytes == 0
                && no_events(disabled.continuation_history), "Failed preparation left a subset of workers enabled");
        limits.continuation_history = true;
        const auto recovered = run(search, limits, terminal);
        require(recovered.continuation_history.entries == 4 * table_entries
                && recovered.continuation_history.allocated_bytes == 4 * table_bytes
                && no_events(recovered.continuation_history), "Recovery did not prepare every worker exactly once");
        ++injected_failures;
        ++checks;
    }
}

void bounded_public_workers(const nnue::Network& network) {
    for (const int workers : {1, 4}) {
        for (const bool diagnostics : {false, true}) {
            Search search(network, 1, workers);
            auto limits = shallow_limits();
            limits.depth = 0;
            limits.nodes = 2500;
            limits.continuation_history = true;
            limits.diagnostics = diagnostics;
            const auto result = run(search, limits);
            const auto legal = Position::start().legal_moves();
            require(std::find(legal.begin(), legal.end(), result.best) != legal.end()
                    && result.nodes == limits.nodes && result.smp.threads == workers
                    && result.smp.worker_nodes.size() == static_cast<std::size_t>(workers)
                    && std::accumulate(result.smp.worker_nodes.begin(), result.smp.worker_nodes.end(),
                                       std::uint64_t{0}) == result.nodes,
                    "Continuation violated legal-result/global-node/worker accounting");
            require(result.continuation_history.enabled
                    && result.continuation_history.entries == static_cast<std::size_t>(workers) * table_entries
                    && result.continuation_history.allocated_bytes == static_cast<std::size_t>(workers) * table_bytes,
                    "Aggregate continuation geometry omitted a worker");
            if (diagnostics)
                require(result.continuation_history.lookups > 0 && result.continuation_history.updates > 0,
                        "Enabled diagnostics did not count real search events");
            else require(no_events(result.continuation_history) && !result.diagnostics,
                         "Diagnostics-off search counted event instrumentation");
            ++checks;
        }
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc > 2) throw std::runtime_error("Usage: continuation-history-search-test [NETWORK.nnue]");
        nnue::Network network;
        if (argc == 2) {
            std::string error;
            if (!network.load(argv[1], error)) throw std::runtime_error("Network load failed: " + error);
        }
        ordering_and_frozen_prefix(network);
        priority_boundaries(network);
        learning_boundaries(network);
        if (network.loaded()) {
            original_piece_context(network);
            speculative_and_aborted_searches(network);
            public_lifecycle(network);
            allocation_transactions(network);
            bounded_public_workers(network);
        }
        std::cout << "Continuation-history search checks passed (" << checks << " bounded groups; "
                  << injected_failures << " injected allocation failures; "
                  << (network.loaded() ? "NNUE/search paths included" : "NNUE/search paths skipped") << ")\n";
    } catch (const std::exception& error) {
        allocation_fault::disarm();
        std::cerr << "Continuation-history search test failed: " << error.what() << '\n';
        return 1;
    }
}
