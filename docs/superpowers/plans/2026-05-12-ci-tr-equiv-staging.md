# trlib `test_equivalence` eq-mirror Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror `python/eqlib/tests/test_equivalence.py`'s two-tier eqdata fallback into `python/trlib/tests/test_equivalence.py` so `TestEquivalence::test_{iter01,tst2}` run on CI instead of silently SKIPping. Closes the invisibility gap that let PR #187 (L-7b-i AJRFT) pass CI for ~10 days with a real 1e-10 failure.

**Architecture:** 3 files in 1 commit on `feat/ci-tr-equiv-staging`:
- `python/trlib/tests/test_equivalence.py` — add `FIXTURES_DIR` constant + 2-tier fallback (verbatim mirror of eq's lines 53, 197-211).
- `python/trlib/tests/fixtures/eqdata.ITER01` — new committed binary fixture (45956 B, copy of `python/eqlib/tests/fixtures/eqdata.ITER01`). The `eqdata.TST-2` mirror already exists in the same dir.
- `.gitignore` — add `!python/trlib/tests/fixtures/eqdata.ITER01` negation next to the existing TST-2 negation.

No CI workflow change, no Fortran build, no other Python source change.

**Tech Stack:** Python 3.10+ (pytest, unittest, ctypes), git, gh CLI.

**Reference:** Spec `docs/superpowers/specs/2026-05-12-ci-tr-equiv-staging-design.md` (HEAD `be5245e7`). TR-side reference for the pattern: `python/eqlib/tests/test_equivalence.py:53,197-211`.

---

## Pre-flight

### Task 0.1: Confirm worktree state + current SKIP behavior

**Files:** none

- [ ] **Step 1: Verify worktree + branch**

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-tr-equiv-staging
pwd                          # → .claude/worktrees/ci-tr-equiv-staging
git branch --show-current    # → feat/ci-tr-equiv-staging
git log --oneline -2
git status -s
```

Expected: worktree CWD, `feat/ci-tr-equiv-staging` branch, HEAD at the spec commit `be5245e7` (or newer), clean working tree (untracked files OK).

- [ ] **Step 2: Confirm trlib test currently SKIPs without staging**

```bash
# Clear any local Phase-0 runner output that might mask the gap.
rm -rf test_run/test_output/tr_iter01 test_run/test_output/tr_tst2
pytest python/trlib/tests/test_equivalence.py -v 2>&1 | tail -10
```

Expected outcome — one of:
- **SKIPPED** with message "`eqdata 'eqdata.ITER01' missing under .../tr_iter01; run \`./test_run/run_tests.sh tr_iter01\` first.`" — this is the gap we're closing.
- **SKIPPED** at the outer `@unittest.skipUnless(DEFAULT_SO.exists())` — happens if `libtrapi.so` is not built locally (common on mac). Still proves nothing about the gap, but it's a known state.

If tests PASS, that means stale `test_run/test_output/<case>/eqdata.<DEV>` exists from a prior run — confirm by `ls test_run/test_output/tr_iter01/` and rerun the cleanup above.

- [ ] **Step 3: Verify eqlib's analogous test still works (regression baseline)**

```bash
pytest python/eqlib/tests/test_equivalence.py -v --collect-only 2>&1 | tail -10
```

Expected: collects without errors (we are NOT modifying eqlib, this is a regression-baseline reference for the pattern we'll mirror).

---

## Phase 1 — Implement the eq-mirror fallback

### Task 1: Copy `eqdata.ITER01` fixture to trlib's fixtures dir

**Files:**
- Create: `python/trlib/tests/fixtures/eqdata.ITER01` (binary, 45956 B, copy of `python/eqlib/tests/fixtures/eqdata.ITER01`)

- [ ] **Step 1: Verify the source fixture exists and is unchanged**

```bash
ls -l python/eqlib/tests/fixtures/eqdata.ITER01
```

Expected: `-rw-r--r-- ... 45956 ... python/eqlib/tests/fixtures/eqdata.ITER01`. If size differs, halt and report — we'd be copying a stale source.

- [ ] **Step 2: Copy via `cp` (binary-safe)**

```bash
cp python/eqlib/tests/fixtures/eqdata.ITER01 \
   python/trlib/tests/fixtures/eqdata.ITER01
```

Do NOT use shell redirection or other text-mode mechanisms — the file is binary.

- [ ] **Step 3: Verify the copy is byte-identical and the dest exists**

```bash
ls -l python/trlib/tests/fixtures/eqdata.ITER01
diff -q python/eqlib/tests/fixtures/eqdata.ITER01 python/trlib/tests/fixtures/eqdata.ITER01
```

Expected: `diff` produces no output (files identical), `ls -l` shows 45956 B.

- [ ] **Step 4: Confirm gitignore currently HIDES the file (untracked)**

```bash
git status -s python/trlib/tests/fixtures/eqdata.ITER01
git check-ignore -v python/trlib/tests/fixtures/eqdata.ITER01
```

Expected: status shows nothing (file is gitignored), check-ignore reports the matching `eqdata*` rule. This proves we need a negation in the next task.

### Task 2: Add `.gitignore` negation for the new fixture

**Files:**
- Modify: `.gitignore` (find the existing TST-2 negation line and add ITER01 negation immediately after)

- [ ] **Step 1: Locate the existing negation block**

```bash
grep -n 'eqdata' .gitignore
```

Expected output (approximate):
```
<N>:eqdata*
<N+1>:!python/trlib/tests/fixtures/eqdata.TST-2
<N+2>:!python/eqlib/tests/fixtures/eqdata.TST-2
<N+3>:!python/eqlib/tests/fixtures/eqdata.ITER01
```

- [ ] **Step 2: Insert the new negation immediately after the existing trlib TST-2 negation**

Edit `.gitignore` so the eqdata block becomes:

```
eqdata*
!python/trlib/tests/fixtures/eqdata.TST-2
!python/trlib/tests/fixtures/eqdata.ITER01
!python/eqlib/tests/fixtures/eqdata.TST-2
!python/eqlib/tests/fixtures/eqdata.ITER01
```

Use the Edit tool (preferred) or insert manually — exact placement is immediately after `!python/trlib/tests/fixtures/eqdata.TST-2` so the two trlib negations are adjacent (mirrors the two eqlib negations being adjacent).

- [ ] **Step 3: Verify the new fixture is now visible to git**

```bash
git status -s python/trlib/tests/fixtures/eqdata.ITER01
git check-ignore -v python/trlib/tests/fixtures/eqdata.ITER01
```

Expected: status shows `?? python/trlib/tests/fixtures/eqdata.ITER01` (untracked, no longer ignored). `check-ignore` returns nothing (exit 1, no match).

### Task 3: Add `FIXTURES_DIR` + 2-tier fallback to trlib's `test_equivalence.py`

**Files:**
- Modify: `python/trlib/tests/test_equivalence.py` — 2 edits:
  - Add `FIXTURES_DIR` constant at lines 41-47 (path-constants block, after `DEFAULT_SO`).
  - Replace SKIP-only logic at lines 178-184 with the 2-tier fallback.

- [ ] **Step 1: Add the `FIXTURES_DIR` constant**

Open `python/trlib/tests/test_equivalence.py` and locate the path-constants block ending with `DEFAULT_SO = REPO / "tr" / "libtrapi.so"` (line 47). Insert one line **immediately after** it:

```python
# Before (lines 41-47):
HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"
DEFAULT_SO = REPO / "tr" / "libtrapi.so"

# After:
HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
BASELINES_DIR = REPO / "test_run" / "baselines"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
FIXTURES_DIR = HERE.parent / "fixtures"
COMPARE_SCRIPT = REPO / "test_run" / "scripts" / "compare_metrics.py"
DEFAULT_SO = REPO / "tr" / "libtrapi.so"
```

The `FIXTURES_DIR` line is positioned **between `TEST_OUTPUT_DIR` and `COMPARE_SCRIPT`** to match eq's ordering (eq's test_equivalence.py:48-53 has the same sequence: HERE / REPO / PYTHON_ROOT / BASELINES_DIR / TEST_OUTPUT_DIR / **FIXTURES_DIR** / COMPARE_SCRIPT).

- [ ] **Step 2: Replace the SKIP-only logic with the 2-tier fallback**

Locate `_check_case` and the block currently at lines 178-184. Replace it as follows:

```python
# Before (lines 178-184 area, inside `_check_case`):
        cwd = None
        knameq = getattr(fixture_module, "STRINGS", {}).get("KNAMEQ")
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
        cwd = None
        knameq = getattr(fixture_module, "STRINGS", {}).get("KNAMEQ")
        if knameq:
            candidate = TEST_OUTPUT_DIR / fixture_module.BASELINE_NAME
            if (candidate / knameq).exists():
                # Prefer dev-generated eqdata (Phase-0 runner output)
                # so local-regen-then-test workflows see their freshly
                # generated data instead of the committed reference.
                cwd = candidate
            elif (FIXTURES_DIR / knameq).exists():
                # CI / fresh checkout: fall back to the committed
                # fixture so the equivalence test runs instead of
                # silently skipping (CLAUDE.md §Test-suite discipline,
                # feedback_equivalence_must_pass.md).
                cwd = FIXTURES_DIR
            else:
                self.skipTest(
                    f"eqdata '{knameq}' missing under {candidate} or "
                    f"{FIXTURES_DIR}; run "
                    f"`./test_run/run_tests.sh {fixture_module.BASELINE_NAME}` first."
                )
```

This is a verbatim structural mirror of `python/eqlib/tests/test_equivalence.py:197-211`, adapted to trlib's local variable names (`knameq`, `candidate`, `fixture_module.BASELINE_NAME` are all the same idioms).

- [ ] **Step 3: Verify the file is syntactically valid**

```bash
python3 -c "import ast; ast.parse(open('python/trlib/tests/test_equivalence.py').read())"
```

Expected: no output (success). Any `SyntaxError` halts.

- [ ] **Step 4: Verify pytest can collect the file**

```bash
pytest python/trlib/tests/test_equivalence.py --collect-only 2>&1 | tail -10
```

Expected: shows `TestEquivalence::test_iter01` and `TestEquivalence::test_tst2` in the collection (collected 2 items minimum). No errors / no `ERROR`.

### Task 4: Local sanity — confirm the fallback engages

**Files:** none (read-only verification)

- [ ] **Step 1: Verify fallback engages when test_output is absent**

```bash
# Ensure test_output is clear (so fallback to FIXTURES_DIR is exercised)
rm -rf test_run/test_output/tr_iter01 test_run/test_output/tr_tst2
pytest python/trlib/tests/test_equivalence.py -v 2>&1 | tail -10
```

Expected — one of:

a. **PASSED** for both test_iter01 and test_tst2 — this means `libtrapi.so` was built locally AND the fallback successfully picked up the committed fixtures. Best outcome.

b. **SKIPPED** at the outer `@unittest.skipUnless(DEFAULT_SO.exists())` — `libtrapi.so` not built locally. The fallback is in place but the test can't end-to-end run on this mac. **Acceptable** — CI will run the end-to-end check.

c. **SKIPPED** with message mentioning the fixture is missing under both `TEST_OUTPUT_DIR / tr_iter01/` AND `FIXTURES_DIR/` — fallback did NOT engage. **Halt and debug**: check Task 1 (fixture copy) and Task 3 (FIXTURES_DIR constant + fallback) — one of them likely has an error.

d. **FAILED** at 1e-10 — fallback engaged but compare_metrics flagged drift. See §6.4 of the spec; this is the contingency path requiring baseline regen on Ubuntu gfortran-13.2.

Document the observed outcome in the commit message under "Local verification:".

- [ ] **Step 2: Verify eqlib regression (sanity that we didn't break eq's pattern)**

```bash
pytest python/eqlib/tests/test_equivalence.py -v --collect-only 2>&1 | tail -5
```

Expected: collection succeeds, same count as in Pre-flight Step 3 (we didn't touch eqlib).

### Task 5: Commit C1

**Files:**
- Stage: `python/trlib/tests/test_equivalence.py`, `python/trlib/tests/fixtures/eqdata.ITER01`, `.gitignore`

- [ ] **Step 1: Confirm exactly the 3 expected files are staged**

```bash
git status -s
```

Expected:
```
M  .gitignore
M  python/trlib/tests/test_equivalence.py
?? python/trlib/tests/fixtures/eqdata.ITER01
```

(After `git add`, `??` becomes `A `.)

- [ ] **Step 2: Stage and commit**

```bash
git add \
  python/trlib/tests/test_equivalence.py \
  python/trlib/tests/fixtures/eqdata.ITER01 \
  .gitignore
git status -s   # confirm A/M lines only

git commit -m "$(cat <<'EOF'
test(trlib): fallback to committed eqdata fixture so test_equivalence runs (#192)

Mirror python/eqlib/tests/test_equivalence.py's two-tier eqdata
fallback into python/trlib/tests/test_equivalence.py so
TestEquivalence::test_{iter01,tst2} run on CI (and on any fresh
checkout) instead of silently SKIPping. Closes the invisibility
gap that let PR #187 (L-7b-i AJRFT) pass CI for ~10 days with a
real 1e-10 failure under chore branch's local test.

Three changes:
- python/trlib/tests/test_equivalence.py: add FIXTURES_DIR constant
  (line 46 area, between TEST_OUTPUT_DIR and COMPARE_SCRIPT) +
  replace SKIP-only logic in _check_case with the two-tier fallback
  (prefer Phase-0 runner output at TEST_OUTPUT_DIR/<case>/<KNAMEQ>,
  fall back to FIXTURES_DIR/<KNAMEQ>, only SKIP if both absent).
  Verbatim structural mirror of eqlib test_equivalence:53, 197-211.
- python/trlib/tests/fixtures/eqdata.ITER01 (new, 45956 B): exact
  copy of python/eqlib/tests/fixtures/eqdata.ITER01. The TST-2
  mirror already lives at python/trlib/tests/fixtures/eqdata.TST-2.
- .gitignore: add !python/trlib/tests/fixtures/eqdata.ITER01
  negation, adjacent to the existing TST-2 negation.

Out of scope (follow-up issues to be filed):
- fp/wr/wrx/ti silent-SKIP audit (different mechanism, no KNAMEQ).
- CI-side eq.x build for fresh eqdata regen (eq-physics drift
  detection); the current fixture-trust model mirrors the project's
  existing convention.

Spec: docs/superpowers/specs/2026-05-12-ci-tr-equiv-staging-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify the commit landed**

```bash
git log --oneline -2
git show --stat HEAD | head -10
```

Expected: HEAD is the new commit, stat shows exactly 3 files (`test_equivalence.py` modified, `eqdata.ITER01` new, `.gitignore` modified).

---

## Phase 2 — Pre-push gate + push + PR

Per CLAUDE.md §Pre-push gate: local pytest + in-house code-reviewer + Codex independent review (parallel) + REVIEW_OK marker + push.

### Task 6: Local pytest matrix (bounded)

**Files:** none

- [ ] **Step 1: Bounded pytest invocation (disk-safety per CLAUDE.md)**

```bash
# macOS has no `timeout`; use pytest's internal --timeout=120 + bound stdout size.
pytest python/totlib/tests/ python/trlib/tests/ test_run/scripts/tests/ \
  --forked --timeout=120 --timeout-method=signal -v 2>&1 \
  | head -c 1048576 | tail -50
```

Expected: all tests PASS or SKIP for known reasons. Particularly:
- Pre-existing failures that are NOT caused by this PR are acceptable; document them in the PR description.
  - `test_close_raises_exception_group_when_multiple_modules_fail` (Python 3.10 lacks `ExceptionGroup`; test docstring acknowledges).
  - `test_fails_when_baseline_is_tiny_and_actual_is_zero` (pre-existing on develop).
- `python/trlib/tests/test_equivalence.py::TestEquivalence::test_{iter01,tst2}` outcome per Task 4 Step 1.

If anything NEW fails (not in the pre-existing list), halt and investigate.

### Task 7: Parallel reviewers (in-house + Codex) on diff

**Files:** none

- [ ] **Step 1: Compute diff range and stage variables**

```bash
git fetch origin
git log --oneline origin/develop..HEAD
```

Expected: exactly 2 commits (spec `be5245e7` + impl C1). Note both SHAs.

- [ ] **Step 2: Fire BOTH agents in ONE message (parallel)**

The in-house reviewer subagent type is `feature-dev:code-reviewer` per CLAUDE.md; fall back to `general-purpose` if unavailable. Codex is `codex:codex-rescue`. Both Agent calls go in a SINGLE message so they run concurrently.

Prompt template (use the same body for both, only `subagent_type` differs):

> Review the diff `origin/develop..HEAD` (2 commits) on branch `feat/ci-tr-equiv-staging` in the worktree `/Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-tr-equiv-staging/`. Issue #192. The spec is at `docs/superpowers/specs/2026-05-12-ci-tr-equiv-staging-design.md`.
>
> Focus areas:
>
> 1. **eq-mirror parity**: Does the new trlib fallback logic at `python/trlib/tests/test_equivalence.py` mirror eqlib's `:53, 197-211` exactly (modulo local variable names)? Spot-check by `git show` + comparison.
> 2. **Fixture integrity**: `python/trlib/tests/fixtures/eqdata.ITER01` is binary 45956 B. Confirm `diff python/eqlib/tests/fixtures/eqdata.ITER01 python/trlib/tests/fixtures/eqdata.ITER01` is empty (byte-identical).
> 3. **.gitignore negation**: confirm the new line is positioned adjacent to the existing TST-2 negation and uses the correct path syntax.
> 4. **Drift risk** (Codex MED from spec review #1, §6.4): is the test_run/baselines/tr_iter01/metrics.json + tr_tst2/metrics.json compatible with Ubuntu gfortran-13.2 at 1e-10? You cannot verify this on mac; flag as "verify in CI".
> 5. **Pre-existing failures**: this PR does NOT touch test_pipeline.py or test_compare_metrics.py; if the local pytest matrix shows their failures, that's a known pre-existing issue, not caused by this PR.
>
> Report HIGH (must-fix before push) / MED (consider) / LOW. Under 400 words.

- [ ] **Step 3: Triage findings**

Paste HIGH + MED from both reviewers back to the user. For each:
- HIGH: fix in a new commit on this branch before push; re-run Task 6 (pytest) + Task 7 (re-review).
- MED: discuss; fix or defer per user judgment.
- LOW: defer (out of scope here).

### Task 8: REVIEW_OK marker + push + PR

**Files:**
- Marker: `$(git rev-parse --git-common-dir)/REVIEW_OK_<HEAD-sha>` (touch-only)

- [ ] **Step 1: Write marker for current HEAD**

```bash
MARKER="$(git rev-parse --git-common-dir)/REVIEW_OK_$(git rev-parse HEAD)"
touch "$MARKER"
ls -la "$MARKER"
```

Expected: file exists, size 0.

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/ci-tr-equiv-staging
```

Expected: `pre-push: review marker present — OK` and a `new branch` line. If the pre-push hook rejects, halt and check the marker was written for the correct SHA.

- [ ] **Step 3: Create PR**

```bash
env -u GITHUB_TOKEN gh pr create --base develop --head feat/ci-tr-equiv-staging \
  --title "test(trlib): eq-mirror eqdata fallback so test_equivalence runs (#192)" \
  --body "$(cat <<'EOF'
## Summary

Closes the silent-SKIP invisibility class on `python/trlib/tests/test_equivalence.py` by mirroring `python/eqlib/tests/test_equivalence.py`'s two-tier eqdata fallback into trlib. Closes #192.

## Why scope is in-test fallback rather than a CI shim

The original issue body proposes adding a CI step that pre-stages eqdata. During design-stage Codex review (round 1, on the brainstorming spec) we discovered `python/eqlib/tests/test_equivalence.py:197-211` already has a two-tier fallback (prefer `TEST_OUTPUT_DIR`, fall back to `FIXTURES_DIR`) — eq is symmetric with what we want; tr is the asymmetric one. Mirroring eq's pattern in trlib is the root-cause fix: it works on CI **and** on any fresh checkout, with no CI yaml change required.

## Changes (3 files, 1 commit)

| File | Change |
|------|--------|
| `python/trlib/tests/test_equivalence.py` | Add `FIXTURES_DIR` constant + 2-tier fallback (verbatim mirror of eq's `:53, :197-211`) |
| `python/trlib/tests/fixtures/eqdata.ITER01` | New committed binary (45956 B, byte-identical copy of `python/eqlib/tests/fixtures/eqdata.ITER01`). `eqdata.TST-2` mirror already exists in the same dir |
| `.gitignore` | Add `!python/trlib/tests/fixtures/eqdata.ITER01` negation, adjacent to existing TST-2 negation |

No CI workflow change. No Fortran build. No other Python source change.

## Verification

- [x] **mac local** (per spec §6.1): `pytest python/trlib/tests/test_equivalence.py --collect-only` succeeds; full run skips at outer `@unittest.skipUnless(libtrapi.so)` on this mac (no libtrapi.so built locally) — that's expected behavior, CI will exercise the path.
- [x] **mac local regression**: eqlib's test_equivalence still collects and (where libtrapi.so/libeqapi.so exist) runs unaffected.
- [ ] **CI** (this PR run): `python/trlib/tests/test_equivalence.py::TestEquivalence::test_iter01` and `test_tst2` should report `PASSED`, not `SKIPPED`. Inspect the pytest log for the matrix's Python 3.11 and 3.13 jobs.

## Drift contingency (spec §6.4)

If CI fails at 1e-10 (CI gfortran-13.2 vs baseline-generation-host gfortran-13.3 ULP drift), regen `test_run/baselines/tr_{iter01,tst2}/metrics.json` on Ubuntu gfortran-13.2 and add as a follow-up commit. Not expected based on prior cross-host runs (memory: 1-2 ULP, 1e-10 absorbs it).

## Follow-up issues to be filed after this PR opens

- `CI: investigate fp/wr/wrx/ti silent SKIPs in test_equivalence` — different mechanism (no `KNAMEQ`), separate audit.
- `CI: build eq.x graphics-stubbed to regen eqdata.* for physics-drift detection` — long-term improvement.

## Pre-existing failures (NOT introduced)

- `test_close_raises_exception_group_when_multiple_modules_fail` — Python 3.10 only (test docstring notes; CI runs 3.11+).
- `test_fails_when_baseline_is_tiny_and_actual_is_zero` — pre-existing on develop (`compare_metrics` edge case).

Neither test file is touched by this PR.

## Review trail

- Brainstorming (2026-05-12): scope choice "tr-only narrow", approach decision A1→A2 pivot triggered by Codex spec review #1.
- Spec at `docs/superpowers/specs/2026-05-12-ci-tr-equiv-staging-design.md` (committed `be5245e7`).
- Per-commit pre-push: in-house code-reviewer + Codex rescue ran in parallel on `origin/develop..HEAD` — findings triaged per CLAUDE.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: returns PR URL (e.g. `https://github.com/k-yoshimi/task/pull/<N>`).

- [ ] **Step 4: Wait for Bugbot trigger / verify it**

Bugbot typically auto-triggers within a few minutes of push. If after ~10 minutes there's no Bugbot review on the PR (check via `gh pr view <N> --json reviews`), comment `@cursor review` per memory `feedback_cursor_review.md`.

Bash background poll (per the AJRFT PR #193 pattern) can be used to wait for completion:

```bash
until env -u GITHUB_TOKEN gh pr view <PR#> --json statusCheckRollup \
    --jq '.statusCheckRollup[] | select(.name=="Cursor Bugbot") | .conclusion' \
    2>/dev/null | grep -qE '^(SUCCESS|FAILURE|NEUTRAL|CANCELLED|TIMED_OUT)$'; do
  sleep 30
done
env -u GITHUB_TOKEN gh pr view <PR#> --json reviews --jq '.reviews[-1]'
```

Run with `run_in_background: true` to free the session.

- [ ] **Step 5: Address Bugbot findings (if any)**

If Bugbot returns findings, address them as follow-up commits. Re-trigger pre-push gate (Tasks 6–8) for each new commit before re-pushing.

If Bugbot returns `✅ Bugbot reviewed your changes and found no new issues!`, the PR is ready for user-approved merge.

---

## Acceptance checklist (cross-reference to spec §7 / issue #192)

- [ ] **#1** "Add a CI step that invokes `./test_run/run_tests.sh tr_iter01 tr_tst2`" — **adapted**: same effect (eqdata becomes visible to the test) via the eq-mirror in-test fallback. Documented in PR description.
- [ ] **#2** "Also stage similar eqdata for fp/wr/wrx/eq/ti/tot equivalence tests as applicable" — **mostly moot**: `eqlib/test_equivalence.py` already has the fallback (no action); `fp/wr/wrx/ti` do not use `KNAMEQ` (follow-up). Follow-up issue filed at PR open.
- [ ] **#3** "Verify equivalence test row in CI now reports `PASSED` (not `SKIPPED`) for at least `test_iter01`" — verified via PR's CI run (Task 8 Step 3 outcome).

---

## Self-review notes (this plan)

- **Spec coverage**: every spec §4 component maps to a task: §4.2.1 `test_equivalence.py` → Task 3 (2 sub-steps); §4.2.2 `eqdata.ITER01` → Task 1; §4.2.3 `.gitignore` → Task 2. Verification at §6.1 → Task 4. CI verification at §6.2 → Task 8 Step 3 + acceptance checklist.
- **Placeholder scan**: each step has exact commands + expected output. No TBD/TODO. Bugbot polling shows `<PR#>` placeholder but it's a value to substitute at runtime (the PR doesn't exist yet at plan-write time).
- **Type/name consistency**: `FIXTURES_DIR`, `TEST_OUTPUT_DIR`, `KNAMEQ`, `candidate`, `fixture_module.BASELINE_NAME` are used identically across Task 3 sub-steps. Path conventions (worktree at `.claude/worktrees/ci-tr-equiv-staging/`, branch `feat/ci-tr-equiv-staging`) are consistent.
