# Phase 4D.1: isolated countermove ordering

This protocol was written before the first candidate measurement. It defines
one bounded development checkpoint, not a strength qualification or permission
to change the default. The isolated hypothesis is that ordering a previously
successful quiet reply to the preceding move ahead of ordinary quiet-history
moves can reduce search work without changing search depth or discarding moves.

## Frozen comparison

- Parent: Phase 4C, source checkpoint `f8e50f3`; native binary SHA-256
  `9b5f03e02d9537041025dfd6a815a1ef734fb7a303a14bcaba17f1ea4f57e898`.
- The candidate has `Countermove Ordering=false` by default. The comparison
  changes only this option, false versus true, using the same candidate binary.
  Record the completed candidate source and executable hashes before execution.
- Network: `nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Corpus: every root in `tests/data/countermove-profile.json`, in file order.
  It combines the three exposed benchmark openings and all twelve exposed
  composed middlegame/endgame roots. No engine result selected or excluded a
  root, and no Phase 3L held-out opening is accessed. These roots are development
  diagnostics, not an independent strength sample.
- Settings: `Threads=1`, `Hash=64`, `Time Policy=classic`,
  `Late Move Reductions=false`, `Capture Ordering=mvv-lva`, `Ponder=false`,
  `Move Overhead=20`, `SyzygyPath=<empty>`, `SyzygyProbeLimit=0`,
  `Search Diagnostics=false`. Timed samples exclude optional diagnostic output;
  dedicated functional tests verify the countermove counters separately.

## Measurement matrix and limits

Run both `go depth 6` and `go movetime 500`, with three repetitions of every
root/policy. For each policy/root/repetition, send `ucinewgame`, the complete
position and `isready`, then measure the cold search. Immediately repeat the
same position and limit without `ucinewgame` or a policy change for the warm
search. Warm means retained transposition **and heuristic** state, not an
isolated transposition-table effect. It is reported separately from cold.

Two resident engines hold one fixed policy each; only one searches at a time.
Alternate off/on order by root, repetition and limit kind. Record all 360
searches; use no outcome-dependent reruns, exclusion or stopping. Readiness,
network loading and reset work are outside the monotonic go-to-bestmove timing.
There are no discarded search warmups: the labeled cold/warm matrix records
both. No build, other benchmark or match runs concurrently with timing.

The external timeout is 60 seconds per search and 600 seconds for the complete
run. A timeout, interruption, illegal move/PV, malformed reply, changed artifact,
or resource refusal invalidates the run and preserves its partial evidence.
The runner closes both engines on every exit. Resource admission is refreshed
before each search; the ordinary local resource policy applies. No schedule or
qualification campaign is started by this protocol.

## Correctness and interpretation

Before candidate-on profiling, compare the frozen parent with candidate-off
using `tools/compare_bench.py` on this same corpus at depth 6, one recorded warmup
and three measured repetitions. Every completed-depth score, PV, node count,
selective depth and final move must match on all sampled searches. This is a
finite regression check, not universal equivalence.

Independently replay every profile root, complete PV, best move and ponder move
with pinned `chess==1.11.2`. Keep LMR and tablebases off. Report all completed
score differences by depth/root/policy, including those with warm state; inspect
any fixed-depth score difference before deciding whether the candidate is fit
for further testing. Equal-score tied moves and different trees are permitted.
Do not silently hide a legal but unfavorable decision.

Report per root and cold/warm limit: nodes, external and reported elapsed time,
NPS, completed depth/seldepth, scores, moves, hash occupancy, and nodes spent
after the last completed iteration. Summarize node and elapsed ratios, total
work, and score/move/depth differences. Timed searches may finish different
iterations; their scores are not automatically comparable minimax results.
Node savings, NPS, depth and timings establish no strength or Elo gain.

The initial checkpoint allows at most one separately recorded diagnostic
revision. Keep unsuccessful evidence. A promising implementation may proceed
to a separately frozen equal-time paired strength comparison; no such campaign
is included here. An inconclusive or unfavorable result retains the existing
default, then development advances to the next justified roadmap candidate.
