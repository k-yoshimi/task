"""eqlib.Eq.get_psi_rz(): the PSI(R,Z) field of the equilibrium, and an error
when there is none (#227 item 6).

``eq_get_psi_rz`` refuses in the cases in which ``eq_save`` does: no
successful ``eq_run`` since ``eq_init``, a later run that failed, a
``set_param`` since. It used to be the gfortran-mangled
``eq_common_get_psi_rz_``, which returned zeros or a stale field then.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import eqlib
from eqlib._ffi import EQ_ERR_INVALID, EQ_ERR_NOT_INIT

np = pytest.importorskip("numpy")

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


@pytest.fixture(autouse=True)
def _in_tmp_dir(tmp_path, monkeypatch):
    """A run may leave files of its own (EQ_REGRESS_DUMP); keep them out of the tree.

    A relative EQLIB_PATH is made absolute first, so that it names the same
    file after the chdir.
    """
    if os.environ.get("EQLIB_PATH"):
        monkeypatch.setenv("EQLIB_PATH", str(Path(os.environ["EQLIB_PATH"]).resolve()))
    monkeypatch.chdir(tmp_path)


def test_get_psi_rz_default_shape():
    with eqlib.Eq() as e:
        e.run(0)
        psi = e.get_psi_rz()
    assert psi.ndim == 2
    assert psi.shape == (33, 33)  # default NRGMAX=NZGMAX=33
    assert psi.dtype == np.float64
    assert np.isfinite(psi).all()
    assert np.any(psi != 0.0)


def test_the_field_is_indexed_r_then_z():
    """The default equilibrium is up-down symmetric and not symmetric in R:
    the second index is Z. Its minimum is the flux on the axis, PSI0."""
    with eqlib.Eq() as e:
        e.run(0)
        psi = e.get_psi_rz()
        psi0 = e.get_state().scalars["psi0"]
    assert np.max(np.abs(psi - psi[:, ::-1])) < 1e-10 * np.max(np.abs(psi))
    assert np.max(np.abs(psi - psi[::-1, :])) > 1e-2 * np.max(np.abs(psi))
    assert psi.min() == pytest.approx(psi0, rel=1e-3)


def test_the_shape_follows_the_grid_counts():
    """NRGMAX=65 with NZGMAX=33: a grid that is not square is where a mixed-up
    layout would show, so the field is checked for its symmetry here too."""
    with eqlib.Eq() as e:
        e.set_param("NRGMAX", 65)
        e.run(0)
        psi = e.get_psi_rz()
    assert psi.shape == (65, 33)
    assert np.max(np.abs(psi - psi[:, ::-1])) < 1e-10 * np.max(np.abs(psi))
    assert np.max(np.abs(psi - psi[::-1, :])) > 1e-2 * np.max(np.abs(psi))


def test_before_any_run_is_refused():
    with eqlib.Eq() as e:
        with pytest.raises(eqlib.EqlibInvalidParamError, match="call run first"):
            e.get_psi_rz()


def test_after_a_run_that_failed_is_refused():
    with eqlib.Eq() as e:
        e.set_param("MODELG", 3)
        e.run(0)
        e.set_param_str("KNAMEQ", "no_such_file")
        with pytest.raises(eqlib.EqlibCalculationFailedError):
            e.run(1)
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.get_psi_rz()
        e.run(0)                        # and a good run gives the field again
        assert e.get_psi_rz().shape == (33, 33)


def test_after_a_parameter_change_waits_for_the_next_run():
    with eqlib.Eq() as e:
        e.run(0)
        e.set_param("PP0", 2.0)
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.get_psi_rz()
        e.run(0)
        assert e.get_psi_rz().shape == (33, 33)


def test_a_string_set_leaves_the_field_readable():
    """The registry does not count the string parameters (as for eq_save)."""
    with eqlib.Eq() as e:
        e.run(0)
        e.set_param_str("KNAMEQ", "eq.bin")
        assert e.get_psi_rz().shape == (33, 33)


def test_the_c_entry_refuses_counts_other_than_the_grids():
    """nr and nz must be NRGMAX and NZGMAX; nothing is written otherwise."""
    with eqlib.Eq() as e:
        e.run(0)
        lib = e._lib
        buf = np.full((33, 34), 7.0)
        ptr = buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        assert lib.eq_get_psi_rz(34, 33, ptr) == EQ_ERR_INVALID
        assert lib.eq_get_psi_rz(33, 34, ptr) == EQ_ERR_INVALID
        assert (buf == 7.0).all()
        assert lib.eq_get_psi_rz(33, 33, None) == EQ_ERR_INVALID


def test_the_c_entry_before_init_is_not_init():
    """After finalize the library is not initialised: EQ_ERR_NOT_INIT."""
    e = eqlib.Eq()
    lib = e._lib
    e.close()
    buf = np.zeros((33, 33))
    rc = lib.eq_get_psi_rz(33, 33, buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
    assert rc == EQ_ERR_NOT_INIT
