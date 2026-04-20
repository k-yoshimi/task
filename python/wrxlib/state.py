"""Pythonic snapshot of the C ``wrx_state_t`` structure.

:class:`WrxState` is a plain :mod:`dataclasses` view. No numpy
dependency; per-ray / per-species / per-bin fields are Python lists so
``to_dict()`` is JSON-serialisable out of the box. The ``to_dict()``
layout follows the Phase-0 baseline JSON shape
``{arrays, arrays2, scalars}`` (``test_run/baselines/wrx_*/metrics.json``)
so ``compare_metrics.py`` can diff Layer-1 output against the baseline
at 1e-10.

2026-04-20: schema extended to surface the per-bin radial power arrays
(pos_nrs, pos_nrl, pwr_nrs_nsa, pwr_nrl_nsa) and the per-ray pwrmax
arrays that the baseline dumps. The earlier ``{rays, profile_rs,
profile_rl}`` layout was a Layer-2-oriented view; the baseline uses the
flat ``{arrays, arrays2}`` grouping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ._ffi import WRX_MAX_NSAMAX, WrxStateC


# Scalar (global) field names in canonical order.
SCALAR_FIELDS = ("pwr_tot",)


@dataclass
class WrxState:
    """Pure-Python snapshot of ``wrx_state_t``.

    Attributes match the C struct field set; the ``to_dict()`` method
    groups them into the baseline's ``arrays`` / ``arrays2`` / ``scalars``
    layout.
    """

    # runtime dims
    nraymax: int
    nstpmax: int
    nsamax: int
    nsmax: int
    nrsmax: int
    nrlmax: int
    modelg: int
    mdlwrq: int
    # scalars
    scalars: Dict[str, float]
    # 1D arrays
    nstp_end: List[int] = field(default_factory=list)
    pwr_nray: List[float] = field(default_factory=list)
    pwr_nsa: List[float] = field(default_factory=list)
    pos_nrs: List[float] = field(default_factory=list)
    pos_nrl: List[float] = field(default_factory=list)
    # 2D arrays
    pwr_nsa_nray: List[List[float]] = field(default_factory=list)
    pwr_nrs_nsa: List[List[float]] = field(default_factory=list)
    pwr_nrl_nsa: List[List[float]] = field(default_factory=list)
    pos_pwrmax_rs_nsa_nray: List[List[float]] = field(default_factory=list)
    pos_pwrmax_rl_nsa_nray: List[List[float]] = field(default_factory=list)
    pwrmax_rs_nsa_nray: List[List[float]] = field(default_factory=list)
    pwrmax_rl_nsa_nray: List[List[float]] = field(default_factory=list)
    # legacy 1D-by-species (kept for BC)
    pos_pwrmax_rs_nsa: List[float] = field(default_factory=list)
    pwrmax_rs_nsa: List[float] = field(default_factory=list)
    pos_pwrmax_rl_nsa: List[float] = field(default_factory=list)
    pwrmax_rl_nsa: List[float] = field(default_factory=list)

    @classmethod
    def from_c(cls, s: WrxStateC) -> "WrxState":
        """Build a WrxState from a populated :class:`WrxStateC`.

        Only ``[0:nraymax]`` / ``[0:nsamax]`` / ``[0:nrsmax]`` / ``[0:nrlmax]``
        slices are copied out; trailing padding (up to ``WRX_MAX_*``) is
        ignored so zero-padded struct tails do not leak into the view.
        """
        nray = int(s.nraymax)
        nsa = int(s.nsamax)
        nrs = int(s.nrsmax)
        nrl = int(s.nrlmax)
        scalars = {k: float(getattr(s, k)) for k in SCALAR_FIELDS}
        # 1D slices
        nstp_end = [int(s.nstpmax_nray[i]) for i in range(nray)]
        pwr_nray = [float(s.pwr_nray[i]) for i in range(nray)]
        pwr_nsa = [float(s.pwr_nsa[j]) for j in range(nsa)]
        pos_nrs = [float(s.pos_nrs[i]) for i in range(nrs)]
        pos_nrl = [float(s.pos_nrl[i]) for i in range(nrl)]

        # 2D slices: C layout [<outer>][NSAMAX]; slice the active corner.
        def _2d(src, n_outer: int, n_inner: int) -> List[List[float]]:
            return [
                [float(src[i][j]) for j in range(n_inner)]
                for i in range(n_outer)
            ]

        pwr_nsa_nray = _2d(s.pwr_nsa_nray, nray, nsa)
        pwr_nrs_nsa = _2d(s.pwr_nrs_nsa, nrs, nsa)
        pwr_nrl_nsa = _2d(s.pwr_nrl_nsa, nrl, nsa)
        pos_pwrmax_rs_nsa_nray = _2d(s.pos_pwrmax_rs_nsa_nray, nray, nsa)
        pos_pwrmax_rl_nsa_nray = _2d(s.pos_pwrmax_rl_nsa_nray, nray, nsa)
        pwrmax_rs_nsa_nray = _2d(s.pwrmax_rs_nsa_nray, nray, nsa)
        pwrmax_rl_nsa_nray = _2d(s.pwrmax_rl_nsa_nray, nray, nsa)
        # legacy 1D-by-species
        pos_pwrmax_rs_nsa = [float(s.pos_pwrmax_rs_nsa[j]) for j in range(nsa)]
        pwrmax_rs_nsa = [float(s.pwrmax_rs_nsa[j]) for j in range(nsa)]
        pos_pwrmax_rl_nsa = [float(s.pos_pwrmax_rl_nsa[j]) for j in range(nsa)]
        pwrmax_rl_nsa = [float(s.pwrmax_rl_nsa[j]) for j in range(nsa)]
        return cls(
            nraymax=nray,
            nstpmax=int(s.nstpmax),
            nsamax=nsa,
            nsmax=int(s.nsmax),
            nrsmax=nrs,
            nrlmax=nrl,
            modelg=int(s.modelg),
            mdlwrq=int(s.mdlwrq),
            scalars=scalars,
            nstp_end=nstp_end,
            pwr_nray=pwr_nray,
            pwr_nsa=pwr_nsa,
            pos_nrs=pos_nrs,
            pos_nrl=pos_nrl,
            pwr_nsa_nray=pwr_nsa_nray,
            pwr_nrs_nsa=pwr_nrs_nsa,
            pwr_nrl_nsa=pwr_nrl_nsa,
            pos_pwrmax_rs_nsa_nray=pos_pwrmax_rs_nsa_nray,
            pos_pwrmax_rl_nsa_nray=pos_pwrmax_rl_nsa_nray,
            pwrmax_rs_nsa_nray=pwrmax_rs_nsa_nray,
            pwrmax_rl_nsa_nray=pwrmax_rl_nsa_nray,
            pos_pwrmax_rs_nsa=pos_pwrmax_rs_nsa,
            pwrmax_rs_nsa=pwrmax_rs_nsa,
            pos_pwrmax_rl_nsa=pos_pwrmax_rl_nsa,
            pwrmax_rl_nsa=pwrmax_rl_nsa,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable dict matching the Phase-0 baseline JSON shape.

        The baseline at ``test_run/baselines/wrx_*/metrics.json`` uses
        a flat ``{arrays, arrays2, scalars}`` grouping with an
        upper-case dimension header. We emit that shape so
        ``compare_metrics.py`` can diff Layer-1 output against the
        baseline at 1e-10 without further transformation.
        """
        return {
            "MDLWRQ": self.mdlwrq,
            "MODELG": self.modelg,
            "NRAYMAX": self.nraymax,
            "NRLMAX": self.nrlmax,
            "NRSMAX": self.nrsmax,
            "NSAMAX_WR": self.nsamax,
            "NSMAX": self.nsmax,
            "NSTPMAX": self.nstpmax,
            "arrays": {
                "NSTPMAX_NRAY": list(self.nstp_end),
                "pos_nrl": list(self.pos_nrl),
                "pos_nrs": list(self.pos_nrs),
                "pwr_nray": list(self.pwr_nray),
                "pwr_nsa": list(self.pwr_nsa),
            },
            "arrays2": {
                "pos_pwrmax_rl_nsa_nray": [list(r) for r in self.pos_pwrmax_rl_nsa_nray],
                "pos_pwrmax_rs_nsa_nray": [list(r) for r in self.pos_pwrmax_rs_nsa_nray],
                "pwr_nrl_nsa": [list(r) for r in self.pwr_nrl_nsa],
                "pwr_nrs_nsa": [list(r) for r in self.pwr_nrs_nsa],
                "pwr_nsa_nray": [list(r) for r in self.pwr_nsa_nray],
                "pwrmax_rl_nsa_nray": [list(r) for r in self.pwrmax_rl_nsa_nray],
                "pwrmax_rs_nsa_nray": [list(r) for r in self.pwrmax_rs_nsa_nray],
            },
            "scalars": dict(self.scalars),
        }


__all__ = ["WrxState", "SCALAR_FIELDS", "WRX_MAX_NSAMAX"]
