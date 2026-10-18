# Phase 4C — optional Syzygy checkpoint

Date: October 18, 2026. Status: implemented and validated on macOS ARM64.
Implementation commit: `2468d73`.
This is an endgame-feature checkpoint, not a release or Elo qualification.

## Result and dependency decision

The owner asked to inspect Gargantua and Sic and use their tablebase dependency.
Dependency-only inspection identified Fathom-family probing in both. chess0live
vendors directly from upstream Fathom commit
`c9c6fef0dddc05d2e242c183acf5833149ab676d`, preserving MIT notices and explicit
Cfish ancestry. No owner-engine adapter, search, tests, or table files were
copied. Upstream whitespace is preserved with its source pins; original project files
pass the whitespace check. The [vendor record](../../third_party/fathom/README.md) pins the inspected
references, checksums, and narrow mapping-error/stdout patches.

The new independently written adapter configures external table directories,
serializes the process-global backend, and invalidates obsolete bindings.
Search uses root DTZ ranks and conservative non-PV WDL bounds, retains own
legal moves and mate proofs, and reports aggregate UCI `tbhits`. Tablebase and
mate score bands remain distinct. Root restrictions respect `searchmoves`;
repeated reversible histories use ordinary search. Interior probes require
zero halfmove clock. See [semantics and setup](../SYZYGY.md).

Table data is optional, downloaded separately, and excluded from Git. Ordinary
build/test commands never fetch it. The explicit test fetcher pins a 4,381,961-byte
three-/four-piece corpus, including provenance notices. Its deterministic oracle
generator uses python-chess 1.11.2 without an engine or owner's positions.

## Executed checks

Host: Apple M5 Pro, macOS ARM64, Apple Clang C++26 mode. Short local checks used
modest concurrency within the nine-worker daytime allowance. No long match,
cloud job, or schedule was started.

| Check | Result |
| --- | --- |
| Native full core/NNUE/search/policy/time suite | Passed |
| Scalar full suite | Passed |
| AddressSanitizer + UndefinedBehaviorSanitizer full suite | Passed |
| ThreadSanitizer search suite | Passed |
| Existing Lazy SMP UCI/lifecycle suite | 43 cases passed in native, ASan/UBSan and TSan builds |
| Real table adapter suite | All four builds passed 140 exact WDL comparisons, DTZ outcome/legality checks and special/lifecycle cases |
| Syzygy UCI suite | 47 cases passed in native, scalar, ASan/UBSan and TSan builds |
| Direct search/tablebase clock gates | Six scenarios each at Threads=1 and 4 passed in all four builds |
| Fixture fetcher | 13 tests passed; all 72 local file hashes verified |
| SMP profiler parser | 25 tests passed, including optional `tbhits` compatibility |
| Oracle reproduction | 140 distinct JSON/C++ cases reproduced byte for byte |
| Default-off parent/candidate comparison | 24 searches exact; independent raw-output/pin audit passed |

The adapter corpus covers all 35 ordinary three-/four-piece material classes,
both turns, and color reflections. Tests also cover essential en passant,
rook underpromotion instead of stalemate, DTZ rounding/clock boundaries,
checkmate precedence at halfmove 100, complete legal root reconciliation,
missing WDL/DTZ, split directories, bad magic/truncation, obsolete contexts,
and concurrent probes. These are exact WDL comparisons and DTZ ranking/outcome
checks, **not raw DTZ-distance equality** through an API that exposes no distance.
Intrinsic five-piece cursed/blessed outcomes and larger corpora were not run.

UCI tests isolate interior hits from root hits using WDL-only folders, prove
history-aware root fallback, and exercise cancellation/reconfiguration with four
workers. Direct search checks prove that prepublished stop, expired receipt
budgets, and already-hit zero-time pondering avoid root probing; unhit pondering
retains access. A one-node request never exceeds its aggregate search node cap.

## Reproduced failures and limitations

Review found a real adapter gap: a 16-byte magic-only file passed the first
shape check. The minimum is now 80 bytes, with a failing-case regression. This
is basic truncated-download detection, not complete compressed-payload safety.
Published checksums and stable trusted table files remain required.

Two test premises were corrected without changing engine behavior: a proposed
interior-probe position had no eligible non-PV zeroing continuation, and the first
clock-test FEN illegally checked the nonmoving king. Failed logs are retained;
final tests use independently checked legal cases. Earlier scalar/TSan optional
suite failures were from the first premise; the corrected 47-case suite passed.

The backend performs synchronous file access. Cold or slow storage can delay a
probe, although elapsed time is charged to the existing clock. Missing tables
fall back; there is no claim of perfect endgame play with incomplete data or
history fallback. Seven-piece format capability and intended foreign targets
are not seven-piece or foreign-platform execution evidence. No GUI visual
pass, whole-engine strength increase, or new release is claimed.

## Default search preservation

Frozen parent: `fac6c43`, executable SHA-256
`0abcb60f7271f17c9e8735095fbb48c72e425beef2647ae0ed24af6f7a5471e9`.
Current native executable SHA-256:
`9b5f03e02d9537041025dfd6a815a1ef734fb7a303a14bcaba17f1ea4f57e898`.

Three exposed benchmark roots at depth 6, Threads=1, Hash=64, with one warmup
per binary/root and three alternating-order measured pairs, produced 24 searches.
All completed-depth nodes, scores, PVs, selective depths, final best/ponder moves,
hashfull, and final node counts agreed; candidate `tbhits` stayed zero.
The nine measured elapsed-time ratios (parent/candidate) had median **1.005949**,
range **0.870506–1.043107**, MAD **0.024450**. This small noisy sample supports
behavior preservation, not a speed or strength gain. No compile or other agent
benchmark ran during these measurements; unrelated machine activity is not
controlled by this tool.

All three stable GUI executables, the Phase 3L engine/manifest, all 16 campaign
source pins and six frozen assets, and the README introduction are unchanged.
The 512-game historical LMR campaign remains unstarted. Raw logs, comparison,
and preservation hashes are in ignored `results/phase4c-20261018/`.

## Reproduction and next checkpoint

```sh
make -j2 test test-smp
make fetch-syzygy-test
make -j2 test-syzygy test-fetch-syzygy test-profile-smp
make -j2 SIMD=scalar test test-syzygy
make -j2 MODE=sanitize test test-syzygy test-smp
make -j2 MODE=thread-sanitize test-search test-syzygy test-smp
python3 tools/generate_syzygy_cases.py
```

Phase 4C's bounded implementation checkpoint is complete. **Next: Phase 4D,
strength-gated search efficiency**, starting with one isolated full-depth
ordering candidate. The [plan](../SEARCH_OPTIMIZATION_PLAN.md) incorporates the
owner's [depth-10 work-count comparison](2026-10-18-depth-feedback.md), then
prioritizes separate LMR and conservative pruning experiments. Default promotion
requires fresh equal-time paired strength evidence. Broader platform execution
and network tooling remain in Phase 4E; no new match launches automatically.
