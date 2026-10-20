# Clock-boundary diagnostic — October 20, 2026

Status at declaration: no measurements collected. This is the bounded
clock-reliability checkpoint before Phase 4D.6, following the
[84-flagfall audit](../reports/2026-10-19-clock-diagnosis.md). It does not qualify
LMR or change the historical campaign decision.

## Question and fixed scope

Separate position reconstruction, command receipt/startup, search/deadline
observation, worker joining, final accounting, reply formatting/flushing, and
the reader's observation. Do not change reserves, pruning, or match accounting
to obtain a favorable result. A short replay cannot establish the cause of
every historical flagfall or prove that clock losses are eliminated.

Use exactly two complete historical position histories, extracted with legal
replay and source hashes into
`results/clock-boundary-20261020/selected-cases.json`:

- `late-receipt`: shard 1, game `p000001-1`, baseline, ply 77. Historical charged
  time 876.721625 ms, reported time 840 ms, hard budget 840 ms.
- `internal-overrun`: shard 8, game `p000006-1`, baseline, ply 93. Historical
  charged time 692.014166 ms, reported time 669 ms, hard budget 600 ms.

Selected-case SHA-256:
`135ce4f7f967a73be8d48c1bdd77033398208ad8a84da98036d621f7af169a2e`.
Both belong to the saved Phase 4D.2 campaign. They are exposed diagnostic roots,
not held-out strength-test openings.

## Fixed matrix and limits

Exactly **32 searches**, one attempt per cell:

`2 histories × 2 clocks × LMR off/on × position readiness barrier off/on
× serial/four concurrent engines`.

Both sides receive 600 or 2,000 ms and a 600 ms increment. Each cell starts a
fresh process/cache, `Threads=1`, `Hash=64`, `Move Overhead=20`, classic time
management, no pondering, no Syzygy, MVV-LVA ordering, and all other experimental
search options off. Load the pinned `nn-1a298aa575a0.nnue` before any measurement.

Without a barrier, send the full `position` history immediately followed by
`go`. With a barrier, send `isready` and await `readyok` between them. The four
concurrent cells share a clock/barrier setting and synchronize before `position`;
they cover both roots and LMR settings.

Maximum four active search workers, below the 50% daytime ceiling on the
detected 18-logical-CPU host. Reserve at least 3 GiB for the four processes and
verify it fits the allowed memory budget. No other benchmark/search workload
during measurement.
Total deadline 300 seconds including cleanup; startup 30 seconds per process,
search/trace receipt 10 seconds. No retry, resume, outlier removal, or overwritten
output. Record every attempted cell and failures. This is a short diagnostic,
not an authorization to start a new long match or create a schedule.

## Measurement boundaries

Build with `CLOCK_TRACE=1`; its separate `-clock-trace` build directory prevents
replacement of ordinary or stable GUI binaries. Ordinary builds compile out
the instrumentation. The engine emits one versioned trace **after** flushing
`bestmove`, while retaining the output lock. The trace carries integer
steady-clock nanoseconds and the exact final reported-time accounting sample.
The first leader hard-stop observation has its own stamp; zero means no such
observation. No additional clock reads are inserted at ordinary visited nodes.

The Python reader timestamps each complete line before its consumer queue.
Record host send-before, send-flush-return, reader receipt, and consumer receipt.
These are user-space observations, not kernel pipe arrival timestamps.

Three `clockping` round trips before and three after each search bound the
host-minus-engine clock offset. Intersect the six causal intervals
`[host_send - engine_stamp, host_receive - engine_stamp]`; reject inconsistent
intervals. Do not assume matching epochs or report half the RTT as a measured
one-way delay. Preserve interval uncertainty, including negative lower bounds
where post-flush sampling can occur after reader receipt.

Validate all fields, event identity/order, reported-time arithmetic, final
statistics, legal PV/bestmove/ponder, process exit, reader drainage, exact
options, source/binary/network hashes, and complete matrix coverage. Await the
post-bestmove trace before another command; it is outside the charged reply.

## Correctness and decision

Before measurement, test the trace schema, corrupt-evidence rejection and UCI
lifecycle. Compare parent/normal/trace fixed-depth decisions, scores, PVs and
nodes with fresh caches on both roots and LMR settings. Run relevant ordinary
and instrumented native/scalar/sanitizer checks. Freeze executable, protocol,
runner and selected-case identities before the matrix.

An independently reviewed report must distinguish measured stages from
unresolved scheduling/transport effects. If a reproducible engine defect is
identified, make a narrow repair with regression coverage and an explicit
follow-up comparison. Otherwise close this diagnostic honestly and specify the
smallest remaining operational check needed before a **fresh, separately
declared** qualification of existing LMR. Do not add broader reductions first.

Preserve the owner's modified `tools/batch_positions.py`, all frozen comparison
assets, and GUI snapshots `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017`, and
`0.1-dev-phase4b-20261018`. No GUI snapshot is being retested here.
