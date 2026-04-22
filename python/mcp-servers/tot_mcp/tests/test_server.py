"""Tests for the tot_mcp FastMCP server.

The suite is structured so that:

* Pure-Python tests (registry shape, error mapping, bulk-param dispatch
  via a mock Tot, namespace-prefix guard) always run — they require
  neither the Python MCP SDK nor a built ``libtotapi.so``.
* Integration tests (`TestIntegration`) run only when
  ``tot/libtotapi.so`` exists.
* FastMCP construction tests (`TestBuildServer`) run only when the
  ``mcp`` SDK is importable.

Run from the repo root::

    python3 -m unittest discover -v \
        -s python/mcp-servers/tot_mcp/tests
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

HERE = Path(__file__).resolve()
TOT_MCP_ROOT = HERE.parents[1]
PYTHON_ROOT = HERE.parents[3]  # .../python
REPO_ROOT = HERE.parents[4]    # repo root

# Ensure we can import both tot_mcp (parent) and totlib (sibling).
for extra in (str(TOT_MCP_ROOT.parent), str(PYTHON_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from tot_mcp import server as srv  # noqa: E402

# totlib exceptions for error-mapping tests.
from totlib import (  # noqa: E402
    TotlibError,
    TotlibInitError,
    TotlibInvalidParamError,
    TotlibNotInitializedError,
    TotlibCalculationFailedError,
    TotlibNotImplementedError,
)
from totlib._ffi import TOT_NAMESPACES  # noqa: E402


LIBTOTAPI_SO = REPO_ROOT / "tot" / "libtotapi.so"


# =====================================================================
# Pure-Python tests (no libtotapi.so, no mcp SDK required).
# =====================================================================
class TestRegistryShape(unittest.TestCase):
    """The per-namespace registries should look sensible."""

    def test_registries_dict_keyed_by_namespace(self) -> None:
        self.assertIsInstance(srv.PARAMETER_REGISTRIES, dict)
        # All six namespaces are present (even if empty), in addition
        # to the `wr` alias of `wrx`.
        for ns in TOT_NAMESPACES:
            self.assertIn(ns, srv.PARAMETER_REGISTRIES)

    def test_eq_inline_registry_nonempty(self) -> None:
        # eq has no eq_mcp sibling yet, so we ship an inline list.
        self.assertGreater(len(srv.PARAMETER_REGISTRIES["eq"]), 10)

    def test_eq_entries_have_required_keys(self) -> None:
        for name, meta in srv.PARAMETER_REGISTRIES["eq"].items():
            with self.subTest(ns="eq", name=name):
                self.assertIn("type", meta)
                self.assertIn("group", meta)
                self.assertIn("description", meta)
                self.assertIsInstance(meta["type"], str)

    def test_eq_contains_expected_core_params(self) -> None:
        expected = {"RR", "RA", "BB", "RIP", "MODELG", "KNAMEQ"}
        missing = expected - set(srv.PARAMETER_REGISTRIES["eq"].keys())
        self.assertFalse(missing, f"missing expected eq params: {missing}")

    def test_wr_is_alias_of_wrx(self) -> None:
        # Either both populated identically (sibling installed), or
        # both empty (sibling not installed). Either way they must
        # match — the Fortran dispatcher treats them as the same.
        self.assertEqual(
            srv.PARAMETER_REGISTRIES["wr"],
            srv.PARAMETER_REGISTRIES["wrx"],
        )

    def test_flat_count_matches_sum(self) -> None:
        total = sum(len(v) for v in srv.PARAMETER_REGISTRIES.values())
        self.assertEqual(srv._flat_count(), total)


class TestStateSchema(unittest.TestCase):
    def test_schema_top_level(self) -> None:
        schema = srv.STATE_SCHEMA
        self.assertEqual(schema["type"], "object")
        for k in ("presence", "NT", "NRMAX", "NSMAX", "scalars", "profile"):
            self.assertIn(k, schema["properties"])

    def test_presence_has_per_module_flags(self) -> None:
        presence = srv.STATE_SCHEMA["properties"]["presence"]
        for mod in ("tr", "ti", "fp", "wr"):
            self.assertIn(mod, presence["properties"])

    def test_describe_state_schema_tool(self) -> None:
        out = srv.handle_describe_state_schema()
        self.assertEqual(out["type"], "object")
        self.assertIn("profile", out["properties"])
        self.assertIn("presence", out["properties"])


class TestDescribeParameters(unittest.TestCase):
    def test_describe_parameters_tool_shape(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["module"], "tot")
        self.assertIn("namespaces", out)
        self.assertIn("name_syntax", out)
        self.assertIn("parameters", out)
        # Every supported namespace should appear.
        for ns in TOT_NAMESPACES:
            self.assertIn(ns, out["parameters"])

    def test_describe_parameters_count_matches(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertEqual(out["count"], srv._flat_count())

    def test_describe_parameters_eq_has_RR(self) -> None:
        out = srv.handle_describe_parameters()
        self.assertIn("RR", out["parameters"]["eq"])


class TestErrorWrap(unittest.TestCase):
    """_wrap_totlib_error converts library exceptions to ToolError."""

    def _assert_message(self, exc: Exception, substr: str) -> None:
        wrapped = srv._wrap_totlib_error(exc)
        # Either ToolError or RuntimeError (when mcp is absent). Either
        # way the message should carry the expected substring.
        self.assertIn(substr, str(wrapped))

    def test_invalid_param_error(self) -> None:
        self._assert_message(
            TotlibInvalidParamError("BAD: rc=1"),
            "invalid parameter",
        )

    def test_invalid_param_error_includes_namespace_hint(self) -> None:
        wrapped = srv._wrap_totlib_error(
            TotlibInvalidParamError("missing prefix"),
        )
        # The hint should remind the LLM about namespace prefixes.
        self.assertIn("ns", str(wrapped))

    def test_not_initialized_error(self) -> None:
        self._assert_message(
            TotlibNotInitializedError("x: rc=2"),
            "library not initialized",
        )

    def test_calc_failed_error(self) -> None:
        self._assert_message(
            TotlibCalculationFailedError("x: rc=3"),
            "calculation failed",
        )

    def test_not_implemented_error(self) -> None:
        self._assert_message(
            TotlibNotImplementedError("x: rc=4"),
            "not implemented",
        )

    def test_init_error(self) -> None:
        self._assert_message(TotlibInitError("misc"), "tot_init failed")

    def test_filenotfound(self) -> None:
        self._assert_message(
            FileNotFoundError("libtotapi.so missing"),
            "libtotapi.so not found",
        )

    def test_base_totliberror(self) -> None:
        self._assert_message(TotlibError("misc"), "totlib error")


# =====================================================================
# Mock-Tot tests: exercise tool dispatch without the shared library.
# =====================================================================
class _MockTot:
    """Minimal Tot stand-in used to verify bulk-param dispatch."""

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
                    "presence": {"tr": 0, "ti": 0, "fp": 0, "wr": 0},
                    "NT": 0, "NRMAX": 0, "NSMAX": 0,
                    "scalars": {}, "profile": [],
                }

        return _S()

    def close(self) -> None:
        self.closed = True


class TestBulkParamDispatch(unittest.TestCase):
    def test_scalar_list_dict_and_string(self) -> None:
        tot = _MockTot()
        params: Dict[str, Any] = {
            "eq:RR":      6.5,
            "eq:BB":      5.3,
            "tr:PN":      [0.7, 0.7],            # list -> tr:PN[1], tr:PN[2]
            "tr:PT":      {2: 4.2, 1: 3.5},      # dict -> tr:PT[2], tr:PT[1]
            "eq:KNAMEQ":  "eqdata.ITER01",       # string path
        }
        applied = srv._apply_bulk_params(tot, params)

        # 2 scalars + 2 list + 2 dict + 1 string = 7 applied keys
        self.assertEqual(len(applied), 7)

        # scalar_calls should cover all non-string numeric sets
        scalar_names = [n for n, _ in tot.scalar_calls]
        for expected in (
            "eq:RR", "eq:BB",
            "tr:PN[1]", "tr:PN[2]",
            "tr:PT[1]", "tr:PT[2]",
        ):
            self.assertIn(expected, scalar_names)

        self.assertEqual(
            tot.string_calls,
            [("eq:KNAMEQ", "eqdata.ITER01")],
        )

    def test_list_preserves_namespace_prefix(self) -> None:
        tot = _MockTot()
        srv._apply_bulk_params(tot, {"tr:PN": [0.1, 0.2, 0.3]})
        names = [n for n, _ in tot.scalar_calls]
        self.assertEqual(names, ["tr:PN[1]", "tr:PN[2]", "tr:PN[3]"])

    def test_rejects_unsupported_type(self) -> None:
        tot = _MockTot()
        with self.assertRaises(TotlibError):
            srv._apply_bulk_params(tot, {"tr:RR": object()})

    def test_rejects_bool(self) -> None:
        # bool is a subclass of int; we want it rejected as ambiguous.
        tot = _MockTot()
        with self.assertRaises(TotlibError):
            srv._apply_bulk_params(tot, {"tr:MDLNB": True})

    def test_rejects_non_numeric_string_element(self) -> None:
        # MED-5: float() on a non-numeric list element maps to TotlibError.
        tot = _MockTot()
        with self.assertRaises(TotlibError) as ctx:
            srv._apply_bulk_params(tot, {"tr:PN": [0.7, "oops"]})
        self.assertIn("tr:PN[2]", str(ctx.exception))

    def test_rejects_non_int_dict_index(self) -> None:
        # MED-5: int() on a non-numeric index maps to TotlibError.
        tot = _MockTot()
        with self.assertRaises(TotlibError) as ctx:
            srv._apply_bulk_params(tot, {"tr:PT": {"bad": 4.2}})
        self.assertIn("tr:PT", str(ctx.exception))

    def test_partial_bulk_mutation_on_failure(self) -> None:
        # LOW-2: on a partial failure, earlier keys remain written.
        # Documented as non-transactional in set_params docstring.
        tot = _MockTot()
        with self.assertRaises(TotlibError):
            srv._apply_bulk_params(
                tot,
                {"eq:RR": 6.5, "tr:BAD": object(), "eq:BB": 5.3},
            )
        scalar_names = [n for n, _ in tot.scalar_calls]
        self.assertIn("eq:RR", scalar_names)
        self.assertNotIn("eq:BB", scalar_names)


class TestSiblingRegistryFallback(unittest.TestCase):
    """LOW-3: sibling-import failure should yield an empty namespace."""

    def test_load_sibling_registry_returns_empty_on_import_error(self) -> None:
        # A deliberately-missing module name must not raise — the
        # loader swallows the import error so tot_mcp stays usable
        # when siblings are not installed alongside.
        out = srv._load_sibling_registry("definitely_not_a_real_module_xyz")
        self.assertEqual(out, {})

    def test_load_sibling_registry_returns_dict_when_present(self) -> None:
        # wrx_mcp ships with this repo, so it must load successfully
        # (even if the dict is small in test setups).
        out = srv._load_sibling_registry("wrx_mcp")
        self.assertIsInstance(out, dict)

    def test_build_namespaced_registry_tolerates_missing_sibling(self) -> None:
        # Simulate a failed sibling import for one namespace by
        # monkey-patching __import__ so tr_mcp.server blows up.
        real_import = __import__
        missing = "tr_mcp.server"

        def _fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == missing:
                raise ImportError(
                    f"simulated missing sibling: {missing}"
                )
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=_fake_import):
            out = srv._build_namespaced_registry()

        # tr namespace must be present but empty; other namespaces
        # still load.
        self.assertIn("tr", out)
        self.assertEqual(out["tr"], {})
        # The eq namespace is inline (no sibling) and must still be
        # populated — the outage must not cascade.
        self.assertGreater(len(out["eq"]), 0)


class TestHandlersWithMockedState(unittest.TestCase):
    """Exercise handle_* against a mocked _ServerState.ensure_open."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()  # fresh state for this test class
        self.addCleanup(self._restore_state)

        self.mock_tot = _MockTot()
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=self.mock_tot
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def test_handle_init(self) -> None:
        msg = srv.handle_init()
        self.assertIn("initialized", msg)

    def test_handle_set_param_numeric(self) -> None:
        msg = srv.handle_set_param("eq:RR", 6.5)
        self.assertIn("eq:RR", msg)
        self.assertEqual(self.mock_tot.scalar_calls[-1], ("eq:RR", 6.5))

    def test_handle_set_param_routes_string_to_str_setter(self) -> None:
        # If a caller goes through the single-set tool with a string
        # value, we should still hit set_param_str.
        msg = srv.handle_set_param("eq:KNAMEQ", "eqdata.ITER01")
        self.assertIn("eq:KNAMEQ", msg)
        self.assertEqual(
            self.mock_tot.string_calls[-1],
            ("eq:KNAMEQ", "eqdata.ITER01"),
        )

    def test_handle_set_param_rejects_list_value(self) -> None:
        # set_param is the scalar/string entry point; bulk array values
        # must go through set_params. The reject path is tested here so
        # the contract does not regress to a generic float() TypeError.
        with self.assertRaises(Exception) as ctx:
            srv.handle_set_param("eq:RIPFC", [1.0, 2.0])  # type: ignore[arg-type]
        self.assertIn("set_params", str(ctx.exception))

    def test_handle_set_param_rejects_dict_value(self) -> None:
        with self.assertRaises(Exception) as ctx:
            srv.handle_set_param("eq:RIPFC", {1: 1.0})  # type: ignore[arg-type]
        self.assertIn("set_params", str(ctx.exception))

    def test_handle_set_params(self) -> None:
        msg = srv.handle_set_params({"tr:DT": 0.01})
        self.assertIn("1 parameter", msg)

    def test_handle_set_params_rejects_non_dict(self) -> None:
        with self.assertRaises(Exception) as ctx:
            srv.handle_set_params(["tr:DT", 0.01])  # type: ignore[arg-type]
        self.assertIn("dict", str(ctx.exception))

    def test_handle_run(self) -> None:
        msg = srv.handle_run(3)
        self.assertIn("3", msg)
        self.assertEqual(self.mock_tot.run_calls, [3])

    def test_handle_get_state(self) -> None:
        out = srv.handle_get_state()
        self.assertIn("NT", out)
        self.assertIn("scalars", out)
        self.assertIn("presence", out)

    def test_handle_run_and_get_state(self) -> None:
        out = srv.handle_run_and_get_state(
            params={"eq:RR": 7.0}, ntmax=2,
        )
        self.assertIn("NT", out)
        self.assertEqual(self.mock_tot.scalar_calls[-1], ("eq:RR", 7.0))
        self.assertEqual(self.mock_tot.run_calls, [2])

    def test_handle_run_and_get_state_no_params(self) -> None:
        # ``params=None`` should still advance and return state.
        out = srv.handle_run_and_get_state(params=None, ntmax=0)
        self.assertEqual(self.mock_tot.run_calls, [0])
        self.assertIn("NT", out)


# =====================================================================
# Namespace prefix guard (delegated to totlib but worth covering here
# so the MCP layer's user-visible behaviour is documented in the suite).
# =====================================================================
class TestNamespaceGuard(unittest.TestCase):
    """Bare names are rejected before reaching the FFI boundary."""

    def setUp(self) -> None:
        self._real_state = srv.STATE
        srv.STATE = srv._ServerState()
        self.addCleanup(self._restore_state)

    def _restore_state(self) -> None:
        srv.STATE = self._real_state

    def _fake_open_returns(self, fake: Any) -> None:
        patcher = mock.patch.object(
            srv.STATE, "ensure_open", return_value=fake
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_bare_name_raises_via_real_tot_validator(self) -> None:
        # Use a tiny stand-in that delegates to the real validator on
        # the Tot class. set_param without a colon triggers the
        # canonical TotlibInvalidParamError, which the MCP layer wraps.
        from totlib.totlib import Tot as RealTot

        class _Validating(_MockTot):
            def set_param(self_inner, name: str, value: float) -> None:
                # Re-use the real static guard; never touches the FFI.
                RealTot._validate_namespaced_name(name)
                self_inner.scalar_calls.append((name, value))

        self._fake_open_returns(_Validating())
        with self.assertRaises(Exception) as ctx:
            srv.handle_set_param("RR", 6.5)
        self.assertIn("invalid parameter", str(ctx.exception))


# =====================================================================
# CLI entry-point: --help / --print-tools must not require mcp SDK.
# =====================================================================
class TestMainCliFlags(unittest.TestCase):
    """--help and --print-tools should work without mcp or libtotapi.so."""

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

    def test_print_tools_lists_all_nine(self) -> None:
        import io
        import contextlib

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            srv.main(["--print-tools"])
        listed = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        # 9 canonical tools, sorted alphabetically.
        self.assertEqual(len(listed), 9)
        for tool in (
            "init", "set_param", "set_params", "run",
            "get_state", "finalize", "describe_parameters",
            "describe_state_schema", "run_and_get_state",
        ):
            self.assertIn(tool, listed)


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
        self.assertEqual(getattr(s, "name", None), "task-tot")


# =====================================================================
# Integration tests (real libtotapi.so).
# =====================================================================
@unittest.skipUnless(
    LIBTOTAPI_SO.exists(),
    f"libtotapi.so not found at {LIBTOTAPI_SO}; skipping integration tests",
)
class TestIntegration(unittest.TestCase):
    """End-to-end against the real .so (set_param works at L-3+).

    L-3/L-4/L-5 keep tot_run / tot_get_state stubbed (rc=4), so we only
    assert that init reports success and that a numeric set_param round
    trips through the namespace-aware dispatcher. Once L-6 lands, the
    run/get_state assertions in the sibling tr_mcp suite become valid
    here too.
    """

    def setUp(self) -> None:
        srv.STATE.close()

    def tearDown(self) -> None:
        srv.STATE.close()

    def test_init_then_set_param(self) -> None:
        self.assertIn("initialized", srv.handle_init())
        # eq:RR is registered in eq_param_registry.f90.
        msg = srv.handle_set_param("eq:RR", 6.2)
        self.assertIn("eq:RR", msg)

    def test_set_param_bare_name_rejected(self) -> None:
        srv.handle_init()
        with self.assertRaises(Exception) as ctx:
            srv.handle_set_param("RR", 6.2)
        self.assertIn("invalid parameter", str(ctx.exception))

    def test_finalize_is_idempotent(self) -> None:
        srv.handle_init()
        self.assertIn("finalized", srv.handle_finalize())
        # Second finalize must not raise.
        self.assertIn("finalized", srv.handle_finalize())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
