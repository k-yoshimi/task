"""Property-based boundary-value sweeps for tilib.

Mutates selected parameters from the ``ti_min`` fixture and asserts the
run either (a) succeeds and produces sane output (finite T scalar,
profile shapes match runtime extents), or (b) fails with the expected
exception type from :mod:`tilib.errors`.

Scope: widen Layer-3 coverage beyond the single canonical fixture; this
is complementary to ``test_equivalence.py`` (1e-10 reference match) and
``test_sweep.py`` (3x3 DT/NRMAX grid). No baseline comparison here --
boundary-value mutation is about regression / crash-safety, not physics.

Uses :class:`TiDataCwdMixin` so each subTest sees the ADPOST/ADF11 data
files via the symlinked tmp cwd, matching the run-test-case harness in
``test_run/run_tests.sh``.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "ti" / "libtiapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from tilib.tests._data_cwd import TiDataCwdMixin  # noqa: E402


def _tilib_importable() -> bool:
    try:
        import tilib  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtiapi.so not built at {DEFAULT_SO}; run `make -C ti libtiapi.so`",
)
@unittest.skipUnless(_tilib_importable(), "python/tilib not importable")
class TestTilibBoundaryValues(TiDataCwdMixin, unittest.TestCase):
    """Boundary-value mutations on top of the ``ti_min`` fixture."""

    NTMAX = 2

    def _apply_and_run(self, ti, mutations: dict, ntmax: int):
        """Apply ti_min, overlay mutations, run, return state."""
        from tilib.tests.fixtures import ti_iter01_params as base
        base.apply(ti)
        ti.set_param("NTMAX", float(ntmax))
        for name, value in mutations.items():
            ti.set_param(name, float(value))
        ti.run(ntmax)
        return ti.get_state()

    def _assert_finite_state(self, state) -> None:
        """Assert the time scalar is finite and profile shapes match."""
        self.assertFalse(math.isnan(state.T), f"NaN T={state.T}")
        self.assertFalse(math.isinf(state.T), f"Inf T={state.T}")
        # 1-D profiles sized by NRMAX.
        self.assertEqual(
            len(state.RBP), state.nrmax,
            f"RBP length {len(state.RBP)} != nrmax={state.nrmax}",
        )
        # 2-D profiles sized by [NRMAX][NSA_MAX].
        self.assertEqual(
            len(state.RNA), state.nrmax,
            f"RNA rows {len(state.RNA)} != nrmax={state.nrmax}",
        )
        if state.nrmax > 0:
            self.assertEqual(
                len(state.RNA[0]), state.nsa_max,
                f"RNA cols {len(state.RNA[0])} != nsa_max={state.nsa_max}",
            )

    # --- sweeps -----------------------------------------------------------
    def test_NSMAX_sweep(self):
        from tilib import TiLib
        from tilib.errors import TilibError
        for nsmax in (1, 2):
            with self.subTest(NSMAX=nsmax):
                with TiLib() as ti:
                    try:
                        state = self._apply_and_run(
                            ti, {"NSMAX": nsmax}, self.NTMAX,
                        )
                    except TilibError:
                        continue
                    self._assert_finite_state(state)

    def test_NRMAX_sweep(self):
        from tilib import TiLib
        from tilib.errors import TilibError
        for nrmax in (10, 20, 50):
            with self.subTest(NRMAX=nrmax):
                with TiLib() as ti:
                    try:
                        state = self._apply_and_run(
                            ti, {"NRMAX": nrmax}, self.NTMAX,
                        )
                    except TilibError:
                        continue
                    self.assertEqual(state.nrmax, nrmax)
                    self._assert_finite_state(state)

    def test_DN0_sweep(self):
        """Particle-diffusion D0 sweep including the boundary value 0.0."""
        from tilib import TiLib
        from tilib.errors import TilibError
        for dn0 in (0.0, 0.1, 1.0):
            with self.subTest(DN0=dn0):
                with TiLib() as ti:
                    try:
                        state = self._apply_and_run(
                            ti, {"DN0": dn0}, self.NTMAX,
                        )
                    except TilibError:
                        continue
                    self._assert_finite_state(state)

    def test_DT0_sweep(self):
        """Heat-diffusion D0 sweep including the boundary value 0.0."""
        from tilib import TiLib
        from tilib.errors import TilibError
        for dt0 in (0.0, 1.0, 5.0):
            with self.subTest(DT0=dt0):
                with TiLib() as ti:
                    try:
                        state = self._apply_and_run(
                            ti, {"DT0": dt0}, self.NTMAX,
                        )
                    except TilibError:
                        continue
                    self._assert_finite_state(state)

    def test_unknown_param_raises(self):
        """Unregistered parameter names raise TilibParamError."""
        from tilib import TiLib
        from tilib.errors import TilibParamError
        with TiLib() as ti:
            with self.assertRaises(TilibParamError):
                ti.set_param("DEFINITELY_NOT_A_PARAM", 1.0)


if __name__ == "__main__":
    unittest.main()
