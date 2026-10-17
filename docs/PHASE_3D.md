# Phase 3D: characterize the short pawn-ending workload

Status: preparation, before engine measurements. This is a baseline-only
diagnostic. Preserve a frozen copy and input hashes before the first search.
No engine implementation, search default, or candidate performance comparison
belongs in this phase. Phase 3C's inconclusive endgame result stays unchanged.

## Fixed inputs

Use only `gamephases-eg-05` from the original
[game-phase suite](../tests/data/performance-gamephases.json):

```text
8/8/5k2/7p/2K2P2/8/8/8 w - - 0 50
```

The composed FEN has an empty history. It was selected for this diagnostic
because its Phase 3C searches were below the declared 50 ms floor. This is
post-hoc workload characterization, not new held-out evidence or root selection
for a favorable candidate outcome. No opponent engine assets are used.

Both roles of the unchanged `tools/compare_bench.py` must run the **same frozen
Phase 3A baseline** from source `9daaade`:

- Executable: `build/experiments/phase3a-20261016/release/chess0live`.
- SHA-256: `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA, Ponder/diagnostics
  off, Move Overhead 20 ms. Explicitly set Threads/Hash/EvalFile; confirm other
  fresh-process defaults from recorded UCI identity and pinned setup code.

The runner's label `candidate` means the **second baseline process** here.
The retained Phase 3B binary may be hash-checked for preservation but must not
be launched. Freeze tool, suite, position-file, protocol, production-source,
network, preserved-binary, and launcher identities in the manifest.

## One bounded ladder

Run depths **8, 9, 10, 11, 12**, in that order, once through the ladder.
Each level uses one warmup and three measured searches per role: eight searches
per level, **40 total**, including ten warmups and 30 measured searches.
Alternate role order by repetition through the existing helper. Clear search
state and complete readiness before each search, outside external monotonic
go-to-bestmove timing. Start fresh processes at each depth.

One search worker is active, with two baseline processes resident. Use the
ordinary 50% daytime/80% nighttime resource budget; no override or schedule.
No concurrent engine tests, compilation, CPU sampler, or match. Host background
activity, core placement, and thermal state remain uncontrolled.

Bound each search to **30 seconds**, each depth comparison to **60 seconds**,
and the complete campaign to **300 seconds**. Recheck frozen identities before
each level and after completion. On timeout, interruption, correctness/identity
drift, or resource failure, clean up the whole subprocess group, preserve partial
evidence, and mark remaining levels not started. Do not skip a slow level or add
repetitions. Failure of a timing-selection condition alone does not stop the
remaining fixed levels.

## Validation and proposal rule

Independently parse every raw response, including warmups. Require exact
iteration depth/seldepth/nodes/score/PV, bestmove, and ponder agreement within
each depth. Common-depth **iteration records** must match across levels too;
final bestmoves/ponders may change as depth increases. Legally replay every PV,
bestmove, and ponder with pinned `chess==1.11.2`. Audit sample/run order, counts,
identity, resource settings, file hashes, timing consistency, and summaries.

Only after **all five levels and their audit pass**, propose the shallowest
tested depth meeting all of these conditions:

1. Both role medians are **at least 0.200 seconds**. This gives margin above the
   earlier 50 ms floor; it does not guarantee a future candidate meets that floor.
2. Every measured search at that depth takes **at most 5.000 seconds**.
3. The median paired first-role/second-role ratio lies in **[0.97, 1.03]**.
4. Its paired median absolute deviation is **at most 0.03**.

No passing level, invalid evidence, or an incomplete ladder means **no proposed
depth**. Do not select an earlier level after a later timeout. Report every
level's nodes, score, move/PV, warmup/measured durations, variation, and order
effects. Changes in final score or move with depth are diagnostic observations,
not tactical-quality or strength claims.

The proposal rule is an engineering heuristic based on three pairs per depth,
not a confidence interval or proof of lasting repeatability. A proposed depth
needs a separately frozen future comparison with exactness, noise, duration,
and regression gates. There is no candidate speed gain or Elo result in Phase
3D, and no retrospective change to Phase 3C's decision.
