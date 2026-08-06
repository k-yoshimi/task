"""FastMCP server exposing the TASK/EQ equilibrium library as MCP tools.

Entry point for ``python -m eq_mcp.server`` or the ``eq-mcp`` console
script declared in :file:`pyproject.toml`.

Design notes
------------
* **One `Eq` instance per server process.** libeqapi.so holds Fortran
  COMMON-block + ``eqcom*_mod`` MODULE singleton state, so there is at
  most one live handle. Subsequent ``init`` calls close the old handle
  and re-open a fresh one so that an LLM can "start over" without
  restarting the server.
* **FastMCP decorator API** (``mcp.server.fastmcp.FastMCP``). Each tool
  is a plain Python function with type hints; the SDK generates the
  JSON Schema advertised to the client automatically.
* **Error mapping.** :class:`eqlib.EqlibError` subclasses are re-raised
  as ``ToolError`` with a human-readable message. The LLM sees the
  error string and can often recover (e.g. by calling ``init`` first).

EQ-specific extras over the canonical sister surface (tr_mcp / ti_mcp /
wrx_mcp):

* ``set_param_str`` — string parameters such as ``KNAMEQ`` (the EQDSK
  file path) routed through :py:meth:`eqlib.Eq.set_param_str`.
* ``validate`` — pre-run cross-parameter validation (Issue #143)
  exposing :py:meth:`eqlib.Eq.validate`. Returns a list of
  ``{param, code, message}`` dicts; an empty list means the current
  state will not trip any validator.

This mirrors the ``tr_mcp`` / ``wrx_mcp`` reference implementations
as closely as possible; the main eq-specific additions are the
validate tool and the broader namelist surface (PSIB[0..5] + the
PFC-coil arrays + ~60 scalar registry entries).

fd-isolation (Fortran WRITE(6) vs MCP JSON-RPC)
-----------------------------------------------
Fortran WRITE(6,...) targets OS fd 1, which is also the JSON-RPC write
pipe to the MCP client parent.  Any Fortran diagnostic line corrupts the
pipe and causes "Connection closed" on the client side.

Fix: installed by main() immediately before the stdio server starts
(NOT at import time -- see #227 item 1):
  1. dup fd 1 (JSON-RPC write pipe) to a fresh fd; redirect fd 1 → stderr
     so Fortran WRITE(6,...) goes to the subprocess stderr (backend log).
  2. Rebuild sys.stdout around the saved fd so the MCP framework's stdio
     transport still writes to the correct pipe.

After this:
  - Fortran WRITE(6,...) → fd 1 → stderr (harmless backend log)
  - MCP sys.stdout.write → saved fd → original JSON-RPC write pipe

NOTE: We do NOT redirect fd 0 (stdin) to /dev/null because the Fortran
library uses stdin internally; redirecting it increases crash rates.

The _redirect_fortran_stdout_to_stderr context manager below is kept as
belt-and-suspenders. Once main() has installed the isolation, dup2(2,1)
when fd 1 is already fd 2 is harmless. For an in-process importer that never
calls main(), it is NOT a no-op -- it is the only thing keeping Fortran
WRITE(6) off the caller's stdout, which is why it stays.
"""
from __future__ import annotations

import os as _os
import sys as _sys

# ---------- fd-isolation (Fortran WRITE(6) vs MCP JSON-RPC) ----------
# fd 1 originally points at the parent's JSON-RPC write pipe. Fortran
# WRITE(6,...) also targets fd 1, corrupting the pipe. We dup the pipe
# to a fresh fd and redirect fd 1 → stderr so Fortran writes go to the
# subprocess stderr (visible in backend log; harmless to JSON-RPC).
#
# The MCP framework writes via sys.stdout, so we rebuild sys.stdout to
# write to the saved (original-pipe) fd. Line buffering keeps JSON-RPC
# records flushing per-message.
#
# NOTE: We do NOT redirect fd 0 (stdin) to /dev/null because the
# Fortran library uses stdin internally; redirecting it increases crash
# rates (~20% → ~50%).
#
# #227 item 1: this MUST NOT run at import time. Importing this module --
# pytest collection, an embedding application, or a bare
# `python -c "import eq_mcp.server"` -- previously mutated the *host*
# process's fd 1 and replaced its sys.stdout. It is now installed
# explicitly by main(), i.e. only when this module actually runs as the
# stdio server.
_FD_ISOLATION_INSTALLED = False
_mcp_pipe_fd = None


def _install_fd_isolation() -> None:
    """Redirect fd 1 to stderr and rebuild sys.stdout on the saved pipe fd.

    Idempotent. Called from main() immediately before the stdio server
    starts; never at import time.
    """
    global _FD_ISOLATION_INSTALLED, _mcp_pipe_fd
    if _FD_ISOLATION_INSTALLED:
        return
    _mcp_pipe_fd = _os.dup(1)
    _os.dup2(2, 1)
    _sys.stdout = _os.fdopen(_mcp_pipe_fd, "w", buffering=1, encoding="utf-8")
    _FD_ISOLATION_INSTALLED = True
# ----------------------------------------------------------------------

import contextlib
import ctypes
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------
# Make ``eqlib`` importable without a wheel install.
#
# This file lives at
#   <repo>/python/mcp-servers/eq_mcp/server.py
# and we want to import ``eqlib`` from
#   <repo>/python/eqlib/
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
# eqlib import (always available from the repo).
# ---------------------------------------------------------------------
from eqlib import (  # noqa: E402
    Eq,
    EqlibError,
    EqlibInitError,
    EqlibInvalidParamError,
    EqlibNotInitializedError,
    EqlibCalculationFailedError,
    EqlibNotImplementedError,
)


# =====================================================================
# Parameter & state schema metadata.
#
# Mirrors ``eq/eq_param_registry.f90`` (the SELECT CASE list). Keeping
# it in Python (rather than re-parsing the Fortran file) lets us attach
# LLM-friendly descriptions; when the Fortran registry changes we
# mirror it here.
# =====================================================================
SupportedValue = Union[float, int, str, List[float], Dict[int, float]]


PARAMETER_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- A. device geometry scalars (plcomm_parm) ------------------
    "RR":     {"type": "float", "group": "geometry", "description": "major radius [m]"},
    "RA":     {"type": "float", "group": "geometry", "description": "minor radius [m]"},
    "RB":     {"type": "float", "group": "geometry", "description": "wall radius [m]"},
    "RKAP":   {"type": "float", "group": "geometry", "description": "plasma elongation"},
    "RDLT":   {"type": "float", "group": "geometry", "description": "plasma triangularity"},
    "BB":     {"type": "float", "group": "geometry", "description": "toroidal field on axis [T]"},
    "Q0":     {"type": "float", "group": "geometry", "description": "safety factor on axis"},
    "QA":     {"type": "float", "group": "geometry", "description": "safety factor at edge"},
    "RIP":    {"type": "float", "group": "geometry", "description": "plasma current [MA]"},
    "RHOMIN": {"type": "float", "group": "geometry", "description": "minimum-q radial position"},
    "QMIN":   {"type": "float", "group": "geometry", "description": "minimum q value"},
    "RHOEDG": {"type": "float", "group": "geometry", "description": "edge radial position"},
    # --- B. profile scalars (eqcom1_mod) ---------------------------
    "PP0":    {"type": "float", "group": "profile", "description": "pressure profile coefficient PP0"},
    "PP1":    {"type": "float", "group": "profile", "description": "pressure profile coefficient PP1"},
    "PP2":    {"type": "float", "group": "profile", "description": "pressure profile coefficient PP2"},
    "PROFP0": {"type": "float", "group": "profile", "description": "pressure profile shape PROFP0"},
    "PROFP1": {"type": "float", "group": "profile", "description": "pressure profile shape PROFP1"},
    "PROFP2": {"type": "float", "group": "profile", "description": "pressure profile shape PROFP2"},
    "PJ0":    {"type": "float", "group": "profile", "description": "current profile coefficient PJ0"},
    "PJ1":    {"type": "float", "group": "profile", "description": "current profile coefficient PJ1"},
    "PJ2":    {"type": "float", "group": "profile", "description": "current profile coefficient PJ2"},
    "PROFJ0": {"type": "float", "group": "profile", "description": "current profile shape PROFJ0"},
    "PROFJ1": {"type": "float", "group": "profile", "description": "current profile shape PROFJ1"},
    "PROFJ2": {"type": "float", "group": "profile", "description": "current profile shape PROFJ2"},
    "FF0":    {"type": "float", "group": "profile", "description": "F=R*B_phi profile coefficient FF0"},
    "FF1":    {"type": "float", "group": "profile", "description": "F=R*B_phi profile coefficient FF1"},
    "FF2":    {"type": "float", "group": "profile", "description": "F=R*B_phi profile coefficient FF2"},
    "PROFF0": {"type": "float", "group": "profile", "description": "F profile shape PROFF0"},
    "PROFF1": {"type": "float", "group": "profile", "description": "F profile shape PROFF1"},
    "PROFF2": {"type": "float", "group": "profile", "description": "F profile shape PROFF2"},
    "PT0":    {"type": "float", "group": "profile", "description": "temperature profile coefficient PT0"},
    "PT1":    {"type": "float", "group": "profile", "description": "temperature profile coefficient PT1"},
    "PT2":    {"type": "float", "group": "profile", "description": "temperature profile coefficient PT2"},
    "PROFTP0": {"type": "float", "group": "profile", "description": "temperature profile shape PROFTP0"},
    "PROFTP1": {"type": "float", "group": "profile", "description": "temperature profile shape PROFTP1"},
    "PROFTP2": {"type": "float", "group": "profile", "description": "temperature profile shape PROFTP2"},
    "PTSEQ":  {"type": "float", "group": "profile", "description": "edge (separatrix) temperature [keV]"},
    "PN0EQ":  {"type": "float", "group": "profile", "description": "central density [10^20 m^-3]"},
    "PV0":    {"type": "float", "group": "profile", "description": "rotation profile coefficient PV0"},
    "PV1":    {"type": "float", "group": "profile", "description": "rotation profile coefficient PV1"},
    "PV2":    {"type": "float", "group": "profile", "description": "rotation profile coefficient PV2"},
    "PROFV0": {"type": "float", "group": "profile", "description": "rotation profile shape PROFV0"},
    "PROFV1": {"type": "float", "group": "profile", "description": "rotation profile shape PROFV1"},
    "PROFV2": {"type": "float", "group": "profile", "description": "rotation profile shape PROFV2"},
    "PROFR0": {"type": "float", "group": "profile", "description": "radial profile shape PROFR0"},
    "PROFR1": {"type": "float", "group": "profile", "description": "radial profile shape PROFR1"},
    "PROFR2": {"type": "float", "group": "profile", "description": "radial profile shape PROFR2"},
    # --- C. convergence / iteration scalars (eqcom1_mod) -----------
    "EPSEQ":  {"type": "float", "group": "convergence", "description": "EQ outer-loop tolerance"},
    "NLPMAX": {"type": "int",   "group": "convergence", "description": "EQ outer-loop max iterations"},
    "EPSNW":  {"type": "float", "group": "convergence", "description": "Newton inner-loop tolerance"},
    "DELNW":  {"type": "float", "group": "convergence", "description": "Newton step damping"},
    "NLPNW":  {"type": "int",   "group": "convergence", "description": "Newton inner-loop max iterations"},
    # --- D. region / boundary scalars (eqcom1_mod) -----------------
    "RGMIN":  {"type": "float", "group": "region", "description": "R-grid lower bound [m]"},
    "RGMAX":  {"type": "float", "group": "region", "description": "R-grid upper bound [m]"},
    "ZGMIN":  {"type": "float", "group": "region", "description": "Z-grid lower bound [m]"},
    "ZGMAX":  {"type": "float", "group": "region", "description": "Z-grid upper bound [m]"},
    "ZLIMP":  {"type": "float", "group": "region", "description": "upper Z limiter [m]"},
    "ZLIMM":  {"type": "float", "group": "region", "description": "lower Z limiter [m]"},
    "FRBIN":  {"type": "float", "group": "region", "description": "RB inner-region scaling"},
    # --- E. integer mesh / model switches --------------------------
    "MODELG": {"type": "int", "group": "models", "description": "equilibrium/geometry selector (1..9; 3 = TASK/EQ binary load)"},
    "MODELQ": {"type": "int", "group": "models", "description": "q-profile model selector"},
    "IDEBUG": {"type": "int", "group": "models", "description": "debug-output level"},
    "MODEFR": {"type": "int", "group": "models", "description": "frequency-space mode switch"},
    "MODEFW": {"type": "int", "group": "models", "description": "wave-frequency mode switch"},
    "MDLEQF": {"type": "int", "group": "models", "description": "equilibrium-fixed-boundary model"},
    "MDLEQC": {"type": "int", "group": "models", "description": "equilibrium-constraint model"},
    "MDLEQA": {"type": "int", "group": "models", "description": "equilibrium-axisymmetry model"},
    "MDLEQX": {"type": "int", "group": "models", "description": "equilibrium-extension model"},
    "MDLEQV": {"type": "int", "group": "models", "description": "equilibrium-volume model"},
    "NPRINT": {"type": "int", "group": "models", "description": "print-output cadence"},
    # --- mesh size scalars (eqcom1_mod) ----------------------------
    "NRMAX":   {"type": "int", "group": "mesh", "description": "radial flux-surface samples (<= EQ_MAX_NRM=1001)"},
    "NTHMAX":  {"type": "int", "group": "mesh", "description": "poloidal samples (<= EQ_MAX_NTHM=2049)"},
    "NSUMAX":  {"type": "int", "group": "mesh", "description": "surface samples (<= EQ_MAX_NSUM=1343)"},
    "NSGMAX":  {"type": "int", "group": "mesh", "description": "PSI(s,t) S-grid samples"},
    "NTGMAX":  {"type": "int", "group": "mesh", "description": "PSI(s,t) T-grid samples"},
    "NUGMAX":  {"type": "int", "group": "mesh", "description": "U-grid samples"},
    "NRGMAX":  {"type": "int", "group": "mesh", "description": "R-grid samples (<= EQ_MAX_NRGM=513)"},
    "NZGMAX":  {"type": "int", "group": "mesh", "description": "Z-grid samples (<= EQ_MAX_NZGM=513)"},
    "NPSMAX":  {"type": "int", "group": "mesh", "description": "psi-surface samples (<= EQ_MAX_NPSM=513)"},
    "NRVMAX":  {"type": "int", "group": "mesh", "description": "volume-grid radial samples"},
    "NTVMAX":  {"type": "int", "group": "mesh", "description": "volume-grid theta samples"},
    "NPFCMAX": {"type": "int", "group": "mesh", "description": "PF-coil count (<= 10)"},
    # --- F. 1D arrays ----------------------------------------------
    # PSIB is unique to EQ: 0-origin (PSIB(0:5)). Bare "PSIB" is
    # rejected with EqlibInvalidParamError; use PSIB[0]..PSIB[5].
    "PSIB":  {"type": "float[0..5]",  "group": "boundary",  "description": "PSI boundary values (0-origin: PSIB[0]..PSIB[5])"},
    "RIPFC": {"type": "float[NPFCM]", "group": "pfcoil",    "description": "PF-coil current per coil (1-origin, 1..10)"},
    "RPFC":  {"type": "float[NPFCM]", "group": "pfcoil",    "description": "PF-coil R position per coil (1-origin)"},
    "ZPFC":  {"type": "float[NPFCM]", "group": "pfcoil",    "description": "PF-coil Z position per coil (1-origin)"},
    "WPFC":  {"type": "float[NPFCM]", "group": "pfcoil",    "description": "PF-coil width per coil (1-origin)"},
    # --- string parameters (set via set_param_str under the hood) --
    "KNAMEQ":  {"type": "str", "group": "io", "description": "equilibrium data file name (EQDSK / TASK-EQ)"},
    "KNAMEQ2": {"type": "str", "group": "io", "description": "secondary equilibrium data file name"},
    "KNAMWR":  {"type": "str", "group": "io", "description": "WR (ray-tracing) input file name"},
    "KNAMWM":  {"type": "str", "group": "io", "description": "WM (full-wave) input file name"},
    "KNAMFP":  {"type": "str", "group": "io", "description": "FP (Fokker-Planck) input file name"},
    "KNAMFO":  {"type": "str", "group": "io", "description": "FP output file name"},
    "KNAMPF":  {"type": "str", "group": "io", "description": "PF coil configuration file name"},
}


STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "title": "EqState (wire format of eqlib.state.EqState.to_dict())",
    "properties": {
        "NRGMAX": {"type": "integer", "description": "active R-grid points"},
        "NZGMAX": {"type": "integer", "description": "active Z-grid points"},
        "NPSMAX": {"type": "integer", "description": "active psi-surface samples"},
        "NRMAX":  {"type": "integer", "description": "active radial samples (psi-mesh)"},
        "NTHMAX": {"type": "integer", "description": "active poloidal samples"},
        "NSUMAX": {"type": "integer", "description": "active surface samples"},
        "NRVMAX": {"type": "integer", "description": "active volume-grid radial samples"},
        "NSGMAX": {"type": "integer", "description": "active PSI(s,t) S-grid samples"},
        "NTGMAX": {"type": "integer", "description": "active PSI(s,t) T-grid samples"},
        "scalars": {
            "type": "object",
            "description": (
                "12 plasma scalars: RAXIS / ZAXIS (magnetic axis), "
                "PSI0 / PSIPA / PSITA (poloidal / toroidal flux), "
                "QAXIS / QSURF (q on axis / at edge), BETAT / BETAP "
                "(toroidal / poloidal beta), PVOL (plasma volume), "
                "RAAVE (volume-averaged R), RIPX (output Ip)"
            ),
            "additionalProperties": {"type": "number"},
        },
        "RG": {
            "type": "array",
            "items": {"type": "number"},
            "description": "R-grid coordinates [m], length = NRGMAX",
        },
        "ZG": {
            "type": "array",
            "items": {"type": "number"},
            "description": "Z-grid coordinates [m], length = NZGMAX",
        },
        "PSIPS": {
            "type": "array",
            "items": {"type": "number"},
            "description": "psi-surface psi values, length = NPSMAX",
        },
        "PPPS": {
            "type": "array",
            "items": {"type": "number"},
            "description": "pressure profile (psi-surface), length = NPSMAX",
        },
        "TTPS": {
            "type": "array",
            "items": {"type": "number"},
            "description": "T = R*B_phi profile (psi-surface), length = NPSMAX",
        },
        "QQPS": {
            "type": "array",
            "items": {"type": "number"},
            "description": "q profile (psi-surface), length = NPSMAX",
        },
        "profile": {
            "type": "array",
            "description": "Per-NR flux-surface profile (1..NRMAX, 7 columns)",
            "items": {
                "type": "object",
                "properties": {
                    "NR":   {"type": "integer", "description": "1-origin radial index"},
                    "PSIP": {"type": "number",  "description": "poloidal flux"},
                    "PSIT": {"type": "number",  "description": "toroidal flux"},
                    "PPS":  {"type": "number",  "description": "pressure"},
                    "TTS":  {"type": "number",  "description": "T = R*B_phi"},
                    "QPS":  {"type": "number",  "description": "safety factor"},
                    "VPS":  {"type": "number",  "description": "differential volume"},
                    "RST":  {"type": "number",  "description": "<R> at this surface"},
                },
            },
        },
    },
    "required": [
        "NRGMAX", "NZGMAX", "NPSMAX", "NRMAX", "NTHMAX", "NSUMAX",
        "NRVMAX", "NSGMAX", "NTGMAX",
        "scalars", "RG", "ZG", "PSIPS", "PPPS", "TTPS", "QQPS",
        "profile",
    ],
}


# =====================================================================
# Server state (process-wide singleton).
# =====================================================================
class _ServerState:
    """Holds the single live :class:`Eq` instance for this server."""

    def __init__(self) -> None:
        self.eq: Optional[Eq] = None

    def ensure_open(self) -> Eq:
        """Return the live handle, opening one if needed."""
        if self.eq is None or self.eq.closed:
            self.eq = Eq()
        return self.eq

    def close(self) -> None:
        if self.eq is not None and not self.eq.closed:
            self.eq.close()
        self.eq = None


STATE = _ServerState()


# =====================================================================
# Helpers — parameter application.
# =====================================================================
def _apply_bulk_params(eq: Eq, params: Dict[str, SupportedValue]) -> List[str]:
    """Apply a bulk ``params`` dict, returning the list of applied keys.

    Accepted value shapes per key:

    * scalar (``float`` / ``int``)   — plain :py:meth:`Eq.set_param`.
    * ``list`` / ``tuple``          — element at 1-origin index ``i``
      is applied as ``NAME[i]``. **Note:** for the EQ-specific
      0-origin ``PSIB`` array, prefer the ``dict`` form below so the
      0-th element can be addressed (a list always starts at index 1).
    * ``dict[int, float]``          — sparse {index: value}, applied as
      ``NAME[index]``; indices must match the array's origin (PSIB is
      0-origin, RIPFC/RPFC/ZPFC/WPFC are 1-origin).
    * ``str``                       — string-valued parameter (e.g.
      ``KNAMEQ``); routed through :py:meth:`Eq.set_param_str`.
    """
    applied: List[str] = []
    for name, value in params.items():
        if isinstance(value, (list, tuple)):
            # PSIB is the only 0-origin array in eq's registry
            # (Fortran REAL(8) :: PSIB(0:5)). Reject list-form for it
            # explicitly: enumerate(start=1) would generate PSIB[1..6],
            # silently writing wrong indices and leaving PSIB[0] unset
            # before the final PSIB[6] write trips out-of-range on
            # partial mutation. Force the dict form.
            if name == "PSIB":
                raise EqlibError(
                    "PSIB is a 0-origin array; pass a dict "
                    "{0: v0, 1: v1, ...} instead of a list "
                    "(a list would silently start at index 1)."
                )
            for i, v in enumerate(value, start=1):
                key = f"{name}[{i}]"
                eq.set_param(key, float(v))
                applied.append(key)
        elif isinstance(value, dict):
            for idx, v in value.items():
                key = f"{name}[{int(idx)}]"
                eq.set_param(key, float(v))
                applied.append(key)
        elif isinstance(value, bool):
            # bool is a subclass of int; reject as ambiguous.
            raise EqlibError(
                f"unsupported value type for '{name}': bool (use 0/1)"
            )
        elif isinstance(value, str):
            # String-valued (e.g. KNAMEQ). Routed through
            # eq_set_param_str on libeqapi.so.
            eq.set_param_str(name, value)
            applied.append(name)
        elif isinstance(value, (int, float)):
            eq.set_param(name, float(value))
            applied.append(name)
        else:
            raise EqlibError(
                f"unsupported value type for '{name}': {type(value).__name__}"
            )
    return applied


def _wrap_eqlib_error(exc: Exception) -> "ToolError":  # noqa: F821
    """Translate an eqlib exception into the MCP ToolError class.

    Kept as a helper so tests can assert the mapping without depending
    on the MCP SDK being installed.
    """
    if isinstance(exc, EqlibInvalidParamError):
        msg = f"invalid parameter: {exc}"
    elif isinstance(exc, EqlibNotInitializedError):
        msg = f"library not initialized (call init first): {exc}"
    elif isinstance(exc, EqlibCalculationFailedError):
        msg = f"calculation failed: {exc}"
    elif isinstance(exc, EqlibNotImplementedError):
        msg = f"not implemented in this libeqapi.so build: {exc}"
    elif isinstance(exc, EqlibInitError):
        msg = f"eq_init failed: {exc}"
    elif isinstance(exc, EqlibError):
        msg = f"eqlib error: {exc}"
    elif isinstance(exc, FileNotFoundError):
        msg = (
            f"libeqapi.so not found: {exc}. "
            "Build it via `make -C eq libeqapi.so` or set EQLIB_PATH."
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

# ---------------------------------------------------------------------
# libc fflush() for the C-level stdout FILE* only.
#
# We flush the C-level stdout FILE* (not fflush(NULL)) so that any
# pending Fortran output in libc's buffer drains into stderr while fd 1
# still points there, BEFORE we restore fd 1 to the JSON-RPC pipe.
# Using fflush(NULL) on macOS also flushes Python's asyncio write
# buffer, which would send pending JSON-RPC responses to stderr.
# Python writes via raw syscalls, not via C's stdout FILE*, so
# fflush(_c_stdout) doesn't affect Python's asyncio writes.
# ---------------------------------------------------------------------
if platform.system() == "Darwin":
    _libc = ctypes.CDLL("libSystem.dylib")
    _c_stdout = ctypes.c_void_p.in_dll(_libc, "__stdoutp")
else:  # Linux
    _libc = ctypes.CDLL("libc.so.6")
    _c_stdout = ctypes.c_void_p.in_dll(_libc, "stdout")

_libc.fflush.argtypes = [ctypes.c_void_p]
_libc.fflush.restype = ctypes.c_int

# Make C-level stdout fully unbuffered so Fortran WRITE(6,...) emits
# immediately. Combined with the redirect window, this eliminates the
# race where buffered Fortran output flushes into the MCP pipe AFTER
# the redirect has been torn down.
#
# setvbuf(FILE *stream, char *buf, int mode, size_t size)
#   _IONBF = 2 on glibc and macOS libc.
_libc.setvbuf.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_size_t]
_libc.setvbuf.restype = ctypes.c_int
_IONBF = 2
_libc.setvbuf(_c_stdout, None, _IONBF, 0)

# Flush Fortran's own I/O buffer for unit 6 (stdout).
#
# gfortran maintains its own Fortran-level I/O buffer (separate from libc's
# C FILE* buffer). fflush(c_stdout) only drains the C buffer; Fortran output
# can still be pending in gfortran's internal buffer after the Fortran call
# returns. Calling _gfortran_flush_i4(&unit) flushes unit 6 at the Fortran
# level — forcing the write to cross the fd boundary — before we restore
# fd 1 to the JSON-RPC pipe.
#
# On Linux the symbol is in the process via libgfortran loaded by libtrapi.so;
# we locate it through ctypes.CDLL(None) (RTLD_DEFAULT). On macOS the path is
# explicit because RTLD_DEFAULT does not search already-loaded dylibs on all
# macOS releases.
_libgfortran_path = "/opt/local/lib/libgcc/libgfortran.5.dylib"  # macOS (MacPorts)
_libgfortran_linux = "libgfortran.so.5"
try:
    if platform.system() == "Darwin":
        _libgfortran = ctypes.CDLL(_libgfortran_path)
    else:
        _libgfortran = ctypes.CDLL(_libgfortran_linux)
    _gfortran_flush = _libgfortran["_gfortran_flush_i4"]
    _gfortran_flush.argtypes = [ctypes.POINTER(ctypes.c_int32)]
    _gfortran_flush.restype = None
    _FORTRAN_UNIT6 = ctypes.c_int32(6)
    _HAS_GFORTRAN_FLUSH = True
except Exception:  # pragma: no cover — libgfortran not found; fall back to C fflush
    _HAS_GFORTRAN_FLUSH = False

# With the permanent fd-isolation, fd 1 is already stderr for the lifetime of
# the process.  Calling _gfortran_flush_i4 after eq.run() is unnecessary
# (Fortran already wrote to fd 1 = stderr; there is nothing to drain into the
# MCP pipe) and is actively harmful: _gfortran_flush_i4 on this build of
# libgfortran/libeqapi.so triggers SIGABRT ~10-40% of the time due to an
# internal heap-corruption bug in the gfortran I/O library triggered by the
# flush sequence.  Disable it when the permanent redirect is active.
# (Decided at call time via _FD_ISOLATION_INSTALLED -- see
# _redirect_fortran_stdout_to_stderr below -- because the redirect is no
# longer installed at import time.)


@contextlib.contextmanager
def _redirect_fortran_stdout_to_stderr():
    """Belt-and-suspenders: ensure fd 1 points at stderr around Fortran calls.

    When main() has installed the fd-isolation, fd 1 already points at
    stderr for the lifetime of the process and this context manager is
    effectively a no-op:
    dup2(2, 1) when fd 1 is already fd 2 is harmless, and the flushes are
    harmless too.

    We keep it so that any call sites that were added before the permanent
    fix continue to work correctly — and as extra insurance if the process
    ever runs without the startup dance (e.g. direct import in tests).

    NOTE: We target fd 1 directly (not sys.stdout.fileno()) because after
    the permanent redirect sys.stdout wraps the *saved* pipe fd, not fd 1.
    Calling sys.stdout.fileno() would redirect the MCP pipe to stderr,
    which is the opposite of what we want.
    """
    # fd 1 is already stderr after module-load redirect; save it anyway
    # (dup2(2,1) is idempotent — this is purely belt-and-suspenders).
    saved_fd = os.dup(1)
    try:
        os.dup2(sys.stderr.fileno(), 1)
        yield
        # 1. Flush Fortran's internal I/O buffer for unit 6.
        if _HAS_GFORTRAN_FLUSH and not _FD_ISOLATION_INSTALLED:
            _gfortran_flush(ctypes.byref(_FORTRAN_UNIT6))
        # 2. Flush C-level stdout FILE* (defense in depth).
        _libc.fflush(_c_stdout)
    finally:
        # Restore fd 1 (no-op if it was already pointing at stderr).
        os.dup2(saved_fd, 1)
        os.close(saved_fd)


def handle_init() -> str:
    try:
        STATE.ensure_open()
        return "eq library initialized"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_set_param(name: str, value: float) -> str:
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            eq.set_param(name, float(value))
        return f"set {name} = {value}"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_set_param_str(name: str, value: str) -> str:
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            eq.set_param_str(name, str(value))
        return f"set {name} = {value!r}"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_save(path: str) -> str:
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            eq.save(path)
        return f"saved equilibrium to {path}"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_get_psi_rz() -> Dict[str, Any]:
    try:
        eq = STATE.ensure_open()
        psi = eq.get_psi_rz()  # numpy ndarray shape (nrg, nzg)
        state = eq.get_state()
        nrg = int(psi.shape[0])
        nzg = int(psi.shape[1])
        # state.rg / state.zg are already trimmed to nrgmax / nzgmax by
        # EqState.from_c(); a plain list copy is sufficient.
        rg = list(state.rg)
        zg = list(state.zg)
        return {
            "nrg": nrg,
            "nzg": nzg,
            "rg": rg,
            "zg": zg,
            "psi_rz": psi.tolist(),
        }
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_set_params(params: Dict[str, SupportedValue]) -> str:
    if not isinstance(params, dict):
        raise ToolError(  # type: ignore[call-arg]
            f"set_params expects a dict; got {type(params).__name__}"
        )
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            applied = _apply_bulk_params(eq, params)
        return f"set {len(applied)} parameter(s): {applied}"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_run(mode: int = 1) -> str:
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            eq.run(int(mode))
        return f"eq_run completed (mode={mode})"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_get_state() -> Dict[str, Any]:
    try:
        eq = STATE.ensure_open()
        with _redirect_fortran_stdout_to_stderr():
            state = eq.get_state()
        return state.to_dict()
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_validate() -> List[Dict[str, Any]]:
    """Return pre-run validation diagnostics as a list of dicts.

    Each entry has ``param`` (str), ``code`` (int — see
    :class:`eqlib.EqDiagCode`), and ``message`` (str). An empty list
    means the current eq state will not trigger any validator.

    Raises (translated to ToolError):

    * :class:`EqlibNotInitializedError` — call ``init`` first.
    * :class:`EqlibError` — the loaded ``libeqapi.so`` does not export
      ``eq_validate`` (rebuild via ``make -C eq libeqapi.so``).
    """
    try:
        eq = STATE.ensure_open()
        diags = eq.validate()
        return [
            {"param": d.param, "code": int(d.code), "message": d.message}
            for d in diags
        ]
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_finalize() -> str:
    try:
        with _redirect_fortran_stdout_to_stderr():
            STATE.close()
        return "eq library finalized"
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


def handle_describe_parameters() -> Dict[str, Any]:
    return {
        "module": "eq",
        "count": len(PARAMETER_REGISTRY),
        "array_syntax": (
            "Use NAME[i] for array elements. Most arrays are 1-origin "
            "(RIPFC[1], RPFC[1], ZPFC[1], WPFC[1]). The PSIB array is "
            "0-origin (PSIB[0]..PSIB[5]) because the underlying Fortran "
            "is REAL(8) :: PSIB(0:5). String parameters (KNAMEQ etc.) "
            "are set via set_param_str."
        ),
        "parameters": PARAMETER_REGISTRY,
    }


def handle_describe_state_schema() -> Dict[str, Any]:
    return STATE_SCHEMA


def handle_run_and_get_state(
    params: Optional[Dict[str, SupportedValue]] = None,
    mode: int = 1,
) -> Dict[str, Any]:
    """One-shot init → set_params → run → get_state.

    Codex review (P2) fix: force-close any prior :class:`Eq` handle
    before opening a fresh one so this call is genuinely isolated.
    Without the close, prior tool calls in the same MCP server process
    leak their parameter mutations (MODELG, KNAMEQ, mesh sizes, etc.)
    into the one-shot run because libeqapi.so holds singleton Fortran
    state — the user-facing contract ("init + set + run + get_state")
    requires a fresh init each call.
    """
    try:
        # Force a fresh handle: STATE.close() finalizes any prior Eq,
        # then ensure_open() opens a new one. Mirrors the documented
        # init step of the one-shot contract.
        STATE.close()
        eq = STATE.ensure_open()
        if params:
            _apply_bulk_params(eq, params)
        with _redirect_fortran_stdout_to_stderr():
            eq.run(int(mode))
        return eq.get_state().to_dict()
    except Exception as exc:
        raise _wrap_eqlib_error(exc) from exc


# =====================================================================
# FastMCP server wiring.
#
# Declared only when the SDK is importable; the handle_* functions
# above are the unit-testable surface either way.
# =====================================================================
def build_server() -> Any:
    """Build and return a FastMCP server instance with the 13 eq tools."""
    if not MCP_AVAILABLE:
        raise RuntimeError(
            "Python MCP SDK (`mcp`) is not installed. "
            "Install it with: pip install 'mcp>=0.9,<2'"
        )

    mcp = FastMCP(  # type: ignore[misc]
        name="task-eq",
        instructions=(
            "TASK/EQ equilibrium MCP server. "
            "Call `init` first, configure parameters with `set_param` "
            "/ `set_param_str` / `set_params`, optionally run "
            "`validate` to check the configuration, execute the "
            "equilibrium load with `run`, and read state with "
            "`get_state`. Use `describe_parameters` to discover valid "
            "parameter names. `run_and_get_state` is a convenience "
            "one-shot wrapper. EQ-specific note: PSIB is 0-origin "
            "(PSIB[0]..PSIB[5]); all other 1D arrays are 1-origin."
        ),
    )

    @mcp.tool()
    def init() -> str:
        """Initialize the eq library with its default parameters.

        Call this once before any other tool. If the library is already
        open, this is a no-op. Subsequent explicit calls after
        `finalize` re-initialize to defaults.
        """
        return handle_init()

    @mcp.tool()
    def set_param(name: str, value: float) -> str:
        """Set an eq numeric parameter by name.

        Use ``NAME[i]`` for array elements. PSIB is 0-origin
        (``PSIB[0]``..``PSIB[5]``); RIPFC / RPFC / ZPFC / WPFC are
        1-origin. For string parameters (KNAMEQ etc.) use
        ``set_param_str`` instead.
        See `describe_parameters` for the full registry.
        """
        return handle_set_param(name, value)

    @mcp.tool()
    def set_param_str(name: str, value: str) -> str:
        """Set an eq string-valued parameter (KNAMEQ etc.).

        Supported names: ``KNAMEQ, KNAMEQ2, KNAMWR, KNAMWM, KNAMFP,
        KNAMFO, KNAMPF`` (CHARACTER(LEN=80) on the Fortran side).
        """
        return handle_set_param_str(name, value)

    @mcp.tool()
    def save(path: str) -> str:
        """Save the current equilibrium to a TASK-binary file at ``path``.

        The path is set as KNAMEQ before calling eq_save. The file is
        consumable by tr_mcp via ``set_param_str("KNAMEQ", path)`` plus
        ``MODELG=3``. Note: the underlying Fortran ``EQSAVE`` silently
        swallows FWOPEN failures (blank KNAMEQ, missing directory,
        permission denied) — callers should verify file existence after
        the call.
        """
        return handle_save(path)

    @mcp.tool()
    def set_params(params: Dict[str, Any]) -> str:
        """Bulk-set eq parameters.

        ``params`` values may be:
        * a number (scalar)
        * a list/tuple (1-origin array, all elements applied)
        * a dict ``{index: value}`` (sparse array; use this for the
          0-origin ``PSIB`` because lists implicitly start at 1)
        * a string (for KNAMEQ and similar string-valued parameters)
        """
        return handle_set_params(params)

    @mcp.tool()
    def run(mode: int = 1) -> str:
        """Execute ``eq_run`` (equilibrium load / solve).

        ``mode=1`` (default) performs the real EQDSK load via
        ``equnit::eq_load`` using the current ``MODELG`` + ``KNAMEQ``.

        ``mode=0`` runs the in-process analytic Grad-Shafranov solve
        (``EQCALC`` + ``EQCALQ``); use it with ``MODELG=2`` and the
        basic geometry parameters (``RR``, ``RA``, ``BB``, ``RIP``,
        ``RKAP``, ``RDLT``, ...) to produce a self-consistent
        equilibrium without any external EQDSK file.
        """
        return handle_run(mode)

    @mcp.tool()
    def get_state() -> Dict[str, Any]:
        """Return the current equilibrium state.

        Returns a dict with grid counters (``NRGMAX``, ``NZGMAX``,
        ``NPSMAX``, ``NRMAX``, ``NTHMAX``, ``NSUMAX``, ``NRVMAX``,
        ``NSGMAX``, ``NTGMAX``), 12 plasma ``scalars`` (RAXIS, ZAXIS,
        PSI0, PSIPA, PSITA, QAXIS, QSURF, BETAT, BETAP, PVOL, RAAVE,
        RIPX), grid coordinates (``RG``, ``ZG``), psi-surface profiles
        (``PSIPS`` / ``PPPS`` / ``TTPS`` / ``QQPS``), and a per-NR
        ``profile`` array of 7 columns (PSIP, PSIT, PPS, TTS, QPS,
        VPS, RST). Schema also available via `describe_state_schema`.
        """
        return handle_get_state()

    @mcp.tool()
    def get_psi_rz() -> Dict[str, Any]:
        """Return the 2-D PSI(R,Z) field plus the RG/ZG grid coordinates.

        Output shape:
            ``{"nrg": int, "nzg": int, "rg": list[float], "zg": list[float],
               "psi_rz": list[list[float]]}``  (psi_rz indexed [i_r][i_z],
            runtime active grid only — default 33×33)

        Note: PSI is populated by ``run()``; calling get_psi_rz before run
        returns whatever is in the buffer (typically zeros on a fresh init).
        """
        return handle_get_psi_rz()

    @mcp.tool()
    def validate() -> List[Dict[str, Any]]:
        """Run pre-run cross-parameter validation (Issue #143).

        Returns a list of diagnostics; each entry has ``param``,
        ``code`` (see ``eqlib.EqDiagCode``), and ``message``. An empty
        list means the current eq state will not trip any validator;
        a non-empty list means run will likely fail unless the listed
        issues are fixed first.
        """
        return handle_validate()

    @mcp.tool()
    def finalize() -> str:
        """Release eq library resources.

        Safe to call multiple times. After finalize, any data-returning
        tool will auto-reinitialize the library.
        """
        return handle_finalize()

    @mcp.tool()
    def describe_parameters() -> Dict[str, Any]:
        """Return the list of supported eq parameters.

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
        mode: int = 1,
    ) -> Dict[str, Any]:
        """Convenience: init + set_params + run + get_state in one call.

        Equivalent to::

            init()
            set_params(params)
            run(mode)
            return get_state()
        """
        return handle_run_and_get_state(params, mode)

    return mcp


def main(argv: Optional[List[str]] = None) -> int:
    """Console-script entry point.

    Runs the FastMCP stdio server. Exits cleanly on SIGINT.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(
            "eq-mcp — Model Context Protocol server for TASK/EQ\n"
            "\n"
            "Usage:\n"
            "  python -m eq_mcp.server    # run over stdio (default)\n"
            "  eq-mcp                     # same, via installed script\n"
            "  eq-mcp --help              # show this help\n"
            "  eq-mcp --print-tools       # list registered tools\n"
            "\n"
            "Environment:\n"
            "  EQLIB_PATH   override path to libeqapi.so\n"
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
                "save",
                "set_params",
                "run",
                "get_state",
                "get_psi_rz",
                "validate",
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

    # Install the fd isolation now -- NOT at import time (#227 item 1).
    # Everything above this point (--help, --print-tools, the MCP-missing
    # error path) returns before we touch the host process's fds.
    _install_fd_isolation()

    server = build_server()
    # FastMCP >=0.9 exposes .run() for stdio transport by default.
    server.run()
    # Skip Python teardown (Eq.__del__ → eq_finalize → potential SIGABRT) by
    # using os._exit.  The MCP session is complete at this point; clean
    # Fortran shutdown is not required.  Flush sys.stdout (the saved
    # JSON-RPC pipe fd) before bypassing Python teardown.
    try:
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
