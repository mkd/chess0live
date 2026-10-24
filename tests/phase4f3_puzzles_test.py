#!/usr/bin/env python3
"""Synthetic protocol, timing and provenance checks for the Phase 4F.3 audit.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_phase4f3_puzzles as p


def reply(score="cp 10", pv="g1h3 g8h6", best="g1h3", ponder="g8h6"):
    return [f"info depth 1 seldepth 2 score {score} nodes 20 time 10 nps 2000 hashfull 0 tbhits 0 pv {pv}",
            "info nodes 25 time 12 nps 2083 hashfull 0 tbhits 0",
            "bestmove " + best + (" ponder " + ponder if ponder else "")]


def declarations():
    lines = []
    for name, kind in p.OPTION_TYPES.items():
        default = p.ADVERTISED_DEFAULTS.get(name, "network")
        tail = (f" default {default} min 0 max 16384" if kind == "spin" else
                " default classic var classic var forecast var bounded" if name == "Time Policy" else
                " default mvv-lva var mvv-lva var see" if name == "Capture Ordering" else f" default {default}")
        lines.append("option name " + name + " type " + kind + tail)
    return lines + ["uciok"]


class Process:
    def __init__(self): self.done = False; self.killed = False
    def poll(self): return 0 if self.done else None
    def kill(self): self.killed = self.done = True
    def wait(self, timeout=None): self.done = True; return 0


class FakeEngine:
    instances = []
    invalid = False
    extra_after_best = False
    mutate = None

    def __init__(self, path, cwd=None):
        self.path, self.process, self.lines = path, Process(), queue.Queue()
        self.transcript, self.commands, self.closed = [], [], False
        self.instances.append(self)

    def send(self, command):
        self.commands.append(command)
        if command == "uci": output = declarations()
        elif command == "isready": output = ["readyok"]
        elif command.startswith("go "):
            score = "cp 20" if "setoption name ProbCut value true" in self.commands else "cp 10"
            output = reply(score=score, best="e2e5" if self.invalid else "g1h3")
            if self.extra_after_best: output.append("info nodes 30 time 15 nps 2000 hashfull 0 tbhits 0")
            if self.mutate: self.mutate.write_bytes(b"changed")
        elif command == "quit": self.process.done = True; output = []
        else: output = []
        for line in output: self.lines.put(line)

    def close(self): self.closed = self.process.done = True


class PuzzleAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.engine, self.network, self.corpus = [self.root / item for item in ("engine", "network", "corpus")]
        for path in (self.engine, self.network, self.corpus): path.write_bytes(b"synthetic asset")
        self.positions = [dict(id=f"puzzle-{i:02d}", fen=p.chess.STARTING_FEN, supplied_mate=7,
                               spreadsheet_row=i) for i in (1, 2)]
        FakeEngine.instances = []
        FakeEngine.invalid = FakeEngine.extra_after_best = False
        FakeEngine.mutate = None

    def run_audit(self, **kwargs):
        with ExitStack() as stack:
            changes = {"ENGINE": self.engine, "NETWORK": self.network,
                       "ENGINE_SHA256": p.digest(self.engine), "NETWORK_SHA256": p.digest(self.network),
                       "Engine": FakeEngine, "load_positions": lambda: self.positions,
                       "asset_paths": lambda: dict(engine=self.engine, network=self.network, corpus=self.corpus),
                       "resource_check": lambda _: dict(active_search_workers=8, resident_engines=1)}
            for name, value in changes.items(): stack.enter_context(patch.object(p, name, value))
            return p.audit(kwargs.get("mode", "smoke"), kwargs.get("output", self.root / "output"),
                           allow_daytime=kwargs.get("allow_daytime", False))

    def test_all_owner_positions_and_annotations_preserved(self):
        before = p.digest(p.OWNER_SOURCE)
        positions = p.load_positions()
        self.assertEqual(len(positions), 39)
        self.assertEqual([positions[0]["supplied_mate"], positions[-1]["supplied_mate"]], [7, 18])
        self.assertEqual(positions, p.extract_positions(p.OWNER_SOURCE))
        self.assertEqual(before, p.digest(p.OWNER_SOURCE))

    def test_corpus_source_hash_or_content_drift_rejected(self):
        document = json.loads(p.CORPUS.read_text())
        path = self.root / "positions.json"
        for field, value in (("owner_source_sha256", "0" * 64), ("positions", [])):
            bad = dict(document, **{field: value}); path.write_text(json.dumps(bad))
            with patch.object(p, "CORPUS", path), self.assertRaises(ValueError): p.load_positions()

    def test_source_is_not_executed_and_nonliteral_rejected(self):
        path = self.root / "owner.py"
        path.write_text("raise RuntimeError('must not execute')\n" + p.OWNER_SOURCE.read_text())
        self.assertEqual(len(p.extract_positions(path)), 39)
        path.write_text("FENS = make_fens()\n")
        with self.assertRaises(ValueError): p.extract_positions(path)

    def test_missing_mate_annotation_rejected(self):
        path = self.root / "owner.py"
        path.write_text(p.OWNER_SOURCE.read_text().replace("# M7, spreadsheet row 4", "# unknown"))
        with self.assertRaisesRegex(ValueError, "annotation"): p.extract_positions(path)

    def test_explicit_matched_options_and_only_package_differences(self):
        for role in p.OPTIONS:
            options = p.OPTIONS[role]
            for name, value in {"Threads": "8", "Hash": "64", "Ponder": "false", "Search Diagnostics": "false",
                                "Time Policy": "classic", "Late Move Reductions": "true",
                                "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0"}.items():
                self.assertEqual(options[name], value)
        differences = {name for name in p.BASE_OPTIONS if p.BASE_OPTIONS[name] != p.PACKAGE_OPTIONS[name]}
        self.assertEqual(differences, {"Deep Quiet Reductions", "Capture Ordering", "Countermove Ordering",
                                      "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut"})
        self.assertEqual(p.role_order(0), tuple(reversed(p.role_order(1))))

    def test_exact_mode_limits(self):
        self.assertEqual(p.MODES["smoke"]["movetime_ms"], 1000)
        self.assertEqual(p.MODES["full"]["movetime_ms"], 60000)
        self.assertLessEqual(p.MODES["smoke"]["total_seconds"], 600)

    def test_full_window_daytime_and_insufficient_time_refused(self):
        for hour in (12, 7, 22, 6):
            with self.subTest(hour=hour), self.assertRaises(ValueError):
                p.night_window("full", datetime(2026, 10, 24, hour, tzinfo=ZoneInfo("Europe/Helsinki")))
        self.assertIsNone(p.night_window("smoke", datetime(2026, 10, 24, 12, tzinfo=timezone.utc))["cutoff_utc"])

    def test_night_window_handles_dst_and_requires_aware_clock(self):
        result = p.night_window("full", datetime(2026, 10, 24, 23, tzinfo=ZoneInfo("Europe/Helsinki")))
        self.assertEqual(result["cutoff_utc"], "2026-10-25T05:00:00+00:00")
        with self.assertRaises(ValueError): p.night_window("full", datetime(2026, 10, 24))

    def test_explicit_daytime_launch_keeps_next_cutoff(self):
        now = datetime(2026, 10, 24, 12, tzinfo=ZoneInfo("Europe/Helsinki"))
        with self.assertRaisesRegex(ValueError, "fresh explicit owner authorization"):
            p.night_window("full", now)
        result = p.night_window("full", now, allow_daytime=True)
        self.assertTrue(result["allow_daytime"])
        self.assertFalse(result["nighttime"])
        self.assertEqual(result["cutoff_utc"], "2026-10-25T05:00:00+00:00")
        self.assertEqual(result["minimum_remaining_seconds"], 5070)

    def test_daytime_flag_does_not_remove_minimum_remaining_time(self):
        now = datetime(2026, 10, 24, 6, tzinfo=ZoneInfo("Europe/Helsinki"))
        with self.assertRaisesRegex(ValueError, "84.5 minutes"):
            p.night_window("full", now, allow_daytime=True)

    def test_daytime_flag_rejected_for_smoke_and_nonboolean_calls(self):
        for mode, value in (("smoke", True), ("full", 1), ("full", "true")):
            with self.subTest(mode=mode, value=value), self.assertRaises(ValueError):
                p.night_window(mode, allow_daytime=value)
            with self.subTest(mode=mode, value=value), self.assertRaises(ValueError):
                self.run_audit(mode=mode, allow_daytime=value)
        self.assertEqual(FakeEngine.instances, [])

    def test_explicit_full_flag_is_recorded_without_claiming_authorization(self):
        window = p.night_window("full", datetime(2026, 10, 24, 12, tzinfo=ZoneInfo("Europe/Helsinki")),
                                allow_daytime=True)
        # Synthetic engines and a future cutoff only: this test starts no real search.
        window["cutoff_utc"] = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
        with patch.object(p, "night_window", return_value=window) as check_window:
            report = self.run_audit(mode="full", allow_daytime=True)
        check_window.assert_called_once_with("full", allow_daytime=True)
        self.assertTrue(report["allow_daytime"] and report["launch_window"]["allow_daytime"])
        self.assertIn("not verified approval", report["authorization_note"])
        self.assertTrue(all("go movetime 60000" in sample["commands"] for sample in report["samples"]))

    def test_cli_passes_only_explicit_daytime_flag(self):
        with patch.object(p, "audit") as audit:
            p.main(["--mode", "full", "--output", str(self.root / "output"), "--allow-daytime"])
            audit.assert_called_once_with("full", self.root / "output", allow_daytime=True)
        with patch.object(p, "audit") as audit:
            p.main(["--mode", "full", "--output", str(self.root / "output")])
            audit.assert_called_once_with("full", self.root / "output", allow_daytime=False)

    def monitor(self, wall=100, mono=10, cutoff=None):
        with patch.object(p.time, "time", return_value=wall), patch.object(p.time, "monotonic", return_value=mono):
            return p.Monitor("smoke", {"cutoff_utc": cutoff}, self.network, [])

    def check_at(self, monitor, wall, mono):
        with patch.object(p.time, "time", return_value=wall), patch.object(p.time, "monotonic", return_value=mono), \
             patch.object(p, "resource_check", return_value={"active_search_workers": 8}):
            monitor.check()

    def test_monitored_suspend_wall_jump_and_scheduler_gap_rejected(self):
        for wall, mono in ((107, 11), (107, 17), (106, 14), (90, 11), (101, 9)):
            with self.subTest(wall=wall, mono=mono), self.assertRaises(RuntimeError):
                self.check_at(self.monitor(), wall, mono)

    def test_monitored_small_steps_do_not_hide_cumulative_clock_drift(self):
        monitor = self.monitor()
        self.check_at(monitor, 103, 11)
        self.check_at(monitor, 106, 12)
        with self.assertRaises(RuntimeError): self.check_at(monitor, 109, 13)

    def test_cutoff_and_total_deadline_enforced_during_poll(self):
        cutoff = datetime.fromtimestamp(101, timezone.utc).isoformat()
        with self.assertRaises(TimeoutError): self.check_at(self.monitor(cutoff=cutoff), 101, 11)
        monitor = self.monitor(); monitor.deadline = 11
        with self.assertRaises(TimeoutError): self.check_at(monitor, 101, 11)

    def test_receipt_tolerance_is_separate_from_hang_watchdog(self):
        for elapsed in (.01, 1.0, 1.25):
            sample = dict(elapsed_seconds=elapsed, wall_elapsed_seconds=elapsed)
            p.validate_search_timing(sample, 1000)
            self.assertTrue(sample["within_receipt_tolerance"])
        for wall, mono in ((1.251, 1.251), (1.4, 1.0), (1.0, 1.4)):
            sample = dict(elapsed_seconds=mono, wall_elapsed_seconds=wall)
            with self.assertRaisesRegex(RuntimeError, "no resampling"): p.validate_search_timing(sample, 1000)
            self.assertFalse(sample["within_receipt_tolerance"])

    def test_resources_rechecked_and_unknown_ram_rejected(self):
        policy = dict(max_cpu_workers=9, memory_fraction=.5)
        with patch.object(p, "current_budget", return_value=policy), patch.object(p, "physical_memory", return_value=64 * 1024**3):
            result = p.resource_check(self.network)
            self.assertEqual(result["active_search_workers"], 8)
            self.assertGreaterEqual(result["estimated_memory_bytes"], 2 * 1024**3)
            policy["max_cpu_workers"] = 7
            with self.assertRaises(ValueError): p.resource_check(self.network)
        with patch.object(p, "current_budget", return_value=dict(max_cpu_workers=9, memory_fraction=.5)), \
             patch.object(p, "physical_memory", return_value=None), patch.object(p.sys, "platform", "linux"):
            with self.assertRaisesRegex(ValueError, "RAM"): p.resource_check(self.network)

    def test_memory_allowance_enforced(self):
        with patch.object(p, "current_budget", return_value=dict(max_cpu_workers=9, memory_fraction=.5)), \
             patch.object(p, "physical_memory", return_value=2 * 1024**3), self.assertRaises(ValueError):
            p.resource_check(self.network)

    def test_legal_cp_and_mate_are_recorded_separately(self):
        result = p.validate_result(reply(), p.chess.STARTING_FEN, 7)
        self.assertEqual(result["score_cp"], 10); self.assertIsNone(result["reported_mate"])
        for value in (7, 8, -7):
            result = p.validate_result(reply(score=f"mate {value}"), p.chess.STARTING_FEN, 7)
            self.assertEqual(result["reported_mate"], value); self.assertIsNone(result["score_cp"])
            self.assertEqual(result["reported_mate_matches_supplied"], value == 7)
            self.assertFalse(result["final_pv_ends_in_checkmate"])
            self.assertIn("does not prove", result["mate_evidence_note"])

    def test_every_pv_bestmove_and_ponder_must_be_legal(self):
        for change in (dict(pv="g1h3 e2e4"), dict(best="e2e5"), dict(ponder="e2e4"), dict(best="0000")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.validate_result(reply(**change), p.chess.STARTING_FEN, 7)

    def test_unknown_bounds_diagnostics_tablebase_hits_and_missing_totals_fail(self):
        for old, new in (("score cp 10", "score cp 10 lowerbound"), ("tbhits 0", "tbhits 1"), ("tbhits 0", "")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                p.validate_result([line.replace(old, new) for line in reply()], p.chess.STARTING_FEN, 7)
        for lines in (["info string smp workers 8"] + reply(), reply()[:1] + reply()[2:]):
            with self.assertRaises(ValueError): p.validate_result(lines, p.chess.STARTING_FEN, 7)

    def test_required_options_validated(self):
        options = dict(p.BASE_OPTIONS, EvalFile="network")
        p.validate_options(declarations(), options)
        for lines in (declarations()[1:], declarations() + declarations()[:1],
                      [line.replace("max 16384", "max 2") for line in declarations()],
                      [line.replace("type check", "type string") for line in declarations()]):
            with self.assertRaises(ValueError): p.validate_options(lines, options)

    def test_advertised_search_defaults_cannot_drift(self):
        for name in ("Late Move Reductions", "Deep Quiet Reductions", "ProbCut", "Capture Ordering"):
            lines = [line.replace(" default " + p.ADVERTISED_DEFAULTS[name], " default wrong")
                     if line.startswith("option name " + name + " type ") else line for line in declarations()]
            with self.assertRaisesRegex(ValueError, "Advertised default"):
                p.validate_options(lines, dict(p.BASE_OPTIONS, EvalFile="network"))

    def test_complete_different_searches_are_allowed_and_processes_fresh(self):
        report = self.run_audit()
        self.assertEqual(report["status"], "complete")
        self.assertFalse(report["allow_daytime"])
        self.assertEqual(report["summary"]["searches"], 4)
        self.assertEqual([s["role"] for s in report["samples"]], ["default", "all-on", "all-on", "default"])
        self.assertEqual(len(FakeEngine.instances), 4)
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))
        self.assertNotEqual(report["samples"][0]["result"]["score_cp"], report["samples"][1]["result"]["score_cp"])
        for sample in report["samples"]:
            self.assertEqual(sample["commands"].count("go movetime 1000"), 1)
            events = [json.loads(line) for line in (self.root / "output" / sample["raw_log"]).read_text().splitlines()]
            self.assertTrue(any(event["line"] == "go movetime 1000" and event["direction"] == ">" for event in events))
            self.assertTrue(any(event["line"].startswith("bestmove") and event["direction"] == "<" for event in events))

    def test_failed_case_keeps_partial_report_and_raw_evidence(self):
        FakeEngine.invalid = True
        with self.assertRaises(ValueError): self.run_audit()
        report = json.loads((self.root / "output/report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["samples"][0]["status"], "failed")
        self.assertTrue(report["samples"][0]["output"])
        self.assertTrue(FakeEngine.instances[0].closed and FakeEngine.instances[0].process.killed)

    def test_post_bestmove_output_rejected(self):
        FakeEngine.extra_after_best = True
        with self.assertRaisesRegex(ValueError, "after bestmove"): self.run_audit()

    def test_changed_input_stops_before_next_search(self):
        FakeEngine.mutate = self.corpus
        with self.assertRaisesRegex(ValueError, "changed"): self.run_audit()
        self.assertEqual(len(FakeEngine.instances), 1)
        report = json.loads((self.root / "output/report.json").read_text())
        self.assertEqual(report["status"], "failed")

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "output"; output.mkdir(); marker = output / "keep"; marker.write_text("untouched")
        with self.assertRaisesRegex(ValueError, "already exists"): self.run_audit()
        self.assertEqual(marker.read_text(), "untouched")
        self.assertEqual(FakeEngine.instances, [])

    def test_incomplete_and_duplicate_matrices_rejected(self):
        report = self.run_audit(); samples = report["samples"]
        for invalid in (samples[:-1], samples + samples[:1]):
            with self.assertRaises(ValueError): p.summarize(invalid, self.positions)
        samples[0]["status"] = "failed"
        with self.assertRaises(ValueError): p.summarize(samples, self.positions)

    def test_full_rejection_before_engine_launch(self):
        with patch.object(p, "night_window", side_effect=ValueError("night window required")), self.assertRaises(ValueError):
            self.run_audit(mode="full")
        self.assertEqual(FakeEngine.instances, [])

    def test_poll_detects_exit_and_timeout_without_search(self):
        monitor = self.monitor(wall=p.time.time(), mono=p.time.monotonic())
        engine = FakeEngine(self.engine); engine.lines.put(None)
        with (self.root / "raw.jsonl").open("w") as raw, patch.object(p, "resource_check", return_value={}):
            with self.assertRaisesRegex(RuntimeError, "exited"): p.read_until(engine, "bestmove ", 1, monitor, raw, [])
            with self.assertRaises(TimeoutError): p.read_until(engine, "bestmove ", 0, monitor, raw, [])


if __name__ == "__main__":
    unittest.main()
