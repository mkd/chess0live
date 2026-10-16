# Phase 3C: broader game-phase performance — October 16, 2026

**Completed with a qualified middlegame gain and inconclusive endgame inference.**
The retained NNUE batching implementation completed the six composed middlegames
with **8.7% and 8.8% higher measured throughput**, preserving exact search results.
The endgame runs were also favorable, but the sparse pawn root took only about
30–32 ms, below the predeclared 50 ms floor. Under the frozen rules, that makes
endgame and overall broader-suite qualification **inconclusive**. No root was
removed, no workload was adapted, and no extra comparisons were added.

The Phase 3B implementation remains retained. This phase changed no engine code,
binary, search-policy default, or GUI bundle. It establishes neither a playing-
strength gain nor a new release. Preparation was committed locally as `ae5853a`.

## Frozen design and provenance

The [protocol](../PHASE_3C.md) was frozen before either engine searched any new
root. The [original suite](../../tests/data/performance-gamephases.json) has six
middlegames and six endgames, three roots with each side to move in each group,
and all eight SFNNv16 material buckets. It covers quiet/tactical middlegames,
queenless play, rook, knight, bishop, pawn, and mixed endings. Composition used
structural coverage, without engine scores, solutions, or timing selection.

Independent `chess==1.11.2` checks found all 12 roots valid, nonterminal,
non-drawn, distinct, and disjoint from all 120 prior opening-suite roots. These
are composed FENs with no earlier history, castling rights, or en-passant rights.
Local validity does not prove historical reachability. This is a finite
engineering suite, not a random sample of tournament play or a strength test.

Host: Apple M5 Pro, 18 logical CPUs, 64 GiB RAM; macOS 26.7.1 ARM64.
Both preserved generic release builds use Apple Clang 21.0.0, C++26 mode,
`-O3 -DNDEBUG`, and the same pinned SF19 network. The unchanged comparison helper
runs one active worker with two resident engines and a conservative combined
memory estimate of about 1.11 GiB, within the ordinary 50% daytime budget.
Background activity, core placement, and thermal state were uncontrolled.

| Artifact | Source / SHA-256 |
| --- | --- |
| Baseline | `9daaade` / `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44` |
| Candidate | `eb059b5` / `2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae` |
| Network | `SF19/SFNNv16` / `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |

Baseline path: `build/experiments/phase3a-20261016/release/chess0live`.
Candidate path: `build/experiments/phase3b-20261016/release/chess0live`.
The ordinary native build remains byte-identical to that candidate. The preserved
GUI snapshot is still `0.1-dev-4b8b35d`; it was not used as this timing baseline.

Each comparison used Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA,
Ponder/diagnostics off, and Move Overhead 20 ms. The helper explicitly sets
Threads/Hash/EvalFile; the remaining settings are confirmed by the fresh-process
UCI defaults and frozen setup code. Outgoing setup commands are not retained in
this older benchmark format, so this is not a complete bidirectional transcript.

Middlegames used depth 6 and endgames depth 8, fixed by phase before measurements.
Each run had one warmup per root/role, followed by five measured repetitions with
alternating role order. Readiness/table clearing was outside the external
monotonic go-to-bestmove timing. Limits were 30 seconds/search, ten minutes/run,
and 15 minutes/campaign. The entire campaign completed **11:57:04–12:11:09
Helsinki, 844.997 seconds**, including startup and checks; all six runs completed.
No sampling, compilation, concurrent engine tests, or automatic schedule ran.

## Exactness, audit, and decision gates

All **432 searches** matched exactly: **72 warmups and 360 measured searches**.
The independent auditor reparsed raw replies and compared every iteration's
depth, selective depth, nodes, score and PV, plus bestmove/ponder, across control,
A/B, roles, and repetitions. It legally replayed **3,024 PV lines / 14,904 plies**,
plus all **432 bestmoves and 432 ponders**. There were no exclusions, timeouts,
search failures, mismatches, or artifact drift.

Both same-binary controls passed aggregate median [0.97, 1.03], paired MAD ≤0.03,
and every root median [0.95, 1.05]. Both candidate runs per phase exceeded the
1.03 aggregate gate; all 12 pooled root ratios exceeded 0.98. However, the timing
floor applies first: every role/root/run median must be at least 50 ms. Only
`gamephases-eg-05` failed, in all six role/run combinations:

| Run | Baseline-role median (ms) | Candidate-role median (ms) |
| --- | ---: | ---: |
| control-endgame | 32.185541 | 32.254125 |
| timing-endgame-a | 32.275541 | 30.149834 |
| timing-endgame-b | 32.041167 | 30.043333 |

In the control, both roles run the baseline binary. Favorable ratios cannot
bypass the duration gate. Middlegames therefore qualify on this composed sample;
endgames and the combined checkpoint remain inconclusive. This is not an observed
regression or a reason to erase Phase 3B's opening evidence.

The 11 existing comparison-tool checks passed. The launcher cleanup check
verified termination of a TERM-ignoring descendant after its parent exits;
the initial process-inspection attempt was sandbox-denied, and the approved
retry passed. Independent audit checks rejected five corruptions (summary ratio,
illegal warmup PV, search timeout, impossible summed elapsed time, wrong binary)
and passed eight classification/threshold cases, including noise/floor precedence.
Those checks used copied in-memory data; raw evidence was unchanged.

Native/scalar/sanitizer and full SF19 stage-oracle suites were not rerun here:
engine code and binaries are unchanged from the [Phase 3B validation](2026-10-16-phase3b-nnue-batching.md).
The new searches add finite exact-search/legal-output evidence, not a replacement
for integer-stage oracle checks or new foreign-platform execution.

## All measured results

Ratios are baseline elapsed / candidate elapsed; greater than 1 favors the
candidate. Each row below contains 30 measured pairs. MAD and range describe
observed variation, not confidence intervals. Endgame candidate rows are
**descriptive observations only**, because their duration gate failed.

| Run | Median ratio | MAD | Individual ratio range | Baseline-first / candidate-first medians |
| --- | ---: | ---: | --- | --- |
| control-middlegame | 1.004420 | 0.003930 | 0.988717–1.017853 | 1.001629 / 1.005726 |
| control-endgame | 0.999512 | 0.003443 | 0.980517–1.015167 | 0.998799 / 0.999601 |
| timing-middlegame-a | 1.087243 | 0.006431 | 1.049222–1.103463 | 1.084264 / 1.087695 |
| timing-endgame-a | 1.090780 | 0.014201 | 1.033671–1.160872 | 1.086651 / 1.094358 |
| timing-middlegame-b | 1.088055 | 0.007593 | 1.073412–1.103633 | 1.085500 / 1.088583 |
| timing-endgame-b | 1.091442 | 0.013034 | 1.055726–1.107238 | 1.097316 / 1.087305 |

The table below pools A/B candidate comparisons only, ten measured pairs per
root. Times are separate medians of each role's ten durations; ratio is the
median of the ten paired ratios, not a quotient of the two time medians.
`mg` is depth 6 and `eg` is depth 8. Short IDs map to `gamephases-<ID>` in the suite.
All roots are included; **every endgame row remains subject to the failed group
qualification**, including the five roots that individually cleared the floor.

| Root | Baseline median (ms) | Candidate median (ms) | Paired ratio | MAD | Individual ratio range | Baseline-first / candidate-first |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| mg-01 | 728.556 | 666.378 | 1.092415 | 0.002345 | 1.082306–1.103633 | 1.090705 / 1.093169 |
| mg-02 | 2775.722 | 2559.614 | 1.084588 | 0.003094 | 1.079074–1.091080 | 1.086171 / 1.082152 |
| mg-03 | 4509.075 | 4173.304 | 1.081385 | 0.001933 | 1.076951–1.088564 | 1.081378 / 1.081813 |
| mg-04 | 3230.486 | 2941.399 | 1.097600 | 0.000923 | 1.066490–1.103463 | 1.097449 / 1.098060 |
| mg-05 | 1030.150 | 956.539 | 1.078696 | 0.004816 | 1.049222–1.089438 | 1.079073 / 1.076282 |
| mg-06 | 2240.082 | 2052.387 | 1.088698 | 0.005789 | 1.077103–1.097516 | 1.089054 / 1.088698 |
| eg-01 | 2690.188 | 2440.286 | 1.103014 | 0.004149 | 1.094358–1.108089 | 1.104822 / 1.097018 |
| eg-02 | 3123.634 | 2912.679 | 1.073009 | 0.002695 | 1.067588–1.142651 | 1.073545 / 1.072446 |
| eg-03 | 395.471 | 359.098 | 1.101471 | 0.003534 | 1.077309–1.108792 | 1.100232 / 1.105005 |
| eg-04 | 931.509 | 860.235 | 1.081711 | 0.004829 | 1.057188–1.091723 | 1.079436 / 1.084206 |
| eg-05 | 32.086 | 30.123 | 1.065695 | 0.004996 | 1.033671–1.086656 | 1.065115 / 1.075539 |
| eg-06 | 2106.702 | 1914.836 | 1.101184 | 0.003025 | 1.086651–1.160872 | 1.099635 / 1.102906 |

There were **zero individual slowdowns among all 120 measured candidate pairs**.
Every same-binary control slowdown is ordinary repeatability evidence; the audit
retains those individual records too. No threshold or root selection changed.

## Evidence and reproduction

Preserve the entire ignored directory `results/phase3c-20261016/`, including
frozen `protocol.md`, `suite.json`, two position lists, `manifest.json`, all six
raw JSON/log pairs, `campaign.json`, the bounded launcher, preflight/cleanup
checks, independent suite audit, final audit/check scripts and results, and
`final-integrity.json` (34 matching artifact/source checks). Large raw outputs
and binaries stay local; the suite, protocol, and this report are versioned.

Selected SHA-256 pins:

| Local evidence file | SHA-256 |
| --- | --- |
| `protocol.md` | `b404ce1f1b23171c36c37eb3acf2d561ae1c1601f08c4aa77f748dca64f82c3e` |
| `suite.json` | `38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c` |
| `manifest.json` | `00b862e3f8486a210e4839ddf1a33e685ad332bf7a1fb09830ac854810793f42` |
| `campaign.json` | `92caa7b041f9c29e8a3a1e65f1f6e18f5302965ee9d08aa90d73b2f0115f6f7d` |
| `run_campaign.py` | `67c5c3e455fd22fb55d53abd8a0fb39dffdc8727f6a45c9a88ec220f6d9a74f3` |
| `audit_bench.py` | `43340af4ae4b01e61d2ebb2d9ba1fe6e77a171c880fbbf2497af5d9d5e0b7d4b` |
| `audit.json` | `e6a4215e8ec4525444ce5dd4cb63ae387868ed8825d1b0b90e045b4782280b95` |
| `audit_checks.py` | `ac730ef85aa725f463e35260a1bd3441d8c4272f274fe0bba43e3f61e1421f7e` |
| `audit-checks.json` | `dae932aa19d0aa2d97d8bfdab863d50fde3d4810da26f283a6c8c9965043ffe6` |
| `final-integrity.json` | `827bfbe78b937278b191f90972b575972faf82fd7596804167dd8240673b57d3` |
| `control-middlegame.json` | `3a4007e6a355f888ea2087bf5dd09b11494bfba647e5fa3380796228e2f11c52` |
| `control-endgame.json` | `279e4415648064fd4ae55b5476794ce3b52269262b3bc2001be2c451fc4db01e` |
| `timing-middlegame-a.json` | `4cddb68ef9b4a5d3877f4b15fc229fbf8bf6a16676759d5e7f48371c5aa6f60c` |
| `timing-endgame-a.json` | `c511f63aebb14d79d032baec580449a651531b37f7b96af544f1a504eccfa462` |
| `timing-middlegame-b.json` | `e91a592254b7cc7ad72f5020b33961153f60a5a7cb5c1ecded588b3c2f871598` |
| `timing-endgame-b.json` | `a9730d540ad8c9a6b27e0594002fa3b2aa84dc834e7bb1d883fff87d7d1fbe28` |

Use the frozen binaries and network hashes above, not an arbitrary later build.
A fresh clone must build/preserve those source revisions with the recorded
compiler/settings or obtain the archived local binaries; record any different
artifact hashes as a new reproduction. The existing public comparison tool
accepts one `fen <six-field FEN>` per line. Export the six roots for each phase
in JSON order, preserving all six fields and no extra move history.

For example, in a new output directory:

```sh
python3 tools/compare_bench.py \
  --baseline build/experiments/phase3a-20261016/release/chess0live \
  --candidate build/experiments/phase3b-20261016/release/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --positions results/phase3c-20261016/middlegame-positions.txt \
  --depth 6 --repeats 5 --hash-mb 64 --search-timeout 30 \
  --output results/phase3c-reproduction/timing-middlegame-a.json
```

The complete run order/settings are in the protocol and recorded command arrays
in `campaign.json`. For controls, both roles use the baseline. Endgames use their
position file at depth 8. Preserve the campaign ceilings and no-overwrite rules;
the single example command alone does not enforce the overall campaign deadline.
Do not overwrite or opportunistically extend this completed experiment.

## Next checkpoint

**Phase 3D: characterize the short endgame workload using the baseline only.**
Predeclare a small bounded depth ladder on the same sparse pawn FEN, then record
exact work and duration growth without candidate comparisons or parameter tuning.
Use that diagnostic to propose a longer fixed workload for a separately frozen
qualification. Do not relabel 3C as passed, omit its sparse root, or repeatedly
resample toward a favorable conclusion. Remaining NNUE processing costs and
parallel search are later implementation work; no new job or schedule is active.
