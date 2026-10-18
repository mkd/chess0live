# Phase 4A: measure cache efficiency and report hash occupancy

Started October 18, 2026 from `33835863d5344946dcf36e4e25af98a48bb0e63a`.
The owner requested visible Cute Chess hash reporting and continuation into cache
work, without indefinitely extending the earlier qualification phases.

## Bounded scope

1. Add standard `hashfull` to every completed UCI search report, including
   terminal/drawn roots. Report integer permille of a bounded sample of nonempty
   entries from the current search generation. This measures recent occupancy,
   not hit rate, allocated memory, or playing strength. Preserve ordinary UCI
   formatting and the plain console commands accepted in Phase 3L.
2. Add opt-in per-search cache counters to `Search Diagnostics`: probes, hits,
   bound cutoffs, save attempts, occupied different-key replacements, and actual
   entry/bucket/capacity/allocation geometry. No per-node output and no counter
   increments when diagnostics are off. Use an independently checked profiler
   over already exposed development roots, with cold and warm table runs.
3. Consider at most one cache change justified by these measurements. Preserve
   full keys, draw/history context, mate normalization, replacement semantics,
   and all stored move information. A representation-only candidate must retain
   bucket count/indexing and exact search behavior. No new pruning, position-only
   bounds, parallel search, or held-out campaign is part of this phase.

The initial measurement is three exposed `tools/bench.py` roots, depth 5,
Hash 1 and 64 MiB, cold then warm, one active worker. The initial instrumented
binary is frozen before any candidate. If a layout candidate is justified,
predeclare its finite comparison before timing it. Do not optimize repeatedly
against the same results. Record a rejected/inconclusive candidate honestly and
finish the checkpoint with useful telemetry.

## Correctness and reporting gates

- Validate the UCI field's presence/range, populated samples, clear/resize/new
  game behavior, current-generation interpretation, and terminal reports.
- Validate counter accounting, zero-work cases, and diagnostics on/off search
  equivalence. Counters include attempted work interrupted by a limit; `stores`
  includes save attempts retaining a deeper exact result. `replacements` counts
  only eviction of another occupied key.
- Check raw profiler output against independent legal PV/bestmove replay,
  exact field accounting, frozen engine/network digests, and resource limits.
- Run native correctness and relevant scalar/sanitizer suites for any entry
  representation change. Preserve both stable GUI bundles and Phase 3L inputs.
- Record bounded measurements and their limits; no Elo/default search-policy
  promotion or broad platform execution claim follows from this phase.

## One layout candidate: declared after the initial measurement

The initial depth-5 profiles passed: the native entry is 24 bytes and a bucket
96 bytes; `Hash=64` allocates 48 MiB for 524,288 buckets / 2,097,152 entries.
Cold runs show genuine cache hits and cutoffs; warm searches reuse state heavily.
The byte geometry justifies one representation candidate: full 64-bit key,
32-bit packed move/bound, signed 16-bit score, 8-bit depth, full 8-bit generation.
Depth never exceeds the root limit 126 because a child decrements before its
single check extension. Preserve all move fields and invalid-square sentinels.
Use 64-byte aligned four-entry buckets, without claiming every CPU has that line
size. Keep the legacy 96-byte sizing divisor so bucket count and replacement
behavior remain unchanged. Expected table storage is 32 MiB at `Hash=64`.

Before candidate measurements, fix these finite checks:

- Exact instrumentation/candidate per-iteration signatures, cache event counts,
  and occupancy for all three bench roots at depth 5, cold/warm, Hash 1 and 64;
  all 12 exposed composed game-phase roots at depth 4, cold/warm, Hash 64.
  Independently validate moves/PVs. Geometry alone is expected to differ.
- Direct entry round trips, special-move flags/promotions/invalid sentinels,
  score/depth/bound/generation limits and wrap, plus native/scalar/sanitizer tests.
- One diagnostics-off alternating timing comparison: three bench roots, depth 6,
  Hash 64, one warmup per engine/root and five measured repetitions. No compiler
  or other engine searches alongside. Require exact work throughout; baseline
  median at least 0.1 s per root, geometric mean of root median paired speed
  ratios at least 0.97, and no root median ratio below 0.90. These are practical
  regression guards for a memory-saving representation, not significance or
  strength tests. Retain only if all correctness and memory gates also pass.

If a gate fails or measurement is inconclusive, keep telemetry, record the
candidate outcome, and defer the representation. Do not add another layout
candidate or raise depth/repeat counts to chase this result.

## Protocol reference

The original [UCI specification](https://www.shredderchess.com/download/div/uci.zip)
(`engine-interface.txt`, linked by the
[UCI publisher](https://www.shredderchess.com/chess-features/uci-universal-chess-interface.html))
defines `hashfull` in permille and requests regular reporting. It does not
prescribe sampling or an age window. This engine explicitly samples up to 1,000
entries and counts entries saved/refreshed in its current 8-bit generation.
Generation wrap is approximate aging, not proof of every entry's true age.

## Exit

Commit tested telemetry, the measured cache decision (if any), practical usage
documentation, and a result report. Keep the README introduction unchanged.
Then proceed to Phase 4B, Lazy SMP, with shared-cache concurrency designed and
tested explicitly; the current table is single-worker owned. Optional Syzygy
follows. The separately frozen Phase 3L campaign remains unstarted.

## Completed decision

All declared gates passed; retain the one compact-entry candidate. The
[result report](reports/2026-10-18-phase4a-cache.md) records exact comparisons,
33.3% smaller table storage, effectively neutral sampled timing, test scope,
raw evidence, and remaining limitations. No search policy or strength claim
changed. Phase 4B is next.
