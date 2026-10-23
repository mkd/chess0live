#!/usr/bin/env python3
"""Bounded ProbCut protocol, draw and tactical checks with an independent referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One engine searches at a time, with one/four workers. Explicit interior probe
activation and rejected quiet-defense evidence are covered by the C++ suite;
these public checks require legal lifecycle behavior, not a favorable result.
"""
import argparse
from pathlib import Path
import queue

import chess

from smp_uci_test import (Engine, configure, fence, fields, only_record,
                          position, ready, replay, validate_result)

ROOT = Path(__file__).resolve().parents[1]
OPTION = "ProbCut"
PREFIX = "info string probcut v1 "
COUNTERS = ("eligible_nodes", "see_evaluations", "qsearches", "qsearch_passes",
            "searches", "cutoffs", "rejected")


def probcut_record(lines, enabled):
    """Validate this option without broadening the frozen SMP output contract."""
    records = [line for line in lines if line.startswith(PREFIX)]
    if not enabled:
        assert not records, records
        return None
    result = only_record(lines, PREFIX)
    assert set(result) == {"enabled", *COUNTERS} and result["enabled"] == "true", result
    values = {}
    for key in COUNTERS:
        text = result[key]
        assert text.isascii() and text.isdecimal(), result
        values[key] = int(text)
        assert values[key] <= 2**64 - 1, result
    assert values["see_evaluations"] <= 3 * values["eligible_nodes"], values
    assert values["qsearches"] <= values["see_evaluations"], values
    assert values["qsearch_passes"] <= values["qsearches"], values
    assert values["searches"] == values["qsearch_passes"], values
    assert values["cutoffs"] + values["rejected"] <= values["searches"], values
    return values


def checked(lines, board, threads, enabled, *, cap=None, allowed=None):
    counts = probcut_record(lines, enabled)
    ordinary = [line for line in lines if not line.startswith(PREFIX)]
    summary = validate_result(ordinary, board, threads, node_limit=cap, allowed=allowed)
    assert summary["policy"] == "classic" and summary["forecast_active"] == "false", summary
    return summary, counts


def reference_fixtures():
    """Verify the independent chess facts behind the directly probed fixtures."""
    quiet = chess.Board("6k1/1p3ppp/8/2b5/8/4q3/P2N2PP/1R5K w - - 0 1")
    sacrifice = chess.Board("3q2k1/ppp2ppp/8/8/5B2/8/PPP2PPP/RN2K3 w - - 0 1")
    checking = chess.Board("6rk/pp5p/6Q1/8/8/5K2/PP6/RN5R w - - 0 1")
    for mirrored in (False, True):
        board = quiet.mirror() if mirrored else quiet.copy()
        assert board.is_valid(), board.fen()
        capture = chess.Move.from_uci("b8b2" if mirrored else "b1b7")
        assert capture in board.legal_moves and board.is_capture(capture)
        board.push(capture)
        defense = chess.Move.from_uci("e6g8" if mirrored else "e3g1")
        assert defense in board.legal_moves and not board.is_capture(defense)
        board.push(defense)
        assert board.is_checkmate(), board.fen()
        board = sacrifice.mirror() if mirrored else sacrifice.copy()
        assert board.is_valid(), board.fen()
        first = chess.Move.from_uci("f5c2" if mirrored else "f4c7")
        reply = chess.Move.from_uci("d1c2" if mirrored else "d8c7")
        assert first in board.legal_moves and board.is_capture(first)
        board.push(first)
        assert reply in board.legal_moves and board.is_capture(reply)
        board = checking.mirror() if mirrored else checking.copy()
        assert board.is_valid(), board.fen()
        capture = chess.Move.from_uci("h8h2" if mirrored else "h1h7")
        assert capture in board.legal_moves and board.is_capture(capture)
        board.push(capture)
        assert board.is_checkmate(), board.fen()


def run(binary, network):
    reference_fixtures()
    checks = 0
    with Engine(binary) as engine:
        identity = engine.handshake()
        assert [line for line in identity if line.startswith(f"option name {OPTION} ")] == [
            f"option name {OPTION} type check default false"], identity
        for name, value in (("Hash", 1), ("EvalFile", network), ("Ponder", "false"),
                            ("Time Policy", "classic"), ("Search Diagnostics", "true"),
                            ("SyzygyProbeLimit", 0)):
            engine.send(f"setoption name {name} value {value}")
        ready(engine)

        def search(board, threads, enabled, command="go nodes 257", cap=257, allowed=None):
            nonlocal checks
            engine.send(command)
            value = checked(engine.until("bestmove ", timeout=10), board, threads, enabled,
                            cap=cap, allowed=allowed)
            fence(engine)
            checks += 1
            return value

        for threads in (1, 4):
            configure(engine, threads)
            engine.send(f"setoption name {OPTION} value false")
            board = position(engine)
            search(board, threads, False)
            for enabled in (True, False):
                engine.send(f"setoption name {OPTION} value {str(enabled).lower()}")
                engine.send(f"setoption name {OPTION} value invalid")
                assert engine.until("info string error:", timeout=5) == [
                    f"info string error: {OPTION} expects true or false"]
                ready(engine)
                search(board, threads, enabled)
            engine.send(f"setoption name {OPTION} value true")
            search(board, threads, True, "go nodes 4096", cap=4096)

            engine.send("go infinite")
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in pending)
            engine.send("stop")
            checked(pending[:-1] + engine.until("bestmove ", timeout=5), board, threads, True)
            fence(engine)
            checks += 1

            engine.send("go ponder depth 2")
            completed = engine.until("info depth 2 ", timeout=10)
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in completed + pending)
            engine.send("ponderhit")
            checked(completed + pending[:-1] + engine.until("bestmove ", timeout=5), board, threads, True)
            fence(engine)
            checks += 1

            for fen in ("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51",
                        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"):
                terminal = position(engine, fen)
                summary, counts = search(terminal, threads, True, "go depth 2", cap=None)
                assert summary["stop_reason"] == "terminal" and int(summary["nodes"]) == 0, summary
                assert not any(counts.values()), counts

            board = position(engine, history=("g1f3", "g8f6", "f3g1", "f6g8") * 2)
            _, counts = search(board, threads, True, "go depth 3", cap=None)
            assert not any(counts.values()), counts
            board = position(engine, "r3k2r/ppp2ppp/8/4p3/8/5N2/PPP2PPP/R3K2R w - - 100 51")
            _, counts = search(board, threads, True, "go depth 3", cap=None)
            assert not any(counts.values()), counts

            for fen, forced in (
                ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
                ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"),
                ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
            ):
                special = position(engine, fen)
                search(special, threads, True, "go depth 3 searchmoves " + forced,
                       cap=None, allowed={forced})

            board = position(engine)
            engine.send("setoption name Search Diagnostics value false")
            engine.send("go nodes 257")
            silent = engine.until("bestmove ", timeout=10)
            assert not any(line.startswith("info string ") for line in silent), silent
            assert not any("error:" in line for line in silent), silent
            best = [line for line in silent if line.startswith("bestmove ")]
            assert len(best) == 1 and best[0] == silent[-1], silent
            tokens = best[0].split()
            assert len(tokens) in (2, 4), tokens
            if len(tokens) == 4:
                assert tokens[2] == "ponder", tokens
            replay(board, [tokens[1]] + ([tokens[3]] if len(tokens) == 4 else []))
            for line in silent:
                if line.startswith("info depth "):
                    tokens = line.split()
                    replay(board, tokens[tokens.index("pv") + 1:])
            final = [line for line in silent if line.startswith("info nodes ")]
            assert len(final) == 1 and int(fields(final[0], "info ")["nodes"]) == 257, silent
            fence(engine)
            checks += 1
            engine.send("setoption name Search Diagnostics value true")
            search(board, threads, True)

        engine.send("quit")
        engine.process.wait(timeout=5)
        assert engine.process.returncode == 0, engine.process.returncode
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive(), "Output reader failed to reach EOF"
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            assert line is None, line
        for line in engine.transcript:
            assert not any(marker in line for marker in ("Sanitizer", "runtime error:", "data race")), line
    print(f"ProbCut UCI checks passed ({checks} short searches/lifecycle cases)")


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
