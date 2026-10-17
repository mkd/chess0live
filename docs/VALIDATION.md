# Validation and experiment protocol

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
