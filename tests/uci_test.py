#!/usr/bin/env python3
"""Verify protocol lifecycle, transactional input, perft, and bounded searches.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from pathlib import Path
import os
import queue
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


def bestmove(lines):
    return lines[-1].split()[1]


def search_diagnostics(lines):
    """Check the public versioned trace and return its final summary fields."""
    summaries = [line for line in lines if line.startswith("info string search-summary v1 ")]
    assert len(summaries) == 1
    fields = summaries[0].split()[4:]
    summary = dict(zip(fields[::2], fields[1::2]))
    iterations = []
    for line in lines:
        if line.startswith("info string search-iteration v1 "):
            fields = line.split()[4:]
            iterations.append(dict(zip(fields[::2], fields[1::2])))
    assert sum(int(item["nodes"]) for item in iterations) == int(summary["nodes"])
    assert lines[-2] == summaries[0] and lines[-1].startswith("bestmove ")
    assert float(summary["predicted_next_ms"]) >= 0
    lmr_lines = [line for line in lines if line.startswith("info string lmr v1 ")]
    assert len(lmr_lines) == 1
    fields = lmr_lines[0].split()[4:]
    lmr = dict(zip(fields[::2], fields[1::2]))
    assert lmr["enabled"] in ("true", "false")
    assert int(lmr["researches"]) <= int(lmr["reductions"])
    assert int(lmr["fail_lows"]) + int(lmr["verified_cutoffs"]) <= int(lmr["researches"])
    return summary, iterations


with Engine(Path(sys.argv[1]).resolve()) as engine:
    handshake = engine.handshake()
    assert any(line.startswith("id name chess0live") for line in handshake)
    assert "option name Time Policy type combo default classic var classic var forecast" in handshake
    assert "option name Search Diagnostics type check default false" in handshake
    assert "option name Late Move Reductions type check default false" in handshake
    engine.send("position startpos")
    engine.send("perft 4")
    assert engine.until("nodes ")[-1].split()[1] == "197281"
    engine.send("position startpos moves e2e4 e7e5")
    engine.send("d")
    before = engine.until("info string fen ")[-1]
    engine.send("position startpos moves e2e9")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("info string fen ")[-1] == before
    engine.send("position fen garbage")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("info string fen ")[-1] == before
    engine.send("position startpos")
    engine.send("divide 1")
    division = engine.until("nodes ")
    assert len([line for line in division if ": " in line]) == 20
    assert division[-1].split()[1] == "20"

    network = ROOT / "networks" / "nn-1a298aa575a0.nnue"
    if network.exists():
        engine.send(f"setoption name EvalFile value {network}")
        engine.send("go depth 1 searchmoves e2e4")
        default_output = engine.until("bestmove ")
        assert bestmove(default_output) == "e2e4"
        assert not any(line.startswith("info string search-") for line in default_output)
        assert not any(line.startswith("info string lmr ") for line in default_output)

        engine.send("setoption name Time Policy value forecast")
        engine.send("setoption name Search Diagnostics value true")
        engine.send("setoption name Time Policy value invalid")
        assert "Time Policy expects" in engine.until("info string error:")[-1]
        engine.send("setoption name Search Diagnostics value invalid")
        assert "Search Diagnostics expects" in engine.until("info string error:")[-1]
        engine.send("go depth 2")
        summary, iterations = search_diagnostics(engine.until("bestmove "))
        assert summary["policy"] == "forecast" and summary["forecast_active"] == "false"
        assert summary["stop_reason"] == "depth_limit" and summary["completed_depth"] == "2"
        assert len(iterations) == 2 and all(item["completed"] == "true" for item in iterations)
        engine.send("setoption name Late Move Reductions value true")
        engine.send("setoption name Late Move Reductions value invalid")
        assert "Late Move Reductions expects" in engine.until("info string error:")[-1]
        engine.send("go depth 5 nodes 20000")
        selective_output = engine.until("bestmove ")
        search_diagnostics(selective_output)
        assert any(line.startswith("info string lmr v1 enabled true reductions ")
                   and int(line.split()[7]) > 0 for line in selective_output)
        engine.send("setoption name Late Move Reductions value false")
        engine.send("go wtime 0 btime 1000 winc 2000 binc 2000")
        summary, iterations = search_diagnostics(engine.until("bestmove "))
        assert summary["forecast_active"] == "true" and summary["stop_reason"] == "hard_time"
        assert summary["nodes"] == "0" and not iterations
        engine.send("setoption name Time Policy value classic")
        engine.send("go nodes 1")
        summary, iterations = search_diagnostics(engine.until("bestmove "))
        assert summary["policy"] == "classic" and summary["forecast_active"] == "false"
        assert summary["stop_reason"] == "node_limit" and summary["completed_depth"] == "0"
        assert len(iterations) == 1 and iterations[0]["completed"] == "false"
        engine.send("setoption name Search Diagnostics value false")
        engine.send("go depth 1")
        disabled_output = engine.until("bestmove ")
        assert not any(line.startswith("info string search-") for line in disabled_output)
        assert not any(line.startswith("info string lmr ") for line in disabled_output)
        for _ in range(5):
            engine.send("go infinite")
            engine.send("isready")
            engine.until("readyok", timeout=3)
            engine.send("stop")
            assert bestmove(engine.until("bestmove ", timeout=3)) != "0000"
        engine.send("go infinite depth 1")
        time.sleep(0.15)
        pending = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            pending.append(line)
        assert not any(line and line.startswith("bestmove ") for line in pending)
        engine.send("stop")
        assert bestmove(engine.until("bestmove ")) != "0000"
        engine.send("go ponder depth 1")
        time.sleep(0.15)
        engine.send("ponderhit")
        assert bestmove(engine.until("bestmove ")) != "0000"
        engine.send("go movetime 100")
        started = time.monotonic()
        assert bestmove(engine.until("bestmove ", timeout=3)) != "0000"
        assert time.monotonic() - started < 2
        # Black is checkmated. No search can return a legal coordinate move.
        engine.send("position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 100 1")
        engine.send("go depth 2")
        assert bestmove(engine.until("bestmove ")) == "0000"
        engine.send("position startpos")
        engine.send("setoption name EvalFile value /definitely/missing/network.nnue")
        engine.send("go depth 1")
        failed = engine.until("bestmove ")
        assert any("network not found" in line for line in failed)
        assert bestmove(failed) == "0000"
    else:
        print("NNUE-dependent UCI cases not run: network missing (make net; make test).")

if network.exists():
    executable = Path(sys.argv[1]).resolve()
    environment = dict(os.environ)
    environment["PATH"] = str(executable.parent) + os.pathsep + environment.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="chess0live-path-test-") as directory:
        with Engine(executable.name, cwd=directory, env=environment) as engine:
            engine.handshake()
            engine.send("position startpos")
            engine.send("go depth 1 searchmoves e2e4")
            assert bestmove(engine.until("bestmove ")) == "e2e4"

print("UCI tests passed")
