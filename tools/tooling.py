"""Isolated, pinned Python setup shared by external tools, never by the engine.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("python-packages.json")
SCHEMA = 1


class ToolingError(RuntimeError):
    """A setup failure that can be explained without an internal traceback."""


def environment_key(manifest_bytes: bytes) -> str:
    """Separate incompatible interpreters, platforms, manifests and layouts."""
    identity = (SCHEMA, sys.version, str(Path(sys._base_executable).resolve()),
                platform.system(), platform.machine(), str(ROOT))
    return hashlib.sha256(repr(identity).encode() + manifest_bytes).hexdigest()[:24]


def python_path(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


@contextmanager
def setup_lock(path: Path, timeout: float = 120):
    """Serialize setup; kernel-owned locks are released even after a killed run.

    Keep the lock file in place: unlinking a locked inode would let new callers
    lock a different file while the first caller still owns the original one.
    """
    with path.open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"\0")
            lock.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise ToolingError("Another tool is still setting up Python. Retry shortly.") from error
                time.sleep(0.1)
        try:
            yield lock.fileno()
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_asset(asset: dict, directory: Path, offline: bool = False) -> Path:
    """Reuse only hash-matching archives; never publish a partial download."""
    filename = asset["filename"]
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ToolingError("Invalid package filename in the tooling manifest.")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.is_file() and digest(destination) == asset["sha256"]:
        return destination
    if offline:
        raise ToolingError(f"Offline setup needs the pinned archive {filename}. "
                           "Run once with Internet access to populate this cache.")
    if not asset["url"].startswith("https://files.pythonhosted.org/"):
        raise ToolingError("Package URL must use the pinned PyPI archive host.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(asset["url"], timeout=30) as response:
                shutil.copyfileobj(response, output)
        if digest(temporary) != asset["sha256"]:
            raise ToolingError(f"Checksum mismatch for {filename}; nothing was installed.")
        temporary.replace(destination)
        return destination
    except (OSError, HTTPException) as error:
        raise ToolingError(f"Could not download {filename}: {error}. "
                           "Check your connection and retry; completed downloads are reusable.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def healthy(directory: Path, key: str, packages: list[dict]) -> bool:
    """Check the ready marker, imports, versions and isolation before reuse."""
    try:
        if ((directory / "ready").read_text() != key
                or (directory / "chess0live-owner").read_text() != key):
            return False
        versions = {asset["name"]: asset["version"] for asset in packages}
        code = ("import sys, pathlib, importlib.metadata as m; import chess, chess.engine, chess.pgn; "
                "assert sys.prefix != sys.base_prefix; "
                f"assert pathlib.Path(sys.prefix).resolve() == pathlib.Path({str(directory)!r}).resolve(); "
                f"assert {{name: m.version(name) for name in {list(versions)!r}}} == {versions!r}; "
                "assert chess.__version__ == m.version('chess')")
        return subprocess.run([str(python_path(directory)), "-I", "-c", code],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def setup_command(command: list[str], *, log, lock_fd: int, env=None, timeout=120):
    """Bound installers and retain the setup lock until their process exits.

    On POSIX each installer has its own process group; cancellation/timeout also
    stops its build/ensurepip descendants. The inherited lock keeps a second
    setup out if the parent is killed before cleanup can run. On Windows the
    direct child is bounded; native process-tree cancellation needs qualification.
    """
    options = {"pass_fds": (lock_fd,), "start_new_session": True} if os.name != "nt" else {}
    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, **options)
    previous = None
    if os.name != "nt" and threading.current_thread() is threading.main_thread():
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        status = process.wait(timeout=timeout)
        if status:
            raise subprocess.CalledProcessError(status, command)
    except BaseException:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def ensure_environment(offline: bool = False, cache: Path | None = None) -> Path:
    """Return a working managed interpreter, repairing incomplete setup locally.

    No activation, system pip install or global configuration changes are used.
    Downloads are pinned, and pip sees only those local archives. The pure-Python
    chess source package builds using the separately pinned build tools. Copied
    interpreters preserve isolation for callers resolving sys.executable.
    """
    if sys.version_info < (3, 10):
        raise ToolingError("Python 3.10 or newer with venv/ensurepip is required.")
    offline = offline or os.environ.get("CHESS0LIVE_TOOL_OFFLINE") == "1"
    cache = Path(cache or os.environ.get("CHESS0LIVE_TOOL_CACHE", ROOT / ".local/tooling")).expanduser().resolve()
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != SCHEMA:
        raise ToolingError("Unsupported Python package manifest schema.")
    packages = manifest["packages"]
    key = environment_key(manifest_bytes)
    directory = cache / ("env-" + key)
    if healthy(directory, key, packages):
        return python_path(directory)
    cache.mkdir(parents=True, exist_ok=True)
    with setup_lock(cache / "setup.lock") as lock_fd:
        if healthy(directory, key, packages):
            return python_path(directory)
        print("Preparing chess0live Python tools (isolated local environment)...", file=sys.stderr, flush=True)
        # Fetch before touching a previous environment. Failed or offline setup
        # leaves existing files alone; only our explicitly owned directory is rebuilt.
        archives = [(asset, download_asset(asset, cache / "downloads", offline)) for asset in packages]
        owner = directory / "chess0live-owner"
        if directory.exists():
            if directory.is_symlink() or not owner.is_file() or owner.read_text() != key:
                raise ToolingError(f"Refusing to replace an unowned environment: {directory}")
            shutil.rmtree(directory)
        directory.mkdir()
        owner.write_text(key)
        log_path = cache / ("setup-" + key + ".log")
        try:
            # venv/ensurepip bootstraps pip from the installed Python, offline.
            # No activation-script paths are relied on, including on Windows.
            with log_path.open("w", encoding="utf-8") as log:
                command = [sys.executable, "-I", "-m", "venv", "--copies", str(directory)]
                setup_command(command, log=log, lock_fd=lock_fd)
                python = python_path(directory)
                # Ignore global pip settings and Python import overrides. Pinning
                # build tools plus --no-build-isolation prevents hidden downloads.
                install_env = {name: value for name, value in os.environ.items()
                               if not name.startswith(("PIP_", "PYTHON"))}
                install_env["PIP_CONFIG_FILE"] = os.devnull
                for stage in ("build", "runtime"):
                    requirements = directory / (stage + ".txt")
                    requirements.write_text("".join(
                        f"{path.as_uri()} --hash=sha256:{asset['sha256']}\n"
                        for asset, path in archives if asset["stage"] == stage), encoding="utf-8")
                    command = [str(python), "-I", "-m", "pip", "--disable-pip-version-check",
                               "install", "--no-index", "--no-deps", "--no-build-isolation",
                               "--no-cache-dir", "--require-hashes", "-r", str(requirements)]
                    setup_command(command, env=install_env, log=log, lock_fd=lock_fd)
            (directory / "ready").write_text(key)
            if not healthy(directory, key, packages):
                raise ToolingError("Installed package validation failed.")
        except (OSError, subprocess.SubprocessError, ToolingError) as error:
            (directory / "ready").unlink(missing_ok=True)
            raise ToolingError(f"Python tool setup did not finish. See {log_path}. "
                               "If venv/ensurepip is missing, install your OS's Python venv component. "
                               "Retry the same command; partial setup is repaired automatically.") from error
        print("Python tools ready; future runs reuse this environment.", file=sys.stderr, flush=True)
        return python_path(directory)


def run_script(script: Path, args: list[str], offline: bool = False,
               replace_process: bool = False) -> int:
    """Use ordinary script execution: preserve argv, cwd, streams and exit code."""
    script = Path(script).expanduser().resolve()
    if not script.is_file() or script.suffix != ".py":
        raise ToolingError(f"Expected an existing Python script: {script}")
    python = ensure_environment(offline=offline)
    # Prevent parent PYTHONPATH/HOME from defeating isolation. Script directory
    # imports still work because Python is invoked normally, without -I here.
    env = {name: value for name, value in os.environ.items() if not name.startswith("PYTHON")}
    env["PYTHONNOUSERSITE"] = "1"
    command = [str(python), str(script), *args]
    # POSIX CLI use replaces the launcher, preserving its PID and signal/exit
    # behavior. Supervisors stopping that PID then stop the actual tool.
    if replace_process and os.name != "nt":
        os.execve(str(python), command, env)
    status = subprocess.call(command, env=env)
    return 128 - status if status < 0 else status


def direct_entry(script: str) -> None:
    """Bootstrap a direct CLI invocation once, without side effects on import."""
    # A managed child already has the exact pinned runtime. Checking the prefix
    # and distribution avoids a recursion flag that could mask a broken install.
    import importlib.metadata
    try:
        manifest_bytes = MANIFEST.read_bytes()
        expected = next(asset["version"] for asset in json.loads(manifest_bytes)["packages"]
                        if asset["name"] == "chess")
        managed = ((Path(sys.prefix) / "chess0live-owner").read_text()
                   == environment_key(manifest_bytes)
                   and importlib.metadata.version("chess") == expected)
    except (OSError, importlib.metadata.PackageNotFoundError):
        managed = False
    if not managed:
        try:
            raise SystemExit(run_script(Path(script), sys.argv[1:], replace_process=True))
        except (ToolingError, OSError) as error:
            raise SystemExit(f"Tool setup: {error}") from error
        except KeyboardInterrupt:
            raise SystemExit("\nStopped.")
