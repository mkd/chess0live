# Provenance

chess0live is an independently authored engine. No implementation, match runner,
benchmark suite, or comparison assets from the owner's earlier engines are used.
The project does not compile or link Stockfish engine code into its executable.

## Original implementation

Position representation, legal move generation, UCI controller, search, NNUE
reader/inference, build tools, and local testing tools were authored for this
project. Published techniques such as bitboards, Zobrist hashing, iterative
deepening, PVS, quiescence, transposition tables, and NNUE are used. An original
implementation of an established technique is not a claim of inventing it.

The optional late-move reduction experiment is independently implemented from
the general published search technique. Conceptual background:
[official Stockfish terminology](https://official-stockfish.github.io/docs/stockfish-wiki/Terminology.html#late-move-reductions),
consulted October 14, 2026. Its conservative guards, tests, and measurements are
documented in [selective search](docs/SELECTIVE_SEARCH.md). No upstream search
implementation is copied into this engine.

## Compatibility reference

The interoperability reference is official Stockfish 19, tag `sf_19`, commit
`edb0d9db6731067ec50ce619ff372b463bc4dd5d`. Its published format identifiers,
dimensions, feature-index definitions, integer arithmetic, and score calibration
define the compatibility contract. Those mathematical definitions are recorded
in [NNUE](docs/NNUE.md), with exact upstream sources.

UCI score display uses the material polynomial from the pinned
[Stockfish UCI implementation](https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/uci.cpp).
This is attributed normalization for the upstream network's scale, not evidence
of chess0live's own win/draw/loss probabilities.

An upstream build used for differential testing is separate from the shipped
engine. Upstream Stockfish is GPL-3.0-or-later, copyright The Stockfish developers;
its notices stay with that reference checkout and any upstream-derived patch.
An unmodified build of the same pinned source is also used as a match opponent;
it is separate from the instrumented NNUE oracle. See [match testing](docs/MATCHES.md).

## Network and fixtures

The official network is downloaded unchanged and verified using
[networks/manifest.json](networks/manifest.json). Its license is recorded
separately there; it is not reattributed to the chess0live author.

Perft reference counts are standard public correctness data. Exact FEN/count
provenance is given in `tests/position_test.cpp`, including
[Perft Results](https://www.chessprogramming.org/Perft_Results).
Random evaluation fixtures use an original deterministic legal-move generator
and recorded seed. No proprietary game collection is included.

The match runner uses the external GPL-3.0-or-later
[python-chess library](https://github.com/niklasf/python-chess), by Niklas Fiekas
and contributors, pinned as `chess==1.11.2` in `requirements-match.txt`. It is a
testing dependency, not part of the engine. The opening selection in
`tests/data/` was authored for chess0live and uses no external game collection.

The GNU GPL text in [LICENSE](LICENSE) is the unmodified FSF license text from
<https://www.gnu.org/licenses/gpl-3.0.txt>. Original project sources are
GPL-3.0-or-later, copyright Claudio M. Camacho.
