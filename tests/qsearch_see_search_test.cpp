/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/exchange.hpp"
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

Position reflected(const Position& position) {
    std::istringstream input(position.fen());
    std::string placement, side, rights, ep;
    input >> placement >> side >> rights >> ep;
    require(rights == "-", "Fixture reflection deliberately excludes castling");
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
    if (ep != "-") ep[1] = static_cast<char>('9' - ep[1] + '0');
    return fen(result + (side == "w" ? " b - " : " w - ") + ep + " 0 1");
}

/** Independently composed chess-rule fixtures, also checked by python-chess
 * in the UCI suite. These inspect the production predicates with actual board
 * facts; they do not expose or claim to observe internal quiescence branches.
 */
void tactical_exemptions() {
    using namespace search_policy;
    struct Case {
        const char* position;
        const char* move;
        int see;
        bool parent_check;
        bool child_check;
        bool terminal;
        bool ordinary_capture;
    };
    const Case cases[] = {
        {"6k1/pp6/4p3/3p4/8/8/PP6/RN1Q2K1 w - - 0 1",
         "d1d5", -800, false, false, false, true},
        {"6rk/pp5p/6Q1/8/8/8/PP6/RN2K3 w - - 0 1",
         "g6h7", -800, false, true, false, true},
        {"4r3/3Q1bk1/8/8/8/8/PP6/RN2K3 w - - 0 1",
         "d7e8", -400, true, false, false, true},
        {"7k/5Q2/5Kr1/8/8/8/8/8 w - - 0 1",
         "f7g6", 500, true, false, true, true},
        {"4k2r/pp4pp/8/2pP4/8/8/PP4PP/R3K3 w - c6 0 1",
         "d5c6", 0, false, false, false, false},
    };
    for (const auto& item : cases) {
        for (const bool mirror : {false, true}) {
            auto position = fen(item.position);
            std::string notation = item.move;
            if (mirror) {
                position = reflected(position);
                notation[1] = static_cast<char>('9' - notation[1] + '0');
                notation[3] = static_cast<char>('9' - notation[3] + '0');
            }
            const auto move = parse_uci_move(position, notation);
            require(move.has_value(), "Tactical fixture must be a legal move");
            const auto before = position.fen();
            const auto key = position.key();
            const int see = static_exchange(position, *move);
            require(see == item.see, "Fixture must retain its specified exchange loss or gain");
            require(position.in_check(position.turn()) == item.parent_check,
                    "Fixture check-evasion property differs");
            QSearchSeeContext context;
            context.ply = 1;
            context.scout = true;
            context.pieces = std::popcount(position.occupied());
            context.in_check = position.in_check(position.turn());
            require(qsearch_see_eligible(context) == (!item.parent_check && context.pieces > 8),
                    "Board-backed evasions must fail the node predicate");
            require(qsearch_see_capture(move->is_capture(), move->promotion != PieceType::none,
                                       (move->flags & en_passant) != 0) == item.ordinary_capture,
                    "Special capture admitted to SEE pruning");
            const auto undo = position.make_move(*move);
            const bool checked = position.in_check(position.turn());
            const bool mobile = !position.legal_moves().empty();
            require(checked == item.child_check && mobile != item.terminal,
                    "Actual checking-sacrifice/terminal fixture property differs");
            require(qsearch_see_skip(see, checked, mobile)
                        == (see < 0 && !item.child_check && !item.terminal),
                    "Child protection must use actual check and mobility");
            if (item.terminal)
                require(!qsearch_see_skip(-1, checked, mobile),
                        "Even a hypothetical negative estimate cannot discard stalemate");
            position.unmake_move(*move, undo);
            require(position.fen() == before && position.key() == key,
                    "Inspecting a skipped child must preserve every root field");
        }
    }
    for (const bool mirror : {false, true}) {
        auto position = fen("r4k2/1P6/8/8/8/8/PP4pp/R3K3 w - - 0 1");
        if (mirror) position = reflected(position);
        for (const auto suffix : {'q', 'r', 'b', 'n'}) {
            std::string notation = mirror ? "b2a1" : "b7a8";
            notation += suffix;
            const auto move = parse_uci_move(position, notation);
            require(move.has_value() && move->is_capture(), "Capture-promotion fixture must be legal");
            require(!qsearch_see_capture(true, move->promotion != PieceType::none, false),
                    "Every color and underpromotion choice must retain ordinary quiescence");
        }
    }
}

SearchLimits limits() {
    SearchLimits request;
    request.late_move_reductions = false; // Combined-policy cases opt in explicitly.
    request.depth = 5;
    request.nodes = 200000;
    request.qsearch_see_pruning = true;
    request.diagnostics = true;
    request.syzygy_probe_limit = 0;
    return request;
}

struct Observation {
    SearchResult result;
    std::vector<SearchInfo> reports;
};

Observation run(Search& search, const Position& root, SearchLimits request,
                bool reset_stop = true) {
    if (reset_stop) search.reset_stop();
    Observation result;
    result.result = search.search(root, {}, request, [&](const SearchInfo& info) {
        auto position = root;
        for (const auto move : info.pv) {
            require(legal(position, move), "Quiescence exposed an illegal PV");
            position.make_move(move);
        }
        result.reports.push_back(info);
    });
    auto position = root;
    const auto& final = result.result;
    if (position.legal_moves().empty()) require(!final.best.valid(), "Terminal root returned a move");
    else {
        require(legal(position, final.best), "Search returned an illegal bestmove");
        position.make_move(final.best);
        if (final.ponder.valid()) require(legal(position, final.ponder), "Search returned illegal ponder");
    }
    require(final.qsearch_see.enabled == request.qsearch_see_pruning,
            "QSearch SEE option snapshot changed during search");
    require(final.qsearch_see.pruned <= final.qsearch_see.evaluations,
            "More captures pruned than inspected");
    if (!request.diagnostics || !request.qsearch_see_pruning)
        require(final.qsearch_see.evaluations == 0 && final.qsearch_see.pruned == 0,
                "Disabled diagnostics retained counters");
    require(std::accumulate(final.smp.worker_nodes.begin(), final.smp.worker_nodes.end(),
                            std::uint64_t{0}) == final.nodes, "Joined worker totals differ");
    if (final.diagnostics) {
        std::uint64_t leader = 0;
        for (const auto& iteration : final.diagnostics->iterations) leader += iteration.nodes;
        require(leader == final.smp.worker_nodes.front(), "Unfinished work missing from diagnostics");
    }
    if (request.nodes) require(final.nodes <= request.nodes, "Aggregate node ceiling exceeded");
    return result;
}

void same(const Observation& left, const Observation& right) {
    const auto& a = left.result;
    const auto& b = right.result;
    require(a.nodes == b.nodes && a.depth == b.depth && a.score == b.score
            && a.best == b.best && a.ponder == b.ponder, "Fresh search signature differs");
    require(left.reports.size() == right.reports.size(), "Iteration counts differ");
    for (std::size_t i = 0; i < left.reports.size(); ++i) {
        const auto& x = left.reports[i];
        const auto& y = right.reports[i];
        require(x.depth == y.depth && x.seldepth == y.seldepth && x.nodes == y.nodes
                && x.score == y.score && x.pv == y.pv, "Per-iteration signature differs");
    }
}

void activation_and_reuse(Search& search, const Position& root) {
    auto request = limits();
    request.qsearch_see_pruning = false;
    search.clear();
    const auto baseline = run(search, root, request);
    request.qsearch_see_pruning = true;
    const auto candidate = run(search, root, request);
    require(candidate.result.depth == request.depth && candidate.result.qsearch_see.pruned > 0,
            "Bounded activation must actually prune quiescence captures");
    request.qsearch_see_pruning = false;
    same(run(search, root, request), baseline);
    request.qsearch_see_pruning = true;
    same(run(search, root, request), candidate);
    search.clear();
    request.diagnostics = false;
    same(run(search, root, request), candidate);
    search.clear();
    request.diagnostics = true;
    same(run(search, root, request), candidate);
    std::cout << "PASS qsearch SEE activation: evaluations "
              << candidate.result.qsearch_see.evaluations << ", pruned "
              << candidate.result.qsearch_see.pruned << '\n';
}

void lifecycle_and_composition(Search& search, const Position& root) {
    for (const int threads : {1, 4}) {
        search.set_threads(threads);
        auto request = limits();
        request.depth = 0;
        for (const std::uint64_t cap : {1, 257, 40000}) {
            search.clear();
            request.nodes = cap;
            const auto result = run(search, root, request).result;
            require(result.nodes == cap && result.smp.threads == threads
                    && result.smp.worker_nodes.size() == static_cast<std::size_t>(threads)
                    && result.diagnostics->stop_reason == StopReason::node_limit,
                    "One node cap must include all joined workers");
        }
        request.nodes = 0;
        search.reset_stop();
        search.stop();
        const auto stopped = run(search, root, request, false).result;
        require(stopped.nodes == 0 && stopped.qsearch_see.evaluations == 0,
                "Published cancellation must survive worker preparation");
        request.received_at = std::chrono::steady_clock::now() - std::chrono::seconds(1);
        request.movetime_ms = 1;
        const auto expired = run(search, root, request).result;
        require(expired.nodes == 0 && expired.qsearch_see.evaluations == 0,
                "An expired clock must preclude quiescence work");
        request = limits();
        search.reset_stop();
        const auto interrupted = search.search(root, {}, request, [&](const SearchInfo& info) {
            if (info.depth == 2) search.stop();
        });
        require(interrupted.depth == 2 && legal(root, interrupted.best)
                && interrupted.diagnostics->stop_reason == StopReason::external_stop,
                "Cancellation must retain the last completed root and join all workers");
        request.depth = 6;
        request.nodes = 120000;
        request.null_move_pruning = true;
        request.reverse_futility_pruning = true;
        request.late_move_reductions = true;
        search.clear();
        const auto combined = run(search, root, request).result;
        require(combined.nullmove.enabled && combined.reverse_futility.enabled && combined.lmr.enabled,
                "Composed search options were lost");
        request = limits();
        request.depth = 2;
        require(run(search, root, request).result.depth == 2, "Post-cancellation search failed");
    }
    search.set_threads(1);
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: qsearch-see-search-test NETWORK");
        tactical_exemptions();
        nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Cannot load pinned network");
        Search search(network, 1);
        const auto root = Position::start();
        const auto before = root.fen();
        const auto key = root.key();
        activation_and_reuse(search, root);
        lifecycle_and_composition(search, root);
        require(root.fen() == before && root.key() == key, "Search altered caller root");
        std::cout << "PASS qsearch SEE: board-backed exclusions, activation, policy reset, diagnostics, "
                     "legal PVs, cancellation, aggregate node caps, 1/4 workers and composition\n";
    } catch (const std::exception& error) {
        std::cerr << "FAIL qsearch SEE search: " << error.what() << '\n';
        return 1;
    }
}
