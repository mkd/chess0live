/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/nnue.hpp"
#include "chess0live/position.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <span>
#include <stdexcept>
#include <string_view>
#include <utility>
#include <vector>

// AArch64 guarantees NEON. The scalar path remains selectable for differential
// tests and is the portable backend on other targets.
#if defined(__aarch64__) && defined(__ARM_NEON) && !defined(CHESS0LIVE_FORCE_SCALAR)
#include <arm_neon.h>
#define CHESS0LIVE_NNUE_NEON 1
#else
#define CHESS0LIVE_NNUE_NEON 0
#endif

namespace chess0live::nnue {
namespace {
// These dimensions and identifiers describe the SF19 interoperable file
// format, not an imported implementation. See docs/NNUE.md for provenance.
constexpr std::size_t width = 1024;
constexpr std::size_t psq_count = 22528;
constexpr std::size_t threat_count = 59808;
constexpr std::size_t pair_count = 4560;
constexpr std::size_t buckets = 8;
constexpr std::uint32_t file_version = 0x6a448afa;
constexpr std::uint32_t transformer_hash =
    std::rotl(std::rotl(std::uint32_t{0x2e6b9d04}, 1) ^ 0x86f2b1ddU, 1)
    ^ 0x7f234cb8U ^ (width * 2);
constexpr std::uint32_t affine_hash(std::uint32_t prior, std::uint32_t outputs) {
    return (0xcc03dae4U + outputs) ^ std::rotr(prior, 1);
}
constexpr std::uint32_t architecture_hash() {
    auto value = std::uint32_t{0xec42e90d} ^ std::uint32_t(width * 2);
    value = affine_hash(value, 32) + 0x538d24c7U;
    value = affine_hash(value, 32) + 0x538d24c7U;
    return affine_hash(value, 1);
}

/** Bounded parser: every read is accounted against the actual file size. */
class Reader {
public:
    explicit Reader(const std::filesystem::path& path) : stream_(path, std::ios::binary) {
        if (!stream_) throw std::runtime_error("cannot open network: " + path.string());
        stream_.seekg(0, std::ios::end);
        const auto length = stream_.tellg();
        if (length < 0 || length > 160 * 1024 * 1024)
            throw std::runtime_error("network size is invalid or exceeds the SFNNv16 limit");
        remaining_ = static_cast<std::size_t>(length);
        stream_.seekg(0);
    }
    void bytes(void* destination, std::size_t count) {
        if (count > remaining_) throw std::runtime_error("truncated NNUE file");
        if (count && !stream_.read(static_cast<char*>(destination), static_cast<std::streamsize>(count)))
            throw std::runtime_error("NNUE file read failed");
        remaining_ -= count;
    }
    std::uint32_t u32() {
        std::array<std::uint8_t, 4> value{};
        bytes(value.data(), value.size());
        return std::uint32_t(value[0]) | (std::uint32_t(value[1]) << 8)
             | (std::uint32_t(value[2]) << 16) | (std::uint32_t(value[3]) << 24);
    }
    void expect(std::uint32_t expected, const char* field) {
        if (u32() != expected) throw std::runtime_error(std::string("unsupported NNUE ") + field);
    }
    void skip_description() {
        const auto count = u32();
        if (count > 1024 * 1024) throw std::runtime_error("NNUE description is too large");
        std::vector<char> description(count);
        bytes(description.data(), description.size());
    }
    template<class T> void compressed(std::span<T> output) {
        constexpr std::string_view marker = "COMPRESSED_LEB128";
        std::array<char, marker.size()> found{};
        bytes(found.data(), found.size());
        if (!std::equal(found.begin(), found.end(), marker.begin()))
            throw std::runtime_error("invalid NNUE compression marker");
        const auto length = u32();
        constexpr unsigned max_groups = (sizeof(T) * 8 + 6) / 7;
        if (length > output.size() * max_groups || length < output.size())
            throw std::runtime_error("invalid NNUE compressed block length");
        std::vector<std::uint8_t> encoded(length);
        bytes(encoded.data(), encoded.size());
        std::size_t cursor = 0;
        for (auto& destination : output) {
            std::uint64_t bits = 0;
            unsigned shift = 0;
            std::uint8_t byte = 0;
            do {
                if (cursor == encoded.size() || shift >= max_groups * 7)
                    throw std::runtime_error("truncated or overlong signed LEB128 integer");
                byte = encoded[cursor++];
                bits |= std::uint64_t(byte & 0x7f) << shift;
                shift += 7;
            } while (byte & 0x80);
            // Decode in a wider signed domain before validating the destination.
            const auto signed_value = static_cast<std::int64_t>(bits)
                - ((byte & 0x40) ? (std::int64_t{1} << shift) : 0);
            if (signed_value < std::numeric_limits<T>::min()
                || signed_value > std::numeric_limits<T>::max())
                throw std::runtime_error("signed LEB128 integer is outside its NNUE field range");
            destination = static_cast<T>(signed_value);
        }
        if (cursor != encoded.size()) throw std::runtime_error("unused bytes in NNUE compressed block");
    }
    [[nodiscard]] bool finished() const { return remaining_ == 0; }
private:
    std::ifstream stream_;
    std::size_t remaining_ = 0;
};

template<std::size_t Inputs, std::size_t Outputs> struct Dense {
    std::array<std::int32_t, Outputs> bias{};
    std::array<std::int8_t, Inputs * Outputs> weight{};
    void read(Reader& source) {
        for (auto& value : bias) value = std::bit_cast<std::int32_t>(source.u32());
        source.bytes(weight.data(), weight.size());
    }
    [[nodiscard]] std::array<std::int32_t, Outputs> run(const std::uint8_t* input) const {
        std::array<std::int32_t, Outputs> result{};
#if CHESS0LIVE_NNUE_NEON
        static_assert(Inputs > 0 && Inputs % 16 == 0);
        static_assert(Inputs <= static_cast<std::size_t>(
            std::numeric_limits<std::int32_t>::max() / (127 * 128)),
            "Dense product sums must fit int32 before adding the bias");
        if constexpr (Outputs % 4 == 0) {
            // Reuse each activation vector across four row-major weight rows.
            // Independent accumulation chains require no new instruction set
            // or weight layout. Activations are [0,127] and weights [-128,127]:
            // the bound above protects every partial and horizontal sum.
            const auto finish = [](std::int32_t bias_value, int32x4_t products) {
                // A valid bias can still overflow int32 when added to the dot
                // product. Widen first, then preserve the format's wraparound.
                const std::int64_t sum = std::int64_t(bias_value) + vaddvq_s32(products);
                return std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(sum));
            };
            for (std::size_t output = 0; output < Outputs; output += 4) {
                int32x4_t sum0 = vdupq_n_s32(0), sum1 = vdupq_n_s32(0);
                int32x4_t sum2 = vdupq_n_s32(0), sum3 = vdupq_n_s32(0);
                for (std::size_t index = 0; index < Inputs; index += 16) {
                    const auto activation = vreinterpretq_s8_u8(vld1q_u8(input + index));
                    const auto low = vget_low_s8(activation);
                    const auto w0 = vld1q_s8(weight.data() + output * Inputs + index);
                    const auto w1 = vld1q_s8(weight.data() + (output + 1) * Inputs + index);
                    const auto w2 = vld1q_s8(weight.data() + (output + 2) * Inputs + index);
                    const auto w3 = vld1q_s8(weight.data() + (output + 3) * Inputs + index);
                    sum0 = vpadalq_s16(sum0, vmull_s8(low, vget_low_s8(w0)));
                    sum0 = vpadalq_s16(sum0, vmull_high_s8(activation, w0));
                    sum1 = vpadalq_s16(sum1, vmull_s8(low, vget_low_s8(w1)));
                    sum1 = vpadalq_s16(sum1, vmull_high_s8(activation, w1));
                    sum2 = vpadalq_s16(sum2, vmull_s8(low, vget_low_s8(w2)));
                    sum2 = vpadalq_s16(sum2, vmull_high_s8(activation, w2));
                    sum3 = vpadalq_s16(sum3, vmull_s8(low, vget_low_s8(w3)));
                    sum3 = vpadalq_s16(sum3, vmull_high_s8(activation, w3));
                }
                result[output] = finish(bias[output], sum0);
                result[output + 1] = finish(bias[output + 1], sum1);
                result[output + 2] = finish(bias[output + 2], sum2);
                result[output + 3] = finish(bias[output + 3], sum3);
            }
            return result;
        }
#endif
        for (std::size_t output = 0; output < Outputs; ++output) {
            std::int64_t sum = bias[output];
#if CHESS0LIVE_NNUE_NEON
            // Every activation is in [0,127], so signed byte multiplication
            // is exact. Widen before adding; no saturating dot-product step.
            int32x4_t partial = vdupq_n_s32(0);
            for (std::size_t index = 0; index < Inputs; index += 16) {
                const auto a = vreinterpretq_s8_u8(vld1q_u8(input + index));
                const auto b = vld1q_s8(weight.data() + output * Inputs + index);
                partial = vpadalq_s16(partial, vmull_s8(vget_low_s8(a), vget_low_s8(b)));
                partial = vpadalq_s16(partial, vmull_high_s8(a, b));
            }
            sum += vaddvq_s32(partial);
#else
            for (std::size_t index = 0; index < Inputs; ++index)
                sum += int(input[index]) * int(weight[output * Inputs + index]);
#endif
            result[output] = std::bit_cast<std::int32_t>(static_cast<std::uint32_t>(sum));
        }
        return result;
    }
};

struct Layers {
    Dense<1024, 32> first;
    Dense<64, 32> second;
    Dense<128, 1> last;
};
struct Model {
    std::array<std::int16_t, width> bias{};
    std::vector<std::int16_t> psq;
    std::vector<std::int8_t> relations;
    std::vector<std::int32_t> psq_value;
    std::vector<std::int32_t> relation_value;
    std::array<Layers, buckets> layers{};
    std::uint64_t generation = 0;

    void read(Reader& source) {
        source.expect(file_version, "format version");
        source.expect(transformer_hash ^ architecture_hash(), "architecture hash");
        source.skip_description();
        source.expect(transformer_hash, "feature-transformer hash");
        psq.resize(psq_count * width);
        relations.resize((threat_count + pair_count) * width);
        psq_value.resize(psq_count * buckets);
        relation_value.resize((threat_count + pair_count) * buckets);
        source.compressed<std::int16_t>(bias);
        source.bytes(relations.data(), threat_count * width);
        source.compressed<std::int32_t>({relation_value.data(), threat_count * buckets});
        source.bytes(relations.data() + threat_count * width, pair_count * width);
        source.compressed<std::int32_t>({relation_value.data() + threat_count * buckets, pair_count * buckets});
        source.compressed<std::int16_t>(psq);
        source.compressed<std::int32_t>(psq_value);
        for (auto& layer : layers) {
            source.expect(architecture_hash(), "layer-stack hash");
            layer.first.read(source);
            layer.second.read(source);
            layer.last.read(source);
        }
        if (!source.finished()) throw std::runtime_error("unexpected trailing NNUE bytes");
    }
};

/** Occupancy-aware geometry, written independently of the board move generator.
 * Threat features include friendly relationships, so legal moves are unsuitable.
 */
Bitboard geometry(PieceType type, Color color, int from, Bitboard occupied) {
    const int file = from % 8, rank = from / 8;
    Bitboard result = 0;
    const auto mark = [&](int f, int r) {
        if (f >= 0 && f < 8 && r >= 0 && r < 8) result |= square_bit(r * 8 + f);
    };
    if (type == PieceType::pawn) {
        const int step = color == Color::white ? 1 : -1;
        mark(file - 1, rank + step);
        mark(file + 1, rank + step);
    } else if (type == PieceType::knight) {
        for (int df : {-2, -1, 1, 2}) {
            const int dr = 3 - std::abs(df);
            mark(file + df, rank + dr);
            mark(file + df, rank - dr);
        }
    } else {
        for (int df = -1; df <= 1; ++df) for (int dr = -1; dr <= 1; ++dr) {
            if (!df && !dr) continue;
            const bool diagonal = df && dr;
            if (type == PieceType::bishop && !diagonal) continue;
            if (type == PieceType::rook && diagonal) continue;
            if (type != PieceType::bishop && type != PieceType::rook
                && type != PieceType::queen && type != PieceType::king) continue;
            for (int f = file + df, r = rank + dr; f >= 0 && f < 8 && r >= 0 && r < 8; f += df, r += dr) {
                const auto square = square_bit(r * 8 + f);
                result |= square;
                if ((occupied & square) || type == PieceType::king) break;
            }
        }
    }
    return result;
}

constexpr int relation_slots(PieceType attacker) {
    switch (attacker) {
    case PieceType::pawn: return 2;
    case PieceType::knight: case PieceType::queen: return 5;
    case PieceType::bishop: case PieceType::rook: return 4;
    default: return 0;
    }
}
constexpr int target_slot(PieceType attacker, PieceType target) {
    if (attacker == PieceType::pawn)
        return target == PieceType::knight ? 0 : target == PieceType::rook ? 1 : -1;
    const int value = static_cast<int>(target) - 1;
    return value >= 0 && value < relation_slots(attacker) ? value : -1;
}

/** Enumerate the format's directed, empty-board geometry in square order.
 * Prefix counts avoid shipping upstream lookup tables or generated assets.
 */
struct RelationLayout {
    std::array<std::uint32_t, 12> base{}, span{};
    std::array<std::array<std::uint16_t, 64>, 12> start{};
    std::array<std::array<Bitboard, 64>, 12> rays{};
    RelationLayout() {
        std::uint32_t next = 0;
        for (int code = 0; code < 12; ++code) {
            const auto type = static_cast<PieceType>(code % 6 + 1);
            const auto color = code < 6 ? Color::white : Color::black;
            base[code] = next;
            for (int square = 0; square < 64; ++square) {
                start[code][square] = static_cast<std::uint16_t>(span[code]);
                if (type == PieceType::pawn && (square < 8 || square >= 56)) continue;
                rays[code][square] = geometry(type, color, square, 0);
                span[code] += std::popcount(rays[code][square]);
            }
            next += span[code] * 2 * relation_slots(type);
        }
        if (next != threat_count) throw std::logic_error("SFNNv16 geometry dimension mismatch");
    }
};
const RelationLayout& relation_layout() {
    static const RelationLayout layout;
    return layout;
}

struct Features {
    std::vector<std::uint32_t> psq, relations;
};

Features enumerate_features(const Position& position, Color perspective) {
    Features features;
    features.psq.reserve(32);
    features.relations.reserve(256);
    const auto& layout = relation_layout();
    const int side = perspective == Color::black;
    const int king = position.king_square(perspective);
    const int king_file = king % 8;
    const int psq_flip = (side ? 56 : 0) ^ (king_file < 4 ? 7 : 0);
    const int relation_flip = (side ? 56 : 0) ^ (king_file >= 4 ? 7 : 0);
    const int king_rank = (king ^ (side ? 56 : 0)) / 8;
    const int king_bucket = (7 - king_rank) * 4 + std::min(king_file, 7 - king_file);
    const Bitboard occupied = position.occupied();
    std::array<int, 16> pawns{};
    int pawn_size = 0;
    for (Bitboard remaining = occupied; remaining; remaining &= remaining - 1) {
        const int square = std::countr_zero(remaining);
        const Piece piece = position.at(square);
        const auto type = type_of(piece);
        const int type_number = static_cast<int>(type);
        const int relative_color = (color_of(piece) == Color::black) ^ side;
        const int plane = type == PieceType::king ? 10 : 2 * (type_number - 1) + relative_color;
        features.psq.push_back(static_cast<std::uint32_t>(king_bucket * 704 + plane * 64 + (square ^ psq_flip)));
        if (type == PieceType::pawn) {
            if (square < 8 || square >= 56 || pawn_size == int(pawns.size()))
                throw std::invalid_argument("NNUE requires a legal pawn configuration");
            pawns[pawn_size++] = square;
        }
        if (!relation_slots(type)) continue;
        const int code = relative_color * 6 + type_number - 1;
        const int oriented_from = square ^ relation_flip;
        const auto possible = geometry(type, color_of(piece), square, occupied) & occupied;
        for (Bitboard targets = possible; targets; targets &= targets - 1) {
            const int target = std::countr_zero(targets);
            const Piece target_piece = position.at(target);
            const int slot = target_slot(type, type_of(target_piece));
            if (slot < 0) continue;
            const int oriented_to = target ^ relation_flip;
            // Symmetric same-type relationships occupy one feature, not two.
            if (type == type_of(target_piece) && oriented_from < oriented_to) continue;
            const int target_color = (color_of(target_piece) == Color::black) ^ side;
            const auto earlier = layout.rays[code][oriented_from] & (square_bit(oriented_to) - 1);
            const auto ordinal = layout.start[code][oriented_from] + std::popcount(earlier);
            const auto feature = layout.base[code]
                + (target_color * relation_slots(type) + slot) * layout.span[code] + ordinal;
            features.relations.push_back(feature);
        }
    }
    for (int a = 0; a < pawn_size; ++a) for (int b = a + 1; b < pawn_size; ++b) {
        if (std::abs(pawns[a] % 8 - pawns[b] % 8) > 1) continue;
        const auto pawn_id = [&](int square) {
            const int color = (color_of(position.at(square)) == Color::black) ^ side;
            return color * 48 + (square ^ relation_flip) - 8;
        };
        const int first = pawn_id(pawns[a]), second = pawn_id(pawns[b]);
        const int high = std::max(first, second), low = std::min(first, second);
        features.relations.push_back(static_cast<std::uint32_t>(threat_count + high * (high - 1) / 2 + low));
    }
    std::sort(features.psq.begin(), features.psq.end());
    std::sort(features.relations.begin(), features.relations.end());
    return features;
}

struct Accumulation {
    alignas(64) std::array<std::int16_t, width> hidden{};
    std::array<std::int32_t, buckets> psqt{};
    Features active;
};

/** Modular arithmetic explicitly matches quantized accumulator lane semantics.
 * This also prevents signed overflow in malformed/adversarial network weights.
 */
template<class Weight> void adjust(Accumulation& state, const Weight* weights,
                                  const std::int32_t* values, int sign) {
#if CHESS0LIVE_NNUE_NEON
    for (std::size_t index = 0; index < width; index += 8) {
        int16x8_t delta;
        if constexpr (sizeof(Weight) == 1) delta = vmovl_s8(vld1_s8(weights + index));
        else delta = vld1q_s16(weights + index);
        const auto prior = vld1q_s16(state.hidden.data() + index);
        const auto next = sign > 0 ? vaddq_s16(prior, delta) : vsubq_s16(prior, delta);
        vst1q_s16(state.hidden.data() + index, next);
    }
#else
    for (std::size_t index = 0; index < width; ++index) {
        const auto sum = static_cast<std::uint16_t>(int(state.hidden[index]) + sign * int(weights[index]));
        state.hidden[index] = std::bit_cast<std::int16_t>(sum);
    }
#endif
    for (std::size_t bucket = 0; bucket < buckets; ++bucket) {
        const auto value = std::bit_cast<std::uint32_t>(values[bucket]);
        auto total = std::bit_cast<std::uint32_t>(state.psqt[bucket]);
        total += sign > 0 ? value : 0U - value;
        state.psqt[bucket] = std::bit_cast<std::int32_t>(total);
    }
}

/** A batch holds column views, never copied weights or a capped feature set. */
template<class Weight> struct FeatureDelta {
    const Weight* weights;
    const std::int32_t* values;
    bool add;
};

/** Keep a small hidden-lane tile live while applying several feature columns.
 * Regrouping additions/subtractions is exact in the accumulator's modular
 * arithmetic. A singleton retains the simple column path; no scratch heap
 * allocation or assumption about legal-transition delta counts is required.
 */
template<class Weight> void adjust_batch(Accumulation& state,
                                        std::span<const FeatureDelta<Weight>> changes) {
    if (changes.empty()) return;
    if (changes.size() == 1) {
        const auto& change = changes.front();
        adjust(state, change.weights, change.values, change.add ? 1 : -1);
        return;
    }
    constexpr std::size_t tile = 32;
    static_assert(width % tile == 0);
    for (std::size_t base = 0; base < width; base += tile) {
#if CHESS0LIVE_NNUE_NEON
        auto a = vld1q_s16(state.hidden.data() + base);
        auto b = vld1q_s16(state.hidden.data() + base + 8);
        auto c = vld1q_s16(state.hidden.data() + base + 16);
        auto d = vld1q_s16(state.hidden.data() + base + 24);
        for (const auto& change : changes) {
            const auto* column = change.weights + base;
            int16x8_t wa, wb, wc, wd;
            if constexpr (sizeof(Weight) == 1) {
                const auto low = vld1q_s8(column);
                const auto high = vld1q_s8(column + 16);
                wa = vmovl_s8(vget_low_s8(low)); wb = vmovl_high_s8(low);
                wc = vmovl_s8(vget_low_s8(high)); wd = vmovl_high_s8(high);
            } else {
                wa = vld1q_s16(column); wb = vld1q_s16(column + 8);
                wc = vld1q_s16(column + 16); wd = vld1q_s16(column + 24);
            }
            if (change.add) {
                a = vaddq_s16(a, wa); b = vaddq_s16(b, wb);
                c = vaddq_s16(c, wc); d = vaddq_s16(d, wd);
            } else {
                a = vsubq_s16(a, wa); b = vsubq_s16(b, wb);
                c = vsubq_s16(c, wc); d = vsubq_s16(d, wd);
            }
        }
        vst1q_s16(state.hidden.data() + base, a);
        vst1q_s16(state.hidden.data() + base + 8, b);
        vst1q_s16(state.hidden.data() + base + 16, c);
        vst1q_s16(state.hidden.data() + base + 24, d);
#else
        std::array<std::uint16_t, tile> lanes;
        for (std::size_t lane = 0; lane < tile; ++lane)
            lanes[lane] = std::bit_cast<std::uint16_t>(state.hidden[base + lane]);
        for (const auto& change : changes) {
            for (std::size_t lane = 0; lane < tile; ++lane) {
                const auto delta = static_cast<std::uint16_t>(change.weights[base + lane]);
                lanes[lane] = static_cast<std::uint16_t>(change.add
                    ? lanes[lane] + delta : lanes[lane] - delta);
            }
        }
        for (std::size_t lane = 0; lane < tile; ++lane)
            state.hidden[base + lane] = std::bit_cast<std::int16_t>(lanes[lane]);
#endif
    }
    // Unsigned arithmetic also preserves adversarial PSQT wraparound exactly.
    for (std::size_t bucket = 0; bucket < buckets; ++bucket) {
        auto total = std::bit_cast<std::uint32_t>(state.psqt[bucket]);
        for (const auto& change : changes) {
            const auto value = std::bit_cast<std::uint32_t>(change.values[bucket]);
            total += change.add ? value : 0U - value;
        }
        state.psqt[bucket] = std::bit_cast<std::int32_t>(total);
    }
}

template<class Weights> void differences(Accumulation& state,
    const std::vector<std::uint32_t>& before, const std::vector<std::uint32_t>& after,
    const Weights& weights, const std::vector<std::int32_t>& values) {
    using Weight = typename Weights::value_type;
    // This is a streaming capacity, not a limit on features or changed columns.
    // Flush and reuse it until the entire sorted multiset difference is applied.
    std::array<FeatureDelta<Weight>, 8> batch;
    std::size_t count = 0;
    const auto append = [&](std::uint32_t feature, bool add) {
        batch[count++] = {weights.data() + std::size_t(feature) * width,
                          values.data() + std::size_t(feature) * buckets, add};
        if (count == batch.size()) {
            adjust_batch<Weight>(state, {batch.data(), count});
            count = 0;
        }
    };
    std::size_t old_index = 0, new_index = 0;
    while (old_index != before.size() || new_index != after.size()) {
        if (new_index == after.size() || (old_index != before.size() && before[old_index] < after[new_index])) {
            const auto feature = before[old_index++];
            append(feature, false);
        } else if (old_index == before.size() || after[new_index] < before[old_index]) {
            const auto feature = after[new_index++];
            append(feature, true);
        } else {
            ++old_index;
            ++new_index;
        }
    }
    adjust_batch<Weight>(state, {batch.data(), count});
}

void update(const Model& model, const Position& position, Color side, Accumulation& state) {
    auto next = enumerate_features(position, side);
    differences(state, state.active.psq, next.psq, model.psq, model.psq_value);
    differences(state, state.active.relations, next.relations, model.relations, model.relation_value);
    state.active = std::move(next);
}

/** Both activation branches preserve integer truncation at their own layer. */
void activate(const std::array<std::int32_t, 32>& input, std::uint8_t* output, unsigned shift) {
    for (std::size_t index = 0; index < input.size(); ++index) {
        const std::int64_t value = input[index];
        const auto square = (value * value) >> (shift * 2 + 7);
        output[index] = static_cast<std::uint8_t>(std::min<std::int64_t>(127, square));
        output[index + 32] = static_cast<std::uint8_t>(std::clamp<std::int64_t>(value >> shift, 0, 127));
    }
}

std::array<std::uint8_t, width> transform(Color side, const std::array<Accumulation, 2>& state) {
    const int first = side == Color::black;
    std::array<std::uint8_t, width> input{};
    for (int part = 0; part < 2; ++part) {
        const auto& hidden = state[first ^ part].hidden;
        for (std::size_t index = 0; index < width / 2; ++index) {
            const int a = std::clamp<int>(hidden[index], 0, 255);
            const int b = std::clamp<int>(hidden[index + width / 2], 0, 255);
            input[part * (width / 2) + index] = static_cast<std::uint8_t>(a * b / 512);
        }
    }
    return input;
}

Raw infer(const Model& model, const Position& position, const std::array<Accumulation, 2>& state) {
    const int piece_count = std::popcount(position.occupied());
    if (piece_count < 2 || piece_count > 32) throw std::invalid_argument("NNUE requires 2 to 32 pieces");
    const auto bucket = static_cast<std::size_t>((piece_count - 1) / 4);
    const int first = position.turn() == Color::black;
    const auto input = transform(position.turn(), state);
    const auto& stack = model.layers[bucket];
    const auto first_output = stack.first.run(input.data());
    std::array<std::uint8_t, 128> concatenated{};
    activate(first_output, concatenated.data(), 7);
    const auto second_output = stack.second.run(concatenated.data());
    activate(second_output, concatenated.data() + 64, 6);
    const auto final_output = stack.last.run(concatenated.data());
    const std::int64_t skip = std::int64_t(first_output[30]) - first_output[31];
    const std::int64_t scaled = (std::int64_t(final_output[0]) + skip) * (600 * 16) / (128 * 64 * 2);
    const std::int64_t psqt = (std::int64_t(state[first].psqt[bucket]) - state[first ^ 1].psqt[bucket]) / 2;
    return {static_cast<int>(psqt / 16), static_cast<int>(scaled / 16)};
}

void initialize(const Model& model, std::array<Accumulation, 2>& state) {
    for (auto& item : state) {
        item.hidden = model.bias;
        item.psqt.fill(0);
        item.active.psq.clear();
        item.active.relations.clear();
    }
}
std::atomic<std::uint64_t> next_generation{1};
} // namespace

struct Network::Impl : Model {};
Network::Network() = default;
Network::~Network() = default;
Network::Network(Network&&) noexcept = default;
Network& Network::operator=(Network&&) noexcept = default;
bool Network::load(const std::filesystem::path& path, std::string& error) {
    try {
        Reader source(path);
        auto candidate = std::make_unique<Impl>();
        candidate->read(source);
        candidate->generation = next_generation.fetch_add(1, std::memory_order_relaxed);
        impl_ = std::move(candidate);
        error.clear();
        return true;
    } catch (const std::exception& failure) {
        error = failure.what();
        return false;
    }
}
bool Network::loaded() const noexcept { return bool(impl_); }
Raw Network::evaluate(const Position& position) const {
    if (!impl_) throw std::logic_error("NNUE evaluation requires a loaded network");
    std::array<Accumulation, 2> state{};
    initialize(*impl_, state);
    update(*impl_, position, Color::white, state[0]);
    update(*impl_, position, Color::black, state[1]);
    return infer(*impl_, position, state);
}

struct Evaluator::Impl {
    const Network& network;
    std::uint64_t generation = 0;
    std::array<Accumulation, 2> state{};
    explicit Impl(const Network& source) : network(source) {}
};
Evaluator::Evaluator(const Network& network) : impl_(std::make_unique<Impl>(network)) {}
Evaluator::~Evaluator() = default;
void Evaluator::reset() { impl_->generation = 0; }
Raw Evaluator::raw(const Position& position) {
    if (!impl_->network.impl_) throw std::logic_error("NNUE evaluation requires a loaded network");
    const auto& model = *impl_->network.impl_;
    if (impl_->generation != model.generation) {
        initialize(model, impl_->state);
        impl_->generation = model.generation;
    }
    update(model, position, Color::white, impl_->state[0]);
    update(model, position, Color::black, impl_->state[1]);
    return infer(model, position, impl_->state);
}
int Evaluator::evaluate(const Position& position) {
    const auto result = raw(position);
    // Format hashes establish shape, not sensible weights. Keep calibration
    // arithmetic bounded even for a structurally valid hostile network and a
    // maximal uint32 halfmove clock. This wide guard is far outside the pinned
    // model's useful chess-score range. It must precede every score product.
    constexpr int safe_component = 1 << 20;
    if (std::abs(std::int64_t(result.psqt)) > safe_component
        || std::abs(std::int64_t(result.positional)) > safe_component)
        throw std::runtime_error("NNUE output is outside the safe calibration range");
    std::int64_t value = std::int64_t(result.psqt) + result.positional;
    value -= value * std::abs(std::int64_t(result.psqt) - result.positional) / 18236;
    constexpr std::array<int, 7> material_weight{0, 534, 781, 825, 1276, 2538, 0};
    int material = 0;
    for (Bitboard pieces = position.occupied(); pieces; pieces &= pieces - 1)
        material += material_weight[static_cast<int>(type_of(position.at(std::countr_zero(pieces))))];
    value += value * material / 91000;
    value -= value * position.halfmove_clock() / 199;
    // SF19's evaluator reserves its mate and tablebase score ranges. This
    // wrapper uses its fixed bound for parity; chess0live search owns its scores.
    return static_cast<int>(std::clamp<std::int64_t>(value, -31506, 31506));
}
} // namespace chess0live::nnue
