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

#include <algorithm>
#include <bit>
#include <charconv>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace chess0live {
namespace {

constexpr const char* default_network = "nn-1a298aa575a0.nnue";

/** argv[0] may be a bare command name. Resolve PATH before locating adjacent
 * assets; otherwise launching from a GUI or another directory breaks defaults.
 */
std::filesystem::path executable_directory(const std::filesystem::path& executable) {
    auto candidate = executable;
    if (!candidate.has_parent_path()) {
        const char* environment = std::getenv("PATH");
        std::istringstream entries(environment ? environment : "");
#ifdef _WIN32
        constexpr char separator = ';';
#else
        constexpr char separator = ':';
#endif
        for (std::string entry; std::getline(entries, entry, separator);) {
            auto path = std::filesystem::path(entry.empty() ? "." : entry) / executable;
#ifdef _WIN32
            if (!path.has_extension()) path += ".exe";
#endif
            if (std::filesystem::is_regular_file(path)) { candidate = path; break; }
        }
    }
    return std::filesystem::weakly_canonical(std::filesystem::absolute(candidate)).parent_path();
}

std::vector<std::string> words(const std::string& line) {
    std::istringstream input(line);
    std::vector<std::string> result;
    for (std::string token; input >> token;) result.push_back(std::move(token));
    return result;
}

template<class T> bool number(const std::string& text, T& value) {
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    return error == std::errc{} && end == text.data() + text.size();
}

std::string join(const std::vector<std::string>& tokens, std::size_t first, std::size_t last) {
    std::string result;
    for (auto i = first; i < last; ++i) {
        if (!result.empty()) result += ' ';
        result += tokens[i];
    }
    return result;
}

/** The controller owns all mutable configuration and joins the worker before
 * replacing it. Its input loop remains responsive while a search is active.
 */
class Controller {
public:
    explicit Controller(const std::filesystem::path& executable)
        : executable_dir_(executable_directory(executable)),
          position_(Position::start()), history_{position_.key()}, search_(network_) {}
    ~Controller() { stop(); }

    void run() {
        for (std::string line; std::getline(std::cin, line);) {
            if (line.size() > 65536) { output("info string error: command too long"); continue; }
            const auto tokens = words(line);
            if (tokens.empty()) continue;
            try {
                const auto& command = tokens.front();
                if (command == "quit") { stop(); break; }
                if (command == "uci") identify();
                else if (command == "isready") {
                    // Loading on readiness keeps network preparation outside the
                    // tournament clock. Dirty configuration cannot coexist with a
                    // running search: setoption joins the worker before changing it.
                    if (network_dirty_) ensure_network();
                    output("readyok");
                }
                else if (command == "stop") stop();
                else if (command == "ponderhit") ponderhit();
                else if (command == "ucinewgame") { stop(); search_.clear(); }
                else if (command == "setoption") option(tokens);
                else if (command == "position") position(tokens);
                else if (command == "go") go(tokens);
                else if (command == "perft" || command == "divide") count(tokens);
                else if (command == "eval") evaluate();
                else if (command == "d") { stop(); output("info string fen " + position_.fen()); }
                // UCI permits ignoring commands an engine does not understand.
            } catch (const std::exception& error) {
                output(std::string("info string error: ") + error.what());
            }
        }
        stop();
    }

private:
    std::filesystem::path executable_dir_;
    Position position_;
    std::vector<std::uint64_t> history_;
    nnue::Network network_;
    Search search_;
    std::string eval_file_ = default_network;
    bool network_dirty_ = true;
    int overhead_ms_ = 20;
    TimePolicy time_policy_ = TimePolicy::classic;
    bool diagnostics_ = false;
    std::thread worker_;
    std::mutex output_mutex_;
    std::mutex result_mutex_;
    std::condition_variable result_ready_;
    bool hold_result_ = false;
    bool infinite_mode_ = false;
    bool ponder_mode_ = false;

    void output(const std::string& line) {
        std::lock_guard guard(output_mutex_);
        std::cout << line << '\n' << std::flush;
    }

    void identify() {
        output("id name chess0live 0.1-dev");
        output("id author Claudio M. Camacho");
        output("option name Hash type spin default 64 min 1 max 16384");
        output("option name Clear Hash type button");
        output("option name Threads type spin default 1 min 1 max " + std::to_string(Search::max_threads));
        output(std::string("option name EvalFile type string default ") + default_network);
        output("option name Move Overhead type spin default 20 min 0 max 5000");
        output("option name Ponder type check default false");
        output("option name Time Policy type combo default classic var classic var forecast");
        output("option name Search Diagnostics type check default false");
        output("uciok");
    }

    /** Stop is published before joining; a just-created worker cannot erase it. */
    void stop() {
        search_.stop();
        {
            std::lock_guard guard(result_mutex_);
            hold_result_ = false;
        }
        result_ready_.notify_all();
        if (worker_.joinable()) worker_.join();
    }

    void ponderhit() {
        search_.ponderhit();
        {
            std::lock_guard guard(result_mutex_);
            if (ponder_mode_ && !infinite_mode_) hold_result_ = false;
        }
        result_ready_.notify_all();
    }

    bool ensure_network() {
        if (!network_dirty_ && network_.loaded()) return true;
        const std::filesystem::path requested(eval_file_);
        std::vector<std::filesystem::path> candidates{requested};
        if (requested == requested.filename()) {
            candidates.emplace_back(std::filesystem::path("networks") / requested);
            candidates.emplace_back(executable_dir_ / requested);
            candidates.emplace_back(executable_dir_ / "networks" / requested);
            candidates.emplace_back(executable_dir_ / ".." / ".." / "networks" / requested);
        }
        std::string error;
        for (const auto& candidate : candidates) {
            if (!std::filesystem::is_regular_file(candidate)) continue;
            if (network_.load(candidate, error)) {
                network_dirty_ = false;
                search_.clear();
                return true;
            }
            output("info string error: rejected network " + candidate.string() + ": " + error);
            return false;
        }
        output("info string error: network not found; run make net or setoption name EvalFile value /path/to/network.nnue");
        return false;
    }

    void option(const std::vector<std::string>& tokens) {
        stop();
        if (tokens.size() < 3 || tokens[1] != "name") return;
        const auto value_it = std::find(tokens.begin() + 2, tokens.end(), "value");
        const auto value_index = static_cast<std::size_t>(value_it - tokens.begin());
        const auto name = join(tokens, 2, value_index);
        const auto value = value_it == tokens.end() ? std::string{} : join(tokens, value_index + 1, tokens.size());
        if (name == "EvalFile") {
            if (value.empty()) { output("info string error: EvalFile cannot be empty"); return; }
            eval_file_ = value;
            network_dirty_ = true;
            return;
        }
        if (name == "Clear Hash") { search_.clear(); return; }
        if (name == "Ponder") {
            if (value != "true" && value != "false") output("info string error: Ponder expects true or false");
            return; // go ponder, not this option, controls the current search.
        }
        if (name == "Time Policy") {
            if (value == "classic") time_policy_ = TimePolicy::classic;
            else if (value == "forecast") time_policy_ = TimePolicy::forecast;
            else output("info string error: Time Policy expects classic or forecast");
            return;
        }
        if (name == "Search Diagnostics") {
            if (value == "true") diagnostics_ = true;
            else if (value == "false") diagnostics_ = false;
            else output("info string error: Search Diagnostics expects true or false");
            return;
        }
        int numeric = 0;
        if (!number(value, numeric)) { output("info string error: option requires an integer"); return; }
        if (name == "Hash" && numeric >= 1 && numeric <= 16384) search_.set_hash(static_cast<std::size_t>(numeric));
        else if (name == "Move Overhead" && numeric >= 0 && numeric <= 5000) overhead_ms_ = numeric;
        else if (name == "Threads" && numeric == 1) {}
        else output("info string error: unsupported option or value");
    }

    /** Parse transactionally: an invalid FEN or move never replaces the game. */
    void position(const std::vector<std::string>& tokens) {
        stop();
        if (tokens.size() < 2) { output("info string error: missing position"); return; }
        auto next = Position::start();
        std::size_t index = 2;
        if (tokens[1] == "fen") {
            if (tokens.size() < 8) { output("info string error: FEN needs six fields"); return; }
            std::string error;
            auto parsed = Position::from_fen(join(tokens, 2, 8), error);
            if (!parsed) { output("info string error: " + error); return; }
            next = *parsed;
            index = 8;
        } else if (tokens[1] != "startpos") {
            output("info string error: expected startpos or fen"); return;
        }
        std::vector<std::uint64_t> keys{next.key()};
        if (index < tokens.size()) {
            if (tokens[index++] != "moves") { output("info string error: expected moves"); return; }
            while (index < tokens.size()) {
                auto move = parse_uci_move(next, tokens[index]);
                if (!move) { output("info string error: illegal move " + tokens[index]); return; }
                next.make_move(*move);
                keys.push_back(next.key());
                ++index;
            }
        }
        position_ = next;
        history_ = std::move(keys);
    }

    void report(const SearchInfo& info) {
        std::ostringstream line;
        line << "info depth " << info.depth << " seldepth " << info.seldepth << " score ";
        if (std::abs(info.score) >= Search::mate_threshold) {
            const int plies = Search::mate_score - std::abs(info.score);
            line << "mate " << (info.score < 0 ? -1 : 1) * ((plies + 1) / 2);
        } else {
            // SF19's display normalization keeps the upstream network's integer
            // scale useful in GUIs. This is not a measured chess0live WDL model.
            int material = 0;
            constexpr int values[] = {0, 1, 3, 3, 5, 9};
            for (int type = 1; type <= 5; ++type)
                for (Color side : {Color::white, Color::black})
                    material += values[type] * std::popcount(position_.pieces(side, static_cast<PieceType>(type)));
            const double m = std::clamp(material, 17, 78) / 58.0;
            const double scale = ((-142.72052667 * m + 372.35176398) * m - 340.71073572) * m + 415.23490212;
            line << "cp " << std::lround(100.0 * info.score / scale);
        }
        line << " nodes " << info.nodes << " time " << info.time_ms
             << " nps " << (info.nodes * 1000 / static_cast<std::uint64_t>(std::max<std::int64_t>(1, info.time_ms)))
             << " pv";
        for (const auto move : info.pv) line << ' ' << move.uci();
        output(line.str());
    }

    /** Versioned, opt-in diagnostics are ordinary UCI string messages. Emit the
     * compact root trace only after searching, so writing diagnostics cannot
     * alter the work of a later iteration or create a per-node output cost.
     */
    void report_diagnostics(const SearchResult& result) {
        if (!result.diagnostics) return;
        const auto& diagnostics = *result.diagnostics;
        for (const auto& iteration : diagnostics.iterations) {
            std::ostringstream line;
            line << std::fixed << std::setprecision(3) << std::boolalpha
                 << "info string search-iteration v1 depth " << iteration.depth
                 << " completed " << iteration.completed << " nodes " << iteration.nodes
                 << " duration_ms " << iteration.duration_ms << " elapsed_ms " << iteration.elapsed_ms;
            output(line.str());
        }
        const char* reason = "depth_limit";
        switch (diagnostics.stop_reason) {
            case StopReason::external_stop: reason = "external_stop"; break;
            case StopReason::node_limit: reason = "node_limit"; break;
            case StopReason::hard_time: reason = "hard_time"; break;
            case StopReason::soft_time: reason = "soft_time"; break;
            case StopReason::forecast: reason = "forecast"; break;
            case StopReason::depth_limit: break;
            case StopReason::mate_limit: reason = "mate_limit"; break;
            case StopReason::terminal: reason = "terminal"; break;
            case StopReason::draw: reason = "draw"; break;
        }
        std::ostringstream line;
        line << std::fixed << std::setprecision(3) << std::boolalpha
             << "info string search-summary v1 policy "
             << (diagnostics.policy == TimePolicy::classic ? "classic" : "forecast")
             << " forecast_active " << diagnostics.forecast_active
             << " stop_reason " << reason << " nodes " << result.nodes
             << " completed_depth " << result.depth << " elapsed_ms " << diagnostics.elapsed_ms
             << " soft_ms " << diagnostics.soft_ms << " hard_ms " << diagnostics.hard_ms
             << " target_ms " << diagnostics.target_ms
             << " predicted_next_ms " << diagnostics.predicted_next_ms;
        output(line.str());
    }

    void go(const std::vector<std::string>& tokens) {
        stop();
        SearchLimits limits;
        limits.move_overhead_ms = overhead_ms_;
        limits.time_policy = time_policy_;
        limits.diagnostics = diagnostics_;
        const std::vector<std::string> keywords{"searchmoves", "ponder", "wtime", "btime", "winc", "binc", "movestogo", "depth", "nodes", "mate", "movetime", "infinite"};
        for (std::size_t i = 1; i < tokens.size(); ++i) {
            const auto& key = tokens[i];
            if (key == "infinite") { limits.infinite = true; continue; }
            if (key == "ponder") { limits.ponder = true; continue; }
            if (key == "searchmoves") {
                const auto before = limits.searchmoves.size();
                while (i + 1 < tokens.size() && std::find(keywords.begin(), keywords.end(), tokens[i + 1]) == keywords.end()) {
                    auto move = parse_uci_move(position_, tokens[++i]);
                    if (!move) { output("info string error: illegal searchmoves entry"); return; }
                    limits.searchmoves.push_back(*move);
                }
                if (limits.searchmoves.size() == before) { output("info string error: empty searchmoves"); return; }
                continue;
            }
            if (std::find(keywords.begin(), keywords.end(), key) == keywords.end()) {
                output("info string error: unsupported go parameter " + key); return;
            }
            std::int64_t value = 0;
            if (++i == tokens.size() || !number(tokens[i], value) || value < 0 || value > 2147483647) {
                output("info string error: invalid go limit"); return;
            }
            if (key == "wtime") limits.wtime_ms = value;
            else if (key == "btime") limits.btime_ms = value;
            else if (key == "winc") limits.winc_ms = value;
            else if (key == "binc") limits.binc_ms = value;
            else if (key == "movetime") limits.movetime_ms = value;
            else if (key == "depth") limits.depth = std::max(1, static_cast<int>(value));
            else if (key == "nodes") limits.nodes = static_cast<std::uint64_t>(std::max<std::int64_t>(1, value));
            else if (key == "mate") limits.mate = std::max(1, static_cast<int>(value));
            else if (key == "movestogo") limits.movestogo = static_cast<int>(value);
        }
        if (!ensure_network()) { output("bestmove 0000"); return; }
        {
            std::lock_guard guard(result_mutex_);
            infinite_mode_ = limits.infinite;
            ponder_mode_ = limits.ponder;
            hold_result_ = infinite_mode_ || ponder_mode_;
        }
        search_.reset_stop();
        worker_ = std::thread([this, limits, root = position_, history = history_]() mutable {
            SearchResult result;
            try { result = search_.search(root, std::move(history), limits, [this](const auto& info) { report(info); }); }
            catch (const std::exception& error) { output(std::string("info string search error: ") + error.what()); }
            {
                std::unique_lock lock(result_mutex_);
                result_ready_.wait(lock, [this] { return !hold_result_; });
            }
            report_diagnostics(result);
            std::string line = "bestmove " + result.best.uci();
            if (result.ponder.valid()) line += " ponder " + result.ponder.uci();
            output(line);
        });
    }

    void count(const std::vector<std::string>& tokens) {
        stop();
        unsigned depth = 0;
        if (tokens.size() != 2 || !number(tokens[1], depth) || depth > 16) {
            output("info string error: expected perft/divide depth (0..16)"); return;
        }
        const auto begin = std::chrono::steady_clock::now();
        std::uint64_t nodes = 0;
        if (tokens[0] == "divide" && depth > 0) {
            auto moves = position_.legal_moves();
            std::sort(moves.begin(), moves.end(), [](Move a, Move b) { return a.uci() < b.uci(); });
            for (auto move : moves) {
                const auto undo = position_.make_move(move);
                const auto count = perft(position_, depth - 1);
                position_.unmake_move(move, undo);
                nodes += count;
                output(move.uci() + ": " + std::to_string(count));
            }
        } else nodes = perft(position_, depth);
        const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - begin).count();
        output("nodes " + std::to_string(nodes) + " time " + std::to_string(elapsed));
    }

    void evaluate() {
        stop();
        if (!ensure_network()) return;
        const auto raw = network_.evaluate(position_);
        nnue::Evaluator evaluator(network_);
        output("info string eval psqt " + std::to_string(raw.psqt) + " positional " + std::to_string(raw.positional)
               + " score " + std::to_string(evaluator.evaluate(position_)));
    }
};
} // namespace
} // namespace chess0live

int main(int argc, char** argv) {
    if (argc > 1 && std::string_view(argv[1]) == "--version") {
        std::cout << "chess0live 0.1-dev\n"; return 0;
    }
    if (argc > 1) {
        std::cout << "chess0live is a UCI engine. Run without arguments.\n"
                     "Diagnostics on stdin: perft N, divide N, eval, d.\n";
        return std::string_view(argv[1]) == "--help" ? 0 : 2;
    }
    try {
        chess0live::Controller controller(argv[0]);
        controller.run();
    } catch (const std::exception& error) {
        std::cerr << "chess0live: " << error.what() << '\n'; return 1;
    }
}
