/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include "chess0live/types.hpp"

#include <cstdint>

namespace chess0live::detail::transposition {

/** Position-only ordering suggestion, never a score or searched bound.
 * Preserve the complete move, including flags and promotion, for exact matching
 * against the current legal list. The invalid Move sentinel marks an empty slot
 * independently of key, so a real zero key remains representable. Publication
 * uses the score table's existing stripe locks; this entry is not atomic.
 */
struct MoveHintEntry {
    std::uint64_t key = 0;
    Move move{};
};
static_assert(sizeof(MoveHintEntry) == 16);

} // namespace chess0live::detail::transposition
