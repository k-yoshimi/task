# wrxlib — Python wrapper for TASK/WRX

`wrxlib` is a thin `ctypes`-based Python wrapper around
`wrx/libwrxapi.so`, the in-process shared-library version of the
TASK/WRX extended ray-tracing code. It lets scripts drive WRX
simulations from Python without shelling out to the standalone `wrx`
binary or going through namelist files.

Sister package to [`wrlib`](../wrlib/) (TASK/WR ray-tracing). They
share the same two-layer architecture but bind to different shared
libraries (`wrx_*` vs `wr_*` C symbols) and can coexist in the same
Python process.

## Overview

TASK/WRX has two user-facing deliverables:

| | Traditional CLI | Library (Phase L) |
|---|---|---|
| Binary | `wrx/wrx` | `wrx/libwrxapi.so` |
| Entry | interactive menu | 5 C ABI functions |
| I/O | namelist + ASCII output | in-memory state struct |
| Graphics | PGPlot / Fortran 90 graphics | excluded |
| Python | — | `python/wrxlib` |

The C ABI is defined in `wrx/wrx_api.h`; the Fortran backend
(`wrx/wrx_api.f90`, `wrx/wrx_param_registry.f90`) is unchanged Fortran
that is also linked into the `wrx` binary. `python/wrxlib` only wraps
the 5 C entry points and marshals a `wrx_state_t` struct into the
pure-Python `WrxState` dataclass.

No third-party dependencies — Python 3.8+ stdlib only (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional.

## Installation

Build the shared library once:

```bash
cd /path/to/task
make -C wrx libwrxapi.so
```

This produces `wrx/libwrxapi.so` with 5 exported symbols (`wrx_init`,
`wrx_run`, `wrx_set_param`, `wrx_get_state`, `wrx_finalize`) plus PIC
variants of the dependent libraries (`lib*_pic.a`). The pre-existing
non-PIC `*.a` archives and the `wrx` binary are unchanged.

Put the wrapper on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Optionally point at a library file outside the repository:

```bash
export WRXLIB_PATH=/custom/path/libwrxapi.so
```

Library lookup order (first match wins): `WRXLIB_PATH` env var,
`<repo>/wrx/libwrxapi.so`, `<repo>/lib/libwrxapi.so`.

## WRX_RUN_OK gate (historical — now retired)

**Resolved (2026-04-20).** Earlier `libwrxapi.so` builds SEGV'd inside
`wrcalpwr → libgrf::grd1d` because `USE libgrf` resolved `grd1d` to the
real `libgrf_pic.a` symbol, which then walked an uninitialized
`grf_attr_type` past the boundary of the no-op `wrx_graphics_stubs.f90`
shims. The fix gates the entire `PAGES/GRD1D/PAGEE` block in
`wrcalpwr.f90` behind a `WRX_NO_GRAPHICS` environment variable that
`wrx_api_init` sets via `setenv()` on `.so` startup. The binary `wrx`
leaves the variable unset and continues to render through the full
`libgsp/libg3d` stack unchanged.

Three companion fixes landed alongside the gate:

* `wrcalpwr.f90`: `nstpmax_all` clamp to `nstpmax-1` so `xtemp(nstp+1)`
  no longer overruns when a ray uses every `NSTPMAX` step.
* `wrcalpwr.f90`: `nraymax >= 2` guard around the unconditional ray-2
  print and `grd1d(2,...)` call.
* `wrcomm.f90 :: wr_allocate`: allocate + zero-init the per-species
  `pos_pwrmax_{rs,rl}_nsa` and `pwrmax_{rs,rl}_nsa` arrays that
  `wrx_get_state` reads (previously declared but never allocated, so
  reading them via the `.so` SEGV'd).
* `wrcomm.f90 :: wr_allocate`: ALLOCATED-canary guard on the SAVE-based
  early-return so a `wrx_finalize → wrx_init` cycle re-allocates rather
  than dereferencing freed pointers.

Tests need not explicitly set `WRX_RUN_OK=1`; PR #166 made `1` the
default for the test-side gate (`os.environ.get("WRX_RUN_OK", "1")
!= "0"`). The env var only affects the pytest suite — the library
itself has no runtime gate.

## Quick start

```python
from wrxlib import Wrxlib

with Wrxlib() as wrx:
    wrx.set_params(MODELG=2, RR=6.2, RA=2.0, BB=5.3,
                   NSMAX=2, NRAYMAX=1, NSTPMAX=2000,
                   MDLWRI=2, MDLWRQ=1, SMAX=2.0, DELS=1e-3)
    wrx.set_param("PA[1]", 2.0);    wrx.set_param("PA[2]", 5.4462e-4)
    wrx.set_param("PZ[1]", 1.0);    wrx.set_param("PZ[2]", -1.0)
    wrx.set_param("PN[1]", 1.0);    wrx.set_param("PN[2]", 1.0)
    wrx.set_param("PTPR[1]", 10.0); wrx.set_param("PTPP[1]", 10.0)
    wrx.set_param("PTPR[2]", 10.0); wrx.set_param("PTPP[2]", 10.0)
    wrx.set_param("RFIN[1]", 170.0e3)   # 170 GHz EC
    wrx.set_param("RPIN[1]", 8.0)
    wrx.set_param("ANGTIN[1]", 10.0)
    wrx.set_param("UUIN[1]", 1.0)
    wrx.set_param("MODEWIN[1]", 1)

    wrx.run(nray_request=0)         # 0 keeps namelist NRAYMAX
    state = wrx.get_state()

print(f"pwr_tot = {state.scalars['pwr_tot']:.4g}")
print(f"per-species peak (rs) = {state.pwrmax_rs_nsa}")
```

See `examples/` for runnable scripts:

- `examples/quickstart.py` — smallest complete run (mirrors
  `wrx_iter01`).
- `examples/parameter_sweep.py` — 3×3 RFIN × ANGPIN grid; each cell
  re-opens a fresh `Wrxlib` context so the init/finalize cycle is
  exercised 9 times.
- `examples/state_dump.py` — single run, full `WrxState.to_dict()` as
  JSON.

All three accept `--dry-run` to validate argument parsing and import
wiring without invoking the FFI (useful for smoke runs without the
shared library present).

## API reference

### `Wrxlib(lib_path: str | None = None)`

Context manager. `__init__` calls `wrx_init`; `__exit__` / `close()`
calls `wrx_finalize`. Only one live instance per process is
meaningful (WRX backend holds global COMMON-block state).

### `Wrxlib.set_param(name, value) -> None`

Set a single parameter. Use `"NAME[i]"` (1-origin) for array elements
(e.g. `"RFIN[1]"`, `"PN[2]"`); Python keyword arguments cannot
contain brackets so array elements must use `set_param`, not
`set_params`.

### `Wrxlib.set_params(**kwargs) -> None`

Bulk-set **scalar** parameters. Raises `WrxlibError` on keys
containing `__` (common array-syntax mistake).

### `Wrxlib.run(nray_request: int = 0) -> None`

Execute `wrx_setup → wrx_exec`. `nray_request > 0` overrides the
namelist `NRAYMAX` before allocation; `nray_request <= 0` keeps
whatever NRAYMAX is currently set.

The historical `libgrf::grd1d` SEGV was retired by PR #123
(`WRX_NO_GRAPHICS=1` setenv inside `wrx_api_init` suppresses the
libgrf path). The library itself has no runtime gate — `.run()`
dispatches unconditionally. The test-side `WRX_RUN_OK` guard was
flipped default-on by PR #166; set `WRX_RUN_OK=0` only to skip
`.run()`-exercising tests when the shared library is absent.

### `Wrxlib.get_state() -> WrxState`

Snapshot current WRCOMM dimensions, the `pwr_tot` scalar, per-ray
and per-species absorbed-power arrays, and per-species peak-power
positions for both `rs` (short-path) and `rl` (long-path) axes into a
`WrxState` dataclass. Trailing padding (up to `WRX_MAX_NRAYMAX=100`,
`WRX_MAX_NSAMAX=8`) is ignored.

### `Wrxlib.close() -> None`

Idempotent. The context manager calls this automatically.

## Supported parameters

The registry below reflects `wrx/wrx_param_registry.f90` at Phase L-3
(~70 names covering ~120 settable variables once subscripts are
counted). Add to it by extending that Fortran `SELECT CASE`; no
Python change is required — the wrapper forwards names verbatim.

| Group | Names | Notes |
|---|---|---|
| Geometry / device (plcomm) | `RR`, `RA`, `RB`, `RKAP`, `RDLT`, `BB`, `Q0`, `QA`, `RIP` | scalar doubles |
| Plasma scalars (plcomm) | `NSMAX`, `PROFJ` | INT cast for NSMAX |
| Plasma per-species (1..NSM) | `PA[i]`, `PZ[i]`, `PN[i]`, `PNS[i]`, `PTPR[i]`, `PTPP[i]`, `PTS[i]`, `PROFN1[i]`, `PROFN2[i]`, `PROFT1[i]`, `PROFT2[i]` | doubles, 1-origin |
| pl/dp integration | `MODELG`, `MODELQ`, `NSAMAX_WR`, `MODELP[i]`, `MODELV[i]`, `NCMIN[i]`, `NCMAX[i]` | INT cast |
| WRX control scalars (wrcomm) | `NRAYMAX`, `NSTPMAX`, `NRSMAX`, `NRLMAX`, `LMAXNW`, `MDLWRI`, `MDLWRG`, `MDLWRP`, `MDLWRQ`, `MDLWRW` | INT cast |
| WRX per-ray initial conditions (NRAYM=100) | `RFIN[i]`, `RPIN[i]`, `ZPIN[i]`, `PHIIN[i]`, `ANGTIN[i]`, `ANGPIN[i]`, `RNPHIN[i]`, `RNZIN[i]`, `MODEWIN[i]`, `UUIN[i]`, `RBRADAIN[i]`, `RBRADBIN[i]`, `RCURVAIN[i]`, `RCURVBIN[i]`, `RNKIN[i]` | 1-origin; MODEWIN INT cast |
| Ray control scalars (wrcomm) | `SMAX`, `DELS`, `UUMIN`, `EPSRAY`, `DELRAY`, `DELDER`, `DELKR`, `EPSNW`, `EPSD0`, `pne_threshold`, `bdr_threshold` | doubles |
| Mode switches | `mode_beam`, `mode_wline`, `mode_fig`, `model_fdrv`, `model_fdrv_ds` | INT cast |

Unknown names return ierr=1 (raised as `WrxlibParamError`).
Out-of-range indices (`PA[0]` or `PN[NSM+1]`) also return ierr=1.

## `WrxState` fields

Matches `wrx_state_t` in `wrx/wrx_api.h`. Full dict layout is
available via `state.to_dict()` (JSON-serialisable; the
`rays` / `profile_rs` / `profile_rl` shape mirrors `wrlib.state` so
`compare_metrics.py` can diff WRX wrapper output against `wrlib`
output for cases where both apply).

| Attribute | Type | Meaning |
|---|---|---|
| `nraymax` | int | rays actually in use |
| `nstpmax` | int | NSTPMAX used for this run |
| `nsamax` | int | plasma species actually in use |
| `nsmax` | int | NSMAX (plasma species count) |
| `modelg` | int | MODELG model switch |
| `mdlwrq` | int | MDLWRQ power-deposition switch |
| `scalars` | dict[str, float] | `{"pwr_tot": <total absorbed power>}` |
| `nstp_end` | list[int] | `[nraymax]` end-step index for each ray |
| `pwr_nray` | list[float] | `[nraymax]` per-ray absorbed power |
| `pwr_nsa` | list[float] | `[nsamax]` per-species absorbed power |
| `pwr_nsa_nray` | list[list[float]] | `[nraymax][nsamax]` per-ray per-species power |
| `pos_pwrmax_rs_nsa` | list[float] | `[nsamax]` peak-power position (rs / short path) by species |
| `pwrmax_rs_nsa` | list[float] | `[nsamax]` peak-power value (rs / short path) by species |
| `pos_pwrmax_rl_nsa` | list[float] | `[nsamax]` peak-power position (rl / long path) by species |
| `pwrmax_rl_nsa` | list[float] | `[nsamax]` peak-power value (rl / long path) by species |

The 2-D `pwr_nsa_nray` matrix is sliced to the active `[0:nraymax]
[0:nsamax]` corner; zero-padded struct tails are dropped.

## Exceptions

Every `wrx_*` return code maps to a concrete subclass of
`WrxlibError`:

| ierr | class | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `WrxlibParamError` | invalid parameter name / index / value |
| 2 | `WrxlibStateError` | API call before `wrx_init` or after `close` |
| 3 | `WrxlibRunError` | calculation (`wrx_setup`/`wrx_exec`) or `wrx_get_state` failed |
| 4 | `WrxlibNotImplementedError` | retained for backward compatibility; no longer returned by L-3+ |

Spec-style aliases (`WrxLibInvalidParam`, `WrxLibNotInitialized`,
`WrxLibCalculationFailed`, `WrxLibNotImplemented`) are also exported.
`raise_for_rc` is an alias of `raise_for_ierr` matching the `fplib` /
`trlib` naming.

## Migration: `wrx` CLI → `wrxlib.Wrxlib`

| CLI step | `wrxlib` equivalent |
|---|---|
| edit `wrxparm` namelist | `wrx.set_param(...)` / `wrx.set_params(...)` |
| menu option `R` (run) | `wrx.run(nray_request=...)` |
| inspect output file | `wrx.get_state()` / `state.to_dict()` |
| menu `Q` (quit) | exit context manager / `wrx.close()` |
| batch parameter sweep | Python `for` loop (see `examples/parameter_sweep.py`) |

The wrapper does **not** wrap graphics, file output, or the
interactive menu — those live in `wrx/wrx` only.

## Known limitations

- **`wrx_run` SEGV in `libgrf::grd1d` (historical).** Earlier
  `libwrxapi.so` builds could SEGV inside `wrcalpwr → libgrf::grd1d`;
  the root cause was fixed in 2026-04-20 by gating the graphics block
  behind a `WRX_NO_GRAPHICS` env var that `wrx_api_init` sets on
  library startup. See the "WRX_RUN_OK gate (historical — now
  retired)" section above and
  [`docs/wrx-library/architecture.md`](../../docs/wrx-library/architecture.md)
  for the full analysis. `.run()` is default-on as of PR #166.
- **Single instance per process.** WRX backend uses COMMON blocks
  plus module-scope allocation flags. Two concurrent `Wrxlib()`
  instances share state; the second `wrx_init` resets globals. For
  parallel sweeps use `multiprocessing` — each worker gets its own
  `libwrxapi.so` state.
- **Beam-tracing (`mode_beam /= 0`) outputs are not exposed through
  `wrx_get_state`.** The ray-tracing solver runs, but only
  ray-tracing per-species power-deposition outputs are surfaced
  (`pwr_nsa`, `pwr_nray`, etc.).
- **Input scalars (`RFIN`, `RPIN`, ...) are not echoed in
  `wrx_get_state`.** Set them via `set_param` and use the round-trip
  for confirmation; reading them back is a future-phase extension.
- **String parameters not yet wired.** Currently-deferred; see
  `docs/superpowers/specs/2026-04-17-tr-library-design.md` §4.3.

## Testing

```bash
cd python/wrxlib/tests
python3 -m unittest discover -v
```

Tests that require `libwrxapi.so` are skipped when the shared library
is absent; pure-Python tests (ctypes layout, error wiring,
`WrxState.from_c`, `to_dict` shape) always run. The test-side
`WRX_RUN_OK` gate on `.run()`-exercising tests was flipped default-on
by PR #166 (`os.environ.get("WRX_RUN_OK", "1") != "0"`). The library
itself has no such gate — `Wrxlib.run()` dispatches unconditionally.

The Phase L-6 4-layer suite is wired into
`test_run/test_definitions.conf`:

- `wrxlib_c_abi` — Layer 2 C ABI (`make -C wrx wrx_api_check_all`;
  includes `test_smoke`, `test_param`, `test_run`, `test_run_so`,
  `test_negative`)
- `wrxlib_ffi`, `wrxlib_wrapper` — Layer 3 Python wrapper
- `wrxlib_equivalence` — Layer 1 vs Phase 0 baselines (tol `1e-10`)
  for `wrx_iter01`
- `wrxlib_sweep` — Layer 4 3×3 RFIN × ANGPIN smoke

## Independence from `wrlib`

`wrlib` (sister WR Phase L-5 package) and `wrxlib` use distinct C
symbol prefixes (`wr_*` vs `wrx_*`) and distinct shared libraries
(`libwrapi.so` vs `libwrxapi.so`). They can coexist in the same
Python process:

```python
from wrlib import Wrlib
from wrxlib import Wrxlib
# both can be loaded simultaneously
```

## License / contributions

`wrxlib` is part of the TASK code and distributed under the
repository's top-level license. Bug reports and PRs are welcome;
please keep wrapper changes minimal — the C ABI is the stable layer,
so new parameters should be added to the Fortran registry first.

## See also

- `docs/superpowers/specs/2026-04-17-tr-library-design.md` — shared
  TR/TI/WR/WRX Phase L design (WRX follows the same pattern)
- `docs/wrx-library/architecture.md` — system diagram, Phase
  completion matrix, and full `libgrf::grd1d` limitation analysis
- `python/wrlib/README.md` — WR sister package
- `wrx/wrx_api.h` — C ABI header
- `wrx/wrx_param_registry.f90` — parameter-name dispatch table
- `CHANGELOG.md` — per-phase history
