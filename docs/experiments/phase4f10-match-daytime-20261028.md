# Phase 4F.10 — October 28 one-run timing amendment

Authorization ID: `phase4f10-daytime-20261028`.

After leaving the prepared match pending a quiet window, the owner wrote:
“Ready, go ahead!” on October 28. This confirmation authorizes the prepared
512-game comparison and the previously explained timing amendment. It replaces
the earlier wait instruction; no previous puzzle or match permission is reused.
The confirmation covers the agreed paused-inference quiet window, AC power,
Automatic mode and keeping the Mac awake. Check current host power separately
before launch.

This changes only start-time permission in the
[original protocol](phase4f10-match.md). With explicit `--allow-daytime`, accept
starts on **October 28, 2026, from 19:00 inclusive to 22:00 exclusive
Europe/Helsinki**. Both admission and completion of preflight must be inside
this window. The fixed cutoff is **October 29, 2026 at 07:00 Helsinki** and
never moves because of delays. Without the flag, ordinary 23:00–23:30 starts
remain unchanged. The independent auditor checks the exact authorization,
date, window, flag and original cutoff.

Resource limits remain 50% daytime / 80% nighttime, with four active search
workers, eight resident engines and at least 6 GiB reserved memory. The identical
engine/network, 512 games, openings, seeds, 60+0.6 clocks, settings, clock boundary,
monitoring, cleanup, statistical criteria and zero-forfeit gate are unchanged.
Only Continuation History differs between roles; defaults remain unchanged.
No game schedule, retry, resumption, replacement, extension or automatic
promotion is introduced. Estimated duration is 6–8 hours, without a completion
guarantee. Keep LM Studio inference paused, AC/Automatic power and the Mac awake;
an idle-sleep inhibitor does not make lid closure or suspend/resume safe.

Before edits, all 61 original preparation source files, including the original
pin file, were copied and verified against preparation commit
`4a530546f1b30c76f6a8fe294443298941d1783f`. Preserve that archive in
`results/phase4f10-match-20261028-preparation/original-preparation/` and its
`initial-state.json`. Original readiness and all previous evidence stay intact.
The amended launcher, independent auditor, their tests and this document receive
new preparation pins after validation. Commit the amendment before any play.
Earlier readiness does not validate the new permission.

After fresh readiness, independent audit and local commitment, launch once into
a new directory; an idle-sleep inhibitor may wrap this foreground command:

```sh
python3 tools/run.py tools/qualify_phase4f10.py run --allow-daytime --output results/phase4f10-match-20261028
python3 tools/run.py tools/audit_phase4f10.py --campaign results/phase4f10-match-20261028 --output results/phase4f10-match-20261028-audit.json
```

Report newly completed games and provisional candidate wins/draws/losses during
play. A separate progress heartbeat may inspect the existing run but must never
launch or retry games. On termination verify cleanup, tell the owner LM Studio
can resume, and independently audit the full evidence before any conclusion.
Do not build engines or run competing benchmarks during play.
