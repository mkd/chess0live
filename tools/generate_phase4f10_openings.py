#!/usr/bin/env python3
"""Freeze/reproduce fresh Continuation History qualification roots without engines.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Public replay needs only the compact snapshot and pinned helpers. Source replay
additionally verifies all original local PGNs; neither mode evaluates a root.
"""
import argparse
import hashlib
import json
from pathlib import Path

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess

import generate_phase4d2_openings as original
import generate_lmr_20261022_openings as history

SEEDS = (202610284101, 202610284102, 202610284103, 202610284104)
DOMAIN = "phase4f10-continuation-512-v1"
PREFIX = "phase4f10-match"
GENERATOR = "tools/generate_phase4f10_openings.py"
HELPER = "tools/generate_lmr_20261022_openings.py"
METADATA = PREFIX + "-generation.json"
EXCLUSION_MANIFEST = "tests/data/" + PREFIX + "-exclusions.json"
SUITE_NAMES = tuple(PREFIX + "-{:02d}.json".format(n) for n in range(1, 5))
MAX_ATTEMPTS = 10000
# Exclude only this new match's evolving preparation. Completed Phase 4F.7
# match games, Phase 4F.8/9 inputs and parked campaigns remain exposure sources.
PREPARATION_NAMES = frozenset({
    "generate_phase4f10_openings.py", "phase4f10_openings_test.py",
    "qualify_phase4f10.py", "qualify_phase4f10_test.py",
    "audit_phase4f10.py", "audit_phase4f10_test.py",
})
PROVENANCE = (
    "The 64 independently authored chess0live 16-ply stems, four new legal tails "
    "each, chosen by a domain-separated SHA256 stream with one seed per shard. "
    "No engine, evaluation, score, result, material filter, external database or "
    "owner previous-engine asset participates; prior roots are exclusion-only."
)
LIMITATIONS = (
    "The stems have been used before and four tails from each stem are related. "
    "Disjoint final canonical roots do not prove independent or representative "
    "samples. Exclusion covers available declared public roots and saved legal "
    "mainlines, not internal search/PV nodes, unsaved games or all dynamic fixtures."
)


def choose_index(count, seed, stem, variant, attempt, ply):
    """Reject high SHA words before modulo; every input and counter is explicit."""
    if count < 1:
        raise ValueError("Cannot sample an empty move list")
    space, counter = 1 << 256, 0
    while True:
        payload = "|".join(map(str, (DOMAIN, seed, stem, variant, attempt, ply, counter)))
        word = int.from_bytes(hashlib.sha256(payload.encode("ascii")).digest(), "big")
        if word < space - space % count:
            return word % count
        counter += 1


def continuation(stem, variant, attempt, seed):
    """Retain full history, and stop at any terminal intermediate position."""
    board, tail = stem["board"].copy(stack=True), []
    for ply in range(3 if variant < 2 else 4):
        if board.outcome(claim_draw=True) is not None:
            return board, tail, True
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        move = moves[choose_index(len(moves), seed, stem["id"], variant, attempt, ply)]
        board.push(move)
        tail.append(move.uci())
        if board.outcome(claim_draw=True) is not None:
            return board, tail, True
    return board, tail, False


def generate(excluded):
    """Produce four balanced shards; rejection never consults a chess score."""
    used, entries, rejections = set(), [], []
    for stem_index, stem in enumerate(original.parse_stems()):
        for variant in range(4):
            shard = (stem_index % 2) * 2 + variant % 2 + 1
            for attempt in range(MAX_ATTEMPTS):
                board, tail, terminal = continuation(stem, variant, attempt, SEEDS[shard - 1])
                key = original.canonical_root(board)
                reason = ("terminal" if terminal else "duplicate" if key in used
                          else "exposed" if key in excluded else None)
                if reason:
                    rejections.append({"stem_id": stem["id"], "variant": variant,
                                       "attempt": attempt, "reason": reason, "root_key": key})
                    continue
                if not board.is_valid() or len(stem["moves"] + tail) != (19 if variant < 2 else 20):
                    raise ValueError("Invalid generated history")
                used.add(key)
                entries.append({"id": PREFIX + "-{}-v{}".format(stem["id"], variant),
                                "stem_id": stem["id"], "variant": variant, "shard": shard,
                                "moves": stem["moves"] + tail, "final_fen": board.fen(),
                                "canonical_root": key, "accepted_attempt": attempt})
                break
            else:
                raise ValueError("Attempt limit reached")
    return entries, rejections


def source_specs(repository):
    """Freeze prior public inputs and all available project PGN directories.

    This phase's evolving preparation files must not become circular sources.
    Current full-history profiling commands are replayed explicitly: a FEN-only
    scan alone would miss their resulting roots. Malformed test FENs are skipped
    by the pinned legal-literal extractor, never treated as valid positions.
    """
    specs = [(original.EXCLUSION_MANIFEST, "canonical-catalog"),
             ("tools/bench.py", "benchmark-constant")]
    for path in sorted((repository / "tests/data").glob("*.json")):
        if PREFIX in path.name or path.name in PREPARATION_NAMES:
            continue
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("openings"), list):
            specs.append((str(path.relative_to(repository)), "opening-suite"))
        roots = data.get("roots")
        if (isinstance(roots, list) and roots
                and all(isinstance(row, dict) and "root_key" in row for row in roots)
                and str(path.relative_to(repository)) != original.EXCLUSION_MANIFEST):
            specs.append((str(path.relative_to(repository)), "canonical-catalog"))
        positions = data.get("positions")
        if (isinstance(positions, list) and positions
                and all(isinstance(row, dict) and ("fen" in row or "position" in row) for row in positions)):
            specs.append((str(path.relative_to(repository)), "json-positions"))
    for directory in ("tests", "tools"):
        for path in sorted((repository / directory).rglob("*")):
            if (path.suffix not in (".py", ".cpp", ".hpp", ".json")
                    or PREFIX in path.name or path.name in PREPARATION_NAMES):
                continue
            try:
                original.source_roots(path, "valid-fen-literals")
            except ValueError as error:
                if str(error).startswith("Empty exclusion source:"):
                    continue
                raise
            specs.append((str(path.relative_to(repository)), "valid-fen-literals"))
    specs += [(str(directory.relative_to(repository)), "saved-pgn-directory")
              for directory in sorted({path.parent for path in (repository / "results").rglob("*.pgn")})
              if not any(PREFIX in part for part in directory.relative_to(repository).parts)]
    return specs


def pin(repository, relative):
    return {"path": relative, "sha256": original.digest((repository / relative).read_bytes())}


def snapshot(repository):
    base, _ = original.exclusion_roots(repository)
    public, games, sources = set(base), set(), []
    for relative, kind in source_specs(repository):
        keys, record = history.source_record(repository, relative, kind)
        (games if kind == "saved-pgn-directory" else public).update(keys)
        sources.append(record)
    entries, rejections = generate(public | games)
    relevant = {row["root_key"] for row in rejections if row["reason"] == "exposed"}
    return {
        "schema_version": 1, "license": original.LICENSE, "copyright": original.COPYRIGHT,
        "generator": GENERATOR, "generator_sha256": pin(repository, GENERATOR)["sha256"],
        "stem_source": pin(repository, original.GENERATOR_PATH), "history_helper": pin(repository, HELPER),
        "seeds": list(SEEDS), "domain": DOMAIN, "chess_version": chess.__version__,
        "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "selection": "64 stems in original order, four variants each; sorted legal UCI moves. SHA256 ASCII domain|shard_seed|stem_id|variant|attempt|tail_ply|draw_counter; unsigned big-endian word; reject >= floor(2**256/count)*count then modulo count. Zero-based counters; variants 0-1 add three plies; 2-3 add four.",
        "sharding": "(stem_index % 2)*2 + variant%2 + 1; each shard has 64 roots, 32 per side, families e4:24 d4:24 c4:8 Nf3:8",
        "rejection_policy": "Reject terminal intermediate/final positions (claim_draw=True), duplicate accepted roots and exposed canonical roots, then increment attempt.",
        "canonicalization": original.CANONICALIZATION,
        "base_exclusion": {"path": original.EXCLUSION_MANIFEST, "sha256": original.EXCLUSION_SHA256},
        "additional_excluded_roots": sorted((public | relevant) - base), "sources": sources,
        "public_unique_roots": len(public), "saved_game_unique_roots": len(games),
        "combined_unique_roots": len(public | games),
        "saved_game_overlap_with_accepted": sorted(games & {row["canonical_root"] for row in entries}),
        "root_count": 256, "white_to_move": 128, "black_to_move": 128,
        "root_plies": {"19": 128, "20": 128}, "rejections": rejections, "accepted": entries,
        "scope": "Pinned inherited catalog; all prior tests/data opening suites and declared position lists; benchmark constants; legal six-field FEN literals recursively in tests/tools Python, C++, headers and JSON; every available project results PGN mainline including October 22 LMR, completed Phase4F7 match, smoke/manual games and legal prefixes of synthetic malformed records. Only the new Phase4F10 match preparation files are excluded from source discovery; prior Phase4F7 match roots/games, Phase4F8 development roots, Phase4F9 puzzles and parked Phase4F3 match roots remain included.",
        "omissions": [
            "Owner workbook and previous-engine assets are not reopened; previously cataloged workbook roots remain inherited.",
            "Internal search/PV nodes, unsaved games and dynamically constructed fixtures are not exhaustive.",
            "Malformed PGNs contribute only legal prefixes; invalid initial positions contribute none. Source records list each omission.",
            "Local games are not redistributed; compact replay retains public roots and rejected exposed candidates. Full saved-game disjointness requires --verify-sources with original local files."]}


def assets(metadata, repository):
    """Regenerate immutable bytes from compact exclusions, without local games."""
    if chess.__version__ != original.REFEREE_VERSION:
        raise ValueError("Requires chess==" + original.REFEREE_VERSION)
    if (metadata.get("seeds") != list(SEEDS) or metadata.get("domain") != DOMAIN
            or metadata.get("chess_version") != original.REFEREE_VERSION
            or metadata.get("base_exclusion") != {"path": original.EXCLUSION_MANIFEST, "sha256": original.EXCLUSION_SHA256}):
        raise ValueError("Frozen generation policy mismatch")
    if metadata["generator_sha256"] != pin(repository, GENERATOR)["sha256"]:
        raise ValueError("Generator hash mismatch")
    for field, path in (("stem_source", original.GENERATOR_PATH), ("history_helper", HELPER)):
        if metadata[field] != pin(repository, path):
            raise ValueError("Helper hash mismatch: " + path)
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
        "schema_version": 1, "description": "Continuation History qualification shard {} of 4; 64 color-swapped pairs".format(index + 1),
        "license": original.LICENSE, "copyright": original.COPYRIGHT, "seed": SEEDS[index],
        "domain": DOMAIN, "shard": index + 1, "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "generator": GENERATOR, "generation_metadata": METADATA,
        "openings": [row for row in entries if row["shard"] == index + 1]})
        for index, name in enumerate(SUITE_NAMES)}
    files[Path(EXCLUSION_MANIFEST).name] = original.encoded({
        "schema_version": 1, "license": original.LICENSE, "copyright": original.COPYRIGHT,
        "canonicalization": original.CANONICALIZATION,
        "scope": "Inherited/public roots and rejected exposed candidates; not all saved-game roots.",
        "limitations": LIMITATIONS + " Full source replay is needed for saved-game disjointness.",
        "generation_metadata": METADATA, "unique_roots": len(base | set(extra)),
        "roots": [{"root_key": root} for root in sorted(base | set(extra))]})
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--create", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--verify-sources", action="store_true", help="Replay every recorded source with original bytes")
    args = parser.parse_args()
    repository = args.repository.resolve()
    directory, metadata_path = repository / "tests/data", repository / "tests/data" / METADATA
    if args.create and metadata_path.exists():
        parser.error("Snapshot already exists")
    metadata = snapshot(repository) if args.create else json.loads(metadata_path.read_text())
    generated = assets(metadata, repository)
    if args.verify_sources:
        history.verify_sources(metadata, repository)
    shards = [{"path": "tests/data/" + name, "sha256": original.digest(generated[name]), "roots": 64}
              for name in SUITE_NAMES]
    exclusion = {"path": EXCLUSION_MANIFEST, "sha256": original.digest(generated[Path(EXCLUSION_MANIFEST).name])}
    if args.create:
        metadata.update(shards=shards, exclusion_manifest=exclusion)
        generated[METADATA] = original.encoded(metadata)
        original.write_assets(generated, directory)
    else:
        original.check_assets(generated, directory)
        if metadata["shards"] != shards or metadata["exclusion_manifest"] != exclusion:
            raise ValueError("Shard digest manifest mismatch")
    print("Validated 256 legal unevaluated roots; four balanced shards; 128 roots per side.")


if __name__ == "__main__":
    main()
