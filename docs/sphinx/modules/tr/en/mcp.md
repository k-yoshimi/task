# MCP Server (`tr_mcp`)

`tr_mcp` is a server compatible with the **Model Context Protocol
(MCP)** that exposes TASK/TR directly to LLM clients such as
**Claude Desktop / Claude Code / Cursor**. Internally it is a thin
wrapper over `python/trlib` (the ctypes wrapper), so the picture is
that `libtrapi.so` is offered to the LLM as a "tool box".

```{admonition} Where this page sits
:class: note

The full beginner-oriented guide is
`python/mcp-servers/tr_mcp/README.md`. This page is a summary plus a
brief usage reference.
```

## What is MCP?

MCP (Model Context Protocol) is **the standard protocol Anthropic
designed to connect LLMs to external tools**. A simplified picture:

```text
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP server         │
│ (Claude etc.)  │◀───────────────── │ (this tr_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  tr/libtrapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

Key points:

- The LLM only has to discover and call tools. No knowledge of TR or
  Fortran is required.
- The server listens on **stdio JSON-RPC**. No network setup needed.
- Tools come with **typed schemas**, so the LLM is unlikely to pass
  the wrong arguments.

## Prerequisites

1. **Python 3.10 or later**
2. **`libtrapi.so` already built** (`make -C tr libtrapi.so`)
3. **The `mcp` package** (`pip install 'mcp>=0.9,<2'`)

## Installation

```bash
cd python/mcp-servers/tr_mcp
pip install -e .
```

This makes the `tr-mcp` command and `python -m tr_mcp.server`
available.

`trlib` itself is a pure-Python package shipped with the repository,
loaded as long as `<repo>/python` is on `PYTHONPATH`.

## Sanity checks

### Confirm the command works

```bash
python -m tr_mcp.server --help
```

### List the registered tools

```bash
python -m tr_mcp.server --print-tools
```

You will see 9 tools (details in "Provided tools" below).

### Environment health check

```bash
tr-mcp doctor
```

Returns JSON with whether the `mcp` package is installed, whether
`tr_mcp` / `trlib` import, whether `libtrapi.so` exists, and the
suggested config-file location.

### Invoking from Python directly

Functions with the `handle_*` prefix are usable both via MCP and from
tests.

```python
>>> from tr_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'tr library initialized'
>>> handle_run(0)
'advanced 0 time step(s)'
>>> state = handle_get_state()
>>> state['NT'], state['NRMAX'], state['NSMAX']
(0, 50, 2)
```

## Registering with LLM clients

### Claude Desktop

Edit the configuration file (`claude_desktop_config.json`). The path
varies by OS:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude-desktop/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "task-tr": {
      "command": "python",
      "args": ["-m", "tr_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TRLIB_PATH": "/absolute/path/to/task/tr/libtrapi.so"
      }
    }
  }
}
```

After saving and restarting Claude Desktop, `task-tr` appears in the
tool list.

### Claude Code

```bash
claude mcp add task-tr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TRLIB_PATH=/absolute/path/to/task/tr/libtrapi.so \
  -- python -m tr_mcp.server
```

Or use `tr-mcp install` to generate `.mcp.json` automatically:

```bash
tr-mcp install --client claude-code --scope project
```

### Cursor / VS Code

Cursor's project config is `.cursor/mcp.json`; the global config is
`~/.cursor/mcp.json`. Both can be auto-updated with `tr-mcp install`.

```bash
tr-mcp install --client cursor --scope project
tr-mcp install --client cursor --scope user
```

### Just print the snippet (manual paste)

```bash
tr-mcp print-config --client cursor --scope project
```

This prints the JSON snippet to stdout without modifying the config
file.

## Provided tools

`tr_mcp` exposes 9 tools.

| Tool | Purpose | Main args |
|---|---|---|
| `init` | initialize the library (`tr_init`) | none |
| `set_param` | set a single parameter | `name`, `value` (arrays use `NAME[i]`) |
| `set_params` | bulk set (scalar / list / dict) | `params` |
| `run` | advance time steps (`tr_run`) | `ntmax` (default=1) |
| `get_state` | read the current state (`tr_get_state`) | none |
| `finalize` | release resources (`tr_finalize`) | none |
| `describe_parameters` | parameter list with types and descriptions (introspection for the LLM) | none |
| `describe_state_schema` | JSON schema of the `get_state` return value | none |
| `run_and_get_state` | bundle `init + set + run + get_state` in one call | `params`, `ntmax` |

`describe_parameters` and `describe_state_schema` exist **so the LLM
does not get parameter names wrong**. The flow is for the LLM to
call these first to confirm names and types, then call `set_params`
and friends.

## Usage examples

Once registered with the LLM client, you can interact in natural
language.

### Example 1: minimum

> Initialise TR, run one step, and tell me the current time T and the
> plasma current AJT.

The LLM internally calls `init → run(1) → get_state` and returns
`scalars.T` and `scalars.AJT`.

### Example 2: change parameters and run

> Set the major radius RR to 6.5 and the toroidal field BB to 5.3,
> then run 10 steps and tell me how the safety factor Q0 changed.

The internal call is:

```python
run_and_get_state(params={"RR": 6.5, "BB": 5.3}, ntmax=10)
```

### Example 3: parameter sweep

> Run for RR = 6.0, 6.5, 7.0 (three points) and compare BETAN at 20
> steps for each.

The LLM calls `run_and_get_state` three times and tabulates the
results.

### Example 4: filtering parameters

> Give me a list of TR parameters, but only the ones related to the
> transport model.

The LLM calls `describe_parameters` and filters by `group ==
"transport"`.

## Usage scenarios — somewhat deeper workflows

The "Provided tools" list alone makes the practical shape of an
MCP-driven TR workflow hard to picture, so two typical analysis
flows are walked through in detail below.

### Scenario A: vary device parameters and inspect the energy balance

User prompt:

> Run 100 steps for ITER-like settings (RR=6.2, BB=5.3, RIP=15)
> and tell me the stored energy WPT and the normalised β (BETAN).
> Then compare with RIP=12 and RIP=18.

The tool calls the LLM makes internally:

```text
1. run_and_get_state(params={RR=6.2, BB=5.3, RIP=15.0, NSMAX=2}, ntmax=100)
   → read state.scalars["WPT"], state.scalars["BETAN"]
2. run_and_get_state(params={RR=6.2, BB=5.3, RIP=12.0, NSMAX=2}, ntmax=100)
   (init/finalize between runs is automatic on the MCP server)
3. run_and_get_state(params={RR=6.2, BB=5.3, RIP=18.0, NSMAX=2}, ntmax=100)
4. Return as a table:
     | RIP   | WPT   | BETAN |
     |-------|-------|-------|
     | 12 MA | ...   | ...   |
     | 15 MA | ...   | ...   |
     | 18 MA | ...   | ...   |
```

Key points:

- The LLM checks names with `describe_parameters` before issuing
  `run_and_get_state`, so parameter-name typos are unlikely.
- Results do not persist across processes, so each
  `run_and_get_state` starts from a clean independent state.
- Asking for the physical interpretation alongside the table
  (see {doc}`appendix-sensitivity` for the rule of thumb that
  `RIP ↑` correlates with `BETAN ↓`) gets the output close to a
  short analysis report.

### Scenario B: let the LLM repair errors via validate

User prompt:

> Run 10 steps with MODELG=3 reading `eqdata.MISSING`. If an
> error fires, guess a sensible file and retry.

What the LLM does:

```text
1. run_and_get_state(params={MODELG: 3, ...}, string_params={KNAMEQ: "eqdata.MISSING"})
   → error (FILE_MISSING)
2. Call validate and inspect the diagnostic
3. Suggest known eqdata filenames (eqdata.ITER01, eqdata.JET, ...)
4. Either confirm with the user, or automatically retry with
   the most likely candidate
```

How aggressive the LLM gets with auto-fixes is up to the LLM's
instructions:

- **Conservative**: call only `validate` and report the result;
  let the user act.
- **Aggressive**: speculatively retry with a guessed correction.

The same pattern can be reached from the Python wrapper side
(see {doc}`applications` §3 validate-driven setup) by having the
LLM call that wrapper instead.

## Architectural notes

### Singleton constraint

The Fortran side of TR keeps state in COMMON blocks, so the rule is
**one MCP process = one TR instance**. To run several at once,
launch separate processes (separate Python processes); see Q4 of
{doc}`faq` for the same reason.

### Dependency on `eqdata` files

When you set `KNAMEQ` with `MODELG=3`, the file must exist in the
**current directory** of the MCP server. When launching from Claude
Desktop, fix `cwd` via an environment variable, or point to the file
with an absolute path.

### Logging / debugging

The MCP server's stderr is forwarded to the LLM client.

- Claude Desktop: developer-tools-style log viewer
- Claude Code: the launching terminal

If errors occur, the first step is to re-confirm the environment
with `tr-mcp doctor`.

## Troubleshooting (summary)

| Symptom | Action |
|---|---|
| `libtrapi.so not found` | Run `make -C tr libtrapi.so`, then set `TRLIB_PATH` to its absolute path |
| `ModuleNotFoundError: trlib` | Add the repository's `python/` to `PYTHONPATH` |
| `ModuleNotFoundError: mcp` | `pip install 'mcp>=0.9,<2'`. Check the virtual environment |
| `invalid parameter` | Use `describe_parameters` to confirm the name (case-sensitive, 1-origin) |
| `calculation failed` | Check the consistency of `NSMAX`, `PN`, `PT`, `DT`. Reset via `finalize` → `init` |

For details, see §8 FAQ of `python/mcp-servers/tr_mcp/README.md`.

## References

- **MCP spec**: <https://modelcontextprotocol.io/>
- **Python MCP SDK**: <https://github.com/modelcontextprotocol/python-sdk>
- **Full guide**: `python/mcp-servers/tr_mcp/README.md` (about 5×
  more detailed than this page)
- **`trlib` README**: `python/trlib/README.md`
