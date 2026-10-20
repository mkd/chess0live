# Phase 4D.5: quiescence SEE development screen

Predeclared October 20, 2026, before candidate measurement. One independently
implemented capture-pruning hypothesis remains disabled by default through
`QSearch SEE Pruning=false`. Delta pruning and changes to other search policies
are outside this screen. No parameter is tuned after observing its results.
This is an exposed development checkpoint, not a playing-strength qualification.

## Fixed candidate

At interior quiescence nodes, consider only ordinary captures with negative
static exchange evaluation (SEE). Require a zero-width window at function
entry, ordinary search mode, no check, ordinary alpha/beta score bands, no
current-position twofold real history, halfmove clock below 80, more than eight
pieces before capture, and no pawn of either color on its relative sixth or
seventh rank. The piece-count guard preserves both seven-piece positions and
captures entering seven-piece positions.

Never prune en passant or promotion moves. For an eligible losing capture,
make the real child and keep the capture if it gives check or reaches a legal
terminal position. Poll search limits and restore the position before skipping;
the skip happens before child history/evaluation processing. Both null-probe
and legal-verification subtrees are excluded. There is no SEE margin to tune.
This is a heuristic: excluding these cases does not prove that every remaining
material-losing capture lacks compensation or a forced tactic.

## Frozen roots, binaries and settings

- Parent source: `dcfd23c4e1f346decb5b3db99426c957ec6ca811`.
- Frozen parent: `build/experiments/phase4d5-20261020/parent-chess0live`.
- Parent SHA-256:
  `361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Source corpus: `tests/data/countermove-profile.json`, SHA-256
  `afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f`.
- The same six previously exposed roots used in Phase 4D.4, in order:
  `opening-01`, `opening-02`, `opening-03`, `gamephases-mg-01`,
  `gamephases-mg-03`, `gamephases-eg-06`.
- Selected source objects, serialized as sorted-key compact JSON and a trailing
  newline, SHA-256:
  `5296ab5c59ae94c87a68e284598fd656afc9881b87f81665351297d684fed307`.

The opening roots retain their complete supplied histories; composed middlegame
and endgame FENs retain the source's reachability and missing-history limitations.
Threads 1, Hash 64 MiB, classic time policy, Move Overhead 20 ms and MVV-LVA
capture ordering are fixed. Ponder, LMR, countermove ordering, null pruning,
reverse futility, Syzygy and search diagnostics are all explicitly disabled.
Only candidate-on enables `QSearch SEE Pruning`.

## One finite 60-search sequence

1. Parent equivalence: parent versus candidate-off, six roots, cold and warm
   depth-6 searches, 24 cells. All per-iteration/final signatures must match
   before the next stage starts.
2. Work comparison: candidate-off versus candidate-on, the same six roots,
   cold and warm depth-6 searches, 24 cells.
3. Equal-time comparison: candidate-off versus candidate-on, six fresh roots,
   `go movetime 500`, 12 cells.

Use one repetition per cell, no discarded warmups, retries, replacement cells or
sample-based tuning. At zero-based even indices use the listed role order; at
odd indices reverse it. Equal-time order reverses the work-stage order again.
Each stage/root/role creates a fresh process. Send `ucinewgame` before the cold
search; only the immediate warm repeat reuses TT and learned state. Equal-time
cells always start fresh. Send `isready` after each position and before timing.

Depth searches have a 60-second external wall limit. Timed searches request
500 ms with a 10-second protocol timeout, not extra thinking time. Setup,
searches and cleanup together must fit within 900 seconds. Check the deadline
again after final engine cleanup; over-budget work is invalid even if all
samples completed. Bounded cleanup and evidence persistence may finish later.
Preserve an interrupted/invalid screen without replacing or extending it.

## Evidence and resource boundaries

The operator must stop other development builds, engine tests and campaigns
before supplying `--quiet-host`. This explicit declaration is recorded and is
not an OS utilization measurement. At most one engine/search worker is active.
Before each search, check current Helsinki resource limits and reserve 256 MiB
plus four network sizes. Reject unknown physical memory or an inadmissible
CPU/memory budget. This tool does not create an automatic schedule.

Save complete commands and output, raw iterations/final counters, observed
elapsed times, resource policy, protocol text, and before/after hashes of the
binaries, network, roots, relevant source and tooling. Output is exclusive;
existing evidence and partial output cannot be overwritten. Require clean
process exit, joined reader, one final EOF and no hidden shutdown output.

The pinned independent `chess==1.11.2` referee must replay every root, PV,
bestmove and ponder. Require ordered exact-score iterations, consistent final
counters, zero tablebase hits and no diagnostics/errors. Parent/off signatures
include depth, seldepth, nodes, score, PV, hash occupancy and final decisions;
they exclude time and NPS.

Report fresh/reused-cache nodes and elapsed time separately. Retain every
common-depth score/PV difference, final decision, completed depth, seldepth and
unfinished-node count. A timed search may complete another depth or choose
another move. These observations are descriptive, not a qualified speed gain,
Elo result or guarantee against tactical or playing-strength regressions.
Pruning stays off pending separate operational and frozen strength evidence.

## Separate puzzle progress requirement

The owner's existing simple `tools/batch_positions.py` and printed scores remain
the puzzle workflow. This profiler neither imports nor edits that script and
does not add a second puzzle benchmark framework.

A bounded 1,000-ms matched smoke of its 39 supplied FENs may accompany this
checkpoint, using a recorded temporary adapter and identical settings. Preserve
the actual editable source text/hash, exact FEN list, annotations, binary/network
pins and complete printed outputs. Record any positive-mate gains, losses and
distance changes without treating the supplied annotations as certified answers.
The short smoke is explicitly separate from the required matched 60,000-ms
progress benchmark in [validation](../VALIDATION.md#use-for-development-progress),
whose first full baseline remains pending. The short screen cannot satisfy that
gate or establish an Elo gain. Long runs remain subject to the overnight policy;
this protocol schedules none.

## Reproduce

After correctness checks and freezing the candidate, with other development
work idle:

```sh
python3 tools/profile_qsearch_see.py \
  build/experiments/phase4d5-20261020/parent-chess0live \
  /absolute/path/to/frozen/candidate/chess0live \
  --quiet-host --output results/phase4d5-20261020/profile.json
```

Frozen historical tools/protocols are unchanged. The new orchestration reuses
their pure corpus, legal-output, resource, summary, cleanup and exclusive-write
helpers. Its own stage names, options, parent pin and deadlines define this
screen; the historical reverse-futility screen is not executed.
