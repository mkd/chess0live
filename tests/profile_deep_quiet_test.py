#!/usr/bin/env python3
"""Engine-free evidence/lifecycle checks for the fixed deep quiet-reduction screen.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_deep_quiet as profile


def transcript(board, role="off", mode="depth", *, active=True, completed=None):
    """Real validators consume these synthetic legal UCI and diagnostic records."""
    enabled = role == "on"
    move = list(board.legal_moves)[1 if enabled else 0].uci()
    after = board.copy()
    after.push_uci(move)
    ponder = next(iter(after.legal_moves)).uci()
    step, score = (7, 11) if enabled else (10, 10)
    completed = (4 if mode == "movetime" else 6) if completed is None else completed
    lines = [f"info depth {depth} seldepth {depth} score cp {score} nodes {depth * step} "
             f"time {depth} nps 10000 hashfull {depth if role == 'parent' else 900} "
             f"tbhits 0 pv {move} {ponder}" for depth in range(1, completed + 1)]
    total = completed * step + (17 if mode == "movetime" else 0)
    budget = 480 if mode == "movetime" else 0
    elapsed = 480 if mode == "movetime" else completed
    lines.append(f"info nodes {total} time {elapsed} nps 10000 hashfull 900 tbhits 0")
    lines.append("info string cache v1 entry_bytes 16 bucket_bytes 64 buckets 524288 "
                 "capacity 2097152 allocated_bytes 33554432 probes 12 hits 5 cutoffs 3 "
                 "stores 9 replacements 1")
    lines += [f"info string search-iteration v1 depth {depth} completed true nodes {step} "
              f"duration_ms 1.000 elapsed_ms {depth}.000" for depth in range(1, completed + 1)]
    if mode == "movetime":
        lines.append(f"info string search-iteration v1 depth {completed + 1} completed false "
                     f"nodes 17 duration_ms {elapsed - completed}.000 elapsed_ms {elapsed}.000")
    lines += ["info string ordering v1 policy mvv-lva see_calls 0 losing_captures 0",
              "info string lmr v1 enabled true reductions 20 researches 8 fail_lows 3 verified_cutoffs 3"]
    if enabled:
        counts = (4, 2, 1, 1) if active else (0, 0, 0, 0)
        lines.append("info string deep-lmr v1 enabled true extra_reductions %d researches %d "
                     "fail_lows %d verified_cutoffs %d" % counts)
    lines += [f"info string search-summary v1 policy classic forecast_active false stop_reason "
              f"{'hard_time' if mode == 'movetime' else 'depth_limit'} nodes {total} "
              f"completed_depth {completed} elapsed_ms {elapsed}.000 soft_ms {budget}.000 hard_ms {budget}.000 "
              f"target_ms {budget}.000 predicted_next_ms 0.000", f"bestmove {move} ponder {ponder}"]
    return lines


class CorpusChecks(unittest.TestCase):
    def test_options_change_only_deeper_reductions(self):
        parent, off, on = [profile.options_for(role, Path("network")) for role in ("parent", "off", "on")]
        self.assertNotIn("Deep Quiet Reductions", parent)
        self.assertEqual(off.pop("Deep Quiet Reductions"), "false")
        self.assertEqual(on.pop("Deep Quiet Reductions"), "true")
        self.assertEqual(parent, off)
        self.assertEqual(off, on)
        self.assertEqual(parent["Reverse Futility Pruning"], "false")
        self.assertEqual(parent["Null Move Pruning"], "false")
        self.assertEqual(parent["QSearch SEE Pruning"], "false")
        self.assertEqual(parent["Late Move Reductions"], "true")
        self.assertEqual(parent["Search Diagnostics"], "true")
        self.assertEqual(parent["Time Policy"], "classic")
        self.assertEqual(parent["Capture Ordering"], "mvv-lva")
        self.assertEqual(parent["SyzygyProbeLimit"], "0")
        with self.assertRaises(ValueError):
            profile.options_for("typo", Path("network"))

    def test_order_alternates_and_equal_time_reverses(self):
        for index in range(6):
            expected = ("off", "on") if index % 2 == 0 else ("on", "off")
            self.assertEqual(profile.role_order("deep_quiet_work", index), expected)
            self.assertEqual(profile.role_order("equal_time", index), expected[::-1])



class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.board = profile.board_for("startpos")

    def validate(self, lines, role="on", mode="depth"):
        return profile.validate_result(lines, self.board, mode, role)

    def test_original_pinned_six_position_subset_and_full_histories(self):
        positions = profile.previous.load_positions()
        self.assertEqual(tuple(row["id"] for row in positions), profile.previous.POSITION_IDS)
        self.assertEqual(profile.previous.CORPUS.name, "countermove-profile.json")
        self.assertEqual(len(positions), 6)
        self.assertTrue(any(" moves " in row["position"] for row in positions))
        self.assertIn("tools/profile_lmr.py", profile.SOURCES)
        self.assertIn("tools/profile_cache.py", profile.SOURCES)
        self.assertIn("tools/profile_deep_quiet.py", profile.SOURCES)

    def test_hash_reporting_changes_are_retained_but_not_part_of_search_signature(self):
        parent = self.validate(transcript(self.board, "parent"), "parent")
        off = self.validate(transcript(self.board, "off"), "off")
        self.assertEqual(parent["signature"], off["signature"])
        self.assertNotEqual(parent["iterations"][0]["hashfull"], off["iterations"][0]["hashfull"])
        self.assertTrue(off["lmr"]["enabled"])
        self.assertEqual(off["lmr"]["reductions"], 20)
        self.assertFalse(off["deep_lmr"]["enabled"])

    def test_actual_lmr_off_is_rejected_even_though_historical_screens_used_it(self):
        lines = [line.replace("lmr v1 enabled true reductions", "lmr v1 enabled false reductions")
                 for line in transcript(self.board, "off")]
        with self.assertRaisesRegex(ValueError, "enabled"):
            self.validate(lines, "off")

    def test_deep_reduction_record_is_required_only_for_enabled_role(self):
        lines = transcript(self.board, "on")
        record = next(line for line in lines if " deep-lmr " in line)
        cases = [([line for line in lines if line != record], "on"), (lines, "off"),
                 (lines, "parent"), (lines[:-1] + [record, lines[-1]], "on")]
        for altered, role in cases:
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.validate(altered, role)
        moved = [line for line in lines if line != record]
        moved.insert(-1, record)
        with self.assertRaisesRegex(ValueError, "after"):
            self.validate(moved)

    def test_deep_counter_schema_partitions_and_subset_are_checked(self):
        changes = [("deep-lmr v1", "deep-lmr v2"),
                   ("extra_reductions 4", "extra_reductions -1"),
                   ("extra_reductions 4", "extra_reductions ４"),
                   ("extra_reductions 4", "extra_reductions nan"),
                   ("extra_reductions 4", "extra_reductions 21"),
                   ("extra_reductions 4", "extra_reductions 1"),
                   ("researches 2", "researches 9"),
                   ("fail_lows 1", "fail_lows 2"),
                   ("fail_lows 1", "researches 1"),
                   ("enabled true", "enabled false"),
                   ("verified_cutoffs 1", "verified_cutoffs 4")]
        for before, after in changes:
            lines = [line.replace(before, after) if " deep-lmr " in line else line
                     for line in transcript(self.board, "on")]
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                self.validate(lines)

    def test_timed_search_counts_interrupted_work_and_unfinished_verification(self):
        lines = [line.replace("fail_lows 1 verified_cutoffs 1", "fail_lows 0 verified_cutoffs 0")
                 for line in transcript(self.board, "on", "movetime")]
        result = self.validate(lines, mode="movetime")
        self.assertEqual(result["unfinished_nodes"], 17)
        self.assertEqual(result["reported_nodes"], 45)
        self.assertEqual(result["trace"]["aborted_duration_ms"], 476.)
        self.assertEqual(result["deep_lmr"]["researches"], 2)
        self.assertEqual(result["deep_lmr"]["verified_cutoffs"], 0)
        self.assertEqual(result["completed_depth"], 4)

    def test_every_pv_and_ponder_must_be_legal(self):
        lines = transcript(self.board, "on")
        illegal_pv = list(lines)
        illegal_pv[0] = illegal_pv[0].split(" pv ")[0] + " pv e2e4 e2e3"
        illegal_ponder = list(lines)
        illegal_ponder[-1] = illegal_ponder[-1].split(" ponder ")[0] + " ponder e2e3"
        for changed in (illegal_pv, illegal_ponder):
            with self.assertRaises(ValueError):
                self.validate(changed)

    def test_corrupt_totals_bounds_hash_and_nonisolated_options_are_rejected(self):
        lines = transcript(self.board, "on")
        cases = [[line.replace("info nodes 42", "info nodes 43") for line in lines],
                 [line.replace("tbhits 0", "tbhits 1") for line in lines],
                 [line.replace("tbhits 0", "tbhits") for line in lines],
                 [line.replace("score cp 11", "score cp 11 lowerbound") for line in lines],
                 [line.replace("hashfull 900", "hashfull 1001") for line in lines],
                 [line.replace("completed_depth 6", "completed_depth 5") for line in lines],
                 [line for line in lines if not line.startswith("info nodes ")]]
        for prefix in ("smp", "nullmove", "countermove", "qsearchsee", "reversefutility"):
            cases.append(lines[:-1] + [f"info string {prefix} v1 enabled true", lines[-1]])
        for changed in cases:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.validate(changed)

    def test_unrelated_stops_and_unknown_modes_fail_closed(self):
        for reason in ("external_stop", "soft_time", "node_limit", "depth_limit"):
            lines = [line.replace("stop_reason hard_time", "stop_reason " + reason)
                     for line in transcript(self.board, "on", "movetime")]
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                self.validate(lines, mode="movetime")
        with self.assertRaises(ValueError):
            self.validate(transcript(self.board), mode="unknown")

    def test_zero_activation_is_reported_without_inventing_an_improvement(self):
        result = self.validate(transcript(self.board, "on", active=False))
        self.assertTrue(result["deep_lmr"]["enabled"])
        self.assertEqual(result["deep_lmr"]["extra_reductions"], 0)

    def test_timed_budget_requires_both_limits_to_subtract_the_overhead(self):
        lines = transcript(self.board, "on", "movetime")
        result = self.validate(lines, mode="movetime")
        self.assertEqual(result["trace"]["summary"]["soft_ms"], 480.)
        self.assertEqual(result["trace"]["summary"]["hard_ms"], 480.)
        for before, after in (("soft_ms 480.000", "soft_ms 0.000"),
                              ("hard_ms 480.000", "hard_ms 500.000"),
                              ("soft_ms 480.000", "soft_ms 479.999")):
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, "budgets"):
                self.validate([line.replace(before, after) for line in lines], mode="movetime")

    def test_fixed_depth_requires_zero_soft_and_hard_budgets(self):
        lines = transcript(self.board, "off")
        result = self.validate(lines, "off")
        self.assertEqual(result["trace"]["summary"]["soft_ms"], 0.)
        self.assertEqual(result["trace"]["summary"]["hard_ms"], 0.)
        for soft, hard in ((0, 500), (480, 480), (0, .001)):
            changed = [line.replace("soft_ms 0.000 hard_ms 0.000", f"soft_ms {soft} hard_ms {hard}")
                       for line in lines]
            with self.subTest(soft=soft, hard=hard), self.assertRaisesRegex(ValueError, "budgets"):
                self.validate(changed, "off")

    def test_cache_diagnostic_is_required_once_and_retained(self):
        lines = transcript(self.board, "on")
        result = self.validate(lines)
        self.assertEqual(result["cache"]["allocated_bytes"], 33554432)
        self.assertEqual(result["cache"]["hits"], 5)
        self.assertEqual(result["signature"]["cache"], result["cache"])
        cache = next(line for line in lines if line.startswith("info string cache "))
        for changed in ([line for line in lines if line != cache], lines[:-1] + [cache, lines[-1]]):
            with self.assertRaisesRegex(ValueError, "exactly one cache"):
                self.validate(changed)

    def test_cache_schema_allocation_and_counter_corruption_fail(self):
        lines = transcript(self.board, "on")
        changes = (("cache v1", "cache v2"), ("hits 5", "hits -1"),
                   ("hits 5", "hits 13"), ("hits 5", "hits ５"),
                   ("hits 5", "hits 18446744073709551616"),
                   ("hits 5", "probes 5"), ("replacements 1", "replacements 10"),
                   ("capacity 2097152", "capacity 2097151"),
                   ("allocated_bytes 33554432", "allocated_bytes 67108865"))
        for before, after in changes:
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                self.validate([line.replace(before, after) for line in lines])

    def test_cache_record_must_precede_the_summary(self):
        lines = transcript(self.board, "on")
        cache = next(line for line in lines if line.startswith("info string cache "))
        changed = [line for line in lines if line != cache]
        changed.insert(-1, cache)
        with self.assertRaisesRegex(ValueError, "precede"):
            self.validate(changed)

    def test_summary_keeps_unmatched_depths_and_rejects_broken_matrix(self):
        samples = []
        for index in range(6):
            for role in ("off", "on"):
                lines = transcript(self.board, role, "movetime", completed=3 if role == "on" else 4)
                samples.append({"stage": "equal_time", "position_index": index,
                                "role": role, "mode": "movetime", "temperature": "cold",
                                "status": "complete", "elapsed_seconds": .5,
                                "result": self.validate(lines, role, "movetime")})
        summary = profile.summarize_search(samples, "equal_time")
        self.assertEqual(summary["pairs"][0]["completed_depths"], [4, 3])
        last = summary["pairs"][0]["iteration_differences"][-1]
        self.assertEqual(last["depth"], 4)
        self.assertIsNone(last["right"])
        self.assertTrue(last["left"])
        for broken in (samples[:-1], samples + [samples[-1]],
                       samples[:-1] + [dict(samples[-1], role="parent")],
                       samples[:-1] + [dict(samples[-1], status="incomplete")]):
            with self.assertRaises(ValueError):
                profile.summarize_search(broken, "equal_time")


class FakeEngine:
    """In-memory protocol stand-in; no subprocess, worker, or engine search."""
    created = []
    failure = None
    drift_path = None

    def __init__(self, path):
        self.path, self.commands, self.transcript = path, [], []
        self.lines, self.process, self.reader = queue.Queue(), SimpleNamespace(returncode=0), Mock()
        self.reader.is_alive.return_value = False
        self.first_ready = True
        self.created.append(self)

    def send(self, command):
        self.commands.append(command)

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            role = "parent" if self.path.name == "parent" else "off"
            output = [f"option name {name} type string default x"
                      for name in profile.options_for(role, Path("network"))
                      if name != "Deep Quiet Reductions"]
            if role != "parent":
                output.append("option name Deep Quiet Reductions type check default false")
            if self.failure == "default":
                output = [line.replace("check default false", "check default true") for line in output]
            output.append("uciok")
        elif prefix == "readyok":
            output = (["info string Syzygy largest 0 pieces; table files are external"]
                      if self.first_ready else []) + ["readyok"]
            self.first_ready = False
        else:
            if self.failure == "timeout":
                self.transcript.append("info string retained synthetic partial output")
                raise TimeoutError("synthetic timeout")
            position = next(command[9:] for command in reversed(self.commands) if command.startswith("position "))
            role = "parent" if self.path.name == "parent" else (
                "on" if "setoption name Deep Quiet Reductions value true" in self.commands else "off")
            mode = "movetime" if self.commands[-1] == "go movetime 500" else "depth"
            output = transcript(profile.board_for(position), role, mode)
            if self.failure == "parent_mismatch" and self.path.name == "candidate":
                output = [line.replace("score cp 10", "score cp 11") for line in output]
            if self.failure == "cache_mismatch" and self.path.name == "candidate":
                output = [line.replace("hits 5", "hits 6") for line in output]
            if self.drift_path is not None:
                self.drift_path.write_text("changed")
        self.transcript.extend(output)
        return output

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.failure == "late_output":
            self.lines.put("info string error: synthetic late error")
        self.lines.put(None)


class LifecycleChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="deep-profile-test-")
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.parent, self.candidate, self.network = [base / name for name in ("parent", "candidate", "network")]
        for path in (self.parent, self.candidate, self.network):
            path.write_text(path.name)
        self.output = base / "evidence.json"
        FakeEngine.created, FakeEngine.failure, FakeEngine.drift_path = [], None, None
        for patcher in (patch.object(profile, "Engine", FakeEngine),
                        patch.object(profile, "PARENT_SHA256", profile.digest(self.parent)),
                        patch.object(profile, "NETWORK_SHA256", profile.digest(self.network)),
                        patch.object(profile, "resource_check", return_value={"synthetic": True}),
                        patch.object(profile, "SOURCES", ())):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_profile(self):
        return profile.profile(self.parent, self.candidate, self.network, self.output, quiet_host=True)

    def test_complete_60_search_36_session_matrix_and_provenance(self):
        report = self.run_profile()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["samples"]), 60)
        self.assertEqual(len(report["sessions"]), 36)
        commands = [command for engine in FakeEngine.created for command in engine.commands]
        self.assertEqual(commands.count("go depth 6"), 48)
        self.assertEqual(commands.count("go movetime 500"), 12)
        self.assertEqual(commands.count("ucinewgame"), 36)
        self.assertEqual(list(report["summaries"]), list(profile.STAGES))
        self.assertEqual([len(report["summaries"][stage]["pairs"]) for stage in profile.STAGES],
                         [12, 12, 6])
        self.assertTrue(all(asset["sha256"] == report["after_sha256"][name]
                            for name, asset in report["assets"].items()))
        self.assertTrue(all(session["shutdown_eof_count"] == 1 for session in report["sessions"]))
        work = report["summaries"]["deep_quiet_work"]
        self.assertEqual(work["diagnostics_by_role"]["on"]["deep_activation_searches"], 12)
        self.assertEqual(work["diagnostics_by_role"]["off"]["deep_activation_searches"], 0)
        self.assertEqual(work["diagnostics_by_role"]["on"]["deep_lmr"]["extra_reductions"], 48)
        self.assertTrue(all(len(pair["iteration_differences"]) == 6 for pair in work["pairs"]))
        self.assertTrue(all("bestmove" in pair["final_differences"] for pair in work["pairs"]))
        self.assertEqual(report["summaries"]["equal_time"]["totals_by_temperature"]["cold"]["on"]["unfinished_nodes"], 102)
        self.assertFalse(report["summaries"]["parent_equivalence"]["equivalence_mismatches"])
        self.assertEqual(commands.count("setoption name Late Move Reductions value true"), 36)
        self.assertEqual(commands.count("setoption name Search Diagnostics value true"), 36)

    def test_enabled_candidate_default_is_rejected_before_its_search(self):
        FakeEngine.failure = "default"
        with self.assertRaisesRegex(ValueError, "option/default"):
            self.run_profile()
        self.assertFalse(any(command.startswith("go ") for engine in FakeEngine.created
                             if engine.path == self.candidate for command in engine.commands))

    def test_cache_only_parent_mismatch_is_preserved_and_blocks_candidate_on(self):
        FakeEngine.failure = "cache_mismatch"
        with self.assertRaisesRegex(ValueError, "Default-off"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        summary = report["summaries"]["parent_equivalence"]
        self.assertEqual(len(summary["equivalence_mismatches"]), 12)
        self.assertTrue(all(list(pair["final_differences"]) == ["cache"] for pair in summary["pairs"]))
        self.assertFalse(any(sample["role"] == "on" for sample in report["samples"]))

    def test_quiet_host_pin_and_existing_evidence_gates(self):
        with self.assertRaisesRegex(ValueError, "quiet-host"):
            profile.profile(self.parent, self.candidate, self.network, self.output)
        with patch.object(profile, "PARENT_SHA256", "wrong"):
            with self.assertRaisesRegex(ValueError, "predeclared pins"):
                self.run_profile()
        temporary = self.output.with_suffix(".json.tmp")
        temporary.write_text("partial")
        with self.assertRaisesRegex(ValueError, "Temporary"):
            self.run_profile()
        temporary.unlink()
        self.output.write_text("original")
        with self.assertRaises(FileExistsError):
            self.run_profile()
        self.assertEqual(self.output.read_text(), "original")
        self.assertFalse(FakeEngine.created)

    def test_parent_mismatch_prevents_candidate_on(self):
        FakeEngine.failure = "parent_mismatch"
        with self.assertRaisesRegex(ValueError, "Default-off"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(len(report["samples"]), 24)
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(len(report["summaries"]["parent_equivalence"]["equivalence_mismatches"]), 12)
        self.assertFalse(any("setoption name Deep Quiet Reductions value true" in engine.commands
                             for engine in FakeEngine.created))

    def test_search_failure_preserves_partial_output_and_shutdown(self):
        FakeEngine.failure = "timeout"
        with self.assertRaises(TimeoutError):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["samples"][0]["status"], "incomplete")
        self.assertEqual(report["samples"][0]["output"], ["info string retained synthetic partial output"])
        self.assertEqual(report["sessions"][0]["shutdown_eof_count"], 1)

    def test_resource_change_stops_before_search(self):
        with patch.object(profile, "resource_check", side_effect=[{}, {}, ValueError("resource changed")]):
            with self.assertRaisesRegex(ValueError, "resource changed"):
                self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["samples"], [])
        self.assertEqual(report["sessions"][0]["shutdown_eof_count"], 1)

    def test_late_output_remains_visible_and_invalidates(self):
        FakeEngine.failure = "late_output"
        with self.assertRaisesRegex(ValueError, "unexpected output"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertIn("synthetic late error", report["sessions"][0]["shutdown_output"][0])

    def test_drift_rejects_after_complete_matrix(self):
        FakeEngine.drift_path = self.candidate
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["artifact_drift"], ["candidate"])
        self.assertEqual(len(report["samples"]), 60)

    def test_budget_prevents_work_and_final_cleanup_overrun_invalidates(self):
        with patch.object(profile, "PROFILE_BUDGET_SECONDS", 0):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                self.run_profile()
        self.assertFalse(FakeEngine.created)
        self.output.unlink()
        clock = [0.]
        finish = profile.finish_session

        def now():
            clock[0] += .001
            return clock[0]

        def delayed_finish(engine, session):
            finish(engine, session)
            if len(FakeEngine.created) == 36:
                clock[0] += profile.PROFILE_BUDGET_SECONDS + 1

        with patch.object(profile.time, "monotonic", side_effect=now), \
                patch.object(profile, "finish_session", side_effect=delayed_finish):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(len(report["samples"]), 60)
        self.assertEqual(report["sessions"][-1]["shutdown_eof_count"], 1)


if __name__ == "__main__":
    unittest.main()
