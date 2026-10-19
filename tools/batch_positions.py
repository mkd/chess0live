#!/usr/bin/env python3
"""Run spreadsheet positions sequentially through any compatible UCI engine.

Python 3.9+, standard library only. Run with --help for examples/options.
UCI format: https://www.shredderchess.com/download/div/uci.zip
Command reference:
https://official-stockfish.github.io/docs/stockfish-wiki/UCI-Protocol-and-Stockfish-Commands.html

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path
import posixpath
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
import zipfile


# Edit these defaults, or override them on the command line.
ENGINE = ""  # Full path to your UCI engine binary.
SPREADSHEET = Path.home() / "Downloads" / "Chess test positions benchmark.xlsx"
THREADS = 1
HASH_MB = 128
MOVETIME_MS = 60000

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def cell_text(element):
    """Read plain/rich text, excluding optional phonetic pronunciation runs."""
    if element is None:
        return ""
    return "".join(t.text or "" for t in
                   element.findall("s:t", NS) + element.findall("s:r/s:t", NS))


def read_cells(path, sheet_name=None, column="A"):
    """Read text cells without Excel or third-party Python packages."""
    with zipfile.ZipFile(path) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = workbook.findall("s:sheets/s:sheet", NS)
        if not sheets:
            raise ValueError("Workbook contains no worksheets")
        sheet = next((s for s in sheets if s_name(s) == sheet_name), None) if sheet_name else sheets[0]
        if sheet is None:
            raise ValueError(f"Sheet {sheet_name!r} not found. Available: {[s_name(s) for s in sheets]}")
        relationships = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(r.attrib["Target"] for r in relationships
                      if r.attrib["Id"] == sheet.attrib[f"{{{REL}}}id"])
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = [cell_text(si) for si in
                       ET.fromstring(book.read("xl/sharedStrings.xml"))]
        root = ET.fromstring(book.read(member))
        cells = []
        for cell in root.findall("s:sheetData/s:row/s:c", NS):
            match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", cell.attrib.get("r", ""))
            if not match or match[1] != column:
                continue
            if cell.find("s:f", NS) is not None:
                # Formula outputs can be stale; positions must be literal text.
                raise ValueError(f"{s_name(sheet)}!{cell.attrib['r']}: use literal positions, not formulas")
            value = cell.findtext("s:v", default="", namespaces=NS)
            if cell.attrib.get("t") == "s":
                value = strings[int(value)]
            elif cell.attrib.get("t") == "inlineStr":
                value = cell_text(cell.find("s:is", NS))
            cells.append((int(match[2]), value.strip()))
        return s_name(sheet), sorted(cells)


def s_name(sheet):
    return sheet.attrib["name"]


def parse_position(text):
    """Ignore headings; normalize FEN syntax, never send answer annotations."""
    tokens = text.split()
    if not tokens or "/" not in tokens[0]:
        return None
    fields = tokens[:tokens.index("bm")] if "bm" in tokens else tokens
    if len(fields) == 4:
        fields += ["0", "1"]
    if len(fields) != 6:
        raise ValueError("expected four or six FEN fields, optionally followed by bm")
    board, side, castling, ep, halfmove, fullmove = fields
    ranks = board.split("/")
    if len(ranks) != 8 or any(
        not re.fullmatch(r"[prnbqkPRNBQK1-8]+", rank)
        or sum(int(c) if c.isdigit() else 1 for c in rank) != 8 for rank in ranks
    ):
        raise ValueError("invalid FEN board layout")
    if board.count("K") != 1 or board.count("k") != 1:
        raise ValueError("FEN must contain one king of each color")
    if side not in ("w", "b") or not re.fullmatch(r"-|K?Q?k?q?", castling):
        raise ValueError("invalid FEN side or castling rights")
    if not re.fullmatch(r"-|[a-h][36]", ep):
        raise ValueError("invalid FEN en-passant square")
    if not halfmove.isdecimal() or not fullmove.isdecimal() or int(fullmove) < 1:
        raise ValueError("invalid FEN move counters")
    expected = re.search(r"\bM([0-9]+)\b", " ".join(tokens[6:] if "bm" not in tokens else tokens[tokens.index("bm") + 1:]))
    return {"fen": " ".join(fields), "expected_mate": "M" + expected[1] if expected else ""}


def parse_score(line):
    """Only exact main-line scores; bounds and secondary PVs are not results."""
    words = line.split()
    if not words or words[0] != "info":
        return None
    # Everything after `string` is arbitrary diagnostic text.
    words = words[:words.index("string")] if "string" in words else words
    def value(key, default=""):
        return words[words.index(key) + 1] if key in words and words.index(key) + 1 < len(words) else default
    if value("multipv", "1") != "1" or "lowerbound" in words or "upperbound" in words:
        return None
    if "score" not in words:
        return None
    index = words.index("score")
    if len(words) <= index + 2 or words[index + 1] not in ("cp", "mate"):
        return None
    try:
        score = int(words[index + 2])
    except ValueError:
        return None
    kind = words[index + 1]
    result = (f"{'-' if score < 0 else ''}M{abs(score)}" if kind == "mate"
              else f"{score / 100:+.2f}")
    return {"result": result, "score_type": kind, "score_value": score,
            "depth": value("depth"), "nodes": value("nodes"),
            "engine_time_ms": value("time"),
            "pv": " ".join(words[words.index("pv") + 1:]) if "pv" in words else ""}


class Engine:
    """A fresh process per position, with bounded reads and cleanup."""
    def __init__(self, binary, cwd, log):
        self.log = log
        self.lock = threading.Lock()
        self.lines = queue.Queue()
        self.process = subprocess.Popen([str(binary)], cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding="utf-8", errors="replace", bufsize=1)
        self.readers = []
        for stream, label in ((self.process.stdout, "<"), (self.process.stderr, "!")):
            reader = threading.Thread(target=self.read, args=(stream, label), daemon=True)
            reader.start()
            self.readers.append(reader)

    def record(self, prefix, line):
        with self.lock:
            self.log.write(f"{prefix} {line}\n")
            self.log.flush()

    def read(self, stream, label):
        try:
            for line in stream:
                line = line.rstrip("\r\n")
                self.record(label, line)
                if label == "<":
                    self.lines.put(line)
        finally:
            if label == "<":
                self.lines.put(None)

    def send(self, command):
        self.record(">", command)
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def until(self, token, timeout, callback=lambda line: None):
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self.lines.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as error:
                raise TimeoutError(f"Engine did not send {token} within {timeout:g}s") from error
            if line is None:
                raise RuntimeError(f"Engine exited before {token}; see protocol log")
            if re.match(r"^(?:info string )?error(?:[: ]|$)", line, re.IGNORECASE):
                raise RuntimeError(f"Engine reported: {line}")
            callback(line)
            if line.split()[:1] == [token]:
                return line
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Engine did not send {token} within {timeout:g}s")

    def close(self):
        if self.process.poll() is None:
            try:
                self.send("stop")
                self.send("quit")
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        for reader in self.readers:
            reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()
        self.process.stderr.close()


def analyze(binary, position, args, log):
    row = {"result": "NO SCORE", "status": "no_score", "mates_seen": ""}
    engine = Engine(binary, args.cwd or binary.parent, log)
    mates = []
    try:
        options = {}
        def handshake(line):
            if line.startswith("id name "):
                row["engine"] = line[8:]
            match = re.match(r"option name (.+?) type (\w+)(.*)$", line)
            if match:
                options[match[1].casefold()] = (match[1], match[2], match[3])
        engine.send("uci")
        engine.until("uciok", args.timeout, handshake)
        settings = {"Threads": args.threads, "Hash": args.hash_mb}
        for name in ("MultiPV", "Ponder"):
            if name.casefold() in options:
                settings[name] = 1 if name == "MultiPV" else "false"
        for name, value in settings.items():
            if name.casefold() not in options:
                raise ValueError(f"Engine does not advertise {name}; cannot apply the requested settings")
            advertised, kind, spec = options[name.casefold()]
            if kind == "spin":
                low, high = re.search(r"\bmin (-?\d+)", spec), re.search(r"\bmax (-?\d+)", spec)
                if (low and int(value) < int(low[1])) or (high and int(value) > int(high[1])):
                    raise ValueError(f"{name}={value} is outside the engine's advertised range:{spec}")
            elif name in ("Threads", "Hash"):
                raise ValueError(f"Engine advertises unsupported {name} type {kind!r}")
            engine.send(f"setoption name {advertised} value {value}")
        engine.send("ucinewgame")
        engine.send("isready")
        engine.until("readyok", args.timeout)
        engine.send("position fen " + position["fen"])
        def info(line):
            score = parse_score(line)
            if score:
                row.update(score)
                row["status"] = "ok"
                if score["score_type"] == "mate" and score["result"] not in mates:
                    mates.append(score["result"])
        started = time.monotonic()
        engine.send(f"go movetime {args.movetime}")
        best = engine.until("bestmove", args.movetime / 1000 + args.timeout, info).split()
        row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        if len(best) < 2 or not re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?|0000|\(none\)", best[1]):
            raise ValueError("Malformed bestmove; see protocol log")
        row["bestmove"] = best[1]
        if row.get("pv") and row["pv"].split()[0] != best[1]:
            raise ValueError("Last exact score's PV disagrees with bestmove; see mates_seen and protocol log")
    except (OSError, RuntimeError, TimeoutError, ValueError) as error:
        row.update(result="ERROR", status="error", error=str(error))
    finally:
        engine.close()
    row["mates_seen"] = " ".join(mates)
    return row


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
        epilog="Example: python3 batch_positions.py /path/to/engine --threads 4 --hash 1024 --movetime 60000")
    parser.add_argument("engine", nargs="?", default=ENGINE, help="UCI executable path or name on PATH")
    parser.add_argument("--input", type=Path, default=SPREADSHEET, help="input .xlsx file")
    parser.add_argument("--sheet", help="worksheet name (default: first worksheet)")
    parser.add_argument("--column", default="A", help="position column (default: A)")
    parser.add_argument("--threads", type=positive, default=THREADS)
    parser.add_argument("--hash", dest="hash_mb", type=positive, default=HASH_MB, help="hash in MB")
    parser.add_argument("--movetime", type=positive, default=MOVETIME_MS, help="search time in milliseconds")
    parser.add_argument("--timeout", type=positive, default=30, help="startup timeout / search grace in seconds")
    parser.add_argument("--cwd", type=Path, help="engine working directory (default: binary directory)")
    parser.add_argument("--output", type=Path, help="new CSV path (default: results/engine-timestamp.csv)")
    parser.add_argument("--start-row", type=positive, default=1, help="start at this spreadsheet row")
    parser.add_argument("--limit", type=positive, help="run only this many positions")
    parser.add_argument("--list-positions", action="store_true", help="check/list inputs without running an engine")
    args = parser.parse_args(argv)
    args.column = args.column.upper()
    if not re.fullmatch(r"[A-Z]+", args.column):
        parser.error("--column must be a column letter such as A")
    try:
        sheet, cells = read_cells(args.input.expanduser(), args.sheet, args.column)
        positions = []
        for row_number, cell in cells:
            if row_number < args.start_row:
                continue
            try:
                position = parse_position(cell)
            except ValueError as error:
                raise ValueError(f"{sheet}!{args.column}{row_number}: {error}") from error
            if position:
                positions.append(dict(position, row=row_number, sheet=sheet))
                if args.limit and len(positions) >= args.limit:
                    break
        if not positions:
            raise ValueError("No positions found in the selected sheet/column/rows")
        if args.list_positions:
            for position in positions:
                print(f"{sheet}!{args.column}{position['row']}: {position['fen']}  {position['expected_mate']}")
            print(f"{len(positions)} positions")
            return 0
        if not args.engine:
            raise ValueError("Supply an engine executable, or edit ENGINE near the top of this script")
        candidate = Path(args.engine).expanduser()
        binary = candidate.resolve() if candidate.is_file() else Path(shutil.which(args.engine) or "")
        if not binary.is_file():
            raise ValueError(f"Engine executable not found: {args.engine}")
        binary = binary.resolve()
        output = args.output or Path("results") / f"{binary.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}.csv"
        output = output.expanduser().resolve()
        if output.suffix.lower() != ".csv":
            raise ValueError("--output must end in .csv")
        scores_path, log_path = output.with_suffix(".scores.txt"), output.with_suffix(".log")
        for path in (output, scores_path, log_path):
            if path.exists():
                raise ValueError(f"Output already exists; choose a new name: {path}")
        output.parent.mkdir(parents=True, exist_ok=True)
        print(f"{len(positions)} positions; Threads={args.threads}, Hash={args.hash_mb} MB, "
              f"movetime={args.movetime} ms. Fresh engine per position.", flush=True)
        print(f"CSV: {output}\nScores (paste from row 1): {scores_path}\nLog: {log_path}", flush=True)
        fields = ["sheet", "row", "result", "mates_seen", "expected_mate", "bestmove", "depth",
                  "score_type", "score_value", "nodes", "engine_time_ms", "elapsed_ms", "pv",
                  "status", "error", "engine", "engine_path", "threads", "hash_mb", "movetime_ms", "fen"]
        failures = 0
        with output.open("x", newline="", encoding="utf-8") as csv_file, \
                scores_path.open("x", encoding="utf-8") as scores_file, \
                log_path.open("x", encoding="utf-8") as log:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            writer.writeheader()
            csv_file.flush()
            next_text_row = 1
            for index, position in enumerate(positions, 1):
                print(f"[{index}/{len(positions)}] {sheet}!{args.column}{position['row']} ...", flush=True)
                log.write(f"\n# {sheet}!{args.column}{position['row']} {position['fen']}\n")
                try:
                    result = analyze(binary, position, args, log)
                except OSError as error:
                    result = {"result": "ERROR", "status": "error", "error": str(error)}
                result.update(position, engine_path=str(binary), threads=args.threads,
                              hash_mb=args.hash_mb, movetime_ms=args.movetime)
                writer.writerow(result)
                csv_file.flush()
                while next_text_row < position["row"]:
                    scores_file.write("\n")
                    next_text_row += 1
                scores_file.write(result["result"] + "\n")
                next_text_row += 1
                scores_file.flush()
                print(f"  {result['result']}  bestmove={result.get('bestmove', '')}  "
                      f"depth={result.get('depth', '')}" +
                      (f"  {result['error']}" if result.get("error") else ""), flush=True)
                failures += result["status"] != "ok"
        print(f"Finished: {len(positions)} positions, {failures} errors/missing scores.")
        return 1 if failures else 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Completed rows remain in the output files.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
