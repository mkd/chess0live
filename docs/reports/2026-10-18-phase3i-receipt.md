# Phase 3I response timing — October 18, 2026

**Retain the match-runner receipt fix. Engine play and historical results are
unchanged.** Logging could add artificial thinking time to a `bestmove` already
delivered in the same input batch as an earlier analysis line. The runner now
timestamps each batch before logging or protocol dispatch. This is a reproduced
measurement defect; the old logs cannot show which historical losses it affected.

All 212 checks in the combined match/qualification/audit/diagnostic suite passed,
including eight new deterministic protocol-clock regressions and eight receipt
tool tests. All 12 declared live controls completed with legal output and no
retry. They separate an intentionally sleeping consumer from a paused engine;
they do not qualify clock reliability under uncontrolled load or playing strength.
Independent replay checked all 12 bestmoves, 12 ponders, and 76 PV lines / 320 plies.

## Reproduction and repair

Work started from `4a2eff1` under the [bounded plan](../PHASE_3I.md). Before
changes, a virtual-time regression delivered `info` and `bestmove` together
at 50 ms, then made logging the first line consume 200 ms. The old runner
charged **250 ms against a 100 ms clock**, creating an artificial flagfall.
The repaired runner charges the correct **50 ms**. This test uses the actual
pinned parser with a controlled logger and monotonic clock; it neither launches
an engine nor relies on host scheduling or sleep duration.

The repair retains python-chess byte buffering, UTF-8 decoding, and CRLF
handling. It collects all complete lines in a callback and records them at the
callback-entry timestamp before dispatching them in original order. This also
keeps transcripts chronological when `readyok` processing synchronously sends
`position` and `go`. A partial line receives the timestamp of the callback that
supplies its newline. Equal timestamps are valid in existing independent audits.

Tests cover delayed same-batch logging, split lines, UTF-8/CRLF and malformed
UTF-8, stderr/error handling, reentrant commands, parser-exception cleanup, and
genuinely late callbacks. The transcript schema remains unchanged; the runner
manifest now states the receipt boundary explicitly. Historical campaign source
pins and outcomes are not rewritten, rescored, or treated as fresh evidence.

## Controlled observations

The frozen final Phase 3H executable ran all twelve searches on October 18,
**19:52:34.642379–19:52:45.811556 Helsinki**. Each fresh process used startpos,
`go movetime 620`, Move Overhead=20, Threads=1, Hash=64 MiB, classic timing,
MVV-LVA, and diagnostics. Both LMR modes ran twice in each condition, sequentially,
with readiness completed before sending `go`. The internal budget was 600 ms.

The dedicated reader thread timestamps complete lines before placing them in
the consumer queue. A consumer-only sleep releases Python's interpreter lock;
it does not suspend that reader. The POSIX engine-pause control sends SIGSTOP
around 400 ms and SIGCONT after a requested 500 ms pause, with resumption in
cleanup. Actual stop requests were 403.188–405.053 ms after go; intervals between
stop and resume requests were 505.103–505.129 ms. These are observed signal-request
times, not proof of the precise instant the kernel stopped execution.

| Condition, four searches each | Internal elapsed | Reader receipt | Consumer receipt | Reader / consumer within 620 ms |
| --- | ---: | ---: | ---: | ---: |
| Normal | 600.001–600.006 ms | 600.111–600.154 ms | 600.134–600.181 ms | 4/4 · 4/4 |
| Consumer sleeps until roughly 900 ms | 600.002–600.007 ms | 600.110–600.151 ms | 905.118–905.154 ms | 4/4 · 0/4 |
| Engine paused across deadline | 908.453–910.277 ms | 908.668–910.489 ms | 908.729–910.545 ms | 0/4 · 0/4 |

The consumer-sleep controls add 304.967–305.043 ms between reader observation
and consumption while engine response remains on time. The engine-pause controls
are late internally and externally. Their deliberate lateness is expected
mechanism evidence, not an operationally clean match result. No engine clock
can ensure response delivery while its process remains suspended.

The reader is a thread in the same Python process, not an independent-process
or kernel observer. Whole-process descheduling and interpreter-lock contention
can affect both reader and consumer. Reader-minus-internal elapsed combines
request transport, post-search/output work, and reader scheduling; it does not
isolate transport latency. The controls also do not exercise the match runner
directly: its correction is covered separately by the deterministic parser and
existing fake-UCI integration/audit tests.

## Remaining operational gap

The repair removes processing bias only after a callback begins. The coordinated
runner still shares one event loop among four shards. Synchronous protocol-log
writes/flushes, PGN generation, game-journal and summary persistence, and resource
observations can delay a later callback in any shard. The existing resource
monitor checks coarse admission/liveness, not sub-20 ms scheduling latency.

These are code-backed risks, not established causes of the 13 Phase 3G losses.
Raw historical logs contain neither byte-batch boundaries nor engine-emission
times, so no defensible corrected score can be calculated. All six candidate
and seven baseline losses remain scored; Phase 3G still fails its operational
gate. LMR stays off, classic timing/MVV-LVA remain defaults, and overhead stays
20 ms. A larger reserve would reduce available search time and cannot protect
against an unbounded pause; this phase supplies no basis for adopting one.

**Next: Phase 3J**, isolate match persistence from timed protocol callbacks and
validate failure handling and receipt timing under a controlled slow writer.
Keep any queue bounded and propagate disk failures without losing evidence.
A small, predeclared operational check can then gate fresh strength testing;
there is no requirement to prove immunity to arbitrary OS suspension. No match,
overnight job, or recurring schedule was started here.

## Validation and preservation

`make test-match test-qualification test-phase3g test-clock-probes` passed
212 checks across eleven test invocations. Expected CLI refusal messages in
negative tests are retained in the successful log. The receipt tool validates
legal PVs/bestmoves, binds the measured reply to validated output, checks timing
order and budgets, preserves interrupted intervention metadata, resumes its
owned child, refuses output overwrite, and stops on failure without retry.

No C++ source changed, no engine rebuild was needed, and no new native/scalar/
sanitizer or NNUE oracle run is claimed. The normal release and frozen Phase 3H
executable remain byte-identical. Stable GUI bundles `0.1-dev-4b8b35d` and
`0.1-dev-phase3f-20261017`, the pinned network, and the README introduction are
unchanged. Work was local within the normal 50% daytime resource budget; live
controls had one active search worker and no concurrent build or match.

Keep the complete ignored `results/phase3i-20261018/` directory. Its pre-probe
manifest pins the tested inputs; `protocol.md` is the plan frozen before live
controls. Reproduction commands are in the
[receipt diagnostic guide](../MATCHES.md#response-timing-diagnostics).

| Evidence or asset | SHA-256 |
| --- | --- |
| Unchanged final Phase 3H executable | `26849eb4a443c31a89fddb48aeffa9dc9e3998895043d95c9ed4409716564878` |
| Old runner source, also used in Phase 3G | `08722176098cd89f7eb252871ab2b3f7711bfe7a16e9efa6cebe8d670570a5da` |
| Repaired runner source | `42709f80f89fc98d976898e0a666dd0cd5a8a893c9454a57c3626a25f3ba2f10` |
| `same-batch-before.json` | `04620f4b60d9be866abd403c9d246514dea845a2e1e161cfc2d9515b7f508565` |
| `same-batch-after.json` | `7721e18411d7873e2b680532f924a980c0fb0c7d07c8bcf6cbb2c3535f615794` |
| `receipt-controls.jsonl` | `246e70346e7f4f1a9f575b7896d460a8f8bb12dceccc86a9f57652337bf97fbf` |
| `integration-tests.log` | `0d8e545ee5643a4d4aefd8118a0df2534c6044b087b36bc7325faf5b151671f5` |
| `pre-probe-manifest.json` | `9ef0ab6c4f55ad99dd85b3b0d95ca98f1accb2b30de313cafaa39b281c469a69` |
| Frozen `protocol.md` | `07f0b40fbda904c8694aec0d539756e31366714900e8fa6e114de61bbfdb5b2f` |
