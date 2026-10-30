# Phase 4F.15: legal null-verification ordering

Declared October 30, 2026, before the work screen. Parent:
`19ddf06c59bf2c3875414f33503f85bc959313ea`. This is one independently authored
ordering hypothesis within the existing opt-in verified null-move experiment.
It does not promote null pruning, change the accepted LMR-on baseline, or start
a game qualification. The owner reports LM Studio running; elapsed time and NPS
are retained raw observations only, with no performance or strength inference.

## Single hypothesis

At an eligible ordinary node, the existing contextual TT lookup may have copied
a move without providing a usable cutoff. Reuse that move **only at the root of
the legal verification search**, after an exact match in that root's legal move
list (including promotion and flags). Pass the move by value, never a score,
bound or depth. Descendant calls omit this argument. This does not use the
separate position-only `TT Move Hints` option.

All original eligibility and static-score guards, depth-minus-three fictional
probe and depth-minus-two legal verification remain unchanged. Neither subtree
may read/write TT bounds, probe tablebases, apply LMR or other speculative
pruning, or learn ordering. The fictional subtree receives no new hint. Real
history/draw rules and discarded speculative PVs retain their existing behavior.
The ordinary caller's prior TT read is the sole source of the move.

This may reduce verification work; the earlier warm-search regression does not
prove its cause. That historical screen had LMR off. Changing fail-soft move
order can change whether verification first returns an ordinary or special-band
score, hence the enclosing cutoff decision. Finite parity is not a proof of
strength preservation. No eligibility-veto or reduction retuning is included.

## Correctness checkpoint

Preserve the stable GUI `build/test-baselines/0.1-dev-4b8b35d/`, normal release,
previous campaign binaries/evidence and exact README introduction. Build parent,
candidate, scalar and sanitizer checks only under `build/experiments/phase4f15/`.
Use at most two compiler jobs and one test executable at a time; tests with
four internal workers stay within the host's recorded resource ceiling.

Run relevant null-state, policy, direct API and independent-referee UCI checks,
including both colors, sparse/zugzwang-risk positions, checks, promotions,
castling, en passant, rule-50/repetition/mate, stop/pondering and helper joins.
Extend diagnostics to count fictional-probe nodes, legal-verification nodes and
verification roots receiving an exact legal hint. Counts include interrupted
work, are worker-local and aggregate after joins; disabled diagnostics stay zero.
Check actual hint activity with LMR on, diagnostics parity, policy reset and
interruption inside hinted verification followed by exact fresh-default reuse.
Independent source review checks no hint propagation or speculative TT access.

## Fixed work screen

- Parent binary, built before edits with the native release compiler:
  SHA-256 `c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d`.
- Network: `networks/nn-1a298aa575a0.nnue`, SHA-256
  `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`.
- Exactly the three exposed full-history `tools/bench.py` roots, newline-joined
  text with trailing newline SHA-256
  `7db7d651ff73d29ee9fd63e3a9cb27c8a5b16fd1894763df167ecef23fa8a38b`.
  This narrow opening-only mechanism screen does not represent all chess;
  the separate correctness corpus exercises other position classes.
- Depth 6, Threads 1, Hash 64 MiB, classic time policy, overhead 20 ms, LMR on,
  MVV-LVA capture ordering, pondering/tablebases/other experiments off.
  Diagnostics on for work counters, never timing interpretation.
- First parent/null-off versus candidate/null-off: three roots, cold/warm,
  12 searches, exact completed iteration/final signatures required before the
  next stage. Then parent/null-on versus candidate/null-on: another 12 searches.
  Report candidate-on against candidate-off as descriptive context using those
  existing cells; launch no additional searches.
- Each role/root gets a fresh process, `ucinewgame`, cold search then immediate
  warm repeat. Alternate role order by root (listed order for 1/3, reverse for 2).
  Total **24 searches, 12 processes, one repetition**, no discarded warmups.
- One resident/searching engine; no concurrent builds or development tests.
  Check normal resource policy before each search. This is admission accounting,
  not continuous measurement of LM Studio or a hard OS utilization cap.
- Each search has 60 seconds; whole screen 600 seconds including setup.
  Stop on failure, preserve partial evidence and do not replace/extend cells.

Freeze candidate binary, protocol, corpus and tool/source digests before play;
verify them afterward. Use an exclusively created result, saving raw commands,
responses, per-cell counters, resource admission and clean exit/OS cleanup.
Independent `chess==1.11.2` replays every PV, bestmove and ponder. Report all
per-iteration score/PV changes and separate cold/warm node totals, not just an
aggregate favorable ratio. The parent has no new per-subtree node counters;
do not invent historical values or compare unequal counter definitions.

One finite candidate decision follows this sample, without retuning. A useful
mechanism result can justify later controlled timing/tactical work in a fresh
quiet window; game qualification additionally needs resolved clock readiness.
No Elo gain, default promotion, new game or automatic schedule follows here.

## Reproduce

After correctness and review, supply the newly frozen candidate digest:

```sh
python3 tools/run.py --offline tools/profile_null_verification.py \
  build/experiments/phase4f15/parent/chess0live \
  build/experiments/phase4f15/candidate/chess0live \
  --parent-sha256 c6a60936a2a0d36ec5de85afc319eeb99b62cddb04ec9f35eebeba695c3e801d \
  --candidate-sha256 CANDIDATE_SHA256 \
  --host-load lm-studio-running \
  --output results/NEW-null-verification-work.json
```

This command is for an expressly authorized new record, not a retry of the
completed sample. Engine-free profiler checks run through
`python3 tools/run.py --offline tests/profile_null_verification_test.py`.
