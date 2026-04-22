"""Tests for the ti_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param
  dispatch via a mock Tilib) always run — they require neither the
  Python MCP SDK nor a built ``libtiapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``ti/libtiapi.so`` exists.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \
        -s python/mcp-servers/ti_mcp/tests
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
TI_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both ti_mcp (parent) and tilib (sibling).
for extra in (str(TI_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from ti_mcp import server as srv  # noqa: E402

# tilib exceptions for error-mapping tests.
from tilib import (  # noqa: E402
    TilibError,
    TilibParamError,
    TilibStateError,
    TilibRunError,
    TilibNotImplementedError,
)


LIBTIAPI_SO = REPO_ROOT / "ti" / "libtiapi.so"


# =====================================================================
# Pure-Python tests (no libtiapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The hardcoded parameter registry should look sensible."""

    def test_registry_nonempty(self) -> None:
        # ti_param_registry.f90 has 50+ SELECT CASE entries; we enforce
        # a generous floor to catch accidental truncation.
        self.assertGreater(len(srv.PARAMETER_REGISTRY), 40)

    def test_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRY.items():
            with self.subTest(name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_contains_expected_core_params(self) -> None:
        expected = {
            "RR", "RA", "BB", "PN", "PT", "NSMAX", "DT", "NTMAX",
            "MODELG", "MODEL_KAI",
        }
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected params: {missing}")

    def test_contains_2d_array_param(self) -> None:
        # MODEL_BND is the canonical 2-D array parameter; make sure
        # users can discover it via describe_parameters.
        self.assertIn("MODEL_BND", srv.PARAMETER_REGISTRY)
        self.assertIn("BND_VALUE", srv.PARAMETER_REGISTRY)


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in ("NT", "NRMAX", "NSA_MAX", "NSMAX", "scalars", "profile"):
            self.assertIn(k, schema["properties"])

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("profile", out["properties"])

    def test_scalars_include_ti_specific_fields(self) -> None:
        # TI surfaces diagnostic scalars that TR does not (loop/mat
        # iteration counters). Int counters live under ``scalars_int``
        # to mirror the Phase-0 baseline JSON grouping (tiregress.f90);
        # real-valued scalars stay under ``scalars``.
        scalars = srv.STATE_SCHEMA["properties"]["scalars"]["properties"]
        for k in ("T", "residual_loop_max"):
            self.assertIn(k, scalars)
        scalars_int = srv.STATE_SCHEMA["properties"]["scalars_int"]["properties"]
        for k in ("icount_loop_max", "icount_mat_max"):
            self.assertIn(k, scalars_int)


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "ti")
        self.assertEqual(out["count"], len(srv.PARAMETER_REGISTRY))
        self.assertIn("parameters", out)
        self.assertIn("RR", out["parameters"])

    def test_describe_parameters_mentions_2d_syntax(self) -> None:
        out = srv.handle_describe_parameters()
        # The LLM needs guidance for MODEL_BND[i,j]; the array_syntax
        # help text should mention the 2-D form.
        self.assertIn("array_syntax", out)
        self.assertIn("[", out["array_syntax"])


class TestErrorWrap(unittest.TestCase):
    """_wrap_tilib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_tilib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_param_error(self) -> None:
        self._assert_message(TilibParamError("BAD: ierr=1"), "invalid parameter")

    def test_state_error(self) -> None:
        self._assert_message(
            TilibStateError("x: ierr=2"),
            "library not initialized",
        )

    def test_run_error(self) -> None:
        self._assert_message(TilibRunError("x: ierr=3"), "calculation failed")

    def test_notimpl_error(self) -> None:
        self._assert_message(
            TilibNotImplementedError("x: ierr=4"),
            "not implemented",
        )

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libtiapi.so missing"),
            "libtiapi.so not found",
        )

    def test_base_tiliberror(self) -> None:
        self._assert_message(TilibError("misc"), "tilib error")


# =====================================================================
# Mock-Tilib tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockTilib:
    """Minimal Tilib stand-in used to verify bulk-param dispatch."""

    def __init__(self) -> None:
        self.scalar_calls: List[tuple] = []
        self.run_calls: List[int] = []
        self.closed = False

    def set_param(self, name: str, value: float) -> None:
        self.scalar_calls.append((name, value))

    def run(self, ntmax: int) -> None:
        self.run_calls.append(int(ntmax))

    def get_state(self) -> Any:
        class _S:
            def to_dict(self_inner) -> Dict[str, Any]:
                return {
                    "NT": 0,
                    "NRMAX": 0,
                    "NSA_MAX": 0,
                    "NSMAX": 0,
                    "scalars": {},
                    "profile": [],
                }

        return _S()

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_and_dict(self) -> None:
        ti = _MockTilib()
        params: Dict[str, Any] = {
            "RR":    3.0,
            "BB":    2.0,
            "PN":    [0.7, 0.7],        # list -> PN[1], PN[2]
            "PT":    {2: 4.2, 1: 3.5},  # dict -> PT[2], PT[1]
        }
        applied = srv._apply_bulk_params(ti, params)

        # 2 scalars + 2 list + 2 dict = 6 applied keys
        self.assertEqual(len(applied), 6)

        scalar_names = [n for n, _ in ti.scalar_calls]
        for expected in ("RR", "BB", "PN[1]", "PN[2]", "PT[1]", "PT[2]"):
            self.assertIn(expected, scalar_names)

    def test_string_rejected(self) -> None:
        # TI has no string-setter on its C ABI, so strings must raise.
        ti = _MockTilib()
        with self.assertRaises(TilibParamError):
            srv._apply_bulk_params(ti, {"KNAMEQ": "eqdata"})

    def test_rejects_unsupported_type(self) -> None:
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(ti, {"RR": object()})

    def test_rejects_bool(self) -> None:
        # bool is a subclass of int; we want it rejected as ambiguous.
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(ti, {"NSMAX": True})

    def test_rejects_bool_in_list(self) -> None:
        # Codex P2 follow-up: nested bool in list must also raise.
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(ti, {"PN": [0.7, True]})

    def test_rejects_bool_in_dict_value(self) -> None:
        # Codex P2 follow-up: bool as dict value must raise.
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(ti, {"PT": {1: True}})

    def test_rejects_bool_dict_index(self) -> None:
        # Codex P2 follow-up: bool key would be int()-coerced to 1.
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(ti, {"PT": {True: 3.5}})

    def test_rejects_non_numeric_string_element(self) -> None:
        # MED-5: float() on a non-numeric list element maps to TilibError.
        ti = _MockTilib()
        with self.assertRaises(TilibError) as ctx:
            srv._apply_bulk_params(ti, {"PN": [0.7, "oops"]})
        self.assertIn("PN[2]", str(ctx.exception))

    def test_rejects_non_int_dict_index(self) -> None:
        # MED-5: int() on a non-numeric index maps to TilibError.
        ti = _MockTilib()
        with self.assertRaises(TilibError) as ctx:
            srv._apply_bulk_params(ti, {"PT": {"not-an-int": 3.5}})
        self.assertIn("PT", str(ctx.exception))

    def test_partial_bulk_mutation_on_failure(self) -> None:
        # LOW-2: on a partial failure, earlier keys remain written.
        # Documented as non-transactional in set_params docstring.
        ti = _MockTilib()
        with self.assertRaises(TilibError):
            srv._apply_bulk_params(
                ti,
                {"RR": 3.0, "BAD": object(), "BB": 2.0},
            )
        scalar_names = [n for n, _ in ti.scalar_calls]
        self.assertIn("RR", scalar_names)
        self.assertNotIn("BB", scalar_names)


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_ti = _MockTilib()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_ti
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_init(self) -> None:
        msg = srv.handle_init()
        self.assertIn("initialized", msg)

    def test_handle_set_param(self) -> None:
        msg = srv.handle_set_param("RR", 3.0)
        self.assertIn("RR", msg)
        self.assertEqual(self.mock_ti.scalar_calls[-1], ("RR", 3.0))

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"BB": 2.0})
        self.assertIn("1 parameter", msg)

    def test_handle_set_params_rejects_non_dict(self) -> None:
        # ToolError may be RuntimeError when mcp is absent, but either
        # way the call must not silently succeed.
        with self.assertRaises(Exception):
            srv.handle_set_params([("BB", 2.0)])  # type: ignore[arg-type]

    def test_handle_run(self) -> None:
        msg = srv.handle_run(3)
        self.assertIn("3", msg)
        self.assertEqual(self.mock_ti.run_calls, [3])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NT", out)
        self.assertIn("scalars", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"RR": 3.2}, ntmax=2,
        )
        self.assertIn("NT", out)
        self.assertEqual(self.mock_ti.scalar_calls[-1], ("RR", 3.2))
        self.assertEqual(self.mock_ti.run_calls, [2])

    def test_handle_run_and_get_state_no_params(self) -> None:
        # Omitting params should still call run and return state.
        out = srv.handle_run_and_get_state(params=None, ntmax=0)
        self.assertIn("NT", out)
        self.assertEqual(self.mock_ti.run_calls, [0])

    def test_handle_run_and_get_state_force_closes_prior(self) -> None:
        """Codex MCP audit 2026-04-22 (HIGH) fix: prior STATE.ti must
        be finalized before the one-shot run, so left-over MODELG /
        mesh / NSMAX / MODEL_BND from earlier tool calls cannot leak
        into the supposedly-isolated run.

        Verified by patching STATE.close() and asserting it is called
        exactly once during handle_run_and_get_state.
        """
        with mock.patch.object(srv.STATE, "close") as mock_close:
            srv.handle_run_and_get_state(params={"RR": 3.2}, ntmax=1)
            self.assertEqual(
                mock_close.call_count, 1,
                "run_and_get_state must STATE.close() to finalize "
                "prior Tilib before opening a fresh handle "
                "(Codex MCP audit 2026-04-22).",
            )


class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libtiapi.so."""

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

    def test_print_tools_output_contains_all_nine(self) -> None:
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = srv.main(["--print-tools"])
        self.assertEqual(rc, 0)
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertEqual(len(lines), 9)
        for t in (
            "init",
            "set_param",
            "set_params",
            "run",
            "get_state",
            "finalize",
            "describe_parameters",
            "describe_state_schema",
            "run_and_get_state",
        ):
            self.assertIn(t, lines)


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
        self.assertEqual(getattr(s, "name", None), "task-ti")


# =====================================================================
# Integration tests (real libtiapi.so).
# =====================================================================
@unittest.skipUnless(
    LIBTIAPI_SO.exists(),
    f"libtiapi.so not found at {LIBTIAPI_SO}; skipping integration tests",
)
class TestIntegration(unittest.TestCase):
    """End-to-end init → run(0) → get_state → finalize against .so."""

    # ti_run / ti_prep read ADPOST/ADF11 data files relative to cwd
    # (see ti/tiadas.f90). Without chdir into a directory containing
    # ``ADF11-bin.data`` the run aborts with ierr=3 at the first
    # OPEN. Reuse the same data dir that the equivalence test uses.
    _DATA_CWD = Path(__file__).resolve().parents[4] / "test_run" / "test_output" / "ti_min"

    def setUp(self) -> None:
        # Reset server state between tests.
        srv.STATE.close()
        self._prev_cwd = os.getcwd()
        if not self._DATA_CWD.exists():
            self.skipTest(
                f"ti_mcp data fixture not found at {self._DATA_CWD}; "
                "run `bash test_run/run_tests.sh` to generate it."
            )
        os.chdir(self._DATA_CWD)

    def tearDown(self) -> None:
        srv.STATE.close()
        os.chdir(self._prev_cwd)

    # ti_run(0) requires a minimally-configured TICOMM (ti_init alone
    # leaves NSMAX/NRMAX etc. at defaults that ti_prep rejects with
    # ierr=3 = CALC_FAILED). Use the ti_min fixture's parameters --
    # the same shape that the libtilib equivalence test uses.
    _MIN_PARAMS = {
        "NSMAX":   1,
        "NRMAX":   10,
        "NTSTEP":  1,
        "NGTSTEP": 1,
        "NGRSTEP": 1,
        "NTMAX":   2,
    }

    def _set_min_params(self) -> None:
        for k, v in self._MIN_PARAMS.items():
            srv.handle_set_param(k, float(v))

    def test_init_run_state_finalize(self) -> None:
        self.assertIn("initialized", srv.handle_init())
        self._set_min_params()
        self.assertIn("0", srv.handle_run(0))
        state = srv.handle_get_state()
        self.assertIn("NT", state)
        self.assertIn("scalars", state)
        self.assertIn("finalized", srv.handle_finalize())

    def test_run_and_get_state_oneshot(self) -> None:
        out = srv.handle_run_and_get_state(params=self._MIN_PARAMS, ntmax=0)
        self.assertIn("NT", out)
        self.assertIsInstance(out["scalars"], dict)

    def test_reinit_cycle_reproducible(self) -> None:
        """init -> set_min_params -> run(0) -> get_state -> finalize, twice.

        Asserts the second cycle's state matches the first. Catches
        heap-reuse leaks of the class fixed in tr's
        ``trcomm_profile.f90`` zero-init sweep on 2026-04-20. ti got a
        SAVE-guard fix today but has not been audited end-to-end for
        the zero-init class of bug; this test is the guard.

        If this SEGVs or produces NaN the test will fail loudly rather
        than be masked; that is the intent.
        """

        # First cycle. Mirror the existing TestIntegration ordering
        # (init first, then set_min_params) so the docstring's
        # ``init -> set_min_params -> run(0)`` sequence matches the code
        # and matches ``test_init_run_state_finalize``.
        srv.handle_init()
        self._set_min_params()
        srv.handle_run(0)
        s1 = srv.handle_get_state()
        srv.handle_finalize()

        # Second cycle with identical params.
        srv.handle_init()
        self._set_min_params()
        srv.handle_run(0)
        s2 = srv.handle_get_state()
        srv.handle_finalize()

        # ti state has no CPU-time fields; use strict equality.
        if s1 != s2:
            diffs = {k: (s1.get(k), s2.get(k)) for k in set(s1) | set(s2)
                     if s1.get(k) != s2.get(k)}
            self.fail(
                "ti reinit cycle produced divergent state (possible "
                f"heap-reuse leak): differing keys = {sorted(diffs)}"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
