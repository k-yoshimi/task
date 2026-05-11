"""High-level :class:`Tot` class tests.

Covers:

* errors module wiring (no ``libtotapi.so`` needed).
* :py:meth:`TotState.from_c` / :py:meth:`TotState.to_dict` shape using
  a hand-built :class:`TotStateC` (no ``libtotapi.so`` needed).
* Namespace prefix enforcement in :py:meth:`Tot.set_param` and
  :py:meth:`Tot.set_params` (no ``libtotapi.so`` needed for the
  Python-side guard tests).
* Full init -> set_param -> get_state -> finalize cycle against the
  real library (skipped if the .so is not built).
* Context-manager lifecycle (``__enter__`` / ``__exit__``).
* Negative tests for invalid params / double-close / closed handle.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from totlib import (  # noqa: E402
    Tot,
    TotState,
    TotlibError,
    TotlibInvalidParamError,
    TotlibNotInitializedError,
    TotlibCalculationFailedError,
    TotlibNotImplementedError,
    raise_for_rc,
    raise_for_ierr,
)
from totlib import _ffi  # noqa: E402
from totlib.totlib import Tot as _TotForGuards  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tot" / "libtotapi.so"


def _resolved_so() -> Path:
    env = os.environ.get("TOTLIB_PATH")
    if env:
        return Path(env)
    return DEFAULT_SO


# =====================================================================
# Tests that do not need libtotapi.so -- always run.
# =====================================================================
class TestErrorsModule(unittest.TestCase):
    def test_raise_for_rc_ok(self):
        # rc=0 must never raise.
        raise_for_rc("dummy", 0)
        raise_for_ierr("dummy", 0)  # alias

    def test_raise_for_rc_codes(self):
        for rc, cls in (
            (1, TotlibInvalidParamError),
            (2, TotlibNotInitializedError),
            (3, TotlibCalculationFailedError),
            (4, TotlibNotImplementedError),
        ):
            with self.assertRaises(cls):
                raise_for_rc("dummy", rc)

    def test_unknown_code_falls_back(self):
        with self.assertRaises(TotlibError):
            raise_for_rc("dummy", 99)

    def test_subclasses(self):
        for cls in (
            TotlibInvalidParamError,
            TotlibNotInitializedError,
            TotlibCalculationFailedError,
            TotlibNotImplementedError,
        ):
            self.assertTrue(issubclass(cls, TotlibError))


class TestNamespaceGuard(unittest.TestCase):
    """Validate the Python-side namespace prefix guard.

    These tests do not require ``libtotapi.so`` because the guard runs
    before the FFI call. We exercise it through the static method to
    avoid needing a live :class:`Tot` instance.
    """

    def test_missing_prefix_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name("RR")

    def test_empty_string_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name("")

    def test_empty_prefix_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name(":RR")

    def test_empty_bare_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name("eq:")

    def test_unknown_prefix_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name("xyz:RR")

    def test_known_prefixes_accepted(self):
        # Should not raise.
        for ns in ("eq", "tr", "fp", "ti", "wr", "wrx"):
            _TotForGuards._validate_namespaced_name(f"{ns}:RR")

    def test_array_subscript_accepted(self):
        # Subscripts pass through to the per-module registry.
        _TotForGuards._validate_namespaced_name("tr:PN[1]")
        _TotForGuards._validate_namespaced_name("eq:PSIB[0]")

    def test_non_string_rejected(self):
        with self.assertRaises(TotlibInvalidParamError):
            _TotForGuards._validate_namespaced_name(123)  # type: ignore[arg-type]


class TestTotStateFromC(unittest.TestCase):
    """Exercise :py:meth:`TotState.from_c` / ``to_dict`` with no library."""

    def _populated_state(self, nr: int = 3, ns: int = 2):
        s = _ffi.TotStateC()
        s.tr_present = 1
        s.ti_present = 0
        s.fp_present = 0
        s.wr_present = 0
        s.nt = 5
        s.nrmax = nr
        s.nsmax = ns
        s.T = 0.5
        s.WPT = 1.5e6
        s.AJT = 2.0e6
        s.Q0 = 1.05
        s.BETA0 = 0.02
        s.BETAP0 = 0.5
        s.BETAA = 0.01
        s.BETAN = 1.5
        s.TAUE1 = 0.3
        s.TAUE2 = 0.4
        s.ZEFF0 = 1.5
        s.ALI = 0.8
        s.RQ1 = 0.4
        s.AJRFT = 1.5   # L-7b-i
        for i in range(nr):
            s.AJ[i] = float(i) * 100.0
            s.QP[i] = 1.0 + float(i) * 0.5
            for j in range(ns):
                s.RN[i][j] = float(i) + 0.1 * float(j)
                s.RT[i][j] = 1.0 + float(i) + 0.1 * float(j)
        return s

    def test_from_c_slices_correctly(self):
        c = self._populated_state(nr=3, ns=2)
        st = TotState.from_c(c)
        self.assertEqual(st.tr_present, 1)
        self.assertEqual(st.ti_present, 0)
        self.assertEqual(st.nt, 5)
        self.assertEqual(st.nrmax, 3)
        self.assertEqual(st.nsmax, 2)
        self.assertEqual(len(st.AJ), 3)
        self.assertEqual(len(st.QP), 3)
        self.assertEqual(len(st.RN), 3)
        self.assertEqual(len(st.RN[0]), 2)
        self.assertAlmostEqual(st.AJ[2], 200.0)
        self.assertAlmostEqual(st.QP[1], 1.5)
        self.assertAlmostEqual(st.RN[2][1], 2.1)
        self.assertAlmostEqual(st.scalars["Q0"], 1.05)
        self.assertAlmostEqual(st.scalars["WPT"], 1.5e6)
        self.assertAlmostEqual(st.scalars["AJRFT"], 1.5)

    def test_from_c_zero_sizes_yields_empty_profiles(self):
        # At L-3/L-4 stub scope the .so returns nrmax=0 / nsmax=0;
        # profile lists must come back empty rather than full of zeros.
        c = _ffi.TotStateC()
        c.nrmax = 0
        c.nsmax = 0
        st = TotState.from_c(c)
        self.assertEqual(st.RN, [])
        self.assertEqual(st.RT, [])
        self.assertEqual(st.AJ, [])
        self.assertEqual(st.QP, [])

    def test_to_dict_shape(self):
        c = self._populated_state(nr=2, ns=2)
        d = TotState.from_c(c).to_dict()
        self.assertEqual(d["NRMAX"], 2)
        self.assertEqual(d["NSMAX"], 2)
        self.assertEqual(d["NT"], 5)
        self.assertIn("presence", d)
        self.assertEqual(d["presence"]["tr"], 1)
        self.assertEqual(d["presence"]["ti"], 0)
        self.assertIn("Q0", d["scalars"])
        self.assertEqual(len(d["profile"]), 2)
        self.assertEqual(d["profile"][0]["NR"], 1)

    def test_to_dict_json_serialisable(self):
        c = self._populated_state(nr=2, ns=2)
        d = TotState.from_c(c).to_dict()
        s = json.dumps(d)
        d2 = json.loads(s)
        self.assertEqual(d2["NRMAX"], 2)


# =====================================================================
# Tests that DO need the real libtotapi.so on disk.
# =====================================================================
@unittest.skipUnless(
    _resolved_so().exists(),
    f"libtotapi.so not built at {_resolved_so()}; "
    "run `make -C tot libtotapi.so`",
)
class TestTotLifecycle(unittest.TestCase):
    def test_context_manager(self):
        with Tot() as tot:
            self.assertFalse(tot.closed)
        self.assertTrue(tot.closed)

    def test_double_close_idempotent(self):
        tot = Tot()
        tot.close()
        tot.close()  # must not raise
        self.assertTrue(tot.closed)

    def test_call_on_closed_raises(self):
        tot = Tot()
        tot.close()
        with self.assertRaises(TotlibError):
            tot.set_param("eq:RR", 6.2)
        with self.assertRaises(TotlibError):
            tot.set_param_str("tr:KNAMEQ", "x")
        with self.assertRaises(TotlibError):
            tot.run(0)
        with self.assertRaises(TotlibError):
            tot.get_state()


@unittest.skipUnless(
    _resolved_so().exists(),
    f"libtotapi.so not built at {_resolved_so()}; "
    "run `make -C tot libtotapi.so`",
)
class TestTotSetParam(unittest.TestCase):
    def test_namespaced_eq_succeeds(self):
        with Tot() as tot:
            tot.set_param("eq:RR", 6.5)  # canonical smoke parameter

    def test_namespaced_tr_succeeds(self):
        with Tot() as tot:
            tot.set_param("tr:DT", 0.001)

    def test_missing_prefix_raises_invalid(self):
        # Caught by the Python-side guard before the FFI call.
        with Tot() as tot:
            with self.assertRaises(TotlibInvalidParamError):
                tot.set_param("RR", 6.5)

    def test_unknown_prefix_raises_invalid(self):
        with Tot() as tot:
            with self.assertRaises(TotlibInvalidParamError):
                tot.set_param("xyz:RR", 6.5)

    def test_unknown_bare_name_raises_invalid(self):
        # Prefix is valid; bare name is not. Downstream returns rc=1.
        with Tot() as tot:
            with self.assertRaises(TotlibInvalidParamError):
                tot.set_param("eq:NOT_A_REAL_PARAMETER", 0.0)

    def test_set_params_dict(self):
        with Tot() as tot:
            tot.set_params({"eq:RR": 6.5, "tr:DT": 0.001})

    def test_set_params_pairs_iterable(self):
        with Tot() as tot:
            tot.set_params([("eq:RR", 6.5), ("tr:DT", 0.001)])

    def test_set_params_rejects_unprefixed_in_dict(self):
        with Tot() as tot:
            with self.assertRaises(TotlibInvalidParamError):
                tot.set_params({"RR": 6.5})

    def test_set_param_str_known_namespace(self):
        # tr: and eq: have backing string setters; we accept either OK
        # or a clean TotlibError (some bare names may not exist).
        with Tot() as tot:
            try:
                tot.set_param_str("tr:KNAMEQ", "")
            except TotlibError:
                pass

    def test_set_param_str_unsupported_namespace(self):
        # fp / ti / wr / wrx have no string registry yet -> rc=1.
        with Tot() as tot:
            with self.assertRaises(TotlibInvalidParamError):
                tot.set_param_str("fp:KNOTHING", "x")


@unittest.skipUnless(
    _resolved_so().exists(),
    f"libtotapi.so not built at {_resolved_so()}; "
    "run `make -C tot libtotapi.so`",
)
class TestTotRunGetState(unittest.TestCase):
    """L-6 fan-out: ``run`` and ``get_state`` are functional.

    Replaces the L-3/L-4/L-5 ``TestTotRunGetStateStubs`` class which
    pinned the ``TotlibNotImplementedError`` contract. The orchestrator
    now drives the TR transport solver internally; ti / fp / wr are
    init'd but their state is not yet aggregated into ``tot_state_c``
    (follow-up).
    """

    def test_run_zero_steps_is_ok(self):
        # ntmax=0 is a valid no-op (proves the fan-out is wired without
        # touching the inner loop body).
        with Tot() as tot:
            tot.run(0)

    def test_get_state_returns_tr_authoritative_block(self):
        # After init the TR-authoritative slots must be populated:
        # NRMAX defaults to 50 and NSMAX defaults to 2 (see
        # tr/trinit.f90). Doing this without a prior run still gives a
        # valid state because tr_api_init pre-populates default sizes.
        with Tot() as tot:
            tot.run(0)
            state = tot.get_state()
        self.assertEqual(state.tr_present, 1)
        self.assertGreater(state.nrmax, 0)
        self.assertGreater(state.nsmax, 0)


if __name__ == "__main__":
    unittest.main()
