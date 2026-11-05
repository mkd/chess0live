#!/usr/bin/env python3
"""Preserve byte-exact macOS power evidence before decoding it for inspection.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

pmset can emit bytes that are not UTF-8. Raw stdout and stderr are authoritative;
human-readable text escapes invalid bytes with UTF-8 backslashreplace. This
module collects evidence only and never starts, stops or configures an engine.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess

PMSET = "/usr/bin/pmset"
HOST_TIMEOUT_SECONDS = 15
LOG_TIMEOUT_SECONDS = 30
DECODING = "utf-8 with backslashreplace; raw stdout/stderr files retain original bytes"
EVENT_PATTERN = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) ([+-]\d{4})\s+(.*)")
EVENT_WORD = re.compile(r"\b(Sleep|Wake|DarkWake|Hibernate|Start)\b", re.I)


class PowerEvidenceError(RuntimeError):
    """A failed command or relevant event parse, with its preserved receipt."""

    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def _bytes(value):
    if value is None:
        return b""
    if not isinstance(value, bytes):
        raise TypeError("Power commands must be captured as raw bytes")
    return value


def _text(value):
    return value.decode("utf-8", errors="backslashreplace")


def _is_utf8(value):
    try:
        value.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return True


def _write_bytes(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def _write_text(path, data):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(data)


def _write_json(path, value):
    _write_text(path, json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n")


def _capture(directory, stem, args, timeout):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    names = {"stdout_file": stem + ".stdout.bin", "stderr_file": stem + ".stderr.bin",
             "command_receipt_file": stem + ".command.json"}
    for name in names.values():
        if (directory / name).exists():
            raise FileExistsError("Existing power evidence must be preserved: " + str(directory / name))
    command = [PMSET, "-g", *args]
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    failure = None
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        stdout, stderr, exit_code = _bytes(result.stdout), _bytes(result.stderr), result.returncode
        if exit_code != 0:
            failure = f"pmset {' '.join(args)} exited {exit_code}"
    except subprocess.TimeoutExpired as error:
        stdout, stderr, exit_code = _bytes(error.stdout), _bytes(error.stderr), None
        failure = f"pmset {' '.join(args)} timed out after {timeout} seconds"
    except OSError as error:
        stdout, stderr, exit_code = b"", b"", None
        failure = f"{type(error).__name__}: {error}"
    _write_bytes(directory / names["stdout_file"], stdout)
    _write_bytes(directory / names["stderr_file"], stderr)
    receipt = dict(command=command, started_utc=started,
                   finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                   timeout_seconds=timeout, exit_code=exit_code, **names,
                   stdout_bytes=len(stdout), stderr_bytes=len(stderr),
                   stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest(),
                   stdout_valid_utf8=_is_utf8(stdout), stderr_valid_utf8=_is_utf8(stderr),
                   decoding=DECODING, status="failed" if failure else "complete")
    if failure:
        receipt["error"] = failure
    _write_json(directory / names["command_receipt_file"], receipt)
    return stdout, stderr, receipt


def host(directory, label):
    """Collect bounded battery/power/thermal/assertions snapshots into directory.

    The historical label-name.txt filenames contain stdout followed by stderr.
    Command failures preserve all available bytes and text, then raise; missing
    output must never masquerade as an empty successful observation.
    """
    directory = Path(directory)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        raise ValueError("Power snapshot label must be a simple filename component")
    receipt = {}
    for name, args in (("battery", ["batt"]), ("power", ["custom"]),
                       ("thermal", ["therm"]), ("assertions", ["assertions"])):
        stem = f"{label}-{name}"
        if (directory / (stem + ".txt")).exists():
            raise FileExistsError("Existing power snapshot must be preserved: " + stem)
        stdout, stderr, entry = _capture(directory, stem, args, HOST_TIMEOUT_SECONDS)
        entry = dict(entry, file=stem + ".txt")
        _write_text(directory / entry["file"], _text(stdout) + _text(stderr))
        receipt[name] = entry
        if entry["status"] != "complete":
            raise PowerEvidenceError(entry["error"], receipt)
    return receipt


def sleep_events(directory, start, end):
    """Preserve full pmset log bytes and select the historical event categories.

    Datetimes must be timezone-aware. Selection includes both endpoints and
    keeps the old Sleep/Wake/DarkWake/Hibernate/Start word filter, including
    assertions mentioning those words. Callers must distinguish actual sleep.
    """
    directory = Path(directory)
    if (not isinstance(start, dt.datetime) or not isinstance(end, dt.datetime)
            or start.utcoffset() is None or end.utcoffset() is None or end < start):
        raise ValueError("Sleep evidence requires an ordered timezone-aware interval")
    for filename in ("sleep-log.txt", "sleep-log-stderr.txt", "sleep-wake-events.txt", "sleep-events.json"):
        if (directory / filename).exists():
            raise FileExistsError("Existing sleep evidence must be preserved: " + filename)
    stdout, stderr, receipt = _capture(directory, "sleep-log", ["log"], LOG_TIMEOUT_SECONDS)
    text = _text(stdout)
    _write_text(directory / "sleep-log.txt", text)
    _write_text(directory / "sleep-log-stderr.txt", _text(stderr))
    selected, malformed = [], []
    for index, line in enumerate(text.splitlines(), 1):
        match = EVENT_PATTERN.match(line)
        if not match or not EVENT_WORD.search(match[3]):
            continue
        try:
            when = dt.datetime.strptime(match[1] + " " + match[2], "%Y-%m-%d %H:%M:%S %z")
        except ValueError as error:
            malformed.append(dict(line_number=index, line=line, error=str(error)))
            continue
        if start <= when <= end:
            selected.append(line)
    _write_text(directory / "sleep-wake-events.txt", "\n".join(selected) + ("\n" if selected else ""))
    receipt.update(events=selected, start_utc=start.astimezone(dt.timezone.utc).isoformat(),
                   end_utc=end.astimezone(dt.timezone.utc).isoformat(), malformed_relevant_lines=malformed,
                   text_file="sleep-log.txt", stderr_text_file="sleep-log-stderr.txt",
                   events_file="sleep-wake-events.txt",
                   note="Selected sleep/wake/hibernate/start records within observed interval; review actual sleep separately from assertions.")
    if malformed:
        receipt.update(status="failed", error="Malformed timestamp on a potentially relevant sleep-log event")
    _write_json(directory / "sleep-events.json", receipt)
    if receipt["status"] != "complete":
        raise PowerEvidenceError(receipt["error"], receipt)
    return receipt
