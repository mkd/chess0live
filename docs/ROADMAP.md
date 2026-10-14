# Development plan and current phase

Keep this page and [handover](HANDOVER.md) current at each material checkpoint.
Progress updates should name the active phase and step, explain what was learned,
and distinguish an implemented experiment from an accepted strength improvement.
The owner handles GitHub pushes. Phase numbers are work areas, not release names.

## Current: Phase 2 — search efficiency and time management

The October 14 Cute Chess feedback confirms useful initial GUI integration and
exposes expensive opening iterations and severe subsequent time pressure.
The [game review](reports/2026-10-14-cutechess.md) records the evidence and limits.

| Step | Deliverable | Status |
| --- | --- | --- |
| 2A | Measure completed and interrupted iteration time/work, with reproducible profiles | Complete: diagnostics, profiler, and checked accounting |
| 2B | Test a forecast policy that avoids starting an iteration unlikely to fit its budget | Implemented and profiled; opt-in, awaiting strength qualification |
| 2C | Evaluate selective-search and move-ordering changes independently | Active: LMR implemented and profiled, opt-in; ordering experiment next |
| 2D | Qualify promising candidates with frozen, paired-opening blitz matches | Prepared as a gate; no strength gain established |

For 2B, the first soft-target gate stopped too early in development profiles
and was rejected. Its narrower replacement forecasts against the hard deadline
while retaining classic soft stopping. It is deliberately optional: saving clock time
can also mean giving up a useful search depth. Profiles must report both saved
time and completed depth, abandoned work, scores, and moves. Only measured
playing strength can justify a claim that this improves chess strength. See the
[results and decisions](TIME_MANAGEMENT.md): the revision retained completed
depth in 32/36 development comparisons, and the same move in all 36. These
results guide the next test; they do not establish an Elo gain.

For 2C, the [selective-search plan](SELECTIVE_SEARCH.md) fixes the first reduction
policy and development checks before measurements. Time policy remains classic
on both sides of this comparison. Move-ordering changes follow as a separate
experiment; the 2B validation openings remain reserved for 2B.
The first candidate passed native/scalar/sanitizer checks and preserved the
default-off search signatures. Depth-5 work dropped 49.79% across the sampled
roots with matching final decisions; at equal nodes, deeper nominal searches
also changed a move and some scores/PVs. This is a research checkpoint, not
completed strength qualification or completion of all Phase 2C work.
The eight-game operational smoke scored 2W/2D/4L for LMR with no protocol errors,
time forfeits, or truncations. LMR stays off by default; the unfavorable small
sample establishes no strength margin in either direction.

Small daytime correctness/profiling checks use the 50% resource budget. Long
campaigns run during 23:00–07:00 Europe/Helsinki at 80%, with a manual override
available. Preparing a command does not start it or create a recurring schedule.
Do not describe a pending campaign as active or completed.

## Other phases and continuing work

1. **Playable foundation:** legal moves, reversible state, pinned SF19 NNUE
   parity, single-worker UCI search, perft, tests, and initial GUI feedback are
   implemented. This remains `0.1-dev`, not a completed release or rated engine.
2. **Search and time management:** the active work above. Keep changes isolated
   enough to attribute their effects and record rejected/inconclusive results.
3. **Desktop performance and parallel search:** efficient move generation and
   NNUE updates, CPU backends, then multicore search with aggregate resource
   limits and correctness/strength checks. NPS alone does not establish Elo.
4. **Broader execution and network tooling:** finish runtime validation across
   required targets and reproducible trainer/export integration. Portable build
   work can proceed alongside earlier phases when toolchains are available;
   do not postpone correctness or label build-only targets runtime-verified.

Every phase preserves the frozen GUI bundle `0.1-dev-4b8b35d`, the NNUE oracle,
and core rule/UCI checks. Release 0.1 only after its [acceptance gates](VALIDATION.md)
are satisfied. Decisively exceeding Stockfish 19 remains a research objective;
none of these phase labels implies that it has been achieved.
