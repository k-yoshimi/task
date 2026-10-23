# Decision record — regenerate the `wrx_demo`, `wrx_iter01`, `wrx_jt60` equivalence baselines for the rl-binning change of `wrx/wrcalpwr.f90`

- **Date:** 2026-10-21
- **Status:** PROPOSED. Quantified by K. Yoshimi on #226 (2026-10-13, comments "wrx gate: quantified shift and a baseline-layout problem" and its follow-up); measured again here. Physics sign-off by the module lead pending.
- **Scope:** upstream PR #226 (`merge/upstream-reconcile-2026-07`), after the merge of `develop` `ea9806ac`.
- **Affects:** `test_run/baselines/wrx_demo/metrics.json`, `wrx_iter01/metrics.json`, `wrx_jt60/metrics.json` (the 1e-10 equivalence baselines of `python/wrxlib/tests/test_equivalence.py`).
- **Adds to:** `2026-06-29-tot-ht6m-qsolver-baseline.md`, whose wrx failures were `pwr_tot` compiler drift and which could not see the array change described here.

## 1. Context

The bpsi base merged by #226 (`7999438d`, through the P0a merge `0254aa91`) changed the major-radius (rl) deposition
binning of `wrx/wrcalpwr.f90`:

```fortran
drl=(rlmax-rlmin)/nrlmax                     ! was (rlmax-rlmin)/(nrlmax-1)
pos_nrl(nrl)=rlmin+(dble(nrl)-0.5D0)*drl     ! was rlmin+(nrl-1)*drl
```

The rl bins are narrower (L/N instead of L/(N-1)) and their positions are cell centres. The same commit rewrote the
minor-radius (rs) deposition in absolute lengths (and the condition `rs1.LE.1.D0.OR.rs1.LE.1.D0` became
`...OR.rs2.LE.1.D0`); on these three cases the rs results do not change.

Until #249 the comparator compared only `scalars.pwr_tot` for wrx, so the change was invisible to the 1e-10 gate. The
June failures of `wrx_demo` / `wrx_iter01` (`pwr_tot` off by 4.9e-10 and 1.55e-9) were compiler drift between the
gfortran 8.5 values of `36586def` and the CI compiler, as the 2026-06-29 record says: on the CI compiler `pwr_tot`
before and after the bpsi change agree to about 6e-16. The baselines regenerated then (`36586def`, `d1f7f9e7`) already
held the new rl arrays, but no comparison looked at them. #249 (in `develop` since 2026-10-13) compares `arrays` /
`arrays2` element by element with shapes checked against the header, and makes `WrxState.to_dict()` emit the five
`*_nsa_nray` blocks species-major, `[NSAMAX_WR][NRAYMAX]`, as `wrx/wrxregress.f90` writes them. Against it, #226's
`wrx_demo` / `wrx_iter01` baselines (ray-major; the same values, transposed) fail the shape check and `wrx_jt60` (never
regenerated on #226) fails on values.

## 2. What changes, measured

`develop`'s baselines (before the change, species-major) against the new values, with `develop`'s comparator
(`test_run/scripts/compare_metrics.py`, tolerance 1e-10):

| quantity | `wrx_demo` | `wrx_iter01` | `wrx_jt60` |
|---|---|---|---|
| `scalars.pwr_tot`, `arrays.pwr_nsa`, `pwr_nray` | equal | equal | equal |
| `arrays.pos_nrs`, `arrays2.pwr_nrs_nsa`, `pwrmax_rs_nsa_nray`, `pos_pwrmax_rs_nsa_nray` | equal | equal | equal |
| `arrays.pos_nrl` | all 200 bins: from +drl/2 at the first to -drl/2 at the last (rel up to 6.8e-3) | all 200 (rel up to 2.4e-3) | all 200 (rel up to 2.1e-3) |
| `arrays2.pwr_nrl_nsa` | 145 of 400 bins differ, rel up to 0.24 | 99 of 400, rel up to 0.99 | 91 of 400, rel up to 0.65 |
| `pwrmax_rl_nsa_nray`, species 1 | 1.43148e-3 -> 1.42433e-3 (-0.50 %) | 0.114080 -> 0.113677 (-0.35 %) | 0.0800219 -> 0.0796514 (-0.46 %) |
| `pos_pwrmax_rl_nsa_nray`, species 1 | 0.308683 -> 0.309608 (+0.30 %) | 0.460679 -> 0.470440 (+2.1 %) | 0.478185 -> 0.482906 (+0.99 %) |
| rl peak vertex, species 1 (see below) | 0.403573 -> 0.405079 m (+1.5 mm) | 6.060257 -> 6.070672 m (+10.4 mm) | 3.353099 -> 3.358046 m (+4.9 mm) |

The bin holding the rl maximum is the same before and after (62, 94, 96). The peak value and position come from a
three-point parabolic fit around it (`wrx/wrcalpwr.f90`, `pwrmax_rl_nsa_nray` and `pos_pwrmax_rl_nsa_nray`), which
changes with the re-binned values and the new `drl`. Species 2 deposits no power in these cases; its
`pos_pwrmax_rl_nsa_nray` is `pos_nrl(1)` and moves by +drl/2.

`pos_pwrmax_rl_nsa_nray` is computed as `(locmax-0.5)/(nrlmax-1) - dpwr/ddpwr`: a bin index scaled to 0..1 plus the fit's
offset in metres, so it is not the major radius of the peak. Its first term is the same before and after (0.309045,
0.469849, 0.479899); the whole change is the offset (for `wrx_iter01` from -9.170 mm to +0.591 mm), which makes the
"~2e-2 deposition-peak shift" of the 2026-07-29 review. The vertex of the same fit at the major radius,
`pos_nrl(locmax) - dpwr/ddpwr`, moves by about half a new bin: +1.5, +10.4 and +4.9 mm (rel 3.7e-3, 1.7e-3, 1.5e-3).
The formula (the same on `develop`) is left to the module lead; this change does not touch it.

So the total absorbed power and every rs quantity are unchanged; the rl profile is re-binned (narrower, cell-centred
bins) and its fitted peak moves by about half a bin.

## 3. The new baselines

The three `metrics.json` are the values `python/wrxlib/tests/test_equivalence.py` captured on the CI runner
(`REGEN_OUTPUT_DIR`) in run 38690362398 of `python-tests.yml` (2026-10-15, `pull_request` on `d8b6e4de`, i.e. #226
merged with the `develop` of that day, which had #249): artifact `equivalence-actuals-3.11-38690362398`; the Python 3.13
artifact of the same run is byte-identical. Between that `develop` and `ea9806ac` nothing in `wrx/` or `python/wrxlib/`
changes the computed values (`develop` added only #261's layout query and ABI check there). The `*_nsa_nray` blocks are
species-major. The 1e-10 tolerance is unchanged.

## 4. Decision

Take the post-change values as the reference for the three cases, pending the module lead's physics sign-off on the rl
binning. If the lead prefers the old node-based binning, the change to revert is the two lines in §1, and the three
baselines are captured again from CI.
