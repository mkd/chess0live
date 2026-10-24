#!/usr/bin/env python3
"""Run a Python tool/test with automatic isolated dependencies.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import argparse
import sys

from tooling import ToolingError, ensure_environment, run_script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="use only the environment and cached archives")
    parser.add_argument("--setup", action="store_true", help="prepare the environment and print its Python path")
    parser.add_argument("script", nargs="?", help="tool or test .py path")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed unchanged to the script")
    options = parser.parse_args()
    if options.setup:
        if options.script:
            parser.error("--setup does not take a script")
        print(ensure_environment(offline=options.offline))
        return 0
    if not options.script:
        parser.error("provide a tool/test script, or --setup")
    return run_script(options.script, options.args, offline=options.offline, replace_process=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ToolingError, OSError) as error:
        sys.exit(f"Tool setup: {error}")
    except KeyboardInterrupt:
        sys.exit("\nStopped.")
