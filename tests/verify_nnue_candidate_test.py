#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Engine-free candidate-oracle routing, evidence and process-lifecycle checks."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_nnue as oracle


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nnue candidate ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.work = self.root / "work"
        self.cache = self.root / "cached reference"
        self.cache.mkdir()
        self.network = self.root / "candidate.nnue"
        self.network.write_bytes(b"candidate weights")
        self.manifest = self.root / "networks/manifest.json"
        self.manifest.parent.mkdir()
        self.manifest.write_text(json.dumps({
            "filename": "pinned.nnue", "size_bytes": 6, "sha256": oracle.digest(b"pinned"),
            "reference_commit": "a" * 40, "reference_tag": "sf_19"}))
        for name in ("src/nnue.cpp", "src/position.cpp", "tests/nnue_test.cpp",
                     "tools/oracle/chess0live_stages.cpp", "tools/oracle/reference_main.cpp",
                     "tools/verify_nnue.py", "include/chess0live/nnue.hpp", "src/private.hpp"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original " + name)
        self.args = oracle.parse_args(["--candidate-network", str(self.network),
                                      "--reference-dir", str(self.cache),
                                      "--work-dir", str(self.work), "--offline"])
        self.calls = []
        self.corpus = b"position one\nposition two\n"
        self.stage = b"1,2;3,4;\n5,6;7,8;\n"
        self.raw = b"1 2 3\n4 5 6\n"
        self.action = None

    def fake_run(self, argv, log, cwd=None, input_data=None, timeout=300, lock_fds=(), output=None):
        argv = list(map(str, argv))
        self.calls.append(argv)
        result = b""
        if "--version" in argv:
            result = b"clang version fixture\n"
        elif argv[:3] == ["git", "rev-parse", "HEAD"]:
            result = ("a" * 40 + "\n").encode()
        elif argv[:2] == ["git", "clone"]:
            reference = Path(argv[-1])
            (reference / "src/nnue").mkdir(parents=True)
            (reference / "src/nnue/network.h").write_text("   private:\n")
            (reference / "src/main.cpp").write_text("upstream main")
            (reference / "src/Makefile").write_text("all:\n")
        elif argv[:2] == ["git", "show"]:
            result = b"   private:\n"
        elif argv[0] == "make":
            (Path(cwd) / ("stockfish.exe" if os.name == "nt" else "stockfish")).write_bytes(b"reference binary")
        elif "-o" in argv:
            Path(argv[argv.index("-o") + 1]).write_bytes(" ".join(argv).encode())
        elif "--positions" in argv:
            result = self.corpus
        elif "--dump" in argv or "--raw" in argv:
            result = self.raw
        elif "nnue-stages-" in argv[0] or Path(argv[0]).name in ("stockfish", "stockfish.exe"):
            result = self.stage
        if self.action:
            result = self.action(argv, result)
        if output is not None:
            Path(output).write_bytes(result)
        return result

    def execute(self):
        with patch.object(oracle, "run", side_effect=self.fake_run), \
                patch.object(oracle, "compiler_argv", return_value=["fixture-clang++"]), \
                patch.object(oracle, "current_budget", return_value={"max_cpu_workers": 1}), \
                contextlib.redirect_stdout(io.StringIO()):
            return oracle.verify(self.args, self.root)

    def report(self):
        return json.loads((self.work / "report.json").read_text())

    def test_candidate_full_comparison_without_pinned_goldens(self):
        report = self.execute()
        self.assertEqual(report["result"], "PASS")
        self.assertFalse(report["network_pinned"])
        self.assertEqual(report["positions"], 2)
        self.assertEqual(report["network_sha256"], oracle.digest(self.network.read_bytes()))
        self.assertEqual(set(report["binaries"]), {"native_raw", "scalar_raw", "native_stages", "scalar_stages", "reference"})
        self.assertEqual(set(report["outputs"]), {"native", "scalar"})
        self.assertIn("include/chess0live/nnue.hpp", report["source_sha256"])
        self.assertIn("src/nnue/network.h", report["reference_source_sha256"])
        self.assertEqual(sum("--dump" in call for call in self.calls), 2)
        self.assertFalse(any("--network" in call and "--dump" not in call for call in self.calls))
        raw_indices = [i for i, call in enumerate(self.calls) if "--dump" in call]
        reference_indices = [i for i, call in enumerate(self.calls) if Path(call[0]).name in ("stockfish", "stockfish.exe")]
        self.assertLess(max(raw_indices), min(reference_indices))
        clone = next(call for call in self.calls if call[:2] == ["git", "clone"])
        self.assertIn("--local", clone)
        self.assertIn("--no-hardlinks", clone)
        self.assertEqual(clone[-2], str(self.cache))

    def test_matching_candidate_also_runs_pinned_goldens(self):
        self.network.write_bytes(b"pinned")
        report = self.execute()
        self.assertTrue(report["network_pinned"])
        self.assertEqual(report["pinned_goldens"], "passed")
        self.assertEqual(sum("--network" in call and "--dump" not in call for call in self.calls), 2)

    def test_old_network_option_remains_strict(self):
        self.args.network, self.args.candidate_network = self.network, None
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.execute()
        self.assertEqual(self.report()["result"], "FAIL")
        self.assertEqual(self.calls, [])

    def test_stale_pass_replaced_on_failure(self):
        self.work.mkdir()
        (self.work / "report.json").write_text('{"result":"PASS","positions":999}')
        self.network.unlink()
        with self.assertRaisesRegex(RuntimeError, "regular SFNNv16"):
            self.execute()
        report = self.report()
        self.assertEqual(report["result"], "FAIL")
        self.assertNotIn("positions", report)
        self.assertIn("run_id", report)

    def test_offline_missing_cache_never_clones(self):
        self.cache.rmdir()
        with self.assertRaisesRegex(RuntimeError, "Offline reference"):
            self.execute()
        self.assertFalse(any(call[:2] == ["git", "clone"] for call in self.calls))

    def test_wrong_reference_pin_rejected_before_build(self):
        self.action = lambda argv, value: b"wrong\n" if argv[:3] == ["git", "rev-parse", "HEAD"] else value
        with self.assertRaisesRegex(RuntimeError, "pinned commit"):
            self.execute()
        self.assertFalse(any(call[0] == "make" for call in self.calls))

    def test_incremental_or_safe_score_failure_prevents_upstream_evaluation(self):
        def fail_raw(argv, value):
            if "--dump" in argv:
                raise RuntimeError("unsafe candidate calibration")
            return value
        self.action = fail_raw
        with self.assertRaisesRegex(RuntimeError, "unsafe candidate"):
            self.execute()
        self.assertFalse(any(Path(call[0]).name in ("stockfish", "stockfish.exe") for call in self.calls))

    def test_stage_difference_is_failure(self):
        self.action = lambda argv, value: b"wrong\nwrong\n" if "nnue-stages-scalar" in argv[0] else value
        with self.assertRaisesRegex(RuntimeError, "integer stages: mismatch"):
            self.execute()
        self.assertEqual(self.report()["result"], "FAIL")

    def test_raw_difference_is_failure(self):
        self.action = lambda argv, value: b"wrong\nwrong\n" if "--raw" in argv else value
        with self.assertRaisesRegex(RuntimeError, "raw/wrapped scores: mismatch"):
            self.execute()

    def test_empty_corpus_is_failure(self):
        self.corpus = b""
        with self.assertRaisesRegex(RuntimeError, "corpus is empty"):
            self.execute()

    def test_network_mutation_invalidates_pass(self):
        def mutate(argv, value):
            if "nnue-stages-scalar" in argv[0]:
                self.network.write_bytes(b"changed candidate")
            return value
        self.action = mutate
        with self.assertRaisesRegex(RuntimeError, "Network changed"):
            self.execute()

    def test_source_mutation_invalidates_pass(self):
        def mutate(argv, value):
            if "nnue-stages-scalar" in argv[0]:
                (self.root / "include/chess0live/nnue.hpp").write_text("changed")
            return value
        self.action = mutate
        with self.assertRaisesRegex(RuntimeError, "local sources changed"):
            self.execute()

    def test_binary_mutation_invalidates_pass(self):
        def mutate(argv, value):
            if "nnue-stages-scalar" in argv[0]:
                Path(argv[0]).write_bytes(b"changed binary")
            return value
        self.action = mutate
        with self.assertRaisesRegex(RuntimeError, "binary changed"):
            self.execute()

    def test_overlapping_work_is_excluded(self):
        self.work.mkdir()
        self.args.lock_timeout = 0
        with oracle.setup_lock(self.work / ".oracle.lock"):
            with self.assertRaisesRegex(RuntimeError, "Another tool"):
                self.execute()
        self.assertEqual(self.calls, [])

    def test_overlapping_cache_writes_current_fail(self):
        self.args.lock_timeout = 0
        with oracle.setup_lock(self.cache.parent / ("." + self.cache.name + ".oracle.lock")):
            with self.assertRaisesRegex(RuntimeError, "Another tool"):
                self.execute()
        self.assertEqual(self.report()["result"], "FAIL")

    def test_interruption_records_fail(self):
        def interrupt(argv, value):
            if "--dump" in argv:
                raise KeyboardInterrupt()
            return value
        self.action = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.execute()
        self.assertIn("KeyboardInterrupt", self.report()["error"])


class ProcessTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("make"), "GNU Make boundary check requires Make")
    def test_upstream_make_preserves_literal_dollars_and_spaces(self):
        with tempfile.TemporaryDirectory(prefix="nnue make ") as folder:
            root = Path(folder)
            compiler = root / "compiler $not_a_variable $(not_a_command).py"
            compiler.write_text("import sys; print('literal compiler ok ' + sys.argv[1])")
            (root / "Makefile").write_text("all:\n\t@$(CXX) --probe\n")
            result = subprocess.run(["make", "all", oracle.make_compiler_assignment([sys.executable, str(compiler)])],
                                    cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("literal compiler ok --probe", result.stdout)

    def test_literal_compiler_path_keeps_spaces_and_alias_name(self):
        args = oracle.parse_args(["--compiler-executable", "/tmp/compiler path/clang++"])
        with patch.object(oracle.shutil, "which", return_value="/tmp/compiler path/clang++"):
            self.assertEqual(oracle.compiler_argv(args), ["/tmp/compiler path/clang++"])

    def test_cli_routes_are_exclusive(self):
        for argv in (["--network", "a", "--candidate-network", "b"],
                     ["--compiler", "a", "--compiler-executable", "b"],
                     ["--timeout", "nan"], ["--lock-timeout", "inf"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                oracle.parse_args(argv)

    def test_empty_matching_dumps_are_not_verification(self):
        with self.assertRaisesRegex(RuntimeError, "empty"):
            oracle.compare(b"", b"", "fixture", b"")

    def test_command_failure_and_timeout(self):
        with self.assertRaisesRegex(RuntimeError, "Command failed"):
            oracle.run([sys.executable, "-c", "raise SystemExit(4)"], io.BytesIO())
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            oracle.run([sys.executable, "-c", "import time; time.sleep(20)"], io.BytesIO(), timeout=.1)
        self.assertLess(time.monotonic() - started, 5)

    def test_timeout_retains_partial_diagnostics(self):
        log = io.BytesIO()
        with self.assertRaises(subprocess.TimeoutExpired):
            oracle.run([sys.executable, "-c", "import time; print('partial diagnostic',flush=True); time.sleep(20)"],
                       log, timeout=.2)
        self.assertIn(b"partial diagnostic", log.getvalue())

    @unittest.skipIf(os.name == "nt", "POSIX process-group cleanup")
    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory() as folder:
            flag = Path(folder) / "child survived"
            child = "import time,pathlib; time.sleep(1); pathlib.Path(" + repr(str(flag)) + ").write_text('bad')"
            parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(20)"
            with self.assertRaises(subprocess.TimeoutExpired):
                oracle.run([sys.executable, "-c", parent], io.BytesIO(), timeout=.2)
            time.sleep(1.1)
            self.assertFalse(flag.exists())


if __name__ == "__main__":
    unittest.main()
