/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute it and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"
#include "chess0live/search.hpp"
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
namespace {
using namespace chess0live;
void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

/** Exercise the coordinator before worker dispatch using actual table files.
 * No sleeps or timing thresholds: expired budgets and published flags are
 * deterministic, including ponderhit delivered before search starts.
 */
void check(nnue::Network& network, const std::filesystem::path& tables, int threads) {
    Search search(network, 1, threads);
    std::string error;
    require(search.set_syzygy_path(tables.string(), error), "Table configuration: " + error);
    require(search.syzygy_largest() >= 3, "Real KQvK tables must be available");
    const auto parsed = Position::from_fen("k7/8/8/8/8/6Q1/8/7K w - - 0 1", error);
    require(parsed.has_value(), "Test FEN: " + error);
    auto position = *parsed;
    const auto legal = position.legal_moves();
    const auto legal_result = [&](const SearchResult& result) {
        require(std::find(legal.begin(), legal.end(), result.best) != legal.end(),
                "Every stopped or limited search must retain a legal root move");
    };
    const auto idle_result = [&](const SearchResult& result) {
        legal_result(result);
        require(result.nodes == 0 && result.tbhits == 0 && result.depth == 0,
                "Preexisting stop/expired clock must skip root probes and all search nodes");
    };
    SearchLimits limits;
    limits.depth = 1;
    limits.move_overhead_ms = 0;
    search.reset_stop();
    search.stop();
    idle_result(search.search(position, {}, limits));

    search.reset_stop();
    limits.movetime_ms = 1;
    limits.received_at = std::chrono::steady_clock::now() - std::chrono::seconds(1);
    idle_result(search.search(position, {}, limits));

    search.reset_stop();
    search.ponderhit();
    limits.received_at.reset();
    limits.movetime_ms = 0;
    limits.ponder = true;
    idle_result(search.search(position, {}, limits));

    search.reset_stop();
    const auto pondering = search.search(position, {}, limits);
    legal_result(pondering);
    require(pondering.depth == 1 && pondering.nodes > 0 && pondering.tbhits >= 1,
            "Unhit ponder ignores the zero clock and must retain root tablebase access");

    search.reset_stop();
    limits.ponder = false;
    limits.movetime_ms = -1;
    limits.nodes = 1;
    const auto bounded = search.search(position, {}, limits);
    legal_result(bounded);
    require(bounded.nodes == 1 && bounded.tbhits == 1,
            "Root probing does not consume or bypass the aggregate one-node search limit");

    require(!search.set_syzygy_path((tables / "missing-test-directory").string(), error)
            && !error.empty() && search.syzygy_largest() == 0, "Invalid path must disable probing");
    search.reset_stop();
    limits.nodes = 0;
    const auto fallback = search.search(position, {}, limits);
    legal_result(fallback);
    require(fallback.depth == 1 && fallback.nodes > 0 && fallback.tbhits == 0,
            "Missing tables must retain ordinary search with zero tablebase hits");
}
} // namespace
int main(int argc, char** argv) {
    try {
        require(argc == 3, "Usage: syzygy-search-test NETWORK TABLE_DIRECTORY");
        chess0live::nnue::Network network;
        std::string error;
        require(network.load(argv[1], error), "Network load: " + error);
        for (const int threads : {1, 4}) check(network, argv[2], threads);
        std::cout << "Syzygy search gates passed: six scenarios each with Threads=1 and Threads=4\n";
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
