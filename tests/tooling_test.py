#!/usr/bin/env python3
"""Check isolated tool setup without installing packages or searching engines.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

import contextlib
import hashlib
import http.client
import importlib.metadata
import io
import json
import os
from pathlib import Path
import runpy
import select
import signal
import subprocess
import sys
import tempfile
import time
from types import ModuleType
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import tooling


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tool setup ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.payload = b"pinned test package\n"
        self.asset = {
            "filename": "fixture-1.0.tar.gz",
            "url": "https://files.pythonhosted.org/packages/fixture-1.0.tar.gz",
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    def fetch(self, payload=None):
        with mock.patch.object(tooling.urllib.request, "urlopen",
                               return_value=io.BytesIO(self.payload if payload is None else payload)):
            return tooling.download_asset(self.asset, self.directory)

    def test_download_is_verified_and_cached_for_offline_reuse(self):
        path = self.fetch()
        self.assertEqual(path.read_bytes(), self.payload)
        with mock.patch.object(tooling.urllib.request, "urlopen",
                               side_effect=AssertionError("offline cache touched network")):
            self.assertEqual(tooling.download_asset(self.asset, self.directory, offline=True), path)

    def test_missing_offline_package_is_actionable(self):
        with mock.patch.object(tooling.urllib.request, "urlopen") as download:
            with self.assertRaises(tooling.ToolingError):
                tooling.download_asset(self.asset, self.directory, offline=True)
            download.assert_not_called()

    def test_corrupt_cache_is_rejected_offline(self):
        path = self.fetch()
        path.write_bytes(b"corrupted cache")
        with mock.patch.object(tooling.urllib.request, "urlopen") as download:
            with self.assertRaises(tooling.ToolingError):
                tooling.download_asset(self.asset, self.directory, offline=True)
            download.assert_not_called()

    def test_online_retry_repairs_corrupt_cache(self):
        path = self.fetch()
        path.write_bytes(b"corrupted cache")
        self.assertEqual(self.fetch().read_bytes(), self.payload)

    def test_bad_download_is_not_accepted_and_retry_succeeds(self):
        with self.assertRaises(tooling.ToolingError):
            self.fetch(b"wrong package bytes")
        # A retry must not treat a previous partial/unverified file as a hit.
        self.assertEqual(self.fetch().read_bytes(), self.payload)

    def test_interrupted_download_can_be_retried(self):
        class Interrupted(io.BytesIO):
            def read(self, size=-1):
                raise OSError("connection interrupted")

        with mock.patch.object(tooling.urllib.request, "urlopen",
                               return_value=Interrupted(self.payload)):
            with self.assertRaises((tooling.ToolingError, OSError)):
                tooling.download_asset(self.asset, self.directory)
        self.assertEqual(self.fetch().read_bytes(), self.payload)

    def test_truncated_http_body_has_friendly_error_and_can_be_retried(self):
        class Truncated(io.BytesIO):
            def read(self, size=-1):
                raise http.client.IncompleteRead(b"partial body", 100)

        with mock.patch.object(tooling.urllib.request, "urlopen",
                               return_value=Truncated(self.payload)):
            with self.assertRaisesRegex(tooling.ToolingError, "retry"):
                tooling.download_asset(self.asset, self.directory)
        self.assertFalse(list(self.directory.glob("*.part")))
        self.assertEqual(self.fetch().read_bytes(), self.payload)

    def test_archive_path_cannot_escape_cache(self):
        for filename in ("../outside.tar.gz", "nested/file.tar.gz", "nested\\file.tar.gz"):
            with self.subTest(filename=filename), self.assertRaises(tooling.ToolingError):
                tooling.download_asset(dict(self.asset, filename=filename), self.directory)

    def test_new_download_requires_pinned_https_host(self):
        for url in ("http://files.pythonhosted.org/fixture", "https://example.com/fixture"):
            with self.subTest(url=url), self.assertRaises(tooling.ToolingError):
                tooling.download_asset(dict(self.asset, url=url), self.directory)


class LockTests(unittest.TestCase):
    def test_exception_releases_setup_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "setup.lock"
            with self.assertRaisesRegex(RuntimeError, "interrupted setup"):
                with tooling.setup_lock(lock, timeout=0.1):
                    raise RuntimeError("interrupted setup")
            with tooling.setup_lock(lock, timeout=0.1):
                pass

    def test_competing_process_times_out_and_later_can_acquire(self):
        with tempfile.TemporaryDirectory(prefix="tool lock ") as directory:
            lock = Path(directory) / "setup.lock"
            source = (
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
                "from pathlib import Path\n"
                "from tooling import setup_lock, ToolingError\n"
                "try:\n"
                f" with setup_lock(Path({str(lock)!r}), timeout=0.1): pass\n"
                "except ToolingError:\n"
                " sys.exit(7)\n"
            )
            command = [sys.executable, "-c", source]
            with tooling.setup_lock(lock, timeout=1):
                failed = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(failed.returncode, 7, failed.stderr)
            success = subprocess.run(command, capture_output=True, text=True, timeout=5)
            self.assertEqual(success.returncode, 0, success.stderr)

    def test_killed_setup_process_does_not_leave_stale_lock(self):
        with tempfile.TemporaryDirectory(prefix="killed setup ") as directory:
            root = Path(directory)
            lock, ready = root / "setup.lock", root / "ready"
            source = (
                "import sys, time\n"
                f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
                "from pathlib import Path\nfrom tooling import setup_lock\n"
                f"with setup_lock(Path({str(lock)!r})):\n"
                f" Path({str(ready)!r}).write_text('locked')\n"
                " time.sleep(60)\n"
            )
            process = subprocess.Popen([sys.executable, "-c", source],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 3
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "lock holder did not reach its ready marker")
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)
            with tooling.setup_lock(lock, timeout=0.1):
                pass


class InstallerProcessTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX installer process-group cleanup")
    def test_timeout_stops_installer_descendant_and_releases_lock(self):
        with tempfile.TemporaryDirectory(prefix="installer timeout ") as directory:
            root = Path(directory)
            marker, lock = root / "child.json", root / "setup.lock"
            child = (
                "import json, os, signal\nfrom pathlib import Path\n"
                f"temporary = Path({str(marker.with_suffix('.part'))!r})\n"
                "temporary.write_text(json.dumps({'parent': os.getppid(), 'child': os.getpid()}))\n"
                f"temporary.replace({str(marker)!r})\n"
                "signal.pause()\n"
            )
            parent = f"import subprocess, sys\nsubprocess.run([sys.executable, '-c', {child!r}])\n"
            pids = None
            read_fd, write_fd = os.pipe()
            try:
                with os.fdopen(write_fd, "w") as log, tooling.setup_lock(lock) as lock_fd:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        tooling.setup_command([sys.executable, "-c", parent],
                                              log=log, lock_fd=lock_fd, timeout=1)
                self.assertTrue(marker.exists(), "installer descendant never reached ready state")
                pids = json.loads(marker.read_text())
                # The descendant inherits stdout. EOF proves it closed the pipe,
                # without mistaking a killed child awaiting OS reaping for a live one.
                readable, _, _ = select.select([read_fd], [], [], 2)
                self.assertTrue(readable, "installer descendant retained its stdout after timeout")
                self.assertEqual(os.read(read_fd, 4096), b"")
                with tooling.setup_lock(lock, timeout=0.1):
                    pass
            finally:
                os.close(read_fd)
                if pids is None and marker.exists():
                    pids = json.loads(marker.read_text())
                if pids:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(pids["parent"], signal.SIGKILL)

    @unittest.skipIf(os.name == "nt", "POSIX installer signal cleanup")
    def test_sigterm_stops_setup_descendants_and_releases_lock(self):
        with tempfile.TemporaryDirectory(prefix="installer signal ") as directory:
            root = Path(directory)
            marker, lock = root / "child.json", root / "setup.lock"
            child = (
                "import json, os, signal\nfrom pathlib import Path\n"
                f"temporary = Path({str(marker.with_suffix('.part'))!r})\n"
                "temporary.write_text(json.dumps({'installer': os.getppid(), 'child': os.getpid()}))\n"
                f"temporary.replace({str(marker)!r})\n"
                "signal.pause()\n"
            )
            installer = f"import subprocess, sys\nsubprocess.run([sys.executable, '-c', {child!r}])\n"
            source = (
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
                "from pathlib import Path\nfrom tooling import setup_lock, setup_command\n"
                f"with setup_lock(Path({str(lock)!r})) as fd:\n"
                f" setup_command([sys.executable, '-c', {installer!r}], log=sys.stdout, lock_fd=fd, timeout=10)\n"
            )
            process = subprocess.Popen([sys.executable, "-c", source],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            pids = None
            try:
                deadline = time.monotonic() + 3
                while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "installer descendant never reached ready state")
                pids = json.loads(marker.read_text())
                process.terminate()
                # communicate reaching EOF also proves descendants closed stdout.
                output, _ = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 128 + signal.SIGTERM, output)
                with tooling.setup_lock(lock, timeout=0.1):
                    pass
            finally:
                if process.poll() is None:
                    process.kill()
                if pids is None and marker.exists():
                    pids = json.loads(marker.read_text())
                if pids:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(pids["installer"], signal.SIGKILL)
                process.communicate(timeout=3)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="environment setup ")
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name).resolve()
        self.packages = json.loads(tooling.MANIFEST.read_text())["packages"]
        self.key = tooling.environment_key(tooling.MANIFEST.read_bytes())
        self.environment = self.cache / ("env-" + self.key)

    def fake_download(self, asset, directory, offline=False):
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / asset["filename"]
        archive.touch()
        return archive

    def fake_healthy(self, directory, key, packages):
        return (directory / "ready").is_file()

    def test_partial_install_has_no_ready_marker_and_retry_succeeds(self):
        with mock.patch.object(tooling, "download_asset", side_effect=self.fake_download), \
                mock.patch.object(tooling, "healthy", side_effect=self.fake_healthy), \
                contextlib.redirect_stderr(io.StringIO()):
            with mock.patch.object(tooling, "setup_command", side_effect=[
                    None, subprocess.CalledProcessError(1, ["pip"])]):
                with self.assertRaisesRegex(tooling.ToolingError, "Retry the same command"):
                    tooling.ensure_environment(cache=self.cache)
            self.assertFalse((self.environment / "ready").exists())
            self.assertTrue((self.environment / "chess0live-owner").is_file())
            sentinel = self.environment / "partial-package"
            sentinel.write_text("not complete")
            with mock.patch.object(tooling, "setup_command"):
                python = tooling.ensure_environment(cache=self.cache)
            self.assertEqual(python, tooling.python_path(self.environment))
            self.assertFalse(sentinel.exists())
            self.assertEqual((self.environment / "ready").read_text(), self.key)

    def test_healthy_reuse_does_not_download_or_install(self):
        with mock.patch.object(tooling, "healthy", return_value=True), \
                mock.patch.object(tooling, "download_asset") as download, \
                mock.patch.object(tooling, "setup_command") as install:
            self.assertEqual(tooling.ensure_environment(cache=self.cache),
                             tooling.python_path(self.environment))
            download.assert_not_called()
            install.assert_not_called()

    def test_missing_or_stale_owner_marker_is_not_a_healthy_environment(self):
        self.environment.mkdir()
        (self.environment / "ready").write_text(self.key)
        owner = self.environment / "chess0live-owner"
        for contents in (None, "stale-environment-key"):
            if contents is not None:
                owner.write_text(contents)
            with self.subTest(owner=contents), \
                    mock.patch.object(tooling.subprocess, "run",
                                      return_value=subprocess.CompletedProcess([], 0)) as probe:
                self.assertFalse(tooling.healthy(self.environment, self.key, self.packages))
                probe.assert_not_called()

    def test_unowned_environment_is_preserved(self):
        self.environment.mkdir()
        sentinel = self.environment / "user-file"
        sentinel.write_text("preserve me")
        with mock.patch.object(tooling, "download_asset", side_effect=self.fake_download), \
                mock.patch.object(tooling, "healthy", return_value=False), \
                contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaisesRegex(tooling.ToolingError, "unowned"):
            tooling.ensure_environment(cache=self.cache)
        self.assertEqual(sentinel.read_text(), "preserve me")

    def test_install_uses_copies_pinned_local_archives_and_isolated_pip(self):
        with mock.patch.object(tooling, "download_asset", side_effect=self.fake_download) as download, \
                mock.patch.object(tooling, "healthy", side_effect=self.fake_healthy), \
                mock.patch.object(tooling, "setup_command") as run, \
                mock.patch.dict(os.environ, {"PIP_TARGET": "/must-not-write",
                                            "PYTHONPATH": "/must-not-import"}), \
                contextlib.redirect_stderr(io.StringIO()):
            tooling.ensure_environment(cache=self.cache, offline=True)
        self.assertIn("--copies", run.call_args_list[0].args[0])
        self.assertTrue(all(call.args[2] for call in download.call_args_list))
        for call in run.call_args_list[1:]:
            command = call.args[0]
            self.assertEqual(command[0], str(tooling.python_path(self.environment)))
            for option in ("--no-index", "--no-deps", "--no-build-isolation", "--require-hashes"):
                self.assertIn(option, command)
            self.assertNotIn("PIP_TARGET", call.kwargs["env"])
            self.assertNotIn("PYTHONPATH", call.kwargs["env"])
            self.assertEqual(call.kwargs["env"]["PIP_CONFIG_FILE"], os.devnull)
            requirements = Path(command[command.index("-r") + 1]).read_text()
            self.assertIn("file:", requirements)
            self.assertIn("--hash=sha256:", requirements)
            self.assertNotIn("https:", requirements)


class LauncherTests(unittest.TestCase):
    def test_environment_identity_tracks_manifest(self):
        first = tooling.environment_key(b"first manifest")
        self.assertEqual(first, tooling.environment_key(b"first manifest"))
        self.assertNotEqual(first, tooling.environment_key(b"updated manifest"))

    def test_managed_chess_pin_matches_historical_match_requirement(self):
        packages = json.loads(tooling.MANIFEST.read_text())["packages"]
        chess = [asset for asset in packages if asset["name"] == "chess"]
        self.assertEqual(len(chess), 1)
        requirements = [line.strip() for line in (ROOT / "requirements-match.txt").read_text().splitlines()
                        if line.strip() and not line.lstrip().startswith("#")]
        self.assertIn("chess==" + chess[0]["version"], requirements)

    def test_python_path_uses_current_platform_layout(self):
        root = Path("environment with spaces")
        expected = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.assertEqual(tooling.python_path(root), expected)

    def test_missing_script_does_not_attempt_setup(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(tooling, "ensure_environment") as setup:
            with self.assertRaises(tooling.ToolingError):
                tooling.run_script(Path(directory) / "missing.py", [])
            setup.assert_not_called()

    def test_child_keeps_arguments_working_directory_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix="launcher fixture ") as directory:
            root = Path(directory)
            script = root / "argument probe.py"
            script.write_text(
                "import json, os, sys\n"
                "print(json.dumps({'arguments': sys.argv[1:], 'cwd': os.getcwd(), "
                "'interpreter': sys.executable}))\n"
                "print('stderr remains stderr', file=sys.stderr)\n"
                "raise SystemExit(7)\n", encoding="utf-8")
            arguments = ["with spaces", "olive 🫒", "--flag", "$(not-a-command)"]
            source = (
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
                "from pathlib import Path\nimport tooling\n"
                "tooling.ensure_environment = lambda **kwargs: Path(sys.executable)\n"
                f"raise SystemExit(tooling.run_script(Path({str(script)!r}), {arguments!r}))\n"
            )
            result = subprocess.run([sys.executable, "-c", source], cwd=root,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 7, result.stderr)
            record = json.loads(result.stdout)
            self.assertEqual(record["arguments"], arguments)
            self.assertEqual(Path(record["cwd"]).resolve(), root.resolve())
            self.assertEqual(Path(record["interpreter"]), Path(sys.executable))
            self.assertIn("stderr remains stderr", result.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX CLI process handoff; native Windows remains separate")
    def test_cli_handoff_preserves_pid_and_sigterm_stops_actual_tool(self):
        with tempfile.TemporaryDirectory(prefix="launcher cancellation ") as directory:
            root = Path(directory)
            script, ready = root / "waiting tool.py", root / "ready"
            script.write_text(
                "import os, signal\nfrom pathlib import Path\n"
                f"temporary = Path({str(ready.with_suffix('.part'))!r})\n"
                "temporary.write_text(str(os.getpid()))\n"
                f"temporary.replace({str(ready)!r})\n"
                "signal.pause()\n", encoding="utf-8")
            source = (
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'tools')!r})\n"
                "from pathlib import Path\nimport tooling\n"
                "tooling.ensure_environment = lambda **kwargs: Path(sys.executable)\n"
                f"tooling.run_script(Path({str(script)!r}), [], replace_process=True)\n"
            )
            process = subprocess.Popen([sys.executable, "-c", source],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            child_pid = None
            try:
                deadline = time.monotonic() + 3
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "tool did not reach its ready marker")
                child_pid = int(ready.read_text())
                self.assertEqual(child_pid, process.pid, "launcher retained a separate tool child")
                process.terminate()
                process.communicate(timeout=3)
                self.assertEqual(process.returncode, -signal.SIGTERM)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=3)
                # If a regression creates a child, clean up that fixture too.
                if child_pid is not None and child_pid != process.pid:
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(child_pid, signal.SIGTERM)

    def test_subprocess_signal_status_has_shell_exit_convention(self):
        with mock.patch.object(tooling, "ensure_environment", return_value=Path(sys.executable)), \
                mock.patch.object(tooling.subprocess, "call", return_value=-signal.SIGTERM):
            self.assertEqual(tooling.run_script(Path(__file__), []), 128 + signal.SIGTERM)

    def test_importing_batch_does_not_trigger_setup(self):
        chess = ModuleType("chess")
        chess.engine = ModuleType("chess.engine")
        with mock.patch.dict(sys.modules, {"chess": chess, "chess.engine": chess.engine}), \
                mock.patch.object(tooling, "direct_entry") as entry, \
                mock.patch.object(tooling, "ensure_environment") as setup:
            module = runpy.run_path(str(ROOT / "tools/batch_positions.py"), run_name="batch_import_probe")
        entry.assert_not_called()
        setup.assert_not_called()
        self.assertEqual(len(module["FENS"]), 39)

    def test_stale_managed_marker_delegates_to_current_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "chess0live-owner").write_text("old-environment-key")
            (root / "ready").write_text("old-environment-key")
            with mock.patch.object(sys, "prefix", directory), \
                    mock.patch.object(sys, "argv", ["batch_positions.py", "engine with spaces"]), \
                    mock.patch.object(importlib.metadata, "version", return_value="1.11.2"), \
                    mock.patch.object(tooling, "run_script", return_value=7) as launch, \
                    self.assertRaises(SystemExit) as stopped:
                tooling.direct_entry("batch_positions.py")
            self.assertEqual(stopped.exception.code, 7)
            launch.assert_called_once_with(Path("batch_positions.py"), ["engine with spaces"],
                                           replace_process=True)

    def test_current_managed_marker_does_not_relaunch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = tooling.environment_key(tooling.MANIFEST.read_bytes())
            (root / "chess0live-owner").write_text(key)
            (root / "ready").write_text(key)
            with mock.patch.object(sys, "prefix", directory), \
                    mock.patch.object(importlib.metadata, "version", return_value="1.11.2"), \
                    mock.patch.object(tooling, "run_script") as launch:
                tooling.direct_entry("batch_positions.py")
            launch.assert_not_called()


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.main = runpy.run_path(str(ROOT / "tools/run.py"), run_name="launcher_import_probe")["main"]

    def test_missing_script_and_setup_misuse_fail_without_setup(self):
        for arguments in ([], ["--setup", "tools/batch_positions.py"]):
            setup = mock.Mock()
            with self.subTest(arguments=arguments), \
                    mock.patch.object(sys, "argv", ["tools/run.py", *arguments]), \
                    mock.patch.dict(self.main.__globals__, ensure_environment=setup), \
                    contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as stopped:
                self.main()
            self.assertEqual(stopped.exception.code, 2)
            setup.assert_not_called()

    def test_invalid_script_rejected_before_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "not a Python script.txt"
            invalid.write_text("fixture")
            for script in (invalid, Path(directory) / "missing.py"):
                with self.subTest(script=script), \
                        mock.patch.object(sys, "argv", ["tools/run.py", str(script)]), \
                        mock.patch.object(tooling, "ensure_environment") as setup, \
                        self.assertRaises(tooling.ToolingError):
                    self.main()
                setup.assert_not_called()

    def test_tool_options_are_forwarded_after_script(self):
        args = ["--output", "file with spaces.json", "--setup"]
        launch = mock.Mock(return_value=8)
        with mock.patch.object(sys, "argv", ["tools/run.py", "--offline", "tools/probe.py", *args]), \
                mock.patch.dict(self.main.__globals__, run_script=launch):
            self.assertEqual(self.main(), 8)
        launch.assert_called_once_with("tools/probe.py", args, offline=True, replace_process=True)


if __name__ == "__main__":
    unittest.main()
