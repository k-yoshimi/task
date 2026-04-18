"""Low-level ctypes FFI for libtiapi.so.

Mirrors ``ti/ti_api.h`` (C ABI). Higher-level helpers live in
``tilib.py``; this module intentionally exposes only raw ctypes objects
so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

1. explicit ``path`` argument to :func:`load_library`
2. ``TILIB_PATH`` environment variable
3. ``<repo>/ti/libtiapi.so`` (standard L-4 build location)
4. ``<repo>/lib/libtiapi.so`` (install-style location, future-proofing)

The package layout is ``python/tilib/_ffi.py`` so the repository root is
two parents above this file (``__file__.parents[2]``).
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Optional

# Optional numpy (we never require it; state.py uses lists).
try:
    import numpy as _np  # noqa: F401
    HAS_NUMPY = True
except ImportError:  # pragma: no cover - numpy is optional
    HAS_NUMPY = False


# ---------------------------------------------------------------------
# Layout constants. Must match ti/ti_api.h exactly.
# ---------------------------------------------------------------------
TI_MAX_NRMAX = 200
TI_MAX_NSA_MAX = 20


# ---------------------------------------------------------------------
# Error codes (kept in sync with ti_api.h::enum ti_error).
# ---------------------------------------------------------------------
TI_OK = 0
TI_ERR_INVALID = 1
TI_ERR_NOT_INIT = 2
TI_ERR_CALC_FAILED = 3
TI_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# ctypes mirror of ti_state_t from ti/ti_api.h.
#
# Memory-layout note (also in ti_api.h):
#   In C, RNA[NRMAX][NSA_MAX] is row-major.
#   In Fortran the matching declaration is RNA(NSA_MAX, NRMAX) column-major.
#   Both lay out the same bytes; only the index order differs.
# ---------------------------------------------------------------------
class TiStateC(ctypes.Structure):
    _fields_ = [
        ("nt", ctypes.c_int),
        ("nrmax", ctypes.c_int),
        ("nsa_max", ctypes.c_int),
        ("nsmax", ctypes.c_int),
        ("T", ctypes.c_double),
        ("residual_loop_max", ctypes.c_double),
        ("icount_loop_max", ctypes.c_int),
        ("icount_mat_max", ctypes.c_int),
        ("RNA", (ctypes.c_double * TI_MAX_NSA_MAX) * TI_MAX_NRMAX),
        ("RTA", (ctypes.c_double * TI_MAX_NSA_MAX) * TI_MAX_NRMAX),
        ("RUA", (ctypes.c_double * TI_MAX_NSA_MAX) * TI_MAX_NRMAX),
        ("RBP", ctypes.c_double * TI_MAX_NRMAX),
        ("RQP", ctypes.c_double * TI_MAX_NRMAX),
        ("RJP", ctypes.c_double * TI_MAX_NRMAX),
        ("ZEFF", ctypes.c_double * TI_MAX_NRMAX),
        ("BETA", ctypes.c_double * TI_MAX_NRMAX),
        ("BETAP", ctypes.c_double * TI_MAX_NRMAX),
    ]


# ---------------------------------------------------------------------
# Library loader.
# ---------------------------------------------------------------------
def _repo_root() -> Path:
    """Return the repository root (two parents up from this file)."""
    return Path(__file__).resolve().parents[2]


def _candidate_paths() -> list[Path]:
    """All library paths that :func:`load_library` will try in order."""
    root = _repo_root()
    return [root / "ti" / "libtiapi.so", root / "lib" / "libtiapi.so"]


def _default_lib_path() -> Path:
    """Resolve the default ``libtiapi.so`` path.

    Honours ``TILIB_PATH`` first; otherwise returns the first existing
    candidate. If none exists, returns the canonical build location so
    the error message from :func:`load_library` mentions it directly.
    """
    env = os.environ.get("TILIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 5 exported C ABI symbols."""
    lib.ti_init.restype = ctypes.c_int
    lib.ti_init.argtypes = []

    lib.ti_run.restype = ctypes.c_int
    lib.ti_run.argtypes = [ctypes.c_int]

    lib.ti_set_param.restype = ctypes.c_int
    lib.ti_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    lib.ti_get_state.restype = ctypes.c_int
    lib.ti_get_state.argtypes = [ctypes.POINTER(TiStateC)]

    lib.ti_finalize.restype = ctypes.c_int
    lib.ti_finalize.argtypes = []
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen. The L-4
# build of libtiapi.so may retain a handful of symbols reachable only
# from graphics-only code paths that the C ABI never calls. Those paths
# are unreachable from ``ti_init`` / ``ti_run`` / ``ti_get_state`` /
# ``ti_finalize`` so lazy binding is safe and matches the design-doc
# stance that graphics is an add-on rather than a blocker for the Python
# wrapper.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libtiapi.so and return the CDLL handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libtiapi.so may retain unresolved symbols
    pointing into graphics-only call paths that the C ABI never reaches.
    Lazy binding defers resolution to first call, so the 5 exported
    entry points load cleanly.

    Raises :class:`FileNotFoundError` with an actionable message when
    the library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        raise FileNotFoundError(
            f"libtiapi.so not found at {p}. "
            f"Tried TILIB_PATH and {tried}. "
            "Build it via `make -C ti libtiapi.so` or set TILIB_PATH."
        )
    # ctypes.RTLD_LAZY may not be defined on all Python builds; fall
    # back to the numeric constant 1 which matches glibc dlfcn.h.
    mode = getattr(ctypes, "RTLD_LAZY", _RTLD_LAZY)
    lib = ctypes.CDLL(str(p), mode=mode)
    return _apply_prototypes(lib)


__all__ = [
    "TI_MAX_NRMAX",
    "TI_MAX_NSA_MAX",
    "TI_OK",
    "TI_ERR_INVALID",
    "TI_ERR_NOT_INIT",
    "TI_ERR_CALC_FAILED",
    "TI_ERR_NOT_IMPL",
    "TiStateC",
    "HAS_NUMPY",
    "load_library",
]
