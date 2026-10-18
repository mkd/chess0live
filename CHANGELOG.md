# Changelog

Versions describe tested, user-visible deliverables. Research phases are not
release numbers; detailed measurements live in the linked experiment records.

## Unreleased — working toward 0.1

### Playing and analysis

- Console board, evaluation, help, and perft output now prints as plain text,
  without `info string` prefixes. Normal UCI search still reports centipawns
  or a signed mate distance; both have explicit protocol regression checks.
- Added ASCII board/state display with `d`, `show`, or `display`, a view-only
  `flip`, and built-in `help`. `eval` now includes the board and a clearly labeled
  static NNUE score. `go perft N` adds root counts, timing/speed statistics, and
  responsive cancellation while preserving the older diagnostics.
- Added manual puzzle input with trailing `bm` answer notes, including four-field
  records with omitted move counters. Notes are ignored by search; invalid boards
  still produce errors. All 39 owner-supplied puzzle inputs passed compatibility
  and independent legal-move checks.
- Fixed clock accounting so preparation and worker startup after receiving `go`
  consume the existing time budget. Expired requests return a legal fallback;
  pondering still starts charging at `ponderhit`. This does not eliminate
  operating-system or transport delays.
- Added a playable, independently written UCI engine with legal bitboard moves,
  draw detection, time management, pondering, and responsive search cancellation.
  Search currently uses one worker.
- Added evaluation using the pinned Stockfish 19 NNUE network, with incremental
  updates, a portable reference implementation, and ARM64 NEON acceleration.
  Feature, accumulator, and output agreement have dedicated oracle checks.
- Added strict FEN input, `perft`, and move-by-move divide output for investigating
  positions and move-generation problems.
- Batched NNUE accumulator updates improve measured throughput on the M5 Pro:
  7.8–8.4% in opening tests, 8.7–8.8% in composed middlegames, and 8.4–8.9%
  in the revised composed endgame test. Exact evaluation/search checks passed;
  measured playing-strength improvement remains open.
- Improved ARM64 neural-network inference by sharing inputs across four outputs.
  The fixed M5 Pro screen measured 19.6% higher opening throughput, 19.7–21.4%
  in middlegames, and 32.4–39.5% in endgames over the previous retained engine.
  Exact results and all gates passed; timing variation and four individual
  slowdowns remain recorded. This is not a measured playing-strength gain.
- Added Cute Chess setup instructions and preserved a separate GUI test bundle
  so development rebuilds do not replace the owner's test executable.
- Recorded [October 18 Cute Chess feedback](docs/reports/2026-10-18-cutechess.md):
  two reported draws without engine errors, a legally checked partial PGN, and
  early clock depletion for further investigation. Defaults remain unchanged.

### Building, testing, and contributing

- Prepared a reproducible 512-game comparison with fresh openings, explicit
  prior-position exclusions, frozen engine inputs, resource controls, and an
  independent audit. Readiness passed without searching the test positions;
  no new match result or search-default change is claimed.
- Validated console diagnostics against an independent chess referee and passed
  a fresh four-game match-runner completion check with no clock, protocol, or
  storage failures. This is operational evidence, not a strength result.
- Moved match logging and result-file writes outside active protocol handling.
  Bounded buffers and explicit storage-failure handling prevent slow writes from
  blocking other games' response callbacks or silently discarding evidence.
- Added a simple Make interface, documented cross-compilation prerequisites,
  configuration-aware rebuilds, and reliable default-network discovery.
  Native macOS ARM64 execution and foreign cross-build evidence are documented
  separately; not every intended target has been run.
- Added independent dense-network arithmetic checks for extreme values and all
  input/output lanes, plus a separate Phase 3F Cute Chess test bundle.
- Added correctness and sanitizer checks, independent legal-move verification,
  reproducible benchmarks, and paired-opening matches with saved PGNs, clocks,
  options, artifact hashes, and independent result audits.
- Added coordinated overnight match testing with a shared resource budget,
  cutoff, and independent whole-campaign audit. Fixed cancellation during engine
  shutdown so a stopped test cannot silently begin another game.
  Added a dated, explicit owner-authorized daytime exception with matching audit
  checks; normal resource limits, fixed samples, and cancellation rules remain.
- Added saved-position clock diagnostics with both LMR modes, legal-PV checks,
  and preserved command/response timestamps for investigating late moves.
- Fixed match-clock measurements so logging cannot charge extra time to moves
  already received in the same input batch. Added controlled receipt-delay
  diagnostics; historical match results and engine playing behavior are unchanged.
- Added GPL-3.0-or-later licensing, architecture and handover documentation,
  a development roadmap, and local resource controls with manual overrides.

### Research status

- Added optional forecast timing, late-move reductions (LMR), and SEE capture
  ordering. **Defaults remain classic timing, LMR off, and MVV-LVA ordering.**
  No accepted playing-strength gain is established.
- Completed the [64-game time-policy screen](docs/reports/2026-10-15-phase2d-time-policy.md)
  and [128-game LMR screen](docs/reports/2026-10-16-phase2d-lmr.md). Both passed
  their operational audits but were inconclusive under their predeclared rules.
  SEE also remains experimental; its small development match does not qualify it.
- Completed and audited the [512-game LMR comparison](docs/reports/2026-10-18-phase3g-lmr.md):
  LMR-on scored 225 wins, 155 draws, and 132 losses (59.08%). Six candidate
  clock forfeits block acceptance; seven baseline clock forfeits also need
  investigation. LMR stays off, with clock reliability the next priority.
- Preserved rejected and inconclusive work, including the discarded NNUE
  buffer-reuse candidate and early forecast policy, in the
  [experiment log](docs/EXPERIMENTS.md).
- Extended CPU profiling to cover legal opening, middlegame, and endgame suites
  with explicit per-position depths and saved workload identities.
- Added a bounded CPU profiler and completed the [Phase 3A performance baseline](docs/reports/2026-10-16-phase3a-baseline.md).
  Its findings led to the retained [Phase 3B accumulator improvement](docs/reports/2026-10-16-phase3b-nnue-batching.md),
  with independent arithmetic tests and audited comparisons. The subsequent
  [game-phase validation](docs/reports/2026-10-16-phase3c-gamephases.md) confirmed
  the middlegame gain; endgame inference remains inconclusive because one pawn
  position was too short for the fixed timing rule. No unfavorable root was omitted.
- Completed a [baseline-only depth ladder](docs/reports/2026-10-17-phase3d-workload.md)
  to propose a longer pawn-ending test. All 40 searches matched exactly and
  replayed legally, preparing the subsequent endgame comparison.
- Completed [endgame requalification](docs/reports/2026-10-17-phase3e-endgames.md)
  with fresh controls and all six roots. All 216 searches matched exactly;
  the declared performance gates passed. Individual slowdowns and timing drift
  remain documented. These checkpoints change no engine behavior or release version.

No release or strength rating has been established yet. Version 0.1 remains
subject to the [release acceptance gates](docs/VALIDATION.md#release-gates).
