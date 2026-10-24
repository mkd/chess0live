#!/usr/bin/env python3
"""Exercise literal compiler paths and legacy Make commands without real builds.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from invoke_compiler import compiler_from_environment


class CompilerEnvironmentTests(unittest.TestCase):
    def test_literal_path_is_not_split_or_resolved(self):
        path = "/toolchain with spaces/target-clang++ $literal 'quote'"
        with mock.patch.dict(os.environ, {"CXX_EXECUTABLE": path}):
            self.assertEqual(compiler_from_environment(), [path])

    def test_missing_environment_has_clear_error(self):
        with mock.patch.dict(os.environ, {"CXX_EXECUTABLE": ""}):
            with self.assertRaisesRegex(ValueError, "one compiler executable path"):
                compiler_from_environment()


@unittest.skipIf(os.name == "nt", "Real fake-compiler shebang/Make checks require a POSIX shell")
class CompilerMakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="compiler-path-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.compiler = self.root / "toolchain with spaces" / "target-clang++ $literal 'quote'"
        self.compiler.parent.mkdir()
        self.journal = self.root / "calls.jsonl"
        self.compiler.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\nfrom pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "source = sys.stdin.read() if '-c' in args and '-' in args else None\n"
            "with open(os.environ['COMPILER_JOURNAL'], 'a') as f:\n"
            " f.write(json.dumps({'executable':sys.argv[0], 'args':args, 'source':source})+'\\n')\n"
            "if '--version' in args: print('synthetic compiler, no C++ execution')\n"
            "if '-o' in args:\n"
            " output = Path(args[args.index('-o')+1]); output.parent.mkdir(parents=True,exist_ok=True)\n"
            " output.write_text('synthetic output only')\n", encoding="utf-8")
        self.compiler.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(CXX_EXECUTABLE=str(self.compiler), COMPILER_JOURNAL=str(self.journal))
        self.env.pop("MAKEFLAGS", None)
        self.env.pop("MFLAGS", None)

    def run_command(self, arguments, *, env=None):
        result = subprocess.run(arguments, cwd=ROOT, env=env or self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def calls(self):
        return [json.loads(line) for line in self.journal.read_text().splitlines()]

    def test_probe_keeps_literal_path_and_records_compiler_identity(self):
        output = self.root / "output with spaces" / "probe.o"
        stamp = self.root / "stamp.json"
        arguments = [sys.executable, "tools/check_toolchain.py", "--target", "linux-riscv64",
                     "--compiler-env", "CXX_EXECUTABLE", "--flags=-std=c++2c -pthread",
                     "--output", str(output), "--stamp", str(stamp)]
        self.run_command(arguments)
        self.assertTrue(output.exists())
        record = json.loads(stamp.read_text())
        self.assertEqual(record["compiler"], [str(self.compiler)])
        self.assertEqual(record["compiler_path"], str(self.compiler.resolve()))
        self.assertEqual(self.calls()[1]["args"], ["-std=c++2c", "-pthread", "-x", "c++", "-c",
                                                 "-", "-o", str(output)])
        self.assertIn("__riscv_xlen == 64", self.calls()[1]["source"])
        # The second identical probe uses the configuration stamp, not another compile.
        self.run_command(arguments)
        self.assertEqual(len(self.calls()), 2)

    def test_make_build_uses_same_literal_compiler_for_probe_compile_and_link(self):
        build = self.root / "build"
        self.run_command(["make", "all", "TARGET=linux-riscv64", "CPU=generic",
                          f"BUILD={build}", "CXX=must-not-run"])
        calls = self.calls()
        self.assertEqual(len(calls), 10)  # version, probe, seven objects and engine link
        self.assertTrue(all(call["executable"] == str(self.compiler) for call in calls))
        self.assertTrue((build / "chess0live").is_file())
        self.assertEqual(json.loads((build / "toolchain.ok").read_text())["compiler"],
                         [str(self.compiler)])
        self.assertTrue(all("-std=c++2c" in call["args"] for call in calls if "-c" in call["args"]))
        self.assertIn("-pthread", calls[-1]["args"])

    def test_make_command_line_literal_value_handles_shell_and_make_characters(self):
        # Dollars and quote characters remain part of argv[0], not shell commands
        # or Make expansions. A literal path mode must not execute command text.
        compiler = self.compiler.with_name("target-clang++ $(must_not_expand) `literal`")
        compiler.write_bytes(self.compiler.read_bytes())
        compiler.chmod(0o755)
        env = self.env.copy()
        env.pop("CXX_EXECUTABLE", None)
        self.run_command(["make", "doctor", "TARGET=linux-arm64",
                          f"BUILD={self.root / 'doctor-build'}", f"CXX_EXECUTABLE={compiler}"], env=env)
        self.assertTrue(all(call["executable"] == str(compiler) for call in self.calls()))

    def test_legacy_compiler_command_and_wrapper_are_preserved(self):
        script = self.root / "legacy.py"
        script.write_bytes(self.compiler.read_bytes())
        compiler = shlex.join([sys.executable, str(script), "--wrapper-sentinel"])
        env = self.env.copy()
        env.pop("CXX_EXECUTABLE", None)
        self.run_command(["make", "all", "TARGET=linux-arm64", f"BUILD={self.root / 'legacy-build'}",
                          f"CXX={compiler}"], env=env)
        calls = self.calls()
        self.assertEqual(len(calls), 10)
        self.assertTrue(all(call["args"][0] == "--wrapper-sentinel" for call in calls))

    def test_all_runtime_link_recipes_use_literal_adapter(self):
        result = self.run_command(["make", "-nB", "runtime-binaries", "TARGET=windows-arm64",
                                   f"BUILD={self.root / 'runtime-build'}", "CXX=must-not-run"])
        commands = [shlex.split(line) for line in result.stdout.splitlines() if line]
        compilers = [command for command in commands if "tools/invoke_compiler.py" in command]
        links = [command for command in compilers if "-c" not in command]
        self.assertEqual(len(links), 8)
        self.assertTrue(all("-static" in command for command in links))
        self.assertFalse(any(command[0] == "must-not-run" for command in commands))


if __name__ == "__main__":
    unittest.main()
