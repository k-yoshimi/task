# MCP Server (`wr_mcp`)

`wr_mcp` is a **Model Context Protocol (MCP)** server that lets LLM
clients such as **Claude Desktop / Claude Code / Cursor** drive TASK/WR
directly.

```{admonition} Scope of this page
:class: note

The full beginner-oriented guide lives in
`python/mcp-servers/wr_mcp/README.md`. This page is a summary. For a
general MCP-protocol introduction, see the corresponding page in the
`tr` module (`docs/sphinx/modules/tr/en/mcp.md`).
```

## Prerequisites

1. **Python 3.10 or newer**
2. **`libwrapi.so` already built** (`make -C wr libwrapi.so`)
3. **The `mcp` package** (`pip install 'mcp>=0.9,<2'`)

## Installation

```bash
cd python/mcp-servers/wr_mcp
pip install -e .
```

## Smoke test

```bash
python -m wr_mcp.server --help
python -m wr_mcp.server --print-tools
wr-mcp doctor
```

## Registering with an LLM client

### Claude Desktop

```json
{
  "mcpServers": {
    "task-wr": {
      "command": "python",
      "args": ["-m", "wr_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "WRLIB_PATH": "/absolute/path/to/task/wr/libwrapi.so"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add task-wr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env WRLIB_PATH=/absolute/path/to/task/wr/libwrapi.so \
  -- python -m wr_mcp.server
```

Or run `wr-mcp install --client claude-code --scope project`.

## Tool list

`wr_mcp` exposes **9 tools**.

| Tool | Purpose | Main arguments |
|---|---|---|
| `init` | initialise the library | none |
| `set_param` | set one parameter | `name`, `value` |
| `set_params` | set many at once | `params` |
| `run` | run the ray trace | `nray_request` (default=0) |
| `get_state` | read current state | none |
| `finalize` | release resources | none |
| `describe_parameters` | parameter list (103) | none |
| `describe_state_schema` | return-value schema | none |
| `run_and_get_state` | one-shot run | `params`, `nray_request` |

## Usage examples

### Example 1: ECRH power-deposition position

> Initialise WR with RR=6.2, BB=5.3, RF=170e9, RPI=8.0, ZPI=0.0, trace
> one ray, and tell me the peak deposition position (pos_pwrmax_rs).

The LLM calls `run_and_get_state(params={"RR": 6.2, "BB": 5.3,
"RF": 170e9, "RPI": 8.0, "ZPI": 0.0}, nray_request=1)` and returns
`scalars.pos_pwrmax_rs`.

### Example 2: Frequency scan

> Run RF at 100, 140, 170, 200 GHz and compare the peak deposition
> positions.

The LLM calls `run_and_get_state` four times and tabulates the result.
Useful for ECRH frequency tuning.

### Example 3: Beam approximation

> With NRAYMAX=5, spread the rays in Z from -0.1 to 0.1 and return the
> summed absorption profile of the 5 rays.

The LLM sets `set_param("ZPIN[1]", -0.1)`, `ZPIN[2]=-0.05`, ... then
calls `run(nray_request=5)` and returns `state.pwr_nrs`.

## Architectural notes

### `run` argument

Unlike the `run(ntmax)` of `tr` / `ti` / `fp`, **`run(nray_request)` is
the number of rays**. `nray_request=0` falls back to the value of
`NRAYMAX`.

### Singleton constraint

`wr` shares its `pl_*` state with `tr`, `eq`, `ti`, and `fp`. It cannot
be co-resident with another `*_mcp` in the same process.

### `wr` vs `wrx`

A guideline for the LLM to choose:

- Quick simple analysis → `wr_mcp`
- Accurate beam-shape modelling → `wrx_mcp`

## Troubleshooting (summary)

| Symptom | Action |
|---|---|
| `libwrapi.so not found` | run `make -C wr libwrapi.so`, give `WRLIB_PATH` an absolute path |
| Ray stops part-way | tune `NSTPMAX`, `UUMIN` ({doc}`faq` Q4) |
| Peak power is zero | check `RF` and launch conditions ({doc}`faq` Q5) |
| Result differs from `wrx2` | run `wrlib_equivalence` |

## References

- **MCP specification**: <https://modelcontextprotocol.io/>
- **Full guide**: `python/mcp-servers/wr_mcp/README.md`
- **`wrlib` README**: `python/wrlib/README.md`
