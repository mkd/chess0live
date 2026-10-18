#!/usr/bin/env python3
"""Reproduce the original, unevaluated Phase 3L full-history opening shards.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The constants and policy below were authored before generating any continuations.
Only python-chess legality and terminal checks are used: no engine is invoked.
Run with Python 3 and chess==1.11.2. --check regenerates bytes in memory;
--output-dir writes missing assets but refuses to overwrite different contents.
"""
import argparse
import ast
import re
import hashlib
import json
from pathlib import Path

import chess


SEED = 2026101818
REFEREE_VERSION = "1.11.2"
MAX_ATTEMPTS = 10000
DOMAIN = "chess0live.phase3l.openings.v1"
LICENSE = "GPL-3.0-or-later"
COPYRIGHT = "Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>"
GENERATOR_PATH = "tools/generate_phase3l_openings.py"
METADATA_NAME = "phase3l-generation.json"
SUITE_NAMES = tuple("phase3l-lmr-{:02d}.json".format(i) for i in range(1, 5))
EXCLUSION_MANIFEST = "tests/data/phase3l-exclusions.json"
EXCLUSION_SHA256 = "f645aafc49d6dee36c8b1b492a0b3fa67665713281a68453f48be4b354ddd9d9"

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
    ('e4-01', 'Vienna fianchetto', 'e4 e5 Nc3 Nc6 g3 g6 Bg2 Bg7 d3 d6 Nge2 Nge7 O-O O-O Be3 Be6'),
    ('e4-02', 'Bishop opening development', 'e4 e5 Bc4 Nf6 d3 Nc6 Nf3 Bc5 O-O d6 c3 O-O Re1 Bb6 Nbd2 a6'),
    ('e4-03', "King's gambit exchange", 'e4 e5 f4 exf4 Nf3 d6 d4 g5 h4 g4 Ng5 h6 Nxf7 Kxf7 Bxf4 Nf6'),
    ('e4-04', 'Scotch gambit development', 'e4 e5 Nf3 Nc6 d4 exd4 Bc4 Bc5 c3 d6 cxd4 Bb4+ Nc3 Nf6 O-O O-O'),
    ('e4-05', 'Closed Sicilian fianchetto', 'e4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7 d3 d6 Be3 e6 Qd2 Nge7 Nge2 O-O'),
    ('e4-06', 'Sicilian e6 development', 'e4 c5 Nf3 e6 d4 cxd4 Nxd4 a6 Nc3 Qc7 Bd3 Nc6 Be3 Nf6 O-O Be7'),
    ('e4-07', 'Sicilian c3 center', 'e4 c5 c3 d5 exd5 Qxd5 d4 Nf6 Nf3 e6 Be2 Be7 O-O O-O Be3 Nc6'),
    ('e4-08', 'French open center', 'e4 e6 d4 d5 Nd2 c5 Ngf3 Nc6 exd5 exd5 Bb5 Bd6 O-O Nge7 dxc5 Bxc5'),
    ('e4-09', 'Caro-Kann advance', 'e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2 Nd7 O-O Ne7 Nbd2 h6 Nb3 Bh7'),
    ('e4-10', 'Pirc f4 center', 'e4 d6 d4 g6 Nc3 Bg7 f4 Nf6 Nf3 O-O Bd3 Na6 O-O c5 d5 Nc7'),
    ('e4-11', 'Alekhine development', 'e4 Nf6 e5 Nd5 d4 d6 Nf3 Bg4 Be2 e6 O-O Be7 c4 Nb6 Nc3 O-O'),
    ('e4-12', 'Scandinavian fianchetto', 'e4 d5 exd5 Nf6 d4 Nxd5 Nf3 g6 Be2 Bg7 O-O O-O c4 Nb6 Nc3 Nc6'),
    ('d4-01', 'Queen-pawn bishop development', 'd4 d5 Nf3 Nf6 Bf4 e6 e3 Bd6 Bxd6 Qxd6 c3 O-O Bd3 c5 O-O Nc6'),
    ('d4-02', 'Queen-pawn c3 center', 'd4 d5 Nf3 Nf6 e3 e6 Bd3 c5 c3 Nc6 O-O Bd6 Nbd2 O-O Re1 b6'),
    ('d4-03', "Queen's gambit h3 development", 'd4 d5 c4 e6 Nf3 Nf6 Nc3 Be7 e3 O-O Bd3 dxc4 Bxc4 c5 O-O Nc6'),
    ('d4-04', 'Slav kingside fianchetto', 'd4 d5 c4 c6 Nf3 Nf6 g3 Bf5 Bg2 e6 O-O Be7 Nc3 O-O Qb3 Qb6'),
    ('d4-05', 'Nimzo-Indian queen development', 'd4 Nf6 c4 e6 Nc3 Bb4 Qc2 O-O a3 Bxc3+ Qxc3 b6 Nf3 Bb7 e3 d6'),
    ('d4-06', "Queen's Indian e3 center", 'd4 Nf6 c4 e6 Nf3 b6 e3 Bb7 Bd3 d5 O-O Bd6 Nc3 O-O Qe2 Nbd7'),
    ('d4-07', "King's Indian fianchetto", 'd4 Nf6 c4 g6 Nf3 Bg7 g3 O-O Bg2 d6 O-O Nbd7 Nc3 e5 e4 c6'),
    ('d4-08', 'Grunfeld fianchetto', 'd4 Nf6 c4 g6 g3 d5 Bg2 Bg7 Nf3 O-O O-O c6 Qb3 Qb6 Nc3 dxc4'),
    ('d4-09', 'Benko pawn advance', 'd4 Nf6 c4 c5 d5 b5 cxb5 a6 bxa6 Bxa6 Nc3 d6 Nf3 g6 e4 Bxf1'),
    ('d4-10', 'Dutch stonewall', 'd4 f5 g3 Nf6 Bg2 e6 Nf3 d5 O-O Bd6 c4 c6 Nc3 O-O Qc2 Qe8'),
    ('d4-11', 'Chigorin central pressure', 'd4 d5 c4 Nc6 Nf3 Bg4 Nc3 e6 e3 Nf6 Be2 Be7 O-O O-O h3 Bh5'),
    ('d4-12', 'Old Indian development', 'd4 Nf6 c4 d6 Nc3 e5 Nf3 Nbd7 e4 Be7 Be2 O-O O-O c6 Be3 Qc7'),
    ('c4-01', 'English kingside structure', 'c4 e5 g3 Nf6 Bg2 Bc5 Nc3 O-O Nf3 d6 O-O Nc6 d3 a6 Rb1 Ba7'),
    ('c4-02', 'English symmetrical bishops', 'c4 c5 Nf3 Nf6 Nc3 Nc6 e3 e6 d4 d5 cxd5 exd5 Bb5 Bd6 O-O O-O'),
    ('c4-03', 'English queenside fianchetto', 'c4 e6 g3 d5 Bg2 Nf6 Nf3 Be7 O-O O-O b3 b6 Bb2 Bb7 d3 c5'),
    ('c4-04', 'English reversed center', 'c4 e5 Nc3 Bb4 Nd5 Bc5 e3 Nf6 d4 exd4 exd4 Nxd5 dxc5 Nf6 Nf3 O-O'),
    ('nf3-01', 'Reti early queenside fianchetto', 'Nf3 d5 b3 Nf6 Bb2 e6 e3 Be7 c4 O-O Nc3 c5 cxd5 exd5 d4 Nc6'),
    ('nf3-02', 'Reti d3 development', 'Nf3 Nf6 g3 d5 Bg2 c6 O-O Bf5 d3 e6 Nbd2 Be7 Qe1 O-O e4 Bg6'),
    ('nf3-03', 'Reti queen-pawn exchange', 'Nf3 d5 c4 c6 g3 Nf6 Bg2 Bg4 O-O e6 d4 Nbd7 Nc3 Be7 cxd5 exd5'),
    ('nf3-04', 'Reti symmetrical fianchetto', 'Nf3 c5 g3 Nc6 Bg2 g6 O-O Bg7 c4 Nf6 Nc3 O-O d4 cxd4 Nxd4 d6'),
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


def exclusion_roots(repository, verify_sources=False):
    """Read the pinned public root catalog; private source files are not needed.

    Generation depends only on the pinned canonical manifest. Explicit source
    auditing verifies and replays available original evidence; tracked sources
    must exist in that mode. Later fixture revisions do not alter or invalidate
    immutable held-out inputs. Missing local artifacts remain recorded limits.
    """
    repository = Path(repository)
    contents = (repository / EXCLUSION_MANIFEST).read_bytes()
    if digest(contents) != EXCLUSION_SHA256:
        raise ValueError("Exclusion manifest hash mismatch")
    document = json.loads(contents)
    if document.get("schema_version") != 1 or document.get("canonicalization") != CANONICALIZATION:
        raise ValueError("Unsupported exclusion manifest")
    sources = document.get("sources", [])
    if not sources or [source.get("id") for source in sources] != list(range(len(sources))):
        raise ValueError("Invalid source identities")
    roots, by_source = set(), {index: set() for index in range(len(sources))}
    for entry in document.get("roots", []):
        key, references = entry.get("root_key"), entry.get("sources")
        if not isinstance(key, str) or len(key.split()) != 4:
            raise ValueError("Malformed canonical root")
        board = chess.Board(key + " 0 1")
        if not board.is_valid() or canonical_root(board) != key or key in roots:
            raise ValueError("Duplicate or noncanonical exclusion root")
        if (not isinstance(references, list) or not references
                or any(type(index) is not int or index not in by_source for index in references)
                or references != sorted(set(references))):
            raise ValueError("Invalid root provenance")
        roots.add(key)
        for index in references:
            by_source[index].add(key)
    if len(roots) != document.get("unique_roots") or not roots:
        raise ValueError("Exclusion root count mismatch")
    for source in sources:
        path = repository / source["path"]
        if source.get("availability") not in ("tracked", "local") or not source["path"].startswith(("tools/", "tests/", "results/")) or ".." in Path(source["path"]).parts:
            raise ValueError("Invalid exclusion source path")
        if len(by_source[source["id"]]) != source["unique_roots"]:
            raise ValueError("Exclusion source root count mismatch")
        if not verify_sources:
            continue
        if path.exists():
            if digest(path.read_bytes()) != source["sha256"]:
                raise ValueError("Exclusion source hash mismatch: " + source["path"])
            parsed = source_roots(path, source["kind"])
            if len(parsed) != source["entries"] or set(parsed) != by_source[source["id"]]:
                raise ValueError("Exclusion source replay mismatch: " + source["path"])
        elif source["availability"] == "tracked":
            raise ValueError("Required exclusion source missing: " + source["path"])
    return roots, sources


CANONICALIZATION = "board.fen(en_passant='legal') first four fields; no clocks"


def command_board(body):
    """Strictly replay a saved UCI position body; reject null and illegal moves."""
    tokens = body.split()
    if tokens[:1] == ["position"]:
        tokens = tokens[1:]
    if tokens[:1] == ["startpos"]:
        board, remaining = chess.Board(), tokens[1:]
    elif tokens[:1] == ["fen"] and len(tokens) >= 7:
        board, remaining = chess.Board(" ".join(tokens[1:7])), tokens[7:]
    else:
        board, remaining = chess.Board(" ".join(tokens)), []
    if remaining:
        if remaining[0] != "moves" or len(remaining) == 1:
            raise ValueError("Malformed saved move history")
        for text in remaining[1:]:
            move = chess.Move.from_uci(text)
            if move not in board.legal_moves:
                raise ValueError("Illegal saved move")
            board.push(move)
    if not board.is_valid():
        raise ValueError("Invalid saved position")
    return board


def source_roots(path, kind):
    """Extract only declared root records, never engine scores or search trees."""
    text = path.read_text()
    bodies = []
    if kind == "opening-suite":
        for entry in json.loads(text)["openings"]:
            body = "fen " + entry["fen"] if "fen" in entry else "startpos"
            if entry.get("moves"):
                body += " moves " + " ".join(entry["moves"])
            bodies.append(body)
    elif kind == "clock-cases":
        for entry in json.loads(text)["cases"]:
            body = entry["position_command"]
            if command_board(body).fen() != entry["final_fen"]:
                raise ValueError("Clock case history disagrees with final FEN")
            bodies.append(body)
    elif kind in ("json-positions", "console-verification"):
        data = json.loads(text)
        for entry in data["positions"]:
            bodies.append(entry["fen"] if "fen" in entry else entry["position"])
        if kind == "console-verification":
            bodies.extend(entry["position"] for entry in data["searches"])
    elif kind == "position-lines":
        bodies = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    elif kind == "benchmark-constant":
        for node in ast.parse(text).body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "POSITIONS" for target in node.targets):
                bodies = ast.literal_eval(node.value)
                break
        if not bodies:
            raise ValueError("Missing benchmark POSITIONS literal")
    elif kind == "valid-fen-literals":
        # Diagnostic tests deliberately contain malformed FENs. Catalog only
        # syntactically complete six-field literals accepted by the referee;
        # rejected literals are malformed-input tests, not searched roots.
        pattern = r"(?<![A-Za-z0-9/])(?:[prnbqkPRNBQK1-8]+/){7}[prnbqkPRNBQK1-8]+ [wb] (?:-|[KQkq]+) (?:-|[a-h][36]) [0-9]+ [0-9]+"
        for match in re.finditer(pattern, text):
            try:
                board = command_board(match.group())
            except ValueError:
                continue
            bodies.append(board.fen())
    else:
        raise ValueError("Unknown exclusion source kind: " + kind)
    if not bodies:
        raise ValueError("Empty exclusion source: " + str(path))
    return [canonical_root(command_board(body)) for body in bodies]


# Catalog scope is frozen before continuation generation. It is intentionally
# explicit: new files appearing in results/ cannot change a held-out suite.
SOURCE_SPECS = (
    ('tests/data/openings-development.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-validation.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-time-validation.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-lmr-validation.json', 'opening-suite', 'tracked'),
    ('tests/data/performance-gamephases.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-phase3g-1.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-phase3g-2.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-phase3g-3.json', 'opening-suite', 'tracked'),
    ('tests/data/openings-phase3g-4.json', 'opening-suite', 'tracked'),
    ('tests/data/clock-flagfalls-phase3g.json', 'clock-cases', 'tracked'),
    ('tools/bench.py', 'benchmark-constant', 'tracked'),
    ('tests/position_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/search_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/exchange_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/nnue_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/uci_test.py', 'valid-fen-literals', 'tracked'),
    ('results/phase3a-20261016/positions.txt', 'position-lines', 'local'),
    ('results/phase3b-20261016/positions.txt', 'position-lines', 'local'),
    ('results/phase3c-20261016/endgame-positions.txt', 'position-lines', 'local'),
    ('results/phase3c-20261016/middlegame-positions.txt', 'position-lines', 'local'),
    ('results/phase3d-20261017/pawn-positions.txt', 'position-lines', 'local'),
    ('results/phase3e-20261017/main-positions.txt', 'position-lines', 'local'),
    ('results/phase3e-20261017/pawn-positions.txt', 'position-lines', 'local'),
    ('results/phase3f-20261017/endgame-main-positions.txt', 'position-lines', 'local'),
    ('results/phase3f-20261017/endgame-pawn-positions.txt', 'position-lines', 'local'),
    ('results/phase3f-20261017/middlegame-positions.txt', 'position-lines', 'local'),
    ('results/phase3f-20261017/opening-positions.txt', 'position-lines', 'local'),
    ('results/phase3h-20261018/development-positions.txt', 'position-lines', 'local'),
    ('results/manual-cutechess-20261014/positions.fen', 'position-lines', 'local'),
    ('results/manual-cutechess-20261018/positions.fen', 'position-lines', 'local'),
    ('results/time-policy-20261014/development-profile.json', 'json-positions', 'local'),
    ('results/time-policy-20261014/manual-root-profile.json', 'json-positions', 'local'),
    ('results/time-policy-hard-20261014/development-profile.json', 'json-positions', 'local'),
    ('results/time-policy-hard-20261014/manual-root-profile.json', 'json-positions', 'local'),
    ('results/phase3f-20261017/profile-opening/report.json', 'json-positions', 'local'),
    ('results/phase3f-20261017/profile-middlegame/report.json', 'json-positions', 'local'),
    ('results/phase3f-20261017/profile-endgame/report.json', 'json-positions', 'local'),
    ('results/phase3j-20261018/workbook-inputs.json', 'json-positions', 'local'),
    ('results/phase3k-20261018/console-verification.json', 'console-verification', 'local'),
)


def catalog_exclusions(repository):
    """Reproduce the manifest from the original local evidence, when available.

    Only canonical board keys and hashes are published; workbook cells, mate
    answers, scores, usernames, and machine paths are not included. The immutable
    manifest permits public generation without access to the local workbook.
    """
    repository = Path(repository)
    sources, references = [], {}
    for identifier, (relative, kind, availability) in enumerate(SOURCE_SPECS):
        path = repository / relative
        keys = source_roots(path, kind)
        source = {"id": identifier, "path": relative, "kind": kind,
                  "availability": availability, "sha256": digest(path.read_bytes()),
                  "entries": len(keys), "unique_roots": len(set(keys))}
        if relative.endswith("workbook-inputs.json"):
            original = json.loads(path.read_bytes())
            source["upstream"] = {"description": "owner-supplied puzzle workbook; not redistributed",
                                  "sha256": original["sha256"], "positions": len(keys)}
        if relative.endswith("positions.fen") and "manual-cutechess" in relative:
            audit = path.parent / "verification.json"
            source["audit"] = {"path": str(audit.relative_to(repository)), "sha256": digest(audit.read_bytes())}
            source["pgn_sha256"] = json.loads(audit.read_bytes())["pgn_sha256"]
        sources.append(source)
        for key in set(keys):
            references.setdefault(key, []).append(identifier)
    return {"schema_version": 1, "license": LICENSE, "copyright": COPYRIGHT,
            "canonicalization": CANONICALIZATION,
            "scope": "Frozen saved roots: earlier opening/performance suites, Phase 3G shards, clock failures, benchmark literals, correctness FEN literals, saved profile roots, manual PGN audit boards, 39 puzzle inputs, and Phase 3K display/perft plus comparison roots.",
            "limitations": [
                "This catalog covers declared saved root corpora, not every internal search node or every position in historical match transcripts.",
                "The second October 18 manual game has no saved PGN; its full position history is unavailable and cannot be exhaustively excluded.",
                "Valid six-field FEN literals are extracted from correctness tests; dynamically constructed/random test states are represented only when saved by the listed evidence.",
                "Local results/ artifacts and the private puzzle workbook are not required in a public checkout; their canonical root keys and source hashes are retained here."],
            "sources": sources, "unique_roots": len(references),
            "roots": [{"root_key": key, "sources": references[key]} for key in sorted(references)]}


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
        raise ValueError("Phase 3L is frozen to seed {}".format(SEED))
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
                identifier = "phase3l-{}-v{}".format(stem["id"], variant)
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
            "schema_version": 1, "description": "Phase 3L frozen opening shard {} of 4".format(index + 1),
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
        "exclusion_manifest": {"path": EXCLUSION_MANIFEST, "sha256": EXCLUSION_SHA256},
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
    parser.add_argument("--verify-sources", action="store_true",
                        help="Also replay original catalog sources and require their frozen hashes")
    args = parser.parse_args()
    try:
        files = generate(args.repository, args.seed)
        if args.verify_sources:
            exclusion_roots(args.repository, verify_sources=True)
        if args.check:
            check_assets(files, args.repository / "tests/data")
        else:
            write_assets(files, args.output_dir)
    except (ValueError, OSError) as error:
        parser.exit(1, "Phase 3L generation failed: {}\n".format(error))
    print(json.dumps({"status": "PASS", "mode": "check" if args.check else "generate",
                      "seed": args.seed, "sha256": {name: digest(contents) for name, contents in files.items()}}, indent=2))


if __name__ == "__main__":
    main()
