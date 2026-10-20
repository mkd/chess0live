#!/usr/bin/env python3
"""Bounded quiescence SEE regressions, using an independent chess referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Reuses established protocol parsing, lifecycle helpers and original rule cases.
New composed boards exercise the protected move classes in both colors. Public
output cannot prove individual internal branches were visited: actual predicate
coverage is separate in the C++ suite. No fixture is an optimal-play oracle.
"""
import argparse
from pathlib import Path
import queue

import chess
import null_move_uci_test as common
import reverse_futility_uci_test as reverse

ROOT = Path(__file__).resolve().parents[1]
OPTION = "QSearch SEE Pruning"
PREFIX = "info string qsearchsee v1 "
COUNTERS = ("evaluations", "pruned")
VALUES = {None: 0, chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}


def exchange_gain(board, move):
    captured = 100 if board.is_en_passant(move) else VALUES[board.piece_type_at(move.to_square)]
    return captured + (VALUES[move.promotion] - 100 if move.promotion else 0)


def exchange_reply(board, target):
    """Slow full-board legal-LVA oracle, unlike the engine's local bitboards."""
    captures = [move for move in board.legal_moves
                if board.is_capture(move) and move.to_square == target
                and move.promotion in (None, chess.QUEEN)]
    if not captures:
        return 0
    move = min(captures, key=lambda m: (VALUES[board.piece_type_at(m.from_square)], m.from_square))
    gain = exchange_gain(board, move)
    child = board.copy(stack=False)
    child.push(move)
    return max(0, gain - exchange_reply(child, target))


def fixture_cases():
    """Pin factual tactical properties before asking the engine to search."""
    cases = [
        ("quiet-losing-capture", "6k1/pp6/4p3/3p4/8/8/PP6/RN1Q2K1 w - - 0 1",
         "d1d5", -800, False, False, False),
        ("checking-sacrifice", "6rk/pp5p/6Q1/8/8/8/PP6/RN2K3 w - - 0 1",
         "g6h7", -800, False, True, False),
        ("losing-evasion", "4r3/3Q1bk1/8/8/8/8/PP6/RN2K3 w - - 0 1",
         "d7e8", -400, True, False, False),
        ("capture-stalemate", "7k/5Q2/5Kr1/8/8/8/8/8 w - - 0 1",
         "f7g6", 500, True, False, True),
        ("en-passant", "4k2r/pp4pp/8/2pP4/8/8/PP4PP/R3K3 w - c6 0 1",
         "d5c6", 0, False, False, False),
    ]
    for promotion, gain in (("q", 1300), ("r", 900), ("b", 730), ("n", 720)):
        cases.append(("capture-promotion-" + promotion,
                      "r4k2/1P6/8/8/8/8/PP4pp/R3K3 w - - 0 1",
                      "b7a8" + promotion, gain, False, promotion in ("q", "r"), False))
    result = []
    for name, fen, notation, expected, checked, checking, terminal in cases:
        for mirror in (False, True):
            board = chess.Board(fen)
            if mirror:
                board = board.mirror()
                coordinate = common.reflected(notation)
            else:
                coordinate = notation
            move = chess.Move.from_uci(coordinate)
            assert board.is_valid() and move in board.legal_moves, (name, board.fen())
            assert board.is_capture(move) and board.is_check() == checked, name
            if name == "en-passant":
                assert board.is_en_passant(move)
            child = board.copy(stack=False)
            child.push(move)
            assert child.is_check() == checking and child.is_stalemate() == terminal, name
            estimate = exchange_gain(board, move) - exchange_reply(child, move.to_square)
            assert estimate == expected, (name, mirror, estimate, expected)
            case = {"id": name + ("-mirror" if mirror else "-original"),
                    "fen": board.fen(en_passant="fen"), "moves": [], "depth": 3,
                    "searchmoves": [coordinate]}
            if terminal:
                case["score"] = ["cp", 0]
            result.append((case, board))
    # Eight pieces cannot grow to nine through legal play. Unlike a checked
    # root alone, this structurally excludes pruning throughout the whole tree.
    sparse = chess.Board("6k1/pp6/4p3/3p4/8/8/P7/3Q2K1 w - - 0 1")
    assert sparse.is_valid() and len(sparse.piece_map()) == 8
    for mirror in (False, True):
        board = sparse.mirror() if mirror else sparse
        result.append(({"id": "eight-piece-boundary" + ("-mirror" if mirror else "-original"),
                        "fen": board.fen(), "moves": [], "depth": 4, "searchmoves": [],
                        "zero_probes": True, "exact_off_parity": True}, board))
    return result


def expand_cases():
    result = common.expand_cases() + fixture_cases()
    for case, board in result:
        if case.get("zero_probes"):
            assert (len(board.piece_map()) <= 8 or board.halfmove_clock >= 100
                    or board.is_repetition(3)), case
    return result


def validate(lines, board, *, enabled, reverse_enabled=False, null_enabled=False,
             diagnostics=True, **expected):
    records = [line for line in lines if line.startswith(PREFIX)]
    counters = None
    if enabled and diagnostics:
        raw = common.only_record(lines, PREFIX)
        assert set(raw) == {"enabled", *COUNTERS} and raw["enabled"] == "true", raw
        counters = {key: int(raw[key]) for key in COUNTERS}
        assert 0 <= counters["pruned"] <= counters["evaluations"], counters
        assert lines.index(records[0]) < len(lines) - 2, lines
    else:
        assert not records, lines
    result = reverse.validate([line for line in lines if not line.startswith(PREFIX)],
                              board, enabled=reverse_enabled, null_enabled=null_enabled,
                              diagnostics=diagnostics, **expected)
    result["counters"] = counters
    result["lines"] = lines
    return result


def search(engine, board, command="go depth 4", *, timeout=30, **expected):
    engine.send(command)
    result = validate(engine.until("bestmove ", timeout=timeout), board, **expected)
    engine.send("stop")
    common.ready(engine)
    return result


def run(executable, network, max_threads, activation_timeout):
    cases = expand_cases()
    checks = 0
    with common.Engine(executable) as engine:
        assert f"option name {OPTION} type check default false" in engine.handshake()
        for name, value in (("EvalFile", network), ("Hash", 1), ("Threads", 1),
                            ("Late Move Reductions", "false"), ("Countermove Ordering", "false"),
                            ("Null Move Pruning", "false"), ("Reverse Futility Pruning", "false"),
                            ("SyzygyProbeLimit", 0), ("Search Diagnostics", "true")):
            common.option(engine, name, value)
        board = common.position(engine)
        baseline = search(engine, board, enabled=False)
        checks += 1
        for value in ("invalid", "1", None):
            common.option(engine, OPTION, value, error=True)
            search(engine, board, "go depth 2", enabled=False)
            checks += 1
        common.option(engine, OPTION, "true")
        common.option(engine, OPTION, "invalid", error=True)
        candidate = search(engine, board, enabled=True)
        common.option(engine, OPTION, "false")
        assert search(engine, board, enabled=False)["signature"] == baseline["signature"]
        common.option(engine, OPTION, "true")
        assert search(engine, board, enabled=True)["signature"] == candidate["signature"]
        checks += 3

        common.option(engine, "Clear Hash")
        before = common.root_evaluation(engine)
        active = search(engine, board, "go depth 5 nodes 200000", enabled=True,
                        node_ceiling=200000, timeout=activation_timeout)
        assert all(active["counters"][key] > 0 for key in COUNTERS), active
        assert common.root_evaluation(engine) == before
        common.option(engine, "Clear Hash")
        common.option(engine, "Search Diagnostics", "false")
        silent = search(engine, board, "go depth 5 nodes 200000", enabled=True,
                        diagnostics=False, node_ceiling=200000, timeout=activation_timeout)
        assert silent["signature"] == active["signature"], (silent, active)
        common.option(engine, "Search Diagnostics", "true")
        checks += 2

        for case, expected_board in cases:
            results = []
            for enabled in ((False, True) if case.get("exact_off_parity") else (True,)):
                common.option(engine, OPTION, str(enabled).lower())
                common.option(engine, "Clear Hash")
                board = common.position(engine, case["fen"], case["moves"])
                assert board.fen() == expected_board.fen()
                command = f"go depth {case['depth']}"
                if case["searchmoves"]:
                    command += " searchmoves " + " ".join(case["searchmoves"])
                result = search(engine, board, command, enabled=enabled,
                                allowed=set(case["searchmoves"]), score=case.get("score"))
                if enabled and case.get("zero_probes"):
                    assert all(value == 0 for value in result["counters"].values()), (case, result)
                engine.send("d")
                assert engine.until("fen ")[-1] == "fen " + board.fen(en_passant="fen")
                results.append(result)
            if case.get("exact_off_parity"):
                assert results[0]["signature"] == results[1]["signature"], (case, results)
            checks += 1

        for threads in ((1,) if max_threads == 1 else (1, 4)):
            common.option(engine, "Threads", threads)
            common.option(engine, OPTION, "true")
            board = common.position(engine)
            for limit in (1, 257, 4096):
                common.option(engine, "Clear Hash")
                search(engine, board, f"go nodes {limit}", enabled=True,
                       threads=threads, node_limit=limit)
                checks += 1
            engine.send("go infinite")
            engine.send("stop")
            validate(engine.until("bestmove ", timeout=10), board, enabled=True, threads=threads)
            common.ready(engine)
            checks += 1
            for command, release in (("go infinite depth 2", "stop"), ("go ponder depth 2", "ponderhit")):
                engine.send(command)
                partial = engine.until("info depth 2 ", timeout=30)
                engine.send("isready")
                pending = engine.until("readyok", timeout=10)
                assert not any(line.startswith("bestmove ") for line in partial + pending)
                engine.send(release)
                validate(partial + pending[:-1] + engine.until("bestmove ", timeout=10),
                         board, enabled=True, threads=threads)
                common.ready(engine)
                checks += 1
            search(engine, board, "go movetime 60", enabled=True, threads=threads)
            checks += 1
            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 3 ", timeout=30)
                engine.send(f"setoption name {OPTION} value {str(following).lower()}")
                validate(partial + engine.until("bestmove ", timeout=10), board,
                         enabled=previous, threads=threads)
                common.ready(engine)
                search(engine, board, "go nodes 257", enabled=following,
                       threads=threads, node_limit=257)
                checks += 1
            for command in ("setoption name Clear Hash", "ucinewgame",
                            "setoption name Hash value 2", f"setoption name EvalFile value {network}"):
                engine.send("go infinite")
                engine.send(command)
                validate(engine.until("bestmove ", timeout=10), board, enabled=True, threads=threads)
                common.ready(engine)
                search(engine, board, "go depth 2", enabled=True, threads=threads)
                checks += 1
            common.option(engine, "Null Move Pruning", "true")
            common.option(engine, "Reverse Futility Pruning", "true")
            search(engine, board, "go depth 6 nodes 120000", enabled=True, null_enabled=True,
                   reverse_enabled=True, node_ceiling=120000, threads=threads,
                   timeout=activation_timeout)
            common.option(engine, "Null Move Pruning", "false")
            common.option(engine, "Reverse Futility Pruning", "false")
            checks += 1

        engine.send("go infinite")
        engine.send("quit")
        engine.process.wait(timeout=10)
        assert engine.process.returncode == 0
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive()
        remaining = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                remaining.append(line)
        assert not any(marker in line for line in engine.transcript + remaining
                       for marker in common.SANITIZER_MARKERS), remaining
        checks += 1
    print(f"QSearch SEE UCI tests passed ({checks} bounded cases; up to {max_threads} workers; no strength claim)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path, nargs="?")
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--threads", type=int, choices=(1, 4), default=4)
    parser.add_argument("--activation-timeout", type=common.activation_seconds, default=30,
                        help="external allowance for node-capped activation/composition, not engine time")
    parser.add_argument("--validate-corpus", action="store_true")
    args = parser.parse_args()
    if args.validate_corpus:
        print(f"QSearch SEE corpus passed ({len(expand_cases())} independently validated colored cases)")
        return
    if args.engine is None:
        parser.error("supply an engine executable or --validate-corpus")
    if not args.network.is_file():
        parser.error("pinned network missing; run make net first")
    run(args.engine.resolve(), args.network.resolve(), args.threads, args.activation_timeout)


if __name__ == "__main__":
    main()
