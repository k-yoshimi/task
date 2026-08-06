"""Tests for the fp_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param
  dispatch via a mock Fplib) always run — they require neither the
  Python MCP SDK nor a built ``libfpapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``fp/libfpapi.so`` exists.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \
        -s python/mcp-servers/fp_mcp/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
FP_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both fp_mcp (parent) and fplib (sibling).
for extra in (str(FP_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from fp_mcp import server as srv  # noqa: E402

# fplib exceptions for error-mapping tests.
from fplib import (  # noqa: E402
    FplibError,
    FplibInitError,
    FplibInvalidParamError,
    FplibNotInitError,
    FplibCalcFailedError,
    FplibNotImplementedError,
)


LIBFPAPI_SO = REPO_ROOT / "fp" / "libfpapi.so"


# =====================================================================
# Pure-Python tests (no libfpapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The hardcoded parameter registry should look sensible."""

    def test_registry_nonempty(self) -> None:
        # fp_param_registry.f90 covers ~40 unique base names.
        self.assertGreaterEqual(len(srv.PARAMETER_REGISTRY), 40)

    def test_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRY.items():
            with self.subTest(name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_contains_expected_core_params(self) -> None:
        expected = {
            "RR", "RA", "BB", "RIP",
            "NRMAX", "NPMAX", "NTHMAX", "NTMAX",
            "NSMAX", "NSAMAX", "NSBMAX",
            "PA", "PZ", "PN", "PNS",
            "DELT", "EPSFP", "LMAXFP",
            "MODELG", "MODELE",
        }
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected params: {missing}")

    def test_contains_wave_heating_group(self) -> None:
        wave_keys = {
            name for name, meta in srv.PARAMETER_REGISTRY.items()
            if meta["group"] == "wave"
        }
        expected = {"PABS_EC", "PABS_LH", "PABS_FW", "PABS_WR", "PABS_WM", "RF_WM"}
        self.assertTrue(
            expected.issubset(wave_keys),
            f"wave group missing: {expected - wave_keys}",
        )

    def test_model_switches_present(self) -> None:
        for name in ("MODEL_NBI", "MODEL_WAVE", "MODEL_BS", "MODEL_FOW"):
            self.assertIn(name, srv.PARAMETER_REGISTRY)


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in ("NRMAX", "NSAMAX", "NPMAX", "NTHMAX", "NTG2", "TIMEFP",
                  "scalars", "profile"):
            self.assertIn(k, schema["properties"])

    def test_profile_items_cover_all_2d_fields(self) -> None:
        items = srv.STATE_SCHEMA["properties"]["profile"]["items"]
        props = items["properties"]
        for field in ("NSA", "RNT", "RWT", "RTT", "RJT", "RPCT", "RPWT"):
            self.assertIn(field, props)

    def test_scalars_cover_all_global_fields(self) -> None:
        """The schema must document every field fplib actually emits."""
        from fplib.state import SCALAR_FIELDS

        props = srv.STATE_SCHEMA["properties"]["scalars"]["properties"]
        self.assertEqual(sorted(props), sorted(SCALAR_FIELDS))

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("profile", out["properties"])


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "fp")
        self.assertEqual(out["count"], len(srv.PARAMETER_REGISTRY))
        self.assertIn("parameters", out)
        self.assertIn("RR", out["parameters"])

    def test_describe_parameters_exposes_mesh_caps(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertIn("caps", out)
        self.assertEqual(out["caps"]["FP_MAX_NSAMAX"], 8)
        self.assertEqual(out["caps"]["FP_MAX_NRMAX"], 100)


class TestErrorWrap(unittest.TestCase):
    """_wrap_fplib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_fplib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_invalid_param_error(self) -> None:
        self._assert_message(
            FplibInvalidParamError("BAD: rc=1"),
            "invalid parameter",
        )

    def test_not_init_error(self) -> None:
        self._assert_message(
            FplibNotInitError("x: rc=2"),
            "library not initialized",
        )

    def test_calc_failed_error(self) -> None:
        self._assert_message(
            FplibCalcFailedError("x: rc=3"),
            "calculation failed",
        )

    def test_notimpl_error(self) -> None:
        self._assert_message(
            FplibNotImplementedError("x: rc=4"),
            "not implemented",
        )

    def test_init_error(self) -> None:
        self._assert_message(FplibInitError("x"), "fp_init failed")

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libfpapi.so missing"),
            "libfpapi.so not found",
        )

    def test_base_fpliberror(self) -> None:
        self._assert_message(FplibError("misc"), "fplib error")


# =====================================================================
# Mock-Fplib tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockFplib:
    """Minimal Fplib stand-in used to verify bulk-param dispatch."""

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
                    "NRMAX": 0, "NSAMAX": 0, "NPMAX": 0,
                    "NTHMAX": 0, "NTG2": 0, "TIMEFP": 0.0,
                    "scalars": {}, "profile": [],
                }

        return _S()

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_and_dict(self) -> None:
        fp = _MockFplib()
        params: Dict[str, Any] = {
            "RR":   6.5,
            "BB":   5.3,
            "PA":   [1.0, 2.0, 12.0],    # list -> PA[1], PA[2], PA[3]
            "PN":   {2: 0.4, 1: 0.8},     # dict -> PN[2], PN[1]
            "MODELG": 3,
        }
        applied = srv._apply_bulk_params(fp, params)

        # 2 scalars + 3 list + 2 dict + 1 scalar(MODELG) = 8 applied keys
        self.assertEqual(len(applied), 8)

        # scalar_calls should cover all numeric sets
        scalar_names = [n for n, _ in fp.scalar_calls]
        for expected in (
            "RR", "BB", "MODELG",
            "PA[1]", "PA[2]", "PA[3]",
            "PN[1]", "PN[2]",
        ):
            self.assertIn(expected, scalar_names)

    def test_rejects_unsupported_type(self) -> None:
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"RR": object()})

    def test_rejects_string_value(self) -> None:
        """fplib has no set_param_str: strings are unsupported."""
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"KNAMFP": "path.in"})

    def test_rejects_bool(self) -> None:
        # bool is a subclass of int; we want it rejected as ambiguous.
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"MODELG": True})

    def test_rejects_bool_in_list(self) -> None:
        # Codex P2 follow-up: nested bool in list must also raise.
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"PA": [1.0, True]})

    def test_rejects_bool_in_dict_value(self) -> None:
        # Codex P2 follow-up: bool as dict value must raise.
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"PN": {1: True}})

    def test_rejects_bool_dict_index(self) -> None:
        # Codex P2 follow-up: bool key would be int()-coerced to 1.
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(fp, {"PN": {True: 0.5}})

    def test_rejects_non_numeric_string_element(self) -> None:
        # MED-5: float() on a non-numeric list element maps to FplibError.
        fp = _MockFplib()
        with self.assertRaises(FplibError) as ctx:
            srv._apply_bulk_params(fp, {"PA": [1.0, "oops"]})
        self.assertIn("PA[2]", str(ctx.exception))

    def test_rejects_non_int_dict_index(self) -> None:
        # MED-5: int() on a non-numeric index maps to FplibError.
        fp = _MockFplib()
        with self.assertRaises(FplibError) as ctx:
            srv._apply_bulk_params(fp, {"PN": {"bad": 0.4}})
        self.assertIn("PN", str(ctx.exception))

    def test_partial_bulk_mutation_on_failure(self) -> None:
        # LOW-2: on a partial failure, earlier keys remain written.
        # Documented as non-transactional in set_params docstring.
        fp = _MockFplib()
        with self.assertRaises(FplibError):
            srv._apply_bulk_params(
                fp,
                {"RR": 6.5, "BAD": object(), "BB": 5.3},
            )
        scalar_names = [n for n, _ in fp.scalar_calls]
        self.assertIn("RR", scalar_names)
        self.assertNotIn("BB", scalar_names)


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_fp = _MockFplib()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_fp
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_set_param(self) -> None:
        msg = srv.handle_set_param("RR", 6.5)
        self.assertIn("RR", msg)
        self.assertEqual(self.mock_fp.scalar_calls[-1], ("RR", 6.5))

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"BB": 5.3})
        self.assertIn("1 parameter", msg)

    def test_handle_set_params_rejects_non_dict(self) -> None:
        with self.assertRaises(Exception):
            srv.handle_set_params(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_handle_run(self) -> None:
        msg = srv.handle_run(3)
        self.assertIn("3", msg)
        self.assertEqual(self.mock_fp.run_calls, [3])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NRMAX", out)
        self.assertIn("profile", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"RR": 7.0}, ntmax=2,
        )
        self.assertIn("NRMAX", out)
        self.assertEqual(self.mock_fp.scalar_calls[-1], ("RR", 7.0))
        self.assertEqual(self.mock_fp.run_calls, [2])

    def test_handle_run_and_get_state_no_params(self) -> None:
        out = srv.handle_run_and_get_state(params=None, ntmax=0)
        self.assertIn("NRMAX", out)
        self.assertEqual(self.mock_fp.run_calls, [0])

    def test_handle_run_and_get_state_force_closes_prior(self) -> None:
        """Codex MCP audit 2026-04-22 (HIGH) fix: prior STATE.fp must
        be finalized before the one-shot run, so left-over NSMAX /
        NRMAX / mesh sizes from earlier tool calls cannot leak into
        the supposedly-isolated run.

        Verified by patching STATE.close() and asserting it is called
        exactly once during handle_run_and_get_state.
        """
        with mock.patch.object(srv.STATE, "close") as mock_close:
            srv.handle_run_and_get_state(params={"RR": 7.0}, ntmax=1)
            self.assertEqual(
                mock_close.call_count, 1,
                "run_and_get_state must STATE.close() to finalize "
                "prior Fplib before opening a fresh handle "
                "(Codex MCP audit 2026-04-22).",
            )


class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libfpapi.so."""

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

    def test_print_tools_lists_nine(self) -> None:
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = srv.main(["--print-tools"])
        self.assertEqual(rc, 0)
        lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 9)
        # A handful of expected entries
        for name in ("init", "run", "get_state", "run_and_get_state"):
            self.assertIn(name, lines)


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
        self.assertEqual(getattr(s, "name", None), "task-fp")


# =====================================================================
# Integration tests (real libfpapi.so).
# =====================================================================
@unittest.skipUnless(
    LIBFPAPI_SO.exists(),
    f"libfpapi.so not found at {LIBFPAPI_SO}; skipping integration tests",
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
        self.assertIn("NRMAX", state)
        self.assertIn("profile", state)
        self.assertIn("finalized", srv.handle_finalize())

    def test_run_and_get_state_oneshot(self) -> None:
        out = srv.handle_run_and_get_state(params=None, ntmax=0)
        self.assertIn("NRMAX", out)
        self.assertIsInstance(out["profile"], list)

    def test_reinit_cycle_reproducible(self) -> None:
        """init -> run(0) -> get_state -> finalize, twice.

        Asserts the second cycle's state matches the first. Catches
        heap-reuse leaks of the class fixed in tr's
        ``trcomm_profile.f90`` zero-init sweep on 2026-04-20 -- fp has
        not yet been audited for the same bug class so this test is
        the first line of defence.

        If this SEGVs or produces NaN the test will fail loudly rather
        than be masked; that is the intent.
        """

        # First cycle: default init, no params.
        srv.handle_init()
        srv.handle_run(0)
        s1 = srv.handle_get_state()
        srv.handle_finalize()

        # Second cycle with identical params.
        srv.handle_init()
        srv.handle_run(0)
        s2 = srv.handle_get_state()
        srv.handle_finalize()

        # fp state has no CPU-time fields (TIMEFP is reset to 0 in
        # fpprep.f90 so it matches across cycles). Strict equality.
        if s1 != s2:
            diffs = {k: (s1.get(k), s2.get(k)) for k in set(s1) | set(s2)
                     if s1.get(k) != s2.get(k)}
            self.fail(
                "fp reinit cycle produced divergent state (possible "
                f"heap-reuse leak): differing keys = {sorted(diffs)}"
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
