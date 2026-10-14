#!/usr/bin/env python3
"""Validate LMR comparison evidence with bounded synthetic protocol peers.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_lmr as profiler


def replies(enabled=False, nodes=False):
    total = 100 if nodes else (80 if enabled else 140)
    lines = ["info depth 1 seldepth 1 score cp 15 nodes 40 time 1 pv e2e4",
             "info string search-iteration v1 depth 1 completed true nodes 40 duration_ms 1.000 elapsed_ms 1.000"]
    if not nodes:
        lines.append(f"info depth 2 seldepth 2 score cp {12 if enabled else 8} nodes {total} time 2 pv e2e4 e7e5")
    lines += [f"info string search-iteration v1 depth 2 completed {'false' if nodes else 'true'} nodes {total - 40} duration_ms 1.000 elapsed_ms 2.000",
              f"info string lmr v1 enabled {str(enabled).lower()} reductions {10 if enabled else 0} researches {3 if enabled else 0} fail_lows {2 if enabled else 0} verified_cutoffs {1 if enabled else 0}",
              f"info string search-summary v1 policy classic forecast_active false stop_reason {'node_limit' if nodes else 'depth_limit'} nodes {total} completed_depth {1 if nodes else 2} elapsed_ms 2.000 soft_ms 0.000 hard_ms 0.000 target_ms 0.000 predicted_next_ms 0.000",
              "bestmove e2e4 ponder e7e5"]
    return lines


class ValidationTests(unittest.TestCase):
    def test_changed_search_work_and_scores_are_retained_not_rejected(self):
        a = profiler.validate_result(replies(False), False, profiler.board_for("startpos"), 2, None)
        b = profiler.validate_result(replies(True), True, profiler.board_for("startpos"), 2, None)
        result = profiler.summarize([{"position_index": 0, "repetition": 0, "enabled": flag, "result": value}
                                    for flag, value in ((False, a), (True, b))])
        self.assertEqual(result["pairs"][0]["nodes_off_on"], [140, 80])
        self.assertFalse(result["pairs"][0]["same_final_score"])
        self.assertTrue(result["pairs"][0]["same_bestmove"])

    def test_fixed_nodes_keeps_last_completed_depth_and_aborted_work(self):
        result = profiler.validate_result(replies(True, True), True, profiler.board_for("startpos"), None, 100)
        self.assertEqual(result["trace"]["summary"]["completed_depth"], 1)
        self.assertEqual(result["trace"]["aborted_nodes"], 60)
        self.assertEqual(result["lmr"]["researches"], 3)
        with self.assertRaises(ValueError): profiler.validate_result(replies(True, True), True, profiler.board_for("startpos"), None, 99)
        with self.assertRaises(ValueError): profiler.validate_result(replies(True, True), True, profiler.board_for("startpos"), None, 101)

    def test_node_stop_before_any_completed_depth_still_validates_ponder(self):
        lines = ["info string search-iteration v1 depth 1 completed false nodes 1 duration_ms 0.000 elapsed_ms 0.000",
                 "info string lmr v1 enabled false reductions 0 researches 0 fail_lows 0 verified_cutoffs 0",
                 "info string search-summary v1 policy classic forecast_active false stop_reason node_limit nodes 1 completed_depth 0 elapsed_ms 0.000 soft_ms 0.000 hard_ms 0.000 target_ms 0.000 predicted_next_ms 0.000",
                 "bestmove e2e4 ponder e7e5"]
        result = profiler.validate_result(lines, False, profiler.board_for("startpos"), None, 1)
        self.assertEqual(result["signature"]["iterations"], [])
        with self.assertRaises(ValueError):
            profiler.validate_result([s.replace("ponder e7e5", "ponder e2e3") for s in lines], False, profiler.board_for("startpos"), None, 1)

    def test_every_completed_pv_and_bestmove_must_be_legal(self):
        lines = replies(True)
        for before, after in (("pv e2e4 e7e5", "pv e2e4 e2e3"), ("pv e2e4\n", "pv e2e5\n"),
                              ("ponder e7e5", "ponder e2e3"), ("e2e4", "e2e5")):
            changed = "\n".join(lines).replace(before, after).splitlines()
            with self.subTest(before=before), self.assertRaises(ValueError):
                profiler.validate_result(changed, True, profiler.board_for("startpos"), 2, None)

    def test_invalid_counter_partitions_schema_and_enabled_state_fail(self):
        lines = replies(True)
        changes = [("researches 3", "researches 11"), ("fail_lows 2", "fail_lows 3"),
                   ("reductions 10", "reductions -1"), ("reductions 10", "reductions nan"),
                   ("enabled true", "enabled false"), ("lmr v1", "lmr v2"),
                   ("fail_lows 2", "researches 2")]
        for before, after in changes:
            with self.subTest(before=before), self.assertRaises(ValueError):
                profiler.validate_result([s.replace(before, after) for s in lines], True, profiler.board_for("startpos"), 2, None)
        with self.assertRaises(ValueError):
            profiler.validate_result([s.replace("enabled true", "enabled false") for s in lines], False, profiler.board_for("startpos"), 2, None)
        for changed in ([s for s in lines if not s.startswith("info string lmr")], lines[:-1] + [lines[-3], lines[-1]]):
            with self.assertRaises(ValueError): profiler.validate_result(changed, True, profiler.board_for("startpos"), 2, None)

    def test_opening_history_legality_and_repetition_are_checked(self):
        board = profiler.board_for("startpos moves e2e4 e7e5 g1f3")
        self.assertEqual(len(board.move_stack), 3)
        with self.assertRaises(ValueError): profiler.board_for("startpos moves e2e5")
        with self.assertRaises(ValueError): profiler.board_for("startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8")


class FakeEngine:
    instances = []
    failure = None
    mutate = None

    def __init__(self, path):
        self.enabled, self.sent, self.transcript = False, [], []
        self.instances.append(self)

    def send(self, command):
        self.sent.append(command)
        if command.startswith("setoption name Late Move Reductions"):
            self.enabled = command.endswith("true")

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            lines = [f"option name {name} type {kind}" for name, kind in
                     (("Hash", "spin"), ("Threads", "spin"), ("EvalFile", "string"), ("Ponder", "check"),
                      ("Time Policy", "combo"), ("Search Diagnostics", "check"), ("Late Move Reductions", "check"))] + ["uciok"]
        elif prefix == "readyok":
            if self.failure == "preparation" and "ucinewgame" in self.sent:
                self.transcript.append("info string preparing test root")
                raise TimeoutError("Injected readiness timeout")
            lines = ["readyok"]
        else:
            lines = replies(self.enabled, self.sent[-1].startswith("go nodes"))
            if self.failure == "timeout":
                self.transcript.extend(lines[:1]); raise TimeoutError("Injected timeout")
            if self.failure == "illegal": lines = [s.replace("e7e5", "e2e3") for s in lines]
            if self.mutate: self.mutate.write_text("changed artifact")
        self.transcript.extend(lines)
        return lines

    def __enter__(self): return self
    def __exit__(self, *_): pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-lmr-profile-")
        self.root = Path(self.temporary.name)
        self.binary, self.network, self.positions = [self.root / name for name in ("engine", "network", "positions.json")]
        self.binary.write_text("fake engine"); self.network.write_text("fake network")
        self.positions.write_text(json.dumps({"openings": [{"id": "original-test", "moves": []}]}))
        self.output = self.root / "profile.json"
        FakeEngine.instances, FakeEngine.failure, FakeEngine.mutate = [], None, None

    def tearDown(self): self.temporary.cleanup()

    def run_profile(self, **kwargs):
        with patch.object(profiler, "Engine", FakeEngine), patch.object(profiler, "resource_check", return_value={"active_search_workers": 1}):
            return profiler.profile(self.binary, self.network, self.positions, self.output, **kwargs)

    def test_full_evidence_alternation_and_state_reset(self):
        report = self.run_profile(depth=2)
        self.assertEqual(report["status"], "complete")
        self.assertEqual([s["enabled"] for s in report["samples"]], [False, True, True, False])
        self.assertEqual(report["assets"]["binary"]["sha256"], report["after_sha256"]["binary"])
        self.assertEqual(report["protocol_output"], FakeEngine.instances[0].transcript)
        for s in report["samples"]:
            self.assertEqual(s["preparation_commands"][-3:], ["ucinewgame", "position startpos", "isready"])
            self.assertEqual(s["go"], "go depth 2")
        with self.assertRaises(ValueError): self.run_profile(depth=2)

    def test_nodes_limit_uses_no_depth_and_preserves_aborted_work(self):
        report = self.run_profile(nodes=100, repeats=1)
        self.assertTrue(all(s["go"] == "go nodes 100" for s in report["samples"]))
        self.assertEqual(report["summary"]["policies"]["on"]["aborted_nodes"], 60)

    def test_illegal_pv_and_timeout_preserve_failure_evidence(self):
        for failure, error in (("illegal", ValueError), ("timeout", TimeoutError)):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(error): self.run_profile(depth=2)
                report = json.loads(self.output.read_text())
                self.assertEqual(report["status"], "invalid_or_interrupted")
                self.assertTrue(report["samples"][0]["output"])
                self.assertNotIn("summary", report)
                self.output.unlink()

    def test_frozen_asset_mutation_invalidates_summary(self):
        FakeEngine.mutate = self.network
        with self.assertRaisesRegex(ValueError, "artifact changed"): self.run_profile(depth=2)
        report = json.loads(self.output.read_text())
        self.assertNotIn("summary", report)
        self.assertNotEqual(report["assets"]["network"]["sha256"], report["after_sha256"]["network"])

    def test_preparation_timeout_preserves_partial_replies_before_search(self):
        FakeEngine.failure = "preparation"
        with self.assertRaises(TimeoutError): self.run_profile(depth=2)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["samples"][0]["preparation_output"], ["info string preparing test root"])
        self.assertFalse(any(command.startswith("go ") for command in FakeEngine.instances[0].sent))
        self.assertNotIn("summary", report)

    def test_limits_and_timeout_reject_unbounded_or_conflicting_requests(self):
        for kwargs in ({"depth": 2, "nodes": 100}, {"nodes": 0}, {"depth": 13}, {"search_timeout": float("nan")}, {"search_timeout": 301}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.run_profile(**kwargs)
        self.assertFalse(FakeEngine.instances)


if __name__ == "__main__": unittest.main()
