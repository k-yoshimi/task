"""Run once and dump ``EqState.to_dict()`` as JSON.

Useful to compare eqlib output to the Phase L-0 baseline JSON produced
by ``test_run/scripts/extract_eq_metrics.py`` — the two layouts share
uppercase keys for direct ``compare_metrics.py`` diffing.

Run from the repository root::

    PYTHONPATH=python python3 python/eqlib/examples/state_dump.py \\
        --out /tmp/eqlib_state.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eqlib import Eq


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knameq", default="eqdata",
                        help="equilibrium file path (default: eqdata)")
    parser.add_argument("--modelg", type=int, default=3,
                        help="MODELG value (default: 3)")
    parser.add_argument("--mode", type=int, default=1,
                        help="eq.run(mode=...) (default: 1)")
    parser.add_argument("--out", type=Path, default=None,
                        help="output JSON path (default: stdout)")
    parser.add_argument("--indent", type=int, default=2,
                        help="JSON indent (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate argument parsing only; skip FFI calls")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] KNAMEQ={args.knameq!r} MODELG={args.modelg} "
              f"mode={args.mode} out={args.out}")
        return 0

    with Eq() as eq:
        eq.set_params(RR=3.0, RA=1.0, RKAP=1.5, RDLT=0.0,
                      BB=3.0, RIP=1.0, MODELG=args.modelg)
        eq.set_param_str("KNAMEQ", args.knameq)
        eq.run(mode=args.mode)
        state = eq.get_state()

    payload = state.to_dict()
    text = json.dumps(payload, indent=args.indent, sort_keys=True)
    if args.out is None:
        print(text)
    else:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}  "
              f"({len(payload['PSIPS'])} psi-surface rows, "
              f"{len(payload['scalars'])} scalars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
