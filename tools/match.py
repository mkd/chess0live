#!/usr/bin/env python3
"""Run a fixed, reproducible set of paired-opening UCI games locally.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Requires chess==1.11.2. Games run sequentially, without pondering. The referee
automatically claims available rule-50/threefold draws for either side. A clock
loss is a real result; protocol failures and ply-cap truncations are excluded.
No evaluation-based resignation/draw adjudication or absolute Elo claim is made.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import queue
import subprocess
import sys
import time
import threading

try:
    import chess
    import chess.engine
    import chess.pgn
except ImportError as error:
    raise SystemExit("Match tools require: python3 -m pip install -r requirements-match.txt") from error

from resources import current_budget
from match_statistics import summarize_pairs

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_CHESS_VERSION = "1.11.2"


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    """Publish a whole JSON document, leaving the previous one intact on error."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


@dataclass(frozen=True)
class EngineSpec:
    role: str
    executable: Path
    network: Path
    network_option: str = "EvalFile"
    arguments: tuple = ()
    source_revision: str = None
    extra_options: tuple = ()

    def artifacts(self):
        """Freeze explicit executables/networks and script-file wrapper arguments."""
        paths = [self.executable, self.network]
        paths.extend(Path(arg).resolve() for arg in self.arguments if Path(arg).is_file())
        return [{"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
                for path in dict.fromkeys(paths)]


def parse_options(entries):
    """Parse explicit experiment options without allowing ambiguous overrides.

    Resource, network, book, tablebase, and protocol-managed options retain the
    common match configuration. Research options such as Time Policy may differ
    between the two engines and are frozen in the match manifest.
    """
    parsed = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, str) or "=" not in entry or any(c in entry for c in "\r\n\0"):
            raise ValueError("Engine options must be single-line NAME=VALUE entries")
        name, value = (part.strip() for part in entry.split("=", 1))
        if not name or name.casefold() in seen:
            raise ValueError("Engine option names must be nonempty and unique")
        seen.add(name.casefold())
        parsed.append((name, value))
    return tuple(parsed)


def experiment_options(spec, protocol, configured):
    """Validate advertised option types before sending any experiment settings."""
    protected = {name.casefold() for name in (
        "Hash", "Threads", spec.network_option, "Ponder", "MultiPV", "UCI_Chess960",
        "UCI_Variant", "OwnBook", "UseBook", "BookFile", "SyzygyPath", "GaviotaTbPath",
        "UCI_LimitStrength", "UCI_AnalyseMode", "UCI_Elo", "Skill Level", "Move Overhead",
        "Search Diagnostics", "Clear Hash")}
    protected.update(name.casefold() for name in configured)
    result = {}
    seen = set()
    for name, value in spec.extra_options:
        if (not isinstance(name, str) or not isinstance(value, str)
                or not name or name != name.strip()
                or any(c in name + value for c in "\r\n\0")):
            raise ValueError("Invalid experiment option name/value")
        if name.casefold() in seen or name.casefold() in protected:
            raise ValueError(f"Duplicate or match-controlled option: {name}")
        seen.add(name.casefold())
        if name not in protocol.options:
            raise ValueError(f"{spec.role} does not advertise experiment option {name}")
        option = protocol.options[name]
        if option.is_managed() or option.type in ("button", "reset", "save"):
            raise ValueError(f"Experiment option cannot be managed or a button: {name}")
        if option.type == "check":
            if value not in ("true", "false"):
                raise ValueError(f"Check option {name} expects true or false")
            value = value == "true"
        result[option.name] = option.parse(value)
    return result


@dataclass(frozen=True)
class Settings:
    initial: float
    increment: float
    hash_mb: int = 64
    threads: int = 1
    max_plies: int = 512
    startup_timeout: float = 30.0
    protocol_timeout: float = 5.0
    move_overhead_ms: int = 20
    smoke: bool = False

    def validate(self):
        for name in ("initial", "increment", "startup_timeout", "protocol_timeout"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0 or (name != "increment" and value == 0):
                raise ValueError(f"{name} must be finite and {'nonnegative' if name == 'increment' else 'positive'}")
        for name, maximum in (("hash_mb", 16384), ("threads", 1024), ("max_plies", 10000)):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer from 1 to {maximum}")
        if not 0 <= self.move_overhead_ms <= 5000:
            raise ValueError("move_overhead_ms must be from 0 to 5000")
        for name, maximum in (("initial", 86400), ("increment", 3600),
                              ("startup_timeout", 600), ("protocol_timeout", 60)):
            if getattr(self, name) > maximum:
                raise ValueError(f"{name} must not exceed {maximum} seconds")


@dataclass
class Opening:
    identifier: str
    board: chess.Board
    key: str


def read_openings(path, contents=None):
    """Parse standard-chess roots plus legal UCI moves, retaining every move.

    A supplied FEN provides no history before that FEN. No opening is silently
    recycled, and terminal/duplicate entries are rejected before launching engines.
    """
    document = json.loads(contents if contents is not None else Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("openings"), list):
        raise ValueError("Opening suite must contain an openings list")
    openings, ids, keys = [], set(), set()
    for entry in document["openings"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
            raise ValueError("Each opening needs a nonempty string id")
        moves = entry.get("moves", [])
        if not isinstance(moves, list) or any(not isinstance(move, str) for move in moves):
            raise ValueError(f"Opening {entry['id']} needs a list of UCI move strings")
        starting_fen = entry.get("fen", chess.STARTING_FEN)
        if not isinstance(starting_fen, str):
            raise ValueError(f"Opening {entry['id']} FEN must be a string")
        board = chess.Board(starting_fen)
        if not board.is_valid():
            raise ValueError(f"Opening {entry['id']} has an invalid standard-chess FEN")
        root = board.fen()
        for text in moves:
            move = chess.Move.from_uci(text)
            if move not in board.legal_moves:
                raise ValueError(f"Opening {entry['id']} contains illegal move {text}")
            board.push(move)
        if not board.is_valid() or board.outcome(claim_draw=True) is not None:
            raise ValueError(f"Opening {entry['id']} must end in a valid, nonterminal position")
        key = hashlib.sha256(json.dumps({"fen": root, "moves": moves}, sort_keys=True).encode()).hexdigest()
        if entry["id"] in ids or key in keys:
            raise ValueError("Opening ids and normalized opening definitions must be unique")
        ids.add(entry["id"])
        keys.add(key)
        openings.append(Opening(entry["id"], board, key))
    if not openings:
        raise ValueError("Opening suite is empty")
    return document, openings


def plan_pairs(openings, count, seed):
    if not 1 <= count <= len(openings):
        raise ValueError("pairs must be between 1 and the number of distinct suite openings; recycling is disabled")
    generator = random.Random(seed)
    selected = list(openings)
    generator.shuffle(selected)
    return [{"pair_id": f"p{index + 1:06d}", "opening": opening,
             "first_candidate_color": generator.choice(("white", "black"))}
            for index, opening in enumerate(selected[:count])]


def physical_memory():
    try:
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        if sys.platform == "win32":
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in
                    ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.total
        return None


def resource_check(settings, specs):
    """Re-read owner overrides between games; never pause an active chess clock.

    Only one engine searches at a time, but both engines stay resident. Memory is
    a conservative reservation estimate, not an OS-enforced RSS ceiling: four
    times network file bytes plus both hash tables and 256 MiB process overhead.
    """
    policy = current_budget()
    reservation = 2 * settings.hash_mb * 1024**2 + 4 * sum(spec.network.stat().st_size for spec in specs) + 256 * 1024**2
    memory = physical_memory()
    policy.update({"active_search_workers": settings.threads, "resident_engines": 2,
                   "estimated_memory_bytes": reservation, "physical_memory_bytes": memory,
                   "memory_estimate_is_hard_cap": False})
    if settings.threads > policy["max_cpu_workers"]:
        raise ValueError("Requested Threads exceeds the current resource budget; use tools/resources.py to adjust it")
    if memory is not None and reservation > memory * policy["memory_fraction"]:
        raise ValueError("Estimated combined engine memory exceeds the current resource budget")
    return policy



class PersistenceError(OSError):
    """Evidence cannot be completed; never score this as an engine loss."""


class BufferedLog:
    """Bounded FIFO protocol persistence, with no disk work in UCI callbacks.

    A single daemon thread owns the file and every write/flush/close. Queue
    capacity includes the in-flight write, and the accounting lock is never held
    during I/O. Callback admission cannot wait for storage: overflow latches a
    permanent failure. The runner observes that failure while engines are active.
    Flush barriers provide backpressure between searches, never during a clock.

    A stuck OS write cannot safely be interrupted by Python. Barriers/close have
    a deadline and fail the run; a blocked daemon may finish later, so its output
    must remain incomplete and must never be resumed or reused.
    """
    MAX_BYTES = 8 * 1024 * 1024
    MAX_RECORDS = 4096
    TIMEOUT = 30.0

    def __init__(self, path, *, max_bytes=None, max_records=None, timeout=None, opener=None):
        self.path = Path(path)
        self.max_bytes = self.MAX_BYTES if max_bytes is None else max_bytes
        self.max_records = self.MAX_RECORDS if max_records is None else max_records
        self.timeout = self.TIMEOUT if timeout is None else timeout
        if (not isinstance(self.max_bytes, int) or self.max_bytes <= 0
                or not isinstance(self.max_records, int) or self.max_records <= 0
                or not math.isfinite(self.timeout) or self.timeout <= 0):
            raise ValueError("Invalid protocol persistence bounds")
        self.loop = asyncio.get_running_loop()
        self.failure = self.loop.create_future()
        self._ready = self.loop.create_future()
        self._done = self.loop.create_future()
        self._queue = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._error = None
        self._closing = False
        self._draining = False
        self._pending_bytes = 0
        self._pending_records = 0
        self._opener = opener or (lambda path: path.open("x", encoding="utf-8"))
        self._thread = threading.Thread(target=self._worker, name="chess0live-evidence", daemon=True)
        self._thread.start()

    @property
    def error(self):
        with self._lock:
            return self._error

    def _post(self, future, value=None):
        def resolve():
            if not future.done():
                future.set_result(value)
        try:
            self.loop.call_soon_threadsafe(resolve)
        except RuntimeError:
            # A timed-out daemon can return after the failed run's loop closes.
            pass

    def fail(self, error):
        if not isinstance(error, PersistenceError):
            error = PersistenceError(f"Protocol log {self.path.name}: {type(error).__name__}: {error}")
        with self._lock:
            if self._error is None:
                self._error = error
            error = self._error
        self._post(self.failure, error)
        return error

    def write(self, text):
        """Admit one immutable serialized record, or fail without blocking."""
        size = len(text.encode("utf-8"))
        with self._lock:
            error = self._error
            if error is None and self._closing:
                error = PersistenceError("Protocol log is already closing")
            if error is None and (self._pending_bytes + size > self.max_bytes
                                  or self._pending_records + 1 > self.max_records):
                error = PersistenceError("Protocol log queue capacity exceeded; evidence is incomplete")
            if error is None:
                self._pending_bytes += size
                self._pending_records += 1
                self._queue.put(("write", text, size))
        if error is not None:
            raise self.fail(error)
        return len(text)

    async def _wait(self, future):
        try:
            result = await asyncio.wait_for(asyncio.shield(future), self.timeout)
        except asyncio.TimeoutError as error:
            raise self.fail(PersistenceError("Protocol persistence deadline exceeded; evidence is incomplete")) from error
        if isinstance(result, BaseException):
            raise result
        if self.error is not None:
            raise self.error

    async def ready(self):
        await self._wait(self._ready)

    async def drain(self):
        """Flush everything admitted so far before admitting the next search."""
        if self.error is not None:
            raise self.error
        barrier = self.loop.create_future()
        with self._lock:
            if self._draining or self._closing:
                invalid = True
            else:
                invalid = False
                self._draining = True
                self._queue.put(("flush", barrier, 0))
        if invalid:
            raise self.fail(PersistenceError("Overlapping or post-close protocol drain"))
        await self._wait(barrier)

    async def close(self):
        with self._lock:
            if not self._closing:
                self._closing = True
                self._queue.put(("close", None, 0))
        await self._wait(self._done)

    def _worker(self):
        stream = None
        try:
            stream = self._opener(self.path)
            self._post(self._ready)
            while True:
                kind, value, size = self._queue.get()
                if kind == "close":
                    break
                if kind == "write":
                    try:
                        if self.error is None:
                            stream.write(value)
                    except Exception as error:
                        self.fail(error)
                    finally:
                        with self._lock:
                            self._pending_bytes -= size
                            self._pending_records -= 1
                else:
                    try:
                        if self.error is None:
                            stream.flush()
                    except Exception as error:
                        self.fail(error)
                    with self._lock:
                        self._draining = False
                    self._post(value, self.error)
        except Exception as error:
            self.fail(error)
        finally:
            if stream is not None:
                try:
                    if self.error is None:
                        stream.flush()
                except Exception as error:
                    self.fail(error)
                try:
                    stream.close()
                except Exception as error:
                    self.fail(error)
            self._post(self._ready, self.error)
            self._post(self._done, self.error)


async def persistence_guard(awaitable, log):
    """Abort setup/search promptly if its asynchronous evidence writer fails."""
    failure = getattr(log, "failure", None)
    if failure is None:
        return await awaitable
    task = asyncio.ensure_future(awaitable)
    try:
        done, _ = await asyncio.wait((task, failure), return_when=asyncio.FIRST_COMPLETED)
        if failure in done or log.error is not None:
            raise log.error or failure.result()
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


class RecordingProtocol(chess.engine.UciProtocol):
    """Timestamp protocol callback boundaries and preserve every raw line.

    The incoming parser is version-pinned and covered by boundary tests.
    Unlike timing an entire play() call, these boundaries exclude its new-game
    readiness handshake. Receipt is a Python callback observation, not kernel
    arrival; host transport/scheduling latency still remains charged.
    """
    def __init__(self, role, log):
        super().__init__()
        self.role, self.log = role, log
        self.go_ns = None
        self.bestmove_ns = None
        self.go_started = asyncio.Event()
        self.errors = []
        self.stderr_seen = False
        self._received_lines = None

    def record(self, direction, line, stamp):
        try:
            self.log.write(json.dumps({"monotonic_ns": stamp, "engine": self.role,
                                       "direction": direction, "line": line}) + "\n")
        except PersistenceError:
            # BufferedLog has latched the failure. Do not throw from an asyncio
            # pipe callback: the active setup/play guard owns orderly abortion.
            pass

    def send_line(self, line):
        if getattr(self.log, "error", None) is not None and line not in ("stop", "quit"):
            # The async guard will abort the command. Do not launch a new search
            # after an already-known persistence failure; retain cleanup commands.
            return
        stamp = time.monotonic_ns()
        if line == "go" or line.startswith("go "):
            self.go_ns, self.bestmove_ns = stamp, None
            self.go_started.set()
        super().send_line(line)
        self.record("to_engine", line, stamp)

    def pipe_data_received(self, fd, data):
        """Stamp all completed lines before logging or parsing can delay them.

        Let python-chess retain ownership of byte buffering, UTF-8 decoding, and
        CRLF handling. A partial line takes the callback time that completes its
        newline. Pre-record the entire completed batch before dispatch: parsing
        readyok can synchronously send position/go, which must follow the input
        bytes already received. Equal receipt timestamps are intentionally valid.
        This excludes processing within this callback, not earlier loop stalls.
        """
        stamp = time.monotonic_ns()
        lines = []
        self._received_lines = lines
        try:
            super().pipe_data_received(fd, data)
        finally:
            self._received_lines = None
        for direction, line in lines:
            self.record(direction, line, stamp)
        for direction, line in lines:
            self._dispatch_received(direction, line, stamp)

    def _dispatch_received(self, direction, line, stamp):
        """Process an already-recorded complete line at its receipt boundary."""
        if direction == "stderr":
            self.stderr_seen = True
            return
        if line.startswith("bestmove "):
            self.bestmove_ns = stamp
        if line.lower().startswith(("info string error:", "info string search error:")):
            self.errors.append(line)
        super()._line_received(line)

    def _line_received(self, line):
        if self._received_lines is not None:
            self._received_lines.append(("from_engine", line))
            return
        stamp = time.monotonic_ns()
        self.record("from_engine", line, stamp)
        self._dispatch_received("from_engine", line, stamp)

    def error_line_received(self, line):
        if self._received_lines is not None:
            self._received_lines.append(("stderr", line))
            return
        stamp = time.monotonic_ns()
        self.record("stderr", line, stamp)
        self._dispatch_received("stderr", line, stamp)


async def start_engine(spec, settings, log):
    kwargs = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    transport, protocol = await asyncio.get_running_loop().subprocess_exec(
        lambda: RecordingProtocol(spec.role, log), str(spec.executable), *spec.arguments, **kwargs)
    try:
        await persistence_guard(asyncio.wait_for(protocol.initialize(), settings.startup_timeout), log)
        configured = {"Hash": settings.hash_mb, "Threads": settings.threads,
                      spec.network_option: str(spec.network)}
        for name in configured:
            if name not in protocol.options:
                raise ValueError(f"{spec.role} does not advertise required UCI option {name}")
        for name, value in (("OwnBook", False), ("UseBook", False), ("BookFile", ""),
                            ("SyzygyPath", ""), ("GaviotaTbPath", ""),
                            ("UCI_LimitStrength", False), ("UCI_AnalyseMode", False),
                            ("Search Diagnostics", False),
                            ("Move Overhead", settings.move_overhead_ms)):
            if name in protocol.options:
                configured[name] = value
        if "Skill Level" in protocol.options and protocol.options["Skill Level"].max is not None:
            configured["Skill Level"] = protocol.options["Skill Level"].max
        configured.update(experiment_options(spec, protocol, configured))
        await persistence_guard(asyncio.wait_for(protocol.configure(configured), settings.startup_timeout), log)
        await persistence_guard(asyncio.wait_for(protocol.ping(), settings.startup_timeout), log)
        if protocol.errors:
            raise ValueError("; ".join(protocol.errors))
        return transport, protocol, configured
    except BaseException:
        transport.close()
        try:
            await asyncio.wait_for(asyncio.shield(protocol.returncode), 2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        raise


async def finish_cleanup(coroutine):
    """Finish bounded subprocess cleanup, then propagate any late cancellation.

    Cancellation during a normal game's quit must never disappear and permit
    another game to start. Shield a separate task so repeated cancellation also
    cannot strand the second resident engine or interrupt evidence persistence.
    """
    task = asyncio.create_task(coroutine)
    cancelled = False
    try:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        return task.result()
    finally:
        if cancelled:
            raise asyncio.CancelledError


async def close_engine(transport, protocol):
    async def close():
        try:
            await asyncio.wait_for(protocol.quit(), 1.0)
        except Exception:
            transport.close()
        finally:
            transport.close()
            try:
                await asyncio.wait_for(asyncio.shield(protocol.returncode), 1.0)
            except Exception:
                pass
    await finish_cleanup(close())


async def _timed_play(protocol, board, limit, game_id, remaining, settings):
    """Separate protocol readiness from the watchdog on the actual chess clock.

    python-chess sends newgame/isready on each process's first play. Readiness
    gets the setup timeout; only a sent go starts remaining-clock plus response
    grace. Grace permits recording a late reply as a real flag fall, never free
    thinking time. Canceling a pending command sends stop before process cleanup.
    """
    protocol.go_ns, protocol.bestmove_ns = None, None
    protocol.go_started.clear()
    playing = asyncio.create_task(protocol.play(
        board, limit, game=game_id, ponder=False,
        info=chess.engine.INFO_BASIC | chess.engine.INFO_SCORE))
    ready = asyncio.create_task(protocol.go_started.wait())
    try:
        done, _ = await asyncio.wait((playing, ready), timeout=settings.startup_timeout,
                                     return_when=asyncio.FIRST_COMPLETED)
        if playing in done:
            return await playing
        if ready not in done:
            raise asyncio.TimeoutError("Engine did not reach go within setup timeout")
        elapsed = (time.monotonic_ns() - protocol.go_ns) / 1e9
        timeout = max(0.0, remaining + settings.protocol_timeout - elapsed)
        return await asyncio.wait_for(asyncio.shield(playing), timeout)
    finally:
        for task in (playing, ready):
            if not task.done():
                task.cancel()
        await asyncio.gather(playing, ready, return_exceptions=True)


async def timed_play(protocol, board, limit, game_id, remaining, settings):
    return await persistence_guard(
        _timed_play(protocol, board, limit, game_id, remaining, settings), protocol.log)


async def disk_io(function, *args, **kwargs):
    """Keep persistence off the shared loop, finishing issued work on cancel.

    Call only outside this shard's active search. Other shards may be searching,
    so even opening/closing files and PGN formatting run in the worker thread.
    """
    return await finish_cleanup(asyncio.to_thread(function, *args, **kwargs))


def clock_outcome(board, loser):
    """Referee approximation for flag falls: python-chess's side-specific
    insufficient-material test is conservative, not a general helpmate solver.
    """
    winner = not loser
    if board.has_insufficient_material(winner):
        return "1/2-1/2"
    return "1-0" if winner == chess.WHITE else "0-1"


def candidate_score(result, color):
    if result == "1/2-1/2":
        return 0.5
    if result == "*":
        return None
    return float((result == "1-0") == (color == "white"))


def persistence_failure(record, error):
    """Invalidate only this new incomplete record; historical games never change."""
    record.setdefault("persistence_error", str(error))
    record.update(status="persistence_failure", termination="evidence_write_failure",
                  result="*", candidate_score=None)


async def play_game(specs, settings, opening, pair_id, game_id, candidate_color, policy, output, append_record):
    board = opening.board.copy(stack=True)
    game = chess.pgn.Game.from_board(board)
    node = game.end()
    game.headers.update({"Event": "chess0live smoke test" if settings.smoke else "chess0live paired match",
                         "Site": "local", "Date": datetime.now(timezone.utc).strftime("%Y.%m.%d"),
                         "Round": game_id, "White": "candidate" if candidate_color == "white" else "opponent",
                         "Black": "opponent" if candidate_color == "white" else "candidate",
                         "TimeControl": f"{settings.initial:g}+{settings.increment:g}",
                         "OpeningId": opening.identifier, "PairId": pair_id})
    record = {"game_id": game_id, "pair_id": pair_id, "opening_id": opening.identifier,
              "opening_key": opening.key, "candidate_color": candidate_color,
              "started_utc": utc_now(), "status": "interrupted", "result": "*",
              "termination": "interrupted", "resource_policy": policy,
              "opening_plies": len(board.move_stack), "played_plies": 0, "moves": [],
              "engines": {}, "pgn": f"{game_id}.pgn", "protocol_log": f"{game_id}.protocol.jsonl"}
    colors = {chess.WHITE: "candidate" if candidate_color == "white" else "opponent",
              chess.BLACK: "opponent" if candidate_color == "white" else "candidate"}
    clocks = {chess.WHITE: settings.initial, chess.BLACK: settings.initial}
    running = {}
    stage = "setup"
    log = BufferedLog(output / record["protocol_log"])
    persistence_error = None
    try:
        await log.ready()
        for spec in specs:
            transport, engine, configured = await start_engine(spec, settings, log)
            running[spec.role] = (transport, engine)
            record["engines"][spec.role] = {"id": dict(engine.id), "options": configured,
                                            "ponder": False, "pid": transport.get_pid()}
        stage = "play"
        while True:
            outcome = board.outcome(claim_draw=True)
            if outcome is not None:
                record.update(status="complete", result=outcome.result(), termination=outcome.termination.name.lower())
                break
            if record["played_plies"] >= settings.max_plies:
                record.update(status="truncated", termination="max_plies")
                break
            side = board.turn
            role = colors[side]
            protocol = running[role][1]
            event = {"ply": board.ply() + 1, "engine": role,
                     "color": "white" if side else "black", "clock_before": clocks[side]}
            limit = chess.engine.Limit(white_clock=clocks[chess.WHITE], black_clock=clocks[chess.BLACK],
                                       white_inc=settings.increment, black_inc=settings.increment)
            # This shard has no running chess clock here. Await durable log
            # progress before go, while other shards retain the event loop.
            await log.drain()
            try:
                played = await timed_play(protocol, board, limit, game_id, clocks[side], settings)
            except asyncio.TimeoutError:
                record.update(status="protocol_timeout", termination="no_bestmove" if protocol.go_ns is not None else "not_ready_for_go",
                              failed_engine=role)
                if protocol.go_ns is not None:
                    event["elapsed_seconds"] = (time.monotonic_ns() - protocol.go_ns) / 1e9
                record["moves"].append(event)
                break
            except chess.engine.EngineError as error:
                record.update(status="protocol_failure", termination="invalid_engine_response",
                              failed_engine=role, error=str(error))
                record["moves"].append(event)
                break
            if protocol.go_ns is None or protocol.bestmove_ns is None:
                raise RuntimeError("Missing clock boundary in UCI transcript")
            elapsed = (protocol.bestmove_ns - protocol.go_ns) / 1e9
            event.update(elapsed_seconds=elapsed, move=played.move.uci() if played.move else None)
            if protocol.errors or played.move is None or not board.is_legal(played.move):
                record.update(status="protocol_failure", termination="illegal_or_failed_move",
                              failed_engine=role, error="; ".join(protocol.errors) or "Missing/illegal bestmove")
                record["moves"].append(event)
                break
            # Increment is earned only by an on-time legal move. An over-clock
            # reply is evidence, not a move pushed onto the game board or PGN.
            if elapsed > clocks[side]:
                clocks[side] -= elapsed
                event.update(clock_after=clocks[side], played=False)
                record["moves"].append(event)
                record.update(status="complete", termination="time_forfeit",
                              result=clock_outcome(board, side), clock_loser=role)
                break
            clocks[side] = clocks[side] - elapsed + settings.increment
            event.update(clock_after=clocks[side], played=True,
                         search={key: played.info[key] for key in ("depth", "seldepth", "nodes") if key in played.info})
            record["moves"].append(event)
            board.push(played.move)
            node = node.add_variation(played.move)
            node.set_clock(clocks[side])
            record["played_plies"] += 1
    except asyncio.CancelledError:
        record.update(status="interrupted", termination="runner_interrupted")
        raise
    except PersistenceError as error:
        persistence_error = error
        persistence_failure(record, error)
    except Exception as error:
        record.update(status="setup_failure" if stage == "setup" else "protocol_failure",
                      termination="engine_setup" if stage == "setup" else "runner_error", error=str(error))
    finally:
        async def close_all():
            for transport, protocol in running.values():
                await close_engine(transport, protocol)
        cleanup_cancelled = False
        try:
            await finish_cleanup(close_all())
        except asyncio.CancelledError:
            cleanup_cancelled = True
        # Drain/close before publishing a game outcome. Missing protocol bytes
        # invalidate the game even if a legal bestmove was already received.
        try:
            await finish_cleanup(log.close())
        except asyncio.CancelledError:
            cleanup_cancelled = True
        except PersistenceError as error:
            persistence_error = error
            persistence_failure(record, error)
        if log.error is not None:
            persistence_error = log.error
            persistence_failure(record, log.error)
        record.update(finished_utc=utc_now(), final_fen=board.fen(),
                      candidate_score=candidate_score(record["result"], candidate_color),
                      clocks={"white": clocks[chess.WHITE], "black": clocks[chess.BLACK]})
        if any(getattr(protocol, "stderr_seen", False) for _, protocol in running.values()):
            record["unexpected_stderr"] = True

        def persist_game():
            # The game tree and record no longer mutate on the event loop. PGN
            # formatting, file writes, the journal and summary all stay off it.
            game.headers["Result"] = record["result"]
            game.headers["Termination"] = record["termination"]
            node.comment = (node.comment + " " + record["status"] + ": " + record["termination"]).strip()
            failure = None
            try:
                (output / record["pgn"]).write_text(str(game) + "\n\n", encoding="utf-8")
            except Exception as error:
                failure = PersistenceError(f"PGN persistence failed: {error}")
                persistence_failure(record, failure)
            # Attempt the failure record once even if the separate PGN failed;
            # a full/unavailable disk may also prevent this best-effort record.
            try:
                append_record(record)
            except Exception as error:
                failure = PersistenceError(f"Game journal/summary persistence failed: {error}")
                persistence_failure(record, failure)
            if failure is not None:
                raise failure

        try:
            await disk_io(persist_game)
        except asyncio.CancelledError:
            cleanup_cancelled = True
        except PersistenceError as error:
            persistence_error = error
        if record["status"] == "persistence_failure" and persistence_error is None:
            persistence_error = PersistenceError(record["persistence_error"])
        if persistence_error is not None:
            raise persistence_error
        if cleanup_cancelled:
            raise asyncio.CancelledError
    return record


def pair_records(plan, records):
    return [{"pair_id": pair["pair_id"], "opening_key": pair["opening"].key,
             "games": [record for record in records if record["pair_id"] == pair["pair_id"]]}
            for pair in plan]


def summary(plan, records, complete, smoke):
    result = summarize_pairs(pair_records(plan, records), experiment_complete=complete)
    if smoke:
        result["inference_eligible"] = False
        result["uncertainty"]["withheld_reasons"].append("smoke_run_not_a_strength_experiment")
        for key in ("radius", "score_interval", "relative_elo_interval"):
            result["uncertainty"][key] = None
    result.update(experiment_complete=complete, smoke=smoke)
    return result


async def run_match(specs, settings, suite_path, output, pairs, seed, *, before_game=None, fail_fast=False):
    """Run the fixed schedule, optionally under an aggregate campaign guard.

    The async guard receives the next game ID before any engine is started.
    Existing standalone protocols retain their historical continue-and-record
    behavior; coordinated campaigns may stop after a recorded invalid game.
    A completed clock forfeit is a valid scored result, never an invalid game.
    """
    settings.validate()
    if chess.__version__ != SUPPORTED_CHESS_VERSION:
        raise ValueError(f"This runner is verified with chess=={SUPPORTED_CHESS_VERSION}; installed {chess.__version__}")
    suite_contents = await asyncio.to_thread(suite_path.read_bytes)
    document, openings = read_openings(suite_path, suite_contents)
    plan = plan_pairs(openings, pairs, seed)
    if await asyncio.to_thread(lambda: output.exists() and any(output.iterdir())):
        raise ValueError("Output directory must be new or empty; existing results are never overwritten")
    def artifact_snapshot():
        return {spec.role: spec.artifacts() for spec in specs}

    # Any shard may share its loop with another live chess clock. All storage
    # and environment observations stay off that loop, even before this shard's
    # own first engine starts. Calls are awaited, so there is no I/O task backlog.
    async def artifacts():
        return await asyncio.to_thread(artifact_snapshot)

    frozen = await artifacts()
    await asyncio.to_thread(resource_check, settings, specs)
    await disk_io(output.mkdir, parents=True, exist_ok=True)
    await disk_io((output / "openings.json").write_bytes, suite_contents)
    source_paths = tuple(ROOT / "tools" / name for name in
                         ("match.py", "match_statistics.py", "resources.py"))
    sources = await asyncio.to_thread(lambda: [
        {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in source_paths])
    environment = await asyncio.to_thread(lambda: (platform.platform(), platform.machine()))
    manifest = {"schema_version": 1, "started_utc": utc_now(), "status": "running",
                "platform": environment[0], "machine": environment[1],
                "python": sys.version, "chess_version": chess.__version__,
                "seed": seed, "planned_pairs": pairs, "settings": vars(settings),
                "engines": {spec.role: {"executable": str(spec.executable), "arguments": list(spec.arguments),
                                        "network": str(spec.network), "network_option": spec.network_option,
                                        "experiment_options": dict(spec.extra_options),
                                        "source_revision": {"label": spec.source_revision, "verified_against_binary": False},
                                        "artifacts": frozen[spec.role]} for spec in specs},
                "runner_sources": sources,
                "persistence": {"protocol_writer": "bounded single-thread FIFO per game",
                                "max_pending_bytes": BufferedLog.MAX_BYTES,
                                "max_pending_records": BufferedLog.MAX_RECORDS,
                                "deadline_seconds": BufferedLog.TIMEOUT,
                                "bounds_include_in_flight": True,
                                "overflow_or_write_error": "abort run; evidence incomplete",
                                "drain_boundary": "before next search and game publication",
                                "flush_is_fsync": False},
                "opening_suite": {"path": str(suite_path), "sha256": hashlib.sha256(suite_contents).hexdigest(),
                                  "frozen_copy": "openings.json",
                                  "description": document.get("description", "")},
                "plan": [{"pair_id": pair["pair_id"], "opening_id": pair["opening"].identifier,
                          "opening_key": pair["opening"].key,
                          "starting_fen": pair["opening"].board.root().fen(),
                          "moves": [move.uci() for move in pair["opening"].board.move_stack],
                          "first_candidate_color": pair["first_candidate_color"]} for pair in plan],
                "referee": {"draw_claims": "automatic when available to side to move",
                            "clock": "monotonic outgoing go to callback receipt completing bestmove; transport/scheduling latency charged, within-callback processing excluded",
                            "flag_fall_material": "python-chess has_insufficient_material(winner); conservative, not full helpmate proof",
                            "truncation": "excluded, never scored as a draw", "evaluation_adjudication": False,
                            "process_cleanup": "Direct engine subprocess; executable wrappers must exec their engine, not leave child processes."},
                "interpretation": "Fixed-sample paired comparison; no universal or absolute Elo claim."}
    def checkout_metadata():
        result = {}
        for key, command in (("runner_checkout_commit", ["git", "rev-parse", "HEAD"]),
                             ("runner_checkout_status", ["git", "status", "--porcelain"])):
            git = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            result[key] = git.stdout.strip() if git.returncode == 0 else None
        return result
    manifest.update(await asyncio.to_thread(checkout_metadata))
    await disk_io(atomic_json, output / "run.json", manifest)
    records = []
    journal = None
    def open_journal():
        # Store ownership before a cancelled async caller can lose the result.
        nonlocal journal
        journal = (output / "games.jsonl").open("w", encoding="utf-8")

    def append_record(record):
        records.append(record)
        journal.write(json.dumps(record, allow_nan=False) + "\n")
        journal.flush()
        atomic_json(output / "summary.json", summary(plan, records, False, settings.smoke))

    try:
        await disk_io(open_journal)
        for pair in plan:
            first = pair["first_candidate_color"]
            for leg, color in enumerate((first, "black" if first == "white" else "white"), start=1):
                game_id = f"{pair['pair_id']}-{leg}"
                if before_game is not None:
                    await before_game(game_id)
                policy = await asyncio.to_thread(resource_check, settings, specs)
                if await artifacts() != frozen:
                    raise ValueError("Frozen executable/network/script changed during the experiment")
                record = await play_game(specs, settings, pair["opening"], pair["pair_id"], game_id,
                                         color, policy, output, append_record)
                if fail_fast and (record["status"] != "complete" or record.get("unexpected_stderr")):
                    reason = "unexpected engine stderr" if record.get("unexpected_stderr") else record["termination"]
                    raise ValueError(f"Invalid game {game_id}: {record['status']}: {reason}")
        # A modification during the last game must not escape the next-game
        # checks merely because the predeclared schedule has just ended.
        if await artifacts() != frozen:
            raise ValueError("Frozen executable/network/script changed during the experiment")
        manifest["status"] = "finished"
    except BaseException as error:
        manifest.update(status="interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        complete = manifest["status"] == "finished"
        manifest["finished_utc"] = utc_now()
        def publish_final():
            if journal is not None:
                journal.close()
            # Publish completion last. If a summary write fails, run.json still
            # says running/interrupted rather than claiming durable completion.
            atomic_json(output / "summary.json", summary(plan, records, complete, settings.smoke))
            atomic_json(output / "run.json", manifest)
        try:
            await disk_io(publish_final)
        except BaseException as error:
            manifest.update(status="interrupted", error=f"{type(error).__name__}: {error}")
            # This is one best-effort failure marker, never a retry of a game.
            # A completely unavailable disk can prevent even this marker; the
            # exception still propagates and no subsequent game is admitted.
            def publish_failure():
                failure = None
                try:
                    if journal is not None:
                        journal.close()
                except Exception as closing_error:
                    failure = closing_error
                # Try both independently: a damaged run.json must not prevent
                # replacing an otherwise writable completed summary as invalid.
                for path, value in ((output / "run.json", manifest),
                                    (output / "summary.json", summary(plan, records, False, settings.smoke))):
                    try:
                        atomic_json(path, value)
                    except Exception as write_error:
                        failure = write_error
                if failure is not None:
                    raise failure
            await disk_io(publish_failure)
            raise
    return summary(plan, records, True, settings.smoke)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ("candidate", "opponent"):
        parser.add_argument(f"--{role}", required=True, type=Path, help="Explicit executable path")
        parser.add_argument(f"--{role}-network", required=True, type=Path)
        parser.add_argument(f"--{role}-network-option", default="EvalFile")
        parser.add_argument(f"--{role}-arg", action="append", default=[], help="Optional executable argument; wrapper processes must exec their engine")
        parser.add_argument(f"--{role}-revision", help="Optional source revision label; not independently verified against binary")
        parser.add_argument(f"--{role}-option", action="append", default=[], metavar="NAME=VALUE",
                            help="Repeatable advertised experiment option; common match settings cannot be overridden")
    parser.add_argument("--openings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pairs", required=True, type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--initial", required=True, type=float, help="Initial seconds per side")
    parser.add_argument("--increment", required=True, type=float, help="Seconds earned per on-time move")
    parser.add_argument("--hash-mb", type=int, default=64)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--max-plies", type=int, default=512, help="Cap engine-played plies; capped games are excluded")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--protocol-timeout", type=float, default=5.0, help="Response watchdog grace after clock expiration; not free thinking time")
    parser.add_argument("--move-overhead-ms", type=int, default=20)
    parser.add_argument("--smoke", action="store_true", help="Mark a short operational check; disable strength inference")
    args = parser.parse_args()
    settings = Settings(**{name: getattr(args, name) for name in Settings.__dataclass_fields__})
    try:
        specs = [EngineSpec(role, getattr(args, role).resolve(), getattr(args, role + "_network").resolve(),
                            getattr(args, role + "_network_option"), tuple(getattr(args, role + "_arg")),
                            getattr(args, role + "_revision"), parse_options(getattr(args, role + "_option")))
                 for role in ("candidate", "opponent")]
        result = asyncio.run(run_match(specs, settings, args.openings.resolve(), args.output.resolve(), args.pairs, args.seed))
        print(json.dumps(result, indent=2, allow_nan=False))
        failures = sum(count for status, count in result["game_status_counts"].items()
                       if status not in ("complete", "truncated"))
        return 1 if failures else 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"Match configuration/run error: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Match interrupted; completed games and the current game record were preserved.\n")


if __name__ == "__main__":
    raise SystemExit(main())
