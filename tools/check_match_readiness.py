#!/usr/bin/env python3
"""One fixed four-worker real-match readiness screen, not strength qualification.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Reuse the existing runner's protocol clocks, persistence and cleanup. This
small supervisor only reserves aggregate resources, bounds the attempt and
rejects operational failures. Historical launchers and evidence are unchanged.
"""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time

import match
from qualify_phase3l import cancel_and_wait, cooperative_signals

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "match-readiness-20261020-v1"
PROTOCOL = "docs/experiments/match-readiness-20261020.md"
ENGINE = ROOT / "build/experiments/match-readiness-20261020/chess0live"
NETWORK = ROOT / "networks/nn-1a298aa575a0.nnue"
ENGINE_SHA = "eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9"
NETWORK_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
SUITES = tuple(ROOT / f"tests/data/match-readiness-20261020-{i:02d}.json"
               for i in range(1, 5))
SEEDS = tuple(range(20261020401, 20261020405))
TIMEOUT_SECONDS, POLL_SECONDS, MAX_POLL_GAP_SECONDS = 180, 1, 5
SETTINGS = match.Settings(3.0, .05, max_plies=1024, smoke=True)
COMMON = (("Time Policy", "classic"), ("Capture Ordering", "mvv-lva"),
          ("Countermove Ordering", "false"), ("Null Move Pruning", "false"),
          ("Reverse Futility Pruning", "false"), ("QSearch SEE Pruning", "false"),
          ("SyzygyProbeLimit", "0"))
SOURCES = (
    "tools/check_match_readiness.py", "tools/audit_match_readiness.py",
    "tests/check_match_readiness_test.py", "tests/audit_match_readiness_test.py",
    "tools/generate_readiness_openings.py",
    "tools/generate_phase4d2_openings.py",
    "tools/match.py", "tools/match_statistics.py", "tools/resources.py",
    "tools/qualify_phase3l.py", "tools/qualification.py",
    "requirements-match.txt", PROTOCOL,
    "tests/data/match-readiness-20261020-generation.json",
)


def specifications(engine=ENGINE, network=NETWORK):
    return tuple(match.EngineSpec(role, engine, network,
        source_revision="23323c6-normal-release",
        extra_options=(*COMMON, ("Late Move Reductions", enabled)))
        for role, enabled in (("candidate", "true"), ("opponent", "false")))


def admission(network):
    """Reserve all eight residents until every shard finishes cleanup."""
    policy = dict(match.current_budget())
    memory = match.physical_memory()
    per_engine = max(768 * 1024**2, 64 * 1024**2
                     + 4 * network.stat().st_size + 128 * 1024**2)
    reserved = 8 * per_engine
    policy.update(active_search_workers=4, resident_engines=8,
                  estimated_memory_bytes=reserved, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    if (policy["max_cpu_workers"] < 4 or memory is None or memory <= 0
            or reserved > memory * policy["memory_fraction"]):
        raise ValueError("Four-worker/eight-engine aggregate budget unavailable")
    return policy


def snapshot(engine, network):
    paths = [ROOT / name for name in SOURCES] + list(SUITES)
    sources = {str(path.relative_to(ROOT)): match.sha256(path) for path in paths}
    binary, weights = match.sha256(engine), match.sha256(network)
    if binary != ENGINE_SHA or weights != NETWORK_SHA:
        raise ValueError("Frozen ordinary engine or pinned network changed")
    return {"source_hashes": sources, "engine_sha256": binary, "network_sha256": weights}


def fingerprints():
    """Cheap monitoring; complete hashes are verified before and after play."""
    paths = [ENGINE, NETWORK, *(ROOT / name for name in SOURCES), *SUITES]
    return {str(path): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            for path in paths for s in (path.stat(),)}


def check_records(output, expected=None):
    """Clock forfeits stay scored in evidence but cannot pass readiness."""
    path = output / "games.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if expected is not None and len(records) != expected:
        raise ValueError("Missing or extra readiness games")
    for record in records:
        if (record["status"] != "complete" or record["termination"] == "time_forfeit"
                or record.get("unexpected_stderr")):
            raise ValueError("Readiness failed: " + record["game_id"] + " " + record["termination"])
    return records


def process_cleanup(output):
    pids = set()
    for path in output.glob("shard-*/games.jsonl"):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            pids.update(engine["pid"] for engine in record.get("engines", {}).values())
    alive, unknown = [], []
    for pid in sorted(pids):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        except PermissionError:
            unknown.append(pid)
        else:
            alive.append(pid)
    return {"engine_pids": sorted(pids), "alive_pids": alive, "unverified_pids": unknown}


async def run(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Preserve the previous attempt; output must not exist")
    initial = await asyncio.to_thread(snapshot, ENGINE, NETWORK)
    policy = await asyncio.to_thread(admission, NETWORK)
    fixed = await asyncio.to_thread(fingerprints)
    await match.disk_io(output.mkdir, parents=True)
    record = dict(initial, schema_version=1, protocol_id=PROTOCOL_ID, status="running",
        started_utc=match.utc_now(), timeout_seconds=TIMEOUT_SECONDS,
        active_search_workers=4, resident_engines=8, settings=vars(SETTINGS),
        seeds=list(SEEDS), engine=str(ENGINE), network=str(NETWORK),
        opening_manifest=[{"path": str(path), "sha256": initial["source_hashes"][str(path.relative_to(ROOT))]}
                          for path in SUITES],
        protocol=(ROOT / PROTOCOL).read_text(), initial_resource_policy=policy,
        admissions=[], resource_events=[])
    await match.disk_io(match.atomic_json, output / "launcher.json", record)
    started = time.monotonic()
    workers, monitor_task, error = [], None, None

    async def observe():
        current = await asyncio.to_thread(admission, NETWORK)
        if await asyncio.to_thread(fingerprints) != fixed:
            raise ValueError("Pinned inputs changed during readiness")
        return current

    async def monitor():
        previous = time.monotonic()
        while True:
            await asyncio.sleep(POLL_SECONDS)
            current = await observe()
            now = time.monotonic()
            event = {"checked_ns": time.monotonic_ns(), "policy": current,
                     "gap_seconds": now - previous}
            record["resource_events"].append(event)
            if now - previous > MAX_POLL_GAP_SECONDS:
                raise ValueError("Resource monitor gap exceeded five seconds")
            previous = now

    async def worker(index):
        folder = output / f"shard-{index + 1}"

        async def before_game(game_id):
            # run_match has already flushed the prior record at this boundary.
            await asyncio.to_thread(check_records, folder)
            current = await observe()
            record["admissions"].append({"shard": folder.name, "game_id": game_id,
                                         "policy": current})

        await match.run_match(specifications(), SETTINGS, SUITES[index], folder,
                              1, SEEDS[index], before_game=before_game, fail_fast=True)
        await asyncio.to_thread(check_records, folder, 2)

    try:
        workers = [asyncio.create_task(worker(i)) for i in range(4)]
        monitor_task = asyncio.create_task(monitor())
        pending = set(workers)
        while pending:
            remaining = TIMEOUT_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Readiness wall deadline reached")
            done, _ = await asyncio.wait(pending | {monitor_task}, timeout=remaining,
                                         return_when=asyncio.FIRST_COMPLETED)
            if not done:
                raise TimeoutError("Readiness wall deadline reached")
            for task in done:
                task.result()
            pending.difference_update(done)
        record["status"] = "finished"
    except BaseException as caught:
        error = caught
        record.update(status="incomplete", error=f"{type(caught).__name__}: {caught}")
    finally:
        await cancel_and_wait(workers + ([monitor_task] if monitor_task else []))
        # Ownership of the runner's cleanup/persistence is retained on failure.
        # A stuck OS write can delay cleanup; exceeding 180 s invalidates the
        # attempt rather than silently calling that wait an on-time success.
        try:
            after = await asyncio.to_thread(snapshot, ENGINE, NETWORK)
            record["source_hashes_after"] = after["source_hashes"]
            record["integrity_unchanged"] = after == initial
            record["cleanup"] = await asyncio.to_thread(process_cleanup, output)
            if after != initial:
                raise ValueError("Final input hash verification failed")
            if record["cleanup"]["alive_pids"] or record["cleanup"]["unverified_pids"]:
                raise ValueError("Engine cleanup could not be verified")
            if time.monotonic() - started > TIMEOUT_SECONDS:
                raise TimeoutError("Readiness including cleanup exceeded its deadline")
        except BaseException as caught:
            error = error or caught
            record.update(status="incomplete", finalization_error=f"{type(caught).__name__}: {caught}")
        record.update(finished_utc=match.utc_now(), elapsed_seconds=time.monotonic() - started)
        await match.disk_io(match.atomic_json, output / "launcher.json", record)
    if error:
        raise error
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    async def execute():
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        await cooperative_signals(run(args.output))
    asyncio.run(execute())


if __name__ == "__main__":
    main()
