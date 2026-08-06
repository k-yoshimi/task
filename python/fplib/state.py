"""Pythonic snapshot of the C ``fp_state_t`` structure.

:class:`FpState` is a plain :mod:`dataclasses` view. No numpy dependency;
profile fields are Python nested lists so ``to_dict()`` is JSON-serialisable
out of the box. The ``to_dict()`` layout mirrors the tr wrapper's
``TrState.to_dict()`` shape so regression tooling can be shared.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import _ffi
from ._ffi import FpStateC
from .errors import FplibNotInitError


# Profile array names in canonical order. These are the 6 2-D arrays
# declared in fp_state_t: RNT, RWT, RTT, RJT, RPCT, RPWT.
PROFILE_FIELDS = ("RNT", "RWT", "RTT", "RJT", "RPCT", "RPWT")

# Global (volume-integrated) scalar field names, in fp_state_t order.
# Grouped into the ``scalars`` dict by ``to_dict()`` so the FP wire
# format has the same top-level shape as TrState.to_dict().
#
# Units, traced to the Fortran (all species-summed at the latest NTG1;
# the per-species PxT accumulators are built in fp/fpsave.f90:106-147):
#   TOTAL_IP         [MA]  sum PIT;  PIT = sum_NR RJS*VOLR / (2*pi*RR)
#                          -- RJS carries the *1.D-6 A->MA conversion
#                          in fp/fpsave.f90:1310; printed as
#                          "total plasma current [MA]" (fpsave.f90:311).
#   STORED_ENERGY    [MJ]  sum PWT;  PWT = sum_NR RWS*VOLR
#                          -- RWS is *1.D-6 J->MJ, fp/fpsave.f90:1377;
#                          printed as the W column of fpsave.f90:252.
#   COLLISION_POWER  [MW]  sum PPCT; RPCS is *1.D-6, fp/fpsave.f90:1509;
#                          printed at fpsave.f90:307.
#   ABSORPTION_POWER [MW]  sum PPWT; RPWS is *1.D-6, fp/fpsave.f90:1510;
#                          printed at fpsave.f90:305.
#   ABSORPTION_WR    [MW]  sum PWRT (ray-tracing share of the above).
#   ABSORPTION_WM    [MW]  sum PWMT (full-wave share of the above).
#   PLASMA_VOLUME    [m^3] TVOLR = sum_NR VOLR, fp/fpprep.f90:231-234;
#                          printed in the DEVICE banner, fpprep.f90:237.
#
# All seven are zero until the first ``run()`` (the Fortran accumulators
# only exist after fp_prep, and only carry a sample once FPSGLB has
# bumped NTG1).
SCALAR_FIELDS = (
    "TOTAL_IP",
    "STORED_ENERGY",
    "COLLISION_POWER",
    "ABSORPTION_POWER",
    "ABSORPTION_WR",
    "ABSORPTION_WM",
    "PLASMA_VOLUME",
)
_DIM_BOUNDS = (
    ("nrmax", "FP_MAX_NRMAX", _ffi.FP_MAX_NRMAX),
    ("nsamax", "FP_MAX_NSAMAX", _ffi.FP_MAX_NSAMAX),
)


def _checked_dim(s: FpStateC, field_name: str, max_name: str, max_value: int) -> int:
    value = int(getattr(s, field_name))
    if value < 0:
        raise FplibNotInitError(
            f"FpState.from_c dimension {field_name}={value} is negative"
        )
    if value > max_value:
        raise FplibNotInitError(
            f"FpState.from_c dimension {field_name}={value} exceeds "
            f"{max_name}={max_value}"
        )
    return value


@dataclass
class FpState:
    """Pure-Python snapshot of ``fp_state_t``.

    Attributes:
        nrmax:  number of radial points actually in use
        nsamax: number of kinetic species actually in use
        npmax:  number of momentum points
        nthmax: number of pitch-angle points
        ntg2:   long-time-axis counter
        timefp: simulation time (s)
        RNT/RWT/RTT/RJT/RPCT/RPWT:
            [nsamax][nrmax] profile arrays, truncated to the runtime
            extents (FP_MAX_NSAMAX x FP_MAX_NRMAX padding is dropped).
        scalars:
            dict of the 7 volume-integrated global quantities
            (see :data:`SCALAR_FIELDS` for names and units).
    """

    nrmax: int
    nsamax: int
    npmax: int
    nthmax: int
    ntg2: int
    timefp: float
    RNT: List[List[float]] = field(default_factory=list)
    RWT: List[List[float]] = field(default_factory=list)
    RTT: List[List[float]] = field(default_factory=list)
    RJT: List[List[float]] = field(default_factory=list)
    RPCT: List[List[float]] = field(default_factory=list)
    RPWT: List[List[float]] = field(default_factory=list)
    scalars: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_c(cls, s: FpStateC) -> "FpState":
        """Build an FpState from a populated :class:`FpStateC`.

        Only the ``[0:nsamax][0:nrmax]`` slice is copied out; the trailing
        padding (up to FP_MAX_*) is ignored.
        """
        dims = {
            field_name: _checked_dim(s, field_name, max_name, max_value)
            for field_name, max_name, max_value in _DIM_BOUNDS
        }
        nr = dims["nrmax"]
        nsa = dims["nsamax"]

        def _slice(arr_2d):
            # arr_2d shape: [FP_MAX_NSAMAX][FP_MAX_NRMAX].
            return [[float(arr_2d[ns][ir]) for ir in range(nr)]
                    for ns in range(nsa)]

        return cls(
            nrmax=nr,
            nsamax=nsa,
            npmax=int(s.npmax),
            nthmax=int(s.nthmax),
            ntg2=int(s.ntg2),
            timefp=float(s.timefp),
            RNT=_slice(s.RNT),
            RWT=_slice(s.RWT),
            RTT=_slice(s.RTT),
            RJT=_slice(s.RJT),
            RPCT=_slice(s.RPCT),
            RPWT=_slice(s.RPWT),
            scalars={k: float(getattr(s, k)) for k in SCALAR_FIELDS},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict (JSON-safe, no numpy types).

        Layout:

            {
              "NRMAX": int, "NSAMAX": int, "NPMAX": int, "NTHMAX": int,
              "NTG2": int, "TIMEFP": float,
              "scalars": {"TOTAL_IP": float, ...},  # 7 global scalars
              "profile": [  # per species, length NSAMAX
                 {"NSA": 1, "RNT": [..NR..], "RWT": [..], "RTT": [..],
                  "RJT": [..], "RPCT": [..], "RPWT": [..]},
                 ...
              ],
            }

        The top-level ``scalars`` key mirrors ``TrState.to_dict()`` so
        consumers (the MCP bridge's steady-state detection, plot
        renderers, regression tooling) can treat fp and tr states the
        same way.
        """
        return {
            "NRMAX": self.nrmax,
            "NSAMAX": self.nsamax,
            "NPMAX": self.npmax,
            "NTHMAX": self.nthmax,
            "NTG2": self.ntg2,
            "TIMEFP": self.timefp,
            "scalars": dict(self.scalars),
            "profile": [
                {
                    "NSA": ns + 1,
                    "RNT": list(self.RNT[ns]),
                    "RWT": list(self.RWT[ns]),
                    "RTT": list(self.RTT[ns]),
                    "RJT": list(self.RJT[ns]),
                    "RPCT": list(self.RPCT[ns]),
                    "RPWT": list(self.RPWT[ns]),
                }
                for ns in range(self.nsamax)
            ],
        }


__all__ = ["FpState", "PROFILE_FIELDS", "SCALAR_FIELDS"]
