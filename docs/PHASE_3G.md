# Phase 3G: fresh LMR blitz screen

Status at the v2 freeze: preparation complete on October 18, 2026; no campaign
has started. The original v1 protocol and suites were recorded in `c177804`.
Protocol identifier: **`phase3g-lmr-512-v2`**. The owner explicitly authorized:
"I authorize a daytime exception; prepare and validate the necessary protocol
change, then run now." This amendment is frozen before the first game.

The only operating change is permission for this one attempt to start during
**October 18, 2026, 07:00–23:00 Europe/Helsinki**, with `--allow-daytime` and the
recorded authorization `owner-20261018-phase3g`. The usual 50% daytime / 80%
nighttime resource policy and original next-07:00 cutoff remain in force.
A daytime launch therefore has more possible wall time than the original night
window; this is an explicit pre-run difference. No opening, sample size, engine,
option, chess clock, statistical rule, or default changes. Historical v1 readiness
evidence is preserved; v2 gets a separate readiness record. No schedule or
automatic retry is authorized. Running and auditing the sample is the next step.

## Hypothesis and prior evidence

The unchanged [conservative LMR experiment](SELECTIVE_SEARCH.md) might make
better decisions within the same chess clocks by reducing later quiet moves.
It can also miss tactics. Test it on the retained Phase 3F engine, with the
same executable and network in both roles and **LMR as the only changed option**.
This measures the combined operating context of the updated engine; it does
not retrospectively qualify the older executable or separate NNUE speed gains
from their possible interaction with reductions.

The exposed [Phase 2D LMR screen](reports/2026-10-16-phase2d-lmr.md) scored
35W/82D/11L, 76/128 points (59.375%), with a conditional 95% interval of
42.40–76.35%. Its decision remains **inconclusive**. Its earlier eight-game
development smoke scored 2W/2D/4L. Neither is pooled with this new sample.
No LMR threshold or search algorithm is changed or tuned for Phase 3G.

## Frozen inputs and isolation

Both roles use a byte-identical copy of the retained Phase 3F executable:

| Input | Location / SHA-256 |
| --- | --- |
| Executable | `build/experiments/phase3g-20261018/chess0live` |
| Executable SHA-256 | `edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b` |
| Implementation | `500b022`; Phase 3F qualification recorded by `e063c32` |
| Network | `networks/nn-1a298aa575a0.nnue` |
| Network SHA-256 | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |

The launcher and independent auditor each declare these opening-file pins:

| File in `tests/data/` | SHA-256 |
| --- | --- |
| `openings-phase3g-1.json` | `e40da564ea899dacdbfce4ab2fc92fb0caf42c14d630de1a065d7cf75f822b97` |
| `openings-phase3g-2.json` | `6ea77165730e2aa5d5d9243649af6297fe3683877ca2736c5c119e6deed6c7d2` |
| `openings-phase3g-3.json` | `3de297a67e0423299b715e7ce7c71102317277fc627ce52d0fef13ed6f7ae2c9` |
| `openings-phase3g-4.json` | `7a2670d433329dc46e6536202c2a87e964d00dcb5683123a3ca563979da2efe1` |

Generation metadata SHA-256:
`b9677909d8d31365725880badd55e9c5d67089efdb3628af0761b96d56e98669`.
The engine copy is separate from ordinary rebuilds and both preserved
GUI snapshots (`0.1-dev-4b8b35d` and `0.1-dev-phase3f-20261017`).

Candidate: `Late Move Reductions=true`; opponent: `false`. Both use:

- `Time Policy=classic`, `Capture Ordering=mvv-lva`.
- Threads 1, Hash 64 MiB, Move Overhead 20 ms, Ponder false, Search Diagnostics false.
- **60 seconds + 0.6 seconds per move**; startup timeout 30 seconds and protocol
  watchdog grace 5 seconds. Grace is not extra chess thinking time.
- Maximum 512 searched plies; a capped game is incomplete, never a scored draw.
- No opening book, tablebases, resignation, or evaluation-based adjudication.
- Pinned original referee implementation with `chess==1.11.2`; automatic draw
  claims include a claim available by announcing the next move. The documented
  conservative insufficient-material rule for a flagfall remains unchanged.

## Original opening construction, fixed before any search

`tools/generate_phase3g_openings.py` independently composes 32 legal 16-ply
stems from familiar chess patterns: 12 e4, 12 d4, four c4, and four Nf3 starts.
No game database, external book, or asset from the owner's previous engines is
imported. Prior project suites are read only for exclusion checks.

Each stem supplies eight continuations. Variants 0–3 end at 19 plies; variants
4–7 at 20. Each continuation move is sampled from sorted legal moves using the
generator's fixed SHA-256 sampling procedure and seed `20261018`. Rejection is
limited to terminal positions, duplicate canonical four-field final roots,
and overlap with the four earlier opening suites or the composed performance
suite. A maximum of 10,000 attempts per slot prevents unbounded generation.
Record rejection counts and the complete procedure; do not adjust selection
after engine evaluation, search, or outcomes. Preserve every full move history.

Variants 0 and 4 go to shard 1, 1 and 5 to shard 2, 2 and 6 to shard 3, and
3 and 7 to shard 4. The result is 64 roots per shard, 256 globally distinct
roots, and 128 roots for each side to move. Within each shard, every root is
played twice with reversed engine colors. Shard shuffle/color seeds are
`202610181`, `202610182`, `202610183`, and `202610184` respectively.

The random continuation moves are **not evaluated for balance or quality**.
Related stems create related positions, and color reversal balances assignment,
not position quality. This deliberately finite screen is not a representative
opening book or an independently sampled rating pool. Do not infer independence
from unique FENs, random ordering, or splitting work across four shards.

## One fixed sample and decision

Run exactly **256 opening pairs / 512 games**, once. Four 64-pair shards are
execution partitions, not four separately qualifying experiments. Use one
pooled decision after every game and independent audit passes. Keep all shard
and family diagnostics, without choosing favorable subsets. Do not extend the
sample, replace games, retry a favorable subset, resume an interrupted run,
alter parameters, or stop early based on scores. Any later attempt needs a
new documented protocol and must disclose this attempt, including failure.

For each opening pair, average its two candidate scores (win 1, draw 0.5,
loss 0). Use the existing two-sided 95% Hoeffding interval on the mean of all
256 pair observations. Its half-width is
`sqrt(log(40) / (2 * 256)) = 0.0848813447`; clip bounds to [0, 1].
The interval is **conditional on independence between opening-pair observations**.
Related stems and common host/thermal effects can violate that assumption;
the reported bounds are not an unconditional general-strength guarantee.

The complete fixed sample must pass frozen input/options/source checks, legal
full-history PGN and raw UCI replay, clock/termination checks, exact shard
membership and color plans, aggregate resource accounting, and common cutoff
checks. Missing, interrupted, capped, setup-failed, protocol-failed, corrupted,
or drifted evidence yields **invalid/incomplete**, with no qualifying interval.
Unexpected engine stderr also invalidates the inherited raw-audit protocol.
Valid clock forfeits are scored results and do not cause outcome-based stopping.

For complete valid evidence, apply these rules in order:

1. **Operational regression:** any candidate clock forfeit. Keep LMR off,
   regardless of the overall score.
2. **Eligible for confirmation review:** lower bound strictly above 0.5,
   requiring at least **299.5/512 points** and no operational regression.
   Prepare a separately frozen fresh confirmation; do not promote defaults.
3. **Negative evidence:** upper bound strictly below 0.5, requiring at most
   **212.5/512 points**. Keep LMR off.
4. **Inconclusive:** otherwise, including 299 or 213 points. This does not
   establish equivalence, harmlessness, or absence of a smaller improvement.

This is a coarse screen for a large effect. The earlier 59.375% score is only
about 0.89 percentage points above the new continuous positive boundary; it
does not establish likely success. A 5-point Hoeffding half-width would require
738 pairs. No power claim for small Elo gains or absolute rating is made.

## Runtime, cancellation, and resources

Normal launch remains **23:00–23:15 Europe/Helsinki**. For the owner's single
October 18 exception, the explicit `--allow-daytime` flag permits launch only
on that Helsinki date between 07:00 inclusive and 23:00 exclusive. It does not
enable daytime runs on other dates. The master records `allow_daytime=true` and
`daytime_authorization=owner-20261018-phase3g`; ordinary night launches record
false and null. Child workers inherit this permission and the master cutoff
without requalifying the start window after readiness. The independent auditor
checks the date/window and authorization, including agreement across all shards.

Start after the owner's Cute Chess games and other heavy work have stopped.
Checking is allowed at any time and never sends a position or search to the
engines. No scheduler, unattended wait, or automatic restart is installed here.

Four games run concurrently, each with one active search and two resident
engines: **four active workers and eight resident engines in total**. The
supervisor checks the aggregate CPU allowance and conservative combined-memory
reservation before launch, at game boundaries, and every second during play.
Allow scheduling jitter, but a gap above five seconds while workers are active
stops the campaign. The auditor rejects gaps above five seconds covering an
active game or missing periodic monitoring; preflight and cleanup outside games
do not need the one-second cadence.
The owner can change the usual resource policy with `tools/resources.py`.
An allowance below this fixed campaign's needs aborts the campaign; it does
not pause chess clocks or silently change concurrency. Policy estimates are
not hard OS CPU/RSS limits. Do not compete with manual GUI games or compilation.

The previous 128-game run took 6h41m12s on the recorded 18-core host. Four
similarly sized shards could fit one night, leaving roughly 79 minutes from a
23:00 start. This is planning context only: different game lengths, machine
contention, and fixed chess clocks prevent a runtime guarantee. Faster NNUE
does not imply that timed games finish proportionally sooner.

Capture one common next Helsinki **07:00 cutoff before preflight**, including
correct daylight-saving conversion. It never moves later because a worker or
readiness check starts late. On cutoff, interruption, insufficient resources,
artifact drift, or an operationally invalid game, cancel all shard tasks and
await their engine cleanup. Retain journals, PGNs, transcripts, and unfinished
manifests. Cleanup may finish just after the cutoff; no new game may start then.
Valid clock forfeits remain scored, and all games continue unless a separate
operational condition requires cancellation.

## Reproducible workflow

Use Python with the pinned `requirements-match.txt` dependencies installed;
large artifacts stay local:

```sh
# Reproduce opening bytes using legal moves only; no engine search.
python3 tools/generate_phase3g_openings.py --check

# Readiness and frozen-input checks only; may run during preparation.
python3 tools/qualify_phase3g.py check

# Owner-authorized first attempt, October 18 daytime only, after GUI games end.
/usr/bin/caffeinate -i python3 tools/qualify_phase3g.py run --allow-daytime \
  --output results/phase3g-lmr-20261018-daytime

# After that one attempt, audit all raw evidence without an engine.
python3 tools/audit_phase3g.py \
  --campaign results/phase3g-lmr-20261018-daytime \
  --output results/phase3g-lmr-20261018-daytime/audit.json
```

`caffeinate` is optional and macOS-specific; it does not prevent lid closure,
explicit sleep, shutdown, or power loss. The example is a manual command, not
authorization for a scheduled launch. Use a new directory and preserve the
whole result tree. A fresh output name does not authorize a second attempt.

The master `campaign.json` freezes the protocol, all inputs, sources, settings,
four shard identities, resource-journal fingerprint, and common window.
Resource observations are appended to `resource-history.jsonl`, avoiding a
growing whole-file rewrite while games are timed. Each
`shard-1` through `shard-4` preserves the existing `launch.json` and `match/`
raw evidence format. The aggregate auditor declares expectations independently
of launcher configuration, reuses the raw per-game verifier, and namespaces
local pair IDs before independently recomputing the pooled statistics.
Existing Phase 2D commands and archived decisions remain unchanged.

After a real attempt, publish every result and operational limitation, update
the roadmap/changelog/handover, and make tested local commits on main.
Only update practical README instructions if their usage changes; preserve its intro.
The owner handles GitHub publishing. Until then, report preparation only.
