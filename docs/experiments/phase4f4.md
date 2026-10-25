# Phase 4F.4 — combined-policy diagnostic screen

Declared October 25, 2026, before searches. Parent: `8892b03`; engine source
baseline `ccb66a4`. This is a bounded development diagnostic, not a strength
qualification or another attempt at Phase 4F.3's exposed puzzles.

## Question and fixed scope

Why can all-on complete less tactical work despite the owner's faster starting-
position result? Separate observations about node mix, active selective branches
and worker participation before choosing one result-preserving implementation
candidate. A counter does not measure function cost, and fewer nodes are not Elo.

Use **all 15 existing roots** in `tests/data/countermove-profile.json`. No puzzle
positions, fresh match openings, selected best-looking subsets or replacement
runs. Preserve full-history opening commands and the composed FEN roots' existing
missing-history/reachability limitations. The 512-game campaign remains parked.

The initial screen is 15 roots × two repetitions × four configurations:
current defaults / all-on, each at Threads=1 and Threads=8. Rotate configuration
order between roots and reverse it on the second repetition. Each search uses
one fresh process, a cleared table/history, `go movetime 1000`, Hash=64 MiB,
Move Overhead=20 ms, classic timing, Ponder=false, Syzygy disabled and the pinned
SF19-compatible network. All-on uses the complete eight-option recipe already
recorded in MANUAL_TESTING; conservative LMR stays enabled in both packages.
Both use the **same frozen Phase 4F.3 executable** (SHA-256
`5714cd8ab2e0a4a721922fa5e02881329e8d865bff87829d8c20fb82302aa947`).

Search Diagnostics is enabled in every case. Its extra counters and different
node mixes prevent interpreting observed NPS as a pure implementation-cost
comparison. Completed iterations, nodes, SEE calls, selective probes/cutoffs,
TT events and worker-node shares are descriptive evidence. Only worker zero's
completed PV/depth is reported; helper work is not extra depth or independent
proof. Check aggregate counters separately from leader-only iteration counters.

## Bounds and evidence

The default screen contains 120 searches, about two minutes of search plus
startup; cap the whole run at 300 seconds and any search at five seconds.
This modest diagnostic fits the daytime policy on the checked 18-CPU/64-GiB
host. Run one engine at a time, at most eight active workers and a two-GiB
reservation. Recheck the current CPU/memory policy during the run and abort
on excessive clock/monitor gaps, time limits, changed inputs or illegal output.
The cap does not authorize a long test or bypass the overnight policy.

The owner confirmed LM Studio inference is paused for these short profiles.
Keep Automatic power mode and AC power unchanged; record these conditions.
A resident model can still consume unified memory. No power settings or other
applications will be changed by the runner. Require an explicit quiet-host
assertion for timing; user confirmation is not continuous load/thermal telemetry.
Do not compile or run another profile concurrently. Idle-sleep prevention is
foreground-only; no automatic schedule is created.

Retain source/binary/network/corpus hashes, applied UCI options, raw commands and
received lines, wall/monotonic receipts, PID/exit code and partial failure output.
Independently replay all PV/best/ponder moves. A failed/partial attempt stays
visible and never silently replaces a completed sample. Reject existing output
paths. Recheck input identities after completion.

## Decision boundary

Use this finite screen to select one concrete implementation candidate, not to
promote pruning defaults or infer a cause solely from correlation. SEE attack
calculation and temporary quiet-history allocation are source-review hypotheses,
not established causes. If the data does not distinguish them, say so.

A chosen implementation must preserve move ordering, legal state, scores, learned
history and diagnostic counters at deterministic limits. Validate with focused
independent reference checks, relevant engine/sanitizer tests and separate
uninstrumented parent/candidate comparisons. Keep performance observations and
exact-result checks separate. Retain regressions; no threshold tuning against
the 39 mate puzzles. Eight-thread timing cannot require identical search trees.

Any search-policy default change still requires predeclared strength evidence.
No Elo, v0.1 release, multithreaded strength gain or resolution of Phase 4F.3's
mate-report deficit follows from this short screen alone.
