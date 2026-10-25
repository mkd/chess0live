# Running Python tools and tests

Install Python 3.10 or newer with its standard `venv`/`ensurepip` component.
Then run a tool from the checkout with one command:

```sh
python3 tools/run.py tools/match.py --help
python3 tools/run.py tools/profile_smp.py --help
python3 tools/run.py tests/batch_positions_test.py
make test-match
```

The launcher configures the pinned Python packages automatically. No activation
or manual `pip install` is needed. Arguments after the script path are passed
to that script unchanged, and relative engine/output paths still use your
current working directory. Setup messages go to stderr, so redirecting a tool's
stdout to a results file does not mix installation progress into the results.
The launcher does not override a tool's time/resource/experiment safeguards.

`batch_positions.py` also has this setup built into its existing direct command:

```sh
python3 tools/batch_positions.py "/path/to/engine"
```

Edit its `ENGINE`, `THREADS`, `HASH_MB`, `MOVETIME_MS` and `FENS` as before.
Setup never rewrites them. Other historical scripts remain unchanged: use the
shared launcher when invoking them directly. Existing optional Make test targets
that need the chess referee use the launcher automatically. Ordinary `make`,
`make test`, network download, resource reporting and standard-library-only
tools keep their dependency-free Python path.

To prepare packages without running a tool, use `make tooling` or
`python3 tools/run.py --setup`. This prints the managed Python path. To check
the setup code and batch runner, use `make test-tooling`.

## Read saved puzzle comparisons

Export a completed TT Move Hints comparison with one command:

```sh
python3 tools/puzzle_report.py results/phase4f7-20261025/smoke/report.json --output results/puzzle-summary
```

Python dependencies prepare automatically through the same isolated setup.
This command reads the saved evidence; it does not launch an engine, compile,
train or repeat a timed search. It currently supports the frozen Phase 4F.7
readiness, smoke and full report formats explicitly. Other historical report
formats are not silently reinterpreted.

Keep the original raw session logs and pinned inputs available and unchanged.
The independent auditor checks them again before publication; missing, altered,
incomplete or failed evidence is rejected. An earlier certificate alone is not
enough. Choose a new output directory; existing files/directories are preserved.
Its parent directory must already exist. CSV uses UTF-8 with a byte-order mark
for spreadsheet import; numeric scores remain numeric and formula-like text
cells are escaped as text.
The export contains:

- `comparison.md`: settings, audit scope and all 39 position comparisons, including
  different scores, moves, depths and mate reports.
- `positions.csv`: one row per position/configuration, suitable for a spreadsheet.
- `audit.json`: the fresh independent audit, bound to the saved report's digest.

Readiness has no searches and produces a CSV header without position rows.
Smoke and full results are labeled separately. Supplied mate distances, reported
mates and legal lines ending in checkmate remain different claims; no Elo or
forced-mate proof follows from this presentation. A larger centipawn score is
not a distance-to-mate measure. These exports are summaries, not replacements
for the original evidence. Test the exporter without engine searches using:

```sh
python3 tools/run.py tests/puzzle_report_test.py
```

On Windows, replace `python3` with `py -3`. The implementation uses portable
Python path/CSV handling; native Windows execution of this exporter is not yet
verified. Its first real integration uses the existing macOS ARM64 smoke data.

## Windows

Use the Python launcher rather than a shell-specific environment activation:

```powershell
py -3 tools/run.py tools/match.py --help
py -3 tools/batch_positions.py "C:\Chess\chess0live.exe"
```

With GNU Make installed, `make PYTHON="py -3" test-match` uses the same setup.
Paths containing spaces are supported through argument lists. Native Windows
execution of this new setup workflow remains unverified; macOS ARM64 and a
Linux ARM64 VM have real setup/run evidence. Python itself, GNU Make/compiler
installation and SDK provisioning have separate requirements. The
[automatic build frontend](PORTABILITY.md#automatic-target-setup) can now provision
pinned Windows toolchains; Linux/system SDK prerequisites remain explicit.

## Cache, offline use and recovery

The default cache is `.local/tooling/` in the checkout, excluded from Git. It
contains downloaded archives, one environment per Python/platform/manifest
identity, and setup logs. It does not install into system Python or alter your
global pip configuration. `CHESS0LIVE_TOOL_CACHE` selects another local directory
if the checkout is read-only or if you prefer a cache outside a cloud-sync folder.
Keep a cache on one machine; Python virtual environments are not portable copies.

After a successful first run, ordinary use needs no Internet access. To forbid
downloads explicitly, put `--offline` before the script:

```sh
python3 tools/run.py --offline tools/match.py --help
```

Alternatively set `CHESS0LIVE_TOOL_OFFLINE=1`, including for direct batch commands
and Make. A missing environment can also be reconstructed offline when all three
pinned archives are already cached. Missing/corrupt archives in offline mode
produce a clear error; an online retry can replace a corrupt download.

Interrupted package installation is rebuilt automatically on the next command.
Simultaneous first runs wait for one setup instead of installing over each other.
On POSIX, installers inherit the lock until they exit, including when the parent
is killed; timeout/cancellation stops their process group. A leftover lock file
is harmless. Native Windows process-tree cancellation remains unverified. If another
setup is still busy after two minutes, retry when it finishes. Setup logs are
`setup-<identity>.log` inside the cache. Failed downloads explain the connection
or checksum problem without publishing the incomplete archive.

If your OS omits Python's `venv`/`ensurepip`, install its Python venv component
through the OS package manager and retry. A folder with missing/foreign ownership
metadata is preserved, not deleted: choose a fresh `CHESS0LIVE_TOOL_CACHE` directory
or move that suspect cache aside before retrying. Do not change/remove managed
environments while tools are running in them.

## Dependency provenance and maintenance

The committed [package manifest](../tools/python-packages.json) pins download
URLs, SHA-256 hashes, versions and license identifiers from official PyPI release
metadata: [chess 1.11.2](https://pypi.org/project/chess/1.11.2/),
[setuptools 80.9.0](https://pypi.org/project/setuptools/80.9.0/) and
[wheel 0.45.1](https://pypi.org/project/wheel/0.45.1/). Upstream license files
remain in the installed packages. `chess` is the only runtime dependency;
setuptools and wheel build its pure-Python source distribution. The Python
installation supplies its bundled pip through `ensurepip`; the setup log records
that tool's output. No unpinned build-environment download is allowed.

Setup uses [Python virtual environments](https://docs.python.org/3/library/venv.html),
copied interpreters, verified local archives, and pip's
[hash-checking mode](https://pip.pypa.io/en/stable/topics/secure-installs/).
Both pip stages disable indexes, dependency resolution and build isolation.
The first stage installs the pinned build tools; the second builds/installs chess.
Import/version/isolation checks run before reuse. These checks detect ordinary
damage; they are not a security sandbox for arbitrary Python scripts.

When updating dependencies, review upstream provenance/licenses, update hashes
and versions together, preserve the runtime pin in `requirements-match.txt`,
and rerun first-use, offline, recovery and tool tests. Old frozen experiment
manifests retain their historical dependency versions; do not reinterpret old
results as runs with the new setup. The engine, NNUE and tablebase data remain
independent of this Python environment. The [build frontend](PORTABILITY.md#automatic-target-setup) handles installed
compiler discovery and supported pinned Windows toolchains separately.
The [network tools](NETWORKS.md) inspect artifacts, compare SFNNv16 evaluation
against the pinned oracle and attach digest-bound training provenance. Unknown
experience counts remain unknown; supplied claims are labeled unverified.
Those tools need no third-party Python packages. The separate
[training workflow](TRAINING.md) prepares its own pinned runtime, creates or
fine-tunes SFNNv16 weights, exports and qualifies them. Its initial runtime is
macOS ARM64 CPU; unsupported training hosts fail explicitly before downloads.
Managed network selection and further training hosts/GPU execution remain open.

## Managed evaluation network choice

`tools/managed_network.py` provides local registration, selection, rollback and
launching using only Python's standard library. `make network-status` and
`make network-run` expose the current choice. Registration automatically invokes
the full network qualification workflow; it needs the native compiler/Git/Make
prerequisites described in [managed selection](NETWORKS.md#managed-selection).
The catalog stays outside Git, and neither inspection nor registration changes
GUI settings or the original default network.
