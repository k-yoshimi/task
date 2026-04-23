"""trlib: Python ctypes wrapper around ``tr/libtrapi.so``.

Two-layer package:

* :mod:`trlib._ffi` is a thin ctypes binding that mirrors
  ``tr/tr_api.h`` exactly (``TrStateC`` structure + prototypes).
* :mod:`trlib.trlib` provides the high-level :class:`Trlib` context
  manager and :class:`~trlib.state.TrState` dataclass.

Example::

    from trlib import Trlib
    with Trlib() as tr:
        tr.run(0)
        state = tr.get_state()
"""
from .trlib import Trlib, TrDiagCode, TrDiagEntryPy
from .state import TrState
from .errors import (
    TrlibError,
    TrlibInitError,
    TrlibParamError,
    TrlibStateError,
    TrlibRunError,
    TrlibNotImplementedError,
    # Aliases kept for spec-style naming.
    TrLibError,
    TrLibInvalidParam,
    TrLibNotInitialized,
    TrLibCalculationFailed,
    TrLibNotImplemented,
    raise_for_ierr,
)

__all__ = [
    "Trlib",
    "TrDiagCode",
    "TrDiagEntryPy",
    "TrState",
    "TrlibError",
    "TrlibInitError",
    "TrlibParamError",
    "TrlibStateError",
    "TrlibRunError",
    "TrlibNotImplementedError",
    "TrLibError",
    "TrLibInvalidParam",
    "TrLibNotInitialized",
    "TrLibCalculationFailed",
    "TrLibNotImplemented",
    "raise_for_ierr",
]
