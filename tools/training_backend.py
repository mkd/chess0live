#!/usr/bin/env python3
# chess0live — an independent UCI chess engine.
# Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later
# GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
"""Managed-environment worker for the pinned external SFNNv16 trainer.

The public tools/train.py command owns setup, resource admission and process
timeouts. This worker builds the external data reader, performs a finite CPU
training run, then exports through its pinned serializer. No trainer or data
reader implementation is linked into the chess0live engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile


MANIFEST = Path(__file__).with_name("trainer-manifest.json")
FEATURES = "Full_Threats+PP_3Wide+HalfKAv2_hm^"


def fingerprint(path):
    checksum = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
            size += len(chunk)
    return {"path": str(Path(path).resolve()), "size_bytes": size, "sha256": checksum.hexdigest()}


def run(command, *, cwd=None):
    """Build one bounded subprocess; the outer worker shares its process group."""
    print("Command: " + json.dumps(list(map(str, command))), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, check=True, timeout=180)


def source_identity(source):
    """Require the pinned committed inputs, allowing only ignored build outputs."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != manifest["commit"]:
        raise RuntimeError("Trainer source does not match the committed manifest")
    status = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"], text=True)
    if status:
        raise RuntimeError("Trainer source contains tracked edits; use a fresh source cache")
    names = subprocess.check_output(["git", "-C", str(source), "ls-files", "-z"]).decode().split("\0")
    hashes = {name: fingerprint(source / name)["sha256"] for name in names if name}
    return {"commit": revision, "files": hashes}


def compiler():
    explicit = os.environ.get("CXX_EXECUTABLE")
    names = [explicit] if explicit else ["clang++", "g++", "c++"]
    for name in names:
        if name and (path := shutil.which(name)):
            return os.path.abspath(path)
    raise RuntimeError("A native Clang/GCC C++ compiler is required for the external trainer data reader")


def build_loader(source, work):
    """Use a private build directory, preserving the immutable trainer cache."""
    directory = work / "build"
    directory.mkdir()
    suffix = ".dylib" if platform.system() == "Darwin" else ".dll" if os.name == "nt" else ".so"
    library = directory / ("libtraining_data_loader" + suffix)
    cpp = source / "data_loader/cpp"
    command = [compiler(), "-std=c++20", "-O2", "-pthread", "-shared"]
    if os.name != "nt":
        command.append("-fPIC")
    command.extend([cpp / "training_data_loader.cpp", cpp / "training_data_loader_abi.cpp", "-o", library])
    run(command)
    return fingerprint(library)


# Original tiny positions and deliberately artificial labels. The external MIT
# writer defines the binary format; no engine games or owner test assets enter
# this fixture. Repeating rows is not additional game experience.
FIXTURE_CPP = r'''// chess0live training-tool fixture, GPL-3.0-or-later.
// Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
#include "lib/binpack.h"
#include <array>
#include <stdexcept>
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const std::array<std::pair<const char*, const char*>, 8> samples{{
        {"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "e2e4"},
        {"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", "e7e5"},
        {"rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2", "g1f3"},
        {"rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2", "b8c6"},
        {"rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1", "d7d5"},
        {"rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6 0 2", "c2c4"},
        {"4k3/pp6/8/8/8/8/PP6/4K3 w - - 0 20", "a2a3"},
        {"4k3/pp6/8/8/8/P7/1P6/4K3 b - - 0 20", "a7a6"}
    }};
    binpack::CompressedTrainingDataEntryWriter writer(argv[1], std::ios_base::trunc);
    for (int index = 0; index < 256; ++index) {
        const auto& sample = samples[index % samples.size()];
        binpack::TrainingDataEntry entry;
        entry.pos = chess::Position::fromFen(sample.first);
        entry.move = chess::uci::uciToMove(entry.pos, sample.second);
        if (!entry.isValid()) throw std::runtime_error("Invalid original fixture move");
        entry.score = 0;
        entry.ply = 40;
        entry.result = 0;
        writer.addTrainingDataEntry(entry);
    }
}
'''


def create_fixture(source, destination):
    """Generate small legal input with known artificial provenance, never overwrite."""
    if destination.exists() or Path(str(destination) + ".json").exists():
        raise RuntimeError("Fixture or provenance file already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    identity = source_identity(source)
    with tempfile.TemporaryDirectory(prefix="fixture-build-", dir=destination.parent) as temp:
        directory = Path(temp)
        cpp = directory / "fixture.cpp"
        cpp.write_text(FIXTURE_CPP, encoding="utf-8")
        executable = directory / ("fixture.exe" if os.name == "nt" else "fixture")
        run([compiler(), "-std=c++20", "-O2", "-pthread", "-I" + str(source / "data_loader/cpp"), cpp, "-o", executable])
        staged = directory / "synthetic.binpack"
        run([executable, staged])
        if staged.stat().st_size == 0:
            raise RuntimeError("Synthetic binpack writer produced an empty file")
        # Exclusive output creation avoids replacing a concurrent user's file.
        with destination.open("xb") as output, staged.open("rb") as content:
            shutil.copyfileobj(content, output)
    record = {"schema_version": 1, "artifact": fingerprint(destination), "records": 256,
              "unique_positions": 8, "games": 0, "synthetic": True,
              "label_quality": "Artificial zero-score/draw placeholders; not strength-training data",
              "trainer_commit": identity["commit"], "fixture_source_sha256": hashlib.sha256(FIXTURE_CPP.encode()).hexdigest()}
    with Path(str(destination) + ".json").open("x", encoding="utf-8") as output:
        json.dump(record, output, indent=2)
        output.write("\n")
    return record


def train(args):
    """Run actual optimizer steps, read observed counters, then quantize/export."""
    source, output, data = args.source.resolve(), args.output.resolve(), args.data.resolve()
    if data.suffix not in (".binpack", ".bin") or not data.is_file() or data.stat().st_size == 0:
        raise RuntimeError("Training data must be a nonempty local .binpack or .bin file")
    initial = source_identity(source)
    data_identity = fingerprint(data)
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "trainer_commit": initial["commit"],
              "trainer_source_sha256": initial["files"], "dataset": data_identity,
              "device": "cpu", "requested_steps": args.steps, "batch_size": args.batch_size,
              "threads": args.threads, "loader_workers": 1, "seed": args.seed,
              "loader_threads_reserved": 4,
              "max_seconds": args.max_seconds,
              "architecture": "SFNNv16", "features": FEATURES,
              "unique_games": None, "strength": "not_measured"}
    try:
        report["data_loader"] = build_loader(source, output)
        # Set limits before importing torch or creating a model. The outer tool
        # enforces aggregate admission: the native loader's concurrency=1
        # creates a file reader, decompressor and feature worker, accompanied
        # by the Python prefetch thread. Reserve all four auxiliary threads.
        os.environ["OMP_NUM_THREADS"] = str(args.threads)
        os.environ["MKL_NUM_THREADS"] = str(args.threads)
        os.environ["OPENBLAS_NUM_THREADS"] = str(args.threads)
        os.environ["TORCHDYNAMO_DISABLE"] = "1"
        os.chdir(output)
        sys.path.insert(0, str(source))
        import torch
        import numpy as np
        import random
        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(1)
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)
        random.seed(args.seed)
        import model as model_api
        config = model_api.NNUELightningConfig()
        config.features = FEATURES
        config.model_config.L1, config.model_config.L2, config.model_config.L3 = 1024, 32, 32
        config.optimizer_config.optimizer_name = "adamw"
        config.optimizer_config.lr = 0.0001
        config.optimizer_config.adamw_fused = False
        hours, remaining = divmod(args.max_seconds, 3600)
        minutes, seconds = divmod(remaining, 60)
        maximum_time = f"00:{hours:02d}:{minutes:02d}:{seconds:02d}"
        arguments = [str(source / "train.py"), str(data), "--accelerator", "cpu",
                     "--threads", str(args.threads), "--num-workers", "1",
                     "--batch-size", str(args.batch_size), "--epoch-size", str(args.steps * args.batch_size),
                     "--max-epochs", "1", "--validation-size", "0", "--max-time", maximum_time,
                     "--default-root-dir", str(output / "training"), "--seed", str(args.seed),
                     "--features", FEATURES, "--l1", "1024", "--l2", "32", "--l3", "32",
                     "--optimizer-name", "adamw", "--lr", "0.0001", "--no-adamw-fused", "--swa-start-epoch", "-1",
                     "--data-loader-queue-size", "1", "--no-pin-memory", "--no-filtered",
                     "--no-wld-filtered", "--soft-early-fen-skipping", "0", "--random-fen-skipping", "0"]
        if args.parent:
            parent = args.parent.resolve()
            if parent.suffix != ".nnue" or not parent.is_file():
                raise RuntimeError("Parent must be a compatible .nnue file; arbitrary pickle checkpoints are not accepted")
            report["parent"] = fingerprint(parent)
            parent_model = model_api.NNUE(config=config)
            with parent.open("rb") as stream:
                reader = model_api.NNUEReader(stream, FEATURES, config=config.model_config)
                parent_model.model = reader.model
                if stream.read(1):
                    raise RuntimeError("Trailing bytes in parent network")
            trusted_parent = output / "parent-weights.pt"
            # Upstream's full-model import uses pickle. This file is created by
            # this process from a parsed NNUE, never accepted from the caller.
            torch.save(parent_model, trusted_parent)
            arguments.extend(["--resume-from-model", str(trusted_parent)])
            del parent_model, reader
        report["trainer_arguments"] = arguments[1:]
        report["torch_version"] = torch.__version__
        report["numpy_version"] = np.__version__
        report["compile"] = "disabled via TORCHDYNAMO_DISABLE=1"
        sys.argv = arguments
        runpy.run_path(str(source / "train.py"), run_name="__main__")
        checkpoint = output / "training/lightning_logs/version_0/checkpoints/last.ckpt"
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        observed_steps = state.get("global_step")
        if type(observed_steps) is not int or observed_steps != args.steps:
            raise RuntimeError("Trainer did not complete the requested number of optimizer steps: " + repr(observed_steps))
        exported = model_api.NNUE(config=config)
        exported.load_state_dict(state["state_dict"])
        exported.eval()
        exported.model.clip_weights(include_input=True)
        writer = model_api.NNUEWriter(exported.model, description="chess0live external trainer export; see accompanying provenance", ft_compression="leb128", verbose=False)
        network = output / "candidate.nnue"
        with network.open("xb") as stream:
            stream.write(writer.buf)
        if fingerprint(data) != data_identity or source_identity(source) != initial:
            raise RuntimeError("Trainer source or dataset changed during the run")
        if args.parent and fingerprint(args.parent.resolve()) != report["parent"]:
            raise RuntimeError("Parent network changed during the run")
        report.update(status="passed", checkpoint=fingerprint(checkpoint), network=fingerprint(network),
                      steps=observed_steps, processed_samples=observed_steps * args.batch_size,
                      completed_epochs=1,
                      epoch_definition="One configured fixed-step epoch; not a claim of a complete pass over distinct dataset records",
                      count_basis="Observed optimizer steps times fixed full-batch size; repeats are not unique games or positions",
                      qualification="not_run")
        return report
    except BaseException as error:
        report.update(status="failed", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--create-fixture", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261024)
    parser.add_argument("--max-seconds", type=int, default=300)
    parser.add_argument("--parent", type=Path)
    args = parser.parse_args()
    args.source = args.source.resolve()
    if args.parent:
        args.parent = args.parent.resolve()
    if args.create_fixture:
        result = create_fixture(args.source, args.create_fixture.resolve())
    else:
        if args.data is None or args.output is None:
            parser.error("Training requires --data and --output")
        if args.steps < 1 or not 1 <= args.batch_size <= 65536 or not 1 <= args.threads <= 64 or not 0 <= args.seed < 2**32 or not 1 <= args.max_seconds <= 28800:
            parser.error("Invalid step, batch, thread, seed or time limit")
        result = train(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print("Training worker failed: " + str(error), file=sys.stderr)
        sys.exit(1)
