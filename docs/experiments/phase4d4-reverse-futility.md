# Phase 4D.4: conservative reverse-futility development screen

Predeclared October 19, 2026, before this candidate's measurement searches.
One independently authored candidate remains disabled by default. The fixed
screen is a development checkpoint, not a held-out strength qualification or
proof that pruning preserves every best move.

## Fixed candidate

`Reverse Futility Pruning` may return beta at an ordinary interior non-PV node
with depth 1–3 when fresh NNUE evaluation minus beta reaches the fixed margin
`50 + 150 * depth`: **200, 350, 500 internal score units**, respectively.
The static evaluation and search window must lie outside the special mate and
tablebase bands. This is a heuristic static bound, not a searched minimax bound.

Reject check, null-probe/verification subtrees, current-position twofold real
history, halfmove clock 80 or greater, seven or fewer total pieces, fewer than
two own non-pawn/non-king pieces, no own pawn, fewer than two legal moves, any
pawn of either color on its relative sixth or seventh rank, and **any legal
capture or promotion**. Quiet checking moves are not excluded; missing a quiet
tactical defense remains an explicit risk. Earlier legal-terminal and draw
handling still applies.

A cutoff changes no chess position or game history and supplies no PV move.
Fresh static evaluation may update worker-local NNUE accumulator caches. It
does not directly save an original-depth TT bound. Ancestor bounds can still
depend on a heuristic cutoff. Policy changes invalidate reusable search state.
Worker-local diagnostic evaluations/cutoffs are aggregated only after worker
joins; diagnostics remain disabled in this screen. These restrictions reduce
the candidate's scope without proving universal zugzwang or tactical safety.
No parameters are retuned after observing this screen.

## Frozen roots and settings

- Parent SHA-256:
  `d0617575e7ece0dc3c38d4f44f33b6bc93adad8cf947a129af6dec137246b530`.
- Network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Exposed source corpus: `tests/data/countermove-profile.json`, SHA-256
  `afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f`.
- Select exactly these six IDs, in order: `opening-01`, `opening-02`,
  `opening-03`, `gamephases-mg-01`, `gamephases-mg-03`, `gamephases-eg-06`.
  They cover three complete opening histories, a quiet closed center, tactical
  minor-piece contacts, and a mixed rook/minor endgame. The composed FENs retain
  the source's missing-history and reachability limitations. No owner's puzzle
  or reserved qualification position is consulted.
- The selected six source objects, serialized as sorted-key compact JSON plus
  one trailing newline, have SHA-256
  `5296ab5c59ae94c87a68e284598fd656afc9881b87f81665351297d684fed307`.
- Threads 1, Hash 64 MiB, classic time policy, Move Overhead 20 ms, MVV-LVA
  captures. Ponder, LMR, countermove ordering, null pruning, Syzygy and search
  diagnostics are disabled. Only the candidate-on role enables reverse futility.

## One finite 60-search sequence

1. **Parent equivalence:** frozen parent versus candidate-off, six roots, cold
   and warm depth-6 searches: 24 searches. Every declared iteration/final
   signature must match before the next stage starts.
2. **Work comparison:** candidate-off versus candidate-on, the same six roots
   and cold/warm depth-6 conditions: 24 searches.
3. **Equal-time comparison:** candidate-off versus candidate-on, six roots,
   fresh state only, `go movetime 500`: 12 searches.

One repetition per cell; no discarded warmups or selective reruns. For each
depth-stage root, use listed role order at zero-based even indices and reversed
order at odd indices. Reverse that order again for the equal-time stage. Each
role/root/stage starts a fresh process. Send `ucinewgame` before its cold search;
the immediate warm repeat retains TT and learned state. Equal-time cells each
start a fresh process with `ucinewgame`; they never inherit the depth stage.

Depth searches have a 60-second wall limit; timed searches have a 10-second
protocol allowance, not extra requested thinking time. The complete screen has
a 900-second admissibility budget covering setup, searches and engine cleanup.
The tool checks this again after the final process closes: a cleanup overrun
invalidates the screen even if all 60 searches completed. Bounded cleanup and
final evidence persistence may finish after the budget; they cannot make
over-budget engine work valid. Preserve failed or interrupted evidence and
stop; do not replace cells or extend the experiment.

## Resources and evidence

All other development builds, engine tests and campaigns must be idle before
passing `--quiet-host`. This declaration is recorded and is not an operating
system utilization measurement. The completed Phase 4D.2 campaign is not
reserved or resumed. At most one profile engine and one search worker are
active. Recheck the current Helsinki resource policy before each search,
reserving 256 MiB plus four times the network file size; reject unknown physical
memory or an inadmissible CPU/memory budget. No automatic schedule is created.

Save the complete command/output sequence, observed search elapsed time, raw
UCI iteration/final counters, resources, protocol text and before/after hashes
of binaries, network, corpus and tooling. Create output exclusively; retain
partial evidence and reject source drift. Preserve late shutdown output and
require clean process exit, joined reader and one final EOF marker.

The pinned independent `chess==1.11.2` referee must replay every root, PV,
bestmove and ponder. Require ordered exact-score iterations, consistent final
counters, zero tablebase hits and no search diagnostics/errors. Parent/off
agreement includes per-depth depth, seldepth, nodes, score, PV, hash occupancy
and final nodes, bestmove and ponder; elapsed time and NPS are excluded.

Report cold/warm nodes and elapsed time separately, every common-depth score/PV
change, final decisions, seldepth, completed depth and unfinished nodes. The
500-ms comparison can select different final depths and decisions; retain those
differences rather than treating matching moves as a prerequisite. This single
exposed repetition supports descriptive measurements only, **not a qualified
speed gain, Elo result or promise of no strength loss**. Keep reverse futility
off pending separate operational and frozen playing-strength evidence. Do not
retune the candidate or start a qualification match from these results alone.

## Reproduce

After correctness checks and freezing the candidate, with other development
work idle:

```sh
python3 tools/profile_reverse_futility.py \
  build/experiments/phase4d3-20261018/chess0live \
  /absolute/path/to/frozen/candidate/chess0live \
  --quiet-host --output results/phase4d4-20261019/profile.json
```

Historical profiling tools, protocols and saved evidence are unchanged. The new
tool reuses their pure validation, legal replay, shutdown and exclusive-write
helpers, while independently freezing this screen's ordering and resource rules.
