#!/usr/bin/env python3
"""Synthetic saved-report export checks; never launch a chess engine.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The independent raw auditor has its own tests. Here its boundary is explicitly
mocked so presentation/publication failures can be exercised using tiny files.
"""
from contextlib import redirect_stdout
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
import puzzle_report as p


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Fixture:
    """Small real evidence files surrounding an explicitly synthetic report."""
    def __init__(self, root, mode="smoke"):
        self.root, self.mode = root, mode
        self.evidence = root / "saved evidence with spaces"
        self.evidence.mkdir()
        self.path = self.evidence / "report.json"
        positions = json.loads((PROJECT / "tests/data/phase4f3-puzzles.json").read_text())["positions"]
        assets = {}
        for name in ("engine", "network", "pins"):
            path = self.evidence / (name + ".fixture")
            path.write_text("synthetic " + name, encoding="utf-8")
            assets[name] = {"path": str(path), "sha256": sha(path)}
        options = {role: {"Threads": "8", "Hash": "64", "Move Overhead": "20",
                         "Time Policy": "classic", "Ponder": "false", "Search Diagnostics": "false",
                         "Late Move Reductions": "true", "TT Move Hints": "true" if role == "hints-on" else "false",
                         "EvalFile": assets["network"]["path"]}
                   for role in ("hints-off", "hints-on")}
        self.report = dict(schema_version=1, protocol="phase4f7-tt-hints-puzzles-v1", status="complete",
                           mode=mode, engine_source_revision="a1b2331273f5baf4fcc2c53ee96a3759337e2399",
                           started_utc="2026-10-25T12:00:00+00:00", finished_utc="2026-10-25T12:01:40+00:00",
                           platform="Synthetic host", chess_version="1.11.2", quiet_host=mode == "full",
                           allow_daytime=mode == "full", assets=assets,
                           after_sha256={name: a["sha256"] for name, a in assets.items()},
                           positions=positions, options=options,
                           settings={"movetime_ms": 0 if mode == "check" else 60000 if mode == "full" else 1000,
                                     "total_seconds": 7200 if mode == "full" else 600}, samples=[])
        cases = [(None, role) for role in options] if mode == "check" else [
            (index, role) for index in range(39)
            for role in (("hints-off", "hints-on") if index % 2 == 0 else ("hints-on", "hints-off"))]
        for sequence, (index, role) in enumerate(cases):
            raw = self.evidence / f"raw-{sequence:02d}.jsonl"
            raw.write_text("synthetic raw evidence\n", encoding="utf-8")
            sample = dict(status="complete", role=role, position_index=index,
                          position_id=positions[index]["id"] if index is not None else None,
                          raw_log=raw.name, raw_sha256=sha(raw), pid=1000 + sequence,
                          exit_code=0, options=options[role])
            if index is not None:
                score = {"type": "cp", "value": 120 + index}
                result = dict(score=score, score_cp=score["value"], reported_mate=None,
                              supplied_mate=positions[index]["supplied_mate"], bestmove="f5f6", ponder=None,
                              completed_depth=6, reported_nodes=1000 + index, reported_time_ms=980,
                              reported_nps=1020, hashfull=0,
                              reported_positive_mate=False, reported_mate_matches_supplied=False,
                              final_pv_ends_in_checkmate=False, first_positive_mate_iteration=None,
                              iterations=[dict(depth=6, seldepth=12, score=score, nodes=1000 + index,
                                               time=980, nps=1020, hashfull=0, tbhits=0, pv=["f5f6"])])
                sample.update(result=result, elapsed_seconds=.9805, wall_elapsed_seconds=.9805)
            self.report["samples"].append(sample)
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.report, indent=2) + "\n", encoding="utf-8")

    def certificate(self):
        searching = self.mode != "check"
        roles = {role: {field: sum(bool(s["result"][field]) for s in self.report["samples"]
                                  if "result" in s and s["role"] == role)
                        for field in ("reported_positive_mate", "reported_mate_matches_supplied",
                                      "final_pv_ends_in_checkmate")}
                 for role in ("hints-off", "hints-on")}
        return dict(schema_version=1, status="passed", mode=self.mode, report_sha256=sha(self.path),
                    assets_checked=3, raw_sessions=78 if searching else 2, zero_exits=78 if searching else 2,
                    distinct_recorded_pids=78 if searching else 2, searches=78 if searching else 0,
                    positions=39 if searching else 0, iterations=78 if searching else 0,
                    legal_pv_plies=78 if searching else 0, legal_best_ponder_plies=78 if searching else 0,
                    commands=100, consumed_output_lines=100, readiness_barriers=234 if searching else 4,
                    resource_observations=313 if searching else 7, roles=roles,
                    same_bestmove=39 if searching else 0, max_gap_seconds=.25,
                    max_clock_drift_seconds=.00001)

    def sample(self, index, role):
        return next(s for s in self.report["samples"] if s["position_index"] == index and s["role"] == role)


class PuzzleReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fixture = Fixture(self.root)
        self.output = self.root / "export with spaces"

    def export(self, fixture=None, **kwargs):
        fixture = fixture or self.fixture
        with patch.object(p.auditor, "audit", return_value=fixture.certificate()) as audit:
            value = p.export_report(fixture.path, kwargs.get("output", self.output))
        audit.assert_called_once_with(fixture.path.resolve())
        return value

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_fresh_audit_and_three_outputs_without_changing_evidence(self):
        before = self.snapshot()
        result = self.export()
        self.assertEqual(result, self.output.resolve())
        self.assertEqual({path.name for path in self.output.iterdir()}, {"comparison.md", "positions.csv", "audit.json"})
        for name, payload in before.items():
            self.assertEqual((self.root / name).read_bytes(), payload)
        certificate = json.loads((self.output / "audit.json").read_text())
        self.assertEqual(certificate["report_sha256"], sha(self.fixture.path))
        self.assertEqual(certificate["status"], "passed")

    def test_all_positions_and_both_roles_export_in_original_order(self):
        rows = p.csv_rows(self.fixture.report)
        self.assertEqual(len(rows), 78)
        self.assertEqual([(row["position_id"], row["role"]) for row in rows],
                         [(position["id"], role) for position in self.fixture.report["positions"]
                          for role in ("hints-off", "hints-on")])
        self.assertEqual({row["fen"] for row in rows}, {position["fen"] for position in self.fixture.report["positions"]})

    def test_markdown_has_every_position_and_traceable_audit_identity(self):
        rendered = p.render_markdown(self.fixture.report, self.fixture.certificate())
        for number in range(1, 40):
            self.assertIn(f"| {number} |", rendered)
        self.assertIn(sha(self.fixture.path), rendered)
        self.assertIn(self.fixture.report["assets"]["network"]["sha256"], rendered)
        self.assertIn("smoke", rendered.lower())
        self.assertIn("strength", rendered.lower())
        self.assertIn("forced mate", rendered.lower())

    def test_signed_cp_and_positive_negative_mates_have_distinct_units(self):
        for score, expected in (({"type": "cp", "value": 120}, "+1.20"),
                                ({"type": "cp", "value": -5}, "-0.05"),
                                ({"type": "cp", "value": 0}, "+0.00"),
                                ({"type": "mate", "value": 7}, "M7"),
                                ({"type": "mate", "value": -7}, "-M7")):
            with self.subTest(score=score):
                self.assertEqual(p.format_score(score), expected)

    def test_readiness_is_not_a_completed_puzzle_comparison(self):
        other = self.root / "check-fixture"; other.mkdir()
        fixture = Fixture(other, "check")
        self.export(fixture)
        rendered = (self.output / "comparison.md").read_text()
        self.assertIn("readiness", rendered.lower())
        self.assertIn("no search", rendered.lower())
        with (self.output / "positions.csv").open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, list(p.CSV_FIELDS))
            self.assertEqual(list(reader), [])

    def test_full_and_smoke_are_labeled_separately_without_pooling(self):
        report = copy.deepcopy(self.fixture.report)
        report.update(mode="full", quiet_host=True, settings={"movetime_ms": 60000, "total_seconds": 7200})
        full = p.render_markdown(report, dict(self.fixture.certificate(), mode="full"))
        smoke = p.render_markdown(self.fixture.report, self.fixture.certificate())
        self.assertIn("60-second comparison", full)
        self.assertIn("one-second smoke", smoke)
        self.assertIn("does not establish playing strength", full)
        self.assertIn("does not replace the full", smoke)
        self.assertNotEqual(full, smoke)

    def test_supplied_reported_and_pv_mate_claims_remain_separate(self):
        off, on = (self.fixture.sample(0, role)["result"] for role in ("hints-off", "hints-on"))
        supplied = self.fixture.report["positions"][0]["supplied_mate"]
        off.update(score={"type": "mate", "value": supplied + 2}, score_cp=None,
                   reported_mate=supplied + 2, reported_positive_mate=True,
                   reported_mate_matches_supplied=False, final_pv_ends_in_checkmate=True)
        on.update(score={"type": "mate", "value": -supplied}, score_cp=None,
                  reported_mate=-supplied, reported_positive_mate=False,
                  reported_mate_matches_supplied=False, final_pv_ends_in_checkmate=False)
        self.fixture.save()
        self.export()
        with (self.output / "positions.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 78)
        for row in rows[:2]:
            self.assertEqual(row["supplied_mate"], str(supplied))
            self.assertEqual(row["score_type"], "mate")
            self.assertEqual(row["score_pawns"], "")
            self.assertEqual(row["reported_mate_matches_supplied"], "False")
        self.assertEqual(rows[0]["reported_mate"], str(supplied + 2))
        self.assertEqual(rows[0]["final_pv_ends_in_checkmate"], "True")
        self.assertEqual(rows[1]["reported_mate"], str(-supplied))
        self.assertEqual(rows[1]["reported_positive_mate"], "False")
        self.assertEqual(rows[1]["final_pv_ends_in_checkmate"], "False")
        self.assertEqual(rows[2]["score_type"], "cp")
        self.assertEqual(rows[2]["score_value"], "121")
        self.assertEqual(rows[2]["score_pawns"], "1.21")
        self.assertEqual(rows[2]["reported_mate"], "")
        self.assertEqual(rows[2]["ponder"], "")
        rendered = (self.output / "comparison.md").read_text()
        self.assertIn(f"| 1 | M{supplied} | M{supplied + 2} / 6 | -M{supplied} / 6 |", rendered)
        self.assertIn("Positive mate reported only with hints off", rendered)
        self.assertIn("proves forced mate", rendered)
        self.assertNotIn("Hints off is stronger", rendered)
        self.assertNotIn("Hints on is stronger", rendered)

    def test_unknown_or_incomplete_schema_is_not_exported(self):
        for field, value in (("schema_version", 2), ("status", "running"),
                             ("protocol", "future-protocol"), ("mode", "partial")):
            with self.subTest(field=field):
                previous = self.fixture.report[field]
                self.fixture.report[field] = value
                self.fixture.save()
                with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), self.assertRaises(ValueError):
                    p.export_report(self.fixture.path, self.output)
                self.assertFalse(self.output.exists())
                self.fixture.report[field] = previous
                self.fixture.save()

    def test_failed_audit_certificate_is_not_treated_as_passed(self):
        certificate = self.fixture.certificate(); certificate["status"] = "failed"
        with patch.object(p.auditor, "audit", return_value=certificate), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())

    def test_arbitrary_text_cannot_inject_markdown_or_spreadsheet_formulas(self):
        hostile = '<script>alert(1)</script>|`quoted`\n=HYPERLINK("bad")'
        self.fixture.report["engine_source_revision"] = hostile
        off = self.fixture.sample(0, "hints-off")["result"]
        off["bestmove"] = '=HYPERLINK("bad","click")'
        off["ponder"] = "\t@injected"
        off["score"] = {"type": "cp", "value": -125}
        self.fixture.save()
        self.export()
        rendered = (self.output / "comparison.md").read_text()
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&#124;", rendered)
        self.assertIn("\\u000a", rendered)
        self.assertIn("<code>=HYPERLINK(&quot;bad&quot;,&quot;click&quot;)</code>", rendered)
        with (self.output / "positions.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["bestmove"], "'" + off["bestmove"])
        self.assertEqual(rows[0]["ponder"], "'" + off["ponder"])
        self.assertEqual(rows[0]["score_value"], "-125")
        self.assertEqual(rows[0]["score_pawns"], "-1.25")
        for value in ("=1+1", "+SUM(A1)", "-SUM(A1)", "@SUM(A1)", "  =1+1", "\r1", "\n1"):
            with self.subTest(value=value):
                self.assertEqual(p.spreadsheet_text(value), "'" + value)
        self.assertEqual(p.spreadsheet_text("e2e4"), "e2e4")

    def test_audit_failure_publishes_nothing_and_preserves_inputs(self):
        before = self.snapshot()
        with patch.object(p.auditor, "audit", side_effect=ValueError("bad raw PV")):
            with self.assertRaises(ValueError): p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot(), before)

    def test_certificate_must_bind_exact_report_bytes(self):
        certificate = self.fixture.certificate(); certificate["report_sha256"] = "0" * 64
        with patch.object(p.auditor, "audit", return_value=certificate), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())

    def test_report_replaced_after_audit_is_rejected(self):
        certificate = self.fixture.certificate()
        def audited(_):
            self.fixture.path.write_text(self.fixture.path.read_text() + " ")
            return certificate
        with patch.object(p.auditor, "audit", side_effect=audited), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())

    def test_changed_evidence_after_audit_is_rejected(self):
        certificate = self.fixture.certificate()
        def audited(_):
            Path(self.fixture.report["assets"]["engine"]["path"]).write_text("changed")
            return certificate
        with patch.object(p.auditor, "audit", side_effect=audited), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())

    def test_raw_evidence_changed_while_staging_blocks_publication(self):
        original = p._write_staged
        raw = self.fixture.evidence / self.fixture.report["samples"][0]["raw_log"]
        def change_evidence(stage, *args):
            original(stage, *args)
            raw.write_text("replaced after audit")
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), \
             patch.object(p, "_write_staged", side_effect=change_evidence), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".puzzle-report-*")), [])

    def test_manifest_pinned_source_changed_while_staging_blocks_publication(self):
        source = self.root / "source fixture.txt"
        source.write_text("original pinned source")
        manifest = self.fixture.evidence / "manifest.json"
        manifest.write_text(json.dumps({"source_sha256": {source.name: sha(source)}}))
        self.fixture.report["assets"]["engine_manifest"] = {"path": str(manifest), "sha256": sha(manifest)}
        self.fixture.save()
        original = p._write_staged
        def change_source(stage, *args):
            original(stage, *args)
            source.write_text("changed pinned source")
        with patch.object(p.auditor, "ROOT", self.root), \
             patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), \
             patch.object(p, "_write_staged", side_effect=change_source), self.assertRaises(ValueError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".puzzle-report-*")), [])

    def test_existing_output_directory_and_file_are_never_overwritten(self):
        for is_directory in (False, True):
            target = self.root / ("existing-dir" if is_directory else "existing-file")
            if is_directory:
                target.mkdir(); (target / "comparison.md").write_text("user file")
            else: target.write_text("user file")
            before = self.snapshot()
            with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), self.assertRaises((ValueError, OSError)):
                p.export_report(self.fixture.path, target)
            self.assertEqual(before, self.snapshot())

    def test_output_must_not_replace_input_report(self):
        before = self.snapshot()
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), self.assertRaises((ValueError, OSError)):
            p.export_report(self.fixture.path, self.fixture.path)
        self.assertEqual(before, self.snapshot())

    def test_existing_empty_directory_and_symlink_are_preserved(self):
        empty = self.root / "existing empty directory"; empty.mkdir()
        link = self.root / "existing link"
        try:
            link.symlink_to(empty, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable on this host")
        for target in (empty, link):
            with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), self.assertRaises((ValueError, OSError)):
                p.export_report(self.fixture.path, target)
        self.assertTrue(link.is_symlink())
        self.assertEqual(list(empty.iterdir()), [])

    def test_failed_staged_write_removes_only_own_temporary_output(self):
        before = self.snapshot()
        def failed(stage, *args):
            (stage / "comparison.md").write_text("partial")
            raise OSError("simulated disk write failure")
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), \
             patch.object(p, "_write_staged", side_effect=failed), self.assertRaises(OSError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot(), before)

    def test_failed_publication_preserves_foreign_file_added_to_output(self):
        original = p.shutil.copyfileobj
        calls = 0
        def fail_second(source, target, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.output / "foreign.txt").write_text("another writer owns this")
                raise OSError("simulated copy failure with concurrent writer")
            return original(source, target, *args, **kwargs)
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), \
             patch.object(p.shutil, "copyfileobj", side_effect=fail_second), self.assertRaises(OSError):
            p.export_report(self.fixture.path, self.output)
        self.assertEqual({item.name for item in self.output.iterdir()}, {"foreign.txt"})
        self.assertEqual((self.output / "foreign.txt").read_text(), "another writer owns this")

    def test_failed_publication_removes_created_files_and_preserves_other_files(self):
        before = self.snapshot()
        original = p.shutil.copyfileobj
        calls = 0
        def fail_second(source, target, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError("simulated second-file copy failure")
            return original(source, target, *args, **kwargs)
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), \
             patch.object(p.shutil, "copyfileobj", side_effect=fail_second), self.assertRaises(OSError):
            p.export_report(self.fixture.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.snapshot(), before)

    def test_missing_output_parent_is_not_silently_created(self):
        missing = self.root / "missing" / "export"
        with patch.object(p.auditor, "audit", return_value=self.fixture.certificate()), self.assertRaises((ValueError, OSError)):
            p.export_report(self.fixture.path, missing)
        self.assertFalse(missing.parent.exists())

    def test_cli_passes_paths_literally_and_requires_output(self):
        with patch.object(p, "export_report", return_value=self.output) as export, redirect_stdout(io.StringIO()):
            self.assertEqual(p.main([str(self.fixture.path), "--output", str(self.output)]), 0)
        export.assert_called_once_with(self.fixture.path, self.output)
        with redirect_stdout(io.StringIO()), patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            p.main([str(self.fixture.path)])


if __name__ == "__main__":
    unittest.main()
