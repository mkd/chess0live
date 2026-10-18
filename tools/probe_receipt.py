#!/usr/bin/env python3
"""Bounded controls separating consumer delay from observed engine response time.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

POSIX diagnostic tooling only. The reader is a thread in this process, not a
kernel timestamp or independent observer. No match adjudication uses this tool.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import time

from bench import digest
from probe_clocks import RecordedEngine
from profile_lmr import board_for, validate_result
from profile_search import reject_errors, resource_check

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("control", "consumer-sleep", "engine-pause")
GO = "go movetime 620"


def wait_until(deadline_ns):
    """Sleep to a monotonic target; report observations rather than exact timing."""
    time.sleep(max(0, deadline_ns - time.monotonic_ns()) / 1e9)


def pause_process(process, duration_seconds=0.5, observations=None):
    """Resume this owned child even if the diagnostic sleep is interrupted.

    Signal-request timestamps do not prove when the kernel stopped the process.
    SIGCONT is harmless if the process was not stopped; no unrelated PID is used.
    """
    observations = {} if observations is None else observations
    observations.update(stop_request_ns=time.monotonic_ns(),
                        requested_pause_ms=duration_seconds * 1000)
    try:
        process.send_signal(signal.SIGSTOP)
        time.sleep(duration_seconds)
    finally:
        if process.poll() is None:
            observations["resume_request_ns"] = time.monotonic_ns()
            process.send_signal(signal.SIGCONT)
        else:
            observations["process_exited_before_resume"] = True
        observations["resume_return_ns"] = time.monotonic_ns()
    return observations


def measure(lines, events, consumed_ns, enabled):
    """Compare three elapsed observations while checking every returned PV."""
    result = validate_result(lines, enabled, board_for("startpos"), None, None,
                             ordering_required=True)
    summary = result["trace"]["summary"]
    if summary["hard_ms"] != 600 or summary["soft_ms"] != 600:
        raise ValueError("Unexpected explicit movetime budget")
    outgoing = [e for e in events if e["direction"] == "to_engine" and e["line"] == GO]
    incoming = [e for e in events if e["direction"] == "from_engine" and e["line"].startswith("bestmove ")]
    if len(outgoing) != 1 or len(incoming) != 1:
        raise ValueError("Expected exactly one go and bestmove observation")
    if incoming[0]["line"] != lines[-1]:
        raise ValueError("Timestamped bestmove disagrees with validated output")
    start, receipt = outgoing[0]["monotonic_ns"], incoming[0]["monotonic_ns"]
    if not start <= receipt <= consumed_ns:
        raise ValueError("Receipt and consumption timestamps are out of order")
    reader_ms, consumer_ms = (receipt-start)/1e6, (consumed_ns-start)/1e6
    return {"result": result, "reader_elapsed_ms": reader_ms,
            "consumer_elapsed_ms": consumer_ms, "internal_elapsed_ms": summary["elapsed_ms"],
            "reader_minus_internal_ms": reader_ms-summary["elapsed_ms"],
            "consumer_minus_reader_ms": (consumed_ns-receipt)/1e6,
            "reader_within_movetime": reader_ms <= 620,
            "consumer_within_movetime": consumer_ms <= 620}


def run(binary, network, output):
    """Run a fixed twelve-search matrix once, recording errors without resumption."""
    binary, network, output = (Path(p).resolve() for p in (binary, network, output))
    if output.exists():
        raise ValueError("Output exists; preserve the prior attempt")
    if os.name != "posix" or not hasattr(signal, "SIGSTOP"):
        raise ValueError("The engine-pause control requires POSIX signals")
    if any("\n" in str(p) or "\r" in str(p) for p in (binary, network)):
        raise ValueError("Asset paths must fit on one UCI line")
    paths = {"engine": binary, "network": network}
    for name in ("probe_receipt.py", "probe_clocks.py", "profile_lmr.py", "profile_search.py",
                 "resources.py", "uci_client.py", "bench.py", "compare_bench.py"):
        paths["tools/" + name] = ROOT / "tools" / name
    assets = {key: {"path": str(path), "sha256": digest(path)} for key, path in paths.items()}
    options = {"Hash": "64", "Threads": "1", "EvalFile": str(network), "Move Overhead": "20",
               "Ponder": "false", "Time Policy": "classic", "Capture Ordering": "mvv-lva",
               "Search Diagnostics": "true"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        def record(value):
            stream.write(json.dumps(value, allow_nan=False) + "\n")
            stream.flush()
        record({"type": "metadata", "schema_version": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
                "assets": assets, "platform": platform.platform(), "options": options,
                "position": "startpos", "go": GO, "searches": 12,
                "interpretation": "Exposed latency controls; no historical causality or strength inference.",
                "observer": "Reader thread and consumer in one Python process; neither is kernel arrival.",
                "residual": "Reader minus internal elapsed combines request transport, post-search/output and reader delay."})
        completed, sample, saved = 0, None, False
        try:
            for repeat in range(2):
                for enabled in (False, True):
                    for scenario in SCENARIOS:
                        sample = {"type": "result", "repeat": repeat, "lmr": enabled,
                                  "scenario": scenario, "status": "preparing"}
                        saved = False
                        sample["resource_policy"] = resource_check(network, 64)
                        with RecordedEngine(binary) as engine:
                            sample["protocol"] = engine.events
                            engine.send("uci")
                            sample["identity"] = engine.until("uciok", timeout=30)
                            reject_errors(sample["identity"])
                            for name, value in dict(options, **{"Late Move Reductions": str(enabled).lower()}).items():
                                if not any(line.startswith(f"option name {name} type ") for line in sample["identity"]):
                                    raise ValueError("Engine lacks required option " + name)
                                engine.send(f"setoption name {name} value {value}")
                            for command in ("ucinewgame", "position startpos", "isready"):
                                engine.send(command)
                            reject_errors(engine.until("readyok", timeout=30))
                            engine.send(GO)
                            # Find the outgoing event explicitly: the reader may
                            # append an info line immediately after send returns.
                            go_ns = next(e["monotonic_ns"] for e in reversed(engine.events)
                                         if e["direction"] == "to_engine" and e["line"] == GO)
                            if scenario == "consumer-sleep":
                                sample["consumer_wait_target_ns"] = go_ns + 900_000_000
                                wait_until(sample["consumer_wait_target_ns"])
                            elif scenario == "engine-pause":
                                wait_until(go_ns + 400_000_000)
                                if any(e["direction"] == "from_engine" and e["line"].startswith("bestmove ")
                                       for e in engine.events):
                                    raise RuntimeError("Engine finished before the planned pause; retain this attempt")
                                sample["pause"] = {}
                                pause_process(engine.process, observations=sample["pause"])
                            lines = engine.until("bestmove ", timeout=5)
                            consumed = time.monotonic_ns()
                            sample.update(output=lines, consumed_ns=consumed)
                            sample.update(measure(lines, engine.events, consumed, enabled))
                            sample["status"] = "complete"
                        record(sample)
                        saved = True
                        completed += 1
            if any(digest(paths[key]) != asset["sha256"] for key, asset in assets.items()):
                raise ValueError("An input artifact changed during the attempt")
            record({"type": "summary", "status": "complete", "searches": completed,
                    "finished_utc": datetime.now(timezone.utc).isoformat()})
        except BaseException as error:
            if sample is not None and not saved:
                sample.update(status="error", error=str(error))
                record(sample)
            record({"type": "summary", "status": "error", "completed_searches": completed,
                    "error": str(error), "finished_utc": datetime.now(timezone.utc).isoformat()})
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.engine, args.network, args.output)


if __name__ == "__main__":
    main()
