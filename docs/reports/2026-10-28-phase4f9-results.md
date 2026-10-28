# Phase 4F.9 — completed Continuation History tactical comparison

The full 39-position comparison and independent audit completed on October 28,
2026. Continuation History on reported **four mates versus three off**, with
one additional M9 report and no lost mate reports in this attempt. All 39 final
moves matched. This completes the finite tactical checkpoint and supports
preparing a separate game-based strength qualification. The option remains
**off by default**; no Elo, strength non-regression or release is established.

## Attempt and evidence

The owner explicitly authorized this one daytime attempt and confirmed paused
LM Studio inference, AC power and Automatic mode. Start/end: **08:37:11–09:55:23
Europe/Helsinki**, duration **78 minutes 12 seconds**. The start-of-run power
snapshot reported AC power and Low Power disabled. A process-lifetime sleep
inhibitor accompanied the runner and exited afterward. Continuous power/thermal
telemetry was not recorded; quiet-host conditions include the owner's attestation.

The [fixed protocol](../experiments/phase4f9.md) and
[tested preparation](2026-10-28-phase4f9-preparation.md), commit `b337990`, were
unchanged. Both roles used the same source-`69215b4` executable, SHA-256
`c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`, and pinned
`nn-1a298aa575a0.nnue` network. Each position/role had a fresh process with eight
threads, 64 MiB Hash and `go movetime 60000`. Only Continuation History differed;
LMR was enabled, TT Move Hints and the other experimental options disabled.
Role order alternated. No tablebase or answer-hint assistance was used.

One engine searched at a time, reserving 2 GiB within the Mac's nine-worker
daytime allowance. Reservations and requested workers are admission estimates,
not measured hard resource caps. The runner retained its two-hour deadline,
clock-continuity checks and next-07:00 cutoff. No retry, replacement, extension,
competing benchmark or new schedule occurred.

Raw results: `results/phase4f9-full-20261028/`. Authorization, launch/cleanup
records, paired summary and validation index:
`results/phase4f9-full-20261028-launch/`. External audit:
`results/phase4f9-full-20261028-audit.json`.

- Report SHA-256:
  `4647955d4a390a1f2a4e3d63433c293103e50f0ebab43478e5aade96c52bd68e`.
- Independent audit SHA-256:
  `9f8ffa45c7d3b148d6b99312acc37b76d51e8178cbb4c733338aca7520e30164`.

The frozen runner was launched through `tools/run.py --offline` in full mode
with the authorized `--quiet-host --allow-daytime` flags. After its zero exit,
the independent auditor was run through the same dependency launcher:

```sh
python3 tools/run.py --offline tools/audit_phase4f9_puzzles.py results/phase4f9-full-20261028/report.json --output results/phase4f9-full-20261028-audit.json
```

## Audit and complete observations

All **78 sessions / 39 pairs** passed, with zero operational failures or
exclusions. The independent raw replay verified 52 input identities, 831 analysis
PVs / 7,707 legal plies, 156 legal best/ponder plies, 2,184 commands, 234 readiness
barriers and 2,575 resource observations. All processes exited zero and delivered
EOF. The launcher exited zero; a separate OS process check found no engine,
match runner or sleep inhibitor remaining. The owner was immediately told
LM Studio inference could resume. Maximum audited gap was 2.043 seconds and
maximum clock drift 0.077 seconds, within the fixed limits.

Both roles reported M7 on positions 1 and 2, and M9 on position 15. On also
reported M9 on **position 13**, spreadsheet row 20; off finished at **+16.62**.
All final reported mate distances matched the supplied labels, and their final PVs
replayed legally to checkmate. Position 13's first positive mate report arrived
at engine-reported **57.386 seconds**, depth 11; off completed depth 10. Both
selected `e6e1`. Its FEN is:

```text
2N3k1/2b1qb2/2n1r3/8/1PP3Pp/P4Q2/8/2R1R2K b - - 2 42
```

Independent replay also confirms that move as `Rxe1+` and the 17-ply final PV
ending in `Qxg3#`. First positive mate-report times below are engine-reported
seconds from this single attempt, not repeatable timing estimates:

| Position | Off | On |
| --- | ---: | ---: |
| 1 | 11.443 | 11.615 |
| 2 | 6.032 | 5.709 |
| 13 | No mate report | 57.386 |
| 15 | 29.832 | 32.671 |

All final moves matched; final scores matched on **32/39** positions. Beyond
the new mate report, on's centipawn score was lower on positions **8, 10, 14,
29** by 34, 107, 107 and 142 cp, respectively; it was higher on **30 and 38**
by 25 and 1 cp. Completed depth was higher on four positions, lower on two
(1 and 14), and equal on 33. Retain these differences alongside the favorable
observation. Higher/lower scores or depths alone do not establish better/worse
play; this was not a speed benchmark.

The 39-position corpus is already exposed and SMP searches are nondeterministic.
The added mate report occurred near the time limit and has not been repeated;
do not call it a repeatable improvement. Legal mating PVs establish legal lines,
not forced mate against every defense. Supplied mate annotations are labels, not
an independently verified oracle. Expected best-move labels are absent, as
clarified before the full run; supplied-best-move accuracy is **unavailable**.

All 1,549 recorded protection entries (1,517 distinct files) matched their
pre-run identities, including the normal/stable GUI binaries, owner batch tool,
historical campaigns and prepared inputs. The README and its introduction were
unchanged in this run. No engine or tooling code changed, so prior synthetic
checks were not repeated; this checkpoint validates the saved full evidence.

## Decision and next step

Close Phase 4F.9 without rerunning or enlarging this attempt. No operational or
lost-mate-report blocker was detected in the fixed sample. Proceed next to
**Phase 4F.10: prepare isolated Continuation History game qualification**, with
a separately declared paired-opening protocol, failure/statistical criteria and
quiet-window authorization before launching games. Do not tune against these
puzzles or change defaults on this evidence. No match is running or scheduled.
TT Move Hints and the older combined-policy promotion remain parked.

## Every position

Scores are from the side-to-move perspective. Ordinary values are pawns; `M7`
or `M9` means the engine reported that mate distance. Moves use UCI notation.
The common-move column records agreement between roles, not expected-answer
accuracy. The last column shows completed off/on depth, not playing strength.

| Position | Spreadsheet row | Supplied mate | Off score | On score | Common best move | Depth off/on |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | 4 | M7 | M7 | M7 | `f5f6` | 11/10 |
| 2 | 5 | M7 | M7 | M7 | `f4f3` | 15/17 |
| 3 | 6 | M7 | +7.06 | +7.06 | `d6c4` | 10/10 |
| 4 | 9 | M8 | +18.20 | +18.20 | `f3g5` | 10/10 |
| 5 | 10 | M8 | +15.82 | +15.82 | `h7h6` | 10/10 |
| 6 | 11 | M8 | +16.73 | +16.73 | `c6e7` | 10/10 |
| 7 | 12 | M8 | +14.91 | +14.91 | `d8d2` | 10/10 |
| 8 | 15 | M9 | +18.32 | +17.98 | `f7g7` | 11/11 |
| 9 | 16 | M9 | +17.07 | +17.07 | `a7e3` | 9/9 |
| 10 | 17 | M9 | +21.44 | +20.37 | `c1c7` | 12/12 |
| 11 | 18 | M9 | +15.99 | +15.99 | `e4c3` | 9/9 |
| 12 | 19 | M9 | +14.07 | +14.07 | `c1h6` | 11/11 |
| 13 | 20 | M9 | +16.62 | M9 | `e6e1` | 10/11 |
| 14 | 21 | M9 | +17.02 | +15.95 | `c3c2` | 10/9 |
| 15 | 22 | M9 | M9 | M9 | `e7d7` | 11/11 |
| 16 | 23 | M9 | +16.39 | +16.39 | `g3f2` | 10/10 |
| 17 | 24 | M9 | +14.81 | +14.81 | `f3h5` | 9/9 |
| 18 | 27 | M10 | +17.27 | +17.27 | `h5h4` | 11/11 |
| 19 | 28 | M10 | +12.13 | +12.13 | `h5g6` | 10/10 |
| 20 | 29 | M10 | +9.58 | +9.58 | `d6d1` | 11/11 |
| 21 | 30 | M10 | +19.27 | +19.27 | `d1h5` | 11/11 |
| 22 | 31 | M10 | +11.14 | +11.14 | `d1d4` | 11/11 |
| 23 | 32 | M10 | +14.36 | +14.36 | `e3e5` | 10/10 |
| 24 | 33 | M10 | +16.33 | +16.33 | `g5h6` | 11/11 |
| 25 | 34 | M10 | +14.21 | +14.21 | `g2d5` | 10/10 |
| 26 | 35 | M10 | +18.09 | +18.09 | `d1h5` | 10/10 |
| 27 | 36 | M10 | +14.42 | +14.42 | `e4d6` | 11/11 |
| 28 | 39 | M11 | +17.74 | +17.74 | `e1e4` | 10/10 |
| 29 | 40 | M11 | +11.34 | +9.92 | `d1h5` | 10/10 |
| 30 | 41 | M11 | +12.90 | +13.15 | `g5g3` | 9/10 |
| 31 | 42 | M11 | +15.87 | +15.87 | `g3h3` | 10/10 |
| 32 | 43 | M11 | +12.78 | +12.78 | `g8g4` | 10/10 |
| 33 | 46 | M12 | +12.55 | +12.55 | `f5h3` | 12/12 |
| 34 | 47 | M12 | +12.78 | +12.78 | `e6g7` | 10/10 |
| 35 | 48 | M12 | +9.43 | +9.43 | `h3b3` | 10/10 |
| 36 | 51 | M15 | -2.75 | -2.75 | `d3h3` | 11/11 |
| 37 | 52 | M15 | +1.07 | +1.07 | `b6d4` | 11/11 |
| 38 | 53 | M17 | +6.42 | +6.43 | `g8g5` | 14/15 |
| 39 | 54 | M18 | +2.89 | +2.89 | `h5h7` | 13/13 |
