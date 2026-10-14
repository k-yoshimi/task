"""The seven global scalars of ``fp_get_state`` between a ``set_param`` and
the next run.

``fp_set_param`` clears the prepared flag without touching the arrays. In
that window ``fp_get_state`` still returns the profiles of the last run,
within the extents that are allocated (#245), while the global scalars
(``TOTAL_IP`` ... ``PLASMA_VOLUME``) are only filled from a prepared state
and read zero. The two rules meet here; these cases pin what the state
documentation says about them. One test per case, no ``subTest``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "fp" / "libfpapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from fplib import Fplib  # noqa: E402
from fplib.state import SCALAR_FIELDS  # noqa: E402

pytestmark = pytest.mark.skipif(
    not DEFAULT_SO.exists(),
    reason=f"libfpapi.so not built at {DEFAULT_SO}; run `make -C fp libfpapi.so`",
)

# Small momentum grid so one step is quick.
NPMAX = 10
NTHMAX = 10
DELT = 0.002

PROFILES = ("RNT", "RWT", "RTT", "RJT", "RPCT", "RPWT")


def _configure(fp: Fplib) -> None:
    fp.set_param("NPMAX", float(NPMAX))
    fp.set_param("NTHMAX", float(NTHMAX))
    fp.set_param("DELT", DELT)


def _all_zero(state) -> bool:
    return all(state.scalars[name] == 0.0 for name in SCALAR_FIELDS)


def test_the_state_has_the_seven_scalars():
    with Fplib() as fp:
        state = fp.get_state()
    assert len(SCALAR_FIELDS) == 7
    assert set(state.scalars) == set(SCALAR_FIELDS)


def test_before_the_first_run_the_scalars_are_zero():
    with Fplib() as fp:
        _configure(fp)
        state = fp.get_state()
    assert _all_zero(state)


def test_after_a_run_the_volume_is_there():
    with Fplib() as fp:
        _configure(fp)
        fp.run(1)
        state = fp.get_state()
    assert state.scalars["PLASMA_VOLUME"] > 0.0
    assert state.scalars["STORED_ENERGY"] > 0.0


def test_a_run_of_zero_steps_gives_the_volume_and_the_initial_sample():
    """``run(0)`` prepares only: the volume exists, and the species sums are
    those of the initial distribution."""
    with Fplib() as fp:
        _configure(fp)
        fp.run(0)
        state = fp.get_state()
    assert state.timefp == 0.0
    assert state.scalars["PLASMA_VOLUME"] > 0.0
    assert state.scalars["STORED_ENERGY"] > 0.0


# (parameter, change, the extents (nrmax, nsamax) reported afterwards): a raised
# count stays capped at what the run allocated, a lowered one applies at once.
@pytest.mark.parametrize(
    "name, change, extents",
    [("NSAMAX", +1, (3, 1)), ("NRMAX", +1, (3, 1)), ("NRMAX", -1, (2, 1))],
    ids=["NSAMAX+1", "NRMAX+1", "NRMAX-1"],
)
def test_after_a_set_param_the_scalars_are_zero_and_the_profiles_the_last_run_s(
        name, change, extents):
    with Fplib() as fp:
        _configure(fp)
        fp.set_param("NRMAX", 3.0)
        fp.run(1)
        before = fp.get_state()
        assert (before.nrmax, before.nsamax) == (3, 1)
        assert before.timefp > 0.0
        assert before.scalars["PLASMA_VOLUME"] > 0.0
        assert before.scalars["STORED_ENERGY"] > 0.0
        fp.set_param(name, float(getattr(before, name.lower()) + change))
        after = fp.get_state()
    assert _all_zero(after)
    # the profiles are still the last run's, within what is allocated (#245)
    assert (after.nrmax, after.nsamax) == extents
    assert after.timefp == before.timefp
    nr, nsa = extents
    for profile in PROFILES:
        rows_before, rows_after = getattr(before, profile), getattr(after, profile)
        assert rows_after == [row[:nr] for row in rows_before[:nsa]], profile


def test_the_next_run_fills_the_scalars_again():
    with Fplib() as fp:
        _configure(fp)
        fp.run(1)
        fp.set_param("DELT", DELT)
        assert _all_zero(fp.get_state())
        fp.run(1)
        state = fp.get_state()
    assert state.scalars["PLASMA_VOLUME"] > 0.0
    assert state.scalars["STORED_ENERGY"] > 0.0
