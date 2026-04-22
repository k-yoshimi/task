# eq_mcp — TASK/EQ MCP server

`eq_mcp` exposes the TASK/EQ equilibrium code (`eq/libeqapi.so`) as
Model Context Protocol tools so an LLM client (Claude Desktop / Claude
Code / Cursor) can drive equilibrium loads without writing Fortran.

It is the EQ-specific sister of `tr_mcp` / `ti_mcp` / `wrx_mcp`; the
shape, packaging and invocation are identical, with two EQ extras:

- `set_param_str` — string parameters such as `KNAMEQ` (the EQDSK file
  path); routed through `eqlib.Eq.set_param_str`.
- `validate` — pre-run cross-parameter validation (Issue #143);
  returns a list of `{param, code, message}` diagnostics so the LLM
  can spot configuration errors before paying for a real EQDSK load.

## Install

```bash
make -C eq libeqapi.so                  # one-time build
pip install -e python/mcp-servers/eq_mcp
```

## Smoke test

```bash
python -m eq_mcp.server --help
python -m eq_mcp.server --print-tools   # 11 tool names, sorted
```

## Use from Claude

Register in `claude_desktop_config.json` (or `claude mcp add task-eq …`):

```jsonc
{
  "mcpServers": {
    "task-eq": {
      "command": "python",
      "args": ["-m", "eq_mcp.server"],
      "env": {
        "PYTHONPATH": "/abs/path/to/task/python",
        "EQLIB_PATH": "/abs/path/to/task/eq/libeqapi.so"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
|---|---|
| `init` / `finalize` | open / close the singleton `Eq` handle |
| `set_param`         | numeric scalar / array element (`NAME[i]`) |
| `set_param_str`     | string parameter (`KNAMEQ` etc.) |
| `set_params`        | bulk dispatch (scalar / list / dict / str) |
| `run`               | `eq_run(mode)`; default `mode=1` (real EQDSK load) |
| `get_state`         | grid counters, 12 scalars, profile arrays |
| `validate`          | pre-run diagnostics (Issue #143) |
| `describe_parameters` / `describe_state_schema` | discovery / schema |
| `run_and_get_state` | one-shot `init + set + run + get_state` |

EQ-specific gotcha: `PSIB` is **0-origin** (`PSIB[0]`..`PSIB[5]`); all
other 1D arrays (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) are 1-origin. The
`describe_parameters` tool surfaces this in its `array_syntax` field.

See [`../../eqlib/README.md`](../../eqlib/README.md) for the
underlying ctypes wrapper and the canonical fixture layout.
