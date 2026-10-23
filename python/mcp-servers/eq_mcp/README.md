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
python -m eq_mcp.server --print-tools   # 13 tool names, sorted
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

## Logs

The server's stderr is what the client shows (Claude Desktop's log viewer,
or the terminal under Claude Code). The library's `WRITE(6,...)` (unit 6,
fd 1) goes there too: fd 1 is the JSON-RPC pipe of a stdio server, so
`main()` hands fd 1 to stderr through the shared `python/_fd_isolation.py`
right before the server is built (#227 / #257 / #263). When stdout and
stderr are the same file (a server started by hand in a terminal, or
`2>&1`), unit 6 output is discarded and one warning line says so on
stderr; give the server a stderr of its own to keep it
(`python -m eq_mcp.server 2>server.log`). The same-file test uses the
`fstat` inode, so on Windows, where a pipe or console has none, a merged
stream is not recognised and fd 1 goes to stderr as usual.

## Tools

| Tool | Purpose |
|---|---|
| `init` / `finalize` | open / close the singleton `Eq` handle |
| `set_param`         | numeric scalar / array element (`NAME[i]`) |
| `set_param_str`     | string parameter (`KNAMEQ` etc.) |
| `set_params`        | bulk dispatch (scalar / list / dict / str) |
| `run`               | `eq_run(mode)`; `mode=1` real EQDSK load (default), `mode=0` analytic Grad-Shafranov solve (with `MODELG=2`) |
| `get_state`         | grid counters, 12 scalars, profile arrays |
| `get_psi_rz`        | the 2-D PSI(R,Z) field with the RG/ZG grid, after `run` (needs numpy) |
| `validate`          | pre-run diagnostics (Issue #143) |
| `save`              | write the equilibrium of the last `run` to a TASK/EQ binary file (`eq_save`); an existing file is replaced only with `overwrite=true`; an error when the file was not opened or is shorter than what was written |
| `describe_parameters` / `describe_state_schema` | discovery / schema |
| `run_and_get_state` | one-shot `init + set + run + get_state` |

EQ-specific gotcha: `PSIB` is **0-origin** (`PSIB[0]`..`PSIB[5]`); all
other 1D arrays (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) are 1-origin. The
`describe_parameters` tool surfaces this in its `array_syntax` field.

See [`../../eqlib/README.md`](../../eqlib/README.md) for the
underlying ctypes wrapper and the canonical fixture layout.
