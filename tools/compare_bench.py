#!/usr/bin/env python3
"""Compare deterministic fixed-depth search throughput, never playing strength.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Both binaries stay loaded. Each search receives a cleared table and the same
position/network/Hash/Threads settings; newgame/readiness work is outside timing.
One warmup per position/binary precedes measured, alternating-order repetitions.
Search signatures must match within and across binaries on every sampled run.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import time

from bench import POSITIONS, digest
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
MOVE = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?")


def reject_errors(lines):
    if any("error:" in line.lower() for line in lines):
        raise ValueError("Engine reported an error: " + " | ".join(lines))


def search_signature(lines, depth):
    """Ignore timing/NPS/hash occupancy; compare all reported search decisions.

    This checks sampled deterministic search equivalence, not a proof that all
    positions evaluate identically. Exact NNUE oracle tests remain independent.
    """
    reject_errors(lines)
    iterations, bestmove, ponder = [], None, None
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"]:
            continue
        if tokens and tokens[0] == "info" and "depth" in tokens:
            def integer(name):
                return int(tokens[tokens.index(name) + 1])
            try:
                score_index = tokens.index("score")
                unit, score = tokens[score_index + 1:score_index + 3]
                pv = tokens[tokens.index("pv") + 1:]
                if unit not in ("cp", "mate") or not pv or any(not MOVE.fullmatch(move) for move in pv):
                    raise ValueError("Malformed score or principal variation")
                if "lowerbound" in tokens or "upperbound" in tokens:
                    raise ValueError("A completed-depth benchmark requires exact scores")
                iteration = {"depth": integer("depth"), "seldepth": integer("seldepth"),
                             "nodes": integer("nodes"), "score": {"unit": unit, "value": int(score)}, "pv": pv}
                if iteration["depth"] != len(iterations) + 1 or iteration["nodes"] <= 0:
                    raise ValueError("Missing, repeated, or non-search iteration")
                iterations.append(iteration)
            except (ValueError, IndexError) as error:
                raise ValueError("Invalid completed iteration: " + line) from error
        elif tokens and tokens[0] == "bestmove":
            if bestmove is not None or len(tokens) not in (2, 4) or not MOVE.fullmatch(tokens[1]):
                raise ValueError("Invalid bestmove: " + line)
            bestmove = tokens[1]
            if len(tokens) == 4:
                if tokens[2] != "ponder" or not MOVE.fullmatch(tokens[3]):
                    raise ValueError("Invalid ponder move: " + line)
                ponder = tokens[3]
    if bestmove is None or len(iterations) != depth:
        raise ValueError("Search did not complete the requested nonterminal depth")
    if iterations[-1]["pv"][0] != bestmove:
        raise ValueError("bestmove disagrees with the last completed principal variation")
    return {"iterations": iterations, "bestmove": bestmove, "ponder": ponder}


def run_order(repetition, position_index):
    return ("baseline", "candidate") if (repetition + position_index) % 2 == 0 else ("candidate", "baseline")


def variability(values):
    median = statistics.median(values)
    return {"median": median, "minimum": min(values), "maximum": max(values),
            "median_absolute_deviation": statistics.median(abs(value - median) for value in values)}


def summarize(samples, positions):
    measured = [sample for sample in samples if not sample["warmup"]]
    results, ratios = [], []
    for index, position in enumerate(positions):
        selected = [sample for sample in measured if sample["position_index"] == index]
        repetitions = sorted({sample["repetition"] for sample in selected})
        paired = []
        for repetition in repetitions:
            pair = [sample for sample in selected if sample["repetition"] == repetition]
            if len(pair) != 2 or {sample["role"] for sample in pair} != {"baseline", "candidate"}:
                raise ValueError("Incomplete or duplicated benchmark pair")
            by_role = {sample["role"]: sample for sample in pair}
            if by_role["baseline"]["signature"] != by_role["candidate"]["signature"]:
                raise ValueError("Different search work cannot support a semantics-preserving speed comparison")
            times = {role: sample["elapsed_seconds"] for role, sample in by_role.items()}
            if any(not math.isfinite(value) or value <= 0 for value in times.values()):
                raise ValueError("Benchmark durations must be finite and positive")
            paired.append(times["baseline"] / times["candidate"])
        if not paired:
            raise ValueError("Each position needs at least one completed measured pair")
        ratios.extend(paired)
        results.append({"position": position, "samples_per_binary": len(paired),
                        "baseline_seconds": variability([sample["elapsed_seconds"] for sample in selected if sample["role"] == "baseline"]),
                        "candidate_seconds": variability([sample["elapsed_seconds"] for sample in selected if sample["role"] == "candidate"]),
                        "paired_speed_ratio": variability(paired)})
    return {"positions": results, "paired_speed_ratio": variability(ratios),
            "ratio_definition": "baseline elapsed / candidate elapsed; greater than one means candidate faster",
            "uncertainty": "Observed variability only; no significance interval, Elo inference, or universal performance claim."}


def publish(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def physical_memory():
    """Best-effort physical RAM detection with no optional package dependency."""
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        if sys.platform == "win32":
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.total
        return None


def resource_check(network, hash_mb):
    """Reserve both resident engines; only one searches at a time.

    Four times each network file plus 256 MiB combined process overhead gives a
    conservative planning estimate. Compressed files, engine allocation strategy,
    and other applications prevent this from being an OS-enforced memory cap.
    """
    policy = dict(current_budget())
    reservation = 2 * hash_mb * 1024**2 + 8 * network.stat().st_size + 256 * 1024**2
    memory = physical_memory()
    policy.update({"active_search_workers": 1, "resident_engines": 2,
                   "estimated_memory_bytes": reservation, "physical_memory_bytes": memory,
                   "memory_estimate_is_hard_cap": False})
    if policy["max_cpu_workers"] < 1:
        raise ValueError("Current resource policy does not permit a search worker")
    if memory is not None and reservation > memory * policy["memory_fraction"]:
        raise ValueError("Estimated combined engine memory exceeds the current resource budget")
    return policy


def prepare(engine, network, hash_mb):
    engine.send("uci")
    identity = engine.until("uciok")
    for name in ("Hash", "Threads", "EvalFile"):
        if not any(line.startswith(f"option name {name} type ") for line in identity):
            raise ValueError(f"Both binaries must advertise the {name} UCI option")
    engine.send(f"setoption name Hash value {hash_mb}")
    engine.send("setoption name Threads value 1")
    engine.send(f"setoption name EvalFile value {network}")
    engine.send("isready")
    reject_errors(engine.until("readyok", timeout=120))
    return identity


def compare(baseline, candidate, network, positions, depth, repeats, hash_mb, output, search_timeout=300.0):
    if not math.isfinite(search_timeout) or not 0 < search_timeout <= 300:
        raise ValueError("search-timeout must be finite and in (0, 300] seconds")
    if output.exists():
        raise ValueError("Comparison output already exists; preserve it and choose a new path")
    assets = {"baseline": baseline, "candidate": candidate, "network": network}
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in assets.items()}
    initial_policy = resource_check(network, hash_mb)
    sources = [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
               for path in (ROOT / "tools" / name for name in
                            ("compare_bench.py", "bench.py", "uci_client.py", "resources.py"))]
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "runner_sources": sources, "platform": platform.platform(),
              "machine": platform.machine(), "depth": depth, "repeats": repeats,
              "threads": 1, "hash_mb": hash_mb, "warmups_per_position_per_binary": 1,
              "per_search_timeout_seconds": search_timeout,
              "initial_resource_policy": initial_policy,
              "positions": positions, "samples": [],
              "timing": "External monotonic go-to-bestmove round trip; newgame/readiness excluded",
              "interpretation": "Sampled exact-search-work throughput comparison, not playing strength."}
    output.parent.mkdir(parents=True, exist_ok=True)
    publish(output, report)
    try:
        with ExitStack() as stack:
            engines = {name: stack.enter_context(Engine(path)) for name, path in assets.items() if name != "network"}
            report["uci_identity"] = {name: prepare(engine, network, hash_mb) for name, engine in engines.items()}
            expected = {}
            for warmup in (True, False):
                for repetition in range(1 if warmup else repeats):
                    for index, position in enumerate(positions):
                        for role in run_order(repetition, index):
                            policy = resource_check(network, hash_mb)
                            engine = engines[role]
                            engine.send("ucinewgame")
                            engine.send("position " + position)
                            engine.send("isready")
                            reject_errors(engine.until("readyok"))
                            transcript_begin = len(engine.transcript)
                            began = time.monotonic_ns()
                            engine.send(f"go depth {depth}")
                            try:
                                lines = engine.until("bestmove ", timeout=search_timeout)
                            except BaseException:
                                report["samples"].append({
                                    "role": role, "position_index": index, "repetition": repetition,
                                    "warmup": warmup, "elapsed_seconds": (time.monotonic_ns() - began) / 1e9,
                                    "resource_policy": policy, "signature": None, "status": "incomplete",
                                    "output": engine.transcript[transcript_begin:]})
                                publish(output, report)
                                raise
                            elapsed = (time.monotonic_ns() - began) / 1e9
                            sample = {"role": role, "position_index": index, "repetition": repetition,
                                      "warmup": warmup, "elapsed_seconds": elapsed,
                                      "resource_policy": policy, "signature": None, "output": lines}
                            report["samples"].append(sample)
                            signature = search_signature(lines, depth)
                            sample["signature"] = signature
                            publish(output, report)
                            if index in expected and signature != expected[index]:
                                raise ValueError(f"Search signature differs for position {index + 1}, {role}, repetition {repetition}")
                            expected[index] = signature
        for name, path in assets.items():
            if digest(path) != frozen[name]["sha256"]:
                raise ValueError(f"Frozen {name} changed during the benchmark")
        for source in sources:
            if digest(ROOT / source["path"]) != source["sha256"]:
                raise ValueError("Benchmark source changed during the experiment")
        report.update(status="complete", signatures_match=True,
                      summary=summarize(report["samples"], positions))
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        publish(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--positions", type=Path, help="One UCI position body per line; default is tools/bench.py suite")
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--search-timeout", type=float, default=300.0, help="Abort comparison if one search exceeds this many seconds (maximum 300)")
    args = parser.parse_args()
    if not 1 <= args.depth <= 12 or not 1 <= args.repeats <= 100 or not 1 <= args.hash_mb <= 16384:
        parser.error("depth must be 1..12, repeats 1..100, and hash-mb 1..16384")
    positions = POSITIONS
    if args.positions:
        positions = [line.strip() for line in args.positions.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
        if not positions or any(not (line == "startpos" or line.startswith("startpos moves ") or line.startswith("fen ")) for line in positions):
            parser.error("Invalid UCI position list")
    try:
        report = compare(args.baseline.resolve(), args.candidate.resolve(), args.network.resolve(),
                         positions, args.depth, args.repeats, args.hash_mb, args.output.resolve(), args.search_timeout)
        print(json.dumps(report["summary"], indent=2, allow_nan=False))
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"Comparison failed: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Comparison interrupted; partial raw results preserved.\n")


if __name__ == "__main__":
    main()
