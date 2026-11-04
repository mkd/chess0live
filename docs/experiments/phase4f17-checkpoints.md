# Phase 4F.17 candidate — selective quiescence-parent checkpoints

Declared November 4, 2026, after the
[diagnosis protocol](phase4f17-nnue-reuse.md) and before candidate measurement.
The independently audited current-parent CPU profile observed NNUE in 4,439 of
5,210 active-search samples (85.20%). Feature planning plus accumulator application
accounted for 3,213 (61.67%). Only 23 short-lived workers were sampled for 30
measured searches; these are sampled stack shares, not cycles or per-root coverage.
All 45 searches, including warmups, passed independent raw replay.

## One bounded hypothesis

Allocate 128 checkpoint slots per search worker before dispatch. Each contains
two numeric accumulators, the saved board and validity metadata; do not copy
active feature vectors. Standalone evaluators keep their existing arbitrary-
transition interface and need no checkpoint allocation. Measure actual storage
size in tests; expected size is approximately 0.6 MiB per worker, below 5 MiB
for eight workers. This is additional storage, independent of configured Hash.

Invalidate the current slot at every actual alpha-beta/quiescence entry, including
unevaluated/terminal nodes. Checkpoint only a nonchecked quiescence parent whose
stand-pat did not cut off and whose tactical move list is nonempty, before searching
children. Checkpointing verifies the current evaluated board and generation; a
mismatch skips caching and never forces evaluation. Main-search static evaluations
and checked nodes are not checkpointed in this first candidate.

Evaluation may reuse the nearest valid ancestor checkpoint. Prepare both exact
update plans from that saved board before modifying current state. Then copy
numeric accumulators, apply both updates, and commit board/generation. Otherwise
retain the existing last-evaluated-position path. Reset/new search or changed
network generation invalidates all checkpoints; failed reload keeps the valid
network. Null moves still infer and calibrate with the actual side/clocks. No
score, bound, feature policy, search depth or pruning decision is cached/changed.

## Correctness gate

Exercise the actual implementation helper and public APIs, requiring positive
reuse plus all hidden/PSQT lanes, feature multisets, raw and calibrated outputs
to agree with full refresh. Cover siblings, skipped/unevaluated parents, stale
slots, deepest slots, special moves, null moves, orientations, arbitrary board
jumps, reset and successful/failed reload. Preserve the existing two-plan
allocation-failure guarantee. Run native/scalar/ASan+UBSan NNUE/search checks,
TSan search/SMP checks and a fresh isolated pinned reference oracle. The external
oracle validates full-refresh arithmetic; new internal checks must separately
validate the checkpoint path. Run optional pruning regressions for the entry-
invalidation integration. Keep all failures and fixes in evidence.

## Fixed timing decision

Freeze candidate sources, binary and protocol after correctness/source review.
Use the unchanged `profile_search_baseline.py`, all fifteen exposed roots, depth 6,
Threads 1, Hash 64 MiB, pinned network, accepted LMR-on/null-off preset, diagnostics
off. The owner confirmed a quiet AC/Automatic host. Two engines resident, only
one active worker; no builds/tests overlap timing. Recheck resource admission.

First run one parent-versus-parent control with two cold/warm repetitions (120
searches). Then exactly three alternating-order parent/candidate blocks with
three repetitions each (180 searches each, 540 total), no discarded warmups.
Each search is capped at 15 seconds, each block's search/setup at 300 seconds;
the existing harness performs final cleanup/hash publication afterward. Preserve
partial evidence and stop on correctness/process failure, never replace failed
cells or extend the matrix after seeing results.

Require exact depth/seldepth/nodes/score/PV/bestmove/ponder agreement across builds
and repetitions, independently replayed legal moves and unchanged frozen assets.
Hash occupancy is range-checked but excluded from exact signatures. Consider
timing inconclusive if the control's pooled median ratio lies outside 0.98–1.02.
Retain the candidate only if **each** of the three candidate blocks has pooled
median parent/candidate elapsed ratio at least **1.03**, and **every** root/state
median pooled across the nine candidate observations is at least **0.98**.
These engineering thresholds are not confidence intervals, Elo evidence or
universal performance claims. No within-phase retuning if they fail.

Record every distribution, failure, host declaration and limitation; confirm
all recorded engine processes exited and immediately release the quiet window.
Archive a rejected candidate and restore parent source bytes. A passing candidate
may be retained as an execution improvement only; tactical/strength and clock
qualification remain separate. No new games, network/default promotion or schedule.
