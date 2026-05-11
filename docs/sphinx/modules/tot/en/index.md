# `tot` — Orchestrator

```{admonition} What you'll learn
:class: tip

How to use `totlib` from Python to drive TASK/TOT (the **orchestrator**
that integrates the eq / tr / ti / fp / wr / wrx modules within a single
library). Topics covered include building the shared library, the
**prefixed parameter naming convention** (`eq:RR`, `tr:NSMAX`, etc.),
sub-module coupling, and the four-layer test suite.
```

## Overview — what `tot` does

**TASK/TOT** is the **orchestrator** for tokamak plasma simulations. It
runs the eq / tr / ti / fp / wr / wrx modules in a single process and
**dynamically passes data between them**.

For example, an integrated simulation combining "equilibrium + transport
+ ECRH heating + fast-ion analysis" would normally require code that
calls `Eq()`, `Trlib()`, `Wrlib()`, and `Fplib()` in sequence and hands
results between them by hand. With `Tot()` it is a single call:

```python
with Tot() as tot:
    tot.set_param("eq:RR", 6.5)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("wr:RF", 170e9)
    tot.run(ntmax=10)
```

Main quantities returned (TR-based):

- Scalars (14): `T`, `WPT`, `BETAN`, `TAUE1`, ..., `AJRFT`
- Profiles: `RN`, `RT`, `AJ`, `QP` (TR-compatible)
- Additionally: `tr_present`, `ti_present`, `fp_present`, `wr_present`
  (sub-module presence flags)

## User guide

```{toctree}
:maxdepth: 1

build
hello-world
parameters
parameter-setting
state
context-manager
faq
applications
```

## Reference

```{toctree}
:maxdepth: 1

quickstart
api-reference
```

## Internals

```{toctree}
:maxdepth: 1

design
mcp
testing
```

## Appendix

```{toctree}
:maxdepth: 1

appendix-sensitivity
```

## Suggested reading order

1. {doc}`build` — build all sub-modules + the tot library
2. {doc}`hello-world` — minimal example using prefixes
3. {doc}`parameters` — prefix routing rules
4. {doc}`parameter-setting` — how to set `eq:RR`, `tr:NSMAX`, etc.
5. {doc}`state` — integrated outputs + presence flags
6. {doc}`context-manager` — coordinated init/finalize across all modules

When you get stuck, see {doc}`faq`. The complete API specification is in
{doc}`api-reference`. The input ↔ output correspondence is summarised in
{doc}`appendix-sensitivity`.

## Differences from other modules (summary)

| | `tr`/`eq`/`fp`/`wr`/`wrx`/`ti` | `tot` |
|---|---|---|
| **Target modules** | one only | **all** (orchestrator) |
| **Parameter names** | `RR`, `BB`, `NSMAX` | `eq:RR`, `tr:NSMAX` (prefix required) |
| **Memory footprint** | only that one module | sum of all modules |
| **C ABI** | 5–6 functions | 6 functions (including `set_param_str`) |
| **Typical use** | single-module analysis | **self-consistent integrated simulation** |

## When should I use `tot`?

- You need a **time-evolving self-consistent simulation** (equilibrium →
  transport → heating → equilibrium, ...)
- You want to **dynamically pass** the result of one module into another
- You want to avoid writing boilerplate code that calls each library in
  sequence

Conversely, **stand-alone modules are preferable** when:

- You are running a unit test or benchmark of a single module
- You need to save memory (tot is heavy because all modules are loaded)
- You need sub-module-specific outputs (e.g. eq's `raxis`, fp's `RJT`) —
  those are not exposed in tot's State
