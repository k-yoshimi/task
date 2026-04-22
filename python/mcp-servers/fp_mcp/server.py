"""FastMCP server exposing the TASK/FP library as MCP tools.

Entry point for ``python -m fp_mcp.server`` or the ``fp-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `Fplib` instance per server process.** libfpapi.so holds
  Fortran COMMON-block singleton state (FPCOMM), so there is at most
  one live handle. Subsequent ``init`` calls close the old handle and
  re-open a fresh one so that an LLM can "start over" without
  restarting the server.

  *Known limitation:* ``fp_finalize`` does NOT deallocate the FPCOMM
  arrays (the Fortran backend has an ``fp_allocate`` / ``fp_deallocate``
  asymmetry). A single ``fp_init`` / ``fp_run`` / ``fp_finalize`` cycle
  per process is the supported lifecycle at Phase L-3, so repeated
  init -> finalize -> init cycles may produce unexpected results. For
  clean re-initialisation, restart the server process.

* **FastMCP decorator API** (`mcp.server.fastmcp.FastMCP`). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** :class:`fplib.FplibError` subclasses are re-raised
  as :class:`ToolError` with a human-readable message. The LLM sees
  the error string and can often recover (e.g. by calling ``init``
  first).

The server is intentionally small — the real heavy lifting is in
:mod:`fplib`. This file mirrors ``tr_mcp/server.py``; adding the
remaining modules (ti / wr / wrx / tot) should be a matter of copying
this file and swapping the backing library.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``fplib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/fp_mcp/server.py
# and we want to import ``fplib`` from
#   <repo>/python/fplib/
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
# fplib import (always available from the repo).
# ---------------------------------------------------------------------
from fplib import (  # noqa: E402
    Fplib,
    FplibError,
    FplibInitError,
    FplibInvalidParamError,
    FplibNotInitError,
    FplibCalcFailedError,
    FplibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Keeping these in Python (rather than re-parsing fp_param_registry.f90)
# is a deliberate short-term choice: the LLM-facing description is more
# valuable than the last ounce of DRYness. When the Fortran registry
# changes we'll mirror it here.
#
# Source of truth: fp/fp_param_registry.f90 (~40 unique base names).
# =====================================================================
# fplib has no ``set_param_str`` so strings are not part of the union —
# every fp parameter is numeric.
SupportedValue = Union[float, int, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- geometry / device scalars (PLCOMM via FPCOMM) --------------
    "RR":    {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":    {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RB":    {"type": "float", "group": "geometry", "description": "wall radius [m]"},
    "RKAP":  {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":  {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":    {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "RIP":   {"type": "float", "group": "geometry", "description": "plasma current [MA]"},
    # --- mesh -------------------------------------------------------
    "NRMAX":  {"type": "int", "group": "mesh", "description": "radial mesh size (<= FP_MAX_NRMAX=100)"},
    "NPMAX":  {"type": "int", "group": "mesh", "description": "momentum-space mesh size"},
    "NTHMAX": {"type": "int", "group": "mesh", "description": "pitch-angle mesh size"},
    "NTMAX":  {"type": "int", "group": "mesh", "description": "time-step count (per fp_run call)"},
    "NAVMAX": {"type": "int", "group": "mesh", "description": "orbit-averaging sub-iterations"},
    # --- species counts --------------------------------------------
    "NSMAX":  {"type": "int", "group": "species", "description": "total number of namelist species"},
    "NSAMAX": {"type": "int", "group": "species", "description": "kinetic species count (<= FP_MAX_NSAMAX=8)"},
    "NSBMAX": {"type": "int", "group": "species", "description": "background species count"},
    # --- species mapping arrays (1..NSM, integer) ------------------
    "NS_NSA": {"type": "int[NSM]", "group": "species", "description": "NSA index -> NS species id (1-origin)"},
    "NS_NSB": {"type": "int[NSM]", "group": "species", "description": "NSB index -> NS species id (1-origin)"},
    # --- species real arrays (1..NSM) ------------------------------
    "PA":   {"type": "float[NSM]", "group": "species", "description": "atomic mass per species (1-origin)"},
    "PZ":   {"type": "float[NSM]", "group": "species", "description": "charge number per species"},
    "PN":   {"type": "float[NSM]", "group": "species", "description": "central density per species [10^20 m^-3]"},
    "PNS":  {"type": "float[NSM]", "group": "species", "description": "edge (separatrix) density per species"},
    "PTPR": {"type": "float[NSM]", "group": "species", "description": "central parallel temperature per species [keV]"},
    "PTPP": {"type": "float[NSM]", "group": "species", "description": "central perpendicular temperature per species [keV]"},
    "PTS":  {"type": "float[NSM]", "group": "species", "description": "edge temperature per species [keV]"},
    "PMAX": {"type": "float[NSM]", "group": "species", "description": "momentum-mesh upper bound per species"},
    # --- time evolution --------------------------------------------
    "DELT":   {"type": "float", "group": "time", "description": "time step [s]"},
    "EPSFP":  {"type": "float", "group": "time", "description": "inner-iteration convergence tolerance"},
    "LMAXFP": {"type": "int",   "group": "time", "description": "max inner-iteration count"},
    # --- radial mesh / scalar physics ------------------------------
    "R1":    {"type": "float", "group": "radial",  "description": "radial profile parameter"},
    "DELR1": {"type": "float", "group": "radial",  "description": "radial profile parameter"},
    "RMIN":  {"type": "float", "group": "radial",  "description": "inner radial boundary (normalised)"},
    "RMAX":  {"type": "float", "group": "radial",  "description": "outer radial boundary (normalised)"},
    "E0":    {"type": "float", "group": "radial",  "description": "initial loop voltage [V]"},
    "ZEFF":  {"type": "float", "group": "radial",  "description": "effective charge Z_eff"},
    # --- wave heating ----------------------------------------------
    "PABS_EC": {"type": "float", "group": "wave", "description": "ECRF absorbed power [MW]"},
    "PABS_LH": {"type": "float", "group": "wave", "description": "LH absorbed power [MW]"},
    "PABS_FW": {"type": "float", "group": "wave", "description": "fast-wave absorbed power [MW]"},
    "PABS_WR": {"type": "float", "group": "wave", "description": "WR ray-tracing absorbed power [MW]"},
    "PABS_WM": {"type": "float", "group": "wave", "description": "WM full-wave absorbed power [MW]"},
    "RF_WM":   {"type": "float", "group": "wave", "description": "WM wave frequency [Hz]"},
    # --- model switches (scalar int) -------------------------------
    "MODELG": {"type": "int", "group": "models", "description": "geometry / equilibrium model (3 = typical for iter01 fixture)"},
    "MODELE": {"type": "int", "group": "models", "description": "equilibrium coupling model"},
    "MODELR": {"type": "int", "group": "models", "description": "relativistic model switch"},
    "MODELS": {"type": "int", "group": "models", "description": "source-term model switch"},
    "MODELD": {"type": "int", "group": "models", "description": "radial-diffusion model switch"},
    "MODEL_NBI":     {"type": "int", "group": "models", "description": "NBI source model"},
    "MODEL_WAVE":    {"type": "int", "group": "models", "description": "wave-source selector"},
    "MODEL_DISRUPT": {"type": "int", "group": "models", "description": "disruption model"},
    "MODEL_BS":      {"type": "int", "group": "models", "description": "bootstrap-current model"},
    "MODEL_LOSS":    {"type": "int", "group": "models", "description": "loss-cone / orbit-loss model"},
    "MODEL_SYNCH":   {"type": "int", "group": "models", "description": "synchrotron-loss model"},
    "MODEL_FOW":     {"type": "int", "group": "models", "description": "finite-orbit-width model"},
    # --- model switches (per-species int arrays) -------------------
    "MODELC": {"type": "int[NSM]", "group": "models", "description": "collision-model selector per species"},
    "MODELW": {"type": "int[NSM]", "group": "models", "description": "wave-model selector per species"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "FpState (wire format of fplib.state.FpState.to_dict())",
    "description": (
        "Snapshot of FPCOMM. Profile arrays are [NSAMAX][NRMAX] in the C "
        "layout (row-major), truncated from the FP_MAX_NSAMAX=8 x "
        "FP_MAX_NRMAX=100 storage. Larger meshes require bumping these "
        "caps in fp/fp_api.h and rebuilding libfpapi.so."
    ),
    "properties": {
        "NRMAX":  {"type": "integer", "description": "radial points in use"},
        "NSAMAX": {"type": "integer", "description": "kinetic species in use"},
        "NPMAX":  {"type": "integer", "description": "momentum mesh size"},
        "NTHMAX": {"type": "integer", "description": "pitch-angle mesh size"},
        "NTG2":   {"type": "integer", "description": "long-time-axis counter"},
        "TIMEFP": {"type": "number",  "description": "simulation time [s]"},
        "profile": {
            "type": "array",
            "description": "per-species profile list, length = NSAMAX",
            "items": {
                "type": "object",
                "properties": {
                    "NSA":  {"type": "integer", "description": "1-origin species index"},
                    "RNT":  {"type": "array", "items": {"type": "number"}, "description": "density profile, length NRMAX"},
                    "RWT":  {"type": "array", "items": {"type": "number"}, "description": "stored-energy profile"},
                    "RTT":  {"type": "array", "items": {"type": "number"}, "description": "temperature profile"},
                    "RJT":  {"type": "array", "items": {"type": "number"}, "description": "current-density profile"},
                    "RPCT": {"type": "array", "items": {"type": "number"}, "description": "collisional-power profile"},
                    "RPWT": {"type": "array", "items": {"type": "number"}, "description": "wave-absorbed-power profile"},
                },
            },
        },
    },
    "required": ["NRMAX", "NSAMAX", "NPMAX", "NTHMAX", "NTG2", "TIMEFP", "profile"],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Fplib` instance for this server."""

    def __init__(self) -> None:
        self.fp: Optional[Fplib] = None

    def ensure_open(self) -> Fplib:
        """Return the live handle, opening one if needed."""
        if self.fp is None or self.fp.closed:
            self.fp = Fplib()
        return self.fp

    def close(self) -> None:
        if self.fp is not None and not self.fp.closed:
            self.fp.close()
        self.fp = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(fp: Fplib, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Fplib.set_param`.
    * ``list`` / ``tuple``          — element at 1-origin index ``i``
      is applied as ``NAME[i]``.
    * ``dict[int, float]``          — sparse {index: value}, applied as
      ``NAME[index]``; indices must be 1-origin.

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
            raise FplibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        if isinstance(value, (list, tuple)):
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise FplibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                fp.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                try:
                    int_idx = int(idx)
                except (TypeError, ValueError) as exc:
                    raise FplibError(
                        f"invalid index for '{name}': {idx!r} ({exc})"
                    ) from exc
                key = f"{name}[{int_idx}]"
                try:
                    coerced = float(v)
                except (TypeError, ValueError) as exc:
                    raise FplibError(
                        f"invalid numeric value for '{key}': {v!r} ({exc})"
                    ) from exc
                fp.set_param(key, coerced)
                applied.append(key)
        elif isinstance(value, (int, float)):
            try:
                coerced = float(value)
            except (TypeError, ValueError) as exc:
                raise FplibError(
                    f"invalid numeric value for '{name}': {value!r} ({exc})"
                ) from exc
            fp.set_param(name, coerced)
            applied.append(name)
        else:
            raise FplibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_fplib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate an fplib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, FplibInvalidParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, FplibNotInitError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, FplibCalcFailedError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, FplibNotImplementedError):
        msg = f"not implemented in this libfpapi.so build: {exc}"
    elif isinstance(exc, FplibInitError):
        msg = f"fp_init failed: {exc}"
    elif isinstance(exc, FplibError):
        msg = f"fplib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libfpapi.so not found: {exc}. "
            "Build it via `make -C fp libfpapi.so` or set FPLIB_PATH."
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
        return "fp library initialized"
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        fp = STATE.ensure_open()
        fp.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        fp = STATE.ensure_open()
        applied = _apply_bulk_params(fp, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_run(ntmax: int = 1) -> str:
    try:
        fp = STATE.ensure_open()
        fp.run(int(ntmax))
        return f"advanced {ntmax} time step(s)"
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        fp = STATE.ensure_open()
        return fp.get_state().to_dict()
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_finalize() -> str:
    try:
        STATE.close()
        return "fp library finalized"
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "fp",
        "count": len(PARAMETER_REGISTRY),
        "array_syntax": "Use NAME[i] (1-origin) for array elements, e.g. PN[1].",
        "caps": {
            "FP_MAX_NSAMAX": 8,
            "FP_MAX_NRMAX": 100,
        },
        "parameters": PARAMETER_REGISTRY,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    ntmax: int = 1,
) -> Dict[str, Any]:
    try:
        fp = STATE.ensure_open()
        if params:
            _apply_bulk_params(fp, params)
        fp.run(int(ntmax))
        return fp.get_state().to_dict()
    except Exception as exc:
        raise _wrap_fplib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 9 fp tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-fp",
        instructions=(
            "TASK/FP Fokker-Planck-code MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "or `set_params`, advance with `run`, and read state with "
            "`get_state`. Use `describe_parameters` to discover valid "
            "parameter names. `run_and_get_state` is a convenience "
            "one-shot wrapper. Note: `set_params` is *non-transactional* "
            "— on a partial failure, parameters applied before the "
            "failing key remain set. Note: fp_finalize does NOT "
            "deallocate FPCOMM — repeated init/finalize cycles in one "
            "process are not supported; restart the server for a clean "
            "slate."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the fp library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults, but note that fp_finalize
        does not fully deallocate FPCOMM arrays (Phase L-3 limitation):
        restart the server process for a truly clean state.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set an fp parameter by name.

        Use ``NAME[i]`` (1-origin) for array elements, e.g. ``PN[1]``.
        See `describe_parameters` for the full registry. All fp
        parameters are numeric (float / int).
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set fp parameters.

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
    def run(ntmax: int = 1) -> str:
        """Advance the simulation by ``ntmax`` time steps.

        ``ntmax=0`` is a valid no-op (useful as a smoke test).
        """
        return handle_run(ntmax)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current simulation state.

        Returns a dict with ``NRMAX``, ``NSAMAX``, ``NPMAX``, ``NTHMAX``,
        ``NTG2``, ``TIMEFP``, and ``profile`` (per-species list of 6
        radial arrays: RNT, RWT, RTT, RJT, RPCT, RPWT). Schema also
        available via `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def finalize() -> str:
        """Release fp library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library — though the L-3
        fp_finalize / fp_init pair does not cleanly reset FPCOMM
        arrays, so results after a re-init may not match a fresh
        process.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported fp parameters.

        Each entry exposes ``type``, ``group``, and ``description``.
        Also reports the FP_MAX_NSAMAX / FP_MAX_NRMAX mesh caps.
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
            "fp-mcp — Model Context Protocol server for TASK/FP\n"
            "\n"
            "Usage:\n"
            "  python -m fp_mcp.server    # run over stdio (default)\n"
            "  fp-mcp                     # same, via installed script\n"
            "  fp-mcp --help              # show this help\n"
            "  fp-mcp --print-tools       # list registered tools\n"
            "\n"
            "Environment:\n"
            "  FPLIB_PATH   override path to libfpapi.so\n"
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
