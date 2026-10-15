# Registered Input Parameters

`eq/eq_param_registry.f90` registers a total of 94 entries (≈78 numeric
scalars, 5 array families, 7 strings). The names match the Fortran
`/EQ/` namelist. Default values are set in `eq/eqinit.f90::EQINIT`.

## Required and recommended parameters

Most parameters have defaults, so a minimal call to `run()` works
without any explicit setting. However, some parameters become
**required under specific conditions**, and others **should be
overridden** to obtain physically meaningful results.

### Required (conditional)

| Condition | Required parameter | Reason |
|---|---|---|
| `MODELG ∈ {3, 5, 8}` | **`KNAMEQ`** (string) | Equilibrium-data filename. If unset, `validate()` returns a `FILE_MISSING` diagnostic and `run()` produces an invalid equilibrium. |

```python
eq.set_param("MODELG", 3)
eq.set_param_str("KNAMEQ", "eqdata.ITER01")
```

With `MODELG=2` (analytic toroidal geometry, the default) `KNAMEQ` is
unused, so **strictly speaking nothing is required**.

### Strongly recommended (defaults are too generic)

The defaults assume a generic, small tokamak placeholder. If you have
a specific device in mind, override these explicitly.

| Name | Default | Suggested override (ITER) |
|---|---|---|
| `RR`     | 3.0 m  | 6.2 m |
| `RA`     | 1.0 m  | 2.0 m |
| `BB`     | 3.0 T  | 5.3 T |
| `RIP`    | 3.0 MA | 15.0 MA |
| `RKAP`   | 1.0    | 1.7 |
| `RDLT`   | 0.0    | 0.5 |

### Grid sizes (defaults usually fine)

| Name | Default | Upper bound |
|---|---|---|
| `NSGMAX` (Grad-Shafranov radial) | 32 | compile-time max |
| `NRGMAX` (R-Z transverse mesh) | 33 | same |
| `NPSMAX` (ψ-surface samples) | 21 | same |
| `NRMAX` (flux-coordinate radial) | 50 | same |
| `NTHMAX` (poloidal) | 64 | same |

`validate()` detects compile-time-max overflow up-front as
`OUT_OF_RANGE` diagnostics.

### Recommended workflow

```python
from eqlib import Eq, EqDiagCode

with Eq() as eq:
    # 1. Things you should always set
    eq.set_params(RR=6.2, RA=2.0, BB=5.3, RIP=15.0,
                  RKAP=1.7, RDLT=0.5)

    # 2. With MODELG=3, KNAMEQ is required
    eq.set_param("MODELG", 3)
    eq.set_param_str("KNAMEQ", "eqdata.ITER01")

    # 3. Validate before run
    diags = eq.validate()
    for d in diags:
        print(f"[{EqDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    eq.run()  # mode=1
    state = eq.get_state()
```

---

## 1. Geometry / device

The plasma's spatial shape and field strength. `RR`, `RA`, `BB`,
and `RIP` are the four most important.

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `RR`    | double | 3.0 | m | plasma major radius |
| `RA`    | double | 1.0 | m | plasma minor radius |
| `RB`    | double | 1.2 | m | wall minor radius |
| `RKAP`  | double | 1.0 | — | elongation |
| `RDLT`  | double | 0.0 | — | triangularity |
| `BB`    | double | 3.0 | T | central toroidal field |
| `RIP`   | double | 3.0 | MA | plasma current |
| `FRBIN` | double | 1.0 | — | $(R_{B,\text{in}} - R_A) / (R_{B,\text{out}} - R_A)$ |

## 2. Safety factor

| Name | Type | Default | Meaning |
|---|---|---|---|
| `Q0`     | double | 1.0 | central $q$ |
| `QA`     | double | 3.0 | surface $q$ |
| `QMIN`   | double | 1.5 | minimum $q$ for reversed shear |
| `RHOMIN` | double | 0.0 | location of minimum $q$ (normalised radius; 0 for normal shear) |
| `RHOEDG` | double | 1.0 | onset of edge smoothing (1 means no smoothing) |

## 3. Pressure profile

$$p(\psi) = P_{P0}(1-\psi^{P_{R0}})^{P_{PROFP0}} + P_{P1}(1-\psi^{P_{R1}})^{P_{PROFP1}} + P_{P2}\,(\text{ITB interior only})$$

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `PP0`     | double | 0.001 | MPa | main amplitude |
| `PP1`     | double | 0.0   | MPa | secondary |
| `PP2`     | double | 0.0   | MPa | ITB-interior addition |
| `PROFP0`  | double | 1.5   | — | main exponent |
| `PROFP1`  | double | 1.5   | — | secondary exponent |
| `PROFP2`  | double | 2.0   | — | ITB exponent |

## 4. Current profile

| Name | Type | Default | Meaning |
|---|---|---|---|
| `PJ0`     | double | 1.0 | central current density (main) |
| `PJ1`     | double | 0.0 | secondary |
| `PJ2`     | double | 0.0 | ITB component |
| `PROFJ0`  | double | 1.5 | main exponent |
| `PROFJ1`  | double | 1.5 | secondary exponent |
| `PROFJ2`  | double | 1.5 | ITB exponent |

## 5. $F(\psi)$ function (toroidal flux function)

$$F(\psi) = B_T R + \mathrm{FF}_0 (1-\psi^{P_{R0}})^{P_{F0}} + \cdots$$

| Name | Type | Default | Meaning |
|---|---|---|---|
| `FF0`     | double | 1.0 | main amplitude |
| `FF1`     | double | 0.0 | secondary |
| `FF2`     | double | 0.0 | ITB component |
| `PROFF0`  | double | 1.5 | main exponent |
| `PROFF1`  | double | 1.5 | secondary exponent |
| `PROFF2`  | double | 1.5 | ITB exponent |

## 6. Temperature / density

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `PT0`      | double | 1.0  | keV | central temperature |
| `PT1`      | double | 0.0  | keV | secondary |
| `PT2`      | double | 0.0  | keV | ITB component |
| `PTSEQ`    | double | 0.05 | keV | edge temperature |
| `PROFTP0`  | double | 1.5  | — | main exponent |
| `PROFTP1`  | double | 1.5  | — | secondary exponent |
| `PROFTP2`  | double | 2.0  | — | ITB exponent |
| `PN0EQ`    | double | 1.0×10²⁰ | m⁻³ | central number density (constant) |

## 7. Toroidal rotation (velocity profile)

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `PV0`     | double | 0.0 | m/s | main |
| `PV1`     | double | 0.0 | m/s | secondary |
| `PV2`     | double | 0.0 | m/s | ITB component |
| `PROFV0`  | double | 1.5 | — | main exponent |
| `PROFV1`  | double | 1.5 | — | secondary exponent |
| `PROFV2`  | double | 2.0 | — | ITB exponent |

## 8. Radial profile shape

| Name | Type | Default | Meaning |
|---|---|---|---|
| `PROFR0` | double | 1.0 | radial-base exponent (main) |
| `PROFR1` | double | 2.0 | radial-base exponent (secondary) |
| `PROFR2` | double | 2.0 | radial-base exponent (ITB) |

## 9. Grid dimensions

These are checked against the compile-time maxima by `validate()`.

| Name | Type | Default | Purpose |
|---|---|---|---|
| `NSGMAX` | int | 32  | Grad-Shafranov radial mesh |
| `NTGMAX` | int | 32  | Grad-Shafranov poloidal mesh |
| `NUGMAX` | int | 32  | radial mesh for flux-surface averages |
| `NRGMAX` | int | 33  | R-axis grid in the R-Z plane |
| `NZGMAX` | int | 33  | Z-axis grid in the R-Z plane |
| `NPSMAX` | int | 21  | number of ψ-surface samples |
| `NRMAX`  | int | 50  | radial mesh in flux coordinates |
| `NTHMAX` | int | 64  | poloidal mesh in flux coordinates |
| `NSUMAX` | int | 65  | number of boundary points |
| `NRVMAX` | int | 50  | radial mesh for surface averaging |
| `NTVMAX` | int | 400 | poloidal mesh for surface averaging |
| `NPFCMAX` | int | 0  | number of PF coils |

## 10. Iteration / convergence

| Name | Type | Default | Meaning |
|---|---|---|---|
| `EPSEQ`  | double | 1×10⁻⁶ | convergence tolerance for equilibrium iteration |
| `NLPMAX` | int    | 100    | maximum number of equilibrium iterations |
| `EPSNW`  | double | 1×10⁻² | Newton-method convergence tolerance |
| `DELNW`  | double | 1×10⁻² | derivative step size for Newton method |
| `NLPNW`  | int    | 20     | maximum Newton iterations |

## 11. Mode switches

`MODELG` (geometry model) is the most important.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `MODELG` | int switch | 2 | geometry-model selector |
| `MODELN` | int switch | 0 | plasma-profile source |
| `MODELQ` | int switch | 0 | $q$-profile control (for `MODELG=0,1,2`) |
| `MDLEQF` | int switch | 0 | which profiles to supply |
| `MDLEQA` | int switch | 0 | choice of $\rho$ |
| `MDLEQC` | int switch | 0 | poloidal-coordinate selector |
| `MDLEQX` | int switch | 0 | free-boundary calculation method |
| `MDLEQV` | int switch | 3 | $\psi$-extrapolation order in vacuum |
| `NPRINT` | int switch | 0 | output verbosity |
| `IDEBUG` | int switch | 0 | debug output flag |
| `MODEFR` | int switch | 0 | (internal) |
| `MODEFW` | int switch | 0 | (internal) |

Allowed values of `MODELG`:

| Value | Behaviour |
|---|---|
| 0 | slab geometry |
| 1 | cylindrical geometry |
| 2 (default) | toroidal geometry (analytic) |
| 3 | TASK/EQ output-file path (requires `KNAMEQ`) |
| 4 | VMEC output path |
| 5 | EQDSK file path (requires `KNAMEQ`) |
| 6 | Boozer-coordinate output |
| 8 | (TASK-internal path; requires `KNAMEQ`) |

Allowed values of `MDLEQF`:

| Value | Profiles supplied |
|---|---|
| 0 (default) | $P, J_\text{tor}, T, V_\varphi$ + $I_p$ (analytic) |
| 1 | $P, F$ + $I_p$ (analytic) |
| 2 | $P, J_\parallel$ + $I_p$ (analytic) |
| 3 | $P, J_\parallel$ (analytic) |
| 4 | $P, q$ (analytic) |
| 5–9 | spline versions of 0–4 |

## 12. Computation domain / limiters

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `RGMIN` | double | 1.5  | m | minimum R of the computation domain |
| `RGMAX` | double | 4.5  | m | maximum R of the computation domain |
| `ZGMIN` | double | -2.0 | m | minimum Z of the computation domain |
| `ZGMAX` | double | 2.0  | m | maximum Z of the computation domain |
| `ZLIMP` | double | 2.5  | m | upper X-point Z |
| `ZLIMM` | double | -2.5 | m | lower X-point Z |

## 13. ψ boundary (`PSIB` — **0-origin**)

Multipole-expansion coefficients of the boundary poloidal flux ψ.
This is a 0-origin array.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `PSIB[0]` | double | 2.0 | order 0 (constant) |
| `PSIB[1]` | double | 0.5 | order 1 |
| `PSIB[2]` | double | 0.0 | order 2 |
| `PSIB[3]` | double | 0.0 | order 3 |
| `PSIB[4]` | double | 0.0 | order 4 |
| `PSIB[5]` | double | 0.0 | order 5 |

```{warning}
The other 1-D arrays (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) are 1-origin.
`PSIB` is the only one that follows the Fortran declaration
`PSIB(0:5)` because counting from $\psi = 0$ (the magnetic axis) is
the physically natural choice (see {doc}`faq` Q1).
```

## 14. PF coils (`RIPFC`, `RPFC`, `ZPFC`, `WPFC` — 1-origin)

| Name | Type | Default | Unit | Meaning |
|---|---|---|---|---|
| `RIPFC[i]` | double[NPFCM] | 0.0   | MA | i-th coil current |
| `RPFC[i]`  | double[NPFCM] | 3.0   | m  | i-th coil R position |
| `ZPFC[i]`  | double[NPFCM] | -1.75 | m  | i-th coil Z position |
| `WPFC[i]`  | double[NPFCM] | 0.75  | m  | i-th coil width |

`NPFCMAX` (default 0) controls how many coils are active.

## 15. Strings (use `set_param_str`)

| Name | Type | Default | Meaning |
|---|---|---|---|
| `KNAMEQ`  | CHARACTER(80) | `'eqdata'`  | equilibrium-data file (required for `MODELG=3,5,8`) |
| `KNAMEQ2` | CHARACTER(80) | `'eqdata2'` | additional equilibrium data |
| `KNAMWR`  | CHARACTER(80) | `'wrdata'`  | ray-tracing data |
| `KNAMWM`  | CHARACTER(80) | `'wmdata'`  | full-wave data |
| `KNAMFP`  | CHARACTER(80) | `'fpdata'`  | Fokker-Planck data |
| `KNAMFO`  | CHARACTER(80) | `'fodata'`  | file output |
| `KNAMPF`  | CHARACTER(80) | `'pfdata'`  | profile data |

String parameters **cannot be passed through `set_param`**. Use
`set_param_str` (see {doc}`parameter-setting`, method C).
