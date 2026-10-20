#!/usr/bin/env python3
"""Bounded live checks for the optional clock-trace build's UCI contract.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Install requirements-match.txt, then pass ENGINE NETWORK. An optional
--normal-engine verifies that ordinary builds omit this diagnostic interface.
One process searches at a time, with at most four workers. The short movetime
case checks clock-accounting identities, not an elapsed-time performance limit.
External harness timeouts only prevent a broken process from hanging the test.
"""
import argparse
from pathlib import Path
import queue
import sys

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine

TRACE = "info string clock-boundary v1 "
PING = "info string clock-ping v1 "
ORDER = (
    "position_begin_ns", "position_end_ns", "go_received_ns",
    "worker_started_ns", "search_started_ns", "leader_finished_ns",
    "joined_ns", "accounted_ns", "search_returned_ns", "reply_ready_ns",
    "bestmove_begin_ns", "bestmove_flushed_ns",
)
FIELDS = {*ORDER, "seq", "hard_stop_ns", "hard_budget_ns", "reported_time_ms"}
SANITIZERS = ("Sanitizer", "runtime error:", "data race")


def fields(line, prefix):
    """Decode complete integer records without accepting duplicate fields."""
    assert line.startswith(prefix), line
    tokens = line[len(prefix):].split()
    assert len(tokens) % 2 == 0, line
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), line
    for key, value in result.items():
        digits = value[1:] if key == "hard_budget_ns" and value.startswith("-") else value
        assert digits and digits.isascii() and digits.isdecimal(), (key, value)
    return {key: int(value) for key, value in result.items()}


def reject_errors(lines):
    assert not any("error:" in line or any(mark in line for mark in SANITIZERS)
                   for line in lines), lines


def ready(engine):
    engine.send("isready")
    lines = engine.until("readyok")
    assert lines == ["readyok"], lines


def configure(engine, network, *, traced):
    engine.send("uci")
    lines = engine.until("uciok")
    reject_errors(lines)
    expected = "id name chess0live 0.1-dev" + (" clock-trace" if traced else "")
    assert [line for line in lines if line.startswith("id name ")] == [expected], lines
    for name, value in (
        ("EvalFile", network), ("Threads", 1), ("Hash", 16),
        ("Move Overhead", 20), ("Time Policy", "classic"),
        ("Ponder", "false"), ("Search Diagnostics", "false"),
        ("Late Move Reductions", "false"), ("Capture Ordering", "mvv-lva"),
        ("Countermove Ordering", "false"), ("Null Move Pruning", "false"),
        ("Reverse Futility Pruning", "false"), ("QSearch SEE Pruning", "false"),
        ("SyzygyPath", "<empty>"), ("SyzygyProbeLimit", 0),
    ):
        engine.send(f"setoption name {name} value {value}")
    engine.send("isready")
    # Configuring an empty tablebase path reports the resulting capacity once.
    # Keep later readiness exchanges strict so stray search output cannot hide.
    assert engine.until("readyok") == [
        "info string Syzygy largest 0 pieces; table files are external", "readyok"]


def position(engine, moves=(), fen=None):
    board = chess.Board(fen) if fen is not None else chess.Board()
    assert board.is_valid(), board.fen()
    command = "position fen " + fen if fen is not None else "position startpos"
    if moves:
        command += " moves " + " ".join(moves)
    for coordinate in moves:
        move = chess.Move.from_uci(coordinate)
        assert move in board.legal_moves, (board.fen(), coordinate)
        board.push(move)
    engine.send(command)
    ready(engine)
    return board


def replay(board, coordinates):
    child = board.copy(stack=True)
    for coordinate in coordinates:
        move = chess.Move.from_uci(coordinate)
        assert move and move in child.legal_moves, (child.fen(), coordinate, coordinates)
        child.push(move)


def validate_moves(lines, board):
    """An independent referee checks every emitted PV and final reply."""
    reject_errors(lines)
    best_lines = [line for line in lines if line.startswith("bestmove ")]
    assert len(best_lines) == 1, lines
    best = best_lines[0].split()
    assert len(best) in (2, 4), best
    if not any(board.legal_moves):
        assert best == ["bestmove", "0000"], best
    else:
        if len(best) == 4:
            assert best[2] == "ponder", best
        replay(board, best[1::2])
    previous_depth, previous_nodes = -1, -1
    for line in lines:
        if not line.startswith("info depth "):
            continue
        tokens = line.split()
        depth = int(tokens[tokens.index("depth") + 1])
        nodes = int(tokens[tokens.index("nodes") + 1])
        assert depth > previous_depth and nodes >= previous_nodes, line
        previous_depth, previous_nodes = depth, nodes
        replay(board, tokens[tokens.index("pv") + 1:])
    finals = [line for line in lines if line.startswith("info nodes ")]
    assert len(finals) == 1, lines
    final = fields(finals[0], "info ")
    assert final["nodes"] >= max(0, previous_nodes), final
    assert 0 <= final["hashfull"] <= 1000, final
    return final


def validate_trace(lines, board, sequence, *, previous=None, same_position=False,
                   timed=False, expected_budget_ns=-1):
    """Assert causal ordering and exact accounting, without speed thresholds."""
    assert lines[-1].startswith(TRACE), lines
    assert sum(line.startswith(TRACE) for line in lines) == 1, lines
    assert lines[-2].startswith("bestmove "), lines
    assert all(line.startswith(("info depth ", "info nodes ", "bestmove ", TRACE))
               for line in lines), lines
    result = fields(lines[-1], TRACE)
    assert set(result) == FIELDS and result["seq"] == sequence, result
    assert all(result[key] > 0 for key in ORDER), result
    assert all(result[a] <= result[b] for a, b in zip(ORDER, ORDER[1:])), result
    hard = result["hard_stop_ns"]
    assert hard == 0 or result["search_started_ns"] <= hard <= result["leader_finished_ns"], result
    if timed:
        # Move Overhead is 20 ms, so a 100-ms request has an 80-ms hard budget.
        assert result["hard_budget_ns"] == 80_000_000 and hard > 0, result
        assert hard >= result["go_received_ns"] + result["hard_budget_ns"], result
    else:
        assert result["hard_budget_ns"] == expected_budget_ns and hard == 0, result
    final = validate_moves(lines[:-1], board)
    assert final["time"] == result["reported_time_ms"], (final, result)
    assert result["reported_time_ms"] == (
        result["accounted_ns"] - result["go_received_ns"]) // 1_000_000, result
    if previous is not None:
        assert result["go_received_ns"] >= previous["bestmove_flushed_ns"], result
        keys = ("position_begin_ns", "position_end_ns")
        if same_position:
            assert all(result[key] == previous[key] for key in keys), (previous, result)
        else:
            assert result["position_begin_ns"] >= previous["bestmove_flushed_ns"], (previous, result)
    return result


def search(engine, board, sequence, command="go depth 3", **expected):
    engine.send(command)
    lines = engine.until(TRACE)
    result = validate_trace(lines, board, sequence, **expected)
    ready(engine)
    return result


def held_search(engine, board, sequence, command, release, **expected):
    """A readiness reply must not release a completed infinite/ponder search."""
    engine.send(command)
    partial = engine.until("info depth 2 ")
    engine.send("isready")
    pending = engine.until("readyok")
    assert not any(line.startswith(("bestmove ", TRACE)) for line in partial + pending)
    reject_errors(partial + pending)
    engine.send(release)
    result = validate_trace(partial + pending[:-1] + engine.until(TRACE),
                            board, sequence, **expected)
    ready(engine)
    return result


def finish(engine):
    """Require clean process exit and a drained, joined reader."""
    engine.send("quit")
    engine.process.wait(timeout=15)
    assert engine.process.returncode == 0, engine.process.returncode
    engine.reader.join(timeout=5)
    assert not engine.reader.is_alive()
    remainder = []
    while True:
        try:
            line = engine.lines.get_nowait()
        except queue.Empty:
            break
        if line is not None:
            remainder.append(line)
    assert not remainder, remainder
    assert not any(mark in line for line in engine.transcript for mark in SANITIZERS)


def run_traced(executable, network):
    with Engine(executable) as engine:
        configure(engine, network, traced=True)
        previous_ping = 0
        for identifier in (0, 7, 18446744073709551615):
            engine.send(f"clockping {identifier}")
            lines = engine.until(PING)
            assert len(lines) == 1, lines
            ping = fields(lines[0], PING)
            assert set(ping) == {"id", "now_ns"}, ping
            assert ping["id"] == identifier and ping["now_ns"] > previous_ping, ping
            previous_ping = ping["now_ns"]
        for command in ("clockping", "clockping -1", "clockping 1.5",
                        "clockping 18446744073709551616", "clockping 1 extra"):
            engine.send(command)
            engine.send("isready")
            assert engine.until("readyok") == [
                "info string error: clockping expects an unsigned integer", "readyok"]

        board = position(engine)
        first = search(engine, board, 1, "go depth 2")
        second = search(engine, board, 2, previous=first, same_position=True)
        board = position(engine, ("e2e4", "e7e5", "g1f3"))
        third = search(engine, board, 3, "go depth 2", previous=second)
        board = position(engine)
        fourth = search(engine, board, 4, "go movetime 100", previous=third, timed=True)

        engine.send("setoption name Threads value 4")
        ready(engine)
        fifth = search(engine, board, 5, previous=fourth, same_position=True)
        engine.send("setoption name Threads value 1")
        ready(engine)
        sixth = held_search(engine, board, 6, "go infinite depth 2", "stop",
                            previous=fifth, same_position=True)
        seventh = held_search(engine, board, 7, "go ponder depth 2", "ponderhit",
                              previous=sixth, same_position=True)

        # Changing position joins the active worker. The departing search must
        # keep the snapshot captured at go, not the new command's begin stamp.
        engine.send("go infinite depth 2")
        partial = engine.until("info depth 2 ")
        engine.send("position startpos moves d2d4 d7d5")
        eighth = validate_trace(partial + engine.until(TRACE), board, 8,
                                previous=seventh, same_position=True)
        ready(engine)
        board = chess.Board()
        board.push_uci("d2d4")
        board.push_uci("d7d5")
        ninth = search(engine, board, 9)
        # The position command began before joining the previous search and
        # completed after its bestmove; its begin need not follow that reply.
        assert eighth["position_begin_ns"] < ninth["position_begin_ns"], (eighth, ninth)
        assert eighth["bestmove_flushed_ns"] <= ninth["position_end_ns"], (eighth, ninth)

        board = position(engine, fen="7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        assert board.is_checkmate()
        tenth = search(engine, board, 10, "go depth 2", previous=ninth)
        board = position(engine)
        # The UCI cap is int32 milliseconds even though SearchLimits uses
        # int64. Explicit depth bounds this request; no huge-clock wait occurs.
        search(engine, board, 11, "go depth 1 movetime 2147483647", previous=tenth,
               expected_budget_ns=(2147483647 - 20) * 1_000_000)
        finish(engine)
    return 11


def run_normal(executable, network):
    with Engine(executable) as engine:
        configure(engine, network, traced=False)
        engine.send("clockping 7")
        ready(engine)
        board = position(engine)
        engine.send("go depth 3")
        lines = engine.until("bestmove ")
        validate_moves(lines, board)
        ready(engine)
        assert not any(line.startswith((TRACE, PING)) for line in engine.transcript)
        finish(engine)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("network", type=Path)
    parser.add_argument("--normal-engine", type=Path)
    args = parser.parse_args()
    for path in (args.engine, args.network, args.normal_engine):
        if path is not None and not path.is_file():
            parser.error(f"missing file: {path}")
    count = run_traced(args.engine.resolve(), args.network.resolve())
    if args.normal_engine:
        run_normal(args.normal_engine.resolve(), args.network.resolve())
    print(f"Clock-boundary UCI contract passed ({count} diagnostic searches; "
          f"normal-build isolation {'checked' if args.normal_engine else 'not requested'}; "
          "no performance or strength claim)")


if __name__ == "__main__":
    main()
