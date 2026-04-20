"""Layer 4: 3x3 parameter sweep smoke test.

The goal is *not* numerical validation -- it is to prove that the
``init -> set_param x N -> run -> get_state -> finalize`` cycle can be
driven in a loop without crashing the orchestrator (regression guard
against leaked state or dangling SAVE variables in the per-module
SO chain that ``libtotapi.so`` composes: eq, tr, fp, ti, wrx).

For each ``(eq:RR, eq:BB)`` pair on a 3x3 grid we:

* open a *fresh* :class:`totlib.Tot` handle (re-init per sample, the
  trlib PR #83 / eqlib L-6 fix translated to tot),
* apply the ``tot_demo2014_short`` fixture as a realistic baseline
  parameter set,
* override ``eq:RR`` and ``eq:BB`` for this grid point,
* drive ``tot.run(ntmax=...)``,
* record post-run integrated dimensions and verify they stay invariant.

A change in ``nrmax`` / ``nsmax`` across cells signals that one of the
per-module ``*COMM`` / module variables leaked across cycles, so we fail
loudly. Nine successful cycles -> PASS.

Skip gates (all must pass for the class to run):

* libtotapi.so is importable via :func:`totlib._ffi._candidate_paths`,
* totlib package is importable.

L-6 status: the ``TOT_RUN_OK`` opt-in gate has been retired now that
the orchestrator fan-out (tr + ti + fp + wrx) is wired inside
``libtotapi.so``. This mirrors what was done for ``EQ_RUN_OK`` once
the eq L-6 work landed.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from totlib import _ffi  # noqa: E402


def _any_so_exists() -> bool:
    """True if libtotapi.so is present at any known candidate path."""
    env = os.environ.get("TOTLIB_PATH")
    if env and Path(env).exists():
        return True
    return any(p.exists() for p in _ffi._candidate_paths())


def _totlib_importable() -> bool:
    try:
        import totlib  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(
    _any_so_exists(),
    "libtotapi.so not built at any candidate path "
    "(tot/libtotapi.so or lib/libtotapi.so); "
    "run `make -C tot libtotapi.so`",
)
@unittest.skipUnless(_totlib_importable(), "python/totlib not importable")
class TestSweep(unittest.TestCase):
    """3x3 ``eq:RR`` x ``eq:BB`` grid; smoke-only (no numerical regression)."""

    #: Keep NTMAX tiny so the whole sweep completes well under the
    #: ``test_definitions.conf`` timeout (240 s).
    NTMAX = 1

    #: Grid centres sit near the DEMO2014 baseline (RR=8.5, BB=5.94)
    #: so every point is a physically plausible perturbation rather
    #: than a pathological extreme that could crash for non-regression
    #: reasons.
    RR_VALUES = (8.0, 8.5, 9.0)
    BB_VALUES = (5.5, 5.94, 6.4)

    def test_3x3_grid_completes(self):
        """Re-init per sample; verify nrmax / nsmax stay invariant.

        This is the trlib PR #83 / eqlib L-6 fix translated to totlib:
        the fresh ``Tot()`` context per ``(rr, bb)`` cell guarantees
        ``tot_init`` is called from a clean state so any leak from a
        previous cell would either crash or surface as a dimension
        change. Nine successful cycles with stable dims and finite
        scalars -> PASS.
        """
        from totlib import Tot
        from totlib.tests.fixtures import tot_demo2014_params

        results = []
        for rr in self.RR_VALUES:
            for bb in self.BB_VALUES:
                # Re-init per sample. A fresh Tot context guarantees
                # tot_init is called from scratch so any leak in the
                # composed per-module SOs (eq + tr + fp + ti + wrx)
                # would surface as a dimension change or a hard crash.
                with Tot() as tot:
                    tot_demo2014_params.apply(tot)
                    tot.set_param("eq:RR", float(rr))
                    tot.set_param("eq:BB", float(bb))
                    tot.run(self.NTMAX)
                    state = tot.get_state()
                    results.append((rr, bb, state))

        # All 9 points must have completed.
        self.assertEqual(
            len(results), 9, f"expected 9 results, got {len(results)}",
        )

        # nrmax / nsmax must stay invariant across all cells: any
        # change here means the re-init did not actually reset shared
        # state and we have a regression to chase down.
        nrmax0 = results[0][2].nrmax
        nsmax0 = results[0][2].nsmax
        for rr, bb, st in results:
            with self.subTest(rr=rr, bb=bb):
                self.assertGreater(st.nrmax, 0, f"RR={rr} BB={bb} nrmax=0")
                self.assertEqual(
                    st.nrmax, nrmax0,
                    f"nrmax leak at RR={rr} BB={bb}: "
                    f"{st.nrmax} vs {nrmax0}",
                )
                self.assertEqual(
                    st.nsmax, nsmax0,
                    f"nsmax leak at RR={rr} BB={bb}: "
                    f"{st.nsmax} vs {nsmax0}",
                )
                # Spot-check a key integrated scalar -- WPT (plasma
                # stored energy) must be finite.
                wpt = st.scalars.get("WPT", float("nan"))
                self.assertFalse(
                    math.isnan(wpt),
                    f"NaN WPT at RR={rr} BB={bb}",
                )
                self.assertFalse(
                    math.isinf(wpt),
                    f"Inf WPT at RR={rr} BB={bb}",
                )


if __name__ == "__main__":
    unittest.main()
