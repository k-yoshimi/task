# TASK/EQ library-ization — architecture

Phase L delivered a shared-library + Python-wrapper alternative to the
traditional `eq` CLI for the TASK MHD-equilibrium module. The EQ
project mirrors the TR Phase L structure (see
`docs/tr-library/architecture.md`); this doc records the EQ-specific
diagram and per-phase status. The one structural difference vs the
sibling tr/ti/wr/fp libraries is a **6th C ABI entry point**,
`eq_set_param_str`, used to set the seven `CHARACTER(LEN=80)` namelist
parameters (`KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`,
`KNAMFO`, `KNAMPF`).

## System diagram

```
+-------------------------------------------------------------------+
| User code                                                          |
|                                                                    |
|   Python scripts            C / C++ drivers          Interactive   |
|   (examples/, tests/)       (own main.c, etc.)       shell users   |
+-----------+-----------------+---------------+--------------+-------+
            |                 |               |              |
            v                 v               v              |
   +------------------+  +---------------+                   |
   |  python/eqlib    |  |  <C driver>   |                   |
   |  (ctypes)        |  |  (#include    |                   |
   |                  |  |   eq_api.h)   |                   |
   |  Eq / EqState    |  +-------+-------+                   |
   |  errors / _ffi   |          |                           |
   +--------+---------+          |                           |
            |                    |                           |
            +----------+---------+                           |
                       |                                     |
                       v                                     v
            +-----------------------+               +----------------+
            |   eq/libeqapi.so      |               |   eq/eq        |
            |   (shared lib, L-4)   |               |   (CLI binary) |
            |                       |               |                |
            |   6 exported symbols  |               |   menu loop,   |
            |   eq_init / eq_run /  |               |   graphics,    |
            |   eq_set_param /      |               |   file I/O     |
            |   eq_set_param_str /  |               +-------+--------+
            |   eq_get_state /      |                       |
            |   eq_finalize         |                       |
            +-----------+-----------+                       |
                        |                                   |
                        v                                   v
            +---------------------------------------------------+
            |  Fortran backend  (shared code)                    |
            |                                                    |
            |   eq_api.f90              wraps eqcom* + COMMON    |
            |   eq_param_registry.f90   name -> variable dispatch|
            |   eq_state.f90            BIND(C) eq_state_t       |
            |   equnit::eq_load         equilibrium-file loader  |
            |   eqcalc / eqcalq / ...   Grad-Shafranov kernels   |
            |   eqcom*_mod              COMMON-block + module    |
            |   eq_graphics_stubs.f90   graphics-symbol stubs    |
            +-------------------+-------------------------------+
                                |
                                v
            +---------------------------------------------------+
            |  Dependency libraries (PIC + non-PIC variants)    |
            |   lib/ libtask_pic.a   pl/ libpl_pic.a            |
            |   bpsd/ libbpsd_pic.a  mtxp/ libmtxp_pic.a        |
            +---------------------------------------------------+
```

## Layering

| Layer | Artefact | Purpose |
|---|---|---|
| 0. Regression baseline | `test_run/baselines/eq_*/metrics.json` | Phase L-0 ground truth (`eq_iter01`, `eq_tst2`) |
| 1. Fortran backend | `eq/eq_api.f90`, `eq_param_registry.f90`, `equnit`, `eqcalc`, ... | Numerics, shared with the `eq` binary |
| 2. C ABI | `eq/eq_api.h` + BIND(C) exports in `eq_api.f90` | 6 functions + 2 layout queries (#246), stable contract |
| 3. Shared library | `eq/libeqapi.so` | `make -C eq libeqapi.so`, links `lib*_pic.a` |
| 4. Python FFI | `python/eqlib/_ffi.py` | `ctypes` layout mirror of `eq_state_t` |
| 5. High-level wrapper | `python/eqlib/eqlib.py`, `state.py`, `errors.py` | Context manager + dataclass + exceptions |
| 6. User scripts | `python/eqlib/examples/*.py`, user notebooks | |

### 6 C ABI entry points (+ 2 layout queries, #246)

From `eq/eq_api.h`:

```c
int eq_init(void);
int eq_run(int mode);
int eq_set_param(const char *name, double value);
int eq_set_param_str(const char *name, const char *value);  /* eq-specific */
int eq_get_state(eq_state_t *state);
int eq_finalize(void);
```

Return codes (`enum eq_error`):

| code | meaning | Python exception |
|---|---|---|
| 0 | OK | — |
| 1 | invalid name / value (incl. bare `"PSIB"` with no idx; a negative `eq_run` mode) | `EqlibInvalidParamError` |
| 2 | not initialised | `EqlibNotInitializedError` |
| 3 | calculation failed (`eq_run` / `eq_get_state`) | `EqlibCalculationFailedError` |
| 4 | not implemented: an `eq_run` mode above 1 | `EqlibNotImplementedError` |

`eq_state_t` carries six grid-counter ints (`nrgmax`, `nzgmax`,
`npsmax`, `nrmax`, `nthmax`, `nsumax`), 12 plasma scalars (`raxis`,
`zaxis`, `psi0`, `psipa`, `psita`, `qaxis`, `qsurf`, `betat`,
`betap`, `pvol`, `raave`, `ripx`), four `[NPSM=513]` 1-D
psi-surface profiles (`psips`, `ppps`, `ttps`, `qqps`), and two
grid-coordinate arrays (`rg[NRGM=513]`, `zg[NZGM=513]`). 2-D
fields (`PSIRZ`, `RPS(NPSM,NTHM)`, `ZPS(NPSM,NTHM)`) are not yet
exported.

### Fortran backend

- `eq_api.f90` owns the BIND(C) wrappers. Each function is a thin
  shim that marshals C arguments into the existing Fortran entry
  points and maps Fortran ierr to the C `enum eq_error`.
- `eq_param_registry.f90` implements a hand-written `SELECT CASE`
  dispatch (94 entries: ~78 numeric scalars/ints, 5 array families
  including 0-origin `PSIB`, 7 string keys via `eq_set_param_str`)
  mapping `"NAME"` or `"NAME[idx]"` strings to `plcomm_parm` /
  `eqcom1_mod` / `eqcom2_mod` / `eqcom3_mod` module variables.
  Extending the registry is the only code change needed to expose
  new parameters.
- Kernel code (`eqcalc`, `eqcalq`, `equnit`, `eqfile`, ...) is
  unchanged and shared with the `eq` binary.

### Python wrapper

- `eqlib._ffi.EqStateC` mirrors `eq_state_t` byte-for-byte (padded to
  `EQ_MAX_NRGM=513`, `EQ_MAX_NZGM=513`, `EQ_MAX_NPSM=513`).
- `eqlib._ffi.load_library` resolves the shared library via
  `EQLIB_PATH` → `eq/libeqapi.so` → `lib/libeqapi.so` and uses
  `RTLD_LAZY` so dangling graphics references never block loading.
  `eq_set_param_str` is attached best-effort so import succeeds on
  pre-L-3 builds; first `set_param_str` call on such a build raises
  `EqlibError` instead.
- `eqlib.Eq` is a context manager: `__init__` calls `eq_init`,
  `__exit__` / `close()` calls `eq_finalize`. All 6 entry points map
  to methods (`set_param`, `set_param_str`, `set_params`, `run`,
  `get_state`, `close`).
- `eqlib.EqState` is a `@dataclass` snapshot; `to_dict()` is
  JSON-serialisable and matches the Phase L-0 baseline layout (uppercase
  keys: `NRGMAX`, `NZGMAX`, `NPSMAX`, `RG`, `ZG`, `PSIPS`, `PPPS`,
  `TTPS`, `QQPS`, plus a `scalars` sub-dict with uppercase scalar names).

### EQ-specific quirks

Three behaviours differ from the sibling tr/ti/wr/fp wrappers:

1. **`PSIB` is 0-origin.** The Fortran declaration is
   `REAL(8) :: PSIB(0:5)`, and the registry uses `idx == -1` as the
   "no subscript" sentinel — bare `"PSIB"` without `[i]` returns
   `EQ_ERR_INVALID`. All other 1-D arrays (`RIPFC`, `RPFC`, `ZPFC`,
   `WPFC`) follow the project convention of 1-origin.
2. **String setter is a separate C ABI symbol.** `eq_set_param_str`
   (the 6th entry) handles the seven `CHARACTER(LEN=80)` namelist
   keys. The numeric `eq_set_param` cannot dispatch them because the
   value type is `c_double`. tr/ti/wr/fp do not currently expose
   string parameters.
3. **`eq.run()` defaults to `mode=1`.** `mode=1` is the
   equilibrium-file load via `equnit::eq_load`: it reads the file of
   the format `MODELG` names (`EQ_READ` in `eq/eqfile.f90`), so with
   the default `MODELG=2`, which names none, `eq.run()` fails
   (`EqlibCalculationFailedError`). `mode=0` is the Grad-Shafranov
   solve: `EQCALC` solves the fixed-boundary equation numerically from
   the parameters, then `EQCALQ`; it needs no file.
   A mode above 1 raises `EqlibNotImplementedError`
   (`EQ_ERR_NOT_IMPL`), a negative one `EqlibInvalidParamError`
   (`EQ_ERR_INVALID`).

## Phase L completion matrix

| Phase | Deliverable | Plan | Merge PR | Status |
|---|---|---|---|---|
| L-0 | Phase 0 regression baselines (`eq_iter01`, `eq_tst2`) + `eqregress.f90` + `extract_eq_metrics.py` | `2026-04-18-eq-library-L0-baseline.md` | #54 | merged |
| L-1 | Makefile graphics split (`SRCS_CORE` / `SRCS_GRAPHICS` / `SRCS_MENU`) | `2026-04-18-eq-library-L1-makefile-split.md` | #65 | merged |
| L-2 | C ABI foundation (`eq_api.h`, stub exports returning ierr=4) | `2026-04-18-eq-library-L2-c-abi-foundation.md` | #70 | merged |
| L-3 | Parameter registry + real `eq_init/run(1)/get_state/finalize` + `eq_set_param_str` | `2026-04-18-eq-library-L3-param-registry.md` | #78 | merged |
| L-4 | `libeqapi.so` shared-library build + PIC variants | `2026-04-18-eq-library-L4-shared-lib-build.md` | #80 | merged |
| L-5 | `python/eqlib/` ctypes wrapper (`Eq`, `EqState`, errors, `set_param_str`) | `2026-04-18-eq-library-L5-python-wrapper.md` | #86 | merged |
| L-6 | 4-layer test suite wired into `run_tests.sh` | `2026-04-18-eq-library-L6-test-4layers.md` | — | pending |
| L-7 | Library documentation (this doc, README, examples, CHANGELOG) | `2026-04-18-eq-library-L7-docs.md` | this PR | open |

## Acceptance criteria status

Mirrors the tr spec's §12.2 for the EQ module:

| Criterion | Sub-phase | How to verify |
|---|---|---|
| `libeqapi.so` generated | L-4 | `ls eq/libeqapi.so && file eq/libeqapi.so` |
| `import eqlib` works | L-5 | `python3 -c "from eqlib import Eq"` |
| `eq_set_param_str` exported | L-3 / L-4 | `nm -D eq/libeqapi.so | grep eq_set_param_str` |
| Layer 1 equivalence PASS | L-6 (pending) | `test_run/run_tests.sh eqlib_equivalence` |
| Layer 2 C ABI PASS | L-6 (pending) | `test_run/run_tests.sh eqlib_c_abi` |
| Layer 3 Python wrapper PASS | L-6 (pending) | `test_run/run_tests.sh eqlib_ffi eqlib_wrapper` |
| Layer 4 sweep smoke PASS | L-6 (pending) | `test_run/run_tests.sh eqlib_sweep` |
| `eq` numerics match Phase L-0 | L-0..L-5 | `test_run/run_tests.sh eq_iter01 eq_tst2` |
| `python/eqlib/README.md` with examples | L-7 | visual review + `python3 -m py_compile examples/*.py` |
| `run_tests.sh` eqlib_* wired | L-6 (pending) | `grep eqlib_ test_run/test_definitions.conf` |

## Known limitations

- **L-6 not yet merged.** The 4-layer test integration (`eqlib_*`
  cases in `test_definitions.conf`) is in flight on its own branch.
  Until L-6 lands, run wrapper tests directly with
  `python3 -m unittest discover python/eqlib/tests`.
- **Single instance per process.** EQ uses COMMON blocks and
  `eqcom*_mod` module variables. Two concurrent `Eq()` handles share
  state; the second `eq_init` resets globals. Use `multiprocessing`
  for parallel sweeps — each worker process gets its own
  `libeqapi.so` load.
- **2-D fields not yet exported.** `PSIRZ`, `RPS(NPSM,NTHM)`, and
  `ZPS(NPSM,NTHM)` will require a future `eq_state_t` extension.
- **Seven string keys only.** Other character-valued entries (if any
  are added later to `eqparm`) need explicit `eq_param_registry.f90`
  extension.
- **`PSIB` 0-origin trap.** Bare `"PSIB"` (no subscript) is rejected
  by the registry. Always use `set_param("PSIB[i]", v)` for
  `i ∈ 0..5`.

## State struct layout rule (#246)

`eq_state_t` (`eq/eq_api.h`) and `eq_state_c` (`eq/eq_state.f90`) are
one fixed layout, filled by `eq_get_state`. Changing it:

1. append the field at the end of both (never reorder, never remove);
2. bump `EQ_STATE_ABI_VERSION` **in both files** (the `#define` and the
   `PARAMETER`; currently `1`);
3. mirror the field in `python/eqlib/_ffi.py` (`EqStateC._fields_`) and
   `state.py`;
4. rebuild `libeqapi.so` in the same commit.

The library exports its own view: `eq_state_abi_version()` returns the
PARAMETER and `eq_state_size()` the `sizeof` of the BIND(C) type, both
callable before `eq_init`. `eq/tests/c_abi/test_negative.c` and
`test_run_so.c` fail when either differs from the header, and
`python/eqlib/_ffi.py::load_library` refuses a library whose version or
size differs from `EqStateC`, or that exports neither symbol (built
before #246), with `EqlibAbiError` naming the fix. Both silent
failure modes of a stale pair are therefore caught at load time: a longer
library struct would have written past the wrapper's allocation, a
shorter one would have left the appended fields as plausible zeros.

## References

- Design spec: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
  (TR template; EQ follows the same pattern with one extra
  string-setter entry point)
- User README: `python/eqlib/README.md`
- Phase plans: `docs/superpowers/plans/2026-04-18-eq-library-L*.md`
- TR counterpart: `docs/tr-library/architecture.md`
- TI counterpart: `docs/ti-library/architecture.md`
- WR counterpart: `docs/wr-library/architecture.md`
- FP counterpart: `docs/fp-library/architecture.md`
- C ABI header: `eq/eq_api.h`
- Parameter registry: `eq/eq_param_registry.f90`
- Top-level changelog: `CHANGELOG.md`
