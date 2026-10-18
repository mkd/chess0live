# Phase 3L: prepare fresh LMR qualification

Prepared October 18, 2026 after the independently audited
[Phase 3K operational pass](reports/2026-10-18-phase3k-console-operations.md).
**Status: preparation plan only.** No new opening suite, campaign pins, dedicated
launcher/auditor, or readiness result exists yet. No match or schedule is active.
This document defines the next implementation checkpoint, not a launch command.

## Objective and fixed comparison

Prepare one new `phase3l-lmr-512-v1` campaign. Preserve the
[Phase 3G settings and decision rules](PHASE_3G.md#one-fixed-sample-and-decision):
256 new opening pairs / 512 games, four 64-pair shards, 60+0.6, four active search
workers/eight resident engines, Threads 1, Hash 64 MiB, overhead 20 ms, classic
timing, MVV-LVA, no ponder/diagnostics/books/tablebases/evaluation adjudication.
Use the same tested executable/network bytes in both roles; candidate LMR=true,
baseline=false. The strength campaign retains the successful Phase 3G limit of
512 searched plies/game; the Phase 3J/3K operational limits do not revise it.

Freeze all execution details before any game, with new identities and file
paths. Preserve historical protocols, exposed suites, raw evidence, and decisions.
Do not pool or resume Phase 2D/3G, replace games, selectively extend a sample,
change clocks, or stop early on score. A positive result permits a separately
frozen confirmation review; it never changes defaults automatically.

## Fresh inputs and exclusion audit

1. Catalog all previously exposed saved **root positions**, with provenance.
   Cover the original generator's five suite exclusions, all four Phase 3G
   shards, other development/benchmark/profiling roots, saved clock-probe roots,
   manually analyzed PGN positions, owner puzzle compatibility inputs, and the
   93 Phase 3K independent verification positions. Pin a deduplicated canonical
   root-key manifest; an explicit manifest may represent private/local inputs
   without publishing the workbook or importing an earlier engine's assets.
   Document missing provenance or unavailable source artifacts before freezing.
2. Independently compose 32 legal stems with the existing family allocation:
   12 e4, 12 d4, four c4, four Nf3. Generate eight continuations each, preserving
   complete legal histories, the 19/20-ply balance, and 128 roots per side to move.
   Use a new deterministic domain and fixed seeds recorded before generation.
3. Deduplicate and exclude canonical root collisions, retaining all rejection
   reasons/counts. Do not evaluate/search positions or select by score, material,
   engine preference, tactical outcome, or match result. Reproduce opening bytes
   from the pinned generator and independently replay every history.

These restrictions cover saved roots, not every internal node ever visited by
an engine. Related stems and shared machine conditions remain dependence risks.

## Decision and validity gates

Use the same conditional 95% pair-level Hoeffding interval: each pair averages
its two scores; at 256 pairs the half-width is `sqrt(log(40)/(2*256))`, about
8.488 percentage points. Its independence assumption is not guaranteed by
related stems or common thermal/scheduling effects. Apply these rules in order:

1. Missing, interrupted, capped, setup/protocol-failed, corrupted, drifted,
   unexpected-stderr, or otherwise invalid evidence: **invalid/incomplete**.
2. For complete valid evidence, any candidate clock forfeit: **operational
   regression**, regardless of score. Valid flagfalls stay scored and do not
   themselves trigger score-based stopping; baseline flags are also disclosed.
3. At least 299.5/512 candidate points, without regression: **eligible for fresh
   confirmation review**.
4. At most 212.5/512 points: **negative evidence**.
5. Otherwise: **inconclusive**, not proof of equivalence or no smaller benefit.

Do not infer an Elo gain, absolute rating, or release acceptance from the screen.

## Implementation and readiness work still required

- Freeze the actual tested engine commit/build manifest/compiler/flags and full
  executable/network hashes, Python dependency pin, opening/exclusion/generator
  identities, seeds, and all updated shared runner/supervisor/auditor sources.
- Implement dedicated Phase 3L launcher and independent auditor identities using
  tested shared machinery, without editing historical Phase 3G pins in place.
- Test thresholds and corruption rejection, all new pin/exclusion rules,
  four-worker aggregate budgets, writer failure, cancellation/cleanup, common
  cutoff, and periodic resource checks. Distinguish the four-worker campaign
  requirements from Phase 3K's successful two-worker check.
- Perform serial two-role readiness with **zero `position` or `go` commands**,
  independently inspect saved evidence, and commit tested preparation locally.
- Record a clear ready/not-ready checkpoint with exact commands and remaining
  limitations before launching anything.

## Launch boundary

Normal launch is 23:00–23:15 Europe/Helsinki, with one immutable next-07:00 cutoff
captured **before** readiness. Recheck aggregate resources before launch, before
each game, and every second during play; a gap above five seconds covering an
active game invalidates the campaign and stops it. Recompute memory reservation;
do not compete with GUI matches or compilation. Preserve cancellation ownership
until processes and outstanding I/O finish, including cleanup after cutoff.

The consumed Phase 3G daytime exception does not transfer. Do not create a
schedule or start the long campaign as part of Phase 3K. A later launch must fit
the normal overnight policy or a new explicit owner exception.
