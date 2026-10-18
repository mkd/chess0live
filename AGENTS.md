# Working on chess0live

Read [requirements](docs/REQUIREMENTS.md), [handover](docs/HANDOVER.md), and
[validation](docs/VALIDATION.md) before changing behavior.

- Independent implementation: no reuse of the owner's previous engines or
  their testing assets. Do not embed or link Stockfish engine code as a shortcut.
  External Stockfish builds are evaluation oracles or match opponents only;
  cite format sources and pin reference builds. The owner specifically approved
  the standalone upstream Fathom Syzygy reader on October 18; this exception
  covers tablebase probing only. Preserve its provenance/MIT notices, author
  the adapter independently, and keep all table data outside Git.
- Strength is the main goal; never claim a strength gain from NPS alone.
- Keep protocol output valid, legal moves correct, and all incremental state
  reversible. Prefer a reproducible failing case before changing chess logic.
- Do not label NNUE support verified merely because a network loads. Prove
  feature, accumulator, and output agreement using the pinned architecture.
- Original sources use GPL-3.0-or-later headers and the author's identity in
  REQUIREMENTS. Document third-party assets and retain applicable notices.
- Use C++26 mode; isolate CPU-specific code. Do not silently claim cross-target
  execution when only a compiler produced a binary.
- Honor local resource limits: 50% daytime, 80% 23:00–07:00 Europe/Helsinki,
  owner override permitted. No paid cloud compute. No automatic schedule unless
  requested. Keep short correctness checks modest and long tests overnight.
- Update README/CHANGELOG and handover for material changes. Run relevant checks,
  commit tested changes locally on main. The owner handles GitHub pushes manually;
  do not attempt authentication or publishing. Do not create PRs by default or
  rewrite history.
- Preserve the owner's README introduction before `## Build and run` exactly.
  Limit README updates to practical building, running, testing, configuration,
  extension, and contribution instructions. Keep development phases, match
  reports, and competitive ambitions in the roadmap and other project docs.
- Record failed and inconclusive experiments honestly. Do not release v0.1 or
  advertise a rating before its acceptance gates pass.
- Keep docs/ROADMAP.md current. Progress updates should identify the active
  phase and step, what was learned, and what remains before the next checkpoint.
- Preserve the owner's stable GUI test bundle recorded in docs/MANUAL_TESTING.md;
  normal rebuilds use a different directory. Include its snapshot name in any
  investigation of manual feedback.
