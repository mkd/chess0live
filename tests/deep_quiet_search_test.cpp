/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"
#include "chess0live/search.hpp"
#include "chess0live/search_policy.hpp"

#include <algorithm>
#include <bit>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using namespace chess0live;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    const auto result = Position::from_fen(text, error);
    if (!result) throw std::runtime_error("Fixture FEN: " + error);
    return *result;
}

bool legal(Position position, Move move) {
    const auto moves = position.legal_moves();
    return std::find(moves.begin(), moves.end(), move) != moves.end();
}

Move parsed(Position position, std::string_view text) {
    const auto result = parse_uci_move(position, text);
    if (!result) throw std::runtime_error("Fixture move: " + std::string(text));
    return *result;
}

/** Swap colors and reflect ranks, preserving draw clocks. These independently
 * composed no-castling fixtures exercise both colors without a second corpus.
 */
Position reflected(const Position& position) {
    std::istringstream input(position.fen());
    std::string placement, side, rights, ep, halfmove, fullmove;
    input >> placement >> side >> rights >> ep >> halfmove >> fullmove;
    require(rights == "-" && ep == "-", "Reflection fixture has unsupported special rights");
    std::vector<std::string> ranks;
    std::istringstream board(placement);
    for (std::string rank; std::getline(board, rank, '/');) ranks.push_back(rank);
    std::reverse(ranks.begin(), ranks.end());
    std::string result;
    for (const auto& rank : ranks) {
        if (!result.empty()) result += '/';
        for (const auto character : rank) {
            const auto byte = static_cast<unsigned char>(character);
            result += static_cast<char>(std::islower(byte) ? std::toupper(byte) : std::tolower(byte));
        }
    }
    return fen(result + (side == "w" ? " b - - " : " w - - ") + halfmove + " " + fullmove);
}

SearchLimits limits(int depth = 7) {
    SearchLimits request;
    request.depth = depth;
    request.nodes = 300000;
    request.late_move_reductions = true;
    request.deep_quiet_reductions = true;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    return request;
}

struct Observation {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

/** Validate real legal PVs and joined node accounting even when the last
 * iteration is interrupted. Counters observe attempts; they are not Elo data.
 */
Observation run(Search& search, const Position& root, const SearchLimits& request,
                bool reset_stop = true, const std::vector<std::uint64_t>& history = {}) {
    const auto before = root.fen();
    const auto key = root.key();
    const auto occupied = root.occupied();
    if (reset_stop) search.reset_stop();
    Observation observation;
    observation.result = search.search(root, history, request, [&](const SearchInfo& info) {
        auto position = root;
        for (const auto move : info.pv) {
            require(legal(position, move), "Deep quiet search exposed an illegal PV");
            position.make_move(move);
        }
        require(info.hashfull >= 0 && info.hashfull <= 1000, "Invalid hash occupancy");
        observation.reports.push_back(info);
    });
    require(root.fen() == before && root.key() == key && root.occupied() == occupied,
            "Search mutated the caller's complete root state");
    auto position = root;
    const auto& result = observation.result;
    if (position.legal_moves().empty()) require(!result.best.valid(), "Terminal root returned a move");
    else {
        require(legal(position, result.best), "Deep quiet search exposed an illegal best move");
        position.make_move(result.best);
        if (result.ponder.valid()) require(legal(position, result.ponder), "Illegal ponder move");
    }
    const auto& d = result.deep_lmr;
    require(d.enabled == request.deep_quiet_reductions, "Deep quiet option snapshot is stale");
    require(d.researches <= d.extra_reductions
            && d.fail_lows + d.verified_cutoffs <= d.researches,
            "Deep quiet verification outcomes exceed attempts");
    require(d.extra_reductions <= result.lmr.reductions && d.researches <= result.lmr.researches
            && d.fail_lows <= result.lmr.fail_lows && d.verified_cutoffs <= result.lmr.verified_cutoffs,
            "Deep quiet counters must be a subset of accepted LMR accounting");
    if (!request.deep_quiet_reductions || !request.late_move_reductions || !request.diagnostics)
        require(d.extra_reductions == 0 && d.researches == 0 && d.fail_lows == 0 && d.verified_cutoffs == 0,
                "Inactive deep quiet diagnostics retained counters");
    require(std::accumulate(result.smp.worker_nodes.begin(), result.smp.worker_nodes.end(),
                            std::uint64_t{0}) == result.nodes, "Joined worker node totals differ");
    if (result.diagnostics) {
        std::uint64_t leader = 0;
        for (const auto& iteration : result.diagnostics->iterations) leader += iteration.nodes;
        require(!result.smp.worker_nodes.empty() && leader == result.smp.worker_nodes.front(),
                "Interrupted leader work is missing from diagnostics");
    }
    if (request.nodes) require(result.nodes <= request.nodes, "Aggregate node ceiling exceeded");
    return observation;
}

void same(const Observation& left, const Observation& right) {
    const auto& a = left.result;
    const auto& b = right.result;
    require(a.nodes == b.nodes && a.depth == b.depth && a.score == b.score
            && a.best == b.best && a.ponder == b.ponder, "Fresh policy result differs");
    require(left.reports.size() == right.reports.size(), "Iteration counts differ");
    for (std::size_t i = 0; i < left.reports.size(); ++i) {
        const auto& x = left.reports[i];
        const auto& y = right.reports[i];
        require(x.depth == y.depth && x.seldepth == y.seldepth && x.nodes == y.nodes
                && x.score == y.score && x.pv == y.pv, "Per-iteration policy signature differs");
    }
}

Observation activation_and_reuse(Search& search, const Position& root) {
    require(!SearchLimits{}.deep_quiet_reductions, "The new candidate must remain opt-in");
    auto request = limits();
    request.deep_quiet_reductions = false;
    search.clear();
    const auto baseline = run(search, root, request);
    request.deep_quiet_reductions = true;
    const auto candidate = run(search, root, request);
    require(candidate.result.deep_lmr.extra_reductions > 0 && candidate.result.lmr.researches > 0
            && candidate.result.lmr.fail_lows + candidate.result.lmr.verified_cutoffs > 0,
            "The activation root must exercise extra reductions and completed shared LMR verification");
    request.deep_quiet_reductions = false;
    same(run(search, root, request), baseline);
    request.deep_quiet_reductions = true;
    same(run(search, root, request), candidate);
    search.clear();
    request.diagnostics = false;
    same(run(search, root, request), candidate);
    std::cout << "PASS deep quiet activation: extra reductions " << candidate.result.deep_lmr.extra_reductions
              << ", re-searches " << candidate.result.deep_lmr.researches << '\n';
    // The initial startpos assertion required an extra-tier alpha-raiser. Six
    // bounded development probes instead observed real extra reductions but
    // no such re-search. Keep that limitation explicit: shared LMR verification
    // runs here and in the existing search suite, while extra-tier verification
    // semantics also require source review. Do not claim the absent event was
    // exercised or tune the policy to manufacture it.

    // Explicit LMR-off is authoritative even if the extra-tier option remains
    // true. Toggling either mode must not leak selective TT/history entries.
    request = limits(3);
    request.late_move_reductions = false;
    request.deep_quiet_reductions = false;
    const auto unreduced = run(search, root, request);
    request.deep_quiet_reductions = true;
    same(run(search, root, request), unreduced);
    return candidate;
}

/** Find the first extra reduction at a bounded deterministic node cap.
 * At that exact boundary the reduced child cannot visit a node. Thus its
 * attempt is visible but no verification/outcome may be published. This
 * locates a correctness event only; it never chooses reduction parameters.
 */
void interrupted_reduction(Search& search, const Position& root, const Observation& complete) {
    auto request = limits();
    std::uint64_t low = 1, high = complete.result.nodes;
    while (low < high) {
        const auto middle = low + (high - low) / 2;
        request.nodes = middle;
        search.clear();
        if (run(search, root, request).result.deep_lmr.extra_reductions > 0) high = middle;
        else low = middle + 1;
    }
    search.clear();
    request.nodes = low;
    const auto result = run(search, root, request).result;
    require(result.nodes == low && result.deep_lmr.extra_reductions == 1 && result.deep_lmr.researches == 0
            && result.deep_lmr.fail_lows == 0 && result.deep_lmr.verified_cutoffs == 0
            && result.diagnostics->stop_reason == StopReason::node_limit
            && !result.diagnostics->iterations.back().completed,
            "Interrupted extra reduction published a verification or completed outcome");
    search.clear();
    same(run(search, root, limits()), complete);
    std::cout << "PASS interrupted extra reduction at node cap " << low << '\n';
}

/** Actual board facts exercise checking quiet tactics and pawn/king protection
 * at a synthetic late scout. These are not claims about a particular internal
 * move's ordering or universal tactical strength.
 */
void board_guards_and_tactics(Search& search) {
    struct Case { const char* fen; const char* move; };
    for (const auto& item : {
        Case{"k7/5ppp/1QK5/8/8/8/5PPP/8 w - - 0 1", "b6b7"}, // Quiet mate, nine pieces.
        Case{"R5k1/ppp3p1/4K3/8/8/8/PPP5/8 b - - 0 1", "g8h7"}, // Quiet evasion.
        Case{"7k/8/8/8/8/4K3/PPP2ppp/8 w - - 0 1", "a2a3"}, // Eight-piece pawn ending.
        Case{"7k/1P6/8/8/8/8/PPP3pp/4K3 w - - 0 1", "b7b8n"}}) { // Breakthrough/underpromotion.
        for (const bool mirror : {false, true}) {
            auto position = fen(item.fen);
            std::string notation = item.move;
            if (mirror) {
                position = reflected(position);
                notation[1] = static_cast<char>('9' - notation[1] + '0');
                notation[3] = static_cast<char>('9' - notation[3] + '0');
            }
            const auto move = parsed(position, notation);
            const auto before = position.fen();
            const auto key = position.key();
            search_policy::LateMoveContext context;
            context.depth = 5;
            context.ply = 1;
            context.searched_moves = 8;
            context.move = move;
            context.moved = position.at(move.from);
            context.parent_in_check = position.in_check(position.turn());
            const int pieces = std::popcount(position.occupied());
            const auto undo = position.make_move(move);
            context.child_in_check = position.in_check(position.turn());
            require(!search_policy::deep_quiet_reduction(context, pieces),
                    "Real quiet tactic, evasion or pawn move bypassed an extra-tier guard");
            position.unmake_move(move, undo);
            require(position.fen() == before && position.key() == key, "Board inspection lost state");
            if (std::string_view(item.move) == "b6b7") {
                const auto result = run(search, position, limits(3)).result;
                require(result.best == move && result.score == Search::mate_score - 1,
                        "The protected quiet mate must retain its move and ply distance");
            }
        }
    }
}

void sparse_and_draw_boundaries(Search& search) {
    auto request = limits(6);
    for (const auto text : {
        "8/8/2k5/2p5/2P5/2K5/8/8 w - - 0 30", // Opposition/zugzwang exposure.
        "8/8/3k4/2p5/2P5/3K4/1N6/8 w - - 0 31", // Sparse minor ending.
        "6k1/1P6/8/8/8/8/6p1/3K4 w - - 0 45", // Both pawn races.
        "7k/6Q1/6K1/8/8/8/8/8 b - - 100 51", // Checkmate precedes rule 50.
        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"}) { // Stalemate.
        for (const bool mirror : {false, true}) {
            const auto position = mirror ? reflected(fen(text)) : fen(text);
            request.deep_quiet_reductions = false;
            search.clear();
            const auto baseline = run(search, position, request);
            request.deep_quiet_reductions = true;
            const auto candidate = run(search, position, request);
            same(candidate, baseline);
            require(candidate.result.deep_lmr.extra_reductions == 0,
                    "A sparse tree cannot use the additional reduction ply");
        }
    }
    auto position = Position::start();
    std::vector<std::uint64_t> history{position.key()};
    for (int cycle = 0; cycle < 2; ++cycle)
        for (const auto text : {"g1f3", "g8f6", "f3g1", "f6g8"}) {
            position.make_move(parsed(position, text));
            history.push_back(position.key());
        }
    const auto draw = run(search, position, request, true, history).result;
    require(draw.nodes == 0 && draw.score == 0 && draw.deep_lmr.extra_reductions == 0,
            "Threefold history must precede reductions");
}

void cancellation_and_workers(Search& search) {
    const auto position = Position::start();
    for (const int threads : {1, 4}) {
        search.set_threads(threads);
        auto request = limits();
        search.reset_stop();
        search.stop();
        const auto stopped = run(search, position, request, false).result;
        require(stopped.nodes == 0 && stopped.deep_lmr.extra_reductions == 0
                && stopped.diagnostics->stop_reason == StopReason::external_stop,
                "Startup lost an already published stop");
        request.movetime_ms = 1;
        request.received_at = std::chrono::steady_clock::now() - std::chrono::seconds(1);
        const auto expired = run(search, position, request).result;
        require(expired.nodes == 0 && expired.deep_lmr.extra_reductions == 0,
                "Expired command receipt allowed speculative work");
        request = limits(12);
        request.nodes = 50000;
        const auto capped = run(search, position, request).result;
        require(capped.nodes == request.nodes && capped.diagnostics->stop_reason == StopReason::node_limit,
                "One/four-worker selective search must respect the aggregate node ceiling");
        search.reset_stop();
        const auto cancelled = search.search(position, {}, limits(), [&](const SearchInfo& info) {
            if (info.depth == 2) search.stop();
        });
        require(cancelled.depth == 2 && legal(position, cancelled.best)
                && cancelled.diagnostics->stop_reason == StopReason::external_stop,
                "Leader cancellation must join every helper and keep the completed result");
        require(run(search, position, limits(2)).result.depth == 2,
                "Search cannot be reused after worker cancellation");
    }
    search.set_threads(1);
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: deep_quiet_search_test network.nnue");
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Network: " + error);
        Search search(network, 16);
        board_guards_and_tactics(search);
        const auto root = Position::start();
        const auto activation = activation_and_reuse(search, root);
        interrupted_reduction(search, root, activation);
        sparse_and_draw_boundaries(search);
        cancellation_and_workers(search);
        std::cout << "PASS deep quiet policy, shared LMR verification, state/cache reuse, tactical/sparse guards and lifecycle\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL deep quiet search: " << error.what() << '\n';
        return 1;
    }
}
