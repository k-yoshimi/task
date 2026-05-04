# totlib — Python wrapper for TASK/TOT (integrated simulator)

`totlib` is a thin `ctypes`-based Python wrapper around
`tot/libtotapi.so`, the in-process shared-library version of the
TASK/TOT integrated transport simulator. It lets scripts drive TOT
calculations from Python without shelling out to the standalone `tot`
binary or going through namelist files.

## Overview

TOT is the **orchestrator (integrated) module** of TASK. It composes
`eq`, `tr`, `fp`, `ti`, `wr`, and `wrx` into a single physics solver,
so its parameter space is the **union** of those six per-module
registries. Same-named parameters across sub-modules (e.g. `RR` lives
in `eq`/`tr`/`ti`/`wrx`; `DT` lives in both `tr` and `ti`) are
disambiguated by a mandatory namespace prefix:

| | Traditional CLI | Library (Phase L) |
|---|---|---|
| Binary | `tot/tot` | `tot/libtotapi.so` |
| Entry | interactive menu | 6 C ABI functions |
| I/O | namelist + ASCII output | in-memory state struct |
| Graphics | PGPlot / Fortran graphics | excluded (graphics stubs) |
| Python | — | `python/totlib` |

The C ABI is defined in `tot/tot_api.h`; the Fortran backend
(`tot/tot_api.f90`, `tot/tot_param_registry.f90`, `tot/tot_state.f90`)
is unchanged Fortran shared with the `tot` binary. `python/totlib`
only wraps the 6 C entry points and marshals a `tot_state_t` struct
into the pure-Python `TotState` dataclass.

No third-party dependencies — Python 3.8+ stdlib only (`ctypes`,
`dataclasses`, `pathlib`, `os`). `numpy` is optional (detected if
present, never required).

## Installation

Build the shared library once:

```bash
cd /path/to/task
make -C tot libtotapi.so
```

This produces `tot/libtotapi.so` plus PIC variants of the dependent
libraries (`lib*_pic.a`, `lib*.so`). The pre-existing non-PIC `*.a`
archives and the `tot` binary are unchanged.

Put the wrapper on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

Optionally point at a library file outside the repository:

```bash
export TOTLIB_PATH=/custom/path/libtotapi.so
```

Library lookup order (first match wins): `TOTLIB_PATH` env var,
`<repo>/tot/libtotapi.so`, `<repo>/lib/libtotapi.so`.

## Quick start

```python
from totlib import Tot

with Tot() as tot:
    # Every name MUST carry a "<ns>:" prefix.
    tot.set_param("eq:RR", 6.5)        # equilibrium major radius [m]
    tot.set_param("tr:DT", 0.01)       # transport time step [s]
    tot.set_param("fp:NSMAX", 2)       # FP species count
    tot.set_param("ti:RR", 6.5)        # TI major radius [m]
    tot.set_param("wrx:RFIN", 170.0)   # WRX RF frequency [GHz]

    # Bulk-set: pass a dict (kwargs cannot contain ':').
    tot.set_params({
        "tr:RA": 2.0,
        "tr:BB": 5.3,
        "eq:RIP": 1.5,
    })

    # L-6 fan-out is wired: tot.run advances tr_api_run; tot.get_state
    # aggregates the TR-authoritative scalars (T, WPT, BETAN, ...).
    tot.run(ntmax=10)
    state = tot.get_state()
```

See `examples/` for runnable scripts (all support `--dry-run`):

- `examples/quickstart.py` — smallest complete invocation
- `examples/parameter_sweep.py` — `eq:RR` × `eq:BB` grid
- `examples/state_dump.py` — single run, `TotState.to_dict()` as JSON

## API reference

### `Tot(lib_path: str | None = None)`

Context manager. `__enter__` calls `tot_init`; `__exit__` / `close()`
calls `tot_finalize`. Only one live instance per process is meaningful
(TOT backend holds global COMMON-block plus per-module module-variable
state).

> **L-6 fan-out wired:** `tot_init` brings up tr + ti + fp + wr (with
> rollback on per-module init failure); `tot_finalize` tears them down
> in reverse order. The wrapper accepts both `OK` and `NOT_IMPL` returns
> for forward compatibility, but the live path is `OK` end-to-end.

### `Tot.set_param(name, value) -> None`

Set one numeric parameter. `name` MUST be `"<ns>:<bare>"`. Validation
runs Python-side first, so missing/unknown prefixes raise
`TotlibInvalidParamError` before any FFI call.

### `Tot.set_param_str(name, value) -> None`

Set one string parameter. At L-3, only the `tr:` and `eq:` namespaces
back string setters (`tr:KNAMEQ`, `eq:KNAMEQ`, etc.). Other namespaces
return `rc=1` and raise `TotlibInvalidParamError`.

### `Tot.set_params(*args, **kwargs) -> None`

Bulk set. **Pass a dict (or iterable of `(name, value)` pairs) as a
positional argument** — Python keyword identifiers cannot contain a
colon, so pure-kwargs cannot express namespaced names:

```python
tot.set_params({"eq:RR": 6.5, "tr:DT": 0.01})
tot.set_params([("fp:NSMAX", 2), ("ti:RR", 6.5)])
```

Each key passes through the same guard as `set_param`.

### `Tot.run(ntmax: int) -> None`

Advance the integrated simulation by `ntmax` steps. L-6 fan-out
invokes `tr_api_run(ntmax)` (the dominant solver and the one whose
state is exposed in `tot_state_t`). `fp_api_run` and `wr_api_run` are
intentionally NOT called here; the cross-module coupling (wr → tr
power deposition, fp → tr current source, etc.) lives in
`totlib.TotPipeline` (L-7a, Python-side) instead of inside
`libtotapi.so`.

### `Tot.get_state() -> TotState`

Snapshot current TOT state into a `TotState` dataclass. Profile arrays
are trimmed to the active runtime slice (`[0:nrmax]` / `[0:nsmax]`),
so trailing zero padding (up to `TOT_MAX_*`) never reaches callers. At
L-6 the orchestrator aggregates the TR-authoritative slots; `ti_present`
/ `fp_present` / `wr_present` stay `0` because those modules are init'd
but their `*_run` is not invoked from `tot_api_run` (the per-module
state is reachable via the per-module wrappers — `from trlib import
Trlib` etc. — or via the L-7a `TotPipeline` orchestrator).

### `Tot.close() -> None`

Idempotent. The context manager calls this automatically.

## Namespace prefix rules (mandatory)

Because TOT unions six per-module registries, every parameter name
passed through `Tot.set_param` / `Tot.set_param_str` / `Tot.set_params`
**must** carry one of the following prefixes:

| Prefix | Backing registry | Examples |
|---|---|---|
| `eq:`  | `eq_param_set`        | `eq:RR`, `eq:BB`, `eq:RIP`, `eq:KNAMEQ` |
| `tr:`  | `tr_param_set`        | `tr:DT`, `tr:NTMAX`, `tr:RR`, `tr:PN[1]` |
| `fp:`  | `fp_param_set`        | `fp:NSMAX`, `fp:DELT` |
| `ti:`  | `ti_param_set`        | `ti:RR`, `ti:DT` |
| `wr:`  | `wrx_param_set` (alias) | `wr:RFIN` |
| `wrx:` | `wrx_param_set`       | `wrx:RFIN`, `wrx:NRAY` |

> **`wr:` is an alias for `wrx:`.** TOT links `wrx/libwr.a` (note: the
> archive lives under `wrx/` despite the name), so the only loadable
> `wr_param_set` symbol in this build is `wrx`'s. `wr:` is therefore
> routed to `wrx_param_set`. To use the real `wr/wr_param_registry`,
> drive `wr/libwrapi.so` directly via `python/wrlib`. See the comment
> header in `tot/tot_param_registry.f90`.

Missing or unknown prefixes are caught Python-side first:

```python
tot.set_param("RR", 6.5)
# -> TotlibInvalidParamError: tot parameter name 'RR' is missing a
#    namespace prefix. tot is the orchestrator: every name must be
#    of the form '<ns>:<name>' where <ns> is one of
#    ('eq', 'tr', 'fp', 'ti', 'wr', 'wrx'). ...
```

Array element syntax follows the per-module convention (e.g.
`tot.set_param("tr:PN[1]", 0.7)`, `tot.set_param("eq:PSIB[0]", 0.0)`).

## `TotState` fields

Matches `tot_state_t` in `tot/tot_api.h`. Full dict layout is
available via `state.to_dict()` (JSON-serialisable; matches the trlib
baseline so cross-comparison tooling works).

| Attribute | Type | Meaning |
|---|---|---|
| `tr_present` | int | 1 if TR sub-module initialized, else 0 |
| `ti_present` | int | 1 if TI sub-module initialized, else 0 |
| `fp_present` | int | 1 if FP sub-module initialized, else 0 |
| `wr_present` | int | 1 if WR sub-module initialized, else 0 |
| `nt`         | int | time-step counter (TR-authoritative) |
| `nrmax`      | int | radial points actually in use |
| `nsmax`      | int | species actually in use |
| `scalars`    | dict[str, float] | 13 integrated plasma scalars |
| `RN`         | list[list[float]] | `[nrmax][nsmax]` density profile |
| `RT`         | list[list[float]] | `[nrmax][nsmax]` temperature profile |
| `AJ`         | list[float]      | `[nrmax]` current density profile |
| `QP`         | list[float]      | `[nrmax]` safety-factor profile |

Scalars (canonical order): `T`, `WPT`, `AJT`, `Q0`, `BETA0`, `BETAP0`,
`BETAA`, `BETAN`, `TAUE1`, `TAUE2`, `ZEFF0`, `ALI`, `RQ1`.

## Exceptions

Every `tot_*` return code maps to a concrete subclass of `TotlibError`:

| rc | class | meaning |
|---|---|---|
| 0 | — | success |
| 1 | `TotlibInvalidParamError` | invalid name (missing prefix / unknown namespace / unknown bare name) |
| 2 | `TotlibNotInitializedError` | API call before `tot_init` |
| 3 | `TotlibCalculationFailedError` | `tot_run` / `tot_get_state` failed |
| 4 | `TotlibNotImplementedError` | stub return (L-3/L-4 `init` / `run` / `get_state` / `finalize`) |

Spec-style aliases (`TotLibError`, `TotLibInvalidParam`,
`TotLibNotInitialized`, `TotLibCalculationFailed`,
`TotLibNotImplemented`) are also exported.

## Migration: `tot` CLI → `totlib.Tot`

| CLI step | `totlib` equivalent |
|---|---|
| edit `eqparm` / `trparm` namelist | `tot.set_param("eq:...", ...)` / `tot.set_param("tr:...", ...)` |
| specify EQDSK file | `tot.set_param_str("eq:KNAMEQ", path)` |
| menu option (run) | `tot.run(ntmax=...)` (L-6+) |
| inspect output file | `tot.get_state()` (L-6+) |
| menu `Q` (quit) | exit context manager / `tot.close()` |
| batch parameter sweep | Python `for` loop with `tot.set_params(...)` |

The wrapper does **not** wrap graphics, file output, or the
interactive menu — those live in `tot/tot` only.

## TotPipeline (L-7a — Python-side scalar coupling)

`TotPipeline` is a thin orchestrator that composes existing per-module
wrappers (`Fplib`, `Trlib`, …) with a hardcoded scalar coupling
registry. It does **not** use `libtotapi.so` — that path is handled by
the legacy `Tot` class above and is left untouched at L-7a.

**When to use which:**

- TR-only transport solver, regression tests against `libtotapi.so` →
  `Tot`
- Multi-module scalar coupling pipelines (e.g. fp driven current → tr) →
  `TotPipeline`
- Direct module access without coupling → `from <mod>lib import <Mod>`

**Same-process coexistence with `Tot` is undefined** — both call
`tr_init` internally on the same Fortran modules. Pick one orchestrator
per process; if you need both, fork via `multiprocessing` or use the
`tot_mcp` `run_pipeline` MCP tool, which force-closes the legacy `Tot`
state on every invocation.

**Example:**

```python
from totlib import TotPipeline

with TotPipeline() as tot:
    tot.set_param("fp:NSAMAX", 2)
    tot.set_param("fp:E0", 0.001)        # active-drive fixture (R3)
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    result = tot.run_pipeline([
        ("fp", {"ntmax": 5}),
        ("tr", {"ntmax": 1}),
    ])
    print(result.last("tr").scalars)
    print(result.last("tr").coupling_applied)
```

**Coupling rules:**

- `fp → tr`: fp's RJT volume integral [A] → tr's `EXTERNAL_DRIVEN_I` [MA]
  (transform `× 1e-6`).

**Rule kinds (L-7b-ii):**

`CouplingRule` には 2 種類がある。`__post_init__` でフィールド検証を行う:

- `kind="transfer"` (デフォルト, L-7a 互換): `src_state_key` →
  `transform` → `set_param` の流れで前段モジュールの状態をスカラー値
  として後段へ渡す。`src_state_key`/`dst_param`/`transform` の 3 つが必須。
- `kind="verify"` (L-7b-ii 新設): 前段ステップ完了後、後段モジュールの
  `verify(curr_inst)` を呼んで真偽値を返す。
  `False` 返却時 → `TotPipelineRunError.__cause__ =
  TotPipelineCouplingError` の **2 段** チェイン
  (元例外がないため `__cause__.__cause__` は None)。
  `verify` 内で例外が送出された場合 → `TotPipelineRunError.__cause__ =
  TotPipelineCouplingError`、`__cause__.__cause__ = 元例外` の
  **3 段** チェイン。`verify` のみ必須。

`("eq","tr")` の verify ルール (BPSD ブローカー経由の equilibrium
受け渡し検証) について — **本リリースでは登録を保留**。
原因: `libeqapi.so` と `libtrapi.so` は別個の共有ライブラリとして
ロードされ、それぞれが BPSD の module-level state
(`___bpsd_equ1d_MOD_equ1dx` ほか) を private に持つため、libeqapi.so
側で `bpsd_put_equ1D` しても libtrapi.so 側の `bpsd_get_equ1D` には
反映されない (`nm` で確認済み)。spec が想定した「BPSD = 共有ブローカー」
の前提が現アーキテクチャでは成立しない。
verify ディスパッチ機構そのものは Layer A モックテストで網羅済みで、
共有 .so / IPC / RTLD_GLOBAL+weak symbols 等の解決方針が決まり次第、
`COUPLING_RULES` に 1 行追加するだけでルールが有効化できる骨組みは
整っている。
レガシーの `Tot` / `libtotapi.so` 経路は eq+tr+bpsd を 1 つの .so に
co-link するため本制約の影響を受けない。

The fp side computes the total driven current via
`compute_rjt_volint(state, R0, a)` (volume integral of `RJT[NSA][NR]`
over the plasma cross-section). The result [A] is converted to MA and
pushed into tr's `EXTERNAL_DRIVEN_I` scalar; tr injects that current
into the transport equation via a Gaussian radial profile
(`EXTERNAL_DRIVEN_R0`, `EXTERNAL_DRIVEN_RW` — defaults 0.0 / 0.3:
axis-peaked, width 30% of minor radius). The Gaussian is normalized
so the integral of AJRF's external contribution equals
`EXTERNAL_DRIVEN_I [MA]` exactly.

Verify the injected total via `tr.get_state().scalars["AJRFT"]`
(total RF + external driven current [MA], includes the
`EXTERNAL_DRIVEN_I` contribution).

**Failure handling:** If a step raises mid-pipeline, the exception is
wrapped as `TotPipelineRunError` whose `partial_result` carries the
steps that completed before the failure. Useful for mid-pipeline
debugging without losing earlier scalars.

**Spec / plan:**

- Spec: `docs/superpowers/specs/2026-04-28-l7a-cross-module-coupling-design.md`
- Plan: `docs/superpowers/plans/2026-04-28-l7a-cross-module-coupling.md`

## Known limitations

- **Single instance per process.** TOT backend uses COMMON blocks plus
  per-module module variables. Two concurrent `Tot()` handles share
  state; the second `tot_init` resets globals. Use `multiprocessing`
  for parallel sweeps — each worker loads its own `libtotapi.so`.
- **Cross-module coupling lives outside the orchestrator.**
  `tot_run(ntmax)` advances `tr_api_run` only — `fp/wr/ti` are init'd
  but their `*_run` is not invoked from the Fortran orchestrator.
  Multi-module pipelines (e.g. fp driven current → tr) are handled at
  the Python layer via `totlib.TotPipeline` (L-7a). For a pure-TR
  transport solve, `Tot()` is enough; for cross-module coupling, use
  `TotPipeline()`.
- **No graphics / MPI / OpenMP API.** Graphics symbols are replaced by
  stubs. The loader uses `RTLD_LAZY`, so unreachable symbols never
  resolve.
- **`wr:` is aliased to `wrx:`.** TOT links `wrx/libwr.a`, so the
  `wr:` prefix is routed through `wrx_param_set`. Use `python/wrlib`
  (not `totlib`) when you need `wr/wr_param_registry` semantics.
- **Unregistered bare names.** Names not in the matching per-module
  registry raise `TotlibInvalidParamError`. New parameters must be
  added on the Fortran side.
- **String parameters** are wired only for `tr:` and `eq:` at L-3.
  Other namespaces will return `rc=1` until they grow a `*_param_set_str`
  entry point.

## Testing

```bash
cd python/totlib/tests
python3 -m unittest discover -v
```

Tests requiring `libtotapi.so` skip automatically when the shared
library is absent. Pure-Python tests (ctypes layout, error wiring,
namespace guard, `TotState.from_c` / `to_dict` shape) always run.

The Phase L-6 4-layer regression suite (`totlib_equivalence`,
`totlib_c_abi`, `totlib_ffi`, `totlib_wrapper`, `totlib_sweep`) is
staged on the L-6 feature branch and will land via its own PR.

## License / contributions

`totlib` is part of the TASK code and follows the repository's
top-level license. Bug reports and PRs are welcome; please keep
wrapper changes minimal — the C ABI is the stable layer, so new
parameters should be added to the matching per-module Fortran registry
first (then they show up automatically through TOT's namespaced
dispatch).

## See also

- `docs/tot-library/architecture.md` — system diagram + Phase L
  completion matrix
- `docs/superpowers/specs/2026-04-17-tr-library-design.md` — Phase L
  design spec (TR template; TOT mirrors it with namespaced dispatch)
- `docs/superpowers/plans/2026-04-18-tot-library-L*.md` — per-phase
  plans
- `tot/tot_api.h` — C ABI header
- `tot/tot_param_registry.f90` — namespaced parameter dispatcher
- `python/trlib/README.md`, `python/eqlib/README.md` — sibling wrapper
  references
- `CHANGELOG.md` — per-phase history
