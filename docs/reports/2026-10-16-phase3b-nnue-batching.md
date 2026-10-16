# Phase 3B: batched NNUE updates — October 16, 2026

**Checkpoint complete: retain batched accumulator updates.** All correctness
gates passed, and the three predeclared timing runs measured 7.8%, 8.0%, and
8.4% higher throughput for identical opening searches. Every root passed the
regression guard. This is a sampled implementation speedup, not an Elo claim.

## Change and preserved behavior

Starting revision: `710523eb1d022d2fd3f14603e83b55993e5a779e`.
Retained implementation commit: `eb059b5`.
The [original protocol](../PHASE_3B.md) was copied into the result directory
before implementation. A single candidate changes only feature-delta application:
stream up to eight feature-column views, apply them to 32 hidden lanes at a time,
and flush until the complete multiset difference is consumed. The capacity
bounds temporary storage, not the number of changed features. Single-column
batches use the previous arithmetic path.

NEON uses non-saturating signed 16-bit operations and signed widening of
relationship weights; the portable path explicitly wraps unsigned lane
representations. PSQT stays modulo-2^32. Feature enumeration/sorting, network
layout, inference, search, time management, and all UCI defaults are unchanged.
No new instruction-set requirement, allocation cache, or accumulator stack is
introduced. The change remains independently implemented.

## Frozen inputs and settings

Host: the same M5 Pro/macOS ARM64 machine as Phase 3A, 18 logical CPUs and
64 GiB RAM. Apple Clang 21.0.0, C++26, generic ARM64 release flags
`-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG`.
All 12 development opening histories are retained in their original order.
Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA, pondering/diagnostics
off, and 20 ms overhead. The pinned runner configures Hash/Threads/EvalFile;
other defaults are checked against the recorded handshake declarations.

| Artifact | SHA-256 |
| --- | --- |
| Frozen Phase 3A baseline | `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44` |
| Batch candidate release | `2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae` |
| Candidate evaluator source | `982401c22195ef86ba29ddebcb86ef25b043b190b2d0c6b6572c2ac6805a4d9b` |
| Pinned SF19 network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Development opening suite | `5cedc1469a43cb7e36dac9ab50379dd42626f9251409f5ad14f4b59919b5ea47` |

All compilation and engine correctness checks finished before comparisons.
The native, scalar, and sanitizer builds each used at most two jobs. Comparisons
use one active search worker, two resident engines, and the ordinary 50% daytime
resource allowance. No sampler, match, or concurrent compiler runs during timing.
No affinity, thermal control, or OS utilization cap is claimed; unrelated host
activity remains an uncontrolled source of timing variation.

## Correctness evidence

All native, forced-scalar, and AddressSanitizer/UndefinedBehaviorSanitizer suites
passed. Coverage includes perft, rules, reversible state, UCI lifecycle, search,
exchange/time/search-policy tests, the 537-position real-network incremental
suite, special moves, sibling/backtracking, reset, reload, and hostile weights.

The new `tests/nnue_updates_test.cpp` adds **360 independent arithmetic
transitions per build**. Its reference counts signed feature multiplicities
and applies whole columns, independently of the production sorted merge and
batch kernel. It checks all 1,024 hidden and eight PSQT lanes for int8/int16
weights, extreme values, duplicate cancellation, empty/singleton/full/partial
batches, arbitrary carried state, and large synthetic changes (up to 32,769
repeated columns). Closed-form overflow anchors supplement the reference.

This independent reference matters: ordinary full-refresh evaluation also uses
`differences`, so incremental/full-refresh agreement alone could hide a shared
batching error. The external Stockfish oracle supplies another independent check.
The **2,057-position** oracle run matched all features, accumulators, PSQT,
transformed input, affine/activation stages, raw outputs, and wrapped outputs
for both native and scalar builds. The corpus and output digests are identical
to the earlier pinned record:

| Oracle artifact | SHA-256 |
| --- | --- |
| Position corpus | `6e48940a6ed8cd8edaedc97580a18840320ae6ee9fad9c8ed1a78f4123431d9e` |
| Canonical integer stages | `4dcca7b66ddb5228ebb2c3ad1b5380f36ee8d0bccdd54e0e94b2488a3f62e1fe` |
| Raw/wrapped scores | `c7a41f1dbfeba274556e579ae0f65e50ae0e5d6a2010d551639d0fbf676d92e3` |

Before timing, all **96 search-parity searches** at depths 5 and 6 matched every
completed iteration's depth, selective depth, nodes, score and PV, plus bestmove
and ponder. Independent legal replay checked 528 PV lines / 1,916 PV plies and
all 96 bestmoves and ponder replies. There were 48 searches at each depth,
including warmups, covering every development root and both binaries.

## Timing decision

The candidate passed every predeclared engineering gate. Each of the two
seven-repetition depth-5 runs and the three-repetition depth-6 run exceeded the
required **1.03 aggregate median** baseline/candidate elapsed ratio. All 24
pooled root/depth medians exceeded **0.98**; the lowest were **1.069335** at
depth 5 and **1.064953** at depth 6. No rule or implementation parameter changed
after timing began, and no run was discarded or repeated to improve the outcome.

| Run | Measured pairs | Median ratio | Paired MAD | Individual ratio range |
| --- | ---: | ---: | ---: | --- |
| Depth 5 A | 84 | 1.078081 | 0.010193 | 1.042722–1.133481 |
| Depth 5 B | 84 | 1.079836 | 0.009110 | 1.058080–1.115824 |
| Depth 6 | 36 | 1.083612 | 0.008573 | 1.050870–1.151320 |

A ratio above one favors the candidate. The ratios correspond to approximately
7.2–7.7% less elapsed time for the same search work; throughput and elapsed-time
percentages use different denominators. These are descriptive measurements,
not confidence intervals or a universal noise bound.

Baseline-first/candidate-first median ratios were 1.077720/1.078539 (depth 5 A),
1.076351/1.081148 (depth 5 B), and 1.083208/1.084068 (depth 6). No individual
measured pair was slower for the candidate. Host background activity and the
related development roots still limit generalization.

All roots are shown below. Depth-5 rows pool the two declared timing runs
(14 pairs/root); depth-6 rows contain three pairs/root. Each ratio is the median
of paired ratios, not the quotient of the two independently calculated time
medians. Times are external go-to-bestmove round trips in milliseconds.

| Development root | D5 baseline / batch ms | D5 ratio | D6 baseline / batch ms | D6 ratio |
| --- | ---: | ---: | ---: | ---: |
| 01 | 205.8 / 189.9 | 1.078827 | 1041.8 / 961.9 | 1.088206 |
| 02 | 500.0 / 466.3 | 1.071799 | 2740.2 / 2544.3 | 1.077116 |
| 03 | 533.3 / 498.1 | 1.069383 | 2564.5 / 2366.2 | 1.083793 |
| 04 | 382.5 / 355.4 | 1.077147 | 1730.8 / 1592.2 | 1.081339 |
| 05 | 425.4 / 397.9 | 1.069335 | 1889.0 / 1757.3 | 1.074943 |
| 06 | 486.0 / 444.9 | 1.092187 | 2906.6 / 2657.1 | 1.094731 |
| 07 | 185.8 / 168.8 | 1.098909 | 909.9 / 829.9 | 1.108568 |
| 08 | 189.1 / 175.5 | 1.079081 | 957.2 / 898.8 | 1.064953 |
| 09 | 185.5 / 170.2 | 1.089014 | 845.3 / 766.8 | 1.093473 |
| 10 | 382.8 / 355.2 | 1.076445 | 1743.9 / 1622.0 | 1.081168 |
| 11 | 414.2 / 383.1 | 1.084140 | 3946.9 / 3603.0 | 1.096466 |
| 12 | 466.4 / 432.8 | 1.079247 | 2317.4 / 2139.4 | 1.088263 |

Including the earlier correctness comparisons, the independent data-only audit
verified **576 searches** (120 warmups, 456 measured), **3,024 PV lines /
10,572 legal PV plies**, and all 576 bestmoves and ponder replies. It reparsed
raw UCI replies, checked exact signatures across binaries/repetitions/runs,
recomputed timing summaries and gates, verified options evidence, and checked
input hashes before/after. All checks passed without errors. Its options claim
is based on recorded handshakes and the pinned runner's setup logic, not a
complete outgoing command transcript.

Two in-memory negative checks also passed: the auditor rejected altered ratio
metadata and an illegal warmup PV. Raw comparison files were not modified.

The 480-search acceptance timing campaign took approximately 5 minutes 20 seconds
including orchestration, sequentially under the ordinary daytime allowance.
Every comparison stayed inside its 30-second per-search and ten-minute outer
bounds. All jobs have ended. No match or schedule was started.

**Decision:** retain the one candidate. The ordinary native build was rebuilt
after timing and is byte-identical to the frozen tested release executable.
The GUI snapshot `0.1-dev-4b8b35d`, all Phase 2 candidates, the Phase 3A baseline,
and the pinned network remain unchanged. A GUI retest is optional, not a gate
for these arithmetic changes; earlier GUI feedback still refers to its old
snapshot. No new release version is declared by this research checkpoint.

**Next checkpoint: Phase 3C — broader game-phase performance validation.**
Freeze a small original middlegame/endgame suite by structural coverage before
examining candidate results, establish same-baseline repeatability there, and
compare the retained implementation with exact-search/legal-PV checks and
predeclared regression guards. This follow-up has not started. Clock-managed
playing strength, multicore search, and other-platform execution remain separate.

## Retained evidence and reproduction

Local evidence is in ignored `results/phase3b-20261016/`: original protocol,
source/asset manifests, candidate patch, test logs, oracle report, exact command
records, full comparison data, and independent legal replay. Candidate build
configurations are under `build/experiments/phase3b-20261016/`.
The separate reference and full dumps are in `build/nnue-oracle-phase3b-20261016/`;
the original oracle directory was preserved.

Use the [benchmark guide](../BENCHMARKING.md) with the frozen binaries, full
position histories from Phase 3A, and the exact Phase 3B repetition/timeout
settings. Choose fresh output paths; retain interrupted or unfavorable runs.
The full oracle command was:

```sh
python3 tools/verify_nnue.py --compiler /usr/bin/clang++ --jobs 2 \
  --reference-arch apple-silicon \
  --work-dir build/nnue-oracle-phase3b-20261016 \
  --network networks/nn-1a298aa575a0.nnue
```

For another run, use a new oracle work directory, copying only the existing
reference checkout and its build-config stamp if avoiding a download. Never
symlink the reference: the harness modifies its isolated test adapter and builds
in place. No upstream engine code is linked into chess0live.

These measurements cover shallow opening search on one ARM64 host. They do not
establish an Elo gain, performance across all game phases, clock-managed strength,
scalar or other-platform throughput, or new foreign-platform runtime validation.

Evidence pins (paths relative to `results/phase3b-20261016/`):

| Record | SHA-256 |
| --- | --- |
| `protocol.md` | `7c52bd3f67ed012f66ac79c78c261311d6693a61d4705a49ad1878ea132cf617` |
| `candidate.json` | `c22b7f6ac75f38baac55f8dbe958b502b1380429068987c5ee81730657408de8` |
| `nnue-oracle-report.json` | `a6e5ee4ab9bfad8c0652cf128b7fb6c976e8c82d49604e18f88276ebc7198678` |
| `correctness-replay.json` | `a9f8501d2aafd399b95c471e45bd5988d196bae6dc33328ff3c28429d6447bf5` |
| `timing-depth5-a.json` | `1b4e3a7d5876db2b3b383dedccb83e93318faece5da88cbc65fecbcfea561832` |
| `timing-depth5-b.json` | `48411eb10e83ed1f5eb43557f0f3cc659f76612f7372012d33be0d85a78c8142` |
| `timing-depth6.json` | `64adb3d3a873109c600f1382a88bf13a430d1062a998d040d85b51a812e75b56` |
| `audit.json` | `4b02bd9df98b42a25999ed740764e452c1ae5de37680b4892a6e638727e4013a` |
| `audit-tamper-checks.json` | `928debd0f3e1a77c3aea82d36a741a4847d0568b5799256b33c67393f1ca025f` |
