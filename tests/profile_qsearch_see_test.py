#!/usr/bin/env python3
"""Engine-free evidence/lifecycle checks for the fixed QSearch SEE screen.

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
import profile_qsearch_see as profile


def transcript(board):
    move = next(iter(board.legal_moves)).uci()
    lines = [f"info depth {depth} seldepth {depth} score cp 10 nodes {depth * 10} "
             f"time {depth} nps 10000 hashfull {depth} tbhits 0 pv {move}"
             for depth in range(1, 7)]
    return lines + ["info nodes 60 time 6 nps 10000 hashfull 6 tbhits 0", f"bestmove {move}"]


class CorpusChecks(unittest.TestCase):
    def test_options_change_only_qsearch_see(self):
        parent, off, on = [profile.options_for(role, Path("network")) for role in ("parent", "off", "on")]
        self.assertNotIn("QSearch SEE Pruning", parent)
        self.assertEqual(off.pop("QSearch SEE Pruning"), "false")
        self.assertEqual(on.pop("QSearch SEE Pruning"), "true")
        self.assertEqual(parent, off)
        self.assertEqual(off, on)
        self.assertEqual(parent["Reverse Futility Pruning"], "false")
        self.assertEqual(parent["Null Move Pruning"], "false")

    def test_order_alternates_and_equal_time_reverses(self):
        for index in range(6):
            expected = ("off", "on") if index % 2 == 0 else ("on", "off")
            self.assertEqual(profile.role_order("qsearch_work", index), expected)
            self.assertEqual(profile.role_order("equal_time", index), expected[::-1])



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
            output = [f"option name {name} type string default x"
                      for name in profile.options_for("off", Path("network"))] + ["uciok"]
        elif prefix == "readyok":
            output = (["info string Syzygy largest 0 pieces; table files are external"]
                      if self.first_ready else []) + ["readyok"]
            self.first_ready = False
        else:
            if self.failure == "timeout":
                raise TimeoutError("synthetic timeout")
            position = next(command[9:] for command in reversed(self.commands) if command.startswith("position "))
            output = transcript(profile.board_for(position))
            if self.failure == "parent_mismatch" and self.path.name == "candidate":
                output = [line.replace("score cp 10", "score cp 11") for line in output]
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
        directory = tempfile.TemporaryDirectory(prefix="qsee-profile-test-")
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
                        patch.object(profile, "resource_check", return_value={"synthetic": True})):
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
        self.assertFalse(any("setoption name QSearch SEE Pruning value true" in engine.commands
                             for engine in FakeEngine.created))

    def test_search_failure_preserves_partial_output_and_shutdown(self):
        FakeEngine.failure = "timeout"
        with self.assertRaises(TimeoutError):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["samples"][0]["status"], "incomplete")
        self.assertEqual(report["samples"][0]["output"], [])
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
