#!/usr/bin/env python3
"""Check or supervise the fixed four-shard Phase 3G LMR screen.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One foreground invocation, one fresh directory, one fixed Helsinki cutoff.
The owner-authorized October 18 daytime exception requires an explicit flag;
there is no schedule, resumption, resource-budget increase, or parameter tuning.
Checks use only referee replay and two serial UCI handshakes, without searches.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import io
import json
from pathlib import Path
import signal
import sys
import time

import match
import qualification as shared

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase3g-lmr-512-v2"
DAYTIME_DATE = "2026-10-18"
DAYTIME_AUTHORIZATION = "owner-20261018-phase3g"
PROTOCOL_DOCUMENT = "docs/PHASE_3G.md"
CHESS_VERSION = "1.11.2"
SHARDS, SHARD_PAIRS, PAIRS = 4, 64, 256
SEEDS = (202610181, 202610182, 202610183, 202610184)
POLL_SECONDS = 1.0
MAX_RESOURCE_GAP_SECONDS = 5.0
SUITE_HASHES = ("e40da564ea899dacdbfce4ab2fc92fb0caf42c14d630de1a065d7cf75f822b97",
                "6ea77165730e2aa5d5d9243649af6297fe3683877ca2736c5c119e6deed6c7d2",
                "3de297a67e0423299b715e7ce7c71102317277fc627ce52d0fef13ed6f7ae2c9",
                "7a2670d433329dc46e6536202c2a87e964d00dcb5683123a3ca563979da2efe1")
FROZEN = {
    "engine": (ROOT / "build/experiments/phase3g-20261018/chess0live",
               "edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b"),
    "network": (ROOT / "networks/nn-1a298aa575a0.nnue",
                "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"),
    **{f"openings_{index}": (ROOT / f"tests/data/openings-phase3g-{index}.json", digest)
       for index, digest in enumerate(SUITE_HASHES, 1)},
}
PREVIOUS_SUITES = ("tests/data/openings-development.json", "tests/data/openings-validation.json",
                   "tests/data/openings-time-validation.json", "tests/data/openings-lmr-validation.json")
GAME_PHASE_SUITE = "tests/data/performance-gamephases.json"
SOURCES = ("tools/qualify_phase3g.py", "tools/audit_phase3g.py", "tools/generate_phase3g_openings.py",
           "tests/phase3g_openings_test.py",
           "tools/qualification.py", "tools/match.py", "tools/audit_time_policy.py",
           "tools/match_statistics.py", "tools/resources.py", "requirements-match.txt",
           PROTOCOL_DOCUMENT, "tests/data/openings-phase3g-generation.json", *PREVIOUS_SUITES, GAME_PHASE_SUITE)
ROLE_OPTIONS = ((("Time Policy", "classic"), ("Capture Ordering", "mvv-lva"), ("Late Move Reductions", "true")),
                (("Time Policy", "classic"), ("Capture Ordering", "mvv-lva"), ("Late Move Reductions", "false")))
REVISIONS = ("phase3g-lmr-on-500b022", "phase3g-lmr-off-500b022")
utc_now = shared.utc_now


def profile(index):
    if type(index) is not int or not 1 <= index <= SHARDS:
        raise ValueError("Shard index must be 1 through 4")
    frozen = {"engine": FROZEN["engine"], "network": FROZEN["network"],
              "openings": FROZEN[f"openings_{index}"]}
    return shared.QualificationProfile(ROOT, f"{PROTOCOL_ID}-shard-{index}", CHESS_VERSION,
        SHARD_PAIRS, SEEDS[index - 1], frozen, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS,
        REVISIONS, ("Late Move Reductions",))


def fixed_request():
    return shared.fixed_request(profile(1))


def configuration():
    specs, settings = fixed_request()
    common = shared.configuration(profile(1), specs, settings)
    return {"settings": common["settings"], "pairs": PAIRS, "games": PAIRS * 2,
            "shards": SHARDS, "shard_pairs": SHARD_PAIRS, "active_search_workers": SHARDS,
            "resident_engines": SHARDS * 2, "resource_poll_seconds": POLL_SECONDS,
            "max_resource_gap_seconds": MAX_RESOURCE_GAP_SECONDS,
            "seeds": list(SEEDS), "engines": common["engines"], "ponder": False, "diagnostics": False}


def snapshot():
    master = shared.QualificationProfile(ROOT, PROTOCOL_ID, CHESS_VERSION, PAIRS, 0,
        FROZEN, SOURCES, PROTOCOL_DOCUMENT, ROLE_OPTIONS, REVISIONS)
    return shared.snapshot(master)


def fingerprints():
    """Catch input replacement or in-place modification without hashing in a live clock loop."""
    paths = {path.resolve() for path, _ in FROZEN.values()} | {(ROOT / name).resolve() for name in SOURCES}
    return {str(path): (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            for path in paths for stat in (path.stat(),)}


def launch_policy(now=None, *, require_window=False, allow_daytime=False):
    """Apply the single dated owner exception without widening resource limits.

    Normal launches retain the original fifteen-minute night window. The
    exception is opt-in and valid only during the authorized date's daytime;
    the same next-07:00 cutoff is captured before any readiness work.
    """
    now = now or utc_now()
    policy = shared.launch_policy(now, allow_daytime=allow_daytime)
    local = datetime.fromisoformat(policy["local_time"])
    if allow_daytime:
        permitted = local.date().isoformat() == DAYTIME_DATE and 7 <= local.hour < 23
        window = "2026-10-18 07:00–23:00 Europe/Helsinki (owner exception)"
    else:
        permitted = local.hour == 23 and local.minute < 15
        window = "23:00–23:15 Europe/Helsinki"
    if require_window and not permitted:
        raise ValueError(f"Phase 3G may launch only {window} (end exclusive)")
    policy.update(launch_window=window, launch_permitted=permitted,
                  daytime_authorization=DAYTIME_AUTHORIZATION if allow_daytime else None)
    return policy


def root_key(board):
    return " ".join(board.fen(en_passant="legal").split()[:4])


def opening_check():
    """Inspect all histories before any engine starts; no evaluation-based selection."""
    roots, identifiers = set(), set()
    for index in range(1, SHARDS + 1):
        _, openings = match.read_openings(FROZEN[f"openings_{index}"][0])
        if len(openings) != SHARD_PAIRS:
            raise ValueError("Each Phase 3G shard requires exactly 64 openings")
        for opening in openings:
            key = root_key(opening.board)
            if key in roots or opening.identifier in identifiers:
                raise ValueError("Duplicate global opening root or identifier")
            if opening.board.root().fen() != match.chess.STARTING_FEN or not opening.board.move_stack:
                raise ValueError("Every Phase 3G opening requires a full nonempty start-position history")
            roots.add(key)
            identifiers.add(opening.identifier)
    previous = {root_key(opening.board) for name in PREVIOUS_SUITES
                for opening in match.read_openings(ROOT / name)[1]}
    phases = {root_key(opening.board) for opening in match.read_openings(ROOT / GAME_PHASE_SUITE)[1]}
    if roots & (previous | phases):
        raise ValueError("New opening roots overlap previously exposed positions")
    return {"opening_count": PAIRS, "distinct_roots": len(roots),
            "previous_root_count": len(previous), "game_phase_root_count": len(phases)}


def resource_policy():
    """Conservatively reserve all four shards until shutdown, even after a shard finishes."""
    specs, settings = fixed_request()
    policy = dict(match.current_budget())
    one = 2 * settings.hash_mb * 1024**2 + 4 * sum(spec.network.stat().st_size for spec in specs) + 256 * 1024**2
    memory = match.physical_memory()
    policy.update(active_search_workers=SHARDS, resident_engines=SHARDS * 2,
                  estimated_memory_bytes=SHARDS * one, physical_memory_bytes=memory,
                  memory_estimate_is_hard_cap=False)
    allowed = (SHARDS <= policy["max_cpu_workers"] and memory is not None and memory > 0
               and SHARDS * one <= memory * policy["memory_fraction"])
    return policy, allowed


def validate_options(protocol, configured, spec, settings):
    shared.validate_options(profile(1), protocol, configured, spec, settings)
    ordering = protocol.options.get("Capture Ordering")
    if (ordering is None or ordering.type != "combo" or ordering.default != "mvv-lva"
            or set(ordering.var or ()) != {"mvv-lva", "see"}):
        raise ValueError("Capture Ordering choices/default must match the frozen Phase 3F binary")


async def check():
    """Any-time serial two-role handshake; no position or go command is sent."""
    if match.chess.__version__ != CHESS_VERSION:
        raise ValueError(f"Qualification requires chess=={CHESS_VERSION}")
    initial = snapshot()
    details = opening_check()
    policy, allowed = resource_policy()
    if not allowed:
        raise ValueError("Aggregate four-worker/eight-engine resource budget is insufficient")
    specs, settings = fixed_request()
    settings.validate()
    engines = []
    for spec in specs:
        log = io.StringIO()
        transport, protocol, configured = await match.start_engine(spec, settings, log)
        try:
            validate_options(protocol, configured, spec, settings)
            engines.append({"role": spec.role, "id": dict(protocol.id),
                "options": {name: vars(option).copy() for name, option in protocol.options.items()},
                "configured": configured})
        finally:
            await match.close_engine(transport, protocol)
        engines[-1]["transcript"] = [json.loads(line) for line in log.getvalue().splitlines()]
    if snapshot() != initial:
        raise ValueError("Frozen inputs or sources changed during preflight")
    config = configuration()
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "status": "checked",
            "checked_utc": utc_now().isoformat(), "configuration": config,
            "configuration_sha256": shared.configuration_hash(config),
            "frozen": initial["assets"], "sources": initial["sources"],
            "artifacts_before": initial, "launch_policy": launch_policy(),
            "preflight": {**details, "engines": engines, "resource_policy": policy}}


def child_report(master, index):
    specs, settings = fixed_request()
    config = shared.configuration(profile(index), specs, settings)
    assets = master["frozen"]
    return {"schema_version": 1, "protocol_id": profile(index).protocol_id, "status": "checked",
            "checked_utc": master["checked_utc"], "configuration": config,
            "configuration_sha256": shared.configuration_hash(config),
            "assets": {"engine": assets["engine"], "network": assets["network"],
                       "openings": assets[f"openings_{index}"]}, "sources": master["sources"],
            "chess_version": CHESS_VERSION,
            "preflight": {"opening_count": SHARD_PAIRS, "distinct_roots": SHARD_PAIRS,
                          "engines": deepcopy(master["preflight"]["engines"]),
                          "resource_policy": master["preflight"]["resource_policy"]}}


async def cancel_and_wait(tasks):
    """Cancel each child at most once, then await its game and process cleanup."""
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def run(output, allow_daytime=False):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Campaign output must be a new directory; overwrite/resume is disabled")
    started = utc_now()
    policy = launch_policy(started, require_window=True, allow_daytime=allow_daytime)
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
        def observe(trigger, **identity):
            budget, allowed = resource_policy()
            event = {"observed_utc": utc_now().isoformat(), "trigger": trigger,
                     "policy": budget, "within_limits": allowed, **identity}
            journal.write(json.dumps(event, allow_nan=False) + "\n")
            journal.flush()
            record["resource_history"]["observations"] += 1
            return allowed

        async def guard(game_id=None, index=None, trigger="before_game"):
            if utc_now() >= cutoff:
                raise shared.WindowExpired("Helsinki 07:00 cutoff; fixed sample incomplete")
            if fingerprints() != metadata:
                raise ValueError("Frozen artifact or source metadata changed during campaign")
            identity = {} if index is None else {"shard_index": index, "game_id": game_id}
            if not observe(trigger, **identity):
                raise ValueError("Aggregate four-worker/eight-engine resource budget became insufficient")

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
            current = shared.launch_policy(utc_now(), allow_daytime=allow_daytime)
            current.update(cutoff_utc=policy["cutoff_utc"], cutoff_local=policy["cutoff_local"],
                           remaining_seconds=(cutoff - utc_now()).total_seconds(),
                           daytime_authorization=policy["daytime_authorization"])
            return current

        async def worker(index):
            async def cached_preflight():
                return child_report(record, index)
            async def before_game(game_id):
                await guard(game_id, index)
            return await shared.run(profile(index), output / f"shard-{index}", allow_daytime=allow_daytime,
                preflight=cached_preflight, request=fixed_request, clock=utc_now, window=child_window,
                run_guard=before_game, fail_fast=True, manage_deadline=False)

        match.atomic_json(output / "campaign.json", record)
        try:
            if not observe("initial"):
                raise ValueError("Aggregate four-worker/eight-engine resource budget is insufficient")
            checked = await check()
            if checked["artifacts_before"] != initial or fingerprints() != metadata:
                raise ValueError("Frozen campaign inputs changed during preflight")
            record.update(checked_utc=checked["checked_utc"], preflight=checked["preflight"])
            if utc_now() >= cutoff:
                raise shared.WindowExpired("Initial Helsinki cutoff elapsed during preflight")
            match.atomic_json(output / "campaign.json", record)
            workers = [asyncio.create_task(worker(i), name=f"phase3g-shard-{i}")
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
                    if not observe("final") and record["status"] == "finished":
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


async def cooperative_signals(coroutine):
    """First SIGINT/SIGTERM cancels; repeated signals never interrupt cleanup."""
    task = asyncio.create_task(coroutine)
    loop = asyncio.get_running_loop()
    received = []
    previous, loop_handlers = {}, set()
    def stop(signum):
        if not received:
            received.append(signum)
            if not task.done():
                task.cancel()
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        try:
            loop.add_signal_handler(signum, stop, signum)
            loop_handlers.add(signum)
        except NotImplementedError:
            signal.signal(signum, lambda value, _frame: loop.call_soon_threadsafe(stop, value))
    try:
        return await task
    finally:
        for signum, handler in previous.items():
            if signum in loop_handlers:
                loop.remove_signal_handler(signum)
            signal.signal(signum, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run"), nargs="?", default="check")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-daytime", action="store_true",
                        help="Owner-authorized October 18 daytime launch only; retains resource policy and next-07:00 cutoff")
    args = parser.parse_args(argv)
    if args.action == "check" and (args.output is not None or args.allow_daytime):
        parser.error("check does not accept --output or --allow-daytime")
    if args.action == "run" and args.output is None:
        parser.error("run requires --output NEW_DIRECTORY")
    async def execute():
        # All coordinated hashing uses one background worker, not four more
        # unbounded CPU jobs alongside the four active engine search workers.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        return await cooperative_signals(check() if args.action == "check" else run(args.output, args.allow_daytime))
    try:
        print(json.dumps(asyncio.run(execute()), indent=2, allow_nan=False))
        return 0
    except shared.WindowExpired:
        print("Phase 3G stopped at its original cutoff; incomplete evidence retained.", file=sys.stderr)
        return 124
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Phase 3G interrupted; cleanup completed and available evidence retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TimeoutError, match.chess.engine.EngineError) as error:
        print(f"Phase 3G check/run failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
