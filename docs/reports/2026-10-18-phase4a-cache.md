# Phase 4A: UCI hash occupancy and compact cache entries

October 18, 2026. **Complete: retain telemetry and the one compact-entry change.**
The [bounded protocol](../PHASE_4A.md) fixed the comparison before candidate
measurements. Parent: `33835863d5344946dcf36e4e25af98a48bb0e63a`.
Tested engine implementation commit: `07d4d6f`.
Next: Phase 4B, Lazy SMP. The frozen Phase 3L campaign has not started.

## User-visible reporting

Standard `info depth ...` lines now include `hashfull N`, including terminal and
drawn roots. This resolves the missing UCI field behind the owner's blank Cute
Chess hash display. Native UCI output is verified; an actual Cute Chess visual
check was not performed in this phase. Use the normal rebuilt executable to see
the change; preserved GUI bundles deliberately retain their earlier behavior.

`hashfull` is integer permille: 949 means approximately 94.9%. A bounded sample
of up to 1,000 entries counts nonempty entries in the current search generation.
It may fall at the next search; zero can simply mean very sparse sampled recent
activity. It is not a hit rate or total RAM percentage. The existing eight-bit
generation can alias older entries after wrap. The protocol document cites the
original UCI specification and distinguishes this implementation's age/sample
policy from the specification's requirements.

Optional `Search Diagnostics` adds one versioned cache record per search:
entry/bucket sizes, bucket count, capacity, allocation, probes, full-key hits,
bound cutoffs, save attempts, and occupied different-key evictions. Per-node
event counters are disabled in ordinary play. Plain console diagnostics remain
plain text; ordinary UCI search diagnostics retain their protocol framing.

## Measurement and candidate

At Hash 64, the baseline uses 524,288 buckets / 2,097,152 entries. Entries occupy
24 bytes and buckets 96 bytes, so actual table storage is 48 MiB. Initial depth-5
measurements on three previously exposed benchmark roots found genuine reuse:

| Root | Cold probes / hits / cutoffs | Cold nodes | Warm nodes |
| --- | --- | ---: | ---: |
| Initial position | 2,141 / 747 / 158 | 15,297 | 2,189 |
| Existing Sicilian development root | 9,071 / 1,777 / 289 | 78,999 | 7,282 |
| Existing queen-pawn development root | 5,447 / 1,549 / 224 | 52,407 | 6,124 |

Warm hit rates were near 100%; the same final move/score was returned on each
root. Warm state also includes learned move-ordering history; the evaluator
resets, and internal-cache effects are not isolated. Node reductions cannot be
assigned solely to the transposition table. At Hash 1, there were 23 cold and
five warm occupied-key evictions; Hash 64 had none on these bounded roots.
This is evidence for reducing representation overhead, not a demonstrated
capacity bottleneck or playing-strength result.

The single candidate uses 16-byte entries: full key64, packed move/bound32,
signed score16, depth8, generation8. All square/promotion bytes, invalid-square
sentinels, four move-flag bits, score bits, and generation bits are retained.
Only positive main-search depths are stored, bounded by root depth126; each
child decrements before its single check extension. Assertions and direct tests
guard that invariant. Four-entry buckets have 64-byte size/alignment.

The old 96-byte budget divisor deliberately preserves bucket count, index mask,
collision behavior, replacement order, and cache contents at every Hash setting.
Changing the divisor to physical size would double capacity and alter search;
that is not this experiment. At Hash 64, entry storage becomes **32 MiB**, down
from **48 MiB**: **33.3% less**, with the same number of entries. This excludes
allocator/vector overhead and is not a 33.3% reduction in total process memory.
Draw/history keys, mate normalization, root restrictions, and search policies
are unchanged. Small/aligned entries still require a separate SMP-safe design.

## Validation and finite decision

- Native, scalar, and Address/UndefinedBehaviorSanitizer `make -j2 test` suites
  passed on macOS ARM64. Direct representation checks exercise every legal
  square/invalid sentinel, promotion enum, flag combination and bound; byte
  preservation, signed-score extremes, depth/generation values and wrap, and
  dynamic allocation alignment. Cache lifecycle/counters and diagnostics on/off
  exact search behavior are covered, alongside existing rules, NNUE, and UCI.
- All 20 profiler checks passed, covering malformed/corrupt counters, legality,
  capacity, output preservation, resource checks, input drift, and failure
  evidence. The profiler reconciles completed unrestricted searches with
  `probes = stores + cutoffs` and `probes <= nodes`.
- Adding telemetry alone preserved all per-iteration search signatures across
  24 parent/instrumented searches. This was a behavior check, not a speed claim.
- Across the entry-layout comparison, **72 searches / 36 matched pairs** over
  exposed opening and composed middlegame/endgame roots had identical completed
  signatures, hash occupancy, probes/hits/cutoffs/stores/replacements and legal
  PV/bestmove/ponder output. Both cold/warm state and Hash 1/64 were covered as
  declared. Only entry/bucket/allocation bytes changed.
- The diagnostics-off depth-6 comparison completed **36 exact searches**,
  including warmups and five measured repetitions per root/binary. Root median
  paired speed ratios (baseline elapsed / candidate elapsed) were **1.010283,
  0.996622, 0.996106**; geometric mean **1.000982**. Baseline medians were
  0.207480, 1.471522, and 1.164698 seconds. All duration/regression guards passed.
  The two slight root slowdowns remain included. Timing is effectively neutral,
  not evidence of a meaningful speed or Elo gain.
- Independent read-only implementation review found no remaining blocking issue.
  No full external SF19 oracle rerun or foreign-target execution is claimed;
  NNUE arithmetic is unchanged and its ordinary correctness suite passed.

Retain the candidate for its measured storage reduction and preserved behavior.
Do not add another cache-tuning subphase or promote an experimental search policy.

## Evidence and preservation

Ignored local evidence is under `results/phase4a-20261018/`: parent/source pins,
native/scalar/sanitizer logs, telemetry parity, baseline/candidate profiles,
`check_layout.py` and `layout-parity.json`, and timing inputs/results/gates.
The initial profiler required allocation above half the requested Hash; review
caught that this wrongly rejected the intended compact geometry. Version 1 tool
and tests are preserved alongside its baseline records; final validation accepts
both representations using the unchanged capacity rule. All saved baseline
outputs were rechecked with the stricter final accounting/legality checks.
An initial postprocessing attempt used the position record as a string; the
corrected saved checker passed without repeating or replacing engine searches.

Frozen executables in `build/experiments/phase4a-20261018/`:

| Executable | SHA-256 |
| --- | --- |
| `parent-chess0live` | `e7c9222c37bacecc3fa0571dd4b19c0e4fc1215dc37fadd42030f610b59b5c31` |
| `instrumented-chess0live` | `d790b89d18645ba1e85a875b9d2e62c7a0549b9f32b2e893285acd43db87b62d` |
| `candidate-chess0live` | `9caa5ccc3716ef25c289c8c43d63762c811163f2a4c7f1e8432fd9e012d8168c` |

The normal release build matches the retained candidate. The pinned network,
both stable GUI bundles (`0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017`), Phase 3L
binary/manifest and campaign inputs, and README introduction remain intact.
One active search worker was used during measurement; two build/test jobs per
configuration stayed within the recorded 50% daytime budget. No long match,
schedule, release, or strength claim was made. Local commits are ready for the
owner's manual publication.
