"""libeqapi is a .dll on Windows and needs its directory on the DLL search path."""
import os
import sys

import pytest

from eqlib import _ffi


def test_windows_candidates_are_dlls(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert [p.relative_to(_ffi._repo_root()).parts for p in _ffi._candidate_paths()] == [
        ("eq", "libeqapi.dll"),
        ("lib", "libeqapi.dll"),
    ]


def test_macos_and_linux_candidates_are_so(monkeypatch):
    for platform in ("darwin", "linux"):
        monkeypatch.setattr(sys, "platform", platform)
        assert [p.name for p in _ffi._candidate_paths()] == ["libeqapi.so", "libeqapi.so"]


def test_windows_registers_dll_directory_before_loading(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_ffi, "_DLL_DIR_HANDLES", {})
    monkeypatch.setattr(_ffi.os, "add_dll_directory",
                        lambda d: calls.append(("dir", d)) or object(), raising=False)

    class FakeCDLL:
        def __init__(self, path, mode=0):
            calls.append(("load", path))

    monkeypatch.setattr(_ffi.ctypes, "CDLL", FakeCDLL)
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib))
    assert calls == [("dir", str(tmp_path)), ("load", str(lib))]
    assert len(_ffi._DLL_DIR_HANDLES) == 1


def test_windows_registers_each_directory_once(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_ffi, "_DLL_DIR_HANDLES", {})
    monkeypatch.setattr(_ffi.os, "add_dll_directory",
                        lambda d: calls.append(("dir", d)) or object(), raising=False)

    class FakeCDLL:
        def __init__(self, path, mode=0):
            calls.append(("load", path))

    monkeypatch.setattr(_ffi.ctypes, "CDLL", FakeCDLL)
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib))
    _ffi.load_library(str(lib))
    assert [c for c in calls if c[0] == "dir"] == [("dir", str(tmp_path))]
    assert [c for c in calls if c[0] == "load"] == [("load", str(lib)), ("load", str(lib))]
    assert len(_ffi._DLL_DIR_HANDLES) == 1


def test_windows_relative_path_is_made_absolute(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_ffi, "_DLL_DIR_HANDLES", {})
    monkeypatch.setattr(_ffi.os, "add_dll_directory",
                        lambda d: calls.append(("dir", d)) or object(), raising=False)

    class FakeCDLL:
        def __init__(self, path, mode=0):
            calls.append(("load", path))

    monkeypatch.setattr(_ffi.ctypes, "CDLL", FakeCDLL)
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library("libeqapi.dll")
    assert calls[0] == ("dir", os.path.realpath(str(tmp_path)))
    assert calls[1] == ("load", os.path.join(os.path.realpath(str(tmp_path)), "libeqapi.dll"))


def test_windows_registrations_are_keyed_case_insensitively(monkeypatch, tmp_path):
    monkeypatch.setattr(_ffi.os.path, "normcase", str.lower)
    dir_upper = tmp_path / "D"
    dir_lower = tmp_path / "d"
    dir_upper.mkdir(exist_ok=True)
    dir_lower.mkdir(exist_ok=True)
    lib_upper = dir_upper / "libeqapi.dll"
    lib_lower = dir_lower / "libeqapi.dll"
    lib_upper.write_bytes(b"")
    lib_lower.write_bytes(b"")
    calls = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_ffi, "_DLL_DIR_HANDLES", {})
    monkeypatch.setattr(_ffi.os, "add_dll_directory",
                        lambda d: calls.append(("dir", d)) or object(), raising=False)

    class FakeCDLL:
        def __init__(self, path, mode=0):
            calls.append(("load", path))

    monkeypatch.setattr(_ffi.ctypes, "CDLL", FakeCDLL)
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib_upper))
    _ffi.load_library(str(lib_lower))
    assert [c for c in calls if c[0] == "dir"] == [("dir", str(dir_upper))]
    assert len(_ffi._DLL_DIR_HANDLES) == 1


def test_windows_missing_library_names_the_dll(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    missing = tmp_path / "libeqapi.dll"
    with pytest.raises(FileNotFoundError, match=r"^libeqapi\.dll not found"):
        _ffi.load_library(str(missing))


def test_non_windows_never_touches_dll_directory(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.so"
    lib.write_bytes(b"")

    def forbidden(_directory):
        raise AssertionError("os.add_dll_directory must not be called off Windows")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(_ffi.os, "add_dll_directory", forbidden, raising=False)
    monkeypatch.setattr(_ffi.ctypes, "CDLL", lambda path, mode=0: object())
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib))


def test_windows_missing_library_hint_names_the_dll(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    missing = tmp_path / "libeqapi.dll"
    with pytest.raises(FileNotFoundError) as info:
        _ffi.load_library(str(missing))
    message = str(info.value)
    assert message.endswith(
        "Build libeqapi.dll from the Fortran sources or set EQLIB_PATH."
    )
    assert "libeqapi.so" not in message


def test_non_windows_missing_library_message_is_unchanged(monkeypatch, tmp_path):
    for platform in ("linux", "darwin"):
        monkeypatch.setattr(sys, "platform", platform)
        missing = tmp_path / "libeqapi.so"
        tried = [str(x) for x in _ffi._candidate_paths()]
        with pytest.raises(FileNotFoundError) as info:
            _ffi.load_library(str(missing))
        assert str(info.value) == (
            f"libeqapi.so not found at {missing}. "
            f"Tried EQLIB_PATH and {tried}. "
            "Build it via `make -C eq libeqapi.so` or set EQLIB_PATH."
        )


class _DirHandle:
    """Stands in for what os.add_dll_directory returns."""

    def __init__(self, directory, events):
        self.directory = directory
        self.closed = False
        self._events = events

    def close(self):
        self.closed = True
        self._events.append(("close", self.directory))


def _fake_windows(monkeypatch, events, handles):
    def add_dll_directory(directory):
        handle = _DirHandle(directory, events)
        handles.append(handle)
        events.append(("dir", directory))
        return handle

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_ffi, "_DLL_DIR_HANDLES", {})
    monkeypatch.setattr(_ffi.os, "add_dll_directory", add_dll_directory, raising=False)


def _refusing_cdll(events):
    def cdll(path, mode=0):
        events.append(("load", path))
        raise OSError("[WinError 193] %1 is not a valid Win32 application")

    return cdll


def test_windows_failed_load_leaves_no_directory_registered(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    events, handles = [], []
    _fake_windows(monkeypatch, events, handles)
    monkeypatch.setattr(_ffi.ctypes, "CDLL", _refusing_cdll(events))
    with pytest.raises(OSError):
        _ffi.load_library(str(lib))
    assert events == [("dir", str(tmp_path)), ("load", str(lib)), ("close", str(tmp_path))]
    assert _ffi._DLL_DIR_HANDLES == {}

    # The next load of a good library registers the directory again and keeps it.
    monkeypatch.setattr(_ffi.ctypes, "CDLL", lambda path, mode=0: object())
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib))
    assert len(handles) == 2 and not handles[1].closed
    assert list(_ffi._DLL_DIR_HANDLES.values()) == [handles[1]]


def test_windows_library_without_the_api_leaves_no_directory_registered(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    events, handles = [], []
    _fake_windows(monkeypatch, events, handles)
    monkeypatch.setattr(_ffi.ctypes, "CDLL", lambda path, mode=0: object())

    def no_such_symbol(_handle):
        raise AttributeError("function 'eq_init' not found")

    monkeypatch.setattr(_ffi, "_apply_prototypes", no_such_symbol)
    with pytest.raises(AttributeError):
        _ffi.load_library(str(lib))
    assert handles[0].closed
    assert _ffi._DLL_DIR_HANDLES == {}


def test_windows_failed_load_keeps_an_earlier_registration(monkeypatch, tmp_path):
    lib = tmp_path / "libeqapi.dll"
    lib.write_bytes(b"")
    events, handles = [], []
    _fake_windows(monkeypatch, events, handles)
    monkeypatch.setattr(_ffi.ctypes, "CDLL", lambda path, mode=0: object())
    monkeypatch.setattr(_ffi, "_apply_prototypes", lambda handle: handle)
    _ffi.load_library(str(lib))
    monkeypatch.setattr(_ffi.ctypes, "CDLL", _refusing_cdll(events))
    with pytest.raises(OSError):
        _ffi.load_library(str(lib))
    assert len(handles) == 1 and not handles[0].closed
    assert list(_ffi._DLL_DIR_HANDLES.values()) == [handles[0]]
