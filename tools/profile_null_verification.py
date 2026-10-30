#!/usr/bin/env python3
"""Fixed Phase 4F.15 null-verification work screen; no timing or Elo inference.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One serial engine, exposed roots, LMR on, separate cold/warm state. The older
tools supply pure evidence validators; their historical protocols are untouched.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import time

from bench import POSITIONS, digest
from compare_bench import physical_memory
from profile_cache import cache_record
from profile_lmr import validate_result as validate_lmr
from profile_null_move import (NETWORK_SHA256, POSITIONS_SHA256, finish_session,
                               publish, validate_result as validate_ordinary)
from profile_smp import board_for, unsigned
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4f15-null-verification.md"
PARENT_REVISION = "19ddf06c59bf2c3875414f33503f85bc959313ea"
PARENT_SHA256 = "c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d"
DEPTH = 6
STAGES = {"parent_equivalence": ("parent_off", "candidate_off"),
          "verification_work": ("parent_on", "candidate_on")}
TEMPERATURES = ("cold", "warm")
COUNTERS = ("probes", "fail_highs", "verifications", "cutoffs", "rejected")
WORK_COUNTERS = ("probe_nodes", "verification_nodes", "verification_hints")
SOURCES = ("tools/profile_null_verification.py", "tests/profile_null_verification_test.py",
           "tools/profile_null_move.py", "tools/profile_lmr.py", "tools/profile_cache.py",
           "tools/profile_smp.py", "tools/profile_search.py", "tools/bench.py",
           "tools/compare_bench.py", "tools/resources.py", "tools/uci_client.py",
           "requirements-match.txt", "networks/manifest.json", "src/search.cpp",
           "src/main.cpp", "include/chess0live/search.hpp", "include/chess0live/search_policy.hpp")


def options_for(role, network):
    if role not in sum(STAGES.values(), ()):
        raise ValueError("Unknown screen role")
    return {"Hash": "64", "Threads": "1", "EvalFile": str(network),
            "Ponder": "false", "Move Overhead": "20", "Time Policy": "classic",
            "Late Move Reductions": "true", "Capture Ordering": "mvv-lva",
            "Null Move Pruning": str(role.endswith("_on")).lower(),
            "Countermove Ordering": "false", "Continuation History": "false",
            "TT Move Hints": "false", "Reverse Futility Pruning": "false",
            "QSearch SEE Pruning": "false", "ProbCut": "false",
            "Deep Quiet Reductions": "false", "SyzygyPath": "<empty>",
            "SyzygyProbeLimit": "0", "Search Diagnostics": "true"}


def resource_check(network):
    policy = dict(current_budget())
    reservation = 256 * 1024**2 + 4 * network.stat().st_size
    memory = physical_memory()
    policy.update(active_search_workers=1, resident_engines=1,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False,
                  host_load="lm-studio-running",
                  note="Admission covers this serial diagnostic, not measured LM Studio or OS utilization.")
    if policy["max_cpu_workers"] < 1 or memory is None or reservation > memory * policy["memory_fraction"]:
        raise ValueError("The serial diagnostic cannot fit the current resource budget")
    return policy


def null_record(lines, role, total):
    records = [line for line in lines if line.startswith("info string nullmove ")]
    enabled = role.endswith("_on")
    if len(records) != int(enabled):
        raise ValueError("Expected one null record only for an enabled role")
    if not enabled:
        return {"enabled": False, **dict.fromkeys(COUNTERS, 0),
                **dict.fromkeys(WORK_COUNTERS, 0 if role.startswith("candidate_") else None)}
    tokens = records[0].split()
    names = (*COUNTERS, *WORK_COUNTERS) if role.startswith("candidate_") else COUNTERS
    if tokens[:4] != ["info", "string", "nullmove", "v1"] or len(tokens) != 6 + 2 * len(names):
        raise ValueError("Unsupported or malformed null diagnostic schema")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != {"enabled", *names} or fields["enabled"] != "true":
        raise ValueError("Missing, duplicate or wrong null diagnostic fields")
    fields = {"enabled": True, **{name: unsigned(fields[name], name) for name in names}}
    fields.update({name: None for name in WORK_COUNTERS if name not in fields})
    if (fields["fail_highs"] != fields["verifications"]
            or fields["verifications"] > fields["probes"]
            or fields["cutoffs"] + fields["rejected"] != fields["verifications"]
            or fields["probes"] > total):
        raise ValueError("Inconsistent completed null attempt/outcome counts")
    if role.startswith("candidate_"):
        if (fields["verification_hints"] > fields["verifications"]
                or fields["probe_nodes"] + fields["verification_nodes"] > total
                or fields["probe_nodes"] < fields["probes"]
                or fields["verification_nodes"] < fields["verifications"]):
            raise ValueError("Inconsistent null subtree work accounting")
    summary_index = next(i for i, line in enumerate(lines) if line.startswith("info string search-summary "))
    if lines.index(records[0]) > summary_index:
        raise ValueError("Null counters arrived after the search summary")
    return fields


def validate_result(lines, board, role):
    if role not in sum(STAGES.values(), ()):
        raise ValueError("Unknown screen role")
    allowed = {"nullmove", "cache", "search-iteration", "search-summary", "ordering", "lmr"}
    ordinary = []
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"]:
            if len(tokens) < 3 or tokens[2] not in allowed:
                raise ValueError("Unexpected diagnostic or nonisolated experiment: " + line)
        else:
            ordinary.append(line)
    diagnostic = validate_lmr(lines, True, board, DEPTH, None, ordering_required=True)
    result = validate_ordinary(ordinary, board)
    trace = diagnostic["trace"]
    summary = trace["summary"]
    if (summary["nodes"] != result["reported_nodes"] or trace["aborted_nodes"]
            or summary["soft_ms"] != 0 or summary["hard_ms"] != 0):
        raise ValueError("Fixed-depth totals, completion or clock budget disagree")
    result.update(trace=trace, lmr=diagnostic["lmr"], ordering=diagnostic["ordering"],
                  cache=cache_record(lines, 64),
                  nullmove=null_record(lines, role, result["reported_nodes"]))
    # Diagnostic timings stay only in raw evidence, outside deterministic parity.
    result["signature"].update(lmr=result["lmr"], ordering=result["ordering"], cache=result["cache"])
    return result


def summarize(samples, stage):
    if stage not in STAGES:
        raise ValueError("Unknown screen stage")
    if any(sample.get("stage") not in STAGES for sample in samples):
        raise ValueError("Unexpected comparison stage")
    roles = STAGES[stage]
    selected = [sample for sample in samples if sample["stage"] == stage]
    lookup = {}
    for sample in selected:
        key = (sample["position_index"], sample["temperature"], sample["role"])
        if key in lookup or sample["status"] != "complete":
            raise ValueError("Incomplete or duplicate comparison cell")
        lookup[key] = sample["result"]
    expected = {(index, temperature, role) for index in range(3)
                for temperature in TEMPERATURES for role in roles}
    if set(lookup) != expected:
        raise ValueError("Comparison must contain every predeclared cell")
    pairs, mismatches = [], []
    for index in range(3):
        for temperature in TEMPERATURES:
            left, right = [lookup[index, temperature, role] for role in roles]
            same = left["signature"] == right["signature"]
            if not same:
                mismatches.append({"position_index": index, "temperature": temperature})
            pairs.append({"position_index": index, "temperature": temperature, "roles": roles,
                          "same_signature": same,
                          "nodes": [left["reported_nodes"], right["reported_nodes"]],
                          "node_ratio_right_over_left": right["reported_nodes"] / left["reported_nodes"],
                          "bestmoves": [left["bestmove"], right["bestmove"]],
                          "ponders": [left["ponder"], right["ponder"]],
                          "scores": [left["score"], right["score"]],
                          "nullmove": [left["nullmove"], right["nullmove"]],
                          "iteration_differences": [
                              {"depth": a["depth"], "left": a, "right": b}
                              for a, b in zip(left["signature"]["iterations"], right["signature"]["iterations"])
                              if a != b]})
    totals = {temperature: {role: sum(lookup[index, temperature, role]["reported_nodes"]
                                    for index in range(3)) for role in roles}
              for temperature in TEMPERATURES}
    counters = {temperature: {role: {
        name: (None if role.startswith("parent_") and name in WORK_COUNTERS else
               sum(lookup[index, temperature, role]["nullmove"][name] for index in range(3)))
        for name in (*COUNTERS, *WORK_COUNTERS)} for role in roles} for temperature in TEMPERATURES}
    return {"pairs": pairs, "total_nodes_by_temperature": totals,
            "null_counters_by_temperature": counters,
            "equivalence_mismatches": mismatches if stage == "parent_equivalence" else [],
            "interpretation": "Finite search-work/decision observations only; no timing, strength or general safety conclusion."}


def profile(parent, candidate, network, output, *, parent_sha256, candidate_sha256, host_load):
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    deadline = started + 600
    if host_load != "lm-studio-running":
        raise ValueError("This screen records the owner-authorized loaded host")
    if any(not re.fullmatch(r"[0-9a-f]{64}", pin) for pin in (parent_sha256, candidate_sha256)):
        raise ValueError("Explicit lowercase parent and candidate SHA-256 pins are required")
    if parent_sha256 != PARENT_SHA256:
        raise ValueError("The parent pin differs from the declared Phase 4F.15 baseline")
    corpus_sha256 = hashlib.sha256(("\n".join(POSITIONS) + "\n").encode()).hexdigest()
    if len(POSITIONS) != 3 or corpus_sha256 != POSITIONS_SHA256:
        raise ValueError("The three exposed benchmark roots have changed")
    boards = [board_for(position) for position in POSITIONS]
    paths = {"parent": parent.resolve(), "candidate": candidate.resolve(),
             "network": network.resolve(), "protocol": PROTOCOL}
    paths.update({name: ROOT / name for name in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    for name, pin in (("parent", parent_sha256), ("candidate", candidate_sha256), ("network", NETWORK_SHA256)):
        if assets[name]["sha256"] != pin:
            raise ValueError(name + " does not match its declared pin")
    report = {"schema_version": 1, "status": "running", "assets": assets,
              "started_utc": started_utc,
              "parent_revision": PARENT_REVISION, "host_load": host_load,
              "protocol": PROTOCOL.read_text(encoding="utf-8"), "positions": POSITIONS,
              "positions_sha256": corpus_sha256, "platform": platform.platform(),
              "referee_version": "1.11.2",
              "settings": {"depth": DEPTH, "hash_mb": 64, "threads": 1, "repetitions": 1,
                           "searches": 24, "per_search_timeout_seconds": 60, "total_timeout_seconds": 600,
                           "late_move_reductions": True, "diagnostics": True},
              "initial_resource_policy": resource_check(network), "sessions": [], "samples": [],
              "summaries": {}, "interpretation": "LM Studio running: timings/NPS are raw evidence only. No strength inference."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary output exists; preserve it and choose a new path")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    def remaining(maximum):
        left = min(maximum, deadline - time.monotonic())
        if left <= 0:
            raise TimeoutError("The fixed whole-screen deadline expired")
        return left

    def record_final_budget():
        # Cleanup and evidence preservation must finish even after the deadline.
        # Such a run is retained as invalid, never accepted just because its
        # final engine reply arrived within the individual search allowance.
        report["elapsed_seconds"] = time.monotonic() - started
        if report["elapsed_seconds"] >= 600:
            report.update(status="invalid_or_interrupted", deadline_exceeded=True)
            report.setdefault("error", "TimeoutError: The fixed whole-screen deadline expired during finalization")
            return True
        return False

    try:
        for stage, roles in STAGES.items():
            for index, position in enumerate(POSITIONS):
                for role in roles if index % 2 == 0 else roles[::-1]:
                    resource_check(network)
                    remaining(30)
                    session = {"stage": stage, "position_index": index, "role": role, "commands": []}
                    report["sessions"].append(session)
                    engine = Engine(paths["parent"] if role.startswith("parent_") else paths["candidate"])
                    session.update(pid=engine.process.pid, output=engine.transcript)
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
                                raise ValueError("Unexpected setup output: " + " | ".join(setup))
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
                                    raise ValueError("Unexpected search readiness output")
                                begin = len(engine.transcript)
                                sample["status"] = "incomplete"
                                try:
                                    send(f"go depth {DEPTH}")
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(60))
                                finally:
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], boards[index], role)
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
            summary = summarize(report["samples"], stage)
            report["summaries"][stage] = summary
            publish(output, report)
            if summary["equivalence_mismatches"]:
                raise ValueError("Default-off search differs from the frozen parent; candidate stage is blocked")
        remaining(1)  # Includes the final validation, summary and engine cleanup.
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["after_sha256"] = {name: digest(path) if path.is_file() else None for name, path in paths.items()}
        changed = [name for name, asset in assets.items() if report["after_sha256"][name] != asset["sha256"]]
        if changed:
            report.update(status="invalid_or_interrupted", artifact_drift=changed)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        expired_before_publish = record_final_budget()
        publish(output, report)
        # A slow final filesystem write is part of the budget too. If it alone
        # crosses the boundary, replace this run's provisional success with its
        # terminal invalid status; do not start or repeat any search.
        if record_final_budget() and not expired_before_publish:
            publish(output, report)
    if report.get("deadline_exceeded"):
        raise TimeoutError("The fixed whole-screen deadline expired during finalization")
    if report["status"] != "complete":
        raise ValueError("Screen artifacts changed during execution")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host-load", required=True, choices=("lm-studio-running",))
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output,
                     parent_sha256=args.parent_sha256, candidate_sha256=args.candidate_sha256,
                     host_load=args.host_load)
    print(json.dumps({"status": report["status"], "summaries": report["summaries"]}, indent=2))


if __name__ == "__main__":
    main()
