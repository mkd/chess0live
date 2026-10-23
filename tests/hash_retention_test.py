#!/usr/bin/env python3
"""Bounded TT-retention regression across UCI positions and explicit resets.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One engine/one worker uses a one-megabyte Hash. python-chess independently
validates every PV, bestmove and ponder. Node differences establish cache reuse
on these fixtures, not a speed or playing-strength claim. By default occupancy
is recorded without imposing a generation-age convention. --retained-report
also requires occupied entries to stay visible until an explicit table reset.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


def record(lines, prefix):
    """Require one diagnostic and unique alternating key/value fields."""
    selected = [line for line in lines if line.startswith(prefix)]
    assert len(selected) == 1, (prefix, selected)
    tokens = selected[0][len(prefix):].split()
    assert len(tokens) % 2 == 0, selected
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), selected
    return result


def replay(board, coordinates):
    position = board.copy(stack=True)
    for coordinate in coordinates:
        move = chess.Move.from_uci(coordinate)
        assert move in position.legal_moves, (position.fen(), coordinate)
        position.push(move)


def retained_occupancy(observations):
    """No-clear occupancy is monotone; idle roots cannot change occupied slots.

    This checks every completed iteration and final report, not only a rounded
    end-of-search summary. Saturation is allowed to stay at 1000 indefinitely.
    """
    previous = 0
    for observation in observations:
        if observation.get("reset_before", False):
            previous = 0
        before = previous
        values = [item["hashfull"] for item in observation.get("iterations", [])]
        values.append(observation["hashfull"])
        for value in values:
            assert type(value) is int and previous <= value <= 1000, observation
            if observation["nodes"] == 0:
                assert value == before, observation
            previous = value


def reporting_contract_checks():
    """Exercise saturation and reject reset/overflow corruption without search."""
    sample = [
        {"nodes": 50, "hashfull": 998},
        {"nodes": 20, "hashfull": 1000, "iterations": [{"hashfull": 999}]},
        {"nodes": 0, "hashfull": 1000},
        {"nodes": 30, "hashfull": 1000},
        {"nodes": 0, "hashfull": 0, "reset_before": True},
        {"nodes": 10, "hashfull": 4},
        {"nodes": 0, "hashfull": 0, "reset_before": True},
    ]
    retained_occupancy(sample)
    for index, field, value in ((2, "hashfull", 0), (3, "hashfull", 1001),
                                (4, "hashfull", 1), (6, "hashfull", 4),
                                (1, "iterations", [{"hashfull": 1}])):
        corrupted = [dict(item) for item in sample]
        corrupted[index][field] = value
        try:
            retained_occupancy(corrupted)
        except AssertionError:
            continue
        raise AssertionError(f"Reporting corruption was accepted: {index}, {field}, {value}")


def run(executable, network, retained_report=False):
    """Seven/nine short searches share a deadline, leaving time for cleanup."""
    started = time.monotonic()
    deadline = started + 24
    observations = []
    commands = []
    with Engine(executable) as engine:
        def send(command):
            commands.append(command)
            engine.send(command)

        def until(prefix):
            remaining = deadline - time.monotonic()
            assert remaining > 0, "Hash-retention check exhausted its shared deadline"
            return engine.until(prefix, timeout=remaining)

        def ready():
            send("isready")
            lines = until("readyok")
            assert lines == ["readyok"], lines

        def search(label, board, position_command, depth, *, reset_before=False):
            # Reissuing position must retain the table; preserve the full real
            # history when advancing, because repetition affects safe TT keys.
            send(position_command)
            ready()
            send(f"go depth {depth} nodes 20000")
            lines = until("bestmove ")
            assert not any("error:" in line for line in lines), lines
            best = lines[-1].split()
            assert len(best) in (2, 4), best
            if board.is_game_over():
                assert best == ["bestmove", "0000"], best
            else:
                replay(board, [best[1]])
                if len(best) == 4:
                    assert best[2] == "ponder", best
                    replay(board, [best[1], best[3]])
            iterations = []
            for line in lines:
                if not line.startswith("info depth "):
                    continue
                fields = line.split()
                pv = fields[fields.index("pv") + 1:] if "pv" in fields else []
                replay(board, pv)
                score = fields.index("score")
                iterations.append({"depth": int(fields[2]),
                                   "nodes": int(fields[fields.index("nodes") + 1]),
                                   "score": fields[score + 1:score + 3], "pv": pv,
                                   "hashfull": int(fields[fields.index("hashfull") + 1])})
            summary = record(lines, "info string search-summary v1 ")
            cache = {key: int(value) for key, value in record(lines, "info string cache v1 ").items()}
            final_lines = [line for line in lines if line.startswith("info nodes ")]
            assert len(final_lines) == 1, final_lines
            final_line = final_lines[0].split()
            nodes = int(final_line[2])
            hashfull = int(final_line[final_line.index("hashfull") + 1])
            assert 0 <= hashfull <= 1000 and nodes == int(summary["nodes"]) <= 20000
            assert 0 <= cache["cutoffs"] <= cache["hits"] <= cache["probes"], cache
            assert summary["stop_reason"] == ("terminal" if board.is_game_over() else "depth_limit"), summary
            if not board.is_game_over():
                assert int(summary["completed_depth"]) == depth, summary
            observation = {"label": label, "nodes": nodes, "hashfull": hashfull,
                           "cache": cache, "bestmove": best[1:], "iterations": iterations,
                           "reset_before": reset_before, "raw": lines}
            observations.append(observation)
            send("stop")
            ready()
            return observation

        send("uci")
        handshake = until("uciok")
        assert "option name Clear Hash type button" in handshake
        for name, value in (("EvalFile", network), ("Threads", 1), ("Hash", 1),
                            ("Search Diagnostics", "true"), ("Late Move Reductions", "true"),
                            ("Capture Ordering", "mvv-lva"), ("Countermove Ordering", "false"),
                            ("Null Move Pruning", "false"), ("Reverse Futility Pruning", "false"),
                            ("QSearch SEE Pruning", "false"), ("SyzygyProbeLimit", 0)):
            send(f"setoption name {name} value {value}")
        ready()
        send("ucinewgame")
        root = chess.Board()
        cold = search("cold root", root, "position startpos", 5)
        repeated = search("same position retained", root, "position startpos", 5)
        assert repeated["cache"]["hits"] > 0 and repeated["cache"]["cutoffs"] > 0
        assert repeated["nodes"] < cold["nodes"], (cold, repeated)

        terminal = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        search("terminal intervening position", terminal, "position fen " + terminal.fen(), 1)
        retained = search("root after intervening position", root, "position startpos", 5)
        assert retained["cache"]["hits"] > 0 and retained["cache"]["cutoffs"] > 0
        assert retained["nodes"] < cold["nodes"], (cold, retained)

        moves = retained["iterations"][-1]["pv"][:2]
        assert len(moves) == 2, retained
        child = root.copy()
        for coordinate in moves:
            child.push_uci(coordinate)
        command = "position startpos moves " + " ".join(moves)
        warm_child = search("next move retained", child, command, 3)
        send("setoption name Clear Hash")
        if retained_report:
            search("empty terminal after Clear Hash", terminal,
                   "position fen " + terminal.fen(), 1, reset_before=True)
        cold_child = search("next move after Clear Hash", child, command, 3,
                            reset_before=not retained_report)
        assert warm_child["cache"]["hits"] > 0 and warm_child["cache"]["cutoffs"] > 0
        assert warm_child["nodes"] < cold_child["nodes"], (warm_child, cold_child)
        send("ucinewgame")
        if retained_report:
            search("empty terminal after ucinewgame", terminal,
                   "position fen " + terminal.fen(), 1, reset_before=True)
        new_game = search("next move after ucinewgame", child, command, 3,
                          reset_before=not retained_report)
        assert cold_child["nodes"] == new_game["nodes"]
        assert cold_child["bestmove"] == new_game["bestmove"]
        assert cold_child["iterations"] == new_game["iterations"]
        if retained_report:
            assert cold["hashfull"] > 0, "Fixture must populate the sampled table"
            retained_occupancy(observations)

    elapsed = time.monotonic() - started
    assert elapsed < 30, elapsed
    return {"passed": True, "engine": str(executable),
            "engine_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "network": str(network), "elapsed_seconds": elapsed,
            "threads": 1, "hash_mb": 1, "retained_report": retained_report, "commands": commands,
            "observations": observations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, help="Optional fresh evidence JSON; existing files are rejected")
    parser.add_argument("--retained-report", action="store_true",
                        help="Require all retained occupied entries to remain visible across searches")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("output already exists")
    reporting_contract_checks()
    result = run(args.engine.resolve(), args.network.resolve(), args.retained_report)
    if args.output is not None:
        with args.output.open("x") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    for observation in result["observations"]:
        print(f"{observation['label']}: nodes={observation['nodes']} "
              f"hits={observation['cache']['hits']} cutoffs={observation['cache']['cutoffs']} "
              f"hashfull={observation['hashfull']}")
    print(f"Hash retention passed: {len(result['observations'])} searches, one worker, "
          f"{result['elapsed_seconds']:.3f}s")


if __name__ == "__main__":
    main()
