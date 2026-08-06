"""High-level :class:`Eq` class tests.

Covers:

* errors module wiring (no ``libeqapi.so`` needed).
* :py:meth:`EqState.from_c` / :py:meth:`EqState.to_dict` shape using
  a hand-built :class:`EqStateC` (no ``libeqapi.so`` needed).
* Full init -> set_param -> get_state -> finalize cycle against the
  real library (skipped if the .so is not built).
* Context-manager lifecycle (``__enter__`` / ``__exit__``).
* Negative tests for invalid params / double-close / closed handle.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eqlib import (  # noqa: E402
    Eq,
    EqState,
    EqlibError,
    EqlibInvalidParamError,
    EqlibNotInitializedError,
    EqlibCalculationFailedError,
    EqlibNotImplementedError,
    raise_for_rc,
    raise_for_ierr,
)
from eqlib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "eq" / "libeqapi.so"


def _resolved_so() -> Path:
    env = os.environ.get("EQLIB_PATH")
    if env:
        return Path(env)
    return DEFAULT_SO


# =====================================================================
# Tests that do not need libeqapi.so -- always run.
# =====================================================================
class TestErrorsModule(unittest.TestCase):
    def test_raise_for_rc_ok(self):
        # rc=0 must never raise.
        raise_for_rc("dummy", 0)
        raise_for_ierr("dummy", 0)  # alias

    def test_raise_for_rc_codes(self):
        for rc, cls in (
            (1, EqlibInvalidParamError),
            (2, EqlibNotInitializedError),
            (3, EqlibCalculationFailedError),
            (4, EqlibNotImplementedError),
        ):
            with self.assertRaises(cls):
                raise_for_rc("dummy", rc)

    def test_unknown_code_falls_back(self):
        with self.assertRaises(EqlibError):
            raise_for_rc("dummy", 99)

    def test_subclasses(self):
        for cls in (
            EqlibInvalidParamError,
            EqlibNotInitializedError,
            EqlibCalculationFailedError,
            EqlibNotImplementedError,
        ):
            self.assertTrue(issubclass(cls, EqlibError))


class TestEqStateFromC(unittest.TestCase):
    """Exercise :py:meth:`EqState.from_c` / ``to_dict`` with no library."""

    def _populated_state(self, nrg: int = 4, nzg: int = 3, nps: int = 2):
        s = _ffi.EqStateC()
        s.nrgmax = nrg
        s.nzgmax = nzg
        s.npsmax = nps
        s.nrmax = 5
        s.nthmax = 6
        s.nsumax = 7
        s.raxis = 3.0
        s.zaxis = 0.5
        s.psi0 = 1.25
        s.psipa = 2.5
        s.psita = 3.75
        s.qaxis = 1.05
        s.qsurf = 3.5
        s.betat = 0.02
        s.betap = 0.5
        s.pvol = 100.0
        s.raave = 1.0
        s.ripx = 1.5
        for i in range(nrg):
            s.rg[i] = float(i) + 1.0
        for j in range(nzg):
            s.zg[j] = float(j) - 1.0
        for k in range(nps):
            s.psips[k] = float(k) * 0.1
            s.ppps[k] = float(k) * 0.2
            s.ttps[k] = float(k) * 0.3
            s.qqps[k] = float(k) * 0.4 + 1.0
        return s

    def test_from_c_slices_correctly(self):
        c = self._populated_state(nrg=4, nzg=3, nps=2)
        st = EqState.from_c(c)
        self.assertEqual(st.nrgmax, 4)
        self.assertEqual(st.nzgmax, 3)
        self.assertEqual(st.npsmax, 2)
        self.assertEqual(st.nrmax, 5)
        self.assertEqual(st.nthmax, 6)
        self.assertEqual(st.nsumax, 7)
        self.assertEqual(len(st.rg), 4)
        self.assertEqual(len(st.zg), 3)
        self.assertEqual(len(st.psips), 2)
        self.assertAlmostEqual(st.rg[3], 4.0)
        self.assertAlmostEqual(st.zg[0], -1.0)
        self.assertAlmostEqual(st.qqps[1], 1.4)
        self.assertAlmostEqual(st.scalars["raxis"], 3.0)
        self.assertAlmostEqual(st.scalars["qaxis"], 1.05)

    def test_to_dict_shape(self):
        c = self._populated_state(nrg=2, nzg=2, nps=2)
        d = EqState.from_c(c).to_dict()
        self.assertEqual(d["NRGMAX"], 2)
        self.assertEqual(d["NZGMAX"], 2)
        self.assertEqual(d["NPSMAX"], 2)
        self.assertEqual(d["NRMAX"], 5)
        self.assertIn("scalars", d)
        # uppercase keys to match Phase 0 baseline JSON.
        self.assertIn("RAXIS", d["scalars"])
        self.assertIn("QAXIS", d["scalars"])
        self.assertEqual(len(d["RG"]), 2)
        self.assertEqual(len(d["PSIPS"]), 2)

    def test_to_dict_json_serialisable(self):
        c = self._populated_state(nrg=2, nzg=2, nps=2)
        d = EqState.from_c(c).to_dict()
        # Must round-trip through JSON without a custom encoder.
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["NRGMAX"], 2)


# =====================================================================
# Tests that DO need the real libeqapi.so on disk.
# =====================================================================
@unittest.skipUnless(
    _resolved_so().exists(),
    f"libeqapi.so not built at {_resolved_so()}; "
    "run `make -C eq libeqapi.so`",
)
class TestEqLifecycle(unittest.TestCase):
    def test_context_manager(self):
        with Eq() as eq:
            self.assertFalse(eq.closed)
        self.assertTrue(eq.closed)

    def test_get_state_after_init(self):
        with Eq() as eq:
            state = eq.get_state()
            self.assertIsInstance(state, EqState)
            self.assertGreaterEqual(state.nrgmax, 0)
            self.assertGreaterEqual(state.nzgmax, 0)

    def test_double_close_idempotent(self):
        eq = Eq()
        eq.close()
        eq.close()  # must not raise
        self.assertTrue(eq.closed)

    def test_call_on_closed_raises(self):
        eq = Eq()
        eq.close()
        with self.assertRaises(EqlibError):
            eq.run(0)
        with self.assertRaises(EqlibError):
            eq.get_state()
        with self.assertRaises(EqlibError):
            eq.set_param("RR", 1.0)
        with self.assertRaises(EqlibError):
            eq.set_param_str("KNAMEQ", "x")
        with self.assertRaises(EqlibError):
            eq.save("/tmp/eq.bin")
        with self.assertRaises(EqlibError):
            eq.get_psi_rz()

    def test_invalid_param_raises(self):
        with Eq() as eq:
            with self.assertRaises((EqlibInvalidParamError, EqlibError)):
                eq.set_param("NOT_A_REAL_PARAMETER", 0.0)

    def test_set_params_rejects_double_underscore(self):
        with Eq() as eq:
            with self.assertRaises(EqlibError):
                # set_params() is scalar-only; '__' is a common
                # array-syntax mistake we reject up-front.
                eq.set_params(PSIB__0=0.0)

    def test_set_params_scalar_kwargs(self):
        # We can't assert the value was accepted at the physics layer
        # but at minimum we exercise the path and ensure either success
        # or a well-typed EqlibError.
        with Eq() as eq:
            try:
                # RR = major radius -- a commonly registered scalar.
                eq.set_params(RR=3.0, BB=3.0)
            except EqlibError:
                pass

    def test_set_params_dict_form(self):
        with Eq() as eq:
            try:
                eq.set_params({"RR": 3.0, "BB": 3.0})
            except EqlibError:
                pass

    def test_set_param_psib_array(self):
        # PSIB is 0-origin (PSIB(0:5)). Bare "PSIB" is rejected by
        # the L-3 registry (idx == -1 sentinel); subscripted form
        # should succeed.
        with Eq() as eq:
            eq.set_param("PSIB[0]", 0.0)
            with self.assertRaises((EqlibInvalidParamError, EqlibError)):
                eq.set_param("PSIB", 0.0)

    def test_set_param_str_knameq(self):
        # KNAMEQ is the canonical string parameter for the EQDSK file
        # path. Setting an empty string is a valid no-op (libeqapi
        # treats it the same as the namelist default).
        with Eq() as eq:
            try:
                eq.set_param_str("KNAMEQ", "eqdata.in")
            except EqlibError:
                # Some L-3 builds may reject; we only care that the
                # call path is exercised without segfault.
                pass

    def test_run_unimplemented_mode_raises(self):
        # eq_run(mode != 1) currently returns EQ_ERR_NOT_IMPL.
        with Eq() as eq:
            with self.assertRaises(EqlibNotImplementedError):
                eq.run(mode=99)


if __name__ == "__main__":
    unittest.main()
