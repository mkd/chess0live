#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Reproduce exact SF19 feature, accumulator, layer and raw-score comparisons.

The default and --network routes require the manifest-pinned network. Explicit
--candidate-network checks other SFNNv16 weights against the same separately
built SF19 oracle. Arithmetic agreement is neither training provenance nor
playing-strength evidence. Upstream code stays in an ignored reference checkout.
Requires Python 3.9+, Git, Make, and Clang or GCC with C++26 draft support.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import uuid

from fetch_network import fingerprint
from resources import current_budget
from tooling import setup_lock


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def identity(path):
    """Record an entire artifact without trusting its basename or timestamps."""
    path = Path(path).resolve()
    if not path.is_file():
        raise RuntimeError("Artifact is not a regular file: " + str(path))
    size, checksum = fingerprint(path)
    return {"path": str(path), "size_bytes": size, "sha256": checksum}


def save_report(path, report):
    """Replace stale success before work starts, then publish one final state."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def stop_process(process):
    """Stop compiler/oracle descendants as well as the immediate process."""
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        # Native Windows process-tree cancellation still needs qualification.
        if process.poll() is None:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.kill()
    return process.communicate()


def run(command, log, cwd=None, input_data=None, timeout=300, lock_fds=(), output=None):
    """Bound each process and preserve diagnostic output, including on failure.

    Canonical dumps go to their own files rather than duplicating 25 MB per
    backend in build.log. Inherited POSIX locks exclude overlapping runs if the
    controller is killed while a compiler still holds the checkout open.
    """
    command = list(map(str, command))
    log.write(("$ " + shlex.join(command) + "\n").encode())
    log.flush()
    options = {"pass_fds": tuple(lock_fds), "start_new_session": True} if os.name != "nt" else {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    def record(stdout, stderr):
        if output is None:
            log.write(stdout)
        else:
            Path(output).write_bytes(stdout)
        log.write(stderr)
        log.flush()
    try:
        stdout, stderr = process.communicate(input=input_data, timeout=timeout)
    except BaseException:
        record(*stop_process(process))
        raise
    record(stdout, stderr)
    if process.returncode:
        raise RuntimeError("Command failed; see build.log: " + shlex.join(command))
    return stdout


@contextmanager
def interruption_cleanup():
    """Turn termination into an exception so child cleanup and FAIL reporting run."""
    previous = None
    if os.name != "nt" and threading.current_thread() is threading.main_thread():
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def compare(expected, actual, name, corpus):
    """Compare complete canonical integer records, not floating point scores."""
    left, right, positions = expected.splitlines(), actual.splitlines(), corpus.splitlines()
    if not positions or len(left) != len(right) or len(left) != len(positions):
        raise RuntimeError(name + ": output/corpus record counts differ or corpus is empty")
    for index, (want, got) in enumerate(zip(left, right)):
        if want != got:
            fields = [str(i) for i, (a, b) in enumerate(zip(want.split(b";"), got.split(b";"))) if a != b]
            raise RuntimeError(name + ": mismatch at zero-based position " + str(index)
                               + ", stage fields " + ",".join(fields)
                               + "; FEN " + positions[index].decode())


def local_sources(root):
    """Pin all local compilation inputs, including headers and test adapters."""
    paths = {root / name for name in (
        "src/nnue.cpp", "src/position.cpp", "tests/nnue_test.cpp",
        "tools/oracle/chess0live_stages.cpp", "tools/oracle/reference_main.cpp",
        "tools/verify_nnue.py")}
    paths.update((root / "include").rglob("*.hpp"))
    paths.update((root / "src").glob("*.hpp"))
    return {str(path.relative_to(root)): identity(path)["sha256"] for path in sorted(paths)}


def reference_sources(reference):
    """Record actual external source after the two independently written adapters."""
    paths = [p for p in (reference / "src").rglob("*")
             if p.is_file() and (p.suffix in (".cpp", ".h", ".hpp") or p.name == "Makefile")]
    return {str(p.relative_to(reference)): identity(p)["sha256"] for p in sorted(paths)}


def compiler_argv(args):
    """Preserve executable aliases and literal paths; legacy CXX keeps shlex parsing."""
    argv = [str(args.compiler_executable)] if args.compiler_executable else shlex.split(args.compiler)
    if not argv or not shutil.which(argv[0]):
        raise RuntimeError("C++ compiler unavailable: " + str(args.compiler_executable or args.compiler))
    # Resolving clang++/cross-target symlinks can change driver behavior.
    argv[0] = str(Path(shutil.which(argv[0])).absolute())
    return argv


def make_compiler_assignment(compiler):
    """Protect both GNU Make expansion and subsequent shell argument splitting."""
    return "CXX=" + shlex.join(compiler).replace("$", "$$")


def verify(args, root=None):
    """Run one locked experiment, preserving current-run failure evidence."""
    root = Path(root or Path(__file__).resolve().parent.parent).resolve()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    cache = (args.reference_dir or work / "stockfish-reference").resolve()
    if cache == work or cache in work.parents:
        raise RuntimeError("Reference cache must not contain the output directory")
    cache.parent.mkdir(parents=True, exist_ok=True)
    report_path = work / "report.json"
    report = {"schema": 2, "result": "RUNNING", "run_id": str(uuid.uuid4()),
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "SF19 integer arithmetic agreement; not provenance or playing strength",
              "work_dir": str(work), "reference_directory": str(cache),
              "candidate_requested": args.candidate_network is not None,
              "offline": args.offline, "command_timeout_seconds": args.timeout}
    with setup_lock(work / ".oracle.lock", timeout=args.lock_timeout) as work_lock:
        save_report(report_path, report)
        try:
            with interruption_cleanup(), setup_lock(
                    cache.parent / ("." + cache.name + ".oracle.lock"),
                    timeout=args.lock_timeout) as cache_lock, (work / "build.log").open("wb") as log:
                def command(argv, cwd=None, input_data=None, output=None):
                    return run(argv, log, cwd, input_data, args.timeout, (work_lock, cache_lock), output)

                manifest_path = root / "networks/manifest.json"
                manifest = json.loads(manifest_path.read_text())
                report["manifest"] = identity(manifest_path)
                network = (args.candidate_network or args.network
                           or root / "networks" / manifest["filename"]).resolve()
                if not network.is_file() or network.stat().st_size > 160 * 1024 * 1024:
                    raise RuntimeError("Network must be a regular SFNNv16 file no larger than 160 MiB")
                report["network"] = identity(network)
                report["network_sha256"] = report["network"]["sha256"]
                pinned = (report["network"]["size_bytes"], report["network_sha256"]) == (
                    manifest["size_bytes"], manifest["sha256"])
                report["network_pinned"] = pinned
                if not pinned and args.candidate_network is None:
                    raise RuntimeError("Network checksum mismatch; --network requires the pinned manifest payload")
                report["source_sha256"] = local_sources(root)
                compiler = compiler_argv(args)
                version = command(compiler + ["--version"]).decode().splitlines()[0]
                reference_compiler = "clang" if "clang" in version.lower() else "gcc"
                arch = args.reference_arch
                if arch == "auto":
                    arch = "apple-silicon" if platform.system() == "Darwin" and platform.machine() == "arm64" else "general-64"
                if not cache.exists():
                    if args.offline:
                        raise RuntimeError("Offline reference checkout is missing; provide --reference-dir with a cached pinned checkout")
                    print("Fetching the immutable Stockfish 19 reference", flush=True)
                    command(["git", "clone", "--depth", "1", "--branch", manifest["reference_tag"],
                             "https://github.com/official-stockfish/Stockfish.git", cache])
                revision = command(["git", "rev-parse", "HEAD"], cache).decode().strip()
                report["reference_commit"] = revision
                if revision != manifest["reference_commit"]:
                    raise RuntimeError("Reference checkout does not match the pinned commit; use a new --reference-dir")
                # Compile only committed source in a fresh local clone. Dirty or
                # ignored files/objects in a reusable cache never enter a build.
                # This is reproducibility isolation, not a security boundary for
                # a hostile local Git installation or compiler.
                reference = work / ("stockfish-build-" + report["run_id"])
                report["reference_build_directory"] = str(reference)
                command(["git", "clone", "--local", "--no-hardlinks", "--no-checkout", cache, reference])
                command(["git", "checkout", "--detach", revision], reference)
                if command(["git", "rev-parse", "HEAD"], reference).decode().strip() != revision:
                    raise RuntimeError("Fresh reference checkout does not match the pinned commit")
                header = command(["git", "show", "HEAD:src/nnue/network.h"], reference).decode()
                if header.count("   private:") != 1:
                    raise RuntimeError("Unexpected upstream Network access layout")
                header = header.replace("   private:", "   public: // Test-only stage inspection.")
                (reference / "src/nnue/network.h").write_text(header)
                (reference / "src/main.cpp").write_bytes((root / "tools/oracle/reference_main.cpp").read_bytes())
                report["reference_source_sha256"] = reference_sources(reference)
                config = {"architecture": arch, "compiler_family": reference_compiler,
                          "compiler_argv": compiler, "compiler_version": version}
                print("Building separate reference and local scalar/native adapters", flush=True)
                allowance = current_budget()
                jobs = min(args.jobs, allowance["max_cpu_workers"])
                command(["make", "-j" + str(jobs), "all", "ARCH=" + arch,
                         "COMP=" + reference_compiler, make_compiler_assignment(compiler),
                         "EXTRACXXFLAGS=-DNNUE_EMBEDDING_OFF"], reference / "src")
                (work / "reference-build-config.json").write_text(json.dumps(config, indent=2) + "\n")
                report.update({"reference_architecture": arch, "compiler": version,
                               "reference_compiler": version, "compiler_argv": compiler,
                               "reference_compile_jobs": jobs, "resource_budget": allowance})
                common = compiler + ["-std=c++2c", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                                     "-I" + str(root / "include"), "-I" + str(root / "src")]
                suffix = ".exe" if os.name == "nt" else ""
                tests, stages = {}, {}
                for backend, flags in (("native", []), ("scalar", ["-DCHESS0LIVE_FORCE_SCALAR"])):
                    tests[backend] = work / ("nnue-test-" + backend + suffix)
                    stages[backend] = work / ("nnue-stages-" + backend + suffix)
                    command(common + flags + [root / "tests/nnue_test.cpp", root / "src/nnue.cpp",
                                             root / "src/position.cpp", "-o", tests[backend]])
                    command(common + flags + [root / "tools/oracle/chess0live_stages.cpp",
                                             root / "src/position.cpp", "-o", stages[backend]])
                    if pinned:
                        command([tests[backend], "--network", network])
                report["pinned_goldens"] = "passed" if pinned else "not applicable to candidate weights"
                reference_executable = reference / "src" / ("stockfish" + suffix)
                binaries = {"reference": reference_executable,
                            **{name + "_raw": path for name, path in tests.items()},
                            **{name + "_stages": path for name, path in stages.items()}}
                report["binaries"] = {name: identity(path) for name, path in binaries.items()}
                corpus = command([tests["native"], "--positions"], output=work / "positions.fen")
                if not corpus.splitlines():
                    raise RuntimeError("Generated NNUE corpus is empty")
                report.update({"positions": len(corpus.splitlines()),
                               "corpus_seed_hex": "4348455353304c49", "corpus_sha256": digest(corpus)})
                print("Comparing " + str(report["positions"]) + " positions at every integer stage", flush=True)
                # Validate bounded wrapped scores before upstream evaluation.
                # --dump accepts candidate weights and checks incremental/full
                # refresh for every FEN without imposing pinned golden scores.
                raw = {backend: command([tests[backend], "--network", network, "--dump"],
                                        input_data=corpus, output=work / (backend + "-raw.txt"))
                       for backend in ("native", "scalar")}
                expected_stages = command([reference_executable, network], input_data=corpus,
                                          output=work / "reference-stages.txt")
                expected_raw = command([reference_executable, network, "--raw"], input_data=corpus,
                                       output=work / "reference-raw.txt")
                outputs = {}
                for backend in ("native", "scalar"):
                    actual_stages = command([stages[backend], network], input_data=corpus,
                                            output=work / (backend + "-stages.txt"))
                    compare(expected_stages, actual_stages, backend + " integer stages", corpus)
                    compare(expected_raw, raw[backend], backend + " raw/wrapped scores", corpus)
                    outputs[backend] = {"stages_sha256": digest(actual_stages), "raw_sha256": digest(raw[backend])}
                report.update({"reference_stages_sha256": digest(expected_stages),
                               "reference_raw_sha256": digest(expected_raw), "outputs": outputs})
                # Do not attribute mixed-input evidence to the initial hashes.
                if identity(network) != report["network"]:
                    raise RuntimeError("Network changed during qualification")
                if identity(manifest_path) != report["manifest"] or local_sources(root) != report["source_sha256"]:
                    raise RuntimeError("Manifest or local sources changed during qualification")
                if reference_sources(reference) != report["reference_source_sha256"]:
                    raise RuntimeError("Reference sources changed during qualification")
                if {name: identity(path) for name, path in binaries.items()} != report["binaries"]:
                    raise RuntimeError("A qualification binary changed during the run")
                report["result"] = "PASS"
        except BaseException as error:
            report["result"] = "FAIL"
            report["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            report["finished_utc"] = datetime.now(timezone.utc).isoformat()
            save_report(report_path, report)
    return report


def parse_args(argv=None):
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    compilers = parser.add_mutually_exclusive_group()
    compilers.add_argument("--compiler", default=os.environ.get("CXX", "clang++"), help="Clang/GCC driver command (legacy shell-style splitting)")
    compilers.add_argument("--compiler-executable", type=Path, help="literal local C++ compiler path, including spaces")
    parser.add_argument("--jobs", type=int, choices=(1, 2), default=2, help="maximum upstream compiler jobs")
    parser.add_argument("--reference-arch", choices=("auto", "general-64", "apple-silicon"), default="auto")
    parser.add_argument("--work-dir", type=Path, default=root / "build/nnue-oracle")
    parser.add_argument("--reference-dir", type=Path, help="cached pinned source; each run compiles a fresh local clone")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--network", type=Path, help="manifest-pinned file, already downloaded")
    network.add_argument("--candidate-network", type=Path, help="explicit SFNNv16 candidate; no pinned golden-value assumption")
    parser.add_argument("--offline", action="store_true", help="require a cached reference checkout; never download")
    parser.add_argument("--timeout", type=float, default=300, help="maximum seconds per compiler/oracle command")
    parser.add_argument("--lock-timeout", type=float, default=120, help="maximum seconds waiting for an active qualification")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not math.isfinite(args.lock_timeout) or args.lock_timeout < 0:
        parser.error("timeout must be finite and positive; lock-timeout finite and nonnegative")
    return args


def main():
    report = verify(parse_args())
    print("PASS: scalar/native/reference stages and raw/wrapped scores agree exactly")
    print("Report:", Path(report["work_dir"]) / "report.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("FAIL:", error, file=sys.stderr)
        sys.exit(1)
