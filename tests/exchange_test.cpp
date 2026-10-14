/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/exchange.hpp"
#include "chess0live/position.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
using namespace chess0live;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

Position fen(std::string_view text) {
    std::string error;
    auto position = Position::from_fen(text, error);
    if (!position) throw std::runtime_error("Invalid fixture: " + error);
    return *position;
}

int value(PieceType type) {
    constexpr std::array<int, 7> values{0, 100, 320, 330, 500, 900, 20000};
    return values[static_cast<unsigned>(type)];
}

int gain(const Position& position, Move move) {
    const int captured = move.flags & en_passant ? 100 : value(type_of(position.at(move.to)));
    return captured + (move.promotion == PieceType::none ? 0 : value(move.promotion) - 100);
}

/** Deliberately slow and structurally different oracle: use the normal legal
 * move generator and full Position copies rather than a local attack model.
 * This checks the documented LVA policy, not exhaustive tactical minimax.
 */
int reply(Position position, int target) {
    auto captures = position.legal_moves();
    std::erase_if(captures, [&](Move move) {
        return !move.is_capture() || move.to != target
            || (move.promotion != PieceType::none && move.promotion != PieceType::queen);
    });
    if (captures.empty()) return 0;
    const auto least = *std::min_element(captures.begin(), captures.end(), [&](Move left, Move right) {
        const auto left_value = value(type_of(position.at(left.from)));
        const auto right_value = value(type_of(position.at(right.from)));
        return left_value != right_value ? left_value < right_value : left.from < right.from;
    });
    const int captured = gain(position, least);
    position.make_move(least);
    return std::max(0, captured - reply(position, target));
}

int reference(Position position, Move move) {
    if (!move.is_capture() && move.promotion == PieceType::none) return 0;
    const int initial = gain(position, move);
    position.make_move(move);
    return initial - reply(position, move.to);
}

int check(Position& position, Move move) {
    const auto before_fen = position.fen();
    const auto before_key = position.key();
    const auto before_occupancy = position.occupied();
    std::array<Bitboard, 12> boards{};
    for (unsigned side = 0; side < 2; ++side)
        for (unsigned type = 1; type <= 6; ++type)
            boards[side * 6 + type - 1] = position.pieces(static_cast<Color>(side), static_cast<PieceType>(type));
    const int estimate = static_exchange(position, move);
    const int expected = reference(position, move);
    if (estimate != expected)
        throw std::runtime_error("Exchange mismatch " + before_fen + " " + move.uci()
                                 + ": " + std::to_string(estimate) + " != " + std::to_string(expected));
    require(position.fen() == before_fen && position.key() == before_key
            && position.occupied() == before_occupancy, "Exchange changed the original position");
    for (unsigned side = 0; side < 2; ++side)
        for (unsigned type = 1; type <= 6; ++type)
            require(boards[side * 6 + type - 1]
                    == position.pieces(static_cast<Color>(side), static_cast<PieceType>(type)),
                    "Exchange changed a piece bitboard");
    return estimate;
}

/** Reflect ranks and exchange colors to exercise both pawn directions. These
 * composed fixtures have no castling rights; en-passant ranks are reflected.
 */
Position reflected(const Position& position) {
    std::istringstream input(position.fen());
    std::string board, side, rights, ep;
    input >> board >> side >> rights >> ep;
    require(rights == "-", "Reflection helper excludes castling-right fixtures");
    std::vector<std::string> ranks;
    std::istringstream board_input(board);
    for (std::string rank; std::getline(board_input, rank, '/');) ranks.push_back(rank);
    std::reverse(ranks.begin(), ranks.end());
    std::string output;
    for (auto& rank : ranks) {
        if (!output.empty()) output += '/';
        for (const auto character : rank) {
            const auto byte = static_cast<unsigned char>(character);
            output += static_cast<char>(std::islower(byte) ? std::toupper(byte) : std::tolower(byte));
        }
    }
    if (ep != "-") ep[1] = static_cast<char>('9' - ep[1] + '0');
    return fen(output + (side == "w" ? " b - " : " w - ") + ep + " 0 1");
}

void composed_cases() {
    struct Case { const char* fen; const char* move; int expected; };
    // Original positions isolate material, pins, x-rays, EP, king defense,
    // initial underpromotion, and promotion inside a recapture sequence.
    constexpr Case cases[] = {
        {"6k1/8/4p3/3p4/8/8/8/3Q2K1 w - - 0 1", "d1d5", -800},
        {"6k1/8/2p5/3q4/4P3/8/8/6K1 w - - 0 1", "e4d5", 800},
        {"4k3/8/4p3/3p4/8/8/8/3QR1K1 w - - 0 1", "d1d5", 100},
        {"3r2k1/8/3r4/3p4/8/8/6B1/3R2K1 w - - 0 1", "g2d5", -230},
        {"3r3k/8/8/3pP3/8/8/8/3R2K1 w - d6 0 2", "e5d6", 100},
        {"5k2/4p3/8/8/1B6/8/8/1K2R3 w - - 0 1", "e1e7", 100},
        {"5k2/4p3/8/8/8/8/8/1K2R3 w - - 0 1", "e1e7", -400},
        {"4r3/8/8/8/6k1/5p2/4B3/4KR2 w - - 0 1", "f1f3", 100},
        {"7k/1R6/6K1/8/8/8/p7/1n6 w - - 0 1", "b7b1", -980},
        {"k6r/6P1/8/8/8/8/8/K7 w - - 0 1", "g7h8q", 1300},
        {"k6r/6P1/8/8/8/8/8/K7 w - - 0 1", "g7h8n", 720},
        {"8/4P2k/8/8/8/8/8/K7 w - - 0 1", "e7e8q", 800},
        {"7k/8/8/3p4/4K3/8/8/8 w - - 0 1", "e4d5", 100},
        {"7k/8/8/3p4/4K3/8/8/8 w - - 0 1", "e4f4", 0},
    };
    for (const auto& item : cases) {
        auto position = fen(item.fen);
        const auto move = parse_uci_move(position, item.move);
        require(move.has_value(), "Composed test move must be legal");
        require(check(position, *move) == item.expected, "Composed exchange has the wrong material estimate");
        auto mirror = reflected(position);
        auto notation = move->uci();
        notation[1] = static_cast<char>('9' - notation[1] + '0');
        notation[3] = static_cast<char>('9' - notation[3] + '0');
        const auto mirror_move = parse_uci_move(mirror, notation);
        require(mirror_move.has_value(), "Reflected move must be legal");
        require(check(mirror, *mirror_move) == item.expected, "Color reflection must preserve exchange value");
    }
}

std::size_t generated_cases() {
    // This small deterministic walk is generated here, not imported from an
    // existing engine's tests or a reserved opening/strength corpus.
    std::uint64_t random = 0xd7919ac57e38b62fULL;
    std::size_t comparisons = 0;
    for (int game = 0; game < 12; ++game) {
        auto position = Position::start();
        for (int ply = 0; ply < 80; ++ply) {
            const auto moves = position.legal_moves();
            if (moves.empty()) break;
            for (const auto move : moves)
                if (move.is_capture() || move.promotion != PieceType::none) {
                    check(position, move);
                    ++comparisons;
                }
            random ^= random << 13;
            random ^= random >> 7;
            random ^= random << 17;
            position.make_move(moves[static_cast<std::size_t>(random % moves.size())]);
        }
    }
    require(comparisons > 500, "Generated walks must exercise a substantial set of capture chains");
    return comparisons;
}
} // namespace

int main() {
    try {
        composed_cases();
        const auto comparisons = generated_cases();
        std::cout << "Exchange checks passed (" << comparisons << " generated comparisons)\n";
    } catch (const std::exception& error) {
        std::cerr << "Exchange test failed: " << error.what() << '\n';
        return 1;
    }
}
