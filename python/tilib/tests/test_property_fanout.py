"""Property-based fan-out parity for tilib.

PROFJ1 / PROFJ2 in ti/ti_param_registry.f90 are scalar fields (radial
current-density profile exponent, see CASE-line for PROFJ1 / PROFJ2):
both the unsubscripted form ``set_param("PROFJ1", v)`` and the
subscripted form ``set_param("PROFJ1[1]", v)`` should target the same
slot. This is the same principle as the tr fan-out test; we keep it
separate per-module so failures attribute to the right wrapper.

If the registry ever upgrades PROFJ1/2 to per-species arrays (matching
the WR PROFN1/PROFT1 pattern) this test will need to be split into a
real fan-out vs element-wise comparison (see the WR analogue in
``python/wrlib/tests/test_property_fanout.py``).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
PYTHON_ROOT = REPO / "python"
DEFAULT_SO = REPO / "ti" / "libtiapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from tilib.tests._data_cwd import TiDataCwdMixin  # noqa: E402


def _tilib_importable() -> bool:
    try:
        import tilib  # noqa: F401
    except Exception:
        return False
    return True


FANOUT_PARAMS = ("PROFJ1", "PROFJ2")
FANOUT_NTMAX = 2


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtiapi.so not built at {DEFAULT_SO}; run `make -C ti libtiapi.so`",
)
@unittest.skipUnless(_tilib_importable(), "python/tilib not importable")
class TestTilibFanoutParity(TiDataCwdMixin, unittest.TestCase):
    """scalar-set vs element-set parity for PROFJ1/PROFJ2."""

    def _run_case(self, apply_extra) -> dict:
        """Run ti_min with an extra apply-overlay, return scalar block.

        Comparing the scalar block keeps the assertion narrow; if the
        scalar PROFJ exponent is a single shared field, the radial
        profile arrays will also be identical, but the scalar block is
        sufficient and faster to diff.
        """
        from tilib import TiLib
        from tilib.tests.fixtures import ti_iter01_params as base
        with TiLib() as ti:
            base.apply(ti)
            ti.set_param("NTMAX", float(FANOUT_NTMAX))
            apply_extra(ti)
            ti.run(FANOUT_NTMAX)
            payload = ti.get_state().to_dict()
        # ti to_dict shape: top-level T / NRMAX etc are scalars; pull
        # only those (drop arrays for a cheap comparison).
        return {
            k: v
            for k, v in payload.items()
            if not isinstance(v, (list, dict))
        }

    def test_scalar_vs_elementwise_parity(self):
        NSMAX = 1  # ti_min default
        for name in FANOUT_PARAMS:
            with self.subTest(param=name):
                a = self._run_case(
                    lambda ti, n=name: ti.set_param(n, 2.0),
                )
                def _apply_b(ti, n=name, ns=NSMAX):
                    for i in range(1, ns + 1):
                        ti.set_param(f"{n}[{i}]", 2.0)
                b = self._run_case(_apply_b)
                self.assertEqual(
                    a, b,
                    f"{name}: scalar vs element-wise top-level scalars differ",
                )


if __name__ == "__main__":
    unittest.main()
