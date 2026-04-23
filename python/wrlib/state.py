"""Pythonic snapshot of the C ``wr_state_t`` structure.

:class:`WrState` is a plain :mod:`dataclasses` view. No numpy
dependency; per-ray and profile fields are Python lists so
``to_dict()`` is JSON-serialisable out of the box. The ``to_dict()``
layout matches the Phase 0 baseline ``extract_wr_metrics.py`` output so
``compare_metrics.py`` can be reused verbatim for L-6 regression
tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import _ffi
from ._ffi import WrStateC
from .errors import WrlibStateError


# Scalar (global) pwrmax field names in canonical order. These are the
# four scalar members of ``wr_state_t`` (see wr/wr_api.h). The runtime
# dimensions nraymax/nrsmax/nrlmax are carried as dedicated attributes
# on WrState, not in ``scalars``.
SCALAR_FIELDS = (
    "pos_pwrmax_rs", "pwrmax_rs",
    "pos_pwrmax_rl", "pwrmax_rl",
)

_DIM_BOUNDS = (
    ("nraymax", "WR_MAX_NRAYMAX", _ffi.WR_MAX_NRAYMAX),
    ("nrsmax", "WR_MAX_NRSMAX", _ffi.WR_MAX_NRSMAX),
    ("nrlmax", "WR_MAX_NRLMAX", _ffi.WR_MAX_NRLMAX),
)


def _checked_dim(s: WrStateC, field_name: str, max_name: str, max_value: int) -> int:
    value = int(getattr(s, field_name))
    if value < 0:
        raise WrlibStateError(
            f"WrState.from_c dimension {field_name}={value} is negative"
        )
    if value > max_value:
        raise WrlibStateError(
            f"WrState.from_c dimension {field_name}={value} exceeds "
            f"{max_name}={max_value}"
        )
    return value


@dataclass
class WrState:
    """Pure-Python snapshot of ``wr_state_t``.

    Attributes:
        nraymax:            number of rays actually in use
        nrsmax:             minor-radius profile size actually in use
        nrlmax:             major-radius profile size actually in use
        scalars:            dict of 4 global peak-power scalars
        nstp_end:           [nraymax] end-step index for each ray
        pos_pwrmax_rs_nray: [nraymax] per-ray peak-power position (rs)
        pwrmax_rs_nray:     [nraymax] per-ray peak-power value   (rs)
        pos_pwrmax_rl_nray: [nraymax] per-ray peak-power position (rl)
        pwrmax_rl_nray:     [nraymax] per-ray peak-power value   (rl)
        rays_end:           [nraymax][NRAY_EQ] end-state of each ray
        pos_nrs / pwr_nrs:  [nrsmax] minor-radius profile
        pos_nrl / pwr_nrl:  [nrlmax] major-radius profile
    """

    nraymax: int
    nrsmax: int
    nrlmax: int
    scalars: Dict[str, float]
    nstp_end: List[int] = field(default_factory=list)
    pos_pwrmax_rs_nray: List[float] = field(default_factory=list)
    pwrmax_rs_nray: List[float] = field(default_factory=list)
    pos_pwrmax_rl_nray: List[float] = field(default_factory=list)
    pwrmax_rl_nray: List[float] = field(default_factory=list)
    rays_end: List[List[float]] = field(default_factory=list)
    pos_nrs: List[float] = field(default_factory=list)
    pwr_nrs: List[float] = field(default_factory=list)
    pos_nrl: List[float] = field(default_factory=list)
    pwr_nrl: List[float] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: WrStateC) -> "WrState":
        """Build a WrState from a populated :class:`WrStateC`.

        Only the ``[0:nraymax]`` / ``[0:nrsmax]`` / ``[0:nrlmax]``
        slice is copied out; trailing padding (up to WR_MAX_*) is
        ignored.
        """
        dims = {
            field_name: _checked_dim(s, field_name, max_name, max_value)
            for field_name, max_name, max_value in _DIM_BOUNDS
        }
        nray = dims["nraymax"]
        nrs = dims["nrsmax"]
        nrl = dims["nrlmax"]
        scalars = {k: float(getattr(s, k)) for k in SCALAR_FIELDS}
        # nray-sized arrays
        nstp_end = [int(s.nstp_end[i]) for i in range(nray)]
        pos_pwrmax_rs_nray = [float(s.pos_pwrmax_rs_nray[i]) for i in range(nray)]
        pwrmax_rs_nray = [float(s.pwrmax_rs_nray[i]) for i in range(nray)]
        pos_pwrmax_rl_nray = [float(s.pos_pwrmax_rl_nray[i]) for i in range(nray)]
        pwrmax_rl_nray = [float(s.pwrmax_rl_nray[i]) for i in range(nray)]
        # rays_end is [NRAYMAX][NRAY_EQ]; all 9 eq-components are always copied.
        from ._ffi import WR_MAX_NRAY_EQ
        rays_end = [
            [float(s.rays_end[i][j]) for j in range(WR_MAX_NRAY_EQ)]
            for i in range(nray)
        ]
        # profiles
        pos_nrs = [float(s.pos_nrs[i]) for i in range(nrs)]
        pwr_nrs = [float(s.pwr_nrs[i]) for i in range(nrs)]
        pos_nrl = [float(s.pos_nrl[i]) for i in range(nrl)]
        pwr_nrl = [float(s.pwr_nrl[i]) for i in range(nrl)]
        return cls(
            nraymax=nray,
            nrsmax=nrs,
            nrlmax=nrl,
            scalars=scalars,
            nstp_end=nstp_end,
            pos_pwrmax_rs_nray=pos_pwrmax_rs_nray,
            pwrmax_rs_nray=pwrmax_rs_nray,
            pos_pwrmax_rl_nray=pos_pwrmax_rl_nray,
            pwrmax_rl_nray=pwrmax_rl_nray,
            rays_end=rays_end,
            pos_nrs=pos_nrs,
            pwr_nrs=pwr_nrs,
            pos_nrl=pos_nrl,
            pwr_nrl=pwr_nrl,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict matching the Phase 0 baseline JSON layout.

        Shape mirrors the WR baseline extractor so the same
        ``compare_metrics.py`` tool can diff Layer-2 (direct C ABI) and
        Layer-3 (Python) outputs against the Layer-1 baseline.
        """
        return {
            "NRAYMAX": self.nraymax,
            "NRSMAX": self.nrsmax,
            "NRLMAX": self.nrlmax,
            "scalars": dict(self.scalars),
            "rays": [
                {
                    "NRAY": i + 1,
                    "nstp_end": self.nstp_end[i],
                    "pos_pwrmax_rs": self.pos_pwrmax_rs_nray[i],
                    "pwrmax_rs": self.pwrmax_rs_nray[i],
                    "pos_pwrmax_rl": self.pos_pwrmax_rl_nray[i],
                    "pwrmax_rl": self.pwrmax_rl_nray[i],
                    "rays_end": list(self.rays_end[i]),
                }
                for i in range(self.nraymax)
            ],
            "profile_rs": [
                {"NRS": i + 1, "pos": self.pos_nrs[i], "pwr": self.pwr_nrs[i]}
                for i in range(self.nrsmax)
            ],
            "profile_rl": [
                {"NRL": i + 1, "pos": self.pos_nrl[i], "pwr": self.pwr_nrl[i]}
                for i in range(self.nrlmax)
            ],
        }


__all__ = ["WrState", "SCALAR_FIELDS"]
