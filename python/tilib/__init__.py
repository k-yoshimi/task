"""tilib: Python ctypes wrapper around ``ti/libtiapi.so``.

Two-layer package:

* :mod:`tilib._ffi` is a thin ctypes binding that mirrors
  ``ti/ti_api.h`` exactly (``TiStateC`` structure + prototypes).
* :mod:`tilib.tilib` provides the high-level :class:`TiLib` context
  manager and :class:`~tilib.state.TiState` dataclass.

Example::

    from tilib import TiLib
    with TiLib() as ti:
        ti.run(0)
        state = ti.get_state()
"""
from .tilib import TiLib, Tilib
from .state import TiState
from .errors import (
    TilibError,
    TilibInitError,
    TilibParamError,
    TilibStateError,
    TilibRunError,
    TilibNotImplementedError,
    # Aliases kept for spec-style naming.
    TiLibError,
    TiLibInvalidParam,
    TiLibNotInitialized,
    TiLibCalculationFailed,
    TiLibNotImplemented,
    raise_for_ierr,
)

__all__ = [
    "TiLib",
    "Tilib",
    "TiState",
    "TilibError",
    "TilibInitError",
    "TilibParamError",
    "TilibStateError",
    "TilibRunError",
    "TilibNotImplementedError",
    "TiLibError",
    "TiLibInvalidParam",
    "TiLibNotInitialized",
    "TiLibCalculationFailed",
    "TiLibNotImplemented",
    "raise_for_ierr",
]
