"""fplib: Python ctypes wrapper around ``fp/libfpapi.so``.

Two-layer package:

* :mod:`fplib._ffi` is a thin ctypes binding that mirrors
  ``fp/fp_api.h`` exactly (:class:`FpStateC` + 5 prototypes).
* :mod:`fplib.fplib` provides the high-level :class:`Fplib` context
  manager and :class:`~fplib.state.FpState` dataclass.

Example::

    from fplib import Fplib
    with Fplib() as fp:
        fp.run(0)
        state = fp.get_state()
"""
from .fplib import Fplib
from .state import FpState
from .errors import (
    FplibError,
    FplibInitError,
    FplibInvalidParamError,
    FplibNotInitError,
    FplibCalcFailedError,
    FplibNotImplementedError,
    FplibOverflowError,
    # Aliases kept for spec-style naming.
    FpLibError,
    FpLibInvalidParam,
    FpLibNotInitialized,
    FpLibCalculationFailed,
    FpLibNotImplemented,
    raise_for_rc,
    raise_for_code,
)

__all__ = [
    "Fplib",
    "FpState",
    "FplibError",
    "FplibInitError",
    "FplibInvalidParamError",
    "FplibNotInitError",
    "FplibCalcFailedError",
    "FplibNotImplementedError",
    "FplibOverflowError",
    "FpLibError",
    "FpLibInvalidParam",
    "FpLibNotInitialized",
    "FpLibCalculationFailed",
    "FpLibNotImplemented",
    "raise_for_rc",
    "raise_for_code",
]
