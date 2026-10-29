/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include <filesystem>
#include <memory>
#include <string>

namespace chess0live {
class Position;

namespace nnue {

/** Exact integer outputs of the pinned SFNNv16 network, in internal units. */
struct Raw {
    int psqt = 0;
    int positional = 0;
    constexpr bool operator==(const Raw&) const = default;
};

/** Immutable weights after a successful load; shared safely by search workers.
 * A failed load preserves the previous network. Evaluators must not run while
 * this object is loading a replacement. See docs/NNUE.md for the format pin.
 */
class Network {
public:
    Network();
    ~Network();
    Network(Network&&) noexcept;
    Network& operator=(Network&&) noexcept;
    Network(const Network&) = delete;
    Network& operator=(const Network&) = delete;
    bool load(const std::filesystem::path& path, std::string& error);
    [[nodiscard]] bool loaded() const noexcept;
    /** Full-refresh evaluation, intended as a correctness reference. */
    [[nodiscard]] Raw evaluate(const Position& position) const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
    friend class Evaluator;
};

/** Worker-local incremental accumulator. Never share one between workers.
 * Changed board squares select exact piece-square, threat and pawn-pair deltas
 * across arbitrary transitions, including make/unmake. King-orientation changes
 * refresh that perspective; the first evaluation after reset refreshes both.
 * Both update plans are prepared before either accumulator changes.
 */
class Evaluator {
public:
    explicit Evaluator(const Network& network);
    ~Evaluator();
    Evaluator(const Evaluator&) = delete;
    Evaluator& operator=(const Evaluator&) = delete;
    [[nodiscard]] Raw raw(const Position& position);
    /** Material/rule-50 calibrated evaluation; search optimism is zero. */
    [[nodiscard]] int evaluate(const Position& position);
    void reset();
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace nnue
} // namespace chess0live
