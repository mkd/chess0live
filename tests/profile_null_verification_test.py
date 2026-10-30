#!/usr/bin/env python3
"""Engine-free validation/lifecycle checks for the fixed null-verification screen.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_null_verification as profile


def transcript(board, role):
    move = next(iter(board.legal_moves)).uci()
    lines = [f"info depth {depth} seldepth {depth} score cp 10 nodes {depth * 10} "
             f"time {depth} nps 10000 hashfull {depth} tbhits 0 pv {move}"
             for depth in range(1, 7)]
    lines += ["info nodes 60 time 6 nps 10000 hashfull 6 tbhits 0",
              "info string cache v1 entry_bytes 16 bucket_bytes 64 buckets 524288 "
              "capacity 2097152 allocated_bytes 33554432 probes 12 hits 5 cutoffs 3 stores 9 replacements 1"]
    lines += [f"info string search-iteration v1 depth {depth} completed true nodes 10 "
              f"duration_ms 1.000 elapsed_ms {depth}.000" for depth in range(1, 7)]
    lines += ["info string ordering v1 policy mvv-lva see_calls 0 losing_captures 0",
              "info string lmr v1 enabled true reductions 20 researches 8 fail_lows 3 verified_cutoffs 3"]
    if role.endswith("_on"):
        record = "info string nullmove v1 enabled true probes 3 fail_highs 2 verifications 2 cutoffs 1 rejected 1"
        if role.startswith("candidate_"):
            record += " probe_nodes 8 verification_nodes 10 verification_hints 1"
        lines.append(record)
    lines += ["info string search-summary v1 policy classic forecast_active false stop_reason depth_limit "
              "nodes 60 completed_depth 6 elapsed_ms 6.000 soft_ms 0.000 hard_ms 0.000 "
              "target_ms 0.000 predicted_next_ms 0.000", f"bestmove {move}"]
    return lines


def samples():
    return [{"stage": stage, "position_index": index, "temperature": temperature,
             "role": role, "status": "complete",
             "result": profile.validate_result(transcript(board, role), board, role)}
            for stage, roles in profile.STAGES.items()
            for index, position in enumerate(profile.POSITIONS)
            for board in [profile.board_for(position)]
            for role in roles for temperature in profile.TEMPERATURES]


class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.board = profile.board_for("startpos")

    def test_pinned_corpus_and_isolated_options(self):
        self.assertEqual(len(profile.POSITIONS), 3)
        self.assertEqual(hashlib.sha256(("\n".join(profile.POSITIONS) + "\n").encode()).hexdigest(),
                         profile.POSITIONS_SHA256)
        baseline = profile.options_for("parent_off", Path("network"))
        self.assertEqual(baseline, profile.options_for("candidate_off", Path("network")))
        for role in ("parent_on", "candidate_on"):
            options = profile.options_for(role, Path("network"))
            self.assertEqual(options.pop("Null Move Pruning"), "true")
            self.assertEqual(options, {k: v for k, v in baseline.items() if k != "Null Move Pruning"})
        self.assertEqual(baseline["Late Move Reductions"], "true")
        self.assertEqual(baseline["Search Diagnostics"], "true")
        self.assertEqual(baseline["Threads"], "1")
        self.assertEqual(baseline["Hash"], "64")
        for option in ("TT Move Hints", "Continuation History", "Countermove Ordering",
                       "Deep Quiet Reductions", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut"):
            self.assertEqual(baseline[option], "false")

    def test_all_roles_and_null_work_accounting(self):
        for role in sum(profile.STAGES.values(), ()):
            result = profile.validate_result(transcript(self.board, role), self.board, role)
            self.assertEqual(result["reported_nodes"], 60)
            self.assertEqual(result["lmr"]["enabled"], True)
            self.assertEqual(result["nullmove"]["enabled"], role.endswith("_on"))
            if role.startswith("parent_"):
                self.assertIsNone(result["nullmove"]["verification_nodes"])
            elif role.endswith("_on"):
                self.assertEqual(result["nullmove"]["verification_hints"], 1)

    def test_corrupt_records_fail(self):
        original = transcript(self.board, "candidate_on")
        move = original[-1].split()[1]
        replacements = {
            "illegal PV": ("pv " + move, "pv 0000"),
            "wrong depth": ("completed_depth 6", "completed_depth 5"),
            "wrong clock": ("soft_ms 0.000", "soft_ms 1.000"),
            "aborted": ("completed true", "completed false"),
            "LMR off": ("lmr v1 enabled true", "lmr v1 enabled false"),
            "SEE": ("policy mvv-lva", "policy see"),
            "tablebases": ("tbhits 0", "tbhits 1"),
            "bounds": ("score cp 10", "score cp 10 lowerbound"),
            "counter total": ("verification_nodes 10", "verification_nodes 60"),
            "unfinished null": ("rejected 1", "rejected 0"),
            "too many hints": ("verification_hints 1", "verification_hints 3"),
            "negative": ("probe_nodes 8", "probe_nodes -8"),
            "missing work": (" probe_nodes 8", ""),
            "duplicate work": ("probe_nodes 8", "probe_nodes 8 probe_nodes 8"),
        }
        for name, (before, after) in replacements.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                profile.validate_result([line.replace(before, after) for line in original], self.board, "candidate_on")
        for corrupt in (original + original[-1:], original[:1] + original,
                        ["info string unexpected v1 value 0"] + original,
                        [line for line in original if not line.startswith("info string nullmove ")]):
            with self.assertRaises(ValueError):
                profile.validate_result(corrupt, self.board, "candidate_on")

    def test_parent_does_not_silently_gain_candidate_schema(self):
        with self.assertRaises(ValueError):
            profile.validate_result(transcript(self.board, "candidate_on"), self.board, "parent_on")
        with self.assertRaises(ValueError):
            profile.validate_result(transcript(self.board, "parent_on"), self.board, "candidate_on")
        with self.assertRaises(ValueError):
            profile.validate_result(transcript(self.board, "candidate_on"), self.board, "candidate_off")

    def test_matrix_requires_every_unique_complete_cell(self):
        matrix = samples()
        self.assertEqual(len(matrix), 24)
        with self.assertRaises(ValueError):
            profile.summarize(matrix + [dict(matrix[0], stage="unexpected")], "parent_equivalence")
        for stage in profile.STAGES:
            selected = [sample for sample in matrix if sample["stage"] == stage]
            for corrupt in (selected[:-1], selected + selected[:1]):
                with self.assertRaises(ValueError):
                    profile.summarize(corrupt, stage)
            for field, value in (("status", "incomplete"), ("temperature", "unknown"), ("role", "unknown")):
                corrupt = copy.deepcopy(selected)
                corrupt[0][field] = value
                with self.assertRaises(ValueError):
                    profile.summarize(corrupt, stage)

    def test_summaries_preserve_parent_mismatches_and_decision_changes(self):
        matrix = samples()
        summary = profile.summarize(matrix, "parent_equivalence")
        self.assertFalse(summary["equivalence_mismatches"])
        self.assertEqual(summary["total_nodes_by_temperature"]["warm"]["candidate_off"], 180)
        row = next(sample for sample in matrix if sample["role"] == "candidate_off")
        row["result"]["signature"]["iterations"][0]["seldepth"] += 1
        self.assertEqual(len(profile.summarize(matrix, "parent_equivalence")["equivalence_mismatches"]), 1)
        row = next(sample for sample in matrix if sample["role"] == "candidate_on")
        row["result"]["signature"]["iterations"][0]["score"]["value"] += 1
        summary = profile.summarize(matrix, "verification_work")
        self.assertEqual(len(summary["pairs"][0]["iteration_differences"]), 1)
        self.assertEqual(summary["null_counters_by_temperature"]["cold"]["candidate_on"]["verification_hints"], 3)
        self.assertIsNone(summary["null_counters_by_temperature"]["cold"]["parent_on"]["verification_nodes"])

    def test_timing_excluded_from_parity(self):
        a = transcript(self.board, "parent_off")
        b = [line.replace("time 6", "time 60").replace("nps 10000", "nps 1000") for line in a]
        left = profile.validate_result(a, self.board, "parent_off")
        right = profile.validate_result(b, self.board, "candidate_off")
        self.assertEqual(left["signature"], right["signature"])


class ResourceChecks(unittest.TestCase):
    def test_one_worker_and_missing_or_excess_memory(self):
        network = Mock()
        network.stat.return_value = SimpleNamespace(st_size=98511183)
        for workers, memory, accepted in ((1, 64 * 1024**3, True), (0, 64 * 1024**3, False),
                                           (1, None, False), (1, 128 * 1024**2, False)):
            with self.subTest(workers=workers, memory=memory), \
                    patch.object(profile, "current_budget", return_value={"max_cpu_workers": workers, "memory_fraction": .5}), \
                    patch.object(profile, "physical_memory", return_value=memory):
                if accepted:
                    result = profile.resource_check(network)
                    self.assertEqual((result["active_search_workers"], result["resident_engines"]), (1, 1))
                else:
                    with self.assertRaises(ValueError):
                        profile.resource_check(network)


class LifecycleChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {name: self.root / name for name in ("parent", "candidate", "network", "protocol")}
        for name, path in self.paths.items():
            path.write_text(name)
        self.output = self.root / "screen.json"
        self.instances = []
        self.fail_search = False
        self.mismatch = False
        self.drift = False
        self.bad_exit = False
        owner = self

        class FakeEngine:
            def __init__(self, path):
                self.candidate = path.resolve() == owner.paths["candidate"].resolve()
                self.commands = []
                self.transcript = []
                self.lines = queue.Queue()
                self.process = SimpleNamespace(pid=100 + len(owner.instances), returncode=None)
                self.reader = Mock()
                self.reader.is_alive.return_value = False
                self.options = {}
                self.position = "startpos"
                self.setup = True
                owner.instances.append(self)

            def send(self, command):
                self.commands.append(command)
                if command.startswith("setoption name "):
                    name, value = command[len("setoption name "):].split(" value ")
                    self.options[name] = value
                elif command.startswith("position "):
                    self.position = command[len("position "):]

            def until(self, prefix, timeout):
                if prefix == "uciok":
                    output = [f"option name {name} type string default ignored"
                              for name in profile.options_for("parent_off", owner.paths["network"])] + ["uciok"]
                elif prefix == "readyok":
                    output = (["info string Syzygy largest 0 pieces; table files are external"] if self.setup else []) + ["readyok"]
                    self.setup = False
                else:
                    role = ("candidate_" if self.candidate else "parent_") + ("on" if self.options["Null Move Pruning"] == "true" else "off")
                    output = transcript(profile.board_for(self.position), role)
                    if owner.fail_search:
                        self.transcript.extend(output[:1])
                        raise TimeoutError("synthetic response timeout")
                    if owner.mismatch and self.candidate:
                        output = [line.replace("score cp 10", "score cp 11") for line in output]
                    if owner.drift:
                        owner.paths["candidate"].write_text("changed artifact")
                self.transcript.extend(output)
                return output

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.commands.append("quit")
                self.process.returncode = 2 if owner.bad_exit else 0
                self.lines.put(None)

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (("ROOT", self.root), ("PROTOCOL", self.paths["protocol"]), ("SOURCES", ()),
                            ("NETWORK_SHA256", profile.digest(self.paths["network"])),
                            ("PARENT_SHA256", profile.digest(self.paths["parent"])), ("Engine", FakeEngine)):
            self.stack.enter_context(patch.object(profile, name, value))
        self.stack.enter_context(patch.object(profile, "resource_check", return_value={"active_search_workers": 1}))

    def run_profile(self):
        return profile.profile(self.paths["parent"], self.paths["candidate"], self.paths["network"], self.output,
                               parent_sha256=profile.digest(self.paths["parent"]),
                               candidate_sha256=profile.digest(self.paths["candidate"]), host_load="lm-studio-running")

    def test_complete_lifecycle_frozen_order_warm_state_cleanup(self):
        result = self.run_profile()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["samples"]), 24)
        self.assertEqual(len(self.instances), 12)
        self.assertEqual([s["role"] for s in result["sessions"][:6]],
                         ["parent_off", "candidate_off", "candidate_off", "parent_off", "parent_off", "candidate_off"])
        for engine, session in zip(self.instances, result["sessions"]):
            self.assertEqual(engine.commands.count("ucinewgame"), 1)
            self.assertEqual(engine.commands.count("go depth 6"), 2)
            self.assertEqual(session["exit_code"], 0)
            self.assertEqual(session["shutdown_eof_count"], 1)
            self.assertIsInstance(session["pid"], int)
        self.assertEqual(json.loads(self.output.read_text())["status"], "complete")

    def test_existing_output_is_never_overwritten(self):
        self.output.write_text("previous evidence")
        with self.assertRaises(FileExistsError):
            self.run_profile()
        self.assertEqual(self.output.read_text(), "previous evidence")
        self.assertFalse(self.instances)

    def test_partial_search_failure_preserves_evidence_and_stops(self):
        self.fail_search = True
        with self.assertRaises(TimeoutError):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(result["status"], "invalid_or_interrupted")
        self.assertEqual(len(result["samples"]), 1)
        self.assertEqual(len(result["samples"][0]["output"]), 1)
        self.assertEqual(result["sessions"][0]["exit_code"], 0)
        self.assertEqual(len(self.instances), 1)

    def test_parent_mismatch_blocks_second_stage_and_retains_differences(self):
        self.mismatch = True
        with self.assertRaisesRegex(ValueError, "candidate stage is blocked"):
            self.run_profile()
        result = json.loads(self.output.read_text())
        self.assertEqual(len(result["samples"]), 12)
        self.assertEqual(len(self.instances), 6)
        self.assertTrue(result["summaries"]["parent_equivalence"]["equivalence_mismatches"])

    def test_artifact_drift_and_bad_exit_are_invalid(self):
        self.drift = True
        with self.assertRaisesRegex(ValueError, "artifacts changed"):
            self.run_profile()
        self.assertIn("candidate", json.loads(self.output.read_text())["artifact_drift"])
        self.output = self.root / "bad-exit.json"
        self.drift = False
        self.bad_exit = True
        with self.assertRaisesRegex(ValueError, "exited unsuccessfully"):
            self.run_profile()
        self.assertEqual(json.loads(self.output.read_text())["status"], "invalid_or_interrupted")

    def test_wrong_pin_and_host_declaration_never_start_engine(self):
        for host, pin in (("quiet", profile.digest(self.paths["parent"])), ("lm-studio-running", "0" * 64)):
            with self.assertRaises(ValueError):
                profile.profile(self.paths["parent"], self.paths["candidate"], self.paths["network"], self.output,
                                parent_sha256=pin, candidate_sha256=profile.digest(self.paths["candidate"]), host_load=host)
        self.assertFalse(self.instances)
        self.assertFalse(self.output.exists())

    def test_final_cleanup_hashing_and_publication_obey_whole_screen_deadline(self):
        original_finish, original_digest, original_publish = profile.finish_session, profile.digest, profile.publish
        for phase in ("cleanup", "hashing", "publication"):
            with self.subTest(phase=phase):
                self.instances.clear()
                self.output = self.root / (phase + ".json")
                clock = [0.0]

                def finished():
                    return len(self.instances) == 12 and all(engine.process.returncode == 0 for engine in self.instances)

                def finish(engine, session):
                    original_finish(engine, session)
                    if phase == "cleanup" and finished():
                        clock[0] = 601.0

                def digest(path):
                    result = original_digest(path)
                    if phase == "hashing" and finished():
                        clock[0] = 601.0
                    return result

                def publish(path, report):
                    original_publish(path, report)
                    if phase == "publication" and report["status"] == "complete":
                        clock[0] = 601.0

                with patch.object(profile.time, "monotonic", side_effect=lambda: clock[0]), \
                        patch.object(profile, "finish_session", side_effect=finish), \
                        patch.object(profile, "digest", side_effect=digest), \
                        patch.object(profile, "publish", side_effect=publish):
                    with self.assertRaises(TimeoutError):
                        self.run_profile()
                result = json.loads(self.output.read_text())
                self.assertEqual(result["status"], "invalid_or_interrupted")
                self.assertTrue(result["deadline_exceeded"])
                self.assertEqual(result["elapsed_seconds"], 601.0)
                self.assertEqual(len(result["samples"]), 24)
                self.assertEqual(len(result["after_sha256"]), 4)
                self.assertTrue(all(session["exit_code"] == 0 for session in result["sessions"]))


if __name__ == "__main__":
    unittest.main()
