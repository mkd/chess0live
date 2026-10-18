#!/usr/bin/env python3
"""Data-only master-audit checks and real raw-child replay corruption checks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Aggregate fixtures mock only the expensive raw-child auditor; they still use
512 records, 256 independently replayed full legal histories, real files and
hashes, and complete schedules/resource admissions. Separate raw-child tests
exercise the actual inherited PGN/UCI verifier. No engine process is started.
"""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import audit_phase3g as auditor
import chess

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
        while len(entries) < 256:
            board, moves = chess.Board(), []
            for _ in range(16):
                if board.outcome(claim_draw=True):
                    break
                move = rng.choice(list(board.legal_moves)); moves.append(move.uci()); board.push(move)
            key = auditor.root_key(board)
            if len(moves) == 16 and not board.outcome(claim_draw=True) and key not in roots:
                roots.add(key)
                entries.append({"id": f"synthetic-full-history-{len(entries)+1}", "moves": moves})
        cls.entries = entries

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="chess0live-phase3g-audit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.campaign = self.root/"campaign"; self.campaign.mkdir()
        self.engine = self.root/"engine"; self.engine.write_bytes(b"synthetic never executed")
        self.network = self.root/"network"; self.network.write_bytes(b"synthetic never loaded")
        sources = {}
        for name in auditor.REQUIRED_SOURCES:
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((REPO/name).read_bytes() if name in auditor.PRIOR_SUITE_SHA256 or name == auditor.GENERATION_METADATA
                             else b"synthetic source\n")
            sources[name] = {key: value for key, value in asset(path).items() if key != "path"}
        assets = {"engine": asset(self.engine), "network": asset(self.network)}
        for index in range(1, 5):
            path = self.root/f"tests/data/openings-phase3g-{index}.json"
            write_json(path, {"openings": self.entries[(index-1)*64:index*64]})
            assets[f"openings_{index}"] = asset(path)
        for name, value in (("ROOT", self.root), ("ENGINE_SHA256", assets["engine"]["sha256"]),
                            ("NETWORK_SHA256", assets["network"]["sha256"]),
                            ("OPENING_SHA256", tuple(assets[f"openings_{i}"]["sha256"] for i in range(1, 5)))):
            p = patch.object(auditor, name, value); p.start(); self.addCleanup(p.stop)
        self.start = datetime(2026, 10, 18, 20, 0, tzinfo=timezone.utc)
        self.end = self.start+timedelta(minutes=5)
        cutoff = self.start+timedelta(hours=8)
        self.cfg = {"settings": dict(auditor.SETTINGS), "pairs": 256, "games": 512, "shards": 4,
                    "shard_pairs": 64, "active_search_workers": 4, "resident_engines": 8,
                    "resource_poll_seconds": 1., "max_resource_gap_seconds": 5., "seeds": list(auditor.SEEDS), "ponder": False,
                    "diagnostics": False, "engines": [
                        {"role": role, "executable": str(self.engine), "network": str(self.network),
                         "network_option": "EvalFile", "arguments": [], "source_revision": "synthetic",
                         "extra_options": options} for role, options in auditor.ROLE_OPTIONS.items()]}
        self.policy = {"timezone": "Europe/Helsinki", "local_time": self.start.isoformat(), "source": "nighttime",
                       "percent": 80, "logical_cpus": 18, "max_cpu_workers": 14, "memory_fraction": .8,
                       "active_search_workers": 4, "resident_engines": 8,
                       "estimated_memory_bytes": 4*(2*64*1024**2+8*self.network.stat().st_size+256*1024**2),
                       "physical_memory_bytes": 64*1024**3, "memory_estimate_is_hard_cap": False}
        self.history = [{"observed_utc": self.start.isoformat(), "trigger": "initial",
                         "policy": copy.deepcopy(self.policy), "within_limits": True}]
        ready_engines = []
        for role in auditor.ROLE_OPTIONS:
            configured = {"Hash": 64, "Threads": 1, "EvalFile": str(self.network), "Move Overhead": 20,
                          "Search Diagnostics": False, "Time Policy": "classic", "Capture Ordering": "mvv-lva",
                          "Late Move Reductions": role == "candidate"}
            options = {name: {"type": "check", "default": False} for name in
                       ("Ponder", "Search Diagnostics", "Late Move Reductions")}
            options.update({"Time Policy": {"type": "combo", "default": "classic", "var": ["classic", "forecast"]},
                            "Capture Ordering": {"type": "combo", "default": "mvv-lva", "var": ["mvv-lva", "see"]}})
            transcript = [{"engine": role, "direction": direction, "line": line, "monotonic_ns": tick}
                          for tick, (direction, line) in enumerate((("to_engine", "uci"), ("from_engine", "uciok"),
                             ("to_engine", "isready"), ("from_engine", "readyok"), ("to_engine", "quit")), 1)]
            ready_engines.append({"role": role, "configured": configured, "options": options, "transcript": transcript})
        self.master = {"schema_version": 1, "protocol_id": auditor.PROTOCOL_ID, "status": "finished",
                       "started_utc": self.start.isoformat(), "checked_utc": self.start.isoformat(),
                       "finished_utc": self.end.isoformat(), "cutoff_utc": cutoff.isoformat(),
                       "launch_policy": {"timezone": "Europe/Helsinki", "local_time": self.start.isoformat(),
                                         "nighttime": True, "allow_daytime": False, "cutoff_utc": cutoff.isoformat(),
                                         "cutoff_local": cutoff.isoformat(), "remaining_seconds": 28800.,
                                         "launch_window": "23:00–23:15 Europe/Helsinki"},
                       "configuration": self.cfg, "configuration_sha256": auditor.child_auditor.canonical_digest(self.cfg),
                       "frozen": assets, "sources": sources, "artifacts_before": {"assets": assets, "sources": sources},
                       "shards": [{"index": i, "protocol_id": f"{auditor.PROTOCOL_ID}-shard-{i}", "seed": auditor.SEEDS[i-1],
                                   "path": f"shard-{i}", "openings": assets[f"openings_{i}"]} for i in range(1, 5)],
                       "preflight": {"opening_count": 256, "distinct_roots": 256, "previous_root_count": 120,
                                     "resource_policy": copy.deepcopy(self.policy), "engines": ready_engines},
                       "protocol": {"path": "protocol.md", "sha256": sources[auditor.PROTOCOL_DOCUMENT]["sha256"]},
                       "shard_statuses": []}
        self.master["artifacts_after"] = {"assets": copy.deepcopy(assets), "sources": copy.deepcopy(sources),
                                          "unchanged": True, "configuration_sha256": self.master["configuration_sha256"]}
        (self.campaign/"protocol.md").write_bytes((self.root/auditor.PROTOCOL_DOCUMENT).read_bytes())
        self.children = []
        for index in range(1, 5):
            directory = self.campaign/f"shard-{index}"; (directory/"match").mkdir(parents=True)
            begin = self.start+timedelta(seconds=2); run_start = begin+timedelta(seconds=1)
            run_end = run_start+timedelta(seconds=257); finish = run_end+timedelta(seconds=1)
            child_cfg = {"pairs": 64, "seed": auditor.SEEDS[index-1], "settings": dict(auditor.SETTINGS),
                         "engines": self.cfg["engines"], "ponder": False, "diagnostics": False}
            launch = {"assets": {"engine": assets["engine"], "network": assets["network"], "openings": assets[f"openings_{index}"]},
                      "sources": sources, "configuration": child_cfg, "status": "finished", "started_utc": begin.isoformat(),
                      "finished_utc": finish.isoformat(), "launch_policy": {"cutoff_utc": cutoff.isoformat(), "allow_daytime": False},
                      "preflight": {"engines": copy.deepcopy(ready_engines)}}
            defs, _ = auditor.definitions({"openings": self.entries[(index-1)*64:index*64]}, full_history=True)
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
                                    estimated_memory_bytes=self.policy["estimated_memory_bytes"]//4)
                    record = {"game_id": game_id, "pair_id": pair["pair_id"], "opening_key": pair["opening_key"],
                              "candidate_color": color, "candidate_score": .5, "status": "complete", "result": "1/2-1/2",
                              "termination": "threefold_repetition", "resource_policy": resource,
                              "started_utc": (admission+timedelta(milliseconds=100)).isoformat(),
                              "finished_utc": (admission+timedelta(seconds=1)).isoformat(),
                              "pgn": game_id+".pgn", "protocol_log": game_id+".protocol.jsonl"}
                    for key in ("pgn", "protocol_log"):
                        (directory/"match"/record[key]).write_text("mocked raw auditor fixture\n")
                    records.append(record)
                    self.history.append({"observed_utc": admission.isoformat(), "trigger": "before_game", "shard_index": index,
                                         "game_id": game_id, "policy": copy.deepcopy(self.policy), "within_limits": True})
            self.master["shard_statuses"].append({"index": index, "status": "finished", "finished_utc": finish.isoformat()})
            self.children.append({"directory": directory, "launch": launch, "run": run, "records": records})
        for second in range(1, 262):
            self.history.append({"observed_utc": (self.start+timedelta(seconds=second)).isoformat(), "trigger": "periodic",
                                 "policy": copy.deepcopy(self.policy), "within_limits": True})
        self.history.append({"observed_utc": self.end.isoformat(), "trigger": "final",
                             "policy": copy.deepcopy(self.policy), "within_limits": True})
        self.history.sort(key=lambda row: row["observed_utc"])
        self.raw_reports = {i: {"errors": [], "complete": True, "statistics": {"inference_eligible": True},
                               "input_sha256": {}, "live_source_differences": [], "decision": "inconclusive"} for i in range(1, 5)}
        def raw_audit(directory, protocol):
            index = int(directory.name.rsplit("-", 1)[1])
            self.assertEqual(protocol, auditor.child_protocol(index))
            return copy.deepcopy(self.raw_reports[index])
        p = patch.object(auditor.child_auditor, "audit", side_effect=raw_audit); p.start(); self.addCleanup(p.stop)
        self.save()

    def save(self):
        for child in self.children:
            write_json(child["directory"]/"launch.json", child["launch"])
            write_json(child["directory"]/"match/run.json", child["run"])
            jsonl(child["directory"]/"match/games.jsonl", child["records"])
        path = self.campaign/"resource-history.jsonl"; jsonl(path, self.history)
        self.master["resource_history"] = {"path": path.name, "observations": len(self.history), "sha256": asset(path)["sha256"]}
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

    def test_complete_512_game_aggregate(self):
        result = self.check("inconclusive")
        self.assertEqual(result["statistics"]["included_pairs"], 256)
        self.assertEqual(result["statistics"]["recorded_games"], 512)
        self.assertAlmostEqual(result["statistics"]["radius"], .08488134473378872)
        self.assertEqual(len({p["pair_id"] for p in result["statistics"]["included_pair_scores"]}), 256)

    def test_positive_and_negative_half_point_boundaries(self):
        for points, decision in ((299, "inconclusive"), (299.5, "eligible_for_confirmation_review"),
                                 (212.5, "negative_evidence"), (213, "inconclusive")):
            with self.subTest(points=points):
                self.score(points); self.check(decision)

    def test_candidate_forfeit_precedes_positive_score(self):
        self.score(350)
        self.children[0]["records"][0].update(termination="time_forfeit", clock_loser="candidate")
        self.check("operational_regression")

    def test_master_pin_tampering(self):
        self.master["frozen"]["engine"]["sha256"] = "0"*64
        self.check()

    def test_configuration_options_cannot_authorize_themselves(self):
        self.cfg["engines"][0]["extra_options"] = dict(auditor.ROLE_OPTIONS["candidate"], **{"Capture Ordering": "see"})
        self.master["configuration_sha256"] = auditor.child_auditor.canonical_digest(self.cfg)
        self.check()

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
        low, high = self.start+timedelta(seconds=3), self.start+timedelta(seconds=14)
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
        self.history = [event for event in self.history if not (event.get("shard_index") == 4 and event.get("game_id") == "p000064-2")]
        result = self.check()
        self.assertEqual(result["statistics"]["recorded_games"], 511)
        self.assertEqual(result["statistics"]["included_pairs"], 255)

    def test_later_live_doc_edits_are_reported_separately(self):
        (self.root/auditor.PROTOCOL_DOCUMENT).write_text("later documentation update\n")
        result = self.check("inconclusive")
        self.assertIn(auditor.PROTOCOL_DOCUMENT, result["live_source_differences"])

    def test_cli_refuses_existing_output(self):
        output = self.root/"existing.json"; output.write_text("preserve me")
        with self.assertRaises(SystemExit):
            auditor.main(["--campaign", str(self.campaign), "--output", str(output)])
        self.assertEqual(output.read_text(), "preserve me")


class RawChildTests(unittest.TestCase):
    """Use real 128-game PGN/transcript fixtures, independently of master mocks."""
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("phase3g_raw_fixture", REPO/"tests/audit_time_policy_test.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        cls.fixture_class = type("Phase3GRawFixture", (module.CampaignTests,), {"protocol_spec": auditor.child_protocol(1)})
        cls.fixture_class.setUpClass()

    def setUp(self):
        self.fixture = self.fixture_class(methodName="test_complete_campaign_replays_all_games_and_excludes_readiness_time")
        self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)

    def test_new_option_protocol_replays_128_games(self):
        self.fixture.test_complete_campaign_replays_all_games_and_excludes_readiness_time()

    def test_real_transcript_and_pgn_corruption_are_rejected(self):
        self.fixture.test_actual_option_and_pgn_tampering_are_detected()

    def test_real_clock_corruption_is_rejected(self):
        self.fixture.test_charged_clock_and_transmitted_clock_tampering_are_detected()

    def test_real_partial_child_withholds_inference(self):
        self.fixture.test_partial_campaign_retains_observed_results_without_qualification()

    def test_real_unexpected_stderr_is_rejected(self):
        self.fixture.test_unexpected_stderr_is_explicitly_rejected()


if __name__ == "__main__":
    unittest.main()
