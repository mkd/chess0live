# Phase 4D.2: current-engine LMR result — October 19, 2026

**Decision: operational regression under the fixed protocol; keep LMR off.**
All 1,024 games / 512 reversed-color pairs finished and passed the raw-evidence
audit. LMR-on scored 458 wins, 299 draws and 267 losses: 607.5/1,024 points
(59.3262%). However, it had 19 flagfalls; the baseline had 65. Any candidate
flagfall fails the predeclared reliability gate, regardless of the score.

Two candidate flagfalls were correctly recorded as draws because the opponent
had only a king. Thus 19 flagfalls means 17 losses and two draws, not 19 losses.
All flagfalls remain in the scored sample. No game was excluded or replaced.
This is not evidence that LMR has more timing failures than the baseline; it is
the protocol's absolute reliability failure. It does not qualify default use.

## Fixed experiment and audit

The [protocol](../PHASE_4D2.md) and
[preparation record](2026-10-18-phase4d2-preparation.md) remain unchanged.
Both roles used the same frozen Phase 4D.1 executable from `74a908b`, with only
LMR on/off differing: one worker each, Hash 64 MiB, 60+0.6, classic timing,
Move Overhead 20 ms, other experimental policies and tablebases disabled.
Eight shards ran concurrently on the M5 Pro. Preparation was committed as
`d376524` before any held-out search.

The campaign ran October 18 23:13:40 to October 19 05:34:17 Helsinki
(6 hours 20 minutes 37 seconds), ending before the immutable 07:00 cutoff.
The foreground launcher has exited; no resume, extension or automatic schedule
was created. The original engine/input/source pins and resource journal passed
the independent auditor, with no live source differences or audit errors.
Admission records meet the shared resource policy; they are not measured OS
CPU/memory caps.

The raw audit replayed 115,571 legal plies (including supplied histories) and
95,687 search events across all 1,024 games. Complete membership, protocol
options, transmitted clocks, elapsed-time accounting, PGNs, process cleanup,
pair statistics and frozen identities passed. Terminations: 643 checkmates,
257 repetitions, 84 flagfalls, 37 insufficient-material draws, two fifty-move
draws and one stalemate. No exclusions or incomplete games occurred.

The conditional 95% pair-level Hoeffding score interval is
**53.3242–65.3282%**. It passes the numerical score gate, but cannot override
the flagfall gate. Independence between related opening stems and shared-host
observations is unproven. No general Elo, external-opponent superiority,
multi-worker strength or universal no-loss claim follows.

| Shard | LMR wins | Draws | LMR losses | LMR flagfalls | Baseline flagfalls |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 54 | 37 | 37 | 3 | 9 |
| 2 | 55 | 41 | 32 | 3 | 10 |
| 3 | 54 | 44 | 30 | 2 | 7 |
| 4 | 57 | 41 | 30 | 3 | 8 |
| 5 | 53 | 36 | 39 | 3 | 7 |
| 6 | 63 | 35 | 30 | 2 | 7 |
| 7 | 59 | 33 | 36 | 1 | 7 |
| 8 | 63 | 32 | 33 | 2 | 10 |
| Total | 458 | 299 | 267 | 19 | 65 |

These breakdowns are descriptive; all shards form one predeclared decision.

## Development overlap and evidence preservation

The separate Phase 4D.3 implementation and modest correctness checks shared
the machine during part of this campaign. Their maximum four active search
workers plus eight match workers and up to two compiler jobs fit the declared
14-worker nighttime allowance. The fixed null-move screen used one worker;
its report deliberately makes no timing interpretation. Resource admission
does not establish scheduling latency, and this audit does not identify the
cause of the flagfalls. Do not attribute them to LMR, the runner, or concurrent
development without a reproducible diagnosis.

Preserve `results/phase4d2-20261018/campaign/`, its console log and
`results/phase4d2-20261018/final-audit.json`. The final audit SHA-256 is
`746fbc68cb17685a6040c98968b8f4da593749a59758011bb2ff606fcaff31bf`.
Frozen builds remain in `build/experiments/phase4d2-20261018/`. These generated
artifacts stay outside Git; archive the complete records when changing hosts.
The completed openings are now exposed evidence, not fresh qualification data.

## Next steps

Keep LMR, countermove ordering and null-move pruning disabled by default.
Do not rerun, extend, pool or retune this campaign. Diagnose the saved flagfalls
before any new timing-dependent qualification. The separate next implementation
checkpoint remains **4D.4 conservative reverse futility**; its correctness work
does not require another long match. Default promotion, release acceptance and
broader platform execution remain open.
