# Phase 4F.8 — contextual quiet-move ordering

Implementation protocol `phase4f8-continuation-history-v1`, October 28, 2026.
The implementation and this bounded validation plan are written before the
first candidate search. Phase 4F.7 is closed: its 512-game TT Move Hints result
was inconclusive, and that experiment remains off and parked.

## Hypothesis and fixed scope

Rank ordinary quiet replies using the colored piece and destination of the
preceding move. A worker-private one-ply continuation-history table supplements
the existing from/to history. The hypothesis is better ordering and earlier
useful cutoffs; this phase does not establish a playing-strength improvement.
Ordering affects which moves receive LMR, so unchanged pruning predicates are
not a guarantee of unchanged playing strength.

The new UCI check option is `Continuation History`, default `false`. It is
independent of Countermove Ordering, TT Move Hints and the historical combined
policy experiment. Do not promote any option or change that frozen recipe.

- Each enabled worker allocates 768 × 768 signed 16-bit entries: nominally
  1,179,648 bytes (1.125 MiB), outside the UCI Hash allocation. Disabled workers
  have no continuation table. Allocate all replacements before committing a
  policy transition or starting any worker; allocation failure preserves the
  previous configuration.
- A context is the original moving piece, including its color, and destination.
  Promotions use the original pawn; the root has no previous-move context.
- Add the contextual value only in the ordinary quiet-history ordering tier.
  Preserve the TT, promotion, capture, killer and countermove priority tiers.
  Cache each sorting score once, as in the existing ordering implementation.
- Reward a completed ordinary quiet beta-cutoff and penalize only previously
  searched quiet moves. Use the existing fixed gravity limit 16,384 and bonus
  `min(2048, depth * depth * 24)`. Do not tune these from the test results.
- Exclude quiescence and null-probe, verification and ProbCut subtrees from
  contextual lookup and learning. Completed ordinary subtrees may learn before
  a later root interruption; never learn from the interrupted move itself.
- Halve history at each new search. Clear it with the existing new-game,
  clear-cache and policy-change lifecycle. A policy change also clears TT bounds
  so different search configurations do not reuse those scores.
- Diagnostics report enabled state, aggregate entries/allocated bytes and
  lookup/nonzero/update counts, only with Search Diagnostics enabled. They do
  not measure cutoff quality or strength.

## Bounded implementation validation

1. Standalone table tests: all context identities, isolation, disabled storage,
   signed decay, extreme bonuses, an independent gravity reference and injected
   allocation failure.
2. Direct search tests: tier priorities, real-move contexts, completed cutoff
   rewards/penalties, speculative-search exclusion, reversible state, public
   worker lifecycle and transactional allocation.
3. UCI tests: advertised default, strict setting parsing, legal PV/best/ponder,
   exact node limits, stop/ponder/infinite handling, terminal roots, clear/new
   game and option transitions, with one and four workers.
4. Existing core, NNUE and search regressions; focused ASan/UBSan and TSan checks
   where supported. Record unsupported or failed checks explicitly.
5. Deterministic one-worker disabled-mode comparison against the preserved
   parent executable on all 15 existing exposed roots in
   `tests/data/countermove-profile.json`: depth 6, two repetitions, an immediate
   cold/warm search per fresh role/root process, 180 searches in total. Compare search
   iterations, scores, PVs, nodes and best/ponder, excluding elapsed time/NPS.
   A small enabled/disabled screen checks legal results and reports all work
   differences without selecting favorable positions. No timing claim is made
   while other applications, including LM Studio, may be active.

Keep the normal release, stable GUI bundle `0.1-dev-4b8b35d`, frozen Phase 4F.7
artifacts and the owner's batch tool untouched. Use
`build/experiments/phase4f8/native/` and new result directories. The starting
manifest is `results/phase4f8-20261028/initial-state.json`; the parent binary is
`build/experiments/phase4f7/chess0live`, SHA-256
`6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f`.
Use the existing pinned network `nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

## Subsequent qualification

Correctness checks and an exposed development screen cannot qualify strength.
After this implementation checkpoint, freeze a separate matched 39-position
tactical comparison at 60 seconds per position/configuration, followed by a
separately declared paired game test if the tactical gate permits. Do not reuse
the Phase 4F.7 campaign or claim its confidence interval covers this candidate.
Long runs need the overnight policy or a fresh owner exception and a confirmed
quiet host. No long test, retry, enlarged sample or automatic schedule is
authorized by this implementation protocol.
