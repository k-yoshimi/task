"""Pythonic snapshot of the C ``tr_state_t`` structure.

:class:`TrState` is a plain :mod:`dataclasses` view. No numpy dependency;
profile fields are Python lists so ``to_dict()`` is JSON-serialisable out
of the box. The ``to_dict()`` layout matches the Phase 0 baseline
``extract_tr_metrics.py`` output so ``compare_metrics.py`` can be reused
verbatim for L-6 regression tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import _ffi
from ._ffi import TrStateC
from .errors import TrlibStateError


# Scalar field names in canonical order. Matches the scalar members of
# ``tr_state_t`` (see tr/tr_api.h). ``nt/nrmax/nsmax`` are carried as
# dedicated attributes on TrState, not in ``scalars``.
SCALAR_FIELDS = (
    "T", "WPT", "AJT", "Q0",
    "BETA0", "BETAP0", "BETAA", "BETAN",
    "TAUE1", "TAUE2", "ZEFF0",
    "ALI", "RQ1",
)

_DIM_BOUNDS = (
    ("nrmax", "TR_MAX_NRMAX", _ffi.TR_MAX_NRMAX),
    ("nsmax", "TR_MAX_NSMAX", _ffi.TR_MAX_NSMAX),
)


def _checked_dim(s: TrStateC, field_name: str, max_name: str, max_value: int) -> int:
    value = int(getattr(s, field_name))
    if value < 0:
        raise TrlibStateError(
            f"TrState.from_c dimension {field_name}={value} is negative"
        )
    if value > max_value:
        raise TrlibStateError(
            f"TrState.from_c dimension {field_name}={value} exceeds "
            f"{max_name}={max_value}"
        )
    return value


@dataclass
class TrState:
    """Pure-Python snapshot of ``tr_state_t``.

    Attributes:
        nt:      time-step counter
        nrmax:   number of radial points actually in use
        nsmax:   number of species actually in use
        scalars: dict of 13 scalar plasma quantities (T, WPT, ...)
        RN:      [nrmax][nsmax] density profile
        RT:      [nrmax][nsmax] temperature profile
        AJ:      [nrmax] current profile
        QP:      [nrmax] safety-factor profile
    """

    nt: int
    nrmax: int
    nsmax: int
    scalars: Dict[str, float]
    RN: List[List[float]] = field(default_factory=list)
    RT: List[List[float]] = field(default_factory=list)
    AJ: List[float] = field(default_factory=list)
    QP: List[float] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: TrStateC) -> "TrState":
        """Build a TrState from a populated :class:`TrStateC`.

        Only the ``[0:nrmax]`` / ``[0:nsmax]`` slice is copied out; the
        trailing padding (up to TR_MAX_*) is ignored.
        """
        dims = {
            field_name: _checked_dim(s, field_name, max_name, max_value)
            for field_name, max_name, max_value in _DIM_BOUNDS
        }
        nr = dims["nrmax"]
        ns = dims["nsmax"]
        scalars = {k: float(getattr(s, k)) for k in SCALAR_FIELDS}
        rn = [[float(s.RN[i][j]) for j in range(ns)] for i in range(nr)]
        rt = [[float(s.RT[i][j]) for j in range(ns)] for i in range(nr)]
        aj = [float(s.AJ[i]) for i in range(nr)]
        qp = [float(s.QP[i]) for i in range(nr)]
        return cls(
            nt=int(s.nt),
            nrmax=nr,
            nsmax=ns,
            scalars=scalars,
            RN=rn,
            RT=rt,
            AJ=aj,
            QP=qp,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict matching the Phase 0 baseline JSON layout.

        The format intentionally mirrors ``extract_tr_metrics.py`` so
        the same ``compare_metrics.py`` tool can diff Layer-2 (direct C
        ABI) and Layer-3 (Python) outputs against the Layer-1 baseline.
        """
        return {
            "NT": self.nt,
            "NRMAX": self.nrmax,
            "NSMAX": self.nsmax,
            "scalars": dict(self.scalars),
            "profile": [
                {
                    "NR": i + 1,
                    "RN": list(self.RN[i]),
                    "RT": list(self.RT[i]),
                    "AJ": self.AJ[i],
                    "QP": self.QP[i],
                }
                for i in range(self.nrmax)
            ],
        }


__all__ = ["TrState", "SCALAR_FIELDS"]
