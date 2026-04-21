"""Property-based boundary-value sweeps for trlib.

Mutates selected parameters from the ``tr_tst2`` fixture and asserts the
run either (a) succeeds and produces sane output (finite scalars, shape
matches NRMAX/NSMAX), or (b) fails with the expected exception type.

Scope: widen Layer-3 coverage beyond the single canonical fixture; this
is complementary to ``test_equivalence.py`` (1e-10 reference match) and
``test_sweep.py`` (3x3 RR/BB grid). No baseline comparison here --
boundary-value mutation is about regression / crash-safety, not physics.

Uses :class:`unittest.subTest` for per-mutation attribution so failures
land on a specific (param, value) pair, not on the test method as a
whole. This matches the style used in the existing wrxlib sweep tests.

Runtime budget: each subTest runs tr_tst2 with ``NTMAX=2`` to stay well
under 30 s of additional wall-time for the whole file.
"""
from __future__ import annotations

import contextlib
import math
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"
FIXTURES_DIR = HERE.parent / "fixtures"
DEFAULT_SO = REPO / "tr" / "libtrapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


@contextlib.contextmanager
def _pushd(target: Path):
    """chdir to ``target`` inside a ``with`` block, restore on exit."""
    prev = Path.cwd()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(prev)


def _trlib_importable() -> bool:
    try:
        import trlib  # noqa: F401
    except Exception:
        return False
    return True


#: Mutation NTMAX; a tiny run is enough to exercise init -> run -> state.
BOUNDARY_NTMAX = 2


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
@unittest.skipUnless(_trlib_importable(), "python/trlib not importable")
class TestTrlibBoundaryValues(unittest.TestCase):
    """Boundary-value mutations on top of the ``tr_tst2`` fixture."""

    #: tst2 writes KNAMEQ=eqdata.TST-2; the eqdata file lives under
    #: test_run/test_output/tr_tst2/ after `./test_run/run_tests.sh tr_tst2`,
    #: but CI does not run that script. Fall back to the committed fixture
    #: at python/trlib/tests/fixtures/eqdata.TST-2 so the NSMAX / NRMAX /
    #: DT / RR / BB sweeps actually exercise libtrapi.so instead of being
    #: skipTest'd away in CI.
    WORKDIR_PRIMARY = TEST_OUTPUT_DIR / "tr_tst2"
    WORKDIR_FIXTURE = FIXTURES_DIR
    EQDATA_PRIMARY = WORKDIR_PRIMARY / "eqdata.TST-2"
    EQDATA_FIXTURE = FIXTURES_DIR / "eqdata.TST-2"

    def setUp(self):
        if self.EQDATA_PRIMARY.exists():
            self.WORKDIR = self.WORKDIR_PRIMARY
        elif self.EQDATA_FIXTURE.exists():
            self.WORKDIR = self.WORKDIR_FIXTURE
        else:
            self.skipTest(
                f"eqdata missing at {self.EQDATA_PRIMARY} or "
                f"{self.EQDATA_FIXTURE}; run "
                "`./test_run/run_tests.sh tr_tst2` first."
            )

    def _apply_and_run(self, tr, mutations: dict, ntmax: int) -> "TrState":
        """Apply the tst2 fixture, overlay ``mutations``, run, return state."""
        from trlib.tests.fixtures import tr_tst2_params as base
        base.apply(tr)
        # Shrink NTMAX so the whole subTest budget stays small.
        tr.set_param("NTMAX", float(ntmax))
        for name, value in mutations.items():
            tr.set_param(name, float(value))
        tr.run(ntmax)
        return tr.get_state()

    def _assert_finite_state(self, state) -> None:
        """Assert scalar block is finite and profile shapes match NRMAX/NSMAX."""
        for name, val in state.scalars.items():
            self.assertFalse(math.isnan(val), f"NaN scalar {name}={val}")
            self.assertFalse(math.isinf(val), f"Inf scalar {name}={val}")
        self.assertEqual(
            len(state.RN), state.nrmax,
            f"RN rows {len(state.RN)} != nrmax={state.nrmax}",
        )
        self.assertEqual(
            len(state.AJ), state.nrmax,
            f"AJ length {len(state.AJ)} != nrmax={state.nrmax}",
        )
        if state.nrmax > 0:
            self.assertEqual(
                len(state.RN[0]), state.nsmax,
                f"RN cols {len(state.RN[0])} != nsmax={state.nsmax}",
            )

    # --- sweeps -----------------------------------------------------------
    def test_NSMAX_in_range(self):
        """NSMAX in {1..4} should either run cleanly or raise TrlibError.

        The tst2 fixture is configured for NSMAX=2; mutating to other
        values may leave PA/PZ/PN/PT slots empty (relying on
        tr_init/pl_init defaults). When the run succeeds we assert
        round-trip + finite state; controlled failures are tolerated
        because the property under test is "no crash, no NaN", not
        "always converges".
        """
        from trlib import Trlib
        from trlib.errors import TrlibError
        for nsmax in (1, 2, 3, 4):
            with self.subTest(NSMAX=nsmax):
                with _pushd(self.WORKDIR):
                    with Trlib() as tr:
                        try:
                            state = self._apply_and_run(
                                tr, {"NSMAX": nsmax}, BOUNDARY_NTMAX,
                            )
                        except TrlibError:
                            continue
                        self.assertEqual(state.nsmax, nsmax)
                        self._assert_finite_state(state)

    def test_NSMAX_above_TR_MAX_get_state_raises(self):
        """NSMAX > TR_MAX_NSMAX (=8) must be rejected by tr_get_state.

        The tr_param_registry CASE for NSMAX has no guard (it just
        INT-casts), so set_param accepts the value silently. The
        failure surfaces in tr_get_state which rejects NSMAX > 8 with
        ierr=3 (mapped to TrlibRunError) at tr/tr_api.f90:281. NSMAX=0
        and NSMAX<0 are intentionally NOT covered here because the
        registry guard for them is missing -- see the deferred
        registry-hardening punch-list reported by this PR.
        """
        from trlib import Trlib
        from trlib.errors import TrlibError
        with self.subTest(NSMAX=9):
            with _pushd(self.WORKDIR):
                with Trlib() as tr:
                    with self.assertRaises(TrlibError):
                        self._apply_and_run(
                            tr, {"NSMAX": 9}, BOUNDARY_NTMAX,
                        )

    def test_NRMAX_not_registered(self):
        """NRMAX is intentionally NOT in tr_param_registry yet (deferred).

        The Phase 0 namelist /TR/ exposes NRMAX but the L-3 registry
        does not route it, so set_param('NRMAX', ...) raises
        TrlibParamError. This subtest documents that gap and will FAIL
        (signalling a registry extension) once NRMAX is wired up; at
        that point this method should be replaced with an actual
        sweep checking state.nrmax round-trip.
        """
        from trlib import Trlib
        from trlib.errors import TrlibParamError
        for nrmax in (10, 50, 100):
            with self.subTest(NRMAX=nrmax):
                with _pushd(self.WORKDIR):
                    with Trlib() as tr:
                        with self.assertRaises(TrlibParamError):
                            tr.set_param("NRMAX", float(nrmax))

    def test_DT_sweep(self):
        """Vary DT over 4 decades; tiny DT may not advance but must not NaN."""
        from trlib import Trlib
        from trlib.errors import TrlibError
        for dt in (1.0e-7, 1.0e-5, 1.0e-3):
            with self.subTest(DT=dt):
                with _pushd(self.WORKDIR):
                    with Trlib() as tr:
                        try:
                            state = self._apply_and_run(
                                tr, {"DT": dt}, BOUNDARY_NTMAX,
                            )
                        except TrlibError:
                            # Non-convergence is acceptable at extremes.
                            continue
                        self._assert_finite_state(state)

    def test_RR_sweep(self):
        from trlib import Trlib
        from trlib.errors import TrlibError
        for rr in (0.5, 1.0, 6.2):
            with self.subTest(RR=rr):
                with _pushd(self.WORKDIR):
                    with Trlib() as tr:
                        try:
                            state = self._apply_and_run(
                                tr, {"RR": rr}, BOUNDARY_NTMAX,
                            )
                        except TrlibError:
                            continue
                        self._assert_finite_state(state)

    def test_BB_sweep(self):
        from trlib import Trlib
        from trlib.errors import TrlibError
        for bb in (0.15, 1.5, 5.3):
            with self.subTest(BB=bb):
                with _pushd(self.WORKDIR):
                    with Trlib() as tr:
                        try:
                            state = self._apply_and_run(
                                tr, {"BB": bb}, BOUNDARY_NTMAX,
                            )
                        except TrlibError:
                            continue
                        self._assert_finite_state(state)

    def test_unknown_param_raises(self):
        """Unregistered names must raise TrlibParamError from set_param."""
        from trlib import Trlib
        from trlib.errors import TrlibParamError
        with _pushd(self.WORKDIR):
            with Trlib() as tr:
                with self.assertRaises(TrlibParamError):
                    tr.set_param("DEFINITELY_NOT_A_PARAM", 1.0)


if __name__ == "__main__":
    unittest.main()
