#!/usr/bin/env python3
"""Verify protocol lifecycle, transactional input, perft, and bounded searches.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from pathlib import Path
import os
import queue
import math
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine


def bestmove(lines):
    return lines[-1].split()[1]


def search_diagnostics(lines, *, expected_lmr=None):
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
    cache_lines = [line for line in lines if line.startswith("info string cache v1 ")]
    assert len(cache_lines) == 1
    fields = cache_lines[0].split()[4:]
    cache = {key: int(value) for key, value in zip(fields[::2], fields[1::2])}
    assert 0 <= cache["cutoffs"] <= cache["hits"] <= cache["probes"]
    assert 0 <= cache["replacements"] <= cache["stores"]
    assert cache["allocated_bytes"] == cache["buckets"] * cache["bucket_bytes"]
    assert cache["capacity"] == 4 * cache["buckets"]
    lmr_lines = [line for line in lines if line.startswith("info string lmr v1 ")]
    assert len(lmr_lines) == 1
    fields = lmr_lines[0].split()[4:]
    lmr = dict(zip(fields[::2], fields[1::2]))
    assert lmr["enabled"] in ("true", "false")
    if expected_lmr is not None:
        assert lmr["enabled"] == str(expected_lmr).lower(), lmr
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


def hashfull_values(lines):
    """UCI hashfull is integer permille, independent of optional diagnostics."""
    values = []
    for line in lines:
        if line.startswith("info depth "):
            fields = line.split()
            assert fields.count("hashfull") == 1, line
            value = fields[fields.index("hashfull") + 1]
            assert value.isdecimal() and 0 <= int(value) <= 1000, line
            values.append(int(value))
    assert values, lines
    return values


def board_state(lines):
    """Decode displayed coordinates independently of row/column orientation."""
    assert not any(line.startswith("info string ") for line in lines), lines
    assert lines[-1].startswith("fen "), lines[-1]
    labels = [line.split() for line in lines
              if line.split() in
              [list("abcdefgh"), list("hgfedcba")]]
    assert len(labels) == 1
    squares = {}
    ranks = []
    for line in lines:
        match = re.fullmatch(r"([1-8]) \|(.*)\|", line)
        if match:
            rank = match[1]
            ranks.append(rank)
            pieces = [value.strip() for value in match[2].split("|")]
            assert len(pieces) == 8
            for file, piece in zip(labels[0], pieces):
                assert piece in ("", *"PNBRQKpnbrqk")
                squares[file + rank] = piece
    assert len(squares) == 64 and len(ranks) == 8
    keys = [line for line in lines if line.startswith("key ")]
    assert len(keys) == 1 and re.fullmatch(r"key 0x[0-9A-F]{16}", keys[0])
    return squares, ranks, labels[0], keys[0], lines[-1]


def diagnostic_perft(engine, depth, total, branches):
    engine.send(f"go perft {depth}")
    lines = engine.until("perft complete ")
    assert not any(line.startswith("info string ") for line in lines), lines
    fields = lines[-1].split()[2:]
    stats = dict(zip(fields[::2], fields[1::2]))
    assert int(stats["depth"]) == depth and int(stats["nodes"]) == total
    assert all(math.isfinite(float(stats[name])) and float(stats[name]) >= 0
               for name in ("time_ms", "nps")), stats
    moves = [line.split(": ") for line in lines[:-1]]
    assert len(moves) == branches
    assert moves == sorted(moves)
    assert all(re.fullmatch(r"[a-h][1-8][a-h][1-8][nbrq]?", move) and int(count) >= 0
               for move, count in moves)
    if depth > 0:
        assert sum(int(count) for _, count in moves) == total
    return lines


with Engine(Path(sys.argv[1]).resolve()) as engine:
    handshake = engine.handshake()
    assert any(line.startswith("id name chess0live") for line in handshake)
    assert "option name Time Policy type combo default classic var classic var forecast var bounded" in handshake
    assert "option name Search Diagnostics type check default false" in handshake
    assert "option name Late Move Reductions type check default true" in handshake
    assert "option name Capture Ordering type combo default mvv-lva var mvv-lva var see" in handshake
    engine.send("position startpos")
    views = []
    for alias in ("d", "show", "display"):
        engine.send(alias)
        views.append(engine.until("fen "))
    assert views[0] == views[1] == views[2]
    start_view = board_state(views[0])
    assert start_view[1] == list("87654321") and start_view[2] == list("abcdefgh")
    assert [start_view[0][file + "1"] for file in "abcdefgh"] == list("RNBQKBNR")
    assert [start_view[0][file + "8"] for file in "abcdefgh"] == list("rnbqkbnr")
    assert all(start_view[0][file + rank] == "" for file in "abcdefgh" for rank in "3456")
    engine.send("flip")
    flipped = board_state(engine.until("fen "))
    assert flipped[1] == list("12345678") and flipped[2] == list("hgfedcba")
    assert flipped[0] == start_view[0] and flipped[3:] == start_view[3:]
    engine.send("flip")
    assert engine.until("fen ") == views[0]
    engine.send("help")
    engine.send("isready")
    help_lines = engine.until("readyok")[:-1]
    assert help_lines and not any(line.startswith("info string ") for line in help_lines)
    for command in ("d | show | display", "flip:", "eval:", "go perft N", "position fen", "quit:"):
        assert any(command in line for line in help_lines), command
    for command in ("d extra", "show extra", "display extra", "flip extra", "eval extra", "help extra",
                    "go perft", "go perft -1", "go perft 17", "go perft x", "go perft 1 extra",
                    "go perft 1 movetime 1", "go perft 99999999999999999999", "go depth 1 perft 2"):
        engine.send(command)
        engine.send("isready")
        invalid = engine.until("readyok")
        assert any(line.startswith("info string error:") for line in invalid), command
        assert not any(line.startswith(("bestmove ", "info depth ", "perft complete"))
                       for line in invalid), (command, invalid)
    diagnostic_perft(engine, 0, 1, 0)
    diagnostic_perft(engine, 1, 20, 20)
    diagnostic_perft(engine, 3, 8902, 20)
    engine.send("d")
    assert engine.until("fen ") == views[0]
    # An intentionally impractical depth must remain cancellable. The test
    # waits on readiness, not on machine-dependent node throughput.
    engine.send("go perft 16")
    engine.send("isready")
    assert engine.until("readyok", timeout=3)[-1] == "readyok"
    started = time.monotonic()
    engine.send("stop")
    stopped = engine.until("perft stopped ", timeout=3)
    assert time.monotonic() - started < 2 and " completed_root_nodes " in stopped[-1]
    assert not any(line.startswith("bestmove ") for line in stopped)
    engine.send("d")
    assert engine.until("fen ") == views[0]
    engine.send("position fen r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    diagnostic_perft(engine, 3, 97862, 48)
    engine.send("position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 100 1")
    diagnostic_perft(engine, 0, 1, 0)
    diagnostic_perft(engine, 2, 0, 0)
    engine.send("position startpos moves e2e4")
    engine.send("d")
    black_view = engine.until("fen ")
    assert "side Black" in black_view
    assert "en-passant e3" in black_view
    assert "castling KQkq" in black_view
    assert "halfmove 0" in black_view and "fullmove 1" in black_view
    # Replacing a position also joins an active diagnostic worker.
    engine.send("go perft 16")
    engine.send("position startpos")
    engine.until("perft stopped ", timeout=3)
    engine.send("perft 4")
    assert engine.until("nodes ")[-1].split()[1] == "197281"
    engine.send("position startpos moves e2e4 e7e5")
    engine.send("d")
    before = engine.until("fen ")[-1]
    engine.send("position startpos moves e2e9")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("fen ")[-1] == before
    # Owner-supplied puzzle regression. Answers are metadata; board validation
    # and transactional rejection must remain independent of the annotation.
    puzzle = "q3rk2/4r3/1p1p1n1b/5Q2/3P3p/P3R2P/1B3P1N/1K2R3 w - - 2 36"
    for suffix in ("", " bm Qxf6+ M7", " bm Qxf6+; M7", " bm deliberately-wrong-answer"):
        engine.send("position fen " + puzzle + suffix)
        engine.send("d")
        reply = engine.until("fen ")
        assert reply[-1] == "fen " + puzzle, reply
    four_fields = " ".join(puzzle.split()[:4])
    engine.send("position fen " + four_fields + " bm Qxf6+ M7")
    engine.send("d")
    before = "fen " + four_fields + " 0 1"
    assert engine.until("fen ")[-1] == before
    for bad in (puzzle + " bm", puzzle + " bm Qxf6+ moves f5f6",
                puzzle + " typo Qxf6+ M7", four_fields,
                four_fields + " 2 bm Qxf6+ M7",
                four_fields + " x 36 bm Qxf6+ M7",
                "8/8/8/8/8/8/8/8 w - - bm Qxf6+ M7"):
        engine.send("position fen " + bad)
        engine.until("info string error:")
        engine.send("d")
        assert engine.until("fen ")[-1] == before
    engine.send("position startpos bm e4")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("fen ")[-1] == before
    # Ordinary six-field FEN followed by a legal UCI history still works.
    engine.send("position fen " + puzzle + " moves f5f6")
    engine.send("d")
    reply = engine.until("fen ")
    assert not any("error:" in line for line in reply)
    before = reply[-1]
    engine.send("position fen garbage")
    engine.until("info string error:")
    engine.send("d")
    assert engine.until("fen ")[-1] == before
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
        assert all(line.startswith(("info depth ", "info nodes ", "bestmove ")) for line in default_output)
        assert any(re.search(r" score cp -?\d+ nodes ", line) for line in default_output)
        assert not any(line.startswith("info string search-") for line in default_output)
        assert not any(line.startswith("info string lmr ") for line in default_output)
        assert not any(line.startswith("info string ordering ") for line in default_output)
        assert not any(line.startswith("info string cache ") for line in default_output)
        hashfull_values(default_output)

        # No LMR setoption precedes this bounded search: verify the active
        # default, not only its advertised spelling or an explicit-on path.
        engine.send("setoption name Hash value 1")
        engine.send("setoption name Search Diagnostics value true")
        engine.send("go depth 5 nodes 20000")
        default_selective = engine.until("bestmove ")
        search_diagnostics(default_selective, expected_lmr=True)
        assert any(line.startswith("info string lmr v1 enabled true reductions ")
                   and int(line.split()[7]) > 0 for line in default_selective)
        for expected in (True, False):
            if not expected:
                engine.send("setoption name Late Move Reductions value false")
            engine.send("setoption name Late Move Reductions value invalid")
            assert "Late Move Reductions expects" in engine.until("info string error:")[-1]
            engine.send("go depth 1")
            search_diagnostics(engine.until("bestmove "), expected_lmr=expected)
        engine.send("setoption name Late Move Reductions value true")
        engine.send("setoption name Search Diagnostics value false")

        # A small table fills sufficiently for visible permille reporting in a
        # bounded search. Clearing, resizing, and a new game must discard entries;
        # a terminal root reports without adding any new table contents.
        engine.send("ucinewgame")
        engine.send("position startpos")
        engine.send("go depth 4")
        occupancy = engine.until("bestmove ")
        assert hashfull_values(occupancy)[-1] > 0
        for reset in ("setoption name Clear Hash", "setoption name Hash value 2", "ucinewgame"):
            engine.send(reset)
            engine.send("position fen 7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
            engine.send("go depth 1")
            assert hashfull_values(engine.until("bestmove ")) == [0]
        engine.send("setoption name Hash value 64")

        # Console diagnostics are plain text, but search scores retain their
        # standard UCI type. These composed KQK positions have a unique mate in
        # one, or one forced king reply followed by mate; reflect colors/ranks
        # to verify the sign follows the side to move rather than White.
        for fen, distance, expected_pv in (
            ("k7/8/1QK5/8/8/8/8/8 w - - 0 1", 1, ["b6b7"]),
            ("8/8/8/8/8/1qk5/8/K7 b - - 0 1", 1, ["b3b2"]),
            ("k7/8/2K5/1Q6/8/8/8/8 b - - 0 1", -1, ["a8a7", "b5b7"]),
            ("8/8/8/8/1q6/2k5/8/K7 w - - 0 1", -1, ["a1a2", "b4b2"]),
        ):
            engine.send("setoption name Clear Hash")
            engine.send("position fen " + fen)
            engine.send("go depth 3")
            mating_output = engine.until("bestmove ")
            hashfull_values(mating_output)
            assert all(line.startswith(("info depth ", "info nodes ", "bestmove ")) for line in mating_output)
            final_info = [line.split() for line in mating_output if line.startswith("info depth ")][-1]
            score_at = final_info.index("score")
            assert final_info[score_at + 1:score_at + 3] == ["mate", str(distance)], mating_output
            assert final_info[final_info.index("pv") + 1:] == expected_pv, mating_output
            assert bestmove(mating_output) == expected_pv[0]
        engine.send("position startpos")

        # Display orientation cannot rotate pieces, change repetition/history,
        # alter evaluation perspective, or affect a bounded fresh-table search.
        display_signatures = []
        for _ in range(2):
            engine.send("setoption name Clear Hash")
            engine.send("go depth 2")
            display_signatures.append(completed_signature(engine.until("bestmove ")))
            engine.send("flip")
            view = board_state(engine.until("fen "))
            assert view[0] == start_view[0] and view[3:] == start_view[3:]
        assert display_signatures[0] == display_signatures[1]

        for position, side in (("startpos", "White"), ("startpos moves e2e4", "Black")):
            engine.send("position " + position)
            engine.send("eval")
            evaluation = engine.until("eval psqt ")
            assert not any(line.startswith("info string ") for line in evaluation)
            assert len([line for line in evaluation if line.startswith("fen ")]) == 1
            human = [line for line in evaluation if line.startswith("NNUE evaluation:")]
            assert len(human) == 1 and f"{side} to move; positive favors {side}" in human[0]
            assert re.search(r"evaluation: [+-]\d+\.\d{2} pawns", human[0])
            fields = evaluation[-1].split()[1:]
            assert fields[::2] == ["psqt", "positional", "score"]
            assert all(re.fullmatch(r"-?\d+", value) for value in fields[1::2])
            engine.send("flip")
            engine.until("fen ")
            engine.send("eval")
            reversed_eval = engine.until("eval psqt ")
            assert reversed_eval[-2:] == evaluation[-2:]
            engine.send("flip")
            engine.until("fen ")
        engine.send("position fen 4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
        engine.send("eval")
        checked_eval = engine.until("eval psqt ")
        assert "check yes" in checked_eval
        assert any("unavailable while in check" in line for line in checked_eval)
        engine.send("position startpos")

        # A console view during search joins the worker before printing a
        # coherent board; the subsequent ordinary search is still usable.
        for command in ("show", "display", "d", "flip", "eval", "help", "go perft 1"):
            engine.send("go infinite depth 1")
            engine.send(command)
            if command == "eval":
                lines = engine.until("eval psqt ")
            elif command == "help":
                engine.send("isready")
                lines = engine.until("readyok")
            elif command == "go perft 1":
                lines = engine.until("perft complete ")
            else:
                lines = engine.until("fen ")
            best_lines = [line for line in lines if line.startswith("bestmove ")]
            assert len(best_lines) == 1 and best_lines[0].split()[1] != "0000", (command, lines)
        engine.send("flip")
        assert engine.until("fen ") == views[0]

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
        terminal_output = engine.until("bestmove ")
        assert bestmove(terminal_output) == "0000"
        assert any(" score mate 0 " in line for line in terminal_output), terminal_output
        engine.send("position startpos")
        engine.send("setoption name EvalFile value /definitely/missing/network.nnue")
        engine.send("eval")
        unavailable = engine.until("info string error:")
        assert any(line.startswith("fen ") for line in unavailable)
        assert not any(line.startswith(("eval psqt ", "NNUE evaluation:"))
                       for line in unavailable)
        # Move counting is network-independent even with an invalid EvalFile.
        diagnostic_perft(engine, 1, 20, 20)
        engine.send("go depth 1")
        failed = engine.until("bestmove ")
        assert any("network not found" in line for line in failed)
        assert bestmove(failed) == "0000"
    else:
        print("NNUE-dependent UCI cases not run: network missing (make net; make test).")

# Quit must join a diagnostic worker even without a network/readiness handshake.
with Engine(Path(sys.argv[1]).resolve()) as engine:
    engine.send("position startpos")
    engine.send("go perft 16")
    started = time.monotonic()
    engine.send("quit")
    engine.process.wait(timeout=3)
    assert time.monotonic() - started < 2 and engine.process.returncode == 0

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
