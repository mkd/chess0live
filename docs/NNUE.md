# NNUE interoperability and verification

chess0live independently implements the **Stockfish 19 release's SFNNv16** file
format, features, quantized evaluation, and a zero-optimism evaluation wrapper.
No implementation from Stockfish or the author's previous engines is linked
into the engine. The interoperability specification was established by reading
the official pinned source. The separate test oracle uses upstream code only
inside an ignored reference checkout.

This is compatibility with one architecture, not with every file ending in
`.nnue`. Stockfish's development branch may change its architecture; do not
silently substitute its current network or source for this release pin.

## Pinned network

| Item | Value |
| --- | --- |
| Reference release/tag | Stockfish 19 / `sf_19` |
| Reference commit | `edb0d9db6731067ec50ce619ff372b463bc4dd5d` |
| Network | `nn-1a298aa575a0.nnue` |
| Full SHA-256 | `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Size | 98,511,183 bytes |
| Network license | CC0-1.0 |

The [official default-name declaration][default-net] identifies the file.
The [official network repository][networks] states that its networks were
uploaded under CC0. Its Git LFS pointer supplies the full digest and size;
both were independently checked against the downloaded payload on 2026-10-13.
The machine-readable record is [networks/manifest.json](../networks/manifest.json).

```sh
make net
python3 tools/fetch_network.py --verify-only
```

The fetcher uses the official service, with the official GitHub LFS media mirror
as a fallback. It validates the complete payload and filename hash prefix before
atomically installing it. It never replaces a valid file with an unverified
download. A previously downloaded payload can be installed with
`--from-file /path/to/network.nnue`. Network payloads are ignored by Git.

## Independently written implementation

`Network` holds immutable weights after a successful load. A failed load leaves
the previously loaded network intact. Load or replace a network only after all
search workers have stopped. `Evaluator` belongs to one worker and references
the longer-lived `Network`; do not share an evaluator between threads.

`Network::evaluate()` rebuilds accumulators from the current position and returns
the two exact integer components, `psqt` and `positional`. It retains the full
feature enumerator as a reference. `Evaluator::raw()` remembers the last
evaluated board and derives changed squares from piece identities. With unchanged
king orientation, it enumerates only affected piece-square, threat and pawn-pair
features, cancels common multiset entries, then subtracts/adds their columns.
Empty-board attack masks conservatively select sources whose targets or blockers
may have changed. A changed king bucket or mirror refreshes that perspective.

Arbitrary transitions, undo, skipped evaluations, siblings, king moves and special
moves retain exact behavior. Both perspectives' feature plans are fully prepared
before either accumulator changes. Null moves reuse accumulator values but still
run inference and calibration with the current side and clocks. Reload/reset
invalidates the remembered board and accumulators through the network generation.

Feature differences now stream through batches of up to eight column views.
Each batch updates a 32-lane tile before storing it, reducing repeated hidden
accumulator loads/stores; singleton batches retain the simple column path.
Every difference is consumed, including duplicates and arbitrary transitions:
the batch capacity never limits feature counts. Hidden and PSQT lanes preserve
the same modulo-2^16 and modulo-2^32 arithmetic in NEON and scalar code.
The [Phase 3B result](reports/2026-10-16-phase3b-nnue-batching.md) records exact
parity and the measured opening-search speedup, without a strength claim.

The worker still has one pair of accumulators, not a per-ply saved stack. It
compares piece bitboards and sorts the affected feature lists; full refreshes retain
full enumeration. A lazy search-state stack and king refresh cache remain future
hypotheses, requiring their own correctness and measurement evidence. The
[Phase 4F.11 protocol](experiments/phase4f11.md) separates exact arithmetic and
implementation timing from subsequent tactical and playing-strength assessment.

On AArch64 with NEON available, independently written vector kernels accelerate
accumulator updates and affine dot products. Other targets use the portable
scalar implementation. Both preserve quantized lane arithmetic explicitly.
The retained Phase 3F dense kernel processes four output rows together in the
`1024→32` and `64→32` layers, reusing each 16-byte activation load across four
independent sums. Weights remain row-major. Product sums fit int32 under the
activation/weight bounds; adding the bias uses int64 before the final modulo
conversion. The scalar kernel and `128→1` output path are unchanged.
The [Phase 3F result](reports/2026-10-17-phase3f-dense.md) records measured
throughput gains over the retained Phase 3B engine of about 19.6% for openings,
19.7–21.4% for middlegames, and 32.4–39.5% for endgames on the fixed M5 Pro sample.
These are local performance observations, not Elo gains or promises for every
position or platform.

Force the scalar backend with:

```sh
make SIMD=scalar test
```

The equivalent compiler definition is `CHESS0LIVE_FORCE_SCALAR`. The Makefile
uses a separate build directory for the scalar configuration. No AVX-specific
backend is implemented in this milestone.

## Format and feature contract

The [official reader][reader] and [integer format definitions][common] define:

1. Little-endian 32-bit version `0x6a448afa`, architecture hash `0xa85b2205`,
   description length, and description bytes.
2. Feature-transformer hash `0xcb685313` and transformer parameters.
3. Eight layer stacks, each preceded by architecture hash `0x63337116`.
4. Exact end of file after the last stack.

Signed-LEB128 blocks start with the 17-byte `COMPRESSED_LEB128` marker and a
little-endian compressed-byte count. The independent reader bounds file and
description lengths, checks compressed byte counts, rejects truncated/overlong
integers and out-of-range decoded values, and rejects trailing file data.

The [transformer serialization order][transformer] is: compressed `i16` biases;
raw `i8` threat weights; compressed `i32` threat PSQT weights; raw `i8` pawn-pair
weights; compressed `i32` pawn-pair PSQT weights; compressed `i16` piece-square
weights; compressed `i32` piece-square PSQT weights. Affine layers then serialize
their `i32` biases and row-major `i8` weights. CPU-specific upstream memory
permutations are not part of the file layout.

| Feature family | Dimensions | Feature hash |
| --- | ---: | --- |
| `HalfKAv2_hm` | 22,528 | `0x7f234cb8` |
| `FullThreats` | 59,808 | `0x2e6b9d04` |
| `PP_3Wide` | 4,560 | `0x86f2b1dd` |

There are 86,896 input dimensions. Piece-square features use 32 mirrored king
buckets, relative piece colors, and separate perspective orientation. The
threat feature set uses selected occupied-piece relationships, including
friendly relationships and symmetry exclusions; legal move generation cannot
replace these features. Pawn pairs cover pawns on the same or adjacent files,
with ranks 2–7 and both colors. Their feature indices start at 59,808 in the
combined relationship array. chess0live generates its geometry/index tables
from these rules, without importing upstream lookup-table assets.
See the pinned [piece-square][psq], [threat][threats], and [pawn-pair][pairs]
definitions.

The [network architecture][architecture] has 1,024 `i16` accumulator elements
and eight `i32` PSQT values per perspective. Clipped pairwise accumulator
products form 512 bytes per perspective, ordered side-to-move first. The first
affine layer is `1024→32`; its squared and linear activations feed a `64→32`
layer. Both activation stages feed a `128→1` layer. The difference of the last
two first-layer outputs provides a skip term. Every activation, division,
truncation, and scale is preserved as integer arithmetic. Material chooses one
of eight stacks using `(piece_count - 1) / 4`.

`Evaluator::evaluate()` returns internal evaluation units, not centipawns. It
applies the pinned [material/complexity/rule-50 wrapper][wrapper] with optimism
fixed at zero. The UCI layer normalizes display scores separately; Stockfish's
fitted display calibration is not a measured chess0live win-probability model.
Structurally valid hostile weights can still produce unreasonable scores, so
calibration rejects raw components outside ±2^20 before multiplication. This
keeps arithmetic bounded even with the largest stored halfmove clock.

## Reproduce the oracle check

```sh
make net
make test-nnue
python3 tools/verify_nnue.py --jobs 2
```

For a simple interface that also accepts alternative SFNNv16 weights, use
`make network-qualify` or `python3 tools/network.py qualify /path/to/candidate.nnue`.
See [network inspection and qualification](NETWORKS.md). The original
`--network` option remains restricted to the pinned artifact; the explicit
`--candidate-network` route compares candidate outputs against the same pinned
reference without imposing the default network's twelve golden scores.

The harness requires Git, Make, Python 3.10+, and a Clang/GCC driver accepting
`-std=c++2c`. `--compiler-executable '/absolute/path/to/clang++'` selects a literal
compiler path for both local and upstream adapters. The legacy `--compiler`
option still accepts a shell-style command. The report records its invoked command
and version. The upstream build uses at most two compiler jobs, reduced by the
current local resource allowance; local adapter builds run serially.

The default workspace is `build/nnue-oracle/`. The harness caches `sf_19`, checks
the exact commit, and builds a fresh local clone of its committed tree for each
run. Dirty cache files and stale objects never enter that build. It opens one
private access label in that isolated header for
test inspection. It preserves upstream notices and builds a separate executable
from the independent [reference adapter](../tools/oracle/reference_main.cpp).
Production sources never depend on that checkout. The local
[stage adapter](../tools/oracle/chess0live_stages.cpp) includes the local evaluator
only to inspect its private implementation in a test executable.

`--reference-dir` selects another pinned cache; `--offline` prohibits its download.
Work/cache locks serialize reuse, each child command has a bounded timeout, and
failure replaces stale success. Reports bind the network, corpus, local/reference
sources and all five test executables by full SHA-256, checked again at the end.
The user-facing network command additionally requires a new output directory,
preserving earlier reports. Native Windows setup/cancellation remains unverified.

The reference defaults to `apple-silicon` on Apple Silicon, otherwise
`general-64`. Those paths have canonical accumulator ordering; the harness
intentionally does not accept arbitrary upstream SIMD architectures whose
internal lane permutations would need separate normalization.

The executable built from `tests/nnue_test.cpp`, invoked with `--positions`,
generates the original deterministic corpus:
special-move positions and their legal successors, followed by twelve seeded
games of up to 160 plies. Seed: `0x4348455353304c49`. No positions, games, or
benchmark assets from the author's previous engines are used.

For every position, the harness compares the complete integer arrays for:

- Piece-square and combined threat/pawn-pair feature indices, both perspectives.
- All accumulator and PSQT entries, both perspectives.
- Transformed input, first and second affine outputs, concatenated activations,
  final affine output, and selected material bucket.
- Exact raw `{psqt, positional}` and the zero-optimism wrapped score. The wrapper
  is excluded in check, matching the upstream evaluator's contract.

Both the native and forced-scalar builds must match the reference. The raw dump
also checks incremental versus full-refresh results at every position. Additional
tests cover sibling make/unmake, reset/reload, failed-load preservation,
malformed compression, twelve pinned raw/wrapped golden cases, and rejection of
an architecture-valid network with an extreme final-layer bias.

`make test-nnue` also runs 360 synthetic update transitions against an independent
column-at-a-time arithmetic reference. It checks signed weight widths, duplicate
multiplicities, batch boundaries, empty and large changes, reversibility, and
extreme modular lane values. This reference never calls the production batch
kernel: both ordinary incremental and full-refresh evaluation do, so their
agreement alone cannot exclude a shared arithmetic error.

The same target also runs the independent dense-layer int64 arithmetic oracle
in `tests/nnue_dense_test.cpp`: **1,515 cases / 84,126 repeated-call output
comparisons** across all three layer shapes. It covers every input lane and
output row, maximum products, extreme biases and modulo wraparound, cancellation,
mixed edges, deterministic random values, and input/model immutability. It does
not share the production vector grouping or call another production kernel as
its expected-result calculation.

## Recorded validation: 2026-10-13

On macOS ARM64, Apple Clang 21.0.0, the reproducible harness passed **2,057
positions with zero differences** for scalar, native NEON, and the official
SF19 Apple Silicon oracle. The same NNUE tests passed AddressSanitizer and
UndefinedBehaviorSanitizer. These observations do not establish runtime
validation on another CPU/OS or playing strength against Stockfish.

| Artifact | SHA-256 |
| --- | --- |
| `positions.fen` | `6e48940a6ed8cd8edaedc97580a18840320ae6ee9fad9c8ed1a78f4123431d9e` |
| Canonical full stage dump, 25,272,656 bytes | `4dcca7b66ddb5228ebb2c3ad1b5380f36ee8d0bccdd54e0e94b2488a3f62e1fe` |
| Raw/wrapped output dump | `c7a41f1dbfeba274556e579ae0f65e50ae0e5d6a2010d551639d0fbf676d92e3` |

The generated `build/nnue-oracle/report.json` includes compiler information,
resource allowance, pins, corpus digest, source-file digests, and all output
digests. Full dumps and build logs remain beside it for inspection. A future
move-generator ordering change may change the seeded corpus digest; rerun both
oracles and investigate changes rather than relabeling old evidence.

The Phase 3B rerun on October 16 passed the same 2,057 positions and all recorded
stage/raw digests for native and scalar builds. New evidence is in
`build/nnue-oracle-phase3b-20261016/`; the original directory is preserved.
The full native/scalar/sanitizer engine suites also passed, including the new
independent arithmetic checks. No foreign-platform throughput is inferred.

The Phase 3F rerun on October 17 again passed the unchanged 2,057-position corpus
for native and scalar builds, with identical corpus, full integer-stage, and
raw/wrapped output digests shown above. Evidence is in
`build/nnue-oracle-phase3f-20261017/`. Native, forced-scalar, and ASan/UBSan engine
suites passed, including all 1,515 dense cases / 84,126 output comparisons per
build, the 360 update transitions, and the existing incremental checks. The
[Phase 3F report](reports/2026-10-17-phase3f-dense.md) records complete validation
and the separate performance decision; no additional platform execution is
claimed.

## Extending the evaluator

Keep the scalar implementation as the mathematical reference. Add a new backend
behind a narrow arithmetic boundary; prove complete parity before benchmarking
it. Keep immutable weights shared and mutable accumulators worker-local. Test
network changes, make/unmake, sparse endgames, king mirroring, promotions, and
changed sliding rays explicitly.

A newly trained network must use exactly this feature mapping, dimensions,
quantization, activation functions, stack selection, and serializer, or require
an explicitly versioned new architecture implementation. Compatible file loading
alone is insufficient proof of evaluation correctness or improved chess strength.
Network-training and self-play-strength validation are separate workstreams.

[default-net]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/evaluate.h
[networks]: https://github.com/official-stockfish/networks
[reader]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/network.cpp
[common]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/nnue_common.h
[transformer]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/nnue_feature_transformer.h
[psq]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/features/half_ka_v2_hm.h
[threats]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/features/full_threats.cpp
[pairs]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/features/pp_3wide.cpp
[architecture]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/nnue/nnue_architecture.h
[wrapper]: https://github.com/official-stockfish/Stockfish/blob/edb0d9db6731067ec50ce619ff372b463bc4dd5d/src/evaluate.cpp
