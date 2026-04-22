"""Pre-run parameter validation API smoke tests (Issue #143 pilot).

Exercises ``eq_validate`` through the FFI directly because the
high-level :class:`Eq` wrapper does not yet expose the validate
surface (Python wrapper coverage arrives in a follow-up PR).

Tests cover:

* validate-before-init returns NOT_INIT (rc=2) and ndiag=0,
* clean-default state after eq_init returns rc=0 / ndiag=0,
* OUT_OF_RANGE diagnostic fires for ``NRMAX`` above ``NRM=1001``,
* FILE_MISSING diagnostic fires when ``MODELG=3`` and ``KNAMEQ`` is
  blank.

Skipped automatically when ``libeqapi.so`` has not been built.
"""
from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eqlib import _ffi  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "eq" / "libeqapi.so"

# Mirror eq_state.f90::EQ_DIAG_PARAM_LEN / EQ_DIAG_MSG_LEN.
_DIAG_PARAM_LEN = 64
_DIAG_MSG_LEN = 128
# Mirror eq_api.h::eq_diag_code values.
_DIAG_OUT_OF_RANGE = 1
_DIAG_FILE_MISSING = 4
# Mirror eq_api.h::eq_error.
_EQ_OK = 0
_EQ_ERR_INVALID = 1
_EQ_ERR_NOT_INIT = 2


class _DiagEntry(ctypes.Structure):
    _fields_ = [
        ("param", ctypes.c_char * _DIAG_PARAM_LEN),
        ("code", ctypes.c_int),
        ("msg", ctypes.c_char * _DIAG_MSG_LEN),
    ]


def _attach_validate(lib):
    """Add eq_validate prototype to the FFI handle (one-shot)."""
    lib.eq_validate.argtypes = [
        ctypes.POINTER(_DiagEntry),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.eq_validate.restype = ctypes.c_int
    lib.eq_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.eq_set_param_str.restype = ctypes.c_int


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libeqapi.so not built at {DEFAULT_SO}; run `make -C eq libeqapi.so`",
)
class TestEqValidate(unittest.TestCase):
    """Pre-run cross-parameter validation (Issue #143 pilot)."""

    def setUp(self) -> None:
        self.lib = _ffi.load_library()
        _attach_validate(self.lib)
        self.buf = (_DiagEntry * 32)()
        self.ndiag = ctypes.c_int(0)

    def tearDown(self) -> None:
        # Idempotent finalize: safe even if eq_init was not called.
        try:
            self.lib.eq_finalize()
        except Exception:
            pass

    def _validate(self) -> int:
        return self.lib.eq_validate(
            self.buf, len(self.buf), ctypes.byref(self.ndiag)
        )

    def test_validate_before_init_returns_not_init(self) -> None:
        rc = self._validate()
        self.assertEqual(rc, _EQ_ERR_NOT_INIT)
        self.assertEqual(self.ndiag.value, 0)

    def test_validate_clean_default_state_returns_ok(self) -> None:
        self.assertEqual(self.lib.eq_init(), _EQ_OK)
        rc = self._validate()
        self.assertEqual(rc, _EQ_OK, "default eq state should validate cleanly")
        self.assertEqual(self.ndiag.value, 0)

    def test_validate_nrmax_overflow_emits_out_of_range(self) -> None:
        self.assertEqual(self.lib.eq_init(), _EQ_OK)
        # NRM compile-time max is 1001 (eq/eqcom0_mod.f90:29).
        self.lib.eq_set_param(b"NRMAX", 9999.0)
        rc = self._validate()
        self.assertEqual(rc, _EQ_ERR_INVALID)
        self.assertGreaterEqual(self.ndiag.value, 1)
        e0 = self.buf[0]
        self.assertEqual(e0.param.decode().rstrip("\x00"), "NRMAX")
        self.assertEqual(e0.code, _DIAG_OUT_OF_RANGE)
        self.assertIn("9999", e0.msg.decode().rstrip("\x00"))

    def test_validate_modelg3_blank_knameq_emits_file_missing(self) -> None:
        self.assertEqual(self.lib.eq_init(), _EQ_OK)
        # eq_init defaults are MODELG=2 / KNAMEQ='eqdata'; switch to a
        # MODELG that requires a file and clear KNAMEQ.
        self.lib.eq_set_param(b"MODELG", 3.0)
        self.lib.eq_set_param_str(b"KNAMEQ", b"")
        rc = self._validate()
        self.assertEqual(rc, _EQ_ERR_INVALID)
        codes = [self.buf[i].code for i in range(self.ndiag.value)]
        self.assertIn(
            _DIAG_FILE_MISSING, codes,
            f"expected FILE_MISSING (code {_DIAG_FILE_MISSING}) in {codes}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
