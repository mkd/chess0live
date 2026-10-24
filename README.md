# chess0live 🫒

An independently written, GPL-3.0-or-later UCI chess engine in C++26.

Author: **Claudio M. Camacho <claudiomkd@gmail.com>**.

## Build and run

Install a recent C++ compiler with C++26 mode, GNU Make, and Python 3.10 or newer
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

For automatic compiler selection and supported local toolchain downloads:

```sh
make portable                              # This computer's target
make portable TARGET=windows-arm64         # Cross-build
make toolchain-plan TARGET=linux-riscv64    # Check available routes without setup
```

These builds go into `build/portable/<target>-generic-release/`, keeping ordinary
GUI builds separate. Windows cross-compilers can be downloaded and verified
automatically; Linux cross-compilers and Apple's SDK have explicit prerequisites.
Use `OFFLINE=1` to reuse cached toolchains without downloads. On Windows, the
same workflow starts with `py -3 tools/build.py --target windows-arm64`.
See [automatic target setup](docs/PORTABILITY.md#automatic-target-setup) for all
six targets, compiler overrides, cache/recovery and current verification limits.

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
help
d
flip
eval
go perft 5
```

`d`, `show`, and `display` print an ASCII board, FEN, position key, side to move,
castling rights, en-passant square, move counters, and check status. `flip` rotates
the view and displays it; the position and search stay unchanged. `eval` displays
the board and static NNUE score in pawns, positive for the side to move, followed
by the raw component/internal-score record. It labels in-check static values as
diagnostic only; static evaluation is not a searched score or a mate proof.

`go perft 5` lists each legal root move's count and reports depth, total nodes,
elapsed milliseconds, and nodes per second. The initial position totals
4,865,609 nodes. Wait for `perft complete ...` before the next command,
or send `stop` to cancel; an interrupted count is explicitly marked `stopped`
and includes only completed root subtrees. Move counting needs no network.
Legacy synchronous `perft N` and `divide N` remain available. Diagnostic depths
are 0–16; high depths can take a very long time. Console diagnostics print plain
text, without `info string` prefixes. Normal search output retains UCI formatting.
Enter `quit` to exit. These commands do not add variants or
an interactive SAN mode. Board, evaluation, and help commands stop any active
search before printing.

For manual puzzle testing, paste a FEN with an optional `bm` answer annotation:

```text
position fen q3rk2/4r3/1p1p1n1b/5Q2/3P3p/P3R2P/1B3P1N/1K2R3 w - - 2 36 bm Qxf6+ M7
go movetime 60000
```

The engine ignores the annotation and searches independently for up to 60 seconds
(less the configured move overhead). Four-field puzzle records immediately
followed by `bm` are also accepted, with missing move counters set to `0 1`.
The board must still be valid. Remove the annotation when using a UCI `moves`
history. See [manual puzzle testing](docs/MANUAL_TESTING.md#manual-puzzle-positions)
for repeatable settings and how to read the result.

During a search, `info ... score cp 120 ...` reports an ordinary evaluation in
centipawns; `info ... score mate 7 ...` reports a found mate in seven moves.
A negative mate distance means the side to move is getting mated. The engine
reports centipawns until it finds a mating line within its search; a time limit
does not guarantee solving the puzzle. `eval` is static and does not search for
mate, and a trailing `bm ... M7` annotation never supplies the answer to search.

### Batch puzzle positions

`tools/batch_positions.py` contains an editable `FENS` list with the 39 supplied
puzzles in spreadsheet order. Set `ENGINE`, `THREADS`, `HASH_MB`, and `MOVETIME_MS`
at the top, then run it. An engine path argument overrides `ENGINE`:

```sh
python3 tools/batch_positions.py "/path/to/engine"
```

The script preserves your editable settings and automatically prepares its pinned
Python dependency on first use. No environment activation or manual package
installation is needed. Stay within the [local resource budget](#local-resource-policy). Each FEN gets a fresh engine
running from its binary directory. The script prints the last exact main-line
score and best move, for example `01/39  M7  bestmove=f5f6`. `-M7` means the side
to move is being mated; ordinary scores are signed pawn values such as `+1.25`.
Errors and missing scores are explicit. To save the printed results, append
`> results.txt` to the command. Edit or slice `FENS` for a shorter run.
No spreadsheet file is needed at runtime. Check the script with
`python3 tools/run.py tests/batch_positions_test.py`.
For development comparisons, follow the [puzzle progress checks](docs/VALIDATION.md#use-for-development-progress)
to keep settings consistent and record both new solves and regressions.

### Automatic Python tool setup

Run tools/tests that need Python packages through the shared launcher:

```sh
python3 tools/run.py tools/match.py --help
python3 tools/run.py tests/batch_positions_test.py
make test-match
```

The launcher and optional Make tests install pinned packages into an isolated
local environment, then reuse it. `batch_positions.py` also supports direct use
as shown above. `make tooling` optionally prepares everything in advance.
Python 3.10+ with its `venv` component is required; on Windows, use `py -3`
in place of `python3`. Ordinary engine builds and core tests need no third-party
Python packages. See [tool setup](docs/TOOLS.md) for offline use, cache location,
repair, package provenance and Windows commands.

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
`Threads` accepts **1–64**, with **1** as the default. Set it to `4` to use four
Lazy SMP search workers, for example:

```text
setoption name Threads value 4
setoption name Hash value 64
isready
position startpos
go movetime 1000
```

Wait for `readyok` before sending the position and search commands. All workers
share one hash table and network; `Hash` is not multiplied by `Threads`. Each
worker has its own board, search history, and NNUE accumulators. Search depth,
score, and PV come from the leading worker; nodes/NPS include all workers and
can include repeated work. A final `info nodes ... time ... nps ... hashfull ... tbhits ...`
line includes unfinished iterations. Additional threads do not guarantee a
particular depth or playing-strength gain. Keep the total active workers within
your local resource allowance, including other engines running concurrently.

A missing or
incompatible network produces an explicit error; the engine does not substitute
an undisclosed evaluator. `isready` prepares a changed network before a timed
search. When distributing the executable, put the default network beside it or
set `EvalFile` to its absolute path.

Search reports include standard UCI `hashfull`, so GUIs can display retained hash
occupancy. Values are in permille: `hashfull 949` means about 94.9%. The engine
samples up to 1,000 nonempty entries, including earlier searches. Starting a new
move does not reset this percentage. Clearing/resizing the table, starting a new
game, or changing incompatible search policies can reset it. This is neither a
cache hit rate nor a RAM usage percentage. `Hash` sets a memory ceiling; bucket sizing can allocate less.
The compact table preserves its established entry capacity: `Hash=64` currently
uses 32 MiB of entry storage. Network/evaluator and other engine memory are extra.

Optional Syzygy tables can be downloaded separately and configured with:

```text
setoption name SyzygyPath value /absolute/path/to/syzygy
isready
```

Wait for `readyok`. Supply both `.rtbw` and `.rtbz` files for root endgame ranking;
incomplete coverage falls back to search. `SyzygyProbeLimit` (0–7, default 7)
caps piece count; 0 disables probing. `SyzygyProbeDepth` (1–128, default 1)
controls interior probes. `SyzygyPath=<empty>` disables the reader. Table files
are excluded from Git and are never downloaded by a normal build. UCI `tbhits`
reports successful probes. DTZ is not mate distance; `score mate` still requires
an actual mating line. See [tablebase setup and testing](docs/SYZYGY.md).

For repeatable parallel measurements, run
`make test-smp test-profile-smp`. The bounded profiler accepts `--threads 1,2,4`,
`--mode movetime|depth|both`, and a new output filename:

```sh
python3 tools/run.py tools/profile_smp.py --engine build/macos-arm64-generic-release/chess0live \
  --network networks/nn-1a298aa575a0.nnue --output results/smp-check.json \
  --threads 1,2,4 --mode both --movetime-ms 1000 --depth 6
```

It saves raw output, artifact hashes, legal-PV checks, throughput, and completed
depth/latency comparisons. These are performance measurements, not an Elo test.
Use `make MODE=thread-sanitize test-search test-smp` for a separate race-detection
build on a toolchain/platform with ThreadSanitizer support.

Timed requests include preparation after the engine receives `go`, including
worker startup. Send `isready` and wait for `readyok` before starting a timed
search so network loading is complete. `Move Overhead` reserves milliseconds
for response delivery; pondering starts consuming its clock at `ponderhit`.

The development executable also offers `Time Policy` (`classic`, the default,
or experimental `forecast` / `bounded`) and optional `Search Diagnostics` (default off).
Forecast estimates whether another search iteration will fit the hard deadline;
it is not yet a demonstrated strength improvement. See
[the time-management experiment](docs/TIME_MANAGEMENT.md) before enabling it.

For a tighter ordinary clock budget, try `setoption name Time Policy value bounded`.
It caps each move at twice the nominal soft allocation instead of four times
(with the existing five-millisecond floor and remaining-clock cap). It keeps the
same soft target and can abandon an expensive iteration earlier. Explicit
`movetime`, depth, nodes, mate, infinite and ponder requests keep existing budgets;
`go movetime 60000` is unaffected. This policy is optional and has not been
qualified for playing strength. Test its protocol with
`make test-bounded-time test-bounded-time-uci`.

`Late Move Reductions` defaults to `true`: guarded one-ply reductions with
ordinary-depth verification of promising probes. Use
`setoption name Late Move Reductions value false` to disable it for controlled
comparisons. Saved GUI settings can override the new default; select `true` in
the engine settings when using a rebuilt executable. See
[selective search](docs/SELECTIVE_SEARCH.md) for safeguards and validation.

`Deep Quiet Reductions` defaults to `false`. With ordinary LMR enabled, it
experimentally reduces selected late quiet piece moves by two plies and verifies
promising probes at ordinary depth. Enable it explicitly with
`setoption name Deep Quiet Reductions value true`; changing it clears incompatible
search state. It is not yet strength-qualified. `Search Diagnostics=true` adds a
`deep-lmr v1` record with extra reductions and verification outcomes. Use
`make test-deep-quiet-search` for state and tactical checks.

`Capture Ordering` defaults to `mvv-lva`; experimental `see` estimates material
exchanges and searches apparently losing captures later. All captures remain
available to search. It is evaluated independently with LMR off and classic
timing; see [the ordering experiment](docs/MOVE_ORDERING.md).

`Null Move Pruning` (default `false`) enables an experimental, guarded pass
probe followed by a search of legal moves before accepting a cutoff. Enable it
with `setoption name Null Move Pruning value true`. It excludes checks,
principal-variation nodes, sparse material, advanced pawns, repeated positions,
and positions near the fifty-move limit. These safeguards do not prove strength
preservation; leave it off for ordinary baseline comparisons. Changing the
policy clears cached search state. With `Search Diagnostics=true`, a final
`nullmove v1` record reports probes, fail-highs, verifications, accepted cutoffs,
and rejected verifications, summed across workers. Check state and protocol
behavior with `make test-null-state test-null-search test-null-move`
with automatic dependency setup. `make test-profile-null-move` checks
the bounded development profiler without starting engine searches.

`Reverse Futility Pruning` (default `false`) is an experimental shallow static
cutoff, enabled with `setoption name Reverse Futility Pruning value true`.
It excludes checks, principal-variation nodes, legal captures/promotions,
sparse endings and draw-sensitive positions. Its fixed margins do not prove
playing-strength preservation; leave it off for baseline comparisons. Changing
the option clears reusable search state. With `Search Diagnostics=true`, a final
`reversefutility v1` record reports eligible evaluations and cutoffs across all
workers. Run
`make test-reverse-futility-search test-reverse-futility` for correctness checks,
or `make test-profile-reverse-futility` for engine-free profiler checks.

`QSearch SEE Pruning` (default `false`) is an experimental quiescence capture
filter. Enable it with `setoption name QSearch SEE Pruning value true`.
It skips selected captures with negative static exchange estimates, excluding
checks, promotions, en passant, small endings and draw-sensitive positions.
These estimates cannot prove that a sacrifice is unsound; leave the option off
for baseline comparisons. Changing it clears reusable search state. With
`Search Diagnostics=true`, the final `qsearchsee v1` record reports exchange
evaluations and skipped captures across joined workers. Use `make test-qsearch-see-search test-qsearch-see`
for correctness checks, or `make test-profile-qsearch-see` for engine-free
profiler checks.

`ProbCut` defaults to `false`. Enable the experimental tactical probe policy
with `setoption name ProbCut value true`. It searches a few promising captures
at reduced depth against a raised cutoff threshold, including quiet defensive
replies before accepting a cutoff. It can miss deeper tactics and has not been
qualified for playing strength; leave it off for baseline comparisons. Changing
it clears reusable search state. `Search Diagnostics=true` adds a `probcut v1`
record with probe attempts, cutoffs and rejected reduced searches, summed across
joined workers. Use `make test-probcut-search test-probcut-uci` for correctness
checks and `make test-profile-probcut` for engine-free profiler checks.

`Countermove Ordering` (default `false`) is a separate experimental ordering
option. It remembers successful quiet replies to the preceding move and tries
them before ordinary quiet-history moves, without reducing depth or pruning.
Enable it with `setoption name Countermove Ordering value true`. Changing the
policy clears learned search state. Leave it off for baseline comparisons;
its mixed development results do not establish a performance or strength gain.
With `Search Diagnostics=true`,
the final `countermove v1` record reports lookups, legal matches, and updates
summed across workers. Check it with `make test-countermove test-profile-countermove`
with automatic dependency setup. The bounded, independently replayed
profiler records cold and warm searches separately:

```sh
python3 tools/run.py tools/profile_countermove.py --engine build/macos-arm64-generic-release/chess0live \
  --network networks/nn-1a298aa575a0.nnue --output results/countermove-check.json
```

See the [comparison protocol](docs/experiments/phase4d-countermove.md) for fixed
settings, resource limits, and interpretation. Use a new output filename each run.

For manual Cute Chess testing while development continues, use the preserved
snapshot and settings in [the GUI testing guide](docs/MANUAL_TESTING.md).
The [first owner-run games](docs/reports/2026-10-14-cutechess.md) passed legal
replay and additional NNUE parity checks; they identify clock allocation and
search efficiency as priorities without establishing an Elo rating. The
[October 18 follow-up](docs/reports/2026-10-18-cutechess.md) reports two draws
without GUI errors and again shows early clock depletion. Its saved PGN is
incomplete; the legal portion passed replay and depth-2 move checks. These
manual games do not establish strength or change the default search options.

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

For paired-opening matches, follow
[the match guide](docs/MATCHES.md). It records full games, clocks, failures,
binary/network hashes, and uncertainty at the opening-pair level. Separate
development and validation opening fixtures are included. `make test-match`
checks the runner; `make verify-moves` independently compares legal moves and
perft against the same optional referee library. These tools do not add a
Python dependency to the engine itself.
The qualification workflows add pinned preflight, a wall-clock cutoff, and an
independent evidence audit; `make test-qualification` checks them. Use
`make test-phase4d2` for the current opening-generation, readiness, supervision,
and audit checks. These checks use synthetic games; they do not launch a match.
Recorded campaigns are completed evidence: do not resume or rerun their exposed
openings as fresh validation. Prepare a new protocol before another campaign;
the [match guide](docs/MATCHES.md) explains resource and evidence requirements.
Preparing the tools creates no scheduled job.

`make test-lmr-qualification` checks the fresh fixed LMR comparison's opening
generator, supervisor and independent auditor using synthetic evidence.
The [qualification guide](docs/experiments/lmr-20261022.md) documents the
separate search-free readiness command, frozen inputs and launch restrictions,
including the explicit dated exception flag. Test targets do not launch the
strength match.

`make test-match-readiness` checks the bounded four-worker match supervisor
and independent raw-game auditor without launching engines. Its fixed
[readiness protocol](docs/experiments/match-readiness-20261020.md) documents
the separate live check, required frozen inputs, resource budget and commands.

`make test-clock-probes` checks saved-position and response-timing diagnostics.

For developer timing investigations, `make CLOCK_TRACE=1` creates a separate
build whose directory ends in `-clock-trace`. It adds a versioned timing record
after each `bestmove` and a `clockping N` calibration command. Ordinary builds
omit this instrumentation. Use
`make CLOCK_TRACE=1 test-clock-trace` for live protocol checks and
`make test-clock-boundaries` for engine-free diagnostic checks. The
[saved-case workflow](docs/experiments/clock-boundary-20261020.md) additionally
requires the locally archived case and campaign evidence.
The [receipt diagnostic guide](docs/MATCHES.md#response-timing-diagnostics)
explains how to distinguish consumer delay from observed engine response time.
Its process-pause control requires POSIX signals; it does not change engine play.

For changes intended to preserve search behavior, use the
[performance comparison guide](docs/BENCHMARKING.md). Its alternating baseline
and candidate runs verify identical search work before reporting timing ratios.
The [experiment log](docs/EXPERIMENTS.md) records decisions, including candidates
that were not retained.
`make test-profile` checks the bounded clock-policy profiler; `make test` also
includes deterministic time-policy and iteration-accounting tests.
For cache diagnostics, run:

```sh
make test-profile-cache
python3 tools/run.py tools/profile_cache.py --engine build/macos-arm64-generic-release/chess0live --depth 5 --hash-mb 64 --output results/cache-new.json
```

Choose a new output filename. The profiler runs three development positions with
cold and warm state, saves raw output, and independently checks legal moves,
hash occupancy, cache counters, and allocation size. Use `--suite gamephases`
for the existing composed middlegame/endgame fixtures. Warm runs retain ordering
state as well as the table, so their difference is not attributable to caching
alone. The tool enables `Search Diagnostics`; normal GUI play can leave it off.

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
It also documents the verified RISC-V cross-toolchain/QEMU route and the pinned
macOS LLVM-MinGW package for Windows ARM64. Automatic dependency/toolchain
setup and custom-network training remain planned work.

### Verify a target runtime

```sh
make runtime-binaries    # Build engine and correctness executables only
make verify-runtime      # Run them on this native host; make net first
make test-runtime-tools  # Check the verifier without running chess searches
```

`runtime-binaries` also accepts the cross-compilation settings above. On the
actual target, run `tools/verify_runtime.py` against that build directory and the
pinned network; no compiler is needed for execution. It checks board rules,
NNUE arithmetic and incremental state, search, time policies, and a two-thread
UCI session. Each run writes a new JSON report and individual logs. A failed,
skipped, or timed-out check prevents a passing report.

Use the explicit VM/emulator/Windows compatibility-layer options and prerequisites in
[Portability](docs/PORTABILITY.md#run-the-portable-checks). These correctness
checks do not measure playing strength or certify every platform capability.

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
between games. The engine defaults to one search worker; the UCI `Threads`
option controls parallel search. The helper does not resize arbitrary running
programs or change an explicitly supplied `make -j` value. Long matches/training belong overnight;
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
