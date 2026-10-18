#!/usr/bin/env python3
"""Exercise SMP measurement validity, comparison pairing and cleanup failures.

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
import profile_smp as profiler


def reply(position="startpos", depth=2, workers=1):
    board = profiler.board_for(position)
    move = next(iter(board.legal_moves)).uci()
    board.push_uci(move)
    ponder = next(iter(board.legal_moves)).uci()
    return ([f"info depth {level} seldepth {level + 2} score cp 20 nodes {100 * level * workers} time {level} nps 100000 hashfull 4 pv {move} {ponder}"
             for level in range(1, depth + 1)]
            + [f"info nodes {(100 * depth + 10) * workers} time {depth + 1} nps 100000 hashfull 5",
               f"bestmove {move} ponder {ponder}"])


class ParserTests(unittest.TestCase):
    def check(self, lines, mode="depth"):
        return profiler.validate_result(lines, profiler.board_for("startpos"), mode, 2)

    def test_final_counts_include_work_after_last_completed_iteration(self):
        result = self.check(reply(workers=4))
        self.assertEqual(result["reported_nodes"], 840)
        self.assertEqual(result["iterations"][-1]["nodes"], 800)
        self.assertEqual(result["completed_depth"], 2)

    def test_optional_syzygy_counter_is_validated(self):
        lines = reply()
        lines[-2] += " tbhits 3"
        self.assertEqual(self.check(lines)["final_aggregate"]["tbhits"], 3)
        for bad in ("-1", "nan", "3 tbhits 4"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.check([line.replace("tbhits 3", "tbhits " + bad) for line in lines])

    def test_missing_duplicate_and_out_of_order_totals_fail(self):
        lines = reply()
        for case in (lines[:-2] + lines[-1:], lines[:-1] + lines[-2:],
                     [lines[-2]] + lines[:-2] + lines[-1:],
                     [line.replace("nodes 210 time", "nodes 199 time") for line in lines],
                     [line.replace("nodes 210 time 3", "nodes 210 time 1") for line in lines]):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_bounds_bad_numbers_and_missing_fields_fail(self):
        for old, new in (("hashfull 4", "hashfull 1001"), ("hashfull 4", "hashfull -1"),
                         ("hashfull 4", "hashfull 4 hashfull 4"), ("hashfull 4 ", ""),
                         ("nodes 100", "nodes 1.5"), ("nodes 100", "nodes １２３"),
                         ("nodes 100", "nodes 18446744073709551616"),
                         ("score cp 20", "score cp nan"), ("score cp 20", "score cp --1"),
                         ("score cp 20", "score win 20"), ("depth 2 seldepth 4", "depth 0 seldepth 1")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.check([line.replace(old, new) for line in reply()])

    def test_every_pv_bestmove_and_ponder_are_legal_and_consistent(self):
        lines = reply()
        for case in ([line.replace("pv g1h3 g8h6", "pv e2e5 g8h6") for line in lines],
                     [line.replace("pv g1h3 g8h6", "pv g1h3 e2e4") for line in lines],
                     lines[:-1] + ["bestmove e2e5"], lines[:-1] + ["bestmove e2e4"],
                     lines[:-1] + ["bestmove 0000"],
                     lines[:-1] + ["bestmove g1h3 ponder e2e4"],
                     lines[:-1] + ["bestmove g1h3 ponder 0000"],
                     [line.replace("pv g1h3 g8h6", "pv g1h3 0000") for line in lines],
                     lines[:-1] + ["bestmove g1h3 ponder e7e5"]):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_terminal_record_errors_and_diagnostic_overhead_fail_closed(self):
        for case in (reply()[:-1], reply() + ["bestmove g1h3"], reply() + ["info nodes 0"],
                     ["info string error: failed"] + reply(), ["garbage"] + reply(),
                     ["info string search-summary v1 nodes 1"] + reply(),
                     ["info string ordering v1 policy mvv-lva"] + reply(),
                     ["info string lmr v1 enabled false"] + reply()):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_time_search_may_complete_less_depth_but_depth_search_must_finish(self):
        self.check(reply(depth=1), "movetime")
        with self.assertRaisesRegex(ValueError, "finish the requested depth"):
            self.check(reply(depth=1))
        with self.assertRaisesRegex(ValueError, "exceeded"):
            self.check(reply(depth=3))

    def test_signed_mate_values_are_accepted(self):
        for score in ("mate 3", "mate -2", "cp -23"):
            result = self.check([line.replace("cp 20", score) for line in reply()])
            self.assertEqual(result["score"]["value"], int(score.split()[1]))

    def test_selective_depth_can_be_less_than_nominal_after_cached_cutoffs(self):
        result = self.check([line.replace("seldepth 4", "seldepth 1") for line in reply()])
        self.assertEqual(result["completed_depth"], 2)

    def test_completed_depth_must_not_repeat_or_skip_iterations(self):
        lines = reply()
        for case in ([lines[0]] + lines, lines[1:],
                     [line.replace("depth 2 seldepth", "depth 3 seldepth") for line in lines]):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_referee_version_and_bad_root_history_fail(self):
        with patch.object(profiler, "chess", None), self.assertRaisesRegex(ValueError, "chess==1.11.2"):
            profiler.board_for("startpos")
        for position in ("startpos\nquit", "startpos wrong e2e4", "startpos moves e2e5", "startpos moves 0000", "fen bogus",
                         "startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                profiler.board_for(position)


def samples():
    result = []
    for index in range(len(profiler.POSITIONS)):
        for workers in (1, 2, 4):
            # Twice the workers has twice the recorded nodes, but equal elapsed
            # time and depth: higher aggregate throughput alone is not deeper.
            result.append({"position_index": index, "repetition": 0, "mode": "movetime",
                           "threads": workers, "warmup": False, "status": "complete", "elapsed_seconds": 1.,
                           "result": {"reported_nodes": 1000 * workers, "completed_depth": 5,
                                      "bestmove": "e2e4", "score": {"type": "cp", "value": 20}}})
    return result


class SummaryTests(unittest.TestCase):
    def test_throughput_does_not_masquerade_as_depth_or_latency_gain(self):
        summary = profiler.summarize(samples(), (1, 2, 4), 1, ("movetime",))
        many = summary["comparisons"][-1]
        self.assertAlmostEqual(many["throughput_ratio_geomean"], 4.)
        self.assertEqual(many["latency_ratio_geomean"], 1.)
        self.assertEqual(many["completed_depth_difference"]["median"], 0)

    def test_incomplete_duplicate_unexpected_and_unusable_samples_fail(self):
        duplicate = samples() + samples()[:1]
        incomplete = samples()
        incomplete[-1]["status"] = "incomplete"
        zero = samples()
        zero[-1]["elapsed_seconds"] = 0.
        infinite = samples()
        infinite[-1]["elapsed_seconds"] = float("inf")
        unknown = samples()
        unknown[-1]["threads"] = 8
        for case in (duplicate, incomplete, zero, infinite, unknown, samples()[:-1]):
            with self.subTest(case=case), self.assertRaises(ValueError):
                profiler.summarize(case, (1, 2, 4), 1, ("movetime",))

    def test_rotating_reversed_orders_balance_every_slot(self):
        orders = [profiler.run_order((1, 2, 4), block) for block in range(6)]
        self.assertEqual(len({tuple(order) for order in orders}), 6)
        for slot in range(3):
            self.assertEqual(sorted(order[slot] for order in orders), [1, 1, 2, 2, 4, 4])


class FakeEngine:
    instances, failure, mutate = [], None, None

    def __init__(self, _):
        self.sent, self.transcript, self.closed = [], [], False
        self.position, self.depth, self.workers = "startpos", 2, 1
        self.instances.append(self)

    def send(self, command):
        self.sent.append(command)
        if command.startswith("position "):
            self.position = command[len("position "):]
        elif command.startswith("go depth "):
            self.depth = int(command.split()[-1])
        elif command.startswith("setoption name Threads "):
            self.workers = int(command.split()[-1])

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            names = ("Hash", "Threads", "EvalFile", "Ponder", "Move Overhead", "Time Policy",
                     "Search Diagnostics", "Late Move Reductions", "Capture Ordering")
            lines = [f"option name {name} type string" for name in names if self.failure != "option" or name != "Threads"] + ["uciok"]
        elif prefix == "readyok":
            lines = (["info string error: rejected", "readyok"] if self.failure == "position" and "ucinewgame" in self.sent else ["readyok"])
            if self.failure == "stale" and "ucinewgame" in self.sent:
                lines = ["bestmove g1h3", "readyok"]
        else:
            lines = reply(self.position, self.depth, self.workers)
            if self.failure == "timeout":
                self.transcript.extend(lines[:1])
                raise TimeoutError("Injected timeout")
            if self.failure == "illegal":
                lines[-1] = "bestmove e2e5"
            if self.mutate:
                self.mutate.write_text("changed input")
        self.transcript.extend(lines)
        return lines

    def __enter__(self): return self
    def __exit__(self, *_): self.closed = True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-smp-profile-")
        self.root = Path(self.temporary.name)
        self.binary, self.network, self.output = [self.root / name for name in ("engine", "network", "profile.json")]
        self.binary.write_text("fake engine")
        self.network.write_text("fake network")
        FakeEngine.instances, FakeEngine.failure, FakeEngine.mutate = [], None, None
        self.budget = {"max_cpu_workers": 4, "memory_fraction": .5}
        patches = [patch.object(profiler, "Engine", FakeEngine),
                   patch.object(profiler, "NETWORK_SHA256", profiler.digest(self.network)),
                   patch.object(profiler, "NETWORK_BYTES", self.network.stat().st_size),
                   patch.object(profiler, "current_budget", return_value=self.budget),
                   patch.object(profiler, "physical_memory", return_value=8 * 1024**3)]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self): self.temporary.cleanup()

    def run_profile(self, **kwargs):
        options = dict(mode="both", depth=2, repeats=1, warmups=0)
        options.update(kwargs)
        return profiler.profile(self.binary, self.network, self.output, **options)

    def test_bounded_matrix_uses_one_engine_fixed_shared_hash_and_clean_state(self):
        report = self.run_profile(warmups=1)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["samples"]), 36)
        self.assertEqual(len(FakeEngine.instances), 1)
        engine = FakeEngine.instances[0]
        self.assertTrue(engine.closed)
        self.assertEqual(engine.sent.count("setoption name Hash value 64"), 1)
        self.assertEqual(engine.sent.count("ucinewgame"), 36)
        self.assertIn("setoption name Search Diagnostics value false", engine.sent)
        self.assertEqual(report["assets"]["binary"]["sha256"], report["after_sha256"]["binary"])
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")

    def test_existing_output_or_temporary_file_is_preserved(self):
        for path in (self.output, self.output.with_suffix(".json.tmp")):
            with self.subTest(path=path):
                path.write_text("preserve")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    self.run_profile()
                self.assertEqual(path.read_text(), "preserve")
                path.unlink()
        self.assertFalse(FakeEngine.instances)

    def test_invalid_input_bounds_fail_before_starting(self):
        for options in ({"threads": ()}, {"threads": (2, 4)}, {"threads": (1, 1)}, {"threads": (True, 2)},
                        {"threads": (1, 65)}, {"repeats": 0}, {"warmups": -1}, {"warmups": 3},
                        {"hash_mb": 0}, {"depth": 9}, {"mode": "heldout"}, {"movetime_ms": 99},
                        {"search_timeout": float("nan")}, {"total_timeout": 301}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_profile(**options)
        self.assertFalse(FakeEngine.instances)

    def test_cpu_and_memory_admission_fail_before_starting(self):
        with patch.object(profiler, "current_budget", return_value={"max_cpu_workers": 3, "memory_fraction": .5}):
            with self.assertRaisesRegex(ValueError, "local budget"):
                self.run_profile()
        with patch.object(profiler, "physical_memory", return_value=1024):
            with self.assertRaisesRegex(ValueError, "local budget"):
                self.run_profile()
        self.assertFalse(FakeEngine.instances)

    def test_live_override_stops_before_disallowed_next_search(self):
        calls = [self.budget, self.budget, {"max_cpu_workers": 1, "memory_fraction": .5}]
        with patch.object(profiler, "current_budget", side_effect=calls), self.assertRaisesRegex(ValueError, "local budget"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(len(report["samples"]), 1)
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertTrue(FakeEngine.instances[0].closed)

    def test_failures_preserve_partial_output_and_close_the_engine(self):
        for failure, error in (("timeout", TimeoutError), ("illegal", ValueError)):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(error):
                    self.run_profile()
                report = json.loads(self.output.read_text())
                self.assertEqual(report["status"], "invalid_or_interrupted")
                self.assertNotIn("summary", report)
                self.assertTrue(report["samples"][-1]["output"])
                self.assertTrue(FakeEngine.instances[-1].closed)
                self.output.unlink()

    def test_preparation_error_or_missing_option_prevents_search(self):
        for failure in ("position", "option"):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(ValueError):
                    self.run_profile()
                self.assertFalse(any(command.startswith("go ") for command in FakeEngine.instances[-1].sent))
                self.assertTrue(FakeEngine.instances[-1].closed)
                self.output.unlink()

    def test_stale_worker_output_before_readiness_invalidates_measurement(self):
        FakeEngine.failure = "stale"
        with self.assertRaisesRegex(ValueError, "stale worker report"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(report["samples"][-1]["preparation_output"], ["bestmove g1h3", "readyok"])
        self.assertFalse(any(command.startswith("go ") for command in FakeEngine.instances[-1].sent))
        self.assertTrue(FakeEngine.instances[-1].closed)

    def test_wrong_binary_and_network_pins_prevent_startup(self):
        with self.assertRaisesRegex(ValueError, "requested SHA-256"):
            self.run_profile(expected_engine_sha256="0" * 64)
        self.network.write_text("wrong network")
        with self.assertRaisesRegex(ValueError, "pinned SF19"):
            self.run_profile()
        self.assertFalse(FakeEngine.instances)

    def test_changed_input_preserves_evidence_and_stops_the_matrix(self):
        FakeEngine.mutate = self.binary
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(len(report["samples"]), 1)
        self.assertNotEqual(report["after_sha256"]["binary"], report["assets"]["binary"]["sha256"])
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertTrue(FakeEngine.instances[0].closed)

    def test_total_time_deadline_cleans_up_and_records_failure(self):
        with patch.object(profiler.time, "monotonic", side_effect=[0., 1000.]):
            with self.assertRaisesRegex(TimeoutError, "total time"):
                self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(report["samples"], [])
        self.assertTrue(FakeEngine.instances[0].closed)


if __name__ == "__main__":
    unittest.main()
