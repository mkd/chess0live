/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
 * Test-only adapter; never linked into the production engine.
 */
// Including the implementation grants test-only access to canonical internal
// stages without introducing public engine API or alternate inference code.
#include "nnue.cpp"
#include <iostream>

template<class Range> void emit(const Range& values) {
    for (const auto value : values) std::cout << int(value) << ',';
    std::cout << ';';
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    using namespace chess0live;
    using namespace chess0live::nnue;
    Reader reader(argv[1]);
    auto model = std::make_unique<Model>();
    model->read(reader);
    std::string fen, error;
    while (std::getline(std::cin, fen)) {
        auto position = Position::from_fen(fen, error);
        if (!position) { std::cerr << error << '\n'; return 3; }
        std::array<Accumulation, 2> state;
        initialize(*model, state);
        update(*model, *position, Color::white, state[0]);
        update(*model, *position, Color::black, state[1]);
        const auto raw = infer(*model, *position, state);
        std::cout << raw.psqt << ',' << raw.positional << ';';
        for (const auto& item : state) {
            emit(item.active.psq); emit(item.active.relations);
            emit(item.hidden); emit(item.psqt);
        }
        const auto bucket = (std::popcount(position->occupied()) - 1) / 4;
        const auto transformed = transform(position->turn(), state);
        emit(transformed);
        const auto& layers = model->layers[bucket];
        const auto first = layers.first.run(transformed.data());
        emit(first);
        std::array<std::uint8_t, 128> concatenated;
        activate(first, concatenated.data(), 7);
        const auto second = layers.second.run(concatenated.data());
        emit(second);
        activate(second, concatenated.data() + 64, 6);
        emit(concatenated);
        const auto last = layers.last.run(concatenated.data());
        std::cout << last[0] << ';' << bucket << '\n';
    }
}
