# Phase 4F.10 — Continuation History match preparation

**The match is prepared, tested and independently checked. No games have
started. Continuation History remains off by default.** Search-free native
readiness completed October 28, 2026 at **10:35:09 Europe/Helsinki**.

## Fixed comparison

The [protocol](../experiments/phase4f10-match.md) was declared before generating
the new openings. It fixes 512 games / 256 reversed-color pairs at 60+0.6,
four simultaneous single-thread searches and eight resident engines with at
least 6 GiB reserved memory. Both roles use Hash 64 and identical settings apart
from Continuation History on versus off. TT Move Hints and other experimental
switches remain off; LMR is on. This follows the completed tactical comparison,
whose extra M9 report is not evidence of stronger play or a repeatable gain.

Both roles reuse the preserved source-`69215b4` binary at
`build/experiments/phase4f9/chess0live`, SHA-256
`c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`.
The pinned network, 27 frozen source/dependency files, committed-source map and
original build manifest agree. No engine was rebuilt or changed. The new tools
reuse the existing game/referee infrastructure without changing historical
helpers or their globals. Independent runner/auditor configuration checks agree.

There are **61 source snapshots and 60 preparation pins**; the pin document
is snapshotted but cannot contain its own digest. Pin-file SHA-256:
`ca31945bdc6a80ea03162ea4d73949f8cf81c662de4f2db8e6207eaf1954bd9e`.
Freeze these identities through the attempt. Corrective preparation changes
must be recorded before any play rather than silently replacing saved evidence.

## Fresh openings

The four new shards contain 256 distinct, legal, nonterminal roots, balanced
32 per side to move per shard. They use the project's original stems and fresh
deterministic legal tails, with the declared domain and seeds. No engine,
evaluation or game result participates in selection.

Full source replay excludes **266,535 known roots** from **169 source records**,
including all **2,796 saved games** and all 512 games of the completed hints match.
One exposed candidate tail was rejected deterministically and recorded; no
accepted root overlaps the recorded exclusions. There were no malformed-game
omissions. The public catalog supports deterministic regeneration; complete
saved-game disjointness requires the original local PGNs. Those games are not
redistributed or pooled as strength evidence. Shared stems and unavailable
internal search/unsaved positions limit independence and exposure claims.

## Validation

All **122 final synthetic tests passed**:

| Suite | Tests | Recorded runtime |
| --- | ---: | ---: |
| Opening generation | 17 | 3.033 s |
| Launcher/supervisor | 38 | 7.618 s |
| Independent auditor | 67 | 51.569 s |

Coverage includes settings isolation, duplicate/missing raw UCI declarations,
source and origin-manifest identities, malformed pins, resource and clock gaps,
cutoff/cancellation, child cleanup, changed membership/histories, forfeits and
decision thresholds. Historical daytime grants are rejected. Raw synthetic
fixtures exercise 128-game PGN/UCI replay without launching a chess engine.
Preliminary auditor fixtures lacked required fixture inputs; these fixture-only
errors were corrected before the final passing suite, and the failed log is
retained. The expected CLI "Output exists" diagnostic tests preservation of
existing evidence. These checks are operational evidence, not strength results.

Actual readiness opened two engine processes serially, validated all **21 UCI
option declarations** and applied settings, then verified both exited with code
zero. The saved transcripts contain **13 commands / 65 events**, with no
`position` or `go` command. Python-chess emitted the existing benign stderr warning
for the Syzygy-disabled informational line; raw evidence confirms no tablebase
assistance. The independent readiness audit passed with no errors, including
all frozen inputs, opening provenance and saved-game replay. Its input map
contains 2,805 recorded file identities.

The host reports 18 logical CPUs and 64 GiB memory; the planned four-worker/
6 GiB reservation fits the normal daytime and nighttime budgets. These are
admission estimates, not hard operating-system utilization caps. Quiet-host
conditions are not required for this search-free check, and its runtime is not
a performance result. LM Studio can remain active during preparation.

All **1,955 protected existing files** and the README introduction remain
byte-identical, including historical tools/evidence, engine/frozen sources,
normal binaries, stable GUI `0.1-dev-4b8b35d` and owner batch settings. Only new
preparation assets and practical/current documentation were changed. No release,
default promotion, game, rebuild, long benchmark or schedule was created.

## Evidence and next checkpoint

Local evidence: `results/phase4f10-preparation-20261028/`, including initial
state, generation/test logs, frozen configuration, readiness JSON/stderr,
independent readiness audit, protection verification and validation index.

- Readiness SHA-256:
  `6b6eb20cdb8dcdf044d9af992bdb9d6b4ef0ec9eedbffe48d14db1d5c832c56e`.
- Independent audit SHA-256:
  `2191a3372a24107219aabdbc17693567a5578a08651dd7024e0b5ef9e8660b3f`.

After the local preparation commit, agree a separate **6–8-hour quiet window**.
Keep AC power and Automatic mode, pause competing inference/heavy work, and
keep the laptop awake throughout. Suspend/resume is unsupported: an excessive
monitoring gap invalidates completion and preserves partial evidence without
resuming or retrying. The launcher accepts starts only 23:00–23:30 Helsinki and
stops at the next 07:00. A daytime attempt needs its own explicit authorization
and a documented/tested timing amendment; puzzle permission does not transfer.

One fixed attempt only, with all 512 games / 256 pairs included in an independent
audit. Any time forfeit by either role blocks eligibility for default review.
The conditional pair-level interval requires at least 299.5/512 candidate points
for eligibility, at most 212.5 for negative evidence; other valid scores are
inconclusive. These assumptions and limits do not qualify eight-thread play,
other opponents/time controls, absolute Elo or universal nonregression. Keep
defaults unchanged until a separate review. See the
[tool guide](../TOOLS.md#check-the-frozen-continuation-history-match) for commands.
The owner handles GitHub pushes manually.
