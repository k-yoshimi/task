"""Direct ctypes-layer tests for :mod:`totlib._ffi`.

These exercise the FFI without going through the high-level :class:`Tot`
class. They verify that:

* the package imports without a ``libtotapi.so`` on disk (load is lazy),
* :class:`TotStateC` has the expected size and field set,
* :func:`load_library` errors clearly when the .so is missing,
* when ``libtotapi.so`` is present, prototypes are attached and the 6
  symbols resolve,
* the dispatcher routes namespaced calls correctly (eq:/tr:/wr:) and
  rejects unprefixed names with rc=1.

Tests that require the shared library are skipped automatically when
it has not been built yet.
"""
from __future__ import annotations

import ctypes
import os
import sys
import unittest
from pathlib import Path

# Make sure the package is importable when tests are run from the
# repo root with ``python3 -m unittest discover``.
HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]  # .../python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from totlib import _ffi  # noqa: E402


REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tot" / "libtotapi.so"


def _resolved_so() -> Path:
    """Mirror :func:`_ffi._default_lib_path` for skip predicates."""
    env = os.environ.get("TOTLIB_PATH")
    if env:
        return Path(env)
    return DEFAULT_SO


class TestFfiImport(unittest.TestCase):
    """Importing _ffi must not require libtotapi.so on disk."""

    def test_module_imports(self):
        self.assertTrue(hasattr(_ffi, "TotStateC"))
        self.assertTrue(hasattr(_ffi, "load_library"))
        self.assertTrue(hasattr(_ffi, "TOT_NAMESPACES"))

    def test_constants_match_header(self):
        # Must match tot/tot_api.h exactly.
        self.assertEqual(_ffi.TOT_MAX_NRMAX, 500)
        self.assertEqual(_ffi.TOT_MAX_NSMAX, 8)
        self.assertEqual(_ffi.TOT_OK, 0)
        self.assertEqual(_ffi.TOT_ERR_INVALID, 1)
        self.assertEqual(_ffi.TOT_ERR_NOT_INIT, 2)
        self.assertEqual(_ffi.TOT_ERR_CALC_FAILED, 3)
        self.assertEqual(_ffi.TOT_ERR_NOT_IMPL, 4)

    def test_namespace_list(self):
        # Must mirror tot_param_registry.f90's SELECT CASE.
        for ns in ("eq", "tr", "fp", "ti", "wr", "wrx"):
            self.assertIn(ns, _ffi.TOT_NAMESPACES)


class TestTotStateCLayout(unittest.TestCase):
    """Structural checks on the ctypes mirror of ``tot_state_t``."""

    def test_has_expected_fields(self):
        names = [f[0] for f in _ffi.TotStateC._fields_]
        for n in (
            "tr_present", "ti_present", "fp_present", "wr_present",
            "nt", "nrmax", "nsmax",
            "T", "WPT", "AJT", "Q0",
            "BETA0", "BETAP0", "BETAA", "BETAN",
            "TAUE1", "TAUE2", "ZEFF0", "ALI", "RQ1",
            "RN", "RT", "AJ", "QP",
            "AJRFT",   # L-7b-i: end-of-struct, matches ABI v2 layout
        ):
            self.assertIn(n, names, f"missing field {n}")

    def test_size_matches_header_math(self):
        # TOT struct: 4 presence flags + 3 size ints = 7 ints total,
        # then 14 doubles (13 pre-AJRFT scalars + AJRFT), then
        # 2 * NR * NS doubles (RN, RT), then 2 * NR doubles (AJ, QP).
        # Compilers may pad the 7 ints to 28 or 32 bytes, so we
        # accept either of the two natural alignments.
        nr = _ffi.TOT_MAX_NRMAX
        ns = _ffi.TOT_MAX_NSMAX
        exp_core = 14 * 8 + 2 * nr * ns * 8 + 2 * nr * 8
        sz = ctypes.sizeof(_ffi.TotStateC)
        self.assertIn(
            sz,
            (28 + exp_core, 32 + exp_core),
            f"unexpected TotStateC size {sz}",
        )

    def test_array_dimensions(self):
        s = _ffi.TotStateC()
        self.assertEqual(len(s.RN), _ffi.TOT_MAX_NRMAX)
        self.assertEqual(len(s.RN[0]), _ffi.TOT_MAX_NSMAX)
        self.assertEqual(len(s.RT), _ffi.TOT_MAX_NRMAX)
        self.assertEqual(len(s.RT[0]), _ffi.TOT_MAX_NSMAX)
        self.assertEqual(len(s.AJ), _ffi.TOT_MAX_NRMAX)
        self.assertEqual(len(s.QP), _ffi.TOT_MAX_NRMAX)


class TestLoadLibraryMissing(unittest.TestCase):
    """Error-path test that runs whether or not .so exists."""

    def test_load_bogus_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            _ffi.load_library("/nonexistent/path/to/libtotapi.so")

    def test_candidate_paths_listed(self):
        cands = _ffi._candidate_paths()
        self.assertTrue(any(str(p).endswith("tot/libtotapi.so") for p in cands))
        self.assertTrue(any(str(p).endswith("lib/libtotapi.so") for p in cands))


@unittest.skipUnless(
    _resolved_so().exists(),
    f"libtotapi.so not built at {_resolved_so()}; "
    "run `make -C tot libtotapi.so`",
)
class TestLoadLibraryReal(unittest.TestCase):
    """Tests that require the real shared library on disk."""

    def test_load_default(self):
        lib = _ffi.load_library()
        self.assertIsInstance(lib, ctypes.CDLL)
        for sym in (
            "tot_init",
            "tot_run",
            "tot_set_param",
            "tot_set_param_str",
            "tot_get_state",
            "tot_finalize",
        ):
            self.assertTrue(hasattr(lib, sym), f"missing export {sym}")

    def test_prototypes_applied(self):
        lib = _ffi.load_library()
        self.assertEqual(lib.tot_init.restype, ctypes.c_int)
        self.assertEqual(lib.tot_run.argtypes, [ctypes.c_int])
        self.assertEqual(
            lib.tot_set_param.argtypes,
            [ctypes.c_char_p, ctypes.c_double],
        )
        self.assertEqual(
            lib.tot_set_param_str.argtypes,
            [ctypes.c_char_p, ctypes.c_char_p],
        )

    def test_set_param_namespaced_eq_succeeds(self):
        # eq:RR is the canonical smoke parameter (test_run_so.c uses it).
        lib = _ffi.load_library()
        rc = lib.tot_set_param(b"eq:RR", ctypes.c_double(6.5))
        self.assertEqual(rc, _ffi.TOT_OK)

    def test_set_param_namespaced_tr_succeeds(self):
        lib = _ffi.load_library()
        rc = lib.tot_set_param(b"tr:DT", ctypes.c_double(0.001))
        self.assertEqual(rc, _ffi.TOT_OK)

    def test_set_param_missing_prefix_rejected(self):
        # Bare "RR" with no namespace is rejected by the dispatcher.
        lib = _ffi.load_library()
        rc = lib.tot_set_param(b"RR", ctypes.c_double(6.5))
        self.assertEqual(rc, _ffi.TOT_ERR_INVALID)

    def test_set_param_unknown_prefix_rejected(self):
        lib = _ffi.load_library()
        rc = lib.tot_set_param(b"xyz:RR", ctypes.c_double(6.5))
        self.assertEqual(rc, _ffi.TOT_ERR_INVALID)


if __name__ == "__main__":
    unittest.main()
