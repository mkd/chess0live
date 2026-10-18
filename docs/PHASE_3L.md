# Phase 3L: prepare fresh LMR qualification

Prepared October 18, 2026 after the independently audited
[Phase 3K operational pass](reports/2026-10-18-phase3k-console-operations.md).
**Status: implementation prepared; this document is the fixed protocol.** The
owner authorized this phase and plain-text console diagnostics on October 18.
Current validation/readiness status is recorded in the
[Phase 3L report](reports/2026-10-18-phase3l-preparation.md), outside this protocol.
Preparation does not launch a match or create a schedule.

## Scope and exit

Remove `info string` prefixes from explicit console board/evaluation/help/perft
output, preserving standard UCI search/error messages. Verify signed mate and
centipawn reporting without changing search logic. Update practical instructions
and retain the README introduction and stable GUI bundles.

Finish preparation once the fresh input catalog/generator, campaign pins,
launcher/auditor tests, and serial readiness pass. Do not add new pruning, clock
policies, repeat canaries, or silently promote LMR. The broader roadmap moves to
cache efficiency, Lazy SMP, and optional Syzygy support after this checkpoint;
a frozen campaign can be run separately without blocking unrelated development.

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
   Use domain `chess0live.phase3l.openings.v1` and generation seed `2026101818`,
   recorded before generating continuations.
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

## Prepared inputs and implementation

- Engine: `build/experiments/phase3l-20261018/chess0live`, from tested source
  revision `56ddbde35104a4d295b871cc570a6a268adb2b62`; SHA-256
  `e7c9222c37bacecc3fa0571dd4b19c0e4fc1215dc37fadd42030f610b59b5c31`.
- Build manifest: adjacent `manifest.json`; SHA-256
  `bf7360cfd3306dd701eba742fc2a1495416a28920554a60afb784734755a097e`.
  It records compiler, flags, platform, engine source hashes, and native tests.
- Network: `nn-1a298aa575a0.nnue`; SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Generator: `tools/generate_phase3l_openings.py`; SHA-256
  `82b91b7af9e54ae114900c05aab535352bcc4713657afe63c95aa212eacf7c04`.
- Exclusions: `tests/data/phase3l-exclusions.json`; 851 canonical roots from 39
  sources, SHA-256 `f645aafc49d6dee36c8b1b492a0b3fa67665713281a68453f48be4b354ddd9d9`.
- Generation metadata: `tests/data/phase3l-generation.json`; SHA-256
  `a5d6adaeb805635b9f836e0dfd5228effedfef14fe9ffcc28c285804bc7bbde4`.
- Four suites: `tests/data/phase3l-lmr-01.json` through `-04.json`. Exact digests
  are in generation metadata and independently pinned in launcher and auditor.
  All 256 roots are distinct, 128 per side to move, with zero terminal,
  duplicate, prior-overlap, or SHA-word rejection in this generation.
- Shuffle seeds, shards 1–4: `2026101831`, `2026101832`, `2026101833`, `2026101834`.
- Dedicated tools: `tools/qualify_phase3l.py`, `tools/audit_phase3l.py`;
  `make test-phase3l` checks generator, lifecycle, and independent audit behavior.
  `make test-qualification` includes this target alongside historical profiles.

Generation/reproduction uses the pinned canonical exclusion manifest, so future
fixture edits cannot change this suite. `--verify-sources` additionally verifies
and replays original catalog artifacts when available; that explicit provenance
check passed at preparation. Missing local ignored sources do not prevent public
reproduction. The missing second October 18 manual PGN and unsaved/dynamic test
states cannot be exhaustively cataloged; see the manifest's limitations.

## Readiness requirements

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

The consumed Phase 3G daytime exception does not transfer. The current launcher
has no daytime switch. Do not create a schedule or start the long campaign as
part of this preparation checkpoint. A later launch must fit the normal overnight
policy; a new owner exception would require an explicit protocol/tool update
before any game, not reuse of historical permission.

## Reproduction and execution interface

```sh
make test-phase3l
python3 tools/generate_phase3l_openings.py --check
# Optional audit of original catalog artifacts, when still available unchanged:
python3 tools/generate_phase3l_openings.py --check --verify-sources

# Any-time readiness: choose a new preflight filename, then audit it.
python3 tools/qualify_phase3l.py check > results/phase3l-preflight-new.json
python3 tools/audit_phase3l.py --preflight results/phase3l-preflight-new.json --output results/phase3l-readiness-audit-new.json

# Later foreground run, only in its launch window and a fresh directory:
python3 tools/qualify_phase3l.py run --output results/phase3l-campaign-new
python3 tools/audit_phase3l.py --campaign results/phase3l-campaign-new --output results/phase3l-campaign-audit-new.json
```

Do not overwrite existing preflight files with shell redirection. Run and audit
commands refuse existing output destinations. Readiness loads/configures the two
roles serially and sends no `position` or `go`; it is not a played match. Run
captures a fresh source snapshot before any game, monitors drift, and rechecks
readiness under the already fixed cutoff. Keep the frozen executable/manifest
and all evidence; a normal rebuild uses a different directory.
