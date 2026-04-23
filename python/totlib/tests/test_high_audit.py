from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import totlib.totlib as totlib_module  # noqa: E402
from totlib import Tot, TotState  # noqa: E402
from totlib import _ffi  # noqa: E402
from totlib.errors import TotlibInvalidParamError, TotlibNotInitializedError  # noqa: E402


class FakeTotLib:
    def __init__(self) -> None:
        self.string_calls: list[tuple[bytes, bytes]] = []

    def tot_init(self) -> int:
        return _ffi.TOT_OK

    def tot_finalize(self) -> int:
        return _ffi.TOT_OK

    def tot_set_param(self, name, value) -> int:
        return _ffi.TOT_OK

    def tot_set_param_str(self, name, value) -> int:
        self.string_calls.append((name, value))
        return _ffi.TOT_OK


@pytest.fixture(autouse=True)
def reset_live_instance():
    Tot._live_instance = None
    yield
    Tot._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeTotLib:
    lib = FakeTotLib()
    monkeypatch.setattr(totlib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    tot = Tot()
    with pytest.raises(TotlibNotInitializedError, match=r"another live Tot\(\)"):
        Tot()
    tot.close()

    reopened = Tot()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.TotStateC()
    c.nrmax = _ffi.TOT_MAX_NRMAX + 1
    with pytest.raises(TotlibNotInitializedError, match="nrmax.*TOT_MAX_NRMAX"):
        TotState.from_c(c)


@pytest.mark.parametrize("bad", ["bad\x00name", "é", "x" * 64])
def test_set_param_str_rejects_bad_name(fake_lib, bad):
    tot = Tot()
    try:
        with pytest.raises(TotlibInvalidParamError):
            tot.set_param_str(bad, "eqdata")
    finally:
        tot.close()


# Value buffer is CHARACTER(LEN=256) -> 256-byte Python limit; 257 fails.
@pytest.mark.parametrize("bad", ["bad\x00value", "é", "x" * 257])
def test_set_param_str_rejects_bad_value(fake_lib, bad):
    tot = Tot()
    try:
        with pytest.raises(TotlibInvalidParamError):
            tot.set_param_str("eq:KNAMEQ", bad)
    finally:
        tot.close()


def test_set_param_str_accepts_normal_ascii(fake_lib):
    tot = Tot()
    try:
        tot.set_param_str("eq:KNAMEQ", "eqdata")
    finally:
        tot.close()
    assert fake_lib.string_calls == [(b"eq:KNAMEQ", b"eqdata")]


def test_set_param_str_accepts_long_value(fake_lib):
    """Regression for #148 review P2: value buffer is 256 bytes;
    values of exactly 256 bytes must be accepted (KNAMEQ paths etc.)."""
    long_value = "x" * 256
    tot = Tot()
    try:
        tot.set_param_str("eq:KNAMEQ", long_value)
    finally:
        tot.close()
    assert fake_lib.string_calls == [(b"eq:KNAMEQ", long_value.encode())]
