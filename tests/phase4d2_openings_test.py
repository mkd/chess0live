#!/usr/bin/env python3
"""Independent Phase 4D.2 history, exclusion, and reproducibility checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
No engine is imported or started; held-out inputs remain unevaluated.
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
import generate_phase4d2_openings as generator
import match


def key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


class Phase4D2OpeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = generator.generate(ROOT)
        cls.documents = [json.loads(cls.files[name]) for name in generator.SUITE_NAMES]
        cls.metadata = json.loads(cls.files[generator.METADATA_NAME])
        cls.catalog = json.loads((ROOT / generator.EXCLUSION_MANIFEST).read_bytes())

    def test_assets_reproduce_byte_for_byte(self):
        generator.check_assets(self.files, ROOT / "tests/data")
        self.assertEqual(generator.generate(ROOT), self.files)

    def test_all_full_histories_legal_unique_balanced_and_nonterminal(self):
        roots, identifiers, turns, lengths = set(), set(), Counter(), Counter()
        for shard, document in enumerate(self.documents):
            self.assertEqual(len(document["openings"]), 64)
            shard_turns = Counter()
            for entry in document["openings"]:
                self.assertNotIn("fen", entry)
                board = chess.Board()
                for ply, text in enumerate(entry["moves"], 1):
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                    self.assertTrue(board.is_valid())
                    if ply >= 16:
                        self.assertIsNone(board.outcome(claim_draw=True))
                expected = 19 if entry["variant"] < 4 else 20
                self.assertEqual(len(board.move_stack), expected)
                self.assertEqual(entry["final_fen"], board.fen())
                self.assertEqual(entry["canonical_root"], key(board))
                self.assertEqual((int(entry["stem_id"].split("-")[1]) - 1) % 2 * 4 + entry["variant"] % 4, shard)
                self.assertNotIn(key(board), roots)
                self.assertNotIn(entry["id"], identifiers)
                roots.add(key(board)); identifiers.add(entry["id"])
                turns[board.turn] += 1; shard_turns[board.turn] += 1
                lengths[expected] += 1
            self.assertEqual(shard_turns, {chess.WHITE: 32, chess.BLACK: 32})
        self.assertEqual(len(roots), 512)
        self.assertEqual(turns, {chess.WHITE: 256, chess.BLACK: 256})
        self.assertEqual(lengths, {19: 256, 20: 256})

    def test_family_allocation_eight_variants_and_new_stems(self):
        stems = self.metadata["stems"]
        self.assertEqual(Counter(stem["moves"][0] for stem in stems),
                         {"e2e4": 24, "d2d4": 24, "c2c4": 8, "g1f3": 8})
        old = json.loads((ROOT / "tests/data/phase3l-generation.json").read_bytes())
        old_histories = {tuple(stem["moves"]) for stem in old["stems"]}
        for stem in stems:
            self.assertNotIn(tuple(stem["moves"]), old_histories)
            variants = []
            for document in self.documents:
                for entry in document["openings"]:
                    if entry["stem_id"] == stem["id"]:
                        self.assertEqual(entry["moves"][:16], stem["moves"])
                        variants.append(entry["variant"])
            self.assertEqual(sorted(variants), list(range(8)))

    def test_disjoint_every_catalog_root(self):
        # Independent decoding, canonicalization, and set checks do not trust
        # the generator's precomputed suite root fields or exclusion helper.
        excluded = set()
        for entry in self.catalog["roots"]:
            board = chess.Board(entry["root_key"] + " 0 1")
            self.assertTrue(board.is_valid())
            self.assertEqual(key(board), entry["root_key"])
            self.assertNotIn(key(board), excluded)
            self.assertTrue(entry["sources"])
            excluded.add(key(board))
        self.assertEqual(len(excluded), self.catalog["unique_roots"])
        for document in self.documents:
            for entry in document["openings"]:
                board = chess.Board()
                for text in entry["moves"]:
                    board.push_uci(text)
                self.assertNotIn(key(board), excluded)

    def test_prior_catalog_and_untouched_3l_roots_programmatically_excluded(self):
        catalog = {entry["root_key"] for entry in self.catalog["roots"]}
        inherited = json.loads((ROOT / "tests/data/phase3l-exclusions.json").read_bytes())
        self.assertTrue({entry["root_key"] for entry in inherited["roots"]} <= catalog)
        self.assertEqual(len(inherited["roots"]), 851)
        heldout_count = 0
        # These previous unplayed inputs are read only for exclusion checking.
        # No engine is invoked, and no old root is printed or searched.
        for source in self.catalog["sources"][1:5]:
            document = json.loads((ROOT / source["path"]).read_bytes())
            for entry in document["openings"]:
                board = chess.Board()
                for text in entry["moves"]:
                    move = chess.Move.from_uci(text)
                    self.assertIn(move, board.legal_moves)
                    board.push(move)
                self.assertIn(key(board), catalog)
                heldout_count += 1
        self.assertEqual(heldout_count, 256)

    def test_new_exposed_corpora_and_private_provenance_preserved(self):
        roots, sources = generator.exclusion_roots(ROOT)
        self.assertEqual(len(roots), self.metadata["excluded_unique_roots"])
        by_path = {source["path"]: source for source in sources}
        self.assertEqual(by_path["tests/data/countermove-profile.json"]["entries"], 15)
        self.assertEqual(by_path["tests/data/syzygy-cases.json"]["entries"], 140)
        base = by_path["tests/data/phase3l-exclusions.json"]
        inherited = {source["path"]: source for source in base["inherited_sources"]}
        self.assertEqual(inherited["results/phase3j-20261018/workbook-inputs.json"]["entries"], 39)
        self.assertEqual(inherited["results/manual-cutechess-20261014/positions.fen"]["entries"], 171)
        self.assertEqual(inherited["results/manual-cutechess-20261018/positions.fen"]["entries"], 122)
        self.assertEqual(hashlib.sha256((ROOT / generator.EXCLUSION_MANIFEST).read_bytes()).hexdigest(),
                         self.metadata["exclusion_manifest"]["sha256"])
        self.assertTrue(any("unavailable" in text for text in self.catalog["limitations"]))
        self.assertEqual(base["sha256"], generator.BASE_CATALOG_SHA256)

    def test_original_local_evidence_reproduces_catalog_when_available(self):
        if not all((ROOT / source["path"]).exists()
                   and generator.digest((ROOT / source["path"]).read_bytes()) == source["sha256"]
                   for source in self.catalog["sources"]):
            self.skipTest("Original frozen evidence is not all present at these revisions")
        self.assertEqual(generator.encoded(generator.catalog_exclusions(ROOT)),
                         (ROOT / generator.EXCLUSION_MANIFEST).read_bytes())

    def public_checkout(self, path):
        for source in self.catalog["sources"]:
            if source["availability"] == "tracked":
                target = path / source["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / source["path"], target)
        target = path / generator.EXCLUSION_MANIFEST
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / generator.EXCLUSION_MANIFEST, target)

    def test_public_checkout_without_private_evidence_reproduces(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self.public_checkout(path)
            self.assertEqual(generator.generate(path), self.files)

    def test_manifest_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self.public_checkout(path)
            catalog_path = path / generator.EXCLUSION_MANIFEST
            catalog_path.write_bytes(catalog_path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                generator.generate(path)

    def test_source_drift_or_missing_tracked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self.public_checkout(path)
            source = path / "tools/bench.py"
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "source hash"):
                generator.exclusion_roots(path, verify_sources=True)
            source.unlink()
            with self.assertRaisesRegex(ValueError, "source missing"):
                generator.exclusion_roots(path, verify_sources=True)

    def test_later_fixture_revisions_do_not_change_immutable_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); self.public_checkout(path)
            source = path / "tests/uci_test.py"
            source.write_bytes(source.read_bytes() + b"\n# Later development fixture.\n")
            self.assertEqual(generator.generate(path), self.files)
            with self.assertRaisesRegex(ValueError, "source hash"):
                generator.exclusion_roots(path, verify_sources=True)

    def test_forged_catalog_roots_and_provenance_are_rejected(self):
        for alteration in ("duplicate", "source", "clock", "missing_root"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as directory:
                path = Path(directory); self.public_checkout(path)
                altered = copy.deepcopy(self.catalog)
                if alteration == "duplicate":
                    altered["roots"].append(altered["roots"][0])
                elif alteration == "source":
                    altered["roots"][0]["sources"] = [-1]
                elif alteration == "clock":
                    altered["roots"][0]["root_key"] += " 0 1"
                else:
                    altered["roots"].pop()
                    altered["unique_roots"] -= 1
                contents = generator.encoded(altered)
                (path / generator.EXCLUSION_MANIFEST).write_bytes(contents)
                with patch.object(generator, "EXCLUSION_SHA256", generator.digest(contents)):
                    with self.assertRaises(ValueError):
                        generator.generate(path)

    def test_match_loader_accepts_full_histories(self):
        for name in generator.SUITE_NAMES:
            _, openings = match.read_openings(name, self.files[name])
            self.assertEqual(len(openings), 64)
            self.assertTrue(all(len(opening.board.move_stack) in (19, 20) for opening in openings))

    def test_metadata_and_rejections_are_accounted(self):
        self.assertEqual(self.metadata["seed"], 20261018422)
        self.assertEqual(self.metadata["policy"]["domain"], "chess0live.phase4d2.openings.v1")
        totals = Counter()
        for slot in self.metadata["slots"]:
            self.assertEqual(slot["accepted_attempt"], len(slot["rejections"]))
            self.assertEqual([x["attempt"] for x in slot["rejections"]], list(range(slot["accepted_attempt"])))
            totals.update(x["reason"] for x in slot["rejections"])
        for reason in ("terminal", "duplicate", "prior_overlap"):
            self.assertEqual(totals[reason], self.metadata["rejection_totals"][reason])
        for shard in self.metadata["shards"]:
            self.assertEqual(generator.digest(self.files[Path(shard["path"]).name]), shard["sha256"])

    def test_wrong_seed_or_referee_rejected(self):
        with self.assertRaisesRegex(ValueError, "frozen to seed"):
            generator.generate(ROOT, seed=1)
        with patch.object(chess, "__version__", "0.0"):
            with self.assertRaisesRegex(ValueError, "Require chess"):
                generator.generate(ROOT)

    def test_sha_sampling_avoids_modulo_bias(self):
        values = [(1 << 256) - 1, 4]
        hashes = [SimpleNamespace(digest=lambda value=value: value.to_bytes(32, "big")) for value in values]
        with patch.object(generator.hashlib, "sha256", side_effect=hashes):
            self.assertEqual(generator.choose_index(3, generator.SEED, "e4-01", 0, 0, 0), (1, 1))

    def test_bad_history_and_null_move_rejected(self):
        for text in ("startpos moves 0000", "startpos moves e2e5", "startpos moves", "startpos wrong"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                generator.command_board(text)

    def test_root_key_normalizes_irrelevant_ep_and_clocks(self):
        board = chess.Board(); board.push_uci("e2e4")
        self.assertNotIn("e3", key(board))
        changed = board.copy(); changed.halfmove_clock = 77; changed.fullmove_number = 90
        self.assertEqual(key(board), key(changed))

    def test_terminal_intermediate_tail_rejected(self):
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

    def test_duplicate_generated_roots_rejected_until_limit(self):
        outcome = generator.continuation(generator.parse_stems()[0], 0, 0, generator.SEED)
        with patch.object(generator, "continuation", return_value=outcome) as continuation:
            with patch.object(generator, "MAX_ATTEMPTS", 2):
                with self.assertRaisesRegex(ValueError, "Attempt limit reached"):
                    generator.generate(ROOT)
        self.assertEqual(continuation.call_count, 3)

    def test_prior_overlap_rejected_until_limit(self):
        board = chess.Board(self.metadata["stems"][0]["root_fen"])
        with patch.object(generator, "exclusion_roots", return_value=({key(board)}, [])):
            with patch.object(generator, "continuation", return_value=(board, [], 0, False)) as continuation:
                with patch.object(generator, "MAX_ATTEMPTS", 2):
                    with self.assertRaisesRegex(ValueError, "Attempt limit reached"):
                        generator.generate(ROOT)
        self.assertEqual(continuation.call_count, 2)

    def test_duplicate_stem_rejected(self):
        with patch.object(generator, "STEMS", generator.STEMS + (generator.STEMS[0],)):
            with self.assertRaisesRegex(ValueError, "Duplicate stem"):
                generator.parse_stems()

    def test_changed_assets_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            generator.write_assets(self.files, directory)
            generator.write_assets(self.files, directory)
            path = Path(directory) / generator.SUITE_NAMES[0]
            path.write_bytes(b"preserve me")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                generator.write_assets(self.files, directory)
            self.assertEqual(path.read_bytes(), b"preserve me")
            with self.assertRaisesRegex(ValueError, "Reproduction mismatch"):
                generator.check_assets(self.files, directory)


if __name__ == "__main__":
    unittest.main()
