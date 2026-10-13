"""Single authoritative source for runtime-mode routing decisions.

Today this owns only the MONO_LIB_PATH env var contract introduced by
#208 Phase 2c PR-A. Future runtime concerns (build flavor, debug
mode) can land here without touching per-module _ffi.py loaders
again. See docs/superpowers/specs/2026-05-23-l7b-ii-phase-2c-pra-
loader-contract-design.md for the full design.
"""
from __future__ import annotations

import ctypes
import functools
import os
import sys
from pathlib import Path
from typing import Optional


@functools.lru_cache(maxsize=None)
def mono_lib_path() -> Optional[Path]:
    """Return Path to libtotapi_mono.so if MONO_LIB_PATH is set and
    points at a valid mono image; return None otherwise. On Windows the
    path returned is absolute, whatever MONO_LIB_PATH held.

    Raises:
        FileNotFoundError: MONO_LIB_PATH set, file missing.
        RuntimeError:      MONO_LIB_PATH set, file is not a mono image
                           (dlopen failed, or tot_is_mono symbol
                           missing, or tot_is_mono() returned 0).

    Cache:
        Result memoized for the lifetime of the Python process.
        Call ``mono_lib_path.cache_clear()`` if the env var is
        mutated at runtime (tests; production code never needs this).
        Under pytest's ``--forked`` each test runs in a fresh
        subprocess so the cache is naturally invalidated between
        tests.
    """
    env = os.environ.get("MONO_LIB_PATH", "").strip()
    if not env:
        return None
    p = Path(env)
    if not p.exists():
        raise FileNotFoundError(
            f"MONO_LIB_PATH={env!r} does not exist. Unset the env "
            "var or build the mono image: "
            "`make -C tot libtotapi_mono.so`."
        )
    if sys.platform == "win32":
        # A bare relative name passes exists() from the working directory,
        # where Windows' DLL search does not look: LoadLibrary would miss
        # the image or the gfortran runtime DLLs beside it. Probe the
        # absolute path, and hand that to the per-module loaders.
        p = Path(os.path.abspath(p))
    # Wrap CDLL so wrong-arch / non-ELF / dep-broken .so files
    # surface as the friendly RuntimeError, NOT a raw OSError with a
    # cryptic dlerror string.
    try:
        lib = ctypes.CDLL(
            str(p), mode=getattr(ctypes, "RTLD_LAZY", 1)
        )
    except OSError as exc:
        raise RuntimeError(
            f"MONO_LIB_PATH={env!r} cannot be dlopen'd: {exc}. "
            "Likely wrong architecture, non-ELF, or missing "
            "dependency. Build via "
            "`make -C tot libtotapi_mono.so` on the same host."
        ) from exc
    if not hasattr(lib, "tot_is_mono"):
        raise RuntimeError(
            f"MONO_LIB_PATH={env!r} exposes no `tot_is_mono` "
            "symbol. This indicates a pre-Phase-2b .so. Rebuild "
            "against develop or a newer branch."
        )
    lib.tot_is_mono.restype = ctypes.c_int
    lib.tot_is_mono.argtypes = []
    if lib.tot_is_mono() != 1:
        raise RuntimeError(
            f"MONO_LIB_PATH={env!r} is not a mono image "
            "(tot_is_mono() returned 0). Set MONO_LIB_PATH to a "
            "libtotapi_mono.so built via "
            "`make -C tot libtotapi_mono.so`."
        )
    return p


__all__ = ["mono_lib_path"]
