#!/usr/bin/env python3
"""Bounded reverse-futility protocol checks using the independent chess referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Composes the existing null-move suite's protocol/referee helpers and its exposed,
engine-authored rule fixtures. No qualification positions or prior engine assets
are used. One engine searches at a time, with one or four workers. Finite legal
searches and matching signatures do not demonstrate unchanged playing strength.
"""
import argparse
from pathlib import Path
import queue

import null_move_uci_test as common

OPTION = "Reverse Futility Pruning"
PREFIX = "info string reversefutility v1 "
COUNTERS = ("evaluations", "cutoffs")
ROOT = Path(__file__).resolve().parents[1]


def expand_cases():
    """Reuse rule fixtures, checking why whole-tree pruning must be absent.

    Existing zero-probe cases are sparse boards or immediate root draws. Unlike
    a root-only check/capture exclusion, these give a whole-search guarantee.
    """
    result = common.expand_cases()
    for case, board in result:
        if case.get("zero_probes"):
            assert (len(board.piece_map()) <= 7 or board.halfmove_clock >= 100
                    or board.is_repetition(3)), case
    return result


def validate(lines, board, *, enabled, null_enabled=False, diagnostics=True, **expected):
    """Share the referee/accounting parser, independently check RFP records."""
    records = [line for line in lines if line.startswith(PREFIX)]
    counters = None
    if enabled and diagnostics:
        raw = common.only_record(lines, PREFIX)
        assert set(raw) == {"enabled", *COUNTERS}, raw
        assert raw["enabled"] == "true", raw
        counters = {key: int(raw[key]) for key in COUNTERS}
        assert 0 <= counters["cutoffs"] <= counters["evaluations"], counters
        assert lines.index(records[0]) < len(lines) - 2, lines
    else:
        assert not records, lines
    # Removing only this diagnostic allows the established validator to reject
    # every other unexpected line, duplicate result, illegal move or bad sum.
    remaining = [line for line in lines if not line.startswith(PREFIX)]
    result = common.validate(remaining, board, enabled=null_enabled,
                             diagnostics=diagnostics, **expected)
    result["null_counters"] = result["counters"]
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
        advertised = engine.handshake()
        assert f"option name {OPTION} type check default false" in advertised, advertised
        for name, value in (("EvalFile", network), ("Hash", 1), ("Threads", 1),
                            ("Late Move Reductions", "false"), ("Countermove Ordering", "false"),
                            ("Null Move Pruning", "false"), ("SyzygyProbeLimit", 0),
                            ("Search Diagnostics", "true")):
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
        restored = search(engine, board, enabled=False)
        assert restored["signature"] == baseline["signature"], (restored, baseline)
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
            variants = (False, True) if case.get("exact_off_parity") else (True,)
            results = []
            for enabled in variants:
                common.option(engine, OPTION, str(enabled).lower())
                common.option(engine, "Clear Hash")
                board = common.position(engine, case["fen"], case["moves"])
                assert board.fen() == expected_board.fen(), case
                command = f"go depth {case['depth']}"
                if case["searchmoves"]:
                    command += " searchmoves " + " ".join(case["searchmoves"])
                result = search(engine, board, command, enabled=enabled,
                                allowed=set(case["searchmoves"]), score=case.get("score"))
                if enabled and case.get("zero_probes"):
                    assert all(value == 0 for value in result["counters"].values()), (case, result)
                engine.send("d")
                assert engine.until("fen ")[-1] == "fen " + board.fen(en_passant="fen"), case
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
            for command, release in (("go infinite depth 2", "stop"),
                                     ("go ponder depth 2", "ponderhit")):
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
            search(engine, board, "go depth 6 nodes 120000", enabled=True, null_enabled=True,
                   node_ceiling=120000, threads=threads, timeout=activation_timeout)
            common.option(engine, "Null Move Pruning", "false")
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
    print(f"Reverse-futility UCI tests passed ({checks} bounded cases; up to {max_threads} workers; no strength claim)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path, nargs="?")
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--threads", type=int, choices=(1, 4), default=4)
    parser.add_argument("--activation-timeout", type=common.activation_seconds, default=30,
                        help="external wait for bounded activation/composition searches, not engine time limits")
    parser.add_argument("--validate-corpus", action="store_true")
    args = parser.parse_args()
    if args.validate_corpus:
        print(f"Reverse-futility corpus passed ({len(expand_cases())} independently validated colored cases)")
        return
    if args.engine is None:
        parser.error("supply an engine executable or --validate-corpus")
    if not args.network.is_file():
        parser.error("pinned network missing; run make net first")
    run(args.engine.resolve(), args.network.resolve(), args.threads, args.activation_timeout)


if __name__ == "__main__":
    main()
