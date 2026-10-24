#!/usr/bin/env python3
"""Run the embedded puzzle positions through a UCI engine, one at a time.

Usage: python3 batch_positions.py /path/to/engine
The pinned chess dependency is configured automatically on first use.
API: https://python-chess.readthedocs.io/en/latest/engine.html

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

from pathlib import Path
import sys
from threading import Timer

if __name__ == "__main__":
    from tooling import direct_entry
    direct_entry(__file__)

import chess
import chess.engine

# Edit these settings. An engine path on the command line overrides ENGINE.
ENGINE = "/Users/claudio/projects/Chess/chess0live/build/macos-arm64-generic-release/chess0live"
#ENGINE = "/Users/claudio/projects/Chess/gargantua/src/gargantua"
#ENGINE = "/Users/claudio/projects/Chess/sic/sic"
THREADS = 8
HASH_MB = 64
MOVETIME_MS = 60000

# From your spreadsheet, in its original order. Comments show expected mates.
# Four positions lacked move counters; those have been filled with 0 1.
FENS = [
    "q3rk2/4r3/1p1p1n1b/5Q2/3P3p/P3R2P/1B3P1N/1K2R3 w - - 2 36",  # M7, spreadsheet row 4
    "1qB1b1rk/1p6/1P3n1p/p1P5/P1N2pp1/B7/6K1/bQ6 b - - 1 60",  # M7, spreadsheet row 5
    "1k2r2r/pbb2p2/2qn2p1/8/PP6/2P2N2/1Q2NPB1/R4RK1 b - - 0 1",  # M7, spreadsheet row 6
    "R1b4k/6pp/2pP4/1rn2rq1/N1Q2P1b/4PN2/1P5P/2B2K1R w - - 1 24",  # M8, spreadsheet row 9
    "4r1rk/p6q/bp2pP1Q/3pP3/P2Nn3/1Pbn1N1P/5PBK/2R3R1 b - - 0 30",  # M8, spreadsheet row 10
    "4r1rk/p3q3/b1N4p/p2pPp2/4n2Q/1P1n1N1P/5P1K/5RRB w - - 2 35",  # M8, spreadsheet row 11
    "2rqN1nk/bp6/7p/pP2p1pb/P1P5/BQ6/2B3K1/1R6 b - - 5 44",  # M8, spreadsheet row 12
    "2r5/1pB2Rbk/6pn/4n1q1/P3B3/1P5P/6P1/2Q1R2K w - - 1 34",  # M9, spreadsheet row 15
    "2b2rk1/q5pp/2p5/3p1p2/1rP2P2/B2nP1NB/3N3P/Q4K1R b - - 4 24",  # M9, spreadsheet row 16
    "r4k2/2r3b1/1p1p1nQ1/q6p/P2P1p1P/4P2R/1B1N1P2/1KR5 w - - 5 35",  # M9, spreadsheet row 17
    "4rk2/4r1b1/1p1p4/1q1P3p/4n3/P1R4P/1BQN1P2/1K3R2 b - - 2 37",  # M9, spreadsheet row 18
    "3q3k/3R1r2/5b2/pN2np2/1P5p/P4pP1/5B1P/2Q1RK2 w - - 1 46",  # M9, spreadsheet row 19
    "2N3k1/2b1qb2/2n1r3/8/1PP3Pp/P4Q2/8/2R1R2K b - - 2 42",  # M9, spreadsheet row 20
    "r6k/4r1bN/P1b3p1/8/2p1P1BP/2q5/2Q3K1/R4R2 b - - 1 49",  # M9, spreadsheet row 21
    "4k3/1p1Qqbr1/6r1/2P1b3/pP2N2p/P4B1P/8/1R3R1K b - - 0 35",  # M9, spreadsheet row 22
    "4r1k1/1q3r1p/3PNb2/1pB5/p1n5/P5p1/5RbP/3QR1K1 b - - 1 34",  # M9, spreadsheet row 23
    "1n2k1r1/1pb1q3/r7/7b/p1P1N2p/P4B1P/1P1Q4/4RR1K w - - 3 33",  # M9, spreadsheet row 24
    "8/1pB1rnbk/6pn/7q/P3B2P/1P6/6P1/2Q1R2K b - - 0 34",  # M10, spreadsheet row 27
    "rn3rk1/p7/bp2p2p/1q1pPp1Q/P2Nn3/1Pb2NPP/5PB1/3RR1K1 w - - 2 23",  # M10, spreadsheet row 28
    "1rb4k/6pp/2pq4/2n2r2/2Q1pP1b/R3P2B/NP5P/2B2KNR b - - 1 25",  # M10, spreadsheet row 29
    "5q1k/8/N1p1bb2/2n2B1p/4pP2/1r2P3/1P5P/2BQ1KNR w - - 0 32",  # M10, spreadsheet row 30
    "R4r1k/1q1bb3/nrp4p/5p2/2B1pP2/4P2N/1P5P/2BQ1K1R w - - 4 32",  # M10, spreadsheet row 31
    "1r2k1nr/pp1b4/1q5p/1P1Pp1pP/6Pn/1R2Q1N1/P1P1B3/5R1K w - - 1 29",  # M10, spreadsheet row 32
    "2r1qk2/1p1b4/p2P1n1p/1P2pPBP/2PbN3/7Q/P3B3/1R5K w - - 1 37",  # M10, spreadsheet row 33
    "2rq2k1/1p6/p2N3p/1P1np1pP/PBPb2b1/3B4/6Q1/1R5K w - - 2 40",  # M10, spreadsheet row 34
    "r1bqkbnr/p5p1/n1pp3p/1p1Pp1B1/7P/P1N5/1PP2PB1/R2QK2R w KQkq - 0 11",  # M10, spreadsheet row 35
    "1n2k1r1/1p2qb2/2rb4/8/pPP1N1Bp/P6P/3Q4/2R1R2K w - - 5 35",  # M10, spreadsheet row 36
    "rn2qrk1/p4p2/1p2p2Q/3pP3/PbbNn3/5NP1/1P3PBP/R3R1K1 w - - 1 19",  # M11, spreadsheet row 39
    "r1bqkbnr/pppp2p1/n3p2p/4Np2/1P1P4/P3P3/2P2PPP/RNBQKB1R w KQkq - 1 7",  # M11, spreadsheet row 40
    "r3k2r/1p3b2/2n5/3p1pq1/pb5p/N2P1B1P/PP2PN1K/R2Q1R2 b kq - 5 27",  # M11, spreadsheet row 41
    "3qk1b1/1p6/Qn2r3/2P1b3/p3N2p/P4BrP/8/1R3R1K b - - 3 39",  # M11, spreadsheet row 42
    "4nqrk/1p6/1P1N3p/p1P1p3/Pb4B1/5b2/2Q1R3/2B3K1 b - - 0 72",  # M11, spreadsheet row 43
    "R4r1k/6pp/2pq4/2n2b2/2Q1pP1b/1r2P2B/NP5P/2B2KNR b - - 1 24",  # M12, spreadsheet row 46
    "r2qk2r/pb1nb1pp/1p1pN3/2p5/3pp2P/6PB/PPP2P2/1RBQ1RK1 w kq - 6 16",  # M12, spreadsheet row 47
    "2rq2k1/3b3n/1p1N3p/1P2p1pP/PB1bB1P1/7Q/8/1R5K w - - 2 41",  # M12, spreadsheet row 48
    "3b4/p3P1q1/P1n2pr1/4p3/2B1n1Pk/1P1R4/P1p3KN/1N6 w - - 0 1",  # M15, spreadsheet row 51
    "7r/8/pB1p1R2/4k2q/1p6/1Pr5/P5Q1/6K1 w - - 0 1",  # M15, spreadsheet row 52
    "kb4Q1/P7/1PP5/K6q/8/8/8/4n3 w - - 0 1",  # M17, spreadsheet row 53
    "3r1r1k/1b4pp/ppn1p3/4Pp1R/Pn5P/3P4/4QP2/1qB1NKR1 w - - 0 1",  # M18, spreadsheet row 54
]


def format_score(score):
    if score is None:
        return "NO SCORE"
    mate = score.mate()
    if mate is not None:
        return f"{'-' if mate < 0 else ''}M{abs(mate)}"
    return f"{score.score() / 100:+.2f}"


def analyze(engine_path, fen):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError("Invalid chess position")
    with chess.engine.SimpleEngine.popen_uci(
        str(engine_path), cwd=engine_path.parent, timeout=30
    ) as engine:
        engine.configure({"Threads": THREADS, "Hash": HASH_MB})
        latest = {}
        # Stop a hung engine too; ordinary searches stop at MOVETIME_MS.
        watchdog = Timer(MOVETIME_MS / 1000 + 30, engine.close)
        watchdog.start()
        try:
            with engine.analysis(board, chess.engine.Limit(time=MOVETIME_MS / 1000)) as search:
                for info in search:
                    if info.get("string", "").lower().startswith("error"):
                        raise RuntimeError(info["string"])
                    if ("score" in info and info.get("multipv", 1) == 1
                            and not info.get("lowerbound") and not info.get("upperbound")):
                        latest = info
                best = search.wait().move
            if latest.get("pv") and latest["pv"][0] != best:
                raise RuntimeError("Last exact score does not match the final best move")
            score = latest["score"].pov(board.turn) if "score" in latest else None
            engine.quit()
            return format_score(score), best.uci() if best else "(none)"
        finally:
            watchdog.cancel()


def main():
    engine_path = Path(sys.argv[1] if len(sys.argv) > 1 else ENGINE).expanduser().resolve()
    if not engine_path.is_file():
        sys.exit("Set ENGINE at the top, or pass the full engine path on the command line.")
    if min(THREADS, HASH_MB, MOVETIME_MS) <= 0:
        sys.exit("THREADS, HASH_MB, and MOVETIME_MS must be positive.")
    print(f"Threads={THREADS}, Hash={HASH_MB} MB, movetime={MOVETIME_MS} ms", flush=True)
    failed = False
    for number, fen in enumerate(FENS, 1):
        print(f"{number:02d}/{len(FENS)}  ", end="", flush=True)
        try:
            score, move = analyze(engine_path, fen)  # A fresh engine for every FEN.
            print(f"{score:<10} bestmove={move}", flush=True)
            failed |= score == "NO SCORE"
        except (OSError, ValueError, RuntimeError, TimeoutError, chess.engine.EngineError) as error:
            print(f"ERROR: {error}", flush=True)
            failed = True
    return int(failed)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
