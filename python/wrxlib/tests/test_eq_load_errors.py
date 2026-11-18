"""``wrx_run`` fails when the equilibrium file does not load.

``wr_prep`` (``wrx/wrprep.f90``) loads ``KNAMEQ`` for MODELG 3 and 5
(``eq_load``) and MODELG 8 (``eq_read``). On a failed load it used to print
the IERR and go on: the plasma bounds came from an earlier run or were zero,
the IERR was lost in ``pl_load`` and ``dp_prep_ns`` (which sets it to 0),
and ``wrx_run`` returned ``WRX_OK`` with NaN powers, or ended the process in
the ``STOP`` of ``BESSJN`` (the ITER01 case below, MODELG 3 and no
``eqdata``). ``wr_prep`` now returns the load's IERR and ``wrx_run`` returns
``WRX_ERR_CALC_FAILED``.

wrxlib has no string parameters, so ``KNAMEQ`` keeps its default
``'eqdata'``, which the Fortran opens relative to the working directory: each
case runs in a directory of its own, and in a process of its own: what the
Fortran wrote (unit 6 is buffered) is all there when the process ends, a
``STOP`` (the code before this fix) fails that case only, and ``wr_prep``'s
memory of a successful load (``INITEQ``, a SAVEd local that only a run with
a MODELG other than 3, 5 and 8 clears, not ``wrx_finalize``) ends with it.
"""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from wrxlib import _ffi  # noqa: E402

EQDATA_ITER01 = REPO / "python" / "eqlib" / "tests" / "fixtures" / "eqdata.ITER01"

# WRX_RUN_OK=0 opts out of the wrx_run tests, as in test_wrxlib.py.
RUN_OK = os.environ.get("WRX_RUN_OK", "1") != "0"

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("WRXLIB_PATH")
        and not any(p.exists() for p in _ffi._candidate_paths()),
        reason="libwrxapi.so not built; run `make -C wrx libwrxapi.so`",
    ),
    pytest.mark.skipif(not RUN_OK, reason="WRX_RUN_OK=0: wrx_run tests opted out"),
]

# The ITER01 ECCD case with its geometry read from KNAMEQ (MODELG = argv[2]),
# in the working directory the parent gives it. A VERDICT line says how
# wrx_run ended and whether wrx_get_state then had a state to return. With
# argv[3], the file argv[3] is then copied to 'eqdata' and the same instance
# runs again: a second VERDICT line.
_CHILD = """
import shutil
import sys
sys.path.insert(0, sys.argv[1])
from wrxlib import Wrxlib, WrxlibRunError, WrxlibStateError
from wrxlib.tests.fixtures import wrx_iter01_params as iter01

def run(wrx):
    try:
        wrx.run(iter01.NRAY_REQUEST)
    except WrxlibRunError:
        try:
            wrx.get_state()
        except WrxlibStateError:
            print("VERDICT FAILED, NO STATE", flush=True)
        else:
            print("VERDICT FAILED, A STATE", flush=True)
    else:
        state = wrx.get_state()
        print("VERDICT RAN", state.modelg, repr(state.scalars["pwr_tot"]), flush=True)

with Wrxlib() as wrx:
    iter01.apply(wrx)
    wrx.set_param("MODELG", float(sys.argv[2]))
    run(wrx)
    if len(sys.argv) > 3:
        shutil.copyfile(sys.argv[3], "eqdata")
        run(wrx)
"""


def _in_a_process_of_its_own(cwd, modelg, *then):
    """(VERDICT lines, the child's output, its tail for a message) of the
    case in directory CWD."""
    # The library the parent would load, also when its path is relative to
    # the parent's working directory and not to CWD.
    # Each read as its loader reads it: _ffi takes WRXLIB_PATH as it is,
    # _runtime_mode.mono_lib_path strips MONO_LIB_PATH (blank = unset).
    env = dict(os.environ)
    wrxlib_path = env.get("WRXLIB_PATH")
    if wrxlib_path:
        env["WRXLIB_PATH"] = str(Path(wrxlib_path).resolve())
    mono_path = env.get("MONO_LIB_PATH", "").strip()
    if mono_path:
        env["MONO_LIB_PATH"] = str(Path(mono_path).resolve())
    done = subprocess.run(
        [sys.executable, "-c", _CHILD, str(PYTHON_ROOT), str(modelg), *map(str, then)],
        cwd=cwd, env=env, capture_output=True, text=True, errors="replace", timeout=60,
    )
    out = done.stdout
    tail = out[-2000:] + done.stderr[-1000:]
    assert done.returncode == 0, tail
    return [line for line in out.splitlines() if line.startswith("VERDICT ")], out, tail


@pytest.mark.parametrize("modelg", [3, 5, 8])
def test_run_fails_when_knameq_is_missing(tmp_path, modelg):
    assert not (tmp_path / "eqdata").exists()
    verdicts, out, tail = _in_a_process_of_its_own(tmp_path, modelg)
    assert verdicts == ["VERDICT FAILED, NO STATE"], tail
    # The failure is the load's: FROPEN's message, then wr_prep's.
    assert "FILE NOT FOUND: eqdata" in out, tail
    assert ("XX EQREAD: IERR=" if modelg == 8 else "XX EQLOAD: IERR=") in out, tail
    # wr_prep returned there: it no longer goes on to print the bounds.
    assert "_eq:" not in out, tail


def test_run_after_a_failed_load_loads_the_file(tmp_path):
    """The failed load is not remembered: the next run reads the file.

    Also the control for the test above: with the file in place the same
    MODELG 3 case runs and deposits power.
    """
    verdicts, out, tail = _in_a_process_of_its_own(tmp_path, 3, EQDATA_ITER01)
    assert len(verdicts) == 2 and verdicts[0] == "VERDICT FAILED, NO STATE", tail
    ran, modelg, pwr_tot = verdicts[1].split(" ", 1)[1].split()
    assert (ran, modelg) == ("RAN", "3"), tail
    assert math.isfinite(float(pwr_tot)) and float(pwr_tot) > 0.0, tail
