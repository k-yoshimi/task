"""Equivalence test: hand-written fp→tr coupling vs run_pipeline.

CLAUDE.md non-negotiable: must pass at 1e-10 relative tolerance.
Requires libfpapi.so + libtrapi.so. Run with --forked --timeout=120
--timeout-method=signal per CLAUDE.md test discipline.

Per spec §9.2. Uses the active-drive fixture from spec §8 R3.

L-7b-i: physical EXTERNAL_DRIVEN_I [MA] coupling. Pattern X (direct call)
and pattern Y (TotPipeline.run_pipeline) push the same EXTERNAL_DRIVEN_I
value to tr; the test verifies their tr final scalars match at 1e-10.
"""
import math
import os
import pytest

from fplib import Fplib
from trlib import Trlib
from totlib import TotPipeline
from totlib.pipeline import _state_to_scalars, compute_rjt_volint


def _libs_present() -> bool:
    repo = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    return all(
        os.path.exists(os.path.join(repo, p))
        for p in ("fp/libfpapi.so", "tr/libtrapi.so")
    )


pytestmark = pytest.mark.skipif(
    not _libs_present(),
    reason="requires libfpapi.so + libtrapi.so — run scripts/setup.sh first",
)


# fp active-drive fixture per R3: E0 (induction E-field, V/m) is the
# minimum-viable trigger that produces a non-trivial RJT (~0.946 MA at R0=3, a=1).
FP_PARAMS = {"E0": 0.001}

# tr fixture from python/trlib/examples/quickstart.py (validated in R1-b);
# RR=6.2, RA=2.0 propagate into compute_rjt_volint via the COUPLING_RULES callable.
# Scalar params are set via set_params(); array params use NAME[i] syntax
# and are set individually via set_param().
TR_SCALAR_PARAMS = {
    "RR": 6.2,
    "RA": 2.0,
    "RKAP": 1.7,
    "BB": 5.3,
    "NSMAX": 2,
    "DT": 0.1,
    "NTSTEP": 10,
}
# Array params: these use the NAME[i] syntax required by tr_set_param.
TR_ARRAY_PARAMS = {
    "PN[1]": 1.0,
    "PN[2]": 1.0,
    "PT[1]": 1.5,
    "PT[2]": 1.5,
}
# Combined for coupling lookups (scalar params only, for compute_rjt_volint).
TR_PARAMS = TR_SCALAR_PARAMS

NTMAX_FP = 1
NTMAX_TR = 1


def _baseline():
    """Pattern X: hand-written coupling."""
    fp = Fplib()
    fp.set_params(**FP_PARAMS)
    fp.run(ntmax=NTMAX_FP)
    fp_state = fp.get_state()
    # Mirror what the COUPLING_RULES callable does inside run_pipeline:
    rjt_volint = compute_rjt_volint(
        fp_state, R0=TR_PARAMS["RR"], a=TR_PARAMS["RA"]
    )
    fp_scalars = _state_to_scalars(fp_state)   # adapter handles missing .scalars
    fp.close()

    tr = Trlib()
    tr.set_params(**TR_SCALAR_PARAMS)
    for name, val in TR_ARRAY_PARAMS.items():
        tr.set_param(name, val)
    tr.set_param("EXTERNAL_DRIVEN_I", rjt_volint * 1e-6)
    tr.run(ntmax=NTMAX_TR)
    tr_scalars = _state_to_scalars(tr.get_state())
    tr.close()
    return fp_scalars, tr_scalars


def _through_pipeline():
    """Pattern Y: run_pipeline."""
    pipe = TotPipeline()
    # fp params
    for k, v in FP_PARAMS.items():
        pipe.set_param(f"fp:{k}", v)
    # tr scalar params
    for k, v in TR_SCALAR_PARAMS.items():
        pipe.set_param(f"tr:{k}", v)
    # tr array params (bracket syntax passes through set_param verbatim)
    for k, v in TR_ARRAY_PARAMS.items():
        pipe.set_param(f"tr:{k}", v)
    result = pipe.run_pipeline([
        ("fp", {"ntmax": NTMAX_FP}),
        ("tr", {"ntmax": NTMAX_TR}),
    ])
    pipe.close()
    return (
        dict(result.last("fp").scalars),
        dict(result.last("tr").scalars),
        result,
    )


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-15)


def test_fp_tr_pipeline_equiv_scalars_match():
    fp_x, tr_x = _baseline()
    fp_y, tr_y, _ = _through_pipeline()
    mismatches = []
    for key in fp_x:
        if not _close(fp_x[key], fp_y[key]):
            mismatches.append(("fp", key, fp_x[key], fp_y[key]))
    for key in tr_x:
        if not _close(tr_x[key], tr_y[key]):
            mismatches.append(("tr", key, tr_x[key], tr_y[key]))
    assert not mismatches, (
        f"{len(mismatches)} scalar(s) deviate beyond 1e-10:\n"
        + "\n".join(f"  {mod}.{k}: baseline={a} pipeline={b}"
                    for mod, k, a, b in mismatches)
    )


def test_pipeline_records_coupling_doc():
    _, _, result = _through_pipeline()
    tr_step = result.last("tr")
    assert tr_step.coupling_applied, "coupling_applied is empty"
    assert any("RJT" in d or "driven current" in d.lower()
               for d in tr_step.coupling_applied), \
        f"expected RJT/driven current doc, got {tr_step.coupling_applied!r}"


def test_pipeline_active_drive_produces_nontrivial_current():
    """Sanity guard: the chosen fixture must trigger non-zero driven current,
    otherwise the equivalence test is vacuous (0 == 0 trivially)."""
    fp = Fplib()
    fp.set_params(**FP_PARAMS)
    fp.run(ntmax=NTMAX_FP)
    rjt_volint = compute_rjt_volint(
        fp.get_state(), R0=TR_PARAMS["RR"], a=TR_PARAMS["RA"]
    )
    fp.close()
    # R3 anchor: ≥ 1e-3 MA = 1e3 A. If your run produces less, the fixture
    # has lost potency — investigate before accepting an equivalence pass.
    assert abs(rjt_volint) >= 1.0e3, (
        f"compute_rjt_volint = {rjt_volint:.3e} A (= {rjt_volint*1e-6:.3e} MA). "
        "Active-drive fixture is supposed to produce ≥ 1e-3 MA per R3 outcome. "
        "The equivalence test would be vacuous at this magnitude — fix the fixture."
    )
