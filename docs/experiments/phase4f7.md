# Phase 4F.7 — move-hint tactical qualification

Protocol: `phase4f7-tt-hints-puzzles-v1`. Declared October 25, 2026, before
any search in this phase. This tests the isolated Phase 4F.6 candidate against
current defaults. No engine code, thresholds, playing default or network changes.
The older combined-policy campaign remains parked and its results are separate.

## Frozen comparison

Both roles use a byte-for-byte copy of the tested native macOS ARM64 generic
release from source `a1b2331273f5baf4fcc2c53ee96a3759337e2399`, preserved at
`build/experiments/phase4f7/chess0live`. Its SHA-256 is
`6dd685119d80145e2c6956c8d27c20a2d67e006bdf6556ceef5b779585baff9f`.
The local `manifest.json` records the source/build provenance. No normal or
stable GUI binary is rebuilt. The network is `networks/nn-1a298aa575a0.nnue`,
SHA-256 `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.

| Setting | `hints-off` | `hints-on` |
| --- | --- | --- |
| TT Move Hints | false | true |
| Threads / Hash | 8 / 64 MiB | 8 / 64 MiB |
| Late Move Reductions | true | true |
| Capture Ordering | mvv-lva | mvv-lva |
| Time Policy / Move Overhead | classic / 20 ms | classic / 20 ms |

Both explicitly disable Deep Quiet Reductions, Countermove Ordering, Null Move
Pruning, Reverse Futility Pruning, QSearch SEE Pruning and ProbCut. Ponder and
Search Diagnostics are false. Both set SyzygyPath to `<empty>`, ProbeLimit to
zero and ProbeDepth to one, and use the same absolute EvalFile path. The hints
setting is the only role difference. Advertised option types/ranges/defaults
and the exact setup responses must pass validation. No diagnostics are added
to timed searches; the previous phase's activation and race checks remain
separate evidence.

Use all 39 owner-supplied positions in their original order from the existing
immutable `tests/data/phase4f3-puzzles.json`. Verify its provenance against the
literal FENS and mate comments in `tools/batch_positions.py`, without executing
or editing that owner file. Reusing this exposed diagnostic suite does not make
it held-out evidence. Supplied answers are not sent as search restrictions.

Freeze the runner, independent auditor, tests, transitive local dependencies,
this protocol, corpus, source provenance, executable and network identities in
`tests/data/phase4f7-pins.json` before real readiness/smoke checks. Require the
same prepared identities for a later full run. The manifest excludes its own
digest to avoid recursion; each run pins it separately before/after. Preserve
any failed or partial attempt and its input bytes; a corrective tool change
requires a recorded new preparation, never retroactive replacement of evidence.

## Three bounded steps

1. **Check:** start one fresh process for each role; handshake, configure,
   verify readiness, quit and verify clean teardown. Do not search a position.
2. **Smoke:** search every position for 1,000 ms per role, 78 searches in total.
   This checks operations and legality, not tactical success or playing strength.
3. **Full:** search every position for 60,000 ms per role, 78 searches in total,
   approximately 78 minutes plus startup. Do not pool the smoke with this sample.

Start a fresh process for every role/position, with a new game and complete FEN.
Only one engine is resident/searching at a time. Run hints-off first on odd
numbered positions and hints-on first on even numbered positions. Do not select
favorable positions, stop based on results, tune thresholds, replace failed
cases, resume incomplete runs or quietly enlarge the sample. Output directories
must be new. Print progress and both outcomes for each position.

Record full raw commands and output, UTC/monotonic receipts, process ID,
pre/post readiness barriers, EOF, reader completion, zero exit status, raw-log
digests, options, file identities and all search iterations. Validate every
principal variation and final best/ponder move with pinned `chess==1.11.2`.
Unexpected output, bounds in exact result lines, nonzero tablebase hits, missing
results or malformed records fail the run. Only the known Syzygy-disabled
setup message is accepted alongside its readiness response. Drain trailing
output after quit; completion is recorded only after successful teardown.

An independent auditor reconstructs the complete matrix, recipes, commands,
search results, legal lines, clock evidence, resource coverage, lifecycle and
prepared identities from the saved raw logs. It does not trust the runner's
summary or reuse its result validator. Retain all adverse observations.

## Resources and comparability

Reserve eight active search workers, one resident engine and at least 2 GiB.
Recheck the existing aggregate resource policy before launch and throughout
the run: 50% daytime, 80% at 23:00–07:00 Europe/Helsinki, with owner overrides.
Configured workers and memory reservations are planning estimates, not measured
OS utilization caps. Do not overlap with other engine searches or builds.

Check and smoke are short correctness runs and need no quiet-host assumption.
For the full comparison, obtain a fresh owner-confirmed quiet window: pause
LM Studio inference and other heavy work, keep AC power and the existing
Automatic profile unchanged. The model may stay loaded. `--quiet-host` records
an operator attestation; it is not continuous thermal/power/GPU telemetry.
No general High Power claim or change is part of this comparison.

Full runs require the overnight window or a fresh explicit daytime exception.
`--allow-daytime` records a requested exception, not proof of human approval;
earlier exceptions do not apply. Request that approval only after the concrete
protocol, tool tests, readiness, smoke and local preparation commit are ready.
No automatic schedule is created. A foreground `caffeinate -i` wrapper on macOS
may prevent idle sleep but does not replace monitoring.

Use a 600-second total check/smoke cap and a 7,200-second full cap, plus the next
Helsinki 07:00 cutoff for full runs. Require at least 84.5 minutes remaining
before that cutoff, including setup allowance. Derive the cutoff using civil
Helsinki time and compare UTC instants across DST. Poll during active work;
a wall/monotonic gap or accumulated discrepancy over five seconds invalidates
completion. A five-second search watchdog grace is separate from the fixed
250-ms bestmove receipt tolerance and never adds usable chess-clock time.
Early completion is allowed. Stop and join every child on failure/cancellation;
retain partial output. Main-loop receipts include queue/I/O delay.

## Interpretation and exit decision

Report all 39 final best moves, scores, mate reports, nominal depths and any
differences. Count reported positive mates, agreement with supplied distance,
and legal final PVs ending in checkmate separately. A larger centipawn score is
not a distance-to-mate measure. Neither an annotation nor one legal mating PV
proves forced mate against every defense. Eight-thread SMP is nondeterministic;
single differences are diagnostic leads, not automatic strength verdicts.

Any operational, identity, legality, clock or resource failure makes the attempt
incomplete/unqualified. Investigate adverse tactical observations before a
strength campaign. A separate diagnostic repeat must be identified as post-hoc,
cannot replace original cases and cannot be pooled into the original sample.
A reproducible serious tactical concern blocks default consideration until
resolved. Do not tune against these 39 positions.

If no such concern blocks progression, prepare a **new** paired-opening blitz
campaign with frozen candidate/control identities, fresh provenance/exclusions,
matched hardware/settings and a predeclared statistical decision before its
first game. This protocol does not launch or authorize that match. Puzzle
completion alone never promotes the option or proves Elo; TT Move Hints remains
off until a separate strength/default review. Broader platform, training and
release gates remain open.
