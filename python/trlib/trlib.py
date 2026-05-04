"""High-level ``Trlib`` class.

See ``docs/superpowers/specs/2026-04-17-tr-library-design.md`` §6.3.

Usage::

    from trlib import Trlib

    with Trlib() as tr:
        tr.set_params(RR=7.5, BB=5.3)   # scalar kwargs only
        tr.set_param("PN[1]", 0.7)      # array elements via set_param
        tr.run(ntmax=100)
        state = tr.get_state()
        print(state.scalars["T"])
"""
from __future__ import annotations

import ctypes
import weakref
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional

from . import _ffi
from .errors import TrlibError, TrlibParamError, TrlibStateError, raise_for_ierr
from .state import TrState


_MAX_C_STRING_BYTES = 63              # name buffer is CHARACTER(LEN=64)
_MAX_C_STRING_VALUE_BYTES = 128       # value buffer is CHARACTER(LEN=128);
                                       # tr_api_set_param_str DO loop reads
                                       # up to LEN(fvalue) chars so full 128 OK


def _encode_name(s: str, max_bytes: int = _MAX_C_STRING_BYTES) -> bytes:
    """Encode a C string argument accepted by the TR registry.

    ``max_bytes`` is the Fortran buffer size minus 1 (for NUL). Names
    use the default; values passed to ``set_param_str`` use
    ``_MAX_C_STRING_VALUE_BYTES``.
    """
    if not isinstance(s, str):
        raise TrlibParamError(
            f"TR C string arguments must be str, got {type(s).__name__}"
        )
    try:
        encoded = s.encode("ascii")
    except UnicodeEncodeError as exc:
        raise TrlibParamError(
            f"TR C string {s!r} contains non-ASCII characters"
        ) from exc
    if b"\x00" in encoded:
        raise TrlibParamError(f"TR C string {s!r} contains an embedded NUL byte")
    if len(encoded) > max_bytes:
        raise TrlibParamError(
            f"TR C string {s!r} is {len(encoded)} bytes; "
            f"maximum is {max_bytes}"
        )
    return encoded


class TrDiagCode(IntEnum):
    """Diagnostic category codes returned by :py:meth:`Trlib.validate`.

    Mirrors ``enum tr_diag_code`` in ``tr/tr_api.h``. Use the integer
    value of the enum when comparing against :attr:`TrDiagEntryPy.code`,
    or compare directly: ``entry.code == TrDiagCode.OUT_OF_RANGE``.
    """

    OUT_OF_RANGE           = _ffi.TR_DIAG_OUT_OF_RANGE
    INCONSISTENT_PAIR      = _ffi.TR_DIAG_INCONSISTENT_PAIR
    OUT_OF_RANGE_AFTER_DEP = _ffi.TR_DIAG_OUT_OF_RANGE_AFTER_DEP
    FILE_MISSING           = _ffi.TR_DIAG_FILE_MISSING
    MISSING_REQUIRED       = _ffi.TR_DIAG_MISSING_REQUIRED


@dataclass(frozen=True)
class TrDiagEntryPy:
    """One pre-run validation diagnostic.

    User-facing return type for :py:meth:`Trlib.validate`. Strings are
    decoded from the underlying CHARACTER arrays with trailing NUL
    padding stripped — no ctypes objects leak through this dataclass.

    Attributes:
        param:   parameter name the diagnostic refers to (e.g. ``NSMAX``)
        code:    diagnostic category (compare against :class:`TrDiagCode`)
        message: human-readable description suitable for surfacing to UI
    """

    param: str
    code: int
    message: str


class Trlib:
    """In-process handle to libtrapi.so. One instance per process.

    libtrapi.so holds singleton Fortran state (COMMON blocks), so
    creating more than one live :class:`Trlib` is not meaningful; the
    second ``__init__`` call will call ``tr_init`` again and reset the
    shared state. This matches the design-spec contract.
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
            raise TrlibStateError(
                "another live Trlib() instance exists; COMMON-block backend "
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
        ierr = self._lib.tr_init()
        raise_for_ierr("tr_init", ierr)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            self._release_live_instance()
            return
        ierr = self._lib.tr_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        self._release_live_instance()
        raise_for_ierr("tr_finalize", ierr)

    def __enter__(self) -> "Trlib":
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
        see the C ABI spec for the full registry.
        """
        if self._closed:
            raise TrlibError("set_param on closed Trlib")
        ierr = self._lib.tr_set_param(
            _encode_name(name), ctypes.c_double(float(value))
        )
        raise_for_ierr(f"tr_set_param('{name}', {value})", ierr)

    def set_param_str(self, name: str, value: str) -> None:
        """Set one string-valued parameter (e.g. ``KNAMEQ``).

        ``libtrapi.so`` exposes ``tr_set_param_str`` as of the L-6
        registry-extension PR. Older builds will raise :class:`TrlibError`
        because :mod:`trlib._ffi` leaves the attribute missing; update
        the .so via ``make -C tr libtrapi.so`` to recover.
        """
        if self._closed:
            raise TrlibError("set_param_str on closed Trlib")
        try:
            fn = self._lib.tr_set_param_str
        except AttributeError as exc:
            raise TrlibError(
                "libtrapi.so does not export tr_set_param_str; "
                "rebuild the shared library after the L-6 registry "
                "extension PR."
            ) from exc
        ierr = fn(
            _encode_name(name),
            _encode_name(value, _MAX_C_STRING_VALUE_BYTES),
        )
        raise_for_ierr(f"tr_set_param_str('{name}', '{value}')", ierr)

    def set_params(self, **kwargs: float) -> None:
        """Bulk-set **scalar** parameters by keyword.

        Array elements are NOT supported here because Python keyword
        arguments cannot contain ``[`` or ``]``. Earlier drafts
        attempted a ``PN__1`` -> ``PN[1]`` convenience conversion via
        ``str.replace`` but that produced malformed names. To set an
        array element, call :py:meth:`set_param` directly::

            tr.set_param("PN[1]", 0.7)

        Names containing ``__`` are rejected up-front as a likely
        array-syntax mistake.
        """
        for k, v in kwargs.items():
            if "__" in k:
                raise TrlibError(
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
            raise TrlibError("run on closed Trlib")
        ierr = self._lib.tr_run(int(ntmax))
        raise_for_ierr(f"tr_run({ntmax})", ierr)

    def get_state(self) -> TrState:
        """Copy the current simulation state into a :class:`TrState`."""
        if self._closed:
            raise TrlibError("get_state on closed Trlib")
        c = _ffi.TrStateC()
        ierr = self._lib.tr_get_state(ctypes.byref(c))
        raise_for_ierr("tr_get_state", ierr)
        return TrState.from_c(c)

    # --- validation (Issue #143) ---------------------------------------
    def validate(self) -> List[TrDiagEntryPy]:
        """Run pre-run cross-parameter validation.

        Returns the list of diagnostics produced by ``tr_validate``
        (read-only against the current tr state). The recommended
        workflow is::

            tr.set_params(...)
            diags = tr.validate()
            if diags:
                # surface / fix / re-validate, then run
                ...
            tr.run(...)

        Return-code mapping (``tr_api_validate`` contract):

        * ``TR_OK`` (0)            -> empty list (clean state)
        * ``TR_ERR_INVALID`` (1)   -> non-empty list (the diagnostics
          themselves are the payload; ``ierr == 1`` only signals
          "diagnostics present" so callers do not need to inspect the
          C-level return code)
        * ``TR_ERR_NOT_INIT`` (2)  -> :class:`TrlibStateError`

        Older builds without ``tr_validate`` raise :class:`TrlibError`
        (rebuild via ``make -C tr libtrapi.so``). The method does not
        modify any tr state.
        """
        if self._closed:
            raise TrlibError("validate on closed Trlib")
        try:
            fn = self._lib.tr_validate
        except AttributeError as exc:
            raise TrlibError(
                "libtrapi.so does not export tr_validate; "
                "rebuild the shared library after the #143 PR."
            ) from exc

        cap = _ffi.TR_DIAG_DEFAULT_CAP
        buf = (_ffi.TrDiagEntry * cap)()
        ndiag = ctypes.c_int(0)
        ierr = fn(buf, cap, ctypes.byref(ndiag))

        # Contract: ierr==2 (NOT_INIT) is the only one that maps to an
        # exception; ierr==0 and ierr==1 both return the list (empty /
        # not).
        if ierr == _ffi.TR_ERR_NOT_INIT:
            raise TrlibStateError(f"tr_validate: ierr={ierr}")
        if ierr not in (_ffi.TR_OK, _ffi.TR_ERR_INVALID):
            # Defensive: future codes should not silently masquerade
            # as success. Reuse the central ierr -> exception mapping.
            raise_for_ierr("tr_validate", ierr)

        n = int(ndiag.value)
        # Fortran push_diag increments nlocal past diag_cap but skips
        # the write (tr_api.f90), so ndiag_out can exceed cap. Clamp
        # and warn so the caller knows results are truncated instead
        # of IndexError-ing off the end of the ctypes buffer.
        if n > cap:
            import warnings
            warnings.warn(
                f"tr_validate produced {n} diagnostics but buffer "
                f"capacity is {cap}; results are truncated. Increase "
                f"trlib._ffi.TR_DIAG_DEFAULT_CAP.",
                RuntimeWarning,
                stacklevel=2,
            )
            n = cap
        out: List[TrDiagEntryPy] = []
        for i in range(n):
            entry = buf[i]
            param = entry.param.decode("ascii", errors="replace").rstrip("\x00")
            message = entry.msg.decode("ascii", errors="replace").rstrip("\x00")
            out.append(TrDiagEntryPy(
                param=param,
                code=int(entry.code),
                message=message,
            ))
        return out

    def check_bpsd_pull(self) -> bool:
        """Verify that BPSD has the 3 eq-pushed slots (device, equ1D,
        metric1D) by performing a non-mutating round-trip pull into
        local discardable types. plasmaf is excluded: it is tr's own
        BPSD output, absent on a fresh eq -> tr pipeline.

        Used by TotPipeline as a pre-tr-run verification of the eq -> tr
        BPSD coupling: after eq.run() pushes equ1D/metric1D into BPSD,
        a False return signals broker failure / missing eq step / wrong
        pipeline order. TRCOMM is unaffected.

        Returns True iff all 3 BPSD slots are pullable (per-slot ierr==0).
        """
        if self._closed:
            raise TrlibError("check_bpsd_pull on closed Trlib")
        ok = ctypes.c_int(0)
        self._lib.tr_check_bpsd_pull(ctypes.byref(ok))
        return ok.value == 1


__all__ = ["Trlib", "TrDiagCode", "TrDiagEntryPy"]
