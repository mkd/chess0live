# Fathom tablebase reader

This directory contains the MIT-licensed, optional Syzygy file reader from
[jdart1/Fathom](https://github.com/jdart1/Fathom), pinned at
[`c9c6fef0dddc05d2e242c183acf5833149ab676d`](https://github.com/jdart1/Fathom/tree/c9c6fef0dddc05d2e242c183acf5833149ab676d)
(upstream commit dated December 24, 2025). It is compiled as C++26, separately
from the independently written chess0live adapter, search, and move generation.

The owner authorized using the same tablebase dependency as Gargantua and Sic;
dependency-only inspection established that both use this reader family. Fathom's probing code derives from Ronald de Man's Cfish tablebase
component; Fathom's own move generation/support code replaces the Cfish board
code. This is a third-party reader, not an independently authored chess0live
decoder. No Stockfish or owner-engine search/evaluation code is linked through
this integration. See the upstream [history and credits](https://github.com/jdart1/Fathom#history-and-credits)
and retained [MIT license](LICENSE).

Dependency-only inspection confirmed the same reader family in Gargantua's
[`src/tbprobe.cpp`](https://github.com/mkd/gargantua/blob/5ae52eeb8212be55c550e0ba2cf7da03208af220/src/tbprobe.cpp)
and Sic's
[`src/tbprobe.c`](https://github.com/mkd/sic/blob/1442e5bfbdf36a543dea10aa119d4cfeef7a370a/src/tbprobe.c).
Those engines' adapters, search logic, tests, and table data were not copied.
All six vendored files were fetched directly from the pinned upstream commit.

## Local patches

[manifest.json](manifest.json) records upstream and vendored SHA-256 values;
[chess0live-safety.patch](chess0live-safety.patch) is the complete source delta.

- Failed file mappings close the file descriptor and return probe failure
  instead of terminating the engine.
- Descriptor ownership on a failed POSIX `fstat` stays with the mapping caller,
  preventing a double close along that error path.
- A failed Windows view creation releases its mapping handle.
- Incomplete-file diagnostics remain on stderr; the extra stdout UCI line is
  removed because the chess0live controller owns protocol output.

No move-ranking, indexing, decoding, WDL, or DTZ algorithm was changed. The
reader's root-probe thread-safety descriptions differ between its README and
header, so the adapter serializes all probes and initialization/destruction.
`TB_NO_THREADS` is not enabled.

## Data and safety boundaries

No `.rtbw`, `.rtbz`, or `.rtbm` files are included here. Table files are separate
user-managed data; obtain them independently and verify their published
checksums. Do not change, replace, truncate, or remove configured files during
search. The adapter checks regular-file status, length congruence, and magic
headers, which detects common incomplete downloads. This is not full
validation of compressed payloads: upstream is not a hardened parser for
arbitrary corrupt or hostile files, and its unchecked low-level allocations
also remain an upstream limitation.

Only WDL and DTZ probing are used. DTZ describes distance to a zeroing move,
not distance to mate. The adapter ignores upstream centipawn/mate-style scores
and PVs; chess0live derives legal moves and any mate proof from its own search.
Root rankings retain upstream handling of rounded DTZ values near the
fifty-move boundary. WDL search probes require a zero halfmove clock.

To update the dependency, review API, threading, parser, license, and rule-50
changes; regenerate both checksums and the complete patch; then rerun adapter,
search, lifecycle, sanitizer, and real-table comparison checks. A successful
compile is not proof of cross-platform execution or correct tablebase results.
