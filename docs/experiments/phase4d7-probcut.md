# Phase 4D.7 — bounded tactical ProbCut

Fixed October 23, 2026, before implementation or candidate searches. Parent
source `8052b09906099fb169d1b9a1e114004fc68be473`, executable SHA-256
`c1858bb92419e00bbe3846e2daa94dc4260effad6acea705a2455881c920c199`.
Local parent: `build/experiments/phase4d7-20261023/parent-chess0live`.
Network SHA-256:
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

## Isolated hypothesis

Add `ProbCut`, default false. A few promising legal captures may establish a
reduced-depth score comfortably beyond an interior scout window, avoiding an
expensive ordinary search there. This is a heuristic prediction, never proof
of a full-depth bound or guaranteed strength preservation.

- Ordinary non-root, non-PV scout nodes at depth >=5 only. Exclude check,
  mate/tablebase-band windows, repeated positions, halfmove clocks >=80,
  advanced pawns of either color, eight-or-fewer-piece positions, fewer than
  two legal moves, and sides with fewer than two non-pawn pieces or no pawns.
- After normal move ordering, examine at most three ordinary legal captures,
  counting the cap before SEE. Exclude promotions and en passant. SEE >=0
  admits a capture to a quiescence screen at `raised_beta = beta + 200`
  internal score units, provided the raised window stays outside special bands.
- A finite ordinary quiescence fail-high permits a legal-move search at child
  depth `depth - 4` against the same raised scout window. All quiet replies and
  check evasions participate. Checking captures are permitted; ordinary check
  extensions still apply. Require a completed finite ordinary score >= raised
  beta in both stages before returning only the original beta.
- Both probe subtrees have genuine game-history draws but no TT probes/stores,
  selective reductions, nested pruning or learning of history/killers/replies.
  Discard their PV evidence at the current node. Do not directly store a
  reduced result as an original-depth TT bound. Ordinary ancestor bounds can
  depend on this heuristic, so changing the option clears TT and ordering state.
- Preserve exact reversible board/history state and account every probe node
  against the normal shared stop, node and clock limits. Attempt counters
  include interrupted work; completed outcomes exclude it. Sum worker-local
  counters only after helpers join.

No tuned margins, broader guards, ordering changes or other new pruning in this
checkpoint. Conventional LMR remains enabled; deeper reductions, null move,
reverse futility, quiescence SEE and countermove ordering remain off.

Technique references: Buro's [ProbCut paper](https://journals.sagepub.com/doi/10.3233/ICG-1995-18202)
and Jiang/Buro's [chess experiments](https://skatgame.net/mburo/ps/chessmpc.pdf).
They motivate shallow-search prediction. This independently authored,
capture-focused fixed-margin hypothesis is not their fitted statistical model;
its margin has no calibrated error probability. No external engine code is used.

## Correctness and finite development screen

Check both colors, sacrificed material and quiet defenses, checks, mate and
stalemate, promotions/en passant, sparse and pawn endings, real repetition and
rule-50 state, interrupted probes, policy switching, node/time limits, stop and
ponder lifecycle. Check source-level isolation of TT, PV and learning state;
test actual activation and completed/rejected outcomes when reproducible.
Do not tune the policy to manufacture a rare diagnostic event. Run relevant
native, scalar, ASan+UBSan and TSan checks with modest worker counts.

Reuse the six exposed positions in `profile_reverse_futility.load_positions`
from `tests/data/countermove-profile.json` unchanged. One 60-search matrix:
parent versus candidate-off at depth 6 cold/warm (24 searches); off versus on
at depth 6 cold/warm (24); off versus on at 500ms cold (12). Alternate roles by
position and reverse the timed-stage order. Use Threads=1, Hash=64,
Move Overhead=20, classic timing, LMR enabled, MVV-LVA, other experiments off,
Syzygy off and the pinned network. Diagnostics record activation, probe/cutoff
counts, legal PVs, scores, completed depth, nodes, time and abandoned work.
The timing is instrumented diagnostic evidence, not a strength or clean NPS test.
Require exact parent/off search parity, including hash occupancy. Limits are
60s per depth search, 10s per timed search and 900s overall. No concurrent builds
or benchmarks during measurements; do not tune or repeat for a better result.

The required full puzzle comparison is 39 positions per build at 60,000ms with
one worker and Hash=64, identical settings except ProbCut, using the frozen
simple owner runner through a separate adapter. Preserve the owner's editable
script, README introduction and GUI snapshots. Save complete outputs and pins;
do not create a second puzzle framework. The approximately 78-minute run needs
the overnight window or a new one-run daytime exception. Previous exceptions
are consumed. No schedule or long match is authorized by this record.

## Decision

A serious reproducible tactical, state or protocol regression parks the candidate.
Record all score/PV changes and costs, including failed probes. Passing the
finite checks permits only consideration of separate equal-resource strength
qualification; keep ProbCut off until that succeeds. Complete this bounded
checkpoint before choosing another search hypothesis or advancing Phase 4E's
platform/runtime and network-tooling work. Do not extend this phase through
repeated tuning of exposed tests.
