#!/usr/bin/env python3
"""Profile clock allocation with bounded, alternating classic/forecast searches.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Each position/repetition starts with fresh synthetic clocks and a cleared table.
This is a diagnostic experiment, not a game simulation or strength measurement.
The engine validates position legality; no optional Python package is needed.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import re
import statistics
import time

from bench import digest
from compare_bench import physical_memory
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = ROOT / "tests/data/openings-development.json"
MOVE = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?")
ITERATION_FIELDS = {"depth", "completed", "nodes", "duration_ms", "elapsed_ms"}
SUMMARY_FIELDS = {"policy", "forecast_active", "stop_reason", "nodes", "completed_depth",
                  "elapsed_ms", "soft_ms", "hard_ms", "target_ms", "predicted_next_ms"}
STOP_REASONS = {"external_stop", "node_limit", "hard_time", "soft_time", "forecast",
                "depth_limit", "mate_limit", "terminal", "draw"}


def reject_errors(lines):
    if any("error:" in line.lower() for line in lines):
        raise ValueError("Engine reported an error: " + " | ".join(lines))


def diagnostics(lines, policy):
    """Validate v1 accounting before reporting aborted-work measurements.

    Millisecond diagnostics have three fractional digits, so sums receive a
    small rounding allowance. Node accounting is exact. Different time policies
    may stop at different depths and choose different moves; that is permitted.
    """
    reject_errors(lines)
    iterations, summary, completed_info, bestmove = [], None, [], None
    for line in lines:
        if bestmove is not None:
            raise ValueError("Unexpected output after bestmove")
        tokens = line.split()
        if tokens[:2] == ["info", "string"] and len(tokens) >= 3 and tokens[2].startswith("search-"):
            kind = tokens[2]
            if kind not in ("search-iteration", "search-summary") or len(tokens) < 4 or tokens[3] != "v1":
                raise ValueError("Unsupported search diagnostic schema: " + line)
            values = tokens[4:]
            if len(values) % 2 or len(set(values[::2])) != len(values) // 2:
                raise ValueError("Malformed diagnostic fields: " + line)
            fields = dict(zip(values[::2], values[1::2]))
            if set(fields) != (ITERATION_FIELDS if kind == "search-iteration" else SUMMARY_FIELDS):
                raise ValueError("Missing or unexpected diagnostic fields: " + line)
            for key, value in fields.items():
                if key in ("completed", "forecast_active"):
                    if value not in ("true", "false"):
                        raise ValueError("Invalid diagnostic boolean: " + line)
                    fields[key] = value == "true"
                elif key in ("depth", "nodes", "completed_depth"):
                    if not value.isascii() or not value.isdecimal():
                        raise ValueError("Invalid diagnostic integer: " + line)
                    fields[key] = int(value)
                elif key.endswith("_ms"):
                    fields[key] = float(value)
                    if not math.isfinite(fields[key]) or fields[key] < 0:
                        raise ValueError("Invalid diagnostic duration: " + line)
            if kind == "search-iteration":
                if summary is not None or fields["depth"] != len(iterations) + 1 or (iterations and not iterations[-1]["completed"]):
                    raise ValueError("Missing/repeated iteration or output after an aborted iteration")
                iterations.append(fields)
            else:
                if summary is not None:
                    raise ValueError("Duplicate search summary")
                summary = fields
        elif tokens and tokens[0] == "info" and "depth" in tokens and tokens[1:2] != ["string"]:
            try:
                completed_info.append({key: int(tokens[tokens.index(key) + 1]) for key in ("depth", "nodes")})
            except (ValueError, IndexError) as error:
                raise ValueError("Malformed completed UCI iteration: " + line) from error
        elif tokens and tokens[0] == "bestmove":
            if summary is None:
                raise ValueError("bestmove arrived before the search summary")
            if len(tokens) not in (2, 4) or not (MOVE.fullmatch(tokens[1]) or tokens[1] == "0000"):
                raise ValueError("Invalid bestmove: " + line)
            if len(tokens) == 4 and (tokens[2] != "ponder" or not MOVE.fullmatch(tokens[3])):
                raise ValueError("Invalid ponder move: " + line)
            bestmove = tokens[1]
    if summary is None or bestmove is None:
        raise ValueError("Search lacks a diagnostic summary or bestmove")
    if summary["policy"] != policy or summary["stop_reason"] not in STOP_REASONS:
        raise ValueError("Wrong time policy or unknown stop reason")
    if summary["forecast_active"] != (policy == "forecast"):
        raise ValueError("Clock-only profile requires the selected policy to be active")
    if bestmove == "0000" and summary["stop_reason"] not in ("terminal", "draw"):
        raise ValueError("Null bestmove from a nonterminal search")
    completed = [item for item in iterations if item["completed"]]
    if summary["completed_depth"] != (completed[-1]["depth"] if completed else 0):
        raise ValueError("Completed-depth summary disagrees with iterations")
    if sum(item["nodes"] for item in iterations) != summary["nodes"]:
        raise ValueError("Iteration node counts do not sum to the search total")
    tolerance = 0.001 * (len(iterations) + 2)
    previous, cumulative, expected_info = 0., 0, []
    for item in iterations:
        if item["elapsed_ms"] + tolerance < previous + item["duration_ms"]:
            raise ValueError("Iteration duration exceeds its elapsed interval")
        previous = item["elapsed_ms"]
        cumulative += item["nodes"]
        if item["completed"]:
            expected_info.append({"depth": item["depth"], "nodes": cumulative})
    if not iterations and summary["stop_reason"] in ("terminal", "draw") and completed_info == [{"depth": 0, "nodes": 0}]:
        completed_info = []  # Root adjudication emits a depth-zero score, not an iteration.
    if completed_info != expected_info:
        raise ValueError("Completed UCI node/depth reports disagree with diagnostics")
    if summary["elapsed_ms"] + tolerance < previous or summary["soft_ms"] > summary["hard_ms"]:
        raise ValueError("Invalid elapsed time or soft/hard budget ordering")
    aborted = [item for item in iterations if not item["completed"]]
    return {"iterations": iterations, "summary": summary, "bestmove": bestmove,
            "aborted_nodes": sum(item["nodes"] for item in aborted),
            "aborted_duration_ms": sum(item["duration_ms"] for item in aborted)}


def positions_from(document, limit):
    """Accept the existing opening-suite format, preserving its complete history."""
    if not isinstance(document, dict) or not isinstance(document.get("openings"), list):
        raise ValueError("Positions JSON must contain an openings list")
    positions, ids = [], set()
    for entry in document["openings"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"] or entry["id"] in ids:
            raise ValueError("Each opening needs a unique nonempty string id")
        moves = entry.get("moves")
        if not isinstance(moves, list) or any(not isinstance(move, str) or not MOVE.fullmatch(move) for move in moves):
            raise ValueError("Opening moves must be UCI coordinate moves")
        fen = entry.get("fen")
        if fen is not None and (not isinstance(fen, str) or "\n" in fen or "\r" in fen or len(fen.split()) != 6):
            raise ValueError("Opening FEN must have six fields on one line")
        body = "fen " + fen if fen is not None else "startpos"
        if moves:
            body += " moves " + " ".join(moves)
        positions.append({"id": entry["id"], "position": body})
        ids.add(entry["id"])
    if not positions:
        raise ValueError("Opening suite is empty")
    return positions[:limit] if limit else positions


def resource_check(network, hash_mb):
    policy = dict(current_budget())
    reservation = hash_mb * 1024**2 + 4 * network.stat().st_size + 128 * 1024**2
    memory = physical_memory()
    policy.update(active_search_workers=1, resident_engines=1,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if policy["max_cpu_workers"] < 1 or (memory is not None and reservation > memory * policy["memory_fraction"]):
        raise ValueError("Estimated engine resources exceed the current local budget")
    return policy


def publish(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def summarize(samples):
    result = {}
    for policy in ("classic", "forecast"):
        selected = [sample for sample in samples if sample["policy"] == policy]
        nodes = sum(sample["diagnostics"]["summary"]["nodes"] for sample in selected)
        aborted = sum(sample["diagnostics"]["aborted_nodes"] for sample in selected)
        result[policy] = {"searches": len(selected), "total_nodes": nodes, "aborted_nodes": aborted,
                          "aborted_node_fraction": aborted / nodes if nodes else 0.,
                          "median_elapsed_ms": statistics.median(sample["diagnostics"]["summary"]["elapsed_ms"] for sample in selected),
                          "aborted_duration_ms": sum(sample["diagnostics"]["aborted_duration_ms"] for sample in selected),
                          "stop_reasons": {reason: sum(sample["diagnostics"]["summary"]["stop_reason"] == reason for sample in selected)
                                           for reason in sorted({sample["diagnostics"]["summary"]["stop_reason"] for sample in selected})}}
    return result


def profile(binary, network, input_path, output, repeats=2, position_limit=6,
            wtime=6000, btime=6000, winc=60, binc=60, hash_mb=64,
            overhead=20, search_timeout=10.):
    if not 1 <= repeats <= 100 or not 0 <= position_limit <= 1000 or not 1 <= hash_mb <= 16384:
        raise ValueError("repeats must be 1..100, position-limit 0..1000, hash-mb 1..16384")
    if any(not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 86400000 for value in (wtime, btime, winc, binc)):
        raise ValueError("Clock values must be integer milliseconds in 0..86400000")
    if min(wtime, btime) <= 0 or not 0 <= overhead <= 5000:
        raise ValueError("Both clocks must be positive; overhead must be 0..5000 ms")
    if not math.isfinite(search_timeout) or not 0 < search_timeout <= 300:
        raise ValueError("search-timeout must be finite and in (0, 300] seconds")
    if output.exists():
        raise ValueError("Profile output already exists; preserve it and choose a new path")
    paths = {"binary": binary, "network": network, "positions": input_path}
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Artifact paths must fit on one UCI command line")
    paths.update({"tools/" + name: ROOT / "tools" / name for name in
                  ("profile_search.py", "uci_client.py", "resources.py", "bench.py", "compare_bench.py")})
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()}
    document = json.loads(input_path.read_text(encoding="utf-8"))
    positions = positions_from(document, position_limit)
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "platform": platform.platform(), "machine": platform.machine(),
              "settings": {"wtime_ms": wtime, "btime_ms": btime, "winc_ms": winc, "binc_ms": binc,
                           "threads": 1, "hash_mb": hash_mb, "move_overhead_ms": overhead,
                           "repeats": repeats, "search_timeout_seconds": search_timeout},
              "positions": positions, "input_description": document.get("description"),
              "initial_resource_policy": resource_check(network, hash_mb), "samples": [],
              "interpretation": "Each sample gets fresh synthetic clocks; not a played game, equal-tree test, speed-gain claim or Elo measurement.",
              "timing": "External monotonic go-to-bestmove round trip; table reset, readiness and network loading excluded. No warmup; policy order alternates."}
    output.parent.mkdir(parents=True, exist_ok=True)
    publish(output, report)
    try:
        with Engine(binary) as engine:
            report["protocol_output"] = engine.transcript  # Preserve even partial handshakes/readiness on failure.
            report["initial_command"] = "uci"
            engine.send("uci")
            report["identity"] = engine.until("uciok")
            reject_errors(report["identity"])
            for name in ("Hash", "Threads", "EvalFile", "Ponder", "Move Overhead", "Time Policy", "Search Diagnostics"):
                if not any(line.startswith(f"option name {name} type ") for line in report["identity"]):
                    raise ValueError(f"Engine must advertise the {name} option")
            commands = [f"setoption name Hash value {hash_mb}", "setoption name Threads value 1",
                        f"setoption name EvalFile value {network}", "setoption name Ponder value false",
                        f"setoption name Move Overhead value {overhead}", "setoption name Search Diagnostics value true", "isready"]
            report["setup_commands"] = commands
            for command in commands:
                engine.send(command)
            report["setup_output"] = engine.until("readyok", timeout=120)
            reject_errors(report["setup_output"])
            for repetition in range(repeats):
                for index, position in enumerate(positions):
                    order = ("classic", "forecast") if (repetition + index) % 2 == 0 else ("forecast", "classic")
                    for policy in order:
                        sample = {"position_index": index, "repetition": repetition, "policy": policy,
                                  "resource_policy": resource_check(network, hash_mb), "status": "preparing"}
                        report["samples"].append(sample)
                        commands = [f"setoption name Time Policy value {policy}", "ucinewgame", "position " + position["position"], "isready"]
                        sample["preparation_commands"] = commands
                        begin = len(engine.transcript)
                        try:
                            for command in commands:
                                engine.send(command)
                            sample["preparation_output"] = engine.until("readyok")
                        finally:
                            sample.setdefault("preparation_output", engine.transcript[begin:])
                        reject_errors(sample["preparation_output"])
                        sample["go"] = f"go wtime {wtime} btime {btime} winc {winc} binc {binc}"
                        sample["status"] = "incomplete"
                        begin = len(engine.transcript)
                        started = time.monotonic_ns()
                        try:
                            engine.send(sample["go"])
                            sample["output"] = engine.until("bestmove ", timeout=search_timeout)
                        finally:
                            sample["elapsed_seconds"] = (time.monotonic_ns() - started) / 1e9
                            sample.setdefault("output", engine.transcript[begin:])
                            publish(output, report)
                        sample["diagnostics"] = diagnostics(sample["output"], policy)
                        sample["status"] = "complete"
                        publish(output, report)
        after = {name: digest(path) for name, path in paths.items()}
        report["after_sha256"] = after
        changed = [name for name in paths if after[name] != frozen[name]["sha256"]]
        if changed:
            raise ValueError("Profile artifacts changed during experiment: " + ", ".join(changed))
        report.update(status="complete", summary=summarize(report["samples"]))
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if "after_sha256" not in report:
            report["after_sha256"] = {}
            for name, path in paths.items():
                try:
                    report["after_sha256"][name] = digest(path)
                except OSError as error:
                    report.setdefault("after_hash_errors", {})[name] = str(error)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        publish(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS, help="Existing JSON opening-suite format, full histories preserved; default development suite")
    parser.add_argument("--position-limit", type=int, default=6, help="First N positions from suite; 0 selects all (default 6)")
    parser.add_argument("--repeats", type=int, default=2)
    for flag in ("wtime", "btime", "winc", "binc"):
        parser.add_argument("--" + flag, type=int, default=6000 if flag.endswith("time") else 60,
                            help="Fresh synthetic " + flag + " per search, in milliseconds; never inferred from a game")
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--overhead", type=int, default=20, help="Move Overhead in milliseconds")
    parser.add_argument("--search-timeout", type=float, default=10., help="External per-search timeout, seconds; maximum 300; partial replies preserved")
    args = parser.parse_args()
    try:
        report = profile(args.engine.resolve(), args.network.resolve(), args.positions.resolve(), args.output.resolve(),
                         args.repeats, args.position_limit, args.wtime, args.btime, args.winc, args.binc,
                         args.hash_mb, args.overhead, args.search_timeout)
        print(json.dumps(report["summary"], indent=2))
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"Profile failed: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Profile interrupted; partial evidence preserved.\n")


if __name__ == "__main__":
    main()
