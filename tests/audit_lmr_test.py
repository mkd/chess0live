#!/usr/bin/env python3
"""Exercise LMR evidence isolation and the predeclared 64-pair decision gates.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_lmr
import audit_time_policy as auditor
import audit_time_policy_test as fixture


class LmrCampaignTests(fixture.CampaignTests):
    # Reuse synthetic evidence construction, not a real engine or held-out game.
    # Every historical corruption/replay test also runs on 128 LMR games.
    protocol_spec = audit_lmr.PROTOCOL

    def test_lmr_toggle_in_actual_transcript_must_match_role(self):
        record = next(g for g in self.records if g["candidate_color"] == "white")
        path = self.match / record["protocol_log"]
        path.write_text(path.read_text().replace("Late Move Reductions value true",
                                                "Late Move Reductions value false"))
        result = self.assert_invalid()
        self.assertTrue(any("Actual UCI options differ" in error for error in result["errors"]))

    def test_forecast_cannot_be_combined_with_lmr(self):
        self.launch["configuration"]["engines"][0]["extra_options"]["Time Policy"] = "forecast"
        self.launch["configuration_sha256"] = auditor.canonical_digest(self.launch["configuration"])
        self.save()
        result = self.assert_invalid()
        self.assertIn("Experimental modes are not isolated", result["errors"])

    def test_time_policy_auditor_rejects_lmr_protocol(self):
        result = auditor.audit(self.directory)
        self.assertIn("Unknown campaign protocol", result["errors"])

    def test_full_sample_uses_64_pair_uncertainty(self):
        result = auditor.audit(self.directory, self.protocol)
        self.assertEqual(result["errors"], [])
        self.assertAlmostEqual(result["statistics"]["radius"], math.sqrt(math.log(40)/128))
        self.assertEqual(result["statistics"]["included_pairs"], 64)


class DecisionTests(unittest.TestCase):
    def test_exact_predeclared_lmr_thresholds(self):
        for points, expected in ((85.5, "inconclusive"), (86., "eligible_for_confirmation_review"),
                                 (42., "negative_evidence"), (42.5, "inconclusive")):
            with self.subTest(points=points):
                radius = math.sqrt(math.log(40)/128)
                score = points/128
                computed = {"inference_eligible": True,
                            "score_interval": {"lower": max(0, score-radius), "upper": min(1, score+radius)}}
                self.assertEqual(auditor.classify(computed, True, [], 0), expected)
                self.assertEqual(auditor.classify(computed, True, [], 1), "operational_regression")
                self.assertEqual(auditor.classify(computed, False, [], 0), "invalid_or_incomplete")
                self.assertEqual(auditor.classify(computed, True, ["corrupt"], 0), "invalid_or_incomplete")


if __name__ == "__main__":
    unittest.main()
