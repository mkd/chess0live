# Phase 4F.7 — completed move-hint tactical comparison

Date: October 26, 2026. Engine source: `a1b2331`; preparation: `52b0dbe`.

The full frozen comparison and independent raw audit passed: **39 positions,
78 searches, eight threads, 60 seconds per configuration/position**. Both
configurations reported the same three mates and chose the same final move on
all 39 positions. No observed material tactical regression blocks preparation
of a fresh strength campaign. **No strength gain or default promotion is
established; TT Move Hints remains off.**

## Scope and conditions

The [original protocol](../experiments/phase4f7.md) remains unchanged. The
[preparation report](2026-10-25-phase4f7.md) preserves the earlier checkpoint,
with a status link to this completion record. This is one complete attempt,
separate from the one-second smoke and older combined-policy campaign.
Both roles use the frozen `a1b2331` native macOS ARM64 generic executable and
pinned SF19-compatible network. Only TT Move Hints differs. Each requests eight
threads, Hash 64, LMR=true, classic timing and 20-ms overhead; all other optional
search policies, pondering, diagnostics and Syzygy are off.

On October 26 the owner paused LM Studio inference and authorized starting.
Initial power inspection found Low Power mode; no full search started in that
state. The owner then set Automatic and explicitly confirmed starting. AC and
Automatic were checked before launch; snapshots at midpoint and completion
also show AC and Low Power disabled. These snapshots and the owner's quiet-host
attestation are not continuous thermal, GPU or competing-workload telemetry.

The run lasted **22:13:40–23:31:55 Europe/Helsinki**, 4,694.52 seconds (78m15s)
including setup. Its pre-23:00 start used the current owner's daytime exception.
One engine ran at a time, with eight workers and a minimum 2 GiB reservation on
the 18-logical-CPU / 64-GiB host. The aggregate policy was checked throughout,
including the transition to the night window; resource reservations are not
measured OS utilization caps. A foreground idle-sleep inhibitor was active.
The owner was told LM Studio could resume immediately after searches finished.

## Independent validation

The independent auditor reconstructed all raw sessions and passed:

- 40 frozen input identities, 78 distinct recorded PIDs and 78 zero exits;
- 822 completed iterations, 7,566 legal PV plies and 156 legal best/ponder plies;
- 2,106 commands, 3,084 consumed output lines and 234 readiness barriers;
- 2,565 resource observations, clean EOF and joined readers for every session.

Go-to-bestmove receipts ranged from **59.980204 to 59.982928 seconds**, within
the fixed allowance; the 20-ms overhead explains early stopping. Maximum
reconstructed monitoring gap was 2.080446 seconds, and wall/monotonic discrepancy
was 55.892 ms, below the five-second failure threshold. No illegal output,
receipt overrun, changed frozen input, resource failure or detected suspension
invalidated the attempt. A separate reviewer parsed every final raw score,
depth and best move and confirmed the saved report.

All 740 files protected at launch, including stable GUI `0.1-dev-4b8b35d`,
previous evidence, owner settings and the frozen campaign, remained unchanged;
so did the README introduction. The ordinary release binary had already changed
before this turn and now matches the frozen candidate; launch-context records
that pre-existing difference. No engine code, build, threshold or playing
default was changed. No match, schedule, platform qualification or release was
started. Existing 54 runner/auditor and 24 exporter synthetic checks are prior
preparation evidence, not newly rerun tests.

## Tactical observations and decision

Both roles reported **M7 on positions 1 and 2, and M9 on position 15**. Each
reported distance matches its supplied annotation, and each final PV legally
ends in checkmate. These are three separate observations; neither a supplied
answer nor one mating line proves forced mate against every defense. The other
36 positions produced no mate report within the allotted time.

All 39 final best moves agree. Score/depth differences occur at positions
**2, 10, 25, 27, 29 and 38**; the table below retains every position. Hints gained
one completed depth at 25 and 29 and lost two at 2, while preserving M7 there.
Final PVs differ at **1, 10, 25, 27, 29 and 38**; position 1 retains the same M7,
depth and best move despite a different mating line. Raw logs preserve all PVs.

This exposed, nondeterministic SMP sample establishes neither superiority nor
universal absence of regressions. Centipawns are not distance to mate, nominal
depth is not a strength score, and equal-time node totals are not an Elo measure.
No serious tactical concern observed here requires a replacement run or tuning.
Do not tune against these 39 positions or pool the earlier smoke into this run.

**Next checkpoint:** prepare a new paired-opening blitz qualification for hints
off/on, with frozen settings, independent results audit, fresh opening provenance
and exclusions, clock-health gates, and a predeclared statistical decision.
Validate the launcher and short readiness before requesting authorization for
that concrete long run. This puzzle authorization does not cover the match.
Hints remain off; the combined-policy campaign remains parked.

## All 39 positions

Each score is followed by the last completed nominal depth. No position is omitted or ranked.

| # | Supplied mate | Hints off: score / depth | Hints on: score / depth | Best moves: off / on | Observed differences |
| ---: | --- | --- | --- | --- | --- |
| 1 | M7 | M7 / 11 | M7 / 11 | <code>f5f6</code> | Same displayed result |
| 2 | M7 | M7 / 15 | M7 / 13 | <code>f4f3</code> | Different depths |
| 3 | M7 | +7.06 / 10 | +7.06 / 10 | <code>d6c4</code> | Same displayed result |
| 4 | M8 | +18.20 / 10 | +18.20 / 10 | <code>f3g5</code> | Same displayed result |
| 5 | M8 | +15.82 / 10 | +15.82 / 10 | <code>h7h6</code> | Same displayed result |
| 6 | M8 | +16.73 / 10 | +16.73 / 10 | <code>c6e7</code> | Same displayed result |
| 7 | M8 | +14.91 / 10 | +14.91 / 10 | <code>d8d2</code> | Same displayed result |
| 8 | M9 | +18.32 / 11 | +18.32 / 11 | <code>f7g7</code> | Same displayed result |
| 9 | M9 | +17.07 / 9 | +17.07 / 9 | <code>a7e3</code> | Same displayed result |
| 10 | M9 | +21.44 / 12 | +21.82 / 12 | <code>c1c7</code> | Different scores |
| 11 | M9 | +15.99 / 9 | +15.99 / 9 | <code>e4c3</code> | Same displayed result |
| 12 | M9 | +14.07 / 11 | +14.07 / 11 | <code>c1h6</code> | Same displayed result |
| 13 | M9 | +16.62 / 10 | +16.62 / 10 | <code>e6e1</code> | Same displayed result |
| 14 | M9 | +17.02 / 10 | +17.02 / 10 | <code>c3c2</code> | Same displayed result |
| 15 | M9 | M9 / 11 | M9 / 11 | <code>e7d7</code> | Same displayed result |
| 16 | M9 | +16.39 / 10 | +16.39 / 10 | <code>g3f2</code> | Same displayed result |
| 17 | M9 | +14.81 / 9 | +14.81 / 9 | <code>f3h5</code> | Same displayed result |
| 18 | M10 | +17.27 / 11 | +17.27 / 11 | <code>h5h4</code> | Same displayed result |
| 19 | M10 | +12.13 / 10 | +12.13 / 10 | <code>h5g6</code> | Same displayed result |
| 20 | M10 | +8.45 / 10 | +8.45 / 10 | <code>d6d1</code> | Same displayed result |
| 21 | M10 | +19.27 / 11 | +19.27 / 11 | <code>d1h5</code> | Same displayed result |
| 22 | M10 | +11.14 / 11 | +11.14 / 11 | <code>d1d4</code> | Same displayed result |
| 23 | M10 | +14.36 / 10 | +14.36 / 10 | <code>e3e5</code> | Same displayed result |
| 24 | M10 | +11.14 / 10 | +11.14 / 10 | <code>g5h6</code> | Same displayed result |
| 25 | M10 | +13.52 / 9 | +14.21 / 10 | <code>g2d5</code> | Different scores; Different depths |
| 26 | M10 | +18.09 / 10 | +18.09 / 10 | <code>d1h5</code> | Same displayed result |
| 27 | M10 | +14.36 / 11 | +14.42 / 11 | <code>e4d6</code> | Different scores |
| 28 | M11 | +17.74 / 10 | +17.74 / 10 | <code>e1e4</code> | Same displayed result |
| 29 | M11 | +10.14 / 9 | +11.34 / 10 | <code>d1h5</code> | Different scores; Different depths |
| 30 | M11 | +12.90 / 9 | +12.90 / 9 | <code>g5g3</code> | Same displayed result |
| 31 | M11 | +15.87 / 10 | +15.87 / 10 | <code>g3h3</code> | Same displayed result |
| 32 | M11 | +12.78 / 10 | +12.78 / 10 | <code>g8g4</code> | Same displayed result |
| 33 | M12 | +12.55 / 12 | +12.55 / 12 | <code>f5h3</code> | Same displayed result |
| 34 | M12 | +12.78 / 10 | +12.78 / 10 | <code>e6g7</code> | Same displayed result |
| 35 | M12 | +9.43 / 10 | +9.43 / 10 | <code>h3b3</code> | Same displayed result |
| 36 | M15 | -2.75 / 11 | -2.75 / 11 | <code>d3h3</code> | Same displayed result |
| 37 | M15 | +1.07 / 11 | +1.07 / 11 | <code>b6d4</code> | Same displayed result |
| 38 | M17 | +6.33 / 15 | +6.43 / 15 | <code>g8g5</code> | Different scores |
| 39 | M18 | +2.89 / 13 | +2.89 / 13 | <code>h5h7</code> | Same displayed result |

A single best move in the table means both roles chose it. The CSV retains each role separately, with the exact FEN, source spreadsheet row, signed UCI score, nodes and timing.

## Evidence and reproduction

Local evidence is under `results/phase4f7-20261026/`: launch-context, start/mid/end
power snapshots, full report/raw logs, run/audit logs, final preservation record
and `full-export/{comparison.md,positions.csv,audit.json}`. The CSV contains all
78 searches with exact FENs, source rows, signed scores, depth, moves and timing.
The export's independently regenerated audit certificate matches the standalone
audit. Exported values were checked against the complete report.

```sh
python3 tools/run.py tools/audit_phase4f7_puzzles.py results/phase4f7-20261026/full/report.json --output results/my-hints-audit.json
python3 tools/puzzle_report.py results/phase4f7-20261026/full/report.json --output results/my-hints-summary
```

Keep saved inputs and raw evidence available and unchanged. Use fresh output
paths. These commands read/audit/export evidence; they launch no engine.

| Artifact | SHA-256 |
| --- | --- |
| Executable | `6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f` |
| Network | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Protocol | `53d172b4f8b0e5ae385c82473c6ac785afaa9b447cd99c7eb566ae235ec65a88` |
| Preparation pins | `2a2a6582382444a5984aee241d6b8fec367ce743307007f7f20a5e0f106703c6` |
| Full report | `0162c22ef12c5c5016e28224f065f0ddbe0c75311e4980021523a442e34bad47` |
| Independent audit | `986f76bf3a3a7e307dde55fdcebedcd3a7d8e1fd8f51a42348f883c1afe618c7` |
