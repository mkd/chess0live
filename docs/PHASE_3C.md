# Phase 3C: performance across game phases

Status: [completed October 16, 2026](reports/2026-10-16-phase3c-gamephases.md).
Middlegames qualified with median ratios 1.087243 and 1.088055; endgames and
overall qualification remain inconclusive because the sparse pawn root failed
the 50 ms duration floor. All 432 searches matched exactly and replayed legally.
No engine or default changed. The original protocol below was frozen before
measurement in `results/phase3c-20261016/protocol.md`, SHA-256
`b404ce1f1b23171c36c37eb3acf2d561ae1c1601f08c4aa77f748dca64f82c3e`.
This later status note does not change those rules or that immutable record.

## Scope and original positions

The [Phase 3B result](reports/2026-10-16-phase3b-nnue-batching.md) measured opening
search only. This follow-up tests six middlegames and six endgames on the M5 Pro.
The independently composed [suite](../tests/data/performance-gamephases.json)
is selected for structural coverage before any engine scores or timings:
quiet and tactically active middlegames; rook, minor-piece, pawn, and mixed
endgames; three roots with each side to move within each phase.

Validate every FEN with the pinned `chess==1.11.2` referee: valid standard
position, nonterminal, no automatic/claimable draw, unique four-field position
key, and no overlap with the existing opening-suite roots. These are composed
positions, not claimed game histories or a representative random sample of
tournament play. FEN validity is not a proof of historical reachability.
Store category, selection reason, and provenance with each root. Keep this
performance suite separate from strength-validation data.

## Fixed artifacts and workload

- Baseline: preserved Phase 3A release, source `9daaade`, SHA-256
  `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
- Candidate: retained Phase 3B release, source `eb059b5`, SHA-256
  `2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.
- Pinned network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Existing unchanged `tools/compare_bench.py`; record it and its dependencies'
  digests, both executables, network, suite, position files, and protocol.
- **Depth 6 for all six middlegames; depth 8 for all six endgames.** The deeper
  endgame limit is chosen by material class, before timing, to reduce the risk
  of timer/transport noise dominating smaller trees. Do not adapt depths later.
- Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA ordering, Ponder and
  diagnostics off, Move Overhead 20 ms. Both binaries use their pinned defaults
  except explicitly set Threads/Hash/EvalFile. Recorded UCI identities must
  confirm the defaults. No clock-managed search, books, or CPU sampler.
- Clear the transposition table and complete readiness before each search.
  Exclude that setup from the external monotonic go-to-bestmove timing.
  One warmup per root/role, then **five measured repetitions**; alternate role
  order by root and repetition using the existing runner.

Run these six comparisons in exactly this order, with fresh output files:

| Run | Roots/depth | Baseline role | Candidate role |
| --- | --- | --- | --- |
| control-middlegame | Middlegame / 6 | Baseline | Baseline |
| control-endgame | Endgame / 8 | Baseline | Baseline |
| timing-middlegame-a | Middlegame / 6 | Baseline | Candidate |
| timing-endgame-a | Endgame / 8 | Baseline | Candidate |
| timing-middlegame-b | Middlegame / 6 | Baseline | Candidate |
| timing-endgame-b | Endgame / 8 | Baseline | Candidate |

This is 72 searches per run, **432 total**, including 72 warmups and 360 measured
searches. Only one worker actively searches, with two engines resident; use the
ordinary 50% daytime/80% nighttime budget and conservative combined memory
planning. No concurrent engine test, compile, or profile. Host background work,
CPU placement, and thermal state are uncontrolled and must be acknowledged.
Each search has a 30-second timeout; each comparison has a ten-minute outer
ceiling, and the complete campaign has a **15-minute wall-clock ceiling**, with
child-process cleanup. Stop on timeout, correctness/identity drift, or a resource
violation, preserving partial evidence and labeling remaining runs not started.
A noise gate failure alone does not stop the remaining declared runs.

## Predeclared decision rules

The paired ratio is baseline elapsed time divided by candidate elapsed time.
Independently reparse every raw response, including warmups. Require identical
per-depth depth/seldepth/nodes/score/PV, bestmove, and ponder across roles,
repetitions, and all three runs for that phase. Replay all PVs/bestmoves/ponders
legally from each FEN. Check expected counts/order, identities, asset hashes,
and independently recompute stored statistics. Any failure invalidates inference.

Assess the two phases separately; do not let a favorable phase hide the other:

1. **Repeatability:** the same-binary control's aggregate median ratio must lie
   in **[0.97, 1.03]**, its paired median absolute deviation must be **at most
   0.03**, and every root's median ratio must lie in **[0.95, 1.05]**.
2. **Timing floor:** in every control and candidate run, each root/role's median
   measured duration must be **at least 0.050 seconds**. Shorter or unstable
   measurements make that phase inconclusive, even if aggregate ratios look good.
3. **Positive aggregate:** both candidate runs for a phase must independently
   reach an aggregate median ratio of **at least 1.03**.
4. **Root regression guard:** pool each root's ten measured candidate-comparison
   pairs across A/B; every root median must be **at least 0.98**.

If exactness and noise gates pass but any root falls below 0.98, report an
**observed regression-guard failure** and reopen retention review separately.
Otherwise, failing a positive aggregate gate leaves the gain unconfirmed.
Both phases must pass to qualify performance across this composed sample. If
correctness fails, stop and investigate before any retention decision. This
phase does not retroactively alter the opening-only Phase 3B evidence or silently
revert a previously accepted implementation. Any rollback or revised test needs
its own explicit evidence and scope. No implementation tuning is part of 3C.

Report per-root median times, ratios, dispersion, role-order effects, and every
individual measured slowdown, with all roots retained. No extra repetitions,
root replacement, score-based selection, revised thresholds, or favorable-run
selection after inspecting results. An inconclusive outcome is a completed
validation checkpoint, not permission to repeatedly test until it passes.

These are engineering acceptance rules, not confidence intervals. Success
supports only this finite suite's throughput on this host, not Elo, universal
endgame speed, clock-managed playing strength, or another platform's performance.
Further optimization, parallel search, and strength campaigns remain separate.
