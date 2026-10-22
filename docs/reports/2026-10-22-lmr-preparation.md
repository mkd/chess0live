# Fresh LMR qualification preparation — October 22, 2026

**Preparation and independent search-free readiness passed. No qualification
game has started, and no schedule exists.** The next action is one launch under
the [fixed protocol](../experiments/lmr-20261022.md). Its original overnight-only
preparation was committed as `548ce74`; the owner subsequently authorized the
dated daytime amendment recorded below, before any game.

The planned comparison has **512 games / 256 reversed-color pairs**, four
concurrent one-thread games, 60+0.6, Hash 64 MiB, Move Overhead 20 ms and classic
timing. Both roles use the same unchanged ordinary release and network; only
existing conservative LMR differs. All unrelated pruning/ordering experiments,
pondering, diagnostics and tablebases are explicitly disabled. No search or
evaluation implementation changed, and LMR remains off by default.

## Completed preparation

- Generated 256 legal full histories, split into four 64-pair shards with
  128 roots for each side to move. Selection used no engine/evaluation/outcomes.
- Checked against **168,111** distinct recorded source roots: 1,917 public roots
  and 167,336 saved-game roots, with overlap between those sets. Replayed all
  1,772 PGNs across 28 directories; one exposed candidate was rejected. All
  saved PGNs were legal. Related stems and unrecorded/internal search positions
  remain limitations; new roots do not prove statistical independence.
- Deterministic public reproduction and full `--check --verify-sources` replay
  passed against all 109 recorded generation sources. Compact public exclusions
  and per-source digests preserve reproducibility without publishing raw games.
- **145 workflow checks passed:** 17 opening, 23 launcher, 48 independent audit,
  17 statistics and 40 existing runner checks. Synthetic fixtures cover clocks,
  legal moves/PVs/ponders, explicit options, altered evidence, cleanup, unknown
  RAM, resource revocation, cancellation, input drift and the launch/cutoff rules.
- Serial real-engine preflight passed at **19:32 Warsaw / 20:32 Helsinki**,
  followed by an independent audit with `checked=true` and no errors. Neither
  role received a `position` or `go` command. Actual option types/defaults and
  settings matched, both engines quit, and the saved sources/assets stayed exact.
- Fresh hardware detection reported 18 logical CPUs and 64 GiB RAM. The four
  active searches/eight resident engines reserve **6 GiB**, within the current
  daytime allowance of nine workers and 32 GiB. This is an admission estimate,
  not measured process utilization or an enforced OS memory ceiling.

The passing October 20 four-worker live readiness screen is retained; it was
not rerun. No full puzzle comparison, new C++ build/sanitizer run, fresh GUI test
or foreign-platform execution was necessary or performed for this tooling-only
preparation. Previously tested ordinary executable bytes remain unchanged.

## Frozen evidence

Engine source checkpoint: `18860b2` (no engine source changes since `23323c6`).
The new frozen directory is `build/experiments/lmr-20261022/`; its manifest
records source hashes, prior compiler/build provenance and validation reports.

| Asset | SHA-256 |
| --- | --- |
| Ordinary/frozen executable | `eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9` |
| NNUE network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Build manifest | `8285c44849f8aa782973922d4ea74fe501fc18a274da1573a3b3e96d7896e00c` |

Preparation records are in `results/lmr-20261022/`: `preflight.json`,
`preflight-audit.json`, the empty `preflight.stderr.log`, opening/source check
logs, launcher/auditor/runner test logs and final protected-asset checks.
The independent readiness audit retains 1,781 input digests, including saved
mainline evidence used to verify root exclusions. Copy the complete evidence
and frozen build directories when moving machines; large artifacts stay outside Git.

All 57 protected historical input/source/binary pins remain unchanged, including
the three GUI bundles `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017` and
`0.1-dev-phase4b-20261018`. Preserve the owner's modified puzzle runner unstaged
and the exact README introduction. The owner handles GitHub pushes.

## Decision still pending

This is readiness evidence only. The long comparison has **zero games played**.
Its normal launch window is 22:00–22:30 Warsaw (23:00–23:30 Helsinki), with the
original 06:00 Warsaw / 07:00 Helsinki cutoff. Budget approximately 6–8 hours;
completion is not guaranteed. No automatic launch is implied by preparation.

After all 512 games, audit before interpreting the result. Any clock forfeit
in either role blocks default eligibility; incomplete/corrupt evidence also
cannot qualify. A passing result needs at least 299.5/512 points under the
predeclared conditional confidence rule to reach a separate default review.
An inconclusive or failed result is recorded and parked, not extended or tuned
against these openings. Decide existing LMR's status before broader Phase 4D.6
reductions. No rating, strength gain or release acceptance is claimed here.

## Authorized daytime amendment

After `548ce74`, the owner answered: **"Run now; I authorize a daytime
exception"**. The explicit `run --allow-daytime` option permits this one October
22 attempt before 23:30 Helsinki, retaining October 23's 07:00 Helsinki / 06:00
Warsaw cutoff. Resource limits remain 50% daytime and 80% nighttime; all match
inputs, settings and decision rules are unchanged. No schedule is created.

All **81 relevant checks passed again**: 27 launcher and 54 independent-auditor
tests. Coverage includes authorization/date/window expiry, child propagation,
the unchanged daytime resource ceiling, crossing into nighttime policy and the
original cutoff. Independent review found no blocking issue. A fresh serial
real-engine readiness check and its independent audit passed with no searches.
All 60 protection checks passed, including 57 historical pins, the owner's
puzzle runner, exact README introduction and ordinary release binary.

Evidence is in `results/lmr-20261022/daytime-preparation/` (`preflight.json`,
`preflight-audit.json`, `protected-after.json`, `authorization.json`), with
`daytime-launcher-tests.log` and `daytime-auditor-tests.log` in the parent folder.
Original preparation evidence is retained unchanged. Commit the tested amendment
before starting; preserve the resulting campaign and do not launch another run.
