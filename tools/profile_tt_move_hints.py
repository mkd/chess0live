#!/usr/bin/env python3
"""Finite Phase 4F.6 work/correctness screen; elapsed times are not speed evidence.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

All fifteen exposed roots, two repetitions and immediate cold/warm searches
compare a frozen parent with candidate hints off/on. One fresh process serves
each role/root/repetition. Instrumentation stays on for every role. Direct
invocation bootstraps the pinned independent Python chess referee.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import queue
import re
import subprocess
import time

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

from bench import digest
from profile_cache import board_for, cache_record, publish
from profile_countermove import validate_result as validate_uci
from profile_search import diagnostics
from profile_search_package import (BASE_OPTIONS, CORPUS, NETWORK, PINNED_NETWORK,
                                    Monitor, diagnostic_record, load_positions,
                                    log, resource_check, send, validate_options)
from compare_bench import reject_errors
from profile_smp import unsigned
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4f6.md"
PROTOCOL_SHA256 = "82cf11bb1b1e37336083038d53e8eb46e9f130cdc4c85b149f9727aca3a4809c"
PARENT_SHA256 = "9c89933b9000bba3b5a77d8981d7fcf7094987e2a45d624e65ec9bc6ed3987d2"
CORPUS_SHA256 = "afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f"
DEPTH, REPETITIONS, HASH_MB = 6, 2, 64
ROLES = ("parent", "off", "on")
SEARCH_TIMEOUT = 10.0
HINT_FIELDS = {"enabled", "slots", "allocated_bytes", "probes", "hits", "legal_matches", "stores"}
SOURCES = ("tools/profile_tt_move_hints.py", "tests/profile_tt_move_hints_test.py",
           "tools/profile_search_package.py", "tools/profile_countermove.py", "tools/profile_cache.py",
           "tools/profile_smp.py", "tools/profile_search.py", "tools/compare_bench.py", "tools/bench.py",
           "tools/resources.py", "tools/uci_client.py", "tools/tooling.py", "tools/run.py",
           "tools/python-packages.json", "requirements-match.txt", "networks/manifest.json", "Makefile")


def options_for(role, network):
    if role not in ROLES:
        raise ValueError("Unknown move-hint comparison role")
    options = dict(BASE_OPTIONS, EvalFile=str(network))
    if role != "parent":
        options["TT Move Hints"] = "true" if role == "on" else "false"
    return options


def run_order(index, repetition):
    offset = index % len(ROLES)
    order = ROLES[offset:] + ROLES[:offset]
    return order if repetition % 2 == 0 else order[::-1]


def hint_record(line):
    tokens = line.split()
    if tokens[:4] != ["info", "string", "move-hints", "v1"] or len(tokens) != 4 + 2 * len(HINT_FIELDS):
        raise ValueError("Malformed move-hint diagnostic schema")
    fields = dict(zip(tokens[4::2], tokens[5::2]))
    if set(fields) != HINT_FIELDS or fields["enabled"] != "true":
        raise ValueError("Missing, duplicate or disabled move-hint fields")
    return {key: True if key == "enabled" else unsigned(value, key) for key, value in fields.items()}


def validate_result(lines, board, role):
    """Replay every PV and verify deterministic single-worker accounting."""
    records, ordinary = {}, []
    summary_seen = best_seen = False
    for line in lines:
        if best_seen:
            raise ValueError("Unexpected output after bestmove")
        if line.startswith("info string "):
            if summary_seen:
                raise ValueError("Diagnostic output after search summary")
            if line.startswith("info string move-hints "):
                name, fields = "move-hints", hint_record(line)
            else:
                name, fields = diagnostic_record(line)
            if name != "search-iteration":
                if name in records:
                    raise ValueError("Duplicate diagnostic record")
                records[name] = fields
                summary_seen = name == "search-summary"
        else:
            if line.startswith("bestmove "):
                if not summary_seen:
                    raise ValueError("Bestmove precedes final diagnostics")
                best_seen = True
            elif summary_seen:
                raise ValueError("Ordinary output after search summary")
            tokens = line.split()
            if tokens[:2] == ["info", "depth"]:
                if (len(tokens) < 20 or [tokens[j] for j in (0, 1, 3, 5, 8, 10, 12, 14, 16, 18)]
                        != ["info", "depth", "seldepth", "score", "nodes", "time", "nps", "hashfull", "tbhits", "pv"]):
                    raise ValueError("Malformed completed UCI iteration")
            ordinary.append(line)
    expected = {"cache", "ordering", "lmr", "search-summary"}
    if role == "on":
        expected.add("move-hints")
    if role not in ROLES or set(records) != expected:
        raise ValueError("Missing or unexpected configured diagnostic record")
    result = validate_uci(ordinary, board, "depth", DEPTH)
    trace = diagnostics(lines, "classic")
    summary = trace["summary"]
    if (summary["stop_reason"] != "depth_limit" or summary["completed_depth"] != DEPTH
            or len(trace["iterations"]) != DEPTH or trace["aborted_nodes"] != 0
            or any(not item["completed"] for item in trace["iterations"])
            or result["unfinished_nodes"] != 0 or result["reported_nodes"] <= 0
            or result["reported_nodes"] != summary["nodes"]):
        raise ValueError("Fixed-depth search did not finish with complete accounting")
    if any(summary[key] != 0 for key in ("soft_ms", "hard_ms", "target_ms", "predicted_next_ms")):
        raise ValueError("A depth-only search unexpectedly used a clock budget")
    cache = records["cache"] = cache_record(lines, HASH_MB)
    if cache["entry_bytes"] != 16 or cache["bucket_bytes"] != 64:
        raise ValueError("Score-table entry or bucket geometry changed")
    if records["ordering"] != dict(policy="mvv-lva", see_calls=0, losing_captures=0):
        raise ValueError("Capture ordering differs from the frozen default")
    lmr = records["lmr"]
    if (not lmr["enabled"] or lmr["researches"] > lmr["reductions"]
            or lmr["fail_lows"] + lmr["verified_cutoffs"] > lmr["researches"]):
        raise ValueError("Invalid LMR work accounting")
    if role == "on":
        hints = records["move-hints"]
        if (hints["slots"] != cache["buckets"] or hints["slots"] <= 0
                or hints["allocated_bytes"] != hints["slots"] * 16
                or hints["allocated_bytes"] + cache["allocated_bytes"] > HASH_MB * 1024**2
                or hints["legal_matches"] > hints["hits"] or hints["hits"] > hints["probes"]):
            raise ValueError("Invalid move-hint capacity or counter accounting")
    result.update(diagnostics=records, leader_iterations=trace["iterations"])
    result["signature"] = signature(result)
    return result


def signature(result):
    """Keep all old deterministic fields, including occupancy and work counters."""
    trim = lambda item: {key: value for key, value in item.items()
                         if key not in ("time", "nps") and not key.endswith("_ms")}
    return dict(iterations=[trim(item) for item in result["iterations"]],
                final_aggregate=trim(result["final_aggregate"]), bestmove=result["bestmove"],
                ponder=result["ponder"], leader_iterations=[trim(item) for item in result["leader_iterations"]],
                diagnostics={name: trim(value) for name, value in result["diagnostics"].items()
                             if name != "move-hints"})


def validate_identity(identity, role, options):
    validate_options(identity, options)
    declarations = [line for line in identity if line.startswith("option name TT Move Hints ")]
    if declarations != ([] if role == "parent" else ["option name TT Move Hints type check default false"]):
        raise ValueError("Unexpected TT Move Hints declaration or default")
    if identity[-1:] != ["uciok"] or identity.count("uciok") != 1:
        raise ValueError("Malformed UCI identity terminator")


def receive(engine, prefix, timeout, monitor, raw, output):
    """Keep partial output and EOF receipts while enforcing the global watchdog."""
    deadline = min(monitor.deadline, time.monotonic() + timeout)
    while True:
        monitor.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for " + prefix)
        try:
            line = engine.lines.get(timeout=min(.25, remaining))
        except queue.Empty:
            continue
        monitor.check()
        log(raw, "<", line)
        if line is None:
            raise RuntimeError("Engine exited before " + prefix)
        output.append(line)
        engine.transcript.append(line)
        reject_errors([line])
        if line.startswith(prefix):
            return output


def finish_session(engine, session, raw):
    """Join and drain the reader so late output and abnormal exits cannot vanish."""
    if engine.process.poll() is None:
        send(engine, "quit", raw, session)
        try:
            engine.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            session["shutdown_error"] = "Engine did not quit within two seconds"
            engine.process.kill()
            engine.process.wait(timeout=2)
    engine.close()
    trailing, eof_count, after_eof = [], 0, False
    while True:
        try:
            line = engine.lines.get_nowait()
        except queue.Empty:
            break
        log(raw, "<", line)
        if line is None:
            eof_count += 1
        else:
            after_eof |= eof_count > 0
            trailing.append(line)
            engine.transcript.append(line)
    session.update(shutdown_output=trailing, shutdown_eof_count=eof_count,
                   exit_code=engine.process.poll(), received_transcript=list(engine.transcript))
    if (session.get("shutdown_error") or session["exit_code"] != 0 or engine.reader.is_alive()
            or eof_count != 1 or after_eof or any(line.strip() for line in trailing)):
        raise ValueError("Unclean engine exit, reader or shutdown output")


def run_session(session, position, binary, network, output, monitor, samples):
    engine = None
    session.update(commands=[], identity=[], setup_output=[], status="preparing")
    raw_path = output / session["raw_log"]
    with raw_path.open("x", encoding="utf-8") as raw:
        try:
            monitor.check(force=True)
            engine = Engine(binary, cwd=ROOT)
            session["pid"] = engine.process.pid
            send(engine, "uci", raw, session)
            receive(engine, "uciok", 10, monitor, raw, session["identity"])
            options = options_for(session["role"], network)
            session["options"] = options
            validate_identity(session["identity"], session["role"], options)
            for name, value in options.items():
                send(engine, "setoption name " + name + " value " + value, raw, session)
            send(engine, "isready", raw, session)
            receive(engine, "readyok", 10, monitor, raw, session["setup_output"])
            if session["setup_output"] != ["info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                raise ValueError("Unexpected setup readiness output")
            for temperature in ("cold", "warm"):
                sample = dict(session_id=session["id"], role=session["role"], repetition=session["repetition"],
                              position_index=session["position_index"], position_id=position["id"],
                              temperature=temperature, status="preparing", preparation_output=[], output=[], post_search_output=[])
                samples.append(sample)
                if temperature == "cold":
                    send(engine, "ucinewgame", raw, session)
                send(engine, "position " + position["position"], raw, session)
                send(engine, "isready", raw, session)
                receive(engine, "readyok", 10, monitor, raw, sample["preparation_output"])
                if sample["preparation_output"] != ["readyok"]:
                    raise ValueError("Unexpected position readiness output")
                monitor.check(force=True)
                sample.update(status="searching", start_wall=time.time(), start_monotonic=time.monotonic())
                send(engine, "go depth " + str(DEPTH), raw, session)
                receive(engine, "bestmove ", SEARCH_TIMEOUT, monitor, raw, sample["output"])
                sample.update(elapsed_seconds=time.monotonic() - sample["start_monotonic"],
                              wall_elapsed_seconds=time.time() - sample["start_wall"])
                elapsed, wall_elapsed = sample["elapsed_seconds"], sample["wall_elapsed_seconds"]
                if (not all(math.isfinite(value) and value > 0 for value in (elapsed, wall_elapsed))
                        or abs(elapsed - wall_elapsed) > .5):
                    raise ValueError("Invalid search receipt clocks or clock discontinuity")
                sample["result"] = validate_result(sample["output"], board_for(position["position"]), session["role"])
                send(engine, "isready", raw, session)
                receive(engine, "readyok", 10, monitor, raw, sample["post_search_output"])
                if sample["post_search_output"] != ["readyok"]:
                    raise ValueError("Unexpected output after bestmove")
                monitor.check(force=True)
                sample["status"] = "complete"
            session["status"] = "complete"
        except BaseException as error:
            session.update(status="failed", error=type(error).__name__ + ": " + str(error))
            if samples and samples[-1]["session_id"] == session["id"] and samples[-1]["status"] != "complete":
                samples[-1].update(status="failed", error=session["error"])
            if engine is not None and engine.process.poll() is None:
                engine.process.kill()
                engine.process.wait(timeout=2)
            raise
        finally:
            if engine is not None:
                try:
                    finish_session(engine, session, raw)
                except BaseException as error:
                    was_complete = session["status"] == "complete"
                    session.update(status="failed", shutdown_error=str(error), exit_code=engine.process.poll(),
                                   received_transcript=list(engine.transcript))
                    if was_complete:
                        raise
            session["finished_utc"] = datetime.now(timezone.utc).isoformat()
    session["raw_sha256"] = digest(raw_path)


def summarize(samples, positions):
    lookup = {}
    for sample in samples:
        key = (sample["repetition"], sample["position_index"], sample["role"], sample["temperature"])
        if key in lookup or sample["status"] != "complete":
            raise ValueError("Duplicate or incomplete work observation")
        lookup[key] = sample["result"]
    expected = {(r, i, role, temp) for r in range(REPETITIONS) for i in range(len(positions))
                for role in ROLES for temp in ("cold", "warm")}
    if set(lookup) != expected:
        raise ValueError("Incomplete comparison matrix")
    pairs, groups = [], {}
    for temp in ("cold", "warm"):
        for i, position in enumerate(positions):
            for r in range(REPETITIONS):
                parent, off, on = [lookup[r, i, role, temp] for role in ROLES]
                if parent["signature"] != off["signature"]:
                    raise ValueError("Parent/off exact parity failed: " + position["id"] + " " + temp)
                for role in ROLES:
                    if lookup[r, i, role, temp]["signature"] != lookup[0, i, role, temp]["signature"]:
                        raise ValueError("Repeated search work was nondeterministic: " + position["id"])
                    if role == "on" and on["diagnostics"]["move-hints"] != lookup[0, i, role, temp]["diagnostics"]["move-hints"]:
                        raise ValueError("Repeated hint counters were nondeterministic")
                pairs.append(dict(position_id=position["id"], repetition=r, temperature=temp,
                                  off_nodes=off["reported_nodes"], on_nodes=on["reported_nodes"],
                                  off_over_on_nodes=off["reported_nodes"] / on["reported_nodes"],
                                  same_bestmove=off["bestmove"] == on["bestmove"],
                                  off_bestmove=off["bestmove"], on_bestmove=on["bestmove"],
                                  off_score=off["score"], on_score=on["score"], hints=on["diagnostics"]["move-hints"]))
        selected = [pair for pair in pairs if pair["temperature"] == temp]
        off_nodes, on_nodes = (sum(pair[key] for pair in selected) for key in ("off_nodes", "on_nodes"))
        groups[temp] = dict(pairs=len(selected), off_nodes=off_nodes, on_nodes=on_nodes,
                            off_over_on_nodes=off_nodes / on_nodes,
                            same_bestmove=sum(pair["same_bestmove"] for pair in selected),
                            hint_totals={name: sum(pair["hints"][name] for pair in selected)
                                         for name in ("probes", "hits", "legal_matches", "stores")})
    totals = {name: sum(group["hint_totals"][name] for group in groups.values())
              for name in ("probes", "hits", "legal_matches", "stores")}
    if any(value == 0 for value in totals.values()):
        raise ValueError("The complete corpus did not demonstrate active move-hint use")
    return dict(exact_parent_off_pairs=len(pairs), on_off_pairs=len(pairs), hint_totals=totals,
                groups=groups, pairs=pairs,
                interpretation="Instrumented fixed-depth work on exposed roots; changing order can change selective results. No speed, Elo or guaranteed tactical-strength claim.")


def source_paths():
    paths = {name: ROOT / name for name in SOURCES}
    for directory in ("src", "include", "third_party/fathom/src"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in (".cpp", ".hpp", ".c", ".h"):
                paths[str(path.relative_to(ROOT))] = path
    return paths


def profile(parent, candidate, output, *, candidate_sha256, network=NETWORK):
    if not isinstance(candidate_sha256, str) or not re.fullmatch("[0-9a-f]{64}", candidate_sha256):
        raise ValueError("Supply the candidate's predeclared SHA-256")
    parent, candidate, output, network = [Path(path).expanduser().resolve() for path in (parent, candidate, output, network)]
    if output.exists():
        raise ValueError("Output exists; preserve it and choose a fresh directory")
    if any(any(ord(c) < 32 for c in str(path)) for path in (parent, candidate, output, network)):
        raise ValueError("Paths must fit on one UCI line")
    corpus, positions = load_positions()
    paths = dict(source_paths(), parent=parent, candidate=candidate, network=network, corpus=CORPUS, protocol=PROTOCOL)
    for name, expected in corpus.get("sources", {}).items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError("Original exposed corpus source changed: " + name)
        paths[name] = path
    frozen = {name: dict(path=str(path), sha256=digest(path)) for name, path in paths.items()}
    for name, expected in (("parent", PARENT_SHA256), ("candidate", candidate_sha256),
                           ("network", PINNED_NETWORK), ("corpus", CORPUS_SHA256), ("protocol", PROTOCOL_SHA256)):
        if frozen[name]["sha256"] != expected:
            raise ValueError("Artifact does not match the frozen pin: " + name)
    report = dict(schema_version=1, status="running", started_utc=datetime.now(timezone.utc).isoformat(),
                  assets=frozen, corpus=corpus, positions=positions,
                  platform=platform.platform(), machine=platform.machine(),
                  git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  git_status=subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
                  source_snapshot_note="Local source hashes identify inspected inputs, not proof of binary/source correspondence; the frozen parent and candidate build provenance remain separate.",
                  settings=dict(depth=DEPTH, repetitions=REPETITIONS, hash_mb=HASH_MB, threads=1,
                                diagnostics=True, max_total_seconds=300, per_search_timeout_seconds=SEARCH_TIMEOUT,
                                clock_gap_limit_seconds=5, resident_engines=1, active_search_workers=1),
                  options={role: options_for(role, network) for role in ROLES},
                  initial_resource_policy=resource_check(network, 1), monitor_events=[], sessions=[], samples=[],
                  timing_qualified=False,
                  timing_note="LM Studio may be active. Main-loop wall/monotonic receipts and engine times are watchdog evidence only; no elapsed-time speed ratios. Immediate warm searches retain both tables and learned history.")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "report.json"
    publish(target, report)
    monitor = Monitor(network, report["monitor_events"])
    monitor.threads = 1
    try:
        for r in range(REPETITIONS):
            for i, position in enumerate(positions):
                for role in run_order(i, r):
                    session = dict(id=len(report["sessions"]), repetition=r, position_index=i,
                                   position_id=position["id"], role=role,
                                   raw_log=f"r{r + 1}-{i + 1:02}-{role}.jsonl")
                    report["sessions"].append(session)
                    run_session(session, position, parent if role == "parent" else candidate,
                                network, output, monitor, report["samples"])
                    publish(target, report)
        report["summary"] = summarize(report["samples"], positions)
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        for session in report["sessions"]:
            raw_path = output / session["raw_log"]
            if raw_path.is_file():
                session["raw_sha256"] = digest(raw_path)
        try:
            report["assets_after"] = {name: digest(path) for name, path in paths.items()}
            if any(report["assets_after"][name] != value["sha256"] for name, value in frozen.items()):
                raise ValueError("A binary, input, protocol or source changed during the screen")
            monitor.check(force=True)
        except BaseException as error:
            was_passed = report["status"] == "passed"
            report.update(status="failed", asset_or_monitor_error=str(error))
            publish(target, report)
            if was_passed:
                raise
        finally:
            report.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                          elapsed_seconds=time.monotonic() - monitor.start_mono,
                          max_clock_gap_seconds=monitor.max_gap,
                          max_clock_discrepancy_seconds=monitor.max_discrepancy)
            publish(target, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--network", type=Path, default=NETWORK)
    args = parser.parse_args(argv)
    report = profile(args.parent, args.candidate, args.output,
                     candidate_sha256=args.candidate_sha256, network=args.network)
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
