# Registered Input Parameters

`tot/tot_param_registry.f90` contains only **9 prefix CASE entries** and
**routes** individual parameters to each sub-module. In other words,
`tot` itself has no parameters of its own; **every parameter of eq, tr,
ti, fp, wr, and wrx is available through the appropriate prefix**.

## Required and recommended parameters

### Required

`tot` itself has no required parameters. Each sub-module's requirements
are met by setting them with the appropriate prefix.

For example, with `MODELG=3` (EQDSK input) the following are required:

```python
tot.set_param("eq:MODELG", 3)
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
```

### Strongly recommended

For practical simulations you should at least set the following:

| Prefix | Parameters | Recommended values (ITER-class) |
|---|---|---|
| `eq:` | `RR`, `RA`, `BB`, `RIP` | 6.2 m, 2.0 m, 5.3 T, 15.0 MA |
| `tr:` | `NSMAX`, `DT`, `NTMAX` | 2, 0.01 s, 100 |

## Routing rules

The `SELECT CASE` in `tot` looks at the leading key (the part before the
`:`) to choose the target module.

| Key (prefix) | Routed to | Covered parameter range |
|---|---|---|
| `eq:`  | `eq_param_set` | All 94 eq parameters (see `docs/sphinx/modules/eq/en/parameters.md`) |
| `tr:`  | `tr_param_set` | All ~30 tr parameters |
| `ti:`  | `ti_param_set` | All 77 ti parameters |
| `fp:`  | `fp_param_set` | All 55 fp parameters |
| `wr:`  | `wr_param_set` | All 103 wr parameters |
| `wrx:` | `wrx_param_set` | All 70 wrx parameters |

For the full parameter list of each sub-module, see its respective
parameters.md.

## String parameters

`set_param_str` follows the same prefix convention, for the namespaces
tot passes string values on for, `eq:` and `tr:` (`tot/tot_param_registry.f90`).
For `fp:`, `ti:`, `wr:` and `wrx:` it raises `TotlibInvalidParamError`.

```python
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_param_str("tr:KNAMEQ", "eqdata.ITER01")
```

`fp:KNAMEQ` is set through `totlib.TotPipeline.set_param("fp:KNAMEQ", ...)`
instead, which hands it to fplib's own `set_param_str` (in `tot_mcp`, a
string value in `run_pipeline`'s `params`); `ti`, `wr` and `wrx` take no
string parameters. tr has its own `KNAMEQ`. eq's `KNAMEQ` is the one in
`pl` (`plcomm`), which fp reads too: where eq and fp share one copy of `pl`,
as in the mono image `libtotapi_mono.so`, `eq:KNAMEQ` also names the file
fp loads.

## Recommended workflow

```python
from totlib import Tot

with Tot() as tot:
    # 1. Common: device parameters (sent to eq)
    tot.set_params({
        "eq:RR": 6.2, "eq:RA": 2.0, "eq:BB": 5.3, "eq:RIP": 15.0,
    })

    # 2. Transport (tr)
    tot.set_params({
        "tr:NSMAX": 2,
        "tr:DT": 0.01, "tr:NTMAX": 100,
        "tr:MDLKAI": 31,           # CDBM
    })

    # 3. (Optional) ECRH ray tracing
    tot.set_params({
        "wr:RF": 170e9,
        "wr:RPI": 8.5, "wr:ZPI": 0.0,
    })

    # 4. (Optional) Fast-ion analysis
    tot.set_params({
        "fp:NSAMAX": 1,
        "fp:NPMAX": 50, "fp:NTHMAX": 25,
    })

    # 5. Time-evolve the coupled system
    tot.run(ntmax=10)
    state = tot.get_state()
```

## Which prefixes are usable

Only sub-modules that were initialised by `Tot()` can be used. All of
them are normally initialised, but you can verify the individual
presence flags with `state.<mod>_present`:

```python
state = tot.get_state()
print("tr ok:" , state.tr_present)
print("fp ok:" , state.fp_present)
print("wr ok:" , state.wr_present)
```

Setting a parameter for a module whose `*_present = 0` raises an error.

## Parameter details for each module

For full details, see the parameters page of each module:

- `tr` parameters: `docs/sphinx/modules/tr/en/parameters.md`
- `eq` parameters: `docs/sphinx/modules/eq/en/parameters.md`
- `ti` parameters: `docs/sphinx/modules/ti/en/parameters.md`
- `fp` parameters: `docs/sphinx/modules/fp/en/parameters.md`
- `wr` parameters: `docs/sphinx/modules/wr/en/parameters.md`
- `wrx` parameters: `docs/sphinx/modules/wrx/en/parameters.md`
