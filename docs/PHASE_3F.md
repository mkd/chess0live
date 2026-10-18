# Phase 3F: profile the retained engine and test one NNUE improvement

Status: complete and retained; all frozen correctness and performance gates passed. This phase profiles the retained Phase 3B engine
across existing game phases, fixes one implementation hypothesis from the
findings, and accepts it only with exact correctness and measured performance.
No search policy, network architecture, or strength claim changes here.

## Preserved baseline and workload

Baseline: retained `build/experiments/phase3b-20261016/release/chess0live`,
source `eb059b5`, SHA-256
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.
Pinned network: `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Preserve the normal native executable, GUI `0.1-dev-4b8b35d`, prior frozen
candidates, raw evidence, and original suites. No prior engine assets are used.

Use all 12 existing development opening histories in original order at depth 5;
all six existing composed middlegames at depth 6; and all six existing composed
endgames at depth 8, except `gamephases-eg-05` at depth 12. Retain full histories
for openings. These exposed development inputs are not held-out match evidence.
Composed FENs have empty histories; validity does not prove reachability.

Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA, Ponder/diagnostics off,
Move Overhead 20 ms; use the pinned default network. Profile setup explicitly
sets every option. Comparison setup sets Threads/Hash/EvalFile and checks the
other fresh-process defaults using UCI identities and pinned source. Clear
search state/readiness before every timed search. No clock-managed search.

## Step 1: bounded current-engine profiling

Generalize the existing CPU recorder to 1–64 distinct legal nonterminal roots,
with optional integer `profile_depth` (1–12) per JSON entry. Keep fixed depth-5
warmups and preserve the existing 12-opening default. Mock-test counts, depth
selection, validation, partial failures, and cleanup before real profiling.

Build the unchanged baseline source separately with ordinary generic ARM64
C++26 `-O3 -DNDEBUG` plus `-g`, and generate a dSYM. Record compiler, flags,
source/binary/network/tool/suite hashes and host/resource metadata. Verify
sampled equivalence against the preserved release on all 24 roots using four
comparison groups (opening/MG/main-endgame/pawn), one warmup and one measured
pair per root: **96 searches**. Per-search timeout 30 seconds, comparison cap
300 seconds, equivalence campaign cap 600 seconds. No speed claim from symbols.

Then profile three groups sequentially with macOS `/usr/bin/sample`, 1 ms
requested interval. One depth-5 warmup per root precedes **two sampled sweeps**:

| Profile | Roots | Measured depth | Sampling window | Outer bound |
| --- | ---: | --- | ---: | ---: |
| opening | 12 | 5 | 30 seconds | 90 seconds |
| middlegame | 6 | 6 | 60 seconds | 120 seconds |
| endgame | 6 | 8, pawn root 12 | 60 seconds | 120 seconds |

Total **72 profile searches**: 24 warmups and 48 sampled searches. Observe
sampler readiness and require every measured search inside the conservative
window. Keep the process alive until sampling finishes naturally. Reject
incomplete/out-of-window coverage; preserve failures. A process-inspection
sandbox rejection may be retried only with the required permission and a fresh
output path, preserving the denied attempt. Do not tune durations after a real
coverage failure to seek a preferred hotspot.

Independently replay all PVs/bestmoves/ponders, compare signatures to release
where depths agree, and compare common iteration prefixes for depth-5 warmups.
Audit raw stack identity, sample lifecycle, source/input hashes, thread totals,
and disjoint residual attribution within `Search::search`. Separate idle/setup
stacks and overlapping inclusive costs. Report each phase separately; aggregate
stacks cannot establish per-root cost or exact cycles. Sampling perturbs timings.

Select one bounded NNUE change from significant measured cost and code review.
Append and commit its exact hypothesis/invariants/tests before implementation.
If evidence does not support an isolated change, complete the phase honestly
with findings rather than implementing an arbitrary optimization.

## Step 2: correctness before acceptance timing

Keep evaluator features, numerical outputs, parser/format, search, options, and
position semantics exact. No combination of unrelated kernels or layout changes.
Add an independent arithmetic/feature oracle appropriate to the chosen change,
including boundary/adversarial cases; shared full-refresh code is insufficient.

Run native, forced-scalar, and ASan/UBSan engine suites, retaining perft/rules,
UCI lifecycle, search, 360 update-arithmetic transitions, and 537-position
incremental checks. Rerun the pinned external SF19 stage oracle on the unchanged
2,057-position corpus for native and scalar; require identical features,
accumulators, transformed inputs, affine/activation stages, and outputs.
Use an isolated copied reference checkout; no upstream code enters the engine.

Correctness failures block performance inference and require a reproducible fix.
Freeze tested candidate, parent, network, sources/tools, and all timing inputs
before acceptance timing. Test-driven implementation repairs are permitted;
no candidate tuning or repeated timing runs after observing acceptance results.

## Step 3: one fixed all-phase performance screen

Use the unchanged equal-work comparison helper and four groups: 12 openings,
six middlegames, five main endgames (`01,02,03,04,06`), and pawn (`05`). Depths
are fixed above. Run control groups in that order, then all four candidate A
groups, then all four candidate B groups, for **12 comparisons**. Control uses
the preserved retained baseline in both roles; A/B use that baseline versus the
new candidate. Each group uses fresh processes, one warmup per root/role and
**three measured pairs per root**: **576 searches**, including 144 warmups and
432 measured searches. The 72 pairs per round give equal weight to each root;
assess openings, middlegames, and endgames separately, never hiding one phase
in a favorable combined statistic.

Per-search timeout 30 seconds; per-comparison outer cap 300 seconds; complete
campaign cap **1,200 seconds**. Stop on correctness, identity, resource, timeout,
or interruption failure, clean up children, preserve partial data, and mark
unstarted runs. Do not stop early merely on a timing gate failure. No extra
repetitions, exclusions, substitutions, or immediate repeat of this campaign.

Independently audit every raw iteration/PV/bestmove/ponder including warmups,
exact agreement across roles/repetitions/rounds, expected counts/order, identities,
settings, resource metadata, timing/lifecycle consistency, and raw summaries.
Incomplete or invalid evidence never qualifies the candidate. For each phase:

1. Fresh control median ratio in **[0.97,1.03]**, paired MAD **≤0.03**, every
   root control median **[0.95,1.05]**; each role/root/round median time **≥50 ms**.
   Failure makes the phase inconclusive, irrespective of candidate ratios.
2. Pool each root's six A/B pairs: every median ratio **≥0.98**. Failure after
   noise/duration pass is an observed regression-guard failure.
3. Both candidate rounds independently have phase median ratio **≥1.03**.
   Otherwise the phase gain is unconfirmed.
4. Retain the new implementation only if **all three phases pass**. Otherwise
   preserve candidate patch/binaries/evidence and restore parent production code.

Ratio is baseline elapsed/candidate elapsed. Merge the two endgame groups by
all individual paired ratios, not group medians. Local index order restarts
per group: each round has opening 18/18, middlegame 9/9, and endgame 10/8
baseline-first/candidate-first pairs. Report these imbalances, each phase/root
median and dispersion/order effects, and every measured slowdown. Three pairs
per root are an engineering screen, not confidence intervals or Elo evidence.

## Resources and delivery

One engine search worker at a time; at most two resident engines for comparisons,
one plus the sampler during profiling. Builds use at most two jobs. Honor
50% daytime and 80% 23:00–07:00 Europe/Helsinki; no cloud, paid compute, or
automatic schedule. Avoid competing engine/build/profile jobs during measurement.
Long acceptance timing runs in the nighttime window; short correctness and
profiling checks can use the ordinary daytime budget. Unrelated host activity,
CPU placement, and thermal state remain uncontrolled and must be reported.

Update README, CHANGELOG, roadmap, validation, and handover; record the full
result and failed/inconclusive observations. Commit tested work locally on main;
the owner publishes manually. A retained implementation permits an optional GUI
retest with a separately labeled build; never overwrite the preserved snapshot.
No release or strength rating follows from this research checkpoint.

## Selected hypothesis — frozen after profiling, before implementation

Preparation commit `dd3d269` produced 96 exact/legal release/symbol equivalence
searches and 72 exact/legal profile searches. Independent audits passed; evidence
is in `results/phase3f-20261017/`. All profiles finished within their windows.
The symbol binary SHA-256 is
`74d27965680eb1bfaf8d4e58c9e439bd67d4665c44e747d21ff49684dc687e18`;
its Mach-O/dSYM UUID is `A175FC5E-C7ED-39A6-B764-7CA894FAE6EA`.

| Profile | Search observations | NNUE share | Inclusive inference | Exclusive first-layer call site |
| --- | ---: | ---: | ---: | ---: |
| Opening | 7,455 | 83.84% | 28.92% | 26.22% |
| Middlegame | 24,888 | 79.63% | 29.62% | 27.09% |
| Endgame | 16,293 | 74.36% | 46.76% | 42.39% |

First-layer attribution is to optimized `infer` source line 533, containing
`stack.first.run`; it is approximate inline source attribution, not measured
load latency or bandwidth. Categories overlap and are not added together.

**Hypothesis:** processing four output rows together in the existing NEON dense
kernel can reuse each 16-byte activation load and expose four independent
accumulation chains. Apply this one transformation to the existing 1024×32 and
64×32 layers. Keep row-major weights, file format, feature generation, accumulator
updates, activations, evaluation calibration, and search unchanged. No transpose,
sparsity, dot-product extension, new instruction requirement, or parameter tuning.
The scalar path and the 128×1 output fallback remain unchanged.

Use four explicit int32 vector accumulators and a compile-time multiple-of-four
output branch. Assert positive input dimensions divisible by 16 and a proven
product-sum bound. Activations are in [0,127], weights in [-128,127]; at most
1024 products have magnitude at most 16,646,144 in total. Partial and horizontal
product sums fit int32. Bias may be any int32 value: widen the product sum and
bias to int64 before preserving the existing modulo-2^32 conversion. No signed
C++ overflow, saturation, intermediate narrowing, or changed integer grouping
outside this proven domain.

Add an independent int64 dense arithmetic test for all three actual shapes,
covering zero/max activations, extreme signed weights and biases, cancellation,
one-hot values at vector/tile boundaries, deterministic random inputs, repeated
calls, and input/model immutability. Integrate it into the standard NNUE target
for native, forced-scalar, and sanitizer builds; do not compare only two shared
production paths. The previously fixed correctness, full SF19 oracle, and all
three game-phase performance gates remain unchanged.

## Completed checkpoint

Implementation `500b022` passed the independent arithmetic, full engine, and
2,057-position stage oracle checks. All 576 timing searches matched exactly and
replayed legally. Every phase passed its control, duration, pooled-root, and
both-round improvement gates. The [result report](reports/2026-10-17-phase3f-dense.md)
contains complete root/order/drift tables and all four individual slowdowns.
Opening gains were 19.6%, middlegame 19.7–21.4%, and endgame 32.4–39.5% relative
to retained Phase 3B. Significant absolute-time drift limits generalization.
No Elo, new release, scalar/foreign-platform speed, or search-default change is
claimed. Preserve the original protocol snapshots and raw evidence; no campaign
was repeated or selectively extended. All jobs ended; publishing remains manual.
