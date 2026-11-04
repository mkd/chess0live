/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Compile the real search here to exercise interior windows and child probes.
// Link position/NNUE/exchange/tablebase objects, never a second search.o.
#include "../src/search.cpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <numeric>
#include <sstream>
#include <string_view>

namespace child_interrupt {
// Inject only while the actual board is the proposed child and its mobility
// list allocates. This observes production state without a search/eval hook.
thread_local const chess0live::Position* position = nullptr;
thread_local std::uint64_t child_key = 0;
thread_local std::atomic<bool>* stop = nullptr;
thread_local bool reached = false;
void disarm() { position = nullptr; stop = nullptr; }
}
void* operator new(std::size_t size) {
    if (child_interrupt::position && child_interrupt::position->key() == child_interrupt::child_key) {
        const auto stop = child_interrupt::stop;
        child_interrupt::reached = true;
        child_interrupt::disarm();
        if (stop) stop->store(true, std::memory_order_relaxed);
        else throw std::bad_alloc{};
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
bool legal(Position position, Move candidate) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), candidate) != moves.end();
}
Position reflected(const Position& position) {
    std::istringstream input(position.fen());
    std::string board, side, rights, ep, halfmove, fullmove;
    input >> board >> side >> rights >> ep >> halfmove >> fullmove;
    require(rights == "-", "Reflection needs a no-castling fixture");
    std::vector<std::string> ranks;
    std::istringstream placement(board);
    for (std::string rank; std::getline(placement, rank, '/');) ranks.push_back(rank);
    std::reverse(ranks.begin(), ranks.end());
    board.clear();
    for (const auto& rank : ranks) {
        if (!board.empty()) board += '/';
        for (auto c : rank) {
            const auto byte = static_cast<unsigned char>(c);
            board += static_cast<char>(std::islower(byte) ? std::toupper(byte) : std::tolower(byte));
        }
    }
    if (ep != "-") ep[1] = static_cast<char>('1' + '8' - ep[1]);
    return fen(board + (side == "w" ? " b - " : " w - ") + ep + " " + halfmove + " " + fullmove);
}
void same_position(const Position& actual, const Position& expected) {
    require(actual.fen() == expected.fen() && actual.key() == expected.key()
            && actual.occupied() == expected.occupied(), "Delta changed board/key/counters");
    for (int square = 0; square < 64; ++square)
        require(actual.at(square) == expected.at(square), "Delta changed a square");
    for (auto side : {Color::white, Color::black}) {
        require(actual.king_square(side) == expected.king_square(side), "Delta changed king state");
        for (unsigned type = 1; type <= 6; ++type)
            require(actual.pieces(side, static_cast<PieceType>(type))
                    == expected.pieces(side, static_cast<PieceType>(type)), "Delta changed a bitboard");
    }
}
void counters(const QSearchDeltaStatistics& stats, bool enabled, bool diagnostics) {
    require(stats.enabled == enabled, "Delta option snapshot is stale");
    require(stats.pruned + stats.protected_checks + stats.protected_terminals <= stats.candidates,
            "Delta counted a candidate twice");
    if (!enabled || !diagnostics)
        require(stats.eligible_nodes == 0 && stats.candidates == 0 && stats.pruned == 0
                && stats.protected_checks == 0 && stats.protected_terminals == 0,
                "Inactive delta diagnostics retained work");
}
struct Interior {
    SharedSearch shared;
    SearchWorker worker;
    Interior(const nnue::Network& network, const Position& root, std::uint64_t nodes = 10000)
        : worker(network, shared, 0) {
        shared.resize(1);
        worker.limits.qsearch_delta_pruning = true;
        worker.limits.diagnostics = true;
        worker.limits.syzygy_probe_limit = 0;
        worker.limits.nodes = nodes;
        worker.qsearch_delta.enabled = true;
        worker.started_ns = now_ns();
        worker.game_history = {root.key()};
        worker.game_history.reserve(Search::max_ply + 1);
    }
    int search(Position& root, int alpha, int width = 1, int ply = 1, Mode mode = Mode::ordinary) {
        const auto before = root;
        const auto history = worker.game_history;
        const int value = worker.quiescence(root, alpha, alpha + width, ply, mode);
        same_position(root, before);
        require(worker.game_history == history, "Delta changed real history");
        counters(worker.qsearch_delta, worker.limits.qsearch_delta_pruning, worker.limits.diagnostics);
        return value;
    }
};
const char* capture_fen = "r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 0 1";

void policy_boundaries() {
    using namespace search_policy;
    QSearchDeltaContext base;
    base.ply = 1;
    base.pieces = 9;
    base.scout = true;
    require(qsearch_delta_eligible(base) && !qsearch_delta_eligible({}), "Delta eligibility default changed");
    for (auto member : {&QSearchDeltaContext::in_check, &QSearchDeltaContext::special_window,
                        &QSearchDeltaContext::speculative, &QSearchDeltaContext::repeated,
                        &QSearchDeltaContext::advanced_pawn}) {
        auto protected_node = base;
        protected_node.*member = true;
        require(!qsearch_delta_eligible(protected_node), "Delta admitted a protected node");
    }
    for (int count : {0, 7, 8, 9, 32}) {
        auto context = base;
        context.pieces = count;
        require(qsearch_delta_eligible(context) == (count > 8), "Delta piece boundary changed");
    }
    for (unsigned halfmove : {0U, 79U, 80U, 100U, std::numeric_limits<unsigned>::max()}) {
        auto context = base;
        context.halfmove = halfmove;
        require(qsearch_delta_eligible(context) == (halfmove < 80), "Delta halfmove boundary changed");
    }
    require(qsearch_delta_margin == 400, "Frozen delta margin changed");
    constexpr int allowances[] = {0, 400, 1280, 1320, 2000, 3600, 0};
    Move capture_move{0, 8, PieceType::none, capture};
    for (unsigned type = 0; type <= 6; ++type) {
        const auto victim = static_cast<PieceType>(type);
        require(qsearch_delta_allowance(victim) == allowances[type], "Frozen victim allowance changed");
        const int edge = 123 + allowances[type] + 400;
        require(!qsearch_delta_candidate(capture_move, victim, 123, edge), "Delta must use strict inequality");
        require(qsearch_delta_candidate(capture_move, victim, 123, edge + 1) == (type >= 1 && type <= 5),
                "Delta rejected a valid victim or accepted none/king");
    }
    require(!qsearch_delta_candidate(capture_move, PieceType::queen, std::numeric_limits<int>::max(),
                                     std::numeric_limits<int>::max()), "Delta arithmetic overflowed high");
    require(qsearch_delta_candidate(capture_move, PieceType::pawn, std::numeric_limits<int>::min(),
                                    std::numeric_limits<int>::max()), "Delta arithmetic overflowed low");
    for (auto special : {Move{0, 8}, Move{48, 57, PieceType::queen, capture},
                         Move{36, 43, PieceType::none, capture | en_passant}})
        require(!qsearch_delta_candidate(special, PieceType::pawn, -10000, 10000),
                "Delta admitted a quiet/special move");
    std::cout << "PASS delta: fixed scale, strict/int64 boundary and all policy guards\n";
}

void actual_skip_and_boundary(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto root = fen(capture_fen);
        if (mirror) root = reflected(root);
        const auto captures = root.legal_tactical_moves().moves;
        require(captures.size() == 1 && captures.front().is_capture(), "Expected exactly one ordinary capture");
        int stand_pat = 0;
        {
            auto direct = std::make_unique<Interior>(network, root);
            stand_pat = direct->worker.evaluate(root);
            const int alpha = stand_pat + 801;
            require(std::abs(alpha + 1) < Search::mate_threshold, "Boundary test needs an ordinary window");
            require(direct->search(root, alpha) == alpha && direct->worker.nodes == 1,
                    "Actual delta skip entered the child search");
            const auto& stats = direct->worker.qsearch_delta;
            require(stats.eligible_nodes == 1 && stats.candidates == 1 && stats.pruned == 1,
                    "Actual delta skip did not complete exactly once");
            require(direct->worker.evaluate(root) == stand_pat, "Skipped child changed incremental NNUE state");
        }
        for (int offset : {799, 800}) {
            auto direct = std::make_unique<Interior>(network, root);
            direct->search(root, stand_pat + offset);
            require(direct->worker.qsearch_delta.candidates == 0 && direct->worker.nodes > 1,
                    "At/below deficit boundary must search the child");
        }
        auto combined = std::make_unique<Interior>(network, root);
        combined->worker.limits.qsearch_see_pruning = true;
        combined->search(root, stand_pat + 801);
        require(combined->worker.qsearch_delta.pruned == 1 && combined->worker.qsearch_see.evaluations == 0
                && combined->worker.qsearch_see.pruned == 0, "SEE counted or inspected a delta-skipped child");

        auto losing = fen("3q2k1/ppp2ppp/8/8/5B2/8/PPP2PPP/RN2K3 w - - 0 1");
        if (mirror) losing = reflected(losing);
        const auto sacrifice = move(losing, mirror ? "f5c2" : "f4c7");
        require(static_exchange(losing, sacrifice) < 0, "SEE complement must lose exchange material");
        int see_score = 0;
        for (bool delta : {false, true}) {
            auto see = std::make_unique<Interior>(network, losing);
            see->worker.limits.qsearch_see_pruning = true;
            see->worker.limits.qsearch_delta_pruning = delta;
            see->worker.qsearch_delta.enabled = delta;
            const int alpha = see->worker.evaluate(losing) + 800;
            const int score = see->search(losing, alpha);
            require(see->worker.qsearch_see.evaluations == 1 && see->worker.qsearch_see.pruned == 1
                    && see->worker.qsearch_delta.candidates == 0 && see->worker.nodes == 1,
                    "Non-proposing delta changed the existing SEE skip");
            if (!delta) see_score = score;
            else require(score == see_score, "SEE-only and non-proposing delta returned different scores");
        }
    }
    std::cout << "PASS delta: both-color real skips, exact deficit boundary, NNUE restore and SEE precedence\n";
}

void actual_exclusions(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        for (const auto mode : {Mode::null_probe, Mode::verification, Mode::probcut}) {
            auto root = fen(capture_fen);
            if (mirror) root = reflected(root);
            auto direct = std::make_unique<Interior>(network, root, 1);
            direct->search(root, 12000, 1, 1, mode);
            require(direct->worker.qsearch_delta.eligible_nodes == 0, "Speculative qsearch invoked delta");
        }
        for (const char* value : {
                "4r1k1/ppp2ppp/8/8/8/5N2/PPP2PPP/4K3 w - - 0 1",
                "r3k2r/ppp2ppp/P7/4p3/8/5N2/1PP2PPP/R3K2R w - - 0 1",
                "r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 80 41",
                "4k3/pp6/8/4p3/8/5N2/PP6/4K3 w - - 0 1"}) {
            auto root = fen(value);
            if (mirror) root = reflected(root);
            auto direct = std::make_unique<Interior>(network, root, 1);
            direct->search(root, 12000);
            require(direct->worker.qsearch_delta.eligible_nodes == 0, "Actual protected position invoked delta");
        }
        auto root = fen(capture_fen);
        if (mirror) root = reflected(root);
        for (int ply : {0, Search::max_ply - 1}) {
            auto direct = std::make_unique<Interior>(network, root, 1);
            direct->search(root, 12000, 1, ply);
            require(direct->worker.qsearch_delta.eligible_nodes == 0, "Root/max-ply quiescence invoked delta");
        }
        {
            auto direct = std::make_unique<Interior>(network, root, 1);
            const int stand = direct->worker.evaluate(root);
            direct->search(root, stand - 1, 2);
            require(direct->worker.qsearch_delta.eligible_nodes == 0,
                    "Stand-pat converted original wide window into a delta scout");
        }
        for (int table_limit : {0, 7}) {
            auto direct = std::make_unique<Interior>(network, root, 1);
            direct->shared.tablebase_limit = table_limit;
            const int band = table_limit ? tablebase_score : Search::mate_threshold;
            direct->search(root, band - 1);
            require(direct->worker.qsearch_delta.eligible_nodes == 0, "Special score band invoked delta");
        }
        auto repeated = fen("r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 8 5");
        if (mirror) repeated = reflected(repeated);
        auto direct = std::make_unique<Interior>(network, repeated, 1);
        direct->worker.game_history = {repeated.key(), 1, repeated.key()};
        direct->search(repeated, 12000);
        require(direct->worker.qsearch_delta.eligible_nodes == 0, "Current twofold invoked delta");
    }
    std::cout << "PASS delta: actual mode, root, check, pawn, history, ending, clock and entry-window exclusions\n";
}

void protected_children_and_specials(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto mate = fen("6rk/pp5p/6Q1/8/8/5K2/PP6/RN5R w - - 0 1");
        if (mirror) mate = reflected(mate);
        {
            auto direct = std::make_unique<Interior>(network, mate);
            const int score = direct->search(mate, 12000);
            require(score >= Search::mate_threshold && direct->worker.qsearch_delta.protected_checks > 0,
                    "Delta removed a real checking mate");
        }
        auto root = fen("7k/5Q2/6p1/8/4K3/8/PPP5/RNBR4 w - - 0 1");
        if (mirror) root = reflected(root);
        const auto capture_move = move(root, mirror ? "f2g3" : "f7g6");
        require(root.legal_tactical_moves().moves.size() == 1, "Stalemate fixture needs exactly one capture");
        auto child = root;
        child.make_move(capture_move);
        require(!child.in_check(child.turn()) && child.legal_moves().empty(), "Child must be actual stalemate");
        {
            auto direct = std::make_unique<Interior>(network, root);
            const int alpha = direct->worker.evaluate(root) + 801;
            require(std::abs(alpha + 1) < Search::mate_threshold, "Stalemate probe needs an ordinary deficit");
            direct->search(root, alpha);
            require(direct->worker.qsearch_delta.protected_terminals == 1
                    && direct->worker.qsearch_delta.pruned == 0 && direct->worker.nodes == 2,
                    "Delta removed a nonchecking terminal child");
        }
        for (const char* value : {
                "4k3/pp3ppp/8/3pP3/8/8/PP3PPP/4K3 w - d6 0 1",
                "1r2k3/Pp3ppp/8/8/8/8/1P3PPP/4K3 w - - 0 1"}) {
            auto special = fen(value);
            if (mirror) special = reflected(special);
            auto direct = std::make_unique<Interior>(network, special, 1);
            direct->search(special, 12000);
            require(direct->worker.qsearch_delta.candidates == 0, "Delta proposed an EP/promotion capture");
        }
        for (const char* value : {"7k/6Q1/6K1/8/8/8/8/8 b - - 100 51",
                                 "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"}) {
            auto terminal = fen(value);
            if (mirror) terminal = reflected(terminal);
            auto direct = std::make_unique<Interior>(network, terminal);
            const int score = direct->search(terminal, 12000);
            require(score == (terminal.in_check(terminal.turn()) ? -Search::mate_score + 1 : 0)
                    && direct->worker.qsearch_delta.eligible_nodes == 0,
                    "Terminal/rule-50 precedence changed");
        }
    }
    std::cout << "PASS delta: both-color checking mate/stalemate children, specials and terminal precedence\n";
}

void interrupted_child_restoration(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto root = fen(capture_fen);
        if (mirror) root = reflected(root);
        const auto before = root;
        const auto capture_move = root.legal_tactical_moves().moves.front();
        auto child = root;
        child.make_move(capture_move);
        for (int scenario : {0, 1, 2}) {
            auto direct = std::make_unique<Interior>(network, root, scenario == 0 ? 1 : 10000);
            const int stand = direct->worker.evaluate(root);
            const auto history = direct->worker.game_history;
            if (scenario != 0) {
                child_interrupt::position = &root;
                child_interrupt::child_key = child.key();
                child_interrupt::stop = scenario == 1 ? &direct->shared.stopped : nullptr;
                child_interrupt::reached = false;
            }
            bool failed = false;
            int score = 0;
            try { score = direct->search(root, stand + 801); }
            catch (const std::bad_alloc&) { failed = true; }
            child_interrupt::disarm();
            require(scenario == 0 || child_interrupt::reached, "Fault/stop missed the actual child mobility allocation");
            require(failed == (scenario == 2), "Child allocation failure was swallowed or manufactured");
            same_position(root, before);
            require(direct->worker.game_history == history && direct->worker.evaluate(root) == stand,
                    "Interrupted child damaged history/NNUE state");
            require(direct->worker.qsearch_delta.candidates == 1 && direct->worker.qsearch_delta.pruned == 0,
                    "Incomplete child inspection counted a completed skip");
            if (scenario < 2)
                require(score == 0 && direct->worker.aborted && direct->worker.nodes == 1,
                        "Inspected child did not honor published stop/node limit");
        }
    }
    std::cout << "PASS delta: both-color node-limit/external-stop/allocation-failure child restoration\n";
}

struct Observation { SearchResult result; std::vector<SearchInfo> reports; };
Observation run(Search& search, const Position& root, const SearchLimits& limits, bool reset = true) {
    if (reset) search.reset_stop();
    Observation out;
    out.result = search.search(root, {}, limits, [&](const SearchInfo& report) {
        auto replay = root;
        for (auto item : report.pv) {
            require(legal(replay, item), "Delta exposed an illegal PV");
            replay.make_move(item);
        }
        out.reports.push_back(report);
    });
    require(legal(root, out.result.best), "Delta exposed an illegal best move");
    auto child = root;
    child.make_move(out.result.best);
    if (out.result.ponder.valid()) require(legal(child, out.result.ponder), "Delta exposed an illegal ponder move");
    counters(out.result.qsearch_delta, limits.qsearch_delta_pruning, limits.diagnostics);
    require(std::accumulate(out.result.smp.worker_nodes.begin(), out.result.smp.worker_nodes.end(),
                            std::uint64_t{0}) == out.result.nodes, "Joined delta worker nodes differ");
    if (limits.nodes) require(out.result.nodes <= limits.nodes, "Delta exceeded global node cap");
    return out;
}
void same(const Observation& a, const Observation& b) {
    require(a.result.best == b.result.best && a.result.ponder == b.result.ponder
            && a.result.score == b.result.score && a.result.nodes == b.result.nodes
            && a.result.depth == b.result.depth && a.reports.size() == b.reports.size(),
            "Delta policy clear/diagnostics changed equivalent fresh search");
    for (std::size_t i = 0; i < a.reports.size(); ++i)
        require(a.reports[i].depth == b.reports[i].depth && a.reports[i].seldepth == b.reports[i].seldepth
                && a.reports[i].nodes == b.reports[i].nodes && a.reports[i].score == b.reports[i].score
                && a.reports[i].pv == b.reports[i].pv, "Equivalent delta iteration signatures differ");
}
void public_lifecycle(const nnue::Network& network) {
    require(!SearchLimits{}.qsearch_delta_pruning, "Delta must remain default-off");
    Search search(network, 1);
    auto root = fen(capture_fen);
    SearchLimits request;
    request.depth = 5;
    request.nodes = 30000;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    const auto baseline = run(search, root, request);
    request.qsearch_delta_pruning = true;
    const auto candidate = run(search, root, request);
    request.qsearch_delta_pruning = false;
    same(run(search, root, request), baseline);
    request.qsearch_delta_pruning = true;
    same(run(search, root, request), candidate);
    search.clear();
    request.diagnostics = false;
    same(run(search, root, request), candidate);
    request.diagnostics = true;
    for (int threads : {1, 4}) {
        search.set_threads(threads);
        request.depth = 0;
        for (std::uint64_t cap : {1, 257, 4096}) {
            request.nodes = cap;
            const auto result = run(search, root, request).result;
            require(result.nodes == cap && result.diagnostics->stop_reason == StopReason::node_limit,
                    "Delta lost exact aggregate node limit");
        }
        request.nodes = 0;
        search.reset_stop();
        search.stop();
        require(run(search, root, request, false).result.nodes == 0, "Delta preparation erased published stop");
        request.received_at = Clock::now() - std::chrono::seconds(1);
        request.movetime_ms = 1;
        require(run(search, root, request).result.nodes == 0, "Delta entered expired clock search");
        request.received_at.reset();
        request.movetime_ms = -1;
        request.depth = 2;
        require(run(search, root, request).result.depth == 2, "Delta post-stop reuse failed");
    }
    std::cout << "PASS delta: opt-in, policy reset, diagnostic parity and one/four-worker lifecycle\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: qsearch-delta-search-test NETWORK");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned NNUE network");
        policy_boundaries();
        actual_skip_and_boundary(network);
        actual_exclusions(network);
        protected_children_and_specials(network);
        interrupted_child_restoration(network);
        public_lifecycle(network);
        std::cout << "PASS delta production-branch and public search checks\n";
    } catch (const std::exception& error) {
        child_interrupt::disarm();
        std::cerr << "FAIL delta search: " << error.what() << '\n';
        return 1;
    }
}
