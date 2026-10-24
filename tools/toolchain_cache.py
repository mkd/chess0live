"""Download and unpack pinned local toolchains without system installation.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from tooling import setup_lock

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("toolchains.json")
OWNER = ".chess0live-toolchain.json"


class ToolchainError(RuntimeError):
    """A provisioning failure with an actionable user-facing message."""


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verified_archive(path: Path, asset: dict) -> bool:
    return path.is_file() and path.stat().st_size == asset["size"] and sha256(path) == asset["sha256"]


def archive_for(asset: dict, cache: Path, offline: bool = False) -> Path:
    """Return a complete pinned archive, including read-only legacy-cache reuse."""
    filename = asset["filename"]
    if Path(filename).name != filename or any(c in filename for c in "\\/:"):
        raise ToolchainError("Invalid toolchain archive filename in manifest.")
    directory = cache / "archives"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if verified_archive(destination, asset):
        return destination
    legacy = ROOT / "build/toolchains" / filename
    if verified_archive(legacy, asset):
        return legacy
    if offline:
        raise ToolchainError(f"Offline toolchain setup needs {filename}; run once online or place "
                             f"the pinned archive in {directory}.")
    if not asset["url"].startswith("https://github.com/mstorsjo/llvm-mingw/releases/download/"):
        raise ToolchainError("Unexpected toolchain download source in manifest.")
    temporary = None
    try:
        print(f"Downloading pinned toolchain {filename}...", file=sys.stderr, flush=True)
        request = urllib.request.Request(asset["url"], headers={"User-Agent": "chess0live-toolchain-setup"})
        with tempfile.NamedTemporaryFile(dir=directory, suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(request, timeout=30) as source:
                received = 0
                while block := source.read(1024 * 1024):
                    received += len(block)
                    if received > asset["size"]:
                        raise ToolchainError(f"Unexpected archive size for {filename}.")
                    output.write(block)
        if not verified_archive(temporary, asset):
            raise ToolchainError(f"Size/checksum mismatch for {filename}; nothing was installed.")
        temporary.replace(destination)
        return destination
    except (OSError, HTTPException) as error:
        raise ToolchainError(f"Could not download {filename}: {error}. Check the connection and retry.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def member_path(name: str, root: str) -> PurePosixPath:
    """Reject path aliases that could escape the archive root on either OS."""
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or path.is_absolute()
            or ".." in path.parts or not path.parts or path.parts[0] != root):
        raise ToolchainError(f"Unsafe toolchain archive path: {name!r}")
    return path


def extract_archive(archive: Path, staging: Path, root: str) -> Path:
    """Extract a distribution without following archive links while writing files.

    Regular members are written first, then internal hardlinks and symlinks.
    Every path is anchored to the named root; links are validated again after
    creation so link chains cannot leave it. No device/FIFO members are accepted.
    Upstream Windows ZIPs contain dereferenced regular files, not symlinks.
    """
    if member_path(root, root).parts != (root,):
        raise ToolchainError("Invalid archive root in manifest.")
    output_root = staging / root
    seen, regular, links = {}, set(), []

    def destination(name, kind):
        relative = member_path(name, root)
        if relative in seen and (kind != "dir" or seen[relative] != "dir"):
            raise ToolchainError(f"Duplicate toolchain archive member: {name}")
        seen[relative] = kind
        output = staging.joinpath(*relative.parts)
        # No link is created until every ordinary member has been written.
        if kind == "dir":
            output.mkdir(parents=True, exist_ok=True)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
        return relative, output

    def write_file(source, output, mode):
        with output.open("xb") as sink:
            shutil.copyfileobj(source, sink)
        # Preserve executable permissions, stripping setuid/setgid/sticky bits.
        output.chmod(mode & 0o777)

    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as source:
                for member in source.infolist():
                    mode = member.external_attr >> 16
                    kind = "dir" if member.is_dir() else "file"
                    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                        raise ToolchainError(f"Unsupported ZIP member type: {member.filename}")
                    relative, output = destination(member.filename, kind)
                    if kind == "file":
                        with source.open(member) as contents:
                            write_file(contents, output, mode or 0o644)
                        regular.add(relative)
        else:
            with tarfile.open(archive, "r:*") as source:
                for member in source.getmembers():
                    kind = ("dir" if member.isdir() else "file" if member.isfile()
                            else "link" if member.issym() or member.islnk() else "unsupported")
                    if kind == "unsupported":
                        raise ToolchainError(f"Unsupported tar member type: {member.name}")
                    relative, output = destination(member.name, kind)
                    if kind == "file":
                        with source.extractfile(member) as contents:
                            write_file(contents, output, member.mode)
                        regular.add(relative)
                    elif kind == "link":
                        links.append((relative, output, member.linkname, member.islnk()))
            # Hardlinks must refer to an already materialized regular member.
            for relative, output, target, hard in links:
                if hard:
                    linked = member_path(target, root)
                    if linked not in regular:
                        raise ToolchainError(f"Hardlink target is not a regular archive member: {target}")
                    os.link(staging.joinpath(*linked.parts), output)
                else:
                    if not target or "\\" in target or ":" in target or PurePosixPath(target).is_absolute():
                        raise ToolchainError(f"Unsafe toolchain symlink: {target!r}")
                    normalized = posixpath.normpath(str(relative.parent / target))
                    member_path(normalized, root)
                    output.symlink_to(target)
            # Only after link creation can chained targets be resolved accurately.
            for _, output, _, _ in links:
                if not output.resolve(strict=True).is_relative_to(output_root.resolve()):
                    raise ToolchainError(f"Toolchain link escapes its root: {output}")
    except (OSError, tarfile.TarError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, ToolchainError):
            raise
        raise ToolchainError(f"Could not safely extract toolchain archive: {error}") from error
    if not output_root.is_dir():
        raise ToolchainError("Toolchain archive did not contain its expected root.")
    return output_root


def ready(directory: Path, asset: dict, host: str) -> bool:
    """Check provenance and required wrappers without executing foreign programs."""
    try:
        if directory.is_symlink():
            return False
        if json.loads((directory / OWNER).read_text()) != {"schema": 1, "asset": asset, "host": host}:
            return False
        extension = ".exe" if host.startswith("windows-") else ""
        for target in ("aarch64", "x86_64"):
            compiler = directory / "bin" / f"{target}-w64-mingw32-clang++{extension}"
            if not compiler.is_file() or not compiler.resolve().is_relative_to(directory.resolve()):
                return False
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def provision_llvm(host: str, *, offline: bool = False, cache: Path | None = None) -> Path:
    """Prepare/reuse the host's pinned Windows-targeting LLVM-MinGW bundle."""
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("schema") != 1:
        raise ToolchainError("Unsupported toolchain manifest schema.")
    if host not in manifest["hosts"]:
        raise ToolchainError(f"No pinned LLVM-MinGW host bundle for {host}; supply an installed compiler.")
    asset = manifest["hosts"][host]
    cache = Path(cache or os.environ.get("CHESS0LIVE_TOOLCHAIN_CACHE", ROOT / ".local/toolchains")).expanduser().resolve()
    installed = cache / "installed"
    directory = installed / (asset["root"] + "-" + asset["sha256"][:12])
    if ready(directory, asset, host):
        return directory
    installed.mkdir(parents=True, exist_ok=True)
    with setup_lock(cache / "setup.lock"):
        if ready(directory, asset, host):
            return directory
        archive = archive_for(asset, cache, offline)
        if directory.exists():
            try:
                owned = json.loads((directory / OWNER).read_text()) == {"schema": 1, "asset": asset, "host": host}
            except (OSError, ValueError):
                owned = False
            if directory.is_symlink() or not owned:
                raise ToolchainError(f"Refusing to replace an unowned toolchain directory: {directory}")
        print(f"Preparing pinned LLVM-MinGW for {host}...", file=sys.stderr, flush=True)
        with tempfile.TemporaryDirectory(prefix=".staging-", dir=installed) as temporary:
            unpacked = extract_archive(archive, Path(temporary), asset["root"])
            (unpacked / OWNER).write_text(json.dumps({"schema": 1, "asset": asset, "host": host}, indent=2) + "\n")
            if not ready(unpacked, asset, host):
                raise ToolchainError("Toolchain archive is missing its expected compiler wrappers.")
            if directory.exists():
                shutil.rmtree(directory)
            unpacked.replace(directory)
        return directory
