#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Reproduce the small independently composed Syzygy oracle corpus.

Defaults to checking the committed JSON and C++ fixtures byte for byte. --write
explicitly regenerates them. Uses chess==1.11.2 and the complete pinned 3/4-piece
tables, with no engine search, external service, or owner-supplied positions.
"""

import argparse
import json
from pathlib import Path
import random
import sys

import chess
import chess.syzygy

import fetch_syzygy_test_tables as fixtures


SEED = 2026101842
PROVENANCE = (
    "Independently generated with random.Random(2026101842), "
    "sorted(chess.syzygy.tablenames(piece_count=4)), white then black; "
    "uniform distinct squares; reject python-chess invalid or no-legal-move "
    "positions. No prior-engine assets or held-out search roots. "
    "Every root is also vertically reflected with colors and side to move "
    "swapped via Board.mirror().")


def generate(directory):
    if chess.__version__ != "1.11.2":
        raise ValueError("Corpus reproduction requires chess==1.11.2")
    fixtures.fetch(fixtures.load_manifest(), directory, verify_only=True)
    randomizer = random.Random(SEED)
    cases = []
    with chess.syzygy.open_tablebase(str(directory)) as tables:
        for name in sorted(chess.syzygy.tablenames(piece_count=4)):
            white, black = name.split("v")
            pieces = ([(symbol, chess.WHITE) for symbol in white]
                      + [(symbol, chess.BLACK) for symbol in black])
            for turn in (chess.WHITE, chess.BLACK):
                for _ in range(10000):
                    board = chess.Board(None)
                    for (symbol, color), square in zip(pieces, randomizer.sample(chess.SQUARES, len(pieces))):
                        board.set_piece_at(square, chess.Piece.from_symbol(symbol if color else symbol.lower()))
                    board.turn = turn
                    if not board.is_valid() or not any(board.legal_moves):
                        continue
                    cases.append({"name": name + ("-white" if turn else "-black"),
                                  "fen": board.fen(), "wdl": tables.probe_wdl(board),
                                  "dtz": tables.probe_dtz(board)})
                    break
                else:
                    raise RuntimeError("Could not compose bounded fixture for " + name)
        for case in cases[:]:
            board = chess.Board(case["fen"]).mirror()
            cases.append({"name": case["name"] + "-color-mirrored", "fen": board.fen(),
                          "wdl": tables.probe_wdl(board), "dtz": tables.probe_dtz(board)})
    if len(cases) != 140 or len({case["fen"] for case in cases}) != 140:
        raise ValueError("Expected 140 distinct valid oracle roots")
    return {"schema": "chess0live-syzygy-composed-cases-v1", "provenance": PROVENANCE,
            "oracle": "chess==1.11.2, local complete 3/4-piece corpus pinned by syzygy-test-manifest.json",
            "cases": cases}


def render_header(cases):
    result = """/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 * GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
 *
 * Frozen independently composed cases; provenance and oracle outputs are also
 * recorded in syzygy-cases.json. All 35 three-/four-piece material classes are
 * covered with both sides to move and a color-swapped vertical reflection.
 * These are test data, not endgame answers embedded into the engine.
 */
#pragma once
#include <array>
#include <string_view>

namespace syzygy_test {
struct OracleCase {
    std::string_view name;
    std::string_view fen;
    int wdl;
    int dtz;
};
"""
    result += f"inline constexpr std::array<OracleCase, {len(cases)}> oracle_cases{{{{\n"
    result += "\n".join('    {"%s", "%s", %d, %d},' % (case["name"], case["fen"], case["wdl"], case["dtz"])
                        for case in cases)
    return result + "\n}};\n} // namespace syzygy_test\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=fixtures.ROOT / "tablebases/test")
    parser.add_argument("--output-directory", type=Path, default=fixtures.ROOT / "tests/data")
    parser.add_argument("--write", action="store_true", help="regenerate fixtures instead of checking them")
    args = parser.parse_args(argv)
    data = generate(args.directory)
    outputs = {"syzygy-cases.json": json.dumps(data, indent=2) + "\n",
               "syzygy_cases.hpp": render_header(data["cases"])}
    for name, text in outputs.items():
        path = args.output_directory / name
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        elif path.read_text() != text:
            raise ValueError("Reproduced oracle corpus differs from " + str(path))
    print("Reproduced 140 distinct Syzygy oracle roots and matching JSON/C++ fixtures")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print("Error:", error, file=sys.stderr)
        sys.exit(1)
