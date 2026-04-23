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


@pytest.mark.parametrize("bad", ["bad\x00name", "é", "x" * 64])
def test_set_param_str_rejects_bad_name(fake_lib, bad):
    fp = Fplib()
    try:
        with pytest.raises(FplibInvalidParamError):
            fp.set_param_str(bad, "eqdata")
    finally:
        fp.close()


# Value buffer is CHARACTER(LEN=128) -> 128-byte Python limit; 129 fails.
@pytest.mark.parametrize("bad", ["bad\x00value", "é", "x" * 129])
def test_set_param_str_rejects_bad_value(fake_lib, bad):
    fp = Fplib()
    try:
        with pytest.raises(FplibInvalidParamError):
            fp.set_param_str("KNAMEQ", bad)
    finally:
        fp.close()


def test_set_param_str_accepts_normal_ascii(fake_lib):
    fp = Fplib()
    try:
        fp.set_param_str("KNAMEQ", "eqdata")
    finally:
        fp.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", b"eqdata")]


def test_set_param_str_accepts_long_value(fake_lib):
    """Regression for #148 review P2: value buffer is 128 bytes;
    values of exactly 128 bytes must be accepted."""
    long_value = "x" * 128
    fp = Fplib()
    try:
        fp.set_param_str("KNAMEQ", long_value)
    finally:
        fp.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", long_value.encode())]
