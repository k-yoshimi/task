"""Phase L-6: end-to-end MCP integration tests for tot_mcp.

The unit-level tests in ``test_server.py::TestIntegration`` only cover
init + set_param against the real ``libtotapi.so`` because at L-3..L-5
``tot_run`` and ``tot_get_state`` were stubs returning rc=4. With the
L-6 fan-out (tr + ti + fp + wrx) wired into ``libtotapi.so``, the
orchestrator now supports a full life cycle end-to-end through the MCP
handler surface. This module pins that contract:

* ``test_init_run_state_finalize`` — drive the cycle one handler at a
  time so a regression in one specific handler is pin-pointable
  (init -> set_param -> run -> get_state -> finalize).
* ``test_run_and_get_state_oneshot`` — exercise the
  ``handle_run_and_get_state`` convenience that bundles the same cycle
  into a single call (the LLM-friendly fast-path).

The tests skip cleanly when ``libtotapi.so`` is missing so they remain
safe to run on a developer machine that has not built the orchestrator.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
TOT_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure both tot_mcp (parent) and totlib (sibling) are importable.
for extra in (str(TOT_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from tot_mcp import server as srv  # noqa: E402

LIBTOTAPI_SO = REPO_ROOT / "tot" / "libtotapi.so"


@unittest.skipUnless(
    LIBTOTAPI_SO.exists(),
    f"libtotapi.so not found at {LIBTOTAPI_SO}; "
    "run `make -C tot libtotapi.so`",
)
class TestL6Integration(unittest.TestCase):
    """Full MCP handler cycle against the L-6 ``libtotapi.so``."""

    def setUp(self) -> None:
        # Each test owns its own _ServerState so a leaked Tot from a
        # neighbouring test cannot mask a real lifecycle bug.
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()

    def tearDown(self) -> None:
        try:
            srv.STATE.close()
        finally:
            srv.STATE = self._real_state

    def test_init_run_state_finalize(self) -> None:
        """Cycle each handler one-by-one.

        Reports the per-step return value via subTest so a regression
        in any specific handler points at the failing step rather than
        producing a generic ``rc=4`` chain.
        """
        with self.subTest("init"):
            self.assertIn("initialized", srv.handle_init())
        with self.subTest("set_param"):
            msg = srv.handle_set_param("tr:DT", 0.001)
            self.assertIn("tr:DT", msg)
        with self.subTest("run"):
            msg = srv.handle_run(0)  # zero steps is a valid no-op
            self.assertIn("0", msg)
        with self.subTest("get_state"):
            state = srv.handle_get_state()
            # L-6 surfaces TR-authoritative slots: tr_present=1, NRMAX>0.
            self.assertEqual(state["presence"]["tr"], 1)
            self.assertGreater(state["NRMAX"], 0)
            self.assertGreater(state["NSMAX"], 0)
            # Scalars block exists and includes the canonical 13 slots.
            self.assertIn("WPT", state["scalars"])
            self.assertIn("Q0", state["scalars"])
        with self.subTest("finalize"):
            self.assertIn("finalized", srv.handle_finalize())

    def test_run_and_get_state_oneshot(self) -> None:
        """``handle_run_and_get_state`` bundles init + set_params + run
        + get_state in one call. After L-6 it must return a populated
        state dict (not the empty L-3/L-4/L-5 stub shape).
        """
        out = srv.handle_run_and_get_state(
            params={"tr:DT": 0.001},
            ntmax=1,
        )
        # Top-level shape mirrors TotState.to_dict().
        for key in ("presence", "NT", "NRMAX", "NSMAX", "scalars", "profile"):
            self.assertIn(key, out)
        self.assertEqual(out["presence"]["tr"], 1)
        self.assertGreater(out["NRMAX"], 0)
        self.assertGreaterEqual(out["NT"], 1, "NT must advance after ntmax=1")
        # Profile slice length matches NRMAX.
        self.assertEqual(len(out["profile"]), out["NRMAX"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
