# CI Baseline Regen Workflow — Design Spec

**Date**: 2026-05-12
**Branch**: `feat/ci-regen-baselines-workflow` (from `develop` at `2220468d`)
**Issue**: #197 (CI baseline regen env mismatch — clavius gfortran 13.3 vs CI gfortran 13.2 produces ~3e-9 drift)
**Author**: Kazuyoshi Yoshimi
**Status**: Approved scope; pending implementation plan

## 1. Goal

Provide a CI-environment-aligned mechanism to regenerate `test_run/baselines/<fixture>/metrics.json` files. Solves the compiler-version drift that blocks #190 (and prevents removing the `xfail` decorator added in PR #195) by ensuring baselines come from the same environment that pytest CI consumes them in.

## 2. Motivation

PR #196 attempted to resolve #190 (`tr_tst2` baseline backfill for AJRFT) by regenerating baselines on **clavius (Ubuntu 24.04, gfortran 13.3.0)**. CI rejected them: `eq_tst2` profile values drift ~3e-9 between gfortran 13.2 (CI default on Ubuntu 24.04) and gfortran 13.3 (clavius). Drift exceeds the 1e-10 Layer-1 tolerance.

Investigation confirmed:
- CI standalone `eq.x` output exactly matches the OLD baseline (rel_err = 0 vs OLD).
- Clavius output is ~3e-9 different.
- Drift is **compiler-version-induced**, not the `a98d66ec` zero-init correctness fix (originally hypothesized).

The actionable conclusion: baselines must be generated in the same environment they will be compared against — i.e., CI's Ubuntu 24.04 + gfortran 13.2. Manual clavius regen is broken for `iterative-solver-heavy` fixtures (`eq_tst2`, `tr_tst2`).

Today, CI **builds** the libraries and binaries needed for `pytest` (lib\*api.so PIC chain + graphics-stubbed `tot/tot`) but does NOT build the standalone `eq.x` or `tr/tr2` binaries the canonical baseline-regen flow (`./test_run/run_tests.sh`) requires. Two parallel additions are needed: Fortran (enable graphics-free builds for `eq` + `tr` standalone binaries) and CI (a workflow that uses them).

## 3. Non-goals

- Auto-PR / auto-commit of regenerated baselines from the workflow (user manually commits artifacts). Layered improvement, separate scope.
- Periodic schedule (nightly drift detection). Out of scope — workflow_dispatch is on-demand only.
- Refactoring graphics stubs into a shared `lib/`-level file (DRY). Three files duplicate the same ~378-line stub set; refactor is a follow-up.
- Resolving the underlying gfortran 13.2 vs 13.3 drift root cause (compiler-level investigation). Out of scope — accept the drift, generate per-environment.
- Supporting in-PR baseline regen via comment-driven trigger (e.g. `/regen-baselines`). Future enhancement.

## 4. Scope (6 files, 1 commit)

### 4.1 Layer A — Fortran static stubs for eq + tr (4 files)

Mirrors the existing `tot/tot_static_stubs.f90` pattern (378 lines, ~100 GSAF graphics-symbol no-op stubs) that lets `tot/Makefile` build `tot/tot` standalone without graphics libs when `GFLIBS` is empty.

#### 4.1.1 `eq/eq_static_stubs.f90` (NEW)

Copy of `tot/tot_static_stubs.f90` with comment header rewritten:
- Title: `! eq_static_stubs.f90`
- Background: "Graphics-symbol stubs for the standalone-link `eq` Fortran binary path. eq/Makefile's `eq` target links the full TASK archive chain (libgrf.a + libeq.a + libpl.a + ...), which transitively references ~100 GSAF graphics primitives ..."
- Same body: ~100 stub SUBROUTINEs + 2 stub FUNCTIONs (same as tot).

The stub bodies themselves are identical to `tot_static_stubs.f90` — all are no-ops. We accept the DRY violation (3 near-identical files: `tot_static_stubs.f90`, `eq_static_stubs.f90`, `tr_static_stubs.f90`) because:
- Stubs change rarely (every ~6 months when a new graphics symbol appears).
- A shared `lib/`-level file would create cross-module entanglement that the existing per-module split (`*_graphics_stubs.f90` PIC variants in each module) deliberately avoids.
- Future refactor is a follow-up; not blocking #197.

#### 4.1.2 `tr/tr_static_stubs.f90` (NEW)

Same as 4.1.1 but for `tr`. Comment header references `tr/Makefile`'s `tr2` target and the libtr2.a / libeq.a / libpl.a / ... archive chain.

#### 4.1.3 `eq/Makefile` (MODIFY)

Add the GFLIBS gate block (mirroring `tot/Makefile:64-70`) before the `eq` target. Approximately:

```makefile
ifeq ($(strip $(GFLIBS)),)
EQ_STATIC_STUBS_OBJ = eq_static_stubs.o
else
EQ_STATIC_STUBS_OBJ =
endif
```

Then update the `eq` target line to include `$(EQ_STATIC_STUBS_OBJ)` in dependencies and link line:

```makefile
eq: libs libeq.a eqmain.o $(EQ_STATIC_STUBS_OBJ)
	$(FLINKER) eqmain.o $(EQ_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

(Current line per `eq/Makefile:116-117`.)

`eq_static_stubs.o` compile rule follows the existing convention for `.f90` files in `eq/Makefile` (no special rule needed, falls through to the default `.f90.o` rule).

#### 4.1.4 `tr/Makefile` (MODIFY)

Same pattern for `tr2` target (currently at `tr/Makefile:132`):

```makefile
ifeq ($(strip $(GFLIBS)),)
TR_STATIC_STUBS_OBJ = tr_static_stubs.o
else
TR_STATIC_STUBS_OBJ =
endif

tr2: $(LIBS2) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ)
	$(FLINKER) $(OBJDIR)/trmain.o $(TR_STATIC_STUBS_OBJ) $(LIBS2) -o $@ $(FFLAGS) $(FLIBS) $(LIBX_MTX)
```

### 4.2 Layer B — GitHub Actions workflow (1 file)

#### 4.2.1 `.github/workflows/regen-baselines.yml` (NEW)

Triggered manually via `workflow_dispatch`. Reuses the build-environment setup steps from `.github/workflows/python-tests.yml:50-240` (apt install, BPSD clone, make.header provisioning, PIC lib chain), adds eq + tr standalone binary builds, runs the canonical regen flow, uploads metrics.json files as artifact.

**Trigger**:

```yaml
on:
  workflow_dispatch:
    inputs:
      fixtures:
        description: 'Space-separated fixture names (default: eq_tst2 tr_tst2)'
        default: 'eq_tst2 tr_tst2'
        required: false
```

**Concurrency** (Codex round 2 MED): mirror `python-tests.yml:15-17`
so stacked manual triggers don't pile up competing artifacts:

```yaml
concurrency:
  group: regen-baselines-${{ github.ref }}
  cancel-in-progress: true
```

A new manual trigger on the same branch cancels any in-flight run.
For workflow_dispatch this is the desired behaviour (the user re-ran
because they want fresh output).

**Permissions** (Codex round 2 LOW — least-privilege): the workflow
only checks out source and uploads artifacts; it does NOT write to
the repo, comment on PRs, or push commits. Restrict accordingly:

```yaml
permissions:
  contents: read
```

If auto-commit / auto-PR is added in a future iteration, expand
to `contents: write` + `pull-requests: write` at that time.

**Cache strategy** (Codex round 2 LOW): no `actions/cache` configured
for this initial iteration. Rationale: on-demand regen is infrequent
(once per baseline-drift incident, expected monthly at most), and a
full clean build is ~5 minutes — caching saves marginal time at the
cost of cache-invalidation complexity (BPSD develop branch updates,
makefile changes). If usage cadence increases, add `actions/cache@v4`
keyed on `hashFiles('eq/Makefile', 'tr/Makefile', '../bpsd/HEAD')` in
a follow-up.

**Job structure** (mirror python-tests.yml's pytest job):

- runs-on: **`ubuntu-24.04` (pinned)** — explicit pin matches the
  python-tests.yml build comments documenting gfortran 13.2.0 on Ubuntu
  24.04. `ubuntu-latest` shifts on GitHub image rotation and the
  baseline reproducibility this workflow exists for depends on a stable
  compiler. Codex spec review #1 flagged this as HIGH.
- timeout-minutes: 20

**Steps**:

1. Checkout (`actions/checkout@v4`).
2. Set up Python 3.11 (or 3.13 — pick 3.11 to match the older matrix used by python-tests.yml).
3. Install Fortran/C build deps — same `apt install gfortran gcc make valgrind` block as python-tests.yml:50-78.
4. Clone BPSD (k-yoshimi/bpsd@develop, same as python-tests.yml:80-105).
5. Provision `mtxp/make.mtxp` from nompi template (mirror python-tests.yml step).
6. Provision `make.header` for Linux gfortran (no graphics) — same.
7. Install Python test dependencies (`pip install pytest pytest-forked pytest-timeout` etc., to support the run_tests.sh fallback to extract_*_metrics.py).
8. Build the dependency chain (lib/, mtxp/, bpsd/, pl/, eq/, fp/, ti/, wr/, wrx/) — same shape as python-tests.yml:160-180 but extending to the eq + tr non-PIC archives needed by `eq.x` and `tr2` (in addition to the `_pic.a` variants already there).
9. Build `eq/eq` standalone binary: `make -C eq eq` (with `GFLIBS` empty → links eq_static_stubs.o automatically per Layer A).
10. Build `tr/tr2` standalone binary: `make -C tr tr2` (same gate).
11. Build `tot/tot` standalone binary: `make -C tot tot` (same as python-tests.yml:263).
12. **Rely on `run_tests.sh`'s built-in dependency-copy** (Codex LOW): for `tr_tst2 → eq_tst2` and similar dep chains, `test_run/run_tests.sh:361-375` already copies `eqdata.*` / `*.gs` from `test_output/<dep>/` to `test_output/<test>/`. No separate staging step needed — when a fixture lists a dep in `test_definitions.conf`, run_tests.sh runs the dep first and propagates outputs. For fixtures that have NO dep but read eqdata (none in current scope), defer to a future iteration.
13. For each fixture in `${{ inputs.fixtures }}`:
    - `./test_run/run_tests.sh <fixture> || true` — but **do NOT
      rely on the suppressed exit code as a success signal**. The
      `|| true` only exists to absorb the expected
      "comparison failed" exit (run_tests.sh:535-538 exits 1 on
      regression failure); a real binary crash or missing input
      would also be swallowed if we relied on that alone.
    - **Narrow failure detection** (Codex MED): immediately after the
      run, check `test -s test_run/test_output/<fixture>/<module>_regress.dat`
      — fail the step if the dump file is empty or missing. This
      catches binary crashes, missing inputs, etc. without
      conflating them with the expected stale-baseline-comparison
      failure.
    - Determine module prefix (`tr_*` → `tr`, `eq_*` → `eq`, `tot_*` → `tot`, etc.).
    - `python3 test_run/scripts/extract_<module>_metrics.py test_run/test_output/<fixture>/<module>_regress.dat > regen-output/<fixture>/metrics.json`.
      The extract scripts (`extract_eq_metrics.py:75-84`,
      `extract_tr_metrics.py:69-78`) **`raise SystemExit`** on
      malformed dumps (missing dimension keys, mismatched profile
      row count, empty scalars), so this step naturally fails the
      workflow if the dump is invalid. Codex MED on pre-upload
      validation is therefore largely covered by existing extractor
      logic.
    - Defense-in-depth shape check (Codex MED 2 nuance): use a
      **per-module shape check** rather than a blanket non-empty
      scalars check. For `tr_*` and `eq_*` fixtures, scalars MUST be
      non-empty (the canonical schema requires populated state).
      For `tot_*` fixtures, `extract_tot_metrics.py` documents
      `scalars: {}` as VALID when `TR_PRESENT=0` (per its header
      docstring lines 5-10), so the check is instead
      `jq -e '.NT >= 0 and .NRMAX >= 0 and .NSMAX >= 0' regen-output/<fixture>/metrics.json`
      — confirming the dimension keys are present.
      Module dispatch by fixture-name prefix mirrors §4.2.1 step 13's
      module-prefix logic for picking the extract script.
14. Upload `regen-output/` as artifact via `actions/upload-artifact@v4`:
    - name: `baselines-${{ github.run_id }}`
    - path: `regen-output/`
    - retention-days: **90** (GH Actions default) — Codex spec review
      #1 flagged the original "30" as too short for manual
      review-and-commit cadence. 90 days gives the user time to
      verify, commit, and run validation CI before the artifact
      expires. Can be reduced later if storage becomes a concern.

Approximate workflow length: ~180-220 lines.

### 4.3 Layer C — Documentation (this spec)

#### 4.3.1 `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md` (this file)

Committed as part of the same PR.

## 5. Commit shape (1 commit)

| File | Type |
|------|------|
| `eq/eq_static_stubs.f90` | NEW (~378 lines, copy of tot_static_stubs.f90) |
| `tr/tr_static_stubs.f90` | NEW (~378 lines, copy of tot_static_stubs.f90) |
| `eq/Makefile` | MODIFY (+~7 lines) |
| `tr/Makefile` | MODIFY (+~7 lines) |
| `.github/workflows/regen-baselines.yml` | NEW (~200 lines) |
| `docs/superpowers/specs/2026-05-12-ci-baseline-regen-workflow-design.md` | NEW (this spec) |

Subject: `ci+eq+tr: workflow_dispatch baseline regen + graphics-stubs for eq.x / tr2 (#197)`

## 6. Data flow

```
User triggers workflow_dispatch on GH Actions UI
  inputs.fixtures = "eq_tst2 tr_tst2"
  ↓
runs-on ubuntu-24.04 (pinned, gfortran 13.2)
  ↓
checkout + apt deps + BPSD clone + make.header (mirrors python-tests.yml)
  ↓
build lib*_pic.a + lib*api.so chain (same as python-tests.yml)
  ↓
build eq/eq (with eq_static_stubs.o linked, via Layer A)
build tr/tr2 (with tr_static_stubs.o linked, via Layer A)
build tot/tot (existing, with tot_static_stubs.o)
  ↓
(dep eqdata propagation handled by run_tests.sh dependency-copy)
  ↓
for fixture in inputs.fixtures:
    ./test_run/run_tests.sh <fixture>  # runs eq.x or tr2 standalone
    extract_<module>_metrics.py  → regen-output/<fixture>/metrics.json
  ↓
upload-artifact: name=baselines-${run_id}, path=regen-output/
  ↓
User downloads artifact zip from Actions UI
  ↓
User extracts + commits to feature branch  → opens PR
  ↓
python-tests CI runs against new baselines  → PASS at 1e-10
  ↓
#190 (and any other compiler-drift baseline issue) is closeable
```

## 7. Testing

### 7.1 Layer A local verification (mac)

After Makefile changes, smoke-test BOTH eq and tr stubs:

```bash
cd /Users/k-yoshimi/Dropbox/cursor/task/.claude/worktrees/ci-baseline-regen-workflow

# eq: confirm GFLIBS gate works.
make -C eq clean
GFLIBS="" make -C eq eq 2>&1 | tail -10
ls -l eq/eq

# tr: same check on tr2 (Codex LOW: don't skip the larger of the two new files).
make -C tr clean
GFLIBS="" make -C tr tr2 2>&1 | tail -10
ls -l tr/tr2
```

Expected: builds proceed without graphics-lib errors; `eq/eq` and `tr/tr2` binaries appear.

Note: macOS may have its own link issues for `eq.x` / `tr2` (LIBX11 etc.) even after stubs. That's a separate macOS issue, not a Layer A problem. CI verification is the authoritative test. If mac fails for X11/etc., document the actual failure and rely on CI.

### 7.2 Layer B verification (CI)

The workflow itself is the test. Procedure:
1. Push the branch with the changes.
2. Open a draft PR.
3. Manually trigger `regen-baselines.yml` from the Actions UI with `fixtures="eq_tst2 tr_tst2"`.
4. Wait for completion (~10 min).
5. Download artifact, inspect `regen-output/eq_tst2/metrics.json` and `tr_tst2/metrics.json` — both should be non-empty with correct schema.
6. Replace `test_run/baselines/eq_tst2/metrics.json` and `tr_tst2/metrics.json` with downloaded versions; remove the `xfail` decorator from PR #195's prior addition.
7. Push the baseline update commit on the same branch.
8. python-tests CI on the new push → `test_eq_tst2`, `test_tr_tst2`, and `test_tst2` all PASS at 1e-10.

Step 6-8 close #190 in a follow-up commit on the same PR; the spec just delivers the workflow infrastructure.

### 7.3 Acceptance

| Acceptance item | Verification |
|------------------|--------------|
| `make -C eq eq` succeeds in CI's gfortran-13.2 / no-graphics env | Workflow step builds successfully; eq/eq binary appears |
| `make -C tr tr2` succeeds in same env | Workflow step builds successfully; tr/tr2 binary appears |
| `workflow_dispatch` accepts `fixtures` input | Run with `fixtures="eq_tst2 tr_tst2"` succeeds |
| Artifact contains valid metrics.json per fixture | `jq` validation in workflow + manual inspection |
| Resulting baselines pass `pytest` at 1e-10 | Follow-up validation by committing to a PR and running python-tests CI |

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `eq_static_stubs.f90` doesn't cover an unresolved GSAF symbol that `eq.x` needs | Med | Med | Compare unresolved symbols at first CI workflow run; add missing stubs to the file. tot's stub set covers ~100 symbols — most cross-module overlap is expected, but eq may need a small delta |
| `tr_static_stubs.f90` same issue | Med | Med | Same mitigation |
| `run_tests.sh <fixture>` exits non-zero (compare-step fails on stale baseline) and aborts step | High | Low | Use `\|\| true` on the `run_tests.sh` step; the dump file is the artifact, not the exit code |
| 3 files duplicate 378 lines of stubs (DRY violation) | High | Low | Accepted; stubs change rarely. Refactor to `lib/` is a follow-up |
| GH Actions artifact retention is 90 days (we use the default) | Low | Low | If 90 days proves too short, make retention a `workflow_dispatch` input. If too long for storage cost, drop to 60 |
| `ubuntu-24.04` pin reaches GitHub's runner deprecation milestone (typical lifecycle ~3-4 years; Canonical LTS support to 2029) | Low | Low | When GH announces deprecation, re-pin to the next LTS (`ubuntu-26.04` or successor) and regenerate baselines once. Same baseline-realignment workflow applies — this workflow IS the regen mechanism |
| Shell behaviour differs across GH runner default vs explicit `bash -lc` | Low | Low | All multi-line `run:` blocks should be explicit `shell: bash` (or rely on GH's documented default `bash -e -o pipefail` on Linux). Note in §4.2.1 |
| Workflow accidentally triggered on push by misconfig | Low | Low | Restrict `on:` to `workflow_dispatch` only (no `push:` block) |

## 9. References

### 9.1 Issues + PRs

- **#197** — driving issue
- **#190** — the immediate beneficiary (tr_tst2 baseline backfill blocked by env mismatch)
- **#192** — silent-SKIP closure (PR #195) added xfail that this workflow unblocks
- **PR #196** — closed without merging; established the diagnostic that led to #197

### 9.2 Code references

- `tot/tot_static_stubs.f90` — the precedent being mirrored (~378 lines, ~100 stubs)
- `tot/Makefile:64-70` — the GFLIBS gate pattern
- `tot/Makefile:178-184` — the `tot` target with stubs link
- `eq/Makefile:116-117` — current `eq` target (to be modified)
- `tr/Makefile:132` — current `tr2` target (to be modified)
- `.github/workflows/python-tests.yml:50-240` — the build setup steps the new workflow will reuse
- `.github/workflows/python-tests.yml:239-285` — the existing "Generate Layer 1 eqdata baselines" step (precedent for staging + binary invocation in CI)
- `test_run/run_tests.sh` — canonical fixture runner (driven by `test_run/test_definitions.conf`)
- `test_run/scripts/extract_<module>_metrics.py` — per-module dump-to-JSON converters
- `test_run/scripts/check_regression.sh` — has a `--generate-baseline` flag that could be invoked alternatively (cf. §4.2.1 step 13)

### 9.3 Memory files

- `reference_clavius_baseline_regen.md` — updated 2026-05-12 to flag tst2 as exception
- `feedback_equivalence_must_pass.md` — "SKIP is invisibility" — same doctrine this workflow continues to serve

### 9.4 Reviewer trail

- **Brainstorming (2026-05-12)**: scope = Route I (Fortran stubs + standalone binary), output = artifact upload (MVP), workflow scope = configurable fixtures input with `eq_tst2 tr_tst2` default.
- **Codex spec review #1 (2026-05-12)**: HIGH (pin `ubuntu-24.04`, not `ubuntu-latest`) + MED 4 (stub duplication acknowledged-but-accepted, `|| true` exit-code masking, 30-day retention too short, pre-upload validation gap) + LOW 2 (§7.1 missing tr2 smoke, redundant eqdata staging vs run_tests.sh built-in dep copy). All but the "stub duplication" finding incorporated; that one is explicitly accepted as a YAGNI trade-off.
- **Codex spec review #2 (2026-05-12, post-round-1)**: MED 3 + LOW 2.
  - MED: round-1's `jq -e '.scalars | length > 0'` rejects valid TOT outputs where `TR_PRESENT=0` (per `extract_tot_metrics.py:5-10`). Fixed with per-module shape check: tr/eq require non-empty scalars; tot uses dimension-keys check instead.
  - MED: §6 data-flow diagram had stale `ubuntu-latest` and "stage shared eqdata fixtures" wording from before the round-1 fixes. Updated to match §4.2.1.
  - MED: missing `concurrency:` block — added (mirrors python-tests.yml:15-17).
  - LOW: missing `permissions: contents: read` least-privilege — added.
  - LOW: cache strategy unspecified — explicit "no cache, rationale documented" added.
- **Codex spec review #3 (2026-05-12, post-round-2)**:
  - 2 MED reported as **false positives** after re-verification:
    - "Stale `ubuntu-latest` at lines 148-152": the reference is the
      *explanation* for why we pin `ubuntu-24.04`, not a stale
      `runs-on` declaration. The actual `runs-on` is correctly pinned.
    - "Dump-path dispatch breaks for `eqdata.demo2014`": confirmed
      against `check_regression.sh` — `tot_*` fixtures dump to
      `tot_regress.dat` (consistent per-module), and `eqdata.demo2014`
      is a separate eq-output file, not the regress dump. The spec's
      `<module>_regress.dat` pattern is correct.
  - 3 LOW incorporated: §8 risk row retention "30 days is enough"
    fixed to reflect the 90-day decision; Ubuntu 24.04 EOL
    acknowledgment row added; shell-locking note added.
- Implementation-time pre-push gate: in-house code-reviewer + Codex rescue (parallel) on each commit's diff per CLAUDE.md.
