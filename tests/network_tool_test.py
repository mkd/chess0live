#!/usr/bin/env python3
"""Exercise network inspection and provenance with small, independent fixtures.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The synthetic files deliberately stop after their headers. Recognizing one
must never imply that its missing weights or evaluation have been verified.
No engine, compiler, network download or third-party Python package is needed.
"""
from argparse import Namespace
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import network as tool


def header(description=b"Independent synthetic test", *, version=0x6A448AFA,
           architecture=0xA85B2205, transformer=0xCB685313):
    """Encode only observed format identifiers, never actual network weights."""
    return (struct.pack("<III", version, architecture, len(description))
            + description + struct.pack("<I", transformer))


class NetworkFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="network inspection ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.network = self.root / "candidate with spaces.nnue"
        self.network.write_bytes(header())
        self.digest = hashlib.sha256(self.network.read_bytes()).hexdigest()

    def metadata(self, **changes):
        value = {"schema_version": 1, "network_sha256": self.digest,
                 "name": "Test candidate", "author": "Test author",
                 "license": None, "source": None,
                 "training": {"games": None, "positions": None, "epochs": None}}
        value.update(changes)
        path = self.root / "metadata.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def cli(self, *arguments):
        return subprocess.run([sys.executable, str(ROOT / "tools/network.py"),
                               *map(str, arguments)], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=15)


class InspectionTests(NetworkFixture):
    def test_header_identity_is_not_full_compatibility(self):
        report = tool.inspect_network(self.network)
        self.assertEqual(report["artifact"]["sha256"], self.digest)
        self.assertEqual(report["artifact"]["size_bytes"], self.network.stat().st_size)
        self.assertEqual(Path(report["artifact"]["path"]), self.network.resolve())
        self.assertEqual(report["architecture"]["status"], "recognized_header")
        self.assertEqual(report["architecture"]["name"], "SFNNv16")
        self.assertEqual(report["verification"]["independent_oracle"], "not_run")
        self.assertEqual(report["verification"]["playing_strength"], "not_measured")

    def test_unknown_training_counts_are_not_invented(self):
        self.network.write_bytes(header(b"Stockfish 19; trained on 999999 games; Elo 4000"))
        report = tool.inspect_network(self.network)
        self.assertEqual(report["provenance"]["source"], "unknown")
        for field in ("games", "positions", "epochs"):
            self.assertIsNone(report["provenance"]["training"][field])

    def test_familiar_filename_does_not_establish_provenance(self):
        named = self.root / "nn-1a298aa575a0.nnue"
        named.write_bytes(self.network.read_bytes())
        report = tool.inspect_network(named)
        self.assertEqual(report["provenance"]["source"], "unknown")

    def test_fingerprint_covers_bytes_beyond_header(self):
        old = tool.inspect_network(self.network)["artifact"]["sha256"]
        self.network.write_bytes(self.network.read_bytes() + b"unvalidated weights")
        report = tool.inspect_network(self.network)
        self.assertNotEqual(report["artifact"]["sha256"], old)
        self.assertEqual(report["artifact"]["sha256"],
                         hashlib.sha256(self.network.read_bytes()).hexdigest())
        self.assertEqual(report["verification"]["independent_oracle"], "not_run")

    def test_filename_extension_does_not_define_architecture(self):
        renamed = self.root / "candidate.bin"
        renamed.write_bytes(self.network.read_bytes())
        self.assertEqual(tool.inspect_network(renamed)["architecture"]["status"],
                         "recognized_header")

    def test_unrecognized_identifiers_are_unsupported(self):
        for field in ("version", "architecture", "transformer"):
            with self.subTest(field=field):
                self.network.write_bytes(header(**{field: 0}))
                report = tool.inspect_network(self.network)
                self.assertEqual(report["architecture"]["status"], "unsupported")
                self.assertNotEqual(report["architecture"].get("name"), "SFNNv16")
                self.assertEqual(report["verification"]["independent_oracle"], "not_run")

    def test_truncated_headers_are_malformed(self):
        complete = header()
        for count in (0, 1, 4, 8, 11, 12, len(complete) - 1):
            with self.subTest(bytes=count):
                self.network.write_bytes(complete[:count])
                self.assertEqual(tool.inspect_network(self.network)["architecture"]["status"],
                                 "malformed")

    def test_description_length_is_bounded(self):
        self.network.write_bytes(struct.pack("<III", 0x6A448AFA, 0xA85B2205,
                                             1024 * 1024 + 1))
        self.assertEqual(tool.inspect_network(self.network)["architecture"]["status"],
                         "malformed")

    def test_non_utf8_description_cannot_crash_inspection(self):
        self.network.write_bytes(header(b"name\xff\xfe"))
        report = tool.inspect_network(self.network)
        self.assertEqual(report["architecture"]["status"], "recognized_header")
        self.assertIsInstance(report["architecture"]["description"], str)

    def test_missing_file_and_directory_fail_explicitly(self):
        for path in (self.root / "missing.nnue", self.root):
            with self.subTest(path=path), self.assertRaises(tool.NetworkToolError):
                tool.inspect_network(path)


class MetadataTests(NetworkFixture):
    def test_declarations_are_attributed_without_verification(self):
        path = self.metadata(training={"games": 20, "positions": 1000, "epochs": 2})
        report = tool.inspect_network(self.network, path)
        self.assertEqual(report["provenance"]["source"], "declared_unverified")
        self.assertEqual(report["provenance"]["training"]["games"], 20)
        self.assertEqual(report["provenance"]["training"]["positions"], 1000)
        self.assertEqual(report["provenance"]["training"]["epochs"], 2)
        self.assertEqual(report["verification"]["playing_strength"], "not_measured")

    def test_metadata_is_bound_to_complete_digest(self):
        path = self.metadata(network_sha256="0" * 64)
        with self.assertRaises(tool.NetworkToolError):
            tool.load_metadata(path, self.digest)

    def test_changed_payload_invalidates_metadata(self):
        path = self.metadata()
        self.network.write_bytes(self.network.read_bytes() + b"different payload")
        with self.assertRaises(tool.NetworkToolError):
            tool.inspect_network(self.network, path)

    def test_schema_version_must_be_supported_integer(self):
        for version in (0, 2, True, "1", None):
            with self.subTest(version=version), self.assertRaises(tool.NetworkToolError):
                tool.load_metadata(self.metadata(schema_version=version), self.digest)

    def test_negative_boolean_and_fractional_counts_are_rejected(self):
        for field in ("games", "positions", "epochs"):
            for value in (-1, True, 1.5, "100"):
                with self.subTest(field=field, value=value):
                    training = {"games": None, "positions": None, "epochs": None}
                    training[field] = value
                    with self.assertRaises(tool.NetworkToolError):
                        tool.load_metadata(self.metadata(training=training), self.digest)

    def test_zero_is_preserved_as_recorded_data(self):
        path = self.metadata(training={"games": 0, "positions": 0, "epochs": 0})
        report = tool.inspect_network(self.network, path)
        self.assertEqual(report["provenance"]["training"]["games"], 0)
        self.assertEqual(report["provenance"]["training"]["positions"], 0)
        self.assertEqual(report["provenance"]["training"]["epochs"], 0)

    def test_unknown_fields_rejected_instead_of_silently_lost(self):
        with self.assertRaises(tool.NetworkToolError):
            tool.load_metadata(self.metadata(estimated_elo=4000), self.digest)
        with self.assertRaises(tool.NetworkToolError):
            tool.load_metadata(self.metadata(training={"gamez": 100}), self.digest)

    def test_data_sources_are_recorded_as_declarations(self):
        training = {"games": None, "positions": 200, "epochs": 1,
                    "data_sources": ["Owner dataset: https://example.org/data"]}
        report = tool.inspect_network(self.network, self.metadata(training=training))
        self.assertEqual(report["provenance"]["training"]["data_sources"],
                         training["data_sources"])
        self.assertEqual(report["provenance"]["source"], "declared_unverified")

    def test_data_sources_and_identity_fields_are_typed(self):
        for value in ("dataset", [1], [None], {"source": "dataset"}):
            with self.subTest(sources=value), self.assertRaises(tool.NetworkToolError):
                tool.load_metadata(self.metadata(training={"data_sources": value}), self.digest)
        for field in ("name", "author", "license", "source"):
            with self.subTest(field=field), self.assertRaises(tool.NetworkToolError):
                tool.load_metadata(self.metadata(**{field: ["incorrect type"]}), self.digest)

    def test_nonobject_and_bad_json_fail_cleanly(self):
        path = self.root / "metadata.json"
        for payload in ("[]", "null", "true", "{not JSON"):
            with self.subTest(payload=payload):
                path.write_text(payload, encoding="utf-8")
                with self.assertRaises(tool.NetworkToolError):
                    tool.load_metadata(path, self.digest)

    def test_duplicate_metadata_keys_cannot_hide_conflicting_claims(self):
        path = self.metadata()
        text = path.read_text(encoding="utf-8")
        path.write_text(text[:-1] + ', "network_sha256": "' + self.digest + '"}',
                        encoding="utf-8")
        with self.assertRaises(tool.NetworkToolError):
            tool.load_metadata(path, self.digest)

    def test_template_preserves_unknowns_and_binds_file(self):
        path = self.root / "new metadata.json"
        tool.write_metadata_template(self.network, path)
        value = tool.load_metadata(path, self.digest)
        self.assertEqual(value["network_sha256"], self.digest)
        for field in ("games", "positions", "epochs"):
            self.assertIsNone(value["training"][field])

    def test_template_cannot_overwrite_existing_evidence(self):
        path = self.root / "existing.json"
        path.write_text("KEEP EXACTLY", encoding="utf-8")
        with self.assertRaises(tool.NetworkToolError):
            tool.write_metadata_template(self.network, path)
        self.assertEqual(path.read_text(encoding="utf-8"), "KEEP EXACTLY")


class CommandTests(NetworkFixture):
    def test_command_and_subcommand_help_work_without_setup(self):
        for arguments in (("--help",), ("inspect", "--help"),
                          ("metadata", "--help"), ("qualify", "--help")):
            with self.subTest(arguments=arguments):
                result = self.cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_inspect_writes_parseable_report_with_spaced_paths(self):
        output = self.root / "new report.json"
        result = self.cli("inspect", self.network, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["artifact"]["sha256"], self.digest)
        self.assertEqual(report["verification"]["independent_oracle"], "not_run")

    def test_inspect_output_does_not_overwrite_existing_file(self):
        output = self.root / "existing report.json"
        output.write_bytes(b"old evidence")
        result = self.cli("inspect", self.network, "--output", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"old evidence")

    def test_terminal_output_escapes_untrusted_description_controls(self):
        self.network.write_bytes(header(b"hello\nFORGED PASS\x1b[31m\r"))
        result = self.cli("inspect", self.network)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("\x1b", result.stdout)
        self.assertNotIn("\nFORGED PASS", result.stdout)

    def test_terminal_output_escapes_untrusted_path_controls(self):
        path = self.root / "candidate\nFORGED PASS.nnue"
        path.write_bytes(self.network.read_bytes())
        result = self.cli("inspect", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("\nFORGED PASS", result.stdout)
        self.assertEqual(Path(json.loads(result.stdout)["artifact"]["path"]), path.resolve())

    def test_unknown_format_can_be_inspected_but_not_qualified(self):
        self.network.write_bytes(header(version=0))
        result = self.cli("inspect", self.network)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli("qualify", self.network, "--output", self.root / "qualification",
                          "--offline")
        self.assertNotEqual(result.returncode, 0)

    def test_qualification_does_not_overwrite_previous_output(self):
        output = self.root / "qualification"
        output.mkdir()
        old = output / "report.json"
        old.write_bytes(b"previous qualification")
        result = self.cli("qualify", self.network, "--output", output, "--offline")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(old.read_bytes(), b"previous qualification")

    def test_missing_metadata_is_a_clean_cli_failure(self):
        result = self.cli("inspect", self.network, "--metadata", self.root / "absent.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


class QualificationTests(NetworkFixture):
    """Check wrapper decisions with fake oracle records, never real NNUE claims."""
    def setUp(self):
        super().setUp()
        self.arguments = Namespace(network=self.network, metadata=None,
                                   output=self.root / "new qualification",
                                   compiler=None, jobs=1,
                                   reference_dir=self.root / "reference cache", offline=True)
        self.valid = {"result": "PASS", "network_sha256": self.digest,
                      "reference_commit": tool.manifest()["reference_commit"],
                      "positions": 2057}

    def run_qualification(self, *, oracle=None, returncode=0, mutate=None, source_drift=False):
        payload = self.valid.copy() if oracle is None else oracle

        def fake_oracle(command, **kwargs):
            directory = self.arguments.output / "oracle"
            directory.mkdir()
            (directory / "report.json").write_text(json.dumps(payload), encoding="utf-8")
            if mutate:
                mutate()
            return subprocess.CompletedProcess(command, returncode)

        pins = [{"source": "before"}, {"source": "after" if source_drift else "before"}]
        with mock.patch.object(tool.shutil, "which", return_value="/fixture/compiler"), \
                mock.patch.object(tool, "run_oracle", side_effect=fake_oracle) as run, \
                mock.patch.object(tool, "source_pins", side_effect=pins), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = tool.qualify(self.arguments)
        report = json.loads((self.arguments.output / "report.json").read_text(encoding="utf-8"))
        return status, report, run

    def assert_failed(self, report):
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["verification"]["independent_oracle"], "not_run")
        self.assertEqual(report["verification"]["playing_strength"], "not_measured")

    def test_matching_complete_wrapper_identity_permits_recorded_pass(self):
        status, report, run = self.run_qualification()
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["verification"]["independent_oracle"], "passed")
        self.assertEqual(report["verification"]["playing_strength"], "not_measured")
        oracle = self.arguments.output / "oracle/report.json"
        self.assertEqual(report["oracle_report_sha256"],
                         hashlib.sha256(oracle.read_bytes()).hexdigest())
        command = run.call_args.args[0]
        self.assertIn("--offline", command)
        self.assertEqual(command[command.index("--candidate-network") + 1], str(self.network.resolve()))

    def test_wrong_network_digest_rejects_pass(self):
        status, report, _ = self.run_qualification(oracle=dict(self.valid, network_sha256="0" * 64))
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_wrong_reference_commit_rejects_pass(self):
        status, report, _ = self.run_qualification(oracle=dict(self.valid, reference_commit="0" * 40))
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_empty_noninteger_and_boolean_corpus_reject_pass(self):
        for index, count in enumerate((0, -1, True, 1.5, "2057", None)):
            with self.subTest(positions=count):
                self.arguments.output = self.root / ("qualification-" + str(index))
                status, report, _ = self.run_qualification(oracle=dict(self.valid, positions=count))
                self.assertEqual(status, 1)
                self.assert_failed(report)

    def test_nonzero_exit_cannot_reuse_an_apparent_pass(self):
        status, report, _ = self.run_qualification(returncode=1)
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_zero_exit_without_pass_record_is_not_success(self):
        status, report, _ = self.run_qualification(oracle=dict(self.valid, result="FAIL"))
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_nonobject_oracle_json_is_clean_failure(self):
        status, report, _ = self.run_qualification(oracle=["PASS"])
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_missing_oracle_report_cannot_be_a_pass(self):
        with mock.patch.object(tool.shutil, "which", return_value="/fixture/compiler"), \
                mock.patch.object(tool, "run_oracle", return_value=subprocess.CompletedProcess([], 0)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = tool.qualify(self.arguments)
        report = json.loads((self.arguments.output / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_payload_changed_during_oracle_rejects_pass(self):
        def mutate():
            self.network.write_bytes(self.network.read_bytes() + b"changed during check")
        status, report, _ = self.run_qualification(mutate=mutate)
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_provenance_changed_during_oracle_rejects_pass(self):
        self.arguments.metadata = self.metadata()

        def mutate():
            self.metadata(training={"games": 999, "positions": 999, "epochs": 1})
        status, report, _ = self.run_qualification(mutate=mutate)
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_tooling_changed_during_oracle_rejects_pass(self):
        status, report, _ = self.run_qualification(source_drift=True)
        self.assertEqual(status, 1)
        self.assert_failed(report)

    def test_existing_output_is_preserved_before_launch(self):
        self.arguments.output.mkdir()
        old = self.arguments.output / "report.json"
        old.write_bytes(b"old record")
        with mock.patch.object(tool, "run_oracle") as run, self.assertRaises(tool.NetworkToolError):
            tool.qualify(self.arguments)
        run.assert_not_called()
        self.assertEqual(old.read_bytes(), b"old record")


if __name__ == "__main__":
    unittest.main()
