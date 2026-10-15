#!/usr/bin/env python3
"""Isolated LMR profile checks using original synthetic roots and fake UCI only.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import match
import qualify_lmr as qualification
import qualify_time_policy as historical
from match_test import FAKE_ENGINE

DECLARED_PINS = qualification.FROZEN.copy()
DECLARED_SOURCES = qualification.SOURCES


class LmrLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="chess0live-lmr-qualification-test-")
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.binary = self.root / "frozen-engine"
        self.binary.write_bytes(b"mock frozen engine")
        self.network = self.root / "network.nnue"
        self.network.write_bytes(b"mock network")
        self.suite = self.root / "openings.json"
        # 64 new test-only roots; no reserved qualification line is loaded.
        self.openings = []
        for first in list(match.chess.Board().legal_moves)[:8]:
            board = match.chess.Board()
            board.push(first)
            for second in list(board.legal_moves)[:8]:
                self.openings.append({"id": f"test-{len(self.openings)}", "moves": [first.uci(), second.uci()]})
        self.suite.write_text(json.dumps({"openings": self.openings}))
        pins = {name: (path, match.sha256(path)) for name, path in
                (("engine", self.binary), ("network", self.network), ("openings", self.suite))}
        self.patch(qualification, "FROZEN", pins)
        sources = ("tools/qualify_lmr.py", "tools/qualification.py", "docs/PHASE_2D_LMR.md")
        for source in sources:
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Original launcher test fixture: " + source)
        self.patch(qualification, "ROOT", self.root)
        self.patch(qualification, "SOURCES", sources)
        self.now = datetime(2026, 10, 15, 21, tzinfo=timezone.utc)
        self.clock = self.patch(qualification, "utc_now", return_value=self.now)
        self.patch(match, "current_budget", return_value={"percent": 50, "max_cpu_workers": 8, "memory_fraction": 0.5})
        self.fake = self.root / "fake.py"
        self.fake.write_text(FAKE_ENGINE.replace(
            '        output("option name Research Toggle type check default true")',
            '        output("option name Late Move Reductions type check default false")'))

    def patch(self, target, name, *args, **kwargs):
        patcher = patch.object(target, name, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def report(self):
        specs, settings = qualification.fixed_request()
        config = qualification.configuration(specs, settings)
        return {"schema_version": 1, "protocol_id": qualification.PROTOCOL_ID,
                "configuration": config, "configuration_sha256": qualification.configuration_hash(config),
                **qualification.snapshot()}

    async def fake_preflight(self):
        specs, settings = qualification.fixed_request()
        specs = [replace(spec, executable=Path(sys.executable).resolve(), arguments=(str(self.fake), "normal"))
                 for spec in specs]
        with patch.object(qualification, "fixed_request", return_value=(specs, settings)):
            return await qualification.check()

    def test_exact_pins_and_isolated_settings(self):
        self.assertEqual(DECLARED_PINS["engine"][1],
                         "b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc")
        self.assertEqual(DECLARED_PINS["network"][1], historical.FROZEN["network"][1])
        self.assertEqual(DECLARED_PINS["openings"][0].name, "openings-lmr-validation.json")
        self.assertEqual(len(DECLARED_PINS["openings"][1]), 64)
        self.assertEqual((qualification.PROTOCOL_ID, qualification.PAIRS, qualification.SEED),
                         ("phase2d-lmr-128-v1", 64, 20261015))
        specs, settings = qualification.fixed_request()
        self.assertEqual([dict(spec.extra_options) for spec in specs],
                         [{"Time Policy": "classic", "Late Move Reductions": "true"},
                          {"Time Policy": "classic", "Late Move Reductions": "false"}])
        self.assertEqual(vars(settings), vars(historical.fixed_request()[1]))
        self.assertEqual(specs[0].executable, specs[1].executable)
        self.assertEqual(specs[0].network, specs[1].network)
        self.assertNotIn("Capture Ordering", qualification.configuration(specs, settings)["engines"][0]["extra_options"])
        self.assertTrue({"tools/qualification.py", "tools/qualify_lmr.py", "tools/audit_lmr.py",
                         "tools/audit_time_policy.py", "docs/PHASE_2D_LMR.md"} <= set(DECLARED_SOURCES))

    def test_frozen_real_suite_has_64_fresh_full_history_roots(self):
        # Referee-only provenance check: never send these positions to an engine.
        path, digest = DECLARED_PINS["openings"]
        self.assertEqual(match.sha256(path), digest)
        _, openings = match.read_openings(path)
        root_key = lambda board: " ".join(board.fen(en_passant="legal").split()[:4])
        roots = {root_key(opening.board) for opening in openings}
        self.assertEqual(len(openings), 64)
        self.assertEqual(len(roots), 64)
        for opening in openings:
            self.assertEqual(opening.board.root().fen(), match.chess.STARTING_FEN)
            self.assertGreater(len(opening.board.move_stack), 0)
        for previous in ("openings-development.json", "openings-validation.json", "openings-time-validation.json"):
            _, previous_roots = match.read_openings(path.parent / previous)
            self.assertFalse(roots & {root_key(opening.board) for opening in previous_roots}, previous)

    def test_preflight_validates_both_roles_without_search_or_later_option(self):
        report = asyncio.run(self.fake_preflight())
        self.assertEqual(report["preflight"]["opening_count"], 64)
        self.assertEqual(report["preflight"]["distinct_roots"], 64)
        for role in report["preflight"]["engines"]:
            commands = [line["line"] for line in role["transcript"] if line["direction"] == "to_engine"]
            self.assertFalse(any(line.startswith(("go", "position")) for line in commands))
            self.assertFalse(any("Capture Ordering" in line for line in commands))
            self.assertEqual(role["configured"]["Time Policy"], "classic")
            self.assertIs(role["configured"]["Late Move Reductions"], role["role"] == "candidate")
            self.assertIs(role["configured"]["Search Diagnostics"], False)
            self.assertIs(role["options"]["Ponder"]["default"], False)

    def test_wrong_lmr_type_or_default_rejected(self):
        original = self.fake.read_text()
        for replacement in ("Late Move Reductions type check default true",
                            "Late Move Reductions type string default false"):
            self.fake.write_text(original.replace("Late Move Reductions type check default false", replacement))
            with self.assertRaisesRegex(ValueError, "Late Move Reductions"):
                asyncio.run(self.fake_preflight())

    def test_missing_lmr_option_rejected(self):
        self.fake.write_text(FAKE_ENGINE)
        with self.assertRaisesRegex(ValueError, "Late Move Reductions"):
            asyncio.run(self.fake_preflight())

    def test_63_or_duplicate_or_terminal_roots_rejected_before_startup(self):
        for entries in (self.openings[:63], self.openings[:63] + [self.openings[0]],
                        self.openings[:63] + [{"id": "dead", "fen": "7k/8/5K2/8/8/8/8/8 w - - 0 1"}]):
            self.suite.write_text(json.dumps({"openings": entries}))
            qualification.FROZEN["openings"] = (self.suite, match.sha256(self.suite))
            with patch.object(match, "start_engine", new_callable=AsyncMock) as startup:
                with self.assertRaises(ValueError):
                    asyncio.run(qualification.check())
                startup.assert_not_called()

    def test_all_frozen_input_changes_rejected(self):
        for path in (self.binary, self.network, self.suite):
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                qualification.snapshot()
            path.write_bytes(original)

    def test_daytime_exception_is_not_inherited(self):
        self.clock.return_value = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)
        with patch.object(qualification, "check", new_callable=AsyncMock) as check:
            with self.assertRaisesRegex(ValueError, "owner authorization"):
                asyncio.run(qualification.run(self.root / "not-authorized"))
            check.assert_not_called()

    def test_original_cutoff_survives_an_explicit_exception(self):
        self.clock.return_value = datetime(2026, 10, 16, 3, 59, tzinfo=timezone.utc)
        report = self.report()
        async def crossed():
            self.clock.return_value = datetime(2026, 10, 16, 4, tzinfo=timezone.utc)
            return report
        with patch.object(qualification, "check", side_effect=crossed), \
             patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "initial Helsinki"):
                asyncio.run(qualification.run(self.root / "late", True))
            runner.assert_not_called()

    def test_run_freezes_exact_lmr_protocol_before_match(self):
        async def runner(specs, settings, suite, output, pairs, seed):
            self.assertEqual((pairs, seed), (64, 20261015))
            self.assertEqual(suite, self.suite)
            self.assertFalse(output.exists())
            launch = json.loads((output.parent / "launch.json").read_text())
            self.assertEqual(launch["status"], "running")
            self.assertEqual(launch["protocol_document"]["source"], "docs/PHASE_2D_LMR.md")
            self.assertEqual(launch["protocol_document"]["sha256"], match.sha256(output.parent / "protocol.md"))
            return {"experiment_complete": True}
        output = self.root / "campaign"
        with patch.object(qualification, "check", return_value=self.report()), patch.object(match, "run_match", side_effect=runner):
            report = asyncio.run(qualification.run(output))
        self.assertEqual(report["status"], "finished")
        self.assertTrue(report["integrity_after"]["unchanged"])
        with self.assertRaisesRegex(ValueError, "new directory"):
            asyncio.run(qualification.run(output))

    def test_deadline_awaits_cancelled_match_cleanup(self):
        cleaned = []
        async def runner(*_):
            try:
                await asyncio.Future()
            finally:
                await asyncio.sleep(0)
                cleaned.append(True)
        policy = qualification.launch_policy()
        policy["cutoff_utc"] = (self.now + timedelta(milliseconds=20)).isoformat()
        output = self.root / "cutoff"
        with patch.object(qualification, "check", return_value=self.report()), \
             patch.object(qualification, "launch_policy", return_value=policy), \
             patch.object(match, "run_match", side_effect=runner):
            with self.assertRaises(qualification.WindowExpired):
                asyncio.run(qualification.run(output))
        self.assertEqual(cleaned, [True])
        report = json.loads((output / "launch.json").read_text())
        self.assertEqual(report["status"], "interrupted")
        self.assertTrue(report["integrity_after"]["unchanged"])

    def test_shared_helper_drift_invalidates_finished_match(self):
        async def runner(*_):
            (self.root / "tools/qualification.py").write_text("changed during match")
            return {"experiment_complete": True}
        output = self.root / "drift"
        with patch.object(qualification, "check", return_value=self.report()), \
             patch.object(match, "run_match", side_effect=runner):
            with self.assertRaisesRegex(ValueError, "settings changed"):
                asyncio.run(qualification.run(output))
        self.assertEqual(json.loads((output / "launch.json").read_text())["status"], "invalidated")

    def test_cli_defaults_to_check_and_has_no_match_parameter_overrides(self):
        with patch.object(qualification, "check", return_value={"status": "checked"}) as checker, \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(qualification.main([]), 0)
            checker.assert_awaited_once()
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                qualification.main(["run", "--output", str(self.root / "other"), "--pairs", "1"])


if __name__ == "__main__":
    unittest.main()
