# Phase 4F.19 — current search combinations

Date: November 4, 2026. Initial comparison prepared; measurement not yet run.

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

## Pending execution and interpretation

Freeze inputs before the single authorized run. Preserve full command/readiness/
search/shutdown transcripts, source/interpreter identities, host samples, all
changed moves/scores/PVs and per-engine exits. The independent auditor must replay
raw evidence and matrix ordering, check legal moves and source/host/cleanup records,
and preserve descriptive observations alongside any nonpassing verdict. Never
overwrite an audit or retry a cell. Confirm external OS cleanup and release LM
Studio before further analysis.

The finite checkpoint ends with a diagnosis and the next separately frozen
component-removal proposal. No game campaign, automatic schedule, default promotion
or Elo claim is implied. The six historical clock forfeits and normal-release
digest uncertainty remain unresolved. Preserve the owner's batch-runner edit,
README introduction, stable GUI `build/test-baselines/0.1-dev-4b8b35d/`, all previous
results and archived sources/binaries. Evidence is under
`results/phase4f19-combinations-20261104/`.
