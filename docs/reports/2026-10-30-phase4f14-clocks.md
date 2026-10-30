# Phase 4F.14 — bounded clock diagnosis and referee responsiveness repair

**Complete:** a reproducible match-runner responsiveness defect is repaired.
All eight short traced searches returned on time under the owner-requested
LM Studio load. The six historical Phase 4F.13 forfeits remain unexplained;
neither general clock reliability nor a strength gain is established.

The [declared scope](../experiments/phase4f14-clocks.md) fixes this finite
checkpoint. Parent: `6d61f8347f712473250fafc164298734672de80a`.

## Reproduced defect and repair

`play_game` previously called `Board.outcome(claim_draw=True)` directly on the
event loop shared by other games. Claimable-draw checks can replay history and
candidate moves. A controlled regression queues another game's ready protocol
callback during adjudication: the original implementation prevents that callback
from running until the adjudication gate's watchdog releases. Virtual clock
observations distinguish the delayed receipt without using wall-time thresholds
as the pass criterion. `adjudication-before-v2.log` retains the pre-fix failure.

The same adjudication now runs in a worker thread, awaited with the existing
cancellation-safe cleanup helper. This game's board remains exclusively owned
until the worker finishes restoring it. Cancellation cannot race cleanup against
temporary board moves; exceptions still produce a recorded runner failure.
Draw rules, move-clock boundaries, increment handling and engine policy do not
change. Worker threads still share Python's GIL and cannot eliminate every
process/scheduling stall.

Three new regressions cover callback progress, cancellation/board restoration
and error propagation. The full match suite passes **43/43**, using fake UCI
processes only. Independent static review found no blocking issue. This proves
a responsiveness repair, not that adjudication caused the six historical losses.

## Saved evidence and resource-call check

Bounded inspection preserves all six forfeits and their raw clocks. Every final
game-finish stamp is 1.486–4.114 ms after a resource observation; the first paired
failure follows 120.160 ms without recorded events across the four active
protocol streams. Two isolated failures follow another game's repetition ending.
These are correlations: resource stamps follow probe completion, finish stamps
follow cleanup, and callback stamps are not kernel-arrival timestamps.

An eight-observation, engine-free check of resource request construction and
physical-memory calls under the requested host condition did not reproduce a
long delay: request construction was at most 0.590 ms and the physical-page
query at most 0.011 ms. No resource-probe change was justified. Receipts retain
source hashes and the original analysis plus a separate correction of two prose
numbers; its structured case data were already correct.

## Short traced-engine result

The single diagnostic ran October 30 at **22:12:27–22:12:28 Helsinki**. Its
measured execution/cleanup duration was **1.186 seconds**. The owner requested
LM Studio running because the next quiet window was unavailable for 72 hours;
this is a declared load condition, not continuous OS load telemetry.

Four exposed positions ran serially, then the same four ran concurrently in
fresh processes: **8/8 complete**, zero late replies, zero failed sessions,
eight clean engine exits and no input drift. Settings: 170-ms clocks, 150-ms
increment, 20-ms overhead, classic policy, Hash 64, Threads 1, conservative LMR
on and other experiments/ponder/tablebases off. The detected host budget allowed
nine daytime workers; this diagnostic reserved four workers and at least 3 GiB.
The owner's LM Studio workload was concurrent, not controlled by this reservation.

| Observation | Result |
| --- | ---: |
| Minimum remaining clock margin | 19.858500 ms |
| Maximum outgoing-go to callback receipt | 150.141500 ms |
| Maximum position reconstruction | 0.014625 ms |
| Maximum go receipt to worker startup | 0.045084 ms |
| Maximum observed hard-stop overshoot | 0.003417 ms |
| Maximum calibrated callback-after-flush upper bound | 0.128584 ms |
| Maximum consumer delay after callback | 0.272083 ms |
| Actual four-way search overlap | 94.771917 ms |
| Four-engine go-send spread | 0.188750 ms |

Independent raw replay verified **48 calibration pings, 42 iterations, 156 legal
PV plies, eight legal bestmoves and eight legal ponder suggestions**, plus all
20 diagnostic input identities. Calibration retains causal offset intervals;
negative lower bounds are not silently rounded away. The protocol uses the
production `start_engine`, `RecordingProtocol` and `timed_play` paths with bounded
in-memory logging. It does not run `play_game` adjudication, full production
persistence, the periodic campaign supervisor or long-lived game histories.
Its clean result therefore does not independently qualify the adjudication fix
under real matches or explain the historical failures.

## Validation, failures and preservation

- Match regressions: **43 passed**. The initial new-test setup omitted required
  settings; its separate failed log is retained and is not defect evidence.
- Short-clock tool: **11 engine-free checks passed**. An initial synthetic check
  exposed a missing duplicate-calibration rejection, repaired before any real
  diagnostic. Independent review then found cleanup receipts could be skipped
  by deferred cancellation; the repair and repeated-cancellation regression
  passed before the single eight-search attempt. No data run was repeated.
- Existing trace UCI contract: **11 diagnostic searches passed**, plus ordinary
  build interface isolation. These are correctness checks, separate from the
  eight timed observations; no scalar/sanitizer/foreign-runtime rerun is claimed.
- Independent raw audit and runner review passed. All eight recorded engine
  PIDs were absent in a separate OS check; runner exit code was zero.
- All **569 protected files**, **18 engine source/Makefile identities** and the
  exact README introduction match the pre-phase record. Normal release,
  qualification binaries and stable GUI **`0.1-dev-4b8b35d`** remain intact.
  The separately disclosed older normal-release digest discrepancy remains
  unresolved; this phase preserves its current recorded bytes only.

Only a new isolated clock-trace executable was built. Engine sources, NNUE
arithmetic, search, clock allocation, overhead and default options are unchanged.

| Evidence | SHA-256 |
| --- | --- |
| Diagnostic executable | `cf1080e141fcfdc52a8ef1313a2e677576dcabadeae608d140a98e31c3ff4f06` |
| `short-clocks.json` | `dd6723e92d7fb5a4d595c6f1f2973d76d370f92d81735c450eccd5797a7c4f19` |
| `diagnostic-audit.json` | `921a8129c7da0a68eb25add27ff2ab7de1bff0b8716e3633858252ab7ad5cc81` |

Logs, before/after preservation, raw observations, analysis scripts, audit,
review and OS cleanup receipts are retained under
`results/phase4f14-clock-20261030/`. Practical commands are in the
[README](../../README.md). Documentation validation and local commit receipts
complete this checkpoint; the owner handles pushing.

## Decision and next checkpoint

Retain the narrow referee responsiveness repair and diagnostic tool. Close this
finite investigation with the **historical cause unresolved**. Keep all previous
match decisions unchanged; no discarded forfeits, replacement games, sample
extension, new campaign or schedule follows.

Next proposed implementation: **Phase 4F.15, one isolated verified-null-move
efficiency hypothesis**, starting with eligibility and verification/re-search
costs against the current LMR-on baseline. Development/correctness work can
proceed while LM Studio is active. Controlled performance or strength testing
requires a fresh suitable window and a separately declared protocol; a future
match must also address the remaining clock-reliability limitation. No quiet
window or game run is automatically scheduled for 72 hours later.
