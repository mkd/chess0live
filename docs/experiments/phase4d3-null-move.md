# Phase 4D.3: verified null-move search-work screen

Predeclared October 18, 2026, before this screen's searches. One restrictive,
independently implemented null-move candidate remains disabled by default.
This is a bounded development check, not held-out strength qualification.

Conceptual source: Omid David-Tabibi and Nathan S. Netanyahu,
[Verified Null-Move Pruning](https://arxiv.org/abs/0808.1125), *ICGA Journal*
25(3), 153–161, September 2002 (arXiv submission in 2008). chess0live's code is
independently authored. Its particular guards, isolation rules and fixed
reductions are not a claim of reproducing that paper's complete algorithm or
its experimental results.

## Fixed candidate

An interior non-PV node at depth at least five may consider a null probe only
outside check and mate/tablebase score windows. It needs at least two own
non-pawn, non-king pieces, one own pawn, eight total pieces, two legal moves,
a halfmove clock below 80, no earlier current-position repetition, and no pawn
of either color on its sixth or seventh rank. Static evaluation must reach beta.

The fictional-pass probe searches depth minus three. A completed ordinary-score
fail-high requires real-position verification at depth minus two and the same
ply. Both complete subtrees disable nested null pruning, LMR, TT reads/writes,
Syzygy probes, and ordering learning. Fake subtrees cannot manufacture a game
repetition or rule-50 draw; real verification retains those rules. A verified
cutoff returns beta, with no fictional PV or direct original-depth TT entry.
These safeguards do not prove safety against all zugzwangs or tactical misses.

## Fixed inputs and order

- Frozen parent SHA-256:
  `bda061408f4ff8339e2fc8f7d3536525373e8a790f7209a35418162928168f7f`.
- Network SHA-256:
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Exactly the three previously exposed full-history roots in `tools/bench.py`.
  Save their text and digest before play; no puzzle or held-out campaign roots.
  Their newline-joined UTF-8 text, including a trailing newline, has SHA-256
  `7db7d651ff73d29ee9fd63e3a9cb27c8a5b16fd1894763df167ecef23fa8a38b`.
- Depth 6, Threads 1, Hash 64 MiB, classic time policy, Move Overhead 20 ms;
  pondering, LMR, countermove ordering, tablebases, and diagnostics disabled;
  MVV-LVA capture ordering. Only the candidate-on role enables null pruning.
- Stage 1: frozen parent versus candidate-off. Stage 2: candidate-off versus
  candidate-on. Each stage has three roots, two roles and cold/warm conditions:
  **24 searches total**, one repetition, no discarded warmups.
- Alternate role order by root: listed order for roots 1/3, reversed for root 2.
  Each role/root gets a fresh process, `ucinewgame`, a cold search and its
  immediate warm repeat without clearing table or learned history.
- Every search must complete within 60 seconds; the complete tool has a
  600-second budget including setup. Do not replace or extend failed samples.

## Resource and evidence gates

Only one profile engine is resident and searching at a time. Reserve the active
Phase 4D.2 campaign's eight workers and 9,525,941,184 bytes in addition to the
profile worker and its conservative memory allocation. Recheck the current
Helsinki budget before each search. Other development tests must be idle.
This is workload admission, not an enforced CPU/memory utilization limit.

The independent pinned `chess==1.11.2` referee must accept all roots, PVs,
bestmoves and ponders. Require complete, ordered exact-score iterations,
zero tablebase hits, no diagnostics/errors, consistent final totals and clean
engine exit. Parent versus candidate-off must agree on every iteration's depth,
selective depth, nodes, score, PV and hash occupancy, plus final nodes, bestmove
and ponder. Failure stops before Stage 2.

Save raw observed protocol output, commands, resource admissions, all samples,
protocol text and before/after binary/network/source/corpus hashes to an
exclusively created output file. Existing evidence must never be overwritten.
Retain partial evidence and mark the screen invalid on interruption, protocol
failure, incomplete search, illegal move, parent mismatch or artifact drift.

Report candidate-off/on node counts separately for cold and warm searches, every
score/PV change, final moves and ponders. Do not retune on these results.
The concurrent campaign makes wall-clock comparisons unsuitable: raw timing/NPS
remain evidence only, with **no timing or speedup interpretation**. Node savings
and matching sampled decisions establish neither a strength gain nor no loss.
Keep the default off pending separately frozen playing-strength evidence.

## Reproduce

Run with the pinned parent and separately frozen candidate after correctness
checks, while no other development tests are active:

```sh
python3 tools/profile_null_move.py \
  build/experiments/phase4d2-20261018/chess0live \
  /absolute/path/to/frozen/candidate/chess0live \
  --output results/phase4d3-20261018/node-work.json
```

The candidate and all tool/protocol inputs are pinned in the result before the
first search and checked again afterward. The parent and network pins above
are enforced independently by the tool. No automatic schedule is created.
