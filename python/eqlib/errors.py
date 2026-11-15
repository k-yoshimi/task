"""Exception hierarchy for eqlib.

Mirrors the ``enum eq_error`` codes declared in ``eq/eq_api.h``:

    EQ_OK              = 0
    EQ_ERR_INVALID     = 1  (invalid parameter name or value)
    EQ_ERR_NOT_INIT    = 2  (eq_init has not been called yet)
    EQ_ERR_CALC_FAILED = 3  (eq_run / eq_get_state failed)
    EQ_ERR_NOT_IMPL    = 4  (eq_run: a mode above 1)

The same hierarchy is used by trlib / tilib so test patterns can be
shared verbatim. ``raise_for_rc`` (and the alias ``raise_for_ierr``)
maps non-zero return codes to the matching subclass.
"""
from __future__ import annotations


class EqlibError(Exception):
    """Base class for all eqlib errors."""


class EqlibInitError(EqlibError):
    """Initialization / finalize lifecycle violation."""


class EqlibInvalidParamError(EqlibError):
    """Invalid parameter name or value (rc == 1).

    Common cause for EQ specifically: passing the bare name ``"PSIB"``
    without a subscript. ``PSIB`` is a 0-origin array (``PSIB(0:5)``)
    and the L-3 registry rejects bare ``"PSIB"`` with idx == -1; use
    ``set_param("PSIB[0]", v)`` instead.
    """


class EqlibNotInitializedError(EqlibError):
    """Library not initialized (rc == 2)."""


class EqlibCalculationFailedError(EqlibError):
    """eq_run / eq_get_state returned non-zero (rc == 3)."""


class EqlibNotImplementedError(EqlibError):
    """The mode is not implemented (rc == 4).

    ``eq_run(mode)`` returns this for a mode above 1; modes 0 (the
    analytic solve, EQCALC + EQCALQ) and 1 (the file load via
    equnit::eq_load) are implemented.
    """


# Spec-style aliases.
EqLibError = EqlibError
EqLibInvalidParam = EqlibInvalidParamError
EqLibNotInitialized = EqlibNotInitializedError
EqLibCalculationFailed = EqlibCalculationFailedError
EqLibNotImplemented = EqlibNotImplementedError


_CODE_MAP = {
    1: EqlibInvalidParamError,
    2: EqlibNotInitializedError,
    3: EqlibCalculationFailedError,
    4: EqlibNotImplementedError,
}


def raise_for_rc(func: str, rc: int) -> None:
    """Raise the matching subclass when ``rc != 0``.

    Unknown codes fall back to the generic :class:`EqlibError`.
    """
    if rc == 0:
        return
    cls = _CODE_MAP.get(int(rc), EqlibError)
    raise cls(f"{func}: rc={rc}")


# Alias matching the trlib / tilib naming.
raise_for_ierr = raise_for_rc


__all__ = [
    "EqlibError",
    "EqlibInitError",
    "EqlibInvalidParamError",
    "EqlibNotInitializedError",
    "EqlibCalculationFailedError",
    "EqlibNotImplementedError",
    "EqlibAbiError",
    "EqLibError",
    "EqLibInvalidParam",
    "EqLibNotInitialized",
    "EqLibCalculationFailed",
    "EqLibNotImplemented",
    "raise_for_rc",
    "raise_for_ierr",
]

class EqlibAbiError(EqlibError):
    """libeqapi.so's eq_state_t layout is not the one this wrapper has (#246).

    Raised by :func:`eqlib._ffi.load_library` before any struct is passed:
    the library does not export ``eq_state_abi_version`` / ``eq_state_size``
    (built before the layout check), or its version or sizeof differs from
    ``eqlib._ffi.EqStateC``. The message names the fix (rebuild the
    library, or update the wrapper).
    """
