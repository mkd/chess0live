#!/usr/bin/env python3
"""Fixed Phase 4D.4 development screen; search speed is not playing strength.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Historical profiler helpers are imported without modifying their old protocols
or reproduction paths. This orchestration owns only the new, finite 60-search
screen: parent/off equivalence, cold/warm work, then fresh equal-time searches.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

from bench import digest
from compare_bench import physical_memory
from profile_countermove import board_for, validate_result as validate_timed_result
from profile_null_move import finish_session, publish, validate_result as validate_depth_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4d4-reverse-futility.md"
CORPUS = ROOT / "tests/data/countermove-profile.json"
CORPUS_SHA256 = "afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f"
POSITIONS_SHA256 = "5296ab5c59ae94c87a68e284598fd656afc9881b87f81665351297d684fed307"
POSITION_IDS = ("opening-01", "opening-02", "opening-03", "gamephases-mg-01",
                "gamephases-mg-03", "gamephases-eg-06")
PARENT_SHA256 = "d0617575e7ece0dc3c38d4f44f33b6bc93adad8cf947a129af6dec137246b530"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
SOURCES = ("tools/profile_reverse_futility.py", "tests/profile_reverse_futility_test.py",
           "tools/profile_null_move.py", "tools/profile_countermove.py", "tools/bench.py",
           "tools/compare_bench.py", "tools/profile_smp.py", "tools/profile_search.py",
           "tools/resources.py", "tools/uci_client.py", "requirements-match.txt",
           "networks/manifest.json")
DEPTH = 6
MOVETIME_MS = 500
TOTAL_TIMEOUT_SECONDS = 900
STAGES = {
    "parent_equivalence": {"roles": ("parent", "off"), "mode": "depth",
                           "temperatures": ("cold", "warm")},
    "reverse_work": {"roles": ("off", "on"), "mode": "depth",
                     "temperatures": ("cold", "warm")},
    "equal_time": {"roles": ("off", "on"), "mode": "movetime",
                   "temperatures": ("cold",)},
}


def load_positions():
    """Select six already exposed roots without reading any held-out corpus."""
    if digest(CORPUS) != CORPUS_SHA256:
        raise ValueError("The exposed source corpus changed")
    entries = json.loads(CORPUS.read_text(encoding="utf-8"))["positions"]
    positions = []
    for identifier in POSITION_IDS:
        matches = [entry for entry in entries if entry.get("id") == identifier]
        if len(matches) != 1:
            raise ValueError("Missing or duplicate predeclared root: " + identifier)
        positions.append(matches[0])
    text = json.dumps(positions, sort_keys=True, separators=(",", ":")) + "\n"
    if hashlib.sha256(text.encode()).hexdigest() != POSITIONS_SHA256:
        raise ValueError("The selected roots changed")
    for entry in positions:
        board_for(entry["position"])
    return positions


def resource_check(network):
    """Admit one serial engine; the operator must keep other workloads idle.

    This is a conservative allocation estimate and an explicit quiet-host
    declaration, not process discovery or an operating-system utilization cap.
    """
    policy = dict(current_budget())
    estimate = 256 * 1024**2 + 4 * network.stat().st_size
    memory = physical_memory()
    policy.update(active_search_workers=1, resident_engines=1,
                  estimated_memory_bytes=estimate, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if policy["max_cpu_workers"] < 1:
        raise ValueError("One search worker exceeds the current budget")
    if memory is None or estimate > memory * policy["memory_fraction"]:
        raise ValueError("The engine memory reservation cannot be admitted")
    return policy


def role_order(stage, index):
    roles = STAGES[stage]["roles"]
    # Equal-time role order reverses the depth-stage order at every root.
    return roles if (index + (stage == "equal_time")) % 2 == 0 else roles[::-1]


def options_for(role, network):
    options = {"Hash": "64", "Threads": "1", "EvalFile": str(network),
               "Ponder": "false", "Move Overhead": "20", "Time Policy": "classic",
               "Late Move Reductions": "false", "Capture Ordering": "mvv-lva",
               "Countermove Ordering": "false", "Null Move Pruning": "false",
               "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0",
               "Search Diagnostics": "false"}
    if role != "parent":
        options["Reverse Futility Pruning"] = "true" if role == "on" else "false"
    return options


def validate_result(lines, board, mode):
    """Reuse strict legal-PV, exact-score, final-counter and tbhits checks."""
    if mode == "depth":
        result = validate_depth_result(lines, board)
        result["unfinished_nodes"] = 0
        result["seldepth"] = result["iterations"][-1]["seldepth"]
        return result
    if mode != "movetime":
        raise ValueError("Unexpected profile search mode")
    return validate_timed_result(lines, board, mode, DEPTH)


def summarize(samples, stage):
    """Require the complete fixed matrix and retain every sampled decision change."""
    config = STAGES[stage]
    roles, temperatures = config["roles"], config["temperatures"]
    lookup = {}
    for sample in samples:
        if sample["stage"] != stage:
            continue
        key = (sample["position_index"], sample["temperature"], sample["role"])
        if sample["status"] != "complete" or key in lookup:
            raise ValueError("Incomplete or duplicate comparison cell")
        if (sample["mode"] != config["mode"] or not math.isfinite(sample["elapsed_seconds"])
                or sample["elapsed_seconds"] <= 0 or sample["result"]["reported_nodes"] <= 0):
            raise ValueError("Invalid search mode, elapsed time or node count")
        lookup[key] = sample
    expected = {(index, temperature, role) for index in range(len(POSITION_IDS))
                for temperature in temperatures for role in roles}
    if set(lookup) != expected:
        raise ValueError("Comparison must contain every predeclared cell")
    pairs = []
    for index in range(len(POSITION_IDS)):
        for temperature in temperatures:
            left_sample, right_sample = [lookup[index, temperature, role] for role in roles]
            left, right = left_sample["result"], right_sample["result"]
            same = (left.get("signature") == right.get("signature")) if config["mode"] == "depth" else None
            if stage == "parent_equivalence" and not same:
                raise ValueError(f"Default-off search differs from the parent at root {index}, {temperature}")
            changes = [{"depth": a["depth"], "left_score": a["score"], "right_score": b["score"],
                        "left_pv": a["pv"], "right_pv": b["pv"]}
                       for a, b in zip(left["iterations"], right["iterations"])
                       if a["score"] != b["score"] or a["pv"] != b["pv"]]
            pairs.append({"position_index": index, "position_id": POSITION_IDS[index],
                          "temperature": temperature, "roles": roles, "same_signature": same,
                          "nodes": [left["reported_nodes"], right["reported_nodes"]],
                          "node_ratio_right_over_left": right["reported_nodes"] / left["reported_nodes"],
                          "elapsed_seconds": [left_sample["elapsed_seconds"], right_sample["elapsed_seconds"]],
                          "completed_depths": [left["completed_depth"], right["completed_depth"]],
                          "seldepths": [left["seldepth"], right["seldepth"]],
                          "unfinished_nodes": [left["unfinished_nodes"], right["unfinished_nodes"]],
                          "bestmoves": [left["bestmove"], right["bestmove"]],
                          "ponders": [left["ponder"], right["ponder"]],
                          "scores": [left["score"], right["score"]],
                          "common_depth_score_or_pv_changes": changes})
    totals = {temperature: {role: {
        "nodes": sum(lookup[index, temperature, role]["result"]["reported_nodes"]
                     for index in range(len(POSITION_IDS))),
        "elapsed_seconds": sum(lookup[index, temperature, role]["elapsed_seconds"]
                               for index in range(len(POSITION_IDS))),
        "unfinished_nodes": sum(lookup[index, temperature, role]["result"]["unfinished_nodes"]
                                for index in range(len(POSITION_IDS)))} for role in roles}
              for temperature in temperatures}
    return {"pairs": pairs, "totals_by_temperature": totals,
            "interpretation": "One exposed repetition; descriptive work/time/decision observations only. No speed qualification, Elo or safety conclusion."}


def profile(parent, candidate, network, output, *, quiet_host=False):
    if not quiet_host:
        raise ValueError("Use --quiet-host only after other development workloads are idle")
    positions = load_positions()
    boards = [board_for(entry["position"]) for entry in positions]
    paths = {"parent": parent.resolve(), "candidate": candidate.resolve(),
             "network": network.resolve(), "protocol": PROTOCOL, "corpus": CORPUS}
    paths.update({name: ROOT / name for name in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    if assets["parent"]["sha256"] != PARENT_SHA256 or assets["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("The parent and network must match the predeclared pins")
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": assets, "protocol": PROTOCOL.read_text(encoding="utf-8"),
              "positions": positions, "positions_sha256": POSITIONS_SHA256,
              "platform": platform.platform(), "referee_version": "1.11.2",
              "settings": {"depth": DEPTH, "movetime_ms": MOVETIME_MS, "hash_mb": 64,
                           "threads": 1, "repetitions": 1, "searches": 60,
                           "depth_search_timeout_seconds": 60, "timed_search_timeout_seconds": 10,
                           "total_timeout_seconds": TOTAL_TIMEOUT_SECONDS},
              "quiet_host_declaration": True, "quiet_host_is_os_measurement": False,
              "initial_resource_policy": resource_check(network), "sessions": [], "samples": [],
              "summaries": {}, "interpretation": "Small exposed development screen, not repeatable speed qualification or playing-strength evidence."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary output exists; preserve it and choose a new path")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    screen_started = time.monotonic()
    deadline = screen_started + TOTAL_TIMEOUT_SECONDS

    def remaining(maximum):
        left = min(maximum, deadline - time.monotonic())
        if left <= 0:
            raise TimeoutError("The declared total profile deadline expired")
        return left

    try:
        for stage, config in STAGES.items():
            for index, position in enumerate(positions):
                for role in role_order(stage, index):
                    resource_check(network)
                    session = {"stage": stage, "position_index": index, "role": role, "commands": []}
                    report["sessions"].append(session)
                    engine = Engine(paths["parent"] if role == "parent" else paths["candidate"])
                    session["output"] = engine.transcript
                    try:
                        with engine:
                            def send(command):
                                session["commands"].append(command)
                                engine.send(command)

                            send("uci")
                            identity = engine.until("uciok", timeout=remaining(30))
                            if any("error:" in line.lower() for line in identity):
                                raise ValueError("Engine rejected its handshake")
                            for name, value in options_for(role, paths["network"]).items():
                                if not any(line.startswith(f"option name {name} type ") for line in identity):
                                    raise ValueError("Missing UCI option: " + name)
                                send(f"setoption name {name} value {value}")
                            send("isready")
                            setup = engine.until("readyok", timeout=remaining(120))
                            if setup != ["info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                                raise ValueError("Unexpected engine setup output: " + " | ".join(setup))
                            for temperature in config["temperatures"]:
                                sample = {"stage": stage, "position_index": index, "role": role,
                                          "mode": config["mode"], "temperature": temperature,
                                          "status": "preparing", "resource_policy": resource_check(network)}
                                report["samples"].append(sample)
                                if temperature == "cold":
                                    send("ucinewgame")
                                send("position " + position["position"])
                                send("isready")
                                if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                    raise ValueError("Unexpected output at a search readiness barrier")
                                begin = len(engine.transcript)
                                sample.update(status="incomplete", started_utc=datetime.now(timezone.utc).isoformat())
                                started = time.monotonic()
                                try:
                                    send(f"go depth {DEPTH}" if config["mode"] == "depth" else f"go movetime {MOVETIME_MS}")
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(60 if config["mode"] == "depth" else 10))
                                finally:
                                    sample["elapsed_seconds"] = time.monotonic() - started
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], boards[index], config["mode"])
                                sample["status"] = "complete"
                                publish(output, report)
                            send("isready")
                            if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                raise ValueError("Unexpected trailing protocol output")
                    finally:
                        failing = sys.exc_info()[0] is not None
                        try:
                            finish_session(engine, session)
                        except ValueError:
                            if not failing:
                                raise
            report["summaries"][stage] = summarize(report["samples"], stage)
            publish(output, report)
        # The last readiness wait may finish before the deadline but cleanup
        # can cross it. Retain that work without accepting an over-budget run.
        report["search_and_cleanup_elapsed_seconds"] = time.monotonic() - screen_started
        if report["search_and_cleanup_elapsed_seconds"] > TOTAL_TIMEOUT_SECONDS:
            raise TimeoutError("The total profile deadline expired during final cleanup")
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report.setdefault("search_and_cleanup_elapsed_seconds", time.monotonic() - screen_started)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["after_sha256"] = {name: digest(path) if path.is_file() else None for name, path in paths.items()}
        changed = [name for name, asset in assets.items() if report["after_sha256"][name] != asset["sha256"]]
        if changed:
            report.update(status="invalid_or_interrupted", artifact_drift=changed)
        report["total_elapsed_seconds"] = time.monotonic() - screen_started
        publish(output, report)
    if report["status"] != "complete":
        raise ValueError("Profile artifacts changed during execution")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet-host", action="store_true",
                        help="Declare other builds, engine tests and campaigns idle for this screen")
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output, quiet_host=args.quiet_host)
    print(json.dumps({"status": report["status"], "summaries": report["summaries"]}, indent=2))


if __name__ == "__main__":
    main()
