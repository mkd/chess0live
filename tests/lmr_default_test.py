#!/usr/bin/env python3
"""Bounded real-engine equivalence check for the qualified LMR default change.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Compare the pinned parent and rebuilt candidate on exposed development roots,
never qualification openings. One process and one search worker run at a time.
This verifies default integration and reversible option/cache boundaries, not
new strength evidence. The existing profiler validates legal PVs and diagnostic
accounting; its signature excludes elapsed time, NPS and hash occupancy.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from bench import digest
from profile_lmr import board_for, validate_result
from profile_search import positions_from, reject_errors, resource_check
from uci_client import Engine

PARENT_SHA256 = "eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
OPTION = "Late Move Reductions"
HASH_MB = 64
MAX_SECONDS = 180
INPUTS = ("tests/data/openings-development.json", "tests/data/performance-gamephases.json")
HELPERS = ("tools/uci_client.py", "tools/profile_lmr.py", "tools/profile_search.py",
           "tools/compare_bench.py", "tools/bench.py", "tools/resources.py")


def cases():
    """Use a small fixed mix of already exposed, independently authored roots."""
    available = {entry["id"]: entry for name in INPUTS
                 for entry in positions_from(json.loads((ROOT / name).read_text()), 0)}
    selected = (("development-01", 5), ("gamephases-mg-02", 5),
                ("gamephases-mg-03", 5), ("gamephases-eg-02", 6))
    return [dict(available[name], depth=depth) for name, depth in selected]


def remaining(deadline, maximum=30):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise TimeoutError("LMR default regression exceeded its 180-second budget")
    return min(maximum, seconds)


def ready(engine, deadline):
    engine.send("isready")
    lines = engine.until("readyok", timeout=remaining(deadline))
    reject_errors(lines)
    if lines != ["readyok"]:
        raise ValueError("Unexpected readiness output: " + repr(lines))


def configure(engine, network, advertised_default, override, deadline):
    engine.send("uci")
    identity = engine.until("uciok", timeout=remaining(deadline))
    reject_errors(identity)
    expected = f"option name {OPTION} type check default {str(advertised_default).lower()}"
    if expected not in identity:
        raise ValueError("Wrong advertised LMR default: " + expected)
    for name in ("Countermove Ordering", "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning"):
        if f"option name {name} type check default false" not in identity:
            raise ValueError("Unrelated experimental default changed: " + name)
    for name, value in (("Hash", HASH_MB), ("Threads", 1), ("EvalFile", network),
                        ("Ponder", "false"), ("Search Diagnostics", "true"),
                        ("Time Policy", "classic"), ("Capture Ordering", "mvv-lva"),
                        ("Countermove Ordering", "false"), ("Null Move Pruning", "false"),
                        ("Reverse Futility Pruning", "false"), ("QSearch SEE Pruning", "false"),
                        ("SyzygyProbeLimit", 0)):
        engine.send(f"setoption name {name} value {value}")
    if override is not None:
        engine.send(f"setoption name {OPTION} value {str(override).lower()}")
    ready(engine, deadline)
    return identity


def search(engine, case, enabled, network, deadline, *, clear=True):
    policy = resource_check(network, HASH_MB)
    if clear:
        engine.send("ucinewgame")
    engine.send("position " + case["position"])
    ready(engine, deadline)
    engine.send(f"go depth {case['depth']}")
    lines = engine.until("bestmove ", timeout=remaining(deadline))
    result = validate_result(lines, enabled, board_for(case["position"]),
                             case["depth"], None, ordering_required=True)
    caches = [line for line in lines if line.startswith("info string cache v1 ")]
    if len(caches) != 1:
        raise ValueError("Missing cache diagnostics")
    values = caches[0].split()[4:]
    cache = {key: int(value) for key, value in zip(values[::2], values[1::2])}
    if len(cache) * 2 != len(values) or not 0 <= cache["cutoffs"] <= cache["hits"] <= cache["probes"]:
        raise ValueError("Malformed cache diagnostics")
    forbidden = ("info string nullmove ", "info string reversefutility ",
                 "info string qsearchsee ", "info string countermove ", "info string smp ")
    if any(line.startswith(forbidden) for line in lines):
        raise ValueError("An unrelated search experiment or SMP became active")
    # All values here are deterministic work/state, with timing deliberately
    # absent. Exact cache equality also detects stale cross-policy TT/history.
    stable = {"signature": result["signature"], "lmr": result["lmr"],
              "ordering": result["ordering"], "cache": cache,
              "stop_reason": result["trace"]["summary"]["stop_reason"]}
    return {"case": case["id"], "enabled": enabled, "cleared": clear,
            "resource_policy": policy, "stable": stable, "output": lines}


def run(parent, candidate, network):
    if digest(parent) != PARENT_SHA256 or digest(network) != NETWORK_SHA256:
        raise ValueError("Parent executable or network differs from the qualified pins")
    paths = {"parent": parent, "candidate": candidate, "network": network,
             **{name: ROOT / name for name in (*INPUTS, *HELPERS, "tests/lmr_default_test.py")}}
    before = {name: digest(path) for name, path in paths.items()}
    selected = cases()
    for case in selected:
        board_for(case["position"])
    report = {"status": "running", "settings": {"threads": 1, "hash_mb": HASH_MB,
              "max_seconds": MAX_SECONDS}, "assets": {name: {"path": str(paths[name]), "sha256": sha}
              for name, sha in before.items()}, "cases": selected, "modes": {}, "cache_transitions": []}
    deadline = time.monotonic() + MAX_SECONDS
    modes = (("parent-default-off", parent, False, None),
             ("parent-explicit-on", parent, False, True),
             ("candidate-default-on", candidate, True, None),
             ("candidate-explicit-on", candidate, True, True),
             ("candidate-explicit-off", candidate, True, False))
    for label, binary, default, override in modes:
        resource_check(network, HASH_MB)
        with Engine(binary) as engine:
            identity = configure(engine, network, default, override, deadline)
            enabled = default if override is None else override
            samples = [search(engine, case, enabled, network, deadline) for case in selected]
            report["modes"][label] = {"identity": identity, "samples": samples}
            if label == "candidate-default-on":
                # Start cold, then let only actual option changes invalidate
                # cached bounds and learned history. No newgame/Clear Hash
                # occurs between on -> off -> on searches.
                report["cache_transitions"].append(search(engine, selected[0], True, network, deadline))
                for enabled in (False, True):
                    engine.send(f"setoption name {OPTION} value {str(enabled).lower()}")
                    report["cache_transitions"].append(
                        search(engine, selected[0], enabled, network, deadline, clear=False))
        if engine.process.returncode != 0:
            raise ValueError(f"{label} did not exit cleanly")

    def signatures(label):
        return [sample["stable"] for sample in report["modes"][label]["samples"]]

    for first, second in (("candidate-default-on", "parent-explicit-on"),
                          ("candidate-explicit-on", "candidate-default-on"),
                          ("candidate-explicit-off", "parent-default-off")):
        if signatures(first) != signatures(second):
            raise ValueError(f"Default integration parity failed: {first} versus {second}")
    on = signatures("candidate-default-on")
    if not any(sample["lmr"]["reductions"] > 0 for sample in on):
        raise ValueError("The selected development roots did not activate LMR")
    for sample in report["cache_transitions"]:
        reference = on[0] if sample["enabled"] else signatures("candidate-explicit-off")[0]
        if sample["stable"] != reference or sample["stable"]["cache"]["stores"] <= 0:
            raise ValueError("Changing the LMR option failed to restore cold-policy equivalence")
    after = {name: digest(path) for name, path in paths.items()}
    if after != before:
        raise ValueError("Regression inputs changed during execution")
    report.update(status="passed", searches=23, comparisons=15, after_sha256=after,
                  total_default_on_reductions=sum(sample["lmr"]["reductions"] for sample in on),
                  note="Fixed-depth default/cache integration parity only; no new strength or SMP claim.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    args = parser.parse_args()
    report = run(args.parent.resolve(), args.candidate.resolve(), args.network.resolve())
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
