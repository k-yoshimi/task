"""Low-level ctypes FFI for libtrapi.so (``libtrapi.dll`` on Windows).

Mirrors ``tr/tr_api.h`` (C ABI). Higher-level helpers live in
``trlib.py``; this module intentionally exposes only raw ctypes objects
so tests can exercise the boundary directly.

Library-path resolution order (first match wins):

0. ``MONO_LIB_PATH`` env var (#208 PR-A): if set, all wrappers route
   to the same monolithic image so eq/tr/etc. share one BPSD broker.
1. explicit ``path`` argument to :func:`load_library`
2. ``TRLIB_PATH`` environment variable
3. ``<repo>/tr/libtrapi.so`` (standard L-4 build location; ``libtrapi.dll``
   on Windows)
4. ``<repo>/lib/libtrapi.so`` (install-style location, future-proofing;
   ``libtrapi.dll`` on Windows)

The package layout is ``python/trlib/_ffi.py`` so the repository root is
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
# Layout constants. Must match tr/tr_api.h exactly.
# ---------------------------------------------------------------------
TR_MAX_NRMAX = 500
TR_MAX_NSMAX = 8


# ---------------------------------------------------------------------
# Error codes (kept in sync with tr_api.h::enum tr_error).
# ---------------------------------------------------------------------
TR_OK = 0
TR_ERR_INVALID = 1
TR_ERR_NOT_INIT = 2
TR_ERR_CALC_FAILED = 3
TR_ERR_NOT_IMPL = 4


# ---------------------------------------------------------------------
# Issue #143 pre-run parameter validation API constants. Must mirror
# tr_api.h (TR_DIAG_PARAM_LEN / TR_DIAG_MSG_LEN) and the enum
# tr_diag_code values; tr_state.f90::tr_diag_entry_c is the matching
# Fortran-side struct.
# ---------------------------------------------------------------------
TR_DIAG_PARAM_LEN = 64
TR_DIAG_MSG_LEN = 128

TR_DIAG_OUT_OF_RANGE           = 1
TR_DIAG_INCONSISTENT_PAIR      = 2
TR_DIAG_OUT_OF_RANGE_AFTER_DEP = 3
TR_DIAG_FILE_MISSING           = 4
TR_DIAG_MISSING_REQUIRED       = 5

# Default capacity for the validate-buffer that the high-level wrapper
# allocates. The L-3 pilot emits at most 5 entries; 32 is conservative
# head-room so future categories can grow without breaking the wrapper.
TR_DIAG_DEFAULT_CAP = 32


# ---------------------------------------------------------------------
# ctypes mirror of tr_diag_entry_t from tr/tr_api.h (Issue #143).
#
# Layout: param[64], code (int), msg[128]. Must match
# tr_state.f90::tr_diag_entry_c byte-for-byte. Fortran fills param /
# msg via TRIM + appended C_NULL_CHAR; the high-level wrapper strips
# trailing NULs on decode (see TrDiagEntryPy in trlib.py).
# ---------------------------------------------------------------------
class TrDiagEntry(ctypes.Structure):
    _fields_ = [
        ("param", ctypes.c_char * TR_DIAG_PARAM_LEN),
        ("code",  ctypes.c_int),
        ("msg",   ctypes.c_char * TR_DIAG_MSG_LEN),
    ]


# ---------------------------------------------------------------------
# ctypes mirror of tr_state_t from tr/tr_api.h.
#
# Memory-layout note (also in tr_api.h):
#   In C, RN[NRMAX][NSMAX] is row-major.
#   In Fortran the matching declaration is RN(NSMAX, NRMAX) column-major.
#   Both lay out the same bytes; only the index order differs.
# ---------------------------------------------------------------------
class TrStateC(ctypes.Structure):
    _fields_ = [
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
        ("RN", (ctypes.c_double * TR_MAX_NSMAX) * TR_MAX_NRMAX),
        ("RT", (ctypes.c_double * TR_MAX_NSMAX) * TR_MAX_NRMAX),
        ("AJ", ctypes.c_double * TR_MAX_NRMAX),
        ("QP", ctypes.c_double * TR_MAX_NRMAX),
        # L-7b-i: total RF + external driven current [MA]. Mirrors AJRFT
        # in tr_state_c (Fortran) and tr_state_t (C). Placed at struct end
        # to preserve existing field offsets.
        ("AJRFT", ctypes.c_double),
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
    """``libtrapi.dll`` on Windows, ``libtrapi.so`` everywhere else.

    macOS keeps the ``.so`` name because that is what ``make libtrapi.so``
    produces there, even though the file is a Mach-O dylib.
    """
    return "libtrapi.dll" if sys.platform == "win32" else "libtrapi.so"


def _candidate_paths() -> list[Path]:
    """All library paths that :func:`load_library` will try in order."""
    root = _repo_root()
    name = _lib_filename()
    return [root / "tr" / name, root / "lib" / name]


def _default_lib_path() -> Path:
    """Resolve the default ``libtrapi.so`` path (``libtrapi.dll`` on Windows).

    Priority (highest first):
      0. ``mono_lib_path()`` — global mono override (``MONO_LIB_PATH``)
      1. ``TRLIB_PATH`` env var
      2. ``<repo>/tr/libtrapi.so``
      3. ``<repo>/lib/libtrapi.so``
    """
    mono = mono_lib_path()
    if mono is not None:
        return mono
    env = os.environ.get("TRLIB_PATH")
    if env:
        return Path(env)
    for cand in _candidate_paths():
        if cand.exists():
            return cand
    return _candidate_paths()[0]


def _apply_prototypes(lib: ctypes.CDLL) -> ctypes.CDLL:
    """Attach argtypes / restype to the 6 exported C ABI symbols.

    ``tr_set_param_str`` (L-6 follow-up) is attached best-effort: older
    libtrapi.so builds from the L-3..L-5 series do not export it, and
    we do not want to break wrapper import in that case. Callers that
    need the string setter will get a clean ``AttributeError`` on first
    use instead.
    """
    lib.tr_init.restype = ctypes.c_int
    lib.tr_init.argtypes = []

    lib.tr_run.restype = ctypes.c_int
    lib.tr_run.argtypes = [ctypes.c_int]

    lib.tr_set_param.restype = ctypes.c_int
    lib.tr_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]

    try:
        lib.tr_set_param_str.restype = ctypes.c_int
        lib.tr_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    except AttributeError:
        # Older .so without the string setter. Leave the attribute
        # missing; Trlib.set_param_str will raise on use.
        pass

    lib.tr_get_state.restype = ctypes.c_int
    lib.tr_get_state.argtypes = [ctypes.POINTER(TrStateC)]

    # tr_validate (Issue #143). Best-effort: older builds without the
    # symbol leave lib.tr_validate as AttributeError on first access,
    # matching the handling for tr_set_param_str above.
    try:
        lib.tr_validate.restype = ctypes.c_int
        lib.tr_validate.argtypes = [
            ctypes.POINTER(TrDiagEntry),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_int),
        ]
    except AttributeError:  # pragma: no cover - only on pre-#143 builds
        pass

    lib.tr_finalize.restype = ctypes.c_int
    lib.tr_finalize.argtypes = []

    # L-7b-ii: BPSD broker round-trip verification (non-mutating).
    # Best-effort: older builds of libtrapi.so may not export this
    # symbol yet (predate L-7b-ii). Mirror tr_validate's try/except
    # pattern -- defer the failure to first call (Trlib.check_bpsd_pull
    # surfaces it as an AttributeError) so unrelated tr_* APIs on
    # the same .so remain usable.
    try:
        lib.tr_check_bpsd_pull.argtypes = [ctypes.POINTER(ctypes.c_int)]
        lib.tr_check_bpsd_pull.restype = None
    except AttributeError:  # pragma: no cover - only on pre-L-7b-ii builds
        pass
    return lib


# RTLD_LAZY: resolve symbols on first use rather than at dlopen. The L-4
# build of libtrapi.so retains a handful of symbols that are reachable
# only from graphics-only code paths that the C ABI never calls (e.g.
# ``viewgtlist_`` inside the ``?`` branch of ``trfout``). Those paths are
# unreachable from ``tr_init`` / ``tr_run`` / ``tr_get_state`` /
# ``tr_finalize`` so lazy binding is safe and matches the design-doc
# stance (§A.4) that graphics is a libtrgrf_pic.a add-on rather than a
# blocker for the Python wrapper.
_RTLD_LAZY = 1


def load_library(path: Optional[str] = None) -> ctypes.CDLL:
    """Load libtrapi.so (``libtrapi.dll`` on Windows) and return the CDLL
    handle with prototypes applied.

    Uses ``RTLD_LAZY`` because libtrapi.so may retain unresolved
    symbols pointing into graphics-only call paths that the C ABI
    never reaches. Lazy binding defers resolution to first call, so
    the 5 exported entry points load cleanly.

    Raises :class:`FileNotFoundError` with an actionable message when
    the library is not where we looked.
    """
    p = Path(path) if path else _default_lib_path()
    if not p.exists():
        tried = [str(x) for x in _candidate_paths()]
        if sys.platform == "win32":
            # The Makefiles have no .dll target, so there is no make
            # command to name here.
            hint = (
                f"Build {_lib_filename()} from the Fortran sources "
                "or set TRLIB_PATH."
            )
        else:
            hint = "Build it via `make -C tr libtrapi.so` or set TRLIB_PATH."
        raise FileNotFoundError(
            f"{_lib_filename()} not found at {p}. "
            f"Tried TRLIB_PATH and {tried}. "
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
    "TR_MAX_NRMAX",
    "TR_MAX_NSMAX",
    "TR_OK",
    "TR_ERR_INVALID",
    "TR_ERR_NOT_INIT",
    "TR_ERR_CALC_FAILED",
    "TR_ERR_NOT_IMPL",
    "TR_DIAG_PARAM_LEN",
    "TR_DIAG_MSG_LEN",
    "TR_DIAG_DEFAULT_CAP",
    "TR_DIAG_OUT_OF_RANGE",
    "TR_DIAG_INCONSISTENT_PAIR",
    "TR_DIAG_OUT_OF_RANGE_AFTER_DEP",
    "TR_DIAG_FILE_MISSING",
    "TR_DIAG_MISSING_REQUIRED",
    "TrDiagEntry",
    "TrStateC",
    "HAS_NUMPY",
    "load_library",
]
