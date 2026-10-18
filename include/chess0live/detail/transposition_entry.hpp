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

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace chess0live::detail::transposition {

enum class Bound : std::uint8_t { empty, exact, lower, upper };

/** Preserve the original bucket count for every public Hash budget. Using the
 * smaller physical bucket size here would change the index mask, collisions,
 * replacement decisions and search tree, rather than just the representation.
 */
inline constexpr std::size_t bucket_budget_bytes = 96;

/** Single-worker entry representation. The complete key, score, and generation
 * remain intact. Move squares/promotion occupy a byte each (including invalid
 * square 64); the four legal flag bits share a byte with the two bound bits.
 * Depth is unsigned because only positive main-search depths are stored; the
 * search boundary proves and checks that its maximum fits this byte.
 *
 * This layout has no concurrent publication guarantees. Shared-table SMP needs
 * an explicit race-safe design; a small or aligned entry is not automatically
 * atomic. Default construction must preserve Move{}'s invalid-square sentinel.
 */
struct Entry {
    std::uint64_t key = 0;
    std::uint32_t move_bound = pack(Move{}, Bound::empty);
    std::int16_t score = 0;
    std::uint8_t depth = 0;
    std::uint8_t generation = 0;

    constexpr Entry() = default;
    constexpr Entry(std::uint64_t key_value, Move move_value, std::int16_t score_value,
                    std::uint8_t depth_value, Bound bound_value, std::uint8_t generation_value)
        : key(key_value), move_bound(pack(move_value, bound_value)), score(score_value),
          depth(depth_value), generation(generation_value) {}

    constexpr Move move() const {
        return {static_cast<std::uint8_t>(move_bound),
                static_cast<std::uint8_t>(move_bound >> 8),
                static_cast<PieceType>(static_cast<std::uint8_t>(move_bound >> 16)),
                static_cast<std::uint8_t>((move_bound >> 24) & 0x0fU)};
    }

    constexpr Bound bound() const {
        return static_cast<Bound>((move_bound >> 28) & 0x03U);
    }

private:
    static constexpr std::uint32_t pack(Move move, Bound bound) {
        assert(move.flags <= 0x0fU);
        assert(static_cast<unsigned>(bound) <= static_cast<unsigned>(Bound::upper));
        return std::uint32_t(move.from) | (std::uint32_t(move.to) << 8)
            | (std::uint32_t(move.promotion) << 16) | (std::uint32_t(move.flags) << 24)
            | (std::uint32_t(bound) << 28);
    }
};

/** Keep a four-entry bucket within conventional 64/128-byte cache lines. This
 * fixed portable alignment does not assert a universal hardware line size.
 */
struct alignas(64) Bucket { std::array<Entry, 4> entries; };
static_assert(sizeof(Entry) == 16);
static_assert(sizeof(Bucket) == 64 && alignof(Bucket) == 64);

} // namespace chess0live::detail::transposition
