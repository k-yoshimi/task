"""High-level :class:`Eq` class wrapping ``libeqapi.so``.

See ``docs/superpowers/specs/2026-04-17-tr-library-design.md`` §6.3 for
the common 2-layer design shared with trlib / tilib; eq follows the same
contract with one extra entry point (``eq_set_param_str``).

Usage::

    from eqlib import Eq

    with Eq() as eq:
        eq.set_params(RR=3.0, BB=3.0, RIP=1.0)
        eq.set_param("PSIB[0]", 0.0)        # array element (0-origin!)
        eq.set_param_str("KNAMEQ", "eqdata")  # string parameter
        eq.run(mode=1)                       # 1 == real EQDSK load
        state = eq.get_state()
        print(state.scalars["raxis"])
"""
from __future__ import annotations

import ctypes
import os
import weakref
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, List, Mapping, Optional

from . import _ffi
from .errors import (
    EqlibError,
    EqlibInvalidParamError,
    EqlibNotInitializedError,
    raise_for_rc,
)
from .state import EqState


_MAX_C_STRING_BYTES = 63              # name buffer is CHARACTER(LEN=64);
                                       # 63 leaves 1 conservative byte
_MAX_C_STRING_VALUE_BYTES = 80        # value buffer is CHARACTER(LEN=80);
                                       # eq_api_set_param_str reads up to
                                       # LEN(fvalue) chars so full 80 is OK


def _encode_name(s: str, max_bytes: int = _MAX_C_STRING_BYTES) -> bytes:
    """Encode a C string argument accepted by the EQ registry.

    ``max_bytes`` is the longest string the Fortran side takes: names use
    the default, ``_MAX_C_STRING_BYTES`` (63 of the CHARACTER(LEN=64)
    buffer, one byte kept spare); values passed to ``set_param_str`` use
    ``_MAX_C_STRING_VALUE_BYTES`` (all 80 characters of KNAMEQ; the NUL is
    not stored).
    """
    if not isinstance(s, str):
        raise EqlibInvalidParamError(
            f"EQ C string arguments must be str, got {type(s).__name__}"
        )
    try:
        encoded = s.encode("ascii")
    except UnicodeEncodeError as exc:
        raise EqlibInvalidParamError(
            f"EQ C string {s!r} contains non-ASCII characters"
        ) from exc
    if b"\x00" in encoded:
        raise EqlibInvalidParamError(
            f"EQ C string {s!r} contains an embedded NUL byte"
        )
    if len(encoded) > max_bytes:
        raise EqlibInvalidParamError(
            f"EQ C string {s!r} is {len(encoded)} bytes; "
            f"maximum is {max_bytes}"
        )
    return encoded


class EqDiagCode(IntEnum):
    """Diagnostic category codes returned by :py:meth:`Eq.validate`.

    Mirrors ``enum eq_diag_code`` in ``eq/eq_api.h``. Use the integer
    value of the enum when comparing against :attr:`EqDiagEntryPy.code`,
    or compare directly: ``entry.code == EqDiagCode.OUT_OF_RANGE``.
    """

    OUT_OF_RANGE           = _ffi.EQ_DIAG_OUT_OF_RANGE
    INCONSISTENT_PAIR      = _ffi.EQ_DIAG_INCONSISTENT_PAIR
    OUT_OF_RANGE_AFTER_DEP = _ffi.EQ_DIAG_OUT_OF_RANGE_AFTER_DEP
    FILE_MISSING           = _ffi.EQ_DIAG_FILE_MISSING
    MISSING_REQUIRED       = _ffi.EQ_DIAG_MISSING_REQUIRED


@dataclass(frozen=True)
class EqDiagEntryPy:
    """One pre-run validation diagnostic.

    User-facing return type for :py:meth:`Eq.validate`. Strings are
    decoded from the underlying CHARACTER arrays with trailing NUL
    padding stripped — no ctypes objects leak through this dataclass.

    Attributes:
        param:   parameter name the diagnostic refers to (e.g. ``NRMAX``)
        code:    diagnostic category (compare against :class:`EqDiagCode`)
        message: human-readable description suitable for surfacing to UI
    """

    param: str
    code: int
    message: str


class Eq:
    """In-process handle to libeqapi.so. One instance per process.

    libeqapi.so holds singleton Fortran state (COMMON blocks plus
    ``eqcom*_mod`` MODULE variables). Creating more than one live
    :class:`Eq` is not meaningful; the second ``__init__`` will call
    ``eq_init`` again and reset the shared state.
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
            raise EqlibNotInitializedError(
                "another live Eq() instance exists; COMMON-block backend "
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
        rc = self._lib.eq_init()
        raise_for_rc("eq_init", rc)
        self._closed = False

    def close(self) -> None:
        """Finalise the library. Idempotent."""
        if self._closed:
            self._release_live_instance()
            return
        rc = self._lib.eq_finalize()
        # Mark closed before raising so __del__ doesn't retry.
        self._closed = True
        self._release_live_instance()
        raise_for_rc("eq_finalize", rc)

    def __enter__(self) -> "Eq":
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
        """Set one numeric parameter by name.

        ``name`` is forwarded verbatim to ``eq_set_param``; parsing
        of array subscripts (``"PSIB[0]"``, ``"RIPFC[3]"``) happens in
        ``eq_param_registry.f90`` (Phase L-3).

        EQ-specific note: ``PSIB`` is **0-origin** because the
        underlying Fortran is ``REAL(8) :: PSIB(0:5)``. Bare
        ``"PSIB"`` (no subscript) is rejected with ``rc == 1`` because
        the registry uses idx == -1 as the "no subscript" sentinel.
        Use ``set_param("PSIB[0]", v)``. All other 1D parameters
        (``RIPFC``, ``RPFC``, ``ZPFC``, ``WPFC``) are 1-origin.
        """
        if self._closed:
            raise EqlibError("set_param on closed Eq")
        rc = self._lib.eq_set_param(
            _encode_name(name), ctypes.c_double(float(value))
        )
        raise_for_rc(f"eq_set_param('{name}', {value})", rc)

    def set_param_str(self, name: str, value: str) -> None:
        """Set one string-valued parameter (e.g. ``KNAMEQ``).

        Supported names (CHARACTER(LEN=80) on the Fortran side):
        ``KNAMEQ, KNAMEQ2, KNAMWR, KNAMWM, KNAMFP, KNAMFO, KNAMPF``.

        Older builds without ``eq_set_param_str`` will raise
        :class:`EqlibError`; rebuild the .so via
        ``make -C eq libeqapi.so`` to recover.
        """
        if self._closed:
            raise EqlibError("set_param_str on closed Eq")
        try:
            fn = self._lib.eq_set_param_str
        except AttributeError as exc:
            raise EqlibError(
                "libeqapi.so does not export eq_set_param_str; "
                "rebuild the shared library after the L-3 registry PR."
            ) from exc
        rc = fn(
            _encode_name(name),
            _encode_name(value, _MAX_C_STRING_VALUE_BYTES),
        )
        raise_for_rc(f"eq_set_param_str('{name}', '{value}')", rc)

    def set_params(self, *args: Mapping[str, Any], **kwargs: Any) -> None:
        """Bulk-set scalar parameters.

        Accepts either a single dict positional argument, a list of
        ``(name, value)`` pairs, or scalar kwargs::

            eq.set_params(RR=3.0, BB=3.0)
            eq.set_params({"RR": 3.0, "BB": 3.0})
            eq.set_params([("RR", 3.0), ("BB", 3.0)])

        Array elements are NOT supported here because Python keyword
        arguments cannot contain ``[`` or ``]``. To set an array
        element, call :py:meth:`set_param` directly::

            eq.set_param("PSIB[0]", 0.0)

        Names containing ``__`` are rejected up-front as a likely
        array-syntax mistake (matches trlib / tilib behaviour).
        """
        items: list = []
        if args:
            if len(args) > 1:
                raise EqlibError(
                    "set_params() takes at most one positional argument; "
                    f"got {len(args)}"
                )
            arg0 = args[0]
            if isinstance(arg0, Mapping):
                items.extend(arg0.items())
            else:
                # Assume iterable of (name, value) pairs.
                items.extend(arg0)
        items.extend(kwargs.items())

        for k, v in items:
            if "__" in k:
                raise EqlibError(
                    f"set_params() received '{k}' which contains '__'. "
                    "set_params is scalar-only; use "
                    "set_param('NAME[i]', value) for array elements."
                )
            self.set_param(k, v)

    # --- run / state ----------------------------------------------------
    def run(self, mode: int = 1) -> None:
        """Run the EQ solver.

        Args:
            mode: Solver mode.

                * ``1`` (default) triggers a real EQDSK load via
                  ``equnit::eq_load`` using the current ``MODELG`` and
                  ``KNAMEQ`` (requires ``MODELG in {3, 5, 8}``).
                * ``0`` runs the in-process analytic Grad-Shafranov
                  solve (``EQCALC`` + ``EQCALQ``); use it with
                  ``MODELG=2`` and the basic geometry parameters
                  (``RR``, ``RA``, ``BB``, ``RIP``, ``RKAP``,
                  ``RDLT``, ...) to produce a self-consistent
                  equilibrium without any external EQDSK file.

                Other values return ``EQ_ERR_NOT_IMPL``.
        """
        if self._closed:
            raise EqlibError("run on closed Eq")
        rc = self._lib.eq_run(int(mode))
        raise_for_rc(f"eq_run({mode})", rc)

    def save(self, path) -> None:
        """Save the equilibrium of the last ``run`` to a TASK/EQ binary file.

        Sets KNAMEQ to ``path``, then calls ``eq_save``. The file is what
        ``MODELG=3`` with ``KNAMEQ=path`` loads. ``path`` is a ``str`` or an
        ``os.PathLike`` that gives one (what ``os.fspath`` refuses is a
        ``TypeError``); KNAMEQ is ASCII, so a ``bytes`` path and a
        non-ASCII one are refused like the other paths listed below.

        Once the path is accepted, KNAMEQ is ``path``, also when the save
        then fails. After a failed write, what is at the path cannot be
        taken for the equilibrium that was to be saved (usually it is a
        short file): do not load it. ``run(1)`` with ``MODELG=3`` ends the process on a file
        that is cut off; the loader does not guard its reads.

        A save whose file was not opened, or is shorter than what was
        written, raises (#227 item 3):

        * :class:`EqlibInvalidParamError`, and no file is touched:
          the fields do not hold the equilibrium of the present parameters
          (no ``run`` since the handle was opened, a later solve or load
          that failed, or ``set_param`` of anything but ``MODEFR`` and
          ``MODEFW`` since the last one: run again first); a blank path,
          one longer
          than the 80 bytes of ``KNAMEQ``, or one that ends in a blank
          (Fortran would drop the blank and write another file);
          ``MODEFW`` other than 0 (overwrite an existing file) or 3
          (refuse one): with 1, 2 and 4 to 7 ``FWOPEN`` can read unit 5.
          A ``bytes`` path and one that is not ASCII are refused here too,
          before KNAMEQ is set.
        * :class:`EqlibCalculationFailedError`: the file could not be
          opened (a directory that is missing or not writable;
          ``MODEFW=3`` and an existing file), a write failed (an existing
          file without write permission), or the file is shorter than what
          was written (a write the system refused, as under a file size
          limit; a device such as ``/dev/null``). An earlier file at
          ``path`` is not taken for a success: ``EQSAVE_IERR`` reports the
          failure itself. Measured with gfortran 15 on macOS under a file
          size limit: a save that leaves a short file also leaves one
          descriptor open in the process.
        * :class:`EqlibError`: the handle is closed, the library does not
          export ``eq_save``, or no non-empty file exists after a call
          that reported success.
        """
        if self._closed:
            raise EqlibError("save on closed Eq")
        try:
            fn = self._lib.eq_save
        except AttributeError as exc:
            raise EqlibError(
                "libeqapi.so does not export eq_save; "
                "rebuild the shared library (`make -C eq libeqapi.so`)."
            ) from exc
        path = os.fspath(path)
        if isinstance(path, str) and path != path.rstrip(" "):
            raise EqlibInvalidParamError(
                f"eq_save: the path {path!r} ends in a blank, which a "
                "Fortran file name cannot keep"
            )
        self.set_param_str("KNAMEQ", path)
        rc = fn()
        raise_for_rc("eq_save", rc)
        # eq_save checked this already; a second look from this side.
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise EqlibError(
                f"eq_save reported success but no non-empty file exists at "
                f"{path!r} (check the directory exists and is writable)"
            )

    def get_state(self) -> EqState:
        """Copy the current EQ state into an :class:`EqState`."""
        if self._closed:
            raise EqlibError("get_state on closed Eq")
        c = _ffi.EqStateC()
        rc = self._lib.eq_get_state(ctypes.byref(c))
        raise_for_rc("eq_get_state", rc)
        return EqState.from_c(c)

    # --- validation (Issue #143) ---------------------------------------
    def validate(self) -> List[EqDiagEntryPy]:
        """Run pre-run cross-parameter validation.

        Returns the list of diagnostics produced by ``eq_validate``
        (read-only against the current eq state). The recommended
        workflow is::

            eq.set_params(...)
            diags = eq.validate()
            if diags:
                # surface / fix / re-validate, then run
                ...
            eq.run()

        Return-code mapping (``eq_api_validate`` contract):

        * ``EQ_OK`` (0)            -> empty list (clean state)
        * ``EQ_ERR_INVALID`` (1)   -> non-empty list (the diagnostics
          themselves are the payload; ``rc == 1`` only signals
          "diagnostics present" so callers do not need to inspect the
          C-level return code)
        * ``EQ_ERR_NOT_INIT`` (2)  -> :class:`EqlibNotInitializedError`

        Older builds without ``eq_validate`` raise :class:`EqlibError`
        (rebuild via ``make -C eq libeqapi.so``). The method does not
        modify any eq state.
        """
        if self._closed:
            raise EqlibError("validate on closed Eq")
        try:
            fn = self._lib.eq_validate
        except AttributeError as exc:
            raise EqlibError(
                "libeqapi.so does not export eq_validate; "
                "rebuild the shared library after the #143 PR."
            ) from exc

        cap = _ffi.EQ_DIAG_DEFAULT_CAP
        buf = (_ffi.EqDiagEntry * cap)()
        ndiag = ctypes.c_int(0)
        rc = fn(buf, cap, ctypes.byref(ndiag))

        # Contract: rc==2 (NOT_INIT) is the only one that maps to an
        # exception; rc==0 and rc==1 both return the list (empty / not).
        if rc == _ffi.EQ_ERR_NOT_INIT:
            raise EqlibNotInitializedError(f"eq_validate: rc={rc}")
        if rc not in (_ffi.EQ_OK, _ffi.EQ_ERR_INVALID):
            # Defensive: future codes should not silently masquerade
            # as success. Reuse the central rc -> exception mapping.
            raise_for_rc("eq_validate", rc)

        n = int(ndiag.value)
        # Fortran push_diag increments nlocal past diag_cap but skips the
        # write (eq_api.f90:393-395), so ndiag_out can exceed cap. Clamp
        # and warn so the caller knows results are truncated instead of
        # IndexError-ing off the end of the ctypes buffer.
        if n > cap:
            import warnings
            warnings.warn(
                f"eq_validate produced {n} diagnostics but buffer capacity "
                f"is {cap}; results are truncated. Increase "
                f"eqlib._ffi.EQ_DIAG_DEFAULT_CAP.",
                RuntimeWarning,
                stacklevel=2,
            )
            n = cap
        out: List[EqDiagEntryPy] = []
        for i in range(n):
            entry = buf[i]
            param = entry.param.decode("ascii", errors="replace").rstrip("\x00")
            message = entry.msg.decode("ascii", errors="replace").rstrip("\x00")
            out.append(EqDiagEntryPy(
                param=param,
                code=int(entry.code),
                message=message,
            ))
        return out


__all__ = ["Eq", "EqDiagCode", "EqDiagEntryPy"]
