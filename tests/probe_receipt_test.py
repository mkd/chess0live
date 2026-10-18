#!/usr/bin/env python3
"""Check receipt controls, failure preservation, and owned-child resumption.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probe_receipt as probe


def replies(elapsed=600):
    return [f"info depth 1 seldepth 1 score cp 0 nodes 1 time {elapsed} pv e2e4",
            f"info string search-iteration v1 depth 1 completed true nodes 1 duration_ms {elapsed}.000 elapsed_ms {elapsed}.000",
            "info string ordering v1 policy mvv-lva see_calls 0 losing_captures 0",
            "info string lmr v1 enabled false reductions 0 researches 0 fail_lows 0 verified_cutoffs 0",
            f"info string search-summary v1 policy classic forecast_active false stop_reason hard_time nodes 1 completed_depth 1 elapsed_ms {elapsed}.000 soft_ms 600.000 hard_ms 600.000 target_ms 600.000 predicted_next_ms 0.000",
            "bestmove e2e4"]


def events(received_ms=600):
    return [{"direction": "to_engine", "line": probe.GO, "monotonic_ns": 1_000_000_000},
            {"direction": "from_engine", "line": "bestmove e2e4",
             "monotonic_ns": 1_000_000_000 + received_ms*1_000_000}]


class ReceiptTests(unittest.TestCase):
    def test_distinguishes_control_consumer_and_engine_delay(self):
        control = probe.measure(replies(), events(), 1_600_000_000, False)
        self.assertTrue(control["reader_within_movetime"])
        self.assertTrue(control["consumer_within_movetime"])
        consumer = probe.measure(replies(), events(), 1_900_000_000, False)
        self.assertTrue(consumer["reader_within_movetime"])
        self.assertFalse(consumer["consumer_within_movetime"])
        self.assertEqual(consumer["consumer_minus_reader_ms"], 300)
        engine = probe.measure(replies(900), events(900), 1_900_000_000, False)
        self.assertFalse(engine["reader_within_movetime"])
        self.assertEqual(engine["reader_minus_internal_ms"], 0)

    def test_rejects_wrong_budget_or_illegal_bestmove(self):
        for before, after in (("hard_ms 600.000", "hard_ms 601.000"),
                              ("bestmove e2e4", "bestmove e2e5")):
            with self.subTest(after=after), self.assertRaises(ValueError):
                probe.measure([s.replace(before, after) for s in replies()], events(), 1_600_000_000, False)

    def test_rejects_missing_duplicate_or_reversed_observations(self):
        for recorded, consumed in ((events()[:1], 1_600_000_000),
                                   (events()+events()[-1:], 1_600_000_000),
                                   (events(), 1_500_000_000), (events(-1), 1_600_000_000)):
            with self.subTest(recorded=recorded), self.assertRaises(ValueError):
                probe.measure(replies(), recorded, consumed, False)

    def test_rejects_timestamp_bound_to_different_legal_move(self):
        recorded = events()
        recorded[-1]["line"] = "bestmove d2d4"
        with self.assertRaisesRegex(ValueError, "disagrees"):
            probe.measure(replies(), recorded, 1_600_000_000, False)

    @unittest.skipUnless(hasattr(signal, "SIGSTOP"), "POSIX pause control")
    def test_pause_always_resumes_owned_live_child_when_interrupted(self):
        process = Mock()
        process.poll.return_value = None
        observations = {}
        with patch.object(probe.time, "sleep", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            probe.pause_process(process, observations=observations)
        self.assertEqual([c.args[0] for c in process.send_signal.call_args_list], [signal.SIGSTOP, signal.SIGCONT])
        self.assertGreaterEqual(observations["resume_return_ns"], observations["stop_request_ns"])

    @unittest.skipUnless(hasattr(signal, "SIGSTOP"), "POSIX pause control")
    def test_pause_records_requests_and_does_not_signal_reaped_child(self):
        process = Mock()
        process.poll.return_value = 0
        with patch.object(probe.time, "sleep") as sleep:
            result = probe.pause_process(process)
        process.send_signal.assert_called_once_with(signal.SIGSTOP)
        sleep.assert_called_once_with(.5)
        self.assertGreaterEqual(result["resume_return_ns"], result["stop_request_ns"])

    def test_existing_output_preserved_without_engine_start(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"prior.jsonl"
            output.write_text("preserve\n")
            with patch.object(probe, "RecordedEngine") as engine, self.assertRaises(ValueError):
                probe.run("missing", "missing", output)
            engine.assert_not_called()
            self.assertEqual(output.read_text(), "preserve\n")

    @unittest.skipUnless(hasattr(signal, "SIGSTOP"), "POSIX pause control")
    def test_startup_failure_is_recorded_once_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary, network, output = (root/p for p in ("engine", "network", "record.jsonl"))
            binary.write_bytes(b"fake engine")
            network.write_bytes(b"fake network")
            with patch.object(probe, "resource_check", return_value={}), \
                    patch.object(probe, "RecordedEngine", side_effect=RuntimeError("startup failed")) as engine:
                with self.assertRaisesRegex(RuntimeError, "startup failed"):
                    probe.run(binary, network, output)
            engine.assert_called_once()
            records = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([r["type"] for r in records], ["metadata", "result", "summary"])
            self.assertEqual(records[-1]["status"], "error")
            self.assertEqual(records[-1]["completed_searches"], 0)


if __name__ == "__main__":
    unittest.main()
