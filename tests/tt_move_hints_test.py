#!/usr/bin/env python3
"""Bounded TT move-hint UCI checks; no timing or strength inference.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Only one engine searches at a time, with at most four workers. python-chess
independently checks every reported PV, best move and ponder move. The Make
target and direct invocation both prepare the pinned referee automatically.
"""
import argparse
from pathlib import Path
import queue
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess
from uci_client import Engine

OPTION = "TT Move Hints"
PREFIX = "info string move-hints v1 "
MARKERS = ("Sanitizer", "runtime error:", "data race", "error:")


def fields(line, prefix):
    assert line.startswith(prefix), line
    tokens = line[len(prefix):].split()
    assert len(tokens) % 2 == 0, line
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), line
    return result


def one(lines, prefix):
    records = [line for line in lines if line.startswith(prefix)]
    assert len(records) == 1, (prefix, records)
    return fields(records[0], prefix)


def replay(board, moves):
    board = board.copy(stack=True)
    for text in moves:
        move = chess.Move.from_uci(text)
        assert move in board.legal_moves, (board.fen(), text)
        board.push(move)


def validate(lines, board, *, enabled, threads=1, diagnostics=True, hash_mb=1,
             node_limit=None, allowed=None, score=None):
    allowed_prefixes = ("info depth ", "info nodes ", "bestmove ",
                        "info string cache v1 ", "info string ordering v1 ",
                        "info string lmr v1 ", "info string smp v1 ",
                        "info string search-iteration v1 ", "info string search-summary v1 ", PREFIX)
    assert all(line.startswith(allowed_prefixes) for line in lines), lines
    assert not any(marker in line for line in lines for marker in MARKERS), lines
    best_lines = [line for line in lines if line.startswith("bestmove ")]
    assert len(best_lines) == 1 and lines[-1] == best_lines[0], lines
    best = best_lines[0].split()
    assert len(best) in (2, 4), best
    if board.is_checkmate() or board.is_stalemate():
        assert best == ["bestmove", "0000"], best
    else:
        assert best[1] != "0000" and (allowed is None or best[1] in allowed), best
        if len(best) == 4:
            assert best[2] == "ponder", best
        replay(board, [best[1]] + ([best[3]] if len(best) == 4 else []))
    iterations = []
    previous_nodes = previous_depth = -1
    for line in lines:
        if not line.startswith("info depth "):
            continue
        words = line.split()
        integer = lambda name: int(words[words.index(name) + 1])
        depth, nodes = integer("depth"), integer("nodes")
        assert depth > previous_depth and nodes >= previous_nodes, line
        previous_depth, previous_nodes = depth, nodes
        assert words.count("hashfull") == words.count("tbhits") == 1, line
        assert 0 <= integer("hashfull") <= 1000 and integer("tbhits") == 0, line
        at = words.index("score")
        kind, value = words[at + 1], int(words[at + 2])
        assert kind in ("cp", "mate"), line
        pv = words[words.index("pv") + 1:]
        replay(board, pv)
        assert allowed is None or not pv or pv[0] in allowed, line
        iterations.append((depth, integer("seldepth"), nodes, kind, value,
                           tuple(pv), integer("hashfull")))
    aggregates = [line for line in lines if line.startswith("info nodes ")]
    assert len(aggregates) == 1, lines
    final = fields(aggregates[0], "info ")
    total = int(final["nodes"])
    assert total >= max(0, previous_nodes) and 0 <= int(final["hashfull"]) <= 1000, final
    assert int(final["tbhits"]) == 0 and int(final["time"]) >= 0 and int(final["nps"]) >= 0, final
    if node_limit is not None:
        assert total == node_limit, (total, node_limit)
    if score is not None:
        assert iterations and iterations[-1][3:5] == score, (iterations, score)
    hint_lines = [line for line in lines if line.startswith(PREFIX)]
    hint = None
    if diagnostics:
        summary = one(lines, "info string search-summary v1 ")
        assert lines[-2].startswith("info string search-summary v1 ") and int(summary["nodes"]) == total
        cache = one(lines, "info string cache v1 ")
        assert int(cache["entry_bytes"]) == 16 and int(cache["bucket_bytes"]) == 64, cache
        slots = int(cache["buckets"])
        assert int(cache["capacity"]) == 4 * slots and int(cache["allocated_bytes"]) == 64 * slots, cache
        if enabled:
            assert len(hint_lines) == 1, lines
            hint = fields(hint_lines[0], PREFIX)
            assert set(hint) == {"enabled", "slots", "allocated_bytes", "probes", "hits", "legal_matches", "stores"}, hint
            assert hint.pop("enabled") == "true", hint
            hint = {key: int(value) for key, value in hint.items()}
            assert hint["slots"] == slots and hint["allocated_bytes"] == 16 * slots, hint
            assert 0 <= hint["legal_matches"] <= hint["hits"] <= hint["probes"] and hint["stores"] >= 0, hint
            assert 80 * slots <= hash_mb * 1024**2, (cache, hint)
        else:
            assert not hint_lines, lines
        if threads == 1:
            assert not any(line.startswith("info string smp v1 ") for line in lines), lines
        else:
            smp = one(lines, "info string smp v1 ")
            worker_nodes = [int(x) for x in smp["worker_nodes"].split(",")]
            worker_depths = [int(x) for x in smp["worker_depths"].split(",")]
            assert int(smp["threads"]) == threads and len(worker_nodes) == len(worker_depths) == threads
            assert all(x >= 0 for x in worker_nodes + worker_depths), smp
            assert sum(worker_nodes) == int(smp["total_nodes"]) == total, smp
            assert worker_nodes[0] == int(smp["leader_nodes"]), smp
            assert worker_depths[0] == int(summary["completed_depth"]), smp
    else:
        assert not any(line.startswith("info string ") for line in lines), lines
    return {"signature": (tuple(iterations), tuple(best), total, int(final["hashfull"])), "hints": hint}


def run(executable, network, timeout):
    checks = 0
    with Engine(executable) as engine:
        def ready(error=False):
            engine.send("isready")
            lines = engine.until("readyok", timeout=timeout)
            assert (len(lines) == 2 and lines[0].startswith("info string error:")) if error else lines == ["readyok"], lines

        def option(name, value=None, error=False):
            engine.send("setoption name " + name + (" value " + str(value) if value is not None else ""))
            ready(error)

        def position(fen=chess.STARTING_FEN, moves=()):
            board = chess.Board(fen)
            assert board.is_valid(), fen
            for coordinate in moves:
                move = chess.Move.from_uci(coordinate)
                assert move in board.legal_moves, coordinate
                board.push(move)
            engine.send("position fen " + fen + (" moves " + " ".join(moves) if moves else ""))
            return board

        def search(board, command="go depth 3", **expected):
            engine.send(command)
            result = validate(engine.until("bestmove ", timeout=timeout), board, **expected)
            ready()
            return result

        advertised = engine.handshake()
        assert "option name TT Move Hints type check default false" in advertised, advertised
        option("EvalFile", network)
        option("Hash", 1)
        option("SyzygyProbeLimit", 0)
        option("Search Diagnostics", "true")
        board = position()
        baseline = search(board, enabled=False)
        for value in ("invalid", "1", None):
            option(OPTION, value, error=True)
            search(board, "go depth 1", enabled=False)
            checks += 1
        option(OPTION, "true")
        option(OPTION, "invalid", error=True)
        on = search(board, enabled=True)
        assert on["hints"]["probes"] > 0 and on["hints"]["stores"] > 0, on
        option(OPTION, "false")
        assert search(board, enabled=False)["signature"] == baseline["signature"]
        option(OPTION, "true")
        repeated = search(board, enabled=True)
        assert repeated == on, (on, repeated)
        checks += 4

        # Diagnostics do not alter cache contents or move ordering.
        option("Clear Hash")
        option("Search Diagnostics", "false")
        assert search(board, enabled=True, diagnostics=False)["signature"] == on["signature"]
        option("Search Diagnostics", "true")
        option("Clear Hash")
        search(board, "go depth 1", enabled=True)
        # Same board key, different rule-50 context: a score-cache hit cannot
        # supply this lookup, but its completed legal move can be a hint.
        board = position(chess.STARTING_FEN.replace("0 1", "1 1"))
        contextual = search(board, "go depth 1", enabled=True)
        assert contextual["hints"]["hits"] == contextual["hints"]["legal_matches"] == 1, contextual
        for command in ("clear", "newgame", "resize"):
            if command == "clear": option("Clear Hash")
            elif command == "newgame": engine.send("ucinewgame"); ready()
            else: option("Hash", 2)
            result = search(board, "go depth 1", enabled=True, hash_mb=2 if command == "resize" else 1)
            assert result["hints"]["hits"] == 0 and result["hints"]["stores"] == 1, result
            checks += 1
        option("Hash", 1)
        checks += 2

        # Draw/terminal handling precedes hint lookups, even with cached data.
        for fen, expected in ((chess.STARTING_FEN.replace("0 1", "100 1"), ("cp", 0)),
                              ("7k/6Q1/5K2/8/8/8/8/8 b - - 100 1", ("mate", 0)),
                              ("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1", ("cp", 0))):
            board = position(fen)
            result = search(board, "go depth 2", enabled=True, score=expected)
            assert all(result["hints"][key] == 0 for key in ("probes", "hits", "legal_matches", "stores")), result
            checks += 1
        board = position(moves=("g1f3", "g8f6", "f3g1", "f6g8") * 2)
        result = search(board, enabled=True, score=("cp", 0))
        assert result["hints"]["probes"] == result["hints"]["stores"] == 0, result
        checks += 1

        # At depth one a restricted root has only quiescence descendants, so
        # neither probing nor storing a hint is permitted anywhere in the tree.
        for fen, coordinate in (("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
                                ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2", "e5d6"),
                                ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1")):
            board = position(fen)
            result = search(board, "go depth 1 searchmoves " + coordinate, enabled=True, allowed={coordinate})
            assert result["hints"]["probes"] == result["hints"]["stores"] == 0, result
            checks += 1

        for threads in (1, 4):
            option("Threads", threads)
            board = position()
            for limit in (1, 257, 4096):
                option("Clear Hash")
                search(board, "go nodes " + str(limit), enabled=True, threads=threads, node_limit=limit)
                checks += 1
            engine.send("go infinite")
            engine.send("stop")
            validate(engine.until("bestmove ", timeout=timeout), board, enabled=True, threads=threads)
            ready()
            checks += 1
            for command, release in (("go infinite depth 2", "stop"), ("go ponder depth 2", "ponderhit")):
                engine.send(command)
                partial = engine.until("info depth 2 ", timeout=timeout)
                engine.send("isready")
                waiting = engine.until("readyok", timeout=timeout)
                assert not any(line.startswith("bestmove ") for line in partial + waiting)
                engine.send(release)
                validate(partial + waiting[:-1] + engine.until("bestmove ", timeout=timeout), board, enabled=True, threads=threads)
                ready()
                checks += 1
            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 2 ", timeout=timeout)
                engine.send("setoption name TT Move Hints value " + str(following).lower())
                validate(partial + engine.until("bestmove ", timeout=timeout), board, enabled=previous, threads=threads)
                ready()
                search(board, "go nodes 257", enabled=following, threads=threads, node_limit=257)
                checks += 1
        engine.send("go infinite")
        engine.send("quit")
        engine.process.wait(timeout=timeout)
        assert engine.process.returncode == 0
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive()
        remainder = []
        while True:
            try: line = engine.lines.get_nowait()
            except queue.Empty: break
            if line is not None: remainder.append(line)
        # Earlier malformed-option checks deliberately emitted error lines;
        # sanitizer/race messages are never expected anywhere in the session.
        assert not any(marker in line for line in engine.transcript + remainder for marker in MARKERS[:-1]), remainder
        checks += 1
    print(f"TT move-hint UCI checks passed ({checks} bounded cases; no strength claim)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--timeout", type=float, default=30, help="Per-operation watchdog; scale for sanitizers")
    args = parser.parse_args()
    if not args.network.is_file() or not 0 < args.timeout <= 120:
        parser.error("Use the pinned network and a finite watchdog in (0, 120] seconds")
    run(args.engine.resolve(), args.network.resolve(), args.timeout)


if __name__ == "__main__":
    main()
