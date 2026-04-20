"""Property-based fan-out parity for wrlib.

The Fortran namelist semantics declared in ``wr/wrparm.f90:87-96`` and
re-implemented in the C ABI by ``wr/wr_api.f90::wr_propagate_namelist_profiles``:
when ``MODEL_PROF==0``, an unsubscripted scalar write to PROFN1 / PROFN2
/ PROFT1 / PROFT2 / PROFU1 / PROFU2 fans out from element (1) to all
NSMAX species before the first ``wr_run`` step.

This test verifies that the Python set_param path matches: for each
covered name, setting the unsubscripted scalar form must produce the
same ``to_dict()`` output as setting every per-species element by
hand. A regression in the fan-out (or in the registry's idx==0
handling) would produce drift on NS>=2 fields.

Coverage: the 6 PROFN/PROFT/PROFU scalars, one subTest each.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "wr" / "libwrapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _wrlib_importable() -> bool:
    try:
        import wrlib  # noqa: F401
    except Exception:
        return False
    return True


# All 6 namelist profile knobs in plcomm that fan out via
# wr_propagate_namelist_profiles. Each is an NSM-element array so the
# subscript form NAME[i] writes element i directly, while the bare
# NAME form writes element 1 + relies on the fan-out.
FANOUT_PARAMS = (
    "PROFN1", "PROFN2",
    "PROFT1", "PROFT2",
    "PROFU1", "PROFU2",
)

#: Override value used in both halves of the parity check. Picked to
#: differ from the test001 fixture's PROFN1=3.7/PROFN2=2.7 defaults so
#: a regression that ignores the override is detected.
OVERRIDE_VALUE = 4.5


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libwrapi.so not built at {DEFAULT_SO}; run `make -C wr libwrapi.so`",
)
@unittest.skipUnless(_wrlib_importable(), "python/wrlib not importable")
class TestWrlibFanoutParity(unittest.TestCase):
    """scalar-set vs element-set parity for PROFN/PROFT/PROFU scalars."""

    NRAYMAX = 1  # cheap: 1 ray * NSTPMAX is plenty to see a drift

    def _run_case(self, apply_extra) -> dict:
        """Run test001 with an extra apply-overlay; return scalar block + ray RAYS_END.

        The fan-out only changes per-species PROFN/T/U values, which feed
        cold dispersion ``omega_pe^2`` along the ray. Hence drifts are
        most visible in the integrated ray state (rays_end) -- we
        compare the entire to_dict for the fullest signal.
        """
        from wrlib import Wrlib
        from wrlib.tests.fixtures import wr_test001_params as base
        with Wrlib() as wr:
            base.apply(wr)
            wr.set_param("NRAYMAX", float(self.NRAYMAX))
            apply_extra(wr)
            wr.run(0)
            return wr.get_state().to_dict()

    def test_scalar_vs_elementwise_parity(self):
        # NSMAX from the test001 fixture is 4; both halves of the test
        # must see the same NSMAX so the fan-out target counts match.
        NSMAX = 4
        for name in FANOUT_PARAMS:
            with self.subTest(param=name):
                # (a) scalar form: registry sets element (1); the
                # subsequent wr_run() call fan-outs to (2..NSMAX) via
                # wr_propagate_namelist_profiles.
                a = self._run_case(
                    lambda wr, n=name: wr.set_param(n, OVERRIDE_VALUE),
                )
                # (b) element-wise: every species set explicitly so the
                # fan-out is a no-op on top of identical state.
                def _apply_b(wr, n=name, ns=NSMAX):
                    for i in range(1, ns + 1):
                        wr.set_param(f"{n}[{i}]", OVERRIDE_VALUE)
                b = self._run_case(_apply_b)
                self.assertEqual(
                    a, b,
                    f"{name}: scalar vs element-wise to_dict differ",
                )


if __name__ == "__main__":
    unittest.main()
