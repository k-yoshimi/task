"""L-7b-ii: Trlib.check_bpsd_pull() unit tests.

Three cases:

  B-1: Fresh Trlib() init -> check_bpsd_pull() == False
       (BPSD slots empty, tr_init does not pre-populate)
  B-2: Closed Trlib -> TrlibError on check_bpsd_pull
  B-3: Smoke: function does not leak Fortran-side exceptions

Skipped when libtrapi.so is absent.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import Trlib, TrlibError  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
class TestCheckBpsdPull(unittest.TestCase):
    """Trlib.check_bpsd_pull() (L-7b-ii)."""

    def test_check_bpsd_pull_fresh_init_returns_false(self):
        """B-1: fresh Trlib() init has no BPSD data; pull returns False."""
        with Trlib() as tr:
            self.assertFalse(tr.check_bpsd_pull())

    def test_check_bpsd_pull_on_closed_raises(self):
        """B-2: closed Trlib must reject check_bpsd_pull (lifecycle guard)."""
        tr = Trlib()
        tr.close()
        with self.assertRaises(TrlibError):
            tr.check_bpsd_pull()

    def test_check_bpsd_pull_smoke_no_exception_leak(self):
        """B-3: ierr handling inside Fortran helper must not surface as
        Python exception; the wrapper returns bool, never raises (except
        on closed Trlib, covered by B-2)."""
        with Trlib() as tr:
            # call repeatedly; should never raise
            for _ in range(5):
                result = tr.check_bpsd_pull()
                self.assertIsInstance(result, bool)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
