#!/usr/bin/env python3
"""Test cache accounting, legal evidence, and profiler lifecycle with fake UCI.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_cache as profiler


def reply(position="startpos", depth=2, hash_mb=64, warm=False,
          entry_bytes=16, bucket_bytes=64):
    board = profiler.board_for(position)
    move = next(iter(board.legal_moves)).uci()
    board.push_uci(move)
    ponder = next(iter(board.legal_moves)).uci()
    lines, increment = [], 20 if warm else 40
    for iteration in range(1, depth + 1):
        lines += [f"info depth {iteration} seldepth {iteration + 1} score cp 20 nodes {iteration * increment} time {iteration} nps 40000 hashfull {iteration * 4} pv {move} {ponder}",
                  f"info string search-iteration v1 depth {iteration} completed true nodes {increment} duration_ms 1.000 elapsed_ms {iteration}.000"]
    fitting = hash_mb * 1024**2 // 96
    buckets = 1 << (fitting.bit_length() - 1)
    probes = depth * increment
    lines += [f"info string cache v1 entry_bytes {entry_bytes} bucket_bytes {bucket_bytes} buckets {buckets} capacity {buckets * 4} allocated_bytes {buckets * bucket_bytes} probes {probes} hits 10 cutoffs 5 stores {probes - 5} replacements 2",
              f"info string search-summary v1 policy classic forecast_active false stop_reason depth_limit nodes {depth * increment} completed_depth {depth} elapsed_ms {depth}.000 soft_ms 0.000 hard_ms 0.000 target_ms 0.000 predicted_next_ms 0.000",
              f"bestmove {move} ponder {ponder}"]
    return lines


class ParserTests(unittest.TestCase):
    def check(self, lines, hash_mb=64):
        return profiler.validate_result(lines, profiler.board_for("startpos"), 2, hash_mb)

    def test_valid_cache_and_every_iteration_hashfull(self):
        result = self.check(reply())
        self.assertEqual(result["cache"]["allocated_bytes"], 32 * 1024**2)
        self.assertEqual(result["hashfull"], [{"depth": 1, "hashfull": 4}, {"depth": 2, "hashfull": 8}])
        self.assertEqual(result["signature"]["iterations"][-1]["nodes"], 80)

    def test_bad_cache_schema_numbers_and_counter_relations(self):
        for before, after in (("cache v1", "cache v2"), ("entry_bytes 16", "hits 16"),
                              ("probes 80", "probes -1"), ("hits 10", "hits 101"),
                              ("cutoffs 5", "cutoffs 11"), ("replacements 2", "replacements 76"),
                              ("stores 75", "stores 18446744073709551616"),
                              ("stores 75", "stores ７５"), ("stores 75", "stores nan")):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                self.check([line.replace(before, after) for line in reply()])

    def test_completed_search_cache_partitions_match_probes_and_nodes(self):
        changes = [lambda line: line.replace("stores 75", "stores 74"),
                   lambda line: line.replace("probes 80", "probes 81").replace("stores 75", "stores 76")]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Completed search cache"):
                self.check([change(line) for line in reply()])

    def test_invalid_table_geometry_and_reserved_memory(self):
        for before, after in (("entry_bytes 16", "entry_bytes 17"), ("entry_bytes 16", "entry_bytes 0"),
                              ("buckets 524288", "buckets 524287"),
                              ("capacity 2097152", "capacity 2097151"),
                              ("allocated_bytes 33554432", "allocated_bytes 33554431")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.check([line.replace(before, after) for line in reply()])
        with self.assertRaises(ValueError):
            self.check(reply(), hash_mb=1)
        with self.assertRaises(ValueError):
            self.check(reply(hash_mb=1, entry_bytes=64, bucket_bytes=256), hash_mb=1)

    def test_old_and_compact_layouts_preserve_bucket_count_for_nonpower_hash_sizes(self):
        for hash_mb in (1, 3, 5, 64):
            with self.subTest(hash_mb=hash_mb):
                old = self.check(reply(hash_mb=hash_mb, entry_bytes=24, bucket_bytes=96), hash_mb)["cache"]
                compact = self.check(reply(hash_mb=hash_mb), hash_mb)["cache"]
                self.assertEqual(old["buckets"], compact["buckets"])
                self.assertEqual(old["capacity"], compact["capacity"])
                self.assertEqual(old["allocated_bytes"] * 2, compact["allocated_bytes"] * 3)
                self.assertLessEqual(compact["allocated_bytes"], hash_mb * 1024**2)
        # A compact 64-byte bucket does not expand capacity to fill Hash; doing
        # so changes indexing/replacement and invalidates this fixed-count test.
        changed = [line.replace("buckets 524288", "buckets 1048576")
                   .replace("capacity 2097152", "capacity 4194304")
                   .replace("allocated_bytes 33554432", "allocated_bytes 67108864")
                   for line in reply()]
        with self.assertRaisesRegex(ValueError, "byte accounting"):
            self.check(changed)

    def test_hashfull_rejects_missing_duplicate_negative_and_overfull(self):
        for before, after in ((" hashfull 4", ""), ("hashfull 4", "hashfull 1001"),
                              ("hashfull 4", "hashfull -1"), ("hashfull 4", "hashfull 4.0"),
                              ("hashfull 4", "hashfull 4 hashfull 4")):
            with self.subTest(after=after), self.assertRaises(ValueError):
                self.check([line.replace(before, after) for line in reply()])
        for value in (0, 1000):
            self.check([line.replace("hashfull 4", f"hashfull {value}") for line in reply()])

    def test_missing_duplicate_or_misordered_cache_fails(self):
        lines = reply()
        cases = [lines[:-3] + lines[-2:], lines[:-3] + [lines[-3]] + lines[-3:],
                 lines[:-3] + [lines[-2], lines[-3], lines[-1]],
                 lines + ["info string cache v1"], lines + ["info string error: rejected"]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.check(case)

    def test_search_errors_limits_and_accounting_fail_closed(self):
        for before, after in (("stop_reason depth_limit", "stop_reason external_stop"),
                              ("completed_depth 2", "completed_depth 1"),
                              ("nodes 80 completed_depth", "nodes 81 completed_depth"),
                              ("depth 2 seldepth", "depth 3 seldepth")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                self.check([line.replace(before, after) for line in reply()])

    def test_bestmove_ponder_and_every_pv_are_independently_legal(self):
        lines = reply()
        for changed in (lines[:-1] + ["bestmove e2e5"],
                        lines[:-1] + [lines[-1].split(" ponder")[0] + " ponder e2e4"],
                        [line.replace("pv g1h3 g8h6", "pv g1h3 e2e4") for line in lines],
                        [line.replace("pv g1h3 g8h6", "pv e2e5 g8h6") for line in lines]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.check(changed)

    def test_referee_version_roots_and_no_heldout_inputs(self):
        for position in ("startpos moves e2e5", "startpos\nquit", "bogus", "startpos wrong e2e4",
                         "startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                profiler.board_for(position)
        with patch.object(profiler, "chess", None), self.assertRaisesRegex(ValueError, "chess==1.11.2"):
            profiler.board_for("startpos")
        with self.assertRaisesRegex(ValueError, "held-out"):
            profiler.positions_from("phase3l")
        self.assertEqual(len(profiler.positions_from("bench")[0]), 3)
        positions, path = profiler.positions_from("gamephases")
        self.assertEqual(len(positions), 12)
        self.assertEqual(path.name, "performance-gamephases.json")
        for position in positions:
            profiler.board_for(position["position"])


class FakeEngine:
    instances = []
    failure = None
    mutate = None

    def __init__(self, path):
        self.sent, self.transcript = [], []
        self.position, self.depth, self.hash_mb, self.searches = "startpos", 2, 64, 0
        self.closed = False
        self.instances.append(self)

    def send(self, command):
        self.sent.append(command)
        if command.startswith("position "):
            self.position = command[len("position "):]
        elif command.startswith("go depth "):
            self.depth = int(command.split()[-1])
        elif command.startswith("setoption name Hash "):
            self.hash_mb = int(command.split()[-1])
        elif command == "ucinewgame":
            self.searches = 0

    def until(self, prefix, timeout=30):
        if prefix == "uciok":
            names = ("Hash", "Threads", "EvalFile", "Ponder", "Move Overhead", "Time Policy",
                     "Search Diagnostics", "Late Move Reductions", "Capture Ordering")
            lines = [f"option name {name} type string" for name in names if self.failure != "option" or name != "Hash"] + ["uciok"]
            if self.failure == "handshake":
                self.transcript.append("id name incomplete")
                raise TimeoutError("Injected handshake timeout")
        elif prefix == "readyok":
            lines = ["info string error: illegal position", "readyok"] if self.failure == "position" and "ucinewgame" in self.sent else ["readyok"]
        else:
            lines = reply(self.position, self.depth, self.hash_mb, warm=self.searches > 0)
            self.searches += 1
            if self.failure == "timeout":
                self.transcript.extend(lines[:1])
                raise TimeoutError("Injected search timeout")
            if self.failure == "cache":
                lines = [line.replace("hits 10", "hits 1001") for line in lines]
            if self.mutate:
                self.mutate.write_text("changed input")
        self.transcript.extend(lines)
        return lines

    def __enter__(self): return self
    def __exit__(self, *_): self.closed = True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-cache-profile-")
        self.root = Path(self.temporary.name)
        self.binary, self.network, self.output = [self.root / name for name in ("engine", "network", "profile.json")]
        self.binary.write_text("fake engine")
        self.network.write_text("fake network")
        FakeEngine.instances, FakeEngine.failure, FakeEngine.mutate = [], None, None
        self.budget = {"max_cpu_workers": 1, "memory_fraction": .5}
        self.patches = [patch.object(profiler, "Engine", FakeEngine),
                        patch.object(profiler, "NETWORK_SHA256", profiler.digest(self.network)),
                        patch.object(profiler, "NETWORK_BYTES", self.network.stat().st_size),
                        patch.object(profiler, "current_budget", return_value=self.budget),
                        patch.object(profiler, "physical_memory", return_value=8 * 1024**3)]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self): self.temporary.cleanup()

    def run_profile(self, **kwargs):
        return profiler.profile(self.binary, self.network, self.output, depth=2, **kwargs)

    def test_cold_warm_preserves_history_and_every_raw_record(self):
        result = self.run_profile()
        self.assertEqual(result["status"], "complete")
        self.assertEqual([sample["state"] for sample in result["samples"]], ["cold", "warm"] * 3)
        self.assertEqual(len(result["summary"]), 3)
        self.assertEqual(result["summary"][0]["nodes_cold_warm"], [80, 40])
        self.assertFalse(result["summary"][0]["same_signature"])
        self.assertTrue(result["summary"][0]["same_bestmove"])
        for sample in result["samples"]:
            self.assertEqual("ucinewgame" in sample["preparation_commands"], sample["state"] == "cold")
            self.assertEqual(sample["output"], reply(result["positions"][sample["position_index"]]["position"], warm=sample["state"] == "warm"))
        self.assertEqual(result["protocol_output"], FakeEngine.instances[0].transcript)
        self.assertEqual(result["commands"], FakeEngine.instances[0].sent)
        self.assertTrue(FakeEngine.instances[0].closed)
        self.assertEqual(result["assets"]["binary"]["sha256"], result["after_sha256"]["binary"])
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")

    def test_existing_outputs_and_stale_temporary_files_are_not_overwritten(self):
        for path in (self.output, self.output.with_suffix(".json.tmp")):
            with self.subTest(path=path):
                path.write_text("preserve me")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    self.run_profile()
                self.assertEqual(path.read_text(), "preserve me")
                self.assertFalse(FakeEngine.instances)
                path.unlink()

    def test_failure_records_preserve_partial_search_and_close_process(self):
        for failure, expected in (("timeout", TimeoutError), ("cache", ValueError), ("handshake", TimeoutError)):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(expected):
                    self.run_profile()
                result = json.loads(self.output.read_text())
                self.assertEqual(result["status"], "invalid_or_interrupted")
                self.assertNotIn("summary", result)
                self.assertTrue(result["protocol_output"])
                if failure == "timeout":
                    self.assertEqual(len(result["samples"][-1]["output"]), 1)
                self.assertTrue(FakeEngine.instances[-1].closed)
                self.output.unlink()

    def test_position_error_or_missing_option_prevents_search(self):
        for failure in ("position", "option"):
            with self.subTest(failure=failure):
                FakeEngine.failure = failure
                with self.assertRaises(ValueError):
                    self.run_profile()
                self.assertFalse(any(command.startswith("go ") for command in FakeEngine.instances[-1].sent))
                self.assertEqual(json.loads(self.output.read_text())["status"], "invalid_or_interrupted")
                self.output.unlink()

    def test_wrong_network_or_requested_binary_pin_prevents_startup(self):
        with self.assertRaisesRegex(ValueError, "requested SHA-256"):
            self.run_profile(expected_engine_sha256="0" * 64)
        self.network.write_text("different net")
        with self.assertRaisesRegex(ValueError, "pinned SF19"):
            self.run_profile()
        self.assertFalse(FakeEngine.instances)
        self.assertFalse(self.output.exists())

    def test_input_mutation_invalidates_and_stops_before_warm_search(self):
        for artifact in (self.binary, self.network):
            with self.subTest(artifact=artifact):
                original = artifact.read_bytes()
                FakeEngine.mutate = artifact
                with self.assertRaisesRegex(ValueError, "artifact changed"):
                    self.run_profile()
                result = json.loads(self.output.read_text())
                self.assertEqual(result["status"], "invalid_or_interrupted")
                self.assertEqual(len(result["samples"]), 1)
                self.assertNotIn("summary", result)
                self.assertTrue(FakeEngine.instances[-1].closed)
                artifact.write_bytes(original)
                self.output.unlink()

    def test_live_resource_override_stops_before_next_search(self):
        with patch.object(profiler, "current_budget", side_effect=[self.budget, self.budget, {"max_cpu_workers": 0, "memory_fraction": .5}]):
            with self.assertRaisesRegex(ValueError, "local budget"):
                self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(result["status"], "invalid_or_interrupted")

    def test_low_initial_memory_admission_does_not_start_an_engine(self):
        with patch.object(profiler, "physical_memory", return_value=1024):
            with self.assertRaisesRegex(ValueError, "local budget"):
                self.run_profile()
        self.assertFalse(FakeEngine.instances)
        self.assertFalse(self.output.exists())

    def test_invalid_bounds_fail_before_startup(self):
        for kwargs in ({"hash_mb": 0}, {"hash_mb": 1025}, {"hash_mb": True},
                       {"search_timeout": float("nan")}, {"search_timeout": 121},
                       {"total_timeout": 0}, {"total_timeout": 301}, {"suite": "phase3l"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_profile(**kwargs)
        self.assertFalse(FakeEngine.instances)

    def test_total_time_allowance_is_bounded_and_failure_is_recorded(self):
        with patch.object(profiler.time, "monotonic", side_effect=[0., 1000.]):
            with self.assertRaisesRegex(TimeoutError, "total time"):
                self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(result["samples"], [])
        self.assertTrue(FakeEngine.instances[-1].closed)


if __name__ == "__main__":
    unittest.main()
