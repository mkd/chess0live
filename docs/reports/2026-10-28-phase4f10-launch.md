# Phase 4F.10 — authorized match launch preparation

The owner confirmed “Ready, go ahead!” after leaving the 512-game Continuation
History comparison pending a quiet window. The
[one-run amendment](../experiments/phase4f10-match-daytime-20261028.md) permits an
explicit October 28 **19:00–22:00 Helsinki** start and retains the fixed
**October 29 07:00** cutoff. It changes admission only. The
[original protocol](../experiments/phase4f10-match.md), sample, engine, network,
openings, clocks, settings, resource budgets and decision criteria are unchanged.

## Validation before play

- **44 launcher and 68 independent-auditor synthetic tests passed.** They cover
  exact boundaries, expired/wrong grants, preflight completion, child admission,
  original cutoff, cleanup and the unchanged ordinary nighttime policy.
- Independent source review found no material timing or preservation issue.
  The original 61 preparation files and 60 pins from commit `4a53054` are archived;
  all 1,955 previously protected files and 14 indexed original evidence files
  remain unchanged. The normal release, stable GUI `0.1-dev-4b8b35d`, owner batch
  settings and README introduction are preserved.
- Only the launcher, independent auditor, their tests and pin file changed;
  the dated amendment is new. There are now **62 source snapshots / 61 pins**.
  Pin-file SHA-256:
  `7a290b7e1cbc5152c00a8305ebe454168acfb65e031abcd3a495faea308b73fa`.
- Fresh native readiness completed at **19:27:57 Helsinki**: two zero exits,
  all 21 UCI options, 13 commands / 65 raw events, no `position` or `go`.
  The independent audit passed with zero errors and 2,805 input identities.
  Engine/native binary SHA remains
  `c117b828efe6c083520b4af6b45818879a70011a47c3acb96e53b112144dfd08`.
- Host checks found AC power and Low Power mode off; the owner confirmed the
  previously agreed Automatic/paused-inference/awake conditions. Four active
  workers and eight resident engines with 6 GiB reserved fit normal limits.
  Reservations are admission estimates, not OS utilization caps.

Evidence: `results/phase4f10-match-20261028-preparation/`. Fresh readiness is
`readiness-final.json`, SHA-256
`c1b772547ff533c9d7bb62f6e39d3e3a0b1c2af7576ae3908e9aa2725b06d59e`;
the independent `readiness-audit.json` SHA-256 is
`f25e0c29d67b60870b4ff60c7c1498b9447687185b98c75d41173b6367290a0a`.

Pre-launch setup observations are retained in `setup-notes.json`: a remembered
Python environment referenced a removed Homebrew library; the normal isolated
tool bootstrap resolved a working environment. An initial search-free readiness
call rejected old preparation pins before opening engines. A local helper's
direct tuple-versus-dictionary comparison was corrected to compare normalized
role settings. These were preparation issues, not game failures; no games or
held-out searches occurred. Original failure evidence was preserved, and fresh
readiness/audit uses new filenames. No shared tool or engine change was needed.

## Run and interpretation

Commit the tested amendment before starting exactly one fresh attempt at
`results/phase4f10-match-20261028/`. At this preparation checkpoint no games have
started. Launch/exit receipts in the preparation directory and the campaign
manifest record the actual lifecycle. An idle-sleep inhibitor accompanies the
foreground launcher; suspend/resume remains unsupported.

Expect roughly 6–8 hours. Progress reports show complete games, candidate
wins/draws/losses, complete pairs and failures as provisional observations.
The progress helper only reads journals. A progress heartbeat may inspect the
existing run but must never schedule, launch, retry or resume games. Immediately
after termination verify cleanup and tell the owner LM Studio can resume, then
independently audit the existing raw evidence. No competing builds/benchmarks
run during play.

Completion requires all 512 games / 256 pairs and valid evidence. Any time
forfeit blocks promotion eligibility. The declared conditional interval and
fixed decision thresholds remain unchanged. Continuation History stays off by
default; neither readiness nor a provisional score establishes playing strength.
