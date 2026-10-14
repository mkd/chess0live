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

No release or strength rating has been established yet.
