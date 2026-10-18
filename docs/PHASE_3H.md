# Phase 3H: clock diagnosis and command-time accounting

Started October 18, 2026 from `8f23d7e`, after the completed Phase 3G audit.
This is a bounded correctness investigation, not a strength qualification.

## Scope fixed before repair

Inspect every one of the 13 Phase 3G clock forfeits and retain exact histories,
commands, timestamps, and evidence hashes. The six candidate and seven baseline
losses remain scored in Phase 3G; its decision cannot be changed by this work.
Both stable GUI bundles remain untouched. Local probes use one active search
worker and the normal 50% daytime resource budget; no match or schedule is added.

Code inspection found that the engine starts its clock inside the search worker,
after command parsing, preparation, and worker dispatch. Reproduce that gap
before repair. The initial cold-network probe is saved in
`results/phase3h-20261018/baseline-cold-go.json`: a 1 ms request took 73.474 ms
with LMR off and 68.632 ms with LMR on, while internal summaries charged about
1 ms and searched 217/219 nodes. Loading completed before search timing began.
This is a reproducible accounting defect; Phase 3G loaded networks during
readiness, so this cold-start case does not prove the cause of its losses.

## Bounded repair and checks

Carry a monotonic command-receipt timestamp from the UCI input loop to search.
Ordinary clock and movetime budgets must age during preparation and worker
dispatch. Direct Search API users can supply that timestamp; omission keeps
entry-time behavior. Ponder remains uncharged until ponderhit, infinite mode
still ignores clocks, and no-clock depth/node searches remain deterministic.
An expired request must retain a legal fallback without starting a new tree.

Do not retune soft allocation, hard multipliers, Move Overhead, LMR, or ordering.
No timer thread, platform-specific scheduler control, or claim of hard real-time
behavior is introduced. Network loading, a blocked output stream, and a
descheduled process cannot be made instantaneous by fixing accounting.

Validate with deterministic expired-receipt API tests, the cold-go UCI regression,
and existing native/scalar/sanitizer correctness and lifecycle checks. Replay
all 13 final histories once per LMR mode with the original clocks, separately
on the frozen baseline and repaired executable, using fresh tables and readiness.
Enable diagnostics for these 52 bounded probes and check legal best moves/PVs,
reported limits, elapsed time, and failures. These are exposed diagnostic roots
with fresh search state, not reproductions of the full matches or strength data.
Retain every result; do not rerun only failures until they disappear.

The checkpoint must distinguish a verified accounting repair from unresolved
host/transport stalls. If the historical flagfalls cannot be reproduced, report
that explicitly. Further reserve/allocation changes and fresh strength testing
need a separately declared experiment after this diagnosis.

## Completed checkpoint

The [October 18 report](reports/2026-10-18-phase3h-clocks.md) records the retained
repair, final native/scalar/sanitizer checks, 52 completed legal/on-time probes,
and unchanged fixed-depth search signatures. Both baseline and repaired probes
passed, so the historical losses were not reproduced. Phase 3I addresses the
remaining scheduling/transport questions; no new match is scheduled.
