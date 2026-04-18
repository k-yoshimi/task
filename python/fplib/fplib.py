"""High-level ``Fplib`` class.

Mirrors the tr L-5 design (see
``docs/superpowers/specs/2026-04-17-tr-library-design.md`` §6) adapted
for the fp C ABI in ``fp/fp_api.h``.

Usage::

    from fplib import Fplib

    with Fplib() as fp:
        fp.set_params(RR=6.5, BB=5.3, NSMAX=3)
        fp.set_param("PN[1]", 0.8)          # array element by name
        fp.run(ntmax=2)
        state = fp.get_state()
        print(state.timefp, state.RNT)
"""
from __future__ import annotations

import ctypes
from typing import Optional

from . import _ffi
from .errors import (
    FplibError, FplibInvalidParamError,
    raise_for_rc,
)
from .state import FpState


class Fplib:
    """In-process handle to libfpapi.so. One instance per process.

    libfpapi.so holds singleton Fortran state (FPCOMM arrays), so
    creating more than one live :class:`Fplib` is not meaningful; the
    second ``__init__`` call will call ``fp_init`` again and reset the
    shared state.
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
        rc = self._lib.fp_init()
        raise_for_rc("fp_init", rc)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            return
        rc = self._lib.fp_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        raise_for_rc("fp_finalize", rc)

    def __enter__(self) -> "Fplib":
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

    # backward-compat alias with the plan draft (``_initialized``).
    @property
    def _initialized(self) -> bool:
        return not self._closed

    # --- parameters -----------------------------------------------------
    def set_param(self, name: str, value: float) -> None:
        """Set one parameter by name. ``name`` is forwarded verbatim.

        Array elements use the ``NAME[i]`` syntax (e.g. ``"PN[1]"``);
        see ``fp/fp_param_registry.f90`` for the full registry.
        """
        if self._closed:
            raise FplibError("set_param on closed Fplib")
        rc = self._lib.fp_set_param(
            name.encode("ascii"), ctypes.c_double(float(value))
        )
        if rc != _ffi.FP_OK:
            raise FplibInvalidParamError(
                f"fp_set_param('{name}', {value}) failed (rc={rc})"
            )

    def set_params(self, **kwargs) -> None:
        """Bulk-set parameters by keyword.

        Array values may be provided as:

        * dict ``{idx: value}`` -> emits ``NAME[idx] = value`` (1-origin)
        * list / tuple ``[v1, v2, ...]`` -> emits ``NAME[1..N] = vi``
        * scalar -> emits ``NAME = value``

        Python keyword argument names cannot contain ``[`` or ``]`` so
        array elements must go through the dict / list form (or call
        :py:meth:`set_param` directly). Keys containing ``__`` are
        rejected as a likely ``NAME__i`` array-syntax mistake.
        """
        for k, v in kwargs.items():
            if "__" in k:
                raise FplibError(
                    f"set_params() received '{k}' which contains '__'. "
                    "Use either set_params(NAME={i: value}) or "
                    "set_param('NAME[i]', value) for array elements."
                )
            if isinstance(v, dict):
                for idx, vv in v.items():
                    self.set_param(f"{k}[{int(idx)}]", float(vv))
            elif isinstance(v, (list, tuple)):
                for i, vv in enumerate(v, start=1):
                    self.set_param(f"{k}[{i}]", float(vv))
            else:
                self.set_param(k, float(v))

    # --- run / state ----------------------------------------------------
    def run(self, ntmax: int) -> None:
        """Advance the FP simulation ``ntmax`` time-steps.

        ``ntmax=0`` is a valid no-op used by the smoke test.
        """
        if self._closed:
            raise FplibError("run on closed Fplib")
        rc = self._lib.fp_run(int(ntmax))
        raise_for_rc(f"fp_run({ntmax})", rc)

    def get_state(self) -> FpState:
        """Copy the current simulation state into a :class:`FpState`."""
        if self._closed:
            raise FplibError("get_state on closed Fplib")
        c = _ffi.FpStateC()
        rc = self._lib.fp_get_state(ctypes.byref(c))
        raise_for_rc("fp_get_state", rc)
        return FpState.from_c(c)


__all__ = ["Fplib"]
