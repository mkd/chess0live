# Phase 4D.5: quiescence SEE checkpoint

## Decision and scope

The isolated candidate is implemented and checked; **`QSearch SEE Pruning`
remains off by default**. The finite development screen is complete. The full
matched 60-second puzzle checkpoint remains pending under the overnight policy,
and no playing-strength qualification has run. Do not treat implementation
completion as satisfying those evidence requirements.

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
en passant, all promotion choices, stalemate children and the eight-piece
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

## Puzzle progress

The unchanged owner-edited batch script and a temporary configuration adapter
use the existing printed-output workflow. The matched 1,000-ms smoke is
recorded separately from the required 60,000-ms checkpoint. Both use the same
39 supplied FENs in order, fresh processes, one worker, Hash 64 MiB and explicit
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

The full matched 60-second baseline/candidate pair remains pending. Allow about
78 minutes of search plus startup for sequential runs. No overnight schedule
or daytime exception was inferred. Expected mate distances are supplied puzzle
annotations, not certified answers; neither puzzle comparison replaces matches.

## Reproduction and preservation

- Parent source: `dcfd23c4e1f346decb5b3db99426c957ec6ca811`.
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
  `results/phase4d5-20261020/`.

The normal rebuild is separate from all GUI snapshots. All 31 protected pins
and the owner's README introduction are preserved, including the local
`tools/batch_positions.py` settings, which are excluded from this work's commit.
Historical campaigns and tools remain intact. No release, new match, default
promotion or GitHub push is part of this checkpoint.

Complete the full puzzle comparison before closing this validation checkpoint.
Then move to a separate bounded candidate in the search plan without tuning
this exposed sample. The [clock boundary diagnostic](2026-10-19-clock-diagnosis.md)
still precedes any further playing-strength qualification.
