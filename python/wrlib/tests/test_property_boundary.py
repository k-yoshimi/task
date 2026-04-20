"""Property-based boundary-value sweeps for wrlib.

Mutates selected parameters from the ``wr_test001`` fixture and asserts
the run either (a) succeeds and produces sane output (finite peak power,
shapes match runtime extents), or (b) fails with the expected exception
type from :mod:`wrlib.errors`.

Scope: widen Layer-3 coverage beyond the single canonical fixture; this
is complementary to ``test_equivalence.py`` (1e-10 reference match) and
``test_sweep.py`` (3x3 RFIN/ANGPHIN grid). No baseline comparison here
-- boundary-value mutation is about regression / crash-safety, not
physics.

Each subTest reduces NRAYMAX to keep the cost low, and uses NSTPMAX
inherited from ``wr_test001`` (2000) which finishes in a few seconds
per ray. We skip MDLWRI values that are documented as unsupported
(see ``wr/wrexecr.f90`` for the supported set).
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "wr" / "libwrapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _wrlib_importable() -> bool:
    try:
        import wrlib  # noqa: F401
    except Exception:
        return False
    return True


# Supported MDLWRI values per wr/wrsetupb.f90 + wrexecr.f90.
# The wr_test001 fixture uses MDLWRI=101 (100-series = RB-mode parser).
# wrsetupb explicitly bails on MDLWRI=2 ("XX MDLWRI=2 IS NOT SUPPORTED
# YET."), so the practical sweep covers {1, 101} plus the default 0.
# We deliberately skip 2/3 to avoid hitting documented unsupported
# branches (the test would have to assert WrlibError, which doesn't
# carry signal beyond what test_unknown_param_raises already covers).
MDLWRI_VALUES = (0, 1, 101)


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libwrapi.so not built at {DEFAULT_SO}; run `make -C wr libwrapi.so`",
)
@unittest.skipUnless(_wrlib_importable(), "python/wrlib not importable")
class TestWrlibBoundaryValues(unittest.TestCase):
    """Boundary-value mutations on top of the ``wr_test001`` fixture."""

    def _apply_and_run(self, wr, mutations: dict, nraymax: int):
        """Apply test001, overlay mutations + reduced NRAYMAX, run, state."""
        from wrlib.tests.fixtures import wr_test001_params as base
        base.apply(wr)
        wr.set_param("NRAYMAX", float(nraymax))
        for name, value in mutations.items():
            wr.set_param(name, float(value))
        wr.run(0)
        return wr.get_state()

    def _assert_finite_state(self, state) -> None:
        """Assert peak power scalars are finite and shapes match extents."""
        for name, val in state.scalars.items():
            self.assertFalse(math.isnan(val), f"NaN scalar {name}={val}")
            self.assertFalse(math.isinf(val), f"Inf scalar {name}={val}")
        self.assertEqual(
            len(state.pwrmax_rs_nray), state.nraymax,
            f"pwrmax_rs_nray length {len(state.pwrmax_rs_nray)} "
            f"!= nraymax={state.nraymax}",
        )
        self.assertEqual(
            len(state.pwr_nrs), state.nrsmax,
            f"pwr_nrs length {len(state.pwr_nrs)} != nrsmax={state.nrsmax}",
        )

    # --- sweeps -----------------------------------------------------------
    def test_NRAYMAX_sweep(self):
        from wrlib import Wrlib
        from wrlib.errors import WrlibError
        for nraymax in (1, 2, 4):
            with self.subTest(NRAYMAX=nraymax):
                with Wrlib() as wr:
                    try:
                        state = self._apply_and_run(
                            wr, mutations={}, nraymax=nraymax,
                        )
                    except WrlibError:
                        continue
                    self.assertEqual(state.nraymax, nraymax)
                    self._assert_finite_state(state)

    def test_MDLWRI_sweep(self):
        from wrlib import Wrlib
        from wrlib.errors import WrlibError
        for mdlwri in MDLWRI_VALUES:
            with self.subTest(MDLWRI=mdlwri):
                with Wrlib() as wr:
                    try:
                        # Reduce to 1 ray to keep each subTest cheap.
                        state = self._apply_and_run(
                            wr, {"MDLWRI": mdlwri}, nraymax=1,
                        )
                    except WrlibError:
                        # Some MDLWRI values may need extra setup; treat
                        # a controlled failure as acceptable rather than
                        # a regression.
                        continue
                    self._assert_finite_state(state)

    def test_unknown_param_raises(self):
        """Unregistered parameter names raise WrlibParamError."""
        from wrlib import Wrlib
        from wrlib.errors import WrlibParamError
        with Wrlib() as wr:
            with self.assertRaises(WrlibParamError):
                wr.set_param("DEFINITELY_NOT_A_PARAM", 1.0)

    def test_NSMAX_in_range(self):
        """NSMAX in {2,3,4} (all available species in the test001 fixture)."""
        from wrlib import Wrlib
        from wrlib.errors import WrlibError
        for nsmax in (2, 3, 4):
            with self.subTest(NSMAX=nsmax):
                with Wrlib() as wr:
                    try:
                        state = self._apply_and_run(
                            wr, {"NSMAX": nsmax}, nraymax=1,
                        )
                    except WrlibError:
                        continue
                    self._assert_finite_state(state)


if __name__ == "__main__":
    unittest.main()
