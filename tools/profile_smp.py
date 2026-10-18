#!/usr/bin/env python3
"""Bounded Lazy SMP scaling measurements on previously exposed benchmark roots.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One engine searches at a time with the same shared Hash reservation and network.
Throughput includes duplicate worker effort; neither throughput nor depth proves
playing strength. Fixed-depth searches need not visit equal nodes across workers.
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

from bench import POSITIONS, digest
from compare_bench import physical_memory
from profile_search import reject_errors
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
NETWORK_BYTES = 98511183
SOURCES = ("tools/profile_smp.py", "tests/profile_smp_test.py", "tools/bench.py",
           "tools/compare_bench.py", "tools/profile_search.py", "tools/resources.py",
           "tools/uci_client.py", "requirements-match.txt", "networks/manifest.json")


def board_for(position):
    """Independently replay an exposed start-position history with pinned chess."""
    if chess is None or chess.__version__ != "1.11.2":
        raise ValueError("SMP profiling requires chess==1.11.2; install requirements-match.txt")
    tokens = position.split()
    if ("\n" in position or "\r" in position or tokens[:1] != ["startpos"]
            or (len(tokens) > 1 and tokens[1] != "moves")):
        raise ValueError("Expected a single-line exposed startpos history")
    board = chess.Board()
    for token in tokens[2:]:
        legal_push(board, token)
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise ValueError("Scaling root is invalid, terminal or already drawn")
    return board


def unsigned(text, name, maximum=2**64 - 1):
    if not text.isascii() or not text.isdecimal() or int(text) > maximum:
        raise ValueError(f"Invalid {name}: {text}")
    return int(text)


def legal_push(board, text):
    """Reject null moves explicitly: python-chess accepts them for analysis."""
    move = chess.Move.from_uci(text)
    if move not in board.legal_moves:
        raise ValueError("Illegal move in search evidence: " + text)
    board.push(move)


def validate_result(lines, board, mode, depth):
    """Check every completed PV, the final move and monotonic UCI counters.

    The final depth-free info record publishes exact aggregate counters after
    helpers have joined. Per-depth records describe the reporting worker's PV.
    """
    reject_errors(lines)
    iterations, bestmove, ponder, totals = [], None, None, None
    for line in lines:
        if bestmove is not None:
            raise ValueError("Unexpected output after bestmove")
        tokens = line.split()
        if tokens[:2] == ["info", "depth"]:
            if totals is not None:
                raise ValueError("Completed iteration after final totals")
            fields = {}
            for name in ("depth", "seldepth", "nodes", "time", "nps", "hashfull", "score", "pv"):
                if tokens.count(name) != 1:
                    raise ValueError("Missing or duplicate info field: " + name)
                at = tokens.index(name)
                if at + 1 == len(tokens):
                    raise ValueError("Missing info value: " + name)
                if name not in ("score", "pv"):
                    fields[name] = unsigned(tokens[at + 1], name, 1000 if name == "hashfull" else 2**64 - 1)
            score_at = tokens.index("score")
            if score_at + 2 >= len(tokens) or tokens[score_at + 1] not in ("cp", "mate"):
                raise ValueError("Invalid score type")
            value = tokens[score_at + 2]
            if not value.lstrip("-").isascii() or not value.lstrip("-").isdecimal() or value.startswith("--"):
                raise ValueError("Invalid signed score")
            fields["score"] = {"type": tokens[score_at + 1], "value": int(value)}
            pv = tokens[tokens.index("pv") + 1:]
            if not pv:
                raise ValueError("A nonterminal search must report a principal variation")
            replay = board.copy()
            for move in pv:
                legal_push(replay, move)
            fields["pv"] = pv
            # Cached cutoffs can complete a nominal depth without traversing
            # that many plies; seldepth is not constrained to exceed depth.
            if fields["depth"] != len(iterations) + 1:
                raise ValueError("Missing, repeated or invalid completed depth")
            if iterations and any(fields[name] < iterations[-1][name] for name in ("nodes", "time")):
                raise ValueError("Search counters went backwards")
            if mode == "depth" and fields["depth"] > depth:
                raise ValueError("Search exceeded the requested completed depth")
            iterations.append(fields)
        elif tokens[:2] == ["info", "nodes"]:
            names = {"nodes", "time", "nps", "hashfull"}
            # Accept both the frozen pre-Syzygy transcript and current UCI totals.
            if "tbhits" in tokens[1::2]:
                names.add("tbhits")
            if totals is not None or len(tokens) != 1 + 2 * len(names) or set(tokens[1::2]) != names:
                raise ValueError("Missing, duplicate or malformed final aggregate counters")
            totals = {name: unsigned(value, name, 1000 if name == "hashfull" else 2**64 - 1)
                      for name, value in zip(tokens[1::2], tokens[2::2])}
        elif tokens[:1] == ["bestmove"]:
            if len(tokens) not in (2, 4) or (len(tokens) == 4 and tokens[2] != "ponder"):
                raise ValueError("Malformed bestmove record")
            bestmove = tokens[1]
            replay = board.copy()
            legal_push(replay, bestmove)
            if len(tokens) == 4:
                ponder = tokens[3]
                legal_push(replay, ponder)
        elif tokens[:2] == ["info", "string"]:
            # Normal timings must have diagnostics disabled; unknown status text
            # is retained, while errors are rejected above.
            if len(tokens) >= 3 and tokens[2] in ("search-summary", "search-iteration", "cache", "smp", "ordering", "lmr"):
                raise ValueError("Search diagnostics must be disabled during scaling timings")
        elif tokens:
            raise ValueError("Unexpected search output: " + line)
    if not iterations or bestmove is None or totals is None:
        raise ValueError("Missing completed search info, final aggregate counters or terminal bestmove")
    final = iterations[-1]
    if any(totals[name] < final[name] for name in ("nodes", "time")):
        raise ValueError("Final aggregate counters went backwards")
    if mode == "depth" and final["depth"] != depth:
        raise ValueError("Search failed to finish the requested depth")
    if final["pv"][0] != bestmove or (ponder is not None and (len(final["pv"]) < 2 or final["pv"][1] != ponder)):
        raise ValueError("Final principal variation and bestmove disagree")
    return {"bestmove": bestmove, "ponder": ponder, "completed_depth": final["depth"],
            "reported_nodes": totals["nodes"], "reported_time_ms": totals["time"],
            "reported_nps": totals["nps"], "score": final["score"],
            "hashfull": totals["hashfull"], "iterations": iterations, "final_aggregate": totals}


def run_order(threads, block):
    """Rotate slots, then reverse the next cycle to reduce ordering bias."""
    offset = block % len(threads)
    order = list(threads[offset:] + threads[:offset])
    return order if block // len(threads) % 2 == 0 else order[::-1]


def resource_check(network, hash_mb, threads, resident_workers=None):
    """Account for shared weights/table and private worker state conservatively."""
    policy = dict(current_budget())
    # Keep the peak worker-state reservation throughout a run even if changing
    # Threads leaves reusable allocations in the engine's memory allocator.
    resident_workers = max(threads, resident_workers or threads)
    reservation = hash_mb * 1024**2 + 4 * network.stat().st_size + (64 + 128 * resident_workers) * 1024**2
    memory = physical_memory()
    policy.update(active_search_workers=threads, resident_engines=1,
                  reserved_worker_states=resident_workers,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if threads > policy["max_cpu_workers"] or (memory is not None and reservation > memory * policy["memory_fraction"]):
        raise ValueError("Estimated SMP resources exceed the current local budget")
    return policy


def distribution(values):
    """Describe observed repetitions without a statistical strength claim."""
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def summarize(samples, threads, repeats, modes):
    """Pair each root/repetition with its one-worker measurement; fail closed."""
    measured = [sample for sample in samples if not sample["warmup"]]
    lookup = {}
    for sample in measured:
        key = (sample["mode"], sample["position_index"], sample["repetition"], sample["threads"])
        if sample["status"] != "complete" or key in lookup:
            raise ValueError("Incomplete or duplicate scaling sample")
        elapsed, nodes = sample["elapsed_seconds"], sample["result"]["reported_nodes"]
        if not math.isfinite(elapsed) or elapsed <= 0 or nodes <= 0:
            raise ValueError("Scaling samples require positive elapsed time and nodes")
        lookup[key] = sample
    expected = {(mode, index, repetition, workers) for mode in modes
                for index in range(len(POSITIONS)) for repetition in range(repeats) for workers in threads}
    if set(lookup) != expected:
        raise ValueError("Incomplete scaling comparison matrix")
    comparisons = []
    for mode in modes:
        for workers in threads:
            pairs = []
            for index in range(len(POSITIONS)):
                for repetition in range(repeats):
                    baseline, sample = [lookup[mode, index, repetition, count] for count in (1, workers)]
                    a, b = baseline["result"], sample["result"]
                    baseline_nps = a["reported_nodes"] / baseline["elapsed_seconds"]
                    sample_nps = b["reported_nodes"] / sample["elapsed_seconds"]
                    pairs.append({"position_index": index, "repetition": repetition,
                                  "throughput_ratio": sample_nps / baseline_nps,
                                  "latency_ratio": baseline["elapsed_seconds"] / sample["elapsed_seconds"],
                                  "completed_depth_difference": b["completed_depth"] - a["completed_depth"],
                                  "same_bestmove": a["bestmove"] == b["bestmove"],
                                  "same_score": a["score"] == b["score"],
                                  "reported_nodes_one_worker_many_workers": [a["reported_nodes"], b["reported_nodes"]]})
            ratios = [pair["throughput_ratio"] for pair in pairs]
            latency = [pair["latency_ratio"] for pair in pairs]
            comparisons.append({"mode": mode, "threads": workers, "pairs": pairs,
                                "throughput_ratio": distribution(ratios),
                                "throughput_ratio_geomean": math.exp(statistics.mean(map(math.log, ratios))),
                                "latency_ratio": distribution(latency),
                                "latency_ratio_geomean": math.exp(statistics.mean(map(math.log, latency))),
                                "completed_depth_difference": distribution([pair["completed_depth_difference"] for pair in pairs])})
    return {"comparisons": comparisons,
            "ratio_definition": "Throughput: reported aggregate nodes / external elapsed relative to Threads=1. Latency: one-worker elapsed / many-worker elapsed. Ratios above one favor more workers.",
            "limitations": "Parallel searches visit different and partly duplicate nodes. Completed depth belongs to the reporting worker. These observed timing/scaling samples prove neither Elo gains nor a general hardware speedup."}


def publish(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def profile(binary, network, output, threads=(1, 2, 4), mode="movetime", movetime_ms=1000,
            depth=7, repeats=3, warmups=1, hash_mb=64, search_timeout=30., total_timeout=120.,
            expected_engine_sha256=None):
    """Run an exclusively claimed, bounded measurement and preserve failures."""
    threads = tuple(threads)
    if (not threads or threads[0] != 1 or len(set(threads)) != len(threads)
            or any(type(value) is not int or not 1 <= value <= 64 for value in threads)):
        raise ValueError("threads must be unique integers in 1..64, starting with 1")
    for value, name, minimum, maximum in ((movetime_ms, "movetime-ms", 100, 10000), (depth, "depth", 1, 8),
                                         (repeats, "repeats", 1, 10), (warmups, "warmups", 0, 2),
                                         (hash_mb, "hash-mb", 1, 1024)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be {minimum}..{maximum}")
    if mode not in ("movetime", "depth", "both"):
        raise ValueError("mode must be movetime, depth or both")
    if (not math.isfinite(search_timeout) or not 0 < search_timeout <= 120
            or not math.isfinite(total_timeout) or not 0 < total_timeout <= 300):
        raise ValueError("search timeout must be (0, 120], total timeout (0, 300] seconds")
    if output.exists() or output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Profile output already exists; choose a new path")
    paths = {"binary": binary.resolve(), "network": network.resolve()}
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Artifact paths must fit on one UCI line")
    boards = [board_for(position) for position in POSITIONS]
    paths.update({name: ROOT / name for name in SOURCES})
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()}
    if frozen["network"]["sha256"] != NETWORK_SHA256 or network.stat().st_size != NETWORK_BYTES:
        raise ValueError("Network differs from the pinned SF19 payload")
    if expected_engine_sha256 is not None and frozen["binary"]["sha256"] != expected_engine_sha256:
        raise ValueError("Engine differs from the requested SHA-256 pin")
    initial = resource_check(network, hash_mb, max(threads))
    modes = ("movetime", "depth") if mode == "both" else (mode,)
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "platform": platform.platform(), "machine": platform.machine(),
              "referee_version": chess.__version__, "positions": POSITIONS,
              "settings": {"threads": threads, "modes": modes, "movetime_ms": movetime_ms, "depth": depth,
                           "repeats": repeats, "warmups": warmups, "hash_mb": hash_mb,
                           "search_diagnostics": False, "lmr": False, "capture_ordering": "mvv-lva",
                           "time_policy": "classic", "ponder": False, "move_overhead_ms": 20,
                           "search_timeout_seconds": search_timeout, "total_timeout_seconds": total_timeout},
              "initial_resource_policy": initial, "samples": [], "commands": [],
              "timing": "External monotonic go-to-bestmove round trip; configuration/newgame/readiness excluded. Each sample clears table and learned history; only one engine is resident.",
              "interpretation": "Bounded scaling observations; parallel duplicate work and changed search trees prevent an Elo or equal-work speed claim."}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    deadline = time.monotonic() + total_timeout

    def remaining(limit):
        duration = min(limit, deadline - time.monotonic())
        if duration <= 0:
            raise TimeoutError("Profile exceeded its bounded total time allowance")
        return duration

    def verify_pins():
        observed = {name: digest(path) for name, path in paths.items()}
        if any(observed[name] != asset["sha256"] for name, asset in frozen.items()):
            raise ValueError("Frozen profile artifact changed")
        return observed

    try:
        with Engine(paths["binary"]) as engine:
            report["protocol_output"] = engine.transcript

            def send(command):
                report["commands"].append(command)
                engine.send(command)

            send("uci")
            report["identity"] = engine.until("uciok", timeout=remaining(30))
            reject_errors(report["identity"])
            options = {"Hash": str(hash_mb), "Threads": "1", "EvalFile": str(paths["network"]),
                       "Ponder": "false", "Move Overhead": "20", "Time Policy": "classic",
                       "Search Diagnostics": "false", "Late Move Reductions": "false", "Capture Ordering": "mvv-lva"}
            for name, value in options.items():
                if not any(line.startswith(f"option name {name} type ") for line in report["identity"]):
                    raise ValueError("Engine lacks option " + name)
                send(f"setoption name {name} value {value}")
            send("isready")
            report["setup_output"] = engine.until("readyok", timeout=remaining(120))
            reject_errors(report["setup_output"])
            for warmup, count in ((True, warmups), (False, repeats)):
                for repetition in range(count):
                    for index, position in enumerate(POSITIONS):
                        for selected_mode in modes:
                            for workers in run_order(threads, repetition * len(POSITIONS) + index):
                                verify_pins()
                                policy = resource_check(network, hash_mb, workers, max(threads))
                                sample = {"mode": selected_mode, "threads": workers, "position_index": index,
                                          "repetition": repetition, "warmup": warmup, "status": "preparing",
                                          "resource_policy": policy}
                                report["samples"].append(sample)
                                sample["preparation_commands"] = [f"setoption name Threads value {workers}", "ucinewgame",
                                                                  "position " + position, "isready"]
                                begin = len(engine.transcript)
                                try:
                                    for command in sample["preparation_commands"]:
                                        send(command)
                                    sample["preparation_output"] = engine.until("readyok", timeout=remaining(30))
                                finally:
                                    sample.setdefault("preparation_output", engine.transcript[begin:])
                                reject_errors(sample["preparation_output"])
                                if sample["preparation_output"] != ["readyok"]:
                                    raise ValueError("Unexpected preparation output; possible stale worker report after bestmove")
                                sample["go"] = f"go movetime {movetime_ms}" if selected_mode == "movetime" else f"go depth {depth}"
                                sample["status"] = "incomplete"
                                begin, started = len(engine.transcript), time.monotonic_ns()
                                try:
                                    send(sample["go"])
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(search_timeout))
                                finally:
                                    sample["elapsed_seconds"] = (time.monotonic_ns() - started) / 1e9
                                    sample.setdefault("output", engine.transcript[begin:])
                                sample["result"] = validate_result(sample["output"], boards[index], selected_mode, depth)
                                sample["status"] = "complete"
                                publish(output, report)
        report["after_sha256"] = verify_pins()
        report.update(status="complete", summary=summarize(report["samples"], threads, repeats, modes))
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
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", default="1,2,4", help="Comma-separated worker counts, beginning with 1")
    parser.add_argument("--mode", choices=("movetime", "depth", "both"), default="movetime")
    parser.add_argument("--movetime-ms", type=int, default=1000)
    parser.add_argument("--depth", type=int, default=7)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--search-timeout", type=float, default=30.)
    parser.add_argument("--total-timeout", type=float, default=120.)
    parser.add_argument("--expected-engine-sha256", help="Optional externally recorded engine pin")
    args = parser.parse_args()
    try:
        workers = tuple(int(value) for value in args.threads.split(","))
        report = profile(args.engine, args.network, args.output, workers, args.mode, args.movetime_ms,
                         args.depth, args.repeats, args.warmups, args.hash_mb, args.search_timeout,
                         args.total_timeout, args.expected_engine_sha256)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"SMP profile failed: {error}\n")
    print(json.dumps({"status": report["status"], "output": str(args.output), "searches": len(report["samples"]),
                      "summary": report["summary"]}))


if __name__ == "__main__":
    main()
