#!/usr/bin/env python3
"""Check or run the fixed Phase 2D time-policy qualification, once, in foreground.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Checking never searches an opening. Running requires a new campaign directory
and the Helsinki night window, unless the owner explicitly authorizes the
--allow-daytime exception. Every run stops at the next Helsinki 07:00, retaining
incomplete evidence and waiting for child cleanup. No scheduling or resumption.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, time, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
from zoneinfo import ZoneInfo

import match

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase2d-time-policy-64-v1"
CHESS_VERSION = "1.11.2"
PAIRS = 32
SEED = 20261014
FROZEN = {
    "engine": (ROOT / "build/experiments/time-policy-hard-20261014/chess0live",
               "cafaa3ae3e6500d75382b3cf943ebc23d2d154247bc18ac3b3254d206619a80c"),
    "network": (ROOT / "networks/nn-1a298aa575a0.nnue",
                "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"),
    "openings": (ROOT / "tests/data/openings-time-validation.json",
                 "163bf4c34547a838c35e03103401c40d448a2f78c535254bf3727913b007b95b"),
}
SOURCES = ("tools/qualify_time_policy.py", "tools/match.py", "tools/match_statistics.py",
           "tools/resources.py", "tools/audit_time_policy.py", "requirements-match.txt",
           "docs/TIME_MANAGEMENT.md", "docs/PHASE_2D.md")


class WindowExpired(TimeoutError):
    """The predeclared wall-clock cutoff interrupted the fixed sample."""


def utc_now():
    return datetime.now(timezone.utc)


def launch_policy(now=None, allow_daytime=False, require_window=False):
    """Use civil Helsinki boundaries, but subtract UTC instants across DST.

    The explicit exception changes only permission to launch during daytime;
    it neither increases the resource budget nor removes the next-07:00 cutoff.
    """
    now = now or utc_now()
    if now.tzinfo is None:
        raise ValueError("The launch clock must be timezone-aware")
    local = now.astimezone(ZoneInfo("Europe/Helsinki"))
    night = local.hour >= 23 or local.hour < 7
    if require_window and not night and not allow_daytime:
        raise ValueError("Run requires 23:00–07:00 Europe/Helsinki; --allow-daytime requires explicit owner authorization")
    end_date = local.date() + timedelta(days=int(local.hour >= 7))
    cutoff = datetime.combine(end_date, time(7), tzinfo=local.tzinfo)
    cutoff_utc = cutoff.astimezone(timezone.utc)
    return {"timezone": "Europe/Helsinki", "local_time": local.isoformat(),
            "nighttime": night, "allow_daytime": allow_daytime,
            "cutoff_local": cutoff.isoformat(), "cutoff_utc": cutoff_utc.isoformat(),
            "remaining_seconds": (cutoff_utc - now.astimezone(timezone.utc)).total_seconds()}


def fixed_request():
    """One predeclared comparison; there are deliberately no tuning arguments."""
    settings = match.Settings(initial=60.0, increment=0.6, hash_mb=64, threads=1,
                              max_plies=512, startup_timeout=30.0,
                              protocol_timeout=5.0, move_overhead_ms=20, smoke=False)
    specs = [match.EngineSpec(role, FROZEN["engine"][0].resolve(), FROZEN["network"][0].resolve(),
                             source_revision=revision, extra_options=(("Time Policy", policy),))
             for role, policy, revision in (
                 ("candidate", "forecast", "phase2-hard-forecast-cafaa3a"),
                 ("opponent", "classic", "phase2-classic-cafaa3a"))]
    return specs, settings


def configuration(specs, settings):
    return {"pairs": PAIRS, "seed": SEED, "settings": vars(settings).copy(),
            "engines": [{"role": spec.role, "executable": str(spec.executable),
                         "network": str(spec.network), "network_option": spec.network_option,
                         "arguments": list(spec.arguments), "source_revision": spec.source_revision,
                         "extra_options": dict(spec.extra_options)} for spec in specs],
            "ponder": False, "diagnostics": False}


def configuration_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def snapshot():
    """Reject asset drift; freeze launcher, runner, audit, and protocol sources."""
    assets = {}
    for name, (path, expected) in FROZEN.items():
        actual = match.sha256(path)
        if actual != expected:
            raise ValueError(f"Frozen {name} SHA-256 mismatch: {path}")
        assets[name] = {"path": str(path.resolve()), "sha256": actual, "bytes": path.stat().st_size}
    sources = {name: {"sha256": match.sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in SOURCES}
    return {"assets": assets, "sources": sources}


def validate_options(protocol, configured, spec, settings):
    """Require the frozen engine's relevant option types and safe defaults.

    Ponder is managed by python-chess and play(..., ponder=False), rather than
    manually configured. Its false default is still mandatory in this check.
    """
    expected_types = {"Hash": "spin", "Threads": "spin", "EvalFile": "string",
                      "Move Overhead": "spin", "Ponder": "check",
                      "Time Policy": "combo", "Search Diagnostics": "check"}
    for name, kind in expected_types.items():
        if name not in protocol.options or protocol.options[name].type != kind:
            raise ValueError(f"{spec.role}: missing or wrong UCI option type for {name}")
    for name in ("Ponder", "Search Diagnostics"):
        if protocol.options[name].default is not False:
            raise ValueError(f"{spec.role}: {name} must default to false")
    policy = protocol.options["Time Policy"]
    if policy.default != "classic" or set(policy.var or ()) != {"classic", "forecast"}:
        raise ValueError(f"{spec.role}: incompatible Time Policy choices/default")
    expected = {"Hash": settings.hash_mb, "Threads": settings.threads,
                "EvalFile": str(spec.network), "Move Overhead": settings.move_overhead_ms,
                "Search Diagnostics": False, "Time Policy": dict(spec.extra_options)["Time Policy"]}
    for name, value in expected.items():
        if configured.get(name) != value:
            raise ValueError(f"{spec.role}: configured {name} differs from the frozen protocol")


async def check():
    """Inspect held-out roots only with the referee; no position/go is sent."""
    if match.chess.__version__ != CHESS_VERSION:
        raise ValueError(f"Qualification requires chess=={CHESS_VERSION}")
    specs, settings = fixed_request()
    settings.validate()
    frozen = snapshot()
    _, openings = match.read_openings(FROZEN["openings"][0])
    roots = {" ".join(opening.board.fen(en_passant="legal").split()[:4]) for opening in openings}
    if len(openings) != PAIRS or len(roots) != PAIRS:
        raise ValueError("Qualification requires exactly 32 distinct, legal, nonterminal roots")
    resource_policy = match.resource_check(settings, specs)
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
    if snapshot() != frozen:
        raise ValueError("Frozen inputs or tool sources changed during preflight")
    config = configuration(specs, settings)
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "status": "checked",
            "checked_utc": utc_now().isoformat(), "configuration": config,
            "configuration_sha256": configuration_hash(config), **frozen,
            "platform": platform.platform(), "machine": platform.machine(),
            "python": sys.version, "chess_version": match.chess.__version__,
            "preflight": {"opening_count": len(openings), "distinct_roots": len(roots),
                          "resource_policy": resource_policy, "engines": engines},
            "launch_policy": launch_policy()}


def verify_unchanged(report, specs, settings):
    current = snapshot()
    current["configuration_sha256"] = configuration_hash(configuration(specs, settings))
    current["unchanged"] = (current["assets"] == report["assets"]
                            and current["sources"] == report["sources"]
                            and current["configuration_sha256"] == report["configuration_sha256"])
    if not current["unchanged"]:
        raise ValueError("Qualification assets, sources, or settings changed")
    return current


async def run(output, allow_daytime=False):
    """Run once with deadline cancellation; match.py owns process cleanup/PGNs."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Campaign output must be a new directory; overwrite/resume is disabled")
    initial_policy = launch_policy(allow_daytime=allow_daytime, require_window=True)
    report = await check()
    # Readiness can cross 07:00. Re-evaluate permission and deadline afterwards.
    policy = launch_policy(allow_daytime=allow_daytime, require_window=True)
    initial_cutoff = datetime.fromisoformat(initial_policy["cutoff_utc"])
    remaining = (initial_cutoff - utc_now()).total_seconds()
    if remaining <= 0:
        raise ValueError("The initial Helsinki 07:00 cutoff elapsed during preflight")
    policy.update(cutoff_local=initial_policy["cutoff_local"], cutoff_utc=initial_policy["cutoff_utc"],
                  remaining_seconds=remaining)
    specs, settings = fixed_request()
    verify_unchanged(report, specs, settings)
    match.resource_check(settings, specs)
    output.mkdir(parents=True, exist_ok=False)
    protocol_source = ROOT / "docs/PHASE_2D.md"
    (output / "protocol.md").write_bytes(protocol_source.read_bytes())
    protocol_sha = match.sha256(output / "protocol.md")
    if protocol_sha != report["sources"]["docs/PHASE_2D.md"]["sha256"]:
        raise ValueError("Predeclared protocol changed before it could be frozen")
    report.update(status="running", started_utc=utc_now().isoformat(),
                  launch_policy=policy, match_directory="match",
                  protocol_document={"source": "docs/PHASE_2D.md", "frozen_copy": "protocol.md",
                                     "sha256": protocol_sha})
    match.atomic_json(output / "launch.json", report)
    try:
        # wait_for cancels the runner and awaits its finally blocks: the current
        # game, journal and incomplete summary are saved before processes close.
        # Cleanup may finish just after the cutoff; no new game is then started.
        remaining = (datetime.fromisoformat(policy["cutoff_utc"]) - utc_now()).total_seconds()
        if remaining <= 0:
            raise asyncio.TimeoutError("The overnight window ended before match startup")
        result = await asyncio.wait_for(match.run_match(
            specs, settings, FROZEN["openings"][0], output / "match", PAIRS, SEED), remaining)
        if not result.get("experiment_complete"):
            raise ValueError("The fixed qualification sample did not complete")
        report.update(status="finished", match_summary=result)
    except asyncio.TimeoutError as error:
        report.update(status="interrupted", error="Helsinki 07:00 cutoff; fixed sample incomplete")
        raise WindowExpired(report["error"]) from error
    except asyncio.CancelledError:
        report.update(status="interrupted", error="Launcher cancelled; fixed sample incomplete")
        raise
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        try:
            report["integrity_after"] = verify_unchanged(report, specs, settings)
        except (ValueError, OSError) as error:
            report.update(status="invalidated", integrity_after={"unchanged": False, "error": str(error)})
            raise
        finally:
            report["finished_utc"] = utc_now().isoformat()
            match.atomic_json(output / "launch.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run"), nargs="?", default="check")
    parser.add_argument("--output", type=Path, help="New campaign directory, required for run")
    parser.add_argument("--allow-daytime", action="store_true",
                        help="Explicit owner-authorized daytime launch; retains resource policy and next-07:00 cutoff")
    args = parser.parse_args(argv)
    if args.action == "check" and (args.output is not None or args.allow_daytime):
        parser.error("check does not accept --output or --allow-daytime")
    if args.action == "run" and args.output is None:
        parser.error("run requires --output NEW_DIRECTORY")
    try:
        result = asyncio.run(check() if args.action == "check" else run(args.output, args.allow_daytime))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except WindowExpired:
        print("Qualification stopped at the overnight cutoff; incomplete evidence retained.", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print("Qualification interrupted; available evidence retained.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TimeoutError, match.chess.engine.EngineError) as error:
        print(f"Qualification check/run failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
