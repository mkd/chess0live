# Phase 4F.15: null-verification ordering — October 30, 2026

**Complete: retain a small opt-in engineering improvement; keep null pruning
off and park its qualification.** The single root-ordering change reduces work
only slightly versus the previous null implementation. It does not fix the
warm-search regression against the accepted LMR-on baseline. No strength or
timing improvement is established, and no match is warranted by this screen.

## Change and fixed comparison

From parent `19ddf06c59bf2c3875414f33503f85bc959313ea`, the ordinary node's
already-copied contextual TT move can order the legal verification root after
exact legal-list validation. No bound/depth is passed, no new TT read occurs,
and descendants receive no hint. Eligibility, reductions, verification depth,
draw rules, speculative isolation, NNUE arithmetic and time management are
unchanged. `Null Move Pruning=false`, LMR on and other parked defaults remain.

The [predeclared protocol](../experiments/phase4f15-null-verification.md) fixes
three exposed opening histories, depth 6, Threads 1, Hash 64, classic timing,
LMR on and other experiments/tablebases off. Diagnostics are enabled. Each
role/root has a fresh process, cold search then immediate warm repeat. The
12 parent-off/candidate-off cells pass exact iteration/final equivalence before
12 parent-on/candidate-on cells. All **24 searches / 12 processes** completed
at **22:38:15–22:38:23 Helsinki**, with no failed, omitted or replacement cells.
LM Studio remained declared active; raw elapsed/NPS observations are not a
controlled performance comparison.

Native executable SHA-256 values:

- Parent: `c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d`.
- Candidate: `17f2951611713b8bd4b13dd0aeee892d972e6aaf829b832ad2737f46045f2800`.
- Network: `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

## Complete node results

| Exposed root | State | Null off (both builds) | Previous null on | Revised null on |
| --- | --- | ---: | ---: | ---: |
| Start position | Cold | 28,945 | 24,574 | 24,509 |
| Start position | Warm | 5,173 | 5,384 | 5,338 |
| Sicilian opening history | Cold | 262,570 | 240,620 | 240,435 |
| Sicilian opening history | Warm | 41,611 | 47,944 | 47,827 |
| Queen's-pawn opening history | Cold | 128,029 | 117,263 | 117,199 |
| Queen's-pawn opening history | Warm | 13,071 | 20,102 | 20,038 |
| **Total** | **Cold** | **419,544** | **382,457** | **382,143** |
| **Total** | **Warm** | **59,855** | **73,430** | **73,203** |

Versus previous null on: **0.0821% fewer cold nodes**, **0.3091% fewer warm
nodes**. All six individual cells use fewer nodes. Versus current null off:
**8.9147% fewer cold nodes**, but **22.3006% more warm nodes**; all three warm
roots regress. The root scores/moves are respectively **+20/e2e4, −34/a7a6,
−26/h7h6**. Every per-depth score/PV and final bestmove/ponder agrees across the
comparisons; changed node counts remain recorded. These are exposed development
positions, not a diverse strength or puzzle sample.

Both old/new null versions record cold **68 probes / 41 verifications / 41
cutoffs**, warm **53 / 41 / 41**, with zero rejected verifications. The revised
version admits **41 legal root hints in each state**. Its cold probe/verification
work is **9,096 / 5,482 nodes**; warm is **8,054 / 5,708**. The old executable
does not expose those three counters, so no old/new subtree reduction is claimed.
Warm speculative work totals 13,762 nodes against 13,348 extra total nodes versus
null off, consistent with a substantial overhead burden in this sample; this
is not a causal attribution of every changed ordinary-search node.

## Validation, audit and limitations

- Native, scalar, ASan/UBSan and ThreadSanitizer direct API checks passed,
  including policy reset, diagnostics parity, history/draw/mate, node/clock/stop
  bounds and one/four-worker accounting. Each build passed **78 UCI cases**
  with independent legal-move/PV checks and both-color regression fixtures.
- Native/scalar/ASan+UBSan null-state checks each passed **63 roots, 202 legal
  children and 1,045 incremental/full-refresh NNUE comparisons**. Pure search
  policy checks passed in those builds; native time-policy checks also passed.
  No new external NNUE oracle or foreign-platform execution is claimed.
- Deterministic stop boundaries are **33,624** nodes at first null dispatch,
  **33,667** at verification dispatch, and **17,186** at the first admitted
  hint with LMR on. Aborted work never publishes a completed cutoff, and reuse
  matches fresh default searches. These are entry boundaries, not every deeper
  interruption or concurrent schedule. Sparse fixtures exercise exclusions;
  neither they nor shallow legal verification prove universal zugzwang safety.
- **15** new profiler tests and **29** package-parser tests pass. Historical
  null records remain readable without inventing absent counters. Before any
  measurement, review corrected strict-schema compatibility and finalization
  deadline accounting; a synthetic path-alias fixture error was also corrected.
  No engine failure or sample rerun occurred.
- Independent raw audit passes with no errors: **24 cells, 12 sessions, 144
  iterations, 612 legal PV plies, 24 bestmoves and 24 ponders**, exact off
  equivalence, **21** unchanged assets and **54** archived build sources.
  All 12 engines exited zero; a separate **22:39:52 Helsinki** OS check found
  those PIDs absent and no remaining phase engine/profiler/test processes.
- **611 protected paths** and the README introduction match their before
  record, including stable GUI **0.1-dev-4b8b35d**, owner batch settings and
  prior campaign evidence. The normal-release historical digest discrepancy
  remains unresolved; only its recorded current bytes are verified. A fresh
  isolated parent build matching those bytes does not resolve the old record.

Only macOS ARM64 was executed. Host load is owner-declared, not continuous
telemetry; admission is not an OS utilization cap. The command log omits the
shared client's implicit final `quit`, while exit/EOF and OS receipts separately
verify cleanup. Per-cell external timestamps are absent. Verification ordering
can affect fail-soft special-band handling or which iteration survives a stop;
matching these finite scores/PVs is not a general equivalence proof.

## Decision and evidence

Retain the tested ordering change inside the disabled null experiment and its
work counters. Do not promote null pruning, retune this sample, or prioritize a
large qualification for this tiny change. No new game, replacement campaign,
automatic schedule, push or release is part of this phase. The six Phase 4F.13
forfeits and unresolved clock-readiness requirements remain intact.

Next proposed **Phase 4F.16**: defer sorting of remaining ordinary moves after
the legal contextual TT move, on the accepted LMR-on/null-off path. Freeze
ranking keys before that child in storage its recursive searches cannot reuse;
delaying scoring would observe changed histories and alter ordering/LMR.
Preserve tie order, learning prefixes and move indices; initially keep
speculative/ProbCut paths eager. It requires its own finite protocol and exact
baseline checks; no large gain is promised. Controlled timing still needs a
fresh suitable window, and game qualification additionally needs clock readiness.

Evidence directory: `results/phase4f15-null-verification-20261030/`, containing
build/source archives, all test logs, raw screen, independent auditor and review,
preservation, cleanup and documentation receipts. Raw screen SHA-256:
`0a15ebf7ad9ea410722e17f8dfc90b8d0ec29760a83aa4b82700f4cd7c458369`.
Independent audit SHA-256:
`efa5947cb76a373cae420326c5e2d986a76c87c8e0abbcf949c9bd73f95b6edc`.
