#!/usr/bin/env python3
"""Synthetic four-shard lifecycle and frozen qualification boundary checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import match
import qualification as shared
import qualify_phase4f13 as campaign
REAL_RUN_SMOKE = campaign.run_smoke
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
    while len(entries) < campaign.PAIRS + campaign.SMOKE_PAIRS:
        board, moves = match.chess.Board(), []
        for _ in range(6):
            if board.outcome(claim_draw=True):
                break
            move = rng.choice(list(board.legal_moves)); moves.append(move.uci()); board.push(move)
        key = " ".join(board.fen().split()[:4])
        if len(moves) == 6 and key not in roots and not board.outcome(claim_draw=True):
            roots.add(key); entries.append({"id": f"synthetic-{len(entries)}", "moves": moves})
    return entries


class PreparationPinsTests(unittest.TestCase):
    def test_schema_membership_and_hashes_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="phase4f13-pins-") as directory:
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
        with tempfile.TemporaryDirectory(prefix="phase4f13-duplicate-") as directory:
            path = Path(directory)/"pins.json"
            path.write_text('{"schema_version": 1, "schema_version": 1}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                campaign.read_json_document(path)


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openings = synthetic_openings()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase4f13-test-")
        self.addCleanup(temporary.cleanup); self.root = Path(temporary.name).resolve()
        self.patch(campaign, "ROOT", self.root)
        for name in campaign.SOURCES:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("synthetic source")
        (self.root/campaign.EXCLUSIONS).write_text(json.dumps({"roots": [{
            "root_key": " ".join(match.chess.Board().fen().split()[:4]), "sources": ["synthetic"]}]}))
        pins = {}
        hashes = {}
        for role, name in campaign.ENGINE_PATHS.items():
            path = self.root/name; path.write_bytes(("synthetic executable " + role).encode())
            hashes[role] = match.sha256(path)
            pins["engine_" + role] = (path, hashes[role])
        self.patch(campaign, "ENGINE_SHA256S", hashes)
        network = self.root/"networks/nn-1a298aa575a0.nnue"
        network.parent.mkdir(exist_ok=True); network.write_bytes(b"synthetic network")
        pins["network"] = (network, match.sha256(network))
        self.patch(campaign, "NETWORK_SHA256", pins["network"][1])
        for i in range(1, 5):
            path = self.root/f"tests/data/phase4f13-match-{i:02d}.json"
            path.write_text(json.dumps({"openings": self.openings[(i-1)*256:i*256]}))
            pins[f"openings_{i}"] = (path, match.sha256(path))
        smoke_entries = [dict(entry, id=identifier) for entry, identifier in
                         zip(self.openings[campaign.PAIRS:], campaign.SMOKE_OPENING_IDS)]
        (self.root/campaign.SMOKE_CATALOG).write_text(json.dumps({"openings": smoke_entries}))
        for index, (name, entry) in enumerate(zip(campaign.SMOKE_SUITE_FILES, smoke_entries), 1):
            path = self.root/name
            path.write_text(json.dumps({"openings": [entry]}))
            pins[f"smoke_openings_{index}"] = (path, match.sha256(path))
        for role, directory in campaign.ROLE_DIRECTORIES.items():
            prefix = directory + "/source/"
            copied = {name: match.sha256(self.root/prefix/name) for name in campaign.ROLE_SOURCE_SUFFIXES[role]}
            if role == "opponent":
                origin = {"parent_commit": campaign.SOURCE_REVISIONS[role],
                          "binary": {"sha256": hashes[role], "flags": campaign.COMPILE_FLAGS},
                          "network_sha256": campaign.NETWORK_SHA256, "sources": copied}
            else:
                origin = {"candidate_sha256": hashes[role], "baseline_sha256": hashes["opponent"],
                          "source_sha256": copied, "oracle_report_sha256": "a"*64}
            (self.root/campaign.ORIGIN_MANIFESTS[role]).write_text(json.dumps(origin))
            manifest = {"schema_version": 1, "role": "baseline" if role == "opponent" else role,
                        "engine_source_revision": campaign.SOURCE_REVISIONS[role],
                        "binary_sha256": hashes[role], "network_sha256": campaign.NETWORK_SHA256,
                        "compile_flags": campaign.COMPILE_FLAGS,
                        "source_sha256": {prefix+name: digest for name, digest in copied.items()},
                        "origin_manifest": campaign.ORIGIN_MANIFESTS[role],
                        "origin_manifest_sha256": match.sha256(self.root/campaign.ORIGIN_MANIFESTS[role]),
                        "build_log": campaign.BUILD_LOGS[role],
                        "build_log_sha256": match.sha256(self.root/campaign.BUILD_LOGS[role])}
            (self.root/campaign.BUILD_MANIFESTS[role]).write_text(json.dumps(manifest))
        self.patch(campaign, "frozen", return_value=pins)
        self.patch(campaign, "input_pins", return_value={name: match.sha256(self.root/name) for name in campaign.PINNED_INPUTS})
        self.fake = self.root/"fake.py"; self.fake.write_text(FAKE)
        self.now = datetime(2026, 10, 22, 20, 2, tzinfo=timezone.utc)
        self.clock = self.patch(campaign, "utc_now", return_value=self.now)
        self.budget = {"timezone": "Europe/Helsinki", "local_time": self.now.isoformat(), "source": "nighttime",
                       "percent": 80, "logical_cpus": 18, "max_cpu_workers": 14, "memory_fraction": .8}
        self.patch(match, "current_budget", side_effect=lambda: self.budget.copy())
        self.patch(match, "physical_memory", return_value=64*1024**3)

        # Existing supervisor tests isolate the held-out stage. Dedicated gate
        # tests below restore the real smoke implementation with mocked games.
        async def completed_smoke(output, record, *_, **__):
            record["clock_smoke"].update(status="passed", started_utc=self.now.isoformat(),
                                        finished_utc=self.now.isoformat(), passed_utc=self.now.isoformat())
        self.patch(campaign, "run_smoke", side_effect=completed_smoke)

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
        self.assertEqual((config["games"], config["pairs"], config["shards"], config["resident_engines"]), (2048,1024,4,8))
        self.assertEqual(campaign.SEEDS, tuple(range(202610304131,202610304135)))
        candidate, opponent = map(dict, campaign.ROLE_OPTIONS)
        for role in (candidate, opponent):
            self.assertEqual(role["Late Move Reductions"], "true")
            self.assertEqual(role["Time Policy"], "classic")
            self.assertEqual(role["SyzygyProbeLimit"], "0")
            self.assertEqual(role["SyzygyProbeDepth"], "1")
            self.assertNotIn("SyzygyPath", role)  # Cleared explicitly by the shared runner.
        self.assertEqual(candidate, opponent)
        self.assertEqual(candidate["Continuation History"], "false")
        self.assertEqual(opponent["Continuation History"], "false")
        for name in campaign.CHECK_OPTIONS:
            if name != "Late Move Reductions":
                self.assertEqual(candidate[name], "false")
                self.assertEqual(opponent[name], "false")
        self.assertEqual(candidate["Capture Ordering"], "mvv-lva")
        self.assertEqual(opponent["Capture Ordering"], "mvv-lva")
        self.assertEqual(campaign.PROTOCOL_ID, "phase4f13-nnue-2048-v1")
        specs, settings = campaign.fixed_request()
        self.assertEqual((settings.initial, settings.increment, settings.threads,
                          settings.hash_mb, settings.move_overhead_ms), (15.0, .15, 1, 64, 20))
        self.assertFalse(settings.smoke)
        self.assertNotEqual(specs[0].executable, specs[1].executable)
        self.assertEqual(tuple(spec.source_revision for spec in specs), campaign.REVISIONS)
        self.assertEqual((settings.max_plies, settings.startup_timeout, settings.protocol_timeout), (512,30.0,5.0))
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
            self.assertIs(engine["configured"]["Continuation History"], False)
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
        self.assertEqual(len(campaign.BUILD_SOURCE_NAMES), 48)
        self.assertTrue(set(campaign.BUILD_SOURCE_NAMES) <= set(campaign.PINNED_INPUTS))

    def test_provenance_identity_membership_and_digests_reject(self):
        for role, manifest_name in campaign.BUILD_MANIFESTS.items():
            path = self.root/manifest_name
            valid = json.loads(path.read_text())
            changes = [[], {**valid, "schema_version": 2}, {**valid, "schema_version": True}]
            for key in ("engine_source_revision", "binary_sha256", "network_sha256", "role", "compile_flags",
                        "origin_manifest", "origin_manifest_sha256", "build_log", "build_log_sha256"):
                changes.append({**valid, key: "wrong"})
            for sources in ({}, {**valid["source_sha256"], "extra.cpp": "a"*64},
                            {name: "invalid" for name in valid["source_sha256"]},
                            {name: "a"*64 for name in valid["source_sha256"]}):
                changes.append({**valid, "source_sha256": sources})
            for document in changes:
                with self.subTest(role=role, document=document):
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

    def test_origin_provenance_rejects_identity_or_inventory_drift(self):
        for role in ("candidate", "opponent"):
            path = self.root/campaign.ORIGIN_MANIFESTS[role]
            manifest_path = self.root/campaign.BUILD_MANIFESTS[role]
            valid, manifest = json.loads(path.read_text()), json.loads(manifest_path.read_text())
            source_key = "source_sha256" if role == "candidate" else "sources"
            changes = [[], {**valid, source_key: {}},
                       {**valid, source_key: {**valid[source_key], "../escape": "a"*64}}]
            fields = ("candidate_sha256", "baseline_sha256", "oracle_report_sha256") if role == "candidate" else (
                "parent_commit", "binary", "network_sha256")
            changes.extend({**valid, key: "wrong"} for key in fields)
            for changed in changes:
                with self.subTest(role=role, changed=changed):
                    path.write_text(json.dumps(changed))
                    manifest_path.write_text(json.dumps({**manifest, "origin_manifest_sha256": match.sha256(path)}))
                    with self.assertRaises(ValueError): campaign.validate_build_provenance()
            path.write_text(json.dumps(valid)); manifest_path.write_text(json.dumps(manifest))
            campaign.validate_build_provenance()

    def test_source_and_build_log_symlink_escape_rejected(self):
        for name in (campaign.BUILD_SOURCE_NAMES[0], campaign.BUILD_LOGS["candidate"]):
            path = self.root/name
            old = path.read_bytes()
            outside = self.root/"outside"; outside.write_bytes(old)
            path.unlink(); path.symlink_to(outside)
            with self.assertRaises(ValueError): campaign.validate_build_provenance()
            path.unlink(); path.write_bytes(old)

    def test_swapped_roles_and_same_binary_reject_before_preflight(self):
        pins = campaign.frozen()
        original = {key: value for key, value in pins.items()}
        mutations = [
            {"engine_candidate": original["engine_opponent"], "engine_opponent": original["engine_candidate"]},
            {"engine_candidate": original["engine_opponent"]},
            {"engine_candidate": (original["engine_candidate"][0], original["engine_opponent"][1])},
        ]
        for mutation in mutations:
            pins.update(mutation)
            with patch.object(match, "start_engine", new_callable=AsyncMock) as start:
                with self.assertRaisesRegex(ValueError, "role identity"):
                    asyncio.run(campaign.check())
                start.assert_not_called()
            pins.update(original)
        with patch.dict(campaign.ENGINE_SHA256S, opponent=campaign.ENGINE_SHA256S["candidate"]):
            pins["engine_opponent"] = (original["engine_opponent"][0], campaign.ENGINE_SHA256S["candidate"])
            with self.assertRaisesRegex(ValueError, "distinct frozen binaries"):
                campaign.fixed_request()
        pins.update(original)

    def test_executable_aliases_rejected(self):
        candidate = campaign.frozen()["engine_candidate"][0]
        opponent = campaign.frozen()["engine_opponent"][0]
        original = opponent.read_bytes()
        for kind in ("symlink", "hardlink"):
            opponent.unlink()
            if kind == "symlink": opponent.symlink_to(candidate)
            else: opponent.hardlink_to(candidate)
            with self.assertRaises(ValueError): campaign.fixed_request()
            opponent.unlink(); opponent.write_bytes(original)

    def test_unequal_role_options_rejected(self):
        options = (campaign.COMMON_OPTIONS, (*campaign.COMMON_OPTIONS, ("Continuation History", "true")))
        with patch.object(campaign, "ROLE_OPTIONS", options):
            with self.assertRaisesRegex(ValueError, "same frozen options"):
                campaign.fixed_request()

    def test_child_report_binds_both_roles_and_requested_shard(self):
        master = self.checked()
        master["configuration"] = campaign.configuration()
        for index in range(1, 5):
            report = campaign.child_report(master, index)
            self.assertEqual(set(report["assets"]), {"engine_candidate", "engine_opponent", "network", "openings"})
            self.assertEqual(report["assets"]["openings"], master["frozen"][f"openings_{index}"])
            self.assertEqual(report["configuration"]["pairs"], 256)
            self.assertEqual(report["configuration"]["seed"], campaign.SEEDS[index-1])
            for engine in report["configuration"]["engines"]:
                self.assertEqual(engine["executable"], master["frozen"]["engine_"+engine["role"]]["path"])

    def test_smoke_profiles_use_fixed_exposed_roots_and_only_smoke_setting_differs(self):
        specs, settings = campaign.fixed_request()
        smoke_specs, smoke_settings = campaign.smoke_request()
        self.assertEqual(smoke_specs, specs)
        self.assertEqual(vars(smoke_settings), dict(vars(settings), smoke=True))
        master = self.checked()
        for index, identifier in enumerate(campaign.SMOKE_OPENING_IDS, 1):
            selected = campaign.profile(index, smoke=True)
            report = campaign.child_report(master, index, smoke=True)
            self.assertEqual(selected.pairs, 1)
            self.assertEqual(selected.seed, campaign.SMOKE_SEEDS[index-1])
            self.assertEqual(selected.protocol_id, f"{campaign.PROTOCOL_ID}-smoke-shard-{index}")
            self.assertEqual(report["assets"]["openings"], master["frozen"][f"smoke_openings_{index}"])
            self.assertEqual(report["configuration"]["settings"]["smoke"], True)
            self.assertEqual(report["preflight"]["opening_count"], 1)
            document = json.loads(selected.frozen["openings"][0].read_text())
            self.assertEqual(document["openings"][0]["id"], identifier)
        self.assertEqual(campaign.SMOKE_TIMEOUT_SECONDS, 600.0)
        self.assertEqual(campaign.SMOKE_SEEDS, tuple(range(202610304151,202610304155)))
        self.assertTrue({campaign.SMOKE_CATALOG,*campaign.SMOKE_SUITE_FILES} <= set(campaign.SOURCES))

    def test_smoke_roots_must_match_catalog_and_never_overlap_heldout(self):
        path = self.root/campaign.SMOKE_SUITE_FILES[0]
        original = path.read_text()
        document = json.loads(original)
        document["openings"][0]["moves"] = self.openings[0]["moves"]
        path.write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError, "exposed development"):
            campaign.opening_check()
        catalog = json.loads((self.root/campaign.SMOKE_CATALOG).read_text())
        catalog["openings"][0] = document["openings"][0]
        (self.root/campaign.SMOKE_CATALOG).write_text(json.dumps(catalog))
        with self.assertRaisesRegex(ValueError, "overlap held-out"):
            campaign.opening_check()

    def smoke_audit_pass(self, output):
        saved = json.loads((output/"campaign.json").read_text())
        self.assertEqual(saved["clock_smoke"]["status"], "completed")
        self.assertEqual(saved["clock_smoke"]["cleanup"]["alive_pids"], [])
        prefix = output/saved["clock_smoke"]["resource_history"]["path"]
        events = [json.loads(line) for line in prefix.read_text().splitlines()]
        self.assertEqual(len(events), saved["clock_smoke"]["resource_history"]["observations"])
        self.assertEqual(match.sha256(prefix), saved["clock_smoke"]["resource_history"]["sha256"])
        self.assertEqual(sum(event["trigger"] == "before_smoke_game" for event in events), 8)
        return {"passed": True, "errors": [], "audited_utc": campaign.utc_now().isoformat(),
                "inference_eligible": False}

    async def successful_games(self, specs, settings, suite, output, pairs, seed, **hooks):
        self.assertEqual((settings.initial, settings.increment, settings.max_plies), (15.,.15,512))
        for pair in range(1, pairs+1):
            for leg in (1,2):
                # Main mocked games need only one admission to exercise routing;
                # smoke always requires its full eight admissions before audit.
                if pair > 1: break
                await hooks["before_game"](f"p{pair:06d}-{leg}")
        return {"experiment_complete": True, "smoke": settings.smoke}

    def test_smoke_audit_and_cleanup_precede_any_heldout_worker(self):
        seen, running = [], set()
        async def runner(*args, **hooks):
            settings, seed = args[1], args[5]
            seen.append((settings.smoke, seed))
            if settings.smoke:
                running.add(seed)
                while len(running) < 4: await asyncio.sleep(.001)
            else:
                saved = json.loads((self.root/"gated"/"campaign.json").read_text())
                self.assertEqual(saved["clock_smoke"]["status"], "passed")
                self.assertTrue((self.root/"gated"/"clock-smoke-audit.json").is_file())
            return await self.successful_games(*args, **hooks)
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(campaign, "audit_clock_smoke", side_effect=self.smoke_audit_pass) as audit, \
                patch.object(match, "run_match", side_effect=runner):
            saved = asyncio.run(campaign.run(self.root/"gated", quiet_host=True))
        self.assertEqual(set(seen[:4]), {(True, seed) for seed in campaign.SMOKE_SEEDS})
        self.assertEqual({seed for smoke, seed in seen[4:] if not smoke}, set(campaign.SEEDS))
        self.assertEqual(saved["status"], "finished")
        self.assertEqual(saved["clock_smoke"]["status"], "passed")
        self.assertEqual(saved["clock_smoke"]["audit"]["path"], "clock-smoke-audit.json")
        audit.assert_called_once()

    def test_smoke_forfeit_or_audit_failure_blocks_heldout_and_preserves_evidence(self):
        for error in ("candidate time forfeit", "incomplete raw protocol evidence"):
            output = self.root/error.replace(" ", "-")
            stages = []
            async def runner(*args, **hooks):
                stages.append(args[1].smoke)
                return await self.successful_games(*args, **hooks)
            with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                    patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(campaign, "audit_clock_smoke", return_value={"passed":False,"errors":[error]}), \
                    patch.object(match, "run_match", side_effect=runner):
                with self.assertRaisesRegex(ValueError, "Clock smoke audit failed"):
                    asyncio.run(campaign.run(output, quiet_host=True))
            self.assertEqual(stages, [True]*4)
            self.assertTrue((output/"clock-smoke-audit.json").is_file())
            self.assertFalse((output/"shard-1").exists())
            saved = json.loads((output/"campaign.json").read_text())
            self.assertEqual(saved["clock_smoke"]["status"], "failed")
            self.assertEqual(saved["status"], "failed")

    def test_smoke_cannot_be_bypassed_by_a_missing_pass_verdict(self):
        with patch.object(campaign, "run_smoke", new_callable=AsyncMock), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "did not pass"):
                asyncio.run(campaign.run(self.root/"no-pass", quiet_host=True))
        runner.assert_not_called()

    def test_smoke_timeout_includes_initial_persistence(self):
        original = shared.disk_io
        delayed = False
        async def delayed_initial_write(function, *args, **kwargs):
            nonlocal delayed
            if (function == match.atomic_json and len(args) == 2
                    and args[1].get("clock_smoke", {}).get("status") == "running" and not delayed):
                delayed = True
                await asyncio.sleep(.08)
            return await original(function, *args, **kwargs)
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "SMOKE_TIMEOUT_SECONDS", .05), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(shared, "disk_io", side_effect=delayed_initial_write), \
                patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(asyncio.TimeoutError, "initial persistence"):
                asyncio.run(campaign.run(self.root/"initial-write-timeout", quiet_host=True))
        self.assertTrue(delayed)
        runner.assert_not_called()
        saved = json.loads((self.root/"initial-write-timeout"/"campaign.json").read_text())
        self.assertEqual(saved["clock_smoke"]["status"], "failed")

    def test_smoke_wall_deadline_checked_before_pass_even_without_monotonic_delay(self):
        def jumped_audit(output):
            result = self.smoke_audit_pass(output)
            self.clock.return_value = self.now + timedelta(seconds=600)
            return result
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(campaign, "audit_clock_smoke", side_effect=jumped_audit), \
                patch.object(match, "run_match", side_effect=self.successful_games):
            with self.assertRaisesRegex(asyncio.TimeoutError, "600-second deadline"):
                asyncio.run(campaign.run(self.root/"wall-smoke-timeout", quiet_host=True))
        self.assertFalse((self.root/"wall-smoke-timeout"/"shard-1").exists())

    def test_smoke_timeout_cancels_all_workers_without_heldout(self):
        cleaned, started = [], set()
        async def runner(*args, **hooks):
            self.assertTrue(args[1].smoke)
            started.add(args[5])
            try: await asyncio.Future()
            finally: cleaned.append(args[5])
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "SMOKE_TIMEOUT_SECONDS", .25), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(match, "run_match", side_effect=runner):
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(campaign.run(self.root/"smoke-timeout", quiet_host=True))
        self.assertEqual(set(cleaned), set(campaign.SMOKE_SEEDS))
        self.assertEqual(len(cleaned), 4)
        self.assertFalse((self.root/"smoke-timeout"/"shard-1").exists())

    def test_smoke_failure_and_late_cancel_join_each_child_once(self):
        async def exercise():
            started, cleaned = set(), []
            entered, release = asyncio.Event(), asyncio.Event()
            async def runner(*args, **hooks):
                self.assertTrue(args[1].smoke)
                seed = args[5]; started.add(seed)
                try:
                    while len(started)<4: await asyncio.sleep(.001)
                    if seed == campaign.SMOKE_SEEDS[0]: raise ValueError("smoke failure")
                    await asyncio.Future()
                finally:
                    if seed != campaign.SMOKE_SEEDS[0]:
                        entered.set(); await release.wait()
                    cleaned.append(seed)
            with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                    patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(match, "run_match", side_effect=runner):
                task = asyncio.create_task(campaign.run(self.root/"smoke-cancel", quiet_host=True))
                await asyncio.wait_for(entered.wait(),2)
                task.cancel(); await asyncio.sleep(.01)
                self.assertFalse(task.done()); release.set()
                with self.assertRaises(asyncio.CancelledError): await asyncio.wait_for(task,2)
            self.assertEqual(set(cleaned), set(campaign.SMOKE_SEEDS))
            self.assertEqual(len(cleaned),4)
        asyncio.run(exercise())
        self.assertFalse((self.root/"smoke-cancel"/"shard-1").exists())

    def test_smoke_audit_cannot_extend_original_cutoff_or_admission(self):
        for delta, error in ((timedelta(minutes=28), ValueError),(timedelta(hours=8), shared.WindowExpired)):
            self.clock.return_value = self.now
            output = self.root/f"late-audit-{delta.total_seconds()}"
            def delayed_audit(directory):
                result = self.smoke_audit_pass(directory)
                self.clock.return_value = self.now + delta
                return result
            with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                    patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(campaign, "audit_clock_smoke", side_effect=delayed_audit), \
                    patch.object(match, "run_match", side_effect=self.successful_games):
                with self.assertRaises(error):
                    asyncio.run(campaign.run(output, quiet_host=True))
            self.assertFalse((output/"shard-1").exists())
            saved = json.loads((output/"campaign.json").read_text())
            self.assertEqual(saved["cutoff_utc"], campaign.launch_policy(self.now)["cutoff_utc"])

    def test_delayed_smoke_audit_does_not_starve_single_io_worker_monitor(self):
        def delayed_audit(output):
            time.sleep(.2)
            return self.smoke_audit_pass(output)
        async def exercise():
            asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
            with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                    patch.object(campaign, "POLL_SECONDS", .01), \
                    patch.object(campaign, "MAX_RESOURCE_GAP_SECONDS", .15), \
                    patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(campaign, "audit_clock_smoke", side_effect=delayed_audit), \
                    patch.object(match, "run_match", side_effect=self.successful_games):
                return await campaign.run(self.root/"audit-monitor", quiet_host=True)
        saved = asyncio.run(exercise())
        self.assertEqual(saved["status"], "finished")
        events = [json.loads(line) for line in (self.root/"audit-monitor"/"resource-history.jsonl").read_text().splitlines()]
        self.assertGreater(sum(event["trigger"] == "periodic" for event in events), 5)

    def test_smoke_unverified_cleanup_blocks_audit_and_heldout(self):
        actual_cleanup = campaign.process_cleanup
        def cleanup(output):
            if output.name == "clock-smoke":
                return {"engine_pids":[123],"alive_pids":[],"unverified_pids":[123]}
            return actual_cleanup(output)
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "check", return_value=self.checked()), \
                patch.object(campaign, "process_cleanup", side_effect=cleanup), \
                patch.object(campaign, "audit_clock_smoke") as audit, \
                patch.object(match, "run_match", side_effect=self.successful_games):
            with self.assertRaisesRegex(ValueError, "Smoke engine process cleanup"):
                asyncio.run(campaign.run(self.root/"smoke-cleanup", quiet_host=True))
        audit.assert_not_called()
        self.assertFalse((self.root/"smoke-cleanup"/"shard-1").exists())

    def test_preparation_drift_rejects(self):
        for name in campaign.input_pins():
            path=self.root/name; old=path.read_bytes(); path.write_bytes(old+b"changed")
            with self.assertRaisesRegex(ValueError,"SHA-256"): campaign.snapshot()
            path.write_bytes(old)

    def test_duplicate_and_exposed_openings_reject_before_process_start(self):
        path=campaign.frozen()["openings_2"][0]
        for entries in (self.openings[:256],self.openings[256:511], [{"id":"missing-history","moves":[]}]*256):
            path.write_text(json.dumps({"openings":entries})); campaign.frozen()["openings_2"]=(path,match.sha256(path)); campaign.input_pins()["tests/data/phase4f13-match-02.json"]=match.sha256(path)
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

    def test_no_inherited_daytime_authorization(self):
        for value in (1, 0, None, "false", "phase4f10-daytime-20261028"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "must be boolean"):
                campaign.launch_policy(self.now, allow_daytime=value)
        for date in (self.now, datetime(2026, 10, 28, 17, tzinfo=timezone.utc),
                     datetime(2026, 10, 29, 12, tzinfo=timezone.utc),
                     datetime(2026, 10, 31, 12, tzinfo=timezone.utc)):
            with self.subTest(date=date), self.assertRaisesRegex(ValueError, "may launch only"):
                campaign.launch_policy(date, allow_daytime=True)

    def test_dated_window_bounds_fixed_cutoff_and_explicit_selection(self):
        day = datetime(2026, 10, 30, tzinfo=timezone.utc)
        for hour, minute, second, permitted in ((11,59,59,False), (12,0,0,True),
                                               (20,44,59,True), (20,45,0,False),
                                               (21,0,0,False)):
            instant = day.replace(hour=hour, minute=minute, second=second)
            with self.subTest(instant=instant):
                if not permitted:
                    with self.assertRaisesRegex(ValueError, "may launch only"):
                        campaign.launch_policy(instant, allow_daytime=True)
                    continue
                policy = campaign.launch_policy(instant, allow_daytime=True, require_window=True)
                self.assertTrue(policy["allow_daytime"])
                self.assertFalse(policy["nighttime"])
                self.assertTrue(policy["launch_permitted"])
                self.assertEqual(policy["daytime_authorization"], "phase4f13-daytime-20261030")
                self.assertEqual(policy["launch_window"], "2026-10-30 14:00–22:45 Europe/Helsinki")
                self.assertEqual(policy["cutoff_local"], "2026-10-31T07:00:00+02:00")
                self.assertEqual(policy["cutoff_utc"], "2026-10-31T05:00:00+00:00")
                self.assertEqual(policy["remaining_seconds"],
                                 (datetime(2026,10,31,5,tzinfo=timezone.utc)-instant).total_seconds())
                with self.assertRaisesRegex(ValueError, "may launch only"):
                    campaign.launch_policy(instant, require_window=True)
        self.assertIn(campaign.BASE_PIN_FILE, campaign.PINNED_INPUTS)
        self.assertIn(campaign.DAYTIME_AMENDMENT, campaign.PINNED_INPUTS)
        self.assertIn(campaign.PIN_FILE, campaign.SOURCES)
        self.assertNotIn(campaign.PIN_FILE, campaign.PINNED_INPUTS)

    def test_dated_readiness_rechecks_window_after_clean_handshakes(self):
        original_close = match.close_engine
        start = datetime(2026, 10, 30, 20, 44, tzinfo=timezone.utc)
        closed = []
        async def close(transport, protocol):
            await original_close(transport, protocol)
            closed.append(transport.get_returncode())
            if len(closed) == 2:
                self.clock.return_value = start.replace(minute=45)
        self.clock.return_value = start
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()), \
                patch.object(match, "close_engine", side_effect=close):
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.check(allow_daytime=True))
        self.assertEqual(closed, [0, 0])

    def test_dated_search_free_readiness_records_current_grant(self):
        self.clock.return_value = datetime(2026, 10, 30, 12, 40, tzinfo=timezone.utc)
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        with patch.object(campaign, "fixed_request", return_value=self.fake_request()):
            report = asyncio.run(campaign.check(allow_daytime=True))
        self.assertTrue(report["launch_policy"]["allow_daytime"])
        self.assertEqual(report["launch_policy"]["daytime_authorization"], campaign.DAYTIME_AUTHORIZATION)
        for engine in report["preflight"]["engines"]:
            self.assertEqual(engine["returncode"], 0)
            self.assertFalse(any(event["line"].startswith(("position ", "go ")) for event in engine["transcript"]))

    def test_dated_grant_reaches_readiness_smoke_and_full_children_without_resource_override(self):
        self.now = datetime(2026, 10, 30, 12, 40, tzinfo=timezone.utc)
        self.clock.return_value = self.now
        self.budget.update(source="daytime", percent=50, max_cpu_workers=9, memory_fraction=.5)
        output = self.root/"dated-gate"
        original = shared.run
        selections = []
        async def child(*args, **kwargs):
            selections.append(kwargs["allow_daytime"])
            return await original(*args, **kwargs)
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "check", return_value=self.checked()) as checked, \
                patch.object(campaign, "audit_clock_smoke", side_effect=self.smoke_audit_pass), \
                patch.object(shared, "run", side_effect=child), \
                patch.object(match, "run_match", side_effect=self.successful_games):
            saved = asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=True))
        checked.assert_awaited_once_with(allow_daytime=True)
        self.assertEqual(selections, [True]*8)
        self.assertEqual(saved["status"], "finished")
        self.assertEqual(saved["clock_smoke"]["status"], "passed")
        for stage in (output, output/"clock-smoke"):
            for index in range(1, 5):
                launch = json.loads((stage/f"shard-{index}"/"launch.json").read_text())
                self.assertEqual(launch["launch_policy"]["daytime_authorization"], campaign.DAYTIME_AUTHORIZATION)
                self.assertEqual(launch["launch_policy"]["cutoff_utc"], saved["cutoff_utc"])
                self.assertTrue(launch["launch_policy"]["allow_daytime"])
        policy, allowed = campaign.resource_policy()
        self.assertTrue(allowed)
        self.assertEqual((policy["percent"], policy["active_search_workers"], policy["resident_engines"],
                          policy["estimated_memory_bytes"]), (50, 4, 8, 6*1024**3))

    def test_dated_smoke_audit_cannot_cross_admission_or_fixed_cutoff(self):
        self.now = datetime(2026, 10, 30, 20, 44, tzinfo=timezone.utc)
        for finish, error in ((self.now.replace(minute=45), ValueError),
                              (datetime(2026,10,31,5,tzinfo=timezone.utc), shared.WindowExpired)):
            self.clock.return_value = self.now
            output = self.root/f"dated-late-audit-{finish.day}-{finish.hour}"
            def delayed_audit(directory):
                result = self.smoke_audit_pass(directory)
                self.clock.return_value = finish
                return result
            with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                    patch.object(campaign, "check", return_value=self.checked()), \
                    patch.object(campaign, "audit_clock_smoke", side_effect=delayed_audit), \
                    patch.object(match, "run_match", side_effect=self.successful_games):
                with self.assertRaises(error):
                    asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=True))
            self.assertFalse((output/"shard-1").exists())
            saved = json.loads((output/"campaign.json").read_text())
            self.assertEqual(saved["cutoff_utc"], "2026-10-31T05:00:00+00:00")
            self.assertEqual(saved["clock_smoke"]["status"], "failed")

    def test_dated_smoke_child_readiness_cannot_cross_admission_endpoint(self):
        self.now = datetime(2026, 10, 30, 20, 44, tzinfo=timezone.utc)
        self.clock.return_value = self.now
        checked = self.checked()
        original = shared.run
        async def delayed_child(*args, **kwargs):
            self.clock.return_value = self.now.replace(minute=45)
            return await original(*args, **kwargs)
        output = self.root/"dated-late-smoke-child"
        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                patch.object(campaign, "check", return_value=checked), \
                patch.object(shared, "run", side_effect=delayed_child), \
                patch.object(match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "may launch only"):
                asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=True))
        runner.assert_not_called()
        saved = json.loads((output/"campaign.json").read_text())
        self.assertEqual(saved["clock_smoke"]["status"], "failed")
        self.assertEqual(saved["cutoff_utc"], "2026-10-31T05:00:00+00:00")
        self.assertFalse((output/"shard-1").exists())

    def test_quiet_host_confirmation_required_before_side_effects(self):
        for value in (False, 1, 0, None, "true"):
            output = self.root/"not-authorized"
            with patch.object(campaign, "check", new_callable=AsyncMock) as checked:
                with self.assertRaisesRegex(ValueError, "quiet-host"):
                    asyncio.run(campaign.run(output, quiet_host=value))
                checked.assert_not_called()
            self.assertFalse(output.exists())

    def test_child_readiness_cannot_cross_admission_endpoint(self):
        for allow_daytime, start, finish in (
                (False, self.now.replace(minute=29), self.now.replace(minute=30)),
                (True, datetime(2026,10,30,20,44,tzinfo=timezone.utc),
                 datetime(2026,10,30,20,45,tzinfo=timezone.utc))):
            self.clock.return_value = start
            checked = self.checked()
            original = shared.run
            async def delayed_child(*args, **kwargs):
                self.clock.return_value = finish
                return await original(*args, **kwargs)
            output = self.root/f"late-child-{allow_daytime}"
            with patch.object(campaign, "check", return_value=checked), \
                    patch.object(shared, "run", side_effect=delayed_child), \
                    patch.object(match, "run_match", new_callable=AsyncMock) as runner:
                with self.assertRaisesRegex(ValueError, "may launch only"):
                    asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=allow_daytime))
            runner.assert_not_called()
            saved = json.loads((output/"campaign.json").read_text())
            self.assertEqual(saved["status"], "failed")
            self.assertTrue(saved["quiet_host"])

    def test_first_game_rechecks_admission_after_awaited_setup_and_guard(self):
        for allow_daytime, start, finish, error in (
                (False, self.now.replace(minute=29), self.now.replace(minute=30), ValueError),
                (True, datetime(2026,10,30,20,44,tzinfo=timezone.utc),
                 datetime(2026,10,30,20,45,tzinfo=timezone.utc), ValueError),
                (False, self.now.replace(minute=29), self.now+timedelta(days=1), shared.WindowExpired),
                (True, datetime(2026,10,30,20,44,tzinfo=timezone.utc),
                 datetime(2026,10,31,5,tzinfo=timezone.utc), shared.WindowExpired)):
            for smoke in (True, False):
                for delay in ("setup", "guard"):
                    with self.subTest(daytime=allow_daytime, smoke=smoke, delay=delay, finish=finish):
                        self.clock.return_value = start
                        cutoff = campaign.launch_policy(start, allow_daytime=allow_daytime)["cutoff_utc"]
                        output = self.root/f"late-first-{allow_daytime}-{smoke}-{delay}-{finish.day}-{finish.hour}"
                        accepted, delayed = [], []
                        original_verify = shared.verify_unchanged
                        original_append = campaign.append_resource_event
                        def verify(profile, *args):
                            result = original_verify(profile, *args)
                            if delay == "setup" and ("-smoke-shard-" in profile.protocol_id) is smoke:
                                self.clock.return_value = finish
                                delayed.append(True)
                            return result
                        def append(journal, event):
                            result = original_append(journal, event)
                            trigger = "before_smoke_game" if smoke else "before_game"
                            if delay == "guard" and event["trigger"] == trigger:
                                self.clock.return_value = finish
                                delayed.append(True)
                            return result
                        async def runner(*args, **hooks):
                            for leg in (1, 2):
                                await hooks["before_game"](f"p000001-{leg}")
                                if args[1].smoke is smoke:
                                    accepted.append((args[5], leg))
                            return {"experiment_complete": True, "smoke": args[1].smoke}
                        with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                                patch.object(campaign, "check", return_value=self.checked()), \
                                patch.object(campaign, "audit_clock_smoke", side_effect=self.smoke_audit_pass), \
                                patch.object(shared, "verify_unchanged", side_effect=verify), \
                                patch.object(campaign, "append_resource_event", side_effect=append), \
                                patch.object(match, "run_match", side_effect=runner):
                            with self.assertRaises(error):
                                asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=allow_daytime))
                        self.assertTrue(delayed)
                        self.assertEqual(accepted, [], "No first game may pass admission after awaited setup or guard")
                        saved = json.loads((output/"campaign.json").read_text())
                        self.assertEqual(saved["status"], "interrupted" if error is shared.WindowExpired else "failed")
                        self.assertEqual(saved["cutoff_utc"], cutoff)
                        if smoke:
                            self.assertFalse((output/"shard-1").exists())

    def test_admitted_shards_continue_games_after_admission_endpoint(self):
        for allow_daytime, start, finish in (
                (False, self.now.replace(minute=29), self.now.replace(minute=30)),
                (True, datetime(2026,10,30,20,44,tzinfo=timezone.utc),
                 datetime(2026,10,30,20,45,tzinfo=timezone.utc))):
            for smoke in (True, False):
                with self.subTest(daytime=allow_daytime, smoke=smoke):
                    self.clock.return_value = start
                    output = self.root/f"ongoing-{allow_daytime}-{smoke}"
                    first, second = set(), set()
                    async def runner(*args, **hooks):
                        if args[1].smoke is not smoke:
                            return await self.successful_games(*args, **hooks)
                        await hooks["before_game"]("p000001-1")
                        first.add(args[5])
                        while len(first) < 4:
                            await asyncio.sleep(.001)
                        self.clock.return_value = finish
                        await hooks["before_game"]("p000001-2")
                        second.add(args[5])
                        return {"experiment_complete": True, "smoke": smoke}
                    with patch.object(campaign, "run_smoke", REAL_RUN_SMOKE), \
                            patch.object(campaign, "check", return_value=self.checked()), \
                            patch.object(campaign, "audit_clock_smoke", side_effect=self.smoke_audit_pass), \
                            patch.object(match, "run_match", side_effect=runner):
                        if smoke:
                            # Games already admitted may finish, but late smoke
                            # completion still cannot admit the held-out stage.
                            with self.assertRaisesRegex(ValueError, "may launch only"):
                                asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=allow_daytime))
                        else:
                            saved = asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=allow_daytime))
                            self.assertEqual(saved["status"], "finished")
                    seeds = set(campaign.SMOKE_SEEDS if smoke else campaign.SEEDS)
                    self.assertEqual(first, seeds)
                    self.assertEqual(second, seeds)

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
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root, quiet_host=True))
            self.clock.return_value=self.now.replace(hour=10)
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root/"day", quiet_host=True))
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
            report=asyncio.run(campaign.run(output, quiet_host=True))
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
            with self.assertRaisesRegex(ValueError,"synthetic failure"): asyncio.run(campaign.run(self.root/"fail", quiet_host=True))
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
            with self.assertRaisesRegex(ValueError,"Aggregate"): asyncio.run(campaign.run(self.root/"drop", quiet_host=True))
        self.assertEqual(cleaned,set(campaign.SEEDS))

    def test_preflight_cannot_roll_cutoff_to_following_night(self):
        checked=self.checked()
        async def delayed(**_): self.clock.return_value=self.now+timedelta(hours=8); return checked
        with patch.object(campaign,"check",side_effect=delayed),patch.object(match,"run_match",new_callable=AsyncMock) as runner:
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"late", quiet_host=True))
        runner.assert_not_called()

    def test_preflight_crossing_launch_window_rejects_without_starting_children(self):
        for allow_daytime, start, finish in (
                (False, self.now.replace(minute=29), self.now.replace(minute=30)),
                (True, datetime(2026,10,30,20,44,tzinfo=timezone.utc),
                 datetime(2026,10,30,20,45,tzinfo=timezone.utc))):
            self.clock.return_value = start
            cutoff = campaign.launch_policy(self.clock.return_value, allow_daytime=allow_daytime)["cutoff_utc"]
            checked = self.checked()

            async def delayed(**_):
                self.clock.return_value = finish
                return checked

            output = self.root / f"past-launch-window-{allow_daytime}"
            with patch.object(campaign, "check", side_effect=delayed), \
                    patch.object(match, "run_match", new_callable=AsyncMock) as runner:
                with self.assertRaisesRegex(ValueError, "may launch only"):
                    asyncio.run(campaign.run(output, quiet_host=True, allow_daytime=allow_daytime))
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
                    asyncio.run(campaign.run(output, quiet_host=True))
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
            with self.assertRaises(shared.WindowExpired): asyncio.run(campaign.run(self.root/"cutoff", quiet_host=True))
        self.assertEqual(len(cleaned),4)
        report=json.loads((self.root/"cutoff/campaign.json").read_text()); self.assertEqual(report["status"],"interrupted")

    def test_cli_has_no_resume_or_sample_overrides(self):
        for argument in ("--resume","--pairs","--seed","--threads"):
            with patch("sys.stderr",new_callable=io.StringIO),self.assertRaises(SystemExit):
                campaign.main(["run","--output",str(self.root/"out"),argument])


    def test_cli_quiet_host_is_explicit_and_run_only(self):
        with patch.object(campaign, "check", new_callable=AsyncMock, return_value={}) as operation, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(campaign.main(["check"]), 0)
        operation.assert_awaited_once_with(allow_daytime=False)
        with patch.object(campaign, "run", new_callable=AsyncMock, return_value={}) as operation, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(campaign.main(["run", "--output", str(self.root/"cli-run"), "--quiet-host"]), 0)
        operation.assert_awaited_once_with(self.root/"cli-run", quiet_host=True, allow_daytime=False)
        for arguments in (["check", "--quiet-host"], ["run", "--output", str(self.root/"cli-run")]):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                campaign.main(arguments)

    def test_cli_daytime_selection_reaches_check_and_run_explicitly(self):
        with patch.object(campaign, "check", new_callable=AsyncMock, return_value={}) as operation, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(campaign.main(["check", "--allow-daytime"]), 0)
        operation.assert_awaited_once_with(allow_daytime=True)
        with patch.object(campaign, "run", new_callable=AsyncMock, return_value={}) as operation, \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(campaign.main(["run", "--quiet-host", "--allow-daytime", "--output",
                                            str(self.root/"dated-cli-run")]), 0)
        operation.assert_awaited_once_with(self.root/"dated-cli-run", quiet_host=True, allow_daytime=True)
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            campaign.main(["run", "--allow-daytime", "--output", str(self.root/"not-quiet")])

    def test_monitor_gap_fails_closed(self):
        async def runner(*_, **__):
            await asyncio.Future()
        with patch.object(campaign,"MAX_RESOURCE_GAP_SECONDS",.002), patch.object(campaign,"POLL_SECONDS",.02), \
             patch.object(campaign,"check",return_value=self.checked()), patch.object(match,"run_match",side_effect=runner):
            with self.assertRaisesRegex(ValueError,"observation gap"):
                asyncio.run(campaign.run(self.root/"gap", quiet_host=True))

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
                        asyncio.run(campaign.run(self.root/f"utc-gap-{jump}", quiet_host=True))
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
            with self.assertRaises(ValueError): asyncio.run(campaign.run(self.root/"drift", quiet_host=True))
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
                task=asyncio.create_task(campaign.run(self.root/"cancel-cleanup", quiet_host=True))
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
