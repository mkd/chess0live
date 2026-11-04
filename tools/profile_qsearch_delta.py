#!/usr/bin/env python3
"""Frozen Phase 4F.18 development screen; no strength or speed qualification.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

import chess
from bench import digest
from compare_bench import physical_memory, reject_errors
from profile_cache import board_for
from profile_null_move import finish_session, publish
import profile_search_baseline as baseline
from profile_smp import validate_result as replay_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4f18-delta.md"
CORPUS = baseline.CORPUS
CORPUS_SHA256 = "afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f"
NETWORK = baseline.NETWORK
NETWORK_SHA256 = baseline.NETWORK_SHA256
PARENT_COMMIT = "0bbe5f08d8976df567a7d62f9692b78ca6199b8a"
PARENT_SHA256 = "17f2951611713b8bd4b13dd0aeee892d972e6aaf829b832ad2737f46045f2800"
DEPTH, MOVETIME_MS = 6, 500
PROFILE_BUDGET_SECONDS = 300
STAGES = {
    "parent_equivalence": {"roles": ("parent", "off"), "mode": "depth", "temperatures": ("cold", "warm")},
    "delta_work": {"roles": ("off", "on"), "mode": "depth", "temperatures": ("cold", "warm")},
    "equal_time": {"roles": ("off", "on"), "mode": "movetime", "temperatures": ("cold",)},
}
EXTRA_SOURCES = ("tools/profile_qsearch_delta.py", "tests/profile_qsearch_delta_test.py",
                 "tools/profile_null_move.py", "tools/profile_smp.py")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_positions():
    if digest(CORPUS) != CORPUS_SHA256:
        raise ValueError("The frozen exposed corpus changed")
    return baseline.load_positions()


def source_paths():
    return dict(baseline.source_paths(), **{name: ROOT / name for name in EXTRA_SOURCES})


def options_for(role, network):
    if role not in ("parent", "off", "on"):
        raise ValueError("Unknown engine role")
    options = dict(baseline.options_for("default"), EvalFile=str(network))
    if role != "parent":
        options["QSearch Delta Pruning"] = "true" if role == "on" else "false"
    return options


def role_order(stage, index):
    roles = STAGES[stage]["roles"]
    return roles if (index + (stage == "equal_time")) % 2 == 0 else roles[::-1]


def resource_check(network):
    policy = dict(current_budget())
    estimate = (64 + 256) * 1024**2 + 4 * network.stat().st_size
    memory = physical_memory()
    policy.update(active_search_workers=1, resident_engines=1, estimated_memory_bytes=estimate,
                  physical_memory_bytes=memory, memory_estimate_is_hard_cap=False)
    if policy["max_cpu_workers"] < 1 or memory is None or estimate > memory * policy["memory_fraction"]:
        raise ValueError("One serial engine cannot be admitted under the current resource policy")
    return policy


def validate_result(lines, board, mode):
    if mode not in ("depth", "movetime"):
        raise ValueError("Unexpected search mode")
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"] or "lowerbound" in tokens or "upperbound" in tokens:
            raise ValueError("Diagnostics and score bounds are forbidden in this screen")
        if tokens[:1] == ["info"]:
            if tokens.count("tbhits") != 1:
                raise ValueError("Each info record must report tablebase hits")
            at = tokens.index("tbhits")
            if at + 1 == len(tokens) or tokens[at + 1] != "0":
                raise ValueError("A tablebase probe would mix experimental factors")
    result = replay_result(lines, board, mode, DEPTH)
    final = result["iterations"][-1]
    result["unfinished_nodes"] = result["reported_nodes"] - final["nodes"]
    if mode == "depth" and result["unfinished_nodes"] != 0:
        raise ValueError("Completed one-worker depth search has unfinished nodes")
    result["seldepth"] = final["seldepth"]
    result["quiescence_nodes"] = None
    result["internal_score"] = None
    result["score_representation"] = "Raw UCI normalized cp or mate; internal integer score is not emitted"
    result["signature"] = {
        "iterations": [{key: row[key] for key in ("depth", "seldepth", "nodes", "score", "pv")}
                       for row in result["iterations"]],
        "bestmove": result["bestmove"], "ponder": result["ponder"],
        "reported_nodes": result["reported_nodes"],
    }
    return result


def summarize(samples, stage, positions):
    config = STAGES[stage]
    roles, temperatures = config["roles"], config["temperatures"]
    lookup = {}
    for sample in samples:
        if sample["stage"] != stage:
            continue
        key = (sample["position_index"], sample["temperature"], sample["role"])
        if key in lookup or sample.get("status") != "complete":
            raise ValueError("Duplicate or incomplete comparison cell")
        if (sample["mode"] != config["mode"] or not math.isfinite(sample["elapsed_seconds"])
                or sample["elapsed_seconds"] <= 0 or sample["result"]["reported_nodes"] <= 0):
            raise ValueError("Invalid mode, elapsed time or node count")
        lookup[key] = sample
    expected = {(i, t, role) for i in range(len(positions)) for t in temperatures for role in roles}
    if set(lookup) != expected:
        raise ValueError("Comparison must contain every predeclared cell")
    pairs = []
    for i, position in enumerate(positions):
        for temperature in temperatures:
            a, b = [lookup[i, temperature, role] for role in roles]
            left, right = a["result"], b["result"]
            changes = [{"depth": x["depth"], "left_score": x["score"], "right_score": y["score"],
                        "left_pv": x["pv"], "right_pv": y["pv"]}
                       for x, y in zip(left["iterations"], right["iterations"])
                       if x["score"] != y["score"] or x["pv"] != y["pv"]]
            pair = dict(position_index=i, position_id=position["id"], temperature=temperature, roles=roles,
                        same_signature=left["signature"] == right["signature"],
                        common_depth_score_or_pv_changes=changes,
                        elapsed_seconds=[a["elapsed_seconds"], b["elapsed_seconds"]],
                        node_ratio_right_over_left=right["reported_nodes"] / left["reported_nodes"])
            for label, field in (("nodes", "reported_nodes"), ("completed_depths", "completed_depth"),
                                 ("seldepths", "seldepth"), ("unfinished_nodes", "unfinished_nodes"),
                                 ("bestmoves", "bestmove"), ("ponders", "ponder"), ("scores", "score"),
                                 ("quiescence_nodes", "quiescence_nodes"), ("internal_scores", "internal_score")):
                pair[label] = [left[field], right[field]]
            pairs.append(pair)
    totals = {t: {role: {
        "nodes": sum(lookup[i, t, role]["result"]["reported_nodes"] for i in range(len(positions))),
        "elapsed_seconds": sum(lookup[i, t, role]["elapsed_seconds"] for i in range(len(positions))),
        "unfinished_nodes": sum(lookup[i, t, role]["result"]["unfinished_nodes"] for i in range(len(positions))),
        "quiescence_nodes": None} for role in roles} for t in temperatures}
    return dict(pairs=pairs, totals_by_temperature=totals,
                exact_search_parity=all(pair["same_signature"] for pair in pairs),
                interpretation="One exposed repetition; descriptive work/time/decision observations only. "
                               "No heuristic safety, speed qualification or strength conclusion.")


def cleanup(engine, session):
    """Bound quit, forced reap and reader join; retain late output and failures."""
    started = time.monotonic()
    process = engine.process
    session["forced_kill"] = False
    try:
        if process.poll() is None:
            session["commands"].append("quit")
            session["events"].append({"direction": "send", "line": "quit"})
            try:
                engine.send("quit")
                process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                session["forced_kill"] = True
                process.kill()
                process.wait(timeout=1)
        engine.reader.join(timeout=1)
        process.stdin.close()
        if not engine.reader.is_alive():
            process.stdout.close()
        finish_session(engine, session)
    finally:
        session["cleanup_seconds"] = time.monotonic() - started
        session["exit_code"] = process.poll()
        session["process_exited"] = session["exit_code"] is not None
        for line in session.get("shutdown_output", []):
            session["events"].append({"direction": "receive", "line": line})


def profile(parent, candidate, network, output, *, quiet_host=False):
    parent, candidate, network, output = [Path(p).resolve() for p in (parent, candidate, network, output)]
    report = dict(schema_version=1, phase="4F.18", status="preparing", started_utc=utc_now(),
                  parent_commit=PARENT_COMMIT, platform=platform.platform(), referee_version=chess.__version__,
                  quiet_host_declared=quiet_host, assets={}, sessions=[], samples=[], summaries={}, failures=[])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary evidence already exists; preserve it")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    started = time.monotonic()
    paths = {}

    def remaining(maximum):
        value = started + PROFILE_BUDGET_SECONDS - time.monotonic()
        if value <= 0:
            raise TimeoutError("The frozen 300-second setup/search deadline expired")
        return min(value, maximum)

    try:
        if not quiet_host:
            raise ValueError("A fresh quiet-host declaration is required")
        if chess.__version__ != "1.11.2":
            raise ValueError("The independent referee must be chess 1.11.2")
        positions = load_positions()
        paths = dict(source_paths(), parent=parent, candidate=candidate, network=network,
                     protocol=PROTOCOL, corpus=CORPUS)
        if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
            raise ValueError("A newline in an input path would corrupt UCI commands")
        report["assets"] = {name: dict(path=str(path), sha256=digest(path), bytes=path.stat().st_size)
                            for name, path in paths.items()}
        if (report["assets"]["parent"]["sha256"] != PARENT_SHA256
                or report["assets"]["network"]["sha256"] != NETWORK_SHA256):
            raise ValueError("Parent/network do not match the predeclared pins")
        if parent == candidate:
            raise ValueError("Parent and candidate must be separate frozen binaries")
        report.update(status="running", positions=positions, protocol_text=PROTOCOL.read_text(),
                      initial_resource_policy=resource_check(network), settings=dict(
            depth=DEPTH, movetime_ms=MOVETIME_MS, repetitions=1, expected_searches=150,
            expected_sessions=90, search_timeouts_seconds={"depth": 15, "movetime": 10},
            setup_search_budget_seconds=PROFILE_BUDGET_SECONDS,
            cleanup_bounds_seconds={"quit": 5, "forced_reap": 1, "reader_join": 1},
            options={role: options_for(role, network) for role in ("parent", "off", "on")},
            missing_fields="Quiescence nodes and internal integer scores are not exposed by uninstrumented UCI; null means unavailable",
            exact_signature_excludes=["time", "nps", "hashfull"]))
        publish(output, report)
        for stage, config in STAGES.items():
            for index, position in enumerate(positions):
                board = board_for(position["position"])
                for role in role_order(stage, index):
                    remaining(1)
                    policy = resource_check(network)
                    session = dict(stage=stage, position_index=index, role=role, commands=[], events=[],
                                   resource_policy=policy, started_utc=utc_now())
                    report["sessions"].append(session)
                    engine = None
                    try:
                        engine = Engine(parent if role == "parent" else candidate)
                        session.update(pid=engine.process.pid, output=engine.transcript)

                        def send(command):
                            session["commands"].append(command)
                            session["events"].append({"direction": "send", "line": command})
                            engine.send(command)

                        def receive(prefix, maximum):
                            begin = len(engine.transcript)
                            try:
                                return engine.until(prefix, timeout=remaining(maximum))
                            finally:
                                session["events"].extend({"direction": "receive", "line": line}
                                                         for line in engine.transcript[begin:])

                        send("uci")
                        identity = receive("uciok", 20)
                        reject_errors(identity)
                        if not identity or identity[-1] != "uciok" or any(line.startswith("bestmove") for line in identity):
                            raise ValueError("Unexpected UCI handshake output")
                        option_types = dict(baseline.OPTION_TYPES, **{"QSearch Delta Pruning": "check"})
                        for name, value in options_for(role, network).items():
                            declarations = [line for line in identity if line.startswith("option name " + name + " type ")]
                            if (len(declarations) != 1 or declarations[0].split(" type ", 1)[1].split()[0]
                                    != option_types[name]):
                                raise ValueError("Missing/duplicate/wrong-type required UCI option: " + name)
                            if name == "QSearch Delta Pruning" and declarations != ["option name QSearch Delta Pruning type check default false"]:
                                raise ValueError("QSearch Delta Pruning must advertise default false")
                            send("setoption name " + name + " value " + value)
                        send("isready")
                        if receive("readyok", 30) != ["info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                            raise ValueError("Unexpected initial readiness output")
                        for temperature in config["temperatures"]:
                            sample = dict(stage=stage, position_index=index, position_id=position["id"],
                                          role=role, mode=config["mode"], temperature=temperature, status="preparing",
                                          session_index=len(report["sessions"]) - 1, pid=engine.process.pid,
                                          resource_policy=resource_check(network))
                            report["samples"].append(sample)
                            if temperature == "cold":
                                send("ucinewgame")
                            send("position " + position["position"])
                            send("isready")
                            if receive("readyok", 10) != ["readyok"]:
                                raise ValueError("Unexpected pre-search readiness output")
                            remaining(1)
                            begin, search_started = len(engine.transcript), time.monotonic()
                            sample.update(status="incomplete", started_utc=utc_now(),
                                          go=f"go depth {DEPTH}" if config["mode"] == "depth" else f"go movetime {MOVETIME_MS}")
                            try:
                                send(sample["go"])
                                receive("bestmove", 15 if config["mode"] == "depth" else 10)
                                remaining(1)
                            finally:
                                sample.update(elapsed_seconds=time.monotonic() - search_started,
                                              output=engine.transcript[begin:])
                                publish(output, report)
                            sample.update(result=validate_result(sample["output"], board, config["mode"]), status="complete")
                            publish(output, report)
                        send("isready")
                        if receive("readyok", 10) != ["readyok"]:
                            raise ValueError("Unexpected final readiness output")
                        remaining(1)
                    finally:
                        failing = sys.exc_info()[0] is not None
                        if engine is not None:
                            try:
                                cleanup(engine, session)
                            except BaseException as error:
                                session["cleanup_error"] = f"{type(error).__name__}: {error}"
                                report["failures"].append(dict(kind="cleanup", session_index=len(report["sessions"]) - 1,
                                                               error=session["cleanup_error"]))
                                if not failing:
                                    raise
                            finally:
                                publish(output, report)
                if stage == "parent_equivalence":
                    for temperature in config["temperatures"]:
                        pair = [s for s in report["samples"] if s["stage"] == stage and s["position_index"] == index
                                and s["temperature"] == temperature]
                        if pair[0]["result"]["signature"] != pair[1]["result"]["signature"]:
                            report["parent_mismatch"] = dict(position_id=position["id"], temperature=temperature)
                            raise ValueError("Default-off search differs from the parent: " + position["id"] + " " + temperature)
            report["summaries"][stage] = summarize(report["samples"], stage, positions)
            publish(output, report)
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
        report.update(finished_utc=utc_now(), elapsed_seconds=time.monotonic() - started)
        publish(output, report)
    if report["artifact_drift"]:
        raise ValueError("Frozen artifacts changed; evidence is invalid")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--network", type=Path, default=NETWORK)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet-host", action="store_true")
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output, quiet_host=args.quiet_host)
    print(json.dumps({"status": report["status"], "searches": len(report["samples"]),
                      "sessions": len(report["sessions"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()
