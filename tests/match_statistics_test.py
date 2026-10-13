#!/usr/bin/env python3
"""Check paired correlation, exclusions, conservative intervals, and JSON boundaries.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from match_statistics import MINIMUM_PAIRS, relative_elo, summarize_pairs


def game(score, color, pair_id):
    white_points = score if color == "white" else 1 - score
    result = {0: "0-1", 0.5: "1/2-1/2", 1: "1-0"}[white_points]
    return {"pair_id": pair_id, "status": "complete", "candidate_color": color,
            "result": result, "candidate_score": score}


def pair(identifier, first=0.5, second=0.5):
    pair_id = f"p{identifier:06d}"
    return {"pair_id": pair_id, "opening_key": f"fixture-opening-{identifier}",
            "games": [game(first, "white", pair_id), game(second, "black", pair_id)]}


class StatisticsTest(unittest.TestCase):
    def test_exact_candidate_perspective_and_pair_distribution(self):
        pairs = [pair(0, 1, 1), pair(1, 1, 0.5), pair(2, 1, 0),
                 pair(3, 0, 0.5), pair(4, 0, 0)]
        before = copy.deepcopy(pairs)
        result = summarize_pairs(pairs)
        self.assertEqual(result["wdl"], {"wins": 4, "draws": 2, "losses": 4})
        self.assertEqual(result["pair_point_counts"],
                         {"0.0": 1, "0.5": 1, "1.0": 1, "1.5": 1, "2.0": 1})
        self.assertEqual(result["score"], 0.5)
        self.assertEqual(result["relative_elo"]["value"], 0)
        self.assertEqual(result["included_games"], 10)
        self.assertEqual(pairs, before, "summarizing must not mutate raw evidence")

    def test_minimum_count_and_completed_experiment_are_required(self):
        pairs = [pair(i) for i in range(MINIMUM_PAIRS)]
        pending = summarize_pairs(pairs)
        self.assertFalse(pending["inference_eligible"])
        self.assertIsNone(pending["uncertainty"]["score_interval"])
        small = summarize_pairs(pairs[:-1], experiment_complete=True)
        self.assertFalse(small["inference_eligible"])
        self.assertIn("insufficient_complete_pairs", small["uncertainty"]["withheld_reasons"])
        full = summarize_pairs(pairs, experiment_complete=True)
        self.assertTrue(full["inference_eligible"])
        self.assertIsNotNone(full["uncertainty"]["score_interval"])

    def test_hoeffding_uses_pair_count_not_game_count(self):
        # Perfectly correlated games: 50 double wins and 50 double losses.
        # Counting games as 200 independent samples would narrow the bound wrongly.
        pairs = [pair(i, 1 if i < 50 else 0, 1 if i < 50 else 0) for i in range(100)]
        result = summarize_pairs(pairs, experiment_complete=True)
        radius = math.sqrt(math.log(40) / 200)
        interval = result["uncertainty"]["score_interval"]
        self.assertAlmostEqual(interval["lower"], 0.5 - radius)
        self.assertAlmostEqual(interval["upper"], 0.5 + radius)
        self.assertEqual(result["uncertainty"]["sample_size_pairs"], 100)
        self.assertGreater(radius, math.sqrt(math.log(40) / 400))

    def test_draws_do_not_produce_a_false_zero_width_interval(self):
        result = summarize_pairs([pair(i) for i in range(100)], experiment_complete=True)
        interval = result["uncertainty"]["score_interval"]
        self.assertLess(interval["lower"], 0.5)
        self.assertGreater(interval["upper"], 0.5)

    def test_all_wins_and_all_losses_encode_infinities_explicitly(self):
        for score, interpretation, boundary in [(1, "positive_infinity", "upper"),
                                                  (0, "negative_infinity", "lower")]:
            result = summarize_pairs([pair(i, score, score) for i in range(100)],
                                     experiment_complete=True)
            self.assertEqual(result["relative_elo"], {"value": None, "interpretation": interpretation})
            self.assertEqual(result["uncertainty"]["relative_elo_interval"][boundary],
                             {"value": None, "interpretation": interpretation})
            self.assertEqual(result["uncertainty"]["score_interval"][boundary], score)
            json.dumps(result, allow_nan=False)

    def test_exclude_whole_error_pair_and_withhold_selection_biased_inference(self):
        pairs = [pair(i, 1, 1) for i in range(30)]
        failed = pair(30, 0, 1)
        failed["games"][0]["status"] = "time_forfeit"
        pairs.append(failed)
        result = summarize_pairs(pairs, experiment_complete=True)
        self.assertEqual(result["included_pairs"], 30)
        self.assertEqual(result["excluded_pairs"], 1)
        self.assertEqual(result["included_games"], 60)
        self.assertEqual(result["excluded_games"], 2)
        self.assertEqual(result["wdl"], {"wins": 60, "draws": 0, "losses": 0})
        self.assertEqual(result["game_status_counts"], {"complete": 61, "time_forfeit": 1})
        self.assertFalse(result["inference_eligible"])
        self.assertIsNone(result["uncertainty"]["score_interval"])
        self.assertIn("excluded_pairs_may_bias_results", result["uncertainty"]["withheld_reasons"])

    def test_incomplete_pair_is_not_a_single_independent_game(self):
        incomplete = pair(0, 1, 1)
        incomplete["games"].pop()
        result = summarize_pairs([incomplete], experiment_complete=True)
        self.assertEqual(result["included_pairs"], 0)
        self.assertEqual(result["excluded_games"], 1)
        self.assertIsNone(result["score"])
        self.assertEqual(result["relative_elo"]["interpretation"], "no_completed_pairs")
        json.dumps(result, allow_nan=False)

    def test_malformed_and_duplicate_records_are_excluded(self):
        bad = []
        for index, mutate in enumerate([
            lambda p: p["games"][1].update(candidate_color="white"),
            lambda p: p["games"][1].update(result="*"),
            lambda p: p["games"][1].update(candidate_score=float("nan")),
            lambda p: p["games"][1].update(pair_id="wrong"),
            lambda p: p["games"].append(p["games"][0].copy()),
            lambda p: p.update(games="not a collection"),
            lambda p: p.update(pair_id=[]),
        ]):
            item = pair(index)
            mutate(item)
            bad.append(item)
        bad.extend([pair(100), pair(100), None, {"pair_id": "empty", "games": []}])
        result = summarize_pairs(bad, experiment_complete=True)
        self.assertEqual(result["included_pairs"], 0)
        self.assertEqual(result["excluded_pairs"], len(bad))
        self.assertIn("duplicate_pair_id", result["excluded_pair_details"][7]["reasons"])
        json.dumps(result, allow_nan=False)

    def test_optional_precomputed_score_is_not_required(self):
        entry = pair(0, 1, 0)
        for record in entry["games"]:
            del record["candidate_score"]
        result = summarize_pairs([entry])
        self.assertEqual(result["score"], 0.5)

    def test_real_clock_forfeit_is_scored_and_reported(self):
        entry = pair(0, 0, 0.5)
        entry["games"][0]["termination"] = "time_forfeit"
        entry["games"][1]["termination"] = "time_forfeit"
        result = summarize_pairs([entry], experiment_complete=True)
        self.assertEqual(result["wdl"], {"wins": 0, "draws": 1, "losses": 1})
        self.assertEqual(result["included_time_forfeit_games"], 2)
        self.assertEqual(result["termination_counts"], {"time_forfeit": 2})
        self.assertEqual(result["excluded_pairs"], 0)

    def test_repeating_same_opening_does_not_create_independent_samples(self):
        pairs = [pair(i, 1, 1) for i in range(100)]
        for entry in pairs:
            entry["opening_key"] = "identical-position-and-opening-moves"
        result = summarize_pairs(pairs, experiment_complete=True)
        self.assertEqual(result["included_pairs"], 100)
        self.assertEqual(result["distinct_identified_openings"], 1)
        self.assertEqual(result["score"], 1)
        self.assertFalse(result["inference_eligible"])
        self.assertIsNone(result["uncertainty"]["score_interval"])
        self.assertIn("repeated_openings_do_not_establish_independent_samples",
                      result["uncertainty"]["withheld_reasons"])

    def test_missing_opening_identity_withholds_inference(self):
        pairs = [pair(i) for i in range(30)]
        del pairs[0]["opening_key"]
        result = summarize_pairs(pairs, experiment_complete=True)
        self.assertFalse(result["inference_eligible"])
        self.assertIn("opening_identity_not_recorded", result["uncertainty"]["withheld_reasons"])

    def test_game_opening_identity_must_match_pair(self):
        entry = pair(0)
        entry["games"][0]["opening_key"] = "different-opening"
        result = summarize_pairs([entry])
        self.assertEqual(result["excluded_pairs"], 1)
        self.assertIn("game_opening_key_mismatch", result["excluded_pair_details"][0]["reasons"])

    def test_game_opening_identity_must_agree_without_pair_key(self):
        entry = pair(0)
        del entry["opening_key"]
        entry["games"][0]["opening_key"] = "first-opening"
        entry["games"][1]["opening_key"] = "different-opening"
        result = summarize_pairs([entry])
        self.assertEqual(result["included_pairs"], 0)
        self.assertIn("game_opening_key_mismatch", result["excluded_pair_details"][0]["reasons"])
        entry["games"][1]["opening_key"] = "first-opening"
        result = summarize_pairs([entry])
        self.assertEqual(result["included_pair_scores"][0]["opening_key"], "first-opening")

    def test_empty_input_and_json_safety(self):
        result = summarize_pairs([], experiment_complete=True)
        self.assertEqual(result["included_games"], 0)
        self.assertEqual(result["game_status_counts"], {})
        self.assertEqual(result["pair_point_counts"]["1.0"], 0)
        self.assertFalse(result["inference_eligible"])
        json.dumps(result, allow_nan=False)

    def test_relative_elo_formula_and_invalid_values(self):
        self.assertAlmostEqual(relative_elo(0.75)["value"], 400 * math.log10(3))
        self.assertAlmostEqual(relative_elo(0.25)["value"], -400 * math.log10(3))
        self.assertTrue(math.isfinite(relative_elo(1e-300)["value"]))
        for invalid in [-1, 2, float("nan"), float("inf"), True, "0.5"]:
            with self.assertRaises(ValueError):
                relative_elo(invalid)
        for invalid in [0, 1, -1, float("nan"), float("inf"), True, "0.95"]:
            with self.assertRaises(ValueError):
                summarize_pairs([], invalid)
        with self.assertRaises(ValueError):
            summarize_pairs([], experiment_complete="true")

    def test_higher_confidence_makes_interval_wider(self):
        pairs = [pair(i, 1, 0.5) for i in range(100)]
        low = summarize_pairs(pairs, 0.9, experiment_complete=True)["uncertainty"]
        high = summarize_pairs(pairs, 0.99, experiment_complete=True)["uncertainty"]
        self.assertGreater(high["radius"], low["radius"])
        interval = low["relative_elo_interval"]
        score_interval = low["score_interval"]
        self.assertEqual(interval["lower"], relative_elo(score_interval["lower"]))
        self.assertEqual(interval["upper"], relative_elo(score_interval["upper"]))


if __name__ == "__main__":
    unittest.main()
