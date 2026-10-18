# Phase 3J: match persistence and annotated puzzle input

October 18, 2026; parent `65a5313`. Puzzle-input implementation committed as
`984f432`. The [predeclared plan](../PHASE_3J.md) separates two changes: manual
input compatibility and match-runner persistence. Neither changes search,
evaluation, clock allocation, LMR defaults, or historical match outcomes.

## Manual puzzle input

The owner supplied their workbook specifically for this compatibility work.
It was read without modification; its previous engine results were not reused.
All 39 position strings were inspected. Four omit both FEN counters; these now
receive `0 1` only when the fourth field is immediately followed by `bm`.
Six-field FEN and ordinary UCI `moves` retain their existing meaning.

The exact supplied command previously failed with `expected moves`. It now
loads, with a nonempty trailing `bm` annotation ignored through end of line.
Invalid boards, invalid counters, unknown suffixes, empty annotations, and mixed
annotation/move histories remain transactional errors. This is a narrow input
extension, not a full EPD parser. The counter default cannot recover omitted
rule-50 history, and answer metadata is not validated or used as a search hint.

Native, scalar, and sanitizer `make -j2 test` passed. The independent
`chess==1.11.2` check matched all 1,627 legal root moves and 58,282 depth-2 leaves
across the 39 supplied boards. All 117 searches matched in three-way groups:
old plain FEN, new plain FEN, and new annotated FEN, with fresh hash tables at
depth 2. UCI regressions also prove that deliberately wrong answer notes preserve
search signatures. These finite checks do not prove the supplied mate distances.

The owner's exact `go movetime 60000` example returned `bestmove f5f6` (Qxf6+)
in 59.983 seconds, with 20 ms overhead and default search options. Its last
completed iteration was depth 8, score cp 1206, 7,976,992 cumulative nodes.
The expected move was found, but mate in seven was **not proved**. No strength
or rating conclusion follows from solving the first move of one exposed puzzle.

## Persistence implementation and deterministic checks

Protocol callbacks timestamp and serialize records, then enqueue them into one
FIFO writer thread per game. Pending serialized payload is capped at 8 MiB and
4,096 records including in-flight writes; one flush barrier and one close control
are permitted. This is not a total Python RSS or parser-buffer cap. Drain/flush
barriers occur before that game's next search, without blocking sibling callbacks.

PGN formatting, game journals, summaries, manifests, resource observations, and
filesystem metadata checks also leave the shared event loop. Dependent mutations
stay serialized, including during cancellation. Errors or overflow invalidate
evidence and stop further games; they do not become an engine defeat. A journal
open interrupted by cancellation retains ownership until the stream is closed.

All **230 checks in 11 invocations** passed:

```sh
make test-match test-qualification test-phase3g test-clock-probes
```

This includes 15 new match tests and three supervisor tests. They cover blocked
storage across distinct receive callbacks, FIFO timestamps, byte/record limits,
open/write/flush failures, failure during search, cancellation, journal ownership,
resource observation counts, and incomplete publication. Existing referee,
qualification, audit, and clock-probe behavior also passed.

Ordinary offloaded finalization waits for I/O ownership to return. Protocol-log
barriers instead have a 30-second deadline: a timed-out daemon may finish later,
so failed directories must never be resumed or reused. Flush is not `fsync`.
Unavailable storage may prevent even a failure marker; the runner still fails
and must not be treated as a completed experiment. Python serialization/GIL work
and arbitrary OS suspension remain outside the disk-isolation guarantee.

## Operational canary

The single predeclared check ran 20:31–20:35 Helsinki, within the normal 50%
daytime resource policy: two concurrent shards, four resident engines, Threads=1,
Hash=64 MiB, default search options, 20 ms overhead, 1+0.05 clocks, the first
original development opening with colors reversed in each shard. Both roles
used the identical new binary. Each protocol write slept 100 ms in its worker.
No sources or assets changed during the attempt. The launcher separately checked
aggregate two-worker/four-engine limits and doubled memory reservation; each
child manifest retains its own one-worker/two-engine resource record.

| Shard / game | Recorded termination | Engine-played plies |
| --- | --- | ---: |
| 1 / 1 | Checkmate | 120 |
| 1 / 2 | Threefold repetition | 54 |
| 2 / 1 | Truncated at the declared ply limit | 128 |
| 2 / 2 | Checkmate | 96 |

Elapsed time was **220.986 seconds**, under the 600-second deadline. All 398
searches were on time; the smallest observed clock slack was 18.857 ms. No
protocol, queue, storage, or clock failure occurred. The independent audit
passed on its first attempt: all charged timestamps match transcripts, all
430 plies including openings replay legally, as do 2,516 PV lines / 7,174 PV
plies and 396 ponder moves. PGNs, journal clocks, summaries, options, and hashes
agree. There were 3,878 measured write delays, each 100.026–105.331 ms, matching
the saved protocol records one for one. All 398 bestmoves arrived during a
write delay in their own shard; 396 also arrived during the other shard's write
delay, with 30 overlapping cross-shard search intervals.

**The full operational gate did not pass:** one game hit the predeclared
128-ply cap. Its result remains `*`, not a draw, and no replacement or extended
game was run. This is an incomplete operational screen, despite valid evidence
and successful disk-isolation observations. The tested implementation is retained;
Phase 3K should predeclare a completion-capable operational check before preparing
fresh held-out LMR strength qualification. No score/rating inference, old result
reclassification, default change, new strength match, or schedule follows.

## Reproduction and evidence

Local raw evidence is `results/phase3j-20261018/`: the pre-change rejection,
workbook source digest and per-position checks, 60-second transcript, native /
scalar / sanitizer logs, workflow suite log, canary launcher, frozen source pins,
writer-delay intervals, PGNs, clocks, and independent audit. The workbook itself
is not published or made a held-out strength suite.

Native executable SHA-256:
`fa329663e4c9f8e07ecb495f1d7f069ffb4d6fdd4f320365eaf7fd25d5ca9637`.
Workbook compatibility record SHA-256:
`bd28fb56e549f2402a0d7bbef5916ed95d41ac1598682591f2623f6c896f2228`.
60-second transcript SHA-256:
`3925fa645ec97e1e5d8171ff0951148c68becb5c2a500846e1453db0a32dc068`.
Workflow test log SHA-256:
`cb39d3cf85e581f29ca6e8844143c0be6b55b46e045b489c3a145c2f6f6f9217`.
Canary independent audit SHA-256:
`25a103f8c50d10804b651bea0f59525e574eaf614b631f5631e16c824044e4f0`.
Frozen canary launcher record SHA-256:
`ff384f7cdbb8cb258016f29705b1ae80724f0dd2c62e166a1b4b00e613bf2c9a`.

The retained local scripts are `check_puzzles.py`, `run_canary.py`, and
`audit_canary_independent.py` under the raw directory. The first uses the saved
read-only workbook extraction. The launcher refuses an existing canary output;
it must not be rerun to replace this attempt. Ordinary reusable regressions are
the native/scalar/sanitizer suites and the four Make targets above.

Both stable GUI bundles and the owner's README introduction are preserved.
The full SF19 oracle corpus was not rerun: evaluator and search sources are
unchanged. Native/scalar NNUE tests were included in the ordinary suites.
