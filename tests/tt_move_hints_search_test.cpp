/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Exercise private cache/mode boundaries without a production test API.
// Link Position/NNUE/exchange/tablebase objects, but never search.o as well.
#include "../src/search.cpp"

#include <cstdlib>
#include <iostream>
#include <new>
#include <string_view>
#include <tuple>

namespace allocation_fault {
// A one-shot, current-thread failure for the exact small hint allocation.
// No huge allocation or exhaustion of the host's memory is needed. Aligned
// allocation (including score buckets) remains the standard implementation.
thread_local std::size_t bytes = 0;
}
void* operator new(std::size_t size) {
    if (size != 0 && size == allocation_fault::bytes) {
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
using Mode = SearchWorker::Mode;
std::size_t checks = 0;
std::size_t injected_failures = 0;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view value) {
    std::string error;
    const auto position = Position::from_fen(value, error);
    if (!position) throw std::runtime_error("Fixture FEN: " + error);
    return *position;
}

Move move(Position position, std::string_view text) {
    const auto parsed = parse_uci_move(position, text);
    if (!parsed) throw std::runtime_error("Fixture move: " + std::string(text));
    return *parsed;
}

auto hints(const SharedSearch& shared) {
    std::vector<std::pair<std::uint64_t, Move>> result;
    for (const auto& entry : shared.move_hints) result.emplace_back(entry.key, entry.move);
    return result;
}

auto scores(const SharedSearch& shared) {
    std::vector<std::tuple<std::uint64_t, Move, int, unsigned, Bound, unsigned>> result;
    for (const auto& bucket : shared.table)
        for (const auto& entry : bucket.entries)
            result.emplace_back(entry.key, entry.move(), entry.score, entry.depth,
                                entry.bound(), entry.generation);
    return result;
}

bool no_events(const MoveHintStatistics& stats) {
    return stats.probes == 0 && stats.hits == 0 && stats.legal_matches == 0 && stats.stores == 0;
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
    explicit Direct(const nnue::Network& network) : worker(network, shared, 0) {
        shared.resize(1);
        shared.set_move_hints(true);
        worker.limits.tt_move_hints = true;
        worker.limits.diagnostics = true;
        worker.limits.late_move_reductions = false;
        worker.limits.syzygy_probe_limit = 0;
        worker.limits.nodes = 5000;
        worker.started_ns = now_ns();
    }
};

void allocation_and_full_keys(const nnue::Network& network) {
    auto direct = std::make_unique<Direct>(network);
    auto& shared = direct->shared;
    auto& worker = direct->worker;
    const auto position = Position::start();
    const auto first = move(position, "e2e4"), second = move(position, "d2d4");
    require(shared.table.size() == 8192 && shared.move_hints.size() == shared.table.size()
            && sizeof(shared.table.front()) == 64 && sizeof(shared.move_hints.front()) == 16
            && 80 * shared.table.size() <= 1024 * 1024, "Hint allocation changed score capacity or Hash budget");
    require(!worker.probe_move_hint(0), "Empty zero-key entry produced a hit");
    worker.store_move_hint(0, first, 0, Mode::ordinary);
    require(worker.probe_move_hint(0) == first, "A real zero key cannot be cached");
    const auto alias = static_cast<std::uint64_t>(shared.table.size());
    require(!worker.probe_move_hint(alias), "Index alias matched without the full key");
    worker.store_move_hint(alias, second, 0, Mode::ordinary);
    require(!worker.probe_move_hint(0) && worker.probe_move_hint(alias) == second,
            "Direct replacement left a stale full-key match");
    worker.save(0xabcdef, first, 237, 4, 0, Bound::exact);
    const auto before_scores = scores(shared);
    const auto before_hints = hints(shared);
    worker.store_move_hint(alias, Move{}, 0, Mode::ordinary);
    require(hints(shared) == before_hints && scores(shared) == before_scores,
            "Invalid hint store changed caches");

    // Fail the optional allocation during resize, after the replacement score
    // storage has been allocated. Neither old cache may have been swapped yet.
    allocation_fault::bytes = 2 * shared.move_hints.size() * sizeof(shared.move_hints.front());
    bool failed = false;
    try { shared.resize(2); } catch (const std::bad_alloc&) { failed = true; }
    allocation_fault::bytes = 0;
    require(failed && scores(shared) == before_scores && hints(shared) == before_hints,
            "Failed resize did not preserve both caches");
    ++injected_failures;
    shared.set_move_hints(false);
    require(shared.move_hints.empty() && shared.move_hints.capacity() == 0
            && scores(shared) == before_scores, "Disabling retained hint allocation or changed score entries");
    allocation_fault::bytes = shared.table.size() * sizeof(MoveHintEntry);
    failed = false;
    try { shared.set_move_hints(true); } catch (const std::bad_alloc&) { failed = true; }
    allocation_fault::bytes = 0;
    require(failed && shared.move_hints.empty() && scores(shared) == before_scores,
            "Failed enable changed prior cache state");
    ++injected_failures;
    worker.move_hints = {};
    require(!worker.probe_move_hint(alias) && no_events(worker.move_hints),
            "Unallocated hint storage was probed");
    shared.set_move_hints(true);
    shared.resize(2);
    require(shared.table.size() == 16384 && shared.move_hints.size() == 16384
            && !worker.probe_move_hint(alias), "Successful resize retained old hints or changed geometry");
    ++checks;
}

void legal_ordering_and_context(const nnue::Network& network) {
    auto direct = std::make_unique<Direct>(network);
    auto& worker = direct->worker;
    const std::array fixtures{
        std::pair{"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4"},
        std::pair{"r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"},
        std::pair{"4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"},
        std::pair{"4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"},
        std::pair{"1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8r"},
        std::pair{"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1", "e7e5"},
        std::pair{"r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", "e8c8"},
        std::pair{"4k3/8/8/8/8/8/1p6/4K3 b - - 0 1", "b2b1n"}};
    for (const auto& [text, coordinate] : fixtures) {
        auto position = fen(text);
        const auto original = position;
        const auto legal = position.legal_moves();
        const auto hint = move(position, coordinate);
        worker.store_move_hint(position.key(), hint, 0, Mode::ordinary);
        const auto frozen_scores = scores(direct->shared);
        const auto selected = worker.ordering_move(position.key(), legal, {}, 0, Mode::ordinary);
        require(selected == hint, "Legal special move was not selected from the hint cache");
        const Move stale_context{0, 63, PieceType::none, quiet};
        require(std::find(legal.begin(), legal.end(), stale_context) == legal.end()
                && worker.ordering_move(position.key(), legal, stale_context, 0, Mode::ordinary) == hint,
                "Stale contextual TT move blocked a legal fallback hint");
        auto ordered = legal;
        worker.order(position, ordered, selected, 0);
        require(ordered.front() == hint, "Hint did not order the existing list");
        for (const auto candidate : legal)
            require(std::count(ordered.begin(), ordered.end(), candidate) == 1,
                    "Hint ordering lost or duplicated a legal move");
        auto contextual = legal.front() == hint ? legal.back() : legal.front();
        const auto before_probes = worker.move_hints.probes;
        require(worker.ordering_move(position.key(), legal, contextual, 0, Mode::ordinary) == contextual
                && worker.move_hints.probes == before_probes, "Hint displaced a legal contextual TT move");

        // A matching key is not authority to execute a move: preserve the full
        // flags and promotion rather than accepting only matching coordinates.
        auto malformed = hint;
        malformed.flags ^= capture;
        worker.store_move_hint(position.key(), malformed, 0, Mode::ordinary);
        const auto before_matches = worker.move_hints.legal_matches;
        require(!worker.ordering_move(position.key(), legal, {}, 0, Mode::ordinary).valid()
                && worker.move_hints.legal_matches == before_matches,
                "Hint with mismatched move flags entered the legal order");
        malformed = hint;
        malformed.promotion = PieceType::king;
        worker.store_move_hint(position.key(), malformed, 0, Mode::ordinary);
        require(!worker.ordering_move(position.key(), legal, {}, 0, Mode::ordinary).valid(),
                "Malformed promotion was accepted as a legal hint");
        require(scores(direct->shared) == frozen_scores, "Move hints supplied or overwrote score-cache data");
        same_position(position, original);
        ++checks;
    }

    auto first = Position::start();
    const auto later = fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 8 5");
    require(first.key() == later.key(), "Fixture must keep the same board identity");
    const auto key_a = worker.table_key(first, mix(first.key()));
    const auto key_b = worker.table_key(later, mix(later.key()));
    const auto key_c = worker.table_key(first, mix(first.key()) + mix(0x1234));
    require(key_a != key_b && key_a != key_c, "Hint option weakened draw-sensitive score keys");
    const auto hint = move(first, "h2h3");
    worker.save(key_a, hint, 1234, 4, 0, Bound::exact);
    worker.store_move_hint(first.key(), hint, 0, Mode::ordinary);
    require(!worker.probe(key_b) && !worker.probe(key_c)
            && worker.ordering_move(later.key(), first.legal_moves(), {}, 0, Mode::ordinary) == hint,
            "Position hint incorrectly carried a score across draw contexts");
    const Move contextual_tt;
    const auto order_hint = worker.ordering_move(first.key(), first.legal_moves(), contextual_tt, 0, Mode::ordinary);
    search_policy::LateMoveContext late{6, 1, 12, false, false, false, false,
        hint, first.at(hint.from), contextual_tt, {}, {}};
    require(order_hint == hint && !contextual_tt.valid() && search_policy::reduce_late_move(late),
            "Ordering-only hint became a contextual LMR exemption");
    ++checks;
}

void modes_and_interruption(const nnue::Network& network) {
    auto position = Position::start();
    const auto legal = position.legal_moves();
    const auto hint = move(position, "d2d4");
    for (const auto mode : {Mode::null_probe, Mode::verification, Mode::probcut}) {
        auto direct = std::make_unique<Direct>(network);
        auto& worker = direct->worker;
        worker.game_history = {position.key()};
        worker.store_move_hint(position.key(), hint, 0, Mode::ordinary);
        const auto before_hints = hints(direct->shared);
        const auto before_scores = scores(direct->shared);
        worker.move_hints = {};
        require(!worker.ordering_move(position.key(), legal, {}, 1, mode).valid(), "Speculation consumed a hint");
        worker.store_move_hint(position.key(), legal.front(), 1, mode);
        const auto before = position;
        (void)worker.alphabeta(position, 2, -infinity, infinity, 1, true, mix(position.key()),
                               SearchWorker::no_previous_move, mode);
        require(!worker.aborted && no_events(worker.move_hints)
                && hints(direct->shared) == before_hints && scores(direct->shared) == before_scores,
                "Speculative subtree read hints or changed cache state");
        require(worker.game_history == std::vector<std::uint64_t>{position.key()}, "Speculation changed history");
        same_position(position, before);
        ++checks;
    }
    for (const bool restricted : {false, true}) {
        auto direct = std::make_unique<Direct>(network);
        auto& worker = direct->worker;
        worker.game_history = {position.key()};
        worker.store_move_hint(position.key(), hint, 0, Mode::ordinary);
        const auto stored = hints(direct->shared);
        worker.move_hints = {};
        if (restricted) worker.limits.searchmoves = {hint};
        else worker.limits.nodes = 1;
        const auto before = position;
        (void)worker.alphabeta(position, 1, -infinity, infinity, 0, true, mix(position.key()));
        require(worker.move_hints.stores == 0 && hints(direct->shared) == stored,
                "Restricted or interrupted node stored a hint");
        require(restricted ? no_events(worker.move_hints) : worker.aborted,
                "Restricted root probed hints or node limit failed to interrupt");
        same_position(position, before);
        ++checks;
    }
    auto direct = std::make_unique<Direct>(network);
    auto& worker = direct->worker;
    worker.game_history = {position.key()};
    worker.store_move_hint(position.key(), hint, 0, Mode::ordinary);
    worker.move_hints = {};
    const auto stored = hints(direct->shared);
    (void)worker.quiescence(position, -infinity, infinity, 0);
    require(no_events(worker.move_hints) && hints(direct->shared) == stored, "Quiescence accessed hint cache");
    worker.limits.searchmoves = {hint};
    require(!worker.move_hints_allowed(0, Mode::ordinary) && worker.move_hints_allowed(1, Mode::ordinary),
            "Root restriction leaked into unrestricted descendants");
    worker.limits.tt_move_hints = false;
    require(!worker.move_hints_allowed(1, Mode::ordinary), "Disabled policy retained hint access");
    ++checks;
}

void public_lifecycle(const nnue::Network& network) {
    Search search(network, 1);
    SearchLimits limits;
    limits.depth = 3;
    limits.late_move_reductions = false;
    limits.syzygy_probe_limit = 0;
    limits.diagnostics = true;
    auto run = [&](Position position, std::vector<std::uint64_t> history = {}) {
        search.reset_stop();
        return search.search(position, std::move(history), limits);
    };
    auto position = Position::start();
    const auto baseline = run(position);
    require(baseline.diagnostics && !baseline.diagnostics->move_hints.enabled
            && baseline.diagnostics->move_hints.slots == 0
            && baseline.diagnostics->move_hints.allocated_bytes == 0
            && no_events(baseline.diagnostics->move_hints), "Default API allocated or used hints");
    {
        // The coordinator must allocate before changing its previous-policy
        // snapshot or clearing warmed bounds/history. Compare with the same
        // ordinary search sequence in an untouched control Search instance.
        Search control(network, 1), failure(network, 1);
        auto request = limits;
        auto checked_run = [&](Search& instance) {
            instance.reset_stop();
            return instance.search(position, {}, request);
        };
        (void)checked_run(control);
        (void)checked_run(failure);
        request.tt_move_hints = true;
        allocation_fault::bytes = 8192 * sizeof(MoveHintEntry);
        bool failed = false;
        try { (void)checked_run(failure); } catch (const std::bad_alloc&) { failed = true; }
        allocation_fault::bytes = 0;
        require(failed, "Public failed-enable fixture did not reach hint allocation");
        request.tt_move_hints = false;
        const auto expected = checked_run(control), actual = checked_run(failure);
        require(actual.best == expected.best && actual.ponder == expected.ponder
                && actual.score == expected.score && actual.nodes == expected.nodes
                && actual.hashfull == expected.hashfull
                && actual.diagnostics->cache.hits == expected.diagnostics->cache.hits
                && actual.diagnostics->move_hints.slots == 0,
                "Failed public enable cleared policy, history, bounds or allocation state");
        ++injected_failures;
        ++checks;
    }
    limits.tt_move_hints = true;
    const auto enabled = run(position);
    require(enabled.score == baseline.score && enabled.depth == baseline.depth
            && enabled.diagnostics->move_hints.enabled && enabled.diagnostics->move_hints.stores > 0,
            "Unpruned shallow minimax score changed or hint path did not activate");
    const auto geometry = enabled.diagnostics->cache;
    require(geometry.capacity == baseline.diagnostics->cache.capacity
            && geometry.allocated_bytes == baseline.diagnostics->cache.allocated_bytes
            && enabled.diagnostics->move_hints.slots == geometry.buckets
            && enabled.diagnostics->move_hints.allocated_bytes == 16 * geometry.buckets,
            "Enabling hints changed score capacity/accounting");
    limits.tt_move_hints = false;
    const auto restored = run(position);
    require(restored.best == baseline.best && restored.ponder == baseline.ponder
            && restored.score == baseline.score && restored.nodes == baseline.nodes
            && restored.hashfull == baseline.hashfull && restored.diagnostics->move_hints.slots == 0,
            "Policy switch did not restore the unchanged default path");
    limits.tt_move_hints = true;
    search.reset_stop();
    search.stop();
    const auto stopped = search.search(position, {}, limits);
    require(stopped.nodes == 0 && no_events(stopped.diagnostics->move_hints), "Policy setup consumed a published stop");
    for (const auto text : {"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 100 1",
                            "7k/6Q1/5K2/8/8/8/8/8 b - - 100 1",
                            "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1"}) {
        const auto root = fen(text);
        const auto result = run(root);
        require(no_events(result.diagnostics->move_hints), "Terminal/drawn root accessed hints before adjudication");
        require(result.score == (root.in_check(root.turn()) ? -Search::mate_score : 0), "Draw/mate precedence changed");
        ++checks;
    }
    position = fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 8 5");
    const auto repetition = run(position, {position.key(), 0x1234, position.key(), 0x5678, position.key()});
    require(repetition.score == 0 && no_events(repetition.diagnostics->move_hints), "Hint bypassed real repetition draw");
    checks += 3;
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Usage: tt-move-hints-search-test NETWORK.nnue");
        nnue::Network network;
        std::string error;
        if (!network.load(argv[1], error)) throw std::runtime_error("Network load failed: " + error);
        allocation_and_full_keys(network);
        legal_ordering_and_context(network);
        modes_and_interruption(network);
        public_lifecycle(network);
        std::cout << "TT move-hint search checks passed (" << checks << " bounded groups; "
                  << injected_failures << " injected allocation failures)\n";
    } catch (const std::exception& error) {
        allocation_fault::bytes = 0;
        std::cerr << "TT move-hint search test failed: " << error.what() << '\n';
        return 1;
    }
}
