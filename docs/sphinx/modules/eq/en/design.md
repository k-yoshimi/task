# Fortran Design

The `eq` library wraps the same physics kernel as the existing `eqx2`
binary (≈32 `.f90` source files including `eqcalq.f90`, `eqfunc.f90`,
`eqcalc.f90`, …) with a thin C-ABI entry layer (`eq_api.f90`) on top
to produce `libeqapi.so`. The shared three-layer design is described
in [Common Architecture](../../../portal/en/common/architecture.md). This page
focuses on the parts specific to `eq`.

## Entry layer (`eq_api.f90`)

There are **six** functions callable from C, plus `eq_validate`, `eq_save` and `eq_get_psi_rz`. The
defining feature of `eq` is the additional `eq_set_param_str` (for
string parameters) on top of the standard five.

| C symbol | Fortran side | Role |
|---|---|---|
| `eq_init`           | `eq_api_init`           | `pl_init` → `eq_init` (internal) — COMMON initialisation |
| `eq_set_param`      | `eq_api_set_param`      | delegates to `eq_param_registry::eq_param_set` |
| `eq_set_param_str`  | `eq_api_set_param_str`  | string version — **the eq-only 6th ABI function** |
| `eq_run`            | `eq_api_run`            | switches behaviour by `mode` (no time evolution) |
| `eq_get_state`      | `eq_api_get_state`      | copies EQCOMM scalars and ψ-surface profiles into the C structure |
| `eq_finalize`       | `eq_api_finalize`       | re-arms the SAVE flag via `eq_bpsd_reset` |
| `eq_validate`       | `eq_api_validate`       | grid-dimension + `KNAMEQ` file-existence checks |
| `eq_save`           | `eq_api_save`           | writes the equilibrium of the last `eq_run` to the file named by `KNAMEQ` (`EQSAVE`); an error when the file was not opened or is shorter than what was written |
| `eq_get_psi_rz`     | `eq_api_get_psi_rz`     | copies the 2-D poloidal flux `PSIRZ` (R index fastest); `EQ_ERR_INVALID` when there is no equilibrium of the present parameters (the cases of `eq_save`) |

All are bound to fixed C ABI symbols via `BIND(C, NAME="eq_xxx")`.

### What is special about `eq_run`

`eq_run(mode)` takes an **operating mode**, not a time-step count.

| `mode` | Behaviour | Legacy CLI |
|---|---|---|
| 0 | `EQCALC` (analytic G-S solve) + `EQCALQ` (post-processing) | `R` -> `F` |
| 1 (default) | `equnit::eq_load` — read the file in `KNAMEQ` and build the equilibrium | `L` |
| 2+ | (for future expansion) — `EqlibNotImplementedError` | — |

The argument has a different meaning from `tr`'s `tr_run(ntmax)`, so
do not confuse the two.

```{note}
`mode=0` is for `MODELG ∈ {0, 1, 2}` (analytic geometries). It solves
the Grad-Shafranov equation analytically from the device parameters
(`RR`, `RA`, `BB`, `RIP`) and the pressure / current profile
coefficients (`PP*`, `PJ*`, `FF*`, ...). It corresponds to the `R`
(Run) command of the legacy `eqx2` CLI: `EQCALC` builds the
equilibrium and then `EQCALQ` runs the flux-surface-average
post-processing that fills the diagnostic quantities `qaxis`,
`qsurf`, `betat`, `betap`, `pvol`, etc.

`mode=1` is for `MODELG ∈ {3, 5, 8}` (file-based geometries) and
loads the EQDSK file named by `KNAMEQ`.
```

### C structure layout (`eq_state_t`)

Defined in `eq/eq_api.h`. The main part:

```c
typedef struct {
    int    nrgmax, nzgmax, npsmax, nrmax, nthmax, nsumax, nrvmax;
    double raxis, zaxis, psi0, psipa, psita;
    double qaxis, qsurf, betat, betap, pvol, raave, ripx;
    double rg[EQ_MAX_NRGMAX];
    double zg[EQ_MAX_NZGMAX];
    double psips[EQ_MAX_NPSMAX];
    double ppps[EQ_MAX_NPSMAX];
    double ttps[EQ_MAX_NPSMAX];
    double qqps[EQ_MAX_NPSMAX];
    /* ... */
} eq_state_t;
```

Note that, unlike `tr_state_t`, this **has no time-step counter**.

## Parameter registry (`eq_param_registry.f90`)

Same `SELECT CASE` style as `tr`, exposing about 94 cases.

- **78 numeric scalars**: `RR`, `RA`, `BB`, `RIP`, `Q0`, `QA`,
  `EPSEQ`, `MODELG`, `MDLEQF`, …
- **5 array families**:
  - `PSIB[0..5]` — **0-origin** (from the `PSIB(0:5)` declaration in `eqcom1_mod`)
  - `RIPFC[1..NPFCM]` (1-origin)
  - `RPFC[1..NPFCM]` (1-origin)
  - `ZPFC[1..NPFCM]` (1-origin)
  - `WPFC[1..NPFCM]` (1-origin)
- **7 strings**: `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`,
  `KNAMFO`, `KNAMPF`

### Separate entry for strings

`KNAMEQ` and similar are `CHARACTER(LEN=80)` and cannot ride the
`REAL(rkind)` pipeline, so a separate `eq_param_set_str` function is
provided. That is the reason for the **6th** function `eq_set_param_str`
in the C ABI.

`tr` later added `tr_set_param_str` as well, but `eq` has needed it
from the start in order to handle EQDSK filenames.

## Source layout inside the library

The ≈32 `.f90` files in `eq/` group by role as follows.

| Group | Main files | Role |
|---|---|---|
| **API layer**           | `eq_api.f90`, `eq_param_registry.f90`, `eq_state.f90` | C ABI entry; does not touch the physics kernel |
| **Main solver**         | `eqcalq.f90`, `eqcalc.f90`, `eqcalv.f90`, `equnit.f90` | Grad-Shafranov iteration, free-boundary calculation |
| **Profiles**            | `eqfunc.f90`, `eqsub.f90`, `eqsplf.f90`, `eqgetp.f90` | evaluation of $p(\psi)$, $F(\psi)$, $q(\psi)$ |
| **Common modules**      | `eqcom0_mod.f90` … `eqcom3_mod.f90`, `equcom.f90` | global state (COMMON blocks lifted into MODULE) |
| **I/O**                 | `eqfile.f90`, `equread.f90`, `eq-eqdsk.f90`, `eqgout.f90` | EQDSK reader, result output |
| **BPSD bridge**         | `eqbpsd.f90`, `eqintf.f90`, `equintf.f90` | inter-module data bridging |
| **Graphics**            | `eq_graphics_stubs.f90`, `eqgsub.f90` | stubbed out in the library build |
| **Interactive menu**    | `eqmenu.f90` | only used by the `eqx2` CLI (unused in the library) |
| **Other**               | `eq-qst.f90`, `eqlib.f90`, `eqrppl.f90` | helper routines |

## F90 modernisation (F-1 through F-5)

The `eq/` tree contained a large body of F77 fixed-form sources and
`eqcom*.inc` INCLUDE files. Modernisation happened in stages, in
parallel with library-isation.

| Phase | PR | Content |
|---|---|---|
| F-1 | #71 | COMMON → `eqcom{0..3}_mod.f90` (shim kept in parallel) |
| F-2 | #79 | fixed-form → free-form (LOW tier) |
| F-3 | #81 | fixed-form → free-form (MED tier, 9 files) |
| F-4 | #87 | fixed-form → free-form (HIGH tier, 8 files) |
| F-5 | #93 | shim removed, `INCLUDE` fully replaced by `USE` |

After F-5, all `eq/` source is F90-only. Other modules can now reach
into `eqcom*_mod` directly via `USE`.

## Re-initialisation and the SAVE flag

`eq_finalize` explicitly calls `eq_bpsd_reset` to re-arm the
`eq_bpsd_init_flag` SAVE state in the `eqbpsd` module. Details:

- When the same process repeats `init` → `finalize` → `init`, the BPSD
  drawing descriptors must be re-zeroed in the second and subsequent
  cycles.
- Forgetting this brings back the suite-level SEGV (the
  `test_reinit_divergence` regression).
- See issue #110 / PR #163 for details.

## PIC build dependencies

`libeqapi.so` is statically linked against the following PIC archives:

```
libeqapi.so
├── lib/lib*_pic.a      (math / I/O utilities)
├── pl/libplcomm_pic.a  (plasma common modules)
├── mtxp/libmtxp_pic.a  (sparse-matrix solver — for Grad-Shafranov)
└── bpsd/libbpsd_pic.a  (BPSD data bridge)
```

Unlike `tr`, `eq` is itself the equilibrium solver, so it does not
depend on the eq PIC archive.

## References

- [`docs/eq-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/eq-library/architecture.md)
  — design notes at the repository root
- [Common Architecture](../../../portal/en/common/architecture.md) — the shared three-layer design across modules
- `eq/eq_api.h` — C ABI header
- `eq/eq_api.f90` — Fortran-side entry points
- `eq/eq_param_registry.f90` — `SELECT CASE` table for `set_param`
- `eq/eq_state.f90` — `TYPE` definitions of `eq_state_c` / `eq_diag_entry_c`
- `eq/eqcalq.f90` — body of the Grad-Shafranov solver
