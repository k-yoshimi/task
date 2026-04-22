"""Tests for the tr_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param
  dispatch via a mock Trlib) always run — they require neither the
  Python MCP SDK nor a built ``libtrapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``tr/libtrapi.so`` exists.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \
        -s python/mcp-servers/tr_mcp/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
TR_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both tr_mcp (parent) and trlib (sibling).
for extra in (str(TR_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from tr_mcp import server as srv  # noqa: E402

# trlib exceptions for error-mapping tests.
from trlib import (  # noqa: E402
    TrlibError,
    TrlibParamError,
    TrlibStateError,
    TrlibRunError,
    TrlibNotImplementedError,
)


LIBTRAPI_SO = REPO_ROOT / "tr" / "libtrapi.so"


# =====================================================================
# Pure-Python tests (no libtrapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The hardcoded parameter registry should look sensible."""

    def test_registry_nonempty(self) -> None:
        self.assertGreater(len(srv.PARAMETER_REGISTRY), 30)

    def test_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRY.items():
            with self.subTest(name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_contains_expected_core_params(self) -> None:
        expected = {"RR", "RA", "BB", "PN", "PT", "NSMAX", "DT", "NTMAX"}
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected params: {missing}")


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in ("NT", "NRMAX", "NSMAX", "scalars", "profile"):
            self.assertIn(k, schema["properties"])

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("profile", out["properties"])


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "tr")
        self.assertEqual(out["count"], len(srv.PARAMETER_REGISTRY))
        self.assertIn("parameters", out)
        self.assertIn("RR", out["parameters"])


class TestErrorWrap(unittest.TestCase):
    """_wrap_trlib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_trlib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_param_error(self) -> None:
        self._assert_message(TrlibParamError("BAD: ierr=1"), "invalid parameter")

    def test_state_error(self) -> None:
        self._assert_message(
            TrlibStateError("x: ierr=2"),
            "library not initialized",
        )

    def test_run_error(self) -> None:
        self._assert_message(TrlibRunError("x: ierr=3"), "calculation failed")

    def test_notimpl_error(self) -> None:
        self._assert_message(
            TrlibNotImplementedError("x: ierr=4"),
            "not implemented",
        )

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libtrapi.so missing"),
            "libtrapi.so not found",
        )

    def test_base_trliberror(self) -> None:
        self._assert_message(TrlibError("misc"), "trlib error")


# =====================================================================
# Mock-Trlib tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockTrlib:
    """Minimal Trlib stand-in used to verify bulk-param dispatch."""

    def __init__(self) -> None:
        self.scalar_calls: List[tuple] = []
        self.string_calls: List[tuple] = []
        self.run_calls: List[int] = []
        self.closed = False

    def set_param(self, name: str, value: float) -> None:
        self.scalar_calls.append((name, value))

    def set_param_str(self, name: str, value: str) -> None:
        self.string_calls.append((name, value))

    def run(self, ntmax: int) -> None:
        self.run_calls.append(int(ntmax))

    def get_state(self) -> Any:
        class _S:
            def to_dict(self_inner) -> Dict[str, Any]:
                return {
                    "NT": 0, "NRMAX": 0, "NSMAX": 0,
                    "scalars": {}, "profile": [],
                }

        return _S()

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_dict_and_string(self) -> None:
        tr = _MockTrlib()
        params: Dict[str, Any] = {
            "RR":     6.5,
            "BB":     5.3,
            "PN":     [0.7, 0.7],        # list -> PN[1], PN[2]
            "PT":     {2: 4.2, 1: 3.5},  # dict -> PT[2], PT[1]
            "KNAMEQ": "eqdata.ITER01",    # string path
        }
        applied = srv._apply_bulk_params(tr, params)

        # 2 scalars + 2 list + 2 dict + 1 string = 7 applied keys
        self.assertEqual(len(applied), 7)

        # scalar_calls should cover all non-string numeric sets
        scalar_names = [n for n, _ in tr.scalar_calls]
        for expected in ("RR", "BB", "PN[1]", "PN[2]", "PT[1]", "PT[2]"):
            self.assertIn(expected, scalar_names)

        self.assertEqual(tr.string_calls, [("KNAMEQ", "eqdata.ITER01")])

    def test_rejects_unsupported_type(self) -> None:
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(tr, {"RR": object()})

    def test_rejects_bool(self) -> None:
        # bool is a subclass of int; we want it rejected as ambiguous.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(tr, {"MDLNB": True})

    def test_rejects_bool_in_list(self) -> None:
        # Codex P2 follow-up: nested bool in a bulk list must also
        # raise, not be silently coerced to 1.0 by float().
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(tr, {"PN": [0.7, True]})

    def test_rejects_bool_in_dict_value(self) -> None:
        # Codex P2 follow-up: nested bool as dict value must also raise.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(tr, {"PT": {1: True}})

    def test_rejects_bool_dict_index(self) -> None:
        # Codex P2 follow-up: bool key would be int()-coerced to 1;
        # reject up-front so the index origin is unambiguous.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(tr, {"PT": {True: 3.5}})

    def test_rejects_non_numeric_string_element(self) -> None:
        # MED-5: float() on a non-numeric string should map to TrlibError
        # (not leak a raw ValueError), with the key name in the message.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError) as ctx:
            srv._apply_bulk_params(tr, {"PN": [0.7, "oops"]})
        self.assertIn("PN[2]", str(ctx.exception))

    def test_rejects_non_int_dict_index(self) -> None:
        # MED-5: int() on a non-numeric index should map to TrlibError.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError) as ctx:
            srv._apply_bulk_params(tr, {"PT": {"not-an-int": 3.5}})
        self.assertIn("PT", str(ctx.exception))

    def test_partial_bulk_mutation_on_failure(self) -> None:
        # LOW-2: on a partial failure, earlier keys remain written.
        # Documented as non-transactional in set_params docstring.
        tr = _MockTrlib()
        with self.assertRaises(TrlibError):
            srv._apply_bulk_params(
                tr,
                {"RR": 6.5, "BAD": object(), "BB": 5.3},
            )
        # RR was applied before the failing 'BAD' key; BB never reached.
        scalar_names = [n for n, _ in tr.scalar_calls]
        self.assertIn("RR", scalar_names)
        self.assertNotIn("BB", scalar_names)


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_tr = _MockTrlib()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_tr
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_set_param(self) -> None:
        msg = srv.handle_set_param("RR", 6.5)
        self.assertIn("RR", msg)
        self.assertEqual(self.mock_tr.scalar_calls[-1], ("RR", 6.5))

    def test_handle_set_param_str(self) -> None:
        # MED-6: tr_mcp exposes set_param_str mirroring eq_mcp.
        msg = srv.handle_set_param_str("KNAMEQ", "eqdata.ITER01")
        self.assertIn("KNAMEQ", msg)
        self.assertIn("eqdata.ITER01", msg)
        self.assertEqual(
            self.mock_tr.string_calls[-1],
            ("KNAMEQ", "eqdata.ITER01"),
        )

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"BB": 5.3})
        self.assertIn("1 parameter", msg)

    def test_handle_run(self) -> None:
        msg = srv.handle_run(3)
        self.assertIn("3", msg)
        self.assertEqual(self.mock_tr.run_calls, [3])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NT", out)
        self.assertIn("scalars", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"RR": 7.0}, ntmax=2,
        )
        self.assertIn("NT", out)
        self.assertEqual(self.mock_tr.scalar_calls[-1], ("RR", 7.0))
        self.assertEqual(self.mock_tr.run_calls, [2])

    def test_handle_run_and_get_state_force_closes_prior(self) -> None:
        """Codex MCP audit 2026-04-22 (HIGH) fix: prior STATE.tr must
        be finalized before the one-shot run, so left-over MODELG /
        mesh / NSMAX from earlier tool calls cannot leak into the
        supposedly-isolated run.

        Verified by patching STATE.close() and asserting it is called
        exactly once during handle_run_and_get_state.
        """
        with mock.patch.object(srv.STATE, "close") as mock_close:
            srv.handle_run_and_get_state(params={"RR": 6.2}, ntmax=1)
            self.assertEqual(
                mock_close.call_count, 1,
                "run_and_get_state must STATE.close() to finalize "
                "prior Trlib before opening a fresh handle "
                "(Codex MCP audit 2026-04-22).",
            )


class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libtrapi.so."""

    def _run_quiet(self, argv: List[str]) -> int:
        # Silence stdout so test output stays clean.
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return srv.main(argv)

    def test_help(self) -> None:
        rc = self._run_quiet(["--help"])
        self.assertEqual(rc, 0)

    def test_print_tools(self) -> None:
        rc = self._run_quiet(["--print-tools"])
        self.assertEqual(rc, 0)


# =====================================================================
# FastMCP construction (skipped if mcp is not installed).
# =====================================================================
@unittest.skipUnless(
    srv.MCP_AVAILABLE, "Python MCP SDK (`mcp`) not installed",
)
class TestBuildServer(unittest.TestCase):
    def test_build_server_returns_instance(self) -> None:
        s = srv.build_server()
        self.assertIsNotNone(s)
        # FastMCP instances expose ``name`` attribute.
        self.assertEqual(getattr(s, "name", None), "task-tr")


# =====================================================================
# Integration tests (real libtrapi.so).
# =====================================================================
@unittest.skipUnless(
    LIBTRAPI_SO.exists(),
    f"libtrapi.so not found at {LIBTRAPI_SO}; skipping integration tests",
)
class TestIntegration(unittest.TestCase):
    """End-to-end init → run(0) → get_state → finalize against .so."""

    def setUp(self) -> None:
        # Reset server state between tests.
        srv.STATE.close()

    def tearDown(self) -> None:
        srv.STATE.close()

    def test_init_run_state_finalize(self) -> None:
        self.assertIn("initialized", srv.handle_init())
        self.assertIn("0", srv.handle_run(0))
        state = srv.handle_get_state()
        self.assertIn("NT", state)
        self.assertIn("scalars", state)
        self.assertIn("finalized", srv.handle_finalize())

    def test_run_and_get_state_oneshot(self) -> None:
        out = srv.handle_run_and_get_state(params=None, ntmax=0)
        self.assertIn("NT", out)
        self.assertIsInstance(out["scalars"], dict)

    def test_reinit_cycle_reproducible(self) -> None:
        """init -> run(0) -> get_state -> finalize, twice.

        Asserts the second cycle's state matches the first byte-for-byte.
        Catches heap-reuse leaks of the class fixed in tr's
        ``trcomm_profile.f90`` zero-init sweep on 2026-04-20: if a SAVE /
        ALLOCATE-without-zeroing regression slips back in, the second
        init will see residual state from the first cycle and this
        test will trip.
        """

        # First cycle: default init, no params needed.
        srv.handle_init()
        srv.handle_run(0)
        s1 = srv.handle_get_state()
        srv.handle_finalize()

        # Second cycle with identical params.
        srv.handle_init()
        srv.handle_run(0)
        s2 = srv.handle_get_state()
        srv.handle_finalize()

        # tr state has no CPU-time fields; direct equality is the strict
        # check. If the two cycles drift we surface it immediately rather
        # than masking with try/except.
        if s1 != s2:
            # Enumerate divergence for a readable failure.
            diffs = {k: (s1.get(k), s2.get(k)) for k in set(s1) | set(s2)
                     if s1.get(k) != s2.get(k)}
            self.fail(
                "tr reinit cycle produced divergent state (possible "
                f"heap-reuse leak): differing keys = {sorted(diffs)}"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
