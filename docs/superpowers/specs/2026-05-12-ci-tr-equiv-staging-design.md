# trlib `test_equivalence.py` — eq-mirror fallback for committed fixtures

**Date**: 2026-05-12
**Branch**: `feat/ci-tr-equiv-staging` (from `develop` at `14659b3a`)
**Issue**: #192 (`CI: stage eqdata.ITER01/TST-2 so test_equivalence.py actually runs (currently silent SKIP)`)
**Author**: Kazuyoshi Yoshimi
**Status**: Approved scope (Approach A2); pending implementation plan

## 1. Goal

Flip `python/trlib/tests/test_equivalence.py::TestEquivalence::test_iter01` and `test_tst2` from **silent SKIP** to **active PASS** on CI (and on any fresh checkout, not just CI). Enforce the invariant from `feedback_equivalence_must_pass.md` — Layer-1 1e-10 equivalence tests must actually run.

## 2. Motivation

PR #187 (`e049a1e4`, L-7b-i `EXTERNAL_DRIVEN_I`) added `AJRFT` to TR's C ABI + Python wrapper but failed to update the paired Phase-0 dump path. Locally the chore branch's `test_iter01` failed at 1e-10 with `compare_metrics FAIL: scalars.AJRFT: missing` — but **CI silently passed for ~10 days** because the test was SKIPping (eqdata absent in CI). The gap was caught only by accident during PNBTOT work (PR #176 thread).

The root cause is an **asymmetry between eq and tr** in their `test_equivalence.py` fixture-lookup logic. `python/eqlib/tests/test_equivalence.py:197-205` has a two-tier fallback:

```python
if (candidate / knameq).exists():
    cwd = candidate            # Prefer dev-generated eqdata (Phase-0 runner output)
elif (FIXTURES_DIR / knameq).exists():
    cwd = FIXTURES_DIR         # CI / fresh checkout: fall back to committed fixture
else:
    self.skipTest(...)
```

`python/trlib/tests/test_equivalence.py` is missing the `FIXTURES_DIR` branch — it goes straight to `skipTest` if `test_run/test_output/<case>/<KNAMEQ>` is absent. This spec closes that asymmetry by mirroring eq's fallback in tr.

## 3. Non-goals

- Adding a CI workflow step to copy fixtures (Option A1 from brainstorming) — superseded by the in-test fallback, which fixes both CI and fresh-clone developer experiences in one change.
- Building `eq.x` or `tr2` standalone binaries in CI for fresh eqdata regen — long-term improvement to detect eq physics drift, deferred.
- Covering `fp/wr/wrx/ti` equivalence tests — they do not use `KNAMEQ` so this fallback class is not applicable; whether they SKIP for other reasons is a separate audit, follow-up.
- Touching `python/eqlib/tests/test_equivalence.py` — already correct; this PR brings tr in line, not the other way around.

## 4. Scope (3 files, 1 commit)

### 4.1 Available fixtures (already mostly in place)

| Path | Size | Status |
|------|------|--------|
| `python/eqlib/tests/fixtures/eqdata.ITER01` | 45956 B | git-tracked (used by eq tests) |
| `python/eqlib/tests/fixtures/eqdata.TST-2` | 45956 B | git-tracked |
| `python/trlib/tests/fixtures/eqdata.TST-2` | 45956 B | **git-tracked** (already mirrors eqlib for tr_tst2) |
| `python/trlib/tests/fixtures/eqdata.ITER01` | — | **MISSING** — needs to be added in this PR |

`.gitignore` rules (excerpt):

```
eqdata*
!python/trlib/tests/fixtures/eqdata.TST-2
!python/eqlib/tests/fixtures/eqdata.TST-2
!python/eqlib/tests/fixtures/eqdata.ITER01
```

A new negation `!python/trlib/tests/fixtures/eqdata.ITER01` must be added.

### 4.2 What needs to change

Three changes in one commit:

#### 4.2.1 `python/trlib/tests/test_equivalence.py` (component 1)

Two edits:

**Add `FIXTURES_DIR` constant** alongside the other path constants (currently lines 41-47, ending with `DEFAULT_SO = ...`):

```python
# Before:
HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"
DEFAULT_SO = REPO / "tr" / "libtrapi.so"

# After: add one line:
FIXTURES_DIR = HERE.parent / "fixtures"
```

**Replace the `_check_case` SKIP logic** (currently around line 171-184) with the two-tier fallback mirroring eq:

```python
# Before:
if knameq:
    candidate = TEST_OUTPUT_DIR / fixture_module.BASELINE_NAME
    if not (candidate / knameq).exists():
        self.skipTest(
            f"eqdata '{knameq}' missing under {candidate}; "
            "run `./test_run/run_tests.sh "
            f"{fixture_module.BASELINE_NAME}` first."
        )
    cwd = candidate

# After:
if knameq:
    candidate = TEST_OUTPUT_DIR / fixture_module.BASELINE_NAME
    if (candidate / knameq).exists():
        # Prefer dev-generated eqdata (Phase-0 runner output) so that
        # local-regen-then-test workflows see their freshly-generated
        # data instead of the committed reference.
        cwd = candidate
    elif (FIXTURES_DIR / knameq).exists():
        # CI / fresh checkout: fall back to the committed fixture so
        # the equivalence test runs instead of silently skipping.
        # See CLAUDE.md §Test-suite discipline + feedback_equivalence_must_pass.md.
        cwd = FIXTURES_DIR
    else:
        self.skipTest(
            f"eqdata '{knameq}' missing under {candidate} or "
            f"{FIXTURES_DIR}; run "
            f"`./test_run/run_tests.sh {fixture_module.BASELINE_NAME}` first."
        )
```

The wording + structure is a verbatim mirror of `python/eqlib/tests/test_equivalence.py:197-205`.

#### 4.2.2 `python/trlib/tests/fixtures/eqdata.ITER01` (component 2)

Add a new binary fixture file. The content is a verbatim copy of `python/eqlib/tests/fixtures/eqdata.ITER01` (45956 B).

Implementation: `cp python/eqlib/tests/fixtures/eqdata.ITER01 python/trlib/tests/fixtures/eqdata.ITER01`.

**Why copy rather than symlink/share**:
- The eq fixtures dir and the trlib fixtures dir are owned by different test packages. A symlink would couple them in a way the existing pattern (with `eqdata.TST-2` already duplicated in both dirs) does not.
- Symlinks on Windows are inconsistent; the project is cross-platform-friendly.
- 45 KB duplicate is negligible.

#### 4.2.3 `.gitignore` (component 3)

Add one negation:

```diff
 eqdata*
 !python/trlib/tests/fixtures/eqdata.TST-2
+!python/trlib/tests/fixtures/eqdata.ITER01
 !python/eqlib/tests/fixtures/eqdata.TST-2
 !python/eqlib/tests/fixtures/eqdata.ITER01
```

Mirrors the existing TST-2 negation immediately above it.

## 5. Commit shape (1 commit)

| # | Subject | Files | LoC |
|---|---------|-------|-----|
| C1 | `test(trlib): fallback to committed eqdata fixture so test_equivalence runs (#192)` | 3 | ~25 (Python) + 1 (.gitignore) + 1 binary (45 KB) |

## 6. Test plan

### 6.1 Local pre-flight (mac)

If `libtrapi.so` is buildable locally (chore branch had this), the test can be exercised end-to-end:

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-tr-equiv-staging
# Confirm both eqdata fixtures are present in trlib/tests/fixtures
ls -l python/trlib/tests/fixtures/eqdata.{ITER01,TST-2}
# With test_run/test_output cleared (or never run), verify fallback engages
rm -rf test_run/test_output/tr_iter01 test_run/test_output/tr_tst2
pytest python/trlib/tests/test_equivalence.py -v 2>&1 | tail -10
```

Expected (when `libtrapi.so` is built):
```
python/trlib/tests/test_equivalence.py::TestEquivalence::test_iter01 PASSED
python/trlib/tests/test_equivalence.py::TestEquivalence::test_tst2 PASSED
```

If `libtrapi.so` is not built locally on mac (the outer `@unittest.skipUnless(DEFAULT_SO.exists())` decorator), both tests will SKIP for a different reason — that's expected and not in scope.

### 6.2 CI verification (post-push)

After the PR opens, inspect the `pytest (Python 3.11)` and `pytest (Python 3.13)` job logs:

1. `python/trlib/tests/test_equivalence.py::TestEquivalence::test_iter01` shows `PASSED`, not `SKIPPED`.
2. Same for `test_tst2`.
3. The `Show collected vs skipped summary` step (already present in the workflow) shows these tests are not in the SKIP list.

### 6.3 Behavior verification (Python-only, no libtrapi.so needed)

The fallback logic itself can be unit-tested on any platform without `libtrapi.so` by directly invoking the `_check_case` path. Add a small follow-up test if it strengthens coverage; **not** in scope for this PR (the integration test that the fallback enables is itself the verification).

### 6.4 Drift sanity (if CI reports 1e-10 failure)

CI uses `gfortran 13.2` (Ubuntu 24.04 default per `.github/workflows/python-tests.yml:50`). The baseline `test_run/baselines/tr_iter01/metrics.json` was generated on clavius (gfortran 13.3.0 per `reference_clavius_baseline_regen.md`). Minor version skew may produce ULP-level drift, which the 1e-10 tolerance is documented to absorb (per same memory: "1-2 ULP drift … Layer-1 1e-10 tolerance absorbs this").

**If CI fails with `compare_metrics FAIL: scalars.<X>: relative_error <Y>` for some `<Y> > 1e-10`**: this PR has uncovered a real gfortran 13.2 vs 13.3 drift issue. The mitigation:
1. Regenerate `test_run/baselines/tr_iter01/metrics.json` and `tr_tst2/metrics.json` on Ubuntu gfortran-13.2 (either on a separate Linux box, or via a one-off GitHub Actions manual run).
2. Commit the regenerated baselines as a follow-up commit to this PR.
3. The new baseline becomes the CI standard; clavius regens going forward should also be checked at this tolerance.

This is documented as a contingency, not the expected path. Memory says the 1e-10 tolerance has absorbed every prior cross-host drift.

## 7. Acceptance mapping (#192 acceptance items)

| Issue item | Status |
|------------|--------|
| 1. "Add a CI step that invokes `./test_run/run_tests.sh tr_iter01 tr_tst2`" | **Reinterpreted**: same effect (eqdata becomes visible to the test) via the eq-mirror fallback rather than a CI step. Documented in PR description with explicit cross-reference to the design alternative. ✓ |
| 2. "Also stage similar eqdata for fp/wr/wrx/eq/ti/tot equivalence tests as applicable" | **Largely moot**: `eqlib/test_equivalence.py` already has the fallback (no action needed); `fp/wr/wrx/ti` do not use `KNAMEQ` (different mechanism, follow-up). Documented. ✓ (deferred) |
| 3. "Verify equivalence test row in CI now reports `PASSED` (not `SKIPPED`) for at least `test_iter01`" | Verified via §6.2. ✓ |

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CI's gfortran-13.2 produces > 1e-10 drift vs the clavius-gfortran-13.3 baseline → tests `PASSED → FAILED` | Low-Med | Med | Documented contingency at §6.4: regen baselines on Ubuntu gfortran-13.2. The memory + prior cross-host runs say 1e-10 has always absorbed gfortran ULP drift |
| Future eq-physics change drifts the committed `eqdata.{ITER01,TST-2}` invisibly | Med | Low | Follow-up issue (CI-side `eq.x` build + regen) would catch this; currently trust the manually-curated fixtures, same as the rest of the project |
| Reading `eqdata.ITER01` from `FIXTURES_DIR` instead of `TEST_OUTPUT_DIR` exposes a path-relative bug (e.g., tr's eq_init opens additional files relative to CWD) | Low | Med | eq's analogous test has used the same fallback for ~6 months without surfacing this. If tr-side reveals one, fix is small (mirror whatever path adjustment eq did) |
| New 45 KB binary fixture inflates repo size | Very Low | Very Low | One-time cost; mirrors the existing `eqdata.TST-2` precedent in the same dir |
| Outer `@unittest.skipUnless(DEFAULT_SO.exists())` still SKIPs in CI | Very Low | Med | CI's build step at `.github/workflows/python-tests.yml:200+` is under `set -e` (line 200) — a libtrapi.so build failure already fails the job before pytest runs, so this decorator can only SKIP if libtrapi.so was somehow removed between steps (it isn't). The current CI runs do hit `libtrapi.so` (the existing eqlib equiv tests PASS), so this is empirically not happening |

## 9. Follow-up issues to file at PR open

1. **`CI: investigate fp/wr/wrx/ti silent SKIPs in test_equivalence`** — these tests do not use `KNAMEQ`. Whether they SKIP for other reasons (e.g., `lib<X>api.so` path, fixture data absent) is a one-day audit.

2. **`CI: build eq.x graphics-stubbed to regen eqdata.* on each PR for physics-drift detection`** — long-term improvement. Add `eq_static_stubs.f90` (mirroring `tot_static_stubs.f90`), then have CI run eq.x to produce fresh eqdata instead of relying on committed fixtures. Detects eq-physics drift early.

## 10. References

### 10.1 Issues + PRs

- **#192** — driving issue
- **#187** (`e049a1e4`) — the AJRFT change whose silent CI motivated #192
- **PR #193** (`14659b3a`) — the TOT AJRFT triangle that exposed the gap

### 10.2 Memory files

- `feedback_equivalence_must_pass.md` — "SKIP is invisibility" doctrine
- `feedback_scalar_field_triangle.md` — the silent-asymmetry class this PR makes harder to recur
- `reference_clavius_baseline_regen.md` — gfortran drift expectations
- `feedback_never_skip_tests.md` — "do not push if local test cannot PASS"

### 10.3 Code references

- `.github/workflows/python-tests.yml:239-285` — existing demo2014/ht6m staging (out-of-pattern for tr because eqdata isn't auto-generated by `tot` for the tr cases)
- `.github/workflows/python-tests.yml:50` — CI gfortran-13.2 declaration
- `python/trlib/tests/test_equivalence.py:41-47` — path constants (where `FIXTURES_DIR` will be added)
- `python/trlib/tests/test_equivalence.py:178-184` — the SKIP logic being rewritten
- `python/eqlib/tests/test_equivalence.py:53` — `FIXTURES_DIR = HERE.parent / "fixtures"` (the pattern being mirrored)
- `python/eqlib/tests/test_equivalence.py:197-211` — the two-tier fallback being mirrored
- `python/trlib/tests/fixtures/eqdata.TST-2` — precedent for `eqdata.ITER01` mirror
- `python/eqlib/tests/fixtures/eqdata.ITER01` — source for the new trlib fixture copy
- `.gitignore` — `eqdata*` ignore rule + negation list

### 10.4 Reviewer trail

- **Brainstorming (2026-05-12)**: initial scope was Approach A1 (CI workflow step), pivoted to A2 (eq-mirror fallback) after Codex spec review surfaced eq's existing fallback at `python/eqlib/tests/test_equivalence.py:197-205`. A2 is the cleaner root-cause fix and is documented in the PR rationale.
- **Codex spec review #1 (2026-05-12, pre-pivot)**: 1 MED (baseline provenance/drift risk) → §6.4 + §8 row added. 2 LOW (eq fallback awareness → triggered A2 pivot; libtrapi.so set -e wording → corrected throughout).
- Implementation-time pre-push gate: in-house code-reviewer + Codex rescue (parallel) on each commit's diff per CLAUDE.md.
