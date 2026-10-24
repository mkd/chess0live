#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Prepare an isolated, pinned CPU/MPS trainer runtime without system installs.

The SF19 trainer requires Python 3.12 and NumPy 1.x. Select a compatible local
interpreter or provision the manifest's standalone distribution. Current artifact
locks cover macOS ARM64; unsupported hosts fail before downloading anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse

from toolchain_cache import extract_archive
from tooling import ToolingError, python_path, setup_command, setup_lock

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("training-packages.json")
OWNER = "chess0live-training-owner.json"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def host_name() -> str:
    system = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system(), "unknown")
    machine = {"aarch64": "arm64", "arm64": "arm64", "AMD64": "x86_64", "x86_64": "x86_64"}.get(platform.machine(), platform.machine())
    return system + "-" + machine


def load_manifest() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("python_version") != [3, 12]:
        raise ToolingError("Unsupported training runtime manifest")
    return data


def plan_training_environment() -> dict:
    """Describe availability and pinned download sizes without modifying state."""
    data = load_manifest()
    host = host_name()
    target = data["platforms"].get(host)
    return {"host": host, "supported": target is not None,
            "python_version": "3.12", "manifest_sha256": checksum(MANIFEST),
            "package_count": len(target["packages"]) if target else 0,
            "package_download_bytes": sum(a["size"] for a in target["packages"]) if target else 0,
            "standalone_python_available": host in data["python_fallbacks"],
            "scope": "Runtime availability only; not a trained-network or hardware acceptance result"}


def fetch_asset(asset: dict, directory: Path, offline: bool) -> Path:
    """Stage complete artifacts; hash/size checks also apply on cache reuse."""
    name = asset["filename"]
    if Path(name).name != name or any(c in name for c in "/\\:"):
        raise ToolingError("Invalid training archive filename")
    url = asset["url"]
    allowed = (url.startswith("https://files.pythonhosted.org/")
               or url.startswith("https://github.com/astral-sh/python-build-standalone/releases/download/"))
    if not allowed or urlparse(url).scheme != "https":
        raise ToolingError("Unapproved training artifact source")
    destination = directory / name
    directory.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == asset["size"] and checksum(destination) == asset["sha256"]:
        return destination
    if offline:
        raise ToolingError("Offline training setup needs the pinned artifact " + name)
    temporary = None
    try:
        print("Downloading training dependency " + name, file=sys.stderr, flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "chess0live-training-setup"})
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as sink:
            temporary = Path(sink.name)
            size = 0
            with urllib.request.urlopen(request, timeout=30) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(block)
                    if size > asset["size"]:
                        raise ToolingError("Training archive exceeds its pinned size: " + name)
                    sink.write(block)
        if temporary.stat().st_size != asset["size"] or checksum(temporary) != asset["sha256"]:
            raise ToolingError("Training archive size/hash mismatch: " + name)
        temporary.replace(destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def interpreter_info(executable: str) -> dict | None:
    """Probe the actual interpreter, never infer compatibility from its name."""
    try:
        result = subprocess.run([executable, "-I", "-c",
            "import json,sys,platform; print(json.dumps({'version':list(sys.version_info[:2]),"
            "'implementation':sys.implementation.name,'system':platform.system(),'machine':platform.machine(),"
            "'executable':sys.executable,'full_version':sys.version}))"],
            capture_output=True, text=True, timeout=15)
        info = json.loads(result.stdout)
        if (result.returncode or info["version"] != [3, 12] or info["implementation"] != "cpython"
                or info["system"] != platform.system()
                or info["machine"].lower() not in ({"arm64", "aarch64"} if host_name().endswith("arm64") else {"amd64", "x86_64"})):
            return None
        return info
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return None


def select_interpreter(data: dict, cache: Path, offline: bool) -> tuple[Path, dict]:
    """Respect an explicit override; otherwise use local 3.12 or a pinned bundle."""
    explicit = os.environ.get("CHESS0LIVE_TRAINING_PYTHON")
    candidates = [explicit] if explicit else [sys.executable, shutil.which("python3.12")]
    for candidate in candidates:
        if candidate and (info := interpreter_info(str(candidate))):
            return Path(info["executable"]).absolute(), info
    if explicit:
        raise ToolingError("CHESS0LIVE_TRAINING_PYTHON must name a native CPython 3.12 executable")
    asset = data["python_fallbacks"].get(host_name())
    if not asset:
        raise ToolingError("Install Python 3.12 or set CHESS0LIVE_TRAINING_PYTHON to its executable")
    directory = cache / ("python-" + asset["sha256"][:16])
    expected = {"schema": 1, "asset": asset}
    owned = False
    if directory.exists() or directory.is_symlink():
        try:
            owned = not directory.is_symlink() and json.loads((directory / OWNER).read_text()) == expected
        except (OSError, ValueError):
            pass
        if not owned:
            raise ToolingError("Refusing to replace an unowned training Python directory: " + str(directory))
        if info := interpreter_info(str(directory / "bin/python3.12")):
            return directory / "bin/python3.12", info
    archive = fetch_asset(asset, cache / "archives", offline)
    with tempfile.TemporaryDirectory(dir=cache, prefix=".python-staging-") as staging:
        extracted = extract_archive(archive, Path(staging), asset["root"])
        (extracted / OWNER).write_text(json.dumps(expected, indent=2) + "\n")
        if not interpreter_info(str(extracted / "bin/python3.12")):
            raise ToolingError("Pinned Python archive did not provide a working native CPython 3.12")
        if owned:
            shutil.rmtree(directory)
        extracted.replace(directory)
    info = interpreter_info(str(directory / "bin/python3.12"))
    if not info:
        raise ToolingError("Installed training Python failed its version check")
    return directory / "bin/python3.12", info


def healthy(directory: Path, expected: dict, packages: list[dict], imports: list[str]) -> bool:
    """Check isolation, runtime imports and exact distribution versions on reuse."""
    try:
        if (directory.is_symlink() or json.loads((directory / OWNER).read_text()) != expected
                or (directory / "ready").read_text() != expected["key"]):
            return False
        versions = {item["name"]: item["version"] for item in packages}
        code = ("import sys,json,pathlib,importlib,importlib.metadata as m; "
                "assert sys.prefix != sys.base_prefix; "
                f"assert pathlib.Path(sys.prefix).resolve()==pathlib.Path({str(directory)!r}).resolve(); "
                f"assert {{name:m.version(name) for name in {list(versions)!r}}}=={versions!r}; "
                f"[importlib.import_module(name) for name in {imports!r}]; "
                "import torch; torch.set_num_threads(1)")
        return subprocess.run([str(python_path(directory)), "-I", "-c", code],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45).returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def ensure_training_environment(offline: bool = False, cache: Path | None = None) -> Path:
    """Return a managed interpreter; install/recover locally without activation."""
    data = load_manifest()
    host = host_name()
    if host not in data["platforms"]:
        raise ToolingError("No pinned training runtime for " + host + "; this checkpoint supports macOS ARM64. Engine targets are independent.")
    target = data["platforms"][host]
    if platform.system() == "Darwin" and tuple(map(int, platform.mac_ver()[0].split(".")[:2])) < (14, 0):
        raise ToolingError("The pinned PyTorch runtime requires macOS 14 or newer")
    cache = Path(cache or os.environ.get("CHESS0LIVE_TRAINING_CACHE", ROOT / ".local/training-runtime")).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    offline = offline or os.environ.get("CHESS0LIVE_TRAINING_OFFLINE") == "1"
    with setup_lock(cache / "setup.lock") as lock_fd:
        interpreter, info = select_interpreter(data, cache, offline)
        identity = {"manifest": checksum(MANIFEST), "interpreter": info, "host": host}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        expected = {"schema": 1, "key": key, "identity": identity}
        directory = cache / ("env-" + key)
        packages = target["packages"]
        if healthy(directory, expected, packages, target["imports"]):
            return python_path(directory)
        if directory.exists() or directory.is_symlink():
            try:
                owned = not directory.is_symlink() and json.loads((directory / OWNER).read_text()) == expected
            except (OSError, ValueError):
                owned = False
            if not owned:
                raise ToolingError("Refusing to replace an unowned training environment: " + str(directory))
            shutil.rmtree(directory)
        archives = cache / "archives"
        for asset in packages:
            fetch_asset(asset, archives, offline)
        directory.mkdir()
        (directory / OWNER).write_text(json.dumps(expected, indent=2) + "\n")
        requirements = directory / "requirements.lock"
        requirements.write_text("".join(f"{a['name']}=={a['version']} --hash=sha256:{a['sha256']}\n" for a in packages))
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INPUT="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        print("Preparing isolated training Python and pinned CPU/MPS packages...", file=sys.stderr, flush=True)
        with (cache / ("setup-" + key + ".log")).open("w", encoding="utf-8") as log:
            setup_command([str(interpreter), "-I", "-m", "venv", "--copies", str(directory)],
                          log=log, lock_fd=lock_fd, env=env, timeout=120)
            setup_command([str(python_path(directory)), "-I", "-m", "pip", "--isolated", "install",
                           "--no-cache-dir", "--no-index", "--no-deps", "--only-binary=:all:",
                           "--require-hashes", "--find-links", str(archives), "-r", str(requirements)],
                          log=log, lock_fd=lock_fd, env=env, timeout=300)
            setup_command([str(python_path(directory)), "-I", "-m", "pip", "--isolated", "check"],
                          log=log, lock_fd=lock_fd, env=env, timeout=45)
        (directory / "ready").write_text(key)
        if not healthy(directory, expected, packages, target["imports"]):
            (directory / "ready").unlink(missing_ok=True)
            raise ToolingError("Training environment import/version check failed; see " + str(cache / ("setup-" + key + ".log")))
        return python_path(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--plan", action="store_true", help="report availability without installing anything")
    args = parser.parse_args()
    try:
        if args.plan:
            print(json.dumps(plan_training_environment(), indent=2))
        else:
            print(ensure_training_environment(offline=args.offline))
    except (OSError, ValueError, ToolingError, subprocess.SubprocessError) as error:
        print("Training setup failed: " + str(error), file=sys.stderr)
        sys.exit(1)
