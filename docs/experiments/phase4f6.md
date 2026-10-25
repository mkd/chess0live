# Phase 4F.6 — position-key move hints

Declared October 25, 2026, before implementation or candidate searches.
Parent checkout: `a96c9a7`; parent engine source: `af2abdb`.
The owner authorized the next development phase. LM Studio may remain active;
this checkpoint measures correctness and fixed search work, not speed or Elo.

## One isolated search hypothesis

Expose `TT Move Hints`, a check option defaulting to false, and
`SearchLimits::tt_move_hints`. When ordinary positive-depth search has no legal
contextual TT move, use a full-position-key cached move to order the existing
legal list. Match the entire Move including promotion and flags. A hint never
supplies a score, bound, cutoff, draw decision or search-depth exemption. Keep
the existing contextual TT move separate for LMR eligibility. Order changes may
change selective search results; this is not an exact-result optimization when on.

Use a separate 16-byte entry per existing score bucket, shared across workers.
Keep the full score keys (reversible history and halfmove clock), four 16-byte
score entries per 64-byte bucket, bucket count/index mask, replacement rules
and score capacity unchanged. Physical score-plus-hint storage is at most 80
bytes per bucket inside the existing 96-byte Hash reservation. Allocate hints
only when enabled; keep allocation failure safe. Reuse striped locks without
nested locking or escaping mutable references. Empty entries must not match a
zero key. The initial replacement policy is simple direct replacement by the
most recently completed legal best move; no tuning of depths or ages.

Probe/store only in ordinary main search; exclude quiescence, null, verification
and ProbCut subtrees, and restricted root nodes (including tablebase root
restrictions). Store only after a completed ordinary node, never a stopped
node or a direct speculative cutoff. Descendants of restricted roots remain
ordinary unrestricted nodes. Clear hints on new game/Clear Hash, hash resize,
thread changes and search-policy changes; disabling releases their allocation.
Keep UCI hashfull and existing score-cache diagnostic meanings unchanged. Add
separate optional hint probes, hits, legal matches and stores summed across
workers. Feature off must preserve parent work/results.

## Bounded correctness and integration

Build separately under `build/phase4f6-native/`, `build/phase4f6-asan/` and, for
shared-state checks, `build/phase4f6-tsan/`. Preserve normal builds, stable GUI
`0.1-dev-4b8b35d`, owner batch settings/FENs and the exact README introduction.
Use at most two compiler jobs and serial checks, one search worker except
bounded four-worker lifecycle/race checks. Inspect the local resource allowance.

Tests must cover full keys/collisions/empty state, memory and score capacity,
legal/special/stale moves, contextual precedence, unchanged draw-sensitive
score keys, ordering-only behavior and LMR separation, speculative isolation,
restricted roots, terminal/draw state, cancellation and option/table/worker
lifecycle. Run native core/NNUE/search checks, focused ASan/UBSan and TSan, and
bounded UCI checks. A sanitizer unavailable on this host is recorded explicitly.
Validate the new profiler with synthetic failures before real searches.

## One finite development comparison

Use all 15 exposed roots in `tests/data/countermove-profile.json`, depth 6,
one worker, Hash 64, two repetitions, cold/warm caches and rotating configuration
order reversed on the second repetition. Three configurations are frozen parent
defaults, candidate hints off and candidate hints on: 180 searches. Use a fresh
process for each configuration/root/repetition and consecutive cold/warm
searches within it (90 sessions), one active engine at a time. Explicitly keep
LMR on, other experimental policies off, classic timing, overhead 20 ms,
Ponder off and Syzygy off. Enable diagnostics consistently for branch evidence;
these are instrumented work observations, not timing comparisons.

Parent/off must agree exactly on nodes, scores, depths, PVs, final moves,
hash occupancy and existing deterministic work counters. On/off may differ;
check legal outputs, active hint counters, complete accounting and record every
root's nodes/moves/scores without choosing a favorable subset. No held-out
match root or 39-puzzle position is selected for development or tuned.

Pin binary/network/corpus/protocol/tool/source identities and retain commands,
full output, PIDs, zero exits, readiness barriers and wall/monotonic receipts.
Use a 300-second total cap and ten-second search watchdog. Reject existing
outputs, retain partial failures, and do not retry to replace adverse results.
Independently audit the saved comparison. LM Studio may affect elapsed times;
do not report timing ratios as speed evidence from this run.

Parent binary: `build/phase4f5-native/chess0live`, SHA-256
`9c89933b9000bba3b5a77d8981d7fcf7094987e2a45d624e65ec9bc6ed3987d2`.
Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

## Exit and subsequent qualification

Commit tested implementation, document negative or inconclusive observations,
and leave hints off by default. Finish this finite checkpoint without repeatedly
tuning the exposed corpus. A useful candidate can then have a separately frozen
39-position/eight-worker tactical comparison and fresh strength-match protocol.
Prepare those concrete runs before requesting a quiet host or any required
daytime exception; this phase does not launch a long test or create a schedule.
The older all-on campaign remains parked and its tactical concern unresolved.
