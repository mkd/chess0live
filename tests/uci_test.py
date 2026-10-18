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
    ordering_lines = [line for line in lines if line.startswith("info string ordering v1 ")]
    assert len(ordering_lines) == 1
    fields = ordering_lines[0].split()[4:]
    ordering = dict(zip(fields[::2], fields[1::2]))
    assert ordering["policy"] in ("mvv-lva", "see")
    assert 0 <= int(ordering["losing_captures"]) <= int(ordering["see_calls"])
    if ordering["policy"] == "mvv-lva":
        assert ordering["see_calls"] == ordering["losing_captures"] == "0"
    return summary, iterations


def completed_signature(lines):
    """Ignore speed/timing; compare the final completed tree and its result."""
    fields = [line.split() for line in lines if line.startswith("info depth ")][-1]
    score_index = fields.index("score")
    return (bestmove(lines), fields[fields.index("nodes") + 1],
            fields[score_index + 1:score_index + 3], fields[fields.index("pv") + 1:])


with Engine(Path(sys.argv[1]).resolve()) as engine:
    handshake = engine.handshake()
    assert any(line.startswith("id name chess0live") for line in handshake)
    assert "option name Time Policy type combo default classic var classic var forecast" in handshake
    assert "option name Search Diagnostics type check default false" in handshake
    assert "option name Late Move Reductions type check default false" in handshake
    assert "option name Capture Ordering type combo default mvv-lva var mvv-lva var see" in handshake
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
    # Owner-supplied puzzle regression. Answers are metadata; board validation
    # and transactional rejection must remain independent of the annotation.
    puzzle = "q3rk2/4r3/1p1p1n1b/5Q2/3P3p/P3R2P/1B3P1N/1K2R3 w - - 2 36"
    for suffix in ("", " bm Qxf6+ M7", " bm Qxf6+; M7", " bm deliberately-wrong-answer"):
        engine.send("position fen " + puzzle + suffix)
        engine.send("d")
        reply = engine.until("info string fen ")
        assert reply == ["info string fen " + puzzle], reply
    four_fields = " ".join(puzzle.split()[:4])
    engine.send("position fen " + four_fields + " bm Qxf6+ M7")
    engine.send("d")
    before = "info string fen " + four_fields + " 0 1"
    assert engine.until("info string fen ") == [before]
    for bad in (puzzle + " bm", puzzle + " bm Qxf6+ moves f5f6",
                puzzle + " typo Qxf6+ M7", four_fields,
                four_fields + " 2 bm Qxf6+ M7",
                four_fields + " x 36 bm Qxf6+ M7",
                "8/8/8/8/8/8/8/8 w - - bm Qxf6+ M7"):
        engine.send("position fen " + bad)
        engine.until("info string error:")
        engine.send("d")
        assert engine.until("info string fen ") == [before]
    engine.send("position startpos bm e4")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("info string fen ") == [before]
    # Ordinary six-field FEN followed by a legal UCI history still works.
    engine.send("position fen " + puzzle + " moves f5f6")
    engine.send("d")
    reply = engine.until("info string fen ")
    assert not any("error:" in line for line in reply)
    before = reply[-1]
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
        assert not any(line.startswith("info string ordering ") for line in default_output)

        # Correct, wrong, and impossible answer notes produce the exact same
        # completed search tree as the unannotated FEN after a fresh hash table.
        signatures = []
        for suffix in ("", " bm Qxf6+ M7", " bm a1a8 M99"):
            engine.send("setoption name Clear Hash")
            engine.send("position fen " + puzzle + suffix)
            engine.send("go depth 2")
            lines = engine.until("bestmove ")
            assert not any("error:" in line for line in lines), lines
            signatures.append(completed_signature(lines))
        assert signatures[0] == signatures[1] == signatures[2], signatures
        engine.send("position startpos")

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
        engine.send("setoption name Time Policy value classic")
        engine.send("position fen 6k1/8/4p3/3p4/8/8/8/3Q2K1 w - - 0 1")
        engine.send("setoption name Clear Hash")
        engine.send("go depth 3")
        ordering_baseline = engine.until("bestmove ")
        search_diagnostics(ordering_baseline)
        engine.send("setoption name Capture Ordering value see")
        engine.send("setoption name Capture Ordering value invalid")
        assert "Capture Ordering expects" in engine.until("info string error:")[-1]
        engine.send("go depth 3")
        ordering_candidate = engine.until("bestmove ")
        search_diagnostics(ordering_candidate)
        assert any(line.startswith("info string ordering v1 policy see see_calls ")
                   and int(line.split()[7]) > 0 and int(line.split()[9]) > 0
                   for line in ordering_candidate)
        engine.send("setoption name Capture Ordering value mvv-lva")
        engine.send("go depth 3")
        ordering_restored = engine.until("bestmove ")
        search_diagnostics(ordering_restored)
        assert completed_signature(ordering_restored) == completed_signature(ordering_baseline)
        engine.send("position startpos")
        engine.send("setoption name Time Policy value forecast")
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
        assert not any(line.startswith("info string ordering ") for line in disabled_output)
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
        # Loading a dirty network during go is charged preparation. It cannot
        # give a short request a new budget when its worker finally starts.
        # The API suite models dispatch delay deterministically with old receipt
        # timestamps; this integration case verifies the UCI propagation path.
        for lmr in ("false", "true"):
            engine.send("setoption name Search Diagnostics value true")
            engine.send("setoption name Move Overhead value 0")
            engine.send("setoption name Late Move Reductions value " + lmr)
            engine.send("setoption name EvalFile value " + str(network))
            engine.send("go movetime 1")
            cold = engine.until("bestmove ")
            summary, iterations = search_diagnostics(cold)
            assert float(summary["elapsed_ms"]) >= 1
            assert summary["nodes"] == "0" and not iterations
            assert summary["stop_reason"] == "hard_time"
            assert bestmove(cold) != "0000"
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
