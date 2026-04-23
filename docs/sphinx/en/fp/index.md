# `fp` — Fokker-Planck

```{admonition} Coming soon
:class: note

Full chapter in preparation. For now, see:

- Python wrapper — `python/fplib/README.md`
- Fortran design — `docs/fp-library/architecture.md`
- MCP server — `python/mcp-servers/fp_mcp/README.md`
```

## Overview

`fp` is the TASK Fokker-Planck solver for fast-ion / energetic-particle
distribution functions. It consumes equilibrium/flux data from `eq` and
can be driven stand-alone or inside a coupled run via `tot`.

## Package docstring (autodoc)

```{eval-rst}
.. automodule:: fplib
   :no-members:
```
