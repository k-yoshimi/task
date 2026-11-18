"""3x3 sweep over RR and BB, collecting qaxis for each cell.

Mirrors design spec §6.4 pattern 1. One ``Eq`` context per cell so each
case starts from a fresh ``eq_init`` state.

Run from the repository root::

    PYTHONPATH=python python3 python/eqlib/examples/parameter_sweep.py
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Tuple

from eqlib import Eq


def _sweep(rr_vals: Iterable[float], bb_vals: Iterable[float],
           knameq: str, modelg: int,
           mode: int) -> List[Tuple[float, float, float]]:
    """Return list of ``(RR, BB, qaxis)`` tuples for each grid cell."""
    rows: List[Tuple[float, float, float]] = []
    for rr in rr_vals:
        for bb in bb_vals:
            with Eq() as eq:
                eq.set_params(RR=rr, BB=bb, RA=1.0, RKAP=1.5,
                              RDLT=0.0, RIP=1.0, MODELG=modelg)
                eq.set_param_str("KNAMEQ", knameq)
                eq.run(mode=mode)
                qaxis = eq.get_state().scalars["qaxis"]
            rows.append((rr, bb, qaxis))
    return rows


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knameq", default="eqdata",
                        help="equilibrium file path (default: eqdata)")
    parser.add_argument("--modelg", type=int, default=3,
                        help="MODELG value (default: 3)")
    parser.add_argument("--mode", type=int, default=1,
                        help="eq.run(mode=...) (default: 1)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the grid only; skip FFI calls")
    args = parser.parse_args(argv)

    rr_vals = (2.5, 3.0, 3.5)
    bb_vals = (2.5, 3.0, 3.5)

    if args.dry_run:
        print(f"[dry-run] grid: RR={list(rr_vals)} x BB={list(bb_vals)} "
              f"KNAMEQ={args.knameq!r} MODELG={args.modelg} mode={args.mode}")
        return 0

    rows = _sweep(rr_vals, bb_vals, args.knameq, args.modelg, args.mode)
    print(f"{'RR':>6} {'BB':>6} {'qaxis':>14}")
    for rr, bb, qaxis in rows:
        print(f"{rr:6.2f} {bb:6.2f} {qaxis:14.6g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
