# Phase 4F.17 — NNUE accumulator reuse

Date: November 4, 2026. Parent: `7163b1ff0f1bb52feb18daefdbe13dc89494f266`;
engine source unchanged from `e16ca73`. Decision: **park the checkpoint candidate
and retain the parent engine**. The independent audit passed result validity,
but all three timing blocks missed the declared improvement gate, and one
root/state failed its slowdown guard. No strength gain is established.

The [diagnosis protocol](../experiments/phase4f17-nnue-reuse.md) and
[candidate protocol](../experiments/phase4f17-checkpoints.md) were declared before
their respective measurements. The owner confirmed LM Studio paused, AC power
and Automatic mode. Work used native macOS ARM64 and at most two compiler jobs.
Profiling/timing used one active search worker, with no competing builds or
tests; bounded parallel correctness checks separately used up to four workers.
No games, clock qualification, default promotion or automatic schedule ran.

## Diagnosis and bounded candidate

The current-parent CPU profile covered all fifteen exposed development roots:
one depth-5 warmup and two depth-6 measured searches per root, Threads 1,
Hash 64 MiB, pinned network, accepted LMR-on/null-off settings and diagnostics
off. The sampler ran for 60 seconds at 1 ms intervals; each search had a
20-second limit. Independent replay accepted all **45 searches / 255 iterations /
1,066 legal PV plies / 45 bestmoves and ponders**, verified eleven assets and
27 archived parent sources, and passed eight parser-corruption checks.

The measured sweep occupied **10.512604 seconds**. The sample contained **5,210
active-search observations across 23 sampled worker threads**; the 52,255
main-thread observations, including the idle tail, were excluded. Disjoint
active attribution was NNUE **85.20%**, legal move generation **10.48%**, move
ordering **2.15%**, and other search work **2.17%**. Overlapping inclusive shares
were feature planning **28.10%**, accumulator application **33.57%**, their
combined share **61.67%**, and inference **20.96%**. Feature discovery (**15.32%**),
feature integer sorting (**7.10%**) and allocation (**4.26%**) are overlapping
subcategories, not additional disjoint costs.

This justified one bounded reuse experiment. It did not prove an achievable
speedup: only 23 short-lived workers received samples for 30 measured searches,
so per-root stack coverage is not established; source-line attribution is
compiler-dependent, inclusive counts overlap, and sampling perturbs execution.
The profiling harness records the sampler's zero exit but not the engine's exit
status. Separate OS inspection confirmed the recorded engine PID absent and no
chess/sampler process remaining; this does not manufacture a missing exit code.

The independently authored candidate allocated **128 worker-private checkpoints**
before search dispatch. Each held both numeric accumulators, the saved board and
validity metadata, without copying active-feature vectors. It saved only an
already-evaluated, nonchecked quiescence parent whose stand-pat did not cut off
and whose tactical move list was nonempty. It never forced an evaluation just
to fill a cache. Every actual main-search/quiescence entry invalidated its slot,
including unevaluated nodes. Evaluation could restore the nearest valid ancestor;
both potentially throwing feature-update plans were prepared before numeric
state was copied or changed. Identical current piece placement kept the existing
path; actual side and clocks still fed inference/calibration. Reset and network
generation changes invalidated saved state; failed reload kept the valid network.

Measured `sizeof(AccumulatorCheckpoint)` was **4,480 bytes**, including alignment,
board and metadata: **573,440 bytes (0.546875 MiB) per worker** for 128 slots,
or **4,587,520 bytes (4.375 MiB) for eight workers**. This is additional checkpoint
array storage, separate from Hash, existing accumulator/feature storage, vector
control and allocator overhead; it is not measured peak RSS. Standalone evaluators
allocated zero checkpoint slots. No search score, bound or policy was cached.

## Correctness and preparation

Native, forced-scalar and ASan+UBSan builds each passed the same NNUE checks:

- **351 checkpoint-path lane/output visits, 299 actual ancestor restores, five
  rejected saves and two injected feature-plan allocation failures**. The checks
  inspect the actual internal runtime state and exercise the public evaluator.
  Both perspectives' entire hidden/PSQT arrays, feature multisets and raw/wrapped
  outputs agree with full refresh. Cases cover descendants, siblings, nearest
  ancestors, skipped parents/stale slots, arbitrary transitions, same-occupancy
  different pieces, side/rule50 metadata, null/undo, king orientations, castling,
  en passant, promotions, bounds, reset, changed-weight reload and failed reload.
  Both injected preparation failures preserve current and saved state; retry
  restores correctly. Snapshot save/invalidation/reset allocate no storage.
- Existing **1,273 feature transitions** included 2,055 incremental plans,
  491 refresh plans and 28 unchanged-board transitions. The parser/evaluator
  covered 537 incremental/full-refresh positions and malformed/unloaded cases;
  update arithmetic covered 360 multiset transitions; dense arithmetic covered
  1,515 cases and 84,126 repeated-call output comparisons.

Native, scalar, ASan+UBSan and ThreadSanitizer each passed the general Search API
and policy checks, **2,264 ordering comparisons**, **1,408 history-prefix
comparisons**, **23 TT-hint groups with three injected allocation failures**, and
**36 continuation-history search groups with five injected allocation failures**.
The continuation table also passed 2,401,659 checks. Native and ThreadSanitizer
each passed **43 bounded SMP searches/lifecycle cases**. Existing search checks
cover interruption/reuse, node/clock/stop limits and worker isolation. Native
optional null, ProbCut, quiescence SEE and reverse-futility regressions passed,
including interrupted speculative searches and one/four-worker composition.
Position/perft/state restoration, **8,018 tactical-generation comparisons**,
**4,117 exchange comparisons**, **145,024 attack-mask comparisons**, time policy,
UCI and resource-policy checks passed after the fixture correction below.
The unchanged profiler passed **29 engine-free tests**.

A fresh isolated offline oracle run passed **2,057 positions**, native and scalar,
against Stockfish reference `edb0d9db6731067ec50ce619ff372b463bc4dd5d` with pinned
network `nn-1a298aa575a0.nnue`: features, accumulators, layers, raw and wrapped
outputs agreed exactly. The external adapters use full refresh; the checkpoint
checks above separately establish the new incremental path. This verifies the
pinned integer arithmetic, not network provenance, cross-target execution or Elo.
Independent source review recorded no blocking findings before the timing freeze.

One recorded preparation failure is retained: the native combined check command
stopped in the UCI temporary-working-directory fixture, where the deeply nested
isolated bundle could not discover the default network and returned `bestmove
0000`. The same failure reproduced with the parent binary. A symlink to the
pinned network was added to the candidate bundle; the unmodified UCI suite then
passed, and the remaining checks ran separately. The engine implementation and
test expectations were not changed to hide the failure. `checks.json`,
`candidate-1.log`, `path-reproduction.json`, `checks-v2.json` and the freeze receipt
preserve the failure, diagnosis and correction. This is the complete correction
known from the saved receipts, not a claim about unrecorded attempts.

## Frozen timing screen

The four declared blocks ran **17:47:30–17:49:43 Helsinki**: one parent/parent
control with two cold/warm repetitions per root, then exactly three alternating-
order parent/candidate blocks with three repetitions. The complete screen contains
**660 searches / 330 pairs** across all fifteen roots. Settings were depth 6,
Threads 1, Hash 64 MiB, pinned network, accepted defaults and diagnostics off;
two engines were resident and only one searched at a time. Each search had a
15-second limit, each block a 300-second search/setup bound. Final cleanup and
hash publication fall outside that bound. No observation was discarded,
replaced, added or used to retune the candidate.

Ratios are parent elapsed / candidate elapsed; above one favors the candidate.
The control pooled median **1.000958776** passed its inclusive 0.98–1.02 gate.
All candidate pooled medians—**1.016390556, 0.999866636, 1.004984039**—failed the
required **1.03 in every block**. Cold `gamephases-eg-02` pooled median
**0.977998564** also failed the **0.98** minimum; it was the only failing one of
thirty root/state guards. Both candidate acceptance requirements therefore failed.

| Block | Searches / pairs | Pooled median | Observed range | Geometric mean | Median absolute deviation |
| --- | ---: | ---: | ---: | ---: | ---: |
| timing-control | 120 / 60 | 1.000958776 | 0.957865–1.085909 | 1.001778 | 0.012254 |
| timing-1 | 180 / 90 | 1.016390556 | 0.937951–1.406115 | 1.024289 | 0.025977 |
| timing-2 | 180 / 90 | 0.999866636 | 0.799480–1.338989 | 1.003151 | 0.021901 |
| timing-3 | 180 / 90 | 1.004984039 | 0.741223–1.142962 | 1.009270 | 0.018712 |

| Block | State | Pairs | Median paired ratio | Aggregate elapsed ratio | Parent / candidate seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| timing-control | cold | 30 | 1.001183 | 1.008545 | 9.846920 / 9.763487 |
| timing-control | warm | 30 | 1.000672 | 0.997172 | 1.883244 / 1.888585 |
| timing-1 | cold | 45 | 1.011558 | 1.037529 | 14.910128 / 14.370810 |
| timing-1 | warm | 45 | 1.020761 | 1.041282 | 2.861930 / 2.748468 |
| timing-2 | cold | 45 | 0.990790 | 1.011216 | 15.325966 / 15.155982 |
| timing-2 | warm | 45 | 1.002073 | 1.029468 | 2.967628 / 2.882683 |
| timing-3 | cold | 45 | 1.002326 | 1.027342 | 15.062674 / 14.661795 |
| timing-3 | warm | 45 | 1.008966 | 1.042418 | 2.924007 / 2.805023 |

The control searched 3,701,668 cold and 790,712 warm nodes per role; each candidate
block searched 5,552,502 cold and 1,186,068 warm nodes per build. Aggregate elapsed
ratios do not override the predeclared median and per-root gates. The control is
a host sanity check, not proof of statistical significance or removal of timing
noise. Small endgame searches and the broad individual ranges warrant caution.

Each following cell gives the median and full observed range of **nine** paired
ratios pooled across the three candidate blocks; the control is excluded.

| Root | Cold median (range) | Warm median (range) |
| --- | ---: | ---: |
| opening-01 | 0.998409 (0.966847–1.013322) | 1.000434 (0.965199–1.029783) |
| opening-02 | 1.017370 (0.978641–1.115296) | 1.030266 (0.970161–1.045523) |
| opening-03 | 1.038020 (0.937888–1.056345) | 1.026665 (0.799480–1.041950) |
| gamephases-mg-01 | 1.008952 (0.915174–1.024715) | 1.006451 (0.979474–1.027581) |
| gamephases-mg-02 | 1.059746 (1.026785–1.087841) | 1.079114 (1.061941–1.098808) |
| gamephases-mg-03 | 1.020624 (0.983055–1.064080) | 1.051919 (1.023298–1.094204) |
| gamephases-mg-04 | 1.059105 (0.976586–1.076788) | 1.066167 (1.006166–1.142962) |
| gamephases-mg-05 | 1.006610 (0.990157–1.026598) | 1.005720 (0.984434–1.338989) |
| gamephases-mg-06 | 0.995172 (0.963612–1.027270) | 1.008412 (0.950682–1.052946) |
| gamephases-eg-01 | 0.990296 (0.907138–1.001049) | 0.991950 (0.741223–1.017766) |
| gamephases-eg-02 | 0.977999 (0.945507–0.996693) | 0.985708 (0.904515–1.072327) |
| gamephases-eg-03 | 0.984485 (0.968281–1.008160) | 0.985176 (0.937951–1.021366) |
| gamephases-eg-04 | 0.982103 (0.963404–1.003563) | 0.985636 (0.968936–1.022368) |
| gamephases-eg-05 | 0.998997 (0.971264–1.406115) | 1.016397 (0.972465–1.329211) |
| gamephases-eg-06 | 0.998903 (0.976402–1.053099) | 0.997993 (0.980205–1.027279) |

## Independent audit, restoration and limits

The independent timing audit accepted all **660 cells / 330 pairs / 3,960
iterations / 17,072 legal PV plies / 660 bestmoves and ponders**, 37 assets per
block, 27 archived parent sources and 30 frozen candidate source/protocol entries.
Completed depth, selective depth, nodes, score, PV and final moves agreed exactly
across both roles, repetitions and all four blocks. Hash occupancy was range-
checked but excluded from signatures. The auditor passed one valid parser case,
nine parser-corruption rejections, eight gate-boundary/failure checks and four
matrix-corruption rejections. Audit validity passed; **timing acceptance failed**.

These are finite exposed development observations with no confidence interval,
Elo estimate or general speed/strength conclusion. Quiet-host status is the
owner's declaration, not continuous external-load measurement. Timed diagnostics
were disabled: the run establishes search parity, not the frequency or savings
of actual checkpoint restores. The unit tests demonstrate positive reuse, but
this screen does not attribute the weak result to cache copying, invalidation,
allocation or another specific cost. Setup/readiness are excluded from measured
search elapsed time. No tactical/clock/strength qualification follows a failed
development gate, and there is no within-phase retuning.

All **eight recorded comparison engine PIDs exited zero**. The cleanup receipt
confirms their absence by OS inspection and no remaining chess/build/sample
process; LM Studio was released. All four candidate implementation/test files
were restored byte-for-byte to parent `7163b1f`. Candidate sources, patch, isolated
executables, logs, raw outputs and audits remain archived. The restoration is
not a retained engine change. Preservation passed **800 protected paths**, all
**27 parent source files**, the exact README introduction and the owner's existing
`tools/batch_positions.py` edit. The stable GUI bundle
`build/test-baselines/0.1-dev-4b8b35d/`, normal release and earlier evidence remain
intact. The historical normal-release digest discrepancy and six Phase 4F.13
forfeits remain unresolved. No default, rating, release or clock decision changes.

## Evidence and next checkpoint

Local evidence is `results/phase4f17-nnue-reuse-20261104/`: `before.json`, both
source archives, CPU profile/raw sample, CPU independent audit, correctness/build
logs and receipts, `oracle-report.json`, `pre-screen.json`, the four timing
reports, `timing-independent-audit.json`, auditor self-tests, `candidate.patch`,
`profile-cleanup.json`, `timing-cleanup.json`, `restoration.json` and
`preservation.json`. The timing audit verifies the candidate before restoration;
its frozen source hashes intentionally describe the archived candidate.

| Artifact | SHA-256 |
| --- | --- |
| Diagnosis protocol | `aeaf9716bd4f5029d1d414587f986ff0afed35bc91bec34078e1bed92f797d48` |
| Candidate protocol | `e71820058f5b80b691248061e377a72fbbb9a1804554ca4e53fa24b155c33b4c` |
| CPU independent audit | `db0a252d75a8b64c0f27efb32b99121509a8bc0a0fe4a6dbd61c421035c78a55` |
| Parent binary | `17f2951611713b8bd4b13dd0aeee892d972e6aaf829b832ad2737f46045f2800` |
| Candidate binary | `3ad870b65630efe5112f58d8a06bea619ff04e787cbeb3786d7d6444b4e2e58a` |
| Pinned network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Fresh oracle report | `ac4d123e3b5f05bf3423713daf06406e31331941cd83a7bf6413c2751f870919` |
| Pre-screen freeze | `36c21e635e1ab8378aa567614e93aee8d791d59b2c14b70b8abe4d3cb6f50fec` |
| Control raw report | `ec87424891b7c324b2d8f45f6ef09ecd551726a6a1f86726d102650c124180ff` |
| Candidate block 1 raw report | `10b6dd186f32f7073400ec0333ac7480395e0fb04ea26dfb2b131917c970bd2b` |
| Candidate block 2 raw report | `dbc4591238bb94a974c39563861c8c1d2b3b488b26488964f8bbbd71cc43adad` |
| Candidate block 3 raw report | `e09722517bc979f0d585f9889acf674ac1895f7c5e186261a9aa15932536c513` |
| Timing independent audit | `b65a180103adbb0f8c900769693358ba82f01fb4e8b94eddeee621d72ef7f38e` |
| Archived candidate patch | `99c5cbb5121f05a27ed5b9c6eaddbd469fae6964f98d05549d5c920ea610cf01` |
| Timing cleanup receipt | `d826637ea3d0dc113fcbd984d456be2ea059700e5014491c022bcb59d0ad9b07` |
| Restoration receipt | `3a431527f11bd59adaba2f9934232ec2e286b49ad9c816f532b2b996b2034a42` |
| Preservation receipt | `9af343c58930c3f682948cc3857fa27b0e2c6d614655186d1cfe43b9e2276c9c` |

Proposed **Phase 4F.18: separate, default-off quiescence delta pruning**, already
identified in the search plan. Freeze one conservative per-capture rule and
margin before measurement, with checks/evasions, promotions, en passant,
mate/tablebase/draw handling and declared endgame exclusions protected. Keep
conservative LMR on and other experiments off. Require exact parent parity when
disabled; because enabled pruning changes search heuristically, report all
behavior differences and require tactical, state-restoration and cancellation
checks. Run one frozen development screen; consider separately authorized clock
and strength qualification only if it is promising. Do not retune this rejected
cache. No implementation, match or schedule for Phase 4F.18 has begun, and no
gain or delivery date is promised.
