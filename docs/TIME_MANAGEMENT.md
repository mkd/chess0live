# Phase 2: iteration timing and the forecast experiment

Status: implemented and profiled; playing-strength qualification is pending. This is an
experimental policy, not an accepted playing-strength improvement. The existing
`classic` policy remains the default. See [the current plan](ROADMAP.md).

## Hypothesis and scope

The [first manual games](reports/2026-10-14-cutechess.md) exposed long opening
thinks followed by severe time pressure. The classic controller checks its
preferred stopping time after completing an iteration; the next iteration may
run to the hard deadline before producing a usable result.

The forecast experiment estimates the next iteration's cost from completed
iterations, including aspiration retries. It can decline to start the next
depth when that work is unlikely to finish before the hard deadline. It retains
the classic soft stopping rule and adjustments for best-move stability and score drops.
The estimate is a heuristic, not a guarantee: it may save time, underestimate an
expensive depth, or stop too early and miss a better move.

The initial constants are explicit: extrapolate with the larger of the last two
iteration growth ratios, bounded to 1.5–16, using a 0.001-ms duration floor;
require at least three completed depths before stopping on a prediction. An
estimate exactly equal to the remaining hard budget fits. These choices are
experimental, not parameters already optimized for Elo.

Forecast applies only to ordinary clock-managed searches. Explicit depth, node,
mate, movetime, infinite, and ponder requests keep classic behavior. The first
implementation excludes all pondering, including after `ponderhit`, rather
than treating time spent pondering as charged clock time.

```text
setoption name Time Policy value forecast
setoption name Search Diagnostics value true
position startpos
go wtime 6000 btime 6000 winc 60 binc 60
```

Return to normal settings with `Time Policy=classic` and
`Search Diagnostics=false`. These are options of the new development executable;
the preserved GUI snapshot `0.1-dev-4b8b35d` does not advertise them.

## Diagnostic contract

Diagnostics are off by default. When requested, the engine emits versioned UCI
`info string search-iteration v1 ...` records and one
`info string search-summary v1 ...` record before `bestmove`. Ordinary UCI
depth/score/PV output remains available. Measurements occur at root-iteration
boundaries; no new per-node timing or logging is added.

Each iteration records its depth, completion flag, node delta, duration, and
cumulative elapsed search time. A partially searched depth is recorded too.
Node deltas must sum exactly to the search total. The summary records selected
policy, whether forecasting was eligible, stopping reason, completed depth,
elapsed time, nominal soft/hard budgets, dynamic target, and predicted next cost.
An aborted iteration can still populate the transposition table or ordering
history; its work is not assumed to be wholly useless.

`tools/profile_search.py` checks this accounting, retains raw output and the
best move, and freezes input/tool/binary/network hashes. It alternates the two
policies, clearing the table and waiting for readiness outside every measured
search. Each search receives fresh synthetic clocks; this is not a complete
game or a strength test. Diagnostics themselves add output/measurement overhead,
so the match runner disables them for playing-strength experiments.
Formatting and transporting diagnostics before `bestmove` also consumes GUI
clock time beyond the measured search itself; leave diagnostics off in ordinary
games, especially near flag fall.

## Predeclared first checks — October 14, 2026

These checks were chosen before inspecting candidate results. They are short
daytime investigations under the 50% resource policy, one searching worker and
64 MiB hash. Do not compile during a timed profile or match.

1. Native, scalar, and sanitizer correctness suites, including deterministic
   policy-boundary tests, search accounting, and UCI lifecycle checks.
2. A fixed-depth comparison against frozen `0.1-dev-4b8b35d` at depth 5 over
   the existing three benchmark roots, three measured repetitions and warmups.
   Classic behavior must retain identical nodes, scores, depths, PVs, and moves.
3. Six existing development opening roots, three repetitions of each policy,
   fresh 6-second clocks with 60-ms increment, alternating policy order.
   Compare time, completed depth, scores/moves, and interrupted work together.
4. One exploratory replay of the position before game 2's 5...c6 under synthetic
   159.1-second clocks with 2-second increment, one search per policy. This
   reproduces a similar budget, not the original exact runtime or clock log.
5. A predeclared two-pair operational smoke match using the existing development
   suite, seed `20261014`, 6 seconds + 0.06 seconds/move, maximum 512 played plies.
   Same executable/network; forecast versus classic. No strength inference.

Example short profile (choose a new output filename for every experiment):

```sh
python3 tools/profile_search.py \
  --engine build/macos-arm64-generic-release/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --repeats 3 --output results/time-policy-development.json
```

## First candidate outcome and predeclared revision

The first candidate compared predicted cost with the dynamic **soft target**.
It is frozen at `build/experiments/time-policy-20261014/chess0live`, SHA-256
`c86fc22ff849c3971506853cdb8db890c917864622a48ceaf6df6b23277ac569`.
All 24 fixed-depth searches matched the preserved GUI snapshot exactly.
Native, scalar, and sanitizer correctness suites passed.

At the manual root before 5...c6, classic spent 26.926 seconds and forecast
5.474 seconds, returning identical depth-7 move, score, and PV. Classic spent
21.453 seconds on an unfinished depth 8. However, on the six short-clock roots,
forecast completed depth 4 versus classic's depth 5 in **all 18 comparisons**.
Best moves agreed, but scores differed in 15 comparisons, by up to 25 cp.
This is a depth/time tradeoff, not an inference-speed improvement. The four-game
smoke ended 1W/2D/1L from forecast's perspective, with no errors or clock losses;
it cannot establish a strength difference.

**Decision:** do not retain the soft-target gate. Before examining a second
candidate, change only its predictive boundary to the **hard deadline**. Keep
the estimator and classic soft stopping unchanged. This narrower hypothesis
targets iterations unlikely to produce a completed result before the existing
deadline, while allowing work predicted to finish after the preferred target.

The second checks are declared before running that candidate:

1. Repeat native, scalar, and sanitizer tests and the depth-5 equivalence check.
2. Profile all 12 development roots, three repetitions per policy, with the
   same fresh 6000+60-ms clocks and alternating order (72 searches). The first
   six roots informed the revision; none of this development set is held out.
3. Repeat the single manual-root pair at 159100+2000 ms.
4. Repeat the same two-pair, seed-20261014, 6+0.06 operational smoke. It is still
   exploratory, not a second independent strength experiment.

Freeze the second executable in a distinct directory and preserve both results.
The 32-root validation suite remains unused by these development checks.

## Hard-deadline revision results

Frozen executable: `build/experiments/time-policy-hard-20261014/chess0live`,
SHA-256 `cafaa3ae3e6500d75382b3cf943ebc23d2d154247bc18ac3b3254d206619a80c`.
Its build manifest records source hashes against parent `ed35abf`, Apple Clang
21, generic ARM64 release flags, and the pinned network. Native, scalar, and
ASan/UBSan suites passed. Default classic retained all 24 fixed-depth signatures.
Median baseline/candidate timing ratio was 0.99687, with median absolute
deviation 0.00964; no throughput improvement is established.

| Development profile: 36 searches per policy | Classic | Forecast |
| --- | ---: | ---: |
| Median elapsed time | 492.176 ms | 435.282 ms |
| Total nodes | 3,726,475 | 2,923,998 |
| Nodes in interrupted iterations | 405,667 (10.886%) | 124,161 (4.246%) |
| Time in interrupted iterations | 2,231.409 ms | 748.031 ms |
| Hard-deadline stops | 3 | 1 |

Both policies selected the same best move in all 36 comparisons and matched
every common completed depth exactly (nodes, selective depth, score, and PV).
Final completed depths matched in 32/36, scores in 35/36, and PVs in 32/36.
Forecast was one depth shallower on all three `development-09` repetitions and
one `development-07` repetition. The latter still hit its hard deadline: this
is a heuristic, not a guarantee that unfinished work disappears. On the six
roots used in the first experiment, the revision retained depth 5 in all 18
comparisons; the soft-target candidate had stopped at depth 4 in all 18.

At the manual root, classic took 26.926 seconds versus forecast's 5.788 seconds.
Both completed depth 7, selective depth 19, 1,084,050 nodes, score -17 cp, move
`c7c6`, and PV `c7c6 e2e3 h7h6 g5h4 c8f5 d1f3 g7g6`. Classic then spent
21.380 seconds on an unfinished depth 8; forecast stopped before starting it.
This supports the narrower clock-allocation hypothesis in this position. It
does not establish stronger play, uniformly better timing, or faster inference.

**Decision:** retain the hard-deadline policy as an opt-in experiment, with
classic still the default. Four shallower development results and a remaining
hard stop warrant the longer game test before any default promotion. Do not
tune further against the held-out suite while still calling it validation.

The second four-game operational smoke completed with 2W/2D/0L for forecast,
two checkmates and two threefold draws, with no protocol failures, truncations,
or time forfeits. This favorable tiny result is not a strength estimate or a
reason to promote the default. It uses the same development pair selection as
the earlier smoke and is not an independent confirmation of a rating margin.

Local raw evidence for the two candidates is under
`results/time-policy-20261014/` and `results/time-policy-hard-20261014/`, including
fixed-depth comparisons, development/manual profiles, and smoke match records.
Each binary has its own ignored `build/experiments/` directory and manifest.
Raw logs and executable snapshots remain local; these summaries and reproduction
instructions are versioned. Rebuilding on another host need not yield the same
binary hash or timing.

Reproduce the revision's development profile using a fresh output path:

```sh
python3 tools/profile_search.py \
  --engine build/experiments/time-policy-hard-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --position-limit 0 --repeats 3 \
  --output results/time-policy-hard-repeat.json
```

The manual root's full history is `d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c4d5 e6d5 c1g5`.
Use a single entry in the documented opening JSON format with that history,
`--position-limit 1 --repeats 1 --wtime 159100 --btime 159100 --winc 2000
--binc 2000 --search-timeout 35`. The synthetic budget is not an exact replay
of the owner's clock log.

## Prepared longer test — Phase 2D

The [Phase 2D protocol](PHASE_2D.md) now fixes the exact decision rule and provides
a pinned launcher, preflight, cutoff, and independent result audit. The owner
authorized one daytime exception on October 15 with one active worker. This
section preserves the original test specification; no match result exists yet.

After freezing the binary/options and passing correctness, the first longer
comparison uses the new `openings-time-validation.json`: 32 distinct roots,
both colors, seed `20261014`, 60+0.6, one worker/64 MiB per engine, diagnostics
and pondering off. It is a fixed 64-game sample; do not stop when the score
first looks favorable or reuse roots to inflate the sample size. Once played,
the suite must not be used for tuning and still called held out.

The suite is an original small selection of legal opening lines, not a
representative rating pool; related opening families limit generalization.
The runner's conservative uncertainty interval may be very wide at 32 pairs.
Default promotion requires predeclared evidence of strength benefit with no
operational regressions, not a favorable tiny sample, NPS, or less thinking time.
An inconclusive result leaves classic as default and calls for a separately
specified follow-up, not a post-hoc change to this sample.

Run the long test only during the permitted overnight window or an explicit
owner override. No automation has been created. If the window ends before the
fixed sample completes, stop cleanly and retain an incomplete result; do not
reinterpret completed games as the full predeclared experiment.

Prepared command for the frozen revision, **not yet run** (requires the optional
match dependencies, the archived revision binary, and a fresh output directory):

```sh
python3 tools/match.py \
  --candidate build/experiments/time-policy-hard-20261014/chess0live \
  --opponent build/experiments/time-policy-hard-20261014/chess0live \
  --candidate-network networks/nn-1a298aa575a0.nnue \
  --opponent-network networks/nn-1a298aa575a0.nnue \
  --candidate-option 'Time Policy=forecast' --opponent-option 'Time Policy=classic' \
  --candidate-revision phase2-hard-forecast-cafaa3a \
  --opponent-revision phase2-classic-cafaa3a \
  --openings tests/data/openings-time-validation.json \
  --pairs 32 --seed 20261014 --initial 60 --increment 0.6 \
  --threads 1 --hash-mb 64 --max-plies 512 \
  --output results/time-policy-validation-60-plus-0.6
```
