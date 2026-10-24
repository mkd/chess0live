# Local network training and export

This external workflow creates or fine-tunes an SFNNv16 network, exports it and
checks its arithmetic before reporting success. The first supported training host
is **macOS 14+ on ARM64, using CPU**. Other engine platforms remain supported as
documented in [portability](PORTABILITY.md); their training-runtime packages and
GPU execution have separate acceptance work. Unsupported training hosts get an
explicit message before any package download.

## Try the complete workflow

```sh
make training-plan
make training-smoke
```

The plan makes no changes. The smoke command automatically prepares isolated
Python/packages and pinned trainer source, generates a small original synthetic
dataset, performs two optimizer steps, exports a compressed `.nnue`, and compares
it with the pinned SF19 reference over 2,057 positions. It leaves your engine,
GUI bundle and selected `EvalFile` unchanged. Its labels are artificial zero-score
draws: this is a correctness check, **not a useful playing network**.

Prerequisites are Python 3.10+ to launch the tool, Git, GNU Make and a native
Clang/GCC compiler supporting C++26. The external data loader uses C++20; the
independent engine/oracle adapters use C++26. No CMake, pip command or environment
activation is required. If Python 3.12 is not installed, setup downloads a pinned
standalone CPython into the local cache. It does not install system packages or
change your global Python settings. Existing compiler/Apple SDK prerequisites
remain explicit.

First setup downloads about 197 MB of package archives and, if needed, 25 MB of
Python. A run needs several GiB of free disk space for its runtime, model,
checkpoint, exported network and oracle evidence. Checkpoints are approximately
1.1 GB in the tested small run even though the dataset is tiny: they contain
weights and optimizer state. Training reserves **8 GiB of memory**; that estimate
is checked against the local resource allowance, not enforced as an OS limit.
Batch size is capped at 1,024 until larger allocations are qualified.

## Use your own data

Supply a local, compatible `.binpack` or `.bin` training dataset whose source,
labels and usage rights you understand. These are the pinned trainer's structured
training records, not PGN/FEN text renamed with a different extension. The trainer
expects its documented score/result/move encoding; see its pinned
[data loader](https://github.com/official-stockfish/nnue-pytorch/tree/aa2fff2f4a67d1a268dad991fcc03430781fde15/data_loader).
This command does not generate a competitive dataset, invent labels, download
large datasets or establish their quality.

```sh
python3 tools/train.py init --data /path/to/training.binpack --output training.json \
  --source 'Description or URL of your dataset' --license 'Your data license' \
  --steps 100 --batch-size 128 --threads 2 --max-seconds 600
python3 tools/train.py plan training.json
python3 tools/train.py run training.json
```

`init` records the dataset's absolute path, complete SHA-256, byte count and
settings. An existing recipe is never overwritten. Optional `--games` and
`--positions` record declared unique source games and dataset rows; omit either
when unknown. The tool does not authenticate these declarations or treat rows as
unique FENs. It hashes inputs before and after a run and rejects changed files.

To fine-tune existing compatible weights, add the following when creating a
recipe:

```sh
python3 tools/train.py init --data /path/to/training.binpack --output fine-tune.json \
  --parent /path/to/compatible.nnue --steps 100 --batch-size 128
```

This starts with those weights and a **fresh optimizer**. It is not a complete
checkpoint/optimizer resume. Arbitrary `.pt`/`.ckpt` pickle inputs are not
accepted. The adapter reads `.nnue` weights and creates any temporary upstream
model object itself; its own resulting checkpoint is read with
`torch.load(weights_only=True)` for export.

The current bounded recipe uses CPU AdamW at learning rate 0.0001, fixed SF19
features/layer sizes, one loader setting, eager PyTorch execution and no data
filtering. It is an explicit starting workflow, not a tuned training recipe.
There is no held-out validation split in this checkpoint. The saved command and
trainer configuration record these choices. A seed is recorded, but input-loader
sampling and platform arithmetic can differ: reproducible configuration and
artifact identities do not promise bit-identical training across machines.

## Resource limits and failure handling

Normal long runs use 23:00–07:00 Europe/Helsinki. Daytime CPU/memory allowance is
50%; nighttime 80%, with the existing [manual resource override](../README.md#local-resource-policy).
The tool conservatively counts `threads + 4`: tensor threads plus the file
reader, decompressor, feature worker and Python prefetch thread. It checks the
allowance again after setup, and refuses training if physical memory cannot be
queried. The smoke recipe uses one tensor thread and reserves five workers.

For a deliberately authorized longer daytime run, use:

```sh
python3 tools/train.py run training.json --allow-daytime
```

This is a one-run scheduling exception; it does not raise the CPU/memory ceiling
or create a schedule. Small runs of at most two steps, batch size at most 32 and
up to ten minutes have the bounded correctness-check allowance. Large step
requests remain long runs even if the time cap is short.

`--max-seconds` in the recipe caps the worker's entire compile/train/export
process. Overnight runs also stop by 07:00. The wrapper kills its worker process
group at the limit; the upstream trainer's internal time check alone is only at
epoch boundaries. An interrupted/incomplete run fails and retains diagnostics
and any checkpoints already written. A mid-epoch interruption may have no
checkpoint; automatic full-state resume is not implemented. Export verification
is a separate short correctness step. No partially completed run is advertised
as successful.

## Reports, experience and selecting a result

Each invocation creates a new timestamped directory under `results/`. Use
`--output results/my-experiment` to choose a new directory explicitly. It contains:

- `recipe.json`, `run.log` and `report.json`: input identities, settings, resource
  allowance, actual interpreter and implementation identities, outcome and errors.
- `work/`: loader build, trainer logs, checkpoint, exported `candidate.nnue` and
  backend report with actual optimizer steps and processed samples.
- `network.metadata.json`: schema 2 provenance tied to the exported SHA-256,
  dataset identity, trainer commit and optional parent-network hash.
- `qualification/`: complete scalar/native/reference comparison and its evidence.

Processed samples mean **observed optimizer steps × fixed full batch size** for
this run. They may repeat rows. The configured single training epoch is a fixed
step budget, not necessarily a full pass over the dataset, so metadata
`training.epochs` stays null. Parent training totals are not known or silently
added. Game/position declarations remain unverified; neither sample counts nor
successful export imply a rating or stronger play.

Only after compatibility, tactical and game testing should you consider using a
result for play. Select it through the existing UCI option while the engine is
idle:

```text
setoption name EvalFile value /absolute/path/to/candidate.nnue
isready
```

Training never changes that setting for you. The [managed selection workflow](NETWORKS.md#managed-selection)
can register an export with its `network.metadata.json`, check it again and keep
a reversible choice. Held-out data validation, trainer tuning, full optimizer
resume and competitive training remain subsequent work.

## Cache and offline use

`make training-setup` optionally prepares Python/packages without training.
The runtime lives in `.local/training-runtime/`; set
`CHESS0LIVE_TRAINING_CACHE` to use another location. Set
`CHESS0LIVE_TRAINING_PYTHON` to an existing compatible Python 3.12 executable.
The trainer source is separately cached in `.local/training/source/`; the run
command's `--cache` selects that source/run-lock location. Do not share a virtual
environment between computers or modify a cache during an active run.

After a successful online setup/run:

```sh
make training-smoke OFFLINE=1
python3 tools/train.py run training.json --offline
```

Offline mode requires the pinned runtime archives/environment, trainer source and
SF19 oracle source already cached. Missing inputs produce an explicit error.
`--reference-dir PATH` can reuse an existing pinned oracle checkout. Setup repairs
owned incomplete environments, checks archive hashes and refuses foreign cache
folders; it never repairs an unknown directory by deleting it. Failed source
downloads are staged, and tracked source edits are rejected rather than reset.

## Upstream provenance and tests

The external trainer is pinned to
[`aa2fff2f4a67d1a268dad991fcc03430781fde15`](https://github.com/official-stockfish/nnue-pytorch/tree/aa2fff2f4a67d1a268dad991fcc03430781fde15).
It retains PSQT, `Full_Threats+PP_3Wide+HalfKAv2_hm^`, 1,024/32/32 layers and
eight stacks. Export explicitly uses signed LEB128 compression. Later development
versions change the architecture even when the outer version integer remains the
same; never update this pin or its packages without export/oracle qualification.

The [trainer manifest](../tools/trainer-manifest.json) and
[runtime package manifest](../tools/training-packages.json) record provenance.
Upstream GPL notices, MIT chess/binpack utilities and nodchip/Stockfish-derived
data-format notices remain in the external checkout. No trainer/data-loader or
Stockfish implementation is linked into the chess0live engine. Runtime assets
come from official PyPI and the
[pinned standalone Python release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261021),
with complete hashes/lengths and retained notices. System Python is untouched.

```sh
make test-training
```

These modest tests cover setup/cache recovery, recipes, resource admission,
provenance and report failures. Real training/export/oracle outcomes and current
platform limits are recorded separately in [validation](VALIDATION.md).
