# L-7b-ii: BPSD broker coupling verification (eq → tr) — Design

**Status:** Partial (verify dispatch shipped; ('eq','tr') registry
entry deferred — see §0 below)
**Date:** 2026-05-03 (spec); 2026-05-04 (implementation deferral note)
**Predecessors:** `2026-04-28-l7a-cross-module-coupling-design.md`,
`2026-05-02-l7b-i-external-driven-i-design.md`
**MVP scope:** "A-medium" — eq → tr orchestrator-level verification of
the existing Fortran-side BPSD coupling. New scope is intentionally
narrow; broader L-7b follow-ups (wr coupling, declarative API, state
aggregation) are out-of-scope (§8.1).

---

## §0. Implementation deferral note (2026-05-04)

実装 PR (branch `claude/2026-05-03-l7b-ii-bpsd-broker-coupling`) 投入時
に確認した制約。本 spec の §1〜§9 の記述は変更していないが、
「BPSD = eq/tr 共有ブローカー」の前提が `TotPipeline` (per-module
.so) アーキテクチャでは成立しないことが分かった。

**確認内容**: `nm libeqapi.so` と `nm libtrapi.so` の両方で
`___bpsd_equ1d_MOD_equ1dx` 等の BPSD module-level シンボルが
小文字 `s` (static linkage = .so 内 private) として現れる。よって
libeqapi.so 側の `bpsd_put_equ1D` は libtrapi.so 側の `bpsd_get_equ1D`
が触る `equ1Dx` には到達しない。レガシー `Tot` / `libtotapi.so`
は eq + tr + bpsd を同一 .so に co-link しているため本制約の影響を
受けない。

**この PR で shipped**:
- §2 Fortran helper `tr_check_bpsd_pull` (非破壊、3 スロット pull)
- §3 C ABI + `Trlib.check_bpsd_pull` Python wrapper
- §4 `CouplingRule.kind` / `verify` フィールド + `__post_init__` 検証
- §5 `pipeline.py` の verify ディスパッチ (`kind="verify"` ブランチ)
- §7 Layer A (8 mock テスト) と Layer B (3 unit テスト)

**この PR で deferred**:
- §4 の `("eq","tr")` ルール登録 → `COUPLING_RULES` には未追加
- §7 Layer C (eq+tr 統合テスト) → `TotPipeline` では構造的に
  C-1 が pass しえず、C-3 は誤った理由で pass するため割愛

**有効化に必要な変更**: 共有 BPSD 状態の確立 — 候補は (a) 共有 .so
への再構成、(b) IPC ベース broker、(c) RTLD_GLOBAL + weak symbols
を用いた dlopen 時の symbol unification、(d) per-module .so のまま
明示的な BPSD blob のシリアライゼーション + Python 側受け渡し。
方針が決まり次第、`COUPLING_RULES` に 1 行と Layer C 統合テストを
追加すればルールが有効化される (verify ディスパッチ機構自体は
完了済み)。

ユーザ向けの説明は `python/totlib/README.md` の Coupling rules 節と
`python/trlib/README.md` の "BPSD ブローカー pull 検証" 節 (両方とも
日本語) を参照。

---

## §1. Overview and data flow

`tot.run_pipeline([("eq", ...), ("tr", ...)])` already triggers
`eq.run()` → `tr.run()`, with the inter-module coupling for equilibrium
data (`equ1D`, `metric1D`) flowing through the BPSD broker
inside the Fortran library (eq pushes via `eq/eqbpsd.f90`,
tr pulls via `tr/trbpsd.f90:tr_bpsd_get`). The Python orchestrator has
no current visibility into whether this coupling actually succeeded;
broker failures, wrong pipeline order, or eq-side silent failures
would surface only as downstream tr behavior (default values, NaNs,
or quiet divergence from baselines).

This spec adds an orchestrator-level verification step that fires
between `eq.run()` and `tr.run()`, asserts that all three BPSD slots
that eq pushes (`device`, `equ1D`, `metric1D`) are pullable. (Note:
`plasmaf` is tr's own output to BPSD — pushed by `tr_bpsd_put`, NOT
by eq — so it is intentionally excluded from the eq→tr verify.), and
raises `TotPipelineCouplingError` (existing class) on failure.

```
[eq.run()] ── pushes equ1D, metric1D, device into BPSD (existing, eqbpsd.f90)
       ↓
[orchestrator] ── after eq, before tr, fires ("eq","tr") VERIFY rule
       ↓
[tr_check_bpsd_pull()] ── new C ABI helper; pulls the 3 eq-pushed slots
                          (device, equ1D, metric1D) into LOCAL discardable
                          types; reports ok = (all 3 ierr==0). plasmaf is
                          NOT checked: it is tr's own BPSD output, pushed
                          by tr_bpsd_put on a previous run, so a fresh
                          [eq, tr] pipeline would spuriously fail a
                          plasmaf check.
       ↓
[orchestrator] ── if ok: continue to tr.run(); if not: raise CouplingError
                  (wrapped by run_pipeline's broad except into RunError)
       ↓
[tr.run()] ── existing flow, re-pulls equ1D/metric1D into TRCOMM
```

### MVP scope clarification

In scope:
- ✅ New non-mutating Fortran helper `tr_check_bpsd_pull` (one-way query)
- ✅ C ABI export + Python wrapper
- ✅ `CouplingRule` extended with `kind` and `verify` fields
- ✅ Single new entry in `COUPLING_RULES` for `("eq","tr")`
- ✅ Test coverage: Layer A (mock dispatch) + Layer B (unit) are
  unconditional MVP. Layer C (integration) is conditionally included
  based on plan-time `Eq` wrapper sufficiency check (§8.4 risk #2);
  if dropped, it ships in a follow-up PR. See AC6.
- ✅ Doc updates in `python/totlib/README.md` and `python/trlib/README.md`

Out of scope (see §8 for full list):
- ❌ Any new `<mod>_api_bpsd_sync()` ABI on either eq or tr
- ❌ BPSD speaker wiring for wr/wrx/fp/ti (deferred to later L-7b phases)
- ❌ Declarative `tot.couple()` runtime API (L-7b-iii)
- ❌ Per-module state aggregation (L-7b-iv)

### New code estimate

| Component | Lines |
|---|---|
| Fortran (`tr/tr_api.f90` + `tr/tr_api.h`) | ~30 |
| Python wrapper (`python/trlib/_ffi.py` + `trlib.py`) | ~30 |
| `CouplingRule` extension + dispatch (`python/totlib/pipeline.py`) | ~25 |
| New `("eq","tr")` rule entry | ~10 |
| Tests (3 layers, 11 cases) | ~245 |
| Doc updates | ~30 |

---

## §2. Fortran additions

### `tr/tr_api.f90` — new non-mutating helper

```fortran
!  --- L-7b-ii: BPSD broker round-trip verification ---------
!  Pull the 3 eq-pushed BPSD slots (device, equ1D, metric1D) into
!  LOCAL discardable types and report ok = (all per-slot ierr == 0).
!  plasmaf is intentionally NOT pulled: it is tr's own BPSD output
!  (via tr_bpsd_put), absent on a fresh eq->tr pipeline.
!  Non-mutating: TRCOMM is untouched; safe to call before or after
!  tr.run(). Per-slot ierr are accumulated to avoid masking earlier
!  failures by later successes.
SUBROUTINE tr_check_bpsd_pull(ok) BIND(C, NAME="tr_check_bpsd_pull")
  USE iso_c_binding, ONLY: c_int
  USE bpsd, ONLY: bpsd_get_data
  USE bpsd_types, ONLY: bpsd_device_type, bpsd_equ1D_type,  &
                         bpsd_metric1D_type
  INTEGER(c_int), INTENT(OUT) :: ok
  TYPE(bpsd_device_type)    :: dev_local
  TYPE(bpsd_equ1D_type)     :: eq_local
  TYPE(bpsd_metric1D_type)  :: met_local
  INTEGER :: ierr_dev, ierr_eq, ierr_met

  CALL bpsd_get_data(dev_local, ierr_dev)
  CALL bpsd_get_data(eq_local,  ierr_eq)
  CALL bpsd_get_data(met_local, ierr_met)

  IF (ierr_dev == 0 .AND. ierr_eq == 0 .AND. ierr_met == 0) THEN
    ok = 1
  ELSE
    ok = 0
  END IF
END SUBROUTINE tr_check_bpsd_pull
```

**Key properties:**
- Local types are `TYPE(...)` declarations on the stack — no allocation
  required from the caller; BPSD's `bpsd_get_data` is expected to
  allocate any internal arrays in the destination type as needed.
  (Implementation risk if BPSD requires pre-allocated destinations:
  see §8.4 for fallback.)
- TRCOMM is never touched, so `tr.run()` afterwards proceeds with its
  natural state (no double-pull-overwrite risk).
- Each `bpsd_get_data` call writes its own `ierr_*`; the final `ok`
  is computed from the AND of all three. No masking by last-write.

### `tr/tr_api.h` — C prototype

```c
/* L-7b-ii: BPSD broker round-trip verification.
 * Returns *ok = 1 on successful pull of the 3 eq-pushed BPSD slots
 * (device, equ1D, metric1D); 0 otherwise. plasmaf is intentionally
 * excluded -- it is tr's own BPSD output, absent on a fresh eq->tr
 * pipeline. Non-mutating: pulls into local discardable types, does
 * not change tr_state. */
void tr_check_bpsd_pull(int *ok);
```

### ABI impact

`TR_STATE_ABI_VERSION` (currently 2 from L-7b-i) is **not** bumped —
no change to `tr_state_t`. Only a new symbol is added.

---

## §3. Python wrapper

### `python/trlib/_ffi.py` — ctypes prototype

```python
lib.tr_check_bpsd_pull.argtypes = [ctypes.POINTER(ctypes.c_int)]
lib.tr_check_bpsd_pull.restype  = None
```

Add to the existing `load_library` prototype-attachment block.

### `python/trlib/trlib.py` — `Trlib.check_bpsd_pull`

```python
def check_bpsd_pull(self) -> bool:
    """Verify that BPSD has the 3 eq-pushed slots (device, equ1D,
    metric1D) by performing a non-mutating round-trip pull into
    local discardable types. plasmaf is excluded: it is tr's own
    BPSD output, absent on a fresh eq -> tr pipeline.

    Used by TotPipeline as a pre-tr-run verification of the eq -> tr
    BPSD coupling: after eq.run() pushes equ1D/metric1D into BPSD,
    a False return signals broker failure / missing eq step / wrong
    pipeline order. TRCOMM is unaffected.
    """
    if self._closed:
        raise TrlibError("check_bpsd_pull on closed Trlib")
    ok = ctypes.c_int(0)
    self._lib.tr_check_bpsd_pull(ctypes.byref(ok))
    return ok.value == 1
```

**Granularity** is intentionally coarse (single bool). Future
per-slot reporting is a future enhancement (§8.3).

---

## §4. `CouplingRule` extension

### `python/totlib/pipeline.py` — dataclass changes

Existing fields stay; two new fields are added; existing transfer
rules continue to work unchanged (defaults preserve their semantics).

```python
@dataclass(frozen=True)   # preserved from existing definition
class CouplingRule:
    # --- existing transfer-rule fields (kind="transfer") ---
    # All three are required for kind="transfer" but defaulted to
    # None so kind="verify" rules can omit them.
    src_state_key: Optional[Callable] = None
    dst_param: Optional[str] = None
    transform: Optional[Callable] = None
    doc: str = ""
    # --- L-7b-ii: rule kind + verify-only callable ---
    kind: str = "transfer"          # "transfer" | "verify"
    verify: Optional[Callable[[Any], bool]] = None
    #   verify(dst_inst) -> bool
    #   only consulted when kind == "verify"

    def __post_init__(self):
        if self.kind == "transfer":
            missing = [
                name for name, val in (
                    ("src_state_key", self.src_state_key),
                    ("dst_param",     self.dst_param),
                    ("transform",     self.transform),
                ) if val is None
            ]
            if missing:
                raise ValueError(
                    f"transfer-kind CouplingRule missing required "
                    f"fields: {missing}"
                )
        elif self.kind == "verify":
            if self.verify is None:
                raise ValueError(
                    "verify-kind CouplingRule requires verify callable"
                )
        else:
            raise ValueError(f"unknown CouplingRule.kind: {self.kind!r}")
```

**Note on `frozen=True`**: The existing dataclass is frozen for
hashability and accidental-mutation guards. `__post_init__` only
raises `ValueError` and never assigns to `self.*`, so frozen
remains compatible.

**Why kind+verify (vs separate `VerificationRule` dataclass)?** MVP
prioritizes minimal infrastructure churn (1 dataclass field + 1
optional callable + 1 dispatch branch) over type-level cleanliness.
Trigger conditions for the future `VerificationRule` split are listed
in §8.3.

### New entry in `COUPLING_RULES`

```python
COUPLING_RULES: Dict[Tuple[str, str], List[CouplingRule]] = {
    ("fp", "tr"): [...existing EXTERNAL_DRIVEN_I rule from L-7b-i...],
    ("eq", "tr"): [
        CouplingRule(
            kind="verify",
            verify=lambda tr_inst: tr_inst.check_bpsd_pull(),
            doc=(
                "eq -> tr equilibrium coupling via BPSD broker "
                "(verifies device + equ1D + metric1D; plasmaf is "
                "tr's own BPSD output and intentionally excluded). "
                "Verified pre-tr-run; raises TotPipelineCouplingError "
                "if BPSD lacks any expected slot."
            ),
        ),
    ],
}
```

### Backward compatibility

Existing `("fp","tr")` rule omits `kind` → defaults to `"transfer"` →
behavior unchanged. `__post_init__` validation accepts the existing
shape because `src_state_key` and `dst_param` are still set.

---

## §5. `pipeline.py` dispatch

The existing rule-firing loop in `run_pipeline` (around
`pipeline.py:425-438`) gains a kind-aware dispatch.

```python
for rule in COUPLING_RULES.get((prev_name, name), []):
    if rule.kind == "transfer":
        # Existing logic: extract -> transform -> set_param -> record.
        # __post_init__ guarantees src_state_key/dst_param/transform
        # are non-None for kind="transfer", so the asserts below are
        # type-narrowing for static checkers (mypy/pyright) and
        # documentation for readers; they are unreachable at runtime.
        raw = self._extract_source(prev_state, rule)
        assert rule.transform is not None    # type narrowing
        assert rule.dst_param is not None    # type narrowing
        try:
            transformed = rule.transform(raw)
        except Exception as e:
            raise TotPipelineCouplingError(
                f"transform failed for rule {rule.doc!r}: {e}"
            ) from e
        module.set_param(rule.dst_param, transformed)
        self._params[f"{name}:{rule.dst_param}"] = transformed
        applied.append(rule.doc)
    elif rule.kind == "verify":
        assert rule.verify is not None    # type narrowing (see transfer branch)
        try:
            ok = rule.verify(module)   # module = curr_inst
        except Exception as e:
            raise TotPipelineCouplingError(
                f"verify failed: rule {rule.doc!r} for "
                f"{prev_name}->{name} raised "
                f"{type(e).__name__}: {e}"
            ) from e
        if not ok:
            callable_repr = getattr(
                rule.verify, "__qualname__", repr(rule.verify)
            )
            raise TotPipelineCouplingError(
                f"verify failed: rule {rule.doc!r} ({callable_repr}) "
                f"for {prev_name}->{name} returned False "
                f"(likely cause: upstream step did not push expected "
                f"data to BPSD broker; check pipeline order and "
                f"MODELG setting)"
            )
        applied.append(rule.doc)   # only on success
```

### Design notes

- `verify(curr_inst)` receives only the dst instance. Future generalization
  to `(src_inst, dst_inst, params)` is left as a follow-up (§8.3).
- `applied.append(rule.doc)` runs **only on success** for verify rules,
  matching transfer-rule semantics where `applied` is a "succeeded"
  snapshot, not "attempted" (`PipelineStep.coupling_applied`).
- Unknown `kind` is rejected at construction time by `__post_init__`,
  so the dispatch needs no `else` branch.
- Both `raise TotPipelineCouplingError(...)` paths flow through the
  existing broad `except Exception` at `pipeline.py:449` and become
  `TotPipelineRunError(__cause__=CouplingError, partial_result=...)`.
  See §6 for the full exception chain.

---

## §6. Failure semantics

### No new exception class

`TotPipelineCouplingError` already exists at `python/totlib/errors.py:99`
as a sibling of `TotPipelineRunError`. It is currently used for
transform failures (`pipeline.py:431`); we extend its use to verify
failures with no class-level changes.

### Three-level exception chain

When verify fails (either by raising or returning False):

1. `TotPipelineCouplingError` raised inside the step loop (§5)
2. Caught by the broad `except Exception` at `pipeline.py:449`
3. Re-raised as `TotPipelineRunError` with:
   - `partial_result=PipelineResult(steps=result_steps)` — eq's
     completed step is preserved
   - `failed_step_index=i`, `failed_module=name`
   - `__cause__` = the `TotPipelineCouplingError`

The user-visible chain in tracebacks is:

```
TotPipelineRunError("step 1 (tr) failed: verify failed: rule 'eq -> tr ...' returned False ...")
    .__cause__ = TotPipelineCouplingError("verify failed: rule ... returned False (likely cause: ...)")
        .__cause__ = (only present when verify itself raised) TrlibError(...) or similar
    .partial_result = PipelineResult([PipelineStep(module="eq", scalars=..., coupling_applied=[])])
```

### Error message format

```
verify failed: rule {rule.doc!r} ({callable_repr}) for {prev}->{curr} returned False (likely cause: ...)
```

where `callable_repr = getattr(rule.verify, "__qualname__", repr(rule.verify))`
(see §5 dispatch). Falls back to `repr(verify)` for `functools.partial`
or other callables without `__qualname__`.

- `verify failed:` prefix improves `pytest -x` one-liner scannability
- Includes src→dst pair + full doc + verify callable qualname for debug
- Distinguishes "raised exception" vs "returned False" failure modes
- Includes actionable hint (pipeline order, MODELG)

### Disambiguation note

Multiple rules per `(src,dst)` pair are not currently supported by
the failure message format (rule index would clarify but is omitted
in MVP). All current pairs have ≤ 1 rule each. If 2+ rules per pair
arise in the future, add `f"rule[{idx}]"` to the format.

---

## §7. Test strategy

Three layers, 11 total cases (C-2 documented for completeness but not
implemented — see Layer C table). All use `pytest`; no new framework
dependencies.

### Layer A: Mock-based dispatch tests

**File:** `python/totlib/tests/test_pipeline_verify.py` (new)
**Dependencies:** None (no `.so` required). Follows existing
`patch_wrappers` pattern (`test_pipeline.py:20`) and
`monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", ...)` pattern
(`test_pipeline.py:305`).

| Case | What it tests |
|---|---|
| A-1 | verify True → rule recorded in `coupling_applied == [rule.doc]` |
| A-2 | verify False → `TotPipelineRunError` raised, `__cause__` is `TotPipelineCouplingError`, `applied` does NOT include the rule (Codex MED on §6 review) |
| A-3 | verify raises → `TotPipelineRunError` raised, 3-level chain: `TotPipelineRunError.__cause__ == TotPipelineCouplingError`, `TotPipelineCouplingError.__cause__ == OriginalError` |
| A-4 | mixed transfer + verify rules in one pair → both fire in declaration order (existing iter is `for rule in rules` per `pipeline.py:426`) |
| A-5 | `CouplingRule.__post_init__` validation: `kind="verify"` + `verify=None` → `ValueError`; `kind="transfer"` + `src_state_key=None` → `ValueError`; unknown kind → `ValueError` |
| A-6 | unregistered pair (e.g. `("eq","wr")`) → silent skip, no exception, `coupling_applied == []` (regression for existing `pipeline.py:426` `.get(..., [])` path) |

~95 lines. < 1 s. CI all platforms.

### Layer B: Unit test for `Trlib.check_bpsd_pull`

**File:** `python/trlib/tests/test_bpsd_check.py` (new)
**Dependencies:** `tr/libtrapi.so` required (existing skipif pattern
from `test_validate.py:45`).

| Case | What it tests |
|---|---|
| B-1 | Fresh `Trlib()` init alone → `check_bpsd_pull() == False` (BPSD slots empty, `tr_init` does not pre-populate; verified at `tr/trbpsd.f90:18` and `tr/tr_api.f90:82` per Codex Q3) |
| B-2 | Closed Trlib → `TrlibError("check_bpsd_pull on closed Trlib")` raise (lifecycle guard) |
| B-3 | Smoke: function does not leak Fortran-side exceptions to Python |

~50 lines. < 1 s.

### Layer C: Integration test with real `eq` + `tr`

**File:** `python/totlib/tests/test_pipeline_eq_tr_verify.py` (new)
**Dependencies:** `eq/libeqapi.so` + `tr/libtrapi.so` + eqdata file.
Uses `pytest.mark.skipif` keyed on file presence (mirrors
`test_equivalence.py:201` pattern):

```python
EQDATA = REPO / "test_run/test_output/tot_demo2014_short/eqdata.demo2014"
LIBEQ  = REPO / "eq/libeqapi.so"
LIBTR  = REPO / "tr/libtrapi.so"
pytestmark = pytest.mark.skipif(
    not (EQDATA.exists() and LIBEQ.exists() and LIBTR.exists()),
    reason="requires eqdata.demo2014 + libeqapi.so + libtrapi.so",
)
```

| Case | What it tests |
|---|---|
| C-1 | pipeline `[("eq", ...), ("tr", ...)]` with MODELG=3 → success; `coupling_applied` contains the verify rule's doc |
| C-2 | pipeline `[("tr", ...)]` only — does NOT exercise verify (prev_name=None, no rule fires); covered by Layer A-2. Drop from MVP. |
| C-3 | MODELG=0 + pipeline `[("eq", ...), ("tr", ...)]` → `TotPipelineRunError(__cause__=TotPipelineCouplingError)`; pin "MODELG=0 + eq→tr is unsupported (verify catches missing equ1D)" as the design assertion. |

~100 lines. Estimated < 5 s (to be measured at plan time; see §8.4).

### MODELG fixture

Extend existing `python/totlib/tests/fixtures/tot_demo2014_params.py`
(per Codex Q5 on §7 review) rather than creating a new
`eq_tr_modelg3.py`. The existing fixture already sets
`eq:KNAMEQ="eqdata.demo2014"`; add `tr:MODELG=3` if not already present.

### CI runtime

| Layer | Cases | Runtime |
|---|---|---|
| A | 6 | < 1 s |
| B | 3 | < 1 s |
| C | 2 (C-1, C-3) | < 5 s (to be measured) |

Existing Layer 1 baselines (demo2014/ht6m at 1e-10) are unaffected:
verify is orchestrator-level only; no Fortran-level numerics change.

---

## §8. Non-goals and Roadmap

### §8.1 Out-of-scope (clear deferrals)

- **L-7b-iii** — declarative `tot.couple(src, dst, rule)` runtime API.
  Current `COUPLING_RULES` is import-time hard-coded.
- **L-7b-iv** — per-module state aggregation
  (`tot.get_state().fp_scalars` etc.) including additional scalar
  exposure (AJOHT/AJBST/AJNBT current-balance series, recommended
  by `2026-05-02-l7b-i-external-driven-i-design.md` Non-goals
  section as part of L-7b-iv).
- **wr/fp/ti への BPSD ABI 追加** — `<mod>_api_bpsd_sync()` 等を
  追加して wr/wrx/fp/ti を BPSD speaker 化する作業全般。
  L-7b-i Non-goals section が L-7b-ii 非ゴールとして明記済。
  MVP は **eq/tr 1 ペアのみ**。

### §8.2 Pending evaluation

- **wr-side BPSD speaker 化 vs Python state-extract の方式選定** —
  L-7a の divergence risk 判断 (Python rho/psi reimplementation
  → BPSD broker 採用、`2026-04-28-l7a-cross-module-coupling-design.md`
  Goals/Non-goals section) は維持。
  - L-7b-i の Python state-extract pattern は scalar 限定で動作確認済
  - profile (radial array) 系 coupling での同等性は未検証
  - **Re-evaluation trigger**: wr Python state-extract が BPSD 経由
    の同等 coupling と **1e-10 (or 物理許容範囲) で数値一致する
    実測データ** が得られた場合のみ、L-7a の判断を再検討する。それ
    以前は L-7a 方針を保持
  - 方式選定は別 spec で改めて議論

### §8.3 Future enhancements (MVP 後の hardening)

- **`VerificationRule` 別 dataclass 分割** — `CouplingRule.kind` overload
  の type debt 解消。
  Trigger criteria (count alone is a smell, not the criterion):
  - distinct lifecycle (verify と transfer の発火タイミングが
    semantically 分離してきた)、または
  - multiple result severities (error / warning / info)、または
  - cross-step state comparisons (verify が複数 step の state を
    比較する必要)、または
  - reusable diagnostics infrastructure (verify 専用 reporter 等)

  Operational note: trigger 判定は実装 PR の author が行い、
  reviewer が acceptance review で確認。
- **MODELG-aware rule conditional registration** — verify rule が
  MODELG を見て fire/skip する設計。MVP は unconditional fire +
  CouplingError raise on missing data
  (本 spec §7 Layer C "MODELG=0 raises CouplingError" testcase
  で acceptance criterion として pin 済)。
- **`check_bpsd_pull_detail() -> dict[str, bool]`** — どの BPSD slot
  が欠けたかの per-slot reporting。MVP は bool only。debug が困難
  になった時点で追加。
- **BPSD time-step freshness verification** — BPSD type は `time`
  field を持つが orchestrator-level の freshness check は無い。
  multi-time-step pipeline で time skew が問題化した時点で追加。
- **rho-grid interpolation step** — 将来の wr→tr Python state-extract
  で必要になる。L-7b-ii MVP は eq→tr verify のみで grid mismatch を
  回避。

### §8.4 Implementation risks (plan-time 解決、fallback 付き)

- **`bpsd_get_data` の destination type 要件**
  Risk: local の uninitialized type に直接 pull できるか。
  Fallback: helper 内で local type の必要 array (e.g. `rho`,
  `psit`, etc.) を `ALLOCATABLE` 宣言 + `ALLOCATE` 前置。
  サイズは BPSD 既存 caller (eq/eqbpsd, tr/trbpsd) のパターンを
  借用。Impact: helper が ~10 行膨らむのみ、design 不変。

- **`python/eqlib/Eq` wrapper の API 充足度**
  Risk: Layer C で `[("eq", ...), ("tr", ...)]` pipeline に必要な
  `set_param` / `set_param_str` / `run` / `get_state` が揃って
  いるか (Codex Q1: Eq wrapper は `python/eqlib/__init__.py:22`
  に exists、ただし `set_param_str` 等の有無は plan time 確認要)。
  Fallback: 不足時は Layer C を MVP から drop、Layer A+B のみで
  commit、follow-up PR で `Eq` wrapper を補強してから Layer C を追加。

- **Layer C 実行時間 (< 5 s) の実測**
  Risk: 推定値、未測定。
  Fallback: > 5 s だった場合、test を fast/dispatch-only と
  slow/real-run に split、slow を `@pytest.mark.slow` で gating
  (CI nightly only)。

- **BPSD source/build availability**
  Risk: `../bpsd/` clone が build 環境に無い場合 (例: 縮小 CI
  runner、貢献者の初回 clone)。
  Fallback: Layer A/B のみ実行 (mock + compile-only)、Layer C
  (real-lib eq+tr run) は `@pytest.mark.slow` gate で nightly CI
  に限定 or BPSD 提供環境を持つ runner に hard-skipif。L-7a が
  同種の lib-availability skip pattern を確立済。

- **Stale BPSD slot data across tests/runs**
  Risk: BPSD persists data put by a previous tr.run() (or earlier
  test in the same process). A pullability check can pass against
  STALE slots even if the current pipeline's eq.run() failed silently.
  - Layer B is unaffected: B-1 starts in a fresh process where BPSD
    is empty (per Codex Q3 confirmation: tr_init does not pre-populate)
  - Layer A is unaffected: it uses mocks, no real BPSD interaction
  - Layer C may be affected: multiple tests in the same process
    share BPSD state
  Fallback: Layer C tests use `--forked` (existing pytest-forked
  pattern in the repo per CLAUDE.md) for per-test process isolation,
  OR explicitly reset BPSD between tests via a fixture finalizer
  (mechanism to be specified at plan-time). Spec assumption: each
  Layer C test starts from a clean BPSD broker.

### §8.5 Explicit assumptions (MVP の前提)

- **eq → tr は single-step pipeline** (multi-time-step での time skew
  検出は wr/fp time-evolving sources 導入時に再検討)。
  Consequence if violated: §7 Layer C テストに freshness/time-skew
  check を追加し、§8.3 BPSD time-step freshness verification を MVP
  に昇格。

- **新 sync ABI 追加なし** (one-way query helper のみ)。
  Consequence if violated: 別 spec で sync ABI 設計が必要。

- **MVP scope は eq → tr 1 ペアのみ**。
  Consequence if violated: 別 spec で wr/fp/ti coupling design が
  必要 (BPSD speaker 化 vs Python state-extract の選定含む、
  §8.2 Re-evaluation trigger 参照)。

---

## Acceptance criteria

This spec is implemented when:

1. `tr/libtrapi.so` exports `tr_check_bpsd_pull` (Fortran + C ABI)
2. `Trlib.check_bpsd_pull()` returns False from a fresh `Trlib()` init
3. `("eq","tr")` rule is registered in `COUPLING_RULES` with
   `kind="verify"`
4. Layer A test cases (A-1 through A-6) all pass
5. Layer B test cases (B-1 through B-3) all pass
6. Layer C decision is **plan-time** (not post-MVP): if `Eq` wrapper
   is sufficient (set_param/set_param_str/run/get_state present per
   §8.4 risk #2), Layer C cases C-1 and C-3 must pass when libs +
   eqdata are present and skip cleanly otherwise. If `Eq` wrapper
   is insufficient, Layer C is removed from MVP scope and AC6 is
   satisfied by Layer A+B alone (follow-up PR adds Layer C after
   `Eq` wrapper is extended). The drop decision is made at plan
   creation, before implementation begins.
7. `python/totlib/README.md` documents the new `("eq","tr")` rule
8. Existing Layer 1 baselines (demo2014, ht6m at 1e-10) unchanged
9. CLAUDE.md pre-push gate passed (local pytest + 2 reviewer agents +
   REVIEW_OK marker)

---

## References

- Predecessor spec: `docs/superpowers/specs/2026-04-28-l7a-cross-module-coupling-design.md`
- Predecessor spec: `docs/superpowers/specs/2026-05-02-l7b-i-external-driven-i-design.md`
- BPSD source (external clone): `../bpsd/bpsd_*.f90`
- Existing tr BPSD code: `tr/trbpsd.f90`, `tr/trbpsd-mod.f90`
- Existing eq BPSD code: `eq/eqbpsd.f90`, `eq/equnit.f90`
- Existing pipeline: `python/totlib/pipeline.py`, `python/totlib/errors.py`
