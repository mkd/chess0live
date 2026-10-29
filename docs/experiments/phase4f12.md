# Phase 4F.12 — NNUE efficiency tactical comparison

Protocol `phase4f12-nnue-puzzles-v1`, October 29, 2026. Freeze this protocol,
tools and input identities before readiness or smoke. This is the equal-time
tactical checkpoint following [Phase 4F.11](../reports/2026-10-29-phase4f11-nnue.md).

## Question and fixed inputs

Does the affected-feature NNUE implementation preserve or improve observed
tactical results on the owner's complete 39-position suite at equal time?
Phase 4F.11 established exact arithmetic and deterministic single-worker search
agreement, with roughly 5% greater execution rate on its exposed finite sample.
That does not establish more solved puzzles, SMP performance or playing strength.

Reuse the tested binaries without rebuilding. Copy their bytes and archived
sources into `build/experiments/phase4f12/{baseline,candidate}/`:

| Role | Committed source | Executable SHA-256 |
| --- | --- | --- |
| baseline | `1ca87d6a596531d19b7b698b84c171fc314fc046` | `8230cb3dd174952866d8c2e9d1eae7f327183b286b393246c6bd7c041a86eabc` |
| candidate | `3ee5eff30981b73099e8a118ff1712f89cdc285a` | `04ef939940ed241f435d6138bcb19213ece28945b347a2ec394e11673109c594` |

The original binaries are `build/experiments/phase4f11-baseline/chess0live` and
`build/experiments/phase4f11-candidate-v2/chess0live`. Both were compiled with
`-std=c++2c -Wall -Wextra -Wpedantic -pthread -O3 -DNDEBUG -g`. Each new role
manifest records source revision, executable/network hashes, complete copied
source inventory, original Phase 4F.11 manifest and build log. Source copies
must agree with their original manifest and committed revision; do not substitute
current files or the rejected first candidate. The auditor reconstructs both
inventories independently. Original evidence remains untouched.

- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Corpus: every entry in `tests/data/phase4f3-puzzles.json`, SHA-256
  `a49062bd0aa5b8d3af66842b266b4f8a8f7871cf64392a96861ea2faa2f5d035`.
- Owner source: the literal list in `tools/batch_positions.py`, SHA-256
  `9fe64dc972744c8589bdfde1ac4b29f1c9bc44931922aafe5b88dc9e9d140c1c`.
  Parse it without executing or modifying its settings. The supplied labels are
  mate distances, not expected best moves; best-move accuracy is unavailable.

`tests/data/phase4f12-pins.json` freezes both builds, their provenance, corpus,
network, protocol and transitive tools/tests. Check identities before and after
each attempt and before every session. Never silently refreeze a failed attempt.
Each sample and raw process-start event identifies the role's executable path
and hash; identical UCI names alone cannot establish treatment assignment.

## Equal settings and finite sequence

Both roles use Threads=8, Hash=64 MiB, LMR=true, classic time policy, MVV-LVA
capture ordering, Move Overhead=20 ms, and the same absolute EvalFile path.
TT Move Hints, Continuation History, Deep Quiet Reductions, Countermove Ordering,
Null Move Pruning, Reverse Futility Pruning, QSearch SEE Pruning, ProbCut,
Search Diagnostics and Ponder are false. SyzygyPath is empty, ProbeLimit=0 and
ProbeDepth=1. Only the executable implementation differs.

1. **Readiness:** one fresh process per role, exact 21-option handshake,
   configuration and clean exit; no position or search commands.
2. **Smoke:** all 39 positions under both roles, 78 searches at 1,000 ms each,
   followed by an independent raw audit. This validates operation only.
3. **Full:** the same matrix at 60,000 ms per search, approximately 78 minutes
   plus setup. Commit tested preparation and agree a quiet window before launch.
4. **Audit:** independently reconstruct all results and adverse differences.
   Any game-based qualification requires its own prospective protocol.

Every role/position gets a new process, `ucinewgame`, cold state and `position fen`.
Alternate baseline/candidate order by position, preserving all original FENs and
their order. Send `go movetime` without answer hints or depth/node limits. Save
every consumed output line, command, process event, timestamp and EOF.

## Operating and failure boundaries

Run one engine at a time, with eight active search workers and at least 2 GiB
reserved memory. Verify admission against detected resources: 50% daytime and
80% from 23:00–07:00 Europe/Helsinki. These are scheduling/reservation estimates,
not measurements of OS utilization. Short readiness/smoke checks do not establish
performance and may run within the ordinary daytime budget.

Full comparison requires paused competing LM Studio inference, no competing
builds/benchmarks, AC power, Automatic mode and an awake Mac throughout. The model
may remain loaded. Long tests run overnight unless the owner explicitly grants
a daytime exception for this comparison. Earlier permissions covered earlier
runs or short comparisons. CLI assertions record the operator's statement; they
are not approval or continuous power/load telemetry. No automatic schedule.

Full admission requires 84.5 minutes before the next 07:00 Helsinki cutoff,
including any authorized daytime launch. Retain a two-hour total watchdog,
five-second discontinuity/poll-gap checks, resource checks every two seconds
during waits, five-second search watchdog grace and separate 250-ms maximum
result-receipt overrun. Early completion is allowed. Every process must exit
zero, deliver EOF and finish its reader. Suspend/resume invalidates continuity.
Preserve all failures and incomplete evidence; no silent retry, resume,
replacement, pooling, extra positions or selective exclusions.

## Independent audit and decision

The new auditor must not import the runner's parser, validation or summary.
Independently verify binary assignment, equal options, complete alternating
matrix, raw command/response sequence, source/provenance identities, resource
samples, clocks and process exits. Replay every PV, best move and ponder move
with pinned independent chess rules. Write audits to fresh external paths.

Report all per-position final moves and scores, mate reports gained/lost,
reported mate-distance and first-report-time changes, completed depth and legal
PV endings. Centipawn changes are not mate distance; a legal mating PV is not
proof against every defense. These exposed SMP observations are nondeterministic
and are not a held-out or repeated statistical test. Do not claim a speedup,
Elo gain, equivalence or universal nonregression from this comparison.

Any operational failure leaves the attempt unqualified. Review all tactical
losses, especially lost positive mate reports. A suspected serious regression
requires a separately documented bounded reproduction, labeled post hoc; it
must not replace the original attempt. A clean result permits consideration of
the next strength test, not automatic setting promotion or release. Preserve
normal release, GUI `0.1-dev-4b8b35d`, owner settings and all previous campaigns.
