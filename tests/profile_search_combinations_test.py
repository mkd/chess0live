#!/usr/bin/env python3
"""Engine-free protocol, failure and evidence tests for Phase 4F.19.

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
import profile_search_combinations as profile


def identity():
    names = ["Deep Quiet Reductions", "Countermove Ordering", "Continuation History", "Null Move Pruning",
             "Reverse Futility Pruning", "QSearch SEE Pruning", "QSearch Delta Pruning", "ProbCut", "TT Move Hints"]
    return ["id name chess0live 0.1-dev", "id author Claudio M. Camacho",
            "option name Hash type spin default 64 min 1 max 16384", "option name Clear Hash type button",
            "option name Threads type spin default 1 min 1 max 128",
            "option name EvalFile type string default nn-1a298aa575a0.nnue",
            "option name SyzygyPath type string default <empty>",
            "option name SyzygyProbeLimit type spin default 7 min 0 max 7",
            "option name SyzygyProbeDepth type spin default 1 min 1 max 128",
            "option name Move Overhead type spin default 20 min 0 max 5000",
            "option name Ponder type check default false",
            "option name Time Policy type combo default classic var classic var forecast var bounded",
            "option name Search Diagnostics type check default false",
            "option name Late Move Reductions type check default true",
            "option name Capture Ordering type combo default mvv-lva var mvv-lva var see",
            *[f"option name {name} type check default false" for name in names], "uciok"]


def transcript(board, depth=3, score=10):
    move = next(iter(board.legal_moves)).uci()
    return [f"info depth {d} seldepth {d + 1} score cp {score} nodes {d * 100} time {d} "
            f"nps 10000 hashfull {d} tbhits 0 pv {move}" for d in range(1, depth + 1)] + [
                f"info nodes {depth * 100 + 9} time 4980 nps 10000 hashfull 5 tbhits 0", f"bestmove {move}"]


def good_host():
    return {"checked_utc": profile.utc_now(), "ac_power": True, "automatic": True, "passed": True,
            "battery": {"returncode": 0, "stdout": "Now drawing from 'AC Power'", "stderr": ""},
            "power": {"returncode": 0, "stdout": "AC Power:\n powermode 0\n", "stderr": ""}}


class ConfigurationChecks(unittest.TestCase):
    def test_fifteen_original_roots_and_frozen_corpus(self):
        self.assertEqual(profile.load_positions(), json.loads(profile.CORPUS.read_text())["positions"])
        with patch.object(profile, "CORPUS_SHA256", "bad"):
            with self.assertRaisesRegex(ValueError, "corpus changed"):
                profile.load_positions()

    def test_exact_profiles_and_balanced_rotation(self):
        off, default, on = [profile.options_for(r, Path("network")) for r in profile.PROFILES]
        self.assertEqual({k for k in off if off[k] != default[k]}, {"Late Move Reductions"})
        self.assertTrue(all(off[k] == "false" and on[k] == "true" for k in profile.SEARCH_OPTIONS))
        self.assertEqual(on["Capture Ordering"], "see")
        for options in (off, default, on):
            self.assertEqual(options["Threads"], "1")
            self.assertEqual(options["Hash"], "64")
            self.assertEqual(options["Search Diagnostics"], "false")
            self.assertEqual(options["SyzygyProbeLimit"], "0")
        for role in profile.PROFILES:
            for slot in range(3):
                self.assertEqual(sum(profile.run_order(i)[slot] == role for i in range(15)), 5)
        with self.assertRaises(ValueError):
            profile.options_for("typo", Path("network"))

    def test_identity_requires_every_exact_default_and_unique_option(self):
        raw = identity()
        profile.validate_identity(raw, profile.NETWORK)
        for changed in (raw[:2] + raw[3:], raw[:-1] + [raw[2], "uciok"],
                        [s.replace("Late Move Reductions type check default true", "Late Move Reductions type check default false") for s in raw],
                        [s.replace("QSearch Delta Pruning type check default false", "QSearch Delta Pruning type check default true") for s in raw],
                        raw[:-1] + ["info string error: setup", "uciok"]):
            with self.subTest(changed=changed[-2:]):
                with self.assertRaises(ValueError):
                    profile.validate_identity(changed, profile.NETWORK)

    def test_runtime_and_bootstrap_dependencies_bound(self):
        paths = profile.source_paths()
        for name in ("tools/run.py", "tools/tooling.py", "tools/python-packages.json", "tools/uci_client.py",
                     "tools/profile_null_move.py", "tools/profile_smp.py", "Makefile", "README.md"):
            self.assertTrue(paths[name].is_file())
        receipt = profile.interpreter_identity()
        self.assertEqual(receipt["sha256"], profile.digest(Path(sys.executable).resolve()))
        self.assertIn("not a full runtime", receipt["limitation"])

    def test_resource_reservation_and_rejections(self):
        policy = {"max_cpu_workers": 9, "memory_fraction": .5}
        with patch.object(profile, "current_budget", return_value=policy), patch.object(profile, "physical_memory", return_value=64 * 1024**3):
            receipt = profile.resource_check(profile.NETWORK)
            self.assertGreaterEqual(receipt["reserved_memory_bytes"], 2 * 1024**3)
            self.assertEqual(receipt["active_search_workers"], 1)
            self.assertEqual(receipt["resident_engines"], 1)
        with patch.object(profile, "current_budget", return_value=policy), patch.object(profile, "physical_memory", return_value=1024**3):
            with self.assertRaisesRegex(ValueError, "resource policy"):
                profile.resource_check(profile.NETWORK)
        with patch.object(profile, "current_budget", return_value=dict(policy, max_cpu_workers=0)), patch.object(profile, "physical_memory", return_value=64 * 1024**3):
            with self.assertRaisesRegex(ValueError, "resource policy"):
                profile.resource_check(profile.NETWORK)


class HostChecks(unittest.TestCase):
    def observe(self, battery, power, code=0):
        results = [subprocess.CompletedProcess([], code, battery, ""),
                   subprocess.CompletedProcess([], code, power, "")]
        with patch.object(profile.sys, "platform", "darwin"), patch.object(profile.subprocess, "run", side_effect=results):
            return profile.host_observation()

    def test_current_and_older_mode_formats_and_battery_discharge_on_ac(self):
        for power in ("AC Power:\n lowpowermode 0\n", "Battery Power:\n powermode 1\nAC Power:\n powermode 0\n",
                      "AC Power:\n powermode 0\nBattery Power:\n powermode 1\n"):
            with self.subTest(power=power):
                self.assertTrue(self.observe("Now drawing from 'AC Power'\n69%; discharging", power)["passed"])

    def test_ac_section_cannot_borrow_zero_mode_from_battery_section(self):
        result = self.observe("Now drawing from 'AC Power'", "AC Power:\n powermode 1\nBattery Power:\n powermode 0\n")
        self.assertFalse(result["passed"])
        self.assertEqual(result["mode_fields"], {"powermode": "1"})

    def test_battery_missing_nonzero_mode_and_command_failure_reject(self):
        for battery, power, code in (("Now drawing from 'Battery Power'", "AC Power:\n powermode 0\n", 0),
                                     ("Now drawing from 'AC Power'", "AC Power:\n sleep 0\n", 0),
                                     ("Now drawing from 'AC Power'", "AC Power:\n lowpowermode 0\n highpowermode 1\n", 0),
                                     ("Now drawing from 'AC Power'", "AC Power:\n powermode 0\n", 1)):
            with self.subTest(battery=battery, power=power, code=code):
                self.assertFalse(self.observe(battery, power, code)["passed"])

    def test_unavailable_pmset_is_preserved(self):
        with patch.object(profile.sys, "platform", "darwin"), patch.object(profile.subprocess, "run", side_effect=OSError("denied")):
            result = profile.host_observation()
        self.assertFalse(result["passed"])
        self.assertIn("denied", result["error"])


class ReplayChecks(unittest.TestCase):
    def setUp(self):
        self.board = profile.board_for("startpos")

    def test_retains_unfinished_work_and_raw_final_fields(self):
        result = profile.validate_result(transcript(self.board), self.board)
        self.assertEqual(result["unfinished_nodes"], 9)
        self.assertEqual(result["reported_time_ms"], 4980)
        self.assertEqual(result["seldepth"], 4)
        self.assertEqual(result["final_aggregate"]["tbhits"], 0)
        self.assertIsNone(result["quiescence_nodes"])
        self.assertIsNone(result["internal_score"])

    def test_rejects_illegal_and_incomplete_protocol_records(self):
        raw = transcript(self.board)
        cases = [raw[1:], raw + [raw[-1]], raw[:-2] + raw[-1:],
                 [s.replace(" pv ", " pv 0000 ") for s in raw],
                 [s.replace("score cp 10", "score cp 10 lowerbound") for s in raw],
                 [s.replace("tbhits 0", "tbhits 1") for s in raw],
                 [s.replace(" tbhits 0", "") for s in raw],
                 [s.replace(" pv ", " unknown 1 pv ") for s in raw],
                 ["info string diagnostics", *raw],
                 raw[:-1] + ["bestmove e2e4 ponder e2e3"]]
        for case in cases:
            with self.subTest(case=case[-1]):
                with self.assertRaises(ValueError):
                    profile.validate_result(case, self.board)


class FakeProcess:
    def __init__(self, owner):
        self.owner, self.pid, self.returncode = owner, 1000 + len(FakeEngine.created), None
        self.stdin, self.stdout = Mock(), Mock()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.owner.failure in ("quit_timeout", "kill_timeout") and not self.owner.killed:
            raise subprocess.TimeoutExpired("synthetic", timeout)
        if self.owner.failure == "kill_timeout":
            raise subprocess.TimeoutExpired("synthetic", timeout)
        self.returncode = -9 if self.owner.killed else 1 if self.owner.failure == "bad_exit" else 0

    def kill(self):
        self.owner.killed = True
        self.owner.lines.put(None)


class FakeEngine:
    created, failure, drift_path = [], None, None

    def __init__(self, path):
        self.path, self.commands, self.transcript = path, [], []
        self.lines, self.reader = queue.Queue(), Mock()
        self.reader.is_alive.return_value = False
        self.process, self.killed, self.first_ready = FakeProcess(self), False, True
        self.created.append(self)

    def send(self, command):
        self.commands.append(command)
        if command == "quit" and self.failure not in ("quit_timeout", "kill_timeout"):
            if self.failure == "late_output":
                self.lines.put("info string error: late synthetic failure")
            self.lines.put(None)

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            output = identity()
            if self.failure == "missing_option":
                output.pop(2)
        elif prefix == "readyok":
            output = (["info string Syzygy largest 0 pieces; table files are external"] if self.first_ready else []) + ["readyok"]
            self.first_ready = False
            if self.failure == "readiness_error":
                output.insert(0, "info string error: readiness")
        else:
            board = profile.board_for(next(c[9:] for c in reversed(self.commands) if c.startswith("position ")))
            role = "all-on" if "setoption name Capture Ordering value see" in self.commands else (
                "default" if "setoption name Late Move Reductions value true" in self.commands else "optional-off")
            offset = profile.PROFILES.index(role)
            output = transcript(board, depth=3 + offset, score=10 + offset)
            if self.failure in ("timeout", "interrupt"):
                self.transcript.append(output[0])
                if self.failure == "interrupt":
                    raise KeyboardInterrupt("synthetic interrupt")
                raise TimeoutError("synthetic timeout")
            if self.drift_path:
                self.drift_path.write_text("changed")
        self.transcript.extend(output)
        return output


class LifecycleChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="combinations-test-")
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.engine, self.network, self.protocol = [base / s for s in ("engine", "nn-1a298aa575a0.nnue", "protocol.md")]
        for path in (self.engine, self.network, self.protocol):
            path.write_text(path.name)
        self.output = base / "evidence.json"
        FakeEngine.created, FakeEngine.failure, FakeEngine.drift_path = [], None, None
        for patcher in (patch.object(profile, "Engine", FakeEngine),
                        patch.object(profile, "ENGINE_SHA256", profile.digest(self.engine)),
                        patch.object(profile, "NETWORK_SHA256", profile.digest(self.network)),
                        patch.object(profile, "PROTOCOL", self.protocol),
                        patch.object(profile, "resource_check", return_value={"synthetic": True}),
                        patch.object(profile, "source_paths", return_value={})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_profile(self, host_check=good_host):
        return profile.profile(self.engine, self.network, self.output, quiet_host=True, host_check=host_check)

    def evidence(self):
        return json.loads(self.output.read_text())

    def test_complete_ordered_matrix_raw_events_zero_exits_and_summary(self):
        result = self.run_profile()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["sessions"]), 45)
        self.assertEqual(len(result["samples"]), 45)
        self.assertEqual(len(result["host_observations"]), 90)
        self.assertEqual(len(result["summary"]["pairs"]), 45)
        self.assertEqual([s["role"] for s in result["samples"]], [role for i in range(15) for role in profile.run_order(i)])
        self.assertTrue(all(s["go"] == "go movetime 5000" for s in result["samples"]))
        self.assertEqual([result["summary"]["profiles"][r]["median_completed_depth"] for r in profile.PROFILES], [3, 4, 5])
        self.assertTrue(all(not p["same_score"] and p["same_bestmove"] for p in result["summary"]["pairs"]))
        for session in result["sessions"]:
            self.assertEqual(session["exit_code"], 0)
            self.assertEqual(session["shutdown_eof_count"], 1)
            self.assertFalse(session["forced_kill"])
            self.assertEqual([e["line"] for e in session["events"] if e["direction"] == "send"], session["commands"])
            self.assertEqual([e["line"] for e in session["events"] if e["direction"] == "receive"], session["output"])
            times = [e["elapsed_seconds"] for e in session["events"]]
            self.assertEqual(times, sorted(times))
        self.assertFalse(result["artifact_drift"])

    def test_incomplete_duplicate_and_changed_decisions_are_not_hidden(self):
        report = self.run_profile()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            profile.summarize(report["samples"][:-1], report["positions"])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            profile.summarize(report["samples"] + report["samples"][:1], report["positions"])
        self.assertTrue(all(p["common_depth_score_or_pv_changes"] for p in report["summary"]["pairs"]))

    def test_quiet_gate_and_existing_evidence_are_preserved(self):
        with self.assertRaisesRegex(ValueError, "quiet-host"):
            profile.profile(self.engine, self.network, self.output)
        saved = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_profile()
        self.assertEqual(saved, self.output.read_bytes())
        self.output.unlink()
        self.output.with_suffix(".json.tmp").write_text("partial")
        with self.assertRaisesRegex(ValueError, "Temporary"):
            self.run_profile()
        self.assertFalse(FakeEngine.created)

    def test_wrong_engine_pin_stops_before_launch(self):
        with patch.object(profile, "ENGINE_SHA256", "wrong"):
            with self.assertRaisesRegex(ValueError, "predeclared pins"):
                self.run_profile()
        self.assertFalse(FakeEngine.created)
        self.assertEqual(self.evidence()["status"], "invalid_or_interrupted")

    def test_host_failure_before_start_and_after_first_cell_stops(self):
        bad = dict(good_host(), passed=False, ac_power=False, error="battery")
        for records, count in (([bad], 0), ([good_host(), bad], 1)):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "Host conditions"):
                self.run_profile(Mock(side_effect=records))
            result = self.evidence()
            self.assertEqual(len(result["samples"]), count)
            self.assertFalse(result["host_observations"][-1]["passed"])
            self.assertTrue(all(s["process_exited"] for s in result["sessions"]))
            self.output.unlink()

    def test_deadline_and_resource_rejection_launch_nothing(self):
        with patch.object(profile, "TOTAL_SECONDS", -1), self.assertRaises(TimeoutError):
            self.run_profile()
        self.assertFalse(FakeEngine.created)
        self.output.unlink()
        with patch.object(profile, "resource_check", side_effect=ValueError("resources")), self.assertRaisesRegex(ValueError, "resources"):
            self.run_profile()
        self.assertFalse(FakeEngine.created)

    def test_timeout_interrupt_partial_output_and_cleanup(self):
        for failure, error in (("timeout", TimeoutError), ("interrupt", KeyboardInterrupt)):
            FakeEngine.failure = failure
            with self.subTest(failure=failure), self.assertRaises(error):
                self.run_profile()
            result = self.evidence()
            self.assertEqual(result["samples"][0]["status"], "incomplete")
            self.assertEqual(len(result["samples"][0]["output"]), 1)
            self.assertEqual(result["sessions"][0]["exit_code"], 0)
            self.output.unlink()

    def test_bad_identity_and_readiness_never_search(self):
        for failure in ("missing_option", "readiness_error"):
            FakeEngine.failure = failure
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.run_profile()
            self.assertFalse(self.evidence()["samples"])
            self.assertTrue(self.evidence()["sessions"][0]["process_exited"])
            self.output.unlink()

    def test_late_output_exit_failure_and_bounded_forced_cleanup_visible(self):
        for failure in ("late_output", "bad_exit", "quit_timeout", "kill_timeout"):
            FakeEngine.failure = failure
            with self.subTest(failure=failure), self.assertRaises((ValueError, subprocess.TimeoutExpired)):
                self.run_profile()
            result = self.evidence()
            self.assertEqual(result["status"], "invalid_or_interrupted")
            self.assertTrue(any(x["kind"] == "cleanup" for x in result["failures"]))
            if failure.endswith("timeout"):
                self.assertTrue(result["sessions"][0]["forced_kill"])
            self.output.unlink()

    def test_artifact_drift_is_retained_and_invalidates_complete_matrix(self):
        FakeEngine.drift_path = self.engine
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        self.assertEqual(self.evidence()["artifact_drift"], ["engine"])
        self.assertEqual(self.evidence()["status"], "invalid_or_interrupted")


if __name__ == "__main__":
    unittest.main()
