# Validation and experiment protocol

## Phase 4F.10 full match — October 28–29, audited October 29, 2026

The [completed report](reports/2026-10-29-phase4f10-match-results.md) records
**512 games / 256 complete color-reversed pairs**, 60+0.6, Threads=1 and Hash=64.
Only Continuation History differed. The authorized run finished at 02:06:51
Helsinki, before the fixed 07:00 cutoff; the launcher exited zero. Saved cleanup
and a separate OS process check confirm no remaining campaign processes, and
the owner may resume LM Studio inference. The progress heartbeat is deleted.

The fresh independent audit through `tools/run.py --offline` exited zero with
`complete=true`, `decision=inconclusive`, `default_change=false`, no errors,
no source differences, no exclusions and zero time forfeits by either role.
It replayed 49,753 search events, 59,737 legal game plies including opening
histories, 2,977,286 PV plies and 49,382 legal ponder suggestions (Ponder=false).
All 1,024 game engine processes, 22,650 parent resource observations, raw clocks,
options, pair membership, provenance and cleanup were checked. The audit records
3,855 input identities. Recorded endings: 361 checkmates, 140 threefold draws,
one stalemate, nine insufficient-material draws and one fifty-move draw.

On scored **179 W / 151 D / 182 L**, **254.5/512 points (49.70703125%)**.
Pair-point buckets for 0/0.5/1/1.5/2 points are **0/42/177/35/2**. The declared
conditional 95% Hoeffding score interval is **41.218897%–58.195166%**. Neither
the 299.5-point promotion-review threshold nor 212.5-point negative threshold
was reached. Keep the option off and park promotion; no gain, loss, equivalence,
universal nonregression or general Elo claim is supported. Shared stems and host
limit independence; broader SMP/time-control/platform gates remain open.

All 1,026 launcher stderr lines are the retained informational Syzygy-disabled
response warning; none are additional match failures. Earlier preparation
failures remain documented in the launch/preparation reports. No games were
replaced, resumed or rerun. All 1,955 protected files, 62 frozen source identities,
61 archived originals and README introduction match their saved identities.

Raw evidence: `results/phase4f10-match-20261028/`. External audit:
`results/phase4f10-match-20261028-audit.json`, SHA-256
`d74c0c0c27eee1a6ea183bd069872b371e44e32afff559a6f48daf688ac59d1b`.
Cleanup, preservation and documentation-validation receipts are in
`results/phase4f10-match-20261028-closeout/`. This checkpoint changes documentation
only; prior synthetic tests were not repeated, and no engine was rebuilt/searched.

## Phase 4F.10 dated launch amendment — October 28, 2026

The [launch record](reports/2026-10-28-phase4f10-launch.md) records the owner's
fresh quiet-window confirmation and bounded 19:00–22:00 Helsinki permission.
All **112 focused synthetic tests** pass (44 launcher, 68 independent auditor).
Native search-free readiness at 19:27:57 and independent audit pass: two clean
exits, all 21 UCI options, 13 commands / 65 events and 2,805 input identities.
All 1,955 protected files, original preparation evidence and README intro remain
unchanged. Archive the original 61 sources/pins; the amended set has 62 source
snapshots / 61 pins. Pre-launch setup failures and their resolution are preserved
in the report and evidence directory; no games were played during validation.
Only the dated admission policy changes. No engine/default/sample change or
strength conclusion follows. The tested amendment was committed as `b9430a6`;
the single attempt started at 19:56 Helsinki with all four workers. Independently
audit its full outcome after cleanup. See the campaign manifest for live state.


## Phase 4F.10 match preparation — October 28, 2026

The [preparation report](reports/2026-10-28-phase4f10-preparation.md) records
**122 passing synthetic checks**: 17 opening, 38 supervisor and 67 independent
auditor tests. Raw fixtures exercise PGN/UCI replay, isolated Continuation History
settings, disabled TT hints, exact provenance, malformed/duplicate declarations,
resource/cutoff/cleanup failures, inherited-permission rejection and statistical
thresholds. Earlier synthetic fixture inputs were incomplete; their failure log
is retained and final corrected tests pass. No real games were played.

Full generator source replay validates 256 balanced unique nonterminal roots
with original histories against 266,535 known roots and 2,796 saved games.
One exposed candidate was rejected deterministically and recorded; accepted
roots have no recorded overlap. There are no malformed saved-game omissions.
Shared stems and unknown internal/unsaved positions remain exposure limitations.

Actual native readiness validated all 21 UCI options in two serial sessions,
with 13 commands / 65 raw events, no `position` or `go`, and two zero exits.
Independent saved-output audit passed with no errors and 2,805 recorded input
identities. The 61 source snapshots / 60 pins include full frozen build provenance.
No frozen source, engine, normal/stable GUI binary or owner batch setting changed;
all 1,955 protected files and the README introduction match their saved identities.

Evidence: `results/phase4f10-preparation-20261028/`. Readiness SHA-256
`6b6eb20cdb8dcdf044d9af992bdb9d6b4ef0ec9eedbffe48d14db1d5c832c56e`;
independent audit SHA-256
`2191a3372a24107219aabdbc17693567a5578a08651dd7024e0b5ef9e8660b3f`.
The prepared 512-game match has not started or been scheduled. It needs a fresh
quiet window, an awake host and applicable timing authorization. Four active
workers / 6 GiB fit the observed 18-CPU / 64-GiB host's ordinary budgets, but these
are reservations, not measured OS utilization caps. No strength, SMP or default
promotion claim follows from preparation.

## Phase 4F.9 full tactical comparison — October 28, 2026

The [completed report](reports/2026-10-28-phase4f9-results.md) includes all
39 positions × two roles × 60 seconds, eight threads and 64 MiB Hash. Only
Continuation History differed. The owner granted one daytime exception and
confirmed the quiet host. The unchanged frozen attempt completed at 09:55:23
Helsinki after 78 minutes 12 seconds, with no failures, retries or exclusions.

The independent auditor passed all 78 raw sessions and 52 input identities:
831 PVs / 7,707 legal plies, 156 best/ponder plies, 2,184 commands, 234 readiness
barriers and 2,575 resource observations. All processes exited zero with EOF;
the launcher exited zero and a separate OS check found no remaining engines
or sleep inhibitor. The owner can resume LM Studio inference. Maximum audited
gap 2.043 seconds and clock drift 0.077 seconds remained inside the declared limits.

On reported 4 mates versus 3 off, with one gained M9 on position 13 and no lost
final mate reports. Shared distances match; all 39 best moves match. The extra
M9 arrived at 57.386 seconds, and its 17-ply final PV legally reaches checkmate. This
does not prove mate against all defenses or a repeatable gain. Scores match
32/39; four lower/two higher non-mate scores and two lower/four higher completed
depths are all retained in the report. Supplied-best-move accuracy is unavailable
because those labels were absent before launch. No Elo or strength nonregression
claim follows; keep the option off pending separate game qualification.

Raw data: `results/phase4f9-full-20261028/`. Independent audit:
`results/phase4f9-full-20261028-audit.json`, SHA-256
`9f8ffa45c7d3b148d6b99312acc37b76d51e8178cbb4c733338aca7520e30164`.
Launch/summary/index records: `results/phase4f9-full-20261028-launch/`.
All 1,549 protected entries (1,517 distinct files), prepared pins and README
introduction match. Engine/tooling bytes did not change; this documentation
checkpoint uses the real full audit and does not rerun prior synthetic tests.

## Phase 4F.9 tactical preparation — October 28, 2026

The [preparation report](reports/2026-10-28-phase4f9-preparation.md) records
40 passing runner and 31 independent-auditor synthetic tests. Failure cases
include wrong roles/settings, missing/duplicate Continuation History options,
an unrelated TT hint toggle, altered inputs, incomplete frozen provenance,
bad clocks, invalid chess output and incomplete process cleanup.

Real readiness passed with two clean, search-free sessions. All 78 one-second
smoke searches then passed; independent raw replay checked 528 analysis lines,
3,412 PV plies, 156 best/ponder plies, 313 resource observations, clean exits/EOF
and 52 input identities. Roles used the same frozen binary and identical
settings except Continuation History. All 39 final moves match; neither role
reported a positive mate. Do not treat smoke as the full tactical or strength
gate, or its elapsed times as a speed benchmark.

The corpus contains supplied mate distances, but no supplied best moves;
supplied-best-move match accuracy requested in the protocol is unavailable.
Record that limitation, never infer annotations or silently add data. A legal
PV, mate report or centipawn difference is not a proof of mate or Elo.
Full 39 × 60-second × two-role comparison is prepared, not run or scheduled;
it requires a separate quiet window and applicable timing permission.

Evidence: `results/phase4f9-preparation-20261028/`, with separate
`readiness-audit.json` and `smoke-audit.json`. No engine code, normal build,
stable GUI snapshot or historical campaign input changed. The short checks
requested eight workers within the 18-CPU Mac's nine-worker daytime allowance,
with 2 GiB reserved memory; admission estimates are not OS utilization caps.

## Phase 4F.8 continuation-history implementation — October 28, 2026

The [protocol](experiments/phase4f8.md) and [report](reports/2026-10-28-phase4f8.md)
cover the new default-off quiet-ordering option. Full native `make test` passed;
new table, 36 direct-search groups and 60 UCI cases passed natively and under
ASan+UBSan/TSan. Checks cover one/four-worker behavior, speculative exclusion,
original-piece context, interrupted-state restoration and allocation failure.
Existing countermove (57 cases), SMP UCI (43 cases) and direct ProbCut regressions
also passed after integration.
The first native PATH-launch fixture failed because the isolated directory had
no default network beside its executable. Saved before/after output establishes
that cause; the unchanged test passed with the adjacent network provisioned.

All 180 fixed-depth searches on 15 exposed roots completed in 90 clean sessions.
Independent raw replay validated 1,080 PVs / 4,656 plies and all best/ponder
results, file identities, clean exits/EOF, 60 exact parent/off comparisons and
90 repeat comparisons including continuation counters. The enabled option's
scores and final moves match, but node work is mixed: fresh +0.28%, reused
+4.08%, combined +0.95%; per-case ratios range 0.7644–1.4847. Report all cases;
no speed, nonregression or Elo qualification follows from this development set.

Evidence lives in `results/phase4f8-20261028/`; the independent audit is
`development-screen-audit.json`. Candidate identity and commands are in the
report. The normal/stable binaries and 1,228 unchanged protected files are
preserved; the other five inventory entries are intentional engine/Makefile/
practical README edits. The README introduction remains byte-identical.
Full matched 39-position tactical qualification and paired games are not yet
run; prepare their separate finite protocol before requesting a quiet window.

## Phase 4F.7 full match — October 27, audited October 28, 2026

The [match report](reports/2026-10-27-phase4f7-match-results.md) records the one
complete fixed attempt: **512 games / 256 color-reversed pairs**, 60+0.6,
Threads=1, Hash=64, four active workers, minimum 6 GiB reservation. Only
TT Move Hints differed. The dated authorization allowed the 16:57:44 Helsinki
start; completion was 23:20:01, before the original next-07:00 cutoff.

Fresh independent audit through `tools/run.py tools/audit_phase4f7.py` exited
zero, with all games/pairs included and no audit errors, source differences or
time forfeits by either role. Saved evidence covers 52,927 search events,
62,911 legal game plies, 3,059,254 legal PV plies and 52,577 legal ponder
suggestions (Ponder=false).
The parent supervisor recorded 23,364 observations. Audit replay validates
membership, legal histories, raw clocks/options, resource coverage, provenance
and cleanup. The launcher exited zero and the separate process check found no
remaining match/search/sleep-inhibitor process; LM Studio may resume.

Hints on scored **162 W / 186 D / 164 L**, **255/512 points (49.8046875%)**.
Pair-point buckets for 0/0.5/1/1.5/2 points are **2/37/179/37/1**. The fixed
conditional 95% Hoeffding score interval is **41.316553%–58.292822%**.
Decision: **inconclusive; park promotion, leave hints off**. Shared opening
stems and shared-host concurrency limit independence; this does not establish
equivalence, a strength gain, absolute Elo, eight-thread match strength or a
general repair of earlier clock failures. No replacement or extension is due.

Raw campaign: `results/phase4f7-match-20261027/`. External audit:
`results/phase4f7-match-20261027-audit.json`, SHA-256
`de9cbe1851f63ae6126450bd35582b0bba1550245c695cce2549918a24e27e4a`.
All 1,031 protected files and the README introduction still match their saved
identities. This checkpoint changes documentation only; previous synthetic
launcher/auditor tests were not rerun, and no engine was rebuilt or searched.

## Phase 4F.7 dated timing amendment — October 27, 2026

The owner confirmed ready and instructed starting the prepared match. The
[amendment](experiments/phase4f7-match-daytime-20261027.md) changes admission only:
explicit flag, exact authorization, October 27 16:00–19:00 Helsinki and the
unchanged October 28 07:00 cutoff. Existing daytime/nighttime budgets apply.

All 37 launcher tests and 63 independent-auditor tests passed, including date
boundaries, wrong/expired grants, ordinary overnight/DST behavior, preflight
expiry, child propagation and cutoff-extension rejection. Opening generator
tests were not repeated because generator/data bytes did not change.
Actual two-session readiness at 16:55:09 Helsinki and its independent audit passed;
both processes exited zero and no position/search command was sent. The full
engine configuration exactly matches the original readiness configuration.
The audit also replays the recorded local game exclusions and new 59-source /
58-pin inventory. Old sources/pins are archived from `2059850`, and original
readiness/report files are preserved.

Evidence: `results/phase4f7-match-20261027-preparation/`. Readiness SHA-256
`6b585d85aa13ed969834baa806a459553ae9b42c43216a13dd682b2ec713d90c`;
audit SHA-256 `adb60b59e0d4b25e0eb5851abdda9a25e5b62aefd99bc0fdcb757755ce9cfd48`.
This validates the launch change only, not game outcomes or strength. Full
campaign evidence and audit must be recorded separately after play.

## Phase 4F.7 strength preparation — October 26–27, 2026

The [preparation report](reports/2026-10-27-phase4f7-match-preparation.md) records
107 passing tests: 17 opening-generation checks, 32 launcher checks and 58
independent-auditor checks. These cover exact hint-only settings, current UCI
types/defaults/ranges, source/build provenance, duplicate input keys, legal roots,
raw game/clock evidence, timing/resource changes, cancellation, process cleanup,
fixed membership and statistical gates. Tests use synthetic evidence/processes;
they do not establish playing strength or long-run stability.

Full source replay validated 256 unique legal roots against 217,477 known roots
from 152 source records, including 2,284 saved games. Shared stems and unknown
internal search positions limit independence/exposure claims. The compact public
catalog does not redistribute saved PGNs; full replay needs those local inputs.

Actual native readiness checked two serial engine configurations, with no
`position`/`go` commands, 20 exact advertised UCI options and clean exits.
The independent auditor passed that saved evidence against all 58 source
snapshots, 57 preparation pins and the existing 25-file build provenance.
The interpreter logged the engine's benign Syzygy-disabled informational line;
raw output and stderr are retained. No tablebase assistance was enabled.

Evidence: `results/phase4f7-match-preparation-20261026/`. No held-out game,
engine rebuild, default promotion, schedule or platform/release qualification
was performed. The actual 512-game campaign needs a separately agreed window.
All 1,022 protected existing files, 57 new preparation pins and the README
introduction matched the saved identities at completion.

## Phase 4F.7 full tactical comparison — October 26, 2026

The [full report](reports/2026-10-26-phase4f7-results.md) records the completed
quiet-window comparison: all 39 positions, 78 searches, eight requested workers,
60 seconds per role, one engine at a time. Only TT Move Hints differs. The owner
confirmed paused inference/Automatic mode and starting now; AC/power snapshots
were captured at start/midpoint/end. Runtime was 78m15s, ending 23:31:55 Helsinki.

Independent raw replay passed all 40 identities, 78 distinct PIDs/zero exits,
822 iterations, 7,566 legal PV plies, 156 best/ponder plies, 2,106 commands,
3,084 consumed lines, 234 barriers and 2,565 resource observations. Receipts
were 59.980204–59.982928 seconds, maximum monitoring gap 2.080446 seconds and
clock discrepancy 55.892 ms, within the frozen limits. No operational failure
invalidated the attempt. Separate manual parsing confirmed all final raw results.

Both roles report three mates (positions 1/2 M7, 15 M9), agree with supplied
distances and end those final PVs legally in mate. All 39 best moves agree.
Six score/depth and six final-PV differences are retained in the report/raw logs.
No observed serious tactical concern blocks preparing a fresh strength campaign;
no universal nonregression, forced-mate proof, Elo gain or default promotion is
established. Hints remain off and the combined-policy campaign remains parked.

The full readable export and 78 CSV rows passed source-value/certificate checks.
All 740 protected files and the README intro remained unchanged. Existing
54 runner/auditor and 24 exporter tests were not rerun because their code was
unchanged. Evidence is in `results/phase4f7-20261026/`. No engine rebuild, new
match, schedule, foreign execution or release acceptance follows.

## Saved puzzle report exporter — October 25, 2026

While Phase 4F.7 awaits the owner's quiet window, the separate
`tools/puzzle_report.py` frontend passed 24 synthetic checks. Coverage includes
all-position ordering, signed centipawn/mate formatting, readiness/smoke/full
labels, fresh-audit and input-drift rejection, Markdown/CSV escaping, existing
output preservation, and handled publication failures. Only the audit boundary
is mocked in these tests; no engine is launched.

Native macOS integration exported the existing readiness and smoke reports
through the real independent auditor. Readiness produced headings-only CSV;
smoke produced all 78 search rows and a 39-position comparison retaining the
three score/depth differences. Both certificates bind the original report
hashes. Evidence and logs are in `results/puzzle-report-20261025/`.

All 728 protected files, including the 40 frozen comparison assets and original
engine provenance, and the README introduction were unchanged. No search,
build, full comparison, schedule, strength claim or default change follows.
The exporter is documented separately from Makefile to preserve the pending
campaign's pins. Native Windows/Linux execution remains unverified.

## Phase 4F.7 tactical preparation checks — October 25, 2026

The [protocol](experiments/phase4f7.md) freezes the current engine with hints
off/on and otherwise identical current-default settings. The
[report](reports/2026-10-25-phase4f7.md) records **54 passing synthetic checks**
(33 runner, 21 independent auditor), two passing search-free readiness sessions
and the complete 39-position/78-search one-second smoke. No engine code changed.

Independent raw replay passed 40 prepared identities, 78 distinct recorded
PIDs/zero exits, 431 iterations, 2,375 legal PV plies, 156 best/ponder plies,
2,106 commands, 2,693 consumed output lines, 234 readiness barriers and 313
resource observations. Both roles requested eight workers and Hash 64, with
one engine resident/searching at a time. Maximum reconstructed clock gap was
0.832775 seconds and discrepancy 0.679 ms; bestmove receipts were within the
fixed tolerance. Clean EOF and joined readers were verified for every session.

All 39 final best moves agreed, with no positive mate report in one second.
Scores/depths differed at positions 1, 15 and 35; retain all three. The smoke
uses nondeterministic SMP and no quiet-host attestation, so neither duration,
centipawns nor depth establishes speed, tactical superiority or playing strength.
It is separate from the full 60-second comparison, which has not started.
That run needs a fresh quiet window and any required timing exception; the
later match needs a fresh protocol. Hints remain off and 4F.7 remains pending.
Original artifacts, normal/stable GUI builds, batch settings and README intro
are preserved; no schedule or new platform/release qualification was created.

## Phase 4F.6 move-hint checks — October 25, 2026

The [protocol](experiments/phase4f6.md) precedes implementation and all candidate
searches; the [report](reports/2026-10-25-phase4f6.md) records the default-off
ordering experiment. Native core/perft/UCI, NNUE, exchange, search, ordering,
history, optional-policy and time checks passed. New direct tests passed 23
bounded groups and three injected allocation failures; new UCI checks passed
36 cases. Existing countermove/SMP checks passed 57/43 cases. ASan/UBSan passed
search, ordering/history, direct hint/UCI and optional-pruning checks. TSan passed
the direct hint, 36 UCI and 43 SMP lifecycle checks. No sanitizer finding occurred.
The two independent implementation/test reviews found no material blocker.

The new profiler passed 21 synthetic tests. Its one real screen completed all
180 searches in 90 serial fresh sessions: all 15 exposed roots, depth 6, one
worker, Hash 64, two repetitions, cold/warm, frozen parent/candidate-off/on.
Diagnostics were enabled throughout. The independently parsed audit verified
1,080 iterations, 4,656 legal PV plies and 360 best/ponder plies; all 60 parent/off
pairs match nodes, scores, depths, PVs, occupancy and old diagnostic work exactly.
It also verified 44 current/before/after assets, 90 raw logs/PIDs/zero exits,
2,760 commands, 5,880 consumed lines, 450 readiness barriers and 452 resource
observations. Its reconstructed maximum clock gap was 1.13635 s, drift 0.235 ms,
and longest search 1.78074 s, within the fixed limits.

Cold total nodes changed from 3,701,668 to 3,491,730; warm from 790,712 to 745,882,
about 5.67% less work in both groups. Hints produced 53,436 accepted legal matches
from 347,776 fallback probes, and 567,514 stores. All 60 on/off final moves and
scores match, but work increased in seven root/cache cases (14/60 repeated pairs),
including warm `gamephases-eg-04` at +33.79%. Forty-two pairs used fewer nodes;
four were equal. Every case remains in the report; no tuning or omission occurred.

LM Studio could be active. These instrumented fixed-depth observations do not
establish timing, strength, exact SMP-tree equivalence or foreign-runtime support.
Hints remain off; no full puzzle run, match, schedule, default promotion or release
was launched. Original frozen evidence, ordinary builds, stable GUI, owner batch
settings and README introduction are preserved. Evidence is under
`results/phase4f6-20261025/`; next is a separately prepared tactical/strength gate.

## Phase 4F.5 quiet-history checks — October 25, 2026

The [report](reports/2026-10-25-phase4f5.md) records 1,408 exact cutoff-learning
comparisons against the former collected-list implementation. Native and
ASan/UBSan search/ordering, null-move, ProbCut, quiescence-SEE and deep-quiet
checks passed. Native core/NNUE/policy/time checks, 57 countermove UCI cases and
43 SMP lifecycle cases also passed. The updated profiler passed 28 synthetic
checks, including explicit presets, stray-output rejection and failed exits.

Independent raw audit of the correctness-only comparison passed 120 searches /
60 exact pairs at depth 6, one worker, defaults/all-on and fresh/reused caches.
It replayed 720 iterations / 3,108 PV plies and 240 best/ponder plies, checked all
500 recorded commands and readiness barriers, zero exits and 27 unchanged pins.
Time/NPS are excluded; LM Studio may have been active. This is bounded native
single-worker equivalence, not timing, strength or exact SMP scheduling proof.

The separately authorized quiet window completed in 65.022700 seconds after the
owner paused LM Studio inference; AC power and Automatic mode were recorded.
The owner was told inference could resume immediately afterward. Three
comparisons used all 15 exposed roots, depth 6, one worker, Hash 64, two
repetitions, alternating build order and fresh/reused caches, with diagnostics,
ponder and tablebases off. The combined cap was 300 seconds and each search had
a ten-second watchdog. The candidate source is `af2abdb`; executable identities
and exact settings are retained in the [report](reports/2026-10-25-phase4f5.md).

Independent replay passed 360 searches / 180 exact pairs, 2,160 iterations,
9,320 legal PV plies and 720 best/ponder plies. Raw nodes, scores, depths, PVs,
moves and hash occupancy matched. All command sequences, 726 readiness barriers,
six recorded process identities/zero exits and full consumed transcripts passed.
The 41 prepared identities and 35 before/after/current input identities per
profile matched. Maximum per-search wall/monotonic discrepancy was 10.417
microseconds; receipts ranged from 1.054 ms to 1.27334 seconds overall.

Aggregate baseline/candidate receipt-time ratios (fresh/reused) were
**1.01506/1.00803** for the SEE implementation with SEE ordering,
**1.01278/1.00687** with all-on, and **1.00518/1.01763** for quiet-history
bookkeeping with defaults. The respective slower pooled root/cache counts were
6/30, 11/30 and 6/30; every slower pair remains in the audit. Examples slower in
both repetitions include SEE ordering's warm `gamephases-mg-05` (0.95519),
all-on's cold/warm `opening-01` (0.99087/0.98322), and the history change's cold
`opening-02` (0.99060). These small, short-sample differences do not establish
statistical significance, universal speed gains or playing strength. Receipt
timing and owner/harness observations are not continuous host telemetry.

The original correctness-only evidence remains separate and unchanged. No
default change, full puzzle rerun, match, foreign-runtime requalification or
release follows. The all-on tactical concern and parked 512-game campaign remain
unchanged. Evidence is retained under `results/phase4f5-20261025/`.

## Phase 4F.4 diagnostic and SEE checks — October 25, 2026

The [report](reports/2026-10-25-phase4f4.md) separates the completed baseline
diagnostic from the subsequent SEE implementation. The screen passed all 120
searches, 989 completed iterations and 5,776 legal PV plies. Independent raw
replay verified all configurations, counters, worker accounting, applied options,
120 distinct recorded PIDs/zero exits, timing and 37 input identities. The
pre-candidate Makefile changed after the run; archived bytes match both original
pins and the independent audit records this explicitly. There were no detected
clock gaps, illegal outputs or operational failures. All 60 eight-thread searches
had all eight workers active. These are instrumented diagnostics, not Elo or
causal per-function cost measurements.

The new diagnostic tool passed 25 synthetic checks. The candidate passed the
native core/search suite, optional ProbCut, quiescence SEE, null-move and deep
quiet checks plus 43 bounded SMP lifecycle cases. Native and ASan/UBSan exchange
checks passed 4,117 generated score comparisons and 145,024 independent attack
mask comparisons. Search, 2,264 ordering comparisons, quiescence SEE and ProbCut
also passed under ASan/UBSan. No architecture-specific intrinsic was added;
foreign execution has not been requalified in this phase.

A separate uninstrumented depth-6 comparison passed 120 searches / 60 exact
parent-candidate pairs under defaults/all-on, one worker and fresh/reused caches.
Independent replay verified 720 completed iterations, 3,108 legal PV plies,
240 bestmove/ponder plies, all 500 recorded commands, 180 readiness barriers,
27 unchanged input identities and both zero exit codes. No bound score,
protocol error, unexpected metadata or tablebase hit was present. Nodes,
scores, depths, PVs, moves and hash occupancy match; time/NPS are excluded.
This establishes bounded single-worker equivalence, not exact SMP behavior.

The owner was told LM Studio could resume after the initial diagnostic, so this
phase's subsequent checks remain correctness-only. The previously pending SEE
timing checkpoint was later completed in the separately authorized Phase 4F.5
window above; its limited observations do not retroactively qualify these
earlier durations. Normal defaults stay unchanged and do not use the optional
SEE paths. The all-on tactical concern and parked 512-game campaign are
unchanged. No new full puzzle run, match, schedule or strength promotion occurred.
This phase's evidence remains in `results/phase4f4-20261025/`.

## Phase 4F.3 combined-policy tactical audit — October 24, 2026

The [protocol](experiments/phase4f3.md) freezes the same current executable and
network for the complete all-on package and current-default control. Both keep
LMR enabled. The [report](reports/2026-10-24-phase4f3.md) records fresh opening
generation, successful real-engine search-free readiness and its independent
audit, plus a completed eight-thread tactical smoke.

The combined tool suite passed 128 checks covering inputs, protocol/clock evidence,
supervision/cleanup, both DST transitions and permission/resource boundaries.

The smoke passed all 39 positions/78 searches. Raw replay checked 453 iteration
records, 2,588 PV moves, final moves and explicit options. Best moves matched at
38 positions; 11 final scores differed, and neither configuration reported mate
within one second. Position 22's different moves are retained without declaring
either a gain or regression. No errors, illegal moves, timing overruns or detected
sleep were observed. This is operational evidence, not the full 60-second audit.

The full comparison completed all 39 positions / 78 searches at 60 seconds,
eight threads and Hash 64. Independent raw replay passed 741 iterations / 6,280
legal PV plies, final best/ponder moves, exact options and source identities.
All 2,572 monitoring observations passed: maximum gap 2.252246 seconds, maximum
wall/monotonic discrepancy 21.704 ms; monotonic bestmove receipts ranged from
59.980226 to 59.983569 seconds. No detected sleep, receipt overrun, illegal move
or operational failure occurred. The owner authorized this run's daytime start;
that exception does not cover the separate match or later long tests.

Defaults reported three positive mates versus two for all-on. All 39 best moves
agreed. Position 1 was M7/default versus M9/all-on; position 15 was M9/default
versus +15.99/all-on. A separate post-hoc overnight diagnostic repeated position
15 twice per role and reproduced M9 versus +15.99, always with `e7d7`. Its raw
audit passed four sessions, 42 iterations / 310 legal PV plies, timing, 132
monitor observations, source identities and original-evidence immutability.
These repeats do not replace or enlarge the original sample.

The [full report](reports/2026-10-24-phase4f3.md) records all 39 results and hashes.
Mate-ending legal PVs do not prove forced mate against all defenses; supplied
mate annotations, centipawn scores, nominal depth and common best moves do not
prove strength. Raw logs verify fresh-session commands, but do not include PIDs
or exit codes. Timing uses main-loop receipts, and configured threads/reservations
are not measured OS utilization. SMP is nondeterministic.

**Defaults remain unchanged; the unstarted 512-game campaign is parked** pending
Phase 4F.4 diagnosis of combined-package cost/SMP interaction on exposed benchmark
roots. No held-out root was searched and no statistical match gate was applied.
This is a repeatable tactical diagnostic concern, not an Elo verdict. The frozen
protocol/tools/corpus and completed smoke snapshots remain unchanged. This
results checkpoint changes documentation only; no additional engine rerun is
needed to validate a code change.

## Phase 4F.2 move-ordering efficiency — October 24, 2026

The [report](reports/2026-10-24-phase4f2.md) records 120 exact current-default
parent/candidate searches: 720 iteration records and 3,104 independently legal
PV moves, with unchanged nodes, scores, depths, final moves and hash occupancy.
Aggregate speed ratios were 1.055 fresh and 1.037 reused; warm opening-02 was
7.14% slower across both repetitions. All 35 recorded input identities matched
before/after. This is limited native ARM64 performance evidence, not Elo.

The direct ordering check passed 2,264 comparisons against the frozen former
comparator: priorities, helper root/interior ties, both policies, both colors,
special moves/flags, SEE counter deltas and scratch reuse after history changes.
Native and ASan/UBSan core/search suites passed; the full sanitizer run includes
the new ordering check. Forced-scalar Search API and ordering checks also passed.
Native null-move, ProbCut, quiescence-SEE, deep-reduction
and 57 countermove UCI checks passed. The SMP suite passed 43 cases.

Both default and all-eight-options-enabled configurations matched their own
parent results on all 39 supplied FENs at 20,000 nodes per search: 156 searches,
528 iteration records and 3,120,000 nodes total. Legal PV/best/ponder replay
passed. This checks implementation equivalence within each configuration;
it does not prove package strength or activation of every selective branch.
The owner's separate depth-10 all-on observation is retained as development
feedback, not folded into the implementation speed result.

Evidence: `results/phase4f2-20261024/`. No policy default changed and no long
campaign was run. Stable GUI `0.1-dev-4b8b35d` remains intact. The ordinary
binary was rebuilt externally during the owner's manual testing and matches
the tested candidate; agent builds stayed in separate directories.

## Phase 4F.1 quiescence efficiency — October 24, 2026

The [report](reports/2026-10-24-phase4f1.md) records exact parent/candidate parity
across 120 current-default searches: 15 exposed roots, two repetitions and
fresh/reused caches. Every iteration's nodes, score, PV and selective depth,
plus final best/ponder moves, agreed. Observed aggregate speed ratios were
1.109 fresh and 1.121 reused; a single 1.3-ms warm sample was slower. These short
native macOS ARM64 observations are not universal performance or Elo evidence.

The full native and ASan/UBSan suites passed. Forced-scalar move-generation and
Search API checks passed. The new generator matched the full legal generator
on 8,018 positions including pins, en passant, all promotions, quiet-only
mobility, terminal states, check evasions, null-search states and full unwinds.
Search regressions exercise quiet stand-pat and promotion mates in both colors.
Native optional null-move, ProbCut and SEE-pruning branch checks passed, as did
43 SMP lifecycle cases and 21 comparison-tool integrity tests.

A separate 20,000-node comparison on all 39 owner-supplied FENs also passed:
78 searches and 260 iteration records matched exactly, including final nodes,
best/ponder moves and independently legal PVs. This is bounded correctness
evidence, not the full 60-second puzzle audit or a playing-strength result.

The implementation skips redundant quiet legality checks only after a legal
witness exists; it never omits a capture/promotion legality check. Complete
evasions remain mandatory in check. Search policy and evaluation are unchanged.
Evidence is under `results/phase4f1-20261024/`. No long campaign or new foreign
execution was performed; existing GUI snapshots and ordinary binaries are intact.

## Phase 4E.7 managed network selection — October 24, 2026

The [report](reports/2026-10-24-phase4e7.md) records a fresh 2,057-position
native/scalar/reference qualification of a copied synthetic training export,
retained evidence verification, and managed/direct UCI launch parity plus
selection/revert/default checks. Catalog/evidence/CLI tests cover atomic failure,
concurrent writers, stale sources, modified/truncated records, missing state,
unsafe paths and explicit GUI overrides. The existing UCI suite also passed.

The engine change is limited to explicit initial file selection and its
advertised default. Normal no-argument defaults and search/evaluation code are
unchanged. Native macOS ARM64 is the real execution scope; no foreign launch,
match/puzzle, strength or new release claim follows. Existing engine binaries,
owner batch settings/FENs, README intro and frozen GUI bundles are preserved.
Evidence is in `results/phase4e7-20261024/`; see the report for exact test counts
and limitations. The managed test catalog is isolated from user selection.

## Phase 4E.6 training/export tooling — October 24, 2026

The [training report](reports/2026-10-24-phase4e6.md) records real automatic
runtime/source setup and offline reuse, plus 132 distinct passing Python checks.
Fresh CPU training (2 optimizer steps/32 samples) and parent-weight fine-tuning
(1 step/4 samples) each exported SFNNv16 files and passed all 2,057 independent
native/scalar/reference positions. An independent audit rehashed source, binary,
dataset, actual checkpoint and result artifacts and verified lineage/counters.
The fixture's 256 rows/eight positions/zero games are synthetic correctness data.

macOS ARM64 CPU is the only qualified training route. Physical memory is queried;
final admission reserves 8 GiB and tensor threads plus four loader threads. The
fresh check measured about 5.34 GiB peak RSS, prompting an increase from its
initial 6 GiB reservation; the parent run used the final policy. No strength,
GPU, foreign training, held-out validation or full optimizer resume is claimed.
The wrapper enforces hard worker/night deadlines and rejects incomplete work.
A real nested-process cancellation regression verifies child cleanup, failed
reports and retained logs; the final parent run includes that correction.
Original engine sources/builds, owner batch inputs, GUI snapshot and README
introduction are preserved. No long match/puzzle campaign or gameplay defaults
changed. Evidence: `results/phase4e6-20261024/` and the linked report.

## Phase 4E.5 network tooling — October 24, 2026

The [network report](reports/2026-10-24-phase4e5.md) records 66 native tool checks
and 65 passes/one missing-Make skip in a Linux ARM64 VM. Two complete native
oracle comparisons passed 2,057 positions each: the manifest-pinned file and a
synthetic final-bias modification. The latter changes 403 output records while
retaining exact native/scalar/reference agreement. Independent audit verified
network, corpus, outputs, all five executables, local/reference source hashes
and reference HEAD. Eight real negative checks reject malformed/trailing files,
unsafe wrapped output and misuse of the strict pinned route.

This establishes finite SFNNv16 arithmetic compatibility and tooling behavior,
not training provenance or playing strength. Unknown counts stay null; metadata
declarations remain unverified. Normal engine, batch settings/FENs, README intro
and stable GUI bundle are preserved. Native Windows, Linux oracle execution
for these new commands, first-use source download and gameplay/long campaigns
were not rerun. Raw evidence is in `results/phase4e5-20261024/`.

## Phase 4E.4 target setup/provisioning — October 24, 2026

The [setup report](reports/2026-10-24-phase4e4.md) records 87 passing checks:
seven compiler-path, 20 cache/extraction, 24 routing/Make integration, and 36
existing runtime-verifier/Make tests. Fresh automatic builds passed for native
macOS, Linux ARM64 and Windows ARM64. The native engine plus seven test binaries
passed all eight runtime checks. Native and Linux ARM64 engine hashes match
their earlier artifacts. Linux/Windows x86-64 compile/link/header probes passed;
missing local RISC-V prerequisites produce the expected clear failure. A clean
Linux ARM64 VM downloaded/prepared the pinned Windows toolchain and passed its
ARM64 compile/link probe. No foreign executable was run in this checkpoint.

All engine/Fathom sources, owner batch settings/FENs, README introduction and
protected GUI assets remain unchanged. Compiler setup, logs, hashes and limits
are in `results/phase4e4-20261024/` and `build/portable/reports/`. Native Windows
execution/cancellation, Linux system compiler provisioning and Apple SDK
installation remain explicit gaps. An intermediate mocked report fixture failure
is retained and fixed; all final checks passed. This is build/tooling evidence,
not a strength gain or release acceptance.

## Phase 4E.3 automatic Python setup — October 24, 2026

The [tooling report](reports/2026-10-24-phase4e3.md) records 197 passing native
checks: 32 new dependency/cache/process tests, seven batch tests and 158 existing
match/profiler/runtime-verifier/Make checks. Real macOS first use, concurrent
offline setup and offline repair of a damaged environment passed. Linux ARM64
VM setup passed with Python 3.13.17; the final run rebuilt from cached archives
with networking disabled and passed all 32 setup plus seven batch checks.
Its initial test-harness `runpy` mock failure is preserved and fixed. No real
engine puzzle/match campaign was run. Native Windows setup/process-tree
cancellation remains unverified.

All 24 engine/Fathom source pins and 61 of 62 protected assets match. The one
intentional file change adds batch bootstrap; the editable settings/FEN block
matches byte-for-byte. Native engine, README intro and GUI snapshots are intact.
The shared launcher leaves frozen qualification scripts and their dependency
requirement unchanged. Raw logs/pins are in `results/phase4e3-20261024/`. This is
tooling evidence, not a strength gain or release acceptance.

## Phase 4E.2 target coverage — October 24, 2026

The [target coverage report](reports/2026-10-24-phase4e2.md) adds Linux RISC-V64
execution under QEMU 10.0.13 and Windows x86-64 execution through Wine 10 on
Docker's emulated x86-64 Linux. Each passed all eight portable runtime checks,
including 537 NNUE incremental/full-refresh positions, twelve pinned raw/wrapped
goldens, 360 update transitions, 1,515 dense cases / 84,126 repeated comparisons,
search/policy/time checks and actual two-worker UCI activity. Each additionally
passed 140 exact Syzygy WDL oracle cases and six search scenarios at Threads 1
and 4. The 72-file table corpus was verified and remains external to Git.

RISC-V uses Debian GCC 14.2.0 in C++26 mode, RV64GC/LP64D, without extra atomic
link libraries. Windows ARM64 engine and seven tests compiled/linked with the
verified LLVM-MinGW 20261020 archive / Clang 23.1.4. PE headers and imports were
inspected. Its Wine ARM64 environment did not finish bootstrap: 90-second
position probe, 30-second loader diagnostic and 45-second fresh-prefix/headless
probe all timed out before a test completion marker. Preserve that failed
environment evidence; Windows ARM64 remains build-only. No native Windows
execution, GUI behavior, CPU speed, strength or new release is established.

The verifier's new `compatibility` label requires a Windows target and explicit
runner, preserving native/VM host matching and all existing binary/network
checks. Thirty-four verifier and two Make tests passed. Engine/Fathom sources,
network, README introduction, native engine and 62 protected assets remain
unchanged. No full SF19 stage oracle, sanitizer/race suite or puzzle/strength
campaign was rerun for this tooling-only checkpoint. Logs, configuration,
package/asset pins and reports are under `results/phase4e2-20261024/`.

## Phase 4E.1 runtime verification — October 24, 2026

The [portable runtime checkpoint](reports/2026-10-24-phase4e1.md) passed 28
engine-free verifier tests and two Make recipe tests. Failure paths include
architecture mismatch (all six target header formats), skipped/missing suites,
wrong network, bad compiler metadata, subprocess/UCI timeouts, illegal replies,
inactive worker accounting, changed artifacts and existing-report preservation.
All C++ test link recipes now receive `LDLIBS`; `runtime-binaries` builds but
does not execute foreign binaries.

All eight checks passed on native macOS ARM64, Linux ARM64 in a local Docker
VM, and Linux x86-64 through Docker emulation. Each ran the existing position,
NNUE, independent update/dense arithmetic, search, selective-policy and time
suites, plus a bounded two-worker UCI lifecycle. NNUE checks include twelve
pinned raw/wrapped goldens, 537 incremental/full-refresh positions, 360 update
transitions, and 1,515 dense cases / 84,126 repeated output comparisons per
runtime. Two-worker activity was observed, not merely requested. Both Linux
targets additionally passed 140 exact Syzygy WDL oracle cases with DTZ
outcome/legality and concurrent probing, plus six search scenarios each at
Threads 1 and 4. The pinned 72-file table corpus remained external to Git.

Windows x86-64 engine/test binaries linked and their PE imports were inspected;
no Windows runtime execution is claimed. Linux RISC-V64 and Windows ARM64
remain unbuilt/unrun locally. These are bounded correctness results, not full
platform certification or native performance evidence. Engine source hashes and
the native binary are unchanged. The full external SF19 stage oracle,
sanitizer/race checks and strength/puzzle campaigns were not rerun. Reports,
logs, commands, compiler configuration and binary/network hashes live under
`results/phase4e1-20261024/`; existing evidence is preserved. No release or
search-default promotion follows.

## Phase 4D.7 implementation — October 23, 2026

The [frozen ProbCut protocol](experiments/phase4d7-probcut.md) isolates one
default-off candidate. Native/scalar/ASan+UBSan/TSan direct tests passed real
two-stage activation, both-color quiet mating defenses that reject the shallow
screen, negative-SEE sacrifices retained by ordinary search, checking mates,
mate/tablebase threshold guards, real repetition/rule-50 draws, isolated TT
and learned-state behavior, exact cancellation and policy-reset parity.
Controlled interior windows exercise rare paths; they are correctness checks,
not strength samples. The production API and normal search use no test hook.

Each build passed 30 short UCI lifecycle cases, including one/four workers,
invalid option preservation, node limits, stop, ponder, special moves, legal
PVs and cleanup. Native passed the existing 43-case SMP suite and core, policy,
time and ordinary search checks; scalar and ASan+UBSan also passed ordinary
search checks. No sanitizer or race finding occurred. The profiler passed
31 engine-free tests covering corruption, exact parent signatures, interrupted
accounting, resource/deadline gates, drift and cleanup. Saved logs are under
`results/phase4d7-20261023/`.

The single fixed 60-search screen and independent saved-evidence audits passed
all 12 exact parent/off cold/warm pairs, 359 legal PVs (1,626 plies), 60 best
moves and 60 ponder moves; all 36 sessions recorded clean exits. All 29 profile
artifact hashes and 62 protected files remained unchanged. Depth-6 fresh-cache
nodes fell 22.05%, reused-cache nodes 2.98%, with matching final decisions;
reused-cache elapsed time rose 1.62%. One of six timed roots gained a ply and
changed its final score/PV; all common-depth scores/PVs matched. See the
[full account and limits](reports/2026-10-23-phase4d7.md). The one-second puzzle
smoke passed independent output/corpus/pin audit: 78 legal final moves, all
39 best moves matching, 14 score differences and no reported mates or errors.
The authorized full attempt after `21d416f` ran October 23 from 09:13 to
11:20 Warsaw. Both adapters and supervisor exited zero. Independent audit
verified all 78 legal ordered results, all 39 best moves matching, M7 on position
2 in both roles, no additional reported mates, 19 score differences and frozen
source/asset pins. This validates output integrity, **not equal-time tactical
qualification**: OS logs confirm 13 sleep intervals totaling 52m39s across both
roles. Wall elapsed 127m18.244s differs from monotonic 75m04.849s by 52m13.395s.
The final-only runner cannot identify affected positions or certify equal
actual search opportunity. Preserve raw status and outputs, plus separate
`puzzles-full-audit.json` and `puzzles-power-events.txt`; no automatic repeat.
Keep ProbCut off and close this attempt as timing-inconclusive. The earlier
bounded screen is separate evidence and does not establish playing strength.

## Phase 4D.6 implementation — October 23, 2026

See the [report](reports/2026-10-23-phase4d6.md) and fixed
[experiment](experiments/phase4d6-deep-quiet.md). The retained-occupancy reporting
fix passed nine real UCI searches and retained the parent's exact search in
all 12 cold/warm pairs. Native core/search/policy/time tests passed. Native,
scalar, ASan+UBSan and TSan each passed direct deeper-reduction/time tests and
24 deep-option / 14 bounded-time UCI cases across one/four workers; native also
passed 43 ordinary SMP cases, scalar/ASan passed the full search suite. No race
or sanitizer finding occurred. TSan completed normally; its long instrumentation
cost is not engine performance evidence.

The first extra-tier activation test incorrectly required a rare alpha-raising
probe. Six bounded fixtures observed activation without that event. The revised
test exercises interruption at the first extra reduction (node 65,900), shared
ordinary-LMR verification and state/cache restoration. Extra-tier verification
was not observed and is not claimed as tested directly; source review checked
the shared ordinary-depth path. Search policy was not tuned to this fixture.

A 28-check mocked profiler suite validates exact time budgets, cache sizing and
counters, schema corruption, parent parity, interruption, cleanup and source drift.
Its single 60-search screen passed with all source pins stable: about 1.05% cold
and 2.23% warm node savings at depth 6, matching final decisions. All six timed
pairs retained the same completed depth/decision. This does not establish Elo.
The independent six-search PGN-clock replay kept all best moves but lost one ply
on one root with tighter timing. New timing and reduction policies remain opt-in.
The frozen owner-runner adapter passed all 78 one-second smoke searches with
legal results and unchanged best moves (two centipawn-score differences, no
positive mates at that short limit). Full matched 60-second puzzle validation
ran under the owner's one-run daytime exception from 06:44 to 08:02 Warsaw
on October 23 (78m05s). Both adapters exited zero. Independent audit passed
all 78 legal final moves, the ordered 39-position corpus, 83 source/asset
checks and the unchanged README introduction. Both builds reported M7 on
position 2 and centipawn scores on the other 38. All 39 best moves matched;
15 centipawn scores differed. No mate gain, loss or distance change occurred.
Saved evidence: `results/phase4d6-20261023/puzzles-full-audit.json` and the
original parent/on text outputs. The simple runner saves final scores/moves,
not a full UCI/PV, depth or per-position timing trace. Legal moves are checked
independently; mate proofs and supplied annotations are not independently
certified. This is not a best-move solve rate or strength measurement.
Close this finite checkpoint with deeper reductions parked off; next is
Phase 4D.7 ProbCut. No match or schedule is running.

## LMR default integration — October 23, 2026

The [separate integration record](reports/2026-10-23-lmr-default.md) changes only
the existing LMR default and checks explicit opt-out against the frozen parent.
Native, scalar and ASan+UBSan builds each passed 23 deterministic searches and
15 exact comparisons, with legal PVs and actual reductions. A direct API test
covers untouched `SearchLimits`; UCI tests cover advertised/active defaults and
invalid-option preservation. Native/scalar/ASan+UBSan core, search, policy,
time, exchange and isolated pruning suites passed, as did TSan search checks.
All four builds passed the 43-case SMP lifecycle suite with default LMR-on.
The integration is retained; opt-out and all unrelated defaults are preserved.
All 60 protected files and the README introduction remained exact.
The completed qualification below remains frozen; no additional match or
SMP-strength claim is implied.

## Fresh LMR qualification result — October 23, 2026

The [final audit](reports/2026-10-23-lmr-results.md) passed all 512 games/256 pairs
with no exclusions, errors, live-source drift or either-role clock forfeits.
LMR-on scored 215W/175D/122L, 302.5/512 points (59.08%); its conditional 95%
score interval is 50.594%–67.570%. The frozen decision is
`eligible_for_default_review`, with `default_change=false`. This remains limited
to the tested one-thread 60+0.6 condition and its stated independence assumptions.

Raw replay verified 50,367 searches, 60,351 legal plies including openings,
2,639,322 PV plies and 50,015 ponder moves; all 1,024 recorded processes exited.
The run finished at 02:18 Warsaw in 6h15m35s, before cutoff. The unchanged auditor
produced `results/lmr-20261022/final-audit.json`; a separate tally agrees and
60 final protection checks passed. No engines, builds or additional matches
were started to audit the saved data. That audit did not automatically promote
the default; the subsequent integration is recorded above. No absolute rating
or SMP strength claim follows.

## Fresh LMR qualification preparation — October 22, 2026

The [fixed 512-game comparison](experiments/lmr-20261022.md)
[launched October 22 at 20:03 Warsaw](reports/2026-10-22-lmr-launch.md); its final
audit is recorded above. Preparation tests passed: 17 opening checks, 23 supervisor checks, 48 independent
audit checks and 57 existing runner/statistics checks, **145 total**. Synthetic
raw games exercise clocks, legal histories/PVs/ponders, actual options, both-role
forfeit classification, corrupted evidence, resource failures, cancellation,
PID cleanup and the unchanged 07:00 cutoff. Full generation-source replay
verified 256 distinct roots against 168,111 recorded source roots.

Serial real-engine readiness sent no `position` or `go`. Its independent audit
passed actual settings, option types/defaults, source/asset identities, legal
opening histories and saved-game exclusions. The unchanged ordinary engine uses
the previously audited four-worker live readiness result; no repeat or fresh
strength result is implied. The [preparation report](reports/2026-10-22-lmr-preparation.md)
records hashes, raw logs and limitations. Full-match evidence is now audited;
default integration is a separate subsequent step recorded above.

After preparation commit `548ce74`, the owner authorized one October 22 daytime
launch. Its dated amendment passed 27 launcher and 54 auditor tests (81 total),
fresh search-free readiness/independent audit, and 60 protected-file checks.
Evidence is under `results/lmr-20261022/daytime-preparation/` and the parent
folder's `daytime-*-tests.log`. The exception preserves resources, match inputs
and the next-07:00 Helsinki cutoff. It was committed as `a81c951` before launch.

## Embedded-position batch runner — October 19, 2026

At the owner's request, the initial XLSX runner was simplified to an embedded
FEN list, four editable settings, python-chess UCI communication, and printed
scores. All 39 embedded positions match the original extracted spreadsheet order
and pass `chess.Board.is_valid()`. Four missing counter pairs were filled as `0 1`.
The referenced old speed benchmark informed the requested simplicity only;
its implementation and position corpus were not reused.

`PYTHONDONTWRITEBYTECODE=1 python3 tests/batch_positions_test.py` passed seven
checks with mocks and original synthetic UCI subprocesses: corpus validity,
signed mate/cp scores, exact-score filtering, side-to-move perspective, missing
scores, diagnostic/PV errors and cleanup, ordered continuation after failure,
and fresh processes. The revised script also passed three-position smokes with
each of chess0live and pinned SF19, using one thread, 16 MB hash and 50 ms per
position. These printed results are recorded in the task, not exported by the
script. The earlier XLSX version's separate evidence remains in ignored
`results/batch-positions-check-20261019/`. Executed binary SHA-256 values:
`d11ed536a5c25336e7b6f8f61a6afd96bce9d19e0ae0c6eb1e9479e48533df59`
(normal chess0live) and
`61d09e76d41697555564498df2ecc7cab0bbe3b40ae626b9e7460ae3d9cbe969`
(SF19, matching the pin in MATCHES.md). These checks validate the batch workflow;
the full 60-second-per-position benchmark and other engines/platforms were not
run. Engine sources, defaults and stable GUI bundles were not changed or rebuilt.

### Use for development progress

The owner requested using this suite to track chess0live development. Include a
before/after puzzle comparison at material search or evaluation checkpoints.
Keep the script simple; use its existing printed output rather than adding a
second benchmark framework.

- Run the same 39 FENs in order with 60,000 ms per position, fresh processes,
  identical Threads/Hash, machine and comparable host load. Keep the NNUE file
  and all other engine settings fixed unless they are the declared change.
- Save both complete outputs under `results/`, with source revisions, binary
  and network hashes, settings and the exact FEN list. Preserve a baseline
  binary before rebuilding. Follow the existing resource/overnight policy.
- Compare each position's final exact score: expected positive mate distance,
  another positive mate distance, no positive mate reported, or an error/missing
  score. Report newly solved positions and regressions separately, including
  changes in mate distance. Expected distances are supplied puzzle annotations,
  not independently certified answers; this tally does not implement the
  spreadsheet's separate any-depth points rule.

Investigate one-run differences; multithreaded searches can vary. Use deliberate
checkpoints: a full 39-position run allows about 39 minutes of search per build.
This exposed suite measures tactical progress and regressions on these puzzles.
It complements correctness checks and separate strength matches; it does not
replace held-out qualification or establish an Elo gain. The first full
60-second baseline and matched candidate comparison completed in Phase 4D.5
below, under an explicit one-run daytime exception. Adopting this workflow
does not authorize automatic runs or schedules.

## Clock-boundary diagnostic — October 20, 2026

The [protocol](experiments/clock-boundary-20261020.md) and
[result](reports/2026-10-20-clock-boundaries.md) cover exactly 32 searches:
two complete historical histories, 600/2,000-ms clocks, LMR off/on, position
barrier off/on, and serial/four-process load. All replies arrived within their
transmitted clocks. Final accounted overrun peaked at 0.007375 ms and full
history processing at 0.160791 ms. No historical large delay was reproduced;
this does not establish a repair or clear the reliability gate.

Ordinary release position/UCI/resource/Search/time checks and 15 prior
clock-probe tests passed. The new tool passed 23 engine-free tests; its UCI
contract passed 11 searches in diagnostic release, scalar and ASan+UBSan
builds. Scalar/sanitizer Search suites also passed. Twelve depth-4 searches
matched parent/ordinary/diagnostic decisions, scores, PVs and nodes exactly.
The ordinary executable hash is unchanged. No new TSan or foreign-platform
run, strength match, full puzzle comparison, or default promotion is claimed.

The initial live contract check rejected an expected empty-Syzygy setup
notice; the test was corrected before measurement, and its failed log retained.
Raw outputs, source/binary hashes, calibration bounds and independent audit
are under `results/clock-boundary-20261020/`. Next: bounded real-match readiness
at the proposed four-worker concurrency before a separately frozen fresh LMR
qualification. Any clock failure remains a blocker.

## Four-worker match readiness — October 20, 2026

The [fixed protocol](experiments/match-readiness-20261020.md) uses eight games
at 3+0.05, four active one-thread searches, fresh paired openings and an
unchanged frozen ordinary executable. Before play, `make test-match
test-match-readiness` passed 94 checks: 17 statistics, 40 runner, 18 supervisor
and 19 independent auditor checks. Deterministic opening regeneration and
source replay also passed, with no engine evaluation or outcome selection.
The supervisor reserves eight resident engines/6 GiB, checks resource/input
stability and retains incomplete or failed evidence. The independent auditor
subsequently passed the single live attempt: eight natural completions,
646 on-time searches, 806 legal game plies including openings, 5,180 legal PVs
and 640 legal ponder moves. Peak concurrency was exactly four, with four
active for 14.977 seconds. Total elapsed was 23.949 seconds; minimum clock
slack was 9.659 ms. All 16 processes closed, 23 resource observations passed
and source/protected identities stayed unchanged. The
[report](reports/2026-10-20-match-readiness.md) records the 3W/2D/3L score,
hashes and scope limits. This passes bounded operational readiness only;
fresh long qualification remains separate and LMR stays off.

## Phase 4D.5 quiescence SEE — October 20, 2026

The [candidate report](reports/2026-10-20-phase4d5-qsearch-see.md) records
native/scalar/ASan+UBSan full suites and new Search API/UCI checks; TSan Search,
SMP and new API/UCI checks also passed. Each build passed 98 bounded UCI cases.
Ten engine-free profiler tests cover the evidence/deadline/resource lifecycle.
The actual-board exception fixtures, pure policy boundaries and source review
are separate from observed pruning activation and legal-output checks; none
proves universal tactical safety.

All 60 predeclared profile searches completed. The independent raw parser
verified the matrix/settings/order, 351 iterations, 1,550 legal PV plies,
120 bestmove/ponder plies, 12 exact parent/off pairs and summary arithmetic.
Fresh/reused nodes fell 11.62%/1.58%; one timed root gained one depth. All final
best moves matched, but starting-position score/PV changes remain recorded.
Single-repetition elapsed changes qualify neither speed nor playing strength.

The unchanged embedded puzzle runner, through a frozen temporary configuration
adapter, completed a separate matched **1,000-ms smoke**: 39 positions per build,
all best moves matching, three centipawn-score differences, no errors or positive
mates. The required matched **60,000-ms checkpoint also completed**, including
the first full baseline, under the owner's explicit October 20 daytime exception.
All 39 positions per build produced legal best moves and exact final scores.
Both reported only M7 on position 2, matching its supplied annotation; 38/39
ended with centipawn scores. No positive-mate gains, losses or distance changes
were observed. All best moves matched; only position 29's score changed from
+9.16 to +9.59. These are fixed-time final scores, not same-depth comparisons.

The independent audit checked all 78 legal moves, settings/order/exit codes,
59 source/protected hashes and all six post-run hashes. Printed final outputs
do not include full PVs or certify a mate. The complete pair took 78m05s
(15:41–16:59 Helsinki). Raw logs, pins and summaries are under
`results/phase4d5-20261020/` and `build/experiments/phase4d5-20261020/`.
Both runs have ended and the one-run exception is consumed. No schedule,
match or default promotion was inferred. The subsequent clock-boundary
diagnostic is recorded above; no clock cause or repair is established yet.

## Phase 4D.2 current-engine LMR qualification — October 18, 2026

The [protocol](PHASE_4D2.md) fixes 1,024 games and 512 reversed-color pairs,
eight workers, fresh unsearched inputs, explicit unrelated options off, and a
fixed next-07:00 cutoff. Independent raw-game and aggregate auditing is mandatory.
Preparation and launch evidence are in the
[checkpoint record](reports/2026-10-18-phase4d2-preparation.md). The eight-worker
load check passed all 24 clock-controlled replies, eight stops and reuse checks;
readiness passed without a held-out search. None of these operational checks
establishes strength. Existing LMR remains disabled until a complete qualifying
result and explicit default review. The pair-level interval is conditional on
independence; related stems and shared host load are documented limitations.

## Baseline verification — October 13, 2026

Native host: macOS 26.7.1 ARM64, Apple Clang 21.0.0, C++26 mode. The full
`make -j2 test` and `make -j2 MODE=sanitize test` suites passed, including
AddressSanitizer and UndefinedBehaviorSanitizer. These checks exercised legal
move generation/perft, FEN and state restoration, real-network evaluation,
incremental refresh/backtracking, hostile-file rejection, search limits and
draw/mate rules, and UCI lifecycle behavior. The ordinary UCI suite also tests
launching by bare executable name through PATH from a different directory.

The pinned network SHA-256 was verified locally. Exact upstream NNUE comparison
is documented with corpus/output digests and reproduction commands in
[NNUE](NNUE.md). This is finite-corpus compatibility evidence, not a formal proof
for every possible position or network. A local benchmark completed with saved
binary/network/position hashes; it provides no Elo or match-strength evidence.

Three foreign targets cross-compiled; they were not executed. See
[portability](PORTABILITY.md) for compiler/runtime details and remaining gaps.
No tournament results, measured Elo rating, parallel search validation, or
training outcome is claimed for this baseline.

## Independent referee checks — October 13, 2026

`make verify-moves` compares every legal root move and each perft branch with
the pinned `chess==1.11.2` reference. The release binary passed all 93 depth-2
cases: 64 deterministic reachable random positions and 29 initial/special/mirrored
fixtures. A depth-3 check also passed all 37 cases (8 random plus the fixtures).
A deliberately incorrect mock engine produced failure records and a nonzero
exit status. These are correctness checks, not strength measurements.

The default seed is `18938320320349523`; the ordered FEN corpus SHA-256 is
`d2d60c101811d895dc3dc309f0f4079258aedab9937abf15a25b46a56cbd28d4`.
The checked binary SHA-256 is
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
The ignored `results/move-verification.json` contains the full inputs, branch
comparison summaries, tool hash, and environment metadata.

## Match-runner verification — October 13, 2026

`make test-match` passed 17 paired-statistics tests and 13 subprocess/referee
integration tests. Coverage includes swapped colors, full opening history,
PGN replay, illegal/null opening rejection, protocol errors and timeouts,
readiness excluded from the chess clock, real clock losses without a credited
increment, resource overrides, artifact changes, and inference exclusions.

A real two-game smoke run against the separately built pinned Stockfish 19
completed with no protocol failures, truncations, or clock losses. Both games
ended in checkmate; chess0live lost both. Settings were 1 second plus 0.01 seconds
per move, one thread, 64 MiB hash, 20 ms move overhead, seed `20261013`, one pair
from the development suite (`development-02`), and a 256-ply safety limit.
Both PGNs replayed legally to the recorded final positions. This deliberately
short run validates the workflow; it is not a blitz rating or evidence for a
strength margin. No confidence interval is produced.

Evidence is in ignored `results/match-smoke-sf19-20261013/`: the manifest, frozen
opening suite, game records, PGNs, raw protocol logs, and summary. The manifest
records source labels, runner/binary/network hashes, platform and actual options.
See [match testing](MATCHES.md) for the separate opponent build and its PGO flags.

## Owner-run GUI feedback — October 14, 2026

Two newly supplied 180+2 Cute Chess games against Gargantua 2.1 completed with a
draw as White and a checkmate loss as Black. The owner reports working UCI GUI
integration. Independent replay verified all 169 plies and both terminations;
the frozen snapshot's legal move sets and native/scalar/pinned-SF19 NNUE stages
and raw/wrapped outputs agreed at all 171 recorded boards, including initial
positions and repeats. The frozen snapshot's binary hash remains unchanged.

The [feedback report](reports/2026-10-14-cutechess.md) preserves PGNs, digests,
reproduction findings, metadata limits, and next hypotheses. Time allocation
deserves further testing; no immediate engine correctness defect was reproduced.
These two exploratory games establish neither a rating nor a strength gain.

## Phase 2 time-policy checkpoint — October 14, 2026

The opt-in hard-deadline forecast candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
These include the real-network 537-position incremental/full-refresh check,
perft/rule/state tests, deterministic forecast boundaries, interrupted-iteration
accounting, explicit-limit/ponder exclusions, and UCI option/lifecycle checks.
The evaluator and position implementations are unchanged; the full separate
Stockfish parity corpus was not rerun for this time-control-only change.

Tool checks passed: 15 profiler tests, 17 paired-statistics tests, 17 match-runner
tests, and 11 equal-work comparison tests. New match checks verify per-engine
options, advertised types, protected common settings, and frozen configuration.
The profiler checks raw diagnostics, exact node totals, partial failures,
artifact stability, resource changes, and timing-accounting consistency.

Default classic search retained exactly the frozen `0.1-dev-4b8b35d` signatures
at all 24 fixed-depth comparisons, including warmups (three roots, depth 5,
three measured repetitions per binary). Timing variation does not establish a
throughput improvement. The optional forecast changes clock allocation, so
clock-managed profiles are assessed for completed depth and moves as well as
time and interrupted work; they do not require identical final results.

The [experiment record](TIME_MANAGEMENT.md) separates the rejected soft-target
candidate from its hard-deadline revision and preserves both evidence sets.
The two four-game operational smokes completed without errors or time forfeits.
Independent replay verified 577 legal plies for the first and 467 for the revision;
each produced two checkmates and two threefold draws. The revision scored
2W/2D/0L, versus the first candidate's 1W/2D/1L, on the same two development pairs.
Correctness and short operational matches are not a strength acceptance gate.
Classic remained the default; the longer held-out blitz test had not run at
that checkpoint. Its subsequent Phase 2D result is recorded below.

## Phase 2C selective-search checkpoint — October 14, 2026

The conservative LMR candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
The policy tests cover eligibility boundaries, checks, mate windows, special
moves, advanced pawn pushes, and ordering hints. A bounded real-network search
exercises both confirmed and rejected reduced probes, an interrupted iteration,
legal PVs, and restoration of baseline results after switching policies. Existing
rule, limit, cancellation, and ponder cases also run with LMR enabled.

The new profiler passed 12 tests, including different search trees, PV/bestmove/
ponder legality, counter accounting, exact node caps, partial search/readiness
failures, and artifact mutation. The existing 15 clock-profiler, 17 statistics,
17 match-runner, and 11 comparison tests passed. NNUE and position code are
unchanged; their normal 537-position incremental checks passed in all three
build modes. The separate full Stockfish oracle corpus was not rerun for LMR.

The [selective-search experiment](SELECTIVE_SEARCH.md) records the frozen
candidate, default-equivalence check, development profiles, and short game test.
These are finite correctness and operational checks. Reduced fail-lows remain
heuristic; this checkpoint does not establish playing strength or make LMR the
default.

Default-off search matched all 24 frozen-parent samples exactly. The depth-5
profile completed 48 searches and the 200,000-node profile completed 24, with
legal PVs and consistent accounting. The eight-game paired operational smoke
scored 2W/2D/4L for LMR, with six checkmates and two threefold draws, no failures,
time forfeits, or truncations. Its unfavorable score is documented without
turning four development pairs into a strength estimate.
The Linux ARM64, Linux x86-64, and Windows x86-64 binaries also rebuilt and linked
successfully; file inspection confirmed target architectures. They remain
cross-build-only. No RISC-V64 or Windows ARM64 build/runtime evidence was added.

## Phase 2C exchange-ordering checks — October 14, 2026

Native `make -j2 test`, `make -j2 SIMD=scalar test`, and
`make -j2 MODE=sanitize test` passed, including 28 composed/reflected exchange
cases and 4,117 generated comparisons against an independent slow legal-move
reference. Search tests exercise genuine negative-exchange classification,
forced losing-capture retention, warm policy switching in both directions,
interrupted node accounting, and diagnostics invariance. Rule, stop, and ponder
cases run again with SEE enabled. The native-CPU exchange/search/UCI checks also
passed. NNUE's 537-position incremental checks passed in all three full suites;
position and NNUE sources are unchanged, and the full separate SF19 stage oracle
was not rerun for this ordering-only change.

Tool checks passed: 20 isolated search-mode profiler tests, 15 clock-profiler
tests, 17 paired-statistics tests, 17 match-runner tests, and 11 equal-work
benchmark tests. The new profiler checks both modes, required ordering records,
counter consistency, isolation from LMR, and partial failures.

Default ordering matched all 24 frozen-parent signatures. The 48 depth-5
searches retained all final moves/scores/PVs; 24 node-limited searches respected
the exact 200,000-node cap and independently legal PVs. See
[capture ordering](MOVE_ORDERING.md) for work, timing, and acceptance limits.

The predeclared eight-game smoke completed 2W/4D/2L for SEE, with four
checkmates, three repetition draws, and one insufficient-material draw. There
were no protocol errors, time forfeits, truncations, or excluded pairs. These
four development pairs are not a strength or equivalence test. Independent replay
verified 703 legal plies (639 searched), clock records, options, hashes, and
terminations. The three repetition draws were valid next-move claims under the
runner's documented policy. The independent profile audit also checked all
120 depth-5 and 62 fixed-node common-depth score/PV comparisons; all matched.
Audit records and their digest are linked from the ordering experiment.

Linux ARM64, Linux x86-64, and Windows x86-64 builds compiled and linked with
the documented toolchains. File inspection confirmed their architectures; none
was executed. RISC-V64 and Windows ARM64 remain unavailable locally.
The frozen GUI, forecast, LMR, and ordering binaries, pinned network, and reserved
time-validation suite retain their recorded hashes. The local
`results/capture-ordering-20261014/validation.json` records successful commands,
source-snapshot agreement, binary hashes, and these validation limits.

The separate [LMR loss diagnosis](reports/2026-10-14-lmr-losses.md) replayed all
four losses at eight selected roots using the frozen LMR executable. All eight
best moves and 40 common-depth scores/PVs agreed between policies. This is
post-hoc, bounded diagnosis; it neither demonstrates an LMR-specific miss nor
establishes strength or safety of all reduced fail-lows.

## Phase 2D qualification tooling — October 15, 2026

Before the first real campaign, `make test-qualification` passed 21 launcher
checks and 14 independent-auditor checks. They cover immutable settings/assets,
no-search UCI preflight, day/night and daylight-saving boundaries, preserving the
original 07:00 cutoff across readiness, cancellation and child-process cleanup,
incomplete PGNs/journals, legal full-history replay including Black to move,
actual UCI options/clocks, late unplayed moves, pair identity, corrupted evidence,
output-overwrite rejection, and exact predeclared decision boundaries.
`make test-match` also passed all 17 statistics and 17 runner checks.
The real no-search preflight passed with both frozen engine roles: 32 distinct
legal roots, correct applied options and artifact digests, and zero `go` commands.
It recorded the M5 Pro's 18 logical CPUs and 64 GiB RAM, a daytime 50% budget,
one active search worker, and two resident engines estimated at 1.11 GiB total.
This is a worker/memory estimate, not an OS-enforced utilization cap.

These tooling checks are separate from the actual match result below. The
campaign changes no engine source or binary; prior correctness and platform results retain
only their stated scope. The [predeclared protocol](PHASE_2D.md) records the
frozen executable, network, held-out suite, settings, decision rule, and the
owner's one-run daytime exception. All 64 games and the independent evidence
audit were subsequently completed.

## Phase 2D first campaign — completed October 15, 2026

The [frozen time-policy screen](reports/2026-10-15-phase2d-time-policy.md) completed
all 64 games / 32 color-reversed pairs in 2h54m on the M5 Pro. Its independent
audit passed: 7,088 legal plies, 6,240 charged search events, exact game/clock/option
agreement, unchanged pinned assets and tool sources, and zero exclusions,
forfeits, protocol failures, or truncations. Terminations: 21 checkmates,
38 threefold-repetition claims, and 5 insufficient-material draws.

Forecast scored 14W/43D/7L (35.5/64, 55.47%). The conditional two-sided 95%
Hoeffding pair-score interval was 31.46–79.48%; the predeclared decision is
**inconclusive**. No default changes, strength-gain claim, or equivalence claim
follow. Raw evidence and audit hashes are recorded in the linked report. The
completed one-run daytime exception does not authorize another long campaign.

## Phase 2D LMR preparation — October 15, 2026

Before starting the new fixed screen, `make test-qualification test-match`
passed **100 checks**: 21 historical launcher, 14 historical audit, 13 LMR
launcher, 18 LMR audit, 17 statistics, and 17 runner checks. The shared lifecycle
preserves the original time-policy CLI and cutoff behavior. New tests require
the exact LMR toggle, classic timing, 64 distinct roots, no later capture-ordering
option, both 64-pair decision boundaries, and independent rejection of altered
options, missing/extra evidence, wrong protocols, and corrupted game records.
Synthetic replay covers all 128 games without playing the held-out openings.

The actual no-search LMR preflight passed for both frozen engine roles, with
the intended applied options and **zero position/go commands**. The suite has
64 unique legal nonterminal roots, 992 history plies, and no final-root overlap
with all 56 earlier development/general/time validation roots. Its SHA-256 is
`1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7`.
Composition and independent replay used the pinned referee only; no evaluation
or outcome filtering. Source review and whitespace validation passed.

The completed time-policy campaign was re-audited using the generalized audit
code: zero errors and exactly matching original statistics/decision. Subsequent
live-source differences are reported separately, not confused with in-run drift.
Local evidence: `results/phase2d-lmr-preflight-20261015.json`,
`results/openings-lmr-validation-20261015/validation.json`, and
`results/phase2d-time-policy-20261015/audit-shared-protocol-20261015.json`.

These are tooling and preparation checks, not LMR strength results. The
actual games required by the [predeclared protocol](PHASE_2D_LMR.md) completed
separately below. No engine implementation, default, GUI bundle, or frozen
network/binary changed.

## Phase 2D LMR completion — October 16, 2026

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) completed all
128 games / 64 color-reversed pairs at 60+0.6 on the M5 Pro, from October 15
23:00 to October 16 05:41 Helsinki. It used the ordinary nighttime resource
budget, one active search worker, and no daytime override. Both sides used
the frozen LMR executable, classic timing, one thread, 64 MiB hash, and the
pinned network; only the LMR option differed.

The independent data-only audit passed with zero errors: 17,175 legal plies
(including opening histories), 15,191 charged search events, exact game/clock/
option agreement, and unchanged pinned assets and tool/protocol sources during
play. There were no exclusions, forfeits, protocol failures, unexpected stderr,
or truncations. Terminations were 46 checkmates, 71 threefold draws,
10 insufficient-material draws, and one rule-50 draw. A separate independent
review replayed the evidence and confirmed the statistics and decision.

LMR on scored **35W/82D/11L (76/128 points, 59.375%)**. The conditional two-sided
95% Hoeffding pair-score interval was **42.398731053%–76.351268947%**. The
predeclared decision is **inconclusive**; LMR remains off and no strength gain
or equivalence is established. The report records sampling limitations, raw
evidence hashes, and reproduction instructions. The original audit and frozen
protocol remain intact; later documentation edits are separate live-source
differences. All frozen executables, the network, and GUI `0.1-dev-4b8b35d`
were preserved. No engine rebuild or additional GUI validation was needed for
this tooling/evidence checkpoint. All campaign processes have exited.

A post-documentation re-audit also passed with identical game/statistical
evidence. Its only differences from the original audit are the audit timestamp
and the two expected live status-document changes (`SELECTIVE_SEARCH.md` and
`PHASE_2D_LMR.md`). Local record:
`results/phase2d-lmr-20261015/audit-after-documentation.json`.

## Phase 3A performance baseline — October 16, 2026

The [measurement checkpoint](reports/2026-10-16-phase3a-baseline.md) completed
on the M5 Pro under the normal 50% daytime budget. Engine source is unchanged
from `9daaade`; the separate release build is byte-identical to the frozen
capture-ordering executable. Position/perft, exchange, NNUE (537 incremental
positions), search, policy/time, UCI, and resource checks passed. An initial
PATH smoke in the custom nested build directory failed to find its default
network; an adjacent symlink to the pinned network fixed the bundle setup,
and `test-core` then passed. Both logs are retained; no engine fix was required.

All 11 comparison-tool checks and 16 new CPU-recorder mock tests passed. The
recorder tests fixed UCI settings, legality, sampling-window bounds, partial
evidence, failures/cleanup, resource changes, and artifact drift. Its first real
attempt was denied process inspection by the sandbox; the approved retry used
a new output path and completed. No failed record was discarded.

All **192 same-binary searches** (12 roots, depth 5, seven measured repetitions
plus warmups) matched exactly. All **48 optimized-symbol/release searches**
also matched. Independent replay verified every iteration's PV, bestmove, and
ponder. Median same-binary time ratio was 0.998546, paired MAD 0.008123; these
describe repeatability, not a speedup or confidence interval.

The separate 120-second CPU sample verified target identity, 1 ms requested
interval, 12 warmups, and all **24 sampled searches** within its conservative
window. Their signatures and moves also matched the release baseline. Two
independent call-tree aggregations agreed: 7,413 search observations, of which
6,304 were in NNUE, including 4,351 in update and 1,935 in inference. Nested
counts overlap. Main-thread idle observations were excluded; aggregate stacks
do not establish per-root sample counts or exact CPU-cycle percentages.

All frozen engine/network/build/benchmark artifacts matched after measurement;
the new Makefile test target and final docs were added afterward. Raw evidence,
failure records, and independent audits are in `results/phase3a-20261016/`.
GUI `0.1-dev-4b8b35d` remains intact. Scalar/sanitizer/full oracle suites were
not rerun for this measurement-only checkpoint. The subsequent
[NNUE update experiment](PHASE_3B.md) reran them as recorded below.

## Phase 3B batched NNUE updates — October 16, 2026

The [isolated batch update](reports/2026-10-16-phase3b-nnue-batching.md) passed
native, forced-scalar, and ASan/UBSan engine suites. These include perft/rule/state,
UCI, search, exchange, timing/search-policy checks, and the 537-position real
network incremental/full-refresh suite. The new test-only arithmetic oracle
adds 360 transitions per build, checking all hidden/PSQT lanes with signed
int8/int16 columns, duplicates, extreme modular arithmetic, empty/partial/full
batches, large changes, and reversal. Its independent multiplicity map and
column-at-a-time arithmetic do not share the production batching kernel.

A fresh external SF19 oracle run passed all **2,057 positions** for native and
scalar, with unchanged corpus, feature/accumulator/layer-stage, and raw/wrapped
output hashes. It used a copied isolated reference checkout and new output
directory `build/nnue-oracle-phase3b-20261016/`; previous oracle evidence survives.

Before timing, all 96 depth-5/depth-6 searches matched exact per-iteration
depth/seldepth/nodes/score/PV, bestmove, and ponder, with independent legal replay.
The three subsequent timing runs also matched. The independent final audit
checked **576 searches**, 3,024 PV lines / 10,572 legal PV plies, and all bestmoves
and ponders, plus identities, raw-reply signatures, runner/asset hashes, histories,
counts, options evidence, independently recomputed timings, and acceptance gates.
Negative checks confirmed rejection of tampered ratio metadata and an illegal PV.

Median baseline/candidate elapsed ratios were **1.078081, 1.079836, 1.083612**;
all exceeded 1.03 and all 24 pooled root/depth medians exceeded 0.98. There were
no observed individual measured slowdowns. The declared result is **retain**
for sampled opening-search performance, without a statistical confidence or Elo
claim. Settings, thresholds, implementation, and all runs were preserved.

Raw records and test logs: `results/phase3b-20261016/`. Candidate release SHA-256:
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.
The ordinary native executable was rebuilt after measurement and is byte-identical.
All prior frozen candidates, GUI `0.1-dev-4b8b35d`, and the pinned network remain
intact. One active worker/two resident engines were used during comparisons,
within the ordinary daytime budget. All jobs ended; no match or schedule exists.
Broader game phases, clock-managed strength, scalar throughput, and foreign
runtime execution were not established by these measurements.

## Phase 3C game-phase validation — October 16, 2026

The [completed comparison](reports/2026-10-16-phase3c-gamephases.md) used 12
original composed FENs, selected before engine evaluation/timing: six middlegames
at depth 6 and six endgames at depth 8, with balanced turns and all eight NNUE
material buckets. The pinned referee confirmed validity, nonterminal/non-drawn
roots, uniqueness, and no overlap with 120 earlier opening roots. Historical
reachability and earlier repetition history are not claimed.

All six frozen comparisons completed in 844.997 seconds with one active worker
under the normal daytime budget. All **432 searches** matched exact per-depth
results; independent raw-reply replay verified **3,024 PVs / 14,904 plies** and
432 bestmoves/ponders. There were no timeouts, exclusions, operational failures,
or asset/source changes. The 11 comparison-tool checks, synthetic descendant
cleanup check, five audit corruption checks, and eight classification/boundary
checks passed. Raw evidence is `results/phase3c-20261016/`.

Both same-binary controls passed repeatability gates. Middlegame ratios
**1.087243 / 1.088055** passed the positive, duration, and pooled-root guards.
The endgame ratios/guards were favorable too, but `gamephases-eg-05` took
30–32 ms, below the predeclared 50 ms floor in all six role/run medians. Endgame
and combined qualification are therefore **inconclusive**. No candidate
slowdown appeared among 120 measured candidate pairs, but favorable ratios
cannot override the duration gate. No roots or thresholds were changed.

Engine code, normal/frozen binaries, defaults, and GUI `0.1-dev-4b8b35d` are
unchanged. Native/scalar/sanitizer/full NNUE oracle checks retain their Phase 3B
scope; they were not rerun for this validation-only phase. No strength gain,
release, new platform execution, or universally faster endgame play is claimed.
The subsequent baseline-only characterization is recorded below; Phase 3C's
decision remains unchanged.

## Phase 3D workload characterization — October 17, 2026

The [completed diagnostic](reports/2026-10-17-phase3d-workload.md) ran the same
frozen Phase 3A baseline in both roles at depths 8–12 for `gamephases-eg-05`.
All **40 searches** matched exactly within depth and all common iteration
prefixes matched across depths. Independent replay verified **400 PV lines /
2,296 plies**, 40 bestmoves, and 40 ponders. No engine code or binary changed.

Depth 12 is the shallowest tested level meeting the predeclared 200 ms minimum,
5-second maximum, ratio [0.97, 1.03], and MAD ≤0.03 proposal rule. Role medians
were 329.881/322.562 ms; ratio 0.999090 and MAD 0.028507. Depth 10's ratio/MAD
failures are retained. This is a three-pair engineering heuristic with a
near-limit MAD, not proof of durable repeatability or candidate improvement.

The 11 comparison-tool tests, two launcher mock cases, syntax check, 35 frozen
input integrity checks, and 20 auditor corruption/selection/prefix checks passed.
Cleanup functions were AST-checked against the previously tested Phase 3C
launcher; its real descendant test was not rerun. The first auditor attempt
failed on an auditor-only API typo before reading search data. Its `audit.json`
is preserved; the repaired auditor passed in **`audit-final.json`** without raw
measurement changes. Native/scalar/sanitizer/full NNUE oracle checks retain
their Phase 3B scope and were not rerun.

The campaign completed in 7.441256 seconds with one active worker under the
ordinary daytime budget. All jobs ended, no schedule is active, and preserved
GUI `0.1-dev-4b8b35d` is unchanged. Raw evidence is
`results/phase3d-20261017/`. Phase 3E needs a separately frozen complete endgame
comparison with fresh controls. Phase 3C remains inconclusive for endgames;
no release, Elo gain, or new platform execution is claimed.

## Phase 3E endgame requalification — October 17, 2026

The [new complete comparison](reports/2026-10-17-phase3e-endgames.md) tested all
six original endgames with the Phase 3D pawn workload at depth 12 and other roots
at depth 8. Fresh controls and two candidate rounds each used five measured
pairs per root plus warmups; no older timing data was pooled. All **216 searches**
matched exact per-depth signatures across roles/repetitions/rounds. Independent
replay checked **1,872 PV lines / 10,512 plies**, 216 bestmoves, and 216 ponders.

The complete control passed median 0.998927 and MAD 0.003985 plus all root
guards. Both complete candidate rounds passed the positive gate at **1.089113 /
1.084243**. All 36 role/root/round medians exceeded 50 ms (minimum 298.212 ms),
and all pooled ten-pair root medians exceeded 0.98 (minimum 1.049976). The result
is **qualified on this revised composed endgame sample**. Two individual
candidate slowdowns, control outliers, and absolute-time drift remain included.
The 16/14 role-order imbalance is documented. No confidence or Elo claim follows.

The 11 comparison-tool tests, three launcher mock cases, syntax checks, suite
referee checks, 29 independent auditor checks, and 37 frozen-input checks passed.
The auditor also checked settings/identity, raw summaries, canonical root mapping,
complete-round aggregation, expected counts/order, resources, and campaign
lifecycle; a separate reviewer independently replayed all searches and recomputed
gates. Cleanup functions match the previously tested Phase 3C implementation;
the real descendant cleanup test was not rerun. Native/scalar/sanitizer/full
NNUE oracle suites retain their unchanged Phase 3B scope and were not rerun.

The campaign completed in 353.663077 seconds within its 600-second cap under
the ordinary daytime budget, with one active worker and two resident engines.
All jobs ended; no schedule is active. Raw evidence is
`results/phase3e-20261017/`. Engine code, defaults, normal build, and GUI
`0.1-dev-4b8b35d` are unchanged. Phase 3C's original endgame/combined decisions
remain inconclusive; this result establishes no new release or platform runtime.

## Phase 3F dense inference — October 17, 2026

The [fixed protocol](PHASE_3F.md) and [full report](reports/2026-10-17-phase3f-dense.md)
record the retained four-output NEON kernel. Native, forced-scalar and ASan/UBSan
full suites passed, each including **1,515 independent dense cases / 84,126 output
comparisons**, **360 update transitions**, and **537 incremental positions**.
The fresh isolated SF19 oracle matched all **2,057 positions**, every integer
stage and raw/wrapped score, retaining the earlier corpus and output digests.
Scalar inference and the singleton-output path remain unchanged.

The 96 release/symbol searches and 72 profile searches passed independent exact
and legal checks. Two independent raw-stack aggregations agreed. The fixed
nighttime performance campaign completed all **576 searches** in 746.807169
seconds with one active worker: **3,552 legal PV lines / 15,840 plies**, plus
576 bestmoves/ponders. Every root signature matched across roles/repetitions.
All 55 frozen inputs, settings, orders, resources, and lifecycle checks passed.
The control, duration, pooled-root, and both-round improvement gates passed in
all three phases. Opening ratios were **1.196321/1.195963**, middlegame
**1.196515/1.213653**, endgame **1.324133/1.394803**, versus retained Phase 3B.

All four individual slowdowns, substantial absolute-time drift, and candidate
endgame dispersion remain included. These observations limit generalization;
no Elo, scalar speed, foreign-platform execution, or release claim follows.
The recorder's 21 mock tests, launcher's 23 cases, and auditor's 52 checks passed.
No failed audit attempt or repeated measurement campaign occurred. Original GUI
`0.1-dev-4b8b35d` and all old frozen binaries remain intact. Normal native output
was promoted after the successful audit and is byte-identical to the qualified
candidate; `final-integrity.json` explicitly records that one intentional change.
The optional new GUI snapshot passed a CLI smoke, not a Cute Chess GUI test.

## Phase 3G qualification preparation — October 18, 2026

The [fixed protocol](PHASE_3G.md) and original opening assets were committed as
`c177804` before any games. The legal-move-only generator reproduces all four
shards and metadata byte-for-byte: **256 distinct full histories**, 64 per
shard, 128 roots per side to move, disjoint from all 132 earlier opening and
performance roots. No continuation was rejected during generation; no engine
evaluation or outcome selected these unevaluated positions.
The tested supervisor, auditor, and lifecycle fixes are recorded in `ff478a7`.

The latest relevant suites pass **172 tests**: 15 opening-generation tests,
24 supervisor/lifecycle tests, 33 aggregate/raw-auditor tests, and 100 historical
match/statistics/qualification tests. Reproduce with
`make PYTHON=python3 test-match test-qualification`. The combined run included
23 launcher cases; the final additional shutdown-cancellation case and all
24 launcher cases passed after that launcher-only fix.

Lifecycle checks use fake UCI processes and synthetic tasks. They verify four
concurrent workers, aggregate CPU/memory rejection and owner-policy changes,
the common cutoff and DST handling, missed monitoring, input drift, invalid
games/stderr, valid scored clock forfeits, and cancellation during shutdown.
Eight real **fake-UCI** subprocesses were checked for disappearance after
repeated SIGINT/SIGTERM, including unresponsive quit. Cancellation now finishes
both engines' cleanup and evidence persistence before propagating; a stopped
worker cannot silently admit the next game. Whole-supervisor finalization is
protected against a first signal arriving during an existing failure cleanup.

The auditor's 28 aggregate tests use synthetic 512-record campaigns with mocked
child audit results. Five separate tests exercise the actual inherited raw
PGN/UCI verifier on 128-game synthetic fixtures, including transcript, PGN,
clock, stderr, and partial-run corruption. Threshold subcases cover 299/299.5
and 212.5/213 points. Master tests cover shard identity, full histories/colors,
all 512 resource admissions, periodic gaps, preflight searches, source/pin
drift, incomplete evidence, and refusal to overwrite. Independent code review
found and resolved lifecycle and resource-timestamp issues before completion.

A real **readiness-only** check passed on the pinned Phase 3F executable for
both LMR roles, with zero `position` or `go` commands. The record is
`results/phase3g-preparation-20261018/preflight.json`; its two UCI transcripts
also passed the independent auditor's preflight checks. All four child profiles
match the launcher/auditor pins and current source snapshots. Aggregate engine
memory reservation is about **4.44 GiB**, an estimate rather than an OS limit.

During v1 preparation, no actual Phase 3G strength game, reserved-position search,
performance run, or C++ rebuild was performed. Both GUI snapshots and the normal
executable remained unchanged. The real campaign had **not yet run**;
synthetic lifecycle tests and readiness do not establish its completion,
playing strength, or foreign-platform execution. LMR remains off, and no
automatic schedule or new release exists.

## Phase 3G daytime amendment — October 18, 2026

Before the first game, the owner explicitly authorized a daytime exception and
requested that its protocol change be prepared and validated before launch.
Protocol `phase3g-lmr-512-v2` adds `--allow-daytime`, limited to October 18
07:00–23:00 Helsinki and recorded as `owner-20261018-phase3g`. The normal
50% daytime / 80% nighttime resource limits and original next-07:00 cutoff
remain; the daytime launch has a longer possible wall-time allowance. The
256 pairs, 512 games, four active workers, engine/network, settings, openings,
and decision rules are unchanged. No engine code or README text changed.

`make PYTHON=python3 test-match test-qualification` passed **189 tests**:
34 match/statistics, 15 opening-generation, 29 coordinated-launcher, 45 aggregate
and raw-auditor, and 66 historical qualification checks. New cases cover exact
date/time boundaries, missing or forged authorization, strict permission flags,
master/child agreement, the unchanged daytime allowance, readiness crossing
23:00, cutoff expiry before startup, and ordinary DST transitions. Full fake
process cancellation and existing raw-evidence corruption checks still pass.
Expected command-line rejection messages are negative test cases, not failed
suites. A separate read-only review found no blocking issue and independently
checked ten window cases plus naive-clock rejection.

Fresh real two-role readiness passed with zero position/search commands and
independent transcript audit. Evidence is
`results/phase3g-preparation-20261018/daytime-v2-preflight.json`; original v1
readiness files are preserved. The v2 record matches all current frozen sources
and assets; its fixed configuration and engine/network/opening artifacts are
identical to v1. Its authorization preview is not a game-start record. The
amendment is committed locally before the one authorized campaign starts in
`results/phase3g-lmr-20261018-daytime/`. Actual outcome and strength qualification
remain pending; no restart, schedule, or default promotion is implied.

The tested amendment was committed as **`fce2539`**. The first real attempt
started **October 18 at 08:54:00.810565 Helsinki**, with all four shards running
and initial admission/resource observations within the normal 50% daytime
budget. The shared cutoff is **October 19 at 07:00 Helsinki**. The campaign
manifest and append-only resource journal record the actual launch; readiness
alone did not establish it. The completed outcome is recorded below.

## Phase 3G completed screen — October 18, 2026

The one authorized attempt finished **15:12:09.041757 Helsinki**, after
6 h 18 min 8.231192 s. All four shards completed 64 pairs / 128 games each;
all **256 pairs / 512 games** remain included. The unchanged independent
`tools/audit_phase3g.py` passed on its first full-campaign audit with zero
errors and no live-source differences. It replayed **60,323 legal plies** and
verified **50,352 charged search events**, full PGNs/UCI histories, actual
options, terminations, paired colors, aggregate resource records, the dated
authorization/cutoff, and unchanged before/after source and asset hashes.

LMR-on scored **225W/155D/132L, 302.5/512 points (59.08%)**. The conditional
95% pair-score interval is **50.5939–67.5702%**. Six candidate clock forfeits
and seven baseline clock forfeits are valid scored outcomes. The candidate
forfeits trigger the first frozen rule: **operational regression; no default
change**, even though 302.5 exceeds the numerical 299.5-point boundary.
No games were replaced, excluded, replayed, or appended. Both roles having
clock losses does not establish their cause or make the candidate acceptable.

See [the result report](reports/2026-10-18-phase3g-lmr.md) for evidence hashes,
per-shard results, limitations, and audit reproduction. Raw evidence and the
original `audit.json` remain in `results/phase3g-lmr-20261018-daytime/`.
No C++ changes, rebuild, new engine tests, or further games were needed for
this data-only audit and documentation checkpoint. Phase 3H will investigate
clock reliability before any fresh confirmation. Both GUI snapshots and the
README remain unchanged.

## Phase 3H command-time accounting — October 18, 2026

A cold-network `go movetime 1` reproduced uncharged preparation in both LMR
modes: 68.6–73.5 ms externally, about 1 ms internally, and 217/219 searched nodes.
The repaired UCI path carries receipt time into search; the expired request now
performs zero tree work while reporting the preparation time. The API also has
deterministic already-expired positive-clock tests for both colors/modes, explicit
limits, pondering, infinite/no-clock search, future origins, and extreme-past
arithmetic. A review-found extreme-past overflow risk was fixed before final
validation; final native, scalar, and Address/UndefinedBehaviorSanitizer suites
passed. No NNUE math changed or new full SF19 oracle run is claimed.

The diagnostic tool's seven focused tests pass. It independently checks legal
PV/bestmove, diagnostic accounting, clock bounds, restricted commands, no
overwrite/resume, and failure records. All **52** prescribed probes completed:
13 full histories × both LMR modes × frozen/repaired binaries, fresh tables and
readiness each time. Every move was legal and received before its original
remaining clock. Both executables had at most 0.003 ms reported hard-deadline
overshoot in this sample. This fails to reproduce the original losses and is
not a match, strength result, or proof that the repair solves scheduler stalls.

The final fixed-depth comparison matched all 48 search signatures (12 development
roots, one warmup and one measured search per executable at depth 4). Timing is
not used as a performance claim. All historical artifacts and both GUI bundles
were preserved. See [the result report](reports/2026-10-18-phase3h-clocks.md) for
source provenance, limited causal findings, artificial suspension control,
commands, and evidence hashes. Phase 3G's operational decision remains unchanged.

## Phase 3I callback receipt — October 18, 2026

The match runner previously timestamped each line after logging earlier lines
in the same callback. The deterministic pre-fix reproduction charged 250 ms to
a reply already received at 50 ms, falsely exceeding a 100 ms clock. The retained
fix timestamps complete batches before logging/dispatch, preserves the pinned
parser, and avoids reentrant-command timestamp inversion. Eight focused tests
cover slow logging, split/UTF-8/CRLF input, errors, cleanup, and genuinely late
callbacks. `make test-match test-qualification test-phase3g test-clock-probes`
passed all 212 checks, including eight tests for the new receipt-control tool.

All 12 prescribed live controls completed on the unchanged Phase 3H executable.
Four normal requests were on time; four consumer-sleep requests reached the
reader on time but were consumed late; four deliberate engine pauses produced
late internal and external observations. Independent replay validated 12 bestmoves,
12 ponders, and 76 PV lines / 320 plies; input hashes and resource policy matched.
These are controlled mechanisms, not a clean operational match or proof of
historical causation. The reader is a thread in the same process, and timestamps
do not identify kernel arrival. The [report](reports/2026-10-18-phase3i-receipt.md)
records exact timings, source pins, limitations, and preserved raw evidence.

No engine source/default changed or engine rebuild occurred, so no new full
native/scalar/sanitizer or NNUE oracle run is claimed. Both stable GUI bundles,
the normal release binary, and the README introduction are unchanged. Phase 3G
retains every original flagfall and its operational-regression decision.

## Phase 3J persistence isolation — October 18, 2026

All 230 match/qualification/audit/clock-probe checks passed in 11 invocations,
including 15 new bounded-writer tests and three resource-supervisor tests.
Coverage includes slow writes across separate callbacks, ordering, byte/record
overflow including in-flight writes, open/write/flush failures, bounded writer
timeout, cancellation, journal ownership, and incomplete evidence publication.

The predeclared four-game, two-shard canary injected 100 ms into every protocol
write and finished in 220.986 seconds. Its independent evidence audit passed:
398 on-time search replies, 430 legal plies including openings, 2,516 legal PV
lines / 7,174 PV plies, 396 legal ponders, consistent PGN/journal clocks, and
unchanged source/asset pins. There were 3,878 measured delayed writes; 396
bestmoves arrived during the other shard's write delay. No protocol, storage,
queue, or clock failure was recorded.

Full operational acceptance **did not pass** because one game hit the declared
128-ply limit. The other games ended in two checkmates and one repetition draw.
The capped game is retained as `*`, without extension or replacement. This
finite mechanism check establishes no strength or general reliability claim.
See the [report](reports/2026-10-18-phase3j-persistence-puzzles.md), frozen plan,
and raw `results/phase3j-20261018/canary/` plus independent audit. The next
operational screen must be separately declared; old campaigns remain unchanged.

## Owner-run GUI feedback — October 18, 2026

The owner reports two draws against Gargantua 2.1 with no engine errors or
disconnections. Intended snapshot: `0.1-dev-phase3f-20261017`; actual executable
identity and UCI options were not captured. The [review](reports/2026-10-18-cutechess.md)
preserves the supplied partial 180+2 PGN byte for byte. `chess==1.11.2` accepted
all 121 plies / 122 positions, and the preserved Phase 3F executable's legal
root sets and all depth-2 divide branches matched at every saved position.

The PGN ends unfinished at 61.Nc3. The owner clarified that they manually
adjudicated game 1 drawn, judging it would finish drawn and wanting to save
the PGN before the GUI advanced. This identifies the summary's user-adjudicated
draw; a played-out or forced draw was not independently verified. Game 2's
ending cannot be replayed without its missing PGN. Rounded thinking times support
early clock depletion, not a proven deadline overrun. No NNUE oracle rerun,
timed search, rebuild, strength match, or new schedule was performed. The review's
local script initially failed on an integrity-record field name after move
checks; its corrected rerun passed. Both GUI binaries and all Phase 3G source
and artifact pins remain unchanged. This is exploratory feedback, not strength
qualification; Phase 3G had not started at the time of that feedback review.

## Release gates

1. **Position correctness:** standard perft vectors and divide diagnostics;
   castling transit attacks, pins, en passant exposing a king, all promotions,
   mate/stalemate, legal-move membership, and complete make/unmake restoration.
2. **Position and input integrity:** FEN rejection without partial state changes,
   deterministic hashes, relevant en-passant repetition keys, reversible clocks,
   promotion/capture handling, and sanitizer-clean tests where available.
3. **NNUE interoperability:** verified network digest and bounded file parser;
   exact active feature indices, integer accumulators, PSQT, and raw outputs
   against the pinned independent test oracle. Incremental evaluation must equal
   refresh across legal sequences and reversals, including every special move.
   Every enabled optimized kernel must equal scalar output.
4. **UCI lifecycle:** handshake, readiness during search, legal best moves, stop
   responsiveness, repeated go/stop, new games, position replacement, hash/network
   changes only after search joins, pondering/infinite result timing, EOF/quit.
5. **Search:** mate distance and score bounds, check evasions at quiescence,
   repetition and rule-50 precedence, terminal positions, node/depth/time limits,
   and deterministic bounded searches. No neural-network-free fallback disguised
   as NNUE strength.
6. **Platforms:** record the exact compiler, standard library, flags, target,
   network digest, and native/VM/emulated/build-only validation for each target.
7. **Performance and strength:** report repeatable benchmarks and local matches.
   A functional 0.1 need not beat Stockfish; no Elo claim without match evidence.

## Annotated puzzle input — October 18, 2026

The exact owner example rejected by `65a5313` with `expected moves` now loads.
Native, scalar, and ASan/UBSan `make -j2 test` passed, including strict board and
counter validation, transactional rejection, ordinary UCI histories, and exact
search signatures with correct, wrong, or absent answer metadata. All 39 supplied
workbook positions (four with omitted counters) matched independent
`chess==1.11.2` legal depth-2 divides and three-way depth-2 search signatures:
frozen Phase 3H plain FEN, new plain FEN, and new annotated FEN.

One requested-style `go movetime 60000` example completed in 59.983 seconds,
returning `f5f6` (Qxf6+) at completed depth 8 / centipawn score 1206. It did not
report mate in seven. Raw source digest, per-position checks, before/after
transcripts, and suite logs are under `results/phase3j-20261018/`.
New native executable SHA-256:
`fa329663e4c9f8e07ecb495f1d7f069ffb4d6fdd4f320365eaf7fd25d5ca9637`.
This checks compatibility and finite search parity, not puzzle answer accuracy,
an engine strength gain, or cross-platform execution.

## Strength measurement

Freeze the two binary hashes, code commits, network digests, clock settings,
thread count, hash size, affinity policy if used, and opening suite digest before
a match. Match resources between engines. Disable ponder and books unless the
experiment explicitly gives both the same access. Play each opening with colors
reversed. Do not tune against the held-out validation set.

Save full PGNs, errors, forfeits, time losses, and machine metadata. Use a
predeclared sample size or a justified sequential test; do not repeatedly peek
at a conventional confidence interval and stop as soon as it turns favorable.
Paired openings produce dependent games: estimate uncertainty at the pair level,
not by pretending each game is independent. Report W/D/L and score with an Elo
difference and uncertainty only when the statistical assumptions are satisfied.

Initial focus is blitz. Exact time controls, opening-suite selection, and sample
sizes are experiment configuration, not invented product achievements. A
statistically positive difference does not automatically mean 'decisively
stronger'; report the measured margin and uncertainty. Absolute 4000 Elo requires
a named calibrated rating pool. NPS, search depth, and solved tactics alone do not
establish playing strength.

## Experiment records

Record hypothesis, parent commit, changed parameter/code, exact command, resource
policy, input hashes, raw results, interpretation, and keep/revert decision.
Keep large generated results, networks, and external reference builds outside
the source tree or ignored. Retain concise result summaries with reproducible
commands when publishing a claim. Test-only Stockfish code must never become an
undeclared dependency of the shipped engine.

## Phase 3K console diagnostics — October 18, 2026

Native macOS ARM64 `make -j2 test`, `make SIMD=scalar -j2 test`, and
`make MODE=sanitize -j2 test` passed. Expanded UCI coverage exercises board aliases,
view-only rotation, FEN/key/evaluation/search preservation, missing networks,
in-check labels, input rejection, start/Kiwipete/terminal perft counts, readiness,
stop, position replacement, and quit during deep diagnostic counting. Legacy
perft/divide and raw evaluation records remain compatible.

An independent `chess==1.11.2` replay checked 93 positions (29 special/start
fixtures and 64 reachable positions, seed 2026101813), all 1,945 legal roots and
51,736 depth-2 nodes, with both display orientations and complete position state.
Thirty-six bounded searches matched every completed depth/node/score/PV, bestmove,
and raw evaluation across the frozen previous binary, new binary, and new binary
after display/perft commands, with LMR off and on. No speed or strength claim
follows. Native executable SHA-256:
`5063b483406d5b8061db330b070962e1665c196870c9a7968a18752432f3894f`.
Raw checks and suite logs are in `results/phase3k-20261018/`. A separate startpos
`go perft 5` example returned 4,865,609 nodes with all 20 root rows.

The predeclared [Phase 3K](PHASE_3K.md) operational screen passed its first
independent audit: four complete games in 17.135 seconds, three repetition draws
and one insufficient-material draw; no clock/protocol/storage/stderr/truncation
failures. Verified 386 on-time replies, 418 legal game plies including openings,
1,517 PV lines / 4,723 PV plies, 385 legal suggested ponders, and minimum clock
slack 19.225 ms. Four ordinary resource admissions covered two active workers /
four resident engines; all eight engine PIDs across the games were closed.
Source/assets, clocks, PGNs, options, and summaries matched. The independent
checker accepted a synthetic fixture and rejected six deliberate corruptions.
See the [report](reports/2026-10-18-phase3k-console-operations.md) for pins and
scope. This is a bounded operational pass, not a strength or general reliability
claim. Historical results/defaults are unchanged; Phase 3L preparation remains next.

## Phase 3L console format and mate reporting — October 18, 2026

At the owner's request, explicit board/evaluation/help/perft commands now print
plain text. Standard search and error output retains UCI formatting. The native
`make -j2 test` suite passed. UCI regressions verify plain output and retained
board/state/cancellation behavior, ordinary centipawn search output, mate +1 and
mate -1 for both colors with exact legal PVs, and mate 0 at a checkmated root.
No search logic changed; the existing engine already supported mate scores.
The static `eval` command does not search for mate. Saved Phase 3K evidence and
its frozen binary remain unchanged.

Independent bounded checks compared 12 old/new depth-4 searches over three
already exposed roots with LMR off/on: every completed iteration's depth,
selective depth, nodes, score, PV, and best move matched. Four signed mate cases
were independently replayed to checkmate. Plain startpos `go perft 5` returned
4,865,609 nodes and all 20 root rows. Raw evidence is in
`results/phase3l-20261018/console-compatibility.json`; the full native test log
is adjacent. Scalar/sanitizer suites were not repeated for this formatting-only
change; their latest execution evidence remains in the Phase 3K report.

The fresh qualification preparation passed 23 generator/exclusion tests,
29 launcher tests, and 42 independent-auditor tests. These 94 checks use
synthetic evidence and fake engines, not qualification games. Reproduction and
explicit original-source verification passed for 256 distinct unsearched roots,
128 per side to move, with zero overlap against 851 cataloged roots from 39
sources. No generator rejection occurred. The catalog covers saved roots, not
every internal search node, and retains explicit missing-source limitations.

Serial readiness passed at 21:16 Helsinki, with both exact configurations,
frozen inputs, and aggregate resource reservation independently audited.
`readiness-audit.json` reports `checked: true`, no errors, and zero held-out
searches. The estimated future four-worker/eight-engine reservation is
4,762,970,592 bytes (about 4.44 GiB); readiness itself loads roles serially.
The launcher correctly reports that a long campaign cannot start at that hour.
No 512-game campaign or schedule was launched. See the
[preparation report](reports/2026-10-18-phase3l-preparation.md) and
[fixed protocol](PHASE_3L.md). This completes preparation only: strength results,
default promotion, release acceptance, and broader platform execution remain open.

## Phase 4A cache reporting and representation — October 18, 2026

Native `make -j2 test`, scalar `make SIMD=scalar -j2 test`, and ASan/UBSan
`make MODE=sanitize -j2 test` passed on macOS ARM64. New checks cover standard
hashfull presence/range, populated occupancy and generation/clear/resize behavior,
terminal reporting, diagnostic accounting and exact on/off search parity, and
packed entry fields/limits/generation wrap/alignment. Twenty optional cache
profiler checks passed; its Make target wiring was dry-run checked.

The parent/instrumented comparison matched all 24 searches. The one compact
layout candidate then matched all 72 profile searches / 36 pairs across declared
exposed roots, cold/warm state, and Hash 1/64: full per-iteration signatures,
occupancy, cache event counts, and independent legal move/PV checks. At Hash 64,
entry storage fell from 48 to 32 MiB with the same 2,097,152 entries. The fixed
36-search timing comparison passed all guards: root median paired ratios
1.010283/0.996622/0.996106, geometric mean 1.000982, all baseline root medians
above 0.1 seconds. Timing is effectively neutral; memory reduction is not Elo.

The final profiler additionally revalidated saved baseline output after review
fixed a capacity-assumption error and strengthened probe accounting. No engine
search result was replaced. Full details, versioned tool evidence, hashes,
scope limits, and the retain decision are in the
[report](reports/2026-10-18-phase4a-cache.md). No new GUI visual test, foreign
execution, full SF19 stage-oracle rerun, long campaign, or release is claimed.
Both GUI snapshots, frozen Phase 3L assets, and search defaults remain intact.

## Phase 4B parallel search — October 18, 2026

Native `make -j2 test` and `make test-smp`, scalar
`make -j2 SIMD=scalar test test-smp`, ASan/UBSan
`make -j2 MODE=sanitize test test-smp`, and ThreadSanitizer
`make -j2 MODE=thread-sanitize test-search test-smp` passed on macOS ARM64.
The optional UCI suite contains 43 bounded cases with an independent legal
referee, and passed under all four build configurations. Direct API checks cover
shared Hash storage, exact global node caps, exceptions/join/reuse, immediate
stop, clock/pondering, root restrictions, and repetition/mate/rule-50 boundaries.
ThreadSanitizer reported no race in the exercised schedules. Twenty-four
profiler tests passed, including input/accounting/failure-path checks.

All 24 parent/candidate one-worker searches matched completed-depth signatures
exactly. Their timing summary suggests a possible small one-worker cost, not a
speedup. The fixed scaling screen completed 72 searches: 18 warmups and 54
measured samples, using three exposed roots, one/two/four workers, 1,000 ms and
depth 6. An independent raw-evidence audit recomputed every ratio and replayed
2,608 legal PV/bestmove/ponder plies. Four workers achieved 3.2505× aggregate
throughput and 2.0933× faster depth-6 latency, with +1 depth in all nine timed
pairs. All current source/binary pins, old GUI bundles, frozen Phase 3L assets,
and the README introduction matched. Four active workers fit the daytime limit
of nine. No long match campaign or automatic schedule was started.

The [report](reports/2026-10-18-phase4b-smp.md) contains exact settings, hashes,
timing variability, reproduction commands, and scope limits. These checks do
not establish an Elo gain, every possible thread interleaving, 64-worker scaling,
foreign-platform execution, or a new GUI visual pass. Threads remains 1 by
default. Phase 4C Syzygy is next; release acceptance remains open.


## Phase 4C — optional Syzygy — October 18, 2026

The [checkpoint report](reports/2026-10-18-phase4c-syzygy.md) records the pinned
reader, separate external data, reproduced failures, checks, hashes, and limits.
Native/scalar/ASan+UBSan full suites and TSan search checks passed. In all four
build modes, the adapter matched 140 exact WDL oracle cases and passed DTZ
outcome/legal-move checks, 47 UCI cases, and six direct clock/stop/node scenarios
with both one and four workers. Fetcher tests (13), profiler tests (25), and
byte-for-byte corpus reproduction passed. The empty-path default preserved all
24 parent/candidate benchmark search signatures; timing was noisy and neutral.

This is finite three-/four-piece evidence, not exact raw DTZ-distance parity,
a seven-piece execution claim, foreign-platform validation, a GUI visual pass,
or an Elo/release acceptance result. Root and interior probes are intentionally
conservative around repetition, halfmove clocks, and PVs. No strength match was
started; existing defaults and frozen campaigns remain unchanged.

## Phase 4D.1 — optional countermove ordering — October 18, 2026

The [report](reports/2026-10-18-phase4d-countermove.md) records the fixed protocol,
artifact identities and bounded decision. Native/scalar/ASan+UBSan suites and
TSan search checks passed; all four builds passed 57 new referee-backed UCI
cases, with direct API tests for counter state, policy switching, special moves,
rules, diagnostics, interruption and SMP. The profiler passed 24 checks. Native
Syzygy regressions remained green. All 180 cold/warm parent/off comparisons
were exact and all 360 on/off profile searches replayed legally.

No broad efficiency improvement was established. The candidate stays off and
further tuning/strength qualification is parked. All final depth-6 scores and
moves matched; intermediate warm score differences are documented rather than
treated as proof of a defect or hidden. No default promotion, Elo claim,
foreign execution, fresh GUI check, or release acceptance follows. Existing
GUI bundles, README introduction, and frozen Phase 3L assets were preserved.

## Phase 4D.3 — optional verified null-move pruning — October 18–19, 2026

Native/scalar/ASan+UBSan full regression suites and ThreadSanitizer search checks
passed on macOS ARM64. All four builds passed 76 new independent-referee UCI
cases and direct API checks for policy resets, diagnostics, legal PVs, real
history, mates, node caps, stop/expiry and one/four-worker joins. Native direct
API execution additionally used real Syzygy fixtures. Deterministic interrupts
at first null-probe entry (33,624 nodes) and first verification entry (33,667)
published no incomplete speculative result and preserved fresh default reuse.
Native/scalar/ASan null-state suites each covered 63 roots, 202 legal children
and 1,045 incremental/full-refresh NNUE comparisons, including exact undo.

The initial TSan UCI activation exceeded its harness's 30-second allowance;
the original failure is retained. A test-only 180-second activation allowance
passed all 76 cases without changing search caps or stop/clock-response waits.
The existing 43-case SMP UCI suite also passed under TSan. Ten timeout-parser
checks and 19 profiler checks passed. Pre-search profiler review repaired local
shutdown-output collection; the frozen shared UCI client was not modified.
The [report](reports/2026-10-18-phase4d3-null-move.md) records exact commands,
raw logs, artifact hashes, repair chronology and finite coverage limits.

All 24 predeclared depth-6 searches completed. The 12 parent/off searches matched
every declared signature, and all six off/on pairs retained each per-depth
score/PV and final move. Cold total nodes fell 16.47%; warm nodes rose 6.08%.
An independent raw-output audit confirmed all 144 iterations, replayed 608 PV
plies and 48 bestmove/ponder plies, recomputed totals, and verified saved pins.
This mixed three-root sample has no speed or strength interpretation. The frozen
LMR match ran concurrently within the shared nighttime resource budget, so raw
timings are not throughput evidence. No default promotion, further null tuning,
new strength campaign, foreign execution, GUI visual pass or release follows.
Null pruning stays off. All existing GUI bundles, frozen Phase 3L/4D.2 inputs
and the owner's README introduction were preserved.

## Phase 4D.2 — completed LMR qualification audit — October 19, 2026

The unchanged independent auditor passed all 1,024 games / 512 pairs, replaying
115,571 legal plies including opening histories and 95,687 search events.
There were no exclusions, audit errors, incomplete games or source/asset drift.
The campaign finished at 05:34:17 Helsinki, before its 07:00 cutoff. Resource
admission and monitoring records passed; they do not measure OS utilization.

LMR-on scored 458W/299D/267L, 607.5 points (59.3262%), with conditional 95%
pair-level bounds 53.3242–65.3282%. Its 19 flagfalls (17 losses, two draws)
fail the protocol's absolute operational gate; the baseline had 65 flagfalls.
Verdict: `operational_regression`, LMR remains off. No general Elo or default
promotion follows. The [report](reports/2026-10-19-phase4d2-results.md) preserves
the favorable score, failure, shared-host development overlap and causality
limits. Keep all raw records and `final-audit.json`; diagnose clock behavior
before any new qualification. No replacement campaign was launched.

## Phase 4D.4 — optional reverse futility — October 19, 2026

Native/scalar/ASan+UBSan full suites and TSan search checks passed. The new UCI
suite passed 78 bounded independent-referee cases in all four builds, with
one/four-worker lifecycle, policy reset, diagnostic, draw/terminal, interruption
and node-limit checks. Pure policy tests cover exclusions, margin/score bands
and integer boundaries. Existing native null interruption and real-fixture
Syzygy search tests passed; the existing 43-case SMP suite also passed under
TSan. The new profiler passed 26 unit checks. These are finite checks, not
proof of optimal play, every thread schedule or a fresh NNUE/TB qualification.

The one predeclared 60-search profile and independent audit passed: 36 process
sessions, 351 iterations, 1,553 legal PV plies and 120 bestmove/ponder plies.
All 12 parent/off pairs matched exactly. At depth 6, total fresh-cache nodes
fell 12.72% and reused-cache nodes fell 1.53%; observed elapsed time changed
−11.51% / +2.28%, respectively. All final fixed-depth moves/scores and all
common-depth score/PVs matched. The six timed comparisons gained one completed
depth on one endgame root, with its final score changing accordingly. This
single exposed repetition does not qualify speed, strength or default promotion.

The [report](reports/2026-10-19-phase4d4-reverse-futility.md) preserves settings,
root variability, commands/logs, hashes and scope limits. All protected GUI and
campaign assets and the README introduction matched. Reverse futility stays
off; no retuning, new GUI visual pass, foreign execution, long campaign or
release acceptance follows.

The separate [84-flagfall audit](reports/2026-10-19-clock-diagnosis.md) verified
92 saved input hashes and recomputed charged durations without accounting
inconsistency. It identified timing-boundary ambiguity, not a proven root cause
or clock repair. No engine or runner timing changed. A short instrumented
diagnostic must precede another qualification match.
