#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Fetch the manifest-pinned CC0 network, verifying before atomic installation.

The binary network is deliberately not versioned with engine source. The full
digest comes from the official network repository's Git LFS pointer and was
independently verified against the payload. No third-party packages are needed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request


def fingerprint(path):
    """Hash a local artifact without loading its entire contents into memory."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def matches(path, manifest):
    return path.is_file() and fingerprint(path) == (manifest["size_bytes"], manifest["sha256"])


def install(stream, destination, manifest):
    """Stage the bytes beside the destination; never replace it with a bad file."""
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".nnue-", delete=False) as output:
            name = Path(output.name)
            size = 0
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                if size > manifest["size_bytes"]:
                    raise ValueError("download exceeds the pinned network size")
                output.write(block)
                digest.update(block)
            if (size, digest.hexdigest()) != (manifest["size_bytes"], manifest["sha256"]):
                raise ValueError("network size or SHA-256 does not match the pinned manifest")
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, destination)
        name = None
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="verify local network; never download")
    parser.add_argument("--output", type=Path, help="destination (defaults to networks/<pinned name>)")
    parser.add_argument("--from-file", type=Path, help="install an already downloaded, verified local payload")
    args = parser.parse_args()
    manifest = json.loads((root / "networks/manifest.json").read_text())
    if manifest["filename"] != "nn-" + manifest["sha256"][:12] + ".nnue":
        raise ValueError("manifest filename does not match its SHA-256 prefix")
    destination = args.output or root / "networks" / manifest["filename"]
    if matches(destination, manifest):
        print("Verified:", destination)
        return 0
    if args.verify_only:
        print("Missing or invalid pinned network:", destination, file=sys.stderr)
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    if args.from_file:
        with args.from_file.open("rb") as source:
            install(source, destination, manifest)
    else:
        errors = []
        for url in manifest["download_urls"]:
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "chess0live-network-fetch/0.1"})
                with urllib.request.urlopen(request, timeout=60) as source:
                    install(source, destination, manifest)
                break
            except (OSError, ValueError) as error:
                errors.append(str(error))
        else:
            raise RuntimeError("Network download failed: " + "; ".join(errors))
    print("Installed and verified:", destination)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as failure:
        print("Error:", failure, file=sys.stderr)
        sys.exit(1)
