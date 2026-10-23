# Architecture and design decisions

## Independence and boundaries

The engine implements chess and search itself. NNUE mathematical/file-format
interoperability is specified from pinned upstream sources; the Stockfish
executable is a separate test oracle. Training tools are separate from inference
and are not required to run the engine. The owner-approved standalone Fathom
reader is isolated behind `tablebase::Syzygy`; its vendor code and MIT notices
are explicit. No search or evaluation code is imported through this dependency.
See [Syzygy semantics and provenance](SYZYGY.md).

The initial dependency direction is:

`types → position → NNUE / tablebase adapter → search → UCI`

Position does not know how a neural network stores features. Search owns its
worker evaluation state and transposition table. UCI owns process interaction
and asynchronous cancellation. Networks become immutable after loading; loading
a replacement requires joining any search using the existing network.

## Position representation

Use 64-bit bitboards plus direct square lookup. Squares are a1=0 to h8=63.
Pieces carry signed type values (positive white, negative black). Incremental
make/unmake must restore every board, clock, castling, en-passant, and hash field.
Repetition keys must not distinguish an en-passant target with no legal capture.
Search history includes the game history supplied through `position ... moves`.

## Evaluation evolution

Version architectures explicitly. Keep serialization validation, feature
enumeration, accumulator updates, integer inference, and score calibration
separate. Preserve a full-refresh path as the reference for incremental state.
Architecture selection occurs outside the search hot path; avoid per-node
virtual dispatch solely for hypothetical future extensions. Future NEON, AVX2,
and other kernels must match the scalar integer reference exactly before use.

The first target is SF19/SFNNv16. Loading a network is not proof of compatible
evaluation. The detailed pin and evidence belong in [NNUE](NNUE.md).

## Search evolution

The UCI controller timestamps each complete command before parsing. A `go`
request carries that monotonic timestamp in `SearchLimits::received_at`, so
preparation and worker dispatch consume the existing clock or movetime budget.
Direct API callers may supply the same-clock receipt time; omission starts at
search entry. Future origins are clamped and extreme past elapsed durations
saturate safely. Pondering charges only from `ponderhit`; infinite mode ignores
clocks. This accounting does not guarantee scheduling or pipe-delivery latency.
Expired requests still return a legal root fallback without entering the tree.

Start with a correctness baseline: iterative deepening, alpha-beta/PVS,
quiescence with check evasions, transposition storage, draw recognition,
move ordering, cancellation, and clock budgeting. Establish deterministic
single-worker evidence before enabling shared-memory search. Add pruning,
reductions, parallelism, and speculative ideas through isolated experiments and
matched-game testing, retaining changes only on appropriate evidence.

Transposition caching is implemented in `src/search.cpp`: four entries
per bucket, stored moves/scores/depths/bounds, generation/depth replacement,
mate-distance normalization, and a history/rule-50-aware key. `Hash` controls
capacity and `Clear Hash` clears cached search state. Internal representation is
isolated in `include/chess0live/detail/transposition_entry.hpp`: 16-byte entries
retain the full key, signed score, full generation byte, and all move information.
Depth fits one byte under the root-depth/check-extension invariant. Four-entry
buckets have 64-byte size/alignment; this is not a universal cache-line claim.
The historical 96-byte budget divisor deliberately retains bucket count/indexing
and collisions at every Hash setting. At `Hash=64`, 2,097,152 entries now occupy
32 MiB instead of 48 MiB. Vector/allocator overhead and other engine memory are
outside that entry-storage figure.

Standard `hashfull` samples up to 1,000 nonempty retained entries at each report,
in permille, including older generations. Generation still ages replacement
priority; it does not filter probes or the occupancy display. This is sampled
occupancy, not physical-memory use, activity or hit rate.
Opt-in `Search Diagnostics` adds one `info string cache v1` record per search,
including geometry and probe/hit/cutoff/save-attempt/occupied-replacement counts.
Counts include interrupted work and are not updated when diagnostics are off.
The [cache profiler](../tools/profile_cache.py) checks exposed cold/warm roots;
warm behavior includes retained ordering history, while the evaluator resets.

Lazy SMP (`Threads=1..64`, default 1) uses one `SharedSearch` and private
`SearchWorker` objects. The single-worker cache path acquires no mutex. With
multiple workers, 1,024 striped mutexes protect complete entry reads/writes;
probes return value snapshots, never pointers into a concurrently modified
bucket. Hash occupancy samples take the same locks. Generation and table sizing
change only while workers are joined. A seqlock around ordinary non-atomic entry
fields would still be a C++ data race and is deliberately avoided. The existing
history/rule-50-aware key and search-policy invalidation remain unchanged.

Worker zero owns the returned move, PV, score, completed depth, and soft/forecast
time decisions. Helpers vary equally ranked root-move tie ordering, without new
pruning or reductions. Positions, repetition histories, killers, history scores,
PV arrays, and NNUE accumulators are private. Only immutable weights, the cache,
and atomic cancellation/ponder/node-accounting state are shared. Helpers run on
separate threads created per search; startup consumes the accepted go budget.
All workers use the same receipt/ponder origin and hard deadline. The leader's
completion cancels helpers; normal and exceptional exits join them before return.
Changing Threads transactionally replaces workers and clears learned/cache state.

Explicit node-limited searches reserve one global atomic ticket per visited
node; the limit is not multiplied by Threads. Other searches publish padded
worker counters every 128 nodes and on iteration/worker completion. Intermediate
UCI totals may therefore lag helper work by up to 127 nodes per helper. Final
`info nodes ... time ... nps ... hashfull ...` totals follow helper joins and are
exact. Depth/score/PV are not repeated in that final totals record. Redundant
worker effort contributes to node counts and is not a strength measure.

With diagnostics enabled, `smp v1` identifies worker count, leader nodes, total
nodes, and comma-separated per-worker node/completed-depth arrays. Existing
`search-iteration v1` records describe only the leader; their nodes sum to
`leader_nodes`. Search-summary, cache events, ordering, and LMR counters aggregate
all workers. Cache geometry still describes just one table. Single-worker
diagnostic accounting stays unchanged and emits no SMP record. Historical
single-worker profilers remain single-worker tools.

See the [Phase 4B contract](PHASE_4B.md) and the
[Phase 4A cache decision](reports/2026-10-18-phase4a-cache.md). Syzygy is a
separate optional module with the draw-rule and configuration boundary below.

The first selective-search experiment is optional, conservative late-move
reduction. Its [policy and verification contract](SELECTIVE_SEARCH.md) are
separate from time management and move ordering. A reduced result that improves
alpha must be verified at ordinary depth before a cutoff. Reduced fail-lows
remain heuristic; nominal depth does not imply all branches received that depth.
Changing reduction policy invalidates transposition bounds and learned ordering
state through the search API, including callers outside the UCI controller.
Keep the option off until strength qualification supports default promotion.

The separate [capture-ordering experiment](MOVE_ORDERING.md) introduces a small
position-dependent exchange module. It reads a Position into private bitboards,
estimates a deterministic legal least-valuable-attacker sequence, and changes
only move priority. It never modifies Position, NNUE, search depth, or move
membership. Experimental ranks are computed once per move; the baseline
comparator remains selectable. Search cache isolation covers both policy axes.

The initial core has no variant framework, opening book, or puzzle service.
Modularity means clear data and responsibility boundaries, not runtime machinery
for extensions that do not yet exist.

## Experimental verified null-move boundary

`Null Move Pruning=false` remains the default. The independent opt-in candidate
uses a fixed reduced pass probe only at eligible interior non-PV nodes, followed
by a reduced search of legal moves on the original position. Both searches must
finish and fail high outside the mate/tablebase bands before returning `beta`.
This is a heuristic cutoff, not proof of the original-depth bound. Exact guards,
depth reductions, and the bounded development contract are in the
[experiment protocol](experiments/phase4d3-null-move.md).

A by-value search mode propagates through every recursive and quiescence call.
Both speculative subtrees disable further null probes, LMR, reverse futility, tablebase probes,
TT reads/writes, and killer/history/countermove learning. Existing ordering hints
may be read. The pass subtree never appends fictional history or adjudicates
repetition/rule-50 draws; legal verification retains genuine history and draw
rules. Terminal legal-move tests still precede evaluation and draws. Neither
speculative PV escapes; only the ordinary search reports real lines. A direct
verified null cutoff is not stored as an original-depth TT entry, though
ancestors can naturally cache results influenced by the experimental policy.

Policy changes clear cached bounds and learned state even through the public
search API. Attempt/outcome counters stay worker-local and are summed after
helpers join; diagnostics remain optional. All speculative work uses existing
node tickets and clock/cancellation checks. Ordinary cancellation restores
moves; exceptions discard the local position and reset worker state on reuse,
rather than promising transactional unwinding of every legal descendant.

## Experimental reverse-futility boundary

`Reverse Futility Pruning=false` remains the default. The opt-in candidate
considers only ordinary interior non-PV nodes at depth 1–3, after legal terminal,
draw, mate-distance, tablebase and transposition handling. A fresh evaluation
must exceed beta by 200, 350 or 500 internal score units, respectively; these
are not normalized UCI centipawns. The [fixed protocol](experiments/phase4d4-reverse-futility.md)
records the quiet-position, material, advanced-pawn, history and score guards.

An accepted cutoff returns beta, clears local PV length, makes no chess move
and does not directly store an original-depth TT bound. Ordinary ancestors may
still cache results influenced by this heuristic. Evaluation can update the
worker-local NNUE accumulator cache using its existing transition mechanism.
Policy switching clears reusable bounds/history. Optional evaluations/cutoffs
counters remain private until helpers join. Both null-move speculative modes
disable this policy through their complete subtrees. Quiescence is unchanged.
Quiet checks, quiet defensive moves and distant threats remain possible failure
modes; the restrictions and tests do not prove unchanged playing strength.

## Experimental quiescence SEE boundary

`QSearch SEE Pruning=false` remains the default. The independently implemented
filter considers only ordinary interior quiescence nodes whose **entry**
window has width one, after terminal/draw handling and a surviving stand-pat.
The [fixed protocol](experiments/phase4d5-qsearch-see.md) records the check,
score-band, repetition, halfmove, advanced-pawn and material exclusions.
Requiring more than eight pieces also protects captures into seven-piece
endings. Both null-probe and verification subtrees disable this filter.

Only ordinary nonpromotion, non-en-passant captures receive an exchange test.
A negative legal-LVA estimate proposes a skip; the real child must still have
legal moves and must not be in check. Inspection makes/unmakes the position
before any child history push or evaluation. Stop checks surround expensive
probes, and skipped captures create neither child nodes nor PV entries. There
is no new quiescence TT storage; ancestor bounds may depend on the heuristic.
Changing the option clears reusable bounds and learned worker state.

Worker-local exchange/pruned counters require diagnostics and aggregate after
helpers join. The existing SEE model ignores off-square threats and alternate
exchange choices, so nonchecking sacrifices can be misjudged. Correct legal
output and reduced node counts do not establish unchanged playing strength.
Delta pruning is a separate, unimplemented experiment.

## Optional tablebase boundary

`Search` owns a configured Syzygy adapter. Path changes happen only while idle
and clear cached search state. Root DTZ ranks are obtained before helpers start,
reconciled against the complete independent legal move list, intersected with
UCI restrictions, and passed to every worker as the same restricted root list.
Repeated reversible histories bypass root ranking. Normal root search owns the
PV and score; no external PV, evaluation, or mate-distance value is imported.

Interior WDL probing is initially limited to non-PV, positive-depth nodes with
zero halfmove clock and no castling. Wins/losses provide only lower/upper bounds;
draws are exact under the fifty-move rule. The ±29000 internal tablebase band
lies below actual mate proofs and above the enabled heuristic evaluation cap.
Missing probes leave ordinary search running. `tbhits` is a shared atomic count
reset per request; final totals are read after all helpers join.

Fathom mappings are process-global. A serialized, generation-bound adapter
prevents stale instances from using or destroying a replacement configuration.
This deliberately conservative implementation has no parallel probe claim.
File integrity remains the user's responsibility; basic setup checks do not
turn the upstream compressed parser into a hardened hostile-input decoder.
