#!/usr/bin/env python3
"""Run bounded correctness checks on an explicitly identified target runtime.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This verifies the supplied binaries, not an entire platform or release. A build
stamp describes compiler configuration; it does not prove a source revision.
VM/emulator/compatibility labels are operator declarations, never inferred from
a successful build. Compatibility-layer checks are not native Windows tests.
Runners must execute synchronously and preserve arguments and exit codes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import queue
import re
import signal
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("macos-arm64", "linux-x86_64", "linux-arm64", "linux-riscv64",
           "windows-x86_64", "windows-arm64")
EXECUTIONS = ("native", "VM", "emulator", "compatibility")
CHECKS = (
    ("position-test", "position tests passed:"),
    ("nnue-test", "PASS NNUE parser,"),
    ("nnue-updates-test", "NNUE update arithmetic:"),
    ("nnue-dense-test", "NNUE dense arithmetic:"),
    ("search-test", "Search correctness checks passed"),
    ("search-policy-test", "Selective-search policy checks passed"),
    ("time-management-test", "Time-management policy checks passed"),
)
START_MOVES = {f"{file}{rank}{file}{target}" for file in "abcdefgh"
               for rank, target in ((2, 3), (2, 4))} | {
                   "b1a3", "b1c3", "g1f3", "g1h3"}
BLACK_START_MOVES = {f"{file}7{file}{target}" for file in "abcdefgh" for target in (5, 6)} | {
    "b8a6", "b8c6", "g8f6", "g8h6"}


def fingerprint(path):
    """Stream large network files without allocating another network in RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}


def binary_identity(path, target):
    """Validate OS format and machine from bytes, independent of binfmt launchers.

    This is an identity check, not a general executable-format validator. The
    runtime checks separately establish that the loader can execute each file.
    """
    system, arch = target.split("-", 1)
    with path.open("rb") as source:
        header = source.read(64)
        if len(header) != 64:
            raise ValueError(f"executable header truncated: {path}")
        if system == "linux":
            machine = {"x86_64": 62, "arm64": 183, "riscv64": 243}[arch]
            if (header[:6] != b"\x7fELF\x02\x01"
                    or int.from_bytes(header[18:20], "little") != machine):
                raise ValueError(f"ELF64 little-endian machine does not match {target}: {path}")
            kind = "ELF64"
        elif system == "macos":
            if (header[:4] != b"\xcf\xfa\xed\xfe"
                    or int.from_bytes(header[4:8], "little") != 0x0100000C):
                raise ValueError(f"Mach-O64 ARM64 header does not match {target}: {path}")
            kind = "Mach-O64"
        else:
            offset = int.from_bytes(header[60:64], "little")
            if header[:2] != b"MZ" or offset < 64 or offset > path.stat().st_size - 26:
                raise ValueError(f"invalid PE header offset: {path}")
            source.seek(offset)
            pe = source.read(26)
            machine = {"x86_64": 0x8664, "arm64": 0xAA64}[arch]
            if (pe[:4] != b"PE\0\0" or int.from_bytes(pe[4:6], "little") != machine
                    or int.from_bytes(pe[20:22], "little") < 2
                    or pe[24:26] != b"\x0b\x02"):
                raise ValueError(f"PE32+ machine does not match {target}: {path}")
            kind = "PE32+"
    return {"format": kind, "target": target}


def binary_fingerprint(path, target):
    return {**fingerprint(path), "identity": binary_identity(path, target)}


def host_identity():
    system, machine = platform.system(), platform.machine()
    os_name = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(system)
    arch = {"aarch64": "arm64", "arm64": "arm64", "amd64": "x86_64",
            "x86_64": "x86_64", "riscv64": "riscv64"}.get(machine.lower())
    return {"system": system, "machine": machine, "release": platform.release(),
            "target": f"{os_name}-{arch}" if os_name and arch else None,
            "python": platform.python_version()}


def positive_timeout(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive and finite")
    return value


def clean_text(value):
    return isinstance(value, str) and bool(value) and not any(c in value for c in "\r\n\0")


def runner_arguments(value, execution):
    prefix = json.loads(value) if value is not None else []
    if not isinstance(prefix, list) or not all(clean_text(item) for item in prefix):
        raise ValueError("runner-json must be an array of nonempty argument strings")
    if execution in ("emulator", "compatibility") and not prefix:
        raise ValueError(f"{execution} execution requires a nonempty --runner-json argv prefix")
    if execution in ("native", "VM") and prefix:
        raise ValueError("native/VM checks must run inside that host without a runner prefix")
    return prefix


def launch(argv, **kwargs):
    """No shell: spaces and metacharacters stay inside their original arguments."""
    return subprocess.Popen(argv, start_new_session=(os.name == "posix"), **kwargs)


def terminate(process):
    """Reap failed/timed-out checks, including synchronous POSIX runner children."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        # Windows does not expose POSIX process groups. taskkill is the system
        # process-tree cleanup mechanism; retain direct-child cleanup as fallback.
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    process.wait(timeout=5)


def standalone(argv, log_path, timeout, marker, record):
    with log_path.open("w", encoding="utf-8") as log:
        process = launch(argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try:
            record["exit_code"] = process.wait(timeout=timeout)
        finally:
            terminate(process)
            record["exit_code"] = process.returncode
    output = log_path.read_text(encoding="utf-8", errors="replace")
    if record["exit_code"] != 0:
        raise RuntimeError(f"child exited {record['exit_code']}")
    if marker not in output or re.search(r"(?im)^\s*SKIP\b", output):
        raise RuntimeError("expected completion marker missing or a required check was skipped")


def search_result(lines, record):
    """Check start-position legality and accounting without optional chess modules."""
    best = lines[-1].split()
    if len(best) not in (2, 4) or best[1] not in START_MOVES:
        raise RuntimeError("search did not return a legal start-position best move")
    if len(best) == 4 and (best[2] != "ponder" or best[3] not in BLACK_START_MOVES):
        raise RuntimeError("search returned an invalid start-position ponder move")
    diagnostics = [line for line in lines if line.startswith("info string smp v1 ")]
    if len(diagnostics) != 1:
        raise RuntimeError("expected exactly one SMP diagnostic record")
    words = diagnostics[0].split()[4:]
    if len(words) % 2:
        raise RuntimeError("malformed SMP diagnostic record")
    fields = dict(zip(words[::2], words[1::2]))
    nodes = [int(value) for value in fields["worker_nodes"].split(",")]
    depths = [int(value) for value in fields["worker_depths"].split(",")]
    if (int(fields["threads"]) != 2 or len(nodes) != 2 or len(depths) != 2
            or any(value < 0 for value in nodes + depths)
            or sum(nodes) != int(fields["total_nodes"])
            or nodes[0] != int(fields["leader_nodes"])):
        raise RuntimeError("two-worker diagnostic accounting failed")
    record.setdefault("searches", []).append({"bestmove": best[1], "worker_nodes": nodes,
                                              "worker_depths": depths})


def uci_session(argv, log_path, timeout, network, record):
    """One bounded session exercises loading, perft, search, ready, stop and quit."""
    deadline = time.monotonic() + timeout
    messages = queue.Queue()
    with log_path.open("w", encoding="utf-8") as log:
        process = launch(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)

        def read():
            try:
                for line in process.stdout:
                    messages.put(line.rstrip("\r\n"))
            finally:
                messages.put(None)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()

        def send(command):
            log.write("> " + command + "\n")
            log.flush()
            process.stdin.write(command + "\n")
            process.stdin.flush()

        def until(prefix):
            lines = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"UCI timeout waiting for {prefix}")
                try:
                    line = messages.get(timeout=remaining)
                except queue.Empty as error:
                    raise TimeoutError(f"UCI timeout waiting for {prefix}") from error
                if line is None:
                    raise RuntimeError(f"UCI child exited before {prefix}")
                log.write("< " + line + "\n")
                log.flush()
                lines.append(line)
                if line.startswith("info string error:"):
                    raise RuntimeError(line)
                if line.startswith(prefix):
                    return lines

        try:
            send("uci")
            handshake = until("uciok")
            for name in ("Threads", "Hash", "EvalFile", "Search Diagnostics"):
                if not any(line.startswith(f"option name {name} type ") for line in handshake):
                    raise RuntimeError(f"UCI option missing: {name}")
            send("setoption name EvalFile value " + str(network))
            send("setoption name Threads value 2")
            send("setoption name Hash value 16")
            send("setoption name Search Diagnostics value true")
            send("isready")
            until("readyok")
            send("ucinewgame")
            send("position startpos")
            send("perft 3")
            if until("nodes ")[-1].split()[1] != "8902":
                raise RuntimeError("start-position perft(3) mismatch")
            send("go depth 3")
            result = until("bestmove ")
            if not any(line.startswith("info depth 3 ") for line in result):
                raise RuntimeError("depth-3 search did not complete")
            search_result(result, record)
            send("go infinite")
            active = until("info depth 3 ")
            send("isready")
            active += until("readyok")
            if any(line.startswith("bestmove ") for line in active):
                raise RuntimeError("infinite search ended before stop")
            send("stop")
            active += until("bestmove ")
            search_result(active, record)
            if not any(all(nodes > 0 for nodes in search["worker_nodes"])
                       for search in record["searches"]):
                raise RuntimeError("no search recorded actual activity from both workers")
            send("isready")
            if until("readyok") != ["readyok"]:
                raise RuntimeError("unexpected output after stopped search")
            send("quit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("UCI session exhausted its deadline before quit")
            record["exit_code"] = process.wait(timeout=remaining)
            if record["exit_code"] != 0:
                raise RuntimeError(f"UCI child exited {record['exit_code']}")
        finally:
            terminate(process)
            record["exit_code"] = process.returncode
            reader.join(timeout=5)
            process.stdin.close()
            process.stdout.close()
            if reader.is_alive():
                raise RuntimeError("UCI output reader did not terminate")


def verify(args):
    """Write failure evidence even when preflight rejects the supplied artifacts."""
    build, network = Path(args.build).resolve(), Path(args.network).resolve()
    output = Path(args.output).resolve() if args.output else build / (
        "runtime-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "report.json"
    report = {"schema": "chess0live.runtime.v1", "status": "failed", "target": args.target,
              "declared_execution": args.execution, "host": host_identity(),
              "started_utc": datetime.now(timezone.utc).isoformat(), "build": str(build),
              "timeout_seconds": args.timeout, "checks": [],
              "scope": "Only the recorded checks and supplied binaries; not release certification, "
                       "playing strength, or native performance. Compiler stamp is configuration "
                       "evidence, not proof of the binaries' source revision."}

    def save():
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(report_path)

    try:
        save()
        if args.target not in TARGETS or args.execution not in EXECUTIONS:
            raise ValueError("unsupported target or execution mode")
        positive_timeout(args.timeout)
        if args.execution == "compatibility" and not args.target.startswith("windows-"):
            raise ValueError("compatibility execution currently supports Windows targets only")
        if args.execution in ("native", "VM") and report["host"]["target"] != args.target:
            raise ValueError("native/VM target does not match this host OS and architecture")
        prefix = runner_arguments(args.runner_json, args.execution)
        if not all(clean_text(str(path)) for path in (build, network)):
            raise ValueError("paths must not contain newline or NUL characters")
        report["runner_argv"] = prefix
        stamp_path = build / "toolchain.ok"
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        if (stamp.get("target") != args.target or not isinstance(stamp.get("compiler"), list)
                or not stamp["compiler"] or not all(clean_text(item) for item in stamp["compiler"])
                or not isinstance(stamp.get("flags"), list)
                or not all(isinstance(item, str) for item in stamp["flags"])
                or not isinstance(stamp.get("link_flags"), str)):
            raise ValueError("toolchain stamp target or compiler/flag metadata is invalid")
        report["toolchain"] = {"configuration": stamp, **fingerprint(stamp_path)}
        manifest_path = ROOT / "networks" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["network_manifest"] = {"configuration": manifest, **fingerprint(manifest_path)}
        report["network"] = fingerprint(network)
        if (report["network"]["sha256"] != manifest["sha256"]
                or report["network"]["size_bytes"] != manifest["size_bytes"]):
            raise ValueError("network does not match the pinned manifest SHA-256 and size")
        suffix = ".exe" if args.target.startswith("windows-") else ""
        paths = {name: build / (name + suffix) for name, _ in CHECKS}
        paths["uci"] = build / ("chess0live" + suffix)
        report["binaries"] = {name: binary_fingerprint(path, args.target) for name, path in paths.items()}
        for name, marker in (*CHECKS, ("uci", None)):
            argv = prefix + [str(paths[name])]
            if name == "nnue-test":
                argv += ["--network", str(network)]
            elif name == "search-test":
                argv.append(str(network))
            record = {"name": name, "status": "failed", "argv": argv,
                      "output_log": str(output / (name + ".log")), "exit_code": None}
            report["checks"].append(record)
            save()
            started = time.monotonic()
            try:
                if name == "uci":
                    uci_session(argv, Path(record["output_log"]), args.timeout, network, record)
                else:
                    standalone(argv, Path(record["output_log"]), args.timeout, marker, record)
                record["status"] = "passed"
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                record["elapsed_seconds"] = time.monotonic() - started
                save()
        # Catch overwritten artifacts instead of attributing mixed-build checks
        # to the initial fingerprints. This is not a claim of atomic snapshots.
        for name, path in paths.items():
            if binary_fingerprint(path, args.target) != report["binaries"][name]:
                raise RuntimeError(f"binary changed during checks: {name}")
        if fingerprint(network) != report["network"]:
            raise RuntimeError("network changed during checks")
        for key, path in (("toolchain", stamp_path), ("network_manifest", manifest_path)):
            if fingerprint(path)["sha256"] != report[key]["sha256"]:
                raise RuntimeError(f"{key} changed during checks")
        report["status"] = "passed"
    except (Exception, KeyboardInterrupt) as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    print(f"Runtime checks {report['status']}: {report_path}")
    return 0 if report["status"] == "passed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, help="directory containing engine, seven tests and toolchain.ok")
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--network", required=True)
    parser.add_argument("--execution", choices=EXECUTIONS, required=True)
    parser.add_argument("--runner-json", help="emulator/compatibility argv prefix as a JSON array; never a shell command")
    parser.add_argument("--output", help="new evidence directory; must not already exist")
    parser.add_argument("--timeout", type=positive_timeout, default=180.0,
                        help="maximum seconds per standalone check / entire UCI session (default: 180)")
    args = parser.parse_args(argv)
    try:
        return verify(args)
    except OSError as error:
        parser.exit(1, f"Cannot create/write runtime evidence: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
