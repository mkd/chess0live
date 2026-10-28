# Phase 4F.9 preparation — October 28, 2026

The isolated Continuation History tactical comparison is prepared and its
readiness/smoke evidence passes independent audit. The full 60-second comparison
has not started. No engine default, search implementation or release changed.

## Frozen comparison

The [predeclared protocol](../experiments/phase4f9.md) compares
`continuation-off` against `continuation-on`, with eight threads, 64 MiB Hash,
LMR enabled and TT Move Hints plus the other experimental options disabled.
Both roles use the exact same tested Phase 4F.8 executable, copied without
rebuilding from source revision `69215b4c7a35bb0ba7ea4b1e9287e8f760199b6c`.

Executable: `build/experiments/phase4f9/chess0live`, SHA-256
`c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`.
All 27 preserved source/Makefile/Fathom files match the original build manifest
and that Git revision. The adjacent normalized manifest retains original build
provenance; `tests/data/phase4f9-pins.json` freezes 51 inputs, with the pins file
itself bringing the audited inventory to 52. This is a local frozen experiment
bundle; large binaries/networks and raw results remain outside Git.

The new direct-entry runner prepares optional Python dependencies automatically.
Its separate auditor imports neither the runner nor its parser/summary and
reconstructs settings, process lifecycle, receipt clocks and legal chess output
from raw transcripts. Each attempt and audit requires a fresh output path.

## Validation completed

| Check | Result |
| --- | --- |
| Runner synthetic cases | 40 passed |
| Independent-auditor synthetic cases | 31 passed |
| Real search-free readiness | 2 sessions, both clean exits; 21 advertised options |
| Readiness audit | Passed, 52 inputs and 50 commands checked |
| One-second smoke | All 39 positions × 2 roles completed, 78 clean exits |
| Independent smoke replay | Passed, 528 PVs / 3,412 legal plies |
| Best/ponder replay | All legal, 156 plies |
| Resource observations in smoke | 313 accepted |
| Final move agreement in smoke | 39/39 positions |
| Positive mate reports in smoke | 0 for each role |

Evidence directory: `results/phase4f9-preparation-20261028/`.
Readiness report SHA-256:
`89fa5b19e8c7000ad981ec0dae286c6547d41548ff40067b82390dc0ab6bd972`.
Smoke report SHA-256:
`3dad91359e3d94848cb5316b22a5a9aa2fcae37c2f6ea3ef619c7936a03711d7`.
Audits are saved outside each attempt as `readiness-audit.json` and
`smoke-audit.json`; raw command/response and cleanup records remain in each
attempt directory. Test output is retained in `runner-tests.log` and
`auditor-tests.log`. `validation-index.json` records the evidence identities.

Commands used through the dependency launcher:

```sh
python3 tools/run.py --offline tests/phase4f9_puzzles_test.py
python3 tools/run.py --offline tests/audit_phase4f9_puzzles_test.py
python3 tools/run.py --offline tools/check_phase4f9_puzzles.py --mode check --output results/phase4f9-preparation-20261028/readiness
python3 tools/run.py --offline tools/audit_phase4f9_puzzles.py results/phase4f9-preparation-20261028/readiness/report.json --output results/phase4f9-preparation-20261028/readiness-audit.json
python3 tools/run.py --offline tools/check_phase4f9_puzzles.py --mode smoke --output results/phase4f9-preparation-20261028/smoke
python3 tools/run.py --offline tools/audit_phase4f9_puzzles.py results/phase4f9-preparation-20261028/smoke/report.json --output results/phase4f9-preparation-20261028/smoke-audit.json
```

No previous engine tests were repeated: no engine code changed, and Phase 4F.8
already records its native/sanitizer checks. No benchmark or match ran alongside
the smoke. The admission record allows nine workers on this 18-CPU, 64-GiB Mac;
the smoke requested eight and reserved 2 GiB. Those are admission estimates,
not measured hard utilization/memory caps. No quiet-host claim is made for this
short operational check, and it establishes no speed or strength result.

## Reporting limitation found before the full run

The protocol refers to supplied best moves and their match accuracy. The frozen
corpus and original literal owner list actually contain only FENs, supplied mate
distances and spreadsheet row numbers. **Supplied-best-move matches are
unavailable.** Treat those protocol metrics as not applicable; do not infer an
answer from either engine, add annotations or change the frozen corpus.
All paired actual moves, final scores, mate-report gains/losses, supplied mate
distances and legal PV endings remain reportable. This clarification changes
no treatment, membership, time budget or search input and is recorded before
the full run.

## Next checkpoint

Obtain a fresh quiet-window confirmation and daytime exception if applicable,
then run the fixed 78 × 60-second attempt, about 78 minutes plus setup. Pause
LM Studio inference and keep AC power/Automatic mode unchanged. No schedule,
retry, full run or match was started by this preparation. Independently audit
the full result and report every adverse observation before deciding whether
a separate paired-game test is warranted. Continuation History remains off;
the older TT Move Hints and combined-policy promotions remain parked.

Normal release binaries, stable GUI snapshot `0.1-dev-4b8b35d`, owner batch
settings and prior experiment evidence are preserved. The README introduction
is byte-identical; only practical tooling instructions were added below it.
