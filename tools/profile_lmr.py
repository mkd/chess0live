#!/usr/bin/env python3
"""Compare isolated LMR or capture-ordering modes at fixed depth OR fixed nodes.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Uses the optional chess==1.11.2 test referee. Different search work is expected;
node counts and timings cannot establish a strength gain. One engine alternates
the selected option with classic timing and cleared state at each full-history
root. The other experimental search option stays at its baseline setting. The
historical filename and default LMR behavior remain compatible with prior runs.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import time

try:
    import chess
except ImportError:
    chess = None

from bench import digest
from compare_bench import search_signature
from profile_search import DEFAULT_POSITIONS, ROOT, diagnostics, positions_from, publish, reject_errors, resource_check
from uci_client import Engine

COUNTERS = ("reductions", "researches", "fail_lows", "verified_cutoffs")


def board_for(position):
    """Replay every supplied move; reject invalid or already adjudicable roots."""
    if chess is None or chess.__version__ != "1.11.2":
        raise ValueError("LMR profiling requires chess==1.11.2; install requirements-match.txt")
    tokens = position.split()
    board = chess.Board() if tokens[0] == "startpos" else chess.Board(" ".join(tokens[1:7]))
    if not board.is_valid():
        raise ValueError("Invalid opening root")
    for token in tokens[tokens.index("moves") + 1:] if "moves" in tokens else []:
        board.push_uci(token)  # Unlike push(), push_uci() checks legality.
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise ValueError("Profile roots must be valid, nonterminal and not already drawn")
    return board


def ordering_record(lines, policy):
    """Reject wrong modes and impossible counts; SEE calls include aborted work."""
    records = [line for line in lines if line.startswith("info string ordering ")]
    if len(records) != 1:
        raise ValueError("Expected exactly one capture-ordering diagnostic record")
    tokens = records[0].split()
    if tokens[:4] != ["info", "string", "ordering", "v1"] or len(tokens[4:]) != 6:
        raise ValueError("Unsupported or malformed ordering diagnostic record")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != {"policy", "see_calls", "losing_captures"} or fields["policy"] != policy:
        raise ValueError("Incorrect capture-ordering policy or fields")
    for name in ("see_calls", "losing_captures"):
        if not fields[name].isascii() or not fields[name].isdecimal():
            raise ValueError("Ordering counters must be nonnegative integers")
        fields[name] = int(fields[name])
    if fields["losing_captures"] > fields["see_calls"] or (policy == "mvv-lva" and fields["see_calls"]):
        raise ValueError("Inconsistent capture-ordering counters")
    if lines.index(records[0]) > next(i for i, line in enumerate(lines) if line.startswith("info string search-summary ")):
        raise ValueError("Ordering counters arrived after the final search summary")
    return fields


def validate_result(lines, enabled, board, depth, nodes, experiment="lmr", ordering_required=False):
    if experiment not in ("lmr", "capture-ordering"):
        raise ValueError("Unknown search experiment")
    lmr_enabled = enabled if experiment == "lmr" else False
    trace = diagnostics(lines, "classic")
    records = [line for line in lines if line.startswith("info string lmr ")]
    if len(records) != 1:
        raise ValueError("Expected exactly one LMR diagnostic record")
    if lines.index(records[0]) > next(i for i, line in enumerate(lines) if line.startswith("info string search-summary ")):
        raise ValueError("LMR counters arrived after the final search summary")
    tokens = records[0].split()
    if tokens[:4] != ["info", "string", "lmr", "v1"] or len(tokens[4:]) != 10:
        raise ValueError("Unsupported or malformed LMR diagnostic record")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != {"enabled", *COUNTERS} or fields["enabled"] != str(lmr_enabled).lower():
        raise ValueError("Missing/duplicate LMR fields or incorrect enabled state")
    for name in COUNTERS:
        if not fields[name].isascii() or not fields[name].isdecimal():
            raise ValueError("LMR counters must be nonnegative integers")
        fields[name] = int(fields[name])
    if (fields["researches"] > fields["reductions"] or
            fields["fail_lows"] + fields["verified_cutoffs"] > fields["researches"] or
            (not lmr_enabled and any(fields[name] for name in COUNTERS))):
        raise ValueError("Inconsistent LMR counter accounting")
    summary = trace["summary"]
    if nodes is not None and (summary["nodes"] > nodes or summary["stop_reason"] not in ("node_limit", "depth_limit")):
        raise ValueError("Search exceeded the node limit or stopped for an unrelated reason")
    if nodes is not None and summary["stop_reason"] == "node_limit" and summary["nodes"] != nodes:
        raise ValueError("Search reports a node-limit stop before reaching the requested count")
    if depth is not None and (summary["completed_depth"] != depth or summary["stop_reason"] != "depth_limit"):
        raise ValueError("Search did not complete the requested depth")
    bestmove_tokens = lines[-1].split()
    signature = search_signature(lines, summary["completed_depth"]) if summary["completed_depth"] else {
        "iterations": [], "bestmove": trace["bestmove"], "ponder": bestmove_tokens[3] if len(bestmove_tokens) == 4 else None}
    board.parse_uci(signature["bestmove"])
    if signature["ponder"]:
        after = board.copy()
        after.push_uci(signature["bestmove"])
        after.parse_uci(signature["ponder"])
    for iteration in signature["iterations"]:
        pv = board.copy()
        for move in iteration["pv"]:
            pv.push_uci(move)
    result = {"trace": trace, "lmr": dict(fields, enabled=lmr_enabled), "signature": signature}
    # Old frozen LMR executables predate this record. New ones must keep capture
    # ordering at baseline so an LMR comparison changes only one option.
    if ordering_required or experiment == "capture-ordering" or any(line.startswith("info string ordering ") for line in lines):
        result["ordering"] = ordering_record(lines, "see" if experiment == "capture-ordering" and enabled else "mvv-lva")
    return result


def summarize(samples, experiment="lmr"):
    """Expose decision changes; never demand equal trees for selective search."""
    grouped = {}
    for sample in samples:
        key = (sample["position_index"], sample["repetition"])
        pair = grouped.setdefault(key, {})
        if sample["enabled"] in pair:
            raise ValueError("Duplicate LMR profile sample")
        pair[sample["enabled"]] = sample
    pairs = []
    for (index, repetition), pair in grouped.items():
        if set(pair) != {False, True}:
            raise ValueError("Incomplete LMR comparison pair")
        a, b = (pair[value]["result"] for value in (False, True))
        ai, bi = a["signature"]["iterations"], b["signature"]["iterations"]
        pairs.append({"position_index": index, "repetition": repetition,
                      "completed_depths": [a["trace"]["summary"]["completed_depth"], b["trace"]["summary"]["completed_depth"]],
                      "same_bestmove": a["signature"]["bestmove"] == b["signature"]["bestmove"],
                      "same_final_score": ai[-1]["score"] == bi[-1]["score"] if ai and bi else None,
                      "same_final_pv": ai[-1]["pv"] == bi[-1]["pv"] if ai and bi else None,
                      "nodes_off_on": [a["trace"]["summary"]["nodes"], b["trace"]["summary"]["nodes"]]})
    record, counters = ("lmr", COUNTERS) if experiment == "lmr" else ("ordering", ("see_calls", "losing_captures"))
    policies = {}
    for enabled in (False, True):
        chosen = [sample for sample in samples if sample["enabled"] == enabled]
        policies["on" if enabled else "off"] = {
            "searches": len(chosen), "total_nodes": sum(s["result"]["trace"]["summary"]["nodes"] for s in chosen),
            "aborted_nodes": sum(s["result"]["trace"]["aborted_nodes"] for s in chosen),
            "median_elapsed_ms": statistics.median(s["result"]["trace"]["summary"]["elapsed_ms"] for s in chosen),
            "counters": {name: sum(s["result"][record][name] for s in chosen) for name in counters}}
    return {"policies": policies, "pairs": pairs,
            "interpretation": "Different search work is expected. These timings, node counts and sampled decisions establish no Elo or strength gain."}


def profile(binary, network, input_path, output, depth=None, nodes=None, repeats=2,
            position_limit=6, hash_mb=64, search_timeout=10., experiment="lmr"):
    if experiment not in ("lmr", "capture-ordering"):
        raise ValueError("Unknown search experiment")
    option = "Late Move Reductions" if experiment == "lmr" else "Capture Ordering"
    values = ("false", "true") if experiment == "lmr" else ("mvv-lva", "see")
    if depth is None and nodes is None: depth = 5
    if (depth is not None and nodes is not None) or (depth is not None and not 1 <= depth <= 12) or (nodes is not None and not 1 <= nodes <= 10000000):
        raise ValueError("Choose depth 1..12 OR nodes 1..10000000, never both")
    if not 1 <= repeats <= 100 or not 0 <= position_limit <= 1000 or not 1 <= hash_mb <= 16384:
        raise ValueError("Invalid repeats, position-limit or hash-mb")
    if not math.isfinite(search_timeout) or not 0 < search_timeout <= 300:
        raise ValueError("search-timeout must be finite and in (0, 300] seconds")
    if output.exists(): raise ValueError("Output already exists; preserve it and choose another path")
    paths = {"binary": binary, "network": network, "positions": input_path}
    if any("\n" in str(p) or "\r" in str(p) for p in paths.values()): raise ValueError("Paths must fit on one UCI line")
    paths.update({"tools/" + name: ROOT / "tools" / name for name in
                  ("profile_lmr.py", "profile_search.py", "uci_client.py", "resources.py", "bench.py", "compare_bench.py")})
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()}
    document = json.loads(input_path.read_text())
    positions = positions_from(document, position_limit)
    boards = [board_for(position["position"]) for position in positions]
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "platform": platform.platform(), "referee_version": chess.__version__,
              "positions": positions, "input_description": document.get("description"),
              "settings": {"depth": depth, "nodes": nodes, "repeats": repeats, "hash_mb": hash_mb,
                           "threads": 1, "time_policy": "classic", "search_timeout_seconds": search_timeout,
                           "experiment": experiment, "option": option, "off_on_values": values},
              "initial_resource_policy": resource_check(network, hash_mb), "samples": [],
              "timing": "One engine, no warmups, alternating baseline/candidate option; fresh table/readiness before go; external elapsed includes protocol transport."}
    output.parent.mkdir(parents=True, exist_ok=True)
    publish(output, report)
    try:
        with Engine(binary) as engine:
            report["protocol_output"] = engine.transcript
            engine.send("uci")
            report["identity"] = engine.until("uciok")
            reject_errors(report["identity"])
            options = {"Hash": str(hash_mb), "Threads": "1", "EvalFile": str(network), "Ponder": "false",
                       "Time Policy": "classic", "Search Diagnostics": "true", "Late Move Reductions": "false"}
            if experiment == "capture-ordering" or any(line.startswith("option name Capture Ordering type ") for line in report["identity"]):
                options["Capture Ordering"] = "mvv-lva"
            for name in options:
                if not any(line.startswith(f"option name {name} type ") for line in report["identity"]): raise ValueError("Engine lacks option " + name)
            report["setup_commands"] = [f"setoption name {name} value {value}" for name, value in options.items()] + ["isready"]
            for command in report["setup_commands"]: engine.send(command)
            report["setup_output"] = engine.until("readyok", timeout=120)
            reject_errors(report["setup_output"])
            for repetition in range(repeats):
                for index, position in enumerate(positions):
                    for enabled in ((False, True) if (repetition + index) % 2 == 0 else (True, False)):
                        sample = {"position_index": index, "repetition": repetition, "enabled": enabled,
                                  "resource_policy": resource_check(network, hash_mb), "status": "preparing"}
                        report["samples"].append(sample)
                        commands = [f"setoption name {option} value {values[int(enabled)]}", "ucinewgame", "position " + position["position"], "isready"]
                        sample["preparation_commands"] = commands
                        begin = len(engine.transcript)
                        try:
                            for command in commands:
                                engine.send(command)
                            sample["preparation_output"] = engine.until("readyok")
                        finally:
                            sample.setdefault("preparation_output", engine.transcript[begin:])
                        reject_errors(sample["preparation_output"])
                        sample["go"] = f"go depth {depth}" if depth is not None else f"go nodes {nodes}"
                        begin, started = len(engine.transcript), time.monotonic_ns()
                        sample["status"] = "incomplete"
                        try:
                            engine.send(sample["go"])
                            sample["output"] = engine.until("bestmove ", timeout=search_timeout)
                        finally:
                            sample["elapsed_seconds"] = (time.monotonic_ns() - started) / 1e9
                            sample.setdefault("output", engine.transcript[begin:])
                            publish(output, report)
                        sample["result"] = validate_result(sample["output"], enabled, boards[index], depth, nodes, experiment, "Capture Ordering" in options)
                        sample["status"] = "complete"
                        publish(output, report)
        report["after_sha256"] = {name: digest(path) for name, path in paths.items()}
        if any(report["after_sha256"][name] != asset["sha256"] for name, asset in frozen.items()): raise ValueError("Frozen profile artifact changed")
        report.update(status="complete", summary=summarize(report["samples"], experiment))
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if "after_sha256" not in report:
            report["after_sha256"] = {}
            for name, path in paths.items():
                try: report["after_sha256"][name] = digest(path)
                except OSError as error: report.setdefault("after_hash_errors", {})[name] = str(error)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        publish(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "network", "output"): parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS, help="JSON opening suite; full histories preserved")
    parser.add_argument("--position-limit", type=int, default=6, help="First N roots; 0 selects all")
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument("--depth", type=int, help="Fixed completed depth; defaults to 5 when no limit given")
    limits.add_argument("--nodes", type=int, help="Fixed total nodes; reports last completed depth and aborted work")
    parser.add_argument("--repeats", type=int, default=2); parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--search-timeout", type=float, default=10., help="Per-search external timeout in seconds, maximum 300")
    parser.add_argument("--experiment", choices=("lmr", "capture-ordering"), default="lmr", help="Change only this option; keep the other at baseline")
    args = parser.parse_args()
    try:
        result = profile(args.engine.resolve(), args.network.resolve(), args.positions.resolve(), args.output.resolve(),
                         args.depth, args.nodes, args.repeats, args.position_limit, args.hash_mb, args.search_timeout, args.experiment)
        print(json.dumps(result["summary"], indent=2))
    except (OSError, ValueError, RuntimeError, TimeoutError) as error: parser.exit(1, f"Search-mode profile failed: {error}\n")
    except KeyboardInterrupt: parser.exit(130, "Interrupted; partial evidence preserved.\n")


if __name__ == "__main__": main()
