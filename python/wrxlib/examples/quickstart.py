"""Smallest possible Wrxlib run: init, set a few params, run, print.

Mirrors the ITER ECCD ray-tracing case from
``test_run/inputs/wrx_iter01.in`` (the ``wrxlib.tests.fixtures.
wrx_iter01_params`` fixture) with ``NRAYMAX`` trimmed to 1 so the
example finishes in a few seconds.

Run from the repository root::

    PYTHONPATH=python \\
        python3 python/wrxlib/examples/quickstart.py

Prerequisites:
  - ``make -C wrx libwrxapi.so`` has been run once.
  - Optional: ``WRXLIB_PATH`` set if the library lives outside the repo.
  - ``Wrxlib.run()`` has no env gate at the library level; the
    historical ``WRX_RUN_OK=1`` requirement applied only to the
    pytest suite and was flipped default-on by PR #166 (root-cause
    SEGV fixed in PR #123).
  - Use ``--dry-run`` to skip the FFI cycle entirely.
"""
from __future__ import annotations

import argparse
import sys

from wrxlib import Wrxlib


def _apply_iter_eccd(wrx: Wrxlib) -> None:
    """Apply a trimmed ``wrx_iter01`` namelist to an open Wrxlib handle."""
    wrx.set_params(MODELG=2, MODELQ=0, RR=6.2, RA=2.0, RB=2.2, BB=5.3,
                   Q0=1.0, QA=3.5, PROFJ=1.0, NSMAX=2,
                   NRAYMAX=1, NSTPMAX=2000,
                   MDLWRI=2, MDLWRQ=1, MDLWRG=1, MDLWRP=1, MDLWRW=0,
                   pne_threshold=1.0e-6, SMAX=2.0, DELS=1.0e-3)
    # Per-species (D + electrons)
    wrx.set_param("PA[1]", 2.0);    wrx.set_param("PA[2]", 5.4462e-4)
    wrx.set_param("PZ[1]", 1.0);    wrx.set_param("PZ[2]", -1.0)
    wrx.set_param("PN[1]", 1.0);    wrx.set_param("PN[2]", 1.0)
    wrx.set_param("PNS[1]", 0.05);  wrx.set_param("PNS[2]", 0.05)
    wrx.set_param("PTPR[1]", 10.0); wrx.set_param("PTPP[1]", 10.0)
    wrx.set_param("PTPR[2]", 10.0); wrx.set_param("PTPP[2]", 10.0)
    wrx.set_param("PTS[1]", 0.5);   wrx.set_param("PTS[2]", 0.5)
    wrx.set_param("PROFN1[1]", 2.0);  wrx.set_param("PROFN1[2]", 2.0)
    wrx.set_param("PROFN2[1]", 1.0);  wrx.set_param("PROFN2[2]", 1.0)
    wrx.set_param("PROFT1[1]", 2.0);  wrx.set_param("PROFT1[2]", 2.0)
    wrx.set_param("PROFT2[1]", 1.0);  wrx.set_param("PROFT2[2]", 1.0)
    wrx.set_param("MODELP[1]", 206); wrx.set_param("MODELP[2]", 206)
    wrx.set_param("MODELV[1]", 3);   wrx.set_param("MODELV[2]", 0)
    wrx.set_param("NCMIN[1]", -3);   wrx.set_param("NCMIN[2]", -3)
    wrx.set_param("NCMAX[1]", 3);    wrx.set_param("NCMAX[2]", 3)
    # EC launcher at R=8.0 m, 170 GHz, 10 deg toroidal angle
    wrx.set_param("RFIN[1]", 170.0e3)
    wrx.set_param("RPIN[1]", 8.0)
    wrx.set_param("ZPIN[1]", 0.0)
    wrx.set_param("PHIIN[1]", 0.0)
    wrx.set_param("ANGPIN[1]", 0.0)
    wrx.set_param("ANGTIN[1]", 10.0)
    wrx.set_param("UUIN[1]", 1.0)
    wrx.set_param("MODEWIN[1]", 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nray-request", type=int, default=0,
                        help="override NRAYMAX for wrx_run (0 keeps namelist)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate argument parsing only; skip FFI calls")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] would call Wrxlib().run(nray_request={args.nray_request})")
        return 0

    with Wrxlib() as wrx:
        _apply_iter_eccd(wrx)
        wrx.run(nray_request=args.nray_request)
        state = wrx.get_state()

    print(f"NRAYMAX={state.nraymax}  NSAMAX={state.nsamax}  "
          f"NSTPMAX={state.nstpmax}")
    print(f"pwr_tot       = {state.scalars['pwr_tot']:.6g}")
    if state.pwr_nray:
        print(f"ray 1 absorbed power  = {state.pwr_nray[0]:.6g}")
        print(f"ray 1 ended at step    = {state.nstp_end[0]}")
    if state.pwrmax_rs_nsa:
        head = ", ".join(f"{v:.3g}" for v in state.pwrmax_rs_nsa)
        print(f"per-species peak (rs)  = [{head}]")
    if state.pwrmax_rl_nsa:
        head = ", ".join(f"{v:.3g}" for v in state.pwrmax_rl_nsa)
        print(f"per-species peak (rl)  = [{head}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
