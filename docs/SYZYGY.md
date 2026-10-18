# Optional Syzygy endgame tables

chess0live uses the standalone MIT-licensed Fathom reader, fetched directly from
its upstream project at the revision recorded in
[the vendor manifest](../third_party/fathom/manifest.json). Search, evaluation,
position state, and the integration adapter are independently implemented.
The owner authorized using the same tablebase dependency as Sic on October 18,
2026. This exception is limited to the external tablebase reader; it does not
permit importing the owner's engine code, match assets, or Stockfish search.
See the [reader provenance](../third_party/fathom/README.md).

## Installation and UCI configuration

Build normally with `make`. The reader is compiled into the executable; table
**data is not**. Obtain ordinary-chess Syzygy `.rtbw` (win/draw/loss) and `.rtbz`
(distance to a zeroing move) files separately, checking the supplier's checksums.
Use a local directory that will remain readable and unchanged while the engine
is running. Full five-, six-, and seven-piece sets can require substantial
storage; no large download happens when building or launching chess0live.

```text
uci
setoption name Threads value 4
setoption name SyzygyPath value /absolute/path/to/syzygy
setoption name SyzygyProbeLimit value 7
setoption name SyzygyProbeDepth value 1
isready
position fen 8/k1P5/2K5/8/8/8/8/8 w - - 0 1
go depth 4
```

Wait for `readyok` before searching. Paths may contain spaces. Multiple table
folders use the platform separator: `:` on Linux/macOS and `;` on Windows.
`SyzygyPath` defaults to `<empty>` (disabled). Setting it to `<empty>` or an empty
value disables probing again. `SyzygyProbeLimit=0` also disables probes; 1–7 cap
the number of pieces, including both kings. `SyzygyProbeDepth` accepts 1–128 and
controls interior probes; it does not defer root DTZ ranking. A reported largest
piece count means some tables of that size were discovered, not that every
material configuration is present.

Configuration stops and joins search workers first and invalidates cached
bounds. `ucinewgame` and `Clear Hash` retain the configured table path.
Successful probes are reported as standard UCI `tbhits N`, aggregated across
workers, including the final totals. A hit is a successful probe, not a file
read, a node count, or proof of mate.

Table directories `/syzygy/` and `/tablebases/`, and `.rtbw`/`.rtbz` files anywhere
in the checkout, are excluded from Git. Users supply their own production data.

## Search semantics

- Before dispatching helpers, root DTZ ranks filter the full legal move list.
  UCI `searchmoves` is intersected first; the best-ranked moves *within the
  allowed subset* remain. Normal search chooses among these moves and produces
  the evaluation and PV. Every external move must decode to exactly one move
  in chess0live's legal list, with no missing or duplicate entries.
- Root ranks account for the current fifty-move clock and DTZ rounding. DTZ is
  distance to a capture or pawn move, **not distance to mate**. The engine never
  converts it to `score mate`. Actual mating lines still come from search.
- Root filtering is skipped if the reversible game history contains any
  repeated position. Table data cannot encode repetition rights. Own mate,
  stalemate, fifty-move, and threefold checks remain authoritative.
- Interior WDL probes initially require a non-PV node, sufficient depth, zero
  halfmove clock, no castling rights, and an available piece count. Quiescence
  uses ordinary search. Restricting WDL to a zeroing position avoids declaring
  a theoretical win with an already exhausted fifty-move budget.
- A genuine WDL win/loss supplies a lower/upper bound in an internal ±29000
  tablebase band, below the mate band. It only cuts off when that bound proves
  the window. Draws, cursed wins, and blessed losses are draws under the
  fifty-move rule. Neural evaluations remain below the tablebase band while
  probing is enabled. Direct probe results are not inserted into the TT;
  ordinary ancestor search bounds retain the history-aware cache key.
- Mate is checked before a fifty-move draw. The engine does not offer a setting
  that turns off the fifty-move rule.

Missing files, incomplete material coverage, unsupported positions, and missing required
DTZ fall back to ordinary search at the affected probe. No synthetic tablebase
result is invented. The adapter checks basic file shape/magic during setup;
this is **not** complete validation of compressed metadata. Use trusted,
checksum-verified tables and do not modify mapped files during a search.
A synchronous disk probe cannot be cancelled midway; cold/slow storage can add
latency. Its elapsed time still consumes the existing search clock.

The backend has process-global state. Adapter calls are serialized and bound
to a configuration generation. Reconfiguration invalidates older adapter
instances; they fall back instead of probing another instance's new directory.
This conservative boundary favors correctness; wider parallel probing is a
separate, measured future change.

## Small reproducible validation corpus

The test-data manifest pins all ordinary three-/four-piece WDL and DTZ files
(70 tables), plus source/license notices, from a fixed python-chess revision.
The total is 4,381,961 bytes. The table data is downloaded into ignored storage;
only checksums, provenance, and independently composed FEN cases are versioned.
The upstream repository notice is preserved without inventing a separate table
license. No files or test positions come from the owner's other engines.

```sh
make fetch-syzygy-test
make test-fetch-syzygy
make -j2 test-syzygy
python3 tools/generate_syzygy_cases.py
```

The download is explicit; ordinary `make` and `make test` never fetch tables.
`test-syzygy` first verifies existing data and fails if it is missing or changed.
Its UCI/PV referee needs the optional `requirements-match.txt` dependencies.
Offline installation is also supported:

```sh
python3 tools/fetch_syzygy_test_tables.py --from-directory /path/to/verified/copy
```

Correctness cases cover underpromotion instead of stalemate, essential en
passant, rule-50 clock sensitivity, mate precedence, and unavailable tables.
Three-/four-piece execution is the bounded initial evidence; seven-piece
support follows the backend's format capability and is not a claim that a
seven-piece corpus or every target platform was executed. This feature does
not establish a whole-engine Elo gain.
