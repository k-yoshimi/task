# `eq` — Equilibrium

```{admonition} Coming soon
:class: note

Full chapter in preparation. In the meantime, the Python wrapper README
and the Fortran architecture notes are the authoritative sources:

- Python wrapper — `python/eqlib/README.md`
- Fortran design — `docs/eq-library/architecture.md`
- MCP server — `python/mcp-servers/eq_mcp/README.md`
```

## Overview

`eq` is the TASK equilibrium solver (Grad-Shafranov family). It is the
typical first step of a TASK pipeline — its output ψ / flux-surface geometry
feeds all downstream modules. As of PR #164/#165 it exposes the library /
Python wrapper / `validate()` APIs, matching the L-6 equivalence gate.

The full chapter will mirror the structure of the `tr` chapter
(quickstart → parameters → API reference → FAQ → Fortran design → MCP →
changelog).

## Package docstring (autodoc)

```{eval-rst}
.. automodule:: eqlib
   :no-members:
```
