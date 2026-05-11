# Fortran Design

The `tr` library is built by layering a thin C-ABI entry layer
(`tr_api.f90`) on top of the same physics kernel as the existing
`tr2` CLI version (`trloop.f90`, `trcalc.f90`, `trcoef_*.f90` and
roughly 64 other `.f90` source files), producing `libtrapi.so`. The
shared three-layer design is described in
[Common Architecture](../../../portal/en/common/architecture.md). This page
focuses on `tr`-specific aspects.

## Entry layer (`tr_api.f90`)

There are **7 functions** called from C: the standard 5 functions +
`tr_set_param_str` (for strings) + `tr_validate` (the pre-run
validation added in PR #172).

| C symbol | Fortran-side | LOC (approx) | Role |
|---|---|---|---|
| `tr_init`          | `tr_api_init`          | ~30 | `pl_init` → `eq_init` → `tr_init` (namelist defaults) → `ALLOCATE_TRCOMM` |
| `tr_set_param`     | `tr_api_set_param`     | ~15 | Delegates the input string to `tr_param_registry::tr_param_set` |
| `tr_set_param_str` | `tr_api_set_param_str` | ~10 | Same as above (string version) |
| `tr_run`           | `tr_api_run`           | ~30 | Calls `tr_prep` only on the first invocation, then `tr_loop(ntmax)`; `NTMAX` is saved/restored |
| `tr_get_state`     | `tr_api_get_state`     | ~40 | Copies the `TRCOMM` scalars and `RN/RT/AJ/QP` into the C struct |
| `tr_finalize`      | `tr_api_finalize`      | ~10 | `DEALLOCATE_TRCOMM` + reset of `g_*` flags |
| `tr_validate`      | `tr_api_validate`      | ~50 | Range checks for registered parameters + `KNAMEQ` file-existence check |

All are bound with `BIND(C, NAME="tr_xxx")` to fix the C ABI symbol
name. The Fortran-side names use the `tr_api_*` prefix to avoid a
symbol clash with the existing `SUBROUTINE tr_init` (`trinit.f90`).

### Mapping to the C struct layout

This corresponds 1:1 with `tr_state_t` defined in `tr/tr_api.h`:

```c
typedef struct {
    int    nt, nrmax, nsmax;
    double T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN;
    double TAUE1, TAUE2, ZEFF0, ALI, RQ1;
    double RN[TR_MAX_NRMAX][TR_MAX_NSMAX];   /* row-major in C */
    double RT[TR_MAX_NRMAX][TR_MAX_NSMAX];
    double AJ[TR_MAX_NRMAX];
    double QP[TR_MAX_NRMAX];
} tr_state_t;
```

`TR_MAX_NRMAX = 500` and `TR_MAX_NSMAX = 8` are compile-time
constants. Only the `nrmax` / `nsmax` slots actually populated are
meaningful; the rest is padding.

## Parameter registry (`tr_param_registry.f90`)

This is a **hand-coded `SELECT CASE` table** that maps external names
(strings such as `"RR"`, `"PN[1]"`, `"CDW[3]"`) to assignments to
TRCOMM variables.

```fortran
FUNCTION tr_param_set(name, value) RESULT(ierr)
  CHARACTER(LEN=*), INTENT(IN) :: name
  REAL(rkind),      INTENT(IN) :: value
  ! Handles subscripted names like name="PN[1]"
  CALL parse_array_subscript(name, base, idx)
  SELECT CASE (TRIM(base))
  CASE ("RR");   RR   = value
  CASE ("PN");   IF (idx<1 .OR. idx>SIZE(PN)) THEN; ierr=1; ELSE; PN(idx)=value; END IF
  ...
  CASE DEFAULT;  ierr = 1   ! unregistered name
  END SELECT
END FUNCTION
```

- **Array subscript handling**: a `parse_array_subscript` helper
  splits `"PN[1]"` into `base="PN"`, `idx=1`.
- **Bounds check**: out-of-range subscripts are rejected with
  `ierr=1` after comparing against `SIZE(arr)`.
- **Special guard for `NSMAX`**: `NSMAX=1` triggers a divide-by-zero
  in `tr_prof_impurity`, which would induce a Fortran-side `STOP` and
  abort the host process. The registry rejects values outside
  `[2, 8]` early
  (see comments at `tr_param_registry.f90:85-93`).

The full list of registered parameters is in {doc}`parameters`.

### Separate entry for string parameters

`CHARACTER(LEN=80)` variables such as `KNAMEQ` cannot ride the
`REAL(rkind)` pipeline, so a separate function `tr_param_set_str` is
provided. Currently only `KNAMEQ` is registered. Adding `KNAMEQ2`,
`KNAMTR`, and so on is a one-line addition to the `SELECT CASE`.

## Library-internal source layout

The roughly 64 `tr/*.f90` files break down by role:

| Group | Main files | Role |
|---|---|---|
| **API layer**           | `tr_api.f90`, `tr_param_registry.f90`, `tr_state.f90` | C ABI entry. Does not touch the physics kernel |
| **Main loop**           | `trmain.f90`, `trloop.f90`, `trexec.f90`, `trprep.f90` | Time-evolution conductor |
| **Model bodies**        | `trcalc.f90`, `trcoef*.f90`, `trcdbm.f90`, `tritg.f90`, `trmdlt.f90` | Physics models for transport / resistivity / diffusion |
| **Profiles**            | `trprof.f90`, `trprf.f90`, `trgrad.f90`, `trmetric.f90` | Initial profile generation, gradient computation |
| **Heating / CD**        | `trpnb.f90`, `trpnf.f90`, `trpel.f90`, `trpsc.f90` | NBI, fusion, pellet, sources |
| **Common modules**      | `trcomm.f90`, `trcomm_*.f90`, `trcom0.f90`, `trcom1.f90` | Global state (COMMON blocks turned into MODULEs) |
| **Result outputs**      | `trrslt_globals.f90`, `trrslt_files.f90`, `trrslt_print.f90` | Computes `TrState` scalars (`WPT`, `BETAN`, ...) |
| **UFILE I/O**           | `tr_ufile_*.f90`, `trufile.f90`, `trufsub.f90`, `tradat.f90` | Experimental data (UFILE) reader |
| **BPSD interop**        | `trbpsd*.f90` | Inter-module data bridge |
| **Graphics**            | `tr_graphics_stubs.f90`, `trg*.f90`, `trview.f90` | Stubbed in the library version |
| **Interactive menu**    | `trmenu.f90`, `trhelp.f90` | `tr2` CLI only (unused in the library version) |
| **Regression**          | `trregress.f90`, `tr_dump_state.f90` | Generates Phase 0 baseline outputs |
| **Subdirectories**      | `itg/`, `nclass/`, `cytran/`, `mbgb/`, `mmm95/`, `libmmm7_1/`, `glf/`, `adpost/` | External physics models (ITG, NCLASS, GLF23, mmm95, mmm7_1, ...) |

### Layers disabled in the library version

`tr_graphics_stubs.f90` overrides calls to PGPlot and other drawing
libraries with empty definitions. This lets `libtrapi.so` load and
run even in environments where graphics libraries are not installed.
Likewise the interactive menu (`trmenu.f90`) is linked but never
reached from the entry points.

## Where the scalar outputs (`TrState.scalars`) are computed

The 14 scalars returned by `tr_get_state` are all computed in
`trrslt_globals.f90::TR_CALC_GLOBAL` and stored in `TRCOMM` module
variables. Excerpt:

```fortran
! excerpt from trrslt_globals.f90
WPT   = WBULKT + WTAILT                                      ! stored energy [MJ]
AJT   = SUM(AJ(1:NRMAX)*DSRHO(1:NRMAX))*DR/1.D6              ! total current [MA]
BETA0 = (4.D0*BETA(1) - BETA(2))/3.D0                        ! axis β
BETAN = BETAA*1.D2/(RIP/(RA*BB))                             ! normalised β (Troyon)
TAUE1 = WPT/PINT                                             ! confinement time
TAUE2 = WPT/(PINT-WPDOT)                                     !   (steady-state corrected)
ALI   = 4.D0*WPOL/(RMU0*RR*(AJTTOR*1.D6)**2)                 ! internal inductance
ZEFF0 = (4.D0*ZEFF(1) - ZEFF(2))/3.D0                        ! axis Zeff
```

For physical meanings, see the table in {doc}`state`.

(reinit-constraints)=
## Re-initialisation constraints

If you repeat `tr_finalize` → `tr_init` in the same process, parts
of the module-level Fortran state are not fully reset (this is a
cross-module issue — see "Module-state reset" in
[Common Architecture](../../../portal/en/common/architecture.md)). For tests
that re-initialise, use `pytest --forked` to isolate by process, or
use `multiprocessing` to spawn a separate process.

## PIC build dependencies

`libtrapi.so` is statically linked against five PIC archives:

```
libtrapi.so
├── lib/lib*_pic.a      (math / I/O utilities)
├── pl/libplcomm_pic.a  (plasma common module)
├── eq/libeqcomm_pic.a  (equilibrium module — required when MODELG=3/9)
├── mtxp/libmtxp_pic.a  (sparse-matrix solver)
└── bpsd/libbpsd_pic.a  (BPSD data bridge)
```

Each `*_pic.a` is built in parallel with the regular `.a` (non-PIC,
for the `tr2` binary), so the library and existing CLI can coexist.

## References

- [`docs/tr-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/tr-library/architecture.md)
  — design notes at the repository root (more design rationale and
  per-phase records)
- [Common Architecture](../../../portal/en/common/architecture.md) — the
  cross-module 3-layer design
- `tr/tr_api.h` — C-ABI header (the `TR_MAX_NRMAX=500`,
  `TR_MAX_NSMAX=8` constants and the error enum)
- `tr/tr_api.f90` — Fortran-side entry points (7 functions)
- `tr/tr_param_registry.f90` — the `SELECT CASE` table used by
  `set_param`
- `tr/tr_state.f90` — `TYPE` definitions for `tr_state_c` /
  `tr_diag_entry_c`
- `tr/trrslt_globals.f90` — computation of the scalar quantities
