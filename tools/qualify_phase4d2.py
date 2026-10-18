#!/usr/bin/env python3
"""Run the fixed current-engine LMR qualification once, within one night.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The existing QualificationProfile/run implementation owns every game's clocks,
process cleanup, raw evidence and child manifests. This facade adds only the
aggregate resource/deadline supervisor. Frozen Phase 3L sources remain unchanged.
No scheduling, resume, sample overrides or inherited daytime exceptions.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import io
import json
from pathlib import Path
import sys
import time

import match
import qualification as shared
from qualify_phase3l import cooperative_signals, cancel_and_wait, append_resource_event

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase4d2-lmr-1024-v1"
PROTOCOL_DOCUMENT = "docs/PHASE_4D2.md"
CHESS_VERSION = "1.11.2"
SHARDS, SHARD_PAIRS, PAIRS = 8, 64, 512
SEEDS = tuple(range(202610184201, 202610184209))
POLL_SECONDS, MAX_RESOURCE_GAP_SECONDS = 1.0, 5.0
SUITE_HASHES = (
    '0c8b1eb8979a6e08e700b7ab6bba7cf4ac0595ad3856e0fd157a68df15aba146',
    '43444b4015df6f83764f901426bc6aa88279f5b65b8a863478623be2b898db11',
    '8f2996d663c6178e451e69771a26addb4d52d5cd79becd8467c5e202aec5c234',
    'a3c497666b171cd570ba2f067f0476c6105ea1806e4bb93152fea65252be0101',
    'dbbbc5fcb13a97acb01dac5eb4d065d13db498374da8886bd3dd21f4757925db',
    '52290546a8248a353cac165b5ddecc448ccf42c422b009ac1ef03608deb3cf9d',
    '981b8639a905684a4f87671f0057d1bb8c1c98d77f2c6aea6eec29bf022b07e2',
    '73602f5c204329fbf5c57ca2b90914c4bb9ad834052a1850a0cd879d16d8a5b5',
)
EXCLUSIONS = "tests/data/phase4d2-exclusions.json"
GENERATION = "tests/data/phase4d2-generation.json"
GENERATOR = "tools/generate_phase4d2_openings.py"
BUILD_MANIFEST = "build/experiments/phase4d2-20261018/manifest.json"
INPUT_PINS = {
    EXCLUSIONS: "94d17056e1b86ebeb4c8e9801c551df9edd8ee8a33cec4ac74a1db39a8de50ee",
    GENERATION: "dae2e9dc2cfbe69b21fd4475caf7c9272bf9cbb038ee26e33e8749859680f367",
    GENERATOR: "63c2feaec89182626316b1294ed33b58aa78d1b33e0dc32ce66cef8f8e29f7e2",
    BUILD_MANIFEST: "918298becbfbcd62148759ea050726bd29070dbad9db66cc22bb8fc91965918c",
}
FROZEN = {
    "engine": (ROOT / "build/experiments/phase4d2-20261018/chess0live", "bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f"),
    "network": (ROOT / "networks/nn-1a298aa575a0.nnue", "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"),
    **{f"openings_{i}": (ROOT / f"tests/data/phase4d2-lmr-{i:02d}.json", digest)
       for i, digest in enumerate(SUITE_HASHES, 1)},
}
SOURCES = ("tools/qualify_phase4d2.py", "tools/audit_phase4d2.py", GENERATOR,
           "tests/phase4d2_openings_test.py", "tests/qualify_phase4d2_test.py", "tests/audit_phase4d2_test.py",
           "tools/qualify_phase3l.py", "tools/audit_phase3l.py", "tools/qualification.py", "tools/match.py",
           "tools/audit_time_policy.py", "tools/match_statistics.py", "tools/resources.py",
           "requirements-match.txt", PROTOCOL_DOCUMENT, EXCLUSIONS, GENERATION, BUILD_MANIFEST)
COMMON_OPTIONS = (("Time Policy", "classic"), ("Capture Ordering", "mvv-lva"),
                  ("Countermove Ordering", "false"), ("SyzygyProbeLimit", "0"))
ROLE_OPTIONS = tuple((*COMMON_OPTIONS, ("Late Move Reductions", enabled)) for enabled in ("true", "false"))
REVISIONS = tuple(f"phase4d2-lmr-{mode}-74a908bb861e8292cdbb10d005410e4364efea5e" for mode in ("on", "off"))
utc_now = shared.utc_now


def profile(index):
    if type(index) is not int or not 1 <= index <= SHARDS:
        raise ValueError(f"Shard index must be 1 through {SHARDS}")
    frozen = {"engine": FROZEN["engine"], "network": FROZEN["network"], "openings": FROZEN[f"openings_{index}"]}
    return shared.QualificationProfile(ROOT, f"{PROTOCOL_ID}-shard-{index}", CHESS_VERSION,
        SHARD_PAIRS, SEEDS[index-1], frozen, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS,
        REVISIONS, ("Late Move Reductions", "Countermove Ordering"))


def fixed_request():
    return shared.fixed_request(profile(1))


def configuration():
    specs, settings = fixed_request()
    common = shared.configuration(profile(1), specs, settings)
    return {"settings": common["settings"], "pairs": PAIRS, "games": 2*PAIRS,
            "shards": SHARDS, "shard_pairs": SHARD_PAIRS, "active_search_workers": SHARDS,
            "resident_engines": 2*SHARDS, "resource_poll_seconds": POLL_SECONDS,
            "max_resource_gap_seconds": MAX_RESOURCE_GAP_SECONDS, "seeds": list(SEEDS),
            "engines": common["engines"], "ponder": False, "diagnostics": False}


def snapshot():
    for name, expected in INPUT_PINS.items():
        if match.sha256(ROOT/name) != expected:
            raise ValueError(f"Frozen input SHA-256 mismatch: {name}")
    return shared.snapshot(shared.QualificationProfile(ROOT, PROTOCOL_ID, CHESS_VERSION, PAIRS, 0,
        FROZEN, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS, REVISIONS))


def fingerprints():
    paths = {path.resolve() for path, _ in FROZEN.values()} | {(ROOT/name).resolve() for name in SOURCES}
    return {str(path): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            for path in paths for s in (path.stat(),)}


def launch_policy(now=None, *, require_window=False):
    policy = shared.launch_policy(now or utc_now(), allow_daytime=False)
    local = datetime.fromisoformat(policy["local_time"])
    permitted = local.hour == 23 and local.minute < 30
    window = "23:00–23:30 Europe/Helsinki"
    if require_window and not permitted:
        raise ValueError(f"Phase 4D.2 may launch only {window} (end exclusive)")
    policy.update(launch_window=window, launch_permitted=permitted, daytime_authorization=None)
    return policy


def opening_check():
    """Referee-only replay: all original histories, unique roots, no exposure overlap."""
    from audit_phase3l import definitions, root_key
    roots, ids = set(), set()
    for index in range(1, SHARDS+1):
        document = json.loads(FROZEN[f"openings_{index}"][0].read_text())
        entries, keys = definitions(document, full_history=True)
        identifiers = {entry["opening_id"] for entry in entries}
        if len(entries) != SHARD_PAIRS or roots & keys or ids & identifiers:
            raise ValueError("Wrong opening count or duplicate global opening root/identifier")
        roots.update(keys); ids.update(identifiers)
    previous = json.loads((ROOT/EXCLUSIONS).read_text())["roots"]
    excluded = {entry["root_key"] for entry in previous}
    if not excluded or len(excluded) != len(previous):
        raise ValueError("Exclusions must contain distinct canonical roots")
    for key in excluded:
        board = match.chess.Board(key + " 0 1")
        if not board.is_valid() or root_key(board) != key:
            raise ValueError("Malformed exclusion root")
    if roots & excluded:
        raise ValueError("New openings overlap previous exposure")
    return {"opening_count": PAIRS, "distinct_roots": len(roots), "previous_root_count": len(excluded)}


def resource_policy():
    """Reserve every shard through cleanup, including already completed shards."""
    specs, settings = fixed_request()
    policy = dict(match.current_budget())
    per_shard = 2*settings.hash_mb*1024**2 + 4*sum(spec.network.stat().st_size for spec in specs) + 256*1024**2
    memory = match.physical_memory()
    policy.update(active_search_workers=SHARDS, resident_engines=2*SHARDS,
                  estimated_memory_bytes=SHARDS*per_shard, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    return policy, (SHARDS <= policy["max_cpu_workers"] and memory is not None and memory > 0
                    and SHARDS*per_shard <= memory*policy["memory_fraction"])


def validate_options(protocol, configured, spec, settings):
    # The historical shared validator handles check/combo values only. Remove
    # the single spin from its immutable request, then validate its parsed int.
    ordinary = replace(spec, extra_options=tuple((n, v) for n, v in spec.extra_options if n != "SyzygyProbeLimit"))
    shared.validate_options(profile(1), protocol, configured, ordinary, settings)
    ordering = protocol.options.get("Capture Ordering")
    if ordering is None or ordering.type != "combo" or ordering.default != "mvv-lva" or set(ordering.var or ()) != {"mvv-lva", "see"}:
        raise ValueError("Capture Ordering choices/default changed")
    limit, path = protocol.options.get("SyzygyProbeLimit"), protocol.options.get("SyzygyPath")
    if limit is None or limit.type != "spin" or limit.min != 0 or limit.max != 7 or configured.get("SyzygyProbeLimit") != 0:
        raise ValueError("SyzygyProbeLimit must support and apply disabled value 0")
    if path is None or path.type != "string" or path.default != "<empty>" or configured.get("SyzygyPath") != "":
        raise ValueError("SyzygyPath must default and remain empty")


async def check():
    if match.chess.__version__ != CHESS_VERSION:
        raise ValueError(f"Qualification requires chess=={CHESS_VERSION}")
    initial, details = snapshot(), opening_check()
    budget, allowed = resource_policy()
    if not allowed:
        raise ValueError("Aggregate eight-worker/sixteen-engine resource budget is insufficient")
    specs, settings = fixed_request(); settings.validate()
    engines = []
    for spec in specs:
        log = io.StringIO()
        transport, protocol, configured = await match.start_engine(spec, settings, log)
        try:
            validate_options(protocol, configured, spec, settings)
            engines.append({"role": spec.role, "id": dict(protocol.id), "configured": configured,
                            "options": {name: vars(option).copy() for name, option in protocol.options.items()}})
        finally:
            await match.close_engine(transport, protocol)
        engines[-1]["transcript"] = [json.loads(line) for line in log.getvalue().splitlines()]
    if snapshot() != initial:
        raise ValueError("Frozen inputs or sources changed during preflight")
    config = configuration()
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "status": "checked", "checked_utc": utc_now().isoformat(),
            "configuration": config, "configuration_sha256": shared.configuration_hash(config),
            "frozen": initial["assets"], "sources": initial["sources"], "artifacts_before": initial,
            "launch_policy": launch_policy(), "preflight": {**details, "engines": engines, "resource_policy": budget}}


def child_report(master, index):
    specs, settings = fixed_request(); config = shared.configuration(profile(index), specs, settings)
    assets = master["frozen"]
    return {"schema_version": 1, "protocol_id": profile(index).protocol_id, "status": "checked",
            "checked_utc": master["checked_utc"], "configuration": config,
            "configuration_sha256": shared.configuration_hash(config), "chess_version": CHESS_VERSION,
            "assets": {"engine": assets["engine"], "network": assets["network"], "openings": assets[f"openings_{index}"]},
            "sources": master["sources"], "preflight": {"opening_count": SHARD_PAIRS, "distinct_roots": SHARD_PAIRS,
                "engines": deepcopy(master["preflight"]["engines"]), "resource_policy": master["preflight"]["resource_policy"]}}


async def run(output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Campaign output must be a new directory; overwrite/resume is disabled")
    started = utc_now()
    policy = launch_policy(started, require_window=True)
    cutoff = datetime.fromisoformat(policy["cutoff_utc"])
    initial = snapshot()
    metadata = fingerprints()
    config = configuration()
    output.mkdir(parents=True, exist_ok=False)
    (output / "protocol.md").write_bytes((ROOT / PROTOCOL_DOCUMENT).read_bytes())
    protocol_sha = match.sha256(output / "protocol.md")
    if protocol_sha != initial["sources"][PROTOCOL_DOCUMENT]["sha256"]:
        raise ValueError("Protocol changed before its frozen copy was written")
    record = {"schema_version": 1, "protocol_id": PROTOCOL_ID, "status": "running",
        "started_utc": started.isoformat(), "cutoff_utc": cutoff.isoformat(), "launch_policy": policy,
        "configuration": config, "configuration_sha256": shared.configuration_hash(config),
        "frozen": initial["assets"], "sources": initial["sources"], "artifacts_before": initial,
        "protocol": {"path": "protocol.md", "sha256": protocol_sha},
        "shards": [{"index": i, "protocol_id": profile(i).protocol_id, "seed": SEEDS[i-1],
                    "path": f"shard-{i}", "openings": initial["assets"][f"openings_{i}"]}
                   for i in range(1, SHARDS + 1)],
        "resource_history": {"path": "resource-history.jsonl", "observations": 0, "sha256": None}}
    tasks, workers = [], []
    journal_path = output / "resource-history.jsonl"
    with journal_path.open("x", encoding="utf-8") as journal:
        observations = asyncio.Lock()
        async def observe(trigger, **identity):
            # One bounded in-flight observation, with no accumulating write
            # queue. Another shard may search while this one waits for storage.
            # The lock covers both commit and count, including cancellation.
            async with observations:
                budget, allowed = await shared.disk_io(resource_policy)
                event = {"observed_utc": utc_now().isoformat(), "trigger": trigger,
                         "policy": budget, "within_limits": allowed, **identity}
                async def commit():
                    await asyncio.to_thread(append_resource_event, journal, event)
                    record["resource_history"]["observations"] += 1
                await match.finish_cleanup(commit())
                return allowed

        async def guard(game_id=None, index=None, trigger="before_game"):
            if utc_now() >= cutoff:
                raise shared.WindowExpired("Helsinki 07:00 cutoff; fixed sample incomplete")
            if await shared.disk_io(fingerprints) != metadata:
                raise ValueError("Frozen artifact or source metadata changed during campaign")
            identity = {} if index is None else {"shard_index": index, "game_id": game_id}
            if not await observe(trigger, **identity):
                raise ValueError("Aggregate eight-worker/sixteen-engine resource budget became insufficient")

        async def monitor():
            previous = time.monotonic()
            while True:
                await guard(trigger="periodic")
                await asyncio.sleep(POLL_SECONDS)
                current = time.monotonic()
                if current - previous > MAX_RESOURCE_GAP_SECONDS:
                    raise ValueError("Aggregate resource monitor exceeded the five-second observation gap")
                previous = current

        async def deadline():
            await asyncio.sleep(max(0, (cutoff - utc_now()).total_seconds()))
            raise shared.WindowExpired("Helsinki 07:00 cutoff; fixed sample incomplete")

        def child_window(**_):
            current = shared.launch_policy(utc_now(), allow_daytime=False)
            current.update(cutoff_utc=policy["cutoff_utc"], cutoff_local=policy["cutoff_local"],
                           remaining_seconds=(cutoff - utc_now()).total_seconds(),
                           daytime_authorization=policy["daytime_authorization"])
            return current

        async def worker(index):
            async def cached_preflight():
                return await shared.disk_io(child_report, record, index)
            async def before_game(game_id):
                await guard(game_id, index)
            return await shared.run(profile(index), output / f"shard-{index}", allow_daytime=False,
                preflight=cached_preflight, request=fixed_request, clock=utc_now, window=child_window,
                run_guard=before_game, fail_fast=True, manage_deadline=False)

        match.atomic_json(output / "campaign.json", record)
        try:
            if not await observe("initial"):
                raise ValueError("Aggregate eight-worker/sixteen-engine resource budget is insufficient")
            checked = await check()
            if checked["artifacts_before"] != initial or fingerprints() != metadata:
                raise ValueError("Frozen campaign inputs changed during preflight")
            record.update(checked_utc=checked["checked_utc"], preflight=checked["preflight"])
            if utc_now() >= cutoff:
                raise shared.WindowExpired("Initial Helsinki cutoff elapsed during preflight")
            match.atomic_json(output / "campaign.json", record)
            workers = [asyncio.create_task(worker(i), name=f"phase4d2-shard-{i}")
                       for i in range(1, SHARDS + 1)]
            tasks = [*workers, asyncio.create_task(monitor()), asyncio.create_task(deadline())]
            pending = set(tasks)
            while any(not task.done() for task in workers):
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            for task in workers:
                task.result()
            record["status"] = "finished"
        except asyncio.CancelledError:
            record.update(status="interrupted", error="Supervisor cancelled; fixed sample incomplete")
            raise
        except shared.WindowExpired as error:
            record.update(status="interrupted", error=str(error))
            raise
        except BaseException as error:
            record.update(status="failed", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            async def finalize():
                await cancel_and_wait(tasks)
                record["shard_statuses"] = []
                for index in range(1, SHARDS + 1):
                    path = output / f"shard-{index}" / "launch.json"
                    child = json.loads(path.read_text()) if path.exists() else {"status": "not_started"}
                    record["shard_statuses"].append({"index": index, **{key: child[key]
                        for key in ("status", "finished_utc", "error") if key in child}})
                try:
                    if not await observe("final") and record["status"] == "finished":
                        raise ValueError("Aggregate resource policy invalid at shutdown")
                    after = await asyncio.to_thread(snapshot)
                    digest = shared.configuration_hash(configuration())
                    unchanged = after == initial and digest == record["configuration_sha256"]
                    record["artifacts_after"] = {**after, "configuration_sha256": digest, "unchanged": unchanged}
                    if not unchanged:
                        raise ValueError("Campaign inputs/configuration changed")
                except (ValueError, OSError) as error:
                    record.update(status="invalidated", artifacts_after={"unchanged": False, "error": str(error)})
                    raise
                finally:
                    journal.flush()
                    record["resource_history"]["sha256"] = match.sha256(journal_path)
                    record["finished_utc"] = utc_now().isoformat()
                    match.atomic_json(output / "campaign.json", record)
            try:
                # A first signal can arrive after a natural failure already
                # began shutdown. Shield the whole finalization, not only each
                # engine, so it cannot re-cancel children or skip the manifest.
                await match.finish_cleanup(finalize())
            except asyncio.CancelledError:
                record.update(status="interrupted", error="Supervisor cancelled during finalization")
                record["finished_utc"] = utc_now().isoformat()
                match.atomic_json(output / "campaign.json", record)
                raise
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run"), nargs="?", default="check")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.action == "check" and args.output is not None:
        parser.error("check does not accept --output")
    if args.action == "run" and args.output is None:
        parser.error("run requires --output NEW_DIRECTORY")
    async def execute():
        # All coordinated hashing uses one background worker, not eight more
        # unbounded CPU jobs alongside the eight active engine search workers.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        return await cooperative_signals(check() if args.action == "check" else run(args.output))
    try:
        print(json.dumps(asyncio.run(execute()), indent=2, allow_nan=False))
        return 0
    except shared.WindowExpired:
        print("Phase 4D.2 stopped at its original cutoff; incomplete evidence retained.", file=sys.stderr)
        return 124
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Phase 4D.2 interrupted; cleanup completed and available evidence retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TimeoutError, match.chess.engine.EngineError) as error:
        print(f"Phase 4D.2 check/run failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
