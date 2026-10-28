#!/usr/bin/env python3
"""Bounded continuation-history protocol and lifecycle regressions.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Run through tools/run.py to obtain the pinned independent python-chess referee.
One engine searches at a time, using one or four workers. These exposed tests
check legal output and state isolation, not playing strength or parallel
determinism. Full-width checks explicitly disable late move reductions.
"""
import argparse
from pathlib import Path
import queue

import chess

from countermove_uci_test import (Engine, fields, option, position, ready,
                                 validate as validate_ordinary)


ROOT = Path(__file__).resolve().parents[1]
OPTION = "Continuation History"
PREFIX = "info string continuation-history v1 "
ENTRIES_PER_WORKER = 12 * 64 * 12 * 64
SANITIZER_MARKERS = ("Sanitizer", "runtime error:", "data race")


def validate(lines, board, *, enabled, threads=1, diagnostics=True, **expected):
    """Reuse the independent legal referee, checking our new record separately.

    The older validator deliberately rejects unknown diagnostic records. Strip
    only this explicitly decoded record; do not weaken its public-output checks.
    Geometry covers all configured workers, while event counters aggregate only
    after workers join. No particular helper scheduling or tree is required.
    """
    records = [line for line in lines if line.startswith(PREFIX)]
    ordinary = [line for line in lines if not line.startswith(PREFIX)]
    result = validate_ordinary(ordinary, board, enabled=False,
                               diagnostics=diagnostics, **expected)
    counters = None
    if enabled and diagnostics:
        assert len(records) == 1, lines
        record = fields(records[0], PREFIX)
        keys = ("entries", "allocated_bytes", "lookups", "nonzero", "updates")
        assert set(record) == {"enabled", *keys} and record["enabled"] == "true", record
        counters = {}
        for key in keys:
            value = record[key]
            assert value.isascii() and value.isdecimal(), record
            counters[key] = int(value)
            assert counters[key] <= 2**64 - 1, record
        assert counters["entries"] == ENTRIES_PER_WORKER * threads, counters
        assert counters["allocated_bytes"] >= 2 * counters["entries"], counters
        assert counters["nonzero"] <= counters["lookups"], counters
    else:
        assert not records, lines

    if diagnostics:
        smp_lines = [line for line in lines if line.startswith("info string smp v1 ")]
        if threads == 1:
            assert not smp_lines, smp_lines
        else:
            assert len(smp_lines) == 1, lines
            smp = fields(smp_lines[0], "info string smp v1 ")
            nodes = [int(value) for value in smp["worker_nodes"].split(",")]
            depths = [int(value) for value in smp["worker_depths"].split(",")]
            assert int(smp["threads"]) == len(nodes) == len(depths) == threads, smp
            assert all(value >= 0 for value in nodes + depths), smp
            assert sum(nodes) == int(smp["total_nodes"]) == result["signature"][-1], smp
            assert nodes[0] == int(smp["leader_nodes"]), smp
    result["counters"] = counters
    return result


def search(engine, board, command="go depth 4", **expected):
    """Fence each finite search so duplicate bestmove output cannot escape."""
    engine.send(command)
    result = validate(engine.until("bestmove ", timeout=30), board, **expected)
    engine.send("stop")
    ready(engine)
    return result


def run(executable, network):
    checks = 0
    with Engine(executable) as engine:
        advertised = engine.handshake()
        assert advertised.count(f"option name {OPTION} type check default false") == 1, advertised
        option(engine, "EvalFile", network)
        option(engine, "Hash", 1)
        option(engine, "Late Move Reductions", "false")
        option(engine, "SyzygyProbeLimit", 0)
        option(engine, "Search Diagnostics", "true")
        board = position(engine)
        baseline = search(engine, board, enabled=False)
        checks += 1

        # Rejected spellings must retain the actual option, in either state.
        for value in ("1", "True", "invalid", None):
            option(engine, OPTION, value, error=True)
            search(engine, board, "go depth 2", enabled=False)
            checks += 1
        option(engine, OPTION, "true")
        option(engine, OPTION, "invalid", error=True)
        cold = search(engine, board, enabled=True)
        assert all(cold["counters"][key] > 0 for key in ("lookups", "nonzero", "updates")), cold
        checks += 1

        # Policy changes must isolate cached bounds and both kinds of history.
        option(engine, OPTION, "false")
        restored = search(engine, board, enabled=False)
        assert restored["signature"] == baseline["signature"], (restored, baseline)
        option(engine, OPTION, "true")
        replayed = search(engine, board, enabled=True)
        assert replayed == cold, (replayed, cold)
        checks += 2

        # Diagnostics report work but cannot change it. Clear Hash and newgame
        # reset learning, while retaining the enabled option and allocation.
        option(engine, "Clear Hash")
        option(engine, "Search Diagnostics", "false")
        silent = search(engine, board, enabled=True, diagnostics=False)
        assert silent["signature"] == cold["signature"], (silent, cold)
        option(engine, "Search Diagnostics", "true")
        for reset in ("setoption name Clear Hash", "ucinewgame"):
            engine.send(reset)
            ready(engine)
            board = position(engine)
            repeated = search(engine, board, enabled=True)
            assert repeated == cold, (reset, repeated, cold)
            checks += 1
        checks += 1

        # There is no preceding context at the root or in quiescence, even
        # after a populated previous search.
        shallow = search(engine, board, "go depth 1", enabled=True)
        assert all(shallow["counters"][key] == 0 for key in ("lookups", "nonzero", "updates")), shallow
        checks += 1

        # A small exposed corpus exercises both sides and quiet/tactical trees.
        # At full width, reordering may alter ties/PVs but not minimax scores.
        for fen in (chess.STARTING_FEN,
                    "2r3k1/5pp1/p3p2p/1p1nP3/3P4/P2B2P1/1P3P1P/2R3K1 w - - 0 30"):
            for start in (chess.Board(fen), chess.Board(fen).mirror()):
                scores = []
                for enabled in (False, True):
                    option(engine, OPTION, str(enabled).lower())
                    option(engine, "Clear Hash")
                    board = position(engine, start.fen())
                    result = search(engine, board, enabled=enabled)
                    assert result["scores"][-1][0] == 4, result
                    scores.append(result["scores"])
                assert scores[0] == scores[1], (fen, scores)
                checks += 1

        # Promotions, captures, en passant and castling must retain legal PVs;
        # mirrored roots exercise the black piece/color indexing as well.
        for fen, coordinate in (
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
            ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8q"),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"),
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
        ):
            for mirrored in (False, True):
                start = chess.Board(fen)
                move = chess.Move.from_uci(coordinate)
                if mirrored:
                    start = start.mirror()
                    move = chess.Move(chess.square_mirror(move.from_square),
                                      chess.square_mirror(move.to_square), move.promotion)
                option(engine, "Clear Hash")
                board = position(engine, start.fen())
                search(engine, board, "go depth 3 searchmoves " + move.uci(),
                       enabled=True, allowed={move.uci()})
                checks += 1

        for fen, expected in (
            ("k7/8/1QK5/8/8/8/8/8 w - - 99 1", ("mate", 1)),
            ("7k/6Q1/5K2/8/8/8/8/8 b - - 100 1", ("mate", 0)),
            ("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1", ("cp", 0)),
            ("7k/8/5K2/8/8/8/8/R7 w - - 100 1", ("cp", 0)),
        ):
            for start in (chess.Board(fen), chess.Board(fen).mirror()):
                option(engine, "Clear Hash")
                board = position(engine, start.fen())
                search(engine, board, "go depth 3", enabled=True, score=expected)
                checks += 1
        board = position(engine, history=("g1f3", "g8f6", "f3g1", "f6g8") * 2)
        assert board.is_repetition(3)
        search(engine, board, enabled=True, score=("cp", 0))
        checks += 1

        # Infinite and ponder modes hold a completed result until released;
        # readiness while held must not leak a premature bestmove.
        board = position(engine)
        for command, release in (("go infinite depth 2", "stop"),
                                 ("go ponder depth 2", "ponderhit")):
            engine.send(command)
            partial = engine.until("info depth 2 ", timeout=30)
            engine.send("isready")
            pending = engine.until("readyok", timeout=10)
            assert not any(line.startswith("bestmove ") for line in partial + pending)
            engine.send(release)
            validate(partial + pending[:-1] + engine.until("bestmove ", timeout=10),
                     board, enabled=True)
            ready(engine)
            checks += 1

        # Each worker owns history. Resource totals must remain correct through
        # early cancellation, joined option mutation and pool reconfiguration.
        for threads in (1, 4, 1):
            option(engine, "Threads", threads)
            option(engine, OPTION, "true")
            board = position(engine)
            for limit in (1, 257, 4096):
                option(engine, "Clear Hash")
                search(engine, board, f"go nodes {limit}", enabled=True,
                       threads=threads, node_limit=limit)
                checks += 1
            engine.send("go infinite")
            engine.send("stop")
            validate(engine.until("bestmove ", timeout=10), board, enabled=True, threads=threads)
            ready(engine)
            checks += 1

            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 2 ", timeout=30)
                engine.send(f"setoption name {OPTION} value {str(following).lower()}")
                validate(partial + engine.until("bestmove ", timeout=10), board,
                         enabled=previous, threads=threads)
                ready(engine)
                search(engine, board, "go nodes 257", enabled=following,
                       threads=threads, node_limit=257)
                checks += 1
            for name, value in (("Hash", 2), ("EvalFile", network)):
                option(engine, name, value)
                search(engine, board, "go nodes 257", enabled=True,
                       threads=threads, node_limit=257)
                checks += 1

        # Shutdown is part of the checked lifecycle; sanitizer reports arrive
        # on the same pipe and must not be hidden by a prior legal bestmove.
        engine.send("go infinite")
        engine.send("quit")
        engine.process.wait(timeout=10)
        assert engine.process.returncode == 0
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive()
        remainder = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                remainder.append(line)
        assert not any(marker in line for line in engine.transcript + remainder
                       for marker in SANITIZER_MARKERS), remainder
        checks += 1
    print(f"Continuation History UCI tests passed ({checks} bounded cases; no strength claim)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    args = parser.parse_args()
    if not args.network.is_file():
        parser.error("pinned network missing; run make net before this integration suite")
    run(args.engine.resolve(), args.network.resolve())


if __name__ == "__main__":
    main()
