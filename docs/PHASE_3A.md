# Phase 3A: measure the default engine

Status: [checkpoint completed October 16, 2026](reports/2026-10-16-phase3a-baseline.md).
The protocol below was fixed before collecting timings or CPU samples and is
preserved verbatim in the local result directory. This later status update
does not alter that record. This checkpoint delivers a reproducible opening-search
baseline and one measured optimization proposal. Engine changes belong to the
next checkpoint, after their correctness and timing criteria are fixed.

## Scope and frozen inputs

Use source revision `9daaade`, C++26, the ordinary generic ARM64 `-O3 -DNDEBUG`
release flags, and the pinned `nn-1a298aa575a0.nnue` network. Make a separate
optimized build with debug symbols for CPU attribution; symbols do not justify
using a debug or sanitizer optimization level. Preserve both executables and
their build/source/compiler/network hashes before measurements. Record host
CPU, RAM, operating system, tool identities, and resource policy.

Both builds use classic timing, LMR off, MVV-LVA, Threads 1, Hash 64 MiB,
Ponder false, Search Diagnostics false, and Move Overhead 20 ms. Verify these
advertised defaults for the existing comparison harness; explicitly set them
in the CPU sampler. The owner's GUI bundle `0.1-dev-4b8b35d` and all Phase 2
frozen executables remain intact.

Use all 12 `tests/data/openings-development.json` histories in their existing
order. Validate legality with `chess==1.11.2`; preserve full histories in the
derived UCI-position file. These are opening positions only, not representative
coverage of middlegames, endgames, or clock-managed search. Do not consume new
validation roots, run matches, retune experiments, or change defaults here.

## Fixed measurements

1. **Repeatability:** run `tools/compare_bench.py` with the same release binary
   in both roles, depth 5, seven measured repetitions, one warmup per root and
   role, Hash 64, and a 20-second per-search timeout. This is 192 searches,
   including 24 warmups. Require exact per-iteration depth, selective depth,
   nodes, score, PV, bestmove, and ponder agreement. Independently replay all
   reported PVs and ponder moves. Report per-root and aggregate timing ratios,
   medians, MAD, and order effects without treating them as confidence intervals.
2. **Symbol-build equivalence:** compare release versus optimized-with-symbols
   using the same roots, depth 5, one measured repetition plus warmup per role,
   and the same timeout. Require identical signatures for all 48 searches.
   This establishes only sampled equivalence, not a claim about symbol-build
   speed or every possible search.
3. **CPU attribution:** profile the optimized symbol build separately from
   timing runs with the macOS `sample` utility, 1 ms requested interval and
   a 120-second bounded window. Warm up all roots at depth 5 first, then search
   two depth-5 sweeps (24 searches) inside the sampling window. Keep the process
   alive until sampling ends, preserving raw stacks and per-root search times.
   Reject incomplete or out-of-window coverage. Idle/setup/waiting stacks are
   separate from active search stacks; inclusive nested costs cannot be added.
   Sample counts are approximate observations, not exact CPU-cycle fractions.

Use one search worker, with at most two resident engines for comparisons.
Stay within the ordinary 50% daytime policy. Complete compilation and tests
before timing; do not run competing engine jobs. Each timing comparison has
a ten-minute outer safety bound; preserve partial evidence if interrupted.
The CPU sampler has its own bounded window and cleanup. No scheduler is created.

## Interpretation and next checkpoint

Same-binary ratios should center near one. If drift or variability prevents
useful timing discrimination, report that limitation and propose a changed
protocol before another run; retain every run. No candidate or speed gain is
being tested in this checkpoint. Transport and process scheduling are included
in the timing harness; short searches and related opening roots limit inference.

Select one optimization based on the observed active-search cost, implementation
scope, and risk. Before implementation, fix exact search-equivalence and timing
criteria plus applicable perft/rule/reversible-state, NNUE oracle/native/scalar,
sanitizer, and UCI checks. Existing buffer-reuse work was inconclusive; a hot
NNUE frame alone does not establish that allocation caused its cost.

The sampler observes optimized stacks, where inlining can blur attribution.
Depth-limited searches do not exercise the per-node active-clock path, so they
cannot exclude a clock-management bottleneck. CPU share suggests where to
investigate; neither it nor throughput establishes an Elo improvement.

Keep README, the roadmap, handover, and validation current. Record the result
and proposal in a versioned report, keep raw artifacts locally, and commit
tested work on `main`. The owner publishes manually. A measurement-only
checkpoint does not establish a new engine release.
