# L-7b-ii BPSD Broker Coupling Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add orchestrator-level verification of the eq → tr BPSD coupling so that broker failures, wrong pipeline order, and silent eq-side failures surface as `TotPipelineCouplingError` immediately, rather than as quiet downstream tr divergence.

**Architecture:** New non-mutating Fortran helper `tr_check_bpsd_pull` pulls the 3 eq-pushed BPSD slots (`device`, `equ1D`, `metric1D`) into local discardable types and reports `ok=(all 3 ierr==0)`. Exposed via C ABI and Python wrapper. `CouplingRule` dataclass gains `kind` and `verify` fields; `pipeline.py` dispatches by kind. New `("eq","tr")` verify rule entry fires between eq.run() and tr.run(). 3-layer test (mock dispatch + unit + integration) ensures regression coverage.

**Tech Stack:** Fortran (gfortran, free-form F90, BIND(C) interop), Python 3.10+ (ctypes + dataclasses), pytest. macOS local build needs `make -C tr GFLIBS=""` override (Linux CI defaults to empty).

**Spec:** `docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md` (commit `bdc09131`)

**Predecessor:** L-7b-i PR #187 (squash-merged `e049a1e4`) established the same 4-phase commit pattern, the `EXTERNAL_DRIVEN_I` scalar plumbing, and the existing `CouplingRule` shape this plan extends.

**PR phases (= 3 commit boundaries):**
- **Phase 1 — Commit 1**: Fortran helper + C ABI export + Python wrapper (`Trlib.check_bpsd_pull`)
- **Phase 2 — Commit 2**: `CouplingRule` extension (`kind`/`verify` + `__post_init__`) + pipeline dispatch + new `("eq","tr")` rule entry
- **Phase 3 — Commit 3**: 3-layer test (Layer A 6 cases mock, Layer B 3 cases unit, Layer C 2 cases integration) + README updates
- **Phase 4 — Pre-push gate (CLAUDE.md)**: pytest sweep + 2 reviewer agents (parallel) + REVIEW_OK marker + feature branch push + PR open

**Plan-time risks already resolved (spec §8.4):**
- Risk #1 (`bpsd_get_data` pre-alloc): NOT triggered. `bpsd_get_*` is `INTENT(INOUT)` and self-allocates when destination's `nrmax` field is 0. Helper must explicitly set `local%nrmax = 0` before each call.
- Risk #2 (`Eq` wrapper sufficiency): NOT triggered. `python/eqlib/eqlib.py` exposes `set_param`, `set_param_str`, `run`, `get_state`. Layer C is in scope.
- Risk #4 (BPSD source/build availability): handled via `pytest.mark.skipif` on file presence; CI staging confirmed at L-7b-i precedent.

**Plan-time risk DEFERRED to implementation:**
- Risk #3 (Layer C runtime): unmeasured; if > 5 s, gate Layer C with `@pytest.mark.slow`.

---

## Phase 0 — Setup feature branch

### Task 0.1: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Verify clean working tree on chore branch**

```bash
git status
```

Expected: only untracked files from prior session leftovers (`.worktrees/`, `docs/doc-design/`, `docs/slides/`, `python/mcp-servers/tr_mcp/setup_cli.py`, etc.). No modified tracked files.

- [ ] **Step 2: Verify chore branch tip matches spec**

```bash
git log --oneline -5
```

Expected first line: `bdc09131 docs(plan): add L-7b-ii BPSD broker coupling implementation plan`

- [ ] **Step 3: Create and switch to feature branch**

```bash
git checkout -b claude/2026-05-03-l7b-ii-bpsd-broker-coupling
```

Expected: `Switched to a new branch 'claude/2026-05-03-l7b-ii-bpsd-broker-coupling'`

---

## Phase 1 — Fortran helper + C ABI + Python wrapper

**Goal of phase:** introduce `tr_check_bpsd_pull` non-mutating helper, expose via C ABI and Python wrapper. End of phase: `make -C tr libtrapi.so` succeeds, `Trlib().check_bpsd_pull()` returns `False` (BPSD slots empty by default), existing trlib tests still pass.

### Task 1.1: Add `tr_check_bpsd_pull` subroutine to `tr/tr_api.f90`

**Files:**
- Modify: `tr/tr_api.f90` (add to PUBLIC list at line 48; add new SUBROUTINE near other helpers)

- [ ] **Step 1: Read current PUBLIC list to confirm insertion point**

```bash
sed -n '46,52p' tr/tr_api.f90
```

Expected: shows `PUBLIC :: tr_api_init, tr_api_run, tr_api_get_state, ...` declaration.

- [ ] **Step 2: Add `tr_check_bpsd_pull` to PUBLIC list**

Edit `tr/tr_api.f90`. Append `tr_check_bpsd_pull` to the PUBLIC list (line 48 area). For example, change:

```fortran
  PUBLIC :: tr_api_init, tr_api_run, tr_api_get_state, &
            tr_api_validate, ...
```

to:

```fortran
  PUBLIC :: tr_api_init, tr_api_run, tr_api_get_state, &
            tr_api_validate, ..., &
            tr_check_bpsd_pull
```

(Read the actual current list and insert the new symbol; preserve continuation style.)

- [ ] **Step 3: Add SUBROUTINE body**

Edit `tr/tr_api.f90`. Insert this subroutine in the file (location: after `tr_api_validate` body or before `END MODULE`, follow existing file convention):

```fortran
  ! ----- L-7b-ii: BPSD broker round-trip verification -------------
  ! Non-mutating: pulls the 3 eq-pushed BPSD slots (device, equ1D,
  ! metric1D) into LOCAL discardable types and reports ok = 1 iff
  ! all three per-slot ierr == 0. plasmaf is intentionally NOT
  ! checked; it is tr's own BPSD output (tr_bpsd_put), absent on a
  ! fresh eq->tr pipeline. Each local %nrmax is set to 0 to trigger
  ! BPSD's self-allocation path (per ../bpsd/bpsd_equ1D.f90:143).
  SUBROUTINE tr_check_bpsd_pull(ok) BIND(C, NAME="tr_check_bpsd_pull")
    USE iso_c_binding, ONLY: c_int
    USE bpsd, ONLY: bpsd_get_data
    USE bpsd_types, ONLY: bpsd_device_type, bpsd_equ1D_type, &
                          bpsd_metric1D_type
    INTEGER(c_int), INTENT(OUT) :: ok
    TYPE(bpsd_device_type)    :: dev_local
    TYPE(bpsd_equ1D_type)     :: eq_local
    TYPE(bpsd_metric1D_type)  :: met_local
    INTEGER :: ierr_dev, ierr_eq, ierr_met

    ! Initialize size fields to 0 so BPSD allocates internally
    ! (mode=0 path in bpsd_get_*). bpsd_device_type has no nrmax.
    eq_local%nrmax  = 0
    met_local%nrmax = 0

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

- [ ] **Step 4: Verify Fortran compiles**

```bash
make -C tr clean 2>&1 | tail -3
make -C tr libtrapi.so 2>&1 | tail -10
```

Expected: build succeeds, no errors. macOS: if linker error, retry with `make -C tr libtrapi.so GFLIBS=""`.

- [ ] **Step 5: Verify symbol exported**

```bash
nm tr/libtrapi.so 2>/dev/null | grep "tr_check_bpsd_pull"
```

Expected: a line like `0000000000XXXXXX T _tr_check_bpsd_pull` (macOS) or `T tr_check_bpsd_pull` (Linux).

- [ ] **Step 6: Commit**

```bash
git add tr/tr_api.f90
git commit -m "tr: add tr_check_bpsd_pull non-mutating helper (L-7b-ii)"
```

### Task 1.2: Add C ABI prototype to `tr/tr_api.h`

**Files:**
- Modify: `tr/tr_api.h` (add prototype near other entry-point declarations, e.g. after `tr_api_validate`)

- [ ] **Step 1: Locate insertion point**

```bash
grep -nE "^(int|void)\s+tr_" tr/tr_api.h | head -10
```

Expected: list of existing prototypes (`tr_init`, `tr_run`, `tr_get_state`, `tr_validate`, etc.).

- [ ] **Step 2: Insert prototype**

Edit `tr/tr_api.h`. After the last `tr_*` prototype (likely near the bottom of the file before `#ifdef __cplusplus` close or `#endif`), insert:

```c
/* L-7b-ii: BPSD broker round-trip verification.
 * Returns *ok = 1 on successful pull of the 3 eq-pushed BPSD slots
 * (device, equ1D, metric1D); 0 otherwise. plasmaf is intentionally
 * excluded -- it is tr's own BPSD output, absent on a fresh eq->tr
 * pipeline. Non-mutating: pulls into local discardable types; does
 * not change tr_state_t contents. */
void tr_check_bpsd_pull(int *ok);
```

- [ ] **Step 3: Sanity check C compiles (no consumer changes yet)**

```bash
make -C tr clean 2>&1 | tail -3
make -C tr libtrapi.so 2>&1 | tail -5
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add tr/tr_api.h
git commit -m "tr: add tr_check_bpsd_pull prototype to C header (L-7b-ii)"
```

### Task 1.3: Add ctypes prototype to `python/trlib/_ffi.py`

**Files:**
- Modify: `python/trlib/_ffi.py` (`load_library` function, near other `lib.tr_*` prototype attachments)

- [ ] **Step 1: Locate prototype attachment block**

```bash
grep -nE "lib\.tr_(init|run|get_state|validate)" python/trlib/_ffi.py | head -5
```

Expected: lines like `lib.tr_init.argtypes = [...]`, `lib.tr_init.restype = ...`.

- [ ] **Step 2: Add prototype**

Edit `python/trlib/_ffi.py`. After the last `lib.tr_*` prototype attachment in `load_library`, insert:

```python
    # L-7b-ii: BPSD broker round-trip verification (non-mutating).
    lib.tr_check_bpsd_pull.argtypes = [ctypes.POINTER(ctypes.c_int)]
    lib.tr_check_bpsd_pull.restype = None
```

- [ ] **Step 3: Verify import does not raise**

```bash
PYTHONPATH=python python3 -c "from trlib import Trlib; tr = Trlib(); tr.close(); print('ffi load ok')"
```

Expected: `ffi load ok` (libtrapi.so loaded, prototype attached). If `AttributeError: undefined symbol: tr_check_bpsd_pull`, Phase 1 Task 1.1 step 5 should have caught the missing symbol — go back.

- [ ] **Step 4: Commit**

```bash
git add python/trlib/_ffi.py
git commit -m "trlib: ctypes prototype for tr_check_bpsd_pull (L-7b-ii)"
```

### Task 1.4: Add `Trlib.check_bpsd_pull` method

**Files:**
- Modify: `python/trlib/trlib.py` (add method to Trlib class, near existing `validate` method)

- [ ] **Step 1: Locate insertion point (next to `validate()` method)**

```bash
grep -nE "def (validate|run|get_state)" python/trlib/trlib.py | head -5
```

Expected: line numbers for `def validate`, `def run`, `def get_state` (per spec §3, `validate` exists at ~line 253).

- [ ] **Step 2: Add method**

Edit `python/trlib/trlib.py`. Insert this method right after the existing `validate` method (or wherever the section break makes sense):

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

        Returns True iff all 3 BPSD slots are pullable (per-slot ierr==0).
        """
        if self._closed:
            raise TrlibError("check_bpsd_pull on closed Trlib")
        ok = ctypes.c_int(0)
        self._lib.tr_check_bpsd_pull(ctypes.byref(ok))
        return ok.value == 1
```

- [ ] **Step 3: Smoke test the wrapper**

```bash
PYTHONPATH=python python3 -c "
from trlib import Trlib
with Trlib() as tr:
    result = tr.check_bpsd_pull()
    print(f'check_bpsd_pull on fresh init: {result}')
"
```

Expected: `check_bpsd_pull on fresh init: False` (BPSD slots empty after `tr_init`, no eq has pushed yet).

- [ ] **Step 4: Verify error on closed Trlib**

```bash
PYTHONPATH=python python3 -c "
from trlib import Trlib, TrlibError
tr = Trlib(); tr.close()
try:
    tr.check_bpsd_pull()
    print('ERROR: should have raised')
except TrlibError as e:
    print(f'got expected TrlibError: {e}')
"
```

Expected: `got expected TrlibError: check_bpsd_pull on closed Trlib`.

- [ ] **Step 5: Run existing trlib tests to confirm no regression**

```bash
PYTHONPATH=python python3 -m pytest --timeout=60 \
    python/trlib/tests/test_trlib.py python/trlib/tests/test_validate.py 2>&1 | tail -5
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add python/trlib/trlib.py
git commit -m "trlib: add Trlib.check_bpsd_pull() wrapper (L-7b-ii)"
```

### Task 1.5: Squash Phase 1 commits into Commit 1

**Files:** none (git rebase)

- [ ] **Step 1: List Phase 1 commits**

```bash
git log --oneline bdc09131..HEAD
```

Expected: 4 commits (Tasks 1.1, 1.2, 1.3, 1.4).

- [ ] **Step 2: Squash via soft reset**

```bash
git reset --soft bdc09131
git status
```

Expected: all Phase 1 changes staged: `tr/tr_api.f90`, `tr/tr_api.h`, `python/trlib/_ffi.py`, `python/trlib/trlib.py`.

- [ ] **Step 3: Create Commit 1**

```bash
git commit -m "$(cat <<'EOF'
tr+trlib: add tr_check_bpsd_pull BPSD broker verification helper (L-7b-ii)

New non-mutating Fortran helper tr_check_bpsd_pull pulls the 3
eq-pushed BPSD slots (device, equ1D, metric1D) into local
discardable types and reports ok = 1 iff all 3 per-slot ierr == 0.
plasmaf is intentionally NOT checked: it is tr's own BPSD output
(tr_bpsd_put), absent on a fresh eq->tr pipeline.

Implementation notes:
- Local types initialized with %nrmax = 0 to trigger BPSD's
  self-allocation path (per ../bpsd/bpsd_equ1D.f90:143-150,
  bpsd_get_* is INTENT(INOUT) and allocates internally when
  the caller passes nrmax=0).
- Per-slot ierr accumulated to AND-condition (avoids masking
  earlier failures by later successes).
- TRCOMM untouched -- safe to call before or after tr.run().
- TR_STATE_ABI_VERSION not bumped (no struct change).

Exposed via C ABI (tr/tr_api.h) and Python wrapper
(Trlib.check_bpsd_pull). Smoke-tested: fresh Trlib() init
returns False (BPSD slots empty); existing trlib tests unchanged.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Verify**

```bash
git log --oneline -3
```

Expected top: the new squashed Commit 1; HEAD~1 is `bdc09131 docs(plan): add L-7b-ii BPSD broker coupling implementation plan`.

---

## Phase 2 — `CouplingRule` extension + pipeline dispatch + new rule entry

**Goal of phase:** extend `CouplingRule` with `kind` and `verify` fields; add `__post_init__` validation; add `verify`-branch dispatch in `pipeline.py`; register the new `("eq","tr")` verify rule. End of phase: existing pipeline tests (`test_pipeline*.py`) all PASS unchanged; new validation raises ValueError on misconstructed rules.

### Task 2.1: Extend `CouplingRule` dataclass

**Files:**
- Modify: `python/totlib/pipeline.py` (`CouplingRule` dataclass area, around line 37-60)

- [ ] **Step 1: Read current dataclass**

```bash
sed -n '35,65p' python/totlib/pipeline.py
```

Expected: `@dataclass(frozen=True) class CouplingRule:` with `src_state_key`, `dst_param`, `transform`, `doc` fields, all required (no defaults).

- [ ] **Step 2: Update typing imports**

Edit `python/totlib/pipeline.py`. Locate the `from typing import ...` line near the top. Ensure these names are imported (add as needed):

```python
from typing import Any, Callable, Dict, List, Optional, Tuple
```

- [ ] **Step 3: Update `CouplingRule` to add `kind` + `verify` and default existing fields to None**

Replace the existing `CouplingRule` definition with:

```python
@dataclass(frozen=True)
class CouplingRule:
    """A single source-to-sink scalar coupling between adjacent steps.

    Frozen so the registry can be hashable in the future (rule dedup,
    set-based lookups) and to prevent accidental mutation by callers.

    Two kinds of rules are supported:

    * kind="transfer" (default): runs src_state_key on the previous
      step's state, applies transform, and pushes via set_param to
      the current module. All three of src_state_key/dst_param/
      transform are required.
    * kind="verify" (L-7b-ii): runs verify(curr_inst) and raises
      TotPipelineCouplingError if False. Only the verify callable
      is required; src_state_key/dst_param/transform are ignored.
    """
    # Transfer-rule fields (required when kind="transfer").
    src_state_key: Optional[Callable] = None
    dst_param: Optional[str] = None
    transform: Optional[Callable] = None
    doc: str = ""
    # L-7b-ii: kind dispatch + verify-only callable.
    kind: str = "transfer"
    verify: Optional[Callable[[Any], bool]] = None
    #   verify(dst_inst) -> bool; only consulted when kind == "verify"

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

- [ ] **Step 4: Verify existing rule construction still works**

```bash
PYTHONPATH=python python3 -c "
from totlib.pipeline import COUPLING_RULES
print('rules registered:', list(COUPLING_RULES.keys()))
for pair, rules in COUPLING_RULES.items():
    for r in rules:
        print(f'  {pair}: kind={r.kind!r} doc={r.doc[:40]!r}...')
"
```

Expected: shows `('fp', 'tr'): kind='transfer' doc='fp driven current ..."`. No `ValueError` raised.

- [ ] **Step 5: Verify validation actually catches misconstruction**

```bash
PYTHONPATH=python python3 -c "
from totlib.pipeline import CouplingRule
# Should raise: missing src_state_key
try:
    CouplingRule(dst_param='X', transform=lambda v: v)
    print('ERROR: should have raised')
except ValueError as e:
    print(f'got expected ValueError: {e}')

# Should raise: missing verify for kind=verify
try:
    CouplingRule(kind='verify')
    print('ERROR: should have raised')
except ValueError as e:
    print(f'got expected ValueError: {e}')

# Should raise: unknown kind
try:
    CouplingRule(kind='bogus')
    print('ERROR: should have raised')
except ValueError as e:
    print(f'got expected ValueError: {e}')
"
```

Expected: 3 `got expected ValueError: ...` lines.

- [ ] **Step 6: Commit**

```bash
git add python/totlib/pipeline.py
git commit -m "pipeline: extend CouplingRule with kind+verify fields (L-7b-ii)"
```

### Task 2.2: Add verify dispatch branch to `pipeline.py`

**Files:**
- Modify: `python/totlib/pipeline.py` (`run_pipeline` rule iteration loop, around line 425-438)

- [ ] **Step 1: Locate the rule iteration loop**

```bash
sed -n '420,445p' python/totlib/pipeline.py
```

Expected: shows the `for rule in COUPLING_RULES.get(...)` loop with `_extract_source` → `transform` → `set_param` sequence.

- [ ] **Step 2: Replace the loop body with kind-aware dispatch**

Edit `python/totlib/pipeline.py`. Locate the existing rule loop (inside the `if prev_name is not None:` block) and replace its body:

```python
                if prev_name is not None:
                    for rule in COUPLING_RULES.get((prev_name, name), []):
                        if rule.kind == "transfer":
                            # Existing logic: extract -> transform -> set_param -> record.
                            # __post_init__ guarantees src_state_key/dst_param/
                            # transform are non-None for kind="transfer", so the
                            # asserts below are type-narrowing for static checkers
                            # (mypy/pyright); they are unreachable at runtime.
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

(Replace verbatim; preserve indentation level matching the surrounding code.)

- [ ] **Step 3: Verify pipeline tests still pass (transfer path unchanged)**

```bash
PYTHONPATH=python python3 -m pytest --timeout=120 --timeout-method=signal \
    python/totlib/tests/test_pipeline.py 2>&1 | grep -E "passed|failed" | tail -3
```

Expected: previous pass count unchanged (the documented Python 3.10 ExceptionGroup test may still fail; otherwise all pass).

- [ ] **Step 4: Commit**

```bash
git add python/totlib/pipeline.py
git commit -m "pipeline: kind-aware dispatch (transfer + verify) (L-7b-ii)"
```

### Task 2.3: Register new `("eq","tr")` verify rule

**Files:**
- Modify: `python/totlib/pipeline.py` (`COUPLING_RULES` dict literal, around line 222-242)

- [ ] **Step 1: Locate `COUPLING_RULES` dict**

```bash
grep -n "^COUPLING_RULES" python/totlib/pipeline.py
sed -n '218,245p' python/totlib/pipeline.py
```

Expected: shows the dict with the existing `("fp", "tr")` entry.

- [ ] **Step 2: Add the new entry**

Edit `python/totlib/pipeline.py`. Within the `COUPLING_RULES` dict literal, after the existing `("fp", "tr")` entry, add:

```python
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
```

The dict literal should now have 2 entries (`("fp","tr")` and `("eq","tr")`).

- [ ] **Step 3: Verify rule construction succeeds**

```bash
PYTHONPATH=python python3 -c "
from totlib.pipeline import COUPLING_RULES
for pair, rules in COUPLING_RULES.items():
    for r in rules:
        print(f'{pair}: kind={r.kind!r}')
"
```

Expected:
```
('fp', 'tr'): kind='transfer'
('eq', 'tr'): kind='verify'
```

- [ ] **Step 4: Verify Layer 1 baseline still passes (verify rule must not affect tr-only pipelines)**

```bash
PYTHONPATH=python python3 -m pytest --timeout=120 --timeout-method=signal \
    python/totlib/tests/test_equivalence.py 2>&1 | grep -E "passed|failed" | tail -3
```

Expected: 2 passed (demo2014, ht6m). The new `("eq","tr")` rule does not fire because the equivalence test does not pipeline through `[eq, tr]`.

- [ ] **Step 5: Commit**

```bash
git add python/totlib/pipeline.py
git commit -m "pipeline: register ('eq','tr') verify rule for BPSD coupling (L-7b-ii)"
```

### Task 2.4: Squash Phase 2 commits into Commit 2

**Files:** none (git rebase)

- [ ] **Step 1: List Phase 2 commits**

```bash
git log --oneline HEAD~3..HEAD
```

Expected: 3 commits (Tasks 2.1, 2.2, 2.3).

- [ ] **Step 2: Squash via soft reset to Commit 1**

Find Commit 1 SHA:

```bash
git log --oneline -5
```

Identify the commit `tr+trlib: add tr_check_bpsd_pull ... (L-7b-ii)` — call its SHA `<C1>`.

```bash
git reset --soft <C1>
git status
```

Expected: all Phase 2 file changes staged (`python/totlib/pipeline.py`).

- [ ] **Step 3: Create Commit 2**

```bash
git commit -m "$(cat <<'EOF'
pipeline: extend CouplingRule for verify rules + register eq->tr (L-7b-ii)

CouplingRule dataclass gains two new fields:

  kind: str = "transfer"   # "transfer" | "verify"
  verify: Optional[Callable[[Any], bool]] = None

Existing transfer-rule fields (src_state_key, dst_param, transform)
are defaulted to None and validated by __post_init__:

  * kind="transfer" requires all three transfer fields
  * kind="verify"   requires verify callable
  * unknown kind raises ValueError

@dataclass(frozen=True) preserved; __post_init__ only raises and
never mutates self, so frozen remains compatible.

run_pipeline rule iteration gains a kind branch:

  * transfer: existing extract -> transform -> set_param -> record
  * verify:   ok = rule.verify(curr_inst); raise CouplingError if
              False or if verify itself raised.
              applied.append only on success (matches transfer-rule
              "succeeded snapshot" semantics of PipelineStep.coupling_applied)

Both error paths flow through the existing broad except at
pipeline.py and become TotPipelineRunError with __cause__ chain
(3-level: RunError -> CouplingError -> OriginalError if any).

New ("eq","tr") rule entry registered with verify=lambda tr_inst:
tr_inst.check_bpsd_pull(). Fires between eq.run() and tr.run() in
any pipeline that contains the pair; surfaces broker failures /
wrong order / missing eq output as TotPipelineCouplingError.

Existing ("fp","tr") transfer rule and Layer 1 baselines (demo2014,
ht6m at 1e-10) are unaffected.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Verify**

```bash
git log --oneline -4
```

Expected top 2: Commit 2 (pipeline) and Commit 1 (Fortran/wrapper); HEAD~2 is `bdc09131 docs(plan): ...`.

---

## Phase 3 — Tests + README updates (Commit 3)

**Goal of phase:** add 3-layer test coverage (mock A / unit B / integration C) and document the new coupling in totlib/trlib READMEs. End of phase: 11 new test cases pass; existing tests unaffected; READMEs explain the new verify rule.

### Task 3.1: Layer A — `test_pipeline_verify.py` (6 mock-based dispatch tests)

**Files:**
- Create: `python/totlib/tests/test_pipeline_verify.py`

- [ ] **Step 1: Read existing mock conventions**

```bash
sed -n '1,30p' python/totlib/tests/test_pipeline.py
grep -n "patch_wrappers\|monkeypatch.setattr.*COUPLING_RULES" python/totlib/tests/test_pipeline.py | head -5
```

Expected: shows `patch_wrappers` fixture at the top + `monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", ...)` example at ~line 305.

- [ ] **Step 2: Write the test file**

Create `python/totlib/tests/test_pipeline_verify.py`:

```python
"""L-7b-ii: verify-rule dispatch tests for TotPipeline.

Six mock-based cases covering:

  A-1: verify True -> rule recorded in coupling_applied
  A-2: verify False -> TotPipelineRunError raised, applied unchanged
  A-3: verify raises -> TotPipelineRunError, 3-level __cause__ chain
  A-4: mixed transfer+verify rules in one pair fire in declaration order
  A-5: __post_init__ validation rejects misconstructed rules
  A-6: unregistered pair -> silent skip, coupling_applied == []

No `.so` required; uses the existing patch_wrappers + monkeypatch
COUPLING_RULES pattern from test_pipeline.py.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from totlib.errors import TotPipelineCouplingError, TotPipelineRunError
from totlib.pipeline import CouplingRule, TotPipeline


def _make_state(scalars):
    """Build a minimal mock state object with .scalars dict."""
    s = MagicMock()
    s.scalars = dict(scalars)
    return s


@pytest.fixture
def patch_wrappers(monkeypatch):
    """Patch _MODULE_REGISTRY entries to return MagicMock classes
    so no real .so is loaded. Mirrors test_pipeline.py:20."""
    classes = {}
    for name in ("eq", "tr", "fp"):
        cls = MagicMock(name=f"{name}_class")
        cls.return_value = MagicMock(name=f"{name}_inst")
        cls.return_value.get_state.return_value = _make_state({})
        classes[name] = cls
        monkeypatch.setattr(
            f"totlib.pipeline._import_wrapper",
            lambda n, _classes=classes: _classes[n],
        )
    return {"classes": classes}


# --- A-1: verify True -> applied recorded ----------------------------

def test_verify_true_records_rule_in_applied(patch_wrappers, monkeypatch):
    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="verify",
                verify=lambda inst: True,
                doc="A-1 happy path",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    result = pipe.run_pipeline([("eq", {}), ("tr", {})])
    tr_step = result.last("tr")
    assert tr_step.coupling_applied == ["A-1 happy path"]


# --- A-2: verify False -> RunError(__cause__=CouplingError) ----------

def test_verify_false_raises_run_error_with_coupling_cause(
    patch_wrappers, monkeypatch
):
    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="verify",
                verify=lambda inst: False,
                doc="A-2 false-return",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("eq", {}), ("tr", {})])
    assert isinstance(exc_info.value.__cause__, TotPipelineCouplingError)
    assert "returned False" in str(exc_info.value.__cause__)
    # eq step completed; tr step did not.
    assert exc_info.value.failed_module == "tr"
    eq_step_applied = exc_info.value.partial_result.last("eq").coupling_applied
    # No verify-rule entry should appear in either step's applied list.
    assert "A-2 false-return" not in eq_step_applied


# --- A-3: verify raises -> RunError(__cause__=CouplingError(__cause__=Original))

def test_verify_raise_preserves_three_level_chain(
    patch_wrappers, monkeypatch
):
    class CustomError(Exception):
        pass

    def boom(inst):
        raise CustomError("verify boom")

    rules = {
        ("eq", "tr"): [
            CouplingRule(kind="verify", verify=boom, doc="A-3 raise"),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("eq", {}), ("tr", {})])

    coupling_err = exc_info.value.__cause__
    assert isinstance(coupling_err, TotPipelineCouplingError)
    original = coupling_err.__cause__
    assert isinstance(original, CustomError)
    assert "verify boom" in str(original)


# --- A-4: mixed transfer + verify fire in declaration order ----------

def test_mixed_transfer_then_verify_fires_in_order(
    patch_wrappers, monkeypatch
):
    fired = []

    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="transfer",
                src_state_key=lambda state, params: 1.0,
                dst_param="MOCK_PARAM",
                transform=lambda v: (fired.append("transfer"), v)[1],
                doc="A-4 transfer first",
            ),
            CouplingRule(
                kind="verify",
                verify=lambda inst: (fired.append("verify"), True)[1],
                doc="A-4 verify second",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    pipe.run_pipeline([("eq", {}), ("tr", {})])
    assert fired == ["transfer", "verify"]


# --- A-5: __post_init__ validation -----------------------------------

def test_post_init_rejects_transfer_missing_fields():
    with pytest.raises(ValueError, match="src_state_key"):
        CouplingRule(dst_param="X", transform=lambda v: v)


def test_post_init_rejects_verify_missing_callable():
    with pytest.raises(ValueError, match="verify"):
        CouplingRule(kind="verify")


def test_post_init_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown CouplingRule.kind"):
        CouplingRule(kind="bogus")


# --- A-6: unregistered pair -> silent skip ---------------------------

def test_unregistered_pair_silent_skip(patch_wrappers, monkeypatch):
    rules = {
        ("eq", "tr"): [
            CouplingRule(kind="verify", verify=lambda i: True, doc="dummy"),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    # Pipeline ("eq", "wr") -- no rule registered for that pair.
    result = pipe.run_pipeline([("eq", {}), ("wr", {})])
    wr_step = result.last("wr")
    assert wr_step.coupling_applied == []
```

- [ ] **Step 3: Run the new tests**

```bash
PYTHONPATH=python python3 -m pytest --timeout=60 -v \
    python/totlib/tests/test_pipeline_verify.py 2>&1 | tail -20
```

Expected: 8 passed (A-1, A-2, A-3, A-4, A-5 ×3, A-6). If any test fails, debug — common issues: `_import_wrapper` mock signature, MockClass construction, or `.last(name)` API mismatch (check `PipelineResult` for the right attribute name).

- [ ] **Step 4: Commit**

```bash
git add python/totlib/tests/test_pipeline_verify.py
git commit -m "test: Layer A mock-based verify dispatch (6 cases) (L-7b-ii)"
```

### Task 3.2: Layer B — `test_bpsd_check.py` (3 unit tests)

**Files:**
- Create: `python/trlib/tests/test_bpsd_check.py`

- [ ] **Step 1: Read existing trlib unit-test conventions**

```bash
sed -n '1,30p' python/trlib/tests/test_validate.py
```

Expected: shows the `unittest.skipUnless(DEFAULT_SO.exists(), ...)` pattern.

- [ ] **Step 2: Write the test file**

Create `python/trlib/tests/test_bpsd_check.py`:

```python
"""L-7b-ii: Trlib.check_bpsd_pull() unit tests.

Three cases:

  B-1: Fresh Trlib() init -> check_bpsd_pull() == False
       (BPSD slots empty, tr_init does not pre-populate)
  B-2: Closed Trlib -> TrlibError on check_bpsd_pull
  B-3: Smoke: function does not leak Fortran-side exceptions

Skipped when libtrapi.so is absent.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import Trlib, TrlibError  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
class TestCheckBpsdPull(unittest.TestCase):
    """Trlib.check_bpsd_pull() (L-7b-ii)."""

    def test_check_bpsd_pull_fresh_init_returns_false(self):
        """B-1: fresh Trlib() init has no BPSD data; pull returns False."""
        with Trlib() as tr:
            self.assertFalse(tr.check_bpsd_pull())

    def test_check_bpsd_pull_on_closed_raises(self):
        """B-2: closed Trlib must reject check_bpsd_pull (lifecycle guard)."""
        tr = Trlib()
        tr.close()
        with self.assertRaises(TrlibError):
            tr.check_bpsd_pull()

    def test_check_bpsd_pull_smoke_no_exception_leak(self):
        """B-3: ierr handling inside Fortran helper must not surface as
        Python exception; the wrapper returns bool, never raises (except
        on closed Trlib, covered by B-2)."""
        with Trlib() as tr:
            # call repeatedly; should never raise
            for _ in range(5):
                result = tr.check_bpsd_pull()
                self.assertIsInstance(result, bool)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
```

- [ ] **Step 3: Run the tests**

```bash
PYTHONPATH=python python3 -m pytest --timeout=60 -v \
    python/trlib/tests/test_bpsd_check.py 2>&1 | tail -10
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add python/trlib/tests/test_bpsd_check.py
git commit -m "test: Layer B Trlib.check_bpsd_pull unit tests (3 cases) (L-7b-ii)"
```

### Task 3.3: Layer C — `test_pipeline_eq_tr_verify.py` (2 integration tests)

**Files:**
- Create: `python/totlib/tests/test_pipeline_eq_tr_verify.py`

- [ ] **Step 1: Inspect demo2014 fixture for needed eq+tr params**

```bash
sed -n '1,80p' python/totlib/tests/fixtures/tot_demo2014_params.py
```

Expected: dict of `eq:*` and `tr:*` params, including `eq:KNAMEQ`, `tr:MODELG`. If `tr:MODELG` is not 3, the spec assumes Layer C MUST set it explicitly.

- [ ] **Step 2: Write the test file**

Create `python/totlib/tests/test_pipeline_eq_tr_verify.py`:

```python
"""L-7b-ii Layer C: integration test for eq -> tr verify rule.

Two cases:

  C-1: pipeline [eq, tr] with MODELG=3 -> success;
       coupling_applied contains the verify rule's doc.
  C-3: pipeline [eq, tr] with MODELG=0 -> TotPipelineRunError
       wrapping TotPipelineCouplingError (verify catches missing
       equ1D/metric1D since MODELG=0 means eq does not push them).

Requires libeqapi.so, libtrapi.so, and the demo2014 eqdata file.
Tests are skipped cleanly when any prerequisite is missing.

Use --forked (or per-test isolation) to avoid BPSD slot leakage
across tests in the same process; spec §8.4 risk #5.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from totlib.errors import TotPipelineCouplingError, TotPipelineRunError
from totlib.pipeline import TotPipeline

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
EQDATA = REPO / "test_run" / "test_output" / "tot_demo2014_short" / "eqdata.demo2014"
LIBEQ  = REPO / "eq" / "libeqapi.so"
LIBTR  = REPO / "tr" / "libtrapi.so"

pytestmark = pytest.mark.skipif(
    not (EQDATA.exists() and LIBEQ.exists() and LIBTR.exists()),
    reason="requires eqdata.demo2014 + libeqapi.so + libtrapi.so",
)


def _eq_params_modelg(modelg: int) -> dict:
    """Minimal eq param set for a 1-step run with the given MODELG."""
    return {
        "eq:RR":   3.0,
        "eq:RA":   1.0,
        "eq:BB":   3.0,
        "eq:RIP":  1.0,
        "tr:MODELG": modelg,
        "tr:RR":   3.0,
        "tr:RA":   1.0,
        "tr:BB":   3.0,
        "tr:NSMAX": 2,
        "tr:DT":   0.1,
        "tr:NTSTEP": 1,
    }


def _eq_str_params() -> dict:
    """String-valued eq params (e.g. KNAMEQ)."""
    return {"eq:KNAMEQ": str(EQDATA)}


def _set_all(pipe: TotPipeline, params: dict, str_params: dict) -> None:
    for k, v in params.items():
        pipe.set_param(k, v)
    for k, v in str_params.items():
        pipe.set_param_str(k, v)


def test_eq_tr_modelg3_verify_passes():
    """C-1: full eq -> tr pipeline with MODELG=3 verifies successfully."""
    pipe = TotPipeline()
    _set_all(pipe, _eq_params_modelg(3), _eq_str_params())
    result = pipe.run_pipeline([
        ("eq", {"mode": 1}),
        ("tr", {"ntmax": 1}),
    ])
    tr_applied = result.last("tr").coupling_applied
    # The verify rule's doc starts with "eq -> tr equilibrium coupling ..."
    assert any("equilibrium coupling" in doc for doc in tr_applied), \
        f"verify rule did not record success in tr step: {tr_applied!r}"


def test_eq_tr_modelg0_verify_fails():
    """C-3: MODELG=0 means eq does not push equ1D/metric1D; verify
    must catch the missing slots and raise CouplingError."""
    pipe = TotPipeline()
    _set_all(pipe, _eq_params_modelg(0), _eq_str_params())
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([
            ("eq", {"mode": 1}),
            ("tr", {"ntmax": 1}),
        ])
    assert isinstance(exc_info.value.__cause__, TotPipelineCouplingError)
    msg = str(exc_info.value.__cause__)
    assert "BPSD broker" in msg
```

- [ ] **Step 3: Run Layer C with `--forked` for BPSD isolation (per spec §8.4 risk #5) and measure runtime**

`--forked` is required (not advisory) — BPSD broker state persists
across in-process tests, and Layer C tests depend on a clean broker.
Without isolation, C-3 (MODELG=0 expected failure) may spuriously
pass if a prior C-1 already populated the BPSD slots.

```bash
time PYTHONPATH=python python3 -m pytest --forked --timeout=120 --timeout-method=signal -v \
    python/totlib/tests/test_pipeline_eq_tr_verify.py 2>&1 | tail -20
```

Expected: 2 passed. Note the `real` time printed.

- [ ] **Step 4: Decide on `@pytest.mark.slow` gating**

If Layer C runtime > 5 s (per spec §8.4 risk #3 fallback), add `@pytest.mark.slow` decorator at the module top:

```python
pytestmark = [
    pytest.mark.skipif(...),  # existing
    pytest.mark.slow,
]
```

Otherwise leave as-is. Document the measured time in the commit message.

- [ ] **Step 5: Commit**

```bash
git add python/totlib/tests/test_pipeline_eq_tr_verify.py
git commit -m "test: Layer C eq->tr integration verify (2 cases) (L-7b-ii)"
```

### Task 3.4: Update `python/totlib/README.md`

**Files:**
- Modify: `python/totlib/README.md` (Coupling rules section)

- [ ] **Step 1: Locate the existing coupling rules section**

```bash
grep -n "Coupling rules\|fp → tr\|EXTERNAL_DRIVEN_I" python/totlib/README.md
```

Expected: section header around line 285-295 (post L-7b-i). Read 10 lines around the match.

- [ ] **Step 2: Add eq → tr documentation**

Edit `python/totlib/README.md`. After the existing `fp → tr` description, add:

```markdown
- `eq → tr`: equilibrium coupling via BPSD broker (verifies
  `device` + `equ1D` + `metric1D` slots are pullable). This is a
  **verify-kind** coupling rule (`kind="verify"` in `CouplingRule`):
  no scalar value is pushed, but the orchestrator checks pre-tr-run
  that BPSD has the slots tr will pull. Failure raises
  `TotPipelineCouplingError` with a 3-level cause chain visible
  via `TotPipelineRunError.__cause__`.

  When MODELG=0 (no geometry-aware transport), eq does not push
  `equ1D`/`metric1D`; the verify rule will surface this misconfiguration
  as a `CouplingError`. Use MODELG ∈ {3, 5, 7, 8, 9} for the eq → tr
  pipeline.
```

- [ ] **Step 3: Commit**

```bash
git add python/totlib/README.md
git commit -m "docs(totlib): document eq->tr verify rule (L-7b-ii)"
```

### Task 3.5: Update `python/trlib/README.md`

**Files:**
- Modify: `python/trlib/README.md` (Add new section near "External driven current" L-7b-i section)

- [ ] **Step 1: Find insertion point**

```bash
grep -n "^## " python/trlib/README.md | head -10
```

Expected: section list. Insert new section after "External driven current" (L-7b-i section).

- [ ] **Step 2: Add new section**

Edit `python/trlib/README.md`. Add this section in the appropriate place:

```markdown
## BPSD broker pull verification

`Trlib.check_bpsd_pull()` (L-7b-ii) returns `True` iff the BPSD
broker has the 3 eq-pushed slots tr expects: `device`, `equ1D`,
`metric1D`. Used by `TotPipeline` to verify the eq → tr coupling
before tr runs; can also be called directly:

```python
from trlib import Trlib

with Trlib() as tr:
    if not tr.check_bpsd_pull():
        # eq has not pushed; running tr would proceed with default
        # (or stale) equilibrium data.
        raise RuntimeError("BPSD broker missing equilibrium data")
    tr.run(ntmax=10)
```

Notes:

- **Non-mutating**: pulls into local discardable types; TRCOMM is
  unchanged. Safe to call before or after `tr.run()`.
- **plasmaf is excluded**: it is tr's own BPSD output (`tr_bpsd_put`),
  absent on a fresh eq → tr pipeline. Including it would cause
  spurious `False` returns on first-time pipelines.
- **Coarse granularity**: bool-only. Per-slot reporting is a future
  enhancement (see spec §8.3).
```

- [ ] **Step 3: Commit**

```bash
git add python/trlib/README.md
git commit -m "docs(trlib): document Trlib.check_bpsd_pull (L-7b-ii)"
```

### Task 3.6: Squash Phase 3 into Commit 3

**Files:** none (git rebase)

- [ ] **Step 1: List Phase 3 commits**

```bash
git log --oneline HEAD~5..HEAD
```

Expected: 5 commits (Tasks 3.1, 3.2, 3.3, 3.4, 3.5).

- [ ] **Step 2: Squash via soft reset to Commit 2**

Find Commit 2 SHA:

```bash
git log --oneline -7
```

Identify `pipeline: extend CouplingRule for verify rules + register eq->tr (L-7b-ii)` — call its SHA `<C2>`.

```bash
git reset --soft <C2>
git status
```

Expected: all Phase 3 file changes staged.

- [ ] **Step 3: Create Commit 3**

```bash
git commit -m "$(cat <<'EOF'
test+docs: BPSD coupling verification 3-layer test + READMEs (L-7b-ii)

Adds 11 new test cases across 3 layers:

  Layer A (test_pipeline_verify.py, no .so): 6 mock-based dispatch
    tests covering verify-True success, verify-False raise+cause-chain,
    verify-raise 3-level chain, mixed transfer+verify ordering,
    __post_init__ validation, unregistered-pair silent skip.

  Layer B (test_bpsd_check.py, libtrapi.so): 3 unit tests for
    Trlib.check_bpsd_pull() -- fresh init returns False, closed
    Trlib raises TrlibError, no exception leak from Fortran.

  Layer C (test_pipeline_eq_tr_verify.py, libeqapi+libtrapi+eqdata):
    2 integration tests -- MODELG=3 success path with coupling_applied
    proof; MODELG=0 surfaces missing equ1D/metric1D as CouplingError.
    Skipif on lib/eqdata absence; --forked recommended for BPSD
    isolation per spec §8.4 risk #5.

README updates:

  python/totlib/README.md: documents the new eq -> tr verify rule
    in the Coupling rules section, including MODELG requirement.

  python/trlib/README.md: new "BPSD broker pull verification" section
    documenting Trlib.check_bpsd_pull() with usage example and notes
    on non-mutating semantics + plasmaf exclusion + coarse granularity.

Total: 11 logical cases (Layer A 6 + Layer B 3 + Layer C 2). The
A-5 validation case is implemented as 3 separate test functions
(transfer-missing-fields / verify-missing-callable / unknown-kind),
so pytest reports 13 individual tests total. Existing Layer 1
baselines (demo2014, ht6m at 1e-10) unchanged.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Verify final commit list**

```bash
git log --oneline -4
```

Expected: 3 PR commits (Phase 3, 2, 1) + plan commit base (`bdc09131`).

---

## Phase 4 — Pre-push gate + PR open

**Goal of phase:** CLAUDE.md pre-push gate (local pytest, 2 reviewers in parallel, marker, push, PR).

### Task 4.1: Final local pytest sweep

**Files:** none (test only)

- [ ] **Step 1: Run canonical CI test set (handoff scope, CLAUDE.md flags)**

CLAUDE.md non-negotiable: pre-push pytest MUST use the SAME flags as
the CI workflow: `--forked --timeout=120 --timeout-method=signal`.
The `--forked` plugin is `pytest-forked`; install via `pip install
pytest-forked` if missing. If the plugin is genuinely unavailable in
the current environment (e.g. fresh contributor clone), document the
substitution explicitly in the commit message and run without
`--forked` as a documented exception.

```bash
PYTHONPATH=python python3 -m pytest --forked --timeout=120 --timeout-method=signal \
    python/totlib/tests/ python/mcp-servers/tot_mcp/tests/ 2>&1 \
    | grep -E "passed|failed" | tail -3
```

Expected: 217 passed (206 baseline + Layer A 8 + integration 2 + the
pre-existing Python 3.10 `ExceptionGroup` unrelated test may still
fail; documented as known-not-blocking).

- [ ] **Step 2: Run new Layer B unit tests**

```bash
PYTHONPATH=python python3 -m pytest --forked --timeout=120 --timeout-method=signal \
    python/trlib/tests/test_bpsd_check.py python/trlib/tests/test_validate.py 2>&1 \
    | grep -E "passed|failed" | tail
```

Expected: all PASS (Layer B 3 + existing validate tests).

- [ ] **Step 3: Re-verify Layer 1 baseline (key backward-compat gate)**

```bash
PYTHONPATH=python python3 -m pytest --forked --timeout=120 --timeout-method=signal \
    python/totlib/tests/test_equivalence.py 2>&1 | grep -E "passed|failed" | tail -3
```

Expected: 2 passed (demo2014 + ht6m at 1e-10). The new verify rule does NOT fire because the equivalence test does not pipeline through `[eq, tr]`.

- [ ] **Step 4: If anything unexpected fails, debug before pushing**

DO NOT proceed if anything other than the documented Python 3.10 ExceptionGroup test fails. Re-read the failing test, reproduce in isolation, fix, re-commit.

### Task 4.2: Run 2 reviewer agents in parallel

**Files:** none (Agent calls)

- [ ] **Step 1: Launch in-house code-reviewer + Codex independent reviewer in PARALLEL**

CLAUDE.md specifies `feature-dev:code-reviewer` as the in-house
reviewer agent. If that subagent_type is unavailable in the current
environment (verify via TaskList of available agents), substitute
`superpowers:code-reviewer`. Both have the same review responsibility;
the priority is "two independent reviewers in parallel".

In a single message, dispatch both:

```
Agent(subagent_type="feature-dev:code-reviewer", prompt="""
Review the diff in /Users/k-yoshimi/Dropbox/cursor/task on branch
claude/2026-05-03-l7b-ii-bpsd-broker-coupling. Run:
    git diff bdc09131..HEAD
to see the 3 commits:

1. tr+trlib: tr_check_bpsd_pull helper + C ABI + Python wrapper
2. pipeline: CouplingRule extension + dispatch + ('eq','tr') rule
3. test+docs: 3-layer test (11 cases) + README updates

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md

Local verification: 217 passed in canonical sweep, Layer 1
equivalence (demo2014+ht6m) PASS at 1e-10, 11 new test cases PASS.

Focus on: (1) Fortran helper non-mutating contract (TRCOMM
unchanged), (2) BPSD type local %nrmax=0 init correctness,
(3) CouplingRule frozen=True + __post_init__ semantics,
(4) verify dispatch error chain (3-level), (5) backward
compatibility of the existing ('fp','tr') transfer rule.

Report HIGH/MED in <400 words.
""")

Agent(subagent_type="codex:codex-rescue", prompt="""
Independent second-opinion review of the same diff. Background:
this PR adds orchestrator-level verification of the eq -> tr BPSD
coupling. New non-mutating Fortran helper checks 3 BPSD slots
(device, equ1D, metric1D); plasmaf is intentionally excluded
(tr's own output). CouplingRule gains kind/verify fields with
__post_init__ validation. 11-case test coverage across 3 layers.

Spec went through 7 rounds of brainstorming review (HIGH/MED all
addressed). Verify the implementation matches the spec, especially:
- §2 Fortran helper signature + 3-slot check (no plasmaf)
- §4 frozen=True dataclass with required-field validation
- §5 dispatch with type-narrowing asserts and 3-level cause chain
- §7 test layers A/B/C as specified

Report HIGH/MED in <400 words. Anchor on spec divergence and
cross-cutting code-quality issues that the in-house reviewer
might miss.
""")
```

Both Agent calls fire in the same message for parallel execution.

- [ ] **Step 2: Surface findings to user; address HIGH/MED on a fix commit**

For each HIGH/MED finding:
- Make a fix commit on top of Commit 3 (do NOT amend — CLAUDE.md says always create new commits)
- Re-run pytest sweep + Layer 1 baseline
- If diff is significant, re-run reviewers on the cumulative diff

### Task 4.3: Write REVIEW_OK marker + push

**Files:** none

- [ ] **Step 1: Mark current HEAD as reviewed**

```bash
touch "$(git rev-parse --git-common-dir)/REVIEW_OK_$(git rev-parse HEAD)"
ls "$(git rev-parse --git-common-dir)/REVIEW_OK_$(git rev-parse HEAD)"
```

Expected: marker file exists for HEAD SHA.

- [ ] **Step 2: Push feature branch to origin**

```bash
git push -u origin claude/2026-05-03-l7b-ii-bpsd-broker-coupling 2>&1 | tail -5
```

Expected: `pre-push: review marker present — OK`. Push succeeds.

If pre-push hook complains about marker missing, re-do Step 1 (the SHA may have changed via a fix commit).

### Task 4.4: Open PR

**Files:** none (gh)

- [ ] **Step 1: Create PR via gh**

```bash
env -u GITHUB_TOKEN gh pr create \
    --base chore/pre-push-hook-worktree-compat \
    --title "tot+tr: BPSD broker coupling verification (eq->tr) (L-7b-ii)" \
    --body "$(cat <<'EOF'
## Summary

Adds orchestrator-level verification of the eq -> tr BPSD coupling.
A new `("eq","tr")` verify-kind `CouplingRule` fires between eq.run()
and tr.run(); it calls `Trlib.check_bpsd_pull()` (a new non-mutating
Fortran helper) which pulls the 3 eq-pushed BPSD slots (device, equ1D,
metric1D) into local discardable types and reports True iff all are
present. False -> `TotPipelineCouplingError` raised, wrapped by
`TotPipelineRunError` with full 3-level `__cause__` chain.

`plasmaf` is intentionally excluded from the check: it is tr's own
BPSD output (`tr_bpsd_put`), absent on a fresh eq -> tr pipeline.

3 commits:
1. **Fortran + wrapper** (tr_check_bpsd_pull + C ABI + Trlib method)
2. **Pipeline extension** (`CouplingRule.kind/verify` + dispatch + new rule)
3. **Tests + docs** (11 cases / 3 layers + READMEs)

Spec: `docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md`

## Test plan

- [x] Layer 1 equivalence (demo2014 + ht6m) PASS at 1e-10 -- backward compat gate
- [x] All existing pipeline tests PASS unchanged (transfer-rule path unaffected)
- [x] 11 new test cases PASS:
      - Layer A (6 mock-based dispatch tests)
      - Layer B (3 unit tests for `Trlib.check_bpsd_pull()`)
      - Layer C (2 integration tests with real eq+tr; MODELG=3 success / MODELG=0 surfaces failure)
- [x] In-house code-reviewer: HIGH/MED resolved
- [x] Codex independent reviewer: HIGH/MED resolved
- [x] CLAUDE.md pre-push gate complete (REVIEW_OK marker for final SHA)

## L-7b-ii scope confirmation

In scope (this PR):
- `tr_check_bpsd_pull` non-mutating Fortran helper + C ABI export
- `Trlib.check_bpsd_pull()` Python wrapper
- `CouplingRule` extension (`kind` + `verify` fields with `__post_init__`)
- `pipeline.py` kind-aware dispatch + new `("eq","tr")` rule
- 3-layer test + README updates

Out of scope (later L-7b phases per spec §8):
- L-7b-iii: declarative `tot.couple()` runtime API
- L-7b-iv: per-module state aggregation + AJOHT/AJBST/AJNBT exposure
- wr/fp/ti BPSD speaker wiring (pending evaluation per spec §8.2)
- VerificationRule dataclass split (future refactor per spec §8.3)
- BPSD time-step freshness verification (future per spec §8.3)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -5
```

Expected: PR URL printed.

- [ ] **Step 2: Note the PR URL**

Print the URL so the user can monitor CI status.

### Task 4.5: Wait for CI + Bugbot, merge

**Files:** none (monitoring)

- [ ] **Step 1: Check CI status**

```bash
env -u GITHUB_TOKEN gh pr view --json statusCheckRollup 2>&1 | head
```

If green: proceed to Step 2.
If red: read the failing job, reproduce locally, fix, push fix commit, re-mark + re-push.

- [ ] **Step 2: Check Bugbot status**

CI/Makefile-only PRs typically do not trigger Bugbot per handoff §D, but content PRs (Fortran + Python like this one) sometimes do. If Bugbot triggers and leaves comments, address per CLAUDE.md `feedback_bugbot_wait.md` (re-review with both agents on the fix diff).

- [ ] **Step 3: Squash-merge when all checks COMPLETED**

```bash
env -u GITHUB_TOKEN gh pr merge --squash --delete-branch 2>&1 | tail -3
```

NEVER use `--admin` or `--no-verify`. Wait for CI even if it takes hours.

- [ ] **Step 4: Update local chore branch**

```bash
git checkout chore/pre-push-hook-worktree-compat
git pull --ff-only origin chore/pre-push-hook-worktree-compat
git log --oneline -3
```

Expected: chore tip is the new merge commit; the L-7b-ii series is now on chore.

---

## Spec coverage check

| Spec section | Implementation task |
|---|---|
| §1 Overview + data flow | Phase 1 + Phase 2 (cumulative) |
| §1 MVP scope clarification | Phase 1, 2, 3 in/out of scope |
| §2 Fortran helper `tr_check_bpsd_pull` | Task 1.1 |
| §2 C prototype | Task 1.2 |
| §2 ABI version unchanged | Task 1.1, 1.2 (no `tr_state_t` change) |
| §3 ctypes prototype | Task 1.3 |
| §3 `Trlib.check_bpsd_pull` method | Task 1.4 |
| §4 `CouplingRule` dataclass extension | Task 2.1 |
| §4 `__post_init__` validation | Task 2.1 |
| §4 `frozen=True` preservation | Task 2.1 |
| §4 New `("eq","tr")` rule entry | Task 2.3 |
| §5 `pipeline.py` kind-aware dispatch | Task 2.2 |
| §5 Type-narrowing asserts | Task 2.2 |
| §6 No new exception class | Task 2.2 (uses existing `TotPipelineCouplingError`) |
| §6 3-level exception chain | Task 2.2 + Layer A-3 verifies |
| §6 Error message format | Task 2.2 |
| §7 Layer A 6 cases | Task 3.1 |
| §7 Layer B 3 cases | Task 3.2 |
| §7 Layer C 2 cases (C-1, C-3) | Task 3.3 |
| §7 MODELG fixture extension | Task 3.3 (introduces local `_eq_params_modelg(modelg)` helper instead of mutating `tot_demo2014_params.py`; rationale: avoid side effects on Layer 1 baselines that share the existing fixture. Spec §7 preferred extending the existing file; this plan deviates for safety. The `eqdata.demo2014` path IS reused.) |
| §7 CI runtime measurement | Task 3.3 Step 3-4 |
| §8.1 Out-of-scope deferrals | PR description Out-of-scope section (Task 4.4) |
| §8.4 BPSD pre-alloc fallback | Task 1.1 (`%nrmax = 0` initialization) |
| §8.4 Eq wrapper sufficiency | Verified at plan-time; no fallback needed |
| §8.4 Layer C runtime fallback | Task 3.3 Step 4 (`@pytest.mark.slow` if > 5 s) |
| §8.4 Stale BPSD slot risk | Task 3.3 (`--forked` recommendation in test docstring) |
| §8.5 Single-step assumption | Task 3.3 (test fixtures use single eq + single tr step) |
| Acceptance criteria 1-9 | covered across all tasks |

All spec sections are implemented in this plan. ✓

---

## Notes for the executor

- **Frequent commits**: each task commits incrementally. Phase 1.5 / 2.4 / 3.6 then squash into the 3 PR-target commits.
- **TDD discipline**: for the new test files (Tasks 3.1, 3.2, 3.3), the Fortran/Python plumbing already exists by the time the tests are written (Phase 1 + 2 are done first). So the tests pass on first run; they are regression guards, not red-green-refactor drivers.
  - If you want strict TDD: write the new tests in Phase 0.5 (between Phase 0 and 1), confirm they fail, then proceed to Phase 1. Tests start passing as you complete each Phase 1+2 task.
- **macOS gotcha**: if `make -C tr` fails on macOS, try `make -C tr GFLIBS=""` (per L-7b-i precedent).
- **Build artifacts NOT in git**: `tr/libtrapi.so` is gitignored. Don't commit it.
- **Layer 1 is the regression gate**: if `test_equivalence.py` fails after Phase 2, the new verify rule has somehow leaked into the equivalence pipeline — check that the new rule has `kind="verify"` and is associated with `("eq","tr")` (not some other pair).
- **Layer C `--forked` consideration**: BPSD persists state across in-process tests. If Layer C tests interfere with each other, add `--forked` to the test-run command or use a process-isolation fixture. Document the choice in the commit message.
- **pre-push gate is non-negotiable**: even for "trivial" fix commits, re-run pytest + 2 reviewers + write a fresh REVIEW_OK marker for the new SHA. The hook (`scripts/pre-push.sh`) enforces this; never bypass with `--no-verify`.
