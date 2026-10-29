# Phase 4F.10 — completed Continuation History comparison

Played October 28–29, 2026; independently audited October 29. Engine source
`69215b4`; original preparation `4a53054`; dated launch amendment `b9430a6`.

**All 512 games / 256 opening pairs completed and passed the independent audit.**
Continuation History on scored **179 wins, 151 draws, 182 losses**, or
**254.5/512 points (49.71%)**, against off. There were no time forfeits, excluded
games or audit errors. The predeclared result is **inconclusive**: keep the
option optional and off by default, park promotion and close this finite attempt.

## Conditions and completion

The [fixed protocol](../experiments/phase4f10-match.md) and
[dated amendment](../experiments/phase4f10-match-daytime-20261028.md) govern this
single attempt. Both roles used the same frozen macOS ARM64 executable and
pinned SF19-compatible network. Only Continuation History differed. Both used
60+0.6, Threads=1, Hash=64 MiB, classic timing, 20-ms overhead, LMR=true and
MVV-LVA captures. TT Move Hints, other optional search policies, pondering,
diagnostics and Syzygy assistance were off. No evaluation adjudication was used.

Four concurrent game streams used four active search workers and at most eight
resident engines, with a 6 GiB reservation. Play ran **October 28 19:56:01 through
October 29 02:06:51 Europe/Helsinki**, **6h10m50s**, under
`phase4f10-daytime-20261028`, before the unchanged October 29 07:00 cutoff.
Ordinary 50% daytime / 80% nighttime admission budgets remained in effect.
Worker counts and reservations are estimates, not measured OS utilization caps.
The owner confirmed a quiet host, paused LM Studio inference, AC/Automatic power
and wakefulness; launch checks recorded AC power and Low Power disabled. This is
not continuous thermal, GPU or competing-workload telemetry.

The launch wrapper exited zero. The campaign's cleanup lists all 1,024 recorded
game engine processes with no live or unverified PIDs; a separate OS process
check found no remaining campaign engine, supervisor or sleep inhibitor. The
owner was told LM Studio inference could resume immediately after that check.
The progress heartbeat was deleted after the terminal result and audit were
reported. No additional games, retries, resumes or schedules were created.

## Results and decision

Candidate means **Continuation History on** throughout; opponent means **off**.

| Shard | Games | Complete pairs | Wins | Draws | Losses | Candidate points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 128 | 64 | 39 | 46 | 43 | 62.0 |
| 2 | 128 | 64 | 51 | 28 | 49 | 65.0 |
| 3 | 128 | 64 | 40 | 42 | 46 | 61.0 |
| 4 | 128 | 64 | 49 | 35 | 44 | 66.5 |
| Total | 512 | 256 | 179 | 151 | 182 | 254.5 |

Pair-point buckets for 0/0.5/1/1.5/2 candidate points are **0/42/177/35/2**.
All shards form one declared sample; no results were selected, pooled or omitted.
Endings comprise 361 checkmates, 140 threefold-repetition draws, one stalemate,
nine insufficient-material draws and one fifty-move draw.

The exact score is **49.70703125%**. The predeclared conditional 95% pair-level
Hoeffding interval is **41.218897%–58.195166%**. Separate default-review eligibility
required at least **299.5/512 points** with zero forfeits; negative evidence
required at most **212.5/512 points**. Neither boundary was reached. The observed
three-game win/loss difference establishes neither a strength loss nor a gain,
and the broad interval does not establish equivalence or nonregression. The
conservative screen can miss small gains. Audit `inference_eligible=true` permits
the conditional calculation; it does not confer default-promotion eligibility.

The 256 distinct roots passed the recorded exclusions, including 2,796 prior
saved games and 266,535 known roots. Shared opening stems, related tails and
shared-host concurrency limit independence; unsaved games/internal search
positions are not covered by that exposure claim. The interval assumes
independent opening pairs. This result covers the frozen single-thread blitz
comparison only: no absolute Elo, external-opponent rating, eight-thread match
strength, other time controls, universal nonregression or general resolution of
earlier clock failures is established. The earlier four-versus-three mate puzzle
observation remains separate evidence and does not override this decision.

**Next checkpoint:** choose a new isolated Phase 4F search hypothesis using
existing diagnostics, and freeze its correctness, tactical and strength criteria
before testing. Do not tune against or enlarge/repeat this completed campaign.
TT Move Hints and the combined package remain parked. No default or release change.

## Independent audit and preserved evidence

The fresh audit replayed saved evidence through `tools/run.py --offline` without
launching engines. It exited zero with `complete=true`, `decision=inconclusive`,
`default_change=false`, no errors or live-source differences, and zero forfeits
or excluded games/pairs. It verified legal histories, raw clocks/options, pair
membership, provenance, resource coverage and cleanup, including:

- 49,753 search events and 59,737 legal game plies including opening histories;
- 2,977,286 legal PV plies and 49,382 legal ponder suggestions (Ponder=false);
- 22,650 parent resource observations and all 1,024 game engine processes;
- 3,855 input file identities, including saved raw outputs.

All 1,026 launcher stderr lines are the retained python-chess warning about the
informational Syzygy-disabled response. They are not failed games. Preparation
fixture/setup failures and their resolution remain in the
[preparation](2026-10-28-phase4f10-preparation.md) and
[launch](2026-10-28-phase4f10-launch.md) reports; no failed match was discarded.

Independent preservation review found no changes among 1,955 protected files,
62 amended campaign source identities, 61 original archived sources/pins,
14 original indexed evidence files and 18 amended indexed evidence files outside
that archive. The normal release, stable GUI `0.1-dev-4b8b35d`, owner batch
settings and exact README introduction are preserved. Frozen sources/pins and
defaults were not edited or rebuilt. This is a documentation-only closeout:
the full audit, evidence reconciliation and local-link/diff checks validate it;
prior synthetic preparation tests were not repeated. Nothing was pushed.

Raw campaign: `results/phase4f10-match-20261028/`. Preparation and launch receipts:
`results/phase4f10-match-20261028-preparation/`. Cleanup, preservation, monitor
deletion and documentation checks: `results/phase4f10-match-20261028-closeout/`.
The full audit is outside the campaign at
`results/phase4f10-match-20261028-audit.json`; never overwrite it. A later
read-only replay must choose a fresh output, for example:

```sh
python3 tools/run.py --offline tools/audit_phase4f10.py \
  --campaign results/phase4f10-match-20261028 \
  --output results/phase4f10-match-20261028-audit-recheck.json
```

| Artifact | SHA-256 |
| --- | --- |
| Completed campaign manifest | `9fb06e445d1fbd09dd85c0c108d363c905e5a2fb13503a746c24326a3335a06d` |
| Independent audit | `d74c0c0c27eee1a6ea183bd069872b371e44e32afff559a6f48daf688ac59d1b` |
| Frozen executable | `c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Preparation pins | `7a290b7e1cbc5152c00a8305ebe454168acfb65e031abcd3a495faea308b73fa` |
