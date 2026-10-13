#!/usr/bin/env python3
"""Describe paired-opening results without treating the two games as independent.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Each input item is {"pair_id": str, "opening_key": str, "games": [game, game]}.
The opening key identifies the canonical starting FEN and exact opening moves;
renaming an opening must not change it. A game supplies
status="complete", candidate_color="white"|"black", and a PGN result. An
optional candidate_score is checked against the result; it is never trusted as
an independent source. Both games must finish and exchange the candidate's color.

The pair score is (candidate_game_1_points + candidate_game_2_points) / 2,
bounded by [0, 1]. For n independent pairs, Hoeffding gives a two-sided interval
with radius sqrt(log(2 / alpha) / (2*n)). Within-pair correlation is unrestricted.
This conservative bound is not a normal approximation or an SPRT. Its assumptions
include a predeclared stopping rule and independent sampling of opening pairs;
this helper cannot establish those assumptions from game records alone.

Reference for the mathematical bound (implementation independently written):
https://ai.stanford.edu/~gwthomas/notes/concentration.html
"""

import argparse
from collections import Counter
from collections.abc import Mapping
import json
import math
from pathlib import Path
import sys


# A reporting policy, not a claimed mathematical threshold: Hoeffding itself
# holds at every positive sample size, but tiny runs should remain smoke tests.
MINIMUM_PAIRS = 30
RESULT_POINTS = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}


def relative_elo(score):
    """Encode 400*log10(score/(1-score)) with JSON-safe boundary descriptions.

    This is a score-to-relative-rating transform, never an absolute engine Elo.
    Null at a boundary means an infinite transform, not zero or missing evidence.
    """
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("score must be a finite number in [0, 1]")
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError("score must be a finite number in [0, 1]")
    if score == 0:
        return {"value": None, "interpretation": "negative_infinity"}
    if score == 1:
        return {"value": None, "interpretation": "positive_infinity"}
    value = 400.0 / math.log(10.0) * (math.log(score) - math.log1p(-score))
    return {"value": value, "interpretation": "finite"}


def _game_score(game, pair_id):
    """Return candidate points or a concise exclusion reason, without mutation."""
    if not isinstance(game, Mapping):
        return None, "invalid_game_record"
    if game.get("status") != "complete":
        return None, "game_not_complete"
    if "pair_id" in game and game["pair_id"] != pair_id:
        return None, "game_pair_id_mismatch"
    color = game.get("candidate_color")
    if color not in ("white", "black"):
        return None, "invalid_candidate_color"
    result = game.get("result")
    if not isinstance(result, str) or result not in RESULT_POINTS:
        return None, "invalid_result"
    white_score = RESULT_POINTS[result]
    score = white_score if color == "white" else 1.0 - white_score
    if "candidate_score" in game:
        supplied = game["candidate_score"]
        if (isinstance(supplied, bool) or not isinstance(supplied, (int, float))
                or not math.isfinite(supplied) or supplied != score):
            return None, "candidate_score_mismatch"
    return score, None


def summarize_pairs(pairs, confidence=0.95, *, experiment_complete=False):
    """Return JSON-safe descriptive statistics and, when eligible, uncertainty.

    ``experiment_complete`` must be True only after the predeclared sample has
    finished. All incomplete, malformed, duplicated, or error-containing pairs
    are excluded as entire clusters. Any exclusion withholds the confidence
    interval because outcome-dependent exclusions can bias strength estimates.
    A successfully completed game in an excluded pair is not counted in W/D/L.

    The reported score is always from the candidate's perspective. Pair-point
    counts use totals out of two points, while score/CI use proportions [0, 1].
    ``inference_eligible`` records these mechanical checks only; it does not
    certify independent sampling, a stopping rule, or a representative suite.
    Missing or repeated opening identities also withhold uncertainty. Merely
    shuffling a small fixed suite cannot create more independent opening samples.
    """
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or not 0 < confidence < 1):
        raise ValueError("confidence must be a finite number strictly between 0 and 1")
    if not isinstance(experiment_complete, bool):
        raise ValueError("experiment_complete must be a boolean")
    if isinstance(pairs, (str, bytes, Mapping)):
        raise ValueError("pairs must be an iterable of pair records")
    records = list(pairs)
    pair_ids = Counter(pair.get("pair_id") for pair in records
                       if isinstance(pair, Mapping)
                       and isinstance(pair.get("pair_id"), str) and pair["pair_id"])
    wdl = {"wins": 0, "draws": 0, "losses": 0}
    pair_points = {"0.0": 0, "0.5": 0, "1.0": 0, "1.5": 0, "2.0": 0}
    statuses = Counter()
    terminations = Counter()
    exclusions = []
    included = []
    recorded_games = 0
    included_clock_forfeits = 0

    for index, pair in enumerate(records):
        reasons = []
        pair_id = pair.get("pair_id") if isinstance(pair, Mapping) else None
        if not isinstance(pair_id, str) or not pair_id:
            reasons.append("missing_or_invalid_pair_id")
            display_id = None
        else:
            display_id = pair_id
            if pair_ids[pair_id] != 1:
                reasons.append("duplicate_pair_id")
        games = pair.get("games") if isinstance(pair, Mapping) else None
        if not isinstance(games, (list, tuple)):
            reasons.append("invalid_games_collection")
            games = []
        recorded_games += len(games)
        if len(games) != 2:
            reasons.append("pair_requires_exactly_two_games")

        points = []
        colors = []
        for game in games:
            status = game.get("status") if isinstance(game, Mapping) else None
            statuses[status if isinstance(status, str) else "missing_or_invalid_status"] += 1
            termination = game.get("termination") if isinstance(game, Mapping) else None
            terminations[termination if isinstance(termination, str) else "not_recorded"] += 1
            score, reason = _game_score(game, pair_id)
            if reason:
                reasons.append(reason)
            else:
                points.append(score)
                colors.append(game["candidate_color"])
        if len(games) == 2 and len(points) == 2 and set(colors) != {"white", "black"}:
            reasons.append("colors_not_reversed")
        # The harness hashes canonical FEN + opening moves, preventing aliases
        # or repeated cycles of one position from masquerading as distinct data.
        opening_key = pair.get("opening_key") if isinstance(pair, Mapping) else None
        game_keys = [game.get("opening_key") for game in games if isinstance(game, Mapping)]
        # Known game identities must agree even if the enclosing pair omitted
        # its key. Otherwise two unrelated games could become a descriptive pair.
        known_keys = [key for key in game_keys if key is not None]
        if len(known_keys) > 1 and any(key != known_keys[0] for key in known_keys[1:]):
            reasons.append("game_opening_key_mismatch")
        if opening_key is None and len(game_keys) == 2 and game_keys[0] == game_keys[1]:
            opening_key = game_keys[0]
        if not isinstance(opening_key, str) or not opening_key:
            opening_key = None
        if opening_key is not None and any(key is not None and key != opening_key for key in game_keys):
            reasons.append("game_opening_key_mismatch")
        if reasons:
            exclusions.append({"record_index": index, "pair_id": display_id,
                               "reasons": sorted(set(reasons)), "recorded_games": len(games)})
            continue

        total = math.fsum(points)
        included.append({"pair_id": pair_id, "opening_key": opening_key,
                         "points": total, "score": total / 2.0})
        pair_points[f"{total:.1f}"] += 1
        included_clock_forfeits += sum(game.get("termination") == "time_forfeit" for game in games)
        for score in points:
            wdl["wins" if score == 1 else "losses" if score == 0 else "draws"] += 1

    count = len(included)
    score = math.fsum(pair["score"] for pair in included) / count if count else None
    withheld = []
    if not experiment_complete:
        withheld.append("predeclared_experiment_not_complete")
    if count < MINIMUM_PAIRS:
        withheld.append("insufficient_complete_pairs")
    if exclusions:
        withheld.append("excluded_pairs_may_bias_results")
    opening_counts = Counter(pair["opening_key"] for pair in included if pair["opening_key"] is not None)
    if any(pair["opening_key"] is None for pair in included):
        withheld.append("opening_identity_not_recorded")
    if any(count > 1 for count in opening_counts.values()):
        withheld.append("repeated_openings_do_not_establish_independent_samples")

    interval = None
    elo_interval = None
    radius = None
    if not withheld:
        alpha = 1.0 - confidence
        radius = math.sqrt(math.log(2.0 / alpha) / (2.0 * count))
        lower, upper = max(0.0, score - radius), min(1.0, score + radius)
        interval = {"lower": lower, "upper": upper}
        elo_interval = {"lower": relative_elo(lower), "upper": relative_elo(upper)}

    return {
        "schema_version": 1,
        "perspective": "candidate",
        "experiment_complete": experiment_complete,
        "supplied_pairs": len(records),
        "included_pairs": count,
        "excluded_pairs": len(exclusions),
        "recorded_games": recorded_games,
        "included_games": 2 * count,
        "excluded_games": recorded_games - 2 * count,
        "game_status_counts": dict(sorted(statuses.items())),
        "termination_counts": dict(sorted(terminations.items())),
        "included_time_forfeit_games": included_clock_forfeits,
        "distinct_identified_openings": len(opening_counts),
        "wdl": wdl,
        "pair_point_counts": pair_points,
        "score": score,
        "relative_elo": relative_elo(score) if score is not None else {
            "value": None, "interpretation": "no_completed_pairs"},
        "relative_elo_note": (
            "Descriptive 400*log10(score/(1-score)) versus this opponent and configuration; "
            "not an absolute Elo or a proven strength advantage. Boundary infinity describes "
            "the observed-score transform, not infinite playing strength."),
        "inference_eligible": not withheld,
        "uncertainty": {
            "method": "conservative_two_sided_Hoeffding_on_opening_pair_scores",
            "confidence": confidence,
            "independent_units": "opening_pairs_not_individual_games",
            "scope": "Configured finite opening suite and engine conditions; no broad rating-pool generalization.",
            "sample_size_pairs": count,
            "minimum_pairs_policy": MINIMUM_PAIRS,
            "radius": radius,
            "score_interval": interval,
            "relative_elo_interval": elo_interval,
            "withheld_reasons": withheld,
            "assumptions": [
                "Opening-pair observations are independent under the declared sampling design.",
                "Shuffling hand-selected openings alone proves neither independence nor representativeness.",
                "Both colors use identical frozen engine, resource, and clock configurations.",
                "The sample size or stopping rule was declared before inspecting results.",
                "No outcome-dependent exclusions or repeated favorable-result peeking occurred.",
                "The interval concerns the sampled opening distribution and these conditions only.",
            ],
        },
        "included_pair_scores": included,
        "excluded_pair_details": exclusions,
    }


def main():
    """Read nested pair records from JSON and print a strict, portable JSON summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pairs", type=Path, help="JSON array of paired game records")
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--complete", action="store_true",
                        help="affirm the predeclared experiment has finished")
    args = parser.parse_args()
    try:
        pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
        summary = summarize_pairs(pairs, args.confidence, experiment_complete=args.complete)
        print(json.dumps(summary, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError) as error:
        print(f"Match statistics failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
