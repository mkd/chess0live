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

No release or strength rating has been established yet.
