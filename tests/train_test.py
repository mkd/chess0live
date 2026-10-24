#!/usr/bin/env python3
"""Check training recipes, resource admission and report trust boundaries.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Orchestration cases use explicit synthetic worker reports. They do not execute
a trainer, establish arithmetic compatibility or qualify playing strength.
"""
from argparse import Namespace
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import train as tool
import training_setup


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="training checks ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "dataset with spaces.binpack"
        self.data.write_bytes(b"Synthetic identity fixture; not training data")
        self.options = Namespace(data=self.data, source=None, license=None,
            games=None, positions=None, parent=None, steps=2, batch_size=16,
            threads=1, seed=42, max_seconds=600)
        self.recipe = tool.create_recipe(self.options)
        self.recipe_file = self.root / "recipe.json"
        self.recipe_file.write_text(json.dumps(self.recipe))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "tools/train.py"),
                               *map(str, args)], capture_output=True, text=True, timeout=15)


class RecipeTests(Fixture):
    def test_recipe_binds_exact_input_and_unknown_counts(self):
        self.assertEqual(self.recipe["data"]["file"], tool.file_identity(self.data))
        self.assertIsNone(self.recipe["data"]["games"])
        self.assertIsNone(self.recipe["data"]["positions"])
        self.assertEqual(self.recipe["architecture"], "SFNNv16")
        self.assertEqual(tool.load_recipe(self.recipe_file), self.recipe)

    def test_zero_counts_remain_known_zero(self):
        self.options.games = self.options.positions = 0
        recipe = tool.create_recipe(self.options)
        self.assertEqual(recipe["data"]["games"], 0)
        self.assertEqual(recipe["data"]["positions"], 0)

    def test_changed_data_is_detected(self):
        self.data.write_bytes(b"changed bytes")
        with self.assertRaisesRegex(tool.TrainingError, "changed"):
            tool.verify_inputs(self.recipe)

    def test_parent_weights_are_bound_and_checked(self):
        parent = self.root / "parent.nnue"
        parent.write_bytes(b"Identity fixture only")
        self.options.parent = parent
        recipe = tool.create_recipe(self.options)
        self.assertEqual(recipe["parent"], tool.file_identity(parent))
        parent.write_bytes(b"replacement weights")
        with self.assertRaises(tool.TrainingError):
            tool.verify_inputs(recipe)

    def test_pickle_parent_is_rejected(self):
        parent = self.root / "untrusted.ckpt"
        parent.write_bytes(b"not deserialized")
        self.options.parent = parent
        with self.assertRaisesRegex(tool.TrainingError, "pickle"):
            tool.create_recipe(self.options)

    def test_missing_empty_and_nonfile_inputs_fail(self):
        empty = self.root / "empty.binpack"
        empty.touch()
        for path in (empty, self.root, self.root / "missing"):
            with self.subTest(path=path), self.assertRaises(tool.TrainingError):
                tool.file_identity(path)

    def test_trainer_architecture_and_extra_fields_fail(self):
        for name, value in (("trainer_commit", "0" * 40), ("architecture", "future"), ("command", "echo bad")):
            changed = copy.deepcopy(self.recipe)
            changed[name] = value
            with self.subTest(name=name), self.assertRaises(tool.TrainingError):
                tool.validate_recipe(changed)

    def test_version_must_be_integer_one(self):
        for value in (True, 2, "1", None):
            changed = copy.deepcopy(self.recipe)
            changed["schema_version"] = value
            with self.subTest(value=value), self.assertRaises(tool.TrainingError):
                tool.validate_recipe(changed)

    def test_training_count_and_seed_boundaries(self):
        for name in ("steps", "batch_size", "threads", "max_seconds"):
            for value in (True, 0, -1, 1.5, "2"):
                changed = copy.deepcopy(self.recipe)
                changed["training"][name] = value
                with self.subTest(name=name, value=value), self.assertRaises(tool.TrainingError):
                    tool.validate_recipe(changed)
        for value in (True, -1, 2 ** 32):
            changed = copy.deepcopy(self.recipe)
            changed["training"]["seed"] = value
            with self.subTest(seed=value), self.assertRaises(tool.TrainingError):
                tool.validate_recipe(changed)

    def test_batch_size_is_bounded_for_memory_admission(self):
        changed = copy.deepcopy(self.recipe)
        changed["training"]["batch_size"] = 1024
        self.assertEqual(tool.validate_recipe(changed)["training"]["batch_size"], 1024)
        changed["training"]["batch_size"] = 1025
        with self.assertRaisesRegex(tool.TrainingError, "batch_size"):
            tool.validate_recipe(changed)

    def test_declared_counts_reject_bools_and_negatives(self):
        for name in ("games", "positions"):
            for value in (True, -1, 1.5, "12"):
                changed = copy.deepcopy(self.recipe)
                changed["data"][name] = value
                with self.subTest(name=name, value=value), self.assertRaises(tool.TrainingError):
                    tool.validate_recipe(changed)

    def test_invalid_file_identity_is_explicit(self):
        for value in (None, {}, {"path": "relative", "size_bytes": 1, "sha256": "0" * 64}):
            changed = copy.deepcopy(self.recipe)
            changed["data"]["file"] = value
            with self.subTest(value=value), self.assertRaises(tool.TrainingError):
                tool.validate_recipe(changed)

    def test_nonhex_digest_and_unknown_gpu_are_rejected(self):
        changed = copy.deepcopy(self.recipe)
        changed["data"]["file"]["sha256"] = "x" * 64
        with self.assertRaises(tool.TrainingError):
            tool.validate_recipe(changed)
        changed = copy.deepcopy(self.recipe)
        changed["training"]["device"] = "mps"
        with self.assertRaises(tool.TrainingError):
            tool.validate_recipe(changed)

    def test_init_preserves_existing_recipe(self):
        old = self.recipe_file.read_bytes()
        result = self.cli("init", "--data", self.data, "--output", self.recipe_file)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.recipe_file.read_bytes(), old)

    def test_plan_is_read_only_and_distinguishes_requested_samples(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        result = self.cli("plan", self.recipe_file)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["requested_samples"], 32)
        self.assertIn("nothing is downloaded", report["note"])
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")))

    def test_changed_input_prevents_plan(self):
        self.data.write_bytes(b"changed")
        result = self.cli("plan", self.recipe_file)
        self.assertNotEqual(result.returncode, 0)


class ResourceTests(Fixture):
    def check(self, *, hour=12, minute=0, workers=9, fraction=.5, memory=64 * 1024 ** 3,
              short=False, override=False):
        config = dict(self.recipe["training"])
        if not short:
            config.update(steps=100, batch_size=128)
        policy = {"local_time": f"2026-10-24T{hour:02}:{minute:02}:00+03:00",
                  "max_cpu_workers": workers, "memory_fraction": fraction}
        with mock.patch.object(tool, "current_budget", return_value=policy), \
                mock.patch.object(tool, "total_memory", return_value=memory):
            return tool.resource_check(config, override)

    def test_daytime_long_run_requires_explicit_exception(self):
        with self.assertRaisesRegex(tool.TrainingError, "23:00"):
            self.check()
        report = self.check(override=True)
        self.assertTrue(report["daytime_override"])
        self.assertEqual(report["timeout_seconds"], 600)

    def test_short_smoke_is_admitted_by_day(self):
        self.assertTrue(self.check(short=True)["bounded_smoke"])

    def test_night_boundary_caps_a_long_run(self):
        self.assertEqual(self.check(hour=6, minute=59)["timeout_seconds"], 60)
        self.assertEqual(self.check(hour=23)["timeout_seconds"], 600)

    def test_reader_decompress_feature_and_prefetch_threads_are_counted(self):
        with self.assertRaisesRegex(tool.TrainingError, "loader"):
            self.check(short=True, workers=4)
        self.assertEqual(self.check(short=True, workers=5)["cpu_workers"], 5)

    def test_memory_reservation_is_checked(self):
        with self.assertRaisesRegex(tool.TrainingError, "memory"):
            self.check(short=True, memory=8 * 1024 ** 3)

    def test_missing_memory_probe_cannot_bypass_admission(self):
        with self.assertRaises(tool.TrainingError):
            self.check(short=True, memory=None)


class SourceTests(Fixture):
    def test_offline_missing_cache_cannot_fetch(self):
        with mock.patch.object(tool, "run_command") as run:
            with self.assertRaisesRegex(tool.TrainingError, "Offline"):
                tool.ensure_source(self.root / "cache", True, io.BytesIO(), 0)
            run.assert_not_called()

    def test_wrong_revision_and_dirty_cache_are_preserved(self):
        source = self.root / "source" / tool.trainer_manifest()["commit"]
        source.mkdir(parents=True)
        marker = source / "user-marker"
        marker.write_text("preserve")
        for outputs in ((b"wrong\n", b""), (tool.trainer_manifest()["commit"].encode(), b" M model.py\n")):
            with mock.patch.object(tool, "run_command", side_effect=outputs):
                with self.assertRaisesRegex(tool.TrainingError, "cache changed"):
                    tool.ensure_source(self.root, True, io.BytesIO(), 0)
            self.assertEqual(marker.read_text(), "preserve")


@unittest.skipUnless(os.name == "posix", "Current training qualification is POSIX-only")
class QualificationCancellationTests(Fixture):
    def test_timeout_unwinds_nested_separate_session_and_records_failure(self):
        script = self.root / "nested oracle.py"
        script.write_text(textwrap.dedent(f"""\
            import json, os, sys, time
            from pathlib import Path
            sys.path.insert(0, {str(ROOT / 'tools')!r})
            import network
            import verify_nnue
            root = Path(__file__).parent
            role = sys.argv[1]
            if role == "native":
                (root / "native.pid").write_text(str(os.getpid()))
                print("native started", flush=True)
                time.sleep(60)
            else:
                status = "passed"
                try:
                    if role == "wrapper":
                        result = network.run_oracle([sys.executable, __file__, "harness"])
                        if result.returncode:
                            raise RuntimeError("harness failed")
                    else:
                        with verify_nnue.interruption_cleanup(), (root / "native.log").open("wb") as log:
                            verify_nnue.run([sys.executable, __file__, "native"], log, timeout=60)
                except BaseException:
                    status = "failed"
                    print(role + " failed", flush=True)
                finally:
                    (root / (role + ".json")).write_text(json.dumps({{"status": status}}))
                sys.exit(0 if status == "passed" else 1)
            """))

        def reap_if_regression():
            pid_file = self.root / "native.pid"
            if pid_file.exists():
                try:
                    os.killpg(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        self.addCleanup(reap_if_regression)
        log = io.BytesIO()
        with self.assertRaises(subprocess.TimeoutExpired):
            tool.run_qualification([sys.executable, script, "wrapper"], log, timeout=1)
        self.assertTrue((self.root / "native.pid").exists(), "Test must reach the native child")
        native_pid = int((self.root / "native.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(native_pid, 0)
        for role in ("wrapper", "harness"):
            self.assertEqual(json.loads((self.root / (role + ".json")).read_text())["status"], "failed")
        self.assertIn(b"native started", (self.root / "native.log").read_bytes())
        self.assertIn(b"wrapper failed", log.getvalue())

    def test_success_inherits_lock_and_preserves_output(self):
        with self.data.open("rb") as lock:
            code = "import os,sys; os.fstat(int(sys.argv[1])); print('done'); print('detail', file=sys.stderr)"
            log = io.BytesIO()
            result = tool.run_qualification([sys.executable, "-c", code, str(lock.fileno())],
                                            log, timeout=5, lock_fds=(lock.fileno(),))
        self.assertEqual(result, b"done\n")
        self.assertIn(b"detail\n", log.getvalue())

    def test_nonzero_exit_preserves_failure_output(self):
        log = io.BytesIO()
        with self.assertRaises(tool.TrainingError):
            tool.run_qualification([sys.executable, "-c", "print('failed'); raise SystemExit(2)"], log, timeout=5)
        self.assertIn(b"failed\n", log.getvalue())


class ExecutionTests(Fixture):
    def run_fake(self, *, mutation=None, result_change=None, qualification_change=None,
                 failure=None, pins=None):
        output = self.root / "output"
        args = Namespace(command="run", recipe=self.recipe_file, output=output,
                         cache=self.root / "cache", offline=True, allow_daytime=False,
                         reference_dir=self.root / "reference")
        self.calls = []

        def command(argv, log, **kwargs):
            if argv[1] == "--version":
                return b"Python test double\n"
            self.calls.append(argv)
            if "training_backend.py" in str(argv[1]):
                work = output / "work"
                work.mkdir()
                network, checkpoint = work / "candidate.nnue", work / "last.ckpt"
                network.write_bytes(b"not a real network; worker fixture")
                checkpoint.write_bytes(b"not a real checkpoint; worker fixture")
                result = {"status": "passed", "steps": 2, "processed_samples": 32,
                          "network": tool.file_identity(network), "checkpoint": tool.file_identity(checkpoint)}
                if result_change:
                    result_change(result)
                (work / "result.json").write_text(json.dumps(result))
                if mutation == "data":
                    self.data.write_bytes(b"changed")
                if failure == "training":
                    raise RuntimeError("synthetic worker failed")
            else:
                qualify = output / "qualification"
                qualify.mkdir()
                result = {"status": "passed", "artifact": tool.file_identity(output / "work/candidate.nnue")}
                if qualification_change:
                    qualification_change(result)
                (qualify / "report.json").write_text(json.dumps(result))
                if mutation == "checkpoint":
                    (output / "work/last.ckpt").write_bytes(b"changed checkpoint")
                if mutation == "network":
                    (output / "work/candidate.nnue").write_bytes(b"changed network")
                if failure == "qualification":
                    raise RuntimeError("synthetic oracle failed despite stale PASS fixture")
                if failure == "qualification_timeout":
                    raise subprocess.TimeoutExpired(argv, 600)
            return b""

        pin_mock = mock.patch.object(tool, "implementation_pins", side_effect=pins) if pins else \
            mock.patch.object(tool, "implementation_pins", return_value={"test": "digest"})
        with mock.patch.object(training_setup, "ensure_training_environment", return_value=Path(sys.executable)), \
                mock.patch.object(tool, "ensure_source", return_value=self.root / "source"), \
                mock.patch.object(tool, "resource_check", return_value={"timeout_seconds": 600}), \
                pin_mock, mock.patch.object(tool, "run_command", side_effect=command), \
                mock.patch.object(tool, "run_qualification", side_effect=command), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = tool.execute(args)
        return status, json.loads((output / "report.json").read_text())

    def test_success_binds_observed_steps_and_unknown_experience(self):
        status, report = self.run_fake()
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["playing_strength"], "not_measured")
        metadata = json.loads((self.root / "output/network.metadata.json").read_text())
        self.assertEqual(metadata["schema_version"], 2)
        self.assertEqual(metadata["training"]["steps"], 2)
        self.assertEqual(metadata["training"]["processed_samples"], 32)
        self.assertIsNone(metadata["training"]["epochs"])
        self.assertIsNone(metadata["training"]["games"])
        self.assertIn("--offline", self.calls[-1])

    def test_incomplete_observed_steps_are_not_promoted(self):
        status, report = self.run_fake(result_change=lambda r: r.update(steps=1, processed_samples=16))
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(self.calls), 1)

    def test_bool_steps_are_not_accepted_as_one(self):
        status, report = self.run_fake(result_change=lambda r: r.update(steps=True))
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_wrong_sample_count_fails(self):
        status, report = self.run_fake(result_change=lambda r: r.update(processed_samples=999))
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_changed_dataset_cannot_reach_qualification(self):
        status, report = self.run_fake(mutation="data")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(self.calls), 1)

    def test_changed_network_cannot_pass(self):
        status, report = self.run_fake(mutation="network")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_changed_checkpoint_cannot_pass(self):
        status, report = self.run_fake(mutation="checkpoint")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_changed_implementation_cannot_pass(self):
        status, report = self.run_fake(pins=[{"test": "before"}, {"test": "after"}])
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_failed_worker_preserves_failure_report(self):
        status, report = self.run_fake(failure="training")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_failed_oracle_never_trusts_its_pass_fixture(self):
        status, report = self.run_fake(failure="qualification")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_qualification_timeout_records_failed_run(self):
        status, report = self.run_fake(failure="qualification_timeout")
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")
        self.assertIn("TimeoutExpired", report["error"])

    def test_wrong_qualified_artifact_is_rejected(self):
        status, report = self.run_fake(qualification_change=lambda r: r["artifact"].update(sha256="0" * 64))
        self.assertNotEqual(status, 0)
        self.assertEqual(report["status"], "failed")

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "existing"
        output.mkdir()
        report = output / "report.json"
        report.write_text("preserve")
        status = self.cli("run", self.recipe_file, "--output", output)
        self.assertNotEqual(status.returncode, 0)
        self.assertEqual(report.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
