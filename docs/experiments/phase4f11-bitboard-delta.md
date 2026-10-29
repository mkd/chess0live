# Phase 4F.11 follow-up — shared bitboard change detection

Declared October 29, 2026, after the first candidate completed its three runs.
Its exact arithmetic/search checks passed and run medians were 1.048235,
1.044654 and 1.047207, but the pooled warm `gamephases-eg-02` ratio was
0.973793, below the declared 0.98 guard. That candidate is not accepted under
the first protocol. Preserve all first-candidate sources, binaries and results.

The first candidate scans 64 square identities separately for each perspective.
The isolated follow-up computes the union of changed piece bitboards once per
evaluation and shares that dirty-square mask between perspectives. Each square
whose piece identity changes must remain included, including captures with
unchanged occupancy and promotion. Feature selection, refresh rules, arithmetic,
network and search policy remain fixed. No thresholds or position-specific
exceptions are introduced.

Repeat native/scalar/sanitizer feature and accumulator checks, exact pinned
reference comparison and relevant search/lifecycle checks on the new source.
After correctness passes, freeze a separate binary and use the same original
parent, fifteen-root corpus, settings and timing rules as
[the first protocol](phase4f11.md). Run three new alternating depth-6 comparisons
with three repetitions per cold/warm case, 20-second search and 300-second run
limits. Each 90-pair run median must exceed 1.03; every pooled nine-pair
root/state median must be at least 0.98. Preserve every result and report this
as a follow-up on exposed development data, not independent confirmation.

The original same-binary control remains the context for timing noise; it does
not eliminate uncertainty in millisecond-scale searches. No full puzzle run,
strength match, new schedule, pruning-policy change or Elo claim is included.
