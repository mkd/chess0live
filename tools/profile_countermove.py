#!/usr/bin/env python3
"""Profile one isolated ordering candidate; search work is not playing strength.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Both policy engines stay resident, but only one searches at a time. Every cold
search starts with ucinewgame; its immediate warm repeat retains both table and
heuristic state. Complete raw evidence, failures and artifact pins are retained.
"""
import argparse
from contextlib import ExitStack
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
from compare_bench import resource_check
from profile_search import reject_errors
from profile_smp import legal_push, validate_result as validate_uci_result
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = ROOT / "tests/data/countermove-profile.json"
PROTOCOL = ROOT / "docs/experiments/phase4d-countermove.md"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
SOURCES = ("tools/profile_countermove.py", "tests/profile_countermove_test.py",
           "tools/profile_smp.py", "tools/profile_search.py", "tools/compare_bench.py",
           "tools/bench.py", "tools/resources.py", "tools/uci_client.py",
           "requirements-match.txt", "networks/manifest.json")
MODES = ("depth", "movetime")
TEMPERATURES = ("cold", "warm")
POLICIES = ("off", "on")


def board_for(position):
    """Replay full histories with a pinned independent legal-move referee."""
    if chess is None or chess.__version__ != "1.11.2":
        raise ValueError("Countermove profiling requires chess==1.11.2")
    if not isinstance(position, str) or "\n" in position or "\r" in position:
        raise ValueError("Position must fit on one command line")
    tokens = position.split()
    if tokens[:1] == ["startpos"]:
        board, consumed = chess.Board(), 1
    elif tokens[:1] == ["fen"] and len(tokens) >= 7:
        board, consumed = chess.Board(" ".join(tokens[1:7])), 7
    else:
        raise ValueError("Expected startpos or a six-field FEN")
    if not board.is_valid():
        raise ValueError("Invalid profile root")
    if len(tokens) > consumed:
        if tokens[consumed] != "moves" or len(tokens) <= consumed + 1:
            raise ValueError("Unexpected position suffix")
        for move in tokens[consumed + 1:]:
            legal_push(board, move)
    if not board.is_valid() or board.is_game_over(claim_draw=True):
        raise ValueError("Profile roots must be valid, nonterminal and not drawn")
    return board


def load_positions(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported corpus schema")
    positions = document.get("positions")
    if not isinstance(positions, list) or not 1 <= len(positions) <= 100:
        raise ValueError("Corpus must have 1..100 positions")
    seen = set()
    for entry in positions:
        if (not isinstance(entry, dict) or not isinstance(entry.get("id"), str)
                or not entry["id"] or entry["id"] in seen):
            raise ValueError("Corpus needs unique nonempty position ids")
        board_for(entry.get("position"))
        seen.add(entry["id"])
    return document, positions


def validate_result(lines, board, mode, depth):
    """Check all PVs and exact iteration scores, with diagnostics/TB disabled."""
    for line in lines:
        tokens = line.split()
        if tokens[:2] == ["info", "string"]:
            raise ValueError("Diagnostic/status output is unexpected in timed search: " + line)
        if "lowerbound" in tokens or "upperbound" in tokens:
            raise ValueError("Completed iterations must report exact scores")
        if tokens[:1] == ["info"]:
            if tokens.count("tbhits") != 1:
                raise ValueError("Every search counter record requires one tbhits field")
            at = tokens.index("tbhits")
            if at + 1 >= len(tokens) or tokens[at + 1] != "0":
                raise ValueError("Tablebase hits would mix experimental factors")
    result = validate_uci_result(lines, board, mode, depth)
    result["unfinished_nodes"] = result["reported_nodes"] - result["iterations"][-1]["nodes"]
    result["seldepth"] = result["iterations"][-1]["seldepth"]
    return result


def run_order(repetition, position_index, mode_index):
    return POLICIES if (repetition + position_index + mode_index) % 2 == 0 else POLICIES[::-1]


def distribution(values):
    return {"minimum": min(values), "median": statistics.median(values),
            "maximum": max(values),
            "geometric_mean": math.exp(statistics.mean(math.log(value) for value in values))}


def summarize(samples, positions, repeats):
    """Require every declared cell; show score changes instead of hiding them."""
    lookup = {}
    for sample in samples:
        key = (sample["mode"], sample["temperature"], sample["position_index"],
               sample["repetition"], sample["policy"])
        if key in lookup or sample["status"] != "complete":
            raise ValueError("Incomplete or duplicated profile sample")
        if (not math.isfinite(sample["elapsed_seconds"]) or sample["elapsed_seconds"] <= 0
                or sample["result"]["reported_nodes"] <= 0):
            raise ValueError("Profile samples need positive finite time and search work")
        lookup[key] = sample
    expected = {(mode, temperature, index, repetition, policy)
                for mode in MODES for temperature in TEMPERATURES
                for index in range(len(positions)) for repetition in range(repeats)
                for policy in POLICIES}
    if set(lookup) != expected:
        raise ValueError("Incomplete or unexpected comparison matrix")
    pairs, groups = [], []
    for mode in MODES:
        for temperature in TEMPERATURES:
            for index, position in enumerate(positions):
                selected = []
                for repetition in range(repeats):
                    off, on = [lookup[mode, temperature, index, repetition, policy] for policy in POLICIES]
                    a, b = off["result"], on["result"]
                    differences = [{"depth": ai["depth"], "off": ai["score"], "on": bi["score"]}
                                   for ai, bi in zip(a["iterations"], b["iterations"])
                                   if ai["score"] != bi["score"]]
                    pair = {"mode": mode, "temperature": temperature, "position_id": position["id"],
                            "position_index": index, "repetition": repetition,
                            "node_ratio_on_over_off": b["reported_nodes"] / a["reported_nodes"],
                            "elapsed_ratio_on_over_off": on["elapsed_seconds"] / off["elapsed_seconds"],
                            "completed_depths_off_on": [a["completed_depth"], b["completed_depth"]],
                            "same_bestmove": a["bestmove"] == b["bestmove"],
                            "same_final_score": a["score"] == b["score"],
                            "common_depth_score_differences": differences}
                    pairs.append(pair)
                    selected.append(pair)
                groups.append({"mode": mode, "temperature": temperature,
                               "position_id": position["id"], "pairs": len(selected),
                               "node_ratio_on_over_off": distribution([p["node_ratio_on_over_off"] for p in selected]),
                               "elapsed_ratio_on_over_off": distribution([p["elapsed_ratio_on_over_off"] for p in selected]),
                               "score_difference_pairs": sum(bool(p["common_depth_score_differences"]) for p in selected),
                               "final_score_difference_pairs": sum(not p["same_final_score"] for p in selected),
                               "bestmove_difference_pairs": sum(not p["same_bestmove"] for p in selected)})
    aggregate = []
    for mode in MODES:
        for temperature in TEMPERATURES:
            selected = [p for p in pairs if p["mode"] == mode and p["temperature"] == temperature]
            policies = {}
            for policy in POLICIES:
                chosen = [s for s in samples if (s["mode"], s["temperature"], s["policy"]) == (mode, temperature, policy)]
                policies[policy] = {"searches": len(chosen),
                                    "total_nodes": sum(s["result"]["reported_nodes"] for s in chosen),
                                    "total_elapsed_seconds": sum(s["elapsed_seconds"] for s in chosen),
                                    "unfinished_nodes": sum(s["result"]["unfinished_nodes"] for s in chosen),
                                    "median_completed_depth": statistics.median(s["result"]["completed_depth"] for s in chosen)}
            aggregate.append({"mode": mode, "temperature": temperature, "policies": policies,
                              "node_ratio_on_over_off": distribution([p["node_ratio_on_over_off"] for p in selected]),
                              "elapsed_ratio_on_over_off": distribution([p["elapsed_ratio_on_over_off"] for p in selected]),
                              "total_node_ratio_on_over_off": policies["on"]["total_nodes"] / policies["off"]["total_nodes"],
                              "total_elapsed_ratio_on_over_off": policies["on"]["total_elapsed_seconds"] / policies["off"]["total_elapsed_seconds"],
                              "score_difference_pairs": sum(bool(p["common_depth_score_differences"]) for p in selected),
                              "final_score_difference_pairs": sum(not p["same_final_score"] for p in selected),
                              "bestmove_difference_pairs": sum(not p["same_bestmove"] for p in selected)})
    return {"aggregate": aggregate, "per_position": groups, "pairs": pairs,
            "ratio_definition": "on / off; below one means less candidate work or elapsed time, not stronger play",
            "interpretation": "Exposed diagnostic positions, not strength or Elo evidence. Inspect score deviations; equal-time depth differences can explain different final scores."}


def publish(output, report):
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(output)


def remaining_timeout(deadline, maximum):
    """Every protocol wait shares the declared run deadline, including setup."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("The declared total profile time budget expired")
    return min(maximum, remaining)


def require_readiness(lines):
    """A barrier must not absorb a duplicate bestmove or other stale reply."""
    if lines != ["readyok"]:
        raise ValueError("Unexpected output at readiness barrier: " + " | ".join(lines))


def prepare(engine, network, hash_mb, policy, deadline):
    engine.send("uci")
    identity = engine.until("uciok", timeout=remaining_timeout(deadline, 30.))
    reject_errors(identity)
    options = {"Hash": str(hash_mb), "Threads": "1", "EvalFile": str(network),
               "Ponder": "false", "Move Overhead": "20", "Time Policy": "classic",
               "Late Move Reductions": "false", "Capture Ordering": "mvv-lva",
               "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "Search Diagnostics": "false",
               "Countermove Ordering": "true" if policy == "on" else "false"}
    for name in options:
        if not any(line.startswith(f"option name {name} type ") for line in identity):
            raise ValueError("Missing required UCI option: " + name)
    commands = [f"setoption name {name} value {value}" for name, value in options.items()] + ["isready"]
    for command in commands:
        engine.send(command)
    reply = engine.until("readyok", timeout=remaining_timeout(deadline, 120.))
    reject_errors(reply)
    return {"identity": identity, "commands": commands, "output": reply}


def profile(binary, network, input_path, output, depth=6, movetime_ms=500, repeats=3,
            hash_mb=64, search_timeout=60., total_timeout=600.):
    if (type(depth) is not int or not 1 <= depth <= 10 or type(movetime_ms) is not int
            or not 1 <= movetime_ms <= 10000 or type(repeats) is not int or not 1 <= repeats <= 10
            or type(hash_mb) is not int or not 1 <= hash_mb <= 16384):
        raise ValueError("Invalid depth, movetime, repetition or Hash limit")
    if (not math.isfinite(search_timeout) or not 0 < search_timeout <= 120
            or not math.isfinite(total_timeout) or not search_timeout <= total_timeout <= 900):
        raise ValueError("Timeouts require 0 < search <= 120 and search <= total <= 900 seconds")
    if output.exists():
        raise ValueError("Output already exists; preserve it and select a new path")
    if digest(network) != NETWORK_SHA256:
        raise ValueError("The network must match the pinned architecture artifact")
    document, positions = load_positions(input_path)
    paths = {"binary": binary, "network": network, "positions": input_path, "protocol": PROTOCOL}
    paths.update({name: ROOT / name for name in SOURCES})
    for name, expected in document.get("sources", {}).items():
        source = ROOT / name
        if source.resolve().is_relative_to(ROOT) is False or digest(source) != expected:
            raise ValueError("Exposed source corpus changed: " + name)
        paths[name] = source
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Artifact paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    report = {"schema_version": 1, "status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "assets": assets, "platform": platform.platform(), "machine": platform.machine(),
              "referee_version": chess.__version__, "positions": positions,
              "initial_resource_policy": resource_check(network, hash_mb),
              "settings": {"depth": depth, "movetime_ms": movetime_ms, "repeats": repeats,
                           "hash_mb": hash_mb, "threads": 1, "diagnostics": False,
                           "search_timeout_seconds": search_timeout, "total_timeout_seconds": total_timeout},
              "timing": "Monotonic go-to-bestmove; reset, readiness and loading excluded. Cold and immediately repeated warm (TT plus heuristics) are separate. No discarded warmups.",
              "samples": [], "protocol_output": {}, "setup": {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    publish(output, report)
    deadline = time.monotonic() + total_timeout
    try:
        with ExitStack() as stack:
            engines = {}
            for policy in POLICIES:
                engine = engines[policy] = stack.enter_context(Engine(binary))
                report["protocol_output"][policy] = engine.transcript
                report["setup"][policy] = prepare(engine, network, hash_mb, policy, deadline)
            for mode_index, mode in enumerate(MODES):
                for repetition in range(repeats):
                    for index, position in enumerate(positions):
                        board = board_for(position["position"])
                        for policy in run_order(repetition, index, mode_index):
                            engine = engines[policy]
                            for temperature in TEMPERATURES:
                                remaining_timeout(deadline, search_timeout)
                                sample = {"mode": mode, "temperature": temperature, "position_index": index,
                                          "position_id": position["id"], "repetition": repetition,
                                          "policy": policy, "status": "preparing",
                                          "resource_policy": resource_check(network, hash_mb)}
                                report["samples"].append(sample)
                                commands = (["ucinewgame"] if temperature == "cold" else []) + [
                                    "position " + position["position"], "isready"]
                                sample["preparation_commands"] = commands
                                begin = len(engine.transcript)
                                try:
                                    for command in commands:
                                        engine.send(command)
                                    sample["preparation_output"] = engine.until("readyok", timeout=remaining_timeout(deadline, 30.))
                                finally:
                                    sample.setdefault("preparation_output", engine.transcript[begin:])
                                require_readiness(sample["preparation_output"])
                                sample["go"] = f"go depth {depth}" if mode == "depth" else f"go movetime {movetime_ms}"
                                sample["status"] = "incomplete"
                                begin, began = len(engine.transcript), time.monotonic_ns()
                                try:
                                    engine.send(sample["go"])
                                    sample["output"] = engine.until("bestmove ", timeout=remaining_timeout(deadline, search_timeout))
                                finally:
                                    sample["elapsed_seconds"] = (time.monotonic_ns() - began) / 1e9
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], board, mode, depth)
                                # This untimed barrier also catches extra output
                                # after the final sample, not just before its successor.
                                engine.send("isready")
                                begin = len(engine.transcript)
                                try:
                                    sample["post_search_output"] = engine.until("readyok", timeout=remaining_timeout(deadline, 30.))
                                finally:
                                    sample.setdefault("post_search_output", engine.transcript[begin:])
                                require_readiness(sample["post_search_output"])
                                sample["status"] = "complete"
                                publish(output, report)
        report["after_sha256"] = {name: digest(path) for name, path in paths.items()}
        changed = [name for name in paths if report["after_sha256"][name] != assets[name]["sha256"]]
        if changed:
            raise ValueError("Profile artifacts changed during execution: " + ", ".join(changed))
        report.update(status="complete", summary=summarize(report["samples"], positions, repeats))
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
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--movetime-ms", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--search-timeout", type=float, default=60.)
    parser.add_argument("--total-timeout", type=float, default=600.)
    args = parser.parse_args()
    try:
        report = profile(args.engine.resolve(), args.network.resolve(), args.positions.resolve(), args.output.resolve(),
                         args.depth, args.movetime_ms, args.repeats, args.hash_mb,
                         args.search_timeout, args.total_timeout)
        print(json.dumps(report["summary"]["aggregate"], indent=2))
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"Countermove profile failed: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Countermove profile interrupted; partial evidence preserved.\n")


if __name__ == "__main__":
    main()
