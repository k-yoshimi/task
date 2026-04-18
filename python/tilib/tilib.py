"""High-level :class:`TiLib` class.

See ``docs/superpowers/specs/2026-04-17-tr-library-design.md`` §6.3 for
the common design shared with trlib; ti tracks the same contract.

Usage::

    from tilib import TiLib

    with TiLib() as ti:
        ti.set_params(RR=6.2, BB=5.3)   # scalar kwargs only
        ti.set_param("PN[1]", 0.7)       # array elements via set_param
        ti.run(ntmax=10)
        state = ti.get_state()
        print(state.T)
"""
from __future__ import annotations

import ctypes
from typing import Optional

from . import _ffi
from .errors import TilibError, raise_for_ierr
from .state import TiState


class TiLib:
    """In-process handle to libtiapi.so. One instance per process.

    libtiapi.so holds singleton Fortran state (COMMON blocks), so
    creating more than one live :class:`TiLib` is not meaningful; the
    second ``__init__`` call will call ``ti_init`` again and reset the
    shared state. This matches the design-spec contract.
    """

    def __init__(self, lib_path: Optional[str] = None) -> None:
        self._lib = _ffi.load_library(lib_path)
        # Start closed so _open() can transition to open.
        self._closed = True
        self._open()

    # --- lifecycle ------------------------------------------------------
    def _open(self) -> None:
        if not self._closed:
            return
        ierr = self._lib.ti_init()
        raise_for_ierr("ti_init", ierr)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            return
        ierr = self._lib.ti_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        raise_for_ierr("ti_finalize", ierr)

    def __enter__(self) -> "TiLib":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            # Destructors must never raise.
            pass

    @property
    def closed(self) -> bool:
        return self._closed

    # --- parameters -----------------------------------------------------
    def set_param(self, name: str, value: float) -> None:
        """Set one parameter by name. ``name`` is forwarded verbatim.

        Array elements use the ``NAME[i]`` syntax (e.g. ``"PN[1]"``);
        see ``ti/ti_param_registry.f90`` for the full registry.
        """
        if self._closed:
            raise TilibError("set_param on closed TiLib")
        ierr = self._lib.ti_set_param(
            name.encode("ascii"), ctypes.c_double(float(value))
        )
        raise_for_ierr(f"ti_set_param('{name}', {value})", ierr)

    def set_params(self, **kwargs: float) -> None:
        """Bulk-set **scalar** parameters by keyword.

        Array elements are NOT supported here because Python keyword
        arguments cannot contain ``[`` or ``]``. To set an array
        element, call :py:meth:`set_param` directly::

            ti.set_param("PN[1]", 0.7)

        Names containing ``__`` are rejected up-front as a likely
        array-syntax mistake.
        """
        for k, v in kwargs.items():
            if "__" in k:
                raise TilibError(
                    f"set_params() received '{k}' which contains '__'. "
                    "set_params is scalar-only; use "
                    "set_param('NAME[i]', value) for array elements."
                )
            self.set_param(k, v)

    # --- run / state ----------------------------------------------------
    def run(self, ntmax: int) -> None:
        """Advance the simulation ``ntmax`` time-steps.

        ``ntmax=0`` is a valid no-op used by the smoke test.
        """
        if self._closed:
            raise TilibError("run on closed TiLib")
        ierr = self._lib.ti_run(int(ntmax))
        raise_for_ierr(f"ti_run({ntmax})", ierr)

    def get_state(self) -> TiState:
        """Copy the current simulation state into a :class:`TiState`."""
        if self._closed:
            raise TilibError("get_state on closed TiLib")
        c = _ffi.TiStateC()
        ierr = self._lib.ti_get_state(ctypes.byref(c))
        raise_for_ierr("ti_get_state", ierr)
        return TiState.from_c(c)


# Spec-style lowercase alias (``Tilib``) for callers who prefer it.
Tilib = TiLib


__all__ = ["TiLib", "Tilib"]
