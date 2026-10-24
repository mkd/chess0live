#!/usr/bin/env python3
"""Invoke one literal compiler path without interpolating it into a shell.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import os
import subprocess
import sys


def compiler_from_environment(name="CXX_EXECUTABLE"):
    """Keep argv[0] intact: target-prefixed clang aliases may select the target."""
    executable = os.environ.get(name)
    if not executable:
        raise ValueError(f"{name} must contain one compiler executable path.")
    return [executable]


def main():
    command = compiler_from_environment() + sys.argv[1:]
    if os.name != "nt":
        # Preserve the compiler PID/signal behavior when Make cancels a job.
        os.execvp(command[0], command)
    status = subprocess.call(command)
    return 128 - status if status < 0 else status


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(f"Compiler invocation failed: {error}")
