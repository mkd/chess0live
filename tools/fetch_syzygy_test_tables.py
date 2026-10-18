#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Install the small, pinned external Syzygy test corpus and its source notices.

No table data is bundled with the engine. Each downloaded file is staged beside
its destination and checked for exact length and SHA-256 before replacement.
Interrupted multi-file downloads are resumable: already verified files are kept.
The manifest records provenance without inventing a license for generated data.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import urllib.request


MAX_TOTAL_BYTES = 20 * 1024 * 1024
SCHEMA = "chess0live-syzygy-test-data-v1"
REPOSITORY = "https://github.com/niklasf/python-chess"
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests/data/syzygy-test-manifest.json"


def load_manifest(path=MANIFEST):
    """Reject ambiguous destinations, mutable source URLs, and oversized input."""
    data = json.loads(Path(path).read_text())
    if data.get("schema") != SCHEMA or data.get("source_repository") != REPOSITORY:
        raise ValueError("unknown Syzygy test manifest schema or repository")
    revision = data.get("source_revision", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("source revision must be a full immutable Git commit")
    expected_base = f"https://raw.githubusercontent.com/niklasf/python-chess/{revision}/"
    if data.get("download_base_url") != expected_base:
        raise ValueError("download URL does not match the pinned repository revision")
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must contain files")
    names = set()
    total = 0
    for entry in entries:
        name = entry.get("filename", "")
        is_table = re.fullmatch(r"K[QRBNP]*vK[QRBNP]*\.rtb[wz]", name)
        is_notice = name in ("UPSTREAM-SOURCE.txt", "UPSTREAM-LICENSE.txt")
        if not (is_table or is_notice) or name in names:
            raise ValueError("invalid or duplicate table/notice filename")
        names.add(name)
        expected_path = ({"UPSTREAM-SOURCE.txt": "data/syzygy/regular/SOURCE.txt",
                          "UPSTREAM-LICENSE.txt": "LICENSE.txt"}.get(name)
                         or "data/syzygy/regular/" + name)
        source = entry.get("source_path")
        if source != expected_path or str(PurePosixPath(source)) != source:
            raise ValueError("unexpected table source path")
        size = entry.get("size_bytes")
        if type(size) is not int or not 0 < size <= MAX_TOTAL_BYTES:
            raise ValueError("invalid pinned file size")
        if not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", "")):
            raise ValueError("invalid pinned SHA-256")
        total += size
    if not {"UPSTREAM-SOURCE.txt", "UPSTREAM-LICENSE.txt"} <= names:
        raise ValueError("upstream source and license notices must be preserved")
    if total > MAX_TOTAL_BYTES or data.get("total_bytes") != total:
        raise ValueError("manifest size does not match the bounded corpus")
    return data


def fingerprint(path):
    """Hash a local file in bounded chunks, including its exact length."""
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def matches(path, entry):
    return path.is_file() and fingerprint(path) == (entry["size_bytes"], entry["sha256"])


def install(stream, destination, entry):
    """Never expose a truncated, oversized, or digest-mismatched replacement."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,
                                         prefix=".syzygy-", delete=False) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                if size > entry["size_bytes"]:
                    raise ValueError("download exceeds the pinned table size")
                output.write(block)
                digest.update(block)
            if (size, digest.hexdigest()) != (entry["size_bytes"], entry["sha256"]):
                raise ValueError("table size or SHA-256 differs from its manifest")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch(manifest, directory, *, verify_only=False, from_directory=None):
    """Install or check every pinned file; verification never creates files."""
    directory = Path(directory)
    invalid = []
    if not verify_only:
        directory.mkdir(parents=True, exist_ok=True)
    for entry in manifest["files"]:
        destination = directory / entry["filename"]
        if matches(destination, entry):
            continue
        if verify_only:
            invalid.append(entry["filename"])
            continue
        if from_directory is not None:
            with (Path(from_directory) / entry["filename"]).open("rb") as source:
                install(source, destination, entry)
        else:
            request = urllib.request.Request(
                manifest["download_base_url"] + entry["source_path"],
                headers={"User-Agent": "chess0live-syzygy-test-fetch/0.1"})
            with urllib.request.urlopen(request, timeout=30) as source:
                install(source, destination, entry)
    if invalid:
        raise ValueError("Missing or invalid pinned files: " + ", ".join(invalid))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "tablebases/test",
                        help="fixture directory (default: tablebases/test)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true",
                      help="verify existing files without downloading or writing")
    mode.add_argument("--from-directory", type=Path,
                      help="install verified copies from an offline source directory")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    fetch(manifest, args.directory, verify_only=args.verify_only,
          from_directory=args.from_directory)
    print(f"Verified {len(manifest['files'])} files / {manifest['total_bytes']} bytes in {args.directory}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print("Error:", error, file=sys.stderr)
        sys.exit(1)
