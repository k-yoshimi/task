# `tr` — Transport

```{admonition} What you'll learn
:class: tip

How to call TASK/TR (1-D tokamak transport simulation) from Python via
the `trlib` library. This chapter covers building the shared library,
the minimal hello-world, the four ways to set parameters (scalar /
array / string / `validate()`), FAQ, and running the regression tests.
```

```{toctree}
:hidden:

quickstart
api-reference
```

## What `tr` does

**TASK/TR** performs **1-D (radial) transport simulations** for tokamaks
and spherical tokamaks. It evolves radial profiles (density, temperature,
current, magnetic equilibrium) self-consistently in time.

Primary output quantities:

- `RN[i][j]` — density at radius point $i$ for species $j$
- `RT[i][j]` — temperature, same index convention
- `AJ[i]`   — current-density profile
- `QP[i]`   — safety-factor ($q$) profile
- Scalars: `T` (time), `WPT` (stored energy), `Q0` (axis $q$),
  `BETAN` ($\beta_N$) — 13 scalars total

See {doc}`../common/architecture` for the shared architectural pattern,
and `docs/tr-library/architecture.md` for Fortran-side design notes.

## Prerequisites and build

### Building the shared library

```bash
cd /path/to/task                    # TASK repository root
make -C lib  libs_pic               # PIC archives for lower-level libs
make -C pl   libs_pic               # plasma common module
make -C eq   libs_pic               # equilibrium module
make -C mtxp libs_pic               # sparse-matrix solver
make -C bpsd libs_pic               # BPSD data bridge
make -C tr   libtrapi.so            # the shared library itself
```

Success means `tr/libtrapi.so` exists:

```bash
$ ls -lh tr/libtrapi.so
-rwxr-xr-x 1 user user 8.2M Apr 23 14:00 tr/libtrapi.so
```

File size is environment-dependent but typically 5–10 MB.

### Verifying exported functions

```bash
$ nm -D tr/libtrapi.so | grep ' T tr_'
000000000005a1b0 T tr_finalize
000000000005a090 T tr_get_state
0000000000059e10 T tr_init
0000000000059f80 T tr_run
0000000000059d30 T tr_set_param
0000000000059ca0 T tr_set_param_str
00000000000?????? T tr_validate            # PR #172 and later
```

The `T` column marks exported functions.

### Making the Python package importable

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Then `import trlib` works.

## Minimal hello-world (5 lines)

```python
from trlib import Trlib            # (1) import
with Trlib() as tr:                # (2) init (tr_init called automatically)
    tr.set_params(RR=3.0, BB=3.0)  # (3) major radius 3 m, field 3 T
    tr.run(ntmax=10)               # (4) advance 10 time steps
    state = tr.get_state()         # (5) read state (TrState)
print(state.scalars["T"])          # final time in seconds
```

### Line-by-line

- **(1) `from trlib import Trlib`** — imports the main class. `Trlib` is
  a handle to the shared library.
- **(2) `with Trlib() as tr:`** — Python context-manager semantics.
  `__enter__` calls `tr_init`; `__exit__` calls `tr_finalize`. Cleanup
  runs even if an exception is raised inside the block.
- **(3) `tr.set_params(RR=3.0, BB=3.0)`** — scalar bulk-setter. Keyword
  names match the Fortran `/TR/` namelist (`RR` = major radius,
  `BB` = toroidal field).
- **(4) `tr.run(ntmax=10)`** — advance 10 time steps with step size
  `DT` (default 0.01 s).
- **(5) `state = tr.get_state()`** — snapshot the current state into a
  `TrState` dataclass. Access scalars via `state.scalars["T"]` and
  profiles via `state.RT[i][j]`.

### Expected output

```bash
$ PYTHONPATH=python python3 examples/quickstart.py
NT=50  NRMAX=50  NSMAX=2
T    = 0.5
WPT  = 8.3e+05
Q0   = 0.96
BETAA= 0.42
```

A fully executable version is at {doc}`quickstart`.

## Setting parameters — four ways

### A. Scalars (`set_params`)

```python
tr.set_params(RR=7.5, RA=2.0, BB=5.3, DT=0.05, NTMAX=200)
```

### B. Array elements (`set_param`)

Python keyword arguments can't contain `[`/`]`, so array elements go
through `set_param`. Indices are **1-origin**.

```python
tr.set_param("PN[1]", 1.0)   # species-1 density
tr.set_param("PN[2]", 1.0)   # species-2 density
tr.set_param("CDW[12]", 0.5) # 12th transport-coefficient slot
```

### C. String parameters (`set_param_str`)

```python
tr.set_param_str("KNAMEQ", "eqdata.ITER01")
```

### D. Pre-run validation (`validate`) — new in PR #172

```{admonition} New API (PR #172)
:class: important

`validate()` performs batch cross-parameter checks before `run()`. It
returns a list of typed diagnostic entries — out-of-range values,
inconsistent pairs, missing files — so callers can surface all problems
at once instead of discovering them one at a time at run time.
```

```python
from trlib import Trlib, TrDiagCode

with Trlib() as tr:
    tr.set_params(RR=3.0, BB=3.0, NSMAX=2)
    tr.set_param_str("KNAMEQ", "eqdata.missing")  # file does not exist

    diags = tr.validate()
    for d in diags:
        print(f"[{TrDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    tr.run(ntmax=10)
```

Diagnostic categories:

| Code | Meaning |
|---|---|
| `OUT_OF_RANGE`           | value outside allowed range |
| `INCONSISTENT_PAIR`      | related parameters violate a cross-constraint |
| `OUT_OF_RANGE_AFTER_DEP` | out-of-range after resolving dependent parameters |
| `FILE_MISSING`           | referenced file doesn't exist (e.g. `KNAMEQ`) |
| `MISSING_REQUIRED`       | a required parameter is unset |

## The `with` context manager

```{admonition} Background
:class: note

Python's `with` statement guarantees that cleanup runs when the block
exits, even via an exception. It mirrors the `with open(...) as f:`
pattern. `Trlib` implements `__enter__` / `__exit__` so
`tr_finalize` is always called.
```

Equivalent explicit form:

```python
tr = Trlib()
try:
    tr.set_params(RR=3.0)
    tr.run(ntmax=10)
    state = tr.get_state()
finally:
    tr.close()
```

## FAQ / common gotchas

### Q1. `FileNotFoundError: libtrapi.so not found …`

Either the library hasn't been built, or it's not where we looked:

1. Check `ls tr/libtrapi.so`.
2. If missing, run `make -C tr libtrapi.so`.
3. To load from a non-standard location:
   `export TRLIB_PATH=/path/to/libtrapi.so`.

### Q2. `TrlibParamError: ierr=1`

Either the parameter name isn't registered, or an array index is out
of range. Check the `SELECT CASE` block in
`tr/tr_param_registry.f90` — adding a new parameter is usually a
one-line change (followed by a rebuild).

### Q3. I typed `set_params(PN__1=1.0)` by accident

Double-underscore keys are rejected explicitly as a likely
mis-encoding of the array syntax. The correct form is
`tr.set_param("PN[1]", 1.0)`.

### Q4. Can I create two `Trlib()` instances in the same process?

**No.** Since PR #171, `Trlib` enforces the singleton boundary via a
`weakref` — the second `Trlib()` raises `TrlibStateError`. For
multi-instance scenarios use `multiprocessing` (process isolation).

### Q5. My results don't match the `tr2` CLI

Run the equivalence regression:

```bash
bash test_run/run_tests.sh trlib_equivalence
```

Tolerance is `1e-10`. Drift beyond that typically means a registered
parameter was missed when the library run was configured.

### Q6. Do I need NumPy?

**No.** `TrState` exposes plain Python `list`s. Convert as needed:
`import numpy as np; np.array(state.RT)`.

## Registered parameters

Main parameters defined in `tr/tr_param_registry.f90`. Names match the
Fortran `/TR/` namelist. Array entries are set via
`set_param("NAME[i]", value)` with 1-origin indexing.

| Name | Type | Meaning |
|---|---|---|
| `RR`      | double     | plasma major radius [m] |
| `RA`      | double     | minor radius [m] |
| `RKAP`    | double     | elongation |
| `RDLT`    | double     | triangularity |
| `BB`      | double     | toroidal field [T] |
| `PHIA`    | double     | total flux [Wb] |
| `RIPS`    | double     | plasma current at t=start [MA] |
| `RIPE`    | double     | plasma current at t=end [MA] |
| `MODELG`  | int        | geometry model (1: analytic, 3: eqdata, 7: VMEC) |
| `NSMAX`   | int        | number of particle species |
| `PA[i]`   | double[]   | atomic mass (species `i`) |
| `PZ[i]`   | double[]   | charge |
| `PN[i]`   | double[]   | central density |
| `PNS[i]`  | double[]   | edge density |
| `PT[i]`   | double[]   | central temperature |
| `PTS[i]`  | double[]   | edge temperature |
| `DT`      | double     | time step [s] |
| `NTMAX`   | int        | number of time steps |
| `NTSTEP`  | int        | output decimation interval |
| `EPSLTR`  | double     | convergence tolerance |
| `LMAXTR`  | int        | maximum iteration count |
| `MDLKAI`  | int        | transport (chi) model selector |
| `MDLETA`  | int        | resistivity model |
| `MDLAD`   | int        | transport-term toggle |
| `MDLAVK`  | int        | transport-averaging-k switch |
| `CDW[i]`  | double[]   | transport coefficients (12 slots) |
| `CHP`, `CK0`, `CK1` | double | chi correction coefficients |
| `MDLNB`, `MDLEC`, `MDLLH`, `MDLIC` | int | NBI/EC/LH/IC heating models |
| `MDLJBS`  | int        | bootstrap current model |
| `MDLPEL`, `MDLST`, `MDLNF`, `MDLUF` | int | pellet/source/fusion/UFILE |
| `PROFN1`, `PROFN2` | double | density profile shape |
| `PNC`, `MDLIMP` | —    | impurity injection |
| `PNBR0`, `PNBRW`, `PNBENG`, `PNBRTG` | double | NBI position/width/energy |
| `PICCD`, `PICR0`, `PICRW`, `PICNPR` | double | ICRF parameters |
| `PECCD`, `PECR0`, `PECRW`, `PECNPR` | double | ECRF parameters |
| `PLHCD`, `PLHR0`, `PLHRW`, `PLHNPR`, `PLHTOT` | double | LH parameters |
| `NGTSTP`, `NGRSTP` | int | graphics decimation |
| `KNAMEQ`  | string     | equilibrium-data filename (via `set_param_str`) |

## `TrState` output

`tr.get_state()` returns a `TrState` dataclass that mirrors the C
`tr_state_t` in `tr/tr_api.h`.

```python
state.nt              # time-step count
state.nrmax           # actual number of radial points (<= 500)
state.nsmax           # actual species count (<= 8)
state.scalars["T"]    # time (seconds)
state.scalars["WPT"]  # stored energy
state.scalars["Q0"]   # axis q
state.scalars["BETAN"]# beta_N
state.RN[0][0]        # RN[radius=0][species=0]
state.RT              # [nrmax][nsmax] 2-D list
state.AJ[0]           # current density (first point)
state.QP[-1]          # edge q
state.to_dict()       # JSON-ready dict
```

See {doc}`api-reference` for the full autodoc listing.

## Fortran design

- [`docs/tr-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/tr-library/architecture.md)
  — design notes
- {doc}`../common/architecture` — cross-module 3-layer design
- `tr/tr_api.f90` — library entry points (5 functions + `tr_validate`)
- `tr/tr_param_registry.f90` — `SELECT CASE` table used by `set_param`

## MCP server

A Model Context Protocol server is bundled so LLMs can drive `tr`
without writing Python:

```bash
cd python/mcp-servers/tr_mcp
uv run python -m tr_mcp
```

See `python/mcp-servers/tr_mcp/README.md` for the exposed tools list.

## Tests

Four layers of regression coverage:

```bash
# Single layers
bash test_run/run_tests.sh trlib_equivalence  # Layer 1 (1e-10 PASS)
bash test_run/run_tests.sh trlib_c_abi        # Layer 2
bash test_run/run_tests.sh trlib_ffi          # Layer 3 (low-level)
bash test_run/run_tests.sh trlib_wrapper      # Layer 3 (high-level)
bash test_run/run_tests.sh trlib_sweep        # Layer 4
```

Or directly via pytest:

```bash
cd python/trlib
pytest --forked --timeout=120 --timeout-method=signal tests/
```

Equivalence tests MUST pass at `1e-10` — no SKIPs (see
`feedback_equivalence_must_pass` in project memory).

## Changelog — Phase L-0 through L-7 and the validate API

| Phase / PR | Date | Content |
|---|---|---|
| L-0 (#2)   | 2026-04-18 | Phase 0 regression test foundation: 3 JSON baselines |
| L-1 (#21)  | 2026-04-18 | `tr/Makefile` graphics separation |
| L-2 (#27)  | 2026-04-18 | C ABI skeleton (5 functions, ierr=4 stubs) |
| L-3 (#33)  | 2026-04-18 | Parameter registry (38 cases) |
| L-4 (#35)  | 2026-04-18 | `make -C tr libtrapi.so` produces the `.so` |
| L-5 (#44)  | 2026-04-18 | Python wrapper `python/trlib/` |
| L-6 (#53)  | 2026-04-18 | 4-layer tests (equivalence PASSes at 1e-10) |
| L-7        | 2026-04-18 | Documentation pass (architecture.md, README, examples/) |
| #171       | 2026-04-23 | Singleton boundary, dim-bound checks, C-string validation |
| **#172**   | 2026-04-23 | **`tr_validate` API (issue #143 pilot)** — pre-run validation |
