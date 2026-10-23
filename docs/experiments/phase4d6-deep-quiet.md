# Phase 4D.6 — one broader quiet-reduction candidate

Fixed October 23, 2026, before candidate searches. Parent source `9bb8ffb`,
executable SHA-256 `4f51466335c5021ace971da8ed12548f884a9c1299484a8e2b3f39858a24b28c`,
network SHA-256 `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Local parent: `build/experiments/phase4d6-20261023/parent-chess0live`.

## Separate changes

1. GUI reporting: retain existing TT replacement/probing, but report sampled
   nonempty retained occupancy instead of current-generation occupancy. Verify
   cross-position reuse, clearing and exact search parity. This changes no
   search policy and does not imply a cache speedup.
2. Opt-in `Time Policy=bounded`: ordinary clock-only requests use the same soft
   budget/signals and a hard ceiling `min(available,max(soft+5ms,2*soft))`, versus
   classic/forecast's four-times multiplier. Explicit depth/nodes/mate/movetime,
   infinite and ponder requests keep their existing budgets. Do not alter
   forecast or promote bounded timing from saved time alone.
3. Opt-in `Deep Quiet Reductions`: when ordinary LMR already permits reduction,
   use two plies rather than one only at depth >=5, after at least eight earlier
   moves, for a knight/bishop/rook/queen move with more than seven pieces on the
   board. All inherited check, PV, root, special move, TT/killer and special-score
   guards remain. An alpha-raising probe re-searches directly at ordinary depth;
   never accept an intermediate reduced verification. LMR off disables both
   tiers. Keep the new option off and clear incompatible TT/history on switching.

No extra pruning, history tuning or parameter variants in this checkpoint.
Pawn/king moves and seven-piece endings keep accepted behavior. These exclusions
limit risk; they do not prove tactical or zugzwang safety in every position.

## Checks and fixed development screen

Run policy boundaries and board-backed checks for both colors, quiet defenses,
pawn breakthroughs, sparse zugzwang, checks, promotions, mate/stalemate, draw
history, interrupted verification, node/time limits and one/four-worker state
restoration. Run relevant native/scalar/ASan+UBSan and TSan checks.

Reuse the six exposed positions selected by `profile_reverse_futility.load_positions`
from `tests/data/performance-gamephases.json`, without editing that corpus.
Use Threads 1, Hash 64, accepted LMR on, classic timing, MVV-LVA, other experiments
off and Syzygy off. Alternate role order by position. A single 60-search matrix:
parent versus candidate-off at depth 6 cold/warm (24); off versus on at depth 6
cold/warm (24); off versus on at 500 ms cold (12). Diagnostics capture activation,
verification, legal PVs, decisions, nodes and discarded iteration work. Preserve
all score/PV/move differences. At most 60 seconds per fixed-depth search, ten
seconds per timed search and 900 seconds overall. Do not tune/repeat the screen
for a more favorable result. Counters/elapsed time do not establish strength.

Timing feedback is a separate small screen: replay the supplied full histories
before White moves 2, 3 and 22, with 120+1 and the approximate remaining clocks
from rounded PGN comments. Compare classic and bounded, one worker, Hash 64,
LMR on, deeper reductions off, alternating order, one search per role/root.
Verify limits/legality and report completed work and losses as well as savings.
This is an exposed diagnostic and cannot reproduce the original ten-worker GUI
schedule. No contemporaneous build or benchmark during timed measurements.

The required matched 39-position, 60-second puzzle comparison uses frozen
parent versus deep-reductions-on, one worker and identical Hash 64/network.
Use the existing simple batch script without changing the owner's configuration.
Save full outputs and identities. A roughly 78-minute run requires the overnight
window or a new owner daytime exception; no schedule or long match is authorized
by this record. Correctness and short screens proceed independently.

## Decision

Retain the reporting correction only with exact search parity. Keep bounded
clock policy and deeper reductions explicitly opt-in; a tactical/operational
failure parks the affected experiment. Full puzzles complement a separately
frozen equal-resource match before any strength/default claim. Do not reuse
exposed October 22 qualification openings. After this finite checkpoint move
toward the planned ProbCut 4D.7 or the most material recorded blocker, without
repeatedly tuning this sample.
