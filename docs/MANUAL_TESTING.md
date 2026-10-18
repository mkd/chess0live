# Test chess0live in Cute Chess

Manual testing and engine development can proceed together. Your GUI feedback
helps find integration problems; automated correctness and controlled match
tests assess code changes and playing strength. Testing is not an approval gate
for continuing development.

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
`results/phase3f-20261017/gui-bundle-smoke.json`. **Cute Chess GUI testing of this
new bundle has not yet been reported.** A few optional 3+2 games can check its
integration; they are not required to continue development.

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

For the owner's current Phase 3F check, play two **3+2** games against Gargantua,
reversing colors. Give both engines Threads 1, Hash 64 MB, and Ponder false.
Save the PGNs and label feedback **`0.1-dev-phase3f-20261017`**. This is an
integration check, not a strength estimate. Phase 3G tool preparation can proceed
alongside these games; its controlled overnight match must wait until GUI games
and other heavy work have stopped. The GUI copy keeps LMR off.

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
