# MCP Server (`fp_mcp`)

`fp_mcp` is a **Model Context Protocol (MCP)** server that lets LLM
clients (Claude Desktop, Claude Code, Cursor, etc.) drive TASK/FP
directly.

```{admonition} Where this page sits
:class: note

The complete getting-started guide is at
`python/mcp-servers/fp_mcp/README.md`. This page is a summary. For
general MCP-protocol material, see the `tr` MCP page
(`docs/sphinx/modules/tr/en/mcp.md`).
```

## Prerequisites

1. **Python 3.10 or later**
2. **`libfpapi.so` already built** (`make -C fp libfpapi.so`)
3. **The `mcp` package** (`pip install 'mcp>=0.9,<2'`)
4. **Enough RAM** — the 5D grid takes hundreds of MB to several GB

## Installation

```bash
cd python/mcp-servers/fp_mcp
pip install -e .
```

## Smoke test

```bash
python -m fp_mcp.server --help
python -m fp_mcp.server --print-tools
fp-mcp doctor
```

## Registering with an LLM client

### Claude Desktop

```json
{
  "mcpServers": {
    "task-fp": {
      "command": "python",
      "args": ["-m", "fp_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "FPLIB_PATH": "/absolute/path/to/task/fp/libfpapi.so"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add task-fp \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env FPLIB_PATH=/absolute/path/to/task/fp/libfpapi.so \
  -- python -m fp_mcp.server
```

Or `fp-mcp install --client claude-code --scope project`.

## Tools exposed

`fp_mcp` exposes **9** tools. The C ABI exposes `fp_set_param_str`, but
this is not currently surfaced through MCP — if you need to override
`KNAMEQ`, prepare the environment beforehand instead of going through
MCP.

| Tool | Purpose | Main arguments |
|---|---|---|
| `init` | Initialise the library | none |
| `set_param` | Set one parameter | `name`, `value` |
| `set_params` | Bulk set | `params` |
| `run` | Advance time | `ntmax` |
| `get_state` | Fetch the current state | none |
| `finalize` | Release resources | none |
| `describe_parameters` | Parameter listing | none |
| `describe_state_schema` | Return-value schema | none |
| `run_and_get_state` | One-shot run | `params`, `ntmax` |

## Usage examples

### Example 1: NBI fast-ion distribution

> Initialise FP, enable `MODEL_NBI=1` with `NSAMAX=2`, advance 10 steps,
> and return the `RTT` (temperature profile) of active species 0.

The LLM sets `MODEL_NBI=1`, `NSAMAX=2` via `set_params`, calls
`run(ntmax=10)`, and reads `state.RTT[0]`.

### Example 2: LH-driven current

> Enable `MODEL_WAVE=1` with `PABS_LH=2.0`, run 5 steps, and integrate
> `RJT` (current density) over volume.

The LLM calls `set_params(PABS_LH=2.0, MODEL_WAVE=1)`, `run(ntmax=5)`,
and integrates `state.RJT[0]` over the `state.nrmax` radial points.

### Example 3: Grid-resolution comparison

> Run with `NPMAX=50` and `NPMAX=100`; tell me how the accuracy
> changes.

The LLM calls `run_and_get_state` twice and compares the `RTT` deltas.

## Architectural notes

### Memory budget

The 5D grid means the MCP server process can use a lot of memory:

```
RAM ≈ NRMAX × NPMAX × NTHMAX × NSAMAX × 800 bytes
```

If the LLM tries `NPMAX=200`-class values it can easily reach GBs.
**Check the parameter ranges via `describe_parameters` before running**
for safety.

### Singleton constraint

`fp` shares `pl_*` state with `tr`, `eq`, and `ti`. You cannot run
multiple `*_mcp` servers in the same process.

### No `validate`

`fp` does not implement a `validate` API. Parameter errors are caught
only by `FplibCalcFailedError` at `run` time, so be mindful of LLM
retry costs during exploratory use.

## Troubleshooting (summary)

| Symptom | Action |
|---|---|
| `libfpapi.so not found` | `make -C fp libfpapi.so`, then set `FPLIB_PATH` to an absolute path |
| `MemoryError` | Lower `NPMAX` / `NTHMAX` |
| Result disagrees with `fpx2` | Check with `fplib_equivalence` |
| Run is slow | Loosen `LMAXFP` / `EPSFP` or reduce grid resolution |

## References

- **MCP specification**: <https://modelcontextprotocol.io/>
- **Full guide**: `python/mcp-servers/fp_mcp/README.md`
- **`fplib` README**: `python/fplib/README.md`
