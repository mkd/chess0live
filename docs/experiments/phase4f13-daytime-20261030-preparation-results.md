# Phase 4F.13 dated launch amendment preparation — October 30, 2026

The [dated timing amendment](phase4f13-match-daytime-20261030.md) is prepared
following the owner's confirmation that LM Studio inference is paused and the
request to proceed. Final suites pass **65 launcher tests and 75 independent
auditor tests**, including a correction to a first-game admission gap found in
independent review. The final dated inventory is frozen. Fresh search-free
readiness and its independent audit passed against the final inventory; no smoke
or qualification game has started at this checkpoint.

## Scope and preserved experiment

Explicit `--allow-daytime` admission is limited to October 30, **14:00 inclusive
to 22:45 exclusive Europe/Helsinki**, with a fixed October 31, **07:00 Helsinki**
cutoff (`2026-10-31T05:00:00Z`). Readiness, smoke and full-child admission all
check this policy. Ordinary 23:00–23:30 launch behavior is unchanged without the
flag. No recurring schedule or retry is authorized.

The [base protocol](phase4f13-match.md) remains unchanged: 2,048 qualification
games/1,024 pairs, 15+0.15, the same two frozen binaries, network, seeds, original
opening histories and options. Four active searches and eight resident engines
reserve at least 6 GiB within ordinary 50% daytime/80% nighttime limits. The
eight-game exposed smoke gate still needs complete raw auditing and cleanup
within 600 seconds before any held-out game, and contributes no strength data.
The statistical interval and its conditional assumptions remain fixed.

## Preservation and evidence

Evidence directory: `results/phase4f13-daytime-20261030-preparation/`.

- `original-70a5f2d/` archives all 96 distinct original source/runtime inputs
  before the launcher, independent auditors and their tests were amended.
- `preservation-before-amendment.json` records the archive and 401 protected
  paths. The completed `source-freeze-final.json` verifies all 96 archived originals,
  both match binaries and 400 protected paths against their original digests;
  the separate normal-release discrepancy is disclosed below.
- The original `tests/data/phase4f13-match-pins.json` remains unchanged. The
  separate `tests/data/phase4f13-match-daytime-20261030-pins.json` inventory has
  **95 source records, 94 pinned inputs and 11 runtime assets**. The original
  pin and dated amendment are pinned inputs; the new pin excludes only itself
  from its input digest map and remains part of source snapshots.
  First dated pin SHA-256, superseded by the boundary review below and preserved
  as `pins-attempt1-before-boundary-review.json`:
  `5dfdac46336a27c161df4c071570a628bab9ad9e44b490a310ca82b8c7b9fe6c`.
  Final dated pin SHA-256:
  `dba5fecdc37983f81f75bd89d9be7d7281b90e270d50fcfec6512089c955d0bb`.
- `launcher-tests-01.log` retains the first passing 63-test run. After extending
  the full-child boundary fixture, `launcher-tests-02.log` records the initial
  **63/63 pass in 44.235 seconds**.
- `launcher-boundary-before-fix.log` retains eight reproduced admission failures.
  `launcher-boundary-final-focused.log` records two passing tests covering 16
  boundary cases plus continued admitted play, in **14.547 seconds**.
  `launcher-boundary-full.log` records the final **65/65 pass in 57.195 seconds**.
- `auditor-dated-targeted.log` records five passing dated-policy checks;
  `auditor-full.log` records **75/75 pass in 132.047 seconds**.

The initial freeze failed before pin creation because
`build/macos-arm64-generic-release/chess0live` differed from the inherited
October 29 preservation digest. `normal-binary-baseline-discrepancy.json` retains:

- Historical SHA-256:
  `b2db6cf80b2db188192fed65b42e16acbc8af4ade5edd2f4cc36f1baf953e37c`.
- Current SHA-256:
  `c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d`.
- October 30 modification/change timestamps of 08:24:16/08:24:24 local, before
  this amendment. The cause is not established; the binary is not a campaign
  input. The completed freeze checks this recorded current digest going forward.

Subsequent independent review found a separate admission issue: awaited child
setup could cross the allowed endpoint after the last policy check but before
its first game. Eight reproduced failures demonstrate this gap before the fix.
The launcher now rechecks admission at every smoke/full shard's first game;
later games in an already-admitted shard continue within the original cutoff.
The final tests and replacement dated freeze pass. The first dated pin and its
evidence are retained, with no readiness session or real game started against
that attempt. This review finding was not detected by the initial passing suites.

Do not claim historical preservation of that normal binary. This amendment
did not rebuild or replace it, rebuild a match engine, change defaults, modify
historical campaigns, play a real game or push remotely. The stable GUI
`0.1-dev-4b8b35d` remains intact. The owner handles GitHub pushes.

## Remaining checkpoint and limitations

Fresh readiness passed at 14:58 Helsinki in 2.54 seconds. The independent audit
passed in 13.53 seconds, with no errors, verifying 95 sources/94 pins, 1,024
distinct held-out roots plus four smoke roots, and 3,322 input hashes. Both serial
UCI handshakes exited zero with zero search commands. OS lookup at 15:00 confirmed
PIDs 66243/66244 absent. Receipts: `readiness.json`, `readiness-exit.json`,
`readiness-audit.json`, `readiness-audit-exit.json`, `readiness-os-cleanup.json`.
Audit SHA-256:
`50a9eda8c3f68f9bd244e07ea5a32a22047f432476340a0bcb4efbe5e0429a90`.
The ignored one-shot launch wrapper and read-only progress helper passed 23
synthetic tests. These establish helper behavior, not a successful live run.

Commit the tested amendment locally and launch the authorized attempt once.
Earlier readiness belongs to the original inventory and was not reused as proof
of amended readiness.
Any failure, forfeit, incomplete pair/sample, changed input, clock/resource gap
or cutoff blocks qualification; preserve the evidence and do not retry or resume.

This change establishes no performance, puzzle or strength gain. The fixed
sample's limited sensitivity to small gains, shared opening stems, incomplete
historical exposure record and conditional statistical assumptions remain
limitations. Resource reservations and operator confirmations are not continuous
OS power/load telemetry. Keep the Mac awake on AC with competing heavy work
paused, and verify process cleanup before releasing it for LM Studio inference.
