#!/usr/bin/env python3
"""Select/check a target toolchain and build through the project's GNU Makefile.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfoNotFoundError

from resources import current_budget
from toolchain_cache import MANIFEST, ToolchainError, provision_llvm
from tooling import ToolingError, setup_command, setup_lock
from verify_runtime import TARGETS, binary_fingerprint, host_identity

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = {
    "linux-arm64": ("aarch64-linux-gnu", "aarch64-unknown-linux-gnu"),
    "linux-x86_64": ("x86_64-linux-gnu", "x86_64-unknown-linux-gnu"),
    "linux-riscv64": ("riscv64-linux-gnu", "riscv64-unknown-linux-gnu"),
    "windows-arm64": ("aarch64-w64-mingw32",),
    "windows-x86_64": ("x86_64-w64-mingw32",),
}


def executable(value: str) -> str | None:
    """Preserve the invoked basename: compiler symlinks can select the target."""
    found = shutil.which(value)
    return os.path.abspath(found) if found else None


def prerequisites(target: str, host: str) -> str:
    if target == "macos-arm64":
        return "Use macOS with Apple's Command Line Tools/SDK and a C++26-capable compiler."
    if target.startswith("windows"):
        return ("Use --toolchain llvm-mingw for the pinned local download on a supported host, "
                "or --compiler /path/to/aarch64-or-x86_64-w64-mingw32-clang++.")
    prefix = PREFIXES[target][0]
    return (f"Install a complete C++26-capable {prefix} GCC toolchain with target libc/C++ "
            "headers and libraries, or pass --compiler to an existing toolchain. "
            "For Debian trixie cross-builds, see the exact package examples in docs/PORTABILITY.md. "
            "This command does not install system packages or an Apple SDK.")


def compiler_candidates(target: str, host: str, explicit: str | None = None) -> list[str]:
    if explicit:
        path = executable(explicit)
        if not path:
            raise ToolingError(f"Compiler executable not found: {explicit}")
        return [path]
    names = []
    if target == host:
        names.extend(["c++", "clang++", "g++"])
        names.extend(f"g++-{version}" for version in range(17, 13, -1))
    for prefix in PREFIXES.get(target, ()):
        names.extend([prefix + "-g++", prefix + "-clang++"])
        names.extend(f"{prefix}-g++-{version}" for version in range(17, 13, -1))
    # Do not deduplicate by resolved target: different aliases can mean different CPUs.
    return list(dict.fromkeys(path for name in names if (path := executable(name))))


def make_program(explicit: str | None, bundle: Path | None) -> tuple[str, str | None]:
    """Prefer the bundled Windows Make/shell as a pair when available."""
    shell = None
    candidates = [explicit] if explicit else []
    if bundle and os.name == "nt":
        shell_path = bundle / "busybox/bin/sh.exe"
        if shell_path.is_file():
            shell = str(shell_path)
            if not explicit:
                candidates.extend([str(bundle / "bin/mingw32-make.exe"),
                                   str(bundle / "busybox/bin/make.exe")])
    if not explicit:
        candidates.extend(["gmake", "make", "mingw32-make"])
    for name in candidates:
        path = executable(name)
        if not path:
            continue
        try:
            version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            if version.returncode == 0 and "GNU Make" in version.stdout:
                return path, shell
        except (OSError, subprocess.SubprocessError):
            pass
    raise ToolingError("GNU Make was not found. Install GNU Make, or pass --make /path/to/make.")


def job_limit(requested: int | None) -> int:
    """Use at most two jobs by default, within the current local resource policy."""
    try:
        maximum = current_budget()["max_cpu_workers"]
    except ZoneInfoNotFoundError:
        # Minimal Windows Python may lack IANA timezone data. One worker is a
        # conservative portable fallback, without silently downloading tzdata.
        maximum = 1
    if requested is None:
        return min(2, maximum)
    if not 1 <= requested <= maximum:
        raise ToolingError(f"Choose --jobs between 1 and {maximum} under the current resource budget.")
    return requested


def make_arguments(make: str, target: str, mode: str, jobs: int,
                   runtime_binaries: bool, shell: str | None) -> list[str]:
    build = f"build/portable/{target}-generic-{mode}"
    # Make recipes use a POSIX shell. Only the Python program value needs shell
    # quoting; the compiler itself travels through a literal exported variable.
    python = shlex.quote(sys.executable.replace("\\", "/")).replace("$", "$$")
    args = [make, f"-j{jobs}", f"TARGET={target}", "CPU=generic", f"MODE={mode}",
            f"BUILD={build}", f"PYTHON={python}"]
    if shell:
        args.append("SHELL=" + shell.replace("\\", "/"))
    args.append("runtime-binaries" if runtime_binaries else "all")
    return args


def probe(compiler: str, target: str, directory: Path, lock_fd: int, env: dict) -> None:
    """Compile and link, then inspect the header. Never execute a foreign probe."""
    directory.mkdir()
    object_file = directory / "probe.o"
    binary = directory / ("probe.exe" if target.startswith("windows") else "probe")
    local_env = dict(env, CXX_EXECUTABLE=compiler)
    check = [sys.executable, str(ROOT / "tools/check_toolchain.py"), "--target", target,
             "--compiler-env", "CXX_EXECUTABLE", "--flags=-std=c++2c -pthread",
             "--output", str(object_file)]
    link = [compiler, str(object_file), "-pthread", "-o", str(binary)]
    if target.startswith("windows"):
        link.append("-static")
    with (directory / "probe.log").open("w", encoding="utf-8") as log:
        previous = Path.cwd()
        try:
            os.chdir(ROOT)
            setup_command(check, env=local_env, log=log, lock_fd=lock_fd, timeout=60)
            setup_command(link, env=local_env, log=log, lock_fd=lock_fd, timeout=60)
        finally:
            os.chdir(previous)
    binary_fingerprint(binary, target)


def build(args) -> Path | None:
    host = host_identity()
    target = args.target or host["target"]
    if target not in TARGETS or host["target"] not in TARGETS:
        raise ToolingError(f"Unsupported host or target: host={host['target']}, target={target}.")
    if target == "macos-arm64" and host["target"] != "macos-arm64":
        raise ToolingError(prerequisites(target, host["target"]))
    if args.toolchain == "llvm-mingw" and not target.startswith("windows"):
        raise ToolingError("LLVM-MinGW targets Windows only; use auto/installed for Linux or macOS.")
    explicit = args.compiler or os.environ.get("CXX_EXECUTABLE")
    if explicit and args.toolchain == "llvm-mingw":
        raise ToolingError("Choose --compiler or --toolchain llvm-mingw, not both.")
    jobs = job_limit(args.jobs)
    candidates = [] if args.toolchain == "llvm-mingw" else compiler_candidates(target, host["target"], explicit)
    may_download = target.startswith("windows") and args.toolchain != "installed" and not explicit
    may_download = may_download and host["target"] in json.loads(MANIFEST.read_text())["hosts"]
    if args.plan:
        print(json.dumps({"host": host["target"], "target": target, "installed_candidates": candidates,
                          "pinned_llvm_fallback": may_download, "offline": args.offline,
                          "jobs": jobs, "build_directory": f"build/portable/{target}-generic-{args.mode}",
                          "prerequisites": prerequisites(target, host["target"]),
                          "note": "Plan only; compilers were not probed, downloaded or executed."}, indent=2))
        return None

    output = ROOT / f"build/portable/{target}-generic-{args.mode}"
    output.mkdir(parents=True, exist_ok=True)
    report_dir = ROOT / "build/portable/reports" / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    report_dir.mkdir(parents=True)
    report = {"schema": 1, "host": host, "target": target, "status": "started",
              "action": "check" if args.check else "build", "jobs": jobs, "attempts": [],
              "runtime_verified": False, "build_directory": str(output)}
    env = dict(os.environ)
    # A parent Make jobserver/variable override must not change the requested
    # target, compiler, output directory or bounded nested job count.
    for name in ("MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKELEVEL"):
        env.pop(name, None)
    bundle = None
    try:
        with setup_lock(output / "build.lock", timeout=120) as lock_fd:
            selected = None
            def try_compiler(path, origin):
                attempt_dir = report_dir / f"probe-{len(report['attempts']) + 1}"
                attempt = {"compiler": path, "origin": origin, "log": str(attempt_dir / "probe.log")}
                report["attempts"].append(attempt)
                print(f"Checking {target} compiler: {path}", flush=True)
                try:
                    probe(path, target, attempt_dir, lock_fd, env)
                    attempt["status"] = "compile-and-link-passed"
                    return path
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    attempt.update(status="failed", error=str(error))
                    return None
            for candidate in candidates:
                selected = try_compiler(candidate, "installed")
                if selected:
                    break
            if selected is None and may_download:
                print("Preparing the pinned LLVM-MinGW toolchain locally...", flush=True)
                bundle = provision_llvm(host["target"], offline=args.offline)
                prefix = PREFIXES[target][0]
                compiler = bundle / "bin" / (prefix + "-clang++" + (".exe" if os.name == "nt" else ""))
                selected = try_compiler(str(compiler), "pinned-llvm-mingw-20261020")
                report["toolchain_directory"] = str(bundle)
            if selected is None:
                raise ToolingError("No working C++26 compile/link route was found. " + prerequisites(target, host["target"]))
            report["compiler"] = selected
            if not args.check:
                make, shell = make_program(args.make, bundle)
                command = make_arguments(make, target, args.mode, jobs, args.runtime_binaries, shell)
                env["CXX_EXECUTABLE"] = selected
                if bundle and os.name == "nt":
                    env["PATH"] = os.pathsep.join([str(bundle / "busybox/bin"), str(bundle / "bin"), env.get("PATH", "")])
                report["command"] = command
                print(f"Building {target} with {jobs} job(s); log: {report_dir / 'build.log'}", flush=True)
                with (report_dir / "build.log").open("w", encoding="utf-8") as log:
                    # Make expects the checkout as cwd, regardless of where the
                    # user's shell invoked this frontend.
                    previous = Path.cwd()
                    try:
                        os.chdir(ROOT)
                        setup_command(command, env=env, log=log, lock_fd=lock_fd, timeout=900)
                    finally:
                        os.chdir(previous)
                engine = output / ("chess0live.exe" if target.startswith("windows") else "chess0live")
                report["engine"] = binary_fingerprint(engine, target)
                report["build_configuration"] = json.loads((output / "toolchain.ok").read_text())
                print(f"Built: {engine}\nBuild verified; runtime testing is a separate step.", flush=True)
            else:
                print(f"Compiler and target libraries ready for {target}; probe was not executed.", flush=True)
            report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        (report_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {report_dir / 'report.json'}", file=sys.stderr, flush=True)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=TARGETS, help="defaults to this host")
    parser.add_argument("--toolchain", choices=("auto", "installed", "llvm-mingw"), default="auto")
    parser.add_argument("--compiler", help="literal compiler executable path, without wrapper arguments")
    parser.add_argument("--make", help="GNU Make executable path")
    parser.add_argument("--mode", choices=("release", "debug"), default="release")
    parser.add_argument("--jobs", type=int, help="default: at most two, within the local resource policy")
    parser.add_argument("--offline", action="store_true", help="reuse cached archives; forbid new toolchain downloads")
    parser.add_argument("--plan", action="store_true", help="show routes without setup or compiler execution")
    parser.add_argument("--check", action="store_true", help="prepare/check compiler and target libraries without building engine")
    parser.add_argument("--runtime-binaries", action="store_true", help="also build the portable correctness executables")
    args = parser.parse_args(argv)
    if args.plan and args.check:
        parser.error("choose --plan or --check")
    build(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, ToolingError, ToolchainError, subprocess.SubprocessError) as error:
        sys.exit(f"Build setup: {error}")
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
