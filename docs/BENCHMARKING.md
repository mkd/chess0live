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
