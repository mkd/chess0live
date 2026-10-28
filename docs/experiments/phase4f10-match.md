# Phase 4F.10 — isolated Continuation History strength qualification

Protocol: `phase4f10-continuation-512-v1`. Declared October 28, 2026, before
opening generation or game play. The completed
[tactical comparison](../reports/2026-10-28-phase4f9-results.md) reported four
mates with Continuation History on versus three off, with all final moves
matching. It establishes neither repeatability nor playing strength. This new,
finite match addresses the latter without changing engine code or defaults.

## Frozen comparison

Both roles use the identical preserved native macOS ARM64 generic executable
from `69215b4c7a35bb0ba7ea4b1e9287e8f760199b6c`:

- Executable: `build/experiments/phase4f9/chess0live`, SHA-256
  `c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Build/source provenance: `build/experiments/phase4f9/manifest.json`, its
  `origin-manifest.json` and all 27 frozen source/dependency files.
- New preparation pins: `tests/data/phase4f10-match-pins.json`.

| Setting | Candidate | Opponent |
| --- | --- | --- |
| Continuation History | true | false |
| TT Move Hints | false | false |
| Late Move Reductions | true | true |
| Capture Ordering | mvv-lva | mvv-lva |
| Time Policy | classic | classic |
| Threads / Hash | 1 / 64 MiB | 1 / 64 MiB |

Both explicitly disable Deep Quiet Reductions, Countermove Ordering, Null Move
Pruning, Reverse Futility Pruning, QSearch SEE Pruning and ProbCut. Both use
Move Overhead=20 ms, empty SyzygyPath, SyzygyProbeLimit=0, SyzygyProbeDepth=1,
Ponder=false and Search Diagnostics=false. There is no opening book, strength
limit or tablebase assistance. Validate the complete current advertised UCI
schema and applied settings; Continuation History must be the only difference.

Freeze all preparation code, tests, protocol, corpus, exclusions, dependency
identities and build provenance before readiness and the local preparation
commit. Preserve historical inputs. A corrective tool change after freezing
requires a recorded new preparation, not silent replacement of evidence.
Readiness sends no `position` or `go` commands and does not play games.

## Fixed sample and opening provenance

- 512 games: 256 opening pairs, reversing candidate color in each pair.
- Four shards, 64 pairs each; seeds `202610284101` through `202610284104`.
- Time control: 60 seconds plus 0.6 seconds per move.
- Four active single-thread searches, eight resident engines, at least 6 GiB
  reserved for network/hash/state across the campaign.
- Maximum 512 searched plies; hitting this cap is incomplete evidence, not a draw.
- Startup allowance 30 seconds and protocol watchdog 5 seconds; watchdog grace
  is not added to the chess clock. Time forfeits remain scored results.
- Pinned referee `chess==1.11.2`; legal terminal outcomes and available
  threefold/fifty-move claims, without evaluation-based adjudication.

Use the project's independently authored 64 opening stems and deterministic
legal tails from the new domain `phase4f10-continuation-512-v1` and seed stream.
Require 256 distinct legal nonterminal roots with original move histories and
32 roots per side to move in each shard. Save generator/source identities,
selection attempts and malformed-source records. Never select by engine
evaluation, preference or results.

Exclude known prior opening-suite roots, saved legal game/mainline positions,
valid literal test/tool positions and exposed puzzle/profile roots. This includes
the completed 512-game TT Move Hints campaign and subsequent continuation-history
development/puzzle roots. Freeze the canonical exclusion catalog and source
identities. Public replay uses the compact catalog; complete saved-game
disjointness also requires replaying the original local PGNs with their recorded
identities. Local game evidence is not redistributed as an opening asset, and
historical scores are not pooled. Do not use the owner's other engines or assets.

Shared stems, related tails, unavailable internal search positions and unsaved
manual games limit independence and exposure claims. Referee replay is allowed
in preparation; do not search these roots before preparation is tested and
committed. One fixed attempt only: no score-based stopping, retries, replacement
games, extensions, resumption, selective omissions or pooling. Preserve every
failed/interrupted attempt. Qualification requires a complete independent audit.

## Resources, timing and clock health

Honor the shared 50% daytime / 80% nighttime resource budgets. Count all four
active workers and eight resident engines together. A 6 GiB reservation and
worker counts are admission estimates, not measured operating-system caps.
Keep builds and competing engine searches separate from the actual match.

The launcher accepts starts only **23:00–23:30 Europe/Helsinki**, stopping at
the following **07:00**. Derive the civil cutoff then compare UTC instants across
DST. Estimated duration is **6–8 hours**, informed by the prior four-worker
campaign; completion within the night is not guaranteed. A cutoff or cap cannot
turn an incomplete run into a smaller qualifying sample.

Agree a fresh quiet window after preparation. Previous puzzle/match daytime
exceptions have expired and do not apply here. A daytime launch requires its own
explicit authorization and documented, validated timing amendment. No automatic
schedule is created. Keep AC power and Automatic mode, pause LM Studio inference
and other heavy work during the actual match, and record host conditions. LM
Studio may run during the short, search-free preparation. A process-lifetime
sleep inhibitor helps prevent idle sleep but does not replace supervision.

Check aggregate admission and input identities before and during the run.
Observe resources approximately once per second. An active wall/monotonic gap
above five seconds, backward clock, changed input or inadequate resource budget
invalidates completion. Cancel and await all owned children at failure, signal
or cutoff, preserve partial logs, and verify cleanup. Do not retry automatically.
Previous higher-concurrency clock failures remain unresolved. Clock accounting
stays go-send through callback receipt, including transport/scheduling delay.

## Predeclared decision and limits

The independent auditor reconstructs all 512 games / 256 pairs, colors,
membership, legal histories, raw clocks/settings, identities, cleanup and resource
coverage. Incomplete games, exclusions or invalid evidence block qualification.
**Any time forfeit by either role blocks promotion eligibility**, even if the
candidate's scored result is favorable.

Use the existing conditional 95% pair-level Hoeffding interval, normalizing each
pair's candidate score to [0,1]. For 256 pairs the radius is
`sqrt(log(40)/(2*256)) = 0.0848813447`. Independence is an assumption, not established
by shared stems or a shared host; report the interval as conditional.

- Eligibility for a **separate default review** requires complete valid evidence,
  zero forfeits, observed score at least 50.72% and a lower bound strictly above
  50%. At this sample size that requires at least **299.5/512 candidate points**.
- Negative evidence requires complete valid evidence with an upper bound below
  50%, at most **212.5/512 candidate points**.
- Otherwise the result is inconclusive: keep the default unchanged and park
  promotion instead of increasing the sample or tuning against the results.

This conservative screen can miss small gains. It concerns this isolated setting
at matched single-thread blitz; it does not qualify eight-thread match strength,
other opponents/time controls, absolute Elo, or universal nonregression. No
automatic promotion follows from this run, tactical reports, greater depth or NPS.

## Preparation commands

The existing isolated tool launcher prepares dependencies automatically. Keep
historical Makefile targets and pinned helpers unchanged.

```sh
python3 tools/run.py tests/phase4f10_openings_test.py
python3 tools/run.py tests/qualify_phase4f10_test.py
python3 tools/run.py tests/audit_phase4f10_test.py
python3 tools/run.py tools/generate_phase4f10_openings.py --check --verify-sources
python3 tools/run.py tools/qualify_phase4f10.py check
```

Save and independently audit readiness before a launch. Record exact validation
and limitations in the preparation report. Preserve the normal release, stable
GUI snapshot `0.1-dev-4b8b35d`, owner batch settings, README introduction and all
prior evidence. The owner handles GitHub pushes manually.
