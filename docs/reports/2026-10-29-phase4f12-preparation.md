# Phase 4F.12 — NNUE tactical comparison preparation

Date: October 29, 2026. Preparation starts from `3ee5eff`.
Decision: readiness and smoke pass; the full equal-time comparison is prepared,
not started or scheduled. No engine/default change or strength claim.

## Fixed comparison

The [protocol](../experiments/phase4f12.md) compares the original NNUE evaluator
with the accepted Phase 4F.11 affected-feature implementation on all 39 owner
positions. Each role gets 60 seconds, eight threads, 64 MiB Hash and identical
current settings. LMR is on; TT Move Hints, Continuation History and other
experimental policies are off. Tablebases are disabled. Each role/position
starts a fresh process; role order alternates by position. One resident engine
and eight active workers reserve at least 2 GiB, within the observed daytime
admission of nine workers on this 18-CPU / 64-GiB host.

Both previously tested binaries were copied without rebuilding into
`build/experiments/phase4f12/{baseline,candidate}/chess0live`:

- Baseline source `1ca87d6`, binary SHA-256
  `8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc`.
- Candidate source `3ee5eff`, binary SHA-256
  `04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594`.

Each role has 24 archived source/test/build-input files, verified against its
original Phase 4F.11 manifest and exact Git revision. Original manifests and
build logs are copied alongside them. Compiler flags match. The 78 frozen
inputs include both binaries, complete provenance, pinned network, unchanged
corpus, owner source, new protocol/tools/tests and transitive dependencies.

## Implementation and validation

The versioned runner and independent auditor adapt the project's Phase 4F.9
workflow without editing its frozen sources. Both sample metadata and raw
process-start records bind the role to its executable path and SHA-256. The
auditor imports no campaign parser, validator or summary; it reconstructs raw
commands, options, legality, clocks, resource checks, exits and both source maps.

All **87 synthetic checks pass**: 46 runner and 41 auditor checks. Cases include
swapped/same binaries, incorrect raw role identities, unequal options, omitted
source provenance, path escapes, missing/extra sessions, malformed analysis,
illegal PV/best/ponder, failed teardown, clock discontinuity, resource limits,
cutoff, quiet-host/daytime assertions and existing-output refusal. Audits must
be written outside the attempt directory to a fresh path.

The first auditor fixture run failed because macOS temporary paths used `/var`
instead of canonical `/private/var`; the fixture was corrected. Failed and
passing logs are retained. There were no actual engine-readiness or smoke
failures. No engine rebuild or repeated native suite was needed for this
tool-only preparation.

Readiness passed in two real sessions with no position/search commands: exact
21-option handshake, 50 commands, four readiness barriers, two EOFs and clean
exits. Independent audit verified all 78 inputs and both role assignments.

The smoke ran **10:28:29–10:29:54 Helsinki**, about 86 seconds, completing all
**78 one-second searches / 39 pairs**. Its independent audit passed:

- 78 zero exits and completed readers; 234 readiness barriers.
- 525 analysis iterations, 3,380 legal PV plies and 156 best/ponder plies.
- 313 resource observations; maximum observed gap 0.771 seconds and clock drift
  0.000586 seconds, within the declared limits.
- All 39 final moves matched; neither role reported a mate. Scores and completed
  depths matched on 36 positions. All three differences remain below.

| Position | Baseline score / depth | Candidate score / depth |
| --- | --- | --- |
| 12 | +1239 cp / 7 | +1128 cp / 6 |
| 23 | +1211 cp / 6 | +1355 cp / 7 |
| 38 | +489 cp / 11 | +373 cp / 10 |

These short, nondeterministic SMP observations validate operation only. They
cannot establish an improvement, regression, repeatability, forced mate or
playing strength. The exposed corpus has supplied mate-distance labels but no
expected-best-move labels; move accuracy is unavailable. Full tactical and
separate game qualification remain pending.

## Preservation and evidence

Local receipts and logs are in `results/phase4f12-preparation-20261029/`, including
`initial-preservation-receipt.json`, `provenance-preservation-audit.json`, readiness
and smoke directories, their external audit JSONs and synthetic test logs.
Readiness audit SHA-256:
`8f0c45eb9d0614cfc40b4d4e6702f77163c35cfa7b100b97e3423bdb07974e14`.
Smoke audit SHA-256:
`60e202929587325afd8780d1d65a2408dc9120cdb787a7457bab00bbb92a8c0e`.

The 69 current protected files, 69 earlier frozen tracked files, three Phase
4F.11 documents and 117 Phase 4F.11 evidence files remain unchanged. README
introduction and owner batch settings are preserved, including stable GUI
`0.1-dev-4b8b35d`. At entry, the normal release already differed from the prior
checkpoint: current SHA-256
`b2db6cf80b2db188192fed65b42e16acbc8af4ade5edd2f4cc36f1baf953e37c`,
versus historical `6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f`.
Its cause/provenance is unknown; the current file was preserved untouched and
was not used as either experimental role. Earlier pins were not rewritten.

A separate OS check after smoke found no remaining comparison engines, runner
or sleep inhibitor. LM Studio inference may resume until a full run is agreed.

## Next checkpoint

Commit tested preparation, then agree the full approximately 78-minute quiet
window. It needs paused inference, AC/Automatic power and an awake Mac; long
tests normally run overnight. A daytime run requires an explicit exception for
this comparison. Earlier short-comparison permission is insufficient. No
schedule or launch was created. Audit the complete attempt before considering
game-based qualification, and report every tactical loss as well as gain.
