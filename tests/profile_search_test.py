#!/usr/bin/env python3
"""Exercise profiler evidence and failure handling without expensive searches.

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
import profile_search as profiler


def reply(policy="classic"):
    return [
        "info depth 1 seldepth 2 score cp 15 nodes 40 time 1 pv e2e4 e7e5",
        "info string search-iteration v1 depth 1 completed true nodes 40 duration_ms 1.100 elapsed_ms 1.100",
        "info string search-iteration v1 depth 2 completed false nodes 60 duration_ms 3.500 elapsed_ms 4.600",
        f"info string search-summary v1 policy {policy} forecast_active {'true' if policy == 'forecast' else 'false'} stop_reason hard_time nodes 100 completed_depth 1 elapsed_ms 4.600 soft_ms 1.000 hard_ms 4.600 target_ms 1.000 predicted_next_ms 0.000",
        "bestmove e2e4 ponder e7e5",
    ]


class AccountingTests(unittest.TestCase):
    def test_aborted_nodes_are_counted_separately_from_completed_uci_nodes(self):
        result = profiler.diagnostics(reply(), "classic")
        self.assertEqual(result["summary"]["nodes"], 100)
        self.assertEqual(result["aborted_nodes"], 60)
        self.assertEqual(result["aborted_duration_ms"], 3.5)
        self.assertEqual(result["bestmove"], "e2e4")

    def test_corrupt_counts_depths_and_durations_cannot_generate_a_summary(self):
        changes = [("stop_reason hard_time nodes 100", "stop_reason hard_time nodes 101"),
                   ("completed_depth 1", "completed_depth 2"),
                   ("score cp 15 nodes 40", "score cp 15 nodes 41"),
                   ("depth 2 completed false", "depth 3 completed false"),
                   ("duration_ms 3.500", "duration_ms 4.500"),
                   ("elapsed_ms 4.600 soft_ms", "elapsed_ms 0.100 soft_ms"),
                   ("duration_ms 3.500", "duration_ms NaN"),
                   ("soft_ms 1.000", "soft_ms 5.000"),
                   ("search-summary v1", "search-summary v2"),
                   ("completed true", "completed yes"),
                   ("policy classic", "policy forecast"),
                   ("forecast_active false", "forecast_active true")]
        for before, after in changes:
            with self.subTest(before=before), self.assertRaises(ValueError):
                profiler.diagnostics([line.replace(before, after) for line in reply()], "classic")

    def test_missing_duplicate_aborted_and_engine_error_reports_fail(self):
        lines = reply()
        cases = [lines[:-1], lines[:3] + lines[4:], lines[:3] + [lines[3]] + lines[3:],
                 lines[:3] + [lines[2].replace("depth 2", "depth 3")] + lines[3:],
                 lines + ["info string error: malformed position"],
                 lines[:-1] + ["bestmove 0000"], lines[:-1] + ["bestmove e2e4 ponder bogus"],
                 lines[:3] + [lines[4], lines[3]], lines + ["info string late output"]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                profiler.diagnostics(case, "classic")

    def test_different_policy_decisions_are_allowed(self):
        changed = [line.replace("e2e4", "d2d4").replace("nodes 40", "nodes 50").replace("nodes 100", "nodes 110")
                   for line in reply("forecast")]
        classic = profiler.diagnostics(reply(), "classic")
        forecast = profiler.diagnostics(changed, "forecast")
        self.assertNotEqual(classic["bestmove"], forecast["bestmove"])
        self.assertNotEqual(classic["summary"]["nodes"], forecast["summary"]["nodes"])

    def test_terminal_root_is_not_mistaken_for_a_completed_iteration(self):
        lines = ["info depth 0 seldepth 0 score mate 0 nodes 0 time 0 pv",
                 "info string search-summary v1 policy classic forecast_active false stop_reason terminal nodes 0 completed_depth 0 elapsed_ms 0.000 soft_ms 1.000 hard_ms 4.000 target_ms 1.000 predicted_next_ms 0.000",
                 "bestmove 0000"]
        result = profiler.diagnostics(lines, "classic")
        self.assertEqual(result["iterations"], [])
        self.assertEqual(result["summary"]["nodes"], 0)

    def test_zero_node_first_iteration_and_rounded_times_remain_valid(self):
        lines = ["info string search-iteration v1 depth 1 completed false nodes 0 duration_ms 0.001 elapsed_ms 0.000",
                 "info string search-summary v1 policy classic forecast_active false stop_reason hard_time nodes 0 completed_depth 0 elapsed_ms 0.000 soft_ms 0.000 hard_ms 0.000 target_ms 0.000 predicted_next_ms 0.000",
                 "bestmove e2e4"]
        self.assertEqual(profiler.diagnostics(lines, "classic")["aborted_nodes"], 0)

    def test_position_history_is_preserved_and_protocol_injection_rejected(self):
        document = {"openings": [{"id": "repeat", "moves": ["g1f3", "g8f6", "f3g1", "f6g8"]}]}
        self.assertEqual(profiler.positions_from(document, 0)[0]["position"], "startpos moves g1f3 g8f6 f3g1 f6g8")
        for entry in ({"id": "bad", "moves": ["e2e4\nquit"]},
                      {"id": "bad", "moves": [], "fen": "8/8/8/8/8/8/8/8 w - - 0\n1"}):
            with self.assertRaises(ValueError): profiler.positions_from({"openings": [entry]}, 0)
        with self.assertRaises(ValueError): profiler.positions_from({"openings": document["openings"] * 2}, 0)


class FakeEngine:
    """A deterministic protocol peer with injectable evidence failures."""
    instances = []
    failure = None
    mutate = None

    def __init__(self, path):
        self.sent, self.transcript, self.policy = [], [], "classic"
        self.instances.append(self)

    def send(self, command):
        self.sent.append(command)
        if command.startswith("setoption name Time Policy"):
            self.policy = command.split()[-1]

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            lines = [f"option name {name} type {kind}" for name, kind in
                     (("Hash", "spin"), ("Threads", "spin"), ("EvalFile", "string"), ("Ponder", "check"),
                      ("Move Overhead", "spin"), ("Time Policy", "combo"), ("Search Diagnostics", "check"))] + ["uciok"]
        elif prefix == "readyok":
            lines = ["info string error: illegal move"] if self.failure == "position" and "ucinewgame" in self.sent else ["readyok"]
        else:
            lines = reply(self.policy)
            if self.failure == "timeout":
                self.transcript.extend(lines[:1])
                raise TimeoutError("Injected bounded search timeout")
            if self.failure == "counts":
                lines = [line.replace("stop_reason hard_time nodes 100", "stop_reason hard_time nodes 101") for line in lines]
            if self.mutate:
                self.mutate.write_text("artifact changed")
        self.transcript.extend(lines)
        return lines

    def __enter__(self): return self
    def __exit__(self, *_): pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-profile-test-")
        self.root = Path(self.temporary.name)
        self.binary, self.network, self.positions = [self.root / name for name in ("engine", "network", "positions.json")]
        self.binary.write_text("fake engine")
        self.network.write_text("fake network")
        self.positions.write_text(json.dumps({"description": "Original synthetic fixture", "openings": [
            {"id": "first", "moves": ["e2e4", "e7e5"]}, {"id": "second", "moves": ["d2d4", "d7d5"]}]}))
        self.output = self.root / "profile.json"
        FakeEngine.instances, FakeEngine.failure, FakeEngine.mutate = [], None, None
        self.budget = {"max_cpu_workers": 1, "memory_fraction": .5}

    def tearDown(self): self.temporary.cleanup()

    def run_profile(self, **kwargs):
        with patch.object(profiler, "Engine", FakeEngine), \
             patch.object(profiler, "physical_memory", return_value=8 * 1024**3), \
             patch.object(profiler, "current_budget", return_value=self.budget):
            return profiler.profile(self.binary, self.network, self.positions, self.output, **kwargs)

    def test_alternation_history_resets_raw_evidence_and_hashes(self):
        result = self.run_profile()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["samples"]), 8)
        self.assertEqual([s["policy"] for s in result["samples"]], ["classic", "forecast", "forecast", "classic", "forecast", "classic", "classic", "forecast"])
        for sample in result["samples"]:
            self.assertEqual(sample["output"], reply(sample["policy"]))
            self.assertEqual(sample["preparation_commands"][-3:], ["ucinewgame", "position " + result["positions"][sample["position_index"]]["position"], "isready"])
            self.assertEqual(sample["go"], "go wtime 6000 btime 6000 winc 60 binc 60")
        self.assertEqual(result["summary"]["classic"]["aborted_node_fraction"], .6)
        self.assertEqual(result["protocol_output"], FakeEngine.instances[0].transcript)
        self.assertEqual(result["assets"]["positions"]["sha256"], result["after_sha256"]["positions"])
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")
        with self.assertRaises(ValueError): self.run_profile()

    def test_bad_accounting_preserves_raw_failure_without_aggregate(self):
        FakeEngine.failure = "counts"
        with self.assertRaises(ValueError): self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertNotIn("summary", result)
        self.assertIn("nodes 101", result["samples"][-1]["output"][-2])

    def test_timeout_preserves_partial_output_without_aggregate(self):
        FakeEngine.failure = "timeout"
        with self.assertRaises(TimeoutError): self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["samples"][-1]["output"], reply()[:1])
        self.assertEqual(result["after_sha256"]["network"], result["assets"]["network"]["sha256"])
        self.assertNotIn("summary", result)

    def test_position_error_is_recorded_before_any_search(self):
        FakeEngine.failure = "position"
        with self.assertRaises(ValueError): self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["samples"][-1]["preparation_output"], ["info string error: illegal move"])
        self.assertFalse(any(command.startswith("go ") for command in FakeEngine.instances[0].sent))

    def test_mutated_input_artifacts_invalidate_results(self):
        for asset in (self.network, self.positions, self.binary):
            with self.subTest(asset=asset):
                original = asset.read_bytes()
                FakeEngine.mutate = asset
                with self.assertRaisesRegex(ValueError, "artifacts changed"):
                    self.run_profile(repeats=1)
                result = json.loads(self.output.read_text())
                self.assertEqual(result["status"], "invalid_or_interrupted")
                self.assertNotIn("summary", result)
                asset.write_bytes(original)
                self.output.unlink()

    def test_live_resource_budget_is_rechecked_between_searches(self):
        good = {"max_cpu_workers": 1, "memory_fraction": .5}
        bad = {"max_cpu_workers": 0, "memory_fraction": .5}
        with patch.object(profiler, "Engine", FakeEngine), \
             patch.object(profiler, "physical_memory", return_value=8 * 1024**3), \
             patch.object(profiler, "current_budget", side_effect=[good, good, bad]):
            with self.assertRaisesRegex(ValueError, "local budget"):
                profiler.profile(self.binary, self.network, self.positions, self.output)
        result = json.loads(self.output.read_text())
        self.assertEqual(len(result["samples"]), 1)
        self.assertNotIn("summary", result)

    def test_memory_reservation_counts_the_loaded_network_and_hash(self):
        with patch.object(profiler, "physical_memory", return_value=1024**3), \
             patch.object(profiler, "current_budget", return_value=self.budget):
            accepted = profiler.resource_check(self.network, 64)
            self.assertEqual(accepted["resident_engines"], 1)
            self.assertFalse(accepted["memory_estimate_is_hard_cap"])
            with self.assertRaises(ValueError): profiler.resource_check(self.network, 512)

    def test_nonfinite_or_unbounded_timeouts_rejected_before_launch(self):
        for timeout in (0., -1., float("nan"), float("inf"), 301.):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.run_profile(search_timeout=timeout)
        self.assertFalse(FakeEngine.instances)


if __name__ == "__main__":
    unittest.main()
