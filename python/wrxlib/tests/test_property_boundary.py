"""Property-based boundary-value sweeps for wrxlib (run-only).

Mutates selected parameters from the ``wrx_demo`` fixture and asserts
``wrx.run()`` either:

* (a) succeeds without raising, OR
* (b) fails with the expected exception type from
  :mod:`wrxlib.errors`.

Scope: widen Layer-3 coverage beyond the single canonical fixture; this
is complementary to ``test_equivalence.py`` and ``test_sweep.py``. We
intentionally do NOT call :py:meth:`wrxlib.Wrxlib.get_state` here: the
goal is crash-safety on parameter perturbation, not numerical
regression -- coverage of the state-extraction path lives in
``test_equivalence.py`` / ``test_sweep.py``.

Skipped when ``libwrxapi.so`` is not built or when ``WRX_RUN_OK=0``.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pytest

# XFAIL_REMOVE_WITH_144: SIGABRT (signal 6) in wrx_heap_reuse_bug_class
# (#110 family) surfaces on mutated-parameter sweeps. Tracked in #144.
# Applied CI-only because the crash is heap-layout dependent and this
# dev host does not reproduce it. strict=True per CLAUDE.md — when
# #144 lands in CI, XPASS → FAILED → CI red → marker removal forced.
# pytest-forked reports SIGABRT worker exits as FAILED (not
# INTERNALERROR), so xfail catches it cleanly.
_CI = os.environ.get("CI", "").lower() == "true"
_XFAIL_WRX_HEAP_144 = pytest.mark.xfail(
    condition=_CI, strict=True,
    reason="SIGABRT in wrx heap-reuse path — tracked in #144; "
           "marker must be removed once that lands.",
)

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from wrxlib import _ffi  # noqa: E402


# Match the gating used by test_wrxlib.py / test_sweep.py:
# default WRX_RUN_OK to ON post-2026-04-20.
RUN_OK = os.environ.get("WRX_RUN_OK", "1") != "0"


def _any_so_exists() -> bool:
    return any(p.exists() for p in _ffi._candidate_paths())


def _wrxlib_importable() -> bool:
    try:
        import wrxlib  # noqa: F401
    except Exception:
        return False
    return True


# Values supported by wrx; the wrx_demo fixture uses MDLWRI=2.
# Unlike the wr-side path, wrx does not branch on MDLWRI inside its
# ray-tracing kernels (it's a tag-only field), so the sweep covers a
# small range without hitting unsupported branches.
MDLWRI_VALUES = (1, 2, 3)
PNE_THRESHOLD_VALUES = (1.0e-7, 1.0e-6, 1.0e-5)


@unittest.skipUnless(
    _any_so_exists(),
    "libwrxapi.so not built at any candidate path "
    "(wrx/libwrxapi.so or lib/libwrxapi.so); run `make -C wrx libwrxapi.so`",
)
@unittest.skipUnless(_wrxlib_importable(), "python/wrxlib not importable")
@unittest.skipUnless(
    RUN_OK,
    "WRX_RUN_OK=1 required: wrx_run may segfault on libgrf::grd1d in the "
    "current L-4 build (see python/wrxlib/README.md Known limitation).",
)
class TestWrxlibBoundaryValues(unittest.TestCase):
    """Boundary-value mutations on top of the ``wrx_demo`` fixture.

    Run-only: skips ``get_state`` so the SEGV-prone state extraction
    path is not exercised here.
    """

    NRAYMAX = 1

    def _apply_and_run(self, wrx, mutations: dict) -> None:
        """Apply demo, overlay mutations + reduced NRAYMAX, run."""
        from wrxlib.tests.fixtures import wrx_demo_params as base
        base.apply(wrx)
        wrx.set_param("NRAYMAX", float(self.NRAYMAX))
        for name, value in mutations.items():
            wrx.set_param(name, float(value))
        wrx.run(self.NRAYMAX)

    # --- sweeps -----------------------------------------------------------
    @_XFAIL_WRX_HEAP_144    # XFAIL_REMOVE_WITH_144
    def test_MDLWRI_sweep(self):
        from wrxlib import Wrxlib
        from wrxlib.errors import WrxlibError
        for mdlwri in MDLWRI_VALUES:
            with self.subTest(MDLWRI=mdlwri):
                with Wrxlib() as wrx:
                    try:
                        self._apply_and_run(wrx, {"MDLWRI": mdlwri})
                    except WrxlibError:
                        # Some MDLWRI values require extra setup; treat
                        # a controlled failure as acceptable.
                        continue

    @_XFAIL_WRX_HEAP_144    # XFAIL_REMOVE_WITH_144
    def test_pne_threshold_sweep(self):
        """pne_threshold (cold dispersion floor) over 3 decades."""
        from wrxlib import Wrxlib
        from wrxlib.errors import WrxlibError
        for thr in PNE_THRESHOLD_VALUES:
            with self.subTest(pne_threshold=thr):
                with Wrxlib() as wrx:
                    try:
                        self._apply_and_run(wrx, {"pne_threshold": thr})
                    except WrxlibError:
                        continue

    def test_unknown_param_raises(self):
        """Unregistered parameter names raise WrxlibParamError."""
        from wrxlib import Wrxlib
        from wrxlib.errors import WrxlibParamError
        with Wrxlib() as wrx:
            with self.assertRaises(WrxlibParamError):
                wrx.set_param("DEFINITELY_NOT_A_PARAM", 1.0)


if __name__ == "__main__":
    unittest.main()
