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
