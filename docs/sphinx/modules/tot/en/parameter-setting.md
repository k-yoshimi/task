# Setting Input Parameters

Unlike the other modules, `tot` **always requires a prefix** on the
parameter name. The prefix tells `tot` which sub-module the parameter
should be routed to.

## Method A — scalars (`set_param` / `set_params`)

```python
tot.set_param("eq:RR", 6.5)         # eq's RR
tot.set_param("tr:NSMAX", 2)        # tr's NSMAX
```

Or use a dict via `set_params`:

```python
tot.set_params({
    "eq:RR": 6.5,
    "eq:BB": 5.3,
    "tr:NSMAX": 2,
    "tr:NTMAX": 100,
    "wr:RF": 170e9,
})
```

## List of prefixes

Prefixes routed by the `SELECT CASE` in `tot/tot_param_registry.f90`:

| Prefix | Target sub-module | Examples |
|---|---|---|
| `eq:` | `eq` (MHD equilibrium) | `eq:RR`, `eq:BB`, `eq:KNAMEQ` |
| `tr:` | `tr` (1D transport) | `tr:NSMAX`, `tr:DT`, `tr:MDLKAI` |
| `ti:` | `ti` (integrated transport) | `ti:MODEL_NB`, `ti:MODEL_KAI` |
| `fp:` | `fp` (Fokker–Planck) | `fp:NPMAX`, `fp:NTHMAX` |
| `wr:` | `wr` (ray tracing) | `wr:RF`, `wr:RPI` |
| `wrx:` | `wrx` (beam tracing) | `wrx:RFIN[1]`, `wrx:RBRADAIN[1]` |

## Method B — array elements

Array parameters of the sub-modules are addressed with a prefix plus an
index.

```python
tot.set_param("tr:PN[1]", 1.0)       # tr's PN[1]
tot.set_param("eq:PSIB[0]", 2.0)     # eq's PSIB[0] (0-origin)
tot.set_param("wrx:RFIN[1]", 170e9)  # wrx's RFIN[1]
```

## Method C — string parameters (`set_param_str`)

Strings such as `KNAMEQ` follow the same prefix rule, for `eq:` and `tr:`,
the namespaces tot passes string values on for.

```python
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_param_str("tr:KNAMEQ", "eqdata.ITER01")  # tr reads the same file
```

`fp:KNAMEQ` is refused here; set it through `totlib.TotPipeline.set_param`
(in `tot_mcp`, `run_pipeline`'s `params`). fp reads the `KNAMEQ` of `pl`,
which is eq's: where the two share one copy of `pl`, as in the mono image,
`eq:KNAMEQ` names fp's file too.

## Pre-run validation (`validate`)

```{important}
`tot` does not currently implement a `validate()` API. Parameter
violations are reported immediately by `set_param` (as
`TotlibInvalidParamError`); calculation failures are reported at
`run()` time as `TotlibCalculationFailedError`.
```

## Typical configuration patterns

### Minimal "equilibrium + transport + heating" set

```python
tot.set_params({
    # Equilibrium
    "eq:RR": 6.2, "eq:RA": 2.0, "eq:BB": 5.3, "eq:RIP": 15.0,
    # Transport
    "tr:NSMAX": 2,
    "tr:DT": 0.01, "tr:NTMAX": 100,
    "tr:MDLKAI": 31,            # CDBM
    # NBI heating (via tr)
    "tr:MDLNB": 1,
})
```

### EQDSK equilibrium + ECRH ray tracing

```python
tot.set_param("eq:MODELG", 3)
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_params({
    "tr:NSMAX": 2,
    "wr:RF": 170e9,
    "wr:RPI": 8.5,
    "wr:ZPI": 1.5,
})
tot.run(ntmax=10)
```

### Fast-ion analysis (fp integration)

```python
tot.set_params({
    "eq:RR": 6.2, "eq:BB": 5.3, "eq:RIP": 15.0,
    "tr:NSMAX": 2, "tr:MDLNB": 1,
    "fp:NSAMAX": 2,                  # fp's active species count
    "fp:NPMAX": 100, "fp:NTHMAX": 50, # fp's 5D grid
})
tot.run(ntmax=50)
```

## What if I forget the prefix?

```python
tot.set_param("RR", 6.5)            # ← TotlibInvalidParamError
```

`tot` **does not accept un-prefixed names**. Always write `eq:RR`,
`tr:RR`, etc.
