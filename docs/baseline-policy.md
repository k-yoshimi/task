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

**Ubuntu CI runner with gfortran 13.x**. The baselines under
`test_run/baselines/*/metrics.json` are exercised on every push by
`.github/workflows/python-tests.yml`'s whole-tree pytest (which sweeps
the 7 module `test_equivalence.py` suites).

They no longer share one provenance, so record it per group. Where a claim
rests on inference rather than a log, it says so.

| baselines | compiler | basis |
|---|---|---|
| `eq_iter01`, `eq_tst2`, `eq_jt60`, `tr_iter01`, `tr_tst2` | GitHub `ubuntu-24.04`, gfortran 13.3.0 | **measured** -- `regen-baselines.yml` run 30514856222 logs it. Regenerated together with the four `eqdata` fixtures they read (NTVMAX 200 -> 400) |
| `tot_ht6m_short`, `wrx_demo`, `wrx_iter01` | GitHub CI runner, gfortran 13.3.0 | **measured** -- run 28327720495, the run `d1f7f9e7` (2026-06-29) cites, logs `GNU Fortran (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`. NOTE: `d1f7f9e7`'s own message says "gf13.2"; that reads the apt metapackage revision `4:13.2.0-7ubuntu1`, printed elsewhere in the same apt step -- measured on run 28327720495 itself, 60 lines later; on run 30516807586, 4 lines in the build-only jobs and 149 in the pytest jobs. The compiler was 13.3.0 |
| `tot_demo2014_short` | clavius | **stated** -- `14659b3a` (2026-05-12) body: "2 baseline regens on clavius". No compiler given |
| `wrx_jt60` | unknown | last touched by `0cd923bf` (2026-04-18), which has an empty body. It predates the `36586def` / `d1f7f9e7` wrx regens, and `36586def` touched only `wrx_demo`/`wrx_iter01`, so attributions for that pair do not transfer. The least-characterised baseline in the set, and the best candidate for the next regeneration |
| `tr_m0904`, `fp_*`, `ti_*`, `wr_*` | clavius, **unconfirmed** | `9614009b` / `8956d7a9` / `a12465a5` / `404b79ec` / `87941c97` name no machine (`404b79ec` says only "on a dev box") and no compiler; the attribution rests on memory `reference_clavius_baseline_regen.md` |

Rows 1 and 2 are the same compiler, 13.3.0 -- there is no patch-level straddle
between them. Read `apt-get install` output with care when attributing one:
`4:13.2.0-7ubuntu1` is the gcc-defaults metapackage revision, not the
compiler. Every job
here prints the real version with `gfortran --version | head -1`; use that.

Anything regenerated from now on must come from the CI runner, not from
clavius or a developer machine. That follows from the canonical-platform
definition above on its own -- generating elsewhere is off-policy by
construction, whatever the size of the gap.

On the size of the gap, two data points of different strength:

- **~3e-9**, clavius vs CI on eq_tst2 / tr_tst2. This is what #197 was
  filed on; the drift is real and measured, though #197's attribution of it
  to a compiler-version difference does not survive checking (see the note
  at the top of `.github/workflows/regen-baselines.yml`).
- **~4e-10**, a macOS-generated `eqdata.TST-2` scored against the CI
  baseline -- 10 mismatches, 4x over tolerance. Reported by a scoping
  investigation for this change and NOT reproduced independently, so treat
  it as indicative. It is quoted because it points at the sharper hazard:
  the gate skips on non-Linux (#213), so a developer-generated fixture
  cannot be scored on the machine that produced it.

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
  pip3 install pytest pytest-forked pytest-timeout pytest-mock
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
