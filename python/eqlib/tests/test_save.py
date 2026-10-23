"""Eq.save(): the equilibrium file is written and loads back, and a save
whose file was not opened or came out short is an error (#227 item 3).

The tests work in a temporary directory with relative file names: KNAMEQ
holds 80 characters, and a temporary directory's own path can be longer.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
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


@pytest.fixture(autouse=True)
def _in_tmp_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _solved():
    """An Eq with the analytic equilibrium of the defaults computed."""
    e = eqlib.Eq()
    e.run(0)
    return e


def _files():
    """The working directory's entries. Compared before and after a refused
    save: a run may leave files of its own there (EQ_REGRESS_DUMP)."""
    return sorted(os.listdir("."))


def test_save_writes_a_file_that_loads_back():
    """The file of ``save`` is what ``MODELG=3`` + ``KNAMEQ`` reads."""
    with _solved() as e:
        saved = e.get_state()
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0

    with eqlib.Eq() as e:
        e.set_param("MODELG", 3)
        e.set_param_str("KNAMEQ", "eq.bin")
        e.run(1)                        # eq_load of the TASK/EQ file
        loaded = e.get_state()

    # Records of the file, read back as they were written.
    assert (loaded.nrgmax, loaded.nzgmax, loaded.npsmax) == (
        saved.nrgmax, saved.nzgmax, saved.npsmax)
    assert loaded.rg == saved.rg and loaded.zg == saved.zg
    assert loaded.psips == saved.psips and loaded.ppps == saved.ppps
    # Recomputed from the loaded fields after the load (EQCALQ).
    for name in ("raxis", "zaxis", "psi0", "psipa", "psita"):
        assert loaded.scalars[name] == pytest.approx(saved.scalars[name], rel=1e-9), name


def test_save_accepts_a_pathlib_path():
    with _solved() as e:
        e.save(Path("eq.bin"))
    assert os.path.getsize("eq.bin") > 0


def test_save_before_any_run_is_refused():
    """There is no equilibrium to write, and the file EQSAVE would produce
    ends the process that loads it."""
    with eqlib.Eq() as e:
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("eq.bin")
    assert not os.path.exists("eq.bin")


def test_save_after_a_run_that_failed_is_refused():
    """A run that fails leaves the fields part-way: they are no longer the
    equilibrium of the run before it. (MODELG is set before the good run and
    only a file name after it, so that nothing but the failed run stands
    between that run and the save.)"""
    with eqlib.Eq() as e:
        e.set_param("MODELG", 3)
        e.run(0)
        e.set_param_str("KNAMEQ", "no_such_file")
        with pytest.raises(eqlib.EqlibCalculationFailedError):
            e.run(1)
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("eq.bin")
        assert not os.path.exists("eq.bin")
        e.run(0)                        # and a good run makes it savable again
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0


def test_a_failed_eqdsk_load_does_not_make_old_fields_savable():
    """The load of a missing EQDSK file used to return success (EQ_READ kept
    EQCALQ's code, not EQDSKR's), over the fields of the earlier run and
    with whatever parameters had been set since."""
    with _solved() as e:
        e.set_param("PP0", 123.0)
        e.set_param("MODELG", 5)
        e.set_param_str("KNAMEQ", "no_such_file")
        with pytest.raises(eqlib.EqlibCalculationFailedError):
            e.run(1)
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("eq.bin")
    assert not os.path.exists("eq.bin")


def test_save_after_a_parameter_change_waits_for_the_next_run():
    """EQSAVE writes the parameters and counts as they stand, over fields
    that were computed for the old ones: a grid count raised after the run
    gave a file that stopped the process loading it."""
    with _solved() as e:
        e.set_param("NRGMAX", 65)
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("eq.bin")
        assert not os.path.exists("eq.bin")
        e.run(0)                        # the equilibrium of the new count
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0


def test_save_is_still_allowed_after_the_file_modes_are_set():
    """MODEFR and MODEFW say how a file is opened, not what the equilibrium
    is."""
    with _solved() as e:
        e.set_param("MODEFR", 0)
        e.set_param("MODEFW", 0)
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0


def test_a_refused_set_leaves_the_save_allowed():
    """A set the registry refuses changes nothing, so the equilibrium of the
    last run is still the one of the present parameters."""
    with _solved() as e:
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.set_param("NO_SUCH_PARAMETER", 1.0)
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0


def test_a_string_set_leaves_the_save_allowed():
    """The string parameters are file names, which the solve does not read
    (the registry does not count them; KNAMEQ, which save sets itself, is
    one of them)."""
    with _solved() as e:
        e.set_param_str("KNAMEQ2", "other.bin")
        e.save("eq.bin")
    assert os.path.getsize("eq.bin") > 0


def test_save_raises_when_directory_missing():
    """FWOPEN cannot create the file: the save is an error, not EQ_OK."""
    with _solved() as e:
        with pytest.raises(eqlib.EqlibCalculationFailedError):
            e.save("no_such_dir/eq.bin")
    assert not os.path.exists("no_such_dir")


def test_save_wants_a_path():
    with _solved() as e:
        with pytest.raises(TypeError):
            e.save(None)


def test_save_rejects_blank_path():
    """A blank KNAMEQ can never produce a file."""
    with _solved() as e:
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("")
        assert _files() == before


def test_save_takes_80_bytes_and_refuses_81():
    """KNAMEQ is CHARACTER(LEN=80): a longer path is refused, not cut."""
    with _solved() as e:
        e.save("x" * 80)
        assert os.path.getsize("x" * 80) > 0
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("y" * 81)
        assert _files() == before


def test_save_refuses_a_path_that_ends_in_a_blank():
    """Fortran drops a trailing blank: ``"result "`` would be written as
    ``"result"``, over whatever is there."""
    Path("result").write_bytes(b"something else")
    with _solved() as e:
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("result ")
        assert _files() == before
    assert Path("result").read_bytes() == b"something else"


def test_save_raises_when_reopen_refused_and_an_earlier_file_exists():
    """A repeat save must not pass for a success because of the first file.

    After one successful save, a save that fails leaves the earlier file in
    place, and "a non-empty file exists afterwards" holds. MODEFW=3 makes
    FWOPEN refuse an existing file; EQSAVE_IERR reports that through its
    argument.
    """
    with _solved() as e:
        e.save("eq.bin")
        first = Path("eq.bin").read_bytes()
        assert first

        e.set_param("MODEFW", 3)
        with pytest.raises(eqlib.EqlibCalculationFailedError):
            e.save("eq.bin")

    # the earlier file is left exactly as it was
    assert Path("eq.bin").read_bytes() == first


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root writes to a read-only file",
)
def test_save_onto_a_read_only_file_is_an_error_not_an_abort():
    """An existing file without write permission is opened for reading by
    FWOPEN, which then returns 0; the first WRITE of EQSAVE fails. That is
    an error return, not the end of the process."""
    with _solved() as e:
        e.save("eq.bin")
        first = Path("eq.bin").read_bytes()
        os.chmod("eq.bin", 0o444)
        try:
            with pytest.raises(eqlib.EqlibCalculationFailedError):
                e.save("eq.bin")
        finally:
            os.chmod("eq.bin", 0o644)
        # the handle is still usable
        e.save("again.bin")
    assert Path("eq.bin").read_bytes() == first
    assert os.path.getsize("again.bin") > 0


@pytest.mark.parametrize("modefw", [1, 2, 4, 5, 6, 7])
def test_save_refuses_the_file_modes_that_ask_on_unit_5(modefw):
    """With MODEFW 1 or 2 FWOPEN asks Y/N before it overwrites, with 4 to 7
    it asks for the file name, both on unit 5: the JSON-RPC pipe of a stdio
    server. Only 0 (overwrite) and 3 (refuse an existing file) are taken."""
    with _solved() as e:
        e.save("eq.bin")
        first = Path("eq.bin").read_bytes()
        e.set_param("MODEFW", modefw)
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("eq.bin")
        assert _files() == before
    assert Path("eq.bin").read_bytes() == first


# ----- a write that fails after the file was opened -----
#
# The save runs in a child process: the size limit is the process's own, and a
# Fortran run-time that ended the process on the refused write would otherwise
# take the test process with it. As measured with gfortran 15 on macOS, no
# statement reports such a write when the file is new: the WRITEs and the
# CLOSE return 0 over a short file, which is what EQSAVE_IERR's comparison of
# the two lengths is for. (Under a 16-byte limit over a file that is not
# empty the first WRITE does report it.) The tests accept either way of
# noticing: an error is raised, the "XX EQSAVE" line is there, the process
# lives.

_CHILD = """
import eqlib
with eqlib.Eq() as e:
    e.run(0)
    {before_save}
    try:
        e.save({path!r})
    except eqlib.EqlibCalculationFailedError:
        print("CHILD: save raised EqlibCalculationFailedError")
    else:
        print("CHILD: save returned")
print("CHILD: alive after save")
"""

_LIMIT = """import resource, signal
    signal.signal(signal.SIGXFSZ, signal.SIG_IGN)     # write() returns EFBIG instead
    resource.setrlimit(resource.RLIMIT_FSIZE, ({limit}, {limit}))"""


def _save_in_a_child(path, before_save="pass"):
    python_root = str(_HERE.parents[2])
    inherited = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([python_root, *inherited])}
    child = subprocess.run(
        [sys.executable, "-c", _CHILD.format(path=path, before_save=before_save)],
        env=env, capture_output=True, text=True, timeout=100)
    assert child.returncode == 0, child.stdout[-2000:] + child.stderr[-2000:]
    assert "CHILD: alive after save" in child.stdout
    return child.stdout


def test_the_child_process_saves_when_nothing_is_in_the_way():
    """The control of the two tests below."""
    out = _save_in_a_child("eq.bin")
    assert "CHILD: save returned" in out
    full = os.path.getsize("eq.bin")
    assert full > 0
    # and the limit of the next test is below this length
    assert full > 4096


@pytest.mark.skipif(sys.platform == "win32", reason="needs RLIMIT_FSIZE")
@pytest.mark.parametrize("limit", [16, 4096])
def test_a_write_the_system_refuses_is_an_error(limit):
    """A file size limit stands in for a full disk: 16 bytes cut the first
    record, 4096 a later one."""
    out = _save_in_a_child("eq.bin", _LIMIT.format(limit=limit))
    assert "CHILD: save raised EqlibCalculationFailedError" in out
    assert "XX EQSAVE" in out
    # at most the limit: the run-time's buffer decides how much of it is
    # flushed before a write is refused (GFORTRAN_UNFORMATTED_BUFFER_SIZE)
    assert os.path.getsize("eq.bin") <= limit


@pytest.mark.skipif(not os.path.exists("/dev/full"), reason="no /dev/full on this system")
def test_a_full_device_is_an_error():
    """Every write to ``/dev/full`` is refused for lack of space. The line of
    ``EQSAVE_IERR`` is asked for: without it the error would only be
    ``eq_save``'s look for a non-empty file, which any device fails."""
    out = _save_in_a_child("/dev/full")
    assert "CHILD: save raised EqlibCalculationFailedError" in out
    assert "XX EQSAVE" in out


# ----- the entry without an argument -----

def _argument_less_eqsave(e):
    """``EQSAVE`` as the EQ menu calls it. It has no C binding: the symbol is
    the compiler's name for an external procedure. The call passes a null
    pointer: a routine without an argument never looks at it, one that takes
    ``IERR_OUT`` writes through it and ends the process, so the test cannot
    pass by accident on an ``EQSAVE`` that grew an argument."""
    entry = getattr(e._lib, "eqsave_", None)
    assert entry is not None, "libeqapi.so has no eqsave_: the argument-less EQSAVE is gone"
    entry.restype = None
    entry.argtypes = [ctypes.c_void_p]
    entry(None)


def test_the_argument_less_eqsave_still_writes_the_file():
    with _solved() as e:
        e.save("by_api.bin")
        e.set_param_str("KNAMEQ", "by_entry.bin")
        _argument_less_eqsave(e)
    assert Path("by_entry.bin").read_bytes() == Path("by_api.bin").read_bytes()


# ----- paths KNAMEQ cannot hold -----

def test_save_refuses_a_bytes_path_and_leaves_knameq_alone():
    with _solved() as e:
        e.save("first.bin")
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save(b"second.bin")
        assert _files() == before
        # KNAMEQ is still first.bin: the entry without an argument writes there
        os.remove("first.bin")
        _argument_less_eqsave(e)
        assert os.path.exists("first.bin") and not os.path.exists("second.bin")


def test_save_refuses_a_path_that_is_not_ascii():
    with _solved() as e:
        before = _files()
        with pytest.raises(eqlib.EqlibInvalidParamError):
            e.save("平衡.bin")
        assert _files() == before
