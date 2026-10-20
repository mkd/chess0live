#!/usr/bin/env python3
"""Engine-free tests for clock-boundary parsing, causal bounds and containment.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import probe_clock_boundaries as probe


OFFSET = 1_000_000_000
GO = "go wtime 600 btime 600 winc 600 binc 600"
CASE = {"id": "late-receipt", "position": {"line": "position startpos moves e2e4"}}


def trace():
    go = 2_003_000_000
    return {
        "seq": 1, "position_begin_ns": 2_000_000_000, "position_end_ns": 2_002_000_000,
        "go_received_ns": go, "worker_started_ns": go + 1_000_000,
        "search_started_ns": go + 2_000_000, "hard_stop_ns": go + 580_000_000,
        "leader_finished_ns": go + 581_000_000, "joined_ns": go + 581_000_000,
        "accounted_ns": go + 582_000_000, "search_returned_ns": go + 583_000_000,
        "reply_ready_ns": go + 584_000_000, "bestmove_begin_ns": go + 585_000_000,
        "bestmove_flushed_ns": go + 586_000_000, "hard_budget_ns": 580_000_000,
        "reported_time_ms": 582,
    }


def trace_line(values=None):
    values = trace() if values is None else values
    return probe.TRACE_PREFIX + "v1 " + " ".join(f"{key} {value}" for key, value in values.items())


def calibrations():
    result = []
    for identifier in range(6):
        stamp = (1_000_000_000 if identifier < 3 else 3_000_000_000) + identifier * 1_000_000
        result.append({"id": identifier, "engine_ns": stamp,
                       "send_before_ns": stamp + OFFSET - 1000,
                       "send_flushed_ns": stamp + OFFSET - 500,
                       "reader_received_ns": stamp + OFFSET + 1000})
    return result


def events():
    values = trace()
    return [{"direction": "to_engine", "line": GO,
             "monotonic_ns": values["go_received_ns"] + OFFSET - 1_000_000},
            {"direction": "from_engine", "line": "bestmove e7e5 ponder g1f3",
             "monotonic_ns": values["bestmove_flushed_ns"] + OFFSET + 500_000}]


def replies():
    return ["info depth 1 seldepth 2 score cp 0 nodes 10 time 582 nps 17 hashfull 0 tbhits 0 pv e7e5 g1f3",
            "info nodes 12 time 582 nps 20 hashfull 0 tbhits 0",
            "bestmove e7e5 ponder g1f3"]


class ParseAndMeasurementTests(unittest.TestCase):
    def test_exact_trace_schema_and_unsigned_ns(self):
        self.assertEqual(probe.parse_trace(trace_line()), trace())
        for line in (trace_line() + " seq 1", trace_line().replace(" v1 ", " v2 "),
                     trace_line().replace("seq 1", "seq 2"), trace_line().replace("seq 1", "seq 1.0"),
                     trace_line().replace("seq 1", "seq ١"),
                     trace_line().replace(" reported_time_ms 582", ""),
                     trace_line().replace("position_begin_ns 2000000000", "position_begin_ns -1")):
            with self.subTest(line=line), self.assertRaises(ValueError):
                probe.parse_trace(line)

    def test_rejects_reversed_engine_boundaries_and_outside_hardstop(self):
        for key, value in (("position_end_ns", 9_000_000_000), ("worker_started_ns", 1),
                           ("hard_stop_ns", 9_000_000_000), ("accounted_ns", 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.parse_trace(trace_line(dict(trace(), **{key: value})))
        self.assertEqual(probe.parse_trace(trace_line(dict(trace(), hard_stop_ns=0)))["hard_stop_ns"], 0)

    def test_ping_schema(self):
        self.assertEqual(probe.parse_ping("info string clock-ping v1 id 3 now_ns 123"),
                         {"id": 3, "now_ns": 123})
        for line in ("info string clock-ping v2 id 3 now_ns 123",
                     "info string clock-ping v1 id 3 now_ns -1",
                     "info string clock-ping v1 id 3 id 4 now_ns 123"):
            with self.subTest(line=line), self.assertRaises(ValueError):
                probe.parse_ping(line)

    def test_calibration_bounds_do_not_assume_shared_epoch_or_half_rtt(self):
        result = probe.clock_offset(calibrations())
        self.assertEqual(result["host_minus_engine_low_ns"], OFFSET - 1000)
        self.assertEqual(result["host_minus_engine_high_ns"], OFFSET + 1000)
        self.assertEqual(result["width_ns"], 2000)
        samples = calibrations()
        samples[0]["send_flushed_ns"] = samples[0]["reader_received_ns"] + 1000
        self.assertEqual(probe.clock_offset(samples), result)

    def test_inconsistent_or_missing_calibration_rejected(self):
        missing, duplicated = calibrations()[:-1], calibrations()
        duplicated[-1]["id"] = 4
        changed = calibrations()
        changed[-1]["engine_ns"] -= 10000
        for rows in (missing, duplicated, changed):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                probe.clock_offset(rows)

    def test_measure_separates_engine_work_transport_bounds_and_consumer_wait(self):
        consumed = events()[-1]["monotonic_ns"] + 90_000_000
        result = probe.measure(trace(), events(), calibrations(), GO, 600, consumed)
        self.assertEqual(result["engine_intervals"]["position_processing_ms"], 2)
        self.assertEqual(result["engine_intervals"]["go_to_accounted_ms"], 582)
        self.assertEqual(result["engine_intervals"]["reply_lock_wait_ms"], 1)
        self.assertEqual(result["go_receipt_after_send_ms_bounds"], [.999, 1.001])
        self.assertEqual(result["reader_after_bestmove_flush_ms_bounds"], [.499, .501])
        self.assertEqual(result["hard_stop_after_deadline_ms"], 0)
        self.assertEqual(result["accounted_after_deadline_ms"], 2)
        self.assertEqual(result["consumer_after_reader_ms"], 90)
        self.assertTrue(result["reader_within_transmitted_clock"])
        self.assertGreater(result["consumer_elapsed_ms"], 600)

    def test_before_flush_receipt_retains_negative_uncertainty(self):
        recorded = events()
        recorded[-1]["monotonic_ns"] = trace()["bestmove_flushed_ns"] + OFFSET - 500
        result = probe.measure(trace(), recorded, calibrations(), GO, 600,
                               recorded[-1]["monotonic_ns"])
        self.assertEqual(result["reader_after_bestmove_flush_ms_bounds"], [-.0015, .0005])

    def test_measure_rejects_wrong_budget_accounting_or_duplicate_receipt(self):
        for changed in (dict(trace(), hard_budget_ns=581_000_000),
                        dict(trace(), hard_budget_ns=-1), dict(trace(), reported_time_ms=581)):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                probe.measure(changed, events(), calibrations(), GO, 600, 4_000_000_000)
        with self.assertRaises(ValueError):
            probe.measure(trace(), events() + [events()[-1]], calibrations(), GO, 600, 4_000_000_000)

    def test_cross_clock_causality_is_required_but_flush_order_is_not(self):
        for index, value in ((0, trace()["go_received_ns"] + OFFSET + 100_000),
                             (1, trace()["bestmove_begin_ns"] + OFFSET - 100_000)):
            recorded = events()
            recorded[index]["monotonic_ns"] = value
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe.measure(trace(), recorded, calibrations(), GO, 600, 4_000_000_000)

    def test_legal_full_pv_bestmove_ponder_and_trace_accounting(self):
        result = probe.validate_output(replies(), CASE, trace())
        self.assertEqual(result["verified_legal_plies"], 4)
        for old, new in (("pv e7e5 g1f3", "pv e7e5 g1g4"),
                         ("ponder g1f3", "ponder g1g4"), ("time 582", "time 583"),
                         ("tbhits 0", "tbhits 1"), ("hashfull 0", "hashfull 1001")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                probe.validate_output([line.replace(old, new) for line in replies()], CASE, trace())

    def test_uncompleted_iteration_still_requires_legal_fallback(self):
        rows = replies()[1:]
        self.assertEqual(probe.validate_output(rows, CASE, trace())["verified_legal_plies"], 2)
        with self.assertRaises(ValueError):
            probe.validate_output(rows + [rows[-1]], CASE, trace())


class ConfigurationTests(unittest.TestCase):
    def test_matrix_has_every_cell_once_and_only_four_homogeneous_concurrent_groups(self):
        batches = probe.matrix([{"id": "late-receipt"}, {"id": "internal-overrun"}])
        self.assertEqual(len(batches), 20)
        self.assertEqual([len(batch) for batch in batches], [1] * 16 + [4] * 4)
        cells = [cell for batch in batches for cell in batch]
        keys = [tuple(cell[key] for key in ("case_id", "clock_ms", "lmr", "position_barrier", "load"))
                for cell in cells]
        self.assertEqual(len(set(keys)), 32)
        for batch in batches[16:]:
            self.assertEqual({cell["clock_ms"] for cell in batch}, {batch[0]["clock_ms"]})
            self.assertEqual({cell["position_barrier"] for cell in batch}, {batch[0]["position_barrier"]})
            self.assertEqual({(cell["case_id"], cell["lmr"]) for cell in batch},
                             {("late-receipt", False), ("late-receipt", True),
                              ("internal-overrun", False), ("internal-overrun", True)})

    def test_options_only_change_lmr_and_disable_unrelated_work(self):
        off, on = [probe.options_for(Path("/network"), enabled) for enabled in (False, True)]
        self.assertEqual(off.pop("Late Move Reductions"), "false")
        self.assertEqual(on.pop("Late Move Reductions"), "true")
        self.assertEqual(off, on)
        self.assertEqual(off["Search Diagnostics"], "false")
        self.assertEqual(off["Threads"], "1")
        self.assertEqual(off["SyzygyPath"], "")
        self.assertEqual(off["SyzygyProbeLimit"], "0")

    def test_resource_check_counts_all_four_resident_engines(self):
        policy = {"max_cpu_workers": 4, "memory_fraction": .5}
        with tempfile.TemporaryDirectory() as directory:
            network = Path(directory) / "network"
            network.write_bytes(b"x")
            with patch.object(probe, "current_budget", return_value=policy), \
                    patch.object(probe, "physical_memory", return_value=8 * 1024**3):
                result = probe.resource_check(network, 4)
                self.assertEqual(result["resident_engines"], 4)
                self.assertEqual(result["estimated_memory_bytes"], 3 * 1024**3)
            for cpus, memory in ((3, 8 * 1024**3), (4, 1024), (4, None)):
                with patch.object(probe, "current_budget",
                                  return_value=dict(policy, max_cpu_workers=cpus)), \
                        patch.object(probe, "physical_memory", return_value=memory), \
                        self.assertRaises(ValueError):
                    probe.resource_check(network, 4)

    def test_deadline_is_finite_and_shared(self):
        with patch.object(probe.time, "monotonic", return_value=10):
            self.assertEqual(probe.remaining(12, 30), 2)
            with self.assertRaises(TimeoutError):
                probe.remaining(10, 30)

    def test_existing_output_and_missing_quiet_declaration_do_not_start_engines(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.jsonl"
            output.write_text("preserve\n")
            with patch.object(probe, "BoundaryEngine") as engine:
                with self.assertRaises(ValueError):
                    probe.run("missing", "missing", "missing", output, quiet_host=True)
                engine.assert_not_called()
            self.assertEqual(output.read_text(), "preserve\n")
            with self.assertRaisesRegex(ValueError, "quiet-host"):
                probe.run("missing", "missing", "missing", output.with_name("new.jsonl"))

    def test_selected_histories_validate_exact_source_hashes_and_moves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "source"
            source.write_bytes(b"original")
            document = {"schema": "chess0live-clock-boundary-selected-cases-v1",
                        "cases": [dict(copy.deepcopy(CASE), history_plies=1,
                                       fen=probe.board_for("startpos moves e2e4").fen()),
                                  {"id": "internal-overrun", "position": {"line": "position startpos moves d2d4"},
                                   "history_plies": 1, "fen": probe.board_for("startpos moves d2d4").fen()}],
                        "source_hashes": {"source": probe.digest(source)}}
            positions = root / "positions.json"
            positions.write_text(json.dumps(document))
            with patch.object(probe, "ROOT", root):
                self.assertEqual(len(probe.load_cases(positions)[1]), 2)
                source.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "changed"):
                    probe.load_cases(positions)
                source.write_bytes(b"original")
                document["cases"][0]["position"]["line"] += "\ngo infinite"
                positions.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    probe.load_cases(positions)

    def test_startup_failure_preserves_result_and_breaks_peer_barrier(self):
        barrier = Mock()
        with patch.object(probe, "BoundaryEngine", side_effect=RuntimeError("startup failed")):
            result = probe.session(Path("none"), Path("none"), CASE,
                                   probe.matrix([{"id": "a"}, {"id": "b"}])[0][0],
                                   probe.time.monotonic() + 10, barrier)
        self.assertEqual(result["status"], "error")
        self.assertIn("startup failed", result["error"])
        barrier.abort.assert_called_once()

    def test_run_failure_and_hash_drift_are_retained_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ("engine", "network", "positions"):
                (root / filename).write_text(filename)
            output = root / "result.jsonl"
            document = {"source_hashes": {}}
            cases = [{"id": "late-receipt"}, {"id": "internal-overrun"}]
            def fail(*args, **kwargs):
                (root / "engine").write_text("drift")
                return {"type": "result", "status": "error", "error": "synthetic"}
            with patch.object(probe, "load_cases", return_value=(document, cases)), \
                    patch.object(probe, "SOURCES", ()), \
                    patch.object(probe, "NETWORK_SHA256", probe.digest(root / "network")), \
                    patch.object(probe, "resource_check", return_value={}), \
                    patch.object(probe, "session", side_effect=fail) as session, \
                    self.assertRaisesRegex(RuntimeError, "without retry"):
                probe.run(root / "engine", root / "network", root / "positions", output, quiet_host=True)
            session.assert_called_once()
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["type"] for row in rows], ["metadata", "admission", "result", "summary"])
            self.assertEqual(rows[-1]["status"], "error")
            self.assertEqual(rows[-1]["artifact_drift"], ["engine"])
            self.assertEqual(rows[-1]["completed_searches"], 0)


class SessionLifecycleTests(unittest.TestCase):
    def fake(self):
        """In-memory protocol stand-in; no subprocess or actual search."""
        engine = Mock()
        engine.process.pid = 123
        engine.events = [
            {"direction": "from_engine", "line": replies()[-1], "monotonic_ns": 1},
            {"direction": "from_engine", "line": trace_line(), "monotonic_ns": 2},
            {"direction": "from_engine", "line": "info string clock-ping v1 id 5 now_ns 3005000000",
             "monotonic_ns": 3},
            {"direction": "eof", "monotonic_ns": 4}]
        engine.cleanup = {"forced_kill": False, "exit_code": 0, "reader_alive": False,
                          "reader_error": None}
        identity = [f"option name {key} type string default x"
                    for key in probe.options_for(Path("network"), False)] + ["uciok"]
        engine.until.side_effect = [identity, ["readyok"], replies(), [trace_line()]]
        return engine

    def run_fake(self, engine):
        cell = {"case_id": CASE["id"], "case_index": 0, "clock_ms": 600, "lmr": False,
                "position_barrier": False, "load": "serial"}
        with patch.object(probe, "BoundaryEngine", return_value=engine), \
                patch.object(probe, "ping", side_effect=calibrations()), \
                patch.object(probe, "measure", return_value={"synthetic": True}):
            return probe.session(Path("engine"), Path("network"), CASE, cell,
                                 probe.time.monotonic() + 60)

    def test_success_requires_post_bestmove_trace_and_clean_exit(self):
        engine = self.fake()
        result = self.run_fake(engine)
        self.assertEqual(result["status"], "complete")
        engine.close.assert_called_once()
        self.assertEqual(engine.until.call_args_list[-1].args[0], probe.TRACE_PREFIX)
        self.assertEqual(result["validated"]["verified_legal_plies"], 4)

    def test_shutdown_failure_never_reports_success(self):
        for change in ({"forced_kill": True}, {"exit_code": 1}, {"reader_alive": True},
                       {"reader_error": "broken pipe"}):
            with self.subTest(change=change):
                engine = self.fake()
                engine.cleanup.update(change)
                result = self.run_fake(engine)
                self.assertEqual(result["status"], "error")
                self.assertIn("shutdown", result["cleanup_error"])
                engine.close.assert_called_once()

    def test_late_duplicate_and_other_shutdown_output_cannot_disappear(self):
        for extra in ("bestmove e7e5", "unexpected trailing line", "info string error: late"):
            with self.subTest(extra=extra):
                engine = self.fake()
                engine.events.insert(-1, {"direction": "from_engine", "line": extra,
                                          "monotonic_ns": 4})
                result = self.run_fake(engine)
                self.assertEqual(result["status"], "error")
                self.assertIn("cleanup_error", result)

    def test_missing_or_extra_post_bestmove_trace_still_closes(self):
        engine = self.fake()
        engine.until.side_effect = [engine.until.side_effect.__next__(), ["readyok"],
                                    replies(), ["extra", trace_line()]]
        result = self.run_fake(engine)
        self.assertEqual(result["status"], "error")
        self.assertIn("between bestmove", result["error"])
        engine.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
