/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/position.hpp"

#include <bit>
#include <cassert>
#include <charconv>
#include <limits>
#include <sstream>

namespace chess0live {
namespace {

constexpr std::uint8_t white_kingside = 1, white_queenside = 2;
constexpr std::uint8_t black_kingside = 4, black_queenside = 8;
constexpr std::array<std::array<int, 2>, 8> knight_steps{{
    {1, 2}, {2, 1}, {2, -1}, {1, -2}, {-1, -2}, {-2, -1}, {-2, 1}, {-1, 2}}};
constexpr std::array<std::array<int, 2>, 8> ray_steps{{
    {1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {1, -1}, {-1, 1}, {-1, -1}}};
constexpr std::array<PieceType, 4> promotions{
    PieceType::queen, PieceType::rook, PieceType::bishop, PieceType::knight};

constexpr bool on_board(int file, int rank) {
    return file >= 0 && file < 8 && rank >= 0 && rank < 8;
}

/** Leaper tables are generated at compile time from geometry, not magic constants. */
consteval auto leaper_table(bool knights) {
    std::array<Bitboard, 64> table{};
    for (int square = 0; square < 64; ++square) {
        for (const auto& step : knights ? knight_steps : ray_steps) {
            const int file = square % 8 + step[0], rank = square / 8 + step[1];
            if (on_board(file, rank)) table[square] |= square_bit(rank * 8 + file);
        }
    }
    return table;
}
constexpr auto knight_attacks = leaper_table(true);
constexpr auto king_attacks = leaper_table(false);

constexpr Bitboard pawn_attacks(Bitboard pawns, Color side) {
    constexpr Bitboard not_a = 0xfefefefefefefefeULL;
    constexpr Bitboard not_h = 0x7f7f7f7f7f7f7f7fULL;
    return side == Color::white ? ((pawns & not_a) << 7) | ((pawns & not_h) << 9)
                                : ((pawns & not_a) >> 9) | ((pawns & not_h) >> 7);
}

/** Fixed SplitMix64 expansion makes keys reproducible across hosts and builds. */
struct Zobrist {
    std::array<std::array<std::array<std::uint64_t, 64>, 7>, 2> piece{};
    std::array<std::uint64_t, 16> castling{};
    std::array<std::uint64_t, 8> ep{};
    std::uint64_t side = 0;
    consteval Zobrist() {
        std::uint64_t state = 0x6368657373306c69ULL;
        const auto next = [&state]() {
            state += 0x9e3779b97f4a7c15ULL;
            auto value = state;
            value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
            value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
            return value ^ (value >> 31);
        };
        for (auto& color : piece)
            for (auto& type : color)
                for (auto& square : type) square = next();
        for (auto& value : castling) value = next();
        for (auto& value : ep) value = next();
        side = next();
    }
};
constexpr Zobrist zobrist;

constexpr std::uint64_t piece_key(Piece piece, int square) {
    return zobrist.piece[static_cast<unsigned>(color_of(piece))]
                        [static_cast<unsigned>(type_of(piece))][square];
}

int pop_square(Bitboard& board) {
    const int square = std::countr_zero(board);
    board &= board - 1;
    return square;
}

std::uint32_t increment(std::uint32_t value) {
    return value == std::numeric_limits<std::uint32_t>::max() ? value : value + 1;
}

bool parse_counter(const std::string& text, std::uint32_t& value) {
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    return error == std::errc{} && end == text.data() + text.size();
}

Piece fen_piece(char symbol) {
    constexpr std::string_view symbols = "PNBRQKpnbrqk";
    const auto index = symbols.find(symbol);
    if (index == std::string_view::npos) return 0;
    return make_piece(index < 6 ? Color::white : Color::black,
                      static_cast<PieceType>(index % 6 + 1));
}

char piece_symbol(Piece piece) {
    return (piece > 0 ? " PNBRQK" : " pnbrqk")[static_cast<unsigned>(type_of(piece))];
}

} // namespace

Position Position::start() {
    std::string error;
    return *from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", error);
}

std::optional<Position> Position::from_fen(std::string_view text, std::string& error) {
    error.clear();
    const auto fail = [&error](std::string message) -> std::optional<Position> {
        error = std::move(message);
        return std::nullopt;
    };
    std::istringstream input{std::string(text)};
    std::array<std::string, 6> fields;
    for (auto& field : fields)
        if (!(input >> field)) return fail("FEN requires six fields");
    std::string trailing;
    if (input >> trailing) return fail("Unexpected text after FEN");

    Position position;
    int rank = 7, file = 0;
    bool previous_digit = false;
    for (const char symbol : fields[0]) {
        if (symbol == '/') {
            if (file != 8 || rank == 0) return fail("FEN must contain eight complete ranks");
            --rank;
            file = 0;
            previous_digit = false;
        } else if (symbol >= '1' && symbol <= '8') {
            if (previous_digit) return fail("Adjacent FEN empty-square digits are invalid");
            file += symbol - '0';
            previous_digit = true;
            if (file > 8) return fail("FEN rank contains more than eight squares");
        } else {
            const Piece piece = fen_piece(symbol);
            if (!piece || file >= 8) return fail("Invalid FEN piece or rank length");
            if (type_of(piece) == PieceType::pawn && (rank == 0 || rank == 7))
                return fail("A pawn cannot occupy the first or eighth rank");
            position.put(rank * 8 + file++, piece);
            previous_digit = false;
        }
    }
    if (rank != 0 || file != 8) return fail("FEN must contain eight complete ranks");
    if (fields[1] == "w") position.side_ = Color::white;
    else if (fields[1] == "b") position.side_ = Color::black;
    else return fail("FEN active color must be w or b");

    for (const Color side : {Color::white, Color::black}) {
        if (std::popcount(position.pieces(side, PieceType::king)) != 1)
            return fail("Each side must have exactly one king");
        if (std::popcount(position.pieces(side, PieceType::pawn)) > 8)
            return fail("A side cannot have more than eight pawns");
        int count = 0;
        for (int type = 1; type <= 6; ++type)
            count += std::popcount(position.pieces(side, static_cast<PieceType>(type)));
        if (count > 16) return fail("A side cannot have more than sixteen pieces");
    }

    if (fields[2] != "-") {
        for (const char symbol : fields[2]) {
            std::uint8_t right = 0;
            switch (symbol) {
            case 'K': right = white_kingside; break;
            case 'Q': right = white_queenside; break;
            case 'k': right = black_kingside; break;
            case 'q': right = black_queenside; break;
            default: return fail("Invalid FEN castling rights");
            }
            if (position.castling_ & right) return fail("Duplicate FEN castling right");
            position.castling_ |= right;
        }
    }
    for (const Color side : {Color::white, Color::black}) {
        const int offset = side == Color::white ? 0 : 56;
        const unsigned rights = side == Color::white ? position.castling_ & 3
                                                     : (position.castling_ >> 2) & 3;
        if (rights && position.at(offset + 4) != make_piece(side, PieceType::king))
            return fail("Castling rights require the king on its starting square");
        if ((rights & 1) && position.at(offset + 7) != make_piece(side, PieceType::rook))
            return fail("Kingside castling rights require the starting rook");
        if ((rights & 2) && position.at(offset) != make_piece(side, PieceType::rook))
            return fail("Queenside castling rights require the starting rook");
    }
    if (!parse_counter(fields[4], position.halfmove_)) return fail("Invalid FEN halfmove clock");
    if (!parse_counter(fields[5], position.fullmove_) || position.fullmove_ == 0)
        return fail("FEN fullmove number must be positive");
    if (fields[3] != "-") {
        const auto& ep = fields[3];
        const char required_rank = position.side_ == Color::white ? '6' : '3';
        if (ep.size() != 2 || ep[0] < 'a' || ep[0] > 'h' || ep[1] != required_rank)
            return fail("Invalid FEN en-passant square");
        position.ep_square_ = (ep[1] - '1') * 8 + ep[0] - 'a';
        const int step = position.side_ == Color::white ? 8 : -8;
        if (position.at(position.ep_square_) != 0
            || position.at(position.ep_square_ - step)
                   != make_piece(opposite(position.side_), PieceType::pawn)
            || position.at(position.ep_square_ + step) != 0 || position.halfmove_ != 0)
            return fail("En-passant square is inconsistent with a preceding double pawn push");
    }
    // Being in check is legal for the active side; the side that just moved may
    // not have left its own king attacked. This also rejects adjacent kings.
    if (position.in_check(opposite(position.side_)))
        return fail("The side not to move cannot be in check");
    position.rebuild_key();
    return position;
}

std::string Position::fen() const {
    std::string result;
    for (int rank = 7; rank >= 0; --rank) {
        int empty = 0;
        for (int file = 0; file < 8; ++file) {
            const Piece piece = at(rank * 8 + file);
            if (!piece) { ++empty; continue; }
            if (empty) { result += char('0' + empty); empty = 0; }
            result += piece_symbol(piece);
        }
        if (empty) result += char('0' + empty);
        if (rank) result += '/';
    }
    result += side_ == Color::white ? " w " : " b ";
    if (!castling_) result += '-';
    if (castling_ & white_kingside) result += 'K';
    if (castling_ & white_queenside) result += 'Q';
    if (castling_ & black_kingside) result += 'k';
    if (castling_ & black_queenside) result += 'q';
    result += ' ';
    if (ep_square_ == -1) result += '-';
    else { result += char('a' + ep_square_ % 8); result += char('1' + ep_square_ / 8); }
    result += ' ' + std::to_string(halfmove_) + ' ' + std::to_string(fullmove_);
    return result;
}

void Position::put(int square, Piece piece) {
    assert(piece != 0 && board_[square] == 0);
    board_[square] = piece;
    pieces_[static_cast<unsigned>(color_of(piece))][static_cast<unsigned>(type_of(piece))]
        |= square_bit(square);
    occupied_ |= square_bit(square);
    key_ ^= piece_key(piece, square);
}

Piece Position::remove(int square) {
    const Piece piece = board_[square];
    assert(piece != 0);
    board_[square] = 0;
    pieces_[static_cast<unsigned>(color_of(piece))][static_cast<unsigned>(type_of(piece))]
        &= ~square_bit(square);
    occupied_ &= ~square_bit(square);
    key_ ^= piece_key(piece, square);
    return piece;
}

int Position::king_square(Color side) const {
    return std::countr_zero(pieces(side, PieceType::king));
}

bool Position::attacked_with(int square, Color by, Bitboard occupancy, Bitboard pawns) const {
    if (pawn_attacks(pawns, by) & square_bit(square)) return true;
    if (knight_attacks[square] & pieces(by, PieceType::knight)) return true;
    if (king_attacks[square] & pieces(by, PieceType::king)) return true;
    for (unsigned direction = 0; direction < ray_steps.size(); ++direction) {
        const auto& step = ray_steps[direction];
        int file = square % 8 + step[0], rank = square / 8 + step[1];
        const Bitboard attackers = pieces(by, PieceType::queen)
            | pieces(by, direction < 4 ? PieceType::rook : PieceType::bishop);
        while (on_board(file, rank)) {
            const Bitboard bit = square_bit(rank * 8 + file);
            if (occupancy & bit) {
                if (attackers & bit) return true;
                break;
            }
            file += step[0];
            rank += step[1];
        }
    }
    return false;
}

bool Position::attacked(int square, Color by) const {
    return attacked_with(square, by, occupied_, pieces(by, PieceType::pawn));
}

bool Position::in_check(Color side) const { return attacked(king_square(side), opposite(side)); }

int Position::ep_hash_file() const {
    if (ep_square_ == -1) return -1;
    const int captured = ep_square_ + (side_ == Color::white ? -8 : 8);
    Bitboard candidates = pawn_attacks(square_bit(ep_square_), opposite(side_))
                        & pieces(side_, PieceType::pawn);
    const Color enemy = opposite(side_);
    const Bitboard enemy_pawns = pieces(enemy, PieceType::pawn) & ~square_bit(captured);
    while (candidates) {
        const int from = pop_square(candidates);
        const Bitboard after = (occupied_ & ~square_bit(from) & ~square_bit(captured))
                              | square_bit(ep_square_);
        // A pseudo-legal EP capture may expose a rook/bishop attack. Such a file
        // must not distinguish repetition-equivalent positions.
        if (!attacked_with(king_square(side_), enemy, after, enemy_pawns))
            return ep_square_ % 8;
    }
    return -1;
}

void Position::rebuild_key() {
    key_ = zobrist.castling[castling_];
    for (int square = 0; square < 64; ++square)
        if (at(square)) key_ ^= piece_key(at(square), square);
    if (side_ == Color::black) key_ ^= zobrist.side;
    const int ep_file = ep_hash_file();
    if (ep_file != -1) key_ ^= zobrist.ep[ep_file];
}

std::vector<Move> Position::pseudo_legal_moves() const {
    std::vector<Move> moves;
    moves.reserve(64);
    Bitboard friendly = 0;
    for (int type = 1; type <= 6; ++type) friendly |= pieces_[static_cast<unsigned>(side_)][type];
    const Bitboard enemy = occupied_ & ~friendly;
    const auto add = [&moves](int from, int to, std::uint8_t flags,
                             PieceType promotion = PieceType::none) {
        moves.push_back(Move{static_cast<std::uint8_t>(from), static_cast<std::uint8_t>(to),
                             promotion, flags});
    };
    const auto add_pawn = [&](int from, int to, std::uint8_t flags) {
        if (to / 8 == 0 || to / 8 == 7)
            for (const PieceType type : promotions) add(from, to, flags, type);
        else add(from, to, flags);
    };
    Bitboard pawns = pieces(side_, PieceType::pawn);
    const int forward = side_ == Color::white ? 8 : -8;
    while (pawns) {
        const int from = pop_square(pawns), to = from + forward;
        if (!at(to)) {
            add_pawn(from, to, quiet);
            if (from / 8 == (side_ == Color::white ? 1 : 6) && !at(to + forward))
                add(from, to + forward, double_push);
        }
        Bitboard captures = pawn_attacks(square_bit(from), side_) & enemy
                          & ~pieces(opposite(side_), PieceType::king);
        while (captures) add_pawn(from, pop_square(captures), capture);
        if (ep_square_ != -1 && (pawn_attacks(square_bit(from), side_) & square_bit(ep_square_)))
            add(from, ep_square_, capture | en_passant);
    }
    for (const PieceType type : {PieceType::knight, PieceType::king}) {
        Bitboard sources = pieces(side_, type);
        while (sources) {
            const int from = pop_square(sources);
            Bitboard targets = (type == PieceType::knight ? knight_attacks[from] : king_attacks[from])
                             & ~friendly & ~pieces(opposite(side_), PieceType::king);
            while (targets) {
                const int to = pop_square(targets);
                add(from, to, (enemy & square_bit(to)) ? capture : quiet);
            }
        }
    }
    for (const PieceType type : {PieceType::bishop, PieceType::rook, PieceType::queen}) {
        Bitboard sources = pieces(side_, type);
        while (sources) {
            const int from = pop_square(sources);
            for (unsigned direction = 0; direction < ray_steps.size(); ++direction) {
                if ((type == PieceType::bishop && direction < 4)
                    || (type == PieceType::rook && direction >= 4)) continue;
                const auto& step = ray_steps[direction];
                int file = from % 8 + step[0], rank = from / 8 + step[1];
                while (on_board(file, rank)) {
                    const int to = rank * 8 + file;
                    if (friendly & square_bit(to)) break;
                    if (enemy & square_bit(to)) {
                        if (type_of(at(to)) != PieceType::king) add(from, to, capture);
                        break;
                    }
                    add(from, to, quiet);
                    file += step[0];
                    rank += step[1];
                }
            }
        }
    }
    const int home = side_ == Color::white ? 4 : 60;
    const unsigned rights = side_ == Color::white ? castling_ & 3 : (castling_ >> 2) & 3;
    if (rights && !in_check(side_)) {
        const Color by = opposite(side_);
        const Bitboard without_king = occupied_ & ~square_bit(home);
        const Bitboard their_pawns = pieces(by, PieceType::pawn);
        if ((rights & 1) && !at(home + 1) && !at(home + 2)
            && !attacked_with(home + 1, by, without_king, their_pawns)
            && !attacked_with(home + 2, by, without_king, their_pawns))
            add(home, home + 2, castle);
        if ((rights & 2) && !at(home - 1) && !at(home - 2) && !at(home - 3)
            && !attacked_with(home - 1, by, without_king, their_pawns)
            && !attacked_with(home - 2, by, without_king, their_pawns))
            add(home, home - 2, castle);
    }
    return moves;
}

std::vector<Move> Position::legal_moves() {
    auto moves = pseudo_legal_moves();
    const Color mover = side_;
    std::size_t count = 0;
    for (const Move move : moves) {
        const Undo undo = make_move(move);
        const bool legal = !in_check(mover);
        unmake_move(move, undo);
        if (legal) moves[count++] = move;
    }
    moves.resize(count);
    return moves;
}

Undo Position::save() const {
    return Undo{0, 0, castling_, ep_square_, halfmove_, fullmove_, key_};
}

Undo Position::make_move(Move move) {
    assert(move.valid() && at(move.from) && color_of(at(move.from)) == side_);
    Undo undo = save();
    undo.moved = at(move.from);
    const int old_ep = ep_hash_file();
    if (old_ep != -1) key_ ^= zobrist.ep[old_ep];
    key_ ^= zobrist.castling[castling_];
    ep_square_ = -1;
    const int captured_square = (move.flags & en_passant)
                              ? move.to + (side_ == Color::white ? -8 : 8) : move.to;
    if (at(captured_square)) undo.captured = remove(captured_square);
    remove(move.from);
    put(move.to, move.promotion == PieceType::none ? undo.moved : make_piece(side_, move.promotion));
    if (move.flags & castle) {
        const int rook_from = move.to > move.from ? move.from + 3 : move.from - 4;
        const int rook_to = move.to > move.from ? move.from + 1 : move.from - 1;
        put(rook_to, remove(rook_from));
    }
    if (type_of(undo.moved) == PieceType::king)
        castling_ &= static_cast<std::uint8_t>(side_ == Color::white ? ~3U : ~12U);
    // A home-rook move or capture irrevocably removes the corresponding right.
    for (const int square : {int(move.from), captured_square}) {
        if (square == 0) castling_ &= static_cast<std::uint8_t>(~white_queenside);
        if (square == 7) castling_ &= static_cast<std::uint8_t>(~white_kingside);
        if (square == 56) castling_ &= static_cast<std::uint8_t>(~black_queenside);
        if (square == 63) castling_ &= static_cast<std::uint8_t>(~black_kingside);
    }
    if (move.flags & double_push) ep_square_ = (int(move.from) + int(move.to)) / 2;
    halfmove_ = undo.captured || type_of(undo.moved) == PieceType::pawn ? 0 : increment(halfmove_);
    if (side_ == Color::black) fullmove_ = increment(fullmove_);
    side_ = opposite(side_);
    key_ ^= zobrist.side ^ zobrist.castling[castling_];
    const int new_ep = ep_hash_file();
    if (new_ep != -1) key_ ^= zobrist.ep[new_ep];
    return undo;
}

void Position::restore_state(const Undo& undo) {
    side_ = opposite(side_);
    castling_ = undo.castling;
    ep_square_ = undo.en_passant_square;
    halfmove_ = undo.halfmove;
    fullmove_ = undo.fullmove;
    key_ = undo.key;
}

void Position::unmake_move(Move move, const Undo& undo) {
    remove(move.to);
    put(move.from, undo.moved);
    if (move.flags & castle) {
        const int rook_from = move.to > move.from ? move.from + 3 : move.from - 4;
        const int rook_to = move.to > move.from ? move.from + 1 : move.from - 1;
        put(rook_from, remove(rook_to));
    }
    if (undo.captured) {
        const int captured_square = (move.flags & en_passant)
                                  ? move.to + (side_ == Color::black ? -8 : 8) : move.to;
        put(captured_square, undo.captured);
    }
    restore_state(undo);
}

Undo Position::make_null_move() {
    const Undo undo = save();
    const int old_ep = ep_hash_file();
    if (old_ep != -1) key_ ^= zobrist.ep[old_ep];
    ep_square_ = -1;
    halfmove_ = increment(halfmove_);
    if (side_ == Color::black) fullmove_ = increment(fullmove_);
    side_ = opposite(side_);
    key_ ^= zobrist.side;
    return undo;
}

void Position::unmake_null_move(const Undo& undo) { restore_state(undo); }

std::uint64_t perft(Position& position, unsigned depth) {
    if (depth == 0) return 1;
    const auto moves = position.legal_moves();
    if (depth == 1) return moves.size();
    std::uint64_t count = 0;
    for (const Move move : moves) {
        const Undo undo = position.make_move(move);
        count += perft(position, depth - 1);
        position.unmake_move(move, undo);
    }
    return count;
}

std::optional<Move> parse_uci_move(Position& position, std::string_view text) {
    if (text.size() != 4 && text.size() != 5) return std::nullopt;
    for (const Move move : position.legal_moves())
        if (move.uci() == text) return move;
    return std::nullopt;
}

} // namespace chess0live
