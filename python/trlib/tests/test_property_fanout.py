"""Property-based list-vs-scalar fan-out parity for trlib.

Fortran namelist semantics: an unsubscripted scalar write like
``PROFN1=2.0`` fans out to all NSMAX species. In tr/trcomm the
``PROFN1`` / ``PROFN2`` symbols are declared as scalars (a single
radial-profile exponent shared across species), so both the scalar form
``set_param("PROFN1", v)`` and the subscripted form
``set_param("PROFN1[1]", v)`` target the same slot.

This test verifies that parity on the Python set_param path -- i.e.,
the registry dispatcher (``tr/tr_param_registry.f90``) accepts the
subscripted form and produces the same ``to_dict()`` after a short run.

See ``wr/wr_api.f90::wr_propagate_namelist_profiles`` for the analogous
fan-out on the WR side (array-typed PROFN1 there); the WR version of
this parity test lives in ``python/wrlib/tests/test_property_fanout.py``.
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
DEFAULT_SO = REPO / "tr" / "libtrapi.so"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


@contextlib.contextmanager
def _pushd(target: Path):
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


# Parameters covered by the fan-out parity check. Expand once the
# registry grows to cover more profile knobs (PROFT1/2, PROFU1/2 in tr
# are not yet registered).
FANOUT_PARAMS = ("PROFN1", "PROFN2")

#: Keep NTMAX tiny: both halves of every pair run init -> run -> state.
FANOUT_NTMAX = 2


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
@unittest.skipUnless(_trlib_importable(), "python/trlib not importable")
class TestTrlibFanoutParity(unittest.TestCase):
    """scalar-set vs element-set parity for PROFN1/PROFN2."""

    WORKDIR = TEST_OUTPUT_DIR / "tr_tst2"
    EQDATA = WORKDIR / "eqdata.TST-2"

    def setUp(self):
        if not self.EQDATA.exists():
            self.skipTest(
                f"eqdata missing at {self.EQDATA}; "
                "run `./test_run/run_tests.sh tr_tst2` first."
            )

    def _run_case(self, apply_extra) -> dict:
        """Run tst2 with an extra apply-overlay, return scalars dict only.

        We only compare the scalar block because mesh-level arrays are
        identical-in-value when the scalar-shape parameter is identical.
        Keeping the compare surface narrow makes failure triage quick.
        """
        from trlib import Trlib
        from trlib.tests.fixtures import tr_tst2_params as base
        with Trlib() as tr:
            base.apply(tr)
            tr.set_param("NTMAX", float(FANOUT_NTMAX))
            apply_extra(tr)
            tr.run(FANOUT_NTMAX)
            return tr.get_state().to_dict()["scalars"]

    def test_scalar_vs_elementwise_parity(self):
        NSMAX = 2  # matches tst2
        for name in FANOUT_PARAMS:
            with self.subTest(param=name):
                with _pushd(self.WORKDIR):
                    # (a) scalar write: tr registry treats PROFN1 as a
                    # scalar so this sets the single field directly.
                    scalars_a = self._run_case(
                        lambda tr, n=name: tr.set_param(n, 2.0),
                    )
                    # (b) per-element writes: since the registry ignores
                    # the [i] subscript for scalar symbols, element-wise
                    # writes must produce the same final state.
                    def _apply_b(tr, n=name, ns=NSMAX):
                        for i in range(1, ns + 1):
                            tr.set_param(f"{n}[{i}]", 2.0)
                    scalars_b = self._run_case(_apply_b)
                self.assertEqual(
                    scalars_a, scalars_b,
                    f"{name}: scalar vs element-wise scalars differ",
                )


if __name__ == "__main__":
    unittest.main()
