#!/usr/bin/env python3
"""Independent legality and deterministic-source checks for fresh LMR inputs.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
No engine is imported or started; these inputs remain unevaluated.
"""
from collections import Counter
import copy
import hashlib
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
import generate_lmr_20261022_openings as generator
import match


def key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


class FreshLMROpeningsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads((ROOT / "tests/data" / generator.METADATA).read_bytes())
        cls.files = generator.assets(cls.metadata, ROOT)
        cls.documents = [json.loads(cls.files[name]) for name in generator.SUITE_NAMES]
        cls.catalog = json.loads(cls.files[Path(generator.EXCLUSION_MANIFEST).name])

    def test_assets_reproduce_byte_for_byte(self):
        generator.original.check_assets(self.files, ROOT / "tests/data")
        self.assertEqual(generator.assets(self.metadata, ROOT), self.files)

    def test_all_histories_legal_unique_and_nonterminal(self):
        roots, identifiers, turns, lengths = set(), set(), Counter(), Counter()
        for shard, document in enumerate(self.documents, 1):
            self.assertEqual(len(document["openings"]), 64)
            shard_turns, families = Counter(), Counter()
            for entry in document["openings"]:
                self.assertNotIn("fen", entry)
                board = chess.Board()
                for text in entry["moves"]:
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                    self.assertTrue(board.is_valid())
                    self.assertIsNone(board.outcome(claim_draw=True))
                expected = 19 if entry["variant"] < 2 else 20
                self.assertEqual(len(board.move_stack), expected)
                self.assertEqual(entry["final_fen"], board.fen())
                self.assertEqual(entry["canonical_root"], key(board))
                self.assertEqual(entry["shard"], shard)
                self.assertNotIn(key(board), roots)
                self.assertNotIn(entry["id"], identifiers)
                roots.add(key(board)); identifiers.add(entry["id"])
                turns[board.turn] += 1; shard_turns[board.turn] += 1
                lengths[expected] += 1; families[entry["moves"][0]] += 1
            self.assertEqual(shard_turns, {chess.WHITE: 32, chess.BLACK: 32})
            self.assertEqual(families, {"e2e4": 24, "d2d4": 24, "c2c4": 8, "g1f3": 8})
        self.assertEqual(len(roots), 256)
        self.assertEqual(turns, {chess.WHITE: 128, chess.BLACK: 128})
        self.assertEqual(lengths, {19: 128, 20: 128})

    def test_exact_original_stems_and_four_variants(self):
        for stem_index, stem in enumerate(generator.original.parse_stems()):
            rows = [row for row in self.metadata["accepted"] if row["stem_id"] == stem["id"]]
            self.assertEqual([row["variant"] for row in rows], [0, 1, 2, 3])
            for row in rows:
                self.assertEqual(row["moves"][:16], stem["moves"])
                self.assertEqual(row["shard"], (stem_index % 2) * 2 + row["variant"] % 2 + 1)
        self.assertIn("stems have been used before", self.metadata["limitations"])

    def test_disjoint_compact_catalog_and_previous_suites(self):
        excluded = {row["root_key"] for row in self.catalog["roots"]}
        self.assertEqual(len(excluded), self.catalog["unique_roots"])
        for root in excluded:
            board = chess.Board(root + " 0 1")
            self.assertTrue(board.is_valid())
            self.assertEqual(key(board), root)
        accepted = {row["canonical_root"] for row in self.metadata["accepted"]}
        self.assertFalse(accepted & excluded)
        for path in (ROOT / "tests/data").glob("*.json"):
            if path.name.startswith(generator.PREFIX):
                continue
            data = json.loads(path.read_text())
            if not isinstance(data, dict) or not isinstance(data.get("openings"), list):
                continue
            for entry in data["openings"]:
                board = chess.Board(entry["fen"]) if "fen" in entry else chess.Board()
                for move in entry.get("moves", []):
                    board.push_uci(move)
                self.assertIn(key(board), excluded)
                self.assertNotIn(key(board), accepted)

    def test_saved_sources_include_every_available_pgn_directory_and_readiness(self):
        records = {row["path"]: row for row in self.metadata["sources"] if row["kind"] == "saved-pgn-directory"}
        # Only immutable pre-existing PGN directories are relevant. A later new
        # campaign can exist without retroactively changing these frozen inputs.
        self.assertEqual(len(records), 28)
        self.assertEqual(sum(row["replay_counts"]["files"] for row in records.values()), 1772)
        for shard in range(1, 5):
            self.assertIn("results/match-readiness-20261020/canary/shard-{}".format(shard), records)
        for row in records.values():
            self.assertEqual(row["exceptions"], [])
        owner = next(row for row in self.metadata["sources"] if row["path"] == "tools/batch_positions.py")
        self.assertEqual(owner["sha256"], "8e5646fcd56693f60d69e7692a5f623568448a646dcd722b484bd386171920ab")
        self.assertEqual(self.metadata["saved_game_overlap_with_accepted"], [])

    def test_rejections_and_shard_digests_accounted(self):
        self.assertEqual(self.metadata["seed"], 20261022422)
        self.assertEqual(self.metadata["domain"], "chess0live.lmr.20261022.openings.v1")
        for entry in self.metadata["accepted"]:
            rejected = [row for row in self.metadata["rejections"]
                        if (row["stem_id"], row["variant"]) == (entry["stem_id"], entry["variant"])]
            self.assertEqual([row["attempt"] for row in rejected], list(range(entry["accepted_attempt"])))
        for row in self.metadata["shards"]:
            self.assertEqual(hashlib.sha256(self.files[Path(row["path"]).name]).hexdigest(), row["sha256"])
        self.assertEqual(hashlib.sha256(self.files[Path(generator.EXCLUSION_MANIFEST).name]).hexdigest(),
                         self.metadata["exclusion_manifest"]["sha256"])

    def test_match_loader_accepts_full_histories(self):
        for name in generator.SUITE_NAMES:
            _, roots = match.read_openings(name, self.files[name])
            self.assertEqual(len(roots), 64)
            self.assertTrue(all(len(root.board.move_stack) in (19, 20) for root in roots))

    def public_checkout(self, path):
        for relative in (generator.GENERATOR, generator.original.GENERATOR_PATH,
                         generator.original.EXCLUSION_MANIFEST):
            target = path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def test_public_reproduction_without_local_game_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self.public_checkout(path)
            self.assertEqual(generator.assets(self.metadata, path), self.files)

    def test_generator_and_stem_source_drift_rejected(self):
        for relative in (generator.GENERATOR, generator.original.GENERATOR_PATH):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                path = Path(directory); self.public_checkout(path)
                target = path / relative
                target.write_bytes(target.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    generator.assets(self.metadata, path)

    def test_altered_seed_domain_roots_or_rejections_rejected(self):
        for field in ("seed", "domain", "accepted", "rejections", "additional_excluded_roots"):
            forged = copy.deepcopy(self.metadata)
            if field == "seed": forged[field] = 1
            elif field == "domain": forged[field] = "other"
            elif field in ("accepted", "rejections"): forged[field] = []
            else: forged[field].append(forged[field][0])
            with self.subTest(field=field), self.assertRaises(ValueError):
                generator.assets(forged, ROOT)

    def test_referee_version_rejected(self):
        with patch.object(chess, "__version__", "0.0"), self.assertRaisesRegex(ValueError, "Requires chess"):
            generator.assets(self.metadata, ROOT)

    def test_unbiased_sha_word_rejection(self):
        values = [(1 << 256) - 1, 4]
        hashes = [SimpleNamespace(digest=lambda value=value: value.to_bytes(32, "big")) for value in values]
        with patch.object(generator.hashlib, "sha256", side_effect=hashes):
            self.assertEqual(generator.choose_index(3, "e4-01", 0, 0, 0), 1)
        with self.assertRaises(ValueError): generator.choose_index(0, "e4-01", 0, 0, 0)

    def test_terminal_intermediate_tail_stops(self):
        board = chess.Board()
        for move in ("f2f3", "e7e5", "g2g4"): board.push_uci(move)
        index = sorted(move.uci() for move in board.legal_moves).index("d8h4")
        with patch.object(generator, "choose_index", return_value=index) as choose:
            result, tail, terminal = generator.continuation({"board": board, "id": "fixture"}, 0, 0)
        self.assertTrue(terminal); self.assertTrue(result.is_checkmate())
        self.assertEqual(tail, ["d8h4"]); self.assertEqual(choose.call_count, 1)

    def test_exposed_and_duplicate_candidates_are_rejected(self):
        stem = generator.original.parse_stems()[0]
        result = generator.continuation(stem, 0, 0)
        with patch.object(generator, "continuation", return_value=result), patch.object(generator, "MAX_ATTEMPTS", 2):
            with self.assertRaisesRegex(ValueError, "Attempt limit"):
                generator.generate({key(result[0])})
            with self.assertRaisesRegex(ValueError, "Attempt limit"):
                generator.generate(set())

    def test_all_pgn_games_and_legal_prefixes_included(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "games.pgn").write_text('[Result "*"]\n\n1. e4 e5 *\n\n[Result "*"]\n\n1. d4 -- *\n')
            roots, counts, exceptions, digest = generator.saved_game_roots(path)
            board = chess.Board(); expected = {key(board)}
            for move in ("e2e4", "e7e5"): board.push_uci(move); expected.add(key(board))
            board = chess.Board(); board.push_uci("d2d4"); expected.add(key(board))
            self.assertEqual(roots, expected)
            self.assertEqual(counts, {"files": 1, "games": 2, "legal_prefix_games": 1, "invalid_initial_games": 0})
            self.assertEqual(len(exceptions), 1); self.assertEqual(len(digest), 64)

    def test_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); (path / "tests").mkdir()
            source = path / "tests/example.py"
            source.write_text('fen = "8/8/8/8/8/2k5/8/K7 w - - 0 1"\n')
            roots, record = generator.source_record(path, "tests/example.py", "valid-fen-literals")
            metadata = {"sources": [record], "accepted": [], "combined_unique_roots": len(roots),
                        "public_unique_roots": len(roots), "saved_game_unique_roots": 0}
            self.assertEqual(generator.verify_sources(metadata, path)["sources"], 1)
            source.write_text(source.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "Source replay/hash"):
                generator.verify_sources(metadata, path)

    def test_changed_assets_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            generator.original.write_assets(self.files, directory)
            changed = Path(directory) / generator.SUITE_NAMES[0]
            changed.write_bytes(b"preserve me")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                generator.original.write_assets(self.files, directory)
            self.assertEqual(changed.read_bytes(), b"preserve me")


if __name__ == "__main__":
    unittest.main()
