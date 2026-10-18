# Phase 3K: console diagnostics and operational completion

October 18, 2026. Implementation started from `ddee513`; tested console changes
and the predeclared [operational plan](../PHASE_3K.md) were committed as
`192d64d` before the match. **The bounded operational gate passed.** This allows
preparing fresh qualification; it does not establish a strength gain or general
clock reliability. Defaults remain classic timing, LMR off, and MVV-LVA.

## Console behavior

The owner's screenshots supplied desired behavior, not source code or test assets.
The implementation is independent:

- `d`, `show`, and `display` show the ASCII board, FEN, position hash, side,
  castling, en passant, counters, and check state. White pieces use uppercase.
- `flip` rotates the view, preserving position, history, key, evaluation, and search.
- `eval` shows the board and static NNUE score in pawns, positive for the side
  to move. In-check values are explicitly diagnostic, not a searched score or
  mate proof. The original raw component/score record remains last.
- `help` documents the implemented commands. New diagnostics use UCI
  `info string` lines and appear only on request; the board's FEN record stays last.
- `go perft N` lists sorted legal root counts and a depth/nodes/milliseconds/NPS
  summary. It needs no network, runs on an owned worker with a copied position,
  and supports `stop`, position replacement, and `quit`. Cancelled output says
  `stopped` and counts only completed root subtrees. Malformed arguments cannot
  fall through into search. Existing synchronous `perft` and `divide` stay intact.

The README introduction and both stable GUI test bundles remain unchanged.
Use the normal build for these features; no new Cute Chess session is claimed.

## Correctness evidence

Native Apple Clang 21.0.0 / macOS ARM64 C++26 mode:

```sh
make -j2 test
make SIMD=scalar -j2 test
make MODE=sanitize -j2 test
python3 results/phase3k-20261018/verify_console.py
```

All suites passed, including expanded UCI tests and Address/UndefinedBehavior
Sanitizers. The independent `chess==1.11.2` check used seed `2026101813`:
29 initial/special/mirrored fixtures and 64 reachable positions. Both display
orientations and full state matched, as did all **1,945 legal roots / 51,736
depth-2 nodes across 93 positions**. **36 searches** compared the previous binary,
new binary, and new binary after display/perft commands, with both LMR settings.
Every completed iteration's depth, selective depth, nodes, score, PV, final
bestmove, and raw evaluation matched. The corpus includes repetition history,
an in-check root, and a queen ending.

A separate console example confirmed `go perft 5` from startpos totals
**4,865,609 nodes**, with 20 root rows and no network-dependent counting.
This checks the requested interface; its timing is not performance qualification.
No engine search policy, move generation, NNUE arithmetic, or clock policy changed.
No new upstream NNUE oracle comparison or foreign-target execution is claimed.

## Fresh four-game operational screen

The frozen plan used two simultaneous shards, one color-reversed opening pair
per shard (`development-01` and `development-02`). Both roles used identical
native bytes and network; only LMR differed. Settings were **1+0.05**, Threads 1,
Hash 64 MiB, overhead 20 ms, classic timing, MVV-LVA, no pondering or diagnostics,
1,024 searched plies/game, and a 180-second global deadline. No injected storage
delay, replacement, extension, or score-based stopping was used.

| Shard/game | Termination | Result | Searched plies |
| --- | --- | --- | ---: |
| 1 / 1 | Threefold repetition | Draw | 77 |
| 1 / 2 | Threefold repetition | Draw | 63 |
| 2 / 1 | Insufficient material | Draw | 139 |
| 2 / 2 | Threefold repetition | Draw | 107 |

All four completed in **17.135 seconds**. The first independent audit passed:

- 386 on-time search replies; minimum recorded clock slack **19.225 ms**.
- 418 legal game plies including openings, 1,517 PV lines / 4,723 PV plies,
  and 385 legal suggested ponder moves (pondering remained disabled).
- Matching PGN/journal clocks, terminations, UCI options, source/asset hashes,
  and summaries; no clock, protocol, persistence, stderr, or truncation failure.
- Four ordinary 50% daytime admissions, two active search workers/four resident
  engines; aggregate reservation 2,381,485,296 bytes (about 2.218 GiB).
- 269 overlapping cross-shard search interval pairs; all eight engine PIDs
  across the four games were absent after cleanup.

The independent auditor also accepted one synthetic complete-game fixture and
rejected six deliberate corruptions: clock duration, illegal journal move,
configured LMR, transmitted LMR, illegal PV, and forged resource budget. Synthetic
options were rewritten only in temporary copied fixtures, not in old evidence.

Phase 3J's 128-ply capped game remains unchanged and incomplete. The present
four-game test is a separate operational attempt, not a continuation or strength
sample. It does not validate an entire night, four-worker reliability, arbitrary
host suspension, or the cause of all historical flags. Phase 3G remains recorded
as an operational regression; LMR remains off.

## Artifacts and next step

Ignored local raw evidence lives under `results/phase3k-20261018/`: three suite
logs, `console-verification.json`, `console-example.txt`, the frozen launcher and
independent auditor, their self-check record, and `canary/` with original PGNs,
protocols, journals, manifests and four resource admissions. The prior binary
is preserved alongside the new binary in `build/experiments/phase3k-20261018/`.

- Previous native executable SHA-256:
  `fa329663e4c9f8e07ecb495f1d7f069ffb4d6fdd4f320365eaf7fd25d5ca9637`.
- New native executable SHA-256:
  `5063b483406d5b8061db330b070962e1665c196870c9a7968a18752432f3894f`.
- Pinned network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Frozen independent auditor SHA-256:
  `b2455fe0de092505ef06a49336626d7b8790ac77806e9774b4f83fe3965ad9a1`.
- Independent audit JSON SHA-256:
  `5b80271740eb601ab95cecc45227b9fc9c1a7f2f2baf4955d76836194b892468`.

[Phase 3L preparation](../PHASE_3L.md) now defines the next checkpoint: genuinely
fresh held-out inputs, current source/asset pins, updated launcher/auditor
readiness, and an unchanged fixed 512-game LMR decision rule. Preparation is
not yet implemented and no long campaign or schedule is active. Version 0.1
acceptance and any public rating remain open.
