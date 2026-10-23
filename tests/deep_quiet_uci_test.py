#!/usr/bin/env python3
"""Check opt-in deeper quiet reductions through short, serial UCI searches.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Requires requirements-match.txt. Uses one engine and at most four workers.
Actual extra-tier activation is covered by deep_quiet_search_test.cpp; these
small protocol checks do not require a particular parallel tree or strength.
"""
import argparse
from pathlib import Path
import queue

from smp_uci_test import (Engine, configure, fence, fields, only_record,
                          position, ready, replay, validate_result)

ROOT = Path(__file__).resolve().parents[1]
OPTION = "Deep Quiet Reductions"
DEEP = "info string deep-lmr v1 "
ORDINARY = "info string lmr v1 "
COUNTERS = ("researches", "fail_lows", "verified_cutoffs")


def counters(record, first, enabled):
    """Reject duplicate/extra fields, non-uint64 values and impossible outcomes."""
    keys = (first, *COUNTERS)
    assert set(record) == {"enabled", *keys}, record
    assert record["enabled"] == str(enabled).lower(), record
    result = {}
    for key in keys:
        value = record[key]
        assert value.isascii() and value.isdecimal(), record
        result[key] = int(value)
        assert result[key] <= 2**64 - 1, record
    assert result["researches"] <= result[first], result
    assert result["fail_lows"] + result["verified_cutoffs"] <= result["researches"], result
    return result


def legal_output(lines, board):
    """Independent legality check also usable when diagnostics are disabled."""
    assert not any("error:" in line for line in lines), lines
    best = [line for line in lines if line.startswith("bestmove ")]
    assert len(best) == 1 and best[0] == lines[-1], lines
    tokens = best[0].split()
    assert len(tokens) in (2, 4), tokens
    if len(tokens) == 4:
        assert tokens[2] == "ponder", tokens
    replay(board, [tokens[1]] + ([tokens[3]] if len(tokens) == 4 else []))
    for line in lines:
        if line.startswith("info depth "):
            tokens = line.split()
            replay(board, tokens[tokens.index("pv") + 1:])


def checked_result(lines, board, threads, enabled, *, master=True, node_limit=None):
    if master:
        summary = validate_result(lines, board, threads, node_limit=node_limit)
    else:
        # The shared SMP suite deliberately asserts master LMR's default-on
        # behavior. Check this explicit opt-out separately without weakening it.
        legal_output(lines, board)
        summary = only_record(lines, "info string search-summary v1 ")
        assert lines[-2].startswith("info string search-summary v1 "), lines
        assert int(summary["nodes"]) == node_limit and summary["stop_reason"] == "node_limit", summary
        final_lines = [line for line in lines if line.startswith("info nodes ")]
        assert len(final_lines) == 1, final_lines
        final = fields(final_lines[0], "info ")
        assert int(final["time"]) >= 0 and int(final["nps"]) >= 0, final
        assert int(final["nodes"]) == node_limit, final
        if threads == 1:
            assert not any(line.startswith("info string smp v1 ") for line in lines), lines
        else:
            smp = only_record(lines, "info string smp v1 ")
            nodes = [int(value) for value in smp["worker_nodes"].split(",")]
            assert int(smp["threads"]) == len(nodes) == threads, smp
            assert all(value >= 0 for value in nodes), smp
            assert sum(nodes) == int(smp["total_nodes"]) == node_limit, smp
    assert summary["policy"] == "classic" and summary["forecast_active"] == "false", summary
    ordinary = counters(only_record(lines, ORDINARY), "reductions", master)
    if not master:
        assert not any(ordinary.values()), ordinary
    deep_lines = [line for line in lines if line.startswith(DEEP)]
    if not enabled:
        assert not deep_lines, deep_lines
    else:
        deep = counters(only_record(lines, DEEP), "extra_reductions", True)
        assert deep["extra_reductions"] <= ordinary["reductions"], (deep, ordinary)
        assert all(deep[key] <= ordinary[key] for key in COUNTERS), (deep, ordinary)
        if not master:
            assert not any(deep.values()), deep
    return summary


def run(binary, network):
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

        def search(board, threads, enabled, command="go nodes 257", *, master=True, node_limit=257):
            nonlocal checks
            engine.send(command)
            result = checked_result(engine.until("bestmove ", timeout=10), board, threads,
                                    enabled, master=master, node_limit=node_limit)
            fence(engine)
            checks += 1
            return result

        for threads in (1, 4):
            configure(engine, threads)
            board = position(engine)
            if threads == 4:
                engine.send(f"setoption name {OPTION} value false")
            # First pass leaves the candidate untouched and tests its default.
            search(board, threads, False)
            for enabled in (True, False):
                engine.send(f"setoption name {OPTION} value {str(enabled).lower()}")
                engine.send(f"setoption name {OPTION} value invalid")
                assert engine.until("info string error:", timeout=5) == [
                    f"info string error: {OPTION} expects true or false"]
                ready(engine)
                search(board, threads, enabled)

            engine.send(f"setoption name {OPTION} value true")
            search(board, threads, True, "go nodes 4096", node_limit=4096)
            engine.send("go infinite")
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in pending)
            engine.send("stop")
            checked_result(pending[:-1] + engine.until("bestmove ", timeout=5), board, threads, True)
            fence(engine)
            checks += 1

            engine.send("go ponder depth 2")
            completed = engine.until("info depth 2 ", timeout=10)
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in completed + pending)
            engine.send("ponderhit")
            checked_result(completed + pending[:-1] + engine.until("bestmove ", timeout=5),
                           board, threads, True)
            fence(engine)
            checks += 1

            for fen in ("7k/6Q1/6K1/8/8/8/8/8 b - - 100 51",
                        "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"):
                terminal = position(engine, fen)
                summary = search(terminal, threads, True, "go depth 2", node_limit=None)
                assert int(summary["nodes"]) == 0 and summary["stop_reason"] == "terminal", summary
            board = position(engine)
            search(board, threads, True)  # Reuse after stop, ponder and terminal roots.

            engine.send("setoption name Late Move Reductions value false")
            search(board, threads, True, master=False)
            engine.send("setoption name Late Move Reductions value true")
            engine.send("setoption name Search Diagnostics value false")
            engine.send("go nodes 257")
            silent = engine.until("bestmove ", timeout=10)
            assert not any(line.startswith("info string ") for line in silent), silent
            legal_output(silent, board)
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
            assert not any(marker in line for marker in
                           ("Sanitizer", "runtime error:", "data race")), line
    print(f"Deep quiet UCI checks passed ({checks} short searches/lifecycle cases)")


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
