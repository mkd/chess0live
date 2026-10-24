#!/usr/bin/env python3
"""Engine-free tests of runtime evidence, launch arguments and failure cleanup.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "verify_runtime", Path(__file__).resolve().parents[1] / "tools" / "verify_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)

# The runner uses the Python interpreter explicitly, making fixtures portable
# without shell scripts, executable-bit assumptions, or Windows file associations.
RUNNER = """import sys
from pathlib import Path
path = sys.argv[1]
sys.argv = sys.argv[1:]
exec(compile(Path(path).read_bytes()[64:].decode(), path, 'exec'), {'__name__':'__main__', '__file__':path})
"""
FAKE_UCI = """import sys
def emit(line): print(line, flush=True)
def result():
    emit('info string smp v1 threads 2 total_nodes 30 leader_nodes 20 worker_nodes 20,10 worker_depths 3,3')
    emit('bestmove e2e4 ponder e7e5')
for line in sys.stdin:
    command = line.strip()
    if command == 'uci':
        emit('id name chess0live fake runtime fixture')
        for name, kind in [('Threads', 'spin'), ('Hash', 'spin'), ('EvalFile', 'string'), ('Search Diagnostics', 'check')]:
            emit('option name ' + name + ' type ' + kind)
        emit('uciok')
    elif command == 'isready': emit('readyok')
    elif command == 'perft 3': emit('nodes 8902 time 1')
    elif command == 'go depth 3':
        emit('info depth 3 score cp 10 nodes 30 time 1 nps 30000 pv e2e4 e7e5')
        result()
    elif command == 'go infinite':
        emit('info depth 3 score cp 10 nodes 30 time 1 nps 30000 pv e2e4 e7e5')
    elif command == 'stop': result()
    elif command == 'quit': break
"""


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="runtime fixture ")
        self.root = Path(self.temporary.name).resolve()
        self.build = self.root / "build with spaces"
        self.build.mkdir()
        self.network = self.root / "network with spaces.nnue"
        self.network.write_bytes(b"pinned fake network\n")
        (self.root / "networks").mkdir()
        manifest = {"sha256": hashlib.sha256(self.network.read_bytes()).hexdigest(),
                    "size_bytes": self.network.stat().st_size, "filename": self.network.name}
        (self.root / "networks" / "manifest.json").write_text(json.dumps(manifest))
        stamp = {"target": "linux-arm64", "compiler": ["compiler with spaces", "--target=aarch64"],
                 "flags": ["-std=c++2c", "-O3"], "link_flags": "-pthread"}
        (self.build / "toolchain.ok").write_text(json.dumps(stamp))
        self.runner = self.root / "runner with spaces.py"
        self.runner.write_text(RUNNER)
        for name, marker in runtime.CHECKS:
            self.write_fixture(name, "print(" + repr(marker + " fake fixture") + ")\n")
        self.write_fixture("chess0live", FAKE_UCI)
        self.args = argparse.Namespace(build=str(self.build), target="linux-arm64",
            network=str(self.network), execution="emulator",
            runner_json=json.dumps([sys.executable, str(self.runner)]),
            output=str(self.root / "evidence with spaces"), timeout=3.0)
        self.root_patch = patch.object(runtime, "ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def run_fixture(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result = runtime.verify(self.args)
        report = json.loads((Path(self.args.output) / "report.json").read_text())
        self.assertEqual(result, int(report["status"] != "passed"))
        return report

    def write_fixture(self, name, source):
        header = bytearray(64)
        header[:6] = b"\x7fELF\x02\x01"
        header[18:20] = (183).to_bytes(2, "little")
        (self.build / name).write_bytes(header + source.encode())

    def failed_report(self, contains):
        report = self.run_fixture()
        self.assertEqual(report["status"], "failed")
        self.assertIn(contains, report["error"])
        return report

    def test_all_checks_and_argument_boundaries(self):
        report = self.run_fixture()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["checks"]), 8)
        self.assertEqual(report["schema"], "chess0live.runtime.v1")
        self.assertEqual(report["declared_execution"], "emulator")
        self.assertEqual(report["runner_argv"], [sys.executable, str(self.runner)])
        self.assertEqual(report["toolchain"]["configuration"]["compiler"][0], "compiler with spaces")
        self.assertEqual(report["network"]["sha256"], runtime.fingerprint(self.network)["sha256"])
        self.assertEqual(set(report["binaries"]), {name for name, _ in runtime.CHECKS} | {"uci"})
        for check in report["checks"]:
            self.assertEqual(check["status"], "passed")
            self.assertEqual(check["exit_code"], 0)
            self.assertTrue(Path(check["output_log"]).exists())
        self.assertEqual(report["checks"][1]["argv"][-2:], ["--network", str(self.network)])
        self.assertEqual(report["checks"][4]["argv"][-1], str(self.network))
        self.assertEqual(report["checks"][-1]["searches"][1]["worker_nodes"], [20, 10])

    def test_missing_binary_fails_before_any_child(self):
        (self.build / "search-test").unlink()
        report = self.failed_report("FileNotFoundError")
        self.assertEqual(report["checks"], [])

    def test_wrong_network_fails_before_any_child(self):
        self.network.write_bytes(b"wrong network")
        report = self.failed_report("pinned manifest")
        self.assertEqual(report["checks"], [])

    def test_stamp_target_mismatch(self):
        self.args.target = "linux-x86_64"
        self.failed_report("toolchain stamp")

    def test_stamp_metadata_missing(self):
        (self.build / "toolchain.ok").write_text('{"target":"linux-arm64"}')
        self.failed_report("toolchain stamp")

    def test_unknown_target_and_execution(self):
        for field, value in (("target", "macos-x86_64"), ("execution", "container")):
            with self.subTest(field=field):
                previous = getattr(self.args, field)
                setattr(self.args, field, value)
                self.args.output = str(self.root / field)
                self.failed_report("unsupported")
                setattr(self.args, field, previous)

    def test_runner_validation(self):
        for index, value in enumerate((None, "[]", '"shell command"', "[1]", '[""]',
                                       '["line\\nbreak"]', "not JSON")):
            with self.subTest(value=value):
                self.args.runner_json = value
                self.args.output = str(self.root / ("runner-" + str(index)))
                report = self.run_fixture()
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["checks"], [])

    def test_native_and_vm_require_matching_host_and_no_runner(self):
        for mode in ("native", "VM"):
            with self.subTest(mode=mode):
                self.args.execution = mode
                self.args.runner_json = None
                self.args.output = str(self.root / (mode + "-host"))
                with patch.object(runtime, "host_identity", return_value={"target": "windows-arm64"}):
                    self.failed_report("does not match")
                self.args.runner_json = json.dumps([sys.executable])
                self.args.output = str(self.root / (mode + "-runner"))
                with patch.object(runtime, "host_identity", return_value={"target": "linux-arm64"}):
                    self.failed_report("without a runner")

    def test_matching_host_preserves_explicit_native_or_vm_label(self):
        original_launch = runtime.launch
        for mode in ("native", "VM"):
            with self.subTest(mode=mode):
                self.args.execution = mode
                self.args.runner_json = None
                self.args.output = str(self.root / (mode + "-declared"))
                with patch.object(runtime, "host_identity", return_value={"target": "linux-arm64"}), \
                        patch.object(runtime, "launch", side_effect=lambda argv, **kwargs:
                                     original_launch([sys.executable, str(self.runner)] + argv, **kwargs)):
                    report = self.run_fixture()
                self.assertEqual(report["status"], "passed")
                self.assertEqual(report["declared_execution"], mode)
                self.assertEqual(report["runner_argv"], [])

    def test_positive_finite_timeout(self):
        for value in ("0", "-1", "nan", "inf", "-inf"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                runtime.positive_timeout(value)
        self.assertEqual(runtime.positive_timeout("1.5"), 1.5)

    def test_child_failure_is_fail_fast_with_log(self):
        self.write_fixture("position-test", "print('deliberate failure', flush=True)\nraise SystemExit(7)\n")
        report = self.failed_report("exited 7")
        self.assertEqual(len(report["checks"]), 1)
        self.assertEqual(report["checks"][0]["exit_code"], 7)
        self.assertIn("deliberate failure", Path(report["checks"][0]["output_log"]).read_text())

    def test_zero_exit_without_marker_is_failure(self):
        self.write_fixture("position-test", "print('wrong program')\n")
        self.failed_report("completion marker")

    def test_skipped_check_is_failure(self):
        self.write_fixture("position-test", "print('position tests passed: fixture')\nprint('SKIP real checks')\n")
        self.failed_report("skipped")

    def test_child_timeout_reaps_process(self):
        pid_path = self.root / "child.pid"
        self.write_fixture("position-test", 
            "import os, time\nfrom pathlib import Path\nPath(" + repr(str(pid_path)) +
            ").write_text(str(os.getpid()))\ntime.sleep(20)\n")
        self.args.timeout = 0.3
        before = time.monotonic()
        report = self.failed_report("TimeoutExpired")
        self.assertLess(time.monotonic() - before, 4)
        self.assertIsNotNone(report["checks"][0]["exit_code"])
        if os.name == "posix":
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_path.read_text()), 0)

    def test_launcher_failure_is_recorded(self):
        self.args.runner_json = json.dumps([str(self.root / "missing launcher")])
        report = self.failed_report("FileNotFoundError")
        self.assertEqual(len(report["checks"]), 1)
        self.assertIsNone(report["checks"][0]["exit_code"])

    def test_uci_timeout_reaps_process(self):
        pid_path = self.root / "uci.pid"
        self.write_fixture("chess0live", 
            "import os, time\nfrom pathlib import Path\nPath(" + repr(str(pid_path)) +
            ").write_text(str(os.getpid()))\ntime.sleep(20)\n")
        self.args.timeout = 0.3
        report = self.failed_report("UCI timeout")
        self.assertEqual(len(report["checks"]), 8)
        if os.name == "posix":
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_path.read_text()), 0)

    def test_bad_perft_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace("nodes 8902", "nodes 8901"))
        self.failed_report("perft(3) mismatch")

    def test_uci_error_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace(
            "emit('nodes 8902 time 1')", "emit('info string error: fake error')"))
        self.failed_report("fake error")

    def test_illegal_bestmove_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace("bestmove e2e4", "bestmove e2e5"))
        self.failed_report("legal start-position")

    def test_inactive_second_worker_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace(
            "total_nodes 30 leader_nodes 20 worker_nodes 20,10", "total_nodes 20 leader_nodes 20 worker_nodes 20,0"))
        self.failed_report("actual activity from both workers")

    def test_malformed_worker_accounting_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace("total_nodes 30", "total_nodes 31"))
        self.failed_report("accounting failed")

    def test_early_infinite_bestmove_fails(self):
        self.write_fixture("chess0live", FAKE_UCI.replace(
            "elif command == 'go infinite':", "elif command == 'go infinite':\n        result()"))
        self.failed_report("infinite search ended before stop")

    def test_artifact_drift_rejected(self):
        self.write_fixture("position-test", "from pathlib import Path\np = Path(__file__)\nprint('position tests passed: fake fixture')\n"
                        "p.write_bytes(p.read_bytes() + b'# changed\\n')\n")
        self.failed_report("binary changed during checks")

    def test_renamed_foreign_binary_rejected_before_launch(self):
        path = self.build / "search-test"
        data = bytearray(path.read_bytes())
        data[18:20] = (62).to_bytes(2, "little")
        path.write_bytes(data)
        report = self.failed_report("does not match linux-arm64")
        self.assertEqual(report["checks"], [])

    def test_raw_headers_for_all_supported_targets(self):
        path = self.root / "synthetic binary"
        for target in runtime.TARGETS:
            with self.subTest(target=target):
                header = bytearray(64)
                if target.startswith("linux-"):
                    header[:6] = b"\x7fELF\x02\x01"
                    machine = {"linux-x86_64": 62, "linux-arm64": 183, "linux-riscv64": 243}[target]
                    header[18:20] = machine.to_bytes(2, "little")
                elif target.startswith("macos-"):
                    header[:4] = b"\xcf\xfa\xed\xfe"
                    header[4:8] = (0x0100000C).to_bytes(4, "little")
                else:
                    header[:2] = b"MZ"
                    header[60:64] = (64).to_bytes(4, "little")
                    pe = bytearray(264)
                    pe[:4] = b"PE\0\0"
                    machine = 0x8664 if target.endswith("x86_64") else 0xAA64
                    pe[4:6] = machine.to_bytes(2, "little")
                    pe[20:22] = (240).to_bytes(2, "little")
                    pe[24:26] = b"\x0b\x02"
                    header += pe
                path.write_bytes(header)
                self.assertEqual(runtime.binary_identity(path, target)["target"], target)
                other = "macos-arm64" if target != "macos-arm64" else "linux-arm64"
                with self.assertRaises(ValueError):
                    runtime.binary_identity(path, other)
                # The right OS/container format with a different CPU must also
                # fail; binfmt support is not evidence of the requested target.
                wrong_machine = bytearray(header)
                if target.startswith("linux-"):
                    wrong_machine[18:20] = (0).to_bytes(2, "little")
                elif target.startswith("macos-"):
                    wrong_machine[4:8] = (0x01000007).to_bytes(4, "little")
                else:
                    wrong_machine[68:70] = (0).to_bytes(2, "little")
                path.write_bytes(wrong_machine)
                with self.assertRaises(ValueError):
                    runtime.binary_identity(path, target)

    def test_truncated_and_wrong_class_headers(self):
        path = self.root / "bad executable"
        for data in (b"", b"MZ", b"\x7fELF\x01\x01" + bytes(58),
                     b"\x7fELF\x02\x02" + bytes(58)):
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                runtime.binary_identity(path, "linux-arm64")

    def test_invalid_pe_offset_and_optional_header(self):
        path = self.root / "bad.exe"
        header = bytearray(90)
        header[:2] = b"MZ"
        header[60:64] = (0xFFFFFFFF).to_bytes(4, "little")
        path.write_bytes(header)
        with self.assertRaisesRegex(ValueError, "offset"):
            runtime.binary_identity(path, "windows-arm64")
        header[60:64] = (64).to_bytes(4, "little")
        header[64:68] = b"PE\0\0"
        header[68:70] = (0xAA64).to_bytes(2, "little")
        header[84:86] = (2).to_bytes(2, "little")
        header[88:90] = b"\x0b\x01"  # PE32 rather than PE32+.
        path.write_bytes(header)
        with self.assertRaisesRegex(ValueError, r"PE32\+"):
            runtime.binary_identity(path, "windows-arm64")

    def test_existing_report_directory_not_overwritten(self):
        Path(self.args.output).mkdir()
        marker = Path(self.args.output) / "report.json"
        marker.write_text("keep me")
        with self.assertRaises(FileExistsError):
            runtime.verify(self.args)
        self.assertEqual(marker.read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()
