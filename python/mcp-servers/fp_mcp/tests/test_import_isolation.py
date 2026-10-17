"""fp_mcp's fd isolation is installed by ``main()``, never by an import.

The isolation (``dup(1)`` / ``dup2(2, 1)`` / a new ``sys.stdout`` on the saved
pipe) keeps Fortran ``WRITE(6,...)`` off the JSON-RPC pipe. Run at module
scope it would redirect fd 1 of whatever process imports ``fp_mcp.server``:
pytest during collection, a notebook, an embedding application. This is the
contract #227 item 1 asks of ``eq_mcp`` and ``tr_mcp``, held here for
``fp_mcp``.

Every check runs in a fresh interpreter: the redirect is process-global, and
in the test process it would take pytest's own capture of fd 1 with it.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[3]          # <repo>/python
REPO_ROOT = PYTHON_ROOT.parent

# What the stdio transport and the Fortran library do, in that order:
# JSON-RPC through sys.stdout, WRITE(6,...) straight to fd 1.
_STUB_SERVER = """
class _Stdio:
    def run(self):
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
srv.MCP_AVAILABLE = True          # build_server is replaced: the SDK is not needed
srv.build_server = lambda: _Stdio()
"""


def _run(code, *args):
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join([str(PYTHON_ROOT), str(PYTHON_ROOT / "mcp-servers")])}
    out = subprocess.run([sys.executable, "-c", textwrap.dedent(code), *args], env=env,
                         cwd=str(REPO_ROOT), capture_output=True, stdin=subprocess.DEVNULL,
                         encoding="utf-8", errors="replace", timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return out


def test_import_leaves_fd1_and_sys_stdout_alone():
    out = _run("""
        import os, sys
        before = os.fstat(1); stdout = sys.stdout
        import fp_mcp.server as srv
        after = os.fstat(1)
        print("fd1_same", (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino))
        print("stdout_same", stdout is sys.stdout)
        print("hook", callable(getattr(srv, "_install_fd_isolation", None)))
        print("installed", srv._FD_ISOLATION_INSTALLED)
        sys.stdout.flush()               # the prints first: os.write is not buffered
        os.write(1, b"FD1-MARKER")
    """)
    assert out.stdout.split() == ["fd1_same", "True", "stdout_same", "True",
                                  "hook", "True", "installed", "False", "FD1-MARKER"]
    assert "FD1-MARKER" not in out.stderr


def test_main_installs_the_isolation_before_the_stdio_server_starts():
    out = _run("import os, sys\nimport fp_mcp.server as srv\n" + _STUB_SERVER + """
assert srv.main([]) == 0
assert srv._FD_ISOLATION_INSTALLED
""")
    assert "JSONRPC-MARKER" in out.stdout and "JSONRPC-MARKER" not in out.stderr
    assert "FORTRAN-MARKER" in out.stderr and "FORTRAN-MARKER" not in out.stdout


def test_installing_twice_keeps_sys_stdout_on_the_pipe():
    # A second dup(1) would save the already-redirected stderr as "the pipe".
    out = _run("""
        import os, sys
        import fp_mcp.server as srv
        srv._install_fd_isolation()
        srv._install_fd_isolation()
        sys.stdout.write("JSONRPC-MARKER"); sys.stdout.flush()
        os.write(1, b"FORTRAN-MARKER")
    """)
    assert "JSONRPC-MARKER" in out.stdout and "JSONRPC-MARKER" not in out.stderr
    assert "FORTRAN-MARKER" in out.stderr and "FORTRAN-MARKER" not in out.stdout


def test_help_and_print_tools_install_nothing():
    for flag in ("--help", "--print-tools"):
        out = _run("""
            import os, sys
            import fp_mcp.server as srv
            assert srv.main([sys.argv[1]]) == 0
            print("installed", srv._FD_ISOLATION_INSTALLED)
            os.write(1, b"FD1-MARKER")
        """, flag)
        assert "installed False" in out.stdout, flag
        assert "FD1-MARKER" in out.stdout and "FD1-MARKER" not in out.stderr, flag
        assert ("fp-mcp" if flag == "--help" else "run_and_get_state") in out.stdout, flag


def test_missing_sdk_installs_nothing():
    out = _run("""
        import os, sys
        import fp_mcp.server as srv
        srv.MCP_AVAILABLE = False
        rc = srv.main([])
        print("rc", rc, "installed", srv._FD_ISOLATION_INSTALLED)
        sys.stdout.flush()
        os.write(1, b"FD1-MARKER")
    """)
    assert "rc 2 installed False" in out.stdout
    assert "FD1-MARKER" in out.stdout and "FD1-MARKER" not in out.stderr
