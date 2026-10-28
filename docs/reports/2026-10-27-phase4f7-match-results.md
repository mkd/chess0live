# Phase 4F.7 — completed TT Move Hints strength comparison

Played October 27, 2026; independently audited October 28. Engine source
`a1b2331`; original preparation `2059850`; timing amendment `984f059`.

**All 512 games / 256 opening pairs completed and passed the independent audit.**
Hints on scored **162 wins, 186 draws and 164 losses**, or **255/512 points
(49.80%)**. There were no time forfeits or excluded games. The predeclared
decision is **inconclusive**. TT Move Hints remains optional and off by default;
promotion is parked and this finite experiment is closed without an extension.

## Conditions and completion

The [frozen protocol](../experiments/phase4f7-match.md) and
[dated timing amendment](../experiments/phase4f7-match-daytime-20261027.md)
govern this single attempt. Both roles used the same frozen macOS ARM64 generic
executable and pinned SF19-compatible network. Only TT Move Hints differed.
Both used Threads=1, Hash=64, 60+0.6, classic timing, 20-ms overhead,
LMR=true and MVV-LVA capture ordering. All other optional search policies,
pondering, diagnostics and Syzygy were off. No evaluation adjudication was used.

Four parallel game streams used four active search workers and at most eight
resident engines, with a minimum 6 GiB reservation. Play ran **16:57:44–23:20:01
Europe/Helsinki**, **6h22m17s**, under `phase4f7-daytime-20261027`, finishing
before the original October 28 07:00 cutoff. Admission retained the ordinary
50% daytime / 80% nighttime resource budgets. Reservations approximate resources;
they are not measured OS utilization caps.

The owner confirmed the agreed quiet window and Automatic profile; launch checks
directly recorded AC power and Low Power disabled. Competing inference was to remain
paused during play. These checks do not provide continuous thermal, GPU or
competing-workload telemetry. The launcher exited zero; saved cleanup records
no live or unverified engine PIDs, and a separate process check found no match
workers or idle-sleep inhibitor. The owner was told LM Studio inference could
resume once cleanup was verified. The progress heartbeat was deleted after the
terminal result and audit were reported.

## Results and decision

Candidate means **hints on** throughout; opponent means **hints off**.

| Shard | Games | Complete pairs | Wins | Draws | Losses | Candidate points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 128 | 64 | 41 | 47 | 40 | 64.5 |
| 2 | 128 | 64 | 42 | 46 | 40 | 65.0 |
| 3 | 128 | 64 | 39 | 45 | 44 | 61.5 |
| 4 | 128 | 64 | 40 | 48 | 40 | 64.0 |
| Total | 512 | 256 | 162 | 186 | 164 | 255.0 |

Pair-point buckets for 0, 0.5, 1, 1.5 and 2 candidate points are
**2, 37, 179, 37 and 1** respectively. All four shards form the one declared
sample; no scores were selected, pooled from other campaigns or dropped.

The exact score is **49.8046875%**. The predeclared conditional 95% pair-level
Hoeffding interval is **41.316553%–58.292822%**. Promotion-review eligibility
required at least **299.5/512 points** and zero forfeits; the negative-evidence
boundary was at most **212.5/512 points**. Neither boundary was reached.
The observed two-game win/loss difference does not demonstrate a strength loss,
and this broad interval also does not prove equivalence or nonregression.

The 256 unique roots were disjoint from the recorded exclusion catalog, but
shared opening stems and concurrent shared-host work limit independence. The
interval is conditional on independent opening-pair observations. This sample
cannot establish absolute Elo, results against Gargantua/Stockfish, eight-thread
match strength, other time controls or resolution of earlier clock failures.
The earlier eight-thread tactical pass remains separate evidence.

**Next checkpoint:** select a new isolated search improvement in Phase 4F and
declare its acceptance criteria before testing. Do not tune against these
completed games or rerun this campaign to seek a favorable outcome. The older
combined-policy candidate remains parked. No playing default or release changes.

## Independent validation and preserved evidence

The fresh auditor replayed the existing campaign through `tools/run.py`; it
launched no engines. It exited zero with `complete=true`, `decision=inconclusive`,
`default_change=false`, and empty error/source-difference lists. It checked
all 512 games, colors, 256 pair memberships, legal histories, raw clocks/options,
provenance, resource coverage and cleanup. Evidence includes:

- 52,927 search events and 62,911 legal game plies, including opening histories;
- 3,059,254 legal PV plies and 52,577 legal ponder suggestions (Ponder=false);
- 1,024 recorded engine processes and 23,364 parent resource observations;
- 3,343 input file identities in the audit, including the saved raw outputs;
- zero time forfeits in either role and zero excluded games/pairs.

The runner retained python-chess warnings about the Syzygy-disabled informational
response; these were not engine errors or game failures. All 1,031 previously
protected files and the README
introduction still match their saved identities, including stable GUI
`0.1-dev-4b8b35d`, normal binaries and owner settings. Frozen sources/pins,
engine defaults and previous experiments were not edited or rebuilt. This
completion checkpoint changes documentation only; prior synthetic preparation
checks were not repeated.

Evidence remains local under `results/phase4f7-match-20261027/`, with preparation
and launch context in `results/phase4f7-match-20261027-preparation/`. The full
audit is outside the frozen campaign at
`results/phase4f7-match-20261027-audit.json`. To replay later, use a fresh output
path rather than overwrite that audit:

```sh
python3 tools/run.py tools/audit_phase4f7.py \
  --campaign results/phase4f7-match-20261027 \
  --output results/phase4f7-match-20261027-audit-recheck.json
```

| Artifact | SHA-256 |
| --- | --- |
| Completed campaign manifest | `b4b8ee004f33ffc38d5aa032a4b8376fa715ce38bb67b4d65d9161381bda5827` |
| Independent audit | `de9cbe1851f63ae6126450bd35582b0bba1550245c695cce2549918a24e27e4a` |
| Frozen executable | `6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Preparation pins | `6516492d905c5bff0c49855af421bc27c870d7df7276cd3fe64cee3106699f8f` |
