#!/usr/bin/env python3
"""Replay exposed clock failures once per LMR mode with fresh engine processes.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This bounded diagnostic cannot establish strength or qualify a search default.
Records are flushed append-only; an error ends the attempt without resumption.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import time

from bench import digest
from profile_lmr import board_for, validate_result
from profile_search import reject_errors, resource_check
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = ROOT / "tests/data/clock-flagfalls-phase3g.json"


class RecordedEngine(Engine):
    """Timestamp incoming lines in the reader, before the consumer queue.

    Receipt is still a host observation, not an engine emission timestamp.
    A descheduled reader can therefore inflate external elapsed time.
    """
    def __init__(self, *args, **kwargs):
        self.events = []
        super().__init__(*args, **kwargs)

    def send(self, command):
        self.events.append({"monotonic_ns": time.monotonic_ns(),
                            "direction": "to_engine", "line": command})
        super().send(command)

    def _read(self):
        for raw in self.process.stdout:
            line = raw.rstrip()
            self.events.append({"monotonic_ns": time.monotonic_ns(),
                                "direction": "from_engine", "line": line})
            self.lines.put(line)
        self.lines.put(None)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_cases(path):
    """Validate every command and replay full histories before starting engines."""
    document = json.loads(path.read_text())
    cases = document.get("cases", [])
    if (document.get("schema_version") != 1 or document.get("purpose") != "exposed-clock-diagnostics"
            or not isinstance(cases, list) or len(cases) != 13):
        raise ValueError("Expected the 13-case v1 exposed clock diagnostic fixture")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in ids:
            raise ValueError("Case ids must be unique nonempty strings")
        ids.add(case["id"])
        position, go = case.get("position_command"), case.get("go_command")
        if any(not isinstance(x, str) or "\n" in x or "\r" in x for x in (position, go)):
            raise ValueError("Commands must each fit on one UCI line")
        if position.split()[:3] != ["position", "startpos", "moves"]:
            raise ValueError("Expected a complete startpos move history")
        board = board_for(position[len("position "):])
        tokens = go.split()
        if (len(tokens) != 9 or tokens[0] != "go"
                or set(tokens[1::2]) != {"wtime", "btime", "winc", "binc"}
                or any(not x.isascii() or not x.isdecimal() for x in tokens[2::2])):
            raise ValueError("Only exact wtime/btime/winc/binc go commands are allowed")
        fields = dict(zip(tokens[1::2], map(int, tokens[2::2])))
        clock = fields["wtime" if board.turn else "btime"]
        if board.fen() != case.get("final_fen") or case.get("input_clock_ms") != clock:
            raise ValueError("Position or input clock disagrees with fixture")
        for key in ("input_clock_ms", "clock_before_ms", "hard_limit_ms"):
            if not finite_number(case.get(key)) or case[key] <= 0:
                raise ValueError("Fixture clock values must be positive finite numbers")
        if (abs(clock - case["clock_before_ms"]) > .501 or not 20 < clock <= 1000
                or case["hard_limit_ms"] > clock - 20 or fields["winc"] != 600 or fields["binc"] != 600):
            raise ValueError("Fixture clocks exceed the bounded Phase 3G replay scope")
    return document, cases


def validate(lines, enabled, case):
    """Reuse strict diagnostic accounting and independently replay every PV."""
    board = board_for(case["position_command"][len("position "):])
    result = validate_result(lines, enabled, board, None, None, ordering_required=True)
    summary = result["trace"]["summary"]
    if summary["stop_reason"] not in ("hard_time", "soft_time", "depth_limit", "draw", "terminal"):
        raise ValueError("Unexpected stop reason for a clock-only diagnostic")
    if (summary["hard_ms"] > case["input_clock_ms"] - 20 + .001
            or summary["hard_ms"] > case["hard_limit_ms"] + .001
            or summary["target_ms"] > summary["hard_ms"] + .001):
        raise ValueError("Search budget exceeds the available clock or fixture limit")
    return result


def run(binary, network, positions, output):
    """Run exactly 26 sequential searches, retaining errors and refusing overwrite."""
    binary, network, positions, output = (Path(p).resolve() for p in (binary, network, positions, output))
    if output.exists():
        raise ValueError("Output exists; preserve it and choose a new diagnostic attempt")
    if any("\n" in str(p) or "\r" in str(p) for p in (binary, network, positions)):
        raise ValueError("Paths must fit on a UCI line")
    document, cases = load_cases(positions)
    paths = {"engine": binary, "network": network, "positions": positions}
    for name in ("probe_clocks.py", "profile_lmr.py", "profile_search.py", "resources.py", "uci_client.py", "bench.py", "compare_bench.py"):
        paths["tools/" + name] = ROOT / "tools" / name
    assets = {name: {"path": str(p), "sha256": digest(p)} for name, p in paths.items()}
    options = {"Hash": "64", "Threads": "1", "EvalFile": str(network), "Move Overhead": "20",
               "Ponder": "false", "Time Policy": "classic", "Capture Ordering": "mvv-lva",
               "Search Diagnostics": "true"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        def record(value):
            stream.write(json.dumps(value, allow_nan=False) + "\n")
            stream.flush()
        record({"type": "metadata", "schema_version": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
                "assets": assets, "options": options, "searches": 26, "timeout_seconds": 10,
                "platform": platform.platform(), "provenance": document.get("provenance"),
                "interpretation": "Exposed diagnostics; fresh process and tables per search; no strength inference."})
        completed = 0
        sample = None
        sample_recorded = False
        try:
            for index, case in enumerate(cases):
                for enabled in (False, True):
                    sample = {"type": "result", "case_id": case["id"], "case_index": index,
                              "lmr": enabled, "status": "preparing", "position": case["position_command"],
                              "go": case["go_command"]}
                    sample_recorded = False
                    sample["resource_policy"] = resource_check(network, 64)
                    with RecordedEngine(binary) as engine:
                        sample["protocol"] = engine.events
                        engine.send("uci")
                        sample["identity"] = engine.until("uciok", timeout=30)
                        reject_errors(sample["identity"])
                        configured = dict(options, **{"Late Move Reductions": str(enabled).lower()})
                        for name, value in configured.items():
                            if not any(line.startswith(f"option name {name} type ") for line in sample["identity"]):
                                raise ValueError("Engine lacks required option " + name)
                            engine.send(f"setoption name {name} value {value}")
                        for command in ("ucinewgame", case["position_command"], "isready"):
                            engine.send(command)
                        reject_errors(engine.until("readyok", timeout=30))
                        engine.send(case["go_command"])
                        go_ns = next(e["monotonic_ns"] for e in reversed(engine.events)
                                     if e["direction"] == "to_engine" and e["line"] == case["go_command"])
                        lines = engine.until("bestmove ", timeout=10)
                        best_ns = next(e["monotonic_ns"] for e in reversed(engine.events)
                                       if e["direction"] == "from_engine" and e["line"].startswith("bestmove "))
                        sample.update(go_ns=go_ns, bestmove_ns=best_ns, output=lines,
                                      external_elapsed_ms=(best_ns-go_ns)/1e6)
                        sample["result"] = validate(lines, enabled, case)
                        summary = sample["result"]["trace"]["summary"]
                        sample.update(status="complete", internal_elapsed_ms=summary["elapsed_ms"],
                                      external_minus_internal_ms=sample["external_elapsed_ms"]-summary["elapsed_ms"],
                                      on_time=sample["external_elapsed_ms"] <= case["clock_before_ms"])
                    record(sample)
                    sample_recorded = True
                    completed += 1
            if any(digest(paths[name]) != value["sha256"] for name, value in assets.items()):
                raise ValueError("An input artifact changed during the diagnostic attempt")
            record({"type": "summary", "status": "complete", "searches": completed,
                    "finished_utc": datetime.now(timezone.utc).isoformat()})
        except BaseException as error:
            if sample is not None and not sample_recorded:
                sample.update(status="error", error=str(error))
                record(sample)
            record({"type": "summary", "status": "error", "completed_searches": completed,
                    "error": str(error), "finished_utc": datetime.now(timezone.utc).isoformat()})
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.engine, args.network, args.positions, args.output)


if __name__ == "__main__":
    main()
