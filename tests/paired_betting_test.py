#!/usr/bin/env python3
"""Check finite-mixture math, sample boundaries and paired-score validation.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""

import itertools
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from paired_betting import LAMBDAS, SCORES, TAIL_THRESHOLD, _counts, _log_capital, summarize


def complete(scores):
    return summarize(scores, expected_pairs=len(scores), experiment_complete=True)


class PairedBettingTest(unittest.TestCase):
    def test_defaults_require_all_1024_predeclared_pairs(self):
        self.assertEqual(summarize([.5] * 1024)["decision"], "unqualified")
        self.assertTrue(summarize([.5] * 1024, experiment_complete=True)["inference_eligible"])
        for count in (0, 1023, 1025):
            value = summarize([.5] * count, experiment_complete=True)
            self.assertFalse(value["inference_eligible"])
            self.assertIsNone(value["score_interval"])
            self.assertIsNone(value["log_e_value_at_half"])
            self.assertEqual(value["decision"], "unqualified")

    def test_unqualified_samples_keep_descriptive_counts(self):
        data = [0, .25, .5, .75, 1]
        before = list(data)
        result = summarize(data)
        self.assertEqual(result["score"], .5)
        self.assertEqual(result["pair_score_counts"], {str(x): 1 for x in SCORES})
        self.assertEqual(len(result["withheld_reasons"]), 2)
        self.assertEqual(data, before)

    def test_invalid_score_values_and_types(self):
        for bad in (True, False, None, "0.5", .1, -.25, 1.25, 10**1000, float("nan"), float("inf"), {}, []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                summarize([bad])
        for bad in (None, {}, ".5", iter([.5]), 3):
            with self.subTest(collection=bad), self.assertRaises(ValueError):
                summarize(bad)

    def test_invalid_completion_and_sample_configuration(self):
        for bad in (True, 0, -1, 1.5, "1024", None):
            with self.subTest(expected=bad), self.assertRaises(ValueError):
                summarize([.5], expected_pairs=bad)
        for bad in (1, 0, "true", None):
            with self.subTest(complete=bad), self.assertRaises(ValueError):
                summarize([.5], experiment_complete=bad)

    def test_all_ties_have_nonzero_uncertainty(self):
        result = complete([.5] * 1024)
        self.assertEqual(result["decision"], "inconclusive")
        self.assertLess(result["score_interval"]["lower"], .5)
        self.assertGreater(result["score_interval"]["upper"], .5)
        self.assertAlmostEqual(sum(result["score_interval"].values()), 1)
        self.assertEqual(result["log_e_value_at_half"], {"positive": 0.0, "negative": 0.0})

    def test_all_wins_losses_and_json_boundaries(self):
        for x, decision, edge, infinity in [(1,"positive","upper","positive_infinity"),
                                           (0,"negative","lower","negative_infinity")]:
            result = complete([x] * 1024)
            self.assertEqual(result["decision"], decision)
            self.assertEqual(result["score_interval"][edge], x)
            self.assertEqual(result["relative_elo"]["interpretation"], infinity)
            json.dumps(result, allow_nan=False)
        json.dumps(summarize([]), allow_nan=False)

    def test_small_sample_cannot_certify_extreme_outcome(self):
        for x in (0,1):
            result = complete([x])
            self.assertEqual(result["score_interval"], {"lower": 0.0,"upper": 1.0})
            self.assertEqual(result["decision"], "inconclusive")

    def test_direct_product_agrees_with_log_mixture(self):
        data = [0, .25, .5, .75, 1, .5]
        for m in (0, .2, .5, .9, 1):
            for sign in (1,-1):
                direct = sum(math.prod(1+sign*l*(x-m) for x in data) for l in LAMBDAS)/len(LAMBDAS)
                self.assertAlmostEqual(math.exp(_log_capital(_counts(data),m,sign)), direct, places=13)

    def test_capital_is_monotone_in_tested_mean(self):
        counts = _counts([0,.25,.5,.75,1] * 30)
        plus = [_log_capital(counts,i/100,1) for i in range(101)]
        minus = [_log_capital(counts,i/100,-1) for i in range(101)]
        self.assertEqual(plus,sorted(plus,reverse=True))
        self.assertEqual(minus,sorted(minus))

    def test_perspective_reversal_reflects_interval_and_decision(self):
        data = [0]*4+[.25]*108+[.5]*708+[.75]*200+[1]*4
        a,b=complete(data),complete([1-x for x in data])
        self.assertEqual((a["decision"],b["decision"]),("positive","negative"))
        self.assertAlmostEqual(a["score_interval"]["lower"],1-b["score_interval"]["upper"])
        self.assertAlmostEqual(a["relative_elo"]["value"],-b["relative_elo"]["value"])

    def test_order_does_not_change_fixed_stake_result(self):
        data=[0,.25,.5,.75,1] * 40
        self.assertEqual(complete(data),complete(list(reversed(data))))

    def test_shared_game_pair_is_one_observation_not_two(self):
        # Perfectly correlated double wins/losses remain one normalized score
        # each. Duplication demonstrably changes the CI and is a caller error.
        data=[0]*50+[1]*50
        a,b=complete(data),complete(data*2)
        self.assertLess(a["score_interval"]["lower"],b["score_interval"]["lower"])
        self.assertGreater(a["score_interval"]["upper"],b["score_interval"]["upper"])

    def test_expected_capital_under_null_is_one_by_exact_enumeration(self):
        # Independent pentanomial data with mean .5; no normal approximation.
        probabilities=(.1,.2,.4,.2,.1)
        for direction in (1,-1):
            expected=0.0
            for indexes in itertools.product(range(5),repeat=4):
                probability=math.prod(probabilities[i] for i in indexes)
                sample=[SCORES[i] for i in indexes]
                expected+=probability*math.exp(_log_capital(_counts(sample),.5,direction))
            self.assertAlmostEqual(expected,1.0,places=12)

    def test_nonconstant_variance_can_preserve_conditional_mean(self):
        # First observation Bernoulli, second conditional distribution varies
        # with first result but has the same .5 conditional mean.
        expected=0.0
        for x,p in [(0,.5),(1,.5)]:
            next_values=[(.5,1)] if x==0 else [(0,.5),(1,.5)]
            for y,q in next_values:
                expected+=p*q*math.exp(_log_capital(_counts([x,y]),.5,1))
        self.assertAlmostEqual(expected,1.0)

    def test_known_symmetric_reference_bounds(self):
        result=complete([0]*4+[.25]*154+[.5]*708+[.75]*154+[1]*4)
        self.assertAlmostEqual(result["score_interval"]["lower"],.4858352078009093,places=12)
        self.assertAlmostEqual(result["score_interval"]["upper"],.5141647921990908,places=12)
        threshold=math.log(TAIL_THRESHOLD)
        for edge,sign in [("lower",1),("upper",-1)]:
            self.assertAlmostEqual(_log_capital(_counts([0]*4+[.25]*154+[.5]*708+[.75]*154+[1]*4),result["score_interval"][edge],sign),threshold,places=10)

    def test_fixed_time_independent_unequal_means_have_bounded_capital(self):
        # Independent Bernoulli variables with means .1 and .9: their average
        # mean is .5 although they lack a common conditional mean. AM-GM gives
        # expectation <=1 at this fixed sample, not optional-stopping validity.
        for sign in (1,-1):
            expected=sum(px*py*math.exp(_log_capital(_counts([x,y]),.5,sign))
                         for x,px in [(0,.9),(1,.1)] for y,py in [(0,.1),(1,.9)])
            self.assertLessEqual(expected,1.0)
            self.assertAlmostEqual(expected,sum(1-.16*l*l for l in LAMBDAS)/len(LAMBDAS))

    def test_large_inputs_stay_finite(self):
        # Avoid exp(product) overflow even under overwhelming evidence.
        result=complete([1]*100000)
        self.assertTrue(math.isfinite(result["log_e_value_at_half"]["positive"]))
        json.dumps(result,allow_nan=False)


if __name__ == "__main__":
    unittest.main()
