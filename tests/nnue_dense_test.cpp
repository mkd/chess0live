/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Test-only access follows the update arithmetic and external stage adapters.
// This translation unit includes the implementation: do not link nnue.o too.
#include "../src/nnue.cpp"

#include <iostream>

namespace {
using chess0live::nnue::Dense;
std::size_t checked_cases = 0, checked_outputs = 0;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

std::uint64_t random_bits(std::uint64_t& seed) {
    seed ^= seed << 13;
    seed ^= seed >> 7;
    seed ^= seed << 17;
    return seed;
}

/** Independent mathematical oracle: full scalar rows with int64 products/sums.
 * It shares neither the production NEON kernel nor its vector grouping, and
 * computes the format's final modulo-2^32 output only after adding the bias.
 */
template<std::size_t Inputs, std::size_t Outputs>
std::array<std::int32_t, Outputs> reference(const Dense<Inputs, Outputs>& layer,
                                           const std::array<std::uint8_t, Inputs>& input) {
    std::array<std::int32_t, Outputs> result{};
    for (std::size_t row = 0; row < Outputs; ++row) {
        std::int64_t total = layer.bias[row];
        for (std::size_t column = 0; column < Inputs; ++column)
            total += std::int64_t(input[column]) * layer.weight[row * Inputs + column];
        result[row] = std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(total));
    }
    return result;
}

template<std::size_t Inputs, std::size_t Outputs>
void check(const Dense<Inputs, Outputs>& layer, const std::array<std::uint8_t, Inputs>& input,
           const std::string& label) {
    const auto saved_input = input;
    const auto saved_bias = layer.bias;
    const auto saved_weight = layer.weight;
    for (const auto value : input)
        require(value <= 127, label + ": fixture violates the activation contract");
    const auto expected = reference(layer, input);
    // Repeated calls also cover retained state accidentally leaking between
    // invocations. The surrounding suite changes both inputs and model values.
    for (unsigned repeat = 0; repeat < 2; ++repeat) {
        const auto actual = layer.run(input.data());
        for (std::size_t row = 0; row < Outputs; ++row)
            require(actual[row] == expected[row], label + ": output " + std::to_string(row));
        require(input == saved_input && layer.bias == saved_bias && layer.weight == saved_weight,
                label + ": inference modified its input or model");
        checked_outputs += Outputs;
    }
    ++checked_cases;
}

template<std::size_t Inputs, std::size_t Outputs>
void randomize(Dense<Inputs, Outputs>& layer, std::array<std::uint8_t, Inputs>& input,
               std::uint64_t& seed) {
    for (auto& value : input) value = static_cast<std::uint8_t>(random_bits(seed) % 128);
    for (auto& value : layer.weight)
        value = std::bit_cast<std::int8_t>(static_cast<std::uint8_t>(random_bits(seed)));
    for (auto& value : layer.bias)
        value = std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(random_bits(seed)));
}

template<std::size_t Inputs, std::size_t Outputs> void suite() {
    Dense<Inputs, Outputs> layer;
    std::array<std::uint8_t, Inputs> input{};
    const std::string shape = std::to_string(Inputs) + "x" + std::to_string(Outputs);
    constexpr std::array<std::int32_t, 8> bias_edges{
        std::numeric_limits<std::int32_t>::min(), std::numeric_limits<std::int32_t>::max(),
        -1, 0, 1, 0x40000000, -0x40000000, 0x12345678};
    constexpr std::array<std::int8_t, 8> weight_edges{-128, 127, -127, 126, -1, 0, 1, 64};
    constexpr std::array<std::uint8_t, 8> activation_edges{0, 127, 1, 126, 63, 64, 2, 125};

    for (std::size_t row = 0; row < Outputs; ++row) layer.bias[row] = bias_edges[row % 8];
    for (std::size_t index = 0; index < layer.weight.size(); ++index)
        layer.weight[index] = weight_edges[index % 8];
    check(layer, input, shape + " zero activations");
    require(layer.run(input.data()) == layer.bias, shape + ": zero-input bias anchor");

    input.fill(127);
    layer.weight.fill(127);
    layer.bias.fill(std::numeric_limits<std::int32_t>::max());
    check(layer, input, shape + " maximum positive dot product and bias wrap");
    layer.weight.fill(-128);
    layer.bias.fill(std::numeric_limits<std::int32_t>::min());
    check(layer, input, shape + " maximum negative dot product and bias wrap");

    // Full mixed-edge rows distinguish neighboring outputs and all four lanes
    // in each row tile. Rotating fixtures avoids identical lane cancellation.
    for (std::size_t phase = 0; phase < 8; ++phase) {
        for (std::size_t column = 0; column < Inputs; ++column)
            input[column] = activation_edges[(column + phase) % 8];
        for (std::size_t row = 0; row < Outputs; ++row) {
            layer.bias[row] = bias_edges[(row + phase) % 8];
            for (std::size_t column = 0; column < Inputs; ++column)
                layer.weight[row * Inputs + column] = weight_edges[(column + row + phase) % 8];
        }
        check(layer, input, shape + " mixed extremes " + std::to_string(phase));
    }

    input.fill(127);
    layer.bias.fill(0);
    for (std::size_t row = 0; row < Outputs; ++row)
        for (std::size_t column = 0; column < Inputs; ++column)
            layer.weight[row * Inputs + column] = (row + column) % 2 ? -127 : 127;
    check(layer, input, shape + " exact sign cancellation");
    for (const auto value : layer.run(input.data()))
        require(value == 0, shape + ": cancellation anchor");

    std::uint64_t seed = 0x44454e53454f5241ULL ^ Inputs ^ (Outputs << 16);
    randomize(layer, input, seed);
    // Every input lane is isolated, including both sides of all SIMD blocks,
    // the first/last columns, and any columns whose stride could be mistaken.
    for (std::size_t column = 0; column < Inputs; ++column) {
        input.fill(0);
        input[column] = column % 2 ? 1 : 127;
        check(layer, input, shape + " one-hot input " + std::to_string(column));
    }

    // Isolate every output row, including each four-row boundary and the final
    // singleton layer. Other rows must preserve their independent biases.
    input.fill(127);
    for (std::size_t row = 0; row < Outputs; ++row) {
        layer.weight.fill(0);
        for (std::size_t output = 0; output < Outputs; ++output)
            layer.bias[output] = bias_edges[output % 8];
        for (std::size_t column = 0; column < Inputs; ++column)
            layer.weight[row * Inputs + column] = weight_edges[(column + row) % 8];
        check(layer, input, shape + " isolated output " + std::to_string(row));
    }

    for (unsigned iteration = 0; iteration < 64; ++iteration) {
        randomize(layer, input, seed);
        check(layer, input, shape + " random " + std::to_string(iteration));
    }

    // Closed-form modulo anchors verify the independent oracle's direction as
    // well as the production result, without relying solely on shared casts.
    input.fill(0);
    input[0] = 1;
    layer.weight.fill(0);
    layer.bias.fill(0);
    layer.weight[0] = 1;
    layer.bias[0] = std::numeric_limits<std::int32_t>::max();
    check(layer, input, shape + " overflow by one");
    require(layer.run(input.data())[0] == std::numeric_limits<std::int32_t>::min(),
            shape + ": INT32_MAX plus one must wrap to INT32_MIN");
    layer.weight[0] = -1;
    layer.bias[0] = std::numeric_limits<std::int32_t>::min();
    check(layer, input, shape + " underflow by one");
    require(layer.run(input.data())[0] == std::numeric_limits<std::int32_t>::max(),
            shape + ": INT32_MIN minus one must wrap to INT32_MAX");
}
} // namespace

int main() {
    try {
        suite<1024, 32>();
        suite<64, 32>();
        suite<128, 1>();
        std::cout << "NNUE dense arithmetic: " << checked_cases << " independent cases / "
                  << checked_outputs << " repeated-call output comparisons passed "
                  << "(three layer shapes, extremes, all input/output lanes, modulo, immutability)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "NNUE dense arithmetic failure: " << error.what() << '\n';
        return 1;
    }
}
