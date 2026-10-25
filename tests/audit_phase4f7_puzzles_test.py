#!/usr/bin/env python3
"""Synthetic independent-auditor checks; never start a real engine or match.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
import audit_phase4f7_puzzles as a


SETTINGS = {
    "Threads": "8", "Hash": "64", "Ponder": "false", "Move Overhead": "20",
    "Time Policy": "classic", "Search Diagnostics": "false", "Late Move Reductions": "true",
    "Deep Quiet Reductions": "false", "Capture Ordering": "mvv-lva", "Countermove Ordering": "false",
    "Null Move Pruning": "false", "Reverse Futility Pruning": "false", "QSearch SEE Pruning": "false",
    "ProbCut": "false", "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
    "TT Move Hints": "false",
}


class Fixture:
    """Construct full raw sessions independently of the campaign and auditor."""
    def __init__(self, root, mode="smoke"):
        self.root, self.mode = root, mode
        root.mkdir(exist_ok=True)
        self.wall = datetime(2026, 10, 25, 12, tzinfo=timezone.utc).timestamp()
        self.mono = 1000.0
        positions = json.loads((PROJECT / "tests/data/phase4f3-puzzles.json").read_text())["positions"]
        self.assets = {}
        for name in set(a.REQUIRED_ASSETS) | {"engine", "network", "corpus", "owner_source", "src/test.cpp"}:
            if name != "pins":
                path = root / (name if "/" in name else name + ".fixture")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic " + name)
                self.assets[name] = {"path": str(path), "sha256": a.digest(path)}
        corpus = {"schema_version": 1, "owner_source_sha256": self.assets["owner_source"]["sha256"], "positions": positions}
        self.asset_json("corpus", corpus)
        self.asset_json("engine_manifest", dict(schema_version=1, engine_source_revision=a.SOURCE_REVISION,
                        binary_sha256=self.assets["engine"]["sha256"], network_sha256=self.assets["network"]["sha256"],
                        source_sha256={"src/test.cpp": self.assets["src/test.cpp"]["sha256"]}))
        pins = root / "pins.json"
        pins.write_text(json.dumps(dict(schema_version=1, engine_source_revision=a.SOURCE_REVISION,
                                      assets={name: entry["sha256"] for name, entry in self.assets.items()})))
        self.assets["pins"] = dict(path=str(pins), sha256=a.digest(pins))
        self.fixed = {name: self.assets[name]["sha256"] for name in a.FIXED_SHA256}
        options = {role: dict(SETTINGS, **{"TT Move Hints": "true" if role == "hints-on" else "false", "EvalFile": self.assets["network"]["path"]})
                   for role in ("hints-off", "hints-on")}
        self.report = dict(schema_version=1, protocol="phase4f7-tt-hints-puzzles-v1", engine_source_revision=a.SOURCE_REVISION,
                           status="complete", mode=mode, chess_version="1.11.2", assets=self.assets,
                           after_sha256={name: entry["sha256"] for name, entry in self.assets.items()},
                           started_utc=self.iso(), positions=positions, options=options, allow_daytime=mode == "full",
                           quiet_host=mode == "full", settings={"movetime_ms": 0 if mode == "check" else 1000 if mode == "smoke" else 60000,
                                                                  "total_seconds": 7200 if mode == "full" else 600},
                           receipt_tolerance_seconds=.250, search_watchdog_grace_seconds=5.0, clock_gap_limit_seconds=5.0,
                           initial_resource_policy=self.policy(), monitor_events=[], samples=[],
                           launch_window={"cutoff_utc": "2026-10-26T05:00:00+00:00" if mode == "full" else None,
                                          "timezone": "Europe/Helsinki", "local_time": datetime.fromtimestamp(self.wall, ZoneInfo("Europe/Helsinki")).isoformat(),
                                          "nighttime": False, "allow_daytime": mode == "full",
                                          "minimum_remaining_seconds": 5070 if mode == "full" else 0 if mode == "check" else 468})
        self.monitor()
        cases = [(None, role) for role in ("hints-off", "hints-on")] if mode == "check" else [
            (index, role) for index in range(39) for role in (("hints-off", "hints-on") if index % 2 == 0 else ("hints-on", "hints-off"))]
        for index, role in cases:
            self.session(index, role, options[role])
        self.monitor()
        self.report["finished_utc"] = self.iso()
        counts = {role: {field: 0 for field in ("reported_positive_mate", "reported_mate_matches_supplied", "final_pv_ends_in_checkmate")} for role in options}
        for sample in self.report["samples"]:
            if "result" in sample:
                for field in counts[sample["role"]]:
                    counts[sample["role"]][field] += bool(sample["result"][field])
        self.report["summary"] = dict(positions=39, sessions=len(cases), searches=0 if mode == "check" else 78)
        if mode != "check":
            self.report["summary"].update(roles=counts, same_bestmove=39, positive_mate_report_gains=[], positive_mate_report_losses=[])
        self.save()

    def asset_json(self, name, data):
        path = Path(self.assets[name]["path"])
        path.write_text(json.dumps(data))
        self.assets[name]["sha256"] = a.digest(path)

    def iso(self):
        return datetime.fromtimestamp(self.wall, timezone.utc).isoformat()

    def tick(self, seconds=.001):
        self.wall += seconds
        self.mono += seconds

    def policy(self):
        return dict(timezone="Europe/Helsinki", local_time=datetime.fromtimestamp(self.wall, ZoneInfo("Europe/Helsinki")).isoformat(),
                    source="daytime", percent=50, logical_cpus=18, max_cpu_workers=9, memory_fraction=.5,
                    active_search_workers=8, resident_engines=1, estimated_memory_bytes=2 * 1024**3,
                    physical_memory_bytes=64 * 1024**3, memory_estimate_is_hard_cap=False)

    def monitor(self):
        self.tick()
        self.report["monitor_events"].append(dict(event="resource_check", wall=self.wall, monotonic=self.mono, policy=self.policy()))

    def session(self, index, role, options):
        self.monitor()
        position = self.report["positions"][index] if index is not None else None
        pid = 6000 + len(self.report["samples"])
        sample = dict(status="complete", position_index=index, position_id=position["id"] if position else None,
                      role=role, pid=pid, options=options, commands=[], identity=[], setup_output=[], preparation_output=[],
                      output=[], post_search_output=[], shutdown_output=[], shutdown_eof_count=1, exit_code=0,
                      reader_alive=False, received_transcript=[], raw_log=f"session-{pid}.jsonl")
        rows = []

        def event(**kwargs):
            self.tick()
            row = dict(wall=self.wall, monotonic=self.mono, **kwargs)
            rows.append(row)
            return row

        def sent(command):
            sample["commands"].append(command)
            return event(direction=">", line=command)

        def received(lines, field):
            sample[field] = list(lines)
            for line in lines:
                sample["received_transcript"].append(line)
                event(direction="<", line=line)

        event(event="process_start", pid=pid)
        sent("uci")
        defaults = dict(SETTINGS, Threads="1", SyzygyProbeLimit="7", EvalFile="nn-1a298aa575a0.nnue")
        declarations = ["id name chess0live 0.1-dev", "id author Claudio M. Camacho", "option name Clear Hash type button"]
        for name, default in defaults.items():
            if name in ("Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth"):
                kind, tail = "spin", f" default {default} min 0 max 16384"
            elif name in ("EvalFile", "SyzygyPath"):
                kind, tail = "string", f" default {default}"
            elif name == "Time Policy":
                kind, tail = "combo", " default classic var classic var forecast var bounded"
            elif name == "Capture Ordering":
                kind, tail = "combo", " default mvv-lva var mvv-lva var see"
            else:
                kind, tail = "check", f" default {default}"
            declarations.append(f"option name {name} type {kind}{tail}")
        received(declarations + ["uciok"], "identity")
        for name, value in options.items():
            sent(f"setoption name {name} value {value}")
        sent("isready")
        received(["info string Syzygy largest 0 pieces; table files are external", "readyok"], "setup_output")
        sent("ucinewgame")
        if position:
            sent("position fen " + position["fen"])
        sent("isready")
        received(["readyok"], "preparation_output")
        if position:
            movetime = 1000 if self.mode == "smoke" else 60000
            go = sent("go movetime " + str(movetime))
            # Long synthetic silence includes independent monitor observations;
            # virtual time advances without sleeping or starting any process.
            if self.mode == "full":
                for _ in range(29):
                    self.tick(1.99)
                    self.monitor()
            else:
                self.tick(.1)
            board = a.chess.Board(position["fen"])
            best = next(iter(board.legal_moves)).uci()
            board.push_uci(best)
            ponder = next(iter(board.legal_moves)).uci() if any(board.legal_moves) else None
            pv = [best] + ([ponder] if ponder else [])
            if ponder:
                board.push_uci(ponder)
            iteration = dict(depth=1, seldepth=len(pv), score={"type": "cp", "value": 10}, nodes=20,
                             time=10, nps=2000, hashfull=0, pv=pv)
            totals = dict(nodes=25, time=12, nps=2083, hashfull=0, tbhits=0)
            lines = [f"info depth 1 seldepth {len(pv)} score cp 10 nodes 20 time 10 nps 2000 hashfull 0 tbhits 0 pv {' '.join(pv)}",
                     "info nodes 25 time 12 nps 2083 hashfull 0 tbhits 0",
                     "bestmove " + best + (" ponder " + ponder if ponder else "")]
            received(lines, "output")
            end = rows[-1]
            sample.update(search_started_wall=go["wall"], search_started_monotonic=go["monotonic"],
                          bestmove_received_wall=end["wall"], bestmove_received_monotonic=end["monotonic"],
                          elapsed_seconds=end["monotonic"] - go["monotonic"], wall_elapsed_seconds=end["wall"] - go["wall"],
                          within_receipt_tolerance=True, movetime_overrun_seconds=0)
            sample["result"] = dict(bestmove=best, ponder=ponder, completed_depth=1, reported_nodes=25, reported_time_ms=12,
                                    reported_nps=2083, score=iteration["score"], hashfull=0, iterations=[iteration],
                                    final_aggregate=totals, score_cp=10, reported_mate=None, supplied_mate=position["supplied_mate"],
                                    reported_positive_mate=False, reported_mate_matches_supplied=False,
                                    first_positive_mate_iteration=None, final_pv_ends_in_checkmate=board.is_checkmate())
            sent("isready")
            received(["readyok"], "post_search_output")
        self.monitor()
        sent("quit")
        event(direction="<", line=None)
        event(event="process_exit", pid=pid, exit_code=0, reader_alive=False, shutdown_eof_count=1)
        sample["finished_utc"] = self.iso()
        self.write_rows(sample, rows)
        self.report["samples"].append(sample)

    def rows(self, sample=0):
        return [json.loads(line) for line in (self.root / self.report["samples"][sample]["raw_log"]).read_text().splitlines()]

    def write_rows(self, sample, rows):
        path = self.root / sample["raw_log"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        sample["raw_sha256"] = a.digest(path)

    def save(self):
        self.path = self.root / "report.json"
        self.path.write_text(json.dumps(self.report))

    def run(self):
        self.save()
        with patch.object(a, "FIXED_SHA256", self.fixed), patch.object(a, "ROOT", self.root):
            return a.audit(self.path)


class AuditorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def fixture(self, mode="smoke"):
        return Fixture(self.root / mode, mode)

    def test_complete_smoke_reconstructed(self):
        result = self.fixture().run()
        self.assertEqual((result["positions"], result["searches"], result["raw_sessions"], result["zero_exits"]), (39, 78, 78, 78))
        self.assertEqual(result["iterations"], 78)
        self.assertGreater(result["legal_pv_plies"], 78)
        self.assertEqual(result["same_bestmove"], 39)

    def test_check_is_search_free_and_complete(self):
        result = self.fixture("check").run()
        self.assertEqual((result["searches"], result["raw_sessions"], result["readiness_barriers"]), (0, 2, 4))

    def test_full_virtual_time_with_continuous_resource_coverage(self):
        result = self.fixture("full").run()
        self.assertEqual(result["searches"], 78)
        self.assertGreater(result["resource_observations"], 2000)

    def test_incomplete_or_wrong_protocol_rejected(self):
        fixture = self.fixture("check")
        for key, value in (("status", "running"), ("protocol", "other"), ("engine_source_revision", "0" * 40), ("chess_version", "0.0")):
            with self.subTest(key=key):
                old = fixture.report[key]; fixture.report[key] = value
                with self.assertRaises(ValueError): fixture.run()
                fixture.report[key] = old

    def test_role_settings_and_durations_cannot_drift(self):
        fixture = self.fixture("check")
        fixture.report["options"]["hints-on"]["ProbCut"] = "true"
        with self.assertRaisesRegex(ValueError, "recipes"): fixture.run()
        fixture.report["options"]["hints-on"]["ProbCut"] = "false"
        fixture.report["settings"]["movetime_ms"] = 1
        with self.assertRaisesRegex(ValueError, "duration"): fixture.run()

    def test_missing_reordered_or_duplicate_session_rejected(self):
        fixture = self.fixture()
        original = list(fixture.report["samples"])
        for samples in (original[:-1], original[::-1], [original[0]] + original[0:-1]):
            fixture.report["samples"] = samples
            with self.assertRaises(ValueError): fixture.run()

    def test_result_and_summary_must_match_raw(self):
        fixture = self.fixture()
        fixture.report["samples"][0]["result"]["score_cp"] = 999
        with self.assertRaisesRegex(ValueError, "result differs"): fixture.run()
        fixture.report["samples"][0]["result"]["score_cp"] = 10
        fixture.report["summary"]["same_bestmove"] = 38
        with self.assertRaisesRegex(ValueError, "Summary differs"): fixture.run()

    def test_raw_hash_and_current_asset_drift_rejected(self):
        fixture = self.fixture("check")
        sample = fixture.report["samples"][0]
        sample["raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Raw transcript hash"): fixture.run()
        sample["raw_sha256"] = a.digest(fixture.root / sample["raw_log"])
        Path(fixture.assets["network"]["path"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "Changed pinned asset"): fixture.run()

    def test_manifest_missing_or_inconsistent_pins_rejected(self):
        fixture = self.fixture("check")
        fixture.report["after_sha256"].pop("network")
        with self.assertRaisesRegex(ValueError, "asset identities"): fixture.run()
        fixture.report["after_sha256"]["network"] = fixture.assets["network"]["sha256"]
        fixture.report["assets"].pop("Makefile")
        fixture.report["after_sha256"].pop("Makefile")
        with self.assertRaisesRegex(ValueError, "required campaign inputs"): fixture.run()

    def test_actual_option_command_tampering_rejected_even_with_updated_hash(self):
        fixture = self.fixture("check"); rows = fixture.rows()
        row = next(row for row in rows if row.get("line") == "setoption name Threads value 8")
        row["line"] = "setoption name Threads value 10"
        fixture.write_rows(fixture.report["samples"][0], rows)
        with self.assertRaisesRegex(ValueError, "applied option"): fixture.run()

    def test_extra_search_in_check_rejected(self):
        fixture = self.fixture("check"); rows = fixture.rows()
        next(row for row in rows if row.get("line") == "quit")["line"] = "go movetime 1000"
        fixture.write_rows(fixture.report["samples"][0], rows)
        with self.assertRaisesRegex(ValueError, "expected quit"): fixture.run()

    def test_nonzero_exit_live_reader_missing_eof_and_pid_tampering(self):
        fixture = self.fixture("check"); original = fixture.rows()
        for field, value in (("exit_code", 7), ("reader_alive", True), ("shutdown_eof_count", 0), ("pid", 9999)):
            with self.subTest(field=field):
                rows = copy.deepcopy(original); rows[-1][field] = value
                fixture.write_rows(fixture.report["samples"][0], rows)
                with self.assertRaisesRegex(ValueError, "process-exit"): fixture.run()
        rows = copy.deepcopy(original); rows[-2]["line"] = "unexpected output"
        fixture.write_rows(fixture.report["samples"][0], rows)
        with self.assertRaisesRegex(ValueError, "EOF"): fixture.run()

    def test_raw_transcript_and_pid_summary_cannot_disagree(self):
        fixture = self.fixture("check")
        fixture.report["samples"][0]["pid"] += 1
        with self.assertRaisesRegex(ValueError, "process-start"): fixture.run()
        fixture.report["samples"][0]["pid"] -= 1
        fixture.report["samples"][0]["received_transcript"].pop()
        with self.assertRaisesRegex(ValueError, "exhaust raw"): fixture.run()

    def test_raw_clock_backwards_and_monitor_gap_rejected(self):
        fixture = self.fixture("check"); rows = fixture.rows()
        rows[2]["monotonic"] = rows[1]["monotonic"] - 1
        fixture.write_rows(fixture.report["samples"][0], rows)
        with self.assertRaisesRegex(ValueError, "clocks went backwards"): fixture.run()
        fixture = self.fixture("full")
        fixture.report["monitor_events"] = fixture.report["monitor_events"][::10]
        with self.assertRaisesRegex(ValueError, "gap"): fixture.run()

    def test_raw_receipt_timing_and_duration_summary_tampering_rejected(self):
        fixture = self.fixture()
        fixture.report["samples"][0]["elapsed_seconds"] += .01
        with self.assertRaisesRegex(ValueError, "timing disagrees"): fixture.run()

    def test_insufficient_cpu_memory_and_resource_window_rejected(self):
        fixture = self.fixture("check")
        policy = fixture.report["monitor_events"][0]["policy"]
        original = dict(policy)
        for changes in ({"logical_cpus": 4, "max_cpu_workers": 2}, {"physical_memory_bytes": 1024**3}, {"source": "nighttime", "percent": 80}):
            with self.subTest(changes=changes):
                policy.clear(); policy.update(original, **changes)
                with self.assertRaises(ValueError): fixture.run()

    def test_full_needs_quiet_assertion_daytime_exception_and_correct_cutoff(self):
        fixture = self.fixture("full")
        for key, value in (("quiet_host", False), ("allow_daytime", False)):
            with self.subTest(key=key):
                fixture.report[key] = value
                with self.assertRaises(ValueError): fixture.run()
                fixture.report[key] = True
        fixture.report["launch_window"]["cutoff_utc"] = "2026-10-26T04:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "cutoff"): fixture.run()

    def test_full_window_metadata_and_final_resource_coverage_are_replayed(self):
        fixture = self.fixture("full")
        window = fixture.report["launch_window"]
        for key, value in (("timezone", "UTC"), ("nighttime", True), ("allow_daytime", False), ("minimum_remaining_seconds", 1),
                           ("local_time", "2026-10-25T14:00:20+02:00")):
            with self.subTest(key=key):
                original = window[key]; window[key] = value
                with self.assertRaises(ValueError): fixture.run()
                window[key] = original
        fixture.report["monitor_events"].pop()
        with self.assertRaisesRegex(ValueError, "last process exit"): fixture.run()

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            json.loads('{"status":"failed","status":"complete"}', object_pairs_hook=a.unique_object)

    def test_result_parser_rejects_illegal_pv_bounds_tablebase_or_diagnostics(self):
        position = dict(fen=a.chess.STARTING_FEN, supplied_mate=7)
        lines = ["info depth 1 seldepth 2 score cp 10 nodes 20 time 10 nps 2000 hashfull 0 tbhits 0 pv g1h3 g8h6",
                 "info nodes 25 time 12 nps 2083 hashfull 0 tbhits 0", "bestmove g1h3 ponder g8h6"]
        self.assertEqual(a.parse_search(lines, position)[1], 2)
        for replacement in (lines[0].replace("g1h3", "e2e5"), lines[0].replace("score cp 10", "score cp 10 lowerbound"),
                            lines[0].replace("tbhits 0", "tbhits 1"), "info string move-hints v1 enabled true"):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                a.parse_search([replacement] + lines[1:], position)

    def test_cli_never_overwrites_certificate(self):
        fixture = self.fixture("check")
        output = fixture.root / "certificate.json"
        with patch.object(a, "FIXED_SHA256", fixture.fixed), patch.object(a, "ROOT", fixture.root), redirect_stdout(io.StringIO()):
            a.main([str(fixture.path), "--output", str(output)])
            with self.assertRaises(FileExistsError): a.main([str(fixture.path), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
