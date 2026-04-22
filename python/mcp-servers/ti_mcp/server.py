"""FastMCP server exposing the TASK/TI library as MCP tools.

Entry point for ``python -m ti_mcp.server`` or the ``ti-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `TiLib` instance per server process.** libtiapi.so holds
  Fortran COMMON-block singleton state, so there is at most one live
  handle. Subsequent ``init`` calls close the old handle and re-open a
  fresh one so that an LLM can "start over" without restarting the
  server.
* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** `tilib.TilibError` subclasses are re-raised as
  `ToolError` with a human-readable message. The LLM sees the error
  string and can often recover (e.g. by calling ``init`` first).

The server is intentionally small — the real heavy lifting is in
:mod:`tilib`. This file mirrors ``tr_mcp/server.py`` and swaps the
backing library, registry, and state schema to match TI.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``tilib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/ti_mcp/server.py
# and we want to import ``tilib`` from
#   <repo>/python/tilib/
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
# tilib import (always available from the repo).
# ---------------------------------------------------------------------
from tilib import (  # noqa: E402
    Tilib,
    TiState,
    TilibError,
    TilibInitError,
    TilibParamError,
    TilibStateError,
    TilibRunError,
    TilibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Keeping these in Python (rather than re-parsing ti_param_registry.f90)
# is a deliberate short-term choice: the LLM-facing description is more
# valuable than the last ounce of DRYness. When the Fortran registry
# changes we'll mirror it here.
#
# Mirrors the SELECT CASE entries in ``ti/ti_param_registry.f90``.
# =====================================================================
# Includes `str` even though ti_api.h exposes no string-setter today;
# this keeps the type surface uniform with tr_mcp so LLM clients can
# send string values without tripping schema-validation. String values
# raise TilibParamError at call time via the float-only ti_set_param
# ABI; the error path is covered by _wrap_tilib_error.
SupportedValue = Union[float, int, str, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- geometry / device (plcomm scalars) ------------------------
    "RR":    {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":    {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RKAP":  {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":  {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":    {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "RIP":   {"type": "float", "group": "geometry", "description": "plasma current [MA]"},
    # --- profile shape (plcomm 1D arrays indexed by NS) ------------
    "PROFN1": {"type": "float[]", "group": "profile", "description": "density profile shape parameter (1-origin)"},
    "PROFN2": {"type": "float[]", "group": "profile", "description": "density profile shape parameter (1-origin)"},
    "PROFT1": {"type": "float[]", "group": "profile", "description": "temperature profile shape parameter (1-origin)"},
    "PROFT2": {"type": "float[]", "group": "profile", "description": "temperature profile shape parameter (1-origin)"},
    "PROFU1": {"type": "float[]", "group": "profile", "description": "velocity profile shape parameter (1-origin)"},
    "PROFU2": {"type": "float[]", "group": "profile", "description": "velocity profile shape parameter (1-origin)"},
    # --- model switches (plcomm) -----------------------------------
    "MODELG":       {"type": "int", "group": "models", "description": "equilibrium/geometry selector"},
    "MODELQ":       {"type": "int", "group": "models", "description": "q-profile model selector"},
    "MODEL_PROF":   {"type": "int", "group": "models", "description": "profile model selector"},
    "MODEL_NPROF":  {"type": "int", "group": "models", "description": "n-profile model selector"},
    # --- plasma scalar int -----------------------------------------
    "NSMAX": {"type": "int", "group": "plasma", "description": "number of species"},
    # --- 1D arrays indexed by NS (plcomm) --------------------------
    "PA":   {"type": "float[NSM]", "group": "plasma", "description": "atomic mass per species (1-origin)"},
    "PZ":   {"type": "float[NSM]", "group": "plasma", "description": "charge number per species (1-origin)"},
    "PN":   {"type": "float[NSM]", "group": "plasma", "description": "initial density per species [10^20 m^-3]"},
    "PNS":  {"type": "float[NSM]", "group": "plasma", "description": "edge (separatrix) density per species"},
    "PT":   {"type": "float[NSM]", "group": "plasma", "description": "initial temperature per species [keV]"},
    "PTPR": {"type": "float[NSM]", "group": "plasma", "description": "parallel temperature per species [keV]"},
    "PTPP": {"type": "float[NSM]", "group": "plasma", "description": "perpendicular temperature per species [keV]"},
    "PTS":  {"type": "float[NSM]", "group": "plasma", "description": "edge temperature per species [keV]"},
    "PU":   {"type": "float[NSM]", "group": "plasma", "description": "initial velocity per species"},
    "PUS":  {"type": "float[NSM]", "group": "plasma", "description": "edge velocity per species"},
    # --- 1D int arrays indexed by NS -------------------------------
    "NPA":      {"type": "int[NSM]", "group": "plasma", "description": "particle-type code per species (1-origin)"},
    "ID_NS":    {"type": "int[NSM]", "group": "plasma", "description": "species identifier per species"},
    "NZMIN_NS": {"type": "int[NSM]", "group": "plasma", "description": "minimum ionization state per species"},
    "NZMAX_NS": {"type": "int[NSM]", "group": "plasma", "description": "maximum ionization state per species"},
    "NZINI_NS": {"type": "int[NSM]", "group": "plasma", "description": "initial ionization state per species"},
    # --- 2D arrays indexed by (i, NS) ------------------------------
    "MODEL_BND": {"type": "int[,NSM]",   "group": "boundary", "description": "boundary-condition model, MODEL_BND[i,NS] (both 1-origin)"},
    "BND_VALUE": {"type": "float[,NSM]", "group": "boundary", "description": "boundary value BND_VALUE[i,NS] (both 1-origin)"},
    # --- time evolution (ticomm_parm) ------------------------------
    "DT":      {"type": "float", "group": "time", "description": "time step [s]"},
    "NRMAX":   {"type": "int",   "group": "time", "description": "number of radial mesh points"},
    "NTMAX":   {"type": "int",   "group": "time", "description": "max number of steps (per run)"},
    "NTSTEP":  {"type": "int",   "group": "time", "description": "output cadence (steps)"},
    "NGTSTEP": {"type": "int",   "group": "time", "description": "graphics-output cadence (time)"},
    "NGRSTEP": {"type": "int",   "group": "time", "description": "graphics-output cadence (radial)"},
    "MAXLOOP": {"type": "int",   "group": "time", "description": "max inner-loop iterations"},
    "EPSLOOP": {"type": "float", "group": "time", "description": "convergence tolerance (loop)"},
    "EPSMAT":  {"type": "float", "group": "time", "description": "convergence tolerance (matrix solve)"},
    "MATTYPE": {"type": "int",   "group": "time", "description": "matrix-solver type selector"},
    "PROFJ1":  {"type": "float", "group": "time", "description": "current-profile parameter"},
    "PROFJ2":  {"type": "float", "group": "time", "description": "current-profile parameter"},
    # --- transport / source switches -------------------------------
    "MODEL_EQB":  {"type": "int", "group": "transport", "description": "equation model: poloidal B field"},
    "MODEL_EQN":  {"type": "int", "group": "transport", "description": "equation model: density"},
    "MODEL_EQT":  {"type": "int", "group": "transport", "description": "equation model: temperature"},
    "MODEL_EQU":  {"type": "int", "group": "transport", "description": "equation model: velocity"},
    "MODEL_KAI":  {"type": "int", "group": "transport", "description": "thermal-diffusivity model"},
    "MODEL_DRR":  {"type": "int", "group": "transport", "description": "particle-diffusion model"},
    "MODEL_VR":   {"type": "int", "group": "transport", "description": "convection model"},
    "MODEL_NC":   {"type": "int", "group": "transport", "description": "neoclassical model"},
    "MODEL_NF":   {"type": "int", "group": "transport", "description": "neutron/fusion model"},
    "MODEL_NB":   {"type": "int", "group": "transport", "description": "NBI heating model"},
    "MODEL_EC":   {"type": "int", "group": "transport", "description": "ECRF heating model"},
    "MODEL_LH":   {"type": "int", "group": "transport", "description": "LH heating model"},
    "MODEL_IC":   {"type": "int", "group": "transport", "description": "ICRF heating model"},
    "MODEL_CD":   {"type": "int", "group": "transport", "description": "current-drive model"},
    "MODEL_SYNC": {"type": "int", "group": "transport", "description": "synchrotron-radiation model"},
    "MODEL_PEL":  {"type": "int", "group": "transport", "description": "pellet-injection model"},
    "MODEL_PSC":  {"type": "int", "group": "transport", "description": "particle-source model"},
    # --- transport-coefficient scalars (ticomm_parm) --------------------
    # Registered in ti/ti_param_registry.f90; required for ti_ar / ti_min /
    # ti_w fixtures to reproduce their Phase-0 baselines (without these the
    # libtiapi.so run uses tiinit defaults and drifts ~2% from the baseline).
    "DN0":  {"type": "float", "group": "transport", "description": "particle diffusivity coefficient (default scalar)"},
    "DT0":  {"type": "float", "group": "transport", "description": "thermal diffusivity coefficient (default scalar)"},
    "DU0":  {"type": "float", "group": "transport", "description": "velocity diffusivity coefficient (default scalar)"},
    "VDN0": {"type": "float", "group": "transport", "description": "particle convection velocity (default scalar)"},
    "VDT0": {"type": "float", "group": "transport", "description": "thermal convection velocity (default scalar)"},
    "VDU0": {"type": "float", "group": "transport", "description": "velocity convection velocity (default scalar)"},
    "DR0":  {"type": "float", "group": "transport", "description": "radial-coefficient inner exponent"},
    "DRS":  {"type": "float", "group": "transport", "description": "radial-coefficient edge exponent"},
    # --- per-species transport-coefficient overrides --------------------
    "DN0_NS":  {"type": "float[NSM]", "group": "transport", "description": "per-species particle diffusivity override (1-origin)"},
    "DT0_NS":  {"type": "float[NSM]", "group": "transport", "description": "per-species thermal diffusivity override (1-origin)"},
    "DU0_NS":  {"type": "float[NSM]", "group": "transport", "description": "per-species velocity diffusivity override (1-origin)"},
    "VDN0_NS": {"type": "float[NSM]", "group": "transport", "description": "per-species particle convection override (1-origin)"},
    "VDT0_NS": {"type": "float[NSM]", "group": "transport", "description": "per-species thermal convection override (1-origin)"},
    "VDU0_NS": {"type": "float[NSM]", "group": "transport", "description": "per-species velocity convection override (1-origin)"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "TiState (wire format of tilib.state.TiState.to_dict())",
    "properties": {
        "NT":      {"type": "integer", "description": "current time-step index"},
        "NRMAX":   {"type": "integer", "description": "radial points in use"},
        "NSA_MAX": {"type": "integer", "description": "active species in use (uppercase canonical)"},
        # The Phase-0 baseline (tiregress.f90) uses lowercase; emit both so
        # compare_metrics and any LLM consumer relying on the .in regression
        # naming both find the key.
        "nsa_max": {"type": "integer", "description": "alias of NSA_MAX (Phase-0 baseline naming)"},
        "NSMAX":   {"type": "integer", "description": "species in TICOMM"},
        "scalars": {
            "type": "object",
            "description": "physical/diagnostic scalars (real)",
            "properties": {
                "T":                 {"type": "number", "description": "simulation time [s]"},
                "residual_loop_max": {"type": "number", "description": "max inner-loop residual"},
            },
        },
        # Iteration counters live in their own group to mirror the Phase-0
        # baseline JSON shape (separate so JSON-Schema readers can keep an
        # int-only group distinct from the float group above).
        "scalars_int": {
            "type": "object",
            "description": "iteration counters (int)",
            "properties": {
                "icount_loop_max":   {"type": "integer", "description": "max inner-loop iteration count"},
                "icount_mat_max":    {"type": "integer", "description": "max matrix-solve iteration count"},
            },
        },
        "profile": {
            "type": "array",
            "description": "radial profile, length = NRMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NR":    {"type": "integer", "description": "1-origin radial index"},
                    "RNA":   {"type": "array", "items": {"type": "number"}, "description": "density per species (length NSA_MAX)"},
                    "RTA":   {"type": "array", "items": {"type": "number"}, "description": "temperature per species"},
                    "RUA":   {"type": "array", "items": {"type": "number"}, "description": "velocity per species"},
                    "RBP":   {"type": "number", "description": "poloidal field"},
                    "RQP":   {"type": "number", "description": "safety factor"},
                    "RJP":   {"type": "number", "description": "current density"},
                    "ZEFF":  {"type": "number", "description": "effective charge"},
                    "BETA":  {"type": "number", "description": "beta"},
                    "BETAP": {"type": "number", "description": "poloidal beta"},
                },
            },
        },
    },
    "required": ["NT", "NRMAX", "NSA_MAX", "nsa_max", "NSMAX", "scalars", "scalars_int", "profile"],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Tilib` instance for this server."""

    def __init__(self) -> None:
        self.ti: Optional[Tilib] = None

    def ensure_open(self) -> Tilib:
        """Return the live handle, opening one if needed."""
        if self.ti is None or self.ti.closed:
            self.ti = Tilib()
        return self.ti

    def close(self) -> None:
        if self.ti is not None and not self.ti.closed:
            self.ti.close()
        self.ti = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(ti: Tilib, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Tilib.set_param`.
    * ``list`` / ``tuple``          — element at 1-origin index ``i``
      is applied as ``NAME[i]``.
    * ``dict[int, float]``          — sparse {index: value}, applied as
      ``NAME[index]``; indices must be 1-origin.
    * ``str``                       — the ti C ABI only accepts
      ``double`` values, so strings raise :class:`TilibParamError`
      here. The error path is then translated by
      :func:`_wrap_tilib_error` into a human-readable ToolError.
      Kept in the surface to keep the shape uniform with
      ``tr_mcp.set_params``.

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
            raise TilibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                # Nested bool: subclass of int would be coerced to 1.0
                # by float() — reject before float() so the top-level
                # bool contract also holds inside bulk arrays.
                if isinstance(v, bool):
                    raise TilibError(
                        f"unsupported value type for '{key}': "
                        f"bool (use 0/1)"
                    )
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TilibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                ti.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                # Reject bool keys AND bool values up-front; int(True)
                # == 1 would otherwise silently land in NAME[1].
                if isinstance(idx, bool):
                    raise TilibError(
                        f"invalid index for '{name}': bool (use 0/1)"
                    )
                if isinstance(v, bool):
                    raise TilibError(
                        f"unsupported value type for '{name}[{idx}]': "
                        f"bool (use 0/1)"
                    )
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise TilibError(
                        f"invalid index for '{name}': {idx!r} ({exc})"
                    ) from exc
                key = f"{name}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TilibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                ti.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, str):
            # No string-setter exists on the ti C ABI (see ti/ti_api.h).
            # Raising here keeps the failure mode uniform with tr_mcp,
            # and _wrap_tilib_error gives the LLM actionable guidance.
            raise TilibParamError(
                f"string values are not supported by ti_set_param "
                f"('{name}' = {value!r}); use a numeric value"
            )
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise TilibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            ti.set_param(name, coerced)
            applied.append(name)
        else:
            raise TilibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_tilib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate a tilib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, TilibParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, TilibStateError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, TilibRunError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, TilibNotImplementedError):
        msg = f"not implemented in this libtiapi.so build: {exc}"
    elif isinstance(exc, TilibInitError):
        msg = f"ti_init failed: {exc}"
    elif isinstance(exc, TilibError):
        msg = f"tilib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libtiapi.so not found: {exc}. "
            "Build it via `make -C ti libtiapi.so` or set TILIB_PATH."
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
        return "ti library initialized"
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        ti = STATE.ensure_open()
        ti.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        ti = STATE.ensure_open()
        applied = _apply_bulk_params(ti, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_run(ntmax: int = 1) -> str:
    try:
        ti = STATE.ensure_open()
        ti.run(int(ntmax))
        return f"advanced {ntmax} time step(s)"
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        ti = STATE.ensure_open()
        return ti.get_state().to_dict()
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "ti library finalized"
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "ti",
        "count": len(PARAMETER_REGISTRY),
        "array_syntax": (
            "Use NAME[i] (1-origin) for array elements, e.g. PN[1]. "
            "For 2-D arrays use NAME[i,j], e.g. MODEL_BND[1,3]."
        ),
        "parameters": PARAMETER_REGISTRY,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    ntmax: int = 1,
) -> Dict[str, Any]:
    try:
        ti = STATE.ensure_open()
        if params:
            _apply_bulk_params(ti, params)
        ti.run(int(ntmax))
        return ti.get_state().to_dict()
    except Exception as exc:
        raise _wrap_tilib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 9 ti tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-ti",
        instructions=(
            "TASK/TI transport-code MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "or `set_params`, advance with `run`, and read state with "
            "`get_state`. Use `describe_parameters` to discover valid "
            "parameter names. `run_and_get_state` is a convenience "
            "one-shot wrapper. Note: `set_params` is *non-transactional* "
            "— on a partial failure, parameters applied before the "
            "failing key remain set."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the ti library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set a ti parameter by name.

        Use ``NAME[i]`` (1-origin) for array elements, e.g. ``PN[1]``.
        Two-dimensional arrays use ``NAME[i,j]``, e.g. ``MODEL_BND[1,3]``.
        See `describe_parameters` for the full registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set ti parameters.

        ``params`` values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (1-origin sparse array)

        The TI C ABI (``ti_set_param``) is double-only, so string values
        are rejected with an ``invalid parameter`` error.

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
        """Advance the simulation by ``ntmax`` time steps.

        ``ntmax=0`` is a valid no-op (useful as a smoke test).
        """
        return handle_run(ntmax)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current simulation state.

        Returns a dict with ``NT``, ``NRMAX``, ``NSA_MAX``, ``NSMAX``,
        ``scalars`` (4 diagnostic scalars), and ``profile`` (radial
        profile array). Schema also available via `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release ti library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported ti parameters.

        Each entry exposes ``type``, ``group``, and ``description``.
        Use this to discover valid parameter names before set_param.
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
            "ti-mcp — Model Context Protocol server for TASK/TI\n"
            "\n"
            "Usage:\n"
            "  python -m ti_mcp.server    # run over stdio (default)\n"
            "  ti-mcp                     # same, via installed script\n"
            "  ti-mcp --help              # show this help\n"
            "  ti-mcp --print-tools       # list registered tools\n"
            "\n"
            "Environment:\n"
            "  TILIB_PATH   override path to libtiapi.so\n"
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
