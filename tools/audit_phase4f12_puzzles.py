#!/usr/bin/env python3
"""Independently replay Phase 4F.12 raw puzzle evidence; never infer Elo.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This auditor intentionally imports no campaign parser, validator or summary.
Its input is the saved report plus complete raw process transcripts and pinned
files. It checks evidence consistency, not the truth of the engine's mate claim.
Only the frozen executable differs between roles; all configured options are identical.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time as civil_time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess

ROOT = Path(__file__).resolve().parents[1]
FIXED_SHA256 = {
    "engine_baseline": "8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc",
    "engine_candidate": "04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594",
    "network": "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2",
    "corpus": "a49062bd0aa5b8d3af66842b266b4f8a8f7871cf64392a96861ea2faa2f5d035",
    "owner_source": "9fe64dc972744c8589bdfde1ac4b29f1c9bc44931922aafe5b88dc9e9d140c1c",
}
SOURCE_REVISIONS = {"baseline": "1ca87d6a596531d19b7b698b84c171fc314fc046",
                    "candidate": "3ee5eff30981b73099e8a118ff1712f89cdc285a"}
COMPILE_FLAGS = "-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g"
REQUIRED_ASSETS = {
    "pins", "manifest_baseline", "manifest_candidate", "docs/experiments/phase4f12.md", "Makefile",
    "tools/check_phase4f12_puzzles.py", "tests/phase4f12_puzzles_test.py",
    "tools/audit_phase4f12_puzzles.py", "tests/audit_phase4f12_puzzles_test.py",
    "tools/check_phase4f3_puzzles.py", "tools/bench.py", "tools/compare_bench.py",
    "tools/profile_smp.py", "tools/profile_search.py", "tools/resources.py",
    "tools/uci_client.py", "tools/tooling.py", "tools/run.py",
    "tools/python-packages.json", "requirements-match.txt", "networks/manifest.json",
}
BASE_OPTIONS = {
    "Threads": "8", "Hash": "64", "Ponder": "false", "Move Overhead": "20",
    "Time Policy": "classic", "Search Diagnostics": "false",
    "Late Move Reductions": "true", "Deep Quiet Reductions": "false",
    "Capture Ordering": "mvv-lva", "Countermove Ordering": "false",
    "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
    "QSearch SEE Pruning": "false", "ProbCut": "false",
    "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
    "TT Move Hints": "false", "Continuation History": "false",
}
SPIN_OPTIONS = {"Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth"}
STRING_OPTIONS = {"EvalFile", "SyzygyPath"}
COMBO_OPTIONS = {"Time Policy", "Capture Ordering"}
ADVERTISED_DEFAULTS = dict(BASE_OPTIONS, Threads="1", SyzygyProbeLimit="7",
                           EvalFile="nn-1a298aa575a0.nnue")
ITERATION = re.compile(
    r"info depth ([0-9]+) seldepth ([0-9]+) score (cp|mate) (-?[0-9]+) "
    r"nodes ([0-9]+) time ([0-9]+) nps ([0-9]+) hashfull ([0-9]+) tbhits 0 pv (.+)")
TOTALS = re.compile(r"info nodes ([0-9]+) time ([0-9]+) nps ([0-9]+) hashfull ([0-9]+) tbhits 0")
BEST = re.compile(r"bestmove ([a-h][1-8][a-h][1-8][nbrq]?)(?: ponder ([a-h][1-8][a-h][1-8][nbrq]?))?")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value), "Invalid numeric " + name)
    return value


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, "Invalid integer " + name)
    return value


def options_for(role, network):
    """Reconstruct the experiment independently; never trust saved recipes."""
    require(role in ("baseline", "candidate"), "Unknown role")
    return dict(BASE_OPTIONS, EvalFile=str(network))


def validate_identity(lines, options):
    """Independently inspect UCI option types, bounds, choices and defaults."""
    require(lines[-1:] == ["uciok"] and lines.count("uciok") == 1, "Invalid UCI identity ending")
    require(sum(line.startswith("id name chess0live ") for line in lines) == 1, "Missing engine identity")
    require(lines.count("id author Claudio M. Camacho") == 1, "Missing author identity")
    declarations = {}
    for line in lines[:-1]:
        if line.startswith("id "):
            require(line.startswith("id name ") or line.startswith("id author "), "Unknown identity field")
            continue
        match = re.fullmatch(r"option name (.+) type (spin|check|combo|string|button)(.*)", line)
        require(match is not None, "Unexpected identity output")
        name, kind, tail = match.groups()
        require(name not in declarations, "Duplicate option declaration")
        declarations[name] = (kind, tail)
    require(set(declarations) == set(options) | {"Clear Hash"}, "Missing or unexpected advertised option")
    require(declarations["Clear Hash"] == ("button", ""), "Invalid Clear Hash declaration")
    for name, value in options.items():
        kind, tail = declarations[name]
        expected = "spin" if name in SPIN_OPTIONS else "string" if name in STRING_OPTIONS else "combo" if name in COMBO_OPTIONS else "check"
        require(kind == expected, "Wrong option type: " + name)
        default = re.search(r"(?:^| )default (.*?)(?= min | max | var |$)", tail)
        require(default is not None and default[1] == ADVERTISED_DEFAULTS[name], "Wrong advertised default: " + name)
        if kind == "spin":
            low, high = re.search(r" min ([0-9]+)", tail), re.search(r" max ([0-9]+)", tail)
            require(low and high and int(low[1]) <= int(value) <= int(high[1]), "Unsupported option range")
        if kind == "combo":
            require(value in re.findall(r" var (\S+)", tail), "Unsupported option choice")


def legal_line(board, moves):
    replay = board.copy()
    for token in moves:
        try:
            move = chess.Move.from_uci(token)
        except ValueError as error:
            raise ValueError("Malformed move in raw evidence") from error
        require(move in replay.legal_moves, "Illegal move in raw evidence: " + token)
        replay.push(move)
    return replay


def parse_search(lines, position):
    """Parse exact uninstrumented output and replay every completed PV."""
    board = chess.Board(position["fen"])
    require(board.is_valid() and not board.is_game_over(claim_draw=True), "Invalid or terminal puzzle")
    iterations, totals, best, ponder = [], None, None, None
    pv_plies = 0
    for line in lines:
        require(best is None, "Output follows bestmove")
        match = ITERATION.fullmatch(line)
        if match:
            require(totals is None, "Iteration follows totals")
            depth, seldepth, kind, score, nodes, elapsed, nps, occupancy, pv = match.groups()
            row = dict(depth=int(depth), seldepth=int(seldepth), score=dict(type=kind, value=int(score)),
                       nodes=int(nodes), time=int(elapsed), nps=int(nps), hashfull=int(occupancy), pv=pv.split())
            require(row["depth"] == len(iterations) + 1 and row["depth"] <= 126, "Invalid completed depth sequence")
            require(0 <= row["hashfull"] <= 1000 and row["nodes"] > 0, "Invalid iteration counter")
            require(all(row[key] <= 2**64 - 1 for key in ("nodes", "time", "nps", "seldepth")), "Overflowed counter")
            require(not iterations or all(row[key] >= iterations[-1][key] for key in ("nodes", "time")), "Iteration counters went backwards")
            legal_line(board, row["pv"])
            pv_plies += len(row["pv"])
            iterations.append(row)
            continue
        match = TOTALS.fullmatch(line)
        if match:
            require(iterations and totals is None, "Missing iterations or duplicate totals")
            totals = dict(zip(("nodes", "time", "nps", "hashfull"), map(int, match.groups())), tbhits=0)
            require(0 <= totals["hashfull"] <= 1000 and all(totals[k] <= 2**64 - 1 for k in ("nodes", "time", "nps")), "Invalid final counters")
            require(all(totals[key] >= iterations[-1][key] for key in ("nodes", "time")), "Final counters went backwards")
            continue
        match = BEST.fullmatch(line)
        require(match is not None and totals is not None, "Unexpected or malformed raw search output")
        best, ponder = match.groups()
        legal_line(board, [best] + ([ponder] if ponder else []))
    require(iterations and best is not None and totals is not None, "Incomplete search transcript")
    final = iterations[-1]
    require(final["pv"][0] == best and (ponder is None or final["pv"][1:2] == [ponder]), "PV and bestmove disagree")
    score = final["score"]
    mate = score["value"] if score["type"] == "mate" else None
    result = dict(bestmove=best, ponder=ponder, completed_depth=final["depth"],
                  reported_nodes=totals["nodes"], reported_time_ms=totals["time"], reported_nps=totals["nps"],
                  score=score, hashfull=totals["hashfull"], iterations=iterations, final_aggregate=totals,
                  score_cp=score["value"] if score["type"] == "cp" else None, reported_mate=mate,
                  supplied_mate=position["supplied_mate"], reported_positive_mate=mate is not None and mate > 0,
                  reported_mate_matches_supplied=mate == position["supplied_mate"],
                  first_positive_mate_iteration=next((row for row in iterations if row["score"]["type"] == "mate" and row["score"]["value"] > 0), None),
                  final_pv_ends_in_checkmate=legal_line(board, final["pv"]).is_checkmate())
    return result, pv_plies


def validate_resource(policy, wall):
    """Recompute scheduling admission; reported reservations are not OS caps."""
    cpus = integer(policy.get("logical_cpus"), "logical CPUs", 1)
    percent = integer(policy.get("percent"), "resource percentage", 1)
    require(percent <= 100, "Invalid resource percentage")
    local = datetime.fromtimestamp(wall, ZoneInfo("Europe/Helsinki"))
    nighttime = local.hour >= 23 or local.hour < 7
    require(policy.get("timezone") == "Europe/Helsinki", "Wrong resource timezone")
    source = policy.get("source")
    require(source in ("manual", "nighttime", "daytime"), "Invalid resource source")
    if source != "manual":
        require(source == ("nighttime" if nighttime else "daytime") and percent == (80 if nighttime else 50), "Resource window percentage mismatch")
    allowed = max(1, math.floor(cpus * percent / 100))
    require(policy.get("max_cpu_workers") == allowed and allowed >= 8, "Insufficient CPU admission")
    require(policy.get("active_search_workers") == 8 and policy.get("resident_engines") == 1, "Wrong admitted process/worker count")
    require(policy.get("memory_fraction") == percent / 100 and policy.get("memory_estimate_is_hard_cap") is False, "Invalid memory policy")
    reserved = integer(policy.get("estimated_memory_bytes"), "memory reservation", 2 * 1024**3)
    physical = integer(policy.get("physical_memory_bytes"), "physical memory", 1)
    require(reserved <= physical * percent / 100, "Insufficient memory admission")
    recorded = datetime.fromisoformat(policy["local_time"])
    require(recorded.tzinfo is not None and abs(recorded.timestamp() - wall) <= 2, "Resource timestamp mismatch")


def validate_clocks(events):
    """Reconstruct continuity from all chronological raw/monitor observations."""
    require(events, "No clock evidence")
    previous = None
    first = None
    max_gap = max_drift = 0.0
    for event in sorted(events, key=lambda row: row["monotonic"]):
        wall = finite(event.get("wall"), "wall timestamp")
        mono = finite(event.get("monotonic"), "monotonic timestamp")
        first = first or (wall, mono)
        drift = abs((wall - first[0]) - (mono - first[1]))
        max_drift = max(max_drift, drift)
        require(drift <= 5, "Cumulative clock discontinuity")
        if previous:
            wall_gap, mono_gap = wall - previous[0], mono - previous[1]
            require(wall_gap >= 0 and mono_gap >= 0, "Clock went backwards")
            require(max(wall_gap, mono_gap) <= 5, "Monitoring/clock gap exceeds five seconds")
            max_gap = max(max_gap, wall_gap, mono_gap)
        previous = (wall, mono)
    return dict(max_gap_seconds=max_gap, max_clock_drift_seconds=max_drift)


def validate_assets(report):
    """Check the separately frozen manifest and every current/before/after byte."""
    assets, after = report.get("assets"), report.get("after_sha256")
    require(isinstance(assets, dict) and isinstance(after, dict) and set(assets) == set(after), "Incomplete asset identities")
    require(set(FIXED_SHA256) | REQUIRED_ASSETS <= set(assets), "Missing required campaign inputs")
    for name, entry in assets.items():
        require(isinstance(entry, dict) and set(entry) >= {"path", "sha256"}, "Invalid asset record")
        require(re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None, "Malformed asset hash")
        path = Path(entry["path"])
        require(path.is_absolute() and path.is_file(), "Missing absolute asset path")
        require(digest(path) == entry["sha256"] == after[name], "Changed pinned asset: " + name)
        if name in FIXED_SHA256:
            require(entry["sha256"] == FIXED_SHA256[name], "Wrong fixed input: " + name)
    manifest = read_json(assets["pins"]["path"])
    require(manifest.get("schema_version") == 1, "Unsupported preparation manifest")
    require(manifest.get("engine_source_revisions") == SOURCE_REVISIONS, "Wrong engine source revisions")
    require(manifest.get("assets") == {name: entry["sha256"] for name, entry in assets.items() if name != "pins"}, "Prepared manifest and report asset map differ")
    require(assets["engine_baseline"]["sha256"] != assets["engine_candidate"]["sha256"], "Both roles use the same binary")
    for role, revision in SOURCE_REVISIONS.items():
        frozen_root = (ROOT / "build/experiments/phase4f12" / role).resolve()
        require(frozen_root.is_relative_to(ROOT.resolve()), "Frozen role directory escapes repository")
        engine = assets["engine_" + role]
        build_manifest = assets["manifest_" + role]
        require(engine["path"] == str(frozen_root / "chess0live")
                and Path(engine["path"]).resolve() == frozen_root / "chess0live", "Wrong role executable path")
        require(build_manifest["path"] == str(frozen_root / "manifest.json")
                and Path(build_manifest["path"]).resolve() == frozen_root / "manifest.json", "Wrong role manifest path")
        provenance = read_json(build_manifest["path"])
        require(provenance.get("schema_version") == 1 and provenance.get("role") == role
                and provenance.get("engine_source_revision") == revision
                and provenance.get("binary_sha256") == engine["sha256"]
                and provenance.get("network_sha256") == assets["network"]["sha256"]
                and provenance.get("compile_flags") == COMPILE_FLAGS, "Invalid frozen build provenance")
        require(isinstance(provenance.get("source_sha256"), dict) and provenance["source_sha256"], "Missing source provenance")
        source_root = frozen_root / "source"
        for name, identity in provenance["source_sha256"].items():
            path = ROOT / name
            require(not Path(name).is_absolute() and ".." not in Path(name).parts
                    and path.resolve().is_relative_to(source_root), "Build source is outside frozen directory")
            require(digest(path) == identity, "Build source provenance changed: " + name)
            require(name in assets and assets[name]["path"] == str(path.resolve())
                    and assets[name]["sha256"] == identity, "Missing or mismatched source asset: " + name)
        for field, leaf in (("origin_manifest", "origin-manifest.json"), ("build_log", "build.log")):
            name = provenance.get(field)
            require(isinstance(name, str) and not Path(name).is_absolute() and ".." not in Path(name).parts,
                    "Missing or unsafe " + field.replace("_", " "))
            path = ROOT / name
            require(path.resolve() == frozen_root / leaf, "Wrong " + field.replace("_", " ") + " path")
            require(name in assets and assets[name]["path"] == str(path.resolve())
                    and digest(path) == provenance.get(field + "_sha256") == assets[name]["sha256"],
                    "Missing or mismatched pinned " + field.replace("_", " "))
        origin = read_json(ROOT / provenance["origin_manifest"])
        if role == "baseline":
            require(origin.get("parent_commit") == revision
                    and origin.get("binary", {}).get("sha256") == engine["sha256"]
                    and origin.get("binary", {}).get("flags") == COMPILE_FLAGS
                    and origin.get("network_sha256") == assets["network"]["sha256"], "Wrong original build identity")
            original_sources = origin.get("sources")
        else:
            require(origin.get("candidate_sha256") == engine["sha256"]
                    and origin.get("baseline_sha256") == assets["engine_baseline"]["sha256"]
                    and re.fullmatch(r"[0-9a-f]{64}", str(origin.get("oracle_report_sha256"))) is not None,
                    "Wrong original build identity")
            original_sources = origin.get("source_sha256")
        require(isinstance(original_sources, dict) and original_sources, "Missing original build source inventory")
        expected_sources = {}
        for name, identity in original_sources.items():
            copied = source_root / name
            require(not Path(name).is_absolute() and ".." not in Path(name).parts
                    and copied.resolve().is_relative_to(source_root), "Unsafe original source path")
            expected_sources[str(copied.relative_to(ROOT.resolve()))] = identity
        require(provenance["source_sha256"] == expected_sources, "Normalized source inventory differs from original build")
    corpus = read_json(assets["corpus"]["path"])
    require(corpus.get("schema_version") == 1 and corpus.get("owner_source_sha256") == assets["owner_source"]["sha256"], "Invalid puzzle provenance")
    positions = corpus.get("positions")
    require(isinstance(positions, list) and len(positions) == 39 and positions == report.get("positions"), "Incomplete or altered position corpus")
    require(len({p["fen"] for p in positions}) == 39, "Repeated puzzle FEN")
    for index, position in enumerate(positions, 1):
        require(position.get("id") == f"puzzle-{index:02d}", "Wrong original puzzle order")
        integer(position.get("supplied_mate"), "supplied mate", 1)
        integer(position.get("spreadsheet_row"), "spreadsheet row", 1)
        board = chess.Board(position["fen"])
        require(board.is_valid() and not board.is_game_over(claim_draw=True), "Invalid frozen puzzle")
    return positions


class Transcript:
    """Consume every raw record exactly once, including EOF and process events."""
    def __init__(self, rows):
        self.rows, self.at = rows, 0

    def take(self):
        require(self.at < len(self.rows), "Truncated raw transcript")
        result = self.rows[self.at]
        self.at += 1
        return result

    def sent(self, command):
        row = self.take()
        require(row.get("direction") == ">" and row.get("line") == command and "event" not in row, "Unexpected raw command; expected " + command)
        return row

    def received(self):
        result = []
        while self.at < len(self.rows) and self.rows[self.at].get("direction") == "<" and self.rows[self.at].get("line") is not None:
            row = self.take()
            require(type(row["line"]) is str and "event" not in row, "Malformed raw output")
            result.append(row["line"])
        return result


def audit_session(sample, position, mode, directory, network, assets):
    require(sample.get("status") == "complete", "Incomplete session")
    require(not any(sample.get(key) for key in ("error", "shutdown_error")), "Session contains failure evidence")
    role = sample["role"]
    options = options_for(role, network)
    executable = assets["engine_" + role]
    require(sample.get("executable") == executable["path"]
            and sample.get("executable_sha256") == executable["sha256"], "Wrong role executable identity")
    require(sample.get("options") == options, "Incorrect recorded role options")
    filename = sample.get("raw_log")
    require(type(filename) is str and Path(filename).name == filename and filename not in (".", ".."), "Unsafe raw-log path")
    raw_path = directory / filename
    require(digest(raw_path) == sample.get("raw_sha256"), "Raw transcript hash changed")
    rows = [json.loads(line, object_pairs_hook=unique_object) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    require(rows, "Empty raw transcript")
    for previous, current in zip(rows, rows[1:]):
        require(all(finite(current.get(key), key) >= finite(previous.get(key), key) for key in ("wall", "monotonic")), "Raw clocks went backwards")
    raw = Transcript(rows)
    start = raw.take()
    pid = integer(sample.get("pid"), "PID", 1)
    require(start.get("event") == "process_start" and start.get("pid") == pid and "direction" not in start, "Missing or inconsistent process-start record")
    require(start.get("executable") == executable["path"]
            and start.get("executable_sha256") == executable["sha256"], "Wrong raw role executable identity")
    raw.sent("uci")
    identity = raw.received()
    require(sample.get("identity") == identity, "Identity summary differs from raw")
    validate_identity(identity, options)
    remaining = dict(options)
    while remaining:
        row = raw.take()
        require(row.get("direction") == ">" and isinstance(row.get("line"), str) and "event" not in row, "Missing option command")
        match = re.fullmatch(r"setoption name (.+) value (.*)", row["line"])
        require(match is not None and match[1] in remaining and remaining[match[1]] == match[2], "Wrong, duplicate or unknown applied option")
        del remaining[match[1]]
    raw.sent("isready")
    setup = raw.received()
    require(setup == ["info string Syzygy largest 0 pieces; table files are external", "readyok"] and sample.get("setup_output") == setup, "Unexpected setup readiness output")
    raw.sent("ucinewgame")
    if mode != "check":
        raw.sent("position fen " + position["fen"])
    raw.sent("isready")
    preparation = raw.received()
    require(preparation == ["readyok"] and sample.get("preparation_output") == preparation, "Unexpected preparation output")
    parsed, plies, search_span = None, 0, None
    if mode != "check":
        movetime = 1000 if mode == "smoke" else 60000
        go = raw.sent("go movetime " + str(movetime))
        output_start = raw.at
        lines = raw.received()
        require(sample.get("output") == lines, "Recorded search output differs from raw")
        parsed, plies = parse_search(lines, position)
        best_record = rows[output_start + len(lines) - 1]
        elapsed = best_record["monotonic"] - go["monotonic"]
        wall_elapsed = best_record["wall"] - go["wall"]
        require(min(elapsed, wall_elapsed) >= 0 and max(elapsed, wall_elapsed) <= movetime / 1000 + .250, "Search receipt exceeds fixed timing allowance")
        fields = {"search_started_wall": go["wall"], "search_started_monotonic": go["monotonic"],
                  "bestmove_received_wall": best_record["wall"], "bestmove_received_monotonic": best_record["monotonic"],
                  "elapsed_seconds": elapsed, "wall_elapsed_seconds": wall_elapsed}
        for key, value in fields.items():
            require(abs(finite(sample.get(key), key) - value) <= 1e-8, "Reported timing disagrees with raw: " + key)
        require(sample.get("within_receipt_tolerance") is True, "Missing receipt validation")
        require(abs(sample.get("movetime_overrun_seconds", -1) - max(0, max(elapsed, wall_elapsed) - movetime / 1000)) <= 1e-8, "Incorrect reported receipt overrun")
        require(isinstance(sample.get("result"), dict), "Missing parsed result")
        for key, value in parsed.items():
            require(sample["result"].get(key) == value, "Reported result differs from independent replay: " + key)
        raw.sent("isready")
        post = raw.received()
        require(post == ["readyok"] and sample.get("post_search_output") == post, "Unexpected post-search output")
        search_span = (go, best_record)
    else:
        require(sample.get("output") == [] and sample.get("post_search_output") == [] and "result" not in sample, "Readiness check contains search evidence")
    raw.sent("quit")
    eof = raw.take()
    require(eof.get("direction") == "<" and eof.get("line", "not-null") is None and "event" not in eof, "Missing clean EOF")
    end = raw.take()
    require(end.get("event") == "process_exit" and end.get("pid") == pid and end.get("exit_code") == 0
            and end.get("reader_alive") is False and end.get("shutdown_eof_count") == 1 and "direction" not in end, "Unclean or inconsistent process-exit record")
    require(raw.at == len(rows), "Unconsumed raw records after process exit")
    require(sample.get("exit_code") == 0 and sample.get("reader_alive") is False and sample.get("shutdown_eof_count") == 1
            and sample.get("shutdown_output") == [], "Unclean recorded shutdown")
    commands = [row["line"] for row in rows if row.get("direction") == ">"]
    transcript = [row["line"] for row in rows if row.get("direction") == "<" and row.get("line") is not None]
    require(commands == sample.get("commands") and transcript == sample.get("received_transcript"), "Recorded transcript does not exhaust raw I/O")
    return dict(result=parsed, pv_plies=plies, rows=rows, search_span=search_span, pid=pid,
                command_count=len(commands), output_count=len(transcript), start=start, end=end)


def audit(report_path):
    """Return an independent certificate only for complete, internally valid data."""
    report_path = Path(report_path).expanduser().resolve()
    report = read_json(report_path)
    require(report.get("schema_version") == 1 and report.get("status") == "complete", "Only complete schema-1 evidence can pass")
    require(report.get("protocol") == "phase4f12-nnue-puzzles-v1" and report.get("engine_source_revisions") == SOURCE_REVISIONS, "Wrong campaign or source identity")
    require(report.get("chess_version") == "1.11.2" and chess.__version__ == "1.11.2", "Pinned independent referee version required")
    mode = report.get("mode")
    require(mode in ("check", "smoke", "full"), "Unknown audit mode")
    expected_settings = {"movetime_ms": 0 if mode == "check" else 1000 if mode == "smoke" else 60000,
                         "total_seconds": 7200 if mode == "full" else 600}
    require(report.get("settings") == expected_settings, "Changed search or total duration")
    positions = validate_assets(report)
    network = report["assets"]["network"]["path"]
    options = {role: options_for(role, network) for role in ("baseline", "candidate")}
    require(report.get("options") == options, "Incorrect campaign option recipes")
    require(report.get("receipt_tolerance_seconds") == .250 and report.get("search_watchdog_grace_seconds") == 5.0
            and report.get("clock_gap_limit_seconds") == 5.0, "Changed fixed timing limits")
    require(type(report.get("allow_daytime")) is bool, "Missing daytime exception flag")
    require(not report["allow_daytime"] or mode == "full", "Invalid daytime exception mode")
    require(type(report.get("quiet_host")) is bool, "Invalid quiet-host assertion")
    if mode == "full":
        require(report.get("quiet_host") is True, "Full comparison lacks quiet-host acknowledgement")
    expected = [(None, role) for role in ("baseline", "candidate")] if mode == "check" else [
        (index, role) for index in range(39) for role in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline"))]
    samples = report.get("samples")
    require(isinstance(samples, list) and len(samples) == len(expected), "Missing or extra sessions")
    require(len({sample.get("raw_log") for sample in samples}) == len(samples), "Repeated raw transcript")
    results, all_clock_events = [], []
    for sample, (index, role) in zip(samples, expected):
        position = positions[index] if index is not None else None
        require(sample.get("position_index") == index and sample.get("role") == role
                and sample.get("position_id") == (position["id"] if position else None), "Wrong original position/role ordering")
        result = audit_session(sample, position, mode, report_path.parent, network, report["assets"])
        require(not results or result["start"]["monotonic"] >= results[-1]["end"]["monotonic"], "Search processes overlap")
        results.append(result)
        all_clock_events.extend(result["rows"])
    monitors = report.get("monitor_events")
    require(isinstance(monitors, list) and monitors, "Missing monitor evidence")
    for previous, current in zip(monitors, monitors[1:]):
        require(current["monotonic"] >= previous["monotonic"] and current["wall"] >= previous["wall"], "Monitor chronology reversed")
    for event in monitors:
        require(event.get("event") == "resource_check", "Monitor recorded failure or unknown event")
        validate_resource(event["policy"], event["wall"])
    validate_clocks(monitors)
    validate_resource(report["initial_resource_policy"], datetime.fromisoformat(report["started_utc"]).timestamp())
    require(monitors[0]["monotonic"] <= results[0]["start"]["monotonic"], "Monitor starts after first process")
    require(monitors[-1]["monotonic"] >= results[-1]["end"]["monotonic"], "Monitor does not cover last process exit")
    all_clock_events.extend(monitors)
    clocks = validate_clocks(all_clock_events)
    started, finished = datetime.fromisoformat(report["started_utc"]), datetime.fromisoformat(report["finished_utc"])
    require(started.tzinfo is not None and finished.tzinfo is not None and started <= finished, "Invalid report interval")
    require(started.timestamp() <= all_clock_events[0]["wall"] + 2 and finished.timestamp() >= results[-1]["end"]["wall"], "Report interval does not enclose sessions")
    cap = expected_settings["total_seconds"]
    require((finished - started).total_seconds() <= cap, "Campaign exceeded total watchdog")
    if mode == "full":
        local = started.astimezone(ZoneInfo("Europe/Helsinki"))
        require(report["allow_daytime"] or local.hour >= 23 or local.hour < 7, "Full run launched outside permitted window")
        end_date = local.date() + timedelta(days=int(local.hour >= 7))
        cutoff = datetime.combine(end_date, civil_time(7), tzinfo=local.tzinfo).astimezone(timezone.utc)
        require((cutoff - started).total_seconds() >= 5070 and finished <= cutoff, "Insufficient night window or passed cutoff")
        window = report.get("launch_window", {})
        require(window.get("cutoff_utc") == cutoff.isoformat(), "Wrong civil-time cutoff")
        require(window.get("timezone") == "Europe/Helsinki" and window.get("minimum_remaining_seconds") == 5070
                and window.get("allow_daytime") is report["allow_daytime"], "Incorrect launch-window policy fields")
        window_local = datetime.fromisoformat(window["local_time"])
        require(window_local.tzinfo is not None and abs(window_local.timestamp() - started.timestamp()) <= 5,
                "Launch-window timestamp differs from campaign start")
        actual_local = window_local.astimezone(ZoneInfo("Europe/Helsinki"))
        require(window_local.utcoffset() == actual_local.utcoffset()
                and window.get("nighttime") is (actual_local.hour >= 23 or actual_local.hour < 7), "Wrong launch-window nighttime or offset")
    counters = ("reported_positive_mate", "reported_mate_matches_supplied", "final_pv_ends_in_checkmate")
    roles = {role: {field: 0 for field in counters} for role in options}
    lookup = {}
    for sample, replay in zip(samples, results):
        if replay["result"] is not None:
            for field in counters:
                roles[sample["role"]][field] += bool(replay["result"][field])
            lookup[sample["position_id"], sample["role"]] = replay["result"]
    same_best = sum(lookup[p["id"], "baseline"]["bestmove"] == lookup[p["id"], "candidate"]["bestmove"] for p in positions) if mode != "check" else 0
    summary = dict(positions=39, sessions=len(results), searches=0 if mode == "check" else len(results))
    if mode != "check":
        gains = [p["id"] for p in positions if lookup[p["id"], "candidate"]["reported_positive_mate"] and not lookup[p["id"], "baseline"]["reported_positive_mate"]]
        losses = [p["id"] for p in positions if lookup[p["id"], "baseline"]["reported_positive_mate"] and not lookup[p["id"], "candidate"]["reported_positive_mate"]]
        summary.update(roles=roles, same_bestmove=same_best,
                       positive_mate_report_gains=gains, positive_mate_report_losses=losses)
    require(isinstance(report.get("summary"), dict), "Missing campaign summary")
    for key, value in summary.items():
        require(report["summary"].get(key) == value, "Summary differs from raw reconstruction: " + key)
    return dict(schema_version=1, status="passed", mode=mode, report_sha256=digest(report_path),
                assets_checked=len(report["assets"]), raw_sessions=len(results), zero_exits=len(results),
                distinct_recorded_pids=len({result["pid"] for result in results}),
                searches=0 if mode == "check" else len(results), positions=0 if mode == "check" else 39,
                iterations=sum(len(result["result"]["iterations"]) for result in results if result["result"]),
                legal_pv_plies=sum(result["pv_plies"] for result in results),
                legal_best_ponder_plies=sum(1 + int(result["result"]["ponder"] is not None) for result in results if result["result"]),
                commands=sum(result["command_count"] for result in results),
                consumed_output_lines=sum(result["output_count"] for result in results),
                readiness_barriers=len(results) * (2 if mode == "check" else 3),
                resource_observations=len(monitors), roles=roles, same_bestmove=same_best, **clocks,
                interpretation="Independent raw replay and identity consistency only. PID records and reservations are harness evidence, not OS utilization telemetry. Exposed puzzle scores, supplied mate annotations and legal mating PVs do not prove forced mate, speed or playing strength.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Saved Phase 4F.12 report.json")
    parser.add_argument("--output", type=Path, help="New JSON certificate; existing files are never overwritten")
    args = parser.parse_args(argv)
    if args.output:
        require(not args.output.expanduser().resolve().is_relative_to(args.report.expanduser().resolve().parent),
                "Audit output must be outside the attempt directory")
    result = audit(args.report)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.expanduser().open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.exit("Independent puzzle audit failed: " + str(error))
