/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Deliberately compile the production search in this test translation unit.
// Explicit interior windows exercise rare probe outcomes deterministically;
// no test hook, alternate evaluator, or production search API is introduced.
// Link position/NNUE/exchange/tablebase objects, but not search.o.
#include "../src/search.cpp"

#include <cctype>
#include <cstring>
#include <iostream>
#include <numeric>
#include <sstream>
#include <string>
#include <string_view>

namespace {
using namespace chess0live;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view value) {
    std::string error;
    const auto result = Position::from_fen(value, error);
    if (!result) throw std::runtime_error("Fixture FEN: " + error);
    return *result;
}

Move move(Position position, std::string_view value) {
    const auto result = parse_uci_move(position, value);
    if (!result) throw std::runtime_error("Fixture move: " + std::string(value));
    return *result;
}

bool legal(Position position, Move value) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), value) != moves.end();
}

/** Color reflection is for these independently composed no-castling fixtures.
 * Preserve the counters so rule-50 exclusions are tested in both directions.
 */
Position reflected(const Position& position) {
    std::istringstream input(position.fen());
    std::string placement, side, rights, ep, halfmove, fullmove;
    input >> placement >> side >> rights >> ep >> halfmove >> fullmove;
    require(rights == "-" && ep == "-", "Reflection requires no special rights");
    std::vector<std::string> ranks;
    std::istringstream board(placement);
    for (std::string rank; std::getline(board, rank, '/');) ranks.push_back(rank);
    std::reverse(ranks.begin(), ranks.end());
    std::string result;
    for (const auto& rank : ranks) {
        if (!result.empty()) result += '/';
        for (const auto c : rank) {
            const auto byte = static_cast<unsigned char>(c);
            result += static_cast<char>(std::islower(byte) ? std::toupper(byte) : std::tolower(byte));
        }
    }
    return fen(result + (side == "w" ? " b - - " : " w - - ") + halfmove + " " + fullmove);
}

void counters(const ProbCutStatistics& p, bool enabled, bool diagnostics) {
    require(p.enabled == enabled, "ProbCut option snapshot is stale");
    require(p.see_evaluations <= 3 * p.eligible_nodes
            && p.qsearches <= p.see_evaluations
            && p.qsearch_passes <= p.qsearches
            && p.searches == p.qsearch_passes
            && p.cutoffs + p.rejected <= p.searches,
            "ProbCut diagnostics have impossible attempt/outcome counts");
    if (!enabled || !diagnostics)
        require(p.eligible_nodes == 0 && p.see_evaluations == 0 && p.qsearches == 0
                && p.qsearch_passes == 0 && p.searches == 0 && p.cutoffs == 0 && p.rejected == 0,
                "Inactive ProbCut diagnostics retained counters");
}

/** A direct interior scout has real board/history/NNUE state. Its artificial
 * window selects a correctness branch, never an estimate of playing strength.
 */
struct Interior {
    SharedSearch shared;
    SearchWorker worker;

    Interior(const nnue::Network& network, const Position& root, std::uint64_t nodes = 20000)
        : worker(network, shared, 0) {
        shared.resize(1);
        worker.limits.probcut = true;
        worker.limits.diagnostics = true;
        worker.limits.nodes = nodes;
        worker.limits.syzygy_probe_limit = 0;
        worker.probcut.enabled = true;
        worker.started_ns = now_ns();
        worker.game_history = {root.key()};
        worker.game_history.reserve(Search::max_ply + 1);
    }

    int scout(Position& root, int beta, int depth = 5,
              SearchWorker::Mode mode = SearchWorker::Mode::ordinary) {
        const auto before = root.fen();
        const auto key = root.key();
        const auto occupied = root.occupied();
        const auto history = worker.game_history;
        const int score = worker.alphabeta(root, depth, beta - 1, beta, 1,
                                           false, mix(root.key()), SearchWorker::no_previous_move, mode);
        require(root.fen() == before && root.key() == key && root.occupied() == occupied
                && worker.game_history == history, "Probe failed to restore board or real history");
        counters(worker.probcut, true, true);
        return score;
    }
};

const char* capture_fen = "r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 0 1";

void policy_boundaries(const nnue::Network& network) {
    using namespace search_policy;
    ProbCutContext base;
    base.depth = 5;
    base.ply = 1;
    base.non_pawns = 2;
    base.pawns = 1;
    base.pieces = 9;
    base.legal_moves = 2;
    base.scout = true;
    require(probcut_eligible(base) && !probcut_eligible({}), "ProbCut eligibility boundary changed");
    for (auto member : {&ProbCutContext::pv_node, &ProbCutContext::in_check,
                        &ProbCutContext::special_window, &ProbCutContext::speculative,
                        &ProbCutContext::repeated, &ProbCutContext::advanced_pawn}) {
        auto context = base;
        context.*member = true;
        require(!probcut_eligible(context), "A protected node became ProbCut eligible");
    }
    for (int depth : {-1, 0, 1, 4, 5, 6, 126}) {
        auto context = base;
        context.depth = depth;
        require(probcut_eligible(context) == (depth >= 5), "Depth eligibility boundary changed");
        if (depth >= 5) require(probcut_child_depth(depth) == depth - 4, "Probe depth changed");
    }
    for (int ply : {-1, 0, 1, 126}) {
        auto context = base;
        context.ply = ply;
        require(probcut_eligible(context) == (ply > 0), "Root exclusion changed");
    }
    for (unsigned halfmove : {0U, 79U, 80U, 100U, std::numeric_limits<unsigned>::max()}) {
        auto context = base;
        context.halfmove = halfmove;
        require(probcut_eligible(context) == (halfmove < 80), "Rule-50-near boundary changed");
    }
    for (int count : {0, 1, 2, 3}) {
        auto context = base;
        context.non_pawns = count;
        require(probcut_eligible(context) == (count >= 2), "Nonpawn material guard changed");
        context = base;
        context.pawns = count;
        require(probcut_eligible(context) == (count >= 1), "Pawn material guard changed");
        context = base;
        context.legal_moves = static_cast<std::size_t>(count);
        require(probcut_eligible(context) == (count >= 2), "Forced-node guard changed");
    }
    for (int count : {0, 7, 8, 9, 32}) {
        auto context = base;
        context.pieces = count;
        require(probcut_eligible(context) == (count > 8), "Tablebase-size boundary changed");
    }
    base.scout = false;
    require(!probcut_eligible(base), "Wide-window node became eligible");
    require(probcut_margin == 200 && probcut_capture_limit == 3, "Frozen policy constants changed");
    require(probcut_capture(true, false, false) && !probcut_capture(false, false, false)
            && !probcut_capture(true, true, false) && !probcut_capture(true, false, true),
            "Probe move filter admitted quiet or special moves");

    // Exercise the actual raised-window gate, not just a manufactured context.
    // Probe the representable ordinary score immediately below the limit and
    // both excluded boundaries. A node cap keeps all continuing searches short.
    for (int table_limit : {0, 7}) {
        const int band = table_limit ? tablebase_score : Search::mate_threshold;
        for (int beta : {band - probcut_margin - 1, band - probcut_margin, -band + 1}) {
            auto root = fen(capture_fen);
            Interior actual(network, root, 257);
            actual.shared.tablebase_limit = table_limit;
            actual.scout(root, beta);
            const bool eligible = beta == band - probcut_margin - 1;
            require((actual.worker.probcut.eligible_nodes != 0) == eligible,
                    "Raised window crossed a mate/tablebase boundary");
            require(actual.worker.probcut.cutoffs == 0,
                    "Ordinary fixture manufactured a special-band cutoff");
        }
    }
    std::cout << "PASS ProbCut: all policy guards and actual mate/tablebase threshold boundaries\n";
}

/** A low ordinary window must complete both stages and return only beta. The
 * reduced result must not become an original-depth cache entry or fabricated PV.
 */
void cutoff_and_interrupt(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto root = fen(capture_fen);
        if (mirror) root = reflected(root);
        Interior completed(network, root);
        const int beta = -20000;
        require(completed.scout(root, beta) == beta && !completed.worker.aborted,
                "Completed ProbCut must return the original window edge");
        const auto& p = completed.worker.probcut;
        require(p.qsearches == 1 && p.qsearch_passes == 1 && p.searches == 1 && p.cutoffs == 1,
                "Controlled capture did not exercise both actual probe stages");
        require(completed.worker.pv_length[1] == 1 && completed.worker.cache.stores == 0,
                "Heuristic cutoff published a line or original-depth cache bound");
        require(!completed.worker.probe(completed.worker.table_key(root, mix(root.key()))),
                "Heuristic cutoff installed a transposition entry");

        // This fixture's capture leaves no opposing capture. Its qsearch uses
        // one visit, so a two-node cap interrupts the reduced search entry.
        Interior interrupted(network, root, 2);
        require(interrupted.scout(root, beta) == 0 && interrupted.worker.aborted
                && interrupted.worker.nodes == 2, "Probe did not respect the exact node ceiling");
        const auto& stop = interrupted.worker.probcut;
        require(stop.qsearch_passes == 1 && stop.searches == 1 && stop.cutoffs == 0
                && stop.rejected == 0 && interrupted.worker.cache.stores == 0,
                "Interrupted verification was misreported as a completed decision");
    }
    std::cout << "PASS ProbCut: both-color cutoff, direct TT/PV exclusion and interrupted second stage\n";
}

/** Qsearch cannot see the quiet ...Qg1# defense after Rxb7. The reduced legal
 * search must reject the apparent capture. The window comes from a separate
 * qsearch solely to exercise this contrast; no policy parameter is fitted.
 */
void quiet_defense(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto root = fen("6k1/1p3ppp/8/2b5/8/4q3/P2N2PP/1R5K w - - 0 1");
        if (mirror) root = reflected(root);
        const auto capture = move(root, mirror ? "b8b2" : "b1b7");
        require(static_exchange(root, capture) >= 0, "Quiet-defense capture must pass SEE");
        auto child = root;
        child.make_move(capture);
        const auto defense = move(child, mirror ? "e6g8" : "e3g1");
        require(!defense.is_capture(), "The defense must be invisible to ordinary stand-pat qsearch");
        auto terminal = child;
        terminal.make_move(defense);
        require(terminal.in_check(terminal.turn()) && terminal.legal_moves().empty(),
                "Quiet defense must actually deliver mate");
        Interior screen(network, child);
        const int qscore = -screen.worker.quiescence(child, -infinity, infinity, 2,
                                                    SearchWorker::Mode::probcut);
        require(!screen.worker.aborted && std::abs(qscore) < Search::mate_threshold - 500,
                "Quiet-defense screen must remain ordinary evaluation evidence");
        Interior actual(network, root);
        actual.scout(root, qscore - search_policy::probcut_margin - 1);
        require(actual.worker.probcut.qsearch_passes == 1 && actual.worker.probcut.searches == 1
                && actual.worker.probcut.rejected == 1 && actual.worker.probcut.cutoffs == 0,
                "Reduced legal search failed to reject the quiet mating defense");
    }
    std::cout << "PASS ProbCut: both-color quiet mating defense rejects qsearch evidence\n";
}

void checking_mate_child(const nnue::Network& network) {
    for (bool mirror : {false, true}) {
        auto root = fen("6rk/pp5p/6Q1/8/8/5K2/PP6/RN5R w - - 0 1");
        if (mirror) root = reflected(root);
        const auto capture = move(root, mirror ? "h8h2" : "h1h7");
        auto terminal = root;
        terminal.make_move(capture);
        require(terminal.in_check(terminal.turn()) && terminal.legal_moves().empty(),
                "Checking capture fixture must actually mate");
        Interior actual(network, root);
        const int score = actual.scout(root, 10000);
        require(!actual.worker.aborted && score >= Search::mate_threshold,
                "Ordinary search lost the checking capture's mate");
        require(actual.worker.probcut.qsearches > 0 && actual.worker.probcut.qsearch_passes == 0
                && actual.worker.probcut.cutoffs == 0,
                "Special mate score was accepted as ordinary ProbCut evidence");
    }
    std::cout << "PASS ProbCut: checking terminal children retain ordinary mating scores\n";
}

/** Probe mode uses real repetition/rule-50 state but cannot consume or mutate
 * the ordinary TT, selective policies, killers, histories or countermoves.
 */
void isolated_mode(const nnue::Network& network) {
    auto root = fen(capture_fen);
    Interior probe(network, root, 2000);
    auto& w = probe.worker;
    w.limits.null_move_pruning = true;
    w.limits.reverse_futility_pruning = true;
    w.limits.qsearch_see_pruning = true;
    w.limits.deep_quiet_reductions = true;
    w.limits.countermove_ordering = true;
    w.history_score[0][0][1] = 123;
    w.killers[2][0] = move(root, "f3e5");
    w.countermoves[0] = w.killers[2][0];
    const auto history = w.history_score;
    const auto killers = w.killers;
    const auto replies = w.countermoves;
    const auto key = w.table_key(root, mix(root.key()));
    w.save(key, move(root, "f3e5"), 12345, 10, 1, Bound::exact);
    w.cache = {};
    const auto table = probe.shared.table;
    const int score = probe.scout(root, 100, 5, SearchWorker::Mode::probcut);
    require(score != 12345 && w.nodes > 1 && w.cache.probes == 0 && w.cache.stores == 0,
            "Isolated probe consumed or stored an ordinary TT result");
    require(std::memcmp(table.data(), probe.shared.table.data(), table.size() * sizeof(Bucket)) == 0,
            "Isolated probe changed the ordinary transposition table");
    require(w.history_score == history && w.killers == killers && w.countermoves == replies,
            "Isolated probe learned ordinary ordering state");
    require(w.probcut.eligible_nodes == 0 && w.lmr.reductions == 0 && w.nullmove.probes == 0
            && w.reverse_futility.evaluations == 0 && w.qsearch_see.evaluations == 0,
            "Isolated probe recursively invoked a selective policy");

    auto repeated_root = fen("r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 8 5");
    Interior repeat(network, repeated_root);
    repeat.worker.game_history = {repeated_root.key(), 1, repeated_root.key(), 2, repeated_root.key()};
    require(repeat.scout(repeated_root, 100, 5, SearchWorker::Mode::probcut) == 0
            && repeat.worker.nodes == 1, "Probe mode ignored a real threefold draw");
    auto fifty = fen("r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 100 51");
    Interior draw(network, fifty);
    require(draw.scout(fifty, 100, 5, SearchWorker::Mode::probcut) == 0 && draw.worker.nodes == 1,
            "Probe mode ignored a real rule-50 draw");
    std::cout << "PASS ProbCut: real draws and complete speculative-policy/cache/ordering isolation\n";
}

struct Observation {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

Observation run(Search& search, const Position& root, const SearchLimits& limits,
                bool reset = true) {
    if (reset) search.reset_stop();
    Observation out;
    out.result = search.search(root, {}, limits, [&](const SearchInfo& info) {
        auto replay = root;
        for (const auto item : info.pv) {
            require(legal(replay, item), "ProbCut exposed an illegal PV");
            replay.make_move(item);
        }
        out.reports.push_back(info);
    });
    auto replay = root;
    if (!replay.legal_moves().empty()) {
        require(legal(replay, out.result.best), "ProbCut exposed an illegal best move");
        replay.make_move(out.result.best);
        if (out.result.ponder.valid()) require(legal(replay, out.result.ponder), "Illegal ponder move");
    } else require(!out.result.best.valid(), "Terminal root returned a move");
    counters(out.result.probcut, limits.probcut, limits.diagnostics);
    require(std::accumulate(out.result.smp.worker_nodes.begin(), out.result.smp.worker_nodes.end(),
                            std::uint64_t{0}) == out.result.nodes, "Joined worker nodes differ");
    if (limits.nodes) require(out.result.nodes <= limits.nodes, "Aggregate node cap exceeded");
    return out;
}

void same(const Observation& a, const Observation& b) {
    require(a.result.best == b.result.best && a.result.ponder == b.result.ponder
            && a.result.score == b.result.score && a.result.nodes == b.result.nodes
            && a.result.depth == b.result.depth && a.reports.size() == b.reports.size(),
            "Policy toggle or diagnostics changed the equivalent fresh search");
    for (std::size_t i = 0; i < a.reports.size(); ++i)
        require(a.reports[i].depth == b.reports[i].depth && a.reports[i].seldepth == b.reports[i].seldepth
                && a.reports[i].nodes == b.reports[i].nodes && a.reports[i].score == b.reports[i].score
                && a.reports[i].pv == b.reports[i].pv, "Equivalent iteration signatures differ");
}

void public_lifecycle(const nnue::Network& network) {
    require(!SearchLimits{}.probcut, "ProbCut must remain opt-in");
    Search search(network, 1);
    auto root = fen(capture_fen);
    SearchLimits request;
    request.depth = 6;
    request.nodes = 30000;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    const auto baseline = run(search, root, request);
    request.probcut = true;
    const auto candidate = run(search, root, request);
    request.probcut = false;
    same(run(search, root, request), baseline);
    request.probcut = true;
    same(run(search, root, request), candidate);
    search.clear();
    request.diagnostics = false;
    same(run(search, root, request), candidate);
    for (int threads : {1, 4}) {
        search.set_threads(threads);
        request.depth = 0;
        request.diagnostics = true;
        for (std::uint64_t cap : {1, 257, 4096}) {
            request.nodes = cap;
            const auto result = run(search, root, request).result;
            require(result.nodes == cap && result.diagnostics->stop_reason == StopReason::node_limit,
                    "Exact global node limit or stop reason changed");
        }
        request.nodes = 0;
        search.reset_stop();
        search.stop();
        require(run(search, root, request, false).result.nodes == 0,
                "Already-published stop was erased by preparation");
        request.received_at = Clock::now() - std::chrono::seconds(1);
        request.movetime_ms = 1;
        require(run(search, root, request).result.nodes == 0, "Expired clock entered search");
        request.received_at.reset();
        request.movetime_ms = -1;
        request.depth = 2;
        require(run(search, root, request).result.depth == 2, "Post-cancellation reuse failed");
    }
    std::cout << "PASS ProbCut: opt-in, policy clearing, diagnostic parity and one/four-worker lifecycle\n";
}

/** Material-losing sacrifices remain legal candidates for ordinary search;
 * SEE filtering only chooses optional ProbCut probes. These tests do not assert
 * that a finite-depth engine proves every sacrifice sound or unsound.
 */
void sacrificed_material(const nnue::Network& network) {
    Search search(network, 1);
    for (bool mirror : {false, true}) {
        auto root = fen("3q2k1/ppp2ppp/8/8/5B2/8/PPP2PPP/RN2K3 w - - 0 1");
        if (mirror) root = reflected(root);
        const auto sacrifice = move(root, mirror ? "f5c2" : "f4c7");
        require(static_exchange(root, sacrifice) < 0, "Sacrifice fixture must lose exchange material");
        Interior interior(network, root);
        require(interior.scout(root, -20000) >= -20000 && !interior.worker.aborted,
                "Ordinary search did not finish after screening the sacrifice");
        require(interior.worker.probcut.see_evaluations == 1
                && interior.worker.probcut.qsearches == 0
                && interior.worker.pv_length[1] > 1 && interior.worker.pv[1][1] == sacrifice,
                "Negative SEE must skip only the probe, then search the real sacrifice normally");
        SearchLimits request;
        request.depth = 3;
        request.probcut = true;
        request.diagnostics = true;
        request.syzygy_probe_limit = 0;
        request.searchmoves = {sacrifice};
        require(run(search, root, request).result.best == sacrifice,
                "ProbCut's SEE screen removed an ordinary requested sacrifice");
    }
    std::cout << "PASS ProbCut: both-color losing sacrifices retain ordinary legal search\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: probcut-search-test NETWORK");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned NNUE network");
        policy_boundaries(network);
        cutoff_and_interrupt(network);
        quiet_defense(network);
        checking_mate_child(network);
        isolated_mode(network);
        public_lifecycle(network);
        sacrificed_material(network);
        std::cout << "PASS ProbCut direct and public search checks\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL ProbCut search: " << error.what() << '\n';
        return 1;
    }
}
