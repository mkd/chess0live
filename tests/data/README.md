# Original test suites

These short legal move sequences were selected for this project; they were not
extracted from the owner's earlier engines, an existing comparison, or a game
database. Each entry starts at the standard initial position and retains its
move history. The files and their selection are GPL-3.0-or-later, copyright
2026 Claudio M. Camacho <claudiomkd@gmail.com>.

- `openings-development.json`: 12 positions for developing the experiment tools
  and exploratory search comparisons.
- `openings-validation.json`: 12 different positions reserved for validation of
  a frozen candidate. Do not use its results to tune that candidate.
- `openings-time-validation.json`: 32 newly selected full-history lines for the
  first fixed-sample overnight classic/forecast comparison. All final board
  states are distinct and disjoint from the two earlier suites. The completed
  [time-policy screen](../../docs/reports/2026-10-15-phase2d-time-policy.md)
  exposed these roots; they are no longer fresh validation data.
- `openings-lmr-validation.json`: 64 fresh full histories selected for the
  completed [LMR screen](../../docs/reports/2026-10-16-phase2d-lmr.md). They are
  now exposed evidence too. Neither completed match suite should be extended
  or retuned as though its outcomes were unseen.
- `performance-gamephases.json`: 12 independently composed FEN roots, six
  middlegames and six endgames, for [Phase 3C](../../docs/PHASE_3C.md).
  These have no supplied game history and are not match openings. Structural
  coverage was chosen before engine evaluation or timing; metadata records
  selection reasons and composition limits. Keep them separate from strength
  validation and report every root in the frozen performance comparison.

The split is by selected line, not by opening family or statistical independence.
These small suites are starting fixtures, not a representative sample of all
chess or enough evidence for a world-leading-strength claim. A longer campaign
needs a broader, predeclared suite with recorded provenance. Reusing a position
with reversed colors creates one pair; those two games are not independent.
