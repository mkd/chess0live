#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Inspect NNUE files and qualify SFNNv16 arithmetic against the pinned oracle.

Uses Python's standard library only. Inspection never executes a network or
downloads anything. Qualification builds separate test programs; it does not
install a network into the engine or establish playing strength.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import struct
import subprocess
import sys

from fetch_network import fingerprint

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 160 * 1024 * 1024
MAX_DESCRIPTION = 1024 * 1024
VERSION = 0x6A448AFA
ARCHITECTURE = 0xA85B2205
TRANSFORMER = 0xCB685313


class NetworkToolError(RuntimeError):
    """A diagnostic failure that should be actionable without a traceback."""


def manifest():
    return json.loads((ROOT / "networks/manifest.json").read_text(encoding="utf-8"))


def default_network():
    return ROOT / "networks" / manifest()["filename"]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def unique_object(pairs):
    """Reject duplicate keys rather than silently changing a provenance claim."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise NetworkToolError("Duplicate metadata key: " + key)
        result[key] = value
    return result


def load_metadata(path: Path, digest: str) -> dict:
    """Validate optional, explicitly unverified claims bound to exact file bytes."""
    try:
        metadata_stat = path.stat()
        if not stat.S_ISREG(metadata_stat.st_mode):
            raise NetworkToolError("Metadata must be a regular file")
        if metadata_stat.st_size > MAX_DESCRIPTION:
            raise NetworkToolError("Metadata exceeds 1 MiB")
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, ValueError) as error:
        raise NetworkToolError("Cannot read metadata: " + str(error)) from error
    allowed = {"schema_version", "network_sha256", "name", "author", "license", "source", "training"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise NetworkToolError("Metadata must be an object containing only documented fields")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise NetworkToolError("Metadata schema_version must be 1")
    if data.get("network_sha256") != digest:
        raise NetworkToolError("Metadata network_sha256 does not match this file")
    for name in ("name", "author", "license", "source"):
        if data.get(name) is not None and not isinstance(data[name], str):
            raise NetworkToolError("Metadata " + name + " must be a string or null")
    training = data.get("training", {})
    if not isinstance(training, dict) or set(training) - {"games", "positions", "epochs", "data_sources"}:
        raise NetworkToolError("Metadata training must contain only documented fields")
    for name in ("games", "positions", "epochs"):
        value = training.get(name)
        if value is not None and (type(value) is not int or value < 0):
            raise NetworkToolError("Training " + name + " must be a nonnegative integer or null")
    sources = training.get("data_sources", [])
    if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
        raise NetworkToolError("Training data_sources must be a list of strings")
    return data


def header_identity(prefix: bytes, size: int) -> dict:
    """Recognize the pinned header only; payload validation belongs to qualify."""
    report = {"status": "malformed", "name": None, "description": None}
    if len(prefix) < 12:
        return dict(report, reason="Truncated NNUE header")
    version, architecture, count = struct.unpack_from("<III", prefix)
    report.update(version=f"0x{version:08x}", architecture_hash=f"0x{architecture:08x}",
                  description_bytes=count)
    if (version, architecture) != (VERSION, ARCHITECTURE):
        return dict(report, status="unsupported", reason="Unrecognized version or architecture")
    if count > MAX_DESCRIPTION:
        return dict(report, reason="Description exceeds the decoder's 1 MiB limit")
    end = 12 + count
    if end + 4 > size or len(prefix) < end + 4:
        return dict(report, reason="Truncated description or transformer header")
    description = prefix[12:end]
    # Description is untrusted text, not authoritative provenance or instructions.
    report.update(description=description[:1024].decode("utf-8", errors="replace"),
                  description_truncated=len(description) > 1024,
                  description_sha256=hashlib.sha256(description).hexdigest())
    transformer, = struct.unpack_from("<I", prefix, end)
    report["transformer_hash"] = f"0x{transformer:08x}"
    if transformer != TRANSFORMER:
        return dict(report, status="unsupported", reason="Unrecognized feature transformer")
    return dict(report, status="recognized_header", name="SFNNv16",
                reason="Header recognized; full payload and evaluation have not been checked")


def inspect_network(path: Path, metadata_path: Path | None = None) -> dict:
    """Hash one bounded regular-file stream and identify its header/provenance."""
    path = Path(path).resolve()
    try:
        # Reject devices/FIFOs before opening them; all supported inputs are files.
        if not stat.S_ISREG(path.stat().st_mode):
            raise NetworkToolError("Network must be a regular file")
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if before.st_size > MAX_FILE:
                raise NetworkToolError("Network exceeds the decoder's 160 MiB limit")
            digest = hashlib.sha256()
            prefix = stream.read(MAX_DESCRIPTION + 16)
            digest.update(prefix)
            size = len(prefix)
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(block)
                if size > MAX_FILE:
                    raise NetworkToolError("Network grew beyond the 160 MiB limit")
                digest.update(block)
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != after.st_size:
                raise NetworkToolError("Network changed during inspection; retry with an immutable file")
    except OSError as error:
        raise NetworkToolError("Cannot read network: " + str(error)) from error
    sha = digest.hexdigest()
    pin = manifest()
    pinned = (size, sha) == (pin["size_bytes"], pin["sha256"])
    declared = load_metadata(Path(metadata_path), sha) if metadata_path else None
    training = {key: None for key in ("games", "positions", "epochs")}
    training["data_sources"] = []
    if declared:
        training.update(declared.get("training", {}))
    provenance = {
        "source": "manifest_pinned" if pinned else "declared_unverified" if declared else "unknown",
        "license": pin["license"] if pinned else None,
        "training": training,
        "training_status": "declared_unverified" if declared and declared.get("training") else "unknown",
        "declared_metadata": declared,
    }
    if pinned:
        provenance["pinned_record"] = {key: pin[key] for key in
            ("reference_release", "reference_commit", "license_source", "digest_source")}
    return {
        "schema_version": 1, "operation": "inspect", "created_at": utc_now(),
        "artifact": {"path": str(path), "size_bytes": size, "sha256": sha},
        "architecture": header_identity(prefix, size), "provenance": provenance,
        "verification": {"file_identity": "manifest_pinned" if pinned else "unrecognized_digest",
                         "full_decoder": "not_run", "independent_oracle": "not_run",
                         "playing_strength": "not_measured"},
    }


def write_json(path: Path, data: dict, *, exclusive=True):
    """Refuse to overwrite user files; reports created in our fresh run may update."""
    try:
        with Path(path).open("x" if exclusive else "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=True, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError) as error:
        raise NetworkToolError("Cannot write report: " + str(error)) from error


def write_metadata_template(network: Path, output: Path):
    """Create an editable record; unknown training counts are never guessed."""
    info = inspect_network(network)
    write_json(output, {
        "schema_version": 1, "network_sha256": info["artifact"]["sha256"],
        "name": None, "author": None, "license": None, "source": None,
        "training": {"games": None, "positions": None, "epochs": None, "data_sources": []},
    })


def source_pins():
    """Bind the wrapper's decision to its local implementation and manifest."""
    paths = ("tools/network.py", "tools/verify_nnue.py", "networks/manifest.json")
    return {name: fingerprint(ROOT / name)[1] for name in paths}


def run_oracle(command):
    """Forward interruption to the harness so it can clean its child groups."""
    previous = signal.getsignal(signal.SIGTERM)
    process = None
    def interrupt(signum, frame):
        raise KeyboardInterrupt("Terminated")
    signal.signal(signal.SIGTERM, interrupt)
    try:
        process = subprocess.Popen(command, cwd=ROOT)
        return subprocess.CompletedProcess(command, process.wait())
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)


def qualify(args):
    """Save a fresh finite oracle run; never promote a network or reuse a PASS."""
    output = args.output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise NetworkToolError("Choose a new qualification output directory: " + str(error)) from error
    report = {"schema_version": 1, "operation": "qualify", "created_at": utc_now(),
              "status": "running", "verification": {"independent_oracle": "not_run",
                                                       "playing_strength": "not_measured"}}
    write_json(output / "report.json", report)
    try:
        report.update(inspect_network(args.network, args.metadata))
        report.update(operation="qualify", status="running", tooling_sha256=source_pins())
        if report["architecture"]["status"] != "recognized_header":
            raise NetworkToolError(report["architecture"]["reason"])
        compiler = args.compiler or os.environ.get("CXX_EXECUTABLE")
        if compiler:
            compiler = shutil.which(compiler)
        else:
            compiler = next((shutil.which(name) for name in ("clang++", "g++", "c++") if shutil.which(name)), None)
        if not compiler:
            raise NetworkToolError("Install a C++26-capable Clang/GCC compiler, or pass --compiler PATH")
        command = [sys.executable, str(ROOT / "tools/verify_nnue.py"),
                   "--candidate-network", report["artifact"]["path"], "--compiler-executable", os.path.abspath(compiler),
                   "--jobs", str(args.jobs), "--work-dir", str(output / "oracle"),
                   "--reference-dir", str(args.reference_dir.resolve())]
        if args.offline:
            command.append("--offline")
        report["command"] = command
        write_json(output / "report.json", report, exclusive=False)
        print("Checking the complete payload and native/scalar/reference arithmetic...", flush=True)
        # The harness owns timeouts, process groups, cache locks and child cleanup.
        # Running in the foreground also propagates ordinary console Ctrl-C.
        result = run_oracle(command)
        oracle_path = output / "oracle/report.json"
        oracle = json.loads(oracle_path.read_text(encoding="utf-8")) if oracle_path.is_file() else {}
        if not isinstance(oracle, dict):
            raise NetworkToolError("Oracle report must be a JSON object")
        report["oracle_report"] = str(oracle_path)
        report["oracle_report_sha256"] = fingerprint(oracle_path)[1] if oracle_path.is_file() else None
        current = inspect_network(args.network, args.metadata)
        if current["artifact"] != report["artifact"] or current["provenance"] != report["provenance"]:
            raise NetworkToolError("Network or provenance changed during qualification")
        if source_pins() != report["tooling_sha256"]:
            raise NetworkToolError("Qualification tooling changed during this run")
        if result.returncode or oracle.get("result") != "PASS":
            raise NetworkToolError("Oracle verification failed; see oracle/report.json and oracle/build.log")
        if (oracle.get("network_sha256") != report["artifact"]["sha256"]
                or oracle.get("reference_commit") != manifest()["reference_commit"]
                or type(oracle.get("positions")) is not int or oracle["positions"] <= 0):
            raise NetworkToolError("Oracle report identity or nonempty corpus check failed")
        report["status"] = "passed"
        report["verification"].update(full_decoder="passed", independent_oracle="passed",
                                      positions=oracle["positions"],
                                      scope="Exact SFNNv16 features, accumulators, integer stages and raw/wrapped outputs on the recorded corpus")
        print(f"PASS: {oracle['positions']} positions agree. Playing strength and training claims are unverified.")
        return 0
    except (OSError, ValueError, NetworkToolError, KeyboardInterrupt) as error:
        report.update(status="failed", error=str(error) or "Interrupted")
        print("FAIL: " + json.dumps(report["error"], ensure_ascii=True), file=sys.stderr)
        return 1
    finally:
        report["finished_at"] = utc_now()
        write_json(output / "report.json", report, exclusive=False)
        print("Report: " + json.dumps(str(output / "report.json"), ensure_ascii=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="hash and identify a local file without loading it")
    inspect.add_argument("network", type=Path, nargs="?", default=default_network())
    inspect.add_argument("--metadata", type=Path)
    inspect.add_argument("--output", type=Path, help="new JSON file; never overwritten")
    metadata = commands.add_parser("metadata", help="create an editable digest-bound provenance template")
    metadata.add_argument("network", type=Path)
    metadata.add_argument("--output", type=Path, required=True)
    check = commands.add_parser("qualify", help="build and compare separate local and SF19 oracle programs")
    check.add_argument("network", type=Path, nargs="?", default=default_network())
    check.add_argument("--output", type=Path,
                       default=ROOT / "results" / ("network-qualification-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")),
                       help="new result directory; defaults to a unique directory under results/")
    check.add_argument("--metadata", type=Path)
    check.add_argument("--compiler", help="literal native C++26 compiler executable path")
    check.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    check.add_argument("--reference-dir", type=Path, default=ROOT / ".local/networks/sf19-reference")
    check.add_argument("--offline", action="store_true", help="require an already cached SF19 reference")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect_network(args.network, args.metadata)
            if args.output:
                write_json(args.output, report)
            print(json.dumps(report, indent=2, ensure_ascii=True))
        elif args.command == "metadata":
            write_metadata_template(args.network, args.output)
            print("Metadata template: " + json.dumps(str(args.output), ensure_ascii=True))
        else:
            return qualify(args)
        return 0
    except (NetworkToolError, OSError, ValueError) as error:
        print("Error: " + json.dumps(str(error), ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
