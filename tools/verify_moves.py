#!/usr/bin/env python3
"""Optional legal-move and perft differential check against python-chess.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Install requirements-match.txt, then run, for example:
  python3 tools/verify_moves.py build/macos-arm64-generic-release/chess0live

The default is 64 independently sampled reachable positions plus explicit
special-move fixtures, at depth 2. No evaluation network is needed. The engine
and reference run sequentially with one worker; this is an optional external
oracle check, not part of the dependency-free core tests or an Elo experiment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import sys

try:
    import chess
except ImportError:
    chess = None

from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
SEED = 0x43484D4F564553
REFERENCE_VERSION = "1.11.2"

# Original constructed fixtures; no earlier engine's assets are used. Each
# fixture is also mirrored to exercise the opposite moving color.
FIXTURES = (
    ("castles-and-home-rook-captures", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"),
    ("castle-through-check", "4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1"),
    ("castle-into-check", "4k3/8/8/8/8/8/6r1/R3K2R w KQ - 0 1"),
    ("castle-out-of-check", "4k3/8/8/8/8/8/4r3/R3K2R w KQ - 0 1"),
    ("queenside-b-file-attacked", "4k3/8/8/8/8/8/1r6/R3K2R w KQ - 0 1"),
    ("ep-horizontal-pin", "7k/8/8/r4pPK/8/8/8/8 w - f6 0 2"),
    ("ep-vertical-pin", "4r2k/8/8/3pP3/8/8/8/4K3 w - d6 0 2"),
    ("ep-one-of-two-candidates-pinned", "4r2k/8/8/2PpP3/8/8/8/4K3 w - d6 0 2"),
    ("ep-check-evasion", "7k/8/8/3pP3/4K3/8/8/8 w - d6 0 2"),
    ("quiet-and-capture-underpromotions", "r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1"),
    ("double-check", "4r2k/8/8/8/1b6/8/8/4K3 w - - 0 1"),
    ("pinned-piece", "4r2k/8/8/8/8/8/4N3/4K3 w - - 0 1"),
    ("mate", "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"),
    ("stalemate", "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"),
)


def digest(path):
    """Hash artifacts in bounded chunks without duplicating them in memory."""
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def cases(seed, count):
    """Generate reproducible fixtures and unique positions from legal playouts."""
    result = [{"id": "start", "kind": "fixture", "fen": chess.STARTING_FEN}]
    for name, fen in FIXTURES:
        board = chess.Board(fen)
        for suffix, position in (("", board), ("-mirrored", board.mirror())):
            if not position.is_valid():
                raise ValueError(f"invalid built-in fixture: {name}{suffix}")
            result.append({"id": name + suffix, "kind": "fixture",
                           "fen": position.fen(en_passant="fen")})
    rng = random.Random(seed)
    seen = {item["fen"] for item in result}
    sampled = 0
    # Each sample begins a fresh legal game, avoiding a corpus confined to one
    # random opening. Sorted UCI moves make selection independent of iteration
    # order in the reference's move generator. The history proves reachability.
    for _ in range(count * 20):
        if sampled == count:
            break
        board = chess.Board()
        history = []
        for _ in range(rng.randint(1, 180)):
            moves = sorted(board.legal_moves, key=lambda move: move.uci())
            if not moves:
                break
            move = moves[rng.randrange(len(moves))]
            history.append(move.uci())
            board.push(move)
        fen = board.fen(en_passant="fen")
        if fen in seen:
            continue
        seen.add(fen)
        result.append({"id": f"random-{sampled:04d}", "kind": "reachable",
                       "fen": fen, "uci_history": history})
        sampled += 1
    if sampled != count:
        raise RuntimeError("could not generate the requested unique positions")
    return result


def perft(board, depth):
    """Count legal leaf nodes, ignoring draw adjudication as perft requires."""
    if depth == 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()
    total = 0
    for move in list(board.legal_moves):
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


def reference_divide(fen, depth):
    board = chess.Board(fen)
    result = {}
    for move in list(board.legal_moves):
        board.push(move)
        result[move.uci()] = perft(board, depth - 1)
        board.pop()
    return result


def engine_divide(engine, fen, depth, timeout):
    """Reject malformed/duplicate branches so protocol errors cannot pass."""
    engine.send("position fen " + fen)
    engine.send(f"divide {depth}")
    lines = engine.until("nodes ", timeout=timeout)
    result = {}
    for line in lines[:-1]:
        branch = re.fullmatch(r"([a-h][1-8][a-h][1-8][qrbn]?): (\d+)", line)
        if branch is None or branch[1] in result:
            raise ValueError(f"invalid or duplicate divide branch: {line}")
        result[branch[1]] = int(branch[2])
    summary = re.fullmatch(r"nodes (\d+) time (\d+)", lines[-1])
    if summary is None:
        raise ValueError(f"invalid divide summary: {lines[-1]}")
    return result, int(summary[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--positions", type=int, default=64,
                        help="number of random positions, in addition to fixtures (0..4096)")
    parser.add_argument("--depth", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=SEED)
    parser.add_argument("--timeout", type=float, default=30,
                        help="maximum seconds per engine divide (1..300)")
    parser.add_argument("--output", type=Path, default=ROOT / "results/move-verification.json")
    args = parser.parse_args()
    if chess is None or chess.__version__ != REFERENCE_VERSION:
        parser.error("requires chess==1.11.2; install requirements-match.txt")
    if not 0 <= args.positions <= 4096:
        parser.error("positions must be 0..4096")
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be 1..300 seconds")
    engine_path = args.engine.resolve()
    if not engine_path.is_file():
        parser.error("engine binary does not exist")
    inputs = cases(args.seed, args.positions)
    result = {
        "schema_version": 1, "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "engine": str(engine_path), "engine_sha256": digest(engine_path),
        "checker_sha256": digest(Path(__file__)),
        "reference": {"package": "chess", "version": chess.__version__},
        "python": platform.python_version(), "platform": platform.platform(),
        "seed": args.seed, "depth": args.depth, "random_positions": args.positions,
        "fixture_positions": len(inputs) - args.positions, "input_count": len(inputs),
        "input_sha256": hashlib.sha256(("\n".join(item["fen"] for item in inputs)
                                         + "\n").encode("utf-8")).hexdigest(),
        "input_hash_format": "UTF-8 FENs in input order, each followed by LF",
        "cpu_workers": 1, "inputs": inputs, "checked": [], "failures": [],
    }
    active = None
    engine = None
    try:
        with Engine(engine_path, cwd=ROOT) as engine:
            result["uci_identity"] = engine.handshake()
            engine.send("setoption name Threads value 1")
            engine.send("setoption name Hash value 1")
            engine.send("isready")
            engine.until("readyok", timeout=args.timeout)
            for active in inputs:
                budget = current_budget()  # Re-read owner overrides between cases.
                expected = reference_divide(active["fen"], args.depth)
                actual, total = engine_divide(engine, active["fen"], args.depth, args.timeout)
                expected_total = sum(expected.values())
                missing = sorted(expected.keys() - actual.keys())
                extra = sorted(actual.keys() - expected.keys())
                mismatched = {move: {"expected": expected[move], "actual": actual[move]}
                              for move in sorted(expected.keys() & actual.keys())
                              if expected[move] != actual[move]}
                record = {"id": active["id"], "root_moves": len(expected),
                          "expected_nodes": expected_total, "actual_nodes": total,
                          "resource_policy": budget}
                result["checked"].append(record)
                if missing or extra or mismatched or total != expected_total or total != sum(actual.values()):
                    result["failures"].append({"id": active["id"], "fen": active["fen"],
                        "kind": "mismatch", "missing_moves": missing, "extra_moves": extra,
                        "branch_mismatches": mismatched, "expected_nodes": expected_total,
                        "actual_nodes": total, "actual_branch_sum": sum(actual.values())})
    except Exception as error:
        result["failures"].append({"kind": "execution", "id": active["id"] if active else None,
                                   "error": f"{type(error).__name__}: {error}",
                                   "engine_tail": engine.transcript[-20:] if engine else []})
    result["checked_count"] = len(result["checked"])
    result["status"] = "pass" if not result["failures"] and len(result["checked"]) == len(inputs) else "fail"
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status'].upper()}: {result['checked_count']}/{len(inputs)} positions, "
          f"depth {args.depth}, {len(result['failures'])} failures; report: {args.output}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
