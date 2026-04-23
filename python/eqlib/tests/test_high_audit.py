from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import eqlib.eqlib as eqlib_module  # noqa: E402
from eqlib import Eq, EqState  # noqa: E402
from eqlib import _ffi  # noqa: E402
from eqlib.errors import EqlibInvalidParamError, EqlibNotInitializedError  # noqa: E402


class FakeEqLib:
    def __init__(self) -> None:
        self.string_calls: list[tuple[bytes, bytes]] = []

    def eq_init(self) -> int:
        return 0

    def eq_finalize(self) -> int:
        return 0

    def eq_set_param(self, name, value) -> int:
        return 0

    def eq_set_param_str(self, name, value) -> int:
        self.string_calls.append((name, value))
        return 0


@pytest.fixture(autouse=True)
def reset_live_instance():
    Eq._live_instance = None
    yield
    Eq._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeEqLib:
    lib = FakeEqLib()
    monkeypatch.setattr(eqlib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    eq = Eq()
    with pytest.raises(EqlibNotInitializedError, match=r"another live Eq\(\)"):
        Eq()
    eq.close()

    reopened = Eq()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.EqStateC()
    c.nrgmax = _ffi.EQ_MAX_NRGM + 1
    with pytest.raises(EqlibNotInitializedError, match="nrgmax.*EQ_MAX_NRGM"):
        EqState.from_c(c)


@pytest.mark.parametrize("bad", ["bad\x00name", "é", "x" * 64])
def test_set_param_str_rejects_bad_name(fake_lib, bad):
    eq = Eq()
    try:
        with pytest.raises(EqlibInvalidParamError):
            eq.set_param_str(bad, "eqdata")
    finally:
        eq.close()


# Value buffer is CHARACTER(LEN=80) -> 80-byte Python limit; 81 fails.
@pytest.mark.parametrize("bad", ["bad\x00value", "é", "x" * 81])
def test_set_param_str_rejects_bad_value(fake_lib, bad):
    eq = Eq()
    try:
        with pytest.raises(EqlibInvalidParamError):
            eq.set_param_str("KNAMEQ", bad)
    finally:
        eq.close()


def test_set_param_str_accepts_normal_ascii(fake_lib):
    eq = Eq()
    try:
        eq.set_param_str("KNAMEQ", "eqdata")
    finally:
        eq.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", b"eqdata")]


def test_set_param_str_accepts_long_value(fake_lib):
    """Regression for the #148 review P2: value buffer is 80 bytes, so
    values of exactly 80 bytes must be accepted (they were rejected
    when the 63-byte name limit was applied to values too)."""
    long_value = "x" * 80
    eq = Eq()
    try:
        eq.set_param_str("KNAMEQ", long_value)
    finally:
        eq.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", long_value.encode())]
