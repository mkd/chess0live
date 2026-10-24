#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Test local network selection transitions without training or engine searches.

The deliberately header-only fixtures and mocked qualification boundary test
catalog behavior, not NNUE compatibility. The receipt suite and separately
recorded real runs establish the evidence-validation and execution coverage.
"""
from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import network
import managed_network as tool


def payload(label):
    """Independent header fixture; no actual weights or compatibility claim."""
    description = label.encode()
    return (struct.pack("<III", 0x6A448AFA, 0xA85B2205, len(description))
            + description + struct.pack("<I", 0xCB685313))


def identity(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {"path": str(path), "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


class CatalogFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="managed network tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = self.root / "catalog with spaces"
        self.default = self.root / "default.nnue"
        self.candidate = self.root / "candidate with spaces.nnue"
        self.second = self.root / "second.nnue"
        self.default.write_bytes(payload("pinned fixture"))
        self.candidate.write_bytes(payload("candidate fixture"))
        self.second.write_bytes(payload("second fixture"))
        self.engine = self.root / "engine with spaces"
        self.engine.write_bytes(b"synthetic executable identity only\n")
        self.engine.chmod(0o755)
        pin = network.manifest()
        pin.update(filename=self.default.name,
                   size_bytes=self.default.stat().st_size,
                   sha256=identity(self.default)["sha256"])
        self.patch(network, "manifest", return_value=pin)
        self.patch(network, "default_network", return_value=self.default)
        self.qualification = self.patch(network, "qualify", side_effect=self.fake_qualify)
        self.validation = self.patch(tool, "validate_qualification", side_effect=self.fake_validate)

    def patch(self, module, name, **kwargs):
        patcher = mock.patch.object(module, name, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def fake_qualify(self, args):
        """Simulate only the external boundary, retaining a digest-bound record."""
        directory = Path(args.output)
        directory.mkdir(parents=True, exist_ok=False)
        info = network.inspect_network(args.network, args.metadata)
        info.update(operation="qualify", status="passed")
        info["verification"].update(full_decoder="passed", independent_oracle="passed",
                                     positions=2057)
        (directory / "report.json").write_text(json.dumps(info))
        (directory / "oracle").mkdir()
        (directory / "oracle/report.json").write_text('{"result":"PASS","positions":2057}')
        return 0

    def fake_validate(self, directory, network_path, metadata_path=None, *, require_current=True):
        """Ensure catalog tests still detect payload/report/provenance substitution."""
        directory = Path(directory)
        report_path = directory / "report.json"
        report = json.loads(report_path.read_text())
        info = network.inspect_network(network_path, metadata_path)
        if (report["status"] != "passed"
                or report["artifact"]["sha256"] != info["artifact"]["sha256"]
                or report["provenance"] != info["provenance"]):
            raise network.NetworkToolError("Synthetic qualification input changed")
        return {"status": "passed", "positions": 2057, "current_sources": True,
                "qualified_at": "2026-10-24T00:00:00+00:00",
                "qualification_report_sha256": identity(report_path)["sha256"],
                "oracle_report_sha256": identity(directory / "oracle/report.json")["sha256"],
                "network_sha256": info["artifact"]["sha256"],
                "scope": "Synthetic catalog test boundary only"}

    def add(self, name="first", path=None, **kwargs):
        return tool.add_network(self.store, name, path or self.candidate, **kwargs)

    def state(self):
        return tool.read_state(self.store)

    def state_bytes(self):
        return (self.store / "catalog.json").read_bytes()

    def entry_dir(self, name="first"):
        return self.store / "entries" / self.state()["entries"][name]["directory"]

    def selected_path(self):
        config = tool.launch_config(self.store, self.engine)
        argv = config["argv"]
        return Path(argv[argv.index("--eval-file") + 1])

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = tool.main(["--store", str(self.store), *map(str, args)])
        return code, stdout.getvalue(), stderr.getvalue()


class SelectionTests(CatalogFixture):
    def test_read_only_empty_status_and_list_do_not_create_store(self):
        tool.status(self.store)
        self.assertEqual([item["name"] for item in tool.list_networks(self.store)], ["default"])
        self.assertFalse(self.store.exists())

    def test_add_qualifies_an_independent_copy_without_selecting_it(self):
        original = self.candidate.read_bytes()
        self.add()
        self.assertIsNone(self.state()["active"])
        self.assertIn("first", self.state()["entries"])
        args = self.qualification.call_args.args[0]
        self.assertNotEqual(Path(args.network).resolve(), self.candidate.resolve())
        self.assertEqual(Path(args.network).read_bytes(), original)
        self.assertEqual(self.candidate.read_bytes(), original)
        self.assertEqual(self.default.read_bytes(), payload("pinned fixture"))
        self.validation.assert_called()

    def test_duplicate_alias_preserves_catalog_and_existing_entry(self):
        self.add()
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            self.add(path=self.second)
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual(self.qualification.call_count, 1)

    def test_invalid_and_reserved_names_never_publish(self):
        for name in ("", "../escape", "a/b", "a\\b", "default", "a\nb", "a" * 65):
            with self.subTest(name=name), self.assertRaises(network.NetworkToolError):
                self.add(name)
        self.assertEqual(self.state()["entries"], {})
        self.qualification.assert_not_called()

    def test_failed_qualification_does_not_register_or_change_selection(self):
        self.add()
        tool.select_network(self.store, "first")
        before = self.state_bytes()
        self.qualification.side_effect = lambda args: 1
        with self.assertRaises(network.NetworkToolError):
            self.add("second", self.second)
        self.assertEqual(self.state_bytes(), before)
        self.assertNotIn("second", self.state()["entries"])

    def test_interrupted_add_does_not_publish(self):
        self.qualification.side_effect = KeyboardInterrupt("test interruption")
        with self.assertRaises(KeyboardInterrupt):
            self.add()
        self.assertEqual(self.state()["entries"], {})

    def test_changed_copy_after_qualification_is_rejected(self):
        def changing(args):
            result = self.fake_qualify(args)
            Path(args.network).write_bytes(payload("changed after qualification"))
            return result
        self.qualification.side_effect = changing
        with self.assertRaises(network.NetworkToolError):
            self.add()
        self.assertEqual(self.state()["entries"], {})

    def test_wrong_metadata_digest_is_rejected_before_qualification(self):
        metadata = self.root / "wrong metadata.json"
        metadata.write_text(json.dumps({"schema_version": 1, "network_sha256": "0" * 64}))
        with self.assertRaises(network.NetworkToolError):
            self.add(metadata=metadata)
        self.qualification.assert_not_called()

    def test_select_then_revert_restores_explicit_default(self):
        self.add()
        tool.select_network(self.store, "first")
        self.assertEqual(self.state()["active"], "first")
        self.assertTrue(self.state()["has_previous"])
        self.assertIsNone(self.state()["previous"])
        tool.revert_network(self.store)
        self.assertIsNone(self.state()["active"])
        self.assertEqual(self.state()["previous"], "first")
        self.assertEqual(self.selected_path(), self.default.resolve())
        tool.revert_network(self.store)
        self.assertEqual(self.state()["active"], "first")

    def test_select_same_name_preserves_previous_choice(self):
        self.add()
        self.add("second", self.second)
        tool.select_network(self.store, "first")
        tool.select_network(self.store, "second")
        before = copy.deepcopy(self.state())
        tool.select_network(self.store, "second")
        self.assertEqual(self.state(), before)
        tool.revert_network(self.store)
        self.assertEqual(self.state()["active"], "first")

    def test_select_default_is_reversible(self):
        self.add()
        tool.select_network(self.store, "first")
        tool.select_network(self.store, "default")
        self.assertIsNone(self.state()["active"])
        tool.revert_network(self.store)
        self.assertEqual(self.state()["active"], "first")

    def test_unknown_name_preserves_existing_selection(self):
        self.add()
        tool.select_network(self.store, "first")
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            tool.select_network(self.store, "unknown")
        self.assertEqual(self.state_bytes(), before)

    def test_revert_without_history_fails(self):
        with self.assertRaises(network.NetworkToolError):
            tool.revert_network(self.store)
        self.assertIsNone(self.state()["active"])

    def test_deleted_original_does_not_break_managed_copy(self):
        self.add()
        self.candidate.unlink()
        tool.select_network(self.store, "first")
        self.assertEqual(self.selected_path().read_bytes(), payload("candidate fixture"))

    def test_modified_managed_file_cannot_launch_or_be_selected(self):
        self.add()
        tool.select_network(self.store, "first")
        managed = self.selected_path()
        managed.write_bytes(payload("modified managed weights"))
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, self.engine)
        with self.assertRaises(network.NetworkToolError):
            tool.select_network(self.store, "first")
        self.assertEqual(self.state_bytes(), before)

    def test_damaged_previous_selection_does_not_replace_active(self):
        self.add()
        self.add("second", self.second)
        tool.select_network(self.store, "first")
        managed = self.selected_path()
        tool.select_network(self.store, "second")
        managed.unlink()
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            tool.revert_network(self.store)
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual(self.state()["active"], "second")

    def test_receipt_change_is_detected(self):
        self.add()
        receipt = self.entry_dir() / "receipt.json"
        receipt.write_bytes(receipt.read_bytes() + b" ")
        with self.assertRaises(network.NetworkToolError):
            tool.select_network(self.store, "first")

    def test_pinned_default_change_refuses_launch(self):
        self.default.write_bytes(payload("different default"))
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, self.engine)

    def test_config_keeps_space_paths_as_literal_arguments(self):
        self.add()
        tool.select_network(self.store, "first")
        config = tool.launch_config(self.store, self.engine)
        self.assertEqual(config["argv"][0], str(self.engine.resolve()))
        self.assertEqual(config["argv"][1], "--eval-file")
        self.assertEqual(len(config["argv"]), 3)
        self.assertTrue(Path(config["argv"][2]).is_absolute())
        self.assertIn(" ", config["argv"][2])

    def test_missing_engine_fails_without_changing_selection(self):
        self.add()
        tool.select_network(self.store, "first")
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, self.root / "missing engine")
        self.assertEqual(self.state_bytes(), before)

    def test_concurrent_choices_keep_valid_catalog(self):
        self.add()
        self.add("second", self.second)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda name: tool.select_network(self.store, name), ["first", "second"]))
        state = self.state()
        self.assertIn(state["active"], {"first", "second"})
        self.assertIn(state["previous"], {"first", "second"})
        self.assertNotEqual(state["active"], state["previous"])
        self.selected_path()

    def test_failed_atomic_write_preserves_complete_previous_catalog(self):
        self.add()
        self.add("second", self.second)
        tool.select_network(self.store, "first")
        before = self.state_bytes()
        with mock.patch.object(tool.os, "replace", side_effect=OSError("simulated full disk")):
            with self.assertRaises(OSError):
                tool.select_network(self.store, "second")
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual(self.state()["active"], "first")
        self.assertEqual(list(self.store.glob(".catalog-*.tmp")), [])

    def test_registered_provenance_is_a_copy_and_preserves_unknown_counts(self):
        metadata = self.root / "source metadata.json"
        claims = {"schema_version": 2, "network_sha256": identity(self.candidate)["sha256"],
                  "name": "My test network", "author": "Declared author", "license": None,
                  "training": {"games": 0, "positions": None, "epochs": None,
                               "processed_samples": 50, "steps": 5}}
        metadata.write_text(json.dumps(claims))
        self.add(metadata=metadata)
        metadata.unlink()
        tool.select_network(self.store, "first")
        selected = tool.status(self.store)
        provenance = selected["provenance"]
        self.assertEqual(provenance["training_status"], "declared_unverified")
        self.assertEqual(provenance["training"]["games"], 0)
        self.assertIsNone(provenance["training"]["positions"])
        self.assertIsNone(provenance["training"]["epochs"])
        self.assertEqual(provenance["training"]["processed_samples"], 50)
        self.assertEqual(selected["playing_strength"], "not_measured")
        self.selected_path()

    def test_qualification_record_change_is_detected(self):
        self.add()
        report = self.entry_dir() / "qualification/report.json"
        report.write_bytes(report.read_bytes() + b" ")
        with self.assertRaises(network.NetworkToolError):
            tool.select_network(self.store, "first")

    def test_stale_evidence_can_be_inspected_but_not_launched(self):
        self.add()
        tool.select_network(self.store, "first")
        before = self.state_bytes()
        def stale(directory, path, metadata=None, *, require_current=True):
            if require_current:
                raise network.NetworkToolError("Evaluator changed; requalify")
            result = self.fake_validate(directory, path, metadata, require_current=False)
            result["current_sources"] = False
            return result
        self.validation.side_effect = stale
        self.assertEqual(tool.status(self.store)["status"], "stale")
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, self.engine)
        with self.assertRaises(network.NetworkToolError):
            tool.select_network(self.store, "first")
        self.assertEqual(self.state_bytes(), before)

    def test_bad_catalog_never_silently_becomes_default(self):
        self.add()
        tool.select_network(self.store, "first")
        state = self.state()
        state["active"] = "missing entry"
        (self.store / "catalog.json").write_text(json.dumps(state))
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, self.engine)

    def test_duplicate_json_keys_are_rejected(self):
        self.store.mkdir()
        (self.store / "catalog.json").write_text(
            '{"schema_version":1,"schema_version":2,"entries":{},'
            '"active":null,"previous":null,"has_previous":false}')
        with self.assertRaises(network.NetworkToolError):
            self.state()

    def test_foreign_catalog_directory_is_preserved(self):
        self.store.mkdir()
        note = self.store / "unrelated owner file.txt"
        note.write_text("preserve me")
        with self.assertRaises(network.NetworkToolError):
            self.add()
        self.assertEqual(note.read_text(), "preserve me")
        self.assertFalse((self.store / "catalog.json").exists())
        self.qualification.assert_not_called()

    def test_control_characters_in_paths_are_rejected(self):
        path = self.root / "candidate\nquit.nnue"
        path.write_bytes(self.candidate.read_bytes())
        with self.assertRaises(network.NetworkToolError):
            self.add(path=path)
        self.qualification.assert_not_called()
        engine = self.root / "engine\nquit"
        engine.write_bytes(self.engine.read_bytes())
        engine.chmod(0o755)
        with self.assertRaises(network.NetworkToolError):
            tool.launch_config(self.store, engine)

    def test_config_exposes_matching_gui_option_and_override_notice(self):
        self.add()
        tool.select_network(self.store, "first")
        config = tool.launch_config(self.store, self.engine)
        self.assertEqual(config["uci_option"], "setoption name EvalFile value " + config["argv"][2])
        self.assertIn("overrides", config["gui_note"])

    def test_run_uses_literal_exec_arguments_and_no_shell(self):
        self.add()
        tool.select_network(self.store, "first")
        expected = tool.launch_config(self.store, self.engine)["argv"]
        class ExecReached(RuntimeError):
            pass
        with mock.patch.object(tool.os, "execv", side_effect=ExecReached) as execute:
            with self.assertRaises(ExecReached):
                self.cli("run", "--engine", self.engine)
        execute.assert_called_once_with(expected[0], expected)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_fifo_receipt_is_rejected_before_any_hash_read(self):
        self.add()
        receipt = self.entry_dir() / "receipt.json"
        receipt.unlink()
        os.mkfifo(receipt)
        with mock.patch.object(tool, "fingerprint", side_effect=AssertionError("must reject before opening FIFO")):
            with self.assertRaises(network.NetworkToolError):
                tool.select_network(self.store, "first")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_fifo_qualification_record_is_rejected_before_hash_read(self):
        self.add()
        report = self.entry_dir() / "qualification/report.json"
        report.unlink()
        os.mkfifo(report)
        original = tool.fingerprint
        def bounded(path):
            if Path(path) == report:
                raise AssertionError("must reject before opening FIFO")
            return original(path)
        with mock.patch.object(tool, "fingerprint", side_effect=bounded):
            with self.assertRaises(network.NetworkToolError):
                tool.select_network(self.store, "first")

    def test_oversized_receipt_is_rejected_before_hash_read(self):
        self.add()
        receipt = self.entry_dir() / "receipt.json"
        with receipt.open("wb") as stream:
            stream.truncate(4 * 1024 * 1024 + 1)
        with mock.patch.object(tool, "fingerprint", side_effect=AssertionError("must reject oversized record first")):
            with self.assertRaises(network.NetworkToolError):
                tool.select_network(self.store, "first")

    @unittest.skipUnless(os.name == "posix", "native symlink permissions vary on Windows")
    def test_symlink_entries_directory_cannot_receive_new_payload(self):
        tool.select_network(self.store, "default")
        outside = self.root / "outside entries"
        outside.mkdir()
        (self.store / "entries").symlink_to(outside, target_is_directory=True)
        before = self.state_bytes()
        with self.assertRaises(network.NetworkToolError):
            self.add()
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual(list(outside.iterdir()), [])
        self.qualification.assert_not_called()

    def test_missing_catalog_after_selection_never_falls_back_to_default(self):
        self.add()
        tool.select_network(self.store, "first")
        original_entry = self.entry_dir()
        (self.store / "catalog.json").unlink()
        for operation in (lambda: tool.status(self.store),
                          lambda: tool.launch_config(self.store, self.engine),
                          lambda: tool.select_network(self.store, "default")):
            with self.subTest(operation=operation), self.assertRaises(network.NetworkToolError):
                operation()
        self.assertFalse((self.store / "catalog.json").exists())
        self.assertTrue(original_entry.is_dir())

    @unittest.skipUnless(os.name == "posix", "native symlink permissions vary on Windows")
    def test_symlink_catalog_never_selects_or_rewrites_foreign_state(self):
        self.add()
        tool.select_network(self.store, "first")
        original = self.state_bytes()
        outside = self.root / "outside catalog.json"
        outside.write_bytes(original)
        catalog = self.store / "catalog.json"
        catalog.unlink()
        catalog.symlink_to(outside)
        for operation in (lambda: self.state(),
                          lambda: tool.launch_config(self.store, self.engine),
                          lambda: tool.select_network(self.store, "default")):
            with self.subTest(operation=operation), self.assertRaises(network.NetworkToolError):
                operation()
        self.assertEqual(outside.read_bytes(), original)
        self.assertTrue(catalog.is_symlink())

    def test_cli_error_is_concise_and_nonzero(self):
        code, stdout, stderr = self.cli("select", "missing")
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", stderr)
        self.assertTrue(stderr.strip())

    def test_help_runs_without_store_or_dependencies(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/managed_network.py"),
                                 "--store", str(self.store), "--help"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        for command in ("add", "select", "revert", "status", "list", "config", "run"):
            self.assertIn(command, result.stdout)
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
