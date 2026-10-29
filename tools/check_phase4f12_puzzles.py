#!/usr/bin/env python3
"""Frozen two-binary NNUE tactical comparison, with complete child-process evidence.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Dependencies are prepared automatically on direct invocation. Check mode only
configures the two roles; smoke searches every supplied position for one second.
Full mode searches each role for sixty seconds and needs a quiet-host assertion
plus the Helsinki night window or fresh owner authorization for a daytime run.
Command-line assertions record the operator's statement; they do not grant that
authorization or monitor other applications. No mode changes engine defaults.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import queue
import signal
import subprocess
import sys
import time

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess

import check_phase4f3_puzzles as prior
from bench import digest
from compare_bench import physical_memory, publish, reject_errors
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REVISIONS = {
    "baseline": "1ca87d6a596531d19b7b698b84c171fc314fc046",
    "candidate": "3ee5eff30981b73099e8a118ff1712f89cdc285a",
}
ENGINES = {role: ROOT / "build/experiments/phase4f12" / role / "chess0live" for role in SOURCE_REVISIONS}
ENGINE_MANIFESTS = {role: path.parent / "manifest.json" for role, path in ENGINES.items()}
ENGINE_SHA256S = {
    "baseline": "8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc",
    "candidate": "04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594",
}
COMPILE_FLAGS = "-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g"
NETWORK = ROOT / "networks/nn-1a298aa575a0.nnue"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
CORPUS = ROOT / "tests/data/phase4f3-puzzles.json"
OWNER_SOURCE = ROOT / "tools/batch_positions.py"
PINS = ROOT / "tests/data/phase4f12-pins.json"
THREADS, HASH_MB = 8, 64
GAP_LIMIT_SECONDS = 5.0
RECEIPT_TOLERANCE_SECONDS = .250
SEARCH_WATCHDOG_GRACE_SECONDS = 5.0
MODES = {"check": {"movetime_ms": 0, "total_seconds": 600},
         "smoke": {"movetime_ms": 1000, "total_seconds": 600},
         "full": {"movetime_ms": 60000, "total_seconds": 7200}}
BASE_OPTIONS = dict(prior.BASE_OPTIONS, **{"TT Move Hints": "false", "Continuation History": "false"})
OPTIONS = {"baseline": dict(BASE_OPTIONS),
           "candidate": dict(BASE_OPTIONS)}
OPTION_TYPES = dict(prior.OPTION_TYPES, **{"TT Move Hints": "check", "Continuation History": "check"})
ADVERTISED_DEFAULTS = dict(prior.ADVERTISED_DEFAULTS,
                          EvalFile="nn-1a298aa575a0.nnue",
                          **{"TT Move Hints": "false", "Continuation History": "false"})
SETUP_OUTPUT = ["info string Syzygy largest 0 pieces; table files are external", "readyok"]
TOOL_SOURCES = (
    "tools/check_phase4f12_puzzles.py", "tests/phase4f12_puzzles_test.py",
    "tools/audit_phase4f12_puzzles.py", "tests/audit_phase4f12_puzzles_test.py",
    "tools/check_phase4f3_puzzles.py", "tools/bench.py", "tools/compare_bench.py",
    "tools/profile_smp.py", "tools/profile_search.py", "tools/resources.py",
    "tools/uci_client.py", "tools/tooling.py", "tools/run.py",
    "tools/python-packages.json", "requirements-match.txt", "networks/manifest.json",
    "docs/experiments/phase4f12.md", "Makefile",
)


def load_positions():
    """Validate the immutable corpus against literal owner FENs without exec."""
    document = json.loads(CORPUS.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or document.get("owner_source_sha256") != digest(OWNER_SOURCE):
        raise ValueError("Puzzle corpus/source identity changed")
    positions = prior.extract_positions(OWNER_SOURCE)
    if document.get("positions") != positions:
        raise ValueError("Puzzle corpus differs from owner FENs or supplied annotations")
    return positions


def role_order(index):
    return ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")


def options_for_role(role, network):
    """Both binaries receive identical frozen playing options."""
    expected = {name: dict(prior.BASE_OPTIONS,
                           **{"TT Move Hints": "false", "Continuation History": "false"})
                for name in ("baseline", "candidate")}
    if OPTIONS != expected or role not in expected:
        raise ValueError("Unknown role or changed identical-options NNUE recipe")
    return dict(expected[role], EvalFile=str(network))


def validate_executable(role, executable):
    """Bind the role to its distinct frozen path and bytes before spawning."""
    if (set(ENGINES) != {"baseline", "candidate"}
            or set(ENGINE_SHA256S) != set(ENGINES) or role not in ENGINES
            or len({path.resolve() for path in ENGINES.values()}) != 2
            or len(set(ENGINE_SHA256S.values())) != 2):
        raise ValueError("Missing, unknown or aliased binary role")
    expected = ENGINES[role].resolve()
    if Path(executable).resolve() != expected or digest(expected) != ENGINE_SHA256S[role]:
        raise ValueError("Wrong executable path or digest for role " + role)
    return str(expected), ENGINE_SHA256S[role]


def night_window(mode, now=None, *, allow_daytime=False):
    """Reuse the civil-time cutoff, with check mode treated as a short smoke."""
    if mode not in MODES:
        raise ValueError("Mode must be check, smoke or full")
    window = prior.night_window("smoke" if mode == "check" else mode, now,
                                allow_daytime=allow_daytime)
    if mode == "check":
        window["minimum_remaining_seconds"] = 0
    return window


def resource_check(network):
    """Reserve one process, eight workers and at least 2 GiB; never a hard cap."""
    policy = dict(current_budget())
    memory = physical_memory()
    if memory is None and sys.platform == "darwin":
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True,
                                            stderr=subprocess.DEVNULL, timeout=2))
    reservation = max(2 * 1024**3, HASH_MB * 1024**2 + 4 * network.stat().st_size
                      + (64 + 128 * THREADS) * 1024**2)
    if memory is None or memory <= 0:
        raise ValueError("Cannot determine physical RAM for the eight-worker audit")
    policy.update(active_search_workers=THREADS, resident_engines=1,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if THREADS > policy["max_cpu_workers"] or reservation > memory * policy["memory_fraction"]:
        raise ValueError("Eight workers or the minimum 2-GiB reservation exceed the current resource policy")
    return policy


class Monitor:
    """Check setup, search and teardown for suspension, budget changes and cutoff."""
    def __init__(self, mode, window, network, events):
        self.start_wall = self.last_wall = time.time()
        self.start_mono = self.last_mono = time.monotonic()
        self.deadline = self.start_mono + MODES[mode]["total_seconds"]
        self.cutoff = datetime.fromisoformat(window["cutoff_utc"]).timestamp() if window["cutoff_utc"] else None
        self.network, self.events = network, events
        self.next_resource = self.start_mono
        self.max_clock_discrepancy = self.max_poll_gap = 0.0

    def check(self, force_resource=False):
        wall, mono = time.time(), time.monotonic()
        gap, wall_gap = mono - self.last_mono, wall - self.last_wall
        discrepancy = max(abs(wall_gap - gap),
                          abs((wall - self.start_wall) - (mono - self.start_mono)))
        self.max_clock_discrepancy = max(self.max_clock_discrepancy, discrepancy)
        self.max_poll_gap = max(self.max_poll_gap, gap)
        self.last_wall, self.last_mono = wall, mono
        if (discrepancy > GAP_LIMIT_SECONDS or gap > GAP_LIMIT_SECONDS or wall_gap > GAP_LIMIT_SECONDS
                or gap < 0 or wall_gap < 0):
            self.events.append(dict(event="clock_violation", wall=wall, monotonic=mono,
                                    poll_gap_seconds=gap, wall_gap_seconds=wall_gap,
                                    clock_discrepancy_seconds=discrepancy))
            raise RuntimeError("Host suspension, scheduling gap or clock discontinuity invalidated this audit")
        if mono >= self.deadline or (self.cutoff is not None and wall >= self.cutoff):
            raise TimeoutError("Audit total limit or Helsinki 07:00 cutoff reached")
        if force_resource or mono >= self.next_resource:
            event = dict(event="resource_check", wall=wall, monotonic=mono)
            self.events.append(event)
            event["policy"] = resource_check(self.network)
            self.next_resource = mono + 2.0


def log_event(raw, **fields):
    event = dict(wall=time.time(), monotonic=time.monotonic(), **fields)
    raw.write(json.dumps(event) + "\n")
    raw.flush()
    return event


def send(engine, command, raw, commands):
    commands.append(command)
    event = log_event(raw, direction=">", line=command)
    engine.send(command)
    return event


def read_until(engine, prefix, seconds, monitor, raw, received, receipt=None):
    """Capture every consumed line including EOF, keeping the monitor live."""
    deadline = min(monitor.deadline, time.monotonic() + seconds)
    while True:
        monitor.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for " + prefix)
        try:
            line = engine.lines.get(timeout=min(.25, remaining))
        except queue.Empty:
            continue
        event = log_event(raw, direction="<", line=line)
        monitor.check()
        if line is None:
            raise RuntimeError("Engine exited before " + prefix)
        engine.transcript.append(line)
        received.append(line)
        reject_errors([line])
        if line.startswith(prefix):
            if receipt is not None:
                receipt.update(event)
            return received


def validate_options(identity, options):
    """Require the frozen declarations, advertised defaults and requested ranges."""
    if set(options) != set(OPTION_TYPES):
        raise ValueError("Missing or unexpected configured option")
    for name, value in options.items():
        declarations = [line for line in identity if line.startswith("option name " + name + " type ")]
        if len(declarations) != 1:
            raise ValueError("Missing or duplicate required option: " + name)
        tokens = declarations[0].split(" type ", 1)[1].split()
        kind = OPTION_TYPES[name]
        if not tokens or tokens[0] != kind:
            raise ValueError("Wrong type for required option: " + name)
        if name in ADVERTISED_DEFAULTS and ("default" not in tokens
                or tokens[tokens.index("default") + 1] != ADVERTISED_DEFAULTS[name]):
            raise ValueError("Advertised default differs from the frozen current recipe: " + name)
        if kind == "spin" and not int(tokens[tokens.index("min") + 1]) <= int(value) <= int(tokens[tokens.index("max") + 1]):
            raise ValueError("Requested value outside engine range: " + name)
        if kind == "combo" and (" var " + value) not in declarations[0]:
            raise ValueError("Missing requested option choice: " + name)


def validate_identity(identity, options):
    validate_options(identity, options)
    fixed = ["id name chess0live 0.1-dev", "id author Claudio M. Camacho",
             "option name Clear Hash type button", "uciok"]
    if identity[-1:] != ["uciok"] or any(identity.count(line) != 1 for line in fixed):
        raise ValueError("Malformed frozen engine identity or UCI terminator")
    declarations = [line for line in identity if line.startswith("option name ")]
    if len(identity) != len(options) + len(fixed) or len(declarations) != len(options) + 1:
        raise ValueError("Unexpected identity output or option declaration")


def validate_result(lines, fen, supplied_mate):
    """The historical independent-referee parser already checks every legal PV."""
    return prior.validate_result(lines, fen, supplied_mate)


def validate_search_timing(sample, movetime_ms):
    prior.validate_search_timing(sample, movetime_ms)


def finish_session(engine, sample, raw):
    """Drain EOF after a bounded exit; reject late output and abnormal teardown."""
    if engine.process.poll() is None:
        try:
            send(engine, "quit", raw, sample["commands"])
            engine.process.wait(timeout=2)
        except BaseException as error:
            sample["shutdown_error"] = type(error).__name__ + ": " + str(error)
    # A broken input pipe does not establish that the child has exited. Await
    # termination even when sending quit failed, before draining the reader.
    if engine.process.poll() is None:
        log_event(raw, event="process_kill", pid=engine.process.pid, reason="failed shutdown")
        try:
            engine.process.kill()
            engine.process.wait(timeout=2)
        except BaseException as error:
            sample["shutdown_error"] = type(error).__name__ + ": " + str(error)
    try:
        engine.close()
    except BaseException as error:
        sample["shutdown_error"] = type(error).__name__ + ": " + str(error)
    trailing, eof_count, after_eof = [], 0, False
    while True:
        try:
            line = engine.lines.get_nowait()
        except queue.Empty:
            break
        log_event(raw, direction="<", line=line)
        if line is None:
            eof_count += 1
        else:
            after_eof |= eof_count > 0
            trailing.append(line)
            engine.transcript.append(line)
    sample.update(shutdown_output=trailing, shutdown_eof_count=eof_count,
                  exit_code=engine.process.poll(), reader_alive=engine.reader.is_alive(),
                  received_transcript=list(engine.transcript))
    log_event(raw, event="process_exit", pid=engine.process.pid, exit_code=sample["exit_code"],
              reader_alive=sample["reader_alive"], shutdown_eof_count=eof_count)
    if (sample.get("shutdown_error") or sample["exit_code"] != 0 or sample["reader_alive"]
            or eof_count != 1 or after_eof or trailing):
        raise ValueError("Unclean engine exit, reader, EOF or shutdown output")


def run_case(sample, position, network, executable, output, mode, monitor):
    """One fresh process per role/position; check mode never sends a search."""
    engine = None
    raw_path = output / sample["raw_log"]
    sample.update(commands=[], identity=[], setup_output=[], preparation_output=[],
                  output=[], post_search_output=[], status="preparing")
    try:
        with raw_path.open("x", encoding="utf-8") as raw:
            try:
                options = options_for_role(sample["role"], network)
                sample["options"] = options
                path, sha256 = validate_executable(sample["role"], executable)
                if sample.get("executable") != path or sample.get("executable_sha256") != sha256:
                    raise ValueError("Sample executable identity differs from its role")
                monitor.check(force_resource=True)
                engine = Engine(executable, cwd=ROOT)
                sample["pid"] = engine.process.pid
                log_event(raw, event="process_start", pid=engine.process.pid,
                          executable=path, executable_sha256=sha256)
                send(engine, "uci", raw, sample["commands"])
                read_until(engine, "uciok", 20, monitor, raw, sample["identity"])
                validate_identity(sample["identity"], options)
                for name, value in options.items():
                    send(engine, "setoption name " + name + " value " + value, raw, sample["commands"])
                send(engine, "isready", raw, sample["commands"])
                read_until(engine, "readyok", 30, monitor, raw, sample["setup_output"])
                if sample["setup_output"] != SETUP_OUTPUT:
                    raise ValueError("Unexpected setup readiness output")
                send(engine, "ucinewgame", raw, sample["commands"])
                if mode != "check":
                    send(engine, "position fen " + position["fen"], raw, sample["commands"])
                send(engine, "isready", raw, sample["commands"])
                read_until(engine, "readyok", 10, monitor, raw, sample["preparation_output"])
                if sample["preparation_output"] != ["readyok"]:
                    raise ValueError("Unexpected preparation readiness output")
                if mode != "check":
                    monitor.check(force_resource=True)
                    sample["status"] = "searching"
                    movetime = MODES[mode]["movetime_ms"]
                    start = send(engine, f"go movetime {movetime}", raw, sample["commands"])
                    sample.update(search_started_wall=start["wall"], search_started_monotonic=start["monotonic"])
                    receipt = {}
                    read_until(engine, "bestmove ", movetime / 1000 + SEARCH_WATCHDOG_GRACE_SECONDS,
                               monitor, raw, sample["output"], receipt)
                    sample.update(bestmove_received_wall=receipt["wall"], bestmove_received_monotonic=receipt["monotonic"],
                                  elapsed_seconds=receipt["monotonic"] - start["monotonic"],
                                  wall_elapsed_seconds=receipt["wall"] - start["wall"])
                    sample["result"] = validate_result(sample["output"], position["fen"], position["supplied_mate"])
                    validate_search_timing(sample, movetime)
                    send(engine, "isready", raw, sample["commands"])
                    read_until(engine, "readyok", 5, monitor, raw, sample["post_search_output"])
                    if sample["post_search_output"] != ["readyok"]:
                        raise ValueError("Unexpected output after bestmove")
                monitor.check(force_resource=True)
                sample["status"] = "validated"
            except BaseException as error:
                sample.update(status="failed", error=type(error).__name__ + ": " + str(error))
                if engine is not None and engine.process.poll() is None:
                    log_event(raw, event="process_kill", pid=engine.process.pid, reason="failed case")
                    engine.process.kill()
                    engine.process.wait(timeout=2)
                raise
            finally:
                if engine is not None:
                    try:
                        finish_session(engine, sample, raw)
                    except BaseException as error:
                        completed = sample["status"] == "validated"
                        sample.update(status="failed", shutdown_error=type(error).__name__ + ": " + str(error),
                                      exit_code=engine.process.poll(), received_transcript=list(engine.transcript))
                        if completed:
                            raise
                sample["finished_utc"] = datetime.now(timezone.utc).isoformat()
                try:
                    monitor.check()
                except BaseException as error:
                    sample.update(status="failed", monitor_error=type(error).__name__ + ": " + str(error))
                    raise
                if sample["status"] == "validated":
                    sample["status"] = "complete"
    finally:
        if raw_path.exists():
            sample["raw_sha256"] = digest(raw_path)


def summarize(samples, positions, mode="smoke"):
    lookup = {(sample["position_id"], sample["role"]): sample for sample in samples}
    expected = ({(None, role) for role in OPTIONS} if mode == "check" else
                {(position["id"], role) for position in positions for role in OPTIONS})
    if len(lookup) != len(samples) or set(lookup) != expected or any(item["status"] != "complete" for item in samples):
        raise ValueError("Audit lacks the complete paired matrix")
    if mode == "check":
        return dict(positions=len(positions), sessions=len(samples), searches=0,
                    interpretation="Search-free identity, configuration and teardown readiness only.")
    counts = {role: {field: sum(bool(lookup[position["id"], role]["result"][field]) for position in positions)
                    for field in ("reported_positive_mate", "reported_mate_matches_supplied", "final_pv_ends_in_checkmate")}
              for role in OPTIONS}
    pairs = [(position["id"], lookup[position["id"], "baseline"]["result"],
              lookup[position["id"], "candidate"]["result"]) for position in positions]
    return dict(positions=len(positions), sessions=len(samples), searches=len(samples), roles=counts,
                same_bestmove=sum(off["bestmove"] == on["bestmove"] for _, off, on in pairs),
                positive_mate_report_gains=[key for key, off, on in pairs if on["reported_positive_mate"] and not off["reported_positive_mate"]],
                positive_mate_report_losses=[key for key, off, on in pairs if off["reported_positive_mate"] and not on["reported_positive_mate"]],
                interpretation="Exposed, nondeterministic SMP puzzle observations only. Different scores and moves are allowed. Mate annotations, legal PVs, centipawns, depth and node counts do not prove playing strength or forced mate correctness.")


def asset_paths():
    """Verify both complete copied build histories; never use live source substitutes."""
    sources = {name: ROOT / name for name in TOOL_SOURCES}
    if set(ENGINE_MANIFESTS) != set(SOURCE_REVISIONS):
        raise ValueError("Missing or unknown role manifest")
    for role in SOURCE_REVISIONS:
        validate_executable(role, ENGINES[role])
        directory = ENGINES[role].parent
        manifest_path = ENGINE_MANIFESTS[role]
        if manifest_path.resolve() != (directory / "manifest.json").resolve():
            raise ValueError("Manifest path differs from its binary role")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frozen_sources = manifest.get("source_sha256")
        if (manifest.get("schema_version") != 1 or manifest.get("role") != role
                or manifest.get("engine_source_revision") != SOURCE_REVISIONS[role]
                or manifest.get("binary_sha256") != ENGINE_SHA256S[role]
                or manifest.get("network_sha256") != NETWORK_SHA256
                or manifest.get("compile_flags") != COMPILE_FLAGS
                or not isinstance(frozen_sources, dict) or not frozen_sources):
            raise ValueError("Frozen engine build manifest identity mismatch: " + role)
        for field, filename in (("origin_manifest", "origin-manifest.json"), ("build_log", "build.log")):
            name = manifest.get(field)
            expected_path = directory / filename
            if (not isinstance(name, str) or not name or Path(name).is_absolute()
                    or ".." in Path(name).parts or name in sources
                    or (ROOT / name).resolve() != expected_path.resolve()
                    or expected_path.resolve().parent != directory.resolve()
                    or digest(expected_path) != manifest.get(field + "_sha256")):
                raise ValueError("Invalid or changed " + field + " for " + role)
            sources[name] = expected_path
        origin = json.loads((directory / "origin-manifest.json").read_text(encoding="utf-8"))
        if role == "baseline":
            original_sources = origin.get("sources")
            binary = origin.get("binary", {})
            valid_origin = (origin.get("parent_commit") == SOURCE_REVISIONS[role]
                            and isinstance(binary, dict) and binary.get("sha256") == ENGINE_SHA256S[role]
                            and binary.get("flags") == COMPILE_FLAGS
                            and origin.get("network_sha256") == NETWORK_SHA256)
        else:
            original_sources = origin.get("source_sha256")
            oracle = origin.get("oracle_report_sha256")
            valid_origin = (origin.get("candidate_sha256") == ENGINE_SHA256S[role]
                            and origin.get("baseline_sha256") == ENGINE_SHA256S["baseline"]
                            and isinstance(oracle, str) and len(oracle) == 64
                            and all(c in "0123456789abcdef" for c in oracle))
        if not valid_origin or not isinstance(original_sources, dict) or not original_sources:
            raise ValueError("Original build provenance does not identify its role")
        normalized = {}
        for name, expected in original_sources.items():
            if (not isinstance(name, str) or not name or Path(name).is_absolute()
                    or ".." in Path(name).parts):
                raise ValueError("Unsafe original source name")
            copied = directory / "source" / name
            key = str(copied.relative_to(ROOT))
            if (key in normalized or key in sources
                    or not copied.resolve().is_relative_to(directory.resolve() / "source")
                    or digest(copied) != expected):
                raise ValueError("Invalid or changed frozen build source: " + name)
            normalized[key] = expected
            sources[key] = copied
        if frozen_sources != normalized:
            raise ValueError("Frozen source map differs from complete original build map")
        sources["engine_" + role] = ENGINES[role]
        sources["manifest_" + role] = manifest_path
    return dict(sources, network=NETWORK, corpus=CORPUS, owner_source=OWNER_SOURCE, pins=PINS)


def validate_prepared_pins(frozen):
    """Require the pre-run preparation map, excluding only its own recursive hash."""
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    expected = {name: item["sha256"] for name, item in frozen.items() if name != "pins"}
    if (pins.get("schema_version") != 1 or pins.get("engine_source_revisions") != SOURCE_REVISIONS
            or pins.get("assets") != expected):
        raise ValueError("Prepared Phase 4F.12 input pins differ; do not replace evidence or silently refreeze")


def verify_assets(assets, frozen):
    after = {name: digest(path) for name, path in assets.items()}
    if any(after[name] != frozen[name]["sha256"] for name in assets):
        raise ValueError("A pinned input, tool or owner source changed during the audit")
    return after


def audit(mode, output, *, allow_daytime=False, quiet_host=False):
    """Run one finite attempt, retaining incomplete/failed cases without retries."""
    for role in role_order(0):
        options_for_role(role, NETWORK)
    if mode not in MODES:
        raise ValueError("Mode must be check, smoke or full")
    if type(allow_daytime) is not bool or (allow_daytime and mode != "full"):
        raise ValueError("--allow-daytime is a boolean full-audit option only")
    if type(quiet_host) is not bool or (mode == "full" and not quiet_host):
        raise ValueError("Full comparison requires --quiet-host after an agreed quiet window")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Output already exists; preserve it and choose a fresh directory")
    paths = asset_paths()
    if any(any(ord(c) < 32 for c in str(path)) for path in paths.values()):
        raise ValueError("Asset paths must fit on one UCI line")
    if chess.__version__ != "1.11.2":
        raise ValueError("Pinned chess 1.11.2 is required; use the automatic direct launcher")
    positions = load_positions()
    frozen = {name: dict(path=str(path.resolve()), sha256=digest(path)) for name, path in paths.items()}
    if (any(frozen["engine_" + role]["sha256"] != ENGINE_SHA256S[role] for role in SOURCE_REVISIONS)
            or frozen["network"]["sha256"] != NETWORK_SHA256):
        raise ValueError("Frozen Phase 4F.12 engine or pinned network identity mismatch")
    validate_prepared_pins(frozen)
    window = night_window(mode, allow_daytime=allow_daytime)
    initial_policy = resource_check(NETWORK)
    report = dict(schema_version=1, protocol="phase4f12-nnue-puzzles-v1", status="running", mode=mode,
                  engine_source_revisions=dict(SOURCE_REVISIONS), assets=frozen, allow_daytime=allow_daytime,
                  quiet_host=quiet_host,
                  authorization_note="Flags record operator assertions, not verified approval or telemetry. Daytime full runs require fresh owner authorization; quiet_host asserts agreed paused competing inference/builds, unchanged power mode and AC power.",
                  started_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
                  chess_version=chess.__version__, positions=positions, settings=dict(MODES[mode]),
                  options={role: options_for_role(role, NETWORK) for role in OPTIONS},
                  launch_window=window, initial_resource_policy=initial_policy, samples=[], monitor_events=[],
                  receipt_tolerance_seconds=RECEIPT_TOLERANCE_SECONDS,
                  search_watchdog_grace_seconds=SEARCH_WATCHDOG_GRACE_SECONDS,
                  clock_gap_limit_seconds=GAP_LIMIT_SECONDS,
                  timing_note="Serial fresh processes; alternating role order. Go and bestmove times are main-loop send/queue-receipt timestamps, not reader-thread arrival times. Setup is excluded; 250-ms tolerance is distinct from the five-second watchdog. Early completion is allowed. Worker counts and memory reservations are estimates, not measured utilization caps.")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "report.json"
    publish(target, report)
    monitor = Monitor(mode, window, NETWORK, report["monitor_events"])
    try:
        cases = ([(None, None, role) for role in role_order(0)] if mode == "check" else
                 [(index, position, role) for index, position in enumerate(positions) for role in role_order(index)])
        for index, position, role in cases:
            monitor.check(force_resource=True)
            verify_assets(paths, frozen)
            key = position["id"] if position is not None else "readiness"
            sample = dict(position_index=index, position_id=position["id"] if position else None,
                          role=role, status="preparing", raw_log=f"{key}-{role}.uci.jsonl",
                          executable=str(ENGINES[role].resolve()), executable_sha256=ENGINE_SHA256S[role])
            report["samples"].append(sample)
            publish(target, report)
            label = f"{index + 1:02d}/{len(positions)}" if index is not None else "readiness"
            print(f"{label} {role}: {'configuring without search' if mode == 'check' else 'searching ' + str(MODES[mode]['movetime_ms'] // 1000) + 's'}", flush=True)
            run_case(sample, position, NETWORK, ENGINES[role], output, mode, monitor)
            if mode != "check":
                result = sample["result"]
                display = f"M{result['reported_mate']}" if result["reported_mate"] is not None else f"cp {result['score_cp']:+d}"
                print(f"{label} {role}: {display}, best {result['bestmove']}, depth {result['completed_depth']}", flush=True)
            publish(target, report)
        report["after_sha256"] = verify_assets(paths, frozen)
        report["summary"] = summarize(report["samples"], positions, mode)
        monitor.check(force_resource=True)
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      max_clock_discrepancy_seconds=monitor.max_clock_discrepancy,
                      max_poll_gap_seconds=monitor.max_poll_gap)
        if "after_sha256" not in report:
            report["after_sha256"] = {}
            for name, path in paths.items():
                try:
                    report["after_sha256"][name] = digest(path)
                except OSError:
                    report["after_sha256"][name] = None
        publish(target, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="check")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-daytime", action="store_true",
                        help="Full only: fresh owner authorization required; resource limits and the next 07:00 cutoff still apply.")
    parser.add_argument("--quiet-host", action="store_true",
                        help="Assert the agreed quiet window: paused competing inference/builds, unchanged power mode and AC power. Required for full.")
    args = parser.parse_args(argv)
    audit(args.mode, args.output, allow_daytime=args.allow_daytime, quiet_host=args.quiet_host)
    return 0


if __name__ == "__main__":
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except (KeyboardInterrupt, OSError, ValueError, RuntimeError, TimeoutError) as error:
        sys.exit(f"Puzzle audit stopped: {error}")
