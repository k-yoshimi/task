# fplib — Python wrapper for TASK/FP

`fplib` is a thin `ctypes`-based Python wrapper around
`fp/libfpapi.so`, the in-process shared-library version of the TASK/FP
Fokker-Planck code. It lets scripts drive FP simulations from Python
without shelling out to the standalone `fp` binary or going through
namelist files.

## Overview

TASK/FP has two user-facing deliverables:

| | Traditional CLI | Library (Phase L) |
|---|---|---|
| Binary | `fp/fp` | `fp/libfpapi.so` |
| Entry | interactive menu | 5 C ABI functions |
| I/O | namelist + ASCII/graphics output | in-memory state struct |
| Graphics | PGPlot / Fortran 90 graphics (`fpgout`, `fpgsub`, `fpcont`, `fpfout`) | excluded |
| Python | — | `python/fplib` |

The C ABI is defined in `fp/fp_api.h`; the Fortran backend
(`fp/fp_api.f90`, `fp/fp_param_registry.f90`) is unchanged Fortran that
is also linked into the `fp` binary. `python/fplib` only wraps the 5 C
entry points and marshals a `fp_state_t` struct into the pure-Python
`FpState` dataclass.

No third-party dependencies — Python 3.8+ stdlib only (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional.

## Installation

Per-system files first (all gitignored; once per checkout):

```bash
cd /path/to/task
cp make.header.org make.header            # edit compiler / flags for your system
cp mtxp/make.mtxp.nompi mtxp/make.mtxp    # or another mtxp/make.mtxp.* template
git clone --branch develop https://github.com/k-yoshimi/bpsd.git ../bpsd   # patched fork, see docs/external-patches/bpsd-fork.md
make -C ../bpsd libbpsd.a                 # populates ../bpsd/mod/*.mod, which pl's PIC build reads
```

The TASK checkout must be named `task`: `../bpsd/Makefile` includes
`../task/make.header`.

Then build the shared library once:

```bash
cd /path/to/task
make -C fp libfpapi.so
```

The target builds the dependent PIC archives (`../lib`, `../mtxp`, `../pl`, `../eq`, `../dp`, `../ob`) and the in-tree
PIC copy of bpsd (`make -C fp bpsd_pic`) in dependency order before
compiling the fp objects, so this one command works from a clean
tree (#230). Build serially: `make -jN` is not supported by the
per-directory Makefiles (no intra-directory object dependencies).

This produces `fp/libfpapi.so` with 5 exported symbols (`fp_init`,
`fp_run`, `fp_set_param`, `fp_get_state`, `fp_finalize`) plus PIC
variants of the dependent libraries (`lib*_pic.a`). The pre-existing
non-PIC `*.a` archives and the standalone `fp` binary are unchanged.

Verify the exported symbol surface:

```bash
nm -D fp/libfpapi.so | grep ' T fp_'
```

Should list exactly `fp_init`, `fp_run`, `fp_set_param`,
`fp_get_state`, `fp_finalize`.

Put the wrapper on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Optionally point at a library file outside the repository:

```bash
export FPLIB_PATH=/custom/path/libfpapi.so
```

Library lookup order (first match wins): `FPLIB_PATH` env var,
`<repo>/fp/libfpapi.so`, `<repo>/lib/libfpapi.so`.

## Quick start

```python
from fplib import Fplib

with Fplib() as fp:
    fp.set_params(
        MODELG=3, NSMAX=3,
        PA={2: 2.0, 3: 3.0},
        PN={1: 0.8, 2: 0.4, 3: 0.4},
        NRMAX=40, NPMAX=50, NTHMAX=50,
        NTMAX=2, DELT=1.0e-3,
        RMIN=0.4, RMAX=0.8,
    )
    fp.run(ntmax=2)
    state = fp.get_state()

print(f"TIMEFP={state.timefp:.6e}  NRMAX={state.nrmax}  NSAMAX={state.nsamax}")
print(f"RNT[NSA=1, NR=1..5] = {state.RNT[0][:5]}")
```

This is the Python equivalent of running `fp/fp` with the standalone
`test_run/inputs/fp_iter01.in` namelist.

See `examples/` for runnable scripts:

- `examples/quickstart.py` — smallest complete run (mirrors `fp_iter01`)
- `examples/parameter_sweep.py` — 3×3 RR × BB grid
- `examples/state_dump.py` — single run, full `FpState.to_dict()` as JSON

## API reference

### `Fplib(lib_path: str | None = None)`

Context manager. `__enter__` calls `fp_init`; `__exit__` / `close()`
calls `fp_finalize`. Only one live instance per process is meaningful
(FP backend holds global FPCOMM state).

### `Fplib.set_param(name, value) -> None`

Set a single parameter. Use `"NAME[i]"` (1-origin) for array elements;
Python keyword arguments cannot contain brackets, so raw bracket syntax
goes through `set_param`.

### `Fplib.set_params(**kwargs) -> None`

Bulk-set parameters. Accepts three value shapes per keyword:

- scalar (`int` / `float`) → `set_param(NAME, value)`
- `dict {idx: value}` → `set_param("NAME[idx]", value)` for each entry
- `list` / `tuple` `[v1, v2, ...]` → `set_param("NAME[i]", vi)` with
  `i = 1, 2, ...`

Raises `FplibError` on keys containing `__` (common array-syntax
mistake).

### `Fplib.run(ntmax: int) -> None`

Advance the simulation by `ntmax` steps. `ntmax=0` is a valid no-op
used by the smoke tests. `fp_run` internally calls `fp_prep` on the
first invocation, then `fp_loop`.

### `Fplib.get_state() -> FpState`

Snapshot current FPCOMM scalars and `[0:nsamax][0:nrmax]` profile
arrays into an `FpState` dataclass. Trailing padding (up to
`FP_MAX_NSAMAX=8` / `FP_MAX_NRMAX=100`) is ignored.

### `Fplib.close() -> None`

Idempotent. The context manager calls this automatically.

## Supported parameters

The registry below reflects `fp/fp_param_registry.f90` at Phase L-3.
Add to it by extending that Fortran `SELECT CASE`; no Python change
is required — the wrapper forwards names verbatim.

| Group | Names | Notes |
|---|---|---|
| Geometry / device | `RR`, `RA`, `RB`, `RKAP`, `RDLT`, `BB`, `RIP` | scalar doubles (PLCOMM) |
| Mesh | `NRMAX`, `NPMAX`, `NTHMAX`, `NTMAX`, `NAVMAX` | cast to INT |
| Species counts | `NSMAX`, `NSAMAX`, `NSBMAX` | cast to INT |
| Species mapping (arrays, 1..NSM) | `NS_NSA[i]`, `NS_NSB[i]` | cast to INT |
| Species real arrays (1..NSM) | `PA[i]`, `PZ[i]`, `PN[i]`, `PNS[i]`, `PTPR[i]`, `PTPP[i]`, `PTS[i]`, `PMAX[i]` | 1-origin |
| Time evolution | `DELT`, `EPSFP`, `LMAXFP` | `LMAXFP` cast to INT |
| Radial / scalar physics | `R1`, `DELR1`, `RMIN`, `RMAX`, `E0`, `ZEFF` | |
| Wave heating | `PABS_EC`, `PABS_LH`, `PABS_FW`, `PABS_WR`, `PABS_WM`, `RF_WM` | |
| Model switches (scalar int) | `MODELG`, `MODELE`, `MODELR`, `MODELS`, `MODELD`, `MODEL_NBI`, `MODEL_WAVE`, `MODEL_DISRUPT`, `MODEL_BS`, `MODEL_LOSS`, `MODEL_SYNCH`, `MODEL_FOW` | |
| Model switches (arrays) | `MODELC[i]`, `MODELW[i]` | per-species |

Unknown names return rc=1 (raised as `FplibInvalidParamError`).

## `FpState` fields

Matches `fp_state_t` in `fp/fp_api.h`. Full dict layout is available
via `state.to_dict()` (JSON-serialisable, layout compatible with
`compare_metrics.py`-style diffing).

| Attribute | Type | Meaning |
|---|---|---|
| `nrmax` | int | radial points actually in use |
| `nsamax` | int | kinetic species actually in use |
| `npmax` | int | momentum points |
| `nthmax` | int | pitch-angle points |
| `ntg2` | int | long-time-axis counter |
| `timefp` | float | simulation time (s) |
| `RNT` | list[list[float]] | `[nsamax][nrmax]` density profile |
| `RWT` | list[list[float]] | `[nsamax][nrmax]` stored-energy profile |
| `RTT` | list[list[float]] | `[nsamax][nrmax]` temperature profile |
| `RJT` | list[list[float]] | `[nsamax][nrmax]` current density profile |
| `RPCT` | list[list[float]] | `[nsamax][nrmax]` collisional power profile |
| `RPWT` | list[list[float]] | `[nsamax][nrmax]` wave-absorbed power profile |
| `scalars` | dict[str, float] | the seven volume-integrated globals below |

`scalars` holds the seven doubles that `fp_state_t` carries after the
profile arrays: the first six are summed over the kinetic species at the
latest global-diagnostic sample (`NTG1`), and `PLASMA_VOLUME` is `TVOLR`,
the sum of the radial cell volumes. All seven are zero until the first
`run()`, and again after a `set_param` until the next `run()` that is
made, while the profiles are still those of the last run:

| Key | Unit | Meaning |
|---|---|---|
| `TOTAL_IP` | MA | total plasma current |
| `STORED_ENERGY` | MJ | stored energy |
| `COLLISION_POWER` | MW | total collisional power |
| `ABSORPTION_POWER` | MW | total absorbed wave power |
| `ABSORPTION_WR` | MW | ray-tracing (WR) part of the absorbed power |
| `ABSORPTION_WM` | MW | full-wave (WM) part of the absorbed power |
| `PLASMA_VOLUME` | m^3 | plasma volume (`TVOLR`) |

`state.to_dict()` puts them under a top-level `"scalars"` key.
`fp_state_t` grows at its end only: a `libfpapi.so` built before these
members existed must be rebuilt (`make -C fp libfpapi.so`) together with
this wrapper.

Memory-layout note: C declares `RNT[NSAMAX][NRMAX]` (row-major); the
Fortran backend declares `RNT(NRMAX, NSAMAX)` (column-major). Both lay
out the same bytes, only the index order differs.

## Exceptions

Every `fp_*` return code maps to a concrete subclass of `FplibError`:

| rc | class | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `FplibInvalidParamError` | invalid parameter name / index / value |
| 2 | `FplibNotInitError` | API call before `fp_init` or after `close` |
| 3 | `FplibCalcFailedError` | `fp_run` or `fp_get_state` failed |
| 4 | `FplibNotImplementedError` | reserved (Phase L-2 stub return) |

Spec-style aliases (`FpLibInvalidParam`, `FpLibNotInitialized`,
`FpLibCalculationFailed`, `FpLibNotImplemented`) are also exported.
`FplibOverflowError` is kept as a backwards-compatible alias for
`FplibCalcFailedError`.

## Migration: `fp` CLI → `fplib.Fplib`

| CLI step | `fplib` equivalent |
|---|---|
| edit `fpparm` namelist | `fp.set_param(...)` / `fp.set_params(...)` |
| menu option `R` (run) | `fp.run(ntmax=...)` |
| inspect graphics output | `fp.get_state()` + plot from Python |
| menu `Q` (quit) | exit context manager / `fp.close()` |
| batch parameter sweep | Python `for` loop (see `examples/parameter_sweep.py`) |

The wrapper does **not** wrap graphics, file I/O, or the interactive
menu — those live in `fp/fp` only.

## Known limitations

- **Single instance per process.** FP backend uses module-level state
  (FPCOMM). Two concurrent `Fplib()` instances share state; the second
  `fp_init` resets globals. Cross-process sweeps work via Python
  `multiprocessing`.
- **No graphics, no MPI, no OpenMP API.** Graphics subsystem
  (`fpgout`, `fpgsub`, `fpcont`, `fpfout`) is stubbed out in
  `fp_graphics_stubs.f90`; the loader uses `RTLD_LAZY` so dangling
  references never resolve.
- **`fp_finalize` does not deallocate FPCOMM arrays** (asymmetry
  between `fp_allocate` and `fp_deallocate`). A single
  `fp_init` / `fp_run` / `fp_finalize` cycle per process is the
  supported lifecycle at Phase L-3.
- **String parameters not yet wired** (e.g. `KNAMFP`). File-name
  namelist keys must be left at their defaults; the float-only C ABI
  cannot carry strings.
- **Unregistered namelist keys** — any name missing from
  `fp_param_registry.f90` returns `FplibInvalidParamError`. The
  current registry covers ~55 settable variables across geometry,
  mesh, species, time, heating, and model switches; less-used knobs
  may require a one-line `CASE` addition.
- **`FP_MAX_NRMAX=100`, `FP_MAX_NSAMAX=8`** are compile-time caps on
  the exported state struct. Runs needing larger meshes require
  bumping these in `fp/fp_api.h` and rebuilding `libfpapi.so`.

## Testing

```bash
cd python/fplib/tests
python3 -m unittest discover -v
```

Tests that require `libfpapi.so` are skipped when the shared library
is absent; pure-Python tests (ctypes layout, error wiring,
`FpState.from_c`, `to_dict` shape) always run.

The full 4-layer regression suite is wired into
`test_run/test_definitions.conf`:

- `fplib_c_abi` — Layer 2 C ABI (`make -C fp fp_api_check_all`)
- `fplib_ffi`, `fplib_wrapper` — Layer 3 Python wrapper
- `fplib_equivalence` — Layer 1 vs Phase 0 baselines (tol `1e-10`)
- `fplib_sweep` — Layer 4 3×3 RR×BB smoke

## License / contributions

`fplib` is part of the TASK code and distributed under the repository's
top-level license. Bug reports and PRs are welcome; please keep
wrapper changes minimal — the C ABI is the stable layer, so new
parameters should be added to the Fortran registry first.

## See also

- Design spec: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
  (TR design; fp follows the same pattern)
- `docs/fp-library/architecture.md` — system diagram and Phase
  completion matrix
- Phase plans: `docs/superpowers/plans/2026-04-18-fp-library-L*.md`
- `fp/fp_api.h` — C ABI header
- `CHANGELOG.md` — per-phase history
