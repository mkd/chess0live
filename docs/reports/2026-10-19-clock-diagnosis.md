# Bounded Phase 4D.2 flagfall audit — October 19, 2026

Read-only diagnosis of the 84 saved final searches in the completed qualification. No engines were run, no frozen evidence changed, and no qualification verdict was revised. Detailed input hashes, exact go/final/bestmove lines, and per-case calculations are in `results/phase4d4-20261019/clock-audit.json` (92 saved input hashes checked).

## Findings

| Quantity | LMR candidate | Baseline |
| --- | ---: | ---: |
| Flagfalls | 19 (17 losses, 2 draws) | 65 |
| Engine-reported final time below real remaining clock | 19/19 | 63/65 |
| Hard-budget overrun, median / maximum | 0 / 15 ms | 0 / 69 ms |
| Charged clock overrun, median / maximum | 11.059 / 37.870 ms | 6.613 / 72.469 ms |
| Charged duration outside reported engine interval, median / maximum | 29.966 / 58.138 ms | 24.118 / 48.118 ms |

All 84 derived hard budgets equal the transmitted remaining clock minus 20 ms; remaining clocks range from 601.399 to 2,242.481 ms (median 619.417 ms). Seventy-six of 84 have more than 20 ms outside the integer engine interval. All final `info nodes` and `bestmove` lines have the same callback timestamp; this does not imply they were written or arrived at identical instants.

Example: shard 1, `p000001-1`, baseline ply 77 had 859.663 ms remaining, received `wtime 860`, reported final time 840 ms, and was charged 876.722 ms. Its 17.059 ms clock overrun cannot be inferred from search runtime alone. The largest engine-interval overrun is shard 8 `p000006-1`, baseline ply 93: hard budget 600 ms, final time 669 ms, charged 692.014 ms, remaining 619.545 ms. There is also genuine time beyond the intended in-engine hard budget in some records; causes are not identified.

## Timing boundaries and scope

`tools/match.py` records outgoing `go` and callback receipt completing `bestmove`. It intentionally charges transport/scheduling delay, excludes setup handshakes, and gives no free thinking time through the five-second protocol watchdog. Final game durations independently recompute exactly from raw boundary timestamps for all 84 failures. No accounting inconsistency was found in these records.

The frozen engine captures `received_at` only after reading the `go` line. `position ... moves ...` is synchronous and replays the complete supplied history; the runner sends position then go without a per-position readiness barrier. Thus any remaining position processing or delayed go receipt can be charged by the runner but lie outside engine-reported elapsed time. The final reported elapsed time is captured after worker joins, but before final hashfull retrieval, formatting and writing. The saved logs cannot separate these pre-/post-interval costs from pipe/event-loop scheduling.

Earliest depth reports provide only upper bounds on pre-receipt delay, since their own delivery may be delayed. For candidates the first-depth outside interval has median 1.333 ms while the final residual median is 29.966 ms; assuming all missing time is position parsing is unsupported. A line can be coalesced or delivered late after computation.

The engine checks hard time at every search-node visit. Deadline checks cannot interrupt an NNUE operation, move generation, output write or OS descheduling, and unwinding/terminal bookkeeping happens afterward. These records do not distinguish such paths or show a cancellation defect. The frozen/current allocation, must-stop, position handling and recording-callback implementations were compared and are unchanged apart from unrelated features.

Actual settings are Threads=1, Hash=64, overhead=20, classic timing, Ponder=false and Syzygy disabled. Most settings are advertised defaults, so python-chess omits redundant setoption commands; run manifests and handshake defaults establish them. The only role difference is LMR. `tools/uci_client.py` is a different benchmark harness and is not used by this match. Multiworker joins, tablebase I/O and ponder transition cannot explain these one-worker failures.

## Next bounded step

Before another timing-dependent qualification, predeclare a short low-clock diagnostic using the exposed saved histories and fixed 600–2,000 ms clocks. Instrument command receipt, end of search and immediately-before-bestmove timestamps in a separate diagnostic build, and record reader receipt independently; compare serial versus declared bounded contention without changing search or reserve parameters. A separate position/isready diagnostic can bound setup cost. Include one saved in-engine overrun and one ordinary-budget/late-receipt case. Preserve every attempt and do not reinterpret the failed qualification or tune to winning outcomes.

That diagnostic can identify where a clock fix belongs; the present logs cannot. Another long match or speculative overhead/default change is not justified yet. The current 20 ms reserve was insufficient for the observed charged end-to-end interval under this workload, but the logs do not establish whether concurrent development, operating-system scheduling, engine bookkeeping, runner scheduling or their combination caused it. No Elo or general latency claim follows from the selected-failure sample.
