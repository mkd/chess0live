/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#pragma once

#include <algorithm>
#include <cmath>

namespace chess0live {

enum class TimePolicy { classic, forecast, bounded };

namespace time_management {

/** Allocate a hard ceiling from an already validated ordinary-clock budget.
 * The caller supplies finite 0 <= soft_ms <= available_ms and decides whether
 * bounded timing is eligible. The experimental two-times ceiling changes only
 * permitted overshoot of the nominal target; classic/forecast retain four.
 * Keep the existing five-millisecond floor and never spend future increment.
 */
[[nodiscard]] inline double clock_hard_limit(double available_ms, double soft_ms,
                                             bool bounded) noexcept {
    return std::min(available_ms, std::max(soft_ms + 5.0, soft_ms * (bounded ? 2.0 : 4.0)));
}

/** Preserve the baseline's root-stability and score-drop allocation signals.
 * Durations are milliseconds. This is a target between completed iterations;
 * the independent hard deadline remains enforceable inside the node search.
 */
inline double iteration_target(double soft_ms, double hard_ms,
                               int stable_iterations, int score_drop) {
    double multiplier = stable_iterations >= 3 ? 0.7 : 1.0;
    if (stable_iterations == 0 || score_drop > 80) multiplier = 1.5;
    return std::min(hard_ms, soft_ms * multiplier);
}

/** An experimental, bounded extrapolation of whole root-iteration cost.
 * Each observation includes all aspiration retries and excludes GUI reporting.
 * The larger of the last two growth ratios avoids an optimistic estimate after
 * one unusually cheap iteration; the ratio bounds are hypotheses, not measured
 * Elo improvements. Three completed depths are required before acting, so tiny
 * opening iterations cannot prevent an initial useful search. This estimator
 * vetoes an iteration predicted to exceed the hard deadline; ordinary elapsed
 * time, not predicted finishing time, still governs the separate soft target.
 *
 * The owner supplies monotonic, high-resolution durations. No timing or memory
 * allocation occurs here, making decisions testable without sleeping. The
 * microsecond floor only prevents unstable divisions for sub-timer samples.
 */
class IterationForecast {
public:
    void observe(double duration_ms) noexcept {
        if (!std::isfinite(duration_ms) || duration_ms < 0) return;
        duration_ms = std::max(0.001, duration_ms);
        if (observations_ > 0) {
            previous_growth_ = growth_;
            growth_ = std::clamp(duration_ms / previous_ms_, 1.5, 16.0);
        }
        previous_ms_ = duration_ms;
        observations_ = std::min(3, observations_ + 1);
    }

    [[nodiscard]] double predicted_next_ms() const noexcept {
        if (observations_ < 2) return 0;
        // Saturating arithmetic makes a pathological duration conservative
        // without publishing infinity in a diagnostic or relying on overflow.
        constexpr double ceiling_ms = 2147483647.0;
        const double multiplier = std::max(growth_, previous_growth_);
        return std::min(previous_ms_, ceiling_ms / multiplier) * multiplier;
    }

    [[nodiscard]] bool should_start_next(int completed_depth, double charged_ms,
                                         double deadline_ms) const noexcept {
        if (completed_depth < 3 || observations_ < 2 || charged_ms < 0 || deadline_ms < 0
            || !std::isfinite(charged_ms) || !std::isfinite(deadline_ms)) return true;
        // Equality fits. Subtraction avoids overflow with extreme clock inputs.
        return predicted_next_ms() <= deadline_ms - charged_ms;
    }

private:
    int observations_ = 0;
    double previous_ms_ = 0;
    double growth_ = 1.5;
    double previous_growth_ = 1.5;
};

} // namespace time_management
} // namespace chess0live
