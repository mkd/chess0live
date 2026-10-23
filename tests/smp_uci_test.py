#!/usr/bin/env python3
"""Bounded Lazy SMP protocol checks with an independent legal-move referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This is an optional integration suite: install requirements-match.txt, then pass
the engine executable and (optionally) the pinned network path. Only one engine
searches at a time, using at most four workers. Parallel search is deliberately
not required to reproduce a particular score, PV, or work distribution.
"""
from pathlib import Path
import argparse
import queue
import sys
import time

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


def fields(line, prefix):
    """Decode a versioned key/value diagnostic, rejecting duplicate keys."""
    assert line.startswith(prefix), line
    tokens = line[len(prefix):].split()
    assert len(tokens) % 2 == 0, line
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), line
    return result


def only_record(lines, prefix):
    records = [line for line in lines if line.startswith(prefix)]
    assert len(records) == 1, (prefix, records)
    return fields(records[0], prefix)


def replay(board, moves):
    """Check coordinate moves against python-chess, including promotions."""
    position = board.copy(stack=True)
    for coordinate in moves:
        move = chess.Move.from_uci(coordinate)
        assert move in position.legal_moves, (position.fen(), coordinate, moves)
        position.push(move)


def validate_result(lines, board, threads, allowed=None, node_limit=None):
    """One coordinator owns all UCI reports; final accounting covers helpers."""
    assert not any("error:" in line for line in lines), lines
    prefixes = ("info depth ", "info nodes ", "bestmove ",
                "info string cache v1 ", "info string search-iteration v1 ",
                "info string ordering v1 ", "info string lmr v1 ", "info string deep-lmr v1 ",
                "info string smp v1 ", "info string search-summary v1 ")
    assert all(line.startswith(prefixes) for line in lines), lines
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
            replay(board, [best[1], best[3]])
        else:
            replay(board, [best[1]])

    previous_depth, previous_nodes = -1, -1
    for line in lines:
        if not line.startswith("info depth "):
            continue
        tokens = line.split()
        depth = int(tokens[tokens.index("depth") + 1])
        nodes = int(tokens[tokens.index("nodes") + 1])
        assert depth > previous_depth, (previous_depth, line)
        assert nodes >= previous_nodes, (previous_nodes, line)
        previous_depth, previous_nodes = depth, nodes
        assert tokens.count("hashfull") == 1, line
        assert 0 <= int(tokens[tokens.index("hashfull") + 1]) <= 1000, line
        score_at = tokens.index("score")
        assert tokens[score_at + 1] in ("cp", "mate"), line
        int(tokens[score_at + 2])
        pv = tokens[tokens.index("pv") + 1:]
        replay(board, pv)
        if allowed is not None and pv:
            assert pv[0] in allowed, line

    summary = only_record(lines, "info string search-summary v1 ")
    # Every case leaves LMR untouched, including zero-node cancellation and
    # lifecycle cases. Default enablement must survive worker reconfiguration.
    lmr = only_record(lines, "info string lmr v1 ")
    assert lmr["enabled"] == "true", lmr
    counters = {key: int(lmr[key]) for key in
                ("reductions", "researches", "fail_lows", "verified_cutoffs")}
    assert all(value >= 0 for value in counters.values()), counters
    assert counters["researches"] <= counters["reductions"], counters
    assert counters["fail_lows"] + counters["verified_cutoffs"] <= counters["researches"], counters
    total = int(summary["nodes"])
    assert total >= max(0, previous_nodes), (summary, previous_nodes)
    assert lines[-2].startswith("info string search-summary v1 "), lines[-3:]
    final_lines = [line for line in lines if line.startswith("info nodes ")]
    assert len(final_lines) == 1, final_lines
    final_info = fields(final_lines[0], "info ")
    assert int(final_info["nodes"]) == total, (final_info, summary)
    assert int(final_info["time"]) >= 0 and int(final_info["nps"]) >= 0, final_info
    assert 0 <= int(final_info["hashfull"]) <= 1000, final_info
    if node_limit is not None:
        # Each node is reserved from one shared limit, rather than giving every
        # worker a full copy. These roots cannot finish before the node budget.
        assert total == node_limit, (node_limit, summary)
        assert summary["stop_reason"] == "node_limit", summary
    if threads == 1:
        assert not any(line.startswith("info string smp v1 ") for line in lines), lines
    else:
        smp = only_record(lines, "info string smp v1 ")
        assert int(smp["threads"]) == threads, smp
        worker_nodes = [int(value) for value in smp["worker_nodes"].split(",")]
        worker_depths = [int(value) for value in smp["worker_depths"].split(",")]
        assert len(worker_nodes) == len(worker_depths) == threads, smp
        assert all(value >= 0 for value in worker_nodes + worker_depths), smp
        assert sum(worker_nodes) == int(smp["total_nodes"]) == total, smp
        assert worker_nodes[0] == int(smp["leader_nodes"]), smp
        assert worker_depths[0] == int(summary["completed_depth"]), (smp, summary)
    return summary


def fence(engine):
    """Join a finished search and catch reports emitted after its bestmove."""
    engine.send("stop")
    engine.send("isready")
    assert engine.until("readyok", timeout=5) == ["readyok"]


def ready(engine):
    engine.send("isready")
    lines = engine.until("readyok", timeout=10)
    assert not any("error:" in line for line in lines), lines
    return lines


def configure(engine, threads):
    engine.send(f"setoption name Threads value {threads}")
    assert ready(engine) == ["readyok"]


def position(engine, fen=None, history=()):
    board = chess.Board(fen) if fen is not None else chess.Board()
    command = "position fen " + fen if fen is not None else "position startpos"
    if history:
        command += " moves " + " ".join(history)
        for coordinate in history:
            board.push_uci(coordinate)
    engine.send(command)
    return board


def search(engine, board, threads, command, **validation):
    engine.send(command)
    lines = engine.until("bestmove ", timeout=10)
    result = validate_result(lines, board, threads, **validation)
    fence(engine)
    return result, lines


def run(executable, network):
    checks = 0
    with Engine(executable) as engine:
        advertised = engine.handshake()
        assert "option name Threads type spin default 1 min 1 max 64" in advertised
        assert "option name Late Move Reductions type check default true" in advertised
        engine.send(f"setoption name EvalFile value {network}")
        engine.send("setoption name Search Diagnostics value true")
        engine.send("setoption name Hash value 1")
        assert ready(engine) == ["readyok"]

        # Default and restored single-worker paths still use the same interface.
        board = position(engine)
        search(engine, board, 1, "go depth 2")
        checks += 1
        for threads in (2, 4):
            configure(engine, threads)
            for invalid in (0, 65):
                engine.send(f"setoption name Threads value {invalid}")
                engine.send("isready")
                rejected = engine.until("readyok")
                assert len(rejected) == 2 and rejected[0].startswith("info string error:"), rejected
            board = position(engine)
            search(engine, board, threads, "go depth 3")
            checks += 1

            for cap in (1, 7, 257, 4096):
                engine.send("setoption name Clear Hash")
                search(engine, board, threads, f"go nodes {cap}", node_limit=cap)
                checks += 1

            # No sleep is needed to create the dispatch/stop race. Its legal
            # fallback and exactly-one-bestmove contract holds even at 0 nodes.
            for _ in range(3):
                engine.send("go infinite")
                engine.send("stop")
                validate_result(engine.until("bestmove ", timeout=5), board, threads)
                fence(engine)
                checks += 1

            engine.send("go infinite")
            before_stop = ready(engine)
            assert not any(line.startswith("bestmove ") for line in before_stop)
            engine.send("stop")
            validate_result(before_stop[:-1] + engine.until("bestmove ", timeout=5), board, threads)
            fence(engine)
            checks += 1

            # Finite work under infinite/ponder still withholds the result until
            # the matching control command, after all helper work has stopped.
            for command, release in (("go infinite depth 2", "stop"),
                                     ("go ponder depth 2", "ponderhit")):
                engine.send(command)
                completed = engine.until("info depth 2 ", timeout=10)
                pending = ready(engine)
                assert not any(line.startswith("bestmove ") for line in completed + pending)
                engine.send(release)
                validate_result(completed + pending[:-1] + engine.until("bestmove ", timeout=5),
                                board, threads)
                fence(engine)
                checks += 1

            engine.send("go ponder movetime 80")
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in pending)
            started = time.monotonic()
            engine.send("ponderhit")
            validate_result(pending[:-1] + engine.until("bestmove ", timeout=5), board, threads)
            assert time.monotonic() - started < 5
            fence(engine)
            checks += 1

            _, clock_lines = search(engine, board, threads, "go movetime 60")
            assert any(line.startswith("info string search-summary v1 ") for line in clock_lines)
            checks += 1

        # Mutations must stop and join every worker before replacing shared or
        # per-worker state. Each completed search also fences for stray output.
        threads = 4
        for command, next_threads in (
            ("setoption name Clear Hash", 4),
            ("setoption name Hash value 2", 4),
            ("ucinewgame", 4),
            (f"setoption name EvalFile value {network}", 4),
            ("setoption name Threads value 2", 2),
            ("setoption name Threads value 1", 1),
            ("setoption name Threads value 4", 4),
        ):
            board = position(engine)
            engine.send("go infinite")
            engine.send(command)
            validate_result(engine.until("bestmove ", timeout=5), board, threads)
            threads = next_threads
            assert ready(engine) == ["readyok"]
            search(engine, board, threads, "go depth 2")
            checks += 1

        for fen in ("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1",
                    "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1"):
            engine.send("setoption name Clear Hash")
            board = position(engine, fen)
            _, lines = search(engine, board, threads, "go depth 3")
            assert " hashfull 0 " in next(line for line in lines if line.startswith("info depth "))
            checks += 1

        # Shared cache entries preserve full special-move flags. The referee
        # checks PV replay independently rather than assuming a coordinate is
        # legal because one engine worker emitted it.
        for fen, move in (
            (None, "e2e4"),
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"),
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
        ):
            board = position(engine, fen)
            search(engine, board, threads, "go depth 3 searchmoves " + move, allowed={move})
            checks += 1

        board = position(engine, history=("g1f3", "g8f6", "f3g1", "f6g8") * 2)
        summary, _ = search(engine, board, threads, "go depth 3")
        assert board.is_repetition(3) and summary["stop_reason"] == "draw"
        checks += 1

        # Preparation of worker state/network remains charged to a short limit.
        board = position(engine)
        engine.send("setoption name Move Overhead value 0")
        engine.send(f"setoption name EvalFile value {network}")
        summary, _ = search(engine, board, threads, "go movetime 1")
        assert summary["stop_reason"] == "hard_time" and int(summary["nodes"]) == 0, summary
        checks += 1

        # Shutdown while helpers are active must not hang or leave an engine
        # subprocess alive. The context manager remains a bounded cleanup guard.
        engine.send("go infinite")
        engine.send("quit")
        engine.process.wait(timeout=5)
        assert engine.process.returncode == 0
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive(), "stdout reader did not finish after engine exit"
        # Engine merges stderr into stdout. Check even late shutdown diagnostics
        # so a successful protocol result cannot conceal sanitizer findings.
        remaining = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                remaining.append(line)
        validate_result(remaining, board, threads)
        for line in engine.transcript + remaining:
            assert not any(marker in line for marker in
                           ("Sanitizer", "runtime error:", "data race")), line
        checks += 1
    print(f"Lazy SMP UCI tests passed ({checks} bounded searches/lifecycle cases)")


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
