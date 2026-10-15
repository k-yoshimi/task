# Decision record — regenerate the `tot_ht6m_short` equivalence baseline for bpsi's merged EQ/TR solver refinements

- **Date:** 2026-06-29
- **Status:** ACCEPTED (physics reviewed and approved by the project owner)
- **Scope:** P0a merge of `bpsi/develop` into `kyoshimi-develop` (branch `integrate/base-2026-06`, task-merge PR #1)
- **Affects:** `test_run/baselines/tot_ht6m_short/metrics.json` (the 1e-10 binary-equivalence baseline for the TOT orchestrator HT6M short case)
- **Related:** [[task-merge-f90-project]] memory; wrx baseline regen `36586def`; the wrx gf-version baseline gap (regen-baselines does not yet support `wrx_*` — a follow-up to the #197 regen pattern; #197 itself was closed by `7a436d39`); design spec `docs/superpowers/specs/2026-06-15-task-merge-f90-design.md`

## 1. Context

The P0a merge brings the 23-commit `bpsi/develop` base onto the kyoshimi
Phase-L fork. After the static-build integration was fixed and CI first
reached pytest, the suite ran **733 passed / 3 failed** on the gfortran-13.2
Linux runner (run 28218102375). All 3 failures are 1e-10 binary-equivalence
baselines, in two unrelated classes:

| Test | Magnitude | Class |
|---|---|---|
| `totlib::test_tot_ht6m_short` | 210 leaves (all 50 rows), rel_err up to ~7.9e-4 | **physics change (this record)** |
| `wrxlib::test_demo` / `test_iter01` | pwr_tot rel_err ~4.9e-10 / 1.55e-9 | compiler-version FP noise (gf8.5 baseline ≠ gf13.2 CI) — separate, see #197 |

This record covers **only** the `tot_ht6m_short` failure. The wrx failures are
a distinct gf-version-sensitivity issue handled separately.

The merge did **not** touch `tot/` or `fp/` Fortran. `eq_iter01`, `tr_iter01`,
`tot_demo2014_short`, and `fp_iter01` all PASS on CI — so the change is not a
broad regression. Only the HT6M coupled run shifted.

## 2. Root cause

`tot_ht6m_short` is a menu-driven **coupled eq→tr run at `modelg=3`**
(`test_run/inputs/tot_ht6m_short.trparm: modelg=3`; the `.in` stdin script runs
`eq r s … tr r s …`, with `tot.HT6M_short.gs` as the GS prologue filename — not
a committed fixture). At `modelg=3` the equilibrium is loaded via `eq_load` /
`trmetric` — so this is NOT the `modelg=9` q-scaling branch.

The shift comes from the merge's bpsi **EQ/TR solver refinements** that the
modelg=3 `eq_load` path uses. Two base commits are responsible:

```
fa9dd493  "tr,eq: fix modelg=9 TR-EQ q-solver coupling" — despite the title, its
          body ALSO rewrites general solver code every modelg uses: EQLOOP
          under-relaxation + EQMAGS robustness + consistent current init
          (eq/eqcalc.f +22, eq/eqsub.f, eq/equnit.f; tr/trmetric.f90 +26,
          tr/trloop.f90, tr/trgrae.f90, tr/trbpsd.f90).
2b2b9408  "eq: eqcalq.f NMAX 200 -> 400" — a finer flux-surface grid for the EQ
          solve (grafted into the modernized eq/eqcalq.f90 in P0a, §3 of the
          merge conflict resolutions).
```

The pre-merge baseline (`8956d7a9`-era) encodes the coarser/older EQ solve; the
merged code solves the same HT6M equilibrium on a finer grid (NMAX 400) with
EQLOOP under-relaxation, yielding a slightly **more accurate**, globally
redistributed current/q profile (§3). demo2014 / iter01 are well-conditioned
configurations where these refinements are inert at 1e-10, which is why only
HT6M moved. The exact dominant sub-change
was not bisected (that needs per-commit rebuilds), but the physics signature in
§3 is unambiguous regardless of which refinement dominates.

## 3. Physics review (why this is a correct refinement, not a bug)

**CORRECTION (2026-06-29):** an earlier draft of this section called the shift
"core-localized (ρ ≤ 0.20), byte-identical beyond." That was wrong — an artifact
of a TRUNCATED CI log (`compare_metrics.py` prints only the first ~52 of 210
mismatched leaves, which happen to be the core rows). The full committed baseline
shows the shift is **global**. Two code reviewers caught the discrepancy; the
corrected signature below is from all 50 profile rows of the committed gf13.2
baseline vs the old baseline, and was re-approved by the owner.

| Quantity | rows changed | max rel_err | shape |
|---|---|---|---|
| AJ (current density j) | 50/50 | 7.91e-4 @ ρ=0.74 | redistribute: + core, − mid, + edge |
| QP (safety factor q)   | 50/50 | 1.33e-4 @ ρ=0.02 | − core, + outer (integral of j) |
| RT (temperature, ×2 spc) | 50/50 | ~1.4e-4 | mild redistribution |
| AJT (total current)    | scalar | 3.91e-5 | ≈ conserved |
| TAUE1/2, ALI, WPT, β*   | scalars | 6e-5 … 3.7e-4 | small, coherent |
| **RN (density n)**     | **0/50** | — | **frozen** |

Four bug-vs-physics discriminators, re-confirmed against the full committed data:

1. **Total current is conserved.** Integrated AJT moves only 3.91e-5 while local
   Δj/j reaches 7.91e-4 (≈20× larger). This is a current-profile REDISTRIBUTION —
   current shifts out of the mid-region (ρ≈0.5–0.85) toward the core and the edge —
   not a net current change. A bug has no reason to conserve the integral.
2. **Density n completely frozen** (0 of 50 rows). n is an input profile, not an
   equilibrium-solver output; an algorithm bug would tend to contaminate it.
3. **q tracks the redistributed current as its integral**: `q ∝ r·Bφ/(R·Bθ)`,
   `Bθ ∝ ∫₀ʳ j dr`. q falls where the cumulative interior current rises (core) and
   rises where it falls (outer); 39 of 50 rows have sign(Δj) = −sign(Δq), the
   remainder being the integral lag near the two sign-crossings. This is the
   correct physical coupling, not a per-point coincidence.
4. **Smooth, bounded, finite** — every change varies smoothly with ρ, bounded at
   ~8e-4, no NaN / no blow-up; downstream scalars (τE/Wp small, li small) are
   consistent with a slightly-redistributed current profile.

Visualization: `Δrel = (new−old)/old × 10⁻⁴` vs ρ across all 50 rows shows j
rising in the core, crossing zero at ρ≈0.43, dipping to −7.9e-4 at ρ=0.74, and
recovering at the edge; q falling in the core, crossing zero at ρ≈0.5, rising in
the outer half. (Corrected global plot rendered; owner re-approved 2026-06-29.)

## 4. Decision

**The new bpsi solver result is accepted as the correct reference for
`tot_ht6m_short`.** The project owner reviewed the per-quantity shift table and
the j/q radial-shift plot on 2026-06-29 and approved: the ~1e-4 change is the
intended physical consequence of bpsi's merged EQ/TR solver refinements (finer
flux-surface grid NMAX 200→400 + EQLOOP under-relaxation, `2b2b9408` /
`fa9dd493`) used by the modelg=3 `eq_load` path, not a merge artifact.

**Action:** regenerate `test_run/baselines/tot_ht6m_short/metrics.json` against
the merged code, on the CI compiler (gfortran-13.2 / x86_64), via the existing
`regen-baselines.yml` (`workflow_dispatch`, `fixtures: tot_ht6m_short`, which
supports the `tot_*` prefix and runs on ubuntu-24.04). Regenerating on gf13.2
(not Mac gf15 / ohtaka gf8.5) also avoids re-introducing the FP-version drift
that bites wrx — see §5.

This is a deliberate baseline change recorded here for audit; the regen commit
references this file. It does NOT loosen the 1e-10 tolerance — it updates the
reference to the physically-correct post-fix values.

## 5. Out of scope — the wrx failures (tracked separately)

`wrxlib::test_demo` / `test_iter01` fail by ~5e-10..1.5e-9 — **compiler-version**
FP reordering, not a physics change: the committed wrx baselines were generated
on gf8.5 (ohtaka, `36586def`) and the CI runs gf13.2; Mac gf15 gives yet a third
value, all within ~1e-9. The 1e-10 binary-equivalence tolerance is simply too
tight for the ray-tracing pwr integral across compiler *versions* (not just
arch). `regen-baselines.yml` does not yet support `wrx_*` (only tr_/eq_/tot_).
Resolution (a follow-up to the #197 regen pattern; #197 itself closed by
`7a436d39`): extend the regen workflow to `wrx_*` and capture the wrx baselines
on gf13.2, OR adopt a per-platform / slightly-looser tolerance for the FP-heavy
scalar. Lesson for the project: **equivalence baselines for the FP-version-
sensitive modules (wrx ray-trace, fp Fokker–Planck) must be captured on the exact
CI compiler.** (tot/eq/tr are compiler-stable at 1e-10 — the tot_ht6m regen here
is for the *physics* shift, not compiler drift, so it would reproduce on any
compiler; gf13.2 is used only to match CI exactly.)

## 6. Appendix — full-radius shift (gf13.2 CI, Δrel = (new−old)/old ×10⁻⁴)

ρ = NR/NRMAX, NRMAX = 50. **ALL 50 rows changed** (global redistribution); a
representative subsample:

| ρ | Δj ×10⁻⁴ | Δq ×10⁻⁴ | | ρ | Δj ×10⁻⁴ | Δq ×10⁻⁴ |
|---|---|---|---|---|---|---|
| 0.02 | +2.67 | −1.33 | | 0.56 | −2.09 | +0.25 |
| 0.10 | +2.43 | −1.22 | | 0.62 | −3.42 | +0.54 |
| 0.20 | +2.00 | −1.02 | | 0.68 | −5.30 | +0.83 |
| 0.30 | +1.42 | −0.77 | | 0.74 | **−7.91** (j min) | +1.10 |
| 0.40 | +0.46 | −0.45 | | 0.80 | −5.06 | **+1.21** (q max) |
| ~0.43 | ≈0 (j sign-cross) | −0.40 | | 0.86 | −0.79 | +1.15 |
| 0.50 | −1.00 | −0.03 | | 0.92 | +2.35 | +0.97 |
| ~0.50 | −1.00 | ≈0 (q sign-cross) | | 1.00 | +4.15 | +0.68 |

profile[0] (ρ=0.02) absolute: AJ 547623.91→547769.87, QP 6.478933→6.478072.
Total current AJT 0.021011987→0.021011165 (rel 3.91e-5, ≈conserved). RN frozen.

Source: baseline = old `test_run/baselines/tot_ht6m_short/metrics.json`; new =
the committed gf13.2 baseline captured from task-merge CI run 28327720495
(gfortran-13.2, ubuntu-24.04, nompi); cross-checked py3.11 == py3.13.
