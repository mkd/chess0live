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
#include <atomic>
#include <bit>
#include <charconv>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace chess0live {
namespace {

constexpr const char* default_network = "nn-1a298aa575a0.nnue";

#ifdef CHESS0LIVE_CLOCK_TRACE
/** Process-local steady clock; the diagnostic reader must calibrate its epoch. */
std::int64_t trace_ns(std::chrono::steady_clock::time_point when = std::chrono::steady_clock::now()) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(when.time_since_epoch()).count();
}
#endif

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
    explicit Controller(const std::filesystem::path& executable,
                        const std::optional<std::filesystem::path>& initial_network = std::nullopt)
        : executable_dir_(executable_directory(executable)),
          position_(Position::start()), history_{position_.key()}, search_(network_) {
        if (initial_network) {
            // An explicit launch choice must load that exact file. Resolve it
            // before UCI begins, without the default basename search/fallback.
            const auto path = std::filesystem::absolute(*initial_network).lexically_normal();
            launch_eval_file_ = path.string();
            if (std::any_of(launch_eval_file_.begin(), launch_eval_file_.end(), [](unsigned char c) {
                    return c < 32 || c == 127;
                }))
                throw std::invalid_argument("--eval-file path contains a UCI control character");
            if (!std::filesystem::is_regular_file(path))
                throw std::runtime_error("--eval-file is not a regular file: " + launch_eval_file_);
            std::string error;
            if (!network_.load(path, error))
                throw std::runtime_error("--eval-file rejected network " + launch_eval_file_ + ": " + error);
            eval_file_ = launch_eval_file_;
            network_dirty_ = false;
        }
    }
    ~Controller() { stop(); }

    void run() {
        for (std::string line; std::getline(std::cin, line);) {
            // Capture before parsing or joining/preparing a worker. Time spent
            // after accepting go belongs to that request's existing budget.
            const auto received_at = std::chrono::steady_clock::now();
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
#ifdef CHESS0LIVE_CLOCK_TRACE
                else if (command == "clockping") {
                    std::uint64_t id = 0;
                    if (tokens.size() != 2 || !number(tokens[1], id))
                        output("info string error: clockping expects an unsigned integer");
                    else {
                        const auto stamp = trace_ns();
                        output("info string clock-ping v1 id " + std::to_string(id)
                               + " now_ns " + std::to_string(stamp));
                    }
                }
#endif
                else if (command == "ponderhit") ponderhit();
                else if (command == "ucinewgame") { stop(); search_.clear(); }
                else if (command == "setoption") option(tokens);
                else if (command == "position") {
#ifdef CHESS0LIVE_CLOCK_TRACE
                    command_trace_.position_begin_ns = trace_ns(received_at);
#endif
                    position(tokens);
#ifdef CHESS0LIVE_CLOCK_TRACE
                    command_trace_.position_end_ns = trace_ns();
#endif
                }
                else if (command == "go") go(tokens, received_at);
                else if (command == "perft" || command == "divide") count(tokens);
                else if (command == "eval" || command == "d" || command == "show"
                         || command == "display" || command == "flip" || command == "help") {
                    if (tokens.size() != 1) { output("info string error: " + command + " takes no arguments"); continue; }
                    stop();
                    if (command == "eval") evaluate();
                    else if (command == "help") help();
                    else {
                        if (command == "flip") flipped_ = !flipped_;
                        display();
                    }
                }
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
    // Keep the launch default distinct from later explicit UCI overrides.
    std::string launch_eval_file_ = default_network;
    std::string eval_file_ = default_network;
    bool network_dirty_ = true;
    int overhead_ms_ = 20;
    TimePolicy time_policy_ = TimePolicy::classic;
    bool diagnostics_ = false;
    bool late_move_reductions_ = true;
    bool deep_quiet_reductions_ = false;
    CaptureOrdering capture_ordering_ = CaptureOrdering::mvv_lva;
    bool countermove_ordering_ = false;
    bool null_move_pruning_ = false;
    bool reverse_futility_pruning_ = false;
    bool qsearch_see_pruning_ = false;
    bool probcut_ = false;
    bool tt_move_hints_ = false;
    int syzygy_probe_limit_ = 7;
    int syzygy_probe_depth_ = 1;
    std::thread worker_;
    std::mutex output_mutex_;
    std::mutex result_mutex_;
    std::condition_variable result_ready_;
    bool hold_result_ = false;
    bool infinite_mode_ = false;
    bool ponder_mode_ = false;
    bool flipped_ = false;
    std::atomic<bool> perft_stop_{false};

#ifdef CHESS0LIVE_CLOCK_TRACE
    struct CommandClockTrace {
        std::uint64_t sequence = 0;
        std::int64_t position_begin_ns = 0, position_end_ns = 0;
        std::int64_t go_received_ns = 0, worker_started_ns = 0, search_returned_ns = 0;
    } command_trace_;

    /** The diagnostic record is formatted only AFTER bestmove was flushed.
     * Holding the output lock keeps the paired record from interleaving with
     * another response; lock waiting is measured separately from the write.
     * These boundaries observe user-space code, not kernel pipe arrival.
     */
    void traced_bestmove(const std::string& line, const SearchResult& result,
                         const CommandClockTrace& command) {
        const auto ready = trace_ns();
        std::lock_guard guard(output_mutex_);
        const auto begin = trace_ns();
        std::cout << line << '\n' << std::flush;
        const auto flushed = trace_ns();
        const auto& search = result.clock_trace;
        std::cout << "info string clock-boundary v1 seq " << command.sequence
                  << " position_begin_ns " << command.position_begin_ns
                  << " position_end_ns " << command.position_end_ns
                  << " go_received_ns " << command.go_received_ns
                  << " worker_started_ns " << command.worker_started_ns
                  << " search_started_ns " << search.search_started_ns
                  << " hard_stop_ns " << search.hard_stop_ns
                  << " leader_finished_ns " << search.leader_finished_ns
                  << " joined_ns " << search.joined_ns
                  << " accounted_ns " << search.accounted_ns
                  << " search_returned_ns " << command.search_returned_ns
                  << " reply_ready_ns " << ready
                  << " bestmove_begin_ns " << begin
                  << " bestmove_flushed_ns " << flushed
                  << " hard_budget_ns " << search.hard_budget_ns
                  << " reported_time_ms " << result.time_ms << '\n' << std::flush;
    }
#endif

    void output(const std::string& line) {
        std::lock_guard guard(output_mutex_);
        std::cout << line << '\n' << std::flush;
    }

    void identify() {
#ifdef CHESS0LIVE_CLOCK_TRACE
        output("id name chess0live 0.1-dev clock-trace");
#else
        output("id name chess0live 0.1-dev");
#endif
        output("id author Claudio M. Camacho");
        output("option name Hash type spin default 64 min 1 max 16384");
        output("option name Clear Hash type button");
        output("option name Threads type spin default 1 min 1 max " + std::to_string(Search::max_threads));
        output(std::string("option name EvalFile type string default ") + launch_eval_file_);
        output("option name SyzygyPath type string default <empty>");
        output("option name SyzygyProbeLimit type spin default 7 min 0 max 7");
        output("option name SyzygyProbeDepth type spin default 1 min 1 max 128");
        output("option name Move Overhead type spin default 20 min 0 max 5000");
        output("option name Ponder type check default false");
        output("option name Time Policy type combo default classic var classic var forecast var bounded");
        output("option name Search Diagnostics type check default false");
        output("option name Late Move Reductions type check default true");
        output("option name Deep Quiet Reductions type check default false");
        output("option name Capture Ordering type combo default mvv-lva var mvv-lva var see");
        output("option name Countermove Ordering type check default false");
        output("option name Null Move Pruning type check default false");
        output("option name Reverse Futility Pruning type check default false");
        output("option name QSearch SEE Pruning type check default false");
        output("option name ProbCut type check default false");
        output("option name TT Move Hints type check default false");
        output("uciok");
    }

    /** Stop is published before joining; a just-created worker cannot erase it. */
    void stop() {
        search_.stop();
        perft_stop_.store(true, std::memory_order_relaxed);
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
        if (name == "SyzygyPath") {
            std::string error;
            if (!search_.set_syzygy_path(value == "<empty>" ? "" : value, error))
                output("info string error: SyzygyPath: " + error);
            else output("info string Syzygy largest " + std::to_string(search_.syzygy_largest())
                        + " pieces; table files are external");
            return;
        }
        if (name == "Ponder") {
            if (value != "true" && value != "false") output("info string error: Ponder expects true or false");
            return; // go ponder, not this option, controls the current search.
        }
        if (name == "Time Policy") {
            if (value == "classic") time_policy_ = TimePolicy::classic;
            else if (value == "forecast") time_policy_ = TimePolicy::forecast;
            else if (value == "bounded") time_policy_ = TimePolicy::bounded;
            else output("info string error: Time Policy expects classic, forecast or bounded");
            return;
        }
        if (name == "Search Diagnostics") {
            if (value == "true") diagnostics_ = true;
            else if (value == "false") diagnostics_ = false;
            else output("info string error: Search Diagnostics expects true or false");
            return;
        }
        if (name == "Deep Quiet Reductions") {
            if (value == "true") deep_quiet_reductions_ = true;
            else if (value == "false") deep_quiet_reductions_ = false;
            else output("info string error: Deep Quiet Reductions expects true or false");
            return;
        }
        if (name == "Late Move Reductions") {
            if (value == "true") late_move_reductions_ = true;
            else if (value == "false") late_move_reductions_ = false;
            else output("info string error: Late Move Reductions expects true or false");
            // Search::run clears both TT and learned ordering state when the
            // actual search policy changes, including calls outside this UCI UI.
            return;
        }
        if (name == "Capture Ordering") {
            if (value == "mvv-lva") capture_ordering_ = CaptureOrdering::mvv_lva;
            else if (value == "see") capture_ordering_ = CaptureOrdering::see;
            else output("info string error: Capture Ordering expects mvv-lva or see");
            return; // Search also isolates the cache for direct API callers.
        }
        if (name == "Countermove Ordering") {
            if (value == "true") countermove_ordering_ = true;
            else if (value == "false") countermove_ordering_ = false;
            else output("info string error: Countermove Ordering expects true or false");
            return; // Search isolates both cache and worker-local histories.
        }
        if (name == "Null Move Pruning") {
            if (value == "true") null_move_pruning_ = true;
            else if (value == "false") null_move_pruning_ = false;
            else output("info string error: Null Move Pruning expects true or false");
            return; // Direct Search callers get the same policy-state isolation.
        }
        if (name == "Reverse Futility Pruning") {
            if (value == "true") reverse_futility_pruning_ = true;
            else if (value == "false") reverse_futility_pruning_ = false;
            else output("info string error: Reverse Futility Pruning expects true or false");
            return; // Isolate cached bounds when the static pruning policy changes.
        }
        if (name == "TT Move Hints") {
            if (value == "true") tt_move_hints_ = true;
            else if (value == "false") tt_move_hints_ = false;
            else output("info string error: TT Move Hints expects true or false");
            return; // Search isolates policy state for UCI and direct API callers.
        }
        if (name == "ProbCut") {
            if (value == "true") probcut_ = true;
            else if (value == "false") probcut_ = false;
            else output("info string error: ProbCut expects true or false");
            return;
        }
        if (name == "QSearch SEE Pruning") {
            if (value == "true") qsearch_see_pruning_ = true;
            else if (value == "false") qsearch_see_pruning_ = false;
            else output("info string error: QSearch SEE Pruning expects true or false");
            return; // Leaf pruning can affect ancestor bounds and learned replies.
        }
        int numeric = 0;
        if (!number(value, numeric)) { output("info string error: option requires an integer"); return; }
        if (name == "Hash" && numeric >= 1 && numeric <= 16384) search_.set_hash(static_cast<std::size_t>(numeric));
        else if (name == "Move Overhead" && numeric >= 0 && numeric <= 5000) overhead_ms_ = numeric;
        else if (name == "Threads" && numeric >= 1 && numeric <= Search::max_threads)
            search_.set_threads(numeric);
        else if (name == "SyzygyProbeLimit" && numeric >= 0 && numeric <= 7) syzygy_probe_limit_ = numeric;
        else if (name == "SyzygyProbeDepth" && numeric >= 1 && numeric <= Search::max_ply)
            syzygy_probe_depth_ = numeric;
        else output("info string error: unsupported option or value");
    }

    /** Parse transactionally: an invalid FEN or move never replaces the game.
     *
     * Manual puzzle extension: a trailing `bm` starts opaque metadata, never
     * search hints. Four-field puzzle records may omit both counters before
     * `bm`; synthesize 0/1 only in that unambiguous case. The position parser
     * still validates every board field. Ordinary UCI FEN/moves stay strict.
     */
    void position(const std::vector<std::string>& tokens) {
        stop();
        if (tokens.size() < 2) { output("info string error: missing position"); return; }
        auto next = Position::start();
        std::size_t index = 2;
        if (tokens[1] == "fen") {
            const bool puzzle_counters_omitted = tokens.size() > 6 && tokens[6] == "bm";
            if (!puzzle_counters_omitted && tokens.size() < 8) {
                output("info string error: FEN needs six fields (or four before bm)"); return;
            }
            index = puzzle_counters_omitted ? 6 : 8;
            auto fen = join(tokens, 2, index);
            if (puzzle_counters_omitted) fen += " 0 1";
            std::string error;
            auto parsed = Position::from_fen(fen, error);
            if (!parsed) { output("info string error: " + error); return; }
            next = *parsed;
            if (index < tokens.size() && tokens[index] == "bm") {
                if (index + 1 == tokens.size()) {
                    output("info string error: bm annotation is empty"); return;
                }
                // Do not silently swallow an intended UCI move history. To
                // replay moves, remove the annotation and use ordinary UCI.
                if (std::find(tokens.begin() + index + 1, tokens.end(), "moves") != tokens.end()) {
                    output("info string error: bm annotation cannot be combined with moves"); return;
                }
                index = tokens.size();
            }
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

    /** Use the same display normalization for static diagnostics and search.
     * It keeps the pinned network's integer scale useful in GUIs; this is not
     * a measured chess0live WDL model or a change to any search score.
     */
    long display_centipawns(int score) const {
        int material = 0;
        constexpr int values[] = {0, 1, 3, 3, 5, 9};
        for (int type = 1; type <= 5; ++type)
            for (Color side : {Color::white, Color::black})
                material += values[type] * std::popcount(position_.pieces(side, static_cast<PieceType>(type)));
        const double m = std::clamp(material, 17, 78) / 58.0;
        const double scale = ((-142.72052667 * m + 372.35176398) * m - 340.71073572) * m + 415.23490212;
        return std::lround(100.0 * score / scale);
    }

    void report(const SearchInfo& info) {
        std::ostringstream line;
        line << "info depth " << info.depth << " seldepth " << info.seldepth << " score ";
        if (std::abs(info.score) >= Search::mate_threshold) {
            const int plies = Search::mate_score - std::abs(info.score);
            line << "mate " << (info.score < 0 ? -1 : 1) * ((plies + 1) / 2);
        } else {
            line << "cp " << display_centipawns(info.score);
        }
        line << " nodes " << info.nodes << " time " << info.time_ms
             << " nps " << (info.nodes * 1000 / static_cast<std::uint64_t>(std::max<std::int64_t>(1, info.time_ms)))
             << " hashfull " << info.hashfull
             << " tbhits " << info.tbhits
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
        if (diagnostics.move_hints.enabled) {
            const auto& hints = diagnostics.move_hints;
            std::ostringstream line;
            line << "info string move-hints v1 enabled true slots " << hints.slots
                 << " allocated_bytes " << hints.allocated_bytes
                 << " probes " << hints.probes << " hits " << hints.hits
                 << " legal_matches " << hints.legal_matches << " stores " << hints.stores;
            output(line.str());
        }
        if (result.probcut.enabled) {
            std::ostringstream line;
            line << "info string probcut v1 enabled true eligible_nodes "
                 << result.probcut.eligible_nodes
                 << " see_evaluations " << result.probcut.see_evaluations
                 << " qsearches " << result.probcut.qsearches
                 << " qsearch_passes " << result.probcut.qsearch_passes
                 << " searches " << result.probcut.searches
                 << " cutoffs " << result.probcut.cutoffs
                 << " rejected " << result.probcut.rejected;
            output(line.str());
        }
        if (result.qsearch_see.enabled) {
            std::ostringstream line;
            line << "info string qsearchsee v1 enabled true evaluations "
                 << result.qsearch_see.evaluations << " pruned " << result.qsearch_see.pruned;
            output(line.str());
        }
        if (result.reverse_futility.enabled) {
            std::ostringstream line;
            line << "info string reversefutility v1 enabled true evaluations "
                 << result.reverse_futility.evaluations
                 << " cutoffs " << result.reverse_futility.cutoffs;
            output(line.str());
        }
        if (result.nullmove.enabled) {
            std::ostringstream line;
            line << "info string nullmove v1 enabled true probes " << result.nullmove.probes
                 << " fail_highs " << result.nullmove.fail_highs
                 << " verifications " << result.nullmove.verifications
                 << " cutoffs " << result.nullmove.cutoffs << " rejected " << result.nullmove.rejected;
            output(line.str());
        }
        if (result.smp.threads > 1) {
            std::ostringstream line;
            line << "info string smp v1 threads " << result.smp.threads
                 << " total_nodes " << result.nodes
                 << " leader_nodes " << result.smp.worker_nodes.front()
                 << " worker_nodes ";
            for (std::size_t i = 0; i < result.smp.worker_nodes.size(); ++i)
                line << (i ? "," : "") << result.smp.worker_nodes[i];
            line << " worker_depths ";
            for (std::size_t i = 0; i < result.smp.worker_depths.size(); ++i)
                line << (i ? "," : "") << result.smp.worker_depths[i];
            output(line.str());
        }
        {
            const auto& cache = diagnostics.cache;
            std::ostringstream line;
            line << "info string cache v1 entry_bytes " << cache.entry_bytes
                 << " bucket_bytes " << cache.bucket_bytes << " buckets " << cache.buckets
                 << " capacity " << cache.capacity << " allocated_bytes " << cache.allocated_bytes
                 << " probes " << cache.probes << " hits " << cache.hits
                 << " cutoffs " << cache.cutoffs << " stores " << cache.stores
                 << " replacements " << cache.replacements;
            output(line.str());
        }
        for (const auto& iteration : diagnostics.iterations) {
            std::ostringstream line;
            line << std::fixed << std::setprecision(3) << std::boolalpha
                 << "info string search-iteration v1 depth " << iteration.depth
                 << " completed " << iteration.completed << " nodes " << iteration.nodes
                 << " duration_ms " << iteration.duration_ms << " elapsed_ms " << iteration.elapsed_ms;
            output(line.str());
        }
        {
            std::ostringstream line;
            line << "info string ordering v1 policy "
                 << (result.ordering.policy == CaptureOrdering::mvv_lva ? "mvv-lva" : "see")
                 << " see_calls " << result.ordering.see_calls
                 << " losing_captures " << result.ordering.losing_captures;
            output(line.str());
        }
        {
            std::ostringstream line;
            line << std::boolalpha << "info string lmr v1 enabled " << result.lmr.enabled
                 << " reductions " << result.lmr.reductions << " researches " << result.lmr.researches
                 << " fail_lows " << result.lmr.fail_lows
                 << " verified_cutoffs " << result.lmr.verified_cutoffs;
            output(line.str());
        }
        if (result.deep_lmr.enabled) {
            std::ostringstream line;
            line << "info string deep-lmr v1 enabled true extra_reductions "
                 << result.deep_lmr.extra_reductions
                 << " researches " << result.deep_lmr.researches
                 << " fail_lows " << result.deep_lmr.fail_lows
                 << " verified_cutoffs " << result.deep_lmr.verified_cutoffs;
            output(line.str());
        }
        const char* reason = "depth_limit";
        if (result.countermove.enabled) {
            std::ostringstream line;
            line << "info string countermove v1 enabled true lookups " << result.countermove.lookups
                 << " matches " << result.countermove.matches
                 << " updates " << result.countermove.updates;
            output(line.str());
        }
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
             << (diagnostics.policy == TimePolicy::classic ? "classic"
                 : diagnostics.policy == TimePolicy::forecast ? "forecast" : "bounded")
             << " forecast_active " << diagnostics.forecast_active
             << " stop_reason " << reason << " nodes " << result.nodes
             << " completed_depth " << result.depth << " elapsed_ms " << diagnostics.elapsed_ms
             << " soft_ms " << diagnostics.soft_ms << " hard_ms " << diagnostics.hard_ms
             << " target_ms " << diagnostics.target_ms
             << " predicted_next_ms " << diagnostics.predicted_next_ms;
        output(line.str());
    }

    void go(const std::vector<std::string>& tokens,
            std::chrono::steady_clock::time_point received_at) {
        stop();
        // An invalid diagnostic must not fall through to ordinary go and start
        // an unlimited search. No evaluation network is needed for legal perft.
        if (tokens.size() > 1 && tokens[1] == "perft") { go_perft(tokens); return; }
        SearchLimits limits;
        limits.received_at = received_at;
        limits.move_overhead_ms = overhead_ms_;
        limits.time_policy = time_policy_;
        limits.diagnostics = diagnostics_;
        limits.late_move_reductions = late_move_reductions_;
        limits.deep_quiet_reductions = deep_quiet_reductions_;
        limits.capture_ordering = capture_ordering_;
        limits.countermove_ordering = countermove_ordering_;
        limits.null_move_pruning = null_move_pruning_;
        limits.reverse_futility_pruning = reverse_futility_pruning_;
        limits.qsearch_see_pruning = qsearch_see_pruning_;
        limits.probcut = probcut_;
        limits.tt_move_hints = tt_move_hints_;
        limits.syzygy_probe_limit = syzygy_probe_limit_;
        limits.syzygy_probe_depth = syzygy_probe_depth_;
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
#ifdef CHESS0LIVE_CLOCK_TRACE
        auto clock_trace = command_trace_;
        clock_trace.sequence = ++command_trace_.sequence;
        clock_trace.go_received_ns = trace_ns(received_at);
#endif
        worker_ = std::thread([this, limits, root = position_, history = history_
#ifdef CHESS0LIVE_CLOCK_TRACE
                              , clock_trace
#endif
                             ]() mutable {
#ifdef CHESS0LIVE_CLOCK_TRACE
            clock_trace.worker_started_ns = trace_ns();
#endif
            SearchResult result;
            // A startup/allocation failure still leaves a legal response. The
            // explicit error remains visible; this is not a completed search.
            try {
                const auto fallback = root.legal_moves();
                if (!fallback.empty()) result.best = fallback.front();
                result = search_.search(root, std::move(history), limits,
                    [this](const auto& info) { report(info); });
            }
            catch (const std::exception& error) { output(std::string("info string search error: ") + error.what()); }
#ifdef CHESS0LIVE_CLOCK_TRACE
            clock_trace.search_returned_ns = trace_ns();
#endif
            {
                std::unique_lock lock(result_mutex_);
                result_ready_.wait(lock, [this] { return !hold_result_; });
            }
            // Completed-depth reports cannot include the unfinished iteration.
            // Publish exact totals after helpers join, without repeating a
            // depth/score/PV that could be mistaken for another completed depth.
            output("info nodes " + std::to_string(result.nodes)
                   + " time " + std::to_string(result.time_ms)
                   + " nps " + std::to_string(result.nodes * 1000
                       / static_cast<std::uint64_t>(std::max<std::int64_t>(1, result.time_ms)))
                   + " hashfull " + std::to_string(result.hashfull)
                   + " tbhits " + std::to_string(result.tbhits));
            report_diagnostics(result);
            std::string line = "bestmove " + result.best.uci();
            if (result.ponder.valid()) line += " ponder " + result.ponder.uci();
#ifdef CHESS0LIVE_CLOCK_TRACE
            traced_bestmove(line, result, clock_trace);
#else
            output(line);
#endif
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
        display();
        if (!ensure_network()) return;
        const auto raw = network_.evaluate(position_);
        nnue::Evaluator evaluator(network_);
        const int score = evaluator.evaluate(position_);
        if (position_.in_check(position_.turn())) {
            output("NNUE evaluation: unavailable while in check; raw static diagnostic below is not a search score or mate assessment");
        } else {
            const std::string side = position_.turn() == Color::white ? "White" : "Black";
            std::ostringstream line;
            line << "NNUE evaluation: " << std::showpos << std::fixed << std::setprecision(2)
                 << display_centipawns(score) / 100.0 << " pawns (" << side
                 << " to move; positive favors " << side << "; static, not a search score)";
            output(line.str());
        }
        // Keep the raw diagnostic record last for console parsers.
        output("eval psqt " + std::to_string(raw.psqt) + " positional " + std::to_string(raw.positional)
               + " score " + std::to_string(score));
    }

    /** Display is a pure view: flip changes coordinates on paper, never pieces,
     * side to move, the hash, repetition history, or evaluation perspective.
     * Explicit console commands use plain text. Ordinary UCI search output
     * remains protocol-formatted; retain the FEN as the final view sentinel.
     */
    void display() {
        const auto fields = words(position_.fen());
        output(std::string("Board (") + (flipped_ ? "Black" : "White")
               + " at bottom; White uppercase, Black lowercase)");
        constexpr const char* border = "  +---+---+---+---+---+---+---+---+";
        output(border);
        for (int row = 0; row < 8; ++row) {
            const int rank = flipped_ ? row : 7 - row;
            std::string line = std::to_string(rank + 1) + " |";
            for (int column = 0; column < 8; ++column) {
                const int file = flipped_ ? 7 - column : column;
                const auto piece = position_.at(rank * 8 + file);
                const auto type = static_cast<unsigned>(type_of(piece));
                line += ' ';
                line += piece < 0 ? " pnbrqk"[type] : " PNBRQK"[type];
                line += " |";
            }
            output(line);
            output(border);
        }
        output(flipped_ ? "    h   g   f   e   d   c   b   a"
                        : "    a   b   c   d   e   f   g   h");
        std::ostringstream key;
        key << "key 0x" << std::hex << std::uppercase << std::setw(16)
            << std::setfill('0') << position_.key();
        output(key.str());
        output(std::string("side ") + (position_.turn() == Color::white ? "White" : "Black"));
        output("castling " + fields[2]);
        output("en-passant " + fields[3]);
        output("halfmove " + fields[4]);
        output("fullmove " + fields[5]);
        output(std::string("check ") + (position_.in_check(position_.turn()) ? "yes" : "no"));
        output("fen " + position_.fen());
    }

    void help() {
        for (const char* line : {
            "chess0live commands (console diagnostics use plain text):",
            "d | show | display: show the board, FEN, hash, and position state",
            "flip: toggle White/Black at bottom and display; position is unchanged",
            "eval: display the board and static NNUE evaluation (positive favors side to move)",
            "position startpos [moves <UCI moves>]: load start position and optional history",
            "position fen <six fields> [moves <UCI moves>]: load a position and optional history",
            "position fen <four or six fields> bm <notes>: ignore puzzle answer metadata",
            "go perft N: legal move counts by root, total, elapsed milliseconds, nodes/second (0..16)",
            "perft N | divide N: legacy synchronous count/divide diagnostics (0..16)",
            "go depth N | go nodes N | go movetime MS: bounded search; limits may be combined",
            "go wtime MS btime MS [winc MS binc MS movestogo N]: clock-managed search",
            "go infinite: untimed search; go ponder: ponder until ponderhit starts the clock",
            "go also accepts mate N and searchmoves <UCI moves>; use stop to return the current best move",
            "stop: finish search or cancel go perft; ponderhit: start the ponder clock",
            "uci: identify engine and list options; setoption name <name> [value <value>]: configure",
            "isready: check readiness; ucinewgame: clear search state; quit: exit",
            "help: show this command reference"}) output(line);
    }

    /** A separate diagnostic traversal permits responsive stop/quit without
     * changing the established, synchronous perft API or its test contract.
     * Aborted subtrees return no count; completed root counts remain identifiable.
     */
    std::optional<std::uint64_t> cancellable_perft(Position& root, unsigned depth) {
        if (perft_stop_.load(std::memory_order_relaxed)) return std::nullopt;
        if (depth == 0) return 1;
        const auto moves = root.legal_moves();
        if (depth == 1) return moves.size();
        std::uint64_t nodes = 0;
        for (const auto move : moves) {
            const auto undo = root.make_move(move);
            const auto child = cancellable_perft(root, depth - 1);
            root.unmake_move(move, undo);
            if (!child) return std::nullopt;
            if (*child > std::numeric_limits<std::uint64_t>::max() - nodes)
                throw std::overflow_error("perft count exceeds 64-bit range");
            nodes += *child;
        }
        return nodes;
    }

    void go_perft(const std::vector<std::string>& tokens) {
        unsigned depth = 0;
        if (tokens.size() != 3 || !number(tokens[2], depth) || depth > 16) {
            output("info string error: expected go perft depth (0..16)"); return;
        }
        perft_stop_.store(false, std::memory_order_relaxed);
        worker_ = std::thread([this, depth, root = position_]() mutable {
            const auto begin = std::chrono::steady_clock::now();
            std::uint64_t nodes = 0;
            bool complete = true;
            try {
                if (depth == 0) nodes = 1;
                else {
                    auto moves = root.legal_moves();
                    std::sort(moves.begin(), moves.end(), [](Move a, Move b) { return a.uci() < b.uci(); });
                    for (const auto move : moves) {
                        const auto undo = root.make_move(move);
                        const auto child = cancellable_perft(root, depth - 1);
                        root.unmake_move(move, undo);
                        if (!child) { complete = false; break; }
                        if (*child > std::numeric_limits<std::uint64_t>::max() - nodes)
                            throw std::overflow_error("perft count exceeds 64-bit range");
                        nodes += *child;
                        output(move.uci() + ": " + std::to_string(*child));
                    }
                }
                const auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - begin).count();
                std::ostringstream summary;
                summary << "perft " << (complete ? "complete" : "stopped")
                        << " depth " << depth << (complete ? " nodes " : " completed_root_nodes ") << nodes
                        << " time_ms " << std::fixed << std::setprecision(3) << elapsed * 1000.0
                        << " nps " << std::setprecision(0) << nodes / std::max(elapsed, 1e-9);
                output(summary.str());
            } catch (const std::exception& error) {
                output(std::string("info string error: go perft failed: ") + error.what());
            }
        });
    }
};
} // namespace
} // namespace chess0live

int main(int argc, char** argv) {
    if (argc == 2 && std::string_view(argv[1]) == "--version") {
        std::cout << "chess0live 0.1-dev\n"; return 0;
    }
    if (argc == 2 && std::string_view(argv[1]) == "--help") {
        std::cout << "chess0live is a UCI engine.\n"
                     "Usage: chess0live [--eval-file PATH]\n"
                     "       chess0live --help | --version\n"
                     "--eval-file loads exactly PATH and advertises it as the UCI launch default.\n"
                     "A later setoption name EvalFile value PATH explicitly overrides that choice.\n"
                     "Diagnostics on stdin: help, d/show/display, flip, eval, go perft N, perft N, divide N.\n";
        return 0;
    }
    std::optional<std::filesystem::path> initial_network;
    if (argc != 1) {
        if (argc != 3 || std::string_view(argv[1]) != "--eval-file"
            || std::string_view(argv[2]).empty() || std::string_view(argv[2]).starts_with("--")) {
            std::cerr << "chess0live: expected no arguments, --eval-file PATH, --help or --version\n";
            return 2;
        }
        initial_network = argv[2];
    }
    try {
        chess0live::Controller controller(argv[0], initial_network);
        controller.run();
    } catch (const std::exception& error) {
        std::cerr << "chess0live: " << error.what() << '\n'; return 1;
    }
}
