#!/usr/bin/env python3
"""Reproduce the original, unevaluated Phase 3G full-history opening shards.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The constants and policy below were authored before generating any continuations.
Only python-chess legality and terminal checks are used: no engine is invoked.
Run with Python 3 and chess==1.11.2. --check regenerates bytes in memory;
--output-dir writes missing assets but refuses to overwrite different contents.
"""
import argparse
import hashlib
import json
from pathlib import Path

import chess


SEED = 20261018
REFEREE_VERSION = "1.11.2"
MAX_ATTEMPTS = 10000
DOMAIN = "chess0live.phase3g.openings.v1"
LICENSE = "GPL-3.0-or-later"
COPYRIGHT = "Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>"
GENERATOR_PATH = "tools/generate_phase3g_openings.py"
METADATA_NAME = "openings-phase3g-generation.json"
SUITE_NAMES = tuple("openings-phase3g-{}.json".format(i) for i in range(1, 5))
EXCLUSION_PATHS = (
    "tests/data/openings-development.json",
    "tests/data/openings-validation.json",
    "tests/data/openings-time-validation.json",
    "tests/data/openings-lmr-validation.json",
    "tests/data/performance-gamephases.json",
)
PROVENANCE = (
    "Original 16-ply stems authored directly for chess0live from ordinary chess "
    "patterns before generating tails; no external game database, prior owner "
    "engine assets, engine search, evaluation, or outcome selection. Earlier "
    "chess0live suites are read only to exclude already exposed final roots."
)
LIMITATIONS = (
    "Stems and their eight continuations are related. SHA-256 selection is "
    "deterministic pseudorandom selection, not proof of independent samples. "
    "Moves are sampled uniformly from sorted legal moves before the documented "
    "terminal/duplicate/overlap rejection. No material or evaluation filter is "
    "applied; balance, representativeness, and independent pair outcomes are "
    "unproven assumptions. Full histories retain all earlier repetition state."
)

# Independently composed chess sequences, not copied from a suite or game asset.
# Each eight-move stem has exactly 16 plies. SAN here is only authoring notation;
# generated suites preserve every move as UCI text from the initial position.
STEMS = (
    ("e4-01", "Ruy Lopez development", "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O"),
    ("e4-02", "Italian development", "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O Re1 a6 Bb3 Ba7"),
    ("e4-03", "Scotch central exchange", "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nc3 Bb4 Nxc6 bxc6 Bd3 d5 exd5 cxd5"),
    ("e4-04", "Petrov development", "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Bd6 O-O O-O c4 c6"),
    ("e4-05", "Philidor development", "e4 e5 Nf3 d6 d4 Nf6 Nc3 Nbd7 Bc4 Be7 O-O O-O Re1 c6 a4 Qc7"),
    ("e4-06", "Sicilian a6 structure", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5 Nb3 Be7 O-O O-O"),
    ("e4-07", "Sicilian fianchetto", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6"),
    ("e4-08", "Sicilian e5 structure", "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5 Ndb5 d6 Bg5 a6 Na3 b5"),
    ("e4-09", "French central space", "e4 e6 d4 d5 Nc3 Nf6 Bg5 Be7 e5 Nfd7 Bxe7 Qxe7 f4 c5 Nf3 Nc6"),
    ("e4-10", "Caro-Kann bishop development", "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 Nf3 Nd7 h5 Bh7"),
    ("e4-11", "Pirc closed center", "e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7 Be2 O-O O-O Nc6 Be3 e5 d5 Ne7"),
    ("e4-12", "Scandinavian development", "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 c6 Nf3 Nf6 Bc4 Bf5 O-O e6 Re1 Nbd7"),
    ("d4-01", "Queen's Gambit declined", "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6 Bd3 Bb7"),
    ("d4-02", "Slav pawn recovery", "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4 O-O Nbd7"),
    ("d4-03", "Semi-Slav development", "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5 Bd3 Bb7"),
    ("d4-04", "Queen's Gambit accepted", "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6 Qe2 b5 Bb3 Bb7"),
    ("d4-05", "Nimzo-Indian exchange", "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3"),
    ("d4-06", "Queen's Indian development", "d4 Nf6 c4 e6 Nf3 b6 g3 Bb7 Bg2 Be7 O-O O-O Nc3 Ne4 Qc2 Nxc3"),
    ("d4-07", "King's Indian center", "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7"),
    ("d4-08", "Grunfeld central exchange", "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Nf3 c5 Be3 Qa5"),
    ("d4-09", "Benoni structure", "d4 Nf6 c4 c5 d5 e6 Nc3 exd5 cxd5 d6 e4 g6 Nf3 Bg7 Be2 O-O"),
    ("d4-10", "Dutch fianchetto", "d4 f5 c4 Nf6 g3 g6 Bg2 Bg7 Nf3 O-O O-O d6 Nc3 Qe8 d5 Na6"),
    ("d4-11", "Tarrasch central structure", "d4 d5 c4 e6 Nc3 c5 cxd5 exd5 Nf3 Nc6 g3 Nf6 Bg2 Be7 O-O O-O"),
    ("d4-12", "Catalan pawn recovery", "d4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4 Qc2 a6 Qxc4 b5"),
    ("c4-01", "Symmetrical English", "c4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7 Nf3 Nf6 O-O O-O d3 d6 Rb1 Rb8"),
    ("c4-02", "English e5 structure", "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 Bb4 Bg2 O-O O-O e4 Ng5 Bxc3 bxc3 Re8"),
    ("c4-03", "English central exchanges", "c4 Nf6 Nc3 e6 Nf3 b6 e4 Bb7 e5 Ne4 Nxe4 Bxe4 d4 Bb4+ Bd2 Bxd2+"),
    ("c4-04", "English queen-pawn transition", "c4 e6 Nc3 d5 d4 Nf6 cxd5 exd5 Bg5 Be7 e3 O-O Bd3 Nbd7 Nge2 c6"),
    ("nf3-01", "King's Indian attack structure", "Nf3 d5 g3 Nf6 Bg2 e6 O-O Be7 d3 O-O Nbd2 c5 e4 Nc6 Re1 b6"),
    ("nf3-02", "Double fianchetto development", "Nf3 Nf6 c4 g6 b3 Bg7 Bb2 O-O g3 d6 Bg2 e5 O-O Nc6 d3 a5"),
    ("nf3-03", "Reti queenside space", "Nf3 d5 c4 d4 b4 Bg4 Ne5 Bh5 g3 Nd7 Nxd7 Qxd7 Bg2 e5 O-O Nf6"),
    ("nf3-04", "Reti open center", "Nf3 c5 c4 Nc6 Nc3 g6 e3 Bg7 d4 cxd4 exd4 d6 Be2 Nf6 O-O O-O"),
)


def encoded(value):
    """Stable UTF-8 JSON bytes, independent of host paths, time, and Python RNG."""
    return (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def digest(contents):
    return hashlib.sha256(contents).hexdigest()


def canonical_root(board):
    """Normalize placement/turn/castling/legal-EP, deliberately excluding clocks."""
    return " ".join(board.fen(en_passant="legal").split()[:4])


def parse_stems():
    result, roots, identifiers = [], set(), set()
    for identifier, label, text in STEMS:
        board, moves = chess.Board(), []
        for san in text.split():
            if board.outcome(claim_draw=True) is not None:
                raise ValueError("Terminal stem: " + identifier)
            move = board.parse_san(san)
            moves.append(move.uci())
            board.push(move)
        key = canonical_root(board)
        if len(moves) != 16 or not board.is_valid() or board.outcome(claim_draw=True) is not None:
            raise ValueError("Invalid 16-ply stem: " + identifier)
        if key in roots or identifier in identifiers:
            raise ValueError("Duplicate stem: " + identifier)
        roots.add(key)
        identifiers.add(identifier)
        result.append({"id": identifier, "label": label, "san": text.split(),
                       "moves": moves, "root_fen": board.fen(), "board": board})
    families = [entry["moves"][0] for entry in result]
    if (len(result) != 32 or families.count("e2e4") != 12 or families.count("d2d4") != 12
            or families.count("c2c4") != 4 or families.count("g1f3") != 4):
        raise ValueError("Stem count/family allocation differs from the frozen design")
    return result


def exclusion_roots(repository):
    """Previous roots are exclusions only; never use their moves as source stems."""
    roots, records = set(), []
    for relative in EXCLUSION_PATHS:
        contents = (repository / relative).read_bytes()
        entries = json.loads(contents)["openings"]
        for entry in entries:
            board = chess.Board(entry.get("fen", chess.STARTING_FEN))
            for move in entry.get("moves", []):
                board.push_uci(move)
            if not board.is_valid():
                raise ValueError("Invalid excluded root in " + relative)
            roots.add(canonical_root(board))
        records.append({"path": relative, "sha256": digest(contents), "entries": len(entries)})
    return roots, records


def choose_index(count, seed, stem, variant, attempt, tail_ply):
    """Unbiased bounded selection from a deterministic SHA-256 word stream.

    Hash the ASCII DOMAIN|seed|stem|variant|attempt|tail_ply|draw_counter, interpret
    the digest as an unsigned big-endian 256-bit integer, and reject words >=
    floor(2**256/count)*count. A rejected word increments only draw_counter.
    """
    if count < 1:
        raise ValueError("Cannot sample an empty move list")
    space = 1 << 256
    limit = space - space % count
    counter = 0
    while True:
        payload = "|".join(map(str, (DOMAIN, seed, stem, variant, attempt, tail_ply, counter)))
        value = int.from_bytes(hashlib.sha256(payload.encode("ascii")).digest(), "big")
        if value < limit:
            return value % count, counter
        counter += 1


def continuation(stem, variant, attempt, seed):
    board = stem["board"].copy(stack=True)
    tail, word_rejections = [], 0
    for tail_ply in range(3 if variant < 4 else 4):
        if board.outcome(claim_draw=True) is not None:
            return board, tail, word_rejections, True
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        index, rejected = choose_index(len(moves), seed, stem["id"], variant, attempt, tail_ply)
        word_rejections += rejected
        move = moves[index]
        board.push(move)
        tail.append(move.uci())
        # Check every intermediate tail position, not just the accepted root.
        if board.outcome(claim_draw=True) is not None:
            return board, tail, word_rejections, True
    return board, tail, word_rejections, False


def generate(repository, seed=SEED):
    if seed != SEED:
        raise ValueError("Phase 3G is frozen to seed {}".format(SEED))
    if chess.__version__ != REFEREE_VERSION:
        raise ValueError("Require chess=={}; found {}".format(REFEREE_VERSION, chess.__version__))
    stems = parse_stems()
    excluded, exclusion_records = exclusion_roots(Path(repository))
    used, shards, slots = set(), [[] for _ in range(4)], []
    totals = {"terminal": 0, "duplicate": 0, "prior_overlap": 0, "sha256_words": 0}
    for stem in stems:
        for variant in range(8):
            rejections = []
            for attempt in range(MAX_ATTEMPTS):
                board, tail, rejected_words, terminal = continuation(stem, variant, attempt, seed)
                totals["sha256_words"] += rejected_words
                key = canonical_root(board)
                reason = ("terminal" if terminal else "duplicate" if key in used
                          else "prior_overlap" if key in excluded else None)
                if reason:
                    totals[reason] += 1
                    rejections.append({"attempt": attempt, "reason": reason,
                                       "tail": tail, "canonical_root": key})
                    continue
                used.add(key)
                identifier = "phase3g-{}-v{}".format(stem["id"], variant)
                shards[variant % 4].append({
                    "id": identifier, "stem_id": stem["id"], "variant": variant,
                    "moves": stem["moves"] + tail, "final_fen": board.fen(),
                    "canonical_root": key, "accepted_attempt": attempt,
                })
                slots.append({"id": identifier, "shard": variant % 4 + 1,
                              "accepted_attempt": attempt, "rejections": rejections})
                break
            else:
                raise ValueError("Attempt limit reached for {} variant {}".format(stem["id"], variant))
    files = {}
    for index, entries in enumerate(shards):
        if len(entries) != 64:
            raise ValueError("Shard size mismatch")
        files[SUITE_NAMES[index]] = encoded({
            "schema_version": 1, "description": "Phase 3G frozen opening shard {} of 4".format(index + 1),
            "license": LICENSE, "copyright": COPYRIGHT,
            "seed": seed, "shard": index + 1, "provenance": PROVENANCE,
            "limitations": LIMITATIONS, "generator": GENERATOR_PATH,
            "generation_metadata": METADATA_NAME, "openings": entries,
        })
    metadata = {
        "schema_version": 1, "license": LICENSE, "copyright": COPYRIGHT,
        "generator": GENERATOR_PATH, "seed": seed, "chess_version": chess.__version__,
        "provenance": PROVENANCE, "limitations": LIMITATIONS,
        "policy": {
            "domain": DOMAIN, "stem_plies": 16, "stems": 32, "variants_per_stem": 8,
            "families": {"e4": 12, "d4": 12, "c4": 4, "Nf3": 4},
            "root_plies": {"variants_0_to_3": 19, "variants_4_to_7": 20},
            "sharding": "variant % 4 + 1; stem order, then ascending variants within each stem",
            "selection": "Sorted legal UCI moves; SHA256 ASCII domain|seed|stem|variant|attempt|tail_ply|draw_counter; big-endian 256-bit word; reject >= floor(2**256/count)*count, then word % count",
            "counters": "variant, attempt, tail_ply, draw_counter are zero-based",
            "rejections": ["terminal anywhere in tail (outcome with claim_draw=True)",
                           "duplicate accepted canonical four-field root", "prior excluded canonical four-field root"],
            "canonical_root": "board.fen(en_passant='legal') first four fields",
            "maximum_attempts_per_slot": MAX_ATTEMPTS,
            "no_evaluation_material_or_balance_filter": True,
        },
        "excluded_suites": exclusion_records, "excluded_unique_roots": len(excluded),
        "stems": [{key: value for key, value in stem.items() if key != "board"} for stem in stems],
        "root_count": len(used), "white_to_move": 128, "black_to_move": 128,
        "rejection_totals": totals, "slots": slots,
        "shards": [{"path": "tests/data/" + name, "sha256": digest(contents), "roots": 64}
                   for name, contents in files.items()],
    }
    files[METADATA_NAME] = encoded(metadata)
    return files


def write_assets(files, directory):
    """Preflight every destination, then create only missing files exclusively."""
    directory = Path(directory)
    for name, contents in files.items():
        path = directory / name
        if path.exists() and path.read_bytes() != contents:
            raise ValueError("Refusing to overwrite different asset: " + str(path))
    directory.mkdir(parents=True, exist_ok=True)
    for name, contents in files.items():
        path = directory / name
        if not path.exists():
            with path.open("xb") as output:
                output.write(contents)


def check_assets(files, directory):
    for name, contents in files.items():
        path = Path(directory) / name
        if not path.is_file() or path.read_bytes() != contents:
            raise ValueError("Reproduction mismatch: " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="Compare regenerated bytes to tracked assets")
    modes.add_argument("--output-dir", type=Path, help="Write assets without overwriting changed files")
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--seed", type=int, default=SEED, help="Frozen seed; other values are rejected")
    args = parser.parse_args()
    try:
        files = generate(args.repository, args.seed)
        if args.check:
            check_assets(files, args.repository / "tests/data")
        else:
            write_assets(files, args.output_dir)
    except (ValueError, OSError) as error:
        parser.exit(1, "Phase 3G generation failed: {}\n".format(error))
    print(json.dumps({"status": "PASS", "mode": "check" if args.check else "generate",
                      "seed": args.seed, "sha256": {name: digest(contents) for name, contents in files.items()}}, indent=2))


if __name__ == "__main__":
    main()
