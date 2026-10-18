# Owner-run Cute Chess feedback — October 18, 2026

The owner reports two draws against Gargantua 2.1, one with each color, with no
engine errors or disconnections. Seven screenshots and one partial PGN accompany
the feedback. These newly played games provide useful GUI and clock observations;
two draws do not establish equal strength, an Elo rating, or a Phase 3F strength
gain. No engine code, option default, or frozen Phase 3G input changed in this review.

## Snapshot and evidence limits

The intended GUI snapshot is **`0.1-dev-phase3f-20261017`**, described in
[manual testing](../MANUAL_TESTING.md). Its executable still has SHA-256
`edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b`.
The recommended settings were Threads 1, Hash 64 MiB, Move Overhead 20 ms,
Ponder false, classic timing, LMR off, MVV-LVA ordering, diagnostics off, and the
pinned `nn-1a298aa575a0.nnue`. The PGN records 180+2, engine names and rounded
score/depth/time annotations, but no executable hashes or actual UCI options.
The supplied evidence therefore does not independently identify the running
binary, GUI version, hardware, or options. The original `0.1-dev-4b8b35d` GUI
bundle also remains unchanged.

The [supplied game 1 PGN](2026-10-18-cutechess-game1.pgn) is preserved byte for
byte from `/Users/claudio/game1.pgn`, SHA-256
`66c816ec7647e0ecf47def4d785237927791d474c6f324041a51dde2c314246c`.
It ends at **61.Nc3**, with `Result "*"` and `Termination "unterminated"`.
The final saved position is:

```text
8/8/1p6/8/P7/1kN5/3K4/8 b - - 2 61
```

It has five legal moves and is not checkmate, stalemate, insufficient material,
or a claimable repetition/fifty-move draw. The last capture is 60.Kxd2; there
are no promotions in the saved portion. This does not contradict a later draw,
but the final result cannot be verified from this incomplete file. Game 2 has
no PGN and cannot be replayed to its ending.

The tournament screenshot records **0 wins, 0 losses, 2 draws**. Its two reason
categories are **"Draw by adjudication: user decision"** and **"Draw by
insufficient mating material"**, one of each. They are not assigned to individual
games in that summary. The owner's description of a fifty-move ending in game 2
remains unverified; it differs from the recorded categories. Do not silently
relabel either game. The displayed `0.0 +/- 0.0` Elo and `nan` LOS are not useful
uncertainty estimates for this two-game, all-draw sample.

## Clock allocation

Game 1's main issue is **early depletion of the clock reserve**, rather than
uniformly longer moves. chess0live spends **21 seconds on 2.d4, 26 on 3.e5,
and 23 on 6.Bd3**: 70 seconds across those three early decisions.

| Through each side's move | chess0live time used | Gargantua time used | Approximate remaining clocks, chess0live / Gargantua |
| --- | ---: | ---: | ---: |
| 8 | 103.7 s | 58.8 s | 92.3 / 137.2 s |
| 20 | 200.1 s | 128.9 s | 19.9 / 91.1 s |
| 34 | 247.7 s | 191.8 s | 0.3 / 56.2 s |

The estimates use `180 + 2 * completed_moves - sum(annotated_seconds)`.
Annotations are rounded and omit exact transport/GUI accounting; these are not
captured UCI clocks. By move 60 this calculation yields -0.1 seconds for White,
demonstrating its limited precision, not a verified time forfeit. The 08:13:23
screenshot after 34.Rg1 shows 00:01 against 00:59, corroborating the imbalance
without providing an exact common timestamp for both completed searches.

The full saved game's median think time is actually 2.3 seconds for chess0live
versus 4.25 for Gargantua: chess0live subsequently plays near the increment.
Game 2's screenshots show a similar pattern: chess0live has 00:20 against 01:11
after 27...exf2+, then a displayed 00:00 against 00:17 after 71...Kg1. A rounded
zero display with a two-second increment does not establish flagfall; no such
result is reported.

The current [time allocation](../../src/search.cpp) is consistent with these
long thinks. Nominal soft time is available clock divided by estimated remaining
moves, plus 80% of increment. The hard allowance is up to four times that soft
budget, capped by the available clock after overhead. Best-move stability and
score drops adjust the soft target. **Soft stopping is checked after a completed
iteration; the hard deadline is checked within search.** An expensive next
iteration can therefore consume much more than the preferred target.

Assuming the intended 20 ms overhead, no `movestogo`, and clocks reconstructed
from rounded annotations, nominal soft/hard budgets are about **7.12/28.50 s for
2.d4**, **6.53/26.12 s for 3.e5**, and **5.64/22.58 s for 6.Bd3**. These are source
calculations, not reproduced timed searches. The rounded 23-second annotation
is compatible with the last allowance. There is no raw iteration trace here
to establish wasted work or prove a deadline violation.

Phase 3F made evaluation faster without changing this policy. More work can fit
inside the same allowance, and a faster iteration may allow the next expensive
one to begin; faster evaluation need not produce earlier moves. The existing
experimental forecast policy addresses iteration cost, but its previous
[strength screen](2026-10-15-phase2d-time-policy.md) was inconclusive. These games
do not justify enabling it or tuning a new reserve policy to this small sample.

## Search depth and playing observations

| Engine in saved game 1 | Annotated moves | Median completed depth | Range |
| --- | ---: | ---: | ---: |
| chess0live, White | 61 | 7 | 6–12 |
| Gargantua, Black | 60 | 22 | 18–25 |

The owner's impression of strong positional play is encouraging feedback,
not an established strength result. Different searches use different reductions,
pruning, and extensions, so reported depth is not a common work or strength
scale. chess0live's defaults still disable LMR, and it has no null-move or
futility pruning. Its check extensions and quiescence can reach beyond nominal
depth: the screenshot's `7/18` reports nominal depth 7 and selective depth 18,
not a uniform 18-ply search. Search efficiency remains a real development task.

In game 2's late screenshot the engines also disagree substantially on score.
Without the complete history and controlled analysis, this does not establish
a forced win, an NNUE defect, or incorrect rule-50 handling. No evaluation
oracle comparison or analysis search of game 2 was performed in this review.

## Checks and next checkpoint

Independent `chess==1.11.2` replay accepted all **121 plies / 122 positions** of
the saved PGN. The preserved Phase 3F executable matched the referee's complete
legal root sets and **every depth-2 divide branch at all 122 positions**. The
ordered FEN corpus SHA-256 is
`f1447376a9d40ed67c49f1facb989f059f1006087889f4a2f25d3112ad347534`.
These checks do not verify the missing endings or the GUI's runtime settings.

Raw local evidence is in ignored `results/manual-cutechess-20261018/`:
`verify_feedback.py`, `verification.json`, `positions.fen`, and
`divide-transcript.txt`. The script reproduces replay, annotation statistics,
move checks and frozen-input integrity with one worker under the normal 50%
daytime policy. Its first invocation completed move checks but failed while
reading a nonexistent integrity-record key; correcting that review-script key
and rerunning passed. No engine failure was observed. No NNUE oracle campaign,
timed search, strength match, rebuild, or schedule was started.

**Phase 3F remains complete and retained; Phase 3G remains prepared, unstarted.**
The next planned checkpoint is the frozen overnight 512-game LMR on/off screen,
followed by its independent audit. Its sources, suite, executable and network
still match readiness hashes. Keep these GUI games as exposed diagnostic data,
outside that held-out suite. Clock allocation warrants a separate subsequent
experiment with completed/interrupted-iteration diagnostics and strength checks;
do not mix timing changes into Phase 3G. No more manual games are required to
unblock development. The engine remains `0.1-dev` with unchanged defaults.
