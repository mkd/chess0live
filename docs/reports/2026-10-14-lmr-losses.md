# LMR loss diagnosis — October 14, 2026

This is post-hoc diagnosis of the four losses in the eight-game development
smoke, not a strength test or independent validation. No LMR-specific tactical
miss was reproduced in the selected roots. Reduced fail-lows remain unproven.

## Selection and controlled replay

For every loss, rank consecutive candidate-turn exact centipawn scores by the
drop between them, preferring a preceding score of at least -100 cp. Break ties
by earliest preceding ply; fall back to all finite exact scores only if needed.
No fallback was needed. Keep both the decision root and the next candidate-turn
witness with full history. The rule and selection were frozen before replay.

Sixteen searches compared LMR off/on at eight roots: 200,000 nodes each, classic
timing, one worker, 64 MiB hash, pinned network, fresh search state each time.
Executable: `build/experiments/lmr-20261014/chess0live`, SHA-256
`b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc`.
The owner's GUI snapshot `0.1-dev-4b8b35d` was not used or modified.

All eight off/on best moves agreed. Seven roots agreed on final depth, score
and PV; the remaining witness reached depth 5 off and 6 on with the same move.
All 40 comparisons at matching completed depths had identical scores and PVs.
Independent `chess==1.11.2` replay verified 16 best moves and 81 completed PVs
(305 PV plies). Node accounting and frozen input/tool hashes passed.

| Game | Selected decision | Original decision → witness score |
| --- | --- | ---: |
| p000002-1 | 11...Nbd7 | -5 → -593 cp |
| p000002-2 | 20.dxc5 | +272 → +50 cp |
| p000003-2 | 11.Ng3 | -3 → -56 cp |
| p000004-2 | 18.Kc2 | +20 → -58 cp |

## Sharpest collapse

Both modes reproduced `11...Nbd7` at depth 4 and -5 cp, with the original PV.
Both switched to `11...O-O` at depth 5 and -14 cp. The played continuation was
`11...Nbd7 12.Nxf7 Bd3 13.Nxd8 Bxe2 14.Nxe2 Kxd8 15.Bxe6`; it is not proved
forced. The shallow choice is shared by both modes. This evidence does not
attribute the loss to LMR, prove castling saves the game, or reproduce the
original warm hash/history and clock-managed search exactly.

**Decision:** end this bounded investigation without changing LMR. Further
searches of these roots would remain development analysis, not a replacement
for the separate strength gate. Capture ordering proceeds independently.

## Reproduction and evidence

The full selected histories below reproduce the node-limited roots with
`tools/profile_lmr.py --nodes 200000 --repeats 1 --position-limit 0` and the
frozen executable/network. Put them in the documented opening JSON format
(`id` and `moves`) and choose a fresh output path. They are diagnostic
development positions and must never be relabeled held out.

p000002-1 decision:

```text
startpos moves e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6 g1f3 e7e6 f3e5 g6h7 f1c4 g8f6 d1e2 f8e7 c2c3
```

p000002-1 witness:

```text
startpos moves e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 h2h4 h7h6 g1f3 e7e6 f3e5 g6h7 f1c4 g8f6 d1e2 f8e7 c2c3 b8d7 e5f7
```

p000002-2 decision:

```text
startpos moves e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 g1f3 b8d7 h2h4 h7h6 h4h5 g6h7 f1d3 h7d3 d1d3 e7e6 c1d2 g8f6 e1c1 d8c7 g3e4 f6e4 d3e4 d7f6 e4e2 a8d8 c1b1 f8d6 f3e5 c6c5 e2b5 e8f8 d2a5 b7b6
```

p000002-2 witness:

```text
startpos moves e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5 e4g3 f5g6 g1f3 b8d7 h2h4 h7h6 h4h5 g6h7 f1d3 h7d3 d1d3 e7e6 c1d2 g8f6 e1c1 d8c7 g3e4 f6e4 d3e4 d7f6 e4e2 a8d8 c1b1 f8d6 f3e5 c6c5 e2b5 e8f8 d2a5 b7b6 d4c5 d6e5
```

p000003-2 decision:

```text
startpos moves e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5 d4e2 c8e6 f2f4 g7g6 f4f5 g6f5 e4f5 e6f5
```

p000003-2 witness:

```text
startpos moves e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5 d4e2 c8e6 f2f4 g7g6 f4f5 g6f5 e4f5 e6f5 e2g3 f5e6
```

p000004-2 decision:

```text
startpos moves d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 f1e2 e7e5 d4d5 b8d7 c1e3 d7c5 f2f3 f6h5 d1d2 d8h4 e1d1 f7f5 g1h3 h5f4 h3f4 e5f4 e3f4 e8g8 e4e5 d6e5 f4e3 b7b6 b2b4 c5b7 e3g5 h4f2
```

p000004-2 witness:

```text
startpos moves d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6 f1e2 e7e5 d4d5 b8d7 c1e3 d7c5 f2f3 f6h5 d1d2 d8h4 e1d1 f7f5 g1h3 h5f4 h3f4 e5f4 e3f4 e8g8 e4e5 d6e5 f4e3 b7b6 b2b4 c5b7 e3g5 h4f2 d1c2 a7a5
```

Local evidence: `results/lmr-loss-forensics-20261014/` contains the frozen
selection, manifest, roots, replay, and independent audit. Audit SHA-256:
`62c8de2e3eacdcba19e4210f622a2ef61fb2396f9d5805c139e1d6180dc96869`.
