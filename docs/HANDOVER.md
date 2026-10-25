# Developer and agent handover

## Accepted direction

Read [requirements](REQUIREMENTS.md) first. The user completed the interview:
original engine, strength over elegance, GPL-3.0-or-later, pinned SF19 network,
no own initial network training, desktop/laptop focus, M5 Pro primary, local-only
compute, and tested commits directly to main. The owner now handles GitHub pushes
manually; do not retry authentication or publishing from an agent session.

Preserve the owner's README introduction before `## Build and run` exactly.
Limit future README edits to practical build, run, test, configuration, extension,
and contribution instructions. Keep phase progress, match reports, and competitive
ambitions in the roadmap and other project docs.

No unresolved product decision blocks the baseline. Nighttime is 23:00–07:00
Europe/Helsinki at 80%; daytime 50%; the owner can override the budget. Blitz is
the first match-testing focus. Do not reuse any of the owner's earlier engines.

## Development sequence

1. Establish legal bitboard moves and reversible state; pass perft and edge cases.
2. Independently implement the pinned SF19 file format, all feature families,
   scalar integer inference, and incremental state. Prove oracle parity.
3. Integrate bounded search and asynchronous UCI; pass lifecycle and rule tests.
4. Record benchmarks and build/platform evidence. Release 0.1 only when all its
   claimed capabilities have evidence; never claim the long-term strength goal.
5. Optimize ARM64, extend portable builds, measure search improvements, and add
   parallelism with correctness and match evidence. Training integration follows.

## Current checkpoint: Phase 4F.5 quiet-history bookkeeping

Read the [protocol](experiments/phase4f5.md) and
[report](reports/2026-10-25-phase4f5.md). `learn_quiet_cutoff` replaces the
collected `searched_quiets` vector with the current node's ordered move prefix.
`move_number` increments only after a completed child/re-search and restoration;
therefore `move_number - 1` is the cutoff index, excluded from the penalty list.
Keep the ordinary-mode/quiet guard, countermove/killer updates, winner reward,
then prior quiet penalties in that exact order. Read history after descendants.
If future pruning skips entries, this prefix no longer equals the searched set:
track the searched subset rather than silently penalizing unsearched moves.

The private reference test includes search.cpp and links other objects only,
with its generated dependency file loaded by Make. `make test-search` includes
it; `make test-history-prefix-search` runs it alone. All 1,408 cases pass, along
with native and focused sanitizer search suites. Independent replay of the
120-search default/all-on correctness comparison verified 60 exact pairs,
720 iterations / 3,108 legal PV plies, commands, barriers, exits and 27 pins.
Timing from that check is unqualified because LM Studio may have been active.

The existing exact-result profiler now takes immutable per-call presets:
`default`, `see-ordering`, `all-on`. Both builds receive the same selected preset.
No global settings are mutated. Reports retain PIDs, exit codes, consumed
transcripts and strict post-search readiness barriers. All 28 synthetic checks
pass. Do not apply this exact-result comparator to a changed search policy and
interpret a signature mismatch as merely slower search.

Builds: `build/phase4f5-native/` and `build/phase4f5-asan/`. Evidence and the
prepared bounded three-comparison window are under `results/phase4f5-20261025/`.
The owner must confirm a new LM Studio pause before timing; no pause is needed
for other work. The earlier SEE source/binary and this new candidate are compared
separately, so the effects are not conflated. The combined cap is 300 seconds;
no automatic repeat, long campaign or schedule is authorized.

Next: Phase 4F.6 may investigate a separate position-key TT move-hint cache inside
the current Hash reservation, leaving full context keys and score-entry capacity
unchanged. It is an opt-in ordering experiment until strength evidence supports
it. Do not reuse hints as scores, violate speculative isolation, or alter stored
move flags without legal-list matching. Preserve the parked all-on campaign,
owner batch settings, exact README intro and stable GUI `0.1-dev-4b8b35d`.

## Previous checkpoint: Phase 4F.4 diagnosis and SEE implementation

Read the [declared diagnostic protocol](experiments/phase4f4.md) and
[report](reports/2026-10-25-phase4f4.md). The initial screen used the frozen
`ccb66a4` engine under both configurations, not the subsequent implementation
candidate. All 120 searches completed; all eight workers contributed in all
60 eight-thread searches, with about 6.14x aggregate scaling under both policies.
This is instrumented exposed-root evidence, not a pure component-cost or strength
measurement. The Phase 4F.3 mate-report concern remains unresolved and its
unstarted 512-game campaign remains parked.

`ExchangeBoard::attackers` now uses a constexpr 64-by-8 ray table (4 KiB).
Intersect a ray with the current occupancy, then select its first blocker with
`countr_zero` for increasing square numbers or `63 - countl_zero` for decreasing
numbers. The nonzero guard is mandatory. All colors and piece types block rays;
only a correctly aligned friendly slider contributes an attacker. Pinned
pseudo-defenders must remain visible to king-safety checks. Capture selection,
x-rays, promotion arithmetic, king legality and LVA ties are unchanged.

`make test-exchange` now includes an independent square-walking mask oracle with
145,024 comparisons in addition to the existing legal-generator score reference.
The private test includes exchange.cpp directly and links Position only; do not
also link exchange.o. Its generated dependency file is loaded by Make. Native
core/selective-search/SMP and focused ASan/UBSan checks passed. Agent builds use
`build/phase4f4-native/` and `build/phase4f4-asan/`; normal and frozen binaries stay
untouched.

`tools/profile_search_package.py` automatically prepares its Python dependencies.
It fixes all 15 exposed roots, two repetitions, default/all-on and one/eight
workers, serial fresh processes, Hash 64, one second and explicit diagnostics.
It records raw I/O, PID/exit code, both clocks, all applied options, input hashes,
branch counters and worker accounting; partial failures remain visible. Never
compare leader-only iteration deltas directly with aggregate worker totals.
A 300-second whole-run cap, five-second watchdog, independent 250-ms receipt
tolerance and resource checks bound this diagnostic. Its 25 synthetic tests do
not launch engine searches. Input hashes record inspected local sources; they
do not prove arbitrary supplied-binary provenance.

A separate depth-6 comparison passed all 120 searches / 60 exact parent-candidate
pairs on the 15 exposed roots: defaults/all-on, one worker, fresh/reused caches.
Nodes, scores, depths, PVs, best/ponder moves and hash occupancy agree. The
comparison disables diagnostics and deliberately excludes time/NPS from parity.
Independent raw replay also passed all 720 iterations / 3,108 legal PV plies,
500 commands, readiness barriers, both exits and 27 input hashes.

The owner was told LM Studio could resume after the initial screen. **Do not run
further speed comparisons without a new quiet-host window.** Correctness-only
checks may continue; their times are not performance evidence. This SEE change
is provisional for performance: the default search does not use the optional
SEE paths, and no speed/default/strength gain is claimed. Next finish one bounded
uninstrumented comparison, then Phase 4F.5 can select an isolated search candidate
on the accepted LMR baseline. Do not silently restart the parked package match.

Keep evidence under `results/phase4f4-20261025/`, including the exact archived
pre-candidate Makefile/source snapshot and independent initial-screen audit.
Preserve owner `tools/batch_positions.py`, the README introduction and stable GUI
`0.1-dev-4b8b35d`. The owner handles GitHub pushes.

## Previous checkpoint: Phase 4F.3 completed tactical audit

Read the [unchanged protocol](experiments/phase4f3.md) and
[full report](reports/2026-10-24-phase4f3.md). Preparation was committed as
`7444f21`; the engine is frozen from `ccb66a4`. No engine source, playing default,
normal binary or stable GUI bundle changed during this audit.

The authorized full run completed October 24, 21:49–23:07 Helsinki: 39 positions,
78 serial fresh-process searches, eight threads, Hash 64, 60 seconds each.
Defaults reported three positive mates versus two for all-on; best moves agreed
39/39. Raw independent replay passed 741 iterations / 6,280 PV plies and all
option, clock, monitoring and input checks. No detected sleep or operational
failure invalidated the comparison. The specific daytime exception is consumed;
it does not authorize a daytime match or later long tests.

A separate overnight post-hoc diagnostic repeated position 15 twice per role.
Defaults reported M9 at depth 11 twice; all-on reported +15.99 at depth 10 twice.
Every run chose `e7d7`. The independent repeat audit passed all four sessions,
42 iterations / 310 PV plies and original-evidence immutability. Do not pool
these observations into the original 39-position result or rerun to replace it.
Legal mate-ending PVs do not prove forced mate; score/depth differences are not Elo.

**Decision: retain defaults; park the all-on package and unstarted 512-game
campaign.** This is conservative progression after a repeatable mate-report
loss, not a proven worse move or statistical strength rejection. No held-out
opening was searched. Preserve the frozen protocol, inputs and all raw evidence
under `results/phase4f3-20261024/`, including both independent audit files.
The report records hashes and limitations: main-loop receipts, unrecorded process
IDs/exit codes, configured rather than measured CPU/memory use and SMP variability.

Next is **Phase 4F.4**, a bounded diagnosis on the existing exposed 15-root
profiling corpus with matched one/eight-thread conditions. Identify added
per-node cost versus tree changes or SMP interaction before selecting one
implementation candidate. Do not tune thresholds on the 39 puzzles or profile
held-out roots. Component removal is a diagnostic, not a requirement that every
component win alone. A changed candidate requires a predeclared match comparison.
Long tests retain the overnight/resource rules; no automatic schedule exists.

Keep owner `tools/batch_positions.py`, README intro and stable GUI
`0.1-dev-4b8b35d` unchanged; the owner handles GitHub pushes.

## Previous checkpoint: Phase 4F.2

Read the [move-ordering report](reports/2026-10-24-phase4f2.md). Each SearchWorker
owns reusable `ranked_moves` storage. Every `order()` call clears/repopulates it,
computes each existing ordering score once, applies the same SEE adjustment,
sorts with unchanged `tie_before()`, then copies the entire move list back.
Nothing refers to scratch after return, so descendants can safely reuse it.
Scores must not survive into a later call: history and killers can change.
There is no fixed move-count bound or per-ply scratch array.

Do not add a singleton early return in SEE mode: every eligible ordinary
non-TT capture still contributes its original SEE counters. Do not replace
the full sort with lazy rescoring after child searches without a separate
semantic review: history changes, ProbCut's pre-pass and LMR move numbers depend
on the original order. The direct ordering regression privately includes
search.cpp and compares against the frozen former comparator without an NNUE
file. It covers helper workers, flags/special moves and scratch reuse.

The existing 15-root current-default profiler is unchanged. The native candidate
is `build/phase4f2-native/chess0live`; evidence is in
`results/phase4f2-20261024/`. Default and all-enabled fixed-node regressions are
separate from the speed comparison. No policy default changed. The owner's
ordinary binary was rebuilt externally during manual testing; agent builds
use separate directories. Stable GUI `0.1-dev-4b8b35d` remains untouched.

Next is **Phase 4F.3 combined-versus-default strength qualification**. The owner
explicitly wants interactions tested, not just isolated component results.
Use the eight-option recipe in MANUAL_TESTING, keeping all other conditions
identical. A winning package need not consist of individually winning features.
The single reported depth-10 speed result motivates this test, not promotion.
Prepare concrete evidence/configurations before requesting any long-test
daytime exception; do not launch or schedule one implicitly.

## Previous checkpoint: Phase 4F.1

Read the [quiescence efficiency report](reports/2026-10-24-phase4f1.md).
`Position::legal_tactical_moves()` returns all legal captures/promotions in
the full generator's order plus `has_legal_move`. The latter is essential:
an empty tactical list can be a quiet playable position, not stalemate.
After finding any legal move, the generator skips further quiet legality checks
but still examines every capture and every promotion. Canonical make/unmake
restores position state. Checked quiescence continues to use `legal_moves()`;
the tactical list alone is not a complete set of check evasions.

The search keeps terminal detection before draw/stand-pat handling. Fixed-depth
parent/candidate comparisons match every completed iteration and final decision;
the optimization removes implementation work without reducing search nodes.
No timing policy, evaluation or selective-search default changed. LMR is on;
SEE ordering and SEE pruning remain optional and unqualified for default use.

Use `tools/run.py tools/profile_search_baseline.py` for the current 15-root
result-preserving comparison. It explicitly sets LMR on and unrelated
experiments off, checks cold/warm results, independently replays all PVs, and
retains source/binary/network identities. Historical experiment tools may pin
LMR off; do not describe those runs as current-default evidence. All implementation
inputs must remain unchanged during the comparison. Use separate build directories
and a new output directory; the tool rejects overwrites and retains failures.

Evidence: `results/phase4f1-20261024/`; candidate:
`build/phase4f1-native/chess0live`. Normal binaries and stable GUI snapshot
`0.1-dev-4b8b35d` were preserved. The owner can rebuild or point a separate GUI
entry at the tested candidate. Next: **Phase 4F.2 move-ordering efficiency**,
followed by strength-gated search candidates. This is not a release or Elo claim.

## Previous checkpoint: Phase 4E.7

Read [managed selection](NETWORKS.md#managed-selection) and the
[report](reports/2026-10-24-phase4e7.md). `tools/managed_network.py` owns the
external ignored catalog; the engine never reads it. Registration copies the
network and optional metadata, runs a fresh full qualification, rechecks retained
evidence through `network_receipt.py`, then atomically publishes an alias.
Names are immutable; a new name triggers a new check after evaluator changes.
State changes serialize under a file lock. Select/revert validate first; repeating
a selection preserves rollback. Default means the untouched manifest-pinned file.

Every managed launch verifies payload, metadata, reports, 2,057 corpus/output
records, binaries/reference sources and current evaluator/tooling pins. These
are local integrity records, not signed attestations or proof of training claims.
Keep the whole store at its original path; reports use absolute paths. Missing
catalog/evidence in an initialized store must fail, never silently choose default.
Failures before alias publication retain an unregistered directory for diagnostics.

`--eval-file PATH` loads exactly that file before UCI and advertises its absolute
path as the launch default; invalid files exit1, malformed arguments exit2.
Later `setoption EvalFile` remains explicit override. GUI saved values can thus
override the launch argument: use `config --engine PATH` to obtain both argv
and the EvalFile path. `run` inherits stdio directly, no proxy. Ordinary engine
launches and existing GUI bundles retain their former defaults.

Real native macOS registration/launch/rollback, complete oracle comparison,
Python catalog/evidence checks, CLI cases and existing UCI regressions passed.
Evidence is `results/phase4e7-20261024/`; tests use an isolated catalog there,
not the user's `.local/networks/managed`. Synthetic weights are test data only.
Normal binaries, owner batch inputs, exact README intro and GUI snapshot
`0.1-dev-4b8b35d` are preserved. New main.cpp is built separately for validation.
No long campaign, training run, strength promotion or foreign execution occurred.

Next is **Phase 4F.1: a compact search baseline and the next isolated
strength-gated candidate**. The first local network workflow is usable; broader
training hosts/GPU and remaining platform/release work stay open in ROADMAP.

## Previous checkpoint: Phase 4E.6

Phase 4E.6 adds `tools/train.py`, `training_setup.py`, `training_backend.py`,
trainer/runtime manifests and Make plan/setup/smoke/test targets. Read
[TRAINING](TRAINING.md) and the [report](reports/2026-10-24-phase4e6.md).
Automatic first use and offline reuse passed on macOS 14+ ARM64 with managed
Python 3.12.15, Torch 2.14.1 and NumPy 1.26.4. Other training hosts/GPU routes
are not qualified; do not infer coverage from engine cross-build support.

The external trainer pin `aa2fff2f4a67d1a268dad991fcc03430781fde15` retains SF19
PSQT/features/serialization. Never substitute current master merely because
its outer network version matches. It and its data-format libraries remain
external, with upstream notices. Source cache is `.local/training/source/`;
runtime is `.local/training-runtime/`. No code is linked into the engine.

Recipes bind data, settings and optional parent .nnue weights. Fine-tuning resets
the optimizer; arbitrary pickle inputs/full-state resume are unsupported. CPU
AdamW/eager mode, no filters and fixed batches are recorded. Sample counters come
from actual checkpoint steps; configured epochs are not full dataset passes.
Schema 2 metadata adds samples/steps/dataset/trainer/parent hashes and keeps
unknown totals null; schema 1 remains accepted. Counts in supplied metadata are
still unverified declarations. No competitive data or default was created.

Admission reserves tensor threads + four loader/prefetch threads and 8 GiB,
caps batch size at 1,024 and checks known physical memory. The outer process
timeout enforces limits/night cutoff: upstream time checks only at epoch end.
Interrupted runs fail and retain diagnostics/any already completed checkpoints.
Qualification cancellation signals the wrapper first so the harness can stop
its native process groups and record failure before bounded escalation. A real
nested-process regression covers this path. No scheduler was created.
CPU/reference work is sequential within a run.

Accepted fresh (2 steps/32 samples) and parent (1 step/4 samples) exports each
passed 2,057 exact oracle positions. Independent audit and 132 distinct Python
checks passed. Fresh-run peak RSS was about 5.34 GiB; the final memory reservation
was increased from 6 to 8 GiB afterward and used by the parent run. All 88
preservation pins and README intro match, including GUI `0.1-dev-4b8b35d`.
Evidence lives in `results/phase4e6-20261024/` and the exploratory ignored build
directory. Synthetic fixture: 256 records, eight unique positions, zero games.

Next: **Phase 4E.7 managed network selection**. Retain reversible choices and
compatibility/provenance evidence. Broader training hosts/GPU execution, held-out
data validation and competitive training remain separate acceptance work.

## Previous checkpoint: Phase 4E.5

Phase 4E.5 adds `tools/network.py` and `make network-inspect`/`network-qualify`.
Read the [network guide](NETWORKS.md) and [report](reports/2026-10-24-phase4e5.md).
The wrapper needs only Python's standard library; qualification also needs a
native C++26 compiler, Git and Make. It does not select/install a network.

Inspection hashes the full payload and labels header recognition separately
from compatibility. Metadata schema 1 binds declarations to that exact SHA-256;
unknown training counts remain null and supplied claims remain unverified.
The extended oracle preserves strict `--network`, adding explicit
`--candidate-network`, offline/reference-cache selection, literal compiler paths,
bounded child cleanup and current-run failure reports. Candidate checks use
their own weights and skip pinned goldens only for non-pinned artifacts. Each
run compiles a fresh committed reference tree and records/rechecks inputs,
sources, corpus, output and executable identities. Reuse never imports dirty
reference files or stale objects. Native Windows remains unverified.

Both pinned and synthetic changed-weight files passed 2,057 exact position
comparisons, independently audited. The fixture changes 403 outputs; it is not
a trained network. Native tool checks: 66 passed. Linux ARM64 VM: 65 passed,
one Make-boundary test skipped because that image lacks Make. Eight real
negative checks passed. All 88 preservation hashes and the README introduction
match; stable GUI bundle `0.1-dev-4b8b35d` and normal engine remain unchanged.
Evidence is under `results/phase4e5-20261024/`; no new long campaign or release.

Next: **Phase 4E.6 reproducible training/export tooling**, using a pinned
compatible trainer and honest data/experience records. Qualify exports before
selection; compatibility alone is not strength or proof of training provenance.
Keep broad platform/release acceptance and competitive training separate.

## Previous checkpoint: Phase 4E.4

Phase 4E.4 adds `tools/build.py` and `make portable`/`toolchain-plan`/
`toolchain-check`. Read the [guide](PORTABILITY.md#automatic-target-setup) and
[report](reports/2026-10-24-phase4e4.md). Installed-compiler discovery covers all
six targets; pinned LLVM-MinGW provisioning covers Windows targets from five
host architectures. Linux compiler/target-library installation and Apple's SDK
are explicit prerequisites. Fresh native macOS/Linux ARM64/Windows ARM64 builds
passed; native macOS passed all eight runtime checks. A Linux ARM64 VM fetched
and checked its Windows toolchain. Native Windows remains unverified.

The literal `CXX_EXECUTABLE` path is exported to the argv adapter, including
spaces/shell characters; preserve the invoked compiler symlink basename.
Legacy `CXX` shell commands remain available in ordinary Make. Automatic builds
use `build/portable/`, leaving normal/GUI builds intact, and save fresh reports.
The native new engine is byte-identical to the ordinary one. No engine source,
search defaults, owner batch settings/FENs or README introduction changed.
The stable GUI bundle `0.1-dev-4b8b35d` and previous protected assets are preserved.

Toolchain archives/installations stay ignored under `.local/toolchains/` (or the
cache override); preserve upstream notices and full archive pins. Extraction is
staged/atomic and validates paths/internal links. Cache reuse checks ownership
and compiler wrappers; it is not a full scan of installed libraries. The setup
probe checks standard complete-toolchain flags, not arbitrary custom sysroots.
Use the ordinary Make path for advanced compiler-wrapper/custom-flag workflows.

Next: **Phase 4E.5 network inspection/qualification**, followed by export,
training and selection with recorded data/experience provenance. Keep native
Windows execution and further Linux provisioning as explicit gaps. No long
puzzle/match campaign, scheduler, strength claim or release was added.

## Previous checkpoint: Phase 4E.3

Phase 4E.3 adds automatic isolated Python setup through `tools/run.py`, optional
Make test targets and direct batch-puzzle invocation. Read [TOOLS](TOOLS.md) and
[the report](reports/2026-10-24-phase4e3.md). The manifest pins chess 1.11.2 plus
setuptools/wheel build inputs; the historical `requirements-match.txt` is intact.
Use the launcher for unchanged historical scripts. Cache/venv files stay under
ignored `.local/tooling/` by default, with an optional external local cache path.
Preserve owner batch settings/FENs: only its docstring/bootstrap changed. The old
whole-file pin therefore changes intentionally; all other protected assets,
engine sources, native binary, README intro and GUI bundle `0.1-dev-4b8b35d` are
preserved. The synthetic batch test now passes interpreter/script as arguments,
so paths with spaces work.

Setup verifies archive hashes, installs with indexes/build isolation disabled,
checks runtime imports/versions, and repairs owned incomplete environments.
POSIX CLI handoff preserves the tool PID; installer cancellation/timeout kills
its process group and inherited locks prevent overlapping installers. Windows
native setup/process-tree cancellation remains unverified. Real setup succeeded
on macOS ARM64 and in a Linux ARM64 VM; the report records scoped test evidence.

Next is **Phase 4E.4 host/target toolchain setup**, followed by network tooling
and honest training provenance. No new long test, strength claim, default change
or release. Keep compiler/SDK prerequisites explicit and preserve frozen experiment
manifests rather than silently rewriting their historical dependency pins.

## Previous checkpoint: Phase 4E.2

Phase 4E.2 is complete within available runtime limits. The
[report](reports/2026-10-24-phase4e2.md) records new C++26 generic builds for
Linux RISC-V64 (Debian GCC 14.2.0, RV64GC/LP64D) and Windows ARM64
(LLVM-MinGW 20261020 / Clang 23.1.4). RISC-V passed eight checks under QEMU
10.0.13; Windows x86-64 passed eight through Wine 10 inside emulated Linux.
Both passed 140-case Syzygy oracle coverage plus six search scenarios at one
and four threads. Windows ARM64 Wine bootstrap timed out before test execution;
keep it build-only. Do not infer an engine defect or native Windows pass.

The runtime verifier adds an explicit Windows-only `compatibility` route with
mandatory runner arguments and unchanged artifact/architecture/network checks.
Thirty-four verifier tests plus two Make tests passed. Evidence is in
`results/phase4e2-20261024/`. All 24 engine/Fathom source pins and 62 protected
assets match; the native engine, README intro and owner batch settings remain
unchanged. Compiler archives, networks, tables and result files stay outside Git.
Isolated phase containers/Wine processes were cleaned up; unrelated Docker
services were not stopped. No long test or automatic schedule was launched.

Next is **Phase 4E.3 one-command tooling setup**, incorporating the owner's
October 24 feedback: automatic isolated dependency environments for tools,
tests and benchmarks, followed by toolchain provisioning and network
create/train/validate/select workflows with honest provenance/experience
metadata. See the [backlog](ROADMAP.md#tooling-usability-backlog--accepted-october-24-2026).
This is planned work; current explicit setup instructions are not automatic
provisioning. Preserve `tools/batch_positions.py` settings when implementing
its bootstrap. Remaining native Windows acceptance and new CPU/backend/network
qualification stay explicit, bounded work rather than repeated Wine diagnosis.
Keep LMR on, experimental pruning off and existing GUI snapshots intact.

## Previous checkpoint: Phase 4E.1

Phase 4E.1 is complete; see the [runtime report](reports/2026-10-24-phase4e1.md).
`make runtime-binaries` cross-builds the engine plus seven correctness binaries
without executing them. `make verify-runtime` checks native execution; the
standalone verifier accepts explicit VM/emulator routes and records architecture,
network, compiler configuration, commands, logs and failure evidence. All C++
test links now receive `LDLIBS`. Thirty verifier/build checks passed; eight
runtime checks passed each on native macOS ARM64, ARM64 Linux VM and emulated
x86-64 Linux. Both Linux builds also passed the existing 140-case Syzygy oracle
and one/four-thread search gates. Current Windows x86-64 compiled/linked only.

Evidence is under `results/phase4e1-20261024/`. Docker test containers were
limited to two CPUs/2 GiB, removed after use, and explicitly cleaned on failure;
ordinary process-group cleanup alone cannot stop daemon-owned containers. Do
not stop unrelated Docker containers. No engine sources changed, and the native
binary remains byte-identical to the Phase 4D.7 candidate. Existing source and
protected-asset pins passed. No fresh full external NNUE stage-oracle,
sanitizer/race campaign, match, puzzle comparison or strength result is claimed.

Next: Phase 4E.2 remaining RISC-V64/Windows ARM64 toolchain and target-execution
gaps, before the separately scoped network qualification/export/trainer work.
Keep conservative LMR on and all other experimental pruning off. Preserve
`0.1-dev-4b8b35d`, other GUI snapshots, the README introduction, and editable
`tools/batch_positions.py`. No long run or schedule is authorized by this
checkpoint. The consumed Phase 4D.7 daytime exception grants no repeat.

## Previous checkpoint: Phase 4D.7

Phase 4D.7 implements the isolated, default-off `ProbCut` hypothesis under its
[fixed protocol](experiments/phase4d7-probcut.md), committed before candidate
searches as `563c040`. Native/scalar/ASan+UBSan/TSan direct and UCI checks passed,
including both-color quiet-defense rejection, checking mates, sacrifice
retention, score/draw boundaries, cancellation and cache isolation. The native
ordinary SMP suite passed 43 cases; the new UCI suite passed 30 per build.
Ordinary search checks passed native/scalar/ASan+UBSan. No sanitizer/race finding
occurred. Two independent reviews found no production blocker; the profiler
passed 31 engine-free checks. The independently audited 60-search screen
preserved all 12 parent/off signatures, including hash occupancy, and found
22.05% fewer fresh-cache nodes and 2.98% fewer reused-cache nodes. Reused-cache
elapsed time rose 1.62%; one of six timed roots gained a ply. Fixed-depth
decisions and all common-depth scores/PVs matched. These are exposed,
instrumented measurements, not strength qualification. See the
[report](reports/2026-10-23-phase4d7.md). Current measurement evidence is under
`results/phase4d7-20261023/`; frozen inputs under
`build/experiments/phase4d7-20261023/`. The one-second puzzle smoke passed
independent audit: 78 legal results, matching best moves, 14 score differences
and no reported mates. The authorized full attempt after `21d416f` finished
October 23 at 11:20:28 Warsaw / 12:20:28 Helsinki; both adapters and supervisor
exited zero. Audit verified 78 legal results, all 39 best moves matching, M7 on
position 2 in both roles, no additional mates and 19 score differences. OS logs
confirm 13 sleep intervals: 59 seconds during parent, 3,100 during candidate.
Wall duration 127m18.244s differs from monotonic 75m04.849s; per-position search
opportunity cannot be recovered. **Equal-time tactical qualification is
inconclusive**, not passed. Preserve original outputs/status and the separate
`puzzles-full-audit.json` / `puzzles-power-events.txt` under the results folder.
The launch record is `0f741fa`; tool session 66275 has finished. No test, repeat
or schedule is running/authorized. Close this attempt with ProbCut parked off;
next broader work is Phase 4E. Any future qualification needs a separately
prepared sleep-aware launcher and new authorization, without tuning this suite.
The owner reports ten-thread Sic/Gargantua M7/M8/M9 solutions; this one-thread
run cannot establish a comparison with those manually observed results.
Keep conservative LMR enabled, all other experimental pruning disabled, timing
classic and the protected GUI bundles intact. Do not overwrite the owner's
editable batch settings. This phase has no strength-qualified result yet.

## Previous completed checkpoint

Phase 4D.6 is complete under its [fixed scope](experiments/phase4d6-deep-quiet.md).
Native/scalar/ASan+UBSan/TSan checks and finite development profiles passed.
The [report](reports/2026-10-23-phase4d6.md) records exact default search parity,
small extra-reduction work savings and the bounded-time depth tradeoff.
The full 60-second comparison finished at 08:02 Warsaw on October 23 in 78m05s.
Independent audit passed all 39 legal results per build and 83 source/asset
checks. Both reported M7 on position 2 and centipawn scores on the other 38;
all best moves matched, with 15 centipawn-score differences. No new or lost
mate was reported. This is not a best-move solve rate or strength qualification.
Frozen candidate SHA-256:
`c1858bb92419e00bbe3846e2daa94dc4260effad6acea705a2455881c920c199`. Keep the
accepted one-ply LMR default true, the new deep option false and timing classic.
The one daytime run authorized after `d25e2e5` is finished; it grants no repeat
or schedule. Raw output and `puzzles-full-audit.json` are under
`results/phase4d6-20261023/`. Preserve the original supervisor status, which
records completion pending audit; the separate audit file records the passed
checks. Park deeper reductions as opt-in without another long qualification
run. Next is the separately scoped **Phase 4D.7 ProbCut** hypothesis.
Historical qualification tooling rejects the added Time Policy choice; preserve
those frozen contracts and use a separately scoped protocol for new qualification.


The [October 23 final LMR audit](reports/2026-10-23-lmr-results.md) passed:
512/512 games, 215W/175D/122L (59.08%), no clock forfeits or audit errors.
The campaign ended at 02:18 Warsaw; all 1,024 engine processes exited. Raw audit
and summary are in `results/lmr-20261022/`. No experiment is currently running.
The frozen rule returned `eligible_for_default_review`, followed by the separate
[default integration](reports/2026-10-23-lmr-default.md). Only LMR's API/UCI
defaults are now true; opt-out and every search rule remain intact. Exact
parent parity, native/scalar/ASan+UBSan regressions and TSan search/SMP checks
passed; the default integration is retained. Other experiments remain off.
The parked 4D.6 candidate is separate from this accepted integration. Do not pool historical results,
retune/retry exposed openings or claim eight-thread strength. The owner's
puzzle-runner settings are now committed unchanged as `dac8a19`; the README
introduction and stable GUI snapshots remain protected.

The [fresh October 22 LMR qualification](reports/2026-10-22-lmr-launch.md)
started at 20:03 Warsaw / 21:03 Helsinki after commits `548ce74` and `a81c951`.
All four games produced searches and moves with startup resources within limits.
Its completed result and independent audit are recorded above.
Read its [fixed protocol](experiments/lmr-20261022.md): 512 games/256 pairs,
four active workers, 60+0.6, same ordinary executable, only LMR on/off differs.
All 145 workflow checks and full generation-source replay passed. Raw preparation
records are in `results/lmr-20261022/`; frozen binary/manifest and protected pins
are in `build/experiments/lmr-20261022/`. Live evidence is under
`results/lmr-20261022/campaign/`; console/session records are in its parent.
**The one long run has finished; no schedule exists.**
After preparation commit `548ce74`, the owner authorized this one October 22
daytime launch. The explicit `run --allow-daytime` amendment passed 81 relevant
checks and fresh independent readiness, committed as `a81c951`. It expires
at 23:30 Helsinki that day. It grants no resource
increase, repeat attempt or schedule. The original next-07:00 Helsinki cutoff
is immutable. Ordinary unflagged launches still require 23:00–23:30 Helsinki.
Any either-role flagfall blocks default eligibility. Preserve all fixed inputs
through audit; no retry/resume, replacement, score-based stop or default change.
The qualification checkpoint is complete. Its default integration is recorded
above, separately from the frozen match protocol and audit.

The [four-worker readiness check](reports/2026-10-20-match-readiness.md) passed:
8/8 natural games, 646 on-time searches, four-way overlap, unchanged pins and
all 16 processes closed in 23.949 seconds. Preparation commit `2b04cd3`
preceded the single attempt. `make test-match test-match-readiness` passed
94 checks. Raw evidence and independent audit are in
`results/match-readiness-20261020/`; its openings are now exposed.
This permitted the separate qualification above. No schedule exists. At that
readiness checkpoint engine defaults, owner puzzle settings and GUI bundles
were unchanged. It was operational evidence, not a historical clock repair
or strength proof. Later default integration is recorded above.

The first three steps are implemented as an unreleased `0.1-dev` baseline.
Normal and sanitizer suites passed natively on macOS ARM64. SF19 integer parity
has a separate reproducible oracle harness. ARM64 NEON is implemented; the
reference remains selectable with `SIMD=scalar`. Three other platform binaries
cross-build, with execution still outstanding. RISC-V64 and Windows ARM64 lack
configured local toolchains. Search now supports configurable Lazy SMP (Phase 4B),
while Threads=1 remains the default.

An original paired-opening runner now records clocks, game files, binary/network
hashes, and pair-level statistics. Small development and validation suites are
separate. Read [the match guide](MATCHES.md) before running it. The optional
external move checker agrees on 93 positions at depth 2, including special moves.
The included 12-opening suites are too small for the runner's uncertainty gate;
no strength rating or improvement is established by their smoke tests.

A deterministic comparison helper now checks equal per-depth search work before
reporting throughput. The first buffer-reuse candidate passed correctness but
had inconclusive timing results, so it was not retained. The later Phase 3B
batching change is separate; [the experiment log](EXPERIMENTS.md) preserves the decision and
local evidence paths. Do not count this experiment as a strength improvement.

The owner is testing with Cute Chess while development continues. Snapshot
`0.1-dev-4b8b35d` is preserved under ignored `build/test-baselines/`, including
its own network and manifest. Read [manual testing](MANUAL_TESTING.md) and do not
replace that copy during ordinary rebuilds. GUI feedback does not block work.
The owner's [first two games](reports/2026-10-14-cutechess.md), submitted October
14, replay legally to threefold repetition and checkmate. All 171 positions
also passed legal-move and exact NNUE oracle checks. The owner reports working
GUI integration; exact runtime options and GUI version were not captured.
Long opening iterations spent much of the clock and left the black game in
severe time pressure. No deadline, mate-reporting, or evaluator defect was reproduced. Treat these games
as exploratory feedback, not a calibrated strength test or held-out suite.

Phase 2 covered **search efficiency and time management**; keep the
[roadmap](ROADMAP.md) and user updates explicit about phase and step. Root-level
diagnostics, an alternating clock-policy profiler, and per-engine match options
support the [time-management experiment](TIME_MANAGEMENT.md). `Time Policy` stays
`classic` by default; `forecast` is opt-in and `Search Diagnostics` defaults off.
The first soft-target forecast gate was rejected after it stopped a full depth
earlier on all 18 short-clock development comparisons. The narrower candidate
uses the hard deadline for prediction and retains classic soft stopping.
Do not treat reduced thinking time as a strength gain or enable diagnostics in
real matches. Explicit limits and all ponder requests exclude forecast behavior.

The 32-root `openings-time-validation.json` is original, legal, and disjoint
from the earlier 24 roots. It was held out until the completed time-policy
campaign described below; it is now exposed evidence, not fresh validation.
Use preserved binaries and complete records when auditing that comparison.

Phase 2C now has a conservative one-ply late-move-reduction candidate, selectable
with `Late Move Reductions=true`; its initial default was false (the October 23
integration above supersedes that setting). Read
[selective search](SELECTIVE_SEARCH.md) for guards, mandatory ordinary-depth
verification, exact hashes, and results. Native/scalar/sanitizer checks passed,
and the new fixed-depth/node profiler independently checks legal PVs. Turning
LMR off preserves all 24 sampled frozen-parent signatures. At depth 5, reductions
used 49.79% fewer nodes with matching final moves/scores/PVs on all 12 development
roots, repeated twice. At 200,000 nodes, 8/12 roots completed an extra nominal
depth, but a move and several scores/PVs changed. This supports further testing,
not a strength claim. Keep classic timing for isolated LMR comparisons and use
`build/experiments/lmr-20261014/` for the frozen candidate. The owner's GUI bundle
and the separately frozen time-policy candidate are unchanged.
The predeclared eight-game smoke scored 2W/2D/4L for LMR with no operational
failures. This unfavorable small sample does not support default promotion;
record it honestly and do not tune to these pairs as if they were held out.

The independent [capture-ordering experiment](MOVE_ORDERING.md) is also now
implemented and checked. `Capture Ordering=mvv-lva` remains the default; `see`
uses legal-LVA material estimates to rank negative exchanges below quiet moves,
without pruning captures. Native/scalar/sanitizer tests, 28 composed/reflected
cases, and 4,117 generated reference comparisons passed. Default mode matched
all 24 parent samples. Depth-5 work fell 4.72% with matching final decisions;
equal-node searches gained one nominal depth on one root and lost one on another.
The eight-game smoke scored 2W/4D/2L without operational failures. No strength
claim or default promotion follows. Frozen candidate:
`build/experiments/capture-ordering-20261014/chess0live`, SHA-256
`7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
Use `tools/profile_lmr.py --experiment capture-ordering` for isolated comparisons;
it pins LMR off and classic timing. Its historical filename still supports LMR.

The separate [LMR loss replay](reports/2026-10-14-lmr-losses.md) found no
LMR-specific miss in its eight selected roots. All moves and all 40 common-depth
scores/PVs agreed; no LMR parameter changed. This is post-hoc development evidence,
not held-out qualification or proof that every reduction is safe.

Phase 2C's initial experiments are complete. Phase 2D's
[first time-policy screen](reports/2026-10-15-phase2d-time-policy.md) finished on
October 15, 14:24–17:18 Helsinki, using preparation commit `2cf55f7` and the
owner's one-run daytime exception. All 64 games / 32 pairs passed the independent
audit: forecast 14W/43D/7L, 35.5/64 points, conditional 95% score bounds
31.46–79.48%, no exclusions, clock forfeits, protocol failures, or artifact drift.
The predeclared result is **inconclusive**. Keep classic timing, LMR off, and
MVV-LVA as defaults; no strength or equivalence claim follows.

Evidence is in `results/phase2d-time-policy-20261015/`, including the immutable
pre-play `protocol.md`, launch manifest, complete match records, and `audit.json`.
Archive the whole directory when moving machines. The audited run's tool/protocol
hashes stayed unchanged during play; later documentation updates do not rewrite
that frozen record. The one-run exception is consumed. The GUI snapshot
`0.1-dev-4b8b35d` is unchanged; the subsequent LMR run used ordinary night limits.

The [isolated LMR screen](reports/2026-10-16-phase2d-lmr.md) is complete:
64 fresh full histories / 128 games at 60+0.6, seed `20261015`, frozen `b825a09`
binary on both sides, classic timing, only LMR on/off differing. It scored
**35W/82D/11L, 76/128 points (59.375%)**. The conditional 95% interval is
**42.40–76.35%**, so the predeclared result is **inconclusive**; LMR stays off.
No strength-gain or equivalence claim follows from the favorable point estimate.

All 100 workflow checks and real no-search preflight passed before play.
Preparation commit: `842ee41`; launch-record commit: `57e21fd`. The match ran
October 15 23:00:08–October 16 05:41:20 Helsinki (6h41m12s), within the ordinary
night window with one active worker. Audit and independent replay verified all
17,175 legal plies / 15,191 searches, exact clocks/options/outcomes, no exclusions,
failures, forfeits, truncations, or artifact drift. The runner and its macOS
idle-sleep assertion have ended; no automatic schedule or resume exists.

Preserve all of `results/phase2d-lmr-20261015/`: the immutable pre-play protocol,
launch/configuration/source hashes, match records, `audit.json`, and
`preserved-assets.json`. All five frozen binary/network artifacts, including
GUI `0.1-dev-4b8b35d`, remain unchanged. Later status-document edits are separate
from the audited unchanged before/after integrity record. The shared launcher
is `tools/qualification.py`, with historical time-policy and LMR entrypoints;
`tools/audit_lmr.py` independently pins the LMR protocol. Both completed suites
are exposed evidence, not fresh validation. Do not extend or retune their samples.

**Phase 3A is complete**, as recorded in the
[performance report](reports/2026-10-16-phase3a-baseline.md). Frozen builds are
`build/experiments/phase3a-20261016/release/` and `symbols/`; the release hash
matches the preserved capture-ordering binary, with experimental options off.
All 192 same-binary searches and 48 symbol-equivalence searches matched, with
independent legal-PV replay. A separate CPU profile and independent audit found
85.04% of 7,413 search observations in NNUE, including 58.69% in update.

Preserve all of `results/phase3a-20261016/`, including the denied sampler attempt,
corrected nested-bundle network setup, raw stacks, independent audits, and frozen
protocol/source hashes. The new `tools/profile_cpu.py` is macOS-only tooling;
`make test-profile-cpu` checks it with mocks. Its report records sampling-window
coverage but raw stacks still need independent identity/attribution inspection.
Do not use sampled timings as throughput results or include main-thread idle
observations in the search denominator. All measurement jobs have ended.

**Phase 3B is complete and retained.** The [result](reports/2026-10-16-phase3b-nnue-batching.md)
records one isolated change: stream up to eight feature columns and update
32 hidden lanes per tile, preserving modulo arithmetic, all multiset deltas,
enumeration, inference, search, and options. All three native/scalar/sanitizer
suites passed, including 360 independent arithmetic transitions and the existing
537-position incremental suite. The external 2,057-position oracle matched the
original corpus and every integer-stage/raw digest for both native and scalar.

All 576 comparison searches retained exact signatures and legal output.
The three fixed timing runs yielded median ratios **1.078081, 1.079836, 1.083612**,
above the 1.03 gate; all 24 pooled root/depth medians passed the 0.98 guard.
This establishes a sampled opening-search speedup on the M5 Pro, not Elo.
Keep `results/phase3b-20261016/`, all three candidate build configurations in
`build/experiments/phase3b-20261016/`, and `build/nnue-oracle-phase3b-20261016/`.
At the Phase 3B checkpoint, the normal native executable was byte-identical
to that tested candidate:
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.

**Phase 3C is complete with a mixed qualification outcome.** The
[report](reports/2026-10-16-phase3c-gamephases.md) records six original middlegames
at depth 6 and six endgames at depth 8, with baseline controls and two candidate
runs per phase. All 432 searches matched exactly; independent replay checked
3,024 PVs / 14,904 plies and all 432 bestmoves/ponders. Middlegames qualified:
ratios 1.087243 and 1.088055, stable control, all floor/root guards passed.
Endgame controls/ratios were favorable, but sparse pawn root `gamephases-eg-05`
took about 30–32 ms, below the frozen 50 ms floor in all six role/run medians.
Endgame and combined qualification are therefore **inconclusive**; no root was
excluded or workload changed. No engine code, binary, or default changed.

Preserve `results/phase3c-20261016/`, especially the frozen protocol, suite,
manifest, all six complete JSON/log comparisons, campaign lifecycle, audits,
and final integrity checks. Preparation commit: `ae5853a`. The full campaign
ran 11:57–12:11 Helsinki on October 16 in 844.997 seconds, within its 900-second
ceiling and normal daytime budget. All processes ended; no schedule is active.

**Phase 3D is complete.** The [report](reports/2026-10-17-phase3d-workload.md)
records baseline-only depths 8–12 and all 40 exact/legal searches. Depth 12
was the shallowest tested level meeting the frozen diagnostic rule: role medians
329.881/322.562 ms, paired ratio 0.999090 and MAD 0.028507. Its MAD is near the
0.03 limit; three pairs do not establish lasting repeatability. Depth 10's
ratio/MAD failures are retained. No candidate was compared or engine changed.

Preserve `results/phase3d-20261017/`: frozen protocol/manifest, five raw JSON/log
pairs, launcher/preflight, campaign, final integrity, and auditor/check scripts
and results. Preparation commit: `ec88195`. The failed `audit.json` records an
auditor-only API typo; the successful audit is **`audit-final.json`**. Raw evidence
was unchanged. All 35 integrity checks and 20 audit checks passed. The campaign
ran 21:10:32–21:10:40 Helsinki on October 17, using one active worker in the normal
daytime budget. All jobs ended; no schedule is active.

**Phase 3E is complete and qualified on the revised composed endgame sample.**
The [report](reports/2026-10-17-phase3e-endgames.md) records all six roots (pawn
`gamephases-eg-05` depth 12; other five depth 8), fresh controls and two candidate
rounds. All 216 searches matched exactly; replay verified 1,872 PV lines /
10,512 plies and 216 bestmoves/ponders. The complete control ratio was 0.998927,
MAD 0.003985; candidate ratios **1.089113 / 1.084243** passed with all duration
and root guards. Each round pools 30 pairs, five per root, with 16 baseline-first
and 14 candidate-first. Two candidate slowdowns, control outliers, and absolute
time drift are retained; no Elo or universal performance claim follows.

Preserve all of `results/phase3e-20261017/`, especially frozen protocol/manifest,
six raw JSON/log pairs, campaign, preflight/suite/integrity checks, auditor/check
scripts and outputs. Preparation commit: `c38bd9c`. Final audit `audit.json`
passed with zero errors; 29 auditor checks and 37 frozen-input checks passed.
The campaign ran 21:25:48–21:31:42 Helsinki on October 17 in 353.663077 seconds,
with one active worker under the normal daytime budget. All jobs ended and no
schedule is active. Production code, defaults, normal and frozen binaries are
unchanged. Phase 3C's original decision remains inconclusive; no old data was
pooled into 3E, and this completed campaign must not be extended selectively.

**Phase 3F is complete and retained.** Read the [fixed protocol](PHASE_3F.md)
and [result](reports/2026-10-17-phase3f-dense.md). Preparation `dd3d269` and
hypothesis `876511b` preceded implementation `500b022`. The NEON dense kernel
shares each activation across four output rows; scalar/singleton paths, feature
math, state updates, and search/defaults are unchanged. All native/scalar/sanitizer
suites passed (1,515 dense cases / 84,126 output comparisons, 360 update transitions,
537 incremental positions per backend); the 2,057-position SF19 oracle retained
all corpus/stage/raw digests. The 96 equivalence and 72 profile searches passed
independent audits and two raw-stack aggregations agreed.

All 576 timing searches matched exactly and replayed legally (3,552 PV lines /
15,840 plies). Control and both candidate rounds passed every phase gate; ratios
were opening **1.196321/1.195963**, middlegame **1.196515/1.213653**, and endgame
**1.324133/1.394803**. Four individual slowdowns, order effects, and substantial
absolute-time drift remain recorded. This finite engineering screen establishes
sampled throughput, not Elo. The campaign ran 23:16:49–23:29:15 Helsinki on
October 17, 746.807169 seconds, one active worker under the normal night budget.

Preserve `results/phase3f-20261017/`, especially both protocol snapshots, all
manifests/raw logs/samples, `timing-audit.json`, `final-integrity.json`, auditor
scripts/checks, candidate patch and full tables. There were no failed audits;
21 recorder tests, 23 launcher mock cases and 52 auditor checks passed. Setup-only
fixes are documented. Timing evidence must not be repeated selectively.

The qualified candidate, normal native executable, and optional
`0.1-dev-phase3f-20261017` GUI bundle share SHA-256
`edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b`.
The original `0.1-dev-4b8b35d` remains intact. The new bundle passed CLI startup,
adjacent-network discovery and legal depth-5 search from an unrelated directory.
The owner subsequently reported two draws against Gargantua with no GUI errors
on October 18. This was the intended snapshot; runtime options and executable
identity were not captured. The [review](reports/2026-10-18-cutechess.md)
preserves the partial PGN: 121 legal plies, matching depth-2 divides at 122
positions, and early clock depletion. The file ends unfinished at 61.Nc3. The
owner clarified that they adjudicated game 1 as drawn, judging it would finish
drawn and wanting to save the PGN before the GUI advanced. This is an owner
adjudication, not a replay-verified played-out ending. Game 2 has no PGN. Treat
these as exposed diagnostic games, not strength qualification or Phase 3G inputs.
The normal executable was intentionally promoted **after** the passing audit; the frozen manifest records
its old hash. Those old bytes remain at the retained Phase 3B path. Use the final
integrity record to distinguish promotion from unexplained artifact drift.

**Phase 3G is complete and audited.** The [fixed plan](PHASE_3G.md) compares
LMR on/off using the same qualified Phase 3F executable on 256 fresh opening
pairs / 512 games at 60+0.6. Four concurrent match workers require aggregate
accounting for four active searches and eight resident engines. Normal launch is
23:00–23:15 Helsinki; one common 07:00 cutoff survives preflight and worker starts.
Before any games, the owner authorized a one-time October 18 daytime start.
Protocol v2 and `--allow-daytime` encode that date-limited exception, preserving
the 50% daytime budget and next-morning cutoff. The amendment was tested and
committed as `fce2539` before starting `results/phase3g-lmr-20261018-daytime`;
no sample or decision
rule changed, no previous attempt ran, and no automatic restart is permitted.
All 189 match/qualification checks pass, including 29 launcher and 45 auditor
cases. Real v2 readiness plus independent transcript audit passed without a
search; retain `results/phase3g-preparation-20261018/daytime-v2-preflight.json`
alongside historical v1 records. See the validation amendment for exact scope.
The first actual attempt ran **October 18, 08:54:00–15:12:09 Helsinki**, before
the common October 19 07:00 cutoff. All four shards finished with 128 games
each. The independent `audit.json` passed with zero errors and no live-source
differences, verifying 60,323 legal plies and 50,352 charged search events.
The [result report](reports/2026-10-18-phase3g-lmr.md) records **225W/155D/132L,
302.5/512 points (59.08%)** and conditional 95% bounds **50.59–67.57%**.
Six candidate and seven baseline clock forfeits remain included. The frozen
decision is **operational regression**, so LMR stays off despite clearing the
numerical screen. This does not establish that LMR caused the flagfalls.
The runner and its idle-sleep assertion have ended; no scheduler or restart
exists. Preserve the full campaign, original audit, and frozen protocol.

The original 32 stems and deterministic legal continuations are not evaluated
for balance; related roots and common-host load limit statistical assumptions.
All 256 pairs passed the independent aggregate audit. Its conditional 95%
half-width is 8.488 percentage points: at least 299.5/512 points is only eligible
for fresh confirmation, never automatic promotion; at most 212.5 is negative.
Candidate clock forfeits take precedence. Do not resume, replace, or selectively
extend a sample, and do not pool the exposed Phase 2D result. Initial owner
feedback on the intended Phase 3F GUI
bundle is recorded; no more manual games are required. Do not start controlled
matches while any GUI games are running. LMR remains off. Phase 3H's subsequent
accounting repair is recorded below; it does not revise Phase 3G's result.
`tools/qualify_phase3g.py` supervises the run; `tools/audit_phase3g.py` checks all
four raw campaigns and one pooled decision. `make test-phase3g` checks the new
tools, while `make test-qualification test-match` includes historical regressions.
The protocol/suite preparation commit is `c177804`; tools and lifecycle fixes
are committed as `ff478a7`. See [validation](VALIDATION.md)
for the distinction between synthetic lifecycle evidence and actual readiness.
Quiescence legal generation still protects stalemate/checkmate precedence and
is outside this optimization. No new search-policy default was promoted.

**Phase 3H's bounded diagnosis/repair is complete.** Read the
[plan](PHASE_3H.md) and [result](reports/2026-10-18-phase3h-clocks.md).
`SearchLimits::received_at` carries the monotonic UCI receipt before parsing,
preparation, and dispatch. Ordinary clocks/movetime now include that delay;
ponderhit remains its own charge origin. Future origins clamp to entry and
extreme past elapsed values saturate safely. No allocation formula, overhead
default, LMR rule, or move-ordering policy changed. Native/scalar/sanitizer
suites pass, including deterministic expired-receipt and cold-network UCI tests.

All 13 Phase 3G flagfall histories are preserved as exposed diagnostics in
`tests/data/clock-flagfalls-phase3g.json`. `tools/probe_clocks.py` ran all 26
history/mode combinations once on each executable, with fresh tables and
readiness. All 52 returned legal, on-time moves; because the baseline also
passed, the historical failure is not reproduced by this isolated workload.
Only one historical case is consistent with uncharged startup; the other 12
cannot be attributed without final internal timestamps or scheduler evidence.
Do not claim all clock losses fixed or reinterpret Phase 3G as qualifying LMR.
Both original GUI bundles remain unchanged. The normal build contains the repair;
a frozen copy is at `build/experiments/phase3h-20261018/chess0live`.

Any reserve/allocation experiment needs a new bounded hypothesis and relevant
evidence; fresh strength confirmation is still deferred. Raw diagnosis, controls,
native/scalar/sanitizer logs, probes, and final integrity are retained under
`results/phase3h-20261018/`; the report documents exact scope and hashes.

**Phase 3I is complete.** Read the [plan](PHASE_3I.md) and
[receipt report](reports/2026-10-18-phase3i-receipt.md). `RecordingProtocol`
timestamps each input callback once, lets the pinned parser collect complete
lines, records the entire batch, then dispatches in original order. This removes
reproduced same-batch logging bias without backward timestamps on reentrant
`readyok` commands. A split line uses its terminating-newline callback; equal
timestamps remain audit-valid. Receipt is not kernel arrival, and earlier
event-loop stalls are still charged. Do not rewrite old logs or outcomes.

All 212 match/qualification/audit/diagnostic checks passed. The new POSIX
`tools/probe_receipt.py` completed its fixed 12-search control matrix: ordinary
replies were on time, a sleeping consumer was late despite on-time reader
receipt, and intentionally paused engines were late internally and externally.
All moves/PVs were independently legal. It uses a same-process reader thread,
not an independent observer; see its limitations before interpreting residuals.
Raw evidence and the frozen pre-probe plan are in `results/phase3i-20261018/`.
Engine sources and the final Phase 3H binary are unchanged; no rebuild or new
full engine/oracle suite is claimed. README introduction and GUI bundles remain.

**Phase 3J's implementation checkpoint is complete.** Its [plan](PHASE_3J.md) also includes the owner's
explicitly requested annotated puzzle input. The normal release accepts a
nonempty `bm` suffix after six FEN fields, or four fields with counters defaulted
to `0 1`. It discards metadata before search and rejects mixed `moves` histories.
Native/scalar/sanitizer suites passed; all 39 supplied workbook inputs matched
independent depth-2 legal divides and old/plain/annotated search signatures.
The exact 60-second example returned Qxf6+ at completed depth 8, without proving
mate in seven. The workbook remains unchanged and is not a held-out strength
suite. See [manual puzzle testing](MANUAL_TESTING.md#manual-puzzle-positions).

Match protocol persistence now uses bounded per-game writer threads; all
game/campaign filesystem work leaves the shared loop. Queue/timeout/disk failures
invalidate evidence and abort, with cancellation-safe cleanup. The 8 MiB / 4,096
record cap covers serialized pending/in-flight log payload, not total RSS. A
30-second writer timeout can leave a daemon that returns later; never reuse a
failed directory. Ordinary offloaded finalization retains ownership until done.
Read [match persistence limits](MATCHES.md#interpret-the-result).

All 230 workflow checks passed. The four-game, two-worker canary injected 100 ms
per log write and finished in 220.986 seconds: two checkmates, one threefold draw,
one 128-ply cap. No clock/protocol/storage failure was recorded, but the capped
game prevents the declared full operational acceptance. Preserve the attempt;
do not extend, replace, or score the capped game as drawn. Read the
[Phase 3J report](reports/2026-10-18-phase3j-persistence-puzzles.md).

**Phase 3K is complete:** [report](reports/2026-10-18-phase3k-console-operations.md).
Independent console tools `d`/`show`/`display`, view-only `flip`, `help`, board-plus-
static `eval`, and cancellable `go perft N` passed native/scalar/sanitizer checks.
New output uses `info string`; the board keeps its FEN sentinel last and eval
keeps the raw record last. Legacy perft/divide contracts remain. Independent
checks cover 93 display/perft positions and 36 exact old/new/diagnostic searches.
The frozen native binary SHA-256 is
`5063b483406d5b8061db330b070962e1665c196870c9a7968a18752432f3894f`.

The separately declared four-game operational screen passed its first independent
audit: four complete draws, 386 on-time searches, no clock/protocol/storage/stderr/
cap failures, unchanged pins, four normal-budget admissions, and all eight engine
processes closed. It finished in 17.135 seconds; minimum recorded clock slack
was 19.225 ms. Raw evidence remains in `results/phase3k-20261018/`. The previous
Phase 3J capped game and Phase 3G operational-regression decision are unchanged.
This finite two-worker result permits preparation, not a reliability/strength claim.

**Phase 3L preparation is complete:** the [fixed protocol](PHASE_3L.md) and
[report](reports/2026-10-18-phase3l-preparation.md) record 256 fresh roots against
851 cataloged exclusions, current frozen inputs, dedicated launcher/auditor
identities, 94 passing workflow checks, and independently audited serial readiness.
The readiness transcripts contain no `position` or `go` commands. The 512-game
comparison has not started; do not reuse historical daytime authorization or
create a schedule. No engine search/clock policy changed. Both GUI bundles and
README introduction remain intact; the owner can test the normal build now,
and no additional GUI tournament is required. The owner handles pushes.

The owner's Phase 3L feedback changes explicit console diagnostics to plain text,
including final `fen ...`, `eval psqt ...`, and `perft complete ...` records.
Standard search/error output retains UCI formatting. Native correctness checks
and signed mate-reporting cases for both colors pass; search logic is unchanged.
Do not adapt historical frozen Phase 3K evidence in place. The owner also asked
for broader progress: finish this bounded preparation, then follow the roadmap's
cache-efficiency (Phase 4A), Lazy SMP, and Syzygy work areas instead of indefinitely adding
qualification subphases. Transposition caching already exists; SMP and Syzygy do not.

**Phase 4A is complete:** [report](reports/2026-10-18-phase4a-cache.md) and
[bounded plan](PHASE_4A.md). Standard search reports include `hashfull` in permille,
including terminal/draw reports; diagnostics additionally expose cache counters
and geometry. The one retained candidate packs entries to 16 bytes in aligned
64-byte buckets, with the old 96-byte sizing divisor preserving all bucket
counts and search semantics. At Hash 64, table storage is 32 MiB instead of
48 MiB. Do not silently change that divisor to the physical size: it would
double capacity and change collisions/search. Full keys, move flags/sentinels,
scores, generation bytes, history/rule-50 keys, and replacement rules remain.

Native/scalar/sanitizer suites and 20 profiler tests passed. All 72 bounded
cache-profile searches preserved exact signatures/counters/occupancy across
representations; the 36-search timing comparison passed the declared guards
with effectively neutral timing. Evidence is in `results/phase4a-20261018/`;
the retained native SHA-256 is
`9caa5ccc3716ef25c289c8c43d63762c811163f2a4c7f1e8432fd9e012d8168c`.
At the Phase 4A checkpoint, the next step was **Phase 4B: Lazy SMP**. The table was
still single-worker owned, and its
packed/aligned representation provides no concurrency guarantees. Keep the
Phase 3L binary/manifest and both GUI bundles frozen. To see hash reporting in
Cute Chess, select the newly rebuilt normal executable, not a preserved bundle;
the UCI bytes are tested, but GUI rendering has not been rechecked in this phase.

**Phase 4B is complete**; implementation/tools commit `b0c22d2` adds configurable
Lazy SMP. Read [the report](reports/2026-10-18-phase4b-smp.md) and
[architecture](ARCHITECTURE.md) before changing shared state. One synchronized
table and immutable network are shared; mutable worker state stays private.
All helpers join before return/exception/resize/reload. `Threads=1` remains
default; 1–64 is configurable. Standard final node totals include unfinished
work; optional SMP diagnostics distinguish leader iterations from aggregate
events. Historical profilers/qualifications still use one worker.

Native/scalar/ASan+UBSan suites, 43 parallel UCI checks under all four native
build modes (including ThreadSanitizer), direct concurrent-search tests, and
24 profiler tests passed. The 24 parent/candidate one-worker searches were
exact; timing suggests a small possible one-worker cost. The independently
audited 72-search screen measured 3.25× aggregate throughput and 2.09× faster
nominal depth-6 completion with four workers; all nine timed four-worker pairs
completed +1 depth. No Elo gain, new GUI visual pass, or 64-worker/foreign runtime
qualification is claimed. Do not tune repeatedly against this bounded screen.

Phase 4B native/frozen candidate SHA-256:
`0abcb60f7271f17c9e8735095fbb48c72e425beef2647ae0ed24af6f7a5471e9`.
Raw checks/results/audit: `results/phase4b-20261018/`. New optional GUI bundle:
`build/test-baselines/0.1-dev-phase4b-20261018/`, with copied network and manifest.
Old GUI bundles, all frozen Phase 3L inputs/tools, and README introduction are
unchanged. The 512-game LMR campaign remains unstarted. At that checkpoint,
Phase 4C was next, with rule-50 semantics, absent-table fallback, provenance,
and independent reference validation explicit. No further SMP tuning subphase
is required before moving forward.

**Phase 4C is now complete**, implementation commit `2468d73`. Read [Syzygy](SYZYGY.md), the
[checkpoint report](reports/2026-10-18-phase4c-syzygy.md), and the vendored Fathom
provenance before changing tablebase behavior. The owner specifically authorized
the reader family used by Gargantua/Sic; only upstream Fathom was imported.
Search/evaluation and the adapter remain independent. Data is user-downloaded,
configured with `SyzygyPath`, and excluded from Git. Tables default to disabled.
Root DTZ filtering and zero-clock interior WDL bounds preserve own mate rules;
root repetition fallback, absent-table fallback, cancellation, and `tbhits`
have dedicated checks. Serialized process-global backend access uses generation
bindings. Basic header/length checks do not validate arbitrary compressed data.

Native/scalar/ASan+UBSan full suites and TSan search checks passed. All four
builds passed 140 exact WDL oracle roots with DTZ outcome/legal-move checks,
47 Syzygy UCI cases, and 12 direct tablebase/search clock scenarios. The three
GUI bundles, README introduction, and frozen Phase 3L campaign remain unchanged.
Default-off comparison: all 24 searches matched the Phase 4B parent exactly;
small timing variation is not a performance gain. Current normal binary SHA-256:
`9b5f03e02d9537041025dfd6a815a1ef734fb7a303a14bcaba17f1ea4f57e898`.
Raw evidence: `results/phase4c-20261018/`. No new GUI snapshot was created; normal
rebuilds continue to leave the owner's existing snapshots untouched.

**Phase 4D.1 is complete**, implementation `2cd3e66`: one opt-in quiet countermove
ordering candidate is implemented. The worker-local table keys the preceding move's original
colored piece and destination; root context is absent. Quiet beta-cutoff replies
rank below killers and above history, without changing quiescence, depth, or
pruning. Context is passed by value and policy changes clear cache/history.
`Countermove Ordering=false` remains the default. Native/scalar/ASan+UBSan/TSan
search checks and 57 independent-referee UCI cases per build passed. The
[predeclared profile](experiments/phase4d-countermove.md) uses 15 exposed roots,
fresh/warm state, depth 6 and 500 ms. All 360 searches completed. Cold total nodes
fell only 0.19%; warm nodes rose 3.78%; aggregate elapsed time rose 1.73%/6.27%.
All 90 fixed-depth pairs agreed on final scores/moves. Timed depth was unchanged
in 86/90 pairs and lower in four. Intermediate warm score deviations and root
variability are retained in [the report](reports/2026-10-18-phase4d-countermove.md).
Do not promote this candidate or start further tuning: park it as an opt-in
experiment. All 180 default-off parent checks matched, including warm reuse;
no default performance/Elo gain is claimed. That checkpoint's binary SHA-256 is
`bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f`.
Raw evidence and frozen executables are in `results/phase4d-20261018/` and
`build/experiments/phase4d-20261018/` respectively. Its follow-ups are the separate
4D.2 LMR qualification and 4D.3 null-move checkpoint recorded below.

**Phase 4D.2 has finished:** see the [protocol](PHASE_4D2.md) and
[preparation/launch record](reports/2026-10-18-phase4d2-preparation.md). It freezes
the existing `74a908b` executable separately, changing only LMR on/off across
1,024 paired games. Eight-worker exposed clock/cancellation checks and independent
serial readiness passed. Results live in `results/phase4d2-20261018/`. Preserve
all pinned sources until the one fixed campaign has ended and been audited;
never resume or replace games. The hard cutoff is the launch's next 07:00 Helsinki.
LMR remains off pending the complete result. Do not pool historical attempts or
retarget the untouched Phase 3L sample. The separate null-move implementation
does not change this campaign's frozen executable or strength gates.
The campaign launched October 18 at **23:13:40 Helsinki**, all eight shards
running, with a fixed October 19 **07:00** cutoff. Preparation commit: `d376524`.
Check the campaign manifest and raw records for current status; this timestamp
is launch evidence only. No recurring task was scheduled. Run the independent
auditor after completion before stating any strength/default decision. That
audit is now complete: [results](reports/2026-10-19-phase4d2-results.md).
All 1,024 games / 512 pairs finished at 05:34:17 Helsinki, with no exclusions,
audit errors or artifact drift. LMR scored 458W/299D/267L (59.3262%; conditional
95% score interval 53.3242–65.3282%). However, 19 candidate flagfalls (17 losses,
two draws) fail the fixed absolute reliability gate; baseline had 65 flagfalls.
Keep LMR off. Preserve `final-audit.json` and all raw records, diagnose clock
behavior before any new qualification, and do not rerun/extend/pool this sample.
The foreground match command has exited. This is an operational rejection,
not proof that LMR has worse timing than the baseline or a general Elo result.

**Phase 4D.3 is complete**, implementation `51c426a`:
[the report](reports/2026-10-18-phase4d3-null-move.md)
records restrictive verified null-move pruning, exposed through the default-off
`Null Move Pruning` option. Fictional-pass and legal verification subtrees isolate
history, transposition access, tablebases and ordering learning; ordinary search
defaults remain unchanged. Native/scalar/ASan+UBSan/ThreadSanitizer checks passed,
including 76 new UCI cases per build, direct API interruption/worker checks,
and incremental null-state tests. The initial TSan activation timeout and its
separate passing retry are both preserved; it was a test-harness allowance,
not a change to search limits or campaign rules.

The fixed 24-search screen matched all 12 parent/off signatures. All six on/off
pairs retained every per-depth score/PV and final move. Total cold nodes fell
16.47%, but warm nodes rose 6.08%. This mixed three-root development sample
does not establish speed or strength; timing cannot be interpreted while the
frozen LMR campaign shares the host. Keep null pruning off and do not repeatedly
tune this sample. Its successor is the 4D.4 checkpoint recorded below.
Any later null-move qualification needs separate quiet equal-time development
evidence and a frozen strength protocol.

Phase 4D.3 binary SHA-256:
`d0617575e7ece0dc3c38d4f44f33b6bc93adad8cf947a129af6dec137246b530`.
Raw evidence and frozen inputs are in `results/phase4d3-20261018/` and
`build/experiments/phase4d3-20261018/`. Existing GUI snapshots, frozen Phase 3L
assets, the completed Phase 4D.2 evidence, and the README introduction are intact.

**Phase 4D.4 is complete**, implementation `9ad2fe9`:
[reverse-futility report](reports/2026-10-19-phase4d4-reverse-futility.md).
`Reverse Futility Pruning=false` remains the default. This shallow interior
static cutoff has fixed margins and strict material, history, tactical and
special-score exclusions; both null-move speculative modes disable it.
Native/scalar/ASan+UBSan suites and TSan search checks passed, including 78 new
UCI cases per build, direct API lifecycle/composition checks and 26 profiler
tests. The profile finished all 60 searches with a separate passing raw-output
audit. All 12 parent/off pairs were exact; all fixed-depth final decisions and
common-depth score/PVs matched. Fresh-cache total nodes fell 12.72%, reused
nodes 1.53%; reused elapsed time rose 2.28%. One of six timed roots completed
one extra depth. These single-repetition observations establish no speed/Elo
gain or universal tactical safety. No margin changed after measurement.

At the Phase 4D.4 checkpoint, normal binary SHA-256:
`361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f`.
Raw evidence is in `results/phase4d4-20261019/`; frozen executables, manifest and
protected pins are in `build/experiments/phase4d4-20261019/`. All three documented
GUI snapshots, frozen Phase 3L assets, completed 4D.2 evidence and the README
introduction are preserved. Normal builds remain separate from GUI snapshots.

The accompanying [clock diagnosis](reports/2026-10-19-clock-diagnosis.md) checked
the 84 saved flagfalls without running engines or changing clocks/runner code.
For all 19 candidate failures, reported engine time was below the real remaining
clock; charged duration includes additional time whose location is unresolved.
Some records also exceed the internal hard budget. Do not blame a specific
component, raise overhead from these selected failures, or rerun qualification.
One short predeclared instrumented timing diagnostic is required before another
qualification; its concrete boundary measurements are in the report.

The next implementation at that checkpoint was **4D.5 quiescence work reduction**,
recorded below. Keep delta pruning separate. No further reverse-
futility tuning, default promotion, automatic schedule, new match or release
is part of this completed checkpoint. Preserve failed/inconclusive evidence.

The [search-efficiency plan](SEARCH_OPTIMIZATION_PLAN.md) prioritizes strength
over depth/NPS and includes the owner's new depth-10 transcript. Later pruning
hypotheses must be isolated and strength-qualified; do not enable existing LMR
without that evidence. Historical Phase 3L remains separate and unstarted.
Broader platform execution/trainer work is retained as Phase 4E.

Further experimental strength qualification, trainer integration, multi-platform
execution, release acceptance, and public strength claims remain open. The owner
can push the local commits. GUI `0.1-dev-4b8b35d` remains preserved; testing the
updated normal build is optional and must be labeled separately. Keep CHANGELOG entries
concise and create real version milestones when tested release gates pass;
research phases do not determine version numbers.

The unmodified SF19 match opponent is in ignored `build/stockfish19-reference`;
the instrumented NNUE oracle is separate. Never substitute one for the other.
Local GitHub authentication failed during initial setup; the owner's subsequent
instruction is to keep developing and committing locally while they push.

README contains the current runnable commands and limitations. CHANGELOG tracks
versions. [Architecture](ARCHITECTURE.md) describes boundaries, [validation](VALIDATION.md)
defines evidence, [portability](PORTABILITY.md) separates intended targets from
verified targets, and [NNUE](NNUE.md) owns the network pin and parity record.

## Current clock-boundary checkpoint — October 20, 2026

The [bounded diagnostic](reports/2026-10-20-clock-boundaries.md) is complete:
all 32 fresh-process searches returned within their transmitted clocks in
18.973 seconds. Maximum final accounted deadline overrun was 0.007375 ms,
position setup 0.160791 ms, and minimum reader-observed clock slack 19.734 ms.
The earlier large delays did not reproduce. No clock repair or strength
improvement is established; the old operational-failure decisions stand.

`make CLOCK_TRACE=1` builds separately with compile-time-only timestamps and
`clockping`; ordinary builds remain byte-identical to the 4D.5 parent.
Twenty-three engine-free tests, eleven live trace cases per native/scalar/
ASan+UBSan build, ordinary/scalar/sanitizer Search API checks and twelve exact
parent/normal/trace depth-4 comparisons passed. Full evidence, protocol,
limits and independent audit are linked in the report.

The subsequent **real-match readiness check at four active workers** passed,
as recorded in the current checkpoint above. Its 3+0.05 games test the proposed
lower concurrency without establishing a repair. Next freeze a separate fresh
qualification protocol for existing LMR and follow overnight/resource policy;
the previous daytime exception is consumed and no schedule exists. Decide
existing LMR's status before implementing broader 4D.6 reductions.

Protected GUI snapshots, all 40 pinned assets and the owner's modified
`tools/batch_positions.py` remain unchanged. The runner modification belongs
to the owner and must remain unstaged. The README introduction is preserved.

## Phase 4D.5 completed checkpoint — October 20, 2026

The isolated quiescence SEE filter is implemented, with native/scalar full
suites, ASan+UBSan, TSan Search/SMP checks and 98 new UCI cases per mode passing.
The [report](reports/2026-10-20-phase4d5-qsearch-see.md) records all guards,
limitations, evidence locations and the independent raw-output audit. The
60-search screen found 11.62% fewer fresh-cache nodes and 1.58% fewer reused
nodes; one timed root reached an extra depth. All final best moves matched,
but starting-position score/PV changes are recorded. No speed/Elo conclusion.

`QSearch SEE Pruning=false` remains the default. Switching it clears TT and
worker learning; diagnostic counters aggregate only after helpers join.
Never interpret its legal-LVA exchange estimate as proof against a sacrifice.
Delta pruning, other defaults, clocks and evaluation mathematics are unchanged.

The full matched **60,000-ms** puzzle comparison completed October 20,
15:41–16:59 Helsinki (78m05s), under the owner's explicit daytime exception.
Each build searched all 39 FENs with one worker, Hash 64 and the same NNUE.
Independent audit verified all 78 legal best moves, no missing/error scores,
59 source/protected hash checks and all six post-run hashes. Both reported
only M7 on position 2; the other 38 ended with centipawn scores. All best moves
matched, and only position 29's score differed (+9.16 to +9.59). No reported
mate gains, losses or distance changes; no Elo or certified-mate conclusion.

The separate 1,000-ms smoke also finished 39 positions per build without errors:
identical best moves, three centipawn-score differences and no positive mates.
The frozen existing-runner adapter and exact FEN/settings/source pins are in
`build/experiments/phase4d5-20261020/`; it accepts `parent|on ENGINE MOVETIME_MS`.
Complete printed outputs and independent audits are in
`results/phase4d5-20261020/`. Implementation commit: `8c772fe`.
Both searches and the launcher have ended; no schedule or new match exists.
The one-run daytime exception is consumed.

At that checkpoint, the next priority was the bounded clock-boundary diagnostic,
now completed above. No cause or clock repair is established yet. Validate any necessary repair and
operational readiness before a fresh qualification of existing conservative
LMR. Decide its status before adding broader 4D.6 reductions; do not rerun or
tune earlier campaigns or this exposed puzzle sample.

Current normal/frozen candidate SHA-256:
`eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
Parent `dcfd23c` has SHA-256
`361c9a2ab92a5702d046fc6d9cfa6cb4e0840defc74c098e67cf846ba8b9a57f`.
All 31 protected pins, three documented GUI bundles and README introduction
are intact. Preserve the owner's existing uncommitted `tools/batch_positions.py`
settings (Threads 8, Hash 64 and personal engine paths); this work does not
stage or commit them. Source/test/protocol pins freeze the candidate independently
of its subsequent commit. The owner still handles GitHub pushes.

## Before committing

The owner requested simplifying `tools/batch_positions.py`: it now embeds all
39 puzzle FENs in order, with editable engine/Threads/Hash/movetime constants.
It uses python-chess (`chess==1.11.2`) for UCI communication, starts a fresh engine
per FEN, and prints scores/best moves. The former XLSX reader, file exports, and
option-heavy CLI are removed. See the README and `tests/batch_positions_test.py`.
The owner also requested adopting the suite for development progress: include
matched before/after puzzle results at material search/evaluation checkpoints,
following [the comparison rules](VALIDATION.md#use-for-development-progress).
The first full baseline and matched candidate run completed in 4D.5; retain
their per-position results, including differences and absent mate progress.
This is auxiliary tooling; the current 4D.5 checkpoint is recorded above.

Run the relevant correctness checks and inspect the diff. Keep generated binaries,
large networks, external oracle source, and raw match output out of Git. Record
what actually ran and what did not. Update these documents when APIs, commands,
test evidence, or limitations change. Make a small local commit on main and leave
GitHub pushes to the owner. Do not amend unrelated commits or rewrite history.
