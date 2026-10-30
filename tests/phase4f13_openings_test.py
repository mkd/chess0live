#!/usr/bin/env python3
"""Bounded, engine-free checks of fresh NNUE History qualification inputs.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
Full historical PGN replay is a separate --check --verify-sources operation.
"""
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import generate_phase4f13_openings as generator
import match


def key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


class NNUEOpeningsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads((ROOT / "tests/data" / generator.METADATA).read_bytes())
        cls.files = generator.assets(cls.metadata, ROOT)
        cls.documents = [json.loads(cls.files[name]) for name in generator.SUITE_NAMES]
        cls.catalog = json.loads(cls.files[Path(generator.EXCLUSION_MANIFEST).name])

    def test_assets_and_digest_manifests_reproduce(self):
        generator.original.check_assets(self.files, ROOT / "tests/data")
        self.assertEqual(generator.assets(self.metadata, ROOT), self.files)
        for record in self.metadata["shards"] + [self.metadata["exclusion_manifest"]]:
            self.assertEqual(generator.original.digest(self.files[Path(record["path"]).name]), record["sha256"])

    def test_all_histories_legal_unique_and_balanced(self):
        roots, identifiers, totals = set(), set(), Counter()
        for shard, document in enumerate(self.documents, 1):
            self.assertEqual(document["seed"], generator.SEEDS[shard - 1])
            self.assertEqual(document["domain"], generator.DOMAIN)
            self.assertEqual(len(document["openings"]), 256)
            turns, families = Counter(), Counter()
            for entry in document["openings"]:
                self.assertNotIn("fen", entry)
                board = chess.Board()
                for text in entry["moves"]:
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                    self.assertTrue(board.is_valid())
                    self.assertIsNone(board.outcome(claim_draw=True))
                self.assertEqual(len(board.move_stack), 19 if entry["variant"] % 4 < 2 else 20)
                self.assertEqual(entry["final_fen"], board.fen())
                self.assertEqual(entry["canonical_root"], key(board))
                self.assertEqual(entry["shard"], shard)
                self.assertNotIn(key(board), roots)
                self.assertNotIn(entry["id"], identifiers)
                roots.add(key(board)); identifiers.add(entry["id"])
                turns[board.turn] += 1; families[entry["moves"][0]] += 1
                totals[len(board.move_stack)] += 1
            self.assertEqual(turns, {chess.WHITE: 128, chess.BLACK: 128})
            self.assertEqual(families, {"e2e4": 96, "d2d4": 96, "c2c4": 32, "g1f3": 32})
        self.assertEqual(len(roots), 1024)
        self.assertEqual(totals, {19: 512, 20: 512})

    def test_stems_and_rejected_attempts_preserved(self):
        for index, stem in enumerate(generator.original.parse_stems()):
            rows = [row for row in self.metadata["accepted"] if row["stem_id"] == stem["id"]]
            self.assertEqual([row["variant"] for row in rows], list(range(16)))
            for row in rows:
                self.assertEqual(row["moves"][:16], stem["moves"])
                self.assertEqual(row["shard"], (index % 2) * 2 + row["variant"] % 2 + 1)
                rejected = [item["attempt"] for item in self.metadata["rejections"]
                            if (item["stem_id"], item["variant"]) == (stem["id"], row["variant"])]
                self.assertEqual(rejected, list(range(row["accepted_attempt"])))
        self.assertIn("stems have been used before", self.metadata["limitations"])

    def test_disjoint_catalog_and_prior_suites(self):
        excluded = {row["root_key"] for row in self.catalog["roots"]}
        accepted = {row["canonical_root"] for row in self.metadata["accepted"]}
        self.assertEqual(len(excluded), self.catalog["unique_roots"])
        self.assertFalse(accepted & excluded)
        # Future suites cannot retroactively alter this frozen exposure snapshot.
        for record in self.metadata["sources"]:
            if record["kind"] == "opening-suite":
                self.assertLessEqual(set(generator.original.source_roots(ROOT / record["path"], "opening-suite")), excluded)
        for relative, kind in (("tests/data/countermove-profile.json", "json-positions"),
                               ("tests/data/phase4f3-puzzles.json", "json-positions"),
                               ("tests/data/performance-gamephases.json", "opening-suite"),
                               ("tests/data/openings-development.json", "opening-suite"),
                               ("tools/batch_positions.py", "valid-fen-literals"),
                               ("tools/bench.py", "benchmark-constant")):
            self.assertLessEqual(set(generator.original.source_roots(ROOT / relative, kind)), excluded)

    def test_recorded_exposure_scope_and_policy(self):
        self.assertEqual(self.metadata["seeds"], list(range(202610304131, 202610304135)))
        self.assertEqual(self.metadata["domain"], "phase4f13-nnue-2048-v1")
        records = {(row["path"], row["kind"]): row for row in self.metadata["sources"]}
        self.assertIn(("tests/data/countermove-profile.json", "json-positions"), records)
        self.assertIn(("tools/batch_positions.py", "valid-fen-literals"), records)
        self.assertIn(("tests/data/phase4f3-puzzles.json", "json-positions"), records)
        self.assertIn(("tests/data/performance-gamephases.json", "opening-suite"), records)
        self.assertIn(("tests/data/openings-development.json", "opening-suite"), records)
        for shard in range(1, 5):
            self.assertIn((f"tests/data/phase4f3-{shard:02}.json", "opening-suite"), records)
            self.assertIn((f"tests/data/phase4f7-match-{shard:02}.json", "opening-suite"), records)
        self.assertFalse(any(Path(path).name in generator.PREPARATION_NAMES for path, _ in records))
        for shard in range(1, 5):
            self.assertIn((f"results/lmr-20261022/campaign/shard-{shard}/match", "saved-pgn-directory"), records)
        prior_match_games = 0
        for shard in range(1, 5):
            saved = records[(f"results/phase4f7-match-20261027/shard-{shard}/match", "saved-pgn-directory")]
            self.assertEqual(saved["replay_counts"]["games"], 128)
            self.assertEqual(saved["replay_counts"]["legal_prefix_games"], 0)
            self.assertEqual(saved["replay_counts"]["invalid_initial_games"], 0)
            prior_match_games += saved["replay_counts"]["games"]
        self.assertEqual(prior_match_games, 512)
        for shard in range(1, 5):
            saved = records[(f"results/phase4f10-match-20261028/shard-{shard}/match", "saved-pgn-directory")]
            self.assertEqual(saved["replay_counts"]["games"], 128)
            self.assertEqual(saved["replay_counts"]["legal_prefix_games"], 0)
            self.assertEqual(saved["replay_counts"]["invalid_initial_games"], 0)
        self.assertFalse(any(generator.PREFIX in path for path, _ in records))
        self.assertEqual(self.metadata["saved_game_overlap_with_accepted"], [])

    def test_match_loader_preserves_full_history(self):
        for name in generator.SUITE_NAMES:
            _, roots = match.read_openings(name, self.files[name])
            self.assertEqual(len(roots), 256)
            self.assertTrue(all(len(root.board.move_stack) in (19, 20) for root in roots))

    def public_checkout(self, directory):
        for relative in (generator.GENERATOR, generator.HELPER,
                         generator.original.GENERATOR_PATH, generator.original.EXCLUSION_MANIFEST):
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def test_public_replay_without_private_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.public_checkout(root)
            self.assertEqual(generator.assets(self.metadata, root), self.files)

    def test_helper_or_generator_drift_rejected(self):
        for relative in (generator.GENERATOR, generator.HELPER, generator.original.GENERATOR_PATH):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.public_checkout(root)
                source = root / relative; source.write_bytes(source.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    generator.assets(self.metadata, root)

    def test_mutated_policy_or_replay_rejected(self):
        for field in ("seeds", "domain", "accepted", "rejections", "additional_excluded_roots"):
            forged = copy.deepcopy(self.metadata)
            if field == "seeds": forged[field] = [1, 2, 3, 4]
            elif field == "domain": forged[field] = "other"
            elif field == "accepted": forged[field][0]["accepted_attempt"] += 1
            elif field == "rejections": forged[field].append({})
            else: forged[field].append(forged[field][0])
            with self.subTest(field=field), self.assertRaises(ValueError):
                generator.assets(forged, ROOT)

    def test_wrong_referee_rejected(self):
        with patch.object(chess, "__version__", "0.0"), self.assertRaisesRegex(ValueError, "Requires chess"):
            generator.assets(self.metadata, ROOT)

    def test_changed_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            generator.original.write_assets(self.files, directory)
            target = Path(directory) / generator.SUITE_NAMES[0]; target.write_bytes(b"preserve me")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                generator.original.write_assets(self.files, directory)
            self.assertEqual(target.read_bytes(), b"preserve me")


class GenerationPolicyTests(unittest.TestCase):
    def test_high_sha_word_rejected_before_modulo(self):
        hashes = [SimpleNamespace(digest=lambda value=value: value.to_bytes(32, "big"))
                  for value in ((1 << 256) - 1, 4)]
        with patch.object(generator.hashlib, "sha256", side_effect=hashes):
            self.assertEqual(generator.choose_index(3, generator.SEEDS[0], "fixture", 0, 0, 0), 1)
        with self.assertRaises(ValueError):
            generator.choose_index(0, generator.SEEDS[0], "fixture", 0, 0, 0)

    def test_terminal_intermediate_tail_stops(self):
        board = chess.Board()
        for move in ("f2f3", "e7e5", "g2g4"): board.push_uci(move)
        index = sorted(move.uci() for move in board.legal_moves).index("d8h4")
        with patch.object(generator, "choose_index", return_value=index) as choose:
            result, tail, terminal = generator.continuation({"board": board, "id": "fixture"}, 0, 0, generator.SEEDS[0])
        self.assertTrue(terminal); self.assertTrue(result.is_checkmate())
        self.assertEqual(tail, ["d8h4"]); self.assertEqual(choose.call_count, 1)

    def test_exposed_and_duplicate_rejection_is_bounded(self):
        stem = generator.original.parse_stems()[0]
        result = generator.continuation(stem, 0, 0, generator.SEEDS[0])
        with patch.object(generator, "continuation", return_value=result), patch.object(generator, "MAX_ATTEMPTS", 2):
            for excluded in ({key(result[0])}, set()):
                with self.assertRaisesRegex(ValueError, "Attempt limit"):
                    generator.generate(excluded)

    def test_synthetic_pgn_prefixes_and_omissions_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "games.pgn").write_text('[Result "*"]\n\n1. e4 e5 *\n\n[Result "*"]\n\n1. d4 -- *\n'
                                            '\n[SetUp "1"]\n[FEN "8/8/8/8/8/8/8/8 w - - 0 1"]\n[Result "*"]\n\n*\n')
            (root / "empty.pgn").write_text("")
            roots, counts, exceptions, digest = generator.history.saved_game_roots(root)
            board = chess.Board(); expected = {key(board)}
            for move in ("e2e4", "e7e5"): board.push_uci(move); expected.add(key(board))
            board = chess.Board(); board.push_uci("d2d4"); expected.add(key(board))
            self.assertEqual(roots, expected)
            self.assertEqual(counts, {"files": 2, "games": 3, "legal_prefix_games": 1, "invalid_initial_games": 1})
            self.assertEqual({row["reason"] for row in exceptions},
                             {"empty_pgn", "invalid_initial_position", "parser_error_or_null_or_illegal_move"})
            self.assertEqual(len(digest), 64)

    def test_source_byte_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "tests").mkdir()
            source = root / "tests/example.py"
            source.write_text('fen = "8/8/8/8/8/2k5/8/K7 w - - 0 1"\n')
            roots, record = generator.history.source_record(root, "tests/example.py", "valid-fen-literals")
            metadata = {"sources": [record], "accepted": [], "combined_unique_roots": len(roots),
                        "public_unique_roots": len(roots), "saved_game_unique_roots": 0}
            self.assertEqual(generator.history.verify_sources(metadata, root)["sources"], 1)
            source.write_text(source.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "Source replay/hash"):
                generator.history.verify_sources(metadata, root)

    def test_source_discovery_excludes_only_new_match_and_keeps_prior_exposure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for part in ("tests/data", "tools", "results/old/match",
                         "results/phase4f7-puzzles/match", "results/phase4f13-match-fixture/match"):
                (root / part).mkdir(parents=True)
            (root / "tools/bench.py").write_text('POSITIONS = ["startpos"]\n')
            prior = root / "tests/data/old.json"
            prior.write_text(json.dumps({"openings": [{"moves": ["e2e4"]}]}))
            profile = json.dumps({"positions": [{"position": "startpos moves d2d4"}]})
            (root / "tests/data/profile.json").write_text(profile)
            (root / "tests/data/phase4f7-puzzles.json").write_text(profile)
            (root / "tests/data/phase4f3-01.json").write_text(prior.read_text())
            (root / "tests/data/phase4f13-match-late.json").write_text(prior.read_text())
            fen = 'fen = "8/8/8/8/8/2k5/8/K7 w - - 0 1"\n'
            for filename in generator.PREPARATION_NAMES:
                (root / "tests" / filename).write_text(fen)
            (root / "tests/phase4f7_puzzles_test.py").write_text(fen)
            for part in ("old", "phase4f7-puzzles", "phase4f13-match-fixture"):
                (root / f"results/{part}/match/game.pgn").write_text('[Result "*"]\n\n1. e4 *\n')
            specs = generator.source_specs(root)
            for relative, kind in (("tests/data/old.json", "opening-suite"),
                                   ("tests/data/profile.json", "json-positions"),
                                   ("tests/data/phase4f7-puzzles.json", "json-positions"),
                                   ("tests/data/phase4f3-01.json", "opening-suite"),
                                   ("tests/phase4f7_puzzles_test.py", "valid-fen-literals"),
                                   ("results/old/match", "saved-pgn-directory"),
                                   ("results/phase4f7-puzzles/match", "saved-pgn-directory")):
                self.assertIn((relative, kind), specs)
            self.assertFalse(any(generator.PREFIX in path for path, _ in specs))
            self.assertFalse(any(Path(path).name in generator.PREPARATION_NAMES for path, _ in specs))

if __name__ == "__main__":
    unittest.main()
