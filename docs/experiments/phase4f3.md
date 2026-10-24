# Phase 4F.3 — combined search policy qualification

Protocol: `phase4f3-combined-512-v1`. Declared October 24, 2026, before any
held-out game. This tests the complete package against current defaults;
individual component wins are not prerequisites. No engine code, evaluation,
timing policy or playing default changes as part of preparation.

## Frozen comparison

Both roles use the same native macOS ARM64 generic release from `ccb66a4`,
copied to `build/experiments/phase4f3/chess0live`:

- Executable SHA-256: `5714cd8ab2e0a4a721922fa5e02881329e8d865bff87829d8c20fb82302aa947`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Build/source provenance: `build/experiments/phase4f3/manifest.json`.
- Frozen corpus/provenance identities: `tests/data/phase4f3-pins.json`.

| UCI option | Candidate: combined | Opponent: current defaults |
| --- | --- | --- |
| Late Move Reductions | true | true |
| Deep Quiet Reductions | true | false |
| Capture Ordering | see | mvv-lva |
| Countermove Ordering | true | false |
| Null Move Pruning | true | false |
| Reverse Futility Pruning | true | false |
| QSearch SEE Pruning | true | false |
| ProbCut | true | false |

Both explicitly use Time Policy=classic, Hash=64 MiB, Move Overhead=20 ms,
Ponder=false, Search Diagnostics=false, empty SyzygyPath and SyzygyProbeLimit=0.
No opening book, strength limit, pondering or tablebase assistance. The tactical
comparison uses eight threads; the match uses one thread per engine. Report
these evidence scopes separately. The current executable's advertised defaults
and each applied option must pass readiness checks; older qualification tools'
LMR=false assumptions do not apply.

## Tactical screen

Freeze all 39 owner-supplied FENs in their original order from
`tools/batch_positions.py` into `tests/data/phase4f3-puzzles.json`. Leave the
editable owner runner unchanged. The full comparison searches every position
for 60,000 ms under each policy, using fresh processes and eight search threads.
Alternate which policy runs first by position. One engine searches at a time;
the 78 searches take approximately 78 minutes plus setup. A separate 1,000-ms
smoke uses the same positions/settings and is only an operational screen.

Retain raw UCI, actual options, all principal variations, final legal best/ponder
moves, scores, reported mates, wall/monotonic timings and file identities.
Report gains, losses and different mate distances without selecting favorable
positions. Exact score/move parity between different policies is not required.
The spreadsheet's mate annotations and a reported mating PV are not independent
proof of forced mate. Exposed puzzles are diagnostic data, not held-out strength
evidence. Do not tune the package against this suite.

Illegal output, missing scores, changed inputs, resource/monitor failure or a
reproducible serious tactical regression blocks progression to default review.
Investigate adverse tactical results before starting the strength campaign.
Keep incomplete/failed attempts; never quietly replace a case. A successfully
completed smoke does not substitute for the full tactical comparison.

## Fixed strength campaign

- 512 games: 256 opening pairs, colors reversed within every pair.
- Four shards, 64 pairs each; seeds `202610244301` through `202610244304`.
- 60 seconds plus 0.6 seconds per move; Threads=1, Hash=64 MiB per engine.
- Four active search workers; eight resident processes. Reserve at least 6 GiB
  including network/state overhead. This is an estimate, not an OS memory cap.
- Maximum 512 searched plies; a cap produces incomplete evidence, never a draw.
- Startup timeout 30 seconds and protocol watchdog 5 seconds. Watchdog grace
  is not credited to the chess clock. Count time forfeits in the score.
- Pinned referee `chess==1.11.2`; legal terminal results, available threefold
  repetition and fifty-move claims. No evaluation-based adjudication.

The new roots use the project's original 64 opening stems plus deterministic
legal tails from a new domain/seed stream. Require 256 distinct valid,
nonterminal roots, 32 roots per side to move in each shard, and full move
histories. Exclude previously exposed suite roots, saved legal game positions,
valid test/tool FENs and current profiling/puzzle roots. Record source digests,
malformed records and the canonical exclusion catalog. Prior campaigns supply
exclusions only. Shared stems, shared hardware and unlogged engine-internal
positions limit independence and exposure guarantees. No evaluation or result
filter selects roots.

This is one fixed attempt. No score-based stopping, retries, replacement games,
sample extension, resumption, selective omission or pooling with old results.
An interrupted campaign remains incomplete. Successful preparation and a local
commit are required before the first held-out search.

## Resources, timing and supervision

Honor 50% daytime and 80% during 23:00–07:00 Europe/Helsinki, or a separately
authorized owner override. Short correctness/smoke checks may run during the
day; full puzzle and strength runs require the night window or a new explicit
exception. Earlier exceptions do not apply. No schedule is created.

The match launches in the first half hour of the night and stops by the next
07:00. Estimate 6–8 hours, not a guaranteed finish. Derive the cutoff from civil
Helsinki time and compare UTC instants: October 24–25 crosses daylight saving
time and has nine elapsed hours between 23:00 and 07:00.

Recheck aggregate CPU/memory admission and pinned inputs before work and during
the run. Observe roughly once per second; any wall-clock or monotonic gap over
five seconds during active work invalidates completion. Cancel and await every
child on failure, interruption or cutoff. Preserve raw output and failure state.
Do not overlap these runs with development searches, builds or the other full
experiment. A foreground `caffeinate -i` wrapper on macOS may prevent idle sleep;
it is not a schedule and does not remove monitoring requirements.

## Predeclared decision

The independent auditor must verify all 512 games/256 pairs, membership, colors,
complete histories, legal output, raw clocks, exact settings, file identities,
process cleanup and resource coverage. Any clock forfeit by either role blocks
promotion eligibility even though it stays in the scored result.

Use the existing pair-level conditional 95% Hoeffding interval, with each pair's
candidate score normalized to [0,1]. Its radius for 256 pairs is
`sqrt(log(40)/(2*256)) = 0.0848813447`. This assumes independent pairs, which
the shared opening stems do not establish. Report that limitation explicitly.

- **Eligible for separate default review:** valid complete evidence, no clock
  forfeits, observed score at least 50.72%, and lower bound strictly above 50%.
  With this fixed sample, this requires at least **299.5/512 points**.
- **Negative evidence:** valid evidence with upper bound below 50%, requiring
  at most **212.5/512 points**.
- Otherwise **inconclusive**; leave defaults unchanged and make an explicit
  park/reject decision rather than quietly increasing the sample.

This conservative screen cannot resolve small improvements or prove universal
absence of strength loss. Any eligibility applies to this package at matched
single-thread blitz settings. Eight-thread puzzle behavior, SMP match strength,
performance against external engines and other time controls are separate.

## Commands

Preparation and checks (no held-out games):

```sh
make test-phase4f3
python3 tools/run.py tools/generate_phase4f3_openings.py --check --verify-sources
python3 tools/run.py tools/qualify_phase4f3.py check
```

See the current [report](../reports/2026-10-24-phase4f3.md) for the prepared
artifacts, completed checks and the exact remaining launch steps. Keep the
owner's stable GUI bundle `0.1-dev-4b8b35d`, normal binaries, README introduction,
editable puzzle runner and historical campaign artifacts intact. The owner
handles GitHub pushes manually.
