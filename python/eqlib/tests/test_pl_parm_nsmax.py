"""``pl_parm`` keeps its PT/PU backups inside their bounds when a read changes NSMAX.

``pl_parm`` (``pl/plparm.f90``) zeroes ``PT`` and ``PU`` of the species
before the namelist read, so that a value given in the read can be told
from one that was not, and restores them when the read fails. The read can
change ``NSMAX``, also when it fails. The backups were sized with the
``NSMAX`` at entry and restored up to the ``NSMAX`` the read left:

- ``NSMAX=4`` and an unknown name, with the default ``NSMAX=2``: the read
  sets ``NSMAX=4``, fails, and the restore loop reads past the 2-element
  backups;
- in ``MODE=0`` a read that ``plcheck`` refuses goes back to label 1, which
  then writes 4 elements into the 2-element backups;
- entered with ``NSMAX=4``, a read that sets ``NSMAX=2`` and fails left PT
  and PU of species 3 and 4 at zero (no overrun, but nothing restored);
- a read that sets ``NSMAX`` outside 1 to ``NSM`` (100) runs the loops of
  ``pl_parm`` past the species arrays themselves.

CI builds ``pl`` with ``OFLAGS`` (``-g -O3 -m64 -std=legacy``), without
run-time checks: an overrun is not trapped there, and whether it ends the
driver depends on the platform. So the tests assert what ``pl_parm`` returned
and left (``IERR``, ``NSMAX``, ``PT``, ``PU``, the messages), and a driver that
ends abnormally fails its test too.

One overrun cannot be relied on to show in those values. When MODE=0 asks again
after ``plcheck`` refused a read that raised ``NSMAX`` and the next read
succeeds, the too-short backups are written and never read back: where that
was measured (macOS arm64) the code before the fix left the right values and
the driver then ended with SIGSEGV. What a write or a read past an array does
is not defined, so neither a value nor a crash is certain on another platform.
``test_mode_0_retry_keeps_its_backups_in_bounds`` therefore runs the two MODE=0
inputs with ``MODELG=26`` once more with ``pl/plparm.f90`` compiled by the test
itself with ``-fcheck=bounds`` and linked ahead of the library's copy: an index
past a backup then ends the driver with gfortran's run-time error on every
platform.

As in ``test_plcheck_modelg.py``, each test compiles a few lines of Fortran
against the PIC build of ``pl`` (that one test adds ``pl/plparm.f90`` itself)
and reads back what ``pl_parm`` returned and left. One test per case, no
``subTest``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eqlib.tests.test_plcheck_modelg import (
    LIB_PL,
    LIB_TASK,
    MAKE_HEADER,
    OBJ_MTX,
    REPO,
    _free_form_compiler,
)

# What a test needs to compile pl/plparm.f90 itself (its modules are pl's,
# lib's and mtxp's).
PLPARM = REPO / "pl" / "plparm.f90"
MOD_DIRS = (REPO / "pl" / "mod_pic", REPO / "lib" / "mod_pic", REPO / "mtxp" / "mod_pic")

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in (LIB_PL, LIB_TASK, OBJ_MTX, MAKE_HEADER)),
    reason="PIC build of pl (libpl_pic.a, libtask_pic.a, libmtxnompi_pic.o) not built",
)

# PT and PU of species 3 and 4 get marks before the call: pl_parm must not
# change them unless the read gives them. Argument 1 is MODE, argument 2
# the line for MODE=2; MODE=0 reads its namelists from standard input.
# Argument 3, if given, is NSMAX at entry (pl_init's is 2).
DRIVER = """\
PROGRAM pl_parm_nsmax_driver
  USE plinit, ONLY: pl_init
  USE plparm, ONLY: pl_parm
  USE plcomm, ONLY: nsmax, pt, pu
  IMPLICIT NONE
  INTEGER :: ierr, mode
  CHARACTER(LEN=80) :: arg, line
  OPEN(7, STATUS='SCRATCH', FORM='FORMATTED')
  CALL pl_init
  pt(3) = 3.25D0
  pt(4) = 4.25D0
  pu(3) = 30.D0
  pu(4) = 40.D0
  CALL GET_COMMAND_ARGUMENT(1, arg)
  READ(arg, *) mode
  CALL GET_COMMAND_ARGUMENT(2, line)
  CALL GET_COMMAND_ARGUMENT(3, arg)
  IF (LEN_TRIM(arg) > 0) READ(arg, *) nsmax
  WRITE(6, '(A,4ES24.16)') 'PL_PARM_PT0=', pt(1:4)
  WRITE(6, '(A,4ES24.16)') 'PL_PARM_PU0=', pu(1:4)
  CALL pl_parm(mode, TRIM(line), ierr)
  WRITE(6, '(A,I0)') 'PL_PARM_IERR=', ierr
  WRITE(6, '(A,I0)') 'PL_PARM_NSMAX=', nsmax
  WRITE(6, '(A,4ES24.16)') 'PL_PARM_PT=', pt(1:4)
  WRITE(6, '(A,4ES24.16)') 'PL_PARM_PU=', pu(1:4)
END PROGRAM pl_parm_nsmax_driver
"""


def _build(tmp_path: Path, bounds_checked: bool = False) -> Path:
    """Compile the driver in ``tmp_path`` and return the executable.

    With ``bounds_checked``, ``pl/plparm.f90`` is compiled here with
    ``-fcheck=bounds`` and linked ahead of the library, whose copy of the
    module is then not used: an index outside an array of ``pl_parm`` ends
    the driver with a run-time error instead of doing whatever the platform
    does with it.
    """
    source = tmp_path / "pl_parm_nsmax_driver.f90"
    source.write_text(DRIVER)
    exe = tmp_path / "pl_parm_nsmax_driver"
    if bounds_checked:
        flags = ["-std=legacy", "-fcheck=bounds", *(f"-I{d}" for d in MOD_DIRS)]
        sources = [str(PLPARM), str(source)]
    else:
        flags = [f"-I{REPO / 'pl' / 'mod_pic'}"]
        sources = [str(source)]
    build = subprocess.run(
        [*_free_form_compiler(), *flags, *sources,
         str(OBJ_MTX), str(LIB_PL), str(LIB_TASK), "-o", str(exe)],
        capture_output=True, text=True, cwd=tmp_path, timeout=60,
    )
    assert build.returncode == 0, f"driver did not build:\n{build.stdout}\n{build.stderr}"
    return exe


def _call(exe: Path, mode: int, line: str = "", stdin: str = "",
          entry_nsmax: int | None = None) -> dict:
    """Call ``pl_parm(mode, line)`` in the driver, return what it printed.

    A driver that ends abnormally (a signal, or a run-time check in a build
    that has them) fails the test here.
    """
    args = [str(exe), str(mode), line]
    if entry_nsmax is not None:
        args.append(str(entry_nsmax))
    run = subprocess.run(args, input=stdin,
                         capture_output=True, text=True, cwd=exe.parent, timeout=20)
    assert run.returncode == 0, f"driver ended with {run.returncode}:\n{run.stdout}\n{run.stderr}"
    out = {"output": run.stdout}
    for key in ("IERR", "NSMAX", "PT", "PU", "PT0", "PU0"):
        lines = [ln for ln in run.stdout.splitlines() if ln.startswith(f"PL_PARM_{key}=")]
        assert len(lines) == 1, run.stdout
        value = lines[0].split("=", 1)[1]
        out[key] = int(value) if key in ("IERR", "NSMAX") else [float(v) for v in value.split()]
    return out


def _run(tmp_path: Path, mode: int, line: str = "", stdin: str = "",
         entry_nsmax: int | None = None) -> dict:
    """Compile the driver against the library and call ``pl_parm(mode, line)``."""
    return _call(_build(tmp_path), mode, line, stdin, entry_nsmax)


def test_failed_read_that_raises_nsmax_restores_only_what_it_saved(tmp_path):
    """The read sets NSMAX=4 and then fails on the unknown name."""
    r = _run(tmp_path, 2, "NSMAX=4,UNKNOWN_PARAMETER=1")
    assert r["IERR"] == 6, r["output"]   # TASK_PARM: namelist line input error
    assert r["PT"] == r["PT0"], r["output"]
    assert r["PU"] == r["PU0"], r["output"]


def test_failed_read_restores_the_species_it_saved(tmp_path):
    """PT and PU of the species present at entry come back after a failed read."""
    r = _run(tmp_path, 2, "PT(1)=7.0,PU(2)=3.0,UNKNOWN_PARAMETER=1")
    assert r["IERR"] == 6, r["output"]
    assert r["PT"] == r["PT0"], r["output"]
    assert r["PU"] == r["PU0"], r["output"]


def test_failed_read_that_lowers_nsmax_restores_every_species_it_saved(tmp_path):
    """Entered with NSMAX=4, the read sets NSMAX=2 and then fails: PT and PU of
    species 3 and 4 come back too (the restore ran to the NSMAX the read left,
    and left them at zero)."""
    r = _run(tmp_path, 2, "NSMAX=2,UNKNOWN_PARAMETER=1", entry_nsmax=4)
    assert r["IERR"] == 6, r["output"]
    assert r["PT"] == r["PT0"], r["output"]
    assert r["PU"] == r["PU0"], r["output"]


MODE_0_RETRY = "&PL NSMAX=4, MODELG=26 /\n&PL MODELG=2 /\n"
MODE_0_INPUT_ENDS = "&PL NSMAX=4, MODELG=26 /\n"


def _after_a_good_read_of_nsmax_4(exe: Path) -> dict:
    """What ``&PL NSMAX=4 /`` alone leaves in MODE=0: no refusal, no retry.

    This, not the state at entry, is what PT and PU are compared with after a
    retry: ``pl_init`` does not set ``PT(2)`` (zero in the driver, static
    storage that nothing has written), and a read that succeeds without giving
    a ``PT`` turns a zero one into ``(PTPR+2*PTPP)/3``.
    """
    r = _call(exe, 0, stdin="&PL NSMAX=4 /\n")
    assert r["IERR"] == 0 and r["NSMAX"] == 4, r["output"]
    assert r["PT"][2:] == r["PT0"][2:], r["output"]   # the marks of species 3 and 4
    assert r["PU"] == r["PU0"], r["output"]
    return r


def test_mode_0_asks_again_after_plcheck_refuses_a_read_that_raised_nsmax(tmp_path):
    """MODELG=26 is refused by plcheck; MODE=0 goes back to label 1 with NSMAX=4.

    The second read gives no PT and no PU: they end as after a read of NSMAX=4
    that nothing refused.
    """
    exe = _build(tmp_path)
    r = _call(exe, 0, stdin=MODE_0_RETRY)
    assert r["IERR"] == 0, r["output"]
    assert r["NSMAX"] == 4, r["output"]
    assert "XX plcheck: INVALID MODELG" in r["output"]
    reference = _after_a_good_read_of_nsmax_4(exe)
    assert r["PT"] == reference["PT"], r["output"]
    assert r["PU"] == reference["PU"], r["output"]


def test_mode_0_restores_at_end_of_input_after_a_read_that_raised_nsmax(tmp_path):
    """As above, but the input ends where MODE=0 asks again: the read at label 1
    fails, and PT and PU of all four species come back from the backups taken
    there with NSMAX=4."""
    exe = _build(tmp_path)
    r = _call(exe, 0, stdin=MODE_0_INPUT_ENDS)
    assert r["IERR"] == 1, r["output"]   # TASK_PARM: end of the standard input
    assert r["NSMAX"] == 4, r["output"]
    assert "XX plcheck: INVALID MODELG" in r["output"]
    reference = _after_a_good_read_of_nsmax_4(exe)
    assert r["PT"] == reference["PT"], r["output"]
    assert r["PU"] == reference["PU"], r["output"]


@pytest.mark.parametrize(
    "stdin, ierr",
    [(MODE_0_RETRY, 0), (MODE_0_INPUT_ENDS, 1)],
    ids=["second_read_succeeds", "input_ends"],
)
def test_mode_0_retry_keeps_its_backups_in_bounds(tmp_path, stdin, ierr):
    """The two inputs above with ``pl/plparm.f90`` compiled here with the bounds
    check: at label 1 the backups hold the four species of the retry. Backups
    sized for the two species at entry end the driver at the first index past
    them, whatever the platform does with an overrun it does not check."""
    r = _call(_build(tmp_path, bounds_checked=True), 0, stdin=stdin)
    assert r["IERR"] == ierr, r["output"]
    assert r["NSMAX"] == 4, r["output"]
    assert "XX plcheck: INVALID MODELG" in r["output"]


def test_nsmax_above_nsm_is_refused(tmp_path):
    r = _run(tmp_path, 2, "NSMAX=101")
    assert r["IERR"] == 101, r["output"]
    assert "XX pl_parm: NSMAX out of range" in r["output"]
    assert r["NSMAX"] == 2, r["output"]   # the value at entry, not the refused one


def test_nsmax_below_1_is_refused(tmp_path):
    r = _run(tmp_path, 2, "NSMAX=0")
    assert r["IERR"] == 101, r["output"]
    assert "XX pl_parm: NSMAX out of range" in r["output"]
    assert r["NSMAX"] == 2, r["output"]


def test_refused_nsmax_restores_pt_and_pu(tmp_path):
    r = _run(tmp_path, 2, "NSMAX=101")
    assert r["PT"] == r["PT0"], r["output"]
    assert r["PU"] == r["PU0"], r["output"]


def test_mode_0_asks_again_after_nsmax_out_of_range(tmp_path):
    r = _run(tmp_path, 0, stdin="&PL NSMAX=101 /\n&PL NSMAX=3 /\n")
    assert r["IERR"] == 0, r["output"]
    assert r["NSMAX"] == 3, r["output"]
    assert "XX pl_parm: NSMAX out of range" in r["output"]


def test_nsmax_at_nsm_is_accepted(tmp_path):
    """The upper end of the range: no overrun with NSMAX = NSM."""
    r = _run(tmp_path, 2, "NSMAX=100")
    assert r["IERR"] == 0, r["output"]
    assert "XX pl_parm: NSMAX out of range" not in r["output"]
    assert r["NSMAX"] == 100, r["output"]


def test_nsmax_in_range_is_accepted(tmp_path):
    r = _run(tmp_path, 2, "NSMAX=4")
    assert r["IERR"] == 0, r["output"]
    assert r["NSMAX"] == 4, r["output"]
