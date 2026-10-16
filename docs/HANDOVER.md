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
had inconclusive timing results, so it was not retained. The original evaluator
remains current; [the experiment log](EXPERIMENTS.md) preserves the decision and
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

The current work is **Phase 2: search efficiency and time management**; keep the
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

**Next checkpoint: Phase 3A measurement only**, as specified in the
[roadmap](ROADMAP.md). Freeze the default baseline, prove timing repeatability
with identical builds, collect a bounded CPU profile on development positions,
and propose one measured bottleneck to address. No engine optimization starts
before its exact-equivalence/timing criteria are fixed. Relevant rule/perft,
NNUE oracle and reversible-state, native/scalar/sanitizer, and UCI gates must
remain intact. Quiescence legal-move generation currently protects stalemate
and checkmate precedence; do not remove that work casually. NPS gains are not
Elo gains. Phase 3A has not started; further experimental strength qualification
(including SEE) is deferred rather than passed. Trainer integration,
multi-platform execution, release acceptance, and public strength claims remain
open. The owner can push the local commits; no GUI retest is required for this
checkpoint because neither engine code nor the frozen GUI binary changed.

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
