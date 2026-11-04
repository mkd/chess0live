#!/usr/bin/env python3
"""Engine-free replay, evidence and lifecycle checks for Phase 4F.18.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_qsearch_delta as profile


def transcript(board, *, depth=6, score=10, extra_nodes=0):
    move = next(iter(board.legal_moves)).uci()
    return [f"info depth {d} seldepth {d} score cp {score} nodes {d * 10} time {d} "
            f"nps 10000 hashfull {d} tbhits 0 pv {move}" for d in range(1, depth + 1)] + [
                f"info nodes {depth * 10 + extra_nodes} time {depth + 1} nps 10000 hashfull {depth} tbhits 0",
                f"bestmove {move}"]


class RuleChecks(unittest.TestCase):
    def test_all_fifteen_roots_and_source_pin(self):
        positions = profile.load_positions()
        self.assertEqual(len(positions), 15)
        self.assertEqual(positions, json.loads(profile.CORPUS.read_text())["positions"])
        with patch.object(profile, "CORPUS_SHA256", "wrong"):
            with self.assertRaisesRegex(ValueError, "corpus changed"):
                profile.load_positions()

    def test_only_delta_changes_and_parent_has_no_new_option(self):
        parent, off, on = [profile.options_for(role, Path("network")) for role in ("parent", "off", "on")]
        self.assertNotIn("QSearch Delta Pruning", parent)
        self.assertEqual(off.pop("QSearch Delta Pruning"), "false")
        self.assertEqual(on.pop("QSearch Delta Pruning"), "true")
        self.assertEqual(parent, off)
        self.assertEqual(off, on)
        self.assertEqual(parent["Late Move Reductions"], "true")
        self.assertEqual(parent["Capture Ordering"], "mvv-lva")
        for option in ("Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut",
                       "Search Diagnostics", "Continuation History", "TT Move Hints", "Deep Quiet Reductions"):
            self.assertEqual(parent[option], "false")
        with self.assertRaises(ValueError):
            profile.options_for("typo", Path("network"))

    def test_alternating_order_and_reverse_timed_order(self):
        for index in range(15):
            expected = ("off", "on") if index % 2 == 0 else ("on", "off")
            self.assertEqual(profile.role_order("delta_work", index), expected)
            self.assertEqual(profile.role_order("equal_time", index), expected[::-1])
            self.assertEqual(profile.role_order("parent_equivalence", index),
                             ("parent", "off") if index % 2 == 0 else ("off", "parent"))


class ReplayChecks(unittest.TestCase):
    def setUp(self):
        self.board = profile.board_for("startpos")

    def test_exact_signature_excludes_clock_and_hash_but_keeps_work(self):
        raw = transcript(self.board)
        a = profile.validate_result(raw, self.board, "depth")
        b = profile.validate_result([line.replace("time 6", "time 7").replace("nps 10000", "nps 999")
                                     .replace("hashfull 6", "hashfull 99") for line in raw], self.board, "depth")
        self.assertEqual(a["signature"], b["signature"])
        self.assertNotEqual(a["hashfull"], b["hashfull"])
        self.assertIsNone(a["quiescence_nodes"])
        self.assertIsNone(a["internal_score"])
        c = profile.validate_result(transcript(self.board, score=11), self.board, "depth")
        self.assertNotEqual(a["signature"], c["signature"])

    def test_timed_unfinished_work_preserved_but_depth_forbids_it(self):
        raw = transcript(self.board, extra_nodes=7)
        result = profile.validate_result(raw, self.board, "movetime")
        self.assertEqual(result["unfinished_nodes"], 7)
        with self.assertRaisesRegex(ValueError, "unfinished nodes"):
            profile.validate_result(raw, self.board, "depth")

    def test_illegal_null_and_bounded_scores_diagnostics_and_probes_rejected(self):
        raw = transcript(self.board)
        bad = [
            [line.replace(" pv ", " pv 0000 ") for line in raw],
            [line.replace("score cp 10", "score cp 10 lowerbound") for line in raw],
            ["info string harmless-looking-diagnostics", *raw],
            [line.replace("tbhits 0", "tbhits 1") for line in raw],
            [line.replace(" tbhits 0", "") for line in raw],
            [line.replace("hashfull 6", "hashfull 1001") for line in raw],
            raw + [raw[-1]],
            raw[1:],
        ]
        for lines in bad:
            with self.subTest(lines=lines[:1]):
                with self.assertRaises(ValueError):
                    profile.validate_result(lines, self.board, "depth")


class FakeProcess:
    def __init__(self, owner):
        self.owner = owner
        self.pid = 1000 + len(FakeEngine.created)
        self.returncode = None
        self.stdin, self.stdout = Mock(), Mock()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.owner.failure in ("quit_timeout", "kill_timeout") and not self.owner.killed:
            raise subprocess.TimeoutExpired("synthetic", timeout)
        if self.owner.failure == "kill_timeout":
            raise subprocess.TimeoutExpired("synthetic", timeout)
        self.returncode = -9 if self.owner.killed else (1 if self.owner.failure == "bad_exit" else 0)
        return self.returncode

    def kill(self):
        self.owner.killed = True
        self.owner.lines.put(None)


class FakeEngine:
    """No process or actual search: the protocol and shutdown are in memory."""
    created = []
    failure = None
    drift_path = None

    def __init__(self, path):
        self.path, self.commands, self.transcript = path, [], []
        self.lines, self.reader = queue.Queue(), Mock()
        self.reader.is_alive.return_value = False
        self.first_ready, self.killed = True, False
        self.process = FakeProcess(self)
        self.created.append(self)

    def send(self, command):
        self.commands.append(command)
        if command == "quit" and self.failure not in ("quit_timeout", "kill_timeout"):
            if self.failure == "late_output":
                self.lines.put("info string error: synthetic late error")
            self.lines.put(None)

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            types = dict(profile.baseline.OPTION_TYPES, **{"QSearch Delta Pruning": "check"})
            output = [f"option name {name} type {types[name]} default false"
                      for name in profile.options_for("parent" if self.path.name == "parent" else "off", Path("network"))]
            if self.failure == "missing_option":
                output = [line for line in output if not line.startswith("option name Hash type ")]
            if self.failure == "duplicate_option":
                output.append(output[0])
            if self.failure == "default_true":
                output = [line.replace("QSearch Delta Pruning type check default false",
                                       "QSearch Delta Pruning type check default true") for line in output]
            output.append("uciok")
        elif prefix == "readyok":
            output = (["info string Syzygy largest 0 pieces; table files are external"]
                      if self.first_ready else []) + ["readyok"]
            self.first_ready = False
            if self.failure == "readiness_error":
                output.insert(0, "info string error: synthetic setup error")
        else:
            position = next(command[9:] for command in reversed(self.commands) if command.startswith("position "))
            score = 10
            if self.failure == "parent_mismatch" and self.path.name == "candidate":
                score = 11
            if self.failure == "heuristic_changes" and "setoption name QSearch Delta Pruning value true" in self.commands:
                score = 12
            output = transcript(profile.board_for(position), score=score)
            if self.failure in ("timeout", "interrupt"):
                self.transcript.append(output[0])
                if self.failure == "interrupt":
                    raise KeyboardInterrupt()
                raise TimeoutError("synthetic timeout")
            if self.drift_path is not None:
                self.drift_path.write_text("changed")
        self.transcript.extend(output)
        return output


class LifecycleChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="qdelta-profile-test-")
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.parent, self.candidate, self.network = [base / name for name in ("parent", "candidate", "network")]
        for path in (self.parent, self.candidate, self.network):
            path.write_text(path.name)
        self.output = base / "evidence.json"
        FakeEngine.created, FakeEngine.failure, FakeEngine.drift_path = [], None, None
        def publish(path, report):
            path.write_text(json.dumps(report))

        for patcher in (patch.object(profile, "Engine", FakeEngine),
                        patch.object(profile, "PARENT_SHA256", profile.digest(self.parent)),
                        patch.object(profile, "NETWORK_SHA256", profile.digest(self.network)),
                        patch.object(profile, "resource_check", return_value={"synthetic": True}),
                        patch.object(profile, "source_paths", return_value={}),
                        patch.object(profile, "publish", side_effect=publish)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_profile(self):
        return profile.profile(self.parent, self.candidate, self.network, self.output, quiet_host=True)

    def evidence(self):
        return json.loads(self.output.read_text())

    def test_complete_frozen_matrix_commands_events_pids_and_provenance(self):
        report = self.run_profile()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["samples"]), 150)
        self.assertEqual(len(report["sessions"]), 90)
        commands = [command for engine in FakeEngine.created for command in engine.commands]
        self.assertEqual(commands.count("go depth 6"), 120)
        self.assertEqual(commands.count("go movetime 500"), 30)
        self.assertEqual(commands.count("ucinewgame"), 90)
        self.assertEqual(commands.count("quit"), 90)
        self.assertEqual(list(report["summaries"]), list(profile.STAGES))
        self.assertEqual([len(report["summaries"][stage]["pairs"]) for stage in profile.STAGES], [30, 30, 15])
        self.assertTrue(all(asset["sha256"] == report["after_sha256"][name] for name, asset in report["assets"].items()))
        for session, engine in zip(report["sessions"], FakeEngine.created):
            self.assertEqual(session["pid"], engine.process.pid)
            self.assertEqual(session["shutdown_eof_count"], 1)
            self.assertEqual(session["exit_code"], 0)
            self.assertEqual(session["commands"], engine.commands)
            self.assertEqual([e["line"] for e in session["events"] if e["direction"] == "receive"], session["output"])
            self.assertEqual([e["line"] for e in session["events"] if e["direction"] == "send"], session["commands"])

    def test_on_differences_are_preserved_without_parity_gate(self):
        FakeEngine.failure = "heuristic_changes"
        report = self.run_profile()
        self.assertTrue(report["summaries"]["parent_equivalence"]["exact_search_parity"])
        for stage in ("delta_work", "equal_time"):
            summary = report["summaries"][stage]
            self.assertFalse(summary["exact_search_parity"])
            self.assertTrue(all(len(pair["common_depth_score_or_pv_changes"]) == 6 for pair in summary["pairs"]))

    def test_quiet_host_pin_and_existing_evidence_gates(self):
        with self.assertRaisesRegex(ValueError, "quiet-host"):
            profile.profile(self.parent, self.candidate, self.network, self.output)
        self.assertEqual(self.evidence()["status"], "invalid_or_interrupted")
        self.output.unlink()
        with patch.object(profile, "PARENT_SHA256", "wrong"):
            with self.assertRaisesRegex(ValueError, "predeclared pins"):
                self.run_profile()
        self.output.unlink()
        temporary = self.output.with_suffix(".json.tmp")
        temporary.write_text("partial")
        with self.assertRaisesRegex(ValueError, "Temporary"):
            self.run_profile()
        self.assertEqual(temporary.read_text(), "partial")
        temporary.unlink()
        self.output.write_text("original")
        with self.assertRaises(FileExistsError):
            self.run_profile()
        self.assertEqual(self.output.read_text(), "original")
        self.assertFalse(FakeEngine.created)

    def test_parent_mismatch_stops_immediately_after_first_paired_root(self):
        FakeEngine.failure = "parent_mismatch"
        with self.assertRaisesRegex(ValueError, "Default-off"):
            self.run_profile()
        report = self.evidence()
        self.assertEqual(len(report["samples"]), 4)
        self.assertEqual(report["parent_mismatch"]["position_id"], "opening-01")
        self.assertFalse(any("setoption name QSearch Delta Pruning value true" in engine.commands
                             for engine in FakeEngine.created))

    def test_timeout_and_interrupt_preserve_partial_output_and_cleanup(self):
        for failure, exception in (("timeout", TimeoutError), ("interrupt", KeyboardInterrupt)):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(exception):
                    self.run_profile()
                report = self.evidence()
                self.assertEqual(report["samples"][0]["status"], "incomplete")
                self.assertEqual(len(report["samples"][0]["output"]), 1)
                self.assertEqual(report["sessions"][0]["shutdown_eof_count"], 1)
                self.assertEqual(report["sessions"][0]["exit_code"], 0)
                self.output.unlink()

    def test_missing_duplicate_options_and_unexpected_readiness_stop_before_search(self):
        for failure in ("missing_option", "duplicate_option", "readiness_error", "default_true"):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(ValueError):
                    self.run_profile()
                complete = [s for s in self.evidence()["samples"] if s["status"] == "complete"]
                self.assertEqual(len(complete), 2 if failure == "default_true" else 0)
                self.assertTrue(all(s["role"] == "parent" for s in complete))
                self.assertEqual(self.evidence()["sessions"][-1]["exit_code"], 0)
                self.output.unlink()

    def test_resource_failure_preserved_before_search(self):
        with patch.object(profile, "resource_check", side_effect=[{}, {}, ValueError("resource changed")]):
            with self.assertRaisesRegex(ValueError, "resource changed"):
                self.run_profile()
        report = self.evidence()
        self.assertEqual(report["samples"], [])
        self.assertEqual(report["sessions"][0]["shutdown_eof_count"], 1)

    def test_cleanup_errors_and_forced_kill_are_visible(self):
        for failure in ("late_output", "bad_exit", "quit_timeout", "kill_timeout"):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                    self.run_profile()
                report = self.evidence()
                self.assertEqual(report["status"], "invalid_or_interrupted")
                self.assertTrue(any(f["kind"] == "cleanup" for f in report["failures"]))
                session = report["sessions"][0]
                if failure == "late_output":
                    self.assertIn("synthetic late error", session["shutdown_output"][0])
                if failure.endswith("timeout"):
                    self.assertTrue(session["forced_kill"])
                if failure == "kill_timeout":
                    self.assertFalse(session["process_exited"])
                self.output.unlink()

    def test_drift_invalidates_complete_screen(self):
        FakeEngine.drift_path = self.candidate
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        self.assertEqual(self.evidence()["artifact_drift"], ["candidate"])
        self.assertEqual(len(self.evidence()["samples"]), 150)

    def test_zero_budget_prevents_process_start(self):
        with patch.object(profile, "PROFILE_BUDGET_SECONDS", 0):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                self.run_profile()
        self.assertFalse(FakeEngine.created)

    def test_final_cleanup_may_finish_after_search_deadline(self):
        clock = [0.]
        original = profile.cleanup

        def cleanup(engine, session):
            original(engine, session)
            if len(FakeEngine.created) == 90:
                clock[0] = 301.

        with patch.object(profile.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(profile, "cleanup", side_effect=cleanup):
            # Nonzero elapsed is required by summary validation; each synthetic
            # search advances the monotonic clock before returning bestmove.
            until = FakeEngine.until

            def advancing_until(engine, prefix, timeout=30):
                if prefix == "bestmove":
                    clock[0] += .01
                return until(engine, prefix, timeout)

            with patch.object(FakeEngine, "until", advancing_until):
                report = self.run_profile()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["elapsed_seconds"], 301.)

    def test_duplicate_missing_and_invalid_cells_rejected(self):
        report = self.run_profile()
        samples = report["samples"]
        for broken in (samples[1:], samples + [samples[0]]):
            with self.assertRaises(ValueError):
                profile.summarize(broken, "parent_equivalence", report["positions"])
        altered = copy.deepcopy(samples)
        altered[0]["elapsed_seconds"] = float("nan")
        with self.assertRaises(ValueError):
            profile.summarize(altered, "parent_equivalence", report["positions"])


if __name__ == "__main__":
    unittest.main()
