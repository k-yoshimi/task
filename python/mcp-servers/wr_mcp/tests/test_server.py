"""Tests for the wr_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param
  dispatch via a mock Wrlib) always run — they require neither the
  Python MCP SDK nor a built ``libwrapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``wr/libwrapi.so`` exists.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \
        -s python/mcp-servers/wr_mcp/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
WR_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both wr_mcp (parent) and wrlib (sibling).
for extra in (str(WR_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from wr_mcp import server as srv  # noqa: E402

# wrlib exceptions for error-mapping tests.
from wrlib import (  # noqa: E402
    WrlibError,
    WrlibParamError,
    WrlibStateError,
    WrlibRunError,
    WrlibNotImplementedError,
)


LIBWRAPI_SO = REPO_ROOT / "wr" / "libwrapi.so"


# =====================================================================
# Pure-Python tests (no libwrapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The hardcoded parameter registry should look sensible."""

    def test_registry_nonempty(self) -> None:
        # The wr registry is ~80 entries (scalar + array names).
        self.assertGreater(len(srv.PARAMETER_REGISTRY), 60)

    def test_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRY.items():
            with self.subTest(name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_contains_expected_wr_scalars(self) -> None:
        # Ray-tracing specific scalars that callers will touch first.
        expected = {
            "RR", "BB", "NRAYMAX", "NSTPMAX", "RF", "RPI", "ZPI",
            "PHII", "RNZI", "RNPHII", "RKR0", "UUI", "mode_beam",
        }
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected params: {missing}")

    def test_contains_per_ray_arrays(self) -> None:
        expected = {
            "RFIN", "RPIN", "ZPIN", "PHIIN", "RKRIN", "RNZIN",
            "RNPHIIN", "ANGZIN", "ANGPHIN", "UUIN", "MODEWIN",
        }
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected arrays: {missing}")


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in ("NRAYMAX", "NRSMAX", "NRLMAX", "scalars",
                  "rays", "profile_rs", "profile_rl"):
            self.assertIn(k, schema["properties"])

    def test_rays_item_has_rays_end(self) -> None:
        rays_item = srv.STATE_SCHEMA["properties"]["rays"]["items"]
        # The 9-element rays_end field is load-bearing for consumers.
        self.assertIn("rays_end", rays_item["properties"])

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("rays", out["properties"])
        self.assertIn("profile_rs", out["properties"])
        self.assertIn("profile_rl", out["properties"])


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "wr")
        self.assertEqual(out["count"], len(srv.PARAMETER_REGISTRY))
        self.assertIn("parameters", out)
        self.assertIn("RR", out["parameters"])
        self.assertIn("RFIN", out["parameters"])


class TestErrorWrap(unittest.TestCase):
    """_wrap_wrlib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_wrlib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_param_error(self) -> None:
        self._assert_message(WrlibParamError("BAD: ierr=1"), "invalid parameter")

    def test_state_error(self) -> None:
        self._assert_message(
            WrlibStateError("x: ierr=2"),
            "library not initialized",
        )

    def test_run_error(self) -> None:
        self._assert_message(WrlibRunError("x: ierr=3"), "calculation failed")

    def test_notimpl_error(self) -> None:
        self._assert_message(
            WrlibNotImplementedError("x: ierr=4"),
            "not implemented",
        )

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libwrapi.so missing"),
            "libwrapi.so not found",
        )

    def test_base_wrliberror(self) -> None:
        self._assert_message(WrlibError("misc"), "wrlib error")


# =====================================================================
# Mock-Wrlib tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockWrlib:
    """Minimal Wrlib stand-in used to verify bulk-param dispatch."""

    def __init__(self) -> None:
        self.scalar_calls: List[tuple] = []
        self.run_calls: List[int] = []
        self.closed = False

    def set_param(self, name: str, value: float) -> None:
        self.scalar_calls.append((name, value))

    def run(self, nray_request: int = 0) -> None:
        self.run_calls.append(int(nray_request))

    def get_state(self) -> Any:
        class _S:
            def to_dict(self_inner) -> Dict[str, Any]:
                return {
                    "NRAYMAX": 0,
                    "NRSMAX": 0,
                    "NRLMAX": 0,
                    "scalars": {},
                    "rays": [],
                    "profile_rs": [],
                    "profile_rl": [],
                }

        return _S()

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_and_dict(self) -> None:
        wr = _MockWrlib()
        params: Dict[str, Any] = {
            "RR":   3.0,
            "BB":   3.5,
            "RFIN": [170.0, 170.0],    # list -> RFIN[1], RFIN[2]
            "UUIN": {2: 0.6, 1: 0.8},   # dict -> UUIN[2], UUIN[1]
        }
        applied = srv._apply_bulk_params(wr, params)

        # 2 scalars + 2 list + 2 dict = 6 applied keys
        self.assertEqual(len(applied), 6)

        scalar_names = [n for n, _ in wr.scalar_calls]
        for expected in ("RR", "BB", "RFIN[1]", "RFIN[2]",
                         "UUIN[1]", "UUIN[2]"):
            self.assertIn(expected, scalar_names)

    def test_rejects_string_value(self) -> None:
        # wrlib has no string-valued parameter, so strings must fail.
        wr = _MockWrlib()
        with self.assertRaises(WrlibError):
            srv._apply_bulk_params(wr, {"RR": "oops"})

    def test_rejects_unsupported_type(self) -> None:
        wr = _MockWrlib()
        with self.assertRaises(WrlibError):
            srv._apply_bulk_params(wr, {"RR": object()})


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_wr = _MockWrlib()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_wr
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_set_param(self) -> None:
        msg = srv.handle_set_param("RR", 3.0)
        self.assertIn("RR", msg)
        self.assertEqual(self.mock_wr.scalar_calls[-1], ("RR", 3.0))

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"BB": 3.5})
        self.assertIn("1 parameter", msg)

    def test_handle_run(self) -> None:
        msg = srv.handle_run(4)
        self.assertIn("4", msg)
        self.assertEqual(self.mock_wr.run_calls, [4])

    def test_handle_run_default_nray_request(self) -> None:
        msg = srv.handle_run()
        self.assertIn("0", msg)
        self.assertEqual(self.mock_wr.run_calls, [0])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NRAYMAX", out)
        self.assertIn("scalars", out)
        self.assertIn("rays", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"RR": 3.2, "RFIN": [170.0]}, nray_request=1,
        )
        self.assertIn("NRAYMAX", out)
        # RR scalar + RFIN[1] from the list
        names = [n for n, _ in self.mock_wr.scalar_calls]
        self.assertIn("RR", names)
        self.assertIn("RFIN[1]", names)
        self.assertEqual(self.mock_wr.run_calls, [1])


class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libwrapi.so."""

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
        self.assertEqual(getattr(s, "name", None), "task-wr")


# =====================================================================
# Integration tests (real libwrapi.so).
# =====================================================================
@unittest.skipUnless(
    LIBWRAPI_SO.exists(),
    f"libwrapi.so not found at {LIBWRAPI_SO}; skipping integration tests",
)
class TestIntegration(unittest.TestCase):
    """End-to-end init → run(0) → get_state → finalize against .so."""

    def setUp(self) -> None:
        # Reset server state between tests.
        srv.STATE.close()

    def tearDown(self) -> None:
        srv.STATE.close()

    # wr_run requires a properly-configured plasma + equilibrium
    # (MODELG, RR, RA, BB, NSMAX, PA/PZ/PN/...). Without them, the
    # default-init wr_run loops on a non-converging dispersion solution
    # for 10-15 seconds before returning ierr=3 (= CALC_FAILED). Two
    # such tests in a row blow the per-module timeout (this was the
    # source of the aggregate `pytest python/` hang). Reuse the
    # wr_test001 fixture that the libwr equivalence test uses so the
    # exact same plasma+ray setup that PASSes there also runs here.
    @classmethod
    def setUpClass(cls) -> None:
        from wrlib.tests.fixtures import wr_test001_params as f
        cls._fixture = f

    def _apply_fixture(self) -> None:
        f = self._fixture
        for name, value in f.SCALARS.items():
            srv.handle_set_param(name, float(value))
        for name, arr in f.ARRAYS.items():
            if isinstance(arr, dict):
                for i, v in arr.items():
                    srv.handle_set_param(f"{name}[{int(i)}]", float(v))
            else:
                for i, v in enumerate(arr, start=1):
                    srv.handle_set_param(f"{name}[{i}]", float(v))

    def test_init_run_state_finalize(self) -> None:
        self.assertIn("initialized", srv.handle_init())
        self._apply_fixture()
        self.assertIn("0", srv.handle_run(0))
        state = srv.handle_get_state()
        self.assertIn("NRAYMAX", state)
        self.assertIn("scalars", state)
        self.assertIn("finalized", srv.handle_finalize())

    def test_run_and_get_state_oneshot(self) -> None:
        # Build the param dict the handler expects: scalars + flattened
        # arrays as "NAME[i]"=value. Mirrors the equivalence-test pattern.
        f = self._fixture
        params: Dict[str, float] = {k: float(v) for k, v in f.SCALARS.items()}
        for name, arr in f.ARRAYS.items():
            if isinstance(arr, dict):
                for i, v in arr.items():
                    params[f"{name}[{int(i)}]"] = float(v)
            else:
                for i, v in enumerate(arr, start=1):
                    params[f"{name}[{i}]"] = float(v)
        out = srv.handle_run_and_get_state(params=params, nray_request=0)
        self.assertIn("NRAYMAX", out)
        self.assertIsInstance(out["scalars"], dict)

    def test_finalize_reset_invariant(self) -> None:
        """After finalize, the next call must reopen a fresh handle."""
        srv.handle_init()
        srv.handle_finalize()
        # ensure_open transparently reopens; the new handle must not
        # be closed from the caller's perspective.
        wr = srv.STATE.ensure_open()
        self.assertFalse(wr.closed)

    def test_reinit_cycle_reproducible(self) -> None:
        """init -> apply_fixture -> run(0) -> get_state -> finalize, twice.

        Asserts the second cycle's state matches the first. Catches
        heap-reuse leaks of the class fixed in tr's
        ``trcomm_profile.f90`` zero-init sweep on 2026-04-20. wr has
        not been audited for the same bug class; this test is the
        first line of defence.

        If this SEGVs or produces NaN the test will fail loudly rather
        than be masked; that is the intent.
        """
        import pytest  # type: ignore[import-not-found]

        # First cycle: init, apply wr_test001 fixture, run.
        srv.handle_init()
        self._apply_fixture()
        srv.handle_run(0)
        s1 = srv.handle_get_state()
        srv.handle_finalize()

        # Second cycle with identical params.
        srv.handle_init()
        self._apply_fixture()
        srv.handle_run(0)
        s2 = srv.handle_get_state()
        srv.handle_finalize()

        # wr state has no CPU-time fields; strict equality.
        if s1 != s2:
            diffs = {k: (s1.get(k), s2.get(k)) for k in set(s1) | set(s2)
                     if s1.get(k) != s2.get(k)}
            pytest.fail(
                "wr reinit cycle produced divergent state (possible "
                f"heap-reuse leak): differing keys = {sorted(diffs)}"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
