/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Test-only access follows tools/oracle/chess0live_stages.cpp. Do not link this
// translation unit with nnue.o: it already includes that implementation.
#include "../src/nnue.cpp"

#include <iostream>
#include <map>
#include <type_traits>

namespace {
using chess0live::nnue::Accumulation;
using chess0live::nnue::buckets;
using chess0live::nnue::differences;
using chess0live::nnue::width;
using FeatureList = std::vector<std::uint32_t>;

static_assert(width == 1024 && buckets == 8, "This test targets the pinned SFNNv16 shape");
constexpr std::size_t feature_count = 67;
std::size_t checked_transitions = 0;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

std::uint64_t random_bits(std::uint64_t& seed) {
    seed ^= seed << 13;
    seed ^= seed >> 7;
    seed ^= seed << 17;
    return seed;
}

template<class Weight> struct Columns {
    std::vector<Weight> hidden = std::vector<Weight>(feature_count * width);
    std::vector<std::int32_t> psqt = std::vector<std::int32_t>(feature_count * buckets);

    Columns() {
        static_assert(std::is_same_v<Weight, std::int8_t> || std::is_same_v<Weight, std::int16_t>);
        std::uint64_t seed = 0x4e4e554544454c54ULL;
        using Bits = std::make_unsigned_t<Weight>;
        for (std::size_t feature = 0; feature < feature_count; ++feature) {
            for (std::size_t lane = 0; lane < width; ++lane) {
                auto value = std::bit_cast<Weight>(static_cast<Bits>(random_bits(seed)));
                // Constant columns force repeated wraps; the remaining columns
                // distinguish every lane and feature instead of hiding strides.
                if (feature == 0) value = 0;
                if (feature == 1) value = 1;
                if (feature == 2) value = std::numeric_limits<Weight>::min();
                if (feature == 3) value = std::numeric_limits<Weight>::max();
                if (feature == 4) value = -1;
                hidden[feature * width + lane] = value;
            }
            for (std::size_t lane = 0; lane < buckets; ++lane) {
                auto value = std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(random_bits(seed)));
                if (feature == 0) value = 0;
                if (feature == 1) value = 1;
                if (feature == 2) value = std::numeric_limits<std::int32_t>::min();
                if (feature == 3) value = std::numeric_limits<std::int32_t>::max();
                if (feature == 4) value = -1;
                psqt[feature * buckets + lane] = value;
            }
        }
        // Isolate the ends of common vector blocks, including the final lane.
        // A missing/repeated lane cannot be masked by identical neighbors.
        constexpr std::array<std::size_t, 19> edges{
            0, 1, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128,
            255, 256, 511, 512, 1015, 1016, 1023};
        std::fill_n(hidden.begin() + 5 * width, width, Weight{0});
        for (std::size_t index = 0; index < edges.size(); ++index)
            hidden[5 * width + edges[index]] = static_cast<Weight>(int(index) - 9);
    }
};

Accumulation starting_state(unsigned phase = 0) {
    Accumulation result;
    constexpr std::array<std::int16_t, 12> hidden{
        -32768, 32767, -32767, 32766, -1, 0, 1, 127, -128, 255, -256, 16384};
    constexpr std::array<std::int32_t, 8> psqt{
        std::numeric_limits<std::int32_t>::min(), std::numeric_limits<std::int32_t>::max(),
        -1, 0, 1, 0x40000000, -0x40000000, 0x12345678};
    for (std::size_t lane = 0; lane < width; ++lane)
        result.hidden[lane] = hidden[(lane + phase) % hidden.size()];
    for (std::size_t lane = 0; lane < buckets; ++lane)
        result.psqt[lane] = psqt[(lane + phase) % psqt.size()];
    // differences owns lane arithmetic only; feature-list ownership belongs to
    // update. Sentinels catch accidental modifications to that separate state.
    result.active.psq = {19, 3, 19};
    result.active.relations = {2, 7, 11, 7};
    return result;
}

/** Independent oracle: count signed multiplicities, then apply whole columns.
 * This intentionally does not reproduce the production sorted-list merge and
 * never calls adjust or any batching helper. Unsigned representations define
 * wraparound explicitly, including subtraction of INT16_MIN/INT32_MIN.
 */
template<class Weight> void reference(Accumulation& state, const FeatureList& before,
                                     const FeatureList& after, const Columns<Weight>& columns) {
    std::map<std::uint32_t, std::int64_t> counts;
    for (const auto feature : before) --counts[feature];
    for (const auto feature : after) ++counts[feature];
    for (const auto& [feature, count] : counts) {
        const auto repetitions = count < 0 ? -count : count;
        for (std::int64_t occurrence = 0; occurrence < repetitions; ++occurrence) {
            for (std::size_t lane = 0; lane < width; ++lane) {
                const auto old = std::bit_cast<std::uint16_t>(state.hidden[lane]);
                const auto delta = static_cast<std::uint16_t>(columns.hidden[feature * width + lane]);
                const auto next = static_cast<std::uint16_t>(count > 0 ? old + delta : old - delta);
                state.hidden[lane] = std::bit_cast<std::int16_t>(next);
            }
            for (std::size_t lane = 0; lane < buckets; ++lane) {
                const auto old = std::bit_cast<std::uint32_t>(state.psqt[lane]);
                const auto delta = std::bit_cast<std::uint32_t>(columns.psqt[feature * buckets + lane]);
                const std::uint32_t next = count > 0 ? old + delta : old - delta;
                state.psqt[lane] = std::bit_cast<std::int32_t>(next);
            }
        }
    }
}

void equal_state(const Accumulation& actual, const Accumulation& expected, const std::string& label) {
    for (std::size_t lane = 0; lane < width; ++lane)
        require(actual.hidden[lane] == expected.hidden[lane], label + ": hidden lane " + std::to_string(lane));
    for (std::size_t lane = 0; lane < buckets; ++lane)
        require(actual.psqt[lane] == expected.psqt[lane], label + ": PSQT lane " + std::to_string(lane));
    require(actual.active.psq == expected.active.psq && actual.active.relations == expected.active.relations,
            label + ": active features unexpectedly modified");
}

template<class Weight> void step(Accumulation& actual, Accumulation& expected,
    const FeatureList& before, const FeatureList& after, const Columns<Weight>& columns,
    const std::string& label) {
    require(std::is_sorted(before.begin(), before.end()) && std::is_sorted(after.begin(), after.end()),
            label + ": fixture lists must respect the sorted-input contract");
    const auto saved_before = before, saved_after = after;
    differences(actual, before, after, columns.hidden, columns.psqt);
    reference(expected, before, after, columns);
    equal_state(actual, expected, label);
    require(before == saved_before && after == saved_after, label + ": input lists changed");
    ++checked_transitions;
}

template<class Weight> void roundtrip(const FeatureList& before, const FeatureList& after,
    const Columns<Weight>& columns, const std::string& label, unsigned phase = 0) {
    const auto initial = starting_state(phase);
    auto actual = initial, expected = initial;
    step(actual, expected, before, after, columns, label);
    step(actual, expected, after, before, columns, label + " reverse");
    equal_state(actual, initial, label + " restoration");
}

FeatureList repeated(std::size_t count, std::uint32_t feature) { return FeatureList(count, feature); }

template<class Weight> void suite() {
    const Columns<Weight> columns;
    const std::string label = sizeof(Weight) == 1 ? "int8" : "int16";
    roundtrip({}, {}, columns, label + " empty");
    roundtrip({1, 1, 2, 66}, {1, 1, 2, 66}, columns, label + " unchanged multiset");
    roundtrip({}, {0, 1, 2, 3, 4, 5, 66}, columns, label + " additions");
    roundtrip({0, 1, 2, 3, 4, 5, 66}, {}, columns, label + " removals", 3);
    roundtrip({0, 1, 1, 1, 2, 4, 5, 5, 66}, {0, 1, 2, 2, 3, 4, 5, 66, 66},
              columns, label + " overlapping multiplicities", 7);
    roundtrip({1, 3, 5, 7, 9, 11, 13}, {0, 2, 4, 6, 8, 10, 12, 14},
              columns, label + " alternating signs", 5);
    roundtrip({}, {5}, columns, label + " vector edge lanes", 1);

    // Boundary sizes are independent of the candidate's batch constant. Include
    // exact powers and both neighbors, then changes far larger than legal sets
    // to expose truncation or an unflushed tail in bounded implementations.
    constexpr std::array<std::size_t, 27> sizes{
        1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 31, 32, 33,
        63, 64, 65, 127, 128, 129, 255, 256, 257, 511, 512, 513, 4097};
    for (const auto size : sizes) {
        FeatureList before, after;
        for (std::size_t index = 0; index < size; ++index) {
            before.push_back(static_cast<std::uint32_t>((index * 3) % feature_count));
            after.push_back(static_cast<std::uint32_t>((index * 5 + 1) % feature_count));
        }
        std::sort(before.begin(), before.end());
        std::sort(after.begin(), after.end());
        roundtrip(before, after, columns, label + " size " + std::to_string(size), static_cast<unsigned>(size));
        roundtrip({}, repeated(size, 2), columns, label + " repeated minimum " + std::to_string(size));
    }
    roundtrip({}, repeated(32769, 3), columns, label + " huge repeated maximum", 9);
    roundtrip(repeated(8193, 2), repeated(8193, 3), columns, label + " huge two-sided change", 11);
    roundtrip(repeated(32769, 4), repeated(32769, 4), columns, label + " huge unchanged multiplicity");

    // Retain arbitrary accumulated state between unrelated lists. This checks
    // that no hidden batch state leaks across calls, including empty transitions.
    auto actual = starting_state(4), expected = actual;
    FeatureList before;
    std::uint64_t seed = 0x434f4c554d4e5355ULL;
    for (unsigned iteration = 0; iteration < 48; ++iteration) {
        FeatureList after;
        const auto count = iteration % 8 == 0 ? 0 : random_bits(seed) % 401;
        for (std::uint64_t index = 0; index < count; ++index)
            after.push_back(static_cast<std::uint32_t>(random_bits(seed) % feature_count));
        std::sort(after.begin(), after.end());
        step(actual, expected, before, after, columns, label + " transition " + std::to_string(iteration));
        before = std::move(after);
    }
    step(actual, expected, before, {}, columns, label + " final empty transition");
    equal_state(actual, starting_state(4), label + " sequence restoration");

    // Closed-form anchors independently check the reference's modular direction.
    actual = starting_state();
    actual.hidden[0] = std::numeric_limits<std::int16_t>::max();
    actual.psqt[0] = std::numeric_limits<std::int32_t>::max();
    expected = actual;
    step(actual, expected, {}, {1}, columns, label + " overflow anchor");
    require(actual.hidden[0] == std::numeric_limits<std::int16_t>::min()
                && actual.psqt[0] == std::numeric_limits<std::int32_t>::min(),
            label + ": adding one must wrap to minimum");
    step(actual, expected, {1}, {}, columns, label + " underflow anchor");
    require(actual.hidden[0] == std::numeric_limits<std::int16_t>::max()
                && actual.psqt[0] == std::numeric_limits<std::int32_t>::max(),
            label + ": subtracting one must wrap to maximum");

    // With no deltas, empty storage is valid and must never be dereferenced.
    actual = starting_state();
    differences(actual, {}, {}, std::vector<Weight>{}, std::vector<std::int32_t>{});
    equal_state(actual, starting_state(), label + " no weight storage");
    ++checked_transitions;
}
} // namespace

int main() {
    try {
        suite<std::int8_t>();
        suite<std::int16_t>();
        std::cout << "NNUE update arithmetic: " << checked_transitions
                  << " independent multiset transitions passed (int8/int16, modular lanes, reversal)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "NNUE update arithmetic failure: " << error.what() << '\n';
        return 1;
    }
}
