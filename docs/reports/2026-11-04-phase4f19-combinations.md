# Phase 4F.19 — current search combinations

Date: November 4, 2026. Single attempt stopped in preflight; measurement not run.

## Outcome

**No comparison result is available: 0/45 searches ran.** At **22:30:54 Helsinki**,
the supervisor's first power sample reported `Now drawing from 'Battery Power'`,
with battery **66%, discharging**. Before/after host files agree. The owner had
confirmed readiness, but the actual launch condition did not meet the frozen AC
requirement. The supervisor stopped before spawning the runner, sleep inhibitor
or any engine. This is a host preflight failure, not an engine/search failure.
Automatic mode and LM Studio state were not independently qualified for a run.

No `screen.json`, runner stdout/stderr, per-profile sample, move/score/PV/depth
comparison or timing statistic exists. Do not substitute zeros for unavailable
performance metrics. No default change, strength gain or all-on advantage can be
inferred. The only attempt is preserved; no retry, extra search or rebuild occurred.

The external OS check confirmed the sole experiment identity, supervisor PID
90478 with start `Wed Nov 4 22:30:54 2026`, had exited. No related runner, engine
or inhibitor process remained and no PID reuse was found. The cleanup receipt is
dated **22:35:14 Helsinki**; LM Studio was released immediately after confirmation.
No cleanup signal was needed. The existing Codex app-server parent predates the
attempt and is not experiment-owned.

## Independent audit and preservation

Preparation commit is **`fa920b8d31fe23850824021b5d37896cd54d97b0`**. Before launch,
`freeze.json` records **61 input identities**, including the unchanged binary,
network, corpus, production sources, protocol, runner, auditor, supervisor,
declared helper dependencies and interpreter. It is not a complete OS/dynamic
dependency freeze. The source engine remains implementation `9f8ff9f`.

The frozen independent search auditor ran **once**, exited **1**, and wrote
`audit.json` with status **failed**: `FileNotFoundError` for absent `screen.json`.
Its stdout/stderr and failed verdict are retained unchanged. The auditor stops
at missing input, so that receipt does not itself validate supervision or cleanup.
The separate **`prelaunch-failure-audit.json`**, status
**`prelaunch_failure_verified`**, independently checks the saved raw power samples,
guard placement before process launch, missing measurement artifacts, source
hashes and the external cleanup receipt. It relies on that approved OS receipt,
not a second OS snapshot. This is a verified prelaunch failure, not a passing
search comparison or replacement qualification audit.

All **1,631 protected paths**, **26 current engine source files** and **61 frozen
inputs** match. README introduction, owner batch-runner edit and stable GUI
`build/test-baselines/0.1-dev-4b8b35d/` are intact. Neither the historical
normal-release digest uncertainty nor the six Phase 4F.13 clock forfeits is
resolved. No publishing, game campaign or schedule occurred.

## Scope and preparation

The owner authorized the next phase and freshly confirmed LM Studio paused, AC
power and Automatic mode. The [prospective protocol](../experiments/phase4f19-combinations.md)
fixes 45 searches: all 15 original mixed roots, three profiles, five seconds each,
one fresh process per cell, rotated order, Threads 1 / Hash 64 and diagnostics off.
No engine implementation, build, network or default changes are made. The same
pinned Phase 4F.18 candidate executable is used for every profile.

Optional-off disables all ten optional search booleans; accepted defaults enable
only LMR; all-on enables all ten and uses SEE capture ordering. Core NNUE/PVS/TT,
killers and ordinary history remain in all profiles. Preserve the original root
histories. Search/setup has a 300-second bound, searches a 10-second reply bound,
and the external supervisor a 360-second backstop, followed by bounded evidence
publication. Reserve at least 2 GiB for the single resident engine and its optional
history/hint storage. Nominal depths, different-tree nodes and evaluations are
observations, not speed or strength qualification.

The new runner passed 21 engine-free tests, including the public Make target.
Independent read-only producer/test/supervisor review found no remaining blocker.
Five engine-free supervisor ownership assertions plus mocked cleanup cases verify
that reused PIDs do not become owned and each signal rechecks identity. Strict
handshake parsing was also checked against preserved raw output from the same
pinned candidate binary without launching an engine. No preparation engine run,
warmup, benchmark or rebuild occurred. The independent auditor passed 44
engine-free tests. Its earlier 36-test pass and a subsequent prelaunch indentation
error are retained; the syntax issue was corrected before the final passing run.
No measurement or frozen input was changed in response to results.

Preflight review corrected a positional-engine CLI mismatch, tightened wrapper
identity ownership and immediate pre-signal checks, and added bounded cleanup
when final verification finds survivors. The host parser supports both current
AC-only lowpowermode output and older powermode output without borrowing another
policy section. The external AC sample interval has a predeclared three-second
maximum; per-cell observations also require Automatic mode. All fixes precede
measurements and logs are preserved.

## Next step and evidence

The initial optional-off/default/all-on diagnosis remains pending. A future
attempt needs authorization, verified AC/quiet-host conditions and a new evidence
directory; preserve this attempt and its frozen inputs. Do not skip ahead to
component-removal tests or select a package without the initial result. If the
comparison later shows useful differences, freeze a separate leave-one-out scope
that respects the LMR/deep-reduction, ordering/history and delta/SEE dependencies.
No automatic retry, future run, game, default promotion or Elo claim is authorized.

Evidence is under `results/phase4f19-combinations-20261104/`: `freeze.json`,
`supervision.json`, raw before/after host files, `cleanup.json`, failed `audit.json`,
`prelaunch-failure-audit.json`, preparation test logs and source copies,
`post-attempt-preservation.json` and documentation validation. The protocol stays
unchanged so the declaration and failed attempt remain reviewable.
