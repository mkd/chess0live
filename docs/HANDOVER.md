# Developer and agent handover

## Accepted direction

Read [requirements](REQUIREMENTS.md) first. The user completed the interview:
original engine, strength over elegance, GPL-3.0-or-later, pinned SF19 network,
no own initial network training, desktop/laptop focus, M5 Pro primary, local-only
compute, and tested commits directly to main. The owner now handles GitHub pushes
manually; do not retry authentication or publishing from an agent session.

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
The normal native executable is byte-identical to the tested candidate:
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

**Active checkpoint: Phase 3E — endgame requalification preparation.** The
[protocol](PHASE_3E.md) fixes five original endgames at depth 8 and pawn root
`gamephases-eg-05` at depth 12. Six split comparisons cover fresh control and
candidate A/B rounds, each with five measured pairs per root plus warmups:
216 searches, 30-second search/300-second comparison/600-second campaign limits.
Pool all 30 individual pair ratios in each round, not the two group medians.
Retain local index ordering (16 baseline-first/14 candidate-first pairs per round).
All six roots participate in fresh exactness/noise/duration/regression gates;
never pool old timings or relabel Phase 3C. Measurements have not started.
The retained batching implementation and all frozen binaries stay unchanged;
further optimization and parallel search remain later work.
Quiescence legal generation still protects stalemate/checkmate precedence and
is outside this optimization. No new search-policy default was promoted.

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
