# Phase 4F.5 — exact quiet-history bookkeeping

Declared October 25, 2026, before candidate searches. Parent: `4815bd2`.
This is one implementation change on the accepted default search, not a new
pruning policy or a strength qualification. The owner may keep LM Studio
running during development and correctness checks.

## Candidate and invariants

Remove alphabeta's per-node `searched_quiets` allocation. At an ordinary quiet
beta cutoff, the already ordered moves strictly before the cutoff are exactly
the completed earlier searches. Filter that prefix using the former rule
(neither capture nor promotion), then apply the same negative history bonuses
in the same order. Reward the cutoff move first, preserve killer/countermove
updates, and retain the learning prohibition in speculative modes. Descendant
searches and re-searches can change history but cannot alter this node's local
move vector. No new fixed move limit, per-ply storage, policy or UCI option.

The independent reference test must reconstruct the former collected list and
compare the actual learning path, including histories changed by descendants,
saturation, mixed tactical/quiet prefixes, castling, promotions, repeated
synthetic move entries and all speculative modes. Native/sanitizer search,
ordering, interruption and SMP checks protect integration. One-worker fixed
limits must preserve nodes, scores, PVs, final moves and diagnostics apart from
timing. Multiworker scheduling is nondeterministic; require legal lifecycle and
resource accounting rather than identical SMP trees.

## Correctness before timing

Build separately in `build/phase4f5-native/` and `build/phase4f5-asan/` with the
existing compiler/options. Preserve the ordinary engine, stable GUI
`0.1-dev-4b8b35d`, owner batch inputs and README introduction. Use two compiler
jobs at most and serial short test suites. No full puzzle or match run is part
of this checkpoint; long-test rules and the parked all-on campaign are unchanged.

Use all 15 exposed roots in `tests/data/countermove-profile.json` for a bounded
parent/candidate check at depth 6, one worker, Hash 64, defaults/all-on, and
fresh/reused caches. Do not infer speed while concurrent inference may be active.
No positions from the 39-puzzle audit or held-out match corpus are selected or
tuned. Preserve partial failures; do not silently replace a completed result.

## One coordinated performance window

Only after implementation, tests and a concrete runner are ready, ask the owner
to pause LM Studio inference briefly; the model may remain resident. Keep AC
power and Automatic mode unchanged and record the new confirmation. No speed
run starts on an assumed quiet host. Tell the owner immediately when the window
ends. No build, test or other engine search runs alongside this comparison.

Use the existing exact-result profiler with explicit immutable presets. Each
comparison includes all 15 roots, depth 6, two repetitions, both fresh/reused
caches, alternating build order: 120 searches / 60 pairs. One active search
worker and two resident engines; Hash 64, pinned network, LMR on, diagnostics,
ponder and tablebases off. All-on means the existing eight-option recipe.

Run these three comparisons once, in this order, under a combined 300-second
cap and ten-second per-search watchdog:

1. Phase 4F.4 SEE-only implementation: frozen `ccb66a4` versus `4815bd2`,
   preset `see-ordering` (only Capture Ordering differs from current defaults).
2. The same two executables with preset `all-on`.
3. This phase's history-bookkeeping candidate versus `4815bd2`, preset `default`.

The two old binary SHA-256 values are respectively
`5714cd8ab2e0a4a721922fa5e02881329e8d865bff87829d8c20fb82302aa947` and
`9389b864f0b6c22d9f2b7c288ee6323ebee17c23547ba26d1f782afaff01e031`.
Pin the tested new candidate and all current tooling before requesting the
window. Each child run receives the remaining total deadline. Stop on failure;
preserve completed/partial reports. No automatic replacement or retry.

Retain and independently replay commands, outputs, PV/best/ponder legality,
exact iteration work, process identities/exits, settings, clocks and source
identities. Both clocks must agree; a quiet-host assertion is not continuous
thermal/GPU telemetry. Short reused-cache samples can be noisy. Report cold and
warm aggregate ratios, individual regressions and duration limitations; do not
select a favorable subset or advertise statistical significance or Elo.

If exact correctness fails, repair the implementation and keep failed evidence.
If timing fails or remains mixed, record it as such and keep performance
qualification pending; do not invent a strength gain. No playing default changes
or policy promotion is authorized by this implementation screen. After this
finite checkpoint, return to search-policy research under its own fresh protocol
rather than repeatedly tuning these exposed roots.
