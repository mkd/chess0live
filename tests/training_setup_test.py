#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Exercise isolated training setup using tiny files and fake package commands."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import training_setup as setup


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="training runtime ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.asset = {"name": "example", "version": "1", "filename": "example-1-py3-none-any.whl",
                      "url": "https://files.pythonhosted.org/packages/example.whl",
                      "size": 5, "sha256": hashlib.sha256(b"wheel").hexdigest()}
        self.manifest = {"schema": 1, "python_version": [3, 12], "python_fallbacks": {},
                         "platforms": {"macos-arm64": {"packages": [self.asset], "imports": []}}}
        self.info = {"version": [3, 12], "implementation": "cpython", "system": "Darwin",
                     "machine": "arm64", "executable": "/native/python3.12", "full_version": "3.12-test"}


class ArchiveTests(Fixture):
    def test_valid_offline_archive_reuses_full_identity(self):
        path = self.root / self.asset["filename"]
        path.write_bytes(b"wheel")
        with patch.object(setup.urllib.request, "urlopen") as request:
            self.assertEqual(setup.fetch_asset(self.asset, self.root, True), path)
            request.assert_not_called()

    def test_same_size_corrupt_archive_is_not_reused_offline(self):
        path = self.root / self.asset["filename"]
        path.write_bytes(b"wrong")
        with self.assertRaisesRegex(setup.ToolingError, "Offline"):
            setup.fetch_asset(self.asset, self.root, True)
        self.assertEqual(path.read_bytes(), b"wrong")

    def test_missing_offline_archive_does_not_download(self):
        with patch.object(setup.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(setup.ToolingError, "Offline"):
                setup.fetch_asset(self.asset, self.root, True)
            request.assert_not_called()

    def test_download_is_checked_and_atomically_published(self):
        with patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(b"wheel")):
            path = setup.fetch_asset(self.asset, self.root, False)
        self.assertEqual(path.read_bytes(), b"wheel")
        self.assertEqual(list(self.root.glob("*.part")), [])

    def test_bad_download_does_not_replace_existing_archive(self):
        path = self.root / self.asset["filename"]
        path.write_bytes(b"prior")
        with patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
            with self.assertRaisesRegex(setup.ToolingError, "mismatch"):
                setup.fetch_asset(self.asset, self.root, False)
        self.assertEqual(path.read_bytes(), b"prior")
        self.assertEqual(list(self.root.glob("*.part")), [])

    def test_oversized_download_is_stopped(self):
        with patch.object(setup.urllib.request, "urlopen", return_value=io.BytesIO(b"wheel-too-large")):
            with self.assertRaisesRegex(setup.ToolingError, "exceeds"):
                setup.fetch_asset(self.asset, self.root, False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_path_aliases_are_rejected(self):
        for name in ("../escape", "/absolute", "C:drive", "foo\\bar"):
            with self.subTest(name=name), self.assertRaises(setup.ToolingError):
                setup.fetch_asset(dict(self.asset, filename=name), self.root, True)

    def test_unpinned_download_hosts_are_rejected(self):
        for url in ("http://files.pythonhosted.org/a", "https://example.com/a",
                    "https://files.pythonhosted.org.evil/a"):
            with self.subTest(url=url), self.assertRaises(setup.ToolingError):
                setup.fetch_asset(dict(self.asset, url=url), self.root, False)


class InterpreterTests(Fixture):
    def probe(self, value, status=0):
        with patch.object(setup.platform, "system", return_value="Darwin"), \
             patch.object(setup, "host_name", return_value="macos-arm64"), \
             patch.object(setup.subprocess, "run", return_value=subprocess.CompletedProcess([], status, json.dumps(value))):
            return setup.interpreter_info("/a path/python")

    def test_version_is_probed_not_inferred_from_filename(self):
        self.assertEqual(self.probe(self.info), self.info)
        self.assertIsNone(self.probe(dict(self.info, version=[3, 14])))

    def test_foreign_architecture_or_interpreter_is_rejected(self):
        for changes in ({"machine": "x86_64"}, {"system": "Linux"}, {"implementation": "pypy"}):
            self.assertIsNone(self.probe(dict(self.info, **changes)))

    def test_failed_or_malformed_probe_is_rejected(self):
        self.assertIsNone(self.probe(self.info, status=1))
        self.assertIsNone(self.probe([]))
        self.assertIsNone(self.probe({}))

    def test_explicit_interpreter_override_is_literal_and_respected(self):
        with patch.dict(os.environ, {"CHESS0LIVE_TRAINING_PYTHON": "/some path/python3.12"}), \
             patch.object(setup, "interpreter_info", return_value=self.info) as probe:
            path, info = setup.select_interpreter(self.manifest, self.root, True)
        probe.assert_called_once_with("/some path/python3.12")
        self.assertEqual(path, Path(self.info["executable"]))

    def test_bad_explicit_interpreter_never_silently_falls_back(self):
        with patch.dict(os.environ, {"CHESS0LIVE_TRAINING_PYTHON": "/wrong/python"}), \
             patch.object(setup, "interpreter_info", return_value=None), \
             patch.object(setup, "fetch_asset") as download:
            with self.assertRaisesRegex(setup.ToolingError, "must name"):
                setup.select_interpreter(self.manifest, self.root, False)
            download.assert_not_called()

    def test_missing_bundle_produces_python_prerequisite(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(setup, "interpreter_info", return_value=None):
            with self.assertRaisesRegex(setup.ToolingError, "Install Python 3.12"):
                setup.select_interpreter(self.manifest, self.root, False)


class EnvironmentTests(Fixture):
    def common(self):
        # Context managers returned separately keep each test's expected command
        # and file effects visible, rather than simulating installed packages.
        return (patch.object(setup, "load_manifest", return_value=self.manifest),
                patch.object(setup, "host_name", return_value="macos-arm64"),
                patch.object(setup.platform, "system", return_value="Darwin"),
                patch.object(setup.platform, "mac_ver", return_value=("15.0", (), "arm64")),
                patch.object(setup, "select_interpreter", return_value=(Path("/native/python3.12"), self.info)))

    def test_unsupported_host_fails_before_download_or_directory_creation(self):
        with patch.object(setup, "load_manifest", return_value=self.manifest), \
             patch.object(setup, "host_name", return_value="linux-riscv64"), \
             patch.object(setup, "fetch_asset") as download:
            with self.assertRaisesRegex(setup.ToolingError, "No pinned"):
                setup.ensure_training_environment(cache=self.root / "untouched")
        self.assertFalse((self.root / "untouched").exists())
        download.assert_not_called()

    def test_setup_uses_only_hash_locked_local_wheels(self):
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", side_effect=[False, True]), \
             patch.object(setup, "fetch_asset") as fetch, patch.object(setup, "setup_command") as run:
            executable = setup.ensure_training_environment(cache=self.root)
        self.assertEqual(len(run.call_args_list), 3)
        command = run.call_args_list[1].args[0]
        for flag in ("--no-index", "--no-deps", "--only-binary=:all:", "--require-hashes", "--no-cache-dir"):
            self.assertIn(flag, command)
        self.assertEqual(fetch.call_count, 1)
        requirements = executable.parent.parent / "requirements.lock"
        self.assertIn("--hash=sha256:" + self.asset["sha256"], requirements.read_text())
        self.assertTrue((requirements.parent / "ready").is_file())

    def test_healthy_cache_never_downloads_or_installs(self):
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", return_value=True), \
             patch.object(setup, "fetch_asset") as fetch, patch.object(setup, "setup_command") as run:
            setup.ensure_training_environment(offline=True, cache=self.root)
        fetch.assert_not_called()
        run.assert_not_called()

    def test_failed_install_leaves_owned_environment_for_recovery(self):
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", return_value=False), \
             patch.object(setup, "fetch_asset"), \
             patch.object(setup, "setup_command", side_effect=subprocess.CalledProcessError(1, ["fake-pip"])):
            with self.assertRaises(subprocess.CalledProcessError):
                setup.ensure_training_environment(cache=self.root)
        directory = next(self.root.glob("env-*"))
        self.assertTrue((directory / setup.OWNER).is_file())
        self.assertFalse((directory / "ready").exists())
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", side_effect=[False, True]), \
             patch.object(setup, "fetch_asset"), patch.object(setup, "setup_command"):
            setup.ensure_training_environment(offline=True, cache=self.root)
        self.assertTrue((directory / "ready").is_file())

    def test_unowned_environment_is_preserved(self):
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", side_effect=[False, True]), \
             patch.object(setup, "fetch_asset"), patch.object(setup, "setup_command"):
            executable = setup.ensure_training_environment(cache=self.root)
        directory = executable.parent.parent
        (directory / setup.OWNER).write_text('{}')
        marker = directory / "user-data"
        marker.write_text("preserve")
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", return_value=False):
            with self.assertRaisesRegex(setup.ToolingError, "unowned"):
                setup.ensure_training_environment(cache=self.root)
        self.assertEqual(marker.read_text(), "preserve")

    def test_failed_final_import_check_does_not_publish_ready(self):
        a,b,c,d,e = self.common()
        with a,b,c,d,e, patch.object(setup, "healthy", return_value=False), \
             patch.object(setup, "fetch_asset"), patch.object(setup, "setup_command"):
            with self.assertRaisesRegex(setup.ToolingError, "import/version"):
                setup.ensure_training_environment(cache=self.root)
        self.assertEqual(list(self.root.glob("env-*/ready")), [])

    def test_plan_has_no_setup_side_effect(self):
        with patch.object(setup, "load_manifest", return_value=self.manifest), \
             patch.object(setup, "host_name", return_value="macos-arm64"), \
             patch.object(setup, "ensure_training_environment") as install:
            report = setup.plan_training_environment()
        self.assertTrue(report["supported"])
        self.assertEqual(report["package_count"], 1)
        self.assertEqual(report["package_download_bytes"], 5)
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
