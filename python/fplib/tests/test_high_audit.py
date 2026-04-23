from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import fplib.fplib as fplib_module  # noqa: E402
from fplib import FpState, Fplib  # noqa: E402
from fplib import _ffi  # noqa: E402
from fplib.errors import FplibInvalidParamError, FplibNotInitError  # noqa: E402


class FakeFpLib:
    def __init__(self) -> None:
        self.string_calls: list[tuple[bytes, bytes]] = []

    def fp_init(self) -> int:
        return 0

    def fp_finalize(self) -> int:
        return 0

    def fp_set_param(self, name, value) -> int:
        return 0

    def fp_set_param_str(self, name, value) -> int:
        self.string_calls.append((name, value))
        return 0


@pytest.fixture(autouse=True)
def reset_live_instance():
    Fplib._live_instance = None
    yield
    Fplib._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeFpLib:
    lib = FakeFpLib()
    monkeypatch.setattr(fplib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    fp = Fplib()
    with pytest.raises(FplibNotInitError, match=r"another live Fplib\(\)"):
        Fplib()
    fp.close()

    reopened = Fplib()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.FpStateC()
    c.nrmax = _ffi.FP_MAX_NRMAX + 1
    with pytest.raises(FplibNotInitError, match="nrmax.*FP_MAX_NRMAX"):
        FpState.from_c(c)


@pytest.mark.parametrize("bad", ["bad\x00name", "x" * 64, "é"])
@pytest.mark.parametrize("field", ["name", "value"])
def test_set_param_str_rejects_bad_c_strings(fake_lib, field, bad):
    fp = Fplib()
    try:
        name = bad if field == "name" else "KNAMEQ"
        value = bad if field == "value" else "eqdata"
        with pytest.raises(FplibInvalidParamError):
            fp.set_param_str(name, value)
    finally:
        fp.close()


def test_set_param_str_accepts_normal_ascii(fake_lib):
    fp = Fplib()
    try:
        fp.set_param_str("KNAMEQ", "eqdata")
    finally:
        fp.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", b"eqdata")]
