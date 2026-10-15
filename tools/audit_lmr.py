#!/usr/bin/env python3
"""Audit the isolated 128-game Phase 2D LMR screen without running an engine.

Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

These constants are independent of the launcher. A campaign cannot supply its
own sample, options, pins, or decision rule to pass this audit.
"""
from audit_time_policy import AuditProtocol, audit as audit_campaign, main

PROTOCOL = AuditProtocol(
    protocol_id="phase2d-lmr-128-v1", pairs=64, seed=20261015,
    protocol_document="docs/PHASE_2D_LMR.md",
    role_options=(("candidate", (("Time Policy", "classic"), ("Late Move Reductions", "true"))),
                  ("opponent", (("Time Policy", "classic"), ("Late Move Reductions", "false")))),
    required_sources=("tools/qualification.py", "tools/qualify_lmr.py", "tools/audit_lmr.py",
                      "tools/audit_time_policy.py", "tools/match.py", "tools/match_statistics.py",
                      "tools/resources.py"),
    pinned_sha256=(("engine", "b825a09efab86d177c08c49a87919bbf1652ec213fae794a3f3b26f365710edc"),
                   ("network", "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"),
                   ("openings", "1627ddfaf83191db1e74274c2de5a43d84a0c41658804314acbe2274eb07c2b7")),
    entrypoint="tools/audit_lmr.py")


def audit(campaign):
    return audit_campaign(campaign, PROTOCOL)


if __name__ == "__main__":
    raise SystemExit(main(PROTOCOL))
