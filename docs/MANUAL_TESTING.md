# Test the stable baseline in Cute Chess

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

## Cute Chess setup

1. Open Cute Chess's **Settings/Preferences**, select **Engines**, and add an
   engine with the **+** button. Depending on platform/version, Settings is in
   the Tools menu or the macOS application menu.
2. Name it **chess0live 0.1-dev 4b8b35d**, select the **uci** protocol, and use
   **Browse** beside Command to choose `chess0live` in the stable folder above.
3. Set **Working Directory** to that same folder. Browse normally fills this
   automatically and handles spaces in the path; no launch arguments are needed.
4. In the engine options, use **Threads = 1**, **Hash = 64 MB**,
   **Ponder = false**, and **Move Overhead = 20 ms** initially. Leave `EvalFile`
   at `nn-1a298aa575a0.nnue`; the copied network is beside the executable.
5. Save the configuration and select this named engine for a normal standard
   chess game. A few 3+2 games are a useful first manual check.

The bundle passed a UCI handshake, evaluation, and legal search when launched
from an unrelated directory, proving it finds its adjacent network. Cute Chess
GUI behavior itself remains subject to your test. Setup fields and executable
browsing behavior were checked against the official
[Cute Chess dialog source](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/gui/src/engineconfigurationdlg.cpp)
and [UI definition](https://github.com/cutechess/cutechess/blob/5e84232be4546aaedc9d87a96c91867a1da06ada/projects/gui/ui/engineconfigdlg.ui).

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

This baseline is playable and single-threaded, with no established rating. It
is a test snapshot rather than a released or competitive-strength milestone.
