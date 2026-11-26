# Equivalence baseline policy

This document defines what the `python/<mod>/tests/test_equivalence.py`
suites assert, why they only run on Linux, and how a contributor
promotes a new platform to canonical when the project's needs change.

Tracking issue: [#213](https://github.com/k-yoshimi/task/issues/213).
Design rationale: `docs/superpowers/specs/2026-05-26-linux-canonical-equiv-policy-design.md`.

## What the 1e-10 contract asserts

For each of 20 cases under `test_run/baselines/<case>/metrics.json`,
the test loads `lib<mod>api.so` (via Python wrapper), replays the
fixture parameters, advances the simulation, serializes the resulting
state, and compares against the committed JSON at relative tolerance
`1e-10`.

The contract is: **same Fortran source + same compiler + same libm =
bit-stable output**. It does NOT promise byte-equivalent output across
different compilers or libm vendors.

## What the contract does NOT assert

- **Cross-platform bit-equivalence**. macOS Homebrew GCC 15.2.0 +
  Apple libm and Ubuntu CI gfortran 13.x + glibc produce slightly
  different floating-point output (single-ULP drift in transcendental
  intrinsics like `exp` / `sin` / `sqrt`). For tight iterative
  solvers (FP collision operator, ray-tracing) the per-step drift
  amplifies past 1e-10 within a handful of iterations.

  The 4 cases that surface this on macOS today (issue #213):
  `fp_dt1` (RPCT[0] rel_err 2.354e-10), `fp_iter01` (40+ RPCT
  mismatches, worst 4.447e-9), `wrx_demo` (~1 scalar), `wrx_iter01`
  (`pwr_tot` rel_err 1.382e-9).

- **Per-platform reproducibility on non-canonical platforms**. The
  policy is "one canonical platform's baseline is the truth". On
  non-canonical platforms the test does not run.

## The canonical platform

**Ubuntu CI runner with gfortran 13.x**. The full set of
`linux-gcc13` baselines under `test_run/baselines/*/metrics.json`
was generated on clavius
(memory `reference_clavius_baseline_regen.md`) and is exercised on
every push by `.github/workflows/python-tests.yml` line 323's
whole-tree pytest (which sweeps the 7 module `test_equivalence.py`
suites). The exception is `tot_ht6m_short`: its baseline was
regenerated with the 4*pi**2 correction of EQ's T(psi) by
`.github/workflows/regen-baselines.yml` on a GitHub `ubuntu-24.04`
runner with gfortran 13.3.0 (run 45555967982 of
HengyuLi-Ozaki-lab/task, 2026-11-25, on a scratch branch holding develop
`47aa06f2` with the fix), together with
`python/totlib/tests/fixtures/eqdata-HT6M`, the eqdata that run solved
(`test_run/test_output/tot_ht6m_short/eqdata-HT6M`; the scratch branch
added a step to keep it, which the workflow does not have). The mono job
of `python-tests.yml` solves no eqdata and loads that committed file, so
the two are regenerated together.

## Non-Linux behavior

`python/<mod>/tests/test_equivalence.py` carries:

```python
IS_LINUX = sys.platform.startswith("linux")

@unittest.skipUnless(
    IS_LINUX,
    "Equivalence tests are Linux-canonical. ... See docs/baseline-policy.md.",
)
class TestEquivalence(...):
```

On macOS / FreeBSD / Windows / any non-Linux: tests skip. On WSL
or Linux containers running on macOS Docker: `sys.platform.startswith("linux")` is True,
so they run. The policy is "Linux userland", not "physical host OS".

The skip is **NOT overridable** by env var. The policy is binary:
Linux userland or no equivalence check.

## What macOS dev gets

- `lib<mod>api.so` build and run normally via the Python wrappers
  (`Tot`, `Eqlib`, `Trlib`, etc.). Other test suites
  (`python/<mod>/tests/test_<mod>lib.py`, etc.) exercise the
  wrappers and ARE run on macOS — they catch ABI / load / call-
  pattern issues.
- Equivalence at 1e-10 is verified by CI Ubuntu every push. Pulling
  the PR after CI green is the verification gate.

## How to verify equivalence locally on non-Linux

Run a Linux container with gfortran 13.x:

```bash
docker run --rm -it -v "$(pwd)":/work -w /work ubuntu:24.04 bash -c "
  apt-get update && apt-get install -y gfortran python3 python3-pip
  pip3 install 'pytest<9.2' pytest-forked pytest-timeout pytest-mock   # as CI (#277)
  ./scripts/setup.sh   # bpsd clone + lib*api.so build
  python3 -m pytest python/ --forked --timeout=120 --timeout-method=signal
"
```

This reproduces the CI gate locally. Slower than running on macOS
directly, but the only way to get the 1e-10 contract verified
off-CI.

## How to promote a new platform to canonical

If a project priority arises (e.g. macOS becomes a supported
production target, not just dev), two structural prerequisites must
be addressed first — these block the platform-keyed baseline
approach that was attempted and rejected on 2026-05-26 (Codex
2-round execution blocker analysis):

1. **Graphics-stubs gap**: 6 of 7 modules (`fp` / `ti` / `tr` /
   `eq` / `wr` / `wrx`) link their standalone Fortran binaries
   against real GFLIBS (`-lg3d-gfc64 -lgsp-gfc64 -lgdp-gfc64`),
   which Homebrew does not provide. Only `tot` has
   `tot_static_stubs.f90` for graphics-free linking.
   `reference_clavius_baseline_regen.md` documents this. Phase-L-
   sized work to write per-module `<mod>_static_stubs.f90` would
   close the gap.
2. **Python-fixture gap**: 6-8 of 20 baseline cases lack
   `<case>_params.py` Python fixtures (`eq_jt60`, `fp_jt60`,
   `ti_min`, `ti_w`, `tr_m0904`, `wrx_jt60`, plus `tot_*_short`
   name-mismatch resolution). They were generated by the Linux-
   only standalone-binary regen workflow and are dead baselines
   from the Python test surface's perspective. See [#215](https://github.com/k-yoshimi/task/issues/215)
   for the gap inventory + how to close it case-by-case.

Once both gaps close, the rejected platform-keyed design
(`docs/superpowers/specs/2026-05-26-platform-keyed-baselines-design.md`
— marked SUPERSEDED) can be revisited as a follow-up.

## References

- Memory: `feedback_equivalence_must_pass.md` — distinguishes
  principled platform-scoped skip (this) from invisibility skip
  (forbidden).
- Memory: `reference_clavius_baseline_regen.md` — Linux canonical
  baseline-gen host conventions.
- Spec: `docs/superpowers/specs/2026-05-26-linux-canonical-equiv-policy-design.md`
  (this design).
- Superseded specs (kept as design history):
  - `docs/superpowers/specs/2026-05-26-platform-keyed-baselines-design.md`
  - `docs/superpowers/plans/2026-05-26-platform-keyed-baselines-implementation.md`
