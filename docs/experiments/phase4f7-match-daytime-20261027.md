# Phase 4F.7 — October 27 one-run timing amendment

Authorization ID: `phase4f7-daytime-20261027`.

On October 27, after leaving the prepared match pending a quiet window, the
owner wrote: “ready, go ahead with the test and/or the next phase; and keep me
updated on the progress with the test”. This current instruction authorizes
starting the prepared match now. It supersedes the earlier wait instruction
and supplies the one-run timing exception; no previous puzzle permission is
reused. The owner's ready confirmation is treated as the agreed paused-inference
quiet window, with host power checked separately before launch.

This amendment changes only the start-time permission in the
[original protocol](phase4f7-match.md). With the explicit `--allow-daytime` flag,
the launcher accepts starts on **October 27, 2026, from 16:00 inclusive to 19:00
exclusive Europe/Helsinki**. Both admission and completion of preflight must be
inside this window. The original next-morning cutoff remains **October 28 at
07:00 Helsinki**; it never moves because of delays. Without the flag, the
ordinary 23:00–23:30 start policy remains unchanged. The independent auditor
requires the exact authorization, date, start window, flag and original cutoff.

No resource exception is requested or applied: keep 50% daytime / 80% nighttime,
four active searches and at least 6 GiB across eight resident engines. Both
roles, network, executable, 512-game sample, openings, seeds, 60+0.6 clocks,
clock-accounting boundary, monitoring, cleanup, statistical thresholds and
zero-forfeit eligibility gate are unchanged. Keep AC power and Automatic mode;
pause competing inference. No schedule, retry, replacement game, sample
extension or automatic default promotion is introduced. Expect roughly 6–8
hours, with no guarantee of completion inside the fixed cutoff.

The original 58 preparation sources, including the pin document, were copied
from commit `20598509a3212ddb5396dc3e4373c6b28bae2fcc` and verified against their
original digests before edits. Local archive:
`results/phase4f7-match-20261027-preparation/original-preparation/`.
Original readiness and evidence remain intact. The updated launcher, independent
auditor, their tests and this amendment receive new recorded preparation pins
after tests. Commit this amendment before any held-out play. Preserve both
preparation versions; never interpret earlier readiness as validation of the
amended policy.

Launch and independent completion audit, after fresh readiness and commitment:

```sh
python3 tools/run.py tools/qualify_phase4f7.py run --allow-daytime --output results/phase4f7-match-20261027
python3 tools/run.py tools/audit_phase4f7.py --campaign results/phase4f7-match-20261027 --output results/phase4f7-match-20261027-audit.json
```

The output directory must be new; no resume/overwrite is permitted. A foreground
idle-sleep inhibitor may wrap the launch. Progress updates report complete games
and provisional candidate wins/draws/losses; only the independent final audit can
qualify the result. No engine builds or competing benchmarks run during play.
