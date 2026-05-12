# CI Baseline Regen Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workflow_dispatch CI job that regenerates `test_run/baselines/<fixture>/metrics.json` files in CI's gfortran-13.2 / Ubuntu-24.04 environment, plus the Fortran graphics-stubs needed so `eq.x` and `tr2` standalone binaries can build without graphics libraries. Closes #197 and unblocks #190.

**Architecture:** 6 files in 1 commit on `feat/ci-regen-baselines-workflow`.
- **Layer A (Fortran)**: 2 new `*_static_stubs.f90` files (eq + tr, each a copy of `tot/tot_static_stubs.f90`) and 2 `Makefile` edits adding `GFLIBS`-empty gates for the standalone binary targets. Mirrors the existing `tot/Makefile:64-70, 178-184` precedent.
- **Layer B (CI)**: 1 new `.github/workflows/regen-baselines.yml` file with `workflow_dispatch` trigger, `fixtures` input (default `"eq_tst2 tr_tst2"`), pinned to `ubuntu-24.04`, artifact upload at the end. Reuses the python-tests.yml build steps for environment setup.
- **Layer C (Spec)**: design doc at `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md` (already committed in this branch).

User downloads artifact via Actions UI, manually extracts metrics.json, commits to a feature branch to resolve #190 (and any other compiler-drift baseline issue). Auto-PR/auto-commit is explicitly deferred.

**Tech Stack:** Fortran 2003 (`*.f90`, no-op stub subroutines), GNU make (Makefile gate pattern), GitHub Actions (workflow_dispatch + actions/upload-artifact@v4), bash, jq, Python 3.11 (`extract_<module>_metrics.py`).

**Reference:** Spec `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md` (HEAD `6deddeb0`, 376 lines, 4 Codex review rounds converged). Issue #197.

---

## Pre-flight

### Task 0.1: Confirm worktree state + sanity baseline

**Files:** none

- [ ] **Step 1: Verify worktree, branch, HEAD**

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-baseline-regen-workflow
pwd                          # → .claude/worktrees/ci-baseline-regen-workflow
git branch --show-current    # → feat/ci-regen-baselines-workflow
git rev-parse HEAD           # → 6deddeb0 (spec) or newer
git status -s                # → clean (untracked files OK)
git log --oneline -3
```

Expected: worktree CWD, `feat/ci-regen-baselines-workflow` branch, HEAD at spec commit `6deddeb0` (or newer), clean working tree.

- [ ] **Step 2: Confirm the source stub file exists and verify line count**

```bash
ls -l tot/tot_static_stubs.f90
wc -l tot/tot_static_stubs.f90
grep -c '^      SUBROUTINE\|^SUBROUTINE\|^  SUBROUTINE' tot/tot_static_stubs.f90
```

Expected: file exists, ~378 lines, ~100 SUBROUTINE declarations. If line count or stub count is dramatically different from spec's "~378 lines, ~100 stubs", halt and investigate — the spec was written against a specific snapshot.

- [ ] **Step 3: Check existing tot Makefile gate (the pattern to mirror)**

```bash
grep -B 2 -A 6 'TOT_STATIC_STUBS_OBJ' tot/Makefile | head -25
```

Expected to see (verbatim):

```
ifeq ($(strip $(GFLIBS)),)
TOT_STATIC_STUBS_OBJ = tot_static_stubs.o
else
TOT_STATIC_STUBS_OBJ =
endif

# ... later ...
tot : $(LIB_MTX) $(LIBS) totmenu.o totregress.o totmain.o $(TOT_STATIC_STUBS_OBJ)
	$(FLINKER) totmenu.o totregress.o totmain.o $(TOT_STATIC_STUBS_OBJ) -o $@ $(FFLAGS) $(LIBS) $(FLIBS) $(LIBX_MTX)
```

This is the precedent we'll mirror in eq/ and tr/.

---

## Phase 1 — Layer A: Add eq + tr graphics stubs and Makefile gates

### Task 1: Add `eq/eq_static_stubs.f90`

**Files:**
- Create: `eq/eq_static_stubs.f90` (copy of `tot/tot_static_stubs.f90` with adjusted comment header)

- [ ] **Step 1: Copy the source file**

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-baseline-regen-workflow
cp tot/tot_static_stubs.f90 eq/eq_static_stubs.f90
ls -l eq/eq_static_stubs.f90
diff -q tot/tot_static_stubs.f90 eq/eq_static_stubs.f90    # expect: files identical (no output)
```

- [ ] **Step 2: Rewrite the comment header (top of file, lines 1-~80)**

Open `eq/eq_static_stubs.f90` and replace the leading comment block (everything before the first `SUBROUTINE` declaration — typically lines 1-80) with eq-specific text. Keep the `! tot_static_stubs.f90` line replaced as `! eq_static_stubs.f90`. The body (stubs) stays identical.

Use the Edit tool to replace the entire leading comment block. New header:

```fortran
! eq_static_stubs.f90
!
! Phase L-? (issue #197 follow-up): graphics-symbol stubs for the
! standalone `eq` Fortran binary path. eq/Makefile's `eq` target links
! the full TASK archive chain (libgrf.a + libeq.a + libpl.a + ...), which
! transitively references ~100 GSAF graphics primitives (GSCALE, GFRAME,
! GPLOTP, CONTF*, ...) that the per-module *_graphics_stubs.f90 files
! only partially cover. With CI's GFLIBS= (no graphics linkage), those
! references go unresolved and the standalone `eq` binary fails to link.
!
! This file provides no-op stubs for every graphics symbol that the
! standalone-link path requires. None are exercised by the eq lifecycle
! that produces eqdata + metrics regression dumps — the eq solver does
! not call into the GR* / EQGS* output paths during a regression-mode
! run — so no-op behaviour is safe.
!
! Scope:
!   - eq_graphics_stubs.f90 (existing) stays as the minimal stub set
!     baked into libeqapi.so for the dlopen / Python wrapper path.
!   - eq_static_stubs.f90 (this file) is linked ONLY into the
!     standalone `eq` binary when GFLIBS is empty (CI / no-graphics
!     build), NEVER into libeqapi.so. The two stub sets coexist without
!     symbol conflict because their object files target distinct binaries.
!
! Mirrors tot/tot_static_stubs.f90; the stub body is identical (the
! GSAF symbol set is shared across modules). Files are duplicated rather
! than shared to preserve per-module isolation that the existing
! *_graphics_stubs.f90 PIC variants already follow. A future refactor
! to a single shared `lib/graphics_stubs.f90` is tracked as a follow-up
! per spec §3 non-goals.
!
! Two of the ~100 entries are functions whose return value the callers
! consume; the rest are subroutines used as side-effecting calls and
! return immediately. See `tot/tot_static_stubs.f90`'s header for the
! detailed audit notes that apply identically here.
```

The exact transition point from header comment to first SUBROUTINE varies between tot's file (around line 80) — locate the first `^SUBROUTINE` or `^      SUBROUTINE` line and place the new header above it, removing the old header block.

- [ ] **Step 3: Verify the body is unchanged**

```bash
# Compare body (everything after the header). Use diff with a stable cutoff.
# Find first SUBROUTINE line in each file and diff from there.
TOT_FIRST=$(grep -n '^.*SUBROUTINE' tot/tot_static_stubs.f90 | head -1 | cut -d: -f1)
EQ_FIRST=$(grep -n '^.*SUBROUTINE' eq/eq_static_stubs.f90 | head -1 | cut -d: -f1)
diff <(tail -n +"$TOT_FIRST" tot/tot_static_stubs.f90) <(tail -n +"$EQ_FIRST" eq/eq_static_stubs.f90)
```

Expected: no output (bodies identical from first SUBROUTINE onward).

- [ ] **Step 4: AST sanity (gfortran parse-only, no link)**

```bash
gfortran -c -fsyntax-only eq/eq_static_stubs.f90 2>&1 | head
```

Expected: no errors. (Just a parse check; not a real compile.)

### Task 2: Edit `eq/Makefile` — add GFLIBS gate + link eq_static_stubs.o

**Files:**
- Modify: `eq/Makefile` (current `eq` target around line 116-117)

- [ ] **Step 1: Find the `eq` target definition**

```bash
grep -n '^eq:\|^eq :' eq/Makefile
```

Expected: line ~116-117, format like:
```
eq: libs libeq.a eqmain.o
	$(FLINKER) eqmain.o $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

- [ ] **Step 2: Insert GFLIBS gate above the `eq` target**

Open `eq/Makefile`. Just BEFORE the `eq:` target line, insert (use the Edit tool):

```makefile
# Issue #197: link eq_static_stubs.o into the standalone `eq` binary
# when GFLIBS is empty (CI / no-graphics build), so the GSAF symbol
# references in the archive chain (libgrf.a / libtask.a / etc.) resolve.
# Mirrors tot/Makefile:64-70's TOT_STATIC_STUBS_OBJ gate.
ifeq ($(strip $(GFLIBS)),)
EQ_STATIC_STUBS_OBJ = eq_static_stubs.o
else
EQ_STATIC_STUBS_OBJ =
endif

```

- [ ] **Step 3: Update the `eq` target to depend on + link the stubs**

Replace the existing `eq:` target line and recipe with:

```makefile
eq: libs libeq.a eqmain.o $(EQ_STATIC_STUBS_OBJ)
	$(FLINKER) eqmain.o $(EQ_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

The dependency `$(EQ_STATIC_STUBS_OBJ)` is empty-expansion when GFLIBS is populated (no link impact); equals `eq_static_stubs.o` when GFLIBS is empty (link order matters — keep it right after eqmain.o so any symbols referenced by libs at the end can still see it).

- [ ] **Step 4: Smoke build (mac, with GFLIBS empty to exercise the new path)**

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-baseline-regen-workflow
make -C eq clean
GFLIBS="" make -C eq eq 2>&1 | tail -20
ls -l eq/eq 2>&1 | head
```

Expected one of:
- (a) `eq/eq` binary appears, link succeeds — best outcome. Done.
- (b) Link fails with errors mentioning OTHER GSAF symbols not in tot_static_stubs.f90's stub set (e.g., a new symbol referenced by eq's archive chain but not tot's). Add the missing stubs to `eq/eq_static_stubs.f90` and re-run. Common cases: any `EQ*` (EQGS*, EQGCONT*, EQGTRAJ*) that tot might not pull in but eq does.
- (c) Link fails with macOS-specific errors (X11, libSystem, ...). That's a known macOS quirk separate from this change. Verify by `git stash` + rerunning the SAME `make` — if it fails identically, the issue is pre-existing. Document and rely on CI for end-to-end verification.

### Task 3: Add `tr/tr_static_stubs.f90`

**Files:**
- Create: `tr/tr_static_stubs.f90` (copy of `tot/tot_static_stubs.f90` with adjusted comment header)

- [ ] **Step 1: Copy the source**

```bash
cp tot/tot_static_stubs.f90 tr/tr_static_stubs.f90
ls -l tr/tr_static_stubs.f90
```

- [ ] **Step 2: Rewrite the comment header**

Same approach as Task 1 Step 2. The header text is identical to eq's except:
- `! tot_static_stubs.f90` → `! tr_static_stubs.f90`
- `standalone `eq`` → `standalone `tr2``
- `eq/Makefile's `eq` target` → `tr/Makefile's `tr2` target`
- `libeq.a + libpl.a` → `libtr2.a + libeq.a + libpl.a` (tr2 also pulls in libeq.a transitively)
- `eq_graphics_stubs.f90` → `tr_graphics_stubs.f90` (the existing PIC-only stubs in tr/)

Use the Edit tool with the same template as Task 1 Step 2, substituting the names.

- [ ] **Step 3: Verify body matches tot's**

```bash
TOT_FIRST=$(grep -n '^.*SUBROUTINE' tot/tot_static_stubs.f90 | head -1 | cut -d: -f1)
TR_FIRST=$(grep -n '^.*SUBROUTINE' tr/tr_static_stubs.f90 | head -1 | cut -d: -f1)
diff <(tail -n +"$TOT_FIRST" tot/tot_static_stubs.f90) <(tail -n +"$TR_FIRST" tr/tr_static_stubs.f90)
```

Expected: no output.

- [ ] **Step 4: AST sanity**

```bash
gfortran -c -fsyntax-only tr/tr_static_stubs.f90 2>&1 | head
```

Expected: no errors.

### Task 4: Edit `tr/Makefile` — add GFLIBS gate + link tr_static_stubs.o

**Files:**
- Modify: `tr/Makefile` (current `tr2` target around line 132)

- [ ] **Step 1: Find the `tr2` target**

```bash
grep -n '^tr2:\|^tr2 :' tr/Makefile
```

Expected: line ~132, format like:
```
tr2: $(LIBS2) $(OBJDIR)/trmain.o
	$(FLINKER) $(OBJDIR)/trmain.o $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

- [ ] **Step 2: Insert GFLIBS gate above the `tr2` target**

Use the Edit tool to insert before the `tr2:` line:

```makefile
# Issue #197: link tr_static_stubs.o into the standalone `tr2` binary
# when GFLIBS is empty (CI / no-graphics build). Mirrors
# tot/Makefile:64-70 and eq/Makefile's analogous gate.
ifeq ($(strip $(GFLIBS)),)
TR_STATIC_STUBS_OBJ = tr_static_stubs.o
else
TR_STATIC_STUBS_OBJ =
endif

```

- [ ] **Step 3: Update the `tr2` target**

Replace the `tr2:` target line + recipe with:

```makefile
tr2: $(LIBS2) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ)
	$(FLINKER) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

- [ ] **Step 4: Smoke build**

```bash
make -C tr clean
GFLIBS="" make -C tr tr2 2>&1 | tail -20
ls -l tr/tr2 2>&1 | head
```

Expected outcomes parallel Task 2 Step 4. (a) success / (b) missing GSAF stub / (c) macOS-specific issue.

---

## Phase 2 — Layer B: CI workflow

### Task 5: Create `.github/workflows/regen-baselines.yml`

**Files:**
- Create: `.github/workflows/regen-baselines.yml` (~210 lines)

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/regen-baselines.yml` with the following content. Note: the build-deps + BPSD-clone + makefile-env steps are **derived from** `python-tests.yml` (lines 50-150 region) — they're not copy-paste; we extract the minimum needed.

```yaml
name: regen-baselines

# Issue #197: in-CI baseline regen for fixtures that exhibit
# cross-host compiler-version drift (notably eq_tst2 / tr_tst2 at
# ~3e-9 between clavius gfortran 13.3 and CI gfortran 13.2).
# Generates metrics.json in CI's own environment, uploads as
# artifact for the user to download and commit.

on:
  workflow_dispatch:
    inputs:
      fixtures:
        description: 'Space-separated fixture names (default: eq_tst2 tr_tst2)'
        default: 'eq_tst2 tr_tst2'
        required: false

# Stacked manual triggers on the same ref cancel the in-flight run —
# the user re-triggered because they want fresh output. Mirrors
# python-tests.yml:15-17.
concurrency:
  group: regen-baselines-${{ github.ref }}
  cancel-in-progress: true

# Least-privilege: workflow only checks out source and uploads artifacts.
# No repo writes, no PR comments. If auto-commit / auto-PR is added in
# a future iteration, expand to `contents: write` + `pull-requests: write`.
permissions:
  contents: read

jobs:
  regen:
    name: regen-baselines (Python 3.11)
    # Pinned to ubuntu-24.04 (NOT ubuntu-latest) — baseline reproducibility
    # depends on a stable gfortran version. Ubuntu 24.04's default is
    # gfortran 13.2.0 (matches python-tests.yml). Re-pin to the next LTS
    # when GitHub deprecates this image and regenerate baselines once.
    runs-on: ubuntu-24.04
    timeout-minutes: 20

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Fortran/C build deps
        shell: bash
        run: |
          set -eo pipefail
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            gfortran gcc make jq
          gfortran --version | head -1

      - name: Clone BPSD (patched fork k-yoshimi/bpsd@develop)
        shell: bash
        run: |
          set -eo pipefail
          git clone --depth 1 --branch develop \
            https://github.com/k-yoshimi/bpsd.git \
            "$GITHUB_WORKSPACE/../bpsd"
          ( cd "$GITHUB_WORKSPACE/../bpsd" && git log --oneline -1 )

      - name: Provision mtxp/make.mtxp from nompi template
        shell: bash
        run: |
          set -eo pipefail
          cp mtxp/make.mtxp.nompi mtxp/make.mtxp
          head -3 mtxp/make.mtxp

      - name: Provision make.header for Linux gfortran (no graphics)
        shell: bash
        run: |
          set -eo pipefail
          # python-tests.yml provisions an empty GFLIBS / FLIBS to disable
          # graphics linkage. Mirror that here. See python-tests.yml around
          # the "Provision make.header" step for the canonical contents.
          # We reuse the same incantation by copying from the established
          # template in the make.header chain.
          cat > make.header <<'EOF'
          # Auto-generated by regen-baselines.yml for the no-graphics CI
          # build path. Mirrors python-tests.yml's make.header provisioning.
          FC = gfortran
          CC = gcc
          GFLIBS =
          FLIBS =
          LIBLA = nolapack.f
          MDSLIB = nomdsplus.f
          EOF
          cat make.header

      - name: Build the dependency chain (lib/, mtxp/, bpsd/, pl/, eq/, fp/, ti/, wr/, wrx/)
        shell: bash
        run: |
          set -eo pipefail
          make -C "$GITHUB_WORKSPACE/../bpsd" libbpsd.a
          make -C lib libtask.a libgrf.a libmds.a
          make -C lib libtask_pic.a libgrf_pic.a libmds_pic.a
          make -C mtxp libmtxnompi.o libmtxbnd.o
          make -C mtxp libmtxnompi_pic.o libmtxbnd_pic.o
          make -C pl libpl.a
          make -C eq libeq.a
          make -C tr libtr2.a
          make -C fp libfp.a
          make -C ti libti.a
          make -C wr libwr.a
          make -C wrx libwr.a   # wrx Makefile names its archive libwr.a too

      - name: Build standalone eq / tr2 / tot binaries (graphics-stubbed)
        shell: bash
        run: |
          set -eo pipefail
          # Layer A enables these builds via the new *_static_stubs.f90
          # files + GFLIBS-empty Makefile gates.
          make -C eq eq
          make -C tr tr2
          make -C tot tot
          ls -l eq/eq tr/tr2 tot/tot

      - name: Regenerate metrics.json per fixture
        shell: bash
        run: |
          set -eo pipefail
          mkdir -p regen-output
          for fixture in ${{ inputs.fixtures }}; do
            echo "::group::regen $fixture"
            mkdir -p "regen-output/$fixture"

            # Run the canonical regen flow. run_tests.sh handles
            # dep-copy internally (eqdata.* / *.gs propagation from
            # dependent test outputs). The "|| true" absorbs the
            # expected baseline-mismatch exit; the actual success
            # signal is the regress.dat file appearing.
            ./test_run/run_tests.sh "$fixture" || true

            # Determine module prefix from the fixture name.
            case "$fixture" in
              tr_*)  module=tr  ;;
              eq_*)  module=eq  ;;
              fp_*)  module=fp  ;;
              ti_*)  module=ti  ;;
              wr_*)  module=wr  ;;
              wrx_*) module=wrx ;;
              tot_*) module=tot ;;
              *) echo "ERROR: unknown module prefix for fixture '$fixture'"; exit 1 ;;
            esac
            dump_file="test_run/test_output/$fixture/${module}_regress.dat"

            # Narrow failure detection: distinguish "binary crashed" /
            # "missing input" (real failure) from "comparison failed"
            # (expected — that's why we're regenerating).
            test -s "$dump_file" || {
              echo "ERROR: dump file $dump_file is empty or missing"
              echo "Last 50 lines of run_tests.sh output:"
              ls -la "test_run/test_output/$fixture/" 2>&1
              exit 1
            }

            # Extract metrics. The extract scripts SystemExit on
            # malformed dumps (missing dimension keys, mismatched
            # profile row count, empty scalars for tr/eq).
            python3 "test_run/scripts/extract_${module}_metrics.py" "$dump_file" \
              > "regen-output/$fixture/metrics.json"

            # Defense-in-depth shape check (per-module).
            case "$module" in
              tot)
                # tot scalars CAN be {} when TR_PRESENT=0 (per
                # extract_tot_metrics.py:5-10). Use dimension keys
                # instead.
                jq -e '.NT >= 0 and .NRMAX >= 0 and .NSMAX >= 0' \
                  "regen-output/$fixture/metrics.json" > /dev/null
                ;;
              *)
                # tr / eq / fp / ti / wr / wrx require non-empty scalars.
                jq -e '.scalars | length > 0' \
                  "regen-output/$fixture/metrics.json" > /dev/null
                ;;
            esac

            echo "  $fixture: scalars=$(jq -r '.scalars | length' regen-output/$fixture/metrics.json)"
            echo "::endgroup::"
          done

          echo
          echo "=== regen-output/ summary ==="
          find regen-output -type f -name '*.json' -exec ls -l {} \;

      - name: Upload regenerated baselines as artifact
        uses: actions/upload-artifact@v4
        with:
          name: baselines-${{ github.run_id }}
          path: regen-output/
          # 90-day retention matches GH Actions default. If 90 days
          # proves too short for the manual review-and-commit cadence,
          # make retention a workflow_dispatch input.
          retention-days: 90
          if-no-files-found: error
```

- [ ] **Step 2: Lint the YAML (syntax check)**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/regen-baselines.yml'))" && echo OK
```

Expected: `OK` (no exceptions).

If `actionlint` is available:

```bash
which actionlint && actionlint .github/workflows/regen-baselines.yml 2>&1 | head
```

If it's not installed, the YAML syntax check above is sufficient for local validation. CI itself is the authoritative validator.

- [ ] **Step 3: Verify referenced files exist**

```bash
# All scripts the workflow references must exist.
for f in \
  test_run/run_tests.sh \
  test_run/scripts/extract_eq_metrics.py \
  test_run/scripts/extract_tr_metrics.py \
  test_run/scripts/extract_tot_metrics.py \
  test_run/scripts/extract_fp_metrics.py \
  test_run/scripts/extract_ti_metrics.py \
  test_run/scripts/extract_wr_metrics.py \
  test_run/scripts/extract_wrx_metrics.py; do
  test -f "$f" && echo "✓ $f" || echo "✗ MISSING: $f"
done
```

All must show `✓`. If any is missing, halt — the workflow's per-module dispatch references that file. (Some extractors may be missing for less-common modules; only require the ones we need.)

---

## Phase 3 — Commit + verification

### Task 6: Final local verification before commit

**Files:** none (verification only)

- [ ] **Step 1: Confirm exactly 5 files staged for commit (plus the spec already committed)**

```bash
git status -s
```

Expected:
```
?? .github/workflows/regen-baselines.yml
?? eq/eq_static_stubs.f90
?? tr/tr_static_stubs.f90
 M eq/Makefile
 M tr/Makefile
```

- [ ] **Step 2: Verify the existing CI workflow still parses (regression sanity)**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/python-tests.yml'))" && echo OK
```

Expected: `OK`. We haven't modified python-tests.yml, but this verifies our YAML changes didn't break parser-shared assumptions.

- [ ] **Step 3: Verify the gate works WITH GFLIBS populated too (regression sanity)**

```bash
# Confirm the GFLIBS=non-empty branch produces empty EQ_STATIC_STUBS_OBJ
# (so existing clavius / graphics-populated builds are unaffected).
echo "Simulated GFLIBS-populated build expansion:"
GFLIBS="-L/foo -lg3d-gfc64" make -C eq -n eq 2>&1 | grep eq_static_stubs.o || echo "(eq_static_stubs.o NOT in link line — correct)"
GFLIBS="-L/foo -lg3d-gfc64" make -C tr -n tr2 2>&1 | grep tr_static_stubs.o || echo "(tr_static_stubs.o NOT in link line — correct)"
echo
echo "Simulated GFLIBS-empty build expansion:"
GFLIBS="" make -C eq -n eq 2>&1 | grep eq_static_stubs.o && echo "(eq_static_stubs.o IS in link line — correct)"
GFLIBS="" make -C tr -n tr2 2>&1 | grep tr_static_stubs.o && echo "(tr_static_stubs.o IS in link line — correct)"
```

Expected: gate switches correctly in both directions.

### Task 7: Commit the change

**Files:**
- Stage: `eq/eq_static_stubs.f90`, `tr/tr_static_stubs.f90`, `eq/Makefile`, `tr/Makefile`, `.github/workflows/regen-baselines.yml`

- [ ] **Step 1: Stage and commit**

```bash
git add \
  eq/eq_static_stubs.f90 \
  tr/tr_static_stubs.f90 \
  eq/Makefile \
  tr/Makefile \
  .github/workflows/regen-baselines.yml

git status -s   # confirm A/M lines for exactly these 5 files

git commit -m "$(cat <<'EOF'
ci+eq+tr: workflow_dispatch baseline regen + graphics-stubs for eq.x / tr2 (#197)

Adds an in-CI baseline-regeneration workflow plus the Fortran
graphics-stubs that let the standalone eq / tr2 binaries build in
CI's gfortran-13.2 / Ubuntu-24.04 / no-graphics environment.

Closes #197 and unblocks the #190 (tr_tst2 baseline backfill) path
that PR #196 ran into.

Layer A (Fortran):
- eq/eq_static_stubs.f90: NEW, copy of tot/tot_static_stubs.f90 with
  comment header adjusted for eq context. ~378 lines, ~100 GSAF
  no-op SUBROUTINEs + 2 FUNCTIONs.
- tr/tr_static_stubs.f90: NEW, same pattern for tr.
- eq/Makefile, tr/Makefile: add the `ifeq ($(strip $(GFLIBS)),)`
  gate (mirror tot/Makefile:64-70) that conditionally links
  EQ_STATIC_STUBS_OBJ / TR_STATIC_STUBS_OBJ into the standalone
  binary target. With GFLIBS populated (clavius / dev hosts), gate
  expands empty → no link impact. With GFLIBS empty (CI / no-graphics),
  links the stubs.

Layer B (CI):
- .github/workflows/regen-baselines.yml: NEW, ~210 lines.
  - workflow_dispatch trigger with `fixtures` input (default
    "eq_tst2 tr_tst2").
  - runs-on: ubuntu-24.04 (pinned, NOT ubuntu-latest), matching
    python-tests.yml's gfortran 13.2.0 environment.
  - concurrency block (mirrors python-tests.yml:15-17).
  - permissions: contents: read (least-privilege).
  - Per-module dump-path dispatch by fixture-name prefix
    (tr_* / eq_* / tot_* / fp_* / ti_* / wr_* / wrx_*).
  - Narrow failure detection: `test -s <dump>` guard distinguishes
    binary crash from expected baseline-mismatch.
  - Per-module shape check (jq): tr/eq require non-empty scalars;
    tot allows empty scalars (TR_PRESENT=0 valid per
    extract_tot_metrics.py:5-10).
  - Uploads regen-output/ as artifact (90-day retention).

Stub-duplication trade-off: 3 files (tot + eq + tr) now contain
the same ~378-line no-op stub body. Accepted per spec §3
non-goals — shared lib/ refactor is a follow-up. Stubs change
rarely (every ~6 months when a new graphics symbol appears).

Spec: docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md
(376 lines, 4 Codex review rounds converged).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Verify the commit**

```bash
git log --oneline -2
git show --stat HEAD | head -10
```

Expected: HEAD is the new commit, stat shows exactly 5 files (eq_static_stubs.f90 + tr_static_stubs.f90 NEW, eq/Makefile + tr/Makefile MODIFIED, regen-baselines.yml NEW). Plus the spec from before (6deddeb0) shows as the parent.

---

## Phase 4 — Pre-push gate + push + PR

### Task 8: Bounded local pytest matrix (sanity check)

**Files:** none

- [ ] **Step 1: Run the bounded pytest matrix**

```bash
pytest python/totlib/tests/ python/trlib/tests/ python/eqlib/tests/ test_run/scripts/tests/ \
  --forked --timeout=120 --timeout-method=signal 2>&1 | head -c 1048576 | tail -25
```

Expected: same baseline as PR #195 / #196 — 200+ PASS, ~90 SKIP, 2 pre-existing failures (`test_close_raises_exception_group_when_multiple_modules_fail` on Python 3.10, `test_fails_when_baseline_is_tiny_and_actual_is_zero` on develop). No NEW failures.

This PR does not change Python source or fixtures, so the pytest result MUST match develop baseline. If anything new fails, halt and investigate.

### Task 9: Parallel reviewers (in-house + Codex) on full diff

**Files:** none

- [ ] **Step 1: Confirm diff range**

```bash
git fetch origin
git log --oneline origin/develop..HEAD
```

Expected: 2 commits (spec at `6deddeb0` + impl C1).

- [ ] **Step 2: Fire BOTH agents in ONE message (parallel)**

In-house code-reviewer subagent type per CLAUDE.md is `feature-dev:code-reviewer`; fall back to `general-purpose` if unavailable. Codex is `codex:codex-rescue`. Both Agent calls in a SINGLE message.

Prompt template (use the same body, differ only on `subagent_type`):

> Review the diff `origin/develop..HEAD` (2 commits) on branch `feat/ci-regen-baselines-workflow` in the worktree `/Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-baseline-regen-workflow/`. Issue #197. The spec is at `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md`.
>
> Focus areas:
>
> 1. **Stub file fidelity**: do `eq/eq_static_stubs.f90` and `tr/tr_static_stubs.f90` have bodies byte-identical to `tot/tot_static_stubs.f90` from the first SUBROUTINE onward? Headers should differ per the spec §4.1.1-4.1.2 templates.
> 2. **Makefile gate correctness**: do `eq/Makefile` and `tr/Makefile` correctly invert the GFLIBS gate (empty → link stubs; non-empty → no stubs)? Spot-check the gate variable name doesn't collide with anything in the existing Makefile.
> 3. **Workflow YAML structural validity**: does `.github/workflows/regen-baselines.yml` parse as valid YAML? Are all referenced scripts (run_tests.sh, extract_<module>_metrics.py) actually present in the repo? Does the per-module dispatch case-statement cover all the prefixes the `fixtures` input could plausibly contain?
> 4. **Permission and concurrency consistency**: spec §4.2.1 specifies `permissions: contents: read` and a concurrency block; does the YAML match?
> 5. **Pre-existing failures**: this PR does NOT modify Python sources; `test_pipeline.py` and `test_compare_metrics.py` failures from develop are not introduced. Confirm via `git diff origin/develop --name-only`.
>
> Report HIGH / MED / LOW. Under 400 words.

- [ ] **Step 3: Triage findings**

Paste HIGH + MED back to the user. For each:
- HIGH: fix in a new commit on this branch before push; re-run Tasks 8 + 9.
- MED: discuss; fix or defer per user judgment.
- LOW: defer.

### Task 10: REVIEW_OK marker + push + PR

**Files:**
- Marker: `$(git rev-parse --git-common-dir)/REVIEW_OK_<HEAD-sha>` (touch-only)

- [ ] **Step 1: Write marker for current HEAD**

```bash
MARKER="$(git rev-parse --git-common-dir)/REVIEW_OK_$(git rev-parse HEAD)"
touch "$MARKER"
ls -la "$MARKER"
```

Expected: file exists, size 0.

- [ ] **Step 2: Push**

```bash
git push -u origin feat/ci-regen-baselines-workflow
```

Expected: `pre-push: review marker present — OK` and a new-branch line.

- [ ] **Step 3: Create PR**

```bash
env -u GITHUB_TOKEN gh pr create --base develop --head feat/ci-regen-baselines-workflow \
  --title "ci+eq+tr: workflow_dispatch baseline regen + graphics-stubs (#197)" \
  --body "$(cat <<'EOF'
## Summary

Closes #197 (CI baseline regen env mismatch — clavius gfortran 13.3 vs CI gfortran 13.2 produces ~3e-9 drift on `eq_tst2` / `tr_tst2` profile arrays). Unblocks #190 (`tr_tst2` baseline backfill).

Adds an in-CI baseline-regeneration workflow plus the Fortran graphics-stubs that let `eq.x` / `tr2` standalone binaries build in CI's gfortran-13.2 / Ubuntu-24.04 / no-graphics environment.

## Why this PR

PR #196 attempted to resolve #190 by regenerating baselines on clavius (gfortran 13.3) but CI rejected them at 1e-10 (gfortran 13.2 produces ~3e-9 different output on the iterative solver path). The diagnostic surfaced that baselines must be generated in the same environment they will be compared against. This PR is the environment-alignment infrastructure.

## Changes (5 files, 1 commit + spec)

| File | Type | Notes |
|------|------|-------|
| `eq/eq_static_stubs.f90` | NEW | Copy of `tot/tot_static_stubs.f90` (~378 lines, ~100 GSAF no-op SUBROUTINEs + 2 FUNCTIONs). Header adjusted. |
| `tr/tr_static_stubs.f90` | NEW | Same pattern for tr. |
| `eq/Makefile` | MODIFY | Add `EQ_STATIC_STUBS_OBJ` GFLIBS gate (mirror `tot/Makefile:64-70`) + include obj in `eq` target link line. |
| `tr/Makefile` | MODIFY | Same pattern for `tr2` target. |
| `.github/workflows/regen-baselines.yml` | NEW | workflow_dispatch trigger, `fixtures` input (default `"eq_tst2 tr_tst2"`), pinned to `ubuntu-24.04`, `permissions: contents: read`, concurrency block, per-module dump-path dispatch, narrow failure detection, per-module shape check, artifact upload (90-day retention). |

Plus the design spec at `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md` (376 lines, 4 Codex review rounds converged at `6deddeb0`).

## Verification

- [x] **mac local smoke**: `GFLIBS="" make -C eq eq` and `GFLIBS="" make -C tr tr2` — outcomes documented per Task 2/4 Step 4 (one of: (a) builds OK, (b) needs additional stubs, (c) macOS-specific issue separate from this change).
- [x] **YAML parse**: `python3 -c "import yaml; yaml.safe_load(...)"` succeeds.
- [x] **Pre-existing failure check**: `git diff origin/develop --name-only` includes none of `test_pipeline.py`, `test_compare_metrics.py` — Python 3.10 ExceptionGroup test + compare_metrics 1e-300 edge case are pre-existing and unaffected.
- [ ] **CI** (this PR run): python-tests.yml workflow continues to PASS — this PR does not modify it.
- [ ] **Workflow validation** (manual, post-merge or on this branch): trigger `regen-baselines.yml` from Actions UI with `fixtures="eq_tst2 tr_tst2"`. Should complete in ~10-15 min and produce a non-empty `baselines-<run-id>.zip` artifact.

## Stub-duplication trade-off

3 files (tot + eq + tr) now contain the same ~378-line no-op stub body. Accepted per spec §3 non-goals; future refactor to a single `lib/graphics_stubs.f90` is a follow-up issue. Stubs change rarely (every ~6 months when a new graphics symbol appears) and the existing per-module split (`*_graphics_stubs.f90` PIC variants) already follows the same per-module-isolation pattern.

## Follow-ups

After this PR merges:
1. Trigger the workflow with `fixtures="eq_tst2 tr_tst2"`.
2. Download artifact, extract `metrics.json` files.
3. Open a follow-up PR replacing `test_run/baselines/{eq_tst2,tr_tst2}/metrics.json` + removing the `@pytest.mark.xfail` decorator added in PR #195. This closes #190 cleanly.

## Review trail

- Brainstorming (2026-05-12): Route I + artifact upload (MVP) + configurable `fixtures` input.
- Spec `6deddeb0` (376 lines, 4 Codex rounds converged at R4 = NO MATERIAL FINDINGS).
- Per-commit pre-push gate: in-house + Codex parallel review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: returns PR URL.

- [ ] **Step 4: Wait for / trigger Bugbot**

Bugbot may auto-trigger on push, or may not (per PR #195/#196 experience). If after ~10 min no Bugbot review appears, comment `@cursor review` (per memory `feedback_cursor_review.md`):

```bash
env -u GITHUB_TOKEN gh issue comment <PR#> --body "@cursor review"
```

Wait for Bugbot completion (background poll script per PR #195's pattern is fine).

### Task 11: Trigger first workflow_dispatch run (post-merge or on-branch)

**Files:** none (workflow validation)

- [ ] **Step 1: Trigger the workflow from the new branch**

The workflow only triggers on `workflow_dispatch`, so it doesn't run automatically on push. Trigger it manually after this PR's CI is green:

```bash
env -u GITHUB_TOKEN gh workflow run regen-baselines.yml \
  --ref feat/ci-regen-baselines-workflow \
  -f fixtures="eq_tst2 tr_tst2"
```

Or via the GitHub Actions UI: Actions → regen-baselines → Run workflow → branch `feat/ci-regen-baselines-workflow` → fixtures `eq_tst2 tr_tst2` → Run.

- [ ] **Step 2: Wait for completion + inspect artifact**

```bash
sleep 60   # initial delay; workflow takes ~10-15 min
env -u GITHUB_TOKEN gh run list --workflow=regen-baselines.yml --limit 3 \
  --json databaseId,status,conclusion,headBranch --jq '.[] | "\(.databaseId) \(.status) \(.conclusion) \(.headBranch)"'
```

Repeat until `status=completed`. Then:

```bash
RUN_ID=<the_id_from_above>
env -u GITHUB_TOKEN gh run view "$RUN_ID" --log-failed 2>&1 | head -100   # if failed
env -u GITHUB_TOKEN gh run download "$RUN_ID" --name "baselines-$RUN_ID" --dir /tmp/regen-test
ls -la /tmp/regen-test/
```

Expected (success path):
- `regen-output/eq_tst2/metrics.json` (non-empty, contains profile array + scalars)
- `regen-output/tr_tst2/metrics.json` (non-empty, 14 scalars including AJRFT=0.0 — per the post-PR-#187 schema)

If failure:
- Build step failure → likely missing GSAF stub (add to the appropriate `*_static_stubs.f90`, push fix, re-trigger).
- Extract step failure → likely malformed dump (binary crashed; check the run_tests.sh output earlier in the log).

---

## Acceptance checklist (cross-reference to spec §7.3 / issue #197)

- [ ] `make -C eq eq` succeeds in CI's gfortran-13.2 / no-graphics env — verified by workflow's "Build standalone" step
- [ ] `make -C tr tr2` succeeds in same env — same step
- [ ] `workflow_dispatch` accepts `fixtures` input — verified by triggering with explicit input value
- [ ] Artifact contains valid metrics.json per fixture — verified by `jq` validation in workflow + Task 11 Step 2 download
- [ ] Resulting baselines pass `pytest` at 1e-10 — verified by **follow-up PR** that commits the downloaded metrics.json + removes the xfail decorator + runs python-tests.yml against the new baselines

---

## Self-review notes (this plan)

- **Spec coverage**: every spec §4 component maps to a task: §4.1.1 → Task 1, §4.1.2 → Task 3, §4.1.3 → Task 2, §4.1.4 → Task 4, §4.2.1 → Task 5. §7.1 local smoke → Task 2/4 Step 4. §7.2 CI verification → Task 11. §7.3 acceptance items → acceptance checklist above.
- **Placeholder scan**: each step has exact commands + expected output. No TBD/TODO. The "<PR#>" in Task 10 Step 4 and "<the_id_from_above>" in Task 11 Step 2 are runtime substitutions (the values don't exist at plan-write time), not stale placeholders.
- **Type/name consistency**: `EQ_STATIC_STUBS_OBJ`, `TR_STATIC_STUBS_OBJ`, `eq_static_stubs.o`, `tr_static_stubs.o`, branch `feat/ci-regen-baselines-workflow`, worktree `.claude/worktrees/ci-baseline-regen-workflow/`, fixtures input default `"eq_tst2 tr_tst2"` — consistent across all tasks.
