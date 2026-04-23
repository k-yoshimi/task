# `eq` — Equilibrium

```{admonition} What you'll learn
:class: tip

How to call TASK/EQ (**MHD equilibrium** solver — reads EQDSK data or
analytic profiles, returns ψ-surface geometry and derived scalars) from
Python via the `eqlib` wrapper. Unlike `tr`, `eq` is a **non-time-stepping**
module — `run()` takes a `mode` argument, not a step count — and it
exports a **6th** C ABI function `eq_set_param_str` for string parameters
like `KNAMEQ`.
```

```{toctree}
:hidden:

quickstart
api-reference
```

## What `eq` does

**TASK/EQ** solves the **MHD equilibrium** of a tokamak. Inputs are
either:

- An EQDSK-format (G-EQDSK) equilibrium file, or
- Analytic profiles (pressure $p(\psi)$, safety factor $q(\psi)$, …)

Outputs include magnetic-axis position (`raxis`, `zaxis`), axis and
surface safety factors (`qaxis`, `qsurf`), plasma beta (`betat`, `betap`),
plasma volume (`pvol`), plus R-Z grid data and ψ-surface profiles
(`psips`, `ppps`, `ttps`, `qqps`).

As of PR #164 / #165 the module exposes the shared-library / Python-wrapper /
`validate()` API stack and passes the L-6 equivalence gate at 1e-10.

## Prerequisites and build

```bash
cd /path/to/task                     # TASK repository root
make -C lib   libs_pic
make -C pl    libs_pic
make -C bpsd  libs_pic
make -C mtxp  libs_pic
make -C eq    libeqapi.so
```

Success means `eq/libeqapi.so` exists. `nm -D eq/libeqapi.so | grep ' T eq_'`
should list **six** symbols (eq is the only module with six; the others
have five):

```bash
$ nm -D eq/libeqapi.so | grep ' T eq_'
... T eq_finalize
... T eq_get_state
... T eq_init
... T eq_run
... T eq_set_param
... T eq_set_param_str       # <-- the 6th: string parameters
... T eq_validate            # PR #164 and later
```

## Minimal hello-world

```python
from eqlib import Eq
with Eq() as eq:
    eq.set_param("RR", 6.5)                    # major radius [m]
    eq.set_param("BB", 5.3)                    # field [T]
    eq.set_param("RIP", 1.5)                   # current [MA]
    eq.set_param("MODELG", 3)                  # EQDSK path
    eq.set_param_str("KNAMEQ", "eqdata.ITER")  # filename
    eq.run()                                   # mode=1 (default)
    st = eq.get_state()
print(f"raxis={st.scalars['raxis']:.4f}  qaxis={st.scalars['qaxis']:.4f}")
```

A fully executable version is at {doc}`quickstart`.

## Setting parameters — four ways

### A. Scalars (`set_param`)

Unlike `tr`, `eq`'s `set_params(**kwargs)` accepts only scalar keyword
arguments **and** a positional mapping (see below). The typical
one-at-a-time form is `set_param("NAME", value)`:

```python
eq.set_param("RR", 6.5)
eq.set_param("MODELG", 3)      # int cast from double is OK
eq.set_param("RIPFC[1]", 0.5)  # PF coil current (1-origin, 1..10)
```

```{admonition} `PSIB` is 0-origin
:class: warning

Fortran declares `REAL(KIND=8) :: PSIB(0:5)`, so indexing starts at
**zero**: `PSIB[0]`, `PSIB[1]`, …, `PSIB[5]`. The bare name `"PSIB"`
(no index) is explicitly rejected by the registry with
`EqlibInvalidParamError`. All other 1-D arrays (`RIPFC`, `RPFC`,
`ZPFC`, `WPFC`) are the usual 1-origin.
```

### B. Bulk dict / kwargs (`set_params`)

```python
eq.set_params(RR=6.5, BB=5.3, MODELG=3)      # kwargs form
eq.set_params({"RR": 6.5, "BB": 5.3})         # positional mapping form
```

### C. String parameters (`set_param_str`)

EQDSK-family filenames are `CHARACTER(LEN=80)` — the string API is
**required**; `set_param` will refuse them.

```python
eq.set_param_str("KNAMEQ",  "eqdata.ITER01")
eq.set_param_str("KNAMWR",  "wrdata.dat")
```

There are **7** string-valued parameters:
`KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`, `KNAMPF`.

### D. Pre-run validation (`validate`) — PR #164

```python
from eqlib import Eq, EqDiagCode

with Eq() as eq:
    eq.set_params(RR=6.5, BB=5.3, RIP=1.5, MODELG=3)
    eq.set_param_str("KNAMEQ", "eqdata.missing")

    diags = eq.validate()
    for d in diags:
        print(f"[{EqDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    eq.run()
```

The diagnostic categories match `tr`
({ref}`OUT_OF_RANGE <eq-diag-table>`,
`INCONSISTENT_PAIR`, `OUT_OF_RANGE_AFTER_DEP`, `FILE_MISSING`,
`MISSING_REQUIRED`).  `eq_validate` checks ten grid dimensions
(`NSGMAX`, `NTGMAX`, `NUGMAX`, `NRGMAX`, `NZGMAX`, `NPSMAX`, `NRMAX`,
`NTHMAX`, `NSUMAX`, `NRVMAX`) plus `KNAMEQ` / `KNAMPF` file presence
for the geometry modes that require them.

## FAQ — `eq`-specific

### Q1. Why is `PSIB` 0-origin when everything else is 1-origin?

`eqcom1_mod.f90` declares `REAL(8) :: PSIB(0:5)`. Physically, ψ boundary
conditions start at `ψ = 0` (magnetic axis), so 0-origin is natural in
the Fortran source. The PF-coil arrays (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`)
follow the usual 1-origin convention.

### Q2. Why does `eq.run()` default to `mode=1`?

`mode=1` invokes `equnit::eq_load`, which reads the current `KNAMEQ`
(EQDSK file) and builds the equilibrium. That is the EQDSK-driven
standard workflow. `mode=0` (direct EQCALQ call) is reserved and
currently raises `EqlibNotImplementedError`. Unlike `tr`/`ti`/`wr`/`fp`,
`eq.run` does not advance a time step — the integer argument is a mode
selector.

### Q3. Passing `KNAMEQ` as a kwarg fails

`set_params(KNAMEQ="...")` is rejected. String parameters must go
through `set_param_str("KNAMEQ", "...")`.

### Q4. `EqlibError: libeqapi.so does not export eq_set_param_str`

The `.so` is older than Phase L-3. Rebuild with
`make -C eq libeqapi.so`.

## Registered parameters (excerpt)

`eq/eq_param_registry.f90` defines ~94 cases total (≈78 scalar doubles,
5 array families, 7 strings). Main entries below. See the registry
source for the full list.

(eq-diag-table)=

| Name | Type | Meaning |
|---|---|---|
| `RR`, `RA`, `RB`                  | double | major / minor / wall radius [m] |
| `RKAP`, `RDLT`                    | double | elongation, triangularity |
| `BB`                              | double | toroidal field [T] |
| `RIP`                             | double | plasma current [MA] |
| `Q0`, `QA`, `QMIN`                | double | axis / surface / min safety factor |
| `RHOMIN`, `RHOEDG`                | double | normalised radius bounds |
| `PP0`, `PP1`, `PP2`               | double | pressure-profile coefficients |
| `PROFP0..2`                       | double | pressure-profile exponents |
| `PJ0`, `PJ1`, `PJ2`               | double | current-profile coefficients |
| `PROFJ0..2`                       | double | current-profile exponents |
| `FF0`, `FF1`, `FF2`               | double | $F(\psi)$ coefficients |
| `PROFF0..2`                       | double | $F(\psi)$ exponents |
| `PT0..2`, `PROFTP0..2`            | double | temperature profile |
| `PV0..2`, `PROFV0..2`             | double | velocity profile |
| `PROFR0..2`                       | double | radial profile |
| `PTSEQ`, `PN0EQ`                  | double | edge temperature / central density |
| `EPSEQ`, `EPSNW`, `DELNW`         | double | convergence tolerances |
| `NLPMAX`, `NLPNW`                 | int    | max iterations |
| `RGMIN`, `RGMAX`, `ZGMIN`, `ZGMAX` | double | R-Z grid extents |
| `ZLIMP`, `ZLIMM`, `FRBIN`         | double | limiter positions |
| `MODELG`                          | int    | 1: analytic, 3: EQDSK, 7: VMEC |
| `MODELQ`, `IDEBUG`, `MODEFR`, `MODEFW` | int | model switches |
| `MDLEQF`, `MDLEQC`, `MDLEQA`, `MDLEQX`, `MDLEQV` | int | internal model selectors |
| `NPRINT`                          | int    | output verbosity |
| `NRMAX`, `NTHMAX`, `NSUMAX`, `NSGMAX`, `NTGMAX`, `NUGMAX` | int | ψ-mesh sizes |
| `NRGMAX`, `NZGMAX`, `NPSMAX`, `NRVMAX`, `NTVMAX`, `NPFCMAX` | int | output grids |
| `PSIB[0..5]`                      | double[] | **0-origin** ψ boundary values |
| `RIPFC[1..10]`, `RPFC[1..10]`, `ZPFC[1..10]`, `WPFC[1..10]` | double[] | PF coils (1-origin) |
| `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`, `KNAMPF` | string | via `set_param_str` only |

## `EqState` output

```python
state.nrgmax, state.nzgmax       # actual R, Z grid sizes
state.npsmax                     # actual ψ-surface sample count
state.nrmax, state.nthmax        # ψ-mesh, poloidal-angle mesh
state.nrvmax                     # volume-grid radial points (MODELG=3 only)
state.nsgmax, state.ntgmax       # TASK-native surface-grid sizes (MODELG=3 only)
state.scalars["raxis"]           # magnetic-axis R [m]
state.scalars["zaxis"]           # magnetic-axis Z [m]
state.scalars["qaxis"]           # axis q
state.scalars["qsurf"]           # surface q
state.scalars["betat"]           # toroidal beta
state.scalars["betap"]           # poloidal beta
state.scalars["pvol"]            # plasma volume [m^3]
state.scalars["raave"]           # volume-averaged minor radius [m]
state.scalars["ripx"]            # plasma current [MA]
state.rg                         # [nrgmax] R grid
state.zg                         # [nzgmax] Z grid
state.psips, state.ppps          # [npsmax] ψ surface values, pressure
state.ttps, state.qqps           # [npsmax] T (= R·Bφ), q
state.to_dict()                  # JSON-ready dict
```

See {doc}`api-reference` for the full autodoc listing.

## Fortran design

- [`docs/eq-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/eq-library/architecture.md)
  — design notes
- {doc}`../common/architecture` — cross-module 3-layer design
- `eq/eq_api.f90` — library entry points (5 core + `eq_set_param_str` + `eq_validate`)
- `eq/eq_param_registry.f90` — parameter registry
- `eq/eqcom{0..3}_mod.f90` — module-hoisted COMMON blocks (Phase F-1 / F-5)

### F90 modernisation (F-1 through F-5)

The `eq/` tree came with a large body of F77 fixed-form source and
`eqcom*.inc` INCLUDE files. Modernisation happened alongside
library-isation:

| Phase | PR | What |
|---|---|---|
| F-1 | #71 | COMMON → `eqcom{0..3}_mod.f90` (shim kept in parallel) |
| F-2 | #79 | Fixed-form → free-form (LOW tier) |
| F-3 | #81 | Fixed-form → free-form (MED tier, 9 files) |
| F-4 | #87 | Fixed-form → free-form (HIGH tier, 8 files) |
| F-5 | #93 | Removed shim, replaced `INCLUDE` with `USE` |

After F-5 the `eq/` sources are F90-only; any other module can pull
`USE eqcom*_mod` directly without shims.

## MCP server

The `eq_mcp` server (PR #167) exposes `eq` to LLMs via the Model
Context Protocol:

```bash
cd python/mcp-servers/eq_mcp
uv run python -m eq_mcp
```

Details: `python/mcp-servers/eq_mcp/README.md`.

## Tests

```bash
bash test_run/run_tests.sh eqlib_equivalence eqlib_c_abi \
     eqlib_ffi eqlib_wrapper eqlib_sweep

# or pytest directly:
cd python/eqlib
pytest --forked --timeout=120 --timeout-method=signal tests/
```

Equivalence tests run at `1e-10` tolerance and **must not** be skipped
(see `feedback_equivalence_must_pass`).

## Changelog — L-0..L-7 + F-1..F-5 + validate API

| Phase / PR | Date | Content |
|---|---|---|
| L-0 (#54)  | 2026-04-18 | `eq_iter01` / `eq_tst2` baselines, `eqregress.f90` |
| L-1 (#65)  | 2026-04-18 | `eq/Makefile` CORE/GRAPHICS/MENU split |
| L-2 (#70)  | 2026-04-18 | C ABI stubs (`eq_api.h`, 5 functions) |
| L-3 (#78)  | 2026-04-18 | Parameter registry (94 cases) + 6th ABI `eq_set_param_str` |
| L-4 (#80)  | 2026-04-18 | `libeqapi.so` build + explicit PIC deps |
| L-5 (#86)  | 2026-04-18 | Python wrapper `python/eqlib/` (`run()` defaults to `mode=1`) |
| L-6 (#92)  | 2026-04-19 | 4-layer integration tests (`eqlib_*`) |
| L-7 (#89)  | 2026-04-19 | Documentation (`README.md`, `architecture.md`) |
| F-1..F-5 (#71 … #93) | 2026-04-18/19 | F90 modernisation: COMMON → module, fixed → free form, shim removal |
| #163       | 2026-04-22 | Rearm `eq_bpsd_init_flag` in `EQFINI` (#110) |
| **#164**   | 2026-04-22 | **Pre-run validation API pilot (#143)** |
| #165       | 2026-04-22 | High-level `Eq.validate()` Python wrapper (#143 follow-up) |
| **#167**   | 2026-04-22 | **MCP server for EQ equilibrium module** |
