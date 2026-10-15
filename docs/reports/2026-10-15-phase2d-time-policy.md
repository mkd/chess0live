# Phase 2D time-policy qualification — October 15, 2026

**Decision: inconclusive. Classic remains the default.** The frozen forecast
policy scored **14 wins, 43 draws, and 7 losses**, or **35.5/64 points (55.46875%)**.
The predeclared pair-level, two-sided 95% Hoeffding score interval is
**31.46068%–79.47682%**, conditional on the sampling assumptions below. The
observed lead does not establish a strength improvement or equivalence.

All 32 opening pairs completed, with no excluded games, time forfeits, setup or
protocol failures, unexpected stderr, or ply-cap truncations. The independent
data-only audit passed and returned `inconclusive`; no engine option or default
was changed in response to the result.

## Frozen experiment

Preparation commit: `2cf55f7a580082bc3fac5b8ad096050738fe1dfd`, recorded with a
clean runner checkout. This identifies campaign preparation, not a new engine
build. Both roles used the same previously frozen hard-deadline executable:

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| Engine | `build/experiments/time-policy-hard-20261014/chess0live` | `cafaa3ae3e6500d75382b3cf943ebc23d2d154247bc18ac3b3254d206619a80c` |
| Network | `networks/nn-1a298aa575a0.nnue` | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Openings | `tests/data/openings-time-validation.json` | `163bf4c34547a838c35e03103401c40d448a2f78c535254bf3727913b007b95b` |

The sole experimental option difference was `Time Policy=forecast` for the
candidate versus `classic` for the opponent. The executable predates optional
LMR and SEE; their effects are not part of this comparison. The owner's stable
GUI bundle `0.1-dev-4b8b35d` was preserved and was not the match executable.

The [predeclared protocol](../PHASE_2D.md), also frozen as the campaign's
`protocol.md`, fixed these conditions before play:

- All 32 original opening histories, each with both colors: 64 games, seed
  `20261014`. No outcome-dependent stopping, sample extension, or exclusions.
- 60 seconds plus 0.6 seconds per move; one thread and 64 MiB hash per engine;
  20 ms move overhead; ponder and search diagnostics disabled.
- One sequential game, two resident engine processes, one active search worker.
  No books, tablebases, evaluation adjudication, or resignations.
- Maximum 512 searched plies per game; capped games would remain incomplete.
  Startup timeout 30 seconds and protocol response grace 5 seconds. Grace does
  not grant extra chess-clock time: late legal replies count as flagfalls.
- Referee `chess==1.11.2`, with automatic available threefold/rule-50 claims,
  including claims available by a next move. Clocks charge outgoing `go` to
  incoming `bestmove`, including transport latency and excluding readiness.

## Completion and audit

The launch manifest records **11:24:26.881267–14:18:16.315123 UTC** on October 15,
or **14:24:26.881267–17:18:16.315123 Europe/Helsinki**. Elapsed campaign time was
**10,429.433856 seconds (2 h 53 min 49.434 s)**. This includes orchestration,
engine setup/cleanup, and final integrity checks; it is not pure search time or
a reliable runtime promise for another campaign.

The run used the owner's explicit one-campaign daytime exception. The recorded
daytime resource policy was 50%, with one active worker on an ARM64 macOS 26.7.1
host reporting 18 logical CPUs and 64 GiB physical memory. Worker and memory
budgets are estimates, not hard OS utilization caps. This exception authorizes
no additional long jobs or recurring schedule.

The independent audit replayed **7,088 legal plies**, including the opening
histories in both color legs, and checked **6,240 search events** against actual
UCI options, full histories, charged clocks, PGNs, and final positions. It found
**21 checkmates, 38 threefold draws, and 5 insufficient-material draws**. Both
candidate and opponent had zero clock forfeits. All 64 games and all 32 pairs
were included. The pair-point histogram was 0 pairs at 0 points, 1 at 0.5,
24 at 1, 6 at 1.5, and 1 at 2.

Binary, network, opening, configuration, and frozen source fingerprints agreed
before and after the run. The audit reported no errors and no live-source
differences at audit time. Subsequent documentation of this outcome does not
modify the frozen campaign evidence.

## Interpretation and next work

The interval treats opening pairs as independent observations. These related,
hand-selected opening lines are neither a representative rating pool nor proof
of independence; the interval and conclusions are conditional and limited to
this suite and configuration. The 32-pair half-width is about 24.008 percentage
points. The predeclared positive screen required at least 47.5/64 points;
35.5/64 does not meet it. No absolute rating or proven Elo gain follows from
the observed score or its descriptive Elo transform in the raw summary.

Retain forecast as opt-in research and classic as default. Do not extend this
completed sample, change its criterion, or tune on its openings while calling
them held out. A future time-policy confirmation needs a fresh, predeclared
design. The first qualification screen is complete; strength qualification
and release acceptance remain unfinished.

The proposed next isolated search qualification prioritizes LMR on/off with
classic timing and baseline capture ordering. Its larger development work/depth
tradeoff makes it informative to test, while reduced fail-lows remain a tactical
risk and its earlier small smoke was unfavorable. That rationale is not a
strength claim. Fresh original histories, sample size, frozen artifacts,
acceptance criteria, and an authorized resource window must be fixed before
play. **No LMR qualification campaign has been launched or scheduled.** SEE
remains a separate opt-in experiment.

## Local evidence

All paths below are relative to `results/phase2d-time-policy-20261015/` and are
ignored local artifacts. The report and reproducing tools are versioned.

| Evidence | SHA-256 |
| --- | --- |
| `launch.json` | `e555d3f172703cfc833d2e7064e9977680b6dce140accacb73c50ed852caefc5` |
| `protocol.md` | `bba96863356e80d95792284548f5984a88cc690576beae677e1ca31b873e34b9` |
| `match/run.json` | `41105652fce594c9ea631176cf6605c2c366840c06d49f06cc45d2d8153c27a0` |
| `match/games.jsonl` | `53138a059acee4458fd83d64b869789ff90d86d864641d7202922a2af3cd6fb5` |
| `match/summary.json` | `8b7915a5afbed9850af9367c18e124f1fc1ac0c6ac81a673532017af3784f16e` |
| `audit.json` | `73982c0af9813dc34328ea0d94093d6940fa11628917bd78f9925778becf220d` |

The match directory also retains frozen openings, all PGNs, and protocol logs;
`audit.json` fingerprints each input it read. The executed auditor's SHA-256 is
`c6f2df2f59a619a53b6304b6e3e4848debe506b66e18c1f3e7ffb676323fba2c`.
The launch configuration digest is
`ba5eb22efea6af87d211cfeeb6af5b504d728a612ddf777b8b8af97d6822a2a4`.
The audit records timestamp `2026-10-15T14:18:25.706357+00:00` and started no
engine. A later audit must use a fresh output filename to preserve this record.
