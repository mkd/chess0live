# Validation and experiment protocol

## Baseline verification — October 13, 2026

Native host: macOS 26.7.1 ARM64, Apple Clang 21.0.0, C++26 mode. The full
`make -j2 test` and `make -j2 MODE=sanitize test` suites passed, including
AddressSanitizer and UndefinedBehaviorSanitizer. These checks exercised legal
move generation/perft, FEN and state restoration, real-network evaluation,
incremental refresh/backtracking, hostile-file rejection, search limits and
draw/mate rules, and UCI lifecycle behavior. The ordinary UCI suite also tests
launching by bare executable name through PATH from a different directory.

The pinned network SHA-256 was verified locally. Exact upstream NNUE comparison
is documented with corpus/output digests and reproduction commands in
[NNUE](NNUE.md). This is finite-corpus compatibility evidence, not a formal proof
for every possible position or network. A local benchmark completed with saved
binary/network/position hashes; it provides no Elo or match-strength evidence.

Three foreign targets cross-compiled; they were not executed. See
[portability](PORTABILITY.md) for compiler/runtime details and remaining gaps.
No tournament results, measured Elo rating, parallel search validation, or
training outcome is claimed for this baseline.

## Independent referee checks — October 13, 2026

`make verify-moves` compares every legal root move and each perft branch with
the pinned `chess==1.11.2` reference. The release binary passed all 93 depth-2
cases: 64 deterministic reachable random positions and 29 initial/special/mirrored
fixtures. A depth-3 check also passed all 37 cases (8 random plus the fixtures).
A deliberately incorrect mock engine produced failure records and a nonzero
exit status. These are correctness checks, not strength measurements.

The default seed is `18938320320349523`; the ordered FEN corpus SHA-256 is
`d2d60c101811d895dc3dc309f0f4079258aedab9937abf15a25b46a56cbd28d4`.
The checked binary SHA-256 is
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
The ignored `results/move-verification.json` contains the full inputs, branch
comparison summaries, tool hash, and environment metadata.

## Match-runner verification — October 13, 2026

`make test-match` passed 17 paired-statistics tests and 13 subprocess/referee
integration tests. Coverage includes swapped colors, full opening history,
PGN replay, illegal/null opening rejection, protocol errors and timeouts,
readiness excluded from the chess clock, real clock losses without a credited
increment, resource overrides, artifact changes, and inference exclusions.

A real two-game smoke run against the separately built pinned Stockfish 19
completed with no protocol failures, truncations, or clock losses. Both games
ended in checkmate; chess0live lost both. Settings were 1 second plus 0.01 seconds
per move, one thread, 64 MiB hash, 20 ms move overhead, seed `20261013`, one pair
from the development suite (`development-02`), and a 256-ply safety limit.
Both PGNs replayed legally to the recorded final positions. This deliberately
short run validates the workflow; it is not a blitz rating or evidence for a
strength margin. No confidence interval is produced.

Evidence is in ignored `results/match-smoke-sf19-20261013/`: the manifest, frozen
opening suite, game records, PGNs, raw protocol logs, and summary. The manifest
records source labels, runner/binary/network hashes, platform and actual options.
See [match testing](MATCHES.md) for the separate opponent build and its PGO flags.

## Owner-run GUI feedback — October 14, 2026

Two newly supplied 180+2 Cute Chess games against Gargantua 2.1 completed with a
draw as White and a checkmate loss as Black. The owner reports working UCI GUI
integration. Independent replay verified all 169 plies and both terminations;
the frozen snapshot's legal move sets and native/scalar/pinned-SF19 NNUE stages
and raw/wrapped outputs agreed at all 171 recorded boards, including initial
positions and repeats. The frozen snapshot's binary hash remains unchanged.

The [feedback report](reports/2026-10-14-cutechess.md) preserves PGNs, digests,
reproduction findings, metadata limits, and next hypotheses. Time allocation
deserves further testing; no immediate engine correctness defect was reproduced.
These two exploratory games establish neither a rating nor a strength gain.

## Phase 2 time-policy checkpoint — October 14, 2026

The opt-in hard-deadline forecast candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
These include the real-network 537-position incremental/full-refresh check,
perft/rule/state tests, deterministic forecast boundaries, interrupted-iteration
accounting, explicit-limit/ponder exclusions, and UCI option/lifecycle checks.
The evaluator and position implementations are unchanged; the full separate
Stockfish parity corpus was not rerun for this time-control-only change.

Tool checks passed: 15 profiler tests, 17 paired-statistics tests, 17 match-runner
tests, and 11 equal-work comparison tests. New match checks verify per-engine
options, advertised types, protected common settings, and frozen configuration.
The profiler checks raw diagnostics, exact node totals, partial failures,
artifact stability, resource changes, and timing-accounting consistency.

Default classic search retained exactly the frozen `0.1-dev-4b8b35d` signatures
at all 24 fixed-depth comparisons, including warmups (three roots, depth 5,
three measured repetitions per binary). Timing variation does not establish a
throughput improvement. The optional forecast changes clock allocation, so
clock-managed profiles are assessed for completed depth and moves as well as
time and interrupted work; they do not require identical final results.

The [experiment record](TIME_MANAGEMENT.md) separates the rejected soft-target
candidate from its hard-deadline revision and preserves both evidence sets.
The two four-game operational smokes completed without errors or time forfeits.
Independent replay verified 577 legal plies for the first and 467 for the revision;
each produced two checkmates and two threefold draws. The revision scored
2W/2D/0L, versus the first candidate's 1W/2D/1L, on the same two development pairs.
Correctness and short operational matches are not a strength acceptance gate.
Classic remains the default; the longer held-out blitz test has not run.

## Phase 2C selective-search checkpoint — October 14, 2026

The conservative LMR candidate passed native `make -j2 test`,
`make -j2 SIMD=scalar test`, and `make -j2 MODE=sanitize test` on macOS ARM64.
The policy tests cover eligibility boundaries, checks, mate windows, special
moves, advanced pawn pushes, and ordering hints. A bounded real-network search
exercises both confirmed and rejected reduced probes, an interrupted iteration,
legal PVs, and restoration of baseline results after switching policies. Existing
rule, limit, cancellation, and ponder cases also run with LMR enabled.

The new profiler passed 12 tests, including different search trees, PV/bestmove/
ponder legality, counter accounting, exact node caps, partial search/readiness
failures, and artifact mutation. The existing 15 clock-profiler, 17 statistics,
17 match-runner, and 11 comparison tests passed. NNUE and position code are
unchanged; their normal 537-position incremental checks passed in all three
build modes. The separate full Stockfish oracle corpus was not rerun for LMR.

The [selective-search experiment](SELECTIVE_SEARCH.md) records the frozen
candidate, default-equivalence check, development profiles, and short game test.
These are finite correctness and operational checks. Reduced fail-lows remain
heuristic; this checkpoint does not establish playing strength or make LMR the
default.

Default-off search matched all 24 frozen-parent samples exactly. The depth-5
profile completed 48 searches and the 200,000-node profile completed 24, with
legal PVs and consistent accounting. The eight-game paired operational smoke
scored 2W/2D/4L for LMR, with six checkmates and two threefold draws, no failures,
time forfeits, or truncations. Its unfavorable score is documented without
turning four development pairs into a strength estimate.
The Linux ARM64, Linux x86-64, and Windows x86-64 binaries also rebuilt and linked
successfully; file inspection confirmed target architectures. They remain
cross-build-only. No RISC-V64 or Windows ARM64 build/runtime evidence was added.

## Release gates

1. **Position correctness:** standard perft vectors and divide diagnostics;
   castling transit attacks, pins, en passant exposing a king, all promotions,
   mate/stalemate, legal-move membership, and complete make/unmake restoration.
2. **Position and input integrity:** FEN rejection without partial state changes,
   deterministic hashes, relevant en-passant repetition keys, reversible clocks,
   promotion/capture handling, and sanitizer-clean tests where available.
3. **NNUE interoperability:** verified network digest and bounded file parser;
   exact active feature indices, integer accumulators, PSQT, and raw outputs
   against the pinned independent test oracle. Incremental evaluation must equal
   refresh across legal sequences and reversals, including every special move.
   Every enabled optimized kernel must equal scalar output.
4. **UCI lifecycle:** handshake, readiness during search, legal best moves, stop
   responsiveness, repeated go/stop, new games, position replacement, hash/network
   changes only after search joins, pondering/infinite result timing, EOF/quit.
5. **Search:** mate distance and score bounds, check evasions at quiescence,
   repetition and rule-50 precedence, terminal positions, node/depth/time limits,
   and deterministic bounded searches. No neural-network-free fallback disguised
   as NNUE strength.
6. **Platforms:** record the exact compiler, standard library, flags, target,
   network digest, and native/VM/emulated/build-only validation for each target.
7. **Performance and strength:** report repeatable benchmarks and local matches.
   A functional 0.1 need not beat Stockfish; no Elo claim without match evidence.

## Strength measurement

Freeze the two binary hashes, code commits, network digests, clock settings,
thread count, hash size, affinity policy if used, and opening suite digest before
a match. Match resources between engines. Disable ponder and books unless the
experiment explicitly gives both the same access. Play each opening with colors
reversed. Do not tune against the held-out validation set.

Save full PGNs, errors, forfeits, time losses, and machine metadata. Use a
predeclared sample size or a justified sequential test; do not repeatedly peek
at a conventional confidence interval and stop as soon as it turns favorable.
Paired openings produce dependent games: estimate uncertainty at the pair level,
not by pretending each game is independent. Report W/D/L and score with an Elo
difference and uncertainty only when the statistical assumptions are satisfied.

Initial focus is blitz. Exact time controls, opening-suite selection, and sample
sizes are experiment configuration, not invented product achievements. A
statistically positive difference does not automatically mean 'decisively
stronger'; report the measured margin and uncertainty. Absolute 4000 Elo requires
a named calibrated rating pool. NPS, search depth, and solved tactics alone do not
establish playing strength.

## Experiment records

Record hypothesis, parent commit, changed parameter/code, exact command, resource
policy, input hashes, raw results, interpretation, and keep/revert decision.
Keep large generated results, networks, and external reference builds outside
the source tree or ignored. Retain concise result summaries with reproducible
commands when publishing a claim. Test-only Stockfish code must never become an
undeclared dependency of the shipped engine.
