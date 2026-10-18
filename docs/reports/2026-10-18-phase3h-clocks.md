# Phase 3H clock accounting — October 18, 2026

**Retain the command-time accounting repair. Historical clock reliability remains
unresolved.** An ordinary timed search now charges preparation and worker startup
after the UCI loop receives `go`. Previously, its clock started inside the worker.
The reproduced defect and regression checks justify this correctness repair;
they do not establish that all 13 Phase 3G flagfalls are fixed.

The final native, scalar, and sanitizer suites passed. All 52 prescribed
saved-position probes returned legal moves on time, including all 26 baseline
probes. Thus the isolated probes **did not reproduce the historical losses**.
LMR stays off, classic timing and MVV-LVA stay selected, and Move Overhead stays
20 ms. No new strength result, rating, release, or default promotion follows.

## Scope and diagnosis

Work started from `8f23d7e` under the [bounded plan](../PHASE_3H.md). The audit
examined all 13 clock forfeits and all 50,352 original search boundaries. It
retains each full history, clock command, transcript timing, and source hashes.
All six candidate and seven baseline losses remain in the unchanged Phase 3G
result; none is excluded or rescored.

At the 13 failed moves, remaining clocks were 619.615–696.625 ms and external
overruns were 2.032–399.958 ms. In 12 cases, the completed search-info timestamps
tracked externally observed elapsed time within roughly 0.2–1.31 ms. These
records do not support a large initial accounting gap as their explanation.
They also lack final internal diagnostics, so they cannot locate the eventual
delay within search, scheduling, output, or the receiving process.

For `shard-4/p000049-2` (baseline), search-info receipt consistently lagged its
reported elapsed time by about 46 ms. That is consistent with an initial delay
outside the old search clock, but does not identify worker startup specifically:
queued position processing and transport are also outside that clock. Some
cross-shard delays cluster near 15:00 Helsinki, suggesting a shared host or
receiver effect worth investigating, not proving one. The runner charges receipt
in its Python process rather than kernel arrival at the pipe; clock rounding
alone cannot explain the observed overruns.

A deliberately cold `go movetime 1`, with Move Overhead=0 and no intervening
readiness, reproduced the accounting gap before repair. The baseline took
73.474/68.632 ms externally with LMR off/on, reported only 1.004/1.001 ms, and
searched 217/219 nodes after loading. Phase 3G prepared networks during readiness,
so this cold-load reproduction is **not evidence that network loading caused
the historical flagfalls**.

## Repair

`SearchLimits::received_at` optionally carries a monotonic receipt timestamp.
The UCI loop captures it before tokenization, preparation, and worker dispatch.
Ordinary clock and movetime budgets age from that point. Direct API calls that
omit it retain search-entry timing; a future timestamp is clamped to entry time.
An extreme-past timestamp saturates elapsed arithmetic safely rather than
overflowing. That edge case was found in review and fixed before final checks.

An already-expired request returns its legal fallback without starting tree work.
Pondering still charges only after `ponderhit`; infinite and no-clock bounded
searches preserve their existing semantics. Allocation formulas, search logic,
NNUE math, and per-node deadline checking are unchanged. The implementation adds
no timer thread or platform-specific scheduler control.

This repair cannot make cold network loading instantaneous, charge time before
the command is read, or ensure delivery while the engine or reader is descheduled.
Send `isready` and wait for `readyok` before a timed request. An artificial local
process-suspension control illustrates the boundary: pausing each tested build
for about 405 ms during a 620 ms movetime request produced roughly 810 ms replies.
This proves neither the historical cause nor the effectiveness of a larger
reserve; it demonstrates why command accounting alone cannot guarantee deadlines.

## Validation

The final executable passed `make -j2 test`, `make -j2 SIMD=scalar test`, and
`make -j2 MODE=sanitize test`. Added tests cover expired positive clocks for
both colors and LMR settings, explicit limits, ponderhit, infinite/no-clock
search, future and extreme-past origins, and UCI propagation through a dirty
network reload. Existing legal-move, incremental NNUE, search, cancellation,
and protocol lifecycle checks also passed. No new full Stockfish oracle run is
claimed; evaluator arithmetic did not change.

`make test-clock-probes` passed seven tooling tests, including command rejection,
illegal output, diagnostic validation, refusal to overwrite, and preserved
failure records. Each of 13 exposed full histories was searched once with LMR
off and once with LMR on on each executable: **52 probes**, fresh processes and
tables, network readiness completed, one active search worker. No failed probe
was replaced. Independent review confirmed all 52 bestmoves/ponders and all
363 PV lines / 1,794 plies legal, with all recorded input hashes intact.

| Measurement | Frozen baseline | Final repair |
| --- | ---: | ---: |
| Completed probes / on time | 26 / 26 | 26 / 26 |
| External elapsed range | 520.999–677.163 ms | 502.527–677.095 ms |
| External minus internal elapsed range | 0.107–0.252 ms | 0.073–0.186 ms |
| Minimum margin before remaining clock expires | 19.463 ms | 19.426 ms |
| Maximum reported internal hard-deadline overshoot | 0.003 ms | 0.003 ms |
| Hard / soft stops | 21 / 5 | 21 / 5 |

These are diagnostic observations with fresh state, not full match reproductions,
performance comparisons, or proof of freedom from clock loss. The final
fixed-depth comparison separately preserved all 48 search signatures across
12 development roots, depth 4, one warmup and one measured search per executable.
Its timings are not used to claim a speedup.

All work used local compute within the ordinary daytime budget, with at most
one active search worker for probes/comparisons and modest two-job builds.
No match or schedule was created. Both stable GUI bundles, `0.1-dev-4b8b35d`
and `0.1-dev-phase3f-20261017`, remain unchanged, as does the README introduction.

## Evidence and reproduction

Keep the entire ignored `results/phase3h-20261018/` directory. The final binary
is frozen at `build/experiments/phase3h-20261018/chess0live`; its manifest records
the source and artifact hashes. The network remains external and explicitly pinned.

| Asset | SHA-256 |
| --- | --- |
| Phase 3G baseline executable | `edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b` |
| Final repaired executable | `26849eb4a443c31a89fddb48aeffa9dc9e3998895043d95c9ed4409716564878` |
| `nn-1a298aa575a0.nnue` | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| `flagfall-audit.json` | `ed00bbea90b56f08904449978d2b6a56b93b7ed71d091d3f2ca162f2efaa6b62` |
| `flagfall-source-provenance.json` | `5a6bdc92761085c6de45737f477f23344bb869d7c7f6589ac7ff8e7bea067408` |
| `baseline-probes.jsonl` | `068a3dc5815db6d7d2332961ee780fe59f7eff3ea46966f447770e73859f9a35` |
| `repaired-probes.jsonl` | `6a8d2d5946d35c0a64233720392c13f3cf47e5ed6d7b23d9de2c56ab9895568b` |
| `fixed-depth-final-parity.json` | `a7942fc44017485c1897d2e14bb74c5bb5f0cfe7a3dde7b9c00432449721ac54` |

Provenance distinctions matter. The audit's initial live-source snapshots were
captured during implementation; its supplemental provenance record identifies
those as worktree snapshots and pins the actual baseline source from `500b022`.
Raw historical game/transcript measurements are unaffected. Saved
`repaired-cold-go.json`, `suspension-control.json`, and `fixed-depth-parity.json`
use intermediate repaired binary `3a29035bffdf9d5db36a72ad931c9d6641a517c46af2bb55f2f6bb42303c3cba`.
They remain preserved as development evidence. The final suites,
`repaired-probes.jsonl`, and `fixed-depth-final-parity.json` cover the final
`26849eb4…` executable, including the arithmetic hardening.

From the repository root, after installing `requirements-match.txt`, reproduce
the bounded diagnostic with a **new** output path (existing records are refused):

```sh
make test-clock-probes
python3 tools/probe_clocks.py \
  --engine build/experiments/phase3h-20261018/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --output results/phase3h-new-attempt.jsonl
```

Use the Phase 3G executable path for a separate baseline attempt. The default
fixture is `tests/data/clock-flagfalls-phase3g.json`. The tool validates its full
histories, applies fixed options, records receiver timestamps and diagnostics,
and stops on error without resuming. The receiver timestamp is still a host
observation, not a kernel or engine-emission timestamp.

## Next checkpoint: Phase 3I

Investigate short-clock resilience under scheduling and transport delays with
bounded, declared probes that distinguish engine work from reader delay.
Assess reserve/allocation changes as separate hypotheses, including their cost
in available search time. Preserve the original 13 losses and avoid tuning to
these exposed positions as if they were fresh qualification. Prepare another
LMR strength campaign only after the operational question is addressed. No
additional manual GUI tournament is required to accept this accounting repair.
