# Phase 4D.2 — current-engine LMR qualification

Protocol: **phase4d2-lmr-1024-v1**, declared October 18, 2026 before any
held-out search. This is one fixed comparison of conservative late-move
reductions on the current engine, after the clock/runner fixes and cache/SMP
implementation. It changes no engine code or search default.

## Hypothesis and isolation

The existing one-ply reduction of eligible late quiet moves, with full-depth
verification when a reduced result raises alpha, improves equal-time play
without an operational regression. The same frozen executable from `74a908b`
plays both roles; candidate LMR is on, opponent LMR is off. Both use classic
timing, MVV-LVA captures, Countermove Ordering=false, Ponder=false, Search
Diagnostics=false, SyzygyPath empty and SyzygyProbeLimit=0. Threads=1, Hash=64
MiB and Move Overhead=20 ms. The pinned NNUE file is identical in both roles.

The implementation remains independent. No owner's engine or match assets are
reused. Historical Phase 3L binaries, inputs, protocol, and source dependencies
remain untouched and unstarted. Phase 4D.1 countermove ordering is parked.

## Fixed sample and openings

- **1,024 games: 512 two-game pairs**, reversing colors at each starting root.
- Eight shards, 64 pairs/128 games each; seeds 202610184201 through 202610184208.
- **60 seconds + 0.6 seconds per move**, no pondering; independent legal referee.
- No score-based early stop, extension, replacement games, resume, unchanged
  retry, or pooling with earlier experiments. One pooled decision only.
- A 512-ply safety cap records an incomplete game, never an invented draw.
  Startup allowance is 30 s; protocol grace 5 s is not free playing time.

The eight `tests/data/phase4d2-lmr-*.json` suites contain 512 unique legal roots
with complete 19/20-ply histories, 256 of each side to move. The generator uses
64 original 16-ply stems (24 e4, 24 d4, eight c4, eight Nf3) and eight legal
SHA-selected continuations per stem. Each shard has 32 roots per side. Selection
seed is 20261018422 with domain `chess0live.phase4d2.openings.v1`.

The 1,265-root exclusion catalog incorporates prior development exposure,
including Phase 3L roots read only for exclusion, and newly exposed cache/SMP,
Syzygy and countermove positions. Its 28 direct source digests and inherited
851-root provenance are retained. Private files are not published; the frozen
canonical catalog permits public reproduction. Neither generation nor readiness
sends a held-out position to an engine. Reproduce with
`python3 tools/generate_phase4d2_openings.py --check --verify-sources`.

## Resource and clock policy

Launch only **23:00 inclusive to 23:30 exclusive, Europe/Helsinki**, with an
immutable cutoff at the following **07:00**. No daytime exception is inherited.
This is a foreground command, not a schedule. Idle-sleep prevention, if used,
must be scoped to this command. Explicit machine sleep, shutdown, or interruption
can invalidate completion; never resume or fill missing games.

Eight active searches and sixteen resident engines remain reserved until all
workers finish cleanup. The conservative memory estimate is about 8.88 GiB;
it is an admission estimate, not an OS-enforced memory cap. Admission must fit
the current local CPU/memory policy before launch and before each game. A
one-second monitor checks resources and source/input metadata; a monitoring
gap above five seconds while games are active invalidates the run. Full asset
and source hashes are checked at readiness and finalization. Resource changes,
cutoff, interruptions and failures cancel and await every worker and its engines.

Before launch, one bounded eight-worker low-clock/cancellation check uses only
already exposed positions; its results are operational evidence, never strength
evidence. The two real qualification roles then undergo serial, search-free UCI
readiness. The launcher and independent auditor must pass their tests, frozen
pins must be finalized, and the protocol must be committed before any match.

Historical 128-game shards took roughly 6h18–6h41. Eight concurrent shards may
fit one night, but increased contention changes that estimate. The maximum
allowed clock use permits over 15 hours per shard, so completion is not promised.
At 07:00 an unfinished sample is incomplete, even if its partial score is favorable.

## Decision rule and uncertainty

Audit all 1,024 raw games and all 512 reversed-color pairs: legality, PGN results,
UCI options, transmitted clocks, measured time, process lifecycle, complete
membership, frozen artifacts and the full resource journal. All valid flagfalls
remain scored. **Any candidate flagfall is an operational regression**, regardless
of score; baseline flagfalls are also reported. Incomplete or corrupted evidence
cannot qualify the candidate.

For complete valid pairs, calculate each candidate pair score divided by two.
The predeclared conditional 95% Hoeffding half-width is
`sqrt(log(40)/(2*512)) = 0.0600201745`, or about 6.002 percentage points.
With operational gates passed, a lower bound strictly above 50% and an observed
score at least 50.72% (rounded +5 Elo practical target) makes the candidate
eligible for a separate default review: **at least 573.5/1,024 points**.
An upper bound below 50% means negative evidence: **450.5 points or fewer**.
Everything between is inconclusive. A favorable score never automatically edits
defaults. No rating or universal absence of strength loss is established.

This interval assumes between-pair independence, which is not proven: the eight
tails per stem are related, and all games share one host. More distinct FENs and
shards do not remove that dependence. Family/shard breakdowns are descriptive,
not separately selected tests. The finite design detects a large observed effect;
it does not resolve +5 Elo. More than 35,000 pairs would be needed merely to make
this conservative half-width narrower than the +5 Elo score difference.

Earlier Phase 2D/3G attempts are disclosed in their reports and never pooled.
Phase 3G's 59.08% score was rejected by six candidate flagfalls. Subsequent fixes
motivate this new current-engine test; they do not retrospectively validate it.
Even a successful result is limited to this single-worker blitz setting.
External opponents, longer controls and Threads=4 need separate confirmation.

## Execution and evidence

Build/network/input digests are independently pinned in
`tools/qualify_phase4d2.py` and `tools/audit_phase4d2.py`. The ignored build
manifest at `build/experiments/phase4d2-20261018/manifest.json` records source,
compiler, flags and provenance. Every run copies this protocol and records all
relevant source/asset hashes and resource admissions before play.

```sh
make test-phase4d2
python3 tools/qualify_phase4d2.py check
# Only after readiness, validation, local commit, and within the launch window:
caffeinate -i python3 tools/qualify_phase4d2.py run --output results/phase4d2-20261018/campaign
python3 tools/audit_phase4d2.py --campaign results/phase4d2-20261018/campaign
```

Confirm actual CLI usage with `--help`; raw output remains ignored by Git.
The report records exactly what ran and its one decision. If inconclusive or
incomplete, keep LMR off and proceed to the separate Phase 4D.3 verified
null-move candidate instead of repeatedly tuning or extending this phase.
