#!/usr/bin/env python3
"""Engine-free checks for byte-exact, bounded macOS power evidence collection.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mac_power_evidence as power


def completed(stdout=b"", stderr=b"", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class PowerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.start = dt.datetime(2026, 11, 4, 10, 0, tzinfo=dt.timezone.utc)
        self.end = self.start + dt.timedelta(minutes=5)

    def read_json(self, name):
        return json.loads((self.directory / name).read_text(encoding="utf-8"))

    def assert_raw(self, receipt, stdout, stderr):
        for stream, data in (("stdout", stdout), ("stderr", stderr)):
            self.assertEqual((self.directory / receipt[stream + "_file"]).read_bytes(), data)
            self.assertEqual(receipt[stream + "_bytes"], len(data))
            self.assertEqual(receipt[stream + "_sha256"], hashlib.sha256(data).hexdigest())

    def assert_binary_call(self, call, command, timeout):
        self.assertEqual(call.args, (["/usr/bin/pmset", "-g", command],))
        self.assertEqual(call.kwargs, {"capture_output": True, "timeout": timeout})

    def test_host_invalid_assertion_bytes_are_preserved_and_escaped(self):
        output = b"Assertion owner: \xd5\nPreventUserIdleSystemSleep 1\n"
        error = b"diagnostic \xd5\n"
        responses = [completed(b"AC Power\n"), completed(b"lowpowermode 0\n"),
                     completed(b"No thermal warning\n"), completed(output, error)]
        with mock.patch.object(power.subprocess, "run", side_effect=responses) as run:
            result = power.host(self.directory, "before")
        self.assertEqual(list(result), ["battery", "power", "thermal", "assertions"])
        entry = result["assertions"]
        self.assert_raw(entry, output, error)
        self.assertFalse(entry["stdout_valid_utf8"])
        self.assertFalse(entry["stderr_valid_utf8"])
        self.assertEqual(entry["status"], "complete")
        self.assertEqual(entry["exit_code"], 0)
        self.assertEqual(entry["file"], "before-assertions.txt")
        self.assertEqual((self.directory / entry["file"]).read_text(encoding="utf-8"),
                         "Assertion owner: \\xd5\nPreventUserIdleSystemSleep 1\ndiagnostic \\xd5\n")
        saved = self.read_json(entry["command_receipt_file"])
        self.assertEqual(saved["stdout_sha256"], entry["stdout_sha256"])
        for call, command in zip(run.call_args_list, ("batt", "custom", "therm", "assertions")):
            self.assert_binary_call(call, command, 15)

    def test_host_endpoint_names_and_valid_utf8_are_compatible(self):
        output = "AC Power – Automatic\n".encode("utf-8")
        with mock.patch.object(power.subprocess, "run", return_value=completed(output)) as run:
            before = power.host(self.directory, "before")
            after = power.host(self.directory, "after")
        self.assertEqual(run.call_count, 8)
        for label, result in (("before", before), ("after", after)):
            for name in ("battery", "power", "thermal", "assertions"):
                entry = result[name]
                self.assertEqual(entry["file"], f"{label}-{name}.txt")
                self.assertEqual((self.directory / entry["file"]).read_bytes(), output)
                self.assertTrue(entry["stdout_valid_utf8"])
                self.assert_raw(entry, output, b"")

    def test_sleep_bad_bytes_inside_and_outside_events_preserve_ascii_records(self):
        raw = (b"unrelated vendor owner \xd5\n"
               b"2026-11-04 12:00:00 +0200 Sleep Entering Sleep owner=\xd5\n"
               b"2026-11-04 10:02:00 +0000 DarkWake normal wake\n"
               b"2026-11-04 12:05:00 +0200 Wake completed\n"
               b"2026-11-04 12:05:01 +0200 Sleep outside\n"
               b"2026-11-04 11:59:59 +0200 Wake outside\n"
               b"2026-11-04 12:03:00 +0200 Battery non-event \xd5\n")
        error = b"log warning \xd5\n"
        with mock.patch.object(power.subprocess, "run", return_value=completed(raw, error)) as run:
            result = power.sleep_events(self.directory, self.start, self.end)
        self.assert_raw(result, raw, error)
        self.assertEqual(result["events"], [
            "2026-11-04 12:00:00 +0200 Sleep Entering Sleep owner=\\xd5",
            "2026-11-04 10:02:00 +0000 DarkWake normal wake",
            "2026-11-04 12:05:00 +0200 Wake completed"])
        self.assertEqual((self.directory / "sleep-log.txt").read_text(encoding="utf-8"),
                         raw.decode("utf-8", errors="backslashreplace"))
        self.assertEqual((self.directory / "sleep-log-stderr.txt").read_text(encoding="utf-8"),
                         "log warning \\xd5\n")
        self.assertEqual((self.directory / "sleep-wake-events.txt").read_text(encoding="utf-8"),
                         "\n".join(result["events"]) + "\n")
        self.assertEqual(self.read_json("sleep-events.json")["events"], result["events"])
        self.assert_binary_call(run.call_args, "log", 30)

    def test_sleep_valid_utf8_remains_readable_and_old_categories_are_retained(self):
        raw = ("2026-11-04 12:00:00 +0200 Hibernate résumé\n"
               "2026-11-04 12:01:00 +0200 Start café\n"
               "2026-11-04 12:02:00 +0200 Assertions Prevent Sleep\n"
               "2026-11-04 12:03:00 +0200 wake lowercase\n"
               "2026-11-04 12:04:00 +0200 Sleepiness is not a category\n").encode("utf-8")
        with mock.patch.object(power.subprocess, "run", return_value=completed(raw)):
            result = power.sleep_events(self.directory, self.start, self.end)
        self.assertTrue(result["stdout_valid_utf8"])
        self.assertEqual(len(result["events"]), 4)
        self.assertEqual((self.directory / "sleep-log.txt").read_bytes(), raw)
        self.assertIn("Hibernate résumé", result["events"][0])

    def test_malformed_unrelated_lines_are_ignored_without_losing_raw_evidence(self):
        raw = (b"Sleep with no timestamp is unrelated free text\n"
               b"2026-99-99 99:99:99 +9999 Battery unrelated malformed timestamp\n"
               b"2026-11-04 12:02:00 +0200 Wake normal\n")
        with mock.patch.object(power.subprocess, "run", return_value=completed(raw)):
            result = power.sleep_events(self.directory, self.start, self.end)
        self.assertEqual(result["malformed_relevant_lines"], [])
        self.assertEqual(result["events"], ["2026-11-04 12:02:00 +0200 Wake normal"])
        self.assert_raw(result, raw, b"")

    def test_malformed_potential_event_fails_after_preserving_evidence(self):
        raw = b"2026-99-99 12:02:00 +0200 Sleep potentially relevant\n"
        with mock.patch.object(power.subprocess, "run", return_value=completed(raw)):
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.sleep_events(self.directory, self.start, self.end)
        result = caught.exception.receipt
        self.assert_raw(result, raw, b"")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["malformed_relevant_lines"][0]["line_number"], 1)
        self.assertEqual(self.read_json("sleep-events.json")["status"], "failed")

    def test_empty_success_is_explicit_and_has_all_sleep_files(self):
        with mock.patch.object(power.subprocess, "run", return_value=completed()):
            result = power.sleep_events(self.directory, self.start, self.end)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["status"], "complete")
        for name in ("sleep-log.txt", "sleep-log-stderr.txt", "sleep-wake-events.txt"):
            self.assertEqual((self.directory / name).read_bytes(), b"")

    def test_host_nonzero_preserves_failed_bytes_and_stops_collection(self):
        stdout, stderr = b"partial \xd5\n", b"permission denied\n"
        with mock.patch.object(power.subprocess, "run", return_value=completed(stdout, stderr, 4)) as run:
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.host(self.directory, "after")
        run.assert_called_once()
        entry = caught.exception.receipt["battery"]
        self.assert_raw(entry, stdout, stderr)
        self.assertEqual(entry["exit_code"], 4)
        self.assertEqual(entry["status"], "failed")
        self.assertTrue((self.directory / "after-battery.txt").exists())
        self.assertEqual(self.read_json("after-battery.command.json")["status"], "failed")

    def test_sleep_nonzero_cannot_look_like_successful_empty_events(self):
        stdout, stderr = b"unrelated \xd5\n", b"pmset failed\n"
        with mock.patch.object(power.subprocess, "run", return_value=completed(stdout, stderr, 3)):
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.sleep_events(self.directory, self.start, self.end)
        result = caught.exception.receipt
        self.assert_raw(result, stdout, stderr)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 3)
        self.assertEqual(result["events"], [])
        self.assertEqual(self.read_json("sleep-events.json")["status"], "failed")

    def test_host_timeout_preserves_partial_output_with_bounded_deadline(self):
        error = subprocess.TimeoutExpired(["pmset"], 15, output=b"partial \xd5", stderr=b"warning")
        with mock.patch.object(power.subprocess, "run", side_effect=error) as run:
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.host(self.directory, "before")
        entry = caught.exception.receipt["battery"]
        self.assert_raw(entry, b"partial \xd5", b"warning")
        self.assertIsNone(entry["exit_code"])
        self.assertEqual(entry["status"], "failed")
        self.assert_binary_call(run.call_args, "batt", 15)

    def test_sleep_timeout_preserves_partial_events_with_bounded_deadline(self):
        raw = b"2026-11-04 12:02:00 +0200 Wake partial \xd5\n"
        error = subprocess.TimeoutExpired(["pmset"], 30, output=raw, stderr=None)
        with mock.patch.object(power.subprocess, "run", side_effect=error) as run:
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.sleep_events(self.directory, self.start, self.end)
        result = caught.exception.receipt
        self.assert_raw(result, raw, b"")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["events"]), 1)
        self.assertIn("timed out", result["error"])
        self.assert_binary_call(run.call_args, "log", 30)

    def test_launch_error_is_recorded_and_raised(self):
        with mock.patch.object(power.subprocess, "run", side_effect=FileNotFoundError("missing pmset")):
            with self.assertRaises(power.PowerEvidenceError) as caught:
                power.host(self.directory, "before")
        entry = caught.exception.receipt["battery"]
        self.assert_raw(entry, b"", b"")
        self.assertEqual(entry["status"], "failed")
        self.assertIn("FileNotFoundError", entry["error"])

    def test_existing_endpoint_evidence_is_never_overwritten(self):
        existing = self.directory / "before-battery.txt"
        existing.write_bytes(b"preserve me")
        with mock.patch.object(power.subprocess, "run") as run:
            with self.assertRaises(FileExistsError):
                power.host(self.directory, "before")
        run.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"preserve me")

    def test_existing_raw_sleep_evidence_is_never_overwritten(self):
        existing = self.directory / "sleep-log.stdout.bin"
        existing.write_bytes(b"preserve \xd5")
        with mock.patch.object(power.subprocess, "run") as run:
            with self.assertRaises(FileExistsError):
                power.sleep_events(self.directory, self.start, self.end)
        run.assert_not_called()
        self.assertEqual(existing.read_bytes(), b"preserve \xd5")

    def test_invalid_inputs_do_not_run_commands(self):
        with mock.patch.object(power.subprocess, "run") as run:
            for label in ("../outside", "", "bad/label"):
                with self.assertRaises(ValueError):
                    power.host(self.directory, label)
            for start, end in ((self.end, self.start), (self.start.replace(tzinfo=None), self.end),
                               (self.start, self.end.replace(tzinfo=None)), (None, self.end)):
                with self.assertRaises(ValueError):
                    power.sleep_events(self.directory, start, end)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
