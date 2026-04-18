"""Exception hierarchy for fplib.

Mirrors the ``enum fp_error`` codes declared in ``fp/fp_api.h``:

    FP_OK              = 0
    FP_ERR_INVALID     = 1  (invalid parameter name or value)
    FP_ERR_NOT_INIT    = 2  (fp_init has not been called yet)
    FP_ERR_CALC_FAILED = 3  (calculation / initialization failed)
    FP_ERR_NOT_IMPL    = 4  (reserved / was L-2 stub return)
"""
from __future__ import annotations


class FplibError(Exception):
    """Base class for all fplib errors."""


class FplibInitError(FplibError):
    """Initialization failed (fp_init returned non-zero)."""


class FplibInvalidParamError(FplibError):
    """Invalid parameter name or value (rc == 1)."""


class FplibNotInitError(FplibError):
    """Library not initialized (rc == 2)."""


class FplibCalcFailedError(FplibError):
    """fp_run / fp_get_state failed (rc == 3)."""


class FplibNotImplementedError(FplibError):
    """Entry point is a stub and not yet implemented (rc == 4)."""


# Aliases preferred by some callers / spec drafts.
FpLibError = FplibError
FpLibInvalidParam = FplibInvalidParamError
FpLibNotInitialized = FplibNotInitError
FpLibCalculationFailed = FplibCalcFailedError
FpLibNotImplemented = FplibNotImplementedError

# Backwards-compatible aliases noted in the plan.
FplibOverflowError = FplibCalcFailedError


_CODE_MAP = {
    1: FplibInvalidParamError,
    2: FplibNotInitError,
    3: FplibCalcFailedError,
    4: FplibNotImplementedError,
}


def raise_for_rc(func: str, rc: int) -> None:
    """Raise the matching subclass when ``rc != 0``.

    Unknown codes fall back to the generic :class:`FplibError`.
    """
    if rc == 0:
        return
    cls = _CODE_MAP.get(int(rc), FplibError)
    raise cls(f"{func}: rc={rc}")


# Also export under the plan-draft name for parity with older docs.
raise_for_code = raise_for_rc
