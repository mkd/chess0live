# Phase 3J: isolated match persistence and manual puzzle input

Started October 18, 2026 from `65a5313`. Keep the two changes independent:
match evidence handling and a requested manual-input convenience. Search,
evaluation, clock allocation, default options, and historical results stay fixed.

## Persistence boundary

Phase 3I timestamps complete input batches before logging, but synchronous disk
writes can still delay subsequent callbacks, including other match shards on the
same event loop. Move protocol persistence to an ordered bounded writer. Include
in-flight records in the memory bound, fail the run on overflow or write errors,
and drain before advancing to the next move or finalizing evidence. Never silently
drop records or reclassify a writer failure as a chess clock loss.

Move PGN, journal, manifest, and campaign resource observations off the event
loop too. Serialize dependent writes and wait for their completion during
cancellation; do not leave a background mutation racing finalization. A blocked
storage device may delay cleanup, but must not block another shard's protocol
callback. This is not a guarantee against arbitrary process or OS suspension.

## Puzzle-input boundary

The owner explicitly supplied their benchmark workbook for manual-input
compatibility. This permits inspecting its position strings, without importing
previous engine implementations, runners, scores, or qualification assets.
The workbook remains unchanged and its positions are exposed development inputs.

Support six-field FEN followed by a nonempty `bm` annotation. Also support four
FEN fields immediately followed by `bm`, synthesizing halfmove/fullmove counters
`0 1`. Validate the resulting board with the existing strict parser. Treat all
annotation text as opaque, ignored metadata: it cannot constrain, guide, or
score the search. Reject mixed `bm` and UCI `moves` histories; users can remove
the annotation to replay ordinary coordinate moves. This is a narrow extension,
not a general EPD-operation interpreter or SAN command interface.

## Checks fixed before live use

1. Preserve the old executable's rejection of the exact owner example. Add UCI
   tests for both input forms, invalid boards/counters/suffixes, transactional
   failure, ordinary move histories, and identical unannotated/correct/wrong
   answer search signatures. Run native, scalar, and sanitizer suites.
2. Check every supplied workbook position against independent board parsing and
   depth-2 legal move counts. Check annotated versus plain fixed-depth searches.
   This establishes compatibility, not the correctness of claimed mate distances.
3. Exercise delayed writes across separate callbacks, FIFO order, bounded queue
   overflow, write/flush failures, and cancellation. Run existing match,
   qualification, campaign audit, and clock-probe regression suites.
4. After all checks, run one bounded operational canary: two concurrent match
   shards, each two games from the first original development opening, swapped
   colors, identical new release binaries and default search settings, 1+0.05,
   Threads=1, Hash=64 MiB, overhead=20 ms, at most 128 plies/game. Inject a 100 ms
   delay in each protocol log write to exercise isolation. Retain all outcomes,
   clocks, legal PGNs, protocol transcripts, and artifact hashes; do not rerun
   an unfavorable result. A ply cap is an operational limitation, not a draw.
   No score/Elo inference; no new strength campaign or schedule is authorized.

The canary has a ten-minute total deadline; cancellation still awaits outstanding
writer cleanup. Operational acceptance requires all four games complete with
legal replay and consistent clocks/transcripts, no truncations, clock forfeits,
protocol failures, queue overflow, or persistence errors. Any failed or incomplete
condition is reported as such, without replacement games or retrospective gates.

The canary uses two active search workers within the ordinary daytime budget.
One separate 60-second search of the owner's exact example exercises the stated
manual workflow. Stop at the bounded checkpoint; fresh strength qualification
requires its own declared protocol and held-out openings.
