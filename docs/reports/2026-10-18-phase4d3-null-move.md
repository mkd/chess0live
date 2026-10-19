# Phase 4D.3: verified null-move checkpoint — October 18–19, 2026

Status: implementation, native/scalar/ASan+UBSan/ThreadSanitizer checks and
the predeclared 24-search screen are complete. `Null Move Pruning`
remains **false** by default. No strength or speed improvement is claimed.
Implementation and validation tooling commit: `51c426a` (parent `6679199`).

## Implementation

The [fixed development protocol](../experiments/phase4d3-null-move.md) specifies
one independently authored candidate. Eligible interior non-PV nodes first
try a reduced fictional pass. A fail-high must survive a second, reduced search
of legal moves on the restored position before returning beta. Checks, special
score windows, sparse/limited material, advanced pawns, repeated positions and
the late rule-50 clock exclude the probe. Verification and material guards
reduce risk; they are not a general proof against zugzwang or missed tactics.

Both speculative subtrees exclude nested null probes, LMR, tablebase access,
transposition reads/writes and ordering learning. Only real verification uses
game-history repetition and rule-50 draws. Speculative moves never enter a
reported PV, and direct null cutoffs are not stored at the original depth.
Ordinary ancestor results may still depend on this heuristic. Policy changes
clear cached state; worker-local diagnostics aggregate after joins. Default
search policy, evaluation math, and time management are unchanged.

## Checks and evidence boundaries

Native, scalar and ASan/UBSan full regression suites passed. Each passed 76 new independent
referee-backed UCI cases, including positive probe/verification/cutoff activity,
diagnostics parity, legal PVs/bestmoves/ponders, signed mates, special moves,
rules, immediate stop, pondering, policy changes and one/four-worker accounting.
The independently composed corpus contains 20 positions and their color
reflections; it is exposed correctness material, not an optimal-play oracle.

Null-state tests passed in native, scalar and ASan/UBSan modes: 63 roots,
202 legal children after a pass and 1,045 incremental/full-refresh NNUE
comparisons per build. They include legal/pinned/unavailable en-passant hashes,
both colors, captures, castling, promotions, counter saturation and exact undo.
The evaluator's format and arithmetic are unchanged; no new SF19 stage-oracle
qualification is claimed by these incremental consistency checks.

Direct API tests passed in all four build modes. Deterministic entry
interruptions at 33,624 nodes (first null probe) and 33,667 (first verification)
published no completed speculative outcome; subsequent default searches matched
fresh state exactly. Node caps, expiry, external stop, real history and helper
joins were also checked. Native execution additionally used the existing real
Syzygy fixtures and checked repetition precedence. Other build modes have no
new real-tablebase execution claim unless separately recorded below.

The phantom-history case tests an ordinary root boundary at depth three; it
does not exercise an internal speculative repetition collision. Sparse fixtures
combine multiple exclusions; individual guard boundaries have separate pure
policy tests and source review. Mate/tablebase cases preserve behavior with the
option enabled but do not force a null-derived special-band score. Targeted
interruptions cover probe/verification entry, not every possible deeper stop
or interleaving. No general tactical/zugzwang immunity is established.

Two independent source reviews found no blocking defect in mode propagation,
PV cleanup, score bands, cancellation, cache invalidation or counter aggregation.
Exceptions discard the local position and reset worker state on reuse; they
do not transactionally unwind every intervening legal move.

The profiler's 19 synthetic tests cover corrupt transcripts, incomplete cells,
parent mismatches, changed-score reporting, resource limits and clean shutdown.
Pre-search review found that the shared UCI client's close method leaves queued
shutdown output unread. The profiler now drains and preserves it locally,
requires a closed reader, one final EOF and exit zero, and rejects unexpected
late output. The frozen shared client was not changed. This repair happened
before any screen search; no failed or unfavorable sample was replaced.

The initial ThreadSanitizer direct API suite passed, but its UCI activation
search exceeded the harness's 30-second response timeout at 250,000 nodes.
The original failure remains in `full-thread-sanitize.log`. A separate
`--activation-timeout` controls only the two fixed-node activation/parity
checks for instrumented builds; the node/depth limits and all stop, pondering
and clock-response waits remain unchanged. The retry uses 180 seconds and is
recorded separately; this does not amend any match or strength protocol.

The retry passed all 76 UCI cases with no reported race; the existing 43-case
parallel UCI suite also passed under ThreadSanitizer. Thus all four builds
passed the new UCI cases and direct API checks. Native defaults were rerun
after the harness adjustment and passed. Make selects 180 seconds for this
activation allowance in `MODE=thread-sanitize`, 30 seconds otherwise; it remains
overridable through `NULL_MOVE_ACTIVATION_TIMEOUT` within the CLI's 1–300 range.

All execution evidence here is local macOS ARM64. There is no new foreign-target
execution, GUI visual validation or proof of every concurrent schedule.

## Frozen development screen

The parent is the preserved Phase 4D.1 executable, SHA-256
`bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f`.
Candidate SHA-256:
`d0617575e7ece0dc3c38d4f44f33b6bc93adad8cf947a129af6dec137246b530`.
The network is the unchanged pinned `nn-1a298aa575a0.nnue`.
`tools/profile_null_move.py` declares 24 single-worker depth-6 searches:
12 parent/off searches first, then 12 off/on searches, three exposed opening
histories and separate cold/warm state. It preserves raw protocol, settings,
resource decisions, intermediate score/PV changes and artifact hashes.

All 24 searches completed. The 12 parent/off searches matched every declared
iteration and final signature. The six off/on pairs retained identical final
moves and scores; every reported per-depth score and PV also matched.

An independent parser audited all 12 process sessions and 144 completed
iterations, replayed 608 legal PV plies plus 48 bestmove/ponder plies, and
recomputed every comparison from raw output without importing the profiler's
validation functions. `independent-audit.json` records the passing result and
its separate script/hash. It also checked all 13 profile assets, 23 source pins,
27 protected artifact pins, and the running campaign's 10 assets/18 sources.
No engine was run and no held-out campaign positions were parsed by this audit.

| Root | Cold off nodes | Cold on nodes | Warm off nodes | Warm on nodes |
| --- | ---: | ---: | ---: | ---: |
| Initial position | 57,487 | 49,232 | 5,302 | 5,634 |
| Sicilian history | 352,925 | 281,328 | 328,178 | 341,407 |
| Queen's Gambit history | 269,238 | 237,142 | 18,628 | 26,468 |
| Total | 679,650 | 567,702 | 352,108 | 373,509 |

Cold-search node work fell **16.47%**; warm-search work rose **6.08%**. All three
roots used fewer cold nodes and more warm nodes. This is mixed development
evidence on three exposed opening roots, not a broad efficiency or strength
result. No parameter was changed or sample replaced after observing it.
There is no timing interpretation: the frozen Phase 4D.2 LMR campaign ran
concurrently. Node reduction alone cannot qualify this candidate for default use.
Default-off elapsed-time overhead is also unqualified during this concurrent
workload; exact search parity is not a runtime-performance measurement.

## Reproduction and preserved work

Raw local evidence: `results/phase4d3-20261018/`. Frozen development binaries and
pin records: `build/experiments/phase4d3-20261018/`. These generated artifacts
remain excluded from Git. Run correctness suites serially within the shared
resource budget:

```sh
make -j1 test test-null-state test-null-search test-null-move
make -j1 SIMD=scalar test test-null-state test-null-search test-null-move
make -j1 MODE=sanitize test test-null-state test-null-search test-null-move
make -j1 MODE=thread-sanitize test-search test-null-search
python3 tests/null_move_uci_test.py build/macos-arm64-generic-thread-sanitize/chess0live \
  --activation-timeout 180
make -j1 MODE=thread-sanitize test-smp
```

The existing campaign retains its original frozen binary and all pinned inputs.
Short development checks share the host, with at most four test workers plus
its eight active search workers; up to two compiler jobs also fit the 14-worker
nighttime budget. This overlap must remain visible when interpreting campaign
timing. No campaign protocol, result, cutoff, or opening is changed.

Preserve GUI snapshots `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017`, and
`0.1-dev-phase4b-20261018`, the frozen Phase 3L assets, and the owner's exact
README introduction. Only normal build directories advance.

## Next checkpoint

Keep the finite result and leave the candidate opt-in. No further tuning or
new null-move match is launched at this checkpoint. Any later qualification
needs a separate quiet equal-time development check and a frozen strength
protocol; this small node screen does not establish that it is worth promoting.
The separate [Phase 4D.2 audit](2026-10-19-phase4d2-results.md), completed during
final handover, rejects LMR promotion because of candidate flagfalls despite a
favorable score. Diagnose clock behavior before another qualification. The next
implementation is **4D.4: conservative reverse futility**, kept separate from
null-move pruning. New equal-time strength qualification, broader platform
execution, and release acceptance remain open; no new long match is launched
by this checkpoint.
