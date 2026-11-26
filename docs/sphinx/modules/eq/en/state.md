# Output Parameters and Physical Quantities (`EqState`)

`eq.get_state()` returns an `EqState` dataclass. This is the full list
of quantities you can retrieve as the result of an equilibrium
calculation. The fields correspond to the C structure `eq_state_t`
declared in `eq/eq_api.h`.

## Dimension fields

| Field | Meaning |
|---|---|
| `state.nrgmax`  | actual number of R grid points |
| `state.nzgmax`  | actual number of Z grid points |
| `state.npsmax`  | actual number of ψ-surface samples |
| `state.nrmax`   | radial points of the ψ mesh |
| `state.nthmax`  | poloidal points of the ψ mesh |
| `state.nsumax`  | number of boundary points |
| `state.nrvmax`  | radial points of the volume grid (`MODELG=3` only) |

## Scalar quantities (12 entries, `state.scalars` dict)

The most representative scalars summarising the equilibrium solution.
Each one captures the whole plasma in a single number.

| Key | Unit | Meaning |
|---|---|---|
| `raxis`  | m | R-coordinate of the magnetic axis |
| `zaxis`  | m | Z-coordinate of the magnetic axis |
| `psi0`   | Wb/rad | ψ at the magnetic axis |
| `psipa`  | Wb/rad | ψ_p (poloidal flux) at the plasma surface |
| `psita`  | Wb/rad | ψ_t (toroidal flux) at the plasma surface |
| `qaxis`  | — | safety factor $q$ at the magnetic axis |
| `qsurf`  | — | safety factor $q$ at the plasma surface |
| `betat`  | — | toroidal $\beta$ |
| `betap`  | — | poloidal $\beta$ |
| `pvol`   | m³ | plasma volume |
| `raave`  | m | volume-averaged minor radius |
| `ripx`   | MA | total plasma current obtained by the solver |

Example:

```python
state.scalars["raxis"]   # R of the magnetic axis
state.scalars["qaxis"]   # central q
state.scalars["betat"]   # toroidal β
state.scalars["pvol"]    # plasma volume
```

```{note}
`ripx` (output) and `RIP` (input) are independent: `ripx` is the total
current obtained by the solver, and `RIP` is the target value you
supplied. If the two do not roughly agree, the equilibrium may not
have converged.
```

## Grid and profile quantities

### R-Z coordinates

```python
state.rg   # [nrgmax] R-axis coordinate
state.zg   # [nzgmax] Z-axis coordinate
```

These are uniformly spaced Cartesian coordinates and represent the
sample points of `psirz` (the ψ values on the R-Z grid).

### ψ-surface profiles

One value per ψ surface (magnetic surface). 1-D arrays of length
`state.npsmax`.

```python
state.psips   # [npsmax] ψ value of each magnetic surface
state.ppps    # [npsmax] pressure profile p(ψ)
state.ttps    # [npsmax] T(ψ) = 2π · R · B_φ
state.qqps    # [npsmax] safety-factor profile q(ψ)
```

Plotting `state.psips` on the x-axis and the others on the y-axis
shows the **per-surface distribution of physical quantities**.

```python
import matplotlib.pyplot as plt
plt.plot(state.psips, state.qqps)
plt.xlabel("ψ")
plt.ylabel("q")
plt.title("Safety factor profile")
```

## Helper methods

```python
state.to_dict()   # JSON-ready dict, compatible with the Phase 0 baseline
```

For the complete attribute list, see the `EqState` autodoc in
{doc}`api-reference`.

## Differences from `tr`'s `TrState`

| | `TrState` (tr) | `EqState` (eq) |
|---|---|---|
| **Dimensions** | `nrmax` × `nsmax` (species) | `nrgmax` × `nzgmax` (R-Z grid) + `npsmax` (ψ surfaces) |
| **Time** | has `nt` (time-step counter) | no time concept |
| **Scalars** | 13 (`T`, `WPT`, `BETAN`, …) | 12 (`raxis`, `qaxis`, `betat`, …) |
| **Main quantities** | density / temperature / current / q profiles | ψ-surface geometry + p, T, q |

`eq` does not advance time — it only "solves the equilibrium for the
given conditions" — so the output corresponds to a **single-time
snapshot**.
