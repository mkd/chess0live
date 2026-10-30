#!/usr/bin/env python3
"""Run the fixed before/after NNUE optimization match once, to its fixed cutoff.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The existing QualificationProfile/run implementation owns every game's clocks,
process cleanup, raw evidence and child manifests. This facade adds only the
aggregate resource/deadline supervisor. Frozen Phase 3L sources remain unchanged.
No scheduling, resume or sample overrides. The separately frozen October 30
daytime amendment requires an explicit flag and fresh quiet-host confirmation;
ordinary search-free readiness remains available anytime.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
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
PROTOCOL_ID = "phase4f13-nnue-2048-v1"
PROTOCOL_DOCUMENT = "docs/experiments/phase4f13-match.md"
DAYTIME_AMENDMENT = "docs/experiments/phase4f13-match-daytime-20261030.md"
DAYTIME_AUTHORIZATION = "phase4f13-daytime-20261030"
DAYTIME_DATE = "2026-10-30"
DAYTIME_WINDOW = "2026-10-30 14:00–22:45 Europe/Helsinki"
CHESS_VERSION = "1.11.2"
SHARDS, SHARD_PAIRS, PAIRS = 4, 256, 1024
SEEDS = tuple(range(202610304131, 202610304135))
POLL_SECONDS, MAX_RESOURCE_GAP_SECONDS = 1.0, 5.0
SMOKE_PAIRS, SMOKE_TIMEOUT_SECONDS = 4, 600.0
SMOKE_SEEDS = tuple(range(202610304151, 202610304155))
SMOKE_CATALOG = "tests/data/openings-development.json"
SMOKE_OPENING_IDS = ("development-01", "development-05", "development-08", "development-09")
SMOKE_SUITE_FILES = tuple(f"tests/data/phase4f13-match-smoke-{i:02d}.json" for i in range(1, 5))
BASE_PIN_FILE = "tests/data/phase4f13-match-pins.json"
PIN_FILE = "tests/data/phase4f13-match-daytime-20261030-pins.json"
EXCLUSIONS = "tests/data/phase4f13-match-exclusions.json"
GENERATION = "tests/data/phase4f13-match-generation.json"
GENERATOR = "tools/generate_phase4f13_openings.py"
ROLE_DIRECTORIES = {"candidate": "build/experiments/phase4f12/candidate",
                    "opponent": "build/experiments/phase4f12/baseline"}
ENGINE_PATHS = {role: directory + "/chess0live" for role, directory in ROLE_DIRECTORIES.items()}
ENGINE_SHA256S = {
    "candidate": "04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594",
    "opponent": "8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc",
}
SOURCE_REVISIONS = {"candidate": "3ee5eff30981b73099e8a118ff1712f89cdc285a",
                    "opponent": "1ca87d6a596531d19b7b698b84c171fc314fc046"}
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
COMPILE_FLAGS = "-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g"
BUILD_MANIFESTS = {role: directory + "/manifest.json" for role, directory in ROLE_DIRECTORIES.items()}
ORIGIN_MANIFESTS = {role: directory + "/origin-manifest.json" for role, directory in ROLE_DIRECTORIES.items()}
BUILD_LOGS = {role: directory + "/build.log" for role, directory in ROLE_DIRECTORIES.items()}
# Exact inventories from the two existing builds. These are provenance records,
# not a claim that compiling the copies would reproduce identical machine code.
BUILD_SOURCE_SUFFIXES = (
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
    "src/exchange.cpp", "src/main.cpp", "src/nnue.cpp", "src/position.cpp",
    "src/search.cpp", "src/tablebase.cpp",
    "third_party/fathom/src/stdendian.h", "third_party/fathom/src/tbchess.c",
    "third_party/fathom/src/tbconfig.h", "third_party/fathom/src/tbprobe.c",
    "third_party/fathom/src/tbprobe.h",
)
ROLE_SOURCE_SUFFIXES = {
    "candidate": (*BUILD_SOURCE_SUFFIXES, "tests/nnue_features_test.cpp"),
    "opponent": (*BUILD_SOURCE_SUFFIXES, "networks/manifest.json"),
}
BUILD_SOURCE_NAMES = tuple(directory + "/source/" + name
    for role, directory in ROLE_DIRECTORIES.items() for name in ROLE_SOURCE_SUFFIXES[role])


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
        raise ValueError("Malformed Phase 4F.13 preparation pins")
    pins = document.get("input_sha256")
    if (type(document.get("schema_version")) is not int or document.get("schema_version") != 1
            or document.get("protocol_id") != PROTOCOL_ID
            or not isinstance(pins, dict) or set(pins) != set(PINNED_INPUTS)
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in pins.values())):
        raise ValueError("Malformed Phase 4F.13 preparation pins")
    return pins


def frozen():
    pins = input_pins()
    return {
        **{"engine_" + role: (ROOT / ENGINE_PATHS[role], ENGINE_SHA256S[role])
           for role in ROLE_DIRECTORIES},
        "network": (ROOT / "networks/nn-1a298aa575a0.nnue", NETWORK_SHA256),
        **{f"openings_{i}": (ROOT / f"tests/data/phase4f13-match-{i:02d}.json",
                             pins[f"tests/data/phase4f13-match-{i:02d}.json"])
           for i in range(1, SHARDS + 1)},
        **{f"smoke_openings_{i}": (ROOT / name, pins[name])
           for i, name in enumerate(SMOKE_SUITE_FILES, 1)},
    }


SOURCES = (
    "tools/qualify_phase4f13.py", "tools/audit_phase4f13.py", "tools/audit_phase4f13_games.py", GENERATOR,
    "tests/phase4f13_openings_test.py", "tests/qualify_phase4f13_test.py", "tests/audit_phase4f13_test.py",
    "tools/paired_betting.py", "tests/paired_betting_test.py",
    "tools/generate_phase4d2_openings.py", "tools/generate_readiness_openings.py",
    "tools/qualify_phase3l.py", "tools/audit_phase3l.py", "tools/audit_time_policy.py", "tools/qualification.py", "tools/match.py",
    "tools/match_statistics.py", "tools/resources.py", "requirements-match.txt",
    PROTOCOL_DOCUMENT, DAYTIME_AMENDMENT, BASE_PIN_FILE, EXCLUSIONS, GENERATION, PIN_FILE,
    SMOKE_CATALOG, *SMOKE_SUITE_FILES,
    *BUILD_MANIFESTS.values(), *ORIGIN_MANIFESTS.values(), *BUILD_LOGS.values(),
    "tests/data/phase4f3-puzzles.json", "tools/generate_lmr_20261022_openings.py",
    "tools/run.py", "tools/tooling.py", "tools/python-packages.json", "tests/match_test.py",
    "tests/data/phase4d2-exclusions.json", *BUILD_SOURCE_NAMES,
    *(f"tests/data/phase4f13-match-{i:02d}.json" for i in range(1, SHARDS + 1)),
)
# Every prepared helper and data/source input is pinned before readiness. The
# pin document itself is snapshotted, but cannot include its own digest.
PINNED_INPUTS = tuple(name for name in SOURCES if name != PIN_FILE)
CHECK_OPTIONS = ("Late Move Reductions", "Deep Quiet Reductions", "Countermove Ordering",
                 "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut",
                 "TT Move Hints", "Continuation History")
COMMON_OPTIONS = (("Time Policy", "classic"), ("SyzygyProbeLimit", "0"), ("SyzygyProbeDepth", "1"),
                  ("Late Move Reductions", "true"), ("Capture Ordering", "mvv-lva"),
                  *((name, "false") for name in CHECK_OPTIONS
                    if name != "Late Move Reductions"))
ROLE_OPTIONS = (COMMON_OPTIONS, COMMON_OPTIONS)
REVISIONS = tuple(SOURCE_REVISIONS[role] for role in ("candidate", "opponent"))

utc_now = shared.utc_now


def profile(index, *, smoke=False):
    if type(index) is not int or not 1 <= index <= SHARDS:
        raise ValueError(f"Shard index must be 1 through {SHARDS}")
    if type(smoke) is not bool:
        raise ValueError("Smoke profile selection must be boolean")
    assets = frozen()
    prefix = "smoke_openings" if smoke else "openings"
    selected = {**{key: assets[key] for key in ("engine_candidate", "engine_opponent", "network")},
                "openings": assets[f"{prefix}_{index}"]}
    identity = f"{PROTOCOL_ID}-{'smoke-' if smoke else ''}shard-{index}"
    return shared.QualificationProfile(ROOT, identity, CHESS_VERSION,
        1 if smoke else SHARD_PAIRS, (SMOKE_SEEDS if smoke else SEEDS)[index-1], selected, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS,
        REVISIONS, CHECK_OPTIONS)


def validate_role_assets():
    """Reject swapped roles, aliased executables, and same-binary comparisons."""
    assets = frozen()
    paths = []
    for role in ("candidate", "opponent"):
        path, digest = assets["engine_" + role]
        expected = ROOT / ENGINE_PATHS[role]
        if (path != expected or path.resolve() != expected.absolute()
                or digest != ENGINE_SHA256S[role]):
            raise ValueError("Frozen engine role identity mismatch: " + role)
        paths.append(path)
    if (ENGINE_SHA256S["candidate"] == ENGINE_SHA256S["opponent"]
            or paths[0].samefile(paths[1])):
        raise ValueError("Comparison requires two distinct frozen binaries")


def fixed_request():
    # The shared default request intentionally models an option toggle on one
    # binary. Inject this request instead; never alter the historical helper.
    validate_role_assets()
    if ROLE_OPTIONS != (COMMON_OPTIONS, COMMON_OPTIONS):
        raise ValueError("Both engine roles require the same frozen options")
    assets = frozen()
    settings = match.Settings(initial=15.0, increment=0.15, hash_mb=64, threads=1,
                              max_plies=512, startup_timeout=30.0,
                              protocol_timeout=5.0, move_overhead_ms=20, smoke=False)
    specs = [match.EngineSpec(role, assets["engine_" + role][0].resolve(), assets["network"][0].resolve(),
                             source_revision=revision, extra_options=options)
             for role, revision, options in zip(("candidate", "opponent"), REVISIONS, ROLE_OPTIONS)]
    return specs, settings


def smoke_request():
    specs, settings = fixed_request()
    return specs, replace(settings, smoke=True)


def configuration():
    specs, settings = fixed_request()
    common = shared.configuration(profile(1), specs, settings)
    return {"settings": common["settings"], "pairs": PAIRS, "games": 2*PAIRS,
            "shards": SHARDS, "shard_pairs": SHARD_PAIRS, "active_search_workers": SHARDS,
            "resident_engines": 2*SHARDS, "resource_poll_seconds": POLL_SECONDS,
            "max_resource_gap_seconds": MAX_RESOURCE_GAP_SECONDS, "seeds": list(SEEDS),
            "engines": common["engines"], "ponder": False, "diagnostics": False}


def validate_build_provenance():
    """Verify both complete, frozen Phase 4F.12 build histories without rebuilding."""
    validate_role_assets()
    for role, directory_name in ROLE_DIRECTORIES.items():
        directory = ROOT / directory_name
        document = read_json_document(ROOT / BUILD_MANIFESTS[role])
        expected = {"schema_version": 1, "role": "baseline" if role == "opponent" else role,
                    "engine_source_revision": SOURCE_REVISIONS[role],
                    "binary_sha256": ENGINE_SHA256S[role], "network_sha256": NETWORK_SHA256,
                    "compile_flags": COMPILE_FLAGS}
        if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
                or any(document.get(key) != value for key, value in expected.items())):
            raise ValueError("Frozen build provenance identity mismatch: " + role)
        for field, name in (("origin_manifest", ORIGIN_MANIFESTS[role]), ("build_log", BUILD_LOGS[role])):
            path = ROOT / name
            if (document.get(field) != name or path.resolve().parent != directory.absolute()
                    or match.sha256(path) != document.get(field + "_sha256")):
                raise ValueError("Frozen build provenance " + field + " SHA-256/path mismatch: " + role)
        digests = document.get("source_sha256")
        prefix = directory_name + "/source/"
        expected_sources = {prefix + name for name in ROLE_SOURCE_SUFFIXES[role]}
        if not isinstance(digests, dict) or set(digests) != expected_sources:
            raise ValueError("Frozen build provenance source inventory mismatch: " + role)
        copied = {}
        for name, digest in digests.items():
            path = ROOT / name
            if (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    or not path.resolve().is_relative_to(directory.absolute() / "source")):
                raise ValueError("Malformed/unsafe frozen build source SHA-256/path: " + name)
            if match.sha256(path) != digest:
                raise ValueError("Frozen build source SHA-256 mismatch: " + name)
            copied[name.removeprefix(prefix)] = digest
        origin = read_json_document(ROOT / ORIGIN_MANIFESTS[role])
        if not isinstance(origin, dict):
            raise ValueError("Original build provenance identity mismatch: " + role)
        if role == "opponent":
            original_sources = origin.get("sources")
            binary = origin.get("binary")
            valid = (origin.get("parent_commit") == SOURCE_REVISIONS[role]
                     and isinstance(binary, dict) and binary.get("sha256") == ENGINE_SHA256S[role]
                     and binary.get("flags") == COMPILE_FLAGS
                     and origin.get("network_sha256") == NETWORK_SHA256)
        else:
            original_sources = origin.get("source_sha256")
            oracle = origin.get("oracle_report_sha256")
            valid = (origin.get("candidate_sha256") == ENGINE_SHA256S[role]
                     and origin.get("baseline_sha256") == ENGINE_SHA256S["opponent"]
                     and isinstance(oracle, str) and re.fullmatch(r"[0-9a-f]{64}", oracle))
        if not valid or original_sources != copied:
            raise ValueError("Original build provenance identity/source inventory mismatch: " + role)


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
    """Admit an ordinary night or the explicit, dated daytime amendment."""
    if type(allow_daytime) is not bool:
        raise ValueError("Phase 4F.13 daytime selection must be boolean")
    policy = shared.launch_policy(now or utc_now(), allow_daytime=allow_daytime)
    local = datetime.fromisoformat(policy["local_time"])
    if allow_daytime:
        permitted = (local.date().isoformat() == DAYTIME_DATE
                     and (14, 0) <= (local.hour, local.minute) < (22, 45))
        window, authorization = DAYTIME_WINDOW, DAYTIME_AUTHORIZATION
    else:
        permitted = local.hour == 23 and local.minute < 30
        window, authorization = "23:00–23:30 Europe/Helsinki", None
    if (require_window or allow_daytime) and not permitted:
        raise ValueError("Phase 4F.13 may launch only " + window)
    policy.update(launch_window=window, launch_permitted=permitted, daytime_authorization=authorization)
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
    catalog = read_json_document(ROOT / SMOKE_CATALOG)
    catalog_entries = {entry["id"]: entry for entry in catalog["openings"]}
    smoke_roots = set()
    for index, identifier in enumerate(SMOKE_OPENING_IDS, 1):
        document = read_json_document(frozen()[f"smoke_openings_{index}"][0])
        if document["openings"] != [catalog_entries[identifier]]:
            raise ValueError("Smoke suite differs from its exposed development opening")
        entries, keys = definitions(document, full_history=True)
        if len(entries) != 1 or smoke_roots & keys or roots & keys:
            raise ValueError("Smoke roots duplicate or overlap held-out openings")
        smoke_roots.update(keys)
    return {"opening_count": PAIRS, "distinct_roots": len(roots), "previous_root_count": len(excluded),
            "smoke_opening_count": SMOKE_PAIRS, "smoke_distinct_roots": len(smoke_roots)}


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
            "launch_policy": launch_policy(allow_daytime=allow_daytime),
            "preflight": {**details, "engines": engines, "resource_policy": budget}}


def child_report(master, index, *, smoke=False):
    specs, settings = smoke_request() if smoke else fixed_request()
    selected = profile(index, smoke=smoke)
    config = shared.configuration(selected, specs, settings)
    prefix, pairs = ("smoke_openings", 1) if smoke else ("openings", SHARD_PAIRS)
    assets = master["frozen"]
    return {"schema_version": 1, "protocol_id": selected.protocol_id, "status": "checked",
            "checked_utc": master["checked_utc"], "configuration": config,
            "configuration_sha256": shared.configuration_hash(config), "chess_version": CHESS_VERSION,
            "assets": {**{key: assets[key] for key in ("engine_candidate", "engine_opponent", "network")},
                       "openings": assets[f"{prefix}_{index}"]},
            "sources": master["sources"], "preflight": {"opening_count": pairs, "distinct_roots": pairs,
                "engines": deepcopy(master["preflight"]["engines"]), "resource_policy": master["preflight"]["resource_policy"]}}


def process_cleanup(output):
    """Record absence of every journaled engine PID after owned cleanup joins."""
    pids = set()
    paths = (*output.glob("shard-*/match/games.jsonl"),
             *output.glob("clock-smoke/shard-*/match/games.jsonl"))
    for path in paths:
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


def smoke_record(initial):
    return {"status": "pending", "pairs": SMOKE_PAIRS, "games": 2*SMOKE_PAIRS,
            "timeout_seconds": SMOKE_TIMEOUT_SECONDS, "seeds": list(SMOKE_SEEDS),
            "shards": [{"index": index, "protocol_id": profile(index, smoke=True).protocol_id,
                        "seed": SMOKE_SEEDS[index-1], "path": f"clock-smoke/shard-{index}",
                        "openings": initial["assets"][f"smoke_openings_{index}"]}
                       for index in range(1, SHARDS+1)]}


def audit_clock_smoke(output):
    # Independently declared audit rules, never an inference from a score/NPS.
    from audit_phase4f13 import audit_smoke
    return audit_smoke(output)


async def isolated_smoke_audit(output):
    # All smoke engines have exited. Leave the main single I/O worker available
    # to the resource monitor while one separate worker replays eight games.
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="phase4f13-smoke-audit")
    future = asyncio.get_running_loop().run_in_executor(executor, audit_clock_smoke, output)
    async def collect():
        return await future
    try:
        return await match.finish_cleanup(collect())
    finally:
        executor.shutdown(wait=True)


async def run_smoke(output, record, guard, child_window, capture_resources, *, allow_daytime=False):
    """One bounded operational gate, owning its four workers through cleanup."""
    started_tick, started = time.monotonic(), utc_now()
    smoke_cutoff = started + timedelta(seconds=SMOKE_TIMEOUT_SECONDS)
    smoke = record["clock_smoke"]
    smoke.update(status="running", started_utc=started.isoformat())
    workers = []

    async def worker(index):
        admitted = False
        async def cached_preflight():
            return await shared.disk_io(child_report, record, index, smoke=True)
        async def before_game(game_id):
            nonlocal admitted
            await guard(game_id, index, trigger="before_smoke_game")
            # Child preparation and the resource journal both await storage.
            # Admit this shard only after they finish; later games retain the
            # original campaign cutoff rather than the launch-window endpoint.
            if not admitted:
                now = utc_now()
                if now >= datetime.fromisoformat(record["cutoff_utc"]):
                    raise shared.WindowExpired("Original Helsinki cutoff elapsed before smoke admission")
                launch_policy(now, allow_daytime=allow_daytime, require_window=True)
                admitted = True
        return await shared.run(profile(index, smoke=True), output/"clock-smoke"/f"shard-{index}",
            allow_daytime=allow_daytime, preflight=cached_preflight, request=smoke_request, clock=utc_now,
            window=child_window, run_guard=before_game, fail_fast=True, manage_deadline=False)

    async def gate():
        workers.extend(asyncio.create_task(worker(i), name=f"phase4f13-smoke-shard-{i}")
                       for i in range(1, SHARDS+1))
        try:
            pending = set(workers)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
            smoke["cleanup"] = await shared.disk_io(process_cleanup, output/"clock-smoke")
            if smoke["cleanup"]["alive_pids"] or smoke["cleanup"]["unverified_pids"]:
                raise ValueError("Smoke engine process cleanup could not be verified")
            if await shared.disk_io(snapshot) != record["artifacts_before"]:
                raise ValueError("Frozen inputs changed during clock smoke")
            smoke["resource_history"] = await capture_resources()
            smoke.update(status="completed", finished_utc=utc_now().isoformat())
            await shared.disk_io(match.atomic_json, output/"campaign.json", record)
            audited = await isolated_smoke_audit(output)
            audit_path = output/"clock-smoke-audit.json"
            def save_audit():
                with audit_path.open("x", encoding="utf-8") as stream:
                    json.dump(audited, stream, indent=2, allow_nan=False)
                    stream.write("\n")
                return match.sha256(audit_path)
            smoke["audit"] = {"path": "clock-smoke-audit.json", "sha256": await shared.disk_io(save_audit)}
            if audited.get("passed") is not True:
                raise ValueError("Clock smoke audit failed: " + "; ".join(map(str, audited.get("errors", []))))
            if utc_now() >= datetime.fromisoformat(record["cutoff_utc"]):
                raise shared.WindowExpired("Original Helsinki cutoff elapsed during clock smoke audit")
            launch_policy(utc_now(), allow_daytime=allow_daytime, require_window=True)
            if utc_now() >= smoke_cutoff or time.monotonic() - started_tick >= SMOKE_TIMEOUT_SECONDS:
                raise asyncio.TimeoutError("Clock smoke exceeded its original 600-second deadline")
            smoke.update(status="passed", passed_utc=utc_now().isoformat())
            await shared.disk_io(match.atomic_json, output/"campaign.json", record)
        finally:
            # The outer supervisor cancels only this stage, never these children
            # again while their owned cleanup is already in progress.
            await match.finish_cleanup(cancel_and_wait(workers))

    try:
        await shared.disk_io(match.atomic_json, output/"campaign.json", record)
        remaining = SMOKE_TIMEOUT_SECONDS - (time.monotonic() - started_tick)
        if remaining <= 0 or utc_now() >= smoke_cutoff:
            raise asyncio.TimeoutError("Clock smoke deadline elapsed during initial persistence")
        await asyncio.wait_for(gate(), remaining)
    except BaseException as error:
        smoke.update(status="failed", error=f"{type(error).__name__}: {error}")
        smoke.setdefault("finished_utc", utc_now().isoformat())
        await match.finish_cleanup(shared.disk_io(match.atomic_json, output/"campaign.json", record))
        raise


async def run(output, quiet_host=False, *, allow_daytime=False):
    if quiet_host is not True:
        raise ValueError("Run requires fresh --quiet-host confirmation: LM Studio paused, AC/Automatic, Mac awake")
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
        "quiet_host": True,
        "configuration": config, "configuration_sha256": shared.configuration_hash(config),
        "frozen": initial["assets"], "sources": initial["sources"], "artifacts_before": initial,
        "protocol": {"path": "protocol.md", "sha256": protocol_sha},
        "shards": [{"index": i, "protocol_id": profile(i).protocol_id, "seed": SEEDS[i-1],
                    "path": f"shard-{i}", "openings": initial["assets"][f"openings_{i}"]}
                   for i in range(1, SHARDS + 1)],
        "resource_history": {"path": "resource-history.jsonl", "observations": 0, "sha256": None},
        "clock_smoke": smoke_record(initial)}
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

        async def capture_smoke_resources():
            async with observations:
                path = output/"clock-smoke"/"resource-history.jsonl"
                def capture():
                    journal.flush()
                    with path.open("xb") as stream:
                        stream.write(journal_path.read_bytes())
                    return {"path": "clock-smoke/resource-history.jsonl", "sha256": match.sha256(path),
                            "observations": record["resource_history"]["observations"]}
                return await shared.disk_io(capture)

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
            # Child readiness may cross the admission endpoint after the
            # parent's check. Reject that launch, while preserving the parent's
            # cutoff for every child that did begin within its allowed window.
            current = launch_policy(utc_now(), allow_daytime=allow_daytime, require_window=True)
            current.update(cutoff_utc=policy["cutoff_utc"], cutoff_local=policy["cutoff_local"],
                           remaining_seconds=(cutoff - utc_now()).total_seconds(),
                           daytime_authorization=policy["daytime_authorization"])
            return current

        async def worker(index):
            admitted = False
            async def cached_preflight():
                return await shared.disk_io(child_report, record, index)
            async def before_game(game_id):
                nonlocal admitted
                await guard(game_id, index)
                if not admitted:
                    now = utc_now()
                    if now >= cutoff:
                        raise shared.WindowExpired("Original Helsinki cutoff elapsed before held-out admission")
                    launch_policy(now, allow_daytime=allow_daytime, require_window=True)
                    admitted = True
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
            supervisors = [asyncio.create_task(monitor()), asyncio.create_task(deadline())]
            smoke_task = asyncio.create_task(run_smoke(output, record, guard, child_window,
                                                       capture_smoke_resources, allow_daytime=allow_daytime),
                                             name="phase4f13-clock-smoke")
            tasks = [smoke_task, *supervisors]
            async def supervise(owned):
                pending = set([*owned, *supervisors])
                while any(not task.done() for task in owned):
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                for task in owned:
                    task.result()
            await supervise([smoke_task])
            # Only a completely audited and cleaned smoke stage may admit a
            # held-out game; the original launch endpoint and cutoff still apply.
            if record["clock_smoke"]["status"] != "passed":
                raise ValueError("Clock smoke gate did not pass")
            launch_policy(utc_now(), allow_daytime=allow_daytime, require_window=True)
            workers = [asyncio.create_task(worker(i), name=f"phase4f13-shard-{i}")
                       for i in range(1, SHARDS + 1)]
            tasks.extend(workers)
            await supervise(workers)
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
    parser.add_argument("--quiet-host", action="store_true",
                        help="Confirm LM Studio inference paused, AC/Automatic mode, and Mac kept awake")
    parser.add_argument("--allow-daytime", action="store_true",
                        help="Use only the frozen October 30 daytime amendment and October 31 07:00 cutoff")
    args = parser.parse_args(argv)
    if args.action == "check" and args.output is not None:
        parser.error("check does not accept --output")
    if args.action == "run" and args.output is None:
        parser.error("run requires --output NEW_DIRECTORY")
    if args.action == "check" and args.quiet_host:
        parser.error("--quiet-host is for run only; check does not start searches")
    if args.action == "run" and not args.quiet_host:
        parser.error("run requires fresh --quiet-host confirmation")
    async def execute():
        # All coordinated hashing uses one background worker, not four more
        # unbounded CPU jobs alongside the four active engine search workers.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        return await cooperative_signals(check(allow_daytime=args.allow_daytime) if args.action == "check"
                                         else run(args.output, quiet_host=args.quiet_host,
                                                  allow_daytime=args.allow_daytime))
    try:
        print(json.dumps(asyncio.run(execute()), indent=2, allow_nan=False))
        return 0
    except shared.WindowExpired:
        print("Phase 4F.13 qualification stopped at its original cutoff; incomplete evidence retained.", file=sys.stderr)
        return 124
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Phase 4F.13 qualification interrupted; cleanup completed and available evidence retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TimeoutError, match.chess.engine.EngineError) as error:
        print(f"Phase 4F.13 qualification check/run failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
