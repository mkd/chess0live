# Linux tournament follow-up: saved settings and recovered final game

November 6, 2026. Supplements and qualifies the
[initial four-engine review](2026-11-06-four-engine-tournament-review.md).
No engine behavior or default changed; no engine search, match or build ran.

**Latest evidence:** the owner subsequently supplied a live Linux UCI handshake
and executable digest. It confirms that the registered GUI schema is stale
relative to the currently probed binary: Threads max 64 and LMR default true.
See [the handshake follow-up](#live-linux-handshake-follow-up). Tournament startup
settings and binary continuity remain unproved; refreshing the GUI profile is
now the immediate step rather than assuming a one-thread-only executable.

## Revised interpretation

The supplied configuration contains a concrete conflict: every engine's raw
initialization commands request Threads 10 / Hash 1024, but the separate saved
option values differ. The owner confirms entering those commands in the engine
setup text field and making no Threads/Hash changes inside tournament setup.
Under the verified standard Cute Chess v1.5.1 startup sequence, the saved options
are applied after the initialization commands, including values equal to their
stored defaults. They would override the intended common settings.

| Engine | Initialization requests | Later saved Threads | Later saved Hash (MB) |
| --- | --- | ---: | ---: |
| chess0live | Threads 10 / Hash 1024 | 1 | 64 |
| Hyperion | Threads 10 / Hash 1024 | 1 | 64 |
| sic | Threads 10 / Hash 1024 | 9 | 4096 |
| Gargantua | Threads 10 / Hash 1024 | 1 | 1024 |

These are the **expected requests from these profiles**, not observed worker
counts or memory usage. The installed Cute Chess version, engine binaries and
startup transcript remain unavailable. The owner's clarification removes the
reported per-tournament manual-override alternative, but does not reconstruct
missing startup evidence. Preserve the original 60-game standings as outcomes
of the configurations that actually played; this is not a verified equal-resource
test of current chess0live. Hyperion and chess0live have the same saved
Threads/Hash values, so this particular saved-setting mismatch does not by itself
explain their gap; actual resource use remains unverified.

The immediate priority is **identify the Linux build, refresh its registered
options and verify final applied settings**. The initial source-review
hypotheses remain useful; they cannot be presented as causes of this event.
The earlier 512-versus-1024-MiB TT comparison describes current sources at a
hypothetical Hash 1024 setting, not established allocations in this tournament.

## Attached evidence

The owner supplied `/Users/claudio/cutechess.ini`, `/Users/claudio/engines.json`
and `/Users/claudio/tournament.log`. Original bytes are retained in ignored
`results/four-engine-owner-20261106/raw/`, with `input-manifest.json` alongside.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| cutechess.ini | 1,477 | `7844167d7c205b2d1a0a5925b89b564b675ec0038abbb4d7548fab8322e51ed3` |
| engines.json | 4,231 | `b1e5fdf8f934117b6fa3555f9583d89c66e8b31350781ff6b1de1d4ae30bd4c7` |
| tournament.log | 570,898 | `88bdc8b81dced272702bbb558f1a8d4246d0656d0cb64fe92a117935c0334870` |

The INI has only UI settings. It does not provide the tournament clock, opening,
concurrency or output configuration. The owner separately confirms tournament
PGN output was unset and no complete tournament PGN was saved. Every engine's
`stderrFile` is empty in the JSON: no engine stderr destination is configured
there. The attached debug text is a selected-game protocol transcript, not a
full tournament/crash log. It contains 4,092 logical lines but only 4,091 newline
characters because the final line has no newline.

## Why the initialization commands are overridden

Official upstream source was inspected at the named **v1.5.1** release, not
assumed to be the user's installed version:

1. `EngineConfiguration` loads both the initialization strings and saved option
   records. The option factory preserves `value` independently of `default`.
2. `ChessEngine::applyConfiguration` queues the raw strings and separately
   buffers every editable saved option. There is no skip for value == default.
3. `start()` flushes raw strings before starting UCI. After `uciok`,
   `onProtocolStart()` applies the buffered saved options, validated against
   the executable's freshly advertised option definitions.
4. The GUI copies global profiles into its tournament list and permits local
   edits. The owner says no such resource edits were made here. General game
   settings apply pondering; they do not replace Threads/Hash values.

Sources: [configuration loading](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/lib/src/engineconfiguration.cpp),
[option decoding](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/lib/src/engineoptionfactory.cpp),
[configuration and startup order](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/lib/src/chessengine.cpp),
[UCI handling](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/lib/src/uciengine.cpp),
[tournament profiles](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/gui/src/newtournamentdialog.cpp),
[game settings](https://github.com/cutechess/cutechess/blob/v1.5.1/projects/gui/src/gamesettingswidget.cpp).

## chess0live's registered schema is old or stale

The profile points to
`/home/claudio/projects/chess0live/build/linux-x86_64-generic-release/chess0live`.
It stores Threads value/default/max **1**, LMR value/default **false**, and only
classic/forecast time policies (`engines.json:73–80,100–121,138`). The network
name is `nn-1a298aa575a0.nnue`; a filename does not verify its bytes or loading.

The option combination matches mainline schema history from
`2e6908376c5817f8499a4c9ca454bf8786d8d47e` (October 14) through
`07d4d6fab173fc71c961b128835fabfdeee1ea41` (October 18), before SMP.
Commit `b0c22d2743125d0fb40a8bede4c31cbd741dd103` on October 18 added actual
multiple-worker support and changed max_threads from 1 to 64. Commit
`9bb8ffb8b6d9e488559b46e12d8f7b378fb182fa` on October 23 enabled accepted LMR by
default. Bounded time policy followed in `d25e2e5a109a584bd41bd18eb42942d6675441c9`.

This identifies a compatible **profile era**, not a proven binary revision or
build date. The executable may have been replaced without refreshing its GUI
registration. A matching historical one-thread binary rejects Threads 10 with
`info string error: unsupported option or value`; it does not gain SMP by
receiving that command (`07d4d6f:src/main.cpp:272–277`). A current binary accepts
up to 64 workers, but a later saved Threads 1 request still selects one, and
saved LMR false explicitly disables the current accepted policy. Preserve stable
GUI snapshot `build/test-baselines/0.1-dev-4b8b35d/`; nothing identifies that
macOS snapshot as the Linux tournament executable.

## Final game recovered from protocol histories

The log has no startup handshake, setoption commands, build/network identities,
process exit status, or chess0live/Gargantua output. It begins at Sic's seventh
move. Subsequent `position startpos moves ...` commands retain the preceding
twelve plies, allowing the full game's move sequence to be recovered.

**Sic was White; Hyperion was Black; Hyperion won 0–1 with 79...Rf8#.** The
reconstructed PGN is
`results/four-engine-owner-20261106/sic-hyperion-log-derived.pgn`.
It labels its source and missing date/round, and distinguishes owner-reported
2+1 time control from the observed 1,000-ms increments.

Validation passes for **158 mainline plies, 146 consistent position histories,
146 legal observed bestmoves matching the following histories, and 3,357 legal
reported PVs**. There are 73 recorded searches for each engine. The exported PGN
round-trips to the complete history, and the final position is checkmate. This
does not establish that each search was sound or prove intermediate mate scores.
It is a mate loss, so it cannot diagnose any of the seven disconnect games or a
chess0live loss.

The reconstruction used an existing environment with chess 0.31.4 after another
existing interpreter failed due to a missing Homebrew library. The initial
failure remains recorded. A separate implementation then replayed the raw
histories, every bestmove/PV and the exported PGN using existing chess 1.11.2
with the working system Python; it independently passes. No dependency was
installed and no engine was executed. Receipts are `log-audit.json`,
`independent-replay.json`, `derived-manifest.json`, `search-sessions.json` and
`info-lines.json` in the same evidence directory.

Sic's lowest observed own clock is 1,048 ms; Hyperion's is 11,990 ms. These
describe this one game, not general clock reliability. Engine-reported final
iteration time is not total move elapsed time. Hyperion's last search reports
depth 127, seldepth 1, 4,699 nodes and 2 ms for mate in one: nominal depth is
plainly not uniform tree coverage or a cross-engine strength measurement.
The file ends with readiness responses and quit commands, not exit-code receipts.

## Live Linux handshake follow-up

The owner ran the identification commands below and supplied
`/Users/claudio/output.txt`. Its original bytes are retained as
`results/four-engine-owner-20261106/raw/output.txt`; the parsed receipt and source
fingerprint are in `linux-handshake.json`. The original three-file manifest is
unchanged. The supplied executable digest is:

```text
07a6d4e7374ed9a4dc1972e364f3f21db971ecee4abb2189e25c32b6d6d2a6c0
```

The queried path is the same Linux path stored in the GUI profile. The transcript
reaches `uciok` and advertises **Threads maximum 64**, **LMR default true**,
bounded time policy, Continuation History, TT Move Hints and other later options.
This confirms the GUI's saved max-1/LMR-false schema is stale relative to the
currently probed executable; it does not establish when that executable changed.
The live default is still Threads 1 / Hash 64: capability is not configuration.
A later saved LMR false request also overrides the advertised true default.

Its complete 21-option list lacks **QSearch Delta Pruning**, which current
mainline added in `9f8ff9f9b203f70cecd8cd8efd23c364176059b8` on November 4.
Consequently the advertised surface differs from current local mainline. This
does not identify an exact commit/build date or prove the default-off delta
feature affected the tournament. The fingerprint is owner-supplied output,
not a locally inspected Linux executable or proof that this binary played every
game. No network load/digest, actual worker count or GUI option exchange is
demonstrated by this handshake.

Independent review of the attachment and local source history agrees. No engine
was executed by the agents and no rebuild is required merely to establish that
this executable advertises multiple-worker capability.

## Concrete next step

The owner has completed this identification step; retain the commands for
reproducibility before any future replacement or rebuild:

```sh
cd /home/claudio/projects/chess0live/build/linux-x86_64-generic-release
printf 'uci\nquit\n' | ./chess0live
sha256sum ./chess0live
```

This handshake requests no search. Retain its complete output, the Cute Chess
version, and the actual network's SHA-256. A source checkout's HEAD alone cannot
identify an already built executable.

Now register the intended Linux binary as a fresh engine entry so its
options are detected again. Set Threads and Hash through the **Options fields**,
remove duplicate resource initialization commands, and use LMR true for the
current accepted chess0live profile. If the freshly detected maximum is still
one thread, first resolve the executable/build identity; editing cached metadata
cannot add SMP. Keep optional experiments at their intended explicit values.
Choose a tournament PGN destination and save the startup exchange, including
final option commands and errors, before a new strength comparison. Verify the
requested aggregate load fits the Linux host; ten threads is an intended setting,
not an automatic resource authorization for every machine/concurrency.

Existing Phase 4F.19 evidence and proposed Phase 4F.20 scope remain unchanged.
The setup correction does not prove a strength gain, invalidate the observed
standings, justify new defaults, or authorize a scheduled rerun. No Linux config
or supplied attachment was edited. The owner's batch-runner edit, production
source, README introduction and stable GUI bundles remain preserved.
