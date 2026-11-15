"""3x3 sweep over eq:RR and eq:BB, collecting WPT for each cell.

Mirrors the trlib / eqlib sweep pattern but uses TOT's namespaced
parameters. One ``Tot`` context per cell so each case starts from a
fresh ``tot_init`` state (TOT keeps singleton COMMON-block state).

Run from the repository root::

    PYTHONPATH=python python3 python/totlib/examples/parameter_sweep.py --dry-run
    PYTHONPATH=python python3 python/totlib/examples/parameter_sweep.py

Stub status note:
  Since Phase L-6, ``tot.run`` / ``tot.get_state`` work. The script still
  reports ``nan`` (printed as NOT_IMPL) for a cell where they raise
  ``TotlibNotImplementedError`` (rc=4, which only the L-3/L-4 stubs
  returned).
"""
from __future__ import annotations

import argparse
import math
import sys
from typing import Iterable, List, Tuple

from totlib import Tot, TotlibNotImplementedError


def _sweep(rr_vals: Iterable[float], bb_vals: Iterable[float],
           ntmax: int) -> List[Tuple[float, float, float]]:
    """Return list of ``(eq:RR, eq:BB, WPT)`` tuples for each grid cell."""
    rows: List[Tuple[float, float, float]] = []
    for rr in rr_vals:
        for bb in bb_vals:
            with Tot() as tot:
                tot.set_params({
                    "eq:RR":    rr,
                    "eq:BB":    bb,
                    "eq:RIP":   1.5,
                    "tr:RA":    2.0,
                    "tr:DT":    0.01,
                    "tr:NTMAX": ntmax,
                    "fp:NSMAX": 2,
                    "ti:RR":    rr,
                })
                tot.set_param("tr:PN[1]", 1.0)
                tot.set_param("tr:PN[2]", 1.0)
                try:
                    tot.run(ntmax=ntmax)
                    wpt = tot.get_state().scalars["WPT"]
                except TotlibNotImplementedError:
                    wpt = float("nan")
            rows.append((rr, bb, wpt))
    return rows


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ntmax", type=int, default=10,
                        help="time-steps per cell (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the grid only; skip FFI calls")
    args = parser.parse_args(argv)

    rr_vals = (6.0, 6.5, 7.0)
    bb_vals = (4.5, 5.3, 6.0)

    if args.dry_run:
        print(f"[dry-run] grid: eq:RR={list(rr_vals)} x eq:BB={list(bb_vals)}"
              f" ntmax={args.ntmax}")
        return 0

    rows = _sweep(rr_vals, bb_vals, args.ntmax)
    print(f"{'eq:RR':>6} {'eq:BB':>6} {'WPT':>14}")
    for rr, bb, wpt in rows:
        if math.isnan(wpt):
            print(f"{rr:6.2f} {bb:6.2f} {'NOT_IMPL':>14}")
        else:
            print(f"{rr:6.2f} {bb:6.2f} {wpt:14.6g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
