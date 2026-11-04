# Phase 4F.17 — NNUE accumulator reuse

Declared November 4, 2026. Parent:
`7163b1ff0f1bb52feb18daefdbe13dc89494f266` (engine unchanged from `e16ca73`).
The owner authorized this phase and confirmed LM Studio paused, AC power and
Automatic mode. No new games, default-policy promotion or automatic schedule.

## Diagnosis before implementation

Preserve normal/stable binaries, stable GUI `0.1-dev-4b8b35d`, previous campaign
evidence, README introduction and the owner's batch-tool edit. New isolated
builds/evidence use `phase4f17` directories. At most two compiler jobs, then one
active search worker; no overlapping builds/tests during profiling or timing.

Build an optimized parent with symbols. Convert all fifteen exposed roots from
`tests/data/countermove-profile.json` to the existing CPU sampler's opening
schema without changing positions/history. Fix every sampled root at depth 6,
two repetitions after the sampler's depth-5 warmups, in a 60-second sampling
window. Threads 1, Hash 64, pinned network, explicit current default preset.
Per-search timeout 20 seconds. Preserve failures and partial evidence; sampling
perturbs execution and identifies hotspots, never speed or strength.

Inspect active-search stacks independently. Proceed with one bounded reuse
candidate only if accumulator feature discovery/update remains material. Declare
its exact memory, invalidation and search integration design before measurement.
Do not eagerly evaluate unevaluated search nodes merely to populate a cache.

## Required candidate checks

Require exact feature multisets, every hidden/PSQT accumulator lane, raw output
and calibrated evaluation versus the full-refresh reference. Exercise real
reuse, siblings, skipped parents, arbitrary transitions, orientation changes,
null moves, special moves, reset, network reload/failure and aborted searches.
Keep worker state private, state restoration reversible and allocation failures
safe. Validate native, scalar, sanitizer and parallel lifecycle paths. Existing
full-refresh external oracle checks alone cannot prove the new incremental path.

Before any candidate timing, declare a finite comparison and acceptance gates.
Use all fifteen exposed roots with accepted defaults, exact completed search
parity and independent legal-PV replay. Freeze source/binary/tool identities,
preserve all attempts, and do not extend or retune from favorable cells. Report
timing limitations separately from later equal-resource strength qualification.

Confirm process cleanup and release the host when profiling/comparison ends.
Record the full decision in roadmap, handover, validation and a concise report;
validate documentation and commit locally on main. The owner handles pushes.
