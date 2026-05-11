# Library application examples (Python wrapper)

`Tot` is the orchestrator that brings up the other 5 modules
(eq / tr / ti / fp / wr) inside a single process. This page shows three
typical patterns.

```{admonition} L-6 stage limitation
:class: warning

The current `Tot` (Phase L-6) **only actually time-evolves the transport
part (TR)**. `eq` / `ti` / `fp` / `wr` are initialized inside the same
process, but `tot.run()` does not invoke their calculations. In other
words:

- Namespaced settings such as `tot.set_param("eq:RR", 6.5)` are
  **distributed to all 5 modules**.
- `tot.run(ntmax)` **only calls `tr_api_run(ntmax)`**.
- `tot.get_state()` returns the **aggregated TR state**
  (`state.tr_present == 1`, `state.ti_present == 0`, ...).

Cross-module coupling for `fp` -> `tr` (driven current scalar) is now
implemented in L-7a as `TotPipeline` (see §3 below). Profile-level
coupling such as `wr` -> `tr` (wave heating deposition profile) and
`eq` -> `tr` (q-profile) is scheduled for L-7b and beyond via the
BPSD broker.
```

```{admonition} About this page
:class: note

What is shown here are **application patterns for using `totlib` from
Python**. For scenarios where an LLM client drives it via natural
language, see {doc}`mcp`.
```

---

## 1. Integrated init + namespaced setup

`Tot()` brings up four sub-modules (tr / ti / fp / wr) in a single
`__init__` call. Parameters for each module are distinguished by a
`<ns>:<name>`-style prefix:

```python
from totlib import Tot


with Tot() as tot:
    # Set the eq geometry (distributed to each sub-module)
    tot.set_param("eq:RR", 6.2)
    tot.set_param("eq:RA", 2.0)
    tot.set_param("eq:BB", 5.3)
    tot.set_param("eq:RIP", 15.0)

    # tr transport configuration
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("tr:DT", 0.01)
    tot.set_param("tr:NTMAX", 100)

    # Advance just one step and check the state
    tot.run(1)
    state = tot.get_state()
    print(f"tr_present={state.tr_present}, T={state.scalars['T']:.3f}s")
```

Expected output:

```text
tr_present=1, T=0.010s
```

Available prefixes:

| Prefix | Module | Notes |
|---|---|---|
| `eq:` | equilibrium | Geometry shared between analytic / EQDSK |
| `tr:` | transport | 1D diffusion equation |
| `ti:` | ion transport | Heavy-ion transport (only when used) |
| `fp:` | Fokker-Planck | Velocity-space distribution |
| `wr:` / `wrx:` | ray tracing | Wave propagation |

Per-namespace definitions can be enumerated via `describe_parameters` on
each module's MCP (see {doc}`mcp`).

### Possible extensions

- Bundle device presets (ITER / JET / DIIID) into a single dict and
  expand them in one shot via `_apply_namespaced(tot, preset)`
- If feeding the same `RR/RA/BB` to eq, tr, and wr feels redundant,
  build a `geometry_from(preset)` helper that expands them

---

## 2. Wrapping the transport advance

At the L-6 stage, `tot.run(ntmax)` advances **only the TR transport
calculation** for ntmax steps. The failure-handling pattern matches
`StableTrRunner` in the tr module's applications page
(`docs/sphinx/modules/tr/en/applications.md`).

```python
from totlib import Tot
from totlib.errors import TotlibCalculationFailedError


def transport_step(tot: Tot, *, ntmax: int = 100) -> dict:
    """Advance transport via tot and return the main scalars."""
    try:
        tot.run(ntmax)
        state = tot.get_state()
        return {
            "tr_present": bool(state.tr_present),
            "T":     state.scalars["T"],
            "WPT":   state.scalars["WPT"],
            "BETAN": state.scalars["BETAN"],
            "TAUE1": state.scalars["TAUE1"],
            "Q0":    state.scalars["Q0"],
        }
    except TotlibCalculationFailedError as e:
        return {"error": repr(e)}


with Tot() as tot:
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("tr:DT", 0.01)
    tot.set_param("tr:NTMAX", 100)
    out = transport_step(tot, ntmax=10)
    for k, v in out.items():
        if isinstance(v, float):
            print(f"  {k} = {v:.4g}")
        else:
            print(f"  {k} = {v}")
```

Expected output:

```text
  tr_present = True
  T = 0.1
  WPT = 10.01
  BETAN = 0.2872
  TAUE1 = 11.42
  Q0 = 2.519
```

### Possible extensions

- Extend the wrapper to return all 14 entries of `state.scalars`
  (`T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN, TAUE1, TAUE2, ZEFF0,
  ALI, RQ1, AJRFT`)
- Accumulate `state.scalars` into a list at every ntmax for time-series
  analysis

---

## 3. Multi-module coupling pipeline (L-7a)

L-7a introduces `TotPipeline`, a Python-side orchestrator that composes
existing per-module wrappers (`Fplib`, `Trlib`, ...) with hardcoded
scalar coupling rules. It does not use `libtotapi.so`; the legacy `Tot`
class above continues to handle that path.

```python
from totlib import TotPipeline

with TotPipeline() as tot:
    # fp side fixture (active drive)
    tot.set_param("fp:NSAMAX", 2)
    tot.set_param("fp:E0", 0.001)        # induction E-field [V/m]

    # tr side fixture (compute_rjt_volint reads tr:RR / tr:RA)
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)

    result = tot.run_pipeline([
        ("fp", {"ntmax": 5}),
        ("tr", {"ntmax": 1}),
    ])
    tr_scalars = result.last("tr").scalars
    print(f"AJT={tr_scalars['AJT']}, coupling={result.last('tr').coupling_applied}")
```

`run_pipeline` automatically applies `COUPLING_RULES` between adjacent
steps. L-7a registers exactly one rule:
`fp -> tr`'s `compute_rjt_volint(state) -> tr.PLHCD`.

```{warning}
**L-7a skeleton coupling:** the sink param `tr.PLHCD` is a
**dimensionless multiplier** (R3 outcome: `tr_param_registry.f90`
does not register `PNBCD`, so `PLHCD` is the only `set_param`-accepting
current-drive scalar). L-7a verifies the **API plumbing**; physical
fidelity will be addressed in L-7b once a dedicated scalar such as
`EXTERNAL_DRIVEN_I` is added on the Fortran side. Profile-level
coupling (RF deposition profile, equilibrium q-profile, ...) is also
deferred to L-7b via the BPSD broker. The equivalence test
(`python/totlib/tests/test_pipeline_equiv.py`) pins `1e-10` agreement
between hand-written and pipeline-driven runs.
```

If a step raises mid-pipeline, a `TotPipelineRunError` is raised whose
`partial_result` attribute carries snapshots of the steps that completed
successfully — so partial analyses are not lost.

### Calling from MCP

The `tot_mcp` server now ships a **`run_pipeline` MCP tool** (see
`python/mcp-servers/tot_mcp/README.md` §7.1). LLM clients can run the
same pipeline via:

```json
{
  "steps": [
    {"module": "fp", "kwargs": {"ntmax": 5}},
    {"module": "tr", "kwargs": {"ntmax": 1}}
  ],
  "params": {"fp:NSAMAX": 2, "fp:E0": 0.001, "tr:RR": 6.2, "tr:RA": 2.0}
}
```

Every invocation force-closes both the legacy `STATE` (the singleton
`Tot`) and any prior pipeline, so successive calls always start from a
clean, isolated state.

---

## Combination patterns

| Combination | Effect |
|---|---|
| **namespaced setup + transport_step** | TR-based steady-state analysis using a single `Tot` (eq geometry is also initialized at the same time) |
| **transport_step + sweep** | Grid scan such as RR x BB to evaluate TR transport sensitivity |
| **TotPipeline (L-7a)** | `fp -> tr` driven-current scalar coupling completes in one PR; profile coupling is L-7b and beyond |

For per-sub-module application patterns, see each module's
`applications.md` (e.g. `docs/sphinx/modules/tr/en/applications.md`,
`docs/sphinx/modules/eq/en/applications.md`, etc.). The same prefixed
parameters can be used to set things up via `Tot` as well.
