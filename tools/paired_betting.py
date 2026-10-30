#!/usr/bin/env python3
"""Fixed-mixture confidence bounds for a prospectively sized paired match.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

One observation is the candidate's total points in a color-reversed pair / 2.
For X in [0, 1] and E[X_i | past] = m, each product
prod_i(1 + lambda * (X_i-m)) is a nonnegative test martingale when 0<lambda<=1.
Mix four fixed products equally, and do the same with the opposite sign.
Markov's inequality at the declared final sample (or Ville's inequality over
time) bounds each tail by 1/40. Inverting both tests gives at least 95% coverage
under the common-conditional-mean assumption. Within-pair dependence is allowed.
At a fixed predeclared sample size, independent nonidentical observations also
permit inference for the average of their means: AM-GM bounds the expectation
of each product by (1 + lambda * (average_mean-m))**n. This broader fixed-time
argument does not justify optional stopping. Shared stems and host dependence
can violate the assumptions; this helper does not prove independence or strength.

This deliberately small implementation uses a fixed grid, not fitted stakes,
an SPRT, a normal approximation or a copy of a third-party implementation.
The caller must audit pair identities, color reversal, raw scores, exclusion
policy, clock forfeits and the predeclared sample. This helper has no game data
with which to certify those facts. Never apply it retrospectively to replace
the decision rule of an older experiment.

Mathematical source: Waudby-Smith and Ramdas, Estimating means of bounded random
variables by betting, section 4 (capital processes); independently implemented.
https://arxiv.org/html/2010.09686v7#S4
"""

from collections import Counter
import math

METHOD = "phase4f13-fixed-mixture-v1"
SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)
LAMBDAS = (0.125, 0.25, 0.5, 1.0)
TAIL_THRESHOLD = 40.0
CONFIDENCE = 0.95
DEFAULT_PAIRS = 1024


def _counts(scores):
    if not isinstance(scores, (list, tuple)):
        raise ValueError("scores must be a list or tuple of normalized pair scores")
    for score in scores:
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or score not in SCORES or not math.isfinite(score)):
            raise ValueError("pair scores must be finite values in {0, .25, .5, .75, 1}")
    counts = Counter(scores)
    return tuple(counts[value] for value in SCORES)


def _log_capital(counts, mean, direction):
    """Stable log of the equal mixture; zero factors mean zero capital."""
    components = []
    for stake in LAMBDAS:
        terms = []
        for score, count in zip(SCORES, counts):
            if not count:
                continue
            change = direction * stake * (score - mean)
            if change == -1.0:
                terms = [-math.inf]
                break
            terms.append(count * math.log1p(change))
        components.append(math.fsum(terms))
    maximum = max(components)
    # The smaller fixed stakes remain strictly positive for every allowed m/X,
    # so the whole mixture never has log(0), even at support boundaries.
    return maximum + math.log(math.fsum(math.exp(x - maximum) for x in components)) - math.log(len(LAMBDAS))


def _interval(counts):
    threshold = math.log(TAIL_THRESHOLD)
    if _log_capital(counts, 0.0, 1) <= threshold:
        lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = (lo + hi) / 2.0
            if _log_capital(counts, mid, 1) > threshold:
                lo = mid
            else:
                hi = mid
        # Round outward so numerical approximation never narrows the bound.
        lower = lo
    if _log_capital(counts, 1.0, -1) <= threshold:
        upper = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(64):
            mid = (lo + hi) / 2.0
            if _log_capital(counts, mid, -1) > threshold:
                hi = mid
            else:
                lo = mid
        upper = hi
    return {"lower": lower, "upper": upper}


def _elo(score):
    if score is None:
        return {"value": None, "interpretation": "no_complete_pairs"}
    if score in (0.0, 1.0):
        return {"value": None, "interpretation": "negative_infinity" if score == 0 else "positive_infinity"}
    return {"value": 400.0 / math.log(10.0) * (math.log(score) - math.log1p(-score)),
            "interpretation": "finite_score_transform"}


def summarize(scores, *, expected_pairs=DEFAULT_PAIRS, experiment_complete=False):
    """Return descriptive scores and conditional inference only at exact completion.

    Malformed scores/arguments raise ValueError. Incomplete, short or overlong
    samples retain descriptive counts but withhold interval, test capital and
    decision. expected_pairs must be frozen by the caller before game play; its
    configurable value supports other declared experiments and synthetic tests,
    not selecting an advantageous stopping point. No identity or forfeit audit
    is possible from the score vector alone.
    """
    if isinstance(expected_pairs, bool) or not isinstance(expected_pairs, int) or expected_pairs <= 0:
        raise ValueError("expected_pairs must be a positive integer")
    if type(experiment_complete) is not bool:
        raise ValueError("experiment_complete must be boolean")
    counts = _counts(scores)
    size = sum(counts)
    score = math.fsum(value * count for value, count in zip(SCORES, counts)) / size if size else None
    withheld = []
    if not experiment_complete:
        withheld.append("predeclared_experiment_not_complete")
    if size != expected_pairs:
        withheld.append("sample_size_differs_from_predeclared_count")
    interval = None
    capital = None
    decision = "unqualified"
    if not withheld:
        interval = _interval(counts)
        capital = {"positive": _log_capital(counts, 0.5, 1),
                   "negative": _log_capital(counts, 0.5, -1)}
        decision = ("positive" if interval["lower"] > 0.5 else
                    "negative" if interval["upper"] < 0.5 else "inconclusive")
    return {
        "schema_version": 1, "method": METHOD,
        "sample_size_pairs": size, "expected_pairs": expected_pairs,
        "experiment_complete": experiment_complete,
        "pair_score_counts": {str(value): count for value, count in zip(SCORES, counts)},
        "score": score, "relative_elo": _elo(score),
        "confidence": CONFIDENCE, "lambda_grid": list(LAMBDAS),
        "mixture_weights": [1.0 / len(LAMBDAS)] * len(LAMBDAS),
        "per_tail_threshold": TAIL_THRESHOLD,
        "log_e_value_at_half": capital, "score_interval": interval,
        "relative_elo_interval": ({key: _elo(value) for key, value in interval.items()} if interval else None),
        "inference_eligible": not withheld, "withheld_reasons": withheld,
        "decision": decision,
        "interpretation": "Conditional finite-sample 95% interval for a common pair-score mean, or the fixed-sample average mean under independence. Within-pair dependence is allowed. Distribution assumptions and valid sample provenance are not certified by this helper. Relative Elo is only a score transform. No automatic promotion follows."
    }
