"""Low-level ctypes FFI for libeqapi.so.

Mirrors ``eq/eq_api.h`` (C ABI). Higher-level helpers live in
``eqlib.py``; this module intentionally exposes only raw ctypes objects
so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

0. ``MONO_LIB_PATH`` env var (#208 PR-A): if set, all wrappers route
   to the same monolithic image so eq/tr/etc. share one BPSD broker.
1. explicit ``path`` argument to :func:`load_library`
2. ``EQLIB_PATH`` environment variable
3. ``<repo>/eq/libeqapi.so`` (standard L-4 build location)
4. ``<repo>/lib/libeqapi.so`` (install-style location, future-proofing)

The package layout is ``python/eqlib/_ffi.py`` so the repository root is
two parents above this file (``__file__.parents[2]``).
"""
from __future__ import annotations

import ctypes
import os
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
# Layout constants. Must match eq/eq_api.h exactly.
# Source of truth: eq/eqcom0.inc (NRGM=513, NZGM=513, NPSM=513,
# NRM=1001, NTHM=2049, NSUM=1343).
# ---------------------------------------------------------------------
EQ_MAX_NRGM = 513
EQ_MAX_NZGM = 513
EQ_MAX_NPSM = 513
EQ_MAX_NRM = 1001
EQ_MAX_NTHM = 2049
EQ_MAX_NSUM = 1343


# ---------------------------------------------------------------------
# Error codes (kept in sync with eq_api.h::enum eq_error).
# ---------------------------------------------------------------------
EQ_OK = 0
EQ_ERR_INVALID = 1
EQ_ERR_NOT_INIT = 2
EQ_ERR_CALC_FAILED = 3
EQ_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# Issue #143 pre-run parameter validation API constants. Must mirror
# eq_api.h (EQ_DIAG_PARAM_LEN / EQ_DIAG_MSG_LEN) and the enum
# eq_diag_code values; eq_state.f90::eq_diag_entry_c is the matching
# Fortran-side struct.
# ---------------------------------------------------------------------
EQ_DIAG_PARAM_LEN = 64
EQ_DIAG_MSG_LEN = 128

EQ_DIAG_OUT_OF_RANGE           = 1
EQ_DIAG_INCONSISTENT_PAIR      = 2
EQ_DIAG_OUT_OF_RANGE_AFTER_DEP = 3
EQ_DIAG_FILE_MISSING           = 4
EQ_DIAG_MISSING_REQUIRED       = 5

# Default capacity for the validate-buffer that the high-level wrapper
# allocates. eq_api_validate currently emits at most ~11 entries; 32 is
# a conservative head-room allowing future categories to grow without
# breaking the wrapper. Mirrors the EQ_DIAG_CAP_HINT note in
# eq_api.f90::push_diag.
EQ_DIAG_DEFAULT_CAP = 32


# ---------------------------------------------------------------------
# ctypes mirror of eq_state_t from eq/eq_api.h.
#
# Phase L-2/L-3 ABI populates 6 grid counters, 12 plasma scalars, and
# 6 fixed-size 1D arrays (4 psi-surface profiles + R/Z grid). Larger
# 2D arrays (PSIRZ, RPS, ZPS) are not part of the C struct as of the
# L-4 build; if added later, append them here in the same order as
# the C header.
#
# Memory-layout note: Fortran-side declarations use the same C-ABI
# struct via ``BIND(C)`` in eq/eq_state.f90, so byte layout is
# guaranteed identical when compiled with the same iso_c_binding
# kinds (C_INT == c_int, C_DOUBLE == c_double).
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# ctypes mirror of eq_diag_entry_t from eq/eq_api.h (Issue #143).
#
# Layout: param[64], code (int), msg[128]. Must match
# eq_state.f90::eq_diag_entry_c byte-for-byte. Fortran fills param /
# msg via TRIM + appended C_NULL_CHAR; the high-level wrapper strips
# trailing NULs on decode (see EqDiagEntryPy in eqlib.py).
# ---------------------------------------------------------------------
class EqDiagEntry(ctypes.Structure):
    _fields_ = [
        ("param", ctypes.c_char * EQ_DIAG_PARAM_LEN),
        ("code",  ctypes.c_int),
        ("msg",   ctypes.c_char * EQ_DIAG_MSG_LEN),
    ]


class EqStateC(ctypes.Structure):
    _fields_ = [
        # --- grid counters (active runtime values, not EQ_MAX_*) ---
        ("nrgmax", ctypes.c_int),
        ("nzgmax", ctypes.c_int),
        ("npsmax", ctypes.c_int),
        ("nrmax", ctypes.c_int),
        ("nthmax", ctypes.c_int),
        ("nsumax", ctypes.c_int),
        # NRVMAX = volume-grid count; NSGMAX/NTGMAX = orthogonal
        # curvilinear PSI(s,t) grid (eqcom1_mod).
        ("nrvmax", ctypes.c_int),
        ("nsgmax", ctypes.c_int),
        ("ntgmax", ctypes.c_int),
        # --- plasma scalars (EQGLB1 / EQGLB2) ---
        ("raxis", ctypes.c_double),
        ("zaxis", ctypes.c_double),
        ("psi0", ctypes.c_double),
        ("psipa", ctypes.c_double),
        ("psita", ctypes.c_double),
        ("qaxis", ctypes.c_double),
        ("qsurf", ctypes.c_double),
        ("betat", ctypes.c_double),
        ("betap", ctypes.c_double),
        ("pvol", ctypes.c_double),
        ("raave", ctypes.c_double),
        ("ripx", ctypes.c_double),
        # --- 1D psi-surface profiles (sampled at 1..npsmax) ---
        ("psips", ctypes.c_double * EQ_MAX_NPSM),
        ("ppps", ctypes.c_double * EQ_MAX_NPSM),
        ("ttps", ctypes.c_double * EQ_MAX_NPSM),
        ("qqps", ctypes.c_double * EQ_MAX_NPSM),
        # --- R / Z grid coordinates ---
        ("rg", ctypes.c_double * EQ_MAX_NRGM),
        ("zg", ctypes.c_double * EQ_MAX_NZGM),
        # --- per-NR flux-surface profile (1..nrmax). Mirrors the 7
        # columns the Phase 0 baseline writes via eqregress.f. ---
        ("profile_psip", ctypes.c_double * EQ_MAX_NRM),
        ("profile_psit", ctypes.c_double * EQ_MAX_NRM),
        ("profile_pps",  ctypes.c_double * EQ_MAX_NRM),
        ("profile_tts",  ctypes.c_double * EQ_MAX_NRM),
        ("profile_qps",  ctypes.c_double * EQ_MAX_NRM),
        ("profile_vps",  ctypes.c_double * EQ_MAX_NRM),
        ("profile_rst",  ctypes.c_double * EQ_MAX_NRM),
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
    return [root / "eq" / "libeqapi.so", root / "lib" / "libeqapi.so"]


def _default_lib_path() -> Path:
    """Resolve the default ``libeqapi.so`` path.

    Priority (highest first):
      0. ``mono_lib_path()`` — global mono override
         (``MONO_LIB_PATH`` env var). See #208 Phase 2c PR-A spec.
      1. ``EQLIB_PATH`` env var
      2. ``<repo>/eq/libeqapi.so``
      3. ``<repo>/lib/libeqapi.so``

    ``load_library(path=...)`` still accepts an explicit override that
    wins over (0) — the early ``if path:`` branch runs before this
    function is consulted.
    """
    mono = mono_lib_path()
    if mono is not None:
        return mono
    env = os.environ.get("EQLIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 6 exported C ABI symbols.

    EQ exports one more entry than tr / ti: ``eq_set_param_str`` for
    string-valued parameters such as ``KNAMEQ``. Older builds without
    the string setter will lack the symbol; we attach it best-effort so
    import does not fail there. Callers will get a clean
    ``AttributeError`` on first use instead.
    """
    lib.eq_init.restype = ctypes.c_int
    lib.eq_init.argtypes = []

    lib.eq_run.restype = ctypes.c_int
    lib.eq_run.argtypes = [ctypes.c_int]

    lib.eq_set_param.restype = ctypes.c_int
    lib.eq_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    try:
        lib.eq_set_param_str.restype = ctypes.c_int
        lib.eq_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    except AttributeError:  # pragma: no cover - only on pre-L-3 builds
        pass

    lib.eq_get_state.restype = ctypes.c_int
    lib.eq_get_state.argtypes = [ctypes.POINTER(EqStateC)]

    # eq_validate (Issue #143). Best-effort: older builds without the
    # symbol leave lib.eq_validate as an AttributeError on first access,
    # matching the handling for eq_set_param_str above.
    try:
        lib.eq_validate.restype = ctypes.c_int
        lib.eq_validate.argtypes = [
            ctypes.POINTER(EqDiagEntry),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
    except AttributeError:  # pragma: no cover - only on pre-#143 builds
        pass

    # eq_save: () -> int
    try:
        lib.eq_save.argtypes = []
        lib.eq_save.restype = ctypes.c_int
    except AttributeError:  # pragma: no cover - only on pre-Task-1.1 builds
        pass

    # eq_common_get_psi_rz_(int* nr, int* nz, double* psi_out)
    try:
        lib.eq_common_get_psi_rz_.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_double),
        ]
        lib.eq_common_get_psi_rz_.restype = None
    except AttributeError:  # pragma: no cover - only on pre-Task-1.4 builds
        pass

    lib.eq_finalize.restype = ctypes.c_int
    lib.eq_finalize.argtypes = []
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen. The
# L-4 build of libeqapi.so retains a handful of symbols reachable only
# from graphics-only code paths that the C ABI never calls (replaced
# by stubs in eq_graphics_stubs.f90 but still possibly referenced from
# legacy Fortran). Lazy binding defers resolution to first call, so
# the 6 exported entry points load cleanly.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libeqapi.so and return the CDLL handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libeqapi.so may retain unresolved
    symbols pointing into graphics-only call paths that the C ABI
    never reaches.

    Raises :class:`FileNotFoundError` with an actionable message when
    the library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        raise FileNotFoundError(
            f"libeqapi.so not found at {p}. "
            f"Tried EQLIB_PATH and {tried}. "
            "Build it via `make -C eq libeqapi.so` or set EQLIB_PATH."
        )
    # ctypes.RTLD_LAZY may not be defined on all Python builds; fall
    # back to the numeric constant 1 which matches glibc dlfcn.h.
    mode = getattr(ctypes, "RTLD_LAZY", _RTLD_LAZY)
    lib = ctypes.CDLL(str(p), mode=mode)
    return _apply_prototypes(lib)


__all__ = [
    "EQ_MAX_NRGM",
    "EQ_MAX_NZGM",
    "EQ_MAX_NPSM",
    "EQ_MAX_NRM",
    "EQ_MAX_NTHM",
    "EQ_MAX_NSUM",
    "EQ_OK",
    "EQ_ERR_INVALID",
    "EQ_ERR_NOT_INIT",
    "EQ_ERR_CALC_FAILED",
    "EQ_ERR_NOT_IMPL",
    "EQ_DIAG_PARAM_LEN",
    "EQ_DIAG_MSG_LEN",
    "EQ_DIAG_DEFAULT_CAP",
    "EQ_DIAG_OUT_OF_RANGE",
    "EQ_DIAG_INCONSISTENT_PAIR",
    "EQ_DIAG_OUT_OF_RANGE_AFTER_DEP",
    "EQ_DIAG_FILE_MISSING",
    "EQ_DIAG_MISSING_REQUIRED",
    "EqDiagEntry",
    "EqStateC",
    "HAS_NUMPY",
    "load_library",
]
