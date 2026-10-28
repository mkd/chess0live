/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/detail/continuation_history.hpp"

#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <stdexcept>
#include <string>
#include <string_view>

namespace allocation_fault {
// Fail only this small table's exact allocation once, without memory pressure.
thread_local std::size_t bytes = 0;
}
void* operator new(std::size_t size) {
    if (size != 0 && size == allocation_fault::bytes) {
        allocation_fault::bytes = 0;
        throw std::bad_alloc{};
    }
    if (void* pointer = std::malloc(size == 0 ? 1 : size)) return pointer;
    throw std::bad_alloc{};
}
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete[](void* pointer) noexcept { std::free(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new(std::size_t size, const std::nothrow_t&) noexcept {
    try { return ::operator new(size); } catch (...) { return nullptr; }
}
void* operator new[](std::size_t size, const std::nothrow_t&) noexcept {
    try { return ::operator new[](size); } catch (...) { return nullptr; }
}
void operator delete(void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }
void operator delete[](void* pointer, const std::nothrow_t&) noexcept { std::free(pointer); }

namespace {
using chess0live::Color;
using chess0live::Piece;
using chess0live::PieceType;
using chess0live::make_piece;
using History = chess0live::detail::ContinuationHistory;

constexpr std::size_t table_entries = 768 * 768;
constexpr std::size_t table_bytes = table_entries * sizeof(std::int16_t);
std::size_t checks = 0;

void require(bool condition, std::string_view message) {
    ++checks;
    if (!condition) throw std::runtime_error(std::string(message));
}

void require_empty(const History& history) {
    require(!history.enabled(), "disabled table reports enabled");
    require(history.entries() == 0, "disabled table retains entries");
    require(history.allocated_bytes() == 0, "disabled table retains allocation");
    require(history.value(0, 0) == 0, "disabled table returns a score");
}

void require_zeroes(const History& history) {
    for (std::size_t previous = 0; previous < History::context_count; ++previous)
        for (std::size_t current = 0; current < History::context_count; ++current)
            require(history.value(previous, current) == 0, "table contains stale history");
}

/**
 * Independent arithmetic oracle: bounded products are exact in floating point
 * (at most 2^28, divided by 2^14), then truncation specifies integer gravity.
 */
int reference_update(int old, int bonus) {
    const int bounded = bonus < -16384 ? -16384 : bonus > 16384 ? 16384 : bonus;
    const int magnitude = bounded < 0 ? -bounded : bounded;
    const auto damping = std::trunc(static_cast<long double>(old) * magnitude / 16384.0L);
    return old + bounded - static_cast<int>(damping);
}

void context_encoding() {
    static_assert(History::context_count == 768);
    static_assert(History::no_context == 768);
    static_assert(History::context(Piece{1}, 0) == 0);
    static_assert(History::context(Piece{-6}, 63) == 767);
    std::array<bool, 768> seen{};
    for (const Color color : {Color::white, Color::black}) {
        for (int type = 1; type <= 6; ++type) {
            for (unsigned square = 0; square < 64; ++square) {
                const auto context = History::context(
                    make_piece(color, static_cast<PieceType>(type)), square);
                require(context < seen.size(), "valid piece/destination rejected");
                require(!seen[context], "colored piece/destination contexts collide");
                seen[context] = true;
            }
        }
    }
    for (const bool occupied : seen) require(occupied, "context encoding leaves a hole");
    for (const Piece piece : {Piece{0}, Piece{7}, Piece{-7},
                              std::numeric_limits<Piece>::min(),
                              std::numeric_limits<Piece>::max()}) {
        require(History::context(piece, 0) == History::no_context,
                "invalid piece accepted as context");
    }
    for (const unsigned square : {64U, std::numeric_limits<unsigned>::max()})
        require(History::context(Piece{1}, square) == History::no_context,
                "invalid destination accepted as context");
}

void disabled_and_allocation_lifecycle() {
    History history;
    require_empty(history);
    history.update(0, 0, 500);
    history.clear();
    history.decay();
    history.enable(false);
    require_empty(history);

    allocation_fault::bytes = table_bytes;
    bool failed = false;
    try { history.enable(true); } catch (const std::bad_alloc&) { failed = true; }
    require(failed && allocation_fault::bytes == 0, "table allocation failure was not injected");
    require_empty(history);
    history.clear();
    history.decay();
    history.enable(true);
    require(history.enabled(), "enable did not allocate the table");
    require(history.entries() == table_entries, "incorrect table dimensions");
    require(history.allocated_bytes() >= table_bytes, "reported storage is too small");
    require_zeroes(history);
    const auto allocation = history.allocated_bytes();

    history.update(7, 11, 1234);
    allocation_fault::bytes = table_bytes;
    history.enable(true);
    require(allocation_fault::bytes == table_bytes, "redundant enable allocated again");
    allocation_fault::bytes = 0;
    require(history.value(7, 11) == 1234, "redundant enable erased learned history");
    require(history.allocated_bytes() == allocation, "redundant enable changed storage");

    history.clear();
    require(history.enabled() && history.allocated_bytes() == allocation,
            "clear changed table ownership");
    require_zeroes(history);
    history.update(7, 11, -900);
    history.enable(false);
    require_empty(history);

    allocation_fault::bytes = table_bytes;
    failed = false;
    try { history.enable(true); } catch (const std::bad_alloc&) { failed = true; }
    require(failed && allocation_fault::bytes == 0, "re-enable failure was not injected");
    require_empty(history);
    history.enable(true);
    require_zeroes(history);
}

void isolation_and_sentinels() {
    History history;
    history.enable(true);
    constexpr auto previous = History::context(Piece{-2}, 21);
    constexpr auto current = History::context(Piece{1}, 28);
    history.update(previous, current, 731);
    require(history.value(previous, current) == 731, "valid update was lost");
    for (const auto alternate : {History::context(Piece{2}, 21),
                                 History::context(Piece{-3}, 21),
                                 History::context(Piece{-2}, 22)}) {
        require(history.value(alternate, current) == 0,
                "previous color/piece/destination leaked into another reply context");
        history.update(alternate, current, -83);
    }
    for (const auto alternate : {History::context(Piece{-1}, 28),
                                 History::context(Piece{2}, 28),
                                 History::context(Piece{1}, 29)}) {
        require(history.value(previous, alternate) == 0,
                "current color/piece/destination leaked into another reply context");
        history.update(previous, alternate, 47);
    }
    require(history.value(previous, current) == 731, "distinct updates changed target reply");
    require(history.value(current, previous) == 0, "previous/current order was ignored");

    for (const auto absent : {History::no_context, History::no_context + 1,
                              std::numeric_limits<std::size_t>::max()}) {
        history.update(absent, current, std::numeric_limits<int>::max());
        history.update(previous, absent, std::numeric_limits<int>::min());
        history.update(absent, absent, 100);
        require(history.value(absent, current) == 0 && history.value(previous, absent) == 0
                    && history.value(absent, absent) == 0,
                "absent context accessed history");
    }
    require(history.value(previous, current) == 731, "invalid update corrupted valid history");
    history.update(History::context(Piece{-6}, 63), History::context(Piece{6}, 63), -99);
    require(history.value(767, 383) == -99, "last context cannot be updated");
}

void gravity_and_decay() {
    History history;
    history.enable(true);
    std::array<int, 8> expected{};
    constexpr std::array bonuses{0, 1, -1, 73, -93, 1024, -4096, 16383, -16383,
                                 16384, -16384, 16385, -16385,
                                 std::numeric_limits<int>::min(), std::numeric_limits<int>::max()};
    // Distinct contexts deliberately share both rows and columns. A repeatable
    // stream checks gradual damping, sign changes, clipping and extreme input.
    std::uint32_t state = 0x31c0a57U;
    for (unsigned step = 0; step < 20000; ++step) {
        state = state * 1664525U + 1013904223U;
        const auto cell = (state >> 16) % expected.size();
        const int bonus = bonuses[(state >> 4) % bonuses.size()];
        expected[cell] = reference_update(expected[cell], bonus);
        const auto previous = cell / 4;
        const auto current = cell % 4;
        history.update(previous, current, bonus);
        require(history.value(previous, current) == expected[cell], "gravity differs from reference");
        require(history.value(previous, current) >= -16384
                    && history.value(previous, current) <= 16384,
                "gravity escaped its representable bound");
    }

    for (const int bonus : {16384, std::numeric_limits<int>::max()}) {
        history.update(9, 10, bonus);
        history.update(9, 10, bonus);
        require(history.value(9, 10) == 16384, "positive saturation is incorrect");
    }
    for (const int bonus : {-16384, std::numeric_limits<int>::min()}) {
        history.update(9, 10, bonus);
        history.update(9, 10, bonus);
        require(history.value(9, 10) == -16384, "negative saturation is incorrect");
    }
    history.update(9, 10, 16384);
    require(history.value(9, 10) == 16384, "opposite full bonus failed to reverse saturation");
    history.update(9, 10, 0);
    require(history.value(9, 10) == 16384, "zero bonus changed learned history");

    history.clear();
    history.update(0, 0, 5);
    history.update(0, 1, -5);
    history.update(767, 767, -16384);
    const auto allocation = history.allocated_bytes();
    history.decay();
    require(history.value(0, 0) == 2 && history.value(0, 1) == -2,
            "decay does not truncate both signs toward zero");
    require(history.value(767, 767) == -8192, "decay skipped the table boundary");
    require(history.enabled() && history.allocated_bytes() == allocation,
            "decay changed table ownership");
    for (unsigned i = 0; i < 14; ++i) history.decay();
    require_zeroes(history);
}
} // namespace

int main() {
    try {
        context_encoding();
        disabled_and_allocation_lifecycle();
        isolation_and_sentinels();
        gravity_and_decay();
        std::cout << "Continuation history: " << checks << " checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        allocation_fault::bytes = 0;
        std::cerr << "Continuation history test failed: " << error.what() << '\n';
        return 1;
    }
}
