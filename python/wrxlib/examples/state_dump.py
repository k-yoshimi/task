"""Run once and dump ``WrxState.to_dict()`` as JSON.

Useful to compare wrxlib output to baseline JSON and to feed
``compare_metrics.py`` for cross-build diffs (the dict layout follows
the same ``rays`` / ``profile_rs`` / ``profile_rl`` shape used by
``wrlib.state``; here the profile axis is per-species rather than
per-radius).

``Wrxlib.run()`` has no env gate at the library level; the
historical ``WRX_RUN_OK=1`` requirement applied only to the pytest
suite and was flipped default-on by PR #166 (root-cause SEGV fixed
in PR #123). ``--dry-run`` validates argument parsing without
invoking the FFI.

Run from the repository root::

    PYTHONPATH=python \\
        python3 python/wrxlib/examples/state_dump.py \\
        --out /tmp/wrxlib_state.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wrxlib import Wrxlib


def _apply_iter_eccd(wrx: Wrxlib) -> None:
    """Apply a trimmed ``wrx_iter01`` namelist (NRAYMAX=1, NSTPMAX=2000)."""
    wrx.set_params(MODELG=2, MODELQ=0, RR=6.2, RA=2.0, RB=2.2, BB=5.3,
                   Q0=1.0, QA=3.5, PROFJ=1.0, NSMAX=2,
                   NRAYMAX=1, NSTPMAX=2000,
                   MDLWRI=2, MDLWRQ=1, MDLWRG=1, MDLWRP=1, MDLWRW=0,
                   pne_threshold=1.0e-6, SMAX=2.0, DELS=1.0e-3)
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
    parser.add_argument("--out", type=Path, default=None,
                        help="output JSON path (default: stdout)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON indent (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate argument parsing only; skip FFI calls")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] nray_request={args.nray_request} out={args.out}")
        return 0

    with Wrxlib() as wrx:
        _apply_iter_eccd(wrx)
        wrx.run(nray_request=args.nray_request)
        state = wrx.get_state()

    payload = state.to_dict()
    text = json.dumps(payload, indent=args.indent, sort_keys=True)
    if args.out is None:
        print(text)
    else:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}  "
              f"(NRAYMAX={payload['NRAYMAX']}, "
              f"NSAMAX_WR={payload['NSAMAX_WR']}, "
              f"{len(payload['scalars'])} scalars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
