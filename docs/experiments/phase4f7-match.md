# Phase 4F.7 — isolated TT Move Hints strength qualification

Protocol: `phase4f7-hints-512-v1`. Declared October 26, 2026, before opening
generation or held-out play. The completed [tactical comparison](../reports/2026-10-26-phase4f7-results.md)
found no observed serious blocker to this separate strength screen. This new
campaign does not alter the earlier puzzle protocol or parked combined-policy
campaign. No engine, evaluation, timing-policy or default changes are made.

## Frozen comparison

Both roles use the same native macOS ARM64 generic executable from
`a1b2331273f5baf4fcc2c53ee96a3759337e2399`, already preserved at
`build/experiments/phase4f7/chess0live`:

- Executable SHA-256: `6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Existing build/source provenance: `build/experiments/phase4f7/manifest.json`.
- New preparation pins: `tests/data/phase4f7-match-pins.json`.

| Setting | Candidate | Opponent |
| --- | --- | --- |
| TT Move Hints | true | false |
| Late Move Reductions | true | true |
| Capture Ordering | mvv-lva | mvv-lva |
| Time Policy | classic | classic |
| Threads / Hash | 1 / 64 MiB | 1 / 64 MiB |

Both explicitly disable Deep Quiet Reductions, Countermove Ordering, Null Move
Pruning, Reverse Futility Pruning, QSearch SEE Pruning and ProbCut. Both use
Move Overhead=20 ms, empty SyzygyPath, SyzygyProbeLimit=0 and SyzygyProbeDepth=1.
Ponder and Search Diagnostics are false. There is no opening book, strength
limit or tablebase assistance. Check the current advertised UCI types, defaults,
combo choices, ranges and exact applied settings; TT Move Hints must be the
only role difference. Retain process identities and full raw UCI evidence.

The current binary/source provenance and all prepared tools, tests, protocol,
corpus and exclusion inputs are frozen before readiness and the local preparation
commit. Keep the existing engine and historical sources unchanged. A corrective
tool change after freezing requires a recorded new preparation; never silently
rewrite earlier reports or pins. Readiness sends no `position` or `go` commands.

## Fixed sample and opening provenance

- 512 games: 256 opening pairs, reversing candidate color in each pair.
- Four shards, 64 pairs each; seeds `202610264701` through `202610264704`.
- Time control: 60 seconds plus 0.6 seconds per move.
- Four active search workers, eight resident engines, at least 6 GiB reserved.
- Maximum 512 searched plies; exhaustion produces incomplete evidence, not a draw.
- Startup allowance 30 seconds and protocol watchdog 5 seconds; watchdog grace
  is not credited to the chess clock. Time forfeits remain scored results.
- Pinned referee `chess==1.11.2`, legal terminal outcomes and available
  threefold/fifty-move claims. No evaluation-based adjudication.

Use the project's original 64 opening stems and fresh deterministic legal tails
from the `phase4f7-hints-512-v1` domain and the declared seed stream. Require 256
globally distinct legal, nonterminal roots, full original move histories and
32 roots per side to move in each shard. Save generator, source/exclusion hashes,
selection attempts and malformed-source records. Do not select by evaluation,
engine preference or game result.

Exclude known prior opening-suite roots, recorded legal game/mainline positions,
valid literal test/tool FENs and exposed puzzle/profile roots, including the
parked combined-policy roots, completed LMR campaign and Phase 4F.7 puzzles.
Freeze the canonical exclusion catalog and its source identities before use.
The compact public catalog contains public roots and any rejected exposed
candidates; complete saved-game disjointness also requires replaying the
original local PGNs against their recorded identities. Local games are not
redistributed as opening assets. Historical campaigns supply exclusions only;
their scores are not pooled.
Shared opening stems and unrecorded engine-internal search positions limit
independence and claims about exposure. Referee replay is allowed in preparation;
no held-out root is searched before this preparation is tested and committed.

One fixed attempt only: no score-based early stopping, retries, replacements,
extensions, resumption, selective omissions or pooling. Preserve every failed
or interrupted attempt. A complete independent audit is required before results
can be interpreted as this campaign's strength evidence.

## Resources, timing and clock health

Honor the shared 50% daytime / 80% nighttime resource budget. Count all four
active workers and eight resident engines in aggregate, reserving at least
6 GiB for hash/network/state. Reservations approximate resources and are not
measured OS utilization limits. Keep other engine searches and builds separate.

This declared launcher permits starting only **23:00–23:30 Europe/Helsinki**
and stops at the following **07:00**. Derive the civil cutoff then compare UTC
instants across DST. Estimate 6–8 hours; completion within a night is not
guaranteed. A late start, cap or cutoff cannot become a smaller qualifying sample.
No daytime exception is authorized or silently inherited from the puzzle run.
Changing this timing policy requires a separately documented and validated
one-run authorization before launch. No automatic schedule is created.

Agree the run window with the owner after preparation. Keep AC power and
Automatic mode, pause competing inference/heavy work during the actual match,
and record the host context. LM Studio may run during the short, search-free
preparation checks. A foreground `caffeinate -i` wrapper can prevent idle sleep;
it does not replace active deadline/resource supervision.

Check aggregate admission and input identities before launch and during work.
Observe resources approximately once per second; an active-work wall/monotonic
gap over five seconds, backwards clock, changed input or inadequate budget
invalidates completion. Cancel and await every owned child at failure, signal
or cutoff, retain partial logs, and verify cleanup. No automatic retry.

The earlier higher-concurrency clock failures remain unresolved. The successful
lower-concurrency LMR campaign supports this bounded setup, not a universal clock
repair. Clock accounting remains go-send through callback receipt, including
transport and scheduling delay; no timing boundary is changed for this candidate.

## Predeclared decision and limits

The independent auditor must reconstruct all 512 games / 256 pairs, colors,
membership, complete legal histories, raw clocks/settings, file identities,
cleanup and resource coverage. Any incomplete game, exclusion or invalid evidence
blocks qualification. **Any time forfeit by either role blocks promotion
eligibility**, even when the candidate's scored result is favorable.

Use the existing conditional 95% pair-level Hoeffding interval, with each pair's
candidate score normalized to [0,1]. For 256 pairs its radius is
`sqrt(log(40)/(2*256)) = 0.0848813447`. Independence between pairs is an assumption
that shared opening stems do not establish; report the bounds as conditional.

- Eligible only for a **separate default review**: complete valid evidence,
  zero forfeits, observed score at least 50.72%, and lower bound strictly above
  50%. Here this requires **at least 299.5/512 candidate points**.
- Negative evidence: valid complete evidence with upper bound below 50%,
  requiring **at most 212.5/512 points**.
- Otherwise inconclusive: leave defaults unchanged and explicitly park/reject
  the experiment instead of quietly increasing the sample.

This conservative sample may miss small gains. Eligibility would concern this
isolated setting at matched single-thread blitz; it does not establish
eight-thread match strength, performance against other engines, absolute Elo,
other time controls or universal nonregression. No option is promoted by a
puzzle pass, greater depth, faster NPS, or preparation/readiness alone.

## Preparation commands

Dependencies prepare automatically through the existing isolated tool launcher.
Historical Makefile targets remain unchanged to preserve earlier pinned inputs.

```sh
python3 tools/run.py tests/phase4f7_openings_test.py
python3 tools/run.py tests/qualify_phase4f7_test.py
python3 tools/run.py tests/audit_phase4f7_test.py
python3 tools/run.py tools/generate_phase4f7_openings.py --check --verify-sources
python3 tools/run.py tools/qualify_phase4f7.py check
```

Save readiness output and audit it before any launch. The preparation report
will record commands, checks and pins. The owner handles GitHub pushes manually.
Preserve stable GUI `0.1-dev-4b8b35d`, normal binaries, owner batch settings,
README introduction, prior evidence and all engine source files.
