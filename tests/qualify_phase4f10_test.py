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
import qualify_phase4f10 as campaign
from match_test import FAKE_ENGINE

FAKE = FAKE_ENGINE.replace(
    '        output("option name Research Toggle type check default true")',
    '        output("option name Late Move Reductions type check default true")\n'
    '        output("option name Continuation History type check default false")\n'
    '        output("option name TT Move Hints type check default false")\n'
    '        output("option name Deep Quiet Reductions type check default false")\n'
    '        output("option name ProbCut type check default false")\n'
    '        output("option name Countermove Ordering type check default false")\n'
    '        output("option name Null Move Pruning type check default false")\n'
    '        output("option name Reverse Futility Pruning type check default false")\n'
    '        output("option name QSearch SEE Pruning type check default false")\n'
    '        output("option name Capture Ordering type combo default mvv-lva var mvv-lva var see")\n'
    '        output("option name SyzygyPath type string default <empty>")\n'
    '        output("option name SyzygyProbeLimit type spin default 7 min 0 max 7")\n'
    '        output("option name SyzygyProbeDepth type spin default 1 min 1 max 128")')

FAKE = FAKE.replace("Time Policy type combo default classic var classic var forecast",
                    "Time Policy type combo default classic var classic var forecast var bounded")

# Match the frozen real binary's option declarations while keeping the process
# deliberately incapable of engine evaluation/search.
for old, new in (("Hash type spin default 8", "Hash type spin default 64"),
                 ("Threads type spin default 2 min 1 max 1024", "Threads type spin default 1 min 1 max 64"),
                 ("Move Overhead type spin default 0", "Move Overhead type spin default 20"),
                 ("EvalFile type string default none", "EvalFile type string default nn-1a298aa575a0.nnue")):
    FAKE = FAKE.replace(old, new)


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
        with tempfile.TemporaryDirectory(prefix="phase4f10-pins-") as directory:
            root = Path(directory)
            path = root/campaign.PIN_FILE; path.parent.mkdir(parents=True)
            valid = {"schema_version": 1, "protocol_id": campaign.PROTOCOL_ID,
                     "input_sha256": {name: "a"*64 for name in campaign.PINNED_INPUTS}}
            with patch.object(campaign, "ROOT", root):
                path.write_text(json.dumps(valid))
                self.assertEqual(campaign.input_pins(), valid["input_sha256"])
                for broken in ([], {**valid, "protocol_id": "historical-permission"},
                               {**valid, "schema_version": 2}, {**valid, "schema_version": True},
                               {**valid, "input_sha256": {}},
                               {**valid, "input_sha256": {**valid["input_sha256"], "extra": "a"*64}},
                               {**valid, "input_sha256": {name: "invalid" for name in campaign.PINNED_INPUTS}}):
                    with self.subTest(broken=broken):
                        path.write_text(json.dumps(broken))
                        with self.assertRaises(ValueError): campaign.input_pins()

    def test_duplicate_preparation_identity_rejects(self):
        with tempfile.TemporaryDirectory(prefix="phase4f10-duplicate-") as directory:
            path = Path(directory)/"pins.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                campaign.read_json_document(path)


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openings = synthetic_openings()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase4f10-test-")
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
            path = self.root/f"tests/data/phase4f10-match-{i:02d}.json"
            path.write_text(json.dumps({"openings": self.openings[(i-1)*64:i*64]}))
            pins[f"openings_{i}"] = (path, match.sha256(path))
        committed = {name: match.sha256(self.root/campaign.FROZEN_SOURCE_PREFIX/name)
                     for name in campaign.SOURCE_RELATIVE_NAMES}
        origin = {"phase": "4F.8", "binary": {"path": "build/experiments/phase4f8/native/chess0live",
                    "sha256": campaign.ENGINE_SHA256}, "network": {
                    "path": "networks/nn-1a298aa575a0.nnue", "sha256": campaign.NETWORK_SHA256},
                  "sources": {name: value for name, value in committed.items() if not name.startswith("third_party/")},
                  "upstream_dependencies": {name: value for name, value in committed.items() if name.startswith("third_party/")}}
        (self.root/campaign.ORIGIN_MANIFEST).write_text(json.dumps(origin))
        manifest = {"schema_version": 1, "engine_source_revision": campaign.SOURCE_REVISION,
                    "copied_from": "build/experiments/phase4f8/native/chess0live",
                    "binary_sha256": campaign.ENGINE_SHA256, "network_sha256": campaign.NETWORK_SHA256,
                    "source_sha256": {name: match.sha256(self.root/name) for name in campaign.BUILD_SOURCE_NAMES},
                    "committed_source_sha256": committed, "origin_manifest": campaign.ORIGIN_MANIFEST,
                    "origin_manifest_sha256": match.sha256(self.root/campaign.ORIGIN_MANIFEST)}
        (self.root/campaign.BUILD_MANIFEST).write_text(json.dumps(manifest))
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
        self.assertEqual(campaign.SEEDS, tuple(range(202610284101,202610284105)))
        candidate, opponent = map(dict, campaign.ROLE_OPTIONS)
        for role in (candidate, opponent):
            self.assertEqual(role["Late Move Reductions"], "true")
            self.assertEqual(role["Time Policy"], "classic")
            self.assertEqual(role["SyzygyProbeLimit"], "0")
            self.assertEqual(role["SyzygyProbeDepth"], "1")
            self.assertNotIn("SyzygyPath", role)  # Cleared explicitly by the shared runner.
        self.assertEqual({name for name in candidate if candidate[name] != opponent[name]}, {"Continuation History"})
        self.assertEqual(candidate["Continuation History"], "true")
        self.assertEqual(opponent["Continuation History"], "false")
        for name in campaign.CHECK_OPTIONS:
            if name not in ("Late Move Reductions", "Continuation History"):
                self.assertEqual(candidate[name], "false")
                self.assertEqual(opponent[name], "false")
        self.assertEqual(candidate["Capture Ordering"], "mvv-lva")
        self.assertEqual(opponent["Capture Ordering"], "mvv-lva")
        self.assertEqual(campaign.PROTOCOL_ID, "phase4f10-continuation-512-v1")
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
        self.assertEqual(len({engine["pid"] for engine in report["preflight"]["engines"]}), 2)
        self.assertFalse(report["launch_policy"]["allow_daytime"])
        self.assertIsNone(report["launch_policy"]["daytime_authorization"])
        for engine in report["preflight"]["engines"]:
            self.assertEqual(engine["configured"]["SyzygyProbeLimit"],0)
            self.assertEqual(engine["configured"]["SyzygyPath"],"")
            for option in ("Countermove Ordering", "Null Move Pruning",
                           "Reverse Futility Pruning", "QSearch SEE Pruning"):
                self.assertIs(engine["configured"][option], False)
            self.assertIs(engine["configured"]["Late Move Reductions"], True)
            for name in ("Deep Quiet Reductions", "ProbCut"):
                self.assertIs(engine["configured"][name], False)
            self.assertIs(engine["configured"]["Continuation History"], engine["role"] == "candidate")
            self.assertEqual(engine["configured"]["SyzygyProbeDepth"], 1)
            self.assertGreater(engine["pid"], 0)
            self.assertEqual(engine["returncode"], 0)
            self.assertFalse(any(e["line"].startswith(("position ","go ")) for e in engine["transcript"]))

    def test_option_default_or_disabled_limit_drift_rejects(self):
        changed_defaults = tuple((f"{option} type check default false", f"{option} type check default true")
                                 for option in ("Deep Quiet Reductions", "Countermove Ordering", "Null Move Pruning",
                                                "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut", "Continuation History", "TT Move Hints"))
        for old,new in (*changed_defaults,
                        ("Late Move Reductions type check default true", "Late Move Reductions type check default false"),
                        ("var classic var forecast var bounded", "var classic var forecast"),
                        ("SyzygyProbeLimit type spin default 7 min 0","SyzygyProbeLimit type spin default 7 min 1"),
                        ("SyzygyPath type string default <empty>","SyzygyPath type string default /tables"),
                        ("SyzygyProbeDepth type spin default 1", "SyzygyProbeDepth type spin default 2"),
                        ("EvalFile type string default nn-1a298aa575a0.nnue", "EvalFile type string default none"),
                        ("Hash type spin default 64", "Hash type spin default 128"),
                        ("Threads type spin default 1 min 1 max 64", "Threads type spin default 1 min 1 max 128"),
                        ("Move Overhead type spin default 20", "Move Overhead type spin default 0"),
                        ("Clear Hash type button", "Clear Hash type check default false")):
            self.fake.write_text(FAKE.replace(old,new))
            with patch.object(campaign,"fixed_request",return_value=self.fake_request()), self.assertRaises((ValueError,match.chess.engine.EngineError)):
                asyncio.run(campaign.check())

    def test_nonzero_readiness_exit_rejected(self):
        self.fake.write_text(FAKE.replace('elif command == "quit": break', 'elif command == "quit": sys.exit(7)'))
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                self.assertRaisesRegex(ValueError, "did not exit cleanly"):
            asyncio.run(campaign.check())

    def test_readiness_reused_pid_rejects_and_closes_both_processes(self):
        original_start, original_close = match.start_engine, match.close_engine
        closed = []
        async def start(*args, **kwargs):
            transport, protocol, configured = await original_start(*args, **kwargs)
            transport.get_pid = lambda: 12345
            return transport, protocol, configured
        async def close(transport, protocol):
            await original_close(transport, protocol)
            closed.append(transport.get_returncode())
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                patch.object(match, "start_engine", side_effect=start), \
                patch.object(match, "close_engine", side_effect=close), \
                self.assertRaisesRegex(ValueError, "repeated preflight"):
            asyncio.run(campaign.check())
        self.assertEqual(closed, [0, 0])

    def test_option_inventory_rejects_unfrozen_behavior(self):
        self.fake.write_text(FAKE.replace('output("uciok")',
            'output("option name Opening Book type check default true"); output("uciok")'))
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                self.assertRaisesRegex(ValueError, "option inventory"):
            asyncio.run(campaign.check())

    def test_duplicate_continuation_declaration_is_not_hidden_by_parser(self):
        self.fake.write_text(FAKE.replace('output("uciok")',
            'output("option name Continuation History type check default false"); output("uciok")'))
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                self.assertRaisesRegex(ValueError, "Duplicate raw UCI"):
            asyncio.run(campaign.check())

    def test_unrelated_hint_setting_must_remain_disabled(self):
        start = match.start_engine
        async def corrupted(*args, **kwargs):
            transport, protocol, configured = await start(*args, **kwargs)
            configured["TT Move Hints"] = True
            return transport, protocol, configured
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                patch.object(match, "start_engine", side_effect=corrupted), \
                self.assertRaisesRegex(ValueError, "frozen package: TT Move Hints"):
            asyncio.run(campaign.check())

    def test_preparation_pins_cover_every_source_except_self(self):
        self.assertEqual(set(campaign.PINNED_INPUTS), set(campaign.SOURCES)-{campaign.PIN_FILE})
        self.assertEqual(len(campaign.SOURCES), len(set(campaign.SOURCES)))
        self.assertEqual(len(campaign.BUILD_SOURCE_NAMES), 27)
        self.assertTrue(set(campaign.BUILD_SOURCE_NAMES) <= set(campaign.PINNED_INPUTS))

    def test_provenance_identity_membership_and_digests_reject(self):
        path = self.root/campaign.BUILD_MANIFEST
        valid = json.loads(path.read_text())
        changes = [[], {**valid, "schema_version": 2}, {**valid, "schema_version": True}]
        for key in ("engine_source_revision", "binary_sha256", "network_sha256", "copied_from", "origin_manifest", "origin_manifest_sha256"):
            changes.append({**valid, key: "wrong"})
        for sources in ({}, {**valid["source_sha256"], "extra.cpp": "a"*64},
                        {name: "invalid" for name in campaign.BUILD_SOURCE_NAMES},
                        {name: "a"*64 for name in campaign.BUILD_SOURCE_NAMES}):
            changes.append({**valid, "source_sha256": sources})
        for document in changes:
            with self.subTest(document=document):
                path.write_text(json.dumps(document))
                with self.assertRaises(ValueError): campaign.validate_build_provenance()
        path.write_text(json.dumps(valid))
        campaign.validate_build_provenance()
        source = self.root/campaign.BUILD_SOURCE_NAMES[0]
        source.write_text("source changed while binary unchanged")
        with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
            campaign.validate_build_provenance()

    def test_frozen_engine_network_and_opening_pins_reject_drift(self):
        for name, (path, expected) in campaign.frozen().items():
            old = path.read_bytes()
            with self.subTest(asset=name):
                path.write_bytes(old + b"changed")
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    campaign.snapshot()
                path.write_bytes(old)
                self.assertEqual(match.sha256(path), expected)

    def test_committed_map_must_match_every_frozen_source(self):
        path = self.root/campaign.BUILD_MANIFEST
        valid = json.loads(path.read_text())
        for committed in ({}, {**valid["committed_source_sha256"], "extra": "a"*64},
                          {name: "a"*64 for name in campaign.SOURCE_RELATIVE_NAMES}):
            path.write_text(json.dumps({**valid, "committed_source_sha256": committed}))
            with self.assertRaises(ValueError):
                campaign.validate_build_provenance()
        path.write_text(json.dumps(valid))
        campaign.validate_build_provenance()

    def test_origin_provenance_rejects_identity_inventory_or_partition_drift(self):
        path = self.root/campaign.ORIGIN_MANIFEST
        manifest_path = self.root/campaign.BUILD_MANIFEST
        valid, manifest = json.loads(path.read_text()), json.loads(manifest_path.read_text())
        original = next(iter(valid["sources"]))
        changes = [[], {**valid, "phase": "4F.7"}, {**valid, "binary": {}},
                   {**valid, "network": {}}, {**valid, "sources": {}},
                   {**valid, "upstream_dependencies": {**valid["upstream_dependencies"],
                                                       original: valid["sources"][original]}}]
        for changed in changes:
            path.write_text(json.dumps(changed))
            manifest_path.write_text(json.dumps({**manifest, "origin_manifest_sha256": match.sha256(path)}))
            with self.assertRaises(ValueError):
                campaign.validate_build_provenance()
        path.write_text(json.dumps(valid)); manifest_path.write_text(json.dumps(manifest))
        campaign.validate_build_provenance()

    def test_preparation_drift_rejects(self):
        for name in campaign.input_pins():
            path=self.root/name; old=path.read_bytes(); path.write_bytes(old+b"changed")
            with self.assertRaisesRegex(ValueError,"SHA-256"): campaign.snapshot()
            path.write_bytes(old)

    def test_duplicate_and_exposed_openings_reject_before_process_start(self):
        path=campaign.frozen()["openings_2"][0]
        for entries in (self.openings[:64],self.openings[64:127], [{"id":"missing-history","moves":[]}]*64):
            path.write_text(json.dumps({"openings":entries})); campaign.frozen()["openings_2"]=(path,match.sha256(path)); campaign.input_pins()["tests/data/phase4f10-match-02.json"]=match.sha256(path)
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

    def test_daytime_authorization_has_exact_date_and_window(self):
        cases = ((datetime(2026, 10, 28, 16, 59, 59, 999999, tzinfo=timezone.utc), False),
                 (datetime(2026, 10, 28, 17, tzinfo=timezone.utc), True),
                 (datetime(2026, 10, 28, 19, 59, 59, 999999, tzinfo=timezone.utc), True),
                 (datetime(2026, 10, 28, 20, tzinfo=timezone.utc), False),
                 (datetime(2026, 10, 27, 17, tzinfo=timezone.utc), False),
                 (datetime(2026, 10, 29, 17, tzinfo=timezone.utc), False),
                 (datetime(2026, 10, 28, 21, tzinfo=timezone.utc), False))
        for stamp, allowed in cases:
            with self.subTest(stamp=stamp):
                if not allowed:
                    with self.assertRaisesRegex(ValueError, "may launch only"):
                        campaign.launch_policy(stamp, allow_daytime=True)
                    continue
                policy = campaign.launch_policy(stamp, allow_daytime=True, require_window=True)
                self.assertTrue(policy["allow_daytime"])
                self.assertTrue(policy["launch_permitted"])
                self.assertFalse(policy["nighttime"])
                self.assertEqual(policy["daytime_authorization"], "phase4f10-daytime-20261028")
                self.assertEqual(policy["launch_window"], "2026-10-28 19:00–22:00 Europe/Helsinki")
                self.assertEqual(datetime.fromisoformat(policy["cutoff_utc"]),
                                 datetime(2026, 10, 29, 5, tzinfo=timezone.utc))
                self.assertEqual(datetime.fromisoformat(policy["cutoff_local"]).hour, 7)
        from zoneinfo import ZoneInfo
        stamp = datetime(2026, 10, 28, 17, 30, tzinfo=timezone.utc)
        self.assertEqual(campaign.launch_policy(stamp, allow_daytime=True),
                         campaign.launch_policy(stamp.astimezone(ZoneInfo("America/New_York")), allow_daytime=True))
        for permission in (0, 1, "true", None):
            with self.assertRaisesRegex(ValueError, "explicit boolean"):
                campaign.launch_policy(stamp, allow_daytime=permission)

    def test_expired_permission_rejects_before_readiness_or_output(self):
        self.clock.return_value = datetime(2026, 10, 28, 20, tzinfo=timezone.utc)
        with patch.object(match, "start_engine", new_callable=AsyncMock) as start:
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.check(allow_daytime=True))
        start.assert_not_called()
        with patch.object(campaign, "check", new_callable=AsyncMock) as check:
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.run(self.root/"daytime", allow_daytime=True))
        check.assert_not_called()
        self.assertFalse((self.root/"daytime").exists())

    def test_dated_readiness_has_exact_grant_without_search_or_budget_change(self):
        self.clock.return_value = datetime(2026, 10, 28, 17, 30, tzinfo=timezone.utc)
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        before_config, before_budget = campaign.configuration(), campaign.resource_policy()
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()):
            report = asyncio.run(campaign.check(allow_daytime=True))
        self.assertEqual(report["launch_policy"]["daytime_authorization"], campaign.DAYTIME_AUTHORIZATION)
        self.assertTrue(report["launch_policy"]["allow_daytime"])
        self.assertEqual(report["preflight"]["resource_policy"]["percent"], 50)
        self.assertEqual(campaign.configuration(), before_config)
        self.assertEqual(campaign.resource_policy(), before_budget)
        for engine in report["preflight"]["engines"]:
            self.assertFalse(any(event["line"].startswith(("position ", "go ")) for event in engine["transcript"]))

    def test_flagged_readiness_expiring_at_completion_rejects_after_cleanup(self):
        self.clock.return_value = datetime(2026, 10, 28, 19, 59, tzinfo=timezone.utc)
        close, closed = match.close_engine, []
        async def delayed_close(transport, protocol):
            await close(transport, protocol)
            closed.append(transport.get_returncode())
            if len(closed) == 2:
                self.clock.return_value = datetime(2026, 10, 28, 20, tzinfo=timezone.utc)
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                patch.object(match, "close_engine", side_effect=delayed_close):
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.check(allow_daytime=True))
        self.assertEqual(closed, [0, 0])

    def test_daytime_flag_reaches_children_and_retains_original_cutoff(self):
        self.now = datetime(2026, 10, 28, 17, 30, tzinfo=timezone.utc)
        self.clock.return_value = self.now
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        before_config = campaign.configuration()
        async def runner(*args, **hooks):
            await hooks["before_game"]("p000001-1")
            return {"experiment_complete": True}
        output = self.root/"authorized-evening"
        with patch.object(campaign, "check", return_value=self.checked()) as check, \
                patch.object(match, "run_match", side_effect=runner):
            report = asyncio.run(campaign.run(output, allow_daytime=True))
        check.assert_awaited_once_with(allow_daytime=True)
        self.assertEqual(report["configuration"], before_config)
        self.assertEqual(report["status"], "finished")
        self.assertEqual(report["launch_policy"]["daytime_authorization"], campaign.DAYTIME_AUTHORIZATION)
        self.assertEqual(datetime.fromisoformat(report["cutoff_utc"]),
                         datetime(2026, 10, 29, 5, tzinfo=timezone.utc))
        for index in range(1, 5):
            child = json.loads((output/f"shard-{index}"/"launch.json").read_text())
            policy = child["launch_policy"]
            self.assertTrue(policy["allow_daytime"])
            self.assertTrue(policy["launch_permitted"])
            self.assertEqual(policy["daytime_authorization"], campaign.DAYTIME_AUTHORIZATION)
            self.assertEqual(policy["launch_window"], campaign.DAYTIME_WINDOW)
            self.assertEqual(policy["cutoff_utc"], report["cutoff_utc"])
            self.assertEqual(policy["cutoff_local"], report["launch_policy"]["cutoff_local"])

    def test_daytime_preflight_expiration_cannot_start_children(self):
        self.now = datetime(2026, 10, 28, 19, 59, tzinfo=timezone.utc)
        self.clock.return_value = self.now
        checked = self.checked()
        async def delayed(**_):
            self.clock.return_value = self.now.replace(hour=20, minute=0)
            return checked
        output = self.root/"expired-evening"
        with patch.object(campaign, "check", side_effect=delayed), \
                patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.run(output, allow_daytime=True))
        runner.assert_not_called()
        saved = json.loads((output/"campaign.json").read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(datetime.fromisoformat(saved["cutoff_utc"]), datetime(2026, 10, 29, 5, tzinfo=timezone.utc))

    def test_child_readiness_crossing_daytime_endpoint_cannot_start_games(self):
        self.now = datetime(2026, 10, 28, 19, 59, tzinfo=timezone.utc)
        self.clock.return_value = self.now
        original = campaign.child_report
        def delayed(master, index):
            report = original(master, index)
            self.clock.return_value = datetime(2026, 10, 28, 20, tzinfo=timezone.utc)
            return report
        output = self.root/"child-expired-evening"
        with patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(campaign, "child_report", side_effect=delayed), \
                patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.run(output, allow_daytime=True))
        runner.assert_not_called()
        saved = json.loads((output/"campaign.json").read_text())
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(datetime.fromisoformat(saved["cutoff_utc"]), datetime(2026, 10, 29, 5, tzinfo=timezone.utc))

    def test_daytime_search_free_readiness_does_not_grant_launch(self):
        self.clock.return_value = datetime(2026, 10, 28, 10, tzinfo=timezone.utc)
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()):
            report = asyncio.run(campaign.check())
        self.assertFalse(report["launch_policy"]["launch_permitted"])
        self.assertFalse(report["launch_policy"]["allow_daytime"])
        self.assertIsNone(report["launch_policy"]["daytime_authorization"])
        for engine in report["preflight"]["engines"]:
            self.assertFalse(any(event["line"].startswith(("position ", "go ")) for event in engine["transcript"]))

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
        async def delayed(**_): self.clock.return_value=self.now+timedelta(hours=8); return checked
        with patch.object(campaign,"check",side_effect=delayed),patch.object(match,"run_match",new_callable=AsyncMock) as runner:
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"late"))
        runner.assert_not_called()

    def test_preflight_crossing_launch_window_rejects_without_starting_children(self):
        for allow_daytime in (False,):
            self.clock.return_value = self.now.replace(minute=29)
            cutoff = campaign.launch_policy(self.clock.return_value, allow_daytime=allow_daytime)["cutoff_utc"]
            checked = self.checked()

            async def delayed(**_):
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
        for argument in ("--resume","--pairs","--seed","--threads"):
            with patch("sys.stderr",new_callable=io.StringIO),self.assertRaises(SystemExit):
                campaign.main(["run","--output",str(self.root/"out"),argument])


    def test_cli_daytime_permission_is_explicit_and_propagates(self):
        for action in ("check", "run"):
            for enabled in (False, True):
                arguments = [action]
                if action == "run": arguments.extend(("--output", str(self.root/"cli-run")))
                if enabled: arguments.append("--allow-daytime")
                with patch.object(campaign, action, new_callable=AsyncMock, return_value={}) as operation, \
                        patch("sys.stdout", new_callable=io.StringIO):
                    self.assertEqual(campaign.main(arguments), 0)
                if action == "check": operation.assert_awaited_once_with(allow_daytime=enabled)
                else: operation.assert_awaited_once_with(self.root/"cli-run", allow_daytime=enabled)

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
