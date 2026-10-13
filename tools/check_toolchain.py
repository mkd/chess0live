#!/usr/bin/env python3
"""Check actual compiler target and required C++26-mode library facilities.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

TARGET_CHECKS = {
    "macos-arm64": "defined(__APPLE__) && defined(__aarch64__)",
    "linux-arm64": "defined(__linux__) && defined(__aarch64__)",
    "linux-x86_64": "defined(__linux__) && defined(__x86_64__)",
    "linux-riscv64": "defined(__linux__) && defined(__riscv) && __riscv_xlen == 64",
    "windows-x86_64": "defined(_WIN32) && (defined(__x86_64__) || defined(_M_X64))",
    "windows-arm64": "defined(_WIN32) && (defined(__aarch64__) || defined(_M_ARM64))",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=TARGET_CHECKS, required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--flags", default="-std=c++2c")
    parser.add_argument("--output", required=True)
    parser.add_argument("--stamp")
    parser.add_argument("--link-flags", default="")
    args = parser.parse_args()
    compiler = shlex.split(args.compiler)
    flags = shlex.split(args.flags)
    resolved = shutil.which(compiler[0])
    if not resolved:
        raise OSError(f"Compiler not found: {compiler[0]}")
    metadata = Path(resolved).stat()
    signature = json.dumps({"target": args.target, "compiler": compiler,
        "compiler_path": str(Path(resolved).resolve()), "compiler_mtime": metadata.st_mtime_ns,
        "compiler_size": metadata.st_size, "flags": flags, "link_flags": args.link_flags,
        "script_mtime": Path(__file__).stat().st_mtime_ns,
        "makefile_mtime": Path("Makefile").stat().st_mtime_ns,
        "environment": {name: os.environ.get(name) for name in
            ("CPATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "SDKROOT", "MACOSX_DEPLOYMENT_TARGET")}},
        sort_keys=True, indent=2) + "\n"
    stamp = Path(args.stamp) if args.stamp else None
    if stamp and stamp.exists() and stamp.read_text() == signature and Path(args.output).exists():
        return
    source = """#include <bit>
#include <cstdint>
#include <filesystem>
#include <thread>
#include <atomic>
#include <charconv>
#if __cplusplus <= 202302L
#error C++26 compilation mode is required
#endif
#if !(TARGET_CHECK)
#error Compiler target does not match the requested TARGET
#endif
static_assert(sizeof(void*) == 8);
static_assert(std::popcount(std::uint64_t{7}) == 3);
std::atomic<bool> flag{false};
int main() { std::filesystem::path p{"."}; std::jthread t([]{}); return p.empty(); }
""".replace("TARGET_CHECK", TARGET_CHECKS[args.target])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(compiler + ["--version"], check=True)
    subprocess.run(compiler + flags + ["-x", "c++", "-c", "-", "-o", args.output], input=source, text=True, check=True)
    if stamp:
        stamp.write_text(signature)
    print(f"Compile probe passed for {args.target}; linking and execution still require separate checks.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Toolchain check failed: {error}", file=sys.stderr)
        sys.exit(1)
