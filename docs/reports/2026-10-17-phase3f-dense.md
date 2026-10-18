# Phase 3F: four-output NNUE inference — October 17, 2026

**Decision: retain the independently implemented NEON change.** All three
predeclared game-phase gates passed, with exact evaluation and search results.
Compared with the retained Phase 3B engine, sampled throughput improved by
**19.6% in openings, 19.7–21.4% in middlegames, and 32.4–39.5% in endgames**.
This is an implementation-speed result on the recorded M5 Pro workload, not Elo.

Substantial absolute-time drift and four individual slowdowns remain included.
The paired gates passed despite these observations; no claim of controlled
thermal state, core placement, or absence of external host load follows.

## Measured motivation and scope

Preparation commit `dd3d269` froze the all-phase protocol. All **96 searches**
comparing the retained Phase 3B release with its optimized symbol build matched
exactly. Independent replay checked 592 PV lines / 2,640 legal PV plies, plus
96 bestmoves and ponders. Profiling then completed **72 searches**: 24 warmups
and 48 sampled searches. Those also matched their release signatures at common
depths; replay checked 416 PV lines / 1,757 plies, plus 72 bestmoves and ponders.
Thus the preparation evidence covers **168 exact/legal searches**, separately
from candidate correctness tests and the acceptance campaign.

Two independent raw-stack aggregations agreed on the current bottleneck:

| Phase | Search observations | NNUE share | Inclusive inference | First-layer call-site share |
| --- | ---: | ---: | ---: | ---: |
| Opening | 7,455 | 83.84% | 28.92% | 26.22% |
| Middlegame | 24,888 | 79.63% | 29.62% | 27.09% |
| Endgame | 16,293 | 74.36% | 46.76% | 42.39% |

Idle/main-thread observations were excluded from these search denominators.
First-layer attribution is the exclusive residual at optimized source line 533,
the `stack.first.run` call. It supports investigating dense inference; it does
not measure hardware load latency, bandwidth, or per-root costs. The categories
overlap and must not be summed. Sampled timings are not throughput evidence.

Commit `876511b` froze the selected hypothesis **before implementation**:
process four output rows together in the existing NEON 1024×32 and 64×32 dense
layers. The independently written kernel reuses each 16-byte activation load
across four explicit accumulator chains. Row-major weights, parser, format,
features, accumulator updates, activations, calibration, search, and defaults
are unchanged. Scalar inference and the 128×1 fallback retain their prior loop.
No prior owner-engine implementation or assets were reused; the external pinned
Stockfish build remains a test oracle only.

Activations are [0,127] and weights [-128,127]. Compile-time bounds guarantee
that product partials and horizontal sums fit int32; arbitrary int32 biases
are added in int64 before the existing modulo-2³² conversion. There is no new
instruction requirement, transpose, sparse path, saturation, or parameter tuning.

## Completed candidate correctness

Native NEON, forced scalar, and ASan/UBSan full suites passed. Each build passed
**1,515 independent dense arithmetic cases / 84,126 repeated-call output
comparisons**, **360 independent update transitions**, and the **537-position**
incremental/full-refresh suite. Dense tests use an independent int64 row oracle
and cover all three real shapes, extreme activations/weights/biases, modular
overflow and underflow, cancellation, every input lane and output row,
deterministic random cases, repeated calls, and input/model immutability.
Perft/rules/state restoration, UCI lifecycle, exchange, search, resource policy,
time management, and selective-search checks also passed.

A fresh isolated external SF19 oracle run matched **2,057 positions** for native
and scalar at all integer stages and raw/wrapped scores. Reference revision:
`edb0d9db6731067ec50ce619ff372b463bc4dd5d`; Apple Clang 21.0.0. The corpus and
output digests are unchanged from Phase 3B:

| Evidence | SHA-256 |
| --- | --- |
| Corpus | `6e48940a6ed8cd8edaedc97580a18840320ae6ee9fad9c8ed1a78f4123431d9e` |
| Reference/native/scalar integer stages | `4dcca7b66ddb5228ebb2c3ad1b5380f36ee8d0bccdd54e0e94b2488a3f62e1fe` |
| Reference/native/scalar raw outputs | `c7a41f1dbfeba274556e579ae0f65e50ae0e5d6a2010d551639d0fbf676d92e3` |

Logs are `native-tests.log`, `scalar-tests.log`, `sanitize-tests.log`, and
`oracle.log` in `results/phase3f-20261017/`. The complete oracle report is
`build/nnue-oracle-phase3f-20261017/report.json`.

Preparation corrected a Python 3.9 digest-API incompatibility and later repinned
the Makefile after the expected test-target integration. These were setup fixes
before their affected launches; no measured campaign was repeated because of them.

## Frozen acceptance commitments and completed result

The selected protocol remains `protocol-selected.md`. Its fixed screen uses
all 12 existing openings at depth 5, six middlegames at depth 6, and all six
endgames (five at depth 8; pawn root at depth 12), with fresh same-baseline
controls followed by complete candidate rounds A and B. Twelve comparisons
produce **576 completed searches**: 144 warmups and 432 measured searches.
Each comparison uses three measured pairs per root, one active search worker,
and at most two resident engines. Acceptance timing uses the ordinary nighttime
budget, with no competing build, profile, or engine-test jobs.

Every phase must pass fresh control ratio/MAD and root-noise guards, the 50 ms
duration floor, each pooled root's 0.98 regression guard, and a median ratio of
at least 1.03 in **both** candidate rounds. Endgame groups are pooled by individual
pairs, not group medians. Retention requires all three phases to pass. No extra
repetitions, exclusions, substitutions, selective stopping, or post-result tuning
are permitted. Incomplete or invalid evidence cannot qualify the change.

The independent audit passed with zero errors: **576 exact/legal searches**,
**3,552 PV lines / 15,840 legal PV plies**, and 576 bestmoves/ponders. All
24 root signatures match across roles, repetitions, and rounds. No observations
were omitted or repeated; all 55 frozen inputs and launch/settings/resource
checks passed. The campaign ran **23:16:49–23:29:15 Europe/Helsinki**, October 17,
in **746.807169 seconds** under the normal 80% nighttime budget. One active
search worker was used; the worker reservation approximates resource use rather
than imposing a hard operating-system CPU quota. All jobs have ended.

The CPU recorder's 21 mock tests, bounded launcher's 23 mock cases, and 52
independent audit checks passed. Launcher cleanup matches the earlier Phase 3C
implementation; its real descendant-cleanup check was not rerun. Two independent
raw-stack aggregations agreed. Existing comparison helpers were unchanged.

## Artifact identities and delivery

| Artifact | Identity |
| --- | --- |
| Preparation commit | `dd3d269` |
| Frozen hypothesis commit | `876511b` |
| Qualified implementation commit | `500b022` |
| Retained parent executable | `2b780105e53033d8070b280d43a37b7f4e474471896611c512cff8863f1879ae` |
| New executable | `edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b` |
| Timing manifest | `33b9284508e33a6e06916bf8e3960a9384cff5c3b86d2725f3d72c42f95a7513` |
| Final timing audit | `4c1de908f49e552756b42589e62f23b6c1a335ea7e6418573d1d5d61517b9260` |

Preserve `results/phase3f-20261017/`: both frozen protocol snapshots, manifests,
launchers, all raw JSON/log/sample files, independent auditors/checks, arithmetic
and full-suite logs, candidate patch, profile reviews, tables, and final integrity
record. The initial manifest pins the unchanged parent; the timing manifest
repins only the candidate source/Makefile and adds its new test/evidence. The
symbol build and all old frozen engine/GUI bundles are preserved. The normal
native rebuild is byte-identical to the qualified candidate. Final integrity
verified **54/55 frozen paths unchanged**, with exactly one intentional
post-audit promotion at the normal executable. Its original bytes remain at the
frozen Phase 3B path; all 80 other audited evidence/input paths were unchanged.
The committed source diff exactly matches the tested candidate patch. Future
re-audits must restore the original normal-binary path or use an explicit
post-promotion mapping; do not silently rewrite its frozen hash.

An optional new GUI bundle is
`build/test-baselines/0.1-dev-phase3f-20261017/`. Its independent executable,
network, license, and manifest do not replace `0.1-dev-4b8b35d`. A command-line
smoke from an unrelated directory passed UCI startup, adjacent-network loading,
and a legal depth-5 search. The new bundle has **not** been tested in Cute Chess;
owner testing is optional and can run alongside future development.

Phase 3F is complete. Search defaults remain classic timing, LMR off, and
MVV-LVA. Version remains `0.1-dev`; release gates and playing-strength evidence
are still open. Next proposed checkpoint is Phase 3G: prepare a fresh controlled
blitz strength screen for the existing LMR experiment on the updated engine.
No match or automatic schedule has been started. Publishing remains manual.

## Phase gates

| Phase | Control median | Control MAD | A median | A MAD | B median | B MAD | Minimum median duration (ms) | Minimum pooled root ratio | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| opening | 1.005014 | 0.006440 | 1.196321 | 0.009131 | 1.195963 | 0.019421 | 141.824 | 1.153248 | qualified_on_composed_sample |
| middlegame | 1.002493 | 0.003192 | 1.196515 | 0.021421 | 1.213653 | 0.021504 | 666.797 | 1.152347 | qualified_on_composed_sample |
| endgame | 0.996561 | 0.008530 | 1.324133 | 0.056316 | 1.394803 | 0.056066 | 292.838 | 1.284440 | qualified_on_composed_sample |

Control MAD applies only to controls; candidate MAD is descriptive. All control root medians pass [0.95,1.05]. Every role/root/round median exceeds 50 ms. Every pooled candidate root ratio exceeds 0.98. All six phase/round medians exceed 1.03. Three measured pairs per root per round are engineering screening, not confidence intervals.

## Raw ratio ranges and order groups

| Phase | Round | Ratio min/max | Baseline-first pairs/median/MAD | Candidate-first pairs/median/MAD |
|---|---|---|---|---|
| opening | control | 0.978262 / 1.053250 | 18 / 1.004678 / 0.007125 | 18 / 1.005404 / 0.005739 |
| opening | a | 1.147533 / 1.228392 | 18 / 1.197719 / 0.007400 | 18 / 1.194654 / 0.010834 |
| opening | b | 0.840540 / 1.282171 | 18 / 1.196283 / 0.018185 | 18 / 1.190422 / 0.027148 |
| middlegame | control | 0.992202 / 1.065562 | 9 / 0.999900 / 0.001622 | 9 / 1.004403 / 0.003507 |
| middlegame | a | 0.828370 / 1.290503 | 9 / 1.198998 / 0.023596 | 9 / 1.194031 / 0.024212 |
| middlegame | b | 0.870251 / 1.282175 | 9 / 1.209875 / 0.009902 | 9 / 1.230158 / 0.025034 |
| endgame | control | 0.970293 / 1.016740 | 10 / 0.995158 / 0.008196 | 8 / 1.000465 / 0.004660 |
| endgame | a | 1.224332 / 1.612610 | 10 / 1.324133 / 0.057466 | 8 / 1.341310 / 0.053072 |
| endgame | b | 1.271406 / 1.639538 | 10 / 1.368748 / 0.067220 | 8 / 1.402620 / 0.020546 |

## Per-root medians

Times are seconds, excluding only the predeclared warmups. C1/C2 are the identical baseline roles in the control round. BA/CA and BB/CB are baseline/candidate times in rounds A and B. Pooled ratios use all six A/B paired observations, never the ratio of pooled median times.

| Root | C1 | C2 | Control ratio | BA | CA | A ratio | BB | CB | B ratio | Pooled ratio | Pooled MAD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| development-01 | 0.189574 | 0.189858 | 0.998502 | 0.189776 | 0.159568 | 1.189313 | 0.280847 | 0.236429 | 1.196542 | 1.192928 | 0.011450 |
| development-02 | 0.468517 | 0.466799 | 1.009382 | 0.466796 | 0.384206 | 1.216650 | 0.692222 | 0.571442 | 1.211843 | 1.214117 | 0.002685 |
| development-03 | 0.499677 | 0.494286 | 1.008650 | 0.500874 | 0.409535 | 1.222061 | 0.736993 | 0.659797 | 1.126279 | 1.153248 | 0.047891 |
| development-04 | 0.362436 | 0.354049 | 1.023688 | 0.358337 | 0.292567 | 1.224805 | 0.534194 | 0.442860 | 1.185097 | 1.212205 | 0.016518 |
| development-05 | 0.395064 | 0.396628 | 0.994818 | 0.399333 | 0.332605 | 1.200391 | 0.590226 | 0.493541 | 1.186733 | 1.195100 | 0.005512 |
| development-06 | 0.443948 | 0.450398 | 0.999764 | 0.444648 | 0.372088 | 1.195010 | 0.671860 | 0.550361 | 1.198473 | 1.196741 | 0.006361 |
| development-07 | 0.172366 | 0.170872 | 1.019267 | 0.168376 | 0.144397 | 1.166061 | 0.248838 | 0.210577 | 1.185181 | 1.175621 | 0.015423 |
| development-08 | 0.179351 | 0.179594 | 1.006790 | 0.176825 | 0.148633 | 1.201721 | 0.267688 | 0.218189 | 1.233375 | 1.203787 | 0.011273 |
| development-09 | 0.170196 | 0.169927 | 1.002457 | 0.169852 | 0.141824 | 1.197632 | 0.252113 | 0.209208 | 1.204283 | 1.203225 | 0.003715 |
| development-10 | 0.354996 | 0.353362 | 1.005550 | 0.354355 | 0.298580 | 1.188086 | 0.526129 | 0.443636 | 1.183968 | 1.187443 | 0.005071 |
| development-11 | 0.383645 | 0.381894 | 1.004586 | 0.381589 | 0.323026 | 1.177829 | 0.566928 | 0.477330 | 1.187706 | 1.180612 | 0.008309 |
| development-12 | 0.431313 | 0.431588 | 0.999220 | 0.434091 | 0.368277 | 1.197806 | 0.656600 | 0.535447 | 1.214377 | 1.200522 | 0.008710 |
| gamephases-mg-01 | 0.666797 | 0.667102 | 0.999763 | 0.781255 | 0.719773 | 1.131698 | 0.994692 | 0.847992 | 1.172996 | 1.152347 | 0.049196 |
| gamephases-mg-02 | 2.561463 | 2.559182 | 0.999540 | 2.642280 | 2.247979 | 1.175402 | 3.832728 | 3.243727 | 1.181581 | 1.178113 | 0.008292 |
| gamephases-mg-03 | 4.180227 | 4.160445 | 1.004113 | 4.269230 | 3.599304 | 1.190161 | 6.286787 | 5.159448 | 1.209875 | 1.206159 | 0.008667 |
| gamephases-mg-04 | 2.962306 | 2.936078 | 1.006253 | 2.996723 | 2.476975 | 1.208966 | 4.477648 | 3.646718 | 1.230158 | 1.209399 | 0.008084 |
| gamephases-mg-05 | 0.954884 | 0.953835 | 0.999900 | 0.967816 | 0.779818 | 1.241080 | 1.435411 | 1.154879 | 1.279679 | 1.246990 | 0.021836 |
| gamephases-mg-06 | 2.059253 | 2.054194 | 1.004403 | 2.267541 | 2.509613 | 1.218243 | 3.080952 | 2.475792 | 1.249911 | 1.237926 | 0.016282 |
| gamephases-eg-01 | 2.837270 | 2.868686 | 0.995228 | 3.662157 | 2.796012 | 1.311064 | 3.680471 | 2.812785 | 1.290717 | 1.302923 | 0.011322 |
| gamephases-eg-02 | 3.379101 | 3.435515 | 1.003097 | 4.422388 | 3.112360 | 1.435188 | 4.363742 | 3.098177 | 1.411329 | 1.413136 | 0.015160 |
| gamephases-eg-03 | 0.432631 | 0.432244 | 0.995087 | 0.530802 | 0.426147 | 1.245584 | 0.530904 | 0.396584 | 1.338691 | 1.325412 | 0.037749 |
| gamephases-eg-04 | 0.988034 | 0.988061 | 0.999972 | 1.274672 | 0.923236 | 1.371556 | 1.283432 | 0.914357 | 1.395695 | 1.394803 | 0.012302 |
| gamephases-eg-05 | 0.359415 | 0.357591 | 0.997893 | 0.440142 | 0.293154 | 1.508295 | 0.439930 | 0.292838 | 1.502297 | 1.505296 | 0.018568 |
| gamephases-eg-06 | 2.233353 | 2.286144 | 0.974170 | 2.847189 | 2.213598 | 1.283198 | 2.841759 | 2.225675 | 1.285682 | 1.284440 | 0.008124 |

## Every individual candidate slowdown

| Root | Round | Repetition (zero-based) | Order | Baseline seconds | Candidate seconds | Paired ratio | Extra time |
|---|---|---:|---|---:|---:|---:|---:|
| gamephases-mg-06 | a | 1 | baseline_first | 2.267541333 | 2.737352417 | 0.828370 | 20.719% |
| development-03 | b | 2 | baseline_first | 0.736992875 | 0.876809250 | 0.840540 | 18.971% |
| gamephases-mg-01 | b | 2 | baseline_first | 1.011493666 | 1.162301667 | 0.870251 | 14.909% |
| development-04 | b | 2 | candidate_first | 0.556455541 | 0.579058291 | 0.960966 | 4.062% |

All 4 slowdowns remain included among 144 candidate pairs. They do not change the predeclared median/root gates. Individual control extremes and candidate ratio ranges above are also retained; no observation was excluded or repeated.

## Absolute-time drift

These descriptive ratios compare median elapsed times across rounds, not paired speedup. Values above 1 mean the later run took longer. They cannot distinguish host load, thermal/core placement, or scheduling effects.

| Root | Baseline A/control | Baseline B/control | Baseline B/A | Candidate B/A |
|---|---:|---:|---:|---:|
| development-01 | 1.001065 | 1.481466 | 1.479889 | 1.481685 |
| development-02 | 0.996327 | 1.477476 | 1.482922 | 1.487330 |
| development-03 | 1.002396 | 1.474938 | 1.471412 | 1.611089 |
| development-04 | 0.988692 | 1.473899 | 1.490756 | 1.513703 |
| development-05 | 1.010807 | 1.494003 | 1.478030 | 1.483866 |
| development-06 | 1.001578 | 1.513375 | 1.510991 | 1.479116 |
| development-07 | 0.976851 | 1.443661 | 1.477873 | 1.458320 |
| development-08 | 0.985918 | 1.492537 | 1.513855 | 1.467976 |
| development-09 | 0.997983 | 1.481314 | 1.484308 | 1.475128 |
| development-10 | 0.998195 | 1.482072 | 1.484751 | 1.485821 |
| development-11 | 0.994642 | 1.477742 | 1.485702 | 1.477683 |
| development-12 | 1.006439 | 1.522328 | 1.512588 | 1.453925 |
| gamephases-mg-01 | 1.171654 | 1.491747 | 1.273197 | 1.178139 |
| gamephases-mg-02 | 1.031551 | 1.496304 | 1.450538 | 1.442952 |
| gamephases-mg-03 | 1.021291 | 1.503934 | 1.472581 | 1.433457 |
| gamephases-mg-04 | 1.011618 | 1.511541 | 1.494181 | 1.472246 |
| gamephases-mg-05 | 1.013544 | 1.503231 | 1.483144 | 1.480959 |
| gamephases-mg-06 | 1.101148 | 1.496151 | 1.358719 | 0.986523 |
| gamephases-eg-01 | 1.290733 | 1.297187 | 1.005001 | 1.005999 |
| gamephases-eg-02 | 1.308747 | 1.291391 | 0.986739 | 0.995443 |
| gamephases-eg-03 | 1.226917 | 1.227152 | 1.000192 | 0.930628 |
| gamephases-eg-04 | 1.290109 | 1.298975 | 1.006872 | 0.990383 |
| gamephases-eg-05 | 1.224606 | 1.224017 | 0.999519 | 0.998922 |
| gamephases-eg-06 | 1.274849 | 1.272418 | 0.998093 | 1.005456 |

## Drift ranges

| Phase | Baseline A/control min/max | Baseline B/control min/max | Candidate B/A min/max |
|---|---|---|---|
| opening | 0.976851 / 1.010807 | 1.443661 / 1.522328 | 1.453925 / 1.611089 |
| middlegame | 1.011618 / 1.171654 | 1.491747 / 1.511541 | 0.986523 / 1.480959 |
| endgame | 1.224606 / 1.308747 | 1.224017 / 1.298975 | 0.930628 / 1.005999 |

No sampled throughput result establishes Elo, universal performance, cross-platform speed, scalar speed, or a release. Phase 3F compares against the retained Phase 3B baseline; do not add these percentages to earlier phases.
