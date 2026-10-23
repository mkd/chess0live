# Conservative LMR default integration — October 23, 2026

## Scope and decision

This checkpoint integrates the existing conservative one-ply LMR policy after
its [fresh 512-game qualification](2026-10-23-lmr-results.md). It changes only
the public API default, the UCI option default and the advertised UCI value.
Search rules, reductions, evaluation, timing, cache layout and worker algorithms
are unchanged. Explicit `Late Move Reductions=false` remains available.

**Decision: retain conservative LMR as the default.** All bounded integration
checks passed. Other experimental policies remain disabled; reductions were
not widened or retuned.

The owner requested that remaining edits be committed. The seven puzzle-runner
checks passed, and the existing local configuration was committed unchanged as
`dac8a19` before implementation. Its eight-thread manual setting is not the
resource setting used by these automated checks.

## Deterministic equivalence

`tests/lmr_default_test.py` performs 23 serial, one-thread searches with Hash 64
and the pinned network, using four already exposed development roots at depths
5/6. It does not consume or tune on qualification openings. Native, forced
scalar and address/undefined-behavior sanitizer builds all passed 15 comparisons:

- New default-on equals the frozen parent's explicit-on behavior.
- New explicit-on equals new default-on.
- New explicit-off equals the parent's default-off behavior.
- On→off→on transitions restore cold-policy behavior without a manual hash clear
  between switches; actual search cache/history invalidation remains effective.

Each comparison includes every iteration's depth, selective depth, score, nodes
and legal PV; final bestmove/ponder; and LMR, capture-ordering and cache counters.
Timing and NPS are excluded. This is cold-search and policy-transition parity,
not a same-policy warm-cache benchmark. A separate direct C++ API test exercises
an untouched `SearchLimits` default rather than relying on UCI configuration.

All four default-on roots activated LMR: 9,900 reductions in total. In this small
fixed-depth sample, nodes fell from 476,531 to 285,958 (39.99%) versus off, with
matching final moves, scores and PVs. This is diagnostic work reduction, not a
new strength estimate or a promise for other positions.

## Regression checks

All checks passed on macOS ARM64:

| Build | Executed checks | Result |
| --- | --- | --- |
| Native release | Core UCI/perft/state, search, policy, timing, exchange, isolated null/reverse-futility/quiescence-SEE, SMP | Passed |
| Forced scalar release | Same suites | Passed |
| ASan + UBSan | Same suites | Passed; no sanitizer findings |
| ThreadSanitizer | Search and SMP | Passed; no race findings |

The 43-case SMP lifecycle suite passed in all four builds. The seven
puzzle-runner checks also passed before the owner's configuration commit.
Exact commands and elapsed times are in `test-summary.json`; full output is
preserved in `tests-*.log`.
Baseline tests explicitly disable LMR where needed to keep off/on experiments
independent. The SMP suite checks default-on diagnostics through cancellation,
node/time limits, ponderhit, worker reconfiguration and shutdown. It does not
require identical multithreaded trees or establish SMP playing strength.

## Reproduction and preserved assets

Parent: `build/experiments/lmr-20261022/chess0live`, SHA-256
`eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
Native candidate: `build/macos-arm64-generic-release/chess0live`, SHA-256
`4f51466335c5021ace971da8ed12548f884a9c1299484a8e2b3f39858a24b28c`.
Network: `nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
A byte-identical native snapshot and manifest are retained at
`build/experiments/lmr-default-20261023/` for the next phase. Raw parity reports
record scalar/sanitizer executable and helper/input hashes.

```sh
python3 tests/lmr_default_test.py \
  build/experiments/lmr-20261022/chess0live \
  build/macos-arm64-generic-release/chess0live
```

The pinned parent is an ignored local artifact, not supplied by a fresh clone.
Build logs, parity reports and regression logs are in
`results/lmr-default-20261023/`. The README introduction, owner puzzle settings,
pinned network, historical evidence and stable GUI bundles
`0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017` and `0.1-dev-phase4b-20261018`
passed all 60 file checks plus the exact README-introduction check. The ordinary
build intentionally changed; frozen GUI and qualification binaries did not.

For current GUI testing select the rebuilt ordinary executable. A saved Cute
Chess option may override the new default with `false`; explicitly select
`Late Move Reductions=true`. Old frozen bundles intentionally keep old behavior.
Older benchmark tools that inherit defaults now measure LMR-on: record options
and binary identity rather than treating results as identical-policy comparisons
with historical runs.

## Next checkpoint

This integration is complete. Next is **Phase 4D.6**, one isolated broader
quiet-move reduction/pruning hypothesis with tactical, pawn-breakthrough and
zugzwang guards. Keep the accepted conservative LMR policy as its baseline.
ProbCut remains 4D.7; other opt-in experiments remain off. No new match or schedule
is started here. The 512-game result is conditional one-thread 60+0.6 evidence;
this integration adds no absolute rating, SMP strength or foreign-platform claim.
The full 39 × 60-second puzzle comparison and NNUE oracle corpus were not rerun
for this default-only wiring change. They retain their earlier evidence scope;
the next material search-policy candidate requires its matched puzzle checkpoint.
