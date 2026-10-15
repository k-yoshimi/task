# MCP Server (`eq_mcp`)

`eq_mcp` is a Model Context Protocol (MCP) server (PR #167) that lets
**LLM clients such as Claude Desktop, Claude Code, and Cursor** drive
TASK/EQ directly. Internally it is a thin layer over `python/eqlib`
(the ctypes wrapper), so it presents `libeqapi.so` to the LLM as a
"toolbox".

```{admonition} Scope of this page
:class: note

The full guide for newcomers is in
`python/mcp-servers/eq_mcp/README.md`. This page is a focused summary
plus a brief usage reference. For the MCP protocol in general, the
`tr_mcp` page (`docs/sphinx/modules/tr/en/mcp.md`) is also a useful
reference.
```

## Architecture

```text
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP server         │
│ (Claude, …)    │◀───────────────── │ (this eq_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  eq/libeqapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

Differences from `tr_mcp`:

- A **`set_param_str`** tool is added — for string parameters such as
  `KNAMEQ` (EQDSK filename). `tr` recently added one too, but `eq`
  has needed it from the start.
- A **`validate`** tool is exposed independently — pre-run validation
  (PR #164) is published on a dedicated endpoint. The LLM can detect
  missing EQDSK files before `run`.
- **11** tools in total (`tr` has 9).

## Prerequisites

1. **Python 3.10 or later**
2. **`libeqapi.so` already built** (`make -C eq libeqapi.so`)
3. **The `mcp` package** (`pip install 'mcp>=0.9,<2'`)

## Installation

```bash
cd python/mcp-servers/eq_mcp
pip install -e .
```

After this the `eq-mcp` command and `python -m eq_mcp.server` are
available.

## Sanity checks

### Confirm the command runs

```bash
python -m eq_mcp.server --help
```

### Show the registered tools

```bash
python -m eq_mcp.server --print-tools
```

You should see 11 tools (see "Tool catalog" below).

### Environment health check

```bash
eq-mcp doctor
```

Returns JSON describing whether the `mcp` package, `eq_mcp` /
`eqlib` imports, and `libeqapi.so` are available, along with the
recommended location of the configuration file.

### Drive it directly from Python

```python
>>> from eq_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'eq library initialized'
>>> # ... after set_param_str("KNAMEQ", "eqdata.ITER01") ...
>>> handle_run(1)   # mode=1 (read KNAMEQ)
'equilibrium loaded with mode=1'
>>> state = handle_get_state()
>>> state['scalars']['raxis'], state['scalars']['qaxis']
(6.4321, 0.9876)
```

## Registering with LLM clients

### Claude Desktop

Add to the configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "task-eq": {
      "command": "python",
      "args": ["-m", "eq_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "EQLIB_PATH": "/absolute/path/to/task/eq/libeqapi.so"
      }
    }
  }
}
```

Make sure the EQDSK file referenced by `KNAMEQ` is in a directory the
server can reach (or specify it by absolute path).

### Claude Code

```bash
claude mcp add task-eq \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env EQLIB_PATH=/absolute/path/to/task/eq/libeqapi.so \
  -- python -m eq_mcp.server
```

Or via `eq-mcp install`:

```bash
eq-mcp install --client claude-code --scope project
```

### Cursor / VS Code

```bash
eq-mcp install --client cursor --scope project
eq-mcp install --client cursor --scope user
```

## Tool catalog

`eq_mcp` exposes **11** tools.

| Tool | Purpose | Main args |
|---|---|---|
| `init` | initialise the library (`eq_init`) | none |
| `set_param` | set a numeric parameter | `name`, `value` (arrays via `NAME[i]`) |
| `set_param_str` | **set a string parameter (EQ-specific)** | `name`, `value` (one of 7 keys including `KNAMEQ`) |
| `set_params` | set many at once (dict) | `params` |
| `run` | run the equilibrium calculation (`eq_run`) | `mode` (default=1) |
| `get_state` | fetch the current state (`eq_get_state`) | none |
| `validate` | **pre-run validation (an EQ strength)** | none |
| `finalize` | release resources (`eq_finalize`) | none |
| `describe_parameters` | list parameters with types and groups | none |
| `describe_state_schema` | JSON schema for the `get_state` return value | none |
| `run_and_get_state` | bundle `init + set + validate + run + get_state` | `params`, `string_params`, `mode` |

`set_param_str` and `validate` are the two distinguishing features of
EQ. `tr_mcp` lacks `set_param_str`, and `validate` was a later
addition there too.

## Usage examples

### Example 1: analytic toroidal geometry (no `KNAMEQ`)

> Initialise EQ, solve the equilibrium with RR=6.5, BB=5.3, RIP=1.5,
> and tell me the magnetic-axis position and qaxis.

The LLM internally calls
`run_and_get_state(params={"RR": 6.5, "BB": 5.3, "RIP": 1.5}, mode=1)`
and returns `scalars.raxis` and `scalars.qaxis`. With `MODELG=2`
(the default), `KNAMEQ` is not needed.

### Example 2: load from an EQDSK file

> Read the ITER EQDSK file `eqdata.ITER01`, build the equilibrium,
> and tell me beta_t and pvol.

The LLM uses `set_param` for `MODELG=3`, `set_param_str` for
`KNAMEQ="eqdata.ITER01"`, then `validate` to confirm the file exists,
and finally `run`.

### Example 3: pre-run validation

> Check whether the current parameters can be run.

The LLM calls `validate` and shows a list of diagnostics
(`FILE_MISSING`, `OUT_OF_RANGE`, …). This avoids loops looking for
EQDSK files.

### Example 4: parameter scan

> Run with RR=5.0, 6.0, 7.0 and compare raxis, qaxis, betat at each
> point.

The LLM calls `run_and_get_state` three times and tabulates the
results.

## Architectural notes

### Singleton constraint

Like `tr`, EQ is one-instance-per-process ({doc}`faq` Q6). To run
several at once, launch them in separate processes.

### Dependence on the `eqdata` file

When `MODELG=3,5,8` and `KNAMEQ` is set, the file must exist in the
**current directory** of the MCP server. When launching from Claude
Desktop, either pin the `cwd` via an environment variable or specify
absolute paths.

### Use `validate` aggressively

It is also available in `tr_mcp` but is particularly effective in
`eq`. It detects EQDSK file existence and compile-time-max overflow
of grid sizes (`NRGMAX`, `NPSMAX`, … ten in total) **without
calling `run`**. In an LLM workflow that varies many parameters,
this directly saves tokens and retries.

## Troubleshooting (summary)

| Symptom | What to do |
|---|---|
| `libeqapi.so not found` | run `make -C eq libeqapi.so`, then set `EQLIB_PATH` to the absolute path |
| `ModuleNotFoundError: eqlib` | add the repo's `python/` to `PYTHONPATH` |
| `ModuleNotFoundError: mcp` | `pip install 'mcp>=0.9,<2'`; check the virtualenv |
| `EQDSK file missing` | confirm the file referenced by `KNAMEQ` is in the current directory |
| `EqlibCalculationFailedError: ierr=3` | check the physical consistency of inputs; relax `EPSEQ` or raise `NLPMAX` |

## References

- **MCP specification**: <https://modelcontextprotocol.io/>
- **Python MCP SDK**: <https://github.com/modelcontextprotocol/python-sdk>
- **Full guide**: `python/mcp-servers/eq_mcp/README.md`
- **`eqlib` README**: `python/eqlib/README.md`
