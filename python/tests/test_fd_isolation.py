"""The module the stdio servers share for their fd isolation
(``python/_fd_isolation.py``).

Here: what belongs to the module and to the process, not to one server. The
checks every server has to pass are in
``python/mcp-servers/fd_isolation_cases.py`` and are run from each server's
own ``tests/test_fd_isolation.py``.

Every check runs in a fresh interpreter: the redirect is process-global, and
in the test process it would take pytest's own capture of fd 1 with it.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

MCP_ROOT = Path(__file__).resolve().parents[1] / "mcp-servers"   # <repo>/python/mcp-servers
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

pytest.register_assert_rewrite("fd_isolation_cases")
import fd_isolation_cases as cases  # noqa: E402
from fd_isolation_cases import run  # noqa: E402

SERVERS = ("eq_mcp", "tr_mcp", "tot_mcp", "ti_mcp", "wr_mcp", "wrx_mcp", "fp_mcp")


# ----- every server runs every shared check -----

@pytest.mark.parametrize("server", SERVERS)
def test_the_server_s_own_test_file_calls_every_shared_case(server):
    # The cases are plain functions: one that a server's file forgets to call
    # is a check that silently does not run for that server.
    shared = [name for name, value in vars(cases).items()
              if callable(value) and getattr(value, "__module__", None) == cases.__name__
              and not name.startswith("_") and name not in ("env", "run")]
    assert len(shared) == 6, shared
    source = (MCP_ROOT / server / "tests" / "test_fd_isolation.py").read_text()
    assert f'SERVER = "{server}"' in source
    missing = [name for name in shared if f"cases.{name}(SERVER" not in source]
    assert not missing, missing


# ----- one flag for the process -----

def test_installing_twice_keeps_sys_stdout_on_the_pipe():
    # A second dup(1) would save the already-redirected stderr as "the pipe".
    out = run("""
        import os, sys
        import _fd_isolation
        _fd_isolation.install()
        _fd_isolation.install()
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """)
    assert "JSONRPC-MARKER" in out.stdout and "JSONRPC-MARKER" not in out.stderr
    assert "FORTRAN-MARKER" in out.stderr and "FORTRAN-MARKER" not in out.stdout


def test_two_servers_started_in_one_process_share_the_installation():
    # tot_mcp imports tr_mcp for its registry; here both main() functions run.
    out = run("import os, sys\nimport tot_mcp.server as tot\nimport tr_mcp.server as tr\n"
              + cases.STUB_SERVER + """
_stub(tot); _stub(tr)
assert tot._fd_isolation is tr._fd_isolation
assert tot.main([]) == 0
assert tr.main([]) == 0
""")
    assert out.stdout.count("JSONRPC-MARKER") == 2 and "JSONRPC-MARKER" not in out.stderr
    assert out.stderr.count("FORTRAN-MARKER") == 2 and "FORTRAN-MARKER" not in out.stdout


# ----- a failure changes nothing -----

_FAILING = {
    # the stream on the saved descriptor cannot be built
    "fdopen": """
        real = iso.os.fdopen
        def failing(*a, **k):
            raise OSError("no stream today")
        iso.os.fdopen = failing
        def restore(): iso.os.fdopen = real
    """,
    # the redirect itself is refused
    "dup2": """
        real = iso.os.dup2
        def failing(src, dst, *a, **k):
            if dst == 1:
                raise OSError("no redirect today")
            return real(src, dst, *a, **k)
        iso.os.dup2 = failing
        def restore(): iso.os.dup2 = real
    """,
}


@pytest.mark.parametrize("step", sorted(_FAILING))
def test_a_failure_up_to_the_redirect_leaves_everything_as_it_was(step):
    out = run("""
        import os, sys
        import _fd_isolation as iso

        def lowest_free():
            fd = os.dup(0); os.close(fd); return fd

        before = os.fstat(1); stdout = sys.stdout; free = lowest_free()
""" + _FAILING[step] + """
        try:
            iso.install()
        except OSError:
            print("raised")
        restore()
        after = os.fstat(1)
        print("installed", iso.installed())
        print("fd1_same", (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino))
        print("stdout_same", stdout is sys.stdout)
        print("no_leak", lowest_free() == free)
        sys.stdout.flush()
        iso.install()                      # and a later call does the work
        sys.stdout.write(" JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """)
    assert out.stdout.split() == ["raised", "installed", "False", "fd1_same", "True",
                                  "stdout_same", "True", "no_leak", "True", "JSONRPC-MARKER"]
    assert "FORTRAN-MARKER" in out.stderr


def test_a_stream_that_owns_fd1_is_not_closed_under_the_redirect():
    # A host that replaced sys.stdout by a stream of its own on fd 1: dropping
    # the last reference to it would close the redirected descriptor.
    out = run("""
        import gc, os, sys
        import _fd_isolation
        sys.stdout = os.fdopen(1, "w", buffering=1)
        _fd_isolation.install()
        gc.collect()
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")       # EBADF if fd 1 went with the old stream
    """)
    assert "JSONRPC-MARKER" in out.stdout and "FORTRAN-MARKER" not in out.stdout
    assert "FORTRAN-MARKER" in out.stderr


# ----- what counts as the same file -----

def test_descriptors_without_an_identity_are_not_taken_for_the_same_file():
    # Windows reports st_dev = st_ino = 0 for a pipe. Two such pipes are two
    # files: the library's output goes to stderr, as it does everywhere else.
    out = run("""
        import os, sys, types
        import _fd_isolation as iso
        real_fstat = os.fstat
        asked = []
        def no_identity(fd):
            asked.append(fd)
            st = real_fstat(fd)
            return types.SimpleNamespace(st_dev=0, st_ino=0, st_mode=st.st_mode)
        iso.os.fstat = no_identity
        iso.install()
        iso.os.fstat = real_fstat
        sys.stdout.write("JSONRPC-MARKER compared=%s" % (1 in asked and 2 in asked))
        sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """)
    # "compared": the patched fstat is what the comparison went through
    assert out.stdout == "JSONRPC-MARKER compared=True"
    assert "FORTRAN-MARKER" in out.stderr
    assert "are the same file" not in out.stderr


@pytest.mark.skipif(sys.platform == "win32",
                    reason="fstat gives a pipe no identity there: a merged stream is not recognised")
def test_the_null_device_opened_for_a_merged_stream_is_closed_again():
    # fd 1 holds the null device after the redirect; the descriptor it was
    # opened on is not left behind.
    out = run("""
        import os, sys
        import _fd_isolation

        def in_use():
            n = 0
            for fd in range(64):
                try:
                    os.fstat(fd); n += 1
                except OSError:
                    pass
            return n

        before = in_use()
        _fd_isolation.install()
        sys.stdout.write("JSONRPC-MARKER more_in_use=%d" % (in_use() - before))   # the saved pipe
        sys.stdout.flush()
    """, stderr=subprocess.STDOUT)
    assert "are the same file" in out.stdout
    assert out.stdout.endswith("JSONRPC-MARKER more_in_use=1")


def test_an_fd2_that_cannot_be_looked_at_is_not_replaced():
    # fstat(2) failing for another reason than EBADF: fd 2 is there, so the
    # null device must not be put on it. The installation fails before it
    # changes anything.
    out = run("""
        import errno, os, sys
        import _fd_isolation as iso
        real = iso.os.fstat
        before = real(2)
        def failing(fd):
            if fd == 2:
                raise OSError(errno.EIO, "no fstat today")
            return real(fd)
        iso.os.fstat = failing
        try:
            iso.install()
            outcome = "installed"
        except OSError as exc:
            outcome = "raised " + errno.errorcode[exc.errno]
        iso.os.fstat = real
        after = real(2)
        sys.stdout.write("%s same_fd2=%s installed=%s" % (
            outcome, (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino),
            iso.installed()))
        sys.stdout.flush()
    """)
    assert out.stdout == "raised EIO same_fd2=True installed=False"


def test_a_stdout_whose_flush_fails_does_not_stop_the_installation():
    # A host's stream of its own: what it held is lost either way, and the
    # server still needs fd 1 off the pipe.
    out = run("""
        import io, os, sys
        import _fd_isolation
        class Broken(io.TextIOBase):
            def flush(self):
                raise RuntimeError("no flush today")
        sys.stdout = Broken()
        _fd_isolation.install()
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """)
    assert out.stdout == "JSONRPC-MARKER"
    assert "FORTRAN-MARKER" in out.stderr


# ----- fd 2 closed -----

@pytest.mark.skipif(sys.platform == "win32", reason="preexec_fn is POSIX only")
def test_closed_fd2_is_repaired_for_python_and_for_children():
    # Python left sys.stderr at None; print(file=None) and a traceback would go
    # to sys.stdout, the pipe. And a child process must get an open fd 2.
    out = run("""
        import os, subprocess, sys, traceback
        import _fd_isolation
        assert sys.stderr is None
        _fd_isolation.install()
        print("PY-STDERR-MARKER", file=sys.stderr)
        try:
            raise RuntimeError("TRACEBACK-MARKER")
        except RuntimeError:
            traceback.print_exc()
        sys.stderr.flush()
        child = subprocess.run([sys.executable, "-c",
                                "import os; os.fstat(2); os.write(2, b'CHILD-STDERR-MARKER')"],
                               stdout=subprocess.DEVNULL, close_fds=False)
        sys.stdout.write("JSONRPC-MARKER inheritable=%s child=%d stderr=%s,%s" % (
            os.get_inheritable(2), child.returncode, sys.stderr.errors, sys.stderr.line_buffering))
        sys.stdout.flush()
    """, preexec_fn=lambda: os.close(2))
    # the stream is as Python's own sys.stderr: a log line with a lone surrogate
    # does not raise, and a line is out when it is written
    assert out.stdout == "JSONRPC-MARKER inheritable=True child=0 stderr=backslashreplace,True"


@pytest.mark.skipif(sys.platform == "win32", reason="preexec_fn is POSIX only")
def test_a_repair_of_fd2_that_fails_is_undone_and_the_next_call_makes_it():
    # fd 2 opened but no sys.stderr built: a second call would find fd 2 open,
    # leave sys.stderr at None, and install on a process whose tracebacks go to
    # the pipe. The half repair is taken back instead.
    out = run("""
        import os, sys, traceback
        import _fd_isolation as iso

        def fd2():
            try:
                os.fstat(2); return "open"
            except OSError:
                return "closed"

        assert sys.stderr is None and fd2() == "closed"
        def failing(*a, **k):
            raise OSError("no stream today")
        iso.open = failing                 # the builtin, as the module sees it
        try:
            iso.install()
            outcome = "installed"
        except OSError:
            outcome = "raised"
        del iso.open
        sys.stdout.write("%s fd2=%s stderr_none=%s installed=%s " % (
            outcome, fd2(), sys.stderr is None, iso.installed()))
        sys.stdout.flush()
        iso.install()
        print("PY-STDERR-MARKER", file=sys.stderr)
        try:
            raise RuntimeError("TRACEBACK-MARKER")
        except RuntimeError:
            traceback.print_exc()
        sys.stderr.flush()
        sys.stdout.write("JSONRPC-MARKER fd2=%s" % fd2()); sys.stdout.flush()
    """, preexec_fn=lambda: os.close(2))
    assert out.stdout == ("raised fd2=closed stderr_none=True installed=False "
                          "JSONRPC-MARKER fd2=open")


def test_a_python_without_sys_stderr_gets_one_on_an_open_fd2():
    out = run("""
        import gc, os, sys, traceback
        import _fd_isolation
        sys.stderr = None
        _fd_isolation.install()
        print("PY-STDERR-MARKER", file=sys.stderr)
        try:
            raise RuntimeError("TRACEBACK-MARKER")
        except RuntimeError:
            traceback.print_exc()
        sys.stderr.flush()
        stream = sys.stderr; sys.stderr = None; del stream; gc.collect()
        os.write(2, b"AFTER-THE-STREAM-MARKER")      # EBADF if the stream owned fd 2
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
    """)
    assert out.stdout == "JSONRPC-MARKER"
    assert "PY-STDERR-MARKER" in out.stderr and "TRACEBACK-MARKER" in out.stderr
    assert "AFTER-THE-STREAM-MARKER" in out.stderr


def test_a_repair_that_fails_leaves_an_fd2_it_did_not_open():
    out = run("""
        import os, sys
        import _fd_isolation as iso
        sys.stderr = None
        def failing(*a, **k):
            raise OSError("no stream today")
        iso.open = failing
        try:
            iso.install()
            outcome = "installed"
        except OSError:
            outcome = "raised"
        del iso.open
        os.write(2, b"FD2-MARKER")                   # EBADF if the undo closed it
        sys.stdout.write(outcome); sys.stdout.flush()
    """)
    assert out.stdout == "raised"
    assert "FD2-MARKER" in out.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="preexec_fn is POSIX only")
def test_the_saved_pipe_never_lands_on_a_standard_descriptor():
    # With fd 0 closed as well, the lowest free descriptor is 0: the pipe must
    # not be saved there, and fd 0 stays as it was.
    def close_0_and_2():
        os.close(0)
        os.close(2)

    out = run("""
        import os, sys
        import _fd_isolation
        _fd_isolation.install()
        try:
            os.fstat(0); stdin = "open"
        except OSError:
            stdin = "closed"
        sys.stdout.write("JSONRPC-MARKER saved_above_2=%s stdin=%s" % (sys.stdout.fileno() > 2, stdin))
        sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """, preexec_fn=close_0_and_2)
    assert out.stdout == "JSONRPC-MARKER saved_above_2=True stdin=closed"


# ----- what was written before, and a warning nobody reads -----

def test_what_python_had_buffered_still_goes_to_the_pipe():
    # A block-buffered sys.stdout holding text when the isolation is installed:
    # flushed afterwards, it would follow fd 1 to stderr.
    out = run("""
        import os, sys
        import _fd_isolation
        # held in the text layer also under PYTHONUNBUFFERED=1
        sys.stdout.reconfigure(line_buffering=False, write_through=False)
        sys.stdout.write("EARLY-MARKER ")           # no flush
        _fd_isolation.install()
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
    """)
    assert out.stdout == "EARLY-MARKER JSONRPC-MARKER"
    assert "EARLY-MARKER" not in out.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="needs os.pipe descriptors passed to a child")
def test_a_warning_that_cannot_be_written_does_not_undo_the_installation(tmp_path):
    # stdout and stderr on one pipe whose reader is gone: the warning's write
    # fails (EPIPE). The installation stands and the flag says so.
    result = tmp_path / "result.txt"
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        child = subprocess.run(
            [sys.executable, "-c", textwrap.dedent("""
                import sys
                import _fd_isolation
                try:
                    _fd_isolation.install()
                    outcome = "installed=%s" % _fd_isolation.installed()
                except BaseException as exc:
                    outcome = "raised %s" % type(exc).__name__
                with open(sys.argv[1], "w") as result:    # closed: no ResourceWarning for
                    result.write(outcome)                  # the dead stderr under -W default
            """), str(result)],
            env=cases.env(), cwd=str(cases.REPO_ROOT), stdin=subprocess.DEVNULL,
            stdout=write_end, stderr=write_end, timeout=60)
    finally:
        os.close(write_end)
    assert result.read_text() == "installed=True"
    assert child.returncode == 0
