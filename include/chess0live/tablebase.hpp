/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute it and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include "chess0live/types.hpp"

#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace chess0live {
class Position;

/** Narrow optional boundary around the separately licensed Fathom reader.
 * Table files are user-managed, verified, immutable data while configured.
 * No tablebase result represents a distance to mate.
 */
namespace tablebase {

enum class Wdl : int { loss = -2, blessed_loss = -1, draw = 0, cursed_win = 1, win = 2 };

/** Greater ranks preserve a better rule-50-aware outcome or safer DTZ progress.
 * These are opaque ordering values, not centipawns, mate distances, or a WDL
 * enum. The caller retains the best rank among its permitted root moves.
 */
struct RootMove {
    Move move;
    int rank = 0;
};

/** Serialized access to Fathom's process-global state.
 *
 * Concurrent probes are supported. The caller must reconfigure only while its
 * own searches are idle and clear search caches after configuration changes.
 * Configuring another instance invalidates earlier bindings; their subsequent
 * probes return no result, rather than accidentally using another table set.
 * Destruction of an invalidated instance cannot free the current table set.
 */
class Syzygy {
public:
    Syzygy();
    ~Syzygy();
    Syzygy(const Syzygy&) = delete;
    Syzygy& operator=(const Syzygy&) = delete;

    /** Configure directories separated by ':' on POSIX or ';' on Windows.
     * Empty or "<empty>" disables probing. Invalid paths/basic file validation
     * failures disable this instance and return false with an explanation.
     * A valid directory with no tables succeeds with largest()==0. The header
     * checks detect common incomplete downloads, not all corrupt encodings;
     * use verified checksums and do not modify files while configured.
     */
    bool set_path(const std::string& path, std::string& error);
    unsigned largest() const;

    /** WDL is valid only immediately after a zeroing move (halfmove==0), with
     * no castling rights. Missing/unsupported tables return no result. Values
     * are from the side-to-move perspective; cursed/blessed results are draws
     * when applying the fifty-move rule.
     */
    std::optional<Wdl> probe_wdl(const Position& position) const;

    /** Rank every legal root move using DTZ and the actual halfmove clock.
     * The caller supplies the full generated legal set, handles terminal/drawn
     * roots first, and skips this probe when reversible history has repeated.
     * Reconcile all upstream moves with that set before exposing any result;
     * special flags therefore always come from our own legal generator.
     * Missing DTZ or incomplete/mismatched results return no result.
     */
    std::optional<std::vector<RootMove>> probe_root(
        const Position& position, const std::vector<Move>& legal) const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace tablebase
} // namespace chess0live
