# Experiment log

Record unsuccessful and inconclusive experiments as well as improvements.
Performance observations are not Elo estimates. Large raw records and experimental
binaries stay in ignored local output directories.

## 2026-10-13 — NNUE feature-buffer reuse: not retained

**Hypothesis:** retaining and swapping worker-local feature-list buffers would
avoid their repeated allocation/free and improve search throughput. The candidate
changed buffer ownership only; feature generation, integer arithmetic, inference,
and search rules remained unchanged. It added a second retained buffer per
perspective, with a modest memory cost.

**Baseline:** source snapshot `4b8b35d`, executable SHA-256
`5e2650fa3d9ff18ba836580bef942dec9223105e584da6853c3e0a81edc5330c`.
**Candidate:** executable SHA-256
`10b2163925be928eac631fe3cbd5ae875e6f32d428948e99109c887f9f703731`.
Both used Apple Clang 21, the generic macOS ARM64 release settings, the same
pinned SF19 network, one search worker, and 64 MiB hash.

The candidate passed native, scalar, and AddressSanitizer/UndefinedBehaviorSanitizer
suites. Its 2,057-position native/scalar/Stockfish oracle comparison matched every
recorded stage exactly. Additional dense/sparse/reset transitions passed. Code
review found no correctness or portability issue.

The first timing run used the three default development positions at depth 6,
seven measured repetitions per binary, and one warmup per position/binary.
Because its tiny effect was smaller than observed variation, one exploratory
follow-up used depth 7, three repetitions, and a 30-second per-search deadline.
Run order alternated; table clearing and readiness were excluded from timing.

| Run | Matching searches, including warmups | Median baseline/candidate ratio | Ratio median absolute deviation |
| --- | ---: | ---: | ---: |
| Depth 6 | 48 / 48 | 1.00310 | 0.00715 |
| Depth 7 | 24 / 24 | 1.00423 | 0.00341 |

Every sampled iteration matched depth, selective depth, nodes, score, and PV;
best moves and ponder moves also matched. The longer run completed without a
timeout; its longest search took 12.13 seconds. Variation differed substantially
by position, particularly in the queen-pawn opening.

**Decision:** not retained. These exploratory results did not establish a clear
throughput benefit, and no playing-strength test or Elo gain was claimed. The
original evaluator was restored. This does not prove buffer reuse is universally
unhelpful; reconsider only with a new hypothesis or stronger evidence.

Local evidence:

- `results/nnue-buffer-reuse-depth6.json`
- `results/nnue-buffer-reuse-depth7.json`
- `results/nnue-buffer-reuse-depth6-compare_bench.py` — exact earlier helper,
  hash-checked against its report before the timeout option was added.
- `results/nnue-buffer-reuse-experiment/` — candidate binary, source patch,
  candidate oracle report, and decision manifest.

The reports record the original rebuild path of the candidate. That path now
contains the restored baseline; use the archived candidate and verify its hash
when reproducing this comparison. The retained comparison helper and its tests
are described in [benchmarking](BENCHMARKING.md).
