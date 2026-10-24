# Portability

GNU Make is the public interface. C++26 mode does not mean that every C++26
feature is available: compiler and standard-library support must both be checked.
The versions below are observed working toolchains, not claims about the oldest
supported compiler. Run `make doctor` to check the selected target and required
facilities before relying on a different toolchain or standard library.

## Automatic target setup

The new frontend keeps GNU Make as the build engine and chooses a complete
compiler for the requested target. From the checkout:

```sh
make portable
make portable TARGET=linux-arm64
make portable TARGET=windows-arm64
make toolchain-plan TARGET=linux-riscv64
make toolchain-check TARGET=windows-arm64
```

The equivalent direct command is `python3 tools/build.py --target <target>`;
on Windows use `py -3 tools/build.py --target <target>`. Supported targets are
`macos-arm64`, `linux-x86_64`, `linux-arm64`, `linux-riscv64`, `windows-x86_64`
and `windows-arm64`. Omit the target to let Python detect the host, including
native Windows hosts without Unix `uname`.

`--plan` is read-only: it reports candidates without compiler execution or
downloads. `--check` may prepare a toolchain, compiles and links a small C++26
probe, and checks its binary architecture; it never executes that probe.
The ordinary build command then compiles through Make and records the engine's
hash/header and actual build configuration. Execution correctness is a separate
step using the [runtime verifier](#run-the-portable-checks).

| Route | Automatic behavior | Remaining prerequisite |
| --- | --- | --- |
| Native macOS ARM64 | Discover/check the installed compiler | macOS, Apple SDK/Command Line Tools, C++26 compiler and GNU Make |
| Native or cross-target Linux | Discover/check installed native or target-prefixed GCC/Clang, including versioned GCC 14–17 | Complete target libc/C++ libraries and GNU Make; install a suitable compiler if absent |
| Windows x86-64 or ARM64 | Try installed compilers, then provision pinned LLVM-MinGW when needed | Supported host runtime; see host coverage below |
| Linux/Windows to macOS | Reject with a clear SDK/host explanation | The supported macOS route requires macOS and Apple's SDK |

The pinned LLVM-MinGW bundle has macOS ARM64, Linux ARM64/x86-64, and Windows
ARM64/x86-64 host packages, each capable of both Windows targets. There is no
pinned RISC-V-host bundle. Linux packages were built for Ubuntu 22.04; host C
library compatibility is still required. Native Windows packages include GNU
Make and a BusyBox shell; the frontend selects them together when it provisions
the bundle. Their native Windows execution remains unverified. The fresh real
setup checks cover macOS ARM64 and a Linux ARM64 VM; metadata/synthetic ZIP
checks are not native Windows evidence. See [the report](reports/2026-10-24-phase4e4.md).

Python 3.10+ is required for this frontend, with no third-party Python packages.
It never installs system packages, changes global compiler settings, obtains an
Apple SDK, launches a foreign executable, or downloads a network/tablebase.
Linux prerequisite examples below remain explicit package-manager steps. On
Debian trixie, a cross-target compiler can be installed with GNU Make and the
corresponding target C library development package, for example:

```sh
apt-get install make g++-14-aarch64-linux-gnu libc6-dev-arm64-cross
apt-get install make g++-14-x86-64-linux-gnu libc6-dev-amd64-cross
apt-get install make g++-14-riscv64-linux-gnu libc6-dev-riscv64-cross
```

These are administrator operations **inside that Debian environment**, not
commands run automatically on the user's host. Other distributions/package
managers differ. Package names are documented by Debian for
[ARM64 GCC](https://packages.debian.org/trixie/g%2B%2B-14-aarch64-linux-gnu),
[x86-64 GCC](https://packages.debian.org/trixie/g%2B%2B-14-x86-64-linux-gnu),
[ARM64 libc](https://packages.debian.org/trixie/libc6-dev-arm64-cross) and
[x86-64 libc](https://packages.debian.org/trixie/libc6-dev-amd64-cross).
Once installed, `make portable TARGET=...` discovers them.

### Output, overrides and cache

Outputs use `build/portable/<target>-generic-<release|debug>/`; ordinary build
and frozen GUI directories are preserved. `--runtime-binaries` also builds the
seven portable correctness executables. `MODE=debug`/`--mode debug` changes mode.
The default job count is at most two and respects the local resource policy;
`BUILD_JOBS=N`/`--jobs N` requests another permitted count. Without IANA timezone
data, the frontend conservatively limits builds to one worker. Other workloads
still count toward the aggregate resource budget.

Use `TOOLCHAIN=installed`/`--toolchain installed` to forbid automatic provisioning,
or `TOOLCHAIN=llvm-mingw`/`--toolchain llvm-mingw` to select the pinned Windows
bundle explicitly. `OFFLINE=1`/`--offline` forbids downloads while permitting a
verified cached archive to be extracted. `--compiler /path/to/compiler` selects
one literal executable; `CXX_EXECUTABLE` is its environment/Make equivalent.
Paths with spaces are passed as arguments, and target-prefixed symlink names
are preserved. Legacy `CXX='wrapper compiler flags'` remains available through
the ordinary Make interface; the automatic frontend deliberately uses the
literal executable interface. `--make /path/to/make` selects GNU Make explicitly.

The setup probe checks a complete toolchain with the standard C++26/thread/static
Windows flags. It does not validate arbitrary custom `SYSROOT`/compiler flag
combinations. Use ordinary `make doctor`/`make` with explicit flags for those;
actual builds still record their effective configuration in `toolchain.ok`.

Toolchains live under ignored `.local/toolchains/` by default. Set
`CHESS0LIVE_TOOLCHAIN_CACHE` to another local directory to keep them outside
cloud synchronization or a read-only checkout. The committed
[manifest](../tools/toolchains.json) pins official release URLs, archive sizes,
SHA-256 hashes and provenance. Cached archives are verified before extraction;
the previous `build/toolchains/` archive can be reused after verification.
Upstream notices are retained. Extraction rejects escaping paths/links and
special files, preserves required internal aliases, and publishes a complete
staged installation atomically. Incomplete setup can be retried; unowned folders
are preserved. Do not remove/change cached toolchains during a build.

Each invocation saves fresh logs, probe attempts and a JSON result under
`build/portable/reports/`. Failure is recorded instead of relabeling an old
binary as a successful new build. Cached installation checks verify ownership
and required compiler wrappers; they are not a full integrity scan of every
installed file. A broken/modified compiler can therefore require moving its
cache aside and re-extracting from the pinned archive. Native Windows process-tree
cancellation remains unverified. `make test-build-setup` runs the small synthetic
setup/recipe tests without downloading toolchains or building real engines.

## Current evidence — October 24, 2026

The [Phase 4E.1 report](reports/2026-10-24-phase4e1.md) and
[Phase 4E.2 follow-up](reports/2026-10-24-phase4e2.md) record current builds and
foreign execution. These labels cover the bounded checks in
that report, not an entire platform's release acceptance.

| Target | Compiler used | Current evidence |
| --- | --- | --- |
| macOS ARM64 | Apple Clang 21.0.0 | `native-tested`: eight portable runtime checks |
| Linux ARM64 | GCC 15.2.0 cross-compiler | `VM-tested`: eight checks in ARM64 Docker Linux VM; separate Syzygy suites passed |
| Linux x86-64 | GCC 15.2.0 cross-compiler | `emulator-tested`: eight checks through Docker x86-64 emulation on ARM64; separate Syzygy suites passed |
| Windows x86-64 | MinGW GCC 16.2.0 | `compatibility-tested`: eight checks and separate Syzygy suites through Wine 10 in emulated x86-64 Linux; no native Windows execution |
| Linux RISC-V64 | Debian GCC 14.2.0 cross-compiler | `emulator-tested`: eight checks through QEMU 10.0.13; separate Syzygy suites passed |
| Windows ARM64 | LLVM-MinGW 20261020 / Clang 23.1.4 | `cross-build-only`: engine and seven tests linked; Wine ARM64 could not complete bootstrap |

Linux execution used Docker Engine 29.8.2 / LinuxKit 7.0.14, a pinned
`python:3.13-slim-trixie` image, Python 3.13.17 and Debian glibc 2.41. Each test
container was limited to two CPUs and 2 GiB. Image digests, exact commands,
compiler flags and artifact hashes are in the report and local evidence.
Different distributions/standard libraries and native x86-64 hardware remain
separate validation targets. No native-speed comparison was made.

## Evidence recorded on 2026-10-13

The cross-build host was macOS ARM64. All three available foreign-target builds
completed compilation and linking with `CPU=generic MODE=release`, using at most
two concurrent compiler jobs. Their binary formats were inspected; **none of the
foreign executables was run**, either natively or under emulation.

| Target | Observed or intended toolchain | Runtime validation route | Current evidence |
| --- | --- | --- | --- |
| macOS ARM64 | Apple Clang 21.0.0 + Apple SDK/libc++ observed | ARM64 macOS host | `native-tested`: full normal and ASan/UBSan suites; see [validation](VALIDATION.md) |
| Linux x86-64 | GCC 15.2.0, `x86_64-unknown-linux-gnu` | ThinkPad Linux or VM | `cross-build-only`: ELF64 LSB x86-64 |
| Linux ARM64 | GCC 15.2.0, `aarch64-unknown-linux-gnu` | ARM64 Linux VM | `cross-build-only`: ELF64 LSB AArch64 |
| Linux RISC-V64 | GCC/Clang + RV64 Linux sysroot intended | QEMU initially | `unavailable`: no configured local target toolchain or emulator; not built or run |
| Windows x86-64 | MinGW GCC 16.2.0, `x86_64-w64-mingw32`, UCRT | ThinkPad Windows if installed | `cross-build-only`: PE32+ x86-64 console executable |
| Windows ARM64 | LLVM-MinGW UCRT intended | ARM64 Windows machine/guest needed | `unavailable`: no configured local target toolchain or runtime; not built or run |

The inventory does not establish the ThinkPad's installed OS. The existence of
a compiler or a successful cross-build does not establish runtime correctness.
Use `native-tested`, `VM-tested`, `emulator-tested`, `compatibility-tested`, `cross-build-only`, or
`unavailable` evidence labels with exact versions and commands.

On October 14, the Phase 2 diagnostics and hard-deadline forecast revision
rebuilt and linked successfully for Linux ARM64, Linux x86-64, and Windows
x86-64 with these same toolchains and commands. File inspection again identified
the intended ELF64/PE32+ architectures. No foreign executable was run; their
status remains `cross-build-only`. Native ARM64 normal, scalar, and sanitizer
suites passed. RISC-V64 and Windows ARM64 remain unverified.

Later on October 14, the Phase 2C guarded-LMR revision also compiled and linked
for all three available foreign targets with the same commands below. Binary
format inspection confirmed the expected architectures; no foreign execution
was performed. Native ARM64, scalar, and ASan/UBSan checks passed with reductions
both disabled and enabled.

The later capture-ordering revision also built and linked for these three
foreign targets on October 14; file inspection again confirmed AArch64 ELF64,
x86-64 ELF64, and Windows x86-64 PE32+. They were not executed. Native ARM64,
scalar, and sanitizer suites passed with the new option disabled and enabled.
No RISC-V64 or Windows ARM64 toolchain/runtime evidence was added.

The successful commands on this host were:

```sh
make -j2 TARGET=linux-arm64 CXX=/opt/homebrew/bin/aarch64-linux-gnu-g++
make -j2 TARGET=linux-x86_64 CXX=/opt/homebrew/bin/x86_64-linux-gnu-g++
make -j2 TARGET=windows-x86_64 CXX=/opt/homebrew/bin/x86_64-w64-mingw32-g++
```

These paths describe the observed Homebrew installations. On another machine,
provide the corresponding installed compiler path; `TARGET` alone does not
install or select a complete cross-toolchain. Source and header dependency
changes rebuild affected objects. A content-compared configuration stamp also
checks compiler identity, compile/link flags, sysroot flags, and relevant
environment settings before reusing outputs. Changing compile or link flags was
verified to rebuild the Linux ARM64 outputs; an unchanged configuration preserved
them, and a missing compiler failed instead of silently reusing the old binary.

## Runtime dependencies and distribution

The observed Windows x86-64 build uses static compiler/runtime linking. Its PE
imports were inspected: `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, and
`libwinpthread-1.dll` are absent. Windows system libraries, including Kernel32
and the Universal C Runtime, remain required. The NNUE file remains an external
asset; it must be downloaded or supplied separately. Static linking success does
not establish native Windows runtime correctness.

The Linux builds remain dynamically linked. ARM64 requests
`/lib/ld-linux-aarch64.so.1`; x86-64 requests
`/lib64/ld-linux-x86-64.so.2`. Both import `libstdc++.so.6`, `libgcc_s.so.1`,
`libpthread.so.0`, `libm.so.6`, and `libc.so.6`. Their inspected version
requirements include `GLIBCXX_3.4.32` and `CXXABI_1.3.11`; an older installed
libstdc++ may therefore prevent startup even if the CPU and kernel are suitable.
Do not treat a successful cross-build as a distribution-independent Linux
package. Native execution and runtime packaging remain release gates.

## Cross-compilation prerequisites

Cross-compilation requires target headers, standard libraries, linker, and SDK
where applicable, not just an architecture flag. The supported macOS release
build route requires macOS and Apple's SDK (Command Line Tools are sufficient
for command-line programs). Linux/Windows-to-macOS is not a promised supported
route. LLVM-MinGW offers Windows ARM64 and x86-64 targeting from supported macOS,
Linux and Windows hosts; the pinned macOS universal distribution was used here. Do not mix incompatible C++
toolchains' object files or libraries.

Provide a generic CPU baseline before optimized variants. Native optimization
flags describe the build machine and must never be silently used for portable
release binaries or cross-builds. Emulation is useful for correctness; its speed
is not evidence of native engine performance.

## RISC-V64 and Windows ARM64 prerequisites

The commands below document the explicit toolchains used for earlier validation.
The [automatic frontend](#automatic-target-setup) can now select installed Linux
compilers and provision the pinned Windows bundle; Linux package installation
remains an explicit prerequisite. Nothing changes system Python or the engine's
runtime dependencies.

### Linux RISC-V64

On Debian trixie ARM64 (including a local Linux VM/container), install the
cross-toolchain and user-mode emulator, then use the existing Make interface:

```sh
apt-get update
apt-get install --no-install-recommends make g++-14-riscv64-linux-gnu libc6-dev-riscv64-cross qemu-user
make -j2 TARGET=linux-riscv64 CXX=riscv64-linux-gnu-g++-14 runtime-binaries
python3 tools/verify_runtime.py \
  --build build/linux-riscv64-generic-release --target linux-riscv64 \
  --network networks/nn-1a298aa575a0.nnue --execution emulator \
  --runner-json '["qemu-riscv64", "-L", "/usr/riscv64-linux-gnu"]' \
  --output results/riscv64-runtime
```

Package installation requires administrator rights **in that Debian environment**.
The observed compiler is GCC 14.2.0 (`14.2.0-19cross1`), with RV64GC/LP64D
and no vector extension; QEMU is `10.0.13`. The cross-compiler already has its
target library search paths: `/usr/riscv64-linux-gnu` above is QEMU's loader
prefix, not an instruction to override Make's `SYSROOT`. The engine linked
without adding `-latomic`. Emulated results do not prove native speed or
hardware memory-model/race behavior. See the [Debian compiler package](https://packages.debian.org/trixie/g%2B%2B-14-riscv64-linux-gnu)
and [QEMU user-mode documentation](https://www.qemu.org/docs/master/user/main.html).

### Windows ARM64 from macOS

Download the official [LLVM-MinGW 20261020 release](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261020)
archive `llvm-mingw-20261020-ucrt-macos-universal.tar.xz`. Verify its SHA-256:
`e9c13e4ede38e715003ffc674d4d00a1088df8235439d1f0c16188ff0704c17e`
(124,415,944 bytes), then extract it into the ignored `build/toolchains/` folder.
This compiler/toolchain stays outside Git. Its observed Clang version is 23.1.4.

```sh
make -j2 TARGET=windows-arm64 \
  CXX=build/toolchains/llvm-mingw-20261020-ucrt-macos-universal/bin/aarch64-w64-mingw32-clang++ \
  runtime-binaries
```

Use a relative compiler path as shown if the checkout path contains spaces.
Do not mix GCC and LLVM-MinGW object files/libraries; the build configuration
stamp rebuilds outputs when the selected compiler changes. The resulting
`build/windows-arm64-generic-release/chess0live.exe` imports Windows OS/UCRT
libraries, with compiler C++/unwind libraries linked statically. It compiled
and linked here; it has **not** passed execution on native Windows or Wine.
The bounded Wine ARM64 attempt stalled during prefix bootstrap, before the
position test ran. No engine failure or successful execution is inferred.

### Wine execution evidence

A Windows-compatible API layer is a separate route from a Windows OS. The
verifier accepts `--execution compatibility` for Windows targets and requires
an explicit runner, for example `--runner-json '["/usr/lib/wine/wine64"]'` inside
a Linux environment with a matching Wine architecture. It retains all PE
architecture, network, suite and UCI checks. Choose an isolated `WINEPREFIX`;
keep Wine's daemon cleanup separate from ordinary process-group cleanup.
The network and binary paths must be visible to Wine (the tested `/workspace`
paths resolved through its Z: drive); no arbitrary path remapping is performed.
Native/VM labels still require the actual matching host OS/architecture.

Wine 10 x86-64 passed the eight checks inside Docker's emulated x86-64 Linux
environment. This nested compatibility/emulation result is not native Windows
execution, GUI verification, distribution certification, or a speed benchmark.
Wine ARM64 did not complete environment startup. See the [Debian Wine package](https://packages.debian.org/trixie/wine64)
and the [checkpoint report](reports/2026-10-24-phase4e2.md) for exact evidence.

## Run the portable checks

Build the engine and seven standalone correctness executables without executing
anything on the build host:

```sh
make -j2 runtime-binaries
make -j2 TARGET=linux-arm64 CXX=aarch64-linux-gnu-g++ runtime-binaries
```

For a cross-build, copy the checkout and that target's build directory to the
target machine, retaining `toolchain.ok`. Supply the separately downloaded
network. Python 3.9+ is required by the verifier; the engine itself does not need
Python. No compiler or third-party Python package is needed to run the checks.
On the matching native target, `make verify-runtime` builds and runs them. To
run an existing build directly inside an ARM64 Linux VM, for example:

```sh
python3 tools/verify_runtime.py \
  --build build/linux-arm64-generic-release --target linux-arm64 \
  --network networks/nn-1a298aa575a0.nnue --execution VM \
  --output results/linux-arm64-runtime
```

Use a **new** output directory. The verifier checks the pinned network digest,
compiler configuration and executable architecture, then runs the existing
position, NNUE, update-arithmetic, dense-arithmetic, search, selective-policy,
and time-management suites sequentially. A final UCI session checks startup,
network loading, start-position perft, a bounded depth search, two-worker
activity/accounting, readiness while searching, stop, and clean exit. It uses
Hash 16 MiB and two search workers. Its default limit is 180 seconds per suite
or complete UCI session; `--timeout` changes that limit. This timeout is a
failure guard, not a performance benchmark. There is no automatic repeat,
download, schedule, or match.

The report records binary/network hashes, raw compiler configuration, host,
actual argument lists, completed checks and failure details. It does not treat
a configuration stamp as proof of a source revision. Keep the source commit,
build logs and runtime/SDK versions with a distributed build. The seven C++
suites retain assertions even in release builds. Test links honor `LDLIBS`,
like the engine link, for target-specific runtime libraries.

Choose `--execution native`, `VM`, `emulator`, or `compatibility` honestly:
VM/emulator/compatibility labels are operator declarations. Native and VM checks require the verifier's host OS
and architecture to match the target. For a synchronous emulator/launcher, use
`--execution emulator --runner-json '["qemu-riscv64", "-L", "/target/sysroot"]'`
with the corresponding RISC-V build. This example requires an installed emulator
and suitable Linux host/sysroot; it does not imply they are available on macOS.
Compatibility mode likewise requires a runner and accepts Windows targets only.
The prefix is an argument array, never a shell command; all binary and network
paths must also be accessible to the runner. The runner must propagate exit
codes, stay attached, and clean up its children when stopped. Remote detached
jobs are not supported. VM/emulation speed says nothing about native throughput.

These checks include twelve pinned NNUE raw/wrapped golden positions and
incremental/full-refresh agreement. They **do not rerun** the full external
Stockfish integer-stage oracle, validate all Syzygy table sizes, replace the
complete SMP/sanitizer suites, or satisfy every release gate. Missing test
binaries, a wrong target/network, nonzero exit, missing completion marker,
explicit skipped checks, timeouts, or changed inputs produce failure evidence.

## Primary references

- [Clang language support](https://clang.llvm.org/cxx_status.html)
- [GCC language support](https://gcc.gnu.org/projects/cxx-status.html)
- [libc++ C++26 support](https://libcxx.llvm.org/Status/Cxx26.html)
- [Clang cross-compilation](https://clang.llvm.org/docs/CrossCompilation.html)
- [LLVM-MinGW](https://github.com/mstorsjo/llvm-mingw)
- [Apple Command Line Tools](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools/)
- [QEMU user-mode limits](https://www.qemu.org/docs/master/user/main.html)
