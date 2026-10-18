# Phase 3L: console feedback and fresh qualification readiness

October 18, 2026. **Preparation complete; no qualification games played.**
The [fixed protocol](../PHASE_3L.md) owns settings, hashes, decision gates,
launch constraints, and reproducible commands. The next development checkpoint
is Phase 4A, search-cache efficiency, followed by Lazy SMP and optional Syzygy.

## User-visible changes

Explicit `d`/`show`/`display`, `flip`, `help`, `eval`, and perft diagnostics now
print plain text, without `info string` prefixes. Standard UCI search and error
messages keep their protocol formatting. Consumers of console diagnostics must
use the new plain final records: `fen ...`, `eval psqt ...`, and
`perft complete ...` (or `perft stopped ...`).

Search already reports `score mate X` when it finds mate, with a negative
distance when the side to move is being mated. Otherwise it reports `score cp`.
Both signs and both colors now have explicit regression coverage, alongside
mate zero at a checkmated root and ordinary centipawn output. Static `eval`
does not search for mate, and puzzle answer annotations never supply a search
result. A fixed time budget does not guarantee that a puzzle will be solved.

The console change is commit `56ddbde35104a4d295b871cc570a6a268adb2b62`.
The frozen native executable is `build/experiments/phase3l-20261018/chess0live`,
SHA-256 `e7c9222c37bacecc3fa0571dd4b19c0e4fc1215dc37fadd42030f610b59b5c31`.
Its adjacent build manifest records source hashes, compiler, flags, and platform.
No engine search, evaluation, clock logic, or default changed in this phase.

## Validation

- The native `make -j2 test` suite passed, including expanded console and mate
  tests. Scalar/sanitizer suites were not rerun for this formatting change;
  the [Phase 3K report](2026-10-18-phase3k-console-operations.md) retains their
  latest execution evidence.
- Twelve bounded old/new searches over three already exposed roots, with LMR
  both off and on, matched every completed depth, selective depth, node count,
  score, PV, and best move. This checks behavior, not speed or strength.
- Four signed mate examples were independently replayed through checkmate using
  `chess==1.11.2`. Plain startpos perft depth 5 returned all 20 root rows and
  4,865,609 nodes. Output examples and exact comparison evidence are saved.
- New tooling passed 94 checks: 23 opening-generator tests, 29 launcher tests,
  and 42 independent-auditor tests. Tests cover reproduction, exclusion rules,
  invalid inputs, four-worker resource accounting, cancellation/cleanup,
  persistence failures, cutoff enforcement, score thresholds, and corrupted
  evidence. These use synthetic evidence/fake engines, not played games.
- An independent code/evidence review found no blocking issue in the prepared
  lifecycle and audit implementation. The Make target wiring was dry-run checked.

## Fresh input preparation

The generator uses 32 independently composed legal stems and eight continuations
per stem: 256 distinct roots, four 64-pair shards, and 128 roots per side to move.
Generation seed `2026101818` and domain `chess0live.phase3l.openings.v1` are fixed.
All histories were legally replayed; byte reproduction and optional original
source verification passed. No terminal, duplicate, prior-overlap, or SHA-word
rejection occurred. No engine evaluated or searched these roots during selection
or readiness.

The pinned exclusion manifest contains 851 canonical roots from 39 sources,
including earlier suites, saved profiling/clock roots, manual PGN positions,
puzzle inputs, and independent verification fixtures. Private workbook contents
are not copied into the project. The manifest records provenance and limitations:
the missing second October 18 PGN and unsaved/dynamic states cannot be fully
cataloged; internal search nodes are outside this saved-root exclusion policy.
Related stems and shared machine conditions remain dependence risks.

## Actual readiness result

At **21:16 Europe/Helsinki**, both roles loaded the pinned network and completed
serial UCI configuration/readiness. Candidate LMR was on, baseline off; all other
settings matched the fixed protocol. Transcripts contain `uci`, required
`setoption` commands, `isready`, and `quit`, with **no `position` or `go`**.
The independent audit returned `checked: true`, `errors: []`.
Closure was awaited and `quit` is recorded, but this readiness format does not
include PID/exit-code records; it is not an independent process-disappearance audit.

The resource admission checked the future aggregate requirement of four active
search workers/eight resident engines, reserving an estimated 4,762,970,592 bytes
(about 4.44 GiB). The host reported 18 logical CPUs and 64 GiB physical memory;
the daytime policy allowed nine workers. This is an estimate/admission check,
not an OS-enforced cap or proof of a long-run peak. Actual readiness loaded the
roles serially and performed no search. At that hour, long-campaign launch was
correctly disallowed; the normal launch window remains 23:00–23:15 Helsinki.

Local raw evidence, excluded from Git, is in `results/phase3l-20261018/`:
`native-tests.log`, `console-compatibility.json`, `console-example.txt`,
`preflight.json`, and `readiness-audit.json`. The preflight SHA-256 is
`0e67137b8a02f59ae04aeec4b6c83ffb446879cabb362387bb72987af5bc21e7`.
Source and asset fingerprints are recorded in that evidence; the later campaign
must capture a fresh snapshot and repeat readiness before any game.

## Decision and remaining work

The bounded preparation exit is satisfied. No 512-game match, recurring schedule,
LMR default promotion, new rating, or release is claimed. Historical Phase 3G
clock forfeits and decisions remain unchanged. A later foreground match must
follow the fixed overnight/cutoff/resource policy; historical daytime permission
does not transfer. Any positive screen requires separate fresh confirmation.

The transposition table already exists, including four-entry buckets, depth and
bound storage, replacement generations, mate normalization, and draw/history-aware
keys. Phase 4A will measure its effectiveness before choosing at most one justified
improvement. Lazy SMP and Syzygy are subsequent implementation areas, not present
features. This frozen comparison can remain separate from normal engine builds;
it need not indefinitely delay broader development.

The README introduction and both preserved GUI bundles remain unchanged. The
owner can rebuild the normal executable and optionally try the console commands;
no additional manual tournament is needed for this checkpoint. GitHub publishing
remains manual.
