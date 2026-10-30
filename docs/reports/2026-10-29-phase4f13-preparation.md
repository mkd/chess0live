# Phase 4F.13 NNUE game qualification preparation — October 29–30, 2026

## Decision and scope

Prepare one prospective comparison of the exact Phase 4F.12 baseline and
optimized NNUE candidate. Phase 4F.11 measured about 5% faster equal-work
execution on its finite sample; Phase 4F.12 subsequently found the same three
positive-mate reports and identical final moves on all 39 positions. Neither
result establishes a playing-strength gain. This preparation starts no full
match, rebuilds no engine and changes no search setting.

The [protocol](../experiments/phase4f13-match.md) fixes **2,048 games / 1,024
color-reversed pairs at 15+0.15**, Threads=1, Hash=64 MiB, four active games,
eight resident engines and at least 6 GiB reserved memory. Existing candidate
`3ee5eff` and baseline `1ca87d6` binaries retain their exact hashes, both complete
build histories and all 48 archived sources. LMR remains on; TT hints,
Continuation History and the other experimental pruning/ordering settings remain off.

An authorized attempt first runs eight exposed development games at the same
clock/options/concurrency. The independent raw audit and process cleanup must
pass with zero forfeits before held-out play starts. This gate has a 600-second
limit, provides no strength inference, and never contributes to the 1,024 pairs.

## Design and sensitivity

The original 64 project-authored 16-ply stems supply sixteen fresh legal tails
each, with full histories retained. The new deterministic SHA-256 sampler uses
four new seeds and a separate domain; it consults no engine evaluation or result.
All **1,024 unique roots** were accepted on their first generation attempt:
512 with White to move and 512 with Black, ending after 19 or 20 plies. Each
256-root shard has 128 per side and family counts 96 e4, 96 d4, 32 c4, 32 Nf3.

Exclusion replay covers **185 recorded sources**, **2,976 public roots**,
**311,141 saved-game roots** and **312,204 combined unique prior roots**, including
the completed Phase 4F.7/4F.10 games. No accepted root overlaps that record.
Shared stems, unsaved games, internal search/PV nodes and dynamically constructed
fixtures remain limitations; disjoint final roots do not establish independent
or representative samples. Smoke uses existing development-01/05/08/09 histories.

The prospective decision uses a fixed four-stake mixture on normalized pair
scores, with threshold 40 per tail, giving a conditional two-sided 95% interval.
The old Hoeffding implementation and all earlier verdicts remain untouched.
Only a complete independently audited zero-forfeit sample permits inference.
The protocol states the common-conditional-mean or fixed-endpoint independence
assumptions and their limitations. Relative Elo is a score transform for this
opponent and control, not an absolute rating.

A reproducible synthetic planning model uses a symmetrized historical pair
histogram and 5,000 trials per hypothetical effect, seed `20261029413`. The
script, output and final-module validation are preserved as
`statistics-planning.py`, `statistics-planning.json` and
`statistics-planning-validation.json` in the preparation evidence directory. Detection rates are
**6.14% at +5, 51.3% at +10, 94.9% at +15 and 99.96% at +20 relative Elo**.
These are conditional planning figures, not forecasts of NNUE's effect. This
is a practical +15-Elo-scale screen with poor sensitivity to +5 and limited
sensitivity to +10. A genuine small improvement can still yield an inconclusive result.

## Validation and preserved evidence

Preparation evidence is retained under
`results/phase4f13-preparation-20261029/`. The opening and statistical suites each
passed 17 tests. The first launcher synthetic fixture encountered a terminal
random line while creating its enlarged test corpus; the fixture now rejects
terminal/short lines and the original failure summary remains recorded.
This was a test-fixture error, with no real chess search or campaign involved.
A later smoke test incorrectly assumed numeric startup order among concurrent
workers; it now checks the exact four-worker membership and that all smoke
workers precede any held-out worker. Its failure log is also retained.

Review added the real short-clock gate, restored a transitive auditor dependency
to the freeze inventory, and anchored existing build-manifest hashes independently
of new pins. It also identified and fixed a timing defect: the smoke timeout
previously began after initial persistence. Both wall and monotonic deadlines
now start before that write and are checked before admission; delayed-write and
clock-boundary tests cover the failure. A separate bounded audit worker keeps
resource monitoring responsive after all smoke engines have exited.

The first full smoke-enabled auditor suite exposed two stale synthetic fixtures:
a main-match resource-gap mutation now touched the smoke prefix, and a cancelled
main-shard mock also replaced the earlier smoke report. Both fixtures were
corrected to target their intended stages without relaxing the audit. The failed
70-test log is preserved. Missing/malformed parent smoke evidence now produces
a failed audit report instead of an exception while formatting its diagnostics.

Final checks passed **161 tests**: 56 launcher, 71 independent auditor, 17
opening-generation and 17 statistical tests. Full synthetic evidence includes
2,048 qualification records, raw 512-game PGN/UCI/clock replay, the eight-game
smoke gate, damaged/missing evidence, resources, cancellation and clock deadlines.
The final logs are `launcher-smoke-tests-final.log`,
`auditor-smoke-tests-20261030T053603Z.log`, `openings-tests-1.log` and
`paired-betting-tests.log`; original-source replay is in `openings-source-replay.log`.

The freeze records **92 pinned inputs / 93 source records** including the pin
file, plus 11 runtime assets. Existing Phase 4F.12 pins independently anchor both
binaries, manifests and copied build evidence. All 370 initially protected files
and the README introduction remain unchanged; among 428 initially tracked files,
only README, changelog, roadmap, handover and validation were updated. A local
receipt script initially looked up role bundles under the wrong protection keys;
it failed before writing pins, then passed using the preserved prior pin aliases.
Its failure receipt is retained. No asset was rebuilt or silently reauthorized.

Actual search-free readiness ran October 30 **07:39:36–07:39:39 Helsinki** and
exited zero. Candidate PID 7260 and baseline PID 7261 each completed a 32-event
transcript with zero search commands and a zero exit. A separate OS check found
neither PID present. The 244-byte stderr log retains two Python referee warnings
about valid `info string Syzygy largest 0 pieces; table files are external`
messages during setup; the independent raw audit accepted these messages and
reported no errors. No Syzygy table data or probing was enabled.

The fresh external `readiness-audit.json` passed, checking 93 sources, 11 assets,
1,024 qualification roots, four development roots and the four-worker/eight-engine
6 GiB resource plan. Its input digest record contains 3,322 paths including prior
PGN exposure evidence. Audit SHA-256:
`7b7a6238191110b267cc6e35230d851e292a5275190a12164c23b3bbf013a0ec`.
Pin-file SHA-256:
`4edf205b0ead0d4e2857d7e4a02dc3366c207c832f67545dd936fdcaaf0b2786`.

**No short-clock smoke or full game has run during preparation.** The actual
operational gate remains required at the next authorized launch. Synthetic
tests and search-free readiness do not establish overnight timing reliability;
LM Studio inference can remain available until that newly confirmed window.

## Operating boundary and next checkpoint

Allow **6–8 hours plus up to ten minutes for the smoke gate**. The duration
estimate scales the previous four-worker 512-game 60+0.6 campaign's 6h10m50s;
startup overhead, different games and host conditions make it uncertain.
Completion before cutoff is not guaranteed. Historical higher-concurrency
forfeits remain unresolved, so concurrency stays at four active games.

Full play requires a fresh quiet window with LM Studio inference and competing
builds paused, AC/Automatic power, and an awake host. Admission is 23:00–23:30
Europe/Helsinki with the original next-07:00 cutoff throughout both stages.
Sleep/resume, source drift, resource gaps or failures invalidate qualification.
No daytime exception, schedule, retry, resume, sample extension, automatic
promotion or GitHub push is part of this preparation. Preserve all terminal
outcomes and verify process cleanup before releasing the host.
