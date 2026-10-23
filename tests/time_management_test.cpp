/*
 * chess0live — an independent UCI chess engine.
 * Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you may redistribute and/or modify it under
 * GNU GPL version 3 or later. It comes WITHOUT ANY WARRANTY. See LICENSE.
 */
#include "chess0live/time_management.hpp"

#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

namespace {
using namespace chess0live::time_management;

void require(bool condition, std::string_view message) {
    if (!condition) throw std::runtime_error(std::string(message));
}

void target_signals() {
    require(iteration_target(100, 400, 2, 0) == 100, "Two stable iterations retain the nominal target");
    require(iteration_target(100, 400, 3, 0) == 70, "Three stable iterations lower the target");
    require(iteration_target(100, 400, 0, 0) == 150, "Changed root move increases the target");
    require(iteration_target(100, 400, 3, 80) == 70, "Score-drop boundary is exclusive");
    require(iteration_target(100, 400, 3, 81) == 150, "Large score drop overrides stability");
    require(iteration_target(100, 120, 0, 0) == 120, "Signals cannot exceed the hard limit");
    require(iteration_target(0, 0, 0, 0) == 0, "Exhausted budget remains exhausted");
}

void bounded_clock_ceiling() {
    // 120 seconds + 1 second, 20 ms overhead, and the opening 32-move horizon.
    constexpr double available = 119980;
    constexpr double soft = 4549.375;
    require(clock_hard_limit(available, soft, false) == 18197.5,
            "Classic and forecast retain their original four-times ceiling");
    require(clock_hard_limit(available, soft, true) == 9098.75,
            "Bounded timing halves this opening hard ceiling without altering soft time");
    require(clock_hard_limit(0, 0, true) == 0
            && clock_hard_limit(1, 1, true) == 1,
            "Exhausted and tiny clocks cannot spend a future increment");
    require(clock_hard_limit(100, 1, true) == 6
            && clock_hard_limit(100, 1, false) == 6,
            "The existing five-millisecond floor still applies to tiny nominal targets");
    for (const auto available_ms : {0., 1., 20., 100., 120000., 9e18}) {
        for (const auto fraction : {0., 0.01, 0.25, 0.5, 1.}) {
            const auto soft_ms = available_ms * fraction;
            const auto classic = clock_hard_limit(available_ms, soft_ms, false);
            const auto bounded = clock_hard_limit(available_ms, soft_ms, true);
            require(soft_ms <= bounded && bounded <= classic && classic <= available_ms,
                    "A bounded ceiling must stay between soft and the existing available ceiling");
            for (const auto stable : {0, 2, 3})
                for (const auto drop : {0, 80, 81})
                    require(iteration_target(soft_ms, bounded, stable, drop)
                                == iteration_target(soft_ms, classic, stable, drop),
                            "Bounded hard time must retain every existing soft-target signal");
        }
    }
}

void forecast_boundaries() {
    IterationForecast forecast;
    require(forecast.predicted_next_ms() == 0 && forecast.should_start_next(3, 1, 1),
            "Missing cost history must not create a forecast stop");
    forecast.observe(10);
    require(forecast.predicted_next_ms() == 0 && forecast.should_start_next(3, 1, 1),
            "One cost cannot estimate growth");
    forecast.observe(20);
    require(forecast.predicted_next_ms() == 40, "Observed doubling predicts the next whole iteration");
    require(forecast.should_start_next(2, 100, 100), "Do not stop before three completed depths");
    require(forecast.should_start_next(3, 60, 100), "A prediction exactly on the hard deadline fits");
    require(!forecast.should_start_next(3, 60.001, 100), "A prediction beyond the hard deadline does not fit");
    require(!forecast.should_start_next(3, 100, 100), "No remaining hard budget can fit another iteration");
    require(forecast.should_start_next(3, -1, 100), "Uncharged pondering time is not elapsed clock time");

    // The candidate's two boundaries serve different purposes. A costly next
    // depth may finish after the soft target, provided it is predicted to fit
    // the hard deadline and the soft target has not already been consumed.
    const double hard = 100;
    const double soft_target = iteration_target(100, hard, 3, 0); // 70 ms
    require(40 < soft_target && 40 + forecast.predicted_next_ms() > soft_target,
            "Fixture must straddle the soft target with remaining hard budget");
    require(forecast.should_start_next(3, 40, hard),
            "Predicted finish beyond soft target but before hard deadline is admitted");
    require(60.001 < soft_target && !forecast.should_start_next(3, 60.001, hard),
            "Hard-deadline forecast can veto before the soft target is consumed");
    const double at_soft_ms = 70;
    require(at_soft_ms >= soft_target && forecast.should_start_next(3, at_soft_ms, 400),
            "At the soft boundary classic stopping must win even when the forecast fits");
    require(iteration_target(100, 400, 0, 0) > soft_target
            && iteration_target(100, 400, 3, 81) > soft_target,
            "Root changes and score drops still extend the independent soft target");
}

void conservative_growth_and_extremes() {
    IterationForecast forecast;
    forecast.observe(1);
    forecast.observe(16);
    require(forecast.predicted_next_ms() == 256, "Cost growth is retained up to the ratio cap");
    forecast.observe(1);
    require(forecast.predicted_next_ms() == 16, "One cheap iteration must not erase recent expensive growth");
    forecast.observe(1);
    require(forecast.predicted_next_ms() == 1.5, "Old spikes expire after two growth samples");
    forecast.observe(-1);
    forecast.observe(std::numeric_limits<double>::infinity());
    forecast.observe(std::numeric_limits<double>::quiet_NaN());
    require(forecast.predicted_next_ms() == 1.5, "Invalid observations must not poison valid history");
    require(forecast.should_start_next(3, 1, -1)
            && forecast.should_start_next(3, 1, std::numeric_limits<double>::infinity())
            && forecast.should_start_next(3, std::numeric_limits<double>::quiet_NaN(), 1),
            "Invalid boundary inputs leave stopping to ordinary limits");

    IterationForecast tiny;
    tiny.observe(0);
    tiny.observe(0.000001);
    require(std::abs(tiny.predicted_next_ms() - 0.0015) < 1e-12,
            "Fast root iterations must not divide by zero or become a zero forecast");

    IterationForecast huge;
    huge.observe(0);
    huge.observe(std::numeric_limits<double>::max());
    require(huge.predicted_next_ms() == 2147483647.0,
            "Extreme predictions must saturate at a finite protocol-scale duration");
    require(!huge.should_start_next(3, 1, 100), "Extreme work estimates cannot fit a tiny budget");
}
} // namespace

int main() {
    try {
        target_signals();
        bounded_clock_ceiling();
        forecast_boundaries();
        conservative_growth_and_extremes();
        std::cout << "Time-management policy checks passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Time-management test failed: " << error.what() << '\n';
        return 1;
    }
}
