#!/usr/bin/env python3
"""One bounded clock-boundary diagnostic, not a match or strength framework.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The reader timestamps complete lines before their consumer queue. These are
Python-thread observations, not kernel arrival times. Clock-ping round trips
bound the offset between Python monotonic and C++ steady-clock epochs; no shared
epoch or exact one-way transport delay is assumed. Instrumentation itself and
ordinary operating-system scheduling can affect the observations.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import threading
import time

from bench import digest
from compare_bench import physical_memory, search_signature
from profile_lmr import board_for
from profile_search import reject_errors
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
TOTAL_SECONDS, STARTUP_SECONDS, SEARCH_SECONDS = 300, 30, 10
SHUTDOWN_SECONDS = 9
CLOCKS_MS = (600, 2000)
TRACE_PREFIX = "info string clock-boundary "
PING_PREFIX = "info string clock-ping "
TRACE_FIELDS = (
    "seq", "position_begin_ns", "position_end_ns", "go_received_ns",
    "worker_started_ns", "search_started_ns", "hard_stop_ns",
    "leader_finished_ns", "joined_ns", "accounted_ns", "search_returned_ns",
    "reply_ready_ns", "bestmove_begin_ns", "bestmove_flushed_ns",
    "hard_budget_ns", "reported_time_ms",
)
SOURCES = (
    "tools/probe_clock_boundaries.py", "tests/probe_clock_boundaries_test.py",
    "tools/uci_client.py", "tools/profile_lmr.py", "tools/profile_search.py",
    "tools/compare_bench.py", "tools/bench.py", "tools/resources.py",
    "src/main.cpp", "src/search.cpp", "include/chess0live/search.hpp", "Makefile",
    "docs/experiments/clock-boundary-20261020.md",
)


def integer(value, *, signed=False):
    """Reject bools, non-ASCII digits, exponent notation and fractional stamps."""
    if not isinstance(value, str):
        raise ValueError("Timestamp fields must be ASCII integers")
    digits = value[1:] if signed and value.startswith("-") else value
    if not digits or not digits.isascii() or not digits.isdecimal():
        raise ValueError("Timestamp fields must be ASCII integers")
    return int(value)


def fields(line, prefix, expected):
    tokens = line.split()
    start = prefix.split() + ["v1"]
    if tokens[:len(start)] != start:
        raise ValueError("Unsupported clock diagnostic schema")
    values = tokens[len(start):]
    if (len(values) % 2 or len(set(values[::2])) != len(values) // 2
            or set(values[::2]) != set(expected)):
        raise ValueError("Missing, repeated, or unexpected clock fields")
    return dict(zip(values[::2], values[1::2]))


def parse_trace(line):
    result = {key: integer(value, signed=key == "hard_budget_ns")
              for key, value in fields(line, TRACE_PREFIX, TRACE_FIELDS).items()}
    order = [key for key in TRACE_FIELDS
             if key not in ("seq", "hard_stop_ns", "hard_budget_ns", "reported_time_ms")]
    if result["seq"] != 1 or any(result[key] <= 0 for key in order):
        raise ValueError("Fresh-session trace must have sequence one and positive stamps")
    if any(result[a] > result[b] for a, b in zip(order, order[1:])):
        raise ValueError("Engine clock boundaries are out of order")
    hard = result["hard_stop_ns"]
    if hard and not result["search_started_ns"] <= hard <= result["leader_finished_ns"]:
        raise ValueError("Hard-stop observation lies outside the leader search")
    return result


def parse_ping(line):
    values = fields(line, PING_PREFIX, ("id", "now_ns"))
    return {"id": integer(values["id"]), "now_ns": integer(values["now_ns"])}


def clock_offset(calibrations):
    """Intersect causal ping bounds without pretending that RTT/2 is one-way."""
    if len(calibrations) != 6 or [p["id"] for p in calibrations] != list(range(6)):
        raise ValueError("Exactly three before and three after pings are required")
    bounds = []
    previous, previous_engine = -1, -1
    for item in calibrations:
        sent, flushed, received, stamp = (item[key] for key in
            ("send_before_ns", "send_flushed_ns", "reader_received_ns", "engine_ns"))
        if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0
               for x in (sent, flushed, received, stamp)):
            raise ValueError("Calibration stamps must be positive integers")
        # A reader can receive before the sending thread records flush return.
        if sent > min(flushed, received) or sent <= previous or stamp <= previous_engine:
            raise ValueError("Ping observations are out of order")
        previous, previous_engine = received, stamp
        bounds.append((sent - stamp, received - stamp))
    low, high = max(b[0] for b in bounds), min(b[1] for b in bounds)
    if low > high:
        raise ValueError("Ping intervals have no consistent clock-epoch mapping")
    return {"host_minus_engine_low_ns": low, "host_minus_engine_high_ns": high,
            "width_ns": high - low,
            "assumption": "No material clock-rate drift over one bounded session; intervals must intersect."}


def one_event(events, direction, line=None, prefix=None):
    chosen = [event for event in events if event["direction"] == direction
              and (line is None or event.get("line") == line)
              and (prefix is None or event.get("line", "").startswith(prefix))]
    if len(chosen) != 1:
        raise ValueError("Expected exactly one recorded protocol boundary")
    return chosen[0]


def measure(trace, events, calibrations, go, clock_ms, consumed_ns):
    """Separate direct engine durations from bounded cross-clock residuals."""
    sent = one_event(events, "to_engine", line=go)
    received = one_event(events, "from_engine", prefix="bestmove ")
    start, receipt = sent["monotonic_ns"], received["monotonic_ns"]
    if not start <= receipt <= consumed_ns:
        raise ValueError("Bestmove observations are out of order")
    if trace["hard_budget_ns"] <= 0 or trace["hard_budget_ns"] > (clock_ms - 20) * 1_000_000:
        raise ValueError("Trace hard budget exceeds the transmitted clock reserve")
    if trace["reported_time_ms"] != (trace["accounted_ns"] - trace["go_received_ns"]) // 1_000_000:
        raise ValueError("Trace reported time disagrees with its accounting boundary")
    offset = clock_offset(calibrations)
    if (calibrations[2]["engine_ns"] > trace["position_begin_ns"]
            or calibrations[3]["engine_ns"] < trace["bestmove_flushed_ns"]):
        raise ValueError("Clock pings do not surround the measured search")
    low, high = (offset[key] for key in
                 ("host_minus_engine_low_ns", "host_minus_engine_high_ns"))
    if trace["go_received_ns"] + high < start:
        raise ValueError("Engine go receipt predates every feasible host-send time")
    if trace["bestmove_begin_ns"] + low > receipt:
        raise ValueError("Reader bestmove predates every feasible engine-write time")
    # If a lower bound is negative, retain it: calibration uncertainty is real,
    # and a reader can run before the engine samples its after-flush timestamp.
    def after_host(engine_stamp, host_stamp):
        return [(engine_stamp + low - host_stamp) / 1e6,
                (engine_stamp + high - host_stamp) / 1e6]
    def before_host(engine_stamp, host_stamp):
        return [(host_stamp - engine_stamp - high) / 1e6,
                (host_stamp - engine_stamp - low) / 1e6]
    def duration(a, b):
        return (trace[b] - trace[a]) / 1e6
    intervals = {
        "position_processing_ms": duration("position_begin_ns", "position_end_ns"),
        "go_to_worker_ms": duration("go_received_ns", "worker_started_ns"),
        "worker_to_search_ms": duration("worker_started_ns", "search_started_ns"),
        "search_to_leader_finish_ms": duration("search_started_ns", "leader_finished_ns"),
        "leader_to_join_ms": duration("leader_finished_ns", "joined_ns"),
        "join_to_accounted_ms": duration("joined_ns", "accounted_ns"),
        "accounted_to_search_return_ms": duration("accounted_ns", "search_returned_ns"),
        "search_return_to_reply_ready_ms": duration("search_returned_ns", "reply_ready_ns"),
        "reply_lock_wait_ms": duration("reply_ready_ns", "bestmove_begin_ns"),
        "bestmove_write_flush_ms": duration("bestmove_begin_ns", "bestmove_flushed_ns"),
        "go_to_accounted_ms": duration("go_received_ns", "accounted_ns"),
        "go_to_bestmove_flushed_ms": duration("go_received_ns", "bestmove_flushed_ns"),
    }
    deadline = trace["go_received_ns"] + trace["hard_budget_ns"]
    return {
        "clock_mapping": offset, "engine_intervals": intervals,
        "reader_elapsed_ms": (receipt - start) / 1e6,
        "consumer_elapsed_ms": (consumed_ns - start) / 1e6,
        "consumer_after_reader_ms": (consumed_ns - receipt) / 1e6,
        "reader_within_transmitted_clock": receipt - start <= clock_ms * 1_000_000,
        "go_receipt_after_send_ms_bounds": after_host(trace["go_received_ns"], start),
        "reader_after_bestmove_begin_ms_bounds": before_host(trace["bestmove_begin_ns"], receipt),
        "reader_after_bestmove_flush_ms_bounds": before_host(trace["bestmove_flushed_ns"], receipt),
        "reader_after_accounted_ms_bounds": before_host(trace["accounted_ns"], receipt),
        "hard_stop_after_deadline_ms": ((trace["hard_stop_ns"] - deadline) / 1e6
                                       if trace["hard_stop_ns"] else None),
        "accounted_after_deadline_ms": (trace["accounted_ns"] - deadline) / 1e6,
        "hard_stop_to_leader_finish_ms": (duration("hard_stop_ns", "leader_finished_ns")
                                         if trace["hard_stop_ns"] else None),
    }


def options_for(network, lmr):
    return {"Hash": "64", "Threads": "1", "EvalFile": str(network),
            "Move Overhead": "20", "Ponder": "false", "Time Policy": "classic",
            "Capture Ordering": "mvv-lva", "Search Diagnostics": "false",
            "Late Move Reductions": str(lmr).lower(), "Countermove Ordering": "false",
            "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
            "QSearch SEE Pruning": "false", "SyzygyPath": "", "SyzygyProbeLimit": "0"}


def load_cases(path):
    document = json.loads(path.read_text())
    cases = document.get("cases")
    if (document.get("schema") != "chess0live-clock-boundary-selected-cases-v1"
            or not isinstance(cases, list) or len(cases) != 2
            or {case.get("id") for case in cases} != {"late-receipt", "internal-overrun"}):
        raise ValueError("Expected exactly the two declared exposed histories")
    for case in cases:
        command = case.get("position", {}).get("line")
        if (not isinstance(command, str) or "\n" in command or "\r" in command
                or command.split()[:3] != ["position", "startpos", "moves"]):
            raise ValueError("Expected one complete startpos history command")
        board = board_for(command[len("position "):])
        if (board.fen() != case.get("fen")
                or len(command.split()) - 3 != case.get("history_plies")):
            raise ValueError("History disagrees with the selected root")
    sources = document.get("source_hashes")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Selected histories need their source evidence hashes")
    for path_string, expected in sources.items():
        source = (ROOT / path_string).resolve()
        if not source.is_relative_to(ROOT) or digest(source) != expected:
            raise ValueError("Selected source evidence changed: " + path_string)
    return document, cases


def matrix(cases):
    """Sixteen serial cells followed by four four-process groups, exactly once."""
    batches = []
    for load in ("serial", "four"):
        for clock_ms in CLOCKS_MS:
            for barrier in (False, True):
                cells = [{"case_id": case["id"], "case_index": index,
                          "clock_ms": clock_ms, "position_barrier": barrier,
                          "lmr": enabled, "load": load}
                         for index, case in enumerate(cases) for enabled in (False, True)]
                batches.extend([[cell] for cell in cells] if load == "serial" else [cells])
    return batches


def resource_check(network, workers):
    policy = dict(current_budget())
    # Keep the predeclared three-GiB floor for the four resident processes even
    # when the file-size estimate happens to be smaller on the current network.
    reservation = workers * max(768 * 1024**2,
                               64 * 1024**2 + 4 * network.stat().st_size + 128 * 1024**2)
    memory = physical_memory()
    policy.update(active_search_workers=workers, resident_engines=workers,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if (workers not in (1, 4) or workers > policy["max_cpu_workers"]
            or memory is None or reservation > memory * policy["memory_fraction"]):
        raise ValueError("Declared aggregate workload exceeds or cannot verify the local budget")
    return policy


class BoundaryEngine(Engine):
    """Own a bounded reader, including raw output after bestmove and at exit."""
    def __init__(self, *args, **kwargs):
        self.events, self.event_lock, self.reader_error = [], threading.Lock(), None
        self.read_bytes = 0
        self.cleanup = {}
        super().__init__(*args, **kwargs)

    def event(self, direction, line=None, **extra):
        item = {"monotonic_ns": time.monotonic_ns(), "direction": direction, **extra}
        if line is not None:
            item["line"] = line
        with self.event_lock:
            self.events.append(item)
        return item

    def send(self, command):
        if not isinstance(command, str) or "\n" in command or "\r" in command:
            raise ValueError("One complete UCI command per send")
        self.event("to_engine", command)
        super().send(command)
        self.event("send_flushed", command)

    def _read(self):
        try:
            for raw in self.process.stdout:
                line = raw.rstrip("\r\n")
                self.event("from_engine", line)
                self.lines.put(line)
                self.read_bytes += len(raw.encode("utf-8"))
                if self.read_bytes > 8 * 1024**2:
                    self.reader_error = "Output exceeded the declared eight-MiB session bound"
                    self.event("reader_error", error=self.reader_error)
                    self.process.kill()
                    break
        except (OSError, ValueError) as error:
            self.reader_error = str(error)
            self.event("reader_error", error=str(error))
        finally:
            self.event("eof")
            self.lines.put(None)

    def close(self):
        if self.cleanup:
            return
        self.cleanup = {"started_ns": time.monotonic_ns(), "forced_kill": False}
        try:
            if self.process.poll() is None:
                try:
                    self.send("quit")
                    self.process.wait(timeout=5)
                except (BrokenPipeError, subprocess.TimeoutExpired, OSError):
                    self.cleanup["forced_kill"] = True
                    self.process.kill()
                    self.process.wait(timeout=2)
            self.reader.join(timeout=2)
        finally:
            self.cleanup.update(exit_code=self.process.poll(), reader_alive=self.reader.is_alive(),
                                reader_error=self.reader_error, finished_ns=time.monotonic_ns())
            self.process.stdin.close()
            if not self.reader.is_alive():
                self.process.stdout.close()


def remaining(deadline, maximum):
    left = min(maximum, deadline - time.monotonic())
    if left <= 0:
        raise TimeoutError("Declared whole-diagnostic deadline expired")
    return left


def ping(engine, identifier, deadline):
    command = f"clockping {identifier}"
    engine.send(command)
    lines = engine.until(PING_PREFIX, timeout=remaining(deadline, 5))
    if len(lines) != 1:
        raise ValueError("Unexpected output around calibration ping")
    result = parse_ping(lines[0])
    if result["id"] != identifier:
        raise ValueError("Clock ping identifier mismatch")
    return {"id": identifier, "engine_ns": result["now_ns"],
            "send_before_ns": one_event(engine.events, "to_engine", line=command)["monotonic_ns"],
            "send_flushed_ns": one_event(engine.events, "send_flushed", line=command)["monotonic_ns"],
            "reader_received_ns": one_event(engine.events, "from_engine", line=lines[0])["monotonic_ns"]}


def validate_output(lines, case, trace):
    """Check standard final accounting and independently replay every full PV."""
    reject_errors(lines)
    if any("sanitizer" in line.lower() or line.startswith("FATAL") for line in lines):
        raise ValueError("Unexpected engine runtime diagnostic")
    if any(line.startswith("info string search-") for line in lines):
        raise ValueError("Search Diagnostics must remain disabled")
    if not lines or not lines[-1].startswith("bestmove ") or sum(
            line.startswith("bestmove ") for line in lines) != 1:
        raise ValueError("Exactly one bestmove must terminate normal search output")
    depth_lines = [line for line in lines if line.startswith("info depth ")]
    if depth_lines:
        signature = search_signature(lines, len(depth_lines))
    else:
        tokens = lines[-1].split()
        if len(tokens) not in (2, 4) or (len(tokens) == 4 and tokens[2] != "ponder"):
            raise ValueError("Invalid fallback bestmove")
        signature = {"iterations": [], "bestmove": tokens[1],
                     "ponder": tokens[3] if len(tokens) == 4 else None}
    board = board_for(case["position"]["line"][len("position "):])
    count = 0
    for entry in signature["iterations"]:
        pv = board.copy()
        for move in entry["pv"]:
            pv.push_uci(move)
            count += 1
    board.push_uci(signature["bestmove"])
    count += 1
    if signature["ponder"]:
        board.push_uci(signature["ponder"])
        count += 1
    totals = [line for line in lines if line.startswith("info nodes ")]
    if len(totals) != 1 or lines[-2] != totals[0]:
        raise ValueError("Expected final search totals immediately before bestmove")
    final = fields(totals[0].replace("info nodes ", "total v1 nodes ", 1),
                   "total", ("nodes", "time", "nps", "hashfull", "tbhits"))
    final = {key: integer(value) for key, value in final.items()}
    if (final["time"] != trace["reported_time_ms"] or not 0 <= final["hashfull"] <= 1000
            or final["tbhits"] != 0 or
            (signature["iterations"] and final["nodes"] < signature["iterations"][-1]["nodes"])):
        raise ValueError("Final UCI accounting disagrees with trace or disabled tablebases")
    return {"signature": signature, "final": final, "verified_legal_plies": count}


def session(binary, network, case, cell, deadline, barrier=None):
    sample = dict(cell, type="result", status="preparing", options=options_for(network, cell["lmr"]))
    engine = None
    try:
        # Reserve the worst bounded quit/kill/reader-join allowance before the
        # global deadline. Per-search watchdogs never provide free chess time.
        deadline -= SHUTDOWN_SECONDS
        startup_deadline = min(deadline, time.monotonic() + STARTUP_SECONDS)
        remaining(startup_deadline, 1)
        engine = BoundaryEngine(binary)
        sample.update(pid=engine.process.pid, protocol=engine.events)
        engine.send("uci")
        sample["identity"] = engine.until("uciok", timeout=remaining(startup_deadline, STARTUP_SECONDS))
        reject_errors(sample["identity"])
        for name, value in sample["options"].items():
            if not any(line.startswith(f"option name {name} type ") for line in sample["identity"]):
                raise ValueError("Missing required UCI option: " + name)
            engine.send(f"setoption name {name} value {value}")
        for command in ("ucinewgame", "isready"):
            engine.send(command)
        reject_errors(engine.until("readyok", timeout=remaining(startup_deadline, STARTUP_SECONDS)))
        sample["calibrations"] = [ping(engine, identifier, startup_deadline) for identifier in range(3)]
        if barrier is not None:
            sample["synchronization_enter_ns"] = time.monotonic_ns()
            barrier.wait(timeout=remaining(deadline, STARTUP_SECONDS))
            sample["synchronization_exit_ns"] = time.monotonic_ns()
        command = case["position"]["line"]
        engine.send(command)
        if cell["position_barrier"]:
            engine.send("isready")
            if engine.until("readyok", timeout=remaining(deadline, STARTUP_SECONDS)) != ["readyok"]:
                raise ValueError("Unexpected position readiness output")
        clock = cell["clock_ms"]
        sample["go"] = f"go wtime {clock} btime {clock} winc 600 binc 600"
        search_deadline = min(deadline, time.monotonic() + SEARCH_SECONDS)
        engine.send(sample["go"])
        sample["output"] = engine.until("bestmove ", timeout=remaining(search_deadline, SEARCH_SECONDS))
        sample["bestmove_consumed_ns"] = time.monotonic_ns()
        trailing = engine.until(TRACE_PREFIX, timeout=remaining(search_deadline, SEARCH_SECONDS))
        if len(trailing) != 1:
            raise ValueError("Unexpected output between bestmove and boundary trace")
        sample["trace_line"] = trailing[0]
        sample["trace"] = parse_trace(trailing[0])
        sample["calibrations"].extend(ping(engine, identifier, deadline) for identifier in range(3, 6))
        sample["validated"] = validate_output(sample["output"], case, sample["trace"])
        sample["measurements"] = measure(sample["trace"], engine.events, sample["calibrations"],
                                         sample["go"], clock, sample["bestmove_consumed_ns"])
        sample["status"] = "complete"
    except BaseException as error:
        sample.update(status="error", error=f"{type(error).__name__}: {error}")
        if barrier is not None:
            barrier.abort()
    finally:
        if engine is not None:
            try:
                engine.close()
                sample["cleanup"] = engine.cleanup
                if (engine.cleanup["forced_kill"] or engine.cleanup["exit_code"] != 0
                        or engine.cleanup["reader_alive"] or engine.cleanup["reader_error"]):
                    raise ValueError("Engine shutdown did not complete cleanly")
                eof = [event for event in engine.events if event["direction"] == "eof"]
                if len(eof) != 1:
                    raise ValueError("Missing or duplicate reader EOF")
                incoming = [event["line"] for event in engine.events if event["direction"] == "from_engine"]
                if any(line.startswith("bestmove ") for line in incoming) and sum(
                        line.startswith("bestmove ") for line in incoming) != 1:
                    raise ValueError("Duplicate bestmove, including shutdown output")
                if sum(line.startswith(TRACE_PREFIX) for line in incoming) != (sample["status"] == "complete"):
                    if sample["status"] == "complete":
                        raise ValueError("Missing or duplicate boundary trace")
                reject_errors(incoming)
                if sample["status"] == "complete":
                    # No unconsumed protocol output may disappear during close.
                    last_ping = next(i for i in range(len(incoming)-1, -1, -1)
                                     if incoming[i].startswith(PING_PREFIX))
                    if incoming[last_ping + 1:]:
                        raise ValueError("Unexpected output after final calibration")
            except BaseException as error:
                sample.update(status="error", cleanup_error=f"{type(error).__name__}: {error}")
        sample["finished_utc"] = datetime.now(timezone.utc).isoformat()
    return sample


def run(binary, network, positions, output, *, quiet_host=False):
    """Run the frozen matrix once; exclusive JSONL records survive any failure."""
    binary, network, positions, output = map(lambda p: Path(p).resolve(),
                                             (binary, network, positions, output))
    if output.exists():
        raise ValueError("Output exists; preserve every previous attempt")
    if not quiet_host:
        raise ValueError("Use --quiet-host only after other development workloads are idle")
    if any("\n" in str(path) or "\r" in str(path) for path in (binary, network, positions)):
        raise ValueError("Input paths must fit on one UCI line")
    document, cases = load_cases(positions)
    paths = {"engine": binary, "network": network, "positions": positions}
    paths.update({name: ROOT / name for name in SOURCES})
    paths.update({name: ROOT / name for name in document["source_hashes"]})
    assets = {key: {"path": str(path), "sha256": digest(path)} for key, path in paths.items()}
    if assets["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("Diagnostic requires the pinned SF19-compatible network")
    batches = matrix(cases)
    initial_policy = resource_check(network, 4)
    started = time.monotonic()
    deadline = started + TOTAL_SECONDS
    output.parent.mkdir(parents=True, exist_ok=True)
    samples = []
    with output.open("x", encoding="utf-8") as stream:
        def record(item):
            stream.write(json.dumps(item, allow_nan=False) + "\n")
            stream.flush()
        record({"type": "metadata", "schema": "chess0live-clock-boundaries-v1",
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "assets": assets, "selected_cases": document, "platform": platform.platform(),
                "quiet_host_declaration": True, "quiet_host_is_os_measurement": False,
                "resource_policy": initial_policy, "matrix": batches,
                "settings": {"searches": 32, "sessions": 32, "threads_per_engine": 1,
                             "max_active_workers": 4, "hash_mb_per_engine": 64,
                             "clocks_ms": list(CLOCKS_MS), "increment_ms": 600,
                             "repetitions": 1, "total_budget_seconds": TOTAL_SECONDS,
                             "startup_timeout_seconds": STARTUP_SECONDS,
                             "search_timeout_seconds": SEARCH_SECONDS,
                             "reserved_shutdown_seconds": SHUTDOWN_SECONDS,
                             "max_output_bytes_per_session": 8 * 1024**2},
                "observer": "Independent reader threads in the same Python process; complete-line observations, not kernel arrival.",
                "interpretation": "Exposed current-build timing diagnosis only; no historical causal reconstruction, reliability qualification, or strength inference."})
        failure = None
        try:
            for batch_index, batch in enumerate(batches):
                remaining(deadline, 1)
                policy = resource_check(network, len(batch))
                record({"type": "admission", "batch_index": batch_index, "resource_policy": policy})
                barrier = threading.Barrier(len(batch)) if len(batch) > 1 else None
                if barrier is None:
                    cell = batch[0]
                    completed = [session(binary, network, cases[cell["case_index"]], cell, deadline)]
                else:
                    futures, interrupted = [], None
                    try:
                        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                            futures = [executor.submit(session, binary, network, cases[cell["case_index"]],
                                                       cell, deadline, barrier) for cell in batch]
                            completed = [future.result() for future in futures]
                    except BaseException as error:
                        # The executor waits for bounded owned sessions. Retain
                        # their raw records even if this consumer was interrupted.
                        interrupted = error
                        barrier.abort()
                        completed = [future.result() for future in futures if future.done()]
                for sample in completed:
                    sample["batch_index"] = batch_index
                    samples.append(sample)
                    record(sample)
                if barrier is not None and interrupted is not None:
                    raise interrupted
                if any(sample["status"] != "complete" for sample in completed):
                    raise RuntimeError("Diagnostic cell failed; preserve this attempt without retry")
            remaining(deadline, 1)
        except BaseException as error:
            failure = error
        finally:
            after = {key: digest(path) if path.is_file() else None for key, path in paths.items()}
            drift = [key for key in paths if after[key] != assets[key]["sha256"]]
            if drift and failure is None:
                failure = ValueError("Input artifact drift invalidates the diagnostic")
            if time.monotonic() > deadline and failure is None:
                failure = TimeoutError("Whole diagnostic including cleanup exceeded its declared budget")
            summary = {"type": "summary", "status": "error" if failure else "complete",
                       "searches": len(samples),
                       "completed_searches": sum(sample["status"] == "complete" for sample in samples),
                       "finished_utc": datetime.now(timezone.utc).isoformat(),
                       "search_and_cleanup_elapsed_seconds": time.monotonic() - started,
                       "after_sha256": after, "artifact_drift": drift}
            if failure:
                summary["error"] = f"{type(failure).__name__}: {failure}"
            record(summary)
        if failure:
            raise failure
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--network", type=Path, required=True)
    parser.add_argument("--positions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet-host", action="store_true")
    args = parser.parse_args()
    run(args.engine, args.network, args.positions, args.output, quiet_host=args.quiet_host)


if __name__ == "__main__":
    main()
