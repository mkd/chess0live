# Inspect and qualify evaluation networks

Use these tools before experimenting with an alternative `.nnue` file. They
run outside the engine and leave its configured network and your GUI build
unchanged. Python's standard library is sufficient: no pip installation or
environment activation is needed.

## Inspect a file

```sh
make network-inspect
python3 tools/network.py inspect /path/to/candidate.nnue
python3 tools/network.py inspect /path/to/candidate.nnue --output inspection.json
```

Omitting the filename selects the pinned default in `networks/manifest.json`.
If it is missing, `make net` downloads and verifies it. Inspection itself never
downloads files or executes a network. It reports the full SHA-256, byte count,
header identifiers, description and known provenance as JSON. `--output` must
name a new file; existing reports are preserved.

`recognized_header` means only that the header identifies the SF19 **SFNNv16**
architecture. The payload may still be truncated, corrupt or unsuitable.
`unsupported` means that the architecture is not supported by this tool;
`malformed` means the recognized header is incomplete or invalid. Descriptions
are untrusted, escaped text, limited to 1,024 displayed bytes. Neither a familiar
filename nor a description establishes the author's identity or training history.

## Verify compatibility

```sh
make network-qualify
python3 tools/network.py qualify /path/to/candidate.nnue
python3 tools/network.py qualify /path/to/candidate.nnue --output results/my-network-check
```

One command builds and runs the complete finite comparison. It needs Git, GNU
Make and a native Clang/GCC compiler accepting C++26 mode. The command discovers
a compiler; `--compiler '/path/with spaces/clang++'` selects a literal executable
path. It does not install a system compiler or Apple's SDK. See the
[build prerequisites](PORTABILITY.md). Compilation uses at most two jobs, further
limited by the local resource policy; evaluation programs run one at a time.

The first run caches the pinned Stockfish 19 reference source under
`.local/networks/sf19-reference/`. Each check builds a separate clean copy inside
its result directory. Stockfish code is used only in that external test program,
never linked into chess0live. Use `--offline` after the source is cached to
prohibit downloads. `--reference-dir PATH` selects a different pinned source
cache, including an existing local oracle checkout. Paths with spaces work.

The check performs full stream decoding and compares the candidate using the
independent chess0live implementation and the pinned SF19 implementation:

- Feature indices, accumulator lanes, activations and every integer layer stage.
- Raw and wrapped evaluation outputs, in both scalar and native backends.
- Incremental versus full-refresh evaluation over the recorded deterministic
  corpus, including ordinary play and special-move positions.

The pinned network additionally runs its existing twelve known-value checks and
parser/backtracking/reset/reload regressions. A different network is not expected
to reproduce those twelve scores; it must agree with the reference using its
**own** weights. The historical `tools/verify_nnue.py --network` command still
requires the exact pinned artifact. Its explicit `--candidate-network` route
provides the new comparison.

Each run writes `report.json` plus the detailed `oracle/` report, logs, corpus,
output digests, source identities and executable hashes. By default the output
is a new timestamped directory under `results/`; an explicit output directory
must not already exist. A failed or interrupted check cannot reuse an old PASS.
The network, provenance and implementation identities are checked for changes
during the run. Preserve a report together with its exact network and build;
rerun qualification after changing weights or evaluator code.

Successful qualification means exact agreement on the recorded corpus. It does
not prove every possible position, training-data quality, a license declaration,
or playing strength. Run tactical and matched-resource game tests before making
a strength decision. A loadable network alone is never described as verified.
New architectures require an explicit decoder/feature/backend implementation and
their own oracle; renaming a network does not convert it.

## Record training provenance

Create a record bound to the network's full SHA-256:

```sh
python3 tools/network.py metadata /path/to/candidate.nnue --output candidate.metadata.json
python3 tools/network.py inspect /path/to/candidate.nnue --metadata candidate.metadata.json
python3 tools/network.py qualify /path/to/candidate.nnue --metadata candidate.metadata.json
```

The template uses schema version 1. The training workflow writes backward-compatible
schema version 2 records with additional work/lineage fields. Fill in only facts
you can support:

| Field | Meaning |
| --- | --- |
| `network_sha256` | Exact artifact identity; changing weights requires a new record |
| `name`, `author`, `license`, `source` | Optional descriptive claims and source location |
| `training.games` | Distinct source games represented in the training data, if known |
| `training.positions` | Position records in the training dataset before epoch repetition; not necessarily unique FENs |
| `training.epochs` | Completed full dataset passes, if known |
| `training.data_sources` | List of source/citation strings for the data and its provenance |
| `training.processed_samples`, `training.steps` (v2) | Samples and optimizer steps in the recorded run; repeats are not unique experience |
| `training.parent_network_sha256` (v2) | Optional exact starting weights; optimizer/full-state resume is a separate capability |
| `training.trainer_commit`, `training.dataset_sha256` (v2) | Pinned trainer and exact input data identities |

Use `null` for unknown text/counts and an empty list for unknown data sources.
Counts must be nonnegative integers; zero means a known zero, not unknown.
All supplied claims are labeled `declared_unverified`. The tool validates their
schema and artifact binding, not their truth. It does not fetch source links.
Pinned upstream licensing/identity remains separate from those declarations.
No training counts are inferred from file size, description, evaluation output,
or the number of games played by the engine. The pinned SF19 network's training
counts are currently unknown in this project's provenance record.

The [local training workflow](TRAINING.md) now creates or fine-tunes compatible
weights and automatically qualifies its exports on the supported CPU host.
Managed network selection remains subsequent work. For an already qualified
compatible file, use the existing UCI option while idle:

```text
setoption name EvalFile value /absolute/path/to/candidate.nnue
isready
```

Check the engine's response for a load error. Qualification does not change this
option or silently replace the default file. Keep network payloads and generated
result directories outside Git; small provenance records may be versioned when
their licensing and data-sharing terms permit it.

## Tool tests and implementation

```sh
make test-network-tools
```

The Python checks cover malformed headers, schema/digest binding, unknown counts,
failure reports, evidence identities, cancellation and output preservation. Real
oracle execution and platform limitations are recorded separately in
[validation](VALIDATION.md). The exact format, feature definitions and pinned
upstream sources are documented in [NNUE interoperability](NNUE.md).
