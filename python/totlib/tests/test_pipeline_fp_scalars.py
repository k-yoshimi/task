"""An FP step of run_pipeline reports ``timefp`` and its counts beside the
seven global scalars of ``FpState.scalars``.

Requires libfpapi.so. Before FpState had a ``scalars`` dict the FP step's
scalars were its numeric top-level attributes; when the dict arrived they
were replaced by it, and ``timefp`` was gone from pipeline results.
"""
import os

import pytest

from fplib import _ffi
from fplib.state import SCALAR_FIELDS
from totlib import TotPipeline


def _lib_present() -> bool:
    # Where the loader will look, in its order (MONO_LIB_PATH, FPLIB_PATH,
    # then <repo>/fp and <repo>/lib), without loading anything while pytest
    # collects.
    mono = os.environ.get("MONO_LIB_PATH", "").strip()   # the loader strips this one
    if mono:
        return os.path.exists(mono)
    lib = os.environ.get("FPLIB_PATH")                    # and takes this one as it is
    if lib:
        return os.path.exists(lib)
    return any(path.exists() for path in _ffi._candidate_paths())


pytestmark = pytest.mark.skipif(
    not _lib_present(),
    reason="requires libfpapi.so — run scripts/setup.sh first",
)

FP_TOP_LEVEL = ("nrmax", "nsamax", "npmax", "nthmax", "ntg2", "timefp")


def test_fp_step_scalars_hold_timefp_the_counts_and_the_globals():
    pipe = TotPipeline()
    try:
        result = pipe.run_pipeline([("fp", {"ntmax": 1})])
        state = pipe._ensure_module("fp").get_state()
    finally:
        pipe.close()
    scalars = result.last("fp").scalars
    assert set(scalars) == set(FP_TOP_LEVEL) | set(SCALAR_FIELDS)
    assert scalars["timefp"] == state.timefp > 0.0
    for name in FP_TOP_LEVEL[:-1]:
        assert scalars[name] == float(getattr(state, name))
    for name in SCALAR_FIELDS:
        assert scalars[name] == state.scalars[name]
    assert scalars["PLASMA_VOLUME"] > 0.0
