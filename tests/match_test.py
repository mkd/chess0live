#!/usr/bin/env python3
"""Referee, clock, pairing, and persistence checks using tiny fake UCI processes.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import asyncio
from dataclasses import replace
import io
import json
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import match
import chess
import chess.pgn


# This deliberately tiny test double chooses legal moves rather than evaluating
# chess. Modes exercise the process/protocol boundary, not just mocked returns.
FAKE_ENGINE = r'''
import os, sys, time
import chess
mode = sys.argv[1]
board = chess.Board()
def output(text): print(text, flush=True)
for line in sys.stdin:
    tokens = line.split()
    if not tokens: continue
    command = tokens[0]
    if command == "uci":
        output("id name fake-" + mode)
        output("option name Hash type spin default 8 min 1 max 16384")
        if mode != "missing_threads":
            output("option name Threads type spin default 2 min 1 max 1024")
        output("option name EvalFile type string default none")
        output("option name Move Overhead type spin default 0 min 0 max 5000")
        output("option name Ponder type check default false")
        output("option name Time Policy type combo default classic var classic var forecast")
        output("option name Search Diagnostics type check default false")
        output("option name Research Toggle type check default true")
        output("option name Clear Hash type button")
        output("uciok")
    elif command == "isready":
        if mode == "slow_ready": time.sleep(0.12)
        output("readyok")
    elif command == "position":
        if tokens[1] == "startpos": board, index = chess.Board(), 2
        else: board, index = chess.Board(" ".join(tokens[2:8])), 8
        if index < len(tokens):
            for move in tokens[index+1:]: board.push_uci(move)
    elif command == "go":
        if mode == "crash": os._exit(7)
        if mode == "hang":
            while True: time.sleep(1)
        if mode == "illegal": output("bestmove a1a8"); continue
        if mode == "late": time.sleep(0.08)
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        chosen = moves[0]
        if mode == "mate":
            for move in moves:
                board.push(move)
                mating = board.is_checkmate()
                board.pop()
                if mating: chosen = move; break
        output("bestmove " + chosen.uci())
    elif command == "quit": break
'''


class ProtocolClockTests(unittest.IsolatedAsyncioTestCase):
    """Exercise real byte parsing with virtual time, without a child process."""

    def protocol(self, *, delayed_line=None):
        self.now = 1_000_000_000

        class DelayedLog(io.StringIO):
            def write(log, text):
                result = super().write(text)
                if delayed_line is not None and delayed_line in text:
                    self.now += 200_000_000
                return result

        self.log = DelayedLog()
        self.engine = match.RecordingProtocol("candidate", self.log)
        self.parsed = []
        self.engine.line_received = self.parsed.append
        return self.engine

    def records(self):
        return [json.loads(line) for line in self.log.getvalue().splitlines()]

    async def test_slow_info_logging_does_not_flag_bestmove_in_same_batch(self):
        engine = self.protocol(delayed_line="info depth 1")
        engine.go_ns = 950_000_000
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(1, b"info depth 1 time 50 nodes 1 pv e2e4\nbestmove e2e4\n")
        self.assertEqual(self.now, 1_200_000_000)
        self.assertEqual(engine.bestmove_ns - engine.go_ns, 50_000_000)
        self.assertLess(engine.bestmove_ns - engine.go_ns, 100_000_000)
        self.assertEqual([event["monotonic_ns"] for event in self.records()],
                         [1_000_000_000, 1_000_000_000])
        self.assertEqual(self.parsed, ["info depth 1 time 50 nodes 1 pv e2e4", "bestmove e2e4"])

    async def test_partial_line_uses_callback_completing_newline(self):
        engine = self.protocol()
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(1, b"bestmove e2")
            self.assertIsNone(engine.bestmove_ns)
            self.assertEqual(self.records(), [])
            self.now = 1_020_000_000
            engine.pipe_data_received(1, b"e4")
            self.assertIsNone(engine.bestmove_ns)
            self.now = 1_030_000_000
            engine.pipe_data_received(1, b"\r\n")
        self.assertEqual(engine.bestmove_ns, 1_030_000_000)
        self.assertEqual(self.parsed, ["bestmove e2e4"])

    async def test_reentrant_readyok_commands_follow_already_received_batch(self):
        engine = self.protocol(delayed_line="readyok")
        writes = []

        class Transport:
            def get_pipe_transport(self, fd):
                self.fd = fd
                return self

            def write(self, data):
                writes.append(data)

        engine.transport = Transport()

        def receive(line):
            self.parsed.append(line)
            if line == "readyok":
                engine.send_line("position startpos")
                engine.send_line("go wtime 100 btime 100")

        engine.line_received = receive
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(1, b"readyok\ninfo string ready\n")
        events = self.records()
        self.assertEqual([event["line"] for event in events],
                         ["readyok", "info string ready", "position startpos", "go wtime 100 btime 100"])
        stamps = [event["monotonic_ns"] for event in events]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(stamps[:2], [1_000_000_000, 1_000_000_000])
        self.assertEqual(engine.go_ns, 1_200_000_000)
        self.assertEqual(writes, [b"position startpos\n", b"go wtime 100 btime 100\n"])
        self.assertEqual(self.parsed, ["readyok", "info string ready"])

    async def test_stderr_batch_is_separate_and_preserves_error_detection(self):
        engine = self.protocol(delayed_line="warning one")
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(2, b"warning one\r\nwarning two\n")
            engine.pipe_data_received(1, b"info string error: invalid input\n")
        events = self.records()
        self.assertTrue(engine.stderr_seen)
        self.assertEqual([event["direction"] for event in events], ["stderr", "stderr", "from_engine"])
        self.assertEqual([event["monotonic_ns"] for event in events],
                         [1_000_000_000, 1_000_000_000, 1_200_000_000])
        self.assertEqual(engine.errors, ["info string error: invalid input"])
        self.assertEqual(self.parsed, ["info string error: invalid input"])

    async def test_utf8_and_crlf_still_use_upstream_buffering(self):
        engine = self.protocol()
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(1, b"info string caf\xc3")
            self.now += 10_000_000
            engine.pipe_data_received(1, b"\xa9\r\nbestmove e2e4\r\n")
        self.assertEqual(self.parsed, ["info string caf\u00e9", "bestmove e2e4"])
        self.assertEqual([event["monotonic_ns"] for event in self.records()],
                         [1_010_000_000, 1_010_000_000])

    async def test_parser_exception_clears_capture_state(self):
        engine = self.protocol()
        with patch.object(chess.engine.UciProtocol, "pipe_data_received", side_effect=ValueError("parser failure")):
            with self.assertRaisesRegex(ValueError, "parser failure"):
                engine.pipe_data_received(1, b"info string failed\n")
        self.assertIsNone(engine._received_lines)
        with patch.object(match.time, "monotonic_ns", return_value=2_000_000_000):
            engine._line_received("bestmove e2e4")
        self.assertEqual(engine.bestmove_ns, 2_000_000_000)
        self.assertEqual(self.parsed, ["bestmove e2e4"])

    async def test_invalid_utf8_does_not_poison_following_complete_line(self):
        engine = self.protocol()
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            with self.assertLogs("chess.engine", level="WARNING"):
                engine.pipe_data_received(1, b"\xff\nbestmove e2e4\n")
        self.assertIsNone(engine._received_lines)
        self.assertEqual(engine.bestmove_ns, 1_000_000_000)
        self.assertEqual(self.parsed, ["bestmove e2e4"])
        self.assertEqual([event["line"] for event in self.records()], ["bestmove e2e4"])

    async def test_actual_late_callback_still_expires_clock(self):
        engine = self.protocol()
        engine.go_ns = 800_000_000
        with patch.object(match.time, "monotonic_ns", side_effect=lambda: self.now):
            engine.pipe_data_received(1, b"bestmove e2e4\n")
        self.assertEqual(engine.bestmove_ns - engine.go_ns, 200_000_000)
        self.assertGreater(engine.bestmove_ns - engine.go_ns, 100_000_000)



class BufferedLogTests(unittest.IsolatedAsyncioTestCase):
    """Deterministic slow/failing storage with no chess engine or disk sleep."""

    async def wait_event(self, event):
        self.assertTrue(await asyncio.to_thread(event.wait, 2.0), "writer did not reach test gate")

    async def test_blocked_writer_does_not_delay_a_later_protocol_callback(self):
        entered, release = threading.Event(), threading.Event()
        events = []
        owner = threading.get_ident()

        class Stream:
            def write(stream, text):
                self.assertNotEqual(threading.get_ident(), owner)
                if not events:
                    entered.set()
                    if not release.wait(2.0):
                        raise RuntimeError("test release missing")
                events.append(text)
            def flush(stream):
                self.assertNotEqual(threading.get_ident(), owner)
            def close(stream):
                self.assertNotEqual(threading.get_ident(), owner)

        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        engine = match.RecordingProtocol("candidate", log)
        engine.line_received = lambda _: None
        engine.go_ns = 950_000_000
        try:
            with patch.object(match.time, "monotonic_ns", return_value=1_000_000_000):
                engine.pipe_data_received(1, b"info depth 1 nodes 1 pv e2e4\n")
            await self.wait_event(entered)
            # A separate later callback runs while persistence is still blocked.
            with patch.object(match.time, "monotonic_ns", return_value=1_010_000_000):
                engine.pipe_data_received(1, b"bestmove e2e4\n")
            self.assertEqual(engine.bestmove_ns - engine.go_ns, 60_000_000)
            self.assertEqual(events, [])
            draining = asyncio.create_task(log.drain())
            await asyncio.sleep(0)
            self.assertFalse(draining.done())
        finally:
            release.set()
        await draining
        await log.close()
        self.assertEqual([json.loads(text)["line"] for text in events],
                         ["info depth 1 nodes 1 pv e2e4", "bestmove e2e4"])

    async def test_byte_capacity_includes_in_flight_utf8_record(self):
        entered, release = threading.Event(), threading.Event()
        class Stream:
            def write(stream, text):
                entered.set()
                release.wait(2.0)
            def flush(stream): pass
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), max_bytes=4, opener=lambda _: Stream())
        await log.ready()
        log.write("éé")
        await self.wait_event(entered)
        try:
            with self.assertRaisesRegex(match.PersistenceError, "capacity"):
                log.write("x")
            self.assertIsNotNone(log.error)
        finally:
            release.set()
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_record_capacity_latches_without_escaping_pipe_callback(self):
        entered, release = threading.Event(), threading.Event()
        class Stream:
            def write(stream, text):
                entered.set()
                release.wait(2.0)
            def flush(stream): pass
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), max_records=1, opener=lambda _: Stream())
        await log.ready()
        engine = match.RecordingProtocol("candidate", log)
        engine.line_received = lambda _: None
        engine.pipe_data_received(1, b"info depth 1\n")
        await self.wait_event(entered)
        try:
            engine.pipe_data_received(1, b"bestmove e2e4\n")
            self.assertIsNotNone(engine.bestmove_ns)
            self.assertIn("capacity", str(log.error))
            self.assertIs(await log.failure, log.error)
        finally:
            release.set()
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_failure_suppresses_new_search_but_keeps_cleanup_commands(self):
        class Stream:
            def write(stream, text): pass
            def flush(stream): pass
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        writes = []
        class Transport:
            def get_pipe_transport(transport, fd): return transport
            def write(transport, data): writes.append(data)
        engine = match.RecordingProtocol("candidate", log)
        engine.transport = Transport()
        log.fail(match.PersistenceError("injected failure"))
        engine.send_line("go wtime 100 btime 100")
        engine.send_line("stop")
        engine.send_line("quit")
        self.assertIsNone(engine.go_ns)
        self.assertEqual(writes, [b"stop\n", b"quit\n"])
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_overlapping_drain_does_not_build_unbounded_barriers(self):
        entered, release = threading.Event(), threading.Event()
        class Stream:
            def write(stream, text):
                entered.set()
                release.wait(2.0)
            def flush(stream): pass
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        log.write("one\n")
        await self.wait_event(entered)
        first = asyncio.create_task(log.drain())
        await asyncio.sleep(0)
        try:
            with self.assertRaisesRegex(match.PersistenceError, "Overlapping"):
                await log.drain()
        finally:
            release.set()
        with self.assertRaises(match.PersistenceError):
            await first
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_write_failure_aborts_active_operation_and_closes_stream(self):
        closed, cancelled = threading.Event(), asyncio.Event()
        class Stream:
            def write(stream, text): raise OSError("injected full disk")
            def flush(stream): pass
            def close(stream): closed.set()
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        async def operation():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        guarded = asyncio.create_task(match.persistence_guard(operation(), log))
        await asyncio.sleep(0)
        log.write("one\n")
        with self.assertRaisesRegex(match.PersistenceError, "full disk"):
            await guarded
        self.assertTrue(cancelled.is_set())
        with self.assertRaises(match.PersistenceError):
            await log.close()
        self.assertTrue(closed.is_set())

    async def test_open_and_flush_failures_are_observed(self):
        def broken_open(_): raise OSError("injected open failure")
        log = match.BufferedLog(Path("unused"), opener=broken_open)
        with self.assertRaisesRegex(match.PersistenceError, "open failure"):
            await log.ready()
        with self.assertRaises(match.PersistenceError):
            await log.close()
        class Stream:
            def write(stream, text): pass
            def flush(stream): raise OSError("injected flush failure")
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        log.write("one\n")
        with self.assertRaisesRegex(match.PersistenceError, "flush failure"):
            await log.drain()
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_final_flush_failure_still_attempts_close(self):
        closed = threading.Event()
        class Stream:
            def write(stream, text): pass
            def flush(stream): raise OSError("injected final flush failure")
            def close(stream): closed.set()
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        log.write("one\n")
        with self.assertRaisesRegex(match.PersistenceError, "final flush failure"):
            await log.close()
        self.assertTrue(closed.is_set())

    async def test_cancelled_close_still_drains_and_closes_before_propagating(self):
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        events = []
        class Stream:
            def write(stream, text):
                entered.set()
                release.wait(2.0)
                events.append(text)
            def flush(stream): pass
            def close(stream): closed.set()
        log = match.BufferedLog(Path("unused"), opener=lambda _: Stream())
        await log.ready()
        log.write("one\n")
        await self.wait_event(entered)
        closing = asyncio.create_task(match.finish_cleanup(log.close()))
        await asyncio.sleep(0)
        closing.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await closing
        self.assertEqual(events, ["one\n"])
        self.assertTrue(closed.is_set())

    async def test_blocked_writer_deadline_fails_closed(self):
        entered, release = threading.Event(), threading.Event()
        class Stream:
            def write(stream, text):
                entered.set()
                release.wait(2.0)
            def flush(stream): pass
            def close(stream): pass
        log = match.BufferedLog(Path("unused"), timeout=0.02, opener=lambda _: Stream())
        await log.ready()
        log.write("one\n")
        await self.wait_event(entered)
        try:
            with self.assertRaisesRegex(match.PersistenceError, "deadline"):
                await log.drain()
            self.assertIsNotNone(log.error)
        finally:
            release.set()
        with self.assertRaises(match.PersistenceError):
            await log.close()

    async def test_disk_checkpoint_finishes_before_cancellation_propagates(self):
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        owner = threading.get_ident()
        def work():
            self.assertNotEqual(threading.get_ident(), owner)
            entered.set()
            release.wait(2.0)
            done.set()
        task = asyncio.create_task(match.disk_io(work))
        await self.wait_event(entered)
        task.cancel()
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(done.is_set())


class RefereeResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    """Adjudication must leave other shards' protocol callbacks serviceable."""

    async def test_adjudication_does_not_block_another_protocol_receipt(self):
        loop = asyncio.get_running_loop()
        delivered = threading.Event()
        observation = {}
        virtual_now = [1_000_000_000]
        receiver = match.RecordingProtocol("other-shard", io.StringIO())
        receiver.go_ns = 950_000_000
        receiver.line_received = lambda _: None
        original_outcome = chess.Board.outcome

        def receive():
            receiver.pipe_data_received(1, b"bestmove e2e4\n")
            delivered.set()

        def adjudicate(board, *, claim_draw=False):
            if not claim_draw:
                return original_outcome(board, claim_draw=claim_draw)
            # The callback is ready while this shard is adjudicating. Only the
            # event loop can release this gate. The watchdog bounds a broken
            # implementation; no measured scheduling duration selects a pass.
            loop.call_soon_threadsafe(receive)
            observation["callback_during_adjudication"] = delivered.wait(2.0)
            if not observation["callback_during_adjudication"]:
                virtual_now[0] += 200_000_000
            return chess.Outcome(chess.Termination.STALEMATE, None)

        with tempfile.TemporaryDirectory(prefix="chess0live-referee-test-") as directory:
            output = Path(directory)
            opening = match.Opening("controlled-adjudication", chess.Board(), "test")
            records = []
            # Empty specs deliberately avoid engines/searches. This is a
            # controlled terminal referee result, not a real chess game.
            with patch.object(chess.Board, "outcome", adjudicate), patch.object(
                    match.time, "monotonic_ns", side_effect=lambda: virtual_now[0]):
                record = await match.play_game([], match.Settings(initial=1.0, increment=0.0), opening,
                                               "p1", "p1-1", "white", {},
                                               output, records.append)
            self.assertEqual(record["termination"], "stalemate")
            self.assertEqual(records, [record])
        self.assertTrue(observation["callback_during_adjudication"],
                        "Referee adjudication blocked another shard's ready callback")
        self.assertEqual(receiver.bestmove_ns - receiver.go_ns, 50_000_000)

    async def test_cancel_waits_for_adjudication_to_restore_board(self):
        entered, release, restored = threading.Event(), threading.Event(), threading.Event()
        original_outcome = chess.Board.outcome
        records = []

        def adjudicate(board, *, claim_draw=False):
            if not claim_draw:
                return original_outcome(board, claim_draw=claim_draw)
            board.push_uci("e2e4")
            entered.set()
            try:
                if not release.wait(2.0):
                    raise RuntimeError("test adjudication gate expired")
            finally:
                board.pop()
                restored.set()
            return None

        def record_result(record):
            self.assertTrue(restored.is_set(), "Cleanup raced a mutating referee worker")
            records.append(record)

        with tempfile.TemporaryDirectory(prefix="chess0live-referee-cancel-") as directory:
            opening = match.Opening("controlled-cancellation", chess.Board(), "test")
            with patch.object(chess.Board, "outcome", adjudicate):
                task = asyncio.create_task(match.play_game(
                    [], match.Settings(initial=1.0, increment=0.0), opening,
                    "p1", "p1-1", "white", {}, Path(directory), record_result))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2.0))
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(task.done())
                    self.assertEqual(records, [])
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertTrue(restored.is_set())
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["status"], "interrupted")
            self.assertEqual(records[0]["final_fen"], chess.STARTING_FEN)
            self.assertEqual(records[0]["played_plies"], 0)
            self.assertEqual(opening.board.fen(), chess.STARTING_FEN)

    async def test_adjudication_error_remains_a_runner_failure(self):
        original_outcome = chess.Board.outcome

        def adjudicate(board, *, claim_draw=False):
            if claim_draw:
                raise RuntimeError("controlled adjudication failure")
            return original_outcome(board, claim_draw=claim_draw)

        with tempfile.TemporaryDirectory(prefix="chess0live-referee-error-") as directory:
            opening = match.Opening("controlled-error", chess.Board(), "test")
            records = []
            with patch.object(chess.Board, "outcome", adjudicate):
                record = await match.play_game(
                    [], match.Settings(initial=1.0, increment=0.0), opening,
                    "p1", "p1-1", "white", {}, Path(directory), records.append)
            self.assertEqual(records, [record])
            self.assertEqual(record["status"], "protocol_failure")
            self.assertEqual(record["termination"], "runner_error")
            self.assertIn("controlled adjudication failure", record["error"])
            self.assertEqual(record["result"], "*")
            self.assertIsNone(record["candidate_score"])


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="chess0live-match-test-")
        self.root = Path(self.directory.name)
        self.fake = self.root / "fake engine.py"
        self.fake.write_text(FAKE_ENGINE, encoding="utf-8")
        self.network = self.root / "fake network.nnue"
        self.network.write_bytes(b"fake network: protocol tests do not load neural weights\n")
        self.suite = self.root / "openings.json"
        self.write_suite([{"id": "test-start", "moves": []}])
        self.settings = match.Settings(initial=1.0, increment=0.0, hash_mb=1,
                                       max_plies=1, startup_timeout=2.0,
                                       protocol_timeout=0.25, move_overhead_ms=0, smoke=True)
        self.sequence = 0
        self.budget = {"percent": 50, "max_cpu_workers": 8, "memory_fraction": 0.5}
        self.policy_patch = patch.object(match, "current_budget", return_value=self.budget.copy())
        self.policy_patch.start()
        logging.getLogger("chess.engine").setLevel(logging.CRITICAL)

    def tearDown(self):
        self.policy_patch.stop()
        self.directory.cleanup()

    def write_suite(self, openings):
        self.suite.write_text(json.dumps({"description": "Original protocol-test fixtures", "openings": openings}), encoding="utf-8")

    def specs(self, candidate="normal", opponent="normal"):
        return [match.EngineSpec(role, Path(sys.executable).resolve(), self.network,
                                 arguments=(str(self.fake), mode), source_revision="unverified-test-label")
                for role, mode in (("candidate", candidate), ("opponent", opponent))]

    def play(self, candidate="normal", opponent="normal", settings=None, opening=None, specs=None):
        self.sequence += 1
        output = self.root / f"game-{self.sequence}"
        output.mkdir()
        if opening is None:
            opening = match.read_openings(self.suite)[1][0]
        records = []
        record = asyncio.run(match.play_game(specs or self.specs(candidate, opponent), settings or self.settings,
                                             opening, "p1", "p1-1", "white", self.budget,
                                             output, records.append))
        self.assertEqual(records, [record])
        self.assertTrue((output / record["pgn"]).is_file())
        transcript = [json.loads(line) for line in (output / record["protocol_log"]).read_text().splitlines()]
        return record, transcript, output

    def test_openings_reject_null_illegal_duplicate_and_terminal(self):
        cases = [
            [{"id": "null", "moves": ["0000"]}],
            [{"id": "illegal", "moves": ["e2e5"]}],
            [{"id": "a", "moves": []}, {"id": "b", "moves": []}],
            [{"id": "drawn", "fen": "7k/8/5K2/8/8/8/8/8 w - - 0 1"}],
            [{"id": "malformed", "fen": None}],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                self.write_suite(entries)
                with self.assertRaises(ValueError): match.read_openings(self.suite)

    def test_seeded_plan_has_no_recycling(self):
        self.write_suite([{"id": f"opening-{index}", "moves": [move]}
                          for index, move in enumerate(("a2a3", "b2b3", "c2c3", "d2d3"))])
        openings = match.read_openings(self.suite)[1]
        first = match.plan_pairs(openings, 4, 271)
        second = match.plan_pairs(openings, 4, 271)
        self.assertEqual([(p["opening"].key, p["first_candidate_color"]) for p in first],
                         [(p["opening"].key, p["first_candidate_color"]) for p in second])
        self.assertEqual(len({pair["opening"].key for pair in first}), 4)
        with self.assertRaises(ValueError): match.plan_pairs(openings, 5, 0)

    def test_nonfinite_and_excessive_limits_rejected(self):
        for field in ("initial", "increment", "startup_timeout", "protocol_timeout"):
            for value in (float("nan"), float("inf"), -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.settings, **{field: value}).validate()
        for field, value in (("threads", 0), ("threads", 1025), ("hash_mb", 16385),
                             ("max_plies", 10001), ("move_overhead_ms", 5001)):
            with self.assertRaises(ValueError): replace(self.settings, **{field: value}).validate()

    def test_full_opening_history_and_increment_survive(self):
        moves = ["g1f3", "g8f6", "f3g1", "f6g8"]
        self.write_suite([{"id": "repetition-history", "moves": moves}])
        record, transcript, output = self.play(settings=replace(self.settings, increment=0.5))
        self.assertEqual(record["status"], "truncated")
        self.assertEqual(record["result"], "*")
        self.assertIsNone(record["candidate_score"])
        event = record["moves"][0]
        self.assertAlmostEqual(event["clock_after"], 1.5 - event["elapsed_seconds"])
        self.assertTrue(event["played"])
        commands = [line["line"] for line in transcript if line["direction"] == "to_engine"]
        self.assertIn("position startpos moves " + " ".join(moves), commands)
        self.assertFalse(any(line.startswith("go ponder") for line in commands))
        self.assertIn("setoption name Hash value 1", commands)
        self.assertIn("setoption name Threads value 1", commands)
        game = chess.pgn.read_game(io.StringIO((output / record["pgn"]).read_text()))
        self.assertEqual([move.uci() for move in game.mainline_moves()][:4], moves)

    def test_late_legal_move_loses_without_increment_or_board_change(self):
        settings = replace(self.settings, initial=0.01, increment=1.0)
        record, _, _ = self.play(candidate="late", settings=settings)
        self.assertEqual(record["status"], "complete")
        self.assertEqual(record["termination"], "time_forfeit")
        self.assertEqual(record["result"], "0-1")
        self.assertEqual(record["candidate_score"], 0.0)
        self.assertEqual(record["played_plies"], 0)
        self.assertEqual(record["final_fen"], chess.STARTING_FEN)
        self.assertFalse(record["moves"][0]["played"])
        self.assertLess(record["clocks"]["white"], 0)

    def test_flagfall_without_opponent_mating_material_draws(self):
        board = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        self.assertEqual(match.clock_outcome(board, chess.WHITE), "1/2-1/2")
        self.assertEqual(match.clock_outcome(board, chess.BLACK), "1-0")

    def test_readiness_is_outside_chess_clock(self):
        record, transcript, _ = self.play(candidate="slow_ready", settings=replace(self.settings, initial=0.05, protocol_timeout=0.02))
        self.assertEqual(record["status"], "truncated")
        self.assertTrue(record["moves"][0]["played"])
        lines = [line for line in transcript if line["engine"] == "candidate"]
        go = next(line for line in lines if line["line"].startswith("go "))
        first_ready = next(line for line in lines if line["line"] == "isready")
        self.assertGreater((go["monotonic_ns"] - first_ready["monotonic_ns"]) / 1e9, 0.2)
        self.assertLess(record["moves"][0]["elapsed_seconds"], 0.05)

    def test_protocol_failure_is_not_a_chess_loss(self):
        for mode in ("illegal", "crash"):
            with self.subTest(mode=mode):
                record, _, _ = self.play(candidate=mode)
                self.assertEqual(record["status"], "protocol_failure")
                self.assertEqual(record["result"], "*")
                self.assertIsNone(record["candidate_score"])
                self.assertEqual(record["played_plies"], 0)

    def test_no_reply_is_protocol_timeout(self):
        record, _, _ = self.play(candidate="hang", settings=replace(self.settings, initial=0.01, protocol_timeout=0.02))
        self.assertEqual(record["status"], "protocol_timeout")
        self.assertEqual(record["result"], "*")

    def test_missing_required_option_is_setup_failure(self):
        record, _, _ = self.play(candidate="missing_threads")
        self.assertEqual(record["status"], "setup_failure")
        self.assertIn("Threads", record["error"])

    def test_full_pair_persists_hashes_pgn_json_and_swaps_colors(self):
        self.write_suite([{"id": "mate-fixture", "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"}])
        output = self.root / "paired"
        result = asyncio.run(match.run_match(self.specs("mate", "mate"), self.settings, self.suite, output, 1, 7))
        records = [json.loads(line) for line in (output / "games.jsonl").read_text().splitlines()]
        self.assertEqual({record["candidate_color"] for record in records}, {"white", "black"})
        self.assertEqual([record["termination"] for record in records], ["checkmate", "checkmate"])
        self.assertEqual(result["included_pairs"], 1)
        self.assertEqual(result["wdl"], {"wins": 1, "draws": 0, "losses": 1})
        self.assertFalse(result["inference_eligible"])
        self.assertIn("smoke_run_not_a_strength_experiment", result["uncertainty"]["withheld_reasons"])
        manifest = json.loads((output / "run.json").read_text())
        self.assertEqual(manifest["status"], "finished")
        self.assertEqual(len(manifest["runner_sources"]), 3)
        self.assertEqual(manifest["plan"][0]["starting_fen"], "7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        self.assertEqual((output / "openings.json").read_bytes(), self.suite.read_bytes())
        for engine in manifest["engines"].values():
            self.assertFalse(engine["source_revision"]["verified_against_binary"])
            self.assertEqual(len(engine["artifacts"]), 3)
            self.assertTrue(all(len(item["sha256"]) == 64 for item in engine["artifacts"]))
        with self.assertRaises(ValueError):
            asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 7))

    def test_protocol_writer_failure_stops_run_and_records_no_chess_result(self):
        output = self.root / "writer-failure"
        class BrokenStream:
            def write(stream, text): raise OSError("injected write failure")
            def flush(stream): pass
            def close(stream): pass
        original = match.BufferedLog
        with patch.object(match, "BufferedLog", side_effect=lambda path: original(
                path, opener=lambda _: BrokenStream())) as factory:
            # Keep the production manifest bounds while injecting only I/O.
            factory.MAX_BYTES, factory.MAX_RECORDS, factory.TIMEOUT = (
                original.MAX_BYTES, original.MAX_RECORDS, original.TIMEOUT)
            with self.assertRaisesRegex(match.PersistenceError, "write failure"):
                asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
        records = [json.loads(line) for line in (output / "games.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "persistence_failure")
        self.assertEqual(records[0]["result"], "*")
        self.assertIsNone(records[0]["candidate_score"])
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "interrupted")
        self.assertFalse(json.loads((output / "summary.json").read_text())["experiment_complete"])

    def test_final_summary_failure_never_publishes_finished_run(self):
        output = self.root / "final-summary-failure"
        original = match.atomic_json
        failed = []
        def write(path, value):
            if path.name == "summary.json" and value["experiment_complete"]:
                failed.append(path)
                raise OSError("injected final summary failure")
            return original(path, value)
        with patch.object(match, "atomic_json", side_effect=write):
            with self.assertRaisesRegex(OSError, "final summary failure"):
                asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
        self.assertEqual(len(failed), 1)
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "interrupted")
        self.assertFalse(json.loads((output / "summary.json").read_text())["experiment_complete"])

    def test_cancelled_journal_open_is_closed_and_recorded_interrupted(self):
        output = self.root / "cancel-journal-open"
        entered, release = threading.Event(), threading.Event()
        handles = []
        original = Path.open
        def open_path(path, *args, **kwargs):
            stream = original(path, *args, **kwargs)
            if path == output / "games.jsonl":
                handles.append(stream)
                entered.set()
                if not release.wait(2.0):
                    raise RuntimeError("test release missing")
            return stream
        async def scenario():
            task = asyncio.create_task(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
            self.assertTrue(await asyncio.to_thread(entered.wait, 2.0))
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        with patch.object(Path, "open", new=open_path):
            asyncio.run(scenario())
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "interrupted")
        self.assertFalse(json.loads((output / "summary.json").read_text())["experiment_complete"])
        self.assertEqual(list(output.glob("*.protocol.jsonl")), [])

    def test_failed_run_marker_still_attempts_incomplete_summary(self):
        output = self.root / "failed-run-marker"
        original = match.atomic_json
        def write(path, value):
            if path.name == "run.json" and value["status"] != "running":
                raise OSError("injected final run marker failure")
            return original(path, value)
        with patch.object(match, "atomic_json", side_effect=write):
            with self.assertRaisesRegex(OSError, "run marker failure"):
                asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
        # The old running marker cannot claim completion, and its separate
        # summary was explicitly invalidated even though run.json still failed.
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "running")
        self.assertFalse(json.loads((output / "summary.json").read_text())["experiment_complete"])

    def test_budget_is_reread_between_games(self):
        output = self.root / "budget-change"
        allowed = dict(self.budget)
        denied = dict(self.budget, max_cpu_workers=1)
        settings = replace(self.settings, threads=2)
        with patch.object(match, "current_budget", side_effect=[allowed, allowed, denied]) as calls:
            with self.assertRaises(ValueError):
                asyncio.run(match.run_match(self.specs(), settings, self.suite, output, 1, 0))
        self.assertEqual(calls.call_count, 3)
        self.assertEqual(len((output / "games.jsonl").read_text().splitlines()), 1)
        self.assertEqual(json.loads((output / "run.json").read_text())["status"], "interrupted")

    def test_last_game_asset_change_invalidates_finished_experiment(self):
        output = self.root / "asset-change"
        original_play = match.play_game
        completed = 0
        async def change_after_second(*args, **kwargs):
            nonlocal completed
            result = await original_play(*args, **kwargs)
            completed += 1
            if completed == 2:
                self.network.write_bytes(b"changed while final game was running")
            return result
        with patch.object(match, "play_game", side_effect=change_after_second):
            with self.assertRaises(ValueError):
                asyncio.run(match.run_match(self.specs(), self.settings, self.suite, output, 1, 0))
        self.assertEqual(completed, 2)
        summary = json.loads((output / "summary.json").read_text())
        self.assertFalse(summary["experiment_complete"])
        self.assertFalse(summary["inference_eligible"])

    def test_experiment_options_are_sent_per_engine_and_recorded(self):
        specs = self.specs()
        specs[0] = replace(specs[0], extra_options=(("Time Policy", "forecast"), ("Research Toggle", "false")))
        specs[1] = replace(specs[1], extra_options=(("Time Policy", "classic"),))
        record, transcript, _ = self.play(specs=specs)
        self.assertEqual(record["status"], "truncated")
        commands = [line["line"] for line in transcript
                    if line["engine"] == "candidate" and line["direction"] == "to_engine"]
        self.assertIn("setoption name Time Policy value forecast", commands)
        self.assertIn("setoption name Research Toggle value false", commands)
        self.assertEqual(record["engines"]["candidate"]["options"]["Time Policy"], "forecast")
        self.assertIs(record["engines"]["candidate"]["options"]["Search Diagnostics"], False)
        self.assertEqual(record["engines"]["opponent"]["options"]["Time Policy"], "classic")

    def test_experiment_options_cannot_bypass_settings_or_protocol(self):
        invalid = (("Hash", "2"), ("hash", "2"), ("Threads", "8"), ("Ponder", "true"),
                   ("EvalFile", "elsewhere"), ("Search Diagnostics", "true"),
                   ("Clear Hash", ""), ("Absent", "forecast"), ("Time Policy", "invalid"),
                   ("Research Toggle", "False"), ("Time Policy", "classic\nquit"))
        for option in invalid:
            with self.subTest(option=option):
                specs = self.specs()
                specs[0] = replace(specs[0], extra_options=(option,))
                record, _, _ = self.play(specs=specs)
                self.assertEqual(record["status"], "setup_failure")
                self.assertEqual(record["played_plies"], 0)

    def test_option_parser_rejects_duplicates_and_command_injection(self):
        self.assertEqual(match.parse_options(["Time Policy=forecast", "Label=a=b"]),
                         (("Time Policy", "forecast"), ("Label", "a=b")))
        for entries in ([""], ["=x"], ["x=1", "X=2"], ["Time Policy=classic\nquit"], ["a\0=x"]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                match.parse_options(entries)

    def test_experiment_options_persist_in_frozen_manifest(self):
        self.write_suite([{"id": "mate-fixture", "fen": "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"}])
        specs = self.specs("mate", "mate")
        specs[0] = replace(specs[0], extra_options=(("Time Policy", "forecast"),))
        output = self.root / "option-manifest"
        asyncio.run(match.run_match(specs, self.settings, self.suite, output, 1, 7))
        manifest = json.loads((output / "run.json").read_text())
        self.assertEqual(manifest["engines"]["candidate"]["experiment_options"], {"Time Policy": "forecast"})
        self.assertEqual(manifest["engines"]["opponent"]["experiment_options"], {})


if __name__ == "__main__":
    unittest.main()
