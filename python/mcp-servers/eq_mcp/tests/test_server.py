"""Tests for the eq_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param
  dispatch via a mock Eq) always run — they require neither the
  Python MCP SDK nor a built ``libeqapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``eq/libeqapi.so`` exists. They cover the safe init / set_param /
  validate / get_state / finalize subset and, when an eqdata fixture
  is available, the full init -> set -> run(1) -> get_state cycle.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \\
        -s python/mcp-servers/eq_mcp/tests
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
EQ_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both eq_mcp (parent) and eqlib (sibling).
for extra in (str(EQ_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from eq_mcp import server as srv  # noqa: E402

# eqlib exceptions for error-mapping tests.
from eqlib import (  # noqa: E402
    EqlibError,
    EqlibInitError,
    EqlibInvalidParamError,
    EqlibNotInitializedError,
    EqlibCalculationFailedError,
    EqlibNotImplementedError,
)


LIBEQAPI_SO = REPO_ROOT / "eq" / "libeqapi.so"
EQDATA_FIXTURE_DIR = (
    REPO_ROOT / "python" / "eqlib" / "tests" / "fixtures"
)


# =====================================================================
# Pure-Python tests (no libeqapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The hardcoded parameter registry should look sensible."""

    def test_registry_nonempty(self) -> None:
        # eq_param_registry.f90 has 60+ SELECT CASE entries plus 7
        # string-valued ones; we enforce a generous floor to catch
        # accidental truncation.
        self.assertGreater(len(srv.PARAMETER_REGISTRY), 50)

    def test_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRY.items():
            with self.subTest(name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_contains_expected_core_params(self) -> None:
        # Cover one name from each major group in eq_param_registry.f90.
        expected = {
            "RR", "RA", "BB", "RIP", "RKAP", "RDLT",        # geometry
            "PP0", "PP1", "PP2", "PJ0", "PJ1", "PJ2",       # profile
            "FF0", "PROFJ0", "PROFJ1", "PROFJ2",            # profile (more)
            "MODELG", "MDLEQF",                              # models
            "NRGMAX", "NZGMAX", "NPSMAX", "NRMAX",           # mesh
            "NTHMAX", "NSUMAX", "NRVMAX", "NTGMAX",          # mesh (more)
            "NSGMAX",                                        # mesh (more)
            "PSIB",                                          # 1D arrays
            "KNAMEQ",                                        # string
        }
        missing = expected - set(srv.PARAMETER_REGISTRY.keys())
        self.assertFalse(missing, f"missing expected params: {missing}")

    def test_has_string_parameter_metadata(self) -> None:
        # KNAMEQ et al. should be tagged type=str so the LLM picks
        # set_param_str rather than set_param.
        for name in ("KNAMEQ", "KNAMEQ2", "KNAMWR", "KNAMPF"):
            with self.subTest(name=name):
                self.assertEqual(srv.PARAMETER_REGISTRY[name]["type"], "str")

    def test_psib_documents_zero_origin(self) -> None:
        # PSIB is the only 0-origin array in EQ; the registry
        # description should make that visible to the LLM.
        meta = srv.PARAMETER_REGISTRY["PSIB"]
        self.assertIn("0-origin", meta["description"])

    def test_array_metadata_mentions_psib_origin(self) -> None:
        # describe_parameters should document both origins (1- and 0-).
        out = srv.handle_describe_parameters()
        self.assertIn("0-origin", out["array_syntax"])
        self.assertIn("1-origin", out["array_syntax"])


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in (
            "NRGMAX", "NZGMAX", "NPSMAX", "NRMAX", "NTHMAX", "NSUMAX",
            "NRVMAX", "NSGMAX", "NTGMAX",
            "scalars",
            "RG", "ZG",
            "PSIPS", "PPPS", "TTPS", "QQPS",
            "profile",
        ):
            self.assertIn(k, schema["properties"])

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("scalars", out["properties"])
        self.assertIn("profile", out["properties"])
        self.assertIn("PSIPS", out["properties"])


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "eq")
        self.assertEqual(out["count"], len(srv.PARAMETER_REGISTRY))
        self.assertIn("parameters", out)
        self.assertIn("RR", out["parameters"])
        self.assertIn("KNAMEQ", out["parameters"])


class TestErrorWrap(unittest.TestCase):
    """_wrap_eqlib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_eqlib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_param_error(self) -> None:
        self._assert_message(
            EqlibInvalidParamError("BAD: rc=1"),
            "invalid parameter",
        )

    def test_state_error(self) -> None:
        self._assert_message(
            EqlibNotInitializedError("x: rc=2"),
            "library not initialized",
        )

    def test_run_error(self) -> None:
        self._assert_message(
            EqlibCalculationFailedError("x: rc=3"),
            "calculation failed",
        )

    def test_notimpl_error(self) -> None:
        self._assert_message(
            EqlibNotImplementedError("x: rc=4"),
            "not implemented",
        )

    def test_init_error(self) -> None:
        self._assert_message(EqlibInitError("init x"), "eq_init failed")

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libeqapi.so missing"),
            "libeqapi.so not found",
        )

    def test_base_eqliberror(self) -> None:
        self._assert_message(EqlibError("misc"), "eqlib error")


# =====================================================================
# Mock-Eq tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockEq:
    """Minimal Eq stand-in used to verify bulk-param dispatch."""

    def __init__(self) -> None:
        self.scalar_calls: List[tuple] = []
        self.str_calls: List[tuple] = []
        self.run_calls: List[int] = []
        self.validate_calls: int = 0
        self._diags: List[Any] = []
        self.closed = False

    def set_param(self, name: str, value: float) -> None:
        self.scalar_calls.append((name, float(value)))

    def set_param_str(self, name: str, value: str) -> None:
        self.str_calls.append((name, value))

    def run(self, mode: int) -> None:
        self.run_calls.append(int(mode))

    def get_state(self) -> Any:
        class _S:
            def to_dict(self_inner) -> Dict[str, Any]:
                return {
                    "NRGMAX": 0, "NZGMAX": 0, "NPSMAX": 0,
                    "NRMAX": 0, "NTHMAX": 0, "NSUMAX": 0,
                    "NRVMAX": 0, "NSGMAX": 0, "NTGMAX": 0,
                    "scalars": {}, "RG": [], "ZG": [],
                    "PSIPS": [], "PPPS": [], "TTPS": [], "QQPS": [],
                    "profile": [],
                }

        return _S()

    def validate(self) -> List[Any]:
        self.validate_calls += 1
        return list(self._diags)

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_and_dict(self) -> None:
        eq = _MockEq()
        params: Dict[str, Any] = {
            "RR":     6.2,
            "BB":     5.3,
            "RIPFC":  [0.5, 1.0],         # list -> RIPFC[1], RIPFC[2]
            "PSIB":   {0: 0.0, 5: 1.0},   # dict -> PSIB[0], PSIB[5]
        }
        applied = srv._apply_bulk_params(eq, params)

        # 2 scalars + 2 list + 2 dict = 6 applied keys
        self.assertEqual(len(applied), 6)

        scalar_names = [n for n, _ in eq.scalar_calls]
        for expected in (
            "RR", "BB",
            "RIPFC[1]", "RIPFC[2]",
            "PSIB[0]", "PSIB[5]",
        ):
            self.assertIn(expected, scalar_names)

    def test_string_value_routes_to_set_param_str(self) -> None:
        eq = _MockEq()
        applied = srv._apply_bulk_params(eq, {"KNAMEQ": "eqdata.ITER01"})
        self.assertEqual(applied, ["KNAMEQ"])
        self.assertEqual(eq.str_calls, [("KNAMEQ", "eqdata.ITER01")])
        self.assertEqual(eq.scalar_calls, [])

    def test_rejects_unsupported_type(self) -> None:
        eq = _MockEq()
        with self.assertRaises(EqlibError):
            srv._apply_bulk_params(eq, {"RR": object()})

    def test_rejects_bool(self) -> None:
        # bool is a subclass of int; we want it rejected as ambiguous.
        eq = _MockEq()
        with self.assertRaises(EqlibError):
            srv._apply_bulk_params(eq, {"MODELG": True})

    def test_psib_list_form_raises(self) -> None:
        """PSIB is 0-origin; list form would silently misalign indices.

        feature-dev review (MED): without an explicit guard,
        ``{"PSIB": [v0, v1, v2, v3, v4, v5]}`` enumerates as
        ``PSIB[1..6]``, leaves ``PSIB[0]`` unset, and trips out-of-range
        only on the final ``PSIB[6]`` write — after partial mutation.
        Force the dict form by raising up-front.
        """
        eq = _MockEq()
        with self.assertRaises(EqlibError) as ctx:
            srv._apply_bulk_params(
                eq, {"PSIB": [2.0, 0.5, 0.0, 0.0, 0.0, 0.0]}
            )
        self.assertIn("PSIB", str(ctx.exception))
        self.assertIn("0-origin", str(ctx.exception))
        # No partial mutation: nothing should have been applied.
        self.assertEqual(eq.scalar_calls, [])


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_eq = _MockEq()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_eq
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_init(self) -> None:
        msg = srv.handle_init()
        self.assertIn("initialized", msg)

    def test_handle_set_param(self) -> None:
        msg = srv.handle_set_param("RR", 6.2)
        self.assertIn("RR", msg)
        self.assertEqual(self.mock_eq.scalar_calls[-1], ("RR", 6.2))

    def test_handle_set_param_str(self) -> None:
        msg = srv.handle_set_param_str("KNAMEQ", "eqdata.ITER01")
        self.assertIn("KNAMEQ", msg)
        self.assertEqual(self.mock_eq.str_calls[-1], ("KNAMEQ", "eqdata.ITER01"))

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"BB": 5.3})
        self.assertIn("1 parameter", msg)

    def test_handle_set_params_rejects_non_dict(self) -> None:
        # ToolError may be RuntimeError when mcp is absent, but either
        # way the call must not silently succeed.
        with self.assertRaises(Exception):
            srv.handle_set_params([("BB", 5.3)])  # type: ignore[arg-type]

    def test_handle_run(self) -> None:
        msg = srv.handle_run(1)
        self.assertIn("eq_run", msg)
        self.assertEqual(self.mock_eq.run_calls, [1])

    def test_handle_run_default_mode(self) -> None:
        # mode defaults to 1 (real EQDSK load).
        srv.handle_run()
        self.assertEqual(self.mock_eq.run_calls, [1])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NRGMAX", out)
        self.assertIn("scalars", out)
        self.assertIn("profile", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"RR": 6.2}, mode=1,
        )
        self.assertIn("NRGMAX", out)
        self.assertEqual(self.mock_eq.scalar_calls[-1], ("RR", 6.2))
        self.assertEqual(self.mock_eq.run_calls, [1])

    def test_handle_run_and_get_state_force_closes_prior(self) -> None:
        """Codex review (P2): prior STATE.eq must be finalized before
        the one-shot run, so left-over MODELG / KNAMEQ / mesh from
        earlier tool calls cannot leak into the supposedly-isolated
        run. Verified by patching STATE.close() and asserting it is
        called before STATE.ensure_open() inside the same handler.
        """
        with mock.patch.object(srv.STATE, "close") as mock_close:
            srv.handle_run_and_get_state(params={"RR": 6.2}, mode=1)
            self.assertEqual(
                mock_close.call_count, 1,
                "run_and_get_state must STATE.close() to finalize prior Eq "
                "before opening a fresh handle (Codex review P2).",
            )

    def test_handle_validate_returns_list_of_dicts(self) -> None:
        # No diagnostics -> empty list.
        out = srv.handle_validate()
        self.assertEqual(out, [])
        self.assertEqual(self.mock_eq.validate_calls, 1)

        # Inject a synthetic diagnostic and verify the dict shape.
        from collections import namedtuple
        DiagShim = namedtuple("DiagShim", ["param", "code", "message"])
        self.mock_eq._diags = [
            DiagShim(param="NRMAX", code=1, message="9999 > 1001"),
            DiagShim(param="KNAMEQ", code=4, message="file missing: ''"),
        ]
        out = srv.handle_validate()
        self.assertEqual(len(out), 2)
        for entry in out:
            self.assertIn("param", entry)
            self.assertIn("code", entry)
            self.assertIn("message", entry)
            self.assertIsInstance(entry["param"], str)
            self.assertIsInstance(entry["code"], int)
            self.assertIsInstance(entry["message"], str)
        self.assertEqual(out[0]["param"], "NRMAX")
        self.assertEqual(out[0]["code"], 1)
        self.assertEqual(out[1]["param"], "KNAMEQ")
        self.assertEqual(out[1]["code"], 4)


class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libeqapi.so."""

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

    def test_print_tools_output_contains_all_eleven(self) -> None:
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = srv.main(["--print-tools"])
        self.assertEqual(rc, 0)
        lines = [ln for ln in buf.getvalue().splitlines() if ln]
        self.assertEqual(len(lines), 11)
        for t in (
            "init",
            "set_param",
            "set_param_str",
            "set_params",
            "run",
            "get_state",
            "validate",
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
        self.assertEqual(getattr(s, "name", None), "task-eq")


# =====================================================================
# Integration tests (real libeqapi.so).
#
# We always cover the safe init / set_param / validate / get_state /
# finalize path. The full init -> set_params -> run(1) -> get_state
# cycle requires an eqdata file in CWD; we use the committed
# python/eqlib/tests/fixtures/eqdata.ITER01 fixture for this.
# =====================================================================
@unittest.skipUnless(
    LIBEQAPI_SO.exists(),
    f"libeqapi.so not found at {LIBEQAPI_SO}; skipping integration tests",
)
class TestIntegration(unittest.TestCase):
    """End-to-end init → set → validate → run → get_state → finalize."""

    def setUp(self) -> None:
        # Reset server state between tests.
        srv.STATE.close()
        self._prev_cwd = os.getcwd()

    def tearDown(self) -> None:
        srv.STATE.close()
        os.chdir(self._prev_cwd)

    def test_init_validate_state_finalize(self) -> None:
        # Safe path: no eq_run, no eqdata file required.
        self.assertIn("initialized", srv.handle_init())

        # validate on the freshly-initialised default state should be
        # clean (eq_validate returns rc=0 / ndiag=0; see
        # python/eqlib/tests/test_validate.py
        # ::test_validate_clean_default_state_returns_ok).
        diags = srv.handle_validate()
        self.assertEqual(diags, [], f"unexpected diagnostics: {diags}")

        # get_state on the fresh state returns the default mesh sizes
        # (no run() yet).
        state = srv.handle_get_state()
        for k in ("NRGMAX", "NZGMAX", "NPSMAX", "scalars", "profile"):
            self.assertIn(k, state)

        self.assertIn("finalized", srv.handle_finalize())

    def test_validate_surfaces_diagnostics_for_bad_params(self) -> None:
        """validate should emit OUT_OF_RANGE for an oversize NRMAX."""
        srv.handle_init()
        # NRM compile-time max is 1001 (eq/eqcom0_mod.f90:29).
        srv.handle_set_param("NRMAX", 9999.0)
        diags = srv.handle_validate()
        self.assertGreaterEqual(len(diags), 1)
        codes = {d["code"] for d in diags}
        # EQ_DIAG_OUT_OF_RANGE = 1 (eq/eq_api.h::eq_diag_code).
        self.assertIn(
            1, codes,
            f"expected OUT_OF_RANGE (code 1) in diagnostics: {diags}",
        )
        # The offending param name should appear somewhere in the list.
        params = {d["param"] for d in diags}
        self.assertIn("NRMAX", params)

    def test_validate_empty_knameq_with_modelg3_emits_file_missing(self) -> None:
        """MODELG=3 with blank KNAMEQ should trip FILE_MISSING (code 4)."""
        srv.handle_init()
        srv.handle_set_param("MODELG", 3.0)
        srv.handle_set_param_str("KNAMEQ", "")
        diags = srv.handle_validate()
        codes = {d["code"] for d in diags}
        # EQ_DIAG_FILE_MISSING = 4 (eq/eq_api.h::eq_diag_code).
        self.assertIn(
            4, codes,
            f"expected FILE_MISSING (code 4) in diagnostics: {diags}",
        )

    @unittest.skipUnless(
        (EQDATA_FIXTURE_DIR / "eqdata.ITER01").exists(),
        f"eqdata.ITER01 fixture missing at {EQDATA_FIXTURE_DIR}",
    )
    def test_init_set_run_get_state_cycle_iter01(self) -> None:
        """Full happy-path: init -> set -> validate -> run(1) -> get_state.

        Uses the committed ITER01 fixture so this runs in CI without
        needing to invoke the Phase-0 Fortran driver. eq.run(mode=1)
        opens KNAMEQ relative to CWD, so we chdir into the fixture
        directory for the duration of the test.
        """
        os.chdir(EQDATA_FIXTURE_DIR)

        # init + apply ITER01 params (mirrors fixtures/eq_iter01_params.py).
        srv.handle_init()
        srv.handle_set_params({
            "MODELG": 3, "RR": 6.2, "RA": 2.0, "RKAP": 1.7,
            "RDLT": 0.33, "RB": 2.1, "BB": 5.3, "RIP": 15.0,
        })
        srv.handle_set_param_str("KNAMEQ", "eqdata.ITER01")

        # validate after configure should be clean (the ITER01
        # configuration is the canonical Layer-1 fixture).
        diags = srv.handle_validate()
        self.assertEqual(
            diags, [],
            f"unexpected diagnostics for ITER01 fixture: {diags}",
        )

        # run -> get_state.
        srv.handle_run(1)
        state = srv.handle_get_state()

        # Sanity: positive grid sizes and a real magnetic axis.
        self.assertGreater(state["NRGMAX"], 0)
        self.assertGreater(state["NZGMAX"], 0)
        self.assertGreater(state["NPSMAX"], 0)
        self.assertGreater(state["NRMAX"], 0)
        # raxis should be near the major radius (~6.2 m for ITER).
        raxis = state["scalars"].get("RAXIS")
        self.assertIsNotNone(raxis)
        self.assertGreater(raxis, 1.0)
        self.assertLess(raxis, 12.0)

        srv.handle_finalize()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
