#!/usr/bin/env python3
"""Check pinned toolchain caching and archive safety with tiny local fixtures.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import contextlib
import hashlib
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import toolchain_cache as cache


def tar_fixture(path, members):
    """Write explicit member tuples: name, kind, bytes/link target, permissions."""
    with tarfile.open(path, "w:xz") as archive:
        for name, kind, payload, mode in members:
            member = tarfile.TarInfo(name)
            member.mode = mode
            if kind == "file":
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            else:
                member.type = {"dir": tarfile.DIRTYPE, "sym": tarfile.SYMTYPE,
                               "hard": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE}[kind]
                if kind in ("sym", "hard"):
                    member.linkname = payload
                archive.addfile(member)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="toolchain cache ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "fixture.tar.xz"
        self.cache = self.root / "cache with spaces"
        self.staging = self.root / "staging"
        self.staging.mkdir()

    def asset(self):
        return {"filename": self.archive.name, "root": "toolchain",
                "size": self.archive.stat().st_size, "sha256": cache.sha256(self.archive),
                "url": "https://github.com/mstorsjo/llvm-mingw/releases/download/test/fixture.tar.xz"}

    def good_archive(self):
        tar_fixture(self.archive, [
            ("toolchain/bin/wrapper.sh", "file", b"#!/bin/sh\n", 0o755),
            ("toolchain/bin/aarch64-w64-mingw32-clang++", "sym", "wrapper.sh", 0o777),
            ("toolchain/bin/x86_64-w64-mingw32-clang++", "sym", "wrapper.sh", 0o777),
            ("toolchain/include/common.h", "file", b"header", 0o644),
            ("toolchain/target/include", "sym", "../include", 0o777),
            ("toolchain/LICENSE.TXT", "file", b"upstream notices", 0o644),
        ])
        return self.asset()


class ArchiveTests(FixtureTests):
    def test_relative_compiler_and_directory_aliases_are_preserved(self):
        self.good_archive()
        result = cache.extract_archive(self.archive, self.staging, "toolchain")
        compiler = result / "bin/aarch64-w64-mingw32-clang++"
        self.assertTrue(compiler.is_symlink())
        self.assertEqual(compiler.read_bytes(), b"#!/bin/sh\n")
        self.assertEqual((result / "target/include/common.h").read_bytes(), b"header")
        self.assertEqual((result / "LICENSE.TXT").read_bytes(), b"upstream notices")
        self.assertEqual(stat.S_IMODE(compiler.stat().st_mode), 0o755)

    def test_internal_hardlink_preserves_content(self):
        tar_fixture(self.archive, [("toolchain/file", "file", b"content", 0o644),
                                   ("toolchain/alias", "hard", "toolchain/file", 0o644)])
        result = cache.extract_archive(self.archive, self.staging, "toolchain")
        self.assertEqual((result / "alias").read_bytes(), b"content")

    def test_zip_regular_files_and_directory_are_supported(self):
        archive = self.root / "fixture.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("toolchain/", b"")
            info = zipfile.ZipInfo("toolchain/bin/compiler.exe")
            info.external_attr = (stat.S_IFREG | 0o755) << 16
            output.writestr(info, b"fixture")
        result = cache.extract_archive(archive, self.staging, "toolchain")
        self.assertEqual((result / "bin/compiler.exe").read_bytes(), b"fixture")
        self.assertEqual(stat.S_IMODE((result / "bin/compiler.exe").stat().st_mode), 0o755)

    def test_unsafe_paths_rejected_before_writing_outside_root(self):
        for name in ("../outside", "/outside", "toolchain/../../outside", "other/file",
                     "toolchain\\escape", "toolchain/C:escape"):
            with self.subTest(name=name):
                tar_fixture(self.archive, [(name, "file", b"bad", 0o644)])
                with self.assertRaises(cache.ToolchainError):
                    cache.extract_archive(self.archive, self.staging, "toolchain")
        self.assertFalse((self.root / "outside").exists())

    def test_zip_traversal_and_special_members_are_rejected(self):
        archive = self.root / "bad.zip"
        for name, mode in [("../outside", stat.S_IFREG),
                           ("toolchain/link", stat.S_IFLNK),
                           ("toolchain/fifo", stat.S_IFIFO)]:
            with self.subTest(name=name, mode=mode):
                with zipfile.ZipFile(archive, "w") as output:
                    info = zipfile.ZipInfo(name)
                    info.external_attr = (mode | 0o777) << 16
                    output.writestr(info, b"data")
                with self.assertRaises(cache.ToolchainError):
                    cache.extract_archive(archive, self.staging, "toolchain")

    def test_escaping_links_are_rejected(self):
        for kind, target in [("sym", "../../outside"), ("sym", "/outside"),
                             ("sym", "C:\\outside"), ("hard", "../outside")]:
            with self.subTest(kind=kind, target=target):
                tar_fixture(self.archive, [("toolchain/link", kind, target, 0o777)])
                with self.assertRaises(cache.ToolchainError):
                    cache.extract_archive(self.archive, self.staging, "toolchain")

    def test_file_under_symlink_does_not_write_through_link(self):
        tar_fixture(self.archive, [("toolchain/link", "sym", "../../outside", 0o777),
                                   ("toolchain/link/file", "file", b"bad", 0o644)])
        with self.assertRaises(cache.ToolchainError):
            cache.extract_archive(self.archive, self.staging, "toolchain")
        self.assertFalse((self.root / "outside").exists())

    def test_looping_link_chain_is_rejected(self):
        tar_fixture(self.archive, [("toolchain/a", "sym", "b", 0o777),
                                   ("toolchain/b", "sym", "a", 0o777)])
        with self.assertRaises(cache.ToolchainError):
            cache.extract_archive(self.archive, self.staging, "toolchain")

    def test_special_tar_members_are_rejected(self):
        tar_fixture(self.archive, [("toolchain/fifo", "fifo", b"", 0o644)])
        with self.assertRaises(cache.ToolchainError):
            cache.extract_archive(self.archive, self.staging, "toolchain")

    def test_duplicate_file_is_rejected(self):
        tar_fixture(self.archive, [("toolchain/file", "file", b"first", 0o644),
                                   ("toolchain/file", "file", b"second", 0o644)])
        with self.assertRaises(cache.ToolchainError):
            cache.extract_archive(self.archive, self.staging, "toolchain")


class DownloadTests(FixtureTests):
    def test_verified_archive_reused_offline(self):
        asset = self.good_archive()
        target = self.cache / "archives" / self.archive.name
        target.parent.mkdir(parents=True)
        target.write_bytes(self.archive.read_bytes())
        with mock.patch.object(cache.urllib.request, "urlopen") as download:
            self.assertEqual(cache.archive_for(asset, self.cache, offline=True), target)
        download.assert_not_called()

    def test_legacy_archive_reuse_is_verified_and_not_modified(self):
        asset = self.good_archive()
        legacy = self.root / "project/build/toolchains" / self.archive.name
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(self.archive.read_bytes())
        before = legacy.stat()
        with mock.patch.object(cache, "ROOT", self.root / "project"), \
                mock.patch.object(cache.urllib.request, "urlopen") as download:
            self.assertEqual(cache.archive_for(asset, self.cache, offline=True), legacy)
        self.assertEqual(legacy.stat().st_mtime_ns, before.st_mtime_ns)
        download.assert_not_called()

    def test_offline_missing_or_corrupt_cache_is_actionable(self):
        asset = self.good_archive()
        for corrupt in (False, True):
            if corrupt:
                target = self.cache / "archives" / self.archive.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"corrupt")
            with self.subTest(corrupt=corrupt), self.assertRaisesRegex(cache.ToolchainError, "Offline"):
                cache.archive_for(asset, self.cache, offline=True)

    def test_online_download_is_published_only_after_size_and_hash_match(self):
        asset = self.good_archive()
        for payload in (b"wrong", b"x" * (asset["size"] + 1)):
            with self.subTest(size=len(payload)), \
                    mock.patch.object(cache.urllib.request, "urlopen", return_value=io.BytesIO(payload)), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(cache.ToolchainError):
                cache.archive_for(asset, self.cache)
            self.assertFalse((self.cache / "archives" / asset["filename"]).exists())
            self.assertFalse(list((self.cache / "archives").glob("*.part")))
        with mock.patch.object(cache.urllib.request, "urlopen", return_value=io.BytesIO(self.archive.read_bytes())), \
                contextlib.redirect_stderr(io.StringIO()):
            result = cache.archive_for(asset, self.cache)
        self.assertTrue(cache.verified_archive(result, asset))

    def test_truncated_download_is_cleaned_and_reports_retry(self):
        asset = self.good_archive()
        with mock.patch.object(cache.urllib.request, "urlopen", side_effect=IncompleteRead(b"part", 20)), \
                contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaisesRegex(cache.ToolchainError, "retry"):
            cache.archive_for(asset, self.cache)
        self.assertFalse(list((self.cache / "archives").glob("*.part")))


class ProvisionTests(FixtureTests):
    def setUp(self):
        super().setUp()
        self.asset_data = self.good_archive()
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"schema": 1, "hosts": {"macos-arm64": self.asset_data}}))
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(cache, "MANIFEST", self.manifest).start()
        mock.patch.object(cache, "archive_for", return_value=self.archive).start()
        self.stderr = contextlib.redirect_stderr(io.StringIO())
        self.stderr.__enter__()
        self.addCleanup(self.stderr.__exit__, None, None, None)

    def test_provision_publishes_valid_root_and_reuses_it_without_unpacking(self):
        result = cache.provision_llvm("macos-arm64", cache=self.cache)
        self.assertTrue(cache.ready(result, self.asset_data, "macos-arm64"))
        self.assertTrue((result / "bin/aarch64-w64-mingw32-clang++").is_symlink())
        with mock.patch.object(cache, "extract_archive") as extract:
            self.assertEqual(cache.provision_llvm("macos-arm64", cache=self.cache, offline=True), result)
        extract.assert_not_called()
        self.assertFalse(list((self.cache / "installed").glob(".staging-*")))

    def test_incomplete_extraction_is_not_published_and_retry_succeeds(self):
        with mock.patch.object(cache, "extract_archive", side_effect=cache.ToolchainError("interrupted")):
            with self.assertRaisesRegex(cache.ToolchainError, "interrupted"):
                cache.provision_llvm("macos-arm64", cache=self.cache)
        self.assertEqual(list((self.cache / "installed").iterdir()), [])
        result = cache.provision_llvm("macos-arm64", cache=self.cache)
        self.assertTrue(cache.ready(result, self.asset_data, "macos-arm64"))

    def test_owned_damaged_install_is_rebuilt(self):
        result = cache.provision_llvm("macos-arm64", cache=self.cache)
        (result / "bin/wrapper.sh").unlink()
        self.assertFalse(cache.ready(result, self.asset_data, "macos-arm64"))
        self.assertEqual(cache.provision_llvm("macos-arm64", cache=self.cache, offline=True), result)
        self.assertTrue(cache.ready(result, self.asset_data, "macos-arm64"))

    def test_unowned_directory_is_not_removed(self):
        result = cache.provision_llvm("macos-arm64", cache=self.cache)
        (result / cache.OWNER).unlink()
        (result / "user-file").write_text("keep")
        with self.assertRaisesRegex(cache.ToolchainError, "unowned"):
            cache.provision_llvm("macos-arm64", cache=self.cache)
        self.assertEqual((result / "user-file").read_text(), "keep")

    def test_unsupported_host_has_clear_error(self):
        with self.assertRaisesRegex(cache.ToolchainError, "No pinned"):
            cache.provision_llvm("linux-riscv64", cache=self.cache)


if __name__ == "__main__":
    unittest.main()
