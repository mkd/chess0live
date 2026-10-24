#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Check explicit network launch selection without changing engine defaults.

Pass the separately built engine and an existing compatible network. These are
short, serial protocol/loading checks using Python's standard library only.
They establish launch behavior, not network arithmetic or playing strength.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAME = "nn-1a298aa575a0.nnue"


class EvalFileLaunchTests(unittest.TestCase):
    binary: Path
    network: Path

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="chess0live cli network ")
        cls.directory = Path(cls.temporary.name).resolve()
        cls.selected = cls.directory / "chosen weights with spaces.nnue"
        shutil.copyfile(cls.network, cls.selected)
        cls.bad = cls.directory / "corrupt.nnue"
        cls.bad.write_bytes(b"invalid network fixture")
        # A filename fallback is deliberately available under networks/. An
        # explicit missing basename must still fail instead of loading this.
        (cls.directory / "networks").mkdir()
        shutil.copyfile(cls.network, cls.directory / "networks" / DEFAULT_NAME)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def invoke(self, arguments=(), commands="uci\nquit\n", cwd=None):
        return subprocess.run([str(self.binary), *map(str, arguments)], input=commands,
                              text=True, capture_output=True, timeout=30,
                              cwd=cwd or self.directory)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("info string error:", result.stdout)

    def launch_line(self, path):
        return "option name EvalFile type string default " + str(path)

    def test_no_arguments_preserve_default(self):
        result = self.invoke()
        self.assert_success(result)
        self.assertIn(self.launch_line(DEFAULT_NAME), result.stdout.splitlines())

    def test_absolute_path_with_spaces_is_advertised_and_loaded(self):
        result = self.invoke(["--eval-file", self.selected], "uci\nisready\neval\nquit\n")
        self.assert_success(result)
        self.assertIn(self.launch_line(self.selected), result.stdout.splitlines())
        self.assertIn("readyok", result.stdout.splitlines())
        self.assertIn("NNUE evaluation: ", result.stdout)

    def test_relative_path_resolves_from_launch_directory(self):
        result = self.invoke(["--eval-file", self.selected.name], "uci\nisready\nquit\n")
        self.assert_success(result)
        self.assertIn(self.launch_line(self.selected), result.stdout.splitlines())

    def test_missing_explicit_file_has_no_default_fallback(self):
        result = self.invoke(["--eval-file", DEFAULT_NAME])
        self.assertEqual(result.returncode, 1)
        self.assertIn("--eval-file is not a regular file", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_directory_is_rejected(self):
        result = self.invoke(["--eval-file", self.directory])
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a regular file", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_corrupt_explicit_file_fails_before_uci(self):
        result = self.invoke(["--eval-file", self.bad])
        self.assertEqual(result.returncode, 1)
        self.assertIn("--eval-file rejected network", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_uci_override_is_applied_then_can_be_restored(self):
        commands = (f"setoption name EvalFile value {self.bad}\nisready\neval\n"
                    f"setoption name EvalFile value {self.selected}\nisready\neval\nuci\nquit\n")
        result = self.invoke(["--eval-file", self.selected], commands)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("rejected network", result.stdout)
        self.assertEqual(result.stdout.count("NNUE evaluation: "), 1,
                         "The old loaded network must not be used after an invalid override")
        self.assertIn(self.launch_line(self.selected), result.stdout.splitlines())

    def test_explicit_and_uci_loaded_scores_agree(self):
        explicit = self.invoke(["--eval-file", self.selected], "eval\nquit\n")
        uci = self.invoke(commands=f"setoption name EvalFile value {self.selected}\neval\nquit\n")
        self.assert_success(explicit)
        self.assert_success(uci)
        score = lambda result: [line for line in result.stdout.splitlines()
                                if line.startswith("NNUE evaluation: ")]
        self.assertEqual(len(score(explicit)), 1)
        self.assertEqual(score(explicit), score(uci))

    def test_help_describes_explicit_launch_and_override(self):
        result = self.invoke(["--help"])
        self.assert_success(result)
        self.assertIn("--eval-file PATH", result.stdout)
        self.assertIn("setoption name EvalFile", result.stdout)
        self.assertNotIn("uciok", result.stdout)

    def test_version_is_unchanged(self):
        result = self.invoke(["--version"])
        self.assert_success(result)
        self.assertEqual(result.stdout, "chess0live 0.1-dev\n")

    def test_invalid_argument_shapes_are_rejected(self):
        for arguments in (["--eval-file"], ["--eval-file", ""], ["--eval-file", "--version"],
                          ["--unknown"], ["--version", "extra"], ["--help", "extra"],
                          ["--eval-file", self.selected, "--eval-file", self.selected],
                          ["--eval-file", self.selected, "--help"]):
            with self.subTest(arguments=arguments):
                result = self.invoke(arguments)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("expected no arguments", result.stderr)

    def test_control_characters_cannot_inject_uci_output(self):
        for character in ("\n", "\r", "\t", "\x7f"):
            with self.subTest(character=repr(character)):
                result = self.invoke(["--eval-file", "path" + character + "uciok.nnue"])
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("UCI control character", result.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks" / DEFAULT_NAME)
    args = parser.parse_args()
    EvalFileLaunchTests.binary = args.binary.resolve()
    EvalFileLaunchTests.network = args.network.resolve()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(EvalFileLaunchTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
