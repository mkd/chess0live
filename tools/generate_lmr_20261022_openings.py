#!/usr/bin/env python3
"""Reproduce the fresh, unevaluated October 22 conservative-LMR openings.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Only legality, terminal-state and prior-root checks select continuations. Public
reproduction uses the compact immutable snapshot; --verify-sources additionally
replays all recorded local PGNs and checks every source digest. No engine runs.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

import chess
import chess.pgn

import generate_phase4d2_openings as original

SEED = 20261022422
DOMAIN = "chess0live.lmr.20261022.openings.v1"
PREFIX = "lmr-20261022"
GENERATOR = "tools/generate_lmr_20261022_openings.py"
METADATA = PREFIX + "-generation.json"
EXCLUSION_MANIFEST = "tests/data/" + PREFIX + "-exclusions.json"
SUITE_NAMES = tuple(PREFIX + "-{:02d}.json".format(n) for n in range(1, 5))
MAX_ATTEMPTS = 10000
PROVENANCE = (
    "The 64 original chess0live 16-ply stems from generate_phase4d2_openings, "
    "with four new SHA-256-selected legal tails per stem. No external database, "
    "owner previous-engine assets, engine search, evaluation, outcome or "
    "material/balance filtering is used. Prior files are read only for exclusion."
)
LIMITATIONS = (
    "Final roots are disjoint from recorded available public inputs, valid FEN "
    "fixtures and saved played mainlines. The stems have been used before and "
    "four continuations from each stem are related; canonical-root disjointness "
    "does not prove independent or representative samples. Internal search/PV "
    "nodes, unsaved games and dynamically constructed fixtures are not covered."
)


def choose_index(count, stem, variant, attempt, ply):
    """Reject high SHA words before modulo to avoid bounded-selection bias."""
    if count < 1:
        raise ValueError("Cannot sample an empty move list")
    space, counter = 1 << 256, 0
    while True:
        payload = "|".join(map(str, (DOMAIN, SEED, stem, variant, attempt, ply, counter)))
        word = int.from_bytes(hashlib.sha256(payload.encode("ascii")).digest(), "big")
        if word < space - space % count:
            return word % count
        counter += 1


def continuation(stem, variant, attempt):
    """Keep full repetition history and reject a terminal intermediate node."""
    board, tail = stem["board"].copy(stack=True), []
    for ply in range(3 if variant < 2 else 4):
        if board.outcome(claim_draw=True) is not None:
            return board, tail, True
        legal = sorted(board.legal_moves, key=lambda move: move.uci())
        move = legal[choose_index(len(legal), stem["id"], variant, attempt, ply)]
        board.push(move)
        tail.append(move.uci())
        if board.outcome(claim_draw=True) is not None:
            return board, tail, True
    return board, tail, False


def generate(excluded):
    """Four 64-pair shards, each with 32 roots per side and balanced families."""
    used, entries, rejections = set(), [], []
    for stem_index, stem in enumerate(original.parse_stems()):
        for variant in range(4):
            for attempt in range(MAX_ATTEMPTS):
                board, tail, terminal = continuation(stem, variant, attempt)
                key = original.canonical_root(board)
                reason = ("terminal" if terminal else "duplicate" if key in used
                          else "exposed" if key in excluded else None)
                if reason:
                    rejections.append({"stem_id": stem["id"], "variant": variant,
                                       "attempt": attempt, "reason": reason, "root_key": key})
                    continue
                expected = 19 if variant < 2 else 20
                if not board.is_valid() or len(stem["moves"] + tail) != expected:
                    raise ValueError("Invalid generated history")
                used.add(key)
                entries.append({"id": PREFIX + "-{}-v{}".format(stem["id"], variant),
                                "stem_id": stem["id"], "variant": variant,
                                "shard": (stem_index % 2) * 2 + variant % 2 + 1,
                                "moves": stem["moves"] + tail, "final_fen": board.fen(),
                                "canonical_root": key, "accepted_attempt": attempt})
                break
            else:
                raise ValueError("Attempt limit reached")
    return entries, rejections


class QuietGameBuilder(chess.pgn.GameBuilder):
    """Keep parser errors in provenance without emitting or selecting on them."""
    def handle_error(self, error):
        self.game.errors.append(error)


def saved_game_roots(directory):
    """Read every PGN in one directory, retaining legal prefixes of bad fixtures.

    No score, result or comment participates. A synthetic PGN with an illegal or
    null move still exposes its legal prefix. Its truncation is explicitly logged
    instead of silently treating it as a valid complete game.
    """
    roots, manifest, exceptions = set(), [], []
    counts = {"files": 0, "games": 0, "legal_prefix_games": 0, "invalid_initial_games": 0}
    for path in sorted(directory.glob("*.pgn")):
        raw = path.read_bytes()
        manifest.append({"path": path.name, "sha256": original.digest(raw)})
        counts["files"] += 1
        stream = io.StringIO(raw.decode("utf-8-sig"))
        file_games = 0
        while True:
            game = chess.pgn.read_game(stream, Visitor=QuietGameBuilder)
            if game is None:
                break
            counts["games"] += 1
            file_games += 1
            try:
                board = game.board()
            except ValueError:
                board = None
            if board is None or not board.is_valid():
                counts["invalid_initial_games"] += 1
                exceptions.append({"path": path.name, "game": file_games, "reason": "invalid_initial_position"})
                continue
            roots.add(original.canonical_root(board))
            incomplete = bool(game.errors)
            for move in game.mainline_moves():
                if not move or move not in board.legal_moves:
                    incomplete = True
                    break
                board.push(move)
                roots.add(original.canonical_root(board))
            if incomplete:
                counts["legal_prefix_games"] += 1
                exceptions.append({"path": path.name, "game": file_games, "reason": "parser_error_or_null_or_illegal_move"})
        if not file_games:
            exceptions.append({"path": path.name, "game": 0, "reason": "empty_pgn"})
    if not manifest:
        raise ValueError("No PGNs in saved source: " + str(directory))
    return roots, counts, exceptions, original.digest(original.encoded(manifest))


def source_record(repository, relative, kind):
    path = repository / relative
    if kind == "saved-pgn-directory":
        keys, counts, exceptions, sha = saved_game_roots(path)
        details = {"entries": counts["games"], "replay_counts": counts, "exceptions": exceptions,
                   "sha256": sha, "digest_scope": "sorted immediate PGN names and each byte-stream SHA256"}
    else:
        values = original.source_roots(path, kind)
        keys = set(values)
        details = {"entries": len(values), "sha256": original.digest(path.read_bytes())}
    record = {"path": relative, "kind": kind,
              "availability": "local" if relative.startswith("results/") else "tracked",
              "unique_roots": len(keys),
              "canonical_roots_sha256": original.digest(original.encoded(sorted(keys))), **details}
    return keys, record


def source_specs(repository):
    """Freeze existing sources only; later files cannot alter the frozen sample."""
    specs = [(original.EXCLUSION_MANIFEST, "canonical-catalog")]
    own = {Path(GENERATOR).name, "lmr_20261022_openings_test.py"}
    for path in sorted((repository / "tests/data").glob("*.json")):
        if path.name.startswith(PREFIX):
            continue
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("openings"), list):
            specs.append((str(path.relative_to(repository)), "opening-suite"))
    # Strict six-field literals cover both JSON position fixtures and C++/Python
    # cases, including the owner's editable puzzle list without writing it.
    for directory in ("tests", "tools"):
        for path in sorted((repository / directory).rglob("*")):
            if path.suffix not in (".py", ".cpp", ".hpp", ".json") or path.name in own or path.name.startswith(PREFIX):
                continue
            try:
                original.source_roots(path, "valid-fen-literals")
            except ValueError as error:
                if str(error).startswith("Empty exclusion source:"):
                    continue
                raise
            specs.append((str(path.relative_to(repository)), "valid-fen-literals"))
    # Include all saved PGNs, not only selected campaigns, and preserve partial
    # histories. Sources outside this project are deliberately not opened.
    specs += [(str(directory.relative_to(repository)), "saved-pgn-directory")
              for directory in sorted({path.parent for path in (repository / "results").rglob("*.pgn")})]
    return specs


def snapshot(repository):
    base, _ = original.exclusion_roots(repository)
    public, games, sources = set(base), set(), []
    for relative, kind in source_specs(repository):
        keys, record = source_record(repository, relative, kind)
        (games if kind == "saved-pgn-directory" else public).update(keys)
        sources.append(record)
    entries, rejections = generate(public | games)
    relevant = {row["root_key"] for row in rejections if row["reason"] == "exposed"}
    return {
        "schema_version": 1, "license": original.LICENSE, "copyright": original.COPYRIGHT,
        "generator": GENERATOR, "generator_sha256": original.digest((repository / GENERATOR).read_bytes()),
        "stem_source": {"path": original.GENERATOR_PATH, "sha256": original.digest((repository / original.GENERATOR_PATH).read_bytes())},
        "seed": SEED, "domain": DOMAIN, "chess_version": chess.__version__,
        "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "selection": "All 64 stems in original order, four variants each. Sorted legal UCI moves; SHA256 ASCII domain|seed|stem_id|variant|attempt|tail_ply|draw_counter, unsigned big-endian word, reject >= floor(2**256/count)*count, then modulo count. Counters zero-based; variants 0-1 add three plies; variants 2-3 add four.",
        "sharding": "(stem_index % 2)*2 + variant%2 + 1; each shard 64 roots, 32 per side, families e4:24 d4:24 c4:8 Nf3:8",
        "rejection_policy": "Reject terminal intermediate/final roots with claim_draw=True, duplicate accepted roots, and exposed canonical roots; increment attempt without changing the stem/variant.",
        "canonicalization": original.CANONICALIZATION,
        "base_exclusion": {"path": original.EXCLUSION_MANIFEST, "sha256": original.EXCLUSION_SHA256},
        "additional_excluded_roots": sorted((public | relevant) - base),
        "sources": sources, "public_unique_roots": len(public), "saved_game_unique_roots": len(games),
        "combined_unique_roots": len(public | games),
        "saved_game_overlap_with_accepted": sorted(games & {row["canonical_root"] for row in entries}),
        "root_count": 256, "white_to_move": 128, "black_to_move": 128,
        "root_plies": {"19": 128, "20": 128}, "rejections": rejections, "accepted": entries,
        "scope": "Pinned Phase 4D.2 exclusions; all prior tests/data JSON opening suites; complete valid six-field FEN literals recursively in tests/ and tools/ Python, C++, headers and JSON; every available results/**/*.pgn mainline, including prior readiness, qualification, manual feedback, smoke games and legal prefixes of malformed synthetic records.",
        "omissions": ["Private workbook and owner previous-engine assets are not reopened; previously cataloged workbook roots remain inherited.",
                      "Internal search/PV nodes, unsaved games and dynamically constructed fixtures are not exhaustive.",
                      "Malformed PGNs contribute only referee-legal prefixes; invalid initial positions contribute none, with every such omission recorded.",
                      "Local evidence is not redistributed. Public reproduction retains public keys and any rejected exposed candidates; --verify-sources replays all original recorded sources and rechecks accepted roots against their full union."],
    }


def assets(metadata, repository):
    if chess.__version__ != original.REFEREE_VERSION:
        raise ValueError("Requires chess==" + original.REFEREE_VERSION)
    if (metadata.get("seed") != SEED or metadata.get("domain") != DOMAIN
            or metadata.get("base_exclusion") != {"path": original.EXCLUSION_MANIFEST, "sha256": original.EXCLUSION_SHA256}):
        raise ValueError("Frozen generation policy mismatch")
    if metadata["generator_sha256"] != original.digest((repository / GENERATOR).read_bytes()):
        raise ValueError("Generator hash mismatch")
    source = metadata["stem_source"]
    if source != {"path": original.GENERATOR_PATH, "sha256": original.digest((repository / original.GENERATOR_PATH).read_bytes())}:
        raise ValueError("Stem source hash mismatch")
    base, _ = original.exclusion_roots(repository)
    extra = metadata["additional_excluded_roots"]
    if extra != sorted(set(extra)):
        raise ValueError("Noncanonical exclusion list")
    for root in extra:
        board = chess.Board(root + " 0 1")
        if not board.is_valid() or original.canonical_root(board) != root:
            raise ValueError("Invalid exclusion root")
    entries, rejections = generate(base | set(extra))
    if entries != metadata["accepted"] or rejections != metadata["rejections"]:
        raise ValueError("Generation replay mismatch")
    files = {name: original.encoded({
        "schema_version": 1, "description": "Fresh conservative LMR shard {} of 4; 64 color-swapped pairs".format(index + 1),
        "license": original.LICENSE, "copyright": original.COPYRIGHT, "seed": SEED,
        "shard": index + 1, "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "generator": GENERATOR, "generation_metadata": METADATA,
        "openings": [row for row in entries if row["shard"] == index + 1]})
        for index, name in enumerate(SUITE_NAMES)}
    # The public catalog is intentionally compact: all public keys plus the
    # exposed candidates rejected during deterministic generation. Full private
    # PGN-root disjointness is separately proved by --verify-sources.
    files[Path(EXCLUSION_MANIFEST).name] = original.encoded({
        "schema_version": 1, "license": original.LICENSE, "copyright": original.COPYRIGHT,
        "canonicalization": original.CANONICALIZATION,
        "scope": "Inherited/public roots and exposed rejected candidates; not the complete saved-game root set.",
        "limitations": LIMITATIONS + " Full local-source replay is required for saved-game disjointness.",
        "generation_metadata": METADATA,
        "unique_roots": len(base | set(extra)),
        "roots": [{"root_key": root} for root in sorted(base | set(extra))]})
    return files


def verify_sources(metadata, repository):
    """Fail on missing/drifted source bytes or root/provenance disagreement."""
    combined, public, games = set(), set(), set()
    for expected in metadata["sources"]:
        relative = Path(expected["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in ("tests", "tools", "results"):
            raise ValueError("Invalid source path")
        keys, actual = source_record(repository, str(relative), expected["kind"])
        if actual != expected:
            raise ValueError("Source replay/hash mismatch: " + str(relative))
        combined.update(keys)
        (games if expected["kind"] == "saved-pgn-directory" else public).update(keys)
    if (len(combined) != metadata["combined_unique_roots"] or len(public) != metadata["public_unique_roots"]
            or len(games) != metadata["saved_game_unique_roots"]):
        raise ValueError("Combined source count mismatch")
    if combined & {row["canonical_root"] for row in metadata["accepted"]}:
        raise ValueError("Accepted root overlaps an exposed source")
    return {"sources": len(metadata["sources"]), "excluded_unique_roots": len(combined)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--create", action="store_true", help="Create the immutable initial snapshot")
    modes.add_argument("--check", action="store_true", help="Reproduce all four public shards")
    parser.add_argument("--verify-sources", action="store_true", help="Replay every recorded source, requiring its original bytes")
    args = parser.parse_args()
    directory = args.repository / "tests/data"
    metadata_path = directory / METADATA
    if args.create:
        if metadata_path.exists():
            parser.error("Snapshot already exists")
        metadata = snapshot(args.repository)
    else:
        metadata = json.loads(metadata_path.read_text())
    generated = assets(metadata, args.repository)
    if args.verify_sources:
        verify_sources(metadata, args.repository)
    shards = [{"path": "tests/data/" + name, "sha256": original.digest(data), "roots": 64}
              for name, data in generated.items() if name in SUITE_NAMES]
    exclusion_manifest = {"path": EXCLUSION_MANIFEST, "sha256": original.digest(generated[Path(EXCLUSION_MANIFEST).name])}
    if args.create:
        metadata["shards"] = shards
        metadata["exclusion_manifest"] = exclusion_manifest
        generated[METADATA] = original.encoded(metadata)
        original.write_assets(generated, directory)
    else:
        original.check_assets(generated, directory)
        if metadata["shards"] != shards or metadata["exclusion_manifest"] != exclusion_manifest:
            raise ValueError("Shard digest manifest mismatch")
    print("Validated 256 legal unevaluated roots, four balanced shards, 128 roots per side.")


if __name__ == "__main__":
    main()
