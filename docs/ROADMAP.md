# Development plan and current phase

Keep this page and [handover](HANDOVER.md) current at each material checkpoint.
Progress updates should name the active phase and step, explain what was learned,
and distinguish an implemented experiment from an accepted strength improvement.
The owner handles GitHub pushes. Phase numbers are work areas, not release names.

## Current checkpoint: Phase 4F.7 tactical preparation — full comparison pending

The [protocol](experiments/phase4f7.md) and
[preparation report](reports/2026-10-25-phase4f7.md) freeze the same `a1b2331`
engine with TT Move Hints off/on; every other setting matches current defaults.
The 39-position comparison requests eight threads, Hash 64 and fresh serial
processes, with 60 seconds per configuration/position for the pending full run.

All 54 synthetic runner/auditor tests passed. Search-free readiness and the
complete one-second smoke passed independent raw replay: 78 searches, 431
iterations, 2,375 legal PV plies, 78 clean exits and 40 unchanged prepared assets.
All final best moves agreed; neither role reported mate. Three positions had
different scores/depths, retained in the report. The short smoke checks operations
and legality; it does not establish which configuration is stronger.

**Next step within 4F.7:** agree a fresh quiet window and, if during the day,
an explicit timing exception for the approximately 78-minute full comparison.
The setup is concrete and validated; no full run or schedule is active. Keep
Automatic mode and AC power, with competing inference paused for that run.
Review its tactical evidence before preparing a fresh paired strength campaign.
TT Move Hints remains off by default. The older all-on campaign remains parked;
broader platform/training/release gates remain open. Normal builds, stable GUI
`0.1-dev-4b8b35d`, the owner's batch file and README introduction are preserved.

The owner is finishing an LM Studio task and will confirm when inference is
paused. Until then, advance independent lightweight tooling. A new saved-puzzle
export command addresses the simple-tooling backlog with readable Markdown and
CSV, using existing evidence only. This does not advance or replace the pending
tactical/strength gate, and the frozen comparison inputs remain unchanged.
The exporter checkpoint is complete: 24 synthetic tests and fresh audits of
the existing readiness/smoke exports passed. See [practical instructions](TOOLS.md#read-saved-puzzle-comparisons).

## Previous checkpoint: Phase 4F.6 move hints — implemented, default off

The [report](reports/2026-10-25-phase4f6.md) records the new optional
`TT Move Hints` cache. It uses full-position-key legal move suggestions when no
legal contextual TT move is available; scores retain their existing draw-sensitive
keys and capacity. It shares the Hash reservation and existing locks, with no
hint allocation when disabled. No score cutoff or LMR exemption comes from a hint.

Native, ASan/UBSan and focused TSan checks passed, including 23 direct test groups,
three injected allocation failures and 36 new UCI cases. The independently audited
180-search screen matched all 60 parent/off pairs exactly. Enabling hints used
5.67% fewer aggregate nodes at depth 6 in both cold and warm samples; all 60 final
moves and scores matched. Seven position/cache cases used more nodes, including
one warm endgame with 33.79% more work. These are exposed, instrumented work
observations, not speed or playing-strength evidence; LM Studio could be active.

**This finite implementation checkpoint is complete; hints remain off.** Next is
**Phase 4F.7: tactical and strength qualification** for this isolated candidate.
Prepare a frozen 39-position/eight-thread, 60-second-per-position comparison
(about 78 minutes plus setup), then a fresh paired match if no reproducible serious
regression blocks it. Agree a quiet window and any required daytime exception
only after concrete preparation. No long test or schedule was started here.
The older all-on campaign remains parked; wider platform/training/release gates
remain open. Normal builds and stable GUI `0.1-dev-4b8b35d` are preserved.

## Previous checkpoint: Phase 4F.5 quiet-history bookkeeping

The [implementation report](reports/2026-10-25-phase4f5.md) records removal of
alpha-beta's per-node temporary quiet-move list. Cutoff learning uses the same
already searched move prefix, preserving update order and speculative isolation.
The 1,408-case reference test, native/sanitizer checks and 120 exact parent versus
candidate searches pass. Defaults and all-on each match their own parent; no
pruning rule or strength assumption changed.

The owner-confirmed quiet window completed in 65.02 seconds, with all 360 searches /
180 parent-candidate pairs exact and independently audited. Cold/warm aggregate
speed ratios were 1.0151/1.0080 for SEE ordering, 1.0128/1.0069 for SEE under
all-on, and 1.0052/1.0176 for default quiet-history bookkeeping. These small,
short-run observations include slower individual positions and establish neither
statistical significance nor playing strength. Automatic mode and AC power stayed
unchanged. The owner was told inference could resume immediately afterward.

**Phase 4F.5's finite checkpoint is complete**, implementation `af2abdb`.
The owner's offer of a longer quiet window does not require another benchmark:
prioritize the next search candidate over repeated microbenchmarks. LM Studio can
remain active during development/correctness work. Arrange a concrete comparison
and a new quiet window when that candidate is ready; no long campaign is active.

Next is **Phase 4F.6: history-independent TT move hints** as an opt-in search
candidate. Keep draw/history-sensitive score validity and score-table capacity
intact; investigate a separate position-key move hint within the existing Hash
reservation. A legal ordering suggestion must never become a bound or cutoff.
This is a concrete research direction, not an accepted strength improvement.
The all-on match remains parked; wider platform/training/release gates stay open.

## Previous checkpoint: Phase 4F.4 diagnosis and SEE implementation

The [bounded diagnostic](reports/2026-10-25-phase4f4.md) completed all 120
searches on the existing 15 exposed roots. Every eight-thread search used all
eight workers. Aggregate instrumented throughput scaled about 6.14 times from
one to eight threads under both default and all-on settings; this screen found
no package-specific aggregate scaling collapse. All-on evaluated SEE about
once per 2–3 nodes. Counters identify frequent work, not its CPU cost or the
cause of the earlier mate-report deficit.

The selected implementation replaces SEE's repeated slider ray walks with
precomputed bitboard rays and nearest-blocker lookup. Exchange rules, legality,
move order, search policies and defaults are unchanged. Native and sanitizer
checks pass, including 145,024 independent attack-mask comparisons. Both default
and all-on settings also match their parent exactly in 120 fixed-depth searches
with fresh/reused caches. The subsequent Phase 4F.5 window completed the bounded,
uninstrumented SEE timing comparison under two explicit presets; its small local
ratios and regressions are recorded above. The default search does not use these
optional SEE paths, so this is not a current-default or strength gain.
Keep the unstarted 512-game all-on campaign parked: no pruning promotion or
resolution of its tactical concern is established by exact implementation changes.

Broader platform/training/release work remains open. No long campaign or schedule
was started, and no v0.1 or Elo claim is made. Stable GUI `0.1-dev-4b8b35d`, owner
batch inputs, README introduction and ordinary build are preserved.

## Previous checkpoint: Phase 4F.3 tactical audit complete; package parked

The [combined-policy audit](reports/2026-10-24-phase4f3.md) completed all 39
positions / 78 searches at 60 seconds, eight threads and Hash 64. Both roles used
the same frozen `ccb66a4` executable/network. Defaults reported three positive
mates; all-on reported two. All 39 best moves agreed. Independent raw legality,
options, timing, monitoring and source checks passed.

Separate post-hoc repeats reproduced position 15: defaults reported M9 twice;
all-on reported +15.99 twice, with the same `e7d7` move. These four searches are
not pooled into the original comparison. Higher scores and deeper nominal
iterations are not strength proof, and the mate reports are not independent
forced-mate proofs.

**Keep defaults and park the unstarted 512-game campaign** while investigating
this repeatable mate-resolution deficit. No Elo verdict or default promotion is
justified. The [predeclared match protocol](experiments/phase4f3.md) and unplayed
held-out roots remain frozen. Preparation's 128 tool checks, readiness and short
smoke remain separate from the completed full tactical evidence.

Next is **Phase 4F.4: diagnose combined-package cost and SMP interactions** on
the existing exposed 15-root benchmark with matched one/eight-thread profiles.
Distinguish per-node overhead, search-tree changes and worker interactions; then
select one concrete implementation candidate. Do not tune against the 39 puzzles
or search held-out match roots for diagnosis. Package testing remains valid even
without individual component wins. Any policy promotion still needs strength
evidence; a changed candidate needs a predeclared comparison before match play.

No engine source/default changed, automatic schedule exists, or v0.1/rating is
claimed. The specific daytime exception covered the completed puzzle comparison
only. Broader platform/training/release work remains open.

## Previous checkpoint: Phase 4F.2 move-ordering efficiency

Move ordering now computes each score once per call and reuses worker-local
temporary storage. It retains the former priorities, helper root tie order,
SEE classification/counters and complete ordering before child searches.
Current-default parent/candidate comparisons matched all 120 searches exactly;
observed speed ratios were 1.055 fresh and 1.037 reused. These are bounded native
macOS implementation measurements, not a playing-strength claim. Read the
[report](reports/2026-10-24-phase4f2.md) for validation and limitations.

The owner also supplied a starting-position depth-10 comparison: all search
experiments enabled together used 21.4% fewer nodes and 21.4% less reported time,
with the same final score/move/PV. Intermediate lines differ. This observation
supports testing the combination; it does not establish strength or isolate
this phase's implementation change. The manual guide now contains a pasteable
[combined configuration](MANUAL_TESTING.md#testing-combined-search-optimizations).

Next is **Phase 4F.3: combined search optimizations versus current defaults**.
Freeze both complete configurations on the same executable/network, check their
tactical behavior, and prepare a matched-resource paired-opening strength test.
Judge the combination as a package: it may qualify even if its components did
not win individually. Component removal can investigate a failed package later;
individual wins are not prerequisites for accepting a winning combination.
Keep defaults unchanged until the package has sufficient evidence. Long tests
use the existing overnight/resource rules or a specific owner exception; no
automatic schedule or campaign is started by this checkpoint.

The build/network workflow and Phase 4F.1 remain available. Native Windows
acceptance, broader training hosts/GPU, held-out training data and release gates
remain open. Stable GUI `0.1-dev-4b8b35d` is preserved; no v0.1 or Elo is claimed.

## Previous checkpoint: Phase 4F.1 quiescence efficiency

Search development has resumed with a result-preserving optimization. Outside
check, quiescence now generates legal captures/promotions and checks quiet moves
only until it establishes a legal-move witness. This avoids discarding a fully
validated quiet list while preserving stalemate detection and all check evasions.
No pruning threshold, NNUE arithmetic or playing option default changed.

The current-default comparison passed all 120 searches with exact iteration
and final-result agreement. Observed aggregate speed ratios were 1.109 with
fresh caches and 1.121 with reused caches; these are finite native macOS
measurements, not Elo evidence. Native, scalar and sanitizer correctness checks
cover the new generator and search integration. Read the
[report](reports/2026-10-24-phase4f1.md) for scope and limitations.

Next is **Phase 4F.2: move-ordering efficiency**. Cache ordering scores and/or
stage move selection while preserving priority and deterministic tie order,
then compare against this checkpoint before accepting a change. Keep each
candidate isolated. Follow with current-baseline strength testing of promising
search options; SEE capture ordering and SEE pruning already exist, but their
historical screens do not justify default promotion with the current LMR baseline.
Do not assume that Stockfish's use of SEE makes our thresholds strength-neutral.

The first local build/network workflow is usable. Further host provisioning,
native Windows acceptance, broader training/GPU support, held-out training data
and release acceptance remain open. No long campaign was launched by this phase;
no v0.1 release or rating is claimed. Stable GUI `0.1-dev-4b8b35d` is preserved.

## Previous checkpoint: Phase 4E.7 managed network selection

[Managed selection](NETWORKS.md#managed-selection) now registers copied NNUE
files only after a fresh full oracle comparison, retains declared provenance and
complete evidence, and provides atomic select/revert/default commands. Read-only
inspection distinguishes ready, stale and unavailable entries. Changed or missing
files/evidence refuse managed launch; evaluation/source changes require a fresh
registration. The external catalog lives outside Git and never changes the pinned
network or GUI settings. A small `--eval-file PATH` engine launch option loads
exactly the requested file and advertises it to UCI clients; saved GUI options
remain explicit overrides.

The native macOS workflow registered the synthetic training export, passed all
2,057 exact evaluation comparisons, and checked managed/direct launching and
rollback with bounded UCI searches. Tool, evidence and CLI checks passed; details
are in the [report](reports/2026-10-24-phase4e7.md). Normal gameplay defaults,
owner batch settings and stable GUI `0.1-dev-4b8b35d` are preserved. This is
configuration/tooling acceptance, not a trained-network or strength promotion.
Other host managed-launch execution remains unverified.

This completes the first local inspect/train/export/select workflow. Next is
**Phase 4F.1: return to strength-focused search development**: establish a compact,
reproducible current-search baseline and choose the next isolated optimization
under the existing strength gates. Do not launch long campaigns automatically
or treat deeper search/fewer nodes as an Elo gain. Training on other hosts/GPU,
held-out data validation, native Windows acceptance, further Linux provisioning
and release acceptance remain explicit follow-ups rather than blocking all
search work. No v0.1 release or rating is claimed.

## Previous checkpoint: Phase 4E.6 local network training and export

The [training workflow](TRAINING.md) now prepares a pinned isolated runtime,
creates digest-bound recipes, trains or fine-tunes SFNNv16 weights on CPU,
exports them and automatically verifies their arithmetic. The first runtime
supports macOS 14+ ARM64; other training hosts and GPU routes fail explicitly or
remain unqualified. No engine default changes. The compatible trainer is pinned
before later incompatible architecture changes.

Real fresh training (2 steps/32 samples) and parent-weight fine-tuning (1 step/4
samples) both passed 2,057 exact native/scalar/reference comparisons. The 132
distinct tool tests and independent artifact audit passed. Synthetic labels
prove workflow correctness, not playing strength. Reports separate observed
samples from unknown/declared game history and preserve exact parent lineage.
The [report](reports/2026-10-24-phase4e6.md) records limits, measured resource use
and corrections made before acceptance. The README introduction, ordinary engine,
owner batch inputs and stable GUI bundle remain intact.

Next is **Phase 4E.7: managed network selection**, with reversible choices and
preserved compatibility/provenance records. Broader training hosts, GPU execution,
held-out dataset validation, competitive training and release/strength acceptance
remain open. This checkpoint did not launch a long campaign or release v0.1.

## Previous checkpoint: Phase 4E.5 network inspection and qualification

The [network tools](NETWORKS.md) now inspect full file identities, distinguish
recognized headers from complete arithmetic verification, and create digest-bound
provenance records. One command compares alternative SFNNv16 weights against the
separate pinned SF19 reference using scalar/native implementations and fresh
reference builds. Unknown training counts stay unknown; declared counts are
explicitly unverified. No engine network or playing default changes.

Both the pinned file and a changed-weight fixture passed all 2,057 positions;
the fixture changed 403 results and still matched the reference exactly.
An independent audit confirmed source/binary/output identities. Sixty-six native
tool checks passed; Linux ARM64 passed 65 with one missing-Make skip. Eight real
negative checks rejected invalid payloads/unsafe weights. See the
[report](reports/2026-10-24-phase4e5.md). The owner's README introduction,
batch settings, native engine and stable GUI bundle remain intact.

Next is **Phase 4E.6: reproducible training and export tooling**: pin a compatible
trainer, prepare local configurations and record data/experience provenance,
then qualify its exports. This does not promise a competitively trained network.
Managed selection, further Linux provisioning, native Windows execution and
release/strength acceptance remain open.

## Previous checkpoint: Phase 4E.4 target setup and local provisioning

`make portable` now detects the host/compiler, checks a complete C++26
compile/link route, and builds into a separate directory. All six targets have
installed-compiler discovery; Windows targets can automatically provision a
hash-pinned LLVM-MinGW bundle for five supported hosts. Compiler paths with
spaces and target-selecting symlinks are preserved. Offline cache reuse, safe
extraction, failure logs and bounded jobs are covered. See the
[guide](PORTABILITY.md#automatic-target-setup) and [report](reports/2026-10-24-phase4e4.md).

Fresh native macOS, Linux ARM64 and Windows ARM64 builds passed; the native build
passed all eight runtime checks and is byte-identical to the unchanged ordinary
GUI build. A clean Linux ARM64 VM also downloaded/prepared its Windows toolchain
and passed an ARM64 compile/link probe. Windows native setup/execution remains
unverified. Linux compiler/system-library installation and Apple's SDK remain
explicit prerequisites; the missing local RISC-V route reports that limitation
rather than substituting the host compiler.

Next is **Phase 4E.5: network inspection and qualification tooling**: identify
architecture/provenance and verify candidate files before selection, then build
the export/training workflow and recorded experience metadata. Further Linux
provisioning and native Windows acceptance remain bounded portability work.
No engine search/default change, strength gain, release or long match follows.

## Previous checkpoint: Phase 4E.3 automatic Python tool setup

The shared launcher now configures and reuses isolated, hash-pinned Python
packages for tools/tests, including automatic direct `batch_positions.py` setup
and optional Make targets. Editable batch settings and all 39 FENs are preserved.
First use, offline reconstruction, concurrent launch and damaged-environment
repair were exercised locally. macOS ARM64 and Linux ARM64 VM checks cover real
setup/run behavior; native Windows setup/process-tree cancellation remains
unverified. See the [tool guide](TOOLS.md) and [report](reports/2026-10-24-phase4e3.md).

This is external tooling work. Engine sources, search defaults, native executable,
README introduction and stable GUI bundles remain unchanged. No strength claim,
release, long puzzle/match run or schedule follows from this checkpoint.

Next is **Phase 4E.4: simpler host/target toolchain setup**: a common command
that identifies the target, diagnoses prerequisites, provisions/cache-reuses
supported toolchains where practical, and makes unavoidable SDK/OS restrictions
clear. Then scope network creation/training/export/selection with recorded
provenance. Native Windows acceptance and additional CPU backends remain open.

## Previous checkpoint: Phase 4E.2 target coverage complete within local runtime limits

All six required targets now compile. New Linux RISC-V64 builds passed all eight
runtime checks through QEMU, and the Windows x86-64 build passed them through
Wine in emulated Linux. Both also passed the existing Syzygy oracle/search
suites. Windows ARM64 builds with pinned LLVM-MinGW, but its Wine environment
stalled during bootstrap: it remains **cross-build-only**, with no native
Windows execution claimed. See the [report](reports/2026-10-24-phase4e2.md).

The verifier now distinguishes Windows **compatibility-layer** execution from
native, VM and CPU-emulated checks. Thirty-six workflow checks passed. Engine
sources/defaults, the native binary, GUI snapshots and owner batch settings are
unchanged. No strength gain or release follows, and no long campaign is running.

Next is **Phase 4E.3: one-command tooling setup**: automatic isolated dependency
setup for tools/tests/benchmarks, preserving editable settings and avoiding
system Python changes. Extend the same foundation to host/target toolchain
provisioning, then separately scope network creation, training, export
qualification, selection and provenance reporting. Native Windows execution
remains an explicit acceptance gap; it does not block unrelated tooling work.

## Previous checkpoint: Phase 4E.1 portable runtime checks complete

The first bounded Phase 4E milestone adds `make runtime-binaries`,
`make verify-runtime` and saved target-specific evidence. Test links now honor
`LDLIBS`, and the verifier rejects wrong executable architectures, mismatched
networks, skipped checks, failures, timeouts and changed inputs. Its 30 workflow
and Make checks passed. All eight runtime checks passed on macOS ARM64,
ARM64 Linux in a local VM and x86-64 Linux through emulation. Both Linux targets
also passed the separate Syzygy oracle/search suites. Windows x86-64 rebuilt,
but was not run. See the [report](reports/2026-10-24-phase4e1.md).

Engine sources and the native engine binary are unchanged; conservative LMR
stays on, ProbCut and other experimental pruning stay off. This checkpoint
adds platform correctness evidence, not a playing-strength or throughput gain.
The protected GUI bundles and owner batch settings are intact. No long test,
match or recurring job was launched.

Next is **Phase 4E.2: remaining target build/runtime coverage**, starting with
Linux RISC-V64 and Windows ARM64 toolchain gaps, plus Windows execution when a
suitable runtime is available. Then scope the reproducible network
qualification/export pathway. CPU backends require separate arithmetic and
performance evidence; trainer integration must preserve the complete pinned
architecture. Phase 4E and release acceptance are not yet complete.

## Tooling usability backlog — accepted October 24, 2026

The owner's feedback calls for a consistent **one-command workflow**, implemented
outside the engine. Phase 4E.3 delivers the first Python setup checkpoint.
Before broader training integration, scope these user-facing deliverables:

- **Tools/tests/benchmarks:** discover dependencies, create/reuse an isolated
  environment and install pinned packages automatically. Existing direct entry
  points, including `batch_positions.py`, should work without asking the user to
  create an environment or install `chess` manually. Preserve editable settings;
  test setup from a clean checkout and recovery from interrupted installs.
- **Cross-compilation:** resolve host/target, provision/cache suitable toolchains
  and SDK prerequisites, build and explain the resulting artifact with one
  command. Keep impossible/licensed/permission-dependent routes explicit; verify
  native, VM, emulator and compatibility-layer evidence separately.
- **Own networks:** simple create/train/validate/select commands, independently
  verified versioned exports, and a useful training-history/provenance report.
  Record known unique source games, positions, processed samples, steps/epochs
  and checkpoint ancestry. Do not invent an experience-game count or equate it
  with strength. Engine loading stays small; training/setup remains external.

These requirements live in [Requirements](REQUIREMENTS.md#tooling-experience--owner-feedback-october-24-2026).
They are planned work, not currently delivered automatic setup or training.

## Previous checkpoint: Phase 4D.7 attempt concluded; ProbCut remains off

Phase 4D.7 is an isolated, default-off ProbCut candidate under its
[fixed scope](experiments/phase4d7-probcut.md). It tests a bounded set of legal
captures against an elevated threshold, then includes quiet defenses in a
reduced search before accepting a heuristic cutoff. Correctness, policy
isolation and native/scalar/sanitizer checks passed. The independently audited
[60-search screen](reports/2026-10-23-phase4d7.md) found 22.05% fewer fresh-cache
nodes and 2.98% fewer reused-cache nodes, with matching fixed-depth decisions;
reused-cache time was slightly worse. One of six timed roots gained a ply.
The one-second puzzle smoke passed with 78 legal results and unchanged best
moves. The full one-thread attempt finished October 23 at 11:20 Warsaw.
Independent audit verified 78 legal results, all 39 best moves matching and
the same M7 on position 2, with 19 score differences and no additional mates.
OS logs confirm sleep during both roles, mostly the candidate; per-position
search opportunity cannot be recovered. Equal-time tactical qualification is
therefore **inconclusive**. Park ProbCut off, preserve the evidence and do not
automatically repeat or tune the exposed suite. No test or schedule is running.
Next broader work is **Phase 4E runtime/platform and network tooling**; future
ProbCut qualification requires a separately prepared sleep-aware protocol.

## Completed Phase 4D.6 checkpoint

Phase 4D.6 implements one opt-in extra-ply reduction for selected late quiet
piece moves. In parallel, the owner's October 23 120+1 game prompted a separate
retained-hash display correction and opt-in bounded clock policy. The fixed
[scope and checks](experiments/phase4d6-deep-quiet.md) keep their effects isolated.
Native/scalar/sanitizer/race checks and both finite development screens passed.
[Results](reports/2026-10-23-phase4d6.md) show exact default search parity, small
extra-reduction work savings and a time/depth tradeoff for bounded timing.
The full matched 60-second puzzle comparison finished at 08:02 Warsaw on
October 23, after 78m05s. Independent audit passed all 78 legal results and
83 source/asset checks. Both builds reported the same M7 on position 2 and
centipawn scores on the other 38; all 39 best moves matched. No additional
mate solution was found. Keep deeper reductions off and timing classic by
default; park this candidate without a long qualification match or further
tuning of the exposed suite. Next is the separate **Phase 4D.7 ProbCut**
hypothesis. No experiment or schedule is running, and no new strength claim
or default change follows from this comparison.

The fresh [512-game qualification](reports/2026-10-23-lmr-results.md) passed at
**215 wins, 175 draws, 122 losses (59.08%)**, with zero clock forfeits or audit
errors. The separate [default integration](reports/2026-10-23-lmr-default.md)
is complete and retained: conservative LMR is now enabled by default. Exact
parent parity, native/scalar/sanitizer regressions and race checks all passed.
Explicit opt-out remains available, other experimental policies stay off, and
SMP playing strength is not established. The completed **Phase 4D.6**
candidate is separate from that accepted conservative LMR integration.
Do not repeat or tune on the exposed qualification sample.

The [October 22 preparation](reports/2026-10-22-lmr-preparation.md) passed
145 workflow checks, opening-source replay and independent search-free engine
readiness. The fixed comparison is 512 games/256 fresh pairs, four active
workers, 60+0.6 and identical binaries with only LMR toggled. The authorized
daytime attempt [started at 20:03 Warsaw / 21:03 Helsinki](reports/2026-10-22-lmr-launch.md)
after preparation `548ce74` and amendment `a81c951`. All four games produced
searches and moves; startup resource checks passed. The amendment passed 81
relevant tests and fresh independent readiness. Resource limits and the original
October 23, 07:00 Helsinki cutoff stayed fixed. The final result is recorded above.
No schedule was created. Any either-role flagfall would have blocked
eligibility. This completed qualification kept engine code/defaults unchanged;
the separately recorded integration above follows it.

The [October 20 clock-boundary replay](reports/2026-10-20-clock-boundaries.md)
completed all 32 searches on time, with no reproduced historical delay.
The subsequent [real-match readiness check](reports/2026-10-20-match-readiness.md)
also passed: eight natural completions, 646 on-time searches, actual four-way
overlap and verified cleanup in 23.949 seconds. The normal release remained
byte-identical at that checkpoint. This permitted the preparation above; it did
not establish a historical clock repair or strength gain.

The October 14 and [October 18 Cute Chess feedback](reports/2026-10-18-cutechess.md)
provide useful initial GUI integration evidence and expose expensive opening
iterations and severe subsequent time pressure. The latest report records two
draws without reported errors, a partial PGN, and matching legal moves/depth-2
divides at all 122 saved positions. The intended Phase 3F snapshot's actual GUI
settings were not captured; the missing final positions limit termination checks.
Clock allocation remains a separate research priority. The owner's latest
feedback also prioritizes search efficiency: immediately after Syzygy, Phase 4D
starts with full-depth move ordering and advances through isolated,
strength-gated pruning experiments. See the
[search optimization plan](SEARCH_OPTIMIZATION_PLAN.md).

| Step | Deliverable | Status |
| --- | --- | --- |
| 2A | Measure completed and interrupted iteration time/work, with reproducible profiles | Complete: diagnostics, profiler, and checked accounting |
| 2B | Test a forecast policy that avoids starting an iteration unlikely to fit its budget | Implemented and profiled; opt-in, awaiting strength qualification |
| 2C | Evaluate selective-search and move-ordering changes independently | Initial experiments complete: both opt-in; bounded LMR loss diagnosis complete |
| 2D | Qualify promising candidates with frozen, paired-opening blitz matches | Initial time-policy and LMR screens complete, both inconclusive; further qualification deferred |
| 3A | Establish a reproducible performance baseline and identify one measured bottleneck | Complete: exact-search baseline, audited CPU sample, and bounded NNUE proposal |
| 3B | Test batched NNUE feature-column updates with exact arithmetic and search parity | Complete and retained: correctness/oracle parity, all three timing gates, all root guards passed |
| 3C | Validate the retained speedup across middlegames and endgames | Complete: middlegames qualified; endgames inconclusive under the duration floor |
| 3D | Characterize the short endgame workload before new qualification | Complete: 40 exact/legal searches; depth 12 proposed under the fixed diagnostic rule |
| 3E | Requalify endgames using the longer pawn workload | Complete: all 216 searches exact/legal; revised endgame workload qualified at 8.4–8.9% higher sampled throughput |
| 3F | Profile the updated engine and implement one justified NNUE improvement | Complete and retained: all 576 searches exact/legal; all three game-phase performance gates passed |
| 3G | Run fresh blitz strength qualification for the existing LMR experiment on the updated engine | Complete and audited: 225W/155D/132L (59.08%); six candidate clock forfeits trigger the operational-regression gate, so LMR stays off |
| 3H | Diagnose clock overruns, reproduce a defect, and validate a bounded repair | Complete bounded checkpoint: command-time accounting fixed; native/scalar/sanitizer and 52 clock probes passed; most historical flagfalls remain unexplained |
| 3I | Investigate short-clock resilience under scheduling and transport delays | Complete: same-batch match logging bias reproduced and fixed; 212 checks and 12 diagnostic controls passed; engine and historical results unchanged |
| 3J | Isolate match persistence from active protocol clocks; accept annotated manual puzzles | Implemented and checked: 230 workflow checks, native/scalar/sanitizer suites, all 39 puzzle inputs; four-game canary has one capped game, so full operational acceptance remains open |
| 3K | Add console diagnostics and complete operational validation before fresh LMR qualification | Complete: console commands validated; all four fresh operational games completed and passed independent audit with no clock/protocol/storage failures |
| 3L | Prepare a fresh held-out 512-game LMR qualification campaign; simplify console output | Complete: plain console output, signed mate checks, 256 fresh roots, 94 workflow checks, and independently audited serial readiness; 512-game campaign not started |
| 4A | Measure cache effectiveness and memory cost; add UCI hash occupancy | Complete: standard hashfull, checked cache profiler, and compact entries retained; one-third smaller table storage with exact search parity and passing timing guards |
| 4B | Add configurable Lazy SMP with a safe shared cache and measure scaling | Complete: native/scalar/sanitizer/race checks passed; 72-search screen measured 3.25× throughput and 2.09× faster depth-6 searches with four workers; default stays one worker |
| 4C | Add optional Syzygy probing with correct draw-rule semantics and missing-table fallback | Complete: pinned Fathom reader, external UCI-configured data, rule/clock/probe checks in four native build modes |
| 4D | Reduce search work while retaining or improving equal-time playing strength | 4D.1 countermove parked; historical 4D.2 failed its clock gate; 4D.3 null, 4D.4 reverse futility and 4D.5 quiescence SEE remain opt-in. Fresh 512-game LMR qualification passed at 59.08% with no forfeits. Default integration passed and conservative LMR is enabled. 4D.6 complete: full puzzle audit passed without additional mates; deeper reductions parked off. 4D.7 bounded checks passed; full attempt completed with unchanged moves/mate reports, but host sleep makes timing qualification inconclusive. ProbCut parked off; next broader work 4E |
| 4E | Broaden runtime support and add reproducible network tooling | Next broader work area after the concluded 4D.7 attempt; qualification of parked pruning remains separate |

For 2B, the first soft-target gate stopped too early in development profiles
and was rejected. Its narrower replacement forecasts against the hard deadline
while retaining classic soft stopping. It is deliberately optional: saving clock time
can also mean giving up a useful search depth. Profiles must report both saved
time and completed depth, abandoned work, scores, and moves. Only measured
playing strength can justify a claim that this improves chess strength. See the
[results and decisions](TIME_MANAGEMENT.md): the revision retained completed
depth in 32/36 development comparisons, and the same move in all 36. These
results guide the next test; they do not establish an Elo gain.

For 2C, the [selective-search plan](SELECTIVE_SEARCH.md) fixes the first reduction
policy and development checks before measurements. Time policy remains classic
on both sides of this comparison. Move ordering has a separate
experiment; the 2B validation openings were reserved for that time-policy screen.
The first candidate passed native/scalar/sanitizer checks and preserved the
default-off search signatures. Depth-5 work dropped 49.79% across the sampled
roots with matching final decisions; at equal nodes, deeper nominal searches
also changed a move and some scores/PVs. This is a research checkpoint, not
completed strength qualification.
The eight-game operational smoke scored 2W/2D/4L for LMR with no protocol errors,
time forfeits, or truncations. LMR stays off by default; the unfavorable small
sample establishes no strength margin in either direction.
The separate [SEE capture-ordering experiment](MOVE_ORDERING.md) passed native,
scalar, and sanitizer checks with LMR disabled and classic timing. It preserved
all 24 default-mode signatures. Its depth-5 comparisons used 4.72% fewer nodes
with matching moves/scores/PVs; equal-node searches gained one depth on one
root and lost one on another. The eight-game smoke scored 2W/4D/2L with no
operational failures. MVV-LVA remains the default.

The [bounded LMR loss diagnosis](reports/2026-10-14-lmr-losses.md) used the frozen
LMR executable. All eight selected roots gave the same off/on best move, and
40 common-depth scores/PVs matched. No reduction parameter changed; this finite
post-hoc check does not establish that reductions are harmless.

The initial Phase 2C experiment checkpoint is complete. **Phase 2D has completed
its first two screens**, without promoting an experimental default. Its
[first time-policy screen](reports/2026-10-15-phase2d-time-policy.md) completed
all 32 opening pairs / 64 games at 60+0.6 with one worker. It ran October 15,
14:24–17:18 Helsinki, under the owner's one-run daytime exception, from preparation
commit `2cf55f7`. Forecast scored **14W/43D/7L, 35.5/64 points (55.47%)**. The
independent audit passed with no exclusions, operational failures, or artifact
drift. Its conditional 95% pair-score interval is **31.46–79.48%**: the predeclared
decision is **inconclusive**, so classic remains default and forecast remains
experimental. A favorable point estimate does not establish a strength gain.
The raw completed campaign is `results/phase2d-time-policy-20261015/`.

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) completed all
64 fresh opening pairs / 128 games at 60+0.6 with classic timing. It ran from
October 15 23:00:08 to October 16 05:41:20 Helsinki, inside the ordinary night
window, from preparation commit `842ee41`. LMR scored **35W/82D/11L,
76/128 points (59.375%)**, with no exclusions, operational failures, or artifact
drift. Independent audit verified 17,175 legal plies and 15,191 searches.
The conditional 95% pair-score interval is **42.40–76.35%**: the predeclared
result is **inconclusive**, so LMR stays off. The favorable score does not
establish strength or equivalence. Raw evidence is
`results/phase2d-lmr-20261015/`; the job and its sleep assertion have ended.

**Phase 3A is complete.** The [result report](reports/2026-10-16-phase3a-baseline.md)
records a frozen default release baseline and optimized symbol build, all 12
original development histories, and the ordinary 50% daytime budget. All 192
same-binary depth-5 searches matched exactly; median paired ratio was 0.998546,
with observed MAD 0.008123. Another 48 searches verified the symbol build's
search equivalence. All reported moves/PVs passed independent legal replay.

A separate 120-second CPU sample contained 7,413 observations inside search
frames. NNUE accounted for 85.04%, including 58.69% in accumulator update and
26.10% in inference. These nested shares overlap. Both independent aggregations
agree; the raw stacks and audits are retained in `results/phase3a-20261016/`.
The profile covers shallow opening search and omits the active clock path.
No engine optimization, speed gain, or strength gain was established.

**Phase 3B is complete and retained.** The [result](reports/2026-10-16-phase3b-nnue-batching.md)
records streaming batches of eight feature-column views and 32-lane hidden tiles.
Features, inference, search, and default policies are unchanged. Native, scalar,
and sanitizer suites passed, including 360 independent arithmetic transitions;
the full 2,057-position SF19 oracle retained exact corpus/stage/output digests.
All 576 benchmark searches matched exactly and replayed legally. The three
declared timing medians were **1.078081, 1.079836, 1.083612**, above the 1.03
gate; all 24 pooled root/depth medians exceeded the 0.98 guard. This is roughly
8% higher sampled opening-search throughput, not a strength improvement.

**Phase 3C is complete.** The [result](reports/2026-10-16-phase3c-gamephases.md)
records all 432 exact/legal searches on 12 original composed roots. Both
middlegame runs passed the frozen gates, at **1.087243 and 1.088055** median
ratios. Endgame runs were favorable, but the sparse pawn root's 30–32 ms searches
failed the 50 ms duration floor; endgame and combined qualification remain
**inconclusive**. Nothing was omitted or retuned. The six-run campaign completed
in 844.997 seconds under the normal daytime budget, with no engine changes.

**Phase 3D is complete.** The [report](reports/2026-10-17-phase3d-workload.md)
records all 40 exact/legal baseline-only searches at depths 8–12. Depth 12
meets the fixed proposal rule, with 329.881/322.562 ms role medians, ratio
0.999090 and MAD 0.028507. Depth 10's timing instability remains recorded.
Three pairs and a near-limit MAD do not establish lasting repeatability.
The campaign completed in 7.441256 seconds within the normal daytime budget;
engine code, binaries, defaults, and Phase 3C's decision are unchanged.

**Phase 3E is complete.** The [result](reports/2026-10-17-phase3e-endgames.md)
qualified performance on the revised six-root endgame sample: complete-round
ratios **1.089113 / 1.084243**, all 216 exact/legal searches, all control,
duration, and root guards passed. The 353.663-second campaign used one active
worker under the ordinary daytime budget. Two individual candidate slowdowns,
control outliers, and upward absolute-time drift remain in the report. No old
timings were pooled; Phase 3C's earlier decision remains unchanged.

**Phase 3F is complete and retained.** The [report](reports/2026-10-17-phase3f-dense.md)
records fresh all-phase profiles, a committed isolated dense-kernel hypothesis,
and independent arithmetic/native/scalar/sanitizer/full-oracle checks. Four
outputs now share each activation vector in the NEON multi-output layers. All
576 performance searches matched exactly and replayed legally; every gate passed.
Paired throughput gains versus retained Phase 3B were **19.6% opening,
19.7–21.4% middlegame, and 32.4–39.5% endgame**. Four slowdowns and substantial
absolute-time drift remain included. No rating, release, or search-default change.

**Phase 3G is complete and audited.** The [result report](reports/2026-10-18-phase3g-lmr.md)
records all 256 pairs / 512 games at 60+0.6, with LMR on versus off in the same
qualified Phase 3F engine. The one authorized daytime attempt ran October 18,
08:54–15:12 Helsinki, using four workers under the normal 50% resource budget.
All 512 games passed independent replay, clock, option, and integrity checks.
LMR-on scored **225W/155D/132L, 302.5/512 points (59.08%)**, with conditional
95% pair-score bounds **50.59–67.57%**. This clears the numerical screen, but
**six candidate clock forfeits take precedence** under the frozen protocol:
the decision is **operational regression; keep LMR off**. Seven baseline clock
forfeits also occurred, so the evidence does not isolate LMR as their cause.

**Phase 3H's bounded checkpoint is complete.** The [result report](reports/2026-10-18-phase3h-clocks.md)
records a reproduced accounting defect: preparation and worker dispatch after
`go` were uncharged. Search now uses the command's original monotonic receipt.
Native, scalar, sanitizer, deterministic expired-receipt, and UCI regression checks
passed. All 52 fresh-table probes (13 exposed histories, both LMR modes, both
executables) were legal and on time. The frozen baseline also passed, so these
probes do not reproduce the historical losses or establish improved reliability.
One historical case is consistent with the repaired gap; the other 12 remain
unexplained by available timestamps. An artificial process pause demonstrated
that command accounting cannot prevent a loss when the host suspends the engine.

**Phase 3I is complete.** The [report](reports/2026-10-18-phase3i-receipt.md)
records a deterministic match-runner defect: slow logging inflated time charged
to a bestmove already received in the same input batch. Callback-entry timing
fixes it while preserving parser and audit behavior. All 212 workflow checks
passed. Twelve live controls distinguished consumer-only sleep from engine
suspension; no historical clock loss is reclassified. Engine code is unchanged.

**Phase 3J's implementation checkpoint is complete.** The
[report](reports/2026-10-18-phase3j-persistence-puzzles.md) records bounded FIFO
protocol writers and off-loop game/campaign persistence, with failure and
cancellation tests. All 230 workflow checks passed. The owner's annotated puzzle
input is supported, including four-field records; all 39 supplied positions
passed independent legal-move and exact-search comparisons. A 60-second example
found Qxf6+ without proving mate in seven. Native/scalar/sanitizer suites passed.

The declared four-game slow-writer canary finished with two checkmates, one
threefold draw, and one 128-ply truncation. The cap prevents full operational
acceptance; it is not a draw or a replacement sample. No clock, protocol, or
storage failures were recorded. See the report for independent audit coverage.
**Phase 3K is complete:** the [report](reports/2026-10-18-phase3k-console-operations.md)
records native/scalar/sanitizer validation, 93 independent display/perft positions,
and 36 exact-search comparisons for the new console commands. The fresh four-game
LMR-on/off operational screen finished in 17.135 seconds with three repetition
draws and one insufficient-material draw. Independent replay validated all 386
on-time search replies, legal games/PVs/ponders, clocks, options, source/asset
pins, resource admissions, and process closure. No clock, protocol, persistence,
stderr, or cap failure occurred. This is a bounded operational pass, not strength
or general reliability qualification; the Phase 3J capped game stays unchanged.

**Phase 3L preparation is complete:** the [report](reports/2026-10-18-phase3l-preparation.md)
records plain console output and signed mate checks, 256 fresh opening roots
against 851 excluded roots, frozen inputs, 94 passing workflow checks, and
independently audited serial readiness. The [fixed protocol](PHASE_3L.md) retains
512 games and the earlier decision thresholds. Zero held-out searches were sent;
no long campaign or schedule is active. Both GUI bundles and all search defaults
remain unchanged. The frozen match can run separately under its
overnight policy without blocking those development areas.

**Phase 4A is complete:** [measurements and decision](reports/2026-10-18-phase4a-cache.md)
confirm working cache reuse and retain one smaller representation with unchanged
capacity/search semantics. Standard UCI hash occupancy is now reported. Native,
scalar, sanitizer, 20 profiler checks, 72 cache-profile searches, and 36 timed
searches passed their applicable gates. Memory fell by one third; timing was
effectively neutral, and no strength gain is claimed.

**Phase 4B is complete:** [parallel-search results](reports/2026-10-18-phase4b-smp.md)
retain configurable 1–64 workers with shared cache/network memory, private search
state, and coordinated cancellation/limits. Native, scalar, ASan/UBSan, and
ThreadSanitizer checks passed. All 24 one-worker parent/candidate searches matched
exactly; a small possible single-worker timing cost remains recorded. The
independently audited 72-search scaling screen found useful gains with two/four
workers; four workers completed one additional depth in all nine timed pairs.
No SMP match strength gain is established. **Phase 4C is complete**: optional
Syzygy is implemented and tested; see [the checkpoint report](reports/2026-10-18-phase4c-syzygy.md).
No further cache/SMP tuning subphase is required for this checkpoint.

The owner requested earlier search optimizations on October 18, supplying a
[depth-10 comparison](reports/2026-10-18-depth-feedback.md) with about 682 times
more chess0live nodes. This is a work-count observation, not strength evidence. **Phase 4D
follows 4C directly**, beginning with one full-depth ordering candidate before
new pruning. The [bounded plan](SEARCH_OPTIMIZATION_PLAN.md) sequences existing
LMR qualification, verified null-move pruning, reverse futility, and separate
quiescence/late-quiet hypotheses. Each needs correctness, clock, and equal-time
strength evidence; neither deeper search nor fewer nodes permits default
promotion. Existing LMR remains off, and no new match is launched by this plan.

LMR confirmation is planned separately in 4D; forecast/SEE qualification remains
deferred, not passed. Do not extend or pool the completed Phase 2D and Phase 3G samples. Parallel
strength qualification, broader runtime validation, and release acceptance remain open.

**Phase 4D.1 is complete:** the [countermove report](reports/2026-10-18-phase4d-countermove.md)
records all four build-mode correctness checks, 180 exact parent/off searches,
and 360 legal cold/warm on/off searches. The candidate changed no pruning or
depth rules but produced no convincing broad efficiency gain: cold total nodes
-0.19%, warm +3.78%, with higher aggregate depth-6 elapsed time. All fixed-depth
final scores/moves agreed; intermediate warm differences remain recorded.
It stays opt-in and further tuning/strength qualification is parked. No default
or Elo improvement is claimed. The **4D.2** current-engine LMR result and
separate **4D.3** checkpoint are recorded below. Internal
iterative deepening, distinct futility variants, and ProbCut are recorded in
the search plan following the owner's additional feedback.

**Phase 4D.2 preparation:** the [fixed protocol](PHASE_4D2.md) compares the same
current executable with LMR on/off over 1,024 games (512 reversed-color pairs),
using eight workers, fresh opening histories and the ordinary overnight limit.
Fresh openings, an eight-worker clock/cancellation check and independent serial
readiness have passed. LMR remains off by default. The
[checkpoint record](reports/2026-10-18-phase4d2-preparation.md) records validation
and launch status. One complete audited result is required before a default
decision; incomplete or inconclusive evidence does not block 4D.3 indefinitely.
The campaign launched October 18 at **23:13:40 Helsinki**, after 90 passing
workflow checks and local commit `d376524`; cutoff is October 19 **07:00**.
The [complete result](reports/2026-10-19-phase4d2-results.md) was audited after
all 1,024 games finished at 05:34:17 Helsinki: 458W/299D/267L, 59.3262%,
conditional 95% score interval 53.3242–65.3282%. Nineteen candidate flagfalls
(two adjudicated draws) and 65 baseline flagfalls fail the absolute reliability
gate. Keep LMR off; no default promotion or new campaign follows. Diagnose
clock behavior before another qualification; do not extend or pool this sample.

**Phase 4D.3 is complete:** the [null-move report](reports/2026-10-18-phase4d3-null-move.md)
records one independently implemented candidate, disabled by default, with
reduced legal-move verification and restrictive draw/endgame safeguards.
Native/scalar/ASan+UBSan/ThreadSanitizer checks passed, including 76 new UCI
cases per build, direct API interruption/worker checks, and incremental state
tests. The instrumented UCI harness needed a longer activation-check timeout;
that failure and the separate passing retry are retained.

All 12 parent/off screen searches were exact. The six off/on pairs retained
every per-depth score/PV and final move, while total cold nodes fell 16.47% and
warm nodes rose 6.08%. This mixed three-root sample does not qualify strength
or speed. The concurrent match prevents timing interpretation. No repeated
tuning or new long campaign follows: keep null pruning off. Its successor is
the **4D.4 reverse-futility checkpoint below**. The
completed LMR audit above is separate and does not qualify either candidate.

**Phase 4D.4 is complete**, implementation `9ad2fe9`: the
[report](reports/2026-10-19-phase4d4-reverse-futility.md) records one default-off
shallow static-pruning candidate, native/scalar/ASan+UBSan/TSan checks and an
independently audited 60-search profile. All 12 parent/off pairs matched exactly.
Depth-6 total nodes fell 12.72% with fresh caches and 1.53% with reused caches;
observed elapsed time fell 11.51% fresh but rose 2.28% reused. One of six timed
roots completed one extra depth. Final moves matched and no common-depth
score/PV differences occurred. This single exposed repetition qualifies neither
speed nor playing strength. Keep reverse futility off and do not retune it here.

The [read-only clock diagnosis](reports/2026-10-19-clock-diagnosis.md) checked
all 84 saved flagfalls. Charged time often extends beyond the engine-reported
interval; the existing logs cannot isolate transport, scheduling and engine
bookkeeping costs. No clock policy or qualification result changed. Before
another match qualification, use one short predeclared instrumented diagnostic.
That checkpoint led to **4D.5 quiescence work reduction** below. Delta pruning
remains a separate unimplemented hypothesis.

**Phase 4D.5 implementation, bounded checks and full puzzle comparison are
complete; the candidate remains experimental and off by default.** The
[report](reports/2026-10-20-phase4d5-qsearch-see.md) records one isolated,
default-off SEE capture filter. Native/scalar/ASan+UBSan/TSan tests passed,
including 98 UCI cases per build. An independent raw audit passed all 60 profile
searches and 12 exact parent/off pairs. Fresh-cache nodes fell 11.62%, reused
nodes 1.58%; one of six 500-ms roots reached an extra depth. Final moves matched,
but starting-position score/PV differences remain recorded. Timing is one
exposed repetition, not speed or strength qualification.

The matched 1-second smoke completed all 39 owner puzzles per build without
errors or bestmove changes. Neither reported a positive mate; three centipawn
scores differed. The separate required **60-second comparison also completed**:
39 positions per frozen build, one worker, Hash 64, October 20 15:41–16:59
Helsinki, under the owner's explicit daytime exception. Independent audit
verified all 78 legal best moves and unchanged inputs. Both reported only M7
on position 2; the other 38 ended with centipawn scores. All best moves matched;
only position 29's printed score changed (+9.16 to +9.59). No mate gains,
losses or distance changes were observed. This is exposed puzzle evidence,
not a strength qualification or proof that reported mates are correct.
No recurring schedule or further match was created.

The subsequent short clock-boundary diagnostic completed all 32 replies on
time without reproducing historical delay. Four-worker real-match readiness
then passed, followed by the fresh 512-game LMR qualification and separate
default integration recorded above. Broader 4D.6 reductions completed their
finite checkpoint and remain off; the current isolated hypothesis is 4D.7.
Do not tune these exposed samples or combine pruning candidates.

Small daytime correctness/profiling checks use the 50% resource budget. Long
campaigns run during 23:00–07:00 Europe/Helsinki at 80%, with a manual override
available. Preparing a command does not start it or create a recurring schedule.
Do not describe a pending campaign as active or completed.

## Broader roadmap and bounded checkpoints

October 19 auxiliary tooling: a small UCI batch runner with embedded FENs supports
the owner's manual puzzle benchmark workflow, with editable engine settings and
printed per-position scores. Short workflow checks are separate from
strength qualification; this addition did not itself advance an engine phase.
At the owner's request, material search/evaluation checkpoints will also include
matched before/after puzzle comparisons under the [validation rules](VALIDATION.md#use-for-development-progress).
The first full 60-second baseline and matched candidate comparison completed
in Phase 4D.5, as recorded above.

The owner asked on October 18 to avoid repeatedly refining a single research
phase while major engine capabilities remain. Phase 3L has a finite exit:
tested plain-text diagnostics, reproducible unsearched inputs, frozen campaign
pins, passing launcher/auditor checks, and serial readiness. It does not include
new search tuning, repeated operational canaries, another clock investigation,
or automatic campaign/confirmation launches. A future result gets one recorded
decision under its fixed rules. Inconclusive evidence is recorded and shelved;
it does not indefinitely block unrelated engine development.

| Work area | Existing foundation | Next concrete deliverable |
| --- | --- | --- |
| 4A: search cache efficiency — complete | Measured cache reuse; compact 16-byte entries, unchanged capacity/draw-aware bounds, UCI occupancy, optional detailed counters | Retained one-third entry-storage reduction with exact parity and passing regression guards; no further tuning required for this checkpoint |
| 4B: Lazy SMP | Implemented configurable workers, shared synchronized cache, private search state, coordinated limits, and audited scaling screen | Complete bounded implementation/scaling checkpoint; broader worker/platform execution and strength qualification remain separate |
| 4C: Syzygy — complete | Pinned Fathom, independent adapter/search integration, external table paths and UCI hits; 140 oracle roots plus lifecycle/clock checks | Bounded three-/four-piece checkpoint complete; larger-table and foreign runtime execution remain unverified |
| 4D: strength-gated search efficiency | PVS, shared TT and qualified conservative LMR enabled; other pruning experiments remain optional | 4D.6 parked off; 4D.7 finite attempt concluded with timing qualification inconclusive after host sleep. ProbCut remains off; 4E next |
| 4E: broader runtime support and network tooling | 4E.7 bounded workflow complete: automatic build/tool setup, inspect/qualify/train/export/select; all six engine targets have prior build evidence | Training on other hosts/GPU, dataset validation, native Windows acceptance and further Linux provisioning remain follow-ups |
| 4F: strength-focused search development | Quiescence/ordering improvements; combined-policy tactical audit and worker diagnosis; exact SEE and quiet-history implementations; optional position-key move hints | 4F.7 frozen tactical preparation and 78-search smoke passed; full comparison awaits quiet window/timing authorization; hints remain off and all-on stays parked |

Freeze qualification binaries separately so later engine development cannot
change an ongoing comparison. The normal build may advance after a frozen
campaign is prepared. Each work area has a documented acceptance decision;
failed or inconclusive experiments do not become default optimizations.
Strength-gated search optimization, broader execution, parallel strength
qualification, and release acceptance remain unfinished. Parallel search and
optional tablebase probing are now implemented.

Every phase preserves the frozen GUI bundle `0.1-dev-4b8b35d`, the NNUE oracle,
and core rule/UCI checks. Release 0.1 only after its [acceptance gates](VALIDATION.md)
are satisfied. Decisively exceeding Stockfish 19 remains a research objective;
none of these phase labels implies that it has been achieved.
