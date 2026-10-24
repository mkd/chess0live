# Project requirements

Accepted with Claudio M. Camacho on October 13, 2026.

## Purpose and priorities

Build an independently written, open-source UCI chess engine for ordinary
desktops and laptops. Playing strength on equal hardware is the primary metric;
elegance and raw throughput may be traded for demonstrated strength. Be willing
to test new ideas, but keep experiments separate from accepted improvements.
Decisively exceeding Stockfish 19 is the research objective. A reproducible
4000+ Elo rating would be desirable; no universal absolute Elo scale or achieved
rating is claimed.

Use published techniques and independently authored implementations. Do not
reuse code, runners, tests, comparisons, or other assets from chess0, chess0x,
Gargantua, Sic, or QWChess. Public upstream format specifications, networks, and
separately built test references are permitted, with provenance and notices.
On October 18 the owner authorized using the same tablebase dependency as Sic:
the standalone upstream Fathom reader, limited to Syzygy probing. Retain its MIT
notices and explicit Cfish ancestry; the adapter/search/evaluation remain
independent. Production table data is user-downloaded, UCI-configured, and
excluded from Git. See [Syzygy](SYZYGY.md).

## Product

- Name: **chess0live** (olive emoji in presentation, plain ASCII executable).
- Author: **Claudio M. Camacho <claudiomkd@gmail.com>**.
- Original code: **GPL-3.0-or-later**. Retain applicable third-party notices.
- C++26 compilation mode, portable supported features, documented toolchains.
- Bitboard chess representation; CPU specialization behind portable interfaces.
- Version 0.1: correct playable UCI engine, `perft`, verified Stockfish 19 NNUE
  evaluation with incremental accumulators and all its feature families,
  extensible search, reproducible benchmarks, and developer documentation.
- Pin the Stockfish 19-compatible network first. New NNUE architectures must be
  explicit versioned additions. Never interpret arbitrary `.nnue` files as one
  interchangeable format.
- Do not spend the initial phase creating or training proprietary/new networks.
  Later tooling may adapt established Python/PyTorch trainers, with reproducible
  configurations, data provenance, and export validation.
- Keep future opening books, puzzle solvers, and chess variants extensible;
  implementing those extensions is outside the core scope.
- Smart tournament time management and analysis must respect UCI control.

## Hardware and resource policy

Primary optimization target: MacBook Pro M5 Pro. The following inventory is
owner-supplied, not a hardware probe:

| Machine | Reported CPU cores | Reported RAM | Reported GPU |
| --- | ---: | ---: | --- |
| MacBook Pro M3 Pro | 12 | 36 GB unified | 18 GPU cores |
| MacBook Pro M5 Pro | 18 | 64 GB unified | 20 GPU cores |
| Lenovo ThinkPad, Core Ultra 7 155U | 14 | 32 GB | Intel Arc |

No paid external testing or training. Long experiments run locally overnight.
Blitz is the initial strength-testing priority, followed by rapid and analysis.
Daytime resource budget is 50%; nighttime is 80%, **23:00–07:00 Europe/Helsinki**.
The owner may raise or lower the budget manually. Detect available resources
before sizing workloads; CPU thread count is a scheduling approximation rather
than an exact utilization guarantee, especially on hybrid CPUs. Count every
engine process and memory allocation in aggregate. Do not launch an unattended
recurring schedule merely because overnight testing is permitted.

## Platforms

Linux: x86-64, ARM64, RISC-V64. Windows: x86-64, ARM64. macOS: ARM64.
Deliver each target as soon as practical; record build and runtime verification
separately. macOS x86-64 is excluded. GNU Make is the public build interface.
Installing compilers, target libraries, and SDKs is acceptable; document host
restrictions instead of promising impossible toolchain-free cross-compilation.

## Delivery and maintenance

Work in the existing local `chess0live` checkout. The owner handles publishing to
<https://github.com/mkd/chess0live> manually; agents should not attempt GitHub
authentication or pushes. Use small tested commits directly on `main`.
Branches/PRs are unnecessary unless an exceptional practical reason arises.
Test first, commit locally second. Update README, concise
version-oriented changelog, implementation decisions, and handover instructions.
Preserve the owner's README introduction before `## Build and run` exactly;
it is a short description of the engine and its author. Future README edits
are limited to practical build, run, test, configuration, extension, and
contribution instructions. Development phases, match reports, and competitive
ambitions belong in the roadmap and other project documentation, not the README.
Use semantic version milestones for tested, user-visible deliverables: patch
releases for compatible fixes and minor releases for new capabilities, with
compatibility breaks explicitly documented. Research phases are planning labels,
not release numbers. Keep pending work under `Unreleased`; when a genuine
release is accepted, record its version, actual release date, and concise
user-facing improvements in CHANGELOG, updating practical README instructions
only where affected. Do not retain the same version indefinitely or declare
version 0.1 before its documented
[acceptance gates](VALIDATION.md#release-gates) pass.
Every release must distinguish measured strength from aspiration, and tested
platforms from merely intended targets. Source files have consistent copyright,
license, and explanatory comments; explain invariants and non-obvious decisions.

## Tooling experience — owner feedback, October 24, 2026

Provide simple, documented commands for running tools/tests/benchmarks,
cross-compiling, and creating/training/selecting a user-owned NNUE network.
External Python/Make or other orchestration must discover and configure the
needed dependencies automatically, using isolated user-local environments.
Users should not have to manually create a Python environment or diagnose a
missing package before running a tool. Existing editable user settings must be
preserved. The engine remains independent of this setup/training tooling.

Offer the same coherent workflow across supported host OS/CPU combinations.
Automate toolchain, target-library, network and environment setup where possible;
state unavoidable SDK, OS, licensing or permission requirements clearly instead
of promising that every cross-target route is possible without prerequisites.
Downloads need pinned identities/provenance, cache reuse and useful recovery
from partial setup. Do not install into system Python or silently change global
user settings as the convenience mechanism.

Network tooling must support creation, training, validation and switching through
simple commands. Report recorded training provenance: source/unique game counts
where known, positions, processed samples, training steps/epochs and parent
checkpoint lineage. Unknown counts remain unknown; repeated training examples
must not be advertised as additional unique games or playing strength. Preserve
format/architecture versioning and verify exported arithmetic and compatibility.
This is future tooling work, not a claim that custom-network training exists now.
