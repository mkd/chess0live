# Architecture and design decisions

## Independence and boundaries

The engine implements chess and search itself. NNUE mathematical/file-format
interoperability is specified from pinned upstream sources; the Stockfish
executable is a separate test oracle. Training tools are separate from inference
and are not required to run the engine.

The initial dependency direction is:

`types → position → NNUE → search → UCI`

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

Transposition caching is already implemented in `src/search.cpp`: four entries
per bucket, stored moves/scores/depths/bounds, generation/depth replacement,
mate-distance normalization, and a history/rule-50-aware key. `Hash` controls
capacity and `Clear Hash` clears cached search state. The current table has one
owning search thread; it is not yet safe to share by simply starting more threads.
Future cache work should measure hit/cutoff behavior and memory cost before
changing representation, key semantics, or replacement. Preserve repetition,
rule-50, and policy-isolation correctness even when a faster key looks attractive.

Lazy SMP is planned as separate worker-local position, history, and NNUE state
over immutable shared weights, with explicitly safe transposition sharing and
coordinated time/stop handling. Syzygy is a later optional endgame-probing module
with its own correctness and configuration boundary. Neither feature exists in
the current executable. These work areas follow the bounded qualification
preparation checkpoint; they do not require repeatedly retuning the same screen.

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
