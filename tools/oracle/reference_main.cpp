/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
 * Independently written test adapter, compiled only in an isolated Stockfish
 * checkout. Stockfish retains its own AUTHORS, Copying.txt and source notices.
 * No upstream implementation is included in the chess0live engine binary.
 */
#include <algorithm>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
#include "attacks.h"
#include "position.h"
#include "evaluate.h"
#include "nnue/network.h"
#include "nnue/nnue_accumulator.h"
#include "nnue/nnue_misc.h"

using namespace Stockfish;
template<class Range> void emit(const Range& values) {
    for (const auto value : values) std::cout << int(value) << ',';
    std::cout << ';';
}

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) return 2;
    const bool raw_only = argc == 3 && std::string(argv[2]) == "--raw";
    Attacks::init();
    Position::init();
    auto network = std::make_unique<Eval::NNUE::Network>();
    Eval::NNUE::EvalFile file;
    network->load_external({}, argv[1], file);
    if (!file.current) return 3;
    auto state = std::make_unique<Eval::NNUE::AccumulatorStack>();
    auto cache = std::make_unique<Eval::NNUE::AccumulatorCaches>(*network);
    std::string fen;
    while (std::getline(std::cin, fen)) {
        Position position;
        StateInfo board_state{};
        if (position.set(fen, false, &board_state)) return 4;
        state->reset();
        const auto [psqt, positional] = network->evaluate(position, *state, *cache);
        if (raw_only) {
            std::cout << psqt << ' ' << positional << ' ';
            if (position.checkers()) std::cout << "check";
            else std::cout << Eval::evaluate(*network, position, *state, *cache, 0);
            std::cout << '\n';
            continue;
        }
        std::cout << psqt << ',' << positional << ';';
        for (Color color : {WHITE, BLACK}) {
            std::vector<unsigned> psq;
            for (Bitboard occupied = position.pieces(); occupied;) {
                const auto square = pop_lsb(occupied);
                psq.push_back(Eval::NNUE::PSQFeatureSet::make_index(
                    color, square, position.piece_on(square), position.square<KING>(color)));
            }
            std::sort(psq.begin(), psq.end());
            emit(psq);
            Eval::NNUE::ThreatFeatureSet::IndexList indices;
            Eval::NNUE::ThreatFeatureSet::append_active_indices(color, position, indices);
            Eval::NNUE::PairFeatureSet::append_active_indices(color, position, indices);
            std::vector<unsigned> relations(indices.begin(), indices.end());
            std::sort(relations.begin(), relations.end());
            emit(relations);
            emit(state->latest().accumulation[color]);
            emit(state->latest().psqtAccumulation[color]);
        }
        const unsigned bucket = (position.count<ALL_PIECES>() - 1) / 4;
        alignas(64) unsigned char transformed[1024];
        Eval::NNUE::NNZInfo<1024> nonzero;
        network->featureTransformer.transform(position, *state, *cache, transformed, bucket, nonzero);
        emit(transformed);
        alignas(64) int first[32], second[32], last[32];
        alignas(64) unsigned char concatenated[128];
        auto& layers = network->network[bucket];
        layers.fc_0.propagate(transformed, first, nonzero);
        emit(first);
        layers.ac_sqr_0.propagate(first, concatenated);
        layers.ac_0.propagate(first, concatenated + 32);
        layers.fc_1.propagate(concatenated, second);
        emit(second);
        layers.ac_sqr_1.propagate(second, concatenated + 64);
        layers.ac_1.propagate(second, concatenated + 96);
        emit(concatenated);
        layers.fc_2.propagate(concatenated, last);
        std::cout << last[0] << ';' << bucket << '\n';
    }
}
