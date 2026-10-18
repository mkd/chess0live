# Owner-supplied depth-10 search comparison — October 18, 2026

The owner supplied console transcripts while Phase 4C was being finalized.
These are observations, not a controlled match or qualification benchmark.
No search code, runner, positions, or historical match assets were imported from
Gargantua. The output motivates independent search-efficiency experiments.

| Reported field at depth 10 | chess0live | Gargantua |
| --- | ---: | ---: |
| Nodes | 34,711,512 | 50,904 |
| Elapsed milliseconds | 145,872 | 74 |
| NPS | 237,958 | 679,324 |
| Hashfull (permille) | 988 | 0 |
| Score (centipawns) | +26 | +73 |
| Best move | e2e4 | d2d4 |
| Selective depth | 24 | Not reported |
| Tablebase hits | 0 | Not reported |

Ratios calculated directly from those lines: 681.90 times the nodes and
1,971.24 times the reported time. Gargantua's reported NPS is 2.85 times higher;
integer time rounding means the reported node/time and NPS ratios need not
multiply exactly. The work-count gap is much larger than the throughput gap.
The first chess0live iteration includes 88 ms of elapsed setup time, which is
small relative to 145,872 ms and cannot explain the full gap.

The preceding `position`, UCI settings, selected build, hash warmness, network,
thread count, machine load, and repeated-run conditions were not supplied.
Current default chess0live uses unreduced PVS; LMR is still opt-in. The logs
alone cannot prove which options were used or attribute the entire ratio to
one mechanism. Depth numbers differ with reductions/extensions and do not
measure equal search coverage. Scores also use engine-specific evaluation
scales. No Elo conclusion follows from these two searches.

Action: [Phase 4D](../SEARCH_OPTIMIZATION_PLAN.md) follows tablebases immediately.
Start with one full-depth ordering candidate; evaluate existing LMR and later
conservative pruning separately. Require correctness and operational checks,
then fresh paired equal-time strength evidence before changing defaults. The
objective is stronger move selection in the available time, not a target node
count or nominal depth. This comparison must not become a single-position
optimization target or replace the separate development/held-out corpora.
