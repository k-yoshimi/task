"""``plcheck`` accepts ``MODELG=25``, the EQDSK geometry ``EQ_READ`` loads (#228).

``pl/plinit.f90`` documents ``MODELG=25`` and ``EQ_READ`` in ``eq/eqfile.f90``
loads it, but ``plcheck`` in ``pl/plparm.f90`` refused every value above 11:
a ``plparm`` namelist carrying it printed ``XX plcheck: INVALID MODELG`` and
``pl_parm`` returned 101, and the PL menu asked again.

No C entry point reaches ``pl_parm`` (the main programs and the PL menu call
it), so each test compiles a few lines of Fortran against the PIC build of
``pl`` that the shared libraries are linked from, with the compiler named in
``make.header``, and reads back the ``ierr`` of ``pl_parm`` (0 accepted, 101
refused by ``plcheck``). One test per value, no ``subTest``.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
LIB_PL = REPO / "pl" / "libpl_pic.a"
LIB_TASK = REPO / "lib" / "libtask_pic.a"
OBJ_MTX = REPO / "mtxp" / "libmtxnompi_pic.o"
MAKE_HEADER = REPO / "make.header"

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in (LIB_PL, LIB_TASK, OBJ_MTX, MAKE_HEADER)),
    reason="PIC build of pl (libpl_pic.a, libtask_pic.a, libmtxnompi_pic.o) not built",
)

# Unit 7 is the scratch unit TASK_PARM parses a line through (lib/libkio.f90);
# the main programs open it the same way.
DRIVER = """\
PROGRAM plcheck_driver
  USE plinit, ONLY: pl_init
  USE plparm, ONLY: pl_parm
  IMPLICIT NONE
  INTEGER :: ierr
  CHARACTER(LEN=80) :: line
  OPEN(7, STATUS='SCRATCH', FORM='FORMATTED')
  CALL pl_init
  CALL GET_COMMAND_ARGUMENT(1, line)
  CALL pl_parm(2, TRIM(line), ierr)
  WRITE(6, '(A,I0)') 'PL_PARM_IERR=', ierr
END PROGRAM plcheck_driver
"""


def _free_form_compiler() -> list[str]:
    """The free-form compiler command of this build (``FCFREE`` in make.header).

    As in make, the last ``=`` or ``:=`` assignment wins, ``?=`` counts only
    while nothing is assigned yet and ``+=`` appends; a trailing comment is
    dropped. A value that refers to another make variable is not expanded
    here and fails the test with that message.
    """
    command = None
    for raw in MAKE_HEADER.read_text().splitlines():
        name, sep, value = raw.partition("=")
        name = name.strip()
        if not sep or name.rstrip(":?+").strip() != "FCFREE":
            continue
        words = shlex.split(value.split("#", 1)[0])
        if name.endswith("+"):
            command = (command or []) + words
        elif not (name.endswith("?") and command is not None):
            command = words
    assert command, f"no FCFREE line in {MAKE_HEADER}"
    assert not any("$" in word for word in command), (
        f"FCFREE in {MAKE_HEADER} refers to a make variable: {command}"
    )
    return command


def _pl_parm_ierr(tmp_path: Path, line: str) -> tuple[int, str]:
    """Compile the driver, give ``line`` to ``pl_parm(2, ...)``, return (ierr, output)."""
    source = tmp_path / "plcheck_driver.f90"
    source.write_text(DRIVER)
    exe = tmp_path / "plcheck_driver"
    build = subprocess.run(
        [*_free_form_compiler(), f"-I{REPO / 'pl' / 'mod_pic'}",
         str(source), str(OBJ_MTX), str(LIB_PL), str(LIB_TASK), "-o", str(exe)],
        capture_output=True, text=True, cwd=tmp_path, timeout=100,
    )
    assert build.returncode == 0, f"driver did not build:\n{build.stdout}\n{build.stderr}"
    run = subprocess.run([str(exe), line], capture_output=True, text=True,
                         cwd=tmp_path, timeout=20)
    assert run.returncode == 0, f"driver ended with {run.returncode}:\n{run.stdout}\n{run.stderr}"
    results = [ln for ln in run.stdout.splitlines() if ln.startswith("PL_PARM_IERR=")]
    assert len(results) == 1, run.stdout
    return int(results[0].split("=", 1)[1]), run.stdout


def test_modelg_25_is_accepted(tmp_path):
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=25")
    assert ierr == 0, output
    assert "INVALID MODELG" not in output


def test_modelg_5_is_accepted(tmp_path):
    """The other EQDSK geometry, inside the range that was always accepted."""
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=5")
    assert ierr == 0, output


def test_modelg_above_25_is_refused(tmp_path):
    """The allowance is for 25, not a widened range."""
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=26")
    assert ierr == 101, output
    assert "XX plcheck: INVALID MODELG" in output


def test_modelg_between_the_range_and_25_is_refused(tmp_path):
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=24")
    assert ierr == 101, output


def test_negative_modelg_is_refused(tmp_path):
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=-1")
    assert ierr == 101, output


def test_modelg_25_keeps_the_other_checks(tmp_path):
    """With MODELG=25 the checks of the non-TASK/EQ branch still run."""
    ierr, output = _pl_parm_ierr(tmp_path, "MODELG=25,MODELQ=7")
    assert ierr == 101, output
    assert "INVALID MODELQ" in output
    assert "INVALID MODELG" not in output
