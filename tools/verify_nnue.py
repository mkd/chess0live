#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Reproduce exact SF19 feature, accumulator, layer and raw-score comparisons.

Upstream sources are fetched into an ignored build directory and compiled as a
separate test executable. No upstream implementation enters the production tree.
Requires Python 3.9+, Git, Make, and Clang or GCC with C++26 draft support.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys

from fetch_network import fingerprint
from resources import current_budget


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def run(command, log, cwd=None, input_data=None):
    """Retain full commands/output for diagnosis while keeping progress concise."""
    log.write(("$ " + shlex.join(map(str, command)) + "\n").encode())
    log.flush()
    result = subprocess.run(list(map(str, command)), cwd=cwd, input=input_data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log.write(result.stdout)
    log.write(result.stderr)
    log.flush()
    if result.returncode:
        raise RuntimeError("Command failed; see build.log: " + shlex.join(map(str, command)))
    return result.stdout


def compare(expected, actual, name, corpus):
    """Compare complete canonical integer records, not floating point scores."""
    left, right = expected.splitlines(), actual.splitlines()
    if len(left) != len(right) or len(left) != len(corpus.splitlines()):
        raise RuntimeError(name + ": output/corpus record counts differ")
    for index, (want, got) in enumerate(zip(left, right)):
        if want != got:
            fields = [str(i) for i, (a, b) in enumerate(zip(want.split(b";"), got.split(b";"))) if a != b]
            raise RuntimeError(name + ": mismatch at zero-based position " + str(index)
                               + ", stage fields " + ",".join(fields)
                               + "; FEN " + corpus.splitlines()[index].decode())


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", default=os.environ.get("CXX", "clang++"), help="local Clang/GCC C++ driver")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2, help="maximum upstream compiler jobs")
    parser.add_argument("--reference-arch", choices=("auto", "general-64", "apple-silicon"), default="auto")
    parser.add_argument("--work-dir", type=Path, default=root / "build/nnue-oracle")
    parser.add_argument("--network", type=Path, help="manifest-pinned file, already downloaded")
    args = parser.parse_args()
    manifest = json.loads((root / "networks/manifest.json").read_text())
    network = (args.network or root / "networks" / manifest["filename"]).resolve()
    if fingerprint(network) != (manifest["size_bytes"], manifest["sha256"]):
        raise RuntimeError("Network checksum mismatch; run python3 tools/fetch_network.py first")
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    reference = work / "stockfish-reference"
    compiler = shlex.split(args.compiler)
    if not compiler or not shutil.which(compiler[0]):
        raise RuntimeError("C++ compiler unavailable: " + args.compiler)
    compiler[0] = str(Path(shutil.which(compiler[0])).resolve())
    arch = args.reference_arch
    if arch == "auto":
        arch = "apple-silicon" if platform.system() == "Darwin" and platform.machine() == "arm64" else "general-64"
    with (work / "build.log").open("wb") as log:
        version = run(compiler + ["--version"], log).decode().splitlines()[0]
        reference_compiler = "clang" if "clang" in version.lower() else "gcc"
        if not reference.exists():
            print("Fetching the immutable Stockfish 19 reference", flush=True)
            run(["git", "clone", "--depth", "1", "--branch", manifest["reference_tag"],
                 "https://github.com/official-stockfish/Stockfish.git", reference], log)
        revision = run(["git", "rev-parse", "HEAD"], log, reference).decode().strip()
        if revision != manifest["reference_commit"]:
            raise RuntimeError("Reference checkout does not match the pinned commit; use a new --work-dir")
        # Always patch from the immutable blob. Upstream source notices remain
        # intact; only a private access label is opened in this test checkout.
        header = run(["git", "show", "HEAD:src/nnue/network.h"], log, reference).decode()
        if header.count("   private:") != 1:
            raise RuntimeError("Unexpected upstream Network access layout")
        header = header.replace("   private:", "   public: // Test-only stage inspection.")
        header_path = reference / "src/nnue/network.h"
        if header_path.read_text() != header:
            header_path.write_text(header)
        adapter = (root / "tools/oracle/reference_main.cpp").read_bytes()
        main_path = reference / "src/main.cpp"
        if main_path.read_bytes() != adapter:
            main_path.write_bytes(adapter)
        stamp = work / "reference-build-config.json"
        config = {"architecture": arch, "compiler_family": reference_compiler,
                  "compiler_argv": compiler, "compiler_version": version}
        if stamp.exists() and json.loads(stamp.read_text()) != config:
            run(["make", "objclean"], log, reference / "src")
        print("Building separate reference and local scalar/native adapters", flush=True)
        allowance = current_budget()
        jobs = min(args.jobs, allowance["max_cpu_workers"])
        run(["make", "-j" + str(jobs), "all", "ARCH=" + arch,
             "COMP=" + reference_compiler, "CXX=" + shlex.join(compiler),
             "EXTRACXXFLAGS=-DNNUE_EMBEDDING_OFF"], log, reference / "src")
        stamp.write_text(json.dumps(config, indent=2) + "\n")
        common = compiler + ["-std=c++2c", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                             "-I" + str(root / "include"), "-I" + str(root / "src")]
        suffix = ".exe" if os.name == "nt" else ""
        tests = {}
        stages = {}
        for backend, flags in (("native", []), ("scalar", ["-DCHESS0LIVE_FORCE_SCALAR"])):
            tests[backend] = work / ("nnue-test-" + backend + suffix)
            stages[backend] = work / ("nnue-stages-" + backend + suffix)
            run(common + flags + [root / "tests/nnue_test.cpp", root / "src/nnue.cpp",
                                 root / "src/position.cpp", "-o", tests[backend]], log)
            run(common + flags + [root / "tools/oracle/chess0live_stages.cpp",
                                 root / "src/position.cpp", "-o", stages[backend]], log)
            run([tests[backend], "--network", network], log)
        corpus = run([tests["native"], "--positions"], log)
        (work / "positions.fen").write_bytes(corpus)
        reference_executable = reference / "src" / ("stockfish" + suffix)
        print("Comparing " + str(len(corpus.splitlines())) + " positions at every integer stage", flush=True)
        # Dump output is intentionally excluded from build.log; files below keep
        # all 25 MB per backend without multiplying log size unnecessarily.
        def capture(command, name):
            result = subprocess.run(list(map(str, command)), input=corpus,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            (work / name).write_bytes(result.stdout)
            return result.stdout
        expected_stages = capture([reference_executable, network], "reference-stages.txt")
        expected_raw = capture([reference_executable, network, "--raw"], "reference-raw.txt")
        outputs = {}
        for backend in ("native", "scalar"):
            actual_stages = capture([stages[backend], network], backend + "-stages.txt")
            actual_raw = capture([tests[backend], "--network", network, "--dump"], backend + "-raw.txt")
            compare(expected_stages, actual_stages, backend + " integer stages", corpus)
            compare(expected_raw, actual_raw, backend + " raw/wrapped scores", corpus)
            outputs[backend] = {"stages_sha256": digest(actual_stages), "raw_sha256": digest(actual_raw)}
        report = {
            "result": "PASS", "positions": len(corpus.splitlines()),
            "reference_commit": revision, "network_sha256": manifest["sha256"],
            "reference_architecture": arch, "compiler": version,
            "reference_compiler": version, "compiler_argv": compiler,
            "reference_compile_jobs": jobs, "resource_budget": allowance,
            "corpus_seed_hex": "4348455353304c49", "corpus_sha256": digest(corpus),
            "reference_stages_sha256": digest(expected_stages),
            "reference_raw_sha256": digest(expected_raw), "outputs": outputs,
            "source_sha256": {name: digest((root / name).read_bytes()) for name in (
                "src/nnue.cpp", "src/position.cpp", "tests/nnue_test.cpp",
                "tools/oracle/chess0live_stages.cpp", "tools/oracle/reference_main.cpp")},
        }
        (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print("PASS: scalar/native/reference stages and raw/wrapped scores agree exactly")
        print("Report:", work / "report.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("FAIL:", error, file=sys.stderr)
        sys.exit(1)
