# Phase 4F.18 — isolated quiescence delta pruning

Declared November 4, 2026, before implementation or candidate measurements.
Parent: `0bbe5f08d8976df567a7d62f9692b78ca6199b8a` (engine same as `e16ca73`).
The owner authorized the next development phase after the read-only Hyperion
review. This is an independently authored hypothesis using chess0live's own
code, fixtures and score scale; no implementation/assets from other engines are
imported. It remains disabled by default: `QSearch Delta Pruning=false`.

## One fixed rule

Consider only ordinary interior quiescence nodes with an original-entry scout
window, no check, ordinary alpha/beta/stand-pat score bands, no current twofold
history, halfmove clock below 80, more than eight pieces, and no pawn of either
color on its relative sixth/seventh rank. Exclude null-probe, verification and
ProbCut modes. Preserve terminal/draw handling before heuristic evaluation.
Only ordinary captures qualify: exclude promotions and en passant, and reject
missing/king victim identities.

Freeze the original stand-pat and entry alpha. Propose skipping a capture only
when `stand_pat + victim_allowance + 400 < entry_alpha`, with int64 arithmetic.
Victim allowances in internal search units are pawn 400, knight 1280, bishop
1320, rook 2000 and queen 3600: four times the existing local material-order
values. The pinned GUI conversion varies with material (roughly 300 internal
units per displayed pawn); these deliberately generous allowances plus the
400-unit margin are an engineering hypothesis, not a mathematical bound on
NNUE or a copy of another engine's centipawn constants. No margin tuning follows
measurement. The rule uses the original stand-pat, never a previously searched
capture's best score.

Inspect the real child after the deficit test. Checking captures and terminal
children retain ordinary search. Poll stop limits after child inspection and
restore state on skip, stop or exception. A skipped child adds no history or
NNUE evaluation. Delta gets the first skip opportunity when both delta and
existing SEE pruning are requested; otherwise SEE keeps its existing rule.
Count an actual skip once. Both options remain off in the accepted baseline;
only delta changes in the development comparison. Changing the delta policy
clears reusable search state. Diagnostics report eligible nodes, proposed
candidates, actual skips, and protected checking/terminal children; diagnostics
must not change search decisions or run in timed cells.

## Correctness and frozen development screen

Require exact parent/candidate-off search equivalence. Check actual skip and
protected-child branches, both colors, specials, mate/stalemate, draw history,
score/margin boundaries, policy changes, aborted searches, allocation-failure
restoration, native/scalar/sanitizer execution and parallel accounting. The
unchanged NNUE arithmetic needs its existing regression suites; this phase
makes no new external-network architecture claim. Preserve failed checks and
fixes. No frozen binary or previous evidence is overwritten.

After correctness and independent review, freeze source/tool/binary identities.
Use all fifteen previously exposed roots from
`tests/data/countermove-profile.json`, retaining their original histories.
Threads 1, Hash 64 MiB, pinned `nn-1a298aa575a0.nnue`, classic time policy,
Move Overhead 20, MVV-LVA and conservative LMR on; all other optional experiments,
Syzygy, ponder and diagnostics off. A fresh quiet-host declaration is required
for timing. At most one active search worker; no overlapping builds/tests.

Run exactly 150 searches, one observation per cell, alternating role order:

1. Parent versus candidate-off, depth 6, cold and warm: 60 searches.
2. Candidate-off versus candidate-on, depth 6, cold and warm: 60 searches.
3. Candidate-off versus candidate-on, fresh 500-ms searches: 30 searches.

Depth searches have a 15-second external bound; timed cells have a 10-second
protocol bound. Search/setup budget is 300 seconds, with bounded cleanup and
evidence publication afterward. No retries, replacement cells, discarded
warmups, extended sample or within-phase retuning. Stop on a correctness or
process failure and preserve partial evidence. Independent raw replay must
verify all legal PV/final moves, complete expected cells, option/transcript
identity, frozen hashes and process exits. Report every common-depth score/PV
and final-move difference, total nodes, completed depth, elapsed time and all
failures; never require enabled-heuristic search parity. Before measurement,
inspection confirmed that uninstrumented UCI exposes neither quiescence-only
nodes nor internal integer scores. Record both as unavailable in timed cells;
retain displayed cp/mate scores without trying to reverse their rounding.
Separate correctness diagnostics establish actual pruning activation.

## Decision and remaining qualification

This finite screen decides whether the candidate merits further investigation,
not whether it is stronger. Correctness failure blocks retention. No activation,
no work savings in either cache condition, or an unexplained tactical regression
parks qualification; do not force success by loosening the rule. Mixed results
are reported as mixed. A sound opt-in implementation may remain available with
its qualification explicitly pending; defaults cannot change from these data.
No percentage speed threshold, Elo estimate or win claim follows this screen.

The existing 39-position, 60-seconds-per-role puzzle comparison remains the
owner's separate full tactical-progress requirement in VALIDATION.md. It takes
about 78 minutes and needs the overnight window or an explicit daytime exception;
the short development screen cannot substitute for it. Prepare concrete inputs
before requesting any needed run authorization. No game campaign or automatic
schedule is authorized here. Later strength qualification also requires clock
readiness; the historical six Phase 4F.13 forfeits remain unresolved.

Confirm engine exits and OS cleanup after the short screen, then release LM
Studio immediately. Preserve stable GUI `0.1-dev-4b8b35d`, the historical normal
release digest caveat, prior campaign evidence and the owner's modified
`tools/batch_positions.py`. Record results/limitations in roadmap, handover,
validation and a dated report; validate documentation and commit locally on main.
The owner handles GitHub pushes.
