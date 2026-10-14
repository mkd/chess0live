# First owner-run Cute Chess feedback — October 14, 2026

The owner reports that UCI works correctly from the GUI perspective and supplied
two new games plus eight screenshots. These games were played to test chess0live;
they are not reused comparisons or assets from an earlier engine project.
The intended snapshot is **0.1-dev-4b8b35d**, preserved as described in
[manual testing](../MANUAL_TESTING.md). No runtime code was changed by this review.

## Scope and provenance

The PGNs confirm the date, engine names, 180+2 time control, moves, annotated
search scores/depths, rounded thinking times, and results. They do not record
binary or network hashes, actual options, GUI version, host hardware, or raw UCI
commands. The recommended one-thread/64 MiB/no-ponder settings therefore remain
the intended settings, not independently verified match metadata.

The original supplied PGNs are preserved byte for byte:

| File | SHA-256 |
| --- | --- |
| [game1](2026-10-14-cutechess-game1.pgn) | `5892cfe828516da9a1c9ce08ff44ac8b671ea63c5c11eeea23f7dbf913397869` |
| [game2](2026-10-14-cutechess-game2.pgn) | `d1c91f8fbdba556db8449d1a92a68c085e34861613d4a5dfa7ea15854ceb4400` |

The local reproduction used the frozen executable with SHA-256
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`
and the [pinned network](../NNUE.md). Its hash still matches the original bundle.
Screenshot observations supplement the PGNs; they are not exact clock logs.

## Verified results

| Game | chess0live color | Result | Verified termination |
| --- | --- | --- | --- |
| 1 | White | Draw | Threefold repetition after 13...Qb6 |
| 2 | Black | Loss | Checkmate on 72.Qe7# |

Independent replay with `chess==1.11.2` accepted all **169 plies**, and all
resulting positions were valid. The repeated position in game 1 occurs after
9...Nf5, 11...Qb6, and 13...Qb6. Game 2 ends in actual checkmate, not a clock
forfeit. The owner reports no GUI integration problems in these games. This
does not establish every UCI lifecycle behavior or an engine strength rating.

The frozen engine's complete legal move set matched the independent referee at
all **171 positions**, counting each game's initial board and every subsequent
board, including repeats. Existing native/scalar NNUE adapters and the separate
pinned SF19 oracle agreed exactly on feature indices, accumulators, layer
outputs, and raw/wrapped scores at every position. The raw adapter also checked
incremental evaluation against full refresh as it advanced through the corpus.
Source fingerprints from the existing oracle report matched the current tree.

| Verification artifact | SHA-256 |
| --- | --- |
| Ordered FEN corpus | `b27d200fa2c658964f2ee7231210e521fd075bf1d5d506575501afbe29769405` |
| Integer-stage output, identical across three backends | `fe43acf68d8c5f14bd637e2f4afa38dffa80eb463276594316231d13201a4f43` |
| Raw/wrapped output, identical across three backends | `4f703d8b3c980a0b8186d2745bc1217cba1dff714a11bac9b74d2302a8223522` |

These are finite-corpus checks, not a proof of all possible engine behavior.
The different score magnitudes in the screenshots do not show an NNUE format
failure; the engines search differently and their displayed scales may differ.

## Findings for development

**Time allocation deserves the next controlled experiment.** In game 2,
chess0live spends 27 seconds on 5...c6, 24 seconds on 6...h6, and 19 seconds on
9...Qxe7. Its first 32 moves use about 243.5 seconds, against Gargantua's 183.8.
Reconstruction from the rounded comments gives roughly half a second remaining
after 32...Qd7. The screenshots corroborate severe time pressure, but exact
remaining milliseconds cannot be recovered from rounded annotations.

The long thinks are consistent with the current policy: a nominal soft target
is checked after each completed iteration, while an expensive next iteration
can run to a hard allowance of four times the nominal target. Approximate
budgets for 5...c6 and 6...h6 are 6.73/26.93 seconds and 5.93/23.70 seconds
(soft/hard). This suggests inefficient clock allocation, not a demonstrated
failure to stop at the hard deadline. Test iteration-cost prediction and reserve
policies separately; do not choose constants solely to fit these two games.

**Search efficiency remains a major research task.** Non-mate reported depth
medians are 7 versus 24 in game 1 and 8 versus 21 in game 2 (chess0live versus
Gargantua). Depth definitions, pruning, and extensions differ across engines;
these are descriptive values, not equivalent lookahead or an Elo estimate.
The baseline deliberately lacks selective pruning. Evaluate selective search
and move ordering with controlled matches against a frozen chess0live baseline.

**Mate reporting is correct in the reproduced final position.** After 71.Nf5,
the FEN is `4k3/7K/3Q4/5N2/8/8/8/8 b - - 9 71`. Replaying the complete game
history and searching with bounded synthetic clocks gives raw UCI `mate -1`,
PV `e8f7 d6e7`. Cute Chess displays the two-ply sequence as `-M2`; its pinned
[UCI parser](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/lib/src/uciengine.cpp#L408)
converts mate moves to plies, and its
[display code](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/lib/src/moveevaluation.cpp#L126)
prints that internal distance. This source explains the screenshot; the exact
installed GUI version was not supplied.

The final iteration reports depth 126 but selective depth 2: repeated
mate-distance cutoffs make later iterations almost immediate. The reproduction
finishes with 412 total nodes and a reported time of 0 ms (rounded down to whole
milliseconds). This is not a 126-ply principal variation. Similarly, Cute Chess's
ponder-hit percentage counts predicted-move matches in its
[move-handling code](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/lib/src/uciengine.cpp#L169);
the displayed percentage does not prove pondering was enabled.

## Evidence and next step

Local raw evidence is kept in ignored `results/manual-cutechess-20261014/`:
`replay.json`, `verification.json`, `positions.fen`, legal-move and NNUE outputs,
`mate-reproduction.json`, and `time-allocation-review.json`. The saved
`verify_games.py` reproduces the legality/NNUE comparison using existing pinned
oracle binaries and checks their recorded source fingerprints. These generated
files are local evidence, not distributed with a fresh clone; the PGNs and
concise findings above are versioned. Checks used one worker sequentially under
the 50% daytime resource policy. No long match campaign was started.

Retain this as successful initial GUI feedback and a source of diagnostic
positions. No engine defect requiring an immediate fix was reproduced. Next,
instrument iteration time and wasted work on interrupted depths, then test one
search/time-management hypothesis at a time with a predeclared broader opening
sample. These two games are exploratory and are not held-out strength data.
There is no need for the owner to run a larger tournament to unblock development.
