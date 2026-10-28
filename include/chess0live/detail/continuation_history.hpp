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

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace chess0live::detail {

/**
 * Worker-private quiet-reply history, indexed by two piece/destination contexts.
 *
 * The caller controls which searches may consult or train this ordering table.
 * It contains no position scores, move legality information, or shared state.
 * Disabling the experiment releases its storage; enabling it starts with zeros.
 */
class ContinuationHistory {
public:
    static constexpr std::size_t context_count = 12 * 64;
    static constexpr std::size_t no_context = context_count;

    /**
     * Encode a colored moving piece and destination, or an absent context.
     * Supply the original moving piece: a promotion's context is still a pawn.
     * Empty/invalid pieces and squares outside a1..h8 are never valid indices.
     */
    static constexpr std::size_t context(Piece piece, unsigned square) noexcept {
        const int signed_piece = static_cast<int>(piece);
        if (signed_piece == 0 || signed_piece < -6 || signed_piece > 6 || square >= 64)
            return no_context;
        const auto type_index = static_cast<std::size_t>(
            signed_piece < 0 ? -signed_piece - 1 : signed_piece - 1);
        const std::size_t color_offset = signed_piece < 0 ? 6 : 0;
        return (color_offset + type_index) * 64 + square;
    }

    /**
     * Allocate only on the disabled-to-enabled transition. A failed allocation
     * leaves the object unchanged, and redundant enabling preserves learned data.
     */
    void enable(bool active) {
        if (active) {
            if (enabled()) return;
            std::vector<std::int16_t> replacement(context_count * context_count, 0);
            scores_.swap(replacement);
        } else {
            // clear() alone retains capacity; disabled workers must own no table.
            std::vector<std::int16_t>{}.swap(scores_);
        }
    }

    [[nodiscard]] bool enabled() const noexcept { return !scores_.empty(); }
    [[nodiscard]] std::size_t entries() const noexcept { return scores_.size(); }
    [[nodiscard]] std::size_t allocated_bytes() const noexcept {
        return scores_.capacity() * sizeof(std::int16_t);
    }

    /** Forget learned replies without changing enabled state or allocation. */
    void clear() noexcept { std::fill(scores_.begin(), scores_.end(), std::int16_t{0}); }

    /** Age every reply symmetrically; integer division truncates toward zero. */
    void decay() noexcept {
        for (auto& score : scores_) score = static_cast<std::int16_t>(score / 2);
    }

    /** An absent previous move, invalid context, or disabled table has no bias. */
    [[nodiscard]] int value(std::size_t previous, std::size_t current) const noexcept {
        if (!enabled() || previous >= context_count || current >= context_count) return 0;
        return scores_[previous * context_count + current];
    }

    /**
     * Apply bounded history gravity: h += b - h * abs(b) / limit.
     * Clamp before taking the magnitude so every int bonus, including INT_MIN,
     * is well-defined. Wide arithmetic and the bound keep stored values within
     * [-16384, 16384], while repeated evidence approaches rather than overflows it.
     */
    void update(std::size_t previous, std::size_t current, int bonus) noexcept {
        if (!enabled() || previous >= context_count || current >= context_count) return;
        auto& score = scores_[previous * context_count + current];
        const auto bounded = std::clamp<std::int64_t>(bonus, -limit, limit);
        const auto magnitude = bounded < 0 ? -bounded : bounded;
        const auto old = static_cast<std::int64_t>(score);
        score = static_cast<std::int16_t>(old + bounded - old * magnitude / limit);
    }

private:
    static constexpr std::int64_t limit = 16384;
    std::vector<std::int16_t> scores_;
};

} // namespace chess0live::detail
