"""tr_mcp lifecycle contract: finalize must actually reset the backend.

Regression test for #227 item 2.

``handle_finalize`` used to mark the :class:`Trlib` handle closed *without*
calling ``tr_finalize``, as a workaround for a SIGABRT in the Fortran cleanup
path.  Because ``tr_init`` is idempotent (``tr/tr_api.f90``: "already
initialized, just return OK"), that left ``g_initialized`` set and made a
subsequent ``init`` a no-op -- so parameters set before ``finalize`` survived
into the next session.  It also disagreed with ``handle_run_and_get_state``,
whose fresh-init contract requires a real finalize.

Both paths now go through ``STATE.close()``.  These tests pin the resulting
observable contract.

Each check runs in a fresh subprocess because libtrapi.so holds singleton
Fortran state that cannot be reset from within the same process except through
the very code under test.

Run from the repo root::

    python3 -m unittest discover -v \\
        -s python/mcp-servers/tr_mcp/tests
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

_LIBTRAPI = REPO_ROOT / "tr" / "libtrapi.so"


def _run(body: str) -> str:
    """Execute `body` against tr_mcp.server in a fresh interpreter."""
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(MCP_ROOT)!r})
        sys.path.insert(0, {str(PYTHON_ROOT)!r})
        import tr_mcp.server as srv
        {textwrap.indent(textwrap.dedent(body), " " * 8).lstrip()}
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
            f"probe exited {proc.returncode}\nstdout: {proc.stdout}\n"
            f"stderr: {proc.stderr[-2000:]}"
        )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")]
    if not lines:
        raise AssertionError(f"probe produced no RESULT line\nstdout: {proc.stdout}")
    return lines[-1][len("RESULT ") :]


@unittest.skipUnless(_LIBTRAPI.exists(), f"{_LIBTRAPI} not built")
class TestFinalizeResetsBackend(unittest.TestCase):
    """#227 item 2: finalize -> init must restore Fortran defaults."""

    def test_finalize_then_init_restores_defaults(self):
        result = _run(
            """
            srv.handle_init()
            default_nsmax = srv.handle_get_state()["NSMAX"]
            srv.handle_set_param("NSMAX", int(default_nsmax) + 1)
            mutated = srv.handle_get_state()["NSMAX"]
            srv.handle_finalize()
            srv.handle_init()
            after = srv.handle_get_state()["NSMAX"]
            print(f"RESULT {default_nsmax} {mutated} {after}")
            """
        )
        default_nsmax, mutated, after = (int(x) for x in result.split())
        self.assertEqual(
            mutated, default_nsmax + 1, "set_param did not take effect"
        )
        self.assertEqual(
            after,
            default_nsmax,
            "finalize() did not reset the Fortran backend: a value set before "
            "finalize survived the following init(). handle_finalize must call "
            "tr_finalize (via STATE.close()), not just mark the handle closed.",
        )

    def test_finalize_is_idempotent(self):
        """A second finalize must not raise.

        Note this exercises the *Python* short-circuit: ``_ServerState.close()``
        sets ``self.tr = None``, so the second call returns without re-entering
        Fortran. The Fortran-level double-DEALLOCATE guard
        (``tr/trcomm.f90``) is what makes that safe if a caller does reach it
        twice; it is measured separately, not by this test.
        """
        result = _run(
            """
            srv.handle_init()
            srv.handle_finalize()
            srv.handle_finalize()
            print("RESULT ok")
            """
        )
        self.assertEqual(result, "ok")

    def test_run_and_get_state_uses_the_same_reset_path(self):
        """run_and_get_state's fresh-init contract survives a prior mutation."""
        result = _run(
            """
            srv.handle_init()
            default_nsmax = srv.handle_get_state()["NSMAX"]
            srv.handle_set_param("NSMAX", int(default_nsmax) + 1)
            state = srv.handle_run_and_get_state(ntmax=1)
            print(f"RESULT {default_nsmax} {state['NSMAX']}")
            """
        )
        default_nsmax, one_shot = (int(x) for x in result.split())
        self.assertEqual(
            one_shot,
            default_nsmax,
            "run_and_get_state leaked a prior session's parameter mutation; "
            "its documented contract is a fresh init each call.",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
