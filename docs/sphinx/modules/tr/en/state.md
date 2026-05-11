# Output Parameters and Physical Quantities (`TrState`)

`tr.get_state()` returns a `TrState` dataclass. This is the full list
of quantities you can read out as simulation results. Its fields
correspond 1-to-1 with the C struct `tr_state_t` in `tr/tr_api.h`.

## Dimension fields

```python
state.nt              # time-step counter
state.nrmax           # actual number of radial points (<= TR_MAX_NRMAX=500)
state.nsmax           # actual number of species (<= TR_MAX_NSMAX=8)
```

## Scalar quantities (14 entries, dictionary `state.scalars`)

Spatially / temporally integrated quantities that summarise the whole
plasma. The 14 entries below are always available.

| Key | Unit | Meaning |
|---|---|---|
| `T`       | s  | simulation time |
| `WPT`     | MJ | total stored plasma energy (`WBULKT + WTAILT`) |
| `AJT`     | MA | total plasma current (radial integral of `AJ`) |
| `Q0`      | — | safety factor on the magnetic axis |
| `BETA0`   | — | toroidal $\beta$ on the axis |
| `BETAP0`  | — | poloidal $\beta$ on the axis |
| `BETAA`   | — | toroidal $\beta$ on the separatrix |
| `BETAN`   | — | normalised $\beta_N$ (Troyon: $\beta_A \cdot 100 / (I_p / (aB))$) |
| `TAUE1`   | s | energy confinement time ($W_{PT}/P_{\mathrm{IN}}$) |
| `TAUE2`   | s | energy confinement time ($W_{PT}/(P_{\mathrm{IN}}-\dot{W})$, steady-state corrected) |
| `ZEFF0`   | — | effective charge $Z_\text{eff}$ on the axis |
| `ALI`     | — | plasma internal inductance $\ell_i$ |
| `RQ1`     | m | radius of the $q=1$ surface (or `RA` if there is none) |
| `AJRFT`   | MA | total RF + external-driven current (L-7b-i) |

Access example:

```python
state.scalars["T"]       # current time
state.scalars["WPT"]     # stored energy
state.scalars["BETAN"]   # Troyon β
state.scalars["TAUE1"]   # τ_E
```

## Profile quantities (radial profiles)

Radial-direction profiles. Two-dimensional fields are indexed as
`[radius_index][species_index]` in C row-major order (see the common
architecture chapter).

```python
state.RN[nr][ns]      # density profile [10^20 m^-3]
state.RT[nr][ns]      # temperature profile [keV]
state.AJ[nr]          # current-density profile [MA/m^2]
state.QP[nr]          # safety-factor profile
```

Indices are 0-origin (Python convention). For example, the boundary
electron temperature is `state.RT[state.nrmax-1][0]`.

## Helper methods

```python
state.to_dict()       # JSON-ready dict (Phase 0 baseline compatible)
```

For the full attribute list, see the `TrState` autodoc in
{doc}`api-reference`.
