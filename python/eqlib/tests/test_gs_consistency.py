"""The T(psi) that EQ exports belongs to the psi it solved.

EQ's psi is the total poloidal flux and T = 2*pi*R*B_phi, so its
Grad-Shafranov equation reads R div(grad psi / R**2) = 2*pi*mu0*j_zeta with

    j_zeta = -2*pi*R*dp/dpsi - T*dT/dpsi / (2*pi*mu0*R).

The test solves an equilibrium (``run(0)``), writes it with ``save`` and
reads back psi(R,Z), p(psi), T(psi) and the solver's own current HJTRZ.
The current that the exported profiles give, integrated over the plasma,
must be the current the solver used. With the factor 4*pi**2 missing from
the pressure term of T**2 (MDLEQF=0 before this test was added) the ratio
was 1.28 at beta_t 1.5 % and grew with beta_p.

Pure Python (no numpy): the file is read with ``struct``, the profile
derivatives are central differences on a fine psi grid (NPSMAX=201).
The tests work in a temporary directory with relative file names, since
KNAMEQ holds 80 characters.
"""
from __future__ import annotations

import math
import os
import struct
from pathlib import Path

import pytest

import eqlib

_HERE = Path(__file__).resolve()
_DEFAULT_SO = _HERE.parents[3] / "eq" / "libeqapi.so"


def _resolved_so() -> Path:
    env = os.environ.get("EQLIB_PATH")
    if env:
        return Path(env)
    return _DEFAULT_SO


pytestmark = pytest.mark.skipif(
    not _resolved_so().exists(), reason="libeqapi.so not built"
)

MU0 = 4.0e-7 * math.pi
AMP = 1.67262192369e-27   # proton mass, bpsd_constants.f90 (EQ's rotation uses it)
AEE = 1.602176634e-19

# ITER-like analytic equilibrium (MODELG=2, fixed boundary).
_ITER = {"MODELG": 2, "RR": 6.2, "RA": 2.0, "RB": 2.4, "RKAP": 1.7,
         "RDLT": 0.33, "BB": 5.3, "RIP": 15.0, "NPSMAX": 201}


@pytest.fixture(autouse=True)
def _in_tmp_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _records(path: str) -> list:
    """Fortran unformatted sequential records (4-byte markers)."""
    data = Path(path).read_bytes()
    out, pos = [], 0
    while pos < len(data):
        (n,) = struct.unpack_from("<i", data, pos)
        out.append(data[pos + 4:pos + 4 + n])
        (n2,) = struct.unpack_from("<i", data, pos + 4 + n)
        assert n2 == n, "record markers do not match"
        pos += 8 + n
    return out


def _f8(b: bytes) -> list:
    return list(struct.unpack("<%dd" % (len(b) // 8), b))


def _i4(b: bytes) -> list:
    return list(struct.unpack("<%di" % (len(b) // 4), b))


def _read_save(path: str) -> dict:
    """The fields of EQSAVE (eq/eqfile.f90) that this test needs."""
    r = _records(path)
    rr, bb, rip = _f8(r[0])
    nrg, nzg = _i4(r[1])
    psirz = _f8(r[4])            # PSIRZ(NRG,NZG), NRG fastest
    hjtrz = _f8(r[-1])           # HJTRZ, same order
    raxis, _zaxis, _psita, _psipa, psi0 = _f8(r[15])
    return {"RR": rr, "BB": bb, "RIP": rip, "NRG": nrg, "NZG": nzg,
            "RG": _f8(r[2]), "ZG": _f8(r[3]), "PSIRZ": psirz,
            "PSIPS": _f8(r[6]), "PPPS": _f8(r[7]), "TTPS": _f8(r[8]),
            "TEPS": _f8(r[9]), "OMPS": _f8(r[10]),
            "RAXIS": raxis, "PSI0": psi0, "HJTRZ": hjtrz,
            "PSIPNV": _f8(r[16]), "TTV": _f8(r[20])}


def _derivative(y: list, h: float) -> list:
    """Second-order finite differences on a uniform grid."""
    n = len(y)
    d = [0.0] * n
    for i in range(1, n - 1):
        d[i] = (y[i + 1] - y[i - 1]) / (2 * h)
    d[0] = (-3 * y[0] + 4 * y[1] - y[2]) / (2 * h)
    d[-1] = (3 * y[-1] - 4 * y[-2] + y[-3]) / (2 * h)
    return d


def _interp(x: float, h: float, y: list) -> float:
    """Linear interpolation of y on the uniform grid 0, h, 2h, ..."""
    i = min(max(int(x / h), 0), len(y) - 2)
    t = x / h - i
    return (1 - t) * y[i] + t * y[i + 1]


def _solve_and_read(params: dict) -> dict:
    with eqlib.Eq() as e:
        e.set_params(params)
        e.run(0)
        e.save("eq.sav")
    return _read_save("eq.sav")


def _current_ratio(s: dict) -> float:
    """(current the exported p and T give) / (current the solver used)."""
    psips = s["PSIPS"]
    psipa = psips[-1]
    h = 1.0 / (len(psips) - 1)               # PSIPS is uniform from 0 to PSIPA
    assert abs(psips[1] - psipa * h) < 1e-9 * psipa
    dp = _derivative(s["PPPS"], h)
    p = s["PPPS"]
    dt2 = _derivative([0.5 * t * t for t in s["TTPS"]], h)
    # rotation: p(psi,R) = P(psi) exp(R**2 U(psi)), U = AMP omega**2 / (2 T)
    u = [AMP * om * om / (2.0 * te * 1.0e3 * AEE) if te > 0 else 0.0
         for om, te in zip(s["OMPS"], s["TEPS"])]
    du = _derivative(u, h)
    rg, zg = s["RG"], s["ZG"]
    da = (rg[1] - rg[0]) * (zg[1] - zg[0])
    nrg = s["NRG"]
    i_solver = i_profiles = 0.0
    for k, psi in enumerate(s["PSIRZ"]):
        if psi >= 0.0:                       # outside the plasma (psi = 0 on its boundary)
            continue
        r = rg[k % nrg]
        x = min(max(1.0 - psi / s["PSI0"], 0.0), 1.0)
        pv, uv = _interp(x, h, p), _interp(x, h, u)
        dpdpsi = ((_interp(x, h, dp) + pv * r * r * _interp(x, h, du))
                  * math.exp(r * r * uv) / psipa)
        tdt = _interp(x, h, dt2) / psipa
        i_profiles += (-2 * math.pi * r * dpdpsi - tdt / (2 * math.pi * MU0 * r)) * da
        i_solver += s["HJTRZ"][k] * da
    return i_profiles / i_solver


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"PP0": 0.6}, id="mdleqf0-beta1.5pct"),
        pytest.param({"PP0": 0.15, "RIP": 5.0}, id="mdleqf0-betap0.8"),
        pytest.param({"PP0": 0.3, "PV0": 5.0e5, "PT0": 10.0}, id="mdleqf0-rotation"),
        pytest.param({"PP0": 0.3, "MDLEQF": 1}, id="mdleqf1-control"),
    ],
)
def test_exported_t_gives_the_solved_current(extra):
    s = _solve_and_read(dict(_ITER, **extra))
    ratio = _current_ratio(s)
    assert abs(ratio - 1.0) < 2e-3, ratio
    # EQRHSV's TTV (the T that EQCALV's flux averages use in the loop) and
    # EQCALP's TTPS are the same function of the normalised flux.
    h = 1.0 / (len(s["TTPS"]) - 1)
    worst = max(abs(_interp(x, h, s["TTPS"]) - t) / t
                for x, t in zip(s["PSIPNV"], s["TTV"]))
    assert worst < 1e-4, worst
