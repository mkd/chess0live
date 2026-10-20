#!/usr/bin/env python3
"""One fixed QSearch SEE development screen; speed is not playing strength.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

This small orchestration reuses frozen validators and summaries, never modifies
their historical protocols. The owner's editable batch script stays separate;
this tool neither imports it nor implements another puzzle benchmark framework.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
import time

from bench import digest
from profile_null_move import finish_session, publish
import profile_reverse_futility as previous
from uci_client import Engine

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/experiments/phase4d5-qsearch-see.md"
PARENT_SHA256 = "361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f"
NETWORK_SHA256 = previous.NETWORK_SHA256
DEPTH, MOVETIME_MS = 6, 500
PROFILE_BUDGET_SECONDS = 900
STAGES = ("parent_equivalence", "qsearch_work", "equal_time")
SOURCES = (*previous.SOURCES, "tools/profile_qsearch_see.py",
           "tests/profile_qsearch_see_test.py", "src/search.cpp", "src/main.cpp",
           "include/chess0live/search.hpp", "include/chess0live/search_policy.hpp")
resource_check = previous.resource_check
board_for = previous.board_for
validate_result = previous.validate_result


def options_for(role, network):
    options = previous.options_for("off", network)
    options["Reverse Futility Pruning"] = "false"
    if role != "parent":
        options["QSearch SEE Pruning"] = "true" if role == "on" else "false"
    return options


def role_order(stage, index):
    if stage == "parent_equivalence":
        roles = ("parent", "off")
    else:
        roles = ("off", "on")
    return roles if (index + (stage == "equal_time")) % 2 == 0 else roles[::-1]


def summarize_search(samples, stage):
    """Reuse pure six-root summary math with an explicit historical name map."""
    old_stage = "reverse_work" if stage == "qsearch_work" else stage
    mapped = [dict(sample, stage=old_stage) for sample in samples if sample["stage"] == stage]
    return previous.summarize(mapped, old_stage)


def profile(parent, candidate, network, output, *, quiet_host=False):
    if not quiet_host:
        raise ValueError("Use --quiet-host only after other development workloads are idle")
    positions = previous.load_positions()
    paths = {"parent": parent.resolve(), "candidate": candidate.resolve(),
             "network": network.resolve(), "protocol": PROTOCOL,
             "corpus": previous.CORPUS}
    paths.update({name: ROOT / name for name in SOURCES})
    if any("\n" in str(path) or "\r" in str(path) for path in paths.values()):
        raise ValueError("Paths must fit on one UCI command line")
    assets = {name: {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}
              for name, path in paths.items()}
    if assets["parent"]["sha256"] != PARENT_SHA256 or assets["network"]["sha256"] != NETWORK_SHA256:
        raise ValueError("Parent/network must match the predeclared pins")
    report = {"schema_version": 1, "status": "running", "assets": assets,
              "started_utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "protocol": PROTOCOL.read_text(encoding="utf-8"),
              "positions": positions, "positions_sha256": previous.POSITIONS_SHA256,
              "referee_version": "1.11.2", "quiet_host_declaration": True,
              "quiet_host_is_os_measurement": False, "initial_resource_policy": resource_check(network),
              "settings": {"depth": DEPTH, "movetime_ms": MOVETIME_MS,
                           "threads": 1, "hash_mb": 64, "repetitions": 1,
                           "searches": 60, "sessions": 36,
                           "depth_search_timeout_seconds": 60, "timed_search_timeout_seconds": 10,
                           "profile_budget_seconds": PROFILE_BUDGET_SECONDS},
              "sessions": [], "samples": [], "summaries": {},
              "interpretation": "Fixed exposed development screen, not speed qualification or playing-strength evidence."}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.with_suffix(output.suffix + ".tmp").exists():
        raise ValueError("Temporary output exists; preserve it and choose a new path")
    with output.open("x", encoding="utf-8") as target:
        target.write(json.dumps(report, indent=2) + "\n")
    started = time.monotonic()

    def remaining(maximum):
        left = min(maximum, started + PROFILE_BUDGET_SECONDS - time.monotonic())
        if left <= 0:
            raise TimeoutError("The declared stage deadline expired")
        return left

    try:
        for stage in STAGES:
            mode = "depth" if stage in ("parent_equivalence", "qsearch_work") else "movetime"
            temperatures = ("cold", "warm") if mode == "depth" else ("cold",)
            for index, position in enumerate(positions):
                board = board_for(position["position"])
                for role in role_order(stage, index):
                    remaining(1)
                    resource_check(network)
                    session = {"stage": stage, "position_index": index, "role": role, "commands": []}
                    report["sessions"].append(session)
                    engine = Engine(paths["parent"] if role == "parent" else paths["candidate"])
                    session["output"] = engine.transcript
                    try:
                        with engine:
                            def send(command):
                                session["commands"].append(command)
                                engine.send(command)
                            send("uci")
                            identity = engine.until("uciok", timeout=remaining(30))
                            if any("error:" in line.lower() for line in identity):
                                raise ValueError("Engine rejected its handshake")
                            for name, value in options_for(role, paths["network"]).items():
                                if not any(line.startswith(f"option name {name} type ") for line in identity):
                                    raise ValueError("Missing UCI option: " + name)
                                send(f"setoption name {name} value {value}")
                            send("isready")
                            if engine.until("readyok", timeout=remaining(120)) != [
                                    "info string Syzygy largest 0 pieces; table files are external", "readyok"]:
                                raise ValueError("Unexpected engine setup output")
                            for temperature in temperatures:
                                sample = {"stage": stage, "position_index": index, "role": role,
                                          "mode": mode, "temperature": temperature, "status": "preparing",
                                          "resource_policy": resource_check(network)}
                                report["samples"].append(sample)
                                if temperature == "cold":
                                    send("ucinewgame")
                                send("position " + position["position"])
                                send("isready")
                                if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                    raise ValueError("Unexpected readiness output")
                                begin, search_started = len(engine.transcript), time.monotonic()
                                sample.update(status="incomplete", started_utc=datetime.now(timezone.utc).isoformat())
                                try:
                                    send(f"go depth {DEPTH}" if mode == "depth" else f"go movetime {MOVETIME_MS}")
                                    sample["output"] = engine.until("bestmove ", timeout=remaining(60 if mode == "depth" else 10))
                                finally:
                                    sample["elapsed_seconds"] = time.monotonic() - search_started
                                    sample.setdefault("output", engine.transcript[begin:])
                                    publish(output, report)
                                sample["result"] = validate_result(sample["output"], board, mode)
                                sample["status"] = "complete"
                                publish(output, report)
                            send("isready")
                            if engine.until("readyok", timeout=remaining(30)) != ["readyok"]:
                                raise ValueError("Unexpected trailing output")
                    finally:
                        failing = sys.exc_info()[0] is not None
                        try:
                            finish_session(engine, session)
                        except ValueError:
                            if not failing:
                                raise
            report["summaries"][stage] = summarize_search(report["samples"], stage)
            publish(output, report)
        remaining(1)  # A final cleanup overrun invalidates even a complete matrix.
        report["search_and_cleanup_elapsed_seconds"] = time.monotonic() - started
        report["status"] = "complete"
    except BaseException as error:
        report.update(status="invalid_or_interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report.setdefault("search_and_cleanup_elapsed_seconds", time.monotonic() - started)
        report["after_sha256"] = {name: digest(path) if path.is_file() else None for name, path in paths.items()}
        changed = [name for name, asset in assets.items() if report["after_sha256"][name] != asset["sha256"]]
        if changed:
            report.update(status="invalid_or_interrupted", artifact_drift=changed)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        report["total_elapsed_seconds"] = time.monotonic() - started
        publish(output, report)
    if report["status"] != "complete":
        raise ValueError("Profile artifacts changed during execution")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--network", type=Path, default=ROOT / "networks/nn-1a298aa575a0.nnue")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet-host", action="store_true")
    args = parser.parse_args()
    report = profile(args.parent, args.candidate, args.network, args.output, quiet_host=args.quiet_host)
    print(json.dumps({"status": report["status"], "summaries": report["summaries"]}, indent=2))


if __name__ == "__main__":
    main()
