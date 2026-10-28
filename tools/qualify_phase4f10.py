#!/usr/bin/env python3
"""Run the fixed Continuation History on/off qualification once, within one night.

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
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import sys
import time

from tooling import direct_entry

if __name__ == "__main__":
    direct_entry(__file__)

import match
import qualification as shared
from qualify_phase3l import cooperative_signals, cancel_and_wait, append_resource_event

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase4f10-continuation-512-v1"
PROTOCOL_DOCUMENT = "docs/experiments/phase4f10-match.md"
CHESS_VERSION = "1.11.2"
SHARDS, SHARD_PAIRS, PAIRS = 4, 64, 256
SEEDS = tuple(range(202610284101, 202610284105))
POLL_SECONDS, MAX_RESOURCE_GAP_SECONDS = 1.0, 5.0
PIN_FILE = "tests/data/phase4f10-match-pins.json"
EXCLUSIONS = "tests/data/phase4f10-match-exclusions.json"
GENERATION = "tests/data/phase4f10-match-generation.json"
GENERATOR = "tools/generate_phase4f10_openings.py"
BUILD_MANIFEST = "build/experiments/phase4f9/manifest.json"
ENGINE_PATH = "build/experiments/phase4f9/chess0live"
ENGINE_SHA256 = "c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
SOURCE_REVISION = "69215b4c7a35bb0ba7ea4b1e9287e8f760199b6c"
# This literal inventory is the existing build manifest's complete source set.
# A manifest cannot silently drop a source or replace it with another path.
SOURCE_RELATIVE_NAMES = (
    "Makefile",
    "include/chess0live/detail/continuation_history.hpp",
    "include/chess0live/detail/move_hint_entry.hpp",
    "include/chess0live/detail/transposition_entry.hpp",
    "include/chess0live/exchange.hpp",
    "include/chess0live/nnue.hpp",
    "include/chess0live/position.hpp",
    "include/chess0live/search.hpp",
    "include/chess0live/search_policy.hpp",
    "include/chess0live/tablebase.hpp",
    "include/chess0live/time_management.hpp",
    "include/chess0live/types.hpp",
    "src/exchange.cpp",
    "src/main.cpp",
    "src/nnue.cpp",
    "src/position.cpp",
    "src/search.cpp",
    "src/tablebase.cpp",
    "third_party/fathom/LICENSE",
    "third_party/fathom/README.md",
    "third_party/fathom/chess0live-safety.patch",
    "third_party/fathom/manifest.json",
    "third_party/fathom/src/stdendian.h",
    "third_party/fathom/src/tbchess.c",
    "third_party/fathom/src/tbconfig.h",
    "third_party/fathom/src/tbprobe.c",
    "third_party/fathom/src/tbprobe.h",
)
FROZEN_SOURCE_PREFIX = "build/experiments/phase4f9/source/"
BUILD_SOURCE_NAMES = tuple(FROZEN_SOURCE_PREFIX + name for name in SOURCE_RELATIVE_NAMES)
ORIGIN_MANIFEST = "build/experiments/phase4f9/origin-manifest.json"


def read_json_document(path):
    """Reject duplicate keys rather than silently choosing a preparation identity."""
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key: " + key)
            value[key] = item
        return value
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def input_pins():
    """Read committed preparation pins; never infer them from live assets."""
    import re
    document = read_json_document(ROOT / PIN_FILE)
    if not isinstance(document, dict):
        raise ValueError("Malformed Phase 4F.10 preparation pins")
    pins = document.get("input_sha256")
    if (type(document.get("schema_version")) is not int or document.get("schema_version") != 1
            or document.get("protocol_id") != PROTOCOL_ID
            or not isinstance(pins, dict) or set(pins) != set(PINNED_INPUTS)
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in pins.values())):
        raise ValueError("Malformed Phase 4F.10 preparation pins")
    return pins


def frozen():
    pins = input_pins()
    return {
        "engine": (ROOT / ENGINE_PATH, ENGINE_SHA256),
        "network": (ROOT / "networks/nn-1a298aa575a0.nnue", NETWORK_SHA256),
        **{f"openings_{i}": (ROOT / f"tests/data/phase4f10-match-{i:02d}.json",
                             pins[f"tests/data/phase4f10-match-{i:02d}.json"])
           for i in range(1, SHARDS + 1)},
    }


SOURCES = ("tools/qualify_phase4f10.py", "tools/audit_phase4f10.py", GENERATOR,
           "tests/phase4f10_openings_test.py", "tests/qualify_phase4f10_test.py", "tests/audit_phase4f10_test.py",
           "tools/generate_phase4d2_openings.py", "tools/generate_readiness_openings.py",
           "tools/qualify_phase3l.py", "tools/audit_phase3l.py", "tools/qualification.py", "tools/match.py",
           "tools/audit_time_policy.py", "tools/match_statistics.py", "tools/resources.py",
           "requirements-match.txt", PROTOCOL_DOCUMENT, EXCLUSIONS, GENERATION, BUILD_MANIFEST, ORIGIN_MANIFEST, PIN_FILE,
           "tests/data/phase4f3-puzzles.json", "tools/generate_lmr_20261022_openings.py",
           "tools/run.py", "tools/tooling.py", "tools/python-packages.json",
           "tests/match_test.py", "tests/audit_time_policy_test.py",
           "tests/data/phase4d2-exclusions.json", *BUILD_SOURCE_NAMES,
    *(f"tests/data/phase4f10-match-{i:02d}.json" for i in range(1, 5)))
# Every prepared helper and data/source input is pinned before readiness. The
# pin document itself is snapshotted, but cannot include its own digest.
PINNED_INPUTS = tuple(name for name in SOURCES if name != PIN_FILE)
CHECK_OPTIONS = ("Late Move Reductions", "Deep Quiet Reductions", "Countermove Ordering",
                 "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut",
                 "TT Move Hints", "Continuation History")
COMMON_OPTIONS = (("Time Policy", "classic"), ("SyzygyProbeLimit", "0"), ("SyzygyProbeDepth", "1"),
                  ("Late Move Reductions", "true"), ("Capture Ordering", "mvv-lva"),
                  *((name, "false") for name in CHECK_OPTIONS
                    if name not in ("Late Move Reductions", "Continuation History")))
ROLE_OPTIONS = tuple((*COMMON_OPTIONS, ("Continuation History", "true" if enabled else "false"))
                     for enabled in (True, False))
REVISIONS = ("phase4f10-continuation-on-69215b4", "phase4f10-continuation-off-69215b4")

utc_now = shared.utc_now


def profile(index):
    if type(index) is not int or not 1 <= index <= SHARDS:
        raise ValueError(f"Shard index must be 1 through {SHARDS}")
    assets = frozen()
    selected = {"engine": assets["engine"], "network": assets["network"], "openings": assets[f"openings_{index}"]}
    return shared.QualificationProfile(ROOT, f"{PROTOCOL_ID}-shard-{index}", CHESS_VERSION,
        SHARD_PAIRS, SEEDS[index-1], selected, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS,
        REVISIONS, CHECK_OPTIONS)


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


def validate_build_provenance():
    """Bind the executable to all 27 frozen sources and the original build.

    The campaign pins immutable source copies, not mutable checkout paths.
    Exact inventories prevent a manifest from silently dropping a source; the
    committed-source map and original build manifest must agree with those copies.
    This validates recorded provenance, not a new reproducible-build claim.
    """
    import re
    document = read_json_document(ROOT / BUILD_MANIFEST)
    expected = {"schema_version": 1, "engine_source_revision": SOURCE_REVISION,
                "binary_sha256": ENGINE_SHA256, "network_sha256": NETWORK_SHA256,
                "origin_manifest": ORIGIN_MANIFEST,
                "copied_from": "build/experiments/phase4f8/native/chess0live"}
    if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
            or any(document.get(key) != value for key, value in expected.items())):
        raise ValueError("Frozen build provenance identity mismatch")
    digests = document.get("source_sha256")
    committed = document.get("committed_source_sha256")
    if (not isinstance(digests, dict) or set(digests) != set(BUILD_SOURCE_NAMES)
            or not isinstance(committed, dict) or set(committed) != set(SOURCE_RELATIVE_NAMES)):
        raise ValueError("Frozen build provenance source inventory mismatch")
    for name, digest in digests.items():
        relative = name.removeprefix(FROZEN_SOURCE_PREFIX)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Malformed frozen build source SHA-256: " + name)
        if match.sha256(ROOT / name) != digest or committed[relative] != digest:
            raise ValueError("Frozen build source SHA-256 mismatch: " + name)
    if match.sha256(ROOT / ORIGIN_MANIFEST) != document.get("origin_manifest_sha256"):
        raise ValueError("Original build manifest SHA-256 mismatch")
    origin = read_json_document(ROOT / ORIGIN_MANIFEST)
    if (not isinstance(origin, dict) or origin.get("phase") != "4F.8"
            or origin.get("binary") != {"path": document["copied_from"], "sha256": ENGINE_SHA256}
            or origin.get("network") != {"path": "networks/nn-1a298aa575a0.nnue", "sha256": NETWORK_SHA256}
            or not isinstance(origin.get("sources"), dict)
            or not isinstance(origin.get("upstream_dependencies"), dict)):
        raise ValueError("Original build manifest identity mismatch")
    originals, dependencies = origin["sources"], origin["upstream_dependencies"]
    if (set(originals) & set(dependencies) or {**originals, **dependencies} != committed):
        raise ValueError("Original build source inventory/digests mismatch")


def snapshot():
    for name, expected in input_pins().items():
        if match.sha256(ROOT/name) != expected:
            raise ValueError(f"Frozen input SHA-256 mismatch: {name}")
    validate_build_provenance()
    return shared.snapshot(shared.QualificationProfile(ROOT, PROTOCOL_ID, CHESS_VERSION, PAIRS, 0,
        frozen(), SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS, REVISIONS))


def fingerprints():
    paths = {path.resolve() for path, _ in frozen().values()} | {(ROOT/name).resolve() for name in SOURCES}
    return {str(path): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            for path in paths for s in (path.stat(),)}


def launch_policy(now=None, *, allow_daytime=False, require_window=False):
    """Limit this preparation to normal nights; never inherit another grant.

    Search-free readiness may run during daytime, but it records that launch is
    unavailable. Actual games must begin 23:00–23:30 Helsinki and retain the
    originally derived next-07:00 UTC cutoff through all child lifetimes.
    """
    if type(allow_daytime) is not bool:
        raise ValueError("Daytime permission must be an explicit boolean")
    if allow_daytime:
        raise ValueError("Phase 4F.10 has no daytime authorization")
    policy = shared.launch_policy(now or utc_now(), allow_daytime=False)
    local = datetime.fromisoformat(policy["local_time"])
    permitted = local.hour == 23 and local.minute < 30
    window = "23:00–23:30 Europe/Helsinki"
    if require_window and not permitted:
        raise ValueError("Phase 4F.10 may launch only " + window)
    policy.update(launch_window=window, launch_permitted=permitted,
                  daytime_authorization=None)
    return policy


def opening_check():
    """Referee-only replay: all original histories, unique roots, no exposure overlap."""
    from audit_phase3l import definitions, root_key
    roots, ids = set(), set()
    for index in range(1, SHARDS+1):
        document = json.loads(frozen()[f"openings_{index}"][0].read_text())
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
    reservation = max(6 * 1024**3, SHARDS * per_shard)
    policy.update(active_search_workers=SHARDS, resident_engines=2*SHARDS,
                  estimated_memory_bytes=reservation, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    return policy, (SHARDS <= policy["max_cpu_workers"] and memory is not None and memory > 0
                    and reservation <= memory*policy["memory_fraction"])


def validate_options(protocol, configured, spec, settings):
    """Validate this engine generation without relaxing historical protocols."""
    kinds = {"Hash": "spin", "Threads": "spin", "Move Overhead": "spin", "EvalFile": "string",
             "Time Policy": "combo", "Capture Ordering": "combo", "SyzygyPath": "string",
             "SyzygyProbeLimit": "spin", "SyzygyProbeDepth": "spin", "Clear Hash": "button",
             "Ponder": "check", "Search Diagnostics": "check",
             **{name: "check" for name in CHECK_OPTIONS}}
    if set(protocol.options) != set(kinds):
        raise ValueError("Unexpected UCI option inventory")
    for name, kind in kinds.items():
        if name not in protocol.options or protocol.options[name].type != kind:
            raise ValueError("Missing/wrong UCI type: " + name)
    for name in ("Ponder", "Search Diagnostics", *CHECK_OPTIONS):
        if protocol.options[name].default is not (name == "Late Move Reductions"):
            raise ValueError("Unexpected UCI check default: " + name)
    for name, default, choices in (("Time Policy", "classic", {"classic", "forecast", "bounded"}),
                                   ("Capture Ordering", "mvv-lva", {"mvv-lva", "see"})):
        option = protocol.options[name]
        if option.default != default or set(option.var or ()) != choices:
            raise ValueError("Unexpected UCI combo choices/default: " + name)
    for name, metadata in {"Hash": (64, 1, 16384), "Threads": (1, 1, 64),
                           "Move Overhead": (20, 0, 5000), "SyzygyProbeLimit": (7, 0, 7),
                           "SyzygyProbeDepth": (1, 1, 128)}.items():
        option = protocol.options[name]
        if (option.default, option.min, option.max) != metadata:
            raise ValueError("Unexpected UCI spin default/range: " + name)
    for name, default in (("EvalFile", "nn-1a298aa575a0.nnue"), ("SyzygyPath", "<empty>"),
                          ("Clear Hash", None)):
        if protocol.options[name].default != default:
            raise ValueError("Unexpected UCI option default: " + name)
    expected = {"Hash": settings.hash_mb, "Threads": settings.threads,
                "EvalFile": str(spec.network), "Move Overhead": settings.move_overhead_ms,
                "Search Diagnostics": False, "SyzygyPath": ""}
    for name, value in spec.extra_options:
        expected[name] = protocol.options[name].parse(value)
    for name, value in expected.items():
        if configured.get(name) != value:
            raise ValueError("Configured UCI option differs from frozen package: " + name)


async def check(allow_daytime=False):
    # Reject inherited grants before starting even a readiness process.
    launch_policy(allow_daytime=allow_daytime)
    if match.chess.__version__ != CHESS_VERSION:
        raise ValueError(f"Qualification requires chess=={CHESS_VERSION}")
    initial, details = snapshot(), opening_check()
    budget, allowed = resource_policy()
    if not allowed:
        raise ValueError("Aggregate four-worker/eight-engine resource budget is insufficient")
    specs, settings = fixed_request(); settings.validate()
    engines, pids = [], set()
    for spec in specs:
        log = io.StringIO()
        transport, protocol, configured = await match.start_engine(spec, settings, log)
        try:
            validate_options(protocol, configured, spec, settings)
            # python-chess stores declarations by name, which can hide a
            # repeated declaration. Check the raw handshake as well.
            declarations = []
            for line in log.getvalue().splitlines():
                event = json.loads(line)
                if event["direction"] == "from_engine" and event["line"].startswith("option "):
                    declaration = re.fullmatch(r"option name (.+?) type .+", event["line"])
                    if declaration is None:
                        raise ValueError("Malformed raw UCI option declaration")
                    declarations.append(declaration.group(1))
            if len(declarations) != len(set(declarations)):
                raise ValueError("Duplicate raw UCI option declaration")
            if set(declarations) != set(protocol.options):
                raise ValueError("Raw UCI option inventory mismatch")
            pid = transport.get_pid()
            if type(pid) is not int or pid <= 0 or pid in pids:
                raise ValueError("Missing or repeated preflight engine process identity")
            pids.add(pid)
            engines.append({"role": spec.role, "pid": pid, "id": dict(protocol.id), "configured": configured,
                            "options": {name: vars(option).copy() for name, option in protocol.options.items()}})
        finally:
            await match.close_engine(transport, protocol)
        engines[-1]["returncode"] = transport.get_returncode()
        if engines[-1]["returncode"] != 0:
            raise ValueError("Preflight engine did not exit cleanly: " + spec.role)
        engines[-1]["transcript"] = [json.loads(line) for line in log.getvalue().splitlines()]
    if snapshot() != initial:
        raise ValueError("Frozen inputs or sources changed during preflight")
    config = configuration()
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "status": "checked", "checked_utc": utc_now().isoformat(),
            "configuration": config, "configuration_sha256": shared.configuration_hash(config),
            "frozen": initial["assets"], "sources": initial["sources"], "artifacts_before": initial,
            "launch_policy": launch_policy(allow_daytime=allow_daytime), "preflight": {**details, "engines": engines, "resource_policy": budget}}


def child_report(master, index):
    specs, settings = fixed_request(); config = shared.configuration(profile(index), specs, settings)
    assets = master["frozen"]
    return {"schema_version": 1, "protocol_id": profile(index).protocol_id, "status": "checked",
            "checked_utc": master["checked_utc"], "configuration": config,
            "configuration_sha256": shared.configuration_hash(config), "chess_version": CHESS_VERSION,
            "assets": {"engine": assets["engine"], "network": assets["network"], "openings": assets[f"openings_{index}"]},
            "sources": master["sources"], "preflight": {"opening_count": SHARD_PAIRS, "distinct_roots": SHARD_PAIRS,
                "engines": deepcopy(master["preflight"]["engines"]), "resource_policy": master["preflight"]["resource_policy"]}}


def process_cleanup(output):
    """Record absence of every journaled engine PID after owned cleanup joins."""
    pids = set()
    for path in output.glob("shard-*/match/games.jsonl"):
        for line in path.read_text().splitlines():
            pids.update(engine["pid"] for engine in json.loads(line).get("engines", {}).values())
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


async def run(output, allow_daytime=False):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Campaign output must be a new directory; overwrite/resume is disabled")
    started = utc_now()
    policy = launch_policy(started, allow_daytime=allow_daytime, require_window=True)
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
                raise ValueError("Aggregate four-worker/eight-engine resource budget became insufficient")

        async def monitor():
            previous, previous_utc = time.monotonic(), utc_now()
            while True:
                await guard(trigger="periodic")
                await asyncio.sleep(POLL_SECONDS)
                current, current_utc = time.monotonic(), utc_now()
                if (current - previous > MAX_RESOURCE_GAP_SECONDS
                        or (current_utc - previous_utc).total_seconds() > MAX_RESOURCE_GAP_SECONDS
                        or current_utc < previous_utc):
                    raise ValueError("Aggregate resource monitor exceeded the five-second observation gap")
                previous, previous_utc = current, current_utc

        async def deadline():
            await asyncio.sleep(max(0, (cutoff - utc_now()).total_seconds()))
            raise shared.WindowExpired("Helsinki 07:00 cutoff; fixed sample incomplete")

        def child_window(**_):
            current = shared.launch_policy(utc_now(), allow_daytime=allow_daytime)
            current.update(cutoff_utc=policy["cutoff_utc"], cutoff_local=policy["cutoff_local"],
                           remaining_seconds=(cutoff - utc_now()).total_seconds(),
                           daytime_authorization=policy["daytime_authorization"])
            return current

        async def worker(index):
            async def cached_preflight():
                return await shared.disk_io(child_report, record, index)
            async def before_game(game_id):
                await guard(game_id, index)
            return await shared.run(profile(index), output / f"shard-{index}", allow_daytime=allow_daytime,
                preflight=cached_preflight, request=fixed_request, clock=utc_now, window=child_window,
                run_guard=before_game, fail_fast=True, manage_deadline=False)

        match.atomic_json(output / "campaign.json", record)
        try:
            if not await observe("initial"):
                raise ValueError("Aggregate four-worker/eight-engine resource budget is insufficient")
            checked = await check(allow_daytime=allow_daytime)
            if checked["artifacts_before"] != initial or fingerprints() != metadata:
                raise ValueError("Frozen campaign inputs changed during preflight")
            record.update(checked_utc=checked["checked_utc"], preflight=checked["preflight"])
            if utc_now() >= cutoff:
                raise shared.WindowExpired("Initial Helsinki cutoff elapsed during preflight")
            # Do not begin held-out games if setup has consumed the launch
            # window; the originally recorded 07:00 cutoff never moves.
            launch_policy(utc_now(), allow_daytime=allow_daytime, require_window=True)
            match.atomic_json(output / "campaign.json", record)
            workers = [asyncio.create_task(worker(i), name=f"phase4f10-shard-{i}")
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
                    record["cleanup"] = await asyncio.to_thread(process_cleanup, output)
                    if record["cleanup"]["alive_pids"] or record["cleanup"]["unverified_pids"]:
                        raise ValueError("Engine process cleanup could not be verified")
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
        # All coordinated hashing uses one background worker, not four more
        # unbounded CPU jobs alongside the four active engine search workers.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        return await cooperative_signals(check() if args.action == "check"
                                         else run(args.output))
    try:
        print(json.dumps(asyncio.run(execute()), indent=2, allow_nan=False))
        return 0
    except shared.WindowExpired:
        print("Phase 4F.10 qualification stopped at its original cutoff; incomplete evidence retained.", file=sys.stderr)
        return 124
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Phase 4F.10 qualification interrupted; cleanup completed and available evidence retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TimeoutError, match.chess.engine.EngineError) as error:
        print(f"Phase 4F.10 qualification check/run failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
