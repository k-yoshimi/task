"""Pythonic snapshot of the C ``ti_state_t`` structure.

:class:`TiState` is a plain :mod:`dataclasses` view. No numpy dependency;
profile fields are Python lists so ``to_dict()`` is JSON-serialisable out
of the box.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ._ffi import TiStateC


# Scalar field names in canonical order. ``nt/nrmax/nsa_max/nsmax`` are
# carried as dedicated attributes on TiState and not listed in the
# ``to_dict`` "scalars" block; the fields below are the physical /
# diagnostic scalars returned from ``ti_get_state``.
SCALAR_FIELDS = (
    "T",
    "residual_loop_max",
    "icount_loop_max",
    "icount_mat_max",
)


@dataclass
class TiState:
    """Pure-Python snapshot of ``ti_state_t``.

    Attributes:
        nt:                time-step counter
        nrmax:             number of radial points actually in use
        nsa_max:           number of active species actually in use
        nsmax:             number of species in TICOMM
        T:                 simulation time
        residual_loop_max: convergence diagnostic
        icount_loop_max:   outer-loop iteration count
        icount_mat_max:    matrix-solve iteration count
        RNA:               [nrmax][nsa_max] density profile
        RTA:               [nrmax][nsa_max] temperature profile
        RUA:               [nrmax][nsa_max] velocity profile
        RBP:               [nrmax] poloidal field profile
        RQP:               [nrmax] safety-factor profile
        RJP:               [nrmax] current-density profile
        ZEFF:              [nrmax] effective charge profile
        BETA:              [nrmax] beta profile
        BETAP:             [nrmax] poloidal beta profile
    """

    nt: int
    nrmax: int
    nsa_max: int
    nsmax: int
    T: float
    residual_loop_max: float
    icount_loop_max: int
    icount_mat_max: int
    RNA: List[List[float]] = field(default_factory=list)
    RTA: List[List[float]] = field(default_factory=list)
    RUA: List[List[float]] = field(default_factory=list)
    RBP: List[float] = field(default_factory=list)
    RQP: List[float] = field(default_factory=list)
    RJP: List[float] = field(default_factory=list)
    ZEFF: List[float] = field(default_factory=list)
    BETA: List[float] = field(default_factory=list)
    BETAP: List[float] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: TiStateC) -> "TiState":
        """Build a TiState from a populated :class:`TiStateC`.

        Only the ``[0:nrmax]`` / ``[0:nsa_max]`` slice is copied out;
        the trailing padding (up to TI_MAX_*) is ignored.
        """
        nr = int(s.nrmax)
        nsa = int(s.nsa_max)
        rna = [[float(s.RNA[i][j]) for j in range(nsa)] for i in range(nr)]
        rta = [[float(s.RTA[i][j]) for j in range(nsa)] for i in range(nr)]
        rua = [[float(s.RUA[i][j]) for j in range(nsa)] for i in range(nr)]
        rbp = [float(s.RBP[i]) for i in range(nr)]
        rqp = [float(s.RQP[i]) for i in range(nr)]
        rjp = [float(s.RJP[i]) for i in range(nr)]
        zeff = [float(s.ZEFF[i]) for i in range(nr)]
        beta = [float(s.BETA[i]) for i in range(nr)]
        betap = [float(s.BETAP[i]) for i in range(nr)]
        return cls(
            nt=int(s.nt),
            nrmax=nr,
            nsa_max=nsa,
            nsmax=int(s.nsmax),
            T=float(s.T),
            residual_loop_max=float(s.residual_loop_max),
            icount_loop_max=int(s.icount_loop_max),
            icount_mat_max=int(s.icount_mat_max),
            RNA=rna,
            RTA=rta,
            RUA=rua,
            RBP=rbp,
            RQP=rqp,
            RJP=rjp,
            ZEFF=zeff,
            BETA=beta,
            BETAP=betap,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict for easy diffing / JSON dumps.

        ``scalars`` groups the physical/diagnostic scalars so downstream
        tools can treat profile rows and scalars uniformly.
        """
        return {
            "NT": self.nt,
            "NRMAX": self.nrmax,
            "NSA_MAX": self.nsa_max,
            "NSMAX": self.nsmax,
            "scalars": {
                "T": self.T,
                "residual_loop_max": self.residual_loop_max,
                "icount_loop_max": self.icount_loop_max,
                "icount_mat_max": self.icount_mat_max,
            },
            "profile": [
                {
                    "NR": i + 1,
                    "RNA": list(self.RNA[i]),
                    "RTA": list(self.RTA[i]),
                    "RUA": list(self.RUA[i]),
                    "RBP": self.RBP[i],
                    "RQP": self.RQP[i],
                    "RJP": self.RJP[i],
                    "ZEFF": self.ZEFF[i],
                    "BETA": self.BETA[i],
                    "BETAP": self.BETAP[i],
                }
                for i in range(self.nrmax)
            ],
        }


__all__ = ["TiState", "SCALAR_FIELDS"]
