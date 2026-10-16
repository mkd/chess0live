# Phase 3B proposal: batch NNUE accumulator updates

Status: proposed after [Phase 3A measurement](reports/2026-10-16-phase3a-baseline.md),
not implemented or benchmarked. Fix this scope and these gates before changing
the engine. The ordinary defaults and all frozen Phase 2 candidates stay intact.

## Evidence and hypothesis

On the M5 Pro, the opening-search sample attributed 4,351 of 7,413 active-search
observations (58.69%) to the NNUE `update` subtree. This includes feature
enumeration, sorting, and delta application. The two delta-application call sites
accounted for 2,582 exclusive observations (34.83%), subject to optimized source
line attribution. These are sampled costs, not hardware bandwidth measurements.

Current `differences` applies each added or removed feature by walking the entire
hidden accumulator through `adjust`. The hypothesis is that collecting the same
feature changes and applying them in batches can reduce repeated hidden-vector
loads/stores. The profile supports investigating this boundary; it does not
prove that these loads/stores are the cause or that batching will be faster.
Extra change-list work and less favorable weight access could erase the benefit.

## One isolated change

Change only how the existing feature deltas update NNUE accumulator/PSQT lanes.
Keep feature enumeration, sorting, network layout, inference layers, evaluation
calibration, search, move ordering, time management, and UCI defaults unchanged.
Do not combine this with a new accumulator stack, dirty-piece tracking, network
format, allocation-only reuse experiment, or new CPU instruction requirement.

Preserve these invariants:

- Exact before/after **multiset** differences, including repeated feature indices.
  Do not assume feature-count or change-count limits without proving them; no
  truncation, undocumented fixed-size buffers, or dropped deltas.
- Hidden lanes use the same modulo-2^16 arithmetic; PSQT lanes use modulo-2^32.
  Addition can be regrouped in that domain, but signed C++ overflow, saturation,
  intermediate narrowing, and SIMD widening must not change the result.
- Arbitrary evaluation transitions still work: skipped nodes, siblings,
  backtracking, king mirror/bucket changes, captures, promotions, en passant,
  castling, reset, and network reload. No assumption of consecutive legal moves
  may replace the evaluator's current contract.
- Both native NEON and portable scalar paths match the existing mathematical
  reference. Keep an independent column-at-a-time check for the new batching
  logic so optimized/full-refresh paths cannot conceal the same error.

## Correctness gates before timing

1. Meaningful unit checks compare batched updates against the old column-at-a-time
   arithmetic for additions/removals, duplicate indices, empty changes, maximum
   legal change sets, and extreme lane/weight values. No undefined overflow.
2. Native, scalar, and ASan/UBSan engine suites pass, including the real-network
   537-position incremental/full-refresh and special-move/backtracking checks.
3. Rerun the pinned Stockfish 19 stage oracle on the recorded 2,057-position
   corpus: features, accumulator, PSQT, transformed input, affine/activation
   layers, and final outputs must agree exactly for native and scalar builds.
   Preserve any changed corpus digest and investigate it rather than relabeling
   previous evidence. Use only the external oracle, never linked engine code.
4. Fixed-depth search signatures and independent legal-PV replay match the frozen
   release baseline at all 12 development roots, depth 5 and depth 6. Run the
   existing perft/rule/state and UCI lifecycle checks. No behavioral tolerance.

## Fixed timing and retain/reject rule

Freeze new artifacts after correctness passes. Compare against the Phase 3A
release executable (`7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`)
with the same compiler and release flags, network, options, host, and 12 roots.
Use one active worker and the ordinary resource budget. No sampling during
timings and no concurrent compilation or engine testing.

- Two complete depth-5 comparisons, each with seven measured repetitions and
  one warmup per root/role, alternating order through `compare_bench.py`.
- A separate depth-6 comparison with three measured repetitions and one warmup
  per root/role. Per-search timeout 30 seconds, outer ceiling ten minutes per
  comparison. Preserve incomplete runs; do not omit slow or unfavorable roots.
- Require exact signatures in every run. Retain the candidate as a measured
  implementation speedup only if the aggregate median ratio is **at least 1.03
  in both depth-5 runs and the depth-6 run**, and each root's pooled median ratio
  is **at least 0.98 at each depth**. Report all per-root times, order effects,
  dispersion, and any large individual slowdowns alongside these gates.

This is an engineering acceptance rule fixed before implementation, not a
statistical confidence interval. It aims to exceed the roughly 0.8-percentage-
point paired MAD observed in Phase 3A. Meeting it supports only sampled
throughput improvement. Failure or inconclusive timing means retain the baseline
and record the experiment; changing the rule requires a new declared experiment.
No default search-policy change or Elo claim follows from this work. Broader
game-phase performance and clock-managed strength remain separate validation.
