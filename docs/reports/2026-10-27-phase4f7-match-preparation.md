# Phase 4F.7 — strength campaign preparation

**The isolated TT Move Hints match is prepared, tested and independently checked.
No match has started; hints remain off by default.** Preparation began October 26
and real readiness completed October 27, 2026, at 06:36:18 Helsinki.

## Prepared experiment

The [protocol](../experiments/phase4f7-match.md), declared before generation or
held-out play, specifies 512 games / 256 reversed-color pairs at 60+0.6. Four
single-thread searches share a minimum 6 GiB reservation across eight resident
engines. Both roles use Hash 64 and otherwise identical current defaults; only
TT Move Hints differs. This follows the completed eight-thread tactical screen,
where both settings found the same three mates and all final best moves agreed.

The original frozen native macOS ARM64 executable from `a1b2331` is reused;
no engine rebuild or change was made. Its SHA-256 is
`6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f`.
The pinned network and complete 25-file build-source provenance are checked.
New launcher, auditor, generator and tests leave historical helpers/Makefile
unchanged. There are 58 source snapshots and 57 preparation pins; the pin document
cannot include its own hash. Pin-file SHA-256:
`c6fde2f53461c81a65fdf80801df99686549f3e35b146f38f143b9c998e95708`.

The four fresh seeded shards contain 256 legal, unique, nonterminal roots,
balanced 32 per side to move in each shard. Generation uses original project
opening stems and deterministic legal tails, without engine evaluation or result
selection. All avoid the 217,477 known roots from 152 source records, including
2,284 saved games. Full source replay passed; no rejected generation attempts or
malformed saved-game omissions occurred. The compact public catalog records
public exclusions; reconstructing complete saved-game exclusion requires the
original local PGNs and recorded identities. These games are not redistributed.
Shared opening stems and unavailable internal search positions limit independence
and exposure claims.

## Validation

All **107 new tests passed** in the final combined check:

| Suite | Tests | Saved runtime |
| --- | ---: | ---: |
| Opening generation | 17 | 6.680 s |
| Launcher/supervisor | 32 | 13.097 s |
| Independent auditor | 58 | 66.972 s |

Coverage includes fixed settings, complete provenance and pins, duplicate input
keys, malformed/changed option declarations, legal roots/output, process identity
and exits, cancellation, clock/resource interruption, evidence membership and
decision thresholds. Synthetic failures are operational tests, not evidence of
strength or guaranteed overnight stability. The auditor test's expected
"Output exists" diagnostic tests preservation of earlier evidence; the suite
completed successfully.

Actual readiness started two serial engine sessions, PIDs 65583 and 65584,
validated all 20 UCI option declarations/defaults/ranges and required settings,
then verified both exited with code zero. Raw transcripts contain 13 commands
and 63 total events. No `position` or `go` command was sent. Python-chess retained
a benign warning for the engine's Syzygy-disabled informational line in stderr;
the raw logs and independent audit confirm tablebase assistance is disabled.

The independent readiness auditor passed with no errors. Its input map contains
2,293 file identities, including replayed local PGNs. All 58 snapshots, 57 pins,
complete build provenance, role settings, clean exits, opening exclusions and
resource admission passed. The host reported 18 logical CPUs and 64 GiB RAM;
the four-worker/6 GiB reservation fits either ordinary budget. This is a planned
reservation, not a measured CPU/memory utilization cap.

All 1,022 protected existing files and the README introduction remained unchanged,
including engine/shared/historical tooling sources, prior evidence, normal
binaries, stable GUI `0.1-dev-4b8b35d` and owner batch settings. New pins also
match. This checkpoint adds no search, platform execution claim, release,
strength claim or option promotion.

## Evidence and next step

Local evidence is in `results/phase4f7-match-preparation-20261026/`:
`initial-state.json`, three test logs, `openings-source-replay.log`, readiness
JSON/stderr, independent audit JSON/logs and `preservation.json`.

- Readiness SHA-256:
  `04198ca450a63f263dbb43e921b3ec4fef198edecb2f35c14b374c26d44af087`.
- Independent audit SHA-256:
  `12d76891bfe5f75a8a22bbbc6e067def34966805424925699b7edec8fb3f5a48`.

Agree a separate **6–8-hour quiet window** before launch. The frozen launcher
accepts starts only 23:00–23:30 Helsinki and stops by next 07:00. No schedule or
match is running; puzzle permission is not reused. LM Studio may run during
preparation; actual play needs paused competing inference and recorded
AC/Automatic mode. A daytime run requires a separately authorized, documented
and tested timing amendment.

One complete attempt only, no retries/extensions or replacement games. Any
forfeit by either role blocks eligibility for default review. With valid complete
evidence, at least 299.5/512 candidate points are needed for the conditional
pair-level lower bound to exceed 50%; 212.5 or fewer gives a negative upper
bound, and other scores are inconclusive. Shared-stem independence is an explicit
assumption, and a single-thread blitz screen cannot qualify all SMP settings.
Keep the earlier higher-concurrency clock failures unresolved. See the protocol
for the full gates and [tool guide](../TOOLS.md#check-the-frozen-move-hint-match)
for preparation/audit commands. The owner handles GitHub pushes manually.
