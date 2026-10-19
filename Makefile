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
ifeq ($(filter $(MODE),release debug sanitize thread-sanitize),)
  $(error MODE must be release, debug, sanitize, or thread-sanitize)
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
CPPFLAGS += -Iinclude -Ithird_party/fathom/src
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
else ifeq ($(MODE),thread-sanitize)
  CXXFLAGS += -O1 -g -fsanitize=thread -fno-omit-frame-pointer
  LDFLAGS += -fsanitize=thread
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

SOURCES := src/position.cpp src/nnue.cpp src/exchange.cpp src/tablebase.cpp src/search.cpp src/main.cpp
OBJECTS := $(patsubst src/%.cpp,$(BUILD)/%.o,$(SOURCES))
TB_OBJECTS := $(BUILD)/tablebase.o $(BUILD)/fathom.o
OBJECTS += $(BUILD)/fathom.o
NET := networks/nn-1a298aa575a0.nnue

.PHONY: all help doctor net test test-core test-nnue test-exchange test-search test-search-policy test-time test-clock-probes test-match test-bench test-profile test-profile-lmr test-profile-ordering test-profile-cpu test-profile-cache test-qualification test-phase3g test-phase3l verify-moves bench resources clean FORCE
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

# The external reader is isolated from engine code and compiled in C++26 mode.
$(BUILD)/fathom.o: third_party/fathom/src/tbprobe.c $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -Wno-deprecated-declarations -Wno-sign-compare -x c++ -MMD -MP -c "$<" -o "$@"

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

# Arithmetic oracles include NNUE internals for testing only; do not also
# link nnue.o. Dependency files track its included source and header changes.
$(BUILD)/nnue-updates-test$(EXE): tests/nnue_updates_test.cpp src/nnue.cpp $(BUILD)/position.o $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(LDFLAGS) -o "$@"

$(BUILD)/nnue-dense-test$(EXE): tests/nnue_dense_test.cpp src/nnue.cpp $(BUILD)/position.o $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(LDFLAGS) -o "$@"

$(BUILD)/search-test$(EXE): tests/search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) -o "$@"

$(BUILD)/exchange-test$(EXE): tests/exchange_test.cpp include/chess0live/exchange.hpp $(BUILD)/position.o $(BUILD)/exchange.o
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/exchange.o $(LDFLAGS) -o "$@"

$(BUILD)/time-management-test$(EXE): tests/time_management_test.cpp include/chess0live/time_management.hpp $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) -o "$@"

$(BUILD)/search-policy-test$(EXE): tests/search_policy_test.cpp include/chess0live/search_policy.hpp include/chess0live/types.hpp $(BUILD)/toolchain.ok
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) -o "$@"

test-core: $(ENGINE) $(BUILD)/position-test$(EXE)
	"$(BUILD)/position-test$(EXE)"
	$(PYTHON) tests/uci_test.py "$(ENGINE)"
	$(PYTHON) tests/resources_test.py

test-nnue: $(BUILD)/nnue-test$(EXE) $(BUILD)/nnue-updates-test$(EXE) $(BUILD)/nnue-dense-test$(EXE)
	"$(BUILD)/nnue-test$(EXE)" --network "$(NET)"
	"$(BUILD)/nnue-updates-test$(EXE)"
	"$(BUILD)/nnue-dense-test$(EXE)"

test-search: $(BUILD)/search-test$(EXE)
	"$(BUILD)/search-test$(EXE)" "$(NET)"

# Experimental null-search state and lifecycle checks; no strength claims.
NULL_MOVE_ACTIVATION_TIMEOUT ?= $(if $(filter thread-sanitize,$(MODE)),180,30)
$(BUILD)/null-state-test$(EXE): tests/null_state_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(LDFLAGS) -o "$@"

$(BUILD)/null-search-test$(EXE): tests/null_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) -o "$@"

.PHONY: test-null-state test-null-search test-null-move test-profile-null-move
test-null-state: $(BUILD)/null-state-test$(EXE)
	"$(BUILD)/null-state-test$(EXE)" "$(NET)"

test-null-search: $(BUILD)/null-search-test$(EXE)
	"$(BUILD)/null-search-test$(EXE)" "$(NET)"

test-null-move: $(ENGINE)
	$(PYTHON) tests/null_move_uci_test.py "$(ENGINE)" --network "$(NET)" --activation-timeout $(NULL_MOVE_ACTIVATION_TIMEOUT)

test-profile-null-move:
	$(PYTHON) tests/profile_null_move_test.py

# Experimental shallow static cutoffs; optional UCI tests use the referee.
REVERSE_FUTILITY_ACTIVATION_TIMEOUT ?= $(if $(filter thread-sanitize,$(MODE)),180,30)
$(BUILD)/reverse-futility-search-test$(EXE): tests/reverse_futility_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) -o "$@"

.PHONY: test-reverse-futility-search test-reverse-futility test-profile-reverse-futility
test-reverse-futility-search: $(BUILD)/reverse-futility-search-test$(EXE)
	"$(BUILD)/reverse-futility-search-test$(EXE)" "$(NET)"

test-reverse-futility: $(ENGINE)
	$(PYTHON) tests/reverse_futility_uci_test.py "$(ENGINE)" --network "$(NET)" --activation-timeout $(REVERSE_FUTILITY_ACTIVATION_TIMEOUT)

test-profile-reverse-futility:
	$(PYTHON) tests/profile_reverse_futility_test.py

# Optional independent-referee checks for the isolated quiet-reply experiment.
.PHONY: test-countermove test-profile-countermove
test-countermove: $(ENGINE)
	$(PYTHON) tests/countermove_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-countermove:
	$(PYTHON) tests/profile_countermove_test.py

test-time: $(BUILD)/time-management-test$(EXE)
	"$(BUILD)/time-management-test$(EXE)"

test-search-policy: $(BUILD)/search-policy-test$(EXE)
	"$(BUILD)/search-policy-test$(EXE)"

test-exchange: $(BUILD)/exchange-test$(EXE)
	"$(BUILD)/exchange-test$(EXE)"

test: test-core test-nnue test-exchange test-search test-search-policy test-time

# Explicit fixture download is separate from ordinary builds/tests. Data is ignored
# by Git; only the small checksum/provenance manifest is versioned.
SYZYGY_TEST_DIR ?= tablebases/test
.PHONY: fetch-syzygy-test test-fetch-syzygy test-syzygy
fetch-syzygy-test:
	$(PYTHON) tools/fetch_syzygy_test_tables.py --directory "$(SYZYGY_TEST_DIR)"

test-fetch-syzygy:
	$(PYTHON) tests/fetch_syzygy_test_tables_test.py

$(BUILD)/tablebase-test$(EXE): tests/tablebase_test.cpp tests/data/syzygy_cases.hpp $(BUILD)/position.o $(TB_OBJECTS)
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(TB_OBJECTS) $(LDFLAGS) -o "$@"

$(BUILD)/syzygy-search-test$(EXE): tests/syzygy_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(CXX) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) -o "$@"

.PHONY: test-syzygy-search
test-syzygy-search: $(BUILD)/syzygy-search-test$(EXE)
	$(PYTHON) tools/fetch_syzygy_test_tables.py --directory "$(SYZYGY_TEST_DIR)" --verify-only
	"$(BUILD)/syzygy-search-test$(EXE)" "$(NET)" "$(SYZYGY_TEST_DIR)"

test-syzygy: $(ENGINE) $(BUILD)/tablebase-test$(EXE) $(BUILD)/syzygy-search-test$(EXE)
	$(PYTHON) tools/fetch_syzygy_test_tables.py --directory "$(SYZYGY_TEST_DIR)" --verify-only
	"$(BUILD)/tablebase-test$(EXE)" "$(SYZYGY_TEST_DIR)"
	"$(BUILD)/syzygy-search-test$(EXE)" "$(NET)" "$(SYZYGY_TEST_DIR)"
	$(PYTHON) tests/syzygy_uci_test.py "$(ENGINE)" --network "$(NET)" --tables "$(SYZYGY_TEST_DIR)"

# Optional independent referee checks: install requirements-match.txt first.
# Keep the engine's ordinary correctness suite free of third-party Python deps.
test-match:
	$(PYTHON) tests/match_statistics_test.py
	$(PYTHON) tests/match_test.py

test-bench:
	$(PYTHON) tests/compare_bench_test.py

test-profile:
	$(PYTHON) tests/profile_search_test.py

# Optional saved-position clock diagnostics; requires requirements-match.txt.
test-clock-probes:
	$(PYTHON) tests/probe_clocks_test.py
	$(PYTHON) tests/probe_receipt_test.py

test-profile-lmr:
	$(PYTHON) tests/profile_lmr_test.py

test-profile-ordering: test-profile-lmr

# Optional macOS CPU recorder; these mock tests need no process inspection.
test-profile-cpu:
	$(PYTHON) tests/profile_cpu_test.py

test-profile-cache:
	$(PYTHON) tests/profile_cache_test.py

# Lazy SMP protocol/PV checks use the optional independent python-chess referee.
.PHONY: test-smp test-profile-smp
test-smp: $(ENGINE)
	$(PYTHON) tests/smp_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-smp:
	$(PYTHON) tests/profile_smp_test.py

# Optional frozen Phase 2D workflow, including independent evidence auditing.
test-qualification: test-phase3g test-phase3l test-phase4d2
	$(PYTHON) tests/qualify_time_policy_test.py
	$(PYTHON) tests/audit_time_policy_test.py
	$(PYTHON) tests/qualify_lmr_test.py
	$(PYTHON) tests/audit_lmr_test.py

test-phase3g:
	$(PYTHON) tests/phase3g_openings_test.py
	$(PYTHON) tests/qualify_phase3g_test.py
	$(PYTHON) tests/audit_phase3g_test.py

test-phase3l:
	$(PYTHON) tests/phase3l_openings_test.py
	$(PYTHON) tests/qualify_phase3l_test.py
	$(PYTHON) tests/audit_phase3l_test.py

.PHONY: test-phase4d2
test-phase4d2:
	$(PYTHON) tests/phase4d2_openings_test.py
	$(PYTHON) tests/phase4d2_load_test.py
	$(PYTHON) tests/qualify_phase4d2_test.py
	$(PYTHON) tests/audit_phase4d2_test.py

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
	@echo 'make MODE=thread-sanitize test-search test-smp   Shared-state race checks'
	@echo 'make fetch-syzygy-test Download the pinned small tablebase test corpus'
	@echo 'make test-syzygy       Test local Syzygy data, probing and UCI lifecycle'
	@echo 'make test-smp          Parallel UCI/PV checks (requirements-match.txt)'
	@echo 'make test-profile-smp  Test the bounded parallel scaling profiler'
	@echo 'make test-countermove test-profile-countermove  Check experimental quiet reply ordering'
	@echo 'make test-null-state test-null-search test-null-move  Check experimental verified null pruning'
	@echo 'make test-reverse-futility-search test-reverse-futility  Check experimental static pruning'
	@echo 'make SIMD=scalar test     Force portable scalar NNUE reference'
	@echo 'make test-match        Test optional match tools (requirements-match.txt)'
	@echo 'make test-qualification Test fixed qualification launchers and evidence audits'
	@echo 'make test-phase3g      Test fresh openings, coordinated launcher, and aggregate audit'
	@echo 'make test-phase3l      Test fresh qualification inputs, readiness, supervision, and audit'
	@echo 'make test-phase4d2     Test current-engine LMR campaign tools without launching games'
	@echo 'make test-bench        Test deterministic baseline/candidate comparisons'
	@echo 'make test-profile      Test clock-policy profiling and diagnostic validation'
	@echo 'make test-profile-cache Test cache profiling, counter validation, and failure evidence'
	@echo 'make test-clock-probes Test saved-position clock diagnostic validation'
	@echo 'make test-profile-lmr  Test selective-search profiles (requirements-match.txt)'
	@echo 'make test-profile-ordering  Test isolated capture-ordering profiles'
	@echo 'make test-profile-cpu  Test bounded CPU-profile recording and cleanup'
	@echo 'make verify-moves      Compare legal moves/perft with the optional referee'
	@echo 'make doctor           Verify selected compiler, standard library, target macros'
	@echo 'make TARGET=linux-arm64 CXX=aarch64-linux-gnu-g++'
	@echo 'make TARGET=windows-arm64 CXX=aarch64-w64-mingw32-clang++'
	@echo 'make resources        Print current local experiment budget'
	@echo 'Build outputs live in build/TARGET-CPU-MODE/'

clean:
	$(PYTHON) -c 'import shutil; shutil.rmtree("$(BUILD)", ignore_errors=True)'

-include $(OBJECTS:.o=.d) $(BUILD)/nnue-updates-test.d $(BUILD)/nnue-dense-test.d
