#!/usr/bin/env python3
"""Bounded null-move protocol and rule regressions with an independent referee.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Install requirements-match.txt, then pass the candidate executable. Only one
engine searches at a time. --threads 1 omits the four-worker lifecycle checks;
the default covers both one and four workers. Neither faster searches nor legal
output establish strength. The separately declared match gate remains necessary.
--activation-timeout changes only the external harness wait for two node-capped
activation/parity searches; it never changes engine limits or lifecycle waits.
"""
import argparse
import json
from pathlib import Path
import queue
import sys

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from uci_client import Engine

OPTION = "Null Move Pruning"
PREFIX = "info string nullmove v1 "
COUNTERS = ("probes", "fail_highs", "verifications", "cutoffs", "rejected",
            "probe_nodes", "verification_nodes", "verification_hints")
CORPUS = ROOT / "tests/data/null-move-regressions.json"
SANITIZER_MARKERS = ("Sanitizer", "runtime error:", "data race")


def fields(line, prefix):
    """Reject duplicate/truncated fields in versioned diagnostics."""
    assert line.startswith(prefix), line
    tokens = line[len(prefix):].split()
    assert len(tokens) % 2 == 0, line
    result = dict(zip(tokens[::2], tokens[1::2]))
    assert len(result) * 2 == len(tokens), line
    return result


def only_record(lines, prefix):
    selected = [line for line in lines if line.startswith(prefix)]
    assert len(selected) == 1, (prefix, selected)
    return fields(selected[0], prefix)


def ready(engine, *, error=False):
    engine.send("isready")
    lines = engine.until("readyok", timeout=15)
    if error:
        assert len(lines) == 2 and lines[0].startswith("info string error:"), lines
    else:
        assert lines == ["readyok"], lines
    return lines


def option(engine, name, value=None, *, error=False):
    command = "setoption name " + name
    if value is not None:
        command += " value " + str(value)
    engine.send(command)
    return ready(engine, error=error)


def reflected(coordinate):
    """Mirror a real move, preserving promotion choice and its side's ranks."""
    move = chess.Move.from_uci(coordinate)
    assert move, coordinate
    return chess.Move(chess.square_mirror(move.from_square),
                      chess.square_mirror(move.to_square), move.promotion).uci()


def expand_cases():
    """Validate the public corpus without consulting any qualification roots."""
    document = json.loads(CORPUS.read_text())
    assert document["schema_version"] == 1
    seen = set()
    result = []
    for original in document["positions"]:
        assert original["id"] not in seen, original
        seen.add(original["id"])
        assert 1 <= original["depth"] <= 6, original
        for mirror in (False, True):
            case = dict(original)
            case["id"] += "-mirror" if mirror else "-original"
            initial = chess.Board(original["fen"])
            assert initial.is_valid(), (original["id"], initial.status())
            if mirror:
                initial = initial.mirror()
            case["fen"] = initial.fen(en_passant="fen")
            case["moves"] = [reflected(move) if mirror else move
                             for move in original.get("moves", ())]
            board = initial.copy(stack=True)
            for coordinate in case["moves"]:
                move = chess.Move.from_uci(coordinate)
                assert move and move in board.legal_moves, (case["id"], coordinate)
                board.push(move)
            assert board.is_valid(), (case["id"], board.status())
            case["searchmoves"] = [reflected(move) if mirror else move
                                   for move in original.get("searchmoves", ())]
            for coordinate in case["searchmoves"]:
                assert chess.Move.from_uci(coordinate) in board.legal_moves, case
            if "repetition" in case:
                assert board.is_repetition(case["repetition"]), case
                assert not board.is_repetition(case["repetition"] + 1), case
            if case.get("in_check"):
                assert board.is_check(), case
            result.append((case, board))
    return result


def position(engine, fen=chess.STARTING_FEN, history=()):
    board = chess.Board(fen)
    assert board.is_valid(), fen
    command = "position fen " + fen
    if history:
        command += " moves " + " ".join(history)
    for coordinate in history:
        move = chess.Move.from_uci(coordinate)
        assert move and move in board.legal_moves, (board.fen(), coordinate)
        board.push(move)
    engine.send(command)
    return board


def replay(board, coordinates):
    """A synthetic pass can never appear in a legal PV, bestmove, or ponder."""
    current = board.copy(stack=True)
    for coordinate in coordinates:
        move = chess.Move.from_uci(coordinate)
        assert move and move in current.legal_moves, (current.fen(), coordinate, coordinates)
        current.push(move)
    return current


def validate(lines, board, *, enabled, threads=1, diagnostics=True, lmr=False,
             allowed=None, node_limit=None, node_ceiling=None, score=None):
    """Check protocol, real-move legality, and aggregate search accounting."""
    prefixes = ("info depth ", "info nodes ", "bestmove ",
                "info string cache v1 ", "info string ordering v1 ",
                "info string lmr v1 ", "info string smp v1 ",
                "info string search-iteration v1 ",
                "info string search-summary v1 ", PREFIX)
    assert all(line.startswith(prefixes) for line in lines), lines
    assert not any(marker in line for line in lines for marker in SANITIZER_MARKERS), lines
    best_lines = [line for line in lines if line.startswith("bestmove ")]
    assert len(best_lines) == 1 and lines[-1] == best_lines[0], lines
    best = best_lines[0].split()
    assert len(best) in (2, 4), best
    if board.is_checkmate() or board.is_stalemate():
        assert best == ["bestmove", "0000"], best
    else:
        assert best[1] != "0000", best
        if allowed:
            assert best[1] in allowed, (best, allowed)
        if len(best) == 4:
            assert best[2] == "ponder", best
            replay(board, (best[1], best[3]))
        else:
            replay(board, (best[1],))

    signatures, scores = [], []
    previous_depth = previous_nodes = -1
    last_pv = []
    for line in lines:
        if not line.startswith(("info depth ", "info nodes ")):
            continue
        tokens = line.split()
        nodes = int(tokens[tokens.index("nodes") + 1])
        assert nodes >= max(0, previous_nodes), line
        previous_nodes = nodes
        assert tokens.count("hashfull") == tokens.count("tbhits") == 1, line
        assert 0 <= int(tokens[tokens.index("hashfull") + 1]) <= 1000, line
        assert int(tokens[tokens.index("tbhits") + 1]) == 0, line
        if line.startswith("info nodes "):
            continue
        depth = int(tokens[tokens.index("depth") + 1])
        assert depth > previous_depth, line
        previous_depth = depth
        at = tokens.index("score")
        kind, value = tokens[at + 1], int(tokens[at + 2])
        assert kind in ("cp", "mate"), line
        last_pv = tokens[tokens.index("pv") + 1:]
        replay(board, last_pv)
        if allowed and last_pv:
            assert last_pv[0] in allowed, line
        scores.append((depth, kind, value))
        signatures.append((depth, int(tokens[tokens.index("seldepth") + 1]),
                           nodes, kind, value, tuple(last_pv)))
    final_lines = [line for line in lines if line.startswith("info nodes ")]
    assert len(final_lines) == 1, final_lines
    final = fields(final_lines[0], "info ")
    total = int(final["nodes"])
    assert total >= max(0, previous_nodes), lines
    if node_limit is not None:
        assert total == node_limit, (total, node_limit, lines)
    if node_ceiling is not None:
        assert total <= node_ceiling, (total, node_ceiling)
    if score is not None:
        assert scores and scores[-1][1:] == tuple(score), (scores, score, lines)
        if score[0] == "mate" and score[1] in (-1, 1):
            assert replay(board, last_pv).is_checkmate(), (board.fen(), last_pv, score)

    null_lines = [line for line in lines if line.startswith(PREFIX)]
    counters = None
    if enabled and diagnostics:
        raw = only_record(lines, PREFIX)
        assert set(raw) == {"enabled", *COUNTERS}, raw
        assert raw["enabled"] == "true", raw
        counters = {key: int(raw[key]) for key in COUNTERS}
        assert all(value >= 0 for value in counters.values()), counters
        assert counters["fail_highs"] <= counters["probes"], counters
        assert counters["fail_highs"] == counters["verifications"], counters
        assert counters["cutoffs"] + counters["rejected"] <= counters["verifications"], counters
        assert counters["verification_hints"] <= counters["verifications"], counters
        assert counters["verification_hints"] <= counters["verification_nodes"], counters
        assert counters["probe_nodes"] + counters["verification_nodes"] <= total, (counters, total)
    else:
        assert not null_lines, lines
    if diagnostics:
        summary = only_record(lines, "info string search-summary v1 ")
        assert int(summary["nodes"]) == total, (summary, total)
        assert lines[-2].startswith("info string search-summary v1 "), lines[-3:]
        lmr_record = only_record(lines, "info string lmr v1 ")
        assert lmr_record["enabled"] == str(lmr).lower(), lmr_record
        smp_lines = [line for line in lines if line.startswith("info string smp v1 ")]
        if threads == 1:
            assert not smp_lines, smp_lines
        else:
            smp = only_record(lines, "info string smp v1 ")
            worker_nodes = list(map(int, smp["worker_nodes"].split(",")))
            worker_depths = list(map(int, smp["worker_depths"].split(",")))
            assert int(smp["threads"]) == len(worker_nodes) == len(worker_depths) == threads, smp
            assert all(value >= 0 for value in worker_nodes + worker_depths), smp
            assert sum(worker_nodes) == int(smp["total_nodes"]) == total, smp
            assert worker_nodes[0] == int(smp["leader_nodes"]), smp
            assert worker_depths[0] == int(summary["completed_depth"]), (smp, summary)
    else:
        assert not any(line.startswith("info string ") for line in lines), lines
    return {"signature": (tuple(signatures), tuple(best), total),
            "scores": scores, "counters": counters, "lines": lines}


def search(engine, board, command="go depth 4", *, timeout=30, **expected):
    engine.send(command)
    result = validate(engine.until("bestmove ", timeout=timeout), board, **expected)
    engine.send("stop")
    ready(engine)
    return result


def root_evaluation(engine):
    """The external root state and raw evaluator must survive speculative work."""
    engine.send("eval")
    lines = engine.until("eval psqt ", timeout=15)
    assert not any(line.startswith("info string error:") for line in lines), lines
    return lines[-1]


def run(executable, network, max_threads, activation_timeout=30):
    cases = expand_cases()
    checks = 0
    with Engine(executable) as engine:
        advertised = engine.handshake()
        assert f"option name {OPTION} type check default false" in advertised, advertised
        option(engine, "EvalFile", network)
        option(engine, "Hash", 1)
        option(engine, "Threads", 1)
        option(engine, "Late Move Reductions", "false")
        option(engine, "Countermove Ordering", "false")
        option(engine, "SyzygyProbeLimit", 0)
        option(engine, "Search Diagnostics", "true")
        board = position(engine)
        baseline = search(engine, board, enabled=False)
        checks += 1
        for value in ("invalid", "1", None):
            option(engine, OPTION, value, error=True)
            search(engine, board, "go depth 2", enabled=False)
            checks += 1
        option(engine, OPTION, "true")
        option(engine, OPTION, "invalid", error=True)
        on_cold = search(engine, board, enabled=True)
        assert all(value == 0 for value in on_cold["counters"].values()), on_cold
        checks += 1
        option(engine, OPTION, "false")
        restored = search(engine, board, enabled=False)
        assert restored["signature"] == baseline["signature"], (restored, baseline)
        option(engine, OPTION, "true")
        repeated = search(engine, board, enabled=True)
        assert repeated["signature"] == on_cold["signature"], (repeated, on_cold)
        checks += 2

        # This node-capped search is an exposed activation check, not a speed
        # target. A plain depth-four search cannot reach an eligible null node.
        option(engine, "Clear Hash")
        root_before = root_evaluation(engine)
        active = search(engine, board, "go depth 7 nodes 250000", enabled=True,
                        node_ceiling=250000, timeout=activation_timeout)
        assert all(active["counters"][key] > 0 for key in
                   ("probes", "fail_highs", "verifications", "cutoffs",
                    "probe_nodes", "verification_nodes", "verification_hints")), active
        assert root_evaluation(engine) == root_before
        option(engine, "Clear Hash")
        option(engine, "Search Diagnostics", "false")
        silent = search(engine, board, "go depth 7 nodes 250000", enabled=True,
                        diagnostics=False, node_ceiling=250000, timeout=activation_timeout)
        assert silent["signature"] == active["signature"], (silent, active)
        option(engine, "Search Diagnostics", "true")
        checks += 2

        # The new root hint must also be consumed with the accepted LMR policy;
        # diagnostics cannot change a fixed-work search or the external root.
        option(engine, "Late Move Reductions", "true")
        option(engine, "Clear Hash")
        hinted = search(engine, board, "go depth 6 nodes 200000", enabled=True,
                        lmr=True, node_ceiling=200000, timeout=activation_timeout)
        assert hinted["counters"]["verification_hints"] > 0, hinted
        assert root_evaluation(engine) == root_before
        option(engine, "Clear Hash")
        option(engine, "Search Diagnostics", "false")
        silent_hint = search(engine, board, "go depth 6 nodes 200000", enabled=True,
                             lmr=True, diagnostics=False, node_ceiling=200000,
                             timeout=activation_timeout)
        assert silent_hint["signature"] == hinted["signature"], (silent_hint, hinted)
        option(engine, "Search Diagnostics", "true")
        option(engine, "Late Move Reductions", "false")
        checks += 2

        for case, expected_board in cases:
            variants = (False, True) if case.get("exact_off_parity") else (True,)
            results = []
            for enabled in variants:
                option(engine, OPTION, str(enabled).lower())
                option(engine, "Clear Hash")
                board = position(engine, case["fen"], case["moves"])
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
            option(engine, "Threads", threads)
            option(engine, OPTION, "true")
            board = position(engine)
            for limit in (1, 257, 4096):
                option(engine, "Clear Hash")
                search(engine, board, f"go nodes {limit}", enabled=True,
                       threads=threads, node_limit=limit)
                checks += 1
            engine.send("go infinite")
            engine.send("stop")
            validate(engine.until("bestmove ", timeout=10), board, enabled=True, threads=threads)
            ready(engine)
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
                ready(engine)
                checks += 1
            search(engine, board, "go movetime 60", enabled=True, threads=threads)
            checks += 1

            # A policy mutation joins every old worker before clearing cache /
            # learned state. Old result reporting must retain the old option.
            for previous, following in ((True, False), (False, True)):
                engine.send("go infinite")
                partial = engine.until("info depth 3 ", timeout=30)
                engine.send(f"setoption name {OPTION} value {str(following).lower()}")
                validate(partial + engine.until("bestmove ", timeout=10), board,
                         enabled=previous, threads=threads)
                ready(engine)
                search(engine, board, "go nodes 257", enabled=following,
                       threads=threads, node_limit=257)
                checks += 1
            for command in ("setoption name Clear Hash", "ucinewgame",
                            "setoption name Hash value 2",
                            f"setoption name EvalFile value {network}"):
                engine.send("go infinite")
                engine.send(command)
                validate(engine.until("bestmove ", timeout=10), board,
                         enabled=True, threads=threads)
                ready(engine)
                search(engine, board, "go depth 2", enabled=True, threads=threads)
                checks += 1

        engine.send("go infinite")
        engine.send("quit")
        engine.process.wait(timeout=10)
        assert engine.process.returncode == 0
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive()
        remainder = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                remainder.append(line)
        assert not any(marker in line for line in engine.transcript + remainder
                       for marker in SANITIZER_MARKERS), remainder
        checks += 1
    print(f"Null-move UCI tests passed ({checks} bounded cases; up to {max_threads} workers; no strength claim)")


def activation_seconds(text):
    """Accept an explicit bounded harness allowance for slow sanitizer builds."""
    try:
        seconds = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("activation timeout must be an integer from 1 to 300") from error
    if not 1 <= seconds <= 300:
        raise argparse.ArgumentTypeError("activation timeout must be an integer from 1 to 300")
    return seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path, nargs="?")
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--threads", type=int, choices=(1, 4), default=4)
    parser.add_argument("--activation-timeout", type=activation_seconds, default=30,
                        metavar="SECONDS",
                        help="wait 1–300 seconds for each of the two fixed-node activation checks (default: 30)")
    parser.add_argument("--validate-corpus", action="store_true",
                        help="validate the independent fixture data without launching an engine")
    args = parser.parse_args()
    if args.validate_corpus:
        print(f"Null-move corpus passed ({len(expand_cases())} independently validated colored cases)")
        return
    if args.engine is None:
        parser.error("supply an engine executable or --validate-corpus")
    if not args.network.is_file():
        parser.error("pinned network missing; run make net before this integration suite")
    run(args.engine.resolve(), args.network.resolve(), args.threads, args.activation_timeout)


if __name__ == "__main__":
    main()
