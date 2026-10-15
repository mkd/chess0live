#!/usr/bin/env python3
"""Bounded Phase 2D launcher tests; no real engine or held-out search is run.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import qualify_time_policy as qualification
import match
from match_test import FAKE_ENGINE


class CalendarTests(unittest.TestCase):
    def local(self, text):
        return datetime.fromisoformat(text).replace(tzinfo=ZoneInfo("Europe/Helsinki"))

    def test_night_boundaries_and_daytime_check(self):
        for text, permitted in (("2026-10-15T06:59:59", True), ("2026-10-15T07:00:00", False),
                                ("2026-10-15T22:59:59", False), ("2026-10-15T23:00:00", True)):
            with self.subTest(text=text):
                policy = qualification.launch_policy(self.local(text))
                self.assertEqual(policy["nighttime"], permitted)
                if permitted:
                    qualification.launch_policy(self.local(text), require_window=True)
                else:
                    with self.assertRaises(ValueError):
                        qualification.launch_policy(self.local(text), require_window=True)

    def test_owner_exception_keeps_next_morning_deadline(self):
        policy = qualification.launch_policy(self.local("2026-10-15T12:00:00"), True, True)
        self.assertTrue(policy["allow_daytime"])
        self.assertFalse(policy["nighttime"])
        self.assertEqual(policy["remaining_seconds"], 19 * 3600)
        self.assertEqual(policy["cutoff_local"], "2026-10-16T07:00:00+03:00")
        self.assertNotIn("percent", policy)

    def test_dst_elapsed_seconds_are_utc_based(self):
        for text, hours in (("2026-03-28T23:00:00", 7), ("2026-10-24T23:00:00", 9)):
            policy = qualification.launch_policy(self.local(text), require_window=True)
            self.assertEqual(policy["remaining_seconds"], hours * 3600)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            qualification.launch_policy(datetime(2026, 10, 15, 23))


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="chess0live-qualification-test-")
        self.root = Path(self.directory.name)
        self.binary = self.root / "frozen-binary"
        self.binary.write_bytes(b"fake binary pin, never executed")
        self.network = self.root / "network.nnue"
        self.network.write_bytes(b"fake network for protocol tests")
        self.suite = self.root / "openings.json"
        # Fresh test-only roots, never the real reserved qualification openings.
        openings = []
        for first in list(match.chess.Board().legal_moves)[:4]:
            board = match.chess.Board()
            board.push(first)
            for second in list(board.legal_moves)[:8]:
                openings.append({"id": f"fixture-{len(openings)}", "moves": [first.uci(), second.uci()]})
        self.openings = openings
        self.suite.write_text(json.dumps({"openings": openings}))
        pins = {name: (path, match.sha256(path)) for name, path in
                (("engine", self.binary), ("network", self.network), ("openings", self.suite))}
        self.pins = patch.object(qualification, "FROZEN", pins)
        self.pins.start()
        self.sources = patch.object(qualification, "SOURCES", ("tools/qualify_time_policy.py", "docs/PHASE_2D.md"))
        self.sources.start()
        self.now = datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc)  # Helsinki midnight.
        self.clock = patch.object(qualification, "utc_now", return_value=self.now)
        self.now_mock = self.clock.start()
        self.policy = {"percent": 50, "max_cpu_workers": 8, "memory_fraction": 0.5}
        self.resources = patch.object(match, "current_budget", return_value=self.policy.copy())
        self.resources.start()
        self.fake = self.root / "fake.py"
        self.fake.write_text(FAKE_ENGINE)
        logging.getLogger("chess.engine").setLevel(logging.CRITICAL)

    def tearDown(self):
        self.resources.stop()
        self.clock.stop()
        self.sources.stop()
        self.pins.stop()
        self.directory.cleanup()

    def specs(self, mode="normal"):
        specs, settings = qualification.fixed_request()
        return [replace(spec, executable=Path(sys.executable).resolve(), arguments=(str(self.fake), mode))
                for spec in specs], settings

    async def preflight(self):
        # Real fake-UCI startup/readiness, with the production parser/cleanup.
        request = self.specs()
        with patch.object(qualification, "fixed_request", return_value=request):
            return await qualification.check()

    def report(self):
        specs, settings = qualification.fixed_request()
        config = qualification.configuration(specs, settings)
        return {"schema_version": 1, "protocol_id": qualification.PROTOCOL_ID,
                "status": "checked", "configuration": config,
                "configuration_sha256": qualification.configuration_hash(config),
                **qualification.snapshot(), "launch_policy": qualification.launch_policy()}

    def test_exact_request_and_no_setting_override(self):
        specs, settings = qualification.fixed_request()
        self.assertEqual(vars(settings), {"initial": 60.0, "increment": 0.6, "hash_mb": 64,
                         "threads": 1, "max_plies": 512, "startup_timeout": 30.0,
                         "protocol_timeout": 5.0, "move_overhead_ms": 20, "smoke": False})
        self.assertEqual([dict(spec.extra_options) for spec in specs],
                         [{"Time Policy": "forecast"}, {"Time Policy": "classic"}])
        self.assertEqual(specs[0].executable, specs[1].executable)
        self.assertEqual(specs[0].network, specs[1].network)
        self.assertEqual((qualification.PAIRS, qualification.SEED), (32, 20261014))
        with self.assertRaises(SystemExit):
            qualification.main(["run", "--output", str(self.root / "run"), "--pairs", "1"])

    def test_each_asset_mismatch_rejected(self):
        for path in (self.binary, self.network, self.suite):
            contents = path.read_bytes()
            path.write_bytes(contents + b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                qualification.snapshot()
            path.write_bytes(contents)

    def test_pinned_chess_version(self):
        with patch.object(match.chess, "__version__", "wrong"), self.assertRaises(ValueError):
            asyncio.run(qualification.check())

    def test_real_fake_preflight_never_searches(self):
        report = asyncio.run(self.preflight())
        self.assertEqual(report["preflight"]["opening_count"], 32)
        self.assertEqual(report["preflight"]["distinct_roots"], 32)
        for engine in report["preflight"]["engines"]:
            commands = [line["line"] for line in engine["transcript"] if line["direction"] == "to_engine"]
            self.assertIn("uci", commands)
            self.assertIn("isready", commands)
            self.assertIn("quit", commands)
            self.assertFalse(any(line.startswith(("go", "position")) for line in commands))
            self.assertIs(engine["configured"]["Search Diagnostics"], False)

    def test_missing_required_preflight_option(self):
        self.fake.write_text(FAKE_ENGINE.replace(
            '        output("option name Search Diagnostics type check default false")', "        pass"))
        with self.assertRaisesRegex(ValueError, "Search Diagnostics"):
            asyncio.run(self.preflight())

    def test_bad_ponder_default(self):
        self.fake.write_text(FAKE_ENGINE.replace("Ponder type check default false", "Ponder type check default true"))
        with self.assertRaisesRegex(ValueError, "Ponder must default"):
            asyncio.run(self.preflight())

    def test_invalid_roots_stop_before_process_startup(self):
        for entries in (self.openings[:31], self.openings[:31] + [self.openings[0]],
                        self.openings[:31] + [{"id": "terminal", "fen": "7k/8/5K2/8/8/8/8/8 w - - 0 1"}]):
            self.suite.write_text(json.dumps({"openings": entries}))
            qualification.FROZEN["openings"] = (self.suite, match.sha256(self.suite))
            with patch.object(match, "start_engine", new_callable=AsyncMock) as startup:
                with self.assertRaises(ValueError):
                    asyncio.run(qualification.check())
                startup.assert_not_called()

    def test_resource_budget_enforced(self):
        with patch.object(match, "current_budget", return_value=dict(self.policy, max_cpu_workers=0)), \
             patch.object(match, "start_engine", new_callable=AsyncMock) as startup:
            with self.assertRaisesRegex(ValueError, "resource budget"):
                asyncio.run(qualification.check())
            startup.assert_not_called()

    def test_new_directory_and_daytime_permission(self):
        with self.assertRaisesRegex(ValueError, "new directory"):
            asyncio.run(qualification.run(self.root))
        self.now_mock.return_value = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)
        with patch.object(qualification, "check", new_callable=AsyncMock) as preflight:
            with self.assertRaisesRegex(ValueError, "owner authorization"):
                asyncio.run(qualification.run(self.root / "day"))
            preflight.assert_not_called()

    def test_window_rechecked_after_readiness(self):
        report = self.report()
        async def readiness_crosses_cutoff():
            self.now_mock.return_value = datetime(2026, 10, 16, 4, tzinfo=timezone.utc)
            return report
        with patch.object(qualification, "check", side_effect=readiness_crosses_cutoff), \
             patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaises(ValueError):
                asyncio.run(qualification.run(self.root / "late"))
            runner.assert_not_called()

    def test_daytime_exception_cannot_roll_cutoff_forward_during_preflight(self):
        report = self.report()
        self.now_mock.return_value = datetime(2026, 10, 16, 3, 59, tzinfo=timezone.utc)
        async def readiness_crosses_cutoff():
            self.now_mock.return_value = datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)
            return report
        with patch.object(qualification, "check", side_effect=readiness_crosses_cutoff), \
             patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "initial Helsinki"):
                asyncio.run(qualification.run(self.root / "late-override", allow_daytime=True))
            runner.assert_not_called()

    def test_exact_run_evidence_and_clean_match_subdirectory(self):
        report = self.report()
        async def runner(specs, settings, suite, output, pairs, seed):
            self.assertEqual((pairs, seed), (32, 20261014))
            self.assertEqual(suite, self.suite)
            self.assertFalse(output.exists())
            before = json.loads((output.parent / "launch.json").read_text())
            self.assertEqual(before["status"], "running")
            self.assertTrue((output.parent / "protocol.md").is_file())
            return {"experiment_complete": True}
        output = self.root / "complete"
        with patch.object(qualification, "check", return_value=report), patch.object(match, "run_match", side_effect=runner):
            result = asyncio.run(qualification.run(output))
        self.assertEqual(result["status"], "finished")
        self.assertTrue(result["integrity_after"]["unchanged"])
        self.assertEqual(result["protocol_document"]["sha256"], match.sha256(output / "protocol.md"))
        with self.assertRaises(ValueError):
            asyncio.run(qualification.run(output))

    def test_authorized_daytime_keeps_resource_percentage(self):
        self.now_mock.return_value = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)
        with patch.object(qualification, "check", return_value=self.report()), \
             patch.object(match, "run_match", return_value={"experiment_complete": True}):
            result = asyncio.run(qualification.run(self.root / "override", allow_daytime=True))
        self.assertTrue(result["launch_policy"]["allow_daytime"])
        self.assertFalse(result["launch_policy"]["nighttime"])
        self.assertEqual(match.current_budget()["percent"], 50)

    def test_post_match_asset_change_invalidates_result(self):
        async def changed(*_):
            self.network.write_bytes(b"changed during last game")
            return {"experiment_complete": True}
        output = self.root / "changed"
        with patch.object(qualification, "check", return_value=self.report()), patch.object(match, "run_match", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                asyncio.run(qualification.run(output))
        result = json.loads((output / "launch.json").read_text())
        self.assertEqual(result["status"], "invalidated")
        self.assertFalse(result["integrity_after"]["unchanged"])

    def test_settings_and_source_change_invalidated(self):
        report = self.report()
        specs, settings = qualification.fixed_request()
        with self.assertRaises(ValueError):
            qualification.verify_unchanged(report, specs, replace(settings, initial=1))
        report["sources"]["tools/qualify_time_policy.py"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            qualification.verify_unchanged(report, specs, settings)

    def test_deadline_cancels_and_awaits_cleanup(self):
        output = self.root / "deadline"
        cleaned = []
        async def blocking(*_):
            try:
                await asyncio.Future()
            finally:
                await asyncio.sleep(0)
                cleaned.append(True)
        policy = qualification.launch_policy()
        policy["cutoff_utc"] = (self.now + timedelta(milliseconds=20)).isoformat()
        with patch.object(qualification, "check", return_value=self.report()), \
             patch.object(qualification, "launch_policy", return_value=policy), \
             patch.object(match, "run_match", side_effect=blocking) as runner:
            with self.assertRaises(qualification.WindowExpired):
                asyncio.run(qualification.run(output))
            runner.assert_awaited_once()
        self.assertEqual(cleaned, [True])
        self.assertEqual(json.loads((output / "launch.json").read_text())["status"], "interrupted")

    def test_cancellation_preserves_real_fake_game_and_reaps_children(self):
        request = self.specs("hang")
        # Keep all real match settings; cancel after the fake process receives go.
        transports = []
        original_start = match.start_engine
        async def start(*args):
            result = await original_start(*args)
            transports.append(result[0])
            return result
        async def exercise():
            with patch.object(qualification, "fixed_request", return_value=request):
                report = self.report()
                with patch.object(qualification, "check", return_value=report), patch.object(match, "start_engine", side_effect=start):
                    output = self.root / "cancelled"
                    task = asyncio.create_task(qualification.run(output))
                    # The protocol log is flushed when commands are written by
                    # the recording wrapper below, making cancellation causal.
                    async def find_go():
                        while True:
                            logs = list((output / "match").glob("*.protocol.jsonl"))
                            if any('"line": "go ' in path.read_text() for path in logs):
                                return
                            await asyncio.sleep(0.01)
                    try:
                        await asyncio.wait_for(find_go(), 5)
                    finally:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    return output
        original_record = match.RecordingProtocol.record
        def flushed(protocol, *args):
            original_record(protocol, *args)
            protocol.log.flush()
        with patch.object(match.RecordingProtocol, "record", new=flushed):
            output = asyncio.run(exercise())
        launch = json.loads((output / "launch.json").read_text())
        self.assertEqual(launch["status"], "interrupted")
        self.assertTrue(launch["integrity_after"]["unchanged"])
        self.assertEqual(json.loads((output / "match/run.json").read_text())["status"], "interrupted")
        self.assertFalse(json.loads((output / "match/summary.json").read_text())["experiment_complete"])
        games = [json.loads(line) for line in (output / "match/games.jsonl").read_text().splitlines()]
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["status"], "interrupted")
        self.assertTrue((output / "match" / games[0]["pgn"]).exists())
        self.assertEqual(len(transports), 2)
        self.assertTrue(all(transport.get_returncode() is not None for transport in transports))


if __name__ == "__main__":
    unittest.main()
