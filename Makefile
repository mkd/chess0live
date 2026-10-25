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
CLOCK_TRACE ?= 0
PYTHON ?= python3
# Managed packages for optional tools only; ordinary builds/tests stay stdlib-only.
TOOL_PYTHON = $(PYTHON) tools/run.py
ifeq ($(origin CXX),default)
  CXX := c++
endif
# Optional literal-path mode for managed toolchains, including paths with spaces.
# Export the path rather than expanding it into shell command text. CXX retains
# its existing shell-style command/wrapper interface when this mode is absent.
override CXX_EXECUTABLE := $(value CXX_EXECUTABLE)
export CXX_EXECUTABLE
ifneq ($(strip $(CXX_EXECUTABLE)),)
  COMPILER_COMMAND = $(PYTHON) tools/invoke_compiler.py
  COMPILER_PROBE = --compiler-env CXX_EXECUTABLE
else
  COMPILER_COMMAND = $(CXX)
  COMPILER_PROBE = --compiler "$(CXX)"
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
ifeq ($(filter $(CLOCK_TRACE),0 1),)
  $(error CLOCK_TRACE must be 0 or 1)
endif
ifeq ($(CPU),native)
  ifneq ($(TARGET),$(HOST_TARGET))
    $(error CPU=native cannot be used for a cross-build)
  endif
endif

BUILD := build/$(TARGET)-$(CPU)-$(MODE)$(if $(filter scalar,$(SIMD)),-scalar,)$(if $(filter 1,$(CLOCK_TRACE)),-clock-trace,)
EXE := $(if $(filter windows-%,$(TARGET)),.exe,)
ENGINE := $(BUILD)/chess0live$(EXE)
CPPFLAGS += -Iinclude -Ithird_party/fathom/src
ifeq ($(CLOCK_TRACE),1)
  # Timing instrumentation is absent from ordinary builds and has its own
  # output directory so diagnostic binaries cannot replace normal GUI builds.
  CPPFLAGS += -DCHESS0LIVE_CLOCK_TRACE
endif
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

# One-command target setup/build. Outputs live separately from ordinary GUI
# builds. Python detects compilers and provisions supported local bundles.
TOOLCHAIN ?= auto
BUILD_JOBS ?=
OFFLINE ?= 0
# Python's host detection also works without Unix uname on native Windows.
ifneq ($(filter file default undefined,$(origin TARGET)),)
  PORTABLE_TARGET =
else
  PORTABLE_TARGET = --target "$(TARGET)"
endif
.PHONY: portable toolchain-plan toolchain-check test-build-setup
portable:
	$(PYTHON) tools/build.py $(PORTABLE_TARGET) --mode "$(MODE)" --toolchain "$(TOOLCHAIN)" $(if $(BUILD_JOBS),--jobs $(BUILD_JOBS),) $(if $(filter 1,$(OFFLINE)),--offline,)

toolchain-plan:
	$(PYTHON) tools/build.py $(PORTABLE_TARGET) --mode "$(MODE)" --toolchain "$(TOOLCHAIN)" --plan $(if $(filter 1,$(OFFLINE)),--offline,)

toolchain-check:
	$(PYTHON) tools/build.py $(PORTABLE_TARGET) --mode "$(MODE)" --toolchain "$(TOOLCHAIN)" --check $(if $(filter 1,$(OFFLINE)),--offline,)

test-build-setup: test-compiler-path
	$(PYTHON) tests/toolchain_cache_test.py
	$(PYTHON) tests/build_setup_test.py

$(BUILD):
	mkdir -p "$@"

# Run a target-specific compile check before building any engine object. It catches
# a host compiler accidentally used to produce a mislabeled cross-target binary.
FORCE:

$(BUILD)/toolchain.ok: FORCE tools/check_toolchain.py tools/invoke_compiler.py Makefile | $(BUILD)
	@$(PYTHON) tools/check_toolchain.py --target $(TARGET) $(COMPILER_PROBE) --flags '$(CPPFLAGS) $(CXXFLAGS)' --link-flags '$(LDFLAGS) $(LDLIBS)' --output "$(BUILD)/toolchain-probe.o" --stamp "$@"

$(BUILD)/%.o: src/%.cpp $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c "$<" -o "$@"

# The external reader is isolated from engine code and compiled in C++26 mode.
$(BUILD)/fathom.o: third_party/fathom/src/tbprobe.c $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(CXXFLAGS) -Wno-deprecated-declarations -Wno-sign-compare -x c++ -MMD -MP -c "$<" -o "$@"

$(ENGINE): $(OBJECTS)
	$(COMPILER_COMMAND) $(OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

# Build the portable correctness executables without trying to run a foreign
# binary on the build host. Copy the checkout/build directory to its target,
# or use an explicit emulator with tools/verify_runtime.py.
RUNTIME_TESTS := position-test nnue-test nnue-updates-test nnue-dense-test search-test search-policy-test time-management-test
.PHONY: runtime-binaries verify-runtime test-runtime-tools
runtime-binaries: $(ENGINE) $(addprefix $(BUILD)/,$(addsuffix $(EXE),$(RUNTIME_TESTS)))

verify-runtime: runtime-binaries
	$(PYTHON) tools/verify_runtime.py --build "$(BUILD)" --target "$(TARGET)" --network "$(NET)" --execution native

test-runtime-tools:
	$(PYTHON) tests/verify_runtime_test.py
	$(PYTHON) tests/runtime_build_test.py

doctor: | $(BUILD)
	$(PYTHON) tools/check_toolchain.py --target $(TARGET) $(COMPILER_PROBE) --flags '$(CPPFLAGS) $(CXXFLAGS)' --output "$(BUILD)/toolchain-probe.o"

net:
	$(PYTHON) tools/fetch_network.py

# Network inspection needs only Python's standard library. Qualification builds
# separate oracle adapters; it never replaces an engine or selected network.
.PHONY: network-inspect network-qualify test-network-tools
network-inspect:
	$(PYTHON) tools/network.py inspect

network-qualify:
	$(PYTHON) tools/network.py qualify $(if $(filter 1,$(OFFLINE)),--offline,)

test-network-tools:
	$(PYTHON) tests/network_tool_test.py
	$(PYTHON) tests/verify_nnue_candidate_test.py

.PHONY: network-status network-list network-default network-revert network-run test-managed-networks
network-status:
	$(PYTHON) tools/managed_network.py status

network-list:
	$(PYTHON) tools/managed_network.py list

network-default:
	$(PYTHON) tools/managed_network.py select default

network-revert:
	$(PYTHON) tools/managed_network.py revert

network-run: $(ENGINE)
	$(PYTHON) tools/managed_network.py run --engine "$(ENGINE)"

test-managed-networks: $(ENGINE)
	$(PYTHON) tests/managed_network_test.py
	$(PYTHON) tests/network_receipt_test.py
	$(PYTHON) tests/eval_file_cli_test.py "$(ENGINE)" --network "$(NET)"

.PHONY: training-plan training-setup training-smoke test-training
training-plan:
	$(PYTHON) tools/train.py plan

training-setup:
	$(PYTHON) tools/training_setup.py $(if $(filter 1,$(OFFLINE)),--offline,)

training-smoke:
	$(PYTHON) tools/train.py smoke $(if $(filter 1,$(OFFLINE)),--offline,)

test-training:
	$(PYTHON) tests/training_setup_test.py
	$(PYTHON) tests/train_test.py
	$(PYTHON) tests/network_tool_test.py

$(BUILD)/position-test$(EXE): tests/position_test.cpp $(BUILD)/position.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/tactical-moves-test$(EXE): tests/tactical_moves_test.cpp $(BUILD)/position.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-tactical-moves test-profile-search-baseline test-profile-search-package
test-tactical-moves: $(BUILD)/tactical-moves-test$(EXE)
	"$(BUILD)/tactical-moves-test$(EXE)"

test-profile-search-baseline:
	$(TOOL_PYTHON) tests/profile_search_baseline_test.py

test-profile-search-package:
	$(TOOL_PYTHON) tests/profile_search_package_test.py

$(BUILD)/nnue-test$(EXE): tests/nnue_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(LDFLAGS) $(LDLIBS) -o "$@"

# Arithmetic oracles include NNUE internals for testing only; do not also
# link nnue.o. Dependency files track its included source and header changes.
$(BUILD)/nnue-updates-test$(EXE): tests/nnue_updates_test.cpp src/nnue.cpp $(BUILD)/position.o $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/nnue-dense-test$(EXE): tests/nnue_dense_test.cpp src/nnue.cpp $(BUILD)/position.o $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/search-test$(EXE): tests/search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

# Direct ordering checks include search.cpp to compare worker-private behavior;
# link the other engine objects but not search.o. No NNUE file is needed.
$(BUILD)/ordering-search-test$(EXE): tests/ordering_search_test.cpp src/search.cpp include/chess0live/search.hpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-ordering-search
test-ordering-search: $(BUILD)/ordering-search-test$(EXE)
	"$(BUILD)/ordering-search-test$(EXE)"

$(BUILD)/exchange-test$(EXE): tests/exchange_test.cpp include/chess0live/exchange.hpp $(BUILD)/position.o $(BUILD)/exchange.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/exchange.o $(LDFLAGS) $(LDLIBS) -o "$@"

# Includes exchange.cpp to compare private attack masks with an independent
# ray-walking reference. Do not also link exchange.o into this executable.
$(BUILD)/exchange-attacks-test$(EXE): tests/exchange_attacks_test.cpp src/exchange.cpp $(BUILD)/position.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/time-management-test$(EXE): tests/time_management_test.cpp include/chess0live/time_management.hpp $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/search-policy-test$(EXE): tests/search_policy_test.cpp include/chess0live/search_policy.hpp include/chess0live/types.hpp $(BUILD)/toolchain.ok
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(LDFLAGS) $(LDLIBS) -o "$@"

test-core: $(ENGINE) $(BUILD)/position-test$(EXE) $(BUILD)/tactical-moves-test$(EXE)
	"$(BUILD)/position-test$(EXE)"
	"$(BUILD)/tactical-moves-test$(EXE)"
	$(PYTHON) tests/uci_test.py "$(ENGINE)"
	$(PYTHON) tests/resources_test.py

test-nnue: $(BUILD)/nnue-test$(EXE) $(BUILD)/nnue-updates-test$(EXE) $(BUILD)/nnue-dense-test$(EXE)
	"$(BUILD)/nnue-test$(EXE)" --network "$(NET)"
	"$(BUILD)/nnue-updates-test$(EXE)"
	"$(BUILD)/nnue-dense-test$(EXE)"

test-search: $(BUILD)/search-test$(EXE) $(BUILD)/ordering-search-test$(EXE)
	"$(BUILD)/search-test$(EXE)" "$(NET)"
	"$(BUILD)/ordering-search-test$(EXE)"

# Isolated deeper-reduction and clock policies; both remain opt-in.
$(BUILD)/deep-quiet-search-test$(EXE): tests/deep_quiet_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/bounded-time-test$(EXE): tests/bounded_time_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-deep-quiet-search test-deep-quiet-uci test-bounded-time test-bounded-time-uci test-profile-deep-quiet
test-deep-quiet-search: $(BUILD)/deep-quiet-search-test$(EXE)
	"$(BUILD)/deep-quiet-search-test$(EXE)" "$(NET)"

test-deep-quiet-uci: $(ENGINE)
	$(TOOL_PYTHON) tests/deep_quiet_uci_test.py "$(ENGINE)" --network "$(NET)"

test-bounded-time: $(BUILD)/bounded-time-test$(EXE)
	"$(BUILD)/bounded-time-test$(EXE)" "$(NET)"

test-bounded-time-uci: $(ENGINE)
	$(TOOL_PYTHON) tests/bounded_time_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-deep-quiet:
	$(TOOL_PYTHON) tests/profile_deep_quiet_test.py

# The direct probe regression includes search.cpp to inspect speculative state;
# do not also link search.o. Production builds expose only the ordinary API.
$(BUILD)/probcut-search-test$(EXE): tests/probcut_search_test.cpp src/search.cpp include/chess0live/search.hpp include/chess0live/search_policy.hpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) -MMD -MP "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-probcut-search test-probcut-uci test-profile-probcut
test-probcut-search: $(BUILD)/probcut-search-test$(EXE)
	"$(BUILD)/probcut-search-test$(EXE)" "$(NET)"

test-probcut-uci: $(ENGINE)
	$(TOOL_PYTHON) tests/probcut_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-probcut:
	$(TOOL_PYTHON) tests/profile_probcut_test.py

# Experimental null-search state and lifecycle checks; no strength claims.
NULL_MOVE_ACTIVATION_TIMEOUT ?= $(if $(filter thread-sanitize,$(MODE)),180,30)
$(BUILD)/null-state-test$(EXE): tests/null_state_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/null-search-test$(EXE): tests/null_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-null-state test-null-search test-null-move test-profile-null-move
test-null-state: $(BUILD)/null-state-test$(EXE)
	"$(BUILD)/null-state-test$(EXE)" "$(NET)"

test-null-search: $(BUILD)/null-search-test$(EXE)
	"$(BUILD)/null-search-test$(EXE)" "$(NET)"

test-null-move: $(ENGINE)
	$(TOOL_PYTHON) tests/null_move_uci_test.py "$(ENGINE)" --network "$(NET)" --activation-timeout $(NULL_MOVE_ACTIVATION_TIMEOUT)

test-profile-null-move:
	$(TOOL_PYTHON) tests/profile_null_move_test.py

# Experimental shallow static cutoffs; optional UCI tests use the referee.
REVERSE_FUTILITY_ACTIVATION_TIMEOUT ?= $(if $(filter thread-sanitize,$(MODE)),180,30)
$(BUILD)/reverse-futility-search-test$(EXE): tests/reverse_futility_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-reverse-futility-search test-reverse-futility test-profile-reverse-futility
test-reverse-futility-search: $(BUILD)/reverse-futility-search-test$(EXE)
	"$(BUILD)/reverse-futility-search-test$(EXE)" "$(NET)"

test-reverse-futility: $(ENGINE)
	$(TOOL_PYTHON) tests/reverse_futility_uci_test.py "$(ENGINE)" --network "$(NET)" --activation-timeout $(REVERSE_FUTILITY_ACTIVATION_TIMEOUT)

test-profile-reverse-futility:
	$(TOOL_PYTHON) tests/profile_reverse_futility_test.py

# Experimental losing-capture filter; off by default and independently checked.
QSEARCH_SEE_ACTIVATION_TIMEOUT ?= $(if $(filter thread-sanitize,$(MODE)),180,30)
$(BUILD)/qsearch-see-search-test$(EXE): tests/qsearch_see_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-qsearch-see-search test-qsearch-see test-profile-qsearch-see
test-qsearch-see-search: $(BUILD)/qsearch-see-search-test$(EXE)
	"$(BUILD)/qsearch-see-search-test$(EXE)" "$(NET)"

test-qsearch-see: $(ENGINE)
	$(TOOL_PYTHON) tests/qsearch_see_uci_test.py "$(ENGINE)" --network "$(NET)" --activation-timeout $(QSEARCH_SEE_ACTIVATION_TIMEOUT)

test-profile-qsearch-see:
	$(TOOL_PYTHON) tests/profile_qsearch_see_test.py

# Optional independent-referee checks for the isolated quiet-reply experiment.
.PHONY: test-countermove test-profile-countermove
test-countermove: $(ENGINE)
	$(TOOL_PYTHON) tests/countermove_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-countermove:
	$(TOOL_PYTHON) tests/profile_countermove_test.py

test-time: $(BUILD)/time-management-test$(EXE)
	"$(BUILD)/time-management-test$(EXE)"

test-search-policy: $(BUILD)/search-policy-test$(EXE)
	"$(BUILD)/search-policy-test$(EXE)"

test-exchange: $(BUILD)/exchange-test$(EXE) $(BUILD)/exchange-attacks-test$(EXE)
	"$(BUILD)/exchange-test$(EXE)"
	"$(BUILD)/exchange-attacks-test$(EXE)"

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
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

$(BUILD)/syzygy-search-test$(EXE): tests/syzygy_search_test.cpp $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS)
	$(COMPILER_COMMAND) $(CPPFLAGS) $(filter-out -DNDEBUG,$(CXXFLAGS)) "$<" $(BUILD)/position.o $(BUILD)/nnue.o $(BUILD)/exchange.o $(BUILD)/search.o $(TB_OBJECTS) $(LDFLAGS) $(LDLIBS) -o "$@"

.PHONY: test-syzygy-search
test-syzygy-search: $(BUILD)/syzygy-search-test$(EXE)
	$(PYTHON) tools/fetch_syzygy_test_tables.py --directory "$(SYZYGY_TEST_DIR)" --verify-only
	"$(BUILD)/syzygy-search-test$(EXE)" "$(NET)" "$(SYZYGY_TEST_DIR)"

test-syzygy: $(ENGINE) $(BUILD)/tablebase-test$(EXE) $(BUILD)/syzygy-search-test$(EXE)
	$(PYTHON) tools/fetch_syzygy_test_tables.py --directory "$(SYZYGY_TEST_DIR)" --verify-only
	"$(BUILD)/tablebase-test$(EXE)" "$(SYZYGY_TEST_DIR)"
	"$(BUILD)/syzygy-search-test$(EXE)" "$(NET)" "$(SYZYGY_TEST_DIR)"
	$(TOOL_PYTHON) tests/syzygy_uci_test.py "$(ENGINE)" --network "$(NET)" --tables "$(SYZYGY_TEST_DIR)"

# Optional independent referee checks configure their pinned dependency automatically.
# Keep the engine's ordinary correctness suite free of third-party Python deps.
test-match:
	$(PYTHON) tests/match_statistics_test.py
	$(TOOL_PYTHON) tests/match_test.py

test-bench:
	$(PYTHON) tests/compare_bench_test.py

test-profile:
	$(PYTHON) tests/profile_search_test.py

# Optional saved-position clock diagnostics use the managed Python environment.
test-clock-probes:
	$(TOOL_PYTHON) tests/probe_clocks_test.py
	$(TOOL_PYTHON) tests/probe_receipt_test.py

.PHONY: test-clock-boundaries test-clock-trace
test-clock-boundaries:
	$(TOOL_PYTHON) tests/probe_clock_boundaries_test.py

# Use CLOCK_TRACE=1; this checks the diagnostic binary, not a timing threshold.
test-clock-trace: $(ENGINE)
	$(TOOL_PYTHON) tests/clock_boundary_uci.py "$(ENGINE)" "$(NET)"

.PHONY: test-match-readiness
test-match-readiness:
	$(TOOL_PYTHON) tests/check_match_readiness_test.py
	$(TOOL_PYTHON) tests/audit_match_readiness_test.py

.PHONY: test-lmr-qualification
test-lmr-qualification:
	$(TOOL_PYTHON) tests/lmr_20261022_openings_test.py
	$(TOOL_PYTHON) tests/qualify_lmr_20261022_test.py
	$(TOOL_PYTHON) tests/audit_lmr_20261022_test.py

.PHONY: test-phase4f3
test-phase4f3:
	$(TOOL_PYTHON) tests/phase4f3_openings_test.py
	$(TOOL_PYTHON) tests/qualify_phase4f3_test.py
	$(TOOL_PYTHON) tests/audit_phase4f3_test.py
	$(TOOL_PYTHON) tests/phase4f3_puzzles_test.py

test-profile-lmr:
	$(TOOL_PYTHON) tests/profile_lmr_test.py

test-profile-ordering: test-profile-lmr

# Optional macOS CPU recorder; these mock tests need no process inspection.
test-profile-cpu:
	$(TOOL_PYTHON) tests/profile_cpu_test.py

test-profile-cache:
	$(TOOL_PYTHON) tests/profile_cache_test.py

# Lazy SMP protocol/PV checks use the optional independent python-chess referee.
.PHONY: test-smp test-profile-smp
test-smp: $(ENGINE)
	$(TOOL_PYTHON) tests/smp_uci_test.py "$(ENGINE)" --network "$(NET)"

test-profile-smp:
	$(TOOL_PYTHON) tests/profile_smp_test.py

# Optional frozen Phase 2D workflow, including independent evidence auditing.
test-qualification: test-phase3g test-phase3l test-phase4d2
	$(TOOL_PYTHON) tests/qualify_time_policy_test.py
	$(TOOL_PYTHON) tests/audit_time_policy_test.py
	$(TOOL_PYTHON) tests/qualify_lmr_test.py
	$(TOOL_PYTHON) tests/audit_lmr_test.py

test-phase3g:
	$(TOOL_PYTHON) tests/phase3g_openings_test.py
	$(TOOL_PYTHON) tests/qualify_phase3g_test.py
	$(TOOL_PYTHON) tests/audit_phase3g_test.py

test-phase3l:
	$(TOOL_PYTHON) tests/phase3l_openings_test.py
	$(TOOL_PYTHON) tests/qualify_phase3l_test.py
	$(TOOL_PYTHON) tests/audit_phase3l_test.py

.PHONY: test-phase4d2
test-phase4d2:
	$(TOOL_PYTHON) tests/phase4d2_openings_test.py
	$(TOOL_PYTHON) tests/phase4d2_load_test.py
	$(TOOL_PYTHON) tests/qualify_phase4d2_test.py
	$(TOOL_PYTHON) tests/audit_phase4d2_test.py

verify-moves: $(ENGINE)
	$(TOOL_PYTHON) tools/verify_moves.py "$(ENGINE)" --positions 64 --depth 2 --output results/move-verification.json

bench: $(ENGINE)
	$(PYTHON) tools/bench.py "$(ENGINE)"

resources:
	$(PYTHON) tools/resources.py show

help:
	@echo 'make portable TARGET=...  Select/prepare a compiler and build in build/portable/'
	@echo 'make toolchain-plan       Show routes without downloads or compiler execution'
	@echo 'make toolchain-check      Prepare and compile/link-check the target toolchain'
	@echo 'make test-build-setup     Check compiler routing and local toolchain provisioning'
	@echo 'make tooling           Prepare pinned Python tools (also automatic on use)'
	@echo 'make test-tooling      Check dependency setup and the batch puzzle runner'
	@echo 'make network-inspect   Identify the default network and known provenance'
	@echo 'make network-qualify   Compare its arithmetic with the pinned SF19 oracle'
	@echo 'make test-network-tools Check network inspection and qualification tooling'
	@echo 'make network-status   Inspect the managed network selection and provenance'
	@echo 'make network-list     List registered networks and verification status'
	@echo 'make network-run      Launch this build with the managed network selection'
	@echo 'make network-default  Select the original pinned network for managed launches'
	@echo 'make network-revert   Restore the previous managed network selection'
	@echo 'make test-managed-networks Check catalog integrity and explicit engine selection'
	@echo 'make test-tactical-moves Check tactical generation and legal mobility witnesses'
	@echo 'make test-ordering-search Check move priorities, SEE counters and worker tie order'
	@echo 'make test-profile-search-baseline Check the current-policy search comparison tool'
	@echo 'make test-profile-search-package Check the bounded search-package diagnostic tool'
	@echo 'make training-plan    Show local training requirements without setup'
	@echo 'make training-smoke   Run tiny synthetic training, export and qualification'
	@echo 'make test-training    Check training setup, recipes and provenance tooling'
	@echo 'make                  Build native portable-CPU executable (one job by default)'
	@echo 'make net              Fetch and verify the pinned official SF19 network'
	@echo 'make test             Run correctness checks; make net first'
	@echo 'make MODE=sanitize test   Address/undefined-behavior checks'
	@echo 'make MODE=thread-sanitize test-search test-smp   Shared-state race checks'
	@echo 'make fetch-syzygy-test Download the pinned small tablebase test corpus'
	@echo 'make test-syzygy       Test local Syzygy data, probing and UCI lifecycle'
	@echo 'make test-smp          Parallel UCI/PV checks (automatic Python setup)'
	@echo 'make test-profile-smp  Test the bounded parallel scaling profiler'
	@echo 'make test-countermove test-profile-countermove  Check experimental quiet reply ordering'
	@echo 'make test-null-state test-null-search test-null-move  Check experimental verified null pruning'
	@echo 'make test-reverse-futility-search test-reverse-futility  Check experimental static pruning'
	@echo 'make SIMD=scalar test     Force portable scalar NNUE reference'
	@echo 'make test-match        Test optional match tools (automatic Python setup)'
	@echo 'make test-match-readiness Test bounded match supervisor and raw auditor'
	@echo 'make test-lmr-qualification Test fresh fixed LMR qualification workflow'
	@echo 'make test-phase4f3     Check combined-policy puzzle/match tools without launching games'
	@echo 'make test-qualification Test fixed qualification launchers and evidence audits'
	@echo 'make test-phase3g      Test fresh openings, coordinated launcher, and aggregate audit'
	@echo 'make test-phase3l      Test fresh qualification inputs, readiness, supervision, and audit'
	@echo 'make test-phase4d2     Test current-engine LMR campaign tools without launching games'
	@echo 'make test-bench        Test deterministic baseline/candidate comparisons'
	@echo 'make test-profile      Test clock-policy profiling and diagnostic validation'
	@echo 'make test-profile-cache Test cache profiling, counter validation, and failure evidence'
	@echo 'make test-clock-probes Test saved-position clock diagnostic validation'
	@echo 'make test-profile-lmr  Test selective-search profiles (automatic Python setup)'
	@echo 'make test-profile-ordering  Test isolated capture-ordering profiles'
	@echo 'make test-profile-cpu  Test bounded CPU-profile recording and cleanup'
	@echo 'make verify-moves      Compare legal moves/perft with the optional referee'
	@echo 'make runtime-binaries Build engine and portable tests without executing them'
	@echo 'make verify-runtime   Run bounded native checks and save an evidence report'
	@echo 'make test-runtime-tools Test the runtime verifier and portable link recipes'
	@echo 'make doctor           Verify selected compiler, standard library, target macros'
	@echo 'make TARGET=linux-arm64 CXX=aarch64-linux-gnu-g++'
	@echo 'make TARGET=windows-arm64 CXX=aarch64-w64-mingw32-clang++'
	@echo 'make resources        Print current local experiment budget'
	@echo 'Build outputs live in build/TARGET-CPU-MODE/'

clean:
	$(PYTHON) -c 'import shutil; shutil.rmtree("$(BUILD)", ignore_errors=True)'

-include $(OBJECTS:.o=.d) $(BUILD)/nnue-updates-test.d $(BUILD)/nnue-dense-test.d \
         $(BUILD)/exchange-attacks-test.d

# Setup is also automatic in TOOL_PYTHON recipes and direct batch puzzle runs.
.PHONY: tooling test-tooling
tooling:
	$(PYTHON) tools/run.py --setup

test-tooling:
	$(PYTHON) tests/tooling_test.py
	$(TOOL_PYTHON) tests/batch_positions_test.py

.PHONY: test-compiler-path
test-compiler-path:
	$(PYTHON) tests/compiler_path_test.py
