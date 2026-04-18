# fplib - Python wrapper for TASK/FP

`fplib` is a ctypes-based Python binding for `fp/libfpapi.so` (Phase L-4
product). It uses only the Python standard library (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional and not required.

See `docs/superpowers/plans/2026-04-18-fp-library-L5-python-wrapper.md`
for the design.

## Architecture

Two layers:

* `fplib._ffi` - low-level ctypes binding. Exposes `FpStateC`
  (mirror of `fp_state_t`) and `load_library()` which resolves and
  `CDLL`-loads `libfpapi.so` with function prototypes attached.
* `fplib.Fplib` - high-level context manager with `init/run/set_param/
  get_state/finalize` methods and `FpState` dataclass output.

## Build prerequisites

1. Build the shared library:

   ```bash
   cd fp && make libs_pic && make libfpapi.so
   ```

   This produces `fp/libfpapi.so` and its 5 exported C symbols
   (`fp_init`, `fp_run`, `fp_set_param`, `fp_get_state`, `fp_finalize`).

2. Add the `python/` directory to `PYTHONPATH`:

   ```bash
   export PYTHONPATH=$(pwd)/python:$PYTHONPATH
   ```

## Library-path lookup

When you do `Fplib()` (no arguments) the loader searches in order:

1. `FPLIB_PATH` environment variable, if set
2. `<repo>/fp/libfpapi.so` (default build location)
3. `<repo>/lib/libfpapi.so` (install-style location)

Override by passing `Fplib(lib_path="/custom/path/libfpapi.so")`.

## Quick example

```python
from fplib import Fplib

with Fplib() as fp:
    fp.set_params(RR=6.5, BB=5.3, NSMAX=3,
                  PN={1: 0.8, 2: 0.4, 3: 0.4})
    fp.set_param("PA[2]", 2.0)
    fp.run(ntmax=2)
    state = fp.get_state()

print("timefp =", state.timefp)
print("first RNT row =", state.RNT[0] if state.RNT else [])

# JSON-serialisable dict:
import json
print(json.dumps(state.to_dict())[:200])
```

## Errors

All exceptions derive from `fplib.FplibError`. Specific subclasses
match the C ABI `enum fp_error` in `fp/fp_api.h`:

| `rc` | exception | meaning |
|---|---|---|
| 0 | - | success |
| 1 | `FplibInvalidParamError` | invalid parameter name / value |
| 2 | `FplibNotInitError` | library not initialised |
| 3 | `FplibCalcFailedError` | calculation / get_state failed |
| 4 | `FplibNotImplementedError` | reserved (was L-2 stub) |

Aliases with the `FpLib...` capitalisation (`FpLibInvalidParam`,
`FpLibNotInitialized`, `FpLibCalculationFailed`, `FpLibNotImplemented`)
are also exported for callers that prefer the spec naming.

## `set_params` vs `set_param`

`set_params(**kwargs)` accepts scalar kwargs directly and also handles
array arguments via dict or list/tuple values:

```python
fp.set_params(RR=6.5, BB=5.3)                 # scalar kwargs
fp.set_params(PN={1: 0.8, 2: 0.4, 3: 0.4})    # dict: NAME[idx]=value
fp.set_params(PN=[0.8, 0.4, 0.4])             # list: NAME[1..N]=values
fp.set_param("PN[1]", 0.7)                    # direct bracket syntax
```

Keys containing `__` are rejected in `set_params` as a common
`NAME__i` array-syntax mistake.

## Running the tests

```bash
cd python/fplib/tests
python3 -m unittest discover -v
```

Tests that require `libfpapi.so` are skipped when it hasn't been built
yet; the remaining tests (ctypes layout, error wiring,
`FpState.from_c`, `to_dict` shape) always run.
