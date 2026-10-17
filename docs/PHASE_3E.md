# Phase 3E: endgame requalification with a longer pawn workload

Status: **complete; qualified on this revised composed endgame sample**. The
[result report](reports/2026-10-17-phase3e-endgames.md) records ratios 1.089113
and 1.084243, all 216 exact/legal searches, two individual candidate slowdowns,
and absolute-time drift. Engine code and defaults are unchanged; Phase 3C's
original endgame/combined decisions remain inconclusive. This later status note
does not alter the frozen protocol at `results/phase3e-20261017/protocol.md`,
SHA-256 `07a0407459d98f1f0237cc38fe53f00e263e2b9d9383114c33f2ce2b775e09a3`.
The original instructions below govern the complete new comparison.

## Fixed roots and artifacts

Use all six endgames from the original
[game-phase suite](../tests/data/performance-gamephases.json), SHA-256
`38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c`.
These are exposed composed FENs with empty histories, not new held-out roots
or a representative sample of tournament play. Confirm valid, unique,
nonterminal roots without claimable draws with pinned `chess==1.11.2`.
Historical reachability and earlier repetitions are not established.

- **Main group, depth 8:** `gamephases-eg-01`, `-02`, `-03`, `-04`, `-06`,
  in original suite order.
- **Pawn group, depth 12:** `gamephases-eg-05` only, proposed by the completed
  [Phase 3D diagnostic](reports/2026-10-17-phase3d-workload.md).

Depth 12 was chosen after the short-duration finding, using a baseline-only
ladder, not a candidate comparison. It passed a three-pair diagnostic heuristic
with near-limit variability; fresh controls remain mandatory. Keep both depths
fixed for this entire campaign. Do not substitute roots or adapt repetitions.

Baseline: `build/experiments/phase3a-20261016/release/chess0live`, source
`9daaade`, SHA-256
`7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
Candidate: `build/experiments/phase3b-20261016/release/chess0live`, source
`eb059b5`, SHA-256
`2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae`.
Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Use unchanged `tools/compare_bench.py` and dependencies; pin their hashes,
production sources, protocol, suite, position files, launcher, and preserved
binaries in a premeasurement manifest. Preserve GUI `0.1-dev-4b8b35d`.

Settings: Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA,
Ponder/diagnostics off, Move Overhead 20 ms. Set Threads/Hash/EvalFile explicitly;
verify other fresh-process defaults from recorded UCI identities and pinned
setup code. The helper records raw replies but not outgoing setup commands.
Clear search state and complete readiness before each externally timed
monotonic go-to-bestmove search. No clock-managed search, books, or CPU sampler.

## One bounded campaign

Use fresh processes per comparison, one warmup per root/role, then **five
measured repetitions**. The unchanged helper alternates role order by local
position index plus repetition. Splitting groups resets the index: each group
starts with baseline first. Each complete round has 16 baseline-first and
14 candidate-first measured pairs; preserve this known imbalance and report
order-group results. No order or sample exclusions may be made after timing.

| Run | Group/depth | Baseline role | Candidate role | Searches including warmups |
| --- | --- | --- | --- | ---: |
| control-main | Main / 8 | Baseline | Baseline | 60 |
| control-pawn | Pawn / 12 | Baseline | Baseline | 12 |
| timing-main-a | Main / 8 | Baseline | Candidate | 60 |
| timing-pawn-a | Pawn / 12 | Baseline | Candidate | 12 |
| timing-main-b | Main / 8 | Baseline | Candidate | 60 |
| timing-pawn-b | Pawn / 12 | Baseline | Candidate | 12 |

Run exactly in this order: **216 searches**, including **36 warmups and 180
measured searches**. Only one worker searches, with two resident engines. Use
the ordinary 50% daytime/80% nighttime policy and combined memory planning;
no override or automatic schedule. Do not run concurrent builds, engine tests,
matches, or CPU profiles. Host background work, core placement, and thermal
state are uncontrolled.

Bound each search to **30 seconds**, each comparison to **300 seconds**, and
the complete campaign to **600 seconds**. Recheck frozen identities before
each comparison and after completion. On timeout, interruption, resource or
identity failure, or search-signature mismatch, clean up the process group,
preserve partial evidence, and mark remaining runs not started. Independent
legality and cross-run checks follow completion; their failure invalidates
inference. Timing-gate failures alone do not terminate the declared campaign.
No extra run or immediate retry is permitted to seek a passing result.

## Aggregation, audit, and decision

Reparse every raw response, including warmups. Require identical per-iteration
depth/seldepth/nodes/score/PV, bestmove and ponder for each root across both
roles, repetitions, and all three rounds. Replay every PV/bestmove/ponder with
the independent referee. Verify expected inputs, counts/order, exact commands,
resource metadata, settings, identities/hashes, lifecycle/timing consistency,
and independently recompute stored summaries. Incomplete or invalid evidence
means **invalid/incomplete**, never a pass from the surviving groups.

Form three rounds: control (both control files), A (both `-a` files), and B
(both `-b` files). Each round contains **30 measured pairs: five per root**.
Pool those 30 individual baseline-time/candidate-time ratios directly for its
median and MAD. Do not average group medians, weight by elapsed time, or give
the one-root pawn group equal weight to the five-root main group. A higher
ratio favors the candidate. Controls use the same binary in both roles.

Apply these rules in order, using unrounded values:

1. **Noise and duration:** the complete control's median ratio must be in
   **[0.97, 1.03]**, its paired MAD **≤0.03**, and each control root's median
   ratio in **[0.95, 1.05]**. Every root/role median duration in every round must
   be **≥0.050 seconds**. Failure makes the endgame result **inconclusive**.
   The 200 ms Phase 3D target was a workload-selection margin; the qualification
   floor remains the original Phase 3C 50 ms rule for every root.
2. **Root regression guard:** pool each root's ten measured candidate pairs
   from A and B; every root's median must be **≥0.98**. A failure after step 1
   is an **observed regression-guard failure**, requiring separate retention
   review. Report it even if aggregate ratios pass.
3. **Positive aggregate:** both complete candidate rounds must independently
   have median ratio **≥1.03**. Otherwise the gain is **unconfirmed**.
4. Only when all prior gates pass is the result **qualified on this revised
   six-root endgame workload**. No retrospective Phase 3C or pooled cross-phase
   qualification follows.

Report all per-root durations, ratio dispersion and order effects, complete
round statistics, subgroup statistics for transparency, and every individual
measured slowdown. Preserve failures and inconclusive results. These are
engineering acceptance rules, not confidence intervals or Elo estimates.
Even a pass establishes only sampled throughput on this host with these
settings. Clock-managed strength, universal endgame performance, scalar/foreign
runtime speed, further optimization, parallel search, and release acceptance
remain separate work. The retained Phase 3B implementation stays unchanged
unless a subsequent explicit correctness/retention investigation warrants a fix.
