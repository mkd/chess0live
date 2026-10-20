#!/usr/bin/env python3
"""Engine-free checks for the bounded real-match readiness supervisor.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_match_readiness as readiness


def game(identifier="p000001-1", **changes):
    return dict({"game_id": identifier, "status": "complete",
                 "termination": "threefold_repetition",
                 "unexpected_stderr": False}, **changes)


def save_games(folder, records):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "games.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records))


class ConfigurationTests(unittest.TestCase):
    def test_reserves_eight_residents_for_four_search_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            network = Path(directory) / "network"
            network.write_bytes(b"x")
            policy = {"max_cpu_workers": 4, "memory_fraction": .5}
            with patch.object(readiness.match, "current_budget", return_value=policy), \
                    patch.object(readiness.match, "physical_memory", return_value=16 * 1024**3):
                result = readiness.admission(network)
            self.assertEqual(result["active_search_workers"], 4)
            self.assertEqual(result["resident_engines"], 8)
            self.assertEqual(result["estimated_memory_bytes"], 6 * 1024**3)
            self.assertFalse(result["memory_estimate_is_hard_cap"])
            self.assertNotIn("resident_engines", policy)

    def test_rejects_unknown_ram_cpu_shortfall_and_combined_memory_shortfall(self):
        with tempfile.TemporaryDirectory() as directory:
            network = Path(directory) / "network"
            network.write_bytes(b"x")
            for workers, memory in ((3, 64 * 1024**3), (4, None), (4, 0),
                                    (4, -1), (4, 8 * 1024**3)):
                with self.subTest(workers=workers, memory=memory), \
                        patch.object(readiness.match, "current_budget",
                                     return_value={"max_cpu_workers": workers, "memory_fraction": .5}), \
                        patch.object(readiness.match, "physical_memory", return_value=memory), \
                        self.assertRaisesRegex(ValueError, "aggregate budget"):
                    readiness.admission(network)

    def test_large_network_reservation_exceeds_the_per_process_floor(self):
        with tempfile.TemporaryDirectory() as directory:
            network = Path(directory) / "network"
            with network.open("wb") as stream:
                stream.truncate(256 * 1024**2)
            with patch.object(readiness.match, "current_budget",
                              return_value={"max_cpu_workers": 4, "memory_fraction": .5}), \
                    patch.object(readiness.match, "physical_memory", return_value=32 * 1024**3):
                result = readiness.admission(network)
            self.assertEqual(result["estimated_memory_bytes"],
                             8 * (64 + 4 * 256 + 128) * 1024**2)

    def test_fixed_settings_and_options_isolate_only_lmr(self):
        settings = readiness.SETTINGS
        settings.validate()
        self.assertEqual((settings.initial, settings.increment, settings.threads,
                          settings.hash_mb, settings.move_overhead_ms, settings.max_plies),
                         (3.0, .05, 1, 64, 20, 1024))
        self.assertTrue(settings.smoke)
        candidate, opponent = readiness.specifications(Path("/engine"), Path("/network"))
        self.assertEqual((candidate.role, opponent.role), ("candidate", "opponent"))
        self.assertEqual(candidate.executable, opponent.executable)
        self.assertEqual(candidate.network, opponent.network)
        on, off = dict(candidate.extra_options), dict(opponent.extra_options)
        self.assertEqual(on.pop("Late Move Reductions"), "true")
        self.assertEqual(off.pop("Late Move Reductions"), "false")
        self.assertEqual(on, off)
        self.assertEqual(on["Time Policy"], "classic")
        self.assertEqual(on["Capture Ordering"], "mvv-lva")
        for name in ("Countermove Ordering", "Null Move Pruning",
                     "Reverse Futility Pruning", "QSearch SEE Pruning"):
            self.assertEqual(on[name], "false")
        self.assertEqual(on["SyzygyProbeLimit"], "0")
        self.assertEqual(len(set(readiness.SUITES)), 4)
        self.assertEqual(len(set(readiness.SEEDS)), 4)

    def test_records_distinguish_complete_forfeit_from_success(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertEqual(readiness.check_records(folder), [])
            with self.assertRaisesRegex(ValueError, "Missing"):
                readiness.check_records(folder, 2)
            save_games(folder, [game(), game("p000001-2")])
            self.assertEqual(len(readiness.check_records(folder, 2)), 2)
            for changes in ({"termination": "time_forfeit"}, {"status": "truncated"},
                            {"status": "interrupted"}, {"unexpected_stderr": True}):
                save_games(folder, [game(**changes)])
                with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "Readiness failed"):
                    readiness.check_records(folder)
            save_games(folder, [game(), game("p000001-2"), game("extra")])
            with self.assertRaisesRegex(ValueError, "extra"):
                readiness.check_records(folder, 2)

    def test_cleanup_counts_unique_pids_and_fails_closed_on_permission_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            engines = {"candidate": {"pid": 101}, "opponent": {"pid": 102}}
            save_games(output / "shard-1", [game(engines=engines), game(engines=engines)])
            save_games(output / "shard-2", [game(engines={"candidate": {"pid": 103}})])

            def kill(pid, signal):
                self.assertEqual(signal, 0)
                if pid == 101:
                    raise ProcessLookupError
                if pid == 103:
                    raise PermissionError

            with patch.object(readiness.os, "kill", side_effect=kill) as observed:
                result = readiness.process_cleanup(output)
            self.assertEqual(observed.call_count, 3)
            self.assertEqual(result, {"engine_pids": [101, 102, 103],
                                      "alive_pids": [102], "unverified_pids": [103]})

    def test_snapshot_requires_both_frozen_binary_and_network(self):
        engine, network = Path("/engine"), Path("/network")
        for bad in (None, engine, network):
            def digest(path):
                if path == bad:
                    return "changed"
                if path == engine:
                    return readiness.ENGINE_SHA
                if path == network:
                    return readiness.NETWORK_SHA
                return "source-hash"

            with self.subTest(bad=bad), patch.object(readiness.match, "sha256", side_effect=digest):
                if bad is not None:
                    with self.assertRaisesRegex(ValueError, "changed"):
                        readiness.snapshot(engine, network)
                else:
                    result = readiness.snapshot(engine, network)
                    self.assertIn(readiness.PROTOCOL, result["source_hashes"])
                    self.assertEqual(len(result["source_hashes"]),
                                     len(readiness.SOURCES) + len(readiness.SUITES))


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.output = self.directory / "attempt"
        self.suites = tuple(self.directory / f"suite-{index}.json" for index in range(4))
        protocol = "protocol.md"
        (self.directory / protocol).write_text("Frozen test protocol.\n")
        self.initial = {
            "source_hashes": {path.name: f"suite-{index}-hash" for index, path in enumerate(self.suites)},
            "engine_sha256": readiness.ENGINE_SHA, "network_sha256": readiness.NETWORK_SHA}
        self.closed, self.started, self.calls = set(), set(), []
        self.all_started = asyncio.Event()
        self.mock("ROOT", self.directory)
        self.mock("SUITES", self.suites)
        self.mock("PROTOCOL", protocol)
        self.mock("TIMEOUT_SECONDS", 3)
        self.mock("POLL_SECONDS", 60)
        self.snapshot = self.mock("snapshot", return_value=self.initial)
        self.admission = self.mock("admission", return_value={"max_cpu_workers": 4})
        self.fingerprints = self.mock("fingerprints", return_value={"fixture": (1, 2, 3, 4, 5)})
        self.cleanup = self.mock("process_cleanup", return_value={
            "engine_pids": [], "alive_pids": [], "unverified_pids": []})

    def mock(self, name, *args, **kwargs):
        return self.stack.enter_context(patch.object(readiness, name, *args, **kwargs))

    def install_runner(self, action):
        async def fake(specs, settings, suite, folder, pairs, seed, *, before_game, fail_fast):
            self.started.add(suite)
            self.calls.append((specs, settings, suite, folder, pairs, seed, fail_fast))
            if len(self.started) == 4:
                self.all_started.set()
            try:
                await self.all_started.wait()
                await action(suite, folder, before_game)
            finally:
                # One yield models asynchronous process/persistence cleanup.
                await asyncio.sleep(0)
                self.closed.add(suite)
        return self.stack.enter_context(patch.object(readiness.match, "run_match", side_effect=fake))

    def evidence(self):
        return json.loads((self.output / "launcher.json").read_text())

    async def blocked(self, suite, folder, before_game):
        await asyncio.Future()

    async def successful(self, suite, folder, before_game):
        records = []
        for number in (1, 2):
            await before_game(f"p000001-{number}")
            records.append(game(f"p000001-{number}"))
            save_games(folder, records)

    async def test_all_four_shards_finish_two_games_and_recheck_every_boundary(self):
        self.install_runner(self.successful)
        result = await readiness.run(self.output)
        self.assertEqual(result["status"], "finished")
        self.assertTrue(result["integrity_unchanged"])
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(len(result["admissions"]), 8)
        self.assertEqual(self.admission.call_count, 9)
        self.assertEqual(self.snapshot.call_count, 2)
        self.assertEqual({call[2] for call in self.calls}, set(self.suites))
        self.assertEqual({call[5] for call in self.calls}, set(readiness.SEEDS))
        self.assertTrue(all(call[4] == 1 and call[6] for call in self.calls))
        self.assertEqual(self.evidence()["status"], "finished")

    async def test_existing_output_is_refused_before_hashes_resources_or_engines(self):
        self.output.mkdir()
        preserved = self.output / "evidence"
        preserved.write_text("keep")
        with patch.object(readiness.match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "previous attempt"):
                await readiness.run(self.output)
            runner.assert_not_awaited()
        self.snapshot.assert_not_called()
        self.admission.assert_not_called()
        self.assertEqual(preserved.read_text(), "keep")

    async def test_failed_admission_starts_no_shard_and_creates_no_attempt(self):
        self.admission.side_effect = ValueError("aggregate budget unavailable")
        with patch.object(readiness.match, "run_match", new_callable=AsyncMock) as runner:
            with self.assertRaisesRegex(ValueError, "aggregate budget"):
                await readiness.run(self.output)
            runner.assert_not_awaited()
        self.assertFalse(self.output.exists())

    async def test_child_failure_cancels_and_awaits_siblings_and_retains_failure(self):
        async def fail_one(suite, folder, before_game):
            if suite == self.suites[0]:
                save_games(folder, [game(status="interrupted", termination="synthetic failure")])
                raise RuntimeError("synthetic child failure")
            await asyncio.Future()

        self.install_runner(fail_one)
        with self.assertRaisesRegex(RuntimeError, "synthetic child failure"):
            await readiness.run(self.output)
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")
        self.assertIn("synthetic child failure", self.evidence()["error"])
        self.assertIn("synthetic failure", (self.output / "shard-1/games.jsonl").read_text())

    async def test_clock_forfeit_cannot_be_promoted_to_finished(self):
        async def forfeit(suite, folder, before_game):
            if suite == self.suites[0]:
                save_games(folder, [game(termination="time_forfeit"), game("p000001-2")])
            else:
                await asyncio.Future()

        self.install_runner(forfeit)
        with self.assertRaisesRegex(ValueError, "time_forfeit"):
            await readiness.run(self.output)
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")

    async def test_wall_deadline_keeps_failure_evidence_after_all_children_close(self):
        self.mock("TIMEOUT_SECONDS", .05)
        self.install_runner(self.blocked)
        with self.assertRaisesRegex(TimeoutError, "deadline"):
            await readiness.run(self.output)
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")
        self.assertIn("TimeoutError", self.evidence()["error"])

    async def test_caller_cancellation_keeps_ownership_until_cleanup_and_publication(self):
        self.install_runner(self.blocked)
        task = asyncio.create_task(readiness.run(self.output))
        await asyncio.wait_for(self.all_started.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")
        self.assertIn("CancelledError", self.evidence()["error"])

    async def test_final_hash_drift_invalidates_otherwise_complete_run(self):
        changed = copy.deepcopy(self.initial)
        changed["source_hashes"]["modified"] = "different"
        self.snapshot.side_effect = [self.initial, changed]
        self.install_runner(self.successful)
        with self.assertRaisesRegex(ValueError, "hash verification"):
            await readiness.run(self.output)
        self.assertFalse(self.evidence()["integrity_unchanged"])
        self.assertEqual(self.evidence()["status"], "incomplete")

    async def test_monitor_detects_input_drift_during_games(self):
        self.mock("POLL_SECONDS", .001)
        self.fingerprints.side_effect = [{"fixed": 1}, {"changed": 2}]
        self.install_runner(self.blocked)
        with self.assertRaisesRegex(ValueError, "Pinned inputs changed"):
            await readiness.run(self.output)
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")

    async def test_monitor_resource_revocation_cancels_running_shards(self):
        self.mock("POLL_SECONDS", .001)
        self.admission.side_effect = [{"max_cpu_workers": 4}, ValueError("aggregate budget revoked")]
        self.install_runner(self.blocked)
        with self.assertRaisesRegex(ValueError, "aggregate budget revoked"):
            await readiness.run(self.output)
        self.assertEqual(self.closed, set(self.suites))
        self.assertEqual(self.evidence()["status"], "incomplete")

    async def test_unverified_cleanup_invalidates_complete_games(self):
        self.cleanup.return_value = {"engine_pids": [42], "alive_pids": [], "unverified_pids": [42]}
        self.install_runner(self.successful)
        with self.assertRaisesRegex(ValueError, "cleanup could not be verified"):
            await readiness.run(self.output)
        self.assertEqual(self.evidence()["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
