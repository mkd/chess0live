# Phase 4F.16 — deferred move sorting

Date: November 4, 2026. Parent: `e16ca73ed7837c5e79b1cf388b2a1e231d906f5d`.
Decision: **park the candidate; retain the parent engine implementation**.
The [fixed protocol](../experiments/phase4f16-deferred-sort.md) was recorded before
measurement. No playing-strength gain is established.

## Candidate and decision

The independently authored candidate froze all ordering scores before child
search, searched an exact legal contextual TT move first, and sorted the tail
only when a second move was needed. Pending ranks used separate worker/ply
vectors. Quiescence, speculative searches, ProbCut, absent/stale contextual TT
moves and fallback-only hints stayed eager. Tie order, learning prefixes, LMR
indices, search policies, NNUE arithmetic and UCI settings were preserved.

The owner confirmed LM Studio paused in reply to the AC/Automatic readiness
question. One finite comparison ran **16:39:58–16:40:33 Helsinki**, on native
macOS ARM64, one active worker and two resident engines, Hash 64 MiB, depth 6,
LMR on/null off. All fifteen exposed development roots received three cold/warm
repetitions in alternating build order: **180 searches / 90 pairs**. No discarded
warmups, omitted cells, repeated attempts or new games.

All search results matched exactly. The pooled median parent/candidate elapsed
ratio was **1.004784856** (about **0.48%** greater execution rate), below the
predeclared **1.01** minimum. Cold `opening-03` median **0.977854645** also fell
below the **0.98** per-position/state guard; this was the only guard failure.
Both acceptance conditions therefore failed. No threshold or corpus was adjusted.

| State | Pairs | Nodes per build, all repetitions | Median paired ratio | Aggregate elapsed ratio | Parent / candidate seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cold | 45 | 5,552,502 | 1.004211 | 1.015543 | 14.592605 / 14.369260 |
| Warm | 45 | 1,186,068 | 1.008490 | 1.012296 | 2.804374 / 2.770311 |

Ratios are parent elapsed / candidate elapsed; above one favors the candidate.
The aggregate averages do not override the declared median and slowdown gates.
These short observations have no significance interval and establish neither a
universal speed gain/loss nor Elo. Allocation, extra TT-move scanning and retained
storage are plausible costs, but this screen does not attribute the result to
any of them. It does not count actual skipped sorts or measure peak storage.

## Every position/state

Each cell gives the median of three paired ratios, followed by the observed range.

| Root | Cold median (range) | Warm median (range) |
| --- | ---: | ---: |
| opening-01 | 0.995403 (0.992394–1.002003) | 1.008900 (0.995279–1.010913) |
| opening-02 | 1.012917 (0.988873–1.032892) | 1.009256 (0.943575–1.026784) |
| opening-03 | 0.977855 (0.968340–1.012574) | 1.009684 (0.998693–1.023925) |
| gamephases-mg-01 | 0.997180 (0.994774–1.014072) | 0.994394 (0.993688–1.058911) |
| gamephases-mg-02 | 1.081633 (0.995893–1.083410) | 1.007121 (0.996847–1.079014) |
| gamephases-mg-03 | 1.038865 (0.994023–1.040235) | 1.028656 (1.010118–1.037262) |
| gamephases-mg-04 | 1.004698 (1.003544–1.010552) | 1.013470 (0.971665–1.014445) |
| gamephases-mg-05 | 1.004211 (0.976120–1.031016) | 1.026516 (0.969914–1.104659) |
| gamephases-mg-06 | 1.018486 (1.016583–1.025726) | 1.008490 (0.998065–1.008815) |
| gamephases-eg-01 | 1.014547 (1.000462–1.017532) | 1.015987 (1.011409–1.057916) |
| gamephases-eg-02 | 1.004279 (1.000002–1.067800) | 1.004407 (0.992784–1.072728) |
| gamephases-eg-03 | 0.995141 (0.990163–1.019281) | 0.993820 (0.979135–0.995920) |
| gamephases-eg-04 | 0.997137 (0.991054–1.001045) | 1.007097 (0.993137–1.008326) |
| gamephases-eg-05 | 0.997432 (0.982047–1.004641) | 1.016902 (0.978091–1.022379) |
| gamephases-eg-06 | 1.004872 (0.995804–1.021020) | 0.993632 (0.948960–0.994368) |

## Correctness, audit and failures

Before measurement, native, forced-scalar, ASan+UBSan and ThreadSanitizer builds
passed the general Search API and policy checks. Each passed **2,264 eager and
7,260 deferred/boundary ordering comparisons**, **1,408 cutoff-prefix comparisons**,
**23 TT-hint groups with three injected allocation failures**, and **36 continuation
search groups with five injected allocation failures**. New checks exercise
frozen scores after child/history/continuation mutations, separate depth storage,
helper ties, flags, promotions, SEE counts and first/later-cutoff learning. Native
and ThreadSanitizer each passed **43 bounded SMP searches/lifecycle cases**.
The existing profiler passed **29 engine-free tests**. No foreign-target execution
or new external NNUE-oracle result is claimed for this ordering experiment.

Independent source review found no material correctness issue. Independent raw
replay verified **180 cells / 90 pairs, 1,080 iterations, 4,656 legal PV plies,
180 bestmoves and 180 ponders, 37 frozen assets and 27 archived parent sources**.
Completed depth, selective depth, nodes, score, PV and final moves agree across
roles and repetitions. Diagnostics were disabled, so this does not compare LMR
counters. Hash occupancy is range-checked but excluded from exact signatures.
The harness's 300-second search/setup bound excludes final cleanup/hash publication.

Disclosed preparation/audit corrections, all preserved:

- The initial new-test build failed because two fixtures declared a `Position`
  const before calling mutable `legal_moves`; both declarations were corrected.
  The candidate engine itself had compiled. All four subsequent builds/tests passed.
- Audit v1 incorrectly rejected a legitimate Syzygy setup information line;
  v2 then incorrectly rejected the final aggregate `info nodes` line. V3 validates
  both explicitly, passes its valid-input and nine corruption checks, and completes
  the raw audit. These were auditor defects, not engine failures. Original scripts,
  failed audits and logs remain alongside v3.

Both comparison engines exited zero. OS inspection confirmed their PIDs absent
and no chess/compiler/test process remaining; the owner was immediately told
LM Studio could resume. The candidate source/test changes were then restored
byte-for-byte to the parent. The failed candidate remains archived with its
complete patch and isolated executables; it was not adopted into production.
All **701 protected paths**, the owner's existing `tools/batch_positions.py`
modification and exact README introduction are preserved, including stable GUI
`build/test-baselines/0.1-dev-4b8b35d/`, previous campaigns and normal release.
The historical normal-release digest discrepancy and six Phase 4F.13 forfeits
remain unresolved. No clock, default, qualification or release decision changes.

## Evidence and next checkpoint

Local evidence: `results/phase4f16-deferred-sort-20261104/`, including `before.json`,
`pre-screen.json`, archived parent/candidate sources, `candidate.patch`, all build
and test logs, `default-comparison/report.json`, three audit versions,
`os-cleanup.json`, `restoration.json`, preservation and documentation receipts.
The final evidence audit ran against the candidate sources before restoration;
its live-source hashes intentionally describe that archived candidate.

- Parent binary SHA-256: `17f2951611713b8bd4b13dd0aeee892d972e6aaf829b832ad2737f46045f2800`.
- Candidate binary SHA-256: `bf70dc26a61090bbbc22c49217b6b2d2424fa251f045c1ecb47e409d06de147b`.
- Raw comparison SHA-256: `7f940ed00a4415ecf34d9c97b49e46248c7dd0b4e8e7a1755e601cea47169f89`.
- Final `independent-audit-v3.json` SHA-256: `fc09ba2f88a3c35fb18ef9f12dce07759c042fde9bdc15d9221fc53bbdff0be9`.

Proposed **Phase 4F.17: NNUE accumulator reuse across search branches**. The current
evaluator updates from its previously evaluated position; it has no search-ply
accumulator restore/cache. Begin with a bounded current-path profile and explicit
memory/correctness design, then test one reuse hypothesis if justified. Require
feature/accumulator/output parity, reversible state and equal-work timing before
retaining it. Prior NNUE hotspot evidence motivates investigation, not a promised
gain. Strength qualification still separately needs clock readiness and a suitable
window. No implementation, game or automatic schedule for that phase is started.
