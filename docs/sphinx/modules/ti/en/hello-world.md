# Minimal hello-world

```python
from tilib import Tilib

with Tilib() as ti:
    ti.set_params(RR=3.0, BB=3.0, NSMAX=2)  # (1) device geometry and species count
    ti.run(ntmax=10)                         # (2) advance 10 time steps
    state = ti.get_state()                   # (3) snapshot the state (TiState)
print(state.scalars["T"], state.scalars["residual_loop_max"])
```

## Line-by-line walkthrough

- **(1) `set_params`**: sets device geometry (`RR`, `BB`) and the species
  count (`NSMAX`) in one call. `ti` accepts the same namelist-style
  parameters as `tr`.
- **(2) `run(ntmax=10)`**: advances the simulation by 10 time steps.
  The step width defaults to `DT = 0.01 s`.
- **(3) `get_state()`**: copies the result into a `TiState` dataclass.
  See {doc}`state` for the full field list.

## Expected output

```
0.1  3.45e-08
```

For a complete runnable example see {doc}`quickstart`.

## Differences from `tr`

- **Physics scope**: `tr` is plain 1-D transport; `ti` is a full package
  that **integrates transport with auxiliary physics (neutral beams, RF
  heating, impurities, fusion)**.
- **Scalar outputs**: `tr` returns 14 scalars (`BETAN`, `TAUE`, …, `AJRFT`); `ti`
  returns **2 scalars + 2 iteration counters** (time and convergence
  diagnostics).
- **Profiles**: in `tr`, the species axis is the outer index
  (`RN[nr][ns]`); in `ti`, the active-species axis is used
  (`RNA[nr][nsa]`, with the species mapping handled internally).
- **Registered parameters**: `tr` has about 30; `ti` has **77** (because
  many auxiliary-physics modules can be toggled).
