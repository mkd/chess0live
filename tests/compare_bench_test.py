#!/usr/bin/env python3
"""Check comparison invariants and evidence preservation without timed searches.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import compare_bench as comparison


LINES = [
    "info depth 1 seldepth 1 score cp 12 nodes 40 time 1 nps 40000 hashfull 0 pv e2e4",
    "info depth 2 seldepth 3 score cp 8 nodes 190 time 3 nps 63000 hashfull 0 pv e2e4 e7e5",
    "bestmove e2e4 ponder e7e5",
]


class SignatureTests(unittest.TestCase):
    def test_timing_and_hash_occupancy_do_not_change_signature(self):
        changed = [line.replace("time 3", "time 5").replace("nps 63000", "nps 38000").replace("hashfull 0", "hashfull 9")
                   for line in LINES]
        self.assertEqual(comparison.search_signature(LINES, 2), comparison.search_signature(changed, 2))

    def test_work_and_decision_changes_are_detectable(self):
        original = comparison.search_signature(LINES, 2)
        for before, after in (("nodes 190", "nodes 191"), ("score cp 8", "score cp 9"),
                              ("seldepth 3", "seldepth 4"), ("e7e5", "c7c5")):
            changed = [line.replace(before, after) for line in LINES]
            self.assertNotEqual(original, comparison.search_signature(changed, 2))

    def test_incomplete_malformed_or_failed_search_rejected(self):
        cases = [LINES[:1] + LINES[2:], LINES[:2], LINES + ["info string error: network failure"],
                 [line.replace("score cp 8", "score cp 8 lowerbound") for line in LINES],
                 LINES[:2] + ["bestmove d2d4"], LINES[:2] + ["bestmove 0000"],
                 [line.replace("nodes 190", "nodes NaN") for line in LINES],
                 LINES[:2] + ["bestmove e2e4 ponder invalid"]]
        for lines in cases:
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                comparison.search_signature(lines, 2)

    def test_alternating_order_balances_positions_and_repetitions(self):
        self.assertEqual(comparison.run_order(0, 0), ("baseline", "candidate"))
        self.assertEqual(comparison.run_order(1, 0), ("candidate", "baseline"))
        self.assertEqual(comparison.run_order(0, 1), ("candidate", "baseline"))

    def samples(self):
        signature = comparison.search_signature(LINES, 2)
        return [{"position_index": 0, "repetition": repetition, "role": role,
                 "warmup": False, "elapsed_seconds": duration, "signature": signature}
                for repetition, times in enumerate(((2.0, 1.0), (4.0, 2.0)))
                for role, duration in zip(("baseline", "candidate"), times)]

    def test_median_paired_ratio_and_variability(self):
        samples = self.samples()
        samples.append(dict(samples[0], warmup=True, elapsed_seconds=1000.0))
        result = comparison.summarize(samples, ["startpos"])
        self.assertEqual(result["paired_speed_ratio"]["median"], 2.0)
        self.assertEqual(result["paired_speed_ratio"]["median_absolute_deviation"], 0.0)
        self.assertEqual(result["positions"][0]["baseline_seconds"]["median"], 3.0)

    def test_changed_work_missing_pairs_and_nonfinite_times_reject_ratios(self):
        samples = self.samples()
        cases = [samples[:-1], samples + [samples[0]]]
        changed = copy.deepcopy(samples)
        changed[0]["signature"]["iterations"][0]["nodes"] += 1
        # Each original sample shares the signature; detach one sample explicitly.
        changed[0]["signature"] = comparison.search_signature(LINES, 2)
        cases.append(changed)
        for value in (0.0, float("nan"), float("inf")):
            invalid = copy.deepcopy(samples)
            invalid[0]["elapsed_seconds"] = value
            cases.append(invalid)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                comparison.summarize(case, ["startpos"])


class FakeEngine:
    instances = []
    change_candidate = False
    timeout_candidate = False

    def __init__(self, path):
        self.path, self.sent, self.transcript = path, [], []
        self.instances.append(self)

    def send(self, command):
        self.sent.append(command)

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            return [f"option name {name} type {kind}" for name, kind in
                    (("Hash", "spin"), ("Threads", "spin"), ("EvalFile", "string"))] + ["uciok"]
        if prefix == "readyok":
            return ["readyok"]
        if self.timeout_candidate and self.path.name == "candidate":
            self.transcript.extend(LINES[:1])
            raise TimeoutError("Injected bounded-search timeout")
        if self.change_candidate and self.path.name == "candidate":
            return [line.replace("nodes 190", "nodes 191") for line in LINES]
        return LINES.copy()

    def __enter__(self): return self
    def __exit__(self, *_): pass


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-compare-test-")
        self.root = Path(self.temporary.name)
        self.baseline, self.candidate, self.network = [self.root / name for name in ("baseline", "candidate", "network")]
        for path in (self.baseline, self.candidate, self.network): path.write_text(path.name)
        self.output = self.root / "result.json"
        FakeEngine.instances = []
        FakeEngine.change_candidate = False
        FakeEngine.timeout_candidate = False

    def tearDown(self): self.temporary.cleanup()

    def compare(self):
        with patch.object(comparison, "Engine", FakeEngine), \
             patch.object(comparison, "physical_memory", return_value=8 * 1024**3), \
             patch.object(comparison, "current_budget", return_value={"max_cpu_workers": 1, "memory_fraction": 0.5}):
            return comparison.compare(self.baseline, self.candidate, self.network,
                                      ["startpos"], 2, 2, 16, self.output)

    def test_raw_samples_provenance_warmups_and_reset_are_preserved(self):
        result = self.compare()
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["signatures_match"])
        self.assertEqual(len(result["samples"]), 6)
        self.assertEqual(sum(sample["warmup"] for sample in result["samples"]), 2)
        self.assertEqual(len(result["runner_sources"]), 4)
        self.assertEqual(result["samples"][0]["output"], LINES)
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")
        for engine in FakeEngine.instances:
            for index, command in enumerate(engine.sent):
                if command.startswith("go "):
                    self.assertEqual(engine.sent[index - 3:index], ["ucinewgame", "position startpos", "isready"])
        with self.assertRaises(ValueError): self.compare()

    def test_semantic_mismatch_preserves_raw_failure_without_speed_claim(self):
        FakeEngine.change_candidate = True
        with self.assertRaises(ValueError): self.compare()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertNotIn("summary", result)
        self.assertEqual(len(result["samples"]), 2)
        self.assertTrue(any("nodes 191" in line for line in result["samples"][-1]["output"]))

    def test_combined_memory_estimate_respects_live_owner_budget(self):
        with patch.object(comparison, "physical_memory", return_value=1024**3), \
             patch.object(comparison, "current_budget", return_value={"max_cpu_workers": 1, "memory_fraction": 0.5}):
            policy = comparison.resource_check(self.network, 16)
            self.assertEqual(policy["resident_engines"], 2)
            self.assertEqual(policy["active_search_workers"], 1)
            self.assertFalse(policy["memory_estimate_is_hard_cap"])
            with self.assertRaises(ValueError): comparison.resource_check(self.network, 256)

    def test_timeout_preserves_incomplete_raw_evidence_without_summary(self):
        FakeEngine.timeout_candidate = True
        with self.assertRaises(TimeoutError): self.compare()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertNotIn("summary", result)
        self.assertEqual(result["samples"][-1]["status"], "incomplete")
        self.assertEqual(result["samples"][-1]["output"], LINES[:1])

    def test_unbounded_or_nonfinite_search_timeouts_rejected(self):
        for timeout in (0, -1, float("nan"), float("inf"), 301):
            with self.assertRaises(ValueError):
                comparison.compare(self.baseline, self.candidate, self.network,
                                   ["startpos"], 2, 2, 16, self.output, timeout)


if __name__ == "__main__":
    unittest.main()
