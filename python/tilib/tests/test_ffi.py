"""Direct ctypes-layer tests.

These exercise :mod:`tilib._ffi` without going through the high-level
``TiLib`` class. They verify that:

* the package imports without a libtiapi.so on disk (load is lazy),
* :class:`TiStateC` has the expected size and layout,
* :func:`load_library` errors clearly when the .so is missing,
* when libtiapi.so **is** present, prototypes are attached and the 5
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

from tilib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "ti" / "libtiapi.so"


class TestFfiImport(unittest.TestCase):
    """Importing _ffi must not require libtiapi.so on disk."""

    def test_module_imports(self):
        self.assertTrue(hasattr(_ffi, "TiStateC"))
        self.assertTrue(hasattr(_ffi, "load_library"))

    def test_constants_match_header(self):
        # Must match ti/ti_api.h exactly.
        self.assertEqual(_ffi.TI_MAX_NRMAX, 200)
        self.assertEqual(_ffi.TI_MAX_NSA_MAX, 20)
        self.assertEqual(_ffi.TI_OK, 0)
        self.assertEqual(_ffi.TI_ERR_INVALID, 1)
        self.assertEqual(_ffi.TI_ERR_NOT_INIT, 2)
        self.assertEqual(_ffi.TI_ERR_CALC_FAILED, 3)
        self.assertEqual(_ffi.TI_ERR_NOT_IMPL, 4)


class TestTiStateCLayout(unittest.TestCase):
    """Structural checks on the ctypes mirror of ``ti_state_t``."""

    def test_has_expected_fields(self):
        names = [f[0] for f in _ffi.TiStateC._fields_]
        for n in (
            "nt", "nrmax", "nsa_max", "nsmax",
            "T", "residual_loop_max",
            "icount_loop_max", "icount_mat_max",
            "RNA", "RTA", "RUA",
            "RBP", "RQP", "RJP",
            "ZEFF", "BETA", "BETAP",
        ):
            self.assertIn(n, names, f"missing field {n}")

    def test_size_matches_header_math(self):
        # 6 ints (nt/nrmax/nsa_max/nsmax/icount_loop_max/icount_mat_max)
        # + 2 doubles (T, residual_loop_max)
        # + 3 * NR*NSA doubles (RNA/RTA/RUA)
        # + 6 * NR doubles (RBP/RQP/RJP/ZEFF/BETA/BETAP).
        #
        # The compiler may pad scalar blocks; we check the sum matches
        # the minimum and that size is a multiple of 8.
        nr = _ffi.TI_MAX_NRMAX
        nsa = _ffi.TI_MAX_NSA_MAX
        doubles_bytes = 2 * 8 + 3 * nr * nsa * 8 + 6 * nr * 8
        ints_bytes = 6 * 4
        min_size = ints_bytes + doubles_bytes
        sz = ctypes.sizeof(_ffi.TiStateC)
        # Allow the layout to match exactly or with up to 4 bytes of
        # trailing padding (most platforms will need zero extra).
        self.assertGreaterEqual(sz, min_size, f"TiStateC size {sz} below minimum {min_size}")
        self.assertLessEqual(sz, min_size + 8, f"TiStateC size {sz} too large (min {min_size})")
        self.assertEqual(sz % 8, 0, f"TiStateC size {sz} not 8-byte aligned")

    def test_profile_array_dimensions(self):
        # RNA / RTA / RUA: [NRMAX][NSA_MAX] row-major in C, equivalent
        # to Fortran (NSA_MAX, NRMAX) column-major -- same memory layout.
        s = _ffi.TiStateC()
        # First index has NRMAX entries, second has NSA_MAX.
        self.assertEqual(len(s.RNA), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.RNA[0]), _ffi.TI_MAX_NSA_MAX)
        self.assertEqual(len(s.RBP), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.RQP), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.RJP), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.ZEFF), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.BETA), _ffi.TI_MAX_NRMAX)
        self.assertEqual(len(s.BETAP), _ffi.TI_MAX_NRMAX)


class TestLoadLibraryMissing(unittest.TestCase):
    """Error-path test that runs whether or not .so exists."""

    def test_load_bogus_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            _ffi.load_library("/nonexistent/path/to/libtiapi.so")

    def test_candidate_paths_listed(self):
        cands = _ffi._candidate_paths()
        self.assertTrue(any(str(p).endswith("ti/libtiapi.so") for p in cands))
        self.assertTrue(any(str(p).endswith("lib/libtiapi.so") for p in cands))


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtiapi.so not built at {DEFAULT_SO}; run `make -C ti libtiapi.so`",
)
class TestLoadLibraryReal(unittest.TestCase):
    """Tests that require the real shared library on disk."""

    def test_load_default(self):
        lib = _ffi.load_library()
        self.assertIsInstance(lib, ctypes.CDLL)
        for sym in (
            "ti_init", "ti_run", "ti_set_param", "ti_get_state", "ti_finalize"
        ):
            self.assertTrue(hasattr(lib, sym), f"missing export {sym}")

    def test_env_override(self):
        old = os.environ.get("TILIB_PATH")
        os.environ["TILIB_PATH"] = str(DEFAULT_SO)
        try:
            lib = _ffi.load_library()
            self.assertIsInstance(lib, ctypes.CDLL)
        finally:
            if old is None:
                os.environ.pop("TILIB_PATH", None)
            else:
                os.environ["TILIB_PATH"] = old

    def test_prototypes_applied(self):
        lib = _ffi.load_library()
        self.assertEqual(lib.ti_init.restype, ctypes.c_int)
        self.assertEqual(lib.ti_run.argtypes, [ctypes.c_int])
        self.assertEqual(
            lib.ti_set_param.argtypes,
            [ctypes.c_char_p, ctypes.c_double],
        )


if __name__ == "__main__":
    unittest.main()
