"""L-7b-ii: verify-rule dispatch tests for TotPipeline.

Six mock-based cases covering:

  A-1: verify True -> rule recorded in coupling_applied
  A-2: verify False -> TotPipelineRunError raised, applied unchanged
  A-3: verify raises -> TotPipelineRunError, 3-level __cause__ chain
  A-4: mixed transfer+verify rules in one pair fire in declaration order
  A-5: __post_init__ validation rejects misconstructed rules
  A-6: unregistered pair -> silent skip, coupling_applied == []

No `.so` required; uses the existing patch_wrappers + monkeypatch
COUPLING_RULES pattern from test_pipeline.py.

Spec: docs/superpowers/specs/2026-05-03-l7b-ii-bpsd-broker-coupling-design.md
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from totlib.errors import (
    TotPipelineCouplingError,
    TotPipelineRunError,
    TotPipelineUnknownModuleError,
)
from totlib.pipeline import CouplingRule, TotPipeline


def _make_state(scalars):
    """Build a minimal mock state object with .scalars dict."""
    s = MagicMock()
    s.scalars = dict(scalars)
    return s


@pytest.fixture
def patch_wrappers(monkeypatch):
    """Patch _import_wrapper / _import_module_error to return MagicMock
    classes so no real .so is loaded. Mirrors test_pipeline.py:21."""
    classes = {}
    err_classes = {}
    for name in ("eq", "tr", "fp", "wr"):
        cls = MagicMock(name=f"{name}_class")
        inst = MagicMock(name=f"{name}_inst")
        inst.get_state.return_value = _make_state({})
        cls.return_value = inst
        classes[name] = cls
        err_classes[name] = type(f"{name}libError", (Exception,), {})

    def fake_import_wrapper(name):
        if name not in classes:
            raise TotPipelineUnknownModuleError(name)
        return classes[name]

    def fake_import_module_error(name):
        if name not in err_classes:
            raise TotPipelineUnknownModuleError(name)
        return err_classes[name]

    monkeypatch.setattr("totlib.pipeline._import_wrapper", fake_import_wrapper)
    monkeypatch.setattr(
        "totlib.pipeline._import_module_error", fake_import_module_error
    )
    return {"classes": classes, "errors": err_classes}


# --- A-1: verify True -> applied recorded ----------------------------

def test_verify_true_records_rule_in_applied(patch_wrappers, monkeypatch):
    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="verify",
                verify=lambda inst: True,
                doc="A-1 happy path",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    result = pipe.run_pipeline([("eq", {}), ("tr", {})])
    tr_step = result.last("tr")
    assert tr_step.coupling_applied == ["A-1 happy path"]


# --- A-2: verify False -> RunError(__cause__=CouplingError) ----------

def test_verify_false_raises_run_error_with_coupling_cause(
    patch_wrappers, monkeypatch
):
    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="verify",
                verify=lambda inst: False,
                doc="A-2 false-return",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("eq", {}), ("tr", {})])
    assert isinstance(exc_info.value.__cause__, TotPipelineCouplingError)
    assert "returned False" in str(exc_info.value.__cause__)
    # eq step completed; tr step did not.
    assert exc_info.value.failed_module == "tr"
    eq_step_applied = exc_info.value.partial_result.last("eq").coupling_applied
    # No verify-rule entry should appear in either step's applied list.
    assert "A-2 false-return" not in eq_step_applied


# --- A-3: verify raises -> RunError(__cause__=CouplingError(__cause__=Original))

def test_verify_raise_preserves_three_level_chain(
    patch_wrappers, monkeypatch
):
    class CustomError(Exception):
        pass

    def boom(inst):
        raise CustomError("verify boom")

    rules = {
        ("eq", "tr"): [
            CouplingRule(kind="verify", verify=boom, doc="A-3 raise"),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("eq", {}), ("tr", {})])

    coupling_err = exc_info.value.__cause__
    assert isinstance(coupling_err, TotPipelineCouplingError)
    original = coupling_err.__cause__
    assert isinstance(original, CustomError)
    assert "verify boom" in str(original)


# --- A-4: mixed transfer + verify fire in declaration order ----------

def test_mixed_transfer_then_verify_fires_in_order(
    patch_wrappers, monkeypatch
):
    fired = []

    rules = {
        ("eq", "tr"): [
            CouplingRule(
                kind="transfer",
                src_state_key=lambda state, params: 1.0,
                dst_param="MOCK_PARAM",
                transform=lambda v: (fired.append("transfer"), v)[1],
                doc="A-4 transfer first",
            ),
            CouplingRule(
                kind="verify",
                verify=lambda inst: (fired.append("verify"), True)[1],
                doc="A-4 verify second",
            ),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    pipe.run_pipeline([("eq", {}), ("tr", {})])
    assert fired == ["transfer", "verify"]


# --- A-5: __post_init__ validation -----------------------------------

def test_post_init_rejects_transfer_missing_fields():
    with pytest.raises(ValueError, match="src_state_key"):
        CouplingRule(dst_param="X", transform=lambda v: v)


def test_post_init_rejects_verify_missing_callable():
    with pytest.raises(ValueError, match="verify"):
        CouplingRule(kind="verify")


def test_post_init_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown CouplingRule.kind"):
        CouplingRule(kind="bogus")


# --- A-6: unregistered pair -> silent skip ---------------------------

def test_unregistered_pair_silent_skip(patch_wrappers, monkeypatch):
    rules = {
        ("eq", "tr"): [
            CouplingRule(kind="verify", verify=lambda i: True, doc="dummy"),
        ],
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    # Pipeline ("eq", "wr") -- no rule registered for that pair.
    result = pipe.run_pipeline([("eq", {}), ("wr", {})])
    wr_step = result.last("wr")
    assert wr_step.coupling_applied == []
