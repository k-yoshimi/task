"""A parameter set after a run re-preps the module, whoever set it (#253).

``tr_api`` / ``fp_api`` / ``ti_api`` used to clear their private "prepared"
flag inside ``<mod>_set_param`` only. tot's ``<mod>:`` dispatcher
(``tot/tot_param_registry.f90``) calls the registries directly, so a set
through ``Tot`` after a run left the flag standing: the next ``tot_run``
continued the old state with ``tr_prep`` skipped, and the #189 pre-run
species check never fired. The registries now count every successful set
and the API re-preps when the count moved since its last prep.

Observable: ``tr_prep`` resets ``NT`` and ``T`` to zero, so a set followed by
``run(1)`` leaves ``nt == 1`` (restart) instead of ``nt == previous + 1``
(continue). That is what ``trlib`` has always done; ``Tot`` now agrees.

fp and ti are checked on the mono image (``libtotapi_mono.so``, one copy
of every module) with raw ctypes: for fp a count changed through
``tot_set_param`` must show in the next ``fp_get_state`` (it reports the
allocated extent, #248), for ti ``NT`` must restart; both only happen when
``<mod>_prep`` ran again. The default image is not used for these two:
``libtotapi.so`` carries five PIC copies of pl / eq / bpsd (one per
sibling ``lib*api.so``, no ``-Bsymbolic``); on ELF the dynamic linker
picks one definer per symbol across all copies, so the pl / eq state
that ``tot_init`` prepared and the state ``fp_run`` touches are not
guaranteed to live in the same copy. ``fp_run`` through that image
crashed on Linux CI (SIGSEGV / SIGBUS) while the mono image passed;
macOS's two-level namespaces bind each library to its own copy and hide
it. No product path calls ``fp_run`` / ``ti_run`` through
``libtotapi.so`` after ``tot_init`` (``tot_run`` drives tr only;
``TotPipeline`` uses ``Fplib``'s own handle without ``tot_init``), and
running fp / ti alongside tot in one process is what the mono image
exists for.

eq has no prep to redo; what a set after a run invalidates there is
``eq_save``, which writes the parameters as they stand over fields computed
for the old ones. eq's registry counts sets as well (not ``MODEFR``,
``MODEFW`` or the string parameters), ``eq_run`` records the count when it
computes or loads the equilibrium, and ``eq_save`` refuses when it moved:
checked on the mono image, where ``tot_set_param("eq:...")`` and ``eq_save``
reach one copy of eq.

Process isolation: ``pytestmark`` requests per-test forking (effective when
pytest-forked is installed, which CI and local dev have), because every
module keeps SAVE'd state in the shared library.
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

pytestmark = [pytest.mark.forked]

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from tilib.tests._data_cwd import TiDataCwdMixin  # noqa: E402

DEFAULT_TOT_SO = REPO / "tot" / "libtotapi.so"
DEFAULT_TR_SO = REPO / "tr" / "libtrapi.so"


def _tot_so() -> Path:
    env = os.environ.get("TOTLIB_PATH")
    return Path(env) if env else DEFAULT_TOT_SO


def _tr_so() -> Path:
    env = os.environ.get("TRLIB_PATH")
    return Path(env) if env else DEFAULT_TR_SO


def _mono_so() -> str:
    # Absolute before any chdir (TiDataCwdMixin moves into a temp dir).
    p = os.environ.get("MONO_LIB_PATH", "")
    return os.path.abspath(p) if p and os.path.exists(p) else ""


# The guards below run in setUp, not at class-decoration time: the .so
# files and MONO_LIB_PATH are mutable preconditions, and a decorator
# evaluates them once at import (Bugbot flagged that pattern on #221).
def _skip_unless_tot(tc: unittest.TestCase) -> None:
    if not _tot_so().exists():
        tc.skipTest(f"libtotapi.so not built at {_tot_so()}; run `make -C tot libtotapi.so`")


def _skip_unless_tr(tc: unittest.TestCase) -> None:
    if not _tr_so().exists():
        tc.skipTest(f"libtrapi.so not built at {_tr_so()}; run `make -C tr libtrapi.so`")


def _skip_unless_mono(tc: unittest.TestCase) -> None:
    if not _mono_so():
        tc.skipTest("MONO_LIB_PATH not set or missing; build with "
                    "`make -C tot libtotapi_mono.so`")


# A small DT keeps each step cheap and finite on the default tr namelist
# (same choice as test_lifecycle.py).
_DT = 0.001


class TestTotSetAfterRun(unittest.TestCase):
    """``Tot.set_param("tr:...")`` after ``run`` restarts, as ``Trlib`` does."""

    def setUp(self):
        _skip_unless_tot(self)
        _skip_unless_tr(self)

    def test_set_after_run_restarts_like_trlib(self):
        from totlib import Tot
        from trlib import Trlib

        with Tot() as tot:
            tot.set_param("tr:DT", _DT)
            tot.run(2)
            tot_before = tot.get_state().nt
            tot.set_param("tr:DT", 2 * _DT)
            tot.run(1)
            tot_after = tot.get_state().nt

        with Trlib() as tr:
            tr.set_param("DT", _DT)
            tr.run(2)
            tr_before = tr.get_state().nt
            tr.set_param("DT", 2 * _DT)
            tr.run(1)
            tr_after = tr.get_state().nt

        self.assertEqual((tr_before, tr_after), (2, 1),
                         "trlib: set_param after run must restart (tr_prep resets NT)")
        self.assertEqual((tot_before, tot_after), (tr_before, tr_after),
                         "Tot must follow trlib's set-after-run semantics (#253)")

    def test_set_after_run_reaches_the_pre_run_check(self):
        """The #189 species check runs where tr_prep is about to run; a
        tot-dispatched NSMAX=3 after a run must reach it, not continue."""
        from totlib import Tot, TotlibError

        with Tot() as tot:
            tot.set_param("tr:DT", _DT)
            tot.run(1)
            tot.set_param("tr:NSMAX", 3)   # species 3 has PN = PNS = 0
            with self.assertRaises(TotlibError):
                tot.run(1)

    def test_failed_set_does_not_restart(self):
        """A set the registry refused changed nothing: the run continues."""
        from totlib import Tot, TotlibError

        with Tot() as tot:
            tot.set_param("tr:DT", _DT)
            tot.run(2)
            with self.assertRaises(TotlibError):
                tot.set_param("tr:NO_SUCH_PARAMETER", 1.0)
            tot.run(1)
            self.assertEqual(tot.get_state().nt, 3)


# --- fp / ti through the same image ---------------------------------------

def _load_image(path: str) -> ctypes.CDLL:
    lib = ctypes.CDLL(os.path.abspath(path))
    for name in ("tot_init", "tot_finalize"):
        fn = getattr(lib, name)
        fn.restype = ctypes.c_int
        fn.argtypes = []
    lib.tot_set_param.restype = ctypes.c_int
    lib.tot_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]
    return lib


def _check_layout(lib: ctypes.CDLL, mod: str, state_cls) -> None:
    """The image fills ``state_cls``'s layout: the wrappers' check (#246).

    These tests pass raw ctypes structs to the image, without going
    through fplib or tilib, which run this check when they load a
    library; a stale image would be written past the struct instead of
    failing here.
    """
    from _abi_check import AbiMismatchError, check_state_layout
    if mod == "fp":
        from fplib._ffi import FP_STATE_ABI_VERSION as version
    elif mod == "ti":
        from tilib._ffi import TI_STATE_ABI_VERSION as version
    else:
        raise AssertionError(f"no state layout version known for {mod!r}")
    try:
        check_state_layout(lib, prefix=mod, struct=state_cls,
                           expected_version=version,
                           lib_name=os.path.basename(lib._name))
    except AbiMismatchError as exc:
        raise AssertionError(str(exc)) from exc


def _drive_through_tot(lib: ctypes.CDLL, mod: str, state_cls, *,
                       steps_before: int, param: str, value: float,
                       steps_after: int, field: str):
    """tot_init; <mod>_run(steps_before); tot_set_param("<mod>:<param>");
    <mod>_run(steps_after); tot_finalize.

    Returns ``field`` of ``<mod>_get_state`` before the set and after the
    second run.
    """
    _check_layout(lib, mod, state_cls)
    run = getattr(lib, f"{mod}_run")
    run.restype = ctypes.c_int
    run.argtypes = [ctypes.c_int]
    get_state = getattr(lib, f"{mod}_get_state")
    get_state.restype = ctypes.c_int
    get_state.argtypes = [ctypes.POINTER(state_cls)]

    rc = lib.tot_init()
    if rc != 0:
        raise AssertionError(f"tot_init returned {rc}")
    try:
        st = state_cls()
        rc = run(steps_before)
        if rc != 0:
            raise AssertionError(f"{mod}_run({steps_before}) returned {rc} before the set")
        get_state(ctypes.byref(st))
        before = getattr(st, field)
        rc = lib.tot_set_param(f"{mod}:{param}".encode(), float(value))
        if rc != 0:
            raise AssertionError(f"tot_set_param({mod}:{param}) returned {rc}")
        rc = run(steps_after)
        if rc != 0:
            raise AssertionError(f"{mod}_run({steps_after}) returned {rc} after the set")
        get_state(ctypes.byref(st))
        return before, getattr(st, field)
    finally:
        lib.tot_finalize()


class _FpReprepCase:
    """fp body; the subclass says which image to load."""

    image: str = ""
    NEW_NRMAX = 20

    def test_fp_reprepares_after_tot_set(self):
        """fp_get_state reports the allocated radial extent (#245/#248), so
        nrmax follows a changed NRMAX only once fp_prep reallocated."""
        from fplib._ffi import FpStateC
        before, after = _drive_through_tot(
            _load_image(self.image), "fp", FpStateC,
            steps_before=0, param="NRMAX", value=self.NEW_NRMAX,
            steps_after=0, field="nrmax")
        self.assertNotEqual(before, self.NEW_NRMAX,
                            "pick a NEW_NRMAX that differs from fp's default")
        self.assertEqual(after, self.NEW_NRMAX,
                         "fp_run after tot_set_param('fp:NRMAX') must re-run fp_prep (#253)")


class _TiReprepCase(TiDataCwdMixin):
    """ti_prep reads ../adpost/ADPOST-DATA relative to the cwd; the mixin
    from tilib's tests arranges that layout."""

    image: str = ""

    def test_ti_reprepares_after_tot_set(self):
        """ti_get_state reports NRMAX straight from the namelist, so the
        observable is NT: ti_prep resets it to 0 (ti/tiprep.f90) and ti_run
        advances it, so run(2), set, run(1) ends at 1 only after a re-prep
        (3 when the old state continues)."""
        from tilib._ffi import TiStateC
        before, after = _drive_through_tot(
            _load_image(self.image), "ti", TiStateC,
            steps_before=2, param="NRMAX", value=20,
            steps_after=1, field="nt")
        self.assertEqual(before, 2, "ti_run(2) must advance NT to 2")
        self.assertEqual(after, 1,
                         "ti_run after tot_set_param('ti:NRMAX') must re-run ti_prep (#253)")


class _FpScalarsCase:
    """fp's seven global scalars (#233) read zero after a set of tot's fp:
    parameters, as after fp_set_param: the registry's count moved, so the
    state is no longer the one of the last preparation."""

    image: str = ""

    def test_fp_scalars_read_zero_after_a_tot_set(self):
        from fplib._ffi import FpStateC
        from fplib.state import SCALAR_FIELDS
        lib = _load_image(self.image)
        _check_layout(lib, "fp", FpStateC)
        lib.fp_run.restype = ctypes.c_int
        lib.fp_run.argtypes = [ctypes.c_int]
        lib.fp_get_state.restype = ctypes.c_int
        lib.fp_get_state.argtypes = [ctypes.POINTER(FpStateC)]
        rc = lib.tot_init()
        if rc != 0:
            raise AssertionError(f"tot_init returned {rc}")
        try:
            st = FpStateC()
            if lib.fp_run(0) != 0:
                raise AssertionError("fp_run(0) failed")
            # fp_get_state zeroes the scalars before it can return an error:
            # a failed read must not pass for the zeros expected below
            if lib.fp_get_state(ctypes.byref(st)) != 0:
                raise AssertionError("fp_get_state failed before the set")
            before = {name: getattr(st, name) for name in SCALAR_FIELDS}
            rc = lib.tot_set_param(b"fp:DELT", 0.002)
            if rc != 0:
                raise AssertionError(f"tot_set_param(fp:DELT) returned {rc}")
            if lib.fp_get_state(ctypes.byref(st)) != 0:
                raise AssertionError("fp_get_state failed after the set")
            after = {name: getattr(st, name) for name in SCALAR_FIELDS}
        finally:
            lib.tot_finalize()
        self.assertGreater(before["PLASMA_VOLUME"], 0.0)
        self.assertEqual(after, {name: 0.0 for name in SCALAR_FIELDS},
                         "fp_get_state after tot_set_param('fp:DELT') must report zero scalars")


class TestSiblingReprepOnMonoImage(_FpReprepCase, unittest.TestCase):
    """libtotapi_mono.so: one image, one copy of every module's state.

    Runs in CI's mono routing step (MONO_LIB_PATH set); skipped elsewhere.
    """

    def setUp(self):
        _skip_unless_mono(self)
        self.image = _mono_so()
        super().setUp()


class TestFpScalarsAfterTotSetOnMonoImage(_FpScalarsCase, unittest.TestCase):
    def setUp(self):
        _skip_unless_mono(self)
        self.image = _mono_so()
        super().setUp()


class TestTiReprepOnMonoImage(_TiReprepCase, unittest.TestCase):
    def setUp(self):
        _skip_unless_mono(self)
        self.image = _mono_so()
        super().setUp()


EQ_ERR_INVALID = 1   # eq/eq_api.h


class _EqSaveCase:
    """tot_init; MODEFW=0; eq_run(0); tot_set_param_str("eq:KNAMEQ");
    optionally tot_set_param("eq:<param>"); eq_save. The file is written in
    a temporary directory under a relative name (KNAMEQ holds 80
    characters). MODEFW is set here rather than taken from the init order,
    and KNAMEQ goes through tot's string dispatcher, which the registry
    does not count."""

    image: str = ""

    def _save_after(self, param=None, value=0.0):
        lib = _load_image(self.image)
        lib.eq_run.restype = ctypes.c_int
        lib.eq_run.argtypes = [ctypes.c_int]
        lib.eq_set_param.restype = ctypes.c_int
        lib.eq_set_param.argtypes = [ctypes.c_char_p, ctypes.c_double]
        lib.tot_set_param_str.restype = ctypes.c_int
        lib.tot_set_param_str.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.eq_save.restype = ctypes.c_int
        lib.eq_save.argtypes = []
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                rc = lib.tot_init()
                if rc != 0:
                    raise AssertionError(f"tot_init returned {rc}")
                try:
                    if lib.eq_set_param(b"MODEFW", 0.0) != 0:
                        raise AssertionError("eq_set_param(MODEFW) failed")
                    if lib.eq_run(0) != 0:
                        raise AssertionError("eq_run(0) failed")
                    if lib.tot_set_param_str(b"eq:KNAMEQ", b"eq.bin") != 0:
                        raise AssertionError("tot_set_param_str(eq:KNAMEQ) failed")
                    if param is not None:
                        rc = lib.tot_set_param(f"eq:{param}".encode(), float(value))
                        if rc != 0:
                            raise AssertionError(f"tot_set_param(eq:{param}) returned {rc}")
                    return lib.eq_save(), os.path.exists("eq.bin")
                finally:
                    lib.tot_finalize()
            finally:
                os.chdir(cwd)

    def test_eq_save_without_a_set_writes(self):
        self.assertEqual(self._save_after(), (0, True))

    def test_eq_save_refuses_after_a_tot_set(self):
        self.assertEqual(self._save_after("RR", 3.5), (EQ_ERR_INVALID, False),
                         "eq_save after tot_set_param('eq:RR') must refuse, as after eq_set_param")

    def test_eq_save_still_writes_after_a_tot_set_of_a_file_mode(self):
        self.assertEqual(self._save_after("MODEFW", 0), (0, True))


class TestEqSaveAfterTotSetOnMonoImage(_EqSaveCase, unittest.TestCase):
    def setUp(self):
        _skip_unless_mono(self)
        self.image = _mono_so()
        super().setUp()


if __name__ == "__main__":
    unittest.main()
