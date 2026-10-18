#!/usr/bin/env python3
"""Check ordering-profile evidence, cold/warm isolation and failure cleanup.

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
import profile_countermove as profiler


def reply(depth=2):
    return ([f"info depth {level} seldepth {level + 2} score cp 20 nodes {100 * level} "
             f"time {level} nps 100000 hashfull 4 tbhits 0 pv g1h3 g8h6"
             for level in range(1, depth + 1)]
            + [f"info nodes {100 * depth + 10} time {depth + 1} nps 100000 hashfull 5 tbhits 0",
               "bestmove g1h3 ponder g8h6"])


class RootAndParserTests(unittest.TestCase):
    def check(self, lines, mode="depth"):
        return profiler.validate_result(lines, profiler.board_for("startpos"), mode, 2)

    def test_complete_corpus_has_all_exposed_roots_without_deduplication(self):
        document, positions = profiler.load_positions(profiler.DEFAULT_POSITIONS)
        self.assertEqual(len(positions), 15)
        self.assertEqual(sum(p["position"].startswith("fen ") for p in positions), 12)
        self.assertEqual(len(document["sources"]), 2)
        for source, expected in document["sources"].items():
            self.assertEqual(profiler.digest(profiler.ROOT / source), expected)

    def test_full_history_and_fen_roots(self):
        board = profiler.board_for("startpos moves e2e4 c7c5")
        self.assertEqual(len(board.move_stack), 2)
        self.assertEqual(profiler.board_for("fen " + board.fen()).fen(), board.fen())

    def test_invalid_null_terminal_and_draw_roots_are_rejected(self):
        for position in (None, "", "startpos\nquit", "startpos garbage", "startpos moves",
                         "startpos moves 0000", "startpos moves e2e5", "fen invalid",
                         "fen 8/8/8/8/8/8/8/K6k w - - 0 1",
                         "startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                profiler.board_for(position)

    def test_missing_referee_fails_before_search(self):
        with patch.object(profiler, "chess", None), self.assertRaisesRegex(ValueError, "chess==1.11.2"):
            profiler.board_for("startpos")

    def test_unfinished_node_accounting_includes_only_work_after_last_iteration(self):
        result = self.check(reply())
        self.assertEqual(result["unfinished_nodes"], 10)
        self.assertEqual(result["reported_nodes"], 210)
        self.assertEqual(result["seldepth"], 4)

    def test_all_pvs_and_final_moves_are_legal(self):
        for old, new in (("pv g1h3 g8h6", "pv g1h3 e2e4"),
                         ("pv g1h3 g8h6", "pv g1h3 0000"),
                         ("bestmove g1h3", "bestmove e2e5"),
                         ("ponder g8h6", "ponder e7e5")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.check([line.replace(old, new) for line in reply()])

    def test_diagnostics_tablebase_hits_and_score_bounds_fail(self):
        for case in (["info string countermove v1 enabled true lookups 1 matches 0 updates 0"] + reply(),
                     ["info string error: failed"] + reply(),
                     [line.replace("tbhits 0", "tbhits 1") for line in reply()],
                     [line.replace(" tbhits 0", "") for line in reply()],
                     [line.replace("tbhits 0", "tbhits 0 tbhits 0") for line in reply()],
                     [line.replace("score cp 20", "score cp 20 lowerbound") for line in reply()]):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_missing_totals_duplicate_bestmove_and_wrong_depth_fail(self):
        for case in (reply()[:-2] + reply()[-1:], reply() + reply()[-1:], reply(depth=1), reply(depth=3)):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)
        self.check(reply(depth=1), "movetime")

    def test_mate_scores_and_reduced_cached_seldepth_are_accepted(self):
        result = self.check([line.replace("cp 20", "mate -3").replace("seldepth 4", "seldepth 1")
                             for line in reply()])
        self.assertEqual(result["score"], {"type": "mate", "value": -3})
        self.assertEqual(result["seldepth"], 1)


def samples():
    result = []
    for mode in profiler.MODES:
        for temperature in profiler.TEMPERATURES:
            for policy in profiler.POLICIES:
                parsed = profiler.validate_result(reply(), profiler.board_for("startpos"), mode, 2)
                if policy == "on":
                    parsed["reported_nodes"] *= 2
                    parsed["iterations"][0]["score"] = {"type": "cp", "value": 19}
                result.append({"mode": mode, "temperature": temperature, "position_index": 0,
                               "repetition": 0, "policy": policy, "status": "complete",
                               "elapsed_seconds": 1. if policy == "off" else 2., "result": parsed})
    return result


class SummaryTests(unittest.TestCase):
    def summarize(self, value):
        return profiler.summarize(value, [{"id": "test-root"}], 1)

    def test_reports_all_groups_ratios_and_common_depth_score_deviations(self):
        summary = self.summarize(samples())
        self.assertEqual(len(summary["aggregate"]), 4)
        self.assertEqual(len(summary["per_position"]), 4)
        self.assertEqual(len(summary["pairs"]), 4)
        for group in summary["aggregate"]:
            self.assertEqual(group["total_node_ratio_on_over_off"], 2.)
            self.assertEqual(group["total_elapsed_ratio_on_over_off"], 2.)
            self.assertEqual(group["score_difference_pairs"], 1)
            self.assertEqual(group["final_score_difference_pairs"], 0)
        self.assertEqual(summary["pairs"][0]["common_depth_score_differences"][0]["depth"], 1)

    def test_missing_duplicate_and_unexpected_cells_are_rejected(self):
        unknown = samples()
        unknown[-1]["temperature"] = "hot"
        for case in (samples()[:-1], samples() + samples()[:1], unknown):
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.summarize(case)

    def test_incomplete_nonfinite_and_nonpositive_measurements_are_rejected(self):
        for field, value in (("status", "incomplete"), ("elapsed_seconds", float("inf")),
                             ("elapsed_seconds", float("nan")), ("elapsed_seconds", 0.)):
            modified = samples()
            modified[-1][field] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.summarize(modified)
        modified = samples()
        modified[-1]["result"]["reported_nodes"] = 0
        with self.assertRaises(ValueError):
            self.summarize(modified)

    def test_order_alternates_by_root_repetition_and_mode(self):
        for root, repetition, mode in ((0, 0, 0), (2, 4, 0), (1, 0, 1)):
            self.assertEqual(profiler.run_order(repetition, root, mode), ("off", "on"))
            self.assertEqual(profiler.run_order(repetition + 1, root, mode), ("on", "off"))


class FakeEngine:
    instances = []
    searches = 0
    fail_at = None
    failure = TimeoutError("synthetic timeout")
    mutate_at = None
    mutate = None
    required_options = ("Hash", "Threads", "EvalFile", "Ponder", "Move Overhead", "Time Policy",
                        "Late Move Reductions", "Capture Ordering", "SyzygyPath", "SyzygyProbeLimit",
                        "Search Diagnostics", "Countermove Ordering")

    def __init__(self, path):
        self.commands, self.transcript, self.closed = [], [], False
        self.waits = []
        type(self).instances.append(self)

    def send(self, command):
        self.commands.append(command)

    def until(self, prefix, timeout=30):
        self.waits.append((prefix, timeout))
        if prefix == "uciok":
            lines = [f"option name {name} type string" for name in self.required_options] + ["uciok"]
        elif prefix == "readyok":
            lines = ["readyok"]
        else:
            type(self).searches += 1
            if type(self).searches == self.fail_at:
                self.transcript.append(reply()[0])
                raise self.failure
            lines = reply()
            if type(self).searches == self.mutate_at:
                type(self).mutate()
        self.transcript.extend(lines)
        return lines

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        directory = Path(self.temporary.name)
        self.binary, self.network = directory / "engine", directory / "network"
        self.binary.write_bytes(b"fake engine")
        self.network.write_bytes(b"fake network")
        self.corpus, self.output = directory / "corpus.json", directory / "result.json"
        self.corpus.write_text(json.dumps({"schema_version": 1, "positions": [{"id": "root", "position": "startpos"}]}))
        FakeEngine.instances, FakeEngine.searches = [], 0
        FakeEngine.fail_at, FakeEngine.mutate_at, FakeEngine.mutate = None, None, None
        FakeEngine.failure = TimeoutError("synthetic timeout")
        for name, value in (("Engine", FakeEngine), ("NETWORK_SHA256", profiler.digest(self.network)),
                            ("resource_check", lambda *args: {"active_search_workers": 1, "resident_engines": 2})):
            patcher = patch.object(profiler, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_profile(self, **kwargs):
        return profiler.profile(self.binary, self.network, self.corpus, self.output,
                                depth=2, movetime_ms=1, repeats=1, **kwargs)

    def test_complete_profile_retains_raw_evidence_and_distinguishes_cold_warm(self):
        report = self.run_profile()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(len(report["samples"]), 8)
        self.assertEqual(len(report["summary"]["pairs"]), 4)
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))
        for engine in FakeEngine.instances:
            self.assertEqual(engine.commands.count("ucinewgame"), 2)
            self.assertEqual(sum(c.startswith("go ") for c in engine.commands), 4)
            self.assertIn("setoption name Search Diagnostics value false", engine.commands)
        for sample in report["samples"]:
            self.assertEqual("ucinewgame" in sample["preparation_commands"], sample["temperature"] == "cold")
            self.assertEqual(sample["status"], "complete")
            self.assertTrue(sample["output"])
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")

    def test_search_timeout_preserves_partial_evidence_and_closes_both_engines(self):
        FakeEngine.fail_at = 2
        with self.assertRaises(TimeoutError):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(report["samples"][-1]["status"], "incomplete")
        self.assertEqual(report["samples"][-1]["output"], [reply()[0]])
        self.assertTrue(report["after_sha256"])
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))

    def test_keyboard_interruption_preserves_evidence_and_cleans_up(self):
        FakeEngine.fail_at, FakeEngine.failure = 1, KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_profile()
        self.assertEqual(json.loads(self.output.read_text())["status"], "invalid_or_interrupted")
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))

    def test_artifact_drift_invalidates_completed_searches(self):
        FakeEngine.mutate_at = 8
        FakeEngine.mutate = lambda: self.binary.write_bytes(b"modified engine")
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(len(report["samples"]), 8)
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))

    def test_preparation_failure_closes_opened_engines(self):
        with patch.object(profiler, "prepare", side_effect=ValueError("missing option")):
            with self.assertRaisesRegex(ValueError, "missing option"):
                self.run_profile()
        self.assertTrue(FakeEngine.instances[0].closed)
        self.assertEqual(json.loads(self.output.read_text())["status"], "invalid_or_interrupted")

    def test_total_budget_expires_before_next_search(self):
        with patch.object(profiler.time, "monotonic", side_effect=[0., 601.]), self.assertRaises(TimeoutError):
            self.run_profile()
        self.assertEqual(FakeEngine.searches, 0)
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))
        self.assertEqual(json.loads(self.output.read_text())["status"], "invalid_or_interrupted")

    def test_all_blocking_protocol_waits_share_total_budget(self):
        with patch.object(profiler.time, "monotonic", return_value=0.):
            self.run_profile(total_timeout=60.)
        for engine in FakeEngine.instances:
            self.assertTrue(all(0 < timeout <= 60. for _, timeout in engine.waits))
            self.assertIn(("uciok", 30.), engine.waits)
            self.assertIn(("readyok", 60.), engine.waits)

    def test_duplicate_output_after_final_search_invalidates_and_is_retained(self):
        original_until = FakeEngine.until

        def duplicated_final_reply(engine, prefix, timeout=30):
            lines = original_until(engine, prefix, timeout)
            if prefix == "readyok" and FakeEngine.searches == 8:
                lines = ["bestmove g1h3 ponder g8h6"] + lines
            return lines

        with patch.object(FakeEngine, "until", duplicated_final_reply), self.assertRaisesRegex(ValueError, "readiness barrier"):
            self.run_profile()
        report = json.loads(self.output.read_text())
        self.assertEqual(report["status"], "invalid_or_interrupted")
        self.assertEqual(report["samples"][-1]["post_search_output"][0], "bestmove g1h3 ponder g8h6")
        self.assertTrue(all(engine.closed for engine in FakeEngine.instances))

    def test_readiness_refuses_stale_search_output(self):
        profiler.require_readiness(["readyok"])
        for lines in ([], ["bestmove g1h3", "readyok"], ["info depth 1", "readyok"]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                profiler.require_readiness(lines)

    def test_existing_output_and_bad_limits_are_rejected_without_processes(self):
        self.output.write_text("preserved")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_profile()
        self.assertEqual(self.output.read_text(), "preserved")
        self.assertEqual(FakeEngine.instances, [])
        for timeout in (float("nan"), -1., 121.):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.run_profile(search_timeout=timeout)

    def test_invalid_corpus_and_source_drift_fail_before_process_creation(self):
        document = json.loads(self.corpus.read_text())
        document["sources"] = {"tools/bench.py": "0" * 64}
        self.corpus.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "source corpus changed"):
            self.run_profile()
        self.assertEqual(FakeEngine.instances, [])
        document.pop("sources")
        document["positions"] *= 2
        self.corpus.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "unique"):
            self.run_profile()


if __name__ == "__main__":
    unittest.main()
