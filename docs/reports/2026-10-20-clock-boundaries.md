# Clock-boundary checkpoint — October 20, 2026

**All 32 diagnostic searches completed on time. No historical delay was
reproduced, and no clock-policy repair or strength gain is claimed.**
The normal release is byte-identical to its parent. This closes the bounded
diagnostic before Phase 4D.6; the historical reliability blocker remains open.

## What was implemented

An optional `CLOCK_TRACE=1` build records position setup, go receipt, worker
startup, search completion, joining, final accounting, reply preparation and
bestmove write/flush. It emits the trace after flushing `bestmove`, with a
versioned schema. A diagnostic-only `clockping` command permits bounded clock
epoch calibration. Ordinary builds contain neither diagnostic interface nor
additional timing reads.
Their output directory remains separate from the diagnostic executable.

The original bounded replay tool saves raw sends, flush returns, reader receipts,
clock calibration, legal-PV verification and exact artifact identities.
The [predeclared protocol](../experiments/clock-boundary-20261020.md) fixes two
historical full-move histories, 600/2,000-ms clocks, LMR off/on, position readiness
barrier off/on, and serial/four-engine load. Each cell uses a fresh process,
Threads 1, Hash 64, a 600-ms increment, overhead 20, classic time management,
the pinned network, and no other experimental search options or tablebases.

The historical examples had 36.72 ms and 23.01 ms between reported and charged
time; the second also exceeded its internal deadline by 69 ms. This experiment
replays their histories on the current build under the stated clock matrix.
It does not recreate the original eight-process campaign or match-runner load.

## Observed result

The run took **18.973 seconds**, October 20 at **17:44 Helsinki**, with no
retries, exclusions, failed cells, process errors or changed input hashes.
Maximum active search workers: four, within the detected 18-CPU host's daytime
limit of nine. Memory reservation: 3 GiB against 64 GiB installed memory;
this is admission accounting, not a measured RSS or operating-system cap.

The independent raw audit passed: all 32 cells, 20 resource admissions,
192 calibration pings, 220 iterations, 990 legal PV plies, 64 legal bestmove/
ponder plies, 168 selected-history plies, 38 source/binary/network/owner hash
checks, and 32 clean exits. The four-process groups genuinely overlapped for
360–465 ms; their go-command send spread was 0.054–0.139 ms.

| Observed interval | Maximum |
| --- | ---: |
| Full position-history processing | 0.160791 ms |
| Go receipt to worker startup | 0.058500 ms |
| Worker startup to Search API entry | 0.002667 ms |
| First hard-stop observation beyond deadline, 10 hard stops | 0.002750 ms |
| Final accounted time beyond deadline, all 32 searches | 0.007375 ms |
| Final accounting to Search API return | 0.002750 ms |
| Search return to reply ready | 0.011167 ms |
| Bestmove write/flush | 0.014709 ms |
| Reader observation to consumer receipt | 0.188708 ms |

Every reader-observed reply fit its transmitted clock. The narrowest remaining
clock margin was **19.734 ms**. No-barrier go-receipt delay upper bounds were
at most **0.200875 ms**; the corresponding barrier upper bound was
**0.050625 ms**. This is consistent with position processing preceding go
receipt, but is much too small here to explain the historical delays.

Cross-process figures are intervals obtained from six ping round trips per
session, not assumed shared clock epochs or half-RTT estimates. Reader receipt
may precede the engine's post-flush sample; negative lower bounds are retained.
Instrumentation and the observer can influence scheduling. The hard-stop
timestamp is sampled after its comparison, so it does not isolate time spent
between individual node checks.

The search-return/reply-ready interval includes final reporting, result
synchronization and move formatting. Accounting/search-return includes final
hash sampling and return bookkeeping. Those combined intervals cannot be
attributed more narrowly from this record.

## Validation and identities

- Ordinary release: position/perft, UCI, resource, Search API, time policy and
  15 existing clock-probe tests passed.
- Diagnostic release: 23 engine-free schema, matrix, calibration, resource,
  failure and cleanup tests passed.
- Diagnostic UCI contract: 11 searches passed in release, scalar release and
  ASan+UBSan builds, covering legal PVs, timestamp arithmetic, repeated searches,
  four-thread joining, hard stops, infinite/ponder withholding, active position
  replacement, mate and the maximum accepted UCI clock. Ordinary-build
  interface isolation also passed.
- Scalar and ASan+UBSan Search API suites passed. No new TSan run or foreign
  platform execution is claimed.
- Twelve fresh-cache depth-4 searches matched the frozen parent, normal and
  trace builds exactly in iterations, scores, PVs, bestmove/ponder and nodes,
  on both histories with LMR off/on.
- The first contract-test attempt incorrectly rejected the expected empty
  Syzygy notice during setup. Its assertion was corrected before measurement;
  the failed log is retained. No engine behavior was changed for that test.

Parent commit: `e2a641fee7dc0d26f1c150628eb2254cbd7f5a01`.
Normal/parent binary SHA-256:
`eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
Measured trace binary SHA-256:
`3a84407c048c32fec840a76e81b7fe6d5f8c95b8778c641711c7dfad837935b8`.
Network SHA-256:
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

Raw protocol, checks and audits: `results/clock-boundary-20261020/`.
Frozen binaries, source copies, protocol and protected-asset manifest:
`build/experiments/clock-boundary-20261020/`. These are local ignored artifacts.
The replay command requires the archived selected-case and original campaign
evidence; the live UCI contract test only requires a built engine and network.

The owner's modified puzzle runner and all 40 protected assets remain intact,
including GUI snapshots `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017`, and
`0.1-dev-phase4b-20261018`. None was replaced or newly tested through CuteChess.

## Decision and next checkpoint

Keep normal engine behavior, overhead and all experimental defaults unchanged.
Do not infer that historical clock failures are fixed from 32 clean replies.
No full puzzle rerun is warranted for compile-time-only diagnostic changes with
a byte-identical normal executable.

Next, prepare **one fresh qualification of existing conservative LMR**, preceded
by a bounded real-match readiness check at the proposed four-active-worker
concurrency. Use the ordinary executable and existing match runner, fresh
opening pairs, explicit unchanged overhead/settings, and independent raw-event
audit. The lower concurrency is a new experimental condition, not a repair or
a reinterpretation of the failed eight-worker campaign. Any clock failure
fails readiness and keeps LMR off; retain it and investigate its measured
boundaries before a long run.

If readiness passes, declare the separate strength protocol before searching
its held-out openings, and use the ordinary overnight policy or a new explicit
owner exception. No long run or schedule was created here. Decide whether to
promote, reject or park existing LMR before broader 4D.6 reductions; 4D.7 ProbCut
and 4E portability/network tooling remain later work.
