"""FastMCP server exposing the TASK/TOT orchestrator as MCP tools.

Entry point for ``python -m tot_mcp.server`` or the ``tot-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `Tot` instance per server process.** libtotapi.so holds Fortran
  COMMON-block singleton state across every backing module (eq / tr /
  fp / ti / wrx), so there is at most one live handle per process.
  Subsequent ``init`` calls close the old handle and re-open a fresh one
  so that an LLM can "start over" without restarting the server.
* **Namespaced parameter names.** TOT is the orchestrator; its
  parameter space is the **union** of six per-module registries. Every
  ``set_param`` / ``set_params`` key MUST be of the form
  ``"<ns>:<name>"`` where ``<ns>`` is one of ``("eq", "tr", "fp", "ti",
  "wr", "wrx")``. Bare names like ``"RR"`` are rejected up-front by
  ``totlib`` with a clear error message. Array-element syntax
  ``"<ns>:NAME[i]"`` (1-origin) is forwarded verbatim to the matching
  per-module registry.
* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** :class:`totlib.TotlibError` subclasses are
  re-raised as :class:`ToolError` with a human-readable message. The
  LLM sees the error string and can often recover (e.g. by adding the
  missing namespace prefix or calling ``init`` first).
* **L-5 stub status.** ``tot_run`` and ``tot_get_state`` return
  ``TOT_ERR_NOT_IMPL`` until L-6 wires up per-module fan-out. The
  wrapper surfaces that as
  :class:`totlib.TotlibNotImplementedError`; the MCP error-mapping
  layer reports it as ``"not implemented in this libtotapi.so build"``.
  ``set_param`` / ``set_param_str`` already work end-to-end.

The server intentionally mirrors :mod:`tr_mcp.server` so that follow-up
maintenance can keep the per-module and orchestrator surfaces aligned.
"""
from __future__ import annotations

import os  # noqa: F401  (re-exported for symmetry with sibling MCP servers)
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``totlib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/tot_mcp/server.py
# and we want to import ``totlib`` from
#   <repo>/python/totlib/
# so prepend ``<repo>/python`` to sys.path if not already there.
# ---------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PYTHON_ROOT = _HERE.parents[2]  # .../python
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

# ---------------------------------------------------------------------
# MCP SDK import.
#
# `mcp` is an external dependency. We import lazily so that tooling
# (syntax check, `-m py_compile`) can still parse this file even when
# the SDK is not installed in the current environment.
# ---------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

    try:
        from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - older mcp layouts
        ToolError = RuntimeError  # type: ignore[assignment,misc]
    MCP_AVAILABLE = True
except Exception:  # pragma: no cover - MCP SDK not installed
    FastMCP = None  # type: ignore[assignment,misc]
    ToolError = RuntimeError  # type: ignore[assignment,misc]
    MCP_AVAILABLE = False

# ---------------------------------------------------------------------
# totlib import (always available from the repo).
# ---------------------------------------------------------------------
from totlib import (  # noqa: E402
    Tot,
    TotlibError,
    TotlibInitError,
    TotlibInvalidParamError,
    TotlibNotInitializedError,
    TotlibCalculationFailedError,
    TotlibNotImplementedError,
)
from totlib._ffi import TOT_NAMESPACES  # noqa: E402


# =====================================================================
# Per-namespace parameter registries.
#
# tot is an orchestrator: rather than re-listing every per-module
# parameter inline (the union is ~250 entries and would drift quickly),
# we delegate to the sibling MCP servers' PARAMETER_REGISTRY exports
# whenever they are importable, and fall back to a small inline
# registry when the sibling is missing (currently only ``eq:`` — there
# is no eq_mcp yet). The dispatch matches ``tot_param_registry.f90``:
#
#   eq   -> inline (no eq_mcp yet)
#   tr   -> tr_mcp.server.PARAMETER_REGISTRY
#   fp   -> fp_mcp.server.PARAMETER_REGISTRY
#   ti   -> ti_mcp.server.PARAMETER_REGISTRY
#   wrx  -> wrx_mcp.server.PARAMETER_REGISTRY
#   wr   -> alias of wrx (matches the Fortran dispatcher: tot links
#           wrx/libwr.a, not wr/libwr.a)
# =====================================================================
# Includes `str` for string-valued parameters under the `tr:` and `eq:`
# namespaces (KNAMEQ etc.); other namespaces will raise
# :class:`TotlibInvalidParamError` for string values, which `_wrap`
# translates.
SupportedValue = Union[float, int, str, List[float], Dict[int, float]]


# Inline registry for the ``eq:`` namespace. There is no eq_mcp yet, so
# we surface the most important parameters by hand. The full list lives
# in ``eq/eq_param_registry.f90``; LLMs can still set bare names that
# are not listed here — the request goes through and only fails if the
# per-module registry rejects the name.
_EQ_INLINE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "RR":      {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":      {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RB":      {"type": "float", "group": "geometry", "description": "vacuum-vessel minor radius [m]"},
    "RKAP":    {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":    {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":      {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "QA":      {"type": "float", "group": "geometry", "description": "edge safety factor"},
    "RIP":     {"type": "float", "group": "geometry", "description": "plasma current [MA]"},
    "RHOMIN":  {"type": "float", "group": "geometry", "description": "minimum normalized radius for q profile"},
    "QMIN":    {"type": "float", "group": "geometry", "description": "minimum q value"},
    "RHOEDG":  {"type": "float", "group": "geometry", "description": "edge normalized radius"},
    "PTSEQ":   {"type": "float", "group": "solver",   "description": "equilibrium pressure scaling"},
    "EPSEQ":   {"type": "float", "group": "solver",   "description": "equilibrium convergence tolerance"},
    "EPSNW":   {"type": "float", "group": "solver",   "description": "Newton solver tolerance"},
    "DELNW":   {"type": "float", "group": "solver",   "description": "Newton solver step damping"},
    "MODELG":  {"type": "int",   "group": "models",   "description": "equilibrium/geometry selector"},
    "MODELQ":  {"type": "int",   "group": "models",   "description": "q-profile model selector"},
    "MDLEQF":  {"type": "int",   "group": "models",   "description": "equilibrium-from-file selector"},
    "MDLEQC":  {"type": "int",   "group": "models",   "description": "equilibrium calculation selector"},
    "NRMAX":   {"type": "int",   "group": "grid",     "description": "number of radial grid points"},
    "NTHMAX":  {"type": "int",   "group": "grid",     "description": "number of poloidal grid points"},
    "NSUMAX":  {"type": "int",   "group": "grid",     "description": "number of equilibrium surfaces"},
    "NPRINT":  {"type": "int",   "group": "io",       "description": "print level"},
    "PSIB":    {"type": "float[0..5]", "group": "boundary", "description": "boundary flux array (0-origin, PSIB[0]..PSIB[5]; matches eq/eq_param_registry.f90 REAL(8) :: PSIB(0:5))"},
    "RIPFC":   {"type": "float[]", "group": "pfc",      "description": "PFC coil currents (1-origin) [MA]"},
    "RPFC":    {"type": "float[]", "group": "pfc",      "description": "PFC coil R positions (1-origin) [m]"},
    "ZPFC":    {"type": "float[]", "group": "pfc",      "description": "PFC coil Z positions (1-origin) [m]"},
    "WPFC":    {"type": "float[]", "group": "pfc",      "description": "PFC coil widths (1-origin) [m]"},
    "KNAMEQ":  {"type": "str", "group": "io", "description": "equilibrium data file name (string-valued)"},
    "KNAMWR":  {"type": "str", "group": "io", "description": "ray-tracing data file name (string-valued)"},
    "KNAMWM":  {"type": "str", "group": "io", "description": "wave-modeling data file name (string-valued)"},
}


def _load_sibling_registry(module_name: str) -> Dict[str, Dict[str, Any]]:
    """Best-effort import of a sibling MCP server's PARAMETER_REGISTRY.

    Returns an empty dict if the sibling is not importable (e.g. the
    user installed ``tot_mcp`` without the rest of the tree). The
    catch-all is intentional: namespace coverage is informational and
    must not break orchestrator tools that work without it.
    """
    try:
        mod = __import__(f"{module_name}.server", fromlist=["server"])
    except Exception:  # pragma: no cover - sibling not installed
        return {}
    return dict(getattr(mod, "PARAMETER_REGISTRY", {}) or {})


def _build_namespaced_registry() -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Assemble per-namespace dicts of {bare_name: {type, group, ...}}.

    Called at import time; the result is cached in
    :data:`PARAMETER_REGISTRIES`. Re-loading would only be useful if a
    sibling MCP package were installed mid-process, which we don't
    support at L-5 scope.
    """
    return {
        "eq":  dict(_EQ_INLINE_REGISTRY),
        "tr":  _load_sibling_registry("tr_mcp"),
        "fp":  _load_sibling_registry("fp_mcp"),
        "ti":  _load_sibling_registry("ti_mcp"),
        "wrx": _load_sibling_registry("wrx_mcp"),
        # ``wr:`` is an alias of ``wrx:`` on the Fortran side
        # (tot/tot_param_registry.f90); keep the same alias here so the
        # describe output mirrors what callers can actually set.
        "wr":  _load_sibling_registry("wrx_mcp"),
    }


PARAMETER_REGISTRIES: Dict[str, Dict[str, Dict[str, Any]]] = _build_namespaced_registry()


def _flat_count() -> int:
    """Return the total number of (namespace, bare_name) pairs known."""
    return sum(len(v) for v in PARAMETER_REGISTRIES.values())


# State schema mirrors ``totlib.state.TotState.to_dict()`` exactly.
STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "TotState (wire format of totlib.state.TotState.to_dict())",
    "properties": {
        "presence": {
            "type": "object",
            "description": (
                "per-sub-module initialization flags (0 = absent, "
                "1 = initialized) — useful to confirm which modules "
                "actually contributed to the snapshot"
            ),
            "properties": {
                "tr": {"type": "integer"},
                "ti": {"type": "integer"},
                "fp": {"type": "integer"},
                "wr": {"type": "integer"},
            },
        },
        "NT":    {"type": "integer", "description": "current time-step index (TR-authoritative)"},
        "NRMAX": {"type": "integer", "description": "radial points actually in use"},
        "NSMAX": {"type": "integer", "description": "species actually in use"},
        "scalars": {
            "type": "object",
            "description": (
                "13 integrated plasma scalars (T, WPT, AJT, Q0, BETA0, "
                "BETAP0, BETAA, BETAN, TAUE1, TAUE2, ZEFF0, ALI, RQ1)"
            ),
            "additionalProperties": {"type": "number"},
        },
        "profile": {
            "type": "array",
            "description": "radial profile, length = NRMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NR": {"type": "integer", "description": "1-origin radial index"},
                    "RN": {"type": "array", "items": {"type": "number"}, "description": "density per species (length NSMAX)"},
                    "RT": {"type": "array", "items": {"type": "number"}, "description": "temperature per species"},
                    "AJ": {"type": "number", "description": "current density"},
                    "QP": {"type": "number", "description": "safety factor"},
                },
            },
        },
    },
    "required": ["presence", "NT", "NRMAX", "NSMAX", "scalars", "profile"],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Tot` instance for this server."""

    def __init__(self) -> None:
        self.tot: Optional[Tot] = None

    def ensure_open(self) -> Tot:
        """Return the live handle, opening one if needed."""
        if self.tot is None or self.tot.closed:
            self.tot = Tot()
        return self.tot

    def close(self) -> None:
        if self.tot is not None and not self.tot.closed:
            self.tot.close()
        self.tot = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(tot: Tot, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Each key MUST be a fully namespaced ``"<ns>:<bare>"`` name. The
    ``<bare>`` portion may itself contain array-element syntax
    (``"NAME[i]"``) which is forwarded verbatim to the per-module
    registry.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Tot.set_param`.
    * ``list`` / ``tuple``           — element at 1-origin index ``i``
      is applied as ``"<ns>:NAME[i]"``. **Rejected for ``eq:PSIB``**
      because that array is 0-origin (``PSIB[0]..PSIB[5]``); use the
      dict form below.
    * ``dict[int, float]``           — sparse {index: value}, applied as
      ``"<ns>:NAME[index]"``; indices are 1-origin for most arrays
      but ``eq:PSIB`` is 0-origin.
    * ``str``                        — forwarded to
      :py:meth:`Tot.set_param_str`.

    .. warning::

       This routine is **non-transactional**: parameters are forwarded
       to the underlying Fortran library one at a time and a failure
       partway through leaves earlier writes in place. Callers that
       need rollback semantics must validate the input dict (and snap
       the prior state) themselves. A two-pass dry-run + apply is
       tracked as a follow-up.
    """
    applied: List[str] = []
    for name, value in params.items():
        # Reject bool early: bool is a subclass of int and would be
        # silently coerced by float(); the contract is explicit numbers.
        if isinstance(value, bool):
            raise TotlibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            # Slice ``"<ns>:BASE"`` so we can re-attach the prefix to
            # each subscripted key. Names without ``:`` will be caught
            # by Tot.set_param's namespace guard on first use.
            ns, sep, bare = name.partition(":")
            if not sep:
                # Forward as-is to let Tot raise the canonical error
                # for "missing namespace prefix" — this keeps the error
                # message LLM-friendly.
                try:
                    coerced = float(value[0]) if value else 0.0
                except (TypeError, ValueError) as exc:
                    raise TotlibError(
                        f"invalid numeric value for '{name}': {value!r} "
                        f"({exc})"
                    ) from exc
                tot.set_param(name, coerced)
                applied.append(name)
                continue
            # eq:PSIB is 0-origin (REAL(8) :: PSIB(0:5)). A list would
            # be enumerated from 1 and silently write to PSIB[1..N],
            # missing PSIB[0] and overshooting past PSIB[5]. Mirror the
            # eq_mcp guard: force the dict form for sparse-indexed
            # 0-origin arrays. (This matches the policy Codex flagged
            # against PR b6d23243 once PSIB was documented as 0-origin
            # at tot_mcp/server.py:148.)
            if ns == "eq" and bare == "PSIB":
                raise TotlibError(
                    "eq:PSIB is a 0-origin array (PSIB[0]..PSIB[5]); "
                    "pass a dict {0: v0, 1: v1, ...} instead of a list "
                    "(a list would silently start at index 1 and miss "
                    "index 0)."
                )
            for i, v in enumerate(value, start=1):
                key = f"{ns}:{bare}[{i}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TotlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                tot.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            ns, sep, bare = name.partition(":")
            if not sep:
                # Same fall-through as the list case: let Tot raise.
                if value:
                    first_idx, first_val = next(iter(value.items()))
                    try:
                        coerced = float(first_val)
                    except (TypeError, ValueError) as exc:
                        raise TotlibError(
                            f"invalid numeric value for '{name}': "
                            f"{first_val!r} ({exc})"
                        ) from exc
                    tot.set_param(name, coerced)
                    applied.append(name)
                continue
            for idx, v in value.items():
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise TotlibError(
                        f"invalid index for '{ns}:{bare}': {idx!r} ({exc})"
                    ) from exc
                key = f"{ns}:{bare}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TotlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                tot.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, str):
            # String setter: only `tr:` and `eq:` are backed today.
            tot.set_param_str(name, value)
            applied.append(name)
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise TotlibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            tot.set_param(name, coerced)
            applied.append(name)
        else:
            raise TotlibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_totlib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate a totlib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, TotlibInvalidParamError):
        msg = (
            f"invalid parameter: {exc}. "
            f"Hint: tot parameter names must be namespaced as "
            f"'<ns>:<name>' where <ns> is one of {TOT_NAMESPACES}."
        )
    elif isinstance(exc, TotlibNotInitializedError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, TotlibCalculationFailedError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, TotlibNotImplementedError):
        msg = (
            f"not implemented in this libtotapi.so build: {exc}. "
            f"L-3/L-4/L-5 ship stub init/run/get_state/finalize; L-6 "
            f"will wire up the per-module fan-out."
        )
    elif isinstance(exc, TotlibInitError):
        msg = f"tot_init failed: {exc}"
    elif isinstance(exc, TotlibError):
        msg = f"totlib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libtotapi.so not found: {exc}. "
            "Build it via `make -C tot libtotapi.so` or set TOTLIB_PATH."
        )
    else:
        # Unexpected — re-wrap so MCP still gets a clean error.
        msg = f"{type(exc).__name__}: {exc}"
    return ToolError(msg)  # type: ignore[operator,call-arg]


# =====================================================================
# Tool handler implementations (plain Python, unit-testable).
#
# The FastMCP-decorated tools below delegate here so that the test
# suite can exercise the same code without spinning up the MCP
# transport.
# =====================================================================
def handle_init() -> str:
    try:
        STATE.ensure_open()
        return "tot library initialized"
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_set_param(name: str, value: Union[float, int, str]) -> str:
    # Bulk types (List/Dict) are intentionally rejected here — use
    # `set_params` for those. Validating up front gives a clearer
    # error than letting `float(value)` raise a generic TypeError.
    if isinstance(value, (list, tuple, dict)):
        raise ToolError(  # type: ignore[call-arg]
            f"set_param does not accept array/dict values for {name}; "
            f"use set_params with a {{name: array|dict}} mapping instead"
        )
    try:
        tot = STATE.ensure_open()
        if isinstance(value, str):
            tot.set_param_str(name, value)
        else:
            tot.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        tot = STATE.ensure_open()
        applied = _apply_bulk_params(tot, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_run(ntmax: int = 1) -> str:
    try:
        tot = STATE.ensure_open()
        tot.run(int(ntmax))
        return f"advanced {ntmax} time step(s)"
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        tot = STATE.ensure_open()
        return tot.get_state().to_dict()
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "tot library finalized"
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    """Return per-namespace registries for the orchestrator.

    The ``namespaces`` key carries a dict mapping each supported
    namespace prefix (``eq``, ``tr``, ``fp``, ``ti``, ``wr``, ``wrx``)
    to its bare-name registry. ``count`` is the total number of
    ``(namespace, bare_name)`` entries across every backing module.
    """
    return {
        "module": "tot",
        "count": _flat_count(),
        "namespaces": list(TOT_NAMESPACES),
        "name_syntax": (
            "Every parameter name MUST be of the form '<ns>:<bare>' "
            "where <ns> is one of {}. Array elements use '<ns>:NAME[i]' "
            "(usually 1-origin), e.g. 'tr:PN[1]'. The eq:PSIB array is "
            "0-origin (eq:PSIB[0]..eq:PSIB[5]) because the underlying "
            "Fortran is REAL(8) :: PSIB(0:5). The 'wr:' namespace is an "
            "alias of 'wrx:' (tot links wrx/libwr.a, not wr/libwr.a; "
            "see tot/tot_param_registry.f90)."
        ).format(TOT_NAMESPACES),
        "parameters": PARAMETER_REGISTRIES,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    ntmax: int = 1,
) -> Dict[str, Any]:
    try:
        tot = STATE.ensure_open()
        if params:
            _apply_bulk_params(tot, params)
        tot.run(int(ntmax))
        return tot.get_state().to_dict()
    except Exception as exc:
        raise _wrap_totlib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 9 tot tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-tot",
        instructions=(
            "TASK/TOT integrated-orchestrator MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "or `set_params` (names MUST be namespaced as '<ns>:<name>' "
            "where <ns> in {eq, tr, fp, ti, wr, wrx}; 'wr:' is an alias "
            "of 'wrx:' on the Fortran side), advance with `run`, and "
            "read state with `get_state`. Use `describe_parameters` to "
            "discover valid namespaced names. `run_and_get_state` is a "
            "convenience one-shot wrapper. Note: `set_params` is "
            "*non-transactional* — on a partial failure, parameters "
            "applied before the failing key remain set; pre-validate "
            "with `describe_parameters` if a clean rollback matters. "
            "EQ-specific note: PSIB is 0-origin (eq:PSIB[0]..eq:PSIB[5]); "
            "all other 1D arrays are 1-origin. Note: `run`/`get_state` "
            "return TotlibNotImplementedError until L-6 lands; "
            "`set_param`/`set_param_str` already work."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the tot library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: Union[float, int, str]) -> str:
        """Set a tot parameter by **namespaced** name.

        ``name`` MUST be of the form ``"<ns>:<bare>"`` where ``<ns>``
        is one of ``("eq", "tr", "fp", "ti", "wr", "wrx")`` — for
        example ``"eq:RR"``, ``"tr:DT"``, ``"fp:NSMAX"``,
        ``"ti:RR"``, ``"wr:RFIN"`` or ``"wrx:RFIN"``. Use
        ``"<ns>:NAME[i]"`` (1-origin) for array elements, e.g.
        ``"tr:PN[1]"``. The ``eq:PSIB`` array is 0-origin
        (``eq:PSIB[0]..eq:PSIB[5]``); all other 1D arrays are
        1-origin. The ``wr:`` namespace is an alias of ``wrx:``
        because tot links ``wrx/libwr.a`` rather than
        ``wr/libwr.a`` — both prefixes route to the same Fortran
        ``wrx_param_set`` (see ``tot/tot_param_registry.f90``).
        ``value`` may be a number or a string — string values route
        to the ``tr:`` / ``eq:`` string setters (other namespaces
        will reject strings). See `describe_parameters` for the full
        registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set tot parameters (every key must be namespaced).

        ``params`` keys MUST already be namespaced as ``"<ns>:<bare>"``;
        values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (sparse array; 1-origin for most
          arrays but the ``eq:PSIB`` array is 0-origin and MUST use the
          dict form — a list is rejected because it would silently
          start at index 1 and skip ``eq:PSIB[0]``)
        * a string (only the ``tr:`` and ``eq:`` namespaces back
          string setters today; other namespaces will reject strings)

        **Non-transactional**: keys are applied in iteration order and
        a failure on key ``N`` leaves keys ``0..N-1`` already written
        to the underlying Fortran library. There is no automatic
        rollback in this PR — pre-validate with ``describe_parameters``
        if a clean rollback matters. (Two-pass dry-run + apply is
        tracked as a follow-up task.)
        """
        return handle_set_params(params)

    @mcp.tool()
    def run(ntmax: int = 1) -> str:
        """Advance the integrated simulation by ``ntmax`` time steps.

        ``ntmax=0`` is a valid no-op (useful as a smoke test). Today
        ``tot_run`` is a stub returning ``TOT_ERR_NOT_IMPL``; the MCP
        layer surfaces that as a "not implemented" error. L-6 will
        flip the switch to per-module fan-out without API changes.
        """
        return handle_run(ntmax)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current orchestrator state.

        Returns a dict with ``presence`` (per-sub-module init flags),
        ``NT``, ``NRMAX``, ``NSMAX``, ``scalars`` (13 plasma scalars),
        and ``profile`` (radial profile array). Schema also available
        via `describe_state_schema`. Stubbed until L-6.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release tot library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the per-namespace tot parameter registries.

        Output structure::

            {
              "module": "tot",
              "count": <int>,
              "namespaces": ["eq", "tr", "fp", "ti", "wr", "wrx"],
              "name_syntax": "<...help text...>",
              "parameters": {
                "eq": { "RR": {...}, "BB": {...}, ... },
                "tr": { ... },
                ...
              }
            }

        Each leaf entry exposes ``type``, ``group`` and
        ``description``.
        """
        return handle_describe_parameters()

    @mcp.tool()
    def describe_state_schema() -> Dict[str, Any]:
        """Return a JSON schema describing `get_state` output."""
        return handle_describe_state_schema()

    @mcp.tool()
    def run_and_get_state(
        params: Optional[Dict[str, Any]] = None,
        ntmax: int = 1,
    ) -> Dict[str, Any]:
        """Convenience: init + set_params + run + get_state in one call.

        Equivalent to::

            init()
            set_params(params)
            run(ntmax)
            return get_state()
        """
        return handle_run_and_get_state(params, ntmax)

    return mcp


def main(argv: Optional[List[str]] = None) -> int:
    """Console-script entry point.

    Runs the FastMCP stdio server. Exits cleanly on SIGINT.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(
            "tot-mcp — Model Context Protocol server for TASK/TOT "
            "(integrated orchestrator)\n"
            "\n"
            "Usage:\n"
            "  python -m tot_mcp.server    # run over stdio (default)\n"
            "  tot-mcp                     # same, via installed script\n"
            "  tot-mcp --help              # show this help\n"
            "  tot-mcp --print-tools       # list registered tools\n"
            "\n"
            "Parameter naming:\n"
            "  Every parameter name MUST be namespaced as '<ns>:<name>'\n"
            "  where <ns> is one of: eq, tr, fp, ti, wr, wrx.\n"
            "  Examples: 'eq:RR', 'tr:DT', 'fp:NSMAX', 'wrx:RFIN'.\n"
            "\n"
            "Environment:\n"
            "  TOTLIB_PATH  override path to libtotapi.so\n"
            "  PYTHONPATH   must include the repo's python/ directory\n"
            "               (set automatically when running in-tree)\n"
        )
        return 0

    if "--print-tools" in argv:
        for tool in sorted(
            [
                "init",
                "set_param",
                "set_params",
                "run",
                "get_state",
                "finalize",
                "describe_parameters",
                "describe_state_schema",
                "run_and_get_state",
            ]
        ):
            sys.stdout.write(tool + "\n")
        return 0

    if not MCP_AVAILABLE:
        sys.stderr.write(
            "error: Python MCP SDK (`mcp`) is not installed.\n"
            "       pip install 'mcp>=0.9'\n"
        )
        return 2

    server = build_server()
    # FastMCP >=0.9 exposes .run() for stdio transport by default.
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
