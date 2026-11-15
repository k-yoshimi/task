"""``MODELG=25``: an EQDSK file loaded and solved end to end (#228-2).

``plcheck`` accepts ``MODELG=25`` since #228-2, and ``EQ_READ``
(``eq/eqfile.f90``) reads it as it reads ``MODELG=5``: ``EQDSKR``, then
``EQCALQ``. In ``eq/eqcalq.f90``, ``EQSETP`` and ``DPPFUNC``/``DTTFUNC``
branch on ``MODELG`` 5 only, so with 25 the axis search starts at
``RAXIS=RR, ZAXIS=0``, and ``DPPFUNC``/``DTTFUNC`` differentiate the splines
of ``PPPS``/``TTPS`` instead of interpolating the derivatives read from the
file (``DPPPS``/``DTTPS``, whose splines are built for 5 only). Those two
functions feed only the averaged current densities ``AVEJTR``/``AVEJPR``
(``eqcalq.f90:418-422``), which the state does not carry, so 5 and 25 give
the same state here to 1e-9 relative.

These tests load one file with 5 and with 25 and check each against the
file: the run returns ``EQ_OK``; the axis is the file's (from ``RR``, 0.08 m
away, for 25; the file is up-down symmetric, so ``ZAXIS`` starts on it);
q on the axis and at the edge are the file's ``QPSI`` ends (computed by
``EQCALQ``, not read); and ``PSI0`` is the file's flux from the boundary to
the axis.

The fixture ``fixtures/iter_taskeq.geqdsk`` (25 KB) is TASK/EQ's own output:
the equilibrium of ``MODELG=2`` with ``RR=6.2``, ``RA=2.0``, ``RB=2.4``,
``RKAP=1.7``, ``RDLT=0.33``, ``BB=5.3``, ``RIP=15`` and the default
33 x 33 grid, written as GEQDSK (COCOS 1, flux per radian) by the
TASK web client's exporter. ``KNAMEQ`` holds 80 bytes, so each test copies
the file into its own directory and names it there.
"""
from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import pytest

import eqlib

_HERE = Path(__file__).resolve()
_DEFAULT_SO = _HERE.parents[3] / "eq" / "libeqapi.so"
FIXTURE = _HERE.parent / "fixtures" / "iter_taskeq.geqdsk"
NAME = "iter_taskeq.geqdsk"


def _resolved_so() -> Path:
    env = os.environ.get("EQLIB_PATH")
    if env:
        return Path(env)
    return _DEFAULT_SO


pytestmark = pytest.mark.skipif(
    not _resolved_so().exists(), reason="libeqapi.so not built"
)


@pytest.fixture(autouse=True)
def _in_tmp_dir(tmp_path, monkeypatch):
    """The file is loaded from the test's own directory (see the module text).

    A relative EQLIB_PATH is made absolute first, so that it names the same
    file after the chdir.
    """
    if os.environ.get("EQLIB_PATH"):
        monkeypatch.setenv("EQLIB_PATH", str(Path(os.environ["EQLIB_PATH"]).resolve()))
    shutil.copyfile(FIXTURE, tmp_path / NAME)
    monkeypatch.chdir(tmp_path)


def _read_geqdsk(path: Path) -> dict:
    """The header values and q(psi) of a GEQDSK file (5 numbers of 16 columns per line)."""
    lines = path.read_text().splitlines()
    nw, nh = (int(v) for v in lines[0].split()[-2:])
    need = 20 + 5 * nw + nw * nh       # header, FPOL, PRES, FFPRIM, PPRIME, PSIRZ, QPSI
    nums: list[float] = []
    for line in lines[1:]:
        nums += [float(line[k:k + 16]) for k in range(0, len(line), 16) if line[k:k + 16].strip()]
        if len(nums) >= need:
            break
    # Header: rdim zdim rcentr rleft zmid / rmaxis zmaxis simag sibry bcentr / ...
    return {
        "rmaxis": nums[5], "zmaxis": nums[6], "simag": nums[7], "sibry": nums[8],
        "qpsi": nums[need - nw:need],
    }


@pytest.mark.parametrize("modelg", [5, 25])
def test_the_file_is_loaded_and_solved(modelg):
    f = _read_geqdsk(FIXTURE)
    with eqlib.Eq() as e:
        e.set_param("MODELG", modelg)
        e.set_param_str("KNAMEQ", NAME)
        e.run(1)                        # EQ_OK, or an exception
        sc = e.get_state().scalars
    # NEWTN stops at |grad psi| <= 1e-4, about 1e-6 m here; for 25 the start is 0.08 m away.
    assert sc["raxis"] == pytest.approx(f["rmaxis"], abs=1e-5)
    assert abs(sc["zaxis"] - f["zmaxis"]) < 1e-6
    assert sc["qaxis"] == pytest.approx(f["qpsi"][0], rel=1e-3)
    assert sc["qsurf"] == pytest.approx(f["qpsi"][-1], rel=1e-3)
    # COCOS 1 gives the flux per radian; EQDSKR measures PSI0 from the boundary.
    assert sc["psi0"] == pytest.approx(2.0 * math.pi * (f["simag"] - f["sibry"]), rel=1e-6)
