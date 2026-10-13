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


with Engine(Path(sys.argv[1]).resolve()) as engine:
    handshake = engine.handshake()
    assert any(line.startswith("id name chess0live") for line in handshake)
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
        assert bestmove(engine.until("bestmove ")) == "e2e4"
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
