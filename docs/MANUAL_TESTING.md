# Test chess0live in Cute Chess

Manual testing and engine development can proceed together. Your GUI feedback
helps find integration problems; automated correctness and controlled match
tests assess code changes and playing strength. Testing is not an approval gate
for continuing development.

## Manual puzzle positions

Rebuild with `make`, then launch `build/macos-arm64-generic-release/chess0live`
from the project directory. The old stable GUI bundles below are preserved and
do not gain new input features from a rebuild. Use the current release build for
annotated puzzles and record its Git revision/hash when reporting results.

```text
uci
setoption name Threads value 1
setoption name Hash value 64
setoption name EvalFile value nn-1a298aa575a0.nnue
setoption name Move Overhead value 20
isready
```

Wait for `readyok`, then for each independent puzzle:

```text
setoption name Clear Hash
position fen q3rk2/4r3/1p1p1n1b/5Q2/3P3p/P3R2P/1B3P1N/1K2R3 w - - 2 36 bm Qxf6+ M7
go movetime 60000
```

Wait for `bestmove` before entering another position. Current defaults use
classic time policy, LMR on, MVV-LVA capture ordering, and pondering off.
For historical LMR-off comparisons, explicitly send
`setoption name Late Move Reductions value false` and record that setting.
Cute Chess may retain a saved `false` value after you rebuild: select `true` in
its engine settings to use the current default policy. The stable GUI snapshots
below retain their original binaries and settings.
`movetime` requests a 60-second budget; the configured overhead is reserved.
Send `stop` to end a search early. `d`, `show`, or `display` displays the loaded
ASCII board and normalized FEN, plus hash, side, castling, en passant, counters,
and check state. `flip` rotates the view only; it does not change the position.
`eval` shows that board and a static NNUE score positive for the side to move,
not a search result. In-check values are labeled diagnostic only. `help` lists
supported commands.

Use `go perft N` for legal root-move counts and total/time/speed statistics. Wait
for `perft complete ...`, or send `stop` to get an explicitly partial
`stopped` summary. It needs no network and supports depths 0–16; start small.
For example, `position startpos` followed by `go perft 5` totals 4,865,609 nodes.
The older `perft N` / `divide N` commands remain synchronous. These console
features require the current normal build; the two stable GUI copies are unchanged.
Console diagnostics use plain text without `info string` prefixes. Ordinary UCI
search and error messages retain their protocol format.

`bm` begins ignored metadata through the end of the line. The supplied SAN
answer and `M7` do not influence search, validate the answer, set `go mate`, or
restrict legal moves. This extension also accepts four FEN fields immediately
followed by `bm`, using counters `0 1`; it cannot recover the original rule-50
counter. Ordinary six-field FEN and coordinate `moves` histories still work.
Do not combine a `bm` annotation with `moves`; remove the annotation first.
This is not a full EPD parser and malformed boards remain errors.

UCI returns coordinate moves: `f5f6` means Qxf6+ in this example. A matching
`bestmove` and a proved `info ... score mate 7` are different observations; log
both if benchmarking mate problems. A centipawn score or a different mate
distance does not prove the spreadsheet's mate claim. Keep full analysis output,
time limit, options, machine, and binary identity with results. Clear Hash avoids
giving later repetitions a warmed table; repeated timings can still vary.

Positive `score mate X` favors the side to move; negative `score mate -X` means
that side is getting mated. The distance is in moves, not plies. Ordinary
`score cp X` remains the output when the search has not found mate. A 60-second
search is a budget, not a guarantee of finding the supplied mate distance.

## Stable local test copy

The October 13, 2026 baseline is `0.1-dev-4b8b35d`, at:

```text
build/test-baselines/0.1-dev-4b8b35d/
```

This ignored local folder contains an independent copy of the macOS ARM64
executable, pinned network, license, and build manifest. It is separate from the
ordinary rebuild output; `make` and the normal `make clean` do not replace it.
Keep the complete folder while reporting test results. Future developers should
preserve it so a reported problem can be reproduced against the same binary.
The development version still identifies itself as `chess0live 0.1-dev` over
UCI; the folder and GUI name distinguish this specific snapshot.

Snapshots are local and are not downloaded with a fresh Git clone. On another
checkout, follow [the build instructions](../README.md#build-and-run), then copy
its executable and verified network into a separately named test folder before
making further changes. Record the revision and file hashes with that copy.

The executable SHA-256 is
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
Its network SHA-256 is recorded in [NNUE](NNUE.md) and the bundle manifest.

## Optional Phase 3F test copy

The retained October 17, 2026 implementation (`500b022`) has a separate local
bundle, **`0.1-dev-phase3f-20261017`**, at:

```text
build/test-baselines/0.1-dev-phase3f-20261017/
```

It contains the macOS ARM64 executable, copied pinned network, license, and
manifest. The executable SHA-256 is
`edcfa5d37603983d0effeb8eac023f216bc2cd6d055f0608f0df70b5c017523b`.
The original `0.1-dev-4b8b35d` bundle is preserved; register this one as a separate
Cute Chess engine named **chess0live 0.1-dev Phase 3F** so feedback identifies the
tested executable. Both still report the development version over UCI.

This bundle passed a command-line handshake and depth-5 search from an unrelated
temporary working directory with its default adjacent network. All reported PVs,
bestmove, and ponder replayed legally. The record is
`results/phase3f-20261017/gui-bundle-smoke.json`. The owner's October 18 feedback
reports two draws against Gargantua with no engine errors or disconnections.
This was the intended bundle; the partial PGN and screenshots do not independently
record executable identity or actual options. See the
[review and evidence limits](reports/2026-10-18-cutechess.md).

Phase 3F improves measured local search throughput while preserving exact
evaluation and search results in the fixed comparisons; it establishes no
Elo gain. See the [Phase 3F report](reports/2026-10-17-phase3f-dense.md).

## Cute Chess setup

1. Open Cute Chess's **Settings/Preferences**, select **Engines**, and add an
   engine with the **+** button. Depending on platform/version, Settings is in
   the Tools menu or the macOS application menu.
2. Choose the snapshot above and use its distinct engine name: **chess0live
   0.1-dev 4b8b35d** or **chess0live 0.1-dev Phase 3F**. Select the **uci** protocol
   and use **Browse** beside Command to choose `chess0live` in that snapshot's
   folder.
3. Set **Working Directory** to that same folder. Browse normally fills this
   automatically and handles spaces in the path; no launch arguments are needed.
4. In the engine options, use **Threads = 1**, **Hash = 64 MB**,
   **Ponder = false**, and **Move Overhead = 20 ms** initially. Leave `EvalFile`
   at `nn-1a298aa575a0.nnue`; the copied network is beside the executable.
   For the Phase 3F bundle, keep **Time Policy = classic**, **Late Move
   Reductions = false**, **Capture Ordering = mvv-lva**, and **Search
   Diagnostics = false** at their defaults.
5. Save the configuration and select this named engine for a normal standard
   chess game. A few 3+2 games are a useful first manual check.

For any further optional Phase 3F check, play two **3+2** games against Gargantua,
reversing colors. Give both engines Threads 1, Hash 64 MB, and Ponder false.
Save the PGNs and label feedback **`0.1-dev-phase3f-20261017`**. This is an
integration check, not a strength estimate. The recorded Phase 3G comparison is
complete; future campaigns follow the current [roadmap](ROADMAP.md) and must wait
until GUI games and other heavy work have stopped. The GUI copy keeps LMR off. The October 18 feedback is sufficient
for this initial integration check; no additional manual tournament is required.

The original `0.1-dev-4b8b35d` bundle passed a UCI handshake, evaluation, and legal
search when launched from an unrelated directory, proving it finds its adjacent
network. Cute Chess
GUI behavior received its first owner confirmation in two games on October 14;
see the [replayed games and findings](reports/2026-10-14-cutechess.md). This is
initial integration feedback, not exhaustive GUI validation. Setup fields and
executable browsing behavior were checked against the official
[Cute Chess dialog source](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/gui/src/engineconfigurationdlg.cpp)
and [UI definition](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/gui/ui/engineconfigdlg.ui).

## Owner observations — October 17, 2026

The owner reports that chess0live beats chess0x and plays approximately level
with sic, which they consider slightly weaker than Gargantua. They observed
reported depths above 20 for sic versus roughly 5–6 for chess0live. These are
exploratory owner observations, not a controlled score, rating, or equivalence
claim. Game counts, PGNs, exact engine revisions, hardware, clocks, and options
were not supplied with this update.

The feedback did not identify whether the original preserved GUI bundle
`0.1-dev-4b8b35d` or a newer development executable was tested.
Do not silently attach these observations to a specific binary. Reported depth
alone is not a common work/strength scale across different selective searches;
the current chess0live default still has LMR disabled. No opponent source or
testing asset is reused as a result of this feedback.

## Owner observations — October 18, 2026

The owner supplied two-game tournament results, seven screenshots, and one
partial 180+2 PGN against Gargantua 2.1: two reported draws, no errors or
disconnections, shallow nominal depth and early clock depletion. The intended
snapshot is `0.1-dev-phase3f-20261017`; actual options and binary identity are not
captured. The [review](reports/2026-10-18-cutechess.md) verifies all 121 saved
plies and the snapshot's depth-2 divide at all 122 positions. The PGN stops at
61.Nc3 with an unfinished result. The owner clarified that they manually
adjudicated game 1 drawn, expecting a draw and wanting to save the PGN before
the GUI advanced. The original file is unchanged; no played-out ending is claimed.
Game 2's missing PGN prevents an independent ending check. No strength or default
change follows.

## Useful feedback

- Does the engine register and start a game without manual workarounds?
- Does it respond reliably when you stop or restart a game/search, change sides,
  or start another game in the same GUI session?
- Are there crashes, hangs, illegal moves, unexplained clock losses, or settings
  that fail to take effect?
- If a move looks unusually poor, save the game and identify the move. One game
  does not measure Elo, but it can expose a search or rule-handling bug.

For a report, include the snapshot name, Cute Chess version, machine/OS, time
control, engine settings, PGN or starting FEN plus moves, and the exact steps to
reproduce it. Include any GUI engine error text or protocol log if available.
Do not spend time running a large tournament just to unblock development.

Both snapshots are playable and single-threaded, with no established rating.
Neither represents a release or a competitive-strength milestone.

## Optional parallel-search test bundle

Configure Threads, Hash and SyzygyPath in Cute Chess's **engine options**.
Do not give them conflicting values in startup commands: Cute Chess sends
initialization strings before applying its saved options, so a saved Threads=1
can override `setoption name Threads value 4`. The same applies to Hash and an
empty SyzygyPath. See the upstream
[configuration order](https://github.com/cutechess/cutechess/blob/master/projects/lib/src/chessengine.cpp#L89-L103).
The owner's October 18 configuration had exactly this conflict (startup 4/128/
table directory versus saved 1/64/empty). The configured executable was the
current `build/macos-arm64-generic-release/chess0live`, SHA-256
`bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f`;
the preserved GUI snapshots below were not involved. The completed GUI game's
actual UCI transcript was not available, so its runtime worker count is not
independently confirmed. No GUI settings were changed during this investigation.

For a direct console check on the current build, set the intended options, then:

```text
setoption name Search Diagnostics value true
isready
```

After `readyok`, send `position startpos` and `go movetime 1000`. On completion,
look for `info string smp v1 threads 4 ... worker_nodes ...`: four counters give
the leader's and three helpers' completed work; their sum equals final nodes.
Restore `Search Diagnostics=false` for ordinary games. Extra OS/input threads
are separate from the four search workers. Completed depth/PV belongs to the
leader, while nodes/NPS include all workers; four workers do not mean four
times the reported depth. Coordinate additional searches with controlled matches
already running on the same computer.

Phase 4B has a separate `0.1-dev-phase4b-20261018` bundle at
`build/test-baselines/0.1-dev-phase4b-20261018/chess0live`, with its pinned network
beside the executable and a manifest. Existing `0.1-dev-4b8b35d` and
`0.1-dev-phase3f-20261017` bundles remain unchanged; they do not support parallel
search. Ordinary `make` also builds the new implementation in the normal release
directory, independently of all three snapshots.

For a small Cute Chess integration check, use Threads=4, Hash=64, Move Overhead=20,
Ponder=false, Search Diagnostics=false, classic Time Policy, LMR=false, and
MVV-LVA Capture Ordering. Use the bundled EvalFile. Give the opponent the same
thread/hash allowance and time control (for example, 3 minutes + 2 seconds),
with no book and one game at a time. If it cannot use four workers, use an
equal-supported configuration rather than call the comparison equal-resource.

Record the snapshot name, both engines' options, full PGNs, and any protocol or
clock problems. Check that nodes/NPS reflect aggregate work and hash occupancy
appears. Depth remains the leader's nominal completed depth; more workers do
not guarantee a particular depth increase or a win. Two games are integration
feedback, not a strength qualification. No fresh GUI visual check is implied
by the automated UCI checks.
