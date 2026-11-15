# MCP Server (`tot_mcp`)

`tot_mcp` is a server that conforms to the **Model Context Protocol
(MCP)**, letting **LLM clients such as Claude Desktop, Claude Code, and
Cursor** drive TASK/TOT directly. Its biggest strength is that **a
single server controls every sub-module in an integrated way**.

```{admonition} Where this page sits
:class: note

The full beginner-friendly guide is in
`python/mcp-servers/tot_mcp/README.md`. This page is a curated summary.
For an explanation of the MCP protocol in general, see the `tr`
module's MCP server page (`docs/sphinx/modules/tr/en/mcp.md`).
```

## Prerequisites

1. **Python 3.10 or later**
2. **`libtotapi.so` already built** (`make -C tot libtotapi.so`)
3. **The `mcp` package**
4. **Sufficient RAM** — several GB may be required because every module
   is loaded

## Installation

```bash
cd python/mcp-servers/tot_mcp
pip install -e .
```

## Smoke test

```bash
python -m tot_mcp.server --help
python -m tot_mcp.server --print-tools
tot-mcp doctor
```

## Registering with an LLM client

### Claude Desktop

```json
{
  "mcpServers": {
    "task-tot": {
      "command": "python",
      "args": ["-m", "tot_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TOTLIB_PATH": "/absolute/path/to/task/tot/libtotapi.so"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add task-tot \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TOTLIB_PATH=/absolute/path/to/task/tot/libtotapi.so \
  -- python -m tot_mcp.server
```

Or use `tot-mcp install --client claude-code --scope project`.

## Tools provided

`tot_mcp` exposes **10 tools**. The use of prefixed parameter names is
what differentiates it from the other modules' servers.

| Tool | Purpose | Main arguments |
|---|---|---|
| `init` | Initialise tot + all sub-modules | none |
| `set_param` | Set a prefixed parameter | `name` (e.g. `"eq:RR"`), `value` |
| `set_params` | Bulk parameter set | `params` (e.g. `{"eq:RR": 6.5, "tr:NSMAX": 2}`) |
| `run` | Run the integrated simulation | `ntmax` |
| `get_state` | Fetch the integrated state | none |
| `finalize` | Release all modules | none |
| `describe_parameters` | List prefixes + parameters | none |
| `describe_state_schema` | Schema of the TotState return value | none |
| `run_and_get_state` | One-shot run | `params`, `ntmax` |
| `run_pipeline` | Run modules in sequence, coupled through scalars (`totlib.TotPipeline`); a string value in `params` goes to the module's own string setter, so `fp:KNAMEQ` works here | `steps`, `params` |

## Usage examples

### Example 1: minimal integrated simulation

> Initialise TOT, run 10 steps with eq:RR=6.5, eq:BB=5.3, tr:NSMAX=2,
> and tell me T and BETAN.

The LLM will issue
`set_params({"eq:RR": 6.5, "eq:BB": 5.3, "tr:NSMAX": 2})`,
`run(ntmax=10)`, and read `state.scalars`.

### Example 2: integrated analysis with ECRH

> Load the ITER EQDSK file `eqdata.ITER01`, run 50 transport steps with
> ECRH ray-tracing at 170 GHz applied, and tell me the time evolution
> of BETAN.

The LLM will pass

```python
{
    "eq:MODELG": 3,
    "eq:KNAMEQ": "eqdata.ITER01",
    "tr:NSMAX": 2,
    "wr:RF": 170e9,
    "wr:RPI": 8.5,
}
```

then call `run(ntmax=50)` and return `state.scalars["BETAN"]`.

### Example 3: checking presence flags

> Tell me whether each sub-module loaded correctly.

The LLM will return `state.tr_present`, `state.fp_present`,
`state.wr_present`, etc. A 0 means that sub-module failed to initialise.

### Example 4: exploring parameter names

> List the parameters available in tot, but only those for the eq
> module.

The LLM will call `describe_parameters` and filter for names that start
with the `eq:` prefix.

## Architectural notes

### Prefix is mandatory

`set_param("RR", 6.5)` is an **error**. You must write
`set_param("eq:RR", 6.5)` or `set_param("tr:RR", 6.5)`. LLMs frequently
trip over this — checking with `describe_parameters` first is the
safest approach.

### Large memory footprint

Because `tot_mcp` keeps every module loaded, the process is heavier than
a stand-alone server (typically 500 MB – 2 GB). Take care when an LLM
turns `fp:NPMAX` up — the footprint grows quickly.

### Servers cannot be multiplexed

`tot_mcp` and a stand-alone server such as `tr_mcp` **cannot live in
the same process**. They must run as independent client configurations.

## Troubleshooting (summary)

| Symptom | Action |
|---|---|
| `libtotapi.so not found` | Run `make -C tot libtotapi.so`; verify all sub-modules have a PIC build |
| `<mod>_present = 0` | Verify the sub-module's `.so` is built |
| `Invalid parameter` (prefix) | Use `describe_parameters` to confirm the available names |
| MemoryError | Reduce `fp:NPMAX`, `fp:NTHMAX`, etc. |

## References

- **MCP specification**: <https://modelcontextprotocol.io/>
- **Full guide**: `python/mcp-servers/tot_mcp/README.md`
- **`totlib` README**: `python/totlib/README.md`
