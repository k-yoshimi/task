"""MONO_LIB_PATH on Windows: the probe and the loaders get an absolute path."""
import os
import sys

import pytest

import _runtime_mode


class _IsMono:
    restype = None
    argtypes = None

    def __call__(self):
        return 1


class _FakeMonoImage:
    def __init__(self):
        self.tot_is_mono = _IsMono()


@pytest.fixture(autouse=True)
def _fresh_cache():
    _runtime_mode.mono_lib_path.cache_clear()
    yield
    _runtime_mode.mono_lib_path.cache_clear()


def _record_loads(monkeypatch):
    loaded = []

    def cdll(path, mode=0):
        loaded.append(path)
        return _FakeMonoImage()

    monkeypatch.setattr(_runtime_mode.ctypes, "CDLL", cdll)
    return loaded


def test_windows_relative_mono_path_is_probed_and_returned_absolute(monkeypatch, tmp_path):
    # A bare name passes Path.exists() from the working directory, where
    # Windows' DLL search does not look.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "libtotapi_mono.dll").write_bytes(b"")
    loaded = _record_loads(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("MONO_LIB_PATH", "libtotapi_mono.dll")
    found = _runtime_mode.mono_lib_path()
    expected = os.path.join(os.path.realpath(str(tmp_path)), "libtotapi_mono.dll")
    assert loaded == [expected]
    assert str(found) == expected


def test_windows_absolute_mono_path_is_kept(monkeypatch, tmp_path):
    lib = tmp_path / "libtotapi_mono.dll"
    lib.write_bytes(b"")
    loaded = _record_loads(monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("MONO_LIB_PATH", str(lib))
    assert str(_runtime_mode.mono_lib_path()) == str(lib)
    assert loaded == [str(lib)]


def test_non_windows_mono_path_is_used_as_given(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "libtotapi_mono.so").write_bytes(b"")
    for platform in ("linux", "darwin"):
        _runtime_mode.mono_lib_path.cache_clear()
        loaded = _record_loads(monkeypatch)
        monkeypatch.setattr(sys, "platform", platform)
        monkeypatch.setenv("MONO_LIB_PATH", "libtotapi_mono.so")
        assert str(_runtime_mode.mono_lib_path()) == "libtotapi_mono.so"
        assert loaded == ["libtotapi_mono.so"]
