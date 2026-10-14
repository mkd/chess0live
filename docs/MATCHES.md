# Local paired-opening experiments

The match runner is an independent development tool, separate from the shipped
engine. It uses the GPL-licensed [python-chess project](https://github.com/niklasf/python-chess)
for rules, UCI communication, and PGN output. Install its pinned importable
package in a local virtual environment:

```sh
python3 -m venv .local/match-venv
.local/match-venv/bin/python -m pip install -r requirements-match.txt
make PYTHON=.local/match-venv/bin/python test-match verify-moves
```

Do not run an experiment while compiling or benchmarking on the same machine.
Prepare both binaries and networks before starting the clocks. Record an
explicit hypothesis, both source revisions, and the planned sample size. Use
the development suite for exploration; reserve the validation suite for a
frozen candidate. Never tune repeatedly against a held-out suite and continue
calling it held out.

## Run a match

Each selected opening is played twice with colors reversed. `--pairs` counts
openings, not games. The seeded ordering and first color make the schedule
reproducible. Use a new output directory for every run.

Optional `--candidate-revision` and `--opponent-revision` flags attach source
labels. Those labels are not automatically verified against a binary; preserve
build records as well as the automatically calculated file hashes.

```sh
.local/match-venv/bin/python tools/match.py \
  --candidate build/macos-arm64-generic-release/chess0live \
  --opponent /absolute/path/to/opponent \
  --candidate-network networks/nn-1a298aa575a0.nnue \
  --opponent-network /absolute/path/to/opponent.nnue \
  --openings tests/data/openings-development.json \
  --pairs 12 --seed 20261013 --initial 60 --increment 0.6 \
  --threads 1 --hash-mb 64 --output results/development-60-plus-0.6
```

The example is a configuration, not a recorded strength result. Run long
experiments overnight (23:00–07:00 Europe/Helsinki). Short tool checks can use
`--smoke --pairs 1 --initial 1 --increment 0.01 --max-plies 80`; this deliberately
small run tests the runner and never establishes playing strength. Consult
`python3 tools/match.py --help` for all options.

Both engines receive equal thread and hash settings, explicit network paths,
and no pondering. Only one game runs at a time. The resource policy is read
between games; lowering the manual budget does not pause an engine mid-clock.
See [the resource policy](../README.md#local-resource-policy). The runner cannot
isolate other applications, pin Apple performance cores, or enforce a hard OS
utilization ceiling. Record unusual system load and do not interpret one noisy
short run as a search improvement.

To compare an experimental setting with its baseline in the same executable,
pass repeatable `--candidate-option 'NAME=VALUE'` and
`--opponent-option 'NAME=VALUE'` arguments. For example:

```sh
--candidate-option 'Time Policy=forecast' --opponent-option 'Time Policy=classic'
```

Each option must be advertised by its engine and match its declared type/range.
Options cannot override the common thread/hash/network/overhead configuration,
books, tablebases, playing-strength controls, diagnostics, or protocol-managed
settings. Search diagnostics are disabled when advertised so profiling output
does not distort a strength comparison. Requested experiment options are frozen
in `run.json`; actual applied options appear in each game record and protocol
log. A requested option unsupported by a frozen older executable is a setup
failure, not a silently ignored experiment.

The opening files contain complete move sequences, so the engines and the
referee retain repetition history. A custom FEN cannot recover moves before
that FEN. Our [initial suites](../tests/data/README.md) are small original
fixtures; they are not a calibrated rating pool or broad opening database.

## Interpret the result

Keep the JSON records and PGNs together. The record identifies binaries,
networks, inputs, options, seed, clocks, platform, and resource policy. Clock
time runs from the outgoing UCI `go` to the incoming `bestmove`, including
communication overhead. Readiness and new-game preparation occur before the
clock starts. Increment is credited after a move that completes within its clock.

`run.json` freezes the configuration; `games.jsonl` records finished or interrupted
games; `summary.json` describes complete pairs and exclusions. Each game also
has its own PGN and raw protocol log. Copy the entire output directory when
archiving evidence. The runner never overwrites an existing experiment.

The referee automatically claims an available threefold/rule-50 draw for either
side. It uses no evaluation-based adjudication. On a clock loss, its material
test can recognize many positions in which the other side cannot mate, but is
not a general proof of whether a cooperative mating sequence exists; the exact
referee rule is recorded in the manifest.

Report protocol failures, crashes, illegal moves, clock losses, and truncated
games explicitly. Clock forfeits count in match results because time management
affects strength. A ply limit is an incomplete game, not a draw. A failed or
incomplete pair does not silently become a normal two-game sample; operational
failures prevent strength inference rather than allowing a favorable subset to
hide them. Inspect failure reasons before comparing search quality.

Uncertainty is calculated using two-game pair scores. It does not pretend the
two color-reversed games are independent. The conservative bounded-score
interval assumes independent outcomes between pairs and describes the tested
conditions and suite. A score-to-Elo transformation is a relative model-based
summary, not an absolute rating. Extreme scores and small samples can produce
unbounded intervals; more games are required, not a larger marketing claim.
The tooling withholds intervals until at least 30 unique complete pairs finish
without exclusions. Thus the included 12-opening fixtures yield descriptive
results only. Thirty is a conservative reporting policy, not a guarantee of
adequate statistical power. A meaningful campaign generally needs many more.

Choose the number of pairs before inspecting scores. The runner does not
implement SPRT or authorize stopping as soon as a confidence interval becomes
favorable. Report exploratory experiments as exploratory. See
[validation](VALIDATION.md) for release and strength-claim requirements.

## Freeze a comparison baseline

Preserve a known binary outside the rebuild directory, together with its source
revision, compiler/flags, and network digest. Compare a changed candidate
against that frozen baseline first. A Stockfish match is useful context, but
an early engine may lose almost every game and provide little information
about small improvements. Never use higher NPS alone to accept a strength claim.

The unmodified Stockfish UCI opponent must be built separately from the patched
NNUE oracle. Upstream source and notices belong in an ignored reference checkout;
neither reference is linked into chess0live. Pin the reference to the release
commit recorded in [NNUE](NNUE.md), not a moving branch.

On the development Mac, the separate reference was built from official commit
`edb0d9db6731067ec50ce619ff372b463bc4dd5d`, with the verified network linked into
its `src` directory, using:

```sh
make -j2 profile-build ARCH=apple-silicon COMP=clang CXX=/usr/bin/clang++
```

This is an **upstream build command**, run inside the reference's `src`, not
the chess0live Makefile. Apple Clang 21.0.0 produced binary SHA-256
`61d09e76d41697555564498df2ecc7cab0bbe3b40ae626b9e7460ae3d9cbe969`.
UCI readiness and a depth-4 search passed on October 13, 2026. The reference uses
NEON/dot-product and upstream profile-guided optimization. Future result reports
must retain this configuration difference when comparing absolute engine speed.
