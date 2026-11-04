#!/usr/bin/env python3
"""Bounded delta-policy protocol, state and lifecycle checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Uses this project's original exposed rule corpus and independent legal referee.
Direct interior-branch coverage belongs to qsearch_delta_search_test.cpp. Legal
output and finite parity checks do not establish tactical or playing strength.
"""
import argparse
from pathlib import Path
import queue

import null_move_uci_test as common
import qsearch_see_uci_test as see
from probcut_uci_test import probcut_record, PREFIX as PROBCUT_PREFIX

ROOT = Path(__file__).resolve().parents[1]
OPTION = "QSearch Delta Pruning"
PREFIX = "info string qsearchdelta v1 "
COUNTERS = ("eligible_nodes", "candidates", "pruned", "protected_checks", "protected_terminals")


def validate(lines, board, *, enabled, diagnostics=True, see_enabled=False,
             probcut_enabled=False, **expected):
    records = [line for line in lines if line.startswith(PREFIX)]
    counters = None
    if enabled and diagnostics:
        raw = common.only_record(lines, PREFIX)
        assert set(raw) == {"enabled", *COUNTERS} and raw["enabled"] == "true", raw
        assert all(raw[key].isascii() and raw[key].isdecimal() for key in COUNTERS), raw
        counters = {key: int(raw[key]) for key in COUNTERS}
        assert all(value < 2**64 for value in counters.values()), counters
        assert sum(counters[key] for key in COUNTERS[2:]) <= counters["candidates"], counters
        assert lines.index(records[0]) < len(lines) - 2, lines
    else:
        assert not records, records
    probcut_record(lines, probcut_enabled and diagnostics)
    ordinary = [line for line in lines if not line.startswith((PREFIX, PROBCUT_PREFIX))]
    result = see.validate(ordinary, board, enabled=see_enabled,
                          diagnostics=diagnostics, **expected)
    result["delta"] = counters
    return result


def search(engine, board, command="go depth 4", *, timeout=30, **expected):
    engine.send(command)
    result = validate(engine.until("bestmove ", timeout=timeout), board, **expected)
    engine.send("stop")
    common.ready(engine)
    return result


def run(executable, network, workers, timeout):
    checks = 0
    with common.Engine(executable) as engine:
        assert f"option name {OPTION} type check default false" in engine.handshake()
        for name, value in (("EvalFile", network), ("Hash", 1), ("Threads", 1),
                            ("Late Move Reductions", "false"), ("SyzygyProbeLimit", 0),
                            ("Search Diagnostics", "true")):
            common.option(engine, name, value)
        board = common.position(engine)
        baseline = search(engine, board, enabled=False)
        for value in ("invalid", "1", None):
            common.option(engine, OPTION, value, error=True)
            search(engine, board, "go depth 2", enabled=False)
            checks += 1
        common.option(engine, OPTION, "true")
        common.option(engine, OPTION, "invalid", error=True)
        active = search(engine, board, enabled=True)
        common.option(engine, OPTION, "false")
        assert search(engine, board, enabled=False)["signature"] == baseline["signature"]
        common.option(engine, OPTION, "true")
        assert search(engine, board, enabled=True)["signature"] == active["signature"]
        checks += 3
        common.option(engine, "Clear Hash")
        before = common.root_evaluation(engine)
        active = search(engine, board, "go depth 6 nodes 60000", enabled=True,
                        node_ceiling=60000, timeout=timeout)
        assert active["delta"]["eligible_nodes"] > 0, active
        assert common.root_evaluation(engine) == before
        common.option(engine, "Clear Hash")
        common.option(engine, "Search Diagnostics", "false")
        silent = search(engine, board, "go depth 6 nodes 60000", enabled=True,
                        diagnostics=False, node_ceiling=60000, timeout=timeout)
        assert silent["signature"] == active["signature"], (silent, active)
        common.option(engine, "Search Diagnostics", "true")
        print("delta activation:", active["delta"])
        checks += 2

        for case, expected_board in see.expand_cases():
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
                    assert all(value == 0 for value in result["delta"].values()), (case, result)
                engine.send("d")
                assert engine.until("fen ")[-1] == "fen " + board.fen(en_passant="fen")
                results.append(result)
            if case.get("exact_off_parity"):
                assert results[0]["signature"] == results[1]["signature"], (case, results)
            checks += 1

        for threads in ((1,) if workers == 1 else (1, 4)):
            common.option(engine, "Threads", threads)
            common.option(engine, OPTION, "true")
            board = common.position(engine)
            for limit in (1, 257, 4096):
                common.option(engine, "Clear Hash")
                search(engine, board, f"go nodes {limit}", enabled=True,
                       threads=threads, node_limit=limit)
                checks += 1
            for command, release in (("go infinite depth 2", "stop"),
                                     ("go ponder depth 2", "ponderhit")):
                engine.send(command)
                partial = engine.until("info depth 2 ", timeout=timeout)
                engine.send("isready")
                pending = engine.until("readyok", timeout=10)
                assert not any(line.startswith("bestmove ") for line in partial + pending)
                engine.send(release)
                validate(partial + pending[:-1] + engine.until("bestmove ", timeout=10),
                         board, enabled=True, threads=threads)
                common.ready(engine)
                checks += 1
            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 3 ", timeout=timeout)
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
            for name in ("Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut"):
                common.option(engine, name, "true")
            search(engine, board, "go depth 6 nodes 60000", enabled=True, null_enabled=True,
                   reverse_enabled=True, see_enabled=True, probcut_enabled=True,
                   node_ceiling=60000, threads=threads, timeout=timeout)
            for name in ("Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut"):
                common.option(engine, name, "false")
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
    print(f"QSearch delta UCI passed ({checks} bounded cases; up to {workers} workers; no strength claim)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--threads", type=int, choices=(1, 4), default=4)
    parser.add_argument("--activation-timeout", type=common.activation_seconds, default=30)
    args = parser.parse_args()
    run(args.engine.resolve(), args.network.resolve(), args.threads, args.activation_timeout)
