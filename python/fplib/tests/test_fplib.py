"""High-level ``Fplib`` class tests.

Covers:

* errors module wiring (no ``libfpapi.so`` needed).
* ``FpState.to_dict()`` shape using a hand-built ``FpStateC`` (no
  ``libfpapi.so`` needed).
* Full init -> set_param -> run(0) -> get_state -> finalize cycle
  against the real library (skipped if not built).
* Context-manager lifecycle (``__enter__``/``__exit__``).
* Negative tests for invalid params / double-close / closed handle.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from fplib import (  # noqa: E402
    Fplib,
    FpState,
    FplibError,
    FplibInvalidParamError,
    FplibNotInitError,
    FplibCalcFailedError,
    FplibNotImplementedError,
    raise_for_rc,
)
from fplib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "fp" / "libfpapi.so"


# =====================================================================
# Tests that do not need libfpapi.so -- always run.
# =====================================================================
class TestErrorsModule(unittest.TestCase):
    def test_raise_for_rc_ok(self):
        # rc=0 must never raise.
        raise_for_rc("dummy", 0)

    def test_raise_for_rc_codes(self):
        for rc, cls in (
            (1, FplibInvalidParamError),
            (2, FplibNotInitError),
            (3, FplibCalcFailedError),
            (4, FplibNotImplementedError),
        ):
            with self.assertRaises(cls):
                raise_for_rc("dummy", rc)

    def test_unknown_code_falls_back(self):
        with self.assertRaises(FplibError):
            raise_for_rc("dummy", 99)

    def test_subclasses(self):
        for cls in (
            FplibInvalidParamError, FplibNotInitError,
            FplibCalcFailedError, FplibNotImplementedError,
        ):
            self.assertTrue(issubclass(cls, FplibError))


class TestFpStateFromC(unittest.TestCase):
    """Exercise :py:meth:`FpState.from_c` / ``to_dict`` with no library."""

    def _populated_state(self, nr: int = 3, nsa: int = 2) -> _ffi.FpStateC:
        s = _ffi.FpStateC()
        s.nrmax = nr
        s.nsamax = nsa
        s.npmax = 50
        s.nthmax = 50
        s.ntg2 = 1
        s.timefp = 1.25e-3
        for ns in range(nsa):
            for ir in range(nr):
                v = float(ns * 100 + ir)
                s.RNT[ns][ir] = v
                s.RWT[ns][ir] = v + 0.1
                s.RTT[ns][ir] = v + 0.2
                s.RJT[ns][ir] = v + 0.3
                s.RPCT[ns][ir] = v + 0.4
                s.RPWT[ns][ir] = v + 0.5
        s.TOTAL_IP = 1.5
        s.STORED_ENERGY = 5.25
        s.COLLISION_POWER = -0.5
        s.ABSORPTION_POWER = 2.0
        s.ABSORPTION_WR = 1.25
        s.ABSORPTION_WM = 0.75
        s.PLASMA_VOLUME = 28.4
        return s

    def test_from_c_slices_correctly(self):
        c = self._populated_state(nr=3, nsa=2)
        st = FpState.from_c(c)
        self.assertEqual(st.nrmax, 3)
        self.assertEqual(st.nsamax, 2)
        self.assertEqual(st.npmax, 50)
        self.assertEqual(st.nthmax, 50)
        self.assertEqual(st.ntg2, 1)
        self.assertAlmostEqual(st.timefp, 1.25e-3)
        self.assertEqual(len(st.RNT), 2)       # NSAMAX outer
        self.assertEqual(len(st.RNT[0]), 3)    # NRMAX inner
        self.assertAlmostEqual(st.RNT[1][2], 102.0)
        self.assertAlmostEqual(st.RTT[0][1], 1.2)
        self.assertAlmostEqual(st.RPWT[1][0], 100.5)

    def test_from_c_copies_global_scalars(self):
        from fplib.state import SCALAR_FIELDS

        c = self._populated_state(nr=3, nsa=2)
        st = FpState.from_c(c)
        self.assertEqual(sorted(st.scalars), sorted(SCALAR_FIELDS))
        self.assertAlmostEqual(st.scalars["TOTAL_IP"], 1.5)
        self.assertAlmostEqual(st.scalars["STORED_ENERGY"], 5.25)
        self.assertAlmostEqual(st.scalars["COLLISION_POWER"], -0.5)
        self.assertAlmostEqual(st.scalars["PLASMA_VOLUME"], 28.4)

    def test_to_dict_shape(self):
        c = self._populated_state(nr=2, nsa=2)
        d = FpState.from_c(c).to_dict()
        self.assertEqual(d["NRMAX"], 2)
        self.assertEqual(d["NSAMAX"], 2)
        self.assertIn("NPMAX", d)
        self.assertIn("TIMEFP", d)
        # `scalars` mirrors the TrState.to_dict() top-level shape.
        self.assertIsInstance(d["scalars"], dict)
        self.assertAlmostEqual(d["scalars"]["PLASMA_VOLUME"], 28.4)
        self.assertEqual(len(d["profile"]), 2)
        p0 = d["profile"][0]
        self.assertEqual(p0["NSA"], 1)
        for name in ("RNT", "RWT", "RTT", "RJT", "RPCT", "RPWT"):
            self.assertIn(name, p0)
            self.assertEqual(len(p0[name]), 2)  # NRMAX entries

    def test_to_dict_json_serialisable(self):
        import json
        c = self._populated_state(nr=2, nsa=2)
        d = FpState.from_c(c).to_dict()
        # Must round-trip through JSON without custom encoder.
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["NRMAX"], 2)
        self.assertEqual(d2["profile"][0]["NSA"], 1)
        self.assertAlmostEqual(d2["scalars"]["STORED_ENERGY"], 5.25)


# =====================================================================
# Tests that DO need the real libfpapi.so on disk.
# =====================================================================
@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libfpapi.so not built at {DEFAULT_SO}; run `make -C fp libfpapi.so`",
)
class TestFplibLifecycle(unittest.TestCase):
    def test_context_manager(self):
        with Fplib() as fp:
            self.assertFalse(fp.closed)
            self.assertTrue(fp._initialized)
        self.assertTrue(fp.closed)
        self.assertFalse(fp._initialized)

    def test_get_state_returns_dataclass(self):
        with Fplib() as fp:
            st = fp.get_state()
            self.assertIsInstance(st, FpState)
            self.assertIsInstance(st.nrmax, int)
            self.assertIsInstance(st.timefp, float)
            self.assertGreaterEqual(st.nrmax, 0)
            self.assertGreaterEqual(st.nsamax, 0)

    def test_double_close_idempotent(self):
        fp = Fplib()
        fp.close()
        fp.close()  # must not raise
        self.assertTrue(fp.closed)

    def test_call_on_closed_raises(self):
        fp = Fplib()
        fp.close()
        with self.assertRaises(FplibError):
            fp.run(0)
        with self.assertRaises(FplibError):
            fp.get_state()
        with self.assertRaises(FplibError):
            fp.set_param("RR", 1.0)

    def test_set_param_scalar(self):
        with Fplib() as fp:
            # RR = major radius, a commonly registered scalar.
            fp.set_param("RR", 7.5)

    def test_set_param_array_bracket(self):
        with Fplib() as fp:
            fp.set_param("PN[1]", 0.8)
            fp.set_param("PN[2]", 0.4)

    def test_unknown_param_raises(self):
        with Fplib() as fp:
            with self.assertRaises(FplibInvalidParamError):
                fp.set_param("NO_SUCH_VAR", 1.0)

    def test_set_params_bulk_dict_form(self):
        with Fplib() as fp:
            fp.set_params(
                RR=6.5, BB=5.3, NSMAX=3,
                PN={1: 0.8, 2: 0.4, 3: 0.4},
            )

    def test_set_params_bulk_list_form(self):
        with Fplib() as fp:
            # list form -> PN[1]=0.8, PN[2]=0.4, PN[3]=0.4
            fp.set_params(PN=[0.8, 0.4, 0.4])

    def test_set_params_rejects_double_underscore(self):
        with Fplib() as fp:
            with self.assertRaises(FplibError):
                fp.set_params(PN__1=0.5)


if __name__ == "__main__":
    unittest.main()
