# MCP Server (`ti_mcp`)

`ti_mcp` is an MCP (Model Context Protocol) server that exposes
TASK/TI directly to LLM clients such as **Claude Desktop / Claude Code
/ Cursor**.

```{admonition} Scope of this page
:class: note

The full beginner's guide lives at
`python/mcp-servers/ti_mcp/README.md`. This page is a focused summary.
For an overview of the MCP protocol itself, see also the MCP page in
the `tr` module (`docs/sphinx/modules/tr/en/mcp.md`).
```

## Prerequisites

1. **Python 3.10 or newer**
2. **`libtiapi.so` already built** (`make -C ti libtiapi.so`)
3. **The `mcp` package** (`pip install 'mcp>=0.9,<2'`)

## Installation

```bash
cd python/mcp-servers/ti_mcp
pip install -e .
```

## Verifying the install

```bash
python -m ti_mcp.server --help
python -m ti_mcp.server --print-tools
ti-mcp doctor
```

## Registering with an LLM client

### Claude Desktop

```json
{
  "mcpServers": {
    "task-ti": {
      "command": "python",
      "args": ["-m", "ti_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TILIB_PATH": "/absolute/path/to/task/ti/libtiapi.so"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add task-ti \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TILIB_PATH=/absolute/path/to/task/ti/libtiapi.so \
  -- python -m ti_mcp.server
```

Or `ti-mcp install --client claude-code --scope project`.

### Cursor

```bash
ti-mcp install --client cursor --scope project
```

## Tools exposed

`ti_mcp` exposes **9 tools** (the same set as `tr_mcp`; `set_param_str`
and `validate` are not implemented in `ti`, so they are absent).

| Tool | Purpose | Main arguments |
|---|---|---|
| `init` | Initialize the library | none |
| `set_param` | Set a single parameter | `name`, `value` (arrays use `NAME[i]`) |
| `set_params` | Set many at once | `params` |
| `run` | Advance time steps | `ntmax` (default=1) |
| `get_state` | Read the current state | none |
| `finalize` | Release resources | none |
| `describe_parameters` | List parameter names, types, descriptions | none |
| `describe_state_schema` | JSON schema of `get_state`'s return | none |
| `run_and_get_state` | `init + set + run + get_state` in one call | `params`, `ntmax` |

## Usage examples

### Example 1: Simple run

> Initialize TI, run 10 steps with RR=6.5, BB=5.3, NSMAX=2, and tell me
> T and the residual.

The LLM internally invokes
`run_and_get_state(params={"RR": 6.5, "BB": 5.3, "NSMAX": 2}, ntmax=10)`
and returns `scalars.T` and `scalars.residual_loop_max`.

### Example 2: Toggling a heating model

> Enable NBI, run 10 steps with RR=6.5, and tell me the central value
> of the BETA profile.

The LLM calls `set_param("MODEL_NB", 1)` and `set_params({"RR": 6.5})`,
runs, and reports `state.BETA[0]` (near the axis).

### Example 3: Comparing transport models

> Run 50 steps with `MODEL_KAI` set to 31 (CDBM) and 140 (mBgB), and
> compare T and the residual at the end.

The LLM calls `run_and_get_state` twice and tabulates the results.

## Architectural notes

### Singleton constraint (conflict with tr/eq)

`ti` shares the global plasma state (`pl_*`) with `tr` and `eq`.
Loading both `ti_mcp` and `tr_mcp` **in the same process will
conflict**. Run them in separate processes ({doc}`faq` Q2).

### No `validate` — be careful

Unlike `tr_mcp` / `eq_mcp`, `ti` has no pre-run validation API. Invalid
parameters are detected for the first time at `run()` via
`TilibRunError`. Be mindful of compute time when an LLM sweeps many
parameters.

## Troubleshooting (summary)

| Symptom | Resolution |
|---|---|
| `libtiapi.so not found` | Run `make -C ti libtiapi.so` and set `TILIB_PATH` to an absolute path |
| `ModuleNotFoundError: tilib` | Add the repo's `python/` to `PYTHONPATH` |
| `MAXLOOP reached` | Reduce `DT`, increase `MAXLOOP` ({doc}`faq` Q6) |
| Results differ from `tr` | `ti` includes auxiliary physics, so disagreement with `tr` is expected. Use `tilib_equivalence` for baseline comparison |

## References

- **MCP specification**: <https://modelcontextprotocol.io/>
- **Full guide**: `python/mcp-servers/ti_mcp/README.md`
- **`tilib` README**: `python/tilib/README.md`
