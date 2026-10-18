#!/usr/bin/env python3
"""Bounded countermove-ordering checks with an independent legal-move referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Install requirements-match.txt, then provide an engine and optional network.
Only one engine searches at a time, with at most four workers. These exposed
regressions check protocol, ordering isolation, and finite search invariants;
they do not establish playing strength or demand deterministic parallel search.
"""
import argparse
from pathlib import Path
import queue
import sys

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


PREFIX = "info string countermove v1 "
OPTION = "Countermove Ordering"
SANITIZER_MARKERS = ("Sanitizer", "runtime error:", "data race")


def fields(line, prefix):
    """Decode public key/value diagnostics without silently accepting repeats."""
    assert line.startswith(prefix), line
    tokens = line[len(prefix):].split()
    assert len(tokens) % 2 == 0, line
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), line
    return result


def ready(engine, *, error=False):
    engine.send("isready")
    lines = engine.until("readyok", timeout=15)
    if error:
        assert len(lines) == 2 and lines[0].startswith("info string error:"), lines
    else:
        assert lines == ["readyok"], lines
    return lines


def option(engine, name, value=None, *, error=False):
    command = "setoption name " + name
    if value is not None:
        command += " value " + str(value)
    engine.send(command)
    return ready(engine, error=error)


def position(engine, fen=chess.STARTING_FEN, history=()):
    """Replay complete history independently so repetition tests retain rights."""
    board = chess.Board(fen)
    assert board.is_valid(), fen
    command = "position fen " + fen
    if history:
        command += " moves " + " ".join(history)
    for coordinate in history:
        move = chess.Move.from_uci(coordinate)
        assert move in board.legal_moves, (board.fen(), coordinate)
        board.push(move)
    engine.send(command)
    return board


def replay(board, coordinates):
    current = board.copy(stack=True)
    for coordinate in coordinates:
        move = chess.Move.from_uci(coordinate)
        assert move in current.legal_moves, (current.fen(), coordinate, coordinates)
        current.push(move)
    return current


def validate(lines, board, *, enabled, diagnostics=True, allowed=None,
             node_limit=None, score=None):
    """Validate legal output, accounting, diagnostics, and exact score labels."""
    prefixes = ("info depth ", "info nodes ", "bestmove ",
                "info string cache v1 ", "info string ordering v1 ",
                "info string lmr v1 ", "info string smp v1 ",
                "info string search-iteration v1 ",
                "info string search-summary v1 ", PREFIX)
    assert all(line.startswith(prefixes) for line in lines), lines
    assert not any(marker in line for line in lines for marker in SANITIZER_MARKERS), lines
    best_lines = [line for line in lines if line.startswith("bestmove ")]
    assert len(best_lines) == 1 and lines[-1] == best_lines[0], lines
    best = best_lines[0].split()
    assert len(best) in (2, 4), best
    if board.is_checkmate() or board.is_stalemate():
        assert best == ["bestmove", "0000"], best
    else:
        assert best[1] != "0000", best
        if allowed is not None:
            assert best[1] in allowed, (best, allowed)
        if len(best) == 4:
            assert best[2] == "ponder", best
            replay(board, (best[1], best[3]))
        else:
            replay(board, (best[1],))

    signatures, scores = [], []
    previous_depth = previous_nodes = -1
    final = []
    for line in lines:
        if not line.startswith(("info depth ", "info nodes ")):
            continue
        tokens = line.split()
        nodes = int(tokens[tokens.index("nodes") + 1])
        assert nodes >= max(0, previous_nodes), line
        previous_nodes = nodes
        assert tokens.count("hashfull") == tokens.count("tbhits") == 1, line
        assert 0 <= int(tokens[tokens.index("hashfull") + 1]) <= 1000, line
        assert int(tokens[tokens.index("tbhits") + 1]) == 0, line
        if line.startswith("info nodes "):
            final.append(fields(line, "info "))
            continue
        depth = int(tokens[tokens.index("depth") + 1])
        assert depth > previous_depth, line
        previous_depth = depth
        score_at = tokens.index("score")
        score_kind = tokens[score_at + 1]
        score_value = int(tokens[score_at + 2])
        assert score_kind in ("cp", "mate"), line
        pv = tokens[tokens.index("pv") + 1:]
        replay(board, pv)
        if allowed is not None and pv:
            assert pv[0] in allowed, (line, allowed)
        scores.append((depth, score_kind, score_value))
        signatures.append((depth, int(tokens[tokens.index("seldepth") + 1]),
                           nodes, score_kind, score_value, tuple(pv)))
    assert len(final) == 1, lines
    total = int(final[0]["nodes"])
    if node_limit is not None:
        assert total == node_limit, (total, node_limit, lines)
    if score is not None:
        assert scores and scores[-1][1:] == score, (scores, score, lines)

    counter_lines = [line for line in lines if line.startswith(PREFIX)]
    counters = None
    if enabled and diagnostics:
        assert len(counter_lines) == 1, lines
        counters = fields(counter_lines[0], PREFIX)
        assert set(counters) == {"enabled", "lookups", "matches", "updates"}, counters
        assert counters["enabled"] == "true", counters
        counters = {key: int(counters[key]) for key in ("lookups", "matches", "updates")}
        assert 0 <= counters["matches"] <= counters["lookups"], counters
        assert counters["updates"] >= 0, counters
    else:
        assert not counter_lines, lines
    if diagnostics:
        summaries = [line for line in lines if line.startswith("info string search-summary v1 ")]
        assert len(summaries) == 1 and lines[-2] == summaries[0], lines
        summary = fields(summaries[0], "info string search-summary v1 ")
        assert int(summary["nodes"]) == total, (summary, final)
        lmr = [fields(line, "info string lmr v1 ") for line in lines
               if line.startswith("info string lmr v1 ")]
        assert len(lmr) == 1 and lmr[0]["enabled"] == "false", lmr
    else:
        assert not any(line.startswith("info string ") for line in lines), lines
    return {"signature": (tuple(signatures), tuple(best), total),
            "scores": scores, "counters": counters}


def search(engine, board, command="go depth 4", **expected):
    engine.send(command)
    result = validate(engine.until("bestmove ", timeout=30), board, **expected)
    engine.send("stop")
    ready(engine)
    return result


def fixture_positions():
    """Small composed/reachable corpus covers both colors and quiet/tactical play."""
    opening = chess.Board()
    for coordinate in ("c2c4", "e7e5", "b1c3", "g8f6", "g2g3", "d7d5"):
        opening.push_uci(coordinate)
    originals = [
        chess.Board(), opening,
        chess.Board("2r3k1/5pp1/p3p2p/1p1nP3/3P4/P2B2P1/1P3P1P/2R3K1 w - - 0 30"),
        chess.Board("8/2p5/1p1k4/p2P4/P1P1K3/1P6/8/8 w - - 0 40"),
        chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2"),
    ]
    return [board.fen() for original in originals for board in (original, original.mirror())]


def run(executable, network):
    checks = 0
    with Engine(executable) as engine:
        advertised = engine.handshake()
        assert f"option name {OPTION} type check default false" in advertised, advertised
        option(engine, "EvalFile", network)
        option(engine, "Hash", 1)
        option(engine, "Late Move Reductions", "false")
        option(engine, "SyzygyProbeLimit", 0)
        option(engine, "Search Diagnostics", "true")
        board = position(engine)
        baseline = search(engine, board, enabled=False)
        checks += 1

        # Rejected input must preserve the active value. No implicit numerical
        # or missing-value spelling is accepted for this boolean option.
        for value in ("invalid", "1", None):
            option(engine, OPTION, value, error=True)
            search(engine, board, "go depth 2", enabled=False)
            checks += 1
        option(engine, OPTION, "true")
        option(engine, OPTION, "invalid", error=True)
        on_cold = search(engine, board, enabled=True)
        checks += 1

        # Switching policies clears the shared cache and each worker's learned
        # state. Neither direction requires the caller to issue Clear Hash.
        option(engine, OPTION, "false")
        restored = search(engine, board, enabled=False)
        assert restored["signature"] == baseline["signature"], (restored, baseline)
        checks += 1
        option(engine, OPTION, "true")
        replayed = search(engine, board, enabled=True)
        assert replayed["signature"] == on_cold["signature"], (replayed, on_cold)
        assert replayed["counters"] == on_cold["counters"]
        checks += 1

        # Diagnostic collection cannot change ordering or work. A depth-one
        # search has no non-root positive-depth child: quiescence must not use
        # countermove lookup/update state, even after a populated earlier search.
        option(engine, "Clear Hash")
        option(engine, "Search Diagnostics", "false")
        silent = search(engine, board, enabled=True, diagnostics=False)
        assert silent["signature"] == on_cold["signature"], (silent, on_cold)
        option(engine, "Search Diagnostics", "true")
        depth_one = search(engine, board, "go depth 1", enabled=True)
        assert depth_one["counters"] == {"lookups": 0, "matches": 0, "updates": 0}, depth_one
        checks += 2

        total_counters = {"lookups": 0, "matches": 0, "updates": 0}
        for fen in fixture_positions():
            results = []
            for enabled in (False, True):
                option(engine, OPTION, str(enabled).lower())
                option(engine, "Clear Hash")
                board = position(engine, fen)
                result = search(engine, board, enabled=enabled)
                assert result["scores"][-1][0] == 4, (fen, result)
                results.append(result)
                if enabled:
                    for key in total_counters:
                        total_counters[key] += result["counters"][key]
            assert results[0]["scores"] == results[1]["scores"], (fen, results)
            checks += 1
        assert all(value > 0 for value in total_counters.values()), total_counters

        # Restrict roots to force special flags through the search stack. The
        # independent referee checks the full PV and both colored reflections.
        for fen, coordinate in (
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q"),
            ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8r"),
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
            ("k7/8/2K5/1Q6/8/8/8/8 b - - 0 1", ("mate", -1)),
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

        for threads in (1, 4):
            option(engine, "Threads", threads)
            option(engine, OPTION, "true")
            board = position(engine)
            for limit in (1, 257, 4096):
                option(engine, "Clear Hash")
                search(engine, board, f"go nodes {limit}", enabled=True, node_limit=limit)
                checks += 1
            engine.send("go infinite")
            engine.send("stop")
            validate(engine.until("bestmove ", timeout=10), board, enabled=True)
            ready(engine)
            checks += 1
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

            # Mutating the option while work is active must join the old search
            # before reusing worker-local state. Validate each old/new policy.
            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 3 ", timeout=30)
                engine.send(f"setoption name {OPTION} value {str(following).lower()}")
                validate(partial + engine.until("bestmove ", timeout=10), board, enabled=previous)
                ready(engine)
                search(engine, board, "go nodes 257", enabled=following, node_limit=257)
                checks += 1

        # Catch shutdown reports as well as ordinary searches: stderr shares
        # stdout in this harness, so a successful bestmove cannot hide a race.
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
    print(f"Countermove UCI tests passed ({checks} bounded cases; no strength claim)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path,
                        default=ROOT / "networks/nn-1a298aa575a0.nnue")
    args = parser.parse_args()
    if not args.network.is_file():
        parser.error("pinned network missing; run make net before this integration suite")
    run(args.engine.resolve(), args.network.resolve())


if __name__ == "__main__":
    main()
