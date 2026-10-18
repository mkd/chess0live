#!/usr/bin/env python3
"""Focused validation checks for bounded, exposed clock diagnostics.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probe_clocks as probe


def replies(case, enabled=False):
    board = probe.board_for(case["position_command"][len("position "):])
    move = next(iter(board.legal_moves)).uci()
    return [f"info depth 1 seldepth 1 score cp 0 nodes 1 time 1 pv {move}",
            "info string search-iteration v1 depth 1 completed true nodes 1 duration_ms 1.000 elapsed_ms 1.000",
            "info string ordering v1 policy mvv-lva see_calls 0 losing_captures 0",
            f"info string lmr v1 enabled {str(enabled).lower()} reductions 0 researches 0 fail_lows 0 verified_cutoffs 0",
            f"info string search-summary v1 policy classic forecast_active false stop_reason soft_time nodes 1 completed_depth 1 elapsed_ms 1.000 soft_ms 100.000 hard_ms {case['hard_limit_ms']:.3f} target_ms 100.000 predicted_next_ms 0.000",
            f"bestmove {move}"]


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.document, self.cases = probe.load_cases(probe.DEFAULT_POSITIONS)

    def changed_fixture(self, mutate):
        document = copy.deepcopy(self.document)
        mutate(document)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(document))
            return probe.load_cases(path)

    def test_all_historical_roots_and_both_modes_validate(self):
        self.assertEqual(len(self.cases), 13)
        for case in self.cases:
            for enabled in (False, True):
                self.assertEqual(probe.validate(replies(case, enabled), enabled, case)["trace"]["summary"]["completed_depth"], 1)

    def test_reject_command_injection_and_additional_go_limits(self):
        for key, value in (("position_command", "position startpos moves e2e4\nquit"),
                           ("go_command", "go wtime 620 btime 620 winc 600 binc 600 depth 1"),
                           ("go_command", "go wtime 620 wtime 620 winc 600 binc 600"),
                           ("go_command", "go wtime -1 btime 620 winc 600 binc 600")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.changed_fixture(lambda d: d["cases"][0].update({key: value}))

    def test_reject_duplicate_missing_or_changed_evidence(self):
        mutations = [lambda d: d["cases"].pop(),
                     lambda d: d["cases"][1].update(id=d["cases"][0]["id"]),
                     lambda d: d["cases"][0].update(final_fen="invalid"),
                     lambda d: d["cases"][0].update(hard_limit_ms=float("nan")),
                     lambda d: d["cases"][0].update(input_clock_ms=True),
                     lambda d: d["cases"][0].update(clock_before_ms=10)]
        for mutate in mutations:
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.changed_fixture(mutate)

    def test_reject_illegal_pv_and_bestmove(self):
        case = self.cases[0]
        for index, text in ((0, "info depth 1 seldepth 1 score cp 0 nodes 1 time 1 pv a1a8"),
                            (-1, "bestmove a1a8")):
            lines = replies(case)
            lines[index] = text
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe.validate(lines, False, case)

    def test_reject_nonfinite_budget_wrong_mode_and_overspending(self):
        case = self.cases[0]
        for before, after in (("elapsed_ms 1.000", "elapsed_ms nan"),
                              ("hard_ms 600.000", "hard_ms 601.000"),
                              ("target_ms 100.000", "target_ms 900.000"),
                              ("enabled false", "enabled true")):
            with self.subTest(after=after), self.assertRaises(ValueError):
                probe.validate([line.replace(before, after) for line in replies(case)], False, case)

    def test_existing_output_is_not_touched_and_no_process_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence.jsonl"
            output.write_text("preserve me\n")
            with patch.object(probe, "RecordedEngine") as engine, self.assertRaises(ValueError):
                probe.run(Path("missing-engine"), Path("missing-network"), probe.DEFAULT_POSITIONS, output)
            engine.assert_not_called()
            self.assertEqual(output.read_text(), "preserve me\n")

    def test_failure_record_is_flushed_without_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, network, output = (root / name for name in ("engine", "network", "evidence.jsonl"))
            binary.write_bytes(b"fake executable")
            network.write_bytes(b"fake network")
            with patch.object(probe, "RecordedEngine", side_effect=RuntimeError("startup failure")) as engine:
                with self.assertRaisesRegex(RuntimeError, "startup failure"):
                    probe.run(binary, network, probe.DEFAULT_POSITIONS, output)
            engine.assert_called_once()
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([r["type"] for r in records], ["metadata", "result", "summary"])
            self.assertEqual(records[1]["status"], "error")
            self.assertEqual(records[-1]["completed_searches"], 0)


if __name__ == "__main__":
    unittest.main()
