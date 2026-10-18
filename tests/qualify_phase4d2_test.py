#!/usr/bin/env python3
"""Synthetic eight-shard lifecycle and fail-closed configuration checks.

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
import qualify_phase4d2 as campaign
from match_test import FAKE_ENGINE

FAKE = FAKE_ENGINE.replace(
    '        output("option name Research Toggle type check default true")',
    '        output("option name Late Move Reductions type check default false")\n'
    '        output("option name Countermove Ordering type check default false")\n'
    '        output("option name Capture Ordering type combo default mvv-lva var mvv-lva var see")\n'
    '        output("option name SyzygyPath type string default <empty>")\n'
    '        output("option name SyzygyProbeLimit type spin default 7 min 0 max 7")')


def synthetic_openings():
    rng, roots, entries = random.Random(4402026), set(), []
    while len(entries) < 512:
        board, moves = match.chess.Board(), []
        for _ in range(6):
            move = rng.choice(list(board.legal_moves)); moves.append(move.uci()); board.push(move)
        key = " ".join(board.fen().split()[:4])
        if key not in roots and not board.outcome(claim_draw=True):
            roots.add(key); entries.append({"id": f"synthetic-{len(entries)}", "moves": moves})
    return entries


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openings = synthetic_openings()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase4d2-test-")
        self.addCleanup(temporary.cleanup); self.root = Path(temporary.name).resolve()
        self.patch(campaign, "ROOT", self.root)
        for name in campaign.SOURCES:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("synthetic source")
        (self.root/campaign.EXCLUSIONS).write_text(json.dumps({"roots": [{
            "root_key": " ".join(match.chess.Board().fen().split()[:4]), "sources": ["synthetic"]}]}))
        self.patch(campaign, "INPUT_PINS", {name: match.sha256(self.root/name) for name in campaign.INPUT_PINS})
        pins = {}
        for name in ("engine", "network"):
            path = self.root/name; path.write_bytes(b"synthetic"); pins[name] = (path, match.sha256(path))
        for i in range(1, 9):
            path = self.root/f"suite-{i}.json"
            path.write_text(json.dumps({"openings": self.openings[(i-1)*64:i*64]}))
            pins[f"openings_{i}"] = (path, match.sha256(path))
        self.patch(campaign, "FROZEN", pins)
        self.fake = self.root/"fake.py"; self.fake.write_text(FAKE)
        self.now = datetime(2026, 10, 18, 20, 2, tzinfo=timezone.utc)
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

    def test_fixed_shape_and_only_lmr_differs(self):
        config = campaign.configuration()
        self.assertEqual((config["games"], config["pairs"], config["shards"], config["resident_engines"]), (1024,512,8,16))
        self.assertEqual(campaign.SEEDS, tuple(range(202610184201,202610184209)))
        roles = [dict(o) for o in campaign.ROLE_OPTIONS]
        self.assertEqual([o.pop("Late Move Reductions") for o in roles], ["true","false"])
        self.assertEqual(roles[0],roles[1]); self.assertEqual(roles[0]["SyzygyProbeLimit"],"0")
        self.assertEqual(roles[0]["Countermove Ordering"],"false")
        for index in (0,9,True,1.0):
            with self.assertRaises(ValueError): campaign.profile(index)

    def test_search_free_serial_handshakes_apply_all_modes(self):
        with patch.object(campaign,"fixed_request",return_value=self.fake_request()): report=asyncio.run(campaign.check())
        for engine in report["preflight"]["engines"]:
            self.assertEqual(engine["configured"]["SyzygyProbeLimit"],0)
            self.assertEqual(engine["configured"]["SyzygyPath"],"")
            self.assertIs(engine["configured"]["Countermove Ordering"],False)
            self.assertIs(engine["configured"]["Late Move Reductions"],engine["role"]=="candidate")
            self.assertFalse(any(e["line"].startswith(("position ","go ")) for e in engine["transcript"]))

    def test_option_default_or_disabled_limit_drift_rejects(self):
        for old,new in (("Countermove Ordering type check default false","Countermove Ordering type check default true"),
                        ("SyzygyProbeLimit type spin default 7 min 0","SyzygyProbeLimit type spin default 7 min 1"),
                        ("SyzygyPath type string default <empty>","SyzygyPath type string default /tables")):
            self.fake.write_text(FAKE.replace(old,new))
            with patch.object(campaign,"fixed_request",return_value=self.fake_request()), self.assertRaises((ValueError,match.chess.engine.EngineError)):
                asyncio.run(campaign.check())

    def test_preparation_drift_rejects(self):
        for name in campaign.INPUT_PINS:
            path=self.root/name; old=path.read_bytes(); path.write_bytes(old+b"changed")
            with self.assertRaisesRegex(ValueError,"SHA-256"): campaign.snapshot()
            path.write_bytes(old)

    def test_duplicate_and_exposed_openings_reject_before_process_start(self):
        path=campaign.FROZEN["openings_2"][0]
        for entries in (self.openings[:64],self.openings[64:127], [{"id":"missing-history","moves":[]}]*64):
            path.write_text(json.dumps({"openings":entries})); campaign.FROZEN["openings_2"]=(path,match.sha256(path))
            with patch.object(match,"start_engine",new_callable=AsyncMock) as start, self.assertRaises((ValueError,match.chess.engine.EngineError)):
                asyncio.run(campaign.check())
            start.assert_not_called()

    def test_aggregate_budget_and_unknown_memory_fail_closed(self):
        self.budget["max_cpu_workers"]=7
        with patch.object(match,"start_engine",new_callable=AsyncMock) as start,self.assertRaisesRegex(ValueError,"Aggregate"):
            asyncio.run(campaign.check())
        start.assert_not_called()
        for memory in (None,1):
            with patch.object(match,"physical_memory",return_value=memory): self.assertFalse(campaign.resource_policy()[1])

    def test_window_bounds_dst_and_no_daytime_argument(self):
        for hour,minute,good in ((19,59,False),(20,0,True),(20,29,True),(20,30,False),(21,0,False)):
            self.assertEqual(campaign.launch_policy(self.now.replace(hour=hour,minute=minute))["launch_permitted"],good)
        for date,hours in ((datetime(2026,3,28,21,tzinfo=timezone.utc),7),(datetime(2026,10,24,20,tzinfo=timezone.utc),9)):
            self.assertEqual(campaign.launch_policy(date)["remaining_seconds"],hours*3600)
        with self.assertRaises(TypeError): campaign.launch_policy(self.now,allow_daytime=True)
        with self.assertRaises(ValueError): campaign.launch_policy(datetime(2026,10,18,23))

    def test_overwrite_and_late_launch_reject_before_preflight(self):
        with patch.object(campaign,"check",new_callable=AsyncMock) as check:
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root))
            self.clock.return_value=self.now.replace(hour=10)
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root/"day"))
            check.assert_not_called()

    def test_all_eight_workers_and_reservations(self):
        started=set()
        async def runner(*args,**hooks):
            started.add(args[5])
            while len(started)<8: await asyncio.sleep(.001)
            self.assertTrue(hooks["fail_fast"]); await hooks["before_game"]("p000001-1")
            return {"experiment_complete":True}
        output=self.root/"done"
        with patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            report=asyncio.run(campaign.run(output))
        self.assertEqual(started,set(campaign.SEEDS)); self.assertEqual(report["status"],"finished")
        self.assertTrue(report["artifacts_after"]["unchanged"])
        events=[json.loads(line) for line in (output/"resource-history.jsonl").read_text().splitlines()]
        self.assertEqual({e["policy"]["resident_engines"] for e in events},{16})
        self.assertEqual({e["shard_index"] for e in events if e["trigger"]=="before_game"},set(range(1,9)))

    def test_worker_failure_cancels_and_awaits_all_cleanup(self):
        started,cleaned=set(),set()
        async def runner(*args,**_):
            seed=args[5]; started.add(seed)
            try:
                while len(started)<8: await asyncio.sleep(.001)
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
                while len(started)<8: await asyncio.sleep(.001)
                self.budget["max_cpu_workers"]=7
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

    def test_cutoff_cancels_every_worker_once_and_retains_manifest(self):
        cleaned=[]
        async def runner(*_,**__):
            try: await asyncio.Future()
            finally: await asyncio.sleep(.01); cleaned.append(True)
        policy=campaign.launch_policy(self.now); policy["cutoff_utc"]=(self.now+timedelta(seconds=.15)).isoformat()
        with patch.object(campaign,"launch_policy",return_value=policy),patch.object(campaign,"check",return_value=self.checked()),patch.object(match,"run_match",side_effect=runner):
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"cutoff"))
        self.assertEqual(len(cleaned),8)
        report=json.loads((self.root/"cutoff/campaign.json").read_text()); self.assertEqual(report["status"],"interrupted")

    def test_cli_has_no_resume_daytime_or_sample_overrides(self):
        for argument in ("--allow-daytime","--resume","--pairs","--seed","--threads"):
            with patch("sys.stderr",new_callable=io.StringIO),self.assertRaises(SystemExit):
                campaign.main(["run","--output",str(self.root/"out"),argument])

    def test_monitor_gap_fails_closed(self):
        async def runner(*_, **__):
            await asyncio.Future()
        with patch.object(campaign,"MAX_RESOURCE_GAP_SECONDS",.002), patch.object(campaign,"POLL_SECONDS",.02), \
             patch.object(campaign,"check",return_value=self.checked()), patch.object(match,"run_match",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"observation gap"):
                asyncio.run(campaign.run(self.root/"gap"))

    def test_source_drift_during_game_invalidates_campaign(self):
        started=set()
        async def runner(*args, **hooks):
            started.add(args[5])
            while len(started)<8:
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
                    while len(started)<8: await asyncio.sleep(.001)
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
        self.assertEqual(len(saved["shard_statuses"]),8)
        self.assertTrue(saved["artifacts_after"]["unchanged"])


if __name__ == "__main__": unittest.main()
