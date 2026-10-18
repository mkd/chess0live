# Development plan and current phase

Keep this page and [handover](HANDOVER.md) current at each material checkpoint.
Progress updates should name the active phase and step, explain what was learned,
and distinguish an implemented experiment from an accepted strength improvement.
The owner handles GitHub pushes. Phase numbers are work areas, not release names.

## Current checkpoint: Phase 3I receipt fix validated; match I/O isolation next

The October 14 and [October 18 Cute Chess feedback](reports/2026-10-18-cutechess.md)
provide useful initial GUI integration evidence and expose expensive opening
iterations and severe subsequent time pressure. The latest report records two
draws without reported errors, a partial PGN, and matching legal moves/depth-2
divides at all 122 saved positions. The intended Phase 3F snapshot's actual GUI
settings were not captured; the missing final positions limit termination checks.
Clock allocation remains a separate research priority after the fixed LMR screen.

| Step | Deliverable | Status |
| --- | --- | --- |
| 2A | Measure completed and interrupted iteration time/work, with reproducible profiles | Complete: diagnostics, profiler, and checked accounting |
| 2B | Test a forecast policy that avoids starting an iteration unlikely to fit its budget | Implemented and profiled; opt-in, awaiting strength qualification |
| 2C | Evaluate selective-search and move-ordering changes independently | Initial experiments complete: both opt-in; bounded LMR loss diagnosis complete |
| 2D | Qualify promising candidates with frozen, paired-opening blitz matches | Initial time-policy and LMR screens complete, both inconclusive; further qualification deferred |
| 3A | Establish a reproducible performance baseline and identify one measured bottleneck | Complete: exact-search baseline, audited CPU sample, and bounded NNUE proposal |
| 3B | Test batched NNUE feature-column updates with exact arithmetic and search parity | Complete and retained: correctness/oracle parity, all three timing gates, all root guards passed |
| 3C | Validate the retained speedup across middlegames and endgames | Complete: middlegames qualified; endgames inconclusive under the duration floor |
| 3D | Characterize the short endgame workload before new qualification | Complete: 40 exact/legal searches; depth 12 proposed under the fixed diagnostic rule |
| 3E | Requalify endgames using the longer pawn workload | Complete: all 216 searches exact/legal; revised endgame workload qualified at 8.4–8.9% higher sampled throughput |
| 3F | Profile the updated engine and implement one justified NNUE improvement | Complete and retained: all 576 searches exact/legal; all three game-phase performance gates passed |
| 3G | Run fresh blitz strength qualification for the existing LMR experiment on the updated engine | Complete and audited: 225W/155D/132L (59.08%); six candidate clock forfeits trigger the operational-regression gate, so LMR stays off |
| 3H | Diagnose clock overruns, reproduce a defect, and validate a bounded repair | Complete bounded checkpoint: command-time accounting fixed; native/scalar/sanitizer and 52 clock probes passed; most historical flagfalls remain unexplained |
| 3I | Investigate short-clock resilience under scheduling and transport delays | Complete: same-batch match logging bias reproduced and fixed; 212 checks and 12 diagnostic controls passed; engine and historical results unchanged |
| 3J | Isolate match persistence from active protocol clocks | Next: bounded buffering, slow-writer/failure tests, then a small predeclared operational check before fresh strength qualification |

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

**Phase 3A is complete.** The [result report](reports/2026-10-16-phase3a-baseline.md)
records a frozen default release baseline and optimized symbol build, all 12
original development histories, and the ordinary 50% daytime budget. All 192
same-binary depth-5 searches matched exactly; median paired ratio was 0.998546,
with observed MAD 0.008123. Another 48 searches verified the symbol build's
search equivalence. All reported moves/PVs passed independent legal replay.

A separate 120-second CPU sample contained 7,413 observations inside search
frames. NNUE accounted for 85.04%, including 58.69% in accumulator update and
26.10% in inference. These nested shares overlap. Both independent aggregations
agree; the raw stacks and audits are retained in `results/phase3a-20261016/`.
The profile covers shallow opening search and omits the active clock path.
No engine optimization, speed gain, or strength gain was established.

**Phase 3B is complete and retained.** The [result](reports/2026-10-16-phase3b-nnue-batching.md)
records streaming batches of eight feature-column views and 32-lane hidden tiles.
Features, inference, search, and default policies are unchanged. Native, scalar,
and sanitizer suites passed, including 360 independent arithmetic transitions;
the full 2,057-position SF19 oracle retained exact corpus/stage/output digests.
All 576 benchmark searches matched exactly and replayed legally. The three
declared timing medians were **1.078081, 1.079836, 1.083612**, above the 1.03
gate; all 24 pooled root/depth medians exceeded the 0.98 guard. This is roughly
8% higher sampled opening-search throughput, not a strength improvement.

**Phase 3C is complete.** The [result](reports/2026-10-16-phase3c-gamephases.md)
records all 432 exact/legal searches on 12 original composed roots. Both
middlegame runs passed the frozen gates, at **1.087243 and 1.088055** median
ratios. Endgame runs were favorable, but the sparse pawn root's 30–32 ms searches
failed the 50 ms duration floor; endgame and combined qualification remain
**inconclusive**. Nothing was omitted or retuned. The six-run campaign completed
in 844.997 seconds under the normal daytime budget, with no engine changes.

**Phase 3D is complete.** The [report](reports/2026-10-17-phase3d-workload.md)
records all 40 exact/legal baseline-only searches at depths 8–12. Depth 12
meets the fixed proposal rule, with 329.881/322.562 ms role medians, ratio
0.999090 and MAD 0.028507. Depth 10's timing instability remains recorded.
Three pairs and a near-limit MAD do not establish lasting repeatability.
The campaign completed in 7.441256 seconds within the normal daytime budget;
engine code, binaries, defaults, and Phase 3C's decision are unchanged.

**Phase 3E is complete.** The [result](reports/2026-10-17-phase3e-endgames.md)
qualified performance on the revised six-root endgame sample: complete-round
ratios **1.089113 / 1.084243**, all 216 exact/legal searches, all control,
duration, and root guards passed. The 353.663-second campaign used one active
worker under the ordinary daytime budget. Two individual candidate slowdowns,
control outliers, and upward absolute-time drift remain in the report. No old
timings were pooled; Phase 3C's earlier decision remains unchanged.

**Phase 3F is complete and retained.** The [report](reports/2026-10-17-phase3f-dense.md)
records fresh all-phase profiles, a committed isolated dense-kernel hypothesis,
and independent arithmetic/native/scalar/sanitizer/full-oracle checks. Four
outputs now share each activation vector in the NEON multi-output layers. All
576 performance searches matched exactly and replayed legally; every gate passed.
Paired throughput gains versus retained Phase 3B were **19.6% opening,
19.7–21.4% middlegame, and 32.4–39.5% endgame**. Four slowdowns and substantial
absolute-time drift remain included. No rating, release, or search-default change.

**Phase 3G is complete and audited.** The [result report](reports/2026-10-18-phase3g-lmr.md)
records all 256 pairs / 512 games at 60+0.6, with LMR on versus off in the same
qualified Phase 3F engine. The one authorized daytime attempt ran October 18,
08:54–15:12 Helsinki, using four workers under the normal 50% resource budget.
All 512 games passed independent replay, clock, option, and integrity checks.
LMR-on scored **225W/155D/132L, 302.5/512 points (59.08%)**, with conditional
95% pair-score bounds **50.59–67.57%**. This clears the numerical screen, but
**six candidate clock forfeits take precedence** under the frozen protocol:
the decision is **operational regression; keep LMR off**. Seven baseline clock
forfeits also occurred, so the evidence does not isolate LMR as their cause.

**Phase 3H's bounded checkpoint is complete.** The [result report](reports/2026-10-18-phase3h-clocks.md)
records a reproduced accounting defect: preparation and worker dispatch after
`go` were uncharged. Search now uses the command's original monotonic receipt.
Native, scalar, sanitizer, deterministic expired-receipt, and UCI regression checks
passed. All 52 fresh-table probes (13 exposed histories, both LMR modes, both
executables) were legal and on time. The frozen baseline also passed, so these
probes do not reproduce the historical losses or establish improved reliability.
One historical case is consistent with the repaired gap; the other 12 remain
unexplained by available timestamps. An artificial process pause demonstrated
that command accounting cannot prevent a loss when the host suspends the engine.

**Phase 3I is complete.** The [report](reports/2026-10-18-phase3i-receipt.md)
records a deterministic match-runner defect: slow logging inflated time charged
to a bestmove already received in the same input batch. Callback-entry timing
fixes it while preserving parser and audit behavior. All 212 workflow checks
passed. Twelve live controls distinguished consumer-only sleep from engine
suspension; no historical clock loss is reclassified. Engine code is unchanged.

**Phase 3J is next:** remove synchronous persistence from active protocol clocks
with bounded buffering and explicit error handling. Test slow writes across
separate callbacks, then use a small declared operational check before fresh
strength qualification. This is not a requirement to eliminate arbitrary OS
suspension. Reserve/allocation changes still need their own evidence. No new
match or schedule is active, and no additional GUI tournament is required.
Both stable GUI bundles remain preserved; Phase 3G's decision and defaults stand.

LMR confirmation and forecast/SEE qualification remain deferred, not passed.
Do not extend or pool the completed Phase 2D and Phase 3G samples. Parallel
search, broader runtime validation, and release acceptance remain open.

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
