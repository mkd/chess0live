# Phase 4F.11 — NNUE update efficiency

Date: October 29, 2026. Parent: `1ca87d6`.

The owner authorized proceeding after the strength review. The objective is to
remove avoidable NNUE update work while preserving exact evaluation and search
policy. This is implementation/performance work; strength requires separate
equal-resource games. No search option or network change is part of this phase.

## Bounded diagnosis

Build a separate optimized parent with symbols; preserve the normal release,
GUI `0.1-dev-4b8b35d`, other stable bundles and completed campaign artifacts.
Reuse the CPU sampler with an explicit current-default preset: one thread,
64 MiB Hash, classic time management, LMR on, other experiments and Syzygy off.
Use all fifteen existing exposed roots in `countermove-profile.json`, converted
without position changes to the sampler format. Opening/middlegame depth is 5,
endgame depth is 6, with two measured repetitions after depth-5 warmups and a
120-second sampling window. Sampling is hotspot evidence, not throughput.
Resource admission and failure/cleanup records remain active. No concurrent
build or benchmark runs during sampling. Short runs use the normal local budget.

If feature discovery/update is material in this sample, implement an isolated
candidate. Prefer the smallest change that removes measured work: deriving
changed features between evaluated board states can precede search-stack
integration. A stack and refresh cache are follow-ups only if evidence supports
them. If this area is not material, record the finding and redirect diagnosis
to selective search; do not expand NNUE work merely to complete a design.

## Correctness before timing

Retain full feature enumeration and full-refresh evaluation as references.
Require exact feature-multiset, hidden-accumulator, PSQT and output agreement
through legal sequences, undo, sibling/arbitrary transitions, null moves,
castling, en passant, promotions, and king bucket/orientation changes. Verify
native/vector and scalar paths, reset and network-generation invalidation.
Run relevant native, sanitizer and worker-lifecycle checks, then fresh pinned
oracle comparison using isolated output paths. No upstream engine code is reused.

Before performance interpretation, all deterministic one-thread fixed-depth
iterations must match the parent in nodes, score, PV, best move and ponder on
all fifteen exposed roots, including cold and reused state. Use the existing
search comparison harness. Preserve failed checks and repair evidence.

## Interpretation and next checkpoint

First run one parent-versus-parent control at depth 6 with two repetitions;
record host noise before interpreting the engineering thresholds. Then use
three alternating comparison runs at depth 6 with three measured repetitions
per cold/warm case (180 searches per run). Cap individual searches at 20 seconds
and each run at 300 seconds. Require exact search agreement throughout.
A candidate is worth continued evaluation if each run's median over all 90
paired parent/candidate elapsed ratios exceeds 1.03 and every pooled root/state
median (nine ratios across the three runs) is at least 0.98. These are
engineering thresholds on exposed positions, not confidence bounds or Elo.
If the screen is too short/noisy or fails, report that outcome without relabeling
it a gain; any subsequent experiment needs a new declared protocol.

A full equal-time puzzle comparison and a paired strength match are later
checkpoints. Their protocols must distinguish tactical observations, statistical
uncertainty and playing-strength conclusions. Long runs require an appropriate
quiet overnight window or an explicit exception; this document creates no
schedule. Commit tested work locally on main; the owner handles publication.
