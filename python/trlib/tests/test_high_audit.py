from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import trlib.trlib as trlib_module  # noqa: E402
from trlib import TrState, Trlib  # noqa: E402
from trlib import _ffi  # noqa: E402
from trlib.errors import TrlibParamError, TrlibStateError  # noqa: E402


class FakeTrLib:
    def __init__(self) -> None:
        self.string_calls: list[tuple[bytes, bytes]] = []

    def tr_init(self) -> int:
        return 0

    def tr_finalize(self) -> int:
        return 0

    def tr_set_param(self, name, value) -> int:
        return 0

    def tr_set_param_str(self, name, value) -> int:
        self.string_calls.append((name, value))
        return 0


@pytest.fixture(autouse=True)
def reset_live_instance():
    Trlib._live_instance = None
    yield
    Trlib._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeTrLib:
    lib = FakeTrLib()
    monkeypatch.setattr(trlib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    tr = Trlib()
    with pytest.raises(TrlibStateError, match=r"another live Trlib\(\)"):
        Trlib()
    tr.close()

    reopened = Trlib()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.TrStateC()
    c.nrmax = _ffi.TR_MAX_NRMAX + 1
    with pytest.raises(TrlibStateError, match="nrmax.*TR_MAX_NRMAX"):
        TrState.from_c(c)


@pytest.mark.parametrize("bad", ["bad\x00name", "x" * 64, "é"])
@pytest.mark.parametrize("field", ["name", "value"])
def test_set_param_str_rejects_bad_c_strings(fake_lib, field, bad):
    tr = Trlib()
    try:
        name = bad if field == "name" else "KNAMEQ"
        value = bad if field == "value" else "eqdata"
        with pytest.raises(TrlibParamError):
            tr.set_param_str(name, value)
    finally:
        tr.close()


def test_set_param_str_accepts_normal_ascii(fake_lib):
    tr = Trlib()
    try:
        tr.set_param_str("KNAMEQ", "eqdata")
    finally:
        tr.close()
    assert fake_lib.string_calls == [(b"KNAMEQ", b"eqdata")]
