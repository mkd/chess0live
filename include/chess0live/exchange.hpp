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

namespace chess0live {
class Position;

/** Material estimate for a legal move followed by captures on its destination.
 * The initial move is mandatory; each subsequent side may stop or use its
 * least-valued legal attacker, breaking ties by ascending source square. Later
 * pawn promotions choose a queen and include its added material. Initial
 * promotions use the supplied piece. Ordinary quiet moves return zero.
 *
 * This is a legal LVA exchange heuristic, not tactical minimax: alternative
 * attackers, off-target threats/evasions, and mating consequences are absent.
 * Even a checked side may stop the hypothetical exchange. It is suitable for
 * ordering moves, never for proving that a sacrifice or legal move is unsound.
 * The position, its history, and its incremental evaluation remain untouched.
 * Precondition: move is legal in position.
 */
int static_exchange(const Position& position, Move move) noexcept;

} // namespace chess0live
