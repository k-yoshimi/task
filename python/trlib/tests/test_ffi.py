"""Direct ctypes-layer tests.

These exercise :mod:`trlib._ffi` without going through the high-level
``Trlib`` class. They verify that:

* the package imports without a libtrapi.so on disk (load is lazy),
* :class:`TrStateC` has the expected size and layout,
* :func:`load_library` errors clearly when the .so is missing,
* when libtrapi.so **is** present, prototypes are attached and the 5
  symbols resolve.

Tests that require the shared library are skipped automatically when
it has not been built yet.
"""
from __future__ import annotations

import ctypes
import os
import unittest
from pathlib import Path

# Make sure the package is importable when tests are run from the
# repo root with ``python3 -m unittest discover``.
import sys
HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


class TestFfiImport(unittest.TestCase):
    """Importing _ffi must not require libtrapi.so on disk."""

    def test_module_imports(self):
        self.assertTrue(hasattr(_ffi, "TrStateC"))
        self.assertTrue(hasattr(_ffi, "load_library"))

    def test_constants_match_header(self):
        # Must match tr/tr_api.h exactly.
        self.assertEqual(_ffi.TR_MAX_NRMAX, 500)
        self.assertEqual(_ffi.TR_MAX_NSMAX, 8)
        self.assertEqual(_ffi.TR_OK, 0)
        self.assertEqual(_ffi.TR_ERR_INVALID, 1)
        self.assertEqual(_ffi.TR_ERR_NOT_INIT, 2)
        self.assertEqual(_ffi.TR_ERR_CALC_FAILED, 3)
        self.assertEqual(_ffi.TR_ERR_NOT_IMPL, 4)


class TestTrStateCLayout(unittest.TestCase):
    """Structural checks on the ctypes mirror of ``tr_state_t``."""

    def test_has_expected_fields(self):
        names = [f[0] for f in _ffi.TrStateC._fields_]
        for n in (
            "nt", "nrmax", "nsmax",
            "T", "WPT", "AJT", "Q0",
            "BETA0", "BETAP0", "BETAA", "BETAN",
            "TAUE1", "TAUE2", "ZEFF0", "ALI", "RQ1",
            "RN", "RT", "AJ", "QP",
            "AJRFT",   # L-7b-i
        ):
            self.assertIn(n, names, f"missing field {n}")

    def test_size_matches_header_math(self):
        # 3 ints + 14 doubles (scalars: 13 + AJRFT) + 2 * NR*NS doubles
        # + 2 * NR doubles. Compilers may pad the 3 ints to 16 bytes,
        # so we accept either 12 or 16 bytes for the int block.
        nr = _ffi.TR_MAX_NRMAX
        ns = _ffi.TR_MAX_NSMAX
        exp_core = 14 * 8 + 2 * nr * ns * 8 + 2 * nr * 8
        sz = ctypes.sizeof(_ffi.TrStateC)
        self.assertIn(
            sz,
            (12 + exp_core, 16 + exp_core),
            f"unexpected TrStateC size {sz}",
        )

    def test_profile_array_dimensions(self):
        # RN / RT: [NRMAX][NSMAX] row-major in C, equivalent to Fortran
        # RN(NSMAX, NRMAX) column-major -- same memory layout.
        s = _ffi.TrStateC()
        # First index has NRMAX entries, second has NSMAX.
        self.assertEqual(len(s.RN), _ffi.TR_MAX_NRMAX)
        self.assertEqual(len(s.RN[0]), _ffi.TR_MAX_NSMAX)
        self.assertEqual(len(s.AJ), _ffi.TR_MAX_NRMAX)
        self.assertEqual(len(s.QP), _ffi.TR_MAX_NRMAX)


class TestLoadLibraryMissing(unittest.TestCase):
    """Error-path test that runs whether or not .so exists."""

    def test_load_bogus_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            _ffi.load_library("/nonexistent/path/to/libtrapi.so")

    def test_candidate_paths_listed(self):
        cands = _ffi._candidate_paths()
        self.assertTrue(any(str(p).endswith("tr/libtrapi.so") for p in cands))
        self.assertTrue(any(str(p).endswith("lib/libtrapi.so") for p in cands))


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
class TestLoadLibraryReal(unittest.TestCase):
    """Tests that require the real shared library on disk."""

    def test_load_default(self):
        lib = _ffi.load_library()
        self.assertIsInstance(lib, ctypes.CDLL)
        for sym in (
            "tr_init", "tr_run", "tr_set_param", "tr_get_state", "tr_finalize"
        ):
            self.assertTrue(hasattr(lib, sym), f"missing export {sym}")

    def test_env_override(self):
        old = os.environ.get("TRLIB_PATH")
        os.environ["TRLIB_PATH"] = str(DEFAULT_SO)
        try:
            lib = _ffi.load_library()
            self.assertIsInstance(lib, ctypes.CDLL)
        finally:
            if old is None:
                os.environ.pop("TRLIB_PATH", None)
            else:
                os.environ["TRLIB_PATH"] = old

    def test_prototypes_applied(self):
        lib = _ffi.load_library()
        self.assertEqual(lib.tr_init.restype, ctypes.c_int)
        self.assertEqual(lib.tr_run.argtypes, [ctypes.c_int])
        self.assertEqual(
            lib.tr_set_param.argtypes,
            [ctypes.c_char_p, ctypes.c_double],
        )


if __name__ == "__main__":
    unittest.main()
