# Phase 4D.5: quiescence SEE checkpoint

## Decision and scope

**Phase 4D.5 is complete as a bounded experimental checkpoint.** The isolated
candidate passed correctness checks and completed its finite development screen
and full matched 60-second puzzle comparison. **`QSearch SEE Pruning` remains off by
default**: no additional mates were reported on this puzzle suite and no
playing-strength qualification has run. The fresh-cache node reduction is
larger than the reused-cache reduction; neither establishes an Elo gain.

The [predeclared protocol](../experiments/phase4d5-qsearch-see.md) fixes a single
negative-SEE capture filter with no tuned margin. Only interior ordinary scout
quiescence is eligible. Checks, special moves, mate/tablebase windows, repeated
positions, high halfmove clocks, advanced pawns and small endings are protected.
More than eight parent pieces also excludes captures into seven-piece endings.
Real child checks and terminal positions veto a skip. These guards cannot prove
that every other sacrifice is unsound. Delta pruning is a separate hypothesis;
no existing search option, clock policy or evaluation arithmetic changed.

The owner's October 20 Cute Chess report motivates this work: wins against
average opponents, losses against Gargantua/Stockfish, and nominal depth 6–7
even with eight threads. No game record, exact binary pin or complete settings
accompanied that report. It is qualitative feedback, not a controlled strength
measurement. Preserved GUI snapshots are `0.1-dev-4b8b35d`,
`0.1-dev-phase3f-20261017` and `0.1-dev-phase4b-20261018`; the tested snapshot
was not identified. Cross-engine nominal depth is not a common quality scale.

## Correctness and isolation

- Native, forced-scalar and ASan+UBSan: full `make test`, new direct Search API
  tests and 98 independent-referee UCI cases passed in each mode.
- TSan: existing Search and 43 SMP lifecycle checks, new Search API tests and
  the same 98 UCI cases passed. No sanitizer findings were reported.
- Ten engine-free profiler tests passed, including exclusive evidence creation,
  source drift, failed parent equivalence, deadlines, resources and late output.
- Activation actually evaluated 728 exchanges and skipped 187 captures on the
  bounded starting-position test. Disabled diagnostics preserve search results;
  toggling the option restores fresh-policy behavior by invalidating cache and
  learned state. Aggregate limits, cancellation and reuse passed with 1/4 workers.

Actual-board fixtures cover negative-SEE checking sacrifices, evasions,
en passant, all capture-promotion choices, stalemate children and the eight-piece
boundary in both colors. Python independently checks their legal and exchange
properties. These predicate/source checks do not claim that each exemption was
observed inside private quiescence branches. Legal public PVs are checked
separately. Combinations with existing experimental pruning were exercised for
lifecycle correctness, not qualified for strength.

## Fixed performance screen

All 60 searches in 36 serial processes completed within the fixed 900-second
budget (47.82 seconds including setup and cleanup). Settings: one worker,
Hash 64 MiB, classic clock policy, pinned NNUE, all unrelated experiments and
Syzygy off. The six roots are exposed development inputs, not held-out matches.
Only one repetition was run; failed cases were not replaced or retuned.

An independent parser audited the raw evidence without importing the profiler's
validators: 351 iterations, 1,550 legal PV plies, 120 bestmove/ponder plies,
matrix/order/options, joined process exits, all summary arithmetic and 76
artifact-hash checks passed.

All 12 frozen-parent/candidate-off pairs had identical per-depth search
signatures and final decisions. Their elapsed totals varied by −0.45% with
fresh caches and −7.00% with reused caches despite identical work, illustrating
why these short single-run timings cannot qualify a speed gain.

| Candidate off versus on, depth 6 | Off nodes | On nodes | Node change | Observed elapsed change |
| --- | ---: | ---: | ---: | ---: |
| Fresh cache | 1,922,478 | 1,699,067 | −11.62% | −14.11% |
| Reused cache | 630,684 | 620,700 | −1.58% | −9.29% |

All 12 fixed-depth final best moves and ponder moves matched. Starting-position
final scores changed from cp20 to cp13 in both cache conditions. Three
common-depth score/PV differences remain in the evidence: cold depth 6 and
warm depths 4/6. They are not discarded because the best move stayed the same.

At equal 500-ms requests, completed depths were `[6,5,5,5,4,6]` off and
`[6,5,5,6,4,6]` on. The quiet-center root reached one extra depth; five depths
and all six best moves matched. The quiet-center final score changed from
cp122 to cp114, and the starting-position score from cp20 to cp13. Aggregate
timed nodes were 839,284 versus 838,414; unfinished nodes 503,908 versus
447,402. These finite observations establish neither Elo nor tactical safety.

## Puzzle comparison

The unchanged owner-edited batch script and a temporary configuration adapter
use the existing printed-output workflow. The matched 1,000-ms smoke is
recorded separately from the required 60,000-ms checkpoint. Both smoke runs used
the same 39 supplied FENs in order, fresh processes, one worker, Hash 64 MiB and explicit
otherwise-identical settings; only the new filter differs.

Both 39-position smoke runs finished with no missing scores or errors. All
39 best moves matched. Neither build reported any positive mate: expected
distance 0/39, other positive distance 0/39, no positive mate 39/39 in both.
There were no positive-mate gains, losses or distance changes to report at this
budget. Three printed centipawn scores differed:

| Embedded position | Parent | Candidate on | Best move in both |
| --- | ---: | ---: | --- |
| 13 | +7.70 | +8.16 | `e6e1` |
| 31 | +10.11 | +8.18 | `g3h3` |
| 33 | +9.23 | +9.30 | `f5h3` |

These are fixed-time final scores, not same-depth score comparisons. This short
smoke validates execution and records differences; it provides little evidence
about the supplied long mating problems.

### Full 60-second checkpoint

The full matched baseline/candidate pair completed October 20, **15:41–16:59
Helsinki**, under the owner's explicit one-run daytime exception. Total recorded
elapsed time was 78m05s: parent 39m02.76s, candidate 39m02.73s. Each role used
60,000 ms per FEN, one search worker, Hash 64 MiB, fresh processes, the pinned
NNUE and identical other settings. All unrelated optional pruning, diagnostics and
Syzygy were off. No automatic schedule or match was started.

Both runs completed all 39 positions without errors or missing scores. The
independent audit checked all 78 legal best moves, exact FEN order, configured
settings, serial completion/exit codes, 59 source/protected hash checks and all
six post-run hashes. The owner's runner and README introduction stayed intact.

| Final positive-mate category | Parent | Candidate on |
| --- | ---: | ---: |
| Matches supplied mate-distance annotation | 1/39 | 1/39 |
| Other positive mate distance | 0/39 | 0/39 |
| No positive mate reported | 38/39 | 38/39 |
| Error or missing score | 0/39 | 0/39 |

Both report **M7 on position 2**, with `f4f3`. There are no reported mate gains,
losses or distance changes. All 39 best moves match. The only printed score
difference is position 29, **+9.16 to +9.59**, with `d1h5` unchanged. These are
fixed-time final scores, not a comparison at the same completed depth. This
single run does not establish that the differing score is more accurate.

The table preserves the complete final results. Decimal scores are printed in
pawn units from the side-to-move perspective; M denotes a reported positive
mate distance. Expected distances are supplied annotations, not certified
answers. Legal best moves do not certify a forced mate. The simple workflow
saves final exact scores/best moves, not full raw UCI/PV transcripts or the
spreadsheet's separate any-depth points calculation.

| Position | Supplied mate distance | Parent score | Candidate score | Best move, both |
| --- | ---: | ---: | ---: | --- |
| 1 | 7 | +12.06 | +12.06 | `f5f6` |
| 2 | 7 | M7 | M7 | `f4f3` |
| 3 | 7 | +6.58 | +6.58 | `d6c4` |
| 4 | 8 | +17.93 | +17.93 | `f3g5` |
| 5 | 8 | +15.82 | +15.82 | `h7h6` |
| 6 | 8 | +11.71 | +11.71 | `c6e7` |
| 7 | 8 | +11.69 | +11.69 | `d8d2` |
| 8 | 9 | +16.15 | +16.15 | `f7g7` |
| 9 | 9 | +14.39 | +14.39 | `a7e3` |
| 10 | 9 | +16.07 | +16.07 | `c1c7` |
| 11 | 9 | +11.08 | +11.08 | `e4c3` |
| 12 | 9 | +12.58 | +12.58 | `c1h6` |
| 13 | 9 | +14.65 | +14.65 | `e6e1` |
| 14 | 9 | +14.53 | +14.53 | `c3c2` |
| 15 | 9 | +16.00 | +16.00 | `e7d7` |
| 16 | 9 | +12.76 | +12.76 | `g3f2` |
| 17 | 9 | +13.98 | +13.98 | `f3h5` |
| 18 | 10 | +10.57 | +10.57 | `h5h4` |
| 19 | 10 | +11.06 | +11.06 | `h5g6` |
| 20 | 10 | +7.22 | +7.22 | `d6d1` |
| 21 | 10 | +14.92 | +14.92 | `d1h5` |
| 22 | 10 | +7.95 | +7.95 | `d1d4` |
| 23 | 10 | +13.41 | +13.41 | `e3e5` |
| 24 | 10 | +9.61 | +9.61 | `g5h6` |
| 25 | 10 | +12.30 | +12.30 | `g2d5` |
| 26 | 10 | +12.39 | +12.39 | `d1h5` |
| 27 | 10 | +11.87 | +11.87 | `e4d6` |
| 28 | 11 | +14.50 | +14.50 | `e1e4` |
| 29 | 11 | +9.16 | +9.59 | `d1h5` |
| 30 | 11 | +11.20 | +11.20 | `g5g3` |
| 31 | 11 | +11.26 | +11.26 | `g3h3` |
| 32 | 11 | +11.45 | +11.45 | `g8g4` |
| 33 | 12 | +11.41 | +11.41 | `f5h3` |
| 34 | 12 | +11.47 | +11.47 | `e6g7` |
| 35 | 12 | +7.39 | +7.39 | `h3b3` |
| 36 | 15 | -1.86 | -1.86 | `d3h3` |
| 37 | 15 | +1.11 | +1.11 | `b6d4` |
| 38 | 17 | +6.19 | +6.19 | `g8g5` |
| 39 | 18 | +0.00 | +0.00 | `h5h7` |

This records a completed development checkpoint with **no demonstrated mate
progress on the supplied suite**. It neither proves absence of tactical
regressions elsewhere nor replaces equal-resource playing-strength matches.
The short-smoke score differences above remain recorded independently; they
were not substituted for this full comparison.

## Reproduction and preservation

- Parent source: `dcfd23c4e1f346decb5b3db99426c957ec6ca811`.
- Implementation commit: `8c772fef32e7a0c16ca8e770bce3746c863e97ff`.
- Parent SHA-256:
  `361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f`.
- Frozen candidate SHA-256:
  `eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
- Network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Frozen binaries, exact source/test/protocol pins, the owner-script snapshot,
  puzzle adapter and FEN/annotation list:
  `build/experiments/phase4d5-20261020/`.
- Complete profile, printed puzzle outputs, audits and build/test logs:
  `results/phase4d5-20261020/`. Full-run evidence includes
  `puzzle-full-run.json`, `puzzle-full-parent.txt`, `puzzle-full-on.txt`,
  `puzzle-full-summary.json`, `independent-puzzle-full-all-audit.json` and
  `independent-puzzle-full-after-pins-audit.json`.
- Full-output SHA-256, parent:
  `dd5567bfe56582396641cfde02e4feb891105186c8da2d3c419f1a868750d4b2`;
  candidate: `9d3870fc0a9237882d3c8950052bc66c748ef858814c261da14fc1410db09e6b`.

The normal rebuild is separate from all GUI snapshots. All 31 protected pins
and the owner's README introduction are preserved, including the local
`tools/batch_positions.py` settings, which are excluded from this work's commit.
Historical campaigns and tools remain intact. No release, new match, default
promotion or GitHub push is part of this checkpoint.

Both full puzzle runs and their launcher have ended; the one-run daytime
exception is consumed. Next prioritize the
[clock boundary diagnostic](2026-10-19-clock-diagnosis.md),
validate any necessary repair and establish operational readiness before a
fresh qualification of existing conservative LMR. No cause or repair is
established yet. Broader 4D.6 reductions follow that decision. Do not tune this
exposed puzzle sample or reinterpret earlier failed campaigns.
