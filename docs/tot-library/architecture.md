# TASK/TOT library-ization — architecture

Phase L delivered a shared-library + Python-wrapper alternative to the
traditional `tot` CLI for the TASK integrated transport simulator. TOT
is the **orchestrator**: it composes `eq`, `tr`, `fp`, `ti`, `wr`,
and `wrx` into a single physics solver, so its parameter space is the
union of the six per-module registries. The C ABI mirrors the sibling
tr/eq/ti libraries, with one TOT-specific feature: **namespaced
parameter dispatch** in `tot_param_registry.f90`.

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
   |  python/totlib   |  |  <C driver>   |                   |
   |  (ctypes)        |  |  (#include    |                   |
   |                  |  |   tot_api.h)  |                   |
   |  Tot / TotState  |  +-------+-------+                   |
   |  errors / _ffi   |          |                           |
   +--------+---------+          |                           |
            |                    |                           |
            +----------+---------+                           |
                       |                                     |
                       v                                     v
            +-----------------------+               +----------------+
            |   tot/libtotapi.so    |               |   tot/tot      |
            |   (composite .so,L-4) |               |   (CLI binary) |
            |                       |               |                |
            |   6 exported symbols  |               |   menu loop,   |
            |   tot_init / tot_run /|               |   graphics,    |
            |   tot_set_param /     |               |   file I/O     |
            |   tot_set_param_str / |               +-------+--------+
            |   tot_get_state /     |                       |
            |   tot_finalize        |                       |
            +-----------+-----------+                       |
                        |                                   |
                        v                                   v
        +----------------------------------------------------------+
        |  TOT orchestrator backend (Fortran, shared with `tot`)   |
        |                                                          |
        |   tot_api.f90              BIND(C) wrappers              |
        |   tot_param_registry.f90   namespaced dispatch (eq:/tr:/ |
        |                            fp:/ti:/wr:/wrx:)             |
        |   tot_state.f90            BIND(C) tot_state_t           |
        |   totexec.f90              integrated time-advance loop  |
        +-----+----+----+----+-----+-------+----------------------+
              |    |    |    |     |       |
              v    v    v    v     v       v
         +-----+-----+-----+-----+-----+--------+
         |  eq |  tr |  fp |  ti |  wr | wrx    |  6 backing modules
         | _api| _api| _api| _api| _api| _api   |  (each: own C ABI,
         |     |     |     |     |     |        |   own libXXapi.so,
         | _pic| _pic| _pic| _pic| _pic| _pic   |   own python/XXlib)
         +-----+-----+-----+-----+-----+--------+
              |
              v
        +----------------------------------------------------------+
        |  Dependency libraries (PIC + non-PIC variants)            |
        |   lib/ libtask_pic.a    pl/ libpl_pic.a                  |
        |   bpsd/ libbpsd_pic.a   mtxp/ libmtxp_pic.a              |
        |   ob/ libob_pic.a       adpost/ ...                      |
        +----------------------------------------------------------+
```

`libtotapi.so` is a **composite** shared library: it links the six
per-module PIC archives plus the shared dependency libraries (lib/,
pl/, bpsd/, mtxp/, ob/, adpost/, open-adas/...). Loading it via
`ctypes` gives Python access to all six sub-modules through one
namespace.

## Layering

| Layer | Artefact | Purpose |
|---|---|---|
| 0. Regression baseline | `test_run/baselines/tot_*/metrics.json` | Phase L-0 ground truth (`tot_iter01`, `tot_demo2014`) |
| 1. Fortran orchestrator | `tot/tot_api.f90`, `tot_param_registry.f90`, `tot_state.f90`, `totexec` | Numerics / fan-out, shared with the `tot` binary |
| 2. C ABI | `tot/tot_api.h` + BIND(C) exports in `tot_api.f90` | 6 functions, stable contract, namespaced names |
| 3. Shared library | `tot/libtotapi.so` | `make -C tot libtotapi.so`, links the 6 PIC archives + deps |
| 4. Python FFI | `python/totlib/_ffi.py` | `ctypes` mirror of `tot_state_t`, `RTLD_LAZY` loader, namespace constants |
| 5. High-level wrapper | `python/totlib/totlib.py`, `state.py`, `errors.py` | Context manager, dataclass, namespace guard, exception hierarchy |
| 6. User scripts | `python/totlib/examples/*.py`, user notebooks | Quickstart, sweep, state-dump |

### 6 C ABI entry points

From `tot/tot_api.h`:

```c
int tot_init(void);
int tot_run(int ntmax);
int tot_set_param(const char *name, double value);          /* namespaced */
int tot_set_param_str(const char *name, const char *value); /* namespaced */
int tot_get_state(tot_state_t *state);
int tot_finalize(void);
```

Return codes (`enum tot_error`):

| code | meaning | Python exception |
|---|---|---|
| 0 | OK | — |
| 1 | invalid name (incl. missing/unknown namespace prefix) | `TotlibInvalidParamError` |
| 2 | not initialized | `TotlibNotInitializedError` |
| 3 | calculation failed (`tot_run` / `tot_get_state`) | `TotlibCalculationFailedError` |
| 4 | not implemented (L-3/L-4 stubs: `init`/`run`/`get_state`/`finalize`) | `TotlibNotImplementedError` |

`tot_state_t` carries: 4 per-module presence flags (`tr_present`,
`ti_present`, `fp_present`, `wr_present`); 3 grid counters (`nt`,
`nrmax`, `nsmax`); 14 integrated plasma scalars (`T`, `WPT`, `AJT`,
`Q0`, `BETA0`, `BETAP0`, `BETAA`, `BETAN`, `TAUE1`, `TAUE2`, `ZEFF0`,
`ALI`, `RQ1`, `AJRFT`); and 4 profile arrays
(`RN[NRMAX][NSMAX]`, `RT[NRMAX][NSMAX]`, `AJ[NRMAX]`, `QP[NRMAX]`)
padded to `TOT_MAX_NRMAX=500` × `TOT_MAX_NSMAX=8`.

### Namespaced parameter dispatch

`tot_param_registry.f90` is the TOT-specific addition vs the per-module
libraries. Names arriving at `tot_set_param` MUST carry one of six
prefixes:

| Prefix | Backing registry | Notes |
|---|---|---|
| `eq:`  | `eq_param_set`        | numeric + 7 string keys (`eq:KNAMEQ`, ...) |
| `tr:`  | `tr_param_set`        | numeric + 1 string key (`tr:KNAMEQ`) |
| `fp:`  | `fp_param_set`        | numeric only |
| `ti:`  | `ti_param_set`        | numeric only |
| `wrx:` | `wrx_param_set`       | numeric only |
| `wr:`  | `wrx_param_set` (alias) | TOT links `wrx/libwr.a` (note: the archive lives under `wrx/`), so the only loadable `wr_param_set` symbol in this build is wrx's. Use `python/wrlib` to access `wr/wr_param_registry` directly. |

Bare names (no `:`), empty prefixes, and unknown prefixes return
`rc=1`. The Python wrapper catches these *before* the FFI call so the
user gets a precise message instead of a generic `rc=1` from the
Fortran side.

### Python wrapper

- `totlib._ffi.TotStateC` mirrors `tot_state_t` byte-for-byte (padded
  to `TOT_MAX_NRMAX=500`, `TOT_MAX_NSMAX=8`).
- `totlib._ffi.TOT_NAMESPACES = ("eq", "tr", "fp", "ti", "wr", "wrx")`
  — single source of truth for the namespace guard.
- `totlib._ffi.load_library` resolves the shared library via
  `TOTLIB_PATH` → `tot/libtotapi.so` → `lib/libtotapi.so` and uses
  `RTLD_LAZY` so dangling graphics references in any of the six
  backing libraries never block loading. `tot_set_param_str` is
  attached best-effort so import succeeds on pre-L-3 builds; first
  call raises `TotlibError` on such a build.
- `totlib.Tot` is a context manager: `__init__` calls `tot_init`,
  `__exit__` / `close()` calls `tot_finalize`. `Tot._validate_namespaced_name`
  rejects bare / unknown / empty-prefix names up-front.
- `totlib.TotState` is a `@dataclass` snapshot; `to_dict()` is
  JSON-serialisable and adds a top-level `presence` sub-dict noting
  which sub-modules contributed.

## TOT-specific quirks

Three behaviours differ from the sibling tr/ti/wr/fp/eq wrappers:

1. **Mandatory namespace prefix.** Every parameter name must be
   `<ns>:<bare>`. Bare names like `"RR"` are ambiguous (4+ modules
   define one) and are rejected with a precise Python-side error.
2. **`wr:` is aliased to `wrx:`.** TOT links `wrx/libwr.a` — the
   archive named `libwr.a` that lives in the `wrx/` directory — so
   the only `wr_param_set` symbol resolvable inside `libtotapi.so` is
   wrx's. The dispatcher routes `wr:` to `dispatch_wrx` accordingly.
   To use the real `wr/wr_param_registry`, drive `wr/libwrapi.so`
   directly through `python/wrlib`.
3. **String setter is restricted at L-3.** Only `tr:` and `eq:` back
   `tot_set_param_str`. Other namespaces return `rc=1` until their
   per-module registries grow a symmetric `*_param_set_str` entry
   point.

## Phase L completion matrix

| Phase | Deliverable | Plan | Merge PR | Status |
|---|---|---|---|---|
| L-0 | Phase 0 regression baselines (`tot_iter01`, `tot_demo2014`) + `totregress.f90` + `extract_tot_metrics.py` | `2026-04-18-tot-library-L0-baseline.md` | #17 | merged |
| L-1 | Makefile graphics split (`TOT_NO_GRAPHICS` preprocessor guards `GSOPEN`/`GSCLOS`) | `2026-04-18-tot-library-L1-graphics-split.md` | #23 | merged |
| L-2 | C ABI foundation (`tot_api.h`, stub exports returning ierr=4) | `2026-04-18-tot-library-L2-c-abi-foundation.md` | #32 | merged |
| L-3 | Namespaced parameter registry (`tot_param_registry.f90`, dispatch to 6 backing `*_param_set` + `*_param_set_str`) | `2026-04-18-tot-library-L3-param-registry.md` | #82 | merged |
| L-4 | `libtotapi.so` composite shared-library build (links 6 per-module PIC archives + deps) | `2026-04-18-tot-library-L4-shared-lib-build.md` | #85 | merged |
| L-5 | `python/totlib/` ctypes wrapper (`Tot`, `TotState`, errors, namespace guard) | `2026-04-18-tot-library-L5-python-wrapper.md` | #91 | merged |
| L-6 | 4-layer test suite wired into `run_tests.sh` (`totlib_*` cases) | `2026-04-18-tot-library-L6-test-4layers.md` | — | pending |
| L-7 | Library documentation (this doc, README, examples, CHANGELOG) | `2026-04-18-tot-library-L7-optimization.md` (this PR delivers the docs subset) | this PR | open |

> **Note on L-7 plan scope.** The plan filename is "L7-optimization"
> because the original L-7 plan was the parameter-optimization
> workflow (scipy/optuna/grid backends). This PR delivers the
> **documentation** subset (README, examples, architecture diagram,
> changelog) needed before / alongside the optimization workflow.
> The optimization driver (`python/totlib/optimize.py`,
> `objectives.py`, `results.py`, optimization notebooks) remains
> deferred to a follow-up PR.

## Acceptance criteria status

Mirrors the tr spec's §12.2 for the TOT module:

| Criterion | Sub-phase | How to verify |
|---|---|---|
| `libtotapi.so` generated | L-4 | `ls tot/libtotapi.so && file tot/libtotapi.so` |
| `import totlib` works | L-5 | `python3 -c "from totlib import Tot"` |
| `tot_set_param_str` exported | L-3 / L-4 | `nm -D tot/libtotapi.so \| grep tot_set_param_str` |
| Namespace dispatch works | L-3 | `python3 -c "from totlib import Tot; Tot().set_param('eq:RR', 6.5)"` |
| Layer 1 equivalence PASS | L-6 (pending) | `test_run/run_tests.sh totlib_equivalence` |
| Layer 2 C ABI PASS | L-6 (pending) | `test_run/run_tests.sh totlib_c_abi` |
| Layer 3 Python wrapper PASS | L-6 (pending) | `test_run/run_tests.sh totlib_ffi totlib_wrapper` |
| Layer 4 sweep smoke PASS | L-6 (pending) | `test_run/run_tests.sh totlib_sweep` |
| `tot` numerics match Phase L-0 | L-0..L-5 | `test_run/run_tests.sh tot_iter01 tot_demo2014` |
| `python/totlib/README.md` with examples | L-7 | visual review + `python3 -m py_compile examples/*.py` |
| `run_tests.sh` totlib_* wired | L-6 (pending) | `grep totlib_ test_run/test_definitions.conf` |

## Known limitations

- **L-6 not yet merged.** The 4-layer test integration (`totlib_*`
  cases in `test_definitions.conf`) is in flight on its own branch.
  Until L-6 lands, run wrapper tests directly with
  `python3 -m unittest discover python/totlib/tests`.
- **`tot.run()` / `tot.get_state()` are stubs at L-3/L-4.** They
  return `rc=4` (`TotlibNotImplementedError`) until L-6 wires up the
  per-module fan-out (`tr_run` + `ti_run` + `fp_run` + `wr_run` +
  `eq_run` chained, with `tot_state` aggregated from the 4 sub-state
  snapshots). `tot.set_param` / `tot.set_param_str` work fully.
- **Single instance per process.** TOT pulls in COMMON blocks from
  six backing modules. Two concurrent `Tot()` handles share state;
  the second `tot_init` resets globals. Use `multiprocessing` for
  parallel sweeps.
- **`wr:` is aliased to `wrx:`.** The `wr/wr_param_registry` is not
  reachable through `libtotapi.so` — use `python/wrlib` for that.
- **String parameters are wired only for `tr:` and `eq:`** at L-3.
  Other namespaces (`fp:`, `ti:`, `wr:`/`wrx:`) reject string calls
  with `rc=1` until their registries gain a `*_param_set_str` entry
  point.
- **Optimization driver (L-7 follow-up).** The `optimize.py` /
  `objectives.py` / `results.py` modules and the three optimization
  notebooks (Q0 maximize, Pareto front) described in the original
  L-7 plan are deferred; this PR ships only the documentation /
  examples subset.

## References

- Design spec: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
  (TR template; TOT mirrors it with namespaced dispatch and a
  composite shared library)
- User README: `python/totlib/README.md`
- Phase plans: `docs/superpowers/plans/2026-04-18-tot-library-L*.md`
- TR counterpart: `docs/tr-library/architecture.md`
- TI counterpart: `docs/ti-library/architecture.md`
- FP counterpart: `docs/fp-library/architecture.md`
- WR counterpart: `docs/wr-library/architecture.md`
- WRX counterpart: `docs/wrx-library/architecture.md`
- EQ counterpart: `docs/eq-library/architecture.md`
- C ABI header: `tot/tot_api.h`
- Namespaced dispatcher: `tot/tot_param_registry.f90`
- Top-level changelog: `CHANGELOG.md`
