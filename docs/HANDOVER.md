# Developer and agent handover

## Accepted direction

Read [requirements](REQUIREMENTS.md) first. The user completed the interview:
original engine, strength over elegance, GPL-3.0-or-later, pinned SF19 network,
no own initial network training, desktop/laptop focus, M5 Pro primary, local-only
compute, and tested commits directly to main. The owner now handles GitHub pushes
manually; do not retry authentication or publishing from an agent session.

No unresolved product decision blocks the baseline. Nighttime is 23:00–07:00
Europe/Helsinki at 80%; daytime 50%; the owner can override the budget. Blitz is
the first match-testing focus. Do not reuse any of the owner's earlier engines.

## Development sequence

1. Establish legal bitboard moves and reversible state; pass perft and edge cases.
2. Independently implement the pinned SF19 file format, all feature families,
   scalar integer inference, and incremental state. Prove oracle parity.
3. Integrate bounded search and asynchronous UCI; pass lifecycle and rule tests.
4. Record benchmarks and build/platform evidence. Release 0.1 only when all its
   claimed capabilities have evidence; never claim the long-term strength goal.
5. Optimize ARM64, extend portable builds, measure search improvements, and add
   parallelism with correctness and match evidence. Training integration follows.

## Current checkpoint

The first three steps are implemented as an unreleased `0.1-dev` baseline.
Normal and sanitizer suites passed natively on macOS ARM64. SF19 integer parity
has a separate reproducible oracle harness. ARM64 NEON is implemented; the
reference remains selectable with `SIMD=scalar`. Three other platform binaries
cross-build, with execution still outstanding. RISC-V64 and Windows ARM64 lack
configured local toolchains. Search deliberately remains single-worker.

An original paired-opening runner now records clocks, game files, binary/network
hashes, and pair-level statistics. Small development and validation suites are
separate. Read [the match guide](MATCHES.md) before running it. The optional
external move checker agrees on 93 positions at depth 2, including special moves.
The included 12-opening suites are too small for the runner's uncertainty gate;
no strength rating or improvement is established by their smoke tests.

The owner is testing with Cute Chess while development continues. Snapshot
`0.1-dev-4b8b35d` is preserved under ignored `build/test-baselines/`, including
its own network and manifest. Read [manual testing](MANUAL_TESTING.md) and do not
replace that copy during ordinary rebuilds. GUI feedback does not block work.

Next work should expand the predeclared opening sample and measure search
improvements against the frozen comparison binary. Investigate incremental feature-list
maintenance, faster sliding attacks, selective search, and worker parallelism as
separate hypotheses; no Elo gain follows automatically from adding them. Preserve
the exact NNUE stage oracle and core rule tests while optimizing. Trainer
integration, multi-platform runtime execution, and any public strength claim
remain open. Avoid marking the overall world-leading-strength objective complete.

The unmodified SF19 match opponent is in ignored `build/stockfish19-reference`;
the instrumented NNUE oracle is separate. Never substitute one for the other.
Local GitHub authentication failed during initial setup; the owner's subsequent
instruction is to keep developing and committing locally while they push.

README contains the current runnable commands and limitations. CHANGELOG tracks
versions. [Architecture](ARCHITECTURE.md) describes boundaries, [validation](VALIDATION.md)
defines evidence, [portability](PORTABILITY.md) separates intended targets from
verified targets, and [NNUE](NNUE.md) owns the network pin and parity record.

## Before committing

Run the relevant correctness checks and inspect the diff. Keep generated binaries,
large networks, external oracle source, and raw match output out of Git. Record
what actually ran and what did not. Update these documents when APIs, commands,
test evidence, or limitations change. Make a small local commit on main and leave
GitHub pushes to the owner. Do not amend unrelated commits or rewrite history.
