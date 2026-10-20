# Four-worker match-readiness result — October 20, 2026

**The single bounded attempt passed its independent operational audit.**
All eight games completed naturally, with no clock forfeits, illegal replies,
protocol/storage failures, unfinished games or input drift. This permits
preparing fresh qualification of existing conservative LMR at four active
workers. It does not establish a historical clock repair, a strength gain or
default promotion.

## Fixed experiment and execution

Preparation commit: `2b04cd3`. The [protocol](../experiments/match-readiness-20261020.md)
was committed before play. The attempt ran October 20, **21:02:18–21:02:42
Europe/Helsinki**, taking **23.949 seconds** against a 180-second limit.
No retry, replacement, exclusion, resume, schedule or longer campaign occurred.

Four shards each played one fresh opening pair with colors reversed:
**3 seconds + 0.05 seconds/move**, Threads 1, Hash 64 MiB, Move Overhead 20 ms,
classic timing, Ponder/diagnostics off, no tablebases. Both roles used the same
ordinary executable; only `Late Move Reductions` differed. Null move, reverse
futility, quiescence SEE and countermove options were off; capture ordering
remained MVV-LVA. The unchanged runner/referee charged actual callback-observed
elapsed time without adding watchdog grace to either clock.

The four 20-ply roots were generated without engine evaluation or outcome
selection. Deterministic regeneration and source replay passed; their final
roots were disjoint from 164,497 recorded exposed roots. These four roots and
the positions played from them are now exposed and must not be reused as fresh
qualification. Fresh roots alone do not establish independent or balanced games.

## Audited observations

| Check | Observation |
| --- | --- |
| Natural completions | 8/8: six checkmates, two threefold repetitions |
| Candidate LMR-on result | 3 wins, 2 draws, 3 losses; 4/8 points |
| On-time searches | 646/646 |
| Minimum observed remaining clock at reply | 9.659 ms |
| Replayed game plies | 806, including 160 opening plies |
| Replayed analysis | 5,180 PV lines / 14,135 PV plies; 640 legal ponder moves |
| Actual concurrency | Peak exactly four; four active for 14.977 seconds |
| Resource checks | Eight admissions, 23 observations; maximum gap 1.047 seconds |
| Cleanup | All 16 engine PIDs absent; no alive or unverified processes |
| Integrity | Source/artifact checks passed; 54 audit input hashes retained |

The fresh resource check detected 18 logical CPUs and 64 GiB RAM. Daytime
policy allowed nine active workers; this attempt reserved four and eight
resident engines, with a conservative 6 GiB memory estimate. These are
admission/monitoring records, not measured OS CPU or RSS limits.

Before play, **94 workflow checks passed**: 17 statistics, 40 existing runner,
18 supervisor and 19 independent auditor checks. The auditor replayed raw
protocol messages, histories, legal moves/PVs/ponders, options, transmitted and
charged clocks, increments, PGNs, referee outcomes, process identities and
concurrency intervals. Its verdict was `audit_passed`, with
`operational_acceptance=true` and no errors.

The short control differs from the historical 60+0.6 campaign and covers only
this host/load sample. Its balanced score is not evidence of equal strength.
LMR remains disabled; all earlier failure decisions remain recorded. No engine
source/default change, fresh GUI visual check, foreign execution, full puzzle
rerun or release acceptance is claimed.

## Evidence and handover

- Frozen ordinary engine and preparation manifest:
  `build/experiments/match-readiness-20261020/`.
- Complete raw records: `results/match-readiness-20261020/canary/`.
- Independent result: `results/match-readiness-20261020/audit.json`,
  SHA-256 `ee9abb2ff0a9e0a31c86cb253746f60ebf6fba1b6f8dfbd6a92d32c3a5b53bff`.
- Checks: `workflow-tests.log`, `openings-check.log`, `protected-after.json`
  in `results/match-readiness-20261020/`.
- Ordinary/frozen executable SHA-256:
  `eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
- Network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

All 40 earlier protected pins, the owner's README introduction and modified
`tools/batch_positions.py`, and the normal release were preserved: 43 post-run
checks passed. GUI snapshots `0.1-dev-4b8b35d`,
`0.1-dev-phase3f-20261017` and `0.1-dev-phase4b-20261018` remain intact.
Keep complete ignored evidence when moving machines; the repository includes
the protocol, suites, generator, supervisor, auditor and this report.

**Next:** declare and freeze one fresh equal-resource LMR qualification with
new openings and the unchanged reliability/strength gates. Follow overnight
policy or obtain a new explicit daytime exception; do not create a schedule
without a request. Decide whether to promote, reject or park existing LMR
before broader Phase 4D.6 reductions. The owner handles GitHub pushes.
