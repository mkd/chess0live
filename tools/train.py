#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Prepare, run and qualify a reproducible local SFNNv16 training experiment.

The independent engine never imports the trainer. Recipes bind input bytes and
settings; run reports distinguish observed work from declared dataset history.
Only short synthetic correctness checks run automatically during development.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import uuid

from fetch_network import fingerprint
from resources import current_budget
from tooling import ToolingError, setup_lock
from verify_nnue import interruption_cleanup, run as run_command

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".local/training"
# Fresh training/export measured roughly 5.34 GiB peak RSS in the small native
# check. Keep additional room for parent weights, batches and library overhead.
MIN_MEMORY = 8 * 1024 ** 3


class TrainingError(RuntimeError):
    """A failed precondition or incomplete run, suitable for a concise CLI error."""


def run_qualification(command, log, timeout=600, lock_fds=()):
    """Let the qualification wrapper unwind its separately grouped children.

    The wrapper forwards SIGTERM to the oracle harness, whose handler stops
    compiler/oracle sessions and writes its failure report. Killing the wrapper
    group first would bypass that cleanup and leave those sessions running.
    This training route currently supports POSIX hosts only.
    """
    if os.name != "posix":
        raise TrainingError("Training qualification requires the supported POSIX runtime")
    command = list(map(str, command))
    log.write(("$ " + shlex.join(command) + "\n").encode())
    log.flush()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True, pass_fds=tuple(lock_fds))

    def record(stdout, stderr):
        log.write(stdout or b"")
        log.write(stderr or b"")
        log.flush()

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        try:
            # Signal only the wrapper: its own 15-second cleanup wait lets the
            # harness reap the native process groups before this outer grace ends.
            if process.poll() is None:
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as error:
                # A malfunctioning escaped child must not hold our pipes open
                # indefinitely, even after the wrapper group has been killed.
                stdout, stderr = error.output, error.stderr
                process.stdout.close()
                process.stderr.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        record(stdout, stderr)
        raise
    record(stdout, stderr)
    if process.returncode:
        raise TrainingError("Qualification command failed; see build.log: " + shlex.join(command))
    return stdout


def trainer_manifest():
    return json.loads((ROOT / "tools/trainer-manifest.json").read_text(encoding="utf-8"))


def file_identity(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise TrainingError("Input is not a regular file: " + str(path))
    size, sha = fingerprint(path)
    if not size:
        raise TrainingError("Input is empty: " + str(path))
    return {"path": str(path), "size_bytes": size, "sha256": sha}


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, record, *, exclusive=False):
    if exclusive:
        with Path(path).open("x", encoding="utf-8") as target:
            json.dump(record, target, indent=2, allow_nan=False)
            target.write("\n")
    else:
        temporary = Path(path).with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)


def positive(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise TrainingError(f"{name} must be an integer between 1 and {maximum}")


def validate_recipe(recipe):
    """Reject silent settings drift and arbitrary command fields in recipes."""
    keys = {"schema_version", "trainer_commit", "architecture", "data", "parent", "training"}
    if not isinstance(recipe, dict) or set(recipe) != keys or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise TrainingError("Expected an exact schema_version 1 training recipe")
    pin = trainer_manifest()
    if recipe["trainer_commit"] != pin["commit"] or recipe["architecture"] != "SFNNv16":
        raise TrainingError("Recipe does not use the pinned SFNNv16 trainer")
    data = recipe["data"]
    if not isinstance(data, dict) or set(data) != {"file", "source", "license", "games", "positions", "synthetic"}:
        raise TrainingError("Unexpected dataset provenance fields")
    for name in ("source", "license"):
        if data[name] is not None and not isinstance(data[name], str):
            raise TrainingError("Dataset " + name + " must be a string or null")
    for name in ("games", "positions"):
        if data[name] is not None and (type(data[name]) is not int or data[name] < 0):
            raise TrainingError("Dataset counts must be nonnegative integers or null")
    if type(data["synthetic"]) is not bool:
        raise TrainingError("Dataset synthetic must be a boolean")
    for index, identity in enumerate((data["file"], recipe["parent"])):
        if identity is None and index == 1:
            continue
        if not isinstance(identity, dict) or set(identity) != {"path", "size_bytes", "sha256"}:
            raise TrainingError("Input identity must contain path, size_bytes and sha256")
        if not isinstance(identity["path"], str) or not Path(identity["path"]).is_absolute():
            raise TrainingError("Recipe input paths must be absolute")
        positive(identity["size_bytes"], "Input size", 2 ** 63 - 1)
        digest = identity["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise TrainingError("Invalid input SHA-256")
    if Path(data["file"]["path"]).suffix not in (".binpack", ".bin"):
        raise TrainingError("Training data must be a .binpack or .bin file")
    if recipe["parent"] and Path(recipe["parent"]["path"]).suffix != ".nnue":
        raise TrainingError("Parent weights must be an SFNNv16 .nnue file, not a pickle checkpoint")
    config = recipe["training"]
    if not isinstance(config, dict) or set(config) != {"steps", "batch_size", "threads", "seed", "max_seconds", "device"}:
        raise TrainingError("Unexpected training settings")
    for name, bound in (("steps", 10000000), ("batch_size", 1024), ("threads", 64), ("max_seconds", 8 * 3600)):
        positive(config[name], name, bound)
    if type(config["seed"]) is not int or not 0 <= config["seed"] < 2 ** 32:
        raise TrainingError("seed must be a 32-bit nonnegative integer")
    if config["device"] != "cpu":
        raise TrainingError("This qualified training route uses CPU; GPU routes remain unverified")
    return recipe


def create_recipe(args, *, synthetic=False):
    pin = trainer_manifest()
    result = {"schema_version": 1, "trainer_commit": pin["commit"], "architecture": "SFNNv16",
              "data": {"file": file_identity(args.data), "source": args.source, "license": args.license,
                       "games": args.games, "positions": args.positions, "synthetic": synthetic},
              "parent": file_identity(args.parent) if args.parent else None,
              "training": {"steps": args.steps, "batch_size": args.batch_size, "threads": args.threads,
                           "seed": args.seed, "max_seconds": args.max_seconds, "device": "cpu"}}
    return validate_recipe(result)


def load_recipe(path):
    if Path(path).stat().st_size > 1024 * 1024:
        raise TrainingError("Recipe exceeds 1 MiB")
    return validate_recipe(json.loads(Path(path).read_text(encoding="utf-8")))


def verify_inputs(recipe):
    """Hash both before and after training; a path alone does not identify data."""
    for identity in (recipe["data"]["file"], recipe["parent"]):
        if identity and file_identity(identity["path"]) != identity:
            raise TrainingError("Input changed since recipe creation: " + identity["path"])


def total_memory():
    try:
        if sys.platform == "darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True,
                                              stderr=subprocess.DEVNULL, timeout=5))
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None


def resource_check(config, allow_daytime=False):
    """Check aggregate CPU allowance and stop long work at the night boundary."""
    budget = current_budget()
    # --num-workers=1 still creates a reader, decompressor and feature worker,
    # accompanied by one Python prefetch thread. Count all four conservatively.
    if config["threads"] + 4 > budget["max_cpu_workers"]:
        raise TrainingError("Tensor threads plus four loader threads exceed the current resource allowance")
    memory = total_memory()
    if memory is None:
        raise TrainingError("Cannot determine physical memory; allow the system memory query before training")
    if MIN_MEMORY > memory * budget["memory_fraction"]:
        raise TrainingError("Training reserves 8 GiB, exceeding the current memory allowance")
    short = config["steps"] <= 2 and config["batch_size"] <= 32 and config["max_seconds"] <= 600
    local = datetime.fromisoformat(budget["local_time"])
    nighttime = local.hour >= 23 or local.hour < 7
    if not short and not nighttime and not allow_daytime:
        raise TrainingError("Long training runs use 23:00–07:00 Helsinki; --allow-daytime explicitly overrides this run")
    timeout = config["max_seconds"]
    if not short and not allow_daytime:
        boundary = local.replace(hour=7, minute=0, second=0, microsecond=0)
        if boundary <= local:
            boundary += timedelta(days=1)
        timeout = min(timeout, max(1, int((boundary - local).total_seconds())))
    return {"policy": budget, "reserved_memory_bytes": MIN_MEMORY, "total_memory_bytes": memory,
            "cpu_workers": config["threads"] + 4, "timeout_seconds": timeout,
            "daytime_override": bool(allow_daytime), "bounded_smoke": short}


def ensure_source(cache, offline, log, lock_fd):
    """Prepare only the pinned committed trainer, retaining upstream notices."""
    pin = trainer_manifest()
    source = Path(cache) / "source" / pin["commit"]
    source.parent.mkdir(parents=True, exist_ok=True)
    command = lambda argv, cwd=None: run_command(argv, log, cwd=cwd, timeout=180, lock_fds=(lock_fd,))
    if not source.exists():
        if offline:
            raise TrainingError("Offline setup needs the pinned trainer source; run once online")
        staging = source.with_name(source.name + ".partial-" + uuid.uuid4().hex)
        staging.mkdir()
        try:
            command(["git", "init", str(staging)])
            command(["git", "remote", "add", "origin", pin["repository"]], staging)
            command(["git", "fetch", "--depth", "1", "origin", pin["commit"]], staging)
            command(["git", "checkout", "--detach", "FETCH_HEAD"], staging)
            staging.rename(source)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    revision = command(["git", "rev-parse", "HEAD"], source).decode().strip()
    dirty = command(["git", "status", "--porcelain", "--untracked-files=no"], source).decode().strip()
    if revision != pin["commit"] or dirty:
        raise TrainingError("Trainer cache changed; preserve it and select a fresh --cache directory")
    return source


def implementation_pins():
    names = ["tools/train.py", "tools/training_backend.py", "tools/training_setup.py", "tools/trainer-manifest.json",
             "tools/training-packages.json", "tools/network.py", "tools/verify_nnue.py"]
    return {name: fingerprint(ROOT / name)[1] for name in names}


def execute(args):
    """Run a fresh experiment through setup, training, export and qualification."""
    from training_setup import ensure_training_environment
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "started_at": now(), "status": "running", "stage": "preflight",
              "playing_strength": "not_measured", "output": str(output)}
    report_path = output / "report.json"
    save(report_path, report)
    cache = args.cache.resolve()
    try:
        cache.mkdir(parents=True, exist_ok=True)
        recipe = None if args.command == "smoke" else load_recipe(args.recipe)
        config = recipe["training"] if recipe else {"steps": 2, "batch_size": 16, "threads": 1,
                                                     "seed": 20261024, "max_seconds": 600, "device": "cpu"}
        report["resources"] = resource_check(config, args.allow_daytime)
        if recipe:
            verify_inputs(recipe)
        report["implementation_sha256"] = implementation_pins()
        with interruption_cleanup(), setup_lock(cache / "run.lock", timeout=120) as lock_fd, (output / "run.log").open("wb") as log:
            report["stage"] = "setup"
            save(report_path, report)
            python = ensure_training_environment(offline=args.offline)
            report["runtime_python"] = file_identity(python)
            report["runtime_version"] = run_command([str(python), "--version"], log, timeout=15,
                                                   lock_fds=(lock_fd,)).decode().strip()
            source = ensure_source(cache, args.offline, log, lock_fd)
            worker = [str(python), str(ROOT / "tools/training_backend.py"), "--source", str(source)]
            if recipe is None:
                fixture = output / "synthetic.binpack"
                run_command(worker + ["--create-fixture", str(fixture)], log, timeout=240, lock_fds=(lock_fd,))
                info = json.loads(Path(str(fixture) + ".json").read_text())
                report["synthetic_fixture"] = info
                smoke_args = argparse.Namespace(data=fixture, source="Original synthetic correctness fixture; placeholder labels",
                    license="CC0-1.0", games=0, positions=info["records"], parent=None, **{k: v for k, v in config.items() if k != "device"})
                recipe = create_recipe(smoke_args, synthetic=True)
            report["recipe"] = recipe
            save(output / "recipe.json", recipe, exclusive=True)
            report["stage"] = "training_and_export"
            save(report_path, report)
            # Re-read the resource allowance after potentially lengthy first setup.
            report["resources"] = resource_check(config, args.allow_daytime)
            command = worker + ["--data", recipe["data"]["file"]["path"], "--output", str(output / "work")]
            for option in ("steps", "batch_size", "threads", "seed"):
                command += ["--" + option.replace("_", "-"), str(config[option])]
            command += ["--max-seconds", str(report["resources"]["timeout_seconds"])]
            if recipe["parent"]:
                command += ["--parent", recipe["parent"]["path"]]
            report["training_command"] = command
            run_command(command, log, timeout=report["resources"]["timeout_seconds"], lock_fds=(lock_fd,))
            result = json.loads((output / "work/result.json").read_text())
            report["backend"] = result
            verify_inputs(recipe)
            if implementation_pins() != report["implementation_sha256"]:
                raise TrainingError("Training implementation changed during this run")
            # The backend reports observed checkpoint steps, never just the request.
            if (result.get("status") != "passed" or type(result.get("steps")) is not int
                    or result["steps"] != config["steps"] or type(result.get("processed_samples")) is not int
                    or result["processed_samples"] != result["steps"] * config["batch_size"]):
                raise TrainingError("Training did not complete the requested fixed batches")
            network = file_identity(result["network"]["path"])
            if network != result["network"] or file_identity(result["checkpoint"]["path"]) != result["checkpoint"]:
                raise TrainingError("Backend artifact identities changed before qualification")
            report["network"] = network
            report["checkpoint"] = result["checkpoint"]
            metadata = {"schema_version": 2, "network_sha256": network["sha256"], "name": "chess0live local experiment",
                "author": None, "license": None, "source": str(report_path),
                "training": {"games": recipe["data"]["games"], "positions": recipe["data"]["positions"],
                    "epochs": None, "data_sources": [recipe["data"]["source"]] if recipe["data"]["source"] else [],
                    "processed_samples": result["processed_samples"], "steps": result["steps"],
                    "parent_network_sha256": recipe["parent"]["sha256"] if recipe["parent"] else None,
                    "trainer_commit": trainer_manifest()["commit"], "dataset_sha256": recipe["data"]["file"]["sha256"]}}
            save(output / "network.metadata.json", metadata, exclusive=True)
            report["stage"] = "qualification"
            save(report_path, report)
            command = [sys.executable, str(ROOT / "tools/network.py"), "qualify", network["path"],
                       "--metadata", str(output / "network.metadata.json"), "--output", str(output / "qualification")]
            if args.offline:
                command.append("--offline")
            if args.reference_dir:
                command += ["--reference-dir", str(args.reference_dir.resolve())]
            run_qualification(command, log, timeout=600, lock_fds=(lock_fd,))
            qualification = json.loads((output / "qualification/report.json").read_text())
            if qualification.get("status") != "passed" or qualification.get("artifact") != network:
                raise TrainingError("Export qualification identity or result failed")
            verify_inputs(recipe)
            if (file_identity(network["path"]) != network
                    or file_identity(report["checkpoint"]["path"]) != report["checkpoint"]
                    or implementation_pins() != report["implementation_sha256"]):
                raise TrainingError("Export or implementation changed during qualification")
            report.update(status="passed", stage="complete", qualification=file_identity(output / "qualification/report.json"))
            print("PASS: training, export and independent compatibility checks completed.")
            print("This is not a playing-strength qualification.")
        return 0
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        print("FAIL: " + json.dumps(report["error"]), file=sys.stderr)
        return 1
    finally:
        report["finished_at"] = now()
        save(report_path, report)
        print("Report: " + json.dumps(str(report_path)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="bind a dataset and settings into a new recipe")
    init.add_argument("--data", type=Path, required=True)
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--parent", type=Path, help="optional compatible .nnue weights; optimizer state is reset")
    init.add_argument("--source")
    init.add_argument("--license")
    init.add_argument("--games", type=int)
    init.add_argument("--positions", type=int)
    init.add_argument("--steps", type=int, default=100)
    init.add_argument("--batch-size", type=int, default=128)
    init.add_argument("--threads", type=int, default=2)
    init.add_argument("--seed", type=int, default=20261024)
    init.add_argument("--max-seconds", type=int, default=600)
    plan = commands.add_parser("plan", help="show requirements/settings without setup or training")
    plan.add_argument("recipe", type=Path, nargs="?")
    for name in ("run", "smoke"):
        command = commands.add_parser(name, help="run a bound recipe" if name == "run" else "run a tiny synthetic train/export correctness check")
        if name == "run":
            command.add_argument("recipe", type=Path)
        command.add_argument("--output", type=Path, default=ROOT / "results" / ("training-" + name + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
        command.add_argument("--cache", type=Path, default=CACHE)
        command.add_argument("--offline", action="store_true")
        command.add_argument("--reference-dir", type=Path, help="optional existing pinned SF19 oracle source cache")
        command.add_argument("--allow-daytime", action="store_true", help="explicit one-run exception for longer daytime training")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            save(args.output, create_recipe(args), exclusive=True)
            print("Recipe: " + json.dumps(str(args.output)))
        elif args.command == "plan":
            from training_setup import plan_training_environment
            result = {"trainer": trainer_manifest(), "setup": "isolated pinned Python packages and external trainer; no engine changes",
                      "environment": plan_training_environment(),
                      "route": "CPU", "memory_reservation_bytes": MIN_MEMORY,
                      "qualification": "export compared with pinned SF19 oracle before run passes",
                      "note": "Plan only: nothing is downloaded, compiled or trained."}
            if args.recipe:
                recipe = load_recipe(args.recipe)
                verify_inputs(recipe)
                result.update(recipe=recipe, requested_samples=recipe["training"]["steps"] * recipe["training"]["batch_size"])
            print(json.dumps(result, indent=2))
        else:
            return execute(args)
        return 0
    except (OSError, ValueError, TrainingError, ToolingError) as error:
        print("Error: " + json.dumps(str(error)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
