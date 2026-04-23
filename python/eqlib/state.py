"""Pythonic snapshot of the C ``eq_state_t`` structure.

:class:`EqState` is a plain :mod:`dataclasses` view. No numpy
dependency; profile fields are Python lists so ``to_dict()`` is
JSON-serialisable out of the box.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import _ffi
from ._ffi import EqStateC
from .errors import EqlibNotInitializedError


# Scalar field names in canonical order. Matches the scalar members of
# ``eq_state_t`` (see eq/eq_api.h). The grid counters (nrgmax / nzgmax
# / npsmax / nrmax / nthmax / nsumax) are carried as dedicated
# attributes on EqState, not in ``scalars``.
SCALAR_FIELDS = (
    "raxis", "zaxis",
    "psi0", "psipa", "psita",
    "qaxis", "qsurf",
    "betat", "betap",
    "pvol", "raave", "ripx",
)

_DIM_BOUNDS = (
    ("nrgmax", "EQ_MAX_NRGM", _ffi.EQ_MAX_NRGM),
    ("nzgmax", "EQ_MAX_NZGM", _ffi.EQ_MAX_NZGM),
    ("npsmax", "EQ_MAX_NPSM", _ffi.EQ_MAX_NPSM),
    ("nrmax", "EQ_MAX_NRM", _ffi.EQ_MAX_NRM),
    ("nthmax", "EQ_MAX_NTHM", _ffi.EQ_MAX_NTHM),
    ("nsumax", "EQ_MAX_NSUM", _ffi.EQ_MAX_NSUM),
)


def _checked_dim(s: EqStateC, field_name: str, max_name: str, max_value: int) -> int:
    value = int(getattr(s, field_name))
    if value < 0:
        raise EqlibNotInitializedError(
            f"EqState.from_c dimension {field_name}={value} is negative"
        )
    if value > max_value:
        raise EqlibNotInitializedError(
            f"EqState.from_c dimension {field_name}={value} exceeds "
            f"{max_name}={max_value}"
        )
    return value


@dataclass
class EqState:
    """Pure-Python snapshot of ``eq_state_t``.

    Attributes:
        nrgmax:  active R-grid points (``rg`` length)
        nzgmax:  active Z-grid points (``zg`` length)
        npsmax:  active psi-surface samples (psips/ppps/ttps/qqps)
        nrmax:   active radial samples (psi-mesh, kept for downstream)
        nthmax:  active poloidal samples (kept for downstream)
        nsumax:  active surface points (kept for downstream)
        scalars: dict of 12 plasma scalars (raxis, zaxis, ...)
        rg:      [nrgmax] R-grid coordinates
        zg:      [nzgmax] Z-grid coordinates
        psips:   [npsmax] psi-surface psi values
        ppps:    [npsmax] pressure profile (psi-surface)
        ttps:    [npsmax] T (= R*B_phi) profile
        qqps:    [npsmax] q profile
    """

    nrgmax: int
    nzgmax: int
    npsmax: int
    nrmax: int
    nthmax: int
    nsumax: int
    nrvmax: int = 0
    nsgmax: int = 0
    ntgmax: int = 0
    scalars: Dict[str, float] = field(default_factory=dict)
    rg: List[float] = field(default_factory=list)
    zg: List[float] = field(default_factory=list)
    psips: List[float] = field(default_factory=list)
    ppps: List[float] = field(default_factory=list)
    ttps: List[float] = field(default_factory=list)
    qqps: List[float] = field(default_factory=list)
    # Per-NR flux-surface profile (1..nrmax). 7 columns mirror the
    # eqregress.f baseline dump: PSIP/PSIT/PPS/TTS/QPS/VPS/RST.
    profile: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: EqStateC) -> "EqState":
        """Build an EqState from a populated :class:`EqStateC`.

        Only the active runtime slice (``[0:nrgmax]`` etc.) is copied;
        the trailing zero-padding (up to EQ_MAX_*) is ignored so
        callers never see fake zeros at the tail of a profile.
        """
        dims = {
            field_name: _checked_dim(s, field_name, max_name, max_value)
            for field_name, max_name, max_value in _DIM_BOUNDS
        }
        nrg = dims["nrgmax"]
        nzg = dims["nzgmax"]
        nps = dims["npsmax"]
        scalars = {k: float(getattr(s, k)) for k in SCALAR_FIELDS}
        nrmax_i = dims["nrmax"]
        profile = [
            {
                "NR":   i + 1,
                "PSIP": float(s.profile_psip[i]),
                "PSIT": float(s.profile_psit[i]),
                "PPS":  float(s.profile_pps[i]),
                "TTS":  float(s.profile_tts[i]),
                "QPS":  float(s.profile_qps[i]),
                "VPS":  float(s.profile_vps[i]),
                "RST":  float(s.profile_rst[i]),
            }
            for i in range(nrmax_i)
        ]
        return cls(
            nrgmax=nrg,
            nzgmax=nzg,
            npsmax=nps,
            nrmax=nrmax_i,
            nthmax=dims["nthmax"],
            nsumax=dims["nsumax"],
            nrvmax=int(s.nrvmax),
            nsgmax=int(s.nsgmax),
            ntgmax=int(s.ntgmax),
            scalars=scalars,
            rg=[float(s.rg[i]) for i in range(nrg)],
            zg=[float(s.zg[i]) for i in range(nzg)],
            psips=[float(s.psips[i]) for i in range(nps)],
            ppps=[float(s.ppps[i]) for i in range(nps)],
            ttps=[float(s.ttps[i]) for i in range(nps)],
            qqps=[float(s.qqps[i]) for i in range(nps)],
            profile=profile,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict for easy diffing / JSON dumps.

        Key names are uppercase to match the Fortran convention used
        by Phase 0 baseline JSON dumps; this lets the L-6 comparator
        diff wrapper output against the reference fixture without a
        rename step.
        """
        return {
            "NRGMAX": self.nrgmax,
            "NZGMAX": self.nzgmax,
            "NPSMAX": self.npsmax,
            "NRMAX": self.nrmax,
            "NTHMAX": self.nthmax,
            "NSUMAX": self.nsumax,
            "NRVMAX": self.nrvmax,
            "NSGMAX": self.nsgmax,
            "NTGMAX": self.ntgmax,
            "scalars": {k.upper(): v for k, v in self.scalars.items()},
            "RG": list(self.rg),
            "ZG": list(self.zg),
            "PSIPS": list(self.psips),
            "PPPS": list(self.ppps),
            "TTPS": list(self.ttps),
            "QQPS": list(self.qqps),
            "profile": list(self.profile),
        }


__all__ = ["EqState", "SCALAR_FIELDS"]
