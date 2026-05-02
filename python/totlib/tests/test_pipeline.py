"""Unit tests for TotPipeline — mock-based, no lib*.so required.

Lifecycle subset (Task 1.4): __init__, __enter__/__exit__, _ensure_module,
set_param, close. run_pipeline tests are added in Task 1.5.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from totlib.errors import (
    TotPipelineCouplingError,
    TotPipelineLifecycleError,
    TotPipelineUnknownModuleError,
)
from totlib.pipeline import TotPipeline


@pytest.fixture
def patch_wrappers(monkeypatch):
    """Replace _import_wrapper / _import_module_error with mocks.

    The returned dict allows tests to inspect which wrappers were
    requested, capture set_param/run/get_state calls, and inject errors.
    """
    fp_mock_class = MagicMock(name="FplibClass")
    tr_mock_class = MagicMock(name="TrlibClass")
    fp_err_class = type("FplibError", (Exception,), {})
    tr_err_class = type("TrlibError", (Exception,), {})

    classes = {"fp": fp_mock_class, "tr": tr_mock_class}
    err_classes = {"fp": fp_err_class, "tr": tr_err_class}

    def fake_import_wrapper(name):
        if name not in classes:
            raise TotPipelineUnknownModuleError(name)
        return classes[name]

    def fake_import_module_error(name):
        if name not in err_classes:
            raise TotPipelineUnknownModuleError(name)
        return err_classes[name]

    monkeypatch.setattr("totlib.pipeline._import_wrapper", fake_import_wrapper)
    monkeypatch.setattr("totlib.pipeline._import_module_error", fake_import_module_error)

    return {"classes": classes, "errors": err_classes}


def test_init_does_not_open_anything(patch_wrappers):
    pipe = TotPipeline()
    assert pipe._modules == {}
    assert pipe._params == {}
    assert pipe._closed is False
    # No wrapper class was instantiated
    patch_wrappers["classes"]["fp"].assert_not_called()
    patch_wrappers["classes"]["tr"].assert_not_called()


def test_set_param_lazy_opens_target_module_only(patch_wrappers):
    pipe = TotPipeline()
    pipe.set_param("fp:NSAMAX", 2)
    # fp is opened
    patch_wrappers["classes"]["fp"].assert_called_once()
    # tr is NOT opened
    patch_wrappers["classes"]["tr"].assert_not_called()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.set_param.assert_called_once_with("NSAMAX", 2.0)


def test_set_param_string_routes_to_set_param_str(patch_wrappers):
    pipe = TotPipeline()
    pipe.set_param("tr:KNAMEQ", "/path/to/eqdsk")
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    tr_inst.set_param_str.assert_called_once_with("KNAMEQ", "/path/to/eqdsk")
    tr_inst.set_param.assert_not_called()


def test_set_param_no_namespace_raises(patch_wrappers):
    pipe = TotPipeline()
    with pytest.raises(TotPipelineCouplingError, match="prefixed"):
        pipe.set_param("nokoron", 1.0)


def test_set_param_unknown_module_raises(patch_wrappers):
    pipe = TotPipeline()
    with pytest.raises(TotPipelineUnknownModuleError):
        pipe.set_param("xx:something", 1.0)


def test_set_param_records_into_params_dict(patch_wrappers):
    """set_param updates self._params after the wrapper accepts the value.

    Numeric values are stored as the same float the wrapper received, so
    coupling rules reading self._params see exactly what the underlying
    module saw. Strings are stored as-is via the set_param_str path.
    """
    pipe = TotPipeline()
    pipe.set_param("tr:RR", 6.2)
    pipe.set_param("tr:RA", 2.0)
    pipe.set_param("fp:NSAMAX", 2)                   # int input → 2.0 stored
    pipe.set_param("tr:KNAMEQ", "/path/to/eqdsk")    # string path
    assert pipe._params == {
        "tr:RR": 6.2,
        "tr:RA": 2.0,
        "fp:NSAMAX": 2.0,
        "tr:KNAMEQ": "/path/to/eqdsk",
    }


def test_set_param_rejects_bool(patch_wrappers):
    """bool inputs are explicitly rejected (Python's bool is a subclass of
    int, so silent float() coercion would mask intent — see Bugbot finding
    on PR #178)."""
    pipe = TotPipeline()
    with pytest.raises(TotPipelineCouplingError, match="bool"):
        pipe.set_param("fp:E0", True)
    # Sanity: integer paths still work.
    pipe.set_param("fp:NSAMAX", 2)
    assert pipe._params["fp:NSAMAX"] == 2.0


def test_set_param_string_to_module_without_set_param_str_raises(monkeypatch):
    """wr/wrx/ti wrappers don't expose set_param_str. Passing a string
    value to one of them must raise TotPipelineCouplingError, not a
    bare AttributeError. (Regression guard: real wrappers checked.)
    """
    # Build a fake wrapper class WITHOUT set_param_str
    fake_wrapper_class = MagicMock(name="WrxlibClass")
    fake_instance = MagicMock(spec=["set_param", "close"])  # no set_param_str
    fake_wrapper_class.return_value = fake_instance

    def fake_import_wrapper(name):
        if name == "wrx":
            return fake_wrapper_class
        raise TotPipelineUnknownModuleError(name)

    monkeypatch.setattr("totlib.pipeline._import_wrapper", fake_import_wrapper)
    pipe = TotPipeline()
    with pytest.raises(TotPipelineCouplingError, match="string parameters"):
        pipe.set_param("wrx:KFILE", "/path/to/something")


def test_close_finalizes_all_open_modules(patch_wrappers):
    pipe = TotPipeline()
    pipe.set_param("fp:A", 1.0)
    pipe.set_param("tr:B", 2.0)
    pipe.close()
    patch_wrappers["classes"]["fp"].return_value.close.assert_called_once()
    patch_wrappers["classes"]["tr"].return_value.close.assert_called_once()
    assert pipe._closed is True


def test_close_is_idempotent(patch_wrappers):
    pipe = TotPipeline()
    pipe.set_param("fp:A", 1.0)
    pipe.close()
    # Second close should not raise and should not re-call close()
    pipe.close()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.close.assert_called_once()


def test_close_finalizes_remaining_modules_on_error(patch_wrappers):
    pipe = TotPipeline()
    pipe.set_param("fp:A", 1.0)
    pipe.set_param("tr:B", 2.0)
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    fp_inst.close.side_effect = RuntimeError("fp boom")
    with pytest.raises(RuntimeError, match="fp boom"):
        pipe.close()
    # tr.close was still called despite fp.close raising
    tr_inst.close.assert_called_once()


def test_close_raises_exception_group_when_multiple_modules_fail(patch_wrappers):
    """When more than one module's close() raises, every error must surface
    via ExceptionGroup so cleanup failures are not silently dropped.

    Note: on Python 3.10 without the `exceptiongroup` backport, close()
    falls back to raising errors[0] only (same as pre-fix behavior).
    CI runs 3.11+ so ExceptionGroup is available here.
    """
    pipe = TotPipeline()
    pipe.set_param("fp:A", 1.0)
    pipe.set_param("tr:B", 2.0)
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    fp_inst.close.side_effect = RuntimeError("fp boom")
    tr_inst.close.side_effect = ValueError("tr boom")
    with pytest.raises(ExceptionGroup) as exc_info:
        pipe.close()
    raised = exc_info.value
    assert len(raised.exceptions) == 2
    assert any(isinstance(e, RuntimeError) and "fp boom" in str(e)
               for e in raised.exceptions)
    assert any(isinstance(e, ValueError) and "tr boom" in str(e)
               for e in raised.exceptions)


def test_set_param_after_close_raises_lifecycle(patch_wrappers):
    pipe = TotPipeline()
    pipe.close()
    with pytest.raises(TotPipelineLifecycleError):
        pipe.set_param("fp:A", 1.0)


def test_context_manager_closes_on_normal_exit(patch_wrappers):
    with TotPipeline() as pipe:
        pipe.set_param("fp:A", 1.0)
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.close.assert_called_once()


def test_context_manager_closes_on_exception(patch_wrappers):
    with pytest.raises(ValueError):
        with TotPipeline() as pipe:
            pipe.set_param("fp:A", 1.0)
            raise ValueError("inner")
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.close.assert_called_once()


# ============================================================
# run_pipeline behavior
# ============================================================

from totlib.errors import TotPipelineRunError


def _make_state(scalars):
    state = MagicMock()
    state.scalars = dict(scalars)
    return state


def test_run_pipeline_empty_steps_raises(patch_wrappers):
    pipe = TotPipeline()
    with pytest.raises(TotPipelineCouplingError, match="non-empty"):
        pipe.run_pipeline([])


def test_run_pipeline_unknown_module_raises(patch_wrappers):
    pipe = TotPipeline()
    with pytest.raises(TotPipelineUnknownModuleError):
        pipe.run_pipeline([("xx", {})])


def test_run_pipeline_bad_kwargs_raises(patch_wrappers):
    pipe = TotPipeline()
    with pytest.raises(TotPipelineCouplingError, match="kwargs"):
        pipe.run_pipeline([("fp", "not_a_dict")])


def test_run_pipeline_accepts_list_shaped_steps(patch_wrappers):
    """JSON-decoded payloads pass list-of-list to run_pipeline; the
    validator must accept those equivalent to tuples (regression
    guard for the MCP transport boundary)."""
    pipe = TotPipeline()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.get_state.return_value = _make_state({"foo": 1.0})
    # List-shape (what JSON deserialisation produces) instead of tuple-shape.
    result = pipe.run_pipeline([["fp", {"ntmax": 1}]])
    assert result.steps[0].module == "fp"
    assert result.steps[0].scalars == {"foo": 1.0}


def test_run_pipeline_calls_module_run_and_collects_state(patch_wrappers):
    pipe = TotPipeline()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    fp_inst.get_state.return_value = _make_state({"foo": 1.5})
    result = pipe.run_pipeline([("fp", {"ntmax": 5})])
    fp_inst.run.assert_called_once_with(ntmax=5)
    assert result.last("fp").scalars == {"foo": 1.5}
    assert result.last("fp").coupling_applied == []


def test_run_pipeline_applies_coupling_rule(patch_wrappers, monkeypatch):
    """Inject a known rule for ('fp','tr') and verify it propagates."""
    from totlib.pipeline import CouplingRule
    rules = {
        ("fp", "tr"): [
            CouplingRule(
                src_state_key="rjt_total",
                dst_param="PNBCD",
                transform=lambda v: v * 2.0,
                doc="test rule",
            ),
        ]
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    fp_inst.get_state.return_value = _make_state({"rjt_total": 5.0})
    tr_inst.get_state.return_value = _make_state({"AJT": 99.0})
    result = pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"ntmax": 1})])
    # tr.set_param was called with the transformed value
    tr_inst.set_param.assert_any_call("PNBCD", 10.0)
    assert "test rule" in result.last("tr").coupling_applied


def test_run_pipeline_missing_source_state_raises_coupling_error(
    patch_wrappers, monkeypatch
):
    from totlib.pipeline import CouplingRule
    rules = {
        ("fp", "tr"): [
            CouplingRule(src_state_key="missing_key", dst_param="X", doc="r"),
        ]
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    patch_wrappers["classes"]["fp"].return_value.get_state.return_value = (
        _make_state({"other_key": 1.0})
    )
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"ntmax": 1})])
    # Wrapped underlying cause is TotPipelineCouplingError
    assert isinstance(exc_info.value.__cause__, TotPipelineCouplingError)
    assert exc_info.value.failed_module == "tr"
    assert exc_info.value.failed_step_index == 1


def test_run_pipeline_partial_failure_carries_partial_result(
    patch_wrappers, monkeypatch
):
    """When step 2 raises, the error carries step 1's snapshot."""
    pipe = TotPipeline()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    fp_inst.get_state.return_value = _make_state({"foo": 7.0})
    tr_err_class = patch_wrappers["errors"]["tr"]
    tr_inst.run.side_effect = tr_err_class("tr boom")
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"ntmax": 1})])
    err = exc_info.value
    assert err.failed_step_index == 1
    assert err.failed_module == "tr"
    assert len(err.partial_result.steps) == 1
    assert err.partial_result.steps[0].module == "fp"
    assert err.partial_result.steps[0].scalars == {"foo": 7.0}
    # No coupling rule fired between fp (first step) and the failed tr step,
    # so the fp snapshot must record an empty applied list (regression guard
    # against silently dropping coupling metadata).
    assert err.partial_result.steps[0].coupling_applied == []


def test_run_pipeline_typeerror_from_bad_kwargs_is_wrapped(patch_wrappers):
    """If module.run(**kwargs) raises TypeError (e.g. unrecognized kwarg),
    the orchestrator must still wrap it as TotPipelineRunError so partial_result
    is preserved. Codex review caught that the previous narrow except-tuple
    let TypeError escape unwrapped."""
    pipe = TotPipeline()
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    # COUPLING_RULES[("fp","tr")] is now populated (Phase 2) — set the minimum
    # tr:RR/tr:RA so the rule's lambda doesn't KeyError before tr.run() is
    # reached. This test is about TypeError wrapping at the run() boundary,
    # not about coupling-rule validation.
    pipe.set_param("tr:RR", 6.2)
    pipe.set_param("tr:RA", 2.0)
    fp_state = _make_state({"foo": 1.0})
    fp_state.nrmax = 0   # compute_rjt_volint short-circuits at nr < 1 → 0.0
    fp_state.nsamax = 0
    fp_inst.get_state.return_value = fp_state
    tr_inst.run.side_effect = TypeError("unexpected kwarg 'unknown'")
    with pytest.raises(TotPipelineRunError) as exc_info:
        pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"unknown": 99})])
    err = exc_info.value
    assert err.failed_step_index == 1
    assert err.failed_module == "tr"
    assert isinstance(err.__cause__, TypeError)
    assert len(err.partial_result.steps) == 1
    assert err.partial_result.steps[0].module == "fp"


def test_run_pipeline_after_close_raises_lifecycle(patch_wrappers):
    pipe = TotPipeline()
    pipe.close()
    with pytest.raises(TotPipelineLifecycleError):
        pipe.run_pipeline([("fp", {})])


def test_run_pipeline_callable_rule_receives_params(patch_wrappers, monkeypatch):
    """Callable src_state_key gets (prev_state, self._params) — verifies
    cross-module context passing (e.g. fp's compute_rjt_volint reading tr's RR/RA).
    """
    from totlib.pipeline import CouplingRule
    captured = {}

    def callable_src(state, params):
        captured["state"] = state
        captured["params"] = dict(params)
        return state.scalars["raw"] * params["tr:RR"]

    rules = {
        ("fp", "tr"): [
            CouplingRule(
                src_state_key=callable_src,
                dst_param="EXTERNAL_DRIVEN_I",
                transform=lambda v: v * 1e-3,
                doc="callable rule with params",
            ),
        ]
    }
    monkeypatch.setattr("totlib.pipeline.COUPLING_RULES", rules)
    pipe = TotPipeline()
    pipe.set_param("tr:RR", 6.2)   # populates _params before pipeline runs
    fp_inst = patch_wrappers["classes"]["fp"].return_value
    tr_inst = patch_wrappers["classes"]["tr"].return_value
    fp_inst.get_state.return_value = _make_state({"raw": 100.0})
    tr_inst.get_state.return_value = _make_state({"AJT": 0.0})
    pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"ntmax": 1})])
    assert captured["params"]["tr:RR"] == 6.2
    # transform applied: 100 * 6.2 * 1e-3 = 0.62
    tr_inst.set_param.assert_any_call("EXTERNAL_DRIVEN_I", 0.62)


def test_state_to_scalars_with_scalars_dict():
    """_state_to_scalars returns a copy of state.scalars when present."""
    from totlib.pipeline import _state_to_scalars
    state = MagicMock()
    state.scalars = {"a": 1.0, "b": 2.0}
    out = _state_to_scalars(state)
    assert out == {"a": 1.0, "b": 2.0}
    # Must be a copy, not the same dict
    out["a"] = 99.0
    assert state.scalars["a"] == 1.0


def test_state_to_scalars_without_scalars_extracts_top_level():
    """_state_to_scalars extracts numeric top-level fields when .scalars absent."""
    from dataclasses import dataclass
    from totlib.pipeline import _state_to_scalars

    @dataclass
    class FakeState:
        nrmax: int = 10
        timefp: float = 0.5
        flag: bool = True              # excluded (bool)
        label: str = "abc"             # excluded (str)
        rjt: list = None               # excluded (not numeric)

    state = FakeState(rjt=[1.0, 2.0])
    out = _state_to_scalars(state)
    assert out == {"nrmax": 10.0, "timefp": 0.5}


def test_coupling_rules_has_fp_to_tr():
    from totlib.pipeline import COUPLING_RULES
    rules = COUPLING_RULES.get(("fp", "tr"), [])
    assert len(rules) == 1, f"expected exactly 1 rule, got {rules!r}"
    rule = rules[0]
    assert rule.dst_param == "EXTERNAL_DRIVEN_I"
    # src_state_key is a callable wrapper around compute_rjt_volint that pulls
    # tr:RR / tr:RA from the params dict.
    assert callable(rule.src_state_key)
    assert "RJT" in rule.doc or "driven current" in rule.doc.lower()


def test_coupling_rules_fp_tr_lambda_calls_compute_rjt_volint():
    """Pin the production fp→tr lambda's behaviour: signature is (state, params),
    it pulls tr:RR / tr:RA from params, and it routes to compute_rjt_volint.
    Uses the helper's nr<1 short-circuit so we don't need real RJT arrays."""
    from totlib.pipeline import COUPLING_RULES
    rule = COUPLING_RULES[("fp", "tr")][0]
    state = MagicMock()
    state.nrmax = 0   # triggers compute_rjt_volint's nr<1 → 0.0 short-circuit
    state.nsamax = 0
    out = rule.src_state_key(state, {"tr:RR": 6.2, "tr:RA": 2.0})
    assert out == 0.0
    # Transform: 0 A → 0 (sanity); the equivalence test (Task 2.3) covers the
    # non-zero path with real lib*.so.
    assert rule.transform(out) == 0.0


def test_coupling_rules_fp_tr_lambda_raises_when_tr_RR_missing(patch_wrappers):
    """If the user forgets pipe.set_param("tr:RR", …), the rule must surface
    a TotPipelineCouplingError whose message names tr:RR (not the lambda repr).
    Regression guard for the _extract_source error-routing fix."""
    pipe = TotPipeline()
    fp_state = _make_state({"foo": 1.0})
    fp_state.nrmax = 0
    fp_state.nsamax = 0
    patch_wrappers["classes"]["fp"].return_value.get_state.return_value = fp_state
    with pytest.raises(TotPipelineRunError) as ei:
        pipe.run_pipeline([("fp", {"ntmax": 1}), ("tr", {"ntmax": 1})])
    assert isinstance(ei.value.__cause__, TotPipelineCouplingError)
    assert "tr:RR" in str(ei.value.__cause__), (
        f"expected 'tr:RR' in error message, got: {ei.value.__cause__!r}"
    )
