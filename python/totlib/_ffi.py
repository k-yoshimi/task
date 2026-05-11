"""Low-level ctypes FFI for libtotapi.so.

Mirrors ``tot/tot_api.h`` (C ABI). Higher-level helpers live in
``totlib.py``; this module intentionally exposes only raw ctypes objects
so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

1. explicit ``path`` argument to :func:`load_library`
2. ``TOTLIB_PATH`` environment variable
3. ``<repo>/tot/libtotapi.so`` (standard L-4 build location)
4. ``<repo>/lib/libtotapi.so`` (install-style location, future-proofing)

The package layout is ``python/totlib/_ffi.py`` so the repository root
is two parents above this file (``__file__.parents[2]``).
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
# Layout constants. Must match tot/tot_api.h exactly.
# ---------------------------------------------------------------------
TOT_MAX_NRMAX = 500
TOT_MAX_NSMAX = 8


# ---------------------------------------------------------------------
# Error codes (kept in sync with tot_api.h::enum tot_error).
# ---------------------------------------------------------------------
TOT_OK = 0
TOT_ERR_INVALID = 1
TOT_ERR_NOT_INIT = 2
TOT_ERR_CALC_FAILED = 3
TOT_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# Supported namespace prefixes for tot_set_param / tot_set_param_str.
# Names without one of these prefixes are rejected by
# tot_param_registry.f90 with rc=1.
# ---------------------------------------------------------------------
TOT_NAMESPACES = ("eq", "tr", "fp", "ti", "wr", "wrx")


# ---------------------------------------------------------------------
# ctypes mirror of tot_state_t from tot/tot_api.h.
#
# At L-3 / L-4 the orchestrator state aggregates per-module presence
# flags plus a flat copy of the integrated TR-authoritative scalars and
# profiles. Layouts agree byte-for-byte with the BIND(C) tot_state_c
# type in tot/tot_state.f90.
#
# Memory-layout note: in C, RN[NRMAX][NSMAX] is row-major; the matching
# Fortran declaration RN(NSMAX, NRMAX) is column-major. The bytes are
# the same; only the index order differs. Only [0..nrmax-1][0..nsmax-1]
# carry valid runtime data; the remainder is padding up to TOT_MAX_*.
# ---------------------------------------------------------------------
class TotStateC(ctypes.Structure):
    _fields_ = [
        # --- per-module presence flags (0 = absent, 1 = initialized) -
        ("tr_present", ctypes.c_int),
        ("ti_present", ctypes.c_int),
        ("fp_present", ctypes.c_int),
        ("wr_present", ctypes.c_int),
        # --- integrated scalars ------------------------------------
        ("nt", ctypes.c_int),
        ("nrmax", ctypes.c_int),
        ("nsmax", ctypes.c_int),
        ("T", ctypes.c_double),
        ("WPT", ctypes.c_double),
        ("AJT", ctypes.c_double),
        ("Q0", ctypes.c_double),
        ("BETA0", ctypes.c_double),
        ("BETAP0", ctypes.c_double),
        ("BETAA", ctypes.c_double),
        ("BETAN", ctypes.c_double),
        ("TAUE1", ctypes.c_double),
        ("TAUE2", ctypes.c_double),
        ("ZEFF0", ctypes.c_double),
        ("ALI", ctypes.c_double),
        ("RQ1", ctypes.c_double),
        # --- integrated profile slots ------------------------------
        ("RN", (ctypes.c_double * TOT_MAX_NSMAX) * TOT_MAX_NRMAX),
        ("RT", (ctypes.c_double * TOT_MAX_NSMAX) * TOT_MAX_NRMAX),
        ("AJ", ctypes.c_double * TOT_MAX_NRMAX),
        ("QP", ctypes.c_double * TOT_MAX_NRMAX),
        # L-7b-i: total RF + external driven current [MA]. Mirrors AJRFT
        # in tr_state_c; appended at end-of-struct for ABI v2 compatibility.
        ("AJRFT", ctypes.c_double),
    ]


# ---------------------------------------------------------------------
# Library loader.
# ---------------------------------------------------------------------
def _repo_root() -> Path:
    """Return the repository root (two parents up from this file)."""
    return Path(__file__).resolve().parents[2]


def _candidate_paths() -> list:
    """All library paths that :func:`load_library` will try in order."""
    root = _repo_root()
    return [root / "tot" / "libtotapi.so", root / "lib" / "libtotapi.so"]


def _default_lib_path() -> Path:
    """Resolve the default ``libtotapi.so`` path.

    Honours ``TOTLIB_PATH`` first; otherwise returns the first existing
    candidate. If none exists, returns the canonical build location so
    the error message from :func:`load_library` mentions it directly.
    """
    env = os.environ.get("TOTLIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 6 exported C ABI symbols.

    TOT exports the same surface as eq: 6 entry points including a
    string setter (``tot_set_param_str``). Older builds without the
    string setter will lack the symbol; we attach it best-effort so
    package import does not fail. Callers will get a clean
    ``AttributeError`` on first use instead.
    """
    lib.tot_init.restype = ctypes.c_int
    lib.tot_init.argtypes = []

    lib.tot_run.restype = ctypes.c_int
    lib.tot_run.argtypes = [ctypes.c_int]

    lib.tot_set_param.restype = ctypes.c_int
    lib.tot_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    try:
        lib.tot_set_param_str.restype = ctypes.c_int
        lib.tot_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    except AttributeError:  # pragma: no cover - only on pre-L-3 builds
        pass

    lib.tot_get_state.restype = ctypes.c_int
    lib.tot_get_state.argtypes = [ctypes.POINTER(TotStateC)]

    lib.tot_finalize.restype = ctypes.c_int
    lib.tot_finalize.argtypes = []
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen.
# libtotapi.so is composed by linking the per-module .so files (libtr,
# libti, libfp, libwr, libeq, ...) which in turn carry references to
# graphics-only symbols (PAGES, r2w2b_, ...). The C ABI happy path
# never reaches those, so deferring resolution lets the loader succeed
# even when the graphics archives are absent. Mirrors the strategy
# already used by trlib / eqlib and tested by tot/tests/c_abi/test_run_so.c.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libtotapi.so and return the CDLL handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libtotapi.so legitimately retains
    unresolved references into per-module graphics paths that are never
    invoked through the C ABI.

    Raises :class:`FileNotFoundError` with an actionable message when
    the library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        raise FileNotFoundError(
            f"libtotapi.so not found at {p}. "
            f"Tried TOTLIB_PATH and {tried}. "
            "Build it via `make -C tot libtotapi.so` or set TOTLIB_PATH."
        )
    # ctypes.RTLD_LAZY may not be defined on all Python builds; fall
    # back to the numeric constant 1 which matches glibc dlfcn.h.
    mode = getattr(ctypes, "RTLD_LAZY", _RTLD_LAZY)
    lib = ctypes.CDLL(str(p), mode=mode)
    return _apply_prototypes(lib)


__all__ = [
    "TOT_MAX_NRMAX",
    "TOT_MAX_NSMAX",
    "TOT_OK",
    "TOT_ERR_INVALID",
    "TOT_ERR_NOT_INIT",
    "TOT_ERR_CALC_FAILED",
    "TOT_ERR_NOT_IMPL",
    "TOT_NAMESPACES",
    "TotStateC",
    "HAS_NUMPY",
    "load_library",
]
