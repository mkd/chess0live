#!/usr/bin/env python3
"""One bounded, equal-time comparison of three explicit search profiles.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The 45 fresh-process cells use exposed development roots. Depth, nodes and
evaluations are descriptive observations, never an Elo or speed qualification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import time

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess
from bench import digest
from compare_bench import physical_memory, reject_errors
from profile_cache import board_for
from profile_null_move import finish_session, publish
from profile_smp import validate_result as replay_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4f19-combinations.md"
CORPUS = ROOT / "tests/data/countermove-profile.json"
NETWORK = ROOT / "networks/nn-1a298aa575a0.nnue"
ENGINE_SHA256 = "8824e8588328ba8ef3f768247f4c68604eec0c1ff22b4655b5b39d7be8270d5e"
CORPUS_SHA256 = "afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
PROFILES = ("optional-off", "default", "all-on")
SEARCH_OPTIONS = ("Late Move Reductions", "Deep Quiet Reductions", "Countermove Ordering",
                  "Continuation History", "Null Move Pruning", "Reverse Futility Pruning",
                  "QSearch SEE Pruning", "QSearch Delta Pruning", "ProbCut", "TT Move Hints")
MOVETIME_MS, TOTAL_SECONDS, SEARCH_TIMEOUT = 5000, 300, 10
SOURCES = ("tools/profile_search_combinations.py", "tests/profile_search_combinations_test.py", "Makefile", "README.md",
           "tools/bench.py", "tools/compare_bench.py", "tools/profile_cache.py",
           "tools/profile_null_move.py", "tools/profile_search.py", "tools/profile_smp.py",
           "tools/resources.py", "tools/uci_client.py", "tools/run.py", "tools/tooling.py",
           "tools/python-packages.json", "requirements-match.txt", "networks/manifest.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def options_for(role, network):
    if role not in PROFILES:
        raise ValueError("Unknown search profile")
    options = {"Threads": "1", "Hash": "64", "EvalFile": str(network), "Ponder": "false",
               "Move Overhead": "20", "Time Policy": "classic", "Search Diagnostics": "false",
               "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
               "Capture Ordering": "see" if role == "all-on" else "mvv-lva"}
    options.update({name: "true" if role == "all-on" or
                    (role == "default" and name == "Late Move Reductions") else "false"
                    for name in SEARCH_OPTIONS})
    return options


def run_order(index):
    offset = index % len(PROFILES)
    return PROFILES[offset:] + PROFILES[:offset]


def source_paths():
    return {name: ROOT / name for name in SOURCES}


def load_positions():
    if digest(CORPUS) != CORPUS_SHA256:
        raise ValueError("The frozen exposed corpus changed")
    document = json.loads(CORPUS.read_text())
    positions = document.get("positions")
    if document.get("schema_version") != 1 or not isinstance(positions, list) or len(positions) != 15:
        raise ValueError("Expected all fifteen exposed development roots")
    seen = set()
    for row in positions:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] or row["id"] in seen:
            raise ValueError("Expected unique nonempty position IDs")
        board_for(row["position"])
        seen.add(row["id"])
    return positions


def resource_check(network):
    policy = dict(current_budget())
    memory = physical_memory()
    if memory is None and sys.platform == "darwin":
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=2))
    # Includes generous headroom for NNUE, score TT, hint table and history.
    reservation = max(2 * 1024**3, 64 * 1024**2 + 4 * network.stat().st_size + 256 * 1024**2)
    if memory is None or policy["max_cpu_workers"] < 1 or reservation > memory * policy["memory_fraction"]:
        raise ValueError("One serial engine cannot be admitted under the resource policy")
    policy.update(active_search_workers=1, resident_engines=1, reserved_memory_bytes=reservation,
                  physical_memory_bytes=memory, memory_reservation_is_hard_cap=False)
    return policy


def host_observation():
    """Observe AC and Automatic mode; a failed observation remains evidence."""
    result = {"checked_utc": utc_now(), "ac_power": False, "automatic": False, "passed": False}
    try:
        if sys.platform != "darwin":
            raise ValueError("This fixed local diagnostic requires the declared macOS host")
        for label, command in (("battery", ["pmset", "-g", "batt"]),
                               ("power", ["pmset", "-g", "custom"])):
            completed = subprocess.run(command, capture_output=True, text=True, timeout=2)
            result[label] = dict(command=command, returncode=completed.returncode,
                                 stdout=completed.stdout, stderr=completed.stderr)
        result["ac_power"] = (result["battery"]["returncode"] == 0 and
                              "Now drawing from 'AC Power'" in result["battery"]["stdout"])
        text = result["power"]["stdout"]
        sections = re.findall(r"(?ms)^AC Power:[ \t]*\n(.*?)(?=^\S[^\n]*:[ \t]*$|\Z)", text)
        ac_section = sections[0] if len(sections) == 1 else ""
        modes = dict(re.findall(r"(?m)^\s*(powermode|lowpowermode|highpowermode)\s+(\d+)\s*$", ac_section))
        result["mode_fields"] = modes
        result["automatic"] = (result["power"]["returncode"] == 0 and
                               ("powermode" in modes or "lowpowermode" in modes) and
                               all(value == "0" for value in modes.values()))
        result["passed"] = result["ac_power"] and result["automatic"]
        if not result["passed"]:
            result["error"] = "AC power and Automatic mode are required throughout the comparison"
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result["error"] = f"{type(error).__name__}: {error}"
    return result


def interpreter_identity():
    executable = Path(sys.executable).resolve()
    return dict(executable=sys.executable, resolved_executable=str(executable), sha256=digest(executable),
                version=sys.version, implementation=platform.python_implementation(),
                prefix=sys.prefix, base_prefix=sys.base_prefix, sys_path=list(sys.path),
                environment={name: os.environ.get(name) for name in
                             ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CHESS0LIVE_TOOLING_ACTIVE")},
                limitation="Interpreter and declared local files are pinned; this is not a full runtime dependency closure")


def validate_identity(lines, network):
    reject_errors(lines)
    if lines[:2] != ["id name chess0live 0.1-dev", "id author Claudio M. Camacho"] or lines[-1:] != ["uciok"]:
        raise ValueError("Unexpected engine identity or UCI handshake")
    expected = {
        "Hash": "spin default 64 min 1 max 16384", "Clear Hash": "button",
        "EvalFile": "string default " + network.name,
        "SyzygyPath": "string default <empty>", "SyzygyProbeLimit": "spin default 7 min 0 max 7",
        "SyzygyProbeDepth": "spin default 1 min 1 max 128", "Move Overhead": "spin default 20 min 0 max 5000",
        "Ponder": "check default false", "Time Policy": "combo default classic var classic var forecast var bounded",
        "Search Diagnostics": "check default false", "Capture Ordering": "combo default mvv-lva var mvv-lva var see",
    }
    expected.update({name: "check default " + ("true" if name == "Late Move Reductions" else "false")
                     for name in SEARCH_OPTIONS})
    found = {}
    for line in lines[2:-1]:
        match = re.fullmatch(r"option name (.+) type (.+)", line)
        if not match or match[1] in found:
            raise ValueError("Malformed or duplicate UCI option declaration")
        found[match[1]] = match[2]
    threads = found.pop("Threads", "")
    if not re.fullmatch(r"spin default 1 min 1 max [1-9]\d*", threads) or found != expected:
        raise ValueError("UCI options or advertised defaults differ from the pinned configuration")


def validate_result(lines, board):
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"] or "lowerbound" in tokens or "upperbound" in tokens:
            raise ValueError("Diagnostics and bounded scores are forbidden")
        if tokens[:1] == ["info"]:
            if tokens.count("tbhits") != 1 or tokens.index("tbhits") + 1 == len(tokens) or tokens[tokens.index("tbhits") + 1] != "0":
                raise ValueError("Every info record must report zero tablebase hits")
        if tokens[:2] == ["info", "depth"]:
            if len(tokens) < 20 or [tokens[i] for i in (1, 3, 5, 8, 10, 12, 14, 16, 18)] != [
                    "depth", "seldepth", "score", "nodes", "time", "nps", "hashfull", "tbhits", "pv"]:
                raise ValueError("Unexpected completed-iteration field layout")
    result = replay_result(lines, board, "movetime", None)
    final = result["iterations"][-1]
    result.update(seldepth=final["seldepth"], unfinished_nodes=result["reported_nodes"] - final["nodes"],
                  quiescence_nodes=None, internal_score=None,
                  score_representation="Raw normalized UCI cp or mate; internal integer score is not emitted")
    if result["reported_nodes"] <= 0:
        raise ValueError("Search did not report positive work")
    return result


def summarize(samples, positions):
    lookup = {}
    for sample in samples:
        key = (sample["position_index"], sample["role"])
        if key in lookup or sample["status"] != "complete":
            raise ValueError("Duplicate or incomplete comparison cell")
        if not math.isfinite(sample["elapsed_seconds"]) or sample["elapsed_seconds"] <= 0:
            raise ValueError("Invalid cell duration")
        lookup[key] = sample
    if set(lookup) != {(i, role) for i in range(len(positions)) for role in PROFILES}:
        raise ValueError("Incomplete three-profile matrix")
    pairs = []
    for i, position in enumerate(positions):
        for left_role, right_role in itertools.combinations(PROFILES, 2):
            a, b = [lookup[i, role] for role in (left_role, right_role)]
            left, right = a["result"], b["result"]
            changes = [dict(depth=x["depth"], left_score=x["score"], right_score=y["score"],
                            left_pv=x["pv"], right_pv=y["pv"])
                       for x, y in zip(left["iterations"], right["iterations"])
                       if x["score"] != y["score"] or x["pv"] != y["pv"]]
            pair = dict(position_index=i, position_id=position["id"], roles=[left_role, right_role],
                        elapsed_seconds=[a["elapsed_seconds"], b["elapsed_seconds"]],
                        common_depth_score_or_pv_changes=changes,
                        completed_depth_delta=right["completed_depth"] - left["completed_depth"],
                        same_bestmove=left["bestmove"] == right["bestmove"], same_score=left["score"] == right["score"])
            for label, field in (("completed_depths", "completed_depth"), ("seldepths", "seldepth"),
                                 ("nodes", "reported_nodes"), ("nps", "reported_nps"),
                                 ("reported_time_ms", "reported_time_ms"), ("unfinished_nodes", "unfinished_nodes"),
                                 ("scores", "score"), ("bestmoves", "bestmove"), ("ponders", "ponder")):
                pair[label] = [left[field], right[field]]
            pairs.append(pair)
    profiles = {}
    for role in PROFILES:
        rows = [lookup[i, role] for i in range(len(positions))]
        depths = [s["result"]["completed_depth"] for s in rows]
        profiles[role] = dict(searches=len(rows), total_nodes=sum(s["result"]["reported_nodes"] for s in rows),
                              elapsed_seconds=sum(s["elapsed_seconds"] for s in rows),
                              completed_depths=depths, minimum_completed_depth=min(depths),
                              median_completed_depth=statistics.median(depths), maximum_completed_depth=max(depths),
                              positive_mate_reports=sum(s["result"]["score"]["type"] == "mate" and
                                                        s["result"]["score"]["value"] > 0 for s in rows))
    return dict(pairs=pairs, profiles=profiles,
                interpretation="One exposed observation per cell; nominal depths, different-tree nodes and scores do not establish speed, tactical correctness or Elo")


def cleanup(engine, session, event):
    started = time.monotonic()
    session["forced_kill"] = False
    try:
        if engine.process.poll() is None:
            session["commands"].append("quit")
            event("send", "quit")
            try:
                engine.send("quit")
                engine.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                session["forced_kill"] = True
                engine.process.kill()
                engine.process.wait(timeout=1)
        engine.reader.join(timeout=1)
        engine.process.stdin.close()
        if not engine.reader.is_alive():
            engine.process.stdout.close()
        finish_session(engine, session)
    finally:
        session.update(cleanup_seconds=time.monotonic() - started, exit_code=engine.process.poll(),
                       process_exited=engine.process.poll() is not None)
        for line in session.get("shutdown_output", []):
            event("receive", line)


def profile(engine_path, network, output, *, quiet_host=False, host_check=None):
    engine_path, network, output = [Path(p).resolve() for p in (engine_path, network, output)]
    started = time.monotonic()
    report = dict(schema_version=1, phase="4F.19", status="preparing", started_utc=utc_now(),
                  quiet_host_declared=quiet_host, platform=platform.platform(), referee_version=chess.__version__,
                  assets={}, sessions=[], samples=[], host_observations=[], failures=[])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary evidence already exists; preserve it")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    paths = {}

    def elapsed():
        return time.monotonic() - started

    def remaining(maximum):
        value = TOTAL_SECONDS - elapsed()
        if value <= 0:
            raise TimeoutError("The frozen 300-second setup/search deadline expired")
        return min(maximum, value)

    def check_host():
        record = (host_check or host_observation)()
        record["elapsed_seconds"] = elapsed()
        report["host_observations"].append(record)
        publish(output, report)
        if not record.get("passed") or not record.get("ac_power") or not record.get("automatic"):
            raise ValueError("Host conditions changed or could not be verified: " + record.get("error", "invalid observation"))
        return record

    try:
        if not quiet_host:
            raise ValueError("A fresh quiet-host declaration is required")
        if chess.__version__ != "1.11.2":
            raise ValueError("Expected the pinned chess 1.11.2 referee")
        positions = load_positions()
        paths = dict(source_paths(), engine=engine_path, network=network, corpus=CORPUS, protocol=PROTOCOL,
                     interpreter=Path(sys.executable).resolve(), referee_module=Path(chess.__file__).resolve())
        if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
            raise ValueError("Input paths must fit on one line")
        report["assets"] = {name: dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size)
                            for name, path in paths.items()}
        if report["assets"]["engine"]["sha256"] != ENGINE_SHA256 or report["assets"]["network"]["sha256"] != NETWORK_SHA256:
            raise ValueError("Engine/network do not match the predeclared pins")
        report.update(status="running", positions=positions, protocol_text=PROTOCOL.read_text(),
                      interpreter=interpreter_identity(), initial_resource_policy=resource_check(network),
                      settings=dict(profiles=list(PROFILES), options={r: options_for(r, network) for r in PROFILES},
                                    movetime_ms=MOVETIME_MS, depth_cap=None, expected_searches=45, expected_sessions=45,
                                    repetitions=1, setup_search_budget_seconds=TOTAL_SECONDS, search_timeout_seconds=SEARCH_TIMEOUT,
                                    cleanup_bounds_seconds={"quit": 5, "forced_reap": 1, "reader_join": 1},
                                    event_timing="Observed command sends and receive batches, not kernel line-arrival timestamps",
                                    missing_fields="Quiescence-only nodes and internal integer scores are unavailable"))
        publish(output, report)
        for index, position in enumerate(positions):
            for role in run_order(index):
                remaining(1)
                before = check_host()
                session = dict(session_index=len(report["sessions"]), position_index=index, position_id=position["id"],
                               role=role, started_utc=utc_now(), started_elapsed_seconds=elapsed(),
                               commands=[], events=[], host_before=before, resource_policy=resource_check(network))
                report["sessions"].append(session)
                engine = None

                def event(direction, line):
                    session["events"].append(dict(direction=direction, line=line, utc=utc_now(), elapsed_seconds=elapsed()))

                try:
                    engine = Engine(engine_path)
                    session.update(pid=engine.process.pid, output=engine.transcript)

                    def send(command):
                        session["commands"].append(command)
                        event("send", command)
                        engine.send(command)

                    def receive(prefix, maximum):
                        begin = len(engine.transcript)
                        try:
                            return engine.until(prefix, timeout=remaining(maximum))
                        finally:
                            for line in engine.transcript[begin:]:
                                event("receive", line)

                    send("uci")
                    validate_identity(receive("uciok", 20), network)
                    for name, value in options_for(role, network).items():
                        send("setoption name " + name + " value " + value)
                    send("isready")
                    if receive("readyok", 30) != ["info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                        raise ValueError("Unexpected initial readiness output")
                    send("ucinewgame")
                    send("position " + position["position"])
                    send("isready")
                    if receive("readyok", 10) != ["readyok"]:
                        raise ValueError("Unexpected pre-search readiness output")
                    remaining(1)
                    begin = len(engine.transcript)
                    sample = dict(session_index=session["session_index"], position_index=index, position_id=position["id"],
                                  role=role, pid=engine.process.pid, status="incomplete", go=f"go movetime {MOVETIME_MS}")
                    report["samples"].append(sample)
                    publish(output, report)
                    search_started = time.monotonic()
                    sample.update(started_utc=utc_now(), started_elapsed_seconds=elapsed())
                    try:
                        send(sample["go"])
                        receive("bestmove", SEARCH_TIMEOUT)
                        remaining(1)
                    finally:
                        sample.update(elapsed_seconds=time.monotonic() - search_started, finished_utc=utc_now(),
                                      finished_elapsed_seconds=elapsed(), output=engine.transcript[begin:])
                        publish(output, report)
                    sample.update(result=validate_result(sample["output"], board_for(position["position"])), status="complete")
                    send("isready")
                    if receive("readyok", 10) != ["readyok"]:
                        raise ValueError("Unexpected final readiness output")
                finally:
                    failing = sys.exc_info()[0] is not None
                    if engine is not None:
                        try:
                            cleanup(engine, session, event)
                        except BaseException as error:
                            session["cleanup_error"] = f"{type(error).__name__}: {error}"
                            report["failures"].append(dict(kind="cleanup", session_index=session["session_index"], error=session["cleanup_error"]))
                            if not failing:
                                raise
                        finally:
                            session.update(finished_utc=utc_now(), finished_elapsed_seconds=elapsed())
                            publish(output, report)
                session["host_after"] = check_host()
                remaining(1)
                publish(output, report)
        report["summary"] = summarize(report["samples"], positions)
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        report["failures"].append(dict(kind="profile", error=report["error"]))
        raise
    finally:
        report["after_sha256"] = {}
        for name, path in paths.items():
            try:
                report["after_sha256"][name] = digest(path)
            except OSError as error:
                report["after_sha256"][name] = None
                report["failures"].append(dict(kind="asset", asset=name, error=str(error)))
        report["artifact_drift"] = [name for name, asset in report["assets"].items()
                                    if report["after_sha256"].get(name) != asset["sha256"]]
        if report["artifact_drift"]:
            report["status"] = "invalid_or_interrupted"
            report["failures"].append(dict(kind="asset_drift", assets=report["artifact_drift"]))
        report.update(finished_utc=utc_now(), elapsed_seconds=elapsed())
        publish(output, report)
    if report["artifact_drift"]:
        raise ValueError("Frozen artifacts changed; evidence is invalid")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=NETWORK)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet-host", action="store_true")
    args = parser.parse_args()

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt("Termination requested; preserve partial evidence and clean up")

    signal.signal(signal.SIGTERM, interrupt)
    result = profile(args.engine, args.network, args.output, quiet_host=args.quiet_host)
    print(json.dumps(dict(status=result["status"], searches=len(result["samples"]), sessions=len(result["sessions"]), output=str(args.output))))


if __name__ == "__main__":
    main()
