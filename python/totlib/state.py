"""Pythonic snapshot of the C ``tot_state_t`` structure.

:class:`TotState` is a plain :mod:`dataclasses` view. No numpy
dependency; profile fields are Python lists so ``to_dict()`` is
JSON-serialisable out of the box. The ``to_dict()`` layout matches the
``trlib.TrState`` baseline so L-6 cross-comparison can reuse the same
``compare_metrics.py`` tooling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ._ffi import TotStateC


# Scalar field names in canonical order. Matches the scalar members of
# ``tot_state_t`` (see tot/tot_api.h). The presence flags
# (tr_present / ti_present / fp_present / wr_present) and the grid
# counters (nt / nrmax / nsmax) are carried as dedicated attributes on
# TotState, not in ``scalars``.
SCALAR_FIELDS = (
    "T", "WPT", "AJT", "Q0",
    "BETA0", "BETAP0", "BETAA", "BETAN",
    "TAUE1", "TAUE2", "ZEFF0",
    "ALI", "RQ1",
)


@dataclass
class TotState:
    """Pure-Python snapshot of ``tot_state_t``.

    Attributes:
        tr_present: 1 if the TR sub-module is initialized, else 0
        ti_present: 1 if the TI sub-module is initialized, else 0
        fp_present: 1 if the FP sub-module is initialized, else 0
        wr_present: 1 if the WR sub-module is initialized, else 0
        nt:         time-step counter (TR-authoritative)
        nrmax:      number of radial points actually in use
        nsmax:      number of species actually in use
        scalars:    dict of 13 integrated plasma scalars
        RN:         [nrmax][nsmax] density profile
        RT:         [nrmax][nsmax] temperature profile
        AJ:         [nrmax] current profile
        QP:         [nrmax] safety-factor profile
    """

    tr_present: int
    ti_present: int
    fp_present: int
    wr_present: int
    nt: int
    nrmax: int
    nsmax: int
    scalars: Dict[str, float] = field(default_factory=dict)
    RN: List[List[float]] = field(default_factory=list)
    RT: List[List[float]] = field(default_factory=list)
    AJ: List[float] = field(default_factory=list)
    QP: List[float] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: TotStateC) -> "TotState":
        """Build a TotState from a populated :class:`TotStateC`.

        Only the active runtime slice (``[0:nrmax]`` / ``[0:nsmax]``)
        is copied; the trailing zero-padding (up to TOT_MAX_*) is
        ignored so callers never see fake zeros at the tail of a
        profile. At L-3 / L-4 stub scope ``nrmax`` and ``nsmax`` are 0
        and the profiles come back as empty lists, which is correct.
        """
        nr = int(s.nrmax)
        ns = int(s.nsmax)
        scalars = {k: float(getattr(s, k)) for k in SCALAR_FIELDS}
        rn = [[float(s.RN[i][j]) for j in range(ns)] for i in range(nr)]
        rt = [[float(s.RT[i][j]) for j in range(ns)] for i in range(nr)]
        aj = [float(s.AJ[i]) for i in range(nr)]
        qp = [float(s.QP[i]) for i in range(nr)]
        return cls(
            tr_present=int(s.tr_present),
            ti_present=int(s.ti_present),
            fp_present=int(s.fp_present),
            wr_present=int(s.wr_present),
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
        """Serialisable dict matching the Phase 0 baseline layout.

        The L-0 baseline (``test_run/baselines/tot_*/metrics.json``)
        produced by ``totregress.f90`` exposes presence flags under a
        ``modules`` sub-dict with upper-case keys
        (``TR_PRESENT`` / ``TI_PRESENT`` / ``FP_PRESENT`` /
        ``WR_PRESENT``). We surface BOTH the baseline-shape ``modules``
        key AND a sibling ``presence`` block (lower-case keys) so
        compare_metrics.py can diff against the baseline without a
        bespoke schema translator while existing callers that read
        ``presence`` keep working.
        """
        return {
            "modules": {
                "TR_PRESENT": self.tr_present,
                "TI_PRESENT": self.ti_present,
                "FP_PRESENT": self.fp_present,
                "WR_PRESENT": self.wr_present,
            },
            "presence": {
                "tr": self.tr_present,
                "ti": self.ti_present,
                "fp": self.fp_present,
                "wr": self.wr_present,
            },
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


__all__ = ["TotState", "SCALAR_FIELDS"]
