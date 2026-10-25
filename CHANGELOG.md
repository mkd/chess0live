# Changelog

Versions describe tested, user-visible deliverables. Research phases are not
release numbers; detailed measurements live in the linked experiment records.

## Unreleased — working toward 0.1

### Developer tools

- The exact-result comparison tool now accepts default, SEE-ordering and all-on
  presets for both builds, records process exits and checks readiness after
  every search. The engine's saved GUI settings are unaffected.

- Added a short default/all-on diagnostic with one/eight-thread accounting,
  saved analysis, automatic dependency setup and resource/time checks. The
  [diagnostic report](docs/reports/2026-10-25-phase4f4.md) separates worker
  activity and search work from speed or playing-strength claims.

- Completed the 39-position, eight-thread comparison of default and combined
  search settings. A repeatable loss of one mate report keeps the combined
  package under investigation; playing defaults remain unchanged. Detailed
  results and limitations are in the [audit report](docs/reports/2026-10-24-phase4f3.md).

- Added a reproducible combined-versus-default search comparison: saved puzzle
  analysis, explicit matched settings and a fresh paired-opening match protocol.
  Checks reject changed inputs, invalid moves, clock/resource failures and sleep
  interruptions. Search defaults remain unchanged pending strength evidence.

- Added a bounded comparison of two engine builds using current playing defaults,
  with exact search-result checks, independent move validation, fresh/reused
  caches and saved file identities. Optional Python dependencies prepare automatically.

- Added reversible local network selection, retained compatibility/provenance
  records, and one-command managed launching. The engine accepts `--eval-file`
  and advertises the chosen launch default to GUIs. Failed checks preserve the
  previous selection; ordinary launches keep their pinned default.

- Added local CPU network training, fine-tuning and export on macOS ARM64,
  with automatic isolated Python/package setup, pinned trainer source, saved
  recipes and automatic export compatibility checks. Reports distinguish actual
  optimizer steps/samples from unknown or declared game history. Synthetic smoke
  networks are for correctness tests; engine defaults remain unchanged.

- Added one-command network inspection and SFNNv16 compatibility checks against
  the separate pinned reference, with saved source/file identities and exact
  scalar/native evaluation comparisons. Alternative weights can be checked
  without changing the engine's network. Added digest-bound provenance templates;
  unknown training counts stay unknown and supplied claims remain unverified.

- Added one-command target builds with compiler discovery, compile/link checks,
  pinned local Windows toolchain downloads, offline cache reuse and saved logs.
  New builds use a separate output directory; SDK/system compiler prerequisites
  remain explicit. Compiler paths containing spaces now work through a literal
  path option without changing the existing Make compiler-command interface.

- Python tools and optional Make tests now prepare and reuse their own pinned
  dependencies automatically. Direct batch-puzzle runs need no manual package
  installation or environment activation; editable settings are preserved.
- Added checksum-verified downloads, offline cache reuse, concurrent-setup
  protection and recovery from incomplete installs, plus a shared tool launcher.

- Added and documented working C++26 build routes for Linux RISC-V64 and
  Windows ARM64. RISC-V passed runtime/Syzygy checks under QEMU; Windows
  ARM64 remains build-only pending a working runtime.
- Added an explicit Windows compatibility-layer validation mode. Windows
  x86-64 passed the runtime and Syzygy checks through Wine; this is separate
  from native Windows validation.

- Added portable runtime verification with saved reports, target/network checks,
  NNUE correctness and a two-thread UCI lifecycle. Current builds passed on
  macOS ARM64, Linux ARM64 in a VM, and emulated Linux x86-64; the Linux builds
  also passed Syzygy checks. Windows x86-64 remains build-only.
- Fixed cross-platform test links to honor the same extra runtime libraries as
  the engine. Added `make runtime-binaries` for building tests without trying to
  execute foreign binaries on the build host.

- Completed a 39-position, 60-second-per-position comparison of deeper quiet
  reductions against the accepted baseline. All 78 final moves were legal;
  best moves and reported mates matched. Deeper reductions remain experimental
  and disabled by default. See the [audit](docs/reports/2026-10-23-phase4d6.md).
- Completed and independently audited a 512-game LMR on/off comparison: 59.08%
  for LMR, with no clock forfeits. The subsequent default integration has its
  own regression checks and preserved opt-out.
- Prepared a fresh paired-opening LMR strength comparison with four concurrent
  games, fixed cutoff/resource limits and independent auditing. An explicit
  dated flag supports the owner's one-run daytime exception. This adds testing
  infrastructure; experimental search defaults remain unchanged.
- Added a bounded four-worker match-readiness check with independent replay of
  clocks, legal moves, settings, concurrency and process cleanup. It prepares
  reliability validation without changing engine play or default settings.
- Added an optional, separately built clock trace to diagnose position setup,
  search deadlines and reply delivery, with calibrated replay and protocol
  checks. Ordinary builds and playing settings are unchanged.

### Playing and analysis

- Added optional `TT Move Hints` to reuse legal cached moves across different
  repetition histories without reusing their scores. It shares the Hash budget,
  preserves score-table capacity and includes diagnostics and lifecycle tests.
  Disabled by default pending playing-strength qualification; the bounded
  [development comparison](docs/reports/2026-10-25-phase4f6.md) used about 5.7%
  fewer aggregate nodes, with some positions requiring more work.

- Removed a temporary quiet-move history list from each regular search node.
  Cutoff learning uses the already searched move-list prefix in the same order;
  bounded comparisons preserve search results. Defaults and pruning rules are
  unchanged. A short local comparison observed about 0.5–1.8% higher aggregate
  throughput, with some slower positions; this is not a strength result.

- Replaced SEE's repeated slider ray walks with precomputed bitboard lookups,
  preserving exchange rules and legal attackers. Independent reference and
  sanitizer checks passed. Short local comparisons observed about 0.7–1.5%
  higher aggregate throughput when SEE was enabled, with some slower positions.
  Playing defaults remain unchanged. See the bounded [comparison report](docs/reports/2026-10-25-phase4f5.md).

- Cached each move's ordering score once per sort and reused temporary storage
  within each search worker. Exact ordering and search results are preserved;
  the local comparison measured about 4–6% higher aggregate throughput, with
  some slower individual positions. Added a console
  recipe for testing all experimental search options together and restoring
  defaults. See the [validation report](docs/reports/2026-10-24-phase4f2.md).

- Reduced unnecessary quiet-move legality checks in quiescence search while
  preserving all legal captures, promotions, check evasions and stalemate
  detection. The local comparison completed the same search work about 11–12%
  faster; playing-strength gains have not been measured. See the
  [validation report](docs/reports/2026-10-24-phase4f1.md).

- Added optional `ProbCut` tactical probes with draw/endgame safeguards,
  reduced searches that include quiet defenses, and diagnostic counters.
  It is disabled by default pending tactical and playing-strength qualification.
- Fixed misleading hash occupancy resets in GUIs: retained entries now count
  across searches. Cache lookup and replacement behavior are unchanged.
- Added optional `Time Policy=bounded` to limit long clock-based thinks, plus
  separate experimental `Deep Quiet Reductions`. Both require explicit selection;
  neither is a demonstrated strength gain.

- Enabled conservative late-move reductions by default following the successful
  512-game comparison and a separate integration check. Explicit opt-out remains
  available; saved GUI settings may need `Late Move Reductions=true`. See the
  [scope and validation](docs/reports/2026-10-23-lmr-default.md).

- Added optional quiescence SEE capture pruning, with check, promotion,
  endgame and draw safeguards, plus diagnostic counters. It remains disabled
  by default pending tactical and playing-strength qualification.
- Added experimental shallow reverse-futility pruning with tactical/endgame
  exclusions and diagnostic counters. It is disabled by default pending
  separate playing-strength qualification.
- Added experimental verified null-move pruning, with legal-move verification,
  draw/endgame safeguards, and per-worker diagnostic counters. It remains
  disabled by default until separate playing-strength qualification.
- Added experimental quiet countermove ordering, with worker-local reply memory
  and diagnostic counters. It changes move order without reducing search depth
  or pruning. The [mixed development screen](docs/reports/2026-10-18-phase4d-countermove.md)
  did not establish a broad efficiency gain; it remains disabled.
- Added optional Syzygy endgame probing through a pinned Fathom reader, with
  UCI path/piece/depth settings and `tbhits` reporting. Table files are downloaded
  separately and excluded from Git. Root move ranking respects the fifty-move
  clock; missing coverage falls back to search. DTZ is never reported as mate.

- Added configurable Lazy SMP parallel search with shared hash/network memory,
  private worker state, and coordinated stopping, clocks, and total node limits.
  `Threads` accepts 1–64 and still defaults to 1. Final UCI node/NPS reports
  include unfinished iterations and all workers; extra work alone is not an
  established playing-strength improvement.
- Measured useful multicore scaling on the M5 Pro: four workers delivered
  3.25× aggregate throughput, finished nominal depth-6 searches 2.09× faster,
  and completed one extra depth in all nine timed comparisons. Single-worker
  search behavior stayed exact, with a small possible timing cost recorded.
  See the [bounded results and limitations](docs/reports/2026-10-18-phase4b-smp.md).
- Added standard UCI `hashfull` reporting so chess GUIs can show recent
  transposition-table occupancy during analysis and play.
- Reduced transposition-table storage by one third while preserving entry
  capacity and tested search behavior. At `Hash=64`, table storage falls from
  48 MiB to 32 MiB; sampled search timing was effectively unchanged.
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
  The initial baseline used one worker; configurable parallel search is now
  available through `Threads`.
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

- Added a small UCI batch runner with 39 embedded FENs, editable Threads/Hash/time
  settings, and printed mate scores and best moves. Uses python-chess for engine
  communication; no spreadsheet input is needed at runtime. Adopted the suite
  for matched tactical progress/regression checks at development checkpoints.

- Added a separate 1,024-game current-engine LMR comparison with fresh paired
  openings, eight-worker resource controls, a fixed overnight cutoff, and an
  independent raw-game audit. This adds validation tooling; LMR remains disabled
  by default pending the result.
- Added optional cache hit/cutoff/replacement diagnostics and a bounded profiler
  that checks legal search output, occupancy, memory accounting, and cold/warm
  behavior on development positions.
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
  ordering. Current defaults are classic timing, conservative LMR on, and
  MVV-LVA ordering; forecast timing and SEE ordering remain experimental.
- Completed the [64-game time-policy screen](docs/reports/2026-10-15-phase2d-time-policy.md)
  and [128-game LMR screen](docs/reports/2026-10-16-phase2d-lmr.md). Both passed
  their operational audits but were inconclusive under their predeclared rules.
  SEE also remains experimental; its small development match does not qualify it.
- Completed and audited the [512-game LMR comparison](docs/reports/2026-10-18-phase3g-lmr.md):
  LMR-on scored 225 wins, 155 draws, and 132 losses (59.08%). Six candidate
  clock forfeits block acceptance; seven baseline clock forfeits also need
  investigation. That historical attempt kept LMR off; the later successful
  qualification and separate integration are recorded above.
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
