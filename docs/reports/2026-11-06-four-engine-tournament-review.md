# Four-engine tournament: results, source review and development priorities

Originally reviewed November 6, 2026. The tournament's execution date was not supplied.
Status: owner-reported tournament summary and read-only source inspection;
not a reproduced match, accepted strength improvement, or release qualification.

**Subsequent attachments materially qualify the interpretation.** Read the
[Linux configuration follow-up](2026-11-06-linux-tournament-followup.md) first.
The owner used raw initialization commands without tournament resource edits;
the saved Options fields would override those commands under verified Cute Chess
v1.5.1 startup behavior. chess0live's profile stores Threads 1 / Hash 64 / LMR
false and a historical maximum of one thread. A subsequent live Linux handshake
advertises max 64 / LMR default true, confirming stale GUI metadata relative to
the probed executable; its supplied digest still does not prove tournament
binary continuity. The final Sic–Hyperion game was recovered and legally replayed;
the complete tournament PGN was not saved. Verify build and applied options
before treating this as a current, equal-resource engine comparison.

## Conclusion

The reported result is a serious playing-strength signal for the chess0live
configuration that played, whose relationship to current defaults is unverified.
Its three wins were all opponent disconnects; its other games were
**0 wins, 20 mate losses and 7 draws**. Hyperion and Gargantua won substantial
numbers of games by mate. Prioritize useful search per second and useful work
from multiple workers, while preserving independent evaluation and chess rules.
The summary cannot identify the losing decisions or assign the gap to a feature.

The most useful source-backed hypotheses are selective-search interactions,
avoidable NNUE work, and transposition-table/SMP effectiveness. Many familiar
features already exist in chess0live. Adding a feature because a stronger engine
has it, enabling every experiment, or importing a competitor's evaluator is not
an evidence-backed improvement.

## Supplied results and reconciliation

Owner settings: **2 minutes + 1 second per move; Threads 10; Hash 1024 MB;
Syzygy disabled; ponder disabled** for each engine. No PGN, opening list,
cross-table, engine output, process exits, executable/network hashes, full UCI
profiles, machine/concurrency details or crash logs accompanied the summary.
The reported common settings are not independently verified effective settings.

| Engine | Games | Wins | Losses | Draws | Points | Score | Reported Elo ± |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Hyperion | 30 | 22 | 0 | 8 | 26 | 86.7% | 325 ±134 |
| Gargantua | 30 | 15 | 3 | 12 | 21 | 70.0% | 147 ±102 |
| sic | 30 | 3 | 20 | 7 | 6.5 | 21.7% | −223 ±134 |
| chess0live | 30 | 3 | 20 | 7 | 6.5 | 21.7% | −223 ±134 |

These are the supplied pool-relative estimates, not calibrated absolute ratings.
The estimator and interval definition are unknown. The supplied SPRT line has
LLR 0 and infinite boundaries; it provides no finite sequential-test decision.
Thirty appearances per engine do not justify a precise long-term ranking or a
claimed Elo deficit. Equal aggregate scores do not establish equal playing strength.

| Engine | Mate wins | Mate losses | Disconnect wins | Disconnect losses | Repetition draws | Insufficient-material draws | Stalemates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hyperion | 20 | 0 | 2 | 0 | 7 | 0 | 1 |
| Gargantua | 13 | 3 | 2 | 0 | 10 | 1 | 1 |
| sic | 3 | 13 | 0 | 7 | 7 | 0 | 0 |
| chess0live | 0 | 20 | 3 | 0 | 6 | 1 | 0 |

The summary reconciles to **60 games: 36 mates, 7 disconnects and 17 draws**.
There are 43 wins and 43 losses across 120 player appearances, 34 draw
appearances and 60 total points. All seven disconnect losses belong to sic;
therefore all three chess0live wins were against sic, if the supplied categories
are complete. No other full head-to-head table can be recovered. Ten games per
pair and color-balanced openings must not be assumed merely from the totals.

For description only, removing every disconnect game gives:

| Engine | Remaining W–D–L | Remaining games | Points / games | Score |
| --- | --- | ---: | --- | ---: |
| Hyperion | 20–8–0 | 28 | 24 / 28 | 85.7% |
| Gargantua | 13–12–3 | 28 | 19 / 28 | 67.9% |
| sic | 3–7–13 | 23 | 6.5 / 23 | 28.3% |
| chess0live | 0–7–20 | 27 | 3.5 / 27 | 13.0% |

Formula: `(wins − disconnect wins + draws / 2) /
(games − disconnect wins − disconnect losses)`. This changes opponent exposure
and selects on termination, so it is **not an unbiased adjusted rating** or a
prediction of what the disconnected games would have become. Keep the official
standings intact. No chess0live disconnect or time-loss category is reported;
this does not clear the six historical Phase 4F.13 clock forfeits. Being mated is
an endpoint, not proof that every loss originated in a tactical search bug.

## Source identities and implementation boundary

The user explicitly requested comparative source inspection. This review uses
the other engines for high-level hypotheses only: no code, constants, runners,
positions, tests, networks or other testing assets were copied into chess0live.
The existing independence requirement remains in force. Fathom's authorized
tablebase-only exception is unchanged and irrelevant to a no-Syzygy tournament.

| Repository | Reviewed local HEAD | Working tree at inspection |
| --- | --- | --- |
| [chess0live](https://github.com/mkd/chess0live) | `491d105c9a790a01515c6b5e64c215c35d2b643a` | Owner edit in `tools/batch_positions.py`; preserved |
| [Hyperion](https://github.com/mkd/hyperion) | `d99868ad217dd44fdf48cd1527bad9d271533cb8` | Clean |
| [Gargantua](https://github.com/mkd/gargantua) | `5ae52eeb8212be55c550e0ba2cf7da03208af220` | Tracked files clean; untracked artifacts present |
| [sic](https://github.com/mkd/sic) | `1442e5bfbdf36a543dea10aa119d4cfeef7a370a` | Tracked files clean; 20 untracked files |

Local roots are `/Users/claudio/projects/Chess/<repository>/`. The chess0live
path resolves to the active CloudStorage checkout, not a separate source copy.
References below are file and line locations at these reviewed commits. Local
HEAD and repository webpages do **not** identify the tournament executables.
The protected GUI snapshot is `build/test-baselines/0.1-dev-4b8b35d/`; another
preserved Phase 3F bundle also exists. Neither a normal rebuild nor this review
updates those bundles or proves which one played. Saved Cute Chess options can
override current defaults, including LMR.

## What the code establishes

### Evaluation is materially different

chess0live independently implements its pinned SF19 SFNNv16 evaluation, including
piece-square, threat and pawn-pair features; see [NNUE](../NNUE.md),
`src/nnue.cpp:332–392,793–830`. Its current evaluator updates from the last
evaluated board, with one accumulator pair per worker.

Hyperion and Gargantua compile Stockfish-derived evaluation code with a
HalfKAv2_hm big/small architecture (2560/128 transformer dimensions). Hyperion:
`Makefile:267–272`, `src/stockfish_probe/nnue/nnue_architecture.h:37–55`.
Gargantua: `src/eval.cpp:54`,
`src/stockfish_probe/nnue/nnue_architecture.h:28–55`,
`src/stockfish_probe/evaluate.cpp:164–180`.
Sic also directly compiles and calls vendored Stockfish evaluation:
`Makefile:30–40`, `src/evaluate.cpp:15–20`,
`src/stockfish_probe/sf_wrapper.cpp:116–117`.

This confounds cross-engine NPS and depth comparisons. It does not establish
that an older/smaller architecture is stronger, nor that chess0live's verified
arithmetic is wrong. Importing those evaluators would violate this project's
requirements. New architecture work would need an explicit independent design,
provenance, parity and strength qualification; it is not the immediate response.

### Search policy is the clearest qualitative difference

Current chess0live defaults retain PVS, aspiration, check extensions, contextual
TT bounds, quiescence, quiet history, killers and conservative one-ply LMR. SEE
ordering, deeper reductions, null pruning, reverse futility, ProbCut, quiescence
SEE/delta, move hints and continuation history remain optional. Evidence:
`src/main.cpp:280–292`, `include/chess0live/search.hpp:61–85`,
`include/chess0live/search_policy.hpp:209–268`.

Hyperion integrates broader selective search and contextual ordering:
`src/search.cpp:691–812,874–979`; Gargantua also uses a broad always-on package:
`src/search.cpp:255–430,493–510,570–662`. Sic has many of these mechanisms too
(`src/search.cpp:533–641,679–807`) despite its weak tournament result. Feature
count is therefore not a useful ranking or proof of causation.

Retain the proposed Phase 4F.20 null/deep-reduction interaction test. Do not
enable everything from this review: the completed Phase 4F.19 screen found only
mixed additional depth from all-on, and no strength gain. Existing tactical and
match evidence continues to govern promotion.

### Avoidable evaluation work deserves a distinct experiment

Hyperion caches static evaluation in its TT and applies correction separately
(`src/tt.h:55–63`, `src/search.cpp:645–676,1059–1066`); it also performs some
pruning before applying a move to its NNUE mirror (`src/search.cpp:874–939`).
chess0live's TT stores searched scores, not raw NNUE components
(`include/chess0live/detail/transposition_entry.hpp:38–43`), and quiescence calls
evaluation without its own TT probe (`src/search.cpp:665–685`). Its previously
recorded Phase 4F.17 sample placed much active search work in NNUE, but that is
one historical sample, not a profile of these tournament games.

A possible independent candidate is a bounded raw-component evaluation cache,
only after measuring repeat opportunities and lookup cost. Do not confuse a
board-based evaluation with a history-sensitive search bound. Include network
generation, side/orientation and all relevant evaluator inputs; the final
wrapper depends on the halfmove clock (`src/nnue.cpp:820–830`). Cache raw
components and reapply the existing evaluation wrapper, or include the required
wrapper context. Preserve
terminal/draw precedence and arbitrary skipped-evaluation transitions. This is
a different hypothesis from Phase 4F.17's rejected accumulator checkpoints;
do not quietly restore that failed candidate or repeat Phase 4F.16 sorting work.

### Equal settings do not establish equal cache or parallel efficiency

chess0live has private worker state, shared TT and root tie-order variation.
Only worker zero supplies the final result; helpers contribute through shared
search information (`src/search.cpp:531–545,1504–1555`). Gargantua and Sic also
use main-worker final selection, so this alone cannot explain the ranking.
chess0live's striped mutexes protect concurrent TT access (`203–206,405–447`);
its score key includes reversible history and halfmove context (`377–385`).
These choices may affect contention and reuse, but must not be discarded just
to imitate a higher-ranked engine. Hyperion and Gargantua have unsynchronized
shared TT fields (`Hyperion src/tt.h:28–30,55–63`; `Gargantua src/tt.cpp:208–281`),
which are C++ concurrency concerns, not acceptable performance shortcuts.

There is also a concrete memory difference at the reported setting. Current
chess0live computes `bit_floor(1024 MiB / 96)` buckets and stores 64 bytes per
bucket: **8,388,608 buckets, 33,554,432 entries, 512 MiB of retained TT storage**
with move hints off. Hyperion allocates **1024 MiB and 67,108,864 entries** at
that setting (`src/tt.cpp:153–164`, `src/tt.h:55–79`). These are source-derived
figures, not tournament memory measurements. chess0live intentionally retained
its historical bucket geometry during packing; see
`include/chess0live/detail/transposition_entry.hpp:21–26,75–77` and
`src/search.cpp:179–190`. Total process memory includes networks, workers and
other allocations, and the engines use different key representations.

Measure one-worker versus permitted multi-worker quality, TT hits/cutoffs,
worker contribution and actual memory before changing capacity or scheduling.
A Hash geometry change alters collisions and search, so it needs its own
qualification. Ten threads is not evidence of ten times useful search. Do not
infer excess host load either: concurrent games and hardware were not supplied.

### Existing history and clock behavior must not be rediscovered

chess0live already retains/decays quiet history and optional continuation
history (`src/search.cpp:1203–1206`). It already has soft/hard limits and
best-move stability/score-drop allocation
(`include/chess0live/time_management.hpp:20–39`). Hyperion provides a useful
comparison, but neither feature is absent from chess0live. Gargantua resets
ordering history each search (`src/search.cpp:867–873`), so retained history is
not a universal explanation of the stronger results. Fresh-process root screens
cannot measure cross-move history benefit; use whole game sequences for that.

## Sic reliability findings: hypotheses, not tournament diagnoses

Read-only source inspection identified several concrete investigation routes:

- **Long history and accumulator bounds:** UCI replay pushes accumulator state
  for game moves (`src/uci.cpp:69–73,98–102`;
  `src/stockfish_probe/sf_wrapper.cpp:86–91,124–129`). Its 247-entry stack starts
  at size one; the attempted 247th combined game-history/search push exceeds
  capacity (`src/stockfish_probe/types.h:117`,
  `src/stockfish_probe/nnue/nnue_accumulator.h:109`,
  `src/stockfish_probe/nnue/nnue_accumulator.cpp:106–111`). Reset occurs before
  history replay, without subsequent root rebasing. Investigate both replay and
  search against a full failing game's history; no failure was reproduced here.
- **Allocation lifecycle:** each `go` coordinator calls `init_thread`, allocating
  raw accumulator/cache pointers without matching ownership cleanup
  (`src/uci.cpp:179–182`, `src/stockfish_probe/sf_wrapper.cpp:19–42`). Measure
  memory over repeated searches before assigning a disconnect to exhaustion.
- **Check-position assertion:** search evaluates after computing `in_check`
  (`src/search.cpp:533–534`), while the wrapped evaluator asserts no check
  (`src/stockfish_probe/evaluate.cpp:47`). Debug/release build identity matters.
- **Startup allocation:** 4096 MB is allocated before GUI Hash override
  (`src/main.cpp:17`, `src/tt.cpp:10–23`). Gargantua also allocates 4096 MB on
  startup (`src/main.cpp:72`); reported Hash 1024 is not the startup peak.
- **Configuration evidence:** Sic's EvalFile option changes a string while its
  initializer loads the compile-time default (`src/uci.cpp:267–269`,
  `src/stockfish_probe/sf_wrapper.cpp:26–34`). Verify the actual loaded network.

None has been tied to one of the seven disconnects. Retain stderr, process exit
status, crash records and full PGN before diagnosing. No Sic files were changed.
For chess0live these are reasons to preserve long-history, repeated-go,
option-verification and cancellation coverage, not evidence that it has the same
defects. An undefeated result likewise does not prove Hyperion race-free.

## Ordered follow-up and decisions

1. **Identify the build and verify the setup.** The subsequent
   [configuration follow-up](2026-11-06-linux-tournament-followup.md) found
   conflicting initialization/saved options and an old or stale chess0live
   profile. Resolve the Linux executable identity, refresh its registration and
   verify final applied options before another comparison. The owner confirms
   no full tournament PGN was saved; the recovered final game contains no
   chess0live moves. Loss reconstruction therefore remains a requirement for
   future retained games, not a claim that these missing games can be recovered.
   Keep openings/color policy, host, concurrency, full logs and file hashes.
   Any later oracle remains external and pinned; exposed games are development
   evidence, with separate held-out openings for qualification.
2. **Complete the existing selective-search diagnosis.** Prepare the separate
   Phase 4F.20 five-profile protocol already described in
   [the search plan](../SEARCH_OPTIMIZATION_PLAN.md#proposed-phase-4f19-combined-search-diagnosis).
   Keep LMR on and isolate null/deep-reduction interaction in the all-on context.
   Its 75 searches are a finite diagnostic, not a parameter sweep or an Elo test.
   Decide whether a specific package merits tactical/clock qualification from
   the complete results; do not promote settings from nominal depth alone.
3. **Measure the actual ten-thread use case.** Start with one worker, then 2/4
   and 10 only if permitted by aggregate host limits. Use fixed identified
   binaries/networks, equal wall time, full UCI outputs, actual TT allocation and
   retained-session tests. Check clock stop/join behavior and memory as well as
   nodes and final move quality. Profile contention/repeated evaluations before
   selecting either a cache/SMP or raw-evaluation-cache implementation candidate.
4. **Make one independent, falsifiable change.** Freeze the hypothesis and
   acceptance gates before coding. A raw-evaluation cache must preserve exact
   evaluation/search semantics at deterministic single-thread fixed limits;
   pruning, TT geometry and scheduling changes need their own behavioral tests.
   Check meaningful tactical and lifecycle failures, then run a fixed-sample or
   properly specified sequential paired-opening match against the retained
   parent. Preserve losses, failures and inconclusive outcomes. Only held-out
   strength evidence can justify a default promotion.

The active development checkpoint remains **Phase 4F.19 complete**. Phase 4F.20
remains proposed; this review adds priorities and evidence requirements, not a
launched experiment or a new schedule. No production behavior/default, network,
GUI bundle or release changed. No new engine build, game or search was run.
Arithmetic and source findings were independently reviewed; documentation links,
README introduction, owner edit, production source and GUI bundle preservation
were checked before the local documentation commit. GitHub publishing remains
with the owner.
