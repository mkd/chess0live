# Phase 4D.2 — current-engine LMR preparation and launch

## Scope

The owner authorized the next phase after pushing Phase 4D.1. The
[fixed protocol](../PHASE_4D2.md) is one 1,024-game current-engine LMR comparison:
512 reversed-color pairs, eight active single-worker searches, sixteen resident
engines, 60+0.6 clocks, 64 MiB hash, classic timing and 20 ms overhead. Countermove,
SEE ordering, pondering, diagnostics and tablebases are disabled in both roles.
The only search-policy difference is LMR on/off. No engine source or default changed.

This campaign is separate from the still-unstarted frozen Phase 3L campaign.
Historical results are disclosed, not pooled. A good score cannot override a
candidate clock forfeit, incomplete evidence, or a failed audit. No match result,
rating, release, or default promotion is claimed by preparation.

## Frozen identity

Source revision: `74a908bb861e8292cdbb10d005410e4364efea5e`.
The executable was copied byte-for-byte from the already tested Phase 4D.1
release, not rebuilt or tuned for the new openings. Native macOS ARM64 execution
only; previous four-build-mode validation is recorded in the
[countermove report](2026-10-18-phase4d-countermove.md).

| Artifact | SHA-256 |
| --- | --- |
| `build/experiments/phase4d2-20261018/chess0live` | `bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f` |
| Build `manifest.json` | `918298becbfbcd62148759ea050726bd29070dbad9db66cc22bb8fc91965918c` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Exclusion catalog | `94d17056e1b86ebeb4c8e9801c551df9edd8ee8a33cec4ac74a1db39a8de50ee` |
| Generation metadata | `dae2e9dc2cfbe69b21fd4475caf7c9272bf9cbb038ee26e33e8749859680f367` |

The launcher and independent auditor each pin all eight opening suite hashes.
Every campaign snapshot also records tool/test/protocol source hashes. Do not
edit those sources while the campaign runs. Normal development binaries and the
owner's GUI bundles are separate from the frozen match executable.

## Preparation evidence

- 512 unique legal roots, 256 per side to move; eight shards of 64 roots, each
  balanced 32/32. Full move histories retain draw state.
- 64 original stems and eight legal continuations each. The 1,265-root exclusion
  catalog retains prior exposure/provenance and 28 direct source fingerprints.
  All 23 opening checks, public byte reproduction and source-digest checks passed.
- Related stems/shared host remain explicit statistical limitations. A conditional
  pair-level interval is not proof of independence or universal strength gain.
- All 59 launcher/auditor tests passed in 122.945 s, including synthetic
  1,024-game corruption checks, raw 128-game PGN/UCI/clock replay, deadline,
  cancellation, resource and drift failures. Together with the 23 opening and
  eight load-checker tests, this is 90 passing workflow checks.
- Native search, selective-policy and time-management checks passed again.
- A single exposed-position load check at 23:08:35 Helsinki completed in 2.769 s:
  16 resident engines, eight actual overlapping searches per wave, 24 timed
  replies on time, eight stops and successful reuse. Minimum clock slack was
  161.028 ms; maximum stop response 2.360 ms. All 162 PV lines/610 plies replayed
  legally; no stderr; all 16 processes closed. Eight checker tests passed.
- Readiness at 23:09:34 Helsinki checked both roles serially, sent no held-out
  searches, and passed the independent audit. Resource admission reserved
  9,525,941,184 bytes (8.87 GiB), eight workers against the nighttime allowance of
  fourteen on this 18-logical-CPU, 64-GiB host. Reservation is not a hard OS cap.
- All 27 protected historical source/assets, including the three owner-facing
  GUI bundles, remain byte-identical. The README introduction is unchanged.

The short load check does not prove long-run reliability. The full raw audit
remains mandatory after completion. All workflow tests and independent readiness
have passed; no held-out game has run as of this preparation record.

Raw preparation evidence is under `results/phase4d2-20261018/`, including
`load-check.json`, `load-protocol/`, `preflight.json` and `preflight-audit.json`.
These large local artifacts are ignored by Git. Readiness currently reports
`checked=true`, no errors, and zero held-out searches.

## Next checkpoint

After all workflow tests and the local commit, launch once in the declared
23:00–23:30 window, with a fixed next-07:00 cutoff. Do not extend or resume an
unfinished sample. Historical throughput suggests roughly 6–7 hours, but eight
concurrent workers and long games can exceed that estimate.

One complete audited result decides whether this single-thread blitz evidence
qualifies LMR for a separate default review. Otherwise keep it off and continue
to Phase 4D.3 verified null-move pruning. External opponents, longer controls,
parallel strength and broader platform execution remain separate work.
