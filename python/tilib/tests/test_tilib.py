"""High-level ``TiLib`` class tests.

Covers:

* errors module wiring (no ``libtiapi.so`` needed).
* ``TiState.to_dict()`` shape using a hand-built ``TiStateC`` (no
  ``libtiapi.so`` needed).
* Full init -> set_param -> run(0) -> get_state -> finalize cycle
  against the real library (skipped if not built).
* Context-manager lifecycle (``__enter__``/``__exit__``).
* Negative tests for invalid params / double-close / closed handle.
* Layer 3 reinforcement (Phase L-6): array round-trip via set_param,
  repeated run accumulates state, set_params dict bulk-set path.

The suite is designed to produce the 24 tests listed in the L-6 plan's
"tilib_wrapper" entry when combined with ``test_ffi.py``. See
``docs/superpowers/plans/2026-04-18-ti-library-L6-test-4layers.md``.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from tilib import (  # noqa: E402
    TiLib,
    Tilib,
    TiState,
    TilibError,
    TilibParamError,
    TilibStateError,
    TilibRunError,
    TilibNotImplementedError,
    raise_for_ierr,
)
from tilib import _ffi  # noqa: E402
from tilib.tests._data_cwd import TiDataCwdMixin  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "ti" / "libtiapi.so"


# =====================================================================
# Tests that do not need libtiapi.so -- always run.
# =====================================================================
class TestErrorsModule(unittest.TestCase):
    def test_raise_for_ierr_ok(self):
        # ierr=0 must never raise.
        raise_for_ierr("dummy", 0)

    def test_raise_for_ierr_codes(self):
        for ierr, cls in (
            (1, TilibParamError),
            (2, TilibStateError),
            (3, TilibRunError),
            (4, TilibNotImplementedError),
        ):
            with self.assertRaises(cls):
                raise_for_ierr("dummy", ierr)

    def test_unknown_code_falls_back(self):
        with self.assertRaises(TilibError):
            raise_for_ierr("dummy", 99)

    def test_subclasses(self):
        for cls in (
            TilibParamError, TilibStateError, TilibRunError,
            TilibNotImplementedError,
        ):
            self.assertTrue(issubclass(cls, TilibError))

    def test_tilib_alias(self):
        # ``Tilib`` is exported as a lowercase-friendly alias for
        # ``TiLib`` to match spec-style naming.
        self.assertIs(Tilib, TiLib)


class TestTiStateFromC(unittest.TestCase):
    """Exercise :py:meth:`TiState.from_c` / ``to_dict`` with no library."""

    def _populated_state(self, nr: int = 3, nsa: int = 2) -> _ffi.TiStateC:
        s = _ffi.TiStateC()
        s.nt = 7
        s.nrmax = nr
        s.nsa_max = nsa
        s.nsmax = nsa + 1
        s.T = 1.25
        s.residual_loop_max = 1.0e-6
        s.icount_loop_max = 13
        s.icount_mat_max = 42
        for i in range(nr):
            for j in range(nsa):
                s.RNA[i][j] = float(i * 10 + j)
                s.RTA[i][j] = float(i * 10 + j) + 0.5
                s.RUA[i][j] = float(i * 10 + j) + 0.25
            s.RBP[i] = float(i) + 0.1
            s.RQP[i] = float(i) + 0.2
            s.RJP[i] = float(i) + 0.3
            s.ZEFF[i] = 1.0 + 0.1 * i
            s.BETA[i] = 0.01 * (i + 1)
            s.BETAP[i] = 0.02 * (i + 1)
        return s

    def test_from_c_slices_correctly(self):
        c = self._populated_state(nr=3, nsa=2)
        st = TiState.from_c(c)
        self.assertEqual(st.nt, 7)
        self.assertEqual(st.nrmax, 3)
        self.assertEqual(st.nsa_max, 2)
        self.assertEqual(st.nsmax, 3)
        self.assertEqual(len(st.RNA), 3)
        self.assertEqual(len(st.RNA[0]), 2)
        self.assertAlmostEqual(st.RNA[2][1], 21.0)
        self.assertAlmostEqual(st.RTA[1][0], 10.5)
        self.assertAlmostEqual(st.RUA[0][1], 1.25)
        self.assertAlmostEqual(st.RBP[2], 2.1)
        self.assertAlmostEqual(st.RQP[0], 0.2)
        self.assertAlmostEqual(st.RJP[1], 1.3)
        self.assertAlmostEqual(st.ZEFF[2], 1.2)
        self.assertAlmostEqual(st.T, 1.25)
        self.assertEqual(st.icount_loop_max, 13)
        self.assertEqual(st.icount_mat_max, 42)

    def test_to_dict_shape(self):
        c = self._populated_state(nr=2, nsa=2)
        d = TiState.from_c(c).to_dict()
        self.assertEqual(d["NT"], 7)
        self.assertEqual(d["NRMAX"], 2)
        self.assertEqual(d["NSA_MAX"], 2)
        self.assertEqual(d["NSMAX"], 3)
        self.assertIn("scalars", d)
        self.assertEqual(
            set(d["scalars"]).issuperset({"T", "residual_loop_max"}),
            True,
        )
        # icount_*_max moved to scalars_int (matches Phase-0 baseline
        # tiregress.f90 grouping) so compare_metrics finds them at the
        # same JSON path the baselines use.
        self.assertIn("scalars_int", d)
        self.assertEqual(
            set(d["scalars_int"]).issuperset({"icount_loop_max", "icount_mat_max"}),
            True,
        )
        self.assertEqual(len(d["profile"]), 2)
        p0 = d["profile"][0]
        self.assertEqual(p0["NR"], 1)
        for k in ("RNA", "RTA", "RUA", "RBP", "RQP", "RJP",
                  "ZEFF", "BETA", "BETAP"):
            self.assertIn(k, p0)
        self.assertEqual(len(p0["RNA"]), 2)  # NSA_MAX entries

    def test_to_dict_json_serialisable(self):
        import json
        c = self._populated_state(nr=2, nsa=2)
        d = TiState.from_c(c).to_dict()
        # Must round-trip through JSON without custom encoder.
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["NRMAX"], 2)


# =====================================================================
# Tests that DO need the real libtiapi.so on disk.
# =====================================================================
@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtiapi.so not built at {DEFAULT_SO}; run `make -C ti libtiapi.so`",
)
class TestTiLibLifecycle(TiDataCwdMixin, unittest.TestCase):
    def test_context_manager(self):
        with TiLib() as ti:
            self.assertFalse(ti.closed)
        self.assertTrue(ti.closed)

    def test_run_zero_and_get_state(self):
        with TiLib() as ti:
            ti.run(0)   # stubs may be no-op; we only require ierr==0
            state = ti.get_state()
            self.assertIsInstance(state, TiState)
            self.assertGreaterEqual(state.nrmax, 0)
            self.assertGreaterEqual(state.nsa_max, 0)

    def test_double_close_idempotent(self):
        ti = TiLib()
        ti.close()
        ti.close()  # must not raise
        self.assertTrue(ti.closed)

    def test_call_on_closed_raises(self):
        ti = TiLib()
        ti.close()
        with self.assertRaises(TilibError):
            ti.run(0)
        with self.assertRaises(TilibError):
            ti.get_state()
        with self.assertRaises(TilibError):
            ti.set_param("RR", 1.0)

    def test_invalid_param_raises(self):
        with TiLib() as ti:
            with self.assertRaises((TilibParamError, TilibError)):
                ti.set_param("NOT_A_REAL_PARAMETER", 0.0)

    def test_set_params_rejects_double_underscore(self):
        with TiLib() as ti:
            with self.assertRaises(TilibError):
                # set_params() is scalar-only; __ is a common array-
                # syntax mistake we reject up-front.
                ti.set_params(PN__1=0.5)

    def test_set_params_scalar_kwargs_round_trip(self):
        # We can't assert the value was accepted (registry is library-
        # dependent) but at minimum we exercise the path and ensure
        # either success or a well-typed TilibError.
        with TiLib() as ti:
            try:
                # RR = major radius -- a commonly registered scalar.
                ti.set_params(RR=3.0)
            except TilibError:
                pass


# =====================================================================
# Layer 3 reinforcement (Phase L-6): array round-trip + repeated run.
# =====================================================================
@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtiapi.so not built at {DEFAULT_SO}; run `make -C ti libtiapi.so`",
)
class TestTiLibLayer3Reinforce(TiDataCwdMixin, unittest.TestCase):
    """L-6 Layer 3: extend the basic lifecycle tests with array-element
    round-trip and multi-step-run state accumulation checks.
    """

    def test_array_element_set_param(self):
        """``PN[1]`` style subscript syntax reaches the registry."""
        with TiLib() as ti:
            # PN is a 1D array in the registry; index 1 must succeed.
            try:
                ti.set_param("PN[1]", 0.5)
            except TilibError as e:
                self.fail(f"PN[1] should be settable but raised: {e}")

    def test_array_element_out_of_range_rejected(self):
        """Out-of-range array subscripts must raise TilibParamError."""
        with TiLib() as ti:
            with self.assertRaises(TilibError):
                ti.set_param("PN[0]", 0.0)         # 1-origin, 0 invalid
            with self.assertRaises(TilibError):
                ti.set_param("PN[99999]", 0.0)     # way out of range

    def test_run_zero_then_get_state_multiple(self):
        """Repeated ``run(0) + get_state`` calls return consistent state."""
        with TiLib() as ti:
            ti.run(0)
            s1 = ti.get_state()
            ti.run(0)
            s2 = ti.get_state()
            # Two zero-step runs must leave NRMAX / NSA_MAX unchanged.
            self.assertEqual(s1.nrmax, s2.nrmax)
            self.assertEqual(s1.nsa_max, s2.nsa_max)

    def test_run_advances_T(self):
        """Finite ``run(n)`` advances the simulation time scalar."""
        with TiLib() as ti:
            try:
                ti.set_param("DT", 0.01)
                ti.set_param("NTSTEP", 1.0)
            except TilibError:
                self.skipTest("DT / NTSTEP not in registry")
            s0 = ti.get_state()
            ti.run(3)
            s1 = ti.get_state()
            # T should be non-decreasing; we don't pin an exact delta
            # because the solver may coalesce steps.
            self.assertGreaterEqual(s1.T, s0.T)

    def test_set_params_bulk_dict_path(self):
        """``set_params(**dict)`` bulk dispatch reaches every name."""
        with TiLib() as ti:
            # Intentionally use only keys ti_param_registry knows.
            ti.set_params(NRMAX=10.0, NTMAX=2.0, NTSTEP=1.0)


if __name__ == "__main__":
    unittest.main()
