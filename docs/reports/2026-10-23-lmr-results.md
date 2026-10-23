# Fresh conservative-LMR qualification — results and decision

**All 512 games completed and the independent audit passed. Existing LMR is
eligible for a separate default-setting review; the shipped default is still
off.** This closes the one fixed qualification attempt without extending,
replacing or retuning its sample. Engine code and evaluation were unchanged.

The [predeclared protocol](../experiments/lmr-20261022.md) compared the identical
frozen engine with `Late Move Reductions=true` versus `false`, using 256 fresh
reversed-color opening pairs, 60+0.6, Threads 1, Hash 64 MiB, Move Overhead 20 ms
and classic timing. Four games ran concurrently. Other pruning/ordering
experiments, pondering, diagnostics and tablebases were disabled.

## Result

All figures below are from the LMR-enabled candidate's perspective.

| Scope | Wins | Draws | Losses | Points | Score |
| --- | ---: | ---: | ---: | ---: | ---: |
| All games | 215 | 175 | 122 | 302.5 / 512 | 59.08% |
| Candidate White | 99 | 88 | 69 | 143 / 256 | 55.86% |
| Candidate Black | 116 | 87 | 53 | 159.5 / 256 | 62.30% |
| Shard 1 | 51 | 49 | 28 | 75.5 / 128 | 58.98% |
| Shard 2 | 52 | 40 | 36 | 72 / 128 | 56.25% |
| Shard 3 | 56 | 39 | 33 | 75.5 / 128 | 58.98% |
| Shard 4 | 56 | 47 | 25 | 79.5 / 128 | 62.11% |

The one pooled decision uses all 256 pairs. Pair-point counts for 0, 0.5, 1,
1.5 and 2 candidate points were **0, 14, 151, 75, 16**. No game or pair was
excluded. The conditional 95% Hoeffding score interval is **50.594%–67.570%**,
clearing the frozen 299.5-point eligibility threshold by three points.

The score corresponds descriptively to **+63.8 relative Elo** against this
LMR-off baseline, with the same conditional bounds of +4.1 to +127.5. This is
not an absolute engine rating or a general +64 Elo promise. The interval assumes
independent pairs; four tails share each original stem and every game ran on
one host, so independence and broader representativeness are not established.
Color/shard breakdowns are descriptive and do not select favorable subsets.

## Operational audit

- **Zero clock forfeits in either role**, crashes, malformed results or audit
  errors. All games ended normally: 337 checkmates, 156 threefold repetitions,
  15 insufficient-material draws and four fifty-move draws.
- Independently replayed **50,367 searches**, **60,351 legal plies including
  openings**, **2,639,322 PV plies** and **50,015 ponder moves**. Recorded ponder
  moves are output validation; pondering was disabled during play.
- Audited actual options, raw protocols/PGNs, charged/transmitted clocks,
  resource observations, fixed input identities and cleanup. All **1,024**
  recorded engine processes had exited; no live-source differences were found.
- Finished **October 23 at 02:18:58 Warsaw / 03:18:58 Helsinki**, after
  **6h 15m 35s**, before the fixed 06:00 Warsaw / 07:00 Helsinki cutoff.
  The owner's dated daytime launch permission was recorded; no schedule exists.
- The match console retained informational Syzygy setup warnings described in
  the [launch record](2026-10-22-lmr-launch.md). These are not missing-table game
  failures: probing was disabled and raw verification passed. The final audit's
  own stdout/stderr logs are empty.

The historical 4D.2 result remains failed on its clock gate and is not pooled
or retrospectively repaired. This successful lower-concurrency run does not
identify the cause of those earlier failures.

## Decision and next checkpoint

**Accept the qualification result and advance existing conservative LMR to one
bounded integration/default review.** Do not broaden its reductions, tune on
these now-exposed openings or rerun this attempt. The ordinary binary/default
remains unchanged during this reporting step.

The integration checkpoint should freeze the parent, change only the LMR
default and corresponding expectations/documentation, and verify that new
default-on behavior matches the old explicit-on path while opt-out matches the
parent. Run relevant native/scalar/sanitizer and UCI lifecycle regressions,
including four-thread stop/node/time handling, before retaining that change.
If a material regression appears, record and park the promotion rather than
silently widening the work. Multithreaded lifecycle checks do not establish SMP
playing strength: this match establishes only the tested one-thread condition.

After that explicit integration decision, proceed to **Phase 4D.6**, one
separate broader quiet-move reduction/pruning hypothesis with dedicated tactical,
pawn-breakthrough and zugzwang checks. **ProbCut remains Phase 4D.7**. Do not
bundle unrelated opt-in null-move, reverse-futility or quiescence SEE experiments.

## Evidence and preservation

Preparation `548ce74`, authorized amendment `a81c951`, launch record `d6967c4`.
Frozen executable/network and build manifest remain as documented in the
[preparation report](2026-10-22-lmr-preparation.md). No rebuild, fresh GUI match
or platform execution was performed to report these results.

Raw campaign: `results/lmr-20261022/campaign/`. Final independent audit:
`results/lmr-20261022/final-audit.json`, SHA-256
`426378d53f6a09406259c46400e8e853eaffbe94cdd8ff295023e9e482d6cddc`.
`result-summary.json` is a separately recomputed tally; `final-protected.json`
records 60 passing preservation checks. Preserve all raw games and audit inputs.
The owner puzzle-runner edit, exact README introduction, ordinary executable,
and stable GUI bundles `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017` and
`0.1-dev-phase4b-20261018` remain unchanged. The owner handles GitHub pushes.
