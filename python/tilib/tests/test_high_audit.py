from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import tilib.tilib as tilib_module  # noqa: E402
from tilib import TiLib, TiState  # noqa: E402
from tilib import _ffi  # noqa: E402
from tilib.errors import TilibParamError, TilibStateError  # noqa: E402


class FakeTiLib:
    def ti_init(self) -> int:
        return 0

    def ti_finalize(self) -> int:
        return 0

    def ti_set_param(self, name, value) -> int:
        return 0


@pytest.fixture(autouse=True)
def reset_live_instance():
    TiLib._live_instance = None
    yield
    TiLib._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeTiLib:
    lib = FakeTiLib()
    monkeypatch.setattr(tilib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    ti = TiLib()
    with pytest.raises(TilibStateError, match=r"another live TiLib\(\)"):
        TiLib()
    ti.close()

    reopened = TiLib()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.TiStateC()
    c.nrmax = _ffi.TI_MAX_NRMAX + 1
    with pytest.raises(TilibStateError, match="nrmax.*TI_MAX_NRMAX"):
        TiState.from_c(c)


# Issue #148 review H-1: set_param name must go through _encode_name
# even though tilib has no set_param_str.
@pytest.mark.parametrize("bad", ["bad\x00name", "é", "x" * 64])
def test_set_param_rejects_bad_c_strings(fake_lib, bad):
    ti = TiLib()
    try:
        with pytest.raises(TilibParamError):
            ti.set_param(bad, 1.0)
    finally:
        ti.close()


def test_set_param_accepts_normal_ascii(fake_lib):
    ti = TiLib()
    try:
        ti.set_param("RR", 6.2)
    finally:
        ti.close()
