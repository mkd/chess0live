# Phase 4F.13 — NNUE short-time-control strength qualification

Prospective protocol `phase4f13-nnue-2048-v1`, October 29, 2026, before game
play. The opening recipe was fixed before generating its roots. This is a new finite experiment following the audited
[Phase 4F.12 tactical comparison](../reports/2026-10-29-phase4f12-results.md).
No additional mate coverage was observed there. The earlier roughly 5%
equal-work execution improvement is not an expected or established Elo gain.

## Comparison and fixed sample

Reuse the exact Phase 4F.12 binaries and complete copied build provenance;
do not rebuild, tune or substitute the normal release:

| Role | Path under build/experiments/phase4f12 | Source revision | Executable SHA-256 |
| --- | --- | --- | --- |
| Candidate | candidate/chess0live | 3ee5eff30981b73099e8a118ff1712f89cdc285a | 04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594 |
| Opponent (baseline) | baseline/chess0live | 1ca87d6a596531d19b7b698b84c171fc314fc046 | 8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc |

The shared network is `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Both role manifests, original build manifests/logs and all 48 archived source
files are frozen. New `tests/data/phase4f13-match-pins.json` pins the protocol,
new tools/tests, inherited dependencies and all opening/provenance inputs.
Readiness and independent audit must verify distinct executable assignment;
identical UCI names do not establish that the correct binaries ran.

- **2,048 games / 1,024 color-reversed opening pairs**, fixed before any play.
- Four execution shards, 256 pairs each; seeds `202610304131`–`202610304134`.
- **15 seconds + 0.15 seconds per move**, Threads=1, Hash=64 MiB.
- Four active games / eight resident engines, minimum 6 GiB reserved memory.
- Maximum 512 searched plies; a cap is incomplete evidence, never a draw.
- Move Overhead=20 ms, startup allowance=30 s, protocol watchdog=5 s.
  Watchdog grace is not free chess-clock time; charge go-send through receipt.
- LMR=true, Time Policy=classic, Capture Ordering=mvv-lva. Both disable Deep
  Quiet Reductions, Countermove Ordering, Null Move Pruning, Reverse Futility
  Pruning, QSearch SEE Pruning, ProbCut, TT Move Hints and Continuation History.
  Ponder and diagnostics are false; SyzygyPath empty, ProbeLimit=0, ProbeDepth=1.

Only the NNUE implementation differs. Referee `chess==1.11.2` determines legal
terminal outcomes and available threefold/fifty-move claims, without evaluation
adjudication. Each game starts fresh processes with its original opening history.
Keep the historical clock accounting, persistence and child cleanup unchanged.
The faster control makes a larger sample practical; it qualifies this specific
short-time-control matchup, not 60+0.6 blitz or eight-thread playing strength.

## Opening generation and exposure

Use the project's 64 independently authored 16-ply stems in original order,
16 legal tails per stem, from the new domain and seeds. Variant modulo four
0–1 adds three plies, 2–3 adds four. Select from sorted legal UCI moves using
the declared SHA-256 rejection/modulo sampler. Shard assignment is
`(stem_index % 2)*2 + variant % 2 + 1`; each shard contains 128 roots per side
to move, with family counts e4=96, d4=96, c4=32 and Nf3=32.

Reject terminal intermediate/final positions, duplicate accepted canonical roots
and exposed roots; record every rejection and attempt. Do not select by engine
evaluation, result or material balance. Preserve full original move histories.
Freeze prior public opening/position catalogs, valid test/tool FEN literals and
all available project saved PGN mainlines, including completed Phase 4F.7 and
4F.10 games and Phase 4F.11/12 exposed inputs. Never use the owner's other engines
or their assets. Compact public replay preserves public and relevant rejected
roots; `--verify-sources` additionally replays the original local game evidence.

Related tails share only 64 stems, and the host is shared. Fresh final roots
do not prove statistical independence or representativeness. Internal search
nodes, unsaved games and dynamically constructed fixtures are not fully covered.
Earlier game scores are used only for explicitly labeled planning, not pooled
with new results or used to select new openings.

## Resources and one-attempt operating boundary

Starts are accepted only **23:00–23:30 Europe/Helsinki**, with the following
**07:00** cutoff. Civil boundaries are converted to UTC across DST. There is
no daytime flag or inherited daytime permission. A different launch window
would require a separately documented, tested amendment and fresh authorization.

Estimate **6–8 hours**: the prior 512-game four-worker 60+0.6 campaign took
6h10m50s; four times as many games at quarter clock duration gives a rough
6h11m planning estimate. Startup overhead, different games and host conditions
make this uncertain. Completion within the night is not guaranteed. Four slots
remain fixed: unresolved historical failures at higher concurrency are not
treated as repaired, and no concurrency increase is used to shorten the test.

Agree a fresh quiet window after preparation is tested and committed. Full play
requires paused competing LM Studio inference/builds, AC power, Automatic mode
and an awake host. `--quiet-host` records the operator's assertion, not permission
or continuous telemetry. Search-free readiness is short and may run separately.
No automatic schedule is created. Count all resident engines and active workers
against the shared 50% daytime / 80% nighttime budget; reservations are estimates,
not OS utilization caps. Preserve the stable GUI `0.1-dev-4b8b35d` and owner settings.

Monitor input identities, aggregate resources and active wall/monotonic continuity
approximately each second. A gap above five seconds, backward clock, changed
input, insufficient budget or cutoff invalidates completion. Cancel and await
owned children, preserve evidence and verify OS cleanup before releasing the host.
No retry, restart, resume, replacement game, partial-sample qualification,
extension or selective exclusion. No statistical stopping before all 1,024 pairs.

## Fixed inferential rule and sensitivity

The old Hoeffding rule remains unchanged for historical results. For this new
experiment, normalize each complete pair's candidate points by two, giving
`X_i` in `{0, 0.25, 0.5, 0.75, 1}`. Treat the pair as the unit; never treat its
two games as independent observations. At the fixed endpoint compute:

```text
lambdas = (0.125, 0.25, 0.5, 1.0), weights = (1/4, 1/4, 1/4, 1/4)
E_plus(m)  = mean_lambda product_i [1 + lambda * (X_i - m)]
E_minus(m) = mean_lambda product_i [1 + lambda * (m - X_i)]
```

Invert each monotone function against **40**, using log products/log-sum-exp and
bisection over `[0,1]`. Retain boundary values explicitly. The lower endpoint
comes from `E_plus`, the upper from `E_minus`. Each side has a 0.025 error budget,
so the resulting interval has conditional two-sided 95% coverage. The code is
independently authored from the bounded-mean betting framework of
[Waudby-Smith and Ramdas, version 7](https://arxiv.org/abs/2010.09686v7).
No upstream implementation is embedded or imported.

Sufficient assumptions are a common conditional mean for the pair-score sequence,
or independent pair scores at this fixed endpoint. In the latter case,
expectation factors; the arithmetic-geometric mean inequality bounds each
product by `[1 + lambda * (average expected score - m)]^n`. This targets the
average expectation even if independent pairs have different means. The broader
fixed-endpoint argument does not justify optional stopping. Related stems and
shared-host effects mean these assumptions remain unverified; label the interval
conditional and do not present it as a general rating guarantee.

Qualification requires complete independently audited evidence, unchanged inputs,
no exclusions and **zero time forfeits by either role**. An operational failure
or any forfeit blocks eligibility, regardless of scored result. Otherwise:

- Lower score endpoint strictly above 0.5: eligible for a separate strength review.
- Upper score endpoint strictly below 0.5: negative evidence for this matchup.
- Otherwise: inconclusive; keep defaults unchanged and do not enlarge the sample.

The descriptive transform `400*log10(score/(1-score))` and interval endpoints are
relative to this opponent/control only, never an absolute engine Elo rating.
Live W/D/L is provisional; no interval or promotion verdict is issued mid-run.

Planning uses a symmetrized historical pair histogram, then an exponential tilt
to several hypothetical effects, with seed `20261029413` and 5,000 simulated
samples of 1,024 pairs each. The normalized-score probabilities at the null
are `[1, 38.5, 177, 38.5, 1] / 256`, ordered from zero through one; exponential
tilting targets each stated score mean. Approximate positive-detection rates are **6% at +5 Elo,
51% at +10, 95% at +15 and nearly 100% at +20**, conditional on that synthetic
model. These are neither forecasts for NNUE nor measured new strength. A
representative near-null mixture interval is roughly 48.58%–51.42%, versus the
old Hoeffding interval's 45.76%–54.24% at 1,024 pairs. Other distributions or
dependence can give much weaker sensitivity. This is a practical +15-Elo-scale
screen; reliable +5-Elo qualification would require substantially more compute.

## Mandatory short-clock operational gate

Every authorized `run` begins with **eight development games / four pairs**,
one color-reversed pair in each of four concurrent slots, before launching any
qualification game. Copy the complete histories of `development-01`,
`development-05`, `development-08` and `development-09` from the existing
`tests/data/openings-development.json` into separately pinned smoke suites.
The copied suites are `tests/data/phase4f13-match-smoke-01.json` through `-04.json`,
with seeds `202610304151`–`202610304154`. These exposed e4/d4/c4/Nf3 roots are
not qualification observations.

Both frozen binaries use the exact 15+0.15 settings, options and resource
reservation above; the evidence is explicitly marked smoke. The stage is
bounded to **600 seconds**, within the same original overnight cutoff, and
shares aggregate resource/continuity supervision. Independent raw PGN/UCI/clock
audit must verify all eight completed games, zero forfeits/failures and clean
process exits before any held-out game starts. Smoke provides no strength
inference and is never pooled with the 1,024 qualification pairs. It does not
prove that a full night will be free of timing failures.

A failed, interrupted or overdue smoke stage aborts the attempt with evidence
preserved. No retry or replacement is automatic. Its runtime and the independent
audit consume the original launch window; held-out work must still begin before
23:30. No fresh cutoff is created between stages. The 6–8-hour estimate is for
the full match, with up to ten additional minutes reserved for this gate.

## Preparation and audit

Validate the generator, new two-binary launcher, independent raw-game auditor
and statistical helper, including corrupt/partial evidence and numerical cases.
Replay generation from original local sources. Pin all assets before actual
search-free readiness, audit its two handshakes/clean exits independently, and
commit tested preparation. Readiness certifies no short-clock game performance; the mandatory operational
gate remains pending until a fresh quiet window is confirmed.

The final auditor reconstructs all PGN/UCI histories, options, role binaries,
charged clocks, pair membership, resource coverage, cleanup and statistics. It
must not import the launcher's configuration or alter frozen historical globals.
Write every audit to a fresh external path. Preserve failed preparation checks
and any interrupted campaign. Report every failure and limitation in roadmap,
handover, validation and results; no default change, release or push is automatic.


## Commands

Search-free check and independent audit (use fresh output paths):

```sh
python3 tools/run.py --offline tools/qualify_phase4f13.py check > results/nnue-match-ready-new.json
python3 tools/run.py --offline tools/audit_phase4f13.py --preflight results/nnue-match-ready-new.json --output results/nnue-match-ready-audit-new.json
```

Only after fresh operating confirmation, within the admitted night window
(the run performs its mandatory development smoke gate first):

```sh
python3 tools/run.py --offline tools/qualify_phase4f13.py run --quiet-host --output results/phase4f13-match-new
python3 tools/run.py --offline tools/audit_phase4f13.py --campaign results/phase4f13-match-new --output results/phase4f13-match-new-audit.json
```

A launch operator must retain separate start/exit receipts and verify that the
runner, all engines and any sleep inhibitor have exited. The campaign supervisor
owns its cutoff and resource checks; a progress monitor must only read evidence.
The command does not schedule a run or itself prevent lid-close sleep. Never use
`--quiet-host` to infer an unanswered operator confirmation.
