#!/usr/bin/env python3
"""Independently audit the fixed current-engine Phase 4D.2 LMR qualification.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

The original raw-game auditor supplies PGN/UCI/clock verification and paired
statistics. This file independently declares the current experiment and checks
all eight shards together. It never imports launcher configuration or changes
any frozen historical module globals. No automatic default promotion.
"""
from __future__ import annotations

import argparse
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
from audit_phase3l import definitions, instant, root_key

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase4d2-lmr-1024-v1"
PROTOCOL_DOCUMENT = "docs/PHASE_4D2.md"
ENGINE_SHA256 = "bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f"
NETWORK_SHA256 = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
OPENING_SHA256 = (
    '0c8b1eb8979a6e08e700b7ab6bba7cf4ac0595ad3856e0fd157a68df15aba146',
    '43444b4015df6f83764f901426bc6aa88279f5b65b8a863478623be2b898db11',
    '8f2996d663c6178e451e69771a26addb4d52d5cd79becd8467c5e202aec5c234',
    'a3c497666b171cd570ba2f067f0476c6105ea1806e4bb93152fea65252be0101',
    'dbbbc5fcb13a97acb01dac5eb4d065d13db498374da8886bd3dd21f4757925db',
    '52290546a8248a353cac165b5ddecc448ccf42c422b009ac1ef03608deb3cf9d',
    '981b8639a905684a4f87671f0057d1bb8c1c98d77f2c6aea6eec29bf022b07e2',
    '73602f5c204329fbf5c57ca2b90914c4bb9ad834052a1850a0cd879d16d8a5b5',
)
GENERATION_METADATA = "tests/data/phase4d2-generation.json"
EXCLUSIONS = "tests/data/phase4d2-exclusions.json"
GENERATOR = "tools/generate_phase4d2_openings.py"
BUILD_MANIFEST = "build/experiments/phase4d2-20261018/manifest.json"
INPUT_PINS = {
    EXCLUSIONS: "94d17056e1b86ebeb4c8e9801c551df9edd8ee8a33cec4ac74a1db39a8de50ee",
    GENERATION_METADATA: "dae2e9dc2cfbe69b21fd4475caf7c9272bf9cbb038ee26e33e8749859680f367",
    GENERATOR: "63c2feaec89182626316b1294ed33b58aa78d1b33e0dc32ce66cef8f8e29f7e2",
    BUILD_MANIFEST: "918298becbfbcd62148759ea050726bd29070dbad9db66cc22bb8fc91965918c",
}
SHARDS, SHARD_PAIRS, PAIRS = 8, 64, 512
SEEDS = tuple(range(202610184201, 202610184209))
SETTINGS = {"initial": 60.0, "increment": 0.6, "hash_mb": 64, "threads": 1,
            "max_plies": 512, "startup_timeout": 30.0, "protocol_timeout": 5.0,
            "move_overhead_ms": 20, "smoke": False}
ROLE_OPTIONS = {role: {"Time Policy": "classic", "Capture Ordering": "mvv-lva",
                      "Countermove Ordering": "false", "SyzygyProbeLimit": "0", "Late Move Reductions": enabled}
                for role, enabled in (("candidate", "true"), ("opponent", "false"))}
ROLE_REVISIONS = {role: f"phase4d2-lmr-{label}-74a908bb861e8292cdbb10d005410e4364efea5e"
                  for role, label in (("candidate", "on"), ("opponent", "off"))}
REQUIRED_SOURCES = (
    "tools/qualify_phase4d2.py", "tools/audit_phase4d2.py", "tools/qualification.py",
    "tools/qualify_phase3l.py", "tools/audit_phase3l.py", "tools/audit_time_policy.py",
    "tools/match.py", "tools/match_statistics.py", "tools/resources.py", GENERATOR,
    "tests/phase4d2_openings_test.py", "tests/qualify_phase4d2_test.py", "tests/audit_phase4d2_test.py",
    GENERATION_METADATA, EXCLUSIONS, BUILD_MANIFEST, "requirements-match.txt", PROTOCOL_DOCUMENT)
FAILURES = (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError, AttributeError)
require = child_auditor.require


def child_protocol(index):
    require(type(index) is int and 1 <= index <= SHARDS, "Invalid shard index")
    return child_auditor.AuditProtocol(
        protocol_id=f"{PROTOCOL_ID}-shard-{index}", pairs=SHARD_PAIRS, seed=SEEDS[index-1],
        protocol_document=PROTOCOL_DOCUMENT,
        role_options=tuple((role, tuple(options.items())) for role, options in ROLE_OPTIONS.items()),
        required_sources=REQUIRED_SOURCES,
        pinned_sha256=(("engine", ENGINE_SHA256), ("network", NETWORK_SHA256),
                       ("openings", OPENING_SHA256[index-1])),
        entrypoint="tools/audit_phase4d2.py")


def pooled_statistics(records, plan, complete):
    """Pool pair observations, never average shard intervals or select shards."""
    ids = {item["pair_id"] for item in plan}
    require(len(ids) == len(plan), "Duplicate pooled pair identity")
    require(len({item["game_id"] for item in records}) == len(records), "Duplicate pooled game identity")
    require(all(item["pair_id"] in ids for item in records), "Unexpected pooled game")
    eligible = complete and len(plan) == PAIRS and len(records) == 2*PAIRS
    result = child_auditor.statistics_for(records, plan, eligible, PAIRS)
    result.update(recorded_games=len(records), points=math.fsum(p["points"] for p in result["included_pair_scores"]),
                  confidence=.95, method="conditional_two_sided_Hoeffding_on_512_opening_pair_scores",
                  assumptions=["Independent opening-pair observations are required, not established by unique roots.",
                               "Related opening stems and concurrent shared-host load limit independence and generalization.",
                               "Eight shards form one fixed sample; no shard selection or score-based stopping."])
    return result


def classify(statistics, complete, errors, candidate_forfeits):
    if errors or not complete or not statistics.get("inference_eligible"):
        return "invalid_or_incomplete"
    if candidate_forfeits:
        return "operational_regression"
    if statistics["score_interval"]["lower"] > .5 and statistics["score"] >= .5072:
        return "eligible_for_default_review"
    if statistics["score_interval"]["upper"] < .5:
        return "negative_evidence"
    return "inconclusive"


class AggregateAudit:
    """Bind master evidence to eight independently checked raw campaigns."""
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
        expected = {"settings": SETTINGS, "pairs": PAIRS, "games": 2*PAIRS, "shards": SHARDS, "shard_pairs": 64,
                    "active_search_workers": SHARDS, "resident_engines": 2*SHARDS, "resource_poll_seconds": 1.,
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
                    and entry["extra_options"] == ROLE_OPTIONS[role]
                    and entry["source_revision"] == ROLE_REVISIONS[role], "Master options/revisions do not isolate LMR")
        sources = m["sources"]
        require(set(REQUIRED_SOURCES) <= set(sources), "Missing required master source freezes")
        for name, expected_sha in INPUT_PINS.items():
            require(sources[name]["sha256"] == expected_sha, "Unpinned generation, exclusion, or build input")
            require(child_auditor.digest(ROOT / name) == expected_sha, "Pinned preparation input changed")
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
        require(policy["allow_daytime"] is False, "Phase 4D.2 has no daytime exception")
        require(local.hour == 23 and local.minute < 30,
                "Master launch is outside 23:00–23:30 Helsinki")
        require(policy["nighttime"] is True and policy["daytime_authorization"] is None,
                "Master ordinary-night launch carries a daytime exception")
        expected_cutoff = datetime.combine(local.date()+timedelta(days=1), time(7), tzinfo=ZoneInfo("Europe/Helsinki"))
        require(cutoff == expected_cutoff and started <= finished, "Master cutoff/timestamp ordering changed")
        require(instant(policy["cutoff_utc"]) == cutoff == instant(policy["cutoff_local"]), "Master cutoff drift")
        require(instant(policy["local_time"]) == started and policy["remaining_seconds"] > 0, "Master launch policy timestamp changed")
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

    def preflight_engines(self):
        """Verify readiness did not search or inspect any held-out position."""
        engines = self.master["preflight"]["engines"]
        require(len(engines) == 2 and {engine["role"] for engine in engines} == set(ROLE_OPTIONS),
                "Preflight must contain exactly the two engine roles")
        for engine in engines:
            role = engine["role"]
            expected = {"Hash": 64, "Threads": 1, "EvalFile": self.master["frozen"]["network"]["path"],
                        "Move Overhead": 20, "Search Diagnostics": False, "Time Policy": "classic",
                        "Capture Ordering": "mvv-lva", "Countermove Ordering": False, "SyzygyProbeLimit": 0,
                        "SyzygyPath": "", "Late Move Reductions": role == "candidate"}
            require(all(engine["configured"].get(name) == value for name, value in expected.items()),
                    "Preflight applied options differ from the fixed comparison")
            options = engine["options"]
            for name in ("Ponder", "Search Diagnostics", "Late Move Reductions", "Countermove Ordering"):
                require(options[name]["type"] == "check" and options[name]["default"] is False,
                        "Preflight boolean option defaults changed")
            for name, default, choices in (("Time Policy", "classic", {"classic", "forecast"}),
                                          ("Capture Ordering", "mvv-lva", {"mvv-lva", "see"})):
                require(options[name]["type"] == "combo" and options[name]["default"] == default
                        and set(options[name]["var"]) == choices, "Preflight option architecture changed")
            require(options["SyzygyPath"]["type"] == "string" and options["SyzygyPath"]["default"] == "<empty>"
                    and options["SyzygyProbeLimit"]["type"] == "spin" and options["SyzygyProbeLimit"]["min"] == 0
                    and options["SyzygyProbeLimit"]["max"] == 7, "Syzygy option architecture changed")
            sent, received, previous, actual, ready_options = [], [], -1, {}, None
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
                if direction == "from_engine":
                    option = re.match(r"option name (.+?) type (?:spin|check|combo|string) default (.*)", line)
                    if option:
                        actual[option[1]] = re.split(r" (?:min|max|var) ", option[2], maxsplit=1)[0]
                    if line == "readyok":
                        ready_options = actual.copy()
                else:
                    setting = re.fullmatch(r"setoption name (.+?) value (.*)", line)
                    require(line in ("uci", "isready", "quit") or setting is not None,
                            "Unexpected command in search-free readiness")
                    if setting:
                        actual[setting[1]] = setting[2]
                (sent if direction == "to_engine" else received).append(line)
            require("uci" in sent and "isready" in sent and "quit" in sent
                    and "uciok" in received and "readyok" in received, "Incomplete preflight readiness/cleanup transcript")
            expected_actual = {name: str(value).lower() if isinstance(value, bool) else str(value)
                               for name, value in {**expected, "Ponder": False}.items()}
            require(ready_options is not None and all(ready_options.get(name) == value
                    for name, value in expected_actual.items()), "Actual readiness UCI options differ")

    def resource_history(self):
        """Check aggregate reservations and every admission, not eight local budgets."""
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
            require(p["active_search_workers"] == SHARDS and p["resident_engines"] == 2*SHARDS
                    and p["estimated_memory_bytes"] == SHARDS*per_worker and p["memory_estimate_is_hard_cap"] is False,
                    "Resource reservation does not count all shards")
            within = self.budget(p, stamp, SHARDS*per_worker)
            require(event["within_limits"] is within, "Recorded aggregate budget verdict is wrong")
            if m["status"] == "finished":
                require(within, "Completed campaign crossed its resource budget")
            trigger = event["trigger"]
            require(trigger in ("initial", "periodic", "before_game", "final"), "Unknown resource observation trigger")
            if trigger == "before_game":
                key = (event["shard_index"], event["game_id"])
                require(type(key[0]) is int and 1 <= key[0] <= SHARDS and key not in self.admissions,
                        "Duplicate or unknown game admission")
                require(within and stamp < self.cutoff, "Game admitted after cutoff or over budget")
                self.admissions[key] = (stamp, p)
        # Readiness and policy sampling occur at separate instants. A legitimate
        # owner override may change between reads while both still allow 8/16.
        preflight = m["preflight"]["resource_policy"]
        checked = instant(m["checked_utc"])
        require(self.started <= checked <= self.finished, "Preflight timestamp escapes master")
        require(preflight["active_search_workers"] == SHARDS and preflight["resident_engines"] == 2*SHARDS
                and preflight["estimated_memory_bytes"] == SHARDS*per_worker
                and preflight["memory_estimate_is_hard_cap"] is False
                and self.budget(preflight, checked, SHARDS*per_worker), "Invalid aggregate preflight resource reservation")
        if m["status"] == "finished":
            require(any(event["trigger"] == "periodic" for event in history), "Missing periodic resource monitoring")

    @staticmethod
    def budget(policy, observed, aggregate_reservation):
        """Validate one independently sampled policy for all eight active shards."""
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
            require(key not in result and entry["sources"], "Duplicate root or missing exclusion provenance")
            result.add(key)
        require(result, "Empty exposure exclusion manifest")
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
                    and local_policy["estimated_memory_bytes"]*SHARDS == policy["estimated_memory_bytes"]
                    and local_policy["memory_estimate_is_hard_cap"] is False, "Game resource reservation changed")
            require(self.budget(local_policy, game_start, policy["estimated_memory_bytes"]),
                    "Game policy cannot support the entire eight-shard experiment")
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
    for index in range(1, SHARDS+1):
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
        require(len(reports) == SHARDS and len(roots) == len(ids) == PAIRS, "Not all eight distinct opening shards audited")
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
    complete = complete and not errors
    stats = pooled_statistics([], [], False)
    try:
        stats = pooled_statistics(checker.records, checker.plans, complete)
    except FAILURES as error:
        errors.append(f"statistics: {error}"); complete = False
    forfeits = {role: sum(record.get("termination") == "time_forfeit" and record.get("clock_loser") == role
                         for record in checker.records) for role in ROLE_OPTIONS}
    decision = classify(stats, complete, errors, forfeits["candidate"])
    return {"schema_version": 1, "protocol_id": PROTOCOL_ID, "campaign": str(checker.campaign),
            "audited_utc": datetime.now(timezone.utc).isoformat(),
            "audit_tool_sha256": child_auditor.digest(Path(__file__)),
            "raw_audit_tool_sha256": child_auditor.digest(Path(child_auditor.__file__)),
            "decision": decision, "complete": complete, "default_change": False, "errors": errors,
            "statistics": stats, "shards": reports, "candidate_time_forfeits": forfeits["candidate"],
            "opponent_time_forfeits": forfeits["opponent"], "input_sha256": checker.inputs,
            "live_source_differences": sorted(set(checker.live_source_differences)),
            "note": "One fixed 1024-game qualification. A positive result permits conditional default review, not automatic promotion or a general Elo claim."}


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
        expected = {"settings": SETTINGS, "pairs": PAIRS, "games": 2*PAIRS, "shards": SHARDS, "shard_pairs": 64,
                    "active_search_workers": SHARDS, "resident_engines": 2*SHARDS, "resource_poll_seconds": 1.,
                    "max_resource_gap_seconds": 5., "seeds": list(SEEDS), "ponder": False, "diagnostics": False}
        require(set(cfg) == set(expected) | {"engines"}
                and all(cfg[key] == value for key, value in expected.items()), "Readiness settings changed")
        require(child_auditor.canonical_digest(cfg) == report["configuration_sha256"], "Readiness configuration hash changed")
        pins = {"engine": ENGINE_SHA256, "network": NETWORK_SHA256,
                **{f"openings_{i}": sha for i, sha in enumerate(OPENING_SHA256, 1)}}
        require(set(assets) == set(pins), "Readiness asset membership changed")
        for name, expected_sha in pins.items():
            checker.artifact(assets[name], expected_sha)
        engines = {entry["role"]: entry for entry in cfg["engines"]}
        require(len(cfg["engines"]) == 2 and set(engines) == set(ROLE_OPTIONS), "Readiness roles changed")
        for role, entry in engines.items():
            require(entry["executable"] == assets["engine"]["path"] and entry["network"] == assets["network"]["path"]
                    and entry["arguments"] == [] and entry["network_option"] == "EvalFile"
                    and entry["extra_options"] == ROLE_OPTIONS[role]
                    and entry["source_revision"] == ROLE_REVISIONS[role], "Readiness options/assets/revisions do not isolate LMR")
        require(set(REQUIRED_SOURCES) == set(sources), "Readiness source membership changed")
        for name, fingerprint in sources.items():
            source = (ROOT / name).resolve()
            require(not Path(name).is_absolute() and source.is_relative_to(ROOT.resolve()), "Readiness source escapes checkout")
            require(child_auditor.digest(source) == fingerprint["sha256"]
                    and source.stat().st_size == fingerprint["bytes"], "Readiness source changed")
        for name, expected_sha in INPUT_PINS.items():
            require(sources[name]["sha256"] == expected_sha, "Readiness preparation pin changed")
        require(report["artifacts_before"] == {"assets": assets, "sources": sources}, "Readiness snapshot disagrees")
        prior, roots, identifiers = checker.prior_roots(), set(), set()
        for index in range(1, SHARDS+1):
            entries, shard_roots = definitions(checker.read(Path(assets[f"openings_{index}"]["path"])), full_history=True)
            ids = {entry["opening_id"] for entry in entries}
            require(len(entries) == 64 and not shard_roots & (prior | roots) and not ids & identifiers,
                    "Readiness roots are duplicate, exposed, or incomplete")
            roots.update(shard_roots); identifiers.update(ids)
        preflight = report["preflight"]
        require(preflight["opening_count"] == preflight["distinct_roots"] == len(roots) == PAIRS
                and preflight["previous_root_count"] == len(prior), "Readiness root counts changed")
        checker.preflight_engines()
        stamp = instant(report["checked_utc"])
        per_worker = 2*64*1024**2 + 8*assets["network"]["bytes"] + 256*1024**2
        policy = preflight["resource_policy"]
        require(policy["active_search_workers"] == SHARDS and policy["resident_engines"] == 2*SHARDS
                and policy["estimated_memory_bytes"] == SHARDS*per_worker
                and policy["memory_estimate_is_hard_cap"] is False
                and checker.budget(policy, stamp, SHARDS*per_worker), "Readiness aggregate budget insufficient")
        launch = report["launch_policy"]
        require(launch["allow_daytime"] is False and launch["daytime_authorization"] is None,
                "Readiness inherited a daytime exception")
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
