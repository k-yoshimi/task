"""3x3 sweep over RFIN[1] (EC frequency) and ANGPIN[1] (poloidal
injection angle), collecting the total absorbed power for each cell.

Mirrors the Layer-4 ``wrxlib_sweep`` regression smoke
(``python/wrxlib/tests/test_sweep.py``) and the design spec pattern 1
(coarse parameter survey). One :class:`Wrxlib` context per cell so each
case starts from a fresh ``wrx_init`` state and the init/finalize
cycle is exercised 9 times back to back.

``Wrxlib.run()`` has no env gate at the library level; the
historical ``WRX_RUN_OK=1`` requirement applied only to the pytest
suite and was flipped default-on by PR #166 (root-cause SEGV fixed
in PR #123). Use ``--dry-run`` to skip the FFI cycle.

Run from the repository root::

    PYTHONPATH=python \\
        python3 python/wrxlib/examples/parameter_sweep.py
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Sequence, Tuple

from wrxlib import Wrxlib


# Fixed physics baseline applied to every cell in the sweep. Values
# mirror the ``wrx_iter01`` fixture with NRAYMAX trimmed to 1 so each
# cell completes quickly.
BASE_SCALARS = {
    "MODELG": 2, "MODELQ": 0, "RR": 6.2, "RA": 2.0, "RB": 2.2, "BB": 5.3,
    "Q0": 1.0, "QA": 3.5, "PROFJ": 1.0, "NSMAX": 2,
    "NRAYMAX": 1, "NSTPMAX": 2000,
    "MDLWRI": 2, "MDLWRQ": 1, "MDLWRG": 1, "MDLWRP": 1, "MDLWRW": 0,
    "pne_threshold": 1.0e-6, "SMAX": 2.0, "DELS": 1.0e-3,
}
BASE_ARRAYS = {
    "PA":      [2.0, 5.4462e-4],
    "PZ":      [1.0, -1.0],
    "PN":      [1.0, 1.0],
    "PNS":     [0.05, 0.05],
    "PTPR":    [10.0, 10.0],
    "PTPP":    [10.0, 10.0],
    "PTS":     [0.5, 0.5],
    "PROFN1":  [2.0, 2.0],
    "PROFN2":  [1.0, 1.0],
    "PROFT1":  [2.0, 2.0],
    "PROFT2":  [1.0, 1.0],
    "MODELP":  [206, 206],
    "MODELV":  [3, 0],
    "NCMIN":   [-3, -3],
    "NCMAX":   [3, 3],
    # Launcher defaults; RFIN[1] and ANGPIN[1] are overridden per cell.
    "RPIN":    [8.0],
    "ZPIN":    [0.0],
    "PHIIN":   [0.0],
    "ANGTIN":  [10.0],
    "UUIN":    [1.0],
    "MODEWIN": [1],
}


def _apply_base(wrx: Wrxlib) -> None:
    for name, value in BASE_SCALARS.items():
        wrx.set_param(name, float(value))
    for name, arr in BASE_ARRAYS.items():
        for i, v in enumerate(arr, start=1):
            wrx.set_param(f"{name}[{i}]", float(v))


def _sweep(rf_vals: Sequence[float], ang_vals: Sequence[float]
           ) -> List[Tuple[float, float, float]]:
    """Return list of ``(RFIN, ANGPIN, pwr_tot)`` tuples."""
    rows: List[Tuple[float, float, float]] = []
    for rf in rf_vals:
        for ang in ang_vals:
            with Wrxlib() as wrx:
                _apply_base(wrx)
                wrx.set_param("RFIN[1]", rf)
                wrx.set_param("ANGPIN[1]", ang)
                wrx.run(nray_request=0)
                s = wrx.get_state()
            rows.append((rf, ang, s.scalars["pwr_tot"]))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the grid only; skip FFI calls")
    args = parser.parse_args(argv)

    rf_vals = (140.0e3, 170.0e3, 200.0e3)   # MHz (EC frequency)
    ang_vals = (0.0, 5.0, 10.0)              # deg (poloidal launch angle)

    if args.dry_run:
        print(f"[dry-run] grid: RFIN={list(rf_vals)} x ANGPIN={list(ang_vals)}")
        return 0

    rows = _sweep(rf_vals, ang_vals)
    print(f"{'RFIN':>10} {'ANGPIN':>8} {'pwr_tot':>14}")
    for rf, ang, pwr in rows:
        print(f"{rf:10.1f} {ang:8.2f} {pwr:14.6g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
