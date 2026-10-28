# Phase 4F.9 — Continuation History tactical qualification

Protocol `phase4f9-continuation-puzzles-v1`, October 28, 2026. Freeze this
protocol and all inputs before the first readiness or smoke session. This is
the tactical checkpoint following Phase 4F.8, not a new search implementation.

## Question and fixed inputs

Does the isolated Continuation History option introduce concerning tactical
losses on the owner's existing 39-position set at an equal 60-second budget?
The Phase 4F.8 development screen found mixed work changes (+0.95% aggregate
nodes), with matching final moves and scores. It did not establish a speed or
strength gain. Ordering can alter LMR decisions even without changing pruning
predicates, so the tactical check is still necessary.

Both roles use the same previously tested executable, copied without rebuilding:

- Source revision: `69215b4c7a35bb0ba7ea4b1e9287e8f760199b6c`.
- Executable: `build/experiments/phase4f9/chess0live`, SHA-256
  `c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Positions: all 39 entries, in their original order, from
  `tests/data/phase4f3-puzzles.json`, SHA-256
  `a49062bd0aa5b8d3af66842b266b4f8a8f7871cf64392a96861ea2faa2f5d035`.
- Annotation provenance: the literal position list in `tools/batch_positions.py`,
  SHA-256 `9fe64dc972744c8589bdfde1ac4b29f1c9bc44931922aafe5b88dc9e9d140c1c`.
  Parse that literal without executing the owner's tool. Supplied best moves and
  mate distances are comparison labels; never pass them as search restrictions.

The new build manifest records all 27 original source, Makefile and Fathom
dependency files under its own `source/` directory. Their bytes must match both
the preserved Phase 4F.8 build inputs and the committed revision. Preserve the
original build manifest alongside the copy. `tests/data/phase4f9-pins.json`
freezes these files, the executable, network, corpus, protocol, runner,
independent auditor, their synthetic tests and transitive local tooling. Check
identities before and after each attempt; do not silently refreeze a failed run.

## Matched settings

| Setting | Both roles, except where stated |
| --- | --- |
| Role names | `continuation-off`, `continuation-on` |
| Continuation History | `false` for off; `true` for on |
| Threads / Hash | 8 / 64 MiB |
| Late Move Reductions | `true` |
| TT Move Hints | `false` |
| Deep Quiet Reductions / Countermove Ordering | `false` |
| Null Move Pruning / Reverse Futility Pruning | `false` |
| QSearch SEE Pruning / ProbCut | `false` |
| Capture Ordering / Time Policy | `mvv-lva` / `classic` |
| Ponder / Search Diagnostics | `false` |
| SyzygyPath / SyzygyProbeLimit / SyzygyProbeDepth | `<empty>` / 0 / 1 |
| Move Overhead | 20 ms |
| EvalFile | Absolute path to the pinned network |

Only Continuation History differs. The enabled table adds 9 MiB across eight
workers, outside Hash. Reserve at least 2 GiB for the one resident engine and
run only one search at a time. A UCI request for eight threads is not itself a
measurement of CPU utilization. Diagnostics stay disabled during qualification;
the preceding implementation phase tested allocation and activation separately.

## Finite sequence and operating conditions

1. **Readiness:** two fresh sessions, one per role, no searches. Verify the
   exact 21-option handshake, all settings, network readiness and clean exit.
2. **Smoke:** every position under both roles, 78 searches at 1,000 ms each.
   Independently audit the raw transcripts. This checks operation only.
3. **Full:** every position under both roles, 78 searches at 60,000 ms each,
   about 78 minutes plus setup. Commit the tested preparation first and obtain
   an agreed quiet window before launching. Do not schedule automatically.
4. **Audit and decision:** independently reconstruct the full attempt; record
   all observations and failures before deciding whether a separate paired
   game qualification is justified. Do not change engine defaults here.

Use a fresh process, `ucinewgame`, a cold hash and a new `position fen` command
for each role/position. Alternate role order by position to reduce simple order
bias. Send `go movetime` without answer hints or a depth/node constraint. Retain
all completed iterations, best/ponder, process events, timestamps and EOF.

Short readiness and smoke checks are modest correctness checks; do not interpret
their elapsed times as performance evidence. The full run requires paused
competing LM Studio inference, no competing builds or benchmarks, AC power and
unchanged Automatic power mode. The model may stay loaded. Resource limits remain
50% daytime and 80% from 23:00–07:00 Europe/Helsinki. Long tests run overnight
unless the owner grants a fresh timing exception. CLI flags attest to operating
conditions; they neither grant permission nor continuously measure power mode.

The full attempt needs at least 84.5 minutes remaining before the next 07:00
cutoff, even with a daytime exception, and has a two-hour overall watchdog.
Check wall/monotonic clock continuity, reject unexplained gaps above five seconds,
and recheck resource admission at least every two seconds during waits. The
five-second per-search watchdog grace is for termination, not usable thinking
time: allow at most 250 ms beyond the requested budget at result receipt. Every
session must quit, return zero, deliver EOF and finish its reader. Preserve
failed/incomplete attempts; never retry, resume, pool or replace them silently.

## Independent audit and interpretation

`tools/audit_phase4f9_puzzles.py` must not import the runner's result parser,
validator or summary. Reconstruct the exact command/response sequence, roles,
complete matrix, option defaults and settings, process cleanup, resource samples,
receipt clocks and asset hashes. Replay every reported PV, best move and ponder
move with independent chess rules. Cross-check the generated report against raw
logs instead of trusting its summaries. Write each audit to a fresh path outside
the attempt directory.

Report per-position final move and score, supplied-move matches, positive mate
reports gained/lost, reported mate distances, and legal PV endings. A higher
centipawn score is not a distance to mate; a legal mating PV does not prove mate
against all defenses. Supplied answers are not an independent oracle. SMP results
are nondeterministic, and this exposed corpus is not a fresh statistical holdout.

Any operational failure leaves the comparison unqualified. Review all tactical
losses, including lost mate reports and changed supplied-move matches. A suspected
serious regression needs a separately documented, bounded reproduction; preserve
the original result and label follow-up analysis as post hoc. Do not select only
favorable positions, tune against this set, or enlarge this attempt. Even an
apparently clean tactical result cannot establish Elo, strength non-regression,
or justify automatic promotion. A game test needs its own declared protocol.

Preserve the normal release executable, GUI snapshot `0.1-dev-4b8b35d`, owner
batch settings and all earlier frozen experiments. Starting identities are in
`results/phase4f9-preparation-20261028/initial-state.json`. Phase 4F.7 remains
closed, with TT Move Hints off and its inconclusive match evidence intact.
