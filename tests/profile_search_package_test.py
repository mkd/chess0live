#!/usr/bin/env python3
"""Synthetic SMP accounting, bounded-process and provenance checks; no engine runs.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_search_package as p


def config(role="default", threads=1):
    return dict(id=f"{role}-t{threads}", role=role, threads=threads)


def reply(role="default", threads=1, movetime_ms=1000):
    """Helper work exceeds the leader trace; partial iterations are intentional."""
    total = 30 if threads == 1 else 100
    callback = 20 if threads == 1 else 40
    budget = movetime_ms - 20
    lines = [f"info depth 1 seldepth 2 score cp 10 nodes {callback} time 5 nps 4000 hashfull 0 tbhits 0 pv g1h3 g8h6",
             f"info nodes {total} time {budget} nps 100 hashfull 1 tbhits 0"]
    if role == "all-on":
        lines += ["info string probcut v1 enabled true eligible_nodes 2 see_evaluations 3 qsearches 2 qsearch_passes 1 searches 1 cutoffs 1 rejected 0",
                  "info string qsearchsee v1 enabled true evaluations 4 pruned 1",
                  "info string reversefutility v1 enabled true evaluations 6 cutoffs 3",
                  "info string nullmove v1 enabled true probes 5 fail_highs 2 verifications 2 cutoffs 1 rejected 1"]
    if threads == 8:
        lines.append("info string smp v1 threads 8 total_nodes 100 leader_nodes 30 worker_nodes 30,10,10,10,10,10,10,10 worker_depths 1,2,2,1,1,2,2,2")
    lines += ["info string cache v1 entry_bytes 16 bucket_bytes 64 buckets 524288 capacity 2097152 allocated_bytes 33554432 probes 10 hits 3 cutoffs 1 stores 7 replacements 2",
              "info string search-iteration v1 depth 1 completed true nodes 20 duration_ms 5.000 elapsed_ms 5.000",
              f"info string search-iteration v1 depth 2 completed false nodes 10 duration_ms {budget-5:.3f} elapsed_ms {budget:.3f}",
              f"info string ordering v1 policy {'see see_calls 5 losing_captures 1' if role == 'all-on' else 'mvv-lva see_calls 0 losing_captures 0'}",
              "info string lmr v1 enabled true reductions 4 researches 2 fail_lows 1 verified_cutoffs 1"]
    if role == "all-on":
        lines += ["info string deep-lmr v1 enabled true extra_reductions 2 researches 1 fail_lows 1 verified_cutoffs 0",
                  "info string countermove v1 enabled true lookups 10 matches 2 updates 3"]
    lines += [f"info string search-summary v1 policy classic forecast_active false stop_reason hard_time nodes {total} completed_depth 1 elapsed_ms {budget+.3:.3f} soft_ms {budget} hard_ms {budget} target_ms {budget} predicted_next_ms 0",
              "bestmove g1h3 ponder g8h6"]
    return lines


def declarations():
    lines = []
    for name, default in dict(p.ADVERTISED_DEFAULTS, EvalFile="network").items():
        if name in ("Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth"):
            tail = f"spin default {default} min 0 max 16384"
        elif name in ("Time Policy", "Capture Ordering"):
            tail = f"combo default {default} var classic var forecast var bounded var mvv-lva var see"
        elif name in ("EvalFile", "SyzygyPath"): tail = f"string default {default}"
        else: tail = f"check default {default}"
        lines.append("option name " + name + " type " + tail)
    return lines + ["uciok"]


class Process:
    next_pid = 4000
    def __init__(self):
        Process.next_pid += 1; self.pid = Process.next_pid; self.returncode = None; self.killed = False
    def poll(self): return self.returncode
    def kill(self): self.killed = True; self.returncode = -9
    def wait(self, timeout=None):
        if self.returncode is None: self.returncode = 0
        return self.returncode


class FakeEngine:
    instances = []
    invalid = False
    mutate = None
    extra = False
    crash_on_go = False
    def __init__(self, path, cwd=None):
        self.process, self.lines, self.transcript = Process(), queue.Queue(), []
        self.commands, self.closed = [], False
        self.threads, self.role = 1, "default"
        self.instances.append(self)
    def send(self, command):
        self.commands.append(command)
        output = []
        if command == "uci": output = declarations()
        elif command == "isready": output = ["readyok"]
        elif command.startswith("setoption name Threads value "): self.threads = int(command.split()[-1])
        elif command == "setoption name ProbCut value true": self.role = "all-on"
        elif command.startswith("go "):
            output = reply(self.role, self.threads, int(command.split()[-1]))
            if self.invalid: output[-1] = "bestmove e2e5"
            if self.extra: output.append("info string unexpected")
            if self.mutate: self.mutate.write_bytes(b"changed")
            if self.crash_on_go: self.process.returncode = 3; output = [None]
        elif command == "quit": self.process.returncode = 0
        for line in output: self.lines.put(line)
    def close(self): self.closed = True


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.engine, self.network, self.corpus = [self.root / name for name in ("engine", "network", "corpus")]
        for path in (self.engine, self.network, self.corpus): path.write_bytes(b"synthetic asset")
        self.positions = [dict(id=f"root-{i}", position="startpos") for i in (1, 2)]
        FakeEngine.instances = []; FakeEngine.invalid = FakeEngine.extra = FakeEngine.crash_on_go = False
        FakeEngine.mutate = None
        self.board = p.board_for("startpos")

    def parse(self, lines=None, role="default", threads=1):
        return p.validate_result(lines or reply(role, threads), self.board, config(role, threads), 1000)

    def run_profile(self, **kwargs):
        changes = {"Engine": FakeEngine, "load_positions": lambda: ({"positions": self.positions}, self.positions),
                   "source_paths": lambda: {}, "CORPUS": self.corpus,
                   "PINNED_NETWORK": p.digest(self.network),
                   "resource_check": lambda network, threads: dict(active_search_workers=threads, resident_engines=1)}
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name, value in changes.items(): stack.enter_context(patch.object(p, name, value))
            return p.profile(self.engine, self.network, self.root / "output", quiet_host=True, **kwargs)

    def test_all_fifteen_exposed_roots_and_full_matrix(self):
        _, positions = p.load_positions()
        self.assertEqual(len(positions), 15)
        self.assertEqual(len(positions) * len(p.CONFIGURATIONS) * p.REPETITIONS, 120)
        self.assertEqual(positions[0]["position"], "startpos")

    def test_corpus_refuses_missing_duplicate_and_invalid_history(self):
        document = json.loads(p.CORPUS.read_text()); path = self.root / "roots.json"
        for mutate in (lambda d: d["positions"].pop(), lambda d: d["positions"].__setitem__(1, d["positions"][0]),
                       lambda d: d["positions"][0].update(position="startpos moves e2e5")):
            bad = copy.deepcopy(document); mutate(bad); path.write_text(json.dumps(bad))
            with patch.object(p, "CORPUS", path), self.assertRaises(ValueError): p.load_positions()

    def test_explicit_recipe_threads_and_order(self):
        for item in p.CONFIGURATIONS:
            options = p.options_for(item, self.network)
            self.assertEqual(options["Threads"], str(item["threads"]))
            for name, value in {"Hash": "64", "Late Move Reductions": "true", "Ponder": "false",
                                "Search Diagnostics": "true", "Time Policy": "classic", "SyzygyProbeLimit": "0"}.items():
                self.assertEqual(options[name], value)
            self.assertEqual(options["ProbCut"], "true" if item["role"] == "all-on" else "false")
        for index in range(15): self.assertEqual(p.run_order(index, 1), p.run_order(index, 0)[::-1])
        self.assertEqual(len({p.run_order(index, 0)[0]["id"] for index in range(4)}), 4)

    def test_valid_t1_and_t8_accounting(self):
        for role in ("default", "all-on"):
            for threads in (1, 8):
                result = self.parse(role=role, threads=threads)
                self.assertEqual(sum(item["nodes"] for item in result["leader_iterations"]), result["leader_nodes"])
                self.assertEqual(sum(result["worker_nodes"]), result["reported_nodes"])
                self.assertEqual(result["leader_aborted_nodes"], 10)
                self.assertEqual(result["active_workers"], threads)
                if threads == 8: self.assertGreater(result["reported_nodes"], result["leader_nodes"])

    def test_worker_inactivity_is_reported_without_faking_participation(self):
        lines = [line.replace("30,10,10,10,10,10,10,10", "30,20,10,10,10,10,10,0") for line in reply(threads=8)]
        result = self.parse(lines, threads=8)
        self.assertEqual(result["active_workers"], 7)

    def test_smp_totals_lengths_leader_and_depth_mismatches_fail(self):
        for old, new in (("total_nodes 100", "total_nodes 101"), ("leader_nodes 30", "leader_nodes 29"),
                         ("30,10,10,10,10,10,10,10", "30,10"), ("worker_depths 1,2", "worker_depths 2,2"),
                         ("threads 8", "threads 7")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.parse([line.replace(old, new) for line in reply(threads=8)], threads=8)

    def test_leader_trace_cannot_be_replaced_by_aggregate_nodes(self):
        with self.assertRaisesRegex(ValueError, "Leader iteration"):
            self.parse([line.replace("completed false nodes 10", "completed false nodes 80") for line in reply(threads=8)], threads=8)
        with self.assertRaises(ValueError): self.parse([line for line in reply(threads=8) if "completed false" not in line], threads=8)
        with self.assertRaises(ValueError): self.parse([line.replace("nodes 40 time", "nodes 19 time") for line in reply(threads=8)], threads=8)

    def test_diagnostic_missing_duplicate_unknown_or_wrong_schema_rejected(self):
        lines = reply()
        for changed in ([line for line in lines if "string cache" not in line], lines[:-1] + [lines[-2]] + lines[-1:],
                        lines[:-2] + ["info string unknown v1 nodes 1"] + lines[-2:],
                        [line.replace("cache v1", "cache v2") for line in lines]):
            with self.assertRaises(ValueError): self.parse(changed)

    def test_optional_presence_and_enablement_follow_config(self):
        with self.assertRaises(ValueError): self.parse(reply("all-on"))
        with self.assertRaises(ValueError): self.parse(reply(), role="all-on")
        for name in p.OPTIONAL_RECORDS:
            lines = [line.replace(f"{name} v1 enabled true", f"{name} v1 enabled false") for line in reply("all-on")]
            with self.subTest(name=name), self.assertRaises(ValueError): self.parse(lines, role="all-on")

    def test_illegal_pv_bestmove_ponder_and_scores_rejected(self):
        for old, new in (("pv g1h3 g8h6", "pv g1h3 e2e4"), ("bestmove g1h3", "bestmove 0000"),
                         ("ponder g8h6", "ponder e2e4"), ("score cp 10", "score cp 10 lowerbound"), ("tbhits 0", "tbhits 1")):
            with self.subTest(new=new), self.assertRaises(ValueError): self.parse([line.replace(old, new) for line in reply()])

    def test_bad_counter_relationships_rejected(self):
        for old, new in (("losing_captures 1", "losing_captures 6"), ("matches 2", "matches 11"),
                         ("fail_highs 2", "fail_highs 3"), ("evaluations 6 cutoffs 3", "evaluations 6 cutoffs 7"),
                         ("evaluations 4 pruned 1", "evaluations 4 pruned 5"),
                         ("eligible_nodes 2 see_evaluations 3", "eligible_nodes 0 see_evaluations 3"),
                         ("extra_reductions 2", "extra_reductions 5")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.parse([line.replace(old, new) for line in reply("all-on")], role="all-on")

    def test_pruned_or_interrupted_cache_accounting_is_permitted(self):
        cache = self.parse()["diagnostics"]["cache"]
        self.assertNotEqual(cache["probes"], cache["stores"] + cache["cutoffs"])

    def test_invalid_iteration_times_budget_and_final_summary_rejected(self):
        for old, new in (("duration_ms 975.000", "duration_ms nan"), ("duration_ms 975.000", "duration_ms 9999"),
                         ("soft_ms 980", "soft_ms 1000"), ("policy classic", "policy forecast"),
                         ("completed_depth 1", "completed_depth 2"), ("stop_reason hard_time", "stop_reason external_stop")):
            with self.subTest(new=new), self.assertRaises(ValueError): self.parse([line.replace(old, new) for line in reply()])

    def test_premature_time_search_completion_rejected(self):
        for reason in ("mate_limit", "depth_limit"):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                self.parse([line.replace("stop_reason hard_time", "stop_reason " + reason) for line in reply()])

    def test_receipt_tolerance_is_not_the_hang_watchdog(self):
        for wall, mono in ((1.0, 1.0), (1.25, 1.25), (.02, .02)):
            sample = dict(elapsed_seconds=mono, wall_elapsed_seconds=wall)
            p.validate_timing(sample, 1000)
            self.assertTrue(sample["within_receipt_tolerance"])
        for wall, mono in ((1.251, 1.251), (2.0, 1.0), (1.0, 2.0), (4.0, 4.0)):
            sample = dict(elapsed_seconds=mono, wall_elapsed_seconds=wall)
            with self.assertRaises(RuntimeError): p.validate_timing(sample, 1000)
            self.assertFalse(sample["within_receipt_tolerance"])

    def test_wrong_network_rejected_before_launch(self):
        with patch.object(p, "load_positions", return_value=({}, self.positions)), patch.object(p, "source_paths", return_value={}), \
             patch.object(p, "CORPUS", self.corpus), self.assertRaisesRegex(ValueError, "pinned"):
            p.profile(self.engine, self.network, self.root / "output", quiet_host=True)
        self.assertFalse((self.root / "output").exists())
        self.assertEqual(FakeEngine.instances, [])

    def test_required_advertised_options_and_values(self):
        options = p.options_for(config("all-on", 8), self.network)
        p.validate_options(declarations(), options)
        for lines in (declarations()[1:], declarations() + declarations()[:1],
                      [line.replace("max 16384", "max 4") for line in declarations()],
                      [line.replace("Late Move Reductions type check default true", "Late Move Reductions type check default false") for line in declarations()]):
            with self.assertRaises(ValueError): p.validate_options(lines, options)

    def test_orchestration_fresh_processes_pid_exit_logs_and_summary(self):
        report = self.run_profile()
        self.assertEqual(report["status"], "complete"); self.assertEqual(len(report["samples"]), 16)
        self.assertEqual(len({sample["pid"] for sample in report["samples"]}), 16)
        self.assertTrue(all(item.closed for item in FakeEngine.instances))
        for sample in report["samples"]:
            self.assertEqual(sample["exit_code"], 0)
            self.assertEqual(sample["commands"].count("ucinewgame"), 1)
            self.assertEqual(sample["commands"].count("go movetime 1000"), 1)
            raw = [json.loads(line) for line in (self.root / "output" / sample["raw_log"]).read_text().splitlines()]
            self.assertTrue(any(event["direction"] == ">" and event["line"] == "quit" for event in raw))
        summary = report["summary"]["configurations"]["all-on-t8"]
        self.assertEqual(summary["leader_node_fraction"], .3)
        self.assertEqual(summary["branch_fractions"]["null_cutoff_per_probe"], .2)
        self.assertEqual(summary["all_workers_active_searches"], 4)
        self.assertNotIn("allocated_bytes", summary["branch_counters"]["cache"])
        pair = next(pair for pair in report["summary"]["common_depth_pairs"] if pair["threads"] == 8)
        self.assertEqual(pair["roles"]["default"]["leader_nodes_through_depth"], 20)
        self.assertEqual(pair["roles"]["default"]["reported_aggregate_nodes_at_depth"], 40)

    def test_failed_search_preserves_raw_partial_report_and_kills_child(self):
        FakeEngine.invalid = True
        with self.assertRaises(ValueError): self.run_profile()
        report = json.loads((self.root / "output/report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["samples"][0]["output"])
        self.assertEqual(report["samples"][0]["exit_code"], -9)
        self.assertTrue(FakeEngine.instances[0].closed)

    def test_nonzero_process_exit_is_retained(self):
        FakeEngine.crash_on_go = True
        with self.assertRaises(RuntimeError): self.run_profile()
        report = json.loads((self.root / "output/report.json").read_text())
        self.assertEqual(report["samples"][0]["exit_code"], 3)

    def test_trailing_output_and_input_drift_stop_without_replacement(self):
        FakeEngine.extra = True
        with self.assertRaises(ValueError): self.run_profile()
        self.assertEqual(len(FakeEngine.instances), 1)
        FakeEngine.extra = False
        FakeEngine.instances = []; FakeEngine.mutate = self.corpus
        with patch.object(p, "publish", wraps=p.publish), self.assertRaises(ValueError):
            # A separate output retains the earlier failure as well.
            with tempfile.TemporaryDirectory() as directory:
                old = self.root; self.root = Path(directory)
                try: self.run_profile()
                finally: self.root = old
        self.assertEqual(len(FakeEngine.instances), 1)

    def test_existing_output_and_unbounded_parameters_refused(self):
        for value in (0, 99, 1001, True, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError): self.run_profile(movetime_ms=value)
        (self.root / "output").mkdir()
        marker = self.root / "output/keep"; marker.write_text("retained")
        with self.assertRaises(ValueError): self.run_profile()
        self.assertEqual(marker.read_text(), "retained")
        self.assertEqual(FakeEngine.instances, [])
        with self.assertRaises(ValueError): p.profile(self.engine, self.network, self.root / "different")

    def test_incomplete_duplicate_or_bad_exit_matrix_refused(self):
        report = self.run_profile(); samples = report["samples"]
        for broken in (samples[:-1], samples + samples[:1]):
            with self.assertRaises(ValueError): p.summarize(broken, self.positions)
        samples[0]["exit_code"] = 2
        with self.assertRaises(ValueError): p.summarize(samples, self.positions)

    def monitor(self):
        with patch.object(p.time, "time", return_value=100), patch.object(p.time, "monotonic", return_value=10):
            return p.Monitor(self.network, [])

    def test_monitor_clocks_total_limit_and_resource_changes(self):
        for wall, mono in ((107, 11), (106, 14), (107, 17), (99, 11), (101, 9)):
            monitor = self.monitor()
            with patch.object(p.time, "time", return_value=wall), patch.object(p.time, "monotonic", return_value=mono), self.assertRaises(RuntimeError): monitor.check()
        monitor = self.monitor(); monitor.deadline = 11
        with patch.object(p.time, "time", return_value=101), patch.object(p.time, "monotonic", return_value=11), self.assertRaises(TimeoutError): monitor.check()
        monitor = self.monitor()
        with patch.object(p.time, "time", return_value=101), patch.object(p.time, "monotonic", return_value=11), \
             patch.object(p, "resource_check", side_effect=ValueError("budget decreased")), self.assertRaises(ValueError): monitor.check()

    def test_cpu_memory_and_unknown_memory_resource_rejection(self):
        policy = dict(max_cpu_workers=9, memory_fraction=.5)
        with patch.object(p, "current_budget", return_value=policy), patch.object(p, "physical_memory", return_value=64 * 1024**3):
            self.assertGreaterEqual(p.resource_check(self.network, 8)["estimated_memory_bytes"], 2 * 1024**3)
            policy["max_cpu_workers"] = 7
            with self.assertRaises(ValueError): p.resource_check(self.network, 8)
        with patch.object(p, "current_budget", return_value=dict(max_cpu_workers=9, memory_fraction=.5)), \
             patch.object(p, "physical_memory", return_value=2 * 1024**3), self.assertRaises(ValueError): p.resource_check(self.network, 8)


if __name__ == "__main__":
    unittest.main()
