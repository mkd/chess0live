#!/usr/bin/env python3
"""Reproducible, bounded NNUE search benchmark; NPS is not an Elo measurement.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from resources import current_budget
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ["startpos", "startpos moves e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3",
             "startpos moves d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7 e2e3"]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--positions", type=Path, help="File with one UCI position body per line: startpos [moves ...] or fen ...")
    args = parser.parse_args()
    if not 1 <= args.depth <= 12:
        parser.error("depth must be 1..12")
    network = ROOT / "networks" / "nn-1a298aa575a0.nnue"
    if not network.exists():
        parser.error("pinned network missing; run make net first")
    engine_path = args.engine.resolve()
    positions = POSITIONS
    if args.positions:
        positions = [line.strip() for line in args.positions.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
        if not positions or any(not (line == "startpos" or line.startswith("startpos moves ")
                                     or line.startswith("fen ")) for line in positions):
            parser.error("positions must contain startpos [moves ...] or fen ... entries")
    records = []
    with Engine(engine_path) as engine:
        engine.handshake()
        engine.send(f"setoption name EvalFile value {network}")
        for position in positions:
            budget = current_budget()  # Owner changes take effect between runs.
            engine.send("ucinewgame")
            engine.send(f"position {position}")
            engine.send(f"go depth {args.depth}")
            lines = engine.until("bestmove ", timeout=300)
            if any("error:" in line for line in lines) or lines[-1] == "bestmove 0000":
                raise RuntimeError("benchmark search failed: " + "\n".join(lines))
            records.append({"position": position, "resource_policy": budget, "output": lines})
    result = {"engine": str(engine_path), "engine_sha256": digest(engine_path),
              "network_sha256": digest(network), "depth": args.depth,
              "platform": platform.platform(), "machine": platform.machine(),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)),
              "threads": 1, "hash_mb": 64, "results": records,
              "positions_sha256": hashlib.sha256(("\n".join(positions) + "\n").encode()).hexdigest(),
              "interpretation": "Throughput/correctness benchmark only. No Elo inference."}
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
