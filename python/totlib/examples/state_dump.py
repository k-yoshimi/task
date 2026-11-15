"""Run once and dump ``TotState.to_dict()`` as JSON.

Useful to compare totlib output to the trlib baseline JSON produced by
``tools/extract_tr_metrics.py`` — the two layouts are aligned (TOT
adds a top-level ``presence`` sub-dict noting which sub-modules
contributed).

Run from the repository root::

    PYTHONPATH=python python3 python/totlib/examples/state_dump.py --dry-run
    PYTHONPATH=python python3 python/totlib/examples/state_dump.py \
        --out /tmp/totlib_state.json

Stub status note:
  Since Phase L-6, ``tot_get_state`` works. The script still catches
  ``TotlibNotImplementedError`` (rc=4, which only the L-3/L-4 stubs
  returned) and exits cleanly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from totlib import Tot, TotlibNotImplementedError


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ntmax", type=int, default=10,
                        help="time-steps to run before snapshot (default: 10)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output JSON path (default: stdout)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON indent (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate argument parsing only; skip FFI calls")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] ntmax={args.ntmax} out={args.out}")
        return 0

    with Tot() as tot:
        tot.set_params({
            "eq:RR":    6.5,
            "eq:BB":    5.3,
            "eq:RIP":   1.5,
            "tr:RA":    2.0,
            "tr:DT":    0.01,
            "tr:NTMAX": args.ntmax,
            "fp:NSMAX": 2,
            "ti:RR":    6.5,
        })
        tot.set_param("tr:PN[1]", 1.0)
        tot.set_param("tr:PN[2]", 1.0)
        try:
            tot.run(ntmax=args.ntmax)
            state = tot.get_state()
        except TotlibNotImplementedError as e:
            print(f"[rc=4] state dump not implemented in this library: {e}",
                  file=sys.stderr)
            return 0

    payload = state.to_dict()
    text = json.dumps(payload, indent=args.indent, sort_keys=True)
    if args.out is None:
        print(text)
    else:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}  "
              f"({len(payload['profile'])} radial rows, "
              f"{len(payload['scalars'])} scalars, "
              f"presence={payload['presence']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
