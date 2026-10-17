#!/usr/bin/env python3
"""Exercise CPU-profile evidence and cleanup without engines or macOS sampling.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_cpu as profiler


IDENTITY = [
    "option name Threads type spin default 1 min 1 max 1",
    "option name Hash type spin default 64 min 1 max 16384",
    "option name Time Policy type combo default classic var classic var forecast",
    "option name Late Move Reductions type check default false",
    "option name Capture Ordering type combo default mvv-lva var mvv-lva var see",
    "option name Search Diagnostics type check default false",
    "option name Ponder type check default false",
    "option name Move Overhead type spin default 20 min 0 max 5000",
    "option name EvalFile type string default default.nnue", "uciok",
]


class Clock:
    def __init__(self):
        self.now = 10**9

    def monotonic_ns(self):
        self.now += 1000000
        return self.now

    def sleep(self, seconds):
        self.now += int(seconds * 10**9)


class Peer:
    """Synchronous fake: no child, thread, engine binary or sampled process."""
    def __init__(self, scenario):
        self.scenario = scenario
        self.process = self
        self.pid = 4242
        self.transcript, self.sent = [], []
        self.closed = False
        self.searches = 0

    def poll(self):
        return 0 if self.closed else None

    def send(self, command):
        self.sent.append(command)
        if command.startswith("position "):
            self.board = profiler.board_for(command[len("position "):])

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            output = self.scenario.identity
        elif prefix == "readyok":
            if self.scenario.failure == "prepare" and "ucinewgame" in self.sent:
                self.transcript.append("info string partial preparation")
                raise TimeoutError("injected preparation timeout")
            output = ["readyok"]
        else:
            self.searches += 1
            if self.scenario.failure == "search" and self.searches == 13:
                self.transcript.append("info string partial search")
                raise TimeoutError("injected search timeout")
            if self.scenario.failure == "overrun" and self.searches == 13:
                self.scenario.clock.sleep(121)
            depth = int(self.sent[-1].split()[-1])
            best = next(iter(self.board.legal_moves)).uci()
            output = [f"info depth {value} seldepth {value} score cp 12 nodes {value * 40} time 1 pv {best}" for value in range(1, depth + 1)]
            output += ["bestmove " + best]
            if self.scenario.failure == "signature" and self.searches == 13:
                output = [line.replace("score cp 12", "score cp 13") for line in output]
        self.transcript.extend(output)
        return output

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class Sampler:
    def __init__(self, scenario, command, stdout, stderr):
        self.scenario, self.command = scenario, command
        self.returncode = None
        self.terminated = self.killed = False
        self.until_ns = scenario.clock.now + int(command[2]) * 10**9
        self.path = Path(command[-1])
        if scenario.failure != "readiness":
            stdout.write(f"Sampling process {command[1]} for {command[2]} seconds with 1 millisecond of run time between samples\n")
            stdout.flush()

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        if self.terminated or self.killed:
            self.returncode = -9 if self.killed else -15
        else:
            if self.scenario.failure == "wait":
                raise subprocess.TimeoutExpired(self.command, timeout)
            if self.scenario.failure != "early":
                self.scenario.clock.now = max(self.scenario.clock.now, self.until_ns)
            self.returncode = 3 if self.scenario.failure == "sampler" else 0
            if self.scenario.failure != "empty":
                self.path.write_text("Synthetic call stacks; not real profiling data.\n")
            if self.scenario.failure == "drift":
                self.scenario.binary.write_bytes(b"changed executable")
        return self.returncode


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.binary, self.network, self.sampler_path = (self.directory / name for name in ("engine", "network", "sample"))
        for path in (self.binary, self.network, self.sampler_path):
            path.write_bytes(path.name.encode())
        self.output = self.directory / "profile"
        self.clock, self.identity, self.failure = Clock(), IDENTITY.copy(), None
        self.peer = self.sampler = None
        self.resource_calls = 0
        for target, value in (("sys.platform", "darwin"), ("SAMPLER", self.sampler_path),
                              ("platform.platform", lambda: "mock-macOS"), ("platform.machine", lambda: "mock-arm64"),
                              ("time.monotonic_ns", self.clock.monotonic_ns), ("time.sleep", self.clock.sleep),
                              ("Engine", self.engine), ("subprocess.Popen", self.start_sampler),
                              ("resource_check", self.resource)):
            self.stack.enter_context(patch("profile_cpu." + target, value))

    def engine(self, path):
        self.assertEqual(path, self.binary)
        self.peer = Peer(self)
        return self.peer

    def start_sampler(self, command, stdout, stderr):
        self.sampler = Sampler(self, command, stdout, stderr)
        return self.sampler

    def resource(self, network, hash_mb):
        self.resource_calls += 1
        self.assertEqual(network, self.network)
        self.assertEqual(hash_mb, 64)
        if self.failure == "budget" and self.resource_calls == 14:
            raise ValueError("injected changed resource budget")
        return {"active_search_workers": 1, "percent": 50}

    def run_profile(self, **kwargs):
        positions = kwargs.pop("positions", profiler.DEFAULT_POSITIONS)
        return profiler.profile(self.binary, self.network, positions, self.output, **kwargs)

    def write_positions(self, name, entries):
        path = self.directory / (name + ".json")
        path.write_text(json.dumps({"openings": entries}))
        return path

    def report(self):
        return json.loads((self.output / "report.json").read_text())

    def test_complete_fixes_options_and_records_only_sampled_sweeps(self):
        report = self.run_profile()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["samples"]), 36)
        self.assertEqual(sum(item["warmup"] for item in report["samples"]), 12)
        self.assertEqual(report["settings"]["root_count"], 12)
        self.assertEqual(list(report["settings"]["position_depths"].values()), [5] * 12)
        self.assertEqual(self.resource_calls, 37)
        self.assertEqual(report["artifact_drift"], [])
        self.assertTrue(self.peer.closed)
        self.assertFalse(self.sampler.terminated)
        for name, value in profiler.BASELINE_OPTIONS.items():
            self.assertIn(f"setoption name {name} value {value}", self.peer.sent)
        sampled = [item for item in report["samples"] if not item["warmup"]]
        timing = report["sampler"]
        self.assertTrue(all(timing["ready_monotonic_ns"] <= item["started_monotonic_ns"] < item["ended_monotonic_ns"] <= timing["conservative_end_monotonic_ns"] for item in sampled))
        self.assertGreaterEqual(timing["finished_monotonic_ns"], timing["conservative_end_monotonic_ns"])
        self.assertEqual(self.sampler.command[1:6], ["4242", "120", "1", "-mayDie", "-file"])
        self.assertIn("tools/profile_cpu.py", report["assets"])
        self.assertIn("tools/profile_lmr.py", report["assets"])
        self.assertTrue(report["output_sha256"]["sample.txt"])

    def test_requested_depth_and_repeats_do_not_change_fixed_warmups(self):
        report = self.run_profile(duration=10, depth=2, repeats=1, search_timeout=1.)
        self.assertEqual([s["depth"] for s in report["samples"]], [5] * 12 + [2] * 12)
        self.assertEqual(self.sampler.command[2], "10")

    def test_one_six_and_twelve_roots_preserve_histories_and_search_counts(self):
        original = json.loads(profiler.DEFAULT_POSITIONS.read_text())["openings"]
        for count in (1, 6, 12):
            with self.subTest(count=count):
                self.output = self.directory / f"roots-{count}"
                self.resource_calls = 0
                path = self.write_positions(f"input-{count}", original[:count])
                report = self.run_profile(positions=path, repeats=2)
                self.assertEqual(report["settings"]["root_count"], count)
                self.assertEqual(len(report["samples"]), count * 3)
                self.assertEqual(self.resource_calls, count * 3 + 1)
                self.assertEqual([item["position_index"] for item in report["samples"]], list(range(count)) * 3)
                expected = ["position startpos moves " + " ".join(entry["moves"]) for entry in original[:count]]
                self.assertEqual([command for command in self.peer.sent if command.startswith("position ")], expected * 3)
                self.assertEqual(["position " + item["position"] for item in report["positions"]], expected)

    def test_per_root_depths_override_default_only_for_sampled_searches(self):
        original = json.loads(profiler.DEFAULT_POSITIONS.read_text())["openings"][:6]
        original[0]["profile_depth"], original[-1]["profile_depth"] = 1, 12
        path = self.write_positions("mixed-depths", original)
        report = self.run_profile(positions=path, depth=6, repeats=2)
        depths = [1, 6, 6, 6, 6, 12]
        self.assertEqual(report["settings"]["depth"], 6)
        self.assertEqual(list(report["settings"]["position_depths"].values()), depths)
        self.assertEqual([item["profile_depth"] for item in report["positions"]], depths)
        self.assertEqual([item["depth"] for item in report["samples"]], [5] * 6 + depths * 2)
        self.assertEqual([command for command in self.peer.sent if command.startswith("go ")],
                         [f"go depth {depth}" for depth in [5] * 6 + depths * 2])
        self.assertTrue(all(len(item["signature"]["iterations"]) == item["depth"] for item in report["samples"]))

    def test_existing_directory_is_not_reused_even_when_empty(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_profile()
        self.assertIsNone(self.peer)

    def test_cli_ranges_and_platform_fail_before_starting_a_child(self):
        for kwargs in ({"duration": 9}, {"duration": 301}, {"depth": 0}, {"depth": 13},
                       {"repeats": 0}, {"repeats": 11}, {"search_timeout": 31},
                       {"search_timeout": 0}, {"search_timeout": float("nan")},
                       {"search_timeout": float("inf")}, {"search_timeout": True},
                       {"search_timeout": "1"}, {"depth": True}, {"depth": 5.0},
                       {"depth": "5"}, {"depth": None}, {"repeats": True},
                       {"repeats": 2.0}, {"duration": 120.0}, {"duration": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_profile(**kwargs)
        with patch("profile_cpu.sys.platform", "linux"), self.assertRaisesRegex(ValueError, "macOS"):
            self.run_profile()
        self.assertIsNone(self.peer)

    def test_missing_wrong_type_or_unsupported_option_rejected(self):
        for identity in ([line for line in IDENTITY if not line.startswith("option name Ponder ")],
                         [line.replace("Late Move Reductions type check", "Late Move Reductions type string") for line in IDENTITY],
                         [line.replace("var mvv-lva var see", "var see") for line in IDENTITY],
                         [line.replace("min 1 max 16384", "min 128 max 16384") for line in IDENTITY]):
            self.identity = identity
            peer = Peer(self)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                profiler.prepare(peer, self.network)
            self.assertFalse(any(command.startswith("go ") for command in peer.sent))

    def test_setup_failure_preserves_identity_transcript_and_closes_engine(self):
        self.identity = ["info string error: injected initialization error", "uciok"]
        with self.assertRaisesRegex(ValueError, "Engine reported"):
            self.run_profile()
        self.assertTrue(self.peer.closed)
        self.assertEqual(self.report()["protocol_output"], self.identity)
        self.assertIsNone(self.sampler)

    def test_search_timeout_preserves_partial_work_and_cleans_both_children(self):
        self.failure = "search"
        with self.assertRaises(TimeoutError):
            self.run_profile()
        report = self.report()
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(report["samples"][-1]["status"], "incomplete")
        self.assertIn("info string partial search", report["samples"][-1]["output"])
        self.assertTrue(self.peer.closed and self.sampler.terminated)
        self.assertEqual(report["sampler"]["returncode"], -15)

    def test_preparation_failure_preserves_partial_protocol(self):
        self.failure = "prepare"
        with self.assertRaises(TimeoutError):
            self.run_profile()
        self.assertIn("info string partial preparation", self.report()["samples"][-1]["preparation_output"])
        self.assertTrue(self.peer.closed)

    def test_readiness_failure_keeps_logs_and_never_starts_sampled_searches(self):
        self.failure = "readiness"
        with self.assertRaises(TimeoutError):
            self.run_profile()
        self.assertEqual(self.peer.searches, 12)
        self.assertTrue(self.sampler.terminated and self.peer.closed)
        self.assertTrue((self.output / "sampler.log").exists())

    def test_overrun_invalidates_work_instead_of_claiming_it_was_sampled(self):
        self.failure = "overrun"
        with self.assertRaisesRegex(RuntimeError, "exceeded"):
            self.run_profile()
        self.assertEqual(self.report()["samples"][-1]["status"], "incomplete")
        self.assertTrue(self.sampler.terminated and self.peer.closed)

    def test_changed_signatures_and_resource_budget_abort_bounded_sweep(self):
        for failure in ("signature", "budget"):
            self.failure = failure
            self.output = self.directory / failure
            self.resource_calls = 0
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.run_profile()
            self.assertTrue(self.sampler.terminated and self.peer.closed)
            self.assertEqual(self.report()["status"], "invalid_or_interrupted")

    def test_sampler_timeout_and_early_or_empty_report_are_invalid(self):
        for failure in ("wait", "early", "empty", "sampler"):
            self.failure, self.output = failure, self.directory / failure
            with self.subTest(failure=failure), self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                self.run_profile()
            self.assertTrue(self.peer.closed)
            self.assertIsNotNone(self.sampler.returncode)
            self.assertEqual(self.report()["status"], "invalid_or_interrupted")

    def test_artifact_drift_is_detected_and_preserved(self):
        self.failure = "drift"
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_profile()
        self.assertEqual(self.report()["artifact_drift"], ["binary"])
        self.assertTrue(self.peer.closed)

    def test_referee_rejects_illegal_pvs_bestmove_and_ponder(self):
        board = profiler.board_for("startpos")
        valid = ["info depth 1 seldepth 2 score cp 1 nodes 2 time 1 pv e2e4 e7e5", "bestmove e2e4 ponder e7e5"]
        profiler.validate_search(valid, 1, board)
        for before, after in (("e2e4", "e2e5"), ("pv e2e4 e7e5", "pv e2e4 e2e3"), ("ponder e7e5", "ponder e2e3")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                profiler.validate_search([line.replace(before, after) for line in valid], 1, board)
        with self.assertRaisesRegex(ValueError, "diagnostics"):
            profiler.validate_search(valid + ["info string search-summary v1"], 1, board)

    def test_invalid_full_history_or_wrong_root_count_fails_before_engine(self):
        original = json.loads(profiler.DEFAULT_POSITIONS.read_text())
        excess = [dict(original["openings"][0], id=f"root-{index}") for index in range(65)]
        for name, document in (("empty", {"openings": []}), ("count", {"openings": excess}),
                               ("illegal", dict(original, openings=[dict(original["openings"][0], moves=["e2e5"])] + original["openings"][1:])),
                               ("duplicate", dict(original, openings=[dict(original["openings"][1], id="duplicate-root")] + original["openings"][1:]))):
            path = self.directory / (name + ".json")
            path.write_text(json.dumps(document))
            with self.subTest(name=name), self.assertRaises(ValueError):
                profiler.profile(self.binary, self.network, path, self.directory / name)
        self.assertIsNone(self.peer)
        with patch.object(profiler.chess, "__version__", "0"), self.assertRaisesRegex(ValueError, "chess==1.11.2"):
            self.run_profile()

    def test_invalid_per_root_depth_is_rejected_before_engine_or_sampler(self):
        original = json.loads(profiler.DEFAULT_POSITIONS.read_text())["openings"][:6]
        for index, value in enumerate((True, False, 0, 13, 5.0, "5", None)):
            with self.subTest(value=value):
                self.output = self.directory / f"bad-depth-{index}"
                entries = original[:-1] + [dict(original[-1], profile_depth=value)]
                path = self.write_positions(f"bad-depth-input-{index}", entries)
                with self.assertRaisesRegex(ValueError, "profile_depth"):
                    self.run_profile(positions=path)
                self.assertEqual(self.report()["status"], "invalid_or_interrupted")
                self.assertEqual(self.report()["samples"], [])
                self.assertIsNone(self.peer)
                self.assertIsNone(self.sampler)

    def test_terminal_drawn_invalid_or_duplicate_roots_fail_before_engine(self):
        cases = {
            "mate": [{"id": "mate", "moves": ["f2f3", "e7e5", "g2g4", "d8h4"]}],
            "draw": [{"id": "draw", "moves": ["g1f3", "g8f6", "f3g1", "f6g8"] * 2}],
            "invalid-fen": [{"id": "invalid", "fen": "8/8/8/8/8/8/8/8 w - - 0 1", "moves": []}],
            "same-board-history": [{"id": "start", "moves": []},
                                   {"id": "cycle", "moves": ["g1f3", "g8f6", "f3g1", "f6g8"]}],
        }
        for name, entries in cases.items():
            with self.subTest(name=name):
                self.output = self.directory / name
                path = self.write_positions(name + "-input", entries)
                with self.assertRaises(ValueError):
                    self.run_profile(positions=path)
                self.assertIsNone(self.peer)
                self.assertIsNone(self.sampler)

    def test_maximum_sixty_four_distinct_roots_is_supported(self):
        board = profiler.board_for("startpos")
        entries = []
        for first in list(board.legal_moves)[:4]:
            after = board.copy()
            after.push(first)
            for second in after.legal_moves:
                entries.append({"id": f"root-{len(entries)}", "moves": [first.uci(), second.uci()]})
        path = self.write_positions("maximum", entries[:64])
        report = self.run_profile(positions=path, repeats=1, depth=1)
        self.assertEqual(report["settings"]["root_count"], 64)
        self.assertEqual(len(report["samples"]), 128)
        self.assertEqual([item["depth"] for item in report["samples"]], [5] * 64 + [1] * 64)

    def test_cleanup_escalates_to_kill_when_helper_ignores_terminate(self):
        class Stuck:
            returncode = None
            def poll(self): return self.returncode
            def terminate(self): pass
            def kill(self): self.returncode = -9
            def wait(self, timeout):
                if self.returncode is None: raise subprocess.TimeoutExpired("sample", timeout)
        record = {}
        profiler.stop_sampler(Stuck(), record)
        self.assertEqual(record, {"cleanup": "killed_after_failure", "returncode": -9})


if __name__ == "__main__":
    unittest.main()
