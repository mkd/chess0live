# Phase 3A: default-engine performance baseline — October 16, 2026

**Checkpoint complete: NNUE accumulator updates are the first optimization
target.** All 192 same-binary timing searches and 48 release-versus-symbol-build
searches matched exactly. Independent replay confirmed every reported PV,
bestmove, and ponder move was legal. A separate CPU sample attributed about
85% of active-search observations to NNUE evaluation and 59% to its update
subtree. No engine implementation, default, release version, or strength claim
changed in this checkpoint.

The next step is the bounded [Phase 3B batching proposal](../PHASE_3B.md).
It is a hypothesis with correctness/timing gates, not an implemented speedup.

## Inputs and execution

Source revision: `9daaade`. Host: Apple M5 Pro, 18 logical CPUs, 64 GiB RAM,
macOS 26.7.1 ARM64. Apple Clang 21.0.0, C++26 mode, generic ARM64 release
flags `-O3 -DNDEBUG`; the profiling build adds `-g` and a separate dSYM.
The release executable is byte-identical to the frozen Phase 2C capture-ordering
executable; its experimental options remain disabled.

| Artifact | SHA-256 |
| --- | --- |
| Release executable | `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44` |
| Optimized symbol executable | `4b317d64ae6b1706663e62e73e033eca1def31dc1b71eafe524085561381565c` |
| Pinned SF19 network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Development opening suite | `5cedc1469a43cb7e36dac9ab50379dd42626f9251409f5ad14f4b59919b5ea47` |

The [protocol](../PHASE_3A.md) was fixed and copied to the result directory
before measurements. All 12 development histories were used in their original
order and checked with `chess==1.11.2`. Settings: Threads 1, Hash 64 MiB,
classic timing, LMR off, MVV-LVA, ponder and diagnostics off, 20 ms overhead.
The comparison harness's advertised defaults were verified; the CPU recorder
explicitly set every option. No fresh validation suite or match was used.

One worker searched at a time, with two resident engines for comparisons and
one for sampling, under the 50% daytime policy. Compilation and correctness
checks finished before timing. There was no CPU affinity, thermal control, or
OS utilization cap, and unrelated applications were not controlled.

## Repeatability and equivalence

Depth 5, seven measured repetitions, and one warmup per root/role produced
**192 same-binary searches**, including 24 warmups and 84 measured pairs.
The run took 67.700207 seconds including orchestration; measured search
round trips totaled 58.079571 seconds. All completed iteration depths,
selective depths, nodes, scores, PVs, bestmoves, and ponder moves matched.

| Timing observation | Value |
| --- | ---: |
| Median baseline/candidate ratio | 0.998546 |
| Paired ratio median absolute deviation | 0.008123 |
| Individual ratio range | 0.960897–1.041423 |
| Baseline-first / candidate-first group medians | 0.998300 / 0.999384 |
| Last / first complete sweep duration | 1.001906 |
| Per-root median release search time range | approximately 176–507 ms |

Ratios center near one, with no conspicuous directional order/drift pattern
in this sample. These describe observed variability, not statistical confidence
or a universal noise bound. The roughly 0.8-percentage-point paired MAD is
planning context for future timing gates. Small differences require caution.

The separately optimized symbol build matched the release build in all
**48 searches**, using one measured repetition and one warmup per role/root.
An independent audit replayed all 240 searches' per-iteration PVs, bestmoves,
and ponder moves. Symbol-build timings are not a product performance claim.

## CPU attribution

The macOS sampler targeted PID 49776, ARM64 executable UUID
`8DC9812F-84DD-3BD3-AAF0-86BFD080FCD6`, matching the symbol build. Requested
window: 120 seconds, interval: 1 ms. After 12 warmups, all 24 depth-5 searches
completed within the conservative observed sampler window and matched the
release signatures. Their recorded round trips totaled 8.628508 seconds;
those perturbed timings are not used as throughput evidence.

The raw call tree contains 24 worker threads and 7,414 worker observations.
Of these, **7,413 lie within `Search::search`**; one thread-start observation
is excluded. The main thread's 105,134 observations, predominantly waiting for
input, are also excluded. Keeping the engine alive after the sweep accounts
for much of that idle time. The denominator below is the 7,413 search-subtree
observations, not elapsed milliseconds or all-thread counts.

| Disjoint search category | Observations | Share |
| --- | ---: | ---: |
| NNUE evaluation | 6,304 | 85.04% |
| Legal move generation | 870 | 11.74% |
| Move ordering | 160 | 2.16% |
| Other search work | 79 | 1.07% |

Within NNUE, inclusive `update` cost was **4,351 observations (58.69% of
search)** and inference was **1,935 (26.10%)**. Feature-integer sorting accounted
for 922 observations (12.44%), geometry for 233 (3.14%), and allocator subtrees
across search for 130 (1.75%). These inclusive figures overlap their parents;
do not add them to the disjoint table.

Aggregation uses each call-tree node's count minus its direct children's counts
as residual weight, classifies each residual once by ancestry, and checks the
total against the outer search frames. An independent aggregation agreed.
Optimized code inlines feature enumeration and delta application into `update`;
its inclusive cost must not be presented as the cost of only one suboperation.
Source-line attribution suggests delta application merits investigation, but
does not prove that hidden-vector memory traffic dominates. Aggregate stacks
also cannot prove how many observations each individual root contributed.

The selected experiment batches the same feature-column additions/removals
while preserving modulo arithmetic and arbitrary-position-transition behavior.
It leaves feature enumeration and search unchanged. Allocation-only buffer reuse
was previously inconclusive, and the present allocator share does not justify
simply repeating that experiment. Broader accumulator stacks or dirty-piece
maintenance would be a separate, larger change.

## Validation, failures, and limits

Native release position/perft, NNUE, search, exchange, time-policy, search-policy,
UCI, and resource checks passed. The first nested-bundle PATH smoke failed
because the default network was not adjacent to that custom build directory.
Adding a symlink to the pinned network fixed the packaging setup; `test-core`
then passed without changing engine code. Both logs are retained.

All 11 benchmark-tool checks and 16 CPU-recorder mock tests passed. The latter
cover fixed options, legal output, bounded sampling, partial failure records,
resource changes, artifact drift, and helper cleanup. The first real sampling
attempt was denied process inspection by the sandbox; its failed record is
retained. The explicitly approved retry completed normally with no artifact
drift. All engine, network, build, and benchmark source hashes matched before
and after measurements; later Makefile test-target/documentation edits are
separate from this frozen record.

No C++ engine source changed. Scalar/sanitizer/full SF19 oracle suites were not
rerun for this measurement-only checkpoint; their earlier evidence is not
relabeled as new testing. All five preserved engine/network assets, including
GUI snapshot `0.1-dev-4b8b35d`, stayed intact. No GUI retest is needed, and no
engine or sampling job remains active.

This covers shallow opening search on one M5 Pro. Inlining, sampling overhead,
transport/scheduling, related roots, and uncontrolled host activity limit
inference. Fixed-depth searches omit the active per-node clock-management path.
No speed improvement, Elo gain, complete release, or other-platform runtime
verification follows from this checkpoint.

## Reproduction and retained evidence

With the frozen executables present, the following reproduces the comparison
inputs and settings in a **new** directory. A fresh clone must first build the
pinned engine revision with the recorded compiler/flags; do not overwrite the
original artifacts. These commands run work and are not a schedule.

```sh
mkdir results/phase3a-rerun
python3 - <<'PY'
import json
from pathlib import Path
document = json.loads(Path('tests/data/openings-development.json').read_text())
lines = ['startpos moves ' + ' '.join(root['moves']) for root in document['openings']]
with Path('results/phase3a-rerun/positions.txt').open('x') as output:
    output.write('\n'.join(lines) + '\n')
PY
python3 tools/compare_bench.py \
  --baseline build/experiments/phase3a-20261016/release/chess0live \
  --candidate build/experiments/phase3a-20261016/release/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --positions results/phase3a-rerun/positions.txt \
  --depth 5 --repeats 7 --hash-mb 64 --search-timeout 20 \
  --output results/phase3a-rerun/repeatability.json
python3 tools/compare_bench.py \
  --baseline build/experiments/phase3a-20261016/release/chess0live \
  --candidate build/experiments/phase3a-20261016/symbols/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --positions results/phase3a-rerun/positions.txt \
  --depth 5 --repeats 1 --hash-mb 64 --search-timeout 20 \
  --output results/phase3a-rerun/symbols-equivalence.json
python3 tools/profile_cpu.py \
  build/experiments/phase3a-20261016/symbols/chess0live \
  --output results/phase3a-rerun/cpu-sample \
  --duration 120 --depth 5 --repeats 2 --search-timeout 20
```

Apply the protocol's ten-minute outer bound to each comparison. Audit output
signatures, legal PVs, raw sampler identity, and stack accounting independently;
successful recording alone is not an interpretation of CPU costs.

All paths below are relative to ignored `results/phase3a-20261016/`:

- `manifest.json`, `protocol.md`, and `positions.txt`: source/build/host/input pins.
- `repeatability.json` and `symbols-equivalence.json`, corresponding command
  JSON files and logs: every timing sample and exact search signature.
- `repeatability-audit.json`: independently replayed search output and statistics.
- `cpu-sample/`: the denied attempt; `cpu-sample-authorized/`: completed report,
  full raw stacks, exact options, root boundaries, and sampler log.
- `analyze_cpu.py`, `cpu-analysis.json`, and `cpu-audit.json`: retained aggregation
  recipe and two independently produced interpretations.
- Build/test logs and `final-integrity.json`: actual checks, setup failure,
  correction, and unchanged source/asset verification.

Preserve the whole directory and both build directories. Use the commands in
the [benchmark guide](../BENCHMARKING.md) and fixed [protocol](../PHASE_3A.md),
choosing new output paths. CPU attribution requires macOS process-inspection
permission; the engine and ordinary comparison harness do not depend on it.
Evidence SHA-256 pins preserve the connection between this summary and the
locally retained records:

| Evidence | SHA-256 |
| --- | --- |
| Frozen protocol | `dc57effe85d66f4b316b26783248c0af46f41b4791d6f6b330c2d7f1b14abde8` |
| Repeatability data | `8592b57671027b357dfb66cc2fac63ce553fa561f5670ccca5418bf89d735638` |
| Symbol-equivalence data | `c809f537371829f60abc35f4a5cf93169645d85f7c69014e7f863828c9c87a87` |
| Independent benchmark audit | `ed36b3ba93bd430daae53f49b994ae507f79d8638a16bc5dfe49f926c4e6721e` |
| Successful CPU recorder report | `6fdb8754261339e6e60ab6a84842e461786741b7f8265c0284c4fdb114ef3e7e` |
| Raw CPU sample | `190f6ae4e7afb79b46647d20537480763e2ab4eaf0bf396412cd6f66dfeab7a9` |
| Independent CPU audit | `d3a0338f92a51710daa675bcd4f87a7825b28a668c45365dcd7b0c5de1f64270` |
