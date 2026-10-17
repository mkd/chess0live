# Phase 3D: a longer pawn-ending workload

Date: October 17, 2026. Status: **complete; depth 12 proposed for future qualification**.
Preparation commit: `ec881950856f42eefb16e6c8b0554ea398f2372f`.

The fixed baseline-only ladder found depth **12** to be the shallowest tested
level meeting the declared workload rule. Its two role medians were
**329.881 and 322.562 ms**, compared with **32.583 and 32.453 ms** at depth 8.
All **40 searches** preserved exact per-iteration results and legal output.
This proposes a longer measurement workload; it establishes no candidate speed
or playing-strength gain. No engine code, executable, or default changed.
[Phase 3C's endgame and combined decisions](2026-10-16-phase3c-gamephases.md)
remain inconclusive.

## Frozen setup and scope

The [Phase 3D protocol](../PHASE_3D.md) was frozen before engine measurements.
The only root was `gamephases-eg-05` from the original
[composed game-phase suite](../../tests/data/performance-gamephases.json):

```text
8/8/5k2/7p/2K2P2/8/8/8 w - - 0 50
```

History is empty. Pinned `chess==1.11.2` confirmed a valid, nonterminal root
without a claimable draw; historical reachability is not proven. The root was
selected after Phase 3C exposed its short duration, so this is post-hoc workload
characterization, not held-out evidence. No opponent code or testing assets
were used.

Both roles of the unchanged comparison helper ran the same Phase 3A baseline,
source `9daaade`, at `build/experiments/phase3a-20261016/release/chess0live`:
SHA-256 `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44`.
The runner label `candidate` means the **second baseline process** throughout
this report. The retained Phase 3B candidate was not launched.

The network was `networks/nn-1a298aa575a0.nnue`, SHA-256
`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
Settings were Threads 1, Hash 64 MiB, classic timing, LMR off, MVV-LVA,
Ponder/diagnostics off, and Move Overhead 20 ms. Threads/Hash/EvalFile were
explicitly set; other settings were checked against recorded fresh-process
UCI defaults and pinned setup code. The benchmark format does not record
outgoing setup commands.

Depths **8, 9, 10, 11, 12** ran once in that order. Each used one warmup and
three measured searches per role, for **10 warmups and 30 measured searches**.
Warmup order was first role then second role. Measured repetitions 0 and 2
searched the first role first; repetition 1 reversed that order. Fresh
processes were started at each depth, and search state was cleared with
readiness completed before every externally timed go-to-bestmove search.

The M5 Pro (18 logical CPUs), macOS 26.7.1 ARM64 campaign ran
**21:10:32–21:10:40 Europe/Helsinki**, lasting **7.441256 seconds**. One search
worker was active, with two baseline processes resident, within the ordinary
50% daytime budget. There was no simultaneous engine test, build, or sampler.
Background activity, core placement, and temperature were not controlled.
All five comparisons exited successfully within the 30-second search,
60-second comparison, and 300-second campaign limits. No extra run, exclusion,
manual resource override, or automatic schedule was used.

## Work and proposal decision

The predeclared rule required a complete valid ladder, both role medians at
least 200 ms, every measured search at most 5 seconds, median paired duration
ratio in [0.97, 1.03], and paired median absolute deviation (MAD) at most 0.03.
Only depth 12 met all conditions. Its longest measured search was 374.466416 ms.

Ratio means first-role elapsed / second-role elapsed. Both roles run the same
binary: variation measures host/run noise. The median paired ratio is not the
quotient of the separately calculated role medians. Nodes are cumulative at
the final iteration; scores are engine centipawns, not independently proven
position values.

| Depth | Nodes | Selective depth | Score cp | First median ms | Second median ms | Paired ratio | Paired MAD | Decision |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 20,790 | 11 | -2 | 32.582833 | 32.453333 | 1.003990345 | 0.009229327 | Too short |
| 9 | 32,676 | 12 | 0 | 51.336792 | 51.010375 | 1.006191021 | 0.000208010 | Too short |
| 10 | 59,694 | 14 | -1 | 104.045667 | 105.214750 | 0.952314800 | 0.031298109 | Too short; ratio and MAD fail |
| 11 | 113,204 | 15 | -6 | 160.971458 | 162.244292 | 0.992154830 | 0.007627583 | Too short |
| 12 | 209,071 | 17 | -4 | 329.880625 | 322.561542 | 0.999090223 | 0.028506983 | Proposed |

Depth 10's timing instability is retained. It was not rerun or removed. Depth
12's MAD of 0.028507 passes but is close to the 0.03 limit. Three pairs provide
limited repeatability evidence; selecting a passing depth from this ladder
cannot guarantee future stability. Fresh controls are required for qualification.

## All durations and order effects

All times below are milliseconds, rounded to six decimals. Measured arrays are
in repetition order (0, 1, 2) for each role, including the reversed search order
in repetition 1. Raw JSON retains full precision. No sample was removed.

| Depth | Warmups first / second | First-role measured times | Second-role measured times |
| ---: | --- | --- | --- |
| 8 | 36.888500 / 33.622042 | 31.961083, 32.733708, 32.582833 | 32.699750, 32.306625, 32.453333 |
| 9 | 50.440209 / 52.385583 | 52.251541, 51.336792, 50.244709 | 51.930041, 51.010375, 50.282917 |
| 10 | 96.029959 / 97.629834 | 96.505042, 109.876792, 104.045667 | 101.337333, 119.299458, 105.214750 |
| 11 | 165.217708 / 163.709083 | 160.320417, 161.444375, 160.971458 | 162.840000, 160.411917, 162.244292 |
| 12 | 318.886459 / 327.364833 | 322.268083, 329.880625, 355.818875 | 322.561542, 321.021333, 374.466416 |

| Depth | Individual ratio range | First-role-first median (2 pairs) | Second-role-first ratio (1 pair) | First / second duration MAD ms |
| ---: | --- | ---: | ---: | --- |
| 8 | 0.977410622–1.013219672 | 0.990700484 | 1.013219672 | 0.150875 / 0.146708 |
| 9 | 0.999240140–1.006399032 | 1.002715581 | 1.006399032 | 0.914749 / 0.727458 |
| 10 | 0.921016691–0.988888602 | 0.970601701 | 0.921016691 | 5.831125 / 3.877417 |
| 11 | 0.984527248–1.006436292 | 0.988341039 | 1.006436292 | 0.472917 / 0.595708 |
| 12 | 0.950202367–1.027597206 | 0.974646295 | 1.027597206 | 7.612542 / 1.540209 |

These subgroup sizes do not support a causal explanation for order effects.
Using the mean of the two role medians, consecutive depth-duration growth was
1.573696×, 2.044614×, 1.544562×, and 2.018596×. These are descriptive observations
on one root and host, not search scaling predictions.

Bestmove remained `c4d3` at every depth. Ponder was `f6f5` at depths 8–10 and
`h5h4` at 11–12. Final PVs were:

| Depth | Final PV |
| ---: | --- |
| 8 | `c4d3 f6f5 d3e3 f5g4 f4f5 g4f5 e3d2 f5f4` |
| 9 | `c4d3 f6f5 d3e3 h5h4 e3f3 h4h3 f3g3 f5e6 f4f5 e6e7` |
| 10 | `c4d3 f6f5 d3e3 f5g4 e3e4 h5h4 e4e3 g4g3 f4f5 h4h3` |
| 11 | `c4d3 h5h4 d3e2 h4h3 e2f2 h3h2 f2g2 h2h1q g2h1 f6f5 h1h2 f5e4` |
| 12 | `c4d3 h5h4 d3e2 h4h3 e2f2 h3h2 f2g2 h2h1q g2h1 f6f5 h1g1 f5g4 g1f2` |

A changed PV, ponder, or score at greater depth is diagnostic output, not a
measured tactical or playing-strength improvement. Common-depth iteration
records matched across all five levels, while final decisions were permitted
to change with depth.

## Validation and limitations

The independent auditor reparsed every raw response, including warmups, and
verified exact depth/seldepth/nodes/score/PV and bestmove/ponder agreement within
each depth. It also verified all common iteration prefixes across depths.
Independent legal replay checked **400 PV lines / 2,296 plies, 40 bestmoves,
and 40 ponders**. Run/sample order, counts, source/assets, resource metadata,
settings, raw/reported timing summaries, and campaign lifecycle passed.
All **35 frozen-input checks passed** (34 unique paths; the baseline is checked
for both roles). No timeout,
search failure, illegal output, or signature mismatch occurred.

The 11 existing comparison-tool tests passed. Two new launcher mock cases
verified all five exact commands/no-overwrite behavior and stopping subsequent
levels after comparison failure; syntax checks passed. The process-group
cleanup and signal-handler functions were AST-checked against the tested Phase
3C launcher. Its real descendant cleanup test was **not rerun**; that earlier
evidence is preserved in `results/phase3c-20261016/launcher-check.json`.

All **20 auditor checks** passed: eight copied-data corruptions were rejected,
ten selection/boundary cases passed, and two cross-depth-prefix cases passed.
These checks launched no engine and modified no raw evidence. The first auditor
attempt stopped before reading search results due to an auditor-only
`legal_moves()` API typo. Its failed `audit.json` is preserved. Only the auditor
was repaired; the successful final result is `audit-final.json`, with zero errors.

Native/scalar/sanitizer and full NNUE oracle suites were not rerun: production
code and binaries are unchanged from Phase 3B. This finite search-output audit
adds no new integer-stage oracle or foreign-platform execution evidence. GUI
snapshot `0.1-dev-4b8b35d`, the normal native build, and all frozen candidates
remain unchanged. No GUI retest is required for this measurement-only phase.

## Evidence and reproduction

Preserve the entire ignored `results/phase3d-20261017/` directory, including
frozen protocol/suite/position/manifest, launcher, all raw JSON/log pairs,
preflight, campaign, both auditor outcomes, audit checks, and final integrity.
The public protocol's status note now links this result; its frozen local copy
retains the exact premeasurement text. Large raw evidence and binaries remain
local; the protocol and this report are versioned.

| Local evidence file | SHA-256 |
| --- | --- |
| `protocol.md` | `43b0edf0197b7a247a4cc3794e3d28fb48c4b5f3e1e69cb99faf1d9015995682` |
| `manifest.json` | `76976709509107dd43684d01e0f2d9e1b9a8b5ebe2db610f83e3b0711f52ed97` |
| `suite.json` | `38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c` |
| `pawn-positions.txt` | `2c65c9e6a4dc83bce0afc6a8a676e3c745736b3b8690b9093c442d59cc8fcea1` |
| `run_ladder.py` | `7ed54429796d6a3a51c06effac2da4f8041b8489725b5dac5b60bbb88d66fae7` |
| `preflight.json` | `16bb6324a964c8b23e9382cf9eaf8009bd671fc0f540dc21cc82857a65b02989` |
| `campaign.json` | `f2882d1235fea6bf06c46815df6643a05d80f52b283720ddb65b7fa3c655d43a` |
| `baseline-depth8.json` | `e39a3cbe44c3db4599f0952da58f98520b848b20a6b3b0561272bee1d901618f` |
| `baseline-depth9.json` | `063cd78ee3c3e1edeb4695648db9c6370175d50d84b129cdf2660a1974d6ee48` |
| `baseline-depth10.json` | `79cf86ec9ec1552b5a0782a343785cbe5c06b46315f20998890bfc9730d3ead7` |
| `baseline-depth11.json` | `628315d1a2fee33d6dedb855e4e8ecd28bd05144e83e644c3ad76b346ab824c7` |
| `baseline-depth12.json` | `b4761bc69dac594dcf910f15edf0d2ec03e0a5b55ae5d4c2385dd1f5c81f2926` |
| `audit_ladder.py` | `3aede80d3da9fae3c627f30d18380101efc67a34e7ed2f33c9f8ba26c76d66db` |
| `audit_checks.py` | `eed8c03827adaebb3428888c11dc5e26a7fa4dabfeb417e9244b1d0b47855b68` |
| `audit.json` | `6097562b356766a671667faff19ada56f23fed354535245a2c76c996c21bd145` |
| `audit-final.json` | `adb0ec47115eac236982f531d0f01c43a7af512a9b802725d6e2a84820a17c24` |
| `audit-checks.json` | `3c0b06402217d5906000a2077b790798dfa58e09c55dd26891879e4168f20f97` |
| `final-integrity.json` | `d94319d08e8972758ae64022fe883e606fea44d5d6786d355bd0dcae9fa4db57` |

The frozen manifest pins the four unchanged runner sources, production sources,
network, baseline, and preserved binaries. Each comparison records its source
hashes and exact UCI replies. To reproduce the depth-12 comparison manually,
use a fresh output path and the preserved baseline for **both** roles:

```sh
python3 tools/compare_bench.py --baseline build/experiments/phase3a-20261016/release/chess0live --candidate build/experiments/phase3a-20261016/release/chess0live --network networks/nn-1a298aa575a0.nnue --positions results/phase3d-20261017/pawn-positions.txt --depth 12 --repeats 3 --hash-mb 64 --search-timeout 30 --output results/phase3d-reproduction-depth12.json
```

This command reproduces one comparison, not the bounded five-level campaign.
The preserved launcher/manifest contain the campaign's commands and outer
limits. Any future execution is a separate run; never overwrite this evidence.
The composed FEN above is sufficient to recreate the one-line position input
by prefixing it with `fen ` when local artifacts are unavailable.

## Next checkpoint: Phase 3E

Propose a separately frozen endgame requalification of the retained Phase 3B
candidate against the Phase 3A baseline. Preserve all six original endgame
roots, with depth 12 for `gamephases-eg-05` and depth 8 for the other five.
Because the helper accepts one depth per comparison, preparation must define
the two depth groups, equal pair counts, complete aggregation, fresh same-binary
controls, and exactness/noise/duration/regression gates before any measurements.
No Phase 3E measurements have started and no schedule is active.

Phase 3C remains unchanged, and Phase 3D does not qualify the candidate for
endgames. Further NNUE optimization, selective-search strength qualification,
parallel search, and release acceptance remain separate roadmap work.
