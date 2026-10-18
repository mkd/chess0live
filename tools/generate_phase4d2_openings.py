#!/usr/bin/env python3
"""Reproduce the original, unevaluated Phase 4D.2 full-history opening shards.

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


SEED = 20261018422
REFEREE_VERSION = "1.11.2"
MAX_ATTEMPTS = 10000
DOMAIN = "chess0live.phase4d2.openings.v1"
LICENSE = "GPL-3.0-or-later"
COPYRIGHT = "Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>"
GENERATOR_PATH = "tools/generate_phase4d2_openings.py"
METADATA_NAME = "phase4d2-generation.json"
SUITE_NAMES = tuple("phase4d2-lmr-{:02d}.json".format(i) for i in range(1, 9))
EXCLUSION_MANIFEST = "tests/data/phase4d2-exclusions.json"
EXCLUSION_SHA256 = "94d17056e1b86ebeb4c8e9801c551df9edd8ee8a33cec4ac74a1db39a8de50ee"

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
    ('e4-01', 'Italian restrained center', 'e4 e5 Nf3 Nc6 Bc4 Bc5 d3 Nf6 c3 d6 O-O O-O h3 a6 Re1 Ba7'),
    ('e4-02', 'Italian central expansion', 'e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5 O-O d6 c3 O-O Bb3 h6 d4 Bb6'),
    ('e4-03', 'Spanish closed development', 'e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O'),
    ('e4-04', 'Spanish exchange structure', 'e4 e5 Nf3 Nc6 Bb5 a6 Bxc6 dxc6 O-O f6 d3 Bg4 Be3 Qd7 Nbd2 O-O-O'),
    ('e4-05', 'Spanish early d6', 'e4 e5 Nf3 Nc6 Bb5 d6 d4 Bd7 Nc3 Nf6 O-O Be7 Re1 O-O Bf1 Re8'),
    ('e4-06', 'Four knights central exchange', 'e4 e5 Nf3 Nc6 Nc3 Nf6 d4 exd4 Nxd4 Bb4 Nxc6 bxc6 Bd3 d5 exd5 cxd5'),
    ('e4-07', 'Four knights bishop exchange', 'e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O d3 d6 Bg5 Bxc3 bxc3 h6'),
    ('e4-08', 'Scotch central knights', 'e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nxc6 bxc6 e5 Qe7 Qe2 Nd5 c4 Nb6'),
    ('e4-09', 'Petrov symmetric center', 'e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Bd6 O-O O-O c4 c6'),
    ('e4-10', 'Philidor exchange center', 'e4 e5 Nf3 d6 d4 exd4 Nxd4 Nf6 Nc3 Be7 Be2 O-O O-O Re8 Bf4 Bf8'),
    ('e4-11', 'Vienna bishop development', 'e4 e5 Nc3 Nf6 Bc4 Nc6 d3 Bc5 h3 d6 Nf3 O-O O-O a6 a4 Ba7'),
    ('e4-12', 'Bishop queenside fianchetto', 'e4 e5 Bc4 Nc6 d3 Nf6 Nc3 Bc5 Nf3 d6 O-O O-O a3 a6 b4 Ba7'),
    ('e4-13', 'Sicilian classical center', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 Nc6 Be2 e6 O-O Be7 Be3 O-O'),
    ('e4-14', 'Sicilian fianchetto center', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6'),
    ('e4-15', 'Sicilian queenside expansion', 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5 Nb3 Be7 O-O O-O'),
    ('e4-16', 'Sicilian restrained bishops', 'e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 e6 Nc3 Qc7 Be2 a6 O-O Nf6 Be3 Bb4'),
    ('e4-17', 'Sicilian bishop exchange', 'e4 c5 Nf3 Nc6 Bb5 g6 Bxc6 dxc6 d3 Bg7 O-O Nf6 h3 O-O Be3 b6'),
    ('e4-18', 'Sicilian f4 structure', 'e4 c5 Nc3 Nc6 f4 g6 Nf3 Bg7 Bc4 e6 O-O Nge7 d3 O-O Qe1 d5'),
    ('e4-19', 'French advance wing play', 'e4 e6 d4 d5 e5 c5 c3 Nc6 Nf3 Qb6 a3 Nge7 b4 cxd4 cxd4 Nf5'),
    ('e4-20', 'French exchange development', 'e4 e6 d4 d5 exd5 exd5 Nf3 Nf6 Bd3 Bd6 O-O O-O c3 c6 Bg5 Bg4'),
    ('e4-21', 'French knight pressure', 'e4 e6 d4 d5 Nc3 Nf6 Bg5 Be7 e5 Nfd7 Bxe7 Qxe7 f4 O-O Nf3 c5'),
    ('e4-22', 'Caro-Kann open knights', 'e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 Nf3 Nd7 h4 h6 Bd3 Bxd3'),
    ('e4-23', 'Caro-Kann exchange center', 'e4 c6 d4 d5 exd5 cxd5 c4 Nf6 Nc3 e6 Nf3 Be7 Bd3 O-O O-O Nc6'),
    ('e4-24', 'Modern classical development', 'e4 g6 d4 Bg7 Nc3 d6 Nf3 a6 Be2 b5 O-O Bb7 Re1 Nd7 Bf1 e5'),
    ('d4-01', 'London castled center', 'd4 d5 Nf3 Nf6 Bf4 c5 e3 Nc6 c3 e6 Nbd2 Bd6 Bg3 O-O Bd3 b6'),
    ('d4-02', 'London early queen exchange', 'd4 Nf6 Bf4 d5 e3 c5 c3 Nc6 Nd2 Qb6 Qb3 Qxb3 axb3 e6 Ngf3 Bd6'),
    ('d4-03', 'Colle queenside fianchetto', 'd4 d5 Nf3 Nf6 e3 e6 Bd3 b6 O-O Bb7 b3 Bd6 Bb2 O-O Nbd2 c5'),
    ('d4-04', 'Torre central advance', 'd4 Nf6 Nf3 e6 Bg5 d5 e3 Be7 Bd3 O-O O-O c5 c3 Nc6 Nbd2 b6'),
    ('d4-05', 'Veresov early bishops', 'd4 d5 Nc3 Nf6 Bg5 e6 e4 Be7 e5 Nfd7 Bxe7 Qxe7 f4 O-O Bd3 c5'),
    ('d4-06', 'Catalan open center', 'd4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4 Qc2 a6 Qxc4 b5'),
    ('d4-07', 'Catalan closed center', 'd4 d5 c4 e6 Nf3 Nf6 g3 Be7 Bg2 O-O O-O Nbd7 Qc2 c6 Nbd2 b6'),
    ('d4-08', 'Orthodox queen gambit', 'd4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6 Bd3 Bb7'),
    ('d4-09', 'Queen gambit exchange structure', 'd4 d5 c4 e6 Nc3 Nf6 cxd5 exd5 Bg5 Be7 e3 O-O Bd3 c6 Qc2 Nbd7'),
    ('d4-10', 'Queen gambit accepted center', 'd4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6 Qe2 b5 Bd3 Bb7'),
    ('d4-11', 'Slav accepted center', 'd4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4 O-O O-O'),
    ('d4-12', 'Slav exchange development', 'd4 d5 c4 c6 cxd5 cxd5 Nc3 Nf6 Nf3 Nc6 Bf4 Bf5 e3 e6 Bd3 Bxd3'),
    ('d4-13', 'Semi Slav central exchange', 'd4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5 Bd3 a6'),
    ('d4-14', 'Tarrasch isolated center', 'd4 d5 c4 e6 Nc3 c5 cxd5 exd5 Nf3 Nc6 g3 Nf6 Bg2 Be7 O-O O-O'),
    ('d4-15', 'Nimzo Indian castled development', 'd4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3'),
    ('d4-16', 'Nimzo Indian fianchetto', 'd4 Nf6 c4 e6 Nc3 Bb4 g3 d5 Bg2 O-O Nf3 dxc4 O-O Nc6 Qa4 a5'),
    ('d4-17', 'Queens Indian bishop pressure', 'd4 Nf6 c4 e6 Nf3 b6 g3 Bb7 Bg2 Be7 O-O O-O Nc3 Ne4 Qc2 Nxc3'),
    ('d4-18', 'Bogo Indian exchange', 'd4 Nf6 c4 e6 Nf3 Bb4+ Bd2 Bxd2+ Qxd2 O-O Nc3 d5 e3 Nbd7 Bd3 c5'),
    ('d4-19', 'Kings Indian classical center', 'd4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7'),
    ('d4-20', 'Kings Indian f3 center', 'd4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 Nc6 Qd2 a6 Nge2 Rb8'),
    ('d4-21', 'Grunfeld exchange center', 'd4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Nf3 c5 Be3 Qa5'),
    ('d4-22', 'Modern Benoni center', 'd4 Nf6 c4 c5 d5 e6 Nc3 exd5 cxd5 d6 e4 g6 Nf3 Bg7 Be2 O-O'),
    ('d4-23', 'Dutch classical castling', 'd4 f5 c4 Nf6 g3 e6 Bg2 Be7 Nf3 O-O O-O d6 Nc3 Qe8 b3 a5'),
    ('d4-24', 'Dutch fianchetto structure', 'd4 f5 g3 Nf6 Bg2 g6 Nf3 Bg7 O-O O-O c4 d6 Nc3 Nc6 d5 Ne5'),
    ('c4-01', 'English four knights center', 'c4 e5 Nc3 Nf6 Nf3 Nc6 g3 d5 cxd5 Nxd5 Bg2 Nb6 O-O Be7 d3 O-O'),
    ('c4-02', 'English reversed fianchetto', 'c4 e5 Nc3 Nc6 g3 g6 Bg2 Bg7 d3 d6 e4 Nge7 Nge2 O-O O-O Be6'),
    ('c4-03', 'English symmetric early d4', 'c4 c5 Nc3 Nc6 Nf3 Nf6 d4 cxd4 Nxd4 e6 g3 Qb6 Nb3 Bb4 Bg2 O-O'),
    ('c4-04', 'English symmetric slow development', 'c4 c5 g3 g6 Bg2 Bg7 Nc3 Nc6 Nf3 Nf6 O-O O-O d3 d6 a3 a6'),
    ('c4-05', 'English queens pawn center', 'c4 e6 Nc3 d5 d4 Nf6 Nf3 Be7 Bg5 O-O e3 h6 Bh4 b6 Qc2 Bb7'),
    ('c4-06', 'English fianchetto dark bishop', 'c4 Nf6 Nc3 e6 e4 d5 e5 d4 exf6 dxc3 bxc3 Qxf6 Nf3 Nc6 d4 h6'),
    ('c4-07', 'English Dutch structure', 'c4 f5 Nc3 Nf6 g3 g6 Bg2 Bg7 d3 O-O e4 d6 Nge2 Nc6 O-O e5'),
    ('c4-08', 'English flank queens', 'c4 b6 Nc3 Bb7 e4 e6 d4 Bb4 Bd3 Nf6 Qc2 d6 Nge2 O-O O-O c5'),
    ('nf3-01', 'Reti central pawn exchange', 'Nf3 d5 c4 dxc4 e3 Nf6 Bxc4 e6 O-O c5 d4 Nc6 Nc3 a6 Qe2 b5'),
    ('nf3-02', 'Reti bishop pin', 'Nf3 d5 g3 c6 Bg2 Bg4 O-O Nd7 d3 e5 c4 Ngf6 cxd5 cxd5 Nc3 Be7'),
    ('nf3-03', 'Reti symmetric knights', 'Nf3 Nf6 c4 c5 g3 g6 Bg2 Bg7 O-O O-O Nc3 Nc6 d4 cxd4 Nxd4 Qb6'),
    ('nf3-04', 'Reti delayed central occupation', 'Nf3 e6 g3 d5 Bg2 Nf6 O-O Be7 d3 O-O Nbd2 c5 e4 Nc6 Re1 b6'),
    ('nf3-05', 'Reti queenside bishop pairing', 'Nf3 Nf6 b3 d5 Bb2 c5 e3 Nc6 Bb5 Bd7 O-O e6 d4 Be7 Nbd2 O-O'),
    ('nf3-06', 'Reti kingside attack structure', 'Nf3 c5 g3 d5 Bg2 Nc6 O-O e5 d3 Nf6 Nbd2 Be7 e4 O-O Re1 d4'),
    ('nf3-07', 'Reti Dutch central exchange', 'Nf3 f5 d4 Nf6 c4 e6 Nc3 Bb4 Bd2 O-O g3 d5 Bg2 c6 O-O Nbd7'),
    ('nf3-08', 'Reti early queenside knight', 'Nf3 d5 Nc3 Nf6 d4 e6 Bg5 Be7 e3 O-O Bd3 c5 O-O Nc6 a3 b6'),
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
    if (len(result) != 64 or families.count("e2e4") != 24 or families.count("d2d4") != 24
            or families.count("c2c4") != 8 or families.count("g1f3") != 8):
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
    if kind == "canonical-catalog":
        bodies = [entry["root_key"] + " 0 1" for entry in json.loads(text)["roots"]]
    elif kind == "fen-cases":
        bodies = [entry["fen"] for entry in json.loads(text)["cases"]]
    elif kind == "console-compatibility":
        data = json.loads(text)
        bodies = [entry["position"] for entry in data["checks"]]
        bodies += [entry["fen"] for entry in data["mate_cases"]]
    elif kind == "opening-suite":
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
# The original Phase 3L public catalog carries forward private-source omissions
# and source hashes. Its unplayed shards are parsed solely for exclusion; their
# roots are never emitted as development inputs, searched, or score-filtered.
SOURCE_SPECS = (
    ('tests/data/phase3l-exclusions.json', 'canonical-catalog', 'tracked'),
    ('tests/data/phase3l-lmr-01.json', 'opening-suite', 'tracked'),
    ('tests/data/phase3l-lmr-02.json', 'opening-suite', 'tracked'),
    ('tests/data/phase3l-lmr-03.json', 'opening-suite', 'tracked'),
    ('tests/data/phase3l-lmr-04.json', 'opening-suite', 'tracked'),
    ('tests/data/countermove-profile.json', 'json-positions', 'tracked'),
    ('tests/data/syzygy-cases.json', 'fen-cases', 'tracked'),
    ('tests/data/performance-gamephases.json', 'opening-suite', 'tracked'),
    ('tools/bench.py', 'benchmark-constant', 'tracked'),
    ('tests/position_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/search_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/exchange_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/nnue_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/uci_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/smp_uci_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/countermove_uci_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/syzygy_uci_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/syzygy_search_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/tablebase_test.cpp', 'valid-fen-literals', 'tracked'),
    ('tests/profile_countermove_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/match_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/qualify_lmr_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/qualify_phase3g_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/qualify_phase3l_test.py', 'valid-fen-literals', 'tracked'),
    ('tests/qualify_time_policy_test.py', 'valid-fen-literals', 'tracked'),
    ('results/phase3l-20261018/console-compatibility.json', 'console-compatibility', 'local'),
    ('results/phase4c-20261018/composed-fixture-oracle.json', 'fen-cases', 'local'),
    ('results/phase4d-20261018/positions.txt', 'position-lines', 'local'),
)
BASE_CATALOG_SHA256 = "f645aafc49d6dee36c8b1b492a0b3fa67665713281a68453f48be4b354ddd9d9"


def catalog_exclusions(repository):
    """Extend the frozen public catalog without reopening private workbook data.

    Published provenance consists of canonical keys, relative paths and digests.
    Original private inputs and all previous catalog limitations remain inherited.
    No evaluator, engine, match result, or score participates in this function.
    """
    repository = Path(repository)
    base_path = repository / SOURCE_SPECS[0][0]
    if digest(base_path.read_bytes()) != BASE_CATALOG_SHA256:
        raise ValueError("Base exclusion catalog hash mismatch")
    base = json.loads(base_path.read_bytes())
    sources, references = [], {}
    for identifier, (relative, kind, availability) in enumerate(SOURCE_SPECS):
        path = repository / relative
        keys = source_roots(path, kind)
        source = {"id": identifier, "path": relative, "kind": kind,
                  "availability": availability, "sha256": digest(path.read_bytes()),
                  "entries": len(keys), "unique_roots": len(set(keys))}
        if identifier == 0:
            source["inherited_sources"] = base["sources"]
            source["inherited_limitations"] = base["limitations"]
        if relative.startswith("tests/data/phase3l-lmr-"):
            source["use"] = "Untouched held-out roots read programmatically for exclusion only; no engine evaluation."
        sources.append(source)
        for key in set(keys):
            references.setdefault(key, []).append(identifier)
    return {"schema_version": 1, "license": LICENSE, "copyright": COPYRIGHT,
            "canonicalization": CANONICALIZATION,
            "scope": "Pinned Phase 3L canonical catalog, its four untouched held-out shards for exclusion only, and exposed saved roots from Phase 3L through Phase 4D.1.",
            "limitations": base["limitations"] + [
                "The earlier catalog is preserved as an immutable dependency; private workbook and local evidence are not reopened or redistributed.",
                "New Syzygy/countermove corpora and current valid FEN literals are excluded; unsaved dynamically constructed test states and historical internal search nodes are not exhaustive.",
                "Related opening stems and common machine conditions remain dependence risks; exclusion proves only disjoint canonical saved roots."],
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
        raise ValueError("Phase 4D.2 is frozen to seed {}".format(SEED))
    if chess.__version__ != REFEREE_VERSION:
        raise ValueError("Require chess=={}; found {}".format(REFEREE_VERSION, chess.__version__))
    stems = parse_stems()
    excluded, exclusion_records = exclusion_roots(Path(repository))
    used, shards, slots = set(), [[] for _ in range(8)], []
    totals = {"terminal": 0, "duplicate": 0, "prior_overlap": 0, "sha256_words": 0}
    for stem_index, stem in enumerate(stems):
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
                identifier = "phase4d2-{}-v{}".format(stem["id"], variant)
                shards[(stem_index % 2) * 4 + variant % 4].append({
                    "id": identifier, "stem_id": stem["id"], "variant": variant,
                    "moves": stem["moves"] + tail, "final_fen": board.fen(),
                    "canonical_root": key, "accepted_attempt": attempt,
                })
                slots.append({"id": identifier, "shard": (stem_index % 2) * 4 + variant % 4 + 1,
                              "accepted_attempt": attempt, "rejections": rejections})
                break
            else:
                raise ValueError("Attempt limit reached for {} variant {}".format(stem["id"], variant))
    files = {}
    for index, entries in enumerate(shards):
        if len(entries) != 64:
            raise ValueError("Shard size mismatch")
        files[SUITE_NAMES[index]] = encoded({
            "schema_version": 1, "description": "Phase 4D.2 frozen opening shard {} of 8".format(index + 1),
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
            "domain": DOMAIN, "stem_plies": 16, "stems": 64, "variants_per_stem": 8,
            "families": {"e4": 24, "d4": 24, "c4": 8, "Nf3": 8},
            "root_plies": {"variants_0_to_3": 19, "variants_4_to_7": 20},
            "sharding": "(stem_index % 2) * 4 + variant % 4 + 1; stem order, then ascending variants",
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
        "root_count": len(used), "white_to_move": 256, "black_to_move": 256,
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
        parser.exit(1, "Phase 4D.2 generation failed: {}\n".format(error))
    print(json.dumps({"status": "PASS", "mode": "check" if args.check else "generate",
                      "seed": args.seed, "sha256": {name: digest(contents) for name, contents in files.items()}}, indent=2))


if __name__ == "__main__":
    main()
