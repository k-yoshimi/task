# `wrx` — Wave Ray Extended

```{admonition} Coming soon
:class: note

Full chapter in preparation. For now, see:

- Python wrapper — `python/wrxlib/README.md`
- Fortran design — `docs/wrx-library/architecture.md`
- MCP server — `python/mcp-servers/wrx_mcp/README.md`
```

## Overview

`wrx` extends the `wr` ray-tracing solver with a beam-tracing option. It
shares the 5-function C ABI described in {doc}`../common/architecture`;
the Python wrapper (`wrxlib`) is the primary entry point for scripting.

## Package docstring (autodoc)

```{eval-rst}
.. automodule:: wrxlib
   :no-members:
```
