from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[2]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import wrlib.wrlib as wrlib_module  # noqa: E402
from wrlib import WrState, Wrlib  # noqa: E402
from wrlib import _ffi  # noqa: E402
from wrlib.errors import WrlibStateError  # noqa: E402


class FakeWrLib:
    def wr_init(self) -> int:
        return 0

    def wr_finalize(self) -> int:
        return 0


@pytest.fixture(autouse=True)
def reset_live_instance():
    Wrlib._live_instance = None
    yield
    Wrlib._live_instance = None


@pytest.fixture
def fake_lib(monkeypatch) -> FakeWrLib:
    lib = FakeWrLib()
    monkeypatch.setattr(wrlib_module._ffi, "load_library", lambda lib_path=None: lib)
    return lib


def test_double_construction_raises_and_close_reopens(fake_lib):
    wr = Wrlib()
    with pytest.raises(WrlibStateError, match=r"another live Wrlib\(\)"):
        Wrlib()
    wr.close()

    reopened = Wrlib()
    reopened.close()


def test_from_c_oversized_dimension_raises():
    c = _ffi.WrStateC()
    c.nraymax = _ffi.WR_MAX_NRAYMAX + 1
    with pytest.raises(WrlibStateError, match="nraymax.*WR_MAX_NRAYMAX"):
        WrState.from_c(c)
