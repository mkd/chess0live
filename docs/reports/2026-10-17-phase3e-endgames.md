# Phase 3E: endgame performance qualifies on the revised workload

Date: October 17, 2026. Status: **complete; qualified on this composed sample**.
Preparation commit: `c38bd9cc8fa4fecd93916650a5771b088aa96e4e`.

The retained Phase 3B NNUE accumulator optimization passed every predeclared
Phase 3E gate. The two complete endgame comparisons measured **8.9% and 8.4%
higher throughput** than the frozen baseline on this M5 Pro, with median paired
elapsed-time ratios **1.089113 and 1.084243**. All **216 searches** matched exactly
and replayed legally. No engine code, executable, or search default changed.

This is a new complete six-root comparison using a longer pawn workload.
[Phase 3C](2026-10-16-phase3c-gamephases.md) remains inconclusive for its original
endgame and combined workload; none of its timings enter this result. The
optimization was already retained from Phase 3B. There is no Elo, universal
endgame-performance, or release claim. Two individual candidate slowdowns and
noticeable absolute-time drift remain in the evidence below.

## Frozen setup

The [protocol](../PHASE_3E.md) was committed and frozen before measurement.
All six original endgames remain in the
[composed suite](../../tests/data/performance-gamephases.json), SHA-256
`38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c`.
The main group contains `gamephases-eg-01`, `-02`, `-03`, `-04`, and `-06`, in
that order, at depth 8. Pawn root `gamephases-eg-05` runs separately at depth 12,
using the [Phase 3D proposal](2026-10-17-phase3d-workload.md). All roots have
empty histories. Pinned `chess==1.11.2` confirmed validity, uniqueness,
nonterminal positions, and no claimable draws. These exposed composed roots
are not held-out tournament data; historical reachability is not proven.

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| baseline | `build/experiments/phase3a-20261016/release/chess0live` | `7d63b9f99bedd93586549bd6fb2057d473024c69a5d19989e6b4569727323b44` |
| candidate | `build/experiments/phase3b-20261016/release/chess0live` | `2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae` |
| network | `networks/nn-1a298aa575a0.nnue` | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |

Baseline source is `9daaade`; candidate source is `eb059b5`. Threads 1, Hash
64 MiB, classic timing, LMR off, MVV-LVA, Ponder/diagnostics off, and Move
Overhead 20 ms match the prior comparisons. Threads/Hash/EvalFile were set
explicitly; other options were checked against fresh-process UCI defaults and
pinned setup code. Raw outgoing setup commands are not stored by this helper.
New-game/readiness work was excluded from external monotonic go-to-bestmove
timing. There was no clock-managed search, book, or sampler.

The campaign ran **21:25:48–21:31:42 Europe/Helsinki** in **353.663077 seconds**
on macOS 26.7.1 ARM64, M5 Pro, 18 logical CPUs and 64 GiB physical memory.
One worker searched with two engines resident, within the ordinary 50% daytime
budget. Combined estimated engine memory was 1,190,742,648 bytes; this is planning,
not an OS-enforced utilization cap. No concurrent engine test, build, match,
or CPU profile ran. Host background work, CPU placement, and temperature were
uncontrolled. All jobs ended; no override or schedule was used.

Each of the six comparisons used fresh processes, one warmup per root/role,
and five measured pairs per root. Run order was control-main, control-pawn,
A-main, A-pawn, B-main, B-pawn. This totals **36 warmups and 180 measured
searches**. Every round contains 30 pairs, five per root. Local position indexes
restart for each group, giving **16 baseline-first and 14 candidate-first pairs
per round**. No sample, root, or run was omitted or repeated. Every comparison
completed within its 300-second outer bound, every search within 30 seconds,
and the campaign within 600 seconds.

## Complete-round decisions

Each round pools all **30 individual paired ratios**, equally weighted by root.
The five-root main group has 25 pairs; the pawn group has five. Group medians
are never averaged or weighted by elapsed time. Ratios are baseline elapsed /
candidate elapsed; in the control, both roles run the baseline. Greater than
one favors the candidate. MAD and ranges describe observed variation, not
confidence intervals. Thresholds were applied to unrounded values.

| Round | Median ratio | Paired MAD | Individual ratio range | Baseline-first / candidate-first medians |
| --- | ---: | ---: | --- | --- |
| control | 0.998927 | 0.003985 | 0.849067–1.044594 | 1.000519 / 0.996164 |
| a | 1.089113 | 0.015311 | 0.976986–1.149556 | 1.087191 / 1.090672 |
| b | 1.084243 | 0.023069 | 0.994604–1.150601 | 1.094397 / 1.072727 |

The control passed median [0.97, 1.03], MAD ≤0.03, and every root median
[0.95, 1.05]. All **36 role/root/round median durations** exceeded the 50 ms
floor; the smallest was **298.212 ms**. Both candidate rounds exceeded the
1.03 positive gate. All six pooled A/B root medians exceeded the 0.98 regression
guard; the lowest was **1.049976**, the pawn root. Thus the declared result is
**qualified on this revised six-root endgame workload**.

For transparency, the split comparison statistics are below. These do not
replace the complete-round decisions.

| Comparison | Pairs | Median ratio | MAD | Individual ratio range | Baseline-first / candidate-first medians |
| --- | ---: | ---: | ---: | --- | --- |
| control-main | 25 | 0.998734 | 0.005368 | 0.849067–1.044594 | 1.000676 / 0.995562 |
| control-pawn | 5 | 1.000071 | 0.002363 | 0.996416–1.006471 | 1.000071 / 1.001443 |
| timing-main-a | 25 | 1.089877 | 0.011683 | 1.051974–1.111845 | 1.089877 / 1.090672 |
| timing-pawn-a | 5 | 1.057122 | 0.037304 | 0.976986–1.149556 | 1.057122 / 1.063271 |
| timing-main-b | 25 | 1.092535 | 0.015144 | 0.994604–1.150601 | 1.095118 / 1.077890 |
| timing-pawn-b | 5 | 1.046649 | 0.022775 | 1.011555–1.138461 | 1.053303 / 1.035261 |

## Per-root results and drift

Short IDs refer to `gamephases-eg-<ID>`. Each row has five measured pairs.
Times are separately calculated role medians, so their quotient need not equal
the median paired ratio. Depth is 8 except `05`, which is depth 12.

| Round | Root | Baseline median ms | Candidate-role median ms | Paired ratio | Paired MAD |
| --- | --- | ---: | ---: | ---: | ---: |
| control | 01 | 2696.414 | 2715.482 | 0.995898 | 0.002999 |
| control | 02 | 3146.184 | 3140.191 | 1.001585 | 0.005672 |
| control | 03 | 395.467 | 397.056 | 0.997705 | 0.005961 |
| control | 04 | 942.134 | 936.412 | 1.006887 | 0.006192 |
| control | 05 | 319.459 | 319.667 | 1.000071 | 0.002363 |
| control | 06 | 2118.834 | 2119.344 | 0.999760 | 0.001026 |
| a | 01 | 2715.930 | 2466.559 | 1.096946 | 0.008870 |
| a | 02 | 3140.803 | 2951.082 | 1.064289 | 0.002545 |
| a | 03 | 397.387 | 359.650 | 1.106993 | 0.002283 |
| a | 04 | 934.810 | 863.716 | 1.085467 | 0.002549 |
| a | 05 | 338.129 | 298.212 | 1.057122 | 0.037304 |
| a | 06 | 2109.878 | 1922.477 | 1.098714 | 0.005424 |
| b | 01 | 2714.746 | 2544.391 | 1.067600 | 0.032735 |
| b | 02 | 3146.196 | 3078.925 | 1.058861 | 0.033670 |
| b | 03 | 396.378 | 366.679 | 1.095118 | 0.016727 |
| b | 04 | 943.028 | 865.088 | 1.090095 | 0.012705 |
| b | 05 | 471.497 | 450.482 | 1.046649 | 0.022775 |
| b | 06 | 2122.977 | 1931.641 | 1.099053 | 0.005669 |

Absolute times rose in the final comparison, especially the pawn group:
control medians were 319.459/319.667 ms, A was 338.129/298.212 ms, and B was
471.497/450.482 ms. The fixed paired and root gates still passed. Without host
telemetry the cause cannot be assigned to background load, temperature, or any
particular engine operation. Preserve this drift rather than describing the
host or all individual measurements as stable.

The next table pools only the ten A/B pairs per root for the regression guard
and order/dispersion report. It does not pool older campaigns.

| Root | Pooled ratio | MAD | Individual ratio range | Baseline-first / candidate-first medians |
| --- | ---: | ---: | --- | --- |
| 01 | 1.093411 | 0.013508 | 0.994604–1.150601 | 1.087455 / 1.106920 |
| 02 | 1.063016 | 0.008044 | 1.019233–1.104904 | 1.062667 / 1.063016 |
| 03 | 1.100468 | 0.008898 | 1.044245–1.147339 | 1.095672 / 1.109495 |
| 04 | 1.086464 | 0.007170 | 1.059068–1.119433 | 1.085364 / 1.086464 |
| 05 | 1.049976 | 0.029815 | 0.976986–1.149556 | 1.055212 / 1.035261 |
| 06 | 1.098884 | 0.005377 | 1.091537–1.107124 | 1.098884 / 1.098761 |

## Every individual measured slowdown

The two candidate slowdowns below are included in all statistics. Repetition
indexes are zero-based. Extra time means `(candidate time / baseline time - 1)`.

| Comparison | Root | Repetition | First role searched | Baseline ms | Candidate ms | Ratio | Extra time |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| timing-pawn-a | 05 | 3 | candidate | 338.128792 | 346.093833 | 0.976985892 | 2.3556% |
| timing-main-b | 01 | 4 | baseline | 3328.552667 | 3346.612292 | 0.994603610 | 0.5426% |

Control slowdowns are listed separately: both roles run the same executable,
so these are timing variation, not candidate regressions. The largest control
outlier had ratio 0.849067 (17.7764% extra second-role time) on root `04`.
The median-based predeclared control gates passed despite this outlier; no
individual-ratio veto was added after inspection.

| Comparison | Root | Repetition | First role searched | Baseline ms | Second baseline ms | Ratio | Extra time |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| control-main | 04 | 4 | candidate | 988.689959 | 1164.443250 | 0.849066675 | 17.7764% |
| control-main | 03 | 4 | baseline | 395.265333 | 419.264125 | 0.942759729 | 6.0716% |
| control-main | 04 | 0 | candidate | 933.943417 | 943.938542 | 0.989411254 | 1.0702% |
| control-main | 03 | 3 | candidate | 395.711041 | 399.005417 | 0.991743531 | 0.8325% |
| control-main | 01 | 1 | candidate | 2687.175792 | 2708.095125 | 0.992275259 | 0.7785% |
| control-main | 01 | 2 | baseline | 2696.414250 | 2715.699708 | 0.992898531 | 0.7152% |
| control-main | 06 | 1 | candidate | 2116.245292 | 2130.379167 | 0.993365559 | 0.6679% |
| control-main | 02 | 0 | candidate | 3376.332166 | 3392.576000 | 0.995211947 | 0.4811% |
| control-main | 01 | 0 | baseline | 2704.342833 | 2715.482167 | 0.995897843 | 0.4119% |
| control-main | 02 | 4 | candidate | 3137.121375 | 3149.996792 | 0.995912562 | 0.4104% |
| control-pawn | 05 | 1 | candidate | 316.295708 | 317.433500 | 0.996415652 | 0.3597% |
| control-main | 01 | 3 | candidate | 2718.783750 | 2727.778292 | 0.996702613 | 0.3308% |
| control-main | 03 | 2 | baseline | 395.306167 | 396.215666 | 0.997704535 | 0.2301% |
| control-main | 06 | 3 | candidate | 2102.572542 | 2105.238750 | 0.998733537 | 0.1268% |
| control-pawn | 05 | 4 | baseline | 319.459416 | 319.852791 | 0.998770137 | 0.1231% |
| control-main | 03 | 1 | candidate | 396.692375 | 397.055750 | 0.999084826 | 0.0916% |
| control-main | 06 | 2 | baseline | 2118.834125 | 2119.343709 | 0.999759556 | 0.0241% |

## Correctness, audit, and boundaries

Independent parsing of all raw replies confirmed identical per-iteration
depth/seldepth/nodes/score/PV, bestmove, and ponder across roles, repetitions,
and all three rounds for every root at its fixed depth. Independent legal replay
checked **1,872 PV lines / 10,512 plies, 216 bestmoves, and 216 ponders**.
Commands, identities/defaults, input mapping, local sample order, counts,
resources, lifecycle, timing consistency, stored summaries, and decision
aggregation all passed. A separate review recomputed the complete-round/root
gates from raw paired durations and agreed. There were no correctness failures,
timeouts, exclusions, or changed artifacts. All **37 frozen-input checks** passed.

The 11 existing comparison-tool tests passed. Three launcher mock cases verified
commands/no-overwrite, failure stopping, and timeout stopping with remaining
runs unstarted. Syntax checks passed. Process-group cleanup/signal-handler
functions were AST-checked against the tested Phase 3C launcher; the actual
descendant cleanup test was not rerun. Independent audit checks passed **29
cases**: ten copied-data corruptions, twelve decision boundaries, and seven
aggregation/mapping/order cases. The earlier 28-case preparation record remains
preserved; the extra check rejects an incorrect UCI identity. These checks
launched no engine and changed no raw measurements.

Native/scalar/sanitizer and the full NNUE oracle suites retain their Phase 3B
scope and were not rerun for this measurement-only phase. The finite search
agreement adds no new integer-stage oracle or foreign-platform execution
claim. GUI `0.1-dev-4b8b35d`, the normal native binary, network, all prior
frozen candidates, and production sources remain unchanged.

Together with the separately reported opening and middlegame measurements,
this result broadens the observed performance evidence for the retained
optimization. It is not a pooled cross-phase statistic or a retrospective
change to Phase 3C. Reused composed roots, small fixed samples, order imbalance,
visible outliers/drift, and uncontrolled host conditions limit generalization.
Clock-managed strength and competitive Elo remain unmeasured here.

## Evidence and reproduction

Preserve the entire ignored `results/phase3e-20261017/` directory: frozen
protocol/manifest/suite, position groups, launcher/preflight/suite checks, all six
raw JSON/log comparisons, campaign lifecycle, final integrity, independent
auditor/check scripts, and both audit-check records. Protocol and this report
are versioned; large raw results and binaries remain local.

| Local evidence file | SHA-256 |
| --- | --- |
| `protocol.md` | `07a0407459d98f1f0237cc38fe53f00e263e2b9d9383114c33f2ce2b775e09a3` |
| `manifest.json` | `3320a602654415d7ebbc9d7b3b776f2234edfe67bfa6b5c8c862c839b94b895c` |
| `suite.json` | `38e1eb26401232b0129191c18f0a0c63f2caae3dc110eddee1a76ef0d1a3133c` |
| `main-positions.txt` | `2392c1fad02c9e86c0aa685d6aec3fa929823e2a4cc9b6af026e38978abdc358` |
| `pawn-positions.txt` | `2c65c9e6a4dc83bce0afc6a8a676e3c745736b3b8690b9093c442d59cc8fcea1` |
| `run_campaign.py` | `1457e20fc1168f38581c172576dba3a2cb8d58f80ace1a3506cf49c6495543ef` |
| `check_launcher.py` | `886275ce72a7b0e4001a3c3d3ddc81ee00b4e8c61972609428ec23a90d53928e` |
| `preflight.json` | `bfc9e7c7d732e0b5019b2f043451f4a7bfb64964eef8d9438f5a093ca63cc3f9` |
| `suite-check.json` | `bfc802e3f54ed4cf6e3109246db896526650bf28a17b06debe79d0e6a4d78df6` |
| `campaign.json` | `4ac5ea76c36402e8c1090c0f3ecfb98f97bb7574ade90d44ebbbf0e7746b832b` |
| `control-main.json` | `399625fe417c71ce242615a8dfae874bdf5a5a17ceb0f73da725b1ac947ac692` |
| `control-pawn.json` | `4bbb9b443e6a2fd731eaa45c4b7945bf0b3cd38311b6ff2935a55dd5f62d277a` |
| `timing-main-a.json` | `530c2506912fe85fbf30683af6b30ff5dc6a4016b79d31de79a4dc62c060c517` |
| `timing-pawn-a.json` | `6b19500259ffef10209366c1ac10cff3a767c6fa800b9d81cdfb905e7971b41d` |
| `timing-main-b.json` | `1e0c47d746d3eb6521a4f56b55d5f8617980bdaea7e6d28d2f510a3a784a7172` |
| `timing-pawn-b.json` | `a94898598c1d0cc86e1059f2a64cf6bbda06a76eee8bdadc6d69a889df67690a` |
| `audit_bench.py` | `4ac97754abc15377a6c0f489e8db487139b8a6ca79f5711b12acf1019032f44b` |
| `audit_checks.py` | `33e3215e3fc514895e983f78e320aa2ca8055f8b4cdc8f7f0c7fe25bbacf7684` |
| `audit-checks.json` | `c97c45f1737c2891bfac95d40f1f69708959cb1308d3faf90602c8dfcbc99194` |
| `audit-checks-final.json` | `25e0c4088ff16b46668003c422d8f72132bb8355106253b895d3b2af92622cd1` |
| `audit.json` | `ad62964e0d4f65855ec05ac23d667662a1c971dd94043d1105214a1b1e696b99` |
| `final-integrity.json` | `c6f73c6bbf9990e027aa50879043be511056fd99999db735f99de5fcaac2639d` |

The manifest pins all tool dependencies and preserved assets. Exact campaign
commands, ordering, and outer limits are in `campaign.json` and the launcher.
To reproduce one pawn comparison, use the frozen binaries and a fresh output:

```sh
python3 tools/compare_bench.py --baseline build/experiments/phase3a-20261016/release/chess0live --candidate build/experiments/phase3b-20261016/release/chess0live --network networks/nn-1a298aa575a0.nnue --positions results/phase3e-20261017/pawn-positions.txt --depth 12 --repeats 5 --hash-mb 64 --search-timeout 30 --output results/phase3e-reproduction-pawn.json
```

That command reproduces one split comparison, not complete qualification or
its outer campaign bound. Recreate position lists from the versioned suite and
fixed grouping in the protocol if local results are unavailable. Never overwrite
completed evidence or add runs to this completed campaign seeking a different
result. Any new campaign needs its own inputs and rules before measurement.

## Next checkpoint: Phase 3F

Move to the next implementation bottleneck: profile the updated engine on
opening, middlegame, and endgame workloads, then choose and implement one
isolated NNUE improvement if the measurements justify it. Keep exact evaluator
and search behavior, independent correctness/oracle checks, and predeclared
performance gates. Freeze the concrete scope before changing production code.
No Phase 3F profile, implementation, or experiment has started. Parallel search,
search-policy strength qualification, broader runtime validation, and release
acceptance remain later roadmap work. No manual GUI retest is needed for Phase
3E because the executable did not change.
