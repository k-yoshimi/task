"""eqlib.Eq.get_psi_rz() returns a 2-D numpy array shaped (NRG, NZG)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import eqlib

np = pytest.importorskip("numpy")

_HERE = Path(__file__).resolve()
_DEFAULT_SO = _HERE.parents[3] / "eq" / "libeqapi.so"


def _resolved_so() -> Path:
    env = os.environ.get("EQLIB_PATH")
    if env:
        return Path(env)
    return _DEFAULT_SO


@pytest.mark.skipif(not _resolved_so().exists(), reason="libeqapi.so not built")
def test_get_psi_rz_default_shape():
    with eqlib.Eq() as e:
        psi = e.get_psi_rz()
    assert psi.ndim == 2
    assert psi.shape == (33, 33)  # default NRGMAX=NZGMAX=33
    assert psi.dtype == np.float64
