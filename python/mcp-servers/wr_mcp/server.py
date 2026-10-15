"""FastMCP server exposing the TASK/WR ray-tracing library as MCP tools.

Entry point for ``python -m wr_mcp.server`` or the ``wr-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One :class:`Wrlib` instance per server process.** libwrapi.so holds
  Fortran COMMON-block singleton state, so there is at most one live
  handle. Subsequent ``init`` calls close the old handle and re-open a
  fresh one so that an LLM can "start over" without restarting the
  server.
* **Post-finalize reset invariant.** After ``finalize``, the next
  data-returning tool auto-reopens a fresh Fortran state. This mirrors
  the PR #36 Bugbot HIGH finding for trlib: callers must not assume
  the previous simulation state survives across a finalize → init
  boundary. The recommended cycle is
  ``init → set_params → run → get_state → finalize`` (one simulation
  per cycle). See README §10 for details.
* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** :class:`wrlib.WrlibError` subclasses are re-raised
  as :class:`ToolError` with a human-readable message. The LLM sees
  the error string and can often recover (e.g. by calling ``init``
  first).

The server is intentionally small — the real heavy lifting is in
:mod:`wrlib`. This file mirrors ``tr_mcp/server.py`` with only the
module-specific names swapped so that future ti / wrx / fp servers
can follow the same pattern.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``wrlib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/wr_mcp/server.py
# and we want to import ``wrlib`` from
#   <repo>/python/wrlib/
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
# wrlib import (always available from the repo).
# ---------------------------------------------------------------------
from wrlib import (  # noqa: E402
    Wrlib,
    WrlibError,
    WrlibInitError,
    WrlibParamError,
    WrlibStateError,
    WrlibRunError,
    WrlibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Keeping these in Python (rather than re-parsing wr_param_registry.f90)
# is a deliberate short-term choice: the LLM-facing description is more
# valuable than the last ounce of DRYness. When the Fortran registry
# changes we'll mirror it here.
# =====================================================================
SupportedValue = Union[float, int, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- A. geometry / device scalars (plcomm) ----------------------
    "RR":     {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":     {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RB":     {"type": "float", "group": "geometry", "description": "wall/boundary radius [m]"},
    "RKAP":   {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":   {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":     {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "Q0":     {"type": "float", "group": "geometry", "description": "safety factor on axis"},
    "QA":     {"type": "float", "group": "geometry", "description": "safety factor at edge"},
    "RIP":    {"type": "float", "group": "geometry", "description": "plasma current [MA]"},

    # --- B. plasma scalars / arrays (plcomm) -----------------------
    "NSMAX":  {"type": "int",        "group": "plasma", "description": "number of species"},
    "PA":     {"type": "float[NSM]", "group": "plasma", "description": "atomic mass per species (1-origin)"},
    "PZ":     {"type": "float[NSM]", "group": "plasma", "description": "charge number per species"},
    "PN":     {"type": "float[NSM]", "group": "plasma", "description": "initial density per species [10^20 m^-3]"},
    "PNS":    {"type": "float[NSM]", "group": "plasma", "description": "edge (separatrix) density per species"},
    "PTPR":   {"type": "float[NSM]", "group": "plasma", "description": "parallel temperature per species [keV]"},
    "PTPP":   {"type": "float[NSM]", "group": "plasma", "description": "perpendicular temperature per species [keV]"},
    "PTS":    {"type": "float[NSM]", "group": "plasma", "description": "edge temperature per species [keV]"},
    "PU":     {"type": "float[NSM]", "group": "plasma", "description": "initial toroidal velocity per species"},
    "PUS":    {"type": "float[NSM]", "group": "plasma", "description": "edge toroidal velocity per species"},
    "PZCL":   {"type": "float[NSM]", "group": "plasma", "description": "collisional broadening per species"},

    # --- C. profile control (plcomm) -------------------------------
    "PROFN1": {"type": "float[NSM]", "group": "profile", "description": "density profile exponent (inner); idx=0/omit hits (1)"},
    "PROFN2": {"type": "float[NSM]", "group": "profile", "description": "density profile exponent (outer); idx=0/omit hits (1)"},
    "PROFT1": {"type": "float[NSM]", "group": "profile", "description": "temperature profile exponent (inner); idx=0/omit hits (1)"},
    "PROFT2": {"type": "float[NSM]", "group": "profile", "description": "temperature profile exponent (outer); idx=0/omit hits (1)"},
    "PROFU1": {"type": "float[NSM]", "group": "profile", "description": "rotation profile exponent (inner); idx=0/omit hits (1)"},
    "PROFU2": {"type": "float[NSM]", "group": "profile", "description": "rotation profile exponent (outer); idx=0/omit hits (1)"},
    "RHOMIN": {"type": "float",      "group": "profile", "description": "min-q radius (rho)"},
    "QMIN":   {"type": "float",      "group": "profile", "description": "minimum safety factor"},
    "RHOITB": {"type": "float[NSM]", "group": "profile", "description": "ITB radius per species; idx=0/omit hits (1)"},
    "PNITB":  {"type": "float[NSM]", "group": "profile", "description": "ITB density per species; idx=0/omit hits (1)"},
    "PTITB":  {"type": "float[NSM]", "group": "profile", "description": "ITB temperature per species; idx=0/omit hits (1)"},
    "PUITB":  {"type": "float[NSM]", "group": "profile", "description": "ITB rotation per species; idx=0/omit hits (1)"},
    "RHOEDG": {"type": "float",      "group": "profile", "description": "edge rho for profile blending"},
    "PPN0":   {"type": "float",      "group": "profile", "description": "edge density floor"},
    "PTN0":   {"type": "float",      "group": "profile", "description": "edge temperature floor"},
    "RF_PL":  {"type": "float",      "group": "profile", "description": "plasma reference frequency [MHz]"},

    # --- D. model switches (plcomm / dpcomm) -----------------------
    "MODELG":      {"type": "int",        "group": "modules", "description": "equilibrium/geometry selector"},
    "MODELQ":      {"type": "int",        "group": "modules", "description": "safety-factor profile selector"},
    "MODEL_PROF":  {"type": "int",        "group": "modules", "description": "profile model selector"},
    "MODEL_NPROF": {"type": "int",        "group": "modules", "description": "density-profile model selector"},
    "MODEFW":      {"type": "int",        "group": "modules", "description": "FW model selector"},
    "MODEFR":      {"type": "int",        "group": "modules", "description": "FR model selector"},
    "IDEBUG":      {"type": "int",        "group": "modules", "description": "debug verbosity level"},
    "MODELP":      {"type": "int[NSM]",   "group": "modules", "description": "plasma model per species"},
    "MODELV":      {"type": "int[NSM]",   "group": "modules", "description": "velocity-distribution model per species"},
    "NCMIN":       {"type": "int[NSM]",   "group": "modules", "description": "min cyclotron harmonic per species"},
    "NCMAX":       {"type": "int[NSM]",   "group": "modules", "description": "max cyclotron harmonic per species"},

    # --- E. WR scalars (wrcomm_parm) -------------------------------
    "NRAYMAX":       {"type": "int",   "group": "wr",        "description": "number of rays to launch (<= WR_MAX_NRAYMAX=100)"},
    "NSTPMAX":       {"type": "int",   "group": "wr",        "description": "max integration steps per ray"},
    "NRSMAX":        {"type": "int",   "group": "wr",        "description": "minor-radius profile bins (<= WR_MAX_NRSMAX=200)"},
    "NRLMAX":        {"type": "int",   "group": "wr",        "description": "major-radius profile bins (<= WR_MAX_NRLMAX=400)"},
    "LMAXNW":        {"type": "int",   "group": "wr",        "description": "max Newton iterations for dispersion solve"},
    "mode_beam":     {"type": "int",   "group": "wr",        "description": "beam-tracing mode switch"},
    "MDLWRI":        {"type": "int",   "group": "wr",        "description": "WR input-mode selector"},
    "MDLWRG":        {"type": "int",   "group": "wr",        "description": "WR graphics-mode selector"},
    "MDLWRP":        {"type": "int",   "group": "wr",        "description": "WR power-deposition model"},
    "MDLWRQ":        {"type": "int",   "group": "wr",        "description": "WR CD-model selector"},
    "MDLWRW":        {"type": "int",   "group": "wr",        "description": "WR line-broadening model"},
    "MODEW":         {"type": "int",   "group": "wr",        "description": "wave-mode selector (O/X)"},
    "nres_max":      {"type": "int",   "group": "wr",        "description": "max resonances considered"},
    "nres_type":     {"type": "int",   "group": "wr",        "description": "resonance-type selector"},
    "mode_wline":    {"type": "int",   "group": "wr",        "description": "warm-plasma dispersion branch"},
    "SMAX":          {"type": "float", "group": "ray",       "description": "max ray arc length [m]"},
    "DELS":          {"type": "float", "group": "ray",       "description": "ray step size [m]"},
    "UUMIN":         {"type": "float", "group": "ray",       "description": "min ray power fraction (termination)"},
    "EPSRAY":        {"type": "float", "group": "ray",       "description": "ray-integrator tolerance"},
    "DELRAY":        {"type": "float", "group": "ray",       "description": "ray-position step for finite diffs"},
    "DELDER":        {"type": "float", "group": "ray",       "description": "derivative step for ray RHS"},
    "DELKR":         {"type": "float", "group": "ray",       "description": "k_r step for dispersion solve"},
    "EPSNW":         {"type": "float", "group": "ray",       "description": "Newton tolerance for dispersion solve"},
    "RF":            {"type": "float", "group": "wave",      "description": "default wave frequency [GHz]"},
    "RPI":           {"type": "float", "group": "wave",      "description": "default ray R-position [m]"},
    "ZPI":           {"type": "float", "group": "wave",      "description": "default ray Z-position [m]"},
    "PHII":          {"type": "float", "group": "wave",      "description": "default ray toroidal angle [deg]"},
    "RNZI":          {"type": "float", "group": "wave",      "description": "default ray parallel n_z"},
    "RNPHII":        {"type": "float", "group": "wave",      "description": "default ray toroidal n_phi"},
    "RKR0":          {"type": "float", "group": "wave",      "description": "default ray initial k_r"},
    "UUI":           {"type": "float", "group": "wave",      "description": "default ray initial power weight"},
    "RCURVA":        {"type": "float", "group": "beam",      "description": "default beam curvature A"},
    "RCURVB":        {"type": "float", "group": "beam",      "description": "default beam curvature B"},
    "RBRADA":        {"type": "float", "group": "beam",      "description": "default beam radius A [m]"},
    "RBRADB":        {"type": "float", "group": "beam",      "description": "default beam radius B [m]"},
    "pne_threshold": {"type": "float", "group": "wr",        "description": "n_e threshold for ray start"},
    "bdr_threshold": {"type": "float", "group": "wr",        "description": "boundary-crossing threshold"},
    "Rmax_wr":       {"type": "float", "group": "wr",        "description": "R-domain max [m]"},
    "Rmin_wr":       {"type": "float", "group": "wr",        "description": "R-domain min [m]"},
    "Zmax_wr":       {"type": "float", "group": "wr",        "description": "Z-domain max [m]"},
    "Zmin_wr":       {"type": "float", "group": "wr",        "description": "Z-domain min [m]"},

    # --- F. WR per-ray arrays (wrcomm_parm, sized NRAYM) -----------
    "RFIN":     {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray frequency [GHz] (1-origin)"},
    "RPIN":     {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray R-position [m]"},
    "ZPIN":     {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray Z-position [m]"},
    "PHIIN":    {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray toroidal angle [deg]"},
    "RKRIN":    {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray initial k_r"},
    "RNZIN":    {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray parallel n_z"},
    "RNPHIIN":  {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray toroidal n_phi"},
    "ANGZIN":   {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray poloidal launch angle [deg]"},
    "ANGPHIN":  {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray toroidal launch angle [deg]"},
    "UUIN":     {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray initial power weight"},
    "RCURVAIN": {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray beam curvature A"},
    "RCURVBIN": {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray beam curvature B"},
    "RBRADAIN": {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray beam radius A [m]"},
    "RBRADBIN": {"type": "float[NRAYM]", "group": "rays",  "description": "per-ray beam radius B [m]"},
    "MODEWIN":  {"type": "int[NRAYM]",   "group": "rays",  "description": "per-ray wave-mode selector (O/X)"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "WrState (wire format of wrlib.state.WrState.to_dict())",
    "properties": {
        "NRAYMAX": {"type": "integer", "description": "rays actually in use"},
        "NRSMAX":  {"type": "integer", "description": "minor-radius profile bins in use"},
        "NRLMAX":  {"type": "integer", "description": "major-radius profile bins in use"},
        "scalars": {
            "type": "object",
            "description": (
                "4 global peak-power scalars: "
                "pos_pwrmax_rs, pwrmax_rs, pos_pwrmax_rl, pwrmax_rl"
            ),
            "additionalProperties": {"type": "number"},
        },
        "rays": {
            "type": "array",
            "description": "per-ray summary, length = NRAYMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NRAY":          {"type": "integer", "description": "1-origin ray index"},
                    "nstp_end":      {"type": "integer", "description": "end-step index"},
                    "pos_pwrmax_rs": {"type": "number",  "description": "minor-radius position of per-ray pwrmax"},
                    "pwrmax_rs":     {"type": "number",  "description": "per-ray peak power (minor radius)"},
                    "pos_pwrmax_rl": {"type": "number",  "description": "major-radius position of per-ray pwrmax"},
                    "pwrmax_rl":     {"type": "number",  "description": "per-ray peak power (major radius)"},
                    "rays_end": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "RAYS(0:NEQ) end-state, always 9 entries",
                    },
                },
            },
        },
        "profile_rs": {
            "type": "array",
            "description": "minor-radius power profile, length = NRSMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NRS": {"type": "integer", "description": "1-origin bin index"},
                    "pos": {"type": "number",  "description": "minor-radius coordinate"},
                    "pwr": {"type": "number",  "description": "deposited power"},
                },
            },
        },
        "profile_rl": {
            "type": "array",
            "description": "major-radius power profile, length = NRLMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NRL": {"type": "integer", "description": "1-origin bin index"},
                    "pos": {"type": "number",  "description": "major-radius coordinate"},
                    "pwr": {"type": "number",  "description": "deposited power"},
                },
            },
        },
    },
    "required": ["NRAYMAX", "NRSMAX", "NRLMAX", "scalars", "rays", "profile_rs", "profile_rl"],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Wrlib` instance for this server."""

    def __init__(self) -> None:
        self.wr: Optional[Wrlib] = None

    def ensure_open(self) -> Wrlib:
        """Return the live handle, opening one if needed.

        Respects the post-finalize reset invariant: after
        :meth:`close`, the next call re-opens a fresh Fortran state.
        """
        if self.wr is None or self.wr.closed:
            self.wr = Wrlib()
        return self.wr

    def close(self) -> None:
        if self.wr is not None and not self.wr.closed:
            self.wr.close()
        self.wr = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(wr: Wrlib, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``) — plain :py:meth:`Wrlib.set_param`.
    * ``list`` / ``tuple``        — element at 1-origin index ``i`` is
      applied as ``NAME[i]``.
    * ``dict[int, float]``        — sparse ``{index: value}``, applied as
      ``NAME[index]``; indices must be 1-origin.

    wrlib has no string-valued parameter equivalent to trlib's KNAMEQ
    at this layer, so strings are rejected with a clear error.

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
            raise WrlibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                # Nested bool: subclass of int would be coerced to 1.0
                # by float() — reject before float() so the top-level
                # bool contract also holds inside bulk arrays.
                if isinstance(v, bool):
                    raise WrlibError(
                        f"unsupported value type for '{key}': "
                        f"bool (use 0/1)"
                    )
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise WrlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                wr.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                # Reject bool keys AND bool values up-front; int(True)
                # == 1 would otherwise silently land in NAME[1].
                if isinstance(idx, bool):
                    raise WrlibError(
                        f"invalid index for '{name}': bool (use 0/1)"
                    )
                if isinstance(v, bool):
                    raise WrlibError(
                        f"unsupported value type for '{name}[{idx}]': "
                        f"bool (use 0/1)"
                    )
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise WrlibError(
                        f"invalid index for '{name}': {idx!r} ({exc})"
                    ) from exc
                key = f"{name}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise WrlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                wr.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise WrlibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            wr.set_param(name, coerced)
            applied.append(name)
        else:
            raise WrlibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_wrlib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate a wrlib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, WrlibParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, WrlibStateError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, WrlibRunError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, WrlibNotImplementedError):
        msg = f"not implemented in this libwrapi.so build: {exc}"
    elif isinstance(exc, WrlibInitError):
        msg = f"wr_init failed: {exc}"
    elif isinstance(exc, WrlibError):
        msg = f"wrlib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libwrapi.so not found: {exc}. "
            "Build it via `make -C wr libwrapi.so` or set WRLIB_PATH."
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
        return "wr library initialized"
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        wr = STATE.ensure_open()
        wr.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        wr = STATE.ensure_open()
        applied = _apply_bulk_params(wr, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_run(nray_request: int = 0) -> str:
    """Execute one ray-tracing sweep.

    ``nray_request > 0`` overrides the namelist NRAYMAX before
    allocation; ``nray_request <= 0`` (the default) keeps whatever
    NRAYMAX was set via init / set_param.
    """
    try:
        wr = STATE.ensure_open()
        wr.run(int(nray_request))
        return f"ran ray tracing (nray_request={nray_request})"
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        wr = STATE.ensure_open()
        return wr.get_state().to_dict()
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "wr library finalized"
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "wr",
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
    :class:`Wrlib` handle before opening a fresh one so this call is
    genuinely isolated. Without the close, prior tool calls in the
    same MCP server process leak their parameter mutations (MODELG,
    RFIN, NRAYMAX, mesh sizes, etc.) into the one-shot run because
    libwrapi.so holds singleton Fortran state -- the user-facing
    contract ("init + set + run + get_state") requires a fresh init
    each call. Mirrors the canonical fix in
    ``eq_mcp.server.handle_run_and_get_state``.
    """
    try:
        # Force a fresh handle: STATE.close() finalizes any prior Wrlib,
        # then ensure_open() opens a new one. Mirrors the documented
        # init step of the one-shot contract.
        STATE.close()
        wr = STATE.ensure_open()
        if params:
            _apply_bulk_params(wr, params)
        wr.run(int(nray_request))
        return wr.get_state().to_dict()
    except Exception as exc:
        raise _wrap_wrlib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 9 wr tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9,<2'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-wr",
        instructions=(
            "TASK/WR ray-tracing MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "or `set_params`, launch the sweep with `run`, and read "
            "state with `get_state`. Use `describe_parameters` to "
            "discover valid parameter names. `run_and_get_state` is a "
            "convenience one-shot wrapper. Note: `set_params` is "
            "*non-transactional* — on a partial failure, parameters "
            "applied before the failing key remain set. After "
            "`finalize`, the next call auto-reinitializes to default "
            "parameters — treat init → run → get_state → finalize as "
            "one simulation."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the wr library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set a wr parameter by name.

        Use ``NAME[i]`` (1-origin) for array elements, e.g. ``RFIN[1]``
        or ``PN[1]``. See `describe_parameters` for the full registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set wr parameters.

        ``params`` values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (1-origin sparse array)

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
        """Launch one ray-tracing sweep.

        ``nray_request > 0`` overrides the namelist ``NRAYMAX`` for
        this call; ``0`` (the default) keeps whatever ``NRAYMAX`` was
        set via `init` / `set_param`.
        """
        return handle_run(nray_request)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current ray-tracing state.

        Returns a dict with ``NRAYMAX``, ``NRSMAX``, ``NRLMAX``,
        ``scalars`` (4 global peak-power values), ``rays`` (per-ray
        summary), ``profile_rs`` (minor-radius power profile) and
        ``profile_rl`` (major-radius power profile). Schema also
        available via `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release wr library resources.

        Safe to call multiple times. After `finalize`, any
        data-returning tool will auto-reinitialize the library to
        defaults — the previous run's state does NOT survive a
        finalize → init cycle.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported wr parameters.

        Each entry exposes ``type``, ``group``, and ``description``.
        Use this to discover valid parameter names before `set_param`.
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
            "wr-mcp — Model Context Protocol server for TASK/WR\n"
            "\n"
            "Usage:\n"
            "  python -m wr_mcp.server    # run over stdio (default)\n"
            "  wr-mcp                     # same, via installed script\n"
            "  wr-mcp --help              # show this help\n"
            "  wr-mcp --print-tools       # list registered tools\n"
            "\n"
            "Environment:\n"
            "  WRLIB_PATH   override path to libwrapi.so\n"
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
            "       pip install 'mcp>=0.9,<2'\n"
        )
        return 2

    server = build_server()
    # FastMCP >=0.9 exposes .run() for stdio transport by default.
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
