#!/usr/bin/env python3
"""Data-only master-audit checks and real raw-child replay corruption checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Aggregate fixtures mock only the expensive raw-child auditor; they still use
2048 records, 1024 independently replayed full legal histories, real files and
hashes, and complete schedules/resource admissions. Separate raw-child tests
exercise the actual inherited PGN/UCI verifier. No engine process is started.
"""
import copy
from datetime import datetime, time, timedelta, timezone
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import audit_phase4f13 as auditor
import chess
import chess.pgn
from match_statistics import summarize_pairs
import audit_phase4f13_games as raw_auditor

REPO = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n")


def jsonl(path, values):
    path.write_text("".join(json.dumps(value)+"\n" for value in values))


def asset(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


class AggregateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Original synthetic legal histories, generated with rules only. They
        # are not qualification inputs and never selected by engine evaluation.
        rng, roots, entries = random.Random(1772026), set(), []
        while len(entries) < 1024:
            board, moves = chess.Board(), []
            for _ in range(6):
                if board.outcome(claim_draw=True):
                    break
                move = rng.choice(list(board.legal_moves)); moves.append(move.uci()); board.push(move)
            key = auditor.root_key(board)
            if len(moves) == 6 and not board.outcome(claim_draw=True) and key not in roots:
                roots.add(key)
                entries.append({"id": f"synthetic-full-history-{len(entries)+1}", "moves": moves})
        cls.entries = entries

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase4f13-audit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.campaign = self.root/"campaign"; self.campaign.mkdir()
        self.engines = {role: self.root/name for role, name in auditor.FROZEN_ENGINES.items()}
        for role, path in self.engines.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic never executed " + role).encode())
        self.network = self.root/"network"; self.network.write_bytes(b"synthetic never loaded")
        sources = {}
        for name in auditor.REQUIRED_SOURCES:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic source\n")
            if name == auditor.EXCLUSIONS:
                write_json(path, {"roots": [{"root_key": auditor.root_key(chess.Board()),
                                             "sources": ["synthetic-start"]}]})
            if name == auditor.GENERATION_METADATA:
                write_json(path, {"sources": [], "saved_game_unique_roots": 0})
            sources[name] = {key: value for key, value in asset(path).items() if key != "path"}
        assets = {**{"engine_" + role: asset(path) for role, path in self.engines.items()}, "network": asset(self.network)}
        for index in range(1, 5):
            path = self.root/f"tests/data/phase4f13-match-{index:02d}.json"
            write_json(path, {"openings": self.entries[(index-1)*256:index*256]})
            assets[f"openings_{index}"] = asset(path)
            sources[str(path.relative_to(self.root))] = {key: value for key, value in asset(path).items() if key != "path"}
        catalog = json.loads((REPO/auditor.SMOKE_CATALOG).read_text())
        write_json(self.root/auditor.SMOKE_CATALOG, catalog)
        sources[auditor.SMOKE_CATALOG] = {key: value for key,value in asset(self.root/auditor.SMOKE_CATALOG).items() if key != "path"}
        selected = {entry["id"]: entry for entry in catalog["openings"]}
        for index, identifier in enumerate(auditor.SMOKE_DEVELOPMENT_IDS, 1):
            name = f"tests/data/phase4f13-match-smoke-{index:02d}.json"
            path = self.root/name
            write_json(path, {"openings": [selected[identifier]]})
            assets[f"smoke_openings_{index}"] = asset(path)
            sources[name] = {key: value for key,value in asset(path).items() if key != "path"}
        for name, value in (("ROOT", self.root), ("ENGINE_SHA256", {role: assets["engine_" + role]["sha256"] for role in self.engines}),
                            ("NETWORK_SHA256", assets["network"]["sha256"])):
            p = patch.object(auditor, name, value); p.start(); self.addCleanup(p.stop)
        for role, folder in auditor.BUILD_ROOTS.items():
            original = {name.split("/source/", 1)[1]: sources[name]["sha256"] for name in auditor.BUILD_SOURCE_NAMES
                        if name.startswith(folder + "/source/")}
            if role == "opponent":
                origin = {"parent_commit": auditor.ROLE_REVISIONS[role],
                          "binary": {"sha256": assets["engine_"+role]["sha256"], "flags": auditor.COMPILE_FLAGS},
                          "network_sha256": assets["network"]["sha256"], "sources": original}
            else:
                origin = {"candidate_sha256": assets["engine_candidate"]["sha256"],
                          "baseline_sha256": assets["engine_opponent"]["sha256"],
                          "oracle_report_sha256": "f"*64, "source_sha256": original}
            origin_name = auditor.ORIGIN_MANIFESTS[role]
            write_json(self.root/origin_name, origin)
            sources[origin_name] = {key: value for key, value in asset(self.root/origin_name).items() if key != "path"}
            manifest = {"schema_version": 1, "role": "baseline" if role == "opponent" else "candidate",
                        "engine_source_revision": auditor.ROLE_REVISIONS[role],
                        "binary_sha256": assets["engine_"+role]["sha256"], "network_sha256": assets["network"]["sha256"],
                        "compile_flags": auditor.COMPILE_FLAGS,
                        "source_sha256": {folder+"/source/"+name: sha for name,sha in original.items()},
                        "origin_manifest": origin_name, "origin_manifest_sha256": sources[origin_name]["sha256"],
                        "build_log": auditor.BUILD_LOGS[role], "build_log_sha256": sources[auditor.BUILD_LOGS[role]]["sha256"]}
            name = auditor.BUILD_MANIFESTS[role]
            write_json(self.root/name, manifest)
            sources[name] = {key: value for key, value in asset(self.root/name).items() if key != "path"}
        fixed_manifests = {role: sources[name]["sha256"] for role, name in auditor.BUILD_MANIFESTS.items()}
        p = patch.object(auditor, "BUILD_MANIFEST_SHA256", fixed_manifests); p.start(); self.addCleanup(p.stop)
        pins = {name: asset(self.root/name)["sha256"] for name in auditor.PINNED_INPUTS}
        for name, value in (("input_pins", pins), ("opening_sha256", tuple(assets[f"openings_{i}"]["sha256"] for i in range(1, 5)))):
            p = patch.object(auditor, name, return_value=value); p.start(); self.addCleanup(p.stop)
        self.start = datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc)
        self.end = self.start+timedelta(minutes=20)
        cutoff = self.start+timedelta(hours=8)
        self.cfg = {"settings": dict(auditor.SETTINGS), "pairs": 1024, "games": 2048, "shards": 4,
                    "shard_pairs": 256, "active_search_workers": 4, "resident_engines": 8,
                    "resource_poll_seconds": 1., "max_resource_gap_seconds": 5., "seeds": list(auditor.SEEDS), "ponder": False,
                    "diagnostics": False, "engines": [
                        {"role": role, "executable": str(self.engines[role]), "network": str(self.network),
                         "network_option": "EvalFile", "arguments": [], "source_revision": auditor.ROLE_REVISIONS[role],
                         "extra_options": options} for role, options in auditor.ROLE_OPTIONS.items()]}
        self.policy = {"timezone": "Europe/Helsinki", "local_time": self.start.isoformat(), "source": "nighttime",
                       "percent": 80, "logical_cpus": 18, "max_cpu_workers": 14, "memory_fraction": .8,
                       "active_search_workers": 4, "resident_engines": 8,
                       "estimated_memory_bytes": auditor.aggregate_reservation(self.network.stat().st_size),
                       "physical_memory_bytes": 64*1024**3, "memory_estimate_is_hard_cap": False}
        self.history = [{"observed_utc": self.start.isoformat(), "trigger": "initial",
                         "policy": copy.deepcopy(self.policy), "within_limits": True}]
        ready_engines = []
        for role in auditor.ROLE_OPTIONS:
            configured = auditor.expected_options(role, self.network)
            options = {name: {"type": "check", "default": name == "Late Move Reductions"}
                       for name in ("Ponder", "Search Diagnostics", *auditor.CHECK_OPTIONS)}
            options.update({"Time Policy": {"type": "combo", "default": "classic", "var": ["classic", "forecast", "bounded"]},
                            "Capture Ordering": {"type": "combo", "default": "mvv-lva", "var": ["mvv-lva", "see"]},
                            "SyzygyPath": {"type": "string", "default": "<empty>"},
                            "EvalFile": {"type": "string", "default": "nn-1a298aa575a0.nnue"},
                            "Clear Hash": {"type": "button"}})
            for name, default, low, high in (("Hash", 64, 1, 16384), ("Threads", 1, 1, 64),
                                           ("Move Overhead", 20, 0, 5000), ("SyzygyProbeLimit", 7, 0, 7),
                                           ("SyzygyProbeDepth", 1, 1, 128)):
                options[name] = {"type": "spin", "default": default, "min": low, "max": high}
            commands = [("to_engine", "uci")]
            for name, option in options.items():
                line = f"option name {name} type {option['type']}"
                for field in ("default", "min", "max"):
                    if field in option:
                        value = option[field]
                        text = str(value).lower() if isinstance(value, bool) else str(value)
                        line += f" {field} {text}"
                for value in option.get("var", ()):
                    line += f" var {value}"
                commands.append(("from_engine", line))
            commands.append(("from_engine", "uciok"))
            for name, value in configured.items():
                text = str(value).lower() if isinstance(value, bool) else str(value)
                commands.append(("to_engine", f"setoption name {name} value {text}"))
            commands.extend((("to_engine", "isready"), ("from_engine", "readyok"), ("to_engine", "quit")))
            transcript = [{"engine": role, "direction": direction, "line": line, "monotonic_ns": tick}
                          for tick, (direction, line) in enumerate(commands, 1)]
            ready_engines.append({"role": role, "pid": 101 if role == "candidate" else 102, "returncode": 0,
                                  "configured": configured, "options": options, "transcript": transcript})
        self.master = {"schema_version": 1, "protocol_id": auditor.PROTOCOL_ID, "status": "finished", "quiet_host": True,
                       "started_utc": self.start.isoformat(), "checked_utc": self.start.isoformat(),
                       "finished_utc": self.end.isoformat(), "cutoff_utc": cutoff.isoformat(),
                       "launch_policy": {"timezone": "Europe/Helsinki", "local_time": self.start.isoformat(),
                                         "nighttime": True, "allow_daytime": False, "cutoff_utc": cutoff.isoformat(),
                                         "daytime_authorization": None,
                                         "cutoff_local": cutoff.isoformat(), "remaining_seconds": 28800.,
                                         "launch_window": "23:00–23:30 Europe/Helsinki", "launch_permitted": True},
                       "configuration": self.cfg, "configuration_sha256": auditor.child_auditor.canonical_digest(self.cfg),
                       "frozen": assets, "sources": sources, "artifacts_before": {"assets": assets, "sources": sources},
                       "shards": [{"index": i, "protocol_id": f"{auditor.PROTOCOL_ID}-shard-{i}", "seed": auditor.SEEDS[i-1],
                                   "path": f"shard-{i}", "openings": assets[f"openings_{i}"]} for i in range(1, 5)],
                       "preflight": {"opening_count": 1024, "distinct_roots": 1024, "previous_root_count": 1,
                                     "smoke_opening_count": 4, "smoke_distinct_roots": 4,
                                     "resource_policy": copy.deepcopy(self.policy), "engines": ready_engines},
                       "protocol": {"path": "protocol.md", "sha256": sources[auditor.PROTOCOL_DOCUMENT]["sha256"]},
                       "shard_statuses": []}
        self.master["artifacts_after"] = {"assets": copy.deepcopy(assets), "sources": copy.deepcopy(sources),
                                          "unchanged": True, "configuration_sha256": self.master["configuration_sha256"]}
        (self.campaign/"protocol.md").write_bytes((self.root/auditor.PROTOCOL_DOCUMENT).read_bytes())
        self.children = []
        for index in range(1, 5):
            directory = self.campaign/f"shard-{index}"; (directory/"match").mkdir(parents=True)
            begin = self.start+timedelta(seconds=32); run_start = begin+timedelta(seconds=1)
            run_end = run_start+timedelta(seconds=1025); finish = run_end+timedelta(seconds=1)
            child_cfg = {"pairs": 256, "seed": auditor.SEEDS[index-1], "settings": dict(auditor.SETTINGS),
                         "engines": self.cfg["engines"], "ponder": False, "diagnostics": False}
            launch = {"assets": {**{"engine_" + role: assets["engine_" + role] for role in self.engines}, "network": assets["network"], "openings": assets[f"openings_{index}"]},
                      "sources": sources, "configuration": child_cfg, "status": "finished", "started_utc": begin.isoformat(),
                      "finished_utc": finish.isoformat(), "launch_policy": {
                          **self.master["launch_policy"], "local_time": begin.isoformat(),
                          "remaining_seconds": (cutoff-begin).total_seconds()},
                      "preflight": {"engines": copy.deepcopy(ready_engines)}}
            defs, _ = auditor.definitions({"openings": self.entries[(index-1)*256:index*256]}, full_history=True)
            rng = random.Random(auditor.SEEDS[index-1]); rng.shuffle(defs)
            plan = [dict(item, pair_id=f"p{i+1:06d}", first_candidate_color=rng.choice(("white", "black")))
                    for i, item in enumerate(defs)]
            run = {"plan": plan, "started_utc": run_start.isoformat(), "finished_utc": run_end.isoformat()}
            records = []
            for pair in plan:
                first = pair["first_candidate_color"]
                for leg, color in enumerate((first, "black" if first == "white" else "white"), 1):
                    game_id = f"{pair['pair_id']}-{leg}"
                    admission = run_start+timedelta(seconds=len(records)*2)
                    resource = copy.deepcopy(self.policy)
                    resource.update(active_search_workers=1, resident_engines=2,
                                    estimated_memory_bytes=auditor.game_reservation(self.network.stat().st_size))
                    record = {"game_id": game_id, "pair_id": pair["pair_id"], "opening_key": pair["opening_key"],
                              "candidate_color": color, "candidate_score": .5, "status": "complete", "result": "1/2-1/2",
                              "termination": "threefold_repetition", "resource_policy": resource,
                              "started_utc": (admission+timedelta(milliseconds=100)).isoformat(),
                              "finished_utc": (admission+timedelta(seconds=1)).isoformat(),
                              "pgn": game_id+".pgn", "protocol_log": game_id+".protocol.jsonl",
                              "engines": {role: {"pid": index*10000+len(records)*2+offset} for offset, role in enumerate(auditor.ROLE_OPTIONS, 1)}}
                    for key in ("pgn", "protocol_log"):
                        (directory/"match"/record[key]).write_text("mocked raw auditor fixture\n")
                    records.append(record)
                    self.history.append({"observed_utc": admission.isoformat(), "trigger": "before_game", "shard_index": index,
                                         "game_id": game_id, "policy": copy.deepcopy(self.policy), "within_limits": True})
            self.master["shard_statuses"].append({"index": index, "status": "finished", "finished_utc": finish.isoformat()})
            self.children.append({"directory": directory, "launch": launch, "run": run, "records": records})
        self.smoke_children = []
        for index in range(1, 5):
            source = self.children[index-1]
            directory = self.campaign/f"clock-smoke/shard-{index}"
            (directory/"match").mkdir(parents=True)
            defs, _ = auditor.definitions(json.loads((self.root/f"tests/data/phase4f13-match-smoke-{index:02d}.json").read_text()), full_history=True)
            rng = random.Random(auditor.SMOKE_SEEDS[index-1]); rng.shuffle(defs)
            plan = [dict(defs[0], pair_id="p000001", first_candidate_color=rng.choice(("white", "black")))]
            launch = copy.deepcopy(source["launch"])
            launch.update(started_utc=(self.start+timedelta(seconds=2)).isoformat(), finished_utc=(self.start+timedelta(seconds=8)).isoformat())
            launch["launch_policy"]["local_time"] = (self.start+timedelta(seconds=2)).isoformat()
            launch["launch_policy"]["remaining_seconds"] = (cutoff-self.start).total_seconds()-2
            launch["assets"]["openings"] = assets[f"smoke_openings_{index}"]
            launch["configuration"].update(pairs=1, seed=auditor.SMOKE_SEEDS[index-1], settings=dict(auditor.SETTINGS, smoke=True))
            games = []
            for leg in (1, 2):
                record = copy.deepcopy(source["records"][leg-1])
                admission = self.start+timedelta(seconds=3+2*(leg-1))
                color = plan[0]["first_candidate_color"]
                if leg == 2:
                    color = "black" if color == "white" else "white"
                record.update(pair_id="p000001", game_id=f"p000001-{leg}", opening_key=plan[0]["opening_key"], candidate_color=color,
                              started_utc=(admission+timedelta(milliseconds=100)).isoformat(),
                              finished_utc=(admission+timedelta(seconds=1)).isoformat(),
                              pgn=f"p000001-{leg}.pgn", protocol_log=f"p000001-{leg}.protocol.jsonl",
                              engines={role:{"pid": 100000+index*100+leg*10+offset} for offset, role in enumerate(auditor.ROLE_OPTIONS)})
                for key in ("pgn", "protocol_log"):
                    (directory/"match"/record[key]).write_text("mocked smoke raw auditor fixture\n")
                games.append(record)
                self.history.append({"observed_utc": admission.isoformat(), "trigger": "before_smoke_game", "shard_index": index,
                                     "game_id": record["game_id"], "policy": copy.deepcopy(self.policy), "within_limits": True})
            run = {"plan": plan, "started_utc": (self.start+timedelta(seconds=3)).isoformat(),
                   "finished_utc": (self.start+timedelta(seconds=7)).isoformat()}
            self.smoke_children.append({"directory":directory, "launch":launch, "run":run, "records":games})
        self.master["clock_smoke"] = {"status":"passed", "pairs":4,"games":8,"timeout_seconds":600.0,
            "seeds":list(auditor.SMOKE_SEEDS),"started_utc":(self.start+timedelta(seconds=1)).isoformat(),
            "finished_utc":(self.start+timedelta(seconds=10)).isoformat(),
            "passed_utc":(self.start+timedelta(seconds=11)).isoformat(),
            "shards":[{"index":i,"protocol_id":f"{auditor.PROTOCOL_ID}-smoke-shard-{i}","seed":auditor.SMOKE_SEEDS[i-1],
                       "path":f"clock-smoke/shard-{i}","openings":assets[f"smoke_openings_{i}"]} for i in range(1,5)],
            "cleanup":{"engine_pids":sorted({e["pid"] for c in self.smoke_children for g in c["records"] for e in g["engines"].values()}),
                       "alive_pids":[],"unverified_pids":[]}}
        for second in range(1, 1064):
            self.history.append({"observed_utc": (self.start+timedelta(seconds=second)).isoformat(), "trigger": "periodic",
                                 "policy": copy.deepcopy(self.policy), "within_limits": True})
        self.history.append({"observed_utc": self.end.isoformat(), "trigger": "final",
                             "policy": copy.deepcopy(self.policy), "within_limits": True})
        self.history.sort(key=lambda row: row["observed_utc"])
        self.raw_reports = {i: {"errors": [], "complete": True, "statistics": {"inference_eligible": True},
                               "input_sha256": {}, "live_source_differences": [], "decision": "inconclusive"} for i in range(1, 5)}
        self.smoke_raw_reports = copy.deepcopy(self.raw_reports)
        def raw_audit(directory, protocol):
            index = int(directory.name.rsplit("-", 1)[1])
            is_smoke = directory.parent.name == "clock-smoke"
            self.assertEqual(protocol, auditor.smoke_child_protocol(index) if is_smoke else auditor.child_protocol(index))
            result = copy.deepcopy((self.smoke_raw_reports if is_smoke else self.raw_reports)[index])
            if is_smoke:
                result["statistics"]["inference_eligible"] = False
            return result
        p = patch.object(auditor, "audit_child", side_effect=raw_audit); p.start(); self.addCleanup(p.stop)
        self.master["cleanup"] = {"engine_pids": sorted({e["pid"] for c in self.children+self.smoke_children for r in c["records"] for e in r["engines"].values()}),
                                  "alive_pids": [], "unverified_pids": []}
        self.save()
        self.save_smoke_audit()

    def save_smoke_audit(self):
        self.save()
        report = auditor.audit_smoke(self.campaign)
        report["audited_utc"] = (datetime.fromisoformat(self.master["clock_smoke"]["finished_utc"])+timedelta(milliseconds=500)).isoformat()
        path = self.campaign/"clock-smoke-audit.json"
        write_json(path, report)
        self.master["clock_smoke"]["audit"] = {"path":path.name,"sha256":asset(path)["sha256"]}
        self.save()
        return report

    def move_campaign(self, start, *, allow_daytime=False):
        """Place the complete synthetic campaign in another civil-time window.

        Shift every recorded event, retaining elapsed durations and the sample.
        Derive the next morning from Helsinki civil time, including DST changes,
        and observe the ordinary resource budget at each admission/sample.
        """
        delta = start-self.start
        timestamp_fields = {"started_utc", "checked_utc", "finished_utc", "observed_utc", "local_time", "passed_utc"}
        def shift(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in timestamp_fields:
                        value[key] = (datetime.fromisoformat(item)+delta).isoformat()
                    else:
                        shift(item)
            elif isinstance(value, list):
                for item in value:
                    shift(item)
        for document in (self.master, self.children, self.smoke_children, self.history):
            shift(document)
        self.start, self.end = start, self.end+delta
        helsinki = ZoneInfo("Europe/Helsinki")
        local = start.astimezone(helsinki)
        cutoff = datetime.combine(local.date()+timedelta(days=1), time(7), tzinfo=helsinki).astimezone(timezone.utc)
        marker = "phase4f13-daytime-20261028" if allow_daytime else None
        launch_window = "2026-10-28 19:00–22:00 Europe/Helsinki" if allow_daytime else "23:00–23:30 Europe/Helsinki"
        permitted = ((local.date().isoformat() == "2026-10-28" and 19 <= local.hour < 22) if allow_daytime
                     else local.hour == 23 and local.minute < 30)
        self.master["cutoff_utc"] = cutoff.isoformat()
        self.master["launch_policy"].update(
            local_time=local.isoformat(), nighttime=local.hour >= 23 or local.hour < 7,
            allow_daytime=allow_daytime, daytime_authorization=marker,
            launch_window=launch_window, launch_permitted=permitted,
            cutoff_utc=cutoff.isoformat(), cutoff_local=cutoff.astimezone(helsinki).isoformat(),
            remaining_seconds=(cutoff-start).total_seconds())
        def budget(policy, observed):
            civil = observed.astimezone(helsinki)
            night = civil.hour >= 23 or civil.hour < 7
            percent = 80 if night else 50
            policy.update(local_time=civil.isoformat(), source="nighttime" if night else "daytime",
                          percent=percent, max_cpu_workers=18*percent//100, memory_fraction=percent/100)
        budget(self.master["preflight"]["resource_policy"], datetime.fromisoformat(self.master["checked_utc"]))
        for event in self.history:
            budget(event["policy"], datetime.fromisoformat(event["observed_utc"]))
        for child in self.children+self.smoke_children:
            child_start = datetime.fromisoformat(child["launch"]["started_utc"])
            child_local = child_start.astimezone(helsinki)
            child["launch"]["launch_policy"] = {
                **self.master["launch_policy"], "local_time": child_local.isoformat(),
                "remaining_seconds": (cutoff-child_start).total_seconds(),
                "launch_permitted": ((child_local.date().isoformat() == "2026-10-28" and 19 <= child_local.hour < 22)
                                     if allow_daytime else child_local.hour == 23 and child_local.minute < 30)}
            for game in child["records"]:
                budget(game["resource_policy"], datetime.fromisoformat(game["started_utc"]))

        self.save_smoke_audit()

    def save(self):
        for child in self.children+self.smoke_children:
            write_json(child["directory"]/"launch.json", child["launch"])
            write_json(child["directory"]/"match/run.json", child["run"])
            jsonl(child["directory"]/"match/games.jsonl", child["records"])
        path = self.campaign/"resource-history.jsonl"; jsonl(path, self.history)
        self.master["resource_history"] = {"path": path.name, "observations": len(self.history), "sha256": asset(path)["sha256"]}
        prefix = [event for event in self.history if datetime.fromisoformat(event["observed_utc"]) <= datetime.fromisoformat(self.master["clock_smoke"]["finished_utc"])]
        path = self.campaign/"clock-smoke/resource-history.jsonl"; jsonl(path, prefix)
        self.master["clock_smoke"]["resource_history"] = {"path":"clock-smoke/resource-history.jsonl", "sha256":asset(path)["sha256"], "observations":len(prefix)}
        write_json(self.campaign/"campaign.json", self.master)

    def check(self, expected="invalid_or_incomplete"):
        self.save(); result = auditor.audit(self.campaign)
        self.assertEqual(result["decision"], expected, result["errors"])
        self.assertFalse(result["default_change"])
        if expected == "invalid_or_incomplete":
            self.assertFalse(result["statistics"]["inference_eligible"])
            self.assertIsNone(result["statistics"]["score_interval"])
        return result

    def score(self, points):
        # Exact half-point boundaries; deliberately independent of game timing.
        units = int(points*2)
        for game in [g for child in self.children for g in child["records"]]:
            amount = min(2, units); units -= amount
            value = amount/2
            white = value if game["candidate_color"] == "white" else 1-value
            game["result"] = {0.: "0-1", .5: "1/2-1/2", 1.: "1-0"}[white]
            game["candidate_score"] = value

    def test_complete_2048_game_aggregate(self):
        result = self.check("inconclusive")
        self.assertEqual(result["statistics"]["included_pairs"], 1024)
        self.assertEqual(result["statistics"]["recorded_games"], 2048)
        self.assertIsNone(result["statistics"]["radius"])
        self.assertEqual(result["statistics"]["betting"]["method"], "phase4f13-fixed-mixture-v1")
        self.assertEqual(len({p["pair_id"] for p in result["statistics"]["included_pair_scores"]}), 1024)


    def test_daytime_requires_exact_recorded_owner_authorization(self):
        self.move_campaign(datetime(2026, 10, 28, 17, 0, tzinfo=timezone.utc), allow_daytime=True)
        for marker in (None, "owner-other-campaign", "phase4f7-daytime-20261027", "missing"):
            with self.subTest(marker=marker):
                if marker == "missing":
                    self.master["launch_policy"].pop("daytime_authorization")
                else:
                    self.master["launch_policy"]["daytime_authorization"] = marker
                self.check()

    def test_daytime_requires_explicit_boolean_permission(self):
        self.move_campaign(datetime(2026, 10, 28, 17, 0, tzinfo=timezone.utc), allow_daytime=True)
        for flag in (False, 1, "true"):
            with self.subTest(flag=flag):
                self.master["launch_policy"]["allow_daytime"] = flag
                self.check()

    def test_recorded_nighttime_must_match_launch_window(self):
        self.master["launch_policy"]["nighttime"] = False
        self.check()
        self.move_campaign(datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc), allow_daytime=True)
        self.master["launch_policy"]["nighttime"] = True
        self.check()

    def test_ordinary_night_cannot_carry_daytime_authorization(self):
        self.master["launch_policy"]["daytime_authorization"] = "owner-20261018-phase4d2"
        self.check()

    def test_ordinary_night_child_cannot_add_daytime_permission(self):
        self.children[0]["launch"]["launch_policy"].update(
            allow_daytime=True, daytime_authorization="owner-20261018-phase4d2")
        self.check()


    def test_ordinary_night_cutoff_tracks_both_dst_transitions(self):
        for start, hours, expected in (
                (datetime(2026, 3, 28, 21, 0, tzinfo=timezone.utc), 7, "2026-03-29T04:00:00+00:00"),
                (datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc), 9, "2026-10-25T05:00:00+00:00")):
            with self.subTest(start=start):
                self.move_campaign(start)
                self.assertEqual(self.master["cutoff_utc"], expected)
                self.assertEqual(self.master["launch_policy"]["remaining_seconds"], hours*3600)
                self.check("inconclusive")

    def test_other_daytime_dates_remain_rejected(self):
        self.move_campaign(datetime(2026, 10, 18, 6, tzinfo=timezone.utc), allow_daytime=True)
        self.check()




    def test_preflight_must_finish_within_authorized_window(self):
        self.move_campaign(datetime(2026, 10, 22, 20, 29, tzinfo=timezone.utc))
        self.master["checked_utc"] = "2026-10-22T20:30:00+00:00"
        result = self.check()
        self.assertTrue(any("Preflight completed outside launch window" in error for error in result["errors"]))


    def test_daytime_child_must_preserve_exact_authorization(self):
        self.move_campaign(datetime(2026, 10, 28, 17, tzinfo=timezone.utc), allow_daytime=True)
        self.children[0]["launch"]["launch_policy"]["daytime_authorization"] = None
        self.check()



    def test_daytime_preflight_cannot_finish_past_authorized_window(self):
        self.move_campaign(datetime(2026, 10, 28, 19, 59, tzinfo=timezone.utc), allow_daytime=True)
        self.master["checked_utc"] = "2026-10-28T20:00:00+00:00"
        self.check()
        self.check_readiness(self.readiness(), False)

    def test_daytime_cutoff_and_declaration_cannot_be_extended(self):
        self.move_campaign(datetime(2026, 10, 28, 17, tzinfo=timezone.utc), allow_daytime=True)
        original = copy.deepcopy(self.master["launch_policy"])
        for corruption in ("cutoff_utc", "cutoff_local", "launch_window", "launch_permitted", "nighttime", "local_time"):
            with self.subTest(corruption=corruption):
                policy = copy.deepcopy(original)
                policy[corruption] = {"cutoff_utc": "2026-10-29T06:00:00+00:00",
                                      "cutoff_local": "2026-10-29T08:00:00+02:00",
                                      "launch_window": "any time",
                                      "launch_permitted": 1, "nighttime": True,
                                      "local_time": "2026-10-29T19:00:00+02:00"}[corruption]
                self.master["launch_policy"] = policy
                self.check()
                self.check_readiness(self.readiness(), False)
        self.master["launch_policy"] = original

    def test_daytime_child_permission_and_original_cutoff_cannot_drift(self):
        self.move_campaign(datetime(2026, 10, 28, 17, tzinfo=timezone.utc), allow_daytime=True)
        original = copy.deepcopy(self.children[0]["launch"]["launch_policy"])
        for key, value in (("allow_daytime", False), ("allow_daytime", 1),
                           ("daytime_authorization", "phase4f7-daytime-20261027"),
                           ("launch_window", "any time"), ("launch_permitted", False),
                           ("local_time", "2026-10-29T19:00:00+02:00"),
                           ("cutoff_local", "2026-10-29T08:00:00+02:00"),
                           ("cutoff_utc", "2026-10-29T06:00:00+00:00")):
            with self.subTest(key=key, value=value):
                self.children[0]["launch"]["launch_policy"] = {**original, key: value}
                self.check()
        self.children[0]["launch"]["launch_policy"] = original

    def test_unflagged_daytime_readiness_never_authorizes_launch(self):
        self.move_campaign(datetime(2026, 10, 28, 17, tzinfo=timezone.utc))
        self.check_readiness(self.readiness())
        self.check()


    def test_exclusion_generator_metadata_and_build_pins_cannot_self_authorize(self):
        for name in auditor.input_pins():
            original = self.master["sources"][name]["sha256"]
            self.master["sources"][name]["sha256"] = "0" * 64
            with self.subTest(name=name):
                self.check()
            self.master["sources"][name]["sha256"] = original

    def readiness(self):
        result = copy.deepcopy(self.master)
        result.update(status="checked")
        return result

    def check_readiness(self, report, expected=True):
        path = self.root / "preflight.json"
        write_json(path, report)
        result = auditor.audit_readiness(path)
        self.assertIs(result["checked"], expected, result["errors"])
        self.assertTrue(result["readiness_only"])
        return result

    def test_independent_readiness_zero_search_and_pin_checks(self):
        self.check_readiness(self.readiness())
        for corruption in ("search", "actual_option", "pin", "source", "resource", "exception"):
            report = self.readiness()
            if corruption == "search":
                report["preflight"]["engines"][0]["transcript"][-1]["line"] = "go depth 1"
            elif corruption == "actual_option":
                for event in report["preflight"]["engines"][0]["transcript"]:
                    if event["line"] == "setoption name Late Move Reductions value true":
                        event["line"] = "setoption name Late Move Reductions value false"
            elif corruption == "pin":
                report["frozen"]["engine_candidate"]["sha256"] = "0" * 64
            elif corruption == "source":
                report["sources"][auditor.GENERATOR]["sha256"] = "0" * 64
            elif corruption == "resource":
                report["preflight"]["resource_policy"]["resident_engines"] = 2
            else:
                report["launch_policy"]["allow_daytime"] = True
            with self.subTest(corruption=corruption):
                self.check_readiness(report, False)

    def test_smoke_gates_full_sample_and_never_infers_strength(self):
        result = auditor.audit_smoke(self.campaign)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual((result["pairs"],result["games"]),(4,8))
        self.assertFalse(result["inference_eligible"])
        self.assertFalse(result["default_change"])
        final = self.check("inconclusive")
        self.assertEqual(final["statistics"]["included_pairs"],1024)
        self.assertEqual(final["statistics"]["recorded_games"],2048)

    def test_smoke_failure_and_corrupt_saved_gate_block_heldout_inference(self):
        original = copy.deepcopy(self.master["clock_smoke"])
        for field,value in (("status","failed"),("games",7),("timeout_seconds",601.0),
                            ("passed_utc",(self.start+timedelta(seconds=700)).isoformat())):
            self.master["clock_smoke"] = copy.deepcopy(original)
            self.master["clock_smoke"][field] = value
            self.check()
        self.master["clock_smoke"] = original
        self.smoke_children[0]["records"][0].update(termination="time_forfeit",clock_loser="opponent")
        self.save()
        self.assertFalse(auditor.audit_smoke(self.campaign)["passed"])
        self.check()

    def test_smoke_games_cannot_start_heldout_early_or_leave_processes(self):
        original = copy.deepcopy(self.master["clock_smoke"])
        self.master["clock_smoke"]["cleanup"]["alive_pids"] = [original["cleanup"]["engine_pids"][0]]
        self.check()
        self.master["clock_smoke"] = original
        self.children[0]["launch"]["started_utc"] = (self.start+timedelta(seconds=5)).isoformat()
        self.check()

    def test_positive_and_negative_half_point_boundaries(self):
        for points, decision in ((1024, "inconclusive"), (1536, "eligible_for_default_review"),
                                 (512, "negative_evidence")):
            with self.subTest(points=points):
                self.score(points); self.check(decision)

    def test_candidate_forfeit_precedes_positive_score(self):
        self.score(1536)
        self.children[0]["records"][0].update(termination="time_forfeit", clock_loser="candidate")
        self.check("operational_regression")

    def test_opponent_forfeit_also_blocks_positive_score(self):
        self.score(1536)
        self.children[0]["records"][0].update(termination="time_forfeit", clock_loser="opponent")
        self.check("operational_regression")

    def test_missing_or_live_cleanup_blocks_review(self):
        self.score(1536)
        for corruption in ("alive", "unknown", "missing_pid"):
            original = copy.deepcopy(self.master["cleanup"])
            if corruption == "missing_pid":
                self.master["cleanup"]["engine_pids"].pop()
            else:
                key = "alive_pids" if corruption == "alive" else "unverified_pids"
                self.master["cleanup"][key] = [original["engine_pids"][0]]
            self.check()
            self.master["cleanup"] = original

    def test_aggregate_reserve_cannot_drop_below_six_gib(self):
        self.history[1]["policy"]["estimated_memory_bytes"] = auditor.game_reservation(self.network.stat().st_size)*4
        self.check()


    def test_master_pin_tampering(self):
        self.master["frozen"]["engine_candidate"]["sha256"] = "0"*64
        self.check()

    def test_actual_package_flags_cannot_spoof_the_opponent(self):
        before = copy.deepcopy(self.master["preflight"]["engines"])
        for field in ("Deep Quiet Reductions", "ProbCut", "Late Move Reductions", "TT Move Hints", "Continuation History"):
            with self.subTest(field=field):
                engines = copy.deepcopy(before)
                engines[1]["configured"][field] = not engines[1]["configured"][field]
                self.master["preflight"]["engines"] = engines
                result = self.check()
                self.assertTrue(result["errors"])
        self.master["preflight"]["engines"] = before

    def test_current_default_claims_are_checked_independently(self):
        before = copy.deepcopy(self.master["preflight"]["engines"])
        for field in ("Late Move Reductions", "Deep Quiet Reductions", "ProbCut", "TT Move Hints", "Continuation History"):
            with self.subTest(field=field):
                engines = copy.deepcopy(before)
                engines[0]["options"][field]["default"] = not engines[0]["options"][field]["default"]
                self.master["preflight"]["engines"] = engines
                self.check()
        self.master["preflight"]["engines"] = before

    def test_pins_document_itself_cannot_drift_after_freeze(self):
        (self.root/auditor.PIN_FILE).write_text("changed pins document")
        result = self.check()
        self.assertTrue(any("Preparation pins changed" in message for message in result["errors"]))

    def test_configuration_options_cannot_authorize_themselves(self):
        self.cfg["engines"][0]["extra_options"] = dict(auditor.ROLE_OPTIONS["candidate"], **{"Capture Ordering": "see"})
        self.master["configuration_sha256"] = auditor.child_auditor.canonical_digest(self.cfg)
        self.check()


    def test_readiness_process_identity_and_cleanup_evidence(self):
        original = copy.deepcopy(self.master["preflight"]["engines"])
        for corruption in ("duplicate_pid", "missing_pid", "negative_pid", "missing_exit", "nonzero_exit", "bool_exit"):
            with self.subTest(corruption=corruption):
                engines = copy.deepcopy(original)
                if corruption == "duplicate_pid":
                    engines[1]["pid"] = engines[0]["pid"]
                elif corruption == "missing_pid":
                    engines[0].pop("pid")
                elif corruption == "negative_pid":
                    engines[0]["pid"] = -1
                elif corruption == "missing_exit":
                    engines[0].pop("returncode")
                else:
                    engines[0]["returncode"] = False if corruption == "bool_exit" else 1
                self.master["preflight"]["engines"] = engines
                self.check_readiness(self.readiness(), False)
        self.master["preflight"]["engines"] = original

    def test_raw_network_hint_defaults_and_spin_ranges_cannot_be_spoofed(self):
        original = copy.deepcopy(self.master["preflight"]["engines"])
        for old, new in (("nn-1a298aa575a0.nnue", "other.nnue"),
                         ("TT Move Hints type check default false", "TT Move Hints type check default true"),
                         ("Continuation History type check default false", "Continuation History type check default true"),
                         ("Threads type spin default 1 min 1 max 64", "Threads type spin default 1 min 1 max 128"),
                         ("SyzygyProbeDepth type spin default 1 min 1 max 128", "SyzygyProbeDepth type spin default 2 min 1 max 128")):
            with self.subTest(old=old):
                engines = copy.deepcopy(original)
                event = next(row for row in engines[0]["transcript"] if row["line"].startswith("option ") and old in row["line"])
                event["line"] = event["line"].replace(old, new)
                # Structured metadata and later explicit settings remain valid;
                # only independently reading the raw defaults catches this.
                self.master["preflight"]["engines"] = engines
                self.check_readiness(self.readiness(), False)
        self.master["preflight"]["engines"] = original

    def test_duplicate_raw_option_declarations_are_rejected(self):
        for name in ("Continuation History", "TT Move Hints"):
            with self.subTest(name=name):
                report = self.readiness()
                transcript = report["preflight"]["engines"][0]["transcript"]
                index = next(i for i, row in enumerate(transcript)
                             if row["line"].startswith(f"option name {name} type "))
                transcript.insert(index, copy.deepcopy(transcript[index]))
                self.check_readiness(report, False)

    def test_overnight_window_declarations_cannot_be_rewritten(self):
        original = copy.deepcopy(self.master["launch_policy"])
        for key, value in (("launch_window", "any time"), ("launch_permitted", False),
                           ("launch_permitted", 1)):
            with self.subTest(key=key, value=value):
                self.master["launch_policy"] = {**original, key: value}
                self.check()
                self.check_readiness(self.readiness(), False)
        self.master["launch_policy"] = original



    def test_role_provenance_inventory_and_origin_are_independent(self):
        auditor.validate_build_provenance(self.master["sources"])
        for role in auditor.ROLE_OPTIONS:
            path = self.root/auditor.BUILD_MANIFESTS[role]
            original = json.loads(path.read_text())
            for corruption in ("revision", "binary", "network", "role", "flags", "missing", "extra", "origin", "log"):
                changed = copy.deepcopy(original)
                if corruption == "missing":
                    changed["source_sha256"].pop(next(iter(changed["source_sha256"])))
                elif corruption == "extra":
                    changed["source_sha256"]["extra.cpp"] = "0"*64
                else:
                    field = {"revision": "engine_source_revision", "binary": "binary_sha256",
                             "network": "network_sha256", "role": "role", "flags": "compile_flags",
                             "origin": "origin_manifest", "log": "build_log"}[corruption]
                    changed[field] = "wrong"
                write_json(path, changed)
                with self.assertRaises(ValueError, msg=role+"/"+corruption):
                    auditor.validate_build_provenance(self.master["sources"])
            write_json(path, original)

    def test_current_pins_cannot_reauthorize_changed_prior_manifest(self):
        name = auditor.BUILD_MANIFESTS["candidate"]
        path = self.root/name
        changed = json.loads(path.read_text())
        changed["extra_fabricated_provenance"] = "changed after acceptance"
        write_json(path, changed)
        # Re-signing the new preparation metadata cannot rewrite old evidence.
        self.master["sources"][name] = {key: value for key, value in asset(path).items() if key != "path"}
        with self.assertRaisesRegex(ValueError, "Preserved Phase 4F.12"):
            auditor.validate_build_provenance(self.master["sources"])

    def test_binary_roles_cannot_be_swapped_or_aliased(self):
        assets = self.master["frozen"]
        original = copy.deepcopy(assets)
        assets["engine_candidate"], assets["engine_opponent"] = assets["engine_opponent"], assets["engine_candidate"]
        self.check()
        assets.clear(); assets.update(original)
        self.master["configuration"]["engines"][0]["executable"] = assets["engine_opponent"]["path"]
        self.master["configuration_sha256"] = auditor.child_auditor.canonical_digest(self.cfg)
        self.check()

    def test_quiet_host_and_external_fresh_output_are_required(self):
        self.master["quiet_host"] = False
        self.check()
        output = self.campaign/"unwanted-audit.json"
        with self.assertRaises(SystemExit):
            auditor.main(["--campaign", str(self.campaign), "--output", str(output)])
        self.assertFalse(output.exists())

    def test_preflight_cannot_search_held_out_positions(self):
        for line in ("position startpos moves e2e4", "go", "go infinite"):
            with self.subTest(line=line):
                self.master["preflight"]["engines"][0]["transcript"][2]["line"] = line
                result = self.check()
                self.assertTrue(any("searched or exposed" in error for error in result["errors"]))

    def test_malformed_master_retains_invalid_report(self):
        write_json(self.campaign/"campaign.json", ["invalid master shape"])
        result = auditor.audit(self.campaign)
        self.assertEqual(result["decision"], "invalid_or_incomplete")
        self.assertFalse(result["statistics"]["inference_eligible"])

    def test_missing_preflight_readiness_is_rejected(self):
        self.master["preflight"]["engines"][0]["transcript"][3]["line"] = "info string no readiness"
        self.check()

    def test_wrong_shard_or_reused_directory(self):
        self.master["shards"][1]["path"] = "shard-1"
        self.check()

    def test_path_escape(self):
        self.children[0]["records"][0]["pgn"] = "../../protocol.md"
        self.check()

    def test_reused_raw_game_file(self):
        self.children[0]["records"][1]["pgn"] = self.children[0]["records"][0]["pgn"]
        self.check()

    def test_duplicate_game_id(self):
        self.children[0]["records"][1]["game_id"] = self.children[0]["records"][0]["game_id"]
        self.check()

    def test_plan_color_or_history_change(self):
        self.children[0]["run"]["plan"][0]["first_candidate_color"] = "invalid"
        self.check()

    def test_changed_child_cutoff(self):
        self.children[0]["launch"]["launch_policy"]["cutoff_utc"] = (self.start+timedelta(hours=9)).isoformat()
        self.check()

    def test_overlapping_game_timestamps(self):
        self.children[0]["records"][1]["started_utc"] = self.children[0]["records"][0]["started_utc"]
        self.check()

    def test_late_master_launch(self):
        self.master["started_utc"] = (self.start+timedelta(minutes=15)).isoformat()
        self.check()

    def test_single_worker_reservation_cannot_cover_four_shards(self):
        self.history[1]["policy"]["active_search_workers"] = 1
        self.check()

    def test_lowered_override_invalidates_completion(self):
        p = self.history[1]["policy"]
        p.update(source="manual", percent=10, max_cpu_workers=1, memory_fraction=.1)
        self.history[1]["within_limits"] = False
        self.check()

    def test_resource_verdict_cannot_lie(self):
        self.history[1]["within_limits"] = False
        self.check()

    def test_missing_admission(self):
        self.history = [event for event in self.history if not (event.get("shard_index") == 1 and event.get("game_id") == "p000001-1")]
        self.check()

    def test_missing_all_periodic_observations(self):
        self.history = [event for event in self.history if event["trigger"] != "periodic"]
        self.check()

    def test_long_gap_during_game_is_rejected(self):
        def later(value):
            return (datetime.fromisoformat(value)+timedelta(seconds=10)).isoformat()
        for child, status in zip(self.children, self.master["shard_statuses"]):
            child["records"][0]["finished_utc"] = later(child["records"][0]["finished_utc"])
            for game in child["records"][1:]:
                for key in ("started_utc", "finished_utc"):
                    game[key] = later(game[key])
            child["run"]["finished_utc"] = later(child["run"]["finished_utc"])
            child["launch"]["finished_utc"] = later(child["launch"]["finished_utc"])
            status["finished_utc"] = child["launch"]["finished_utc"]
        for event in self.history:
            if event["trigger"] == "before_game" and event["game_id"] != "p000001-1":
                event["observed_utc"] = later(event["observed_utc"])
        low, high = self.start+timedelta(seconds=33), self.start+timedelta(seconds=44)
        self.history = [event for event in self.history if not (event["trigger"] == "periodic"
                       and low < datetime.fromisoformat(event["observed_utc"]) < high)]
        self.history.sort(key=lambda event: event["observed_utc"])
        result = self.check()
        self.assertTrue(any("gap over five seconds" in error for error in result["errors"]), result["errors"])

    def test_policy_samples_may_differ_in_time_and_allowed_override(self):
        p = self.master["preflight"]["resource_policy"]
        p.update(local_time=(self.start+timedelta(seconds=1)).isoformat(), source="manual", percent=50,
                 max_cpu_workers=9, memory_fraction=.5)
        self.master["checked_utc"] = (self.start+timedelta(seconds=1)).isoformat()
        local = self.children[0]["records"][0]["resource_policy"]
        local.update(source="manual", percent=50, max_cpu_workers=9, memory_fraction=.5)
        self.check("inconclusive")

    def test_child_source_freeze_must_match_master(self):
        self.children[0]["launch"]["sources"] = copy.deepcopy(self.master["sources"])
        self.children[0]["launch"]["sources"]["tools/match.py"]["sha256"] = "0"*64
        self.check()

    def test_raw_transcript_or_pgn_failure_blocks_aggregate(self):
        for error in ("Actual UCI options differ", "PGN differs from full journal history"):
            with self.subTest(error=error):
                self.raw_reports[2]["errors"] = [error]
                self.check()

    def test_partial_cancellation_retains_observed_descriptive_pairs(self):
        self.master["status"] = "interrupted"
        self.children[3]["records"].pop()
        self.children[3]["launch"]["status"] = "interrupted"
        self.raw_reports[4]["complete"] = False
        self.raw_reports[4]["statistics"]["inference_eligible"] = False
        self.history = [event for event in self.history if not (event.get("shard_index") == 4 and event.get("game_id") == "p000256-2")]
        result = self.check()
        self.assertEqual(result["statistics"]["recorded_games"], 2047)
        self.assertEqual(result["statistics"]["included_pairs"], 1023)

    def test_all_preparation_sources_remain_pinned_including_protocol(self):
        (self.root/auditor.PROTOCOL_DOCUMENT).write_text("later documentation update\n")
        self.check()

    def test_cli_refuses_existing_output(self):
        output = self.root/"existing.json"; output.write_text("preserve me")
        with self.assertRaises(SystemExit):
            auditor.main(["--campaign", str(self.campaign), "--output", str(output)])
        self.assertEqual(output.read_text(), "preserve me")


class RawFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Independently composed legal mate-in-one roots; no engines or game assets.
        cls.roots = []
        for king, queen, defender in __import__("itertools").product(range(64), range(64), (chess.H8, chess.A8, chess.H1, chess.A1)):
            if len({king, queen, defender}) != 3:
                continue
            board = chess.Board(None)
            for square, piece in ((king, chess.Piece(chess.KING, True)),
                                  (queen, chess.Piece(chess.QUEEN, True)),
                                  (defender, chess.Piece(chess.KING, False))):
                board.set_piece_at(square, piece)
            board.turn = chess.WHITE
            if not board.is_valid() or board.outcome(claim_draw=True):
                continue
            for move in list(board.legal_moves):
                child = board.copy(); child.push(move)
                if child.is_checkmate():
                    cls.roots.append((board.fen(), move.uci()))
                    break
            if len(cls.roots) == cls.protocol_spec.pairs:
                return
        raise AssertionError("Could not compose enough test roots")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="chess0live-audit-")
        self.directory = Path(self.temporary.name)
        self.match = self.directory / "match"; self.match.mkdir()
        engine, network, openings = (self.directory / name for name in ("engine_candidate", "network", "openings.json"))
        engine.write_bytes(b"synthetic: never executed\n"); network.write_bytes(b"synthetic: never loaded\n")
        entries = [{"id": f"synthetic-{i}", "fen": fen, "moves": []} for i, (fen, _) in enumerate(self.roots)]
        write_json(openings, {"openings": entries})
        (self.match / "openings.json").write_bytes(openings.read_bytes())
        opponent = self.directory / "engine_opponent"
        opponent.write_bytes(b"other synthetic never executed")
        assets = {name: asset(path) for name, path in (("engine_candidate", engine), ("engine_opponent", opponent), ("network", network), ("openings", openings))}
        self.protocol = replace(self.protocol_spec, pinned_sha256=tuple(
            (key, value["sha256"]) for key, value in assets.items()))
        sources = {}
        for name in (*self.protocol.required_sources, self.protocol.protocol_document):
            source = asset(raw_auditor.ROOT / name)
            sources[name] = {key: source[key] for key in ("sha256", "bytes")}
        (self.directory / "protocol.md").write_bytes((raw_auditor.ROOT / self.protocol.protocol_document).read_bytes())
        config = {"pairs": self.protocol.pairs, "seed": self.protocol.seed, "settings": dict(self.protocol.settings), "ponder": False,
                  "diagnostics": False, "engines": []}
        specs = {}
        for role in ("candidate", "opponent"):
            engine = Path(assets["engine_" + role]["path"])
            config["engines"].append({"role": role, "executable": str(engine), "network": str(network),
                                      "network_option": "EvalFile", "arguments": [],
                                      "source_revision": "synthetic", "extra_options": self.protocol.options(role)})
            specs[role] = {"executable": str(engine), "network": str(network), "network_option": "EvalFile",
                           "arguments": [], "experiment_options": self.protocol.options(role),
                           "artifacts": [assets["engine_" + role], assets["network"]]}
        self.launch = {"schema_version": 1, "protocol_id": self.protocol.protocol_id, "status": "finished",
                       "chess_version": "1.11.2", "configuration": config,
                       "started_utc": "2026-10-15T20:00:00.001+00:00",
                       "finished_utc": "2026-10-15T20:30:00+00:00",
                       "launch_policy": {"timezone": "Europe/Helsinki", "local_time": "2026-10-15T23:00:00+03:00",
                                         "nighttime": True, "allow_daytime": False,
                                         "cutoff_local": "2026-10-16T07:00:00+03:00",
                                         "cutoff_utc": "2026-10-16T04:00:00+00:00", "remaining_seconds": 28800.},
                       "preflight": {"opening_count": self.protocol.pairs, "distinct_roots": self.protocol.pairs},
                       "configuration_sha256": raw_auditor.canonical_digest(config), "assets": assets, "sources": sources,
                       "match_directory": "match", "protocol_document": {"source": self.protocol.protocol_document,
                       "frozen_copy": "protocol.md", "sha256": sources[self.protocol.protocol_document]["sha256"]}}
        self.launch["integrity_after"] = {"configuration_sha256": self.launch["configuration_sha256"],
                                          "assets": copy.deepcopy(assets), "sources": copy.deepcopy(sources), "unchanged": True}
        self.plan = []
        shuffled = list(entries); generator = random.Random(self.protocol.seed); generator.shuffle(shuffled)
        for index, entry in enumerate(shuffled):
            definition = {"fen": entry["fen"], "moves": []}
            key = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
            self.plan.append({"pair_id": f"p{index+1:06d}", "opening_id": entry["id"], "opening_key": key,
                              "starting_fen": entry["fen"], "moves": [],
                              "first_candidate_color": generator.choice(("white", "black"))})
        self.run = {"schema_version": 1, "settings": dict(self.protocol.settings), "planned_pairs": self.protocol.pairs, "seed": self.protocol.seed,
                    "chess_version": "1.11.2", "status": "finished", "plan": self.plan, "engines": specs,
                    "opening_suite": {"sha256": assets["openings"]["sha256"]},
                    "runner_sources": [{"path": key, "sha256": sources[key]["sha256"]} for key in
                                       ("tools/match.py", "tools/match_statistics.py", "tools/resources.py")]}
        self.records = []
        for pair in self.plan:
            first = pair["first_candidate_color"]
            for leg, color in enumerate((first, "black" if first == "white" else "white"), 1):
                self.records.append(self.make_game(pair, leg, color))
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def make_game(self, pair, leg, color, late=False, bestmove=None):
        game_id = f"{pair['pair_id']}-{leg}"
        board = chess.Board(pair["starting_fen"])
        game = chess.pgn.Game(); game.setup(board)
        node = game
        for token in pair["moves"]:
            board.push_uci(token)
            node = node.add_variation(chess.Move.from_uci(token))
        move = bestmove or next(move for fen, move in self.roots if fen == board.fen())
        moving_color = "white" if board.turn else "black"
        role = "candidate" if color == moving_color else "opponent"
        elapsed = 16. if late else .25
        after = -1. if late else 15.-elapsed+.15
        event = {"ply": board.ply()+1, "engine": role, "color": moving_color, "clock_before": 15., "elapsed_seconds": elapsed,
                 "move": move, "clock_after": after, "played": not late}
        if not late:
            board.push_uci(move); node = node.add_variation(chess.Move.from_uci(move)); node.set_clock(after)
        result, termination = ("1/2-1/2", "time_forfeit") if late else ("1-0" if moving_color == "white" else "0-1", "checkmate")
        game.headers.update(Result=result, Termination=termination)
        (self.match / f"{game_id}.pgn").write_text(str(game)+"\n\n")
        log = []; tick = 0
        def emit(direction, line, advance=1):
            nonlocal tick
            tick += advance
            log.append({"engine": role, "direction": direction, "line": line, "monotonic_ns": tick})
        expected = {"Hash": "64", "Threads": "1", "Ponder": "false", "Search Diagnostics": "false",
                    "Move Overhead": "20", "EvalFile": self.launch["assets"]["network"]["path"],
                    **self.protocol.options(role)}
        for key, value in expected.items(): emit("to_engine", f"setoption name {key} value {value}")
        emit("to_engine", "ucinewgame"); emit("to_engine", "isready")
        emit("from_engine", "readyok", 10_000_000_000)  # Deliberately long readiness is outside the clock.
        history = " moves " + " ".join(pair["moves"]) if pair["moves"] else ""
        emit("to_engine", "position fen "+pair["starting_fen"]+history)
        emit("to_engine", "go wtime 15000 btime 15000 winc 150 binc 150")
        emit("from_engine", "bestmove "+move, int(elapsed*1e9))
        jsonl(self.match / f"{game_id}.protocol.jsonl", log)
        record = {"game_id": game_id, "pair_id": pair["pair_id"], "opening_id": pair["opening_id"],
                  "opening_key": pair["opening_key"], "candidate_color": color, "status": "complete",
                  "result": result, "termination": termination, "opening_plies": len(pair["moves"]), "played_plies": int(not late),
                  "moves": [event], "final_fen": board.fen(), "clocks": dict({"white": 15., "black": 15.}, **{moving_color: after}),
                  "candidate_score": .5 if late else float(color == moving_color),
                  "pgn": f"{game_id}.pgn", "protocol_log": f"{game_id}.protocol.jsonl"}
        if late: record["clock_loser"] = role
        return record

    def save(self):
        nested = [{"pair_id": p["pair_id"], "opening_key": p["opening_key"],
                   "games": [g for g in self.records if g["pair_id"] == p["pair_id"]]} for p in self.plan]
        summary = summarize_pairs(nested, experiment_complete=self.run["status"] == "finished")
        summary["smoke"] = dict(self.protocol.settings)["smoke"]
        if summary["smoke"]:
            summary["inference_eligible"] = False
            summary["uncertainty"]["withheld_reasons"].append("smoke_run_not_a_strength_experiment")
            for key in ("radius", "score_interval", "relative_elo_interval"):
                summary["uncertainty"][key] = None
        self.launch["match_summary"] = summary
        write_json(self.directory / "launch.json", self.launch)
        write_json(self.match / "run.json", self.run)
        write_json(self.match / "summary.json", summary)
        jsonl(self.match / "games.jsonl", self.records)


class RawChildTests(unittest.TestCase):
    """Use real 512-game PGN/transcript fixtures, independently of master mocks."""
    @classmethod
    def setUpClass(cls):
        with patch.object(auditor, "opening_sha256", return_value=("0"*64,)*4):
            protocol = auditor.child_protocol(1)
        protocol = replace(protocol, required_sources=("tools/match.py", "tools/audit_phase4f13_games.py",
                                                       "tools/audit_phase3l.py", "tools/match_statistics.py",
                                                       "tools/resources.py"))
        cls.fixture_class = type("NNUEComparisonRawFixture", (RawFixture,), {"protocol_spec": protocol})
        cls.fixture_class.setUpClass()

    def setUp(self):
        self.fixture = self.fixture_class()
        self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        for record in self.fixture.records:
            path = self.fixture.match/record["protocol_log"]
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events.insert(0, {"engine": events[0]["engine"], "direction": "to_engine",
                              "line": "setoption name SyzygyPath value ", "monotonic_ns": 0})
            record["engines"] = {role: {"ponder": False, "options":
                auditor.expected_options(role, self.fixture.launch["assets"]["network"]["path"])}
                for role in auditor.ROLE_OPTIONS}
            tick = events[-1]["monotonic_ns"]
            events.extend({"engine": role, "direction": "to_engine", "line": "quit", "monotonic_ns": tick+i}
                          for i, role in enumerate(auditor.ROLE_OPTIONS, 1))
            jsonl(path, events)
        self.fixture.save()

    def test_two_game_smoke_raw_profile_has_no_strength_inference(self):
        with patch.object(auditor, "smoke_opening_sha256", return_value=("0"*64,)*4):
            protocol = auditor.smoke_child_protocol(1)
        protocol = replace(protocol, required_sources=self.fixture.protocol.required_sources)
        fixture_class = type("SmokeRawFixture", (RawFixture,), {"protocol_spec":protocol})
        fixture_class.setUpClass()
        fixture = fixture_class(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        for record in fixture.records:
            path = fixture.match/record["protocol_log"]
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events.insert(0,{"engine":events[0]["engine"],"direction":"to_engine","line":"setoption name SyzygyPath value ","monotonic_ns":0})
            record["engines"] = {role:{"ponder":False,"options":auditor.expected_options(role,fixture.launch["assets"]["network"]["path"])}
                                 for role in auditor.ROLE_OPTIONS}
            tick = events[-1]["monotonic_ns"]
            events.extend({"engine":role,"direction":"to_engine","line":"quit","monotonic_ns":tick+i}
                          for i,role in enumerate(auditor.ROLE_OPTIONS,1))
            jsonl(path,events)
        fixture.save()
        result = auditor.audit_child(fixture.directory,fixture.protocol)
        self.assertEqual(result["errors"],[])
        self.assertTrue(result["complete"])
        self.assertFalse(result["statistics"]["inference_eligible"])
        self.assertIsNone(result["statistics"]["score_interval"])
        fixture.run["settings"]["smoke"] = False
        fixture.save()
        self.assertTrue(auditor.audit_child(fixture.directory,fixture.protocol)["errors"])

    def test_new_option_protocol_replays_512_games(self):
        result = auditor.audit_child(self.fixture.directory, self.fixture.protocol)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["output_checks"]), 512)

    def test_real_pv_ponder_and_quit_corruption_are_rejected(self):
        path = self.fixture.match/self.fixture.records[0]["protocol_log"]
        saved = [json.loads(line) for line in path.read_text().splitlines()]
        best = next(i for i, row in enumerate(saved) if row["line"].startswith("bestmove "))
        for corruption in ("pv", "ponder", "quit", "tablebase"):
            events = copy.deepcopy(saved)
            if corruption == "pv":
                events.insert(best, dict(events[best], line="info depth 1 pv a1a1"))
            elif corruption == "ponder":
                events[best]["line"] += " ponder a1a1"
            elif corruption == "quit":
                events.pop()
            else:
                first_go = next(i for i, event in enumerate(events) if event["line"].startswith("go "))
                events.insert(first_go, dict(events[first_go], line="setoption name SyzygyPath value /tables"))
            jsonl(path, events)
            result = auditor.audit_child(self.fixture.directory, self.fixture.protocol)
            self.assertFalse(result["complete"], corruption)
            self.assertTrue(result["errors"], corruption)
        jsonl(path, saved)


    def test_raw_search_cannot_enable_unrelated_hints_or_change_continuation(self):
        path = self.fixture.match/self.fixture.records[0]["protocol_log"]
        saved = [json.loads(line) for line in path.read_text().splitlines()]
        first_go = next(i for i, event in enumerate(saved) if event["line"].startswith("go "))
        role = saved[first_go]["engine"]
        expected = auditor.ROLE_OPTIONS[role]["Continuation History"]
        for name, value in (("TT Move Hints", "true"),
                            ("Continuation History", "false" if expected == "true" else "true")):
            with self.subTest(name=name):
                events = copy.deepcopy(saved)
                events.insert(first_go, dict(events[first_go], line=f"setoption name {name} value {value}"))
                jsonl(path, events)
                result = auditor.audit_child(self.fixture.directory, self.fixture.protocol)
                self.assertFalse(result["complete"])
                self.assertTrue(result["errors"])
        jsonl(path, saved)

    def test_clock_and_increment_and_missing_evidence_fail(self):
        game = self.fixture.records[0]
        saved = copy.deepcopy(game)
        for field, value in (("clock_before", 60.), ("clock_after", 15.35), ("elapsed_seconds", .75)):
            game["moves"][0][field] = value
            self.fixture.save()
            self.assertTrue(auditor.audit_child(self.fixture.directory, self.fixture.protocol)["errors"])
            game.clear(); game.update(copy.deepcopy(saved))
        self.fixture.save()
        (self.fixture.match/game["pgn"]).write_text("bad pgn")
        self.assertTrue(auditor.audit_child(self.fixture.directory, self.fixture.protocol)["errors"])

    def test_wrong_binary_role_fails(self):
        self.fixture.run["engines"]["candidate"]["executable"] = self.fixture.run["engines"]["opponent"]["executable"]
        self.fixture.save()
        self.assertTrue(auditor.audit_child(self.fixture.directory, self.fixture.protocol)["errors"])

    def test_partial_raw_evidence_withholds_inference(self):
        self.fixture.records.pop()
        self.fixture.run["status"] = self.fixture.launch["status"] = "cancelled"
        self.fixture.save()
        result = auditor.audit_child(self.fixture.directory, self.fixture.protocol)
        self.assertFalse(result["complete"])
        self.assertFalse(result["statistics"]["inference_eligible"])

class OutputAndSourceTests(unittest.TestCase):
    """Small real chess records exercise additions without campaign stubs."""
    def test_missing_or_malformed_smoke_parent_returns_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="chess0live-smoke-malformed-") as temporary:
            directory = Path(temporary)
            self.assertFalse(auditor.audit_smoke(directory)["passed"])
            for document in (None, [], {},
                             {"schema_version":1,"protocol_id":auditor.PROTOCOL_ID,"quiet_host":False},
                             {"schema_version":1,"protocol_id":auditor.PROTOCOL_ID,"quiet_host":True,
                              "frozen":{},"sources":{},"configuration":{},"clock_smoke":None},
                             {"schema_version":1,"protocol_id":auditor.PROTOCOL_ID,"quiet_host":True,
                              "frozen":{},"sources":{},"configuration":{},"clock_smoke":[]}):
                write_json(directory/"campaign.json",document)
                result = auditor.audit_smoke(directory)
                self.assertFalse(result["passed"])
                self.assertTrue(result["errors"])
                self.assertFalse(result["inference_eligible"])
                self.assertIsNone(result["smoke_started_utc"])

    def test_preparation_pin_schema_membership_and_ambiguity(self):
        with tempfile.TemporaryDirectory(prefix="phase4f13-pins-audit-") as directory:
            root = Path(directory)
            path = root/auditor.PIN_FILE
            path.parent.mkdir(parents=True)
            valid = {"schema_version": 1, "protocol_id": auditor.PROTOCOL_ID,
                     "input_sha256": {name: "1"*64 for name in auditor.PINNED_INPUTS}}
            with patch.object(auditor, "ROOT", root):
                write_json(path, valid)
                self.assertEqual(auditor.input_pins(), valid["input_sha256"])
                for corruption in ("old_protocol", "missing_source", "extra_source", "bad_hash", "bool_schema", "duplicate_key"):
                    with self.subTest(corruption=corruption):
                        document = copy.deepcopy(valid)
                        if corruption == "old_protocol":
                            document["protocol_id"] = "phase4f3-combined-512-v1"
                        elif corruption == "missing_source":
                            document["input_sha256"].pop(auditor.BUILD_SOURCE_NAMES[0])
                        elif corruption == "extra_source":
                            document["input_sha256"]["unexpected.py"] = "1"*64
                        elif corruption == "bad_hash":
                            document["input_sha256"][auditor.GENERATOR] = "invalid"
                        elif corruption == "bool_schema":
                            document["schema_version"] = True
                        write_json(path, document)
                        if corruption == "duplicate_key":
                            path.write_text(path.read_text().replace('"schema_version": 1,', '"schema_version": 1, "schema_version": 1,'))
                        with self.assertRaises(ValueError):
                            auditor.input_pins()

    def test_valid_pv_and_ponder_are_replayed(self):
        rows = [("candidate", "to_engine", "setoption name SyzygyPath value "),
                ("candidate", "to_engine", "position startpos"),
                ("candidate", "to_engine", "go wtime 60000 btime 60000 winc 600 binc 600"),
                ("candidate", "from_engine", "info depth 2 pv e2e4 e7e5"),
                ("candidate", "from_engine", "bestmove e2e4 ponder e7e5"),
                ("candidate", "to_engine", "quit"), ("opponent", "to_engine", "quit")]
        events = [dict(engine=r, direction=d, line=l, monotonic_ns=t) for t, (r,d,l) in enumerate(rows)]
        report = auditor.audit_output_transcript(events)
        self.assertEqual(report, {"search_windows": [(2, 4)], "pv_plies": 2, "ponders": 1})
        for replacement in ("info depth 2 pv e2e4 e2e3", "info depth 2 pv 0000"):
            events[3]["line"] = replacement
            with self.assertRaises(ValueError):
                auditor.audit_output_transcript(events)

    def test_saved_pgn_manifest_and_real_roots_are_independently_verified(self):
        with tempfile.TemporaryDirectory(prefix="phase4f13-pgn-audit-") as directory:
            root = Path(directory)
            folder = root/"results/original"; folder.mkdir(parents=True)
            path = folder/"game.pgn"
            path.write_text('[Result "*"]\n\n1. e4 e5 2. Nf3 *\n')
            board, keys = chess.Board(), {auditor.root_key(chess.Board())}
            for move in ("e2e4", "e7e5", "g1f3"):
                board.push_uci(move); keys.add(auditor.root_key(board))
            def digest_json(value):
                return hashlib.sha256((json.dumps(value, indent=2, ensure_ascii=True)+"\n").encode()).hexdigest()
            record = {"path": "results/original", "kind": "saved-pgn-directory",
                      "sha256": digest_json([{"path": "game.pgn", "sha256": asset(path)["sha256"]}]),
                      "entries": 1, "unique_roots": 4, "canonical_roots_sha256": digest_json(sorted(keys)),
                      "exceptions": [], "replay_counts": {"files": 1, "games": 1, "legal_prefix_games": 0, "invalid_initial_games": 0}}
            metadata = root/auditor.GENERATION_METADATA; metadata.parent.mkdir(parents=True)
            write_json(metadata, {"sources": [record], "saved_game_unique_roots": 4})
            with patch.object(auditor, "ROOT", root):
                self.assertEqual(auditor.AggregateAudit(root).saved_roots(), keys)
                path.write_text(path.read_text().replace("Nf3", "Nc3"))
                with self.assertRaisesRegex(ValueError, "byte manifest"):
                    auditor.AggregateAudit(root).saved_roots()
                record["sha256"] = digest_json([{"path": "game.pgn", "sha256": asset(path)["sha256"]}])
                write_json(metadata, {"sources": [record], "saved_game_unique_roots": 4})
                with self.assertRaisesRegex(ValueError, "canonical roots"):
                    auditor.AggregateAudit(root).saved_roots()


if __name__ == "__main__":
    unittest.main()
