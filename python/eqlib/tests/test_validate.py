"""High-level :py:meth:`Eq.validate` tests (Issue #143 pilot wrapper).

Exercises the supported Python surface introduced in the
``feat/eqlib-validate-python-wrapper`` PR. The same scenarios were
previously covered against raw ctypes; that path is preserved by the
underlying _ffi prototype but the user-facing tests now go through
:class:`Eq` so the coverage tracks the API contract.

Tests cover:

* the contract that constructing :class:`Eq` auto-initialises the
  library, so ``validate()`` after ``Eq()`` always sees an initialised
  state (the raw-ctypes "before init" smoke test is documented as a
  regression below — there is no Python entry point that lets a caller
  call validate before init without going around the wrapper);
* clean-default state after ``Eq()`` returns an empty list;
* OUT_OF_RANGE diagnostic fires for ``NRMAX`` above ``NRM=1001``;
* FILE_MISSING diagnostic fires when ``MODELG=3`` and ``KNAMEQ`` is
  blank.

Skipped automatically when ``libeqapi.so`` has not been built.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eqlib import (  # noqa: E402
    Eq,
    EqDiagCode,
    EqDiagEntryPy,
    EqlibNotInitializedError,
)
from eqlib import _ffi  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "eq" / "libeqapi.so"


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libeqapi.so not built at {DEFAULT_SO}; run `make -C eq libeqapi.so`",
)
class TestEqValidate(unittest.TestCase):
    """High-level :py:meth:`Eq.validate` (Issue #143 pilot)."""

    def test_validate_after_close_raises_not_init(self) -> None:
        """Regression for the rc=2 (NOT_INIT) path.

        :class:`Eq` auto-initialises in ``__init__``, so the raw-ctypes
        "validate before init" scenario is unreachable through the
        wrapper. The closest user-visible equivalent is calling
        ``validate`` after ``close()``: the library is no longer
        initialised, and the wrapper raises
        :class:`EqlibNotInitializedError` (mapped from rc==2).
        """
        eq = Eq()
        eq.close()
        # Manually flip _closed back to False so validate() does not
        # short-circuit on the Python guard ("validate on closed Eq")
        # and instead exercises the underlying NOT_INIT contract from
        # the C library. This keeps the test honest about what the
        # Fortran side returns when g_initialized == .FALSE.
        eq._closed = False  # noqa: SLF001 - regression hook
        try:
            with self.assertRaises(EqlibNotInitializedError):
                eq.validate()
        finally:
            eq._closed = True  # noqa: SLF001

    def test_validate_clean_default_state_returns_empty_list(self) -> None:
        with Eq() as eq:
            diags = eq.validate()
        self.assertEqual(diags, [], "default eq state should validate cleanly")

    def test_validate_nrmax_overflow_emits_out_of_range(self) -> None:
        with Eq() as eq:
            # NRM compile-time max is 1001 (eq/eqcom0_mod.f90:29).
            eq.set_param("NRMAX", 9999.0)
            diags = eq.validate()

        self.assertGreaterEqual(len(diags), 1)
        e0 = diags[0]
        self.assertIsInstance(e0, EqDiagEntryPy)
        self.assertEqual(e0.param, "NRMAX")
        self.assertEqual(e0.code, EqDiagCode.OUT_OF_RANGE)
        self.assertIn("9999", e0.message)

    def test_validate_modelg3_blank_knameq_emits_file_missing(self) -> None:
        with Eq() as eq:
            # eq_init defaults are MODELG=2 / KNAMEQ='eqdata'; switch to
            # a MODELG that requires a file and clear KNAMEQ.
            eq.set_param("MODELG", 3.0)
            eq.set_param_str("KNAMEQ", "")
            diags = eq.validate()

        codes = [d.code for d in diags]
        self.assertIn(
            int(EqDiagCode.FILE_MISSING), codes,
            f"expected FILE_MISSING (code {int(EqDiagCode.FILE_MISSING)}) "
            f"in {codes}",
        )
        # The FILE_MISSING entry should refer to KNAMEQ specifically.
        knameq_diags = [
            d for d in diags
            if d.code == EqDiagCode.FILE_MISSING and d.param == "KNAMEQ"
        ]
        self.assertEqual(len(knameq_diags), 1)


class TestFFIBindings(unittest.TestCase):
    """Smoke tests for the new _ffi exports (no .so needed)."""

    def test_diag_constants_match_c_header(self) -> None:
        # Mirror the values from eq/eq_api.h enum eq_diag_code.
        self.assertEqual(_ffi.EQ_DIAG_OUT_OF_RANGE, 1)
        self.assertEqual(_ffi.EQ_DIAG_INCONSISTENT_PAIR, 2)
        self.assertEqual(_ffi.EQ_DIAG_OUT_OF_RANGE_AFTER_DEP, 3)
        self.assertEqual(_ffi.EQ_DIAG_FILE_MISSING, 4)
        self.assertEqual(_ffi.EQ_DIAG_MISSING_REQUIRED, 5)
        self.assertEqual(_ffi.EQ_DIAG_PARAM_LEN, 64)
        self.assertEqual(_ffi.EQ_DIAG_MSG_LEN, 128)

    def test_diag_struct_layout(self) -> None:
        # param[64] + int + msg[128] = 64 + 4 + 128 = 196 bytes (plus
        # potential trailing padding for 4-byte alignment, which is a
        # no-op here since 196 is already 4-aligned).
        import ctypes
        self.assertEqual(ctypes.sizeof(_ffi.EqDiagEntry), 64 + 4 + 128)

    def test_eq_diag_code_enum_matches_ffi(self) -> None:
        self.assertEqual(EqDiagCode.OUT_OF_RANGE, _ffi.EQ_DIAG_OUT_OF_RANGE)
        self.assertEqual(EqDiagCode.FILE_MISSING, _ffi.EQ_DIAG_FILE_MISSING)
        self.assertEqual(
            EqDiagCode.MISSING_REQUIRED, _ffi.EQ_DIAG_MISSING_REQUIRED
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
