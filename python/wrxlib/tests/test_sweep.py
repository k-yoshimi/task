"""Layer 4: 3x3 parameter sweep smoke test.

The goal is *not* numerical validation -- it is to prove that the
``init -> set_param x N -> run -> get_state -> finalize`` cycle can be
driven in a loop without crashing the library (regression guard
against leaked state or dangling SAVE variables inside WRCOMM).

For each ``(RFIN, ANGPIN)`` pair on a 3x3 grid we:

* open a fresh :class:`wrxlib.Wrxlib` handle,
* apply the ``wrx_iter01`` fixture as a realistic baseline parameter
  set,
* override ``NRAYMAX`` to 1 and swap in the grid point's
  ``RFIN[1]`` / ``ANGPIN[1]``,
* run ``wrx_run`` (``nray_request=1``),
* recursively walk ``state.to_dict()`` and assert every numeric field
  is finite.

A NaN/Inf on any point signals that WRCOMM state leaked across cycles,
so we fail loudly. Nine successful cycles -> PASS.

Gated on:

* libwrxapi.so exists at a known candidate path
  (:func:`wrxlib._ffi._candidate_paths`),
* wrxlib is importable,
* ``WRX_RUN_OK=1`` (same segfault-risk gate as
  ``test_equivalence.py``; see README.md Known Limitation).
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

from wrxlib import _ffi  # noqa: E402


# See test_wrxlib.py for context: gate defaults ON post-2026-04-20.
RUN_OK = os.environ.get("WRX_RUN_OK", "1") != "0"


def _any_so_exists() -> bool:
    return any(p.exists() for p in _ffi._candidate_paths())


def _wrxlib_importable() -> bool:
    try:
        import wrxlib  # noqa: F401
    except Exception:
        return False
    return True


def _assert_finite_tree(obj, path: str, tc: unittest.TestCase) -> None:
    """Walk ``obj`` recursively; fail if any numeric leaf is NaN/Inf.

    Handles the ``to_dict()`` shape: nested dicts / lists of dicts /
    lists of scalars. Booleans are intentionally skipped (bool is a
    subclass of int but NaN-checking it via ``math.isnan`` raises).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite_tree(v, f"{path}.{k}", tc)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite_tree(v, f"{path}[{i}]", tc)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, float):
        tc.assertFalse(math.isnan(obj), f"NaN at {path}")
        tc.assertFalse(math.isinf(obj), f"Inf at {path}")
    elif isinstance(obj, int):
        # ints cannot be NaN/Inf by definition; nothing to check.
        return
    # strings / None / other: ignore (schema dims are ints, names are
    # strs, both safe).


@unittest.skipUnless(
    _any_so_exists(),
    "libwrxapi.so not built at any candidate path "
    "(wrx/libwrxapi.so or lib/libwrxapi.so); "
    "run `make -C wrx libwrxapi.so`",
)
@unittest.skipUnless(_wrxlib_importable(), "python/wrxlib not importable")
@unittest.skipUnless(
    RUN_OK,
    "WRX_RUN_OK=1 required: wrx_run may segfault on libgrf::grd1d "
    "in the current L-4 build (see README.md Known limitation).",
)
class TestSweep(unittest.TestCase):
    """3x3 RFIN x ANGPIN grid; smoke-only (no numerical regression)."""

    #: Keep NRAYMAX tiny so the whole sweep completes well under the
    #: test_definitions.conf timeout.
    NRAYMAX = 1

    #: Grid centres sit near the ITER01 baseline so every point is a
    #: physically plausible perturbation rather than a pathological
    #: extreme that could crash for non-regression reasons.
    RFIN_VALUES = (140.0e3, 170.0e3, 200.0e3)
    ANGPIN_VALUES = (0.0, 5.0, 10.0)

    def test_3x3_grid_completes(self):
        from wrxlib import Wrxlib
        from wrxlib.tests.fixtures import wrx_iter01_params

        count = 0
        for rfin in self.RFIN_VALUES:
            for ang in self.ANGPIN_VALUES:
                with self.subTest(rfin=rfin, angpin=ang):
                    with Wrxlib() as wrx:
                        # Realistic base parameters from the ITER01
                        # fixture.
                        wrx_iter01_params.apply(wrx)
                        # Override the swept axes and force a single
                        # ray so the sweep stays cheap.
                        wrx.set_param("NRAYMAX", float(self.NRAYMAX))
                        wrx.set_param("RFIN[1]",   float(rfin))
                        wrx.set_param("ANGPIN[1]", float(ang))
                        # nray_request=1 overrides any lingering
                        # namelist NRAYMAX inside wr_prep.
                        wrx.run(int(self.NRAYMAX))
                        state = wrx.get_state()
                        payload = state.to_dict()
                        _assert_finite_tree(
                            payload,
                            f"[rfin={rfin},ang={ang}]",
                            self,
                        )
                        count += 1

        # All 9 points must have completed.
        self.assertEqual(count, 9, f"expected 9 sweep points, got {count}")


if __name__ == "__main__":
    unittest.main()
