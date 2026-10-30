#!/usr/bin/env python3
"""Independently audit the fixed Phase 4F.13 NNUE efficiency qualification.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

A separately versioned raw-game auditor verifies PGNs, UCI clocks and saved
legacy summaries; the aggregate applies the new prospective paired interval. This file independently declares the current experiment and checks
all four shards together. It never imports launcher configuration or changes
any frozen historical module globals. No automatic default promotion.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
from zoneinfo import ZoneInfo

from tooling import direct_entry

if __name__ == "__main__":
    direct_entry(__file__)

import chess
import chess.pgn
import audit_phase4f13_games as child_auditor
import paired_betting
from audit_phase3l import definitions, instant, root_key

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase4f13-nnue-2048-v1"
PROTOCOL_DOCUMENT = "docs/experiments/phase4f13-match.md"
ENGINE_SHA256 = {
    "candidate": "04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594",
    "opponent": "8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc",
}
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
PIN_FILE = "tests/data/phase4f13-match-pins.json"
GENERATION_METADATA = "tests/data/phase4f13-match-generation.json"
EXCLUSIONS = "tests/data/phase4f13-match-exclusions.json"
GENERATOR = "tools/generate_phase4f13_openings.py"
BUILD_ROOTS = {"candidate": "build/experiments/phase4f12/candidate", "opponent": "build/experiments/phase4f12/baseline"}
BUILD_MANIFESTS = {role: path + "/manifest.json" for role, path in BUILD_ROOTS.items()}
# Previously accepted Phase 4F.12 provenance bytes, independently anchored
# before generating the new match pins; preparation cannot rewrite this history.
BUILD_MANIFEST_SHA256 = {
    "candidate": "5ac36545a2acfb4503aa542c836441e762a533f0ff1a81b14c6cd0b18a5225b3",
    "opponent": "946b1904b2621aac8ce8d8ffc1bdbbea366033b90faac668319457c0db279247",
}
ORIGIN_MANIFESTS = {role: path + "/origin-manifest.json" for role, path in BUILD_ROOTS.items()}
BUILD_LOGS = {role: path + "/build.log" for role, path in BUILD_ROOTS.items()}
FROZEN_ENGINES = {role: path + "/chess0live" for role, path in BUILD_ROOTS.items()}
COMPILE_FLAGS = "-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g"



def unique_object(pairs):
    """Reject ambiguous pin/provenance JSON instead of keeping its last key."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate preparation JSON key: " + name)
        result[name] = value
    return result


def input_pins():
    """Expect the committed preparation schema, independently of the launcher."""
    document = json.loads((ROOT / PIN_FILE).read_text(), object_pairs_hook=unique_object)
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


def opening_sha256():
    pins = input_pins()
    return tuple(pins[f"tests/data/phase4f13-match-{i:02d}.json"] for i in range(1, 5))


SHARDS, SHARD_PAIRS, PAIRS = 4, 256, 1024
SMOKE_PAIRS, SMOKE_TIMEOUT_SECONDS = 4, 600.0
SMOKE_SEEDS = tuple(range(202610304151, 202610304155))
SMOKE_DEVELOPMENT_IDS = ("development-01", "development-05", "development-08", "development-09")
SMOKE_CATALOG = "tests/data/openings-development.json"
SEEDS = tuple(range(202610304131, 202610304135))
SETTINGS = {"initial": 15.0, "increment": 0.15, "hash_mb": 64, "threads": 1,
            "max_plies": 512, "startup_timeout": 30.0, "protocol_timeout": 5.0,
            "move_overhead_ms": 20, "smoke": False}
CHECK_OPTIONS = ("Late Move Reductions", "Deep Quiet Reductions", "Countermove Ordering",
                 "Null Move Pruning", "Reverse Futility Pruning", "QSearch SEE Pruning", "ProbCut", "TT Move Hints", "Continuation History")
ROLE_OPTIONS = {
    role: {"Time Policy": "classic", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
           "Capture Ordering": "mvv-lva",
           **{name: "true" if name == "Late Move Reductions" else "false" for name in CHECK_OPTIONS}}
    for role in ("candidate", "opponent")
}
ROLE_REVISIONS = {"candidate": "3ee5eff30981b73099e8a118ff1712f89cdc285a",
                  "opponent": "1ca87d6a596531d19b7b698b84c171fc314fc046"}


def expected_options(role, network):
    return {"Hash": 64, "Threads": 1, "Move Overhead": 20, "Search Diagnostics": False,
            "EvalFile": str(network), "SyzygyPath": "",
            **{name: value == "true" if name in CHECK_OPTIONS else int(value) if name in ("SyzygyProbeLimit", "SyzygyProbeDepth") else value
               for name, value in ROLE_OPTIONS[role].items()}}


BUILD_SOURCE_SUFFIXES = (
    'Makefile',
    'include/chess0live/detail/continuation_history.hpp',
    'include/chess0live/detail/move_hint_entry.hpp',
    'include/chess0live/detail/transposition_entry.hpp',
    'include/chess0live/exchange.hpp',
    'include/chess0live/nnue.hpp',
    'include/chess0live/position.hpp',
    'include/chess0live/search.hpp',
    'include/chess0live/search_policy.hpp',
    'include/chess0live/tablebase.hpp',
    'include/chess0live/time_management.hpp',
    'include/chess0live/types.hpp',
    'src/exchange.cpp',
    'src/main.cpp',
    'src/nnue.cpp',
    'src/position.cpp',
    'src/search.cpp',
    'src/tablebase.cpp',
    'third_party/fathom/src/stdendian.h',
    'third_party/fathom/src/tbchess.c',
    'third_party/fathom/src/tbconfig.h',
    'third_party/fathom/src/tbprobe.c',
    'third_party/fathom/src/tbprobe.h',
)
BUILD_SOURCE_NAMES = tuple(
    BUILD_ROOTS[role] + "/source/" + suffix
    for role in ("candidate", "opponent")
    for suffix in (*BUILD_SOURCE_SUFFIXES, "tests/nnue_features_test.cpp" if role == "candidate" else "networks/manifest.json"))

REQUIRED_SOURCES = (
    "tools/qualify_phase4f13.py", "tools/audit_phase4f13.py", "tools/qualification.py",
    "tools/qualify_phase3l.py", "tools/audit_phase3l.py", "tools/audit_time_policy.py", "tools/audit_phase4f13_games.py", "tools/paired_betting.py", "tests/paired_betting_test.py",
    "tools/match.py", "tools/match_statistics.py", "tools/resources.py", GENERATOR,
    "tools/generate_phase4d2_openings.py", "tools/generate_readiness_openings.py",
    "tests/phase4f13_openings_test.py", "tests/qualify_phase4f13_test.py", "tests/audit_phase4f13_test.py",
    GENERATION_METADATA, EXCLUSIONS, *BUILD_MANIFESTS.values(), *ORIGIN_MANIFESTS.values(), *BUILD_LOGS.values(), "requirements-match.txt", PROTOCOL_DOCUMENT,
    PIN_FILE, "tests/data/phase4f3-puzzles.json", "tools/generate_lmr_20261022_openings.py",
    "tools/run.py", "tools/tooling.py", "tools/python-packages.json",
    "tests/data/phase4d2-exclusions.json", "tests/match_test.py",
    SMOKE_CATALOG,
    *(f"tests/data/phase4f13-match-smoke-{i:02d}.json" for i in range(1, 5)),
    *BUILD_SOURCE_NAMES,
    *(f"tests/data/phase4f13-match-{i:02d}.json" for i in range(1, 5)))
PINNED_INPUTS = tuple(name for name in REQUIRED_SOURCES if name != PIN_FILE)
FAILURES = (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError, AttributeError)
require = child_auditor.require


def option_architecture():
    """Declare the pinned executable's complete UCI interface independently."""
    return {
        **{name: {"type": "check", "default": name == "Late Move Reductions"}
           for name in ("Ponder", "Search Diagnostics", *CHECK_OPTIONS)},
        **{name: {"type": "spin", "default": default, "min": low, "max": high}
           for name, default, low, high in (("Hash", 64, 1, 16384), ("Threads", 1, 1, 64),
                                            ("Move Overhead", 20, 0, 5000),
                                            ("SyzygyProbeLimit", 7, 0, 7),
                                            ("SyzygyProbeDepth", 1, 1, 128))},
        "Clear Hash": {"type": "button"},
        "EvalFile": {"type": "string", "default": "nn-1a298aa575a0.nnue"},
        "SyzygyPath": {"type": "string", "default": "<empty>"},
        "Time Policy": {"type": "combo", "default": "classic", "var": ["classic", "forecast", "bounded"]},
        "Capture Ordering": {"type": "combo", "default": "mvv-lva", "var": ["mvv-lva", "see"]},
    }


def option_declaration(name, schema):
    """Canonical raw declaration: check metadata against the actual handshake."""
    line = f"option name {name} type {schema['type']}"
    if "default" in schema:
        value = schema["default"]
        line += " default " + (str(value).lower() if type(value) is bool else str(value))
    for field in ("min", "max"):
        if field in schema:
            line += f" {field} {schema[field]}"
    for value in schema.get("var", ()):
        line += " var " + value
    return line


def validate_build_provenance(sources):
    """Independently bind both role binaries to exact preserved build inventories."""
    for role, folder in BUILD_ROOTS.items():
        require(child_auditor.digest(ROOT / BUILD_MANIFESTS[role]) == BUILD_MANIFEST_SHA256[role]
                == sources[BUILD_MANIFESTS[role]]["sha256"], "Preserved Phase 4F.12 manifest identity changed")
        manifest = json.loads((ROOT / BUILD_MANIFESTS[role]).read_text(), object_pairs_hook=unique_object)
        require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1
                and manifest["role"] == ("baseline" if role == "opponent" else "candidate")
                and manifest["engine_source_revision"] == ROLE_REVISIONS[role]
                and manifest["binary_sha256"] == ENGINE_SHA256[role]
                and manifest["network_sha256"] == NETWORK_SHA256
                and manifest["compile_flags"] == COMPILE_FLAGS, "Frozen engine build provenance changed")
        names = {name for name in BUILD_SOURCE_NAMES if name.startswith(folder + "/source/")}
        hashes = manifest["source_sha256"]
        require(set(hashes) == names and len(names) == 24, "Frozen build source membership changed")
        for name, expected in hashes.items():
            require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)
                    and (ROOT / name).resolve().is_relative_to((ROOT / folder / "source").resolve())
                    and sources[name]["sha256"] == child_auditor.digest(ROOT / name) == expected,
                    "Frozen build source differs: " + name)
        for field, name in (("origin_manifest", ORIGIN_MANIFESTS[role]), ("build_log", BUILD_LOGS[role])):
            require(manifest[field] == name and manifest[field + "_sha256"] == sources[name]["sha256"]
                    == child_auditor.digest(ROOT / name), "Original build evidence changed: " + field)
        origin = json.loads((ROOT / ORIGIN_MANIFESTS[role]).read_text(), object_pairs_hook=unique_object)
        if role == "opponent":
            require(origin["parent_commit"] == ROLE_REVISIONS[role]
                    and origin["binary"]["sha256"] == ENGINE_SHA256[role]
                    and origin["binary"]["flags"] == COMPILE_FLAGS
                    and origin["network_sha256"] == NETWORK_SHA256, "Original baseline build identity changed")
            original = origin["sources"]
        else:
            require(origin["candidate_sha256"] == ENGINE_SHA256[role]
                    and origin["baseline_sha256"] == ENGINE_SHA256["opponent"]
                    and isinstance(origin["oracle_report_sha256"], str)
                    and re.fullmatch(r"[0-9a-f]{64}", origin["oracle_report_sha256"]), "Original candidate build identity changed")
            original = origin["source_sha256"]
        require(all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in original)
                and hashes == {folder + "/source/" + name: sha for name, sha in original.items()},
                "Original and copied source inventories disagree")


def game_reservation(network_bytes):
    """The match runner's two-resident single-search memory estimate."""
    return 2*64*1024**2 + 8*network_bytes + 256*1024**2


def aggregate_reservation(network_bytes):
    """Reserve all eight engines, with a conservative six-GiB minimum."""
    return max(6*1024**3, SHARDS*game_reservation(network_bytes))


def permitted_launch(local, allow_daytime):
    """A fresh run can begin only in the fixed overnight admission window."""
    return allow_daytime is False and local.hour == 23 and local.minute < 30


def validate_launch_policy(policy, label, *, require_window=False, cutoff=None):
    """Independently verify permission metadata and the original civil cutoff.

    Search-free readiness is valid outside the launch window. A match launch
    must use the overnight window; no earlier daytime exception transfers.
    Returning a valid policy never authorizes a second attempt or a later cutoff.
    """
    flag = policy["allow_daytime"]
    require(policy["timezone"] == "Europe/Helsinki" and type(flag) is bool,
            label + " launch timezone or permission type changed")
    stamp = instant(policy["local_time"])
    local = stamp.astimezone(ZoneInfo("Europe/Helsinki"))
    permitted = permitted_launch(local, flag)
    require(flag is False and policy["daytime_authorization"] is None,
            label + " inherits a forbidden daytime exception")
    require(policy["launch_window"] == "23:00–23:30 Europe/Helsinki"
            and policy["launch_permitted"] is permitted,
            label + " declared launch window changed")
    require(policy["nighttime"] is (local.hour >= 23 or local.hour < 7),
            label + " nighttime flag differs from Helsinki civil time")
    require(not (require_window or flag) or permitted,
            label + " launch is outside its authorized date/window")
    expected_cutoff = datetime.combine(local.date()+timedelta(days=int(local.hour >= 7)),
                                       time(7), tzinfo=ZoneInfo("Europe/Helsinki"))
    require(instant(policy["cutoff_utc"]) == expected_cutoff == instant(policy["cutoff_local"])
            and (cutoff is None or cutoff == expected_cutoff), label + " original cutoff changed")
    require(type(policy["remaining_seconds"]) in (int, float)
            and math.isfinite(policy["remaining_seconds"]) and policy["remaining_seconds"] > 0,
            label + " remaining-time declaration changed")
    return stamp


def child_protocol(index):
    require(type(index) is int and 1 <= index <= SHARDS, "Invalid shard index")
    return child_auditor.AuditProtocol(
        protocol_id=f"{PROTOCOL_ID}-shard-{index}", pairs=SHARD_PAIRS, seed=SEEDS[index-1],
        protocol_document=PROTOCOL_DOCUMENT,
        role_options=tuple((role, tuple(options.items())) for role, options in ROLE_OPTIONS.items()),
        required_sources=REQUIRED_SOURCES,
        pinned_sha256=(*(("engine_" + role, sha) for role, sha in ENGINE_SHA256.items()), ("network", NETWORK_SHA256),
                       ("openings", opening_sha256()[index-1])),
        entrypoint="tools/audit_phase4f13.py")


def smoke_opening_sha256():
    pins = input_pins()
    return tuple(pins[f"tests/data/phase4f13-match-smoke-{i:02d}.json"] for i in range(1, 5))


def smoke_roots():
    roots = set()
    for index in range(1, SHARDS+1):
        document = json.loads((ROOT/f"tests/data/phase4f13-match-smoke-{index:02d}.json").read_text())
        _, current = definitions(document, full_history=True)
        roots.update(current)
    require(len(roots) == SHARDS, "Smoke development roots are not four distinct positions")
    return roots


def smoke_child_protocol(index):
    require(type(index) is int and 1 <= index <= SHARDS, "Invalid smoke shard index")
    return child_auditor.AuditProtocol(
        protocol_id=f"{PROTOCOL_ID}-smoke-shard-{index}", pairs=1, seed=SMOKE_SEEDS[index-1],
        protocol_document=PROTOCOL_DOCUMENT,
        role_options=tuple((role, tuple(options.items())) for role, options in ROLE_OPTIONS.items()),
        required_sources=REQUIRED_SOURCES,
        pinned_sha256=(*(("engine_" + role, sha) for role, sha in ENGINE_SHA256.items()),
                       ("network", NETWORK_SHA256), ("openings", smoke_opening_sha256()[index-1])),
        entrypoint="tools/audit_phase4f13.py", settings=tuple(dict(SETTINGS, smoke=True).items()))


def audit_output_transcript(events):
    """Validate emitted PV/ponder moves and both engines' shutdown commands.

    The legacy raw referee already binds bestmove timestamps and exact transmitted
    clocks to the move journal. This extra pass checks search-output legality
    without altering the historical referee or using launcher configuration.
    """
    boards = {role: None for role in ROLE_OPTIONS}
    paths = {role: None for role in ROLE_OPTIONS}
    quits = {role: 0 for role in ROLE_OPTIONS}
    active, windows, pv_plies, ponders = None, [], 0, 0
    for event in events:
        role, line, tick = event["engine"], event["line"], event["monotonic_ns"]
        require(role in boards and type(tick) is int and tick >= 0, "Malformed output event")
        if event["direction"] == "to_engine":
            require(quits[role] == 0, "Command after engine quit")
            if line.startswith("setoption name SyzygyPath value "):
                paths[role] = line.split(" value ", 1)[1]
            elif line.startswith("position "):
                require(active is None, "Position changed during active search")
                boards[role] = child_auditor.board_from_command(line[9:])
            elif line.startswith("go "):
                require(active is None and boards[role] is not None, "Missing/overlapping search position")
                require(paths[role] == "", "Syzygy tablebase path enabled during search")
                active = (role, tick)
            elif line == "quit":
                require(active is None, "Engine quit during active search")
                quits[role] += 1
        elif event["direction"] == "from_engine":
            if line.startswith("option name SyzygyPath type string default "):
                value = line.split(" default ", 1)[1]
                paths[role] = "" if value == "<empty>" else value
            if line.startswith("info ") and not line.startswith("info string ") and " pv " in line:
                require(active is not None and active[0] == role, "PV outside active search")
                board = boards[role].copy(stack=True)
                for token in line.split(" pv ", 1)[1].split():
                    move = chess.Move.from_uci(token)
                    require(move in board.legal_moves, "Illegal PV move")
                    board.push(move)
                    pv_plies += 1
            elif line.startswith("bestmove "):
                require(active is not None and active[0] == role, "Bestmove outside active search")
                tokens = line.split()
                require(len(tokens) == 2 or (len(tokens) == 4 and tokens[2] == "ponder"), "Malformed bestmove output")
                board = boards[role].copy(stack=True)
                for token in ([tokens[1], tokens[3]] if len(tokens) == 4 else [tokens[1]]):
                    move = chess.Move.from_uci(token)
                    require(move in board.legal_moves, "Illegal bestmove/ponder output")
                    board.push(move)
                ponders += int(len(tokens) == 4)
                require(tick >= active[1], "Search boundary timestamp reversed")
                windows.append((active[1], tick))
                active = None
        else:
            raise ValueError("Unexpected output direction or stderr")
    require(active is None and all(count == 1 for count in quits.values()), "Missing search finish or engine quit")
    return {"search_windows": windows, "pv_plies": pv_plies, "ponders": ponders}


def audit_child(directory, protocol):
    """Retain historical raw replay, adding current output and cleanup checks."""
    report = child_auditor.audit(directory, protocol)
    report["output_checks"] = []
    try:
        path = Path(directory)/"match/games.jsonl"
        records = [json.loads(line) for line in path.read_bytes().splitlines()]
        launch = json.loads((Path(directory)/"launch.json").read_text())
        for record in records:
            if record["status"] != "complete":
                continue
            require(set(record["engines"]) == set(ROLE_OPTIONS), "Recorded engine roles changed")
            for role, engine in record["engines"].items():
                expected = expected_options(role, launch["assets"]["network"]["path"])
                require(engine["ponder"] is False and all(engine["options"].get(k) == v for k,v in expected.items()),
                        "Recorded actual per-game options drifted")
            transcript = (Path(directory)/"match"/record["protocol_log"]).resolve()
            require(transcript.is_relative_to((Path(directory)/"match").resolve()), "Output transcript escapes match")
            raw = transcript.read_bytes()
            report["input_sha256"][str(transcript)] = hashlib.sha256(raw).hexdigest()
            result = audit_output_transcript([json.loads(line) for line in raw.splitlines()])
            report["output_checks"].append(dict(game_id=record["game_id"], **result))
    except FAILURES as error:
        report["errors"].append("output: " + str(error))
    if report["errors"]:
        report["complete"] = False
        report["decision"] = "invalid_or_incomplete"
        report["statistics"]["inference_eligible"] = False
        report["statistics"].update(radius=None, score_interval=None, relative_elo_interval=None)
    return report


def pooled_statistics(records, plan, complete):
    """Pool pair observations, never average shard intervals or select shards."""
    ids = {item["pair_id"] for item in plan}
    require(len(ids) == len(plan), "Duplicate pooled pair identity")
    require(len({item["game_id"] for item in records}) == len(records), "Duplicate pooled game identity")
    require(all(item["pair_id"] in ids for item in records), "Unexpected pooled game")
    eligible = (complete and len(plan) == PAIRS and len(records) == 2*PAIRS
                and not any(record.get("termination") == "time_forfeit" for record in records))
    result = child_auditor.statistics_for(records, plan, eligible, PAIRS)
    betting = paired_betting.summarize([p["score"] for p in result["included_pair_scores"]],
                                      expected_pairs=PAIRS, experiment_complete=eligible)
    result.update(recorded_games=len(records), points=math.fsum(p["points"] for p in result["included_pair_scores"]),
                  legacy_hoeffding={key: result[key] for key in ("radius", "score_interval", "relative_elo_interval")},
                  betting=betting)
    result["radius"] = None
    result["score_interval"] = betting["score_interval"]
    result["relative_elo_interval"] = betting["relative_elo_interval"]
    result["inference_eligible"] = betting["inference_eligible"]
    return result


def classify(statistics, complete, errors, time_forfeits):
    if errors or not complete:
        return "invalid_or_incomplete"
    if time_forfeits:
        return "operational_regression"
    if not statistics.get("inference_eligible"):
        return "invalid_or_incomplete"
    if statistics["score_interval"]["lower"] > .5:
        return "eligible_for_default_review"
    if statistics["score_interval"]["upper"] < .5:
        return "negative_evidence"
    return "inconclusive"


class AggregateAudit:
    """Bind master evidence to four independently checked raw campaigns."""
    def __init__(self, campaign):
        self.campaign = Path(campaign).resolve()
        self.inputs, self.live_source_differences = {}, []
        self.master, self.plans, self.records, self.admissions = None, [], [], {}
        self.smoke_admissions = {}
        self.smoke_cleanup_pids = []
        self.child_windows, self.evidence_paths = {}, set()
        self.observations, self.game_windows = [], []
        self.saved_root_cache = None

    def read(self, path, *, lines=False):
        path = Path(path).resolve()
        raw = path.read_bytes()
        self.inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return [json.loads(line) for line in raw.splitlines()] if lines else json.loads(raw)

    def local(self, name):
        path = (self.campaign/name).resolve()
        require(path.is_relative_to(self.campaign), "Evidence path escapes campaign")
        return path

    def artifact(self, asset, expected):
        require(asset["sha256"] == expected, "Artifact is not independently pinned")
        path = Path(asset["path"])
        require(path.is_absolute() and str(path.resolve()) == str(path), "Artifact path must be canonical and absolute")
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        self.inputs[str(path)] = actual
        require(actual == expected and len(raw) == asset["bytes"], "Frozen artifact changed")

    @staticmethod
    def role_asset_paths(assets):
        for role, name in FROZEN_ENGINES.items():
            require(assets["engine_" + role]["path"] == str((ROOT / name).resolve()),
                    "Executable path differs from the fixed role")
        require(ENGINE_SHA256["candidate"] != ENGINE_SHA256["opponent"]
                and not Path(assets["engine_candidate"]["path"]).samefile(assets["engine_opponent"]["path"]),
                "Both roles alias one executable")

    def master_manifest(self):
        m = self.read(self.local("campaign.json"))
        self.master = m
        require(m.get("quiet_host") is True, "Campaign lacks confirmed quiet host conditions")
        require(m["schema_version"] == 1 and m["protocol_id"] == PROTOCOL_ID, "Wrong master protocol")
        require(chess.__version__ == "1.11.2", "Wrong referee version")
        cfg = m["configuration"]
        expected = {"settings": SETTINGS, "pairs": PAIRS, "games": 2*PAIRS, "shards": SHARDS, "shard_pairs": SHARD_PAIRS,
                    "active_search_workers": SHARDS, "resident_engines": 2*SHARDS, "resource_poll_seconds": 1.,
                    "max_resource_gap_seconds": 5.,
                    "seeds": list(SEEDS), "ponder": False, "diagnostics": False}
        require(set(cfg) == set(expected)|{"engines"}, "Unexpected master configuration fields")
        require(all(cfg[key] == value for key, value in expected.items()), "Master sample/settings changed")
        require(child_auditor.canonical_digest(cfg) == m["configuration_sha256"], "Master configuration digest mismatch")
        assets = m["frozen"]
        pins = {**{"engine_" + role: sha for role, sha in ENGINE_SHA256.items()}, "network": NETWORK_SHA256,
                **{f"openings_{i}": sha for i, sha in enumerate(opening_sha256(), 1)},
                **{f"smoke_openings_{i}": sha for i, sha in enumerate(smoke_opening_sha256(), 1)}}
        require(set(assets) == set(pins), "Unexpected frozen asset membership")
        for name, expected_sha in pins.items():
            self.artifact(assets[name], expected_sha)
        self.role_asset_paths(assets)
        engines = {entry["role"]: entry for entry in cfg["engines"]}
        require(len(cfg["engines"]) == 2 and set(engines) == set(ROLE_OPTIONS), "Invalid master roles")
        for role, entry in engines.items():
            require(entry["executable"] == assets["engine_" + role]["path"] and entry["network"] == assets["network"]["path"],
                    "Master role does not use its frozen binary/network")
            require(entry["arguments"] == [] and entry["network_option"] == "EvalFile"
                    and entry["extra_options"] == ROLE_OPTIONS[role]
                    and entry["source_revision"] == ROLE_REVISIONS[role], "Master options/revisions do not match the before/after NNUE packages")
        sources = m["sources"]
        require(set(REQUIRED_SOURCES) == set(sources), "Missing or unexpected master source freezes")
        require(child_auditor.digest(ROOT / PIN_FILE) == sources[PIN_FILE]["sha256"],
                "Preparation pins changed since campaign freeze")
        for name, expected_sha in input_pins().items():
            require(sources[name]["sha256"] == expected_sha, "Unpinned generation, exclusion, or build input")
            require(child_auditor.digest(ROOT / name) == expected_sha, "Pinned preparation input changed")
        validate_build_provenance(sources)
        for name, fingerprint in sources.items():
            source = (ROOT/name).resolve()
            require(not Path(name).is_absolute() and source.is_relative_to(ROOT.resolve()), "Source path escapes checkout")
            require(re.fullmatch(r"[0-9a-f]{64}", fingerprint["sha256"]) and type(fingerprint["bytes"]) is int
                    and fingerprint["bytes"] > 0, "Malformed frozen source record")
            if not source.is_file() or child_auditor.digest(source) != fingerprint["sha256"]:
                self.live_source_differences.append(name)
        require(m["artifacts_before"] == {"assets": assets, "sources": sources}, "Initial master snapshot disagrees")
        require(m["artifacts_after"] == {"assets": assets, "sources": sources, "unchanged": True,
                                          "configuration_sha256": m["configuration_sha256"]}, "Final master integrity check failed")
        protocol = m["protocol"]
        require(protocol["path"] == "protocol.md", "Unexpected master protocol path")
        raw = self.local("protocol.md").read_bytes()
        self.inputs[str(self.local("protocol.md"))] = hashlib.sha256(raw).hexdigest()
        require(hashlib.sha256(raw).hexdigest() == protocol["sha256"] == sources[PROTOCOL_DOCUMENT]["sha256"],
                "Master protocol snapshot changed")
        started, finished, cutoff = (instant(m[key]) for key in ("started_utc", "finished_utc", "cutoff_utc"))
        stamp = validate_launch_policy(m["launch_policy"], "Master", require_window=True, cutoff=cutoff)
        require(stamp == started and started <= finished, "Master launch policy timestamp changed")
        if m["status"] == "finished":
            require(finished <= cutoff, "Finished master exceeded cutoff")
        require(m["preflight"]["opening_count"] == m["preflight"]["distinct_roots"] == PAIRS
                and m["preflight"]["previous_root_count"] == len(self.prior_roots()), "Master preflight root counts changed")
        self.preflight_engines()
        expected_shards = [{"index": i, "protocol_id": f"{PROTOCOL_ID}-shard-{i}", "seed": SEEDS[i-1],
                            "path": f"shard-{i}", "openings": assets[f"openings_{i}"]} for i in range(1, SHARDS+1)]
        require(m["shards"] == expected_shards, "Shard membership, path or seed changed")
        self.started, self.finished, self.cutoff = started, finished, cutoff
        self.resource_history()
        self.validate_smoke_gate()

    def validate_smoke_gate(self):
        smoke = self.master["clock_smoke"]
        require(smoke["status"] == "passed", "Required clock smoke has not passed")
        require(smoke["audit"]["path"] == "clock-smoke-audit.json", "Unexpected smoke audit location")
        path = self.local(smoke["audit"]["path"])
        saved = self.read(path)
        require(self.inputs[str(path)] == smoke["audit"]["sha256"], "Saved smoke audit hash changed")
        actual = audit_smoke(self.campaign)
        require(actual["passed"] and saved["passed"], "Independent clock smoke failed")
        # The parent campaign manifest necessarily evolves after this gate.
        # Every immutable smoke/input byte and every stable verdict must agree.
        for report in (saved, actual):
            report["input_sha256"].pop(str(self.local("campaign.json")), None)
        for key in actual:
            if key != "audited_utc":
                require(saved.get(key) == actual[key], "Saved smoke audit differs: " + key)
        passed, audited = instant(smoke["passed_utc"]), instant(saved["audited_utc"])
        end, start = instant(smoke["finished_utc"]), instant(smoke["started_utc"])
        require(end <= audited <= passed <= start + timedelta(seconds=SMOKE_TIMEOUT_SECONDS)
                and passed <= self.cutoff, "Smoke audit/passage escaped its original deadline")
        require(len(self.smoke_admissions) == 2*SMOKE_PAIRS, "Smoke admission count changed")
        require(all(passed <= stamp for stamp, _ in self.admissions.values()),
                "Held-out game admitted before smoke audit passed")
        self.smoke_passed = passed
        self.smoke_cleanup_pids = smoke["cleanup"]["engine_pids"]
        self.inputs.update(actual["input_sha256"])

    def preflight_engines(self):
        """Replay exact, search-free handshakes and their completed cleanup."""
        engines = self.master["preflight"]["engines"]
        require(len(engines) == 2 and {engine["role"] for engine in engines} == set(ROLE_OPTIONS),
                "Preflight must contain exactly the two engine roles")
        pids = [engine["pid"] for engine in engines]
        require(all(type(pid) is int and pid > 0 for pid in pids) and len(set(pids)) == 2
                and all(type(engine["returncode"]) is int and engine["returncode"] == 0 for engine in engines),
                "Preflight process identities or successful cleanup missing")
        architecture = option_architecture()
        declarations = {option_declaration(name, schema): name for name, schema in architecture.items()}
        for engine in engines:
            role = engine["role"]
            expected = expected_options(role, self.master["frozen"]["network"]["path"])
            require(engine["configured"] == expected, "Preflight applied options differ from the fixed comparison")
            options = engine["options"]
            require(set(options) == set(architecture), "Preflight UCI option membership changed")
            for name, schema in architecture.items():
                for field, value in schema.items():
                    actual = options[name].get(field)
                    require(type(actual) is type(value) and actual == value,
                            "Preflight UCI option type/range/default changed: " + name)
            previous, actual, ready_options, seen = -1, {}, None, set()
            stage = "new"
            for event in engine["transcript"]:
                tick = event["monotonic_ns"]
                require(event["engine"] == role and type(tick) is int and tick >= previous,
                        "Preflight role/timestamps changed")
                previous = tick
                line, direction = event["line"], event["direction"]
                require(direction in ("to_engine", "from_engine"), "Unexpected preflight stderr/direction")
                require(line not in ("position", "go", "bestmove") and not line.startswith(("position ", "go ", "bestmove ")),
                        "Preflight searched or exposed an opening")
                require(not line.lower().startswith(("info string error:", "info string search error:")),
                        "Preflight engine reported an error")
                if direction == "from_engine":
                    if line.startswith("option "):
                        require(stage == "uci" and line in declarations and declarations[line] not in seen,
                                "Actual UCI declaration changed or duplicated")
                        name = declarations[line]
                        seen.add(name)
                        if "default" in architecture[name]:
                            value = architecture[name]["default"]
                            actual[name] = str(value).lower() if type(value) is bool else str(value)
                    elif line == "uciok":
                        require(stage == "uci" and seen == set(architecture), "Incomplete UCI declarations")
                        stage = "configured"
                    elif line == "readyok":
                        require(stage == "waiting", "Unexpected readiness acknowledgement")
                        ready_options, stage = actual.copy(), "ready"
                else:
                    setting = re.fullmatch(r"setoption name (.+?) value (.*)", line)
                    if line == "uci":
                        require(stage == "new", "Duplicate/out-of-order UCI handshake")
                        stage = "uci"
                    elif setting:
                        require(stage == "configured" and setting[1] in architecture
                                and architecture[setting[1]]["type"] != "button", "Unexpected readiness setting")
                        actual[setting[1]] = setting[2]
                    elif line == "isready":
                        require(stage == "configured", "Out-of-order readiness request")
                        stage = "waiting"
                    elif line == "quit":
                        require(stage == "ready", "Premature/duplicate readiness cleanup")
                        stage = "closed"
                    else:
                        raise ValueError("Unexpected command in search-free readiness")
            require(stage == "closed", "Incomplete preflight readiness/cleanup transcript")
            expected_actual = {name: str(value).lower() if type(value) is bool else str(value)
                               for name, value in {**expected, "Ponder": False}.items()}
            require(ready_options is not None and all(ready_options.get(name) == value
                    for name, value in expected_actual.items()), "Actual readiness UCI options differ")

    def resource_history(self):
        """Check aggregate reservations and every admission, not four local budgets."""
        m = self.master
        reservation = aggregate_reservation(m["frozen"]["network"]["bytes"])
        previous = self.started
        journal = m["resource_history"]
        require(journal["path"] == "resource-history.jsonl", "Unexpected resource journal path")
        history = self.read(self.local(journal["path"]), lines=True)
        require(self.inputs[str(self.local(journal["path"]))] == journal["sha256"]
                and len(history) == journal["observations"], "Resource journal hash/count changed")
        require(history and history[0]["trigger"] == "initial" and history[-1]["trigger"] == "final",
                "Missing initial/final aggregate resource observations")
        for event in history:
            stamp = instant(event["observed_utc"])
            require(previous <= stamp <= self.finished, "Resource history timestamps are not ordered")
            previous = stamp
            self.observations.append(stamp)
            p = event["policy"]
            require(p["active_search_workers"] == SHARDS and p["resident_engines"] == 2*SHARDS
                    and p["estimated_memory_bytes"] == reservation and p["memory_estimate_is_hard_cap"] is False,
                    "Resource reservation does not count all shards")
            within = self.budget(p, stamp, reservation)
            require(event["within_limits"] is within, "Recorded aggregate budget verdict is wrong")
            if m["status"] == "finished":
                require(within, "Completed campaign crossed its resource budget")
            trigger = event["trigger"]
            require(trigger in ("initial", "periodic", "before_game", "before_smoke_game", "final"), "Unknown resource observation trigger")
            if trigger in ("before_game", "before_smoke_game"):
                admissions = self.admissions if trigger == "before_game" else self.smoke_admissions
                key = (event["shard_index"], event["game_id"])
                require(type(key[0]) is int and 1 <= key[0] <= SHARDS and key not in admissions,
                        "Duplicate or unknown game admission")
                require(within and stamp < self.cutoff, "Game admitted after cutoff or over budget")
                admissions[key] = (stamp, p)
        # Readiness and policy sampling occur at separate instants. A legitimate
        # owner override may change between reads while both still allow 4/8.
        preflight = m["preflight"]["resource_policy"]
        checked = instant(m["checked_utc"])
        require(self.started <= checked <= self.finished, "Preflight timestamp escapes master")
        checked_local = checked.astimezone(ZoneInfo("Europe/Helsinki"))
        require(checked_local.date() == self.started.astimezone(ZoneInfo("Europe/Helsinki")).date()
                and permitted_launch(checked_local, m["launch_policy"]["allow_daytime"]), "Preflight completed outside launch window")
        require(preflight["active_search_workers"] == SHARDS and preflight["resident_engines"] == 2*SHARDS
                and preflight["estimated_memory_bytes"] == reservation
                and preflight["memory_estimate_is_hard_cap"] is False
                and self.budget(preflight, checked, reservation), "Invalid aggregate preflight resource reservation")
        if m["status"] == "finished":
            require(any(event["trigger"] == "periodic" for event in history), "Missing periodic resource monitoring")

    @staticmethod
    def budget(policy, observed, aggregate_reservation):
        """Validate one independently sampled policy for all four active shards."""
        p = policy
        require(type(p["logical_cpus"]) is int and p["logical_cpus"] > 0 and type(p["percent"]) is int
                and 1 <= p["percent"] <= 100, "Invalid CPU/resource percentage")
        local = observed.astimezone(ZoneInfo("Europe/Helsinki"))
        nighttime = local.hour >= 23 or local.hour < 7
        require(p["timezone"] == "Europe/Helsinki" and p["source"] in ("manual", "nighttime", "daytime"),
                "Unknown resource policy source")
        if p["source"] != "manual":
            require(p["source"] == ("nighttime" if nighttime else "daytime")
                    and p["percent"] == (80 if nighttime else 50), "Resource percentage differs from civil-time policy")
        require(p["max_cpu_workers"] == max(1, math.floor(p["logical_cpus"]*p["percent"]/100))
                and p["memory_fraction"] == p["percent"]/100, "Derived resource budget changed")
        memory = p["physical_memory_bytes"]
        require(type(memory) is int and memory > 0, "Aggregate physical memory is unknown")
        return SHARDS <= p["max_cpu_workers"] and aggregate_reservation <= memory*p["memory_fraction"]

    def prior_roots(self):
        document = self.read(ROOT / EXCLUSIONS)
        entries = document["roots"]
        result = set()
        for entry in entries:
            key = entry["root_key"]
            board = chess.Board(key + " 0 1")
            require(board.is_valid() and root_key(board) == key, "Malformed canonical exclusion root")
            require(key not in result, "Duplicate exclusion root")
            result.add(key)
        require(result, "Empty exposure exclusion manifest")
        return result

    def saved_roots(self):
        """Independently replay all recorded saved PGNs, not generator output.

        The compact public exclusion catalog is sufficient for deterministic
        generation. This separate local check proves that accepted roots also
        avoid the full saved-mainline set at preparation. Scores/PVs are ignored.
        """
        if self.saved_root_cache is not None:
            return self.saved_root_cache
        metadata = self.read(ROOT / GENERATION_METADATA)
        combined, source_paths = set(), set()
        def digest_json(value):
            raw = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode()
            return hashlib.sha256(raw).hexdigest()
        for source in metadata["sources"]:
            if source["kind"] != "saved-pgn-directory":
                continue
            directory = (ROOT/source["path"]).resolve()
            require(not Path(source["path"]).is_absolute() and directory.is_relative_to(ROOT.resolve())
                    and directory not in source_paths, "Saved-PGN source escapes checkout or duplicates")
            source_paths.add(directory)
            manifest, roots, exceptions = [], set(), []
            counts = {"files": 0, "games": 0, "legal_prefix_games": 0, "invalid_initial_games": 0}
            for path in sorted(directory.glob("*.pgn")):
                raw = path.read_bytes()
                sha = hashlib.sha256(raw).hexdigest()
                self.inputs[str(path)] = sha
                manifest.append({"path": path.name, "sha256": sha})
                counts["files"] += 1
                stream, file_games = io.StringIO(raw.decode("utf-8-sig")), 0
                while True:
                    game = chess.pgn.read_game(stream)
                    if game is None:
                        break
                    counts["games"] += 1
                    file_games += 1
                    board = game.board()
                    if not board.is_valid():
                        counts["invalid_initial_games"] += 1
                        exceptions.append({"path": path.name, "game": file_games, "reason": "invalid_initial_position"})
                        continue
                    roots.add(root_key(board))
                    partial = bool(game.errors)
                    for move in game.mainline_moves():
                        if not move or move not in board.legal_moves:
                            partial = True
                            break
                        board.push(move)
                        roots.add(root_key(board))
                    if partial:
                        counts["legal_prefix_games"] += 1
                        exceptions.append({"path": path.name, "game": file_games, "reason": "parser_error_or_null_or_illegal_move"})
                if not file_games:
                    exceptions.append({"path": path.name, "game": 0, "reason": "empty_pgn"})
            require(manifest and digest_json(manifest) == source["sha256"], "Saved PGN byte manifest changed")
            require(counts == source["replay_counts"] and counts["games"] == source["entries"]
                    and exceptions == source["exceptions"], "Saved PGN replay counts or omissions changed")
            require(len(roots) == source["unique_roots"]
                    and digest_json(sorted(roots)) == source["canonical_roots_sha256"], "Saved PGN canonical roots changed")
            combined.update(roots)
        require(len(combined) == metadata["saved_game_unique_roots"], "Saved PGN union count differs")
        self.saved_root_cache = combined
        return combined

    def shard(self, index, prior, seen_roots, seen_ids):
        """Validate child/master binding and reconstruct the global full schedule."""
        directory = self.local(f"shard-{index}")
        require(directory == self.campaign/f"shard-{index}" and not directory.is_symlink(), "Shard directory aliases another path")
        launch = self.read(directory/"launch.json")
        m, asset = self.master, self.master["frozen"][f"openings_{index}"]
        require(launch["assets"] == {**{"engine_" + role: m["frozen"]["engine_" + role] for role in ROLE_OPTIONS}, "network": m["frozen"]["network"], "openings": asset},
                "Child artifacts differ from master")
        require(launch["sources"] == m["sources"], "Child source freeze differs from master")
        require(launch["preflight"]["engines"] == m["preflight"]["engines"], "Child readiness does not match shared preflight")
        cfg = launch["configuration"]
        require(cfg == {"pairs": SHARD_PAIRS, "seed": SEEDS[index-1], "settings": SETTINGS, "engines": m["configuration"]["engines"],
                        "ponder": False, "diagnostics": False}, "Child configuration differs from master")
        start, end = instant(launch["started_utc"]), instant(launch["finished_utc"])
        require(self.started <= self.smoke_passed <= start <= end <= self.finished, "Child window escapes master or starts before smoke passed")
        child_policy, master_policy = launch["launch_policy"], m["launch_policy"]
        child_stamp = validate_launch_policy(child_policy, "Child", require_window=True, cutoff=self.cutoff)
        require(self.started <= child_stamp <= start
                and child_policy["allow_daytime"] is master_policy["allow_daytime"]
                and child_policy["daytime_authorization"] == master_policy["daytime_authorization"]
                and child_policy["launch_window"] == master_policy["launch_window"],
                "Child cutoff/daytime authorization differs from master")
        if launch["status"] == "finished":
            require(end <= self.cutoff, "Completed child exceeded common cutoff")
        self.child_windows[index] = (start, end)
        definitions_list, roots = definitions(self.read(Path(asset["path"])), full_history=True)
        require(len(definitions_list) == SHARD_PAIRS and not roots & (prior|seen_roots), "Fresh roots duplicate or overlap exposed evidence")
        ids = {entry["opening_id"] for entry in definitions_list}
        require(not ids & seen_ids, "Opening IDs reused between shards")
        seen_ids.update(ids); seen_roots.update(roots)
        rng = random.Random(SEEDS[index-1]); rng.shuffle(definitions_list)
        plan = [dict(entry, pair_id=f"p{i+1:06d}", first_candidate_color=rng.choice(("white", "black")))
                for i, entry in enumerate(definitions_list)]
        run = self.read(directory/"match/run.json")
        require(run["plan"] == plan, "Child plan differs from independent full-history/color reconstruction")
        run_start, run_end = instant(run["started_utc"]), instant(run["finished_utc"])
        require(start <= run_start <= run_end <= end, "Runner timestamps escape child")
        records = self.read(directory/"match/games.jsonl", lines=True)
        expected = [(pair, leg, color) for pair in plan
                    for leg, color in enumerate((pair["first_candidate_color"],
                       "black" if pair["first_candidate_color"] == "white" else "white"), 1)]
        require(len(records) <= 2*SHARD_PAIRS, "Too many games in shard")
        previous_end = run_start
        for record, (pair, leg, color) in zip(records, expected):
            game_id = f"{pair['pair_id']}-{leg}"
            require(record["game_id"] == game_id and record["pair_id"] == pair["pair_id"]
                    and record["candidate_color"] == color, "Game order/identity/colors changed")
            game_start, game_end = instant(record["started_utc"]), instant(record["finished_utc"])
            require(previous_end <= game_start <= game_end <= run_end, "Games overlap or escape runner timestamps")
            previous_end = game_end
            self.game_windows.append((game_start, game_end))
            admitted, policy = self.admissions[(index, game_id)]
            require(run_start <= admitted <= game_start, "Game admission timestamp is outside its setup boundary")
            local_policy = record["resource_policy"]
            require(local_policy["active_search_workers"] == 1 and local_policy["resident_engines"] == 2
                    and local_policy["estimated_memory_bytes"] == game_reservation(m["frozen"]["network"]["bytes"])
                    and local_policy["memory_estimate_is_hard_cap"] is False, "Game resource reservation changed")
            require(self.budget(local_policy, game_start, policy["estimated_memory_bytes"]),
                    "Game policy cannot support the entire four-shard experiment")
            for key in ("pgn", "protocol_log"):
                path = (directory/"match"/record[key]).resolve()
                require(path.is_relative_to(directory/"match") and path not in self.evidence_paths,
                        "Evidence path escapes, aliases, or is reused")
                require(path.is_file(), "Missing raw game evidence")
                self.evidence_paths.add(path)
            self.records.append(dict(record, pair_id=f"shard-{index}/{record['pair_id']}", game_id=f"shard-{index}/{game_id}"))
        self.plans.extend(dict(pair, pair_id=f"shard-{index}/{pair['pair_id']}") for pair in plan)
        return launch, records


def audit_smoke(campaign):
    """Audit exactly eight development games, without ever estimating strength.

    Called before held-out admission and again during final qualification audit.
    The resource prefix is immutable while the parent supervisor keeps running.
    No frozen globals, historical helpers, games or engine settings are changed.
    """
    checker, errors, records, shard_results = AggregateAudit(campaign), [], [], []
    smoke = {}
    try:
        master = checker.read(checker.local("campaign.json"))
        checker.master = master
        require(master["schema_version"] == 1 and master["protocol_id"] == PROTOCOL_ID
                and master["quiet_host"] is True, "Wrong smoke parent identity or quiet-host admission")
        assets, sources, cfg, smoke = (master[key] for key in ("frozen", "sources", "configuration", "clock_smoke"))
        require(set(sources) == set(REQUIRED_SOURCES), "Smoke source membership changed")
        for name, expected in input_pins().items():
            require(sources[name]["sha256"] == child_auditor.digest(ROOT/name) == expected,
                    "Smoke pinned preparation input changed: " + name)
            checker.inputs[str((ROOT/name).resolve())] = expected
        require(child_auditor.digest(ROOT/PIN_FILE) == sources[PIN_FILE]["sha256"], "Smoke preparation pin file changed")
        validate_build_provenance(sources)
        pins = {**{"engine_" + role: sha for role, sha in ENGINE_SHA256.items()}, "network": NETWORK_SHA256,
                **{f"openings_{i}": sha for i, sha in enumerate(opening_sha256(), 1)},
                **{f"smoke_openings_{i}": sha for i, sha in enumerate(smoke_opening_sha256(), 1)}}
        require(set(assets) == set(pins), "Smoke parent artifact membership changed")
        for name, expected in pins.items():
            checker.artifact(assets[name], expected)
        checker.role_asset_paths(assets)
        require(master["artifacts_before"] == {"assets": assets, "sources": sources}, "Smoke initial snapshot differs")
        expected_cfg = {"settings": SETTINGS, "pairs": PAIRS, "games": 2*PAIRS, "shards": SHARDS,
                        "shard_pairs": SHARD_PAIRS, "active_search_workers": SHARDS, "resident_engines": 2*SHARDS,
                        "resource_poll_seconds": 1., "max_resource_gap_seconds": 5., "seeds": list(SEEDS),
                        "ponder": False, "diagnostics": False}
        require(set(cfg) == set(expected_cfg)|{"engines"} and all(cfg[k] == v for k,v in expected_cfg.items())
                and child_auditor.canonical_digest(cfg) == master["configuration_sha256"], "Smoke parent configuration changed")
        engines = {entry["role"]: entry for entry in cfg["engines"]}
        require(len(cfg["engines"]) == 2 and set(engines) == set(ROLE_OPTIONS), "Smoke parent roles changed")
        for role, entry in engines.items():
            require(entry == {"role": role, "executable": assets["engine_"+role]["path"],
                              "network": assets["network"]["path"], "network_option": "EvalFile", "arguments": [],
                              "source_revision": ROLE_REVISIONS[role], "extra_options": ROLE_OPTIONS[role]},
                    "Smoke before/after recipe changed")
        checker.preflight_engines()
        require(master["preflight"]["smoke_opening_count"] == master["preflight"]["smoke_distinct_roots"] == SHARDS,
                "Smoke preflight root counts changed")
        parent_start = validate_launch_policy(master["launch_policy"], "Smoke parent", require_window=True)
        cutoff = instant(master["cutoff_utc"])
        require(parent_start == instant(master["started_utc"])
                and cutoff == instant(master["launch_policy"]["cutoff_utc"]), "Smoke parent original cutoff changed")
        start, end = instant(smoke["started_utc"]), instant(smoke["finished_utc"])
        require(smoke["status"] in ("completed", "passed") and smoke["pairs"] == SMOKE_PAIRS
                and smoke["games"] == 2*SMOKE_PAIRS and smoke["timeout_seconds"] == SMOKE_TIMEOUT_SECONDS
                and smoke["seeds"] == list(SMOKE_SEEDS), "Smoke sample or deadline changed")
        require(parent_start <= instant(master["checked_utc"]) <= start <= end <= cutoff
                and end <= start+timedelta(seconds=SMOKE_TIMEOUT_SECONDS), "Smoke stage escaped original time bounds")
        expected_shards = [{"index": i, "protocol_id": f"{PROTOCOL_ID}-smoke-shard-{i}", "seed": SMOKE_SEEDS[i-1],
                            "path": f"clock-smoke/shard-{i}", "openings": assets[f"smoke_openings_{i}"]} for i in range(1, 5)]
        require(smoke["shards"] == expected_shards, "Smoke shard identity or order changed")
        catalog = checker.read(ROOT/SMOKE_CATALOG)["openings"]
        selected = {entry["id"]: entry for entry in catalog}
        require(len(selected) == len(catalog), "Development catalog has duplicate identities")
        history = smoke["resource_history"]
        require(history["path"] == "clock-smoke/resource-history.jsonl", "Wrong smoke resource prefix path")
        prefix_path = checker.local(history["path"])
        observations = checker.read(prefix_path, lines=True)
        prefix = prefix_path.read_bytes()
        with checker.local("resource-history.jsonl").open("rb") as stream:
            require(stream.read(len(prefix)) == prefix, "Smoke resource snapshot is not the parent journal prefix")
        require(history["sha256"] == checker.inputs[str(prefix_path)] and history["observations"] == len(observations)
                and observations and observations[0]["trigger"] == "initial", "Smoke resource snapshot hash/count changed")
        admissions, observation_times = {}, []
        reservation = aggregate_reservation(assets["network"]["bytes"])
        previous = parent_start
        for event in observations:
            stamp, policy = instant(event["observed_utc"]), event["policy"]
            require(previous <= stamp <= end and event["trigger"] in ("initial", "periodic", "before_smoke_game"),
                    "Smoke resource event ordering or trigger changed")
            previous = stamp; observation_times.append(stamp)
            require(policy["active_search_workers"] == SHARDS and policy["resident_engines"] == 2*SHARDS
                    and policy["estimated_memory_bytes"] == reservation and policy["memory_estimate_is_hard_cap"] is False
                    and checker.budget(policy, stamp, reservation) and event["within_limits"] is True,
                    "Smoke aggregate resource budget failed")
            if event["trigger"] == "before_smoke_game":
                key = event["shard_index"], event["game_id"]
                require(type(key[0]) is int and 1 <= key[0] <= SHARDS and key not in admissions
                        and start <= stamp <= end, "Smoke admission is repeated, unknown or outside the stage")
                admissions[key] = stamp
        require(any(e["trigger"] == "periodic" for e in observations), "Smoke has no periodic resource supervision")
        game_windows, evidence_paths = [], set()
        for index in range(1, SHARDS+1):
            directory = checker.local(f"clock-smoke/shard-{index}")
            require(directory == checker.campaign/f"clock-smoke/shard-{index}", "Smoke shard directory aliases another path")
            suite = checker.read(Path(assets[f"smoke_openings_{index}"]["path"]))
            require(suite["openings"] == [selected[SMOKE_DEVELOPMENT_IDS[index-1]]],
                    "Smoke opening differs from the fixed exposed development position")
            defs, _ = definitions(suite, full_history=True)
            rng = random.Random(SMOKE_SEEDS[index-1]); rng.shuffle(defs)
            plan = [dict(defs[0], pair_id="p000001", first_candidate_color=rng.choice(("white", "black")))]
            launch, run = checker.read(directory/"launch.json"), checker.read(directory/"match/run.json")
            require(launch["assets"] == {**{key: assets[key] for key in ("engine_candidate", "engine_opponent", "network")},
                                         "openings": assets[f"smoke_openings_{index}"]}
                    and launch["sources"] == sources and launch["preflight"]["engines"] == master["preflight"]["engines"],
                    "Smoke child artifacts or readiness differ from parent")
            require(launch["configuration"] == {"pairs": 1, "seed": SMOKE_SEEDS[index-1], "settings": dict(SETTINGS, smoke=True),
                                                "engines": cfg["engines"], "ponder": False, "diagnostics": False}
                    and run["plan"] == plan, "Smoke configuration, plan or color order changed")
            child_start, child_end = instant(launch["started_utc"]), instant(launch["finished_utc"])
            child_stamp = validate_launch_policy(launch["launch_policy"], "Smoke child", require_window=True, cutoff=cutoff)
            run_start, run_end = instant(run["started_utc"]), instant(run["finished_utc"])
            require(parent_start <= child_stamp <= child_start and start <= child_start <= run_start <= run_end <= child_end <= end,
                    "Smoke child timing escapes its stage")
            games = checker.read(directory/"match/games.jsonl", lines=True)
            require(len(games) == 2, "Smoke shard lacks exactly two games")
            first, previous_end = plan[0]["first_candidate_color"], run_start
            for leg, game in enumerate(games, 1):
                game_id = f"p000001-{leg}"
                color = first if leg == 1 else "black" if first == "white" else "white"
                require(game["game_id"] == game_id and game["pair_id"] == "p000001" and game["candidate_color"] == color,
                        "Smoke game identity or color reversal changed")
                begin, finish = instant(game["started_utc"]), instant(game["finished_utc"])
                require(previous_end <= begin <= finish <= run_end and run_start <= admissions[(index, game_id)] <= begin,
                        "Smoke games overlap or lack timely admission")
                previous_end = finish; game_windows.append((begin, finish))
                policy = game["resource_policy"]
                require(policy["active_search_workers"] == 1 and policy["resident_engines"] == 2
                        and policy["estimated_memory_bytes"] == game_reservation(assets["network"]["bytes"])
                        and policy["memory_estimate_is_hard_cap"] is False and checker.budget(policy, begin, reservation),
                        "Smoke game budget differs from full-load reservation")
                for key in ("pgn", "protocol_log"):
                    path = (directory/"match"/game[key]).resolve()
                    require(path.is_relative_to(directory/"match") and path.is_file() and path not in evidence_paths,
                            "Smoke raw evidence is missing, reused or outside its shard")
                    evidence_paths.add(path)
                records.append(game)
            raw = audit_child(directory, smoke_child_protocol(index))
            checker.inputs.update(raw["input_sha256"])
            require(raw["complete"] and not raw["errors"] and raw["statistics"]["inference_eligible"] is False,
                    "Smoke raw audit failed: " + "; ".join(raw["errors"]))
            shard_results.append({"index": index, "games": len(games), "complete": True})
        require(len(admissions) == 8 and len(records) == 8 and len(shard_results) == SHARDS,
                "Smoke is missing games or admissions")
        require(not any(game.get("termination") == "time_forfeit" for game in records), "Smoke has a clock forfeit")
        for left, right in zip(observation_times, observation_times[1:]+[end]):
            require((right-left).total_seconds() <= 5 or not any(a < right and b > left for a,b in game_windows),
                    "Smoke resource observation gap exceeded five seconds during a game")
        expected_pids = sorted({engine["pid"] for game in records for engine in game["engines"].values()})
        require(all(type(pid) is int and pid > 0 for pid in expected_pids)
                and smoke["cleanup"] == {"engine_pids": expected_pids, "alive_pids": [], "unverified_pids": []},
                "Smoke cleanup is missing, mismatched or incomplete")
    except FAILURES as error:
        errors.append(str(error))
    smoke_details = smoke if isinstance(smoke, dict) else {}
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID + "-smoke", "campaign": str(checker.campaign),
            "audited_utc": datetime.now(timezone.utc).isoformat(), "passed": not errors, "errors": errors,
            "games": len(records), "pairs": len(records)//2, "shards": shard_results,
            "smoke_started_utc": smoke_details.get("started_utc"), "smoke_finished_utc": smoke_details.get("finished_utc"),
            "time_forfeits": sum(game.get("termination") == "time_forfeit" for game in records),
            "inference_eligible": False, "default_change": False,
            "audit_tool_sha256": child_auditor.digest(Path(__file__)),
            "raw_audit_tool_sha256": child_auditor.digest(Path(child_auditor.__file__)),
            "input_sha256": checker.inputs, "note": "Eight exposed development games only; excluded from strength inference and qualification pair counts."}


def audit(campaign):
    """Return descriptive incomplete evidence, with inference withheld on any error."""
    checker, errors, reports = AggregateAudit(campaign), [], []
    master_valid = False
    try:
        checker.master_manifest()
        prior = checker.prior_roots() | checker.saved_roots() | smoke_roots()
        master_valid = True
    except FAILURES as error:
        errors.append(f"master: {error}")
        prior = set()
    roots, ids = set(), set()
    for index in range(1, SHARDS+1):
        try:
            directory = checker.local(f"shard-{index}")
            require(directory == checker.campaign/f"shard-{index}", "Shard path aliases another directory")
            raw = audit_child(directory, child_protocol(index))
            reports.append(dict(index=index, **raw))
            checker.inputs.update(raw["input_sha256"])
            checker.live_source_differences.extend(raw["live_source_differences"])
            if master_valid:
                checker.shard(index, prior, roots, ids)
            require(not raw["errors"] and raw["complete"] and raw["statistics"]["inference_eligible"],
                    "Raw child audit is invalid or incomplete: " + "; ".join(raw["errors"]))
        except FAILURES as error:
            errors.append(f"shard-{index}: {error}")
    master = checker.master if isinstance(checker.master, dict) else {}
    complete = master.get("status") == "finished" and not errors
    try:
        require(len(reports) == SHARDS and len(roots) == len(ids) == PAIRS, "Not all four distinct opening shards audited")
        require(len(checker.admissions) == 2*PAIRS, "Missing or excess aggregate game admissions")
        statuses = master["shard_statuses"]
        require(len(statuses) == SHARDS and [s["index"] for s in statuses] == list(range(1, SHARDS+1)), "Shard completion membership changed")
        for status in statuses:
            require(status["status"] == "finished" and instant(status["finished_utc"]) == checker.child_windows[status["index"]][1],
                    "Master shard status differs from completed child")
        for left, right in zip(checker.observations, checker.observations[1:]):
            if (right-left).total_seconds() > 5:
                require(not any(start < right and end > left for start, end in checker.game_windows),
                        "Resource observations have a gap over five seconds during a game")
    except FAILURES as error:
        errors.append(f"aggregate: {error}")
        complete = False
    try:
        expected_pids = sorted({engine["pid"] for record in checker.records for engine in record["engines"].values()}
                               | set(checker.smoke_cleanup_pids))
        require(all(type(pid) is int and pid > 0 for pid in expected_pids), "Invalid recorded engine PID")
        cleanup = master["cleanup"]
        require(cleanup == {"engine_pids": expected_pids, "alive_pids": [], "unverified_pids": []},
                "Engine cleanup missing, mismatched, or unverified")
    except FAILURES as error:
        errors.append(f"cleanup: {error}")
        complete = False
    complete = complete and not errors
    stats = pooled_statistics([], [], False)
    try:
        stats = pooled_statistics(checker.records, checker.plans, complete)
    except FAILURES as error:
        errors.append(f"statistics: {error}"); complete = False
    forfeits = {role: sum(record.get("termination") == "time_forfeit" and record.get("clock_loser") == role
                         for record in checker.records) for role in ROLE_OPTIONS}
    decision = classify(stats, complete, errors, sum(forfeits.values()))
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "campaign": str(checker.campaign),
            "audited_utc": datetime.now(timezone.utc).isoformat(),
            "audit_tool_sha256": child_auditor.digest(Path(__file__)),
            "raw_audit_tool_sha256": child_auditor.digest(Path(child_auditor.__file__)),
            "decision": decision, "complete": complete, "default_change": False, "errors": errors,
            "statistics": stats, "shards": reports, "candidate_time_forfeits": forfeits["candidate"],
            "opponent_time_forfeits": forfeits["opponent"], "input_sha256": checker.inputs,
            "live_source_differences": sorted(set(checker.live_source_differences)),
            "note": "One fixed 2048-game qualification. A positive result permits conditional default review, not automatic promotion or a general Elo claim."}


def audit_readiness(path):
    """Audit two serial, search-free handshakes and all fresh preparation pins.

    This reports readiness only. It does not create game evidence or certify a
    future campaign's clocks, cleanup, resource monitoring, or playing strength.
    """
    path = Path(path).resolve()
    checker, errors = AggregateAudit(path.parent), []
    try:
        report = checker.read(path)
        checker.master = report
        require(report["schema_version"] == 1 and report["protocol_id"] == PROTOCOL_ID
                and report["status"] == "checked", "Wrong readiness identity or status")
        require(chess.__version__ == "1.11.2", "Wrong referee version")
        cfg, assets, sources = report["configuration"], report["frozen"], report["sources"]
        expected = {"settings": SETTINGS, "pairs": PAIRS, "games": 2*PAIRS, "shards": SHARDS, "shard_pairs": SHARD_PAIRS,
                    "active_search_workers": SHARDS, "resident_engines": 2*SHARDS, "resource_poll_seconds": 1.,
                    "max_resource_gap_seconds": 5., "seeds": list(SEEDS), "ponder": False, "diagnostics": False}
        require(set(cfg) == set(expected) | {"engines"}
                and all(cfg[key] == value for key, value in expected.items()), "Readiness settings changed")
        require(child_auditor.canonical_digest(cfg) == report["configuration_sha256"], "Readiness configuration hash changed")
        pins = {**{"engine_" + role: sha for role, sha in ENGINE_SHA256.items()}, "network": NETWORK_SHA256,
                **{f"openings_{i}": sha for i, sha in enumerate(opening_sha256(), 1)},
                **{f"smoke_openings_{i}": sha for i, sha in enumerate(smoke_opening_sha256(), 1)}}
        require(set(assets) == set(pins), "Readiness asset membership changed")
        for name, expected_sha in pins.items():
            checker.artifact(assets[name], expected_sha)
        checker.role_asset_paths(assets)
        engines = {entry["role"]: entry for entry in cfg["engines"]}
        require(len(cfg["engines"]) == 2 and set(engines) == set(ROLE_OPTIONS), "Readiness roles changed")
        for role, entry in engines.items():
            require(entry["executable"] == assets["engine_" + role]["path"] and entry["network"] == assets["network"]["path"]
                    and entry["arguments"] == [] and entry["network_option"] == "EvalFile"
                    and entry["extra_options"] == ROLE_OPTIONS[role]
                    and entry["source_revision"] == ROLE_REVISIONS[role], "Readiness options/assets/revisions do not match the before/after NNUE packages")
        require(set(REQUIRED_SOURCES) == set(sources), "Readiness source membership changed")
        validate_build_provenance(sources)
        for name, fingerprint in sources.items():
            source = (ROOT / name).resolve()
            require(not Path(name).is_absolute() and source.is_relative_to(ROOT.resolve()), "Readiness source escapes checkout")
            require(child_auditor.digest(source) == fingerprint["sha256"]
                    and source.stat().st_size == fingerprint["bytes"], "Readiness source changed")
        for name, expected_sha in input_pins().items():
            require(sources[name]["sha256"] == expected_sha, "Readiness preparation pin changed")
        require(report["artifacts_before"] == {"assets": assets, "sources": sources}, "Readiness snapshot disagrees")
        prior, roots, identifiers = checker.prior_roots(), set(), set()
        saved_roots = checker.saved_roots() | smoke_roots()
        for index in range(1, SHARDS+1):
            entries, shard_roots = definitions(checker.read(Path(assets[f"openings_{index}"]["path"])), full_history=True)
            ids = {entry["opening_id"] for entry in entries}
            require(len(entries) == SHARD_PAIRS and not shard_roots & (prior | saved_roots | roots) and not ids & identifiers,
                    "Readiness roots are duplicate, exposed, or incomplete")
            roots.update(shard_roots); identifiers.update(ids)
        preflight = report["preflight"]
        require(preflight["opening_count"] == preflight["distinct_roots"] == len(roots) == PAIRS
                and preflight["previous_root_count"] == len(prior), "Readiness root counts changed")
        checker.preflight_engines()
        require(preflight["smoke_opening_count"] == preflight["smoke_distinct_roots"] == SHARDS,
                "Readiness smoke root counts changed")
        stamp = instant(report["checked_utc"])
        reservation = aggregate_reservation(assets["network"]["bytes"])
        policy = preflight["resource_policy"]
        require(policy["active_search_workers"] == SHARDS and policy["resident_engines"] == 2*SHARDS
                and policy["estimated_memory_bytes"] == reservation
                and policy["memory_estimate_is_hard_cap"] is False
                and checker.budget(policy, stamp, reservation), "Readiness aggregate budget insufficient")
        launch = report["launch_policy"]
        validate_launch_policy(launch, "Readiness")
        if launch["allow_daytime"]:
            require(permitted_launch(stamp.astimezone(ZoneInfo("Europe/Helsinki")), True),
                    "Readiness preflight completed outside its authorized date/window")
    except FAILURES as error:
        errors.append(str(error))
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "readiness_only": True,
            "checked": not errors, "errors": errors, "input_sha256": checker.inputs,
            "audit_tool_sha256": child_auditor.digest(Path(__file__)),
            "note": "Readiness only: zero held-out searches; no campaign launched or strength result."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--campaign", type=Path)
    inputs.add_argument("--preflight", type=Path, help="Audit saved search-free readiness only")
    parser.add_argument("--output", type=Path, help="Fresh JSON file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    if args.output and args.campaign and args.output.resolve().is_relative_to(args.campaign.resolve()):
        parser.error("Audit output must be outside preserved campaign evidence")
    if args.output and args.output.exists():
        parser.error("Output exists; audit evidence is never overwritten")
    result = audit_readiness(args.preflight) if args.preflight else audit(args.campaign)
    encoded = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")
    return int(not result["checked"]) if args.preflight else int(result["decision"] == "invalid_or_incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
