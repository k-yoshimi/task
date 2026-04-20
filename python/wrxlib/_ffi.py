"""Low-level ctypes FFI for libwrxapi.so.

Mirrors ``wrx/wrx_api.h`` (C ABI). Higher-level helpers live in
``wrxlib.py``; this module intentionally exposes only raw ctypes
objects so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

1. explicit ``path`` argument to :func:`load_library`
2. ``WRXLIB_PATH`` environment variable
3. ``<repo>/wrx/libwrxapi.so`` (standard L-4 build location)
4. ``<repo>/lib/libwrxapi.so`` (install-style location, future-proofing)

The package layout is ``python/wrxlib/_ffi.py`` so the repository root
is two parents above this file (``__file__.parents[2]``).
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import List, Optional

# Optional numpy (we never require it; state.py uses lists).
try:
    import numpy as _np  # noqa: F401
    HAS_NUMPY = True
except ImportError:  # pragma: no cover - numpy is optional
    HAS_NUMPY = False


# ---------------------------------------------------------------------
# Layout constants. Must match wrx/wrx_api.h exactly.
# ---------------------------------------------------------------------
WRX_MAX_NRAYMAX = 100
WRX_MAX_NSAMAX = 8
WRX_MAX_NRSMAX = 256
WRX_MAX_NRLMAX = 256


# ---------------------------------------------------------------------
# Error codes (kept in sync with wrx_api.h::enum wrx_error).
# ---------------------------------------------------------------------
WRX_OK = 0
WRX_ERR_INVALID = 1
WRX_ERR_NOT_INIT = 2
WRX_ERR_CALC_FAILED = 3
WRX_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# ctypes mirror of wrx_state_t from wrx/wrx_api.h.
#
# Memory-layout note (also in wrx_api.h):
#   In C, pwr_nsa_nray[NRAYMAX][NSAMAX] is row-major.
#   In Fortran the matching declaration is pwr_nsa_nray(NSAMAX, NRAYMAX)
#   (column-major). Both lay out the same bytes; only the index order
#   differs.
# ---------------------------------------------------------------------
class WrxStateC(ctypes.Structure):
    _fields_ = [
        # runtime dims
        ("nraymax", ctypes.c_int),
        ("nstpmax", ctypes.c_int),
        ("nsamax", ctypes.c_int),
        ("nsmax", ctypes.c_int),
        ("nrsmax", ctypes.c_int),
        ("nrlmax", ctypes.c_int),
        ("modelg", ctypes.c_int),
        ("mdlwrq", ctypes.c_int),
        # scalars
        ("pwr_tot", ctypes.c_double),
        # 1D arrays (baseline "arrays" group)
        ("nstpmax_nray", ctypes.c_int * WRX_MAX_NRAYMAX),
        ("pwr_nray", ctypes.c_double * WRX_MAX_NRAYMAX),
        ("pwr_nsa", ctypes.c_double * WRX_MAX_NSAMAX),
        ("pos_nrs", ctypes.c_double * WRX_MAX_NRSMAX),
        ("pos_nrl", ctypes.c_double * WRX_MAX_NRLMAX),
        # 2D arrays (baseline "arrays2" group). Fortran (NSAMAX, <outer>)
        # == C [<outer>][NSAMAX] under column-major-to-row-major bit
        # equivalence (see wrx_api.h note).
        ("pwr_nsa_nray", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRAYMAX),
        ("pwr_nrs_nsa", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRSMAX),
        ("pwr_nrl_nsa", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRLMAX),
        ("pos_pwrmax_rs_nsa_nray", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRAYMAX),
        ("pos_pwrmax_rl_nsa_nray", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRAYMAX),
        ("pwrmax_rs_nsa_nray", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRAYMAX),
        ("pwrmax_rl_nsa_nray", (ctypes.c_double * WRX_MAX_NSAMAX) * WRX_MAX_NRAYMAX),
        # legacy 1D-by-species (kept for BC)
        ("pos_pwrmax_rs_nsa", ctypes.c_double * WRX_MAX_NSAMAX),
        ("pwrmax_rs_nsa", ctypes.c_double * WRX_MAX_NSAMAX),
        ("pos_pwrmax_rl_nsa", ctypes.c_double * WRX_MAX_NSAMAX),
        ("pwrmax_rl_nsa", ctypes.c_double * WRX_MAX_NSAMAX),
    ]


# ---------------------------------------------------------------------
# Library loader.
# ---------------------------------------------------------------------
def _repo_root() -> Path:
    """Return the repository root (two parents up from this file)."""
    return Path(__file__).resolve().parents[2]


def _candidate_paths() -> List[Path]:
    """All library paths that :func:`load_library` will try in order."""
    root = _repo_root()
    return [root / "wrx" / "libwrxapi.so", root / "lib" / "libwrxapi.so"]


def _default_lib_path() -> Path:
    """Resolve the default ``libwrxapi.so`` path.

    Honours ``WRXLIB_PATH`` first; otherwise returns the first existing
    candidate. If none exists, returns the canonical build location so
    the error message from :func:`load_library` mentions it directly.
    """
    env = os.environ.get("WRXLIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 5 exported C ABI symbols."""
    lib.wrx_init.restype = ctypes.c_int
    lib.wrx_init.argtypes = []

    lib.wrx_run.restype = ctypes.c_int
    lib.wrx_run.argtypes = [ctypes.c_int]

    lib.wrx_set_param.restype = ctypes.c_int
    lib.wrx_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    lib.wrx_get_state.restype = ctypes.c_int
    lib.wrx_get_state.argtypes = [ctypes.POINTER(WrxStateC)]

    lib.wrx_finalize.restype = ctypes.c_int
    lib.wrx_finalize.argtypes = []
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen. The
# L-4 build of libwrxapi.so retains a few symbols that are reachable
# only from graphics-only code paths (e.g. libgrf::grd1d used by
# wrcalpwr) that the C ABI never calls during init/set_param/
# get_state/finalize. Lazy binding is safe for those entry points
# and matches the pattern established by wrlib._ffi / trlib._ffi.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libwrxapi.so and return the CDLL handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libwrxapi.so may retain unresolved
    symbols pointing into graphics-only call paths that the C ABI
    never reaches. Lazy binding defers resolution to first call, so
    the 5 exported entry points load cleanly.

    Raises :class:`FileNotFoundError` with an actionable message when
    the library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        raise FileNotFoundError(
            f"libwrxapi.so not found at {p}. "
            f"Tried WRXLIB_PATH and {tried}. "
            "Build it via `make -C wrx libwrxapi.so` or set WRXLIB_PATH."
        )
    # ctypes.RTLD_LAZY may not be defined on all Python builds; fall
    # back to the numeric constant 1 which matches glibc dlfcn.h.
    mode = getattr(ctypes, "RTLD_LAZY", _RTLD_LAZY)
    lib = ctypes.CDLL(str(p), mode=mode)
    return _apply_prototypes(lib)


__all__ = [
    "WRX_MAX_NRAYMAX",
    "WRX_MAX_NSAMAX",
    "WRX_OK",
    "WRX_ERR_INVALID",
    "WRX_ERR_NOT_INIT",
    "WRX_ERR_CALC_FAILED",
    "WRX_ERR_NOT_IMPL",
    "WrxStateC",
    "HAS_NUMPY",
    "load_library",
]
