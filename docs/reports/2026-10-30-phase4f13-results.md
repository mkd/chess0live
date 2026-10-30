# Phase 4F.13 — completed NNUE comparison, qualification blocked

Played and independently audited October 30, 2026 under `phase4f13-daytime-20261030`, from preparation
commit `e60345dc1e16c01e8cff4273608eb85d58b2f53d`.

**All 2,048 qualification games / 1,024 reversed-color pairs completed.** The
optimized NNUE candidate scored **686 wins, 695 draws and 667 losses**:
**1,033.5/2,048 points (50.4638671875%)**. Six time forfeits, three per version,
fail the prospectively fixed zero-forfeit requirement. No game or pair was
excluded. This is not a qualified strength gain, loss, equivalence or rating.

## Conditions and completion

The [base protocol](../experiments/phase4f13-match.md) and
[dated amendment](../experiments/phase4f13-match-daytime-20261030.md) govern this
single attempt. The preserved candidate source is `3ee5eff`, baseline `1ca87d6`.
Both used the same pinned SF19-compatible network, 15+0.15, Threads=1, Hash=64,
classic timing, 20-ms overhead, LMR=true and MVV-LVA capture ordering. Other
experimental search options, pondering, diagnostics and Syzygy assistance were
off. There was no evaluation adjudication, rebuild, retry, resume or replacement.

The campaign ran **15:04:34.532843–21:20:41.143133 Europe/Helsinki**, about
**6h16m07s**, before the fixed October 31 07:00 cutoff. Qualification began at
15:06:27.993884–15:06:27.994546; its last game finished at 21:20:40. The separate
smoke gate completed eight draws/four pairs with no failures or forfeits and
passed independent audit/cleanup at 15:06:27.831943. Smoke is excluded from every
qualification total below.

Four active search workers and eight resident engines reserved at least 6 GiB,
under ordinary 50% daytime/80% nighttime limits. Reservations and owner quiet-host
confirmation are not continuous OS load, temperature, power or GPU telemetry.
The wrapper and sleep inhibitor exited zero. The terminal campaign lists all
4,112 game engine PIDs (4,096 qualification plus 16 smoke) with no live or
unverified PIDs. A separate OS check at **21:40:00 Helsinki** found all 4,116
recorded engine PIDs including preflight/readiness, runner 67419, wrapper 67416
and sleep inhibitor 67420 absent, with no surviving campaign process or auditor.
The owner was explicitly told **LM Studio inference can resume** after this check.

## Full descriptive results

Candidate means the optimized NNUE executable throughout.

| Shard | Games | Complete pairs | Wins | Draws | Losses | Candidate points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 512 | 256 | 168 | 179 | 165 | 257.5 |
| 2 | 512 | 256 | 166 | 191 | 155 | 261.5 |
| 3 | 512 | 256 | 170 | 170 | 172 | 255.0 |
| 4 | 512 | 256 | 182 | 155 | 175 | 259.5 |
| Total | 2,048 | 1,024 | 686 | 695 | 667 | 1,033.5 |

Pair-point buckets for **0 / 0.5 / 1 / 1.5 / 2** candidate points are
**18 / 133 / 696 / 166 / 11**. Shards use local pair identifiers; pairs with the
same local label in different shards are distinct. Endings: 1,347 checkmates,
600 repetitions, 76 insufficient-material draws, 16 fifty-move draws, three
stalemates and six time forfeits. All six forfeits remain scored in these totals.

## Timing failures and causal limits

Every late move was marked unplayed, without increment credit. JSON clocks,
raw command-to-bestmove receipt durations and PGN endings agree in the bounded
independent inspections. Times below are UTC on October 30; lateness is relative
to the recorded clock before the attempted move, not the rounded UCI clock.

| Shard / game | Loser | Finish UTC | Clock before ms | Observed elapsed ms | Late by ms | Engine-reported ms |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 4 / p000104-1 | Baseline | 15:41:14.627192 | 169.808835 | 195.686208 | 25.877373 | 150 |
| 1 / p000179-2 | Candidate | 17:25:25.554616 | 169.919375 | 170.922708 | 1.003333 | 150 |
| 2 / p000188-1 | Candidate | 17:40:11.754453 | 187.278330 | 241.093083 | 53.814753 | 167 |
| 3 / p000188-2 | Baseline | 17:40:11.754485 | 169.992373 | 224.964000 | 54.971627 | 150 |
| 3 / p000256-2 | Baseline | 19:19:14.649400 | 169.971002 | 170.613375 | 0.642373 | 150 |
| 4 / p000256-1 | Candidate | 19:19:14.649458 | 170.029833 | 184.203334 | 14.173501 | 150 |

The two pairs of clustered finishes differ by 32 and 58 microseconds respectively.
The first clustered pair has roughly 74–75 ms between engine-reported search time
and observed receipt elapsed time; the second has roughly 21–34 ms. These are
possible shared timing disturbances, not proof of a particular cause. Existing
logs cannot locate the extra delay among engine stopping, OS scheduling, pipe
delivery and runner processing. The ordinary resource/continuity gate does not
prove millisecond-scale timing reliability. Three forfeits on each side do not
cancel the zero-forfeit requirement. Do not discard, replace or reinterpret them
as ordinary played outcomes to recover qualification.

## Independent audit and decision

The fresh independent audit exited zero with **`complete=true`, `errors=[]`,
no live-source differences and `default_change=false`**. The aggregate decision
is **`operational_regression`**, with **`inference_eligible=false`** because either
role's time forfeit disqualifies the attempt. This verdict describes a failed
operational gate; it does not prove that the NNUE optimization caused a regression.

The predeclared conditional 95% **score and relative-Elo intervals are withheld
(`null`)**, as are the test capitals. The betting helper's generic
`predeclared_experiment_not_complete` reason refers here to failed operational
eligibility, not missing games: all 2,048 games and 1,024 pairs are present.
The audit retains a descriptive score-to-Elo transform of +3.22337; it is not
qualified Elo evidence or an achieved rating. No alternative interval is used.
Historical per-shard diagnostic intervals/labels are not the aggregate verdict.

Full raw replay checked all qualification games and separately replayed smoke,
including legal histories, UCI options/output, clocks, pair membership, input
identities, resource coverage and cleanup. Qualification coverage includes
**200,958 search events, 240,888 legal game plies including openings,
8,435,752 legal PV plies and 199,532 legal ponder suggestions** (Ponder=false).
The campaign has **24,495 aggregate resource observations**; the final audit
records **7,570 input file hashes**. Its successful evidence audit does not erase
the six operational clock failures.

All **4,114 launcher stderr lines** are retained Syzygy-disabled informational
warnings accepted by the auditor. No additional game or audit errors were found.
Preparation failures and limitations remain in the linked preparation records.

| Artifact | SHA-256 |
| --- | --- |
| Terminal campaign manifest | `4b82cd7de1e9a2766d2f70ed12c9ac9228dae54ea82130f0641280a4f55839bb` |
| Independent final audit | `967c1ff7c55c6c5b7a536c95c26146e307dad38f33369c74ccf2adb9ad073627` |
| Candidate executable | `04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594` |
| Baseline executable | `8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |

The fixed protocol withholds strength qualification after any forfeit. The
50.46% descriptive score and earlier approximately 5% execution-rate improvement
do not establish Elo. Related tails share 64 opening stems; historical exposure
coverage is incomplete, and independence/common conditional-mean assumptions
remain unverified. This finite single-thread short-clock matchup cannot establish
external-opponent strength, eight-thread strength, other time controls or a
universal nonregression result.

## Preservation and next checkpoint

Independent preservation verification found **zero new mismatches**: 96 archived
original inputs, 95 campaign/readiness source records, 94 dated pinned inputs
and 11 runtime assets match. The dated pin remains
`dba5fecdc37983f81f75bd89d9be7d7281b90e270d50fcfec6512089c955d0bb`.
The stable GUI **0.1-dev-4b8b35d** (all five files), protected owner batch runner
and exact README introduction are preserved. External GUI application settings
were not independently inspected.

Of 401 historically protected paths, 400 match. The sole remaining discrepancy
is the previously disclosed normal-release binary, outside campaign inputs:
its current SHA-256 `c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d`
is preserved, but it differs from inherited October 29
`b2db6cf80b2db188192fed65b42e16acbc8af4ade5edd2f4cc36f1baf953e37c`.
Its cause remains unknown; historical normal-release preservation is not claimed.
Keep the [preparation disclosure](../experiments/phase4f13-daytime-20261030-preparation-results.md).

**Next checkpoint:** investigate and reproduce the short-clock timing failure
before proposing another strength qualification. Distinguish engine output timing
from harness receipt timing with a prospective diagnostic design; these logs alone
do not justify changing either implementation. Do not tune on, extend or rerun
this completed sample. No engine/default promotion, new game schedule, release or
push follows from this closeout. TT Move Hints and Continuation History stay off.

Preserve the raw campaign `results/phase4f13-match-20261030/`, the outside final
audit `results/phase4f13-match-20261030-audit.json`, the preparation directory
`results/phase4f13-daytime-20261030-preparation/` and closeout receipts in
`results/phase4f13-match-20261030-closeout/`. Never overwrite the final audit.
The progress heartbeat was deleted after the terminal result and audit were
reported. Documentation link/diff checks, audited arithmetic reconciliation and
independent documentation review validate this documentation-only closeout;
synthetic preparation tests were not repeated. Changes are committed locally on
main; the owner handles pushes.
