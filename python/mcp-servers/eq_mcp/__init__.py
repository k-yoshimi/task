"""eq_mcp: FastMCP server exposing TASK/EQ equilibrium code as MCP tools.

Thin wrapper over :mod:`eqlib` (ctypes binding to ``libeqapi.so``).
Sister server to :mod:`tr_mcp` / :mod:`ti_mcp` / :mod:`wrx_mcp` —
same shape, different backing library.

The EQ-specific surface adds two extras over the canonical sister set:

* ``set_param_str`` — string parameters (``KNAMEQ`` and friends),
  routed through ``eqlib.Eq.set_param_str``.
* ``validate`` — pre-run cross-parameter validation (Issue #143)
  exposing ``eqlib.Eq.validate()`` so an LLM can spot configuration
  errors before paying for a real EQDSK load.

See :mod:`eq_mcp.server` for the tool implementations.
"""
