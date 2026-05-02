"""L-7b-i: external driven current scalar verification.

Covers:

* default (un-set) ≡ explicit 0.0 — backward-compat invariant
* I=1.0 MA changes a downstream observable (Q0)
* AJRFT integrates to EXTERNAL_DRIVEN_I within ~1e-12 (Gaussian
  normalization correctness)
* All 3 EXTERNAL_DRIVEN_* scalars round-trip through ``set_param``
  (registry CASE coverage)
* ``validate()`` surfaces RW=0 + I!=0 as ``OUT_OF_RANGE``

Spec: ``docs/superpowers/specs/2026-05-02-l7b-i-external-driven-i-design.md``
Skipped automatically when ``libtrapi.so`` has not been built.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from trlib import Trlib, TrDiagCode  # noqa: E402

REPO = HERE.parents[3]
DEFAULT_SO = REPO / "tr" / "libtrapi.so"


# ITER-like fixture from python/trlib/examples/quickstart.py.
SCALAR_PARAMS = {
    "RR":     8.5,
    "RA":     2.0,
    "RKAP":   1.7,
    "BB":     5.3,
    "NSMAX":  2,
    "DT":     0.1,
    "NTSTEP": 10,
}
ARRAY_PARAMS = (
    ("PN[1]", 1.0),
    ("PN[2]", 1.0),
    ("PT[1]", 1.5),
    ("PT[2]", 1.5),
)


def _apply_fixture(tr: Trlib, extras: dict | None = None) -> None:
    tr.set_params(**SCALAR_PARAMS)
    for name, value in ARRAY_PARAMS:
        tr.set_param(name, value)
    if extras:
        for name, value in extras.items():
            tr.set_param(name, value)


def _run_scalars(extras: dict | None = None) -> dict:
    with Trlib() as tr:
        _apply_fixture(tr, extras)
        tr.run(ntmax=1)
        return dict(tr.get_state().scalars)


@unittest.skipUnless(
    DEFAULT_SO.exists(),
    f"libtrapi.so not built at {DEFAULT_SO}; run `make -C tr libtrapi.so`",
)
class TestExternalDrivenCurrent(unittest.TestCase):

    def test_default_is_noop(self) -> None:
        """Un-set state and explicit ``EXTERNAL_DRIVEN_I=0`` are bit-identical.

        Guards the backward-compat invariant: existing baselines (Layer 1
        demo2014 / ht6m) only hold if the new injection block is fully
        bypassed at I=0.
        """
        s_default = _run_scalars()
        s_zero = _run_scalars({"EXTERNAL_DRIVEN_I": 0.0})
        for k, v_default in s_default.items():
            self.assertEqual(
                v_default, s_zero[k],
                f"{k}: default vs explicit-zero diverged "
                f"({v_default!r} vs {s_zero[k]!r})",
            )

    def test_changes_downstream_q0(self) -> None:
        """I=1.0 MA shifts Q0 measurably from the default-zero baseline.

        Q0 (safety factor on axis) is a clean downstream proxy: AJT is
        a boundary condition (RIPS/RIPE) and so is invariant for ntmax=1.
        """
        s_zero = _run_scalars()
        s_one = _run_scalars({"EXTERNAL_DRIVEN_I": 1.0})
        delta = abs(s_one["Q0"] - s_zero["Q0"])
        self.assertGreater(
            delta, 1.0e-3,
            f"Q0 shift too small ({delta:.3e}); expected >1e-3 from "
            f"EXTERNAL_DRIVEN_I=1.0. baseline Q0={s_zero['Q0']:.6f}, "
            f"with-drive Q0={s_one['Q0']:.6f}",
        )

    def test_ajrft_integrates_to_total(self) -> None:
        """AJRFT exactly equals the requested EXTERNAL_DRIVEN_I [MA].

        Default I=0: AJRFT must be 0 (no PLH/PEC/PIC drive configured).
        I=1.0 MA: AJRFT == 1.0 within Gaussian-quadrature roundoff
        (the trprf normalization makes this an algebraic identity, so
        only floating-point noise should appear).
        """
        s_zero = _run_scalars()
        s_one = _run_scalars({"EXTERNAL_DRIVEN_I": 1.0})
        self.assertEqual(s_zero["AJRFT"], 0.0)
        self.assertTrue(
            math.isclose(s_one["AJRFT"], 1.0, rel_tol=1.0e-12),
            f"AJRFT={s_one['AJRFT']!r} did not match injected I=1.0",
        )

    def test_three_scalars_round_trip(self) -> None:
        """All 3 EXTERNAL_DRIVEN_* scalars are accepted by set_param.

        Catches missing CASE entries in tr_param_registry.f90.
        """
        with Trlib() as tr:
            _apply_fixture(tr, {
                "EXTERNAL_DRIVEN_I":  0.5,
                "EXTERNAL_DRIVEN_R0": 0.2,
                "EXTERNAL_DRIVEN_RW": 0.4,
            })
            tr.run(ntmax=1)

    def test_validate_zero_width_emits_out_of_range(self) -> None:
        """RW=0 + I!=0 surfaces as OUT_OF_RANGE in tr_api_validate."""
        with Trlib() as tr:
            tr.set_param("EXTERNAL_DRIVEN_I", 1.0)
            tr.set_param("EXTERNAL_DRIVEN_RW", 0.0)
            diags = tr.validate()
        matched = [
            d for d in diags
            if d.param == "EXTERNAL_DRIVEN_RW"
            and d.code == TrDiagCode.OUT_OF_RANGE
        ]
        self.assertEqual(
            len(matched), 1,
            f"expected exactly 1 OUT_OF_RANGE diagnostic for "
            f"EXTERNAL_DRIVEN_RW; got {diags}",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
