"""Unit tests for pipeline.py data classes."""
import pytest
from totlib.pipeline import CouplingRule, PipelineStep, PipelineResult


def test_coupling_rule_defaults():
    # L-7b-ii: transform は kind="transfer" で必須になったため、
    # ここでも明示的に渡す。doc / kind の既定値が変わっていない
    # ことだけを確認する。
    r = CouplingRule(src_state_key="x", dst_param="Y", transform=lambda v: v)
    assert r.doc == ""
    assert r.kind == "transfer"


def test_coupling_rule_with_transform():
    r = CouplingRule(
        src_state_key="x",
        dst_param="Y",
        transform=lambda v: v * 2,
        doc="double it",
    )
    assert r.transform(2.0) == 4.0
    assert r.doc == "double it"


def test_pipeline_step_holds_scalars_and_coupling():
    s = PipelineStep(module="fp", scalars={"a": 1.0}, coupling_applied=["doc1"])
    assert s.module == "fp"
    assert s.scalars == {"a": 1.0}
    assert s.coupling_applied == ["doc1"]


def test_pipeline_result_last():
    s1 = PipelineStep("fp", {"a": 1.0}, [])
    s2 = PipelineStep("tr", {"b": 2.0}, ["fp->tr"])
    r = PipelineResult(steps=[s1, s2])
    assert r.last("fp") is s1
    assert r.last("tr") is s2


def test_pipeline_result_last_returns_most_recent_for_repeated_module():
    """When the same module appears twice, last() returns the latest step."""
    s1 = PipelineStep("fp", {"a": 1.0}, [])
    s2 = PipelineStep("tr", {"b": 2.0}, [])
    s3 = PipelineStep("fp", {"a": 99.0}, [])
    r = PipelineResult(steps=[s1, s2, s3])
    assert r.last("fp") is s3


def test_pipeline_result_last_raises_keyerror():
    r = PipelineResult(steps=[PipelineStep("fp", {}, [])])
    with pytest.raises(KeyError):
        r.last("nope")


def test_pipeline_result_to_dict_flattens():
    r = PipelineResult(steps=[
        PipelineStep("fp", {"a": 1.0}, []),
        PipelineStep("tr", {"b": 2.0}, ["fp RJT -> tr PNBCD"]),
    ])
    d = r.to_dict()
    assert d["fp"] == {"a": 1.0}
    assert d["tr"] == {"b": 2.0}
    assert "_steps" in d
    assert len(d["_steps"]) == 2
    assert d["_steps"][1]["coupling_applied"] == ["fp RJT -> tr PNBCD"]


def test_to_dict_returns_defensive_copies():
    """Mutation of the returned dict must not perturb the originating PipelineStep."""
    step1 = PipelineStep("fp", {"foo": 1.0}, [])
    step2 = PipelineStep("tr", {"bar": 2.0}, ["fp -> tr"])
    result = PipelineResult(steps=[step1, step2])
    out = result.to_dict()

    # Mutate every payload returned by to_dict.
    out["fp"]["foo"] = 999.0
    out["tr"]["bar"] = 888.0
    out["_steps"][1]["scalars"]["bar"] = 777.0
    out["_steps"][1]["coupling_applied"].append("manipulated")

    # Originating PipelineStep instances must be untouched.
    assert step1.scalars == {"foo": 1.0}
    assert step2.scalars == {"bar": 2.0}
    assert step2.coupling_applied == ["fp -> tr"]
