"""Smallest possible Eqlib run: init, set a few scalars + KNAMEQ, run, print.

Run from the repository root::

    PYTHONPATH=python python3 python/eqlib/examples/quickstart.py

Prerequisites:
  - ``make -C eq libeqapi.so`` has been run once.
  - An equilibrium file readable via the current ``MODELG`` + ``KNAMEQ``
    setting; the defaults below expect a TASK/EQ file named "eqdata"
    (MODELG=3), the format the test fixtures load.
  - Optional: ``EQLIB_PATH`` set if the library lives outside the repo.
"""
from __future__ import annotations

import argparse
import sys

from eqlib import Eq


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knameq", default="eqdata",
                        help="equilibrium file path passed to set_param_str (default: eqdata)")
    parser.add_argument("--modelg", type=int, default=3,
                        help="MODELG value (default: 3 = a TASK/EQ file)")
    parser.add_argument("--mode", type=int, default=1,
                        help="eq.run(mode=...) (default: 1 = the equilibrium-file load; "
                             "0 = the Grad-Shafranov solve, no file, with --modelg 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate argument parsing only; skip FFI calls")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] would call Eq().run(mode={args.mode}) "
              f"with KNAMEQ={args.knameq!r} MODELG={args.modelg}")
        return 0

    with Eq() as eq:
        # Geometry / device scalars (truncated; see tests/fixtures/ for full set).
        eq.set_params(RR=3.0, RA=1.0, RKAP=1.5, RDLT=0.0,
                      BB=3.0, RIP=1.0, MODELG=args.modelg)
        eq.set_param_str("KNAMEQ", args.knameq)
        eq.run(mode=args.mode)
        state = eq.get_state()

    print(f"NRGMAX={state.nrgmax}  NZGMAX={state.nzgmax}  "
          f"NPSMAX={state.npsmax}")
    print(f"raxis = {state.scalars['raxis']:.6g}")
    print(f"zaxis = {state.scalars['zaxis']:.6g}")
    print(f"qaxis = {state.scalars['qaxis']:.6g}")
    print(f"qsurf = {state.scalars['qsurf']:.6g}")
    print(f"betap = {state.scalars['betap']:.6g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
