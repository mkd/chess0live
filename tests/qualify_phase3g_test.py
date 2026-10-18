#!/usr/bin/env python3
"""Phase 3G orchestration checks: synthetic roots, mocked games, and fake UCI only.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import match
import qualification as shared
import qualify_phase3g as campaign
from match_test import FAKE_ENGINE

DECLARED_ROOT = campaign.ROOT
DECLARED_PINS = campaign.FROZEN.copy()
DECLARED_SOURCES = campaign.SOURCES
FAKE = FAKE_ENGINE.replace(
    '        output("option name Research Toggle type check default true")',
    '        output("option name Late Move Reductions type check default false")\n'
    '        output("option name Capture Ordering type combo default mvv-lva var mvv-lva var see")')


class Phase3gTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="chess0live-phase3g-test-")
        self.root = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.patch(campaign, "ROOT", self.root)
        self.binary, self.network = self.root / "engine", self.root / "network.nnue"
        self.binary.write_bytes(b"synthetic frozen engine")
        self.network.write_bytes(b"synthetic network")
        self.fake = self.root / "fake.py"
        self.fake.write_text(FAKE)
        for source in DECLARED_SOURCES:
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic source " + source)
        prior = {"openings": [{"id": "prior", "moves": ["e2e4", "e7e5", "g1f3", "b8c6"]}]}
        for source in (*campaign.PREVIOUS_SUITES, campaign.GAME_PHASE_SUITE):
            (self.root / source).write_text(json.dumps(prior))
        roots = []
        for first in list(match.chess.Board().legal_moves)[:16]:
            board = match.chess.Board()
            board.push(first)
            for second in list(board.legal_moves)[:16]:
                roots.append({"id": f"fixture-{len(roots)}", "moves": [first.uci(), second.uci()]})
        pins = {name: (path, match.sha256(path)) for name, path in
                (("engine", self.binary), ("network", self.network))}
        self.entries = {}
        for index in range(1, 5):
            path = self.root / f"suite-{index}.json"
            entries = roots[(index - 1) * 64:index * 64]
            path.write_text(json.dumps({"openings": entries}))
            self.entries[index] = entries
            pins[f"openings_{index}"] = (path, match.sha256(path))
        self.patch(campaign, "FROZEN", pins)
        self.now = datetime(2026, 10, 18, 20, 2, tzinfo=timezone.utc)
        self.clock = self.patch(campaign, "utc_now", return_value=self.now)
        self.budget = {"timezone": "Europe/Helsinki", "local_time": self.now.isoformat(),
                       "source": "nighttime", "percent": 80, "logical_cpus": 18,
                       "max_cpu_workers": 14, "memory_fraction": .8}
        self.patch(match, "current_budget", side_effect=lambda: self.budget.copy())
        self.patch(match, "physical_memory", return_value=64 * 1024**3)

    def patch(self, target, name, *args, **kwargs):
        patcher = patch.object(target, name, *args, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def checked(self):
        before = campaign.snapshot()
        config = campaign.configuration()
        return {"checked_utc": self.now.isoformat(), "artifacts_before": before,
                "frozen": before["assets"], "sources": before["sources"],
                "configuration": config, "configuration_sha256": shared.configuration_hash(config),
                "preflight": {**campaign.opening_check(), "engines": [],
                              "resource_policy": campaign.resource_policy()[0]}}

    def repin(self, index, entries):
        path = campaign.FROZEN[f"openings_{index}"][0]
        path.write_text(json.dumps({"openings": entries}))
        campaign.FROZEN[f"openings_{index}"] = (path, match.sha256(path))

    def fake_request(self, mode="normal", settings=None):
        specs, standard = campaign.fixed_request()
        specs = [replace(spec, executable=Path(sys.executable).resolve(),
                         arguments=(str(self.fake), mode)) for spec in specs]
        return specs, settings or standard

    def events(self, output):
        return [json.loads(line) for line in (output / "resource-history.jsonl").read_text().splitlines()]

    def test_pinned_shape_and_only_lmr_differs(self):
        self.assertEqual(DECLARED_PINS["engine"][1], "edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b")
        self.assertEqual(campaign.SEEDS, (202610181, 202610182, 202610183, 202610184))
        config = campaign.configuration()
        self.assertEqual((config["pairs"], config["games"], config["shards"], config["shard_pairs"]), (256, 512, 4, 64))
        self.assertEqual((config["active_search_workers"], config["resident_engines"]), (4, 8))
        self.assertEqual((config["resource_poll_seconds"], config["max_resource_gap_seconds"]), (1., 5.))
        options = [dict(role) for role in campaign.ROLE_OPTIONS]
        self.assertEqual(options[0].pop("Late Move Reductions"), "true")
        self.assertEqual(options[1].pop("Late Move Reductions"), "false")
        self.assertEqual(options[0], options[1])
        self.assertEqual(options[0], {"Time Policy": "classic", "Capture Ordering": "mvv-lva"})
        for index in (0, 5, True, 1.0):
            with self.assertRaises(ValueError):
                campaign.profile(index)

    def test_real_suites_are_pinned_and_referee_only(self):
        with patch.object(campaign, "ROOT", DECLARED_ROOT), patch.object(campaign, "FROZEN", DECLARED_PINS):
            details = campaign.opening_check()
        self.assertEqual(details, {"opening_count": 256, "distinct_roots": 256,
                                  "previous_root_count": 120, "game_phase_root_count": 12})
        for name, (path, digest) in DECLARED_PINS.items():
            if name.startswith("openings_"):
                self.assertEqual(match.sha256(path), digest)
        self.assertIn("tests/data/openings-phase3g-generation.json", DECLARED_SOURCES)

    def test_short_duplicate_cross_shard_terminal_and_missing_history_reject_before_start(self):
        cases = [self.entries[1][:-1], self.entries[1][:-1] + [self.entries[2][0]],
                 self.entries[1][:-1] + [{"id": "dead", "fen": "7k/8/5K2/8/8/8/8/8 w - - 0 1"}],
                 self.entries[1][:-1] + [{"id": "no-history", "moves": []}]]
        for entries in cases:
            self.repin(1, entries)
            with patch.object(match, "start_engine", new_callable=AsyncMock) as start:
                with self.assertRaises(ValueError):
                    asyncio.run(campaign.check())
                start.assert_not_called()

    def test_previous_root_overlap_rejected(self):
        entries = self.entries[1][:-1] + [{"id": "exposed", "moves": ["e2e4", "e7e5", "g1f3", "b8c6"]}]
        self.repin(1, entries)
        with self.assertRaisesRegex(ValueError, "overlap"):
            campaign.opening_check()

    def test_serial_preflight_two_handshakes_no_search(self):
        request = self.fake_request()
        with patch.object(campaign, "fixed_request", return_value=request):
            report = asyncio.run(campaign.check())
        self.assertEqual(len(report["preflight"]["engines"]), 2)
        for engine in report["preflight"]["engines"]:
            commands = [entry["line"] for entry in engine["transcript"] if entry["direction"] == "to_engine"]
            self.assertFalse(any(line.startswith(("position", "go")) for line in commands))
            self.assertIs(engine["configured"]["Late Move Reductions"], engine["role"] == "candidate")
            self.assertEqual(engine["configured"]["Capture Ordering"], "mvv-lva")

    def test_wrong_capture_default_rejected(self):
        self.fake.write_text(FAKE.replace("combo default mvv-lva var", "combo default see var"))
        request = self.fake_request()
        with patch.object(campaign, "fixed_request", return_value=request):
            with self.assertRaisesRegex(ValueError, "Capture Ordering"):
                asyncio.run(campaign.check())

    def test_aggregate_budget_blocks_before_engine_even_when_one_worker_fits(self):
        self.budget["max_cpu_workers"] = 3
        specs, settings = campaign.fixed_request()
        match.resource_check(settings, specs)
        with patch.object(match, "start_engine", new_callable=AsyncMock) as start:
            with self.assertRaisesRegex(ValueError, "Aggregate"):
                asyncio.run(campaign.check())
            start.assert_not_called()

    def test_aggregate_memory_estimate_and_unknown_memory(self):
        specs, settings = campaign.fixed_request()
        one = match.resource_check(settings, specs)
        policy, allowed = campaign.resource_policy()
        self.assertTrue(allowed)
        self.assertEqual(policy["estimated_memory_bytes"], 4 * one["estimated_memory_bytes"])
        for memory in (None, 1):
            with patch.object(match, "physical_memory", return_value=memory):
                self.assertFalse(campaign.resource_policy()[1])

    def test_launch_window_and_dst(self):
        for hour, minute, permitted in ((19, 59, False), (20, 0, True), (20, 14, True), (20, 15, False), (21, 0, False)):
            instant = self.now.replace(hour=hour, minute=minute)
            self.assertEqual(campaign.launch_policy(instant)["launch_permitted"], permitted)
        spring = datetime(2026, 3, 28, 21, tzinfo=timezone.utc)
        fall = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)
        self.assertEqual(campaign.launch_policy(spring)["remaining_seconds"], 7 * 3600)
        self.assertEqual(campaign.launch_policy(fall)["remaining_seconds"], 9 * 3600)

    def test_daytime_and_existing_directory_rejected_before_preflight(self):
        with patch.object(campaign, "check", new_callable=AsyncMock) as check:
            with self.assertRaisesRegex(ValueError, "new directory"):
                asyncio.run(campaign.run(self.root))
            self.clock.return_value = self.now.replace(hour=10)
            with self.assertRaisesRegex(ValueError, "23:00"):
                asyncio.run(campaign.run(self.root / "day"))
            check.assert_not_called()

    def test_dated_daytime_exception_boundaries_and_naive_clock(self):
        # October 18 Helsinki is UTC+3. Only this date's daytime is authorized.
        for day, hour, minute, permitted in ((17, 5, 0, False), (18, 3, 59, False),
                (18, 4, 0, True), (18, 19, 59, True), (18, 20, 0, False), (19, 5, 0, False)):
            instant = self.now.replace(day=day, hour=hour, minute=minute)
            with self.subTest(instant=instant):
                policy = campaign.launch_policy(instant, allow_daytime=True)
                self.assertIs(policy["launch_permitted"], permitted)
                self.assertIs(policy["allow_daytime"], True)
                self.assertEqual(policy["daytime_authorization"], "owner-20261018-phase3g")
                if permitted:
                    self.assertIs(policy["nighttime"], False)
                    self.assertEqual(datetime.fromisoformat(policy["cutoff_utc"]),
                                     datetime(2026, 10, 19, 4, tzinfo=timezone.utc))
                    self.assertFalse(campaign.launch_policy(instant)["launch_permitted"])
                else:
                    with self.assertRaises(ValueError):
                        campaign.launch_policy(instant, allow_daytime=True, require_window=True)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            campaign.launch_policy(datetime(2026, 10, 18, 10), allow_daytime=True)
        self.assertIsNone(campaign.launch_policy(self.now)["daytime_authorization"])

    def test_daytime_wrong_date_rejects_before_output_or_preflight(self):
        self.clock.return_value = self.now.replace(day=19, hour=6)
        output = self.root / "wrong-date"
        with patch.object(campaign, "check", new_callable=AsyncMock) as check:
            with self.assertRaisesRegex(ValueError, "2026-10-18"):
                asyncio.run(campaign.run(output, allow_daytime=True))
            check.assert_not_called()
        self.assertFalse(output.exists())

    def test_daytime_run_inherits_authorization_without_increasing_budget(self):
        self.now = self.now.replace(hour=6)
        self.clock.return_value = self.now
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        async def runner(*_, **hooks):
            await hooks["before_game"]("p000001-1")
            return {"experiment_complete": True}
        output = self.root / "authorized-day"
        with patch.object(campaign, "check", return_value=self.checked()), \
             patch.object(match, "run_match", side_effect=runner):
            record = asyncio.run(campaign.run(output, allow_daytime=True))
        self.assertEqual(record["status"], "finished")
        self.assertIs(record["launch_policy"]["allow_daytime"], True)
        self.assertEqual(record["launch_policy"]["daytime_authorization"], "owner-20261018-phase3g")
        for index in range(1, 5):
            child = json.loads((output / f"shard-{index}/launch.json").read_text())
            for key in ("allow_daytime", "daytime_authorization", "cutoff_utc", "cutoff_local"):
                self.assertEqual(child["launch_policy"][key], record["launch_policy"][key])
        self.assertEqual({e["policy"]["percent"] for e in self.events(output)}, {50})
        self.assertEqual({e["policy"]["active_search_workers"] for e in self.events(output)}, {4})

    def test_daytime_preflight_does_not_requalify_children_or_move_cutoff(self):
        self.now = self.now.replace(hour=19, minute=59)  # Authorized 22:59 Helsinki.
        self.clock.return_value = self.now
        checked = self.checked()
        async def delayed():
            self.clock.return_value = self.now + timedelta(minutes=31)
            return checked
        async def runner(*_, **__):
            return {"experiment_complete": True}
        with patch.object(campaign, "check", side_effect=delayed), \
             patch.object(match, "run_match", side_effect=runner):
            record = asyncio.run(campaign.run(self.root / "late-day", allow_daytime=True))
        self.assertEqual(record["cutoff_utc"], campaign.launch_policy(self.now)["cutoff_utc"])
        for index in range(1, 5):
            policy = json.loads((self.root / f"late-day/shard-{index}/launch.json").read_text())["launch_policy"]
            self.assertIs(policy["allow_daytime"], True)
            self.assertIs(policy["nighttime"], True)
            self.assertEqual(policy["cutoff_utc"], record["cutoff_utc"])

    def test_daytime_preflight_expiry_keeps_original_next_morning_cutoff(self):
        self.now = self.now.replace(hour=6)  # 09:02 Helsinki on the authorized date.
        self.clock.return_value = self.now
        checked = self.checked()
        cutoff = datetime.fromisoformat(campaign.launch_policy(self.now)["cutoff_utc"])
        async def delayed():
            self.clock.return_value = cutoff
            return checked
        output = self.root / "day-expired"
        with patch.object(campaign, "check", side_effect=delayed), \
             patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaises(shared.WindowExpired):
                asyncio.run(campaign.run(output, allow_daytime=True))
            runner.assert_not_called()
        record = json.loads((output / "campaign.json").read_text())
        self.assertEqual(datetime.fromisoformat(record["cutoff_utc"]), cutoff)
        self.assertEqual(record["status"], "interrupted")

    def test_four_coroutines_exact_settings_frozen_before_games(self):
        running, seen = set(), []
        async def runner(specs, settings, suite, output, pairs, seed, **hooks):
            running.add(seed)
            while len(running) < 4:
                await asyncio.sleep(.001)
            self.assertEqual((pairs, settings.initial, settings.increment), (64, 60, .6))
            self.assertTrue(hooks["fail_fast"])
            self.assertEqual(json.loads((output.parent.parent / "campaign.json").read_text())["status"], "running")
            await hooks["before_game"]("p000001-1")
            seen.append(seed)
            return {"experiment_complete": True}
        output = self.root / "complete"
        with patch.object(campaign, "check", return_value=self.checked()), patch.object(match, "run_match", side_effect=runner):
            record = asyncio.run(campaign.run(output))
        self.assertEqual(sorted(seen), list(campaign.SEEDS))
        self.assertEqual(record["status"], "finished")
        self.assertTrue(record["artifacts_after"]["unchanged"])
        self.assertEqual(record["resource_history"]["sha256"], match.sha256(output / "resource-history.jsonl"))
        events = self.events(output)
        self.assertEqual(record["resource_history"]["observations"], len(events))
        self.assertEqual((events[0]["trigger"], events[-1]["trigger"]), ("initial", "final"))
        self.assertEqual({entry["shard_index"] for entry in events if entry["trigger"] == "before_game"}, {1, 2, 3, 4})
        self.assertEqual({entry["policy"]["resident_engines"] for entry in events}, {8})

    def test_preflight_keeps_original_cutoff_and_late_entry_is_not_relaunched(self):
        checked = self.checked()
        async def delayed():
            self.clock.return_value = self.now + timedelta(hours=8)
            return checked
        output = self.root / "late"
        with patch.object(campaign, "check", side_effect=delayed), patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaises(shared.WindowExpired):
                asyncio.run(campaign.run(output))
            runner.assert_not_called()
        record = json.loads((output / "campaign.json").read_text())
        self.assertEqual(record["cutoff_utc"], campaign.launch_policy(self.now)["cutoff_utc"])
        self.assertEqual(record["started_utc"], self.now.isoformat())

    def test_worker_failure_cancels_and_awaits_all_other_cleanups(self):
        started, cleaned = set(), []
        async def runner(*args, **_):
            seed = args[5]
            started.add(seed)
            try:
                while len(started) < 4:
                    await asyncio.sleep(.001)
                if seed == campaign.SEEDS[0]:
                    raise ValueError("synthetic invalid game")
                await asyncio.Future()
            finally:
                await asyncio.sleep(.01)
                cleaned.append(seed)
        output = self.root / "failed"
        with patch.object(campaign, "check", return_value=self.checked()), patch.object(match, "run_match", side_effect=runner):
            with self.assertRaisesRegex(ValueError, "synthetic invalid"):
                asyncio.run(campaign.run(output))
        self.assertEqual(sorted(cleaned), list(campaign.SEEDS))
        self.assertEqual(json.loads((output / "campaign.json").read_text())["status"], "failed")

    def test_budget_drop_and_metadata_drift_cancel_all(self):
        for change in ("budget", "source"):
            started, cleaned = set(), []
            async def runner(*args, **hooks):
                seed = args[5]
                started.add(seed)
                try:
                    while len(started) < 4:
                        await asyncio.sleep(.001)
                    if seed == campaign.SEEDS[0]:
                        if change == "budget":
                            self.budget["max_cpu_workers"] = 3
                        else:
                            (self.root / campaign.PROTOCOL_DOCUMENT).write_text("drift")
                        await hooks["before_game"]("p000001-1")
                    await asyncio.Future()
                finally:
                    cleaned.append(seed)
            output = self.root / change
            checked = self.checked()
            with patch.object(campaign, "check", return_value=checked), patch.object(match, "run_match", side_effect=runner):
                with self.assertRaises(ValueError):
                    asyncio.run(campaign.run(output))
            self.assertEqual(sorted(cleaned), list(campaign.SEEDS))
            self.budget["max_cpu_workers"] = 14

    def test_first_cancellation_during_failure_cleanup_preserves_master_record(self):
        output = self.root / "late-supervisor-cancel"
        async def exercise():
            cleanup_entered, release = asyncio.Event(), asyncio.Event()
            started, cleaned = set(), []
            async def runner(*args, **_):
                seed = args[5]
                started.add(seed)
                try:
                    while len(started) < 4:
                        await asyncio.sleep(.001)
                    if seed == campaign.SEEDS[0]:
                        raise ValueError("synthetic failure")
                    await asyncio.Future()
                finally:
                    if seed != campaign.SEEDS[0]:
                        cleanup_entered.set()
                        await release.wait()
                    cleaned.append(seed)
            with patch.object(campaign, "check", return_value=self.checked()), \
                 patch.object(match, "run_match", side_effect=runner):
                task = asyncio.create_task(campaign.run(output))
                await asyncio.wait_for(cleanup_entered.wait(), 2)
                task.cancel()
                await asyncio.sleep(.01)
                self.assertFalse(task.done())
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 2)
            self.assertEqual(sorted(cleaned), list(campaign.SEEDS))
        asyncio.run(exercise())
        record = json.loads((output / "campaign.json").read_text())
        self.assertEqual(record["status"], "interrupted")
        self.assertEqual(len(record["shard_statuses"]), 4)
        self.assertTrue(record["artifacts_after"]["unchanged"])
        self.assertEqual(record["resource_history"]["sha256"], match.sha256(output / "resource-history.jsonl"))

    def test_cutoff_cancels_all_once(self):
        cleaned = []
        async def runner(*_, **__):
            try:
                await asyncio.Future()
            finally:
                await asyncio.sleep(.02)
                cleaned.append(True)
        policy = campaign.launch_policy(self.now)
        policy["cutoff_utc"] = (self.now + timedelta(seconds=.1)).isoformat()
        with patch.object(campaign, "launch_policy", return_value=policy), \
             patch.object(campaign, "check", return_value=self.checked()), patch.object(match, "run_match", side_effect=runner):
            with self.assertRaises(shared.WindowExpired):
                asyncio.run(campaign.run(self.root / "cutoff"))
        self.assertEqual(len(cleaned), 4)

    def test_monitor_gap_is_bounded(self):
        async def runner(*_, **__):
            await asyncio.Future()
        with patch.object(campaign, "MAX_RESOURCE_GAP_SECONDS", .002), \
             patch.object(campaign, "POLL_SECONDS", .02), patch.object(campaign, "check", return_value=self.checked()), \
             patch.object(match, "run_match", side_effect=runner):
            with self.assertRaisesRegex(ValueError, "observation gap"):
                asyncio.run(campaign.run(self.root / "gap"))

    def test_cli_explicit_daytime_flag_but_no_resume_or_parameter_overrides(self):
        with patch.object(campaign, "check", return_value={"status": "checked"}) as checked, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(campaign.main([]), 0)
            checked.assert_awaited_once()
        with patch.object(campaign, "run", return_value={"status": "finished"}) as run, \
             patch("sys.stdout", new_callable=io.StringIO):
            output = self.root / "out"
            self.assertEqual(campaign.main(["run", "--output", str(output), "--allow-daytime"]), 0)
            run.assert_awaited_once_with(output, True)
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            campaign.main(["check", "--allow-daytime"])
        for argument in ("--resume", "--pairs", "--seed", "--threads"):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                campaign.main(["run", "--output", str(self.root / "out"), argument])

    def test_coordinated_git_metadata_does_not_block_other_clocks(self):
        specs, settings = campaign.fixed_request()
        ticks = []
        def slow_git(*_, **__):
            time.sleep(.03)
            return type("Result", (), {"returncode": 0, "stdout": "synthetic"})()
        async def tick():
            for _ in range(8):
                await asyncio.sleep(.008)
                ticks.append(True)
        async def stop(_):
            raise ValueError("stop before fake game")
        async def exercise():
            heartbeat = asyncio.create_task(tick())
            with self.assertRaisesRegex(ValueError, "stop before"):
                await match.run_match(specs, settings, campaign.FROZEN["openings_1"][0], self.root / "git", 1, 1, before_game=stop)
            self.assertGreaterEqual(len(ticks), 4)
            await heartbeat
        with patch.object(match.subprocess, "run", side_effect=slow_git), patch.object(match.platform, "platform", return_value="synthetic"):
            asyncio.run(exercise())

    def test_close_engine_preserves_cancellation_during_quit_and_returncode(self):
        async def exercise(stage):
            entered, release = asyncio.Event(), asyncio.Event()
            code = asyncio.get_running_loop().create_future()
            closed = []
            class Protocol:
                returncode = code
                async def quit(self):
                    if stage == "quit":
                        entered.set()
                        await release.wait()
            class Transport:
                def close(self):
                    closed.append(True)
                    if stage == "returncode":
                        entered.set()
                    elif not code.done():
                        code.set_result(0)
            task = asyncio.create_task(match.close_engine(Transport(), Protocol()))
            await entered.wait()
            task.cancel()
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            release.set()
            if stage == "returncode":
                code.set_result(0)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(closed)
        for stage in ("quit", "returncode"):
            asyncio.run(exercise(stage))

    def test_late_game_cleanup_cancel_closes_both_engines_and_never_admits_next_game(self):
        async def exercise():
            entered, release = asyncio.Event(), asyncio.Event()
            closed, admissions = [], []
            class Protocol:
                id = {"name": "synthetic"}
                def __init__(self, role):
                    self.role = role
                    self.returncode = asyncio.get_running_loop().create_future()
                async def quit(self):
                    if self.role == "candidate":
                        entered.set()
                        await release.wait()
            class Transport:
                def __init__(self, protocol):
                    self.protocol = protocol
                def get_pid(self):
                    return 1
                def close(self):
                    closed.append(self.protocol.role)
                    if not self.protocol.returncode.done():
                        self.protocol.returncode.set_result(0)
            async def start(spec, *_):
                protocol = Protocol(spec.role)
                return Transport(protocol), protocol, {}
            async def guard(game_id):
                admissions.append(game_id)
            # A synthetic completed game enters normal cleanup without sending
            # any fake engine a chess search. Cancellation arrives at quit.
            specs, settings = campaign.fixed_request()
            output = self.root / "late-cleanup"
            outcome = match.chess.Outcome(match.chess.Termination.THREEFOLD_REPETITION, None)
            opening_data = match.read_openings(campaign.FROZEN["openings_1"][0])
            with patch.object(match, "start_engine", side_effect=start), \
                 patch.object(match, "read_openings", return_value=opening_data), \
                 patch.object(match.chess.Board, "outcome", return_value=outcome):
                task = asyncio.create_task(match.run_match(specs, settings,
                    campaign.FROZEN["openings_1"][0], output, 1, 1, before_game=guard))
                await asyncio.wait_for(entered.wait(), 2)
                task.cancel()
                await asyncio.sleep(0)
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertEqual(set(closed), {"candidate", "opponent"})
            self.assertEqual(admissions, ["p000001-1"])
            self.assertEqual(len((output / "games.jsonl").read_text().splitlines()), 1)
        asyncio.run(exercise())

    def test_fail_fast_preserves_invalid_record_and_keeps_clock_forfeit_scored(self):
        specs, settings = campaign.fixed_request()
        for status in ("protocol_failure", "setup_failure", "truncated", "complete"):
            output = self.root / status
            calls = []
            async def game(*args):
                calls.append(args[4])
                record = {"game_id": args[4], "pair_id": args[3], "candidate_color": args[5],
                          "status": status, "result": "0-1" if status == "complete" else "*",
                          "candidate_score": 0 if status == "complete" else None,
                          "termination": "time forfeit" if status == "complete" else status}
                args[-1](record)
                return record
            with patch.object(match, "play_game", side_effect=game):
                if status == "complete":
                    result = asyncio.run(match.run_match(specs, settings, campaign.FROZEN["openings_1"][0], output, 1, 1, fail_fast=True))
                    self.assertTrue(result["experiment_complete"])
                    self.assertEqual(len(calls), 2)
                else:
                    with self.assertRaisesRegex(ValueError, "Invalid game"):
                        asyncio.run(match.run_match(specs, settings, campaign.FROZEN["openings_1"][0], output, 1, 1, fail_fast=True))
                    self.assertEqual(len(calls), 1)
                self.assertEqual(len((output / "games.jsonl").read_text().splitlines()), len(calls))

    def test_stderr_from_completed_fake_game_aborts_before_next_game(self):
        self.fake.write_text(FAKE.replace('elif command == "quit": break',
            'elif command == "quit":\n        print("unexpected diagnostic", file=sys.stderr, flush=True)\n        break'))
        specs, settings = self.fake_request("mate")
        suite = self.root / "mate.json"
        suite.write_text(json.dumps({"openings": [{"id": "mate", "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"}]}))
        output = self.root / "stderr"
        admissions = []
        async def guard(game_id):
            admissions.append(game_id)
        with self.assertRaisesRegex(ValueError, "unexpected engine stderr"):
            asyncio.run(match.run_match(specs, settings, suite, output, 1, 1, before_game=guard, fail_fast=True))
        self.assertEqual(admissions, ["p000001-1"])
        records = [json.loads(line) for line in (output / "games.jsonl").read_text().splitlines()]
        self.assertEqual(records[0]["status"], "complete")
        self.assertTrue(records[0]["unexpected_stderr"])

    @unittest.skipIf(sys.platform == "win32", "POSIX signal delivery test")
    def test_real_fake_uci_signals_wait_for_eight_hanging_processes_and_preserve_partial_games(self):
        pidfile = self.root / "pids.txt"
        self.fake.write_text(FAKE.replace("board = chess.Board()", "board = chess.Board()\n"
            f"with open({str(pidfile)!r}, 'a') as f: f.write(str(os.getpid()) + '\\n')", 1))
        request = self.fake_request("hang")
        output = self.root / "signals"
        pids = []
        async def exercise():
            task = asyncio.create_task(campaign.cooperative_signals(campaign.run(output)))
            limit = asyncio.get_running_loop().time() + 15
            while len(pids) < 8:
                if task.done():
                    await task
                if pidfile.exists():
                    pids[:] = [int(line) for line in pidfile.read_text().splitlines()]
                self.assertLess(asyncio.get_running_loop().time(), limit, "fake engines failed to start")
                await asyncio.sleep(.01)
            os.kill(os.getpid(), signal.SIGINT)
            await asyncio.sleep(.03)
            os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.sleep(.03)
            os.kill(os.getpid(), signal.SIGINT)
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 8)
        with patch.object(campaign, "fixed_request", return_value=request), \
             patch.object(campaign, "check", return_value=self.checked()):
            asyncio.run(exercise())
        self.assertEqual(len(pids), 8)
        for pid in pids:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        record = json.loads((output / "campaign.json").read_text())
        self.assertEqual(record["status"], "interrupted")
        for index in range(1, 5):
            directory = output / f"shard-{index}" / "match"
            self.assertTrue(list(directory.glob("*.pgn")))
            records = [json.loads(line) for line in (directory / "games.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "interrupted")


if __name__ == "__main__":
    unittest.main()
