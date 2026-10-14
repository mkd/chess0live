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
Phase 2D strength qualification remains a separate next step.

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
