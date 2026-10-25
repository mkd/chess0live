#!/usr/bin/env python3
"""Synthetic integrity checks; no engine process or performance measurement.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import queue
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_tt_move_hints as p


def reply(role="off", unit=None):
    unit = unit or (18 if role == "on" else 20)
    score = 12 if role == "on" else 10
    rows = [f"info depth {d} seldepth {d + 1} score cp {score} nodes {d * unit} time {d} nps 1000 hashfull 2 tbhits 0 pv g1h3 g8h6"
            for d in range(1, p.DEPTH + 1)]
    rows += [f"info nodes {p.DEPTH * unit} time {p.DEPTH} nps 1000 hashfull 2 tbhits 0"]
    if role == "on":
        rows += ["info string move-hints v1 enabled true slots 524288 allocated_bytes 8388608 probes 12 hits 5 legal_matches 4 stores 9"]
    rows += ["info string cache v1 entry_bytes 16 bucket_bytes 64 buckets 524288 capacity 2097152 allocated_bytes 33554432 probes 100 hits 20 cutoffs 10 stores 70 replacements 5",
             "info string ordering v1 policy mvv-lva see_calls 0 losing_captures 0",
             "info string lmr v1 enabled true reductions 4 researches 2 fail_lows 1 verified_cutoffs 1"]
    rows += [f"info string search-iteration v1 depth {d} completed true nodes {unit} duration_ms 1 elapsed_ms {d}"
             for d in range(1, p.DEPTH + 1)]
    rows += [f"info string search-summary v1 policy classic forecast_active false stop_reason depth_limit nodes {p.DEPTH * unit} completed_depth {p.DEPTH} elapsed_ms {p.DEPTH} soft_ms 0 hard_ms 0 target_ms 0 predicted_next_ms 0",
             "bestmove g1h3 ponder g8h6"]
    return rows


def identity(candidate):
    rows = ["id name synthetic chess0live", "id author synthetic test"]
    for name, value in dict(p.BASE_OPTIONS, EvalFile="network").items():
        if name in ("Threads", "Hash", "Move Overhead", "SyzygyProbeLimit", "SyzygyProbeDepth"):
            default = "7" if name == "SyzygyProbeLimit" else value
            kind = f"spin default {default} min 0 max 16384"
        elif name in ("Time Policy", "Capture Ordering"):
            choices = "classic var forecast" if name == "Time Policy" else "mvv-lva var see"
            kind = f"combo default {value} var {choices}"
        elif name in ("EvalFile", "SyzygyPath"):
            kind = "string default " + value
        else:
            kind = "check default " + ("false" if name == "Search Diagnostics" else value)
        rows.append("option name " + name + " type " + kind)
    if candidate:
        rows.append("option name TT Move Hints type check default false")
    return rows + ["uciok"]


class SyntheticQueue(queue.Queue):
    fail_when_empty = False

    def get(self, block=True, timeout=None):
        if block and self.fail_when_empty and self.empty():
            raise TimeoutError("synthetic partial search timeout")
        return super().get(block, timeout)


class FakeEngine:
    instances = []
    bad_exit = stray_ready = late_output = partial_timeout = mutate_candidate = bad_parity = False

    def __init__(self, path, cwd=None):
        self.path, self.lines, self.transcript, self.commands = path, SyntheticQueue(), [], []
        self.options, self.closed, self.after_search = {}, False, False
        self.process = SimpleNamespace(pid=1000 + len(self.instances), returncode=None)
        self.process.poll = lambda: self.process.returncode
        self.process.kill = lambda: setattr(self.process, "returncode", -9)
        self.process.wait = self.wait
        self.reader = SimpleNamespace(is_alive=lambda: not self.closed)
        self.instances.append(self)

    def wait(self, timeout=None):
        if self.process.returncode is None:
            self.process.returncode = 7 if self.bad_exit else 0
        return self.process.returncode

    def send(self, command):
        self.commands.append(command)
        rows = []
        if command == "uci":
            rows = identity(self.path.name == "candidate")
        elif command.startswith("setoption name "):
            name, value = command.removeprefix("setoption name ").split(" value ", 1)
            self.options[name] = value
            if name == "SyzygyPath":
                rows = ["info string Syzygy largest 0 pieces; table files are external"]
        elif command == "isready":
            rows = (["bestmove g1h3"] if self.stray_ready and self.after_search else []) + ["readyok"]
            self.after_search = False
        elif command.startswith("go depth "):
            role = "parent" if self.path.name == "parent" else ("on" if self.options.get("TT Move Hints") == "true" else "off")
            rows = reply(role, 21 if self.bad_parity and role == "off" else None)
            if self.partial_timeout and role == "off":
                rows = rows[:1]
                self.lines.fail_when_empty = True
            if self.mutate_candidate and role == "off":
                self.path.write_bytes(b"changed synthetic executable")
            self.after_search = True
        for row in rows:
            self.lines.put(row)

    def close(self):
        self.closed = True
        if self.late_output:
            self.lines.put("info string unexpected shutdown output")
        self.lines.put(None)


class FakeMonitor:
    fail = False

    def __init__(self, network, events):
        self.start_mono = time.monotonic()
        self.deadline = self.start_mono + 300
        self.max_gap = self.max_discrepancy = 0

    def check(self, force=False):
        if self.fail:
            raise TimeoutError("synthetic total deadline")


class MoveHintProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.parent, self.candidate, self.network = [self.root / name for name in ("parent", "candidate", "network")]
        for path in (self.parent, self.candidate, self.network):
            path.write_bytes(path.name.encode())
        self.positions = [dict(id="synthetic-opening", position="startpos")]
        self.board = p.board_for("startpos")
        FakeEngine.instances = []
        for name in ("bad_exit", "stray_ready", "late_output", "partial_timeout", "mutate_candidate", "bad_parity"):
            setattr(FakeEngine, name, False)
        FakeMonitor.fail = False

    def profile(self, **kwargs):
        with ExitStack() as stack:
            replacements = dict(Engine=FakeEngine, Monitor=FakeMonitor, source_paths=lambda: {},
                                load_positions=lambda: ({"sources": {}}, self.positions),
                                CORPUS=self.network, PROTOCOL=self.network,
                                PARENT_SHA256=p.digest(self.parent), CORPUS_SHA256=p.digest(self.network),
                                PROTOCOL_SHA256=p.digest(self.network),
                                PINNED_NETWORK=p.digest(self.network),
                                resource_check=lambda *args: dict(active_search_workers=1, resident_engines=1))
            for name, value in replacements.items():
                stack.enter_context(patch.object(p, name, value))
            return p.profile(self.parent, self.candidate, self.root / "output", network=self.network,
                             candidate_sha256=kwargs.pop("candidate_sha256", p.digest(self.candidate)), **kwargs)

    def saved(self):
        return json.loads((self.root / "output/report.json").read_text())

    def test_fixed_existing_corpus_and_pins(self):
        document, positions = p.load_positions()
        self.assertEqual(len(positions), 15)
        self.assertEqual(p.digest(p.CORPUS), p.CORPUS_SHA256)
        self.assertIn("sources", document)
        self.assertEqual((p.DEPTH, p.REPETITIONS, p.HASH_MB), (6, 2, 64))

    def test_immutable_explicit_options_and_role_order(self):
        original = dict(p.BASE_OPTIONS)
        for role in p.ROLES:
            options = p.options_for(role, self.network)
            self.assertEqual(options["Search Diagnostics"], "true")
            self.assertEqual(options["Late Move Reductions"], "true")
            self.assertEqual(options["Threads"], "1")
            self.assertEqual(options["Hash"], "64")
            self.assertEqual(options["SyzygyProbeLimit"], "0")
            self.assertEqual(options.get("TT Move Hints"), {"parent": None, "off": "false", "on": "true"}[role])
            options["Threads"] = "999"
        self.assertEqual(p.BASE_OPTIONS, original)
        self.assertEqual(p.run_order(0, 0), ("parent", "off", "on"))
        for index in range(15):
            self.assertEqual(p.run_order(index, 1), p.run_order(index, 0)[::-1])
        with self.assertRaises(ValueError):
            p.options_for("invalid", self.network)

    def test_default_identity_compatibility(self):
        for role in p.ROLES:
            p.validate_identity(identity(role != "parent"), role, p.options_for(role, self.network))
        for bad in (identity(False), [row.replace("Hints type check default false", "Hints type check default true") for row in identity(True)],
                    identity(True)[:-1] + ["uciok broken"]):
            with self.assertRaises(ValueError):
                p.validate_identity(bad, "on", p.options_for("on", self.network))

    def test_all_legal_results_and_work_signature(self):
        parent, off, on = [p.validate_result(reply(role), self.board, role) for role in p.ROLES]
        self.assertEqual(parent["signature"], off["signature"])
        self.assertNotEqual(off["signature"], on["signature"])
        self.assertEqual(on["diagnostics"]["move-hints"]["legal_matches"], 4)
        changed = [row.replace(" time 6 ", " time 9 ").replace(" nps 1000 ", " nps 900 ") for row in reply()]
        self.assertEqual(p.validate_result(changed, self.board, "off")["signature"], off["signature"])

    def test_illegal_best_ponder_pv_and_null_rejected(self):
        for old, new in (("pv g1h3 g8h6", "pv g1h3 e2e4"), ("bestmove g1h3", "bestmove e2e5"),
                         ("ponder g8h6", "ponder e2e4"), ("pv g1h3 g8h6", "pv 0000")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                p.validate_result([row.replace(old, new) for row in reply()], self.board, "off")

    def test_hint_record_presence_and_exact_schema(self):
        line = reply("on")[7]
        for bad in (line + " hits 1", line.replace("v1", "v2"), line.replace("enabled true", "enabled false"),
                    line.replace("hits 5", "hits -1"), line.replace("stores 9", "stores nan")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.hint_record(bad)
        with self.assertRaises(ValueError):
            p.validate_result(reply("on"), self.board, "off")
        with self.assertRaises(ValueError):
            p.validate_result(reply(), self.board, "on")

    def test_hint_geometry_and_counter_relationships(self):
        for old, new in (("slots 524288", "slots 0"), ("allocated_bytes 8388608", "allocated_bytes 8388609"),
                         ("hits 5", "hits 13"), ("legal_matches 4", "legal_matches 6")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                p.validate_result([row.replace(old, new) for row in reply("on")], self.board, "on")

    def test_legacy_policy_geometry_bounds_and_accounting(self):
        for old, new in (("entry_bytes 16", "entry_bytes 15"), ("reductions 4", "reductions 1"),
                         ("see_calls 0", "see_calls 1"), ("stop_reason depth_limit", "stop_reason hard_time"),
                         ("soft_ms 0", "soft_ms 1"), ("completed true nodes 20", "completed true nodes 21"),
                         ("completed true", "completed false"), ("score cp 10", "score cp 10 lowerbound"),
                         ("tbhits 0", "tbhits 1"), ("hashfull 2", "hashfull 1001")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                p.validate_result([row.replace(old, new) for row in reply()], self.board, "off")

    def test_unknown_duplicate_reordered_or_trailing_output(self):
        rows = reply()
        variants = [rows[:-1] + ["info string unknown v1 x 0", rows[-1]], rows + ["readyok"],
                    rows[:-1] + [rows[7], rows[-1]], rows[:-2] + [rows[-1], rows[-2]],
                    rows[:1] + rows[2:], ["info string error: synthetic"] + rows]
        for bad in variants:
            with self.subTest(bad=bad[-2:]), self.assertRaises(ValueError):
                p.validate_result(bad, self.board, "off")

    def test_complete_synthetic_matrix_sessions_raw_and_barriers(self):
        report = self.profile()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["samples"]), 12)
        self.assertEqual(len(report["sessions"]), 6)
        self.assertEqual(report["summary"]["exact_parent_off_pairs"], 4)
        self.assertFalse(report["timing_qualified"])
        for session, engine in zip(report["sessions"], FakeEngine.instances):
            self.assertEqual(session["exit_code"], 0)
            self.assertEqual(session["shutdown_eof_count"], 1)
            self.assertEqual(engine.commands.count("ucinewgame"), 1)
            self.assertEqual(engine.commands.count("go depth 6"), 2)
            self.assertEqual(engine.commands.count("isready"), 5)
            self.assertEqual(engine.commands[-1], "quit")
            raw = self.root / "output" / session["raw_log"]
            self.assertEqual(session["raw_sha256"], p.digest(raw))
            events = [json.loads(line) for line in raw.read_text().splitlines()]
            self.assertIsNone(events[-1]["line"])
            self.assertEqual([event["line"] for event in events if event["direction"] == ">"], engine.commands)
        self.assertEqual(set(report["assets_after"]), set(report["assets"]))

    def test_summary_rejects_missing_duplicate_and_nondeterministic_work(self):
        report = self.profile()
        for samples in (report["samples"][:-1], report["samples"] + report["samples"][:1]):
            with self.assertRaises(ValueError):
                p.summarize(samples, self.positions)
        changed = copy.deepcopy(report["samples"])
        next(sample for sample in changed if sample["repetition"] == 1 and sample["role"] == "on")["result"]["signature"]["bestmove"] = "g1f3"
        with self.assertRaisesRegex(ValueError, "nondeterministic"):
            p.summarize(changed, self.positions)

    def test_no_hint_activation_is_failure(self):
        report = self.profile()
        for sample in report["samples"]:
            if sample["role"] == "on":
                sample["result"]["diagnostics"]["move-hints"].update(probes=0, hits=0, legal_matches=0, stores=0)
        with self.assertRaisesRegex(ValueError, "active move-hint"):
            p.summarize(report["samples"], self.positions)

    def test_output_overwrite_and_pin_mismatch_before_launch(self):
        with self.assertRaisesRegex(ValueError, "frozen pin"):
            self.profile(candidate_sha256="0" * 64)
        self.assertEqual(FakeEngine.instances, [])
        (self.root / "output").mkdir()
        with self.assertRaisesRegex(ValueError, "Output exists"):
            self.profile()
        self.assertEqual(FakeEngine.instances, [])

    def test_partial_timeout_retains_raw_and_partial_output(self):
        FakeEngine.partial_timeout = True
        with self.assertRaises(TimeoutError):
            self.profile()
        report = self.saved()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(report["samples"][-1]["output"]), 1)
        self.assertEqual(report["samples"][-1]["status"], "failed")
        self.assertIn("raw_sha256", report["sessions"][-1])

    def test_post_search_fence_rejects_stray_output(self):
        FakeEngine.stray_ready = True
        with self.assertRaisesRegex(ValueError, "after bestmove"):
            self.profile()
        self.assertEqual(self.saved()["status"], "failed")

    def test_unclean_exit_retained(self):
        FakeEngine.bad_exit = True
        with self.assertRaisesRegex(ValueError, "Unclean"):
            self.profile()
        self.assertEqual(self.saved()["sessions"][0]["exit_code"], 7)

    def test_late_shutdown_output_retained(self):
        FakeEngine.late_output = True
        with self.assertRaisesRegex(ValueError, "Unclean"):
            self.profile()
        self.assertIn("unexpected", self.saved()["sessions"][0]["shutdown_output"][0])

    def test_asset_drift_is_failure(self):
        FakeEngine.mutate_candidate = True
        with self.assertRaisesRegex(ValueError, "changed during"):
            self.profile()
        self.assertEqual(self.saved()["status"], "failed")
        self.assertNotEqual(self.saved()["assets"]["candidate"]["sha256"], self.saved()["assets_after"]["candidate"])

    def test_exact_parent_off_failure_is_retained(self):
        FakeEngine.bad_parity = True
        with self.assertRaisesRegex(ValueError, "exact parity failed"):
            self.profile()
        self.assertEqual(len(self.saved()["samples"]), 12)
        self.assertEqual(self.saved()["status"], "failed")

    def test_total_deadline_failure_preserves_report(self):
        FakeMonitor.fail = True
        with self.assertRaises(TimeoutError):
            self.profile()
        self.assertEqual(self.saved()["status"], "failed")
        self.assertEqual(FakeEngine.instances, [])

    def test_cli_forwards_pin_without_timing_or_corpus_controls(self):
        with patch.object(p, "profile", return_value={"summary": {}}) as call, redirect_stdout(io.StringIO()):
            self.assertEqual(p.main(["--parent", str(self.parent), "--candidate", str(self.candidate),
                                     "--candidate-sha256", "a" * 64, "--output", str(self.root / "output")]), 0)
        self.assertEqual(call.call_args.kwargs["candidate_sha256"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
