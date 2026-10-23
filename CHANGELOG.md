# Changelog

All notable changes to the TASK code are recorded here. This file
starts with Phase L (library-ization) of TASK/TR; earlier history is
in `git log` and `HISTORY`.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **MCP server `fp_mcp`: a `set_param_str` tool** (#231) sets `KNAMEQ`,
  the equilibrium file that `MODELG=3` loads, so an EQ to FP handoff (an
  equilibrium written by `eq_mcp`'s `save` tool) can be driven through
  MCP; `set_params` passes a `str` value to it. It calls
  `fplib.Fplib.set_param_str`, which needs a `libfpapi.so` that exports
  `fp_set_param_str`. A successful call zeroes the state's `scalars` until
  the next run, as a numeric set does. `tot_mcp`'s `describe_parameters`
  marks `fp:KNAMEQ` as settable through `run_pipeline` only, since tot's
  `set_param` passes string values on for `eq:` and `tr:` only.
- **FP library: `fp_get_state` returns seven global scalars** after the
  profile arrays: `TOTAL_IP` [MA], `STORED_ENERGY` [MJ], `COLLISION_POWER`,
  `ABSORPTION_POWER`, `ABSORPTION_WR`, `ABSORPTION_WM` [MW] (species sums at
  the latest `NTG1` sample, what FP otherwise only writes to unit 6) and
  `PLASMA_VOLUME` [m^3]. They are what shows an EQ to FP handoff: the six
  profiles are local quantities and stay bit-identical when only the
  equilibrium changes (without radial transport, waves or current drive).
  `fp_state_t` grows by 56 bytes at its end (layout version 2, #246), so
  `libfpapi.so` and its callers are rebuilt together: `fplib` refuses a
  library built before this change with `FplibAbiError` instead of reading
  the scalars as zeros. `FpState.scalars`, `to_dict()["scalars"]`
  and the `scalars` object of fp_mcp's state carry them, and an FP step of
  the `totlib` pipeline keeps them beside `timefp` and its counts. They are
  zero until the first run, and again after any successful parameter set
  (`fp_set_param`, `fp_set_param_str`, or tot's `fp:` parameters, which the
  registry counts since #253) until the next run that is made.
- **EQ library: `eq_save`, `Eq.save(path)` and the `save` tool of `eq_mcp`**
  write the equilibrium of the last `eq_run` to a TASK/EQ binary file through
  `EQSAVE`, the file that `MODELG=3` with `KNAMEQ` loads. A save whose file
  was not opened, or is shorter than what was written, is an error, not
  `EQ_OK`. The work is in a new routine, `EQSAVE_IERR(IERR_OUT)`; `EQSAVE`
  keeps its argument-less entry and calls it, so `eq/eqmenu.f90` (the `S`
  command) and `tr/f77/trfile.f` are unchanged. `IERR_OUT` is `FWOPEN`'s
  failure (a directory that is missing or not writable, `MODEFW=3` and an
  existing file), or 9 when the file was opened and a `WRITE` or the `CLOSE`
  reported an error (an existing file without write permission, which used
  to end the program at the first `WRITE`) or the file is shorter than what
  was written to the unit. The comparison of the two lengths is there
  because a write the system refuses is not always reported: measured with
  gfortran 15 on macOS, a save to a new file under a file size limit
  returned success over a short file, no `WRITE` and not the `CLOSE` having
  reported it. What is then at the path is left in place and must not be
  loaded. `eq_save` returns
  `EQ_ERR_CALC_FAILED` for those, and `EQ_ERR_INVALID`, touching no file,
  when the fields do not hold the equilibrium of the present parameters (no
  successful `eq_run` yet, a later solve or load that failed, or
  `eq_set_param` of anything but `MODEFR` and `MODEFW` since), for a blank
  `KNAMEQ`, and for `MODEFW` other than 0 or 3 (with 1, 2 and 4 to 7
  `FWOPEN` can read unit 5). The `save` tool replaces an existing file only
  with `overwrite=true`: when it saves it sets `MODEFW` itself (3, or 0). In
  the same change, `eq_run(1)` reports a load that failed: `EQ_READ` called
  `EQCALQ` after `EQDSKR` had failed (`MODELG=5`, a missing file) and
  returned `EQCALQ`'s code, and left `IERR` unassigned for a `MODELG` that
  is no file format; it now starts from `IERR=0`, calls `EQCALQ` only after
  a successful `EQDSKR`, and returns 1 for an unknown `MODELG`.
- **CI: `clean-tree-build` workflow (#250).** Runs the wrapper READMEs'
  fresh-checkout sequence (per-system files, `make -C ../bpsd libbpsd.a`,
  one `make -C <mod> lib<mod>api.so`) for tr / fp / ti / wr / wrx / eq, one
  module per runner with nothing pre-built, and checks that the `.so`
  exists and loads with `RTLD_NOW` (`ctypes.CDLL`). Triggered by changes to
  Makefiles, `make.header.org`, Fortran sources and includes, `mtxp/`, the
  workflow file and the action; by hand (on the ref chosen in the dispatch)
  and weekly on `develop` once the workflow file reaches `master` (a
  dispatch or schedule needs the file on the default branch, which
  carries no workflow files yet). The pytest and mono-build
  jobs pre-build the whole PIC chain first, which is why #230 regressed
  unnoticed. The `make.header` heredoc and the `mtxp/make.mtxp` copy that
  those two jobs carried as KEEP-IN-SYNC steps are now the composite action
  `.github/actions/provision-build-env`, shared by all three.
- **C ABI: every library reports its state-struct layout, and the Python
  wrappers refuse a mismatch (#246).** `X_state_abi_version()` returns
  `X_STATE_ABI_VERSION` (now a `PARAMETER` in `X_state.f90`, mirrored by
  the `#define` in `X_api.h`; tr and tot stay at 2, eq / fp / ti / wr / wrx
  start at 1) and `X_state_size()` the `sizeof` of the `BIND(C)` type, both
  callable before `X_init`, for tr / fp / eq / ti / wr / wrx / tot and the
  mono image. The C-ABI drivers (`test_negative.c`, `test_run_so.c`) fail
  when either differs from the header; `python/Xlib/_ffi.py::load_library`
  raises `XlibAbiError` when the library's version or size differs from
  `XStateC`, or when the library exports neither symbol (built before this
  change), naming the fix. CI runs the six per-module dlopen drivers
  (`X_api_check_so`) and `libtotapi_mono_inspect` checks the twelve symbols.
  A library and a wrapper from different commits used to fail silently:
  a longer library struct wrote past the wrapper's allocation, a shorter
  one left the appended fields as plausible zeros. The check protects
  callers from this change on; a caller older than it never asks, and
  `X_get_state` still takes no buffer size.

### Changed

- **tr / fp / ti libraries, `Tot` and `tot_mcp`: a parameter set after a
  run re-preps the module, whoever set it (#253).** `tr_set_param` /
  `fp_set_param` / `ti_set_param` used to clear the module's private
  "prepared" flag themselves; tot's `tr:` / `fp:` / `ti:` dispatcher wrote
  to the registries directly and left the flag standing, so after a run a
  `Tot.set_param("tr:NSMAX", 3)` continued the old state with `tr_prep`
  skipped and the #189 pre-run species check never fired. The registries
  now count every successful set and `tr_run` / `fp_run` / `ti_run`
  re-prep when the count moved since their last prep. Behaviour change for
  `Tot` and `tot_mcp` only: a set after a run now restarts the module
  (`NT` and `T` back to 0), which is what `trlib` / `fplib` / `tilib` and
  `TotPipeline` have always done; a set the registry refused changes
  nothing. `eq` has no prepared flag on `develop`; the same counter is the
  natural precondition for `eq_save` (#256).

- **FP library: `fp_run` refuses `NRMAX` above `FP_MAX_NRMAX` (100).** Such a
  run was made, and `fp_get_state` then returned rc=3: its results could be
  read only from the log on unit 6 or from `fp_regress.dat`
  (`FP_REGRESS_DUMP=1`). `fp_run` now returns `FP_ERR_INVALID` before any
  work.

### Fixed

- **MCP servers: the `mcp` dependency is pinned to `>=1.2,<2`** in the
  seven server `pyproject.toml` files, the CI workflow, the servers' own
  "not installed" message, the READMEs, the Sphinx MCP pages, the
  trlib presentation and its builder, and the 2026-04-18 MCP plan.
  `mcp.server.fastmcp` exists from mcp 1.2.0 (the old floor, 0.9, let
  1.0 and 1.1 in, where the import fails the same way) and mcp 2.0
  removed it, so an unpinned install (`pip install -e
  python/mcp-servers/eq_mcp` on a fresh environment, or the workflow's
  bare `pip install mcp`, which took mcp 2.3.0) left every server with
  `MCP_AVAILABLE = False`: `python -m <mod>_mcp.server` exited 2 and the
  seven `TestBuildServer` classes skipped, so CI was green without
  exercising a single FastMCP construction. The workflow now asserts
  `MCP_AVAILABLE` right after the install, so that skip is a failure
  there. Porting the servers to the 2.x API is separate work. Fix by
  Li Hengyu, cherry-picked from #226.
- **FP library: `fp_run` refuses the counts the solver cannot run with**,
  before any work, with `FP_ERR_INVALID` and one `XX fp_run: ...` line per
  violation on unit 6 (`fp_param_check` in `fp/fp_param_registry.f90`).
  They were accepted when set and then ran past an array bound (an abort
  when built with run-time checks), ended the host process, or never
  returned: `NRMAX` below 1; `NPMAX` or `NTHMAX` below 2; `LMAXFP` below 0
  or at the largest integer (the iteration's exit, `N_IMPL = 1 + LMAXFP`,
  overflows and a step never ends); `NSAMAX` above `NSBMAX`; an evolved
  species number outside 1 to `MIN(NSMAX, NSBMAX)`; a background species
  number outside 1 to `NSMAX`.
- **MCP servers `eq_mcp`, `tr_mcp`, `tot_mcp`: Fortran output no longer
  reaches the JSON-RPC pipe.** A stdio server's fd 1 is the pipe to its
  client, and the library's `WRITE(6,...)` went into it: in one stdio
  session (`initialize`, `init`, `run`) 9 of the 12 stdout lines of
  `tr_mcp` and of `tot_mcp` were not JSON-RPC, and 2 of 5 of `eq_mcp` with
  `run(mode=1)`. `main()` now calls `_fd_isolation.install()` (one module
  shared by the three servers, `python/_fd_isolation.py`, with one flag for
  the process) immediately before the stdio server is built: fd 1 is
  redirected to stderr and `sys.stdout` keeps the pipe. Importing a server
  module leaves fd 1 and `sys.stdout` of the importing process alone (#227
  item 1); `--help` and `--print-tools` print to the terminal as before.
  Two descriptor layouts in which the redirect alone does nothing are
  handled: with fd 2 closed it is opened on the null device first (and
  `sys.stderr` given it), and when stdout and stderr are the same file (the
  host merged them, `2>&1`) fd 1 goes to the null device and one line on
  stderr says that what is written to fd 1 is discarded. A terminal on
  both counts as the same file too: a server started by hand in a
  terminal shows that line and no longer the library's output. Where
  `fstat` gives a descriptor no identity (Windows for a pipe or a console)
  the merged layout is not recognised and fd 1 goes to stderr as usual.
- **tot docs and `tot_mcp`: string parameters and the tool count** (#274).
  The tot Sphinx pages showed `tot.set_param_str("fp:KNAMEQ", ...)` and
  `("wr:KNAMEQ", ...)`, which tot refuses: it passes string values on for
  `eq:` and `tr:` only. They now use `eq:` and `tr:`, and say that
  `fp:KNAMEQ` goes through `totlib.TotPipeline.set_param` (`tot_mcp`'s
  `run_pipeline` `params`), that `ti`, `wr` and `wrx` take no strings, and
  that `eq:KNAMEQ` is `pl`'s, which fp reads too (one variable in the mono
  image). `tot_mcp` registers 10 tools, not 9 (`__init__.py`, the Sphinx MCP
  pages, now with a `run_pipeline` row); its README says where `fp:KNAMEQ`
  goes. `tot_mcp`'s hints: a refused string set no longer gets the hint to
  namespace its name but one that names the string parameters (the seven
  `eq:` file names, `tr:KNAMEQ`) and says to send numbers as numbers; a
  refused numeric set of a namespaced name points at `describe_parameters`;
  a string totlib rejects itself (too long, not ASCII) and a refused
  `tot_run` argument get no hint. The `tot_mcp` server instructions,
  docstrings and README, `totlib`'s errors, README and examples, and
  `docs/tot-library/architecture.md` no longer say that `run` and
  `get_state` are stubs until L-6 (#96, #124), nor that `tot_mcp` has a
  `set_param_str`; `architecture.md`'s quirks and limitations follow the
  code (eq in the fan-out, one live `Tot()` per process).
- **MCP servers `ti_mcp`, `wr_mcp`, `wrx_mcp`: the same fd isolation** (#262).
  The three servers had the layout of the other three and the same exposure:
  `main()` now calls `_fd_isolation.install()` immediately before the stdio
  server is built, importing a server module leaves the importing process's
  fd 1 and `sys.stdout` alone, and `--help` / `--print-tools` / the
  missing-SDK path return before anything is redirected. Each server's
  `tests/test_fd_isolation.py` runs the shared checks
  (`python/mcp-servers/fd_isolation_cases.py`), and
  `python/tests/test_fd_isolation.py` checks that all six servers run every
  one of them. `fp_mcp` follows in #232.
- **MCP server `fp_mcp`: the same fd isolation** (#232). `fp_mcp` had the
  most of it: `FPWRTPRF` writes the radial profile table to unit 6 once at
  preparation and then every `NTG2STEP` steps (every step by default), so
  the lines that are not JSON-RPC grew with `NTMAX`: in one stdio session
  (`initialize`, `init`, `run`, library defaults) 63 of the 66 stdout lines
  at `NTMAX=1`, 83 of 86 at `NTMAX=2`. `main()` now calls `_fd_isolation.install()`
  immediately before the stdio server is built, as the other six servers
  do; its `tests/test_fd_isolation.py` runs the shared checks, and
  `python/tests/test_fd_isolation.py` checks all seven servers.
- **EQ library: `eq_save` also refuses after a set of tot's `eq:` parameters**
  (as #253 did for tr, fp and ti). tot's `eq:` dispatcher calls
  `eq_param_registry` directly, so the flag that `eq_set_param` cleared stayed
  set and `eq_save` wrote the parameters as they stood over fields computed
  for the old ones. The registry now counts every successful numeric set
  (`eq_param_generation()`) except `MODEFR` and `MODEFW`; `eq_run` records
  the count when it computes or loads the equilibrium, and `eq_save` refuses
  when it moved. String sets (`KNAMEQ` and the other `KNAM*`) are not counted,
  as before. What no registry sees in the mono image (another module's
  `eq_init`, `eq_load`, `eq_calc`, a `plcomm` variable set through another
  module's registry) is #260; `eq_api.h` and the eqlib README say so. Smaller
  points from the review of #256: the eq_mcp `save` tool says that the
  `MODEFW` it sets stays; a sentence in `eq/eqfile.f90` (comment only) that
  the length comparison depends on the run-time reporting the unit's
  length; `test_save.py` accepts a short file of at most the limit;
  `_encode_name` says 80 bytes for a value.
- **MCP stdio servers: two edge cases of the fd isolation** (from the review
  of #257). `python/_fd_isolation.py` repairs fd 2 only when `fstat` says
  `EBADF`; another error means fd 2 is there, so it is left alone and the
  installation fails before changing anything. A host's `sys.stdout` whose
  `flush` raises an `Exception` no longer stops the installation.

## TR Phase L — library-ization (2026-04-18)

Phase L turned TASK/TR from a CLI-only Fortran program into an
additionally-loadable shared library with a Python wrapper. The `tr2`
binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #2)** — Phase 0 regression-test infrastructure:
  `test_run/baselines/tr_{iter01,m0904,tst2}.json`,
  `tools/extract_tr_metrics.py`, `tools/compare_metrics.py`.
- **L-1 (2026-04-18, PR #21)** — `tr/Makefile` graphics split; `tr2`
  still links graphics, `libtrapi.so` builds are graphics-free.
- **L-2 (2026-04-18, PR #27)** — C ABI foundation: `tr/tr_api.h`,
  `tr/tr_api.f90`, `tr/tr_state.f90`; 5 entry-point stubs exported
  from `libtrapi` returning `TR_ERR_NOT_IMPL` (ierr=4).
- **L-3 (2026-04-18, PR #33)** — Parameter registry
  (`tr/tr_param_registry.f90`, ~38 `SELECT CASE` entries) and real
  bodies for `tr_init` / `tr_run` / `tr_get_state` / `tr_finalize`.
  `tr_set_param` accepts `"NAME"` and `"NAME[idx]"` (1-origin).
- **L-4 (2026-04-18, PR #35)** — `make -C tr libtrapi.so` builds the
  shared library. PIC variants (`*_pic.a`) of `lib`, `pl`, `eq`, `ob`,
  `mtxp`, `bpsd` added to participating Makefiles. Non-PIC archives
  and `tr2` are unchanged.
- **L-5 (2026-04-18, PR #44)** — Python wrapper `python/trlib/`:
  `Trlib` context manager, `TrState` dataclass, exception hierarchy
  mirroring `enum tr_error`, `_ffi` ctypes layer with `TRLIB_PATH`
  override and `RTLD_LAZY` loading.
- **L-6 (2026-04-18, PR #53)** — 4-layer test suite wired into
  `test_run/test_definitions.conf`:
  `trlib_equivalence` (Layer 1 vs Phase 0 baselines, tol `1e-10`),
  `trlib_c_abi` (Layer 2 `make -C tr tr_api_check_all`),
  `trlib_ffi` + `trlib_wrapper` (Layer 3 Python),
  `trlib_sweep` (Layer 4 3×3 RR×BB smoke).
- **L-7 (2026-04-18, this PR)** — User-facing documentation:
  rewritten `python/trlib/README.md`, example scripts
  (`quickstart.py`, `parameter_sweep.py`, `state_dump.py`),
  architecture doc (`docs/tr-library/architecture.md`), and this
  changelog.

### Known issues

- `tr_m0904` Layer 1 comparison drifts from its Phase 0 baseline by
  `~1e-8` under current `tr2`; it is pinned to the baseline rather
  than regenerated. `tr_iter01` and `tr_tst2` match to `1e-10`.
- String parameters (`KNAMEQ`, `KNAMTR`, etc.) are not yet wired
  through `tr_set_param` (design spec §4.3 deferral).
- Single instance per process only — TR globals are COMMON-block
  state.

## TI Phase L — library-ization (2026-04-18)

Phase L mirrors the TR library-ization for the TASK/TI impurity-
transport module: the same 5 C ABI functions, the same wrapper
architecture, parameter registry, and 4-layer test structure. The
`ti` CLI binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #12)** — Phase 0 regression-test
  infrastructure for TI: `test_run/baselines/ti_{min,ar,w}/`,
  `tools/extract_ti_metrics.py`, `test_run/inputs/ti_*.in`.
- **L-1 (2026-04-18, PR #22)** — `ti/Makefile` split into
  CORE / GRAPHICS / MENU `SRCS` groups so graphics-free Fortran
  compilations can be staged without touching the `ti` binary
  build.
- **L-2 (2026-04-18, PR #28)** — C ABI foundation: `ti/ti_api.h`,
  `ti/ti_api.f90`, `ti/ti_state.f90`; 5 entry-point stubs returning
  `TI_ERR_NOT_IMPL` (ierr=4), plus `ti_api_check` target and first
  C-side smoke tests under `ti/tests/c_abi/`.
- **L-3 (2026-04-18, PR #34)** — Parameter registry
  (`ti/ti_param_registry.f90`, ~35 `SELECT CASE` entries covering
  scalars, 1-D arrays, and 2-D `[i,j]` subscripts) plus real bodies
  for `ti_init` / `ti_run` / `ti_get_state` / `ti_finalize`.
  `ti_set_param` accepts `"NAME"`, `"NAME[i]"`, and `"NAME[i,j]"`
  (1-origin). PA/PM naming deliberately exposes only `PA` (the
  PLCOMM true name).
- **L-4 (2026-04-18, PR #41)** — `make -C ti libtiapi.so` builds
  the shared library. PIC variants (`*_pic.a`) of `lib`, `pl`,
  `eq`, `adpost`, `open-adas/adf11`, `mtxp`, `bpsd` added to
  participating Makefiles. Non-PIC archives and the `ti` binary are
  unchanged. (Target is staged on feature branch; see Known issues.)
- **L-5 (2026-04-18, PR #47)** — Python wrapper `python/tilib/`:
  `TiLib` / `Tilib` context manager, `TiState` dataclass,
  exception hierarchy mirroring `enum ti_error`, `_ffi` ctypes
  layer with `TILIB_PATH` override and `RTLD_LAZY` loading.
- **L-6 (2026-04-18, PR #57)** — 4-layer test suite wired into
  `test_run/test_definitions.conf` (`tilib_equivalence` Layer 1
  vs Phase 0 baselines at tol `1e-10`, `tilib_c_abi` Layer 2
  `make -C ti ti_api_check_all`, `tilib_ffi` + `tilib_wrapper`
  Layer 3 Python, `tilib_sweep` Layer 4 3×3 DT×NRMAX smoke) plus
  Ar fixture applying atomic mass via `PA[3]` instead of the dead
  `PM` alias.
- **L-7 (2026-04-18, this PR)** — User-facing documentation:
  rewritten `python/tilib/README.md`, example scripts
  (`quickstart.py`, `parameter_sweep.py`, `state_dump.py`),
  architecture doc (`docs/ti-library/architecture.md`), and this
  changelog entry.

### Known issues

- `libtiapi.so` Makefile target has not yet merged into `develop`;
  it lives on `feature/ti-library-L4-shared-lib` and is pending a
  follow-up PR. The wrapper, examples, and tests all tolerate a
  missing library by skipping FFI-level checks.
- `ti_ar` baseline shows small drift similar in character to
  `tr_m0904`; when regeneration is needed pin the baseline rather
  than re-running against a moving `ti` output.
- String parameters (`KID_NS`, ...) are not wired through
  `ti_set_param`. Argon fixtures work around this by setting
  `NPA[3]=18` and letting `tiinit.f90` recompute the label.
- Per-species diffusion knobs `DN0`, `DT0`, `DR0`, `DRS`,
  `DN0_NS[i]` are not yet in the registry.
- Single instance per process only — TI globals are COMMON-block
  state.

## FP Phase L — library-ization (2026-04-18)

Phase L mirrors the TR library-ization for the TASK/FP Fokker-Planck
module: the same 5 C ABI functions, the same wrapper architecture,
parameter registry, and 4-layer test structure. The `fp` CLI binary
and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #13)** — Phase 0 regression-test
  infrastructure for FP: `test_run/baselines/fp_{iter01,jt60,dt1}/`,
  `fpregress.f90` (env-guarded high-precision dump),
  `test_run/scripts/extract_fp_metrics.py`, and the three baseline
  test cases `fp_iter01`, `fp_jt60`, `fp_dt1` wired into
  `test_definitions.conf`.
- **L-1 (2026-04-18, PR #26)** — `fp/Makefile` split into
  CORE / GRAPHICS / MENU `SRCS` groups so graphics-free Fortran
  compilations can be staged without touching the `fp` binary
  build.
- **L-2 (2026-04-18, PR #29)** — C ABI foundation: `fp/fp_api.h`,
  `fp/fp_api.f90`, `fp/fp_state.f90`; 5 entry-point stubs returning
  `FP_ERR_NOT_IMPL` (ierr=4), plus first C-side compile-only smoke
  tests under `fp/tests/c_abi/`.
- **L-3 (2026-04-18, PR #37)** — Parameter registry
  (`fp/fp_param_registry.f90`) and real bodies for
  `fp_init` / `fp_run` / `fp_get_state` / `fp_finalize`.
- **L-4 (2026-04-18, PR #43)** — `make -C fp libfpapi.so` builds the
  shared library.
- **L-5 (2026-04-18, PR #55)** — Python wrapper `python/fplib/`.
- **L-6 (2026-04-18, PR #56)** — 4-layer test suite wired into
  `test_run/test_definitions.conf`.
- **L-7 (2026-04-18, PR #68)** — User-facing documentation:
  rewritten `python/fplib/README.md`, example scripts,
  architecture doc (`docs/fp-library/architecture.md`).

## WR Phase L — library-ization (2026-04-18)

Phase L mirrors the TR library-ization for the TASK/WR ray-tracing
module. The `wr` CLI binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #15)** — Phase 0 regression-test
  infrastructure for WR.
- **L-1 (2026-04-18, PR #24)** — `wr/Makefile` SRCS split.
- **L-2 (2026-04-18, PR #30)** — C ABI foundation: `wr/wr_api.h`,
  `wr/wr_api.f90`.
- **L-3 (2026-04-18, PR #36)** — Parameter registry and real
  bodies. Includes the Bugbot HIGH fix (double-free on
  finalize-then-reinit): `wr_allocate` SAVE flags moved to module
  scope, `wr_reset_alloc_state` added and called from `wr_finalize`,
  and every `wr_deallocate` guarded with `ALLOCATED()`.
- **L-4 (2026-04-18, PR #42)** — `make -C wr libwrapi.so` builds
  the shared library.
- **L-5 (2026-04-18, PR #46)** — Python wrapper `python/wrlib/`.
- **L-6 (2026-04-18, PR #60)** — 4-layer test suite wired into
  `test_run/test_definitions.conf`.
- **L-7 (2026-04-18, this PR)** — User-facing documentation:
  rewritten `python/wrlib/README.md`, example scripts
  (`quickstart.py`, `parameter_sweep.py`, `state_dump.py`),
  architecture doc (`docs/wr-library/architecture.md`), and this
  changelog entry.

### Known issues

**FP:**
- `fp_finalize` does not deallocate FPCOMM arrays (asymmetry between
  `fp_allocate` and `fp_deallocate`); long-running drivers can leak
  allocations.
- String parameters (`KNAMFP`, ...) are not wired through
  `fp_set_param`.
- Mesh caps `FP_MAX_NRMAX=100` and `FP_MAX_NSAMAX=8` are baked into
  the exported `fp_state_t`.
- Single instance per process only.

**WR:**
- Post-finalize state-reset invariant: `wr_finalize` must call
  `wr_reset_alloc_state` to zero `wr_allocate`'s SAVE flags
  (`INIT`, `NRAYMAX_SAVE`, `NSTPMAX_SAVE`). Do not remove this hook
  (PR #36 Bugbot HIGH).
- Beam tracing (`mode_beam /= 0`) is not exposed through
  `wr_get_state`; only ray-tracing outputs are surfaced.
- Input scalars (`RF`, `RPI`, ...) are not echoed in
  `wr_get_state`.
- String parameters are not wired through `wr_set_param`.
- Single instance per process only.

## WRX Phase L — library-ization (2026-04-18)

Phase L mirrors the WR library-ization for the TASK/WRX extended
ray-tracing module: the same 5 C ABI functions, the same wrapper
architecture, parameter registry, and 4-layer test structure. The
`wrx` CLI binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #16)** — Phase 0 regression-test
  infrastructure for WRX (`wrx_iter01` baseline,
  `tools/extract_wrx_metrics.py`, `test_run/inputs/wrx_iter01.in`).
- **L-1 (2026-04-18, PR #25)** — `wrx/Makefile` SRCS split into
  CORE / GRAPHICS / MENU groups so graphics-free Fortran
  compilations can be staged without touching the `wrx` binary
  build.
- **L-2 (2026-04-18, PR #31)** — C ABI foundation: `wrx/wrx_api.h`,
  `wrx/wrx_api.f90`; 5 entry-point stubs returning
  `WRX_ERR_NOT_IMPL` (ierr=4), plus first C-side smoke tests under
  `wrx/tests/c_abi/`.
- **L-3 (2026-04-18, PR #38)** — Parameter registry
  (`wrx/wrx_param_registry.f90`, ~70 `SELECT CASE` entries covering
  scalars and 1-D arrays) plus real bodies for `wrx_init` /
  `wrx_run` / `wrx_get_state` / `wrx_finalize`. `wrx_set_param`
  accepts `"NAME"` and `"NAME[idx]"` (1-origin).
- **L-4 (2026-04-18, PR #52)** — `make -C wrx libwrxapi.so` builds
  the shared library. PIC variants (`*_pic.a`) of `lib`, `pl`, `eq`,
  `dp`, `mtxp`, `bpsd` added. Non-PIC archives and the `wrx` binary
  are unchanged.
- **L-5 (2026-04-18, PR #59)** — Python wrapper `python/wrxlib/`:
  `Wrxlib` context manager, `WrxState` dataclass, exception
  hierarchy mirroring `enum wrx_error`, `_ffi` ctypes layer with
  `WRXLIB_PATH` override and `RTLD_LAZY` loading.
- **L-6 (2026-04-18, PR #67)** — 4-layer test suite wired into
  `test_run/test_definitions.conf`:
  `wrxlib_c_abi` (Layer 2 `make -C wrx wrx_api_check_all`),
  `wrxlib_ffi` + `wrxlib_wrapper` (Layer 3 Python),
  `wrxlib_equivalence` (Layer 1 vs Phase 0 baselines, tol `1e-10`,
  `WRX_RUN_OK` gated), `wrxlib_sweep` (Layer 4 3×3 RFIN × ANGPIN
  smoke, `WRX_RUN_OK` gated).
- **L-7 (2026-04-19, this PR)** — User-facing documentation:
  rewritten `python/wrxlib/README.md` (with prominent `WRX_RUN_OK`
  gate section), example scripts (`quickstart.py`,
  `parameter_sweep.py`, `state_dump.py` — all `--dry-run` capable),
  architecture doc (`docs/wrx-library/architecture.md`, including a
  dedicated `libgrf::grd1d` limitation analysis with remediation
  roadmap), and this changelog entry.

### Known issues

**WRX:**
- **`wrx_run` may segfault on the shared build** because
  `wrcalpwr.f90` retains an unconditional call to `libgrf::grd1d`
  that the L-1 graphics split deliberately excludes from
  `libwrxapi.so`. `RTLD_LAZY` loading hides the unresolved symbol
  at `dlopen` time; the segfault occurs the first time `wrcalpwr`
  is reached. Mitigation: every `.run()`-dependent test class is
  gated behind `WRX_RUN_OK=1`; the C-side `test_run_so.c` skips
  `wrx_run` likewise. Remediation roadmap (stub `grd1d`,
  conditionalise `wrcalpwr`, or PIC `libgrf_pic.a`) tracked in
  `docs/wrx-library/architecture.md`.
- Beam tracing (`mode_beam /= 0`) is not exposed through
  `wrx_get_state`; only ray-tracing per-species power-deposition
  outputs are surfaced.
- Input scalars (`RFIN`, `RPIN`, ...) are not echoed in
  `wrx_get_state`.
- String parameters are not wired through `wrx_set_param`.
- Single instance per process only — WRX globals are COMMON-block
  state.

## EQ Phase L — library-ization (2026-04-19)

Phase L mirrors the TR library-ization for the TASK/EQ MHD-equilibrium
module. The structure matches the sibling tr/ti/wr/fp libraries with
one EQ-specific addition: a **6th C ABI entry point**
`eq_set_param_str` to set the seven `CHARACTER(LEN=80)` namelist keys
(`KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`,
`KNAMPF`). The `eq` CLI binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #54)** — Phase L-0 regression-test
  infrastructure for EQ: `test_run/baselines/eq_iter01/`,
  `test_run/baselines/eq_tst2/`, `eqregress.f90` (env-guarded
  high-precision dump), `test_run/scripts/extract_eq_metrics.py`,
  and the two baseline test cases `eq_iter01`, `eq_tst2` wired into
  `test_definitions.conf`.
- **L-1 (2026-04-18, PR #65)** — `eq/Makefile` split into
  `SRCS_CORE` / `SRCS_GRAPHICS` / `SRCS_MENU` groups so graphics-free
  Fortran compilations can be staged without touching the `eq`
  binary build.
- **L-2 (2026-04-18, PR #70)** — C ABI foundation: `eq/eq_api.h`,
  `eq/eq_api.f90`, `eq/eq_state.f90`; 5 entry-point stubs returning
  `EQ_ERR_NOT_IMPL` (ierr=4), plus first C-side compile-only smoke
  tests under `eq/tests/c_abi/`.
- **L-3 (2026-04-18, PR #78)** — Parameter registry
  (`eq/eq_param_registry.f90`, 94 `SELECT CASE` entries covering
  ~78 numeric scalars/ints, 5 array families with the 0-origin
  `PSIB[0..5]` and 1-origin `RIPFC/RPFC/ZPFC/WPFC[1..10]`, and 7
  string keys via `eq_set_param_str`) plus real bodies for `eq_init`
  / `eq_run(mode=1)` / `eq_get_state` / `eq_finalize`. The 6th C ABI
  entry `eq_set_param_str` is added here for `CHARACTER(LEN=80)`
  namelist parameters.
- **L-4 (2026-04-18, PR #80)** — `make -C eq libeqapi.so` builds the
  shared library. PIC variants (`*_pic.a`) of `lib`, `pl`, `bpsd`,
  `mtxp` added to participating Makefiles. Non-PIC archives and the
  `eq` binary are unchanged. Includes explicit PIC inter-module
  dependency declarations to prevent parallel-build races.
- **L-5 (2026-04-18, PR #86)** — Python wrapper `python/eqlib/`:
  `Eq` context manager, `EqState` dataclass, exception hierarchy
  mirroring `enum eq_error`, `_ffi` ctypes layer with `EQLIB_PATH`
  override and `RTLD_LAZY` loading. `Eq.run()` defaults to `mode=1`
  so `eq.run()` (no arg) performs the canonical EQDSK load.
- **L-7 (2026-04-19, this PR)** — User-facing documentation:
  rewritten `python/eqlib/README.md` with full 6-fn API table,
  60+ registry parameters, `EqState` field table, exception
  hierarchy, EQ-specific quirks (PSIB 0-origin / `set_param_str`
  for KNAMEQ / `eq.run(mode=1)` default), and CLI→library migration
  notes; example scripts (`quickstart.py`, `parameter_sweep.py`,
  `state_dump.py` — all with `--dry-run`); architecture doc
  (`docs/eq-library/architecture.md`) with ASCII diagram and Phase L
  completion matrix; this changelog entry.

### Known issues

- **L-6 (4-layer test integration) is not yet merged.** Wrapper-only
  tests run via `python3 -m unittest discover python/eqlib/tests`;
  the `eqlib_*` cases in `test_run/test_definitions.conf` will land
  with the L-6 PR.
- `eq_run(mode=0)` (direct EQCALQ entry) returns
  `EQ_ERR_NOT_IMPL`; only `mode=1` (EQDSK load via
  `equnit::eq_load`) is currently wired. Other modes raise
  `EqlibNotImplementedError`.
- `eq_state_t` exports 1-D psi-surface profiles, R/Z grids, and 12
  scalars only. 2-D fields (`PSIRZ`, `RPS(NPSM,NTHM)`,
  `ZPS(NPSM,NTHM)`) require a future C-ABI extension.
- `PSIB` is 0-origin (Fortran `REAL(8) :: PSIB(0:5)`), unlike all
  other 1-D array parameters. Bare `"PSIB"` with no subscript is
  rejected by the registry; always use `set_param("PSIB[i]", v)` for
  `i ∈ 0..5`.
- String parameters (`KNAMEQ` and the six siblings) require the
  dedicated `set_param_str` method — they cannot be passed through
  `set_params(**kwargs)` or `set_param`.
- Single instance per process only — EQ globals are COMMON-block
  plus `eqcom*_mod` module variables.

## TOT Phase L — library-ization (2026-04-19)

Phase L turned TASK/TOT (the integrated transport orchestrator) from a
CLI-only Fortran program into an additionally-loadable composite
shared library with a Python wrapper. TOT is the orchestrator: its
parameter space is the **union** of the six per-module registries
(`eq`, `tr`, `fp`, `ti`, `wr`, `wrx`), so the TOT-specific addition
vs the sibling tr/eq/ti/fp/wr/wrx libraries is **namespaced parameter
dispatch** — every parameter name passed through `tot_set_param`
must carry an `eq:` / `tr:` / `fp:` / `ti:` / `wr:` / `wrx:` prefix.
The `tot` CLI binary and its menu/graphics are unchanged.

### Added

- **L-0 (2026-04-18, PR #17)** — Phase L-0 regression-test
  infrastructure for TOT: `test_run/baselines/tot_*/`,
  `totregress.f90` (env-guarded high-precision dump), Phase-0 baseline
  cases wired into `test_definitions.conf`.
- **L-1 (2026-04-18, PR #23)** — `tot/Makefile` graphics split via
  `TOT_NO_GRAPHICS` preprocessor guard around `GSOPEN` / `GSCLOS`
  call sites; standalone `tot` binary still links graphics, the
  upcoming `libtotapi.so` build path is graphics-free.
- **L-2 (2026-04-18, PR #32)** — C ABI foundation: `tot/tot_api.h`,
  `tot/tot_api.f90`, `tot/tot_state.f90`; 6 entry-point stubs
  returning `TOT_ERR_NOT_IMPL` (ierr=4), plus first C-side smoke
  tests under `tot/tests/c_abi/`.
- **L-3 (2026-04-18, PR #82)** — Namespaced parameter dispatcher
  (`tot/tot_param_registry.f90`) routing `<ns>:<bare>` names to the
  six per-module registries (`eq_param_set`, `tr_param_set`,
  `fp_param_set`, `ti_param_set`, `wrx_param_set`). `wr:` is aliased
  to `wrx:` because TOT links `wrx/libwr.a` (the `wr_param_set`
  symbol resolvable inside `libtotapi.so` is wrx's). String setter
  (`tot_set_param_str`) supports the `tr:` and `eq:` namespaces.
- **L-4 (2026-04-18, PR #85)** — `make -C tot libtotapi.so` builds
  the **composite** shared library: links the six per-module PIC
  archives plus the shared dependency PIC libraries (`lib`, `pl`,
  `bpsd`, `mtxp`, `ob`, `adpost`, `open-adas/adf11`). Non-PIC
  archives and the `tot` binary are unchanged.
- **L-5 (2026-04-18, PR #91)** — Python wrapper `python/totlib/`:
  `Tot` context manager, `TotState` dataclass with `presence`
  sub-dict, exception hierarchy mirroring `enum tot_error`, `_ffi`
  ctypes layer with `TOTLIB_PATH` override and `RTLD_LAZY` loading,
  Python-side namespace guard (`Tot._validate_namespaced_name`)
  catching missing/empty/unknown prefixes before any FFI call.
- **L-7 (2026-04-19, this PR)** — User-facing documentation:
  rewritten `python/totlib/README.md` with full 6-fn API table,
  namespace-prefix rules (with `wr:`→`wrx:` alias), `TotState` field
  table, exception hierarchy, CLI→library migration notes, and known
  limitations; example scripts (`quickstart.py`,
  `parameter_sweep.py`, `state_dump.py` — all with `--dry-run` and
  graceful `TotlibNotImplementedError` handling for the L-3/L-4 stub
  state); architecture doc (`docs/tot-library/architecture.md`) with
  ASCII diagram showing TOT orchestrating the 6 backing modules and
  Phase L completion matrix; this changelog entry.

### Known issues

- **L-6 (4-layer test integration) is not yet merged.** Wrapper-only
  tests run via `python3 -m unittest discover python/totlib/tests`;
  the `totlib_*` cases in `test_run/test_definitions.conf` will land
  with the L-6 PR.
- **`tot.run()` / `tot.get_state()` are stubs.** `tot_init`,
  `tot_run`, `tot_get_state`, `tot_finalize` currently return
  `TOT_ERR_NOT_IMPL` (rc=4); the wrapper accepts both `OK` and
  `NOT_IMPL` from `tot_init` / `tot_finalize` so `set_param` testing
  works today, but `run` / `get_state` raise
  `TotlibNotImplementedError` until L-6 wires the per-module fan-out.
- **`wr:` is aliased to `wrx:`.** TOT links `wrx/libwr.a`, so the
  `wr/wr_param_registry` is not reachable through `libtotapi.so`.
  Use `python/wrlib` (against `wr/libwrapi.so`) to drive the real
  `wr` registry.
- **String parameters wired only for `tr:` and `eq:`.** Other
  namespaces (`fp:`, `ti:`, `wr:`/`wrx:`) reject `tot_set_param_str`
  with `rc=1` until their per-module registries grow a symmetric
  `*_param_set_str` entry point.
- **Single instance per process** — TOT pulls in COMMON blocks from
  six backing modules; two concurrent `Tot()` handles share state.
- **Optimization driver deferred.** The original L-7 plan
  (`docs/superpowers/plans/2026-04-18-tot-library-L7-optimization.md`)
  scoped a parameter-optimization workflow (`optimize.py`,
  `objectives.py`, `results.py`, scipy/optuna/grid backends, three
  notebooks). This PR delivers the documentation subset only;
  the optimization driver is deferred to a follow-up PR.
