# eqlib — Python wrapper for TASK/EQ

`eqlib` is a thin `ctypes`-based Python wrapper around
`eq/libeqapi.so`, the in-process shared-library version of the TASK/EQ
MHD-equilibrium code. It lets scripts drive EQ calculations (EQDSK
load and downstream `equnit` post-processing) from Python without
shelling out to the standalone `eq` binary or going through namelist
files.

## Overview

TASK/EQ has two user-facing deliverables:

| | Traditional CLI | Library (Phase L) |
|---|---|---|
| Binary | `eq/eq` | `eq/libeqapi.so` |
| Entry | interactive menu | 6 C ABI functions |
| I/O | namelist + EQDSK + ASCII | in-memory state struct |
| Graphics | PGPlot / Fortran 90 graphics | excluded (replaced by stubs) |
| Python | — | `python/eqlib` |

The C ABI is defined in `eq/eq_api.h`; the Fortran backend
(`eq/eq_api.f90`, `eq/eq_param_registry.f90`) is unchanged Fortran
that is also linked into the `eq` binary. `python/eqlib` wraps the 6
C entry points (one more than tr/ti/wr/fp because EQ exposes a string
setter for `KNAMEQ` and friends) and marshals an `eq_state_t` struct
into the pure-Python `EqState` dataclass.

No third-party dependencies — Python 3.8+ stdlib only (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional and detected at
runtime if present.

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
make -C eq libeqapi.so
```

The target builds the dependent PIC archives (`../lib`, `../mtxp`, `../pl`) and the in-tree
PIC copy of bpsd (`make -C eq bpsd_pic`) in dependency order before
compiling the eq objects, so this one command works from a clean
tree (#230). Build serially: `make -jN` is not supported by the
per-directory Makefiles (no intra-directory object dependencies).

This produces `eq/libeqapi.so` together with PIC variants of the
dependent libraries (`lib*_pic.a`). The pre-existing non-PIC `*.a`
archives and the `eq` binary are unchanged.

Put the wrapper on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Optionally point at a library file outside the repository:

```bash
export EQLIB_PATH=/custom/path/libeqapi.so
```

Library lookup order (first match wins): `EQLIB_PATH` env var,
`<repo>/eq/libeqapi.so`, `<repo>/lib/libeqapi.so`.

## Quick start

```python
from eqlib import Eq

with Eq() as eq:
    eq.set_params(RR=3.0, BB=3.0, RIP=1.0, MODELG=3)
    eq.set_param_str("KNAMEQ", "eqdata")   # path to EQDSK file
    eq.run()                               # mode=1 (default) → eq_load
    state = eq.get_state()

print(f"raxis={state.scalars['raxis']:.4f}  "
      f"qaxis={state.scalars['qaxis']:.4f}")
```

See `examples/` for runnable scripts:

- `examples/quickstart.py` — smallest complete run
- `examples/parameter_sweep.py` — RR / BB grid
- `examples/state_dump.py` — single run, full `EqState.to_dict()` as JSON

All three accept `--dry-run` so you can validate argument parsing on a
machine without `libeqapi.so` built.

## Library layout check (#246)

`load_library()` asks `libeqapi.so` for its `eq_state_t` layout
(`eq_state_abi_version()`, `eq_state_size()`) and refuses it with
`EqlibAbiError` when the version or the size differs from this wrapper's
`EqStateC`, or when the library exports neither symbol (built before
#246). The message names the fix: rebuild the library
(`make -C eq libeqapi.so`) or update the wrapper. A library and a
wrapper from different commits used to fail silently (fields written
past the struct, or appended fields read as `0.0`). A wrapper older
than #246 does not ask, so keep the two from the same commit.

## API reference

### `Eq(lib_path: str | None = None)`

Context manager. `__init__` calls `eq_init`; `__exit__` / `close()`
calls `eq_finalize`. Only one live instance per process is meaningful
(EQ backend holds singleton COMMON-block + `eqcom*_mod` module state).

### `Eq.set_param(name, value) -> None`

Set a single numeric parameter. Use `"NAME[i]"` for array elements;
**`PSIB` is the only 0-origin array** (Fortran `REAL(8) :: PSIB(0:5)`)
— write `set_param("PSIB[0]", 0.0)`. All other 1-D array parameters
(`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) use 1-origin subscripts. Bare
`"PSIB"` with no subscript is rejected (`EqlibInvalidParamError`).

### `Eq.set_param_str(name, value) -> None`

Set one of the seven string-valued (`CHARACTER(LEN=80)`) parameters:
`KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`,
`KNAMPF`. This is the EQ-specific 6th C ABI symbol
(`eq_set_param_str`); other library wrappers in the project do not
have it. Older `libeqapi.so` builds without the string setter raise
`EqlibError` — rebuild via `make -C eq libeqapi.so` to recover.

### `Eq.set_params(*args, **kwargs) -> None`

Bulk-set **scalar** parameters. Accepts kwargs, a dict positional
arg, or an iterable of `(name, value)` pairs. Names containing `__`
are rejected up-front as a likely array-subscript mistake — call
`set_param("NAME[i]", v)` for array elements (Python kwargs cannot
contain `[` or `]`).

### `Eq.run(mode: int = 1) -> None`

Run the EQ solver. **Default is `mode=1`** (real EQDSK load via
`equnit::eq_load` using the current `MODELG` + `KNAMEQ`); other modes
return `EQ_ERR_NOT_IMPL` and raise `EqlibNotImplementedError`. Mode 0
is reserved for a future direct EQCALQ entry. Note that this default
choice differs from tr/ti/wr/fp where `run(ntmax=...)` is positional;
EQ's mode is a small integer enum, not a step count.

### `Eq.get_state() -> EqState`

Snapshot the current grid/profile state into an `EqState` dataclass.
Profile arrays are sliced to the active runtime size (`[0:nrgmax]`,
`[0:npsmax]`, etc.); the trailing zero-padding (up to `EQ_MAX_*`)
is hidden from callers.

### `Eq.save(path) -> None`

Write the equilibrium of the last `run` to a TASK/EQ binary file
(`EQSAVE`): sets `KNAMEQ` to `path` (a `str` or a `pathlib.Path`), then
calls `eq_save`. The file is what `MODELG=3` with `KNAMEQ=path` loads, in
EQ (`run(1)`) and in the modules that read an equilibrium file. `KNAMEQ`
is ASCII: a `bytes` path and a non-ASCII one are refused. Once the path is
accepted, `KNAMEQ` stays at it also when the save then fails. After a
failed write, what is at the path cannot be taken for the equilibrium that
was to be saved (usually it is a short file): do not load it (`run(1)` with `MODELG=3`
ends the process on a file that is cut off).

A save whose file was not opened, or is shorter than what was written, is
an error:

- `EqlibInvalidParamError`, and no file is touched: the fields do not
  hold the equilibrium of the present parameters (no `run` since the
  handle was opened, a later solve or load that failed, or `set_param` of anything
  but `MODEFR` and `MODEFW` since the last one: run again first); a blank
  path, one longer than the 80 bytes of `KNAMEQ` (refused, not cut), or
  one that ends in a blank; `MODEFW` other than 0 (overwrite an existing
  file) or 3 (refuse one): with 1, 2 and 4 to 7 `FWOPEN` can read unit 5.
- `EqlibCalculationFailedError`: the file could not be opened (a
  directory that is missing or not writable; `MODEFW=3` and an existing
  file), a write failed (an existing file without write permission), or
  the file is shorter than what was written (a write the system refused,
  as under a file size limit; a device such as `/dev/null`).

"A `run` since" and "a `set_param` since" are what `eq_api` and eq's
parameter registry saw; a set of tot's `eq:` parameters goes through the
registry and counts as a `set_param`. In the mono image (`MONO_LIB_PATH`,
`libtotapi_mono.so`) the other modules can change the equilibrium past
both (the `eq_init` or `EQINIT` of the other modules' init, `eq_load` and
`eq_calc` in the tr, fp and wrx run paths, a `plcomm` variable set through
another module's registry, such as `ti:RR`), and `save` then writes what
the fields hold (#260).

### `Eq.close() -> None`

Idempotent. The context manager calls this automatically on exit.

## Supported parameters

The registry below reflects `eq/eq_param_registry.f90` at Phase L-3
(94 `CASE` entries: ~78 numeric scalars, 5 array families, 7 string
keys). Add to it by extending the Fortran `SELECT CASE`; no Python
change is required — names are forwarded verbatim.

| Group | Names | Notes |
|---|---|---|
| Geometry / device | `RR`, `RA`, `RB`, `RKAP`, `RDLT`, `BB`, `Q0`, `QA`, `RIP`, `RHOMIN`, `QMIN`, `RHOEDG` | `plcomm_parm` scalars |
| Pressure profile | `PP0`, `PP1`, `PP2`, `PROFP0`, `PROFP1`, `PROFP2` | `eqcom1_mod` |
| Current profile | `PJ0`, `PJ1`, `PJ2`, `PROFJ0`, `PROFJ1`, `PROFJ2` | |
| F-function profile | `FF0`, `FF1`, `FF2`, `PROFF0`, `PROFF1`, `PROFF2` | |
| Temperature profile | `PT0`, `PT1`, `PT2`, `PROFTP0`, `PROFTP1`, `PROFTP2`, `PTSEQ`, `PN0EQ` | |
| Velocity profile | `PV0`, `PV1`, `PV2`, `PROFV0`, `PROFV1`, `PROFV2` | |
| Radial profile | `PROFR0`, `PROFR1`, `PROFR2` | |
| Convergence | `EPSEQ`, `EPSNW`, `DELNW`, `NLPMAX`, `NLPNW` | |
| Domain | `RGMIN`, `RGMAX`, `ZGMIN`, `ZGMAX`, `ZLIMP`, `ZLIMM`, `FRBIN` | |
| Model switches | `MODELG`, `MODELQ`, `IDEBUG`, `MODEFR`, `MODEFW`, `MDLEQF`, `MDLEQC`, `MDLEQA`, `MDLEQX`, `MDLEQV`, `NPRINT` | int (cast via INT(value)) |
| Mesh sizes | `NRMAX`, `NTHMAX`, `NSUMAX`, `NSGMAX`, `NTGMAX`, `NUGMAX`, `NRGMAX`, `NZGMAX`, `NPSMAX`, `NRVMAX`, `NTVMAX`, `NPFCMAX` | int |
| 1-D arrays (0-origin) | `PSIB[0..5]` | **Bare `"PSIB"` rejected — always pass `[i]`** |
| 1-D arrays (1-origin) | `RIPFC[1..10]`, `RPFC[1..10]`, `ZPFC[1..10]`, `WPFC[1..10]` | PF-coil descriptors |
| String (`set_param_str`) | `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`, `KNAMPF` | `CHARACTER(LEN=80)` |

Unknown names return `rc == 1` (raised as `EqlibInvalidParamError`).
Run `grep -E "^\s*CASE \(" eq/eq_param_registry.f90` to dump the
exact registry contents from your build.

## `EqState` fields

Matches `eq_state_t` in `eq/eq_api.h`. `state.to_dict()` is
JSON-serialisable and uses uppercase keys to match the Phase L-0
baseline format so `compare_metrics.py` can diff wrapper output
against the `eq` binary.

| Attribute | Type | Meaning |
|---|---|---|
| `nrgmax` | int | active R-grid points (`rg` length) |
| `nzgmax` | int | active Z-grid points (`zg` length) |
| `npsmax` | int | active psi-surface samples (psips/ppps/ttps/qqps) |
| `nrmax` | int | psi-mesh runtime size |
| `nthmax` | int | poloidal-angle runtime size |
| `nsumax` | int | surface-points runtime size |
| `scalars` | `dict[str, float]` | 12 plasma scalars (see below) |
| `rg` | `list[float]` | `[nrgmax]` R-grid coordinates |
| `zg` | `list[float]` | `[nzgmax]` Z-grid coordinates |
| `psips` | `list[float]` | `[npsmax]` psi-surface ψ values |
| `ppps` | `list[float]` | `[npsmax]` pressure profile |
| `ttps` | `list[float]` | `[npsmax]` T (= R·Bφ) profile |
| `qqps` | `list[float]` | `[npsmax]` q profile |

Scalars (canonical order): `raxis`, `zaxis`, `psi0`, `psipa`,
`psita`, `qaxis`, `qsurf`, `betat`, `betap`, `pvol`, `raave`, `ripx`.

## Exception hierarchy

Every `eq_*` return code maps to a concrete subclass of `EqlibError`:

| rc | class | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `EqlibInvalidParamError` | invalid parameter name / index / value (incl. bare `"PSIB"`) |
| 2 | `EqlibNotInitializedError` | API call before `eq_init` or after `close` |
| 3 | `EqlibCalculationFailedError` | `eq_run` / `eq_get_state` failed (e.g. EQDSK file missing) |
| 4 | `EqlibNotImplementedError` | Phase L-2 stub — `eq_run(mode != 1)` returns this |

Spec-style aliases (`EqLibError`, `EqLibInvalidParam`,
`EqLibNotInitialized`, `EqLibCalculationFailed`,
`EqLibNotImplemented`) are also exported.

## Migration: `eq` CLI → `eqlib.Eq`

| CLI step | `eqlib` equivalent |
|---|---|
| edit `eqparm` namelist | `eq.set_param(...)` / `eq.set_params(...)` |
| EQDSK file path / namelist `KNAMEQ` | `eq.set_param_str("KNAMEQ", path)` |
| menu option for EQDSK load | `eq.run(mode=1)` (default `mode=1`) |
| inspect graphics output | `eq.get_state()` → numpy / matplotlib |
| menu `Q` (quit) | exit context manager / `eq.close()` |
| batch parameter sweep | Python `for` loop (see `examples/parameter_sweep.py`) |

The wrapper does **not** wrap graphics, file output, or the
interactive menu — those live in `eq/eq` only.

### EQ-specific quirks worth knowing

These three behaviours catch new users:

1. **`PSIB` is 0-origin.** Always `set_param("PSIB[0]", v)`; bare
   `"PSIB"` (no subscript) is rejected by the registry. All other
   1-D arrays (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) are 1-origin.
2. **String parameters use `set_param_str`, not `set_param`.**
   `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`,
   `KNAMPF` go through the dedicated 6th C ABI entry. They cannot be
   passed via `set_params(**kwargs)`.
3. **`Eq.run()` defaults to `mode=1`.** Calling `eq.run()` with no
   argument loads the current `KNAMEQ` via `equnit::eq_load`. This
   matches the canonical EQDSK-driven workflow. `mode=0` is reserved
   for a future direct EQCALQ entry and currently raises
   `EqlibNotImplementedError`.

## Known limitations

- **Single instance per process.** EQ uses COMMON blocks + module
  variables (`eqcom*_mod`). Two concurrent `Eq()` handles share state;
  the second `eq_init` resets globals. Use `multiprocessing` for
  parallel sweeps — each worker process gets its own `libeqapi.so`
  load.
- **No graphics, no MPI, no OpenMP API.** Graphics symbols are
  stubbed; `RTLD_LAZY` defers resolution so the unreferenced stubs
  never block library load.
- **`eq_run(mode=0)` (direct EQCALQ) is not yet implemented.** Only
  `mode=1` (EQDSK load) returns success; other modes raise
  `EqlibNotImplementedError`.
- **2-D fields not yet exported.** The current `eq_state_t` carries
  1-D psi-surface profiles, R/Z grids, and 12 scalars only. `PSIRZ`,
  `RPS(NPSM, NTHM)`, and `ZPS(NPSM, NTHM)` will require a future
  C-ABI extension.
- **Only seven string keys are wired.** Other character-valued
  namelist entries in `eqparm` (if any are added later) need
  registry extension.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `FileNotFoundError: libeqapi.so not found` | not built | `make -C eq libeqapi.so` |
| `OSError: cannot open shared object file` | dependent libs missing from `LD_LIBRARY_PATH` | export `LD_LIBRARY_PATH` with their install path |
| `EqlibInvalidParamError` on a name that should work | not yet in `eq_param_registry.f90` | add a `CASE ("MYNAME")` and rebuild `libeqapi.so` |
| `EqlibInvalidParamError` on `"PSIB"` | bare name has no idx | always use `"PSIB[0]"` … `"PSIB[5]"` |
| `EqlibError: libeqapi.so does not export eq_set_param_str` | pre-L-3 build | rebuild `libeqapi.so` after the L-3 registry land |
| `EqlibCalculationFailedError` in `eq.run()` | `KNAMEQ` not set or EQDSK missing | call `set_param_str("KNAMEQ", path)` first |
| `EqlibNotImplementedError` in `eq.run()` | mode != 1 | use `eq.run()` (mode=1 default) |

## Tests

```bash
cd python/eqlib/tests
python3 -m unittest discover -v
```

Tests that require `libeqapi.so` are skipped when the shared library
is absent; pure-Python tests (ctypes layout, error wiring,
`EqState.from_c`, `to_dict` shape) always run.

## See also

- `docs/eq-library/architecture.md` — system diagram + Phase L
  completion matrix
- `docs/superpowers/specs/2026-04-17-tr-library-design.md` — full
  design spec (TR template; eq follows the same pattern with one extra
  string-setter entry point)
- `docs/superpowers/plans/2026-04-18-eq-library-L*.md` — per-phase
  plans
- `eq/eq_api.h` — C ABI header
- `eq/eq_param_registry.f90` — parameter registry source
- `python/trlib/README.md`, `python/tilib/README.md`,
  `python/wrlib/README.md`, `python/fplib/README.md` —
  sibling library wrappers
- `CHANGELOG.md` — top-level per-phase history
