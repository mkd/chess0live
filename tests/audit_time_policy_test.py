#!/usr/bin/env python3
"""Exercise campaign evidence auditing with original synthetic chess records.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_time_policy as auditor
from match_statistics import summarize_pairs
import chess
import chess.pgn


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n")


def jsonl(path, values):
    path.write_text("".join(json.dumps(value)+"\n" for value in values))


def fingerprints(path):
    return {"path": str(path), "sha256": auditor.digest(path), "bytes": path.stat().st_size}


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Independently composed legal mate-in-one roots; no engines or game assets.
        cls.roots = []
        for king in range(64):
            for queen in range(64):
                if len({king, queen, chess.H8}) != 3:
                    continue
                board = chess.Board(None)
                for square, piece in ((king, chess.Piece(chess.KING, True)),
                                      (queen, chess.Piece(chess.QUEEN, True)),
                                      (chess.H8, chess.Piece(chess.KING, False))):
                    board.set_piece_at(square, piece)
                board.turn = chess.WHITE
                if not board.is_valid() or board.outcome(claim_draw=True):
                    continue
                for move in list(board.legal_moves):
                    child = board.copy(); child.push(move)
                    if child.is_checkmate():
                        cls.roots.append((board.fen(), move.uci()))
                        break
                if len(cls.roots) == 32:
                    return
        raise AssertionError("Could not compose 32 test roots")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-audit-")
        self.directory = Path(self.temporary.name)
        self.match = self.directory / "match"; self.match.mkdir()
        engine, network, openings = (self.directory / name for name in ("engine", "network", "openings.json"))
        engine.write_bytes(b"synthetic: never executed\n"); network.write_bytes(b"synthetic: never loaded\n")
        entries = [{"id": f"synthetic-{i}", "fen": fen, "moves": []} for i, (fen, _) in enumerate(self.roots)]
        write_json(openings, {"openings": entries})
        (self.match / "openings.json").write_bytes(openings.read_bytes())
        assets = {name: fingerprints(path) for name, path in (("engine", engine), ("network", network), ("openings", openings))}
        self.pin = patch.object(auditor, "PINNED_SHA256", {key: value["sha256"] for key, value in assets.items()})
        self.pin.start()
        sources = {}
        for name in ("tools/qualify_time_policy.py", "tools/audit_time_policy.py", "tools/match.py",
                     "tools/match_statistics.py", "tools/resources.py", "docs/PHASE_2D.md"):
            source = fingerprints(auditor.ROOT / name)
            sources[name] = {key: source[key] for key in ("sha256", "bytes")}
        (self.directory / "protocol.md").write_bytes((auditor.ROOT / "docs/PHASE_2D.md").read_bytes())
        config = {"pairs": 32, "seed": 20261014, "settings": dict(auditor.SETTINGS), "ponder": False,
                  "diagnostics": False, "engines": []}
        specs = {}
        for role, policy in (("candidate", "forecast"), ("opponent", "classic")):
            config["engines"].append({"role": role, "executable": str(engine), "network": str(network),
                                      "network_option": "EvalFile", "arguments": [],
                                      "source_revision": "synthetic", "extra_options": {"Time Policy": policy}})
            specs[role] = {"executable": str(engine), "network": str(network), "network_option": "EvalFile",
                           "arguments": [], "experiment_options": {"Time Policy": policy},
                           "artifacts": [assets["engine"], assets["network"]]}
        self.launch = {"schema_version": 1, "protocol_id": auditor.PROTOCOL_ID, "status": "finished",
                       "chess_version": "1.11.2", "configuration": config,
                       "started_utc": "2026-10-15T10:00:00.001+00:00",
                       "finished_utc": "2026-10-15T10:30:00+00:00",
                       "launch_policy": {"timezone": "Europe/Helsinki", "local_time": "2026-10-15T13:00:00+03:00",
                                         "nighttime": False, "allow_daytime": True,
                                         "cutoff_local": "2026-10-16T07:00:00+03:00",
                                         "cutoff_utc": "2026-10-16T04:00:00+00:00", "remaining_seconds": 64800.},
                       "preflight": {"opening_count": 32, "distinct_roots": 32},
                       "configuration_sha256": auditor.canonical_digest(config), "assets": assets, "sources": sources,
                       "match_directory": "match", "protocol_document": {"source": "docs/PHASE_2D.md",
                       "frozen_copy": "protocol.md", "sha256": sources["docs/PHASE_2D.md"]["sha256"]}}
        self.launch["integrity_after"] = {"configuration_sha256": self.launch["configuration_sha256"],
                                          "assets": copy.deepcopy(assets), "sources": copy.deepcopy(sources), "unchanged": True}
        self.plan = []
        shuffled = list(entries); generator = random.Random(20261014); generator.shuffle(shuffled)
        for index, entry in enumerate(shuffled):
            definition = {"fen": entry["fen"], "moves": []}
            key = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
            self.plan.append({"pair_id": f"p{index+1:06d}", "opening_id": entry["id"], "opening_key": key,
                              "starting_fen": entry["fen"], "moves": [],
                              "first_candidate_color": generator.choice(("white", "black"))})
        self.run = {"schema_version": 1, "settings": dict(auditor.SETTINGS), "planned_pairs": 32, "seed": 20261014,
                    "chess_version": "1.11.2", "status": "finished", "plan": self.plan, "engines": specs,
                    "opening_suite": {"sha256": assets["openings"]["sha256"]},
                    "runner_sources": [{"path": key, "sha256": sources[key]["sha256"]} for key in
                                       ("tools/match.py", "tools/match_statistics.py", "tools/resources.py")]}
        self.records = []
        for pair in self.plan:
            first = pair["first_candidate_color"]
            for leg, color in enumerate((first, "black" if first == "white" else "white"), 1):
                self.records.append(self.make_game(pair, leg, color))
        self.save()

    def tearDown(self):
        self.pin.stop(); self.temporary.cleanup()

    def make_game(self, pair, leg, color, late=False, bestmove=None):
        game_id = f"{pair['pair_id']}-{leg}"
        board = chess.Board(pair["starting_fen"])
        game = chess.pgn.Game(); game.setup(board)
        node = game
        for token in pair["moves"]:
            board.push_uci(token)
            node = node.add_variation(chess.Move.from_uci(token))
        move = bestmove or next(move for fen, move in self.roots if fen == board.fen())
        moving_color = "white" if board.turn else "black"
        role = "candidate" if color == moving_color else "opponent"
        elapsed = 61. if late else .25
        after = -1. if late else 60.-elapsed+.6
        event = {"ply": board.ply()+1, "engine": role, "color": moving_color, "clock_before": 60., "elapsed_seconds": elapsed,
                 "move": move, "clock_after": after, "played": not late}
        if not late:
            board.push_uci(move); node = node.add_variation(chess.Move.from_uci(move)); node.set_clock(after)
        result, termination = ("1/2-1/2", "time_forfeit") if late else ("1-0" if moving_color == "white" else "0-1", "checkmate")
        game.headers.update(Result=result, Termination=termination)
        (self.match / f"{game_id}.pgn").write_text(str(game)+"\n\n")
        log = []; tick = 0
        def emit(direction, line, advance=1):
            nonlocal tick
            tick += advance
            log.append({"engine": role, "direction": direction, "line": line, "monotonic_ns": tick})
        expected = {"Hash": "64", "Threads": "1", "Ponder": "false", "Search Diagnostics": "false",
                    "Move Overhead": "20", "EvalFile": self.launch["assets"]["network"]["path"],
                    "Time Policy": "forecast" if role == "candidate" else "classic"}
        for key, value in expected.items(): emit("to_engine", f"setoption name {key} value {value}")
        emit("to_engine", "ucinewgame"); emit("to_engine", "isready")
        emit("from_engine", "readyok", 10_000_000_000)  # Deliberately long readiness is outside the clock.
        history = " moves " + " ".join(pair["moves"]) if pair["moves"] else ""
        emit("to_engine", "position fen "+pair["starting_fen"]+history)
        emit("to_engine", "go wtime 60000 btime 60000 winc 600 binc 600")
        emit("from_engine", "bestmove "+move, int(elapsed*1e9))
        jsonl(self.match / f"{game_id}.protocol.jsonl", log)
        record = {"game_id": game_id, "pair_id": pair["pair_id"], "opening_id": pair["opening_id"],
                  "opening_key": pair["opening_key"], "candidate_color": color, "status": "complete",
                  "result": result, "termination": termination, "opening_plies": len(pair["moves"]), "played_plies": int(not late),
                  "moves": [event], "final_fen": board.fen(), "clocks": dict({"white": 60., "black": 60.}, **{moving_color: after}),
                  "candidate_score": .5 if late else float(color == moving_color),
                  "pgn": f"{game_id}.pgn", "protocol_log": f"{game_id}.protocol.jsonl"}
        if late: record["clock_loser"] = role
        return record

    def save(self):
        nested = [{"pair_id": p["pair_id"], "opening_key": p["opening_key"],
                   "games": [g for g in self.records if g["pair_id"] == p["pair_id"]]} for p in self.plan]
        summary = summarize_pairs(nested, experiment_complete=self.run["status"] == "finished")
        summary["smoke"] = False
        self.launch["match_summary"] = summary
        write_json(self.directory / "launch.json", self.launch)
        write_json(self.match / "run.json", self.run)
        write_json(self.match / "summary.json", summary)
        jsonl(self.match / "games.jsonl", self.records)

    def assert_invalid(self):
        result = auditor.audit(self.directory)
        self.assertEqual(result["decision"], "invalid_or_incomplete", result)
        self.assertTrue(result["input_sha256"])
        return result

    def test_complete_campaign_replays_all_games_and_excludes_readiness_time(self):
        result = auditor.audit(self.directory)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(len(result["games"]), 64)
        self.assertEqual(result["statistics"]["wdl"], {"wins": 32, "draws": 0, "losses": 32})
        self.assertFalse(result["default_change"])

    def test_candidate_flagfall_is_scored_without_pushing_or_increment(self):
        index = next(i for i, g in enumerate(self.records) if g["candidate_color"] == "white")
        old = self.records[index]; pair = next(p for p in self.plan if p["pair_id"] == old["pair_id"])
        self.records[index] = self.make_game(pair, int(old["game_id"].rsplit("-", 1)[1]), "white", late=True)
        self.save(); result = auditor.audit(self.directory)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["decision"], "operational_regression")
        self.assertEqual(result["candidate_time_forfeits"], 1)
        self.assertEqual(result["statistics"]["included_games"], 64)
        self.assertEqual(result["statistics"]["wdl"]["draws"], 1)  # Opponent has only a king.

    def test_partial_campaign_retains_observed_results_without_qualification(self):
        self.records = self.records[:-1]; self.run["status"] = self.launch["status"] = "interrupted"
        self.save(); result = self.assert_invalid()
        self.assertEqual(result["statistics"]["included_pairs"], 31)
        self.assertIsNone(result["statistics"]["score_interval"])

    def test_charged_clock_and_transmitted_clock_tampering_are_detected(self):
        original = copy.deepcopy(self.records)
        self.records[0]["moves"][0]["elapsed_seconds"] += .01
        self.save(); self.assert_invalid()
        self.records = original; self.save()
        path = self.match / self.records[0]["protocol_log"]
        path.write_text(path.read_text().replace("wtime 60000", "wtime 59000"))
        self.assert_invalid()

    def test_actual_option_and_pgn_tampering_are_detected(self):
        path = self.match / self.records[0]["protocol_log"]
        before = path.read_text(); path.write_text(before.replace("Hash value 64", "Hash value 128"))
        self.assert_invalid(); path.write_text(before)
        path = self.match / self.records[0]["pgn"]
        path.write_text(path.read_text().replace('[Result "1-0"]', '[Result "0-1"]'))
        self.assert_invalid()

    def test_asset_and_final_source_drift_are_detected(self):
        self.launch["integrity_after"]["sources"]["tools/match.py"]["sha256"] = "0"*64
        self.save(); self.assert_invalid()
        self.launch["integrity_after"]["sources"] = copy.deepcopy(self.launch["sources"])
        self.save(); Path(self.launch["assets"]["network"]["path"]).write_bytes(b"changed")
        self.assert_invalid()

    def test_later_live_doc_edit_does_not_change_frozen_protocol_evidence(self):
        # Model later documentation edits by freezing an additional old source digest.
        value = {"sha256": "a"*64, "bytes": 1}
        self.launch["sources"]["docs/README-later.md"] = value
        self.launch["integrity_after"]["sources"]["docs/README-later.md"] = value
        self.save(); result = auditor.audit(self.directory)
        self.assertEqual(result["errors"], [])
        self.assertIn("docs/README-later.md", result["live_source_differences"])

    def test_summary_tampering_and_duplicate_game_ids_are_detected(self):
        path = self.match / "summary.json"; summary = json.loads(path.read_text())
        summary["wdl"]["wins"] += 1; write_json(path, summary)
        self.assert_invalid(); self.save()
        self.records[-1]["game_id"] = self.records[0]["game_id"]
        self.save(); self.assert_invalid()

    def test_game_identifier_must_belong_to_its_declared_pair(self):
        self.records[0]["game_id"], self.records[2]["game_id"] = self.records[2]["game_id"], self.records[0]["game_id"]
        self.save()
        result = self.assert_invalid()
        self.assertTrue(any("belongs to another pair" in error for error in result["errors"]))

    def test_unexpected_stderr_is_explicitly_rejected(self):
        path = self.match / self.records[0]["protocol_log"]
        events = [json.loads(line) for line in path.read_text().splitlines()]
        events.append(dict(events[-1], direction="stderr", line="unexpected engine diagnostic"))
        jsonl(path, events)
        result = self.assert_invalid()
        self.assertTrue(any("Unexpected stderr" in error for error in result["errors"]))

    def test_daytime_exception_and_next_morning_cutoff_are_required(self):
        self.launch["launch_policy"]["allow_daytime"] = False
        self.save(); self.assert_invalid()
        self.launch["launch_policy"]["allow_daytime"] = True
        self.launch["launch_policy"]["cutoff_local"] = "2026-10-16T08:00:00+03:00"
        self.save(); self.assert_invalid()

    def test_full_opening_history_and_black_to_move_are_preserved(self):
        pair = dict(self.plan[0], starting_fen=chess.STARTING_FEN, moves=["f2f3", "e7e5", "g2g4"])
        record = self.make_game(pair, 1, "black", bestmove="d8h4")
        checker = auditor.Audit(self.directory)
        checker.assets = self.launch["assets"]
        result = checker.game(record, pair)
        self.assertEqual(result["legal_plies"], 4)
        self.assertEqual(result["result"], "0-1")
        self.assertEqual(record["clocks"], {"white": 60., "black": 60.35})
        path = self.match / record["protocol_log"]
        path.write_text(path.read_text().replace(" moves f2f3 e7e5 g2g4", ""))
        with self.assertRaisesRegex(ValueError, "history"):
            checker.game(record, pair)

    def test_cli_refuses_to_overwrite_evidence(self):
        output = self.directory / "audit.json"; output.write_text("preserve")
        with patch.object(sys, "argv", ["audit", "--campaign", str(self.directory), "--output", str(output)]):
            with self.assertRaises(SystemExit): auditor.main()
        self.assertEqual(output.read_text(), "preserve")


class DecisionTests(unittest.TestCase):
    def test_exact_predeclared_thresholds(self):
        for points, expected in ((47., "inconclusive"), (47.5, "eligible_for_confirmation_review"),
                                 (16.5, "negative_evidence"), (17., "inconclusive")):
            with self.subTest(points=points):
                radius = (math_log_40() / 64)**.5
                score = points/64
                computed = {"inference_eligible": True,
                            "score_interval": {"lower": max(0, score-radius), "upper": min(1, score+radius)}}
                self.assertEqual(auditor.classify(computed, True, [], 0), expected)
                self.assertEqual(auditor.classify(computed, True, [], 1), "operational_regression")
                self.assertEqual(auditor.classify(computed, False, [], 0), "invalid_or_incomplete")
                self.assertEqual(auditor.classify(computed, True, ["corrupt"], 0), "invalid_or_incomplete")


def math_log_40():
    import math
    return math.log(40)


if __name__ == "__main__":
    unittest.main()
