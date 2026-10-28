#!/usr/bin/env python3
"""Synthetic lifecycle and evidence checks for the continuation-history tactical audit.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Every child below is an in-memory fake. No engine search or benchmark runs here.
"""
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_phase4f9_puzzles as p


def reply(score="cp 10", pv="g1h3 g8h6", best="g1h3", ponder="g8h6"):
    return [f"info depth 1 seldepth 2 score {score} nodes 20 time 10 nps 2000 hashfull 0 tbhits 0 pv {pv}",
            "info nodes 25 time 12 nps 2083 hashfull 0 tbhits 0",
            "bestmove " + best + (" ponder " + ponder if ponder else "")]


def declarations():
    lines = ["id name chess0live 0.1-dev", "id author Claudio M. Camacho", "option name Clear Hash type button"]
    for name, kind in p.OPTION_TYPES.items():
        default = p.ADVERTISED_DEFAULTS.get(name, "nn-1a298aa575a0.nnue")
        tail = (f" default {default} min 0 max 16384" if kind == "spin" else
                " default classic var classic var forecast var bounded" if name == "Time Policy" else
                " default mvv-lva var mvv-lva var see" if name == "Capture Ordering" else f" default {default}")
        lines.append("option name " + name + " type " + kind + tail)
    return lines + ["uciok"]


class SyntheticQueue(queue.Queue):
    """An injected stalled response fails immediately instead of burning time."""
    stall = False

    def get(self, block=True, timeout=None):
        if block and self.stall and self.empty():
            raise TimeoutError("synthetic search stall")
        return super().get(block, timeout)


class FakeEngine:
    instances = []
    fault = None
    mutate = None

    def __init__(self, path, cwd=None):
        self.path, self.lines = path, SyntheticQueue()
        self.transcript, self.commands, self.options = [], [], {}
        self.closed = self.killed = self.after_search = False
        self.process = SimpleNamespace(pid=5000 + len(self.instances), returncode=None)
        self.process.poll = lambda: self.process.returncode
        self.process.wait = self.wait
        self.process.kill = self.kill
        self.reader = SimpleNamespace(is_alive=lambda: not self.closed or self.fault == "reader-alive")
        self.instances.append(self)

    def wait(self, timeout=None):
        if self.fault == "quit-timeout" and not self.killed:
            raise subprocess.TimeoutExpired("synthetic-engine", timeout)
        if self.process.returncode is None:
            self.process.returncode = 7 if self.fault == "bad-exit" else 0
        return self.process.returncode

    def kill(self):
        self.killed = True
        self.process.returncode = -9
        if not any(item is None for item in list(self.lines.queue)):
            self.lines.put(None)

    def send(self, command):
        self.commands.append(command)
        rows = []
        if command == "uci":
            rows = declarations()
        elif command.startswith("setoption name "):
            name, value = command.removeprefix("setoption name ").split(" value ", 1)
            self.options[name] = value
            if name == "SyzygyPath":
                rows = ["info string Syzygy largest 0 pieces; table files are external"]
                if self.fault == "bad-setup":
                    rows = ["info string Syzygy largest 1 pieces; table files are external"]
                elif self.fault == "extra-setup":
                    rows.append("info string arbitrary unexpected setup text")
        elif command == "isready":
            rows = ["readyok"]
            if self.after_search and self.fault == "post-bestmove":
                rows.insert(0, "bestmove g1h3")
            self.after_search = False
        elif command.startswith("go "):
            score = "cp 20" if self.options.get("Continuation History") == "true" else "cp 10"
            rows = reply(score=score, best="e2e5" if self.fault == "illegal-best" else "g1h3")
            if self.fault == "partial-timeout":
                rows = rows[:1]
                self.lines.stall = True
            elif self.fault == "early-eof":
                rows = rows[:1] + [None]
                self.process.returncode = 1
            elif self.fault == "interrupt":
                raise KeyboardInterrupt("synthetic interruption")
            if self.mutate is not None:
                self.mutate.write_bytes(b"changed during synthetic search")
            self.after_search = True
        elif command == "quit":
            if self.fault != "quit-timeout":
                self.process.returncode = 7 if self.fault == "bad-exit" else 0
            if self.fault == "late-output":
                rows.append("info string unexpected shutdown output")
            if self.fault != "missing-eof":
                rows.append(None)
            if self.fault == "duplicate-eof":
                rows.append(None)
        for row in rows:
            self.lines.put(row)

    def close(self):
        self.closed = True


class PuzzleAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.engine, self.network, self.corpus = [self.root / name for name in ("engine", "network", "corpus")]
        for path in (self.engine, self.network, self.corpus):
            path.write_bytes(b"synthetic asset")
        self.positions = [dict(id=f"puzzle-{i:02d}", fen=p.chess.STARTING_FEN,
                               supplied_mate=7, spreadsheet_row=i) for i in (1, 2)]
        self.pins = self.root / "pins.json"
        self.assets = dict(engine=self.engine, network=self.network, corpus=self.corpus)
        self.pins.write_text(json.dumps(dict(schema_version=1, engine_source_revision=p.SOURCE_REVISION,
                                            assets={name: p.digest(path) for name, path in self.assets.items()})))
        self.assets["pins"] = self.pins
        FakeEngine.instances, FakeEngine.fault, FakeEngine.mutate = [], None, None

    def run_audit(self, mode="smoke", **kwargs):
        with ExitStack() as stack:
            replacements = dict(ENGINE=self.engine, NETWORK=self.network, PINS=self.pins,
                                ENGINE_SHA256=p.digest(self.engine), NETWORK_SHA256=p.digest(self.network),
                                Engine=FakeEngine, load_positions=lambda: self.positions,
                                asset_paths=lambda: self.assets,
                                resource_check=lambda _: dict(active_search_workers=8, resident_engines=1))
            for name, value in replacements.items():
                stack.enter_context(patch.object(p, name, value))
            stack.enter_context(redirect_stdout(io.StringIO()))
            return p.audit(mode, self.root / "output", **kwargs)

    def saved(self):
        return json.loads((self.root / "output/report.json").read_text())

    def test_original_39_positions_and_annotations_remain_exact(self):
        before = p.digest(p.OWNER_SOURCE)
        positions = p.load_positions()
        self.assertEqual(len(positions), 39)
        self.assertEqual([positions[0]["supplied_mate"], positions[-1]["supplied_mate"]], [7, 18])
        self.assertEqual(before, p.digest(p.OWNER_SOURCE))

    def test_changed_corpus_provenance_or_positions_rejected(self):
        document = json.loads(p.CORPUS.read_text())
        path = self.root / "changed.json"
        for field, value in (("owner_source_sha256", "0" * 64), ("positions", [])):
            with self.subTest(field=field):
                path.write_text(json.dumps(dict(document, **{field: value})))
                with patch.object(p, "CORPUS", path), self.assertRaises(ValueError):
                    p.load_positions()

    def test_only_continuation_option_differs_and_all_resources_are_explicit(self):
        self.assertEqual(set(p.OPTIONS), {"continuation-off", "continuation-on"})
        off, on = p.OPTIONS["continuation-off"], p.OPTIONS["continuation-on"]
        self.assertEqual(set(off), set(on))
        self.assertEqual({key for key in off if off[key] != on[key]}, {"Continuation History"})
        self.assertEqual((off["Continuation History"], on["Continuation History"]), ("false", "true"))
        for options in (off, on):
            for name, value in {"Threads": "8", "Hash": "64", "Search Diagnostics": "false", "Ponder": "false",
                                "Time Policy": "classic", "Late Move Reductions": "true", "Move Overhead": "20",
                                "SyzygyPath": "<empty>", "SyzygyProbeLimit": "0", "SyzygyProbeDepth": "1",
                                "TT Move Hints": "false", "Deep Quiet Reductions": "false",
                                "Capture Ordering": "mvv-lva", "Countermove Ordering": "false",
                                "Null Move Pruning": "false", "Reverse Futility Pruning": "false",
                                "QSearch SEE Pruning": "false", "ProbCut": "false"}.items():
                self.assertEqual(options[name], value)
        self.assertEqual(p.role_order(0), ("continuation-off", "continuation-on"))
        self.assertEqual(p.role_order(1), ("continuation-on", "continuation-off"))

    def test_declared_modes_and_frozen_engine_identity(self):
        self.assertEqual({name: value["movetime_ms"] for name, value in p.MODES.items()},
                         {"check": 0, "smoke": 1000, "full": 60000})
        self.assertEqual(p.ENGINE_SHA256, "c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08")

    def test_identity_requires_all_21_options_and_unique_terminator(self):
        options = dict(p.OPTIONS["continuation-on"], EvalFile=str(self.network))
        self.assertEqual(sum(line.startswith("option name ") for line in declarations()), 21)
        p.validate_identity(declarations(), options)
        for bad in (declarations()[:-1], declarations() + ["uciok"],
                    [line for line in declarations() if not line.startswith("option name TT Move Hints ")],
                    [line.replace("TT Move Hints type check default false", "TT Move Hints type check default true") for line in declarations()],
                    [line for line in declarations() if not line.startswith("option name Continuation History ")],
                    [line.replace("Continuation History type check default false", "Continuation History type check default true") for line in declarations()],
                    declarations()[:-1] + ["option name Continuation History type check default false", "uciok"],
                    declarations()[:-1] + ["option name TT Move Hints type check default false", "uciok"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                p.validate_identity(bad, options)

    def test_identity_rejects_other_changed_defaults_types_and_ranges(self):
        options = dict(p.OPTIONS["continuation-off"], EvalFile=str(self.network))
        for old, new in (("Late Move Reductions type check default true", "Late Move Reductions type check default false"),
                         ("TT Move Hints type check", "TT Move Hints type string"),
                         ("Continuation History type check", "Continuation History type string"),
                         ("max 16384", "max 2"), (" var mvv-lva", " var wrong")):
            with self.subTest(old=old), self.assertRaises(ValueError):
                p.validate_identity([line.replace(old, new) for line in declarations()], options)

    def test_unknown_missing_extra_and_inverted_roles_refused_before_launch(self):
        with self.assertRaises(ValueError):
            p.options_for_role("hints-on", self.network)
        for change in ("missing", "extra", "inverted"):
            recipes = {role: dict(values) for role, values in p.OPTIONS.items()}
            if change == "missing":
                recipes.pop("continuation-on")
            elif change == "extra":
                recipes["unknown"] = dict(recipes["continuation-on"])
            else:
                recipes["continuation-off"], recipes["continuation-on"] = recipes["continuation-on"], recipes["continuation-off"]
            with self.subTest(change=change), patch.object(p, "OPTIONS", recipes), self.assertRaises(ValueError):
                self.run_audit("check")
        self.assertEqual(FakeEngine.instances, [])

    def test_changed_role_values_or_unrelated_hints_cannot_launch(self):
        changes = (("continuation-off", "Continuation History", "true"),
                   ("continuation-on", "Continuation History", "false"),
                   ("continuation-on", "Continuation History", "yes"),
                   ("continuation-on", "Continuation History", True),
                   ("continuation-off", "TT Move Hints", "true"),
                   ("continuation-on", "TT Move Hints", "true"),
                   ("continuation-on", "Late Move Reductions", "false"),
                   ("continuation-on", "Unknown Setting", "false"))
        for role, name, value in changes:
            recipes = {key: dict(options) for key, options in p.OPTIONS.items()}
            recipes[role][name] = value
            with self.subTest(role=role, name=name, value=value), patch.object(p, "OPTIONS", recipes), self.assertRaises(ValueError):
                self.run_audit("check")
        self.assertEqual(FakeEngine.instances, [])

    def test_missing_or_unknown_requested_option_rejected_explicitly(self):
        options = p.options_for_role("continuation-off", self.network)
        for change in ("missing", "extra"):
            changed = dict(options)
            if change == "missing":
                changed.pop("Continuation History")
            else:
                changed["Unknown Setting"] = "true"
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.validate_identity(declarations(), changed)

    def test_readiness_mode_never_searches_and_checks_both_roles(self):
        report = self.run_audit("check")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["searches"], 0)
        self.assertEqual(len(FakeEngine.instances), 2)
        self.assertEqual({sample["role"] for sample in report["samples"]}, {"continuation-off", "continuation-on"})
        for engine in FakeEngine.instances:
            self.assertFalse(any(command.startswith(("go ", "position ")) for command in engine.commands))
            self.assertIn("ucinewgame", engine.commands)
            self.assertTrue(engine.closed)

    def test_smoke_records_distinct_processes_raw_eof_and_complete_commands(self):
        report = self.run_audit()
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["summary"]["searches"], 4)
        self.assertEqual([sample["role"] for sample in report["samples"]],
                         ["continuation-off", "continuation-on", "continuation-on", "continuation-off"])
        self.assertEqual(len({sample["pid"] for sample in report["samples"]}), 4)
        self.assertNotEqual(report["samples"][0]["result"]["score_cp"], report["samples"][1]["result"]["score_cp"])
        for sample in report["samples"]:
            self.assertEqual(sample["exit_code"], 0)
            self.assertEqual(sample["shutdown_eof_count"], 1)
            self.assertEqual(sample["shutdown_output"], [])
            self.assertEqual(sample["commands"].count("go movetime 1000"), 1)
            self.assertEqual(sample["commands"][-1], "quit")
            rows = [json.loads(line) for line in (self.root / "output" / sample["raw_log"]).read_text().splitlines()]
            self.assertTrue(any(row.get("line") is None and row.get("direction") == "<" for row in rows))
            self.assertEqual([row["line"] for row in rows if row.get("direction") == ">"], sample["commands"])
            starts = [row for row in rows if row.get("event") == "process_start"]
            exits = [row for row in rows if row.get("event") == "process_exit"]
            self.assertEqual([row["pid"] for row in starts], [sample["pid"]])
            self.assertEqual([(row["pid"], row["exit_code"], row["reader_alive"], row["shutdown_eof_count"])
                              for row in exits], [(sample["pid"], 0, False, 1)])
            self.assertEqual(sample["raw_sha256"], p.digest(self.root / "output" / sample["raw_log"]))
            self.assertTrue(FakeEngine.instances[sample["pid"] - 5000].closed)

    def test_known_syzygy_disabled_setup_line_only(self):
        for fault in ("bad-setup", "extra-setup"):
            with self.subTest(fault=fault):
                FakeEngine.fault = fault
                with self.assertRaises(ValueError):
                    self.run_audit()
                self.assertEqual(self.saved()["status"], "failed")
                self.assertTrue(FakeEngine.instances[-1].closed)
                # Each synthetic failure retains evidence under a separate path.
                (self.root / "output").rename(self.root / fault)

    def test_illegal_result_preserves_partial_evidence_and_kills_child(self):
        FakeEngine.fault = "illegal-best"
        with self.assertRaises(ValueError):
            self.run_audit()
        report = self.saved()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["samples"][0]["status"], "failed")
        self.assertTrue(report["samples"][0]["output"])
        self.assertTrue(FakeEngine.instances[0].closed and FakeEngine.instances[0].killed)

    def test_missing_response_and_early_exit_preserve_failures(self):
        for fault in ("partial-timeout", "early-eof"):
            with self.subTest(fault=fault):
                FakeEngine.fault = fault
                with self.assertRaises((RuntimeError, TimeoutError)):
                    self.run_audit()
                self.assertEqual(self.saved()["status"], "failed")
                self.assertTrue(FakeEngine.instances[-1].closed)
                (self.root / "output").rename(self.root / fault)

    def test_keyboard_interrupt_cleans_up_and_keeps_partial_run(self):
        FakeEngine.fault = "interrupt"
        with self.assertRaises(KeyboardInterrupt):
            self.run_audit()
        self.assertEqual(self.saved()["status"], "failed")
        self.assertTrue(FakeEngine.instances[0].closed and FakeEngine.instances[0].killed)

    def test_post_bestmove_extra_result_rejected(self):
        FakeEngine.fault = "post-bestmove"
        with self.assertRaises(ValueError):
            self.run_audit()
        self.assertEqual(self.saved()["status"], "failed")

    def test_shutdown_faults_cannot_be_reported_complete(self):
        for fault in ("bad-exit", "late-output", "missing-eof", "duplicate-eof", "reader-alive", "quit-timeout"):
            with self.subTest(fault=fault):
                FakeEngine.fault = fault
                with self.assertRaises((RuntimeError, ValueError, TimeoutError)):
                    self.run_audit()
                report = self.saved()
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["samples"][0]["status"], "failed")
                self.assertTrue(FakeEngine.instances[-1].closed)
                if fault == "bad-exit":
                    self.assertEqual(report["samples"][0]["exit_code"], 7)
                if fault == "quit-timeout":
                    self.assertTrue(FakeEngine.instances[-1].killed)
                (self.root / "output").rename(self.root / fault)

    def test_asset_drift_stops_before_another_engine_and_is_recorded(self):
        FakeEngine.mutate = self.corpus
        with self.assertRaises(ValueError):
            self.run_audit()
        self.assertEqual(len(FakeEngine.instances), 1)
        report = self.saved()
        self.assertEqual(report["status"], "failed")
        self.assertNotEqual(report["assets"]["corpus"]["sha256"], report["after_sha256"]["corpus"])

    def test_prepared_manifest_cannot_omit_add_or_change_input_identities(self):
        original = json.loads(self.pins.read_text())
        for change in ("omit", "extra", "digest", "source", "schema"):
            with self.subTest(change=change):
                document = json.loads(json.dumps(original))
                if change == "omit":
                    document["assets"].pop("corpus")
                elif change == "extra":
                    document["assets"]["unprepared"] = "0" * 64
                elif change == "digest":
                    document["assets"]["engine"] = "0" * 64
                elif change == "source":
                    document["engine_source_revision"] = "0" * 40
                else:
                    document["schema_version"] = 999
                self.pins.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    self.run_audit("check")
                self.assertEqual(FakeEngine.instances, [])
                output = self.root / "output"
                if output.exists():
                    output.rename(self.root / ("bad-pins-" + change))

    def test_missing_prepared_manifest_refused_before_any_process(self):
        self.pins.unlink()
        with self.assertRaises((OSError, ValueError)):
            self.run_audit("check")
        self.assertEqual(FakeEngine.instances, [])

    def frozen_source_manifest(self):
        """Save a miniature build snapshot, without compiling or invoking it."""
        directory = self.root / "build/experiments/phase4f9"
        source = directory / "source/src/search.cpp"
        source.parent.mkdir(parents=True)
        source.write_text("synthetic preserved source")
        origin = directory / "origin-manifest.json"
        origin.write_text('{"synthetic_original_build": true}')
        manifest = directory / "manifest.json"
        document = dict(schema_version=1, engine_source_revision=p.SOURCE_REVISION,
                        binary_sha256=p.ENGINE_SHA256, network_sha256=p.NETWORK_SHA256,
                        source_sha256={str(source.relative_to(self.root)): p.digest(source)},
                        origin_manifest=str(origin.relative_to(self.root)), origin_manifest_sha256=p.digest(origin))
        manifest.write_text(json.dumps(document))
        return manifest, source, document

    def test_frozen_build_sources_are_pinned_without_live_source_substitution(self):
        manifest, source, _ = self.frozen_source_manifest()
        live_source = self.root / "src/search.cpp"
        live_source.parent.mkdir()
        live_source.write_text("different later checkout source")
        with patch.object(p, "ROOT", self.root), patch.object(p, "ENGINE_MANIFEST", manifest):
            paths = p.asset_paths()
        self.assertEqual(paths[str(source.relative_to(self.root))], source)
        self.assertNotIn("src/search.cpp", paths)
        self.assertEqual(paths["engine_manifest"], manifest)
        self.assertEqual(paths["build/experiments/phase4f9/origin-manifest.json"], manifest.parent / "origin-manifest.json")

    def test_manifest_identity_empty_sources_or_changed_copy_fail_closed(self):
        manifest, source, original = self.frozen_source_manifest()
        for name, value in (("schema_version", 9), ("engine_source_revision", "0" * 40),
                            ("binary_sha256", "0" * 64), ("network_sha256", "0" * 64),
                            ("source_sha256", {}), ("source_sha256", []),
                            ("source_sha256", {str(source.relative_to(self.root)): "0" * 64})):
            manifest.write_text(json.dumps(dict(original, **{name: value})))
            with self.subTest(name=name, value=value), patch.object(p, "ROOT", self.root), \
                 patch.object(p, "ENGINE_MANIFEST", manifest), self.assertRaises(ValueError):
                p.asset_paths()
        self.assertEqual(FakeEngine.instances, [])

    def test_manifest_sources_cannot_escape_snapshot_or_alias_tool_input(self):
        manifest, source, original = self.frozen_source_manifest()
        outside = self.root / "outside.cpp"
        outside.write_bytes(source.read_bytes())
        for name in (str(source), "outside.cpp", "build/experiments/phase4f9/../outside.cpp",
                     "tools/check_phase4f9_puzzles.py"):
            changed = dict(original, source_sha256={name: p.digest(source)})
            manifest.write_text(json.dumps(changed))
            with self.subTest(name=name), patch.object(p, "ROOT", self.root), \
                 patch.object(p, "ENGINE_MANIFEST", manifest), self.assertRaises(ValueError):
                p.asset_paths()

    def test_original_build_provenance_missing_changed_or_escaping_rejected(self):
        manifest, _, original = self.frozen_source_manifest()
        origin = self.root / original["origin_manifest"]
        for name, value in (("origin_manifest", None), ("origin_manifest", str(origin)),
                            ("origin_manifest", "../origin-manifest.json"),
                            ("origin_manifest_sha256", "0" * 64)):
            manifest.write_text(json.dumps(dict(original, **{name: value})))
            with self.subTest(name=name, value=value), patch.object(p, "ROOT", self.root), \
                 patch.object(p, "ENGINE_MANIFEST", manifest), self.assertRaises(ValueError):
                p.asset_paths()

    def test_existing_output_refused_before_any_process(self):
        output = self.root / "output"
        output.mkdir()
        (output / "marker").write_text("retain me")
        with self.assertRaises(ValueError):
            self.run_audit()
        self.assertEqual((output / "marker").read_text(), "retain me")
        self.assertEqual(FakeEngine.instances, [])

    def test_missing_or_duplicate_matrix_and_failed_case_rejected(self):
        samples = self.run_audit()["samples"]
        for invalid in (samples[:-1], samples + samples[:1]):
            with self.assertRaises(ValueError):
                p.summarize(invalid, self.positions)
        samples[0]["status"] = "failed"
        with self.assertRaises(ValueError):
            p.summarize(samples, self.positions)

    def test_full_needs_quiet_attestation_before_launch(self):
        with self.assertRaises(ValueError):
            self.run_audit("full", allow_daytime=True)
        self.assertEqual(FakeEngine.instances, [])

    def test_full_daytime_flag_and_quiet_host_do_not_claim_human_approval(self):
        window = p.night_window("full", datetime(2026, 10, 25, 14, tzinfo=ZoneInfo("Europe/Helsinki")),
                                allow_daytime=True)
        window["cutoff_utc"] = datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
        with patch.object(p, "night_window", return_value=window):
            report = self.run_audit("full", allow_daytime=True, quiet_host=True)
        self.assertTrue(report["allow_daytime"] and report["quiet_host"])
        self.assertIn("not verified approval", report["authorization_note"])
        self.assertTrue(all("go movetime 60000" in sample["commands"] for sample in report["samples"]))

    def test_daytime_without_specific_exception_rejected(self):
        now = datetime(2026, 10, 25, 14, tzinfo=ZoneInfo("Europe/Helsinki"))
        with self.assertRaises(ValueError):
            p.night_window("full", now)
        self.assertTrue(p.night_window("full", now, allow_daytime=True)["allow_daytime"])

    def test_minimum_time_to_cutoff_cannot_be_overridden(self):
        for flag in (False, True):
            with self.assertRaises(ValueError):
                p.night_window("full", datetime(2026, 10, 25, 6, tzinfo=ZoneInfo("Europe/Helsinki")),
                               allow_daytime=flag)

    def test_both_dst_transitions_use_civil_seven_cutoff(self):
        for date, cutoff in (((2026, 10, 24), "2026-10-25T05:00:00+00:00"),
                             ((2026, 3, 28), "2026-03-29T04:00:00+00:00")):
            result = p.night_window("full", datetime(*date, 23, tzinfo=ZoneInfo("Europe/Helsinki")))
            self.assertEqual(result["cutoff_utc"], cutoff)
        with self.assertRaises(ValueError):
            p.night_window("full", datetime(2026, 10, 25))

    def test_invalid_flags_and_modes_never_launch(self):
        for mode, values in (("invalid", {}), ("smoke", {"allow_daytime": True}),
                             ("check", {"allow_daytime": True}), ("full", {"allow_daytime": 1, "quiet_host": True}),
                             ("full", {"allow_daytime": True, "quiet_host": "yes"})):
            with self.subTest(mode=mode, values=values), self.assertRaises(ValueError):
                self.run_audit(mode, **values)
        self.assertEqual(FakeEngine.instances, [])

    def test_cli_passes_explicit_flags_only(self):
        with patch.object(p, "audit") as audit:
            p.main(["--mode", "full", "--output", str(self.root), "--allow-daytime", "--quiet-host"])
            audit.assert_called_once_with("full", self.root, allow_daytime=True, quiet_host=True)
        with patch.object(p, "audit") as audit:
            p.main(["--mode", "check", "--output", str(self.root)])
            audit.assert_called_once_with("check", self.root, allow_daytime=False, quiet_host=False)

    def monitor(self, wall=100, mono=10, cutoff=None):
        with patch.object(p.time, "time", return_value=wall), patch.object(p.time, "monotonic", return_value=mono):
            return p.Monitor("smoke", {"cutoff_utc": cutoff}, self.network, [])

    def check_at(self, monitor, wall, mono):
        with patch.object(p.time, "time", return_value=wall), patch.object(p.time, "monotonic", return_value=mono), \
             patch.object(p, "resource_check", return_value={"active_search_workers": 8}):
            monitor.check()

    def test_suspend_wall_jumps_backward_clock_and_cumulative_drift_rejected(self):
        for wall, mono in ((107, 11), (107, 17), (106, 14), (90, 11), (101, 9)):
            with self.subTest(wall=wall, mono=mono), self.assertRaises(RuntimeError):
                self.check_at(self.monitor(), wall, mono)
        monitor = self.monitor()
        self.check_at(monitor, 103, 11)
        self.check_at(monitor, 106, 12)
        with self.assertRaises(RuntimeError):
            self.check_at(monitor, 109, 13)

    def test_total_deadline_and_cutoff_checked_during_poll(self):
        cutoff = datetime.fromtimestamp(101, timezone.utc).isoformat()
        with self.assertRaises(TimeoutError):
            self.check_at(self.monitor(cutoff=cutoff), 101, 11)
        monitor = self.monitor()
        monitor.deadline = 11
        with self.assertRaises(TimeoutError):
            self.check_at(monitor, 101, 11)

    def test_receipt_overrun_and_nonfinite_timings_rejected(self):
        sample = dict(elapsed_seconds=1.25, wall_elapsed_seconds=1.25)
        p.validate_search_timing(sample, 1000)
        for wall, mono in ((1.251, 1.251), (1.4, 1), (1, 1.4), (float("nan"), 1), (1, float("inf")), (-1, 1)):
            with self.subTest(wall=wall, mono=mono), self.assertRaises((ValueError, RuntimeError)):
                p.validate_search_timing(dict(elapsed_seconds=mono, wall_elapsed_seconds=wall), 1000)

    def test_memory_cpu_and_unknown_resource_limits_fail_closed(self):
        for cpu, ram in ((7, 64 * 1024**3), (9, 2 * 1024**3), (9, None)):
            with patch.object(p, "current_budget", return_value=dict(max_cpu_workers=cpu, memory_fraction=.5)), \
                 patch.object(p, "physical_memory", return_value=ram), patch.object(p.sys, "platform", "linux"), \
                 self.assertRaises(ValueError):
                p.resource_check(self.network)
        with patch.object(p, "current_budget", return_value=dict(max_cpu_workers=9, memory_fraction=.5)), \
             patch.object(p, "physical_memory", return_value=64 * 1024**3):
            resource = p.resource_check(self.network)
            self.assertEqual(resource["active_search_workers"], 8)
            self.assertGreaterEqual(resource["estimated_memory_bytes"], 2 * 1024**3)
            self.assertFalse(resource["memory_estimate_is_hard_cap"])

    def test_cp_mate_distance_and_pv_checkmate_are_distinct_claims(self):
        cp = p.validate_result(reply(), p.chess.STARTING_FEN, 7)
        self.assertEqual(cp["score_cp"], 10)
        self.assertIsNone(cp["reported_mate"])
        for value in (7, 8, -7):
            mate = p.validate_result(reply(score=f"mate {value}"), p.chess.STARTING_FEN, 7)
            self.assertEqual(mate["reported_mate"], value)
            self.assertEqual(mate["reported_mate_matches_supplied"], value == 7)
            self.assertEqual(mate["reported_positive_mate"], value > 0)
            self.assertFalse(mate["final_pv_ends_in_checkmate"])
            self.assertIn("does not prove", mate["mate_evidence_note"])

    def test_all_pvs_best_ponder_and_null_moves_require_legality(self):
        for changes in (dict(pv="g1h3 e2e4"), dict(best="e2e5"), dict(ponder="e2e4"), dict(best="0000")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                p.validate_result(reply(**changes), p.chess.STARTING_FEN, 7)

    def test_bounds_diagnostics_tb_hits_and_missing_score_or_total_rejected(self):
        for old, new in (("score cp 10", "score cp 10 lowerbound"), ("tbhits 0", "tbhits 1"),
                         ("tbhits 0", ""), ("score cp 10", "")):
            with self.subTest(new=new), self.assertRaises(ValueError):
                p.validate_result([line.replace(old, new) for line in reply()], p.chess.STARTING_FEN, 7)
        for rows in (["info string move-hints v1 enabled true"] + reply(), reply()[:1] + reply()[2:]):
            with self.assertRaises(ValueError):
                p.validate_result(rows, p.chess.STARTING_FEN, 7)


if __name__ == "__main__":
    unittest.main()
