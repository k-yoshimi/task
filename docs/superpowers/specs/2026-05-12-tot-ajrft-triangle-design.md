# TOT AJRFT Triangle Backfill — Design Spec

**Date**: 2026-05-12
**Branch**: `feat/tot-ajrft-triangle` (from `develop` at `f01386e0`)
**Issue**: #191 (`tot: backfill AJRFT in totregress + extract_tot_metrics.py + baselines (PR #187 follow-up)`)
**Author**: Kazuyoshi Yoshimi
**Status**: Approved scope; pending implementation plan

## 1. Goal

Expose the `AJRFT` (total RF + external-driven current, [MA]) scalar end-
to-end through the TOT orchestrator: the C ABI struct (`tot_state_c`),
the Python ctypes mirror (`TotStateC`), the Python state wrapper
(`SCALAR_FIELDS`), and the Phase-0 regression dump path (`totregress.f90`
→ `extract_tot_metrics.py` → baselines). After this work, the L-7b-i
`EXTERNAL_DRIVEN_I → tr → AJRFT` pipeline has regression coverage on
both the regress-dump path (Layer-1 baseline diff) and the totlib
pipeline path (`Tot.get_state().scalars["AJRFT"]`).

## 2. Motivation

PR #187 (`e049a1e4`, "L-7b-i EXTERNAL_DRIVEN_I scalar") added AJRFT to
the **TR** C ABI + Python wrapper + regress paths, but did **not** touch
the parallel TOT triangle. The TR-side regress mirror gap was closed in
`24b1b12f` and `d17f71ec` (2026-05-11). The TOT triangle gap remains:

- `tot/tot_state.f90:60-72` carries only the pre-AJRFT scalar set (13
  fields). The orchestrator struct is layout-compatible with `tr_state_c`
  at L-2 (per the file's own L-3+ TODO), but stopped tracking when
  `tr_state_c` gained a 14th scalar.
- `tot/tot_api.h:53-55` mirrors the same omission in the public C header.
- `tot/tot_api.f90:225-237` (init) and `:280-292` (copy-from-trstate)
  zero/propagate the 13 pre-AJRFT scalars but not AJRFT.
- `python/totlib/_ffi.py:81-93` ctypes `TotStateC._fields_` ends with
  `RQ1`; the AJRFT field that TR's `_ffi.py:119` carries is absent.
- `python/totlib/state.py:24-29` `SCALAR_FIELDS` omits `"AJRFT"`.
- `tot/totregress.f90:25-29,60-72` USE list and WRITE block omit AJRFT.
- `test_run/scripts/extract_tot_metrics.py:27-30` `SCALAR_KEYS` omits
  `"AJRFT"`.
- `test_run/baselines/tot_demo2014_short/metrics.json` and
  `test_run/baselines/tot_ht6m_short/metrics.json` have no AJRFT signal.
- `test_run/scripts/tests/fixtures/sample_tot_regress.dat` and
  `test_run/scripts/tests/test_extract_tot_metrics.py` lock the
  pre-AJRFT 13-scalar shape.

The functional impact, as documented in `feedback_tot_mirrors_tr.md`,
is that the totlib pipeline path that **physically writes AJRFT** via
`EXTERNAL_DRIVEN_I → tr` has **zero regression coverage** on AJRFT at
the TOT exit. Any regression that drifts AJRFT in the totlib pipeline
(e.g. a stale-state bug between `tr_get_state` calls) will pass tot
regression silently. This is the L-7b-i feature's whole point of
measurement.

This spec closes the gap by mirroring the **PR #187 TR-side pattern in
its entirety** onto the TOT triangle, plus the regress-mirror work that
`24b1b12f` + `d17f71ec` did for TR.

## 3. Non-goals

- Adding a dedicated `test_pipeline_equiv` assertion specifically on
  AJRFT propagation. The verify-only contract for issue acceptance #6
  is satisfied by `Tot.get_state().scalars["AJRFT"]` flowing through
  the metrics path once the triangle is closed; existing `compare_metrics.py`
  key-union semantics surface drift automatically. A dedicated AJRFT
  assertion can be filed as a follow-up if a non-baseline-driven check
  is desired.
- PNBTOT or any other TR scalar's TOT mirror. PNBTOT is a registry
  parameter, not a state-struct field, and lives on a different
  triangle (registry / namelist / Python wrapper). Out of class.
- Composing `tot_state_c` from nested per-module L-2 structs (per the
  `tot_state.f90:13-17` L-3+ TODO). AJRFT continues to live in the
  flat "integrated scalars" block alongside `WPT/AJT/Q0/...` for now;
  re-nesting is a refactor for the L-3 composition pass, not for #191.
- Changing the L-2 placeholder semantics in `tot_state.f90`
  (`USE tr_state` continues to be intentionally absent).
- ABI version bump beyond a single increment of `TOT_STATE_ABI_VERSION`.
  TR established the precedent with `TR_STATE_ABI_VERSION 2` (`tr_api.h:38`)
  when AJRFT was added; TOT follows the same `1 → 2` increment. No major
  restructure.

## 4. Scope (16 modification points + ABI bump + 3 commits)

The work is grouped into three commit-level concerns:

### 4.1 Group 1 — TOT C ABI + Python wrapper + docs parity (10 components)

Mirrors the AJRFT-injection block PR #187 (`e049a1e4`) applied to
TR. All six components are interdependent (a single missing one
re-creates the same invisibility class) and ship together.

#### 4.1.1 `tot/tot_state.f90` (component 1)

Append `REAL(C_DOUBLE) :: AJRFT` to the `tot_state_c` BIND(C) TYPE,
placed **after `QP(TOT_MAX_NRMAX)` (line 80, end of profile slots)**.
This matches TR-side end-of-struct placement (`tr_state.f90:66`) and
preserves byte offsets for the existing 13 scalars + 4 profile arrays.

Inline comment (mirroring TR `tr_state.f90:64-66`):

```
! L-7b-i: total RF + external driven current [MA]. Mirrors AJRFT in
! tr_state_c; appended at end-of-struct for ABI v2 compatibility.
REAL(C_DOUBLE) :: AJRFT
```

#### 4.1.2 `tot/tot_api.h` (component 2)

The header structure (lines 1-38) is: include guard (1-6), header
comment block `/* ... */` (8-32), grid-size defines (34-35:
`TOT_MAX_NRMAX`, `TOT_MAX_NSMAX`), then `enum tot_error { ... }`
(line 38+). The current scalar block is around line 54-55 inside
`struct tot_state_t`. Two edits:

1. **ABI version constant**. Insert a new comment block + `#define
   TOT_STATE_ABI_VERSION 2` **between line 35 (`#define
   TOT_MAX_NSMAX 8`) and the start of the `enum tot_error` block**
   (line ~37). Mirror TR `tr_api.h:27-38` exactly with `TOT_`
   substitution. The "v1 → v2" framing notes that v1 was implicit
   (pre-AJRFT, 13-scalar layout) and v2 appends AJRFT at
   end-of-struct. Sample content:

   ```c
   /*
    * tot_state_t ABI version. Bumped whenever a field is added/removed/
    * reordered in tot_state_t (i.e. whenever sizeof(tot_state_t) changes).
    * Out-of-tree binary consumers should compare TOT_STATE_ABI_VERSION at
    * compile time against any cached layout assumption and recompile when
    * it bumps.
    *
    * History:
    *   1 -> initial layout (Phase L-2)
    *   2 -> appended AJRFT [MA] (L-7b-i); existing field offsets preserved.
    */
   #define TOT_STATE_ABI_VERSION 2
   ```

2. **AJRFT field**. After the existing scalar block `double T, WPT,
   AJT, Q0, ..., RQ1;` (around line 54-55) and after the profile
   array members (RN/RT/AJ/QP), append a matching `double AJRFT;`
   field with comment `/* L-7b-i: matches tot_state.f90 end-of-struct
   placement; ABI v2. */`. Implementation note: open the file to
   the actual `struct tot_state_t { ... }` body during impl and
   place AJRFT as the last field before the closing `};` — line
   numbers shift once edit 1 is applied so don't depend on them.

#### 4.1.3 `tot/tot_api.f90` (component 3)

`tot_api_get_state` (line 210+) does **not** USE TRCOMM directly.
It declares `TYPE(tr_state_c) :: trstate` (line 214), calls
`tr_api_get_state(trstate)` (line 265), then field-copies trstate
into `state`. So all AJRFT plumbing goes through trstate, not TRCOMM.
PR #187 already updated `tr_api.f90:283,315` to populate
`trstate%AJRFT`, so on the TOT side we only need two new lines:

1. **Init block** (lines 217-241): after `state%RQ1 = 0.0_C_DOUBLE`
   (line 237), insert:

   ```
   state%AJRFT = 0.0_C_DOUBLE   ! L-7b-i
   ```

   (No semantic ordering constraint between scalars and the profile
   array zero-init that follows on lines 238-241, but grouping with
   the other scalars keeps the block readable.)

2. **Copy-from-trstate block** (lines 277-292): after
   `state%RQ1 = trstate%RQ1` (line 292), and before the DO loop
   that copies the profile arrays (line 293+), insert:

   ```
   state%AJRFT = trstate%AJRFT   ! L-7b-i: includes EXTERNAL_DRIVEN_I contribution
   ```

   Placement-wise this groups AJRFT with the other scalar copies even
   though the struct definition appends AJRFT at end-of-struct — the
   struct layout (where the memory sits) and the assignment order
   (when the code writes to it) are independent.

#### 4.1.4 `python/totlib/_ffi.py` (component 4)

In `TotStateC._fields_` (line 71-99): after `("QP", ctypes.c_double *
TOT_MAX_NRMAX),` (line 98), append:

```
# L-7b-i: total RF + external driven current [MA]. Mirrors AJRFT in
# tr_state_c; appended at end-of-struct for ABI v2 compatibility.
("AJRFT", ctypes.c_double),
```

Mirrors TR `_ffi.py:116-119` exactly.

#### 4.1.5 `python/totlib/state.py` (component 5)

In the `SCALAR_FIELDS` tuple (line 24-29): after `"ALI", "RQ1",` insert
on a new line:

```
"AJRFT",   # L-7b-i: includes EXTERNAL_DRIVEN_I contribution
```

Mirrors TR `state.py:27` exactly. Also update the module docstring
"scalars: dict of N scalar plasma quantities" to bump N from 13 → 14
(or to the equivalent phrasing TR's `state.py` already uses).

#### 4.1.6 `python/totlib/tests/test_ffi.py` (component 6)

Two edits, both mirroring TR `test_ffi.py` post-PR #187 (lines 60-85).

1. **`test_has_expected_fields` (line 74-84)**: append `"AJRFT",`
   at the **end of the expected-name tuple, after `"QP"`** (NOT in
   the scalar group between `"RQ1"` and `"RN"`). The assertion is
   order-insensitive, but locking the spec to ABI order (end-of-
   struct, matching `_fields_` and `tot_state_c`) prevents a future
   `sizeof`/offset coverage addition from disagreeing with this list.
   Mirrors TR `test_ffi.py:66`.

2. **New `test_size_matches_header_math`**: add a new test method
   to `TestTotStateCLayout` that asserts `ctypes.sizeof(TotStateC)`
   matches the explicit header arithmetic. Mirror TR
   `test_ffi.py:70-85` line-for-line with `TR_MAX_*` →
   `TOT_MAX_*`, `TrStateC` → `TotStateC`, and adjusted core math:

   - TOT struct adds **4 ints** of presence flags
     (`tr_present`/`ti_present`/`fp_present`/`wr_present`) on top
     of TR's `nt/nrmax/nsmax` ints — so TOT's core math is **7 ints
     + 14 doubles + 2*NR*NS doubles + 2*NR doubles**.
   - Accept either 28+exp_core or 32+exp_core for the int block to
     tolerate compiler padding from 28→32 bytes (mirroring TR's
     12→16 tolerance for its 3-int block).

   This is the canonical sizeof check that prevents a misplaced
   `AJRFT` field (e.g. inserted in the middle of the struct, breaking
   pre-AJRFT offsets) from passing the field-name-only test.

#### 4.1.7 User-facing scalar-count surfaces (components 6a-6d)

Four user-facing documents hard-code the "13 scalars" count and the
explicit scalar list, and become stale when `SCALAR_FIELDS` grows to
14. All four must be updated in the same commit that bumps the count
(C1):

- **Component 6a — `python/totlib/README.md` (line ~210)**: the table
  row `| 'scalars' | dict[str, float] | 13 integrated plasma scalars |`
  → bump count to 14 and (mirroring TR's README treatment) optionally
  note "+ AJRFT (L-7b-i)" in the description column.

- **Component 6b — `python/mcp-servers/tot_mcp/server.py` (line ~230)**:
  the schema description string
  `"13 integrated plasma scalars (T, WPT, AJT, Q0, BETA0, BETAP0,
  BETAA, BETAN, TAUE1, TAUE2, ZEFF0, ALI, RQ1)"` → bump to 14 and
  append `, AJRFT` to the parenthetical list.

- **Component 6c — `docs/sphinx/modules/tot/en/state.md` (line ~35)**:
  heading `## Scalars (13 entries, the state.scalars dict)` and the
  surrounding text that references the count → bump to 14. Add a
  row to the scalar table with key `AJRFT`, unit `MA`, meaning
  "total RF + external-driven current (L-7b-i)".

- **Component 6d — `docs/sphinx/modules/tot/ja/state.md` (line ~33)**:
  heading `## スカラー量 (13 個, state.scalars 辞書)` and surrounding
  text → 13 → 14, and add the AJRFT row in the bilingual counterpart
  of the scalar table.

These are documentation/UX gap; the C ABI works without them, but a
user reading the docs after C1 lands would see 13 in the docs and 14
in `Tot.get_state().scalars`. Including in C1 keeps the commit
self-consistent.

### 4.2 Group 2 — Regress dump + baselines (4 components)

Mirrors TR `24b1b12f`.

#### 4.2.1 `tot/totregress.f90` (component 7)

1. USE TRCOMM list (line 25-29): append `AJRFT,` to the second
   line (between AJT and Q0 of the WPT/AJT/.../BETAN row).
2. WRITE block (between line 62 `'AJT='` and line 63 `'Q0='`):
   insert `WRITE(UNIT_DUMP, '(A,1PE24.16)')  'AJRFT=',  AJRFT`.

Inside the `IF (TR_OK) THEN` guard (line 55-88), so the AJRFT line
is gated on TR's allocatable arrays being allocated, matching the
existing pre-AJRFT scalars' behavior. Under `TR_PRESENT=0`, no AJRFT
is written (consistent with the rest of the TR block being skipped).

#### 4.2.2 `test_run/scripts/extract_tot_metrics.py` (component 8)

Line 27-30 `SCALAR_KEYS` set: insert `"AJRFT"` after `"AJT"` (matches
TR `extract_tr_metrics.py:20`).

#### 4.2.3 `test_run/baselines/tot_demo2014_short/metrics.json` (component 9)

Regenerate on **clavius** (Linux, gfortran 13.3.0; see
`reference_clavius_baseline_regen.md`):

1. ssh to clavius, `cd ~/task && git fetch && git checkout feat/tot-ajrft-triangle`
2. Build tot2: `cd tot && make` (or `make tot2`, per repo Makefile;
   confirm via `tot/Makefile` target survey).
3. Run with dump enabled:
   `TOT_REGRESS_DUMP=1 ./tot2 < test_run/inputs/tot_demo2014_short.in`
4. `python3 test_run/scripts/extract_tot_metrics.py tot_regress.dat > new_metrics.json`
5. `mv new_metrics.json test_run/baselines/tot_demo2014_short/metrics.json`
6. scp back to mac, `git add` + commit.

The new baseline will have `"AJRFT": <value>` added to `scalars`.
For demo2014 with `EXTERNAL_DRIVEN_I=0` default, `AJRFT` reflects only
the existing PEC/PLH/PIC RF contributions and should be a small but
nonzero value (whatever the demo2014 input produces — confirm during
regen, do not predict).

#### 4.2.4 `test_run/baselines/tot_ht6m_short/metrics.json` (component 10)

Same procedure as 4.2.3 with `tot_ht6m_short.in`. Sister-baseline.

### 4.3 Group 3 — Extractor unit-test fixture (2 components)

Mirrors TR `d17f71ec`.

#### 4.3.1 `test_run/scripts/tests/fixtures/sample_tot_regress.dat` (component 11)

After the `AJT=1.5451000000000000E+01` line (line 8, currently between
`WPT=` on line 7 and `Q0=` on line 9), insert exactly:

```
AJRFT=0.0000000000000000E+00
```

Matching TR fixture's `0.0E+00` placeholder value (commit `d17f71ec`).
Profile rows and trailing module-presence flags stay unchanged.

#### 4.3.2 `test_run/scripts/tests/test_extract_tot_metrics.py` (component 12)

In the `test_extracts_tr_scalars` function (line 19-27), after the
existing assertions on `T`/`WPT`/`Q0`, add two lines mirroring TR's
`d17f71ec` test diff:

```python
assert "AJRFT" in data["scalars"]
assert data["scalars"]["AJRFT"] == 0.0
```

This locks the fixture against future "what does a real dump look
like" copy-paste recreating the same invisibility class.

## 5. Commit shape (3 commits)

Mirrors PR #187's TR-side three-layer commit structure:

| # | Subject | Components | TR-side mirror |
|---|---------|------------|----------------|
| C1 | `feat(tot): add AJRFT to tot_state ABI + Python wrapper (#191 / PR #187 follow-up)` | 1, 2, 3, 4, 5, 6, 6a-6d + `TOT_STATE_ABI_VERSION 2` bump | PR #187 ABI block |
| C2 | `test+tot: backfill AJRFT in regression dump (#191 / PR #187 follow-up)` | 7, 8, 9, 10 | TR `24b1b12f` |
| C3 | `test: backfill AJRFT in extractor unit-test fixture (#191)` | 11, 12 | TR `d17f71ec` |

**Dependency**: C1 ⊥ C2 (independent). C3 **depends on C2**: C3's
new assertion `assert "AJRFT" in data["scalars"]` only passes after
C2's component 8 has added `"AJRFT"` to `SCALAR_KEYS`, because the
extractor's parser silently skips keys not in the allowlist
(`extract_tot_metrics.py:79-80`). Order must therefore be C1 → C2 →
C3 (functional), which also happens to match PR #187's TR-side
review order. C2's baseline regen runs on clavius (Linux build of
tot2); C1 and C3 are mac-friendly.

## 6. Acceptance mapping (issue #191)

| Issue item | Components |
|------------|------------|
| 1. Add AJRFT to `tot/totregress.f90` USE + WRITE | #7 ✓ |
| 2. Add `"AJRFT"` to `extract_tot_metrics.py` SCALAR_KEYS | #8 ✓ |
| 3. Regenerate `tot_demo2014_short` + `tot_ht6m_short` baselines | #9, #10 ✓ |
| 4. Unit-test fixture coverage in `sample_tot_regress.dat` | #11 ✓ |
| 5. `./test_run/run_tests.sh tot_demo2014_short tot_ht6m_short` passes | C2 clavius verification ✓ |
| 6. Verify totlib pipeline equivalence covers AJRFT | **Verify-only** via existing `test_pipeline_equiv.py` after C1 (components 1-6 + 6a-6d) propagates AJRFT through `Tot.get_state()` ✓ |

The issue's acceptance #6 requires the full C1 set in addition to the
literal text of the issue body; this expansion is what Codex's design-
stage review surfaced (HIGH finding, 2026-05-12), with a further
spec-file review on 2026-05-12 adding the `test_size_matches_header_math`
sizeof guard and the four user-facing scalar-count surfaces (§4.1.7).

## 7. Test plan

### 7.1 Local (mac, after C1)

- `pytest python/totlib/tests/test_ffi.py -v -k Layout` — `TotStateC.AJRFT`
  layout assertion passes.
- `pytest python/totlib/tests/test_ffi.py -v` (whole file) — no regression
  in other layout / loader tests.
- `pytest python/totlib/tests/ -v --collect-only` — confirm no test file
  silently broke at collection time (catches import errors from
  state.py / _ffi.py changes).

### 7.2 Local (mac, after C3)

- `pytest test_run/scripts/tests/test_extract_tot_metrics.py -v` —
  fixture's new `AJRFT=0.0` extracts and asserts cleanly.

### 7.3 Clavius (after C2)

- Build libtotapi.so + tot2: `cd tot && make` (or per Makefile target).
- Generate fresh baselines (procedure in 4.2.3 / 4.2.4).
- `./test_run/run_tests.sh tot_demo2014_short tot_ht6m_short` —
  Layer-1 1e-10 equivalence PASS against the newly regenerated
  baselines.
- `pytest python/totlib/tests/test_pipeline_equiv.py -v` — pipeline-
  level equiv continues to pass (existing tests, verify no regression;
  no new AJRFT-specific assertion added per §3 non-goals).
- `pytest python/trlib/tests/test_equivalence.py -v` — TR-side
  `tr_iter01` baseline 1e-10 PASS (regression check against TR-side
  rebuild on the same clavius env).

### 7.4 CI (full PR)

`python-tests` workflow runs both python 3.11 and 3.13 matrices over
`pytest test_run/scripts/tests/`, `python/totlib/tests/`,
`python/trlib/tests/`. C3's fixture assertion plus C1's layout
assertion provide the long-lived automated regression once the PR
lands.

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `tot_state_c` byte-offset shift breaks an unforeseen consumer | Low | High | End-of-struct placement preserves all pre-AJRFT offsets; ABI version bump signals the change to any binary consumer at compile time |
| Baseline regen on clavius produces unexpected AJRFT magnitude (e.g. nonzero where expected zero) | Low | Med | demo2014/ht6m inputs use default `EXTERNAL_DRIVEN_I=0`, so AJRFT should reflect existing RF (PEC/PLH/PIC). Confirm value during regen; if anomalous, debug before commit (do not commit anomalous baseline) |
| ctypes layout mismatch between Fortran struct and Python `TotStateC` after edit | Low | High | Two complementary tests in §4.1.6: `test_has_expected_fields` locks the name set (in ABI order), and the **new** `test_size_matches_header_math` (mirroring TR `test_ffi.py:70-85`) asserts `ctypes.sizeof(TotStateC)` matches the explicit header arithmetic. The name-only test alone would not catch a misplaced field; the sizeof test does. Existing TR-side commits prove this combination survives the same edit class |
| `tot_api.f90`'s `trstate` fetch doesn't actually carry AJRFT (e.g. uses a stale getter) | Low | Med | PR #187 already updated `tr_api.f90:283,315` to populate AJRFT in the state struct that `trstate` reads from. Verify the trstate type during impl via a targeted grep |
| totlib `test_pipeline.py:298,420` mocks (`_make_state({"AJT": ...})`) drift | Low | Low | These mocks build partial state dicts; if `SCALAR_FIELDS` is loosely-checked downstream, the mocks may need an AJRFT key. Pre-flight grep during impl |
| Concurrent PR #178+ work on `python/totlib/` introduces a merge conflict on `_ffi.py` / `state.py` | Med | Low | Rebase on develop before push; conflict-resolution mechanical |

## 9. Out-of-scope tracked separately

If the verify-only path (§3) proves insufficient over time (e.g. a
regression surfaces that the metrics-path key-union doesn't catch), a
follow-up issue should add an AJRFT-specific assertion to
`test_pipeline_equiv.py` (e.g. inject `EXTERNAL_DRIVEN_I=1.0` via
`Tot.set_param`, run the pipeline, assert
`Tot.get_state().scalars["AJRFT"] ≈ 1.0` at 1e-10). Filed as a
hypothetical follow-up after this PR lands if needed.

## 10. References

### 10.1 Related commits

- `e049a1e4` PR #187 — `tr+totlib: physical EXTERNAL_DRIVEN_I scalar
  (L-7b-i)`. The TR-side reference for the ABI/wrapper triangle.
- `24b1b12f` (2026-05-11) — `test+tr: backfill AJRFT in regression
  dump (PR #187 follow-up)`. TR-side regress mirror.
- `d17f71ec` (2026-05-11) — `test: backfill AJRFT in extractor
  unit-test fixture (PR #187 follow-up)`. TR-side fixture/unit-test.

### 10.2 Issues

- #191 — driving issue
- #187 — originating PR (TR-side AJRFT addition)
- (No new follow-up filed; verify-only contract per §3)

### 10.3 Memory files

- `feedback_scalar_field_triangle.md` — TR scalar = C ABI + Python
  wrapper + regress/extractor triangle (this design extends the
  pattern to TOT)
- `feedback_tot_mirrors_tr.md` — "TR scalar additions need paired
  TOT update" — driving feedback for this work
- `feedback_codex_worktree_sharing.md` — Worktree isolation discipline
- `reference_clavius_baseline_regen.md` — baseline regen procedure
- `feedback_equivalence_must_pass.md` — SKIP ≠ verification

### 10.4 Reviewer trail

- **Design-stage Codex review #1** (2026-05-12, brainstorming
  output): HIGH finding "TOT triangle expansion needed beyond
  regress paths" → incorporated as §4.1 (Group 1).
- **Self-review** (1df54938): scope/consistency/ambiguity scan,
  fixed §4.1.3 (no TRCOMM USE) and §5 (commit ordering rationale).
- **Spec-file Codex review #2** (2026-05-12, written spec): HIGH
  (§4.1.2 tot_api.h placement) + MED (§4.3.1 line off-by-one,
  test_ffi sizeof guard missing, four user-facing docs surfaces
  missing, §5 commit-dependency claim wrong) + LOW (§4.1.6
  field-order ambiguity). All incorporated in this revision.
- Implementation-time pre-push gate: in-house code-reviewer + Codex
  rescue (parallel) on each commit's diff per CLAUDE.md.
