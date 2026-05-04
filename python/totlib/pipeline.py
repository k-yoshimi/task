"""TotPipeline — Python-side scalar coupling orchestrator (L-7a).

Spec: docs/superpowers/specs/2026-04-28-l7a-cross-module-coupling-design.md

This module composes existing per-module wrappers (Fplib, Trlib, ...)
to form a multi-step pipeline with hardcoded scalar coupling rules.
It does NOT touch libtotapi.so — that path is handled by the legacy
totlib.Tot class and remains untouched at L-7a.
"""

import importlib
import math

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ExceptionGroup is a Python 3.11+ builtin. The exceptiongroup PyPI
# package back-ports it to 3.10. Fall back to None if neither is
# available (close() then degrades to raising errors[0] only — same
# pre-fix behavior, slightly less informative).
try:
    ExceptionGroup  # type: ignore[name-defined]  # builtin on 3.11+
except NameError:  # pragma: no cover  # Python 3.10 path
    try:
        from exceptiongroup import ExceptionGroup  # type: ignore[no-redef]  # backport
    except ImportError:  # pragma: no cover
        ExceptionGroup = None  # type: ignore[assignment]

from .errors import (
    TotPipelineCouplingError,
    TotPipelineLifecycleError,
    TotPipelineRunError,
    TotPipelineUnknownModuleError,
)


@dataclass(frozen=True)
class CouplingRule:
    """A single source-to-sink scalar coupling between adjacent steps.

    Frozen so the registry can be hashable in the future (rule dedup,
    set-based lookups) and to prevent accidental mutation by callers.

    Two kinds of rules are supported:

    * kind="transfer" (default): runs src_state_key on the previous
      step's state, applies transform, and pushes via set_param to
      the current module. All three of src_state_key/dst_param/
      transform are required.
    * kind="verify" (L-7b-ii): runs verify(curr_inst) and raises
      TotPipelineCouplingError if False. Only the verify callable
      is required; src_state_key/dst_param/transform are ignored.

    src_state_key (transfer-kind only) resolves a value from the source
    module's get_state():

    * str  -> looked up in prev_state.scalars (only valid for modules
      that expose a .scalars dict — Tr/Eq/Wr/Wrx/Ti).
    * callable(prev_state, params) -> float. params is TotPipeline._params,
      a dict of every set_param call so far keyed as "<ns>:<bare>" (used
      by fp's compute_rjt_volint which needs tr's RR/RA).

    dst_param is the bare parameter name on the sink module (set via
    sink.set_param). transform is applied to the source value (e.g. unit
    conversion) before it reaches the sink.
    """
    # Transfer-rule fields (required when kind="transfer").
    src_state_key: Optional[Union[str, Callable[[Any, Dict[str, Any]], float]]] = None
    dst_param: Optional[str] = None
    transform: Optional[Callable[[float], float]] = None
    doc: str = ""
    # L-7b-ii: kind dispatch + verify-only callable.
    kind: str = "transfer"
    verify: Optional[Callable[[Any], bool]] = None
    #   verify(dst_inst) -> bool; only consulted when kind == "verify"

    def __post_init__(self):
        if self.kind == "transfer":
            missing = [
                name for name, val in (
                    ("src_state_key", self.src_state_key),
                    ("dst_param",     self.dst_param),
                    ("transform",     self.transform),
                ) if val is None
            ]
            if missing:
                raise ValueError(
                    f"transfer-kind CouplingRule missing required "
                    f"fields: {missing}"
                )
        elif self.kind == "verify":
            if self.verify is None:
                raise ValueError(
                    "verify-kind CouplingRule requires verify callable"
                )
        else:
            raise ValueError(f"unknown CouplingRule.kind: {self.kind!r}")


@dataclass
class PipelineStep:
    """Snapshot of one completed pipeline step."""

    module: str
    scalars: Dict[str, float]
    coupling_applied: List[str]


@dataclass
class PipelineResult:
    """Aggregated result from a run_pipeline call."""

    steps: List[PipelineStep] = field(default_factory=list)

    def last(self, module: str) -> PipelineStep:
        """Return the most recent step for the given module name.

        Raises KeyError if the module never ran in this result.
        """
        for step in reversed(self.steps):
            if step.module == module:
                return step
        raise KeyError(module)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for MCP transport.

        For repeated modules, later steps overwrite earlier in the
        flat per-module map; the full timeline is preserved under
        the "_steps" key. Inner dicts/lists are defensive copies so
        callers (e.g. the MCP `run_pipeline` tool that may add metadata
        or filter scalars before transport) cannot mutate the originating
        PipelineStep.
        """
        out: Dict[str, Any] = {}
        for step in self.steps:
            out[step.module] = dict(step.scalars)  # defensive copy
        out["_steps"] = [
            {
                "module": s.module,
                "scalars": dict(s.scalars),               # defensive copy
                "coupling_applied": list(s.coupling_applied),  # defensive copy
            }
            for s in self.steps
        ]
        return out


def _state_to_scalars(state) -> Dict[str, float]:
    """Extract a flat dict of numeric scalars from any module's state.

    Modules that expose state.scalars dict (Tr, Eq, Wr, Wrx, Ti) — return
    a shallow copy. Modules that don't (Fp) — extract numeric top-level
    dataclass attributes (excluding bool, str, and non-numeric).

    Per spec §5.3. Required because FpState lacks the uniform .scalars
    dict the spec originally assumed (R1/R2 finding).
    """
    if hasattr(state, "scalars") and isinstance(state.scalars, dict):
        return dict(state.scalars)
    out: Dict[str, float] = {}
    for name in dir(state):
        if name.startswith("_"):
            continue
        val = getattr(state, name, None)
        if callable(val):
            continue
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            out[name] = float(val)
    return out


_MODULE_REGISTRY: Dict[str, Tuple[str, str, str]] = {
    # name : (package, wrapper_class, base_error_class)
    "fp":  ("fplib",  "Fplib",  "FplibError"),
    "tr":  ("trlib",  "Trlib",  "TrlibError"),
    "eq":  ("eqlib",  "Eq",     "EqlibError"),
    "wr":  ("wrlib",  "Wrlib",  "WrlibError"),
    "wrx": ("wrxlib", "Wrxlib", "WrxlibError"),
    "ti":  ("tilib",  "TiLib",  "TilibError"),    # NB: wrapper class TiLib (capital L) but TilibError
}


def _import_wrapper(name: str):
    """Lazy-import the per-module wrapper class for `name`.

    Only modules actually used in a pipeline are loaded (matters on
    macOS where wr/wrx may not have buildable lib*.so). Raises
    TotPipelineUnknownModuleError if name is not in _MODULE_REGISTRY.
    """
    if name not in _MODULE_REGISTRY:
        raise TotPipelineUnknownModuleError(
            f"unknown module {name!r}; expected one of {sorted(_MODULE_REGISTRY)}"
        )
    pkg, cls_name, _ = _MODULE_REGISTRY[name]
    return getattr(importlib.import_module(pkg), cls_name)


def _import_module_error(name: str) -> type:
    """Lazy-import the base error class for module `name`.

    Same lazy pattern as _import_wrapper — only the errors.py for the
    requested module is imported. Used by run_pipeline to determine
    which exceptions to catch + wrap as TotPipelineRunError.
    """
    if name not in _MODULE_REGISTRY:
        raise TotPipelineUnknownModuleError(
            f"unknown module {name!r}; expected one of {sorted(_MODULE_REGISTRY)}"
        )
    pkg, _, err_cls_name = _MODULE_REGISTRY[name]
    errors_mod = importlib.import_module(f"{pkg}.errors")
    return getattr(errors_mod, err_cls_name)


def compute_rjt_volint(state, *, R0: float, a: float) -> float:
    """fp's driven current as a scalar [Amperes]: integral of RJT(rho) dA_pol.

    Per spec §8 R2: fp stores RJT in [MA/m^2] on a uniform rho-grid in [0,1]
    with NRMAX cells. The poloidal cross-section element is
        dA_pol(NR) = 2*pi * rho_mid * a^2 * drho
    matching fp's VOLR/(2*pi*R0). Sums over species (matches fp's
    rtotalIP = sum_NSA PIT). R0 is unused in the area integral but kept
    in the signature for symmetry with future toroidal-volume variants.

    Args:
        state: FpState (from fplib.Fplib.get_state()). Reads .RJT[ns][i],
            .nrmax, .nsamax.
        R0: major radius [m]. Sourced from tr.RR (set via tot.set_param("tr:RR", ...)).
        a: minor radius [m]. Sourced from tr.RA (R3 confirmed RA, not RB —
            fp's rho mesh is RA-normalized per fp/fpcale.f90:34,56).

    Returns:
        Driven current in Amperes (positive → co-current direction).
    """
    nr = state.nrmax
    if nr < 1:
        return 0.0
    drho = 1.0 / nr
    total = 0.0
    for ns in range(state.nsamax):
        for i in range(nr):
            rho_mid = (i + 0.5) * drho
            dA_pol = 2.0 * math.pi * rho_mid * (a ** 2) * drho
            total += state.RJT[ns][i] * 1.0e6 * dA_pol  # MA/m^2 -> A/m^2
    _ = R0  # unused in area integral; reserved for future toroidal extension
    return total


# ------------------------------------------------------------------
# Coupling rule registry
# ------------------------------------------------------------------
# L-7b-i: ('fp','tr') uses the physical EXTERNAL_DRIVEN_I scalar [MA]
# (Gaussian-profile injection in trprf). Future L-7b-ii will add more pairs
# (('wr','fp'), ('wr','tr'), ('eq','tr'), ...) via BPSD broker without
# changing the orchestrator code.

COUPLING_RULES: Dict[Tuple[str, str], List[CouplingRule]] = {
    ("fp", "tr"): [
        CouplingRule(
            # Callable: receives (prev_state, params); pulls tr:RR / tr:RA
            # from params (set via tot.set_param("tr:RR", ...) before run_pipeline).
            src_state_key=lambda state, params: compute_rjt_volint(
                state,
                R0=params["tr:RR"],
                a=params["tr:RA"],
            ),
            dst_param="EXTERNAL_DRIVEN_I",      # MA, injected as Gaussian profile in trprf
            transform=lambda v: v * 1e-6,       # Amperes -> MA
            doc="fp driven current (RJT volume integral, A) -> tr EXTERNAL_DRIVEN_I (MA)",
        ),
    ],
    # NOTE (L-7b-ii, 2026-05-04): ('eq','tr') verify ルールは保留。
    #   spec は BPSD を eq/tr 間の共有ブローカーとして扱う前提だったが、
    #   実装の `libeqapi.so` と `libtrapi.so` はそれぞれ独立した .so で、
    #   `nm` で確認したとおり `___bpsd_equ1d_MOD_equ1dx` 等は各 .so 内
    #   private な module-level 変数 (static linkage)。よって libeqapi.so
    #   側で `bpsd_put_equ1D` しても libtrapi.so 側の equ1Dx は更新されず、
    #   `Trlib.check_bpsd_pull()` は常に False。spec の前提が成立しない。
    #
    #   verify ディスパッチ (kind="verify") の機構自体は本 PR で導入済み
    #   (Layer A モックテストで網羅) なので、共有 .so / IPC / プロセス間
    #   broker といった解決方針が決まり次第ルールを追加できる骨組みは
    #   揃っている。詳細は spec §後続検討、および
    #   `python/totlib/README.md` の Coupling rules 節を参照。
}


class TotPipeline:
    """Python-side multi-module orchestrator with scalar coupling.

    Lazy-instantiates per-module wrappers (Fplib, Trlib, ...) only when
    referenced by set_param or run_pipeline. Coupling between adjacent
    steps follows COUPLING_RULES (populated in Task 1.5 / 2.2).

    Mutually exclusive with the legacy totlib.Tot class — both call
    tr_init internally and same-process coexistence is undefined.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, Any] = {}
        # Track every set_param call, indexed by namespaced key. Used by
        # CouplingRule callables that need cross-module context (e.g. fp's
        # compute_rjt_volint needs tr's RR/RA). Per spec §5.4.
        self._params: Dict[str, Any] = {}
        self._closed: bool = False

    def __enter__(self) -> "TotPipeline":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _ensure_module(self, name: str):
        if self._closed:
            raise TotPipelineLifecycleError("TotPipeline is closed")
        if name not in self._modules:
            cls = _import_wrapper(name)
            self._modules[name] = cls()
        return self._modules[name]

    def set_param(self, namespaced: str, value) -> None:
        """Set a per-module parameter via 'module:name' addressing.

        E.g. set_param('fp:NSAMAX', 2). String values are routed to
        set_param_str on the sink wrapper; numeric values to set_param.

        Note: only fp/tr/eq currently expose set_param_str; wr/wrx/ti
        accept numeric params only. Passing a string value to one of
        those raises TotPipelineCouplingError (rather than a bare
        AttributeError leaking out of getattr).

        Records the value into self._params after the wrapper accepts
        it (failed validation in the wrapper keeps _params consistent).
        """
        if self._closed:
            raise TotPipelineLifecycleError("TotPipeline is closed")
        if ":" not in namespaced:
            raise TotPipelineCouplingError(
                f"param name must be prefixed with '<module>:', got {namespaced!r}"
            )
        ns, bare = namespaced.split(":", 1)
        module = self._ensure_module(ns)
        # bool is a subclass of int in Python, so it would silently take
        # the numeric branch and become 1.0/0.0 — semantically lossy.
        # Reject explicitly so callers must be deliberate.
        if isinstance(value, bool):
            raise TotPipelineCouplingError(
                f"set_param: bool value not accepted (would silently coerce to "
                f"{float(value)}); pass an explicit float/int. Got {namespaced!r}={value!r}"
            )
        if isinstance(value, str):
            setter = getattr(module, "set_param_str", None)
            if setter is None:
                raise TotPipelineCouplingError(
                    f"module {ns!r} does not accept string parameters "
                    f"(set_param_str not defined); got {namespaced!r}={value!r}"
                )
            setter(bare, value)
            self._params[namespaced] = value
        else:
            # Store the coerced value so coupling rules reading self._params
            # see the same scalar the wrapper actually received.
            coerced = float(value)
            module.set_param(bare, coerced)
            self._params[namespaced] = coerced

    def close(self) -> None:
        """Finalize all opened module wrappers. Idempotent. If any close
        raises, all remaining modules are still finalized; on a single
        failure the original exception is re-raised, on multiple failures
        an ExceptionGroup carrying every collected error is raised so no
        cleanup failure is silently dropped."""
        if self._closed:
            return
        errors = []
        for name, module in list(self._modules.items()):
            try:
                module.close()
            except Exception as e:  # noqa: BLE001 — caller wants to see all
                errors.append(e)
        self._modules.clear()
        self._closed = True
        if len(errors) == 1:
            raise errors[0]
        if errors:
            if ExceptionGroup is None:
                # Python 3.10 without the backport — surface the first
                # error and lose visibility on the rest. Same as pre-fix.
                raise errors[0]
            raise ExceptionGroup(
                f"{len(errors)} module(s) failed to close", errors
            )

    @staticmethod
    def _validate_steps(steps) -> None:
        """Pre-flight: reject malformed steps before any side effects."""
        if not steps:
            raise TotPipelineCouplingError("steps must be non-empty")
        for i, item in enumerate(steps):
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise TotPipelineCouplingError(
                    f"steps[{i}] must be (module_name, kwargs) sequence of length 2, got {item!r}"
                )
            name, kwargs = item
            if name not in _MODULE_REGISTRY:
                raise TotPipelineUnknownModuleError(
                    f"steps[{i}].module = {name!r}; expected one of "
                    f"{sorted(_MODULE_REGISTRY)}"
                )
            if not isinstance(kwargs, dict):
                raise TotPipelineCouplingError(
                    f"steps[{i}].kwargs must be dict, got {type(kwargs).__name__}"
                )

    def _extract_source(self, prev_state, rule: CouplingRule) -> float:
        """Resolve a rule's source value from the previous module's state.

        - If src_state_key is a callable, invoke it with (prev_state, self._params).
          The params dict carries every set_param call so the rule can pull
          cross-module context (e.g. fp's compute_rjt_volint needs tr's RR/RA).
        - If src_state_key is a string, look it up in
          _state_to_scalars(prev_state) — handles both .scalars-bearing modules
          and FpState's top-level attribute layout.
        Wraps lookup/computation errors as TotPipelineCouplingError.
        """
        if callable(rule.src_state_key):
            try:
                return float(rule.src_state_key(prev_state, self._params))
            except Exception as e:
                raise TotPipelineCouplingError(
                    f"source extraction failed for rule {rule.doc!r}: "
                    f"{type(e).__name__}: {e}"
                ) from e
        try:
            scalars = _state_to_scalars(prev_state)
            return float(scalars[rule.src_state_key])
        except KeyError as e:
            raise TotPipelineCouplingError(
                f"source state key {rule.src_state_key!r} missing from "
                f"prev_state scalars; rule: {rule.doc!r}"
            ) from e
        except Exception as e:
            raise TotPipelineCouplingError(
                f"source extraction failed for rule {rule.doc!r}: "
                f"{type(e).__name__}: {e}"
            ) from e

    def run_pipeline(self, steps) -> PipelineResult:
        """Run the given module steps in order, applying COUPLING_RULES
        between adjacent (prev, current) pairs.

        Returns a PipelineResult. Per-module exceptions during execution
        are wrapped as TotPipelineRunError exposing partial_result.
        """
        if self._closed:
            raise TotPipelineLifecycleError("TotPipeline is closed")
        self._validate_steps(steps)

        result_steps: List[PipelineStep] = []
        prev_name = None
        prev_state = None

        for i, (name, kwargs) in enumerate(steps):
            # The catch below is broad on purpose: any Exception during step
            # execution (per-module domain error, TypeError from bad kwargs,
            # etc.) is wrapped as TotPipelineRunError so partial_result is
            # always available to the caller. Keyboard/system signals are NOT
            # caught.
            try:
                module = self._ensure_module(name)
                applied: List[str] = []

                if prev_name is not None:
                    for rule in COUPLING_RULES.get((prev_name, name), []):
                        if rule.kind == "transfer":
                            # __post_init__ guarantees src_state_key/dst_param/
                            # transform are non-None for kind="transfer", so the
                            # asserts below are type-narrowing for static checkers
                            # (mypy/pyright); they are unreachable at runtime.
                            raw = self._extract_source(prev_state, rule)
                            assert rule.transform is not None    # type narrowing
                            assert rule.dst_param is not None    # type narrowing
                            try:
                                transformed = rule.transform(raw)
                            except Exception as e:
                                raise TotPipelineCouplingError(
                                    f"transform failed for rule {rule.doc!r}: {e}"
                                ) from e
                            module.set_param(rule.dst_param, transformed)
                            # Record the injected value so subsequent rules can see it
                            # (mirrors set_param's _params bookkeeping).
                            self._params[f"{name}:{rule.dst_param}"] = transformed
                            applied.append(rule.doc)
                        elif rule.kind == "verify":
                            assert rule.verify is not None    # type narrowing (see transfer branch)
                            try:
                                ok = rule.verify(module)   # module = curr_inst
                            except Exception as e:
                                raise TotPipelineCouplingError(
                                    f"verify failed: rule {rule.doc!r} for "
                                    f"{prev_name}->{name} raised "
                                    f"{type(e).__name__}: {e}"
                                ) from e
                            if not ok:
                                callable_repr = getattr(
                                    rule.verify, "__qualname__", repr(rule.verify)
                                )
                                raise TotPipelineCouplingError(
                                    f"verify failed: rule {rule.doc!r} ({callable_repr}) "
                                    f"for {prev_name}->{name} returned False "
                                    f"(likely cause: upstream step did not push expected "
                                    f"data to BPSD broker; check pipeline order and "
                                    f"MODELG setting)"
                                )
                            applied.append(rule.doc)   # only on success

                module.run(**kwargs)
                cur_state = module.get_state()
                # _state_to_scalars adapter handles fp (no .scalars) and tr (.scalars dict) uniformly.
                result_steps.append(PipelineStep(
                    module=name,
                    scalars=_state_to_scalars(cur_state),
                    coupling_applied=applied,
                ))
                prev_name, prev_state = name, cur_state
            except Exception as e:  # noqa: BLE001 — see comment above
                raise TotPipelineRunError(
                    f"step {i} ({name}) failed: {e}",
                    partial_result=PipelineResult(steps=result_steps),
                    failed_step_index=i,
                    failed_module=name,
                ) from e

        return PipelineResult(steps=result_steps)
