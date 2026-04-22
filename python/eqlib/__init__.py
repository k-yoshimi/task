"""eqlib: Python ctypes wrapper around ``eq/libeqapi.so``.

Two-layer package:

* :mod:`eqlib._ffi` is a thin ctypes binding that mirrors
  ``eq/eq_api.h`` exactly (``EqStateC`` structure + 6 entry-point
  prototypes).
* :mod:`eqlib.eqlib` provides the high-level :class:`Eq` context
  manager and :class:`~eqlib.state.EqState` dataclass.

Example::

    from eqlib import Eq

    with Eq() as eq:
        eq.set_params(RR=3.0, BB=3.0, RIP=1.0)
        eq.set_param_str("KNAMEQ", "eqdata")
        eq.run(mode=1)
        state = eq.get_state()
        print(state.scalars["raxis"])
"""
from .eqlib import Eq, EqDiagCode, EqDiagEntryPy
from .state import EqState
from .errors import (
    EqlibError,
    EqlibInitError,
    EqlibInvalidParamError,
    EqlibNotInitializedError,
    EqlibCalculationFailedError,
    EqlibNotImplementedError,
    EqLibError,
    EqLibInvalidParam,
    EqLibNotInitialized,
    EqLibCalculationFailed,
    EqLibNotImplemented,
    raise_for_rc,
    raise_for_ierr,
)

__all__ = [
    "Eq",
    "EqDiagCode",
    "EqDiagEntryPy",
    "EqState",
    "EqlibError",
    "EqlibInitError",
    "EqlibInvalidParamError",
    "EqlibNotInitializedError",
    "EqlibCalculationFailedError",
    "EqlibNotImplementedError",
    "EqLibError",
    "EqLibInvalidParam",
    "EqLibNotInitialized",
    "EqLibCalculationFailed",
    "EqLibNotImplemented",
    "raise_for_rc",
    "raise_for_ierr",
]
