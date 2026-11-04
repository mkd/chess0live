# Phase 4F.19 — current search combinations

Declared November 4, 2026, before any measurements in this phase. Parent checkout
`652971fce9de071bf5cb56f9a2b39e9f1180d5dd`; production engine source is unchanged
from implementation `9f8ff9f`. The owner authorized this next phase and freshly
confirmed LM Studio paused, AC power and Automatic mode for the short comparison.
This is a configuration diagnosis, with no engine implementation/default change.
No previous-engine code, runners or testing assets are imported.

## Fixed initial question and inputs

Determine how the current optional-off, accepted-default and all-experiments
profiles differ after the same requested thinking time. The older all-on package
does not settle the current combination; features can interact. Nominal depth,
total nodes, NPS and scores alone do not establish playing strength or optimal
moves. There is no expectation that all-on must win this diagnostic.

Use one existing binary for every cell, without rebuilding or modifying it:

| Input | SHA-256 |
| --- | --- |
| `build/experiments/phase4f18/candidate/chess0live` | `8824e8588328ba8ef3f768247f4c68604eec0c1ff22b4655b5b39d7be8270d5e` |
| `networks/nn-1a298aa575a0.nnue` | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| `tests/data/countermove-profile.json` | `afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f` |

All fifteen existing mixed roots retain their original position/history commands
and order. No root is chosen or discarded using these results. Freeze the runner,
independent auditor, protocol, applicable source/tool/dependency identities and
interpreter identity before execution. Preserve the current environment receipt;
this is a declared input set, not a claim to freeze the entire operating system
or all dynamic dependencies. Keep the prior phase's source/build archives intact.

## Exactly three profiles

| Search option | optional-off | default | all-on |
| --- | --- | --- | --- |
| Late Move Reductions | false | true | true |
| Deep Quiet Reductions | false | false | true |
| Capture Ordering | mvv-lva | mvv-lva | see |
| Countermove Ordering | false | false | true |
| Continuation History | false | false | true |
| Null Move Pruning | false | false | true |
| Reverse Futility Pruning | false | false | true |
| QSearch SEE Pruning | false | false | true |
| QSearch Delta Pruning | false | false | true |
| ProbCut | false | false | true |
| TT Move Hints | false | false | true |

The common settings are Threads 1, Hash 64 MiB, the pinned network, Move Overhead
20 ms, Time Policy classic, Ponder false, Search Diagnostics false, empty Syzygy
path, SyzygyProbeLimit 0 and SyzygyProbeDepth 1. Preserve core NNUE, PVS, aspiration,
contextual score TT, killers, ordinary history, quiescence and check extensions.
Optional-off differs from accepted defaults only in LMR. Capture Ordering and
Time Policy are enums; literal everything-on is undefined. Equal Hash preserves
score-table geometry, not total memory: all-on adds history/hint allocations.

## Finite execution and host guard

Run **45 searches in 45 fresh processes**, exactly one per root/profile. Each
search is `go movetime 5000`, with no requested depth or node cap, no warmup and
no retained state from another cell. The engine's normal 20-ms overhead reservation
still applies. Rotate `(optional-off, default, all-on)` left by root index modulo
three, so each profile occupies each execution slot five times. Fresh processes
retain within-search learning but do not test cross-search history reuse.

One active search worker and one resident engine are allowed. Reserve at least
2 GiB under the detected daytime 50% / nighttime 80% policy; this conservative
reservation is not an observed RSS or a hard OS utilization limit. Search/setup
budget is 300 seconds, individual search-response bound 10 seconds, with bounded
cleanup/evidence publication afterward. Expected requested search totals 225
seconds; allow roughly five minutes for the initial measurement. No competing
build, engine test or benchmark runs during the measurement.

Before timing, require the owner's fresh quiet-host confirmation plus actual AC
and Automatic-mode evidence. Capture power/mode before and after every cell,
and have the external supervisor sample AC status during searches (about once
per second), requiring no gap above three seconds between consecutive samples.
Record raw host samples and times. Stop on a detected power/mode
change, unavailable required host observation, protocol/legality/process failure,
input drift or deadline. Preserve partial output; do not retry or replace cells.
Do not stop based on an unfavorable depth, move or score. There is no sample
extension, tuning, automatic schedule or game campaign in this initial run.

Track a sleep inhibitor, runner and every observed engine identity; record
before/after host/thermal evidence and sleep/wake events. Sleep assertions are
not system sleep. Record both wall and monotonic times to expose interruptions.
Sampling cannot prove constant host load or exclude every sub-second power event.
The supervisor must clean up only its own matching process identities on failure.
After completion or failure, confirm all experiment-owned processes have exited
using receipts and the OS, handling PID reuse by identity. Release LM Studio
immediately after cleanup is confirmed, before longer analysis or documentation.

## Evidence, independent audit and decision

Preserve complete commands/readiness/search/shutdown transcripts, timed events,
PIDs, exit status, EOF/late-output checks and partial output on failure. Explicitly
validate all expected options and advertised defaults, all fifteen root histories,
every completed iteration, legal PV/best/ponder moves, exact score formatting,
zero tablebase hits, absence of diagnostics, resource settings and source pins.
Matching enabled-profile search results are not required. Preserve every changed
score, move and PV, including differences at common nominal depths.

Report all three pairwise comparisons per root, completed depth/seldepth, total
and completed-iteration nodes, unfinished iteration work, observed elapsed time,
reported NPS, displayed score, PV, best move and ponder. Quiescence-only nodes
and internal integer scores are unavailable in this uninstrumented run; retain
them as unavailable rather than infer them from normalized cp. Describe medians
and counts without confidence intervals or a strength/performance acceptance gate:
one observation per exposed cell is only a diagnostic.

An independent engine-free auditor replays raw evidence without trusting the
producer's aggregates. Check complete matrix/order, source identities, options,
legal output, per-engine exits, timings, host and cleanup records. Never overwrite
an existing audit. If host comparability fails, retain a nonpassing qualification
decision while still reporting independently validated descriptive observations;
do not hide partial evidence behind an early host-check failure.

The checkpoint ends with a concrete diagnosis and a proposed next experiment.
If a profile shows useful differences, separately freeze leave-one-out work to
identify interactions; do not tune this package on its observed cells. Removing
LMR also disables Deep Quiet Reductions. Delta precedes SEE pruning; their
savings cannot be added independently. Ordering changes affect LMR eligibility.
Any later retained-state study, tactical suite or match needs its own bounded
scope and host window. No implementation selection guarantees a gain. Historical
six Phase 4F.13 time forfeits remain unresolved before strength qualification.

Record the outcome, all failures and limits in roadmap, handover, validation and
a dated report; update practical tool documentation and commit tested changes
locally on main. Preserve the owner's batch-runner edit, README introduction,
stable GUI `build/test-baselines/0.1-dev-4b8b35d/`, earlier evidence and historical
normal-release digest caveat. No default promotion, release, push or future run is
authorized by a promising initial diagnostic alone.
