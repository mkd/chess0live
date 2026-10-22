# Fresh LMR qualification launched — October 22, 2026

The one authorized attempt started at **18:03:23 UTC / 20:03:23 Warsaw /
21:03:23 Helsinki**, after preparation commit `548ce74` and tested daytime
amendment `a81c951`. This is a launch record, not a result or default promotion.

The [fixed protocol](../experiments/lmr-20261022.md) compares existing LMR on/off
in 512 games / 256 reversed-color pairs at 60+0.6. Four concurrent games each
use one search thread and Hash 64 MiB; eight engines are resident, with 6 GiB
reserved. Both roles use the same frozen executable/network. Other experiments,
ponder and tablebases are disabled. All engine code and defaults are unchanged.

The owner explicitly authorized this one daytime launch. The 50% daytime / 80%
nighttime resource policy remains active. Its immutable cutoff is **October 23,
04:00 UTC / 06:00 Warsaw / 07:00 Helsinki**. Estimated duration is 6–8 hours,
roughly 02:00–04:00 Warsaw; completion before the cutoff is not guaranteed.

## Startup verification

- The amendment passed 27 launcher and 54 independent-auditor tests. Fresh
  search-free readiness and its independent audit passed. All 60 protection
  checks passed; original preparation evidence remains preserved.
- Before launch, the process inventory showed no other matching chess engines.
- All four child manifests entered `running`; all four raw transcripts then
  recorded `go`, search information and `bestmove` responses. Periodic resource
  observations reported `within_limits=true` at startup. No game was complete
  when this record was written; there is no provisional strength result.
- The Python UCI adapter logged the engine's informational `Syzygy largest 0
  pieces; table files are external` setup output as unexpected. Tablebases are
  intentionally disabled, and all four games proceeded. Preserve this console
  output for the final audit; no source is modified during the campaign.

## Continuation

The foreground `caffeinate -i` wrapper prevents ordinary idle sleep while the
command runs. No schedule, recurring task or system sleep-setting change was
created. Keep the machine available and avoid overlapping builds/engine tests.

Live evidence is under `results/lmr-20261022/campaign/`: `campaign.json`,
`resource-history.jsonl`, and each `shard-N/match/games.jsonl` with raw protocols
and PGNs. Parent-folder `campaign.stdout.json` and `campaign.stderr.log` retain
console output. Session metadata is in `launch-process.json` beside those logs.
Do not launch a second attempt, resume, overwrite or change frozen inputs.

After termination, independently audit the complete campaign before interpreting
scores. Any either-role clock forfeit blocks default eligibility. Decide
promote/reject/park before broader Phase 4D.6 work. The normal GUI build is
unchanged, and the owner handles GitHub pushes manually.
