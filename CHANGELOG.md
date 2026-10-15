# Changelog

Versions describe tested deliverables. Research objectives are not results.

## Unreleased — working toward 0.1

- Established the independent-engine scope, GPL-3.0-or-later license, SF19 NNUE
  interoperability target, and desktop-first platform priorities.
- Defined correctness, evaluation-parity, reproducibility, and strength gates.
- Recorded local resource policy: 50% daytime, 80% from 23:00 to 07:00 in
  Europe/Helsinki, with a manual override.
- Added reversible bitboard positions, legal move generation, strict FEN parsing,
  deterministic hashing, `perft`, and divide diagnostics.
- Added the pinned SF19/SFNNv16 reader, all three feature families, incremental
  accumulators, integer inference, scalar reference, and ARM64 NEON kernels.
- Added independently written single-worker PVS search, quiescence, bounded
  transposition storage, draw handling, cancellation, pondering, and time control.
- Added asynchronous UCI, network configuration, exact oracle comparison tools,
  regression tests, sanitizer builds, and repeatable custom-position benchmarks.
- Added Make cross-target checks and configuration-aware rebuilds; fixed network
  preparation before timed search and default-network discovery via PATH.
- Added paired-opening match tooling with explicit clocks, PGNs, reproducibility
  records, separate failure reporting, and conservative pair-level statistics.
- Added original development/validation openings and optional independent
  legal-move/perft comparison against a pinned external referee library.
- Updated the workflow to tested local commits; the owner publishes to GitHub.
- Preserved a separate local GUI test snapshot and documented Cute Chess setup
  so manual feedback and engine development can proceed together.
- Added alternating baseline/candidate benchmarks that require identical search
  work, preserve raw evidence, and report observed timing variability.
- Recorded an inconclusive NNUE buffer-reuse experiment; the candidate was not
  retained and no speed or strength gain is claimed.
- Recorded the first owner-run Cute Chess games, verified all 169 plies and
  legal-move/NNUE agreement at 171 positions, and documented clock-allocation
  findings. No runtime change or strength claim follows from these two games.
- Added validated per-engine match options, frozen in experiment records, while
  preserving common resource settings and disabling search diagnostics in games.
- Added opt-in root-iteration diagnostics and an alternating clock-policy
  profiler with raw output, exact work accounting, and reproducible inputs.
- Added an experimental hard-deadline forecast policy; classic remains the
  default. Rejected its earlier soft-target gate after it stopped too early.
- Added a 32-opening held-out time-policy suite, documented both candidate
  results, and prepared a longer blitz test without starting or scheduling it.
- Added a phase roadmap and checkpoints for continuing development; no playing
  strength improvement is claimed from the short profiles or smoke games.
- Added experimental one-ply late-move reductions, protected tactical/special
  moves, ordinary-depth verification of promising probes, and search-policy
  cache isolation. The option remains disabled by default.
- Added selective-search diagnostics, deterministic guard/verification tests,
  and fixed-depth/node profiles with independent legal-PV checks and preserved
  partial-failure evidence. Move ordering and time-policy experiments stay separate.
- Recorded the LMR candidate's reduced depth-5 work and unfavorable 2W/2D/4L
  operational smoke; retained it only as an opt-in experiment, with no strength
  gain or default promotion claimed.

- Added an independent static-exchange estimator and optional capture ordering,
  preserving every searched move and leaving MVV-LVA as the default. Covered
  pins, x-rays, king recaptures, en passant, promotions, and reversible state
  with composed and generated reference checks.
- Extended the fixed-depth/node profiler to isolate capture ordering from LMR,
  validate ordering diagnostics, and preserve partial-failure evidence.
- Investigated all four LMR smoke losses at eight selected roots; no LMR-specific
  miss was demonstrated in the bounded replay, so no reduction parameters changed.

- Recorded capture ordering's 4.72% lower sampled depth-5 work and 2W/4D/2L
  operational smoke. It remains opt-in; the initial Phase 2C experiments are
  complete and Phase 2D strength qualification remains pending.

- Prepared Phase 2D's fixed 64-game time-policy qualification with pinned assets,
  readiness checks, an enforced Helsinki cutoff, preserved interrupted evidence,
  and an independent game/clock/statistics audit. Predeclared a conservative
  confirmation-review criterion; no automatic default promotion.

No release or strength rating has been established yet.
