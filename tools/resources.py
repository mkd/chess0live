#!/usr/bin/env python3
"""Read and override the local experiment scheduling budget.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This is a workload-sizing policy, not an operating-system CPU utilization cap.
Runners should re-read it between work units. Running games must not be paused
mid-clock merely to adjust a scheduling budget.
"""
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = ROOT / ".local" / "resource-policy.json"


def budget(now=None, override=None, cpus=None):
    """Return the Helsinki time-window budget and aggregate worker allowance."""
    now = (now or datetime.now(ZoneInfo("Europe/Helsinki"))).astimezone(ZoneInfo("Europe/Helsinki"))
    nighttime = now.hour >= 23 or now.hour < 7
    percent = 80 if nighttime else 50
    source = "nighttime" if nighttime else "daytime"
    if override is not None:
        if not isinstance(override, int) or isinstance(override, bool) or not 1 <= override <= 100:
            raise ValueError("override must be an integer from 1 to 100")
        percent, source = override, "manual"
    cpus = cpus or os.cpu_count() or 1
    return {"timezone": "Europe/Helsinki", "local_time": now.isoformat(),
            "source": source, "percent": percent, "logical_cpus": cpus,
            "max_cpu_workers": max(1, math.floor(cpus * percent / 100)),
            "memory_fraction": percent / 100,
            "note": "Worker count approximates CPU usage; this is not a hard OS utilization cap."}


def current_budget():
    override = None
    if OVERRIDE.exists():
        override = json.loads(OVERRIDE.read_text())["percent"]
    return budget(override=override)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("show", "set", "clear"))
    parser.add_argument("percent", type=int, nargs="?")
    args = parser.parse_args()
    if args.action == "set":
        if args.percent is None:
            parser.error("set requires a percentage")
        budget(override=args.percent)  # Validate before changing local state.
        OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        temporary = OVERRIDE.with_suffix(".tmp")
        temporary.write_text(json.dumps({"percent": args.percent}) + "\n")
        temporary.replace(OVERRIDE)
    elif args.action == "clear":
        OVERRIDE.unlink(missing_ok=True)
    elif args.percent is not None:
        parser.error("show does not accept a percentage")
    print(json.dumps(current_budget(), indent=2))


if __name__ == "__main__":
    main()
