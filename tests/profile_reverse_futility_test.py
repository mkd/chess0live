#!/usr/bin/env python3
"""Engine-free checks of the fixed reverse-futility evidence and lifecycle gates.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import json
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_reverse_futility as profile


def transcript(board, *, depth=6, partial=0):
    move = next(iter(board.legal_moves)).uci()
    lines = [f"info depth {d} seldepth {d} score cp 10 nodes {d * 10} "
             f"time {d} nps 10000 hashfull {d} tbhits 0 pv {move}"
             for d in range(1, depth + 1)]
    return lines + [f"info nodes {depth * 10 + partial} time {depth} nps 10000 hashfull {depth} tbhits 0",
                    f"bestmove {move}"]


def samples():
    result = []
    for stage, config in profile.STAGES.items():
        for index, position in enumerate(profile.load_positions()):
            board = profile.board_for(position["position"])
            validated = profile.validate_result(transcript(board), board, config["mode"])
            for temperature in config["temperatures"]:
                for role in config["roles"]:
                    result.append({"stage": stage, "position_index": index, "role": role,
                                   "mode": config["mode"], "temperature": temperature,
                                   "status": "complete", "elapsed_seconds": .5,
                                   "result": copy.deepcopy(validated)})
    return result


class EvidenceChecks(unittest.TestCase):
    def test_frozen_corpus_is_legal_and_has_exact_order(self):
        positions = profile.load_positions()
        self.assertEqual(tuple(entry["id"] for entry in positions), profile.POSITION_IDS)
        self.assertEqual(len(positions), 6)
        for entry in positions:
            self.assertTrue(profile.board_for(entry["position"]).is_valid())

    def test_source_corpus_drift_rejects(self):
        with patch.object(profile, "CORPUS_SHA256", "changed"):
            with self.assertRaisesRegex(ValueError, "source corpus changed"):
                profile.load_positions()

    def test_selected_corpus_drift_rejects(self):
        with patch.object(profile, "POSITIONS_SHA256", "changed"):
            with self.assertRaisesRegex(ValueError, "selected roots changed"):
                profile.load_positions()

    def test_role_order_alternates_and_timed_order_reverses(self):
        for index in range(6):
            self.assertEqual(profile.role_order("reverse_work", index),
                             ("off", "on") if index % 2 == 0 else ("on", "off"))
            self.assertEqual(profile.role_order("equal_time", index),
                             profile.role_order("reverse_work", index)[::-1])

    def test_candidate_option_only_changes_one_factor(self):
        parent, off, on = [profile.options_for(role, Path("network")) for role in ("parent", "off", "on")]
        self.assertNotIn("Reverse Futility Pruning", parent)
        self.assertEqual(off.pop("Reverse Futility Pruning"), "false")
        self.assertEqual(on.pop("Reverse Futility Pruning"), "true")
        self.assertEqual(parent, off)
        self.assertEqual(off, on)
        self.assertEqual(parent["Null Move Pruning"], "false")

    def test_fixed_depth_rejects_unfinished_work_but_timed_retains_it(self):
        board = profile.board_for("startpos")
        lines = transcript(board, partial=3)
        with self.assertRaises(ValueError):
            profile.validate_result(lines, board, "depth")
        result = profile.validate_result(lines, board, "movetime")
        self.assertEqual(result["unfinished_nodes"], 3)
        self.assertEqual(result["seldepth"], 6)
        with self.assertRaises(ValueError):
            profile.validate_result(lines, board, "unknown")

    def test_diagnostics_bounds_tablebases_and_illegal_moves_fail(self):
        board = profile.board_for("startpos")
        original = transcript(board)
        corruptions = [
            ["info string reversefutility v1 enabled true"] + original,
            [line.replace("score cp 10", "score cp 10 lowerbound") for line in original],
            [line.replace("tbhits 0", "tbhits 1") for line in original],
            [line.replace(" tbhits 0", "") for line in original],
            [line.replace("pv g1h3", "pv 0000") for line in original],
            original + [original[-1]], original[1:],
        ]
        for mode in ("depth", "movetime"):
            for index, lines in enumerate(corruptions):
                with self.subTest(mode=mode, corruption=index):
                    with self.assertRaises(ValueError):
                        profile.validate_result(lines, board, mode)

    def test_all_sixty_cells_and_stage_totals(self):
        matrix = samples()
        self.assertEqual(len(matrix), 60)
        self.assertEqual([sum(s["stage"] == stage for s in matrix) for stage in profile.STAGES], [24, 24, 12])
        for stage, config in profile.STAGES.items():
            summary = profile.summarize(matrix, stage)
            self.assertEqual(len(summary["pairs"]), 6 * len(config["temperatures"]))
            for values in summary["totals_by_temperature"].values():
                self.assertEqual(values, {role: {"nodes": 360, "elapsed_seconds": 3., "unfinished_nodes": 0}
                                          for role in config["roles"]})

    def test_incomplete_duplicate_unknown_and_nonfinite_cells_fail(self):
        for stage in profile.STAGES:
            selected = [sample for sample in samples() if sample["stage"] == stage]
            for mutation in ("incomplete", "wrong_mode", "unknown", "nan", "zero_time", "zero_nodes"):
                changed = copy.deepcopy(selected)
                if mutation == "incomplete":
                    changed[0]["status"] = "incomplete"
                elif mutation == "wrong_mode":
                    changed[0]["mode"] = "unknown"
                elif mutation == "unknown":
                    changed[0]["position_index"] = 6
                elif mutation == "nan":
                    changed[0]["elapsed_seconds"] = float("nan")
                elif mutation == "zero_time":
                    changed[0]["elapsed_seconds"] = 0
                else:
                    changed[0]["result"]["reported_nodes"] = 0
                with self.subTest(stage=stage, mutation=mutation):
                    with self.assertRaises(ValueError):
                        profile.summarize(changed, stage)
            for changed in (selected[:-1], selected + selected[:1]):
                with self.assertRaises(ValueError):
                    profile.summarize(changed, stage)

    def test_parent_mismatch_blocks_gate(self):
        matrix = samples()
        target = next(s for s in matrix if s["stage"] == "parent_equivalence" and s["role"] == "off")
        target["result"]["signature"]["iterations"][0]["nodes"] += 1
        with self.assertRaisesRegex(ValueError, "Default-off search differs"):
            profile.summarize(matrix, "parent_equivalence")

    def test_pruned_changes_are_reported_instead_of_hidden(self):
        matrix = samples()
        target = next(s for s in matrix if s["stage"] == "reverse_work" and s["role"] == "on")
        target["result"]["iterations"][0]["score"]["value"] += 1
        target["result"]["reported_nodes"] = 30
        summary = profile.summarize(matrix, "reverse_work")
        pair = summary["pairs"][0]
        self.assertEqual(pair["node_ratio_right_over_left"], .5)
        self.assertEqual(pair["common_depth_score_or_pv_changes"][0]["right_score"]["value"], 11)
        self.assertEqual(summary["totals_by_temperature"]["cold"]["on"]["nodes"], 330)

    def test_timed_different_depth_and_unfinished_work_are_retained(self):
        matrix = samples()
        target = next(s for s in matrix if s["stage"] == "equal_time" and s["role"] == "on")
        board = profile.board_for(profile.load_positions()[0]["position"])
        target["result"] = profile.validate_result(transcript(board, depth=7, partial=8), board, "movetime")
        pair = profile.summarize(matrix, "equal_time")["pairs"][0]
        self.assertEqual(pair["completed_depths"], [6, 7])
        self.assertEqual(pair["unfinished_nodes"], [0, 8])
        self.assertIsNone(pair["same_signature"])


class ResourceChecks(unittest.TestCase):
    def test_single_worker_and_memory_reservation(self):
        network = Mock()
        network.stat.return_value = SimpleNamespace(st_size=98511183)
        with patch.object(profile, "current_budget", return_value={"max_cpu_workers": 1, "memory_fraction": .5}), \
                patch.object(profile, "physical_memory", return_value=64 * 1024**3):
            result = profile.resource_check(network)
        self.assertEqual(result["active_search_workers"], 1)
        self.assertEqual(result["resident_engines"], 1)
        self.assertEqual(result["estimated_memory_bytes"], 256 * 1024**2 + 4 * 98511183)
        self.assertFalse(result["memory_estimate_is_hard_cap"])

    def test_unknown_or_insufficient_resources_reject(self):
        network = Mock()
        network.stat.return_value = SimpleNamespace(st_size=98511183)
        for workers, memory in ((0, 64 * 1024**3), (1, None), (1, 128 * 1024**2)):
            with self.subTest(workers=workers, memory=memory), \
                    patch.object(profile, "current_budget", return_value={"max_cpu_workers": workers, "memory_fraction": .5}), \
                    patch.object(profile, "physical_memory", return_value=memory):
                with self.assertRaises(ValueError):
                    profile.resource_check(network)


class FakeEngine:
    """Protocol-only process stand-in; never launches or searches an engine."""
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
                self.drift_path.write_text("mutated")
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
        self.directory = tempfile.TemporaryDirectory(prefix="reverse-profile-test-")
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.parent, self.candidate, self.network = [self.base / name for name in ("parent", "candidate", "network")]
        for path in (self.parent, self.candidate, self.network):
            path.write_text(path.name)
        self.output = self.base / "evidence.json"
        FakeEngine.created, FakeEngine.failure, FakeEngine.drift_path = [], None, None
        for patcher in (patch.object(profile, "Engine", FakeEngine),
                        patch.object(profile, "PARENT_SHA256", profile.digest(self.parent)),
                        patch.object(profile, "NETWORK_SHA256", profile.digest(self.network)),
                        patch.object(profile, "resource_check", return_value={"synthetic": True})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_profile(self):
        return profile.profile(self.parent, self.candidate, self.network, self.output, quiet_host=True)

    def test_quiet_host_is_required_before_engine_creation(self):
        with self.assertRaisesRegex(ValueError, "quiet-host"):
            profile.profile(self.parent, self.candidate, self.network, self.output)
        self.assertEqual(FakeEngine.created, [])
        self.assertFalse(self.output.exists())

    def test_all_commands_sessions_pins_and_gates_complete(self):
        result = self.run_profile()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["samples"]), 60)
        self.assertEqual(len(result["sessions"]), 36)
        self.assertEqual(list(result["summaries"]), list(profile.STAGES))
        self.assertEqual(sum(engine.commands.count("ucinewgame") for engine in FakeEngine.created), 36)
        self.assertEqual(sum(engine.commands.count("go depth 6") for engine in FakeEngine.created), 48)
        self.assertEqual(sum(engine.commands.count("go movetime 500") for engine in FakeEngine.created), 12)
        self.assertTrue(all(session["shutdown_eof_count"] == 1 for session in result["sessions"]))
        self.assertTrue(all(result["after_sha256"][name] == asset["sha256"] for name, asset in result["assets"].items()))
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")

    def test_existing_evidence_is_preserved_before_engine_creation(self):
        self.output.write_text("existing evidence")
        with self.assertRaises(FileExistsError):
            self.run_profile()
        self.assertEqual(self.output.read_text(), "existing evidence")
        self.assertEqual(FakeEngine.created, [])

    def test_temporary_evidence_is_preserved(self):
        temporary = self.output.with_suffix(".json.tmp")
        temporary.write_text("partial evidence")
        with self.assertRaisesRegex(ValueError, "Temporary output exists"):
            self.run_profile()
        self.assertEqual(temporary.read_text(), "partial evidence")
        self.assertEqual(FakeEngine.created, [])

    def test_parent_or_network_pin_rejects_before_engine_creation(self):
        for name in ("PARENT_SHA256", "NETWORK_SHA256"):
            with self.subTest(pin=name), patch.object(profile, name, "wrong digest"):
                with self.assertRaisesRegex(ValueError, "predeclared pins"):
                    self.run_profile()
        self.assertEqual(FakeEngine.created, [])
        self.assertFalse(self.output.exists())

    def test_total_deadline_stops_and_preserves_cleanup(self):
        with patch.object(profile, "TOTAL_TIMEOUT_SECONDS", 0):
            with self.assertRaisesRegex(TimeoutError, "total profile deadline expired"):
                self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["samples"], [])
        self.assertEqual(result["sessions"][0]["shutdown_eof_count"], 1)

    def test_final_cleanup_overrun_invalidates_complete_samples(self):
        clock = [0.]
        finish = profile.finish_session

        def now():
            clock[0] += .001
            return clock[0]

        def delayed_finish(engine, session):
            finish(engine, session)
            if len(FakeEngine.created) == 36:
                clock[0] += profile.TOTAL_TIMEOUT_SECONDS + 1

        with patch.object(profile.time, "monotonic", side_effect=now), \
                patch.object(profile, "finish_session", side_effect=delayed_finish):
            with self.assertRaisesRegex(TimeoutError, "deadline expired during final cleanup"):
                self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(len(result["samples"]), 60)
        self.assertTrue(all(sample["status"] == "complete" for sample in result["samples"]))
        self.assertGreater(result["search_and_cleanup_elapsed_seconds"], profile.TOTAL_TIMEOUT_SECONDS)
        self.assertGreaterEqual(result["total_elapsed_seconds"], result["search_and_cleanup_elapsed_seconds"])
        self.assertEqual(result["sessions"][-1]["shutdown_eof_count"], 1)

    def test_resource_change_stops_before_search(self):
        with patch.object(profile, "resource_check", side_effect=[{}, {}, ValueError("resource limit changed")]):
            with self.assertRaisesRegex(ValueError, "resource limit changed"):
                self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["samples"], [])
        self.assertEqual(result["sessions"][0]["shutdown_eof_count"], 1)

    def test_parent_mismatch_stops_before_on_searches(self):
        FakeEngine.failure = "parent_mismatch"
        with self.assertRaisesRegex(ValueError, "Default-off search differs"):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(len(result["samples"]), 24)
        self.assertFalse(any("setoption name Reverse Futility Pruning value true" in engine.commands
                             for engine in FakeEngine.created))

    def test_timeout_preserves_partial_output_and_shutdown(self):
        FakeEngine.failure = "timeout"
        with self.assertRaisesRegex(TimeoutError, "synthetic timeout"):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["samples"][0]["status"], "incomplete")
        self.assertEqual(result["samples"][0]["output"], [])
        self.assertEqual(result["sessions"][0]["shutdown_eof_count"], 1)

    def test_late_output_is_preserved_and_rejected(self):
        FakeEngine.failure = "late_output"
        with self.assertRaisesRegex(ValueError, "unexpected output"):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertIn("synthetic late error", result["sessions"][0]["shutdown_output"][0])

    def test_artifact_drift_invalidates_complete_matrix(self):
        FakeEngine.drift_path = self.candidate
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["artifact_drift"], ["candidate"])


if __name__ == "__main__":
    unittest.main()
