# Phase 4F.14 — bounded short-clock diagnosis

Declared October 30, 2026, after the owner authorized the next phase. This is
clock diagnosis and a narrowly reproduced runner repair, not another match.
The owner explicitly requests the short diagnostic **with LM Studio running**;
the next quiet window is unavailable for 72 hours. Record this as a loaded-host
condition, not a quiet-host declaration or a performance comparison.

## Questions and finite exit

Separate engine deadline observation/output from the match runner's observation
of a complete reply. Preserve all six Phase 4F.13 forfeits and its failed
operational qualification. Neither simultaneous failures nor a separately
reproduced runner defect establishes their historical cause.

First, use deterministic engine-free tests to reproduce cross-game callback
blocking during synchronous draw adjudication. A narrow off-loop repair must
preserve board ownership through cancellation and propagate adjudication errors.
The complete match regression suite must pass. Python worker threads still share
the GIL; this change cannot promise scheduling immunity.

Then run the fixed eight-search diagnostic below once. Close with its complete
evidence and limitations whether replies are on time or late. Do not extend,
repeat, replace failed cells or tune clock reserves to obtain a pass. If the
historical cause remains unresolved, say so and define the next checkpoint.
No strength run, automatic schedule or default promotion is authorized here.

## Fixed real-engine diagnostic

Use unchanged current engine sources with the existing `CLOCK_TRACE=1`
instrumentation in a new `build/experiments/phase4f14/clock-trace/` directory.
Preserve normal builds, all match binaries and stable GUI `0.1-dev-4b8b35d`.
Record parent revision, source/binary/network hashes and the diagnostic script.

Exactly four exposed positions, each in a fresh process:

1. Initial position.
2. `e2e4 e7e5 g1f3 b8c6`.
3. `d2d4 d7d5 c2c4 e7e6 b1c3`.
4. `c2c4 e7e5 b1c3 g8f6 g1f3 b8c6`.

Run those four serially, then the same four concurrently: **eight searches**,
not complete games. Both clocks are 170 ms with 150 ms increment, overhead
20 ms, classic policy, Hash 64 MiB and Threads 1. LMR is on; experimental search
options, pondering and Syzygy are off. Use the pinned `nn-1a298aa575a0.nnue`.
These are diagnostic positions, not strength-test openings or a reproduction
of the original long game histories, warm caches, long-lived runner memory or
the full campaign supervisor's periodic resource observations.

Use the real `match.RecordingProtocol` receipt boundary and `timed_play` path,
with a diagnostic protocol extension for existing trace/ping records. Raw
protocol records use bounded in-memory storage during the search. This does
not exercise `play_game` adjudication or the full production persistence path;
the deterministic regressions separately validate the adjudication repair. Three
clock pings before and three after each search bound the host/engine clock
offset; never assume a common epoch or infer one-way delay from half a round
trip. Retain raw sends/receipts, ordered engine stamps, legal bestmove/PV checks,
clock margin, interval uncertainty, actual concurrency and process cleanup.

Maximum four active search workers/four resident engines, at least 3 GiB reserved,
subject to the normal detected host budget. The owner-authorized LM Studio
workload is concurrent and not controlled or included in a hard utilization cap.
No build, other chess benchmark or test suite overlaps the measured searches.
Whole diagnostic watchdog: 180 seconds including bounded cleanup. Preserve
partial evidence on failure and never overwrite an existing output.

## Interpretation

Engine-reported elapsed time ends before final reply delivery. Trace stamps can
locate engine-side intervals; receipt delay also includes scheduling, transport,
Python/GIL and event-loop effects. User-space stamps are not kernel arrival
timestamps. A clean eight-search sample cannot prove reliability, explain the
historical six failures or establish any Elo/performance change. An induced
adjudication stall demonstrates susceptibility, not historical incidence.

Record one decision, update roadmap/handover/validation and the practical tool
instructions, validate documentation and commit tested changes locally on main.
The owner handles pushing. Search, NNUE arithmetic, time allocation and default
options remain unchanged in this phase.
