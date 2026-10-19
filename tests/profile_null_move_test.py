#!/usr/bin/env python3
"""Synthetic evidence checks for the fixed null-move screen; no engine runs.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import hashlib
from pathlib import Path
import queue
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_null_move as profile


def transcript(board):
    """A legal one-move PV at each depth, with complete deterministic totals."""
    move = next(iter(board.legal_moves)).uci()
    lines = [f"info depth {depth} seldepth {depth} score cp 10 nodes {depth * 10} "
             f"time {depth} nps 10000 hashfull {depth} tbhits 0 pv {move}"
             for depth in range(1, 7)]
    return lines + ["info nodes 60 time 6 nps 10000 hashfull 6 tbhits 0", f"bestmove {move}"]


def samples():
    """Build the entire declared two-stage matrix from independently legal PVs."""
    result = []
    for stage, roles in profile.STAGES.items():
        for index, position in enumerate(profile.POSITIONS):
            board = profile.board_for(position)
            validated = profile.validate_result(transcript(board), board)
            for temperature in profile.TEMPERATURES:
                for role in roles:
                    result.append({"stage": stage, "position_index": index,
                                   "temperature": temperature, "role": role,
                                   "status": "complete", "result": copy.deepcopy(validated)})
    return result


class EvidenceChecks(unittest.TestCase):
    def test_corpus_pin_and_legal_histories(self):
        self.assertEqual(len(profile.POSITIONS), 3)
        digest = hashlib.sha256(("\n".join(profile.POSITIONS) + "\n").encode()).hexdigest()
        self.assertEqual(digest, profile.POSITIONS_SHA256)
        for position in profile.POSITIONS:
            with self.subTest(position=position):
                board = profile.board_for(position)
                self.assertTrue(board.is_valid())
                self.assertFalse(board.is_game_over(claim_draw=True))

    def test_complete_iterations_and_final_totals(self):
        for position in profile.POSITIONS:
            with self.subTest(position=position):
                board = profile.board_for(position)
                result = profile.validate_result(transcript(board), board)
                self.assertEqual(result["reported_nodes"], 60)
                self.assertEqual(len(result["signature"]["iterations"]), 6)
                self.assertEqual(result["signature"]["nodes"], 60)
                self.assertEqual(result["signature"]["hashfull"], 6)

    def test_corrupt_search_records_are_rejected(self):
        for position in profile.POSITIONS:
            board = profile.board_for(position)
            lines = transcript(board)
            move = lines[-1].split()[1]
            corruptions = {
                "tablebase_hit": [line.replace("tbhits 0", "tbhits 1") for line in lines],
                "missing_tbhits": [line.replace(" tbhits 0", "") for line in lines],
                "lower_bound": [line.replace("score cp 10", "score cp 10 lowerbound") for line in lines],
                "upper_bound": [line.replace("score cp 10", "score cp 10 upperbound") for line in lines],
                "fictional_pass_in_pv": [line.replace("pv " + move, "pv 0000") for line in lines],
                "diagnostic": ["info string nullmove v1 enabled true"] + lines,
                "missing_depth": lines[1:],
                "duplicate_depth": lines[:1] + lines,
                "duplicate_bestmove": lines + lines[-1:],
                "unfinished_nodes": lines[:-2] + [
                    "info nodes 61 time 6 nps 10000 hashfull 6 tbhits 0", lines[-1]],
            }
            for name, corrupt in corruptions.items():
                with self.subTest(position=position, corruption=name):
                    with self.assertRaises(ValueError):
                        profile.validate_result(corrupt, board)

    def test_complete_matrix_and_totals(self):
        matrix = samples()
        self.assertEqual(len(matrix), 24)
        for stage, roles in profile.STAGES.items():
            with self.subTest(stage=stage):
                summary = profile.summarize(matrix, stage)
                self.assertEqual(len(summary["pairs"]), 6)
                self.assertTrue(all(pair["same_signature"] for pair in summary["pairs"]))
                self.assertEqual(summary["total_nodes_by_temperature"], {
                    temperature: {role: 180 for role in roles}
                    for temperature in profile.TEMPERATURES})

    def test_missing_duplicate_and_incomplete_cells_fail(self):
        matrix = samples()
        for stage in profile.STAGES:
            chosen = [sample for sample in matrix if sample["stage"] == stage]
            incomplete = copy.deepcopy(chosen)
            incomplete[0]["status"] = "incomplete"
            for name, corrupt in (("missing", chosen[:-1]), ("duplicate", chosen + chosen[:1]),
                                  ("incomplete", incomplete)):
                with self.subTest(stage=stage, corruption=name):
                    with self.assertRaises(ValueError):
                        profile.summarize(corrupt, stage)

    def test_unknown_matrix_cell_fails(self):
        matrix = samples()
        matrix[0]["temperature"] = "unplanned"
        with self.assertRaises(ValueError):
            profile.summarize(matrix, "parent_equivalence")

    def test_parent_mismatch_blocks_candidate_stage(self):
        for field in ("score", "nodes", "hashfull", "seldepth", "pv"):
            with self.subTest(field=field):
                matrix = samples()
                changed = next(sample for sample in matrix
                               if sample["stage"] == "parent_equivalence" and sample["role"] == "off")
                row = changed["result"]["signature"]["iterations"][0]
                if field == "score":
                    row[field]["value"] += 1
                elif field == "pv":
                    row[field] = ["e2e4"] if row[field] != ["e2e4"] else ["d2d4"]
                else:
                    row[field] += 1
                with self.assertRaises(ValueError):
                    profile.summarize(matrix, "parent_equivalence")

    def test_candidate_score_and_pv_changes_are_reported(self):
        matrix = samples()
        changed = next(sample for sample in matrix
                       if sample["stage"] == "null_work" and sample["role"] == "on")
        changed["result"]["iterations"][0]["score"]["value"] += 1
        changed["result"]["iterations"][1]["pv"] = ["e2e4"]
        summary = profile.summarize(matrix, "null_work")
        differences = summary["pairs"][0]["iteration_score_or_pv_changes"]
        self.assertEqual([difference["depth"] for difference in differences], [1, 2])
        self.assertEqual(differences[0]["left_score"]["value"], 10)
        self.assertEqual(differences[0]["right_score"]["value"], 11)
        self.assertEqual(differences[1]["right_pv"], ["e2e4"])

    def test_node_ratio_uses_reported_work(self):
        matrix = samples()
        changed = next(sample for sample in matrix
                       if sample["stage"] == "null_work" and sample["role"] == "on")
        changed["result"]["reported_nodes"] = 30
        summary = profile.summarize(matrix, "null_work")
        self.assertEqual(summary["pairs"][0]["node_ratio_right_over_left"], .5)
        self.assertEqual(summary["total_nodes_by_temperature"]["cold"]["on"], 150)


class ResourceChecks(unittest.TestCase):
    def setUp(self):
        self.network = Mock()
        self.network.stat.return_value = SimpleNamespace(st_size=98511183)
        self.policy = {"max_cpu_workers": 9, "memory_fraction": .5}

    def admitted(self, memory=64 * 1024**3):
        with patch.object(profile, "current_budget", return_value=self.policy), \
                patch.object(profile, "physical_memory", return_value=memory):
            return profile.resource_check(self.network)

    def test_reserves_campaign_and_serial_engine(self):
        result = self.admitted()
        self.assertEqual(result["active_search_workers"], 9)
        self.assertEqual(result["resident_engines"], 17)
        self.assertEqual(result["estimated_memory_bytes"],
                         9525941184 + 256 * 1024**2 + 4 * 98511183)
        self.assertTrue(result["includes_frozen_campaign"])
        self.assertFalse(result["memory_estimate_is_hard_cap"])

    def test_worker_budget_boundary(self):
        self.policy["max_cpu_workers"] = 8
        with self.assertRaises(ValueError):
            self.admitted()
        self.policy["max_cpu_workers"] = 9
        self.admitted()

    def test_unknown_memory_rejects(self):
        with self.assertRaises(ValueError):
            self.admitted(None)

    def test_memory_budget_rejects(self):
        self.policy["memory_fraction"] = .1
        with self.assertRaises(ValueError):
            self.admitted()


class ShutdownChecks(unittest.TestCase):
    """Late output lives in the reader queue, beyond the consumed transcript."""

    def fixture(self, pending, *, exit_code=0, reader_alive=False):
        engine = SimpleNamespace(lines=queue.Queue(), transcript=["readyok"],
                                 process=SimpleNamespace(returncode=exit_code),
                                 reader=Mock())
        engine.reader.is_alive.return_value = reader_alive
        for item in pending:
            engine.lines.put(item)
        return engine, {"output": engine.transcript}

    def test_clean_joined_exit_requires_final_eof(self):
        engine, session = self.fixture([None])
        profile.finish_session(engine, session)
        self.assertEqual(session["shutdown_output"], [])
        self.assertEqual(session["shutdown_eof_count"], 1)
        self.assertEqual(session["exit_code"], 0)
        self.assertNotIn("shutdown_error", session)
        self.assertTrue(engine.lines.empty())

    def test_shutdown_error_is_preserved_and_rejected(self):
        for line in ("info string error: late failure", "runtime error: bad access",
                     "unexpected debug output"):
            with self.subTest(line=line):
                engine, session = self.fixture([line, None])
                with self.assertRaisesRegex(ValueError, "unexpected output"):
                    profile.finish_session(engine, session)
                self.assertEqual(session["shutdown_output"], [line])
                self.assertEqual(session["output"], ["readyok", line])
                self.assertEqual(session["shutdown_eof_count"], 1)
                self.assertEqual(session["exit_code"], 0)
                self.assertIn("shutdown_error", session)

    def test_empty_lines_are_retained_without_becoming_diagnostics(self):
        engine, session = self.fixture(["", "  ", None])
        profile.finish_session(engine, session)
        self.assertEqual(session["shutdown_output"], ["", "  "])
        self.assertEqual(session["output"], ["readyok", "", "  "])

    def test_missing_duplicate_and_misordered_eof_fail(self):
        for pending in ([], [None, None], [None, ""], [None, "late"]):
            with self.subTest(pending=pending):
                engine, session = self.fixture(pending)
                with self.assertRaisesRegex(ValueError, "shutdown EOF"):
                    profile.finish_session(engine, session)
                self.assertEqual(session["shutdown_output"],
                                 [line for line in pending if line is not None])
                self.assertTrue(engine.lines.empty())

    def test_nonzero_or_unreaped_exit_fails(self):
        for exit_code in (1, -9, None):
            with self.subTest(exit_code=exit_code):
                engine, session = self.fixture([None], exit_code=exit_code)
                with self.assertRaisesRegex(ValueError, "exited unsuccessfully"):
                    profile.finish_session(engine, session)
                self.assertEqual(session["exit_code"], exit_code)

    def test_active_reader_cannot_prove_complete_shutdown_output(self):
        engine, session = self.fixture([None], reader_alive=True)
        with self.assertRaisesRegex(ValueError, "reader remained active"):
            profile.finish_session(engine, session)


if __name__ == "__main__":
    unittest.main()
