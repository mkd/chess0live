# chess0live — Copyright (C) 2026 Claudio M. Camacho <claudiomkd@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later. See LICENSE; no warranty.

HOST_OS := $(shell uname -s 2>/dev/null)
HOST_CPU := $(shell uname -m 2>/dev/null)
ifeq ($(HOST_OS),Darwin)
  HOST_SYSTEM := macos
else ifeq ($(HOST_OS),Linux)
  HOST_SYSTEM := linux
else
  HOST_SYSTEM := windows
endif
ifneq ($(filter arm64 aarch64,$(HOST_CPU)),)
  HOST_ARCH := arm64
else ifneq ($(filter riscv64,$(HOST_CPU)),)
  HOST_ARCH := riscv64
else
  HOST_ARCH := x86_64
endif
HOST_TARGET := $(HOST_SYSTEM)-$(HOST_ARCH)
TARGET ?= $(HOST_TARGET)
CPU ?= generic
MODE ?= release
SIMD ?= auto
PYTHON ?= python3
ifeq ($(origin CXX),default)
  CXX := c++
endif

VALID_TARGETS := macos-arm64 linux-x86_64 linux-arm64 linux-riscv64 windows-x86_64 windows-arm64
ifeq ($(filter $(TARGET),$(VALID_TARGETS)),)
  $(error Unsupported TARGET=$(TARGET). Choose $(VALID_TARGETS))
endif
ifeq ($(filter $(CPU),generic native),)
  $(error CPU must be generic or native)
endif
ifeq ($(filter $(MODE),release debug sanitize),)
  $(error MODE must be release, debug, or sanitize)
endif
ifeq ($(filter $(SIMD),auto scalar),)
  $(error SIMD must be auto or scalar)
endif
ifeq ($(CPU),native)
  ifneq ($(TARGET),$(HOST_TARGET))
    $(error CPU=native cannot be used for a cross-build)
  endif
endif

BUILD := build/$(TARGET)-$(CPU)-$(MODE)$(if $(filter scalar,$(SIMD)),-scalar,)
EXE := $(if $(filter windows-%,$(TARGET)),.exe,)
ENGINE := $(BUILD)/chess0live$(EXE)
CPPFLAGS += -Iinclude
ifeq ($(SIMD),scalar)
  CPPFLAGS += -DCHESS0LIVE_FORCE_SCALAR
endif
CXXFLAGS += -std=c++2c -Wall -Wextra -Wpedantic -pthread
LDFLAGS += -pthread
ifneq ($(filter windows-%,$(TARGET)),)
  # Ship one console executable rather than requiring users to locate compiler
  # runtime DLLs. Windows system libraries remain ordinary OS dependencies.
  LDFLAGS += -static
endif
ifeq ($(MODE),release)
  CXXFLAGS += -O3 -DNDEBUG
else ifeq ($(MODE),debug)
  CXXFLAGS += -O0 -g
else
  CXXFLAGS += -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
  LDFLAGS += -fsanitize=address,undefined
endif
ifeq ($(CPU),native)
  CXXFLAGS += $(if $(filter arm64,$(HOST_ARCH)),-mcpu=native,-march=native)
endif
ifneq ($(SYSROOT),)
  CPPFLAGS += --sysroot="$(SYSROOT)"
  LDFLAGS += --sysroot="$(SYSROOT)"
endif

SOURCES := src/position.cpp src/nnue.cpp src/search.cpp src/main.cpp
OBJECTS := $(patsubst src/%.cpp,$(BUILD)/%.o,$(SOURCES))
NET := networks/nn-1a298aa575a0.nnue

.PHONY: all help doctor net test test-core test-nnue test-search test-search-policy test-time test-match test-bench test-profile test-profile-lmr verify-moves bench resources clean FORCE
all: $(ENGINE)

$(BUILD):
	mkdir -p "$@"

# Run a target-specific compile check before building any engine object. It catches
# a host compiler accidentally used to produce a mislabeled cross-target binary.
FORCE:

$(BUILD)/toolchain.ok: FORCE tools/check_toolchain.py Makefile | $(BUILD)
	@$(PYTHON) tools/check_toolchain.py --target $(TARGET) --compiler "$(CXX)" --flags '$(CPPFLAGS) $(CXXFLAGS)' --link-flags '$(LDFLAGS) $(LDLIBS)' --output "$(BUILD)/toolchain-probe.o" --stamp "$@"

$(BUILD)/%.o: src/%.cpp $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c "$<" -o "$@"

$(ENGINE): $(OBJECTS)
	$(CXX) $(OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

doctor: | $(BUILD)
	$(PYTHON) tools/check_toolchain.py --target $(TARGET) --compiler "$(CXX)" --flags '$(CPPFLAGS) $(CXXFLAGS)' --output "$(BUILD)/toolchain-probe.o"

net:
	$(PYTHON) tools/fetch_network.py

$(BUILD)/position-test$(EXE): tests/position_test.cpp $(BUILD)/position.o
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(LDFLAGS) -o "$@"

$(BUILD)/nnue-test$(EXE): tests/nnue_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(LDFLAGS) -o "$@"

$(BUILD)/search-test$(EXE): tests/search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/search.o
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/search.o $(LDFLAGS) -o "$@"

$(BUILD)/time-management-test$(EXE): tests/time_management_test.cpp include/chess0live/time_management.hpp $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) -o "$@"

$(BUILD)/search-policy-test$(EXE): tests/search_policy_test.cpp include/chess0live/search_policy.hpp include/chess0live/types.hpp $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) -o "$@"

test-core: $(ENGINE) $(BUILD)/position-test$(EXE)
	"$(BUILD)/position-test$(EXE)"
	$(PYTHON) tests/uci_test.py "$(ENGINE)"
	$(PYTHON) tests/resources_test.py

test-nnue: $(BUILD)/nnue-test$(EXE)
	"$(BUILD)/nnue-test$(EXE)" --network "$(NET)"

test-search: $(BUILD)/search-test$(EXE)
	"$(BUILD)/search-test$(EXE)" "$(NET)"

test-time: $(BUILD)/time-management-test$(EXE)
	"$(BUILD)/time-management-test$(EXE)"

test-search-policy: $(BUILD)/search-policy-test$(EXE)
	"$(BUILD)/search-policy-test$(EXE)"

test: test-core test-nnue test-search test-search-policy test-time

# Optional independent referee checks: install requirements-match.txt first.
# Keep the engine's ordinary correctness suite free of third-party Python deps.
test-match:
	$(PYTHON) tests/match_statistics_test.py
	$(PYTHON) tests/match_test.py

test-bench:
	$(PYTHON) tests/compare_bench_test.py

test-profile:
	$(PYTHON) tests/profile_search_test.py

test-profile-lmr:
	$(PYTHON) tests/profile_lmr_test.py

verify-moves: $(ENGINE)
	$(PYTHON) tools/verify_moves.py "$(ENGINE)" --positions 64 --depth 2 --output results/move-verification.json

bench: $(ENGINE)
	$(PYTHON) tools/bench.py "$(ENGINE)"

resources:
	$(PYTHON) tools/resources.py show

help:
	@echo 'make                  Build native portable-CPU executable (one job by default)'
	@echo 'make net              Fetch and verify the pinned official SF19 network'
	@echo 'make test             Run correctness checks; make net first'
	@echo 'make MODE=sanitize test   Address/undefined-behavior checks'
	@echo 'make SIMD=scalar test     Force portable scalar NNUE reference'
	@echo 'make test-match        Test optional match tools (requirements-match.txt)'
	@echo 'make test-bench        Test deterministic baseline/candidate comparisons'
	@echo 'make test-profile      Test clock-policy profiling and diagnostic validation'
	@echo 'make test-profile-lmr  Test selective-search profiles (requirements-match.txt)'
	@echo 'make verify-moves      Compare legal moves/perft with the optional referee'
	@echo 'make doctor           Verify selected compiler, standard library, target macros'
	@echo 'make TARGET=linux-arm64 CXX=aarch64-linux-gnu-g++'
	@echo 'make TARGET=windows-arm64 CXX=aarch64-w64-mingw32-clang++'
	@echo 'make resources        Print current local experiment budget'
	@echo 'Build outputs live in build/TARGET-CPU-MODE/'

clean:
	$(PYTHON) -c 'import shutil; shutil.rmtree("$(BUILD)", ignore_errors=True)'

-include $(OBJECTS:.o=.d)
