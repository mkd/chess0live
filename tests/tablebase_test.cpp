/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 * GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/position.hpp"
#include "chess0live/tablebase.hpp"
#include "data/syzygy_cases.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace {
using namespace chess0live;
using tablebase::RootMove;
using tablebase::Syzygy;
namespace fs = std::filesystem;

void require(bool value, std::string_view message) {
    if (!value) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    auto position = Position::from_fen(text, error);
    if (!position) throw std::runtime_error("Invalid test position: " + error);
    return *position;
}

void configure(Syzygy& tables, const fs::path& directory) {
    std::string error;
    if (!tables.set_path(directory.string(), error))
        throw std::runtime_error("Cannot configure test tables: " + error);
    require(tables.largest() == 4, "Complete pinned fixture set must report four pieces");
}

int rank_of(const std::vector<RootMove>& moves, std::string_view uci) {
    for (const auto& move : moves)
        if (move.move.uci() == uci) return move.rank;
    throw std::runtime_error("Missing ranked move " + std::string(uci));
}

int best_rank(const std::vector<RootMove>& moves) {
    require(!moves.empty(), "Nonterminal root must have ranked moves");
    return std::max_element(moves.begin(), moves.end(),
                           [](const auto& a, const auto& b) { return a.rank < b.rank; })->rank;
}

/** The adapter must return the complete set with our exact special-move flags.
 * FEN and key are checked as well: probing must not mutate any position state.
 */
std::vector<RootMove> rank_root(Syzygy& tables, Position position) {
    const auto before = position.fen();
    const auto key = position.key();
    const auto legal = position.legal_moves();
    const auto result = tables.probe_root(position, legal);
    require(result.has_value(), "Complete fixture set must rank this eligible root");
    require(result->size() == legal.size(), "DTZ root result must cover every legal move");
    std::set<std::string> seen;
    for (const auto& move : *result) {
        require(std::find(legal.begin(), legal.end(), move.move) != legal.end(),
                "Ranked move must match a generated legal move including special flags");
        require(seen.insert(move.move.uci()).second, "Ranked root moves must not be duplicated");
    }
    require(position.fen() == before && position.key() == key,
            "Table probing must preserve FEN and repetition key");
    return *result;
}

void oracle_corpus(Syzygy& tables) {
    for (const auto& sample : syzygy_test::oracle_cases) {
        auto position = fen(sample.fen);
        const auto wdl = tables.probe_wdl(position);
        if (!wdl || static_cast<int>(*wdl) != sample.wdl)
            throw std::runtime_error("WDL disagrees with python-chess oracle: " + std::string(sample.name));
        const auto moves = rank_root(tables, position);
        const int rank = best_rank(moves);
        // None of these three-/four-piece samples is intrinsically cursed or
        // blessed. DTZ ranks encode progress as well as outcome; do not treat
        // their numerical magnitude as a distance to mate or evaluation.
        const bool agrees = sample.wdl == 2 ? rank >= 901
                           : sample.wdl == -2 ? rank <= -900 : rank == 0;
        if (!agrees)
            throw std::runtime_error("DTZ outcome disagrees with oracle: " + std::string(sample.name));
    }
}

void special_moves_and_clocks(Syzygy& tables) {
    auto ep = fen("8/8/8/3pPk2/8/8/K7/8 w - d6 0 1");
    require(tables.probe_wdl(ep) == tablebase::Wdl::draw, "En passant must preserve the draw");
    const auto ep_moves = rank_root(tables, ep);
    require(rank_of(ep_moves, "e5d6") == 0, "Essential EP must keep its drawing rank");
    for (const auto& move : ep_moves) {
        if (move.move.uci() == "e5d6")
            require((move.move.flags & en_passant) != 0 && move.move.is_capture(),
                    "EP move must retain both engine flags");
        else
            require(move.rank < 0, "Every alternative to essential EP loses");
    }
    auto no_ep = fen("8/8/8/3pPk2/8/8/K7/8 w - - 0 1");
    require(tables.probe_wdl(no_ep) == tablebase::Wdl::loss, "Removing EP changes this root to a loss");

    auto promotion = fen("8/k1P5/2K5/8/8/8/8/8 w - - 0 1");
    const auto promotions = rank_root(tables, promotion);
    require(rank_of(promotions, "c7c8r") >= 901, "Rook underpromotion must preserve a win");
    require(rank_of(promotions, "c7c8q") == 0, "Queen promotion stalemates and must rank as draw");
    require(rank_of(promotions, "c7c8b") == 0 && rank_of(promotions, "c7c8n") == 0,
            "Bishop and knight promotions must retain their drawing results");

    auto rook_fresh = fen("7k/8/5K2/8/8/8/8/R7 w - - 0 1");
    auto rook_99 = fen("7k/8/5K2/8/8/8/8/R7 w - - 99 1");
    require(tables.probe_wdl(rook_fresh) == tablebase::Wdl::win,
            "Fresh rook position is a tablebase win");
    require(!tables.probe_wdl(rook_99), "WDL lookup must refuse a nonzero halfmove clock");
    require(best_rank(rank_root(tables, rook_fresh)) >= 901, "Fresh DTZ position must retain winning rank");
    require(best_rank(rank_root(tables, rook_99)) < 900,
            "Clock99 cannot retain a safe win when shortest zeroing distance is three plies");

    auto mate_99 = fen("7k/8/5KQ1/8/8/8/8/8 w - - 99 1");
    const auto ranked = rank_root(tables, mate_99);
    const auto legal = mate_99.legal_moves();
    bool saw_mate = false;
    for (const auto move : legal) {
        auto child = mate_99;
        child.make_move(move);
        if (child.in_check(child.turn()) && child.legal_moves().empty()) {
            saw_mate = true;
            require(rank_of(ranked, move.uci()) == best_rank(ranked),
                    "Immediate mate at clock99 must not be ranked below a slower move");
        }
    }
    require(saw_mate, "Boundary fixture must actually contain a legal mate in one");

    // This composed KBNvK root has independently measured DTZ=8. A substantial
    // safety margin avoids relying on rounded DTZ's possible one-ply ambiguity.
    // The same board must cease to offer a guaranteed win as the clock fills.
    auto sufficient = fen("3N3k/8/1B3K2/8/8/8/8/8 w - - 89 1");
    auto insufficient = fen("3N3k/8/1B3K2/8/8/8/8/8 w - - 96 1");
    require(best_rank(rank_root(tables, sufficient)) >= 901,
            "DTZ eight with eleven plies remaining must retain a safe win");
    require(best_rank(rank_root(tables, insufficient)) < 900,
            "DTZ eight with four plies remaining must lose guaranteed-win status");
}

void unsupported_and_bad_root_sets(Syzygy& tables) {
    auto castling = fen("r3k3/8/8/8/8/8/8/4K2R w Kq - 0 1");
    require(!tables.probe_wdl(castling) && !tables.probe_root(castling, castling.legal_moves()),
            "Castling rights are outside Syzygy coverage");
    auto too_many = Position::start();
    require(!tables.probe_wdl(too_many) && !tables.probe_root(too_many, too_many.legal_moves()),
            "Positions above available material coverage must fall back");
    auto position = fen("7k/8/5KQ1/8/8/8/8/8 w - - 0 1");
    auto legal = position.legal_moves();
    auto partial = legal;
    partial.pop_back();
    require(!tables.probe_root(position, partial), "Incomplete supplied root set must fail closed");
    partial = legal;
    partial.back() = partial.front();
    require(!tables.probe_root(position, partial), "Duplicated supplied root set must fail closed");
    require(!tables.probe_root(position, {}), "Empty supplied root set must not produce a partial ranking");

    for (const auto text : {"7k/6Q1/5K2/8/8/8/8/8 b - - 100 1",
                            "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1"}) {
        auto terminal = fen(text);
        require(terminal.legal_moves().empty(), "Terminal fixture must have no legal moves");
        require(!tables.probe_root(terminal, {}), "Terminal roots belong to normal mate/stalemate handling");
    }
}

/** Destruction cleans only this test's newly created unique directory. */
struct TemporaryDirectory {
    fs::path path;
    TemporaryDirectory() {
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        for (unsigned attempt = 0; attempt < 100; ++attempt) {
            path = fs::temp_directory_path() / ("chess0live-syzygy-test-" + std::to_string(stamp)
                                                + "-" + std::to_string(attempt));
            if (fs::create_directory(path)) return;
        }
        throw std::runtime_error("Cannot create isolated tablebase test directory");
    }
    ~TemporaryDirectory() { std::error_code error; fs::remove_all(path, error); }
};

void configuration_and_missing_data(const fs::path& full) {
    TemporaryDirectory temporary;
    const auto empty = temporary.path / "empty";
    const auto wdl_only = temporary.path / "wdl-only";
    const auto dtz_only = temporary.path / "dtz-only";
    fs::create_directory(empty);
    fs::create_directory(wdl_only);
    fs::create_directory(dtz_only);
    fs::copy_file(full / "KQvK.rtbw", wdl_only / "KQvK.rtbw");
    fs::copy_file(full / "KQvK.rtbz", dtz_only / "KQvK.rtbz");
    auto position = fen("2Q5/4K3/8/8/8/8/8/6k1 w - - 0 1");
    std::string error;
    Syzygy tables;
    require(tables.largest() == 0 && !tables.probe_wdl(position), "Default tablebases must be disabled");
    require(tables.set_path(empty.string(), error) && tables.largest() == 0,
            "Existing empty directory must be an explicit no-table configuration");
    require(!tables.probe_root(position, position.legal_moves()), "No tables must fall back from root probe");
    require(!tables.set_path((temporary.path / "absent").string(), error) && !error.empty()
            && tables.largest() == 0, "Missing directory must return a useful error and disable probing");
    require(tables.set_path(wdl_only.string(), error) && tables.largest() == 3,
            "Partial fixture directory must expose its actual WDL cardinality");
    require(tables.probe_wdl(position) == tablebase::Wdl::win, "WDL-only material must remain probeable");
    require(!tables.probe_root(position, position.legal_moves()),
            "Missing DTZ must fail closed instead of inventing a root ranking");
    require(tables.set_path(dtz_only.string(), error) && tables.largest() == 0
            && !tables.probe_wdl(position), "DTZ without supporting WDL cannot establish coverage");
#ifdef _WIN32
    constexpr char separator = ';';
#else
    constexpr char separator = ':';
#endif
    require(tables.set_path(wdl_only.string() + separator + dtz_only.string(), error)
            && tables.largest() == 3, "Multiple configured directories must combine table coverage");
    require(tables.probe_root(position, position.legal_moves()).has_value(),
            "WDL and DTZ in separate directories must support root probing");
    require(!tables.set_path(full.string() + separator, error) && !error.empty(),
            "Empty path-list components must be rejected explicitly");
    require(tables.set_path("", error) && tables.largest() == 0 && !tables.probe_wdl(position),
            "Empty SyzygyPath must disable the configured tables");
    configure(tables, full);
    require(tables.set_path("<empty>", error) && tables.largest() == 0,
            "UCI empty sentinel must disable probing");

    auto older = std::make_unique<Syzygy>();
    configure(*older, full);
    Syzygy newer;
    configure(newer, full);
    require(older->largest() == 0 && !older->probe_wdl(position)
            && !older->probe_root(position, position.legal_moves()),
            "Reconfiguration by another instance must invalidate old bindings safely");
    older.reset();
    require(newer.probe_wdl(position) == tablebase::Wdl::win,
            "Destroying an invalidated context must not unload the active context");
    require(newer.set_path(wdl_only.string(), error), "Active instance must reconfigure while idle");
    require(newer.probe_wdl(position) == tablebase::Wdl::win
            && !newer.probe_root(position, position.legal_moves()),
            "Reconfigured WDL-only context must not retain stale DTZ mappings");

    // Operations on an obsolete object must not unload another object's tables,
    // including a failed path update and explicit disabling.
    auto stale = std::make_unique<Syzygy>();
    configure(*stale, full);
    configure(newer, full);
    require(!stale->set_path((temporary.path / "absent").string(), error),
            "An invalid path on an obsolete binding must still report failure");
    require(newer.probe_wdl(position) == tablebase::Wdl::win,
            "An obsolete binding's failed reconfiguration must not invalidate its successor");
    require(stale->set_path("", error), "Disabling an obsolete binding must succeed");
    require(newer.probe_wdl(position) == tablebase::Wdl::win,
            "Disabling an obsolete binding must not unload its successor");
    stale.reset();
    require(newer.probe_wdl(position) == tablebase::Wdl::win,
            "Destroying an obsolete disabled binding must leave its successor usable");
}

void malformed_file_rejection(const fs::path& full) {
    TemporaryDirectory temporary;
    std::string error;
    auto position = fen("2Q5/4K3/8/8/8/8/8/6k1 w - - 0 1");
    // Only copies in the freshly created temporary directory are modified.
    // The downloaded checksum-pinned corpus remains immutable throughout.
    for (const std::string name : {"bad-magic", "truncated", "header-only", "nonregular"}) {
        const auto directory = temporary.path / name;
        fs::create_directory(directory);
        const auto target = directory / "KQvK.rtbw";
        if (name == "nonregular") {
            fs::create_directory(target);
        } else {
            fs::copy_file(full / "KQvK.rtbw", target);
            if (name == "bad-magic") {
                std::fstream stream(target, std::ios::binary | std::ios::in | std::ios::out);
                stream.write("BAD!", 4);
                require(bool(stream), "Cannot write isolated malformed-header fixture");
            } else {
                fs::resize_file(target, name == "header-only" ? 16 : 65);
            }
        }
        Syzygy tables;
        configure(tables, full);
        require(!tables.set_path(directory.string(), error) && !error.empty(),
                "Malformed, truncated, and nonregular table files must fail before probing");
        require(tables.largest() == 0 && !tables.probe_wdl(position),
                "A rejected file configuration must disable the old table binding");
    }
    Syzygy tables;
    configure(tables, full);
    const auto ordinary_file = temporary.path / "regular-file";
    std::ofstream(ordinary_file) << "not a directory";
    require(!tables.set_path(ordinary_file.string(), error) && !error.empty(),
            "A regular file cannot be used as a tablebase directory");
    require(!tables.set_path(std::string("invalid\0path", 12), error) && !error.empty(),
            "A NUL-containing directory cannot be silently truncated");
}

void concurrent_probes(Syzygy& tables) {
    std::atomic<bool> correct{true};
    std::vector<std::jthread> threads;
    for (unsigned worker = 0; worker < 4; ++worker) {
        threads.emplace_back([&] {
            try {
                for (const auto& sample : syzygy_test::oracle_cases) {
                    auto position = fen(sample.fen);
                    auto result = tables.probe_wdl(position);
                    if (!result || static_cast<int>(*result) != sample.wdl) correct.store(false);
                }
            } catch (...) { correct.store(false); }
        });
    }
    threads.clear(); // jthread joins before inspecting the final shared result.
    require(correct.load(), "Concurrent WDL probes must retain all independently verified results");
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: tablebase-test <verified-test-table-directory>");
        const auto directory = fs::absolute(argv[1]);
        configuration_and_missing_data(directory);
        malformed_file_rejection(directory);
        Syzygy tables;
        configure(tables, directory);
        oracle_corpus(tables);
        special_moves_and_clocks(tables);
        unsupported_and_bad_root_sets(tables);
        concurrent_probes(tables);
        std::cout << "Syzygy tests passed: " << syzygy_test::oracle_cases.size()
                  << " exact WDL oracle cases with DTZ root outcome/legality checks; "
                     "special moves, clocks, fallback, malformed files, and concurrent probes\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Syzygy test failure: " << error.what() << '\n';
        return 1;
    }
}
