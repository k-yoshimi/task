#!/usr/bin/env python3
"""Convert tot_regress.dat into a JSON for regression comparison.

Schema:
    {
      "NT": int, "NRMAX": int, "NSMAX": int,
      "modules": {"TR_PRESENT": 0|1, "TI_PRESENT": 0|1,
                  "FP_PRESENT": 0|1, "WR_PRESENT": 0|1},
      "scalars": {...},   # TR scalars when TR_PRESENT=1, else {}
      "profile": [...],   # TR profile rows when TR_PRESENT=1, else []
    }

Compatible with the existing compare_metrics.py (which already inspects
NT/NRMAX/NSMAX/scalars/profile and ignores unknown top-level keys like
"modules"). The "modules" dict carries presence flags for downstream
phases (L-2 tot_get_state, L-6 metrics_from_state) where richer per-
module dumps will be added; today these flags are part of the regression
signature so a structural drift (e.g. tot stops calling wr_init) still
fails the check.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCALAR_KEYS = {
    "T", "WPT", "AJT", "AJRFT", "Q0", "BETA0", "BETAP0", "BETAA", "BETAN",
    "TAUE1", "TAUE2", "ZEFF0", "ALI", "RQ1",
}
MODULE_KEYS = {"TR_PRESENT", "TI_PRESENT", "FP_PRESENT", "WR_PRESENT"}
RE_PROFILE_HEADER = re.compile(r"^#\s*profile columns:")
# `KEY=VAL` (uppercase letters / digits / underscore, then '=') is the
# unambiguous signal we are back in scalar/key territory. The Fortran
# dump emits TI_PRESENT=/FP_PRESENT=/WR_PRESENT= AFTER the profile rows
# WITHOUT a separating blank line or '#' comment, so relying on those
# alone leaves the parser stuck in `in_profile=True` and misclassifies
# the trailing presence flags as malformed profile rows.
RE_KEY_VAL = re.compile(r"^[A-Z_][A-Z0-9_]*\s*=")


def parse(dump_path: Path) -> dict:
    lines = dump_path.read_text().splitlines()
    result = {
        "NT": 0, "NRMAX": 0, "NSMAX": 0,
        "modules": {},
        "scalars": {},
        "profile": [],
    }
    in_profile = False
    for raw in lines:
        line = raw.strip()
        if not line:
            # Blank line terminates the current section (e.g. profile block).
            in_profile = False
            continue
        if RE_PROFILE_HEADER.match(line):
            in_profile = True
            continue
        if line.startswith("#"):
            # Any non-profile-header comment line also closes the profile
            # block, so subsequent `KEY=VAL` sections are parsed correctly.
            in_profile = False
            continue
        if RE_KEY_VAL.match(line):
            # A KEY=VAL line unambiguously closes the profile block, even
            # without a preceding blank line or '#' comment.
            in_profile = False
        if not in_profile:
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key in MODULE_KEYS:
                result["modules"][key] = int(val)
            elif key in ("NT", "NRMAX", "NSMAX"):
                result[key] = int(val)
            elif key in SCALAR_KEYS:
                result["scalars"][key] = float(val)
            else:
                pass  # ignore unknown
        else:
            parts = line.split()
            if len(parts) < 4:
                continue
            nsmax = result.get("NSMAX", 0)
            if nsmax <= 0:
                raise SystemExit("profile row encountered before NSMAX")
            expected = 1 + 2 * nsmax + 2  # NR + RN(NSMAX) + RT(NSMAX) + AJ + QP
            if len(parts) != expected:
                raise SystemExit(
                    f"malformed profile row (expected {expected} cols, got {len(parts)}): {raw}"
                )
            nr = int(parts[0])
            rn = [float(x) for x in parts[1 : 1 + nsmax]]
            rt = [float(x) for x in parts[1 + nsmax : 1 + 2 * nsmax]]
            aj = float(parts[1 + 2 * nsmax])
            qp = float(parts[2 + 2 * nsmax])
            result["profile"].append({"NR": nr, "RN": rn, "RT": rt, "AJ": aj, "QP": qp})

    if result["modules"].get("TR_PRESENT", 0) == 1:
        if result["NRMAX"] == 0:
            raise SystemExit("TR_PRESENT=1 but NRMAX missing")
        if len(result["profile"]) != result["NRMAX"]:
            raise SystemExit(
                f"profile row count {len(result['profile'])} != NRMAX {result['NRMAX']}"
            )
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", type=Path)
    args = ap.parse_args()
    json.dump(parse(args.dump), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
