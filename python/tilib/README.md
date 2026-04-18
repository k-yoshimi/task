# tilib - Python wrapper for TASK/TI

`tilib` is a ctypes-based Python binding for `ti/libtiapi.so` (Phase L-4
product). It uses only the Python standard library (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional and not required.

See `docs/superpowers/specs/2026-04-17-tr-library-design.md` §6 for the
shared TR/TI design.

## Architecture

Two layers:

* `tilib._ffi` - low-level ctypes binding. Exposes `TiStateC`
  (mirror of `ti_state_t`) and `load_library()` which resolves and
  `CDLL`-loads `libtiapi.so` with function prototypes attached.
* `tilib.TiLib` - high-level context manager with `init/run/set_param/
  get_state/finalize` methods and `TiState` dataclass output.

## Install / Build prerequisites

1. Build the shared library:

   ```bash
   cd ti && make libtiapi.so
   ```

   This produces `ti/libtiapi.so` and its 5 exported C symbols
   (`ti_init`, `ti_run`, `ti_set_param`, `ti_get_state`, `ti_finalize`).

2. Add the `python/` directory to `PYTHONPATH`:

   ```bash
   export PYTHONPATH=$(pwd)/python:$PYTHONPATH
   ```

## Library-path lookup

When you do `TiLib()` (no arguments) the loader searches in order:

1. `TILIB_PATH` environment variable, if set
2. `<repo>/ti/libtiapi.so` (default build location)
3. `<repo>/lib/libtiapi.so` (install-style location)

Override by passing `TiLib(lib_path="/custom/path/libtiapi.so")`.

## Quick example

```python
from tilib import TiLib

with TiLib() as ti:
    ti.set_params(RR=6.2, BB=5.3)        # scalar params via kwargs
    ti.set_param("PN[1]", 0.7)            # array element by name
    ti.run(ntmax=10)
    state = ti.get_state()

print("T =", state.T)
print("first RTA row =", state.RTA[0])

# JSON-serialisable dict:
import json
print(json.dumps(state.to_dict())[:200])
```

## Errors

All exceptions derive from `tilib.TilibError`. Specific subclasses
match the C ABI `enum ti_error` in `ti/ti_api.h`:

| `ierr` | exception | meaning |
|---|---|---|
| 0 | - | success |
| 1 | `TilibParamError` | invalid parameter name / value |
| 2 | `TilibStateError` | library not initialised |
| 3 | `TilibRunError` | calculation / get_state failed |
| 4 | `TilibNotImplementedError` | L-2 stub; not implemented yet |

Aliases with the `TiLib...` capitalisation (`TiLibInvalidParam`,
`TiLibNotInitialized`, `TiLibCalculationFailed`, `TiLibNotImplemented`)
are also exported for callers that prefer the spec naming.

## `set_params` vs `set_param`

`set_params(**kwargs)` is **scalar-only** because Python keyword
argument names cannot contain `[` or `]`. For array elements call
`set_param()` directly:

```python
ti.set_params(RR=3.0, BB=2.0)
ti.set_param("PN[1]", 0.7)      # array element
```

Keys containing `__` are rejected in `set_params` as a common
array-syntax mistake.

## Running the tests

```bash
cd python/tilib/tests
python3 -m unittest discover -v
```

Tests that require `libtiapi.so` are skipped when it hasn't been built
yet; the remaining tests (ctypes layout, error wiring, `TiState.from_c`,
`to_dict` shape) always run.
