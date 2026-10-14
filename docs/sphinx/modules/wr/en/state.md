# Output Parameters and Physical Quantities (`WrState`)

`wr.get_state()` returns a `WrState` dataclass. This is the complete
list of quantities you can read from a ray-tracing run.

## Dimension fields

| Field | Meaning |
|---|---|
| `state.nraymax` | actual number of rays traced |
| `state.nrsmax`  | radial (minor radius) profile points |
| `state.nrlmax`  | major-radius profile points |

## Scalar quantities (4, in `state.scalars`)

The main `wr` outputs: location and value of the peak power across all
rays.

| Key | Unit | Meaning |
|---|---|---|
| `pos_pwrmax_rs` | m | peak-power position in the minor-radius profile |
| `pwrmax_rs`     | -- | the peak value |
| `pos_pwrmax_rl` | m | peak-power position in the major-radius profile |
| `pwrmax_rl`     | -- | the peak value |

```python
state.scalars["pos_pwrmax_rs"]   # peak position in minor radius
state.scalars["pwrmax_rs"]       # value
state.scalars["pos_pwrmax_rl"]   # peak position in major radius
state.scalars["pwrmax_rl"]       # value
```

A typical use to inspect the ECRH/ECCD power-deposition position:

```python
print(f"ECRH deposition: r/a ≈ {state.scalars['pos_pwrmax_rs']/RA:.2f}")
```

## Per-ray termination data

For each ray, where it ended and where its peak power was. Array indices
are 0-origin (Python convention).

| Field | Type | Meaning |
|---|---|---|
| `state.nstp_end[i]`           | int   | terminating step number of ray i |
| `state.pos_pwrmax_rs_nray[i]` | float | peak position (rs) of ray i |
| `state.pwrmax_rs_nray[i]`     | float | the peak value |
| `state.pos_pwrmax_rl_nray[i]` | float | peak position (rl) of ray i |
| `state.pwrmax_rl_nray[i]`     | float | the peak value |
| `state.rays_end[i][k]`        | float | the k-th physical quantity at termination of ray i (`NRAY_EQ` total) |

`rays_end[i]` carries the position, wave-vector and power at termination
(the ray-equation variables).

## Profile quantities (radial profiles)

Radial distribution of absorbed power (sum over all rays).

```python
state.pos_nrs[k]   # k-th minor-radius sample position [m]
state.pwr_nrs[k]   # power-deposition density at that position
state.pos_nrl[k]   # k-th major-radius sample position [m]
state.pwr_nrl[k]   # power-deposition density at that position
```

Visualisation example:

```python
import matplotlib.pyplot as plt
plt.plot(state.pos_nrs, state.pwr_nrs, label="rs profile")
plt.plot(state.pos_nrl, state.pwr_nrl, label="rl profile")
plt.xlabel("R [m]")
plt.ylabel("Absorbed power")
plt.legend()
```

## Helper methods

```python
state.to_dict()   # JSON-ready dict
```

For the complete attribute list see the `WrState` autodoc in
{doc}`api-reference`.

## Differences from `tr` / `fp` State

| | `TrState` (tr) | `FpState` (fp) | `WrState` (wr) |
|---|---|---|---|
| **Time** | yes (`nt`) | yes (`timefp`) | **no** (spatial integration) |
| **Dimensions** | radius × species | 5D phase space (moments) | **rays × steps** + radial profiles |
| **Scalars** | 13 (T, BETAN, ...) | 7 global (+ `timefp`) | **4** (peak position + value) |
| **Main output** | profiles | moments | **ray trajectories + absorption profile** |
| **Physical units** | fluid quantities | distribution-function moments | RF power deposition |
