"""High-level :py:meth:`Trlib.validate` tests (Issue #143 pilot wrapper).

Mirrors ``python/eqlib/tests/test_validate.py``. Exercises the
supported Python surface introduced in the tr side of the #143 pilot.

Tests cover:

* the contract that constructing :class:`Trlib` auto-initialises the
  library, so ``validate()`` after ``Trlib()`` always sees an
  initialised state — the raw-ctypes "before init" smoke test is not
  reachable through the wrapper;
* clean-default state after ``Trlib()`` returns an empty list;
* OUT_OF_RANGE diagnostic fires for ``NSMAX`` above ``NSM=4`` (compile
  max in ``tr/trcom0.f90``). The registry accepts NSMAX up to 8 (C
  ABI capacity), so 5..8 exercise the gap between the registry
  bound and the TRCOM0 compile-time bound that validate guards.
* FILE_MISSING diagnostic fires when ``MODELG=3`` and ``KNAMEQ`` is
  blank (mirrors eq_api_validate).

Skipped automatically when ``libtrapi.so`` has not been built.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import (  # noqa: E402
    Trlib,
    TrDiagCode,
    TrDiagEntryPy,
    TrlibStateError,
)
from trlib import _ffi  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
class TestTrValidate(unittest.TestCase):
    """High-level :py:meth:`Trlib.validate` (Issue #143 pilot)."""

    def test_validate_after_close_raises_not_init(self) -> None:
        """Regression for the ierr=2 (NOT_INIT) path.

        :class:`Trlib` auto-initialises in ``__init__``, so the raw-
        ctypes "validate before init" scenario is unreachable through
        the wrapper. The closest user-visible equivalent is calling
        ``validate`` after ``close()``: the library is no longer
        initialised, and the wrapper raises :class:`TrlibStateError`
        (mapped from ierr==2).
        """
        tr = Trlib()
        tr.close()
        # Manually flip _closed back to False so validate() does not
        # short-circuit on the Python guard ("validate on closed Trlib")
        # and instead exercises the underlying NOT_INIT contract from
        # the C library. Keeps the test honest about what Fortran
        # returns when g_initialized == .FALSE.
        tr._closed = False  # noqa: SLF001 - regression hook
        try:
            with self.assertRaises(TrlibStateError):
                tr.validate()
        finally:
            tr._closed = True  # noqa: SLF001

    def test_validate_clean_default_state_returns_empty_list(self) -> None:
        with Trlib() as tr:
            diags = tr.validate()
        self.assertEqual(diags, [], "default tr state should validate cleanly")

    def test_validate_nsmax_overflow_emits_out_of_range(self) -> None:
        with Trlib() as tr:
            # Registry accepts NSMAX in [2, 8]; NSM compile-time max
            # is 4 (tr/trcom0.f90:11). 5..8 fit in the registry bound
            # but overflow NSM, so validate catches it.
            tr.set_param("NSMAX", 6.0)
            diags = tr.validate()

        nsmax_diags = [d for d in diags if d.param == "NSMAX"]
        self.assertEqual(len(nsmax_diags), 1)
        e0 = nsmax_diags[0]
        self.assertIsInstance(e0, TrDiagEntryPy)
        self.assertEqual(e0.code, TrDiagCode.OUT_OF_RANGE)
        self.assertIn("6", e0.message)

    def test_validate_modelg3_blank_knameq_emits_file_missing(self) -> None:
        with Trlib() as tr:
            # tr_init defaults keep KNAMEQ='eqdata'; switch MODELG to
            # one of the file-dependent modes and blank out KNAMEQ.
            tr.set_param("MODELG", 3.0)
            tr.set_param_str("KNAMEQ", "")
            diags = tr.validate()

        codes = [d.code for d in diags]
        self.assertIn(
            int(TrDiagCode.FILE_MISSING), codes,
            f"expected FILE_MISSING (code {int(TrDiagCode.FILE_MISSING)}) "
            f"in {codes}",
        )
        knameq_diags = [
            d for d in diags
            if d.code == TrDiagCode.FILE_MISSING and d.param == "KNAMEQ"
        ]
        self.assertEqual(len(knameq_diags), 1)

    def test_validate_modelg7_blank_knameq_emits_file_missing(self) -> None:
        """Regression for Codex review P2: MODELG=7 (VMEC via
        ``tr_set_metric -> pl_vmec``) also takes KNAMEQ as the input
        filename, so validate must catch the blank case there too."""
        with Trlib() as tr:
            tr.set_param("MODELG", 7.0)
            tr.set_param_str("KNAMEQ", "")
            diags = tr.validate()

        knameq_diags = [
            d for d in diags
            if d.code == TrDiagCode.FILE_MISSING and d.param == "KNAMEQ"
        ]
        self.assertEqual(len(knameq_diags), 1)


class TestFFIBindings(unittest.TestCase):
    """Smoke tests for the new _ffi exports (no .so needed)."""

    def test_diag_constants_match_c_header(self) -> None:
        # Mirror the values from tr/tr_api.h enum tr_diag_code.
        self.assertEqual(_ffi.TR_DIAG_OUT_OF_RANGE, 1)
        self.assertEqual(_ffi.TR_DIAG_INCONSISTENT_PAIR, 2)
        self.assertEqual(_ffi.TR_DIAG_OUT_OF_RANGE_AFTER_DEP, 3)
        self.assertEqual(_ffi.TR_DIAG_FILE_MISSING, 4)
        self.assertEqual(_ffi.TR_DIAG_MISSING_REQUIRED, 5)
        self.assertEqual(_ffi.TR_DIAG_PARAM_LEN, 64)
        self.assertEqual(_ffi.TR_DIAG_MSG_LEN, 128)

    def test_diag_struct_layout(self) -> None:
        # param[64] + int + msg[128] = 64 + 4 + 128 = 196 bytes (plus
        # potential trailing padding for 4-byte alignment, which is a
        # no-op here since 196 is already 4-aligned).
        import ctypes
        self.assertEqual(ctypes.sizeof(_ffi.TrDiagEntry), 64 + 4 + 128)

    def test_tr_diag_code_enum_matches_ffi(self) -> None:
        self.assertEqual(TrDiagCode.OUT_OF_RANGE, _ffi.TR_DIAG_OUT_OF_RANGE)
        self.assertEqual(TrDiagCode.FILE_MISSING, _ffi.TR_DIAG_FILE_MISSING)
        self.assertEqual(
            TrDiagCode.MISSING_REQUIRED, _ffi.TR_DIAG_MISSING_REQUIRED
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
