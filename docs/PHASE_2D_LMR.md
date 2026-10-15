# Phase 2D: isolated LMR qualification

Status: protocol prepared before play on October 15, 2026. This document defines
one fixed screen, `phase2d-lmr-128-v1`; a launch freezes its exact bytes as
`protocol.md`. Preparation and passing checks are not a completed match.
Classic timing, LMR off, and MVV-LVA remain defaults. No result is yet available
for this protocol, and no automatic schedule is created.

## Hypothesis and isolation

The [conservative one-ply reduction](SELECTIVE_SEARCH.md) may improve decisions
within the same chess clock by allocating less search to later quiet moves.
Reduced fail-lows can also hide tactics. The development node savings do not
establish strength, and the eight-game smoke's 2W/2D/4L result was unfavorable.
The subsequent bounded loss replay found no LMR-specific miss in its selected
roots but did not prove the heuristic safe. This screen tests the unchanged
candidate; no reduction thresholds are tuned for it.

Both roles use `build/experiments/lmr-20261014/chess0live`, SHA-256
`b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc`.
The implementation is recorded at `586b34f`; the frozen source/build manifest
is retained separately from ordinary rebuilds. Candidate: `Late Move
Reductions=true`. Opponent: `Late Move Reductions=false`. Both use `Time
Policy=classic`. This binary predates the SEE experiment, so baseline MVV-LVA
is inherent; do not send the later `Capture Ordering` option. The sole changed
option is LMR. Neither role uses the frozen time-policy executable.

Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Opening suite: `tests/data/openings-lmr-validation.json`, SHA-256
`1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7`.

The suite contains 64 independently composed full histories from the standard
initial position: 992 history plies, 15–16 per line, with 32 roots per side to
move. Coverage starts with 24 e4, 24 d4, eight c4, and eight Nf3 histories. Its legal, nonterminal final roots must be unique and disjoint
from all three previous opening suites: development, general validation, and
the now-exposed time-policy validation suite. No engine evaluation or game
outcome is used to select or filter these new lines. Composition from familiar
opening ideas is original work, not an imported game database or an asset from
the owner's previous engines. Related families remain related observations;
unique final FENs do not make this a representative random sample or prove
statistical independence. Playing both colors balances assignment, not the
underlying position's evaluated strength.

## Fixed sample and settings

- **64 opening pairs / 128 games**, seed `20261015`, all openings used once per
  color. Shuffle order and choose first-leg color with the runner's fixed seed.
- **60 seconds + 0.6 seconds per move**, Threads 1, Hash 64 MiB, Move Overhead
  20 ms, Ponder false, Search Diagnostics false.
- One sequential game at a time, two resident engines, one actively searching.
- At most 512 searched plies per game; reaching the cap is incomplete, not a draw.
- No books, tablebases, resignation, or evaluation-based adjudication.
- Pinned referee `chess==1.11.2`; documented automatic threefold and rule-50
  claims include a claim available by announcing a next move.
- No outcome-dependent stopping, discarded losses, repeated openings,
  parameter changes, replacement games, or enlarging the sample after results.

## Predeclared interpretation

Use the existing pair-level two-sided 95% Hoeffding interval, independently
recomputed by the evidence auditor. Each pair observation is its two candidate
game scores divided by two. For 64 pairs the half-width is
`sqrt(log(40) / 128) = 0.1697626895`. Bounds are clipped to [0, 1].
This interval is conditional on independent opening-pair observations. Shuffling
hand-selected related openings does not establish that assumption; conclusions
are limited to this configuration and suite, not a general Elo rating.

Interpret only the complete fixed sample with a passing audit: correct frozen
binaries/network/suite/options, all 128 games and reversed-color pairs, legal
full PGNs, matching clocks and terminations, no exclusions or artifact drift.
Missing, interrupted, capped, corrupted, setup-failed, or protocol-failed
evidence makes qualification invalid/incomplete. Any unexpected engine stderr
also invalidates this frozen protocol. Clock forfeits are real scored outcomes
and are retained in the sample, never silently excluded.

For valid complete evidence, in this precedence order:

1. **Operational regression:** any candidate clock forfeits. Keep LMR off and
   investigate, regardless of score.
2. **Eligible for confirmation review:** the lower 95% bound exceeds 0.5, with
   no operational regression. This requires at least **86/128 points** and
   warrants a separately frozen fresh confirmation campaign. It does not
   automatically change defaults or establish general superiority.
3. **Negative evidence:** the upper bound is below 0.5, at most **42/128 points**.
   Keep LMR off and use this exposed result only as development evidence.
4. **Inconclusive:** otherwise, including 85.5 or 42.5 points. Keep LMR off;
   this does not establish equivalence or harmlessness.

This conservative screen can miss small improvements. The increased sample
reduces the previous screen's uncertainty but is still not a precision Elo
measurement. Do not substitute a more favorable criterion after seeing results.
SEE remains a separate experiment, and no combined-option test is implied.

## Runtime and resources

The normal long-test window is **23:00–07:00 Europe/Helsinki**, at up to 80% of
local resources. The completed time-policy campaign's daytime exception is
consumed and does not cover this run. Start manually in the night window;
`--allow-daytime` would need a new explicit owner authorization. No scheduler,
recurring task, cloud compute, or automatic resume is installed.

The previous 64-game campaign took 2h53m49s, including setup. Doubling that is
about 5h48m of planning context, not a runtime guarantee: different openings,
game lengths, and search decisions can change duration. Even an eight-hour
window is not a worst-case completion guarantee. The original next Helsinki
07:00 cutoff survives preflight; if unfinished, cancel active work, await child
cleanup, and preserve the incomplete campaign. Never shrink the sample, extend
the window, or merge partial output into a completed result after looking at it.

The resource policy is an aggregate worker/memory budget, not a hard operating
system utilization cap. One active search worker is comfortably within the
specified desktops' limits. Avoid competing engine searches or compilation
during measured play. On macOS a foreground `/usr/bin/caffeinate -i` assertion
may keep the system awake for this run only; it does not prevent lid closure,
explicit sleep, power loss, or shutdown.

## Reproducible workflow

```sh
# Preflight only: no position/go, held-out evaluation, or timed game.
python3 tools/qualify_lmr.py check

# Manual launch within the normal overnight window, fresh directory only.
/usr/bin/caffeinate -i python3 tools/qualify_lmr.py run \
  --output results/phase2d-lmr-20261015

# After completion, independently audit the saved evidence without an engine.
python3 tools/audit_lmr.py \
  --campaign results/phase2d-lmr-20261015 \
  --output results/phase2d-lmr-20261015/audit.json
```

The launcher pins artifacts and freezes configuration, tool/source fingerprints,
the protocol, platform, actual UCI readiness/options, and the allowed window in
`launch.json`. It uses the same tested runner as the first screen. The new
profile shares lifecycle code, but the auditor independently declares its
sample, option, and artifact expectations; a manifest cannot choose its own
acceptance criteria. The historical time-policy command still audits its
original 32-pair protocol. Subsequent live-source edits are reported separately
from the frozen before/after integrity evidence of a completed campaign.

Raw evidence under the ignored result directory includes full opening histories,
the fixed plan, per-game PGNs and UCI transcripts, game journal, summary, launch
record, frozen protocol, and independent audit. Preserve the entire directory;
existing campaigns and audit files are never overwritten. The GUI snapshot
`0.1-dev-4b8b35d` and all frozen engine/network artifacts remain unchanged.
After audit, publish a concise versioned result report and update the
[roadmap](ROADMAP.md), README, changelog, and handover. The owner pushes GitHub.
