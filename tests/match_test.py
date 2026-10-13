#!/usr/bin/env python3
"""Referee, clock, pairing, and persistence checks using tiny fake UCI processes.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import match
import chess
import chess.pgn


# This deliberately tiny test double chooses legal moves rather than evaluating
# chess. Modes exercise the process/protocol boundary, not just mocked returns.
FAKE_ENGINE = r'''
import os, sys, time
import chess
mode = sys.argv[1]
board = chess.Board()
def output(text): print(text, flush=True)
for line in sys.stdin:
    tokens = line.split()
    if not tokens: continue
    command = tokens[0]
    if command == "uci":
        output("id name fake-" + mode)
        output("option name Hash type spin default 8 min 1 max 16384")
        if mode != "missing_threads":
            output("option name Threads type spin default 2 min 1 max 1024")
        output("option name EvalFile type string default none")
        output("option name Move Overhead type spin default 0 min 0 max 5000")
        output("option name Ponder type check default false")
        output("uciok")
    elif command == "isready":
        if mode == "slow_ready": time.sleep(0.12)
        output("readyok")
    elif command == "position":
        if tokens[1] == "startpos": board, index = chess.Board(), 2
        else: board, index = chess.Board(" ".join(tokens[2:8])), 8
        if index < len(tokens):
            for move in tokens[index+1:]: board.push_uci(move)
    elif command == "go":
        if mode == "crash": os._exit(7)
        if mode == "hang":
            while True: time.sleep(1)
        if mode == "illegal": output("bestmove a1a8"); continue
        if mode == "late": time.sleep(0.08)
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        chosen = moves[0]
        if mode == "mate":
            for move in moves:
                board.push(move)
                mating = board.is_checkmate()
                board.pop()
                if mating: chosen = move; break
        output("bestmove " + chosen.uci())
    elif command == "quit": break
'''


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="chess0live-match-test-")
        self.root = Path(self.directory.name)
        self.fake = self.root / "fake engine.py"
        self.fake.write_text(FAKE_ENGINE, encoding="utf-8")
        self.network = self.root / "fake network.nnue"
        self.network.write_bytes(b"fake network: protocol tests do not load neural weights\n")
        self.suite = self.root / "openings.json"
        self.write_suite([{"id": "test-start", "moves": []}])
        self.settings = match.Settings(initial=1.0, increment=0.0, hash_mb=1,
                                       max_plies=1, startup_timeout=2.0,
                                       protocol_timeout=0.25, move_overhead_ms=0, smoke=True)
        self.sequence = 0
        self.budget = {"percent": 50, "max_cpu_workers": 8, "memory_fraction": 0.5}
        self.policy_patch = patch.object(match, "current_budget", return_value=self.budget.copy())
        self.policy_patch.start()
        logging.getLogger("chess.engine").setLevel(logging.CRITICAL)

    def tearDown(self):
        self.policy_patch.stop()
        self.directory.cleanup()

    def write_suite(self, openings):
        self.suite.write_text(json.dumps({"description": "Original protocol-test fixtures", "openings": openings}), encoding="utf-8")

    def specs(self, candidate="normal", opponent="normal"):
        return [match.EngineSpec(role, Path(sys.executable).resolve(), self.network,
                                 arguments=(str(self.fake), mode), source_revision="unverified-test-label")
                for role, mode in (("candidate", candidate), ("opponent", opponent))]

    def play(self, candidate="normal", opponent="normal", settings=None, opening=None):
        self.sequence += 1
        output = self.root / f"game-{self.sequence}"
        output.mkdir()
        if opening is None:
            opening = match.read_openings(self.suite)[1][0]
        records = []
        record = asyncio.run(match.play_game(self.specs(candidate, opponent), settings or self.settings,
                                             opening, "p1", "p1-1", "white", self.budget,
                                             output, records.append))
        self.assertEqual(records, [record])
        self.assertTrue((output / record["pgn"]).is_file())
        transcript = [json.loads(line) for line in (output / record["protocol_log"]).read_text().splitlines()]
        return record, transcript, output

    def test_openings_reject_null_illegal_duplicate_and_terminal(self):
        cases = [
            [{"id": "null", "moves": ["0000"]}],
            [{"id": "illegal", "moves": ["e2e5"]}],
            [{"id": "a", "moves": []}, {"id": "b", "moves": []}],
            [{"id": "drawn", "fen": "7k/8/5K2/8/8/8/8/8 w - - 0 1"}],
            [{"id": "malformed", "fen": None}],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                self.write_suite(entries)
                with self.assertRaises(ValueError): match.read_openings(self.suite)

    def test_seeded_plan_has_no_recycling(self):
        self.write_suite([{"id": f"opening-{index}", "moves": [move]}
                          for index, move in enumerate(("a2a3", "b2b3", "c2c3", "d2d3"))])
        openings = match.read_openings(self.suite)[1]
        first = match.plan_pairs(openings, 4, 271)
        second = match.plan_pairs(openings, 4, 271)
        self.assertEqual([(p["opening"].key, p["first_candidate_color"]) for p in first],
                         [(p["opening"].key, p["first_candidate_color"]) for p in second])
        self.assertEqual(len({pair["opening"].key for pair in first}), 4)
        with self.assertRaises(ValueError): match.plan_pairs(openings, 5, 0)

    def test_nonfinite_and_excessive_limits_rejected(self):
        for field in ("initial", "increment", "startup_timeout", "protocol_timeout"):
            for value in (float("nan"), float("inf"), -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.settings, **{field: value}).validate()
        for field, value in (("threads", 0), ("threads", 1025), ("hash_mb", 16385),
                             ("max_plies", 10001), ("move_overhead_ms", 5001)):
            with self.assertRaises(ValueError): replace(self.settings, **{field: value}).validate()

    def test_full_opening_history_and_increment_survive(self):
        moves = ["g1f3", "g8f6", "f3g1", "f6g8"]
        self.write_suite([{"id": "repetition-history", "moves": moves}])
        record, transcript, output = self.play(settings=replace(self.settings, increment=0.5))
        self.assertEqual(record["status"], "truncated")
        self.assertEqual(record["result"], "*")
        self.assertIsNone(record["candidate_score"])
        event = record["moves"][0]
        self.assertAlmostEqual(event["clock_after"], 1.5 - event["elapsed_seconds"])
        self.assertTrue(event["played"])
        commands = [line["line"] for line in transcript if line["direction"] == "to_engine"]
        self.assertIn("position startpos moves " + " ".join(moves), commands)
        self.assertFalse(any(line.startswith("go ponder") for line in commands))
        self.assertIn("setoption name Hash value 1", commands)
        self.assertIn("setoption name Threads value 1", commands)
        game = chess.pgn.read_game(io.StringIO((output / record["pgn"]).read_text()))
        self.assertEqual([move.uci() for move in game.mainline_moves()][:4], moves)

    def test_late_legal_move_loses_without_increment_or_board_change(self):
        settings = replace(self.settings, initial=0.01, increment=1.0)
        record, _, _ = self.play(candidate="late", settings=settings)
        self.assertEqual(record["status"], "complete")
        self.assertEqual(record["termination"], "time_forfeit")
        self.assertEqual(record["result"], "0-1")
        self.assertEqual(record["candidate_score"], 0.0)
        self.assertEqual(record["played_plies"], 0)
        self.assertEqual(record["final_fen"], chess.STARTING_FEN)
        self.assertFalse(record["moves"][0]["played"])
        self.assertLess(record["clocks"]["white"], 0)

    def test_flagfall_without_opponent_mating_material_draws(self):
        board = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        self.assertEqual(match.clock_outcome(board, chess.WHITE), "1/2-1/2")
        self.assertEqual(match.clock_outcome(board, chess.BLACK), "1-0")

    def test_readiness_is_outside_chess_clock(self):
        record, transcript, _ = self.play(candidate="slow_ready", settings=replace(self.settings, initial=0.05, protocol_timeout=0.02))
        self.assertEqual(record["status"], "truncated")
        self.assertTrue(record["moves"][0]["played"])
        lines = [line for line in transcript if line["engine"] == "candidate"]
        go = next(line for line in lines if line["line"].startswith("go "))
        first_ready = next(line for line in lines if line["line"] == "isready")
        self.assertGreater((go["monotonic_ns"] - first_ready["monotonic_ns"]) / 1e9, 0.2)
        self.assertLess(record["moves"][0]["elapsed_seconds"], 0.05)

    def test_protocol_failure_is_not_a_chess_loss(self):
        for mode in ("illegal", "crash"):
            with self.subTest(mode=mode):
                record, _, _ = self.play(candidate=mode)
                self.assertEqual(record["status"], "protocol_failure")
                self.assertEqual(record["result"], "*")
                self.assertIsNone(record["candidate_score"])
                self.assertEqual(record["played_plies"], 0)

    def test_no_reply_is_protocol_timeout(self):
        record, _, _ = self.play(candidate="hang", settings=replace(self.settings, initial=0.01, protocol_timeout=0.02))
        self.assertEqual(record["status"], "protocol_timeout")
        self.assertEqual(record["result"], "*")

    def test_missing_required_option_is_setup_failure(self):
        record, _, _ = self.play(candidate="missing_threads")
        self.assertEqual(record["status"], "setup_failure")
        self.assertIn("Threads", record["error"])

    def test_full_pair_persists_hashes_pgn_json_and_swaps_colors(self):
        self.write_suite([{"id": "mate-fixture", "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"}])
        output = self.root / "paired"
        result = asyncio.run(match.run_match(self.specs("mate", "mate"), self.settings, self.suite, output, 1, 7))
        records = [json.loads(line) for line in (output / "games.jsonl").read_text().splitlines()]
        self.assertEqual({record["candidate_color"] for record in records}, {"white", "black"})
        self.assertEqual([record["termination"] for record in records], ["checkmate", "checkmate"])
        self.assertEqual(result["included_pairs"], 1)
        self.assertEqual(result["wdl"], {"wins": 1, "draws": 0, "losses": 1})
        self.assertFalse(result["inference_eligible"])
        self.assertIn("smoke_run_not_a_strength_experiment", result["uncertainty"]["withheld_reasons"])
        manifest = json.loads((output / "run.json").read_text())
        self.assertEqual(manifest["status"], "finished")
        self.assertEqual(len(manifest["runner_sources"]), 3)
        self.assertEqual(manifest["plan"][0]["starting_fen"], "7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        self.assertEqual((output / "openings.json").read_bytes(), self.suite.read_bytes())
        for engine in manifest["engines"].values():
            self.assertFalse(engine["source_revision"]["verified_against_binary"])
            self.assertEqual(len(engine["artifacts"]), 3)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in engine["artifacts"]))
        with self.assertRaises(ValueError):
            asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 7))

    def test_budget_is_reread_between_games(self):
        output = self.root / "budget-change"
        allowed = dict(self.budget)
        denied = dict(self.budget, max_cpu_workers=1)
        settings = replace(self.settings, threads=2)
        with patch.object(match, "current_budget", side_effect=[allowed, allowed, denied]) as calls:
            with self.assertRaises(ValueError):
                asyncio.run(match.run_match(self.specs(), settings, self.suite, output, 1, 0))
        self.assertEqual(calls.call_count, 3)
        self.assertEqual(len((output / "games.jsonl").read_text().splitlines()), 1)
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "interrupted")

    def test_last_game_asset_change_invalidates_finished_experiment(self):
        output = self.root / "asset-change"
        original_play = match.play_game
        completed = 0
        async def change_after_second(*args, **kwargs):
            nonlocal completed
            result = await original_play(*args, **kwargs)
            completed += 1
            if completed == 2:
                self.network.write_bytes(b"changed while final game was running")
            return result
        with patch.object(match, "play_game", side_effect=change_after_second):
            with self.assertRaises(ValueError):
                asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
        self.assertEqual(completed, 2)
        summary = json.loads((output / "summary.json").read_text())
        self.assertFalse(summary["experiment_complete"])
        self.assertFalse(summary["inference_eligible"])


if __name__ == "__main__":
    unittest.main()
