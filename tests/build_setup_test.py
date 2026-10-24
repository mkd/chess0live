#!/usr/bin/env python3
"""Check portable build selection/orchestration without downloads or C++ builds.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build as builder


class CompilerSelectionTests(unittest.TestCase):
    def test_executable_preserves_invoked_alias(self):
        alias = "/toolchain with spaces/bin/aarch64-w64-mingw32-clang++"
        with mock.patch.object(builder.shutil, "which", return_value=alias):
            self.assertEqual(builder.executable("aarch64-w64-mingw32-clang++"), alias)

    def test_native_search_includes_versioned_compilers_and_deduplicates_paths(self):
        available = {"c++": "/usr/bin/clang++", "clang++": "/usr/bin/clang++",
                     "g++-14": "/usr/bin/g++-14"}
        with mock.patch.object(builder, "executable", side_effect=available.get):
            self.assertEqual(builder.compiler_candidates("linux-arm64", "linux-arm64"),
                             ["/usr/bin/clang++", "/usr/bin/g++-14"])

    def test_foreign_search_never_selects_unprefixed_host_compiler(self):
        looked_up = []
        def lookup(name):
            looked_up.append(name)
            return "/usr/bin/" + name if name == "riscv64-linux-gnu-g++-14" else None
        with mock.patch.object(builder, "executable", side_effect=lookup):
            self.assertEqual(builder.compiler_candidates("linux-riscv64", "macos-arm64"),
                             ["/usr/bin/riscv64-linux-gnu-g++-14"])
        self.assertFalse(any(name in looked_up for name in ("c++", "g++", "clang++")))

    def test_explicit_missing_compiler_fails_instead_of_searching(self):
        with mock.patch.object(builder, "executable", return_value=None) as lookup:
            with self.assertRaisesRegex(builder.ToolingError, "Compiler executable not found"):
                builder.compiler_candidates("windows-arm64", "macos-arm64", "/missing/compiler")
        lookup.assert_called_once_with("/missing/compiler")


class ResourceAndMakeTests(unittest.TestCase):
    def test_default_jobs_and_explicit_jobs_respect_current_budget(self):
        with mock.patch.object(builder, "current_budget", return_value={"max_cpu_workers": 9}):
            self.assertEqual(builder.job_limit(None), 2)
            self.assertEqual(builder.job_limit(9), 9)
            for value in (0, -1, 10):
                with self.subTest(value=value), self.assertRaises(builder.ToolingError):
                    builder.job_limit(value)
        with mock.patch.object(builder, "current_budget", return_value={"max_cpu_workers": 1}):
            self.assertEqual(builder.job_limit(None), 1)

    def test_missing_timezone_database_uses_one_worker(self):
        with mock.patch.object(builder, "current_budget", side_effect=ZoneInfoNotFoundError):
            self.assertEqual(builder.job_limit(None), 1)
            with self.assertRaises(builder.ToolingError):
                builder.job_limit(2)

    def test_make_must_identify_as_gnu(self):
        outputs = [subprocess.CompletedProcess([], 0, "BSD make", ""),
                   subprocess.CompletedProcess([], 0, "GNU Make 4.4.1", "")]
        with mock.patch.object(builder, "executable", side_effect=lambda name: "/bin/" + name), \
                mock.patch.object(builder.subprocess, "run", side_effect=outputs) as run:
            self.assertEqual(builder.make_program(None, None), ("/bin/make", None))
        self.assertEqual([call.args[0] for call in run.call_args_list],
                         [["/bin/gmake", "--version"], ["/bin/make", "--version"]])

    def test_bad_explicit_make_does_not_silently_use_another(self):
        with mock.patch.object(builder, "executable", return_value="/bad/make") as lookup, \
                mock.patch.object(builder.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0, "BSD Make", "")):
            with self.assertRaisesRegex(builder.ToolingError, "GNU Make"):
                builder.make_program("/bad/make", None)
        lookup.assert_called_once_with("/bad/make")

    def test_make_arguments_use_isolated_generic_output_and_quote_python(self):
        executable = "/Python with spaces/$literal $(NAME)/python3"
        with mock.patch.object(builder.sys, "executable", executable):
            args = builder.make_arguments("/make", "windows-arm64", "debug", 2, True, "/shell path/sh")
        self.assertEqual(args[-1], "runtime-binaries")
        self.assertIn("TARGET=windows-arm64", args)
        self.assertIn("CPU=generic", args)
        self.assertIn("BUILD=build/portable/windows-arm64-generic-debug", args)
        self.assertIn("SHELL=/shell path/sh", args)
        python = next(value.split("=", 1)[1] for value in args if value.startswith("PYTHON="))
        # Make must retain literal dollars before the POSIX shell receives the
        # quoted interpreter value; otherwise $(NAME) could silently disappear.
        env = {key: value for key, value in os.environ.items()
               if key not in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL")}
        result = subprocess.run(["make", "-n", "toolchain-plan", "PYTHON=" + python],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(shlex.split(result.stdout)[0], executable)
        self.assertFalse(any("CXX=" in value for value in args))


class PublicMakeTargetTests(unittest.TestCase):
    def commands(self, arguments=(), environment=None):
        env = {key: value for key, value in os.environ.items()
               if key not in ("TARGET", "MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL")}
        env.update(environment or {})
        # Simulate the older Make fallback detecting x86-64 when uname is
        # absent. The Python frontend must retain responsibility for host CPU.
        result = subprocess.run(["make", "-n", "portable", "toolchain-plan", "toolchain-check",
                                 "HOST_OS=Windows_NT", "HOST_CPU=unknown", *arguments],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [shlex.split(line) for line in result.stdout.splitlines() if line]
        self.assertEqual(len(commands), 3)
        self.assertTrue(all("tools/build.py" in command for command in commands))
        return commands

    def test_default_public_targets_leave_host_detection_to_python(self):
        for command in self.commands():
            self.assertNotIn("--target", command)

    def test_public_targets_forward_explicit_command_line_or_environment_target(self):
        for arguments, environment in [(["TARGET=windows-arm64"], {}),
                                       ([], {"TARGET": "linux-riscv64"})]:
            expected = "windows-arm64" if arguments else "linux-riscv64"
            with self.subTest(source="command" if arguments else "environment"):
                for command in self.commands(arguments, environment):
                    self.assertEqual(command[command.index("--target") + 1], expected)


class BuildFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="build setup ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = io.StringIO()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(contextlib.redirect_stdout(self.output))
        self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.stack.enter_context(mock.patch.object(builder, "ROOT", self.root))
        self.host = self.stack.enter_context(mock.patch.object(
            builder, "host_identity", return_value={"target": "macos-arm64"}))
        self.stack.enter_context(mock.patch.object(builder, "current_budget", return_value={"max_cpu_workers": 4}))
        self.stack.enter_context(mock.patch.dict(os.environ, {"CXX_EXECUTABLE": ""}))
        self.candidates = self.stack.enter_context(mock.patch.object(
            builder, "compiler_candidates", return_value=["/installed/compiler"]))
        self.probe = self.stack.enter_context(mock.patch.object(builder, "probe"))
        self.provision = self.stack.enter_context(mock.patch.object(
            builder, "provision_llvm", return_value=self.root / "pinned toolchain"))
        self.make = self.stack.enter_context(mock.patch.object(builder, "make_program", return_value=("/make", None)))
        self.command = self.stack.enter_context(mock.patch.object(builder, "setup_command"))
        self.fingerprint = self.stack.enter_context(mock.patch.object(
            builder, "binary_fingerprint", return_value={"identity": {"format": "PE32+"}}))

    def args(self, **values):
        defaults = dict(target="windows-arm64", toolchain="auto", compiler=None, make=None,
                        mode="release", jobs=None, offline=False, plan=False, check=False,
                        runtime_binaries=False)
        return SimpleNamespace(**(defaults | values))

    def report(self):
        reports = list((self.root / "build/portable/reports").glob("*/report.json"))
        self.assertEqual(len(reports), 1)
        return json.loads(reports[0].read_text())

    def test_plan_does_not_write_download_probe_or_build(self):
        self.assertIsNone(builder.build(self.args(plan=True)))
        plan = json.loads(self.output.getvalue())
        self.assertTrue(plan["pinned_llvm_fallback"])
        self.assertEqual(plan["jobs"], 2)
        self.assertFalse((self.root / "build").exists())
        for operation in (self.probe, self.provision, self.make, self.command):
            operation.assert_not_called()

    def test_unsupported_host_target_and_mac_sdk_boundary(self):
        for host, target, message in [(None, "windows-arm64", "Unsupported"),
                                      ("macos-arm64", "linux-unknown", "Unsupported"),
                                      ("linux-arm64", "macos-arm64", "Apple")]:
            self.host.return_value = {"target": host}
            with self.subTest(host=host, target=target), self.assertRaisesRegex(builder.ToolingError, message):
                builder.build(self.args(target=target))
        self.provision.assert_not_called()

    def test_riscv_host_does_not_advertise_unsupported_download(self):
        self.host.return_value = {"target": "linux-riscv64"}
        builder.build(self.args(plan=True))
        self.assertFalse(json.loads(self.output.getvalue())["pinned_llvm_fallback"])
        self.provision.assert_not_called()

    def test_llvm_target_and_explicit_compiler_conflicts(self):
        for values, message in [({"target": "linux-arm64"}, "Windows only"),
                                 ({"compiler": "/compiler"}, "not both")]:
            with self.subTest(values=values), self.assertRaisesRegex(builder.ToolingError, message):
                builder.build(self.args(toolchain="llvm-mingw", **values))
        self.provision.assert_not_called()

    def test_explicit_compiler_failure_never_downloads_fallback(self):
        self.probe.side_effect = subprocess.CalledProcessError(1, ["compiler", "link"])
        with self.assertRaisesRegex(builder.ToolingError, r"No working C\+\+26"):
            builder.build(self.args(compiler="/installed/compiler", check=True))
        self.provision.assert_not_called()
        report = self.report()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["attempts"][0]["status"], "failed")
        self.assertFalse(report["runtime_verified"])

    def test_installed_candidates_fall_back_after_compile_or_link_failure(self):
        self.candidates.return_value = ["/wrong-target/compiler", "/missing-libraries/compiler", "/working/compiler"]
        self.probe.side_effect = [subprocess.CalledProcessError(1, ["compile"]),
                                 subprocess.CalledProcessError(1, ["link"]), None]
        builder.build(self.args(check=True))
        report = self.report()
        self.assertEqual([attempt["status"] for attempt in report["attempts"]],
                         ["failed", "failed", "compile-and-link-passed"])
        self.assertEqual(report["compiler"], "/working/compiler")
        self.provision.assert_not_called()
        self.command.assert_not_called()

    def test_auto_provisions_pinned_fallback_and_check_never_runs_engine(self):
        self.probe.side_effect = [ValueError("wrong target"), None]
        result = builder.build(self.args(check=True, offline=True))
        self.provision.assert_called_once_with("macos-arm64", offline=True)
        self.assertEqual(result, self.root / "build/portable/windows-arm64-generic-release")
        report = self.report()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["action"], "check")
        self.assertNotIn("engine", report)
        self.assertFalse(report["runtime_verified"])
        self.assertIn("pinned-llvm-mingw", report["attempts"][1]["origin"])
        self.command.assert_not_called()
        self.make.assert_not_called()

    def test_installed_only_failure_does_not_download(self):
        self.candidates.return_value = []
        with self.assertRaises(builder.ToolingError):
            builder.build(self.args(toolchain="installed", check=True))
        self.provision.assert_not_called()

    def test_download_failure_is_reported_and_never_builds(self):
        self.candidates.return_value = []
        self.provision.side_effect = builder.ToolchainError("offline archive unavailable")
        with self.assertRaisesRegex(builder.ToolchainError, "offline archive"):
            builder.build(self.args(check=True, offline=True))
        self.assertEqual(self.report()["status"], "failed")
        self.command.assert_not_called()

    def test_make_uses_checkout_cwd_literal_compiler_and_sanitized_parent_flags(self):
        outside = self.root / "caller directory"
        outside.mkdir()
        original = Path.cwd()
        observed = []
        def completed_make(*args, **kwargs):
            observed.append((Path.cwd(), args[0], kwargs["env"]))
            output = self.root / "build/portable/windows-arm64-generic-release"
            (output / "toolchain.ok").write_text("{}")
        self.command.side_effect = completed_make
        try:
            os.chdir(outside)
            with mock.patch.dict(os.environ, {"MAKEFLAGS": "-j99 TARGET=bad", "MFLAGS": "-j99",
                                             "MAKEOVERRIDES": "BUILD=bad", "MAKELEVEL": "7"}):
                builder.build(self.args(runtime_binaries=True))
            self.assertEqual(Path.cwd(), outside)
        finally:
            os.chdir(original)
        self.assertEqual(observed[0][0], self.root)
        self.assertEqual(observed[0][1][-1], "runtime-binaries")
        self.assertEqual(observed[0][2]["CXX_EXECUTABLE"], "/installed/compiler")
        for name in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL"):
            self.assertNotIn(name, observed[0][2])
        self.assertEqual(self.report()["status"], "passed")
        self.assertEqual(self.report()["build_configuration"], {})
        self.assertFalse(self.report()["runtime_verified"])

    def test_make_failure_restores_cwd_and_records_failure(self):
        original = Path.cwd()
        self.command.side_effect = subprocess.CalledProcessError(2, ["make"])
        with self.assertRaises(subprocess.CalledProcessError):
            builder.build(self.args())
        self.assertEqual(Path.cwd(), original)
        self.assertEqual(self.report()["status"], "failed")
        self.fingerprint.assert_not_called()


class ProbeAndCliTests(unittest.TestCase):
    def test_probe_compiles_links_inspects_but_never_executes_the_target(self):
        with tempfile.TemporaryDirectory(prefix="probe source ") as directory:
            root = Path(directory).resolve()
            original = Path.cwd()
            observed = []
            def command(argv, **kwargs):
                observed.append((Path.cwd(), argv, kwargs["env"]))
            with mock.patch.object(builder, "ROOT", root), \
                    mock.patch.object(builder, "setup_command", side_effect=command), \
                    mock.patch.object(builder, "binary_fingerprint") as fingerprint:
                builder.probe("/compiler path/target-clang++", "windows-arm64", root / "probe", 5, {})
            self.assertEqual(Path.cwd(), original)
            self.assertEqual(len(observed), 2)
            self.assertTrue(all(cwd == root for cwd, _, _ in observed))
            self.assertIn(str(root / "tools/check_toolchain.py"), observed[0][1])
            self.assertEqual(observed[1][1][0], "/compiler path/target-clang++")
            self.assertIn("-static", observed[1][1])
            self.assertTrue(all(env["CXX_EXECUTABLE"] == "/compiler path/target-clang++"
                                for _, _, env in observed))
            fingerprint.assert_called_once_with(root / "probe/probe.exe", "windows-arm64")

    def test_cli_rejects_ambiguous_actions_and_invalid_jobs_are_forwarded_for_policy(self):
        with mock.patch.object(builder, "build") as build, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                builder.main(["--plan", "--check"])
            build.assert_not_called()
            self.assertEqual(builder.main(["--target", "linux-riscv64", "--jobs", "1", "--check"]), 0)
            self.assertEqual(build.call_args.args[0].jobs, 1)
            self.assertEqual(build.call_args.args[0].target, "linux-riscv64")


if __name__ == "__main__":
    unittest.main()
