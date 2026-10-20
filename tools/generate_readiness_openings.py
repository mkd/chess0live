#!/usr/bin/env python3
"""Reproduce four original, unevaluated roots for the October 20 readiness check.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The public snapshot records source digests and canonical exclusions. Generation
uses no engine, evaluation, result, or material filter. --check needs only public
assets; --verify-sources also replays the recorded local game evidence.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

import chess
import chess.pgn

import generate_phase4d2_openings as original


SEED = 20261020401
DOMAIN = "chess0live.match-readiness.20261020.v1"
STEM_IDS = ("e4-01", "d4-01", "c4-01", "nf3-01")
PREFIX = "match-readiness-20261020"
METADATA = PREFIX + "-generation.json"
GENERATOR = "tools/generate_readiness_openings.py"
PROVENANCE = (
    "The first original chess0live 16-ply stem from each e4, d4, c4, and Nf3 "
    "family in generate_phase4d2_openings.STEMS, followed by four legal "
    "SHA-256-selected plies. No owner previous-engine assets, external games, "
    "engine searches, evaluations, outcomes, or balance filters were used."
)
LIMITATIONS = (
    "These four related opening roots are a short match-runner readiness sample, "
    "not strength evidence. Freshness means only disjoint canonical roots from "
    "the recorded available sources. Unrecorded positions and internal search "
    "nodes are not covered; no independent or representative sampling is claimed."
)


def sample(count, stem, attempt, ply):
    """Unbiased SHA word rejection, with a separately named readiness domain."""
    counter, space = 0, 1 << 256
    while True:
        message = "|".join(map(str, (DOMAIN, SEED, stem, attempt, ply, counter)))
        word = int.from_bytes(hashlib.sha256(message.encode("ascii")).digest(), "big")
        if word < space - space % count:
            return word % count
        counter += 1


def generate(excluded):
    """Return exactly one legal nonterminal 20-ply full history per family."""
    stems = {entry["id"]: entry for entry in original.parse_stems()}
    used, entries, rejections = set(), [], []
    for stem_id in STEM_IDS:
        stem = stems[stem_id]
        for attempt in range(10000):
            board, tail = stem["board"].copy(stack=True), []
            terminal = False
            for ply in range(4):
                legal = sorted(board.legal_moves, key=lambda move: move.uci())
                if board.outcome(claim_draw=True) is not None or not legal:
                    terminal = True
                    break
                move = legal[sample(len(legal), stem_id, attempt, ply)]
                board.push(move)
                tail.append(move.uci())
                if board.outcome(claim_draw=True) is not None:
                    terminal = True
                    break
            key = original.canonical_root(board)
            reason = ("terminal" if terminal else "duplicate" if key in used
                      else "exposed" if key in excluded else None)
            if reason:
                rejections.append({"stem_id": stem_id, "attempt": attempt,
                                   "reason": reason, "root_key": key})
                continue
            if len(stem["moves"] + tail) != 20 or not board.is_valid():
                raise ValueError("Invalid generated history")
            used.add(key)
            entries.append({"id": PREFIX + "-" + stem_id, "stem_id": stem_id,
                            "moves": stem["moves"] + tail,
                            "final_fen": board.fen(), "canonical_root": key,
                            "accepted_attempt": attempt})
            break
        else:
            raise ValueError("Attempt limit reached")
    return entries, rejections


def game_roots(path):
    """Replay played game histories only; never inspect PVs or score fields."""
    roots, games = set(), 0
    for line in path.read_text().splitlines():
        record = json.loads(line)
        if not record.get("pgn"):
            raise ValueError("Missing game PGN: " + str(path))
        pgn_path = path.parent / record["pgn"]
        if pgn_path.parent != path.parent:
            raise ValueError("Unexpected PGN path: " + str(pgn_path))
        game = chess.pgn.read_game(io.StringIO(pgn_path.read_text()))
        if game is None or game.errors:
            raise ValueError("Invalid game PGN: " + str(path))
        board = game.board()
        roots.add(original.canonical_root(board))
        for move in game.mainline_moves():
            if move not in board.legal_moves:
                raise ValueError("Illegal recorded move in {}: {}".format(path, move))
            board.push(move)
            roots.add(original.canonical_root(board))
        games += 1
    return roots, games


def source_keys(path, kind):
    if kind == "played-game-histories":
        return game_roots(path)
    values = original.source_roots(path, kind)
    return set(values), len(values)


def pgn_manifest_digest(path):
    """Bind each referenced PGN byte stream without publishing full histories."""
    records = [json.loads(line) for line in path.read_text().splitlines()]
    entries = []
    for record in records:
        pgn = path.parent / record["pgn"]
        if pgn.parent != path.parent:
            raise ValueError("Unexpected PGN path")
        entries.append({"path": record["pgn"], "sha256": original.digest(pgn.read_bytes())})
    return original.digest(original.encoded(entries))


def snapshot(repository):
    """Freeze public fixture roots and compact provenance for local histories."""
    base, _ = original.exclusion_roots(repository)
    specs = [(original.EXCLUSION_MANIFEST, "canonical-catalog")]
    for path in sorted((repository / "tests/data").glob("*.json")):
        if path.name.startswith(PREFIX):
            continue
        data = json.loads(path.read_text())
        if isinstance(data, dict) and isinstance(data.get("openings"), list):
            specs.append((str(path.relative_to(repository)), "opening-suite"))
    # Include the owner's current embedded puzzle corpus read-only, plus current
    # public development/test FEN literals. Malformed-input fixtures are skipped
    # by the original strict parser, not treated as searched chess positions.
    for directory in ("tests", "tools"):
        for path in sorted((repository / directory).glob("*")):
            if path.suffix not in (".py", ".cpp") or path.name == Path(GENERATOR).name:
                continue
            try:
                original.source_roots(path, "valid-fen-literals")
            except ValueError as error:
                if str(error).startswith("Empty exclusion source:"):
                    continue
                raise
            specs.append((str(path.relative_to(repository)), "valid-fen-literals"))
    # Complete saved qualification histories; earlier synthetic smoke games may
    # contain intentional null/illegal moves and are not qualification evidence.
    # Mainline roots, rather than all protocol PV nodes, bound this audit.
    specs += [(str(path.relative_to(repository)), "played-game-histories")
              for path in sorted((repository / "results").rglob("games.jsonl"))
              if path.relative_to(repository / "results").parts[0].startswith(
                  ("phase2d-", "phase3g-lmr-", "phase4d2-"))]
    public, games, sources = set(base), set(), []
    for relative, kind in specs:
        path = repository / relative
        keys, entries = source_keys(path, kind)
        target = games if kind == "played-game-histories" else public
        target.update(keys)
        sources.append({"path": relative, "kind": kind,
                        "availability": "local" if relative.startswith("results/") else "tracked",
                        "sha256": original.digest(path.read_bytes()), "entries": entries,
                        "unique_roots": len(keys),
                        "canonical_roots_sha256": original.digest(original.encoded(sorted(keys)))})
        if kind == "played-game-histories":
            sources[-1]["referenced_pgn_manifest_sha256"] = pgn_manifest_digest(path)
    entries, rejections = generate(public | games)
    # Replay only needs the public additional catalog and any rejected game
    # candidates. The full (much larger) private game root set is not published.
    relevant = {row["root_key"] for row in rejections if row["reason"] == "exposed"}
    return {
        "schema_version": 1, "license": original.LICENSE, "copyright": original.COPYRIGHT,
        "generator": GENERATOR, "generator_sha256": original.digest((repository / GENERATOR).read_bytes()),
        "stem_source": {"path": original.GENERATOR_PATH,
                        "sha256": original.digest((repository / original.GENERATOR_PATH).read_bytes())},
        "seed": SEED, "domain": DOMAIN, "chess_version": chess.__version__,
        "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "selection": "First listed stem in each family; sorted legal UCI moves; unsigned big-endian SHA256 of ASCII domain|seed|stem_id|attempt|tail_ply|draw_counter, rejecting words >= floor(2**256/count)*count; remaining word modulo count. Counters are zero-based.",
        "rejection_policy": "Reject terminal intermediate/final roots with claim_draw=True, duplicate accepted roots, and exposed canonical roots; increment attempt without changing the stem.",
        "canonicalization": original.CANONICALIZATION,
        "base_exclusion": {"path": original.EXCLUSION_MANIFEST, "sha256": original.EXCLUSION_SHA256},
        "additional_excluded_roots": sorted((public | relevant) - base),
        "sources": sources, "public_unique_roots": len(public),
        "saved_game_unique_roots": len(games), "combined_unique_roots": len(public | games),
        "saved_game_overlap_with_accepted": sorted(games & {entry["canonical_root"] for entry in entries}),
        "root_count": 4, "plies_per_root": 20, "white_to_move": 4, "black_to_move": 0,
        "rejections": rejections, "accepted": entries,
        "scope": "Pinned Phase 4D.2 exclusions, every current tests/data JSON opening suite, valid complete six-field FEN literals in tests/*.py, tests/*.cpp and tools/*.py including the read-only owner puzzle runner, plus every saved results/{phase2d-*,phase3g-lmr-*,phase4d2-*}/**/games.jsonl qualification mainline available at creation.",
        "omissions": ["No raw private workbook or owner previous-engine assets reopened.",
                      "Dynamically constructed test positions, unsaved games, and internal/PV search positions are not exhaustive.",
                      "Saved qualification histories are replayed; older synthetic smoke games with null/illegal moves are outside that scope.",
                      "Local game sources are optional for public reproduction; --verify-sources requires all recorded sources and rechecks their hashes and roots."],
    }


def assets(metadata, repository):
    if chess.__version__ != original.REFEREE_VERSION:
        raise ValueError("Requires chess==" + original.REFEREE_VERSION)
    if metadata["generator_sha256"] != original.digest((repository / GENERATOR).read_bytes()):
        raise ValueError("Generator hash mismatch")
    source = metadata["stem_source"]
    if source["sha256"] != original.digest((repository / source["path"]).read_bytes()):
        raise ValueError("Stem source hash mismatch")
    base, _ = original.exclusion_roots(repository)
    entries, rejections = generate(base | set(metadata["additional_excluded_roots"]))
    if entries != metadata["accepted"] or rejections != metadata["rejections"]:
        raise ValueError("Generation replay mismatch")
    return {
        PREFIX + "-{:02d}.json".format(index + 1): original.encoded({
            "schema_version": 1, "description": "Four-worker match readiness shard {} of 4; one color-swapped pair".format(index + 1),
            "license": original.LICENSE, "copyright": original.COPYRIGHT,
            "seed": SEED, "shard": index + 1, "provenance": PROVENANCE,
            "limitations": LIMITATIONS, "generator": GENERATOR,
            "generation_metadata": METADATA, "openings": [entry]})
        for index, entry in enumerate(entries)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--create", action="store_true", help="Create the immutable initial snapshot")
    modes.add_argument("--check", action="store_true", help="Reproduce all four public shards")
    parser.add_argument("--verify-sources", action="store_true", help="Require/replay all recorded local and public sources")
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
        combined = set()
        for source in metadata["sources"]:
            path = args.repository / source["path"]
            if original.digest(path.read_bytes()) != source["sha256"]:
                raise ValueError("Source hash mismatch: " + source["path"])
            keys, count = source_keys(path, source["kind"])
            if (count != source["entries"] or len(keys) != source["unique_roots"]
                    or original.digest(original.encoded(sorted(keys))) != source["canonical_roots_sha256"]):
                raise ValueError("Source replay mismatch: " + source["path"])
            if (source["kind"] == "played-game-histories"
                    and pgn_manifest_digest(path) != source["referenced_pgn_manifest_sha256"]):
                raise ValueError("Referenced PGN digest mismatch: " + source["path"])
            combined.update(keys)
        if combined & {entry["canonical_root"] for entry in metadata["accepted"]}:
            raise ValueError("Accepted root overlaps an exposed source")
    if args.create:
        metadata["shards"] = [{"path": "tests/data/" + name, "sha256": original.digest(data)}
                              for name, data in generated.items()]
        generated[METADATA] = original.encoded(metadata)
        original.write_assets(generated, directory)
    else:
        original.check_assets(generated, directory)
        if metadata["shards"] != [{"path": "tests/data/" + name, "sha256": original.digest(data)}
                                   for name, data in generated.items()]:
            raise ValueError("Shard digest manifest mismatch")
    print("Validated four legal 20-ply roots; no engine or evaluation used.")


if __name__ == "__main__":
    main()
