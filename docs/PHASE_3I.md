# Phase 3I: response timing and receiver-delay diagnosis

Started October 18, 2026 from `4a2eff1`. Phase 3H fixed command-time accounting;
its isolated probes did not reproduce the original match losses. This phase
separates measurable receiver processing from engine response delay before
considering a reserve or allocation change.

## Bounded hypothesis and scope

Inspection found that the match runner timestamps decoded lines individually,
then logs each one synchronously. If an `info` line and `bestmove` are already
in the same input callback, logging the first line can inflate the charged time
of the second. A deterministic pre-change reproduction is preserved in
`results/phase3i-20261018/same-batch-before.json`: a complete reply received at
50 ms is charged 250 ms after 200 ms of simulated logging, falsely exceeding a
100 ms clock. This demonstrates a measurement defect, not its incidence in
Phase 3G. Historical logs lack callback boundaries and cannot be corrected.

Retain the pinned Python chess parser. Timestamp each delivered byte callback
once and collect its complete decoded lines, then record the whole input batch
before dispatching any line to the protocol. This must prevent both slow-logging
inflation and backward transcript timestamps when `readyok` synchronously sends
`position`/`go`. Split lines receive the timestamp of the callback supplying the
terminating newline. Preserve stderr, cancellation, and parser behavior.

The timestamp remains an asyncio callback observation. It cannot measure kernel
arrival or eliminate a receiver/process stall before callback delivery. No
engine behavior, UCI option, overhead default, allocation formula, historical
outcome, or strength gate changes in this phase. Do not launch a match or schedule.

## Checks fixed before live probes

1. Reproduce the defect before repair, then test slow same-batch logging, split
   lines, reentrant commands, stderr, and exception cleanup. Run match and
   qualification/audit regressions with the small fake processes they already use.
2. Add a bounded receipt-diagnostic tool with failure preservation, legal-PV
   validation, input hashes, and cleanup. Test it before live use.
3. Run exactly 12 sequential searches on the frozen final Phase 3H executable:
   startpos, `go movetime 620`, overhead 20 ms, Threads=1, Hash=64 MiB, classic
   timing, MVV-LVA, diagnostics enabled; both LMR modes, two repetitions, three
   conditions: ordinary consumption; a 900 ms consumer sleep after sending go;
   and an engine-process pause from roughly 400 to 900 ms after go.
4. Timestamp receipt in the existing dedicated reader thread and consumption
   separately. A sleeping consumer releases Python's interpreter lock; this
   deliberately distinguishes that consumer from its reader. It is **not** an
   independent-process observer and does not isolate whole-process/GIL stalls.
   The process-pause control uses POSIX signals only, always resumes in cleanup,
   and must not be described as a portable engine feature.

Readiness and fresh process/table setup precede each clock. Retain every attempt;
no selective retry, tuning, or clock-forfeit reinterpretation is allowed. These
are exposed mechanism controls, not held-out play or a strength comparison.
Use one active search worker within the ordinary resource policy. A naturally
late control remains evidence, not a reason to replace it. Distinguish the
intentional pause duration from observed scheduling/timestamp values.

## Decision boundary

Retain a runner fix only if the deterministic regression passes and existing
protocol/audit behavior remains sound. Diagnostic controls should demonstrate
which delays each observation can distinguish, without claiming a historical
root cause. A larger reserve trades away search time and cannot guarantee
delivery during arbitrary suspension; do not silently adopt one. The next
checkpoint must name any remaining operational gap and a concrete bounded step
toward fresh strength qualification.
