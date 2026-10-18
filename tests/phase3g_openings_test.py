#!/usr/bin/env python3
"""Independent replay and deterministic-generation checks; no engine processes.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import generate_phase3g_openings as generator
import match


def root_key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


class Phase3GOpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = generator.generate(ROOT)
        cls.documents = [json.loads(cls.files[name]) for name in generator.SUITE_NAMES]
        cls.metadata = json.loads(cls.files[generator.METADATA_NAME])

    def test_checked_assets_reproduce_byte_for_byte(self):
        generator.check_assets(self.files, ROOT / "tests/data")
        self.assertEqual(generator.generate(ROOT), self.files)

    def test_every_full_history_is_legal_and_tail_is_nonterminal(self):
        roots, ids, turns, lengths = set(), set(), Counter(), Counter()
        for shard_index, document in enumerate(self.documents):
            self.assertEqual(len(document["openings"]), 64)
            shard_turns = Counter()
            for entry in document["openings"]:
                self.assertNotIn("fen", entry, "All histories must start at startpos")
                board = chess.Board()
                for ply, text in enumerate(entry["moves"], 1):
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                    self.assertTrue(board.is_valid())
                    if ply >= 16:
                        self.assertIsNone(board.outcome(claim_draw=True))
                expected_plies = 19 if entry["variant"] < 4 else 20
                self.assertEqual(len(board.move_stack), expected_plies)
                self.assertEqual(entry["final_fen"], board.fen())
                self.assertEqual(entry["canonical_root"], root_key(board))
                self.assertEqual(entry["variant"] % 4, shard_index)
                self.assertNotIn(root_key(board), roots)
                self.assertNotIn(entry["id"], ids)
                roots.add(root_key(board))
                ids.add(entry["id"])
                turns[board.turn] += 1
                shard_turns[board.turn] += 1
                lengths[expected_plies] += 1
            self.assertEqual(shard_turns, {chess.WHITE: 32, chess.BLACK: 32})
        self.assertEqual(len(roots), 256)
        self.assertEqual(turns, {chess.WHITE: 128, chess.BLACK: 128})
        self.assertEqual(lengths, {19: 128, 20: 128})

    def test_stems_and_sharding_follow_frozen_plan(self):
        stems = self.metadata["stems"]
        self.assertEqual(len(stems), 32)
        self.assertEqual(Counter(stem["moves"][0] for stem in stems),
                         {"e2e4": 12, "d2d4": 12, "c2c4": 4, "g1f3": 4})
        for shard, document in enumerate(self.documents):
            for index, stem in enumerate(stems):
                entries = document["openings"][2 * index:2 * index + 2]
                self.assertEqual([entry["variant"] for entry in entries], [shard, shard + 4])
                for entry in entries:
                    self.assertEqual(entry["stem_id"], stem["id"])
                    self.assertEqual(entry["moves"][:16], stem["moves"])

    def test_disjoint_all_exposed_suites(self):
        # Replay exclusions independently rather than importing the generator's
        # exclusion helper or trusting its precomputed root count.
        excluded, entry_count = set(), 0
        for relative in generator.EXCLUSION_PATHS:
            document = json.loads((ROOT / relative).read_bytes())
            for entry in document["openings"]:
                board = chess.Board(entry.get("fen", chess.STARTING_FEN))
                for text in entry.get("moves", []):
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                excluded.add(root_key(board))
                entry_count += 1
        self.assertEqual(entry_count, 132)
        self.assertEqual(len(excluded), self.metadata["excluded_unique_roots"])
        for document in self.documents:
            for entry in document["openings"]:
                self.assertNotIn(entry["canonical_root"], excluded)

    def test_match_reader_accepts_all_four_full_history_shards(self):
        for name in generator.SUITE_NAMES:
            _, openings = match.read_openings(name, self.files[name])
            self.assertEqual(len(openings), 64)
            self.assertTrue(all(len(opening.board.move_stack) in (19, 20) for opening in openings))

    def test_metadata_pins_sources_shards_and_rejection_counts(self):
        self.assertEqual(self.metadata["seed"], 20261018)
        self.assertEqual(self.metadata["chess_version"], "1.11.2")
        self.assertEqual(self.metadata["root_count"], 256)
        for source in self.metadata["excluded_suites"]:
            self.assertEqual(hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest(), source["sha256"])
        for shard in self.metadata["shards"]:
            self.assertEqual(hashlib.sha256(self.files[Path(shard["path"]).name]).hexdigest(), shard["sha256"])
        totals = Counter()
        for slot in self.metadata["slots"]:
            self.assertEqual(slot["accepted_attempt"], len(slot["rejections"]))
            self.assertEqual([rejection["attempt"] for rejection in slot["rejections"]],
                             list(range(slot["accepted_attempt"])))
            totals.update(rejection["reason"] for rejection in slot["rejections"])
        for reason in ("terminal", "duplicate", "prior_overlap"):
            self.assertEqual(totals[reason], self.metadata["rejection_totals"][reason])

    def test_wrong_seed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "frozen to seed"):
            generator.generate(ROOT, seed=20261019)

    def test_wrong_referee_version_is_rejected(self):
        with patch.object(chess, "__version__", "0.0"):
            with self.assertRaisesRegex(ValueError, "Require chess"):
                generator.generate(ROOT)

    def test_sha_selection_rejects_modulo_bias_word(self):
        values = [(1 << 256) - 1, 4]  # For three choices the first is beyond the limit.
        hashes = [SimpleNamespace(digest=lambda value=value: value.to_bytes(32, "big")) for value in values]
        with patch.object(generator.hashlib, "sha256", side_effect=hashes) as hashed:
            index, rejections = generator.choose_index(3, 20261018, "fixture", 0, 0, 0)
        self.assertEqual((index, rejections), (1, 1))
        self.assertTrue(hashed.call_args_list[0].args[0].endswith(b"|0"))
        self.assertTrue(hashed.call_args_list[1].args[0].endswith(b"|1"))

    def test_empty_move_sampling_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty move list"):
            generator.choose_index(0, generator.SEED, "fixture", 0, 0, 0)

    def test_terminal_intermediate_tail_is_rejected(self):
        board = chess.Board()
        for text in ("f2f3", "e7e5", "g2g4"):
            board.push_uci(text)
        legal = sorted(move.uci() for move in board.legal_moves)
        with patch.object(generator, "choose_index", return_value=(legal.index("d8h4"), 0)) as choice:
            result, tail, _, terminal = generator.continuation({"board": board, "id": "fixture"}, 0, 0, generator.SEED)
        self.assertTrue(terminal)
        self.assertTrue(result.is_checkmate())
        self.assertEqual(tail, ["d8h4"])
        self.assertEqual(choice.call_count, 1)

    def test_duplicate_generated_root_rejected_until_limit(self):
        stem = generator.parse_stems()[0]
        outcome = generator.continuation(stem, 0, 0, generator.SEED)
        self.assertFalse(outcome[3])
        with patch.object(generator, "continuation", return_value=outcome) as continuation:
            with patch.object(generator, "MAX_ATTEMPTS", 2):
                with self.assertRaisesRegex(ValueError, "Attempt limit reached"):
                    generator.generate(ROOT)
        self.assertEqual(continuation.call_count, 3)  # First accepted; then two duplicate attempts.

    def test_prior_overlap_rejected_until_limit(self):
        board = chess.Board(self.metadata["stems"][0]["root_fen"])
        with patch.object(generator, "exclusion_roots", return_value=({root_key(board)}, [])):
            with patch.object(generator, "continuation", return_value=(board, [], 0, False)) as continuation:
                with patch.object(generator, "MAX_ATTEMPTS", 2):
                    with self.assertRaisesRegex(ValueError, "Attempt limit reached"):
                        generator.generate(ROOT)
        self.assertEqual(continuation.call_count, 2)

    def test_duplicate_stem_rejected(self):
        with patch.object(generator, "STEMS", generator.STEMS + (generator.STEMS[0],)):
            with self.assertRaisesRegex(ValueError, "Duplicate stem"):
                generator.parse_stems()

    def test_changed_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="phase3g-openings-") as directory:
            generator.write_assets(self.files, directory)
            generator.write_assets(self.files, directory)  # Identical bytes are a no-op.
            generator.check_assets(self.files, directory)
            changed = Path(directory) / generator.SUITE_NAMES[0]
            changed.write_bytes(b"changed fixture\n")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                generator.write_assets(self.files, directory)
            self.assertEqual(changed.read_bytes(), b"changed fixture\n")
            with self.assertRaisesRegex(ValueError, "Reproduction mismatch"):
                generator.check_assets(self.files, directory)


if __name__ == "__main__":
    unittest.main()
