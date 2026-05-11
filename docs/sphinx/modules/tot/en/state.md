# Output Parameters and Physical Quantities (`TotState`)

`tot.get_state()` returns a `TotState` dataclass. Its layout is
**`TrState` extended with sub-module presence flags**.

## Sub-module presence flags

These 0/1 flags tell you whether each sub-module was successfully
initialised.

| Field | Meaning |
|---|---|
| `state.tr_present`  | 1 if TR is loaded |
| `state.ti_present`  | 1 if TI is loaded |
| `state.fp_present`  | 1 if FP is loaded |
| `state.wr_present`  | 1 if WR is loaded |

Normally all are 1. Trying to set a parameter for a module whose flag is
0 raises an error.

## Dimension fields

| Field | Meaning |
|---|---|
| `state.nt`     | Time-step counter (sourced from TR) |
| `state.nrmax`  | Number of radial grid points (sourced from TR) |
| `state.nsmax`  | Number of species (sourced from TR) |

```{note}
These dimensions come **from the TR module**. Profiles from eq/fp/wr or
the other modules are not accessible — use the stand-alone module if
you need them.
```

## Scalars (14 entries, the `state.scalars` dict)

These are **exactly the same** 14 scalars as in `TrState`. They are
representative quantities for the whole plasma.

| Key | Unit | Meaning |
|---|---|---|
| `T`       | s  | Simulation time |
| `WPT`     | MJ | Total stored plasma energy |
| `AJT`     | MA | Total plasma current |
| `Q0`      | — | Safety factor on the magnetic axis |
| `BETA0`   | — | Toroidal $\beta$ on axis |
| `BETAP0`  | — | Poloidal $\beta$ on axis |
| `BETAA`   | — | Toroidal $\beta$ at the separatrix |
| `BETAN`   | — | Normalised $\beta_N$ |
| `TAUE1`   | s | Energy confinement time |
| `TAUE2`   | s | Energy confinement time (steady-state-corrected) |
| `ZEFF0`   | — | Effective charge on axis |
| `ALI`     | — | Plasma internal inductance |
| `RQ1`     | m | Radius of the $q=1$ surface |
| `AJRFT`   | MA | Total RF + external-driven current (L-7b-i) |

For the physical meaning and exact formulas, see the `tr` module's state
page (`docs/sphinx/modules/tr/en/state.md`).

```python
state.scalars["T"]
state.scalars["BETAN"]
```

## Profile quantities (radial profiles)

Same as `TrState`: the radial profiles from `tr` are returned.

```python
state.RN[nr][ns]      # density profile [10^20 m^-3]
state.RT[nr][ns]      # temperature profile [keV]
state.AJ[nr]          # current-density profile [MA/m^2]
state.QP[nr]          # safety-factor profile
```

After `tr` has run, you obtain the **most recent values**, which already
reflect the influence of eq, ti, fp, and wr.

## Helper methods

```python
state.to_dict()       # JSON-ready dict
```

For the complete attribute list, see the `TotState` autodoc in
{doc}`api-reference`.

## When you need sub-module-specific outputs

`TotState` only contains **TR data + presence flags**. For example:

- eq's `raxis`, `qaxis`, etc. are not exposed
- fp's `RJT`, `RWT`, etc. are not exposed
- wr's `pwr_nrs[]` profile is not exposed

If you need these, run the **stand-alone module** (`Eq`, `Fplib`,
`Wrlib`) instead of `Tot`, or wait for an extension of the `Tot` API.

## Relationship to `TrState`

| | `TrState` (tr alone) | `TotState` (tot integrated) |
|---|---|---|
| **Dimensions** | nt, nrmax, nsmax | + tr_present, ti_present, fp_present, wr_present |
| **Scalars** | 14 | 14 (same set) |
| **Profiles** | RN, RT, AJ, QP | RN, RT, AJ, QP (same) |
| **Source** | tr alone | tr (with eq/ti/fp/wr influence applied) |
