"""FastMCP server exposing the TASK/WRX ray-tracing library as MCP tools.

Entry point for ``python -m wrx_mcp.server`` or the ``wrx-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `Wrxlib` instance per server process.** libwrxapi.so holds
  Fortran COMMON-block singleton state, so there is at most one live
  handle. Subsequent ``init`` calls close the old handle and re-open a
  fresh one so that an LLM can "start over" without restarting the
  server.
* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** `wrxlib.WrxlibError` subclasses are re-raised as
  `ToolError` with a human-readable message.
* **WRX_RUN_OK gate (CRITICAL).** The L-4 build of ``libwrxapi.so``
  retains an unresolved reference to ``libgrf::grd1d`` via
  ``wrcalpwr.f90``. Calling ``wrx_run`` through ``dlopen`` may
  segfault. The ``run`` and ``run_and_get_state`` tools therefore
  refuse to invoke ``wrx_run`` unless the caller has explicitly set
  ``WRX_RUN_OK=1`` in the environment. See ``python/wrxlib/README.md``
  "Known limitation: wrx_run in the shared build".

This mirrors the ``tr_mcp`` reference implementation as closely as
possible; the main wrx-specific additions are the WRX_RUN_OK gate and
the different parameter registry / state schema.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``wrxlib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/wrx_mcp/server.py
# and we want to import ``wrxlib`` from
#   <repo>/python/wrxlib/
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
# wrxlib import (always available from the repo).
# ---------------------------------------------------------------------
from wrxlib import (  # noqa: E402
    Wrxlib,
    WrxlibError,
    WrxlibInitError,
    WrxlibParamError,
    WrxlibStateError,
    WrxlibRunError,
    WrxlibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Mirrors ``wrx/wrx_param_registry.f90``. Keeping it in Python (rather
# than re-parsing the Fortran file) lets us attach LLM-friendly
# descriptions; when the Fortran registry changes we mirror it here.
# =====================================================================
SupportedValue = Union[float, int, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- geometry / device scalars ---------------------------------
    "RR":     {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":     {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RB":     {"type": "float", "group": "geometry", "description": "wall radius [m]"},
    "RKAP":   {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":   {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":     {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "Q0":     {"type": "float", "group": "geometry", "description": "safety factor on axis"},
    "QA":     {"type": "float", "group": "geometry", "description": "safety factor at edge"},
    "RIP":    {"type": "float", "group": "geometry", "description": "plasma current [MA]"},
    # --- plasma scalars --------------------------------------------
    "NSMAX":  {"type": "int",   "group": "plasma",   "description": "number of plasma species"},
    "PROFJ":  {"type": "float", "group": "plasma",   "description": "current profile parameter"},
    # --- plasma arrays (1..NSM) ------------------------------------
    "PA":     {"type": "float[NSM]", "group": "plasma", "description": "atomic mass per species (1-origin)"},
    "PZ":     {"type": "float[NSM]", "group": "plasma", "description": "charge number per species"},
    "PN":     {"type": "float[NSM]", "group": "plasma", "description": "initial density per species [10^20 m^-3]"},
    "PNS":    {"type": "float[NSM]", "group": "plasma", "description": "edge density per species"},
    "PTPR":   {"type": "float[NSM]", "group": "plasma", "description": "parallel temperature per species [keV]"},
    "PTPP":   {"type": "float[NSM]", "group": "plasma", "description": "perpendicular temperature per species [keV]"},
    "PTS":    {"type": "float[NSM]", "group": "plasma", "description": "edge temperature per species [keV]"},
    "PROFN1": {"type": "float[NSM]", "group": "plasma", "description": "density profile parameter 1"},
    "PROFN2": {"type": "float[NSM]", "group": "plasma", "description": "density profile parameter 2"},
    "PROFT1": {"type": "float[NSM]", "group": "plasma", "description": "temperature profile parameter 1"},
    "PROFT2": {"type": "float[NSM]", "group": "plasma", "description": "temperature profile parameter 2"},
    # --- pl/dp integration -----------------------------------------
    "MODELG":    {"type": "int",        "group": "modules", "description": "equilibrium/geometry selector"},
    "MODELQ":    {"type": "int",        "group": "modules", "description": "q-profile model selector"},
    "NSAMAX_WR": {"type": "int",        "group": "modules", "description": "number of species used by WR"},
    "MODELP":    {"type": "int[NSM]",   "group": "modules", "description": "dielectric tensor model per species"},
    "MODELV":    {"type": "int[NSM]",   "group": "modules", "description": "velocity-distribution model per species"},
    "NCMIN":     {"type": "int[NSM]",   "group": "modules", "description": "cyclotron harmonic min per species"},
    "NCMAX":     {"type": "int[NSM]",   "group": "modules", "description": "cyclotron harmonic max per species"},
    # --- WRX control scalars ---------------------------------------
    "NRAYMAX": {"type": "int", "group": "wrx",     "description": "number of rays (<= NRAYM=100)"},
    "NSTPMAX": {"type": "int", "group": "wrx",     "description": "max steps along ray"},
    "NRSMAX":  {"type": "int", "group": "wrx",     "description": "radial mesh (rs axis)"},
    "NRLMAX":  {"type": "int", "group": "wrx",     "description": "radial mesh (rl axis)"},
    "LMAXNW":  {"type": "int", "group": "wrx",     "description": "Newton iteration max"},
    "MDLWRI":  {"type": "int", "group": "wrx",     "description": "ray-init mode selector"},
    "MDLWRG":  {"type": "int", "group": "wrx",     "description": "graphics mode selector"},
    "MDLWRP":  {"type": "int", "group": "wrx",     "description": "power-deposition mode"},
    "MDLWRQ":  {"type": "int", "group": "wrx",     "description": "quasi-linear mode selector"},
    "MDLWRW":  {"type": "int", "group": "wrx",     "description": "wave-mode selector"},
    # --- ray init arrays (1..NRAYM=100) ----------------------------
    "RFIN":     {"type": "float[NRAYM]", "group": "ray_init", "description": "launch frequency [Hz]"},
    "RPIN":     {"type": "float[NRAYM]", "group": "ray_init", "description": "launch R position [m]"},
    "ZPIN":     {"type": "float[NRAYM]", "group": "ray_init", "description": "launch Z position [m]"},
    "PHIIN":    {"type": "float[NRAYM]", "group": "ray_init", "description": "launch toroidal angle [rad]"},
    "ANGTIN":   {"type": "float[NRAYM]", "group": "ray_init", "description": "launch toroidal ray angle [rad]"},
    "ANGPIN":   {"type": "float[NRAYM]", "group": "ray_init", "description": "launch poloidal ray angle [rad]"},
    "RNPHIN":   {"type": "float[NRAYM]", "group": "ray_init", "description": "launch n_phi (parallel index)"},
    "RNZIN":    {"type": "float[NRAYM]", "group": "ray_init", "description": "launch n_Z (vertical index)"},
    "MODEWIN":  {"type": "int[NRAYM]",   "group": "ray_init", "description": "wave-mode selector per ray"},
    "UUIN":     {"type": "float[NRAYM]", "group": "ray_init", "description": "launch beam amplitude"},
    "RBRADAIN": {"type": "float[NRAYM]", "group": "ray_init", "description": "beam radius a (ellipse semi-axis)"},
    "RBRADBIN": {"type": "float[NRAYM]", "group": "ray_init", "description": "beam radius b (ellipse semi-axis)"},
    "RCURVAIN": {"type": "float[NRAYM]", "group": "ray_init", "description": "beam curvature a"},
    "RCURVBIN": {"type": "float[NRAYM]", "group": "ray_init", "description": "beam curvature b"},
    "RNKIN":    {"type": "float[NRAYM]", "group": "ray_init", "description": "launch |n| (refractive index)"},
    # --- ray control scalars ---------------------------------------
    "SMAX":          {"type": "float", "group": "ray_ctrl", "description": "max ray-path length"},
    "DELS":          {"type": "float", "group": "ray_ctrl", "description": "ray integration step"},
    "UUMIN":         {"type": "float", "group": "ray_ctrl", "description": "ray-amplitude cutoff"},
    "EPSRAY":        {"type": "float", "group": "ray_ctrl", "description": "ray-integration tolerance"},
    "DELRAY":        {"type": "float", "group": "ray_ctrl", "description": "ray step control"},
    "DELDER":        {"type": "float", "group": "ray_ctrl", "description": "derivative step"},
    "DELKR":         {"type": "float", "group": "ray_ctrl", "description": "k-space step"},
    "EPSNW":         {"type": "float", "group": "ray_ctrl", "description": "Newton tolerance"},
    "EPSD0":         {"type": "float", "group": "ray_ctrl", "description": "dispersion tolerance"},
    "pne_threshold": {"type": "float", "group": "ray_ctrl", "description": "density threshold for ray launch"},
    "bdr_threshold": {"type": "float", "group": "ray_ctrl", "description": "boundary threshold for ray launch"},
    # --- mode switches ---------------------------------------------
    "mode_beam":     {"type": "int", "group": "mode", "description": "beam model switch"},
    "mode_wline":    {"type": "int", "group": "mode", "description": "wave-line model switch"},
    "mode_fig":      {"type": "int", "group": "mode", "description": "figure-output switch"},
    "model_fdrv":    {"type": "int", "group": "mode", "description": "Fokker-Planck drive model"},
    "model_fdrv_ds": {"type": "int", "group": "mode", "description": "F-P drive ds model"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "WrxState (wire format of wrxlib.state.WrxState.to_dict())",
    "properties": {
        "NRAYMAX": {"type": "integer", "description": "number of rays actually used"},
        "NSTPMAX": {"type": "integer", "description": "max ray steps used"},
        "NSAMAX":  {"type": "integer", "description": "number of species in use (for per-species power)"},
        "NSMAX":   {"type": "integer", "description": "NSMAX (plasma species count)"},
        "MODELG":  {"type": "integer", "description": "MODELG equilibrium model switch"},
        "MDLWRQ":  {"type": "integer", "description": "MDLWRQ power-deposition switch"},
        "scalars": {
            "type": "object",
            "description": "global scalars; currently {'pwr_tot': total absorbed power}",
            "additionalProperties": {"type": "number"},
        },
        "rays": {
            "type": "array",
            "description": "per-ray info, length = NRAYMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NRAY":     {"type": "integer", "description": "1-origin ray index"},
                    "nstp_end": {"type": "integer", "description": "last step index reached"},
                    "pwr":      {"type": "number",  "description": "absorbed power for this ray"},
                    "pwr_nsa":  {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "per-species absorbed power (length NSAMAX)",
                    },
                },
            },
        },
        "profile_rs": {
            "type": "array",
            "description": "per-species peak-power info on rs axis, length = NSAMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NSA":        {"type": "integer", "description": "1-origin species index"},
                    "pos_pwrmax": {"type": "number",  "description": "peak-power position (rs axis)"},
                    "pwrmax":     {"type": "number",  "description": "peak-power value (rs axis)"},
                    "pwr":        {"type": "number",  "description": "total absorbed power for species"},
                },
            },
        },
        "profile_rl": {
            "type": "array",
            "description": "per-species peak-power info on rl axis, length = NSAMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NSA":        {"type": "integer", "description": "1-origin species index"},
                    "pos_pwrmax": {"type": "number",  "description": "peak-power position (rl axis)"},
                    "pwrmax":     {"type": "number",  "description": "peak-power value (rl axis)"},
                },
            },
        },
    },
    "required": [
        "NRAYMAX", "NSTPMAX", "NSAMAX", "NSMAX",
        "MODELG", "MDLWRQ", "scalars", "rays",
        "profile_rs", "profile_rl",
    ],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Wrxlib` instance for this server."""

    def __init__(self) -> None:
        self.wrx: Optional[Wrxlib] = None

    def ensure_open(self) -> Wrxlib:
        """Return the live handle, opening one if needed."""
        if self.wrx is None or self.wrx.closed:
            self.wrx = Wrxlib()
        return self.wrx

    def close(self) -> None:
        if self.wrx is not None and not self.wrx.closed:
            self.wrx.close()
        self.wrx = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(wrx: Wrxlib, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Wrxlib.set_param`.
    * ``list`` / ``tuple``          — element at 1-origin index ``i``
      is applied as ``NAME[i]``.
    * ``dict[int, float]``          — sparse {index: value}, applied as
      ``NAME[index]``; indices must be 1-origin.

    Unlike :mod:`tr_mcp`, wrxlib has no string parameters so those are
    rejected here with a clear message.

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
        # bool is a subclass of int; reject as ambiguous up-front
        # before any shape-specific branches.
        if isinstance(value, bool):
            raise WrxlibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                # Nested bool: subclass of int would be coerced to 1.0
                # by float() — reject before float() so the top-level
                # bool contract also holds inside bulk arrays.
                if isinstance(v, bool):
                    raise WrxlibError(
                        f"unsupported value type for '{key}': "
                        f"bool (use 0/1)"
                    )
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise WrxlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                wrx.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                # Reject bool keys AND bool values up-front; int(True)
                # == 1 would otherwise silently land in NAME[1].
                if isinstance(idx, bool):
                    raise WrxlibError(
                        f"invalid index for '{name}': bool (use 0/1)"
                    )
                if isinstance(v, bool):
                    raise WrxlibError(
                        f"unsupported value type for '{name}[{idx}]': "
                        f"bool (use 0/1)"
                    )
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise WrxlibError(
                        f"invalid index for '{name}': {idx!r} ({exc})"
                    ) from exc
                key = f"{name}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise WrxlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                wrx.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise WrxlibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            wrx.set_param(name, coerced)
            applied.append(name)
        else:
            raise WrxlibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_wrxlib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate a wrxlib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, WrxlibParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, WrxlibStateError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, WrxlibRunError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, WrxlibNotImplementedError):
        msg = f"not implemented in this libwrxapi.so build: {exc}"
    elif isinstance(exc, WrxlibInitError):
        msg = f"wrx_init failed: {exc}"
    elif isinstance(exc, WrxlibError):
        msg = f"wrxlib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libwrxapi.so not found: {exc}. "
            "Build it via `make -C wrx libwrxapi.so` or set WRXLIB_PATH."
        )
    else:
        # Unexpected — re-wrap so MCP still gets a clean error.
        msg = f"{type(exc).__name__}: {exc}"
    return ToolError(msg)  # type: ignore[operator,call-arg]


# =====================================================================
# WRX_RUN_OK gate.
#
# libwrxapi.so (L-4 build) retains an unresolved libgrf::grd1d reference
# via wrcalpwr.f90, so calling wrx_run through dlopen may segfault.
# Gate wrx_run on WRX_RUN_OK=1 so an LLM gets a clear error instead of
# crashing the whole server process.
# =====================================================================
_WRX_RUN_GATE_MSG = (
    "wrx_run is disabled because WRX_RUN_OK is not set to '1'. "
    "Calling wrx_run through the shared library can segfault due to an "
    "unresolved libgrf::grd1d reference in wrcalpwr.f90 (see "
    "python/wrxlib/README.md 'Known limitation: wrx_run in the shared "
    "build'). Set WRX_RUN_OK=1 only if your local libwrxapi.so has been "
    "patched to resolve grd1d."
)


def _wrx_run_enabled() -> bool:
    """Return True iff the WRX_RUN_OK=1 gate is open."""
    return os.environ.get("WRX_RUN_OK", "") == "1"


# =====================================================================
# Tool handler implementations (plain Python, unit-testable).
# =====================================================================
def handle_init() -> str:
    try:
        STATE.ensure_open()
        return "wrx library initialized"
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        wrx = STATE.ensure_open()
        wrx.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        wrx = STATE.ensure_open()
        applied = _apply_bulk_params(wrx, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_run(nray_request: int = 0) -> str:
    if not _wrx_run_enabled():
        raise ToolError(_WRX_RUN_GATE_MSG)  # type: ignore[call-arg]
    try:
        wrx = STATE.ensure_open()
        wrx.run(int(nray_request))
        return f"wrx_run completed (nray_request={nray_request})"
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        wrx = STATE.ensure_open()
        return wrx.get_state().to_dict()
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "wrx library finalized"
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "wrx",
        "count": len(PARAMETER_REGISTRY),
        "array_syntax": "Use NAME[i] (1-origin) for array elements, e.g. RFIN[1].",
        "parameters": PARAMETER_REGISTRY,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    nray_request: int = 0,
) -> Dict[str, Any]:
    """One-shot init -> set_params -> run -> get_state.

    Codex MCP audit 2026-04-22 (HIGH) fix: force-close any prior
    :class:`Wrxlib` handle before opening a fresh one so this call is
    genuinely isolated. Without the close, prior tool calls in the
    same MCP server process leak their parameter mutations (MODELG,
    RFIN, NRAYMAX, mesh sizes, etc.) into the one-shot run because
    libwrxapi.so holds singleton Fortran state -- the user-facing
    contract ("init + set + run + get_state") requires a fresh init
    each call. Mirrors the canonical fix in
    ``eq_mcp.server.handle_run_and_get_state``.

    The WRX_RUN_OK gate is still consulted up-front so we do not
    teardown a perfectly good handle when the caller is gated out.
    """
    if not _wrx_run_enabled():
        raise ToolError(_WRX_RUN_GATE_MSG)  # type: ignore[call-arg]
    try:
        # Force a fresh handle: STATE.close() finalizes any prior
        # Wrxlib, then ensure_open() opens a new one. Mirrors the
        # documented init step of the one-shot contract.
        STATE.close()
        wrx = STATE.ensure_open()
        if params:
            _apply_bulk_params(wrx, params)
        wrx.run(int(nray_request))
        return wrx.get_state().to_dict()
    except Exception as exc:
        raise _wrap_wrxlib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 9 wrx tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-wrx",
        instructions=(
            "TASK/WRX ray-tracing MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "or `set_params`, execute ray tracing with `run`, and read "
            "state with `get_state`. Use `describe_parameters` to "
            "discover valid parameter names. `run_and_get_state` is a "
            "convenience one-shot wrapper. Note: `set_params` is "
            "*non-transactional* — on a partial failure, parameters "
            "applied before the failing key remain set. "
            "NOTE: `run` / `run_and_get_state` require WRX_RUN_OK=1 in "
            "the environment because of a known libgrf::grd1d dlopen "
            "issue; see README."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the wrx library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set a wrx parameter by name.

        Use ``NAME[i]`` (1-origin) for array elements, e.g. ``RFIN[1]``.
        See `describe_parameters` for the full registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set wrx parameters.

        ``params`` values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (1-origin sparse array)

        (wrxlib has no string parameters.)

        **Non-transactional**: keys are applied in iteration order and
        a failure on key ``N`` leaves keys ``0..N-1`` already written
        to the underlying Fortran library. There is no automatic
        rollback in this PR — pre-validate with ``describe_parameters``
        if a clean rollback matters. (Two-pass dry-run + apply is
        tracked as a follow-up task.)
        """
        return handle_set_params(params)

    @mcp.tool()
    def run(nray_request: int = 0) -> str:
        """Execute ``wrx_run`` (ray tracing).

        ``nray_request > 0`` overrides NRAYMAX set by the namelist /
        set_param. ``nray_request <= 0`` keeps the configured NRAYMAX.

        NOTE: wrx_run through dlopen may segfault unless the build has
        resolved the ``libgrf::grd1d`` dependency (see README). This
        tool therefore refuses to proceed unless ``WRX_RUN_OK=1`` is
        set in the server process environment.
        """
        return handle_run(nray_request)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current simulation state.

        Returns a dict with ``NRAYMAX``, ``NSTPMAX``, ``NSAMAX``,
        ``NSMAX``, ``MODELG``, ``MDLWRQ``, ``scalars``, ``rays``,
        ``profile_rs``, ``profile_rl``. Schema also available via
        `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release wrx library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported wrx parameters.

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
        nray_request: int = 0,
    ) -> Dict[str, Any]:
        """Convenience: init + set_params + run + get_state in one call.

        Equivalent to::

            init()
            set_params(params)
            run(nray_request)
            return get_state()

        Same ``WRX_RUN_OK=1`` gate as :func:`run`.
        """
        return handle_run_and_get_state(params, nray_request)

    return mcp


def main(argv: Optional[List[str]] = None) -> int:
    """Console-script entry point.

    Runs the FastMCP stdio server. Exits cleanly on SIGINT.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(
            "wrx-mcp — Model Context Protocol server for TASK/WRX\n"
            "\n"
            "Usage:\n"
            "  python -m wrx_mcp.server   # run over stdio (default)\n"
            "  wrx-mcp                    # same, via installed script\n"
            "  wrx-mcp --help             # show this help\n"
            "  wrx-mcp --print-tools      # list registered tools\n"
            "\n"
            "Environment:\n"
            "  WRXLIB_PATH  override path to libwrxapi.so\n"
            "  WRX_RUN_OK   set to '1' to allow the `run` / \n"
            "               `run_and_get_state` tools. Unset by default\n"
            "               because libwrxapi.so may segfault inside\n"
            "               wrx_run via libgrf::grd1d.\n"
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
