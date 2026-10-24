#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Recheck retained network qualification evidence without executing its contents.

The managed catalog calls this after its own fresh qualification and before
selection or launch. These are local integrity records, not signed provenance:
matching arithmetic does not authenticate training claims or establish strength.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import stat

import network
from network import NetworkToolError
from verify_nnue import local_sources

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_POSITIONS = 2057
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_EVIDENCE_BYTES = 256 * 1024 * 1024


def require(condition: bool, message: str):
    """Convert malformed or stale evidence into the public tool's error type."""
    if not condition:
        raise NetworkToolError("Qualification evidence: " + message)


def inside(base: Path, path: Path) -> Path:
    """Resolve symlinks and refuse evidence paths outside the owned run tree."""
    resolved = path.resolve()
    require(resolved.is_relative_to(base.resolve()), "path escapes the retained run directory")
    return resolved


def checked_file(path: Path, maximum: int = MAX_EVIDENCE_BYTES) -> tuple[int, str, int]:
    """Hash bounded regular bytes and count canonical newline records.

    For binaries the record count is unused. Checking the open file's identity
    before and after hashing prevents accepting an ordinarily changing file.
    """
    info = path.stat()
    require(stat.S_ISREG(info.st_mode), "expected a regular evidence file")
    require(0 < info.st_size <= maximum, "empty or oversized evidence file")
    digest = hashlib.sha256()
    length = 0
    records = 0
    tail = b""
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            length += len(block)
            require(length <= maximum, "evidence grew beyond its size bound")
            digest.update(block)
            records += block.count(b"\n")
            tail = block[-1:]
        after = os.fstat(stream.fileno())
    current = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino)
            == (after.st_size, after.st_mtime_ns, after.st_ino)
            == (current.st_size, current.st_mtime_ns, current.st_ino)
            and length == after.st_size, "file changed while being inspected")
    # Oracle canonical dumps always end in LF. Missing final LF is a changed
    # artifact and its hash will also fail; retain an exact splitlines count.
    return length, digest.hexdigest(), records + (tail != b"\n")


def read_report(path: Path) -> dict:
    """Read bounded JSON while rejecting duplicate keys and non-object roots."""
    checked_file(path, MAX_REPORT_BYTES)
    with path.open("rb") as stream:
        payload = stream.read(MAX_REPORT_BYTES + 1)
    require(len(payload) <= MAX_REPORT_BYTES, "report grew beyond its size bound")
    def invalid_constant(value):
        raise NetworkToolError("Qualification evidence: invalid JSON number")
    result = json.loads(payload, object_pairs_hook=network.unique_object,
                        parse_constant=invalid_constant)
    require(isinstance(result, dict), "report must be an object")
    return result


def validate_qualification(directory: Path, network_path: Path,
                           metadata_path: Path | None = None, *, require_current=True) -> dict:
    """Verify the finite SFNNv16 qualification retained by one catalog entry.

    No executable or shell command from a report is run. A registration owns
    this run directory and retains its corpus, outputs, binaries and reference
    source tree. Current source mismatches refuse selection/launch by default;
    inspection may request historical evidence with ``require_current=False``.
    """
    try:
        directory = Path(directory).resolve()
        report_path = inside(directory, directory / "report.json")
        oracle_path = inside(directory, directory / "oracle/report.json")
        report_sha = checked_file(report_path, MAX_REPORT_BYTES)[1]
        oracle_sha = checked_file(oracle_path, MAX_REPORT_BYTES)[1]
        report = read_report(report_path)
        oracle = read_report(oracle_path)
        require(type(report.get("schema_version")) is int and report["schema_version"] == 1
                and report.get("operation") == "qualify" and report.get("status") == "passed",
                "missing successful qualification report")
        require(type(oracle.get("schema")) is int and oracle["schema"] == 2
                and oracle.get("result") == "PASS", "missing successful oracle report")
        require(Path(report["oracle_report"]).resolve() == oracle_path,
                "oracle report location differs")
        require(report.get("oracle_report_sha256") == oracle_sha, "oracle report hash differs")

        inspected = network.inspect_network(Path(network_path), metadata_path)
        require(inspected["architecture"]["status"] == "recognized_header",
                "managed network architecture is unsupported")
        require(report.get("artifact") == inspected["artifact"]
                and oracle.get("network") == inspected["artifact"]
                and oracle.get("network_sha256") == inspected["artifact"]["sha256"],
                "network identity differs")
        require(report.get("architecture") == inspected["architecture"], "architecture record differs")
        require(report.get("provenance") == inspected["provenance"], "provenance record differs")
        require(oracle.get("reference_commit") == network.manifest()["reference_commit"],
                "reference commit differs from the architecture pin")
        verification = report["verification"]
        require(isinstance(verification, dict)
                and verification.get("independent_oracle") == "passed"
                and verification.get("full_decoder") == "passed",
                "decoder/oracle checks did not pass")
        for count in (oracle.get("positions"), verification.get("positions")):
            require(type(count) is int and count == EXPECTED_POSITIONS,
                    "expected the complete 2,057-position corpus")

        current = (report.get("tooling_sha256") == network.source_pins()
                   and oracle.get("source_sha256") == local_sources(ROOT))
        require(not require_current or current,
                "evaluation or qualification sources changed; register a fresh check")
        require(isinstance(report.get("tooling_sha256"), dict)
                and isinstance(oracle.get("source_sha256"), dict)
                and bool(oracle["source_sha256"]), "missing source identity records")

        work = oracle_path.parent
        require(Path(oracle["work_dir"]).resolve() == work, "oracle work directory differs")
        _, corpus_sha, positions = checked_file(inside(directory, work / "positions.fen"))
        require(corpus_sha == oracle.get("corpus_sha256") and positions == EXPECTED_POSITIONS,
                "corpus hash or record count differs")
        outputs = oracle["outputs"]
        require(isinstance(outputs, dict) and set(outputs) == {"native", "scalar"},
                "missing native/scalar output records")
        for kind in ("raw", "stages"):
            _, expected, records = checked_file(inside(directory, work / f"reference-{kind}.txt"))
            require(records == EXPECTED_POSITIONS
                    and expected == oracle.get(f"reference_{kind}_sha256"),
                    "reference output hash or record count differs")
            for backend in ("native", "scalar"):
                _, actual, records = checked_file(inside(directory, work / f"{backend}-{kind}.txt"))
                require(isinstance(outputs[backend], dict)
                        and records == EXPECTED_POSITIONS and actual == expected
                        and actual == outputs[backend].get(f"{kind}_sha256"),
                        "native/scalar output disagrees with the complete reference")

        binaries = oracle["binaries"]
        require(isinstance(binaries, dict) and set(binaries) == {
            "reference", "native_raw", "scalar_raw", "native_stages", "scalar_stages"},
            "missing qualification binaries")
        for entry in binaries.values():
            require(isinstance(entry, dict), "invalid binary record")
            path = inside(directory, Path(entry["path"]))
            size, checksum, _ = checked_file(path)
            require(type(entry.get("size_bytes")) is int and entry["size_bytes"] == size
                    and entry.get("sha256") == checksum, "qualification binary identity differs")

        reference = inside(directory, Path(oracle["reference_build_directory"]))
        sources = oracle["reference_source_sha256"]
        require(isinstance(sources, dict) and bool(sources), "missing reference source identities")
        for relative, expected in sources.items():
            require(isinstance(relative, str) and not Path(relative).is_absolute(),
                    "invalid reference source path")
            actual = checked_file(inside(reference, reference / relative))[1]
            require(actual == expected, "retained reference source changed")

        timestamp = report["finished_at"]
        require(isinstance(timestamp, str) and datetime.fromisoformat(timestamp).tzinfo is not None,
                "missing qualification completion timestamp")
        require(checked_file(report_path, MAX_REPORT_BYTES)[1] == report_sha
                and checked_file(oracle_path, MAX_REPORT_BYTES)[1] == oracle_sha,
                "reports changed while evidence was inspected")
        return {
            "schema_version": 1, "status": "passed", "positions": EXPECTED_POSITIONS,
            "current_sources": current, "qualified_at": timestamp,
            "qualification_report_sha256": report_sha,
            "oracle_report_sha256": oracle_sha, "network_sha256": inspected["artifact"]["sha256"],
            "scope": "Finite SFNNv16 arithmetic agreement; training claims and playing strength unverified",
        }
    except NetworkToolError:
        raise
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        raise NetworkToolError("Qualification evidence is missing or invalid: " + str(error)) from error
