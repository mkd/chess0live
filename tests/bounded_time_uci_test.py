#!/usr/bin/env python3
"""Check opt-in bounded timing through UCI with one and four search workers.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Requires requirements-match.txt. Searches are short, serial correctness checks;
timing ceilings are checked from diagnostics, not scheduler-sensitive latency.
"""
import argparse
from pathlib import Path
import queue

from smp_uci_test import Engine, configure, fence, position, ready, validate_result

ROOT = Path(__file__).resolve().parents[1]


def bounded_result(lines, board, threads, hard=None):
    """Reuse the existing independent legal-PV and complete worker accounting."""
    summary = validate_result(lines, board, threads)
    assert summary["policy"] == "bounded", summary
    assert summary["forecast_active"] == "false", summary
    assert float(summary["predicted_next_ms"]) == 0, summary
    if hard is not None:
        assert float(summary["hard_ms"]) == hard, summary
    return summary


def run(binary, network):
    checks = 0
    with Engine(binary) as engine:
        identity = engine.handshake()
        options = [line for line in identity if line.startswith("option name Time Policy ")]
        assert len(options) == 1, options
        assert options[0] == ("option name Time Policy type combo default classic "
                              "var classic var forecast var bounded"), options
        for name, value in (("Hash", 1), ("EvalFile", network), ("Ponder", "false"),
                            ("Move Overhead", 20), ("SyzygyProbeLimit", 0),
                            ("Search Diagnostics", "true"), ("Time Policy", "bounded")):
            engine.send(f"setoption name {name} value {value}")
        ready(engine)

        for threads in (1, 4):
            configure(engine, threads)
            board = position(engine)
            # All cases run from startpos so the expected allocation is exact.
            for command, hard in (
                ("go wtime 620 btime 620", 37.5),
                ("go wtime 0 btime 0 winc 1000 binc 1000", 0),
                ("go movetime 40", 20),
                ("go depth 2 wtime 120000 btime 120000 winc 1000 binc 1000", 18197.5),
            ):
                engine.send(command)
                lines = engine.until("bestmove ", timeout=10)
                bounded_result(lines, board, threads, hard)
                fence(engine)
                checks += 1

            # No sleep: a completed ponder iteration is a protocol-visible
            # barrier before testing ready/ponderhit and the held bestmove.
            engine.send("go ponder depth 2 wtime 120000 btime 120000 winc 1000 binc 1000")
            completed = engine.until("info depth 2 ", timeout=10)
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in completed + pending)
            engine.send("ponderhit")
            bounded_result(completed + pending[:-1] + engine.until("bestmove ", timeout=5),
                           board, threads, 18197.5)
            fence(engine)
            checks += 1

            engine.send("go infinite")
            pending = ready(engine)
            assert not any(line.startswith("bestmove ") for line in pending)
            engine.send("stop")
            bounded_result(pending[:-1] + engine.until("bestmove ", timeout=5),
                           board, threads, 0)
            fence(engine)
            checks += 1

        engine.send("setoption name Time Policy value invalid")
        rejected = engine.until("info string error:", timeout=5)
        assert len(rejected) == 1, rejected
        ready(engine)
        engine.send("go depth 1")
        bounded_result(engine.until("bestmove ", timeout=10), board, threads, 0)
        fence(engine)
        checks += 1

        # Quit must join every worker, emit one final result, and exit normally.
        # Popen.wait detects forced termination independently of Engine.close.
        engine.send("go infinite")
        pending = ready(engine)
        assert not any(line.startswith("bestmove ") for line in pending)
        engine.send("quit")
        engine.process.wait(timeout=5)
        assert engine.process.returncode == 0, engine.process.returncode
        engine.reader.join(timeout=1)
        assert not engine.reader.is_alive(), "Output reader failed to reach EOF"
        remaining = []
        while True:
            try:
                line = engine.lines.get_nowait()
            except queue.Empty:
                break
            if line is not None:
                remaining.append(line)
        bounded_result(pending[:-1] + remaining, board, threads, 0)
        for line in engine.transcript + remaining:
            assert not any(marker in line for marker in
                           ("Sanitizer", "runtime error:", "data race")), line
        checks += 1
    print(f"Bounded timing UCI checks passed ({checks} searches/lifecycle cases)")


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
