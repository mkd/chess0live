# Phase 4D.4: conservative reverse futility — October 19, 2026

Implementation commit: `9ad2fe9`, based on `ddea518`. The implementation and its
bounded development checkpoint are complete. **Keep `Reverse Futility
Pruning=false`.** The six-root sample reduces aggregate fixed-depth work, but
reused-cache timing is mixed and there is no playing-strength qualification.
No margin was changed after measurement. Advance implementation to 4D.5 rather
than repeatedly tuning this sample.

## Implemented boundary

The independently written candidate applies only to ordinary interior non-PV
nodes at depth 1–3. Fresh NNUE evaluation must exceed beta by 200, 350 or 500
internal score units, respectively; these are not normalized UCI centipawns.
The [frozen protocol](../experiments/phase4d4-reverse-futility.md) specifies all
guards: no check, speculative null subtree, repeated current position, high
halfmove clock, advanced pawn, legal capture/promotion, sparse material,
single legal move, or special mate/tablebase window. Earlier terminal/draw
handling retains precedence.

An accepted cutoff returns beta, clears local PV length and makes no chess
move. It does not directly store an original-depth TT bound; ancestors can
still cache results influenced by the heuristic. Static evaluation may update
worker-local NNUE accumulator caches normally. Policy changes clear reusable
bounds and learning. Diagnostic evaluations/cutoffs aggregate after joins.
Quiet defenses, quiet checks, distant threats and unrepresented zugzwangs
remain risks. These restrictions cannot promise no strength loss.

## Executed checks

All checks ran locally on macOS ARM64 in C++26 mode. Logs are preserved under
`results/phase4d4-20261019/`.

| Check | Result / raw log |
| --- | --- |
| `make -j1 test` | Passed; `full-native.log` |
| `make -j1 SIMD=scalar test` | Passed; `full-scalar.log` |
| `make -j1 MODE=sanitize test` | ASan/UBSan passed; `full-sanitize.log` |
| New direct API and UCI suites, native/scalar/ASan+UBSan | Passed; `rfp-native.log`, `rfp-scalar.log`, `rfp-sanitize.log` |
| TSan search, new API/UCI suites, existing SMP suite | Passed; `rfp-thread-sanitize.log` |
| New profiler / historical null-profiler unit checks | 26 / 19 passed; `profile-tool-tests.log`, `historical-profile-tool-tests.log` |

The new UCI suite passed **78 bounded cases per build**, with independent
`chess==1.11.2` legal-move/PV replay and up to four search workers. Direct API
checks cover positive activation, policy on/off reuse, diagnostics, root
evaluation restoration, terminal/draw rules, stop/expiry/node limits, joined
accounting and bounded composition with null pruning and LMR. The deterministic
activation case observed 1,406 eligible evaluations and 136 cutoffs in each
build. Pure policy checks exercise eligibility, exact margin and score-band
edges, and widened integer arithmetic.

The 40-case UCI regression set reuses this project's original null-move cases
and their color mirrors. Passing legal outcomes does not establish optimal
play. Whole-tree zero-cutoff assertions apply only where sparse/terminal guards
guarantee exclusion; a checked root can have eligible descendants. Full
null-subtree exclusion is covered by policy checks and source inspection;
composition tests do not observe every internal node mode.

The TSan run also passed the existing 43-case SMP suite with no reported race.
Its activation-only harness allowance is 180 seconds, versus 30 normally;
search clocks and cancellation allowances are unchanged. Native existing null
interruption checks and six Syzygy search scenarios with one/four workers
passed against 72 verified fixture files. This is not a new RFP-enabled
tablebase oracle qualification or a complete SF19 NNUE stage-oracle rerun.
No new GUI visual, foreign-target execution, or 64-worker claim follows.

## One frozen development measurement

All other managed engine tests/builds and campaigns had finished. The profile
used one active worker at a time, below the daytime 50% resource ceiling.
`--quiet-host` records an operator declaration, not measured OS utilization.
No long match or automatic schedule was started.

The predeclared 60-search sequence completed at **08:27:58 Helsinki**, with
47.716 seconds of setup/search/cleanup inside its 900-second budget. It used
six exposed roots, Threads 1, Hash 64, classic timing, 20 ms overhead and all
other experiments/tablebases off. Each depth-stage process ran a fresh search
then an immediate cache-preserving repeat. The final 500-ms stage used fresh
processes. There was one repetition per cell, no discarded warmup and no
replacement search.

The 24 parent/off searches matched every declared signature in all 12 pairs,
including nodes, hash occupancy, per-depth score/PV, final move and ponder.
Observed parent/off elapsed totals were 8.020/7.949 seconds fresh and
2.341/2.256 seconds reused. These single-repetition timings do not qualify a
default speed change.

| Depth-6 state | Off nodes | On nodes | Node change | Off elapsed | On elapsed | Elapsed change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fresh cache | 1,922,478 | 1,677,937 | −12.72% | 7.00884 s | 6.20229 s | −11.51% |
| Reused cache | 630,684 | 621,031 | −1.53% | 2.03124 s | 2.07746 s | +2.28% |

Per-root depth-6 nodes retain the variability hidden by those totals:

| Root ID | Fresh off → on | Reused off → on |
| --- | ---: | ---: |
| opening-01 | 57,487 → 52,162 | 5,302 → 5,144 |
| opening-02 | 352,925 → 314,000 | 328,178 → 348,808 |
| opening-03 | 269,238 → 269,232 | 18,628 → 18,628 |
| gamephases-mg-01 | 147,435 → 124,745 | 22,865 → 23,956 |
| gamephases-mg-03 | 1,016,071 → 867,525 | 219,249 → 195,999 |
| gamephases-eg-06 | 79,322 → 50,273 | 36,462 → 28,496 |

All 12 fixed-depth off/on pairs retained the final move, ponder and score;
there were no common-depth score/PV changes. Fresh `gamephases-mg-03` seldepth
changed from 19 to 18; all other final fixed-depth seldepths matched.

At equal requested time, completed depths were off/on **6/6, 5/5, 5/5, 5/5,
4/4, 6/7** in the listed root order. Every final move/ponder matched. The last
root's final score changed from +355 to +371 cp because the candidate finished
depth 7; common-depth scores/PVs still matched. Total nodes were 835,775 versus
806,220, including 500,399 versus 448,107 nodes in unfinished iterations. Each
search's observed interval was about 480 ms because the 20-ms overhead applies
to `go movetime 500`. The deeper endgame result is a diagnostic observation,
not proof of a better move or stronger play.

An independently authored parser audited all **60 searches, 36 clean process
sessions, 351 iterations, 1,553 PV plies and 120 bestmove/ponder plies**. It
recomputed summaries and checked 17 profile assets, 23 candidate source pins,
29 protected pins, frozen campaign inputs and 61 resource admissions. No
engine was rerun by the auditor. All preserved GUI bundles, the owner's README
introduction, frozen Phase 3L assets and completed Phase 4D.2 evidence matched.

## Artifacts and continuation

Raw results: `results/phase4d4-20261019/profile.json`,
`independent-audit.json`, complete transcripts and check logs. Frozen parent,
candidate, source manifest and protected pins:
`build/experiments/phase4d4-20261019/`. The normal native executable is
`build/macos-arm64-generic-release/chess0live`; existing GUI snapshots are intact.

| Artifact | SHA-256 |
| --- | --- |
| Parent executable | `d0617575e7ece0dc3c38d4f44f33b6bc93adad8cf947a129af6dec137246b530` |
| Candidate / normal executable | `361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Frozen source manifest | `d812fd9af9acb95c20ecabdec9b29d553c57f6e8106f8b85914d610fd29cd31c` |
| Profile | `66983cda34d54e76824105a607112c0e1b01027132f188e0e52f563d1e41c9ff` |
| Independent audit | `aea46b03eee2d915397d91852022b9c4be23763d071741515b998ac8eeace8c0` |

The separate [read-only flagfall diagnosis](2026-10-19-clock-diagnosis.md)
examined all 84 historical failed searches without changing engine timing or
the match runner. End-to-end charged time often exceeds the engine-reported
interval, but saved timestamps cannot locate the cause. Before any new
qualification, run one short, predeclared instrumented clock diagnostic.
Do not reinterpret or extend the failed LMR qualification.

Next implementation is **4D.5: quiescence work reduction**, beginning with one
isolated SEE capture-pruning hypothesis; delta pruning remains separate.
No pruning default is promoted, no release is declared and no strength rating
is established here. Further qualification needs operational reliability and a
new frozen playing-strength protocol. Manual Cute Chess testing is optional;
the owner handles publishing these local commits.
