#!/usr/bin/env python3
"""Synthetic four-shard lifecycle and frozen qualification boundary checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import match
import qualification as shared
import qualify_phase4f3 as campaign
from match_test import FAKE_ENGINE

FAKE = FAKE_ENGINE.replace(
    '        output("option name Research Toggle type check default true")',
    '        output("option name Late Move Reductions type check default true")\n'
    '        output("option name Deep Quiet Reductions type check default false")\n'
    '        output("option name ProbCut type check default false")\n'
    '        output("option name Countermove Ordering type check default false")\n'
    '        output("option name Null Move Pruning type check default false")\n'
    '        output("option name Reverse Futility Pruning type check default false")\n'
    '        output("option name QSearch SEE Pruning type check default false")\n'
    '        output("option name Capture Ordering type combo default mvv-lva var mvv-lva var see")\n'
    '        output("option name SyzygyPath type string default <empty>")\n'
    '        output("option name SyzygyProbeLimit type spin default 7 min 0 max 7")')

FAKE = FAKE.replace("Time Policy type combo default classic var classic var forecast",
                    "Time Policy type combo default classic var classic var forecast var bounded")

def synthetic_openings():
    rng, roots, entries = random.Random(4402026), set(), []
    while len(entries) < 256:
        board, moves = match.chess.Board(), []
        for _ in range(6):
            move = rng.choice(list(board.legal_moves)); moves.append(move.uci()); board.push(move)
        key = " ".join(board.fen().split()[:4])
        if key not in roots and not board.outcome(claim_draw=True):
            roots.add(key); entries.append({"id": f"synthetic-{len(entries)}", "moves": moves})
    return entries


class PreparationPinsTests(unittest.TestCase):
    def test_schema_membership_and_hashes_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="phase4f3-pins-") as directory:
            root = Path(directory)
            path = root/campaign.PIN_FILE; path.parent.mkdir(parents=True)
            valid = {"schema_version": 1, "protocol_id": campaign.PROTOCOL_ID,
                     "input_sha256": {name: "a"*64 for name in campaign.PINNED_INPUTS}}
            with patch.object(campaign, "ROOT", root):
                path.write_text(json.dumps(valid))
                self.assertEqual(campaign.input_pins(), valid["input_sha256"])
                for broken in ([], {**valid, "protocol_id": "historical-permission"},
                               {**valid, "schema_version": 2},
                               {**valid, "input_sha256": {}},
                               {**valid, "input_sha256": {**valid["input_sha256"], "extra": "a"*64}},
                               {**valid, "input_sha256": {name: "invalid" for name in campaign.PINNED_INPUTS}}):
                    with self.subTest(broken=broken):
                        path.write_text(json.dumps(broken))
                        with self.assertRaises(ValueError): campaign.input_pins()


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openings = synthetic_openings()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase4f3-test-")
        self.addCleanup(temporary.cleanup); self.root = Path(temporary.name).resolve()
        self.patch(campaign, "ROOT", self.root)
        for name in campaign.SOURCES:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("synthetic source")
        (self.root/campaign.EXCLUSIONS).write_text(json.dumps({"roots": [{
            "root_key": " ".join(match.chess.Board().fen().split()[:4]), "sources": ["synthetic"]}]}))
        pins = {}
        for name in ("engine", "network"):
            path = self.root/name; path.write_bytes(b"synthetic"); pins[name] = (path, match.sha256(path))
        for i in range(1, 5):
            path = self.root/f"tests/data/phase4f3-{i:02d}.json"
            path.write_text(json.dumps({"openings": self.openings[(i-1)*64:i*64]}))
            pins[f"openings_{i}"] = (path, match.sha256(path))
        self.patch(campaign, "frozen", return_value=pins)
        self.patch(campaign, "input_pins", return_value={name: match.sha256(self.root/name) for name in campaign.PINNED_INPUTS})
        self.fake = self.root/"fake.py"; self.fake.write_text(FAKE)
        self.now = datetime(2026, 10, 22, 20, 2, tzinfo=timezone.utc)
        self.clock = self.patch(campaign, "utc_now", return_value=self.now)
        self.budget = {"timezone": "Europe/Helsinki", "local_time": self.now.isoformat(), "source": "nighttime",
                       "percent": 80, "logical_cpus": 18, "max_cpu_workers": 14, "memory_fraction": .8}
        self.patch(match, "current_budget", side_effect=lambda: self.budget.copy())
        self.patch(match, "physical_memory", return_value=64*1024**3)

    def patch(self, target, name, *args, **kwargs):
        p = patch.object(target, name, *args, **kwargs); result = p.start(); self.addCleanup(p.stop); return result

    def checked(self):
        before = campaign.snapshot()
        return {"checked_utc": self.now.isoformat(), "artifacts_before": before, "frozen": before["assets"],
                "sources": before["sources"], "preflight": {**campaign.opening_check(), "engines": [],
                "resource_policy": campaign.resource_policy()[0]}}

    def fake_request(self):
        specs, settings = campaign.fixed_request()
        return [replace(s, executable=Path(sys.executable).resolve(), arguments=(str(self.fake), "normal")) for s in specs], settings

    def test_fixed_shape_and_complete_packages(self):
        config = campaign.configuration()
        self.assertEqual((config["games"], config["pairs"], config["shards"], config["resident_engines"]), (512,256,4,8))
        self.assertEqual(campaign.SEEDS, tuple(range(202610244301,202610244305)))
        candidate, opponent = map(dict, campaign.ROLE_OPTIONS)
        for role in (candidate, opponent):
            self.assertEqual(role["Late Move Reductions"], "true")
            self.assertEqual(role["Time Policy"], "classic")
            self.assertEqual(role["SyzygyProbeLimit"], "0")
            self.assertNotIn("SyzygyPath", role)  # Cleared explicitly by the shared runner.
        for name in campaign.CHECK_OPTIONS[1:]:
            self.assertEqual(candidate[name], "true")
            self.assertEqual(opponent[name], "false")
        self.assertEqual(candidate["Capture Ordering"], "see")
        self.assertEqual(opponent["Capture Ordering"], "mvv-lva")
        self.assertEqual(campaign.PROTOCOL_ID, "phase4f3-combined-512-v1")
        specs, settings = campaign.fixed_request()
        self.assertEqual((settings.initial, settings.increment, settings.threads,
                          settings.hash_mb, settings.move_overhead_ms), (60.0, .6, 1, 64, 20))
        self.assertFalse(settings.smoke)
        self.assertEqual(specs[0].executable, specs[1].executable)
        self.assertEqual(specs[0].network, specs[1].network)
        self.assertFalse(config["ponder"])
        self.assertFalse(config["diagnostics"])
        for index in (0,5,True,1.0):
            with self.assertRaises(ValueError): campaign.profile(index)

    def test_search_free_serial_handshakes_apply_all_modes(self):
        original_start, original_close = match.start_engine, match.close_engine
        active, closed = set(), []

        async def start(*args, **kwargs):
            self.assertFalse(active, "Preflight must not overlap engine processes")
            result = await original_start(*args, **kwargs)
            active.add(id(result[1]))
            return result

        async def close(transport, protocol):
            await original_close(transport, protocol)
            active.remove(id(protocol))
            closed.append(True)

        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                patch.object(match, "start_engine", side_effect=start), \
                patch.object(match, "close_engine", side_effect=close):
            report = asyncio.run(campaign.check())
        self.assertEqual(len(closed), 2)
        self.assertFalse(active)
        self.assertFalse(report["launch_policy"]["allow_daytime"])
        self.assertIsNone(report["launch_policy"]["daytime_authorization"])
        for engine in report["preflight"]["engines"]:
            self.assertEqual(engine["configured"]["SyzygyProbeLimit"],0)
            self.assertEqual(engine["configured"]["SyzygyPath"],"")
            for option in ("Countermove Ordering", "Null Move Pruning",
                           "Reverse Futility Pruning", "QSearch SEE Pruning"):
                self.assertIs(engine["configured"][option], engine["role"] == "candidate")
            self.assertIs(engine["configured"]["Late Move Reductions"], True)
            for name in ("Deep Quiet Reductions", "ProbCut"):
                self.assertIs(engine["configured"][name], engine["role"] == "candidate")
            self.assertFalse(any(e["line"].startswith(("position ","go ")) for e in engine["transcript"]))

    def test_option_default_or_disabled_limit_drift_rejects(self):
        changed_defaults = tuple((f"{option} type check default false", f"{option} type check default true")
                                 for option in ("Deep Quiet Reductions", "Countermove Ordering", "Null Move Pruning",
                                                "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut"))
        for old,new in (*changed_defaults,
                        ("Late Move Reductions type check default true", "Late Move Reductions type check default false"),
                        ("var classic var forecast var bounded", "var classic var forecast"),
                        ("SyzygyProbeLimit type spin default 7 min 0","SyzygyProbeLimit type spin default 7 min 1"),
                        ("SyzygyPath type string default <empty>","SyzygyPath type string default /tables")):
            self.fake.write_text(FAKE.replace(old,new))
            with patch.object(campaign,"fixed_request",return_value=self.fake_request()), self.assertRaises((ValueError,match.chess.engine.EngineError)):
                asyncio.run(campaign.check())

    def test_frozen_engine_network_and_opening_pins_reject_drift(self):
        for name, (path, expected) in campaign.frozen().items():
            old = path.read_bytes()
            with self.subTest(asset=name):
                path.write_bytes(old + b"changed")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    campaign.snapshot()
                path.write_bytes(old)
                self.assertEqual(match.sha256(path), expected)

    def test_preparation_drift_rejects(self):
        for name in campaign.input_pins():
            path=self.root/name; old=path.read_bytes(); path.write_bytes(old+b"changed")
            with self.assertRaisesRegex(ValueError,"SHA-256"): campaign.snapshot()
            path.write_bytes(old)

    def test_duplicate_and_exposed_openings_reject_before_process_start(self):
        path=campaign.frozen()["openings_2"][0]
        for entries in (self.openings[:64],self.openings[64:127], [{"id":"missing-history","moves":[]}]*64):
            path.write_text(json.dumps({"openings":entries})); campaign.frozen()["openings_2"]=(path,match.sha256(path)); campaign.input_pins()["tests/data/phase4f3-02.json"]=match.sha256(path)
            with patch.object(match,"start_engine",new_callable=AsyncMock) as start, self.assertRaises((ValueError,match.chess.engine.EngineError)):
                asyncio.run(campaign.check())
            start.assert_not_called()

    def test_aggregate_budget_and_unknown_memory_fail_closed(self):
        self.budget["max_cpu_workers"]=3
        with patch.object(match,"start_engine",new_callable=AsyncMock) as start,self.assertRaisesRegex(ValueError,"Aggregate"):
            asyncio.run(campaign.check())
        start.assert_not_called()
        self.budget["max_cpu_workers"] = 4
        for memory in (None, 0, -1, 1):
            with patch.object(match,"physical_memory",return_value=memory): self.assertFalse(campaign.resource_policy()[1])

    def test_minimum_memory_reserves_all_eight_processes(self):
        policy, allowed = campaign.resource_policy()
        self.assertTrue(allowed)
        self.assertEqual(policy["active_search_workers"], 4)
        self.assertEqual(policy["resident_engines"], 8)
        self.assertEqual(policy["estimated_memory_bytes"], 6 * 1024**3)
        self.assertFalse(policy["memory_estimate_is_hard_cap"])
        self.budget["memory_fraction"] = .5
        with patch.object(match, "physical_memory", return_value=12 * 1024**3):
            self.assertTrue(campaign.resource_policy()[1])
        with patch.object(match, "physical_memory", return_value=12 * 1024**3 - 1):
            self.assertFalse(campaign.resource_policy()[1])

    def test_larger_network_expands_beyond_memory_floor(self):
        network = campaign.frozen()["network"][0]
        with network.open("wb") as stream:
            stream.truncate(256 * 1024**2)
        policy, allowed = campaign.resource_policy()
        self.assertTrue(allowed)
        self.assertEqual(policy["estimated_memory_bytes"], 8 * (64 + 4 * 256 + 128) * 1024**2)

    def test_daytime_rejected_even_through_python_api(self):
        with self.assertRaisesRegex(ValueError, "no authorized daytime"):
            campaign.launch_policy(self.now, allow_daytime=True)

    def test_ordinary_window_bounds_dst_and_timezone(self):
        for hour,minute,good in ((19,59,False),(20,0,True),(20,29,True),(20,30,False),(21,0,False)):
            self.assertEqual(campaign.launch_policy(self.now.replace(hour=hour,minute=minute))["launch_permitted"],good)
        for date,hours in ((datetime(2026,3,28,21,tzinfo=timezone.utc),7),(datetime(2026,10,24,20,tzinfo=timezone.utc),9)):
            self.assertEqual(campaign.launch_policy(date)["remaining_seconds"],hours*3600)
        from zoneinfo import ZoneInfo
        warsaw = self.now.astimezone(ZoneInfo("Europe/Warsaw"))
        self.assertEqual(campaign.launch_policy(self.now), campaign.launch_policy(warsaw))
        self.assertEqual(campaign.launch_policy(warsaw)["timezone"], "Europe/Helsinki")
        self.assertIsNone(campaign.launch_policy(warsaw)["daytime_authorization"])
        with self.assertRaises(ValueError): campaign.launch_policy(datetime(2026,10,22,23))




    def test_overwrite_and_late_launch_reject_before_preflight(self):
        with patch.object(campaign,"check",new_callable=AsyncMock) as check:
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root))
            self.clock.return_value=self.now.replace(hour=10)
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root/"day"))
            check.assert_not_called()

    def test_all_four_workers_and_reservations(self):
        started=set()
        async def runner(*args,**hooks):
            started.add(args[5])
            while len(started)<4: await asyncio.sleep(.001)
            self.assertTrue(hooks["fail_fast"]); await hooks["before_game"]("p000001-1")
            return {"experiment_complete":True}
        output=self.root/"done"
        with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            report=asyncio.run(campaign.run(output))
        self.assertEqual(started,set(campaign.SEEDS)); self.assertEqual(report["status"],"finished")
        self.assertTrue(report["artifacts_after"]["unchanged"])
        events=[json.loads(line) for line in (output/"resource-history.jsonl").read_text().splitlines()]
        self.assertEqual({e["policy"]["resident_engines"] for e in events},{8})
        self.assertEqual({e["shard_index"] for e in events if e["trigger"]=="before_game"},set(range(1,5)))

    def test_worker_failure_cancels_and_awaits_all_cleanup(self):
        started,cleaned=set(),set()
        async def runner(*args,**_):
            seed=args[5]; started.add(seed)
            try:
                while len(started)<4: await asyncio.sleep(.001)
                if seed==campaign.SEEDS[0]: raise ValueError("synthetic failure")
                await asyncio.Future()
            finally:
                await asyncio.sleep(.01); cleaned.add(seed)
        with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"synthetic failure"): asyncio.run(campaign.run(self.root/"fail"))
        self.assertEqual(cleaned,set(campaign.SEEDS))

    def test_budget_drop_cancels_all_workers(self):
        started,cleaned=set(),set()
        async def runner(*args,**hooks):
            seed=args[5]; started.add(seed)
            try:
                while len(started)<4: await asyncio.sleep(.001)
                self.budget["max_cpu_workers"]=3
                await hooks["before_game"]("p000001-1")
            finally: cleaned.add(seed)
        with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"Aggregate"): asyncio.run(campaign.run(self.root/"drop"))
        self.assertEqual(cleaned,set(campaign.SEEDS))

    def test_preflight_cannot_roll_cutoff_to_following_night(self):
        checked=self.checked()
        async def delayed(): self.clock.return_value=self.now+timedelta(hours=8); return checked
        with patch.object(campaign,"check",side_effect=delayed),patch.object(match,"run_match",new_callable=AsyncMock) as runner:
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"late"))
        runner.assert_not_called()

    def test_preflight_crossing_launch_window_rejects_without_starting_children(self):
        for allow_daytime in (False,):
            self.clock.return_value = self.now.replace(minute=29)
            cutoff = campaign.launch_policy(self.clock.return_value, allow_daytime=allow_daytime)["cutoff_utc"]
            checked = self.checked()

            async def delayed():
                self.clock.return_value = self.now.replace(minute=30)
                return checked

            output = self.root / f"past-launch-window-{allow_daytime}"
            with patch.object(campaign, "check", side_effect=delayed), \
                    patch.object(match, "run_match", new_callable=AsyncMock) as runner:
                with self.assertRaisesRegex(ValueError, "may launch only"):
                    asyncio.run(campaign.run(output, allow_daytime=allow_daytime))
            runner.assert_not_called()
            saved = json.loads((output / "campaign.json").read_text())
            self.assertEqual(saved["cutoff_utc"], cutoff)
            self.assertEqual(saved["status"], "failed")
            self.assertEqual([child["status"] for child in saved["shard_statuses"]], ["not_started"] * 4)

    def test_process_cleanup_deduplicates_pids_and_preserves_unknown_status(self):
        output = self.root / "cleanup"
        for index, pids in ((1, (101, 102)), (2, (102, 103))):
            folder = output / f"shard-{index}" / "match"
            folder.mkdir(parents=True)
            record = {"engines": {role: {"pid": pid} for role, pid in zip(("candidate", "opponent"), pids)}}
            (folder / "games.jsonl").write_text(json.dumps(record) + "\n")

        def status(pid, signal):
            self.assertEqual(signal, 0)
            if pid == 101:
                raise ProcessLookupError
            if pid == 103:
                raise PermissionError

        with patch.object(campaign.os, "kill", side_effect=status) as kill:
            result = campaign.process_cleanup(output)
        self.assertEqual(kill.call_count, 3)
        self.assertEqual(result, {"engine_pids": [101, 102, 103], "alive_pids": [102], "unverified_pids": [103]})

    def test_unverified_cleanup_invalidates_and_retains_campaign(self):
        for failure in ("alive_pids", "unverified_pids"):
            cleanup = {"engine_pids": [100], "alive_pids": [], "unverified_pids": []}
            cleanup[failure] = [100]
            output = self.root / failure
            with patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(match, "run_match", new_callable=AsyncMock, return_value={"experiment_complete": True}), \
                    patch.object(campaign, "process_cleanup", return_value=cleanup):
                with self.assertRaisesRegex(ValueError, "cleanup could not be verified"):
                    asyncio.run(campaign.run(output))
            saved = json.loads((output / "campaign.json").read_text())
            self.assertEqual(saved["status"], "invalidated")
            self.assertEqual(saved["cleanup"], cleanup)

    def test_cutoff_cancels_every_worker_once_and_retains_manifest(self):
        cleaned=[]
        async def runner(*_,**__):
            try: await asyncio.Future()
            finally: await asyncio.sleep(.01); cleaned.append(True)
        policy=campaign.launch_policy(self.now); policy["cutoff_utc"]=(self.now+timedelta(seconds=.15)).isoformat()
        with patch.object(campaign,"launch_policy",return_value=policy),patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"cutoff"))
        self.assertEqual(len(cleaned),4)
        report=json.loads((self.root/"cutoff/campaign.json").read_text()); self.assertEqual(report["status"],"interrupted")

    def test_cli_has_no_resume_or_sample_overrides(self):
        for argument in ("--resume","--pairs","--seed","--threads", "--allow-daytime"):
            with patch("sys.stderr",new_callable=io.StringIO),self.assertRaises(SystemExit):
                campaign.main(["run","--output",str(self.root/"out"),argument])


    def test_monitor_gap_fails_closed(self):
        async def runner(*_, **__):
            await asyncio.Future()
        with patch.object(campaign,"MAX_RESOURCE_GAP_SECONDS",.002), patch.object(campaign,"POLL_SECONDS",.02), \
             patch.object(campaign,"check",return_value=self.checked()), patch.object(match,"run_match",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"observation gap"):
                asyncio.run(campaign.run(self.root/"gap"))

    def test_utc_jump_aborts_even_when_monotonic_elapsed_is_small(self):
        # Model laptop sleep on hosts where monotonic time does not advance.
        # A normal short loop is insufficient: the separate civil UTC check must fire.
        for jump in (6, -1):
            with self.subTest(jump=jump):
                self.clock.return_value = self.now
                started, cleaned = set(), set()
                async def runner(*args, **hooks):
                    seed = args[5]; started.add(seed)
                    try:
                        while len(started) < 4:
                            await asyncio.sleep(.001)
                        await asyncio.sleep(.03)
                        self.clock.return_value = self.now + timedelta(seconds=jump)
                        await asyncio.Future()
                    finally:
                        cleaned.add(seed)
                with patch.object(campaign, "POLL_SECONDS", .01), \
                        patch.object(campaign, "check", return_value=self.checked()), \
                        patch.object(match, "run_match", side_effect=runner):
                    with self.assertRaisesRegex(ValueError, "observation gap"):
                        asyncio.run(campaign.run(self.root/f"utc-gap-{jump}"))
                self.assertEqual(cleaned, set(campaign.SEEDS))

    def test_source_drift_during_game_invalidates_campaign(self):
        started=set()
        async def runner(*args, **hooks):
            started.add(args[5])
            while len(started)<4:
                await asyncio.sleep(.001)
            (self.root/campaign.PROTOCOL_DOCUMENT).write_text("changed after admission")
            await hooks["before_game"]("p000001-1")
        with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root/"drift"))
        saved=json.loads((self.root/"drift/campaign.json").read_text())
        self.assertEqual(saved["status"],"invalidated")
        self.assertFalse(saved["artifacts_after"]["unchanged"])

    def test_cancel_during_failure_cleanup_waits_for_every_child(self):
        async def exercise():
            started,cleaned=set(),set()
            entered,release=asyncio.Event(),asyncio.Event()
            async def runner(*args,**_):
                seed=args[5]; started.add(seed)
                try:
                    while len(started)<4: await asyncio.sleep(.001)
                    if seed==campaign.SEEDS[0]: raise ValueError("original failure")
                    await asyncio.Future()
                finally:
                    if seed!=campaign.SEEDS[0]:
                        entered.set(); await release.wait()
                    cleaned.add(seed)
            with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
                task=asyncio.create_task(campaign.run(self.root/"cancel-cleanup"))
                await asyncio.wait_for(entered.wait(),2)
                task.cancel(); await asyncio.sleep(.01)
                self.assertFalse(task.done()); release.set()
                with self.assertRaises(asyncio.CancelledError): await asyncio.wait_for(task,2)
            self.assertEqual(cleaned,set(campaign.SEEDS))
        asyncio.run(exercise())
        saved=json.loads((self.root/"cancel-cleanup/campaign.json").read_text())
        self.assertEqual(saved["status"],"interrupted")
        self.assertEqual(len(saved["shard_statuses"]),4)
        self.assertTrue(saved["artifacts_after"]["unchanged"])


if __name__ == "__main__": unittest.main()
