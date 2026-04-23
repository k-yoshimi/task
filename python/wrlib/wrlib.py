"""High-level ``Wrlib`` class.

See ``docs/superpowers/plans/2026-04-18-wr-library-L5-python-wrapper.md``.

Usage::

    from wrlib import Wrlib

    with Wrlib() as wr:
        wr.set_params(RR=3.0, BB=3.5)    # scalar kwargs only
        wr.set_param("PN[1]", 0.7)       # array elements via set_param
        wr.run(nray_request=0)           # 0 keeps namelist NRAYMAX
        state = wr.get_state()
        print(state.scalars["pwrmax_rs"])
"""
from __future__ import annotations

import ctypes
import weakref
from typing import Optional

from . import _ffi
from .errors import WrlibError, WrlibParamError, WrlibStateError, raise_for_ierr
from .state import WrState


_MAX_C_STRING_BYTES = 63              # name buffer is CHARACTER(LEN=64)


def _encode_name(s: str, max_bytes: int = _MAX_C_STRING_BYTES) -> bytes:
    """Encode a C string argument accepted by the WR registry."""
    if not isinstance(s, str):
        raise WrlibParamError(
            f"WR C string arguments must be str, got {type(s).__name__}"
        )
    try:
        encoded = s.encode("ascii")
    except UnicodeEncodeError as exc:
        raise WrlibParamError(
            f"WR C string {s!r} contains non-ASCII characters"
        ) from exc
    if b"\x00" in encoded:
        raise WrlibParamError(f"WR C string {s!r} contains an embedded NUL byte")
    if len(encoded) > max_bytes:
        raise WrlibParamError(
            f"WR C string {s!r} is {len(encoded)} bytes; "
            f"maximum is {max_bytes}"
        )
    return encoded


class Wrlib:
    """In-process handle to libwrapi.so. One instance per process.

    libwrapi.so holds singleton Fortran state (COMMON blocks + SAVE
    variables), so creating more than one live :class:`Wrlib` is not
    meaningful; the second ``__init__`` call will call ``wr_init``
    again and reset the shared state. This matches the design-spec
    contract.
    """

    _live_instance = None

    def __init__(self, lib_path: Optional[str] = None) -> None:
        # Start closed so _open() can transition to open.
        self._closed = True
        self._claim_live_instance()
        try:
            self._lib = _ffi.load_library(lib_path)
            self._open()
        except Exception:
            self._release_live_instance()
            raise

    # --- lifecycle ------------------------------------------------------
    def _claim_live_instance(self) -> None:
        cls = self.__class__
        ref = cls._live_instance
        live = ref() if ref is not None else None
        if live is not None:
            raise WrlibStateError(
                "another live Wrlib() instance exists; COMMON-block backend "
                "cannot be safely shared"
            )
        cls._live_instance = weakref.ref(self)

    def _release_live_instance(self) -> None:
        cls = self.__class__
        ref = cls._live_instance
        if ref is not None and ref() is self:
            cls._live_instance = None

    def _open(self) -> None:
        if not self._closed:
            return
        ierr = self._lib.wr_init()
        raise_for_ierr("wr_init", ierr)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            self._release_live_instance()
            return
        ierr = self._lib.wr_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        self._release_live_instance()
        raise_for_ierr("wr_finalize", ierr)

    def __enter__(self) -> "Wrlib":
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
        see the C ABI spec and ``wr_param_registry.f90`` for the full
        registry.
        """
        if self._closed:
            raise WrlibError("set_param on closed Wrlib")
        ierr = self._lib.wr_set_param(
            _encode_name(name), ctypes.c_double(float(value))
        )
        raise_for_ierr(f"wr_set_param('{name}', {value})", ierr)

    def set_params(self, **kwargs: float) -> None:
        """Bulk-set **scalar** parameters by keyword.

        Array elements are NOT supported here because Python keyword
        arguments cannot contain ``[`` or ``]``. To set an array
        element, call :py:meth:`set_param` directly::

            wr.set_param("PN[1]", 0.7)

        Names containing ``__`` are rejected up-front as a likely
        array-syntax mistake.
        """
        for k, v in kwargs.items():
            if "__" in k:
                raise WrlibError(
                    f"set_params() received '{k}' which contains '__'. "
                    "set_params is scalar-only; use "
                    "set_param('NAME[i]', value) for array elements."
                )
            self.set_param(k, v)

    # --- run / state ----------------------------------------------------
    def run(self, nray_request: int = 0) -> None:
        """Execute ``wr_run`` with the given number of rays requested.

        ``nray_request > 0`` overrides the namelist NRAYMAX before
        allocation. ``nray_request <= 0`` keeps whatever NRAYMAX was
        set via init / set_param.
        """
        if self._closed:
            raise WrlibError("run on closed Wrlib")
        ierr = self._lib.wr_run(int(nray_request))
        raise_for_ierr(f"wr_run({nray_request})", ierr)

    def get_state(self) -> WrState:
        """Copy the current simulation state into a :class:`WrState`."""
        if self._closed:
            raise WrlibError("get_state on closed Wrlib")
        c = _ffi.WrStateC()
        ierr = self._lib.wr_get_state(ctypes.byref(c))
        raise_for_ierr("wr_get_state", ierr)
        return WrState.from_c(c)


__all__ = ["Wrlib"]
