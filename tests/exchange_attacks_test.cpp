/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
// Exercise the exchange-local attack model without exposing a production API.
// Link the normal Position dependencies, but not exchange.o: its implementation
// is included here so the private ExchangeBoard can be tested directly.
#include "../src/exchange.cpp"

#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
using namespace chess0live;
std::size_t comparisons = 0;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

/** Independent square-by-square reference. Neither the production ray tables
 * nor its pawn/leaper masks are consulted. Slider rays stop at the first piece
 * of either color and any type, including a piece that cannot attack back.
 */
Bitboard reference_attackers(const ExchangeBoard& board, int target, Color side) {
    const auto& own = board.pieces[static_cast<unsigned>(side)];
    const int target_file = target % 8, target_rank = target / 8;
    Bitboard result = 0;
    for (int source = 0; source < 64; ++source) {
        const auto bit = Bitboard{1} << source;
        const int df = target_file - source % 8;
        const int dr = target_rank - source / 8;
        if ((df == -1 || df == 1) && dr == (side == Color::white ? 1 : -1))
            result |= bit & own[static_cast<unsigned>(PieceType::pawn)];
        if (df * df + dr * dr == 5)
            result |= bit & own[static_cast<unsigned>(PieceType::knight)];
        if (df >= -1 && df <= 1 && dr >= -1 && dr <= 1 && (df || dr))
            result |= bit & own[static_cast<unsigned>(PieceType::king)];
    }
    for (int df = -1; df <= 1; ++df)
        for (int dr = -1; dr <= 1; ++dr) {
            if (!(df || dr)) continue;
            const auto sliders = own[static_cast<unsigned>(PieceType::queen)]
                | own[static_cast<unsigned>(df && dr ? PieceType::bishop : PieceType::rook)];
            int file = target_file + df, rank = target_rank + dr;
            while (file >= 0 && file < 8 && rank >= 0 && rank < 8) {
                const auto bit = Bitboard{1} << (rank * 8 + file);
                if (board.occupied & bit) {
                    result |= bit & sliders;
                    break;
                }
                file += df;
                rank += dr;
            }
        }
    return result;
}

void compare_all(const ExchangeBoard& board, std::string_view label) {
    const auto before_pieces = board.pieces;
    const auto before_occupied = board.occupied;
    const auto before_kings = board.kings;
    for (int target = 0; target < 64; ++target)
        for (Color side : {Color::white, Color::black}) {
            const auto expected = reference_attackers(board, target, side);
            const auto actual = board.attackers(target, side);
            if (actual != expected) {
                std::ostringstream message;
                message << label << " target " << char('a' + target % 8)
                        << char('1' + target / 8) << " side " << static_cast<unsigned>(side)
                        << " expected 0x" << std::hex << expected << " got 0x" << actual;
                throw std::runtime_error(message.str());
            }
            ++comparisons;
        }
    require(board.pieces == before_pieces && board.occupied == before_occupied
            && board.kings == before_kings, "Attack lookup changed the exchange board");
}

ExchangeBoard empty_board() {
    static const auto start = Position::start();
    ExchangeBoard board(start);
    board.pieces = {};
    board.occupied = 0;
    board.kings = {-1, -1};
    return board;
}

/** Synthetic fixtures test geometry, not legal chess positions. Piece boards
 * remain disjoint and their union is occupied; kings need not be present.
 * Construct them independently of ExchangeBoard::place/remove.
 */
void insert(ExchangeBoard& board, Color side, PieceType type, int square) {
    const auto bit = Bitboard{1} << square;
    require(!(board.occupied & bit), "Synthetic pieces must not overlap");
    board.pieces[static_cast<unsigned>(side)][static_cast<unsigned>(type)] |= bit;
    board.occupied |= bit;
    if (type == PieceType::king) board.kings[static_cast<unsigned>(side)] = square;
}

void single_piece_cases() {
    // Includes every edge, both pawn directions, a piece on the target itself,
    // and bit 63, where selecting the nearest blocker must not wrap or shift 64.
    compare_all(empty_board(), "empty");
    for (int square = 0; square < 64; ++square)
        for (Color side : {Color::white, Color::black})
            for (unsigned type = 1; type <= 6; ++type) {
                auto board = empty_board();
                insert(board, side, static_cast<PieceType>(type), square);
                compare_all(board, "single piece");
            }
}

void mixed_occupancies() {
    constexpr std::array<Bitboard, 8> patterns{
        ~Bitboard{0}, 0xaa55aa55aa55aa55ULL, 0x55aa55aa55aa55aaULL,
        0xff818181818181ffULL, 0x8040201008040201ULL,
        0x0102040810204080ULL, 0x0000001818000000ULL, 0x8100000000000081ULL,
    };
    for (const auto pattern : patterns)
        for (unsigned rotation = 0; rotation < 12; ++rotation) {
            auto board = empty_board();
            for (int square = 0; square < 64; ++square)
                if (pattern & (Bitboard{1} << square)) {
                    const auto assignment = (static_cast<unsigned>(square) + rotation) % 12;
                    insert(board, static_cast<Color>(assignment / 6),
                           static_cast<PieceType>(assignment % 6 + 1), square);
                }
            compare_all(board, "mixed occupancy pattern");
        }

    // These boards are created only for this geometric regression, with no
    // dependency on exposed puzzle positions or reserved strength openings.
    std::uint64_t state = 0x8ff15e7a2c1936b5ULL;
    const auto random = [&state] {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        return state;
    };
    for (unsigned sample = 0; sample < 256; ++sample) {
        auto board = empty_board();
        const unsigned density = sample % 8 + 1;
        for (int square = 0; square < 64; ++square) {
            const auto bits = random();
            if (bits % 9 >= density) continue;
            insert(board, static_cast<Color>((bits >> 8) & 1),
                   static_cast<PieceType>((bits >> 16) % 6 + 1), square);
        }
        compare_all(board, "deterministic mixed board");
    }
}

Position fen(std::string_view text) {
    std::string error;
    const auto position = Position::from_fen(text, error);
    if (!position) throw std::runtime_error("Fixture FEN: " + error);
    return *position;
}

void composed_cases() {
    // A pinned defender still attacks its geometric squares for king safety.
    ExchangeBoard pinned(fen("4r3/8/8/8/6k1/5p2/4B3/4KR2 w - - 0 1"));
    compare_all(pinned, "pinned defender");
    require((pinned.attackers(21, Color::white) & (Bitboard{1} << 12)) != 0,
            "The pinned bishop e2 must attack f3");

    // Removing the nearer rook reveals the more distant rook on the same ray.
    ExchangeBoard orthogonal(fen("3r2k1/8/3r4/3p4/8/8/6B1/3R2K1 w - - 0 1"));
    compare_all(orthogonal, "blocked orthogonal x-ray");
    require(orthogonal.attackers(35, Color::black) == (Bitboard{1} << 43),
            "Only the nearest rook d6 may attack d5");
    orthogonal.remove(Color::black, PieceType::rook, 43);
    compare_all(orthogonal, "revealed orthogonal x-ray");
    require(orthogonal.attackers(35, Color::black) == (Bitboard{1} << 59),
            "Removing d6 must reveal the rook d8");

    auto diagonal = empty_board();
    insert(diagonal, Color::white, PieceType::pawn, 45); // f6
    insert(diagonal, Color::black, PieceType::bishop, 54); // g7
    insert(diagonal, Color::black, PieceType::queen, 63); // h8
    compare_all(diagonal, "opposing pawn blocks diagonal");
    require(diagonal.attackers(27, Color::black) == 0,
            "The pawn f6 must block black sliders from d4");
    diagonal.remove(Color::white, PieceType::pawn, 45);
    compare_all(diagonal, "revealed diagonal bishop");
    require(diagonal.attackers(27, Color::black) == (Bitboard{1} << 54),
            "The nearest bishop g7 must hide the queen h8");
    diagonal.remove(Color::black, PieceType::bishop, 54);
    compare_all(diagonal, "revealed diagonal queen");
    require(diagonal.attackers(27, Color::black) == (Bitboard{1} << 63),
            "Removing g7 must reveal the queen h8");

    struct Case { const char* position; const char* move; };
    constexpr Case cases[] = {
        {"3r3k/8/8/3pP3/8/8/8/3R2K1 w - d6 0 2", "e5d6"},
        {"7k/8/8/3p4/4K3/8/8/8 w - - 0 1", "e4d5"},
        {"k6r/6P1/8/8/8/8/8/K7 w - - 0 1", "g7h8n"},
    };
    for (const auto& item : cases) {
        auto position = fen(item.position);
        compare_all(ExchangeBoard(position), "before special move");
        const auto move = parse_uci_move(position, item.move);
        require(move.has_value(), "Special-move fixture must be legal");
        position.make_move(*move);
        compare_all(ExchangeBoard(position), "after special move");
    }
}
} // namespace

int main() {
    try {
        single_piece_cases();
        mixed_occupancies();
        composed_cases();
        std::cout << "Exchange attack masks passed (" << comparisons << " comparisons)\n";
    } catch (const std::exception& error) {
        std::cerr << "Exchange attack-mask test failed: " << error.what() << '\n';
        return 1;
    }
}
