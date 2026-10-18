# Phase 4D.1 — isolated quiet reply ordering

Decision: keep countermove ordering disabled and park further tuning. The
implementation passed correctness checks, but the bounded profile did not
establish a broad efficiency benefit. No playing-strength gain is claimed.

Implementation checkpoint: `2cd3e66`. The
[protocol](../experiments/phase4d-countermove.md) was fixed before measurements;
this is one bounded ordering experiment, separate from later LMR and pruning
qualification. All work ran locally on macOS ARM64, with one active search
worker during timing. No qualification games or automatic schedule were started.

## Implementation

`Countermove Ordering` is an opt-in UCI boolean, default `false`. Each worker
owns a 12-by-64 table keyed by the preceding move's original colored piece and
destination. Promotions use the original pawn, castling the king, and en passant
the pawn. Context travels by value through PVS/re-search calls; the root has no
inferred preceding move. Only completed quiet beta cutoffs train replies.

A remembered reply ranks below both killers and above ordinary quiet history.
It must match an existing legal move, including flags; no move is inserted.
Capture/promotion priorities, depth, check extensions, quiescence, pruning,
evaluation, and time allocation are unchanged. Hints persist between searches
but clear with all existing learned-state resets and policy transitions.
Optional counters are worker-local and summed after joining helpers.

The feature does not promise strength preservation: ordering changes which
iterations finish under a clock and interacts with existing TT behavior.
The default remains off pending separately qualified playing evidence.

## Correctness and default compatibility

- Native, scalar, and ASan/UBSan full suites passed. TSan search and the existing
  43-case SMP UCI suite passed.
- Extended direct search checks passed in all four builds: rules, signed mates,
  repetition, restricted roots, legal PVs, receipt/clock accounting, immediate
  stop, pondering, one/four-worker lifecycle, special previous moves, policy
  isolation, and diagnostic parity with the candidate enabled.
- The new independently replayed UCI suite passed **57 bounded cases in each
  build**. Ten mirrored on/off roots agreed on all depth-1–4 completed scores;
  exact signatures were required for cold replay and policy restoration.
- The new profiler passed **24 lightweight checks**, including incomplete
  evidence, artifact drift, invalid PVs, matrix/ratio validation, total deadline,
  and stale-output fencing. Review caught and repaired deadline/readiness gaps
  before any actual profile search.
- Native Syzygy regressions passed: 140 WDL oracle roots with root outcome and
  move checks, 47 UCI cases, and 12 direct search-clock scenarios. No tablebase
  feature was enabled in timing comparisons.
- All **120** parent/candidate-off depth-6 searches matched exactly across the
  fifteen exposed roots. This includes one recorded warmup and three measured
  repetitions per engine/root. Median paired parent/candidate elapsed ratio was
  **1.00077**, with range 0.88139–1.08923: effectively neutral, variable timing.
- A separate correctness-only extension immediately repeated each root without
  clearing TT or history. All **60 cold/warm searches** matched their parent
  counterpart exactly. This is not additional candidate-on performance evidence.

The unchanged README introduction, three stable GUI executables, and frozen
Phase 3L sources/assets were verified against their saved hashes. No new GUI
bundle was created and no visual Cute Chess test is claimed. In particular,
`0.1-dev-phase4b-20261018` remains the preserved parallel GUI bundle.

## Measurements and decision

All **360/360 searches** completed on October 18, 22:46:31–22:49:56 Helsinki,
within the ordinary daytime budget. Every PV, bestmove, and ponder replayed
legally. Two engines were resident, with one active search worker; builds and
other engine tests had finished before timing. The corpus, settings, protocol,
and source/binary hashes remained fixed throughout the run.

The depth-6 comparison has 45 paired observations per state (15 roots times
three repetitions). Changes below use **candidate-on / off totals minus one**;
negative is less work/time. They are sampled work measurements, not confidence
intervals or strength estimates.

| State | Total nodes off | Total nodes on | Node change | Total elapsed change | Final score / bestmove agreement |
| --- | ---: | ---: | ---: | ---: | --- |
| Cold | 12,579,933 | 12,555,732 | -0.19% | +1.73% | 45/45 both |
| Warm (TT and history) | 2,830,662 | 2,937,660 | +3.78% | +6.27% | 45/45 both |

Results depend on the workload: warm endgames eg-01/eg-04 used 12.70%/19.31%
fewer nodes, while opening-02 used 10.81% more. Equal-weight geometric-mean
warm ratios are 0.98476 for nodes and 0.98326 for elapsed time, unlike the
aggregate totals dominated by longer searches. Cold geometric-mean ratios are
0.99738 and 1.01532. A cold opening-03 timing outlier (+17.69% median elapsed)
is retained, not excluded. The short roots and timing variability prevent a
universal performance claim in either direction.

At the fixed 500 ms limit (20 ms overhead), the candidate completed the same
depth in **43/45 cold pairs and 43/45 warm pairs**, and one lower depth in each
of the other four pairs; it completed a higher depth in none. Final best moves
differed in one cold and three warm pairs. Fewer nodes under a fixed time limit
cannot be treated as an improvement; depth, scores, moves and unfinished work
are preserved together in the raw report.

Six warm timed pairs also differ at one or more common nominal depths
(opening-01, mg-02, eg-04 and eg-05); the audit retains every differing value.
The warm searches inherit differently completed cold searches, so equal nominal
depth does not establish equal cached information. This remains recorded
sensitivity, not proof of strength preservation or a causal TT diagnosis.

All final fixed-depth scores agree. The three repeated warm mg-02 comparisons
differ only at intermediate depths: depth 4 is off +363 / on +368 cp; depth 5
is +363 / +367; depth 6 is +371 in both. Cold mg-02 agrees at every depth
(depth 4 +368, depth 5 +355, depth 6 +371). Existing default-off cold/warm
scores therefore differ too. Deeper TT entries reused during shallower warm
iterations plausibly explain this sensitivity; it is not a demonstrated defect
or a proof of causation. No chess logic or parameter was changed to force
agreement, and no scored discrepancy was hidden.

**Decision: no default promotion; park further countermove tuning and expensive
strength qualification.** The implementation remains available as an explicitly
opt-in, reproducible experiment, not an accepted performance or strength gain.
The small/mixed efficiency result does not justify another tuning subphase.
No diagnostic revision was used. This completes the finite **4D.1** checkpoint;
the broader Phase 4D strength objective remains open.

Next is **4D.2**, current-engine qualification of existing conservative LMR,
then **4D.3**, a separately implemented and tested verified null-move candidate.
The owner's further technique list is reflected in the
[search plan](../SEARCH_OPTIMIZATION_PLAN.md): distinguish already implemented
mate-distance/PVS/aspiration/check/history features from future internal
iterative deepening, futility variants and ProbCut. Each selective change needs
its own safeguards and equal-time playing evidence; zero strength loss cannot
be guaranteed in advance. The frozen Phase 3L campaign is still unstarted and
must not be retargeted to the current engine.

## Artifact identity and reproduction

Independent audit (`results/phase4d-20261018/audit.json`) replayed all **540**
parent/off/profile transcripts: 3,274 iteration records and 15,736 legal
PV/bestmove/ponder plies. It verified exact parent signatures, the complete
profile matrix/order/settings/resources, recomputed ratios, all 15 profile
asset pins, seven implementation pins, 27 protected artifacts and README intro.
No invalid run condition was found. It independently recommended parking this
candidate and advancing to LMR qualification.

- Parent source: `f8e50f3` (Phase 4C).
- Parent binary: `9b5f03e02d9537041025dfd6a815a1ef734fb7a303a14bcaba17f1ea4f57e898`.
- Candidate binary: `bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f`.
- Network: `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Corpus: `afd19399b8dfd284ea274a850988989f4127097eefb9266905faef7b3e6a300f`.
- Raw local evidence: `results/phase4d-20261018/`; frozen executables:
  `build/experiments/phase4d-20261018/`. Generated evidence and binaries are
  ignored by Git. The retained source corpus and profiling tools are versioned.

```sh
make test test-countermove test-profile-countermove
make SIMD=scalar test test-countermove
make MODE=sanitize test test-countermove
make MODE=thread-sanitize test-search test-smp test-countermove
python3 tools/profile_countermove.py \
  --engine build/macos-arm64-generic-release/chess0live \
  --network networks/nn-1a298aa575a0.nnue \
  --output results/countermove-new-run.json
```

Use a new output path and keep builds/other engine workloads out of the timed
run. Its source/corpus/network/executable hashes and raw replies are recorded.
Foreign-target execution, strength qualification, and release acceptance remain
open.
