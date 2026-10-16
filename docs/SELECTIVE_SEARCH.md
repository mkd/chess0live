# Phase 2C: conservative late-move reductions

Status: first candidate implemented and tested; retained as opt-in research.
The initial eight-game smoke was unfavorable; the subsequent 128-game
[Phase 2D screen](reports/2026-10-16-phase2d-lmr.md) had a favorable point
estimate but remained inconclusive under its predeclared rule. This experiment
changes search selectivity, not evaluation or time allocation. The existing
search remains the default; no playing-strength improvement is established.

## Hypothesis

History, killer, capture, and transposition-table ordering already put promising
moves near the front of the search. Some later quiet moves may be rejected with
a shallower probe. Searching them one ply less could leave more work for useful
lines, provided apparently promising probes receive ordinary-depth verification.
This is a heuristic: a reduced fail-low can hide a tactic that deeper search
would reveal. Nominal depth is not a guarantee of exhaustive minimax coverage.

The implementation is independently authored. The general technique is described
in the [official Stockfish terminology](https://official-stockfish.github.io/docs/stockfish-wiki/Terminology.html#late-move-reductions),
consulted October 14, 2026. No Stockfish or previous-owner-engine implementation
is copied, linked, or used as the candidate. Null-move pruning and new move
ordering are deferred so this comparison changes one search technique.

## Initial policy, fixed before measurements

`Late Move Reductions` is a UCI check option, initially `false`. When enabled,
reduce by exactly one ply only if all of these conditions hold:

- Interior, non-principal-variation node with depth at least three.
- At least four earlier moves have already been searched.
- Parent is not in check and this move does not give check.
- Quiet move: no capture, promotion, or castling.
- Not the transposition-table move or either killer move.
- Not a pawn push reaching the mover's sixth or seventh rank.
- The search window is outside the mate-score band.

If the reduced zero-window probe exceeds alpha, repeat it at ordinary depth
before allowing a cutoff, including when the reduced result exceeds beta.
Existing full-window PVS verification remains in place. Board state, evaluation,
and repetition history must unwind correctly after every attempt and abort.
Switching the option clears relevant cached search state through the Search API
as well as UCI, preventing selective bounds from contaminating baseline searches.

The opt-in diagnostic line `info string lmr v1 ...` records whether reductions
are enabled, reduction attempts, ordinary-depth re-search attempts, verified
cutoffs, and verification fail-lows. Attempts can include interrupted work;
do not interpret them as completed searches. The existing time-diagnostic v1
schema remains unchanged. Diagnostics stay off in ordinary games and matches.

## Predeclared development checks — October 14, 2026

Parent source commit: `03b6228a5557a8b05ad21e3c721a2448ca72290f`.
Baseline: `build/test-baselines/phase2c-03b6228/chess0live`, SHA-256
`cafaa3ae3e6500d75382b3cf943ebc23d2d154247bc18ac3b3254d206619a80c`.
This is separate from the owner's preserved GUI bundle `0.1-dev-4b8b35d`.
The pinned network, one worker, and 64 MiB hash are shared by both modes.
`Time Policy=classic` throughout: forecast timing is a different experiment.

1. Deterministic eligibility and verification tests, real reduction/re-search
   coverage, baseline restoration after toggling, and legal-PV/rule/limit checks.
2. Native, scalar, and ASan/UBSan correctness suites plus UCI/tool checks.
3. Option-off equivalence against the frozen baseline: the existing three
   benchmark roots, depth 5, three measured repetitions plus warmups. All sampled
   search signatures must match. Timing variation is reported separately.
4. Same-binary off/on profiles at depth 5 over all 12 development openings,
   two repetitions per mode, alternating order: 48 searches. Compare work,
   elapsed time, moves, scores, PVs, and verification behavior together.
5. The same 12 roots, one repetition per mode at exactly 200,000 nodes:
   24 searches. Record completed depth and interrupted work; do not infer
   playing strength merely from nominal depth or agreement on these roots.
6. A four-pair operational smoke: eight games on development openings, seed
   `20261014`, 6+0.06, maximum 512 played plies, identical binary/network,
   reductions on versus off, classic timing, diagnostics and ponder off.

These are short daytime checks under the 50% policy, one active searching
worker. Do not compile during measured profiles or matches. Freeze the built
candidate and inputs before running them; preserve failures and partial output.
The time-policy 32-opening validation suite remains untouched by Phase 2C.

## Acceptance and next work

Passing correctness and development checks allows an opt-in research checkpoint;
it does not justify changing the default. Retain or reject that checkpoint based
on documented functional evidence and whether the hypothesis remains plausible.
Promoting it requires a separately specified, frozen paired-opening strength
test with adequate uncertainty reporting. Long campaigns belong overnight and
are not automatically scheduled. Never tune against validation results while
continuing to label that suite held out.

Move ordering was subsequently evaluated independently. Combine accepted
changes only after isolated comparisons can identify their effects. The separate
time-policy campaign used its own frozen executable.

## Frozen candidate and profile results

Candidate: `build/experiments/lmr-20261014/chess0live`, SHA-256
`b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc`.
Implementation commit: `586b34f`. Engine and tool sources match the frozen
snapshot; the committed Makefile additionally declares the standalone policy
test's `types.hpp` prerequisite. That target was rebuilt and passed.
Its manifest preserves exact source/tool/test hashes and copies, the parent
commit above, Apple Clang 21, generic ARM64 release flags, and pinned network
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
The development-opening file SHA-256 is
`5cedc1469a43cb7e36dac9ab50379dd42626f9251409f5ad14f4b59919b5ea47`.
Frozen binaries, raw reports, and source copies are local ignored artifacts;
this record and the reproducing tools are versioned.

Native, scalar, and ASan/UBSan suites passed, including the new deterministic
policy guards, real accepted/rejected verification paths, interruption, policy
switching, and LMR-enabled rule/cancellation/ponder cases. The profiler passed
12 unit tests. See [validation](VALIDATION.md) for the full evidence boundary.

With LMR disabled, all 24 sampled searches matched the frozen parent exactly,
including every completed iteration's depth, selective depth, nodes, score, PV,
bestmove, and ponder. Median paired baseline/candidate elapsed ratio was 1.00152
with median absolute deviation 0.01654; no default-mode speed gain is established.

| Depth 5: 24 searches per mode across 12 development roots | LMR off | LMR on |
| --- | ---: | ---: |
| Total nodes | 1,686,386 | 846,808 |
| Median reported search time | 464.977 ms | 217.769 ms |
| Reduced probes | 0 | 25,760 |
| Ordinary-depth verifications | 0 | 16 |
| Rejected probes / confirmed cutoffs after verification | 0 / 0 | 10 / 6 |

All 24 off/on pairs retained the same final move, score, and PV at depth 5.
Total searched nodes decreased 49.79%. This is a shallower treatment of selected
branches, not an equal-work throughput result. A different position or depth
can expose a missed tactic. The short timing samples have no significance
interval and are not an Elo estimate.

At 200,000 nodes per search, all 24 searches respected the exact cap. LMR completed
one more nominal depth in 8/12 roots and the same depth in 4/12. Final moves agreed
in 11/12 and scores/PVs in 4/12. On `development-10`, the move changed from
`g2g3` at depth 5 (+17 cp) to `e2e4` at depth 6 (+12 cp); this experiment does
not determine which move is better. On `development-09`, both reached depth 6
with `c2c4`, but the score changed from +28 to +29 cp and the PV differed.
That same-depth difference illustrates the selectivity tradeoff directly.

Nodes in interrupted iterations totaled 1,133,653 off versus 945,186 on, out of
2,400,000 nodes per mode. Reported median times were 1,077.271 and 1,072.638 ms;
similar fixed-node timing does not establish a throughput gain. LMR recorded
67,430 reductions and 55 verifications: 23 were rejected and 32 confirmed
cutoffs. Independent referee checks replayed all reported PVs, best moves,
and ponder replies legally. Reduced fail-lows are not independently verified
by these counters or legality checks.

Local evidence: `results/lmr-20261014/default-equivalence.json`, `depth5.json`,
and `nodes200000.json`. All profiles use classic timing; none consumes the
separate 2B held-out suite.

## Operational match and decision

The predeclared eight games completed: **2 wins, 2 draws, 4 losses** from the
LMR-enabled side, or 3/8 points. There were six checkmates and two threefold
draws, with no protocol failures, time forfeits, exclusions, or ply-cap
truncations. Both sides used the frozen candidate binary, pinned network,
classic timing, one thread, 64 MiB hash, 20 ms overhead, and disabled diagnostics
and pondering. The sole experiment option difference was LMR on/off.
Independent replay verified all 1,231 plies and both types of termination;
protocol logs confirmed the intended options and frozen artifact hashes.

The result is unfavorable to LMR but cannot establish a strength difference
from four development opening pairs at 6+0.06. It does not validate an Elo claim
in either direction. Do not selectively rerun these games or tune against them
while treating later scores as independent validation.

**Decision:** retain the isolated implementation and tools for further research,
with `Late Move Reductions=false`. Correctness passed and the work reduction
makes the hypothesis worth investigating, but the smoke provides no support
for promotion. A larger, separately specified strength campaign and analysis
of tactical misses are still needed. Move ordering is evaluated in a [separate Phase 2C experiment](MOVE_ORDERING.md);
its results must not be attributed to reductions or combined with this baseline.

A subsequent [bounded diagnosis of all four losses](reports/2026-10-14-lmr-losses.md)
found no LMR-specific miss in eight selected roots: all off/on moves agreed at
200,000 nodes, and all 40 common-depth scores/PVs agreed. In the sharpest collapse,
both policies made the same shallow choice and changed it a depth later. This
post-hoc evidence does not establish strength or validate all reduced fail-lows.

The raw match is in `results/lmr-20261014/match-smoke/`: `run.json`, frozen
openings, per-game records, PGNs, protocol logs, and `summary.json`. The independent
audit of profiles and game replay is saved locally in `results/lmr-20261014/audit.json`.

## Subsequent isolated qualification — October 16, 2026

The same frozen candidate completed the predeclared 128-game Phase 2D screen
on 64 fresh opening histories at 60+0.6, with only LMR toggled and classic timing
on both sides. LMR on scored **35W/82D/11L**, or **76/128 points (59.375%)**.
All games passed independent replay with no operational failures. The
conditional two-sided 95% Hoeffding pair-score interval was **42.40–76.35%**;
the predeclared decision is **inconclusive**, so the default remains off.

See the [audited result](reports/2026-10-16-phase2d-lmr.md) for immutable input
and evidence hashes, sampling assumptions, and replay instructions. These
results neither supersede the small development smoke nor establish a rating.
Further strength qualification is deferred. Phase 3A performance measurement
is next, with all experimental search defaults unchanged.

## Reproducing the short development checks

Use the frozen binary locally, or rebuild the recorded source elsewhere.
New builds need not share binary hashes or timings. Each run requires a fresh
output path. Optional dependencies are in `requirements-match.txt`.

```sh
python3 tools/compare_bench.py \
  --baseline build/test-baselines/phase2c-03b6228/chess0live \
  --candidate build/experiments/lmr-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --depth 5 --repeats 3 --search-timeout 10 \
  --output results/lmr-default-repeat.json

python3 tools/profile_lmr.py \
  --engine build/experiments/lmr-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --position-limit 0 --depth 5 --repeats 2 \
  --output results/lmr-depth5-repeat.json

python3 tools/profile_lmr.py \
  --engine build/experiments/lmr-20261014/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --position-limit 0 --nodes 200000 --repeats 1 \
  --output results/lmr-nodes-repeat.json

python3 tools/match.py \
  --candidate build/experiments/lmr-20261014/chess0live \
  --opponent build/experiments/lmr-20261014/chess0live \
  --candidate-network networks/nn-1a298aa575a0.nnue \
  --opponent-network networks/nn-1a298aa575a0.nnue \
  --candidate-option 'Late Move Reductions=true' \
  --opponent-option 'Late Move Reductions=false' \
  --candidate-option 'Time Policy=classic' --opponent-option 'Time Policy=classic' \
  --candidate-revision phase2c-lmr-b825a09efab8 \
  --opponent-revision phase2c-unreduced-b825a09efab8 \
  --openings tests/data/openings-development.json \
  --pairs 4 --seed 20261014 --initial 6 --increment 0.06 \
  --threads 1 --hash-mb 64 --max-plies 512 --smoke \
  --output results/lmr-smoke-repeat
```

The same executable tests both modes. Preserve full opening histories and
record changes to results instead of requiring the search trees to match.
