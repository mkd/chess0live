#!/usr/bin/env python3
"""Fixed Phase 4D.3 search-work screen; deliberately makes no timing/Elo claim.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import queue
import sys
import time

from bench import POSITIONS, digest
from compare_bench import physical_memory
from profile_smp import board_for, validate_result as validate_uci_result
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4d3-null-move.md"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
PARENT_SHA256 = "bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f"
POSITIONS_SHA256 = "7db7d651ff73d29ee9fd63e3a9cb27c8a5b16fd1894763df167ecef23fa8a38b"
SOURCES = ("tools/profile_null_move.py", "tools/bench.py", "tools/compare_bench.py",
           "tools/profile_smp.py", "tools/profile_search.py", "tools/resources.py",
           "tools/uci_client.py", "requirements-match.txt", "networks/manifest.json")
STAGES = {"parent_equivalence": ("parent", "off"), "null_work": ("off", "on")}
TEMPERATURES = ("cold", "warm")
DEPTH = 6
CAMPAIGN_WORKERS = 8
CAMPAIGN_BYTES = 9525941184


def resource_check(network):
    """Reserve the concurrent frozen campaign plus one serial profile engine.

    This intentionally over-reserves after campaign completion. The caller must
    keep other development workloads idle; this is not process discovery or an
    operating-system CPU/memory cap.
    """
    policy = dict(current_budget())
    estimate = CAMPAIGN_BYTES + 256 * 1024**2 + 4 * network.stat().st_size
    memory = physical_memory()
    policy.update(active_search_workers=CAMPAIGN_WORKERS + 1, resident_engines=17,
                  estimated_memory_bytes=estimate, physical_memory_bytes=memory,
                  includes_frozen_campaign=True, memory_estimate_is_hard_cap=False)
    if policy["max_cpu_workers"] < CAMPAIGN_WORKERS + 1:
        raise ValueError("Aggregate campaign/profile workers exceed the current budget")
    if memory is None or estimate > memory * policy["memory_fraction"]:
        raise ValueError("Aggregate memory reservation cannot be admitted")
    return policy


def publish(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def finish_session(engine, session):
    """Preserve and validate output produced after the final readiness fence.

    Engine.close() joins the reader but intentionally does not consume its
    queue. Drain it here without changing that frozen shared dependency. A
    successful profile requires a clean exit and exactly one final EOF marker;
    late diagnostics cannot disappear merely because bestmove was already read.
    """
    trailing = []
    eof_count = 0
    after_eof = False
    while True:
        try:
            line = engine.lines.get_nowait()
        except queue.Empty:
            break
        if line is None:
            eof_count += 1
        else:
            after_eof |= eof_count > 0
            trailing.append(line)
            engine.transcript.append(line)
    session["shutdown_output"] = trailing
    session["shutdown_eof_count"] = eof_count
    session["exit_code"] = engine.process.returncode
    problems = []
    if engine.reader.is_alive():
        problems.append("stdout reader remained active after engine cleanup")
    if engine.process.returncode != 0:
        problems.append("engine exited unsuccessfully")
    if eof_count != 1 or after_eof:
        problems.append("missing, duplicate or misordered shutdown EOF")
    if any(line.strip() for line in trailing):
        problems.append("unexpected output during engine shutdown")
    if problems:
        session["shutdown_error"] = "; ".join(problems)
        raise ValueError(session["shutdown_error"])


def validate_result(lines, board):
    """Require exact completed iterations and replay every real PV/ponder move."""
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"] or "lowerbound" in tokens or "upperbound" in tokens:
            raise ValueError("Diagnostics and score bounds are forbidden in this screen")
        if tokens[:1] == ["info"]:
            if tokens.count("tbhits") != 1:
                raise ValueError("Every info record must report tablebase hits")
            at = tokens.index("tbhits")
            if at + 1 == len(tokens) or tokens[at + 1] != "0":
                raise ValueError("A tablebase probe would mix experimental factors")
    result = validate_uci_result(lines, board, "depth", DEPTH)
    if result["reported_nodes"] != result["iterations"][-1]["nodes"]:
        raise ValueError("A completed one-worker fixed-depth search must not leave unfinished nodes")
    # Timing and NPS are retained in the raw evidence, never compared. Hash
    # occupancy is deterministic here and therefore part of parent equivalence.
    result["signature"] = {
        "iterations": [{key: row[key] for key in ("depth", "seldepth", "nodes", "score", "pv", "hashfull")}
                       for row in result["iterations"]],
        "bestmove": result["bestmove"], "ponder": result["ponder"],
        "nodes": result["reported_nodes"], "hashfull": result["hashfull"]}
    return result


def summarize(samples, stage):
    roles = STAGES[stage]
    lookup = {}
    for sample in samples:
        if sample["stage"] != stage:
            continue
        key = (sample["position_index"], sample["temperature"], sample["role"])
        if sample["status"] != "complete" or key in lookup:
            raise ValueError("Incomplete or duplicate comparison cell")
        lookup[key] = sample["result"]
    expected = {(index, temperature, role) for index in range(3)
                for temperature in TEMPERATURES for role in roles}
    if set(lookup) != expected:
        raise ValueError("Comparison must contain every predeclared cell")
    pairs = []
    for index in range(3):
        for temperature in TEMPERATURES:
            left, right = [lookup[index, temperature, role] for role in roles]
            same = left["signature"] == right["signature"]
            if stage == "parent_equivalence" and not same:
                raise ValueError(f"Default-off search differs from the parent at root {index}, {temperature}")
            changes = [{"depth": a["depth"], "left_score": a["score"], "right_score": b["score"],
                        "left_pv": a["pv"], "right_pv": b["pv"]}
                       for a, b in zip(left["iterations"], right["iterations"])
                       if a["score"] != b["score"] or a["pv"] != b["pv"]]
            pairs.append({"position_index": index, "temperature": temperature,
                          "roles": roles, "same_signature": same,
                          "nodes": [left["reported_nodes"], right["reported_nodes"]],
                          "node_ratio_right_over_left": right["reported_nodes"] / left["reported_nodes"],
                          "bestmoves": [left["bestmove"], right["bestmove"]],
                          "ponders": [left["ponder"], right["ponder"]],
                          "scores": [left["score"], right["score"]],
                          "iteration_score_or_pv_changes": changes})
    totals = {temperature: {role: sum(lookup[index, temperature, role]["reported_nodes"]
                                    for index in range(3)) for role in roles}
              for temperature in TEMPERATURES}
    return {"pairs": pairs, "total_nodes_by_temperature": totals,
            "interpretation": "Search-work/decision observations only; no timing, strength or safety conclusion."}


def profile(parent, candidate, network, output):
    corpus_sha256 = hashlib.sha256(("\n".join(POSITIONS) + "\n").encode()).hexdigest()
    if len(POSITIONS) != 3 or corpus_sha256 != POSITIONS_SHA256:
        raise ValueError("The declared benchmark corpus must still contain exactly three roots")
    boards = [board_for(position) for position in POSITIONS]
    paths = {"parent": parent.resolve(), "candidate": candidate.resolve(),
             "network": network.resolve(), "protocol": PROTOCOL}
    paths.update({name: ROOT / name for name in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    if assets["parent"]["sha256"] != PARENT_SHA256 or assets["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("The parent and network must match the predeclared pins")
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": assets, "protocol": PROTOCOL.read_text(encoding="utf-8"),
              "positions": POSITIONS, "positions_sha256": corpus_sha256,
              "platform": platform.platform(), "referee_version": "1.11.2",
              "settings": {"depth": DEPTH, "hash_mb": 64, "threads": 1, "repetitions": 1,
                           "searches": 24, "per_search_timeout_seconds": 60, "total_timeout_seconds": 600},
              "initial_resource_policy": resource_check(network), "sessions": [], "samples": [],
              "summaries": {}, "interpretation": "Concurrent frozen LMR campaign prevents timing interpretation. Nodes and depth do not establish strength."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary output exists; preserve it and choose a new path")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    deadline = time.monotonic() + 600

    def remaining(maximum):
        left = min(maximum, deadline - time.monotonic())
        if left <= 0:
            raise TimeoutError("The declared total profile deadline expired")
        return left

    try:
        for stage, roles in STAGES.items():
            for index, position in enumerate(POSITIONS):
                for role in roles if index % 2 == 0 else roles[::-1]:
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
                            options = {"Hash": "64", "Threads": "1", "EvalFile": str(paths["network"]),
                                       "Ponder": "false", "Move Overhead": "20", "Time Policy": "classic",
                                       "Late Move Reductions": "false", "Capture Ordering": "mvv-lva",
                                       "Countermove Ordering": "false", "SyzygyPath": "<empty>",
                                       "SyzygyProbeLimit": "0", "Search Diagnostics": "false"}
                            if role != "parent":
                                options["Null Move Pruning"] = "true" if role == "on" else "false"
                            if any("error:" in line.lower() for line in identity):
                                raise ValueError("Engine rejected its handshake")
                            for name, value in options.items():
                                if not any(line.startswith(f"option name {name} type ") for line in identity):
                                    raise ValueError("Missing UCI option: " + name)
                                send(f"setoption name {name} value {value}")
                            send("isready")
                            setup = engine.until("readyok", timeout=remaining(120))
                            if setup != ["info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                                raise ValueError("Unexpected engine setup output: " + " | ".join(setup))
                            for temperature in TEMPERATURES:
                                sample = {"stage": stage, "position_index": index, "role": role,
                                          "temperature": temperature, "status": "preparing",
                                          "resource_policy": resource_check(network)}
                                report["samples"].append(sample)
                                if temperature == "cold":
                                    send("ucinewgame")
                                send("position " + position)
                                send("isready")
                                if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                    raise ValueError("Unexpected output at a search readiness barrier")
                                begin = len(engine.transcript)
                                sample["status"] = "incomplete"
                                try:
                                    send(f"go depth {DEPTH}")
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(60))
                                finally:
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], boards[index])
                                sample["status"] = "complete"
                                publish(output, report)
                            send("isready")
                            if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                raise ValueError("Unexpected trailing protocol output")
                    finally:
                        # Retain shutdown evidence on failure as well. If the
                        # search already failed, keep that original exception;
                        # the separate cleanup defect remains in the session.
                        failing = sys.exc_info()[0] is not None
                        try:
                            finish_session(engine, session)
                        except ValueError:
                            if not failing:
                                raise
            report["summaries"][stage] = summarize(report["samples"], stage)
            publish(output, report)
        report.update(status="complete")
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["after_sha256"] = {name: digest(path) if path.is_file() else None for name, path in paths.items()}
        changed = [name for name, asset in assets.items() if report["after_sha256"][name] != asset["sha256"]]
        if changed:
            report.update(status="invalid_or_interrupted", artifact_drift=changed)
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
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output)
    print(json.dumps({"status": report["status"], "summaries": report["summaries"]}, indent=2))


if __name__ == "__main__":
    main()
