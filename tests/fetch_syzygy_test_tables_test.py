#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Exercise bounded fixture downloads, immutable pins, and atomic failures."""

import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fetch_syzygy_test_tables as fetcher


class FixtureFetchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = b"test table data"
        self.entry = {"filename": "KQvK.rtbw", "source_path": "data/syzygy/regular/KQvK.rtbw",
                      "size_bytes": len(self.payload), "sha256": hashlib.sha256(self.payload).hexdigest()}
        self.destination = self.root / self.entry["filename"]

    def manifest_file(self, data):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(data))
        return path

    def test_repository_manifest_is_complete_and_bounded(self):
        manifest = fetcher.load_manifest()
        tables = [e["filename"] for e in manifest["files"] if e["filename"].endswith((".rtbw", ".rtbz"))]
        self.assertEqual(len(tables), 70)
        self.assertEqual({name[:-5] for name in tables if name.endswith(".rtbw")},
                         {name[:-5] for name in tables if name.endswith(".rtbz")})
        self.assertIn("KPvKP.rtbz", tables)
        self.assertLess(manifest["total_bytes"], fetcher.MAX_TOTAL_BYTES)

    def test_mutable_and_mismatched_sources_fail(self):
        original = fetcher.load_manifest()
        for key, value in (("schema", "unknown"), ("source_revision", "master"),
                           ("source_repository", "https://example.invalid/repo"),
                           ("download_base_url", "https://example.invalid/tables/"),
                           ("total_bytes", original["total_bytes"] + 1)):
            with self.subTest(key=key):
                data = copy.deepcopy(original)
                data[key] = value
                with self.assertRaises(ValueError):
                    fetcher.load_manifest(self.manifest_file(data))

    def test_paths_sizes_and_hashes_fail_closed(self):
        original = fetcher.load_manifest()
        for key, value in (("filename", "../KQvK.rtbw"), ("source_path", "../secret"),
                           ("size_bytes", -1), ("size_bytes", True),
                           ("size_bytes", fetcher.MAX_TOTAL_BYTES + 1),
                           ("sha256", "0" * 63), ("sha256", "g" * 64)):
            with self.subTest(key=key, value=value):
                data = copy.deepcopy(original)
                data["files"][0][key] = value
                with self.assertRaises(ValueError):
                    fetcher.load_manifest(self.manifest_file(data))

    def test_duplicate_files_and_missing_notices_fail(self):
        original = fetcher.load_manifest()
        duplicate = copy.deepcopy(original)
        duplicate["files"].append(duplicate["files"][0])
        missing = copy.deepcopy(original)
        missing["files"] = [e for e in missing["files"] if e["filename"] != "UPSTREAM-SOURCE.txt"]
        for data in (duplicate, missing):
            with self.assertRaises(ValueError):
                fetcher.load_manifest(self.manifest_file(data))

    def test_install_is_verified_before_replacement(self):
        self.destination.write_bytes(b"previous data")
        fetcher.install(io.BytesIO(self.payload), self.destination, self.entry)
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertEqual(list(self.root.glob(".syzygy-*")), [])

    def test_truncated_corrupt_and_oversized_preserve_previous_data(self):
        for payload in (self.payload[:-1], b"x" * len(self.payload), self.payload + b"x"):
            with self.subTest(payload=payload):
                self.destination.write_bytes(b"previous data")
                with self.assertRaises(ValueError):
                    fetcher.install(io.BytesIO(payload), self.destination, self.entry)
                self.assertEqual(self.destination.read_bytes(), b"previous data")
                self.assertEqual(list(self.root.glob(".syzygy-*")), [])

    def test_stream_failure_cleans_temporary(self):
        class FailingStream:
            def read(self, size):
                raise OSError("interrupted transfer")
        with self.assertRaises(OSError):
            fetcher.install(FailingStream(), self.destination, self.entry)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.root.glob(".syzygy-*")), [])

    def test_replace_failure_cleans_temporary(self):
        self.destination.write_bytes(b"previous data")
        with patch.object(fetcher.os, "replace", side_effect=OSError("denied")):
            with self.assertRaises(OSError):
                fetcher.install(io.BytesIO(self.payload), self.destination, self.entry)
        self.assertEqual(self.destination.read_bytes(), b"previous data")
        self.assertEqual(list(self.root.glob(".syzygy-*")), [])

    def test_verify_missing_never_writes_or_downloads(self):
        destination = self.root / "does-not-exist"
        manifest = {"files": [self.entry]}
        with patch.object(fetcher.urllib.request, "urlopen", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(ValueError, "Missing or invalid"):
                fetcher.fetch(manifest, destination, verify_only=True)
        self.assertFalse(destination.exists())

    def test_existing_verified_files_skip_network(self):
        self.destination.write_bytes(self.payload)
        with patch.object(fetcher.urllib.request, "urlopen", side_effect=AssertionError("network")):
            fetcher.fetch({"files": [self.entry]}, self.root)
            fetcher.fetch({"files": [self.entry]}, self.root, verify_only=True)

    def test_offline_source_is_verified_and_can_resume(self):
        source = self.root / "source"
        source.mkdir()
        (source / self.entry["filename"]).write_bytes(self.payload)
        destination = self.root / "destination"
        fetcher.fetch({"files": [self.entry]}, destination, from_directory=source)
        self.assertEqual((destination / self.entry["filename"]).read_bytes(), self.payload)
        (source / self.entry["filename"]).unlink()
        fetcher.fetch({"files": [self.entry]}, destination, from_directory=source)

    def test_bad_offline_source_is_not_installed(self):
        source = self.root / "source"
        source.mkdir()
        (source / self.entry["filename"]).write_bytes(b"corrupt")
        destination = self.root / "destination"
        with self.assertRaises(ValueError):
            fetcher.fetch({"files": [self.entry]}, destination, from_directory=source)
        self.assertFalse((destination / self.entry["filename"]).exists())

    def test_download_uses_immutable_url_and_is_verified(self):
        base = "https://raw.githubusercontent.com/niklasf/python-chess/" + "a" * 40 + "/"
        with patch.object(fetcher.urllib.request, "urlopen", return_value=io.BytesIO(self.payload)) as request:
            fetcher.fetch({"files": [self.entry], "download_base_url": base}, self.root)
        self.assertEqual(request.call_args.args[0].full_url, base + self.entry["source_path"])
        self.assertEqual(request.call_args.kwargs["timeout"], 30)
        self.assertTrue(fetcher.matches(self.destination, self.entry))


if __name__ == "__main__":
    unittest.main()
