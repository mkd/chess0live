# Opening suites

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
  states are distinct and disjoint from the two existing suites. They have not
  been used for candidate tuning or a match; preserve that distinction until
  the [planned campaign](../../docs/TIME_MANAGEMENT.md) is run. The file records
  its original selection provenance and limitations.

The split is by selected line, not by opening family or statistical independence.
These small suites are starting fixtures, not a representative sample of all
chess or enough evidence for a world-leading-strength claim. A longer campaign
needs a broader, predeclared suite with recorded provenance. Reusing a position
with reversed colors creates one pair; those two games are not independent.
