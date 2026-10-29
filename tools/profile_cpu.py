#!/usr/bin/env python3
"""Record a bounded macOS CPU sample under an explicit search preset.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Warmups precede sampling. The engine stays alive until sample ends naturally;
idle stacks after the search sweep are expected. Sampling perturbs execution:
these records identify candidate hotspots, never throughput or playing strength.
The historical preset preserves the original LMR-off setup; current explicitly
selects accepted defaults with tablebase probing disabled.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

from bench import digest
from compare_bench import reject_errors, search_signature
from profile_lmr import board_for, chess
from profile_search import DEFAULT_POSITIONS, ROOT, positions_from, publish, resource_check
from uci_client import Engine

SAMPLER = Path("/usr/bin/sample")
SOURCES = tuple(ROOT / "tools" / name for name in (
    "profile_cpu.py", "profile_lmr.py", "profile_search.py", "compare_bench.py",
    "bench.py", "uci_client.py", "resources.py"))
BASELINE_OPTIONS = {
    "Threads": "1", "Hash": "64", "Time Policy": "classic",
    "Late Move Reductions": "false", "Capture Ordering": "mvv-lva",
    "Search Diagnostics": "false", "Ponder": "false", "Move Overhead": "20",
}
CURRENT_OPTIONS = dict(BASELINE_OPTIONS, **{
    "Late Move Reductions": "true", "Deep Quiet Reductions": "false",
    "Countermove Ordering": "false", "Continuation History": "false",
    "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
    "QSearch SEE Pruning": "false", "ProbCut": "false", "TT Move Hints": "false",
    "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
})
PRESETS = ("historical", "current")
OPTION_TYPES = {
    "Threads": "spin", "Hash": "spin", "Time Policy": "combo",
    "Late Move Reductions": "check", "Capture Ordering": "combo",
    "Search Diagnostics": "check", "Ponder": "check", "Move Overhead": "spin",
    "EvalFile": "string",
    "Deep Quiet Reductions": "check", "Countermove Ordering": "check",
    "Continuation History": "check", "Null Move Pruning": "check",
    "Reverse Futility Pruning": "check", "QSearch SEE Pruning": "check",
    "ProbCut": "check", "TT Move Hints": "check", "SyzygyPath": "string",
    "SyzygyProbeLimit": "spin", "SyzygyProbeDepth": "spin",
}


def options_for(preset="historical"):
    """Keep historical calls unchanged and isolate each run's selected options."""
    if preset not in PRESETS:
        raise ValueError("Unknown CPU profile preset: " + str(preset))
    return dict(BASELINE_OPTIONS if preset == "historical" else CURRENT_OPTIONS)


def prepare(engine, network, preset="historical"):
    """Require supported option types/values, then explicitly set every policy."""
    options = dict(options_for(preset), EvalFile=str(network))
    engine.send("uci")
    identity = engine.until("uciok")
    reject_errors(identity)
    for name, value in options.items():
        prefix = f"option name {name} type "
        declarations = [line[len(prefix):].split() for line in identity if line.startswith(prefix)]
        if len(declarations) != 1 or not declarations[0] or declarations[0][0] != OPTION_TYPES[name]:
            raise ValueError("Missing, duplicate or wrong-type UCI option: " + name)
        tokens = declarations[0]
        if tokens[0] == "combo" and value not in [tokens[i + 1] for i, token in enumerate(tokens[:-1]) if token == "var"]:
            raise ValueError("Unsupported baseline option value: " + name)
        if tokens[0] == "spin":
            try:
                supported = int(tokens[tokens.index("min") + 1]) <= int(value) <= int(tokens[tokens.index("max") + 1])
            except (ValueError, IndexError) as error:
                raise ValueError("Malformed spin option: " + name) from error
            if not supported:
                raise ValueError("Unsupported baseline option value: " + name)
    commands = [f"setoption name {name} value {value}" for name, value in options.items()] + ["isready"]
    for command in commands:
        engine.send(command)
    ready = engine.until("readyok", timeout=120)
    reject_errors(ready)
    return {"identity": identity, "commands": commands, "output": ready}


def validate_search(lines, depth, board):
    """Validate every completed PV and the best/ponder moves on a fresh referee."""
    signature = search_signature(lines, depth)
    board.parse_uci(signature["bestmove"])
    if signature["ponder"]:
        after = board.copy()
        after.push_uci(signature["bestmove"])
        after.parse_uci(signature["ponder"])
    for iteration in signature["iterations"]:
        after = board.copy()
        for move in iteration["pv"]:
            after.push_uci(move)
    if any(line.startswith(("info string search-", "info string lmr ", "info string ordering ")) for line in lines):
        raise ValueError("Search diagnostics were emitted despite the fixed disabled option")
    return signature


def await_sampling(process, log, pid, duration, launched_ns):
    """Observe sample's startup message; never guess that attach has completed.

    The conservative end bound is launch+duration, earlier than attach+duration.
    Unrecognized/localized startup output is an invalid attempt, not evidence
    that the requested searches were sampled.
    """
    marker = re.compile(rf"Sampling process {pid} for {duration} seconds\b")
    deadline = min(launched_ns + duration * 10**9, time.monotonic_ns() + 10 * 10**9)
    while time.monotonic_ns() < deadline:
        output = log.read_text(encoding="utf-8", errors="replace")
        if marker.search(output):
            if process.poll() is not None:
                raise RuntimeError("Sampler exited before the measured sweep")
            return time.monotonic_ns()
        if process.poll() is not None:
            raise RuntimeError("Sampler exited without a recognized readiness message")
        time.sleep(0.02)
    raise TimeoutError("Sampler readiness was not observed within its bounded startup window")


def stop_sampler(process, record):
    """Always reap the helper; failed attempts need not produce a usable sample."""
    if process.poll() is None:
        record["cleanup"] = "terminated_after_failure"
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            record["cleanup"] = "killed_after_failure"
            process.kill()
            process.wait(timeout=5)
    record["returncode"] = process.returncode


def hashes(paths):
    """Missing artifacts remain visible in partial failure evidence."""
    return {name: digest(path) if path.is_file() else None for name, path in paths.items()}


def profile_positions(document, depth):
    """Resolve bounded per-root depths while preserving complete UCI histories.

    Final-position uniqueness ignores the move counters but retains side,
    castling rights and legal en-passant availability. Histories are replayed by
    the referee before any engine starts, including claimable-draw detection.
    """
    positions = positions_from(document, 0)
    if not 1 <= len(positions) <= 64:
        raise ValueError("This profile requires 1..64 roots")
    for position, entry in zip(positions, document["openings"]):
        requested = entry.get("profile_depth", depth)
        if type(requested) is not int or not 1 <= requested <= 12:
            raise ValueError("profile_depth must be an integer in 1..12: " + position["id"])
        position["profile_depth"] = requested
    boards = [board_for(position["position"]) for position in positions]
    if len({" ".join(board.fen().split()[:4]) for board in boards}) != len(positions):
        raise ValueError("Profile roots must be distinct")
    return positions, boards


def profile(binary, network, input_path, output, duration=120, depth=5, repeats=2, search_timeout=20.,
            preset="historical"):
    if sys.platform != "darwin":
        raise ValueError("CPU sampling requires macOS /usr/bin/sample")
    options = options_for(preset)
    if any(type(value) is not int or not lower <= value <= upper for value, lower, upper in
           ((duration, 10, 300), (depth, 1, 12), (repeats, 1, 10))):
        raise ValueError("Use duration 10..300, depth 1..12 and repeats 1..10")
    if (not isinstance(search_timeout, (int, float)) or isinstance(search_timeout, bool)
            or not math.isfinite(search_timeout) or not 0 < search_timeout <= 30):
        raise ValueError("search-timeout must be finite and in (0, 30] seconds")
    binary, network, input_path, output = (Path(path).resolve() for path in (binary, network, input_path, output))
    if output.exists():
        raise ValueError("Output already exists; preserve it and choose a new directory")
    paths = {"binary": binary, "network": network, "positions": input_path, "sampler": SAMPLER}
    paths.update({str(path.relative_to(ROOT)): path for path in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on a single UCI line")
    frozen = {name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()}
    output.mkdir(parents=True, exist_ok=False)
    report_path, log_path, sample_path = (output / name for name in ("report.json", "sampler.log", "sample.txt"))
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": frozen, "platform": platform.platform(), "machine": platform.machine(),
              "python": sys.version, "referee_version": getattr(chess, "__version__", None),
              "settings": {"preset": preset, "options": dict(options, EvalFile=str(network)), "depth": depth,
                           "repeats": repeats, "duration_seconds": duration, "sampling_interval_ms": 1,
                           "warmup_depth": 5, "warmups_per_root": 1, "search_timeout_seconds": search_timeout},
              "samples": [], "sampler": {},
              "interpretation": "CPU hotspot evidence only. Sampling perturbs search; idle stacks after the sweep are expected. No throughput or strength claim."}
    publish(report_path, report)
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        positions, boards = profile_positions(document, depth)
        report["positions"] = positions
        report["settings"]["position_depths"] = {position["id"]: position["profile_depth"] for position in positions}
        report["settings"]["root_count"] = len(positions)
        report["initial_resource_policy"] = resource_check(network, 64)
        with ExitStack() as stack:
            engine = stack.enter_context(Engine(binary))
            report["protocol_output"] = engine.transcript
            report["setup"] = prepare(engine, network, preset)
            expected = {}

            def search(index, repetition, warmup):
                requested_depth = 5 if warmup else positions[index]["profile_depth"]
                item = {"position_index": index, "repetition": repetition, "warmup": warmup,
                        "depth": requested_depth, "status": "preparing", "resource_policy": resource_check(network, 64)}
                report["samples"].append(item)
                begin = len(engine.transcript)
                commands = ["ucinewgame", "position " + positions[index]["position"], "isready"]
                item["preparation_commands"] = commands
                try:
                    for command in commands:
                        engine.send(command)
                    item["preparation_output"] = engine.until("readyok")
                finally:
                    item.setdefault("preparation_output", engine.transcript[begin:])
                reject_errors(item["preparation_output"])
                if not warmup and (sampler.poll() is not None or time.monotonic_ns() >= window_end):
                    raise RuntimeError("Sampler window ended before a measured search could start")
                begin = len(engine.transcript)
                item.update(status="incomplete", go=f"go depth {requested_depth}", started_monotonic_ns=time.monotonic_ns())
                try:
                    engine.send(item["go"])
                    item["output"] = engine.until("bestmove ", timeout=search_timeout)
                finally:
                    item["ended_monotonic_ns"] = time.monotonic_ns()
                    item.setdefault("output", engine.transcript[begin:])
                    publish(report_path, report)
                if not warmup and (item["ended_monotonic_ns"] > window_end or sampler.poll() is not None):
                    raise RuntimeError("Measured search exceeded the conservative active sampler window")
                signature = validate_search(item["output"], requested_depth, boards[index])
                key = (index, requested_depth)
                if key in expected and signature != expected[key]:
                    raise ValueError("Repeated search signature changed for root " + positions[index]["id"])
                expected[key] = signature
                item.update(status="complete", signature=signature)
                publish(report_path, report)

            for index in range(len(positions)):
                search(index, 0, True)
            log = stack.enter_context(log_path.open("w", encoding="utf-8"))
            command = [str(SAMPLER), str(engine.process.pid), str(duration), "1", "-mayDie", "-file", str(sample_path)]
            launched_ns = time.monotonic_ns()
            window_end = launched_ns + duration * 10**9
            report["sampler"].update(command=command, launched_monotonic_ns=launched_ns,
                                     conservative_end_monotonic_ns=window_end)
            sampler = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            stack.callback(stop_sampler, sampler, report["sampler"])
            report["sampler"]["ready_monotonic_ns"] = await_sampling(sampler, log_path, engine.process.pid, duration, launched_ns)
            publish(report_path, report)
            for repetition in range(repeats):
                for index in range(len(positions)):
                    search(index, repetition, False)
            report["sampler"]["sweep_ended_monotonic_ns"] = time.monotonic_ns()
            # Keep the target alive; do not depend on SIGINT flushing a report.
            sampler.wait(timeout=max(0.001, (window_end - time.monotonic_ns()) / 1e9 + 15))
            report["sampler"]["finished_monotonic_ns"] = time.monotonic_ns()
            if report["sampler"]["finished_monotonic_ns"] < window_end or engine.process.poll() is not None:
                raise RuntimeError("Sampler or target exited before the natural sampling window completed")
            if sampler.returncode != 0 or not sample_path.is_file() or not sample_path.stat().st_size:
                raise RuntimeError("Sampler failed or produced no nonempty sample report")
        report["after_sha256"] = hashes(paths)
        if any(report["after_sha256"][name] != asset["sha256"] for name, asset in frozen.items()):
            raise ValueError("Frozen profiling artifact changed during the run")
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["after_sha256"] = hashes(paths)
        report["artifact_drift"] = [name for name, asset in frozen.items() if report["after_sha256"][name] != asset["sha256"]]
        report["output_sha256"] = hashes({"sampler.log": log_path, "sample.txt": sample_path})
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        publish(report_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS,
                        help="JSON suite with 1..64 distinct legal nonterminal roots; optional per-entry profile_depth")
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing evidence is never overwritten")
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--depth", type=int, default=5,
                        help="Sampled search depth unless overridden by profile_depth; warmups remain depth 5")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--search-timeout", type=float, default=20.)
    parser.add_argument("--preset", choices=PRESETS, default="historical",
                        help="historical preserves LMR-off setup; current pins accepted search defaults and disables tablebases")
    args = parser.parse_args(argv)
    try:
        report = profile(args.engine, args.network, args.positions, args.output, args.duration, args.depth, args.repeats,
                         args.search_timeout, preset=args.preset)
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"CPU profile failed: {error}\n")
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
