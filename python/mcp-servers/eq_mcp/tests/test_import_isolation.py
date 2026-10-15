"""Importing the MCP server modules must not mutate the host process.

Regression test for #227 item 1.

Both ``eq_mcp.server`` and ``tr_mcp.server`` install an fd-isolation shim
(``dup(1)`` / ``dup2(2, 1)`` / rebuild ``sys.stdout``) so that Fortran
``WRITE(6,...)`` cannot corrupt the JSON-RPC pipe.  That shim used to run at
*module scope*, so merely importing either module -- during pytest collection,
from an embedding application, or via ``python -c "import eq_mcp.server"`` --
redirected the whole process's fd 1 to stderr and replaced ``sys.stdout``.

The shim now lives in ``_install_fd_isolation()`` and is invoked explicitly by
``main()``.  These tests pin that contract.

Each check runs in a fresh subprocess: the mutation is process-global and
irreversible, so it cannot be asserted in-process after the fact.

Run from the repo root::

    python3 -m unittest discover -v \\
        -s python/mcp-servers/eq_mcp/tests
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
PYTHON_ROOT = HERE.parents[3]  # .../python
MCP_ROOT = HERE.parents[2]     # .../python/mcp-servers
REPO_ROOT = HERE.parents[4]    # repo root


def _probe(module: str) -> dict:
    """Import `module` in a fresh interpreter; report what it did to fd 1."""
    code = textwrap.dedent(
        f"""
        import os, sys
        sys.path.insert(0, {str(MCP_ROOT)!r})
        sys.path.insert(0, {str(PYTHON_ROOT)!r})

        before_fd1 = os.fstat(1)
        before_stdout = sys.stdout

        import {module}  # the operation under test

        after_fd1 = os.fstat(1)
        fd1_unchanged = (
            (before_fd1.st_dev, before_fd1.st_ino)
            == (after_fd1.st_dev, after_fd1.st_ino)
        )
        stdout_unchanged = before_stdout is sys.stdout

        # The module must still *offer* the isolation hook, just not run it.
        mod = sys.modules[{module!r}]
        has_hook = callable(getattr(mod, "_install_fd_isolation", None))
        installed = getattr(mod, "_FD_ISOLATION_INSTALLED", None)

        sys.stderr.write(
            f"{{fd1_unchanged}},{{stdout_unchanged}},{{has_hook}},{{installed}}\\n"
        )
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"probe for {module} exited {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    fields = proc.stderr.strip().splitlines()[-1].split(",")
    return {
        "fd1_unchanged": fields[0] == "True",
        "stdout_unchanged": fields[1] == "True",
        "has_hook": fields[2] == "True",
        "installed": fields[3],
    }


class TestImportDoesNotMutateProcess(unittest.TestCase):
    """#227 item 1: import must be side-effect free w.r.t. fd 1 / sys.stdout."""

    def _assert_clean(self, module: str) -> None:
        r = _probe(module)
        self.assertTrue(
            r["fd1_unchanged"],
            f"importing {module} redirected the host process's fd 1 "
            "(the fd-isolation shim must only run from main())",
        )
        self.assertTrue(
            r["stdout_unchanged"],
            f"importing {module} replaced sys.stdout "
            "(the fd-isolation shim must only run from main())",
        )
        self.assertTrue(
            r["has_hook"],
            f"{module} no longer exposes _install_fd_isolation(); "
            "main() needs it to set up the stdio transport",
        )
        self.assertEqual(
            r["installed"],
            "False",
            f"{module}._FD_ISOLATION_INSTALLED should be False after a bare import",
        )

    def test_eq_mcp_server_import_is_clean(self):
        self._assert_clean("eq_mcp.server")

    def test_tr_mcp_server_import_is_clean(self):
        self._assert_clean("tr_mcp.server")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
