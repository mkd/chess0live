# Phase 4D: search efficiency with strength gates

Status: Phase 4D.1 complete with countermove ordering parked after a mixed
360-search screen; [results and decision](reports/2026-10-18-phase4d-countermove.md).
Phase 4D.2 finished all 1,024 games: its [audited result](reports/2026-10-19-phase4d2-results.md)
fails the absolute reliability gate despite 59.33% points, with 19 candidate
flagfalls and 65 baseline flagfalls. LMR stays off; diagnose clock behavior
before another qualification, without extending or retuning this sample.
Phase 4D.3 verified null-move pruning is implemented and checked under its
[separate development protocol](experiments/phase4d3-null-move.md). Its
[mixed cold/warm screen](reports/2026-10-18-phase4d3-null-move.md) leaves it off
by default. Phase 4D.4 reverse futility is also implemented and checked:
[its 60-search screen](reports/2026-10-19-phase4d4-reverse-futility.md) found
12.72% fewer fresh-cache nodes but only 1.53% fewer reused-cache nodes, with
2.28% longer reused-cache elapsed time. It stays off without repeated tuning.
**4D.5 quiescence SEE is implemented and checked**, with
[60 audited profile searches](reports/2026-10-20-phase4d5-qsearch-see.md):
fresh-cache nodes fell 11.62%, reused nodes 1.58%, and one timed root completed
an extra depth. Starting-position score/PV changes are retained. It stays off.
The required matched 60-second puzzle checkpoint is also complete: 39 positions
per build, one worker, no errors, all best moves matching. Both reported M7 on
position 2 and centipawn scores on the other 38; only position 29's score
differed (+9.16 to +9.59). There were no reported mate gains, losses or distance
changes. The independent audit passed; this exposed suite establishes no Elo
gain. The owner's October 20 daytime exception covered this completed run only.
Do not tune this sample. The
[short instrumented diagnostic](reports/2026-10-20-clock-boundaries.md) is now
complete: 32/32 replies were on time, but the historical large delays did not
reproduce. No cause or clock fix is established from the saved Phase 4D.2
failures. The subsequent [four-worker match-readiness screen](reports/2026-10-20-match-readiness.md)
passed all eight games and 646 on-time searches, with actual four-way overlap
and complete cleanup. The lower concurrency is a new test condition, not a
repair. The [fresh 512-game qualification](reports/2026-10-22-lmr-preparation.md)
is now prepared with 256 new pairs and four workers; 145 workflow checks and
independent search-free readiness passed. No game or schedule has started.
The prepared tools permit overnight launch only; a newly authorized daytime
exception would first require a tested, recorded protocol/tool amendment.
Make its promotion,
rejection or parking decision before adding broader 4D.6 reductions. Delta
pruning remains separate and unimplemented.
This follows the owner's
October 18 request and is a sequence of bounded experiments, not an enabled
bundle of new pruning rules. Phase 4E retains broader platform execution and
network tooling. No campaign or schedule is started by this document.

## Objective and current evidence

Spend the available thinking time on better moves. Reducing nodes, completing
more nominal depth, or increasing NPS is useful diagnostic evidence, but only
equal-resource playing results can establish a strength improvement.

The owner supplied both depth-10 transcripts on October 18. chess0live reported
34,711,512 nodes in 145,872 ms; Gargantua reported 50,904 nodes in 74 ms. Those
are about **681.9 times the nodes** and **1,971.2 times the reported elapsed
time**. The visible search-work gap strongly motivates this phase. The logs do
not record complete settings, starting history, cache state, binary/network
pins, hardware/load, or a controlled repeat; they are owner observations, not
qualification data. See [the recorded comparison](reports/2026-10-18-depth-feedback.md).

We will not reuse Gargantua's search code or testing assets. Different
reductions, extensions, quiescence policies, transposition-table contents, and
node-counting conventions make nominal depth and node totals unsuitable as a
cross-engine quality metric. With Lazy SMP, chess0live's node total also
includes helper work; compare equal thread counts and distinguish leader depth
from aggregate work. The next candidate must improve useful equal-time results,
not merely imitate the other engine's reported depth.

chess0live already has mate-distance bounds, PVS, aspiration windows, interior
check extensions, transposition bounds, MVV-LVA, killer ordering, bounded
positive/negative history-gravity updates, quiescence, and an opt-in conservative
LMR experiment. Outer iterative deepening is implemented; internal iterative
deepening at a node without a useful hash move is a separate, unimplemented idea. The
[LMR development record](SELECTIVE_SEARCH.md) reported 49.79% fewer nodes at
depth 5 on its exposed sample, but that was not strength qualification. Later
qualification was inconclusive or failed an operational gate. These results
motivate useful next work; they do not authorize switching LMR on by default.

## Work order and finite checkpoints

Implement one isolated candidate, complete its bounded checks, and record one
decision before moving to another. Reuse the existing profiling, referee, and
paired-match infrastructure where suitable. Do not spend another series of
phases tuning a single unsuccessful heuristic.

| Order | Candidate | Initial scope and safeguard |
| --- | --- | --- |
| 4D.1 | Better full-depth move ordering | First test improved quiet-history updates or a countermove ordering signal, one at a time. Then consider continuation history and a staged move picker as separate candidates. Keep the current capture policy and search depths unchanged while isolating each idea. |
| 4D.2 | Existing conservative LMR | Reassess the existing opt-in one-ply reduction on the current engine with a separately frozen protocol. Preserve its check, promotion, advanced-pawn, TT/killer, and mate-band exclusions and mandatory ordinary-depth re-search when a reduced probe raises alpha. Do not broaden reductions and change ordering in the same experiment. |
| 4D.3 | Verified null-move pruning | Begin with a restrictive interior non-PV experiment: no check, no mate-band window, no consecutive null moves, adequate depth, and non-pawn material. Add ordinary-search verification before a candidate cutoff and explicit zugzwang exclusions/tests. Material guards and verification reduce risk; neither proves every position safe. |
| 4D.4 | Conservative reverse futility | Separate shallow interior non-PV candidate, disabled in check and near mate/tablebase score bands. Freeze depth-dependent margins before testing; keep checks, tactical exceptions, and draw handling explicit. |
| 4D.5 | Quiescence work reduction | Test SEE-based capture pruning and delta pruning separately. Preserve all check evasions, promotions, mate/stalemate handling, and designated tactical exceptions. Static material estimates do not justify silently dropping a forced line. |
| 4D.6 | Late quiet-move pruning or broader reductions | First resolve the clock-reliability blocker and make a qualification decision on existing conservative LMR. Only then consider one separate higher-risk reduction hypothesis, with dedicated late quiet tactics, pawn breakthroughs, and zugzwang tests. |
| 4D.7 | ProbCut | A separate later candidate: bounded reduced-depth tactical probes at an elevated cutoff threshold, with frozen margins and explicit check, mate/tablebase, and draw exclusions. A successful reduced probe is heuristic evidence, not proof of a full-depth bound. Require sacrificed-material and quiet-defense regressions and an isolated strength comparison. |

The owner supplied Gargantua's optimization list during 4D.1. Treat it as a list
of techniques to consider, not source or assets to copy. After this single
ordering checkpoint, prioritize the existing LMR qualification and verified
null-move experiment for larger work reductions. Add internal iterative
deepening as a separate later ordering candidate: at eligible nodes without a
useful TT move, a bounded shallower search may supply a hint, but the original
depth search must still run. Its extra search cost must be measured. Do not
combine it with the current countermove experiment.

Forward futility (skipping individual late quiet moves) and reverse futility
(returning a static bound at a node) must use separate candidates, despite the
shared name. The former belongs with 4D.6, the latter with 4D.4. Null-move depth
reduction is part of the reduced null probe in 4D.3, not a license to remove its
verification or zugzwang safeguards. Neither those techniques nor ProbCut can
be promised to lose no strength at all; full-depth ordering also needs
equal-time evidence because it changes allocation of finite search time.

4D.1 is the first implementation checkpoint after tablebases. Its exit is one
tested candidate and a reproducible decision, not completion of every row.
Subsequent rows are priorities, not a commitment to retain every technique.
If a candidate fails, keep the recorded failure and advance to the next
justified idea. New hypotheses use new records; unsuccessful runs are not erased.

Full-depth ordering does not intentionally discard moves, making it the best
first candidate. It can still change which useful iteration completes before
the clock expires, which tied move is chosen, and how existing selective rules
behave. It therefore needs playing-strength evidence too. Heuristic pruning
can miss a critical move; do not describe it as mathematically strength-safe.

## Isolation and implementation checks

Each candidate starts from a frozen current parent with the same network,
compiler/CPU backend, hash budget, tablebase policy, and time manager. Keep
`Time Policy=classic`, diagnostics off for timing and matches, and unrelated
search experiments off. Use `Threads=1` first to isolate the technique; follow
accepted results with a separate `Threads=4` interaction check under equal
resources. Tablebase access must be identical on both sides and remain a
separate experimental factor.

- Candidate-off searches must preserve the parent behavior on the fixed
  regression corpus. Candidate-on full-depth ordering should retain completed
  minimax scores in controlled searches without selective pruning; inspect
  differences rather than forcing identical tied moves or node counts.
- Independently verify legal best moves and complete PVs. Exercise captures,
  en passant, castling, underpromotion, checks, stalemate, signed mate scores,
  repetition, the fifty-move boundary, and tablebase score boundaries.
- Add independently authored tactical and zugzwang regressions for the actual
  failure modes of the candidate. Use both colors and interrupted searches.
  Reproduce a failing position before changing chess logic. Exposed owner
  puzzles remain development diagnostics, not fresh qualification positions.
- Every new incremental state must undo exactly after ordinary moves, null
  moves, re-searches, and cancellation. A null move must not create a legal-game
  repetition or manufacture a rule-50 draw. Do not reuse incompatible selective
  bounds after switching policies; invalidate cached state appropriately.
- Run relevant native, scalar, and sanitizer checks. Concurrent mutable
  histories remain worker-local; shared state needs explicit synchronization
  and applicable race checks. Recheck immediate stop, ponderhit, node limits,
  hard deadlines, and one legal bestmove per request.

Record all failures. A tactical test pass is finite evidence, not proof of
universal correctness or strength preservation. Reject a reproducible serious
tactical, clock, protocol, or state-restoration regression before a long match.

## Bounded development measurements

Before searching, freeze a small exposed corpus spanning openings, tactical
middlegames, quiet positions, and endgames; declare the depth/time limits,
repetitions, role order, and interruption policy. Keep table state controlled:
fresh-search profiles clear it; a separately labeled warm-table check preserves
it. Include both, rather than comparing one engine's warm search to another's
cold search. Do not compile or run another benchmark during timed measurements.

Report wall-clock time, nodes, NPS, completed depth/seldepth, best moves, scores,
and unfinished iteration work together. Also count eligibility, reductions or
prunes, and verification/re-search work with diagnostics in separate runs.
The main performance question is time to useful results under an equal time
budget. Fixed-depth and fixed-node measurements help explain the mechanism;
they do not select the strongest candidate by themselves.

An exploratory operational match may verify complete legal games and clocks.
Its outcome is reported, including losses, but a small smoke test is not a
promotion test. At most one bounded diagnostic revision is part of a candidate's
initial checkpoint. A further revision requires a new hypothesis/record rather
than repeatedly searching for a favorable screen on the same data.

## Strength qualification and default promotion

Prepare a separate frozen comparison only for a candidate that passes the
implementation and operational checks. Use fresh held-out opening histories,
colors reversed, equal resources, and full PGN/protocol/clock records. Match
candidate against its frozen parent first; separately compare retained changes
against external opponents to check that self-play gains generalize.

The experiment protocol must declare, before the first held-out search:

1. The exact isolated hypothesis, binaries, source/network/tablebase digests,
   settings, opening exclusions, blitz time control, and resource admission.
2. A fixed maximum number of complete opening pairs or a justified sequential
   design. State the uncertainty method and stopping rule; use pair-level
   observations and at least 95% confidence. Do not stop early because a
   conventional repeatedly inspected interval becomes favorable. Testing many
   variants needs a fresh final holdout and an explicit multiplicity policy.
3. A practically meaningful target and a realistic local-compute budget. The
   initial planning target is +5 Elo against the parent (about 50.72% expected
   score), not a promised detectable effect. Choose sample size from the
   declared statistical method and target before the campaign. If local compute
   cannot resolve that margin, say so and retain an inconclusive outcome.
4. Promotion requires passing all operational gates, an observed gain meeting
   the predeclared practical target, and the 95% lower confidence bound for
   expected score above 50%. Report W/D/L, pair count, margin, uncertainty, and
   limitations. A noninferiority result alone supports no positive Elo claim.

These are planning requirements, not an already executable match protocol.
The final design may set a larger meaningful target to fit available compute;
it must do so before seeing results. No finite match proves that strength can
never decrease in another time control, opening family, or hardware setting.

An unfavorable or inconclusive result keeps the accepted default unchanged.
Do not reinterpret "no statistically significant loss" as equivalent strength,
trade an unexplained tactical regression for extra depth, or pool unsuccessful
experiments into a favorable new sample. Initial gains are specific to the
tested blitz conditions; verify a separately declared longer-control sample
and four-worker interactions before making broad claims or expanding rollout.

The frozen [Phase 3L](PHASE_3L.md) 512-game LMR comparison remains unstarted and
belongs to its original binary, roots, and protocol. Do not silently retarget it
to a new engine, use its untouched roots for development, merge its eventual
results with a new campaign, or treat earlier daytime exceptions as permission
for new long tests. A future current-engine candidate needs its own declared
comparison. Development proceeds while historical frozen campaigns remain
separate; they do not block 4D.1.

All work remains local: modest short checks within the current resource budget;
long tests overnight, 23:00–07:00 Europe/Helsinki, unless the owner authorizes a
specific exception. No automatic schedule. Preserve stable GUI bundles and
the README introduction, document decisions, and commit tested changes locally
on main for the owner's manual push.
