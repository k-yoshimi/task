"""tot_mcp — Model Context Protocol server for TASK/TOT.

Exposes 10 tools that wrap :mod:`totlib` (``python/totlib``). TOT is the
TASK orchestrator: its parameter space is the **union** of the per-module
registries (eq, tr, fp, ti, wr, wrx), so every parameter name passed
through the MCP tools MUST carry a namespace prefix such as ``"eq:RR"``,
``"tr:DT"``, ``"fp:NSMAX"``, ``"ti:RR"``, ``"wr:RFIN"`` or
``"wrx:RFIN"``. See ``README.md`` for installation and Claude Desktop /
Claude Code registration instructions.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
