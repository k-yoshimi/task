# Output Parameters and Physical Quantities (`FpState`)

`fp.get_state()` returns an `FpState` dataclass. `fp` does not return
the distribution function $f(r, p, \theta)$ itself — it exposes only
**moment quantities** (integrated physical quantities).

## Dimension fields

| Field | Meaning |
|---|---|
| `state.nrmax`  | Number of radial mesh points in the profile arrays: once a run has allocated them, the lesser of the current `NRMAX` and that allocation (a raised `NRMAX` applies from the next run); before the first run, `NRMAX` itself with zero profiles |
| `state.nsamax` | Number of active species (those whose distribution functions were solved) in the profile arrays: the lesser of the current `NSAMAX` and the allocation, likewise |
| `state.npmax`  | Number of momentum mesh points |
| `state.nthmax` | Number of pitch-angle mesh points |
| `state.ntg2`   | Long-time-axis counter |

## Scalar quantities

The simulation time is a top-level field, and `state.scalars` is a dict
of **seven global quantities**: six volume-integrated diagnostics, each
summed over the active species at the latest global-diagnostic sample
(`NTG1`), and the plasma volume (`TVOLR`, the sum of the radial cell
volumes):

```python
state.timefp                      # simulation time [s]
state.scalars["TOTAL_IP"]         # total plasma current [MA]
```

| Key of `state.scalars` | Quantity | Unit |
|---|---|---|
| `TOTAL_IP`         | Total plasma current | MA |
| `STORED_ENERGY`    | Stored energy | MJ |
| `COLLISION_POWER`  | Total collisional power | MW |
| `ABSORPTION_POWER` | Total absorbed wave power | MW |
| `ABSORPTION_WR`    | Ray-tracing (WR) part of the absorbed power | MW |
| `ABSORPTION_WM`    | Full-wave (WM) part of the absorbed power | MW |
| `PLASMA_VOLUME`    | Plasma volume | m³ |

All seven are zero until the first `run()`, and again after a
`set_param` until the next `run()` that is made, while the profiles are
still those of the last run. Unlike the per-unit-volume profiles
below, they depend on the equilibrium through the volume element. `fp`
still does not carry the plasma-performance scalars of `tr`/`eq`:
derived quantities (`BETA`, `TAUE`, etc.) are left to user-side
post-processing.

## Profile quantities (radial × species moment arrays)

The main `fp` outputs. Each is a **2D array of shape `[nsamax][nrmax]`**
that gives the radial profile per active species.

| Field | Quantity | Unit |
|---|---|---|
| `state.RNT[isa][nr]`  | Particle-number density (zeroth moment of $f$) | 10²⁰ m⁻³ |
| `state.RWT[isa][nr]`  | Energy density (second moment) | MJ/m³ |
| `state.RTT[isa][nr]`  | Average temperature (from `RWT/RNT`) | keV |
| `state.RJT[isa][nr]`  | Current density (first moment, pitch-angle weighted) | MA/m² |
| `state.RPCT[isa][nr]` | Collisional power exchange | MW/m³ |
| `state.RPWT[isa][nr]` | Wave-heating power exchange | MW/m³ |

```python
state.RNT[0][0]      # on-axis density of active species 0
state.RTT[0]         # full temperature profile of active species 0
state.RJT[1]         # current-density profile of active species 1
```

## Accessing the 5D distribution function

`FpState` **does not include the distribution function itself**. A 5D
grid would not serialise sensibly to JSON. If you need it:

1. Use additional fields in the `FpStateC` C-ABI struct
   (implementation-dependent).
2. Or: build your analysis from the moment quantities (RNT, RWT, RJT).
3. Or: wait for a separate API such as
   `fp_get_distribution(species, ir)` (planned).

## Helper methods

```python
state.to_dict()   # JSON-ready dict
```

For the full attribute list, see the `FpState` autodoc in
{doc}`api-reference`.

## Differences from `tr`/`ti` State

| | `TrState` (tr) | `TiState` (ti) | `FpState` (fp) |
|---|---|---|---|
| **Species axis** | NSMAX | active NSA_MAX | active NSAMAX |
| **Phase space** | 1D radial | 1D radial | **5D** (r, p, θ, species, t) |
| **Number of scalars** | 13 | 2 + 2int | **7** global (+ `timefp`) |
| **Main outputs** | RN, RT, AJ, QP | RNA, RTA, RUA, RBP, ZEFF, BETA | RNT, RWT, RTT, RJT, RPCT, RPWT |
| **Meaning** | Fluid moments | Integrated-transport moments | Distribution-function moments |
| **Memory cost** | Low | Medium | **High** (5D) |
