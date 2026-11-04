# Phase 4F.16: defer sorting after the contextual TT move

Declared November 4, 2026 before measurements. Parent:
`e16ca73ed7837c5e79b1cf388b2a1e231d906f5d`. The owner authorized the next phase
and confirmed LM Studio paused in reply to the AC/Automatic readiness question.

## Hypothesis and invariants

At an ordinary node with an exact legal contextual TT move, freeze all ranking
keys before child search, put that move first, and sort/copy the remaining keys
only if the first child neither cuts off nor aborts. The TT priority is strictly
above all other ranks. Keep the existing comparator, including helper-root ties.
Store pending keys per worker and per ply, separate from eager shared scratch.
Use the completed move prefix unchanged for history learning and LMR indices.
Quiescence, speculative searches, missing/stale/fallback-only hints, singleton
lists and any enabled ProbCut retain eager ordering. No pruning, search-policy
default, NNUE arithmetic, clock policy or public option changes.

This saves sorting at first-child cutoffs but adds retained per-ply storage and
allocation costs. Exact finite search agreement and a bounded timing screen
decide this candidate; neither demonstrates an Elo gain.

## Correctness and preservation

Preserve the current user modification to `tools/batch_positions.py`, README
introduction, stable GUI `build/test-baselines/0.1-dev-4b8b35d/`, normal release,
previous campaign binaries, pins and raw evidence. Keep the unresolved historical
normal-release digest caveat. New builds use `build/experiments/phase4f16/` only.
Archive parent/candidate build sources and hashes. No previous output is replaced.

Use at most two compiler jobs, then one test executable at a time. Direct checks
compare full ordering against the independent eager reference, including flags,
promotions, SEE accounting, continuation scores, helper ties, first-cutoff learning,
child scratch reuse and frozen keys surviving history changes. Run relevant native,
scalar, ASan/UBSan and ThreadSanitizer search tests and bounded SMP lifecycle tests.
Speculative ordering stays eager; existing optional-policy regressions remain valid.

## One fixed timing screen

After correctness and source review, use the existing independently refereed
`tools/profile_search_baseline.py` with all fifteen exposed roots from
`tests/data/countermove-profile.json`. Fixed depth 6, three repetitions, cold and
immediate warm repeat, alternating baseline/candidate order: **180 searches,
90 matched pairs**, no discarded warmups. Threads 1, Hash 64 MiB, pinned network
`nn-1a298aa575a0.nnue`, accepted LMR-on/null-off preset, diagnostics off. Two engines
resident, one searching; no builds or other tests overlap the measurement.

Per-search timeout 15 seconds; search/setup deadline 300 seconds. Existing final
cleanup, hashing and publication occur after that deadline. Check resource
admission between cells, retain partial failure evidence, and never repeat or
extend measured cells to obtain a favorable outcome. Independently replay raw
outputs, frozen assets and all legal PV/best/ponder moves; require exact reported
depth/seldepth/nodes/score/PV/final moves across both builds and repetitions.
Hash occupancy is range-checked but is not part of the harness's exact signature.

Retain the optimization only if correctness passes, the pooled median paired
parent/candidate elapsed ratio is at least **1.01**, and no position/temperature
median is below **0.98**. These engineering screen thresholds are not statistical
significance or strength gates. Report every position/temperature, all failures,
and observed variability; otherwise park this implementation with its evidence.
Do not retune within this phase. No games, automatic schedule or setting promotion.

```sh
python3 tools/run.py --offline tools/profile_search_baseline.py \
  --baseline build/experiments/phase4f16/parent/chess0live \
  --candidate build/experiments/phase4f16/candidate/chess0live \
  --output results/phase4f16-deferred-sort-20261104/default-comparison \
  --preset default --depth 6 --repetitions 3 \
  --search-timeout 15 --total-timeout 300 --quiet-host
```

Confirm recorded process cleanup after the run and immediately release the quiet
window. Record the finite decision in roadmap, handover, validation and a concise
report, validate documentation, and commit locally on main; the owner pushes.
