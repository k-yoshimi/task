"""FastMCP server exposing the TASK/TR library as MCP tools.

Entry point for ``python -m tr_mcp.server`` or the ``tr-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `Trlib` instance per server process.** libtrapi.so holds
  Fortran COMMON-block singleton state, so there is at most one live
  handle. Subsequent ``init`` calls close the old handle and re-open a
  fresh one so that an LLM can "start over" without restarting the
  server.
* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** `trlib.TrlibError` subclasses are re-raised as
  `ToolError` with a human-readable message. The LLM sees the error
  string and can often recover (e.g. by calling ``init`` first).

The server is intentionally small — the real heavy lifting is in
:mod:`trlib`. Adding new modules (ti / wr / wrx / fp) should be a
matter of copying this file and swapping the backing library.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``trlib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/tr_mcp/server.py
# and we want to import ``trlib`` from
#   <repo>/python/trlib/
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
# trlib import (always available from the repo).
# ---------------------------------------------------------------------
from trlib import (  # noqa: E402
    Trlib,
    TrlibError,
    TrlibInitError,
    TrlibParamError,
    TrlibStateError,
    TrlibRunError,
    TrlibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Keeping these in Python (rather than re-parsing tr_param_registry.f90)
# is a deliberate short-term choice: the LLM-facing description is more
# valuable than the last ounce of DRYness. When the Fortran registry
# changes we'll mirror it here.
# =====================================================================
# Includes `str` for string-valued parameters like KNAMEQ / MODELG
# (set via trlib.Trlib.set_param_str).
SupportedValue = Union[float, int, str, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- geometry / device ------------------------------------------
    "RR":     {"type": "float", "group": "geometry",     "description": "major radius [m]"},
    "RA":     {"type": "float", "group": "geometry",     "description": "minor radius [m]"},
    "RKAP":   {"type": "float", "group": "geometry",     "description": "plasma elongation"},
    "RDLT":   {"type": "float", "group": "geometry",     "description": "plasma triangularity"},
    "BB":     {"type": "float", "group": "geometry",     "description": "toroidal field on axis [T]"},
    "PHIA":   {"type": "float", "group": "geometry",     "description": "plasma surface toroidal flux [Wb]"},
    "MODELG": {"type": "int",   "group": "geometry",     "description": "equilibrium/geometry selector"},
    # --- plasma arrays (1..NSMM) ------------------------------------
    "NSMAX":  {"type": "int",   "group": "plasma",       "description": "number of species"},
    "PA":     {"type": "float[NSMM]", "group": "plasma", "description": "atomic mass per species (1-origin)"},
    "PZ":     {"type": "float[NSMM]", "group": "plasma", "description": "charge number per species"},
    "PN":     {"type": "float[NSMM]", "group": "plasma", "description": "initial density per species [10^20 m^-3]"},
    "PNS":    {"type": "float[NSMM]", "group": "plasma", "description": "edge (separatrix) density per species"},
    "PT":     {"type": "float[NSMM]", "group": "plasma", "description": "initial temperature per species [keV]"},
    "PTS":    {"type": "float[NSMM]", "group": "plasma", "description": "edge temperature per species [keV]"},
    "PROFN1": {"type": "float", "group": "plasma",       "description": "density profile parameter"},
    "PROFN2": {"type": "float", "group": "plasma",       "description": "density profile parameter"},
    "PNC":    {"type": "float", "group": "plasma",       "description": "impurity density"},
    "MDLIMP": {"type": "int",   "group": "plasma",       "description": "impurity model selector"},
    # --- current / time --------------------------------------------
    "RIPS":   {"type": "float", "group": "current",      "description": "plasma current at start [MA]"},
    "RIPE":   {"type": "float", "group": "current",      "description": "plasma current at end [MA]"},
    "DT":     {"type": "float", "group": "time",         "description": "time step [s]"},
    "NTMAX":  {"type": "int",   "group": "time",         "description": "max number of steps (per run)"},
    "NTSTEP": {"type": "int",   "group": "time",         "description": "output cadence"},
    "EPSLTR": {"type": "float", "group": "time",         "description": "convergence tolerance"},
    "LMAXTR": {"type": "int",   "group": "time",         "description": "max inner-iteration count"},
    "NGTSTP": {"type": "int",   "group": "time",         "description": "graphics-output cadence (steps)"},
    "NGRSTP": {"type": "int",   "group": "time",         "description": "graphics-output cadence (radial)"},
    # --- transport coefficients ------------------------------------
    "MDLKAI": {"type": "int",   "group": "transport",    "description": "thermal-diffusivity model"},
    "MDLETA": {"type": "int",   "group": "transport",    "description": "resistivity model"},
    "MDLAD":  {"type": "int",   "group": "transport",    "description": "particle-diffusion model"},
    "MDLAVK": {"type": "int",   "group": "transport",    "description": "convection model"},
    "CDW":    {"type": "float[]", "group": "transport",  "description": "drift-wave tuning coefficients (array, 1-origin)"},
    "CHP":    {"type": "float", "group": "transport",    "description": "tuning coefficient"},
    "CK0":    {"type": "float", "group": "transport",    "description": "tuning coefficient"},
    "CK1":    {"type": "float", "group": "transport",    "description": "tuning coefficient"},
    # --- module switches -------------------------------------------
    "MDLNB":  {"type": "int", "group": "modules", "description": "NBI heating module"},
    "MDLEC":  {"type": "int", "group": "modules", "description": "ECRF heating module"},
    "MDLLH":  {"type": "int", "group": "modules", "description": "LH heating module"},
    "MDLIC":  {"type": "int", "group": "modules", "description": "ICRF heating module"},
    "MDLPEL": {"type": "int", "group": "modules", "description": "pellet injection module"},
    "MDLJBS": {"type": "int", "group": "modules", "description": "bootstrap-current model"},
    "MDLST":  {"type": "int", "group": "modules", "description": "sawtooth model"},
    "MDLNF":  {"type": "int", "group": "modules", "description": "neutron/fusion module"},
    "MDLUF":  {"type": "int", "group": "modules", "description": "UFILE I/O mode"},
    # --- heating / current-drive scalars ---------------------------
    "PNBR0":  {"type": "float", "group": "nbi",  "description": "NBI deposition center [m]"},
    "PNBRW":  {"type": "float", "group": "nbi",  "description": "NBI deposition width [m]"},
    "PNBENG": {"type": "float", "group": "nbi",  "description": "NBI beam energy [keV]"},
    "PNBRTG": {"type": "float", "group": "nbi",  "description": "NBI tangency radius [m]"},
    "PICCD":  {"type": "float", "group": "icrf", "description": "ICRF CD efficiency"},
    "PICR0":  {"type": "float", "group": "icrf", "description": "ICRF deposition center"},
    "PICRW":  {"type": "float", "group": "icrf", "description": "ICRF deposition width"},
    "PICNPR": {"type": "float", "group": "icrf", "description": "ICRF parallel index"},
    "PECCD":  {"type": "float", "group": "ecrf", "description": "ECRF CD efficiency"},
    "PECR0":  {"type": "float", "group": "ecrf", "description": "ECRF deposition center"},
    "PECRW":  {"type": "float", "group": "ecrf", "description": "ECRF deposition width"},
    "PECNPR": {"type": "float", "group": "ecrf", "description": "ECRF parallel index"},
    "PLHCD":  {"type": "float", "group": "lh",   "description": "LH CD efficiency"},
    "PLHR0":  {"type": "float", "group": "lh",   "description": "LH deposition center"},
    "PLHRW":  {"type": "float", "group": "lh",   "description": "LH deposition width"},
    "PLHNPR": {"type": "float", "group": "lh",   "description": "LH parallel index"},
    "PLHTOT": {"type": "float", "group": "lh",   "description": "LH total power [MW]"},
    # --- string parameter (set via set_param_str under the hood) ----
    "KNAMEQ": {"type": "str", "group": "io", "description": "equilibrium data file name"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "TrState (wire format of trlib.state.TrState.to_dict())",
    "properties": {
        "NT":    {"type": "integer", "description": "current time-step index"},
        "NRMAX": {"type": "integer", "description": "radial points in use"},
        "NSMAX": {"type": "integer", "description": "species in use"},
        "scalars": {
            "type": "object",
            "description": "13 plasma scalars (T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN, TAUE1, TAUE2, ZEFF0, ALI, RQ1)",
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
    "required": ["NT", "NRMAX", "NSMAX", "scalars", "profile"],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Trlib` instance for this server."""

    def __init__(self) -> None:
        self.tr: Optional[Trlib] = None

    def ensure_open(self) -> Trlib:
        """Return the live handle, opening one if needed."""
        if self.tr is None or self.tr.closed:
            self.tr = Trlib()
        return self.tr

    def close(self) -> None:
        if self.tr is not None and not self.tr.closed:
            self.tr.close()
        self.tr = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(tr: Trlib, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Trlib.set_param`.
    * ``list`` / ``tuple``          — element at 1-origin index ``i``
      is applied as ``NAME[i]``.
    * ``dict[int, float]``          — sparse {index: value}, applied as
      ``NAME[index]``; indices must be 1-origin.
    * ``str``                       — forwarded to
      :py:meth:`Trlib.set_param_str` (e.g. ``KNAMEQ``).

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
            raise TrlibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                # Nested bool: subclass of int would be coerced to 1.0
                # by float() — reject before float() so the top-level
                # bool contract also holds inside bulk arrays.
                if isinstance(v, bool):
                    raise TrlibError(
                        f"unsupported value type for '{key}': "
                        f"bool (use 0/1)"
                    )
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TrlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                tr.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                # Reject bool keys AND bool values up-front; int(True)
                # == 1 would otherwise silently land in NAME[1].
                if isinstance(idx, bool):
                    raise TrlibError(
                        f"invalid index for '{name}': bool (use 0/1)"
                    )
                if isinstance(v, bool):
                    raise TrlibError(
                        f"unsupported value type for '{name}[{idx}]': "
                        f"bool (use 0/1)"
                    )
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise TrlibError(
                        f"invalid index for '{name}': {idx!r} ({exc})"
                    ) from exc
                key = f"{name}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise TrlibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                tr.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, str):
            # String-valued (e.g. KNAMEQ). Requires libtrapi.so with L-6
            # extension; otherwise trlib raises TrlibError with a
            # helpful message, which _wrap will translate.
            tr.set_param_str(name, value)
            applied.append(name)
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise TrlibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            tr.set_param(name, coerced)
            applied.append(name)
        else:
            raise TrlibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_trlib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate a trlib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, TrlibParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, TrlibStateError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, TrlibRunError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, TrlibNotImplementedError):
        msg = f"not implemented in this libtrapi.so build: {exc}"
    elif isinstance(exc, TrlibInitError):
        msg = f"tr_init failed: {exc}"
    elif isinstance(exc, TrlibError):
        msg = f"trlib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libtrapi.so not found: {exc}. "
            "Build it via `make -C tr libtrapi.so` or set TRLIB_PATH."
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
        return "tr library initialized"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        tr = STATE.ensure_open()
        tr.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_set_param_str(name: str, value: str) -> str:
    """Set a string-valued tr parameter (e.g. ``KNAMEQ``).

    Routed through :py:meth:`Trlib.set_param_str`, which requires a
    libtrapi.so built with the L-6 registry extension. Older builds
    raise :class:`TrlibError` with a rebuild hint; that message is
    translated by :func:`_wrap_trlib_error` into a human-readable
    ToolError.
    """
    try:
        tr = STATE.ensure_open()
        tr.set_param_str(name, str(value))
        return f"set {name} = {value!r}"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        tr = STATE.ensure_open()
        applied = _apply_bulk_params(tr, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_run(ntmax: int = 1) -> str:
    try:
        tr = STATE.ensure_open()
        tr.run(int(ntmax))
        return f"advanced {ntmax} time step(s)"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        tr = STATE.ensure_open()
        return tr.get_state().to_dict()
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "tr library finalized"
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "tr",
        "count": len(PARAMETER_REGISTRY),
        "array_syntax": "Use NAME[i] (1-origin) for array elements, e.g. PN[1].",
        "parameters": PARAMETER_REGISTRY,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    ntmax: int = 1,
) -> Dict[str, Any]:
    """One-shot init -> set_params -> run -> get_state.

    Codex MCP audit 2026-04-22 (HIGH) fix: force-close any prior
    :class:`Trlib` handle before opening a fresh one so this call is
    genuinely isolated. Without the close, prior tool calls in the
    same MCP server process leak their parameter mutations (MODELG,
    mesh sizes, NSMAX, etc.) into the one-shot run because libtrapi.so
    holds singleton Fortran state -- the user-facing contract
    ("init + set + run + get_state") requires a fresh init each call.
    Mirrors the canonical fix in ``eq_mcp.server.handle_run_and_get_state``.
    """
    try:
        # Force a fresh handle: STATE.close() finalizes any prior Trlib,
        # then ensure_open() opens a new one. Mirrors the documented
        # init step of the one-shot contract.
        STATE.close()
        tr = STATE.ensure_open()
        if params:
            _apply_bulk_params(tr, params)
        tr.run(int(ntmax))
        return tr.get_state().to_dict()
    except Exception as exc:
        raise _wrap_trlib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 10 tr tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-tr",
        instructions=(
            "TASK/TR transport-code MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "/ `set_param_str` / `set_params`, advance with `run`, and "
            "read state with `get_state`. Use `describe_parameters` to "
            "discover valid parameter names. `run_and_get_state` is a "
            "convenience one-shot wrapper. Note: `set_params` is "
            "*non-transactional* — on a partial failure, parameters "
            "applied before the failing key remain set."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the tr library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set a tr parameter by name.

        Use ``NAME[i]`` (1-origin) for array elements, e.g. ``PN[1]``.
        For string parameters (``KNAMEQ`` etc.) use ``set_param_str``
        instead. See `describe_parameters` for the full registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_param_str(name: str, value: str) -> str:
        """Set a tr string-valued parameter (``KNAMEQ`` etc.).

        Requires a ``libtrapi.so`` built with the L-6 registry
        extension (``make -C tr libtrapi.so``); older builds raise a
        clear "rebuild the shared library" error.
        """
        return handle_set_param_str(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set tr parameters.

        ``params`` values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (1-origin sparse array)
        * a string (for KNAMEQ and similar string-valued parameters)

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

        Returns a dict with ``NT``, ``NRMAX``, ``NSMAX``, ``scalars``
        (13 plasma scalars), and ``profile`` (radial profile array).
        Schema also available via `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release tr library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported tr parameters.

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
            "tr-mcp — Model Context Protocol server for TASK/TR\n"
            "\n"
            "Usage:\n"
            "  python -m tr_mcp.server    # run over stdio (default)\n"
            "  tr-mcp                     # same, via installed script\n"
            "  tr-mcp --help              # show this help\n"
            "  tr-mcp --print-tools       # list registered tools\n"
            "\n"
            "Environment:\n"
            "  TRLIB_PATH   override path to libtrapi.so\n"
            "  PYTHONPATH   must include the repo's python/ directory\n"
            "               (set automatically when running in-tree)\n"
        )
        return 0

    if "--print-tools" in argv:
        for tool in sorted(
            [
                "init",
                "set_param",
                "set_param_str",
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
