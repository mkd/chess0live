# Development plan and current phase

Keep this page and [handover](HANDOVER.md) current at each material checkpoint.
Progress updates should name the active phase and step, explain what was learned,
and distinguish an implemented experiment from an accepted strength improvement.
The owner handles GitHub pushes. Phase numbers are work areas, not release names.

## Current checkpoint: Phase 2D initial screens complete; Phase 3A next

The October 14 Cute Chess feedback confirms useful initial GUI integration and
exposes expensive opening iterations and severe subsequent time pressure.
The [game review](reports/2026-10-14-cutechess.md) records the evidence and limits.

| Step | Deliverable | Status |
| --- | --- | --- |
| 2A | Measure completed and interrupted iteration time/work, with reproducible profiles | Complete: diagnostics, profiler, and checked accounting |
| 2B | Test a forecast policy that avoids starting an iteration unlikely to fit its budget | Implemented and profiled; opt-in, awaiting strength qualification |
| 2C | Evaluate selective-search and move-ordering changes independently | Initial experiments complete: both opt-in; bounded LMR loss diagnosis complete |
| 2D | Qualify promising candidates with frozen, paired-opening blitz matches | Initial time-policy and LMR screens complete, both inconclusive; further qualification deferred |
| 3A | Establish a reproducible performance baseline and identify one measured bottleneck | Next checkpoint; not started |

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
on both sides of this comparison. Move ordering has a separate
experiment; the 2B validation openings were reserved for that time-policy screen.
The first candidate passed native/scalar/sanitizer checks and preserved the
default-off search signatures. Depth-5 work dropped 49.79% across the sampled
roots with matching final decisions; at equal nodes, deeper nominal searches
also changed a move and some scores/PVs. This is a research checkpoint, not
completed strength qualification.
The eight-game operational smoke scored 2W/2D/4L for LMR with no protocol errors,
time forfeits, or truncations. LMR stays off by default; the unfavorable small
sample establishes no strength margin in either direction.
The separate [SEE capture-ordering experiment](MOVE_ORDERING.md) passed native,
scalar, and sanitizer checks with LMR disabled and classic timing. It preserved
all 24 default-mode signatures. Its depth-5 comparisons used 4.72% fewer nodes
with matching moves/scores/PVs; equal-node searches gained one depth on one
root and lost one on another. The eight-game smoke scored 2W/4D/2L with no
operational failures. MVV-LVA remains the default.

The [bounded LMR loss diagnosis](reports/2026-10-14-lmr-losses.md) used the frozen
LMR executable. All eight selected roots gave the same off/on best move, and
40 common-depth scores/PVs matched. No reduction parameter changed; this finite
post-hoc check does not establish that reductions are harmless.

The initial Phase 2C experiment checkpoint is complete. **Phase 2D has completed
its first two screens**, without promoting an experimental default. Its
[first time-policy screen](reports/2026-10-15-phase2d-time-policy.md) completed
all 32 opening pairs / 64 games at 60+0.6 with one worker. It ran October 15,
14:24–17:18 Helsinki, under the owner's one-run daytime exception, from preparation
commit `2cf55f7`. Forecast scored **14W/43D/7L, 35.5/64 points (55.47%)**. The
independent audit passed with no exclusions, operational failures, or artifact
drift. Its conditional 95% pair-score interval is **31.46–79.48%**: the predeclared
decision is **inconclusive**, so classic remains default and forecast remains
experimental. A favorable point estimate does not establish a strength gain.
The raw completed campaign is `results/phase2d-time-policy-20261015/`.

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) completed all
64 fresh opening pairs / 128 games at 60+0.6 with classic timing. It ran from
October 15 23:00:08 to October 16 05:41:20 Helsinki, inside the ordinary night
window, from preparation commit `842ee41`. LMR scored **35W/82D/11L,
76/128 points (59.375%)**, with no exclusions, operational failures, or artifact
drift. Independent audit verified 17,175 legal plies and 15,191 searches.
The conditional 95% pair-score interval is **42.40–76.35%**: the predeclared
result is **inconclusive**, so LMR stays off. The favorable score does not
establish strength or equivalence. Raw evidence is
`results/phase2d-lmr-20261015/`; the job and its sleep assertion have ended.

**Next checkpoint: Phase 3A measurement only.** Freeze the current default
baseline (classic timing, LMR off, MVV-LVA) and record binary/source/network,
compiler, flags, and CPU identities. Establish timing repeatability with the
existing alternating benchmark harness and identical builds, then collect one
bounded CPU profile on development positions separately from timed comparisons.
Deliver the reproducible baseline and one optimization proposal supported by
measured cost, before changing engine behavior or implementation.

Source inspection suggests NNUE feature enumeration/sorting, move-list
allocations, and ray-based attacks as possible costs; these are hypotheses,
not measured bottlenecks. Select only one after profiling. Predeclare exact
search-equivalence and timing criteria before implementing it. Depending on
scope, require perft/legal-move/reversible-state checks or full-refresh versus
incremental NNUE agreement and pinned feature/accumulator/output parity, plus
relevant native/scalar/sanitizer and UCI checks. Preserve stalemate/checkmate
precedence in quiescence. Measured speed does not establish an Elo gain.

Phase 3A has not started. Further LMR, forecast, and SEE strength qualification
remains explicitly deferred, not passed. Do not opportunistically extend or
retune either completed sample. A later campaign needs fresh openings and a
predeclared sample/decision rule that justifies its cost. Both completed suites
are now exposed evidence; repeated roots add no independent openings.
No long job or automatic schedule is active. Keep the preserved GUI bundle
`0.1-dev-4b8b35d`, all frozen candidates, and exact NNUE oracle intact.

Small daytime correctness/profiling checks use the 50% resource budget. Long
campaigns run during 23:00–07:00 Europe/Helsinki at 80%, with a manual override
available. Preparing a command does not start it or create a recurring schedule.
Do not describe a pending campaign as active or completed.

## Other phases and continuing work

1. **Playable foundation:** legal moves, reversible state, pinned SF19 NNUE
   parity, single-worker UCI search, perft, tests, and initial GUI feedback are
   implemented. This remains `0.1-dev`, not a completed release or rated engine.
2. **Search and time management:** the recorded experiments above. Keep changes isolated
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
