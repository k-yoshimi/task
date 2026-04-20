"""Layer 4: 3x3 parameter sweep smoke test.

The goal is *not* numerical validation -- it is to prove that the
``init -> set_param x N -> run -> get_state -> finalize`` cycle can be
driven in a loop without crashing the library (regression guard against
leaked state or dangling SAVE variables inside ``eqcom*_mod`` MODULEs).

For each ``(RR, BB)`` pair on a 3x3 grid we:

* open a *fresh* :class:`eqlib.Eq` handle (re-init per sample, matching
  the trlib L-6 fix in PR #83),
* apply the ``eq_iter01`` fixture as a realistic baseline parameter set,
* override ``RR`` and ``BB`` for this grid point,
* drive ``eq_run(mode=1)``,
* record the post-run grid dimensions and verify they stay invariant.

A change in ``nrgmax`` / ``nzgmax`` / ``npsmax`` across cells signals
that ``eqcom*_mod`` state leaked across cycles, so we fail loudly. Nine
successful cycles -> PASS.

Skip gates (all must pass for the class to run):

* libeqapi.so is importable via :func:`eqlib._ffi._candidate_paths`,
* eqlib package is importable,
* the ``test_run/test_output/eq_iter01/eqdata.ITER01`` file exists --
  the sweep runs ``eq_run(mode=1)`` which loads a real EQDSK; if
  the L-0 baseline has not been generated yet we skip with an
  instruction to ``./test_run/run_tests.sh eq_iter01`` first.
"""
from __future__ import annotations

import contextlib
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
TEST_OUTPUT_DIR = REPO / "test_run" / "test_output"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from eqlib import _ffi  # noqa: E402


@contextlib.contextmanager
def _pushd(target: Path):
    """chdir to ``target`` inside a ``with`` block, restore on exit.

    EQRTSK / EQDSK loads in eqfile.f90 open ``KNAMEQ`` relative to the
    current working directory, so MODELG=3 fixtures must run from
    ``test_run/test_output/<case>/`` where the eqdata file lives.
    """
    prev = Path.cwd()
    os.chdir(target)
    try:
        yield target
    finally:
        os.chdir(prev)


def _any_so_exists() -> bool:
    """True if libeqapi.so is present at any known candidate path."""
    env = os.environ.get("EQLIB_PATH")
    if env and Path(env).exists():
        return True
    return any(p.exists() for p in _ffi._candidate_paths())


def _eqlib_importable() -> bool:
    try:
        import eqlib  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(
    _any_so_exists(),
    "libeqapi.so not built at any candidate path "
    "(eq/libeqapi.so or lib/libeqapi.so); "
    "run `make -C eq libeqapi.so`",
)
@unittest.skipUnless(_eqlib_importable(), "python/eqlib not importable")
class TestSweep(unittest.TestCase):
    """3x3 RR x BB grid; smoke-only (no numerical regression)."""

    #: ``MODE`` passed to ``eq.run(mode=...)`` for each grid point.
    #: 1 == real EQDSK load via ``equnit::eq_load`` (only implemented mode).
    MODE = 1

    #: Grid centres sit near the ITER01 baseline so every point is a
    #: physically plausible perturbation rather than a pathological
    #: extreme that could crash for non-regression reasons.
    RR_VALUES = (5.8, 6.2, 6.6)
    BB_VALUES = (5.0, 5.3, 5.6)

    def test_3x3_grid_completes(self):
        """Re-init per sample; verify nrgmax/nzgmax/npsmax stay invariant.

        This is the trlib PR #83 fix translated to eqlib: the fresh
        ``Eq()`` context per ``(rr, bb)`` cell guarantees
        ``eq_init`` is called from a clean state, so any leak from a
        previous cell would either crash or surface as a dimension
        change. Nine successful cycles with stable dims -> PASS.
        """
        from eqlib import Eq
        from eqlib.tests.fixtures import eq_iter01_params

        # eq.run(mode=1) loads ``eqdata.ITER01`` relative to CWD, so we
        # cd into the L-0 test_output directory that holds the file.
        # If the L-0 baseline has not been generated yet, skip with an
        # actionable hint rather than failing with rc=3.
        eqdata_dir = TEST_OUTPUT_DIR / "eq_iter01"
        knameq = eq_iter01_params.STRINGS.get("KNAMEQ", "eqdata.ITER01")
        if not (eqdata_dir / knameq).exists():
            self.skipTest(
                f"eqdata '{knameq}' missing under {eqdata_dir}; "
                "run `./test_run/run_tests.sh eq_iter01` first."
            )

        results = []
        with _pushd(eqdata_dir):
            for rr in self.RR_VALUES:
                for bb in self.BB_VALUES:
                    # Re-init per sample (mirror trlib PR #83 fix). A
                    # fresh Eq context guarantees eq_init is called
                    # from scratch, so any TRCOMM-style leak in
                    # eqcom*_mod would surface as a dimension change
                    # or a hard crash.
                    with Eq() as eq:
                        eq_iter01_params.apply(eq)
                        eq.set_param("RR", float(rr))
                        eq.set_param("BB", float(bb))
                        eq.run(mode=self.MODE)
                        state = eq.get_state()
                        results.append((rr, bb, state))

        # All 9 points must have completed.
        self.assertEqual(
            len(results), 9, f"expected 9 results, got {len(results)}",
        )

        # nrgmax/nzgmax/npsmax must stay invariant across all cells:
        # any change here means the re-init did not actually reset
        # eqcom*_mod state and we have a regression to chase down.
        nrg0 = results[0][2].nrgmax
        nzg0 = results[0][2].nzgmax
        nps0 = results[0][2].npsmax
        for rr, bb, st in results:
            with self.subTest(rr=rr, bb=bb):
                self.assertGreater(st.nrgmax, 0, f"RR={rr} BB={bb} nrgmax=0")
                self.assertEqual(
                    st.nrgmax, nrg0,
                    f"nrgmax leak at RR={rr} BB={bb}: {st.nrgmax} vs {nrg0}",
                )
                self.assertEqual(
                    st.nzgmax, nzg0,
                    f"nzgmax leak at RR={rr} BB={bb}: {st.nzgmax} vs {nzg0}",
                )
                self.assertEqual(
                    st.npsmax, nps0,
                    f"npsmax leak at RR={rr} BB={bb}: {st.npsmax} vs {nps0}",
                )


if __name__ == "__main__":
    unittest.main()
