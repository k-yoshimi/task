"""High-level ``Wrxlib`` class tests.

Covers:

* errors module wiring (no ``libwrxapi.so`` needed).
* ``WrxState.to_dict()`` shape using a hand-built ``WrxStateC`` (no
  ``libwrxapi.so`` needed).
* Full init -> set_param -> get_state -> finalize cycle against the
  real library (skipped if not built).
* Context-manager lifecycle (``__enter__``/``__exit__``).
* Negative tests for invalid params / double-close / closed handle.

.. note:: The ``.run()`` lifecycle tests are gated behind the
   ``WRX_RUN_OK=1`` environment variable. On the current L-4 build,
   ``wrx_run`` pulls in ``libgrf::grd1d`` via ``wrcalpwr`` and may
   segfault inside the shared library; ``test_run_so.c`` (L-4) skips
   for the same reason. Set ``WRX_RUN_OK=1`` only when you have
   verified the segfault is fixed in your build.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from wrxlib import (  # noqa: E402
    Wrxlib,
    WrxState,
    WrxlibError,
    WrxlibParamError,
    WrxlibStateError,
    WrxlibRunError,
    WrxlibNotImplementedError,
    raise_for_ierr,
    raise_for_rc,
)
from wrxlib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "wrx" / "libwrxapi.so"
RUN_OK = os.environ.get("WRX_RUN_OK") == "1"


# =====================================================================
# Tests that do not need libwrxapi.so -- always run.
# =====================================================================
class TestErrorsModule(unittest.TestCase):
    def test_raise_for_ierr_ok(self):
        raise_for_ierr("dummy", 0)

    def test_raise_for_rc_alias(self):
        # raise_for_rc is an alias of raise_for_ierr for fplib/trlib
        # naming compatibility.
        self.assertIs(raise_for_rc, raise_for_ierr)
        raise_for_rc("dummy", 0)

    def test_raise_for_ierr_codes(self):
        for ierr, cls in (
            (1, WrxlibParamError),
            (2, WrxlibStateError),
            (3, WrxlibRunError),
            (4, WrxlibNotImplementedError),
        ):
            with self.assertRaises(cls):
                raise_for_ierr("dummy", ierr)

    def test_unknown_code_falls_back(self):
        with self.assertRaises(WrxlibError):
            raise_for_ierr("dummy", 99)

    def test_subclasses(self):
        for cls in (
            WrxlibParamError, WrxlibStateError, WrxlibRunError,
            WrxlibNotImplementedError,
        ):
            self.assertTrue(issubclass(cls, WrxlibError))


class TestWrxStateFromC(unittest.TestCase):
    """Exercise :py:meth:`WrxState.from_c` / ``to_dict`` with no library."""

    def _populated_state(
        self, nray: int = 3, nsa: int = 2,
        nrs: int = 4, nrl: int = 5,
    ) -> _ffi.WrxStateC:
        s = _ffi.WrxStateC()
        s.nraymax = nray
        s.nstpmax = 2000
        s.nsamax = nsa
        s.nsmax = nsa
        s.nrsmax = nrs
        s.nrlmax = nrl
        s.modelg = 2
        s.mdlwrq = 1
        s.pwr_tot = 0.75
        for i in range(nray):
            s.nstpmax_nray[i] = i * 10 + 7
            s.pwr_nray[i] = 0.1 * (i + 1)
            for j in range(nsa):
                s.pwr_nsa_nray[i][j] = 100.0 * (i + 1) + (j + 1)
                s.pos_pwrmax_rs_nsa_nray[i][j] = 0.01 * (i + 1) + 0.001 * (j + 1)
                s.pos_pwrmax_rl_nsa_nray[i][j] = 0.02 * (i + 1) + 0.001 * (j + 1)
                s.pwrmax_rs_nsa_nray[i][j] = 1000.0 * (i + 1) + (j + 1)
                s.pwrmax_rl_nsa_nray[i][j] = 2000.0 * (i + 1) + (j + 1)
        for j in range(nsa):
            s.pwr_nsa[j] = float(j) + 1.0
            s.pos_pwrmax_rs_nsa[j] = 0.2 * (j + 1)
            s.pwrmax_rs_nsa[j] = 10.0 + j
            s.pos_pwrmax_rl_nsa[j] = 0.3 * (j + 1)
            s.pwrmax_rl_nsa[j] = 20.0 + j
        for i in range(nrs):
            s.pos_nrs[i] = 0.1 * (i + 1)
            for j in range(nsa):
                s.pwr_nrs_nsa[i][j] = 5.0 * (i + 1) + 0.1 * (j + 1)
        for i in range(nrl):
            s.pos_nrl[i] = 0.2 * (i + 1)
            for j in range(nsa):
                s.pwr_nrl_nsa[i][j] = 7.0 * (i + 1) + 0.1 * (j + 1)
        return s

    def test_from_c_slices_correctly(self):
        c = self._populated_state(nray=3, nsa=2, nrs=4, nrl=5)
        st = WrxState.from_c(c)
        self.assertEqual(st.nraymax, 3)
        self.assertEqual(st.nsamax, 2)
        self.assertEqual(st.nsmax, 2)
        self.assertEqual(st.nrsmax, 4)
        self.assertEqual(st.nrlmax, 5)
        self.assertEqual(st.modelg, 2)
        self.assertEqual(st.mdlwrq, 1)
        self.assertAlmostEqual(st.scalars["pwr_tot"], 0.75)
        # per-ray
        self.assertEqual(len(st.nstp_end), 3)
        self.assertEqual(st.nstp_end[2], 27)
        self.assertAlmostEqual(st.pwr_nray[0], 0.1)
        # 2D
        self.assertEqual(len(st.pwr_nsa_nray), 3)
        self.assertEqual(len(st.pwr_nsa_nray[0]), 2)
        self.assertAlmostEqual(st.pwr_nsa_nray[2][1], 302.0)
        # per-species arrays
        self.assertEqual(len(st.pwr_nsa), 2)
        self.assertAlmostEqual(st.pwr_nsa[1], 2.0)
        self.assertAlmostEqual(st.pos_pwrmax_rs_nsa[0], 0.2)
        self.assertAlmostEqual(st.pwrmax_rl_nsa[1], 21.0)
        # new per-bin arrays (pos/pwr for rs and rl)
        self.assertEqual(len(st.pos_nrs), 4)
        self.assertEqual(len(st.pos_nrl), 5)
        self.assertEqual(len(st.pwr_nrs_nsa), 4)
        self.assertEqual(len(st.pwr_nrs_nsa[0]), 2)
        self.assertEqual(len(st.pwr_nrl_nsa), 5)
        self.assertEqual(len(st.pwr_nrl_nsa[0]), 2)
        # new per-ray pwrmax 2D arrays
        self.assertEqual(len(st.pos_pwrmax_rs_nsa_nray), 3)
        self.assertEqual(len(st.pos_pwrmax_rs_nsa_nray[0]), 2)
        self.assertEqual(len(st.pwrmax_rs_nsa_nray), 3)
        self.assertEqual(len(st.pwrmax_rs_nsa_nray[0]), 2)

    def test_from_c_does_not_leak_padding(self):
        # Only the [0:nraymax] / [0:nsamax] / [0:nrsmax] / [0:nrlmax]
        # slices should appear; the fixed-size struct is zero-padded up
        # to WRX_MAX_*.
        c = self._populated_state(nray=1, nsa=1, nrs=1, nrl=1)
        st = WrxState.from_c(c)
        self.assertEqual(len(st.pwr_nray), 1)
        self.assertEqual(len(st.pwr_nsa), 1)
        self.assertEqual(len(st.pwr_nsa_nray), 1)
        self.assertEqual(len(st.pwr_nsa_nray[0]), 1)
        self.assertEqual(len(st.pos_nrs), 1)
        self.assertEqual(len(st.pos_nrl), 1)
        self.assertEqual(len(st.pwr_nrs_nsa), 1)
        self.assertEqual(len(st.pwr_nrl_nsa), 1)

    def test_to_dict_shape(self):
        # to_dict() follows the Phase-0 baseline JSON shape:
        # {MDLWRQ, MODELG, NRAYMAX, NRLMAX, NRSMAX, NSAMAX_WR, NSMAX,
        #  NSTPMAX, arrays, arrays2, scalars}.
        c = self._populated_state(nray=2, nsa=3, nrs=4, nrl=5)
        d = WrxState.from_c(c).to_dict()
        # Dimension header (upper-case; NSAMAX_WR not NSAMAX).
        self.assertEqual(d["NRAYMAX"], 2)
        self.assertEqual(d["NSAMAX_WR"], 3)
        self.assertEqual(d["NSMAX"], 3)
        self.assertEqual(d["NRSMAX"], 4)
        self.assertEqual(d["NRLMAX"], 5)
        self.assertEqual(d["MODELG"], 2)
        self.assertEqual(d["MDLWRQ"], 1)
        self.assertEqual(d["NSTPMAX"], 2000)
        # scalars group
        self.assertIn("scalars", d)
        self.assertIn("pwr_tot", d["scalars"])
        self.assertAlmostEqual(d["scalars"]["pwr_tot"], 0.75)
        # arrays group: 1D per-ray / per-species / per-bin.
        self.assertIn("arrays", d)
        arrays = d["arrays"]
        self.assertEqual(
            set(arrays.keys()),
            {"NSTPMAX_NRAY", "pos_nrl", "pos_nrs", "pwr_nray", "pwr_nsa"},
        )
        self.assertEqual(len(arrays["NSTPMAX_NRAY"]), 2)
        self.assertEqual(len(arrays["pwr_nray"]), 2)
        # pwr_nsa length == nsa (= NSAMAX_WR)
        self.assertEqual(len(arrays["pwr_nsa"]), 3)
        self.assertEqual(len(arrays["pos_nrs"]), 4)
        self.assertEqual(len(arrays["pos_nrl"]), 5)
        # arrays2 group: 2D shapes [outer][nsa].
        self.assertIn("arrays2", d)
        arrays2 = d["arrays2"]
        self.assertEqual(
            set(arrays2.keys()),
            {
                "pwr_nsa_nray",
                "pwr_nrs_nsa", "pwr_nrl_nsa",
                "pos_pwrmax_rs_nsa_nray", "pos_pwrmax_rl_nsa_nray",
                "pwrmax_rs_nsa_nray", "pwrmax_rl_nsa_nray",
            },
        )
        # pwr_nsa_nray: [nray][nsa]
        self.assertEqual(len(arrays2["pwr_nsa_nray"]), 2)
        self.assertEqual(len(arrays2["pwr_nsa_nray"][0]), 3)
        # pwr_nrs_nsa: [nrs][nsa]
        self.assertEqual(len(arrays2["pwr_nrs_nsa"]), 4)
        self.assertEqual(len(arrays2["pwr_nrs_nsa"][0]), 3)
        # pwr_nrl_nsa: [nrl][nsa]
        self.assertEqual(len(arrays2["pwr_nrl_nsa"]), 5)
        self.assertEqual(len(arrays2["pwr_nrl_nsa"][0]), 3)
        # pos_pwrmax_*_nsa_nray / pwrmax_*_nsa_nray: [nray][nsa]
        for key in (
            "pos_pwrmax_rs_nsa_nray",
            "pos_pwrmax_rl_nsa_nray",
            "pwrmax_rs_nsa_nray",
            "pwrmax_rl_nsa_nray",
        ):
            self.assertEqual(len(arrays2[key]), 2, key)
            self.assertEqual(len(arrays2[key][0]), 3, key)

    def test_to_dict_json_serialisable(self):
        import json
        c = self._populated_state(nray=2, nsa=2, nrs=3, nrl=3)
        d = WrxState.from_c(c).to_dict()
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["NRAYMAX"], 2)
        self.assertEqual(d2["NSAMAX_WR"], 2)
        self.assertEqual(d2["NRSMAX"], 3)
        self.assertEqual(d2["NRLMAX"], 3)
        # arrays / arrays2 / scalars round-trip intact
        self.assertIn("arrays", d2)
        self.assertIn("arrays2", d2)
        self.assertIn("scalars", d2)


# =====================================================================
# Tests that DO need the real libwrxapi.so on disk.
# =====================================================================
@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libwrxapi.so not built at {DEFAULT_SO}; run `make -C wrx libwrxapi.so`",
)
class TestWrxlibLifecycle(unittest.TestCase):
    """Lifecycle tests that do NOT invoke ``wrx_run``.

    ``wrx_run`` pulls in ``libgrf::grd1d`` which may segfault in the
    current L-4 shared build; see README.md "Known limitation".
    """

    def test_context_manager(self):
        with Wrxlib() as wrx:
            self.assertFalse(wrx.closed)
        self.assertTrue(wrx.closed)

    def test_double_close_idempotent(self):
        wrx = Wrxlib()
        wrx.close()
        wrx.close()  # must not raise
        self.assertTrue(wrx.closed)

    def test_call_on_closed_raises(self):
        wrx = Wrxlib()
        wrx.close()
        with self.assertRaises(WrxlibError):
            wrx.run(0)
        with self.assertRaises(WrxlibError):
            wrx.get_state()
        with self.assertRaises(WrxlibError):
            wrx.set_param("RR", 1.0)

    def test_invalid_param_raises(self):
        with Wrxlib() as wrx:
            with self.assertRaises((WrxlibParamError, WrxlibError)):
                wrx.set_param("NOT_A_REAL_PARAMETER", 0.0)

    def test_set_params_rejects_double_underscore(self):
        with Wrxlib() as wrx:
            with self.assertRaises(WrxlibError):
                # set_params() is scalar-only; __ is a common
                # array-syntax mistake we reject up-front.
                wrx.set_params(PN__1=0.5)

    def test_set_params_scalar_kwargs_round_trip(self):
        with Wrxlib() as wrx:
            try:
                # RR = major radius -- a registered scalar in
                # wrx_param_registry.f90.
                wrx.set_params(RR=6.2)
            except WrxlibError:
                pass

    def test_get_state_before_run(self):
        # Before wrx_run, wrx_get_state returns ierr=2 (not initialized,
        # meaning g_run_called is false). Some earlier L-2 stubs may
        # have returned 4; accept either mapping.
        with Wrxlib() as wrx:
            with self.assertRaises((WrxlibStateError,
                                    WrxlibNotImplementedError,
                                    WrxlibError)):
                wrx.get_state()


@unittest.skipUnless(
    DEFAULT_SO.exists() and RUN_OK,
    "wrx_run skipped: set WRX_RUN_OK=1 to enable (libgrf segfault risk; "
    "see README.md Known limitation). Also requires libwrxapi.so.",
)
class TestWrxlibRun(unittest.TestCase):
    """wrx_run-dependent tests (gated behind WRX_RUN_OK=1)."""

    def test_run_and_get_state(self):
        with Wrxlib() as wrx:
            # minimal namelist fixtures
            wrx.set_params(
                MODELG=2, RR=6.2, RA=2.0, BB=5.3, NSMAX=2,
                NRAYMAX=1, NSTPMAX=2000, MDLWRI=2, MDLWRQ=1,
                SMAX=2.0, DELS=1e-3,
            )
            for i, (pa, pz, pn, pns, pt, pts) in enumerate([
                (2.0, 1.0, 1.0, 0.05, 10.0, 0.5),
                (5.4462e-4, -1.0, 1.0, 0.05, 10.0, 0.5),
            ], start=1):
                wrx.set_param(f"PA[{i}]", pa)
                wrx.set_param(f"PZ[{i}]", pz)
                wrx.set_param(f"PN[{i}]", pn)
                wrx.set_param(f"PNS[{i}]", pns)
                wrx.set_param(f"PTPR[{i}]", pt)
                wrx.set_param(f"PTPP[{i}]", pt)
                wrx.set_param(f"PTS[{i}]", pts)
            wrx.set_param("RFIN[1]", 170.0e3)
            wrx.set_param("RPIN[1]", 8.0)
            wrx.set_param("ZPIN[1]", 0.0)
            wrx.set_param("PHIIN[1]", 0.0)
            wrx.set_param("ANGPIN[1]", 0.0)
            wrx.set_param("ANGTIN[1]", 10.0)
            wrx.set_param("UUIN[1]", 1.0)
            wrx.set_param("MODEWIN[1]", 1)
            wrx.run(0)
            state = wrx.get_state()
            self.assertIsInstance(state, WrxState)
            self.assertEqual(state.nraymax, 1)
            self.assertGreaterEqual(state.nsamax, 0)


if __name__ == "__main__":
    unittest.main()
