#!/usr/bin/env python3
"""Small original UCI process harness for bounded local tests and benchmarks.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
import queue
import subprocess
import threading
import time


class Engine:
    """Own a child engine and read complete lines without blocking deadlines."""
    def __init__(self, path, cwd=None, env=None):
        self.process = subprocess.Popen([str(path)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1, cwd=cwd, env=env)
        self.lines = queue.Queue()
        self.transcript = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line.rstrip())
        self.lines.put(None)

    def send(self, command):
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def until(self, prefix, timeout=30):
        deadline = time.monotonic() + timeout
        received = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {prefix}: {received[-10:]}")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as error:
                raise TimeoutError(f"Timed out waiting for {prefix}") from error
            if line is None:
                raise RuntimeError(f"Engine exited before {prefix}: {received[-10:]}")
            self.transcript.append(line)
            received.append(line)
            if line.startswith(prefix):
                return received

    def handshake(self):
        self.send("uci")
        result = self.until("uciok")
        self.send("isready")
        self.until("readyok")
        return result

    def close(self):
        if self.process.poll() is None:
            try:
                self.send("quit")
                self.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        self.reader.join(timeout=1)
        self.process.stdin.close()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
