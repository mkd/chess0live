# Phase 4F.13 timing amendment — October 30, 2026

Authorization identifier: `phase4f13-daytime-20261030`.
Base protocol: [`phase4f13-nnue-2048-v1`](phase4f13-match.md), prepared in
commit `70a5f2d`. No smoke or qualification game had started when this amendment
was prepared. The original protocol, original pin file and all earlier evidence
remain unchanged; 96 original inputs are archived in the dated preparation folder.

## Authorization and timing

After being told the match requires approximately 6–8 hours, the owner requested:
“Perfect. LM Studio is paused, proceed with the next phase.” The request arrived
on October 30 during the daytime. This is treated as authorization to begin this
specific prepared comparison today, with the ordinary daytime resource ceiling.
It grants no recurring schedule, retry, sample extension or engine promotion.

The explicit `--allow-daytime` flag admits starts only on **October 30, 2026,
14:00 inclusive to 22:45 exclusive, Europe/Helsinki**. All stages retain a fixed
**October 31, 2026, 07:00 Europe/Helsinki** cutoff (`2026-10-31T05:00:00Z`).
Readiness, smoke and held-out admission must all respect that dated window;
the ten-minute smoke timeout includes setup persistence and its audit. No stage
resets the cutoff. A missing flag retains the original ordinary overnight window.
A flag on a different date or outside the stated window is rejected.

The observed host was on AC power, fully charged, with Low Power Mode disabled
and AC idle sleep disabled. The owner has confirmed LM Studio inference is
paused. Keep AC connected, competing inference/builds paused, and the Mac awake
with its lid open. A sleep inhibitor can prevent idle sleep; it does not make
lid-close suspension safe. These observations and operator confirmations are
not continuous power, temperature or external-load telemetry.

## Unchanged experiment

All statistical and chess conditions remain those of the base protocol:
2,048 qualification games / 1,024 pairs, 15+0.15, the same frozen binaries,
network, options, four seeds and opening histories; the separate eight-game
smoke gate must pass independent raw auditing and cleanup before held-out play.
Smoke remains excluded from strength inference. Four active searches and eight
resident engines reserve at least 6 GiB, within the ordinary **50% daytime /
80% nighttime** budget. There is no resource override or concurrency increase.

Any failure, forfeit, incomplete sample, invalid evidence, changed input,
resource/clock continuity violation or cutoff prevents qualification. Preserve
all evidence, verify cleanup and release the host explicitly. Do not retry or
resume this attempt, change the interval rule, enlarge the sample, or promote
settings automatically. The original conditional statistical interpretation and
limited sensitivity to small gains remain unchanged.

## Implementation and validation

The existing new Phase 4F.13 launcher, independent aggregate/raw auditors and
their tests receive only the dated operating-policy extension. Their original
bytes and runtime inputs are archived under
`results/phase4f13-daytime-20261030-preparation/original-70a5f2d/`, with a hash
manifest. The original `tests/data/phase4f13-match-pins.json` is retained and
included as an input of the new
`tests/data/phase4f13-match-daytime-20261030-pins.json` freeze. The base protocol
and this amendment are both pinned. No historical campaign, engine or statistical
helper is edited or rebuilt.

Test ordinary overnight behavior, the exact dated admission boundaries, wrong
date/authorization/cutoff rejection, smoke and full-game policy agreement, and
unchanged resources/settings. Repeat search-free readiness and its independent
audit against the new frozen inventory, then commit the tested amendment locally
before launching once. Save separate authorization, launch-started and launch-exit
receipts. Final audit replays both stages and reports the entire outcome; live
scores remain provisional.

```sh
python3 tools/run.py --offline tools/qualify_phase4f13.py check --allow-daytime
python3 tools/run.py --offline tools/qualify_phase4f13.py run --quiet-host --allow-daytime --output results/phase4f13-match-20261030
python3 tools/run.py --offline tools/audit_phase4f13.py --campaign results/phase4f13-match-20261030 --output results/phase4f13-match-20261030-audit.json
```

The command creates no schedule. Existing output directories and audit files
must never be overwritten. The campaign supervisor owns its cutoff and resource
checks; progress monitoring only reads evidence.
