#!/usr/bin/env python3
"""Check cross-build recipes without compiling or executing target binaries.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeBuildTests(unittest.TestCase):
    def commands(self, *targets):
        result = subprocess.run(
            ["make", "-nB", "TARGET=linux-riscv64", "CPU=generic", "MODE=release",
             "CXX=unavailable-test-compiler", "LDLIBS=-lchess0live_test_sentinel",
             *targets], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [shlex.split(line) for line in result.stdout.splitlines() if line]

    def test_all_correctness_links_receive_target_libraries(self):
        # Discover every concrete C++ test link rule, including experimental
        # search tests, so future additions cannot silently omit target libraries.
        makefile = (ROOT / "Makefile").read_text()
        names = re.findall(r"^\$\(BUILD\)/([\w-]+-test)\$\(EXE\):", makefile, re.M)
        self.assertGreaterEqual(len(names), 10)
        targets = ["build/linux-riscv64-generic-release/" + name for name in names]
        links = [cmd for cmd in self.commands(*targets)
                 if cmd[0] == "unavailable-test-compiler" and "-c" not in cmd]
        self.assertEqual(len(links), len(names))
        for cmd in links:
            with self.subTest(output=cmd[-1]):
                self.assertIn("-lchess0live_test_sentinel", cmd)
                self.assertLess(cmd.index("-lchess0live_test_sentinel"), cmd.index("-o"))

    def test_runtime_binaries_only_builds(self):
        commands = self.commands("runtime-binaries")
        links = [cmd for cmd in commands
                 if cmd[0] == "unavailable-test-compiler" and "-c" not in cmd]
        self.assertEqual(len(links), 8)  # Engine plus seven portable C++ suites.
        self.assertTrue(all("-lchess0live_test_sentinel" in cmd for cmd in links))
        for cmd in commands:
            self.assertFalse(cmd[0].startswith("build/"), cmd)
            self.assertNotIn("tools/verify_runtime.py", cmd)


if __name__ == "__main__":
    unittest.main()
