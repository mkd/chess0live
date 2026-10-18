# Phase 4B: configurable Lazy SMP

This checkpoint adds parallel search after Phase 4A's compact cache. It does not
change the default search policies or declare a playing-strength gain. Parent:
`a58da0d`, executable SHA-256
`9caa5ccc3716ef25c289c8c43d63762c811163f2a4c7f1e8432fd9e012d8168c`.

## Implementation contract

- `Threads=1` remains the default; support 1–64 workers with one shared Hash
  allocation and immutable network weights. Mutable positions, NNUE accumulators,
  histories, killers, and principal variations belong to individual workers.
- Publish and read complete cache entries with legal C++ synchronization. No
  unsynchronized data race, including an assumed harmless torn cache entry.
  Retain the existing single-worker cache capacity and replacement semantics.
- The leader supplies moves, scores, and completed depth. Helpers explore
  alternate move orders and contribute shared cache entries. All workers obey
  one cancellation request, pondering origin, hard deadline, and total node cap.
- Join helpers before returning a result, replacing the network, changing
  options, clearing memory, or shutting down. Immediate stop and exceptions
  must not leave a worker behind.
- UCI nodes/NPS describe aggregate work, including redundant work. A final
  nodes/time/hashfull record includes unfinished iterations and helper shutdown.
  Opt-in diagnostics distinguish leader iterations from per-worker totals.

## Bounded validation and measurement

1. Run existing correctness suites and independent multiworker protocol/legal-PV
   checks. Exercise two/four workers, immediate/repeated stop, ponderhit, global
   node caps, terminal roots, searchmoves, resize, and newgame. Attempt a separate
   ThreadSanitizer build; record runtime limitations rather than claiming a pass.
2. Compare the saved parent and candidate at Threads=1 on the three already
   exposed `tools/bench.py` roots. Require exact completed-depth nodes, scores,
   and PVs. Record timing as a regression diagnostic.
3. Measure Threads=1/2/4 at Hash=64 with the pinned network, classic timing,
   LMR off, MVV-LVA, and diagnostics off. One resident/active engine, clear state
   between samples, rotating/reversed order, one warmup and three measured
   repetitions per root/configuration. Use 1,000 ms searches and depth 6 for
   bounded fixed-depth latency. Preserve raw lines and artifact hashes.
4. Report aggregate throughput, completed leader depths, external latency, and
   variability separately. Parallel searches need not have equal node counts or
   PVs. More nodes per second alone cannot establish strength or useful scaling.

Use only exposed roots, never the frozen Phase 3L qualification openings. Recheck
the local resource budget between samples; four workers fit this host's daytime
allowance of nine. No match campaign, automatic schedule, or default-policy
promotion is part of this checkpoint. Stable GUI bundles and the frozen Phase 3L
executable/manifest remain untouched. Next roadmap area: Phase 4C, Syzygy.

## Evidence

The [result report](reports/2026-10-18-phase4b-smp.md) records the completed,
independently audited screen, passing correctness/race checks, measured parallel
gains, small possible single-worker cost, and limitations. Retain the implementation
with Threads=1 still default; no Elo or release claim. Raw local artifacts live under
`results/phase4b-20261018/`; binaries under `build/experiments/phase4b-20261018/`.
