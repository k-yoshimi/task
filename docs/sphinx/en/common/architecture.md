# Common Architecture

```{admonition} What you'll learn
:class: tip

This chapter covers what is shared by every module
(`eq` / `tr` / `ti` / `fp` / `wr` / `wrx` / `tot`): the three core
software layers (Python wrapper → C ABI → Fortran backend), the
five-function C ABI, error codes 0–4, the PIC build flow, and the
two-layer Python wrapper. Every per-module chapter after this one is an
application of this one.
```

## The layered architecture

Every `Xlib` (where X is one of `eq`, `tr`, `ti`, `fp`, `wr`, `wrx`,
`tot`) has the same structure: three software layers (Python wrapper →
C ABI → Fortran backend), with the user sitting above and the compiled
shared library `.so` being the build artifact that packages all three
into one loadable binary.

```text
┌───────────────────────────────────────────────────────────────────┐
│ User layer (Python script / C driver / Jupyter notebook)          │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ Python wrapper layer                                               │
│   python/Xlib/: Xlib class, XState dataclass, exception hierarchy, │
│                 _ffi.py (ctypes bindings)                          │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ C ABI layer (5 functions + 2 structs)                              │
│   X/X_api.h:                                                       │
│     X_init / X_run / X_set_param / X_get_state / X_finalize        │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ Fortran backend (physics kernel, unchanged from tr2 / eqx2 / …)    │
│   X/X_api.f90, X_param_registry.f90, Xloop/Xcalc/ …                │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ Shared library X/libXapi.so  (statically linked with PIC deps)     │
└───────────────────────────────────────────────────────────────────┘
```

### Role of each layer

- **User layer** — your code. You call into Python like any other
  Python library.
- **Python wrapper layer** — translates Python calls into C ABI calls
  via `ctypes`, handling `.so` loading, exception mapping, and struct
  marshalling.
- **C ABI layer** — five C functions that bridge Python/C to Fortran.
  Five is small enough to memorise, and identical across all seven
  modules apart from the `X_` prefix.
- **Fortran backend** — the physics. The library build links exactly
  the same source files as the standalone `tr2` / `eqx2` binaries, so
  numerical results are guaranteed to match (see the L-6 equivalence
  gate).
- **Shared library** — the whole stack compiled into a single `.so`
  (`shared object`) file, loaded at run time.

## What a shared library (`.so`) is

```{admonition} Background
:class: note

A **shared library** (`.so` file) is a reusable chunk of machine code
that a program can load at run time. It is the Linux equivalent of
Windows `.dll` or macOS `.dylib`.

Unlike a self-contained `.exe`, a shared library can be loaded from any
language after the fact:

- From Python: `ctypes.CDLL("libtrapi.so")`.
- From C: link time with `gcc -ltrapi`, or run time with `dlopen()`.

That's what lets us drive the same Fortran physics kernel from Python
notebooks, MCP servers, or third-party C code.
```

## The 5-function C ABI

For each module `X` exactly five C functions are exported. Learn these
once and the pattern repeats seven times; only the `X_` prefix changes.

```c
/* Example for tr. Replace tr_ with eq_ / wr_ / wrx_ / ti_ / fp_ / tot_. */
int tr_init(void);                                  /* initialise  */
int tr_run(int ntmax);                              /* step time   */
int tr_set_param(const char* name, double value);   /* configure   */
int tr_get_state(tr_state_t* state);                /* read state  */
int tr_finalize(void);                              /* tear down   */
```

Every return value is an **error code** (see the next section).

Some modules export a few additional specialised variants
(`X_set_param_str` for strings, `X_validate` for batch pre-run checks,
and per-shape accessors `X_get_state_s/v/m`), but the five functions
above are the backbone of every module.

## Error codes 0–4

The C ABI uses a 5-value return convention. It's short enough to memorise.

| Code | Constant | Meaning |
|:-:|---|---|
| 0 | `X_OK`              | success |
| 1 | `X_ERR_INVALID`     | invalid parameter name / value |
| 2 | `X_ERR_NOT_INIT`    | `X_init` was never called |
| 3 | `X_ERR_CALC_FAILED` | physics calculation failed |
| 4 | `X_ERR_NOT_IMPL`    | stub / not implemented (Phase L-2 hangover) |

The Python wrappers translate any non-zero return into a typed exception
from the `Xlib`\ `Error` hierarchy (e.g. `TrlibParamError`,
`FplibNotInitError`). You never need to inspect the integer return
yourself from Python.

## Lifecycle of the 5 functions

```text
  X_init ──▶ X_set_param ──▶ X_run ──▶ X_get_state ──▶ X_finalize
                 ▲     │
                 └─────┘
               (repeat)
```

- `X_init` — call **once per process**. Initialises Fortran COMMON
  blocks and allocates working arrays.
- `X_set_param` — call as many times as you like. Examples: `"RR"`
  (major radius), `"BB"` (on-axis field), `"PN[1]"` (ion density for
  species 1).
- `X_run` — advance the integration by a caller-chosen number of
  steps.
- `X_get_state` — copy the current state out into an `X_state_t`
  struct. On the Python side this turns into an `XState` dataclass.
- `X_finalize` — tear-down. The Python `with` statement calls this
  automatically on exit.

```{admonition} Module state does not fully reset
:class: warning

Calling `X_finalize` does not reset every piece of module-level Fortran
state. If you need to reinitialise in the same process — e.g. inside a
test — isolate with `pytest --forked` (see the testing chapter and the
project CLAUDE.md for the underlying discipline).
```

## PIC — position-independent code

```{admonition} Background
:class: note

**PIC** (Position Independent Code) is the compilation mode that lets a
shared library work no matter where in memory it's loaded. Regular
static archives (`.a`) don't need it; `.so`s do.

TASK keeps both: every legacy archive (non-PIC, used by `tr2` /
`eqx2`) stays untouched, and a parallel `lib*_pic.a` is built for the
library path. This means the existing executables build exactly as
before while the libraries become available as a by-product.
```

### PIC Makefile targets

The following targets are added to each module:

```bash
make -C lib  libs_pic    # PIC archives under lib/
make -C pl   libs_pic    # pl/plcomm_pic.a, etc.
make -C eq   libs_pic
make -C mtxp libs_pic
make -C bpsd libs_pic
make -C tr   libtrapi.so   # final product (eqx / fpx / … analogous)
```

## The two-layer Python wrapper

The Python side is **deliberately** split into two layers.

```text
┌────────────────────────────────────────────────────────────┐
│ High-level:                                                 │
│   Trlib, TrState, TrlibError hierarchy                      │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│ Low-level:                                                  │
│   trlib._ffi  (ctypes CDLL, TrStateC struct mirror)         │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│ tr/libtrapi.so  (loaded via dlopen)                         │
└────────────────────────────────────────────────────────────┘
```

The low-level `_ffi.py` is a **byte-for-byte mirror** of the C ABI —
each `ctypes.Structure` has the exact same field order and types as the
corresponding `X_state_t`. That means the Fortran-written raw data can
be read straight out without an intermediate copy.

The high-level `Xlib.py` exposes the Pythonic surface — `with`
statements, dataclasses, typed exceptions, and (for modules that have
it) the `validate()` pre-run check.

## How the library is located

When `Xlib()` is invoked with no `lib_path` argument it searches for
`libXapi.so` in this order:

1. The environment variable `XLIB_PATH` (e.g. `TRLIB_PATH`,
   `FPLIB_PATH`, `EQLIB_PATH`, `WRLIB_PATH`, `WRXLIB_PATH`,
   `TILIB_PATH`, `TOTLIB_PATH`).
2. `<repo_root>/X/libXapi.so` — the default build output.
3. `<repo_root>/lib/libXapi.so` — reserved for a future install target.

To pin the path explicitly, pass `Trlib(lib_path="/absolute/path")`.

## RTLD_LAZY loading

```{admonition} Background
:class: note

`ctypes.CDLL(..., mode=RTLD_LAZY)` tells the dynamic loader to defer
symbol resolution until a symbol is actually used. TASK's shared
libraries still carry a handful of graphics / PGPlot symbols that
never get called from the library path; `RTLD_NOW` (eager resolution)
would refuse to load the `.so` because of those stragglers.
`RTLD_LAZY` sidesteps the problem — as long as you don't call into the
graphics path from Python, resolution never happens.
```

## Memory layout (C vs Fortran)

```{admonition} Careful with axis order
:class: warning

C is **row-major**, Fortran is **column-major**. A C declaration
`double RN[NRMAX][NSMAX]` is byte-identical to Fortran
`REAL(KIND=8) :: RN(NSMAX, NRMAX)` — but the index order is reversed.
The Python `XState` dataclass follows the C convention: `nrmax` is the
outer list dimension, `nsmax` the inner.
```

## Chapter summary

Every per-module chapter after this one reapplies the same pattern:
*five functions, five error codes, `Xlib`\ `Error`-derived exceptions,
`with` for the lifetime, and a `validate()` call where available*.
Read the {doc}`../tr/index` chapter next, then generalise to
`eq` / `ti` / `fp` / `wr` / `wrx` / `tot`.
