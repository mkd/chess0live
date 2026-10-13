#!/usr/bin/env python3
"""Resource-window boundaries and overrides, without changing user settings.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from resources import budget

for hour, minute, percent in [(22, 59, 50), (23, 0, 80), (6, 59, 80), (7, 0, 50)]:
    result = budget(datetime(2026, 10, 13, hour, minute, tzinfo=ZoneInfo("Europe/Helsinki")), cpus=18)
    assert result["percent"] == percent
    assert result["max_cpu_workers"] == (9 if percent == 50 else 14)
assert budget(override=25, cpus=18)["max_cpu_workers"] == 4
assert budget(override=100, cpus=18)["max_cpu_workers"] == 18
for invalid in (0, 101, -1, True, "50"):
    try:
        budget(override=invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid resource override: {invalid}")
print("resource policy tests passed")
