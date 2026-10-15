#!/usr/bin/env python3
"""Check or run the fixed Phase 2D isolated LMR qualification, once, in foreground.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

Checking never searches an opening. Running requires a new campaign directory
and the Helsinki night window, unless the owner explicitly authorizes the
--allow-daytime exception. Every run stops at the next Helsinki 07:00, retaining
incomplete evidence and waiting for child cleanup. No scheduling or resumption.
"""
from pathlib import Path

import match
import qualification as shared

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ID = "phase2d-lmr-128-v1"
CHESS_VERSION = "1.11.2"
PAIRS = 64
SEED = 20261015
FROZEN = {
    "engine": (ROOT / "build/experiments/lmr-20261014/chess0live",
               "b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc"),
    "network": (ROOT / "networks/nn-1a298aa575a0.nnue",
                "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"),
    "openings": (ROOT / "tests/data/openings-lmr-validation.json",
                 "1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7"),
}
SOURCES = ("tools/qualify_lmr.py", "tools/qualification.py", "tools/match.py",
           "tools/match_statistics.py", "tools/resources.py", "tools/audit_lmr.py",
           "tools/audit_time_policy.py", "requirements-match.txt",
           "docs/SELECTIVE_SEARCH.md", "docs/PHASE_2D_LMR.md")
PROTOCOL_DOCUMENT = "docs/PHASE_2D_LMR.md"
ROLE_OPTIONS = ((("Time Policy", "classic"), ("Late Move Reductions", "true")),
                (("Time Policy", "classic"), ("Late Move Reductions", "false")))
REVISIONS = ("phase2-lmr-on-b825a09", "phase2-lmr-off-b825a09")
CHECK_OPTIONS = ("Late Move Reductions",)


# These facades retain the original public helpers and CLI. Workflow logic lives
# in qualification.py, so future profiles share cancellation and evidence rules.
WindowExpired = shared.WindowExpired
configuration_hash = shared.configuration_hash
utc_now = shared.utc_now


def profile():
    return shared.QualificationProfile(
        ROOT, PROTOCOL_ID, CHESS_VERSION, PAIRS, SEED, FROZEN, SOURCES,
        PROTOCOL_DOCUMENT, ROLE_OPTIONS, REVISIONS, CHECK_OPTIONS)


def launch_policy(now=None, allow_daytime=False, require_window=False):
    return shared.launch_policy(now or utc_now(), allow_daytime, require_window)


def fixed_request():
    return shared.fixed_request(profile())


def configuration(specs, settings):
    return shared.configuration(profile(), specs, settings)


def snapshot():
    return shared.snapshot(profile())


def validate_options(protocol, configured, spec, settings):
    return shared.validate_options(profile(), protocol, configured, spec, settings)


async def check():
    return await shared.check(profile(), request=fixed_request, clock=utc_now, window=launch_policy)


def verify_unchanged(report, specs, settings):
    return shared.verify_unchanged(profile(), report, specs, settings)


async def run(output, allow_daytime=False):
    return await shared.run(profile(), output, allow_daytime, preflight=check,
                            request=fixed_request, clock=utc_now, window=launch_policy)


def main(argv=None):
    return shared.main(argv, description=__doc__, check_fn=check, run_fn=run)


if __name__ == "__main__":
    raise SystemExit(main())
