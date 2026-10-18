# Phase 3K: console diagnostics and completion-capable operational screen

Started October 18, 2026 from `ddee513`. The owner requested this phase plus
console board display, display flipping, help, perft summaries, and board-plus-
NNUE evaluation. Supplied screenshots define the desired behavior; no code or
assets from Gargantua or the owner's other engines are reused.

## Implementation boundary

- `d`, `show`, and `display` share an ASCII board and position-state display.
- `flip` changes display orientation only: no position, key, history, side,
  castling, en-passant, evaluation, or search change.
- `help` describes implemented commands and exact usage.
- `go perft N` prints legal root counts and depth/nodes/time/speed statistics,
  with cancellation and no NNUE requirement. Reject malformed arguments before
  entering normal search. Keep legacy `perft` / `divide` output contracts.
- `eval` displays the board and NNUE diagnostic, labels perspective and units,
  and preserves the existing raw component/score record. In-check diagnostics
  must not imply a search score or mate proof.
- Preserve `info string fen ...` and raw evaluation records for existing tools.
  New human-readable diagnostics are UCI `info string` output, emitted only on
  request. Ordinary handshake/search output and all default options stay fixed.

Validate aliases, orientation, state/key restoration, evaluation output and
errors, input rejection, perft zero/terminal/special-position counts, nonnegative
finite timing/speed, stop/quit responsiveness, and no unsolicited GUI output.
Run native, scalar, and sanitizer suites; compare old/new fixed-depth search
signatures and independently replay display/perft output. Preserve README intro
and both stable GUI bundles; normal builds remain separate.

## Fresh operational attempt, fixed before running

Phase 3J's one 128-ply truncation remains an incomplete recorded game. Do not
extend, replace, pool, or reclassify it. This new screen tests complete game and
cleanup handling on normal storage; Phase 3J already exercised slow-writer
isolation. No extra clock reserve, allocation change, or search tuning is allowed.

1. Run exactly **four games**, two concurrent shards with one pair each. Shard 1
   uses `development-01`; shard 2 uses `development-02` from the original project
   development suite. Play each root with colors reversed. Seeds are
   `2026101811` and `2026101812`. These exposed roots are not strength holdouts.
2. Both roles use the same frozen final Phase 3K native executable and pinned
   `nn-1a298aa575a0.nnue`. Candidate LMR=true, opponent LMR=false. Both have
   classic timing, MVV-LVA, Threads=1, Hash=64 MiB, overhead=20 ms, no ponder,
   no search diagnostics, books, tablebases, or evaluation adjudication.
3. Chess clocks are **1+0.05**, with maximum **1,024 searched plies/game**,
   setup timeout 30 seconds, protocol grace 5 seconds (never free thinking time).
   Global wall deadline **180 seconds**; cleanup may complete later while
   retaining ownership of outstanding I/O. Never silently score a cap as drawn.
4. Freeze launcher/source/engine/network/opening hashes before the first game.
   Retain every result, PGN, transcript, charged clock, and partial failure.
   Recheck aggregate resources before each game: two active search workers,
   four resident engines, doubled per-shard memory reservation. Use ordinary
   50% daytime / 80% night policy; no schedule or long daytime match is implied.
5. Acceptance requires all four complete within the wall deadline, zero clock,
   protocol, persistence, stderr, or truncation failures, legal game/PV/ponder
   replay, matching UCI options and charged clock boundaries, consistent PGNs
   and summaries, unchanged source/assets, and closed engine processes.
   No replacement games or gate changes after seeing outcomes.

The larger ply limit makes completion possible; it does not guarantee it. The
nominal two-game shard clock allowance is about 106.4 seconds at the ply cap,
excluding setup, I/O, and scheduler delays. A failed deadline remains evidence.
This small screen is not a statistical reliability claim or playing-strength test.

## Next checkpoint

If the operational gate passes, prepare the next fresh LMR qualification protocol:
256 new opening pairs / 512 games, equal hardware and settings, fixed statistical
and operational gates, and no pooling of Phase 2D/3G results. Holdouts must be
created and frozen without engine evaluation or outcome selection, excluding all
previously exposed roots. The updated runner and executable need fresh pins,
launcher/auditor readiness checks, and the normal overnight policy before launch.
This phase does not launch or schedule that long campaign. If the operational
screen fails, record the actual cause and make the next bounded step explicit.
