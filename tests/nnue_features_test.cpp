/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 * GNU GPL version 3 or later; WITHOUT ANY WARRANTY. See LICENSE.
 */
// Test-only access to feature plans and all accumulator lanes. Do not link
// nnue.o: this translation unit already includes the implementation.
#include "../src/nnue.cpp"

#include <chrono>
#include <iostream>
#include <map>
#include <optional>

namespace {
using namespace chess0live;
using namespace chess0live::nnue;
using Counts = std::map<std::uint32_t, int>;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

Position parse(const std::string& fen) {
    std::string error;
    auto result = Position::from_fen(fen, error);
    require(result.has_value(), "Invalid original fixture: " + error + " / " + fen);
    return *result;
}

std::uint64_t random_bits(std::uint64_t& value) {
    value ^= value << 13;
    value ^= value >> 7;
    value ^= value << 17;
    return value;
}

Counts counts(const std::vector<std::uint32_t>& values) {
    Counts result;
    for (const auto value : values) ++result[value];
    return result;
}

// This oracle accounts for signed multiplicities independently of production's
// sorted-list merge. An unchanged relation may occur in both partial lists.
void compare_features(const std::vector<std::uint32_t>& old_features,
                      const std::vector<std::uint32_t>& new_features,
                      const std::vector<std::uint32_t>& removed,
                      const std::vector<std::uint32_t>& added,
                      bool refresh, const std::string& label) {
    auto actual = refresh ? Counts{} : counts(old_features);
    require(!refresh || removed.empty(), label + ": refresh removed features");
    for (const auto feature : removed) --actual[feature];
    for (const auto feature : added) ++actual[feature];
    for (auto it = actual.begin(); it != actual.end();) {
        require(it->second >= 0, label + ": removed a nonexistent feature");
        if (!it->second) it = actual.erase(it);
        else ++it;
    }
    require(actual == counts(new_features), label + ": feature multiset mismatch");
}

int calibrated(const Position& position, Raw raw) {
    // Apply the documented calibration to independent full-refresh output.
    // All values here come from the pinned ordinary network, not hostile input.
    std::int64_t value = std::int64_t(raw.psqt) + raw.positional;
    value -= value * std::abs(std::int64_t(raw.psqt) - raw.positional) / 18236;
    constexpr std::array<int, 7> weights{0, 534, 781, 825, 1276, 2538, 0};
    int material = 0;
    for (int square = 0; square < 64; ++square)
        material += weights[static_cast<unsigned>(type_of(position.at(square)))];
    value += value * material / 91000;
    value -= value * position.halfmove_clock() / 199;
    return static_cast<int>(std::clamp<std::int64_t>(value, -31506, 31506));
}

struct Checks {
    const Model& model;
    const Network& network;
    Evaluator evaluator;
    std::array<Accumulation, 2> state{};
    std::optional<Position> previous;
    std::size_t visits = 0, incremental_plans = 0, refresh_plans = 0;
    std::size_t unchanged_board_transitions = 0;

    Checks(const Model& weights, const Network& source)
        : model(weights), network(source), evaluator(source) {}

    void visit(const Position& position, const std::string& label) {
        if (previous) {
            // Independent square-array oracle catches occupied captures and
            // promotions whose occupancy XOR alone would miss changed pieces.
            Bitboard expected_dirty = 0;
            for (int square = 0; square < 64; ++square)
                if (previous->at(square) != position.at(square))
                    expected_dirty |= square_bit(square);
            require(changed_squares(*previous, position) == expected_dirty,
                    label + ": changed-square bitboard mismatch");
        }
        std::array<FeatureUpdatePlan, 2> plans;
        for (unsigned index = 0; index < 2; ++index) {
            const auto side = static_cast<Color>(index);
            plans[index] = previous ? prepare_update(*previous, position, side)
                                    : prepare_refresh(position, side);
            const auto before = previous ? enumerate_features(*previous, side) : Features{};
            const auto after = enumerate_features(position, side);
            const auto& plan = plans[index];
            const auto context = label + " side " + std::to_string(index);
            compare_features(before.psq, after.psq, plan.removed.psq, plan.added.psq,
                             plan.refresh, context + " PSQ");
            compare_features(before.relations, after.relations, plan.removed.relations,
                             plan.added.relations, plan.refresh, context + " relations");
            if (plan.refresh) ++refresh_plans;
            else ++incremental_plans;
        }
        std::array<Accumulation, 2> reference{};
        initialize(model, reference);
        for (unsigned index = 0; index < 2; ++index) {
            update(model, position, static_cast<Color>(index), reference[index]);
            apply_update(model, state[index], plans[index]);
            require(state[index].hidden == reference[index].hidden,
                    label + ": hidden accumulator lane mismatch side " + std::to_string(index));
            require(state[index].psqt == reference[index].psqt,
                    label + ": PSQT accumulator lane mismatch side " + std::to_string(index));
        }
        if (previous) {
            bool same = true;
            for (int square = 0; square < 64; ++square)
                same &= previous->at(square) == position.at(square);
            if (same) {
                ++unchanged_board_transitions;
                for (const auto& plan : plans)
                    require(!plan.refresh && plan.removed.psq.empty() && plan.added.psq.empty()
                            && plan.removed.relations.empty() && plan.added.relations.empty(),
                            label + ": unchanged board requested accumulator work");
            }
        }
        const auto expected = infer(model, position, reference);
        require(infer(model, position, state) == expected, label + ": applied-plan raw mismatch");
        require(evaluator.raw(position) == expected, label + ": public incremental raw mismatch");
        require(evaluator.evaluate(position) == calibrated(position, expected),
                label + ": public calibrated output mismatch");
        previous = position;
        ++visits;
    }

    void reset() {
        evaluator.reset();
        previous.reset();
        // Deliberately retain nonzero lanes: prepare_refresh must replace them.
    }
};

// Original small board constructions, expanded only by this project's legal
// move generator. They are not puzzle answers or imported playing-strength data.
const std::vector<std::string> fixtures{
    Position::start().fen(),
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
    "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",
    "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
    "4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1",
    "2r4k/1P6/8/8/8/8/8/K7 w - - 0 1",
    "k7/8/8/8/8/8/1p6/2R4K b - - 0 1",
    "4k3/8/3r4/3p4/3R4/3P4/8/4K3 w - - 0 1",
    "4k3/8/8/2n1n3/3N4/2B1B3/8/4K3 w - - 0 1",
    "4k3/pp2pp2/8/2pP4/2P1P3/8/PP3PPP/4K3 w - - 0 1",
    "3k4/8/8/8/8/8/8/3K4 w - - 99 70",
};

void special_transitions(Checks& check) {
    unsigned castles[2]{}, en_passants[2]{};
    std::array<std::array<unsigned, 7>, 2> promotions{}, capture_promotions{};
    for (std::size_t index = 0; index < fixtures.size(); ++index) {
        auto position = parse(fixtures[index]);
        const auto initial_fen = position.fen();
        const auto side = static_cast<unsigned>(position.turn());
        check.visit(position, "fixture " + std::to_string(index));
        const auto moves = position.legal_moves();
        for (const auto move : moves) {
            if (move.flags & castle) ++castles[side];
            if (move.flags & en_passant) ++en_passants[side];
            if (move.promotion != PieceType::none) {
                ++promotions[side][static_cast<unsigned>(move.promotion)];
                if (move.is_capture()) ++capture_promotions[side][static_cast<unsigned>(move.promotion)];
            }
            const auto undo = position.make_move(move);
            check.visit(position, "child " + std::to_string(index) + " " + move.uci());
            position.unmake_move(move, undo);
            check.visit(position, "undo " + std::to_string(index) + " " + move.uci());
            require(position.fen() == initial_fen, "Fixture make/unmake corrupted the board");
        }
        // Visit consecutive siblings while intentionally skipping parent evals.
        for (const auto move : moves) {
            const auto undo = position.make_move(move);
            check.visit(position, "sibling " + std::to_string(index) + " " + move.uci());
            position.unmake_move(move, undo);
        }
        check.visit(position, "final parent " + std::to_string(index));
        if (!position.in_check(position.turn())) {
            const auto undo = position.make_null_move();
            check.visit(position, "null " + std::to_string(index));
            position.unmake_null_move(undo);
            check.visit(position, "undo null " + std::to_string(index));
        }
    }
    for (unsigned side = 0; side < 2; ++side) {
        require(castles[side] == 2 && en_passants[side] == 1, "Special-move fixture coverage incomplete");
        for (unsigned type = static_cast<unsigned>(PieceType::knight);
             type <= static_cast<unsigned>(PieceType::queen); ++type)
            require(promotions[side][type] >= 2 && capture_promotions[side][type] >= 1,
                    "Missing quiet/capture promotion or underpromotion coverage");
    }
}

std::string kings_fen(int white, int black, Color turn) {
    std::string fen;
    for (int rank = 7; rank >= 0; --rank) {
        unsigned empty = 0;
        for (int file = 0; file < 8; ++file) {
            const int square = rank * 8 + file;
            if (square != white && square != black) { ++empty; continue; }
            if (empty) { fen += char('0' + empty); empty = 0; }
            fen += square == white ? 'K' : 'k';
        }
        if (empty) fen += char('0' + empty);
        if (rank) fen += '/';
    }
    return fen + (turn == Color::white ? " w - - 0 1" : " b - - 0 1");
}

void king_orientations(Checks& check) {
    for (unsigned side = 0; side < 2; ++side) {
        for (int square = 0; square < 64; ++square) {
            const int other = square / 8 < 4 ? 63 : 0;
            const auto position = parse(kings_fen(side ? other : square, side ? square : other,
                                                 static_cast<Color>(side)));
            check.visit(position, "king square " + std::to_string(side) + "/" + std::to_string(square));
        }
    }
}

void legal_walks(Checks& check) {
    std::uint64_t seed = 0x4645415455524553ULL;
    std::vector<Position> retained;
    for (unsigned walk = 0; walk < 4; ++walk) {
        auto position = Position::start();
        std::vector<std::pair<Move, Undo>> undo;
        check.reset();
        check.visit(position, "walk start");
        for (unsigned ply = 0; ply < 96; ++ply) {
            const auto moves = position.legal_moves();
            if (moves.empty()) break;
            const auto move = moves[random_bits(seed) % moves.size()];
            undo.emplace_back(move, position.make_move(move));
            // Every fourth step is intentionally invisible to the evaluator.
            if (ply % 4 != 1) check.visit(position, "walk " + std::to_string(walk) + "/" + std::to_string(ply));
            if (ply % 8 == 0) retained.push_back(position);
        }
        for (std::size_t remaining = undo.size(); remaining; --remaining) {
            position.unmake_move(undo[remaining - 1].first, undo[remaining - 1].second);
            if (remaining % 3) check.visit(position, "backtrack " + std::to_string(remaining));
        }
        require(position.fen() == Position::start().fen(), "Random legal walk failed to restore its root");
        check.visit(position, "restored walk root");
    }
    // A different order deliberately jumps between unrelated material layouts,
    // bypassing any single-move assumptions in the production fast path.
    for (std::size_t i = 0; i < retained.size(); ++i)
        check.visit(retained[(i * 17) % retained.size()], "arbitrary jump " + std::to_string(i));
}

struct TemporaryNetwork {
    std::filesystem::path path = std::filesystem::temp_directory_path()
        / ("chess0live-feature-reload-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".nnue");
    ~TemporaryNetwork() { std::error_code error; std::filesystem::remove(path, error); }
};

void replacement_bias_network(const std::filesystem::path& source, const std::filesystem::path& target) {
    // Keep every weight and format marker, replacing only the transformer's
    // compressed bias block with signed-LEB128 1024 (0x80,0x08) in every lane.
    // Unlike reloading identical bytes, this detects stale accumulator values.
    std::ifstream input(source, std::ios::binary);
    const auto u32 = [&]() {
        std::array<unsigned char, 4> bytes{};
        input.read(reinterpret_cast<char*>(bytes.data()), bytes.size());
        require(bool(input), "Could not read NNUE fixture header");
        return std::uint32_t(bytes[0]) | (std::uint32_t(bytes[1]) << 8)
            | (std::uint32_t(bytes[2]) << 16) | (std::uint32_t(bytes[3]) << 24);
    };
    (void)u32(); (void)u32();
    const auto description = u32();
    constexpr std::string_view compressed_marker = "COMPRESSED_LEB128";
    const auto length_offset = std::streamoff(12 + description + 4 + compressed_marker.size());
    input.seekg(length_offset);
    const auto original_length = u32();
    input.seekg(0);
    std::vector<char> prefix(static_cast<std::size_t>(length_offset));
    input.read(prefix.data(), static_cast<std::streamsize>(prefix.size()));
    require(bool(input), "Could not copy NNUE fixture header");
    std::ofstream output(target, std::ios::binary);
    output.write(prefix.data(), static_cast<std::streamsize>(prefix.size()));
    const auto length = std::uint32_t(width * 2);
    for (unsigned shift = 0; shift < 32; shift += 8) output.put(char((length >> shift) & 255));
    for (std::size_t i = 0; i < width; ++i) { output.put(char(0x80)); output.put(char(0x08)); }
    input.seekg(length_offset + 4 + original_length);
    output << input.rdbuf();
    require(bool(output), "Could not write bias replacement fixture");
}

void generation_and_reset(const std::filesystem::path& path, Network& network) {
    Evaluator evaluator(network);
    const auto position = parse(fixtures[9]);
    const auto original = evaluator.raw(position);
    evaluator.reset();
    require(evaluator.raw(position) == original, "Explicit reset changed raw output");
    TemporaryNetwork changed;
    replacement_bias_network(path, changed.path);
    std::string error;
    require(network.load(changed.path, error), "Could not load bias replacement: " + error);
    const auto replacement = network.evaluate(position);
    require(replacement != original, "Bias replacement did not distinguish stale state");
    require(evaluator.raw(position) == replacement, "Network generation retained stale accumulator weights");
    require(evaluator.evaluate(position) == calibrated(position, replacement), "Reloaded calibrated output mismatch");
    require(!network.load(changed.path.string() + ".missing", error), "Missing replacement was accepted");
    require(evaluator.raw(position) == replacement, "Failed reload damaged valid incremental state");
    require(network.load(path, error), "Could not restore pinned network: " + error);
    require(evaluator.raw(position) == original, "Pinned-network reload retained changed accumulators");
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: nnue-features-test NETWORK");
        Reader source(argv[1]);
        auto model = std::make_unique<Model>();
        model->read(source);
        Network network;
        std::string error;
        require(network.load(argv[1], error), "Could not load pinned network: " + error);
        Checks check(*model, network);
        special_transitions(check);
        king_orientations(check);
        legal_walks(check);
        require(check.incremental_plans > 100 && check.refresh_plans > 100
                && check.unchanged_board_transitions >= 20, "Insufficient transition coverage");
        generation_and_reset(argv[1], network);
        std::cout << "PASS NNUE feature multisets, all hidden/PSQT lanes, raw/calibrated outputs: "
                  << check.visits << " transitions, " << check.incremental_plans << " incremental plans, "
                  << check.refresh_plans << " refresh plans, " << check.unchanged_board_transitions
                  << " unchanged-board transitions; reset and changed-weight reload\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL NNUE feature updates: " << error.what() << '\n';
        return 1;
    }
}
