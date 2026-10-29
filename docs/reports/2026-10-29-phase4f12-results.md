# Phase 4F.12 — NNUE equal-time tactical results

Date: October 29, 2026. Preparation commit: `f15d003`.
Decision: **operational audit passed; no additional mate reports were observed**.
Both binaries reported the same three mates and chose the same 39 final moves.
This completes the tactical checkpoint, without establishing a strength gain,
equivalence, universal nonregression or a release gate.

## Attempt and independent audit

The owner replied “Ready, go ahead!” to the explicit full-run permission request,
confirming paused LM Studio inference, AC power, Automatic mode, an awake Mac and
a daytime exception. One attempt ran **21:58:31–23:16:42 Helsinki**, taking
**78 minutes 10.6 seconds**, under `phase4f12-daytime-20261029`. No retry,
resumption, replacement or automatic schedule was used.

The unchanged [protocol](../experiments/phase4f12.md) compared baseline source
`1ca87d6` with the accepted affected-feature NNUE source `3ee5eff`, using the
already tested frozen binaries. All 39 positions received 60 seconds per binary,
eight search workers, Hash=64 MiB and identical options; role order alternated,
with a fresh process and cold state for every search. LMR was on, TT Move Hints
and Continuation History off, and tablebases disabled. One resident engine and
eight workers reserved 2 GiB throughout. Admission changed from the ordinary
daytime 9-worker allowance to the nighttime 14-worker allowance at 23:00; actual
requested workers stayed at eight. Reservations are not utilization telemetry.

The independent auditor, invoked through `tools/run.py --offline`, passed:

- **78 searches / 39 complete pairs**, all 78 pinned inputs unchanged.
- 78 distinct recorded process IDs, all exit codes zero, one EOF per session and finished
  readers; no failed searches, exclusions or launcher stderr output.
- 823 completed analysis iterations, 7,584 legal PV plies and 156 legal
  best/ponder plies; 2,184 commands, 3,163 output lines and 234 readiness barriers.
- 2,545 resource observations; maximum gap 2.082915 seconds and clock drift
  0.008109 seconds, within the five-second limits. The longest measured search
  receipt interval was 59.982913 seconds, within the separate overrun boundary.

The launcher exited zero. A separate OS snapshot after exit found no remaining
comparison engine, runner or sleep inhibitor. The owner was immediately told
that **LM Studio inference could resume**. The earlier 87 synthetic checks and
readiness/smoke audits remain applicable; they were not redundantly rerun for this
unchanged implementation and documentation-only closeout.

## Observed results and adverse differences

Both roles reported positive mates on **3/39 positions**: position 1, mate in 7;
position 2, mate in 7; and position 15, mate in 9. All three final distances match
the supplied annotations, and all three final PVs end in checkmate under legal
replay. There were **zero gained or lost positive mate reports**, and all
**39/39 final best moves match**. The other 36 positions produced no positive
mate report during any completed iteration.

Candidate completed depth was one greater on positions 29 and 31, one lower on
position 1, and equal on 36 positions. Scores differ only on positions 3, 10,
29 and 31. Position 10's candidate score is 38 cp lower; these evaluation
differences do not by themselves establish correctness or tactical regression.
The table below retains all final observations, including those unfavorable to
the candidate. Scores are from the side to move; `M` is an engine mate claim.

| Position | Best move, both | Baseline score | Depth | Candidate score | Depth |
| --- | --- | --- | --- | --- | --- |
| 01 | f5f6 | M7 | 11 | M7 | 10 |
| 02 | f4f3 | M7 | 14 | M7 | 14 |
| 03 | d6c4 | +702 cp | 10 | +706 cp | 10 |
| 04 | f3g5 | +1820 cp | 10 | +1820 cp | 10 |
| 05 | h7h6 | +1582 cp | 10 | +1582 cp | 10 |
| 06 | c6e7 | +1673 cp | 10 | +1673 cp | 10 |
| 07 | d8d2 | +1491 cp | 10 | +1491 cp | 10 |
| 08 | f7g7 | +1832 cp | 11 | +1832 cp | 11 |
| 09 | a7e3 | +1707 cp | 9 | +1707 cp | 9 |
| 10 | c1c7 | +2182 cp | 12 | +2144 cp | 12 |
| 11 | e4c3 | +1599 cp | 9 | +1599 cp | 9 |
| 12 | c1h6 | +1407 cp | 11 | +1407 cp | 11 |
| 13 | e6e1 | +1662 cp | 10 | +1662 cp | 10 |
| 14 | c3c2 | +1702 cp | 10 | +1702 cp | 10 |
| 15 | e7d7 | M9 | 11 | M9 | 11 |
| 16 | g3f2 | +1639 cp | 10 | +1639 cp | 10 |
| 17 | f3h5 | +1481 cp | 9 | +1481 cp | 9 |
| 18 | h5h4 | +1727 cp | 11 | +1727 cp | 11 |
| 19 | h5g6 | +1213 cp | 10 | +1213 cp | 10 |
| 20 | d6d1 | +845 cp | 10 | +845 cp | 10 |
| 21 | d1h5 | +1927 cp | 11 | +1927 cp | 11 |
| 22 | d1d4 | +1114 cp | 11 | +1114 cp | 11 |
| 23 | e3e5 | +1436 cp | 10 | +1436 cp | 10 |
| 24 | g5h6 | +1633 cp | 11 | +1633 cp | 11 |
| 25 | g2d5 | +1421 cp | 10 | +1421 cp | 10 |
| 26 | d1h5 | +1809 cp | 10 | +1809 cp | 10 |
| 27 | e4d6 | +1436 cp | 11 | +1436 cp | 11 |
| 28 | e1e4 | +1774 cp | 10 | +1774 cp | 10 |
| 29 | d1h5 | +1014 cp | 9 | +1134 cp | 10 |
| 30 | g5g3 | +1290 cp | 9 | +1290 cp | 9 |
| 31 | g3h3 | +1467 cp | 9 | +1587 cp | 10 |
| 32 | g8g4 | +1278 cp | 10 | +1278 cp | 10 |
| 33 | f5h3 | +1255 cp | 12 | +1255 cp | 12 |
| 34 | e6g7 | +1278 cp | 10 | +1278 cp | 10 |
| 35 | h3b3 | +943 cp | 10 | +943 cp | 10 |
| 36 | d3h3 | -275 cp | 11 | -275 cp | 11 |
| 37 | b6d4 | +107 cp | 11 | +107 cp | 11 |
| 38 | g8g5 | +642 cp | 15 | +642 cp | 15 |
| 39 | h5h7 | +289 cp | 13 | +289 cp | 13 |

The first positive mate report was **later for the candidate on all three
positions**. These are engine-reported iteration times, not independently timed
proof-completion times. Position 1 first reported M9 before reaching final M7.

| Position | First reported mate | Baseline first report | Candidate first report | Candidate delay |
| --- | --- | --- | --- | --- |
| 01 | M9 | 11.303 s | 12.806 s | +1.503 s |
| 02 | M7 | 5.788 s | 10.794 s | +5.006 s |
| 15 | M9 | 34.673 s | 35.297 s | +0.624 s |

Position 1 first matched its supplied M7 at 28.513 seconds baseline versus
32.389 seconds candidate, a 3.876-second delay. For positions 2 and 15, the
first positive reports already matched the supplied distance. These adverse
timings remain part of the result; no post-hoc rerun was used to replace them.

## Interpretation, preservation and next checkpoint

The earlier roughly 5% equal-work execution improvement **did not produce an
extra mate report in this attempt**. Single eight-worker searches are
nondeterministic; the corpus is exposed, not held out or repeatedly sampled.
The supplied labels are mate distances, not expected best moves, so best-move
accuracy cannot be calculated. A legal mating PV alone does not prove a forced
mate against every defense. Neither centipawns, depth nor node counts establish
Elo, and this comparison does not establish eight-thread speedup or equivalence.

All raw evidence is retained in `results/phase4f12-full-20261029/`. The external
audit is `results/phase4f12-full-20261029-audit.json`, SHA-256
`18869298dfefa29653e811f76047bf9b7c808b5974874846b3bdd74a875f0a8d`.
Report SHA-256:
`00b016aade30aff45aa1f69d218600d3f990ad8f103697467b453d46f00d80eb`.
Authorization, launch/exit records, stdout/stderr, OS cleanup and closeout
validation live in `results/phase4f12-full-20261029-launch/`. Never overwrite the
attempt or audit. The protocol, pins, binaries, network, prior campaigns, owner
batch settings, README introduction and stable GUI `0.1-dev-4b8b35d` are preserved.
The normal release's pre-existing provenance gap remains as recorded in the
[preparation report](2026-10-29-phase4f12-preparation.md); it was not used here.

Next is a **separate prospective paired game qualification**, designed to assess
modest gains with explicit uncertainty and feasible local resources. Freeze its
sample, settings, stopping rules and decision criteria before play; a new long
run needs its own agreed window. Do not pool previous option experiments or infer
strength from this tactical pass. No new engine/default promotion, game launch,
schedule, release or GitHub push follows automatically.
