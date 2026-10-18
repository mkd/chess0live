#!/usr/bin/env python3
"""Bounded cold/warm transposition-table diagnostics on exposed development roots.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Requires the optional chess==1.11.2 referee. A warm search retains the table and
learned move history; each search resets the evaluator. Changes cannot be
attributed to the table alone, including possible effects of internal caches.
These diagnostics establish neither playing strength nor a general speed gain.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import time

try:
    import chess
except ImportError:
    chess = None

from bench import POSITIONS, digest
from compare_bench import search_signature
from profile_search import diagnostics, physical_memory, reject_errors
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
NETWORK_BYTES = 98511183
# Phase 4A preserves the original 96-byte bucket sizing divisor when compacting
# entries. Configured Hash is a reservation ceiling, not promised allocation.
BUCKET_SIZING_BYTES = 96
CACHE_FIELDS = {"entry_bytes", "bucket_bytes", "buckets", "capacity", "allocated_bytes",
                "probes", "hits", "cutoffs", "stores", "replacements"}
SOURCES = ("tools/profile_cache.py", "tools/bench.py", "tools/compare_bench.py",
           "tools/profile_search.py", "tools/resources.py", "tools/uci_client.py",
           "tests/profile_cache_test.py", "requirements-match.txt", "networks/manifest.json")


def positions_from(suite):
    """Restrict profiling to named, previously exposed development suites."""
    if suite == "bench":
        return [{"id": f"bench-{index + 1}", "position": body}
                for index, body in enumerate(POSITIONS)], None
    if suite != "gamephases":
        raise ValueError("suite must be bench or gamephases; held-out roots are not supported")
    path = ROOT / "tests/data/performance-gamephases.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    positions = []
    for entry in document["openings"]:
        if entry.get("moves") != [] or len(entry["fen"].split()) != 6:
            raise ValueError("Expected exposed six-field gamephase roots without histories")
        positions.append({"id": entry["id"], "position": "fen " + entry["fen"]})
    if len(positions) != 12 or len({item["id"] for item in positions}) != 12:
        raise ValueError("Expected twelve distinct development gamephase roots")
    return positions, path


def board_for(position):
    """Replay the full history through the separately pinned legal-move referee."""
    if chess is None or chess.__version__ != "1.11.2":
        raise ValueError("Cache profiling requires chess==1.11.2; install requirements-match.txt")
    if "\n" in position or "\r" in position:
        raise ValueError("Position must fit on one UCI line")
    tokens = position.split()
    if tokens[:1] == ["startpos"]:
        board, suffix = chess.Board(), tokens[1:]
    elif tokens[:1] == ["fen"] and len(tokens) >= 7:
        board, suffix = chess.Board(" ".join(tokens[1:7])), tokens[7:]
    else:
        raise ValueError("Invalid position command body")
    if not board.is_valid() or (suffix and suffix[0] != "moves"):
        raise ValueError("Invalid root or move-list syntax")
    for move in suffix[1:]:
        board.push_uci(move)
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise ValueError("Profile roots must be valid, nonterminal and not already drawn")
    return board


def cache_record(lines, hash_mb):
    """Check counters, actual bytes, and Phase 4A's preserved bucket count."""
    records = [line for line in lines if line.startswith("info string cache ")]
    if len(records) != 1:
        raise ValueError("Expected exactly one cache diagnostic record")
    tokens = records[0].split()
    if tokens[:4] != ["info", "string", "cache", "v1"] or len(tokens[4:]) != 2 * len(CACHE_FIELDS):
        raise ValueError("Unsupported or malformed cache diagnostic schema")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != CACHE_FIELDS:
        raise ValueError("Missing, duplicate, or unexpected cache fields")
    for name, value in fields.items():
        if not value.isascii() or not value.isdecimal() or int(value) > 2**64 - 1:
            raise ValueError("Cache values must be unsigned 64-bit integers")
        fields[name] = int(value)
    entry, bucket, count, capacity, allocated = (
        fields[name] for name in ("entry_bytes", "bucket_bytes", "buckets", "capacity", "allocated_bytes"))
    requested = hash_mb * 1024**2
    fitting = requested // BUCKET_SIZING_BYTES
    expected_count = 1 << (fitting.bit_length() - 1) if fitting else 0
    if (min(entry, bucket, count, capacity, allocated) <= 0 or count & (count - 1)
            or capacity != 4 * count or bucket < 4 * entry or allocated != bucket * count
            or count != expected_count or allocated > requested):
        raise ValueError("Inconsistent table capacity or byte accounting")
    if (fields["cutoffs"] > fields["hits"] or fields["hits"] > fields["probes"]
            or fields["replacements"] > fields["stores"]):
        raise ValueError("Inconsistent cache counter relationships")
    summary = next((i for i, line in enumerate(lines) if line.startswith("info string search-summary ")), -1)
    if summary < 0 or lines.index(records[0]) > summary:
        raise ValueError("Cache counters must precede the final search summary")
    return fields


def validate_result(lines, board, depth, hash_mb):
    """Require complete search accounting, bounded hashfull, and legal PVs."""
    trace = diagnostics(lines, "classic")
    summary = trace["summary"]
    if summary["completed_depth"] != depth or summary["stop_reason"] != "depth_limit":
        raise ValueError("Search did not finish the requested depth")
    signature = search_signature(lines, depth)
    occupancy = []
    for line in lines:
        tokens = line.split()
        if tokens[:2] != ["info", "depth"]:
            continue
        for name in ("depth", "seldepth", "nodes", "score", "hashfull", "pv"):
            if tokens.count(name) != 1:
                raise ValueError("Missing or duplicate completed-info field: " + name)
        at = tokens.index("hashfull")
        value = tokens[at + 1] if at + 1 < len(tokens) else ""
        if not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 1000:
            raise ValueError("hashfull must be an integer in 0..1000 permille")
        occupancy.append({"depth": int(tokens[tokens.index("depth") + 1]), "hashfull": int(value)})
    if len(occupancy) != depth:
        raise ValueError("Every completed iteration must report hashfull")
    after = board.copy()
    after.push_uci(signature["bestmove"])
    if signature["ponder"]:
        after.parse_uci(signature["ponder"])
    for iteration in signature["iterations"]:
        pv = board.copy()
        for move in iteration["pv"]:
            pv.push_uci(move)
    cache = cache_record(lines, hash_mb)
    # These unrestricted, completed searches cannot abort a probed node: every
    # probe either cuts off from its cached bound or reaches one save attempt.
    if cache["probes"] != cache["stores"] + cache["cutoffs"] or cache["probes"] > summary["nodes"]:
        raise ValueError("Completed search cache probes disagree with saves/cutoffs or total nodes")
    return {"cache": cache, "hashfull": occupancy,
            "signature": signature, "search_summary": summary}


def resource_check(network, hash_mb):
    """Reserve one resident, single-worker engine; this is not an OS usage cap."""
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
    """Update only our exclusively claimed output; preserve another run's temp."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def summarize(samples):
    """Describe cold/warm observations without claiming equal search work."""
    pairs = []
    for index in range(0, len(samples), 2):
        cold, warm = samples[index:index + 2]
        if (cold["state"], warm["state"]) != ("cold", "warm") or cold["position_index"] != warm["position_index"]:
            raise ValueError("Incomplete or unordered cold/warm comparison")
        a, b = cold["result"], warm["result"]
        pairs.append({"position_index": cold["position_index"],
                      "same_signature": a["signature"] == b["signature"],
                      "same_bestmove": a["signature"]["bestmove"] == b["signature"]["bestmove"],
                      "same_final_score": a["signature"]["iterations"][-1]["score"] == b["signature"]["iterations"][-1]["score"],
                      "nodes_cold_warm": [r["search_summary"]["nodes"] for r in (a, b)],
                      "cache_cold_warm": [r["cache"] for r in (a, b)],
                      "final_hashfull_cold_warm": [r["hashfull"][-1]["hashfull"] for r in (a, b)]})
    return pairs


def profile(binary, network, output, depth=5, hash_mb=64, suite="bench",
            search_timeout=30., total_timeout=180., expected_engine_sha256=None):
    """Run cold then warm at each root; never clear state between paired searches."""
    if type(depth) is not int or not 1 <= depth <= 8 or type(hash_mb) is not int or not 1 <= hash_mb <= 1024:
        raise ValueError("depth must be 1..8 and hash-mb must be 1..1024")
    if (not math.isfinite(search_timeout) or not 0 < search_timeout <= 120
            or not math.isfinite(total_timeout) or not 0 < total_timeout <= 300):
        raise ValueError("search timeout must be (0, 120], total timeout (0, 300] seconds")
    if output.exists() or output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Profile output already exists; preserve it and choose a new path")
    paths = {"binary": binary.resolve(), "network": network.resolve()}
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Artifact paths must fit on one UCI line")
    positions, suite_path = positions_from(suite)
    boards = [board_for(item["position"]) for item in positions]
    paths.update({name: ROOT / name for name in SOURCES})
    if suite_path:
        paths["positions"] = suite_path
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()}
    if frozen["network"]["sha256"] != NETWORK_SHA256 or network.stat().st_size != NETWORK_BYTES:
        raise ValueError("Network differs from the pinned SF19 payload")
    if expected_engine_sha256 is not None and frozen["binary"]["sha256"] != expected_engine_sha256:
        raise ValueError("Engine differs from the requested SHA-256 pin")
    initial = resource_check(network, hash_mb)
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "platform": platform.platform(), "machine": platform.machine(),
              "referee_version": chess.__version__, "positions": positions, "suite": suite,
              "settings": {"depth": depth, "hash_mb": hash_mb, "threads": 1, "lmr": False,
                           "capture_ordering": "mvv-lva", "time_policy": "classic", "ponder": False,
                           "search_diagnostics": True, "search_timeout_seconds": search_timeout,
                           "total_timeout_seconds": total_timeout},
              "initial_resource_policy": initial, "samples": [], "commands": [],
              "timing": "External monotonic go-to-bestmove round trip; preparation excluded. One cold then one warm search per exposed root.",
              "interpretation": "Warm searches retain TT and learned move history; each search resets the evaluator. Internal cache effects are not isolated. Diagnostic counts and timings are not a strength result, an isolated TT causal effect, or a general speed claim."}
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
                       "Search Diagnostics": "true", "Late Move Reductions": "false", "Capture Ordering": "mvv-lva"}
            for name, value in options.items():
                if not any(line.startswith(f"option name {name} type ") for line in report["identity"]):
                    raise ValueError("Engine lacks option " + name)
                send(f"setoption name {name} value {value}")
            send("isready")
            report["setup_output"] = engine.until("readyok", timeout=remaining(120))
            reject_errors(report["setup_output"])
            for index, position in enumerate(positions):
                for state in ("cold", "warm"):
                    verify_pins()
                    sample = {"position_index": index, "state": state, "status": "preparing",
                              "resource_policy": resource_check(network, hash_mb)}
                    report["samples"].append(sample)
                    sample["preparation_commands"] = (["ucinewgame"] if state == "cold" else []) + ["position " + position["position"], "isready"]
                    begin = len(engine.transcript)
                    try:
                        for command in sample["preparation_commands"]:
                            send(command)
                        sample["preparation_output"] = engine.until("readyok", timeout=remaining(30))
                    finally:
                        sample.setdefault("preparation_output", engine.transcript[begin:])
                    reject_errors(sample["preparation_output"])
                    sample["go"], sample["status"] = f"go depth {depth}", "incomplete"
                    begin, started = len(engine.transcript), time.monotonic_ns()
                    try:
                        send(sample["go"])
                        sample["output"] = engine.until("bestmove ", timeout=remaining(search_timeout))
                    finally:
                        sample["elapsed_seconds"] = (time.monotonic_ns() - started) / 1e9
                        sample.setdefault("output", engine.transcript[begin:])
                    sample["result"] = validate_result(sample["output"], boards[index], depth, hash_mb)
                    sample["status"] = "complete"
                    publish(output, report)
        report["after_sha256"] = verify_pins()
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
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--suite", choices=("bench", "gamephases"), default="bench")
    parser.add_argument("--search-timeout", type=float, default=30.)
    parser.add_argument("--total-timeout", type=float, default=180.)
    parser.add_argument("--expected-engine-sha256", help="Optional externally recorded engine pin")
    args = parser.parse_args()
    try:
        report = profile(args.engine, args.network, args.output, args.depth, args.hash_mb,
                         args.suite, args.search_timeout, args.total_timeout, args.expected_engine_sha256)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"Cache profile failed: {error}\n")
    print(json.dumps({"status": report["status"], "output": str(args.output), "searches": len(report["samples"])}))


if __name__ == "__main__":
    main()
