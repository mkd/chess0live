# Phase 4F.19 — current search combinations

Date: November 4, 2026. Initial three-profile diagnostic completed and independently audited.

## Decision

**Accepted LMR explains most of the observed depth improvement. Enabling every
experiment does not produce a large additional depth jump in this screen.**
Defaults complete a higher nominal depth than optional-off on all 15 roots,
with mean paired difference +1.4 plies. All-on versus defaults is higher on five,
equal on eight and lower on two; the mean paired difference is only +0.2 plies.
The all-on median is 8 versus default 9, while its mean is 9.4 versus 9.2;
the paired counts describe the mixed effect better than either aggregate alone.

All-on changes one final move versus defaults, `gamephases-mg-04`:
`d6d5` → `f6g4`. Legality is verified; superiority is not. Keep the accepted
defaults. These are single exposed development observations, not statistical
speed, tactical safety or Elo evidence. The screen cannot explain a depth-25
claim from a different engine/position/settings, and does not support promising
such a gain merely by enabling everything.

## Completed measurement and audit

The successful run used the [original protocol](../experiments/phase4f19-combinations.md)
and the prospective [monitor repair addendum](../experiments/phase4f19-monitor-repair.md).
It ran **23:00:41–23:04:33 Helsinki**, completing **45/45 searches in 45 fresh
processes**, with **232.093 seconds** of supervision. The runner interval was
231.532 seconds; measured search intervals sum to 224.107 seconds. Requests were
5,000 ms each; the unchanged 20-ms overhead reservation gives observed replies
about 4.980 seconds after `go`.

One unchanged pinned Phase 4F.18 executable/network, all 15 original mixed roots
and histories, rotated profile order, Threads 1, Hash 64 MiB, diagnostics/ponder
off, classic time policy, and Syzygy disabled. Optional-off disables ten optional
booleans; defaults enable only LMR; all-on enables all ten and SEE capture
ordering. Core NNUE/PVS/aspiration/TT/killers/ordinary history remain active.
Equal Hash does not imply equal total memory: optional history/hint storage adds
allocations. One worker/one resident engine with 2 GiB reserved remained within
the detected nighttime budget (18 logical CPUs, 64 GiB RAM, maximum 14 admitted
workers). No build, competing benchmark, warmup, game or replacement cell ran.

The frozen independent auditor passed on its **first invocation**: complete
matrix and order, explicit options/advertised defaults, legal outputs, summaries,
source identities, host and cleanup evidence. There are **396 completed
iterations and 2,428 PV plies** in the raw records. All 45 engine exits, runner
and supervisor exits are zero; no forced cleanup, source drift or failed cell.
The audit verifies **90 per-cell endpoint host observations** and **222 external
AC samples**, maximum gap **1.071354 seconds**. Endpoints remain AC, battery
63% → 65%; Automatic mode checks pass. No actual sleep/wake event or recorded
thermal/performance warning appears. Sampling does not establish constant load
or exclude every brief change; LM Studio pause is owner-declared.

External OS verification at **23:05:09** confirms all **48 recorded identities**
gone (45 engines, runner, inhibitor and supervisor), no related survivor or PID
reuse. **LM Studio was released immediately afterward.** The existing Codex
app-server parent predates the experiment and was not touched.

The supplemental `power-evidence-audit.json` also passes: nine captures / 18 raw
streams, hashes, lengths, UTF-8 flags and every escaped view are independently
reproduced. Invalid bytes remain preserved in both assertion snapshots and the
full sleep log. Independent event filtering, including a one-second boundary
check, finds no selected or actual sleep event.

## Complete profile observations

All scores below are displayed UCI centipawns, not objective values or proof that
one move is stronger. Completed depths are nominal; pruning changes tree coverage.
No profile reports a positive final mate on these mixed development positions.

| Profile | Completed depth min / median / max | Mean depth | Total nodes | Unfinished-iteration nodes |
| --- | ---: | ---: | ---: | ---: |
| Optional-off | 6 / 7 / 16 | 7.8 | 32,453,425 | 16,128,005 |
| Accepted defaults | 7 / 9 / 18 | 9.2 | 32,422,797 | 8,888,735 |
| All-on | 7 / 8 / 18 | 9.4 | 31,379,529 | 11,565,651 |

Different-tree node counts and reported NPS are not matched-work speed results.
All elapsed times, selective depths, reported times/NPS, final ponders, complete
PVs and common-depth changes are retained in `screen.json` and independently
replayed in `audit.json`; quiescence-only nodes and internal integer scores are
unavailable. The following table includes every final move and score difference.

| Root | Depth off / default / all-on | Final moves off / default / all-on | Scores off / default / all-on (cp) |
| --- | --- | --- | --- |
| opening-01 | 7 / 9 / 9 | `e2e4` / `e2e4` / `e2e4` | 27 / 31 / 31 |
| opening-02 | 6 / 7 / 8 | `a7a6` / `a7a6` / `a7a6` | -38 / -34 / -32 |
| opening-03 | 6 / 7 / 8 | `h7h6` / `b8d7` / `b8d7` | -26 / -22 / -23 |
| gamephases-mg-01 | 7 / 8 / 8 | `g2g3` / `g1h1` / `g1h1` | 121 / 111 / 110 |
| gamephases-mg-02 | 6 / 7 / 8 | `c6b4` / `c6b4` / `c6b4` | 371 / 328 / 348 |
| gamephases-mg-03 | 6 / 7 / 7 | `e5f6` / `e5f6` / `e5f6` | 710 / 745 / 745 |
| gamephases-mg-04 | 6 / 7 / 8 | `d6d5` / `d6d5` / `f6g4` | 366 / 366 / 397 |
| gamephases-mg-05 | 7 / 9 / 8 | `a1b1` / `a1b1` / `a1b1` | 151 / 234 / 166 |
| gamephases-mg-06 | 6 / 7 / 8 | `e7f5` / `c8d8` / `c8d8` | 30 / 23 / 22 |
| gamephases-eg-01 | 8 / 10 / 10 | `f3e4` / `f3e4` / `f3e4` | 0 / 0 / 0 |
| gamephases-eg-02 | 9 / 10 / 10 | `a3a2` / `a3a2` / `a3a2` | 616 / 533 / 533 |
| gamephases-eg-03 | 10 / 11 / 11 | `e2g3` / `e2g3` / `e2g3` | 4 / 5 / 6 |
| gamephases-eg-04 | 9 / 11 / 11 | `d5b3` / `d5b3` / `d5b3` | 6 / 6 / 6 |
| gamephases-eg-05 | 16 / 18 / 18 | `c4d3` / `c4d3` / `c4d3` | -2 / -1 / -1 |
| gamephases-eg-06 | 8 / 10 / 9 | `a7c7` / `a7c7` / `a7c7` | 410 / 352 / 373 |

| Right profile versus left | Higher / equal / lower depth | Changed final moves | Changed final scores | Changed common-depth score/PV records (roots) | Changed ponders |
| --- | --- | ---: | ---: | --- | ---: |
| Default versus optional-off | 15 / 0 / 0 | 3 | 12 | 14 (7) | 6 |
| All-on versus default | 5 / 8 / 2 | 1 | 9 | 18 (9) | 3 |
| All-on versus optional-off | 15 / 0 / 0 | 4 | 13 | 12 (6) | 6 |

All-on's default-relative depth losses are `gamephases-mg-05` (9 → 8) and
`gamephases-eg-06` (10 → 9). Its five increases are one ply each, on opening-02,
opening-03, mg-02, mg-04 and mg-06. All 45 pairwise rows and every changed
common-depth score/PV are retained; none was excluded because it was unfavorable.

## Preserved prelaunch failures and monitor repair

The first attempt at **22:30:54** stopped on Battery Power at 66%, despite the
owner's ready declaration. It launched no runner, inhibitor or engine: **0/45**.
External cleanup passed at **22:35:14** and LM Studio was released. The frozen
search audit failed with `FileNotFoundError` for absent `screen.json`; the separate
`prelaunch-failure-audit.json` verifies the failure, not a passing comparison.
Its 61 frozen inputs and all original evidence remain unchanged under
`results/phase4f19-combinations-20261104/`.

The owner then instructed “go ahead with the next step.” Actual AC/Automatic
mode was observed before a new attempt. At **22:54:15**, attempt2 failed before
launch because `pmset` assertions contained non-UTF-8 byte `0xd5`; after-host and
sleep-log collection also raised decoding errors. **No engines or searches ran**.
The first power-monitor sample was never reached. Endpoint battery files report
AC at 63%. The original malformed assertion/log bytes were lost before files
could be written, so their exact contents cannot be reconstructed. External
cleanup passed at **22:55:42**; its missing-screen audit remains failed and the
separate prelaunch review verifies the engineering failure. Its 62 frozen inputs
remain unchanged in `results/phase4f19-combinations-20261104-attempt2/`.

The narrow fix adds `tools/mac_power_evidence.py`: collect raw stdout/stderr
bytes, preserve them with hashes/lengths and command receipts, and write escaped
UTF-8 text for inspection and ASCII event parsing. Nonzero exits, timeouts and
launch errors remain failures; existing evidence is never overwritten. The new
supervisor redirects only host/sleep collection to this helper. Process ownership,
cleanup, search producer, auditor and all experimental settings are unchanged.

**15 engine-free helper tests pass on their first run**, covering invalid bytes
inside/outside events, valid UTF-8, endpoint/event compatibility, malformed relevant
timestamps, failures/partial timeouts, bounded calls and no overwrite. A live,
read-only preflight reproduced invalid UTF-8 in assertions and the 7,520,891-byte
system log and passed with byte evidence preserved. That tested helper was frozen
unchanged before measurement. Original runner **21 tests** and auditor **44 tests**
are reused from unchanged versions; they were not rerun or counted as new tests.
Preserve the original auditor's earlier indentation error and corrected pass,
plus the prior supervisor ownership/cleanup tests and preparation review fixes.

## Source preservation, limitations and next step

Successful evidence: `results/phase4f19-combinations-20261104-attempt3/`, including
`freeze.json`, source copies, raw screen/supervision, endpoint and sampled host
records, raw host/log bytes, cleanup, full audit, helper tests and live preflight.
The freeze identifies parent commit `c5cd567` plus the explicitly hashed,
then-uncommitted monitor/helper/test/addendum files; it does not claim those
changes were already in that commit. Production engine source stays `9f8ff9f`.
All **66 frozen inputs**, **26 engine source files** and **1,795 protected paths**
match, including both failed attempts. The owner's `tools/batch_positions.py`
edit, README introduction and stable GUI `build/test-baselines/0.1-dev-4b8b35d/`
remain intact. The historical normal-release digest discrepancy and six Phase
4F.13 clock forfeits are unresolved. No release, rating or default promotion.

This is one observation per exposed root/profile, with no confidence interval,
objective move-quality oracle or mate proof. Fresh processes do not qualify
cross-search history benefits. The input set/interpreter are pinned, not the
entire OS or every dynamic dependency. No previous-engine code or testing assets
were reused. The small screen identifies a mixed package effect, not its cause.

**Proposed Phase 4F.20:** a separately frozen ablation of null-move pruning and
Deep Quiet Reductions in the all-on context: five profiles (defaults, all-on,
all-on minus null, all-on minus deep reductions, all-on minus both), the same
15 roots and five seconds per cell. That is 75 fresh searches / 375 seconds of
requested thinking, roughly seven minutes overall. Retain ordinary LMR in all
five profiles. Hold other toggles fixed within the four all-on-derived profiles;
accepted defaults is a separate reference with its usual additional differences.
This is a 2×2 null/deep-reduction diagnostic plus a baseline. It tests those two
components and their interaction, not every remaining feature. Null pruning's earlier
warm-search regression is a reason to test it, not proof it caused either loss
here; fresh searches remain a separate limitation. Do not retune on these roots.

The next experiment requires its own frozen protocol and authorization; it was
not launched or scheduled. A promising package still needs tactical, clock and
held-out game qualification before a strength claim or default change.
