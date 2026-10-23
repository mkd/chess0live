#!/usr/bin/env python3
"""One fixed deep quiet-reduction development screen; speed is not playing strength.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This small orchestration reuses frozen validators and summaries, never modifies
their historical protocols. The owner's editable batch script stays separate;
this tool neither imports it nor implements another puzzle benchmark framework.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time

from bench import digest
from profile_cache import cache_record
from profile_null_move import finish_session, publish
from profile_lmr import validate_result as validate_lmr
from profile_smp import validate_result as validate_uci
import profile_reverse_futility as previous
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4d6-deep-quiet.md"
PARENT_SHA256 = "4f51466335c5021ace971da8ed12548f884a9c1299484a8e2b3f39858a24b28c"
NETWORK_SHA256 = previous.NETWORK_SHA256
DEPTH, MOVETIME_MS, MOVE_OVERHEAD_MS = 6, 500, 20
PROFILE_BUDGET_SECONDS = 900
STAGES = ("parent_equivalence", "deep_quiet_work", "equal_time")
SOURCES = (*previous.SOURCES, "tools/profile_deep_quiet.py",
           "tests/profile_deep_quiet_test.py", "src/search.cpp", "src/main.cpp",
           "include/chess0live/search.hpp", "include/chess0live/search_policy.hpp",
           "include/chess0live/time_management.hpp", "tools/profile_lmr.py",
           "tools/profile_cache.py")
resource_check = previous.resource_check
board_for = previous.board_for
COUNTERS = ("extra_reductions", "researches", "fail_lows", "verified_cutoffs")


def options_for(role, network):
    options = previous.options_for("off", network)
    if role not in ("parent", "off", "on"):
        raise ValueError("Unknown profile role")
    options.update({"Late Move Reductions": "true", "Search Diagnostics": "true",
                    "Move Overhead": str(MOVE_OVERHEAD_MS),
                    "Reverse Futility Pruning": "false", "QSearch SEE Pruning": "false"})
    if role != "parent":
        options["Deep Quiet Reductions"] = "true" if role == "on" else "false"
    return options


def role_order(stage, index):
    if stage == "parent_equivalence":
        roles = ("parent", "off")
    else:
        roles = ("off", "on")
    return roles if (index + (stage == "equal_time")) % 2 == 0 else roles[::-1]


def summarize_search(samples, stage):
    """Retain every decision/work difference before gating parent equivalence.

    Historical summaries assume the older LMR-off protocol. Reuse only their
    pure matrix/accounting code under its off/on names, then add diagnostics and
    complete per-depth differences here, including unmatched completed depths.
    """
    if stage not in STAGES:
        raise ValueError("Unknown profile stage")
    roles = ("parent", "off") if stage == "parent_equivalence" else ("off", "on")
    old_stage = "equal_time" if stage == "equal_time" else "reverse_work"
    selected = [sample for sample in samples if sample["stage"] == stage]
    mapped = [dict(sample, stage=old_stage, role="off" if sample["role"] == roles[0] else "on")
              for sample in selected]
    if any(sample["role"] not in roles for sample in selected):
        raise ValueError("Unexpected comparison role")
    result = previous.summarize(mapped, old_stage)
    lookup = {(sample["position_index"], sample["temperature"], sample["role"]): sample["result"]
              for sample in selected}
    mismatches = []
    for pair in result["pairs"]:
        index, temperature = pair["position_index"], pair["temperature"]
        left, right = [lookup[index, temperature, role] for role in roles]
        a, b = [value["signature"] for value in (left, right)]
        pair["roles"] = list(roles)
        rows = [{row["depth"]: row for row in value["iterations"]} for value in (a, b)]
        pair["iteration_differences"] = [
            {"depth": depth, "left": rows[0].get(depth), "right": rows[1].get(depth)}
            for depth in sorted(rows[0].keys() | rows[1].keys())
            if rows[0].get(depth) != rows[1].get(depth)]
        pair["final_differences"] = {key: [a[key], b[key]]
                                     for key in ("bestmove", "ponder", "nodes", "lmr", "ordering", "cache")
                                     if a[key] != b[key]}
        pair["lmr"] = [left["lmr"], right["lmr"]]
        pair["deep_lmr"] = [left["deep_lmr"], right["deep_lmr"]]
        pair["cache"] = [left["cache"], right["cache"]]
        pair["aborted_duration_ms"] = [left["trace"]["aborted_duration_ms"],
                                       right["trace"]["aborted_duration_ms"]]
        if stage == "parent_equivalence" and a != b:
            mismatches.append({"position_index": index, "temperature": temperature})
    if stage == "parent_equivalence":
        for temperature, totals in result["totals_by_temperature"].items():
            result["totals_by_temperature"][temperature] = {
                "parent": totals["off"], "off": totals["on"]}
    result["equivalence_mismatches"] = mismatches
    result["diagnostics_by_role"] = {
        role: {"searches": len(chosen),
               "lmr": {name: sum(sample["result"]["lmr"][name] for sample in chosen)
                       for name in ("reductions", "researches", "fail_lows", "verified_cutoffs")},
               "deep_lmr": {name: sum(sample["result"]["deep_lmr"][name] for sample in chosen)
                            for name in COUNTERS},
               "deep_activation_searches": sum(sample["result"]["deep_lmr"]["extra_reductions"] > 0
                                               for sample in chosen)}
        for role in roles
        for chosen in [[sample for sample in selected if sample["role"] == role]]}
    return result


def deep_record(lines, role, lmr):
    """The enabled-only record is absent for both parent and candidate-off.

    Deep counters are a subset of ordinary LMR counters. A research interrupted
    before verification completes need not belong to either outcome partition.
    """
    records = [line for line in lines if line.startswith("info string deep-lmr ")]
    enabled = role == "on"
    if len(records) != int(enabled):
        raise ValueError("Expected one deep-lmr record only for candidate-on")
    if not enabled:
        return dict(enabled=False, **dict.fromkeys(COUNTERS, 0))
    tokens = records[0].split()
    if tokens[:4] != ["info", "string", "deep-lmr", "v1"] or len(tokens) != 14:
        raise ValueError("Malformed deep-lmr schema")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != {"enabled", *COUNTERS} or fields["enabled"] != "true":
        raise ValueError("Missing/duplicate deep-lmr fields or wrong enabled state")
    for name in COUNTERS:
        if not fields[name].isascii() or not fields[name].isdecimal():
            raise ValueError("Deep-lmr counters must be nonnegative integers")
        fields[name] = int(fields[name])
        parent_name = "reductions" if name == "extra_reductions" else name
        if fields[name] > lmr[parent_name]:
            raise ValueError("Deep-lmr counter exceeds its ordinary LMR total")
    if (fields["researches"] > fields["extra_reductions"] or
            fields["fail_lows"] + fields["verified_cutoffs"] > fields["researches"]):
        raise ValueError("Inconsistent deep-lmr verification accounting")
    if lines.index(records[0]) > next(i for i, line in enumerate(lines)
                                    if line.startswith("info string search-summary ")):
        raise ValueError("Deep-lmr record arrived after the final search summary")
    return dict(fields, enabled=True)


def validate_result(lines, board, mode, role):
    """Validate both UCI totals/legal PVs and the actual LMR-on search trace.

    The strict historical UCI validator receives only ordinary UCI records;
    every removed diagnostic is explicitly allowlisted and the search/LMR ones
    are independently parsed. Hash occupancy remains in evidence but is omitted
    from the exact off/parent signature because its reporting changes here.
    """
    if mode not in ("depth", "movetime") or role not in ("parent", "off", "on"):
        raise ValueError("Unknown search mode or role")
    allowed = {"cache", "search-iteration", "search-summary", "ordering", "lmr", "deep-lmr"}
    ordinary = []
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"]:
            if len(tokens) < 3 or tokens[2] not in allowed:
                raise ValueError("Unexpected diagnostic or nonisolated experiment: " + line)
            continue
        if tokens[:1] == ["info"]:
            if (tokens.count("tbhits") != 1 or tokens[-1] == "tbhits" or
                    tokens[tokens.index("tbhits") + 1] != "0"):
                raise ValueError("Every info record must have zero tablebase hits")
            if "lowerbound" in tokens or "upperbound" in tokens:
                raise ValueError("Completed iterations require exact scores")
        ordinary.append(line)
    diagnostic = validate_lmr(lines, True, board, DEPTH if mode == "depth" else None,
                              None, ordering_required=True)
    result = validate_uci(ordinary, board, mode, DEPTH)
    trace, lmr = diagnostic["trace"], diagnostic["lmr"]
    summary = trace["summary"]
    if summary["nodes"] != result["reported_nodes"]:
        raise ValueError("Final UCI total disagrees with search diagnostics")
    # Explicit movetime subtracts Move Overhead from both limits. Fixed-depth
    # requests have no clock budget. Verify actual activation, not just commands.
    expected_budget = MOVETIME_MS - MOVE_OVERHEAD_MS if mode == "movetime" else 0
    if summary["soft_ms"] != expected_budget or summary["hard_ms"] != expected_budget:
        raise ValueError("Search budgets differ from the requested fixed limits")
    if mode == "movetime" and summary["stop_reason"] != "hard_time":
        raise ValueError("The fixed movetime request stopped for an unrelated reason")
    if mode == "depth" and trace["aborted_nodes"]:
        raise ValueError("Completed fixed-depth search contains interrupted work")
    result.update(trace=trace, lmr=lmr, deep_lmr=deep_record(lines, role, lmr),
                  ordering=diagnostic["ordering"], cache=cache_record(lines, 64),
                  unfinished_nodes=trace["aborted_nodes"],
                  seldepth=result["iterations"][-1]["seldepth"])
    result["signature"] = {
        "iterations": [{name: row[name] for name in ("depth", "seldepth", "nodes", "score", "pv")}
                       for row in result["iterations"]],
        "bestmove": result["bestmove"], "ponder": result["ponder"],
        "nodes": result["reported_nodes"], "lmr": lmr, "ordering": result["ordering"],
        "cache": result["cache"]}
    return result


def profile(parent, candidate, network, output, *, quiet_host=False):
    if not quiet_host:
        raise ValueError("Use --quiet-host only after other development workloads are idle")
    positions = previous.load_positions()
    paths = {"parent": parent.resolve(), "candidate": candidate.resolve(),
             "network": network.resolve(), "protocol": PROTOCOL,
             "corpus": previous.CORPUS}
    paths.update({name: ROOT / name for name in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    if assets["parent"]["sha256"] != PARENT_SHA256 or assets["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("Parent/network must match the predeclared pins")
    report = {"schema_version": 1, "status": "running", "assets": assets,
              "started_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "protocol": PROTOCOL.read_text(encoding="utf-8"),
              "positions": positions, "positions_sha256": previous.POSITIONS_SHA256,
              "referee_version": "1.11.2", "quiet_host_declaration": True,
              "quiet_host_is_os_measurement": False, "initial_resource_policy": resource_check(network),
              "settings": {"depth": DEPTH, "movetime_ms": MOVETIME_MS,
                           "threads": 1, "hash_mb": 64, "repetitions": 1,
                           "options_by_role": {role: options_for(role, paths["network"])
                                               for role in ("parent", "off", "on")},
                           "searches": 60, "sessions": 36,
                           "depth_search_timeout_seconds": 60, "timed_search_timeout_seconds": 10,
                           "profile_budget_seconds": PROFILE_BUDGET_SECONDS},
              "sessions": [], "samples": [], "summaries": {},
              "interpretation": "Fixed exposed development screen, not speed qualification or playing-strength evidence."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary output exists; preserve it and choose a new path")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    started = time.monotonic()

    def remaining(maximum):
        left = min(maximum, started + PROFILE_BUDGET_SECONDS - time.monotonic())
        if left <= 0:
            raise TimeoutError("The declared stage deadline expired")
        return left

    try:
        for stage in STAGES:
            mode = "depth" if stage in ("parent_equivalence", "deep_quiet_work") else "movetime"
            temperatures = ("cold", "warm") if mode == "depth" else ("cold",)
            for index, position in enumerate(positions):
                board = board_for(position["position"])
                for role in role_order(stage, index):
                    remaining(1)
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
                            advertised = [line for line in identity
                                          if line.startswith("option name Deep Quiet Reductions ")]
                            expected = [] if role == "parent" else [
                                "option name Deep Quiet Reductions type check default false"]
                            if advertised != expected:
                                raise ValueError("Unexpected Deep Quiet Reductions option/default")
                            for name, value in options_for(role, paths["network"]).items():
                                if not any(line.startswith(f"option name {name} type ") for line in identity):
                                    raise ValueError("Missing UCI option: " + name)
                                send(f"setoption name {name} value {value}")
                            send("isready")
                            if engine.until("readyok", timeout=remaining(120)) != [
                                    "info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                                raise ValueError("Unexpected engine setup output")
                            for temperature in temperatures:
                                sample = {"stage": stage, "position_index": index, "role": role,
                                          "mode": mode, "temperature": temperature, "status": "preparing",
                                          "resource_policy": resource_check(network)}
                                report["samples"].append(sample)
                                if temperature == "cold":
                                    send("ucinewgame")
                                send("position " + position["position"])
                                send("isready")
                                if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                    raise ValueError("Unexpected readiness output")
                                begin, search_started = len(engine.transcript), time.monotonic()
                                sample.update(status="incomplete", started_utc=datetime.now(timezone.utc).isoformat())
                                try:
                                    send(f"go depth {DEPTH}" if mode == "depth" else f"go movetime {MOVETIME_MS}")
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(60 if mode == "depth" else 10))
                                finally:
                                    sample["elapsed_seconds"] = time.monotonic() - search_started
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], board, mode, role)
                                sample["status"] = "complete"
                                publish(output, report)
                            send("isready")
                            if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                raise ValueError("Unexpected trailing output")
                    finally:
                        failing = sys.exc_info()[0] is not None
                        try:
                            finish_session(engine, session)
                        except ValueError:
                            if not failing:
                                raise
            report["summaries"][stage] = summarize_search(report["samples"], stage)
            publish(output, report)
            if stage == "parent_equivalence" and report["summaries"][stage]["equivalence_mismatches"]:
                raise ValueError("Default-off search differs from the parent; all differences retained")
        remaining(1)  # A final cleanup overrun invalidates even a complete matrix.
        report["search_and_cleanup_elapsed_seconds"] = time.monotonic() - started
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report.setdefault("search_and_cleanup_elapsed_seconds", time.monotonic() - started)
        report["after_sha256"] = {name: digest(path) if path.is_file() else None for name, path in paths.items()}
        changed = [name for name, asset in assets.items() if report["after_sha256"][name] != asset["sha256"]]
        if changed:
            report.update(status="invalid_or_interrupted", artifact_drift=changed)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["total_elapsed_seconds"] = time.monotonic() - started
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
    parser.add_argument("--quiet-host", action="store_true")
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output, quiet_host=args.quiet_host)
    print(json.dumps({"status": report["status"], "summaries": report["summaries"]}, indent=2))


if __name__ == "__main__":
    main()
