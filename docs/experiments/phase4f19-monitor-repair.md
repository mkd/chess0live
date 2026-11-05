# Phase 4F.19 — host-log repair before measurement

Declared November 4, 2026, before any search observation. The owner's latest
instruction is “go ahead with the next step,” following the first prelaunch stop.
The intended work remains the [fixed three-profile comparison](phase4f19-combinations.md).

The first attempt stopped on Battery Power at 22:30:54 Helsinki, with zero
engines. After the owner's new instruction, AC/Automatic mode was observed.
The second process attempt stopped at 22:54:15 before launching its runner:
macOS assertion/log output contained a byte invalid in UTF-8. Both failed
attempts and audits remain preserved. Neither produced a search or profile result.

Complete the authorized comparison after a narrow monitor repair. Add a helper
that captures command output as bytes, preserves those bytes, and writes an
escaped UTF-8 view for human inspection and ASCII timestamp/event parsing.
Nonzero commands and timeouts still fail visibly. Test invalid bytes, event
selection, raw preservation and command failures before freezing the repaired
helper and supervisor. Keep the old supervisor/helper files unchanged.

Use `results/phase4f19-combinations-20261104-attempt3/` for the repaired attempt.
Freeze the new helper/tests, supervisor and this addendum along with all original
inputs. Verify the two previous evidence directories remain unchanged. Perform
a read-only live host-log collection before launch to confirm the decoding fix.

No engine, producer, auditor, network, corpus, option, ordering or search-budget
change is permitted. The original 45 fresh serial searches remain fixed:
15 roots, rotated optional-off/default/all-on, 5,000 ms each, Threads 1, Hash 64,
minimum 2 GiB reservation. There is no replacement of measured cells, extra
warmup, extension, tuning or game campaign. The original host/deadline/cleanup
rules and diagnostic-only interpretation still apply. Record this repair and
both prelaunch failures with the final outcome. Stop and preserve evidence if
the repaired measurement fails; no subsequent automatic attempt is authorized.

The latest instruction authorizes completing this comparison and the necessary
monitor repair. It does not authorize later component-removal measurements,
default promotion, GitHub publishing or a future schedule.
