# Experiment log

Record unsuccessful and inconclusive experiments as well as improvements.
Performance observations are not Elo estimates. Large raw records and experimental
binaries stay in ignored local output directories.

## 2026-10-14 — capture ordering: opt-in, not promoted

**Hypothesis:** rank captures with negative static exchange estimates below
quiet moves, so useful quiet cutoffs can precede material-losing captures.
The original legal-LVA estimator handles pins, x-rays, king safety, en passant,
and promotions. It changes priority only: captures are neither pruned nor
reduced. LMR stays disabled, timing classic, and the evaluator unchanged.

Native, scalar, sanitizer, and independent reference checks passed, including
28 composed/reflected cases and 4,117 generated exchanges. Default mode matched
all 24 frozen-parent signatures. Depth-5 search used 4.72% fewer nodes with
matching final moves/scores/PVs in all 24 comparisons. At 200,000 nodes, one root
gained a nominal depth and another lost one; all 12 best moves agreed.

The predeclared eight-game smoke scored **2W/4D/2L** with no operational failures,
time forfeits, truncations, or exclusions. Four development pairs cannot show a
strength advantage or statistical equivalence. No parameter was tuned or
favorable subset selected after measurement.

**Decision:** retain as an opt-in research checkpoint; MVV-LVA remains default.
The modest sampled work reduction merits further investigation, not an Elo
claim. [Capture ordering](MOVE_ORDERING.md) records the algorithm's limits,
predeclared checks, frozen hashes, exact results, and reproduction commands.
The completed time-policy and isolated LMR screens are recorded below;
further search-candidate qualification remains deferred.

## 2026-10-14 — bounded LMR loss diagnosis: no policy change

Selected a decision root and its next-turn witness from each of the four LMR
smoke losses by a frozen score-drop rule. Sixteen node-limited off/on searches
on the frozen LMR executable agreed on all eight best moves and all 40
common-depth scores/PVs. Both policies reproduced the sharpest shallow choice
and changed it one depth later. No LMR-specific miss was demonstrated; no LMR
parameter changed. This post-hoc evidence neither proves reductions safe nor
replaces strength qualification. See the [full diagnosis](reports/2026-10-14-lmr-losses.md).

## 2026-10-14 — conservative LMR: opt-in, not promoted

**Hypothesis:** independently implemented one-ply reductions on later quiet
scout moves can reduce search work while ordinary-depth re-search verifies
promising probes. Checks, tactical/special moves, ordering hints, advanced pawn
pushes, root/PV nodes, and mate windows retain ordinary depth. Reduced fail-lows
remain a heuristic that can miss tactics. Classic timing and ordering are fixed.

Native, scalar, and sanitizer suites passed, including real accepted/rejected
verifications and policy-switch restoration. Default-off search matched all
24 frozen-parent samples. At depth 5, all 24 development comparisons kept the
same move/score/PV while total nodes fell 49.79%. At 200,000 nodes, 8/12 roots
completed one more nominal depth; one move and several scores/PVs changed.
These observations do not establish chess strength or equal-work throughput.

The predeclared eight-game, four-pair 6+0.06 smoke scored **2W/2D/4L** for LMR,
with no failures, time forfeits, or truncations. Independent replay checked all
1,231 plies: six checkmates and two threefold draws. The result is unfavorable,
but this tiny development sample cannot establish a strength difference.

**Decision:** retain the guarded implementation, diagnostics, and profiler as
an opt-in research checkpoint; leave LMR disabled. No default promotion or
strength claim. Investigate tactical misses and qualify with a separately
predeclared longer campaign. New move ordering is a separate next experiment.
See [selective search](SELECTIVE_SEARCH.md) for exact hashes, commands, raw
evidence paths, and the safeguards against combining this with forecast timing.

## 2026-10-14 — forecast time allocation: opt-in, not promoted

**Hypothesis:** observed completed-iteration cost can predict when the next
depth is unlikely to finish before the hard deadline, avoiding long thinks
that return the previous depth's result. This follows the owner's manual
feedback for frozen GUI snapshot `0.1-dev-4b8b35d`, not an NNUE throughput change.

The first soft-target gate was rejected: all 18 short-clock comparisons lost a
completed depth relative to classic. A separately frozen revision changes only
that gate to the hard deadline and retains classic soft stopping. It preserved
completed depth in 32/36 development comparisons and best move in 36/36. At the
manual 5...c6 root it returned the same depth-7 move/score/PV in 5.788 seconds
versus classic's 26.926 seconds, avoiding an unfinished depth 8.

Both candidates passed native, scalar, and sanitizer correctness checks and
retained all 24 sampled default-classic fixed-depth signatures. Their four-game
operational smokes scored 1W/2D/1L and 2W/2D/0L respectively, with no errors or
time forfeits. These very small exploratory games establish no strength margin.

**Decision:** retain instrumentation, the profiler, and the hard-deadline policy
as an optional experiment. Classic remains the default. The 32-root held-out
blitz campaign is prepared, not started or scheduled. Exact candidate hashes,
settings, commands, limitations, and local evidence paths are recorded in the
[time-management experiment](TIME_MANAGEMENT.md).

## 2026-10-13 — NNUE feature-buffer reuse: not retained

**Hypothesis:** retaining and swapping worker-local feature-list buffers would
avoid their repeated allocation/free and improve search throughput. The candidate
changed buffer ownership only; feature generation, integer arithmetic, inference,
and search rules remained unchanged. It added a second retained buffer per
perspective, with a modest memory cost.

**Baseline:** source snapshot `4b8b35d`, executable SHA-256
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
**Candidate:** executable SHA-256
`10b2163925be928eac631fe3cbd5ae875e6f32d428948e99109c887f9f703731`.
Both used Apple Clang 21, the generic macOS ARM64 release settings, the same
pinned SF19 network, one search worker, and 64 MiB hash.

The candidate passed native, scalar, and AddressSanitizer/UndefinedBehaviorSanitizer
suites. Its 2,057-position native/scalar/Stockfish oracle comparison matched every
recorded stage exactly. Additional dense/sparse/reset transitions passed. Code
review found no correctness or portability issue.

The first timing run used the three default development positions at depth 6,
seven measured repetitions per binary, and one warmup per position/binary.
Because its tiny effect was smaller than observed variation, one exploratory
follow-up used depth 7, three repetitions, and a 30-second per-search deadline.
Run order alternated; table clearing and readiness were excluded from timing.

| Run | Matching searches, including warmups | Median baseline/candidate ratio | Ratio median absolute deviation |
| --- | ---: | ---: | ---: |
| Depth 6 | 48 / 48 | 1.00310 | 0.00715 |
| Depth 7 | 24 / 24 | 1.00423 | 0.00341 |

Every sampled iteration matched depth, selective depth, nodes, score, and PV;
best moves and ponder moves also matched. The longer run completed without a
timeout; its longest search took 12.13 seconds. Variation differed substantially
by position, particularly in the queen-pawn opening.

**Decision:** not retained. These exploratory results did not establish a clear
throughput benefit, and no playing-strength test or Elo gain was claimed. The
original evaluator was restored. This does not prove buffer reuse is universally
unhelpful; reconsider only with a new hypothesis or stronger evidence.

Local evidence:

- `results/nnue-buffer-reuse-depth6.json`
- `results/nnue-buffer-reuse-depth7.json`
- `results/nnue-buffer-reuse-depth6-compare_bench.py` — exact earlier helper,
  hash-checked against its report before the timeout option was added.
- `results/nnue-buffer-reuse-experiment/` — candidate binary, source patch,
  candidate oracle report, and decision manifest.

The reports record the original rebuild path of the candidate. That path now
contains the restored baseline; use the archived candidate and verify its hash
when reproducing this comparison. The retained comparison helper and its tests
are described in [benchmarking](BENCHMARKING.md).

## 2026-10-15 — Phase 2D time policy: inconclusive, classic retained

The predeclared 32-pair, 64-game 60+0.6 campaign completed under the owner's
one-worker daytime exception. Forecast scored **14W/43D/7L**, or **35.5/64 points
(55.46875%)**. Its conditional pair-level 95% Hoeffding score interval was
**31.46068%–79.47682%**: the result is inconclusive, not evidence for promotion
or equality. All games were included, with no failures, clock forfeits, or
truncations. Independent audit checked 7,088 legal plies, 6,240 searches,
actual clocks/options, and unchanged frozen artifacts. Elapsed campaign time
was 2 h 53 min 49.434 s.

**Decision:** keep classic as default and forecast opt-in; do not extend or
retune this completed sample. The subsequently completed isolated LMR screen
used classic timing and baseline ordering; its October 16 result appears below.
The [full time-policy report](reports/2026-10-15-phase2d-time-policy.md) records
preparation commit `2cf55f7`, exact settings, artifact/evidence hashes,
uncertainty, and the remaining qualification requirements.

## 2026-10-15 — Phase 2D isolated LMR screen prepared

The [predeclared 128-game protocol](PHASE_2D_LMR.md) freezes 64 fresh original
full-history roots, seed `20261015`, 60+0.6, one active worker, and identical
frozen LMR executables. Both use classic timing and baseline capture ordering;
only the reduction toggle differs. A conditional 95% pair-score interval must
clear 0.5 for confirmation review, requiring at least 86/128 points. At most
42/128 is negative evidence; otherwise the screen is inconclusive. No default
promotion is automatic. Candidate clock forfeits block a positive decision.

All 100 workflow checks and real no-search preflight passed; the previous
time-policy audit remains reproducible. These checks establish readiness,
not a played result. Ordinary overnight limits and the original 07:00 Helsinki
cutoff apply; the prior one-run daytime exception is consumed. The suite and
candidate must remain frozen during play, with incomplete evidence retained.

## 2026-10-16 — Phase 2D isolated LMR: inconclusive, default off

The predeclared 64-pair, 128-game 60+0.6 overnight screen completed in
**6 h 41 min 12.439774 s**. LMR on scored **35W/82D/11L**, or **76/128 points
(59.375%)**. Its conditional pair-level 95% Hoeffding score interval was
**42.398731053%–76.351268947%**; 76 points did not reach the predeclared
86-point confirmation threshold. The favorable point estimate remains
**inconclusive**, not a proven strength gain, rating, or equivalence result.

All 128 games passed the independent audit with no exclusions, clock forfeits,
protocol failures, or truncations. Replay checked 17,175 legal plies and 15,191
searches: 46 checkmates, 71 threefold draws, 10 insufficient-material draws,
and one rule-50 draw. Frozen campaign sources/assets and all five separately
preserved engine/network hashes remained unchanged, including GUI snapshot
`0.1-dev-4b8b35d`.

**Decision:** keep classic timing, LMR off, and MVV-LVA as defaults. Do not
extend or retune this completed sample. Propose Phase 3A's measured performance
baseline with those settings; further LMR and separate SEE qualification are
deferred, not completed or promoted. The [full report](reports/2026-10-16-phase2d-lmr.md)
records preparation commit `842ee41`, launch-record commit `57e21fd`, exact
settings, evidence digests, sampling limitations, and data-only audit reproduction.

## 2026-10-16 — Phase 3A baseline: NNUE update selected for investigation

The [fixed measurement protocol](PHASE_3A.md) completed on the M5 Pro with
classic timing, LMR off, and MVV-LVA. All 192 same-binary searches matched;
median paired ratio was 0.998546 with MAD 0.008123. All 48 symbol-build/release
searches also matched. Independent replay checked every reported move/PV.

A separate CPU sample attributed 85.04% of 7,413 active-search observations
to NNUE, including 58.69% in accumulator update. These are overlapping sampled
costs, not exact CPU time or strength evidence. The profiler and 16 mocked
lifecycle/evidence checks are reusable; denied inspection and the corrected
custom-bundle network setup are retained in the evidence record.

**Decision:** propose isolated batched feature-column updates, with exact
modular arithmetic, native/scalar/full-oracle parity, and fixed throughput
gates in [Phase 3B](PHASE_3B.md). Do not change engine code or defaults in this
measurement checkpoint. The [full report](reports/2026-10-16-phase3a-baseline.md)
records inputs, figures, interpretation limits, and reproduction. No speedup,
release, Elo gain, or additional platform execution is established.

## 2026-10-16 — Phase 3B: retain batched NNUE feature-column updates

Starting at `710523e`, one candidate applied the existing sorted multiset
differences in streaming batches of eight column views, with 32 hidden lanes
per tile. Enumeration, inference, search, and policies stayed unchanged. Native,
scalar, and sanitizer suites passed, including 360 independent synthetic update
transitions; the pinned external 2,057-position stage oracle matched all original
corpus and output digests for native and scalar.

All 576 searches in correctness and timing comparisons matched exactly; the
independent audit replayed 3,024 PV lines / 10,572 legal PV plies and verified
all bestmoves and ponders. The two depth-5 timing medians were **1.078081** and
**1.079836**, and the depth-6 median was **1.083612**. All cleared the declared
1.03 gate, and all 24 pooled root/depth medians exceeded 0.98. No observed
individual measured slowdown, discarded run, or threshold change occurred.

**Decision: retain**, as a sampled implementation speedup on the M5 Pro. No
playing-strength gain follows from throughput alone. The [full report](reports/2026-10-16-phase3b-nnue-batching.md)
contains per-root times, order effects, dispersion, limits, and evidence hashes.
Raw evidence is `results/phase3b-20261016/`; the frozen candidate is under
`build/experiments/phase3b-20261016/`. Next is broader middlegame/endgame
performance validation, with new structural coverage fixed before measurements.

## 2026-10-16 — Phase 3C: middlegames qualified, endgames inconclusive

The unchanged retained batching candidate was compared with the preserved
baseline on 12 original composed FENs. Six predeclared runs completed within
15 minutes using one worker; all 432 searches matched exactly and replayed
legally. Both same-binary controls were stable. Middlegame ratios **1.087243**
and **1.088055** passed every noise, duration, positive, and root-regression gate.

The endgame ratios and root guards were also favorable, but the sparse pawn
root took only 30–32 ms, below the frozen 50 ms floor. **Endgame and overall
qualification are inconclusive.** No root was dropped, no depth changed, and
no extra run was added. No candidate slowdown appeared in 120 measured pairs,
but that cannot override the duration gate or establish playing strength.

The [full report](reports/2026-10-16-phase3c-gamephases.md) records every root,
order effects, dispersion, exact hashes, and independent audit/check evidence.
Keep `results/phase3c-20261016/`. No engine/default/binary changed; the existing
batching implementation remains retained. Next is baseline-only characterization
of the short pawn workload before separately frozen qualification, not tuning
or repeating this completed experiment toward a preferred result.

## 2026-10-17 — Phase 3D: propose depth 12 for the short pawn workload

The [frozen diagnostic](PHASE_3D.md) used only the Phase 3A baseline at depths
8–12 on `gamephases-eg-05`. All 40 searches matched exact per-iteration results,
with matching common-depth prefixes and independent legal replay. The bounded
campaign completed in 7.441256 seconds under the ordinary daytime budget.

Depth 12 was the shallowest level meeting the fixed proposal rule, at
329.881/322.562 ms role medians, ratio 0.999090 and MAD 0.028507. Depth 10's
ratio/MAD failures remain in the evidence. Three pairs, including a near-limit
MAD at depth 12, do not prove durable repeatability. The result is a proposed
workload, not a candidate speed gain, strength result, or change to Phase 3C.

The [report](reports/2026-10-17-phase3d-workload.md) preserves every duration,
score, move/PV, order effect, and evidence hash. Keep
`results/phase3d-20261017/`, including the failed auditor-only API-typo attempt
and successful `audit-final.json`; no raw measurement was changed. All 20 audit
checks passed. No production code, default, or binary changed. Phase 3E should
freeze a new complete six-root endgame comparison using the longer pawn workload
and fresh controls before measuring; old favorable roots must not be pooled
with a new pawn result to claim a retrospective pass.

## 2026-10-17 — Phase 3E: revised endgame workload qualifies

The [separately frozen campaign](PHASE_3E.md) retained all six original endgames,
with the pawn root at depth 12 and other five at depth 8. Fresh baseline controls
and two candidate rounds completed all 216 exact/legal searches in 353.663077
seconds under the normal daytime budget. Each round pools all 30 individual
pairs, five per root, with no older campaign timings.

The complete control passed at median 0.998927/MAD 0.003985. Candidate ratios
**1.089113 / 1.084243** passed with all duration and root guards. The result is
**qualified on this revised composed endgame sample**. All 29 auditor checks
passed. The [report](reports/2026-10-17-phase3e-endgames.md) preserves every
measured slowdown, including two candidate pairs, and the substantial absolute
time drift in later samples. Nothing was excluded or rerun.

Keep `results/phase3e-20261017/` intact. No engine/default/binary changed, no Elo
gain follows, and Phase 3C's original decisions remain unchanged. Next is Phase
3F: profile the updated engine and choose one justified, isolated NNUE improvement
with exact correctness and predeclared performance gates. Do not extend this
completed campaign or pool favorable old roots into it.
