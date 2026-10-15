# Phase 2C: capture ordering

Status: initial development checks complete; retained as an opt-in experiment,
not an accepted strength improvement. This changes move priority; LMR remains
off and timing remains classic in its comparisons.
It does not prune captures, change their depth, or change the NNUE evaluator.

## Hypothesis and scope

The baseline puts every capture ahead of quiet moves, using most-valuable-victim,
least-valuable-attacker (MVV-LVA) priority. An apparently valuable capture may
lose material after recaptures. Deferring such captures could find useful quiet
cutoffs earlier, but the exchange estimate costs CPU time and can undervalue
sacrifices or tactics on other squares.

`Capture Ordering` is a UCI combo option: `mvv-lva` remains the default, and
`see` selects the experiment. The order is TT move, promotions, nonlosing
captures by MVV-LVA, killers, quiet history moves, and losing captures by MVV-LVA.
The same ordering applies in quiescence, without changing stand-pat or check
evasions. Every move still reaches the existing search unless an ordinary
alpha-beta cutoff has already made further searching unnecessary.

The static exchange estimate uses a private board state and deterministic
least-valuable legal recaptures on one square, with optional stopping. It updates
x-rays, filters self-check and illegal king recaptures, removes an initial en
passant victim from its actual square, and accounts for promotion material.
Hypothetical later promotions choose a queen. This is a material heuristic,
not exact chess minimax: off-square tactics, forced check responses, and choices
among different attackers can make the estimate misleading. It must not become
a pruning rule without a separate proposal and validation.

Each experimental key is computed once per move before sorting. The baseline
path and deterministic square/promotion tie breaks are preserved. Changing
either ordering or reduction policy invalidates cached search state through the
Search API, with automatic clearing charged to the search clock. Prepublished
stop and ponder events must survive that clearing.

Opt-in diagnostics add `info string ordering v1 policy ... see_calls ...
losing_captures ...`. Counters describe ordering work, including work inside an
interrupted iteration; they do not count unique positions or establish strength.
Existing diagnostic schemas remain unchanged.

The implementation is original. Conceptual background:
[Stockfish's move-ordering terminology](https://official-stockfish.github.io/docs/stockfish-wiki/Terminology.html#move-ordering)
and the abstract of Fritz Reul's
[Static Exchange Evaluation with alpha-beta Approach (2010)](https://doi.org/10.3233/ICG-2010-33102),
consulted October 14, 2026. No upstream engine code or fixtures are copied.

## Predeclared checks — October 14, 2026

Parent commit: `4a46a355ed73dc06fe58deed0b4b89cc5fb1d751`.
Baseline: `build/test-baselines/capture-ordering-4a46a35/chess0live`, SHA-256
`b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc`.
The preserved GUI bundle `0.1-dev-4b8b35d` and the earlier forecast/LMR experiment
snapshots remain unchanged. Freeze the new candidate before measurements.

1. Original exchange fixtures and a slow legal-move reference check pins,
   x-rays, king recaptures, en passant, promotions, and caller-state preservation.
   Integration tests cover actual SEE calls and losing-capture classification,
   cache switching, legal PVs, limits, and UCI options/lifecycle.
2. Native, scalar, ASan/UBSan, and profiler tests. Rebuild available foreign
   targets and distinguish cross-build success from runtime validation.
3. Default `mvv-lva` equivalence against the frozen baseline on the existing
   three benchmark roots at depth 5: three measured repetitions and warmups,
   24 searches total. Sampled search signatures must match exactly.
4. Same-binary ordering off/on on all 12 development openings at depth 5,
   two repetitions per mode, alternating order: 48 searches. Record work,
   elapsed time, moves, scores, PVs, and exchange counters. Investigate score
   disagreements; move ordering need not preserve tied moves or search trees.
5. The same 12 roots at 200,000 nodes, one repetition per mode: 24 searches.
   Record completed depth, interrupted work, timing, and decision differences.
6. An eight-game, four-pair operational smoke with seed `20261014`, 6+0.06,
   max 512 played plies, one thread, 64 MiB hash, 20 ms overhead, diagnostics
   and ponder off. Same binary/network, SEE versus MVV-LVA, LMR false and
   classic timing on both sides. Replay all games independently.

Use the pinned network and modest daytime resources. No concurrent compilation
or other engine jobs during timed profiles or games. The profiler's historical
filename remains `tools/profile_lmr.py`; use `--experiment capture-ordering`.
It pins the other experimental option at baseline and preserves raw output,
partial failures, full histories, and before/after artifact hashes.

These are development checks, not a calibrated strength test. A favorable
eight-game result cannot justify default promotion. A candidate with unresolved
correctness defects is rejected; a candidate with plausible but inconclusive
functional/performance evidence may remain opt-in for a separately predeclared
larger match. Record unfavorable results too. Do not tune to the reserved
32-opening time-policy validation suite or combine experimental options here.

## Separate LMR loss investigation

The earlier four losses were replayed with the frozen LMR executable,
not this ordering candidate. Roots are selected from every loss by a recorded
score-drop rule and retain full history. This is post-hoc diagnosis, not held-out
validation. A score collapse between different positions is not proof that
reduced fail-lows caused it. The [completed diagnosis](reports/2026-10-14-lmr-losses.md)
found identical off/on moves at all eight roots and identical scores/PVs at all
40 common-depth comparisons. No LMR-specific miss was demonstrated; no LMR
parameter was changed. This finite result does not vindicate every reduction.

## Frozen candidate and development profiles

Candidate: `build/experiments/capture-ordering-20261014/chess0live`, SHA-256
`7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
Implementation commit: `2e69083`. Engine, Makefile, tool, and test hashes still
match the frozen source snapshot. The manifest contains that snapshot, the premeasurement
plan, tracked diff, and their hashes. Built with Apple Clang 21, C++26,
`CPU=generic MODE=release SIMD=auto` on macOS ARM64. The network SHA-256 is
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`;
development openings SHA-256 is
`5cedc1469a43cb7e36dac9ab50379dd42626f9251409f5ad14f4b59919b5ea47`.
Raw records and snapshots are ignored local artifacts; this plan, results, and
reproduction tools are versioned.

Native, scalar, and ASan/UBSan suites passed. The exchange test covers 28 composed
and color-reflected cases plus 4,117 generated captures/promotions checked against
a slower legal-move reference. Integration tests exercise actual losing captures,
forced capture retention, both cache transitions, interrupted work, diagnostics,
legal PVs, rules, limits, cancellation, and pondering. The extended profiler
passed 20 tests, including isolated policies, invalid/missing diagnostic records,
and partial failures. Position and NNUE implementations are unchanged; their
normal 537-position incremental checks passed in each build mode. The separate
full Stockfish oracle corpus was not rerun for this ordering-only change.

All 24 default-mode samples matched the frozen parent signatures exactly:
per-iteration depth, selective depth, nodes, score, PV, bestmove, and ponder.
The median paired baseline/candidate elapsed ratio was 1.00434 with median
absolute deviation 0.01117. This establishes sampled behavior preservation,
not a default-mode speed improvement.

| Depth 5: 24 searches per mode across 12 roots | MVV-LVA | SEE |
| --- | ---: | ---: |
| Total nodes | 1,686,386 | 1,606,868 |
| Median reported search time | 433.690 ms | 414.077 ms |
| Exchange estimates | 0 | 727,704 |
| Negative exchange estimates | 0 | 344,518 |

All 24 comparisons retained the same final move, score, and PV. Total nodes fell
4.72%, with fewer nodes in 10 roots and more in 2. This is different search work,
not an equal-work throughput measurement; short timings have no significance
interval or strength implication. Both repetitions were deterministic; all
120 common-depth score/PV comparisons agreed. The paired MVV-LVA/SEE reported
elapsed ratio had median 1.03525, median absolute deviation 0.07063, and range
0.85641–1.15432. That variation does not establish a consistent speed improvement.

All 24 node-limited searches stopped at exactly 200,000 nodes. SEE completed
one extra nominal depth on `development-01` (5 to 6), one fewer on
`development-08` (6 to 5), and the same depth on the other 10 roots. All 12 best
moves matched; final scores/PVs matched on the 10 equal-depth roots. The first
changed from +16 to +23 cp with castling in both modes; the second from +11 to
+25 cp with `f1g2` in both. The deeper result is not automatically the better move.
Nodes in interrupted iterations totaled 1,133,653 for MVV-LVA and 1,206,032 for
SEE, out of 2,400,000 per mode. Median reported times were 1,069.635 and
1,054.503 ms. SEE made 1,423,256 estimates, classifying 674,502 as negative.
All 62 common-depth scores/PVs agreed. The paired reported elapsed ratio had
median 1.00538, median absolute deviation 0.01553, and range 0.91214–1.04097;
again, this is observed variability, not a significance interval.

The available Linux ARM64, Linux x86-64, and Windows x86-64 targets also compiled
and linked; file inspection confirmed their architectures. They were not run.
No RISC-V64 or Windows ARM64 runtime/build evidence was added. The owner's
`0.1-dev-4b8b35d` GUI bundle, prior forecast/LMR snapshots, pinned network, and
reserved time-validation suite retain their hashes. Commands and source/hash
checks are recorded in local `results/capture-ordering-20261014/validation.json`.

Evidence: `results/capture-ordering-20261014/default-equivalence.json`,
`depth5.json`, and `nodes200000.json`. All use classic timing with LMR disabled.

## Operational match and decision

The predeclared eight-game smoke scored **2 wins, 4 draws, 2 losses** for SEE.
Four games ended in checkmate, three in threefold repetition, and one in
insufficient material. There were no protocol failures, time forfeits,
truncations, or excluded pairs. Both sides used the same frozen binary/network,
classic timing, LMR disabled, one thread, 64 MiB hash, 20 ms overhead, diagnostics
and ponder off. Capture ordering was the only differing option.
Independent replay verified all 703 legal plies, including 639 searched plies,
actual protocol options, clocks, terminations, and frozen artifacts. The three
repetition draws were valid claims based on a possible next move; the final
boards were not already threefold. This matches the runner's documented draw
claim policy.

The raw match is in `results/capture-ordering-20261014/match-smoke/`. The
independent profile/game audit and companion script are `audit.json` and
`audit.py` in its parent directory. Audit SHA-256:
`69d4a6c57e37799419eff40f642c8c891111207bd98513fac7222eedc84c3bf5`.

Four development pairs at 6+0.06 cannot establish a strength advantage or
statistical equivalence. The equal score and mixed equal-node depth results do
not justify changing the default. No parameter was tuned after seeing these
results, and no favorable subset or repeat was selected.

**Decision:** retain the tested estimator, isolated option, and reproducible
comparison tool as a research checkpoint. `Capture Ordering=mvv-lva` remains
the default. The modest work reduction at matching depth-5 decisions makes
further investigation plausible; it is not a demonstrated Elo gain. Any promotion
requires a separately predeclared larger strength campaign. Keep this candidate
separate from LMR and forecast timing until their individual effects are tested.

The initial Phase 2C experiments are complete. The later [Phase 2D time-policy
screen](reports/2026-10-15-phase2d-time-policy.md) finished inconclusively on
October 15. Search-candidate qualification still needs fresh openings and its own
frozen sample, settings, and acceptance rule; LMR is the next research priority,
with SEE kept separate. Long campaigns require a manually launched overnight
session or an explicit owner exception; no further job or schedule is active.

## Reproducing the checks

Use these frozen paths locally or rebuild the recorded source. Different builds
need not share binary hashes or timings. Output paths must be fresh; install
`requirements-match.txt` for the optional referee first.

```sh
python3 tools/compare_bench.py \
  --baseline build/test-baselines/capture-ordering-4a46a35/chess0live \
  --candidate build/experiments/capture-ordering-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --depth 5 --repeats 3 --search-timeout 10 \
  --output results/ordering-default-repeat.json

python3 tools/profile_lmr.py --experiment capture-ordering \
  --engine build/experiments/capture-ordering-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --position-limit 0 --depth 5 --repeats 2 \
  --output results/ordering-depth5-repeat.json

python3 tools/profile_lmr.py --experiment capture-ordering \
  --engine build/experiments/capture-ordering-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --position-limit 0 --nodes 200000 --repeats 1 \
  --output results/ordering-nodes-repeat.json

python3 tools/match.py \
  --candidate build/experiments/capture-ordering-20261014/chess0live \
  --opponent build/experiments/capture-ordering-20261014/chess0live \
  --candidate-network networks/nn-1a298aa575a0.nnue \
  --opponent-network networks/nn-1a298aa575a0.nnue \
  --candidate-option 'Capture Ordering=see' \
  --opponent-option 'Capture Ordering=mvv-lva' \
  --candidate-option 'Late Move Reductions=false' \
  --opponent-option 'Late Move Reductions=false' \
  --candidate-option 'Time Policy=classic' --opponent-option 'Time Policy=classic' \
  --candidate-revision phase2c-see-7d63b9f99bed \
  --opponent-revision phase2c-mvv-7d63b9f99bed \
  --openings tests/data/openings-development.json \
  --pairs 4 --seed 20261014 --initial 6 --increment 0.06 \
  --threads 1 --hash-mb 64 --move-overhead-ms 20 --max-plies 512 --smoke \
  --output results/ordering-smoke-repeat
```
