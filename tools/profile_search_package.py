#!/usr/bin/env python3
"""Bounded combined-search diagnostics on fifteen exposed development roots.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Fresh processes compare default/all-on policies at one/eight workers, twice each.
Diagnostics perturb execution; nodes, depth and counters cannot establish Elo,
universal speed, or the causal cost of a particular search component. Direct
invocation prepares the pinned Python referee automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import queue
import signal
import statistics
import subprocess
import sys
import time

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

from bench import digest
from compare_bench import physical_memory, reject_errors
from profile_cache import board_for, cache_record, publish
from profile_smp import unsigned, validate_result as validate_uci
from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/data/countermove-profile.json"
NETWORK = ROOT / "networks/nn-1a298aa575a0.nnue"
PINNED_NETWORK = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
TOTAL_SECONDS, SEARCH_TIMEOUT, GAP_LIMIT = 300.0, 5.0, 5.0
RECEIPT_TOLERANCE_SECONDS = .250
REPETITIONS, HASH_MB = 2, 64
BASE_OPTIONS = {
    "Threads": "1", "Hash": "64", "Ponder": "false", "Move Overhead": "20",
    "Time Policy": "classic", "Search Diagnostics": "true",
    "Late Move Reductions": "true", "Deep Quiet Reductions": "false",
    "Capture Ordering": "mvv-lva", "Countermove Ordering": "false",
    "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
    "QSearch SEE Pruning": "false", "ProbCut": "false",
    "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
}
PACKAGE_CHANGES = {"Deep Quiet Reductions": "true", "Capture Ordering": "see",
                   "Countermove Ordering": "true", "Null Move Pruning": "true",
                   "Reverse Futility Pruning": "true", "QSearch SEE Pruning": "true", "ProbCut": "true"}
CONFIGURATIONS = tuple(dict(id=f"{role}-t{threads}", role=role, threads=threads)
                       for threads in (1, 8) for role in ("default", "all-on"))
ADVERTISED_DEFAULTS = dict(BASE_OPTIONS, **{"Search Diagnostics": "false", "SyzygyProbeLimit": "7"})
SCHEMAS = {
    "search-iteration": "depth completed nodes duration_ms elapsed_ms",
    "search-summary": "policy forecast_active stop_reason nodes completed_depth elapsed_ms soft_ms hard_ms target_ms predicted_next_ms",
    "smp": "threads total_nodes leader_nodes worker_nodes worker_depths",
    "cache": "entry_bytes bucket_bytes buckets capacity allocated_bytes probes hits cutoffs stores replacements",
    "ordering": "policy see_calls losing_captures",
    "lmr": "enabled reductions researches fail_lows verified_cutoffs",
    "deep-lmr": "enabled extra_reductions researches fail_lows verified_cutoffs",
    "countermove": "enabled lookups matches updates",
    "nullmove": "enabled probes fail_highs verifications cutoffs rejected",
    "reversefutility": "enabled evaluations cutoffs",
    "qsearchsee": "enabled evaluations pruned",
    "probcut": "enabled eligible_nodes see_evaluations qsearches qsearch_passes searches cutoffs rejected",
}
NULL_WORK_FIELDS = {"probe_nodes", "verification_nodes", "verification_hints"}
OPTIONAL_RECORDS = {"deep-lmr", "countermove", "nullmove", "reversefutility", "qsearchsee", "probcut"}
SOURCES = ("tools/profile_search_package.py", "tests/profile_search_package_test.py", "Makefile",
           "tools/bench.py", "tools/compare_bench.py", "tools/profile_cache.py",
           "tools/profile_search.py", "tools/profile_smp.py", "tools/resources.py", "tools/uci_client.py",
           "tools/tooling.py", "tools/python-packages.json", "requirements-match.txt", "networks/manifest.json")


def options_for(config, network):
    options = dict(BASE_OPTIONS)
    if config["role"] == "all-on": options.update(PACKAGE_CHANGES)
    elif config["role"] != "default": raise ValueError("Unknown search policy")
    if config["threads"] not in (1, 8): raise ValueError("Expected one or eight workers")
    options.update(Threads=str(config["threads"]), EvalFile=str(network))
    return options


def run_order(position_index, repetition):
    offset = position_index % len(CONFIGURATIONS)
    order = CONFIGURATIONS[offset:] + CONFIGURATIONS[:offset]
    return order if repetition % 2 == 0 else order[::-1]


def load_positions():
    document = json.loads(CORPUS.read_text(encoding="utf-8"))
    positions = document.get("positions") if isinstance(document, dict) else None
    if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(positions, list) or len(positions) != 15:
        raise ValueError("Use all fifteen existing exposed roots; no alternate corpus is supported")
    seen = set()
    for item in positions:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or item["id"] in seen:
            raise ValueError("Development roots require unique IDs")
        if not isinstance(item.get("position"), str): raise ValueError("Missing UCI position")
        board_for(item["position"])
        seen.add(item["id"])
    return document, positions


def diagnostic_record(line):
    """Strict schema parsing shared only within this new SMP-aware profiler."""
    tokens = line.split()
    if len(tokens) < 4 or tokens[:2] != ["info", "string"] or tokens[2] not in SCHEMAS or tokens[3] != "v1":
        raise ValueError("Unsupported diagnostic record: " + line)
    name, values = tokens[2], tokens[4:]
    if len(values) % 2 or len(set(values[::2])) != len(values) // 2:
        raise ValueError("Malformed or duplicate diagnostic fields")
    fields = dict(zip(values[::2], values[1::2]))
    expected = set(SCHEMAS[name].split())
    # Preserve old evidence verbatim; the additive null-work extension must be
    # complete when present. Missing historical work counts are not zeros.
    if set(fields) != expected and not (name == "nullmove" and set(fields) == expected | NULL_WORK_FIELDS):
        raise ValueError("Missing or unexpected diagnostic fields")
    for key, value in fields.items():
        if key in ("enabled", "completed", "forecast_active"):
            if value not in ("true", "false"): raise ValueError("Invalid diagnostic boolean")
            fields[key] = value == "true"
        elif key in ("worker_nodes", "worker_depths"):
            fields[key] = [unsigned(number, key) for number in value.split(",")]
        elif key.endswith("_ms"):
            fields[key] = float(value)
            if not math.isfinite(fields[key]) or fields[key] < 0: raise ValueError("Invalid diagnostic duration")
        elif key not in ("policy", "stop_reason"):
            fields[key] = unsigned(value, key)
    return name, fields


def validate_result(lines, board, config, movetime_ms):
    """Separate leader-only iteration deltas from joined aggregate counters."""
    reject_errors(lines)
    records, iterations, ordinary = {}, [], []
    summary_seen = best_seen = False
    for line in lines:
        if best_seen: raise ValueError("Unexpected output after bestmove")
        if line.startswith("info string "):
            if summary_seen: raise ValueError("Diagnostics after final summary")
            name, fields = diagnostic_record(line)
            if name == "search-iteration":
                if fields["depth"] != len(iterations) + 1 or (iterations and not iterations[-1]["completed"]):
                    raise ValueError("Missing/repeated leader iteration or work after an aborted iteration")
                iterations.append(fields)
            else:
                if name in records: raise ValueError("Duplicate diagnostic record")
                records[name] = fields
                summary_seen = name == "search-summary"
        else:
            tokens = line.split()
            if tokens[:1] == ["bestmove"]:
                if not summary_seen: raise ValueError("Bestmove precedes final diagnostics")
                best_seen = True
            elif summary_seen: raise ValueError("Ordinary search info after final summary")
            if "lowerbound" in tokens or "upperbound" in tokens: raise ValueError("Completed score must be exact")
            if tokens[:1] == ["info"]:
                if tokens.count("tbhits") != 1 or tokens[-1] == "tbhits" or tokens[tokens.index("tbhits") + 1] != "0":
                    raise ValueError("Each ordinary info record must have zero tablebase hits")
            ordinary.append(line)
    expected = {"cache", "ordering", "lmr", "search-summary"}
    if config["threads"] > 1: expected.add("smp")
    if config["role"] == "all-on": expected.update(OPTIONAL_RECORDS)
    if set(records) != expected or not iterations: raise ValueError("Missing or unexpected configured diagnostic record")
    result = validate_uci(ordinary, board, "time", None)
    summary = records["search-summary"]
    if (summary["policy"] != "classic" or summary["forecast_active"]
            or summary["stop_reason"] not in ("hard_time", "depth_limit")
            or (summary["stop_reason"] == "depth_limit" and summary["completed_depth"] != 126)
            or summary["nodes"] != result["reported_nodes"]
            or summary["completed_depth"] != result["completed_depth"]):
        raise ValueError("Search summary disagrees with configured policy or UCI totals")
    if summary["soft_ms"] != movetime_ms - 20 or summary["hard_ms"] != movetime_ms - 20:
        raise ValueError("Reported time budget differs from explicit movetime and overhead")
    if config["threads"] == 1:
        worker_nodes, worker_depths = [summary["nodes"]], [summary["completed_depth"]]
    else:
        smp = records["smp"]
        worker_nodes, worker_depths = smp["worker_nodes"], smp["worker_depths"]
        if (smp["threads"] != config["threads"] or len(worker_nodes) != config["threads"]
                or len(worker_depths) != config["threads"] or sum(worker_nodes) != summary["nodes"]
                or smp["total_nodes"] != summary["nodes"] or smp["leader_nodes"] != worker_nodes[0]
                or worker_depths[0] != summary["completed_depth"]):
            raise ValueError("SMP worker accounting disagrees with joined totals or leader depth")
    completed = [item for item in iterations if item["completed"]]
    if len(completed) != summary["completed_depth"] or sum(item["nodes"] for item in iterations) != worker_nodes[0]:
        raise ValueError("Leader iteration nodes/depth disagree with leader worker totals")
    tolerance, previous_time, cumulative = .001 * (len(iterations) + 2), 0.0, 0
    for item in iterations:
        if item["elapsed_ms"] + tolerance < previous_time + item["duration_ms"]:
            raise ValueError("Leader iteration duration exceeds its elapsed interval")
        previous_time = item["elapsed_ms"]
        cumulative += item["nodes"]
        if item["completed"]:
            info = result["iterations"][item["depth"] - 1]
            # Ordinary callbacks sample aggregate work while helpers are running.
            if info["nodes"] < cumulative or (config["threads"] == 1 and info["nodes"] != cumulative):
                raise ValueError("Completed aggregate nodes cannot be below completed leader work")
    if summary["elapsed_ms"] + tolerance < previous_time: raise ValueError("Summary precedes leader completion")
    records["cache"] = cache_record(lines, HASH_MB)
    if records["ordering"]["policy"] != ("see" if config["role"] == "all-on" else "mvv-lva"):
        raise ValueError("Wrong capture ordering policy")
    if records["ordering"]["losing_captures"] > records["ordering"]["see_calls"]:
        raise ValueError("Invalid SEE ordering accounting")
    if config["role"] == "default" and records["ordering"]["see_calls"] != 0:
        raise ValueError("Default capture ordering unexpectedly evaluated SEE")
    for name in {"lmr"} | (OPTIONAL_RECORDS if config["role"] == "all-on" else set()):
        if not records[name]["enabled"]: raise ValueError("Configured search policy was not enabled")
    for name, reduction in (("lmr", "reductions"), ("deep-lmr", "extra_reductions")):
        if name not in records: continue
        counters = records[name]
        if counters["researches"] > counters[reduction] or counters["fail_lows"] + counters["verified_cutoffs"] > counters["researches"]:
            raise ValueError("Invalid reduction/research accounting")
    if config["role"] == "all-on":
        deep, counter, null, rfp, qsee, pc = [records[name] for name in
            ("deep-lmr", "countermove", "nullmove", "reversefutility", "qsearchsee", "probcut")]
        if deep["extra_reductions"] > records["lmr"]["reductions"] or counter["matches"] > counter["lookups"]:
            raise ValueError("Invalid deep-reduction or countermove accounting")
        if (null["fail_highs"] > null["probes"] or null["verifications"] != null["fail_highs"]
                or null["cutoffs"] + null["rejected"] > null["verifications"]):
            raise ValueError("Invalid null-move accounting")
        if NULL_WORK_FIELDS <= null.keys():
            # An attempted subtree can stop before its first node; completed
            # outcomes and admitted hints require at least one visited node.
            if (null["probe_nodes"] + null["verification_nodes"] > summary["nodes"]
                    or null["probe_nodes"] < null["fail_highs"]
                    or null["verification_nodes"] < null["cutoffs"] + null["rejected"]
                    or null["verification_hints"] > min(null["verifications"], null["verification_nodes"])
                    or (null["probes"] == 0 and null["probe_nodes"] != 0)
                    or (null["verifications"] == 0 and null["verification_nodes"] != 0)):
                raise ValueError("Invalid null-move work accounting")
        if rfp["cutoffs"] > rfp["evaluations"] or qsee["pruned"] > qsee["evaluations"]:
            raise ValueError("Invalid futility/SEE pruning accounting")
        if (pc["see_evaluations"] > 3 * pc["eligible_nodes"] or pc["qsearches"] > pc["see_evaluations"]
                or pc["qsearch_passes"] > pc["qsearches"] or pc["searches"] != pc["qsearch_passes"]
                or pc["cutoffs"] + pc["rejected"] > pc["searches"]):
            raise ValueError("Invalid ProbCut accounting")
    result.update(diagnostics=records, leader_iterations=iterations, worker_nodes=worker_nodes,
                  worker_depths=worker_depths, leader_nodes=worker_nodes[0],
                  active_workers=sum(value > 0 for value in worker_nodes),
                  leader_aborted_nodes=sum(item["nodes"] for item in iterations if not item["completed"]))
    return result


def resource_check(network, threads):
    policy = dict(current_budget())
    memory = physical_memory()
    if memory is None and sys.platform == "darwin":
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True,
                                            stderr=subprocess.DEVNULL, timeout=2))
    reservation = max(2 * 1024**3, HASH_MB * 1024**2 + 4 * network.stat().st_size + (64 + 128 * threads) * 1024**2)
    if memory is None or memory <= 0: raise ValueError("Cannot determine physical RAM")
    if threads > policy["max_cpu_workers"] or reservation > memory * policy["memory_fraction"]:
        raise ValueError("Diagnostic workers or minimum 2-GiB reservation exceed the current resource budget")
    return dict(policy, active_search_workers=threads, resident_engines=1,
                estimated_memory_bytes=reservation, physical_memory_bytes=memory, memory_estimate_is_hard_cap=False)


class Monitor:
    """Deadline and resource checks remain live while waiting on an engine queue."""
    def __init__(self, network, events):
        self.start_wall = self.last_wall = time.time()
        self.start_mono = self.last_mono = time.monotonic()
        self.deadline = self.start_mono + TOTAL_SECONDS
        self.network, self.events, self.threads = network, events, 8
        self.next_resource = 0.0
        self.max_gap = self.max_discrepancy = 0.0

    def check(self, force=False):
        wall, mono = time.time(), time.monotonic()
        wall_gap, mono_gap = wall - self.last_wall, mono - self.last_mono
        discrepancy = max(abs(wall_gap - mono_gap), abs((wall - self.start_wall) - (mono - self.start_mono)))
        self.max_gap, self.max_discrepancy = max(self.max_gap, wall_gap, mono_gap), max(self.max_discrepancy, discrepancy)
        self.last_wall, self.last_mono = wall, mono
        if min(wall_gap, mono_gap) < 0 or max(wall_gap, mono_gap, discrepancy) > GAP_LIMIT:
            self.events.append(dict(event="clock_violation", wall=wall, monotonic=mono,
                                    wall_gap=wall_gap, monotonic_gap=mono_gap, discrepancy=discrepancy))
            raise RuntimeError("Suspension, clock discontinuity or scheduling gap invalidated diagnostics")
        if mono >= self.deadline: raise TimeoutError("300-second diagnostic limit reached")
        if force or mono >= self.next_resource:
            event = dict(event="resource_check", wall=wall, monotonic=mono)
            self.events.append(event)
            event["policy"] = resource_check(self.network, self.threads)
            self.next_resource = mono + 2


def log(raw, direction, line):
    raw.write(json.dumps(dict(wall=time.time(), monotonic=time.monotonic(), direction=direction, line=line)) + "\n")
    raw.flush()


def send(engine, command, raw, sample):
    sample["commands"].append(command); log(raw, ">", command); engine.send(command)


def receive(engine, prefix, timeout, monitor, raw, output):
    deadline = min(monitor.deadline, time.monotonic() + timeout)
    while True:
        monitor.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise TimeoutError("Timed out waiting for " + prefix)
        try: line = engine.lines.get(timeout=min(.25, remaining))
        except queue.Empty: continue
        monitor.check()
        if line is None: raise RuntimeError("Engine exited before " + prefix)
        output.append(line); engine.transcript.append(line); log(raw, "<", line)
        reject_errors([line])
        if line.startswith(prefix): return output


def validate_options(identity, options):
    for name, value in options.items():
        declarations = [line for line in identity if line.startswith("option name " + name + " type ")]
        if len(declarations) != 1: raise ValueError("Missing/duplicate option: " + name)
        tokens = declarations[0].split(" type ", 1)[1].split()
        kind = ("spin" if name in ("Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth") else
                "combo" if name in ("Time Policy", "Capture Ordering") else
                "string" if name in ("EvalFile", "SyzygyPath") else "check")
        if tokens[0] != kind: raise ValueError("Wrong option type: " + name)
        if name in ADVERTISED_DEFAULTS and ("default" not in tokens or tokens[tokens.index("default") + 1] != ADVERTISED_DEFAULTS[name]):
            raise ValueError("Advertised current default differs: " + name)
        if kind == "spin" and not int(tokens[tokens.index("min") + 1]) <= int(value) <= int(tokens[tokens.index("max") + 1]):
            raise ValueError("Requested option outside engine range: " + name)
        if kind == "combo" and (" var " + value) not in declarations[0]: raise ValueError("Missing option choice: " + name)


def validate_timing(sample, movetime_ms):
    """The hang watchdog is not a substitute for matched analysis time."""
    elapsed = (sample["elapsed_seconds"], sample["wall_elapsed_seconds"])
    if any(not math.isfinite(value) or value <= 0 for value in elapsed): raise ValueError("Invalid elapsed measurement")
    sample["receipt_overrun_seconds"] = max(0.0, max(elapsed) - movetime_ms / 1000)
    sample["within_receipt_tolerance"] = sample["receipt_overrun_seconds"] <= RECEIPT_TOLERANCE_SECONDS
    if not sample["within_receipt_tolerance"]:
        raise RuntimeError("Search receipt exceeded the fixed 250-ms tolerance; preserve failure without replacement")


def run_case(sample, position, config, engine_path, network, output, movetime_ms, monitor):
    engine = None
    with (output / sample["raw_log"]).open("x", encoding="utf-8") as raw:
        sample.update(commands=[], setup_output=[], output=[])
        try:
            monitor.threads = config["threads"]; monitor.check(force=True)
            engine = Engine(engine_path, cwd=ROOT)
            sample["pid"] = engine.process.pid
            send(engine, "uci", raw, sample)
            identity = receive(engine, "uciok", 10, monitor, raw, sample["setup_output"])
            options = options_for(config, network)
            validate_options(identity, options)
            for name, value in options.items(): send(engine, "setoption name " + name + " value " + value, raw, sample)
            send(engine, "isready", raw, sample)
            receive(engine, "readyok", 15, monitor, raw, sample["setup_output"])
            if any(line.startswith("bestmove") for line in sample["setup_output"]): raise ValueError("Unexpected setup bestmove")
            for command in ("ucinewgame", "position " + position["position"], "isready"): send(engine, command, raw, sample)
            ready = receive(engine, "readyok", 5, monitor, raw, [])
            sample["setup_output"].extend(ready)
            if ready != ["readyok"]: raise ValueError("Unexpected position readiness output")
            monitor.check(force=True)
            sample.update(status="searching", start_wall=time.time(), start_monotonic=time.monotonic())
            send(engine, "go movetime " + str(movetime_ms), raw, sample)
            receive(engine, "bestmove ", SEARCH_TIMEOUT, monitor, raw, sample["output"])
            sample.update(elapsed_seconds=time.monotonic() - sample["start_monotonic"],
                          wall_elapsed_seconds=time.time() - sample["start_wall"])
            sample["result"] = validate_result(sample["output"], board_for(position["position"]), config, movetime_ms)
            validate_timing(sample, movetime_ms)
            send(engine, "isready", raw, sample)
            sample["post_search_output"] = receive(engine, "readyok", 5, monitor, raw, [])
            if sample["post_search_output"] != ["readyok"]: raise ValueError("Unexpected output after bestmove")
            monitor.check(force=True)
            sample["status"] = "complete"
        except BaseException as error:
            sample.update(status="failed", error=type(error).__name__ + ": " + str(error))
            if engine is not None and engine.process.poll() is None:
                engine.process.kill(); engine.process.wait(timeout=2)
            raise
        finally:
            if engine is not None:
                try:
                    if engine.process.poll() is None:
                        send(engine, "quit", raw, sample)
                        try: engine.process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            sample["shutdown_error"] = "Engine did not quit within two seconds"
                            engine.process.kill(); engine.process.wait(timeout=2)
                    engine.close()
                finally:
                    sample["exit_code"] = engine.process.poll()
                    sample["process_finished_utc"] = datetime.now(timezone.utc).isoformat()
                if sample["status"] == "complete" and (sample.get("shutdown_error") or sample["exit_code"] != 0):
                    sample["status"] = "failed"
                    raise RuntimeError("Engine shutdown was not clean")


def fraction(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize_group(samples):
    total_nodes = sum(sample["result"]["reported_nodes"] for sample in samples)
    seconds = sum(sample["elapsed_seconds"] for sample in samples)
    totals = {name: {} for name in SCHEMAS if name not in ("search-iteration", "search-summary", "smp")}
    for sample in samples:
        for name in totals:
            for key, value in sample["result"]["diagnostics"].get(name, {}).items():
                if name == "cache" and key in ("entry_bytes", "bucket_bytes", "buckets", "capacity", "allocated_bytes"):
                    continue  # Geometry is retained per search, never summed as an activity counter.
                if type(value) is int: totals[name][key] = totals[name].get(key, 0) + value
    fractions = {}
    for label, record, numerator, denominator in (
            ("cache_hit_per_probe", "cache", "hits", "probes"), ("cache_cutoff_per_probe", "cache", "cutoffs", "probes"),
            ("ordering_losing_per_see", "ordering", "losing_captures", "see_calls"),
            ("lmr_research_per_reduction", "lmr", "researches", "reductions"),
            ("deep_research_per_extra_reduction", "deep-lmr", "researches", "extra_reductions"),
            ("countermove_match_per_lookup", "countermove", "matches", "lookups"),
            ("null_cutoff_per_probe", "nullmove", "cutoffs", "probes"),
            ("rfp_cutoff_per_evaluation", "reversefutility", "cutoffs", "evaluations"),
            ("qsee_pruned_per_evaluation", "qsearchsee", "pruned", "evaluations"),
            ("probcut_cutoff_per_reduced_search", "probcut", "cutoffs", "searches")):
        fractions[label] = fraction(totals[record].get(numerator, 0), totals[record].get(denominator, 0))
    return dict(searches=len(samples), nodes=total_nodes, receipt_seconds=seconds,
                nodes_per_receipt_second=fraction(total_nodes, seconds),
                leader_depths=[sample["result"]["completed_depth"] for sample in samples],
                median_leader_depth=statistics.median(sample["result"]["completed_depth"] for sample in samples),
                leader_node_fraction=fraction(sum(sample["result"]["leader_nodes"] for sample in samples), total_nodes),
                leader_aborted_node_fraction=fraction(sum(sample["result"]["leader_aborted_nodes"] for sample in samples),
                                                     sum(sample["result"]["leader_nodes"] for sample in samples)),
                active_workers=[sample["result"]["active_workers"] for sample in samples],
                all_workers_active_searches=sum(sample["result"]["active_workers"] == sample["threads"] for sample in samples),
                branch_counters=totals, branch_fractions=fractions,
                activity_per_node={f"{record}.{counter}": fraction(values.get(counter, 0), total_nodes)
                    for record, counter in (("ordering", "see_calls"), ("qsearchsee", "evaluations"),
                                            ("probcut", "see_evaluations"), ("nullmove", "probes"),
                                            ("reversefutility", "evaluations")) for values in [totals[record]]})


def summarize(samples, positions):
    lookup = {(sample["position_id"], sample["config_id"], sample["repetition"]): sample for sample in samples}
    expected = {(position["id"], config["id"], repetition) for position in positions
                for config in CONFIGURATIONS for repetition in range(REPETITIONS)}
    if len(lookup) != len(samples) or set(lookup) != expected or any(sample["status"] != "complete" or sample["exit_code"] != 0 for sample in samples):
        raise ValueError("Diagnostic matrix is incomplete, duplicated or contains failed processes")
    if any(not math.isfinite(sample["elapsed_seconds"]) or sample["elapsed_seconds"] <= 0 for sample in samples):
        raise ValueError("Invalid elapsed diagnostic measurement")
    common_depth_pairs = []
    for position in positions:
        for repetition in range(REPETITIONS):
            for threads in (1, 8):
                results = {role: lookup[position["id"], f"{role}-t{threads}", repetition]["result"]
                           for role in ("default", "all-on")}
                depth = min(result["completed_depth"] for result in results.values())
                common_depth_pairs.append(dict(position_id=position["id"], repetition=repetition, threads=threads,
                    depth=depth, roles={role: dict(
                        leader_nodes_through_depth=sum(item["nodes"] for item in result["leader_iterations"] if item["depth"] <= depth),
                        reported_aggregate_nodes_at_depth=result["iterations"][depth-1]["nodes"],
                        score=result["iterations"][depth-1]["score"], pv=result["iterations"][depth-1]["pv"])
                        for role, result in results.items()}))
    return dict(configurations={config["id"]: summarize_group([sample for sample in samples if sample["config_id"] == config["id"]]) for config in CONFIGURATIONS},
                roots={position["id"]: {config["id"]: summarize_group([lookup[position["id"], config["id"], r] for r in range(REPETITIONS)])
                                        for config in CONFIGURATIONS} for position in positions},
                common_depth_pairs=common_depth_pairs,
                interpretation="Diagnostic instrumentation, different trees and duplicated SMP work affect throughput. Counters locate activity, not causal component cost. Exposed roots and two repetitions provide no Elo, general speed or forced-mate claim.")


def source_paths():
    paths = {name: ROOT / name for name in SOURCES}
    for directory in ("src", "include", "third_party/fathom/src"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in (".cpp", ".hpp", ".c", ".h"):
                paths[str(path.relative_to(ROOT))] = path
    return paths


def verify_assets(paths, frozen):
    result = {name: digest(path) for name, path in paths.items()}
    if any(result[name] != frozen[name]["sha256"] for name in paths): raise ValueError("A binary, input or source changed during the screen")
    return result


def profile(engine, network, output, *, movetime_ms=1000, quiet_host=False):
    if not quiet_host: raise ValueError("Use --quiet-host after stopping competing compute/build workloads")
    if type(movetime_ms) is not int or not 100 <= movetime_ms <= 1000:
        raise ValueError("movetime-ms must be an integer from 100 to 1000")
    engine, network, output = [Path(path).expanduser().resolve() for path in (engine, network, output)]
    if output.exists(): raise ValueError("Output exists; choose a new directory and preserve earlier evidence")
    if any(any(ord(c) < 32 for c in str(path)) for path in (engine, network, output)):
        raise ValueError("Paths must fit on one UCI line")
    corpus, positions = load_positions()
    paths = dict(source_paths(), engine=engine, network=network, corpus=CORPUS)
    frozen = {name: dict(path=str(path.resolve()), sha256=digest(path)) for name, path in paths.items()}
    if frozen["network"]["sha256"] != PINNED_NETWORK:
        raise ValueError("Phase 4F.4 requires the pinned nn-1a298aa575a0.nnue network")
    initial_resource = resource_check(network, 8)
    report = dict(schema_version=1, status="running", started_utc=datetime.now(timezone.utc).isoformat(),
                  assets=frozen, corpus=corpus, positions=positions, platform=platform.platform(), machine=platform.machine(),
                  pinned_network_match=frozen["network"]["sha256"] == PINNED_NETWORK,
                  source_snapshot_note="Local source hashes record inspected inputs; they do not prove that a user-supplied executable was built from these files.",
                  quiet_host_declared=True,
                  settings=dict(movetime_ms=movetime_ms, repetitions=REPETITIONS, total_seconds=TOTAL_SECONDS,
                                per_search_timeout_seconds=SEARCH_TIMEOUT, gap_limit_seconds=GAP_LIMIT,
                                receipt_tolerance_seconds=RECEIPT_TOLERANCE_SECONDS),
                  options={config["id"]: options_for(config, network) for config in CONFIGURATIONS},
                  initial_resource_policy=initial_resource, monitor_events=[], samples=[],
                  timing_note="Main-loop send/queue-receipt timestamps, not reader arrival. Setup excluded; post-search diagnostics and helper joining included. Both clocks must meet the 250-ms receipt tolerance separately from the five-second hang watchdog; failed observations are not replaced. Diagnostics perturb timing. Serial fresh processes; no warm caches or held-out/puzzle roots.")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "report.json"; publish(target, report)
    monitor = Monitor(network, report["monitor_events"])
    try:
        for repetition in range(REPETITIONS):
            for index, position in enumerate(positions):
                for config in run_order(index, repetition):
                    monitor.check(force=True)
                    verify_assets(paths, frozen)
                    sample = dict(repetition=repetition, position_id=position["id"], position_index=index,
                                  config_id=config["id"], role=config["role"], threads=config["threads"], status="preparing",
                                  raw_log=f"r{repetition+1}-{position['id']}-{config['id']}.uci.jsonl")
                    report["samples"].append(sample); publish(target, report)
                    print(f"{len(report['samples'])}/{len(positions)*len(CONFIGURATIONS)*REPETITIONS} {position['id']} {config['id']}", flush=True)
                    run_case(sample, position, config, engine, network, output, movetime_ms, monitor)
                    publish(target, report)
        report["after_sha256"] = verify_assets(paths, frozen)
        report["summary"] = summarize(report["samples"], positions)
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        if "after_sha256" not in report:
            report["after_sha256"] = {}
            for name, path in paths.items():
                try: report["after_sha256"][name] = digest(path)
                except OSError: report["after_sha256"][name] = None
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(), max_clock_gap_seconds=monitor.max_gap,
                      max_clock_discrepancy_seconds=monitor.max_discrepancy)
        publish(target, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--network", type=Path, default=NETWORK)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--movetime-ms", type=int, default=1000)
    parser.add_argument("--quiet-host", action="store_true", help="Declare that competing compute and build workloads have been stopped")
    args = parser.parse_args(argv)
    profile(args.engine, args.network, args.output, movetime_ms=args.movetime_ms, quiet_host=args.quiet_host)
    return 0


if __name__ == "__main__":
    def interrupted(signum, _frame): raise KeyboardInterrupt(f"Signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    try: sys.exit(main())
    except (KeyboardInterrupt, OSError, ValueError, RuntimeError, TimeoutError) as error:
        sys.exit(f"Search package diagnostic stopped: {error}")
