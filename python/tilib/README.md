# tilib — Python wrapper for TASK/TI

`tilib` is a thin `ctypes`-based Python wrapper around
`ti/libtiapi.so`, the in-process shared-library version of the TASK/TI
impurity-transport code. It lets scripts drive TI simulations from
Python without shelling out to the standalone `ti` binary or going
through namelist files.

## Overview

TASK/TI has two user-facing deliverables:

| | Traditional CLI | Library (Phase L) |
|---|---|---|
| Binary | `ti/ti` | `ti/libtiapi.so` |
| Entry | interactive menu | 5 C ABI functions |
| I/O | namelist + ASCII output | in-memory state struct |
| Graphics | PGPlot / Fortran 90 graphics | excluded |
| Python | — | `python/tilib` |

The C ABI is defined in `ti/ti_api.h`; the Fortran backend
(`ti/ti_api.f90`, `ti/ti_param_registry.f90`) is unchanged Fortran that
is also linked into the `ti` binary. `python/tilib` only wraps the 5 C
entry points and marshals a `ti_state_t` struct into the pure-Python
`TiState` dataclass.

No third-party dependencies — Python 3.8+ stdlib only (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional.

## Installation

Build the shared library once:

```bash
cd /path/to/task
make -C ti libtiapi.so
```

This is intended to produce `ti/libtiapi.so` with 5 exported symbols
(`ti_init`, `ti_run`, `ti_set_param`, `ti_get_state`, `ti_finalize`)
plus PIC variants of the dependent libraries (`lib*_pic.a`).

> **Known gap (2026-04-18):** the `libtiapi.so` target is not yet
> merged into the `ti/Makefile` on `develop`. Phase L-4 lives on
> `feature/ti-library-L4-shared-lib` and will provide the rule in a
> follow-up PR. Until that lands, obtain `libtiapi.so` by building
> from that branch and copying the artefact into place, or point
> `TILIB_PATH` at a library built elsewhere. The Python wrapper,
> test suite, and examples tolerate a missing `libtiapi.so` —
> FFI-level tests are skipped until the library is available.

Put the wrapper on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Optionally point at a library file outside the repository:

```bash
export TILIB_PATH=/custom/path/libtiapi.so
```

Library lookup order (first match wins): `TILIB_PATH` env var,
`<repo>/ti/libtiapi.so`, `<repo>/lib/libtiapi.so`.

## Quick start

```python
from tilib import TiLib

with TiLib() as ti:
    ti.set_params(NSMAX=1, NRMAX=10, NTSTEP=1,
                  NGTSTEP=1, NGRSTEP=1, NTMAX=2)
    ti.run(ntmax=2)
    state = ti.get_state()

print(f"T={state.T:.6e}  nt={state.nt}  NRMAX={state.nrmax}")
```

This is the Python equivalent of running `ti/ti` with the standalone
`test_run/inputs/ti_min.in` namelist (NSMAX=1, NRMAX=10, NTMAX=2).

See `examples/` for runnable scripts:

- `examples/quickstart.py` — smallest complete run (mirrors `ti_min`)
- `examples/parameter_sweep.py` — 3×3 NRMAX × BB grid
- `examples/state_dump.py` — single run, full `TiState.to_dict()` as JSON

## API reference

### `TiLib(lib_path: str | None = None)`

Context manager. `__enter__` calls `ti_init`; `__exit__` / `close()`
calls `ti_finalize`. Only one live instance per process is meaningful
(TI backend holds global COMMON-block state). The lowercase alias
`Tilib` is exported for callers who prefer it.

### `TiLib.set_param(name, value) -> None`

Set a single parameter. Use `"NAME[i]"` (1-origin) for array elements
and `"NAME[i,j]"` for 2-D arrays (e.g. `"MODEL_BND[1,3]"`); Python
keyword arguments cannot contain brackets so array elements must use
`set_param`, not `set_params`.

### `TiLib.set_params(**kwargs) -> None`

Bulk-set **scalar** parameters. Raises `TilibError` on keys containing
`__` (common array-syntax mistake).

### `TiLib.run(ntmax: int) -> None`

Advance the simulation by `ntmax` steps. `ntmax=0` is a valid no-op
used by the smoke tests.

### `TiLib.get_state() -> TiState`

Snapshot current TICOMM scalars and `[0:nrmax][0:nsa_max]` profile
arrays into a `TiState` dataclass. Trailing padding (up to
`TI_MAX_NRMAX=200` / `TI_MAX_NSA_MAX=20`) is ignored.

### `TiLib.close() -> None`

Idempotent. The context manager calls this automatically.

## Supported parameters

The registry below reflects `ti/ti_param_registry.f90` at Phase L-3.
Add to it by extending that Fortran `SELECT CASE`; no Python change
is required — the wrapper forwards names verbatim.

| Group | Names | Notes |
|---|---|---|
| Geometry / device (plcomm) | `RR`, `RA`, `RKAP`, `RDLT`, `BB`, `RIP` | scalar doubles |
| Profile shape (1-D arrays) | `PROFN1[i]`, `PROFN2[i]`, `PROFT1[i]`, `PROFT2[i]`, `PROFU1[i]`, `PROFU2[i]` | 1-origin index by species |
| Model switches (plcomm) | `MODELG`, `MODELQ`, `MODEL_PROF`, `MODEL_NPROF` | INT cast |
| Plasma scalars | `NSMAX` | INT cast |
| Plasma per-species (1..NSM) | `PA[i]`, `PZ[i]`, `PN[i]`, `PNS[i]`, `PT[i]`, `PTPR[i]`, `PTPP[i]`, `PTS[i]`, `PU[i]`, `PUS[i]` | doubles, 1-origin |
| Species type / charge range | `NPA[i]`, `ID_NS[i]`, `NZMIN_NS[i]`, `NZMAX_NS[i]`, `NZINI_NS[i]` | INT cast |
| Boundary (2-D) | `MODEL_BND[1..3,NS]`, `BND_VALUE[1..3,NS]` | `[row,species]` |
| Time evolution | `DT`, `NRMAX`, `NTMAX`, `NTSTEP`, `NGTSTEP`, `NGRSTEP`, `MAXLOOP`, `EPSLOOP`, `EPSMAT`, `MATTYPE`, `PROFJ1`, `PROFJ2` | mixed int/double |
| Transport / source switches | `MODEL_EQB`, `MODEL_EQN`, `MODEL_EQT`, `MODEL_EQU`, `MODEL_KAI`, `MODEL_DRR`, `MODEL_VR`, `MODEL_NC`, `MODEL_NF`, `MODEL_NB`, `MODEL_EC`, `MODEL_LH`, `MODEL_IC`, `MODEL_CD`, `MODEL_SYNC`, `MODEL_PEL`, `MODEL_PSC` | INT cast |

Unknown names return ierr=1 (raised as `TilibParamError`).

**PA vs PM naming.** `plcomm` defines the atomic-mass array as
`PA(NSM)`. The TI namelist uses `PM(NS)` via a `USE plcomm, pm=>pa`
rename inside `ticomm.f90`, but that alias is not re-exported.
`ti_param_registry` therefore registers only `PA`; pass `"PA[3]"` to
set Argon's atomic mass, not `"PM[3]"`.

## `TiState` fields

Matches `ti_state_t` in `ti/ti_api.h`. Full dict layout is available
via `state.to_dict()` (JSON-serialisable).

| Attribute | Type | Meaning |
|---|---|---|
| `nt` | int | current time-step index |
| `nrmax` | int | radial points actually in use |
| `nsa_max` | int | active species count |
| `nsmax` | int | total species count (from TICOMM) |
| `T` | float | simulation time |
| `residual_loop_max` | float | outer-loop convergence residual |
| `icount_loop_max` | int | outer-loop iterations |
| `icount_mat_max` | int | matrix-solve iterations |
| `RNA` | list[list[float]] | `[nrmax][nsa_max]` density profile |
| `RTA` | list[list[float]] | `[nrmax][nsa_max]` temperature profile |
| `RUA` | list[list[float]] | `[nrmax][nsa_max]` velocity profile |
| `RBP` | list[float] | `[nrmax]` poloidal field |
| `RQP` | list[float] | `[nrmax]` safety-factor profile |
| `RJP` | list[float] | `[nrmax]` current-density profile |
| `ZEFF` | list[float] | `[nrmax]` effective-charge profile |
| `BETA` | list[float] | `[nrmax]` beta profile |
| `BETAP` | list[float] | `[nrmax]` poloidal beta profile |

`TiState.to_dict()` groups the four diagnostic scalars under
`"scalars"` and emits per-radial rows under `"profile"` with a
1-origin `NR` index, making it easy to diff against other dumps or
to serialise directly with `json.dumps`.

## Exceptions

Every `ti_*` return code maps to a concrete subclass of `TilibError`:

| ierr | class | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `TilibParamError` | invalid parameter name / index / value |
| 2 | `TilibStateError` | API call before `ti_init` or after `close` |
| 3 | `TilibRunError` | calculation or `ti_get_state` failed |
| 4 | `TilibNotImplementedError` | Phase L-2 stub return |

Spec-style aliases (`TiLibInvalidParam`, `TiLibNotInitialized`,
`TiLibCalculationFailed`, `TiLibNotImplemented`) are also exported.

## Migration: `ti` CLI → `tilib.TiLib`

| CLI step | `tilib` equivalent |
|---|---|
| edit `&ti` namelist | `ti.set_param(...)` / `ti.set_params(...)` |
| menu option `R` (run) | `ti.run(ntmax=...)` |
| inspect output file | `ti.get_state()` / `state.to_dict()` |
| menu `Q` (quit) | exit context manager / `ti.close()` |
| batch parameter sweep | Python `for` loop (see `examples/parameter_sweep.py`) |

String-valued namelist keys (e.g. `KID_NS(3)='Ar'`) have no equivalent
in the float-only C ABI. In practice `KID_NS` is recomputed from
`NPA` inside `tiinit.f90`, so setting `"NPA[3]"=18.0` gives you the
`Ar` label automatically. Other string parameters remain accessible
only via the CLI until a `ti_set_param_str` extension lands.

The wrapper does **not** wrap graphics, file output, or the
interactive menu — those live in `ti/ti` only.

## Known limitations

- **Single instance per process.** TI backend uses COMMON blocks.
  Two concurrent `TiLib()` instances share state; the second
  `ti_init` resets globals. For parallel sweeps use
  `multiprocessing` — each worker gets its own libtiapi.so state.
- **No graphics, no MPI, no OpenMP API.** Graphics symbols exist but
  are not reachable from the 5 exported entry points.
- **String parameters not yet wired** (`KID_NS`, and any other
  character-valued namelist keys). See `docs/superpowers/specs/
  2026-04-17-tr-library-design.md` §4.3 and the `tilib` fixtures'
  `UNREGISTERED_KEYS` tuples for the current gap list.
- *(2026-04-20: previously the diffusion-coefficient scalars
  `DN0`, `DT0`, `DU0`, `VDN0`, `VDT0`, `VDU0`, `DR0`, `DRS` and the
  per-species overrides `DN0_NS[i]` / `DT0_NS[i]` / etc. were not
  registered. They are now wired through `ti/ti_param_registry.f90`,
  exposed in `ti_mcp/server.py:PARAMETER_REGISTRY`, and the
  `ti_ar` / `ti_min` Layer 1 equivalence tests pass at 1e-10. No
  fallback to `ti_init` defaults is needed any more.)*
- **NRMAX ceiling.** `TI_MAX_NRMAX=200` and `TI_MAX_NSA_MAX=20` bound
  the shared-state struct; exceeding either is reported as ierr=4 by
  `ti_get_state`.
- **`libtiapi.so` build not yet on `develop`.** See "Installation"
  known gap above.

## Testing

```bash
cd python/tilib/tests
python3 -m unittest discover -v
```

Tests that require `libtiapi.so` are skipped when the shared library
is absent; pure-Python tests (ctypes layout, error wiring,
`TiState.from_c`, `to_dict` shape) always run.

The Phase L-6 4-layer suite adds:

- `python/tilib/tests/test_equivalence.py` — Layer 1 vs Phase 0
  baselines (tol `1e-10`)
- `ti/tests/c_abi/test_negative.c` — Layer 2 C ABI rejection contracts
- `python/tilib/tests/test_tilib.py` / `test_ffi.py` — Layer 3
  Python wrapper
- `python/tilib/tests/test_sweep.py` — Layer 4 3×3 DT × NRMAX smoke

When the `tilib_*` entries in `test_run/test_definitions.conf` are
wired up (tracked with the L-6 merge), the whole suite runs through
`run_tests.sh`.

## License / contributions

`tilib` is part of the TASK code and distributed under the repository's
top-level license. Bug reports and PRs are welcome; please keep
wrapper changes minimal — the C ABI is the stable layer, so new
parameters should be added to the Fortran registry first.

## See also

- `docs/superpowers/specs/2026-04-17-tr-library-design.md` — shared
  TR/TI Phase L design
- `docs/ti-library/architecture.md` — system diagram and Phase
  completion matrix
- `ti/ti_api.h` — C ABI header
- `ti/ti_param_registry.f90` — parameter-name dispatch table
- `CHANGELOG.md` — per-phase history
