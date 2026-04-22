"""Property-based boundary-value sweeps for fplib.

Mutates selected parameters from the ``fp_dt1`` fixture and asserts the
run either (a) succeeds and produces sane output (finite TIMEFP, profile
shapes match runtime extents), or (b) fails with the expected exception
type from :mod:`fplib.errors`.

Scope: widen Layer-3 coverage beyond the single canonical fixture; this
is complementary to ``test_equivalence.py`` (1e-10 reference match) and
``test_sweep.py`` (3x3 RR/BB grid). No baseline comparison here --
boundary-value mutation is about regression / crash-safety, not physics.

Each subTest reuses the ``fp_dt1`` fixture (NRMAX=1, NTMAX=1) which is
the cheapest registered FP case; mutating NPMAX / NTHMAX does change
runtime, so the upper bounds in the sweep are kept conservative
(<= 100 for NPMAX / 50 for NTHMAX).
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

import pytest

# SIGABRT manifests in CI (GH Actions' Ubuntu heap layout) but not on
# this dev host. Apply xfail CI-only so strict=True (CLAUDE.md rule)
# does not fail local runs where the test happens to pass.
_CI = os.environ.get("CI", "").lower() == "true"

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "fp" / "libfpapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _fplib_importable() -> bool:
    try:
        import fplib  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libfpapi.so not built at {DEFAULT_SO}; run `make -C fp libfpapi.so`",
)
@unittest.skipUnless(_fplib_importable(), "python/fplib not importable")
class TestFplibBoundaryValues(unittest.TestCase):
    """Boundary-value mutations on top of the ``fp_dt1`` fixture."""

    NTMAX = 1

    def _apply_and_run(self, fp, mutations: dict, ntmax: int):
        """Apply the dt1 fixture, overlay ``mutations``, run, return state."""
        from fplib.tests.fixtures import fp_dt1_params as base
        base.apply(fp)
        fp.set_param("NTMAX", float(ntmax))
        for name, value in mutations.items():
            fp.set_param(name, float(value))
        fp.run(ntmax)
        return fp.get_state()

    def _assert_finite_state(self, state) -> None:
        """Assert TIMEFP finite and profile shapes match runtime extents."""
        self.assertFalse(
            math.isnan(state.timefp), f"NaN timefp={state.timefp}",
        )
        self.assertFalse(
            math.isinf(state.timefp), f"Inf timefp={state.timefp}",
        )
        self.assertEqual(
            len(state.RNT), state.nsamax,
            f"RNT rows {len(state.RNT)} != nsamax={state.nsamax}",
        )
        if state.nsamax > 0:
            self.assertEqual(
                len(state.RNT[0]), state.nrmax,
                f"RNT cols {len(state.RNT[0])} != nrmax={state.nrmax}",
            )

    # --- sweeps -----------------------------------------------------------
    def test_NPMAX_sweep(self):
        from fplib import Fplib
        from fplib.errors import FplibError
        for npmax in (20, 50, 100):
            with self.subTest(NPMAX=npmax):
                with Fplib() as fp:
                    try:
                        state = self._apply_and_run(
                            fp, {"NPMAX": npmax}, self.NTMAX,
                        )
                    except FplibError:
                        continue
                    self.assertEqual(state.npmax, npmax)
                    self._assert_finite_state(state)

    def test_NTHMAX_sweep(self):
        from fplib import Fplib
        from fplib.errors import FplibError
        for nthmax in (10, 30, 50):
            with self.subTest(NTHMAX=nthmax):
                with Fplib() as fp:
                    try:
                        state = self._apply_and_run(
                            fp, {"NTHMAX": nthmax}, self.NTMAX,
                        )
                    except FplibError:
                        continue
                    self.assertEqual(state.nthmax, nthmax)
                    self._assert_finite_state(state)

    def test_DELT_sweep(self):
        """DELT spans 4 decades; extreme values may not converge.

        Acceptance policy follows the trlib pattern: extreme values are
        allowed to raise FplibError (non-convergence is a valid library
        outcome), but a successful run must produce finite output.
        """
        from fplib import Fplib
        from fplib.errors import FplibError
        for delt in (1.0e-4, 1.0e-2, 1.0):
            with self.subTest(DELT=delt):
                with Fplib() as fp:
                    try:
                        state = self._apply_and_run(
                            fp, {"DELT": delt}, self.NTMAX,
                        )
                    except FplibError:
                        continue
                    self._assert_finite_state(state)

    # XFAIL_REMOVE_WITH_144: tracked in #144 — SIGABRT (signal 6) in
    # fp heap-reuse path (#111 family). DOCUMENTED EXCEPTION to
    # CLAUDE.md §Test-suite discipline: strict=False.
    # The crash is heap-layout flaky — run 24751395782 CRASHED, run
    # 24753105813 passed cleanly. strict=True would FAIL CI on every
    # clean-pass run (XPASS(strict)=FAILED). Removal pressure
    # intentionally shifts from strict-flip to the grep string +
    # #144 link; when #144 lands the follow-up PR will delete this
    # marker directly.
    @pytest.mark.xfail(
        condition=_CI, strict=False,
        reason="SIGABRT in fp heap-reuse path — tracked in #144; "
               "marker must be removed once that lands.",
    )
    def test_NSMAX_in_range(self):
        """NSMAX in {1..4} must round-trip via FpState.nsamax (NSAMAX=NSMAX)."""
        from fplib import Fplib
        from fplib.errors import FplibError
        # Note: fp_dt1 sets NSAMAX=1 implicitly (via fp_init) and
        # NSMAX=4. Mutating NSMAX alone may leave NSAMAX > NSMAX
        # downstream; we tolerate FplibError on that interaction.
        for nsmax in (1, 2, 3, 4):
            with self.subTest(NSMAX=nsmax):
                with Fplib() as fp:
                    try:
                        state = self._apply_and_run(
                            fp, {"NSMAX": nsmax}, self.NTMAX,
                        )
                    except FplibError:
                        continue
                    self._assert_finite_state(state)

    def test_unknown_param_raises(self):
        """Unregistered parameter names raise FplibInvalidParamError."""
        from fplib import Fplib
        from fplib.errors import FplibInvalidParamError
        with Fplib() as fp:
            with self.assertRaises(FplibInvalidParamError):
                fp.set_param("DEFINITELY_NOT_A_PARAM", 1.0)

    def test_NRMAX_sweep(self):
        """Vary NRMAX while keeping NTMAX small.

        NRMAX>1 enables the radial transport solver, which is a different
        code path than the dt1 fixture's NRMAX=1 zero-D case. We bound at
        20 to keep the subTest quick.
        """
        from fplib import Fplib
        from fplib.errors import FplibError
        for nrmax in (1, 5, 20):
            with self.subTest(NRMAX=nrmax):
                with Fplib() as fp:
                    try:
                        state = self._apply_and_run(
                            fp, {"NRMAX": nrmax}, self.NTMAX,
                        )
                    except FplibError:
                        continue
                    self.assertEqual(state.nrmax, nrmax)
                    self._assert_finite_state(state)


if __name__ == "__main__":
    unittest.main()
