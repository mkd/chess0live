#!/usr/bin/env python3
"""Eight exposed short-clock searches through the production match transport.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This is a loaded-host boundary diagnosis, not a match, strength test or proof
of clock reliability. No games, retries, scheduling or sleep inhibition occur.
The production RecordingProtocol timestamps remain authoritative observations;
calibrated engine flush times cannot establish kernel pipe-arrival times.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import time

from tooling import direct_entry

if __name__ == "__main__":
    direct_entry(__file__)

import chess
import chess.engine

import match
import probe_clock_boundaries as boundary

ROOT = Path(__file__).resolve().parents[1]
CLOCK_MS, INCREMENT_MS = 170, 150
TOTAL_SECONDS, CLEANUP_RESERVE = 180, 10
MAX_BYTES = 8 * 1024**2
SETTINGS = match.Settings(initial=.170, increment=.150, hash_mb=64, threads=1,
                          startup_timeout=20, protocol_timeout=3, move_overhead_ms=20)
# Independently authored, exposed development histories, never held-out games.
CASES = (
    ("initial", ()),
    ("open-game", ("e2e4", "e7e5", "g1f3", "b8c6")),
    ("queen-pawn", ("d2d4", "d7d5", "c2c4", "e7e6", "b1c3")),
    ("english", ("c2c4", "e7e5", "b1c3", "g8f6", "g1f3", "b8c6")),
)
OPTIONS = (("Time Policy", "classic"), ("Late Move Reductions", "true"),
           ("Capture Ordering", "mvv-lva"), ("SyzygyProbeLimit", "0"),
           ("SyzygyProbeDepth", "1"), *((name, "false") for name in (
               "Deep Quiet Reductions", "Countermove Ordering", "Continuation History",
               "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning",
               "ProbCut", "TT Move Hints")))
SOURCES = ("tools/probe_short_clocks.py", "tests/probe_short_clocks_test.py",
           "tools/match.py", "tools/probe_clock_boundaries.py", "tools/resources.py",
           "tools/bench.py", "tools/compare_bench.py", "tools/profile_lmr.py",
           "tools/profile_search.py", "tools/uci_client.py", "tools/match_statistics.py",
           "tools/run.py", "tools/tooling.py", "tools/python-packages.json",
           "src/main.cpp", "src/search.cpp", "include/chess0live/search.hpp",
           "docs/experiments/phase4f14-clocks.md")


def cases():
    result = []
    for identifier, moves in CASES:
        board = chess.Board()
        for move in moves:
            board.push_uci(move)
        if not board.is_valid() or board.outcome(claim_draw=True):
            raise ValueError("Diagnostic cases must be valid and nonterminal")
        line = "position startpos" + (" moves " + " ".join(moves) if moves else "")
        result.append({"id": identifier, "moves": list(moves), "fen": board.fen(),
                       "position": {"line": line}})
    return result


def matrix():
    return [[("serial", index)] for index in range(4)] + [[("four", index) for index in range(4)]]


def classify(trace, measurement, go_ns, receipt_ns):
    """Classify only boundaries proved by the whole calibration interval."""
    mapping = measurement["clock_mapping"]
    low, high = (mapping[f"host_minus_engine_{name}_ns"] for name in ("low", "high"))
    deadline = go_ns + CLOCK_MS * 1_000_000
    if receipt_ns <= deadline:
        label = "callback_on_time"
    elif trace["bestmove_flushed_ns"] + high <= deadline:
        label = "output_flushed_on_time_receipt_late"
    elif trace["bestmove_begin_ns"] + low > deadline:
        label = "engine_write_started_after_clock"
    else:
        label = "late_receipt_boundary_uncertain"
    return {"classification": label, "clock_lateness_ms": (receipt_ns - deadline) / 1e6,
            "write_begin_after_host_deadline_ms_bounds": [
                (trace["bestmove_begin_ns"] + offset - deadline) / 1e6 for offset in (low, high)],
            "flush_after_host_deadline_ms_bounds": [
                (trace["bestmove_flushed_ns"] + offset - deadline) / 1e6 for offset in (low, high)],
            "limitation": "Receipt is callback observation; transport and scheduling remain combined."}


class MemoryLog:
    """Bounded raw evidence retained in memory until this batch has no clocks.

    Production protocol serialization and timestamp placement are unchanged.
    The diagnostic stores the resulting records instead of adding timed disk IO.
    """
    def __init__(self):
        self.events, self.bytes, self.error = [], 0, None
        self.changed = asyncio.Event()
        self.failure = asyncio.get_running_loop().create_future()
        self.protocol = None

    def write(self, value):
        self.bytes += len(value.encode("utf-8"))
        if self.bytes > MAX_BYTES:
            self.error = match.PersistenceError("Diagnostic raw output exceeded eight MiB")
            if not self.failure.done():
                self.failure.set_result(self.error)
            raise self.error
        self.events.append(json.loads(value))
        self.changed.set()

    async def wait_line(self, prefix, after=0):
        async def wait():
            while True:
                if self.error:
                    raise self.error
                selected = [e for e in self.events[after:]
                            if e["direction"] == "from_engine" and e["line"].startswith(prefix)]
                if selected:
                    if len(selected) != 1:
                        raise ValueError("Duplicate diagnostic reply")
                    return selected[0]
                self.changed.clear()
                await self.changed.wait()
        return await asyncio.wait_for(wait(), 5)


class OwnedProtocol(match.RecordingProtocol):
    """Retain ownership even if production start_engine fails during setup."""
    def __init__(self, role, log):
        super().__init__(role, log)
        log.protocol = self


async def ping(protocol, log, identifier):
    command, after = f"clockping {identifier}", len(log.events)
    protocol.send_line(command)
    returned = time.monotonic_ns()
    event = await log.wait_line(boundary.PING_PREFIX, after)
    parsed = boundary.parse_ping(event["line"])
    if parsed["id"] != identifier:
        raise ValueError("Clock calibration identifier mismatch")
    sent = boundary.one_event(log.events, "to_engine", line=command)
    return {"id": identifier, "engine_ns": parsed["now_ns"],
            "send_before_ns": sent["monotonic_ns"], "send_flushed_ns": returned,
            "reader_received_ns": event["monotonic_ns"],
            "send_return_is_flush_guarantee": False}


def validate_sample(sample):
    events, case = sample["protocol"], sample["case"]
    incoming = [e["line"] for e in events if e["direction"] == "from_engine"]
    if sample["cleanup"].get("exit_code") != 0 or not sample["cleanup"].get("exited"):
        raise ValueError("Engine did not exit cleanly")
    if any(e["direction"] == "stderr" for e in events):
        raise ValueError("Unexpected engine stderr")
    boundary.reject_errors(incoming)
    for item in sample["calibrations"]:
        sent = boundary.one_event(events, "to_engine", line=f"clockping {item['id']}")
        received = boundary.one_event(events, "from_engine", line=(
            f"info string clock-ping v1 id {item['id']} now_ns {item['engine_ns']}"))
        if (sent["monotonic_ns"] != item["send_before_ns"]
                or received["monotonic_ns"] != item["reader_received_ns"]):
            raise ValueError("Calibration disagrees with raw protocol")
    trace_event = boundary.one_event(events, "from_engine", prefix=boundary.TRACE_PREFIX)
    trace = boundary.parse_trace(trace_event["line"])
    if trace["hard_budget_ns"] != 150_000_000:
        raise ValueError("Expected exactly 150 ms hard budget")
    go_event = boundary.one_event(events, "to_engine", prefix="go ")
    go = go_event["line"]
    if go != "go wtime 170 btime 170 winc 150 binc 150":
        raise ValueError("Unexpected production clock command")
    position = boundary.one_event(events, "to_engine", prefix="position ")
    if position["line"].strip() != case["position"]["line"]:
        raise ValueError("Production position differs from declared case")
    best = boundary.one_event(events, "from_engine", prefix="bestmove ")
    start_index, best_index = events.index(go_event), events.index(best)
    if best_index <= start_index or events.index(trace_event) <= best_index:
        raise ValueError("Search reply/trace order is invalid")
    lines = [e["line"] for e in events[start_index + 1:best_index + 1]
             if e["direction"] == "from_engine"]
    output = boundary.validate_output(lines, case, trace)
    measurement = boundary.measure(trace, events, sample["calibrations"], go, CLOCK_MS,
                                   sample["consumed_ns"])
    if sample["go_ns"] != go_event["monotonic_ns"] or sample["receipt_ns"] != best["monotonic_ns"]:
        raise ValueError("Production boundaries disagree with raw events")
    if sample["bestmove"] != output["signature"]["bestmove"]:
        raise ValueError("Production move disagrees with raw bestmove")
    final_ping = max(i for i, e in enumerate(events)
                     if e["direction"] == "from_engine" and e["line"].startswith(boundary.PING_PREFIX))
    if any(e["direction"] in ("from_engine", "stderr") for e in events[final_ping + 1:]):
        raise ValueError("Unexpected output after final calibration")
    return {"trace": trace, "output": output, "measurement": measurement,
            "boundary": classify(trace, measurement, sample["go_ns"], sample["receipt_ns"])}


def coverage(samples):
    expected = [(load, CASES[index][0]) for batch in matrix() for load, index in batch]
    actual = [(s["load"], s["case"]["id"]) for s in samples]
    if actual != expected or any(s.get("status") != "complete" for s in samples):
        raise ValueError("Exactly the declared eight complete cells are required")
    parallel = samples[4:]
    overlap = min(s["receipt_ns"] for s in parallel) - max(s["go_ns"] for s in parallel)
    intervals = [{"load": s["load"], "case_id": s["case"]["id"], "go_ns": s["go_ns"],
                  "receipt_ns": s["receipt_ns"]} for s in samples]
    return {"searches": 8, "four_way_overlap_ms": max(0, overlap) / 1e6,
            "actual_four_way_overlap": overlap > 0,
            "go_send_spread_ms": (max(s["go_ns"] for s in parallel)
                                  - min(s["go_ns"] for s in parallel)) / 1e6,
            "intervals": intervals}


async def session(binary, network, case, load, sample, release, arrived, width):
    log = MemoryLog()
    sample.update(case=case, load=load, status="preparing", protocol=log.events,
                  calibrations=[], started_utc=match.utc_now())
    try:
        spec = match.EngineSpec(case["id"], binary, network, extra_options=OPTIONS)
        transport, protocol, configured = await match.start_engine(spec, SETTINGS, log)
        sample.update(pid=transport.get_pid(), identity=dict(protocol.id), options=configured)
        if protocol.id.get("name") != "chess0live 0.1-dev clock-trace":
            raise ValueError("A CLOCK_TRACE=1 engine is required")
        for identifier in range(3):
            sample["calibrations"].append(await ping(protocol, log, identifier))
        arrived.append(case["id"])
        if len(arrived) == width:
            release.set()
        await release.wait()
        board = chess.Board()
        for move in case["moves"]:
            board.push_uci(move)
        limit = chess.engine.Limit(white_clock=.170, black_clock=.170, white_inc=.150, black_inc=.150)
        played = await match.timed_play(protocol, board, limit, object(), .170, SETTINGS)
        sample.update(consumed_ns=time.monotonic_ns(), go_ns=protocol.go_ns,
                      receipt_ns=protocol.bestmove_ns,
                      bestmove=played.move.uci() if played.move else None)
        await log.wait_line(boundary.TRACE_PREFIX)
        for identifier in range(3, 6):
            sample["calibrations"].append(await ping(protocol, log, identifier))
        sample["status"] = "searched"
    except BaseException as error:
        sample.update(status="error", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        protocol = log.protocol
        transport = getattr(protocol, "transport", None)
        try:
            if protocol is not None and transport is not None:
                sample["pid"] = transport.get_pid()
                try:
                    await match.close_engine(transport, protocol)
                finally:
                    # Production cleanup defers cancellation until the owned
                    # process is closed, then re-raises it. Preserve its receipt
                    # even when repeated cancellation arrives during that wait.
                    exited = protocol.returncode.done() and not protocol.returncode.cancelled()
                    sample["cleanup"] = {"exited": exited,
                                         "exit_code": protocol.returncode.result() if exited else None}
            else:
                sample["cleanup"] = {"exited": True, "exit_code": None, "process_started": False}
        finally:
            sample["finished_utc"] = match.utc_now()


async def batches(binary, network, samples, policies):
    case_list = cases()
    for batch in matrix():
        policies.append(await asyncio.to_thread(boundary.resource_check, network, len(batch)))
        release, arrived = asyncio.Event(), []
        group = [{} for _ in batch]
        samples.extend(group)
        tasks = [asyncio.create_task(session(binary, network, case_list[index], load, sample,
                                            release, arrived, len(batch)))
                 for (load, index), sample in zip(batch, group)]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        # Replay only after every process in this batch has exited.
        for sample in group:
            try:
                sample.update(validate_sample(sample), status="complete")
            except Exception as error:
                sample.update(status="error", error=f"{type(error).__name__}: {error}")
                raise


async def run(binary, network, output, *, host_load):
    if host_load != "lm-studio-running":
        raise ValueError("Explicit --host-load lm-studio-running declaration is required")
    binary, network, output = (Path(p).resolve() for p in (binary, network, output))
    if output.exists():
        raise ValueError("Output exists; preserve the previous attempt")
    if any(any(c in str(p) for c in "\r\n\0") for p in (binary, network, output)):
        raise ValueError("Paths must fit one protocol line")
    if chess.__version__ != match.SUPPORTED_CHESS_VERSION:
        raise ValueError("Pinned python-chess version is required")
    assets = {"engine": binary, "network": network, **{name: ROOT / name for name in SOURCES}}
    hashes = {name: match.sha256(path) for name, path in assets.items()}
    if hashes["network"] != boundary.NETWORK_SHA256:
        raise ValueError("Pinned SF19-compatible network required")
    admission = boundary.resource_check(network, 4)
    metadata = {"schema": "chess0live-short-clocks-v1", "started_utc": match.utc_now(),
                "host_load": host_load, "host_load_is_os_measurement": False,
                "assets": {name: {"path": str(path), "sha256": hashes[name]} for name, path in assets.items()},
                "cases": cases(), "matrix": matrix(), "resource_admission": admission,
                "settings": {**vars(SETTINGS), "searches": 8, "max_engines": 4,
                             "whole_search_cleanup_watchdog_seconds": TOTAL_SECONDS},
                "observer": "Production match.RecordingProtocol callback; in-memory raw evidence in this diagnostic.",
                "interpretation": "Loaded-host exposed timing diagnosis only; no games, rating, reliability or speed qualification.",
                "samples": [], "resource_observations": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    failure, started = None, time.monotonic()
    # start_engine's factory is specialized only in this standalone diagnostic.
    # All send, receipt, parsing, readiness and timed_play implementations remain
    # production code. Restore it even on cancellation or setup failure.
    original = match.RecordingProtocol
    with output.open("x", encoding="utf-8") as stream:
        try:
            match.RecordingProtocol = OwnedProtocol
            await asyncio.wait_for(batches(binary, network, metadata["samples"], metadata["resource_observations"]),
                                   TOTAL_SECONDS - CLEANUP_RESERVE)
            metadata["coverage"] = coverage(metadata["samples"])
        except BaseException as error:
            failure = error
            metadata["error"] = f"{type(error).__name__}: {error}"
        finally:
            match.RecordingProtocol = original
            metadata["elapsed_seconds"] = time.monotonic() - started
            after = {name: match.sha256(path) if path.is_file() else None for name, path in assets.items()}
            metadata["after_sha256"] = after
            metadata["artifact_drift"] = [name for name in hashes if hashes[name] != after[name]]
            if metadata["artifact_drift"] or metadata["elapsed_seconds"] > TOTAL_SECONDS:
                failure = failure or ValueError("Input drift or whole diagnostic deadline exceeded")
                metadata["error"] = metadata.get("error", str(failure))
            metadata.update(status="error" if failure else "complete", finished_utc=match.utc_now())
            json.dump(metadata, stream, indent=2, allow_nan=False)
            stream.write("\n")
    if failure:
        raise failure
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("network", type=Path)
    parser.add_argument("output", type=Path, help="new exclusive JSON evidence file")
    parser.add_argument("--host-load", required=True, choices=("lm-studio-running",))
    options = parser.parse_args()
    result = asyncio.run(run(options.engine, options.network, options.output, host_load=options.host_load))
    print(json.dumps({"status": result["status"], "coverage": result["coverage"],
                      "boundary_counts": {label: sum(s["boundary"]["classification"] == label for s in result["samples"])
                                          for label in sorted({s["boundary"]["classification"] for s in result["samples"]})}}, indent=2))


if __name__ == "__main__":
    main()
