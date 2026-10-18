#!/usr/bin/env python3
"""Independently audit the entire fixed Phase 3G screen without running engines.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Four execution shards form one 256-pair experiment. No shard may be selected,
replaced, or independently promoted. Historical raw-game auditing is reused;
the master expectations and pooled calculation do not import the launcher.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
from zoneinfo import ZoneInfo

import chess
import audit_time_policy as child_auditor

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase3g-lmr-512-v2"
DAYTIME_AUTHORIZATION = "owner-20261018-phase3g"
PROTOCOL_DOCUMENT = "docs/PHASE_3G.md"
ENGINE_SHA256 = "edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
OPENING_SHA256 = ("e40da564ea899dacdbfce4ab2fc92fb0caf42c14d630de1a065d7cf75f822b97",
                  "6ea77165730e2aa5d5d9243649af6297fe3683877ca2736c5c119e6deed6c7d2",
                  "3de297a67e0423299b715e7ce7c71102317277fc627ce52d0fef13ed6f7ae2c9",
                  "7a2670d433329dc46e6536202c2a87e964d00dcb5683123a3ca563979da2efe1")
GENERATION_METADATA = "tests/data/openings-phase3g-generation.json"
GENERATION_SHA256 = "b9677909d8d31365725880badd55e9c5d67089efdb3628af0761b96d56e98669"
SEEDS = (202610181, 202610182, 202610183, 202610184)
SETTINGS = {"initial": 60.0, "increment": 0.6, "hash_mb": 64, "threads": 1,
            "max_plies": 512, "startup_timeout": 30.0, "protocol_timeout": 5.0,
            "move_overhead_ms": 20, "smoke": False}
ROLE_OPTIONS = {
    role: {"Time Policy": "classic", "Capture Ordering": "mvv-lva",
           "Late Move Reductions": enabled}
    for role, enabled in (("candidate", "true"), ("opponent", "false"))}
PRIOR_SUITE_SHA256 = {
    "tests/data/openings-development.json": "5cedc1469a43cb7e36dac9ab50379dd42626f9251409f5ad14f4b59919b5ea47",
    "tests/data/openings-validation.json": "47b2f96c4de46c73e81c3c9561ea32c138648e0512f95d5c85f53f3403002e6c",
    "tests/data/openings-time-validation.json": "163bf4c34547a838c35e03103401c40d448a2f78c535254bf3727913b007b95b",
    "tests/data/openings-lmr-validation.json": "1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7",
    "tests/data/performance-gamephases.json": "38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c"}
REQUIRED_SOURCES = (
    "tools/qualify_phase3g.py", "tools/audit_phase3g.py", "tools/qualification.py",
    "tools/audit_time_policy.py", "tools/match.py", "tools/match_statistics.py",
    "tools/resources.py", "tools/generate_phase3g_openings.py", "tests/phase3g_openings_test.py",
    GENERATION_METADATA, "requirements-match.txt", PROTOCOL_DOCUMENT,
    *PRIOR_SUITE_SHA256)
FAILURES = (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError, AttributeError)
require = child_auditor.require


def child_protocol(index):
    """Declare each shard independently of its launcher or saved manifest."""
    require(type(index) is int and 1 <= index <= 4, "Invalid shard index")
    return child_auditor.AuditProtocol(
        protocol_id=f"{PROTOCOL_ID}-shard-{index}", pairs=64, seed=SEEDS[index-1],
        protocol_document=PROTOCOL_DOCUMENT,
        role_options=tuple((role, tuple(options.items())) for role, options in ROLE_OPTIONS.items()),
        required_sources=REQUIRED_SOURCES,
        pinned_sha256=(("engine", ENGINE_SHA256), ("network", NETWORK_SHA256),
                       ("openings", OPENING_SHA256[index-1])),
        entrypoint="tools/audit_phase3g.py")


def instant(value):
    """Reject ambiguous wall times; compare timezone-aware UTC instants."""
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, "Timestamp lacks timezone")
    return result.astimezone(timezone.utc)


def root_key(board):
    """Use legal en-passant rights and ignore the two move counters."""
    return " ".join(board.fen(en_passant="legal").split()[:4])


def definitions(document, *, full_history):
    """Referee-only replay of original histories, with no engine evaluation."""
    entries, roots, identifiers = [], set(), set()
    for entry in document["openings"]:
        identifier, moves = entry["id"], entry["moves"]
        require(isinstance(identifier, str) and identifier and identifier not in identifiers,
                "Duplicate or missing opening identifier")
        identifiers.add(identifier)
        require(isinstance(moves, list) and all(isinstance(move, str) for move in moves),
                "Opening history is not a move list")
        board = chess.Board(entry.get("fen", chess.STARTING_FEN))
        starting = board.fen()
        require(board.is_valid(), "Invalid opening starting position")
        if full_history:
            require(starting == chess.STARTING_FEN and moves, "Fresh openings require full initial-position histories")
        for token in moves:
            require(board.outcome(claim_draw=True) is None, "Opening continues after a terminal or claimable position")
            board.push_uci(token)
        require(board.is_valid() and board.outcome(claim_draw=True) is None, "Invalid or terminal opening root")
        key = root_key(board)
        require(key not in roots, "Duplicate canonical opening root")
        roots.add(key)
        opening_key = hashlib.sha256(json.dumps({"fen": starting, "moves": moves}, sort_keys=True).encode()).hexdigest()
        entries.append({"opening_id": identifier, "opening_key": opening_key,
                        "starting_fen": starting, "moves": moves})
    return entries, roots


def pooled_statistics(records, plan, complete):
    """Compute all pair observations directly, never average shard intervals."""
    groups = {}
    for record in records:
        groups.setdefault(record["pair_id"], []).append(record)
    included, excluded, counts = [], [], Counter(wins=0, draws=0, losses=0)
    histogram = {f"{value/2:.1f}": 0 for value in range(5)}
    for pair in plan:
        games = groups.get(pair["pair_id"], [])
        if (len(games) != 2 or any(game.get("status") != "complete" for game in games)
                or {game.get("candidate_color") for game in games} != {"white", "black"}):
            excluded.append(pair["pair_id"])
            continue
        points = []
        for game in games:
            require(game["opening_key"] == pair["opening_key"], "Pooled opening identity mismatch")
            white = {"1-0": 1., "1/2-1/2": .5, "0-1": 0.}[game["result"]]
            score = white if game["candidate_color"] == "white" else 1-white
            require(game["candidate_score"] == score, "Pooled score differs from PGN result")
            points.append(score)
            counts["wins" if score == 1 else "losses" if score == 0 else "draws"] += 1
        total = math.fsum(points)
        histogram[f"{total:.1f}"] += 1
        included.append({"pair_id": pair["pair_id"], "opening_key": pair["opening_key"],
                         "points": total, "score": total/2})
    score = math.fsum(pair["score"] for pair in included)/len(included) if included else None
    eligible = complete and len(plan) == len(included) == 256 and len(records) == 512 and not excluded
    radius = math.sqrt(math.log(40)/512) if eligible else None
    return {"wdl": dict(counts), "pair_point_counts": histogram,
            "points": math.fsum(pair["points"] for pair in included), "score": score,
            "included_pairs": len(included), "excluded_pairs": len(excluded),
            "included_games": 2*len(included), "recorded_games": len(records),
            "included_pair_scores": included, "excluded_pair_ids": excluded,
            "inference_eligible": eligible, "confidence": .95, "radius": radius,
            "score_interval": {"lower": max(0., score-radius), "upper": min(1., score+radius)} if eligible else None,
            "method": "conditional_two_sided_Hoeffding_on_256_opening_pair_scores",
            "assumptions": ["Independent opening-pair observations are required and not proved by unique roots.",
                            "Related families and concurrent shared-host load limit independence and generalization.",
                            "This is one fixed sample; shards are execution partitions, not independent qualifying tests."]}


class AggregateAudit:
    """Bind master evidence to four independently checked raw campaigns."""
    def __init__(self, campaign):
        self.campaign = Path(campaign).resolve()
        self.inputs, self.live_source_differences = {}, []
        self.master, self.plans, self.records, self.admissions = None, [], [], {}
        self.child_windows, self.evidence_paths = {}, set()
        self.observations, self.game_windows = [], []

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

    def master_manifest(self):
        m = self.read(self.local("campaign.json"))
        self.master = m
        require(m["schema_version"] == 1 and m["protocol_id"] == PROTOCOL_ID, "Wrong master protocol")
        require(chess.__version__ == "1.11.2", "Wrong referee version")
        cfg = m["configuration"]
        expected = {"settings": SETTINGS, "pairs": 256, "games": 512, "shards": 4, "shard_pairs": 64,
                    "active_search_workers": 4, "resident_engines": 8, "resource_poll_seconds": 1.,
                    "max_resource_gap_seconds": 5.,
                    "seeds": list(SEEDS), "ponder": False, "diagnostics": False}
        require(set(cfg) == set(expected)|{"engines"}, "Unexpected master configuration fields")
        require(all(cfg[key] == value for key, value in expected.items()), "Master sample/settings changed")
        require(child_auditor.canonical_digest(cfg) == m["configuration_sha256"], "Master configuration digest mismatch")
        assets = m["frozen"]
        pins = {"engine": ENGINE_SHA256, "network": NETWORK_SHA256,
                **{f"openings_{i}": sha for i, sha in enumerate(OPENING_SHA256, 1)}}
        require(set(assets) == set(pins), "Unexpected frozen asset membership")
        for name, expected_sha in pins.items():
            self.artifact(assets[name], expected_sha)
        engines = {entry["role"]: entry for entry in cfg["engines"]}
        require(len(cfg["engines"]) == 2 and set(engines) == set(ROLE_OPTIONS), "Invalid master roles")
        for role, entry in engines.items():
            require(entry["executable"] == assets["engine"]["path"] and entry["network"] == assets["network"]["path"],
                    "Master roles do not share frozen assets")
            require(entry["arguments"] == [] and entry["network_option"] == "EvalFile"
                    and entry["extra_options"] == ROLE_OPTIONS[role], "Master options do not isolate LMR")
        sources = m["sources"]
        require(set(REQUIRED_SOURCES) <= set(sources), "Missing required master source freezes")
        require(sources[GENERATION_METADATA]["sha256"] == GENERATION_SHA256, "Unpinned generation metadata")
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
        local = started.astimezone(ZoneInfo("Europe/Helsinki"))
        policy = m["launch_policy"]
        require(policy["timezone"] == "Europe/Helsinki" and type(policy["allow_daytime"]) is bool,
                "Master launch timezone or permission type changed")
        if policy["allow_daytime"]:
            # The owner's one-run exception changes launch permission only. It
            # cannot authorize another date, a nighttime override, or a larger
            # resource budget; the latter remains independently checked below.
            require(local.date().isoformat() == "2026-10-18" and 7 <= local.hour < 23,
                    "Master daytime launch is outside the authorized Helsinki date/window")
            require(policy["nighttime"] is False and policy["daytime_authorization"] == DAYTIME_AUTHORIZATION,
                    "Master daytime launch lacks the recorded owner authorization")
        else:
            require(local.hour == 23 and local.minute < 15,
                    "Master launch is outside 23:00–23:15 Helsinki")
            require(policy["nighttime"] is True and policy["daytime_authorization"] is None,
                    "Master ordinary-night launch carries a daytime exception")
        expected_cutoff = datetime.combine(local.date()+timedelta(days=1), time(7), tzinfo=ZoneInfo("Europe/Helsinki"))
        require(cutoff == expected_cutoff and started <= finished, "Master cutoff/timestamp ordering changed")
        require(instant(policy["cutoff_utc"]) == cutoff == instant(policy["cutoff_local"]), "Master cutoff drift")
        require(instant(policy["local_time"]) == started and policy["remaining_seconds"] > 0, "Master launch policy timestamp changed")
        if m["status"] == "finished":
            require(finished <= cutoff, "Finished master exceeded cutoff")
        require(m["preflight"]["opening_count"] == m["preflight"]["distinct_roots"] == 256
                and m["preflight"]["previous_root_count"] == 120, "Master preflight root counts changed")
        self.preflight_engines()
        expected_shards = [{"index": i, "protocol_id": f"{PROTOCOL_ID}-shard-{i}", "seed": SEEDS[i-1],
                            "path": f"shard-{i}", "openings": assets[f"openings_{i}"]} for i in range(1, 5)]
        require(m["shards"] == expected_shards, "Shard membership, path or seed changed")
        self.started, self.finished, self.cutoff = started, finished, cutoff
        self.resource_history()

    def preflight_engines(self):
        """Verify readiness did not search or inspect any held-out position."""
        engines = self.master["preflight"]["engines"]
        require(len(engines) == 2 and {engine["role"] for engine in engines} == set(ROLE_OPTIONS),
                "Preflight must contain exactly the two engine roles")
        for engine in engines:
            role = engine["role"]
            expected = {"Hash": 64, "Threads": 1, "EvalFile": self.master["frozen"]["network"]["path"],
                        "Move Overhead": 20, "Search Diagnostics": False, "Time Policy": "classic",
                        "Capture Ordering": "mvv-lva", "Late Move Reductions": role == "candidate"}
            require(all(engine["configured"].get(name) == value for name, value in expected.items()),
                    "Preflight applied options differ from the fixed comparison")
            options = engine["options"]
            for name in ("Ponder", "Search Diagnostics", "Late Move Reductions"):
                require(options[name]["type"] == "check" and options[name]["default"] is False,
                        "Preflight boolean option defaults changed")
            for name, default, choices in (("Time Policy", "classic", {"classic", "forecast"}),
                                          ("Capture Ordering", "mvv-lva", {"mvv-lva", "see"})):
                require(options[name]["type"] == "combo" and options[name]["default"] == default
                        and set(options[name]["var"]) == choices, "Preflight option architecture changed")
            sent, received, previous = [], [], -1
            for event in engine["transcript"]:
                require(event["engine"] == role and event["monotonic_ns"] >= previous,
                        "Preflight role/timestamps changed")
                previous = event["monotonic_ns"]
                line, direction = event["line"], event["direction"]
                require(direction in ("to_engine", "from_engine"), "Unexpected preflight stderr/direction")
                require(line not in ("position", "go", "bestmove") and not line.startswith(("position ", "go ", "bestmove ")),
                        "Preflight searched or exposed an opening")
                require(not line.lower().startswith(("info string error:", "info string search error:")),
                        "Preflight engine reported an error")
                (sent if direction == "to_engine" else received).append(line)
            require("uci" in sent and "isready" in sent and "quit" in sent
                    and "uciok" in received and "readyok" in received, "Incomplete preflight readiness/cleanup transcript")

    def resource_history(self):
        """Check aggregate reservations and every admission, not four local budgets."""
        m = self.master
        per_worker = 2*64*1024**2 + 8*m["frozen"]["network"]["bytes"] + 256*1024**2
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
            require(p["active_search_workers"] == 4 and p["resident_engines"] == 8
                    and p["estimated_memory_bytes"] == 4*per_worker and p["memory_estimate_is_hard_cap"] is False,
                    "Resource reservation does not count all shards")
            within = self.budget(p, stamp, 4*per_worker)
            require(event["within_limits"] is within, "Recorded aggregate budget verdict is wrong")
            if m["status"] == "finished":
                require(within, "Completed campaign crossed its resource budget")
            trigger = event["trigger"]
            require(trigger in ("initial", "periodic", "before_game", "final"), "Unknown resource observation trigger")
            if trigger == "before_game":
                key = (event["shard_index"], event["game_id"])
                require(type(key[0]) is int and 1 <= key[0] <= 4 and key not in self.admissions,
                        "Duplicate or unknown game admission")
                require(within and stamp < self.cutoff, "Game admitted after cutoff or over budget")
                self.admissions[key] = (stamp, p)
        # Readiness and policy sampling occur at separate instants. A legitimate
        # owner override may change between reads while both still allow 4/8.
        preflight = m["preflight"]["resource_policy"]
        checked = instant(m["checked_utc"])
        require(self.started <= checked <= self.finished, "Preflight timestamp escapes master")
        require(preflight["active_search_workers"] == 4 and preflight["resident_engines"] == 8
                and preflight["estimated_memory_bytes"] == 4*per_worker
                and preflight["memory_estimate_is_hard_cap"] is False
                and self.budget(preflight, checked, 4*per_worker), "Invalid aggregate preflight resource reservation")
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
        return 4 <= p["max_cpu_workers"] and aggregate_reservation <= memory*p["memory_fraction"]

    def prior_roots(self):
        result, count = set(), 0
        for name, expected in PRIOR_SUITE_SHA256.items():
            require(self.master["sources"][name]["sha256"] == expected, "Prior suite reference is not independently pinned")
            path = ROOT/name
            require(child_auditor.digest(path) == expected, "Prior suite reference changed")
            _, roots = definitions(self.read(path), full_history=False)
            if "performance-gamephases" not in name:
                count += len(roots)
            result.update(roots)
        require(count == 120, "Expected 120 exposed match roots")
        return result

    def shard(self, index, prior, seen_roots, seen_ids):
        """Validate child/master binding and reconstruct the global full schedule."""
        directory = self.local(f"shard-{index}")
        require(directory == self.campaign/f"shard-{index}" and not directory.is_symlink(), "Shard directory aliases another path")
        launch = self.read(directory/"launch.json")
        m, asset = self.master, self.master["frozen"][f"openings_{index}"]
        require(launch["assets"] == {"engine": m["frozen"]["engine"], "network": m["frozen"]["network"], "openings": asset},
                "Child artifacts differ from master")
        require(launch["sources"] == m["sources"], "Child source freeze differs from master")
        require(launch["preflight"]["engines"] == m["preflight"]["engines"], "Child readiness does not match shared preflight")
        cfg = launch["configuration"]
        require(cfg == {"pairs": 64, "seed": SEEDS[index-1], "settings": SETTINGS, "engines": m["configuration"]["engines"],
                        "ponder": False, "diagnostics": False}, "Child configuration differs from master")
        start, end = instant(launch["started_utc"]), instant(launch["finished_utc"])
        require(self.started <= start <= end <= self.finished, "Child window escapes master")
        child_policy, master_policy = launch["launch_policy"], m["launch_policy"]
        require(instant(child_policy["cutoff_utc"]) == self.cutoff
                and child_policy["allow_daytime"] is master_policy["allow_daytime"]
                and child_policy["daytime_authorization"] == master_policy["daytime_authorization"],
                "Child cutoff/daytime authorization differs from master")
        if launch["status"] == "finished":
            require(end <= self.cutoff, "Completed child exceeded common cutoff")
        self.child_windows[index] = (start, end)
        definitions_list, roots = definitions(self.read(Path(asset["path"])), full_history=True)
        require(len(definitions_list) == 64 and not roots & (prior|seen_roots), "Fresh roots duplicate or overlap exposed evidence")
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
        require(len(records) <= 128, "Too many games in shard")
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
                    and local_policy["estimated_memory_bytes"]*4 == policy["estimated_memory_bytes"]
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


def audit(campaign):
    """Return descriptive incomplete evidence, with inference withheld on any error."""
    checker, errors, reports = AggregateAudit(campaign), [], []
    master_valid = False
    try:
        checker.master_manifest()
        prior = checker.prior_roots()
        master_valid = True
    except FAILURES as error:
        errors.append(f"master: {error}")
        prior = set()
    roots, ids = set(), set()
    for index in range(1, 5):
        try:
            directory = checker.local(f"shard-{index}")
            require(directory == checker.campaign/f"shard-{index}", "Shard path aliases another directory")
            raw = child_auditor.audit(directory, child_protocol(index))
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
        require(len(reports) == 4 and len(roots) == len(ids) == 256, "Not all four distinct opening shards audited")
        require(len(checker.admissions) == 512, "Missing or excess aggregate game admissions")
        statuses = master["shard_statuses"]
        require(len(statuses) == 4 and [s["index"] for s in statuses] == [1, 2, 3, 4], "Shard completion membership changed")
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
    complete = complete and not errors
    stats = pooled_statistics([], [], False)
    try:
        stats = pooled_statistics(checker.records, checker.plans, complete)
    except FAILURES as error:
        errors.append(f"statistics: {error}"); complete = False
    forfeits = {role: sum(record.get("termination") == "time_forfeit" and record.get("clock_loser") == role
                         for record in checker.records) for role in ROLE_OPTIONS}
    decision = child_auditor.classify(stats, complete, errors, forfeits["candidate"])
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "campaign": str(checker.campaign),
            "audited_utc": datetime.now(timezone.utc).isoformat(),
            "audit_tool_sha256": child_auditor.digest(Path(__file__)),
            "raw_audit_tool_sha256": child_auditor.digest(Path(child_auditor.__file__)),
            "decision": decision, "complete": complete, "default_change": False, "errors": errors,
            "statistics": stats, "shards": reports, "candidate_time_forfeits": forfeits["candidate"],
            "opponent_time_forfeits": forfeits["opponent"], "input_sha256": checker.inputs,
            "live_source_differences": sorted(set(checker.live_source_differences)),
            "note": "One fixed 512-game screen. A positive result permits fresh confirmation review, not automatic default promotion or an Elo claim."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Fresh JSON file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error("Output exists; audit evidence is never overwritten")
    result = audit(args.campaign)
    encoded = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    else:
        print(encoded, end="")
    return int(result["decision"] == "invalid_or_incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
