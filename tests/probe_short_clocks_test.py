#!/usr/bin/env python3
"""Engine-free checks for the fixed loaded-host short-clock diagnostic.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probe_short_clocks as probe

OFFSET = 1_000_000_000


def sample():
    go = 2_000_000_000
    trace = {"seq": 1, "position_begin_ns": go - 100_000,
             "position_end_ns": go - 50_000, "go_received_ns": go,
             "worker_started_ns": go + 10_000, "search_started_ns": go + 20_000,
             "hard_stop_ns": go + 150_000_000, "leader_finished_ns": go + 150_001_000,
             "joined_ns": go + 150_002_000, "accounted_ns": go + 150_003_000,
             "search_returned_ns": go + 150_004_000, "reply_ready_ns": go + 150_005_000,
             "bestmove_begin_ns": go + 150_006_000, "bestmove_flushed_ns": go + 150_007_000,
             "hard_budget_ns": 150_000_000, "reported_time_ms": 150}
    events, calibrations = [], []
    def event(direction, line, stamp):
        events.append({"direction": direction, "line": line, "monotonic_ns": stamp, "engine": "initial"})
    for identifier in range(6):
        stamp = (go - 1_000_000 if identifier < 3 else go + 180_000_000) + identifier * 100_000
        calibration = {"id": identifier, "engine_ns": stamp,
                       "send_before_ns": stamp + OFFSET - 1000,
                       "send_flushed_ns": stamp + OFFSET - 500,
                       "reader_received_ns": stamp + OFFSET + 1000}
        calibrations.append(calibration)
        event("to_engine", f"clockping {identifier}", calibration["send_before_ns"])
        event("from_engine", f"info string clock-ping v1 id {identifier} now_ns {stamp}", calibration["reader_received_ns"])
    before, after = events[:6], events[6:]
    events = before
    event("to_engine", "position startpos", go + OFFSET - 200_000)
    event("to_engine", "go wtime 170 btime 170 winc 150 binc 150", go + OFFSET - 100_000)
    event("from_engine", "info depth 1 seldepth 1 score cp 0 nodes 10 time 20 nps 500 hashfull 0 tbhits 0 pv e2e4 e7e5", go + OFFSET + 20_100_000)
    event("from_engine", "info nodes 20 time 150 nps 133 hashfull 0 tbhits 0", go + OFFSET + 151_000_000)
    event("from_engine", "bestmove e2e4 ponder e7e5", go + OFFSET + 151_000_000)
    event("from_engine", probe.boundary.TRACE_PREFIX + "v1 " + " ".join(f"{k} {v}" for k, v in trace.items()), go + OFFSET + 151_100_000)
    events.extend(after)
    event("to_engine", "quit", go + OFFSET + 181_000_000)
    return {"case": probe.cases()[0], "load": "serial", "protocol": events,
            "calibrations": calibrations, "cleanup": {"exit_code": 0, "exited": True},
            "consumed_ns": go + OFFSET + 151_200_000,
            "go_ns": go + OFFSET - 100_000, "receipt_ns": go + OFFSET + 151_000_000,
            "bestmove": "e2e4", "status": "complete"}


class EvidenceTests(unittest.TestCase):
    def test_fixed_matrix_and_valid_exposed_histories(self):
        self.assertEqual([len(batch) for batch in probe.matrix()], [1, 1, 1, 1, 4])
        self.assertEqual(len(probe.cases()), 4)
        self.assertEqual(len({case["fen"] for case in probe.cases()}), 4)
        self.assertEqual(probe.SETTINGS.threads, 1)
        self.assertEqual(probe.SETTINGS.initial, .170)
        self.assertEqual(probe.SETTINGS.increment, .150)

    def test_raw_sample_replay(self):
        result = probe.validate_sample(sample())
        self.assertEqual(result["boundary"]["classification"], "callback_on_time")
        self.assertEqual(result["output"]["verified_legal_plies"], 4)

    def test_reject_corrupt_trace_clock_move_cleanup_and_coverage(self):
        mutations = [
            lambda s: s.update(bestmove="e2e3"),
            lambda s: s.update(go_ns=s["go_ns"] + 1),
            lambda s: s["cleanup"].update(exit_code=1),
            lambda s: s["protocol"].append(dict(s["protocol"][-4])),
            lambda s: s["protocol"][7].update(line="go wtime 171 btime 170 winc 150 binc 150"),
            lambda s: s["protocol"][8].update(line=s["protocol"][8]["line"].replace("e2e4 e7e5", "e2e5")),
            lambda s: s["protocol"][11].update(line=s["protocol"][11]["line"].replace("seq 1", "seq 2")),
            lambda s: s["protocol"][11].update(line=s["protocol"][11]["line"].replace("hard_budget_ns 150000000", "hard_budget_ns 151000000")),
            lambda s: s["calibrations"].pop(),
        ]
        for index, mutate in enumerate(mutations):
            changed = sample()
            mutate(changed)
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe.validate_sample(changed)

    def test_classification_uses_full_calibration_bounds(self):
        s = sample()
        parsed = probe.validate_sample(s)
        trace, measurement = parsed["trace"], parsed["measurement"]
        deadline = s["go_ns"] + 170_000_000
        self.assertEqual(probe.classify(trace, measurement, s["go_ns"], deadline)["classification"], "callback_on_time")
        self.assertEqual(probe.classify(trace, measurement, s["go_ns"], deadline + 50_000_000)["classification"], "output_flushed_on_time_receipt_late")
        late = dict(trace, bestmove_begin_ns=deadline - OFFSET + 1_000_000,
                    bestmove_flushed_ns=deadline - OFFSET + 2_000_000)
        self.assertEqual(probe.classify(late, measurement, s["go_ns"], deadline + 50_000_000)["classification"], "engine_write_started_after_clock")
        ambiguous = dict(late, bestmove_begin_ns=deadline - OFFSET,
                         bestmove_flushed_ns=deadline - OFFSET)
        self.assertEqual(probe.classify(ambiguous, measurement, s["go_ns"], deadline + 1_000_000)["classification"], "late_receipt_boundary_uncertain")

    def test_exact_coverage_reports_overlap_and_no_overlap_honestly(self):
        samples = [dict(sample(), load=load, case=probe.cases()[index])
                   for batch in probe.matrix() for load, index in batch]
        self.assertTrue(probe.coverage(samples)["actual_four_way_overlap"])
        samples[-1]["go_ns"] += 200_000_000
        samples[-1]["receipt_ns"] += 200_000_000
        self.assertFalse(probe.coverage(samples)["actual_four_way_overlap"])
        for changed in (samples[:-1], samples + [samples[-1]], list(reversed(samples))):
            with self.assertRaises(ValueError):
                probe.coverage(changed)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_callback_timestamps_are_unchanged(self):
        log = probe.MemoryLog()
        protocol = probe.OwnedProtocol("test", log)
        with patch.object(probe.match.time, "monotonic_ns", return_value=123):
            protocol.pipe_data_received(1, b"info nodes 10 time 150\nbestmove e2e4\n")
        self.assertIs(log.protocol, protocol)
        self.assertEqual(protocol.bestmove_ns, 123)
        self.assertEqual([e["monotonic_ns"] for e in log.events], [123, 123])

    async def test_log_bound_latches_failure_and_rejects_wait(self):
        log = probe.MemoryLog()
        with patch.object(probe, "MAX_BYTES", 1), self.assertRaises(probe.match.PersistenceError):
            log.write(json.dumps({"direction": "from_engine", "line": "bestmove e2e4"}))
        self.assertTrue(log.failure.done())
        with self.assertRaises(probe.match.PersistenceError):
            await log.wait_line("bestmove ")

    async def test_wait_rejects_duplicate_trace(self):
        log = probe.MemoryLog()
        event = {"direction": "from_engine", "line": "info string clock-boundary v1"}
        log.write(json.dumps(event)); log.write(json.dumps(event))
        with self.assertRaises(ValueError):
            await log.wait_line(probe.boundary.TRACE_PREFIX)

    async def test_requires_declared_loaded_host_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_text("preserve")
            with self.assertRaises(ValueError):
                await probe.run("unused", "unused", output, host_load="quiet")
            with self.assertRaises(ValueError):
                await probe.run("unused", "unused", output, host_load="lm-studio-running")
            self.assertEqual(output.read_text(), "preserve")

    async def test_startup_failure_retains_and_closes_owned_pid(self):
        sample_record = {}
        returned = asyncio.get_running_loop().create_future()
        returned.set_result(1)
        protocol = Mock(transport=Mock(), returncode=returned)
        protocol.transport.get_pid.return_value = 1234
        async def fail_start(spec, settings, log):
            log.protocol = protocol
            raise ValueError("expected setup failure")
        with patch.object(probe.match, "start_engine", side_effect=fail_start), \
                patch.object(probe.match, "close_engine", new=AsyncMock()) as close:
            with self.assertRaisesRegex(ValueError, "setup failure"):
                await probe.session(Path("engine"), Path("network"), probe.cases()[0], "serial",
                                    sample_record, asyncio.Event(), [], 1)
        close.assert_awaited_once_with(protocol.transport, protocol)
        self.assertEqual(sample_record["pid"], 1234)
        self.assertEqual(sample_record["cleanup"], {"exited": True, "exit_code": 1})

    async def test_repeated_cancellation_during_cleanup_keeps_receipt(self):
        sample_record = {}
        quitting, release = asyncio.Event(), asyncio.Event()
        returned = asyncio.get_running_loop().create_future()
        async def quit_process():
            quitting.set()
            await release.wait()
        def close_transport():
            if not returned.done():
                returned.set_result(0)
        transport = Mock()
        transport.get_pid.return_value = 4321
        transport.close.side_effect = close_transport
        protocol = SimpleNamespace(transport=transport, returncode=returned, quit=quit_process)
        async def fail_start(spec, settings, log):
            log.protocol = protocol
            raise ValueError("expected setup failure")
        with patch.object(probe.match, "start_engine", side_effect=fail_start):
            task = asyncio.create_task(probe.session(Path("engine"), Path("network"), probe.cases()[0],
                "serial", sample_record, asyncio.Event(), [], 1))
            await quitting.wait()
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(sample_record["pid"], 4321)
        self.assertEqual(sample_record["cleanup"], {"exited": True, "exit_code": 0})
        self.assertIn("finished_utc", sample_record)


if __name__ == "__main__":
    unittest.main()
