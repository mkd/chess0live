#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Test retained-evidence validation with explicitly synthetic, inert records.

The tiny network only has a recognizable header; dummy binaries, fake FENs and
repeated output lines establish no NNUE arithmetic or real executable behavior.
Actual exported-network qualification is recorded separately in validation docs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import network
import network_receipt as receipt


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "qualification"
        self.work = self.run / "oracle"
        self.work.mkdir(parents=True)
        self.net = self.root / "candidate.nnue"
        self.net.write_bytes(struct.pack("<IIII", network.VERSION, network.ARCHITECTURE,
                                        0, network.TRANSFORMER) + b"synthetic-test-only")
        self.metadata = self.root / "metadata.json"
        self.metadata.write_text(json.dumps({"schema_version": 2, "network_sha256": sha(self.net),
                                            "training": {"games": None, "steps": 4}}))
        inspected = network.inspect_network(self.net, self.metadata)
        self.outer = dict(inspected, operation="qualify", status="passed",
                          tooling_sha256=network.source_pins(),
                          finished_at="2026-10-24T12:00:00+00:00",
                          oracle_report=str(self.work / "report.json"))
        self.outer["verification"] = {"independent_oracle": "passed", "full_decoder": "passed",
                                      "positions": receipt.EXPECTED_POSITIONS}
        corpus = self.work / "positions.fen"
        corpus.write_bytes(b"synthetic FEN record\n" * receipt.EXPECTED_POSITIONS)
        reference = self.work / "reference-build"
        (reference / "src").mkdir(parents=True)
        source = reference / "src/fake.cpp"
        source.write_text("// synthetic source, not compiled\n")
        binaries = {}
        for name in ("reference", "native_raw", "scalar_raw", "native_stages", "scalar_stages"):
            binary = self.work / (name + ".dummy")
            binary.write_bytes(b"inert binary fixture " + name.encode())
            binaries[name] = {"path": str(binary), "size_bytes": binary.stat().st_size,
                              "sha256": sha(binary)}
        self.inner = {"schema": 2, "result": "PASS", "network": inspected["artifact"],
                      "network_sha256": inspected["artifact"]["sha256"],
                      "reference_commit": network.manifest()["reference_commit"],
                      "positions": receipt.EXPECTED_POSITIONS,
                      "source_sha256": receipt.local_sources(receipt.ROOT),
                      "work_dir": str(self.work), "corpus_sha256": sha(corpus),
                      "binaries": binaries, "reference_build_directory": str(reference),
                      "reference_source_sha256": {"src/fake.cpp": sha(source)},
                      "outputs": {"native": {}, "scalar": {}}}
        for kind in ("raw", "stages"):
            data = (kind.encode() + b";fake integer values\n") * receipt.EXPECTED_POSITIONS
            for backend in ("reference", "native", "scalar"):
                (self.work / f"{backend}-{kind}.txt").write_bytes(data)
            digest = sha(self.work / f"reference-{kind}.txt")
            self.inner[f"reference_{kind}_sha256"] = digest
            for backend in ("native", "scalar"):
                self.inner["outputs"][backend][f"{kind}_sha256"] = digest
        self.publish()

    def publish(self):
        (self.work / "report.json").write_text(json.dumps(self.inner))
        self.outer["oracle_report_sha256"] = sha(self.work / "report.json")
        (self.run / "report.json").write_text(json.dumps(self.outer))

    def validate(self, **kwargs):
        return receipt.validate_qualification(self.run, self.net, self.metadata, **kwargs)

    def rejects(self):
        with self.assertRaises(network.NetworkToolError):
            self.validate()

    def test_complete_retained_evidence_and_unknown_games(self):
        result = self.validate()
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["current_sources"])
        self.assertEqual(result["positions"], 2057)
        self.assertEqual(result["network_sha256"], sha(self.net))
        self.assertIsNone(self.outer["provenance"]["training"]["games"])

    def test_changed_evaluation_source_requires_fresh_check(self):
        name = next(iter(self.inner["source_sha256"]))
        self.inner["source_sha256"][name] = "0" * 64
        self.publish()
        self.rejects()
        self.assertFalse(self.validate(require_current=False)["current_sources"])

    def test_changed_qualification_tool_requires_fresh_check(self):
        self.outer["tooling_sha256"]["tools/network.py"] = "0" * 64
        self.publish()
        self.rejects()

    def test_ordinary_inspection_is_not_qualification(self):
        self.outer["operation"] = "inspect"
        self.publish()
        self.rejects()

    def test_failed_oracle_is_not_success(self):
        self.inner["result"] = "FAIL"
        self.publish()
        self.rejects()

    def test_decoder_must_pass(self):
        self.outer["verification"]["full_decoder"] = "not_run"
        self.publish()
        self.rejects()

    def test_boolean_position_count_rejected(self):
        self.inner["positions"] = True
        self.publish()
        self.rejects()

    def test_changed_nested_report_rejected(self):
        with (self.work / "report.json").open("a") as stream:
            stream.write(" ")
        self.rejects()

    def test_wrong_reference_pin_rejected(self):
        self.inner["reference_commit"] = "0" * 40
        self.publish()
        self.rejects()

    def test_missing_output_rejected(self):
        (self.work / "native-stages.txt").unlink()
        self.rejects()

    def test_changed_output_rejected(self):
        with (self.work / "native-raw.txt").open("ab") as stream:
            stream.write(b"unexpected\n")
        self.rejects()

    def test_truncated_equal_outputs_still_rejected(self):
        for backend in ("reference", "native", "scalar"):
            path = self.work / f"{backend}-raw.txt"
            path.write_bytes(b"same\n" * (receipt.EXPECTED_POSITIONS - 1))
            if backend == "reference":
                self.inner["reference_raw_sha256"] = sha(path)
            else:
                self.inner["outputs"][backend]["raw_sha256"] = sha(path)
        self.publish()
        self.rejects()

    def test_disagreeing_output_with_updated_hash_rejected(self):
        path = self.work / "native-raw.txt"
        path.write_bytes(b"wrong\n" * receipt.EXPECTED_POSITIONS)
        self.inner["outputs"]["native"]["raw_sha256"] = sha(path)
        self.publish()
        self.rejects()

    def test_empty_corpus_rejected(self):
        path = self.work / "positions.fen"
        path.write_bytes(b"")
        self.inner["corpus_sha256"] = sha(path)
        self.publish()
        self.rejects()

    def test_network_changed_rejected(self):
        with self.net.open("ab") as stream:
            stream.write(b"changed")
        self.rejects()

    def test_provenance_changed_rejected(self):
        data = json.loads(self.metadata.read_text())
        data["training"]["games"] = 123
        self.metadata.write_text(json.dumps(data))
        self.rejects()

    def test_architecture_record_changed_rejected(self):
        self.outer["architecture"]["name"] = "different"
        self.publish()
        self.rejects()

    def test_binary_identity_changed_rejected(self):
        Path(self.inner["binaries"]["native_raw"]["path"]).write_bytes(b"changed")
        self.rejects()

    def test_binary_path_escape_rejected(self):
        outside = self.root / "outside-binary"
        outside.write_bytes(b"inert")
        self.inner["binaries"]["native_raw"] = {
            "path": str(outside), "size_bytes": outside.stat().st_size, "sha256": sha(outside)}
        self.publish()
        self.rejects()

    def test_reference_source_changed_rejected(self):
        reference = Path(self.inner["reference_build_directory"])
        (reference / "src/fake.cpp").write_text("changed\n")
        self.rejects()

    def test_reference_source_path_escape_rejected(self):
        outside = self.root / "outside-source.cpp"
        outside.write_text("synthetic\n")
        self.inner["reference_source_sha256"] = {str(outside): sha(outside)}
        self.publish()
        self.rejects()

    def test_duplicate_json_key_rejected(self):
        path = self.run / "report.json"
        text = path.read_text()
        path.write_text(text[:-1] + ', "status": "passed"}')
        self.rejects()

    def test_invalid_json_constant_rejected(self):
        path = self.run / "report.json"
        text = path.read_text()
        path.write_text(text[:-1] + ', "extra": NaN}')
        self.rejects()

    def test_boolean_schema_rejected(self):
        self.outer["schema_version"] = True
        self.publish()
        self.rejects()

    def test_completion_timestamp_must_be_zoned(self):
        self.outer["finished_at"] = "2026-10-24T12:00:00"
        self.publish()
        self.rejects()

    def test_oversized_report_rejected(self):
        (self.run / "report.json").write_bytes(b" " * (receipt.MAX_REPORT_BYTES + 1))
        self.rejects()

    @unittest.skipIf(os.name == "nt", "native Windows symlink creation is not assumed")
    def test_symlink_output_escape_rejected(self):
        path = self.work / "native-raw.txt"
        outside = self.root / "outside-output.txt"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        self.rejects()


if __name__ == "__main__":
    unittest.main()
