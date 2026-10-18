# Validation and experiment protocol

## Phase 4D.2 current-engine LMR qualification — October 18, 2026

The [protocol](PHASE_4D2.md) fixes 1,024 games and 512 reversed-color pairs,
eight workers, fresh unsearched inputs, explicit unrelated options off, and a
fixed next-07:00 cutoff. Independent raw-game and aggregate auditing is mandatory.
Preparation and launch evidence are in the
[checkpoint record](reports/2026-10-18-phase4d2-preparation.md). The eight-worker
load check passed all 24 clock-controlled replies, eight stops and reuse checks;
readiness passed without a held-out search. None of these operational checks
establishes strength. Existing LMR remains disabled until a complete qualifying
result and explicit default review. The pair-level interval is conditional on
independence; related stems and shared host load are documented limitations.

## Baseline verification — October 13, 2026

Native host: macOS 26.7.1 ARM64, Apple Clang 21.0.0, C++26 mode. The full
`make -j2 test` and `make -j2 MODE=sanitize test` suites passed, including
AddressSanitizer and UndefinedBehaviorSanitizer. These checks exercised legal
move generation/perft, FEN and state restoration, real-network evaluation,
incremental refresh/backtracking, hostile-file rejection, search limits and
draw/mate rules, and UCI lifecycle behavior. The ordinary UCI suite also tests
launching by bare executable name through PATH from a different directory.

The pinned network SHA-256 was verified locally. Exact upstream NNUE comparison
is documented with corpus/output digests and reproduction commands in
[NNUE](NNUE.md). This is finite-corpus compatibility evidence, not a formal proof
for every possible position or network. A local benchmark completed with saved
binary/network/position hashes; it provides no Elo or match-strength evidence.

Three foreign targets cross-compiled; they were not executed. See
[portability](PORTABILITY.md) for compiler/runtime details and remaining gaps.
No tournament results, measured Elo rating, parallel search validation, or
training outcome is claimed for this baseline.

## Independent referee checks — October 13, 2026

`make verify-moves` compares every legal root move and each perft branch with
the pinned `chess==1.11.2` reference. The release binary passed all 93 depth-2
cases: 64 deterministic reachable random positions and 29 initial/special/mirrored
fixtures. A depth-3 check also passed all 37 cases (8 random plus the fixtures).
A deliberately incorrect mock engine produced failure records and a nonzero
exit status. These are correctness checks, not strength measurements.

The default seed is `18938320320349523`; the ordered FEN corpus SHA-256 is
`d2d60c101811d895dc3dc309f0f4079258aedab9937abf15a25b46a56cbd28d4`.
The checked binary SHA-256 is
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
The ignored `results/move-verification.json` contains the full inputs, branch
comparison summaries, tool hash, and environment metadata.

## Match-runner verification — October 13, 2026

`make test-match` passed 17 paired-statistics tests and 13 subprocess/referee
integration tests. Coverage includes swapped colors, full opening history,
PGN replay, illegal/null opening rejection, protocol errors and timeouts,
readiness excluded from the chess clock, real clock losses without a credited
increment, resource overrides, artifact changes, and inference exclusions.

A real two-game smoke run against the separately built pinned Stockfish 19
completed with no protocol failures, truncations, or clock losses. Both games
ended in checkmate; chess0live lost both. Settings were 1 second plus 0.01 seconds
per move, one thread, 64 MiB hash, 20 ms move overhead, seed `20261013`, one pair
from the development suite (`development-02`), and a 256-ply safety limit.
Both PGNs replayed legally to the recorded final positions. This deliberately
short run validates the workflow; it is not a blitz rating or evidence for a
strength margin. No confidence interval is produced.

Evidence is in ignored `results/match-smoke-sf19-20261013/`: the manifest, frozen
opening suite, game records, PGNs, raw protocol logs, and summary. The manifest
records source labels, runner/binary/network hashes, platform and actual options.
See [match testing](MATCHES.md) for the separate opponent build and its PGO flags.

## Owner-run GUI feedback — October 14, 2026

Two newly supplied 180+2 Cute Chess games against Gargantua 2.1 completed with a
draw as White and a checkmate loss as Black. The owner reports working UCI GUI
integration. Independent replay verified all 169 plies and both terminations;
the frozen snapshot's legal move sets and native/scalar/pinned-SF19 NNUE stages
and raw/wrapped outputs agreed at all 171 recorded boards, including initial
positions and repeats. The frozen snapshot's binary hash remains unchanged.

The [feedback report](reports/2026-10-14-cutechess.md) preserves PGNs, digests,
reproduction findings, metadata limits, and next hypotheses. Time allocation
deserves further testing; no immediate engine correctness defect was reproduced.
These two exploratory games establish neither a rating nor a strength gain.

## Phase 2 time-policy checkpoint — October 14, 2026

The opt-in hard-deadline forecast candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
These include the real-network 537-position incremental/full-refresh check,
perft/rule/state tests, deterministic forecast boundaries, interrupted-iteration
accounting, explicit-limit/ponder exclusions, and UCI option/lifecycle checks.
The evaluator and position implementations are unchanged; the full separate
Stockfish parity corpus was not rerun for this time-control-only change.

Tool checks passed: 15 profiler tests, 17 paired-statistics tests, 17 match-runner
tests, and 11 equal-work comparison tests. New match checks verify per-engine
options, advertised types, protected common settings, and frozen configuration.
The profiler checks raw diagnostics, exact node totals, partial failures,
artifact stability, resource changes, and timing-accounting consistency.

Default classic search retained exactly the frozen `0.1-dev-4b8b35d` signatures
at all 24 fixed-depth comparisons, including warmups (three roots, depth 5,
three measured repetitions per binary). Timing variation does not establish a
throughput improvement. The optional forecast changes clock allocation, so
clock-managed profiles are assessed for completed depth and moves as well as
time and interrupted work; they do not require identical final results.

The [experiment record](TIME_MANAGEMENT.md) separates the rejected soft-target
candidate from its hard-deadline revision and preserves both evidence sets.
The two four-game operational smokes completed without errors or time forfeits.
Independent replay verified 577 legal plies for the first and 467 for the revision;
each produced two checkmates and two threefold draws. The revision scored
2W/2D/0L, versus the first candidate's 1W/2D/1L, on the same two development pairs.
Correctness and short operational matches are not a strength acceptance gate.
Classic remained the default; the longer held-out blitz test had not run at
that checkpoint. Its subsequent Phase 2D result is recorded below.

## Phase 2C selective-search checkpoint — October 14, 2026

The conservative LMR candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
The policy tests cover eligibility boundaries, checks, mate windows, special
moves, advanced pawn pushes, and ordering hints. A bounded real-network search
exercises both confirmed and rejected reduced probes, an interrupted iteration,
legal PVs, and restoration of baseline results after switching policies. Existing
rule, limit, cancellation, and ponder cases also run with LMR enabled.

The new profiler passed 12 tests, including different search trees, PV/bestmove/
ponder legality, counter accounting, exact node caps, partial search/readiness
failures, and artifact mutation. The existing 15 clock-profiler, 17 statistics,
17 match-runner, and 11 comparison tests passed. NNUE and position code are
unchanged; their normal 537-position incremental checks passed in all three
build modes. The separate full Stockfish oracle corpus was not rerun for LMR.

The [selective-search experiment](SELECTIVE_SEARCH.md) records the frozen
candidate, default-equivalence check, development profiles, and short game test.
These are finite correctness and operational checks. Reduced fail-lows remain
heuristic; this checkpoint does not establish playing strength or make LMR the
default.

Default-off search matched all 24 frozen-parent samples exactly. The depth-5
profile completed 48 searches and the 200,000-node profile completed 24, with
legal PVs and consistent accounting. The eight-game paired operational smoke
scored 2W/2D/4L for LMR, with six checkmates and two threefold draws, no failures,
time forfeits, or truncations. Its unfavorable score is documented without
turning four development pairs into a strength estimate.
The Linux ARM64, Linux x86-64, and Windows x86-64 binaries also rebuilt and linked
successfully; file inspection confirmed target architectures. They remain
cross-build-only. No RISC-V64 or Windows ARM64 build/runtime evidence was added.

## Phase 2C exchange-ordering checks — October 14, 2026

Native `make -j2 test`, `make -j2 SIMD=scalar test`, and
`make -j2 MODE=sanitize test` passed, including 28 composed/reflected exchange
cases and 4,117 generated comparisons against an independent slow legal-move
reference. Search tests exercise genuine negative-exchange classification,
forced losing-capture retention, warm policy switching in both directions,
interrupted node accounting, and diagnostics invariance. Rule, stop, and ponder
cases run again with SEE enabled. The native-CPU exchange/search/UCI checks also
passed. NNUE's 537-position incremental checks passed in all three full suites;
position and NNUE sources are unchanged, and the full separate SF19 stage oracle
was not rerun for this ordering-only change.

Tool checks passed: 20 isolated search-mode profiler tests, 15 clock-profiler
tests, 17 paired-statistics tests, 17 match-runner tests, and 11 equal-work
benchmark tests. The new profiler checks both modes, required ordering records,
counter consistency, isolation from LMR, and partial failures.

Default ordering matched all 24 frozen-parent signatures. The 48 depth-5
searches retained all final moves/scores/PVs; 24 node-limited searches respected
the exact 200,000-node cap and independently legal PVs. See
[capture ordering](MOVE_ORDERING.md) for work, timing, and acceptance limits.

The predeclared eight-game smoke completed 2W/4D/2L for SEE, with four
checkmates, three repetition draws, and one insufficient-material draw. There
were no protocol errors, time forfeits, truncations, or excluded pairs. These
four development pairs are not a strength or equivalence test. Independent replay
verified 703 legal plies (639 searched), clock records, options, hashes, and
terminations. The three repetition draws were valid next-move claims under the
runner's documented policy. The independent profile audit also checked all
120 depth-5 and 62 fixed-node common-depth score/PV comparisons; all matched.
Audit records and their digest are linked from the ordering experiment.

Linux ARM64, Linux x86-64, and Windows x86-64 builds compiled and linked with
the documented toolchains. File inspection confirmed their architectures; none
was executed. RISC-V64 and Windows ARM64 remain unavailable locally.
The frozen GUI, forecast, LMR, and ordering binaries, pinned network, and reserved
time-validation suite retain their recorded hashes. The local
`results/capture-ordering-20261014/validation.json` records successful commands,
source-snapshot agreement, binary hashes, and these validation limits.

The separate [LMR loss diagnosis](reports/2026-10-14-lmr-losses.md) replayed all
four losses at eight selected roots using the frozen LMR executable. All eight
best moves and 40 common-depth scores/PVs agreed between policies. This is
post-hoc, bounded diagnosis; it neither demonstrates an LMR-specific miss nor
establishes strength or safety of all reduced fail-lows.

## Phase 2D qualification tooling — October 15, 2026

Before the first real campaign, `make test-qualification` passed 21 launcher
checks and 14 independent-auditor checks. They cover immutable settings/assets,
no-search UCI preflight, day/night and daylight-saving boundaries, preserving the
original 07:00 cutoff across readiness, cancellation and child-process cleanup,
incomplete PGNs/journals, legal full-history replay including Black to move,
actual UCI options/clocks, late unplayed moves, pair identity, corrupted evidence,
output-overwrite rejection, and exact predeclared decision boundaries.
`make test-match` also passed all 17 statistics and 17 runner checks.
The real no-search preflight passed with both frozen engine roles: 32 distinct
legal roots, correct applied options and artifact digests, and zero `go` commands.
It recorded the M5 Pro's 18 logical CPUs and 64 GiB RAM, a daytime 50% budget,
one active search worker, and two resident engines estimated at 1.11 GiB total.
This is a worker/memory estimate, not an OS-enforced utilization cap.

These tooling checks are separate from the actual match result below. The
campaign changes no engine source or binary; prior correctness and platform results retain
only their stated scope. The [predeclared protocol](PHASE_2D.md) records the
frozen executable, network, held-out suite, settings, decision rule, and the
owner's one-run daytime exception. All 64 games and the independent evidence
audit were subsequently completed.

## Phase 2D first campaign — completed October 15, 2026

The [frozen time-policy screen](reports/2026-10-15-phase2d-time-policy.md) completed
all 64 games / 32 color-reversed pairs in 2h54m on the M5 Pro. Its independent
audit passed: 7,088 legal plies, 6,240 charged search events, exact game/clock/option
agreement, unchanged pinned assets and tool sources, and zero exclusions,
forfeits, protocol failures, or truncations. Terminations: 21 checkmates,
38 threefold-repetition claims, and 5 insufficient-material draws.

Forecast scored 14W/43D/7L (35.5/64, 55.47%). The conditional two-sided 95%
Hoeffding pair-score interval was 31.46–79.48%; the predeclared decision is
**inconclusive**. No default changes, strength-gain claim, or equivalence claim
follow. Raw evidence and audit hashes are recorded in the linked report. The
completed one-run daytime exception does not authorize another long campaign.

## Phase 2D LMR preparation — October 15, 2026

Before starting the new fixed screen, `make test-qualification test-match`
passed **100 checks**: 21 historical launcher, 14 historical audit, 13 LMR
launcher, 18 LMR audit, 17 statistics, and 17 runner checks. The shared lifecycle
preserves the original time-policy CLI and cutoff behavior. New tests require
the exact LMR toggle, classic timing, 64 distinct roots, no later capture-ordering
option, both 64-pair decision boundaries, and independent rejection of altered
options, missing/extra evidence, wrong protocols, and corrupted game records.
Synthetic replay covers all 128 games without playing the held-out openings.

The actual no-search LMR preflight passed for both frozen engine roles, with
the intended applied options and **zero position/go commands**. The suite has
64 unique legal nonterminal roots, 992 history plies, and no final-root overlap
with all 56 earlier development/general/time validation roots. Its SHA-256 is
`1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7`.
Composition and independent replay used the pinned referee only; no evaluation
or outcome filtering. Source review and whitespace validation passed.

The completed time-policy campaign was re-audited using the generalized audit
code: zero errors and exactly matching original statistics/decision. Subsequent
live-source differences are reported separately, not confused with in-run drift.
Local evidence: `results/phase2d-lmr-preflight-20261015.json`,
`results/openings-lmr-validation-20261015/validation.json`, and
`results/phase2d-time-policy-20261015/audit-shared-protocol-20261015.json`.

These are tooling and preparation checks, not LMR strength results. The
actual games required by the [predeclared protocol](PHASE_2D_LMR.md) completed
separately below. No engine implementation, default, GUI bundle, or frozen
network/binary changed.

## Phase 2D LMR completion — October 16, 2026

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) completed all
128 games / 64 color-reversed pairs at 60+0.6 on the M5 Pro, from October 15
23:00 to October 16 05:41 Helsinki. It used the ordinary nighttime resource
budget, one active search worker, and no daytime override. Both sides used
the frozen LMR executable, classic timing, one thread, 64 MiB hash, and the
pinned network; only the LMR option differed.

The independent data-only audit passed with zero errors: 17,175 legal plies
(including opening histories), 15,191 charged search events, exact game/clock/
option agreement, and unchanged pinned assets and tool/protocol sources during
play. There were no exclusions, forfeits, protocol failures, unexpected stderr,
or truncations. Terminations were 46 checkmates, 71 threefold draws,
10 insufficient-material draws, and one rule-50 draw. A separate independent
review replayed the evidence and confirmed the statistics and decision.

LMR on scored **35W/82D/11L (76/128 points, 59.375%)**. The conditional two-sided
95% Hoeffding pair-score interval was **42.398731053%–76.351268947%**. The
predeclared decision is **inconclusive**; LMR remains off and no strength gain
or equivalence is established. The report records sampling limitations, raw
evidence hashes, and reproduction instructions. The original audit and frozen
protocol remain intact; later documentation edits are separate live-source
differences. All frozen executables, the network, and GUI `0.1-dev-4b8b35d`
were preserved. No engine rebuild or additional GUI validation was needed for
this tooling/evidence checkpoint. All campaign processes have exited.

A post-documentation re-audit also passed with identical game/statistical
evidence. Its only differences from the original audit are the audit timestamp
and the two expected live status-document changes (`SELECTIVE_SEARCH.md` and
`PHASE_2D_LMR.md`). Local record:
`results/phase2d-lmr-20261015/audit-after-documentation.json`.

## Phase 3A performance baseline — October 16, 2026

The [measurement checkpoint](reports/2026-10-16-phase3a-baseline.md) completed
on the M5 Pro under the normal 50% daytime budget. Engine source is unchanged
from `9daaade`; the separate release build is byte-identical to the frozen
capture-ordering executable. Position/perft, exchange, NNUE (537 incremental
positions), search, policy/time, UCI, and resource checks passed. An initial
PATH smoke in the custom nested build directory failed to find its default
network; an adjacent symlink to the pinned network fixed the bundle setup,
and `test-core` then passed. Both logs are retained; no engine fix was required.

All 11 comparison-tool checks and 16 new CPU-recorder mock tests passed. The
recorder tests fixed UCI settings, legality, sampling-window bounds, partial
evidence, failures/cleanup, resource changes, and artifact drift. Its first real
attempt was denied process inspection by the sandbox; the approved retry used
a new output path and completed. No failed record was discarded.

All **192 same-binary searches** (12 roots, depth 5, seven measured repetitions
plus warmups) matched exactly. All **48 optimized-symbol/release searches**
also matched. Independent replay verified every iteration's PV, bestmove, and
ponder. Median same-binary time ratio was 0.998546, paired MAD 0.008123; these
describe repeatability, not a speedup or confidence interval.

The separate 120-second CPU sample verified target identity, 1 ms requested
interval, 12 warmups, and all **24 sampled searches** within its conservative
window. Their signatures and moves also matched the release baseline. Two
independent call-tree aggregations agreed: 7,413 search observations, of which
6,304 were in NNUE, including 4,351 in update and 1,935 in inference. Nested
counts overlap. Main-thread idle observations were excluded; aggregate stacks
do not establish per-root sample counts or exact CPU-cycle percentages.

All frozen engine/network/build/benchmark artifacts matched after measurement;
the new Makefile test target and final docs were added afterward. Raw evidence,
failure records, and independent audits are in `results/phase3a-20261016/`.
GUI `0.1-dev-4b8b35d` remains intact. Scalar/sanitizer/full oracle suites were
not rerun for this measurement-only checkpoint. The subsequent
[NNUE update experiment](PHASE_3B.md) reran them as recorded below.

## Phase 3B batched NNUE updates — October 16, 2026

The [isolated batch update](reports/2026-10-16-phase3b-nnue-batching.md) passed
native, forced-scalar, and ASan/UBSan engine suites. These include perft/rule/state,
UCI, search, exchange, timing/search-policy checks, and the 537-position real
network incremental/full-refresh suite. The new test-only arithmetic oracle
adds 360 transitions per build, checking all hidden/PSQT lanes with signed
int8/int16 columns, duplicates, extreme modular arithmetic, empty/partial/full
batches, large changes, and reversal. Its independent multiplicity map and
column-at-a-time arithmetic do not share the production batching kernel.

A fresh external SF19 oracle run passed all **2,057 positions** for native and
scalar, with unchanged corpus, feature/accumulator/layer-stage, and raw/wrapped
output hashes. It used a copied isolated reference checkout and new output
directory `build/nnue-oracle-phase3b-20261016/`; previous oracle evidence survives.

Before timing, all 96 depth-5/depth-6 searches matched exact per-iteration
depth/seldepth/nodes/score/PV, bestmove, and ponder, with independent legal replay.
The three subsequent timing runs also matched. The independent final audit
checked **576 searches**, 3,024 PV lines / 10,572 legal PV plies, and all bestmoves
and ponders, plus identities, raw-reply signatures, runner/asset hashes, histories,
counts, options evidence, independently recomputed timings, and acceptance gates.
Negative checks confirmed rejection of tampered ratio metadata and an illegal PV.

Median baseline/candidate elapsed ratios were **1.078081, 1.079836, 1.083612**;
all exceeded 1.03 and all 24 pooled root/depth medians exceeded 0.98. There were
no observed individual measured slowdowns. The declared result is **retain**
for sampled opening-search performance, without a statistical confidence or Elo
claim. Settings, thresholds, implementation, and all runs were preserved.

Raw records and test logs: `results/phase3b-20261016/`. Candidate release SHA-256:
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.
The ordinary native executable was rebuilt after measurement and is byte-identical.
All prior frozen candidates, GUI `0.1-dev-4b8b35d`, and the pinned network remain
intact. One active worker/two resident engines were used during comparisons,
within the ordinary daytime budget. All jobs ended; no match or schedule exists.
Broader game phases, clock-managed strength, scalar throughput, and foreign
runtime execution were not established by these measurements.

## Phase 3C game-phase validation — October 16, 2026

The [completed comparison](reports/2026-10-16-phase3c-gamephases.md) used 12
original composed FENs, selected before engine evaluation/timing: six middlegames
at depth 6 and six endgames at depth 8, with balanced turns and all eight NNUE
material buckets. The pinned referee confirmed validity, nonterminal/non-drawn
roots, uniqueness, and no overlap with 120 earlier opening roots. Historical
reachability and earlier repetition history are not claimed.

All six frozen comparisons completed in 844.997 seconds with one active worker
under the normal daytime budget. All **432 searches** matched exact per-depth
results; independent raw-reply replay verified **3,024 PVs / 14,904 plies** and
432 bestmoves/ponders. There were no timeouts, exclusions, operational failures,
or asset/source changes. The 11 comparison-tool checks, synthetic descendant
cleanup check, five audit corruption checks, and eight classification/boundary
checks passed. Raw evidence is `results/phase3c-20261016/`.

Both same-binary controls passed repeatability gates. Middlegame ratios
**1.087243 / 1.088055** passed the positive, duration, and pooled-root guards.
The endgame ratios/guards were favorable too, but `gamephases-eg-05` took
30–32 ms, below the predeclared 50 ms floor in all six role/run medians. Endgame
and combined qualification are therefore **inconclusive**. No candidate
slowdown appeared among 120 measured candidate pairs, but favorable ratios
cannot override the duration gate. No roots or thresholds were changed.

Engine code, normal/frozen binaries, defaults, and GUI `0.1-dev-4b8b35d` are
unchanged. Native/scalar/sanitizer/full NNUE oracle checks retain their Phase 3B
scope; they were not rerun for this validation-only phase. No strength gain,
release, new platform execution, or universally faster endgame play is claimed.
The subsequent baseline-only characterization is recorded below; Phase 3C's
decision remains unchanged.

## Phase 3D workload characterization — October 17, 2026

The [completed diagnostic](reports/2026-10-17-phase3d-workload.md) ran the same
frozen Phase 3A baseline in both roles at depths 8–12 for `gamephases-eg-05`.
All **40 searches** matched exactly within depth and all common iteration
prefixes matched across depths. Independent replay verified **400 PV lines /
2,296 plies**, 40 bestmoves, and 40 ponders. No engine code or binary changed.

Depth 12 is the shallowest tested level meeting the predeclared 200 ms minimum,
5-second maximum, ratio [0.97, 1.03], and MAD ≤0.03 proposal rule. Role medians
were 329.881/322.562 ms; ratio 0.999090 and MAD 0.028507. Depth 10's ratio/MAD
failures are retained. This is a three-pair engineering heuristic with a
near-limit MAD, not proof of durable repeatability or candidate improvement.

The 11 comparison-tool tests, two launcher mock cases, syntax check, 35 frozen
input integrity checks, and 20 auditor corruption/selection/prefix checks passed.
Cleanup functions were AST-checked against the previously tested Phase 3C
launcher; its real descendant test was not rerun. The first auditor attempt
failed on an auditor-only API typo before reading search data. Its `audit.json`
is preserved; the repaired auditor passed in **`audit-final.json`** without raw
measurement changes. Native/scalar/sanitizer/full NNUE oracle checks retain
their Phase 3B scope and were not rerun.

The campaign completed in 7.441256 seconds with one active worker under the
ordinary daytime budget. All jobs ended, no schedule is active, and preserved
GUI `0.1-dev-4b8b35d` is unchanged. Raw evidence is
`results/phase3d-20261017/`. Phase 3E needs a separately frozen complete endgame
comparison with fresh controls. Phase 3C remains inconclusive for endgames;
no release, Elo gain, or new platform execution is claimed.

## Phase 3E endgame requalification — October 17, 2026

The [new complete comparison](reports/2026-10-17-phase3e-endgames.md) tested all
six original endgames with the Phase 3D pawn workload at depth 12 and other roots
at depth 8. Fresh controls and two candidate rounds each used five measured
pairs per root plus warmups; no older timing data was pooled. All **216 searches**
matched exact per-depth signatures across roles/repetitions/rounds. Independent
replay checked **1,872 PV lines / 10,512 plies**, 216 bestmoves, and 216 ponders.

The complete control passed median 0.998927 and MAD 0.003985 plus all root
guards. Both complete candidate rounds passed the positive gate at **1.089113 /
1.084243**. All 36 role/root/round medians exceeded 50 ms (minimum 298.212 ms),
and all pooled ten-pair root medians exceeded 0.98 (minimum 1.049976). The result
is **qualified on this revised composed endgame sample**. Two individual
candidate slowdowns, control outliers, and absolute-time drift remain included.
The 16/14 role-order imbalance is documented. No confidence or Elo claim follows.

The 11 comparison-tool tests, three launcher mock cases, syntax checks, suite
referee checks, 29 independent auditor checks, and 37 frozen-input checks passed.
The auditor also checked settings/identity, raw summaries, canonical root mapping,
complete-round aggregation, expected counts/order, resources, and campaign
lifecycle; a separate reviewer independently replayed all searches and recomputed
gates. Cleanup functions match the previously tested Phase 3C implementation;
the real descendant cleanup test was not rerun. Native/scalar/sanitizer/full
NNUE oracle suites retain their unchanged Phase 3B scope and were not rerun.

The campaign completed in 353.663077 seconds within its 600-second cap under
the ordinary daytime budget, with one active worker and two resident engines.
All jobs ended; no schedule is active. Raw evidence is
`results/phase3e-20261017/`. Engine code, defaults, normal build, and GUI
`0.1-dev-4b8b35d` are unchanged. Phase 3C's original endgame/combined decisions
remain inconclusive; this result establishes no new release or platform runtime.

## Phase 3F dense inference — October 17, 2026

The [fixed protocol](PHASE_3F.md) and [full report](reports/2026-10-17-phase3f-dense.md)
record the retained four-output NEON kernel. Native, forced-scalar and ASan/UBSan
full suites passed, each including **1,515 independent dense cases / 84,126 output
comparisons**, **360 update transitions**, and **537 incremental positions**.
The fresh isolated SF19 oracle matched all **2,057 positions**, every integer
stage and raw/wrapped score, retaining the earlier corpus and output digests.
Scalar inference and the singleton-output path remain unchanged.

The 96 release/symbol searches and 72 profile searches passed independent exact
and legal checks. Two independent raw-stack aggregations agreed. The fixed
nighttime performance campaign completed all **576 searches** in 746.807169
seconds with one active worker: **3,552 legal PV lines / 15,840 plies**, plus
576 bestmoves/ponders. Every root signature matched across roles/repetitions.
All 55 frozen inputs, settings, orders, resources, and lifecycle checks passed.
The control, duration, pooled-root, and both-round improvement gates passed in
all three phases. Opening ratios were **1.196321/1.195963**, middlegame
**1.196515/1.213653**, endgame **1.324133/1.394803**, versus retained Phase 3B.

All four individual slowdowns, substantial absolute-time drift, and candidate
endgame dispersion remain included. These observations limit generalization;
no Elo, scalar speed, foreign-platform execution, or release claim follows.
The recorder's 21 mock tests, launcher's 23 cases, and auditor's 52 checks passed.
No failed audit attempt or repeated measurement campaign occurred. Original GUI
`0.1-dev-4b8b35d` and all old frozen binaries remain intact. Normal native output
was promoted after the successful audit and is byte-identical to the qualified
candidate; `final-integrity.json` explicitly records that one intentional change.
The optional new GUI snapshot passed a CLI smoke, not a Cute Chess GUI test.

## Phase 3G qualification preparation — October 18, 2026

The [fixed protocol](PHASE_3G.md) and original opening assets were committed as
`c177804` before any games. The legal-move-only generator reproduces all four
shards and metadata byte-for-byte: **256 distinct full histories**, 64 per
shard, 128 roots per side to move, disjoint from all 132 earlier opening and
performance roots. No continuation was rejected during generation; no engine
evaluation or outcome selected these unevaluated positions.
The tested supervisor, auditor, and lifecycle fixes are recorded in `ff478a7`.

The latest relevant suites pass **172 tests**: 15 opening-generation tests,
24 supervisor/lifecycle tests, 33 aggregate/raw-auditor tests, and 100 historical
match/statistics/qualification tests. Reproduce with
`make PYTHON=python3 test-match test-qualification`. The combined run included
23 launcher cases; the final additional shutdown-cancellation case and all
24 launcher cases passed after that launcher-only fix.

Lifecycle checks use fake UCI processes and synthetic tasks. They verify four
concurrent workers, aggregate CPU/memory rejection and owner-policy changes,
the common cutoff and DST handling, missed monitoring, input drift, invalid
games/stderr, valid scored clock forfeits, and cancellation during shutdown.
Eight real **fake-UCI** subprocesses were checked for disappearance after
repeated SIGINT/SIGTERM, including unresponsive quit. Cancellation now finishes
both engines' cleanup and evidence persistence before propagating; a stopped
worker cannot silently admit the next game. Whole-supervisor finalization is
protected against a first signal arriving during an existing failure cleanup.

The auditor's 28 aggregate tests use synthetic 512-record campaigns with mocked
child audit results. Five separate tests exercise the actual inherited raw
PGN/UCI verifier on 128-game synthetic fixtures, including transcript, PGN,
clock, stderr, and partial-run corruption. Threshold subcases cover 299/299.5
and 212.5/213 points. Master tests cover shard identity, full histories/colors,
all 512 resource admissions, periodic gaps, preflight searches, source/pin
drift, incomplete evidence, and refusal to overwrite. Independent code review
found and resolved lifecycle and resource-timestamp issues before completion.

A real **readiness-only** check passed on the pinned Phase 3F executable for
both LMR roles, with zero `position` or `go` commands. The record is
`results/phase3g-preparation-20261018/preflight.json`; its two UCI transcripts
also passed the independent auditor's preflight checks. All four child profiles
match the launcher/auditor pins and current source snapshots. Aggregate engine
memory reservation is about **4.44 GiB**, an estimate rather than an OS limit.

During v1 preparation, no actual Phase 3G strength game, reserved-position search,
performance run, or C++ rebuild was performed. Both GUI snapshots and the normal
executable remained unchanged. The real campaign had **not yet run**;
synthetic lifecycle tests and readiness do not establish its completion,
playing strength, or foreign-platform execution. LMR remains off, and no
automatic schedule or new release exists.

## Phase 3G daytime amendment — October 18, 2026

Before the first game, the owner explicitly authorized a daytime exception and
requested that its protocol change be prepared and validated before launch.
Protocol `phase3g-lmr-512-v2` adds `--allow-daytime`, limited to October 18
07:00–23:00 Helsinki and recorded as `owner-20261018-phase3g`. The normal
50% daytime / 80% nighttime resource limits and original next-07:00 cutoff
remain; the daytime launch has a longer possible wall-time allowance. The
256 pairs, 512 games, four active workers, engine/network, settings, openings,
and decision rules are unchanged. No engine code or README text changed.

`make PYTHON=python3 test-match test-qualification` passed **189 tests**:
34 match/statistics, 15 opening-generation, 29 coordinated-launcher, 45 aggregate
and raw-auditor, and 66 historical qualification checks. New cases cover exact
date/time boundaries, missing or forged authorization, strict permission flags,
master/child agreement, the unchanged daytime allowance, readiness crossing
23:00, cutoff expiry before startup, and ordinary DST transitions. Full fake
process cancellation and existing raw-evidence corruption checks still pass.
Expected command-line rejection messages are negative test cases, not failed
suites. A separate read-only review found no blocking issue and independently
checked ten window cases plus naive-clock rejection.

Fresh real two-role readiness passed with zero position/search commands and
independent transcript audit. Evidence is
`results/phase3g-preparation-20261018/daytime-v2-preflight.json`; original v1
readiness files are preserved. The v2 record matches all current frozen sources
and assets; its fixed configuration and engine/network/opening artifacts are
identical to v1. Its authorization preview is not a game-start record. The
amendment is committed locally before the one authorized campaign starts in
`results/phase3g-lmr-20261018-daytime/`. Actual outcome and strength qualification
remain pending; no restart, schedule, or default promotion is implied.

The tested amendment was committed as **`fce2539`**. The first real attempt
started **October 18 at 08:54:00.810565 Helsinki**, with all four shards running
and initial admission/resource observations within the normal 50% daytime
budget. The shared cutoff is **October 19 at 07:00 Helsinki**. The campaign
manifest and append-only resource journal record the actual launch; readiness
alone did not establish it. The completed outcome is recorded below.

## Phase 3G completed screen — October 18, 2026

The one authorized attempt finished **15:12:09.041757 Helsinki**, after
6 h 18 min 8.231192 s. All four shards completed 64 pairs / 128 games each;
all **256 pairs / 512 games** remain included. The unchanged independent
`tools/audit_phase3g.py` passed on its first full-campaign audit with zero
errors and no live-source differences. It replayed **60,323 legal plies** and
verified **50,352 charged search events**, full PGNs/UCI histories, actual
options, terminations, paired colors, aggregate resource records, the dated
authorization/cutoff, and unchanged before/after source and asset hashes.

LMR-on scored **225W/155D/132L, 302.5/512 points (59.08%)**. The conditional
95% pair-score interval is **50.5939–67.5702%**. Six candidate clock forfeits
and seven baseline clock forfeits are valid scored outcomes. The candidate
forfeits trigger the first frozen rule: **operational regression; no default
change**, even though 302.5 exceeds the numerical 299.5-point boundary.
No games were replaced, excluded, replayed, or appended. Both roles having
clock losses does not establish their cause or make the candidate acceptable.

See [the result report](reports/2026-10-18-phase3g-lmr.md) for evidence hashes,
per-shard results, limitations, and audit reproduction. Raw evidence and the
original `audit.json` remain in `results/phase3g-lmr-20261018-daytime/`.
No C++ changes, rebuild, new engine tests, or further games were needed for
this data-only audit and documentation checkpoint. Phase 3H will investigate
clock reliability before any fresh confirmation. Both GUI snapshots and the
README remain unchanged.

## Phase 3H command-time accounting — October 18, 2026

A cold-network `go movetime 1` reproduced uncharged preparation in both LMR
modes: 68.6–73.5 ms externally, about 1 ms internally, and 217/219 searched nodes.
The repaired UCI path carries receipt time into search; the expired request now
performs zero tree work while reporting the preparation time. The API also has
deterministic already-expired positive-clock tests for both colors/modes, explicit
limits, pondering, infinite/no-clock search, future origins, and extreme-past
arithmetic. A review-found extreme-past overflow risk was fixed before final
validation; final native, scalar, and Address/UndefinedBehaviorSanitizer suites
passed. No NNUE math changed or new full SF19 oracle run is claimed.

The diagnostic tool's seven focused tests pass. It independently checks legal
PV/bestmove, diagnostic accounting, clock bounds, restricted commands, no
overwrite/resume, and failure records. All **52** prescribed probes completed:
13 full histories × both LMR modes × frozen/repaired binaries, fresh tables and
readiness each time. Every move was legal and received before its original
remaining clock. Both executables had at most 0.003 ms reported hard-deadline
overshoot in this sample. This fails to reproduce the original losses and is
not a match, strength result, or proof that the repair solves scheduler stalls.

The final fixed-depth comparison matched all 48 search signatures (12 development
roots, one warmup and one measured search per executable at depth 4). Timing is
not used as a performance claim. All historical artifacts and both GUI bundles
were preserved. See [the result report](reports/2026-10-18-phase3h-clocks.md) for
source provenance, limited causal findings, artificial suspension control,
commands, and evidence hashes. Phase 3G's operational decision remains unchanged.

## Phase 3I callback receipt — October 18, 2026

The match runner previously timestamped each line after logging earlier lines
in the same callback. The deterministic pre-fix reproduction charged 250 ms to
a reply already received at 50 ms, falsely exceeding a 100 ms clock. The retained
fix timestamps complete batches before logging/dispatch, preserves the pinned
parser, and avoids reentrant-command timestamp inversion. Eight focused tests
cover slow logging, split/UTF-8/CRLF input, errors, cleanup, and genuinely late
callbacks. `make test-match test-qualification test-phase3g test-clock-probes`
passed all 212 checks, including eight tests for the new receipt-control tool.

All 12 prescribed live controls completed on the unchanged Phase 3H executable.
Four normal requests were on time; four consumer-sleep requests reached the
reader on time but were consumed late; four deliberate engine pauses produced
late internal and external observations. Independent replay validated 12 bestmoves,
12 ponders, and 76 PV lines / 320 plies; input hashes and resource policy matched.
These are controlled mechanisms, not a clean operational match or proof of
historical causation. The reader is a thread in the same process, and timestamps
do not identify kernel arrival. The [report](reports/2026-10-18-phase3i-receipt.md)
records exact timings, source pins, limitations, and preserved raw evidence.

No engine source/default changed or engine rebuild occurred, so no new full
native/scalar/sanitizer or NNUE oracle run is claimed. Both stable GUI bundles,
the normal release binary, and the README introduction are unchanged. Phase 3G
retains every original flagfall and its operational-regression decision.

## Phase 3J persistence isolation — October 18, 2026

All 230 match/qualification/audit/clock-probe checks passed in 11 invocations,
including 15 new bounded-writer tests and three resource-supervisor tests.
Coverage includes slow writes across separate callbacks, ordering, byte/record
overflow including in-flight writes, open/write/flush failures, bounded writer
timeout, cancellation, journal ownership, and incomplete evidence publication.

The predeclared four-game, two-shard canary injected 100 ms into every protocol
write and finished in 220.986 seconds. Its independent evidence audit passed:
398 on-time search replies, 430 legal plies including openings, 2,516 legal PV
lines / 7,174 PV plies, 396 legal ponders, consistent PGN/journal clocks, and
unchanged source/asset pins. There were 3,878 measured delayed writes; 396
bestmoves arrived during the other shard's write delay. No protocol, storage,
queue, or clock failure was recorded.

Full operational acceptance **did not pass** because one game hit the declared
128-ply limit. The other games ended in two checkmates and one repetition draw.
The capped game is retained as `*`, without extension or replacement. This
finite mechanism check establishes no strength or general reliability claim.
See the [report](reports/2026-10-18-phase3j-persistence-puzzles.md), frozen plan,
and raw `results/phase3j-20261018/canary/` plus independent audit. The next
operational screen must be separately declared; old campaigns remain unchanged.

## Owner-run GUI feedback — October 18, 2026

The owner reports two draws against Gargantua 2.1 with no engine errors or
disconnections. Intended snapshot: `0.1-dev-phase3f-20261017`; actual executable
identity and UCI options were not captured. The [review](reports/2026-10-18-cutechess.md)
preserves the supplied partial 180+2 PGN byte for byte. `chess==1.11.2` accepted
all 121 plies / 122 positions, and the preserved Phase 3F executable's legal
root sets and all depth-2 divide branches matched at every saved position.

The PGN ends unfinished at 61.Nc3. The owner clarified that they manually
adjudicated game 1 drawn, judging it would finish drawn and wanting to save
the PGN before the GUI advanced. This identifies the summary's user-adjudicated
draw; a played-out or forced draw was not independently verified. Game 2's
ending cannot be replayed without its missing PGN. Rounded thinking times support
early clock depletion, not a proven deadline overrun. No NNUE oracle rerun,
timed search, rebuild, strength match, or new schedule was performed. The review's
local script initially failed on an integrity-record field name after move
checks; its corrected rerun passed. Both GUI binaries and all Phase 3G source
and artifact pins remain unchanged. This is exploratory feedback, not strength
qualification; Phase 3G had not started at the time of that feedback review.

## Release gates

1. **Position correctness:** standard perft vectors and divide diagnostics;
   castling transit attacks, pins, en passant exposing a king, all promotions,
   mate/stalemate, legal-move membership, and complete make/unmake restoration.
2. **Position and input integrity:** FEN rejection without partial state changes,
   deterministic hashes, relevant en-passant repetition keys, reversible clocks,
   promotion/capture handling, and sanitizer-clean tests where available.
3. **NNUE interoperability:** verified network digest and bounded file parser;
   exact active feature indices, integer accumulators, PSQT, and raw outputs
   against the pinned independent test oracle. Incremental evaluation must equal
   refresh across legal sequences and reversals, including every special move.
   Every enabled optimized kernel must equal scalar output.
4. **UCI lifecycle:** handshake, readiness during search, legal best moves, stop
   responsiveness, repeated go/stop, new games, position replacement, hash/network
   changes only after search joins, pondering/infinite result timing, EOF/quit.
5. **Search:** mate distance and score bounds, check evasions at quiescence,
   repetition and rule-50 precedence, terminal positions, node/depth/time limits,
   and deterministic bounded searches. No neural-network-free fallback disguised
   as NNUE strength.
6. **Platforms:** record the exact compiler, standard library, flags, target,
   network digest, and native/VM/emulated/build-only validation for each target.
7. **Performance and strength:** report repeatable benchmarks and local matches.
   A functional 0.1 need not beat Stockfish; no Elo claim without match evidence.

## Annotated puzzle input — October 18, 2026

The exact owner example rejected by `65a5313` with `expected moves` now loads.
Native, scalar, and ASan/UBSan `make -j2 test` passed, including strict board and
counter validation, transactional rejection, ordinary UCI histories, and exact
search signatures with correct, wrong, or absent answer metadata. All 39 supplied
workbook positions (four with omitted counters) matched independent
`chess==1.11.2` legal depth-2 divides and three-way depth-2 search signatures:
frozen Phase 3H plain FEN, new plain FEN, and new annotated FEN.

One requested-style `go movetime 60000` example completed in 59.983 seconds,
returning `f5f6` (Qxf6+) at completed depth 8 / centipawn score 1206. It did not
report mate in seven. Raw source digest, per-position checks, before/after
transcripts, and suite logs are under `results/phase3j-20261018/`.
New native executable SHA-256:
`fa329663e4c9f8e07ecb495f1d7f069ffb4d6fdd4f320365eaf7fd25d5ca9637`.
This checks compatibility and finite search parity, not puzzle answer accuracy,
an engine strength gain, or cross-platform execution.

## Strength measurement

Freeze the two binary hashes, code commits, network digests, clock settings,
thread count, hash size, affinity policy if used, and opening suite digest before
a match. Match resources between engines. Disable ponder and books unless the
experiment explicitly gives both the same access. Play each opening with colors
reversed. Do not tune against the held-out validation set.

Save full PGNs, errors, forfeits, time losses, and machine metadata. Use a
predeclared sample size or a justified sequential test; do not repeatedly peek
at a conventional confidence interval and stop as soon as it turns favorable.
Paired openings produce dependent games: estimate uncertainty at the pair level,
not by pretending each game is independent. Report W/D/L and score with an Elo
difference and uncertainty only when the statistical assumptions are satisfied.

Initial focus is blitz. Exact time controls, opening-suite selection, and sample
sizes are experiment configuration, not invented product achievements. A
statistically positive difference does not automatically mean 'decisively
stronger'; report the measured margin and uncertainty. Absolute 4000 Elo requires
a named calibrated rating pool. NPS, search depth, and solved tactics alone do not
establish playing strength.

## Experiment records

Record hypothesis, parent commit, changed parameter/code, exact command, resource
policy, input hashes, raw results, interpretation, and keep/revert decision.
Keep large generated results, networks, and external reference builds outside
the source tree or ignored. Retain concise result summaries with reproducible
commands when publishing a claim. Test-only Stockfish code must never become an
undeclared dependency of the shipped engine.

## Phase 3K console diagnostics — October 18, 2026

Native macOS ARM64 `make -j2 test`, `make SIMD=scalar -j2 test`, and
`make MODE=sanitize -j2 test` passed. Expanded UCI coverage exercises board aliases,
view-only rotation, FEN/key/evaluation/search preservation, missing networks,
in-check labels, input rejection, start/Kiwipete/terminal perft counts, readiness,
stop, position replacement, and quit during deep diagnostic counting. Legacy
perft/divide and raw evaluation records remain compatible.

An independent `chess==1.11.2` replay checked 93 positions (29 special/start
fixtures and 64 reachable positions, seed 2026101813), all 1,945 legal roots and
51,736 depth-2 nodes, with both display orientations and complete position state.
Thirty-six bounded searches matched every completed depth/node/score/PV, bestmove,
and raw evaluation across the frozen previous binary, new binary, and new binary
after display/perft commands, with LMR off and on. No speed or strength claim
follows. Native executable SHA-256:
`5063b483406d5b8061db330b070962e1665c196870c9a7968a18752432f3894f`.
Raw checks and suite logs are in `results/phase3k-20261018/`. A separate startpos
`go perft 5` example returned 4,865,609 nodes with all 20 root rows.

The predeclared [Phase 3K](PHASE_3K.md) operational screen passed its first
independent audit: four complete games in 17.135 seconds, three repetition draws
and one insufficient-material draw; no clock/protocol/storage/stderr/truncation
failures. Verified 386 on-time replies, 418 legal game plies including openings,
1,517 PV lines / 4,723 PV plies, 385 legal suggested ponders, and minimum clock
slack 19.225 ms. Four ordinary resource admissions covered two active workers /
four resident engines; all eight engine PIDs across the games were closed.
Source/assets, clocks, PGNs, options, and summaries matched. The independent
checker accepted a synthetic fixture and rejected six deliberate corruptions.
See the [report](reports/2026-10-18-phase3k-console-operations.md) for pins and
scope. This is a bounded operational pass, not a strength or general reliability
claim. Historical results/defaults are unchanged; Phase 3L preparation remains next.

## Phase 3L console format and mate reporting — October 18, 2026

At the owner's request, explicit board/evaluation/help/perft commands now print
plain text. Standard search and error output retains UCI formatting. The native
`make -j2 test` suite passed. UCI regressions verify plain output and retained
board/state/cancellation behavior, ordinary centipawn search output, mate +1 and
mate -1 for both colors with exact legal PVs, and mate 0 at a checkmated root.
No search logic changed; the existing engine already supported mate scores.
The static `eval` command does not search for mate. Saved Phase 3K evidence and
its frozen binary remain unchanged.

Independent bounded checks compared 12 old/new depth-4 searches over three
already exposed roots with LMR off/on: every completed iteration's depth,
selective depth, nodes, score, PV, and best move matched. Four signed mate cases
were independently replayed to checkmate. Plain startpos `go perft 5` returned
4,865,609 nodes and all 20 root rows. Raw evidence is in
`results/phase3l-20261018/console-compatibility.json`; the full native test log
is adjacent. Scalar/sanitizer suites were not repeated for this formatting-only
change; their latest execution evidence remains in the Phase 3K report.

The fresh qualification preparation passed 23 generator/exclusion tests,
29 launcher tests, and 42 independent-auditor tests. These 94 checks use
synthetic evidence and fake engines, not qualification games. Reproduction and
explicit original-source verification passed for 256 distinct unsearched roots,
128 per side to move, with zero overlap against 851 cataloged roots from 39
sources. No generator rejection occurred. The catalog covers saved roots, not
every internal search node, and retains explicit missing-source limitations.

Serial readiness passed at 21:16 Helsinki, with both exact configurations,
frozen inputs, and aggregate resource reservation independently audited.
`readiness-audit.json` reports `checked: true`, no errors, and zero held-out
searches. The estimated future four-worker/eight-engine reservation is
4,762,970,592 bytes (about 4.44 GiB); readiness itself loads roles serially.
The launcher correctly reports that a long campaign cannot start at that hour.
No 512-game campaign or schedule was launched. See the
[preparation report](reports/2026-10-18-phase3l-preparation.md) and
[fixed protocol](PHASE_3L.md). This completes preparation only: strength results,
default promotion, release acceptance, and broader platform execution remain open.

## Phase 4A cache reporting and representation — October 18, 2026

Native `make -j2 test`, scalar `make SIMD=scalar -j2 test`, and ASan/UBSan
`make MODE=sanitize -j2 test` passed on macOS ARM64. New checks cover standard
hashfull presence/range, populated occupancy and generation/clear/resize behavior,
terminal reporting, diagnostic accounting and exact on/off search parity, and
packed entry fields/limits/generation wrap/alignment. Twenty optional cache
profiler checks passed; its Make target wiring was dry-run checked.

The parent/instrumented comparison matched all 24 searches. The one compact
layout candidate then matched all 72 profile searches / 36 pairs across declared
exposed roots, cold/warm state, and Hash 1/64: full per-iteration signatures,
occupancy, cache event counts, and independent legal move/PV checks. At Hash 64,
entry storage fell from 48 to 32 MiB with the same 2,097,152 entries. The fixed
36-search timing comparison passed all guards: root median paired ratios
1.010283/0.996622/0.996106, geometric mean 1.000982, all baseline root medians
above 0.1 seconds. Timing is effectively neutral; memory reduction is not Elo.

The final profiler additionally revalidated saved baseline output after review
fixed a capacity-assumption error and strengthened probe accounting. No engine
search result was replaced. Full details, versioned tool evidence, hashes,
scope limits, and the retain decision are in the
[report](reports/2026-10-18-phase4a-cache.md). No new GUI visual test, foreign
execution, full SF19 stage-oracle rerun, long campaign, or release is claimed.
Both GUI snapshots, frozen Phase 3L assets, and search defaults remain intact.

## Phase 4B parallel search — October 18, 2026

Native `make -j2 test` and `make test-smp`, scalar
`make -j2 SIMD=scalar test test-smp`, ASan/UBSan
`make -j2 MODE=sanitize test test-smp`, and ThreadSanitizer
`make -j2 MODE=thread-sanitize test-search test-smp` passed on macOS ARM64.
The optional UCI suite contains 43 bounded cases with an independent legal
referee, and passed under all four build configurations. Direct API checks cover
shared Hash storage, exact global node caps, exceptions/join/reuse, immediate
stop, clock/pondering, root restrictions, and repetition/mate/rule-50 boundaries.
ThreadSanitizer reported no race in the exercised schedules. Twenty-four
profiler tests passed, including input/accounting/failure-path checks.

All 24 parent/candidate one-worker searches matched completed-depth signatures
exactly. Their timing summary suggests a possible small one-worker cost, not a
speedup. The fixed scaling screen completed 72 searches: 18 warmups and 54
measured samples, using three exposed roots, one/two/four workers, 1,000 ms and
depth 6. An independent raw-evidence audit recomputed every ratio and replayed
2,608 legal PV/bestmove/ponder plies. Four workers achieved 3.2505× aggregate
throughput and 2.0933× faster depth-6 latency, with +1 depth in all nine timed
pairs. All current source/binary pins, old GUI bundles, frozen Phase 3L assets,
and the README introduction matched. Four active workers fit the daytime limit
of nine. No long match campaign or automatic schedule was started.

The [report](reports/2026-10-18-phase4b-smp.md) contains exact settings, hashes,
timing variability, reproduction commands, and scope limits. These checks do
not establish an Elo gain, every possible thread interleaving, 64-worker scaling,
foreign-platform execution, or a new GUI visual pass. Threads remains 1 by
default. Phase 4C Syzygy is next; release acceptance remains open.


## Phase 4C — optional Syzygy — October 18, 2026

The [checkpoint report](reports/2026-10-18-phase4c-syzygy.md) records the pinned
reader, separate external data, reproduced failures, checks, hashes, and limits.
Native/scalar/ASan+UBSan full suites and TSan search checks passed. In all four
build modes, the adapter matched 140 exact WDL oracle cases and passed DTZ
outcome/legal-move checks, 47 UCI cases, and six direct clock/stop/node scenarios
with both one and four workers. Fetcher tests (13), profiler tests (25), and
byte-for-byte corpus reproduction passed. The empty-path default preserved all
24 parent/candidate benchmark search signatures; timing was noisy and neutral.

This is finite three-/four-piece evidence, not exact raw DTZ-distance parity,
a seven-piece execution claim, foreign-platform validation, a GUI visual pass,
or an Elo/release acceptance result. Root and interior probes are intentionally
conservative around repetition, halfmove clocks, and PVs. No strength match was
started; existing defaults and frozen campaigns remain unchanged.

## Phase 4D.1 — optional countermove ordering — October 18, 2026

The [report](reports/2026-10-18-phase4d-countermove.md) records the fixed protocol,
artifact identities and bounded decision. Native/scalar/ASan+UBSan suites and
TSan search checks passed; all four builds passed 57 new referee-backed UCI
cases, with direct API tests for counter state, policy switching, special moves,
rules, diagnostics, interruption and SMP. The profiler passed 24 checks. Native
Syzygy regressions remained green. All 180 cold/warm parent/off comparisons
were exact and all 360 on/off profile searches replayed legally.

No broad efficiency improvement was established. The candidate stays off and
further tuning/strength qualification is parked. All final depth-6 scores and
moves matched; intermediate warm score differences are documented rather than
treated as proof of a defect or hidden. No default promotion, Elo claim,
foreign execution, fresh GUI check, or release acceptance follows. Existing
GUI bundles, README introduction, and frozen Phase 3L assets were preserved.
