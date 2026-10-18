# Developer and agent handover

## Accepted direction

Read [requirements](REQUIREMENTS.md) first. The user completed the interview:
original engine, strength over elegance, GPL-3.0-or-later, pinned SF19 network,
no own initial network training, desktop/laptop focus, M5 Pro primary, local-only
compute, and tested commits directly to main. The owner now handles GitHub pushes
manually; do not retry authentication or publishing from an agent session.

Preserve the owner's README introduction before `## Build and run` exactly.
Limit future README edits to practical build, run, test, configuration, extension,
and contribution instructions. Keep phase progress, match reports, and competitive
ambitions in the roadmap and other project docs.

No unresolved product decision blocks the baseline. Nighttime is 23:00–07:00
Europe/Helsinki at 80%; daytime 50%; the owner can override the budget. Blitz is
the first match-testing focus. Do not reuse any of the owner's earlier engines.

## Development sequence

1. Establish legal bitboard moves and reversible state; pass perft and edge cases.
2. Independently implement the pinned SF19 file format, all feature families,
   scalar integer inference, and incremental state. Prove oracle parity.
3. Integrate bounded search and asynchronous UCI; pass lifecycle and rule tests.
4. Record benchmarks and build/platform evidence. Release 0.1 only when all its
   claimed capabilities have evidence; never claim the long-term strength goal.
5. Optimize ARM64, extend portable builds, measure search improvements, and add
   parallelism with correctness and match evidence. Training integration follows.

## Current checkpoint

The first three steps are implemented as an unreleased `0.1-dev` baseline.
Normal and sanitizer suites passed natively on macOS ARM64. SF19 integer parity
has a separate reproducible oracle harness. ARM64 NEON is implemented; the
reference remains selectable with `SIMD=scalar`. Three other platform binaries
cross-build, with execution still outstanding. RISC-V64 and Windows ARM64 lack
configured local toolchains. Search deliberately remains single-worker.

An original paired-opening runner now records clocks, game files, binary/network
hashes, and pair-level statistics. Small development and validation suites are
separate. Read [the match guide](MATCHES.md) before running it. The optional
external move checker agrees on 93 positions at depth 2, including special moves.
The included 12-opening suites are too small for the runner's uncertainty gate;
no strength rating or improvement is established by their smoke tests.

A deterministic comparison helper now checks equal per-depth search work before
reporting throughput. The first buffer-reuse candidate passed correctness but
had inconclusive timing results, so it was not retained. The later Phase 3B
batching change is separate; [the experiment log](EXPERIMENTS.md) preserves the decision and
local evidence paths. Do not count this experiment as a strength improvement.

The owner is testing with Cute Chess while development continues. Snapshot
`0.1-dev-4b8b35d` is preserved under ignored `build/test-baselines/`, including
its own network and manifest. Read [manual testing](MANUAL_TESTING.md) and do not
replace that copy during ordinary rebuilds. GUI feedback does not block work.
The owner's [first two games](reports/2026-10-14-cutechess.md), submitted October
14, replay legally to threefold repetition and checkmate. All 171 positions
also passed legal-move and exact NNUE oracle checks. The owner reports working
GUI integration; exact runtime options and GUI version were not captured.
Long opening iterations spent much of the clock and left the black game in
severe time pressure. No deadline, mate-reporting, or evaluator defect was reproduced. Treat these games
as exploratory feedback, not a calibrated strength test or held-out suite.

Phase 2 covered **search efficiency and time management**; keep the
[roadmap](ROADMAP.md) and user updates explicit about phase and step. Root-level
diagnostics, an alternating clock-policy profiler, and per-engine match options
support the [time-management experiment](TIME_MANAGEMENT.md). `Time Policy` stays
`classic` by default; `forecast` is opt-in and `Search Diagnostics` defaults off.
The first soft-target forecast gate was rejected after it stopped a full depth
earlier on all 18 short-clock development comparisons. The narrower candidate
uses the hard deadline for prediction and retains classic soft stopping.
Do not treat reduced thinking time as a strength gain or enable diagnostics in
real matches. Explicit limits and all ponder requests exclude forecast behavior.

The 32-root `openings-time-validation.json` is original, legal, and disjoint
from the earlier 24 roots. It was held out until the completed time-policy
campaign described below; it is now exposed evidence, not fresh validation.
Use preserved binaries and complete records when auditing that comparison.

Phase 2C now has a conservative one-ply late-move-reduction candidate, selectable
with `Late Move Reductions=true`; the default remains false. Read
[selective search](SELECTIVE_SEARCH.md) for guards, mandatory ordinary-depth
verification, exact hashes, and results. Native/scalar/sanitizer checks passed,
and the new fixed-depth/node profiler independently checks legal PVs. Turning
LMR off preserves all 24 sampled frozen-parent signatures. At depth 5, reductions
used 49.79% fewer nodes with matching final moves/scores/PVs on all 12 development
roots, repeated twice. At 200,000 nodes, 8/12 roots completed an extra nominal
depth, but a move and several scores/PVs changed. This supports further testing,
not a strength claim. Keep classic timing for isolated LMR comparisons and use
`build/experiments/lmr-20261014/` for the frozen candidate. The owner's GUI bundle
and the separately frozen time-policy candidate are unchanged.
The predeclared eight-game smoke scored 2W/2D/4L for LMR with no operational
failures. This unfavorable small sample does not support default promotion;
record it honestly and do not tune to these pairs as if they were held out.

The independent [capture-ordering experiment](MOVE_ORDERING.md) is also now
implemented and checked. `Capture Ordering=mvv-lva` remains the default; `see`
uses legal-LVA material estimates to rank negative exchanges below quiet moves,
without pruning captures. Native/scalar/sanitizer tests, 28 composed/reflected
cases, and 4,117 generated reference comparisons passed. Default mode matched
all 24 parent samples. Depth-5 work fell 4.72% with matching final decisions;
equal-node searches gained one nominal depth on one root and lost one on another.
The eight-game smoke scored 2W/4D/2L without operational failures. No strength
claim or default promotion follows. Frozen candidate:
`build/experiments/capture-ordering-20261014/chess0live`, SHA-256
`7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
Use `tools/profile_lmr.py --experiment capture-ordering` for isolated comparisons;
it pins LMR off and classic timing. Its historical filename still supports LMR.

The separate [LMR loss replay](reports/2026-10-14-lmr-losses.md) found no
LMR-specific miss in its eight selected roots. All moves and all 40 common-depth
scores/PVs agreed; no LMR parameter changed. This is post-hoc development evidence,
not held-out qualification or proof that every reduction is safe.

Phase 2C's initial experiments are complete. Phase 2D's
[first time-policy screen](reports/2026-10-15-phase2d-time-policy.md) finished on
October 15, 14:24–17:18 Helsinki, using preparation commit `2cf55f7` and the
owner's one-run daytime exception. All 64 games / 32 pairs passed the independent
audit: forecast 14W/43D/7L, 35.5/64 points, conditional 95% score bounds
31.46–79.48%, no exclusions, clock forfeits, protocol failures, or artifact drift.
The predeclared result is **inconclusive**. Keep classic timing, LMR off, and
MVV-LVA as defaults; no strength or equivalence claim follows.

Evidence is in `results/phase2d-time-policy-20261015/`, including the immutable
pre-play `protocol.md`, launch manifest, complete match records, and `audit.json`.
Archive the whole directory when moving machines. The audited run's tool/protocol
hashes stayed unchanged during play; later documentation updates do not rewrite
that frozen record. The one-run exception is consumed. The GUI snapshot
`0.1-dev-4b8b35d` is unchanged; the subsequent LMR run used ordinary night limits.

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) is complete:
64 fresh full histories / 128 games at 60+0.6, seed `20261015`, frozen `b825a09`
binary on both sides, classic timing, only LMR on/off differing. It scored
**35W/82D/11L, 76/128 points (59.375%)**. The conditional 95% interval is
**42.40–76.35%**, so the predeclared result is **inconclusive**; LMR stays off.
No strength-gain or equivalence claim follows from the favorable point estimate.

All 100 workflow checks and real no-search preflight passed before play.
Preparation commit: `842ee41`; launch-record commit: `57e21fd`. The match ran
October 15 23:00:08–October 16 05:41:20 Helsinki (6h41m12s), within the ordinary
night window with one active worker. Audit and independent replay verified all
17,175 legal plies / 15,191 searches, exact clocks/options/outcomes, no exclusions,
failures, forfeits, truncations, or artifact drift. The runner and its macOS
idle-sleep assertion have ended; no automatic schedule or resume exists.

Preserve all of `results/phase2d-lmr-20261015/`: the immutable pre-play protocol,
launch/configuration/source hashes, match records, `audit.json`, and
`preserved-assets.json`. All five frozen binary/network artifacts, including
GUI `0.1-dev-4b8b35d`, remain unchanged. Later status-document edits are separate
from the audited unchanged before/after integrity record. The shared launcher
is `tools/qualification.py`, with historical time-policy and LMR entrypoints;
`tools/audit_lmr.py` independently pins the LMR protocol. Both completed suites
are exposed evidence, not fresh validation. Do not extend or retune their samples.

**Phase 3A is complete**, as recorded in the
[performance report](reports/2026-10-16-phase3a-baseline.md). Frozen builds are
`build/experiments/phase3a-20261016/release/` and `symbols/`; the release hash
matches the preserved capture-ordering binary, with experimental options off.
All 192 same-binary searches and 48 symbol-equivalence searches matched, with
independent legal-PV replay. A separate CPU profile and independent audit found
85.04% of 7,413 search observations in NNUE, including 58.69% in update.

Preserve all of `results/phase3a-20261016/`, including the denied sampler attempt,
corrected nested-bundle network setup, raw stacks, independent audits, and frozen
protocol/source hashes. The new `tools/profile_cpu.py` is macOS-only tooling;
`make test-profile-cpu` checks it with mocks. Its report records sampling-window
coverage but raw stacks still need independent identity/attribution inspection.
Do not use sampled timings as throughput results or include main-thread idle
observations in the search denominator. All measurement jobs have ended.

**Phase 3B is complete and retained.** The [result](reports/2026-10-16-phase3b-nnue-batching.md)
records one isolated change: stream up to eight feature columns and update
32 hidden lanes per tile, preserving modulo arithmetic, all multiset deltas,
enumeration, inference, search, and options. All three native/scalar/sanitizer
suites passed, including 360 independent arithmetic transitions and the existing
537-position incremental suite. The external 2,057-position oracle matched the
original corpus and every integer-stage/raw digest for both native and scalar.

All 576 comparison searches retained exact signatures and legal output.
The three fixed timing runs yielded median ratios **1.078081, 1.079836, 1.083612**,
above the 1.03 gate; all 24 pooled root/depth medians passed the 0.98 guard.
This establishes a sampled opening-search speedup on the M5 Pro, not Elo.
Keep `results/phase3b-20261016/`, all three candidate build configurations in
`build/experiments/phase3b-20261016/`, and `build/nnue-oracle-phase3b-20261016/`.
At the Phase 3B checkpoint, the normal native executable was byte-identical
to that tested candidate:
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.

**Phase 3C is complete with a mixed qualification outcome.** The
[report](reports/2026-10-16-phase3c-gamephases.md) records six original middlegames
at depth 6 and six endgames at depth 8, with baseline controls and two candidate
runs per phase. All 432 searches matched exactly; independent replay checked
3,024 PVs / 14,904 plies and all 432 bestmoves/ponders. Middlegames qualified:
ratios 1.087243 and 1.088055, stable control, all floor/root guards passed.
Endgame controls/ratios were favorable, but sparse pawn root `gamephases-eg-05`
took about 30–32 ms, below the frozen 50 ms floor in all six role/run medians.
Endgame and combined qualification are therefore **inconclusive**; no root was
excluded or workload changed. No engine code, binary, or default changed.

Preserve `results/phase3c-20261016/`, especially the frozen protocol, suite,
manifest, all six complete JSON/log comparisons, campaign lifecycle, audits,
and final integrity checks. Preparation commit: `ae5853a`. The full campaign
ran 11:57–12:11 Helsinki on October 16 in 844.997 seconds, within its 900-second
ceiling and normal daytime budget. All processes ended; no schedule is active.

**Phase 3D is complete.** The [report](reports/2026-10-17-phase3d-workload.md)
records baseline-only depths 8–12 and all 40 exact/legal searches. Depth 12
was the shallowest tested level meeting the frozen diagnostic rule: role medians
329.881/322.562 ms, paired ratio 0.999090 and MAD 0.028507. Its MAD is near the
0.03 limit; three pairs do not establish lasting repeatability. Depth 10's
ratio/MAD failures are retained. No candidate was compared or engine changed.

Preserve `results/phase3d-20261017/`: frozen protocol/manifest, five raw JSON/log
pairs, launcher/preflight, campaign, final integrity, and auditor/check scripts
and results. Preparation commit: `ec88195`. The failed `audit.json` records an
auditor-only API typo; the successful audit is **`audit-final.json`**. Raw evidence
was unchanged. All 35 integrity checks and 20 audit checks passed. The campaign
ran 21:10:32–21:10:40 Helsinki on October 17, using one active worker in the normal
daytime budget. All jobs ended; no schedule is active.

**Phase 3E is complete and qualified on the revised composed endgame sample.**
The [report](reports/2026-10-17-phase3e-endgames.md) records all six roots (pawn
`gamephases-eg-05` depth 12; other five depth 8), fresh controls and two candidate
rounds. All 216 searches matched exactly; replay verified 1,872 PV lines /
10,512 plies and 216 bestmoves/ponders. The complete control ratio was 0.998927,
MAD 0.003985; candidate ratios **1.089113 / 1.084243** passed with all duration
and root guards. Each round pools 30 pairs, five per root, with 16 baseline-first
and 14 candidate-first. Two candidate slowdowns, control outliers, and absolute
time drift are retained; no Elo or universal performance claim follows.

Preserve all of `results/phase3e-20261017/`, especially frozen protocol/manifest,
six raw JSON/log pairs, campaign, preflight/suite/integrity checks, auditor/check
scripts and outputs. Preparation commit: `c38bd9c`. Final audit `audit.json`
passed with zero errors; 29 auditor checks and 37 frozen-input checks passed.
The campaign ran 21:25:48–21:31:42 Helsinki on October 17 in 353.663077 seconds,
with one active worker under the normal daytime budget. All jobs ended and no
schedule is active. Production code, defaults, normal and frozen binaries are
unchanged. Phase 3C's original decision remains inconclusive; no old data was
pooled into 3E, and this completed campaign must not be extended selectively.

**Phase 3F is complete and retained.** Read the [fixed protocol](PHASE_3F.md)
and [result](reports/2026-10-17-phase3f-dense.md). Preparation `dd3d269` and
hypothesis `876511b` preceded implementation `500b022`. The NEON dense kernel
shares each activation across four output rows; scalar/singleton paths, feature
math, state updates, and search/defaults are unchanged. All native/scalar/sanitizer
suites passed (1,515 dense cases / 84,126 output comparisons, 360 update transitions,
537 incremental positions per backend); the 2,057-position SF19 oracle retained
all corpus/stage/raw digests. The 96 equivalence and 72 profile searches passed
independent audits and two raw-stack aggregations agreed.

All 576 timing searches matched exactly and replayed legally (3,552 PV lines /
15,840 plies). Control and both candidate rounds passed every phase gate; ratios
were opening **1.196321/1.195963**, middlegame **1.196515/1.213653**, and endgame
**1.324133/1.394803**. Four individual slowdowns, order effects, and substantial
absolute-time drift remain recorded. This finite engineering screen establishes
sampled throughput, not Elo. The campaign ran 23:16:49–23:29:15 Helsinki on
October 17, 746.807169 seconds, one active worker under the normal night budget.

Preserve `results/phase3f-20261017/`, especially both protocol snapshots, all
manifests/raw logs/samples, `timing-audit.json`, `final-integrity.json`, auditor
scripts/checks, candidate patch and full tables. There were no failed audits;
21 recorder tests, 23 launcher mock cases and 52 auditor checks passed. Setup-only
fixes are documented. Timing evidence must not be repeated selectively.

The qualified candidate, normal native executable, and optional
`0.1-dev-phase3f-20261017` GUI bundle share SHA-256
`edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b`.
The original `0.1-dev-4b8b35d` remains intact. The new bundle passed CLI startup,
adjacent-network discovery and legal depth-5 search from an unrelated directory.
The owner subsequently reported two draws against Gargantua with no GUI errors
on October 18. This was the intended snapshot; runtime options and executable
identity were not captured. The [review](reports/2026-10-18-cutechess.md)
preserves the partial PGN: 121 legal plies, matching depth-2 divides at 122
positions, and early clock depletion. The file ends unfinished at 61.Nc3. The
owner clarified that they adjudicated game 1 as drawn, judging it would finish
drawn and wanting to save the PGN before the GUI advanced. This is an owner
adjudication, not a replay-verified played-out ending. Game 2 has no PGN. Treat
these as exposed diagnostic games, not strength qualification or Phase 3G inputs.
The normal executable was intentionally promoted **after** the passing audit; the frozen manifest records
its old hash. Those old bytes remain at the retained Phase 3B path. Use the final
integrity record to distinguish promotion from unexplained artifact drift.

**Phase 3G is complete and audited.** The [fixed plan](PHASE_3G.md) compares
LMR on/off using the same qualified Phase 3F executable on 256 fresh opening
pairs / 512 games at 60+0.6. Four concurrent match workers require aggregate
accounting for four active searches and eight resident engines. Normal launch is
23:00–23:15 Helsinki; one common 07:00 cutoff survives preflight and worker starts.
Before any games, the owner authorized a one-time October 18 daytime start.
Protocol v2 and `--allow-daytime` encode that date-limited exception, preserving
the 50% daytime budget and next-morning cutoff. The amendment was tested and
committed as `fce2539` before starting `results/phase3g-lmr-20261018-daytime`;
no sample or decision
rule changed, no previous attempt ran, and no automatic restart is permitted.
All 189 match/qualification checks pass, including 29 launcher and 45 auditor
cases. Real v2 readiness plus independent transcript audit passed without a
search; retain `results/phase3g-preparation-20261018/daytime-v2-preflight.json`
alongside historical v1 records. See the validation amendment for exact scope.
The first actual attempt ran **October 18, 08:54:00–15:12:09 Helsinki**, before
the common October 19 07:00 cutoff. All four shards finished with 128 games
each. The independent `audit.json` passed with zero errors and no live-source
differences, verifying 60,323 legal plies and 50,352 charged search events.
The [result report](reports/2026-10-18-phase3g-lmr.md) records **225W/155D/132L,
302.5/512 points (59.08%)** and conditional 95% bounds **50.59–67.57%**.
Six candidate and seven baseline clock forfeits remain included. The frozen
decision is **operational regression**, so LMR stays off despite clearing the
numerical screen. This does not establish that LMR caused the flagfalls.
The runner and its idle-sleep assertion have ended; no scheduler or restart
exists. Preserve the full campaign, original audit, and frozen protocol.

The original 32 stems and deterministic legal continuations are not evaluated
for balance; related roots and common-host load limit statistical assumptions.
All 256 pairs passed the independent aggregate audit. Its conditional 95%
half-width is 8.488 percentage points: at least 299.5/512 points is only eligible
for fresh confirmation, never automatic promotion; at most 212.5 is negative.
Candidate clock forfeits take precedence. Do not resume, replace, or selectively
extend a sample, and do not pool the exposed Phase 2D result. Initial owner
feedback on the intended Phase 3F GUI
bundle is recorded; no more manual games are required. Do not start controlled
matches while any GUI games are running. LMR remains off. Phase 3H's subsequent
accounting repair is recorded below; it does not revise Phase 3G's result.
`tools/qualify_phase3g.py` supervises the run; `tools/audit_phase3g.py` checks all
four raw campaigns and one pooled decision. `make test-phase3g` checks the new
tools, while `make test-qualification test-match` includes historical regressions.
The protocol/suite preparation commit is `c177804`; tools and lifecycle fixes
are committed as `ff478a7`. See [validation](VALIDATION.md)
for the distinction between synthetic lifecycle evidence and actual readiness.
Quiescence legal generation still protects stalemate/checkmate precedence and
is outside this optimization. No new search-policy default was promoted.

**Phase 3H's bounded diagnosis/repair is complete.** Read the
[plan](PHASE_3H.md) and [result](reports/2026-10-18-phase3h-clocks.md).
`SearchLimits::received_at` carries the monotonic UCI receipt before parsing,
preparation, and dispatch. Ordinary clocks/movetime now include that delay;
ponderhit remains its own charge origin. Future origins clamp to entry and
extreme past elapsed values saturate safely. No allocation formula, overhead
default, LMR rule, or move-ordering policy changed. Native/scalar/sanitizer
suites pass, including deterministic expired-receipt and cold-network UCI tests.

All 13 Phase 3G flagfall histories are preserved as exposed diagnostics in
`tests/data/clock-flagfalls-phase3g.json`. `tools/probe_clocks.py` ran all 26
history/mode combinations once on each executable, with fresh tables and
readiness. All 52 returned legal, on-time moves; because the baseline also
passed, the historical failure is not reproduced by this isolated workload.
Only one historical case is consistent with uncharged startup; the other 12
cannot be attributed without final internal timestamps or scheduler evidence.
Do not claim all clock losses fixed or reinterpret Phase 3G as qualifying LMR.
Both original GUI bundles remain unchanged. The normal build contains the repair;
a frozen copy is at `build/experiments/phase3h-20261018/chess0live`.

Any reserve/allocation experiment needs a new bounded hypothesis and relevant
evidence; fresh strength confirmation is still deferred. Raw diagnosis, controls,
native/scalar/sanitizer logs, probes, and final integrity are retained under
`results/phase3h-20261018/`; the report documents exact scope and hashes.

**Phase 3I is complete.** Read the [plan](PHASE_3I.md) and
[receipt report](reports/2026-10-18-phase3i-receipt.md). `RecordingProtocol`
timestamps each input callback once, lets the pinned parser collect complete
lines, records the entire batch, then dispatches in original order. This removes
reproduced same-batch logging bias without backward timestamps on reentrant
`readyok` commands. A split line uses its terminating-newline callback; equal
timestamps remain audit-valid. Receipt is not kernel arrival, and earlier
event-loop stalls are still charged. Do not rewrite old logs or outcomes.

All 212 match/qualification/audit/diagnostic checks passed. The new POSIX
`tools/probe_receipt.py` completed its fixed 12-search control matrix: ordinary
replies were on time, a sleeping consumer was late despite on-time reader
receipt, and intentionally paused engines were late internally and externally.
All moves/PVs were independently legal. It uses a same-process reader thread,
not an independent observer; see its limitations before interpreting residuals.
Raw evidence and the frozen pre-probe plan are in `results/phase3i-20261018/`.
Engine sources and the final Phase 3H binary are unchanged; no rebuild or new
full engine/oracle suite is claimed. README introduction and GUI bundles remain.

**Phase 3J's implementation checkpoint is complete.** Its [plan](PHASE_3J.md) also includes the owner's
explicitly requested annotated puzzle input. The normal release accepts a
nonempty `bm` suffix after six FEN fields, or four fields with counters defaulted
to `0 1`. It discards metadata before search and rejects mixed `moves` histories.
Native/scalar/sanitizer suites passed; all 39 supplied workbook inputs matched
independent depth-2 legal divides and old/plain/annotated search signatures.
The exact 60-second example returned Qxf6+ at completed depth 8, without proving
mate in seven. The workbook remains unchanged and is not a held-out strength
suite. See [manual puzzle testing](MANUAL_TESTING.md#manual-puzzle-positions).

Match protocol persistence now uses bounded per-game writer threads; all
game/campaign filesystem work leaves the shared loop. Queue/timeout/disk failures
invalidate evidence and abort, with cancellation-safe cleanup. The 8 MiB / 4,096
record cap covers serialized pending/in-flight log payload, not total RSS. A
30-second writer timeout can leave a daemon that returns later; never reuse a
failed directory. Ordinary offloaded finalization retains ownership until done.
Read [match persistence limits](MATCHES.md#interpret-the-result).

All 230 workflow checks passed. The four-game, two-worker canary injected 100 ms
per log write and finished in 220.986 seconds: two checkmates, one threefold draw,
one 128-ply cap. No clock/protocol/storage failure was recorded, but the capped
game prevents the declared full operational acceptance. Preserve the attempt;
do not extend, replace, or score the capped game as drawn. Read the
[Phase 3J report](reports/2026-10-18-phase3j-persistence-puzzles.md).

**Phase 3K is in progress:** [the fixed plan](PHASE_3K.md) adds independently
implemented console tools and declares a fresh four-game LMR-on/off completion
screen at 1+0.05, two active workers, a 1,024-ply cap, and a 180-second deadline.
The screen is pending. Console `d`/`show`/`display`, view-only `flip`, `help`,
board-plus-static `eval`, and cancellable `go perft N` are implemented and checked.
New output uses `info string`; board output retains the FEN sentinel last, and
evaluation retains the raw record last. Legacy perft/divide contracts remain.
Native/scalar/sanitizer suites, independent board/perft checks on 93 positions,
and 36 exact old/new/diagnostic search comparisons passed. No engine search or
clock policy changed. Both GUI bundles and the README introduction remain intact.
The owner can test the normal build now; no additional GUI tournament is required.
No long campaign or schedule is active; the owner handles pushes.

Further experimental strength qualification, trainer integration, multi-platform
execution, release acceptance, and public strength claims remain open. The owner
can push the local commits. GUI `0.1-dev-4b8b35d` remains preserved; testing the
updated normal build is optional and must be labeled separately. Keep CHANGELOG entries
concise and create real version milestones when tested release gates pass;
research phases do not determine version numbers.

The unmodified SF19 match opponent is in ignored `build/stockfish19-reference`;
the instrumented NNUE oracle is separate. Never substitute one for the other.
Local GitHub authentication failed during initial setup; the owner's subsequent
instruction is to keep developing and committing locally while they push.

README contains the current runnable commands and limitations. CHANGELOG tracks
versions. [Architecture](ARCHITECTURE.md) describes boundaries, [validation](VALIDATION.md)
defines evidence, [portability](PORTABILITY.md) separates intended targets from
verified targets, and [NNUE](NNUE.md) owns the network pin and parity record.

## Before committing

Run the relevant correctness checks and inspect the diff. Keep generated binaries,
large networks, external oracle source, and raw match output out of Git. Record
what actually ran and what did not. Update these documents when APIs, commands,
test evidence, or limitations change. Make a small local commit on main and leave
GitHub pushes to the owner. Do not amend unrelated commits or rewrite history.
