"""Low-level ctypes FFI for libfpapi.so (``libfpapi.dll`` on Windows).

Mirrors ``fp/fp_api.h`` (C ABI). Higher-level helpers live in
``fplib.py``; this module intentionally exposes only raw ctypes objects
so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

0. ``MONO_LIB_PATH`` env var (#208 PR-A): if set, all wrappers route
   to the same monolithic image so eq/tr/etc. share one BPSD broker.
1. explicit ``path`` argument to :func:`load_library`
2. ``FPLIB_PATH`` environment variable
3. ``<repo>/fp/libfpapi.so`` (standard L-4 build location; ``libfpapi.dll``
   on Windows)
4. ``<repo>/lib/libfpapi.so`` (install-style location, future-proofing;
   ``libfpapi.dll`` on Windows)

The package layout is ``python/fplib/_ffi.py`` so the repository root is
two parents above this file (``__file__.parents[2]``).
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional

from _runtime_mode import mono_lib_path

# Optional numpy (we never require it; state.py uses lists).
try:
    import numpy as _np  # noqa: F401
    HAS_NUMPY = True
except ImportError:  # pragma: no cover - numpy is optional
    HAS_NUMPY = False


# ---------------------------------------------------------------------
# Layout constants. Must match fp/fp_api.h exactly.
# ---------------------------------------------------------------------
FP_MAX_NRMAX = 100
FP_MAX_NSAMAX = 8


# ---------------------------------------------------------------------
# Error codes (kept in sync with fp_api.h::enum fp_error).
# ---------------------------------------------------------------------
FP_OK = 0
FP_ERR_INVALID = 1
FP_ERR_NOT_INIT = 2
FP_ERR_CALC_FAILED = 3
FP_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# ctypes mirror of fp_state_t from fp/fp_api.h.
#
# Memory-layout note (also in fp_api.h):
#   In C, RNT[NSAMAX][NRMAX] is row-major.
#   In Fortran the matching declaration is RNT(NRMAX, NSAMAX) column-major.
#   Both lay out the same bytes; only the index order differs.
# ---------------------------------------------------------------------
_PROFILE_2D = (ctypes.c_double * FP_MAX_NRMAX) * FP_MAX_NSAMAX


class FpStateC(ctypes.Structure):
    _fields_ = [
        ("nrmax", ctypes.c_int),
        ("nsamax", ctypes.c_int),
        ("npmax", ctypes.c_int),
        ("nthmax", ctypes.c_int),
        ("ntg2", ctypes.c_int),
        ("timefp", ctypes.c_double),
        ("RNT", _PROFILE_2D),
        ("RWT", _PROFILE_2D),
        ("RTT", _PROFILE_2D),
        ("RJT", _PROFILE_2D),
        ("RPCT", _PROFILE_2D),
        ("RPWT", _PROFILE_2D),
    ]


# ---------------------------------------------------------------------
# Library loader.
# ---------------------------------------------------------------------
def _repo_root() -> Path:
    """Return the repository root (two parents up from this file)."""
    return Path(__file__).resolve().parents[2]


# Handles returned by os.add_dll_directory, keyed by directory. Kept so each
# directory is registered once however often a library is opened (the MCP
# servers build a fresh library handle after every finalize), and so it
# could later be removed with close(). Dropping a handle does NOT unregister
# its directory. A directory enters the dict only after a library loaded
# from it; a load that fails closes the handle it had just made.
_DLL_DIR_HANDLES: dict = {}


def _lib_filename() -> str:
    """``libfpapi.dll`` on Windows, ``libfpapi.so`` everywhere else.

    macOS keeps the ``.so`` name because that is what ``make libfpapi.so``
    produces there, even though the file is a Mach-O dylib.
    """
    return "libfpapi.dll" if sys.platform == "win32" else "libfpapi.so"


def _candidate_paths() -> list:
    """All library paths that :func:`load_library` will try in order."""
    root = _repo_root()
    name = _lib_filename()
    return [root / "fp" / name, root / "lib" / name]


def _default_lib_path() -> Path:
    """Resolve the default ``libfpapi.so`` path (``libfpapi.dll`` on Windows).

    Priority (highest first):
      0. ``mono_lib_path()`` — global mono override (``MONO_LIB_PATH``)
      1. ``FPLIB_PATH`` env var
      2. ``<repo>/fp/libfpapi.so``
      3. ``<repo>/lib/libfpapi.so``
    """
    mono = mono_lib_path()
    if mono is not None:
        return mono
    env = os.environ.get("FPLIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 5 exported C ABI symbols."""
    lib.fp_init.restype = ctypes.c_int
    lib.fp_init.argtypes = []

    lib.fp_run.restype = ctypes.c_int
    lib.fp_run.argtypes = [ctypes.c_int]

    lib.fp_set_param.restype = ctypes.c_int
    lib.fp_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    if hasattr(lib, "fp_set_param_str"):
        lib.fp_set_param_str.restype = ctypes.c_int
        lib.fp_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]

    lib.fp_get_state.restype = ctypes.c_int
    lib.fp_get_state.argtypes = [ctypes.POINTER(FpStateC)]

    lib.fp_finalize.restype = ctypes.c_int
    lib.fp_finalize.argtypes = []
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen. Mirrors
# the tr L-5 choice: libfpapi.so pulls in graphics stubs (fp_graphics_stubs.f90)
# but the 5 exported entry points never reach any unresolved symbols.
# Lazy binding keeps us resilient if future versions leave stragglers.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libfpapi.so (``libfpapi.dll`` on Windows) and return the CDLL
    handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libfpapi.so may retain unresolved symbols
    pointing into code paths the C ABI never reaches. Lazy binding defers
    resolution to first call, so the 5 exported entry points load cleanly.

    Raises :class:`FileNotFoundError` with an actionable message when the
    library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        if sys.platform == "win32":
            # The Makefiles have no .dll target, so there is no make
            # command to name here.
            hint = (
                f"Build {_lib_filename()} from the Fortran sources "
                "or set FPLIB_PATH."
            )
        else:
            hint = "Build it via `make -C fp libfpapi.so` or set FPLIB_PATH."
        raise FileNotFoundError(
            f"{_lib_filename()} not found at {p}. "
            f"Tried FPLIB_PATH and {tried}. "
            + hint
        )
    new_dir_handle = None
    if sys.platform == "win32":
        # Python 3.8+ no longer resolves a DLL's dependencies through PATH.
        # The gfortran runtime (libgfortran-5.dll, libquadmath-0.dll,
        # libgcc_s_seh-1.dll, libwinpthread-1.dll) ships next to this DLL.
        # ctypes' default winmode searches the loaded DLL's own directory
        # for its dependencies once the name is a full path, which the line
        # below guarantees; registering the directory too is a second line
        # of defence. Never pass winmode=0 to "fix" a load error: that
        # skips registered directories and restores the PATH/cwd search.
        # AddDllDirectory rejects relative paths, hence abspath.
        dll_dir = os.path.abspath(p.parent)
        p = Path(dll_dir) / p.name
        key = os.path.normcase(dll_dir)
        if key not in _DLL_DIR_HANDLES:
            new_dir_handle = os.add_dll_directory(dll_dir)
    # ctypes.RTLD_LAZY may not be defined on all Python builds; fall
    # back to the numeric constant 1 which matches glibc dlfcn.h.
    mode = getattr(ctypes, "RTLD_LAZY", _RTLD_LAZY)
    try:
        lib = _apply_prototypes(ctypes.CDLL(str(p), mode=mode))
    except BaseException:
        # A file that does not load (wrong architecture, a missing
        # dependency) or is not this library must not leave its directory
        # in the process-wide DLL search set, nor an entry in the dict.
        # BaseException, re-raised: an interrupt during the load cleans
        # up too.
        if new_dir_handle is not None:
            new_dir_handle.close()
        raise
    if new_dir_handle is not None:
        _DLL_DIR_HANDLES[key] = new_dir_handle
    return lib


__all__ = [
    "FP_MAX_NRMAX",
    "FP_MAX_NSAMAX",
    "FP_OK",
    "FP_ERR_INVALID",
    "FP_ERR_NOT_INIT",
    "FP_ERR_CALC_FAILED",
    "FP_ERR_NOT_IMPL",
    "FpStateC",
    "HAS_NUMPY",
    "load_library",
]
