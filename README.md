# chess0live 🫒

An independently written, GPL-3.0-or-later UCI chess engine in C++26.

**Status: 0.1 development baseline.** The long-term objective is decisively
stronger play than Stockfish 19 on equal desktop hardware. No Elo rating or
competitive superiority has been established. The current search is an early
single-worker implementation; strength testing and further optimization remain.

**Search qualification: Phase 2D's initial time-policy and LMR screens are complete.**
Both passed their independent evidence audits and were inconclusive under their
predeclared rules. The [128-game LMR screen](docs/reports/2026-10-16-phase2d-lmr.md)
scored **35W/82D/11L, 76/128 points (59.38%)**, with no operational failures.
Its conditional 95% paired-score interval is **42.40–76.35%**; the favorable
point estimate does not qualify LMR for promotion. Classic timing, LMR off,
and MVV-LVA remain defaults. The frozen GUI test bundle is unchanged.

**Phase 3B is complete:** [batched NNUE accumulator updates](docs/reports/2026-10-16-phase3b-nnue-batching.md)
improved throughput by **7.8–8.4% in the three declared opening-search runs** on
the M5 Pro. All 576 benchmark searches preserved exact results; native, scalar,
sanitizer, and full 2,057-position SF19 oracle checks passed. The optimization is
retained; search-policy defaults remain unchanged. This is a sampled speed gain,
not a measured playing-strength gain or a new release.
**Phase 3C is complete:** [broader validation](docs/reports/2026-10-16-phase3c-gamephases.md)
confirmed **8.7–8.8% higher throughput on six composed middlegames**, with all
432 searches across both game phases matching exactly. Endgame qualification
remains inconclusive: one sparse pawn position was below the fixed timing floor.
**Phase 3D is complete:** the [baseline-only depth ladder](docs/reports/2026-10-17-phase3d-workload.md)
proposes depth 12 for that pawn ending, taking about 323–330 ms. All 40 searches
matched exactly and replayed legally; this phase changed no engine code or defaults.
**Next: Phase 3E — separately frozen endgame requalification**, preserving all
six roots and using the longer workload for the short pawn position.
Follow the [development plan](docs/ROADMAP.md). No job or schedule is active.

Author: **Claudio M. Camacho <claudiomkd@gmail.com>**.

## Build and run

Install a recent C++ compiler with C++26 mode, GNU Make, and Python 3.9 or newer
(tooling only). The engine has no Python runtime dependency. From this directory:

```sh
make doctor
make -j2
make net
make test
./build/macos-arm64-generic-release/chess0live
```

The executable path changes with the target; for example Linux x86-64 uses
`build/linux-x86_64-generic-release/chess0live`. A bare `make` uses one build job.
Choose parallel jobs within the current [resource budget](#local-resource-policy).
The network is about 98.5 MB; `make net` downloads the pinned official file and
verifies its full SHA-256. Large networks and build outputs are excluded from Git.

Configure a UCI-compatible chess GUI to launch the executable, or use stdin:

```text
uci
isready
position startpos moves e2e4 c7c5
go movetime 1000
```

Wait for `bestmove` before sending `quit`. For diagnostics:

```text
position startpos
perft 5
divide 2
eval
d
quit
```

`perft 5` from the initial position is 4,865,609 nodes. `divide` lists each root
move's count. `eval` reports raw NNUE components and calibrated internal score;
`d` prints FEN. These diagnostics do not add variants or an interactive SAN mode.

## Evaluation and search

- Versioned SF19/SFNNv16 file reader and independently implemented feature math.
- Pinned network: `nn-1a298aa575a0.nnue`; full digest and provenance in
  [the network manifest](networks/manifest.json).
- Piece-square, threat, and pawn-pair features; incremental accumulators;
  integer inference; ARM64 NEON kernels; scalar/full-refresh reference paths.
- Legal bitboard moves, castling, en passant, underpromotion, reversible state,
  and deterministic position hashing.
- Iterative deepening, PVS/alpha-beta, quiescence, aspiration windows, move
  ordering, bounded transposition storage, repetition and rule-50 handling.
- UCI cancellation, pondering, search limits, and soft/hard clock allocation.

`Hash`, `Clear Hash`, `EvalFile`, `Move Overhead`, and `Ponder` are configurable.
`Threads` currently accepts **1**. Parallel search is future work. A missing or
incompatible network produces an explicit error; the engine does not substitute
an undisclosed evaluator. `isready` prepares a changed network before a timed
search. When distributing the executable, put the default network beside it or
set `EvalFile` to its absolute path.

The development executable also offers `Time Policy` (`classic`, the default,
or experimental `forecast`) and optional `Search Diagnostics` (default off).
Forecast estimates whether another search iteration will fit the hard deadline;
it is not yet a demonstrated strength improvement. See
[the time-management experiment](docs/TIME_MANAGEMENT.md) before enabling it.

`Late Move Reductions` (default `false`) enables the separate Phase 2C search
experiment: guarded one-ply reductions with ordinary-depth verification of
promising probes. See [selective search](docs/SELECTIVE_SEARCH.md) for safeguards,
comparison settings, and results. It is not yet an accepted strength improvement.

`Capture Ordering` defaults to `mvv-lva`; experimental `see` estimates material
exchanges and searches apparently losing captures later. All captures remain
available to search. It is evaluated independently with LMR off and classic
timing; see [the ordering experiment](docs/MOVE_ORDERING.md).

For manual Cute Chess testing while development continues, use the preserved
snapshot and settings in [the GUI testing guide](docs/MANUAL_TESTING.md).
The [first owner-run games](docs/reports/2026-10-14-cutechess.md) passed legal
replay and additional NNUE parity checks; they identify clock allocation and
search efficiency as priorities without establishing an Elo rating.

See [NNUE compatibility and evidence](docs/NNUE.md). UCI centipawn display uses
SF19's normalization for its network scale; it is not a calibrated chess0live
win-probability model. Network compatibility does not establish engine strength.

## Tests and benchmarks

```sh
make test
make MODE=sanitize -j2 test
make SIMD=scalar -j2 test
make bench
python3 tools/bench.py build/macos-arm64-generic-release/chess0live --depth 5 --output results/bench.json
```

Tests cover published perft counts, chess-rule edge cases, state/hash restoration,
NNUE parser rejection and accumulator parity, search terminal states/limits, and
asynchronous UCI behavior. Benchmarks record binary/network hashes, Git state,
positions, search output, and resource policy. NPS and solved positions are not
Elo estimates. [Validation](docs/VALIDATION.md) defines the required evidence for
future match results and releases.

Pass `--positions /path/to/positions.txt` to benchmark your own positions/openings,
one `startpos moves ...` or `fen ...` entry per line. Comments start with `#`.
`python3 tools/verify_nnue.py` builds a separate pinned Stockfish test reference
and compares scalar/native features, accumulators, layers, and outputs. It
downloads upstream source into the ignored build directory; it is not part of
the shipped executable.

For paired-opening matches, install `requirements-match.txt` and follow
[the match guide](docs/MATCHES.md). It records full games, clocks, failures,
binary/network hashes, and uncertainty at the opening-pair level. Separate
development and validation opening fixtures are included. `make test-match`
checks the runner; `make verify-moves` independently compares legal moves and
perft against the same optional referee library. These tools do not add a
Python dependency to the engine itself.
The [fixed Phase 2D workflow](docs/PHASE_2D.md) adds pinned preflight, a wall-clock
cutoff, and an independent evidence audit; `make test-qualification` checks it.
The [LMR protocol](docs/PHASE_2D_LMR.md) uses the same lifecycle with independently
pinned audit expectations. `python3 tools/qualify_lmr.py check` performs readiness
checks without searching; `run --output NEW_DIRECTORY` starts the fixed sample
within the normal overnight window. The completed time-policy daytime exception
does not authorize a daytime LMR run.

For changes intended to preserve search behavior, use the
[performance comparison guide](docs/BENCHMARKING.md). Its alternating baseline
and candidate runs verify identical search work before reporting timing ratios.
The [experiment log](docs/EXPERIMENTS.md) records decisions, including candidates
that were not retained.
`make test-profile` checks the bounded clock-policy profiler; `make test` also
includes deterministic time-policy and iteration-accounting tests.
`make test-profile-lmr` checks the optional selective-search profiler, using the
same pinned referee dependency as matches. It compares LMR off/on at fixed
depth or nodes and independently replays every reported principal variation.
Use `--experiment capture-ordering` with that profiler to compare SEE against
MVV-LVA while pinning LMR off. `make test-profile-ordering` checks both profiler
modes; `make test` includes exchange estimates versus a slow legal-move reference.

## Cross-compilation

```sh
make TARGET=linux-arm64 CXX=aarch64-linux-gnu-g++
make TARGET=linux-x86_64 CXX=x86_64-linux-gnu-g++
make TARGET=linux-riscv64 CXX=riscv64-linux-gnu-g++
make TARGET=windows-x86_64 CXX=x86_64-w64-mingw32-g++
make TARGET=windows-arm64 CXX=aarch64-w64-mingw32-clang++
```

Install the relevant compiler and target libraries first. `SYSROOT=/path` is
available for toolchains requiring an explicit sysroot. `CPU=generic` is the
portable default; `CPU=native` is for the current machine only. macOS ARM64 builds
require a supported macOS host and Apple SDK. Windows builds statically link the
compiler runtimes. [Portability](docs/PORTABILITY.md) records tested versus
intended targets and host restrictions; producing a binary is not runtime testing.

## Local resource policy

Local compute only: **50% daytime**, **80% 23:00–07:00 Europe/Helsinki**. Override
the workload budget at any time, or restore the automatic time-window policy:

```sh
python3 tools/resources.py show
python3 tools/resources.py set 60
python3 tools/resources.py clear
```

The helper calculates aggregate worker and memory budgets; it is **not an OS
utilization limiter**. Benchmarks re-read it between positions and matches
between games. Current
search uses one worker. It does not resize arbitrary running programs or change
an explicitly supplied `make -j` value. Long matches/training belong overnight;
no recurring job has been scheduled. On systems without IANA timezone data,
install the Python `tzdata` package for these resource tools.

## Contributing and continuing development

Start with [requirements](docs/REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md),
[handover](docs/HANDOVER.md), [validation](docs/VALIDATION.md), and [agent guidance](AGENTS.md).
The [changelog](CHANGELOG.md) distinguishes planned releases from measured work;
[provenance](PROVENANCE.md) identifies external specifications and assets.

Development uses small tested commits directly on `main`. The owner publishes
those commits to GitHub manually; agent sessions work and commit locally.

Priorities after correctness: efficient ARM64 evaluation and move generation,
measured search improvements, desktop parallelism, broader runtime verification,
and reproducible training integration. Proposed ideas need falsifiable
hypotheses and controlled results. The owner's previous engines and testing
assets are not reused. Future books, puzzles, and variants are outside this core.

Original code is licensed under [GNU GPL version 3 or later](LICENSE), without
warranty. See the network manifest for the separate upstream network license.
