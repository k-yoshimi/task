# TASK/FP library-ization — architecture

Phase L delivers a shared-library + Python-wrapper alternative to the
traditional `fp` CLI for the TASK Fokker-Planck module. The FP project
mirrors the TR Phase L structure (see
`docs/tr-library/architecture.md`); this doc records the FP-specific
diagram and per-phase status.

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
   |  python/fplib    |  |  <C driver>   |                   |
   |  (ctypes)        |  |  (#include    |                   |
   |                  |  |   fp_api.h)   |                   |
   |  Fplib / FpState |  +-------+-------+                   |
   |  errors / _ffi   |          |                           |
   +--------+---------+          |                           |
            |                    |                           |
            +----------+---------+                           |
                       |                                     |
                       v                                     v
            +-----------------------+               +----------------+
            |   fp/libfpapi.so      |               |   fp/fp        |
            |   (shared lib, L-4)   |               |   (CLI binary) |
            |                       |               |                |
            |   5 exported symbols  |               |   menu loop,   |
            |   fp_init / fp_run /  |               |   graphics,    |
            |   fp_set_param /      |               |   file I/O     |
            |   fp_get_state /      |               +-------+--------+
            |   fp_finalize         |                       |
            +-----------+-----------+                       |
                        |                                   |
                        v                                   v
            +---------------------------------------------------+
            |  Fortran backend  (shared code)                    |
            |                                                    |
            |   fp_api.f90              wraps FPCOMM globals     |
            |   fp_param_registry.f90   name -> variable dispatch|
            |   fp_prep / fp_loop       time-advance kernels     |
            |   fpcomm.f90 + submodules  module-level state      |
            |   fp_graphics_stubs.f90   dangling-symbol shims    |
            +-------------------+-------------------------------+
                                |
                                v
            +---------------------------------------------------+
            |  Dependency libraries (PIC + non-PIC variants)    |
            |   lib/ libtask_pic.a   pl/ libpl_pic.a            |
            |   eq/ libeq_pic.a      ob/ libob_pic.a            |
            |   dp/ libdp_pic.a      mtxp/ libmtxp_pic.a        |
            |   ../bpsd/ libbpsd_pic.a                          |
            +---------------------------------------------------+
```

## Layering

| Layer | Artefact | Purpose |
|---|---|---|
| 0. Regression baseline | `test_run/baselines/fp_{iter01,jt60,dt1}/` | Phase 0 ground truth (tol `1e-10`) |
| 1. Fortran backend | `fp/fp_api.f90`, `fp_param_registry.f90`, `fpprep`, `fploop`, ... | Numerics, shared with `fp` binary |
| 2. C ABI | `fp/fp_api.h` + BIND(C) exports in `fp_api.f90` | 5 functions, stable contract |
| 3. Shared library | `fp/libfpapi.so` | `make -C fp libs_pic && make -C fp libfpapi.so` |
| 4. Python FFI | `python/fplib/_ffi.py` | `ctypes` layout mirror of `fp_state_t` |
| 5. High-level wrapper | `python/fplib/fplib.py`, `state.py`, `errors.py` | Context manager + dataclass |
| 6. User scripts | `python/fplib/examples/*.py`, user notebooks | |

### 5 C ABI entry points

From `fp/fp_api.h`:

```c
int fp_init(void);
int fp_run(int ntmax);
int fp_set_param(const char *name, double value);
int fp_get_state(fp_state_t *state);
int fp_finalize(void);
```

Return codes (`enum fp_error`):

| code | meaning | Python exception |
|---|---|---|
| 0 | OK | — |
| 1 | invalid name / value; from `fp_run`, a count it cannot run with (below) | `FplibInvalidParamError` |
| 2 | not initialised | `FplibNotInitError` |
| 3 | calculation failed | `FplibCalcFailedError` |
| 4 | not implemented (Phase L-2 stub) | `FplibNotImplementedError` |

`fp_run` checks the counts together before any work (`fp_param_check`,
`fp/fp_param_registry.f90`) and returns 1, with one `XX fp_run: ...` line per
violation on unit 6, for a count the solver cannot run with:

| count | accepted | without the check |
|---|---|---|
| `NRMAX` | 1 to `FP_MAX_NRMAX` (100) | below 1 the mesh set-up ran past an array bound; above 100 the run was made and `fp_get_state` could not return it |
| `NPMAX`, `NTHMAX` | 2 or more | the solver ran past an array bound |
| `LMAXFP` | 0 to `HUGE - 1` | below 0 no pass was made and `fp_loop` tested an error flag that no pass had set; at `HUGE` a step never ended |
| `NSAMAX` | at most `NSBMAX` | an array bound of the collision arrays |
| `NS_NSA(1..NSAMAX)` | 1 to `MIN(NSMAX, NSBMAX)` (0: the slot's own number) | an array bound |
| `NS_NSB(1..NSBMAX)` | 1 to `NSMAX` (0: the slot's own number) | an array bound |

An array bound passed is an abort when the library is built with run-time
checks and undefined behaviour without them. The reason for a refusal is on
unit 6 only: `fp_run` returns the one code. The handle stays usable: correct
the count and call `fp_run` again. Until that run is made, as after any
`fp_set_param` that changes `NRMAX` or `NSAMAX`, the arrays of the last run
keep their old extents: `fp_get_state` copies, along each axis, the lesser
of the current count and the allocated extent, and reports the extents it
copied in `nrmax` / `nsamax`, so the `[nsamax][nrmax]` slice is always data
that exists (#245). A lowered count truncates the snapshot to its leading
slice at once; a raised count stays capped at the old allocation until the
next `fp_run`. Either way the profiles are still those of the last run's
mesh and species, so run before reading them as the new configuration. The
C ABI has no parameter getter, so a raised `NRMAX` / `NSAMAX` is not
observable through `fp_get_state` while its reported extents stay capped.
`fp_get_state` still returns rc=3 while `NRMAX` is above `FP_MAX_NRMAX`.
Before the first run in a process (nothing allocated) it returns the
namelist counts with zero profiles. The arrays are per process, not per
handle (`fp_finalize` keeps them, `fp_init` resets the counts to 1), so a
second handle in the same process that reads before its own first run gets
the previous handle's data truncated to its own counts (a 1 x 1 slice after
`fp_init`), not zeros.

Not checked: a mesh too large for memory, or whose `NRMAX * NPMAX * NTHMAX`
passes a default integer (`NPMAX` and `NTHMAX` have no upper bound); `NPMAX`
or `NTHMAX` of 2, which runs and is too coarse for a result; an evolved
species that no background slot names (`fp_set_nsa_nsb` reports it and the
run is made without that species' collisions with its own kind).

`fp_state_t` carries 5 integer scalars (`nrmax`, `nsamax`, `npmax`,
`nthmax`, `ntg2`), the simulation time `timefp` (double), and six 2-D
profile arrays `RNT`, `RWT`, `RTT`, `RJT`, `RPCT`, `RPWT` of shape
`[FP_MAX_NSAMAX][FP_MAX_NRMAX]` = `[8][100]`. The runtime copy uses
only the `[0:nsamax][0:nrmax]` slice. After the arrays come seven
doubles: six volume-integrated globals summed over the species at the
latest `NTG1` sample, `TOTAL_IP` [MA], `STORED_ENERGY` [MJ],
`COLLISION_POWER`, `ABSORPTION_POWER`, `ABSORPTION_WR`, `ABSORPTION_WM`
[MW], and `PLASMA_VOLUME` [m^3] (`TVOLR`). They are zero until the first
run, and again after a `fp_set_param` until the next run that is made,
while the profiles above are still those of the last run. The
struct grows at its end only, and `fp/fp_state.f90`, `fp/fp_api.h` and
`fplib._ffi.FpStateC` change together with a rebuilt `libfpapi.so`.

### Fortran backend

- `fp_api.f90` owns the BIND(C) wrappers. Each function is a thin
  shim that marshals C arguments into the existing Fortran entry
  points (`fp_init`, `fp_prep`, `fp_loop`, ...) and maps Fortran ierr
  to the C `enum fp_error`.
- `fp_param_registry.f90` implements a hand-written `SELECT CASE`
  dispatch (~40 unique names / ~55 settable variables once array
  subscripts are counted) mapping `"NAME"` or `"NAME[idx]"` strings
  to FPCOMM / PLCOMM module variables. Extending the registry is the
  **only** code change needed to expose new parameters.
- Kernel code (`fp_prep`, `fp_loop`, `fpcalc`, `fpcoef`, ...) is
  unchanged and shared with the `fp` binary.
- `fp_graphics_stubs.f90` provides weak shims for graphics entry
  points (`fpgout`, `fpgsub`, `fpcont`, `fpfout`) so the shared
  library links without pulling PGPlot; the 5 exported C ABI
  functions never reach these paths.

### Python wrapper

- `fplib._ffi.FpStateC` mirrors `fp_state_t` byte-for-byte (padded to
  `FP_MAX_NRMAX=100`, `FP_MAX_NSAMAX=8`).
- `fplib._ffi.load_library` resolves the shared library via
  `FPLIB_PATH` → `fp/libfpapi.so` → `lib/libfpapi.so` and uses
  `RTLD_LAZY` so dangling graphics references never block loading.
- `fplib.Fplib` is a context manager: `__enter__` calls `fp_init`,
  `__exit__` calls `fp_finalize`. All 5 entry points map 1:1 to
  methods. `set_params` accepts scalar, `dict{idx: v}`, or
  `list/tuple` values so array elements can be set without resorting
  to the bracket syntax.
- `fplib.FpState` is a `@dataclass` snapshot; `to_dict()` is
  JSON-serialisable and uses a
  `{"NRMAX": ..., "NSAMAX": ..., "scalars": {"TOTAL_IP": ..., ...}, "profile": [{"NSA": i, "RNT": ...}, ...]}`
  layout so downstream tools can diff wrapper output against `fp`
  CLI runs.

## Phase L completion matrix

| Phase | Deliverable | Plan | Merge PR | Date |
|---|---|---|---|---|
| L-0 | Phase 0 regression baselines (`fp_iter01`, `fp_jt60`, `fp_dt1`) | `2026-04-18-fp-library-L0-baseline.md` | #13 | 2026-04-18 |
| L-1 | Makefile graphics-split (core/graphics/menu) | `2026-04-18-fp-library-L1-graphics-split.md` | #26 | 2026-04-18 |
| L-2 | C ABI foundation (`fp_api.h`, stub exports returning ierr=4) | `2026-04-18-fp-library-L2-c-abi-foundation.md` | #29 | 2026-04-18 |
| L-3 | Parameter registry + real `fp_init/run/get_state/finalize` | `2026-04-18-fp-library-L3-param-registry.md` | #37 | 2026-04-18 |
| L-4 | `libfpapi.so` shared-library build + PIC variants | `2026-04-18-fp-library-L4-shared-lib-build.md` | #43 | 2026-04-18 |
| L-5 | `python/fplib/` ctypes wrapper (`Fplib`, `FpState`, errors) | `2026-04-18-fp-library-L5-python-wrapper.md` | #55 | 2026-04-18 |
| L-6 | 4-layer test suite wired into `run_tests.sh` | `2026-04-18-fp-library-L6-test-4layers.md` | #56 | 2026-04-18 |
| L-7 | Library documentation (this doc, README, examples, CHANGELOG) | `2026-04-18-fp-library-L7-docs.md` | this PR | 2026-04-18 |

## Acceptance criteria status

Mirrors the tr spec's §12.2 for the FP module:

| Criterion | Sub-phase | How to verify |
|---|---|---|
| `libfpapi.so` generated | L-4 | `ls fp/libfpapi.so && file fp/libfpapi.so` |
| `import fplib` works | L-5 | `python3 -c "from fplib import Fplib"` |
| Layer 1 equivalence PASS | L-6 | `test_run/run_tests.sh fplib_equivalence` |
| Layer 2 C ABI PASS | L-6 | `test_run/run_tests.sh fplib_c_abi` |
| Layer 3 Python wrapper PASS | L-6 | `test_run/run_tests.sh fplib_ffi fplib_wrapper` |
| Layer 4 sweep smoke PASS | L-6 | `test_run/run_tests.sh fplib_sweep` |
| `fp` numerics match Phase 0 | L-0..L-6 | `test_run/run_tests.sh fp_iter01 fp_jt60 fp_dt1` |
| `python/fplib/README.md` with examples | L-7 | visual review + `python3 -m py_compile examples/*.py` |
| `run_tests.sh` fplib_* wired | L-6 | `grep fplib_ test_run/test_definitions.conf` |

## Known gaps at L-7 merge

- **`fp_finalize` does not deallocate FPCOMM arrays.** The registry
  ships an asymmetric `fp_allocate` / `fp_deallocate` pair; a single
  `fp_init` / `fp_run` / `fp_finalize` per process is the supported
  lifecycle. Repeated cycles (as in the 3×3 sweep) work in practice
  because `fp_init` resets the necessary SAVE state, but long-running
  processes can leak FPCOMM allocations.
- **String parameters not wired.** `KNAMFP` and similar namelist
  keys cannot flow through the float-only C ABI; they stay at their
  defaults. A follow-up PR with a `fp_set_param_str` entry point is
  tracked separately (mirrors the trlib L-L approach).
- **Compile-time mesh caps.** `FP_MAX_NRMAX=100` and
  `FP_MAX_NSAMAX=8` are baked into the exported `fp_state_t`; runs
  needing larger meshes require bumping the constants in
  `fp/fp_api.h` + `fp/fp_state.f90` and rebuilding `libfpapi.so`.
- **Single instance per process.** FP globals are module-level
  state; two concurrent `Fplib()` instances share FPCOMM.

## References

- Design spec: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
  (FP follows the same pattern; no separate FP spec)
- User README: `python/fplib/README.md`
- Phase plans: `docs/superpowers/plans/2026-04-18-fp-library-L*.md`
- tr counterpart: `docs/tr-library/architecture.md`
- ti counterpart: `docs/ti-library/architecture.md`
- Changelog: top-level `CHANGELOG.md`
