"""``MODELG=9`` (TR with the EQ q-solver): the initial state and its failures (#228).

With ``MODELG=9`` ``tr_set_metric`` builds the initial state by solving the
equilibrium and scaling q until the equilibrium current matches ``RIPS``;
during that, ``tr_bpsd_get`` adopts EQ's psi_p while the saved flag
``tr_eq_init`` is set, and the transport owns psi_p afterwards.

* The flag was cleared by the first run and never set again, so every later
  initial state in the same process (a second ``tr_init`` .. ``tr_finalize``
  lifecycle, or a second ``tr_prep`` after a parameter change) skipped the
  adoption: ``tr_run`` returned 0 with q = NaN in a new lifecycle, and with
  the previous run's psi_p inside one lifecycle.
* A failure inside the q-scaling (the equilibrium solve, a BPSD transfer, a
  scale factor that is zero or not finite, no agreement after 30 iterations)
  was at most printed; ``tr_run`` went on with what was left.

The good case is ``RIPS=RIPE=3`` (the ``tr_init`` default, set here by
name) on the other defaults: the q-scaling agrees there after three clean
equilibrium solves. ``RIPS=100`` asks for q(a) of about 0.15, and the first
equilibrium solve fails. No input that was tried reaches the other
branches of the q-scaling, and they have no test here. The failing runs
are ``run(0)``, which prepares and takes no step, so that an error of the
transport step cannot stand in for the preparation's; one case reads unit 6
of a child process to see that it is the equilibrium step that reported.
One test per case, no ``subTest``. Skipped when ``libtrapi.so`` has not
been built.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import Trlib, TrlibRunError  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"

pytestmark = pytest.mark.skipif(not DEFAULT_SO.exists(), reason="libtrapi.so not built")

RIPS_GOOD = 3.0
RIPS_NO_EQUILIBRIUM = 100.0


def _configure(tr: Trlib, rips: float) -> None:
    tr.set_param("MODELG", 9)
    tr.set_param("RIPS", rips)
    tr.set_param("RIPE", rips)


def _profiles(state) -> dict:
    """The radial profiles of a state: what ``tr_prep`` builds."""
    n = state.nrmax
    return {
        "QP": list(state.QP[:n]),
        "AJ": list(state.AJ[:n]),
        "RN": [list(row) for row in state.RN[:n]],
        "RT": [list(row) for row in state.RT[:n]],
    }


def _everything(state) -> dict:
    return {"nt": state.nt, "scalars": dict(state.scalars), **_profiles(state)}


def _one_step(rips: float = RIPS_GOOD) -> dict:
    """One lifecycle: configure, one transport step, the whole state."""
    with Trlib() as tr:
        _configure(tr, rips)
        tr.run(1)
        return _everything(tr.get_state())


def _assert_finite(state: dict) -> None:
    flat = list(state["scalars"].values()) + state["QP"] + state["AJ"]
    flat += [x for row in state["RN"] + state["RT"] for x in row]
    bad = [x for x in flat if not math.isfinite(x)]
    assert not bad, f"{len(bad)} of {len(flat)} values are not finite"


def test_first_lifecycle_is_finite_and_near_the_commanded_current():
    state = _one_step()
    _assert_finite(state)
    assert state["nt"] == 1
    assert state["scalars"]["AJT"] == pytest.approx(RIPS_GOOD, rel=0.05)
    assert all(q > 0.0 for q in state["QP"])


def test_second_lifecycle_equals_the_first():
    first = _one_step()
    second = _one_step()
    _assert_finite(second)
    assert second == first


def test_third_lifecycle_equals_the_first():
    first = _one_step()
    _one_step()
    assert _one_step() == first


def test_second_preparation_in_one_lifecycle_equals_the_first():
    """``run(0)`` prepares without a step; the profiles are what was prepared.

    The scalars are left out: no step evaluates them after ``run(0)``.
    """
    with Trlib() as tr:
        _configure(tr, RIPS_GOOD)
        tr.run(0)
        first = _profiles(tr.get_state())
        tr.run(1)                         # the transport now owns psi_p
        tr.set_param("RIPS", RIPS_GOOD)   # same value: asks for tr_prep again
        tr.run(0)
        second = _profiles(tr.get_state())
    assert all(math.isfinite(q) for q in second["QP"])
    assert second == first


def _assert_preparation_fails(tr: Trlib) -> None:
    """``run(0)`` is ``tr_prep`` alone, so the error is the preparation's."""
    _configure(tr, RIPS_NO_EQUILIBRIUM)
    with pytest.raises(TrlibRunError):
        tr.run(0)


def test_an_equilibrium_that_cannot_be_solved_fails_the_preparation():
    with Trlib() as tr:
        _assert_preparation_fails(tr)


# Unit 6 is buffered by the Fortran run-time and written out when the
# process ends, so the lines are read from a child process.
_CHILD = """
import sys
from trlib import Trlib, TrlibRunError
with Trlib() as tr:
    tr.set_param("MODELG", 9)
    tr.set_param("RIPS", {rips})
    tr.set_param("RIPE", {rips})
    try:
        tr.run(0)
    except TrlibRunError:
        print("CHILD: run(0) raised TrlibRunError")
    else:
        print("CHILD: run(0) returned")
"""


def test_the_failure_reported_is_the_equilibrium_step_of_the_q_scaling():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(PYTHON_ROOT)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
    )
    child = subprocess.run(
        [sys.executable, "-c", _CHILD.format(rips=RIPS_NO_EQUILIBRIUM)],
        capture_output=True, text=True, env=env, cwd=str(REPO), timeout=100,
    )
    assert child.returncode == 0, child.stdout[-2000:] + child.stderr[-2000:]
    assert "CHILD: run(0) raised TrlibRunError" in child.stdout
    assert re.search(
        r"XX tr_set_metric: eq_calc: iteration\s*\d+, ierr=\s*-?\d+", child.stdout
    ), child.stdout[-2000:]


def test_it_fails_the_preparation_in_a_later_lifecycle_too():
    _one_step()
    with Trlib() as tr:
        _assert_preparation_fails(tr)


def test_a_good_run_after_a_failed_preparation_on_the_same_handle_equals_a_first_run():
    reference = _one_step()
    with Trlib() as tr:
        _assert_preparation_fails(tr)
        _configure(tr, RIPS_GOOD)
        tr.run(1)
        recovered = _everything(tr.get_state())
    assert recovered == reference


def test_a_lifecycle_after_a_failed_preparation_equals_a_first_run():
    reference = _one_step()
    with Trlib() as tr:
        _assert_preparation_fails(tr)
    assert _one_step() == reference
