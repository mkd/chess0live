# Compare performance without changing search work

Use `tools/compare_bench.py` for implementation changes that should preserve
evaluation and search decisions. It compares two explicit frozen binaries at
fixed depth. It is not suitable for measuring the strength of a new pruning
rule, search heuristic, or evaluator that deliberately changes the searched
tree; use [paired matches](MATCHES.md) for those experiments.

Example using the preserved local test snapshot:

```sh
python3 tools/compare_bench.py \
  --baseline build/test-baselines/0.1-dev-4b8b35d/chess0live \
  --candidate build/macos-arm64-generic-release/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --depth 6 --repeats 7 --search-timeout 30 \
  --output results/comparison.json
```

Choose an unused output path each time. Snapshots are local; a fresh clone must
first build and preserve its comparison binary. The helper needs only Python's
standard library. `make test-bench` checks its parsing, comparison invariants,
resource planning, and preservation of incomplete evidence.

Both processes remain loaded with identical networks, one search thread, and
64 MiB hash by default. Before each search, the table is cleared and readiness
completes. One warmup per position and binary is excluded from statistics.
Measured runs alternate binary order across positions and repetitions. The
default is three development positions; `--positions` accepts the same UCI
position-body file format as `tools/bench.py`.

Every completed iteration must agree on depth, selective depth, node count,
score, and principal variation; best move and ponder move must also agree.
A mismatch or timeout invalidates the performance comparison and preserves raw
output. This sampled equality supplements the independent NNUE oracle; it does
not prove universal equivalence on every possible position.

The report records file/tool hashes, options, inputs, platform, individual times,
and observed variation. A speed ratio is baseline elapsed time divided by
candidate elapsed time, so values above one favor the candidate. Median,
minimum, maximum, and median absolute deviation describe the observations;
they are not confidence intervals. Fixed-depth NPS or speed ratios are not Elo.

Two processes remain resident, but only one searches at a time. The runner
checks a conservative combined memory estimate and rereads the local resource
budget between searches. The estimate is not an OS-enforced utilization cap.
Avoid concurrent engine testing, compilation, or other heavy work when collecting
timings intended for a performance claim. Manual GUI testing can otherwise
continue independently using its preserved copy.

Declare the positions, depth, repeat count, and decision criterion before a
comparison. If a follow-up is needed because variation obscures the result,
record that fact and preserve both runs. Never discard an unfavorable run or
present exploratory tuning as a predeclared statistical strength experiment.

## Broader game-phase results

The [Phase 3C protocol](PHASE_3C.md) adds an original composed middlegame/endgame
suite with predeclared same-binary noise controls, duration floors, and root
regression guards. The [completed report](reports/2026-10-16-phase3c-gamephases.md)
preserves every root and all six runs: middlegames qualified; endgame inference
remains inconclusive because one pawn root was below the 50 ms floor. Do not
remove short roots or repeatedly adapt the workload after candidate results.
Any revised workload needs a separately frozen protocol and preserved evidence.

The [Phase 3D ladder](reports/2026-10-17-phase3d-workload.md) characterized that
same pawn root using only the baseline at depths 8–12. All 40 searches matched
exactly and replayed legally. Depth 12 meets the diagnostic proposal rule at
323–330 ms; three measured pairs and a near-limit MAD require fresh noise
controls in the future comparison. Depth 10's timing instability is preserved.
No candidate endgame qualification followed from this diagnostic alone.

The separately frozen [Phase 3E comparison](reports/2026-10-17-phase3e-endgames.md)
subsequently qualified all six revised endgames, with 1.089113/1.084243 complete
round ratios and 216 exact/legal searches. It pools 30 individual pairs per
round across depth groups, not an average of group medians. Fresh controls and
all duration/root guards passed. Two candidate slowdowns and absolute-time drift
remain recorded; Phase 3C's earlier decision is unchanged. No data from the
older campaign is pooled into this result.

## CPU attribution on macOS

`tools/profile_cpu.py` records bounded CPU samples of the default engine using
the built-in `/usr/bin/sample`. It is a development tool for macOS; the engine's
platform support does not depend on this sampler. Install `requirements-match.txt`
for independent legal-history and PV replay. Build with release optimization
and symbols in a separate directory, preserving the normal and GUI executables:

```sh
make -j2 BUILD=build/profile-symbols \
  CXXFLAGS='-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g'
xcrun dsymutil build/profile-symbols/chess0live
python3 tools/profile_cpu.py build/profile-symbols/chess0live \
  --output results/cpu-profile-new --duration 120 --depth 5 --repeats 2
```

First verify sampled search equivalence against the ordinary release build
with `compare_bench.py`. The recorder explicitly pins classic timing, LMR off,
MVV-LVA, Threads 1, Hash 64, Ponder and diagnostics off, and Move Overhead 20 ms.
By default it uses all 12 development roots. `--positions` accepts 1–64 distinct
legal, nonterminal roots in the opening-suite JSON format, preserving complete
move histories. An entry may set an integer `profile_depth` from 1 through 12 to
override `--depth` for that root's sampled searches. All roots receive one fixed
depth-5 warmup before sampling; overrides do not change warmups. The report
records each chosen depth in `positions` and `settings.position_depths`.
The recorder waits for the sampler's startup message, records full output and
monotonic boundaries for each search, and keeps the target idle afterward until
sampling completes naturally. Input validation finishes before starting the
engine, including root uniqueness, draw status, histories and depth ranges.

Outputs are `report.json`, `sample.txt`, and `sampler.log` in a new directory.
Failures, incomplete searches, changed assets, and late sampling coverage remain
recorded; existing output is never overwritten. On systems that deny process
inspection, grant permission through the host's normal approval mechanism and
use a fresh directory for another attempt. `make test-profile-cpu` checks the
recorder's settings, evidence validation, and process cleanup with mocks.

Inspect the raw sample's target identity, requested interval, and useful active
search stacks before interpreting it. The recorder checks lifecycle and window
coverage but does not parse Apple's stack format. Aggregate stacks cannot prove
that every root contributed an observation. Exclude idle/readiness stacks from
the active-search denominator; do not add nested inclusive costs. Sampling
perturbs execution and is separate from throughput timing. Fixed-depth searches
do not measure the active clock-management path or establish an Elo improvement.
See [Phase 3A](PHASE_3A.md) for the original opening-only checkpoint.
