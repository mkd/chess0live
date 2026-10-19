#!/usr/bin/env python3
"""Check spreadsheet/UCI batching with original synthetic, non-chess engines.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from xml.sax.saxutils import escape
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import batch_positions as batch

FEN4 = "7k/8/8/8/8/8/8/K7 w - -"
FEN = FEN4 + " 0 1"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def workbook(path, cells, shared=None):
    """Create only the XLSX parts needed to exercise the independent reader."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'''<workbook xmlns="{SHEET_NS}"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
            <sheets><sheet name="Positions" sheetId="1" r:id="rId1"/></sheets>
            </workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '''<Relationships
            xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
            <Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
        rows = []
        for address, kind, value in cells:
            number = "".join(c for c in address if c.isdigit())
            if kind == "inlineStr":
                content = f"<is><t>{escape(value)}</t></is>"
            elif kind == "formula":
                content = f"<f>CONCAT(A1,A2)</f><v>{escape(value)}</v>"
            else:
                content = f"<v>{escape(str(value))}</v>"
            rows.append(f'<row r="{number}"><c r="{address}" t="{kind}">{content}</c></row>')
        archive.writestr("xl/worksheets/sheet1.xml",
                        f'<worksheet xmlns="{SHEET_NS}"><sheetData>'
                        + "".join(rows) + "</sheetData></worksheet>")
        if shared is not None:
            archive.writestr("xl/sharedStrings.xml",
                            f'<sst xmlns="{SHEET_NS}">' + "".join(shared) + "</sst>")


def fake_engine(path, journal, modes):
    """Each fresh subprocess chooses its behavior from an append-only journal."""
    path.write_text(f"#!{sys.executable}\n" + '''
import json
import os
import sys
from pathlib import Path
''' + f"journal = Path({str(journal)!r})\nmodes = {modes!r}\n" + '''
old = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
index = sum(record["event"] == "start" for record in old)
mode = modes[index]
def record(event, value=""):
    with journal.open("a") as output:
        output.write(json.dumps({"event": event, "value": value, "pid": os.getpid()}) + "\\n")
def emit(line):
    print(line, flush=True)
record("start")
for command in sys.stdin:
    command = command.strip()
    record("command", command)
    if command == "uci":
        emit("id name Synthetic batch fixture")
        emit("option name Threads type spin default 1 min 1 max 8")
        if mode != "missing_hash":
            emit("option name Hash type spin default 16 min 1 max 512")
        emit("option name MultiPV type spin default 1 min 1 max 10")
        emit("option name Ponder type check default true")
        emit("uciok")
    elif command == "isready":
        emit("readyok")
    elif command.startswith("go "):
        if mode == "crash":
            emit("info depth 1 score mate 99")
            sys.exit(3)
        if mode == "timeout":
            continue
        if mode == "diagnostic_error":
            emit("info string error: missing required network")
            emit("bestmove a1a2")
            continue
        if mode == "pv_mismatch":
            emit("info depth 1 score mate 7 pv a1a2 h8h7")
            emit("bestmove a1b1")
            continue
        if mode == "no_score":
            emit("info string diagnostics score mate 77")
        elif mode == "bad_bestmove":
            emit("info depth 1 score cp 12")
            emit("bestmove nonsense")
            continue
        else:
            emit("info depth 1 score mate 9 nodes 5 time 1 pv a1a2")
            emit("info depth 2 score " + mode + " nodes 11 time 2 pv a1a2 h8h7")
            emit("info depth 3 score mate 55 lowerbound")
            emit("info depth 4 multipv 2 score mate 44")
            emit("info string misleading score mate 33")
        emit("bestmove a1a2")
    elif command == "quit":
        break
record("exit")
''', encoding="utf-8")
    path.chmod(0o755)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def run_batch(self, cells, modes, extra=()):
        source = self.root / "positions.xlsx"
        workbook(source, cells)
        engine, journal = self.root / "fake engine", self.root / "journal.jsonl"
        fake_engine(engine, journal, modes)
        output = self.root / "results.csv"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = batch.main([str(engine), "--input", str(source), "--threads", "2",
                                 "--hash", "64", "--movetime", "1", "--timeout", "1",
                                 "--output", str(output), *extra])
        rows = list(csv.DictReader(io.StringIO(output.read_text()))) if output.exists() else []
        events = [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []
        return status, rows, events, stdout.getvalue(), stderr.getvalue()

    def test_shared_and_inline_strings_in_sheet_row_order(self):
        source = self.root / "positions.xlsx"
        workbook(source, [("A9", "inlineStr", "  " + FEN + "  "),
                          ("B2", "inlineStr", "ignored"), ("A2", "s", 0),
                          ("A1", "inlineStr", "Position")],
                 shared=[f"<si><r><t>{FEN4}</t></r><r><t> bm Ka2; M7</t></r>"
                         "<rPh sb=\"0\" eb=\"1\"><t>phonetic metadata</t></rPh></si>"])
        sheet, cells = batch.read_cells(source, sheet_name="Positions")
        self.assertEqual(sheet, "Positions")
        self.assertEqual(cells, [(1, "Position"), (2, FEN4 + " bm Ka2; M7"), (9, FEN)])
        self.assertEqual(batch.read_cells(source, column="B")[1], [(2, "ignored")])
        with self.assertRaisesRegex(ValueError, "not found"):
            batch.read_cells(source, sheet_name="Missing")

    def test_formula_positions_rejected(self):
        source = self.root / "positions.xlsx"
        workbook(source, [("A2", "formula", FEN)])
        with self.assertRaisesRegex(ValueError, "Positions!A2.*literal"):
            batch.read_cells(source)

    def test_four_field_fen_normalization_removes_answers(self):
        self.assertEqual(batch.parse_position(FEN4 + " bm Ka2; M7"),
                         {"fen": FEN, "expected_mate": "M7"})
        self.assertEqual(batch.parse_position(FEN + " bm Ka2; M8")["fen"], FEN)
        self.assertIsNone(batch.parse_position("Position"))
        self.assertIsNone(batch.parse_position(""))
        for invalid in ["8/8/8/8/8/8/8/8 w - -", FEN.replace(" w ", " x "),
                        FEN.replace("K7", "K8"), FEN4 + " 0 0"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                batch.parse_position(invalid)

    def test_score_signs_metadata_and_untrusted_diagnostics(self):
        for kind, number, expected in [("mate", 7, "M7"), ("mate", -8, "-M8"),
                                       ("mate", 0, "M0"), ("cp", 123, "+1.23"),
                                       ("cp", -25, "-0.25"), ("cp", 0, "+0.00")]:
            with self.subTest(kind=kind, number=number):
                score = batch.parse_score(f"info depth 12 multipv 1 score {kind} {number} "
                                          "nodes 90 time 3 pv a1a2 h8h7")
                self.assertEqual(score["result"], expected)
                self.assertEqual(score["score_value"], number)
                self.assertEqual(score["depth"], "12")
                self.assertEqual(score["pv"], "a1a2 h8h7")
        for line in ["info multipv 2 score mate 1", "info score mate 1 lowerbound",
                     "info score cp 20 upperbound", "info string score mate 7",
                     "info depth 7 string score mate 8", "info score mate nope",
                     "info score mate", "bestmove a1a2", "info depth 7 nodes 50"]:
            with self.subTest(line=line):
                self.assertIsNone(batch.parse_score(line))

    def test_fresh_engines_settings_and_row_aligned_outputs(self):
        cells = [("A8", "inlineStr", FEN), ("A1", "inlineStr", "Position"),
                 ("A3", "inlineStr", FEN4 + " bm Ka2; M7")]
        status, rows, events, _, errors = self.run_batch(cells, ["mate 7", "mate -8"])
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual([row["row"] for row in rows], ["3", "8"])
        self.assertEqual([row["result"] for row in rows], ["M7", "-M8"])
        self.assertEqual([row["mates_seen"] for row in rows], ["M9 M7", "M9 -M8"])
        self.assertEqual(rows[0]["expected_mate"], "M7")
        self.assertEqual(rows[0]["nodes"], "11")
        self.assertEqual(rows[0]["engine"], "Synthetic batch fixture")
        self.assertEqual((self.root / "results.scores.txt").read_text().splitlines(),
                         ["", "", "M7", "", "", "", "", "-M8"])
        starts = [event for event in events if event["event"] == "start"]
        self.assertEqual(len(starts), 2)
        self.assertEqual(len({event["pid"] for event in starts}), 2)
        for start in starts:
            commands = [event["value"] for event in events
                        if event["pid"] == start["pid"] and event["event"] == "command"]
            self.assertEqual(commands[:9], ["uci", "setoption name Threads value 2",
                             "setoption name Hash value 64", "setoption name MultiPV value 1",
                             "setoption name Ponder value false", "ucinewgame", "isready",
                             "position fen " + FEN, "go movetime 1"])
            self.assertEqual(commands[-1], "quit")
        self.assertIn("< info depth 2 score mate 7", (self.root / "results.log").read_text())

    def test_failures_do_not_erase_completed_rows_or_stop_remaining_positions(self):
        modes = ["cp 25", "no_score", "crash", "timeout", "bad_bestmove", "missing_hash",
                 "diagnostic_error", "pv_mismatch", "mate 8"]
        status, rows, _, _, errors = self.run_batch(
            [(f"A{i + 2}", "inlineStr", FEN) for i in range(len(modes))], modes)
        self.assertEqual((status, errors), (1, ""))
        expected = ["+0.25", "NO SCORE", "ERROR", "ERROR", "ERROR", "ERROR", "ERROR", "ERROR", "M8"]
        self.assertEqual([row["result"] for row in rows], expected)
        self.assertEqual([row["status"] for row in rows],
                         ["ok", "no_score", "error", "error", "error", "error", "error", "error", "ok"])
        self.assertIn("before bestmove", rows[2]["error"])
        self.assertIn("within", rows[3]["error"])
        self.assertIn("Malformed bestmove", rows[4]["error"])
        self.assertIn("Hash", rows[5]["error"])
        self.assertIn("missing required network", rows[6]["error"])
        self.assertIn("bestmove", rows[7]["error"])
        self.assertEqual(rows[7]["mates_seen"], "M7")
        self.assertEqual((self.root / "results.scores.txt").read_text().splitlines(), [""] + expected)

    def test_interruption_preserves_completed_rows(self):
        original = batch.analyze
        calls = 0
        def interrupt_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt
            return original(*args)
        with mock.patch.object(batch, "analyze", side_effect=interrupt_second):
            status, rows, events, _, errors = self.run_batch(
                [("A2", "inlineStr", FEN), ("A4", "inlineStr", FEN)], ["mate 7"])
        self.assertEqual(status, 130)
        self.assertEqual([row["result"] for row in rows], ["M7"])
        self.assertEqual((self.root / "results.scores.txt").read_text(), "\nM7\n")
        self.assertIn("Completed rows remain", errors)
        self.assertEqual(sum(event["event"] == "exit" for event in events), 1)

    def test_start_row_and_limit_keep_original_spreadsheet_alignment(self):
        status, rows, _, _, _ = self.run_batch(
            [(f"A{i}", "inlineStr", FEN) for i in (2, 5, 9)], ["mate 7"],
            extra=["--start-row", "5", "--limit", "1"])
        self.assertEqual(status, 0)
        self.assertEqual([row["row"] for row in rows], ["5"])
        self.assertEqual((self.root / "results.scores.txt").read_text(), "\n\n\n\nM7\n")

    def test_malformed_positions_outside_selected_range_are_ignored(self):
        status, rows, _, _, errors = self.run_batch(
            [("A2", "inlineStr", "8/8 invalid"), ("A5", "inlineStr", FEN),
             ("A9", "inlineStr", "8/8 invalid")], ["mate 7"],
            extra=["--start-row", "5", "--limit", "1"])
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual([row["row"] for row in rows], ["5"])


if __name__ == "__main__":
    unittest.main()
