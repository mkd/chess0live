# Phase 2D: playing-strength qualification

Status: first fixed qualification screen prepared and tool checks passed on
October 15, 2026; ready for the explicitly authorized daytime launch.
No result is available. Engine defaults remain classic timing, LMR off, and
MVV-LVA capture ordering. This phase measures game outcomes, not NPS or nominal
depth. The full engine remains unreleased and unrated `0.1-dev`.

## First campaign: time management

The hypothesis is that the frozen hard-deadline forecast policy improves game
outcomes by avoiding expensive iterations unlikely to finish. The earlier
[development work](TIME_MANAGEMENT.md) selected this candidate. This first
qualification screen uses the already reserved opening suite without tuning
or searching its roots during preparation.

Both roles use `build/experiments/time-policy-hard-20261014/chess0live`, SHA-256
`cafaa3ae3e6500d75382b3cf943ebc23d2d154247bc18ac3b3254d206619a80c`.
This executable predates the optional LMR and SEE changes. Its source snapshot
and original manifest remain preserved; do not substitute a current rebuild.
The candidate uses `Time Policy=forecast`; the opponent uses `classic`.
No other engine option differs.

Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Openings: `tests/data/openings-time-validation.json`, SHA-256
`163bf4c34547a838c35e03103401c40d448a2f78c535254bf3727913b007b95b`.
All 32 full histories are legal and nonterminal (424 history plies); their final
positions are unique and disjoint from the earlier development/general-validation
suites. These are original, hand-selected opening lines, not a calibrated or
representative rating pool. Related opening families limit generalization.

Fixed before play:

- All 32 openings, both colors: **64 games**, seed `20261014`.
- **60 seconds + 0.6 seconds per move**, one search worker and 64 MiB hash per
  engine, 20 ms move overhead, ponder and diagnostics disabled.
- One sequential game at a time; two resident processes, one actively searching.
- Maximum 512 searched plies per game. A capped game is incomplete, never a draw.
- No books, tablebases, evaluation adjudication, or resignations.
- Referee: pinned `chess==1.11.2`, with the runner's documented automatic
  threefold/rule-50 claims, including claims available by a next move.
- No outcome-dependent stopping, exclusions, repeated openings, or parameter
  changes. Do not promote a favorable interim score to a completed experiment.

## Decision rule, predeclared October 15 before play

The runner's pair-level, two-sided 95% Hoeffding interval remains unchanged.
A pair's score is its two candidate game scores divided by two. The interval
assumes independent opening-pair observations; shuffling related hand-selected
openings does not establish that assumption. Any interval here is conditional
on those assumptions and applies only to this suite and configuration.

Require the whole fixed sample and a passing evidence audit before interpretation:
exact binaries/network/suite/options, all 64 games and reversed-color pairs,
legal PGNs, matching clocks/terminations, and no exclusions or artifact drift.
Missing, interrupted, truncated, or corrupted evidence prevents qualification.
Setup/protocol failures also prevent qualification. The frozen engine is expected
to be silent on stderr; any unexpected stderr invalidates this first protocol's
evidence and must be investigated. Time forfeits remain real
game outcomes and must never be silently removed from the score.

With valid complete evidence, classify:

1. **Operational regression:** any candidate clock forfeits. Keep classic;
   investigate separately, even if the score looks favorable.
2. **Eligible for confirmation review:** the lower 95% score bound exceeds 0.5,
   with no operational regression. This warrants a fresh confirmation campaign;
   it does not automatically change defaults or establish general superiority.
3. **Negative evidence:** the upper bound is below 0.5. Keep classic.
4. **Inconclusive:** otherwise. Keep classic; this does not establish equality.

For 32 pairs, the interval half-width is approximately 0.240081. The positive
screen therefore needs at least **47.5/64 points**; the negative screen is at
most **16.5/64**. This conservative screen will usually be inconclusive for a
small improvement. Do not replace the criterion or extend this sample after
seeing results. A follow-up needs its own frozen design and fresh openings.

## Launch and resource controls

The normal long-test window remains **23:00–07:00 Europe/Helsinki**, at up to
80% of resources; daytime is 50%. On October 15 the owner explicitly authorized
a daytime exception for this one 64-game campaign, with one search worker.
That exception does not change the percentage policy or authorize other long
jobs. No automatic schedule or recurring task is created.

The qualification launcher verifies pinned artifacts, the full legal opening
histories, referee version, resources, and both roles' UCI readiness/options
before any timed game. Its check command sends no `go` and does not evaluate
held-out positions. A run records the fixed configuration, source/artifact
hashes, platform, preflight, and window/exception in `launch.json`.

A normal launch outside the overnight window fails. `--allow-daytime` records
an explicitly authorized one-run exception. In either mode, the next Helsinki
07:00 is the cutoff: cancel active work, clean up engines, and preserve incomplete
games/results if the fixed sample is unfinished. This is not a pause/resume
system. Never merge a favorable incomplete subset into a complete experiment.
Machine sleep or an external interruption can also invalidate timing; keep the
computer awake and avoid competing engine jobs or compilation during games.

The owner GUI bundle `0.1-dev-4b8b35d`, frozen LMR/SEE binaries, network, and
opening files remain unchanged. The current campaign changes no engine source.

## Commands and evidence

From the project directory, with the pinned optional match dependency installed:

```sh
python3 tools/qualify_time_policy.py check

# Only for the explicitly authorized October 15 daytime exception:
python3 tools/qualify_time_policy.py run --allow-daytime \
  --output results/phase2d-time-policy-20261015

# Normal manual overnight launch; choose a fresh directory:
python3 tools/qualify_time_policy.py run \
  --output results/phase2d-time-policy-overnight

# After the complete campaign, independently replay its saved evidence:
python3 tools/audit_time_policy.py \
  --campaign results/phase2d-time-policy-20261015 \
  --output results/phase2d-time-policy-20261015/audit.json
```

A campaign directory contains `launch.json`, a frozen copy of this protocol,
and the runner's `match/` directory
with its plan, frozen openings, game journal, PGNs, protocol logs, and summary.
All raw evidence remains locally ignored. The audit reads saved evidence without
starting an engine, checks legal replay and actual clock/option records, recomputes
pair statistics, and applies the rule above. It reports subsequent live-source
changes separately from the frozen before/after integrity record. Existing
campaigns and audit outputs are never overwritten. No result or completed launch
is implied by these prepared commands. See [validation](VALIDATION.md) for the
tool checks completed before play.

On macOS, the authorized foreground run may be prefixed with
`/usr/bin/caffeinate -i` to prevent idle system sleep for that process's lifetime.
This does not change persistent power settings or protect against lid closure,
shutdown, or an explicit sleep command.

## Remaining Phase 2D work

After this screen, record its outcome and keep/reject/follow-up decision. Then
predeclare separate qualification for one search hypothesis (LMR or SEE) with
fresh full-history openings and classic timing. The existing 12 general-validation
roots are below the runner's 30-pair reporting floor; recycling them does not
create independent evidence. Do not combine experimental options or reuse the
time suite for tuning while calling it held out. Manual Cute Chess play is
optional feedback, not a prerequisite for this controlled comparison.
