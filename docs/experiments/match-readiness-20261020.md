# Four-worker real-match readiness — October 20, 2026

Protocol **match-readiness-20261020-v1**. Declared before any selected-root
search. This is the next bounded checkpoint after the
[clock-boundary diagnostic](../reports/2026-10-20-clock-boundaries.md), before
fresh qualification of existing conservative LMR and broader Phase 4D.6 work.

## Fixed attempt

- **Eight games**, four opening pairs with colors reversed. Four concurrent
  calls to the existing `match.run_match`, one pair per shard.
- **3 seconds + 0.05 seconds per move**, Threads 1, Hash 64 MiB, Move Overhead
  20 ms, classic time management, Ponder false, diagnostics false.
- Both roles use the same frozen ordinary engine from source `23323c6`;
  candidate LMR on, opponent LMR off. All other experimental search policies
  remain off, capture ordering is MVV-LVA, Syzygy path empty/probe limit zero.
- Maximum **1,024 searched plies per game**. A cap is incomplete, never a draw.
  Engine startup allowance 30 seconds, protocol watchdog grace 5 seconds.
  Grace is not credited as chess time.
- Seeds **20261020401–20261020404**, one per shard in order.
- **180-second live-attempt deadline**, starting after input checks and initial
  manifest publication, before starting workers. Cancel and await every owned
  worker/process on failure. Cleanup exceeding that deadline invalidates the
  attempt; an uninterruptible OS storage operation may still delay shutdown.
- No retries, replacement games, resume, score-based stop, or output overwrite.
  Preserve all partial records, scored clock forfeits and failure reasons.

This is a short operational test permitted within the daytime correctness
budget. It does not authorize a long daytime campaign or any schedule.
The 3+0.05 setting does not reproduce the historical 60+0.6 campaign.

## Inputs and isolation

The independently authored project opening generator provides one 16-ply
stem each from the e4, d4, c4 and Nf3 families. Four deterministic SHA-selected
legal continuations produce full 20-ply histories, without engine evaluation.
Reject terminal, duplicate and catalogued exposed roots; no outcome selection.
The new generator, four suites and provenance metadata retain the precise
selection/exclusion policy and source hashes. Starting-root freshness does not
establish independent samples, balanced play or a representative rating pool.

Files: `tests/data/match-readiness-20261020-01.json` through `-04.json`,
plus `match-readiness-20261020-generation.json`. These become exposed when
searched and must be excluded from subsequent qualification roots.

Frozen ordinary executable:
`build/experiments/match-readiness-20261020/chess0live`,
SHA-256 `eaf26b5f13e9de38cc8e5b8da06dc582ff935ca7c01e27e0dc7a6451146a77b9`.
Pinned network: `nn-1a298aa575a0.nnue`,
SHA-256 `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
There is no engine search, evaluation or clock-policy change.

Use the existing runner's callback timestamps, protocol persistence, referee,
PGNs and cleanup. No injected delays, diagnostic build, instrumentation command,
post-position barrier or modified clock accounting. Freeze source hashes before
play and check metadata during the run and full hashes afterward. Commit the
tested supervisor/auditor/protocol before launching the live attempt.

## Resources and operational gate

Reserve **four active searches, eight resident engines and at least 6 GiB**
until all workers finish cleanup. Detect CPU/RAM and apply the owner's current
resource budget; the detected 18-CPU/64-GiB machine permits nine active workers
during daytime. This is an admission estimate, not an OS utilization/RSS cap.
Check aggregate admission before each game and approximately every second;
a monitoring gap above five seconds invalidates the attempt. Other development
searches, builds and benchmarks must be idle.

Readiness passes only with all eight games naturally completed under the
referee, no clock loss in either role, no illegal/protocol/storage/stderr
failure, no cap, unchanged pins, verified process cleanup and an independent
raw-evidence audit. A clock forfeit remains scored in the game record but
fails this readiness gate. Abort siblings when a shard or prior-game guard
detects a failure; already-owned cleanup is always awaited.

The audit must replay complete histories, PVs and ponder moves, verify actual
options, charged clocks/increments, PGNs, outcomes, admissions and identities.
Sweep half-open raw go-to-bestmove intervals: require actual peak concurrency
**exactly four**, never above four, and report time at that concurrency.
No Elo interval or strength claim follows from this eight-game screen.

## Decision and next step

After preparation tests and the local preparation commit, run exactly once:

```sh
python3 tools/check_match_readiness.py --output results/match-readiness-20261020/canary
python3 tools/audit_match_readiness.py --campaign results/match-readiness-20261020/canary \
  --output results/match-readiness-20261020/audit.json
```

The live output directory must not exist; the audit refuses to overwrite a
report. Run `make test-match test-match-readiness` before freezing inputs.
`python3 tools/generate_readiness_openings.py --check --verify-sources`
replays the recorded generation sources without starting engines.

A clean result permits preparation of a separately frozen, fresh LMR strength
qualification protocol at the proposed concurrency. It does not establish that
the historical clock failures are repaired or justify enabling LMR by default.
That longer test follows ordinary overnight policy or a new explicit owner
exception. If this screen fails, retain its evidence and diagnose the concrete
failure before any long run. Do not repeatedly tune and rerun this small sample.

Keep the owner's README introduction, modified puzzle runner, frozen experiment
assets, and GUI snapshots `0.1-dev-4b8b35d`, `0.1-dev-phase3f-20261017` and
`0.1-dev-phase4b-20261018` unchanged. The owner handles GitHub publishing.
