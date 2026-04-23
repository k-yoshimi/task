# `tot` — Orchestrator

```{admonition} Coming soon
:class: note

Full chapter in preparation. For now, see:

- Python wrapper — `python/totlib/README.md`
- Fortran design — `docs/tot-library/architecture.md`
- MCP server — `python/mcp-servers/tot_mcp/README.md`
```

## Overview

`tot` is the orchestrator module that composes runs across
`eq` → `tr` / `ti` / `fp` / `wr` / `wrx`. It uses a namespace-prefixed
parameter dictionary (e.g. `eq:BB`, `tr:NSMAX`) so sub-module parameters
can be set from a single Python dict or TOML file.

## Package docstring (autodoc)

```{eval-rst}
.. automodule:: totlib
   :no-members:
```
