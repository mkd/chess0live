#!/usr/bin/env python3
"""Bounded, matched-resource Phase 4F.3 puzzle comparison; never a strength proof.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Direct invocation prepares pinned Python dependencies automatically. Smoke uses
one second per search; full uses sixty seconds and normally requires the Helsinki
night window. --allow-daytime requires fresh explicit owner authorization for
that full run; supplying the flag does not itself establish approval. Both modes
retain all 39 supplied positions and start a fresh engine per role.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, time as civil_time, timedelta, timezone
import io
import json
import math
from pathlib import Path
import platform
import queue
import re
import signal
import subprocess
import sys
import time
import tokenize
from zoneinfo import ZoneInfo

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess

from bench import digest
from compare_bench import physical_memory, publish, reject_errors
from profile_smp import validate_result as parse_search_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "build/experiments/phase4f3/chess0live"
ENGINE_SHA256 = "5714cd8ab2e0a4a721922fa5e02881329e8d865bff87829d8c20fb82302aa947"
NETWORK = ROOT / "networks/nn-1a298aa575a0.nnue"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
CORPUS = ROOT / "tests/data/phase4f3-puzzles.json"
OWNER_SOURCE = ROOT / "tools/batch_positions.py"
THREADS, HASH_MB = 8, 64
GAP_LIMIT_SECONDS = 5.0
RECEIPT_TOLERANCE_SECONDS = 0.250
SEARCH_WATCHDOG_GRACE_SECONDS = 5.0
MODES = {"smoke": {"movetime_ms": 1000, "total_seconds": 600},
         "full": {"movetime_ms": 60000, "total_seconds": 7200}}
BASE_OPTIONS = {
    "Threads": "8", "Hash": "64", "Ponder": "false", "Move Overhead": "20",
    "Time Policy": "classic", "Search Diagnostics": "false",
    "Late Move Reductions": "true", "Deep Quiet Reductions": "false",
    "Capture Ordering": "mvv-lva", "Countermove Ordering": "false",
    "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
    "QSearch SEE Pruning": "false", "ProbCut": "false",
    "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
}
PACKAGE_OPTIONS = dict(BASE_OPTIONS, **{
    "Deep Quiet Reductions": "true", "Capture Ordering": "see",
    "Countermove Ordering": "true", "Null Move Pruning": "true",
    "Reverse Futility Pruning": "true", "QSearch SEE Pruning": "true", "ProbCut": "true",
})
OPTIONS = {"default": BASE_OPTIONS, "all-on": PACKAGE_OPTIONS}
OPTION_TYPES = {name: ("spin" if name in ("Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth")
                      else "combo" if name in ("Time Policy", "Capture Ordering")
                      else "string" if name == "SyzygyPath" else "check") for name in BASE_OPTIONS}
OPTION_TYPES["EvalFile"] = "string"
ADVERTISED_DEFAULTS = dict(BASE_OPTIONS, Threads="1", SyzygyProbeLimit="7")
TOOL_SOURCES = ("tools/check_phase4f3_puzzles.py", "tests/phase4f3_puzzles_test.py",
                "tools/bench.py", "tools/compare_bench.py", "tools/profile_smp.py",
                "tools/profile_search.py", "tools/resources.py", "tools/uci_client.py",
                "tools/tooling.py", "tools/python-packages.json", "requirements-match.txt",
                "networks/manifest.json")


def extract_positions(source):
    """Read literal FENS and its mate comments through AST/tokenization, never exec."""
    text = source.read_text(encoding="utf-8")
    assignments = [node for node in ast.parse(text).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "FENS" for target in node.targets)]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.List):
        raise ValueError("Owner source must contain one literal FENS list")
    comments = {token.start[0]: token.string for token in tokenize.generate_tokens(io.StringIO(text).readline)
                if token.type == tokenize.COMMENT}
    positions = []
    for index, node in enumerate(assignments[0].value.elts, 1):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            raise ValueError("FENS must contain literal strings only")
        annotation = re.fullmatch(r"# M([1-9][0-9]*), spreadsheet row ([1-9][0-9]*)", comments.get(node.end_lineno, ""))
        if annotation is None:
            raise ValueError("Missing or malformed supplied mate annotation")
        board = chess.Board(node.value)
        if not board.is_valid() or board.is_game_over(claim_draw=True):
            raise ValueError("Puzzle must be a valid, nonterminal chess position")
        positions.append(dict(id=f"puzzle-{index:02d}", fen=node.value,
                              supplied_mate=int(annotation[1]), spreadsheet_row=int(annotation[2])))
    if len(positions) != 39 or len({item["fen"] for item in positions}) != 39:
        raise ValueError("Expected all 39 distinct supplied positions")
    return positions


def load_positions():
    """The checked-in corpus must still match the owner's untouched source."""
    document = json.loads(CORPUS.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or document.get("owner_source_sha256") != digest(OWNER_SOURCE):
        raise ValueError("Puzzle corpus/source identity changed; revalidate provenance before a new campaign")
    positions = extract_positions(OWNER_SOURCE)
    if document.get("positions") != positions:
        raise ValueError("Puzzle corpus differs from owner FENS or mate annotations")
    return positions


def role_order(index):
    return ("default", "all-on") if index % 2 == 0 else ("all-on", "default")


def night_window(mode, now=None, *, allow_daytime=False):
    """A specifically authorized daytime launch still stops at the next 07:00.

    The caller must establish fresh owner authorization before using the flag.
    This records a requested exception; the tool cannot verify human approval.
    """
    if mode not in MODES:
        raise ValueError("Mode must be smoke or full")
    if type(allow_daytime) is not bool or (allow_daytime and mode != "full"):
        raise ValueError("--allow-daytime is a boolean full-audit option only")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("A timezone-aware clock is required")
    local = now.astimezone(ZoneInfo("Europe/Helsinki"))
    nighttime = local.hour >= 23 or local.hour < 7
    end_date = local.date() + timedelta(days=int(local.hour >= 7))
    cutoff = datetime.combine(end_date, civil_time(7), tzinfo=local.tzinfo).astimezone(timezone.utc)
    # Reserve the complete 78-search sample plus five seconds startup per case.
    minimum = 78 * (MODES[mode]["movetime_ms"] / 1000 + 5)
    if mode == "full" and not nighttime and not allow_daytime:
        raise ValueError("Full audit needs 23:00–07:00 Helsinki; --allow-daytime requires fresh explicit owner authorization for this run")
    if mode == "full" and (cutoff - now).total_seconds() < minimum:
        raise ValueError("Full audit needs at least 84.5 minutes before the next Helsinki 07:00 cutoff, including with --allow-daytime")
    return dict(timezone="Europe/Helsinki", local_time=local.isoformat(), nighttime=nighttime,
                cutoff_utc=cutoff.isoformat() if mode == "full" else None,
                minimum_remaining_seconds=minimum, allow_daytime=allow_daytime)


def resource_check(network):
    """Reserve one process, eight searching workers and at least 2 GiB."""
    policy = dict(current_budget())
    memory = physical_memory()
    if memory is None and sys.platform == "darwin":
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True,
                                            stderr=subprocess.DEVNULL, timeout=2))
    reservation = max(2 * 1024**3, HASH_MB * 1024**2 + 4 * network.stat().st_size
                      + (64 + 128 * THREADS) * 1024**2)
    if memory is None or memory <= 0:
        raise ValueError("Cannot determine physical RAM for the eight-worker audit")
    policy.update(active_search_workers=THREADS, resident_engines=1,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if THREADS > policy["max_cpu_workers"] or reservation > memory * policy["memory_fraction"]:
        raise ValueError("Eight workers or the minimum 2-GiB reservation exceed the current resource policy")
    return policy


class Monitor:
    """Poll throughout setup/search: abort after suspension, clock jumps or cutoff."""
    def __init__(self, mode, window, network, events):
        self.start_wall = self.last_wall = time.time()
        self.start_mono = self.last_mono = time.monotonic()
        self.deadline = self.start_mono + MODES[mode]["total_seconds"]
        self.cutoff = datetime.fromisoformat(window["cutoff_utc"]).timestamp() if window["cutoff_utc"] else None
        self.network, self.events = network, events
        self.next_resource = self.start_mono
        self.max_clock_discrepancy = self.max_poll_gap = 0.0

    def check(self, force_resource=False):
        wall, mono = time.time(), time.monotonic()
        gap = mono - self.last_mono
        wall_gap = wall - self.last_wall
        discrepancy = max(abs(wall_gap - gap),
                          abs((wall - self.start_wall) - (mono - self.start_mono)))
        self.max_clock_discrepancy = max(self.max_clock_discrepancy, discrepancy)
        self.max_poll_gap = max(self.max_poll_gap, gap)
        self.last_wall, self.last_mono = wall, mono
        if (discrepancy > GAP_LIMIT_SECONDS or gap > GAP_LIMIT_SECONDS or wall_gap > GAP_LIMIT_SECONDS
                or gap < 0 or wall_gap < 0):
            self.events.append(dict(event="clock_violation", wall=wall, monotonic=mono,
                                    poll_gap_seconds=gap, wall_gap_seconds=wall_gap,
                                    clock_discrepancy_seconds=discrepancy))
            raise RuntimeError("Host suspension, scheduling gap or clock discontinuity invalidated this audit")
        if mono >= self.deadline or (self.cutoff is not None and wall >= self.cutoff):
            raise TimeoutError("Audit total limit or Helsinki 07:00 cutoff reached")
        if force_resource or mono >= self.next_resource:
            event = dict(event="resource_check", wall=wall, monotonic=mono)
            self.events.append(event)
            event["policy"] = resource_check(self.network)
            self.next_resource = mono + 2.0


def read_until(engine, prefix, seconds, monitor, raw, received):
    """A bounded queue loop keeps resource and sleep checks active while searching."""
    deadline = time.monotonic() + seconds
    while True:
        monitor.check()
        remaining = min(deadline, monitor.deadline) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for " + prefix)
        try:
            line = engine.lines.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        monitor.check()
        if line is None:
            raise RuntimeError("Engine exited before " + prefix)
        engine.transcript.append(line)
        received.append(line)
        log_line(raw, "<", line)
        reject_errors([line])
        if line.startswith(prefix):
            return received


def log_line(raw, direction, line):
    raw.write(json.dumps(dict(wall=time.time(), monotonic=time.monotonic(), direction=direction, line=line)) + "\n")
    raw.flush()


def send(engine, command, raw, commands):
    commands.append(command)
    log_line(raw, ">", command)
    engine.send(command)


def validate_options(identity, options):
    for name, value in options.items():
        lines = [line for line in identity if line.startswith("option name " + name + " type ")]
        if len(lines) != 1:
            raise ValueError("Missing or duplicate required option: " + name)
        tokens = lines[0].split(" type ", 1)[1].split()
        kind = OPTION_TYPES[name]
        if tokens[0] != kind:
            raise ValueError("Wrong type for required option: " + name)
        if name in ADVERTISED_DEFAULTS and ("default" not in tokens
                or tokens[tokens.index("default") + 1] != ADVERTISED_DEFAULTS[name]):
            raise ValueError("Advertised default differs from the frozen current-default recipe: " + name)
        if kind == "spin" and not int(tokens[tokens.index("min") + 1]) <= int(value) <= int(tokens[tokens.index("max") + 1]):
            raise ValueError("Requested value outside engine range: " + name)
        if kind == "combo" and (" var " + value) not in lines[0]:
            raise ValueError("Missing requested option choice: " + name)


def validate_result(lines, fen, supplied_mate):
    """Replay every PV and final move; a reported mate is not an external proof."""
    for line in lines:
        tokens = line.split()
        if "lowerbound" in tokens or "upperbound" in tokens or tokens[:2] == ["info", "string"]:
            raise ValueError("Expected exact, uninstrumented search output")
        if tokens[:1] == ["info"]:
            if tokens.count("tbhits") != 1 or tokens[tokens.index("tbhits") + 1] != "0":
                raise ValueError("Tablebase hits must be explicitly zero")
    board = chess.Board(fen)
    result = parse_search_result(lines, board, "time", None)
    score = result["score"]
    result["score_cp"] = score["value"] if score["type"] == "cp" else None
    result["reported_mate"] = score["value"] if score["type"] == "mate" else None
    result["supplied_mate"] = supplied_mate
    result["reported_positive_mate"] = result["reported_mate"] is not None and result["reported_mate"] > 0
    result["reported_mate_matches_supplied"] = result["reported_mate"] == supplied_mate
    result["first_positive_mate_iteration"] = next((row for row in result["iterations"]
        if row["score"]["type"] == "mate" and row["score"]["value"] > 0), None)
    final = board.copy()
    for move in result["iterations"][-1]["pv"]:
        final.push_uci(move)  # All moves already independently validated above.
    result["final_pv_ends_in_checkmate"] = final.is_checkmate()
    result["mate_evidence_note"] = "Supplied annotations and engine mate scores are claims; legal PV replay does not prove a forced mate against every defense."
    return result


def validate_search_timing(sample, movetime_ms):
    """The generous hang watchdog never makes an overlong result comparable."""
    values = (sample["elapsed_seconds"], sample["wall_elapsed_seconds"])
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Invalid elapsed search timing")
    sample["movetime_overrun_seconds"] = max(0.0, max(values) - movetime_ms / 1000)
    sample["within_receipt_tolerance"] = sample["movetime_overrun_seconds"] <= RECEIPT_TOLERANCE_SECONDS
    if not sample["within_receipt_tolerance"]:
        raise RuntimeError("Bestmove receipt exceeded the fixed 250-ms timing tolerance; no resampling")


def run_case(sample, position, network, executable, output, mode, monitor):
    """Each role starts with completely fresh TT, histories and process state."""
    engine = None
    with (output / sample["raw_log"]).open("x", encoding="utf-8") as raw:
        sample.update(commands=[], setup_output=[], output=[])
        try:
            monitor.check(force_resource=True)
            engine = Engine(executable, cwd=ROOT)
            send(engine, "uci", raw, sample["commands"])
            identity = read_until(engine, "uciok", 20, monitor, raw, sample["setup_output"])
            options = dict(OPTIONS[sample["role"]], EvalFile=str(network))
            validate_options(identity, options)
            for name, value in options.items():
                send(engine, "setoption name " + name + " value " + value, raw, sample["commands"])
            send(engine, "isready", raw, sample["commands"])
            read_until(engine, "readyok", 30, monitor, raw, sample["setup_output"])
            if any(line.startswith("bestmove") for line in sample["setup_output"]):
                raise ValueError("Unexpected search result during setup")
            send(engine, "ucinewgame", raw, sample["commands"])
            send(engine, "position fen " + position["fen"], raw, sample["commands"])
            send(engine, "isready", raw, sample["commands"])
            ready = read_until(engine, "readyok", 10, monitor, raw, [])
            sample["setup_output"].extend(ready)
            if ready != ["readyok"]:
                raise ValueError("Unexpected output at position readiness barrier")
            monitor.check(force_resource=True)
            sample.update(status="searching", search_started_wall=time.time(), search_started_monotonic=time.monotonic())
            movetime = MODES[mode]["movetime_ms"]
            send(engine, f"go movetime {movetime}", raw, sample["commands"])
            read_until(engine, "bestmove ", movetime / 1000 + SEARCH_WATCHDOG_GRACE_SECONDS,
                       monitor, raw, sample["output"])
            sample["elapsed_seconds"] = time.monotonic() - sample["search_started_monotonic"]
            sample["wall_elapsed_seconds"] = time.time() - sample["search_started_wall"]
            sample["result"] = validate_result(sample["output"], position["fen"], position["supplied_mate"])
            validate_search_timing(sample, movetime)
            # A final readiness barrier catches extra results/errors before teardown.
            send(engine, "isready", raw, sample["commands"])
            sample["post_search_output"] = read_until(engine, "readyok", 5, monitor, raw, [])
            if sample["post_search_output"] != ["readyok"]:
                raise ValueError("Unexpected output after bestmove")
            monitor.check(force_resource=True)
            sample["status"] = "complete"
        except BaseException as error:
            sample.update(status="failed", error=type(error).__name__ + ": " + str(error))
            if engine is not None and engine.process.poll() is None:
                engine.process.kill()  # Stop resource/clock violations immediately, without another search grace period.
                engine.process.wait(timeout=5)
            raise
        finally:
            if engine is not None:
                if engine.process.poll() is None:
                    send(engine, "quit", raw, sample["commands"])
                engine.close()


def summarize(samples, positions):
    lookup = {(sample["position_id"], sample["role"]): sample for sample in samples}
    expected = {(position["id"], role) for position in positions for role in OPTIONS}
    if len(lookup) != len(samples) or set(lookup) != expected or any(item["status"] != "complete" for item in samples):
        raise ValueError("Puzzle audit lacks the complete paired matrix")
    roles = {role: {field: sum(bool(lookup[position["id"], role]["result"][field]) for position in positions)
                   for field in ("reported_positive_mate", "reported_mate_matches_supplied", "final_pv_ends_in_checkmate")}
             for role in OPTIONS}
    return dict(positions=len(positions), searches=len(samples), roles=roles,
                same_bestmove=sum(lookup[p["id"], "default"]["result"]["bestmove"] == lookup[p["id"], "all-on"]["result"]["bestmove"] for p in positions),
                interpretation="Exposed puzzle observations only. Different scores/moves are permitted. Neither mate annotations, legal PVs nor deeper search prove playing strength or forced mate correctness.")


def asset_paths():
    return dict({name: ROOT / name for name in TOOL_SOURCES}, engine=ENGINE, network=NETWORK,
                corpus=CORPUS, owner_source=OWNER_SOURCE)


def verify_assets(assets, frozen):
    after = {name: digest(path) for name, path in assets.items()}
    if any(after[name] != frozen[name]["sha256"] for name in assets):
        raise ValueError("A pinned input, tool or owner source changed during the audit")
    return after


def audit(mode, output, *, allow_daytime=False):
    if mode not in MODES:
        raise ValueError("Mode must be smoke or full")
    if type(allow_daytime) is not bool or (allow_daytime and mode != "full"):
        raise ValueError("--allow-daytime is a boolean full-audit option only")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Output already exists; preserve it and choose a fresh directory")
    paths = asset_paths()
    if any(any(ord(c) < 32 for c in str(path)) for path in paths.values()):
        raise ValueError("Asset paths must fit on one UCI line")
    if chess.__version__ != "1.11.2":
        raise ValueError("Pinned chess 1.11.2 is required; use the automatic direct launcher")
    positions = load_positions()
    frozen = {name: dict(path=str(path.resolve()), sha256=digest(path)) for name, path in paths.items()}
    if frozen["engine"]["sha256"] != ENGINE_SHA256 or frozen["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("Frozen Phase 4F.3 engine or pinned network identity mismatch")
    window = night_window(mode, allow_daytime=allow_daytime)
    initial_policy = resource_check(NETWORK)
    report = dict(schema_version=1, status="running", mode=mode, assets=frozen,
                  allow_daytime=allow_daytime,
                  authorization_note="The daytime flag records an operator request, not verified approval. Its use requires fresh explicit owner authorization for this full run.",
                  started_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
                  chess_version=chess.__version__, positions=positions, settings=dict(MODES[mode]),
                  options={role: dict(options, EvalFile=str(NETWORK)) for role, options in OPTIONS.items()},
                  launch_window=window, initial_resource_policy=initial_policy, samples=[], monitor_events=[],
                  receipt_tolerance_seconds=RECEIPT_TOLERANCE_SECONDS,
                  search_watchdog_grace_seconds=SEARCH_WATCHDOG_GRACE_SECONDS,
                  clock_gap_limit_seconds=GAP_LIMIT_SECONDS,
                  timing_note="Serial fresh processes, alternating first role by position; go-to-bestmove excludes setup. Timestamps are main-loop queue receipt times, not reader-thread arrival times. A 250-ms receipt tolerance covers helper joining and I/O; a five-second watchdog is only a process guard. Early completion is permitted; late observations fail without resampling. Eight search workers, one resident engine. Worker/memory limits are planning estimates, not OS utilization caps.")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "report.json"
    publish(target, report)
    monitor = Monitor(mode, window, NETWORK, report["monitor_events"])
    try:
        for index, position in enumerate(positions):
            for role in role_order(index):
                monitor.check(force_resource=True)
                verify_assets(paths, frozen)
                sample = dict(position_index=index, position_id=position["id"], role=role, status="preparing",
                              raw_log=f"{position['id']}-{role}.uci.jsonl")
                report["samples"].append(sample)
                publish(target, report)
                print(f"{index+1:02d}/{len(positions)} {role}: searching {MODES[mode]['movetime_ms']//1000}s; supplied M{position['supplied_mate']}", flush=True)
                run_case(sample, position, NETWORK, ENGINE, output, mode, monitor)
                result = sample["result"]
                display = f"M{result['reported_mate']}" if result["reported_mate"] is not None else f"cp {result['score_cp']:+d}"
                print(f"{index+1:02d}/{len(positions)} {role}: {display}, best {result['bestmove']}, depth {result['completed_depth']}", flush=True)
                publish(target, report)
        report["after_sha256"] = verify_assets(paths, frozen)
        report["summary"] = summarize(report["samples"], positions)
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      max_clock_discrepancy_seconds=monitor.max_clock_discrepancy,
                      max_poll_gap_seconds=monitor.max_poll_gap)
        if "after_sha256" not in report:
            report["after_sha256"] = {}
            for name, path in paths.items():
                try:
                    report["after_sha256"][name] = digest(path)
                except OSError:
                    report["after_sha256"][name] = None
        publish(target, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="smoke")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-daytime", action="store_true",
                        help="Full mode only: use only after fresh explicit owner authorization for this run. The flag does not establish approval; resources and the next 07:00 cutoff remain enforced.")
    args = parser.parse_args(argv)
    audit(args.mode, args.output, allow_daytime=args.allow_daytime)
    return 0


if __name__ == "__main__":
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except (KeyboardInterrupt, OSError, ValueError, RuntimeError, TimeoutError) as error:
        sys.exit(f"Puzzle audit stopped: {error}")
