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

Start with a correctness baseline: iterative deepening, alpha-beta/PVS,
quiescence with check evasions, transposition storage, draw recognition,
move ordering, cancellation, and clock budgeting. Establish deterministic
single-worker evidence before enabling shared-memory search. Add pruning,
reductions, parallelism, and speculative ideas through isolated experiments and
matched-game testing, retaining changes only on appropriate evidence.

The initial core has no variant framework, opening book, or puzzle service.
Modularity means clear data and responsibility boundaries, not runtime machinery
for extensions that do not yet exist.
