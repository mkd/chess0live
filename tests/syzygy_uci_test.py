#!/usr/bin/env python3
"""Bounded Syzygy UCI checks against independent legal and tablebase referees.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Install requirements-match.txt and fetch the pinned optional three/four-piece
fixtures first. Only one engine searches at a time, with at most four workers.
The composed cases are development regressions, not strength evidence.
"""
import argparse
from pathlib import Path
import queue
import shutil
import sys
import tempfile

import chess
import chess.syzygy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


# These positions were composed for Phase 4C, independently of owner engines.
# Promotion/EP/rule-50 outcomes are rechecked by python-chess on every run.
QUEEN = "8/8/7k/8/8/8/8/KQ6 w - - 0 1"
UNDERPROMOTION = "8/k1P5/2K5/8/8/8/8/8 w - - 0 1"
PROMOTION = "8/4P3/4K3/8/8/8/8/7k w - - 0 1"
EN_PASSANT = "8/8/8/3pPk2/8/8/K7/8 w - d6 0 1"
RULE50 = "7k/8/5K2/8/8/8/8/R7 w - - 99 1"
MATE_ONE = "7k/8/5KQ1/8/8/8/8/8 w - - 99 1"
MATED = "7k/6Q1/5K2/8/8/8/8/8 b - - 100 1"
STALEMATE = "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1"
REPETITION = "7k/8/8/8/8/8/8/KR6 w - - 0 1"
REVERSIBLE_CYCLE = ("b1b2", "h8h7", "b2b1", "h7h8")


def ready(engine, *, error=False):
    """Fence control changes; only requested option errors may be present."""
    engine.send("isready")
    lines = engine.until("readyok", timeout=10)
    errors = [line for line in lines if line.startswith("info string error:")]
    assert bool(errors) == error, lines
    assert not any(line.startswith("bestmove ") for line in lines), lines
    assert all(line == "readyok" or line.startswith("info string ") for line in lines), lines
    return lines


def option(engine, name, value=None, *, error=False):
    command = "setoption name " + name
    if value is not None:
        command += " value " + str(value)
    engine.send(command)
    return ready(engine, error=error)


def set_position(engine, fen, history=()):
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


def replay(board, moves):
    """Reject illegal coordinates and PVs with independent move generation."""
    current = board.copy(stack=True)
    for coordinate in moves:
        move = chess.Move.from_uci(coordinate)
        assert move in current.legal_moves, (current.fen(), coordinate, moves)
        current.push(move)


def validate_result(lines, board, *, allowed=None, hits=None, score=None):
    """Check public protocol, legal PVs, and monotonic aggregate hit reporting."""
    assert not any("error:" in line for line in lines), lines
    assert all(line.startswith(("info depth ", "info nodes ", "bestmove "))
               for line in lines), lines
    best_lines = [line for line in lines if line.startswith("bestmove ")]
    assert len(best_lines) == 1 and lines[-1] == best_lines[0], lines
    tokens = best_lines[0].split()
    assert len(tokens) in (2, 4), tokens
    best = tokens[1]
    if board.is_checkmate() or board.is_stalemate():
        assert tokens == ["bestmove", "0000"], tokens
    else:
        assert best != "0000", tokens
        if allowed is not None:
            assert best in allowed, (tokens, allowed)
        if len(tokens) == 4:
            assert tokens[2] == "ponder", tokens
            replay(board, [best, tokens[3]])
        else:
            replay(board, [best])

    previous_hits = previous_nodes = -1
    scores = []
    depth_lines = []
    final_lines = []
    for line in lines:
        if not line.startswith("info "):
            continue
        tokens = line.split()
        assert tokens.count("tbhits") == 1, line
        current_hits = int(tokens[tokens.index("tbhits") + 1])
        current_nodes = int(tokens[tokens.index("nodes") + 1])
        assert current_hits >= max(0, previous_hits), (previous_hits, line)
        assert current_nodes >= max(0, previous_nodes), (previous_nodes, line)
        previous_hits, previous_nodes = current_hits, current_nodes
        assert tokens.count("hashfull") == 1, line
        assert 0 <= int(tokens[tokens.index("hashfull") + 1]) <= 1000, line
        if line.startswith("info nodes "):
            final_lines.append(line)
            continue
        depth_lines.append(line)
        score_at = tokens.index("score")
        score_kind, score_value = tokens[score_at + 1:score_at + 3]
        assert score_kind in ("cp", "mate"), line
        int(score_value)
        scores.append((score_kind, score_value))
        pv = tokens[tokens.index("pv") + 1:]
        replay(board, pv)
        if allowed is not None and pv:
            assert pv[0] in allowed, (line, allowed)
    assert len(final_lines) == 1, final_lines
    if hits is True:
        assert previous_hits > 0, lines
    elif hits is False:
        assert previous_hits == 0, lines
    if score is not None:
        assert scores and scores[-1] == score, (scores, score, lines)
    return {"best": best, "hits": previous_hits, "scores": scores,
            "depth_lines": depth_lines, "lines": lines}


def search(engine, fen, command="go depth 3", *, history=(), **expectations):
    option(engine, "Clear Hash")
    board = set_position(engine, fen, history)
    engine.send(command)
    result = validate_result(engine.until("bestmove ", timeout=15), board, **expectations)
    engine.send("stop")
    assert ready(engine) == ["readyok"]
    return result


def verify_fixtures(tables):
    """Validate the test premises without consulting engine output."""
    with chess.syzygy.open_tablebase(str(tables)) as oracle:
        board = chess.Board(QUEEN)
        assert board.is_valid() and oracle.probe_wdl(board) == 2
        assert oracle.probe_dtz(board) > 6  # A DTZ win is not a searched short mate.

        board = chess.Board(UNDERPROMOTION)
        assert oracle.probe_wdl(board) == 2
        queen, rook = board.copy(), board.copy()
        queen.push_uci("c7c8q")
        rook.push_uci("c7c8r")
        assert queen.is_stalemate() and oracle.probe_wdl(queen) == 0
        assert oracle.probe_wdl(rook) == -2

        board = chess.Board(PROMOTION)
        assert board.is_valid() and oracle.probe_wdl(board) == 2
        for coordinate in ("e7e8q", "e7e8r"):
            child = board.copy()
            child.push_uci(coordinate)
            assert child.halfmove_clock == 0 and oracle.probe_wdl(child) == -2

        board = chess.Board(EN_PASSANT)
        assert board.has_legal_en_passant() and oracle.probe_wdl(board) == 0
        without_ep = board.copy()
        without_ep.ep_square = None
        assert oracle.probe_wdl(without_ep) == -2
        for move in list(board.legal_moves):
            child = board.copy()
            child.push(move)
            expected = 0 if move.uci() == "e5d6" else -2
            assert -oracle.probe_wdl(child) == expected, (move, child.fen())

        board = chess.Board(RULE50)
        assert oracle.probe_wdl(board) == 2 and oracle.probe_dtz(board) > 1
        for move in list(board.legal_moves):
            child = board.copy()
            child.push(move)
            assert not child.is_checkmate() and child.halfmove_clock == 100
            assert child.is_fifty_moves()
        board = chess.Board(MATE_ONE)
        board.push_uci("g6g7")
        assert board.is_checkmate() and board.halfmove_clock == 100
        assert chess.Board(MATED).is_checkmate()
        assert chess.Board(STALEMATE).is_stalemate()


def run(executable, network, tables):
    verify_fixtures(tables)
    checks = 0
    with Engine(executable) as engine:
        advertised = engine.handshake()
        for expected in (
            "option name SyzygyPath type string default <empty>",
            "option name SyzygyProbeLimit type spin default 7 min 0 max 7",
            "option name SyzygyProbeDepth type spin default 1 min 1 max 128",
        ):
            assert expected in advertised, (expected, advertised)
        option(engine, "EvalFile", network)
        option(engine, "Hash", 1)
        option(engine, "Search Diagnostics", "false")
        search(engine, QUEEN, hits=False)
        checks += 1

        for name, values in (("SyzygyProbeLimit", (-1, 8, "bad")),
                             ("SyzygyProbeDepth", (0, 129, "bad"))):
            for value in values:
                option(engine, name, value, error=True)
                checks += 1
        option(engine, "SyzygyPath", tables)
        for threads in (1, 4):
            option(engine, "Threads", threads)
            result = search(engine, QUEEN, hits=True)
            assert result["scores"] and all(kind == "cp" for kind, _ in result["scores"]), result
            checks += 1

            # Ranking must be relative to the allowed set. A request containing
            # only a losing move remains valid even when an unrestricted draw exists.
            search(engine, EN_PASSANT, allowed={"e5d6"}, hits=True)
            search(engine, EN_PASSANT, "go depth 3 searchmoves a2a3",
                   allowed={"a2a3"}, hits=True)
            search(engine, UNDERPROMOTION, "go depth 3 searchmoves c7c8q c7c8r",
                   allowed={"c7c8r"}, hits=True)
            search(engine, UNDERPROMOTION, "go depth 3 searchmoves c7c8q",
                   allowed={"c7c8q"}, hits=True, score=("cp", "0"))
            checks += 4

            search(engine, RULE50, hits=True, score=("cp", "0"))
            result = search(engine, MATE_ONE, hits=True, score=("mate", "1"))
            mated = chess.Board(MATE_ONE)
            mated.push_uci(result["best"])
            assert mated.is_checkmate() and mated.halfmove_clock == 100
            search(engine, MATED, hits=False, score=("mate", "0"))
            search(engine, STALEMATE, hits=False, score=("cp", "0"))
            checks += 4

            # ProbeLimit=0 explicitly disables root and interior probing. A
            # three-piece root is also ineligible with a two-piece limit.
            for limit in (0, 2):
                option(engine, "SyzygyProbeLimit", limit)
                search(engine, QUEEN, hits=False)
                checks += 1
            option(engine, "SyzygyProbeLimit", 7)
            # ProbeDepth controls interior probes, not eligibility of root DTZ.
            option(engine, "SyzygyProbeDepth", 128)
            search(engine, QUEEN, hits=True)
            option(engine, "SyzygyProbeDepth", 1)
            checks += 1

        for command in ("ucinewgame", "setoption name Clear Hash"):
            engine.send(command)
            ready(engine)
            search(engine, QUEEN, hits=True)
            checks += 1

        # A root can itself be new while earlier reversible positions repeat.
        # DTZ does not encode those rights, so any duplicate disables root
        # filtering. Keep interior probes off to isolate that guard completely.
        option(engine, "Threads", 1)
        option(engine, "SyzygyProbeDepth", 128)
        history = REVERSIBLE_CYCLE + ("b1b3", "h8g8")
        board = chess.Board(REPETITION)
        for coordinate in history:
            board.push_uci(coordinate)
        assert not board.is_repetition(2) and board.halfmove_clock == 6
        preceding = board.copy(stack=True)
        preceding.pop()
        preceding.pop()
        assert preceding.is_repetition(2)
        search(engine, REPETITION, "go depth 1", history=history, hits=False)
        search(engine, board.fen(), "go depth 1", hits=True)
        history = REVERSIBLE_CYCLE * 2
        board = chess.Board(REPETITION)
        for coordinate in history:
            board.push_uci(coordinate)
        assert board.is_repetition(3)
        search(engine, REPETITION, "go depth 1", history=history,
               hits=False, score=("cp", "0"))
        checks += 3

        # A WDL-only directory cannot establish decisive root DTZ rankings;
        # the drawn EP root can still resolve its zero DTZ from WDL. Depth128
        # isolates that root-only control (0 and 1 hits respectively). Extra
        # hits with Depth1 must come from interior probes after zeroing moves.
        with tempfile.TemporaryDirectory(prefix="chess0live-syzygy-wdl-") as directory:
            wdl_tables = Path(directory)
            for source in tables.glob("*.rtbw"):
                shutil.copyfile(source, wdl_tables / source.name)
            assert (wdl_tables / "KPvKP.rtbw").is_file()
            assert not list(wdl_tables.glob("*.rtbz"))
            option(engine, "SyzygyPath", wdl_tables)
            for fen, root_hits in ((PROMOTION, 0), (EN_PASSANT, 1)):
                option(engine, "SyzygyProbeDepth", 128)
                control = search(engine, fen, "go depth 4", hits=bool(root_hits))
                assert control["hits"] == root_hits, control
                option(engine, "SyzygyProbeDepth", 1)
                interior = search(engine, fen, "go depth 4", hits=True)
                assert interior["hits"] > control["hits"], (control, interior)
                checks += 2
            # Release file mappings before the temporary directory is removed.
            option(engine, "SyzygyPath", tables)
        option(engine, "Threads", 4)

        option(engine, "SyzygyPath", "<empty>")
        search(engine, QUEEN, hits=False)
        checks += 1
        option(engine, "SyzygyPath", tables)
        with tempfile.TemporaryDirectory(prefix="chess0live-syzygy-uci-") as directory:
            missing = Path(directory) / "absent"
            option(engine, "SyzygyPath", missing, error=True)
            search(engine, QUEEN, hits=False)
            checks += 1
        option(engine, "SyzygyPath", tables)

        # Path/limit changes while a real probe-enabled search is pending must
        # stop and join helpers before freeing or replacing backend state.
        for name, value, expected_hits in (
            ("SyzygyPath", "<empty>", False),
            ("SyzygyPath", tables, True),
            ("SyzygyProbeLimit", 0, False),
            ("SyzygyProbeLimit", 7, True),
            ("SyzygyProbeDepth", 2, True),
        ):
            board = set_position(engine, QUEEN)
            engine.send("go infinite")
            # Wait for actual search output so this exercises both dispatch and
            # an already initialized/probed worker, not only pre-start cancel.
            initial = engine.until("info depth 1 ", timeout=10)
            engine.send(f"setoption name {name} value {value}")
            validate_result(initial + engine.until("bestmove ", timeout=10), board)
            ready(engine)
            search(engine, QUEEN, hits=expected_hits)
            checks += 1

        engine.send("quit")
        engine.process.wait(timeout=5)
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
        assert not remaining, remaining
        for line in engine.transcript:
            assert not any(marker in line for marker in
                           ("Sanitizer", "runtime error:", "data race")), line
    print(f"Syzygy UCI tests passed ({checks} bounded searches/options/lifecycle cases)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--tables", type=Path, default=ROOT / "tablebases/test")
    args = parser.parse_args()
    if not args.engine.is_file() or not args.network.is_file():
        parser.error("engine/network missing; build the engine and run make net")
    if not (args.tables / "KQvK.rtbw").is_file():
        parser.error("Syzygy fixtures missing; fetch the pinned optional test tables first")
    run(args.engine.resolve(), args.network.resolve(), args.tables.resolve())


if __name__ == "__main__":
    main()
